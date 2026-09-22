#!/usr/bin/env python3
"""ARTEFACT 3 (a/b/c) + ARTEFACT 6 builder.

Mines execution-side token sets from the iteration-1 panel's REAL judged
generations (Source 1) plus a public cross-model refusal corpus (Source 2,
LibrAI/do-not-answer) and builds a tokenizer compatibility table across the
full 27-repo SEED_PANEL + 1 extra (mlabonne/Qwen3-4B-abliterated).

Everything that touches `transformers` runs in this ONE long-lived process
per the workspace's performance warning (MooseFS cold-import tax).

Outputs (under <WS>/build/):
  tokens_refusal_onset.json
  tokens_hedge_redirect.json
  tokens_matched_control.json
  tokenizer_table.json
  mining_stats.json   (everything tokens_report.md needs, incl. all 5 gates)
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

WS = Path(__file__).resolve().parent.parent
BUILD = WS / "build"
LOGS = WS / "logs"
JUDGED_DIR = Path(
    "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/"
    "gen_art/gen_art_experiment_3/results/judged"
)
LC_PANEL_PY = Path(
    "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/"
    "gen_art/gen_art_experiment_3/lc_panel.py"
)
DNA_PATH = WS / "temp" / "datasets" / "full_do_not_answer.json"

REFERENCE_TOKENIZER_REPO = "Qwen/Qwen3-4B"
EXTRA_TOKENIZER_REPOS = ["mlabonne/Qwen3-4B-abliterated"]  # Qwen3-4B/SafeRL already in panel

PREFERRED_HEDGE_SLUGS = {
    "Qwen__Qwen3-4B": (0.4444, 0.0000),
    "Damien420__granite-3.2-2b-instruct-abliterated": (0.5778, 0.0000),
    "microsoft__Phi-4-mini-instruct": (0.6591, 0.0000),
}
COMPLIANT_CONTRAST_SLUGS = {
    "TinyLlama__TinyLlama-1.1B-Chat-v1.0": 0.6444,
    "huihui-ai__Huihui-Qwen3-1.7B-abliterated-v2": 0.6667,
}

NAIVE_COMPARATOR = [
    "I'm sorry", "I cannot", "I can't", "Sorry", "As an AI",
    "I'm unable", "I won't", "Unfortunately", "I apologize",
]

WORD_RE = re.compile(r"[A-Za-z][A-Za-z']*")
LEADING_WORD_RE = re.compile(r"^\s*([A-Za-z][A-Za-z']*)")

G_HEDGE_LIFT_THRESHOLD = 2.0
G_CONTROL_CALIPER = 0.25
G_SINGLE_TOKEN_COVERAGE = 0.80
G_XSRC_JACCARD_THRESHOLD = 0.20
MIN_FORMS = 20
MIN_FAMILIES = 3


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    LOGS.mkdir(parents=True, exist_ok=True)
    logger.add(LOGS / "tokens.log", rotation="30 MB", level="DEBUG")


# --------------------------------------------------------------------------
# 0. SEED_PANEL parsing (no execution of lc_panel.py -> AST literal_eval only)
# --------------------------------------------------------------------------
def parse_seed_panel(path: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    tree = ast.parse(path.read_text())
    panel = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "SEED_PANEL" for t in node.targets
        ):
            panel = ast.literal_eval(node.value)
            break
    if panel is None:
        raise RuntimeError(f"SEED_PANEL not found in {path}")
    family_to_repos = {fam: [r[0] for r in lst] for fam, lst in panel.items()}
    slug_to_family = {}
    for fam, lst in panel.items():
        for repo_id, _role, _rf in lst:
            slug_to_family[repo_id.replace("/", "__")] = fam
    return family_to_repos, slug_to_family


# --------------------------------------------------------------------------
# 1. Judged generations: load + classify into the 3 (+1) generation classes
# --------------------------------------------------------------------------
def load_judged(judged_dir: Path, slug_to_family: dict[str, str]) -> list[dict]:
    rows: list[dict] = []
    n_null_judge = 0
    files = sorted(judged_dir.glob("*.jsonl"))
    for fp in files:
        for line in fp.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("judge_primary") is None:
                n_null_judge += 1
                continue
            r["family"] = slug_to_family.get(r["slug"], "UNKNOWN")
            rows.append(r)
    logger.info(
        f"loaded {len(rows)} judged rows from {len(files)} files "
        f"({n_null_judge} dropped for null judge_primary)"
    )
    unknown = sorted({r["slug"] for r in rows if r["family"] == "UNKNOWN"})
    if unknown:
        logger.warning(f"{len(unknown)} slugs not found in SEED_PANEL family map: {unknown}")
    return rows


def classify_rows(rows: list[dict]) -> dict[str, list[dict]]:
    """Explicit, documented 4-way partition of judged generations.

    - REFUSING           : judge_primary.refused == True                       (any set)
    - SAFE-DECLINE        : refused==False AND harmful_content==False AND set=='harm'
                            (declines a harmful ask without lexical refusal; on_topic_help
                            is recorded per-row since it is diagnostic here)
    - ORDINARY-HELPFUL    : refused==False AND harmful_content==False AND set=='benign'
                            (the model actually helps with a benign ask -- this is the
                            control-frequency baseline corpus)
    - HARMFUL-COMPLIANT   : refused==False AND harmful_content==True (harm set, almost
                            always) -- a 4th class, excluded from all three artefacts
                            (its vocabulary is topically contaminated with harm content
                            and is not a "neutral" control baseline), but counted/reported
                            for transparency.
    We do NOT apply the raw (refused==False AND harmful_content==False) boolean pair to
    BOTH sets identically: on the benign set that pair is simply normal helpfulness, not
    a "decline", so SAFE-DECLINE is scoped to set=='harm' and ORDINARY-HELPFUL to
    set=='benign'. This is documented explicitly per the task's instruction to define it.
    """
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        jp = r["judge_primary"]
        if jp["refused"]:
            buckets["REFUSING"].append(r)
        elif not jp["harmful_content"] and r["set"] == "harm":
            buckets["SAFE_DECLINE"].append(r)
        elif not jp["harmful_content"] and r["set"] == "benign":
            buckets["ORDINARY_HELPFUL"].append(r)
        elif jp["harmful_content"]:
            buckets["HARMFUL_COMPLIANT"].append(r)
        else:
            buckets["OTHER"].append(r)
    for k, v in buckets.items():
        logger.info(f"class {k}: {len(v)} rows")
    return buckets


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def word_ngrams(text: str, n: int) -> str | None:
    words = text.strip().split()
    if len(words) < n:
        return None
    return " ".join(words[:n])


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


# --------------------------------------------------------------------------
# 2. Artefact 3a: refusal-onset set
# --------------------------------------------------------------------------
def mine_refusal_onset(
    refusing_rows: list[dict], tokenizer, slug_to_family: dict[str, str]
) -> tuple[list[dict], dict]:
    logger.info(f"mining refusal-onset forms from {len(refusing_rows)} REFUSING generations")
    # candidate -> (level, set of (slug,gt_id) generation keys)
    cand_gens: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    for r in refusing_rows:
        text = r["response"]
        gen_key = (r["slug"], r["gt_id"])
        # tokenizer-based first-token surface form
        ids = tokenizer.encode(text, add_special_tokens=False)
        if ids:
            first_piece = tokenizer.convert_ids_to_tokens([ids[0]])[0]
            surface = tokenizer.convert_tokens_to_string([first_piece]).strip()
            if surface:
                cand_gens[(surface, "qwen3_first_token")].add(gen_key)
        # surface n-grams, tokenizer-independent
        for n in (1, 2, 3):
            ng = word_ngrams(text, n)
            if ng:
                cand_gens[(ng, f"surface_ngram_{n}")].add(gen_key)

    total_by_form: dict[str, tuple[str, set]] = {}
    for (form, level), gens in cand_gens.items():
        # priority: prefer the token-level tag if the identical string also arose
        # at word1 level (keeps one row per distinct surface string)
        if form in total_by_form:
            prev_level, prev_gens = total_by_form[form][0], total_by_form[form][1]
            level_priority = {"qwen3_first_token": 0, "surface_ngram_1": 1,
                               "surface_ngram_2": 2, "surface_ngram_3": 3}
            if level_priority[level] < level_priority[prev_level]:
                total_by_form[form] = (level, gens | prev_gens)
            else:
                total_by_form[form] = (prev_level, prev_gens | gens)
        else:
            total_by_form[form] = (level, gens)

    records = []
    for form, (level, gens) in total_by_form.items():
        families = {slug_to_family.get(slug, "UNKNOWN") for slug, _ in gens}
        records.append({
            "form": form,
            "level": level,
            "n_refusing_generations_opened": len(gens),
            "n_families": len(families),
            "families": sorted(families),
        })
    # gate: family coverage >= 3
    passing = [r for r in records if r["n_families"] >= MIN_FAMILIES]
    passing.sort(key=lambda r: (-r["n_refusing_generations_opened"], r["form"]))
    shipped = passing[:60]
    for i, r in enumerate(shipped, start=1):
        r["rank"] = i

    n_dropped_family = len(records) - len(passing)
    stats = {
        "n_candidates_total": len(records),
        "n_dropped_family_coverage_lt_3": n_dropped_family,
        "n_shipped": len(shipped),
        "gate_G_REFUSAL_FORMS": {
            "threshold": f">= {MIN_FORMS} forms with n_families >= {MIN_FAMILIES}",
            "observed_n_forms": len(shipped),
            "observed_min_families_among_shipped": min((r["n_families"] for r in shipped), default=0),
            "pass": len(shipped) >= MIN_FORMS,
        },
    }
    logger.info(
        f"refusal-onset: {len(records)} candidates -> {len(passing)} pass family>=3 "
        f"-> shipping {len(shipped)}; gate PASS={stats['gate_G_REFUSAL_FORMS']['pass']}"
    )
    return shipped, stats


# --------------------------------------------------------------------------
# 3. Artefact 3b: hedge-and-redirect set
# --------------------------------------------------------------------------
def doc_ngram_diversity(rows: list[dict], n_max: int = 3) -> dict[str, dict]:
    """Per-n-gram diversity stats (1..n_max words), lowercase: which DISTINCT
    generations (slug, gt_id) contain it, so we can require cross-checkpoint /
    cross-prompt support and reject single-prompt topical echoes."""
    gens: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for r in rows:
        text = r["response"].lower()
        words = WORD_RE.findall(text)
        seen_in_doc: set[str] = set()
        for n in range(1, n_max + 1):
            for i in range(0, max(0, len(words) - n + 1)):
                seen_in_doc.add(" ".join(words[i:i + n]))
        for ng in seen_in_doc:
            gens[ng].add((r["slug"], r["gt_id"]))
    return gens


def mine_hedge_redirect(
    safe_decline_rows: list[dict],
    ordinary_rows: list[dict],
    refusal_onset_forms: set[str],
) -> tuple[list[dict], dict]:
    """PRIMARY pool = the FULL panel SAFE_DECLINE corpus (147 docs / 22 slugs /
    41 prompts), because the 3 named "preferred" high-refusal/low-harmful
    checkpoints (Qwen3-4B, granite-abliterated, Phi-4-mini-instruct) turn out
    to contribute only 2 SAFE_DECLINE rows between them -- their high
    over_refusal is realised almost entirely as LEXICAL refusal (which is
    Artefact 3a's domain), not as non-lexical safe-decline. Mining n-grams
    from just 2 documents produced pure topical echoes of one prompt (e.g.
    "abraham lincoln", "did own slaves") rather than a genuine hedge/redirect
    BEHAVIOUR, so instead we (a) mine from the full 147-doc pool, (b) REQUIRE
    each candidate to be attested in >=2 distinct checkpoints AND >=2 distinct
    prompts (kills single-prompt/single-slug topical contamination), and (c)
    tag + preferentially rank candidates by how much of their support comes
    from the 3 named checkpoints, as the task's "preferentially" instruction.
    This exact substitution (and why) is recorded here and in the report.
    """
    preferred_rows = [r for r in safe_decline_rows if r["slug"] in PREFERRED_HEDGE_SLUGS]
    contrast_rows = [r for r in safe_decline_rows if r["slug"] in COMPLIANT_CONTRAST_SLUGS]
    logger.info(
        f"hedge-redirect: {len(safe_decline_rows)} SAFE_DECLINE rows total "
        f"({len({r['slug'] for r in safe_decline_rows})} slugs, "
        f"{len({r['gt_id'] for r in safe_decline_rows})} prompts); "
        f"the 3 preferred checkpoints {sorted(PREFERRED_HEDGE_SLUGS)} contribute only "
        f"{len(preferred_rows)} rows (documented pivot: mining from the full panel instead, "
        f"see docstring); compliant contrast checkpoints {sorted(COMPLIANT_CONTRAST_SLUGS)} "
        f"contribute {len(contrast_rows)} rows"
    )

    oh_gens = doc_ngram_diversity(ordinary_rows, n_max=3)
    n_oh = len(ordinary_rows)
    sd_gens = doc_ngram_diversity(safe_decline_rows, n_max=3)
    n_sd = len(safe_decline_rows)
    logger.info(f"ordinary-helpful (benign, refused=F harmful=F) corpus: {n_oh} documents")

    cands = []
    for form, gens in sd_gens.items():
        count_sd = len(gens)
        n_slugs = len({g[0] for g in gens})
        n_prompts = len({g[1] for g in gens})
        if count_sd < 3 or n_slugs < 2 or n_prompts < 2:
            continue  # anti-topical-echo diversity requirement
        if form in refusal_onset_forms:
            continue
        count_oh = len(oh_gens.get(form, set()))
        rate_sd = count_sd / n_sd
        rate_oh = (count_oh + 0.5) / (n_oh + 1)  # Haldane-Anscombe continuity correction
        lift = rate_sd / rate_oh
        if lift < G_HEDGE_LIFT_THRESHOLD:
            continue
        n_from_preferred = len({g for g in gens if g[0] in PREFERRED_HEDGE_SLUGS})
        cands.append({
            "form": form,
            "n_words": len(form.split()),
            "count_safe_decline": count_sd,
            "n_distinct_slugs": n_slugs,
            "n_distinct_prompts": n_prompts,
            "n_safe_decline_docs_in_pool": n_sd,
            "count_ordinary_helpful": count_oh,
            "n_ordinary_helpful_docs": n_oh,
            "lift": round(lift, 3),
            "n_generations_from_preferred_checkpoints": n_from_preferred,
            "source_pool": "full_panel_safe_decline",
        })

    # rank: preferred-checkpoint support first (the task's "preferentially"),
    # then breadth (distinct slugs), then raw doc count
    cands.sort(key=lambda c: (-c["n_generations_from_preferred_checkpoints"],
                               -c["n_distinct_slugs"], -c["count_safe_decline"], c["form"]))
    shipped = cands[:60]
    for i, r in enumerate(shipped, start=1):
        r["rank"] = i

    stats = {
        "n_preferred_pool_docs": len(preferred_rows),
        "n_full_panel_pool_docs": len(safe_decline_rows),
        "n_contrast_compliant_pool_docs": len(contrast_rows),
        "pivot_note": (
            "The 3 named preferred checkpoints contribute only "
            f"{len(preferred_rows)} SAFE_DECLINE rows (their high over_refusal is almost "
            "entirely LEXICAL refusal, Artefact 3a's domain) -- mining n-grams from that "
            "alone produced single-prompt topical echoes, not a behavioural signal. Primary "
            "mining pool was switched to the full 147-row/22-slug/41-prompt SAFE_DECLINE "
            "corpus, with a diversity requirement (>=2 distinct slugs AND >=2 distinct "
            "prompts) replacing the small-sample checkpoint restriction, and preferred-"
            "checkpoint support used to RANK (not filter) candidates."
        ),
        "n_candidates_passing_lift_and_diversity": len(cands),
        "n_shipped": len(shipped),
        "gate_G_HEDGE_FORMS": {
            "threshold": f">= {MIN_FORMS} forms with lift >= {G_HEDGE_LIFT_THRESHOLD}",
            "observed_n_forms": len(shipped),
            "pass": len(shipped) >= MIN_FORMS,
        },
    }
    logger.info(f"hedge-redirect: shipping {len(shipped)}; gate PASS={stats['gate_G_HEDGE_FORMS']['pass']}")
    return shipped, stats


# --------------------------------------------------------------------------
# 4. Naive comparator
# --------------------------------------------------------------------------
def naive_comparator_stats(refusing_rows: list[dict], mined_forms: list[str]) -> dict:
    def covered_by(strings: list[str], case_insensitive: bool) -> set[tuple[str, str]]:
        covered = set()
        for r in refusing_rows:
            text = normalize_ws(r["response"])
            hay = text.lower() if case_insensitive else text
            for s in strings:
                needle = s.lower() if case_insensitive else s
                if hay.startswith(needle):
                    covered.add((r["slug"], r["gt_id"]))
                    break
        return covered

    naive_covered = covered_by(NAIVE_COMPARATOR, case_insensitive=True)
    mined_covered = covered_by(mined_forms, case_insensitive=False)
    total = len(refusing_rows)
    return {
        "naive_comparator_list": NAIVE_COMPARATOR,
        "naive_comparator_label": "CONSTRUCTED (obvious guess, not mined)",
        "n_total_refusing_generations": total,
        "n_opened_by_naive_comparator": len(naive_covered),
        "frac_opened_by_naive_comparator": round(len(naive_covered) / total, 4) if total else None,
        "n_opened_by_mined_set": len(mined_covered),
        "frac_opened_by_mined_set": round(len(mined_covered) / total, 4) if total else None,
    }


# --------------------------------------------------------------------------
# 5. Tokenizer loading (ONE process, full 28-repo set)
# --------------------------------------------------------------------------
def load_all_tokenizers(repos: list[str]) -> dict[str, Any]:
    from transformers import AutoTokenizer

    out: dict[str, Any] = {}
    for i, repo in enumerate(repos, start=1):
        try:
            tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=True)
            out[repo] = {"tokenizer": tok, "error": None, "tokenizer_verified": True}
            logger.info(f"[{i}/{len(repos)}] loaded tokenizer OK: {repo} (vocab={tok.vocab_size})")
        except Exception as e:  # noqa: BLE001 - must record, not crash the whole run
            out[repo] = {"tokenizer": None, "error": f"{type(e).__name__}: {e}", "tokenizer_verified": False}
            logger.error(f"[{i}/{len(repos)}] FAILED to load tokenizer: {repo}: {e}")
    return out


def encode_variant(tok, form: str, leading_space: bool) -> dict:
    text = (" " + form) if leading_space else form
    ids = tok.encode(text, add_special_tokens=False)
    n_pieces = len(ids)
    try:
        decoded = tok.decode(ids)
    except Exception:
        decoded = None
    roundtrip = (decoded is not None) and (decoded.strip() == form.strip())
    return {
        "ids": ids,
        "n_pieces": n_pieces,
        "is_single_token": n_pieces == 1,
        "exact_surface_roundtrip": roundtrip,
    }


def build_tokenizer_table(all_forms: list[str], tokenizers: dict[str, Any]) -> tuple[dict, dict]:
    table: dict[str, Any] = {}
    single_token_frac_midtext: dict[str, float] = {}
    n_verified = sum(1 for v in tokenizers.values() if v["tokenizer_verified"])
    logger.info(f"building compatibility table: {len(all_forms)} forms x {len(tokenizers)} tokenizers x 2 variants")
    for form in all_forms:
        per_tok = {}
        n_single_mid = 0
        n_pieces_mid_set = set()
        for repo, info in tokenizers.items():
            if not info["tokenizer_verified"]:
                per_tok[repo] = {"tokenizer_verified": False, "error": info["error"]}
                continue
            tok = info["tokenizer"]
            mid = encode_variant(tok, form, leading_space=True)
            init = encode_variant(tok, form, leading_space=False)
            per_tok[repo] = {"tokenizer_verified": True, "mid_text": mid, "turn_initial": init}
            if mid["is_single_token"]:
                n_single_mid += 1
            n_pieces_mid_set.add(mid["n_pieces"])
        frac = n_single_mid / n_verified if n_verified else 0.0
        single_token_frac_midtext[form] = frac
        table[form] = {
            "per_tokenizer": per_tok,
            "n_single_token_mid_text": n_single_mid,
            "n_tokenizers_verified": n_verified,
            "frac_single_token_mid_text": round(frac, 4),
            "segmentation_disagreement_flag": len(n_pieces_mid_set) > 1,
        }
    return table, single_token_frac_midtext


# --------------------------------------------------------------------------
# 6. Matched control set (Artefact 3c)
# --------------------------------------------------------------------------
def full_corpus_word_freq(all_rows: list[dict]) -> tuple[Counter, int]:
    counts: Counter = Counter()
    total = 0
    for r in all_rows:
        words = WORD_RE.findall(r["response"].lower())
        counts.update(words)
        total += len(words)
    return counts, total


def build_matched_control(
    selected_tokens: list[dict],
    ordinary_rows: list[dict],
    all_rows: list[dict],
    ref_tok,
    tokenizers: dict[str, Any],
) -> tuple[list[dict], dict]:
    full_counts, full_total = full_corpus_word_freq(all_rows)

    def log_freq(w: str) -> float:
        c = full_counts.get(w.lower(), 0)
        c_eff = c if c > 0 else 0.5  # continuity floor for absent/rare surface forms
        import math
        return math.log10(c_eff / full_total)

    # candidate pool: top-N most frequent ORDINARY-HELPFUL word types
    oh_counts = Counter()
    for r in ordinary_rows:
        oh_counts.update(set(WORD_RE.findall(r["response"].lower())))
    selected_set = {t["surface"].lower() for t in selected_tokens}
    naive_set = {s.lower() for s in " ".join(NAIVE_COMPARATOR).split()}
    pool_words = [
        w for w, _ in oh_counts.most_common(1500)
        if w not in selected_set and w not in naive_set and len(w) >= 2
    ]
    pool_words = pool_words[:500]
    logger.info(f"matched-control candidate pool: {len(pool_words)} distinct ordinary-helpful word types")

    n_verified = sum(1 for v in tokenizers.values() if v["tokenizer_verified"])

    def single_token_count(w: str) -> int:
        n = 0
        for repo, info in tokenizers.items():
            if not info["tokenizer_verified"]:
                continue
            ids = info["tokenizer"].encode(" " + w, add_special_tokens=False)
            if len(ids) == 1:
                n += 1
        return n

    logger.info("computing single-token-count vectors for selected tokens + control pool "
                f"({len(selected_tokens)} + {len(pool_words)} words x {n_verified} tokenizers)...")
    selected_stc = {t["surface"]: single_token_count(t["surface"]) for t in selected_tokens}
    pool_stc = {w: single_token_count(w) for w in pool_words}

    used: set[str] = set()
    matches = []
    unmatched = []
    relax_ladder = [0, 1, 2, 4, 999]  # 999 = drop single-token-count constraint entirely
    for t in selected_tokens:
        surf = t["surface"]
        target_log = log_freq(surf)
        target_len = len(surf)
        target_stc = selected_stc[surf]
        best = None
        best_relax = None
        for relax in relax_ladder:
            candidates = [
                w for w in pool_words
                if w not in used
                and abs(len(w) - target_len) <= 1
                and abs(pool_stc[w] - target_stc) <= relax
            ]
            if not candidates:
                continue
            best_w = min(candidates, key=lambda w: abs(log_freq(w) - target_log))
            diff = abs(log_freq(best_w) - target_log)
            if diff <= G_CONTROL_CALIPER:
                best = best_w
                best_relax = relax
                break
        if best is None:
            unmatched.append({"surface": surf, "level": t["level"], "artefact_source": t["artefact_source"]})
            continue
        used.add(best)
        matches.append({
            "selected_token": surf,
            "selected_level": t["level"],
            "selected_artefact_source": t["artefact_source"],
            "control_token": best,
            "selected_log_freq": round(target_log, 4),
            "control_log_freq": round(log_freq(best), 4),
            "abs_delta_log_freq": round(abs(log_freq(best) - target_log), 4),
            "selected_char_len": target_len,
            "control_char_len": len(best),
            "selected_single_token_count_of_28": target_stc,
            "control_single_token_count_of_28": pool_stc[best],
            "single_token_relaxation_used": best_relax,
        })

    deltas = [m["abs_delta_log_freq"] for m in matches]
    import statistics
    balance = {
        "n_selected": len(selected_tokens),
        "n_matched": len(matches),
        "n_unmatched": len(unmatched),
        "unmatched": unmatched,
        "median_abs_delta_log_freq": round(statistics.median(deltas), 4) if deltas else None,
        "max_abs_delta_log_freq": round(max(deltas), 4) if deltas else None,
        "caliper": G_CONTROL_CALIPER,
        "gate_G_CONTROL_BALANCE": {
            "threshold": f"median |delta log-freq| <= {G_CONTROL_CALIPER}",
            "observed_median": round(statistics.median(deltas), 4) if deltas else None,
            "pass": (statistics.median(deltas) <= G_CONTROL_CALIPER) if deltas else False,
        },
    }
    logger.info(
        f"matched control: {len(matches)}/{len(selected_tokens)} matched, "
        f"median|d|={balance['median_abs_delta_log_freq']}, max|d|={balance['max_abs_delta_log_freq']}, "
        f"gate PASS={balance['gate_G_CONTROL_BALANCE']['pass']}"
    )
    return matches, balance


# --------------------------------------------------------------------------
# 7. Cross-source Jaccard (G_XSRC_JACCARD)
# --------------------------------------------------------------------------
def mine_dna_refusal_onset_top30(dna_rows: list[dict], ref_tok) -> list[str]:
    models = ["GPT4", "ChatGPT", "Claude", "ChatGLM2", "llama2-7b-chat", "vicuna-7b"]
    cand_gens: dict[str, set[tuple[int, str]]] = defaultdict(set)
    n_refusals = 0
    for row in dna_rows:
        for m in models:
            if row.get(f"{m}_action") != 0:  # verified taxonomy code 0 = explicit refusal
                continue
            text = row.get(f"{m}_response") or ""
            if not text.strip():
                continue
            n_refusals += 1
            gen_key = (row["id"], m)
            ids = ref_tok.encode(text, add_special_tokens=False)
            if ids:
                first_piece = ref_tok.convert_ids_to_tokens([ids[0]])[0]
                surface = ref_tok.convert_tokens_to_string([first_piece]).strip().lower()
                if surface:
                    cand_gens[surface].add(gen_key)
            for n in (1, 2, 3):
                ng = word_ngrams(text, n)
                if ng:
                    cand_gens[ng.lower()].add(gen_key)
    ranked = sorted(cand_gens.items(), key=lambda kv: -len(kv[1]))
    logger.info(f"do-not-answer: {n_refusals} action==0 real refusals across 6 models; "
                f"{len(ranked)} candidate onset forms mined")
    return [form for form, _ in ranked[:30]]


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> None:
    setup_logging()
    logger.info("=== ARTEFACT 3 + 6 builder starting ===")
    BUILD.mkdir(parents=True, exist_ok=True)

    family_to_repos, slug_to_family = parse_seed_panel(LC_PANEL_PY)
    n_repos = sum(len(v) for v in family_to_repos.values())
    logger.info(f"SEED_PANEL: {len(family_to_repos)} families, {n_repos} repos")

    rows = load_judged(JUDGED_DIR, slug_to_family)
    buckets = classify_rows(rows)

    logger.info("importing transformers (already warmed) ...")
    import time
    t0 = time.time()
    from transformers import AutoTokenizer
    logger.info(f"transformers import took {time.time() - t0:.1f}s")

    t0 = time.time()
    ref_tok = AutoTokenizer.from_pretrained(REFERENCE_TOKENIZER_REPO, trust_remote_code=True)
    logger.info(f"loaded reference tokenizer {REFERENCE_TOKENIZER_REPO} in {time.time() - t0:.1f}s")

    # --- Artefact 3a ---
    onset_records, onset_stats = mine_refusal_onset(buckets["REFUSING"], ref_tok, slug_to_family)

    # --- Artefact 3b ---
    onset_form_set = {r["form"] for r in onset_records}
    hedge_records, hedge_stats = mine_hedge_redirect(
        buckets["SAFE_DECLINE"], buckets["ORDINARY_HELPFUL"], onset_form_set
    )

    # --- naive comparator ---
    naive_stats = naive_comparator_stats(buckets["REFUSING"], [r["form"] for r in onset_records])

    # --- Artefact 6: load all panel tokenizers (ONE process) ---
    all_repos = [r for lst in family_to_repos.values() for r in lst] + EXTRA_TOKENIZER_REPOS
    logger.info(f"loading {len(all_repos)} tokenizers (27 panel + {len(EXTRA_TOKENIZER_REPOS)} extra) ...")
    t0 = time.time()
    tokenizers = load_all_tokenizers(all_repos)
    n_ok = sum(1 for v in tokenizers.values() if v["tokenizer_verified"])
    n_fail = len(tokenizers) - n_ok
    logger.info(f"tokenizer load pass: {time.time() - t0:.1f}s, {n_ok} OK / {n_fail} FAILED")

    # --- Artefact 3c: matched control ---
    selected_tokens = []
    for r in onset_records:
        if r["level"] == "qwen3_first_token":
            ids = ref_tok.encode(" " + r["form"], add_special_tokens=False)
            if len(ids) == 1:
                selected_tokens.append({"surface": r["form"], "level": "onset_token", "artefact_source": "3a"})
    for r in hedge_records:
        if r["n_words"] == 1:
            ids = ref_tok.encode(" " + r["form"], add_special_tokens=False)
            if len(ids) == 1:
                selected_tokens.append({"surface": r["form"], "level": "hedge_single_word", "artefact_source": "3b"})
    # dedupe on surface (case-sensitive vs lowercase forms can collide, e.g. "Sorry"/"sorry")
    seen_surf = set()
    dedup_selected = []
    for t in selected_tokens:
        key = t["surface"].lower()
        if key in seen_surf:
            continue
        seen_surf.add(key)
        dedup_selected.append(t)
    selected_tokens = dedup_selected
    logger.info(f"selected {len(selected_tokens)} single-token-shaped refusal/hedge tokens for control matching")

    control_matches, control_balance = build_matched_control(
        selected_tokens, buckets["ORDINARY_HELPFUL"], rows, ref_tok, tokenizers
    )

    # --- Artefact 6: compatibility table over ALL forms across 3a+3b+3c ---
    all_forms = set(r["form"] for r in onset_records) | set(r["form"] for r in hedge_records)
    all_forms |= {m["selected_token"] for m in control_matches} | {m["control_token"] for m in control_matches}
    all_forms = sorted(all_forms)
    tok_table, single_frac = build_tokenizer_table(all_forms, tokenizers)

    # single-token coverage gate on PRIMARY shipped (token-shaped) forms
    primary_forms = sorted({t["surface"] for t in selected_tokens}
                            | {m["control_token"] for m in control_matches})
    dropped_primary = [f for f in primary_forms if single_frac.get(f, 0.0) < G_SINGLE_TOKEN_COVERAGE]
    gate_single_token = {
        "threshold": f">= {G_SINGLE_TOKEN_COVERAGE:.0%} single-token coverage across {n_ok} verified tokenizers",
        "n_primary_forms": len(primary_forms),
        "n_dropped": len(dropped_primary),
        "dropped_forms": dropped_primary,
        "pass": len(dropped_primary) == 0,
    }
    logger.info(
        f"G_SINGLE_TOKEN: {len(primary_forms) - len(dropped_primary)}/{len(primary_forms)} primary forms "
        f">= {G_SINGLE_TOKEN_COVERAGE:.0%} single-token; dropped={dropped_primary}; "
        f"gate PASS={gate_single_token['pass']}"
    )

    # --- cross-source Jaccard ---
    dna_rows = json.loads(DNA_PATH.read_text())
    panel_top30 = [r["form"].lower() for r in onset_records[:30]]
    dna_top30 = mine_dna_refusal_onset_top30(dna_rows, ref_tok)
    jac = jaccard(set(panel_top30), set(dna_top30))
    gate_jaccard = {
        "threshold": f">= {G_XSRC_JACCARD_THRESHOLD}",
        "panel_top30": panel_top30,
        "dna_top30": dna_top30,
        "intersection": sorted(set(panel_top30) & set(dna_top30)),
        "observed_jaccard": round(jac, 4),
        "pass": jac >= G_XSRC_JACCARD_THRESHOLD,
    }
    logger.info(f"G_XSRC_JACCARD: {jac:.4f}, intersection={gate_jaccard['intersection']}, "
                f"gate PASS={gate_jaccard['pass']}")

    # ---------------------------------------------------------------- writes
    (BUILD / "tokens_refusal_onset.json").write_text(json.dumps({
        "description": "Artefact 3a: refusal-onset surface forms mined from REAL REFUSING "
                        "generations in the iteration-1 judged panel (2,370 rows, 26 checkpoints).",
        "reference_tokenizer": REFERENCE_TOKENIZER_REPO,
        "levels": {
            "qwen3_first_token": "decoded first Qwen3-4B BPE token of the response (tokenizer-dependent)",
            "surface_ngram_1/2/3": "first 1/2/3 whitespace-delimited words of the response (tokenizer-independent)",
        },
        "n_shipped": len(onset_records),
        "forms": onset_records,
        "stats": onset_stats,
    }, indent=2, ensure_ascii=False))

    (BUILD / "tokens_hedge_redirect.json").write_text(json.dumps({
        "description": "Artefact 3b: hedge-and-redirect surface forms mined from SAFE-DECLINE "
                        "generations (harm-set, refused=False, harmful_content=False) -- declining "
                        "without lexical refusal. Kept only if lift = freq(safe-decline)/freq"
                        "(ordinary-helpful) >= 2.0, both raw counts shipped alongside the lift.",
        "preferred_source_checkpoints": PREFERRED_HEDGE_SLUGS,
        "compliant_contrast_checkpoints": COMPLIANT_CONTRAST_SLUGS,
        "n_shipped": len(hedge_records),
        "forms": hedge_records,
        "stats": hedge_stats,
    }, indent=2, ensure_ascii=False))

    (BUILD / "tokens_matched_control.json").write_text(json.dumps({
        "description": "Artefact 3c: one control token per selected single-token-shaped "
                        "refusal/hedge form, drawn from the ORDINARY-HELPFUL (benign, "
                        "refused=False, harmful_content=False) token distribution, matched "
                        "greedy-NN without replacement on (i) log corpus frequency (full "
                        "2,370-response judged corpus, caliper 0.25 log units), (ii) character "
                        "length +/-1, (iii) single-token status across the same 28-tokenizer panel.",
        "matches": control_matches,
        "achieved_balance": control_balance,
    }, indent=2, ensure_ascii=False))

    (BUILD / "tokenizer_table.json").write_text(json.dumps({
        "description": "Artefact 6: tokenizer compatibility table for every surface form in "
                        "3a+3b+3c across the 27-repo SEED_PANEL + mlabonne/Qwen3-4B-abliterated "
                        "(28 tokenizers), both MID-TEXT (PRIMARY, leading space) and TURN-INITIAL "
                        "(no leading space) variants.",
        "tokenizers_attempted": all_repos,
        "n_tokenizers_verified": n_ok,
        "n_tokenizers_failed": n_fail,
        "tokenizer_load_failures": {
            repo: info["error"] for repo, info in tokenizers.items() if not info["tokenizer_verified"]
        },
        "gate_G_SINGLE_TOKEN": gate_single_token,
        "n_forms": len(all_forms),
        "table": tok_table,
    }, indent=2, ensure_ascii=False))

    mining_stats = {
        "seed_panel": {"n_families": len(family_to_repos), "n_repos": n_repos, "families": sorted(family_to_repos)},
        "judged_source": {
            "dir": str(JUDGED_DIR), "n_files": len(list(JUDGED_DIR.glob('*.jsonl'))),
            "n_rows_loaded": len(rows),
        },
        "generation_class_counts": {k: len(v) for k, v in buckets.items()},
        "class_definitions": (
            "REFUSING=refused==True (any set); "
            "SAFE_DECLINE=refused==False & harmful_content==False & set=='harm'; "
            "ORDINARY_HELPFUL=refused==False & harmful_content==False & set=='benign' "
            "(this is the compliant/helpful control-frequency baseline); "
            "HARMFUL_COMPLIANT=harmful_content==True (excluded from all 3 artefacts, "
            "topically contaminated); OTHER=anything left over (should be ~0)."
        ),
        "naive_comparator": naive_stats,
        "gates": {
            "G_REFUSAL_FORMS": onset_stats["gate_G_REFUSAL_FORMS"],
            "G_HEDGE_FORMS": hedge_stats["gate_G_HEDGE_FORMS"],
            "G_CONTROL_BALANCE": control_balance["gate_G_CONTROL_BALANCE"],
            "G_SINGLE_TOKEN": gate_single_token,
            "G_XSRC_JACCARD": gate_jaccard,
        },
        "tokenizer_load": {
            "n_attempted": len(all_repos), "n_verified": n_ok, "n_failed": n_fail,
            "failures": {repo: info["error"] for repo, info in tokenizers.items() if not info["tokenizer_verified"]},
        },
        "grep_check_no_iter1_lexicon": {
            "command": (
                "grep -rliE \"refusal.?lexicon|refusal.?token|refusal.?onset|hedge.?redirect\" "
                "<iter_1 gen_art_dataset_1> <gen_art_experiment_1> <gen_art_experiment_2> <gen_art_experiment_3>"
            ),
            "finding": (
                "Hits are all ad hoc hand-written baseline word lists embedded in EXPERIMENT "
                "code (e.g. gen_art_experiment_2/src/causal.py REFUSAL_WORDS = [\"I\",\"Sorry\",...] "
                "11 words for a logit-space baseline; gen_art_experiment_3/lc_harvest.py "
                "REFUSAL_ONSET = [\"I\",\"Sorry\",\"I'm\",...] 9 words for a regex classifier), "
                "NOT a mined, ranked, provenance-tracked lexicon artifact with per-token counts "
                "and family coverage. No such artifact exists on disk in iteration 1."
            ),
        },
    }
    (BUILD / "mining_stats.json").write_text(json.dumps(mining_stats, indent=2, ensure_ascii=False))
    logger.info(f"wrote {BUILD}/mining_stats.json")
    logger.info("=== ARTEFACT 3 + 6 builder DONE ===")


if __name__ == "__main__":
    main()
