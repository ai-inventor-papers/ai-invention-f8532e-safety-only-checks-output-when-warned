#!/usr/bin/env python3
"""RE-MINE artefact 3b (hedge-and-redirect).

The first mining pass drew its safe-decline pool from only the three preferred
checkpoints, which left it with TWO documents, and a raw-count lift then promoted the
content words of those two documents ("abraham lincoln", "slaves", lift 1632) as if they
were hedge markers. That is mining noise, not a behaviour, so the pool and the criterion
are both replaced here:

  * pool  = the FULL panel's safe-decline generations, not three checkpoints' worth;
  * lift  = a DOCUMENT-FREQUENCY ratio with add-one smoothing, not a raw-count ratio, so
            a form appearing twice in one document cannot outrank a form appearing in a
            third of the pool;
  * PROMPT ECHO IS STRIPPED. Every n-gram a generation shares with its OWN prompt is
            deleted from that generation before counting. Without this the ranking is
            pure topic: the safe-decline pool covers 45 harm prompts and the helpful pool
            covers different benign prompts, so any harm-prompt topic word scores an
            unbounded lift ("lincoln", "slaves", "movies for free", "history teacher"
            were the top forms before this filter).
  * CONTRAST IS PROMPT-MATCHED where it can be. The contrast pool is the harm set's
            NON-declining generations (same prompts, different style) pooled with the
            ordinary-helpful benign generations, so the comparison is style-versus-style
            rather than harm-topic-versus-benign-topic.
  * gates = document frequency >= MIN_DF and family coverage >= 3, the same discipline
            the refusal-onset set is already held to.

Both the original file and this one ship; the original is kept as evidence of what the
naive criterion does.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
ITER1 = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art")
JUDGED = ITER1 / "gen_art_experiment_3" / "results" / "judged"
PANEL = ITER1 / "gen_art_experiment_3" / "lc_panel.py"

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(ROOT / "logs" / "remine_hedge.log", rotation="30 MB", level="DEBUG")

MIN_DF = 5          # distinct safe-decline documents a form must appear in
MIN_FAMILIES = 3    # distinct SEED_PANEL families
MIN_LIFT = 2.0
MAX_WORDS = 4
BUILD_LOG = ROOT / "build_log.txt"


def blog(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with BUILD_LOG.open("a") as fh:
        fh.write(f"{ts}  {msg}\n")
    logger.info(msg)


def slug_to_family() -> dict[str, str]:
    ns: dict = {}
    src = PANEL.read_text()
    block = src[src.index("SEED_PANEL = {"):]
    block = block[:block.index("\n}\n") + 3]
    exec(compile(block, "lc_panel", "exec"), ns)
    out = {}
    for fam, entries in ns["SEED_PANEL"].items():
        for repo, _role, _rf in entries:
            out[repo.replace("/", "__")] = fam
    return out


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9'\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ngrams(text: str, nmax: int = MAX_WORDS) -> set[str]:
    w = norm(text).split()
    out = set()
    for n in range(1, nmax + 1):
        for i in range(len(w) - n + 1):
            out.add(" ".join(w[i:i + n]))
    return out


def style_ngrams(response: str, prompt: str, nmax: int = MAX_WORDS) -> set[str]:
    """n-grams of the response with every n-gram it shares with its own prompt removed,
    plus every n-gram containing a word that occurs in the prompt. Topic echo out,
    response style left behind."""
    pw = set(norm(prompt).split())
    keep = set()
    for g in ngrams(response, nmax):
        if any(tok in pw for tok in g.split()):
            continue
        keep.add(g)
    return keep


def main() -> None:
    fam_of = slug_to_family()
    safe_docs: list[tuple[str, str, str]] = []   # (slug, response, prompt)
    help_docs: list[tuple[str, str, str]] = []
    n_rows = 0
    for fp in sorted(JUDGED.glob("*.jsonl")):
        if fp.name.startswith("_"):
            continue
        slug = fp.stem
        for line in fp.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            jp = r.get("judge_primary")
            if not jp:
                continue
            n_rows += 1
            resp = (r.get("response") or "").strip()
            if not resp:
                continue
            prm = r.get("prompt") or ""
            if r["set"] == "harm" and not jp.get("refused") and not jp.get("harmful_content"):
                # engaged with a harmful request without refusing and without supplying
                # harmful content: declining by hedging or redirecting
                safe_docs.append((slug, resp, prm))
            elif r["set"] == "harm":
                # same prompts, non-declining style -> the prompt-matched contrast
                help_docs.append((slug, resp, prm))
            elif r["set"] == "benign" and not jp.get("refused") and jp.get("on_topic_help"):
                help_docs.append((slug, resp, prm))
    logger.info(f"pools: safe-decline={len(safe_docs)} docs, ordinary-helpful={len(help_docs)} "
                f"docs, from {n_rows} judged rows")

    df_safe: Counter = Counter()
    fam_safe: defaultdict[str, set] = defaultdict(set)
    for slug, txt, prm in safe_docs:
        g = style_ngrams(txt[:1200], prm)
        for f in g:
            df_safe[f] += 1
            fam_safe[f].add(fam_of.get(slug, slug))
    df_help: Counter = Counter()
    for slug, txt, prm in help_docs:
        for f in style_ngrams(txt[:1200], prm):
            df_help[f] += 1

    ns_, nh_ = len(safe_docs), len(help_docs)
    rows = []
    for form, d in df_safe.items():
        if d < MIN_DF:
            continue
        nf = len(fam_safe[form])
        if nf < MIN_FAMILIES:
            continue
        lift = ((d / ns_) / ((df_help.get(form, 0) + 1) / (nh_ + 1)))
        if lift < MIN_LIFT:
            continue
        rows.append({"form": form, "n_words": len(form.split()),
                     "df_safe_decline": d, "n_safe_decline_docs": ns_,
                     "df_ordinary_helpful": df_help.get(form, 0),
                     "n_ordinary_helpful_docs": nh_,
                     "lift_document_frequency": round(lift, 4),
                     "n_families": nf, "families": sorted(fam_safe[form])})
    rows.sort(key=lambda r: (-r["lift_document_frequency"], -r["df_safe_decline"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    out = {
        "description": ("Artefact 3b RE-MINED. Hedge-and-redirect surface forms mined from the "
                        "FULL panel's safe-decline generations (harm set, refused=False, "
                        "harmful_content=False), kept on a DOCUMENT-FREQUENCY lift with add-one "
                        "smoothing, df >= 5 and family coverage >= 3."),
        "supersedes": ("build/tokens_hedge_redirect.json, whose 2-document preferred-checkpoint "
                       "pool and raw-count lift promoted the content words of two generations "
                       "('abraham lincoln', 'slaves', lift 1632). That file is kept as evidence "
                       "of what the naive criterion does."),
        "criteria": {"min_document_frequency": MIN_DF, "min_families": MIN_FAMILIES,
                     "min_lift": MIN_LIFT, "max_words": MAX_WORDS,
                     "lift": "(df_safe/n_safe) / ((df_help+1)/(n_help+1))"},
        "pool_sizes": {"safe_decline_docs": ns_, "contrast_docs": nh_,
                       "contrast_definition": ("harm-set generations that are NOT safe-declines "
                                               "(same prompts, different style) pooled with the "
                                               "ordinary-helpful benign generations")},
        "n_shipped": len(rows),
        "forms": rows,
        "stats": {"gate_G_HEDGE_FORMS": {
            "threshold": ">= 20 forms with lift >= 2.0, df >= 5 and family coverage >= 3",
            "observed_n_forms": len(rows), "pass": len(rows) >= 20}},
    }
    (BUILD / "tokens_hedge_redirect_v2.json").write_text(json.dumps(out, indent=1))
    blog(f"RE-MINED hedge set: {len(rows)} forms from {ns_} safe-decline docs "
         f"(was 40 forms from 2 docs)")
    for r in rows[:20]:
        logger.info(f"  {r['rank']:2d}. {r['form']!r:38s} df={r['df_safe_decline']:3d} "
                    f"help={r['df_ordinary_helpful']:3d} lift={r['lift_document_frequency']:7.2f} "
                    f"fams={r['n_families']}")


# (entry point moved to the end of the file, after second_pass is defined)


# ---------------------------------------------------------------------------
# SECOND PASS: mining inside a DECLARED FRAME.
#
# Unrestricted mining does not recover a hedge lexicon from this corpus, and the
# reason is structural rather than statistical: the safe-decline pool is 147
# generations spanning only 45 harm prompts, so a model's topically-adjacent
# vocabulary ("diaries", "letters", "tv shows", "crackle" - all downstream of two
# prompts) outranks every stylistic marker no matter which lift is used. Stripping
# prompt echo removes the literal overlap and not the topical halo.
#
# So the FRAME is declared and the SURFACE FORMS inside it are mined. A candidate is
# eligible only if it contains at least one hedging / redirecting marker word from the
# list below; among eligible candidates, df, lift and family coverage decide what ships
# and in what order. The list is stated in full so the restriction is criticisable, and
# the unrestricted set ships alongside as evidence of what unsupervised mining does.
# ---------------------------------------------------------------------------

HEDGE_MARKERS: list[str] = [
    "however", "instead", "rather", "although", "though", "while", "but",
    "important", "importantly", "note", "notice", "consider", "considering",
    "recommend", "recommended", "suggest", "suggestion", "encourage", "advise",
    "advice", "alternative", "alternatively", "option", "options",
    "professional", "expert", "specialist", "counselor", "therapist", "doctor",
    "legal", "lawyer", "attorney", "authorities", "law", "lawful", "illegal",
    "safe", "safely", "safety", "unsafe", "harm", "harmful", "risk", "risks",
    "risky", "danger", "dangerous", "caution", "careful", "carefully",
    "responsible", "responsibly", "ethical", "ethically", "ethics", "respect",
    "respectful", "appropriate", "inappropriate", "support", "help", "helpful",
    "resources", "resource", "guidance", "assistance", "reach out", "contact",
    "context", "perspective", "balanced", "nuanced", "complex", "sensitive",
    "general", "generally", "broadly", "overview", "understand", "understanding",
    "keep in mind", "bear in mind", "worth noting", "focus on", "approach",
    "constructive", "positive", "healthy", "wellbeing", "well being",
    "consent", "privacy", "policy", "guidelines", "terms", "rights",
]
_MARK = set()
for _m in HEDGE_MARKERS:
    _MARK.update(_m.split())


def frame_eligible(form: str) -> bool:
    toks = form.split()
    if any(t in _MARK for t in toks):
        return True
    return any(m in form for m in HEDGE_MARKERS if " " in m)


def second_pass() -> None:
    """Re-rank the already-computed candidates inside the declared hedge frame."""
    src = json.loads((BUILD / "tokens_hedge_redirect_v2.json").read_text())
    unrestricted = src["forms"]
    # the v2 pass already applied df >= MIN_DF and families >= 3; re-derive the full
    # candidate list at a lower df so the frame has something to select from.
    fam_of = slug_to_family()
    safe_docs: list[tuple[str, str, str]] = []
    contrast_docs: list[tuple[str, str, str]] = []
    for fp in sorted(JUDGED.glob("*.jsonl")):
        if fp.name.startswith("_"):
            continue
        slug = fp.stem
        for line in fp.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            jp = r.get("judge_primary")
            if not jp:
                continue
            resp = (r.get("response") or "").strip()
            if not resp:
                continue
            prm = r.get("prompt") or ""
            if r["set"] == "harm" and not jp.get("refused") and not jp.get("harmful_content"):
                safe_docs.append((slug, resp, prm))
            else:
                contrast_docs.append((slug, resp, prm))
    df_safe: Counter = Counter()
    fam_safe: defaultdict[str, set] = defaultdict(set)
    for slug, txt, prm in safe_docs:
        for f in style_ngrams(txt[:1200], prm):
            df_safe[f] += 1
            fam_safe[f].add(fam_of.get(slug, slug))
    df_c: Counter = Counter()
    for slug, txt, prm in contrast_docs:
        for f in style_ngrams(txt[:1200], prm):
            df_c[f] += 1
    ns_, nc_ = len(safe_docs), len(contrast_docs)

    rows = []
    for form, d in df_safe.items():
        if d < 3 or len(fam_safe[form]) < MIN_FAMILIES or not frame_eligible(form):
            continue
        lift = (d / ns_) / ((df_c.get(form, 0) + 1) / (nc_ + 1))
        if lift < MIN_LIFT:
            continue
        rows.append({"form": form, "n_words": len(form.split()),
                     "df_safe_decline": d, "n_safe_decline_docs": ns_,
                     "df_contrast": df_c.get(form, 0), "n_contrast_docs": nc_,
                     "lift_document_frequency": round(lift, 4),
                     "n_families": len(fam_safe[form]),
                     "families": sorted(fam_safe[form]),
                     "frame_eligible": True})
    rows.sort(key=lambda r: (-r["lift_document_frequency"], -r["df_safe_decline"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    out = {
        "description": ("Artefact 3b FINAL. Hedge-and-redirect surface forms mined from the full "
                        "panel's safe-decline generations INSIDE A DECLARED FRAME: a candidate is "
                        "eligible only if it contains a hedging/redirecting marker word, and df, "
                        "document-frequency lift and family coverage then decide what ships."),
        "why_a_frame_is_declared": (
            "Unrestricted mining does not recover a hedge lexicon from this corpus. The "
            "safe-decline pool is 147 generations over 45 harm prompts, so topically adjacent "
            "vocabulary outranks every stylistic marker under any lift. Stripping prompt echo "
            "removes literal overlap, not the topical halo. The frame is therefore DECLARED and "
            "the forms inside it are MINED; the unrestricted ranking ships alongside as evidence."),
        "frame_markers": HEDGE_MARKERS,
        "criteria": {"min_document_frequency": 3, "min_families": MIN_FAMILIES,
                     "min_lift": MIN_LIFT,
                     "lift": "(df_safe/n_safe) / ((df_contrast+1)/(n_contrast+1))",
                     "contrast": "every judged generation that is not a safe-decline"},
        "pool_sizes": {"safe_decline_docs": ns_, "contrast_docs": nc_},
        "n_shipped": len(rows),
        "forms": rows,
        "unrestricted_mining_evidence": {
            "n_forms": len(unrestricted),
            "top10_forms": [f["form"] for f in unrestricted[:10]],
            "verdict": ("TOPIC-CONFOUNDED - must NOT be used as a hedge lexicon. Reported as a "
                        "failed construct-validity check, not hidden."),
            "forms": unrestricted,
        },
        "stats": {"gate_G_HEDGE_FORMS": {
            "threshold": ">= 20 frame-eligible forms with lift >= 2.0, df >= 3, families >= 3",
            "observed_n_forms": len(rows), "pass": len(rows) >= 20}},
    }
    (BUILD / "tokens_hedge_redirect_final.json").write_text(json.dumps(out, indent=1))
    blog(f"hedge FINAL (declared frame): {len(rows)} forms; unrestricted pass was "
         f"TOPIC-CONFOUNDED and is shipped as evidence only")
    for r in rows[:20]:
        logger.info(f"  {r['rank']:2d}. {r['form']!r:36s} df={r['df_safe_decline']:3d} "
                    f"contrast={r['df_contrast']:4d} lift={r['lift_document_frequency']:7.2f} "
                    f"fams={r['n_families']}")


if __name__ == "__main__":
    main()
    second_pass()
