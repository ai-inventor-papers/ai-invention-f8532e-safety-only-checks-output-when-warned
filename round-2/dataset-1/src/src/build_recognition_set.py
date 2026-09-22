#!/usr/bin/env python3
"""Build ARTEFACT 2: the HARD RECOGNITION SET for the Qwen3 safety run.

Assembles ~1300-1600 rows across five difficulty/harm strata from the
already-downloaded source datasets under WS/temp/datasets, deduplicates them,
checks disjointness against iteration-1 judged material and the iteration-1
XSTest 96/54 scenario split, assigns the frozen fit/screen/sealed_holdout
split, and runs the two-sided TF-IDF proxy AUROC gate. All source-agnostic
mechanics (normalisation, dedup, split, proxy) come from lib_recog.py; the
stratum vocabulary and keyword/category machinery comes from lib_strata.py.
Nothing here reimplements either library.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lib_recog import assign_split, dedup, phash, proxy_auroc, sizing_statement  # noqa: E402
from lib_strata import (  # noqa: E402
    CONSTRUCTED_WRAPPERS,
    is_lexically_innocuous,
    map_category,
    surface_keywords_hit,
)

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
logger.add(LOG_DIR / "build_recognition_set.log", rotation="30 MB", level="DEBUG")

DATASETS_DIR = ROOT / "temp" / "datasets"
BUILD_DIR = ROOT / "build"
OUT_PATH = BUILD_DIR / "recognition_set.json"

NON_BASE_STYLES = [
    "ascii", "atbash", "authority_endorsement", "caesar", "evidence-based_persuasion",
    "expert_endorsement", "logical_appeal", "misrepresentation", "misspellings", "morse",
    "question", "role_play", "slang", "technical_terms", "translate-fr", "translate-ml",
    "translate-mr", "translate-ta", "translate-zh-cn", "uncommon_dialects",
]

# ---- source licences, resolved from build/repo_meta/*.json (HF card API "license"
# field) and download-lane notes; see the sources_used block in the shipped JSON for
# the exact provenance of each string. -----------------------------------------------
SOURCE_LICENSES: dict[str, str] = {
    "or_bench_hard_1k": "cc-by-4.0",
    "or_bench_toxic": "cc-by-4.0",
    "or_bench_80k_sample": "cc-by-4.0",
    "xstest_github": "cc-by-4.0",
    "phtest": "mit",
    "falsereject_test": "cc-by-nc-4.0",
    "falsereject_train": "cc-by-nc-4.0",
    "sorrybench_sillytilly": "other",
    "jbb_behaviors_harmful": "mit",
    "jbb_behaviors_benign": "mit",
    "advbench_github": "mit",
    "beavertails_30k_test": "cc-by-nc-4.0",
    "pku_saferlhf_test": "cc-by-nc-4.0",
}
LICENSE_NOTES: dict[str, str] = {
    "or_bench_hard_1k": "HF card API license for bench-llm/or-bench (build/repo_meta/bench-llm__or-bench.json).",
    "or_bench_toxic": "same repo as or_bench_hard_1k.",
    "or_bench_80k_sample": "same repo as or_bench_hard_1k.",
    "xstest_github": "GitHub CSV (paul-rottger/exaggerated-safety) has no separate LICENSE probe on disk; "
                     "cross-checked against byte-identical HF mirrors Paul/XSTest and natolambert/xstest-v2-copy, "
                     "both cc-by-4.0 (build/repo_meta/Paul__XSTest.json, natolambert__xstest-v2-copy.json).",
    "phtest": "HF card API license for furonghuang-lab/PHTest.",
    "falsereject_test": "HF card API license for AmazonScience/FalseReject.",
    "falsereject_train": "same repo as falsereject_test.",
    "sorrybench_sillytilly": "UNVERIFIED_MIRROR_LICENSE: the ungated mirror SillyTilly/SorryBench does not "
                              "redeclare a license on its HF card (build/repo_meta/SillyTilly__SorryBench.json "
                              "license=null). Inherited from the original gated repos sorry-bench/sorry-bench-202406 "
                              "and -202503, both license='other' (gated='auto'). Shipped as 'other' to flag that it "
                              "is not a standard open licence.",
    "jbb_behaviors_harmful": "HF card API license for JailbreakBench/JBB-Behaviors.",
    "jbb_behaviors_benign": "same repo as jbb_behaviors_harmful.",
    "advbench_github": "GitHub CSV (llm-attacks/llm-attacks) has no separate LICENSE probe on disk (walledai/AdvBench "
                        "is now gated='auto' per a live re-check by the sourcing lane and is NOT the source used). "
                        "Cross-checked via row-count-identical community HF mirror carl213/advbench, license=mit "
                        "(build/repo_meta/carl213__advbench.json).",
    "beavertails_30k_test": "HF card API license for PKU-Alignment/BeaverTails (build/hf_candidates.json candidate 17).",
    "pku_saferlhf_test": "HF card API license for PKU-Alignment/PKU-SafeRLHF (build/repo_meta/PKU-Alignment__PKU-SafeRLHF.json).",
}

SOURCE_PRIORITY = [
    "xstest_github",
    "sorrybench_sillytilly",
    "or_bench_hard_1k",
    "or_bench_toxic",
    "falsereject_test",
    "phtest",
    "jbb_behaviors_harmful",
    "jbb_behaviors_benign",
    "advbench_github",
    "beavertails_30k_test",
    "pku_saferlhf_test",
    "or_bench_80k_sample",
    "falsereject_train",
]


def load_rows(source_id: str) -> list[dict]:
    path = DATASETS_DIR / source_id / "data.json"
    data = json.loads(path.read_text())
    rows = data["rows"] if isinstance(data, dict) and "rows" in data else data
    if not isinstance(rows, list):
        raise ValueError(f"{source_id}: unexpected data.json shape {type(data)}")
    logger.info(f"loaded {source_id}: n={len(rows)}")
    return rows


def build_sorrybench_category_taxonomy(fr_test: list[dict], fr_train: list[dict]) -> dict[str, str]:
    """FalseReject ships (category:int, category_text:str) pairs for the SAME 1-46
    SORRY-Bench-style taxonomy that sorrybench_sillytilly's numeric `category` field
    uses (verified: both range 1-45/46, and FalseReject's own sample_rows in
    build/hf_candidates.json show category=1 -> 'Personal Insulting Words', which is
    exactly SORRY-Bench category 1). Built from data already on disk, no network.
    """
    tax: dict[str, str] = {}
    for r in fr_test + fr_train:
        tax[str(r["category"])] = r["category_text"]
    logger.info(f"sorrybench/falsereject numeric->text taxonomy: {len(tax)} categories")
    return tax


def make_row(
    *,
    text: str,
    harm_label: str,
    difficulty: str,
    stratum: str,
    source_dataset: str,
    source_row_id: str,
    raw_category: str | None,
    graded_harm: int | None = None,
    graded_harm_source: str | None = None,
    twin_id: str | None = None,
    wrapped_style: str | None = None,
    wrapped_source: str | None = None,
) -> dict[str, Any]:
    category, mapped = map_category(raw_category)
    row: dict[str, Any] = {
        "input": text,
        "output": harm_label,
        "metadata_row_id": f"{source_dataset}__{source_row_id}",
        "metadata_harm_label": harm_label,
        "metadata_graded_harm": graded_harm,
        "metadata_graded_harm_source": graded_harm_source,
        "metadata_difficulty": difficulty,
        "metadata_stratum": stratum,
        "metadata_source_dataset": source_dataset,
        "metadata_source_row_id": source_row_id,
        "metadata_harm_category": category,
        "metadata_harm_category_raw": raw_category,
        "metadata_harm_category_mapped": mapped,
        "metadata_twin_id": twin_id,
        "metadata_split": None,   # filled after dedup
        "metadata_fold": None,    # filled after dedup, same value as split
        "metadata_license": SOURCE_LICENSES[source_dataset],
        "metadata_used_in_iter1_judged": False,  # filled after dedup
        "metadata_prompt_hash": phash(text),
        "metadata_readout_class": "text",
        "metadata_surface_keywords_hit": surface_keywords_hit(text),
    }
    if wrapped_style is not None:
        row["metadata_wrapped_style"] = wrapped_style
    if wrapped_source is not None:
        row["metadata_wrapped_source"] = wrapped_source
    return row


@logger.catch(reraise=True)
def main() -> None:
    prereg_sha256 = (ROOT / "prereg.sha256").read_text().split()[0]
    logger.info(f"prereg_sha256={prereg_sha256}")

    behavioural = json.loads((BUILD_DIR / "behavioural.json").read_text())
    judged_prompt_index: dict[str, dict] = behavioural["judged_prompt_index"]
    iter1_hashes = set(behavioural["iter1_prompt_hashes"]["data_out"]) | set(
        behavioural["iter1_prompt_hashes"]["heldout_cells"]
    )
    logger.info(
        f"judged_prompt_index: {len(judged_prompt_index)} phashes; "
        f"iter1 96/54 xstest split: {len(iter1_hashes)} phashes"
    )

    probe_pools_path = BUILD_DIR / "probe_pools.json"
    probe_hashes: set[str] = set()
    if probe_pools_path.exists():
        probe_pools = json.loads(probe_pools_path.read_text())

        def _collect(o: Any) -> None:
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("prompt_hash", "metadata_prompt_hash") and isinstance(v, str):
                        probe_hashes.add(v)
                    else:
                        _collect(v)
            elif isinstance(o, list):
                for v in o:
                    _collect(v)

        _collect(probe_pools)
        logger.info(f"probe_pools.json FOUND: collected {len(probe_hashes)} phashes to exclude")
    else:
        logger.info("probe_pools.json ABSENT (expected if the parallel step hasn't written it yet) - skipping")

    # ---- load every source ---------------------------------------------------------
    xstest = load_rows("xstest_github")
    sorrybench = load_rows("sorrybench_sillytilly")
    or_hard = load_rows("or_bench_hard_1k")
    or_toxic = load_rows("or_bench_toxic")
    fr_test = load_rows("falsereject_test")
    fr_train = load_rows("falsereject_train")
    phtest = load_rows("phtest")
    jbb_harm = load_rows("jbb_behaviors_harmful")
    jbb_benign = load_rows("jbb_behaviors_benign")
    advbench = load_rows("advbench_github")
    beavertails = load_rows("beavertails_30k_test")
    pku = load_rows("pku_saferlhf_test")
    or_80k = load_rows("or_bench_80k_sample")

    sb_taxonomy = build_sorrybench_category_taxonomy(fr_test, fr_train)

    def sb_category(cat_id: str) -> str | None:
        return sb_taxonomy.get(str(cat_id))

    used: set[tuple[str, str]] = set()  # (source_dataset, source_row_id) already claimed by a stratum
    n_skipped_iter1_split = 0
    n_skipped_probe_pool = 0

    def claim(source_dataset: str, source_row_id: str, text: str) -> bool:
        """Claim a candidate row iff it hasn't been claimed yet AND it does not fall in
        the iteration-1 96/54 scenario split or any probe pool. Checking contamination
        HERE (before a row is even built) means per-source quota caps are spent only on
        rows that will actually survive, instead of being wasted on doomed candidates.
        """
        nonlocal n_skipped_iter1_split, n_skipped_probe_pool
        key = (source_dataset, str(source_row_id))
        if key in used:
            return False
        h = phash(text)
        if h in iter1_hashes:
            n_skipped_iter1_split += 1
            return False
        if h in probe_hashes:
            n_skipped_probe_pool += 1
            return False
        used.add(key)
        return True

    rows_by_stratum: dict[str, list[dict]] = {
        "hard_benign": [], "harmful_lexically_innocuous": [], "borderline_dual_use": [],
        "wrapped": [], "easy_anchors": [],
    }

    # =========================================================================
    # (a) hard_benign  ~400  difficulty=hard, harm_label=benign
    # =========================================================================
    # -- xstest safe rows: ALL 250, and build the position-based twin index while
    #    we're here (see the "twins" section below for the join rule derivation).
    xstest_sorted = sorted(xstest, key=lambda r: int(r["id"]))
    n_chunks = len(xstest_sorted) // 25
    chunks = [xstest_sorted[i * 25:(i + 1) * 25] for i in range(n_chunks)]
    XSTEST_TYPE_TO_RAW = {
        "homonyms": "homonyms", "contrast_homonyms": "contrast homonyms",
        "figurative_language": "figurative language",
        "contrast_figurative_language": "contrast figurative language",
        "safe_targets": "safe targets", "contrast_safe_targets": "contrast safe targets",
        "safe_contexts": "safe contexts", "contrast_safe_contexts": "contrast safe contexts",
        "definitions": "definitions", "contrast_definitions": "contrast definitions",
        "nons_group_real_discr": "nonsense discr, real group",
        "real_group_nons_discr": "real discr, nonsense group",
        "contrast_discr": "contrast real discr, nonsense group",
        "historical_events": "historical events",
        "contrast_historical_events": "contrast historical events",
        "privacy_public": "privacy (public)", "privacy_fictional": "privacy (fictional)",
        "contrast_privacy": "contrast privacy (public)",
    }
    twin_pairs: list[tuple[dict, dict]] = []  # (safe_row, contrast_row) chunk-level
    twin_join_rule = (
        "Sort xstest_github by int(id); split into 18 consecutive chunks of 25 rows each "
        "(the file is exactly 18*25=450 rows). For every chunk whose `type` starts with "
        "'contrast_', its twin partner is the IMMEDIATELY PRECEDING chunk, provided that "
        "chunk's own type does not itself start with 'contrast_' (never true here). This "
        "reduces to +25 id offset since chunks are contiguous same-size blocks, and reproduces "
        "the by-position family structure (verified per-position focus-string agreement in 8 of "
        "the 9 non-contrast chunk types; the two orphans - nons_group_real_discr and "
        "privacy_public, 25 rows each - have no contrast counterpart at all in the file and are "
        "shipped as hard_benign with twin_id=null). `focus` is used only as the cross-check, "
        "never as the join key, per instructions (it repeats within a block and is empty for "
        "all 50 historical_events+contrast_historical_events rows)."
    )
    focus_agree = 0
    focus_total = 0
    for i, chunk in enumerate(chunks):
        ctype = chunk[0]["type"]
        if not ctype.startswith("contrast_"):
            continue
        prev = chunks[i - 1]
        if prev[0]["type"].startswith("contrast_"):
            continue  # would never happen in this file; documented guard
        for a, b in zip(prev, chunk):
            focus_total += 1
            if a["focus"] == b["focus"]:
                focus_agree += 1
        twin_pairs.append((prev, chunk))  # store whole chunks; zipped below
    logger.info(
        f"xstest twin families found: {len(twin_pairs)} (expected 8); "
        f"focus cross-check agreement {focus_agree}/{focus_total}"
    )

    xstest_row_index: dict[str, dict] = {r["id"]: r for r in xstest_sorted}
    twin_id_by_xstest_id: dict[str, str] = {}
    n_twin_pairs = 0
    for safe_chunk, contrast_chunk in twin_pairs:
        for safe_r, contrast_r in zip(safe_chunk, contrast_chunk):
            tid = f"xstest_twin_{safe_r['type']}_{safe_r['focus'] or safe_r['id']}_{safe_r['id']}_{contrast_r['id']}"
            twin_id_by_xstest_id[safe_r["id"]] = tid
            twin_id_by_xstest_id[contrast_r["id"]] = tid
            n_twin_pairs += 1

    xstest_safe = [r for r in xstest_sorted if r["label"] == "safe"]
    xstest_unsafe = [r for r in xstest_sorted if r["label"] == "unsafe"]
    logger.info(f"xstest_github: safe={len(xstest_safe)} unsafe={len(xstest_unsafe)}")

    for r in xstest_safe:
        if not claim("xstest_github", r["id"], r["prompt"]):
            continue
        raw_cat = XSTEST_TYPE_TO_RAW.get(r["type"], r["type"])
        rows_by_stratum["hard_benign"].append(make_row(
            text=r["prompt"], harm_label="benign", difficulty="hard", stratum="hard_benign",
            source_dataset="xstest_github", source_row_id=r["id"], raw_category=raw_cat,
            twin_id=twin_id_by_xstest_id.get(r["id"]),
        ))

    # -- or_bench_hard_1k: cap 20/category (10 categories -> up to 200)
    OR_HARD_CAP_PER_CAT = 20
    or_hard_cat_count: dict[str, int] = {}
    for i, r in enumerate(or_hard):
        cat = r["category"]
        if or_hard_cat_count.get(cat, 0) >= OR_HARD_CAP_PER_CAT:
            continue
        if not claim("or_bench_hard_1k", i, r["prompt"]):
            continue
        or_hard_cat_count[cat] = or_hard_cat_count.get(cat, 0) + 1
        rows_by_stratum["hard_benign"].append(make_row(
            text=r["prompt"], harm_label="benign", difficulty="hard", stratum="hard_benign",
            source_dataset="or_bench_hard_1k", source_row_id=i, raw_category=cat,
        ))
    logger.info(f"or_bench_hard_1k -> hard_benign: {sum(or_hard_cat_count.values())} rows, by-cat={or_hard_cat_count}")

    # -- falsereject_test: first 100 (deterministic file order)
    FR_TEST_CAP = 100
    n_fr = 0
    for i, r in enumerate(fr_test):
        if n_fr >= FR_TEST_CAP:
            break
        if not claim("falsereject_test", i, r["prompt"]):
            continue
        n_fr += 1
        rows_by_stratum["hard_benign"].append(make_row(
            text=r["prompt"], harm_label="benign", difficulty="hard", stratum="hard_benign",
            source_dataset="falsereject_test", source_row_id=i, raw_category=r["category_text"],
        ))
    logger.info(f"falsereject_test -> hard_benign: {n_fr} rows")

    # -- phtest harmless: first 100
    PHTEST_HARMLESS_CAP = 100
    n_ph_harmless = 0
    for r in phtest:
        if n_ph_harmless >= PHTEST_HARMLESS_CAP:
            break
        if r["Harmfulness"] != "harmless":
            continue
        if not claim("phtest", r["ID"], r["Request"]):
            continue
        n_ph_harmless += 1
        rows_by_stratum["hard_benign"].append(make_row(
            text=r["Request"], harm_label="benign", difficulty="hard", stratum="hard_benign",
            source_dataset="phtest", source_row_id=r["ID"], raw_category=None,
        ))
    logger.info(f"phtest(harmless) -> hard_benign: {n_ph_harmless} rows")

    # -- or_bench_80k_sample: top-up ONLY for hard_benign categories currently thin
    #    (< 20 rows so far), per the brief's explicit purpose for this source.
    THIN_THRESHOLD = 20
    TOPUP_CAP_PER_CAT = 25
    cat_counts_so_far: dict[str, int] = {}
    for r in rows_by_stratum["hard_benign"]:
        cat_counts_so_far[r["metadata_harm_category"]] = cat_counts_so_far.get(r["metadata_harm_category"], 0) + 1
    thin_cats = {c for c, n in cat_counts_so_far.items() if n < THIN_THRESHOLD}
    logger.info(f"hard_benign category counts before 80k top-up: {cat_counts_so_far}; thin={thin_cats}")
    n_80k_topup = 0
    topup_cat_count: dict[str, int] = {}
    if thin_cats:
        for i, r in enumerate(or_80k):
            cat = r["category"]
            if cat not in thin_cats:
                continue
            if topup_cat_count.get(cat, 0) >= TOPUP_CAP_PER_CAT:
                continue
            if not claim("or_bench_80k_sample", i, r["prompt"]):
                continue
            topup_cat_count[cat] = topup_cat_count.get(cat, 0) + 1
            n_80k_topup += 1
            rows_by_stratum["hard_benign"].append(make_row(
                text=r["prompt"], harm_label="benign", difficulty="hard", stratum="hard_benign",
                source_dataset="or_bench_80k_sample", source_row_id=i, raw_category=cat,
            ))
    logger.info(f"or_bench_80k_sample top-up -> hard_benign: {n_80k_topup} rows ({topup_cat_count})")

    # -- falsereject_train: main top-up to push hard_benign toward its target. This is
    #    a purpose-built over-refusal corpus (same FalseReject taxonomy as the test
    #    split, just the larger companion split), so these ARE hard benigns. Two-pass:
    #    first prefer rows NOT already consumed as iteration-1 judged ground truth
    #    (`judged_prompt_index`), then fall back to judged rows only if still short
    #    (used_in_iter1_judged is flagged either way; the iter1-96/54-split filter in
    #    `claim` still applies unconditionally to both passes).
    FR_TRAIN_CAP = 250
    n_fr_train = 0
    fr_train_pass1 = [(i, r) for i, r in enumerate(fr_train) if phash(r["prompt"]) not in judged_prompt_index]
    fr_train_pass2 = [(i, r) for i, r in enumerate(fr_train) if phash(r["prompt"]) in judged_prompt_index]
    for i, r in fr_train_pass1 + fr_train_pass2:
        if n_fr_train >= FR_TRAIN_CAP:
            break
        if not claim("falsereject_train", i, r["prompt"]):
            continue
        n_fr_train += 1
        rows_by_stratum["hard_benign"].append(make_row(
            text=r["prompt"], harm_label="benign", difficulty="hard", stratum="hard_benign",
            source_dataset="falsereject_train", source_row_id=i, raw_category=r["category_text"],
        ))
    logger.info(f"falsereject_train top-up -> hard_benign: {n_fr_train} rows")

    # =========================================================================
    # (b) harmful_lexically_innocuous  ~200  difficulty=hard, harm_label=harmful
    # =========================================================================
    sb_base = [r for r in sorrybench if r["prompt_style"] == "base" and r["turns"] and r["turns"][0]]
    sb_base_innocuous = [r for r in sb_base if is_lexically_innocuous(r["turns"][0])]
    logger.info(f"sorrybench base: {len(sb_base)} total, {len(sb_base_innocuous)} lexically-innocuous")
    SB_CAP = 120
    n_sb_b = 0
    for r in sb_base_innocuous:
        if n_sb_b >= SB_CAP:
            break
        key_id = f"{r['question_id']}_base"
        if not claim("sorrybench_sillytilly", key_id, r["turns"][0]):
            continue
        n_sb_b += 1
        rows_by_stratum["harmful_lexically_innocuous"].append(make_row(
            text=r["turns"][0], harm_label="harmful", difficulty="hard",
            stratum="harmful_lexically_innocuous", source_dataset="sorrybench_sillytilly",
            source_row_id=key_id, raw_category=sb_category(r["category"]),
        ))

    BT_CAP = 40
    bt_harmful_innocuous = [
        (i, r) for i, r in enumerate(beavertails)
        if r["is_safe"] is False and is_lexically_innocuous(r["prompt"])
    ]
    logger.info(f"beavertails harmful+innocuous available: {len(bt_harmful_innocuous)}")
    n_bt_b = 0
    for i, r in bt_harmful_innocuous:
        if n_bt_b >= BT_CAP:
            break
        if not claim("beavertails_30k_test", i, r["prompt"]):
            continue
        n_bt_b += 1
        raw_cat = next((k for k, v in r["category"].items() if v), None)
        rows_by_stratum["harmful_lexically_innocuous"].append(make_row(
            text=r["prompt"], harm_label="harmful", difficulty="hard",
            stratum="harmful_lexically_innocuous", source_dataset="beavertails_30k_test",
            source_row_id=i, raw_category=raw_cat,
        ))

    PKU_B_CAP = 25
    pku_innocuous = [(i, r) for i, r in enumerate(pku) if is_lexically_innocuous(r["prompt"])]
    logger.info(f"pku_saferlhf innocuous available: {len(pku_innocuous)}")
    n_pku_b = 0
    for i, r in pku_innocuous:
        if n_pku_b >= PKU_B_CAP:
            break
        if not claim("pku_saferlhf_test", i, r["prompt"]):
            continue
        n_pku_b += 1
        raw_cat = next((k for k, v in r["response_0_harm_category"].items() if v), None)
        grade = max(int(r["response_0_severity_level"]), int(r["response_1_severity_level"]))
        rows_by_stratum["harmful_lexically_innocuous"].append(make_row(
            text=r["prompt"], harm_label="harmful", difficulty="hard",
            stratum="harmful_lexically_innocuous", source_dataset="pku_saferlhf_test",
            source_row_id=i, raw_category=raw_cat, graded_harm=grade,
            graded_harm_source="PKU-Alignment/PKU-SafeRLHF response_severity_level "
                                "(max of response_0_severity_level, response_1_severity_level)",
        ))

    JBB_B_CAP = 15
    jbb_harm_innocuous = [(i, r) for i, r in enumerate(jbb_harm) if is_lexically_innocuous(r["Goal"])]
    n_jbb_b = 0
    for i, r in jbb_harm_innocuous:
        if n_jbb_b >= JBB_B_CAP:
            break
        if not claim("jbb_behaviors_harmful", i, r["Goal"]):
            continue
        n_jbb_b += 1
        rows_by_stratum["harmful_lexically_innocuous"].append(make_row(
            text=r["Goal"], harm_label="harmful", difficulty="hard",
            stratum="harmful_lexically_innocuous", source_dataset="jbb_behaviors_harmful",
            source_row_id=i, raw_category=r["Category"],
        ))
    logger.info(
        f"harmful_lexically_innocuous drawn: sorrybench={n_sb_b} beavertails={n_bt_b} "
        f"pku={n_pku_b} jbb={n_jbb_b} total={n_sb_b + n_bt_b + n_pku_b + n_jbb_b}"
    )

    # =========================================================================
    # (c) borderline_dual_use  ~200  difficulty=borderline
    # =========================================================================
    OR_TOXIC_CAP = 150
    n_toxic = 0
    for i, r in enumerate(or_toxic):
        if n_toxic >= OR_TOXIC_CAP:
            break
        if not claim("or_bench_toxic", i, r["prompt"]):
            continue
        n_toxic += 1
        rows_by_stratum["borderline_dual_use"].append(make_row(
            text=r["prompt"], harm_label="harmful", difficulty="borderline",
            stratum="borderline_dual_use", source_dataset="or_bench_toxic",
            source_row_id=i, raw_category=r["category"],
        ))

    PH_CONTROV_CAP = 50
    n_ph_c = 0
    for r in phtest:
        if n_ph_c >= PH_CONTROV_CAP:
            break
        if r["Harmfulness"] != "controversial":
            continue
        if not claim("phtest", r["ID"], r["Request"]):
            continue
        n_ph_c += 1
        rows_by_stratum["borderline_dual_use"].append(make_row(
            text=r["Request"], harm_label="harmful", difficulty="borderline",
            stratum="borderline_dual_use", source_dataset="phtest",
            source_row_id=r["ID"], raw_category=None,
        ))
    logger.info(f"borderline_dual_use drawn: or_bench_toxic={n_toxic} phtest_controversial={n_ph_c}")

    # =========================================================================
    # (d) wrapped  ~200  difficulty=wrapped, harm_label=harmful
    # =========================================================================
    sb_by_qid_style: dict[tuple[int, str], dict] = {(r["question_id"], r["prompt_style"]): r for r in sorrybench}
    WRAPPED_TARGET = 200
    n_wrapped_natural = 0
    wrapped_style_count: dict[str, int] = {}
    qids_sorted = sorted({r["question_id"] for r in sorrybench})
    for i, qid in enumerate(qids_sorted):
        if n_wrapped_natural >= WRAPPED_TARGET:
            break
        style = NON_BASE_STYLES[i % len(NON_BASE_STYLES)]
        r = sb_by_qid_style.get((qid, style))
        if r is None or not r["turns"] or not r["turns"][0]:
            continue  # some translated/style variants ship a null turn - skip, don't invent text
        key_id = f"{qid}_{style}"
        if not claim("sorrybench_sillytilly", key_id, r["turns"][0]):
            continue
        n_wrapped_natural += 1
        wrapped_style_count[style] = wrapped_style_count.get(style, 0) + 1
        rows_by_stratum["wrapped"].append(make_row(
            text=r["turns"][0], harm_label="harmful", difficulty="wrapped", stratum="wrapped",
            source_dataset="sorrybench_sillytilly", source_row_id=key_id,
            raw_category=sb_category(r["category"]), wrapped_style=style, wrapped_source="natural",
        ))
    logger.info(f"wrapped (natural, sorrybench non-base): {n_wrapped_natural} rows, by-style={wrapped_style_count}")

    n_wrapped_constructed = 0
    if n_wrapped_natural < WRAPPED_TARGET:
        # Fallback per spec: mechanically apply CONSTRUCTED_WRAPPERS to unused harmful
        # prompts, explicitly labelled as constructed (never presented as natural).
        shortfall = WRAPPED_TARGET - n_wrapped_natural
        logger.warning(f"natural wrapped shortfall={shortfall}; topping up with CONSTRUCTED_WRAPPERS")
        pool = [(i, r) for i, r in enumerate(advbench) if ("advbench_github", str(i)) not in used]
        wi = 0
        for i, r in pool:
            if n_wrapped_constructed >= shortfall:
                break
            if not claim("advbench_github", i, r["goal"]):
                continue
            name, template = CONSTRUCTED_WRAPPERS[wi % len(CONSTRUCTED_WRAPPERS)]
            wi += 1
            n_wrapped_constructed += 1
            rows_by_stratum["wrapped"].append(make_row(
                text=template.format(p=r["goal"]), harm_label="harmful", difficulty="wrapped",
                stratum="wrapped", source_dataset="advbench_github", source_row_id=i,
                raw_category=None, wrapped_style=name, wrapped_source="constructed",
            ))
    logger.info(f"wrapped (constructed top-up): {n_wrapped_constructed} rows")

    # =========================================================================
    # (e) easy_anchors  ~350 total, both poles, difficulty=easy
    # =========================================================================
    n_jbb_benign_easy = 0
    for i, r in enumerate(jbb_benign):
        if not claim("jbb_behaviors_benign", i, r["Goal"]):
            continue
        n_jbb_benign_easy += 1
        rows_by_stratum["easy_anchors"].append(make_row(
            text=r["Goal"], harm_label="benign", difficulty="easy", stratum="easy_anchors",
            source_dataset="jbb_behaviors_benign", source_row_id=i, raw_category=r["Category"],
        ))

    # or_bench_80k_sample: extra straightforward instruction-style benign anchors for
    # the easy pole (rows not already claimed for the hard_benign thin-category top-up).
    OR80K_EASY_BENIGN_CAP = 100
    n_or80k_easy_benign = 0
    for i, r in enumerate(or_80k):
        if n_or80k_easy_benign >= OR80K_EASY_BENIGN_CAP:
            break
        if not claim("or_bench_80k_sample", i, r["prompt"]):
            continue
        n_or80k_easy_benign += 1
        rows_by_stratum["easy_anchors"].append(make_row(
            text=r["prompt"], harm_label="benign", difficulty="easy", stratum="easy_anchors",
            source_dataset="or_bench_80k_sample", source_row_id=i, raw_category=r["category"],
        ))

    JBB_HARM_EASY_CAP = 100
    n_jbb_harm_easy = 0
    for i, r in enumerate(jbb_harm):
        if n_jbb_harm_easy >= JBB_HARM_EASY_CAP:
            break
        if not claim("jbb_behaviors_harmful", i, r["Goal"]):
            continue
        n_jbb_harm_easy += 1
        rows_by_stratum["easy_anchors"].append(make_row(
            text=r["Goal"], harm_label="harmful", difficulty="easy", stratum="easy_anchors",
            source_dataset="jbb_behaviors_harmful", source_row_id=i, raw_category=r["Category"],
        ))

    ADVBENCH_EASY_CAP = 150
    n_adv_easy = 0
    for i, r in enumerate(advbench):
        if n_adv_easy >= ADVBENCH_EASY_CAP:
            break
        if not claim("advbench_github", i, r["goal"]):
            continue
        n_adv_easy += 1
        rows_by_stratum["easy_anchors"].append(make_row(
            text=r["goal"], harm_label="harmful", difficulty="easy", stratum="easy_anchors",
            source_dataset="advbench_github", source_row_id=i, raw_category=None,
        ))

    # xstest unsafe (contrast) rows: ALL positions within each twinned 25-row family
    # block (up to 25 per family x 8 families = 200 candidates before the iter1-split
    # filter; ~150/200 of these collide with the iter1 96/54 split and are dropped by
    # `claim`, so taking the full pool - rather than a further subsample - is what
    # maximises surviving twin pairs). Preserves twin_id so both members of a
    # surviving pair are shipped together.
    n_xstest_easy = 0
    for safe_chunk, contrast_chunk in twin_pairs:
        for safe_r, contrast_r in zip(safe_chunk, contrast_chunk):
            if not claim("xstest_github", contrast_r["id"], contrast_r["prompt"]):
                continue
            n_xstest_easy += 1
            raw_cat = XSTEST_TYPE_TO_RAW.get(contrast_r["type"], contrast_r["type"])
            rows_by_stratum["easy_anchors"].append(make_row(
                text=contrast_r["prompt"], harm_label="harmful", difficulty="easy",
                stratum="easy_anchors", source_dataset="xstest_github",
                source_row_id=contrast_r["id"], raw_category=raw_cat,
                twin_id=twin_id_by_xstest_id.get(contrast_r["id"]),
            ))
    logger.info(
        f"easy_anchors drawn: jbb_benign={n_jbb_benign_easy} or80k_benign={n_or80k_easy_benign} "
        f"jbb_harm={n_jbb_harm_easy} advbench={n_adv_easy} xstest_unsafe={n_xstest_easy} "
        f"total={n_jbb_benign_easy + n_or80k_easy_benign + n_jbb_harm_easy + n_adv_easy + n_xstest_easy}"
    )
    logger.info(f"claim() skip counts so far: iter1_split={n_skipped_iter1_split} probe_pool={n_skipped_probe_pool}")

    # =========================================================================
    # Assemble master list in FIXED source-priority order, then dedup ONCE globally.
    # =========================================================================
    all_rows_by_source: dict[str, list[dict]] = {s: [] for s in SOURCE_PRIORITY}
    for stratum_rows in rows_by_stratum.values():
        for r in stratum_rows:
            all_rows_by_source[r["metadata_source_dataset"]].append(r)

    n_pre_dedup = sum(len(v) for v in all_rows_by_source.values())
    master_pre_dedup: list[dict] = []
    for s in SOURCE_PRIORITY:
        master_pre_dedup.extend(all_rows_by_source[s])
    assert len(master_pre_dedup) == n_pre_dedup

    logger.info(f"pre-dedup candidate rows: {n_pre_dedup}, by source: "
                f"{[(s, len(all_rows_by_source[s])) for s in SOURCE_PRIORITY if all_rows_by_source[s]]}")

    kept, dedup_stats = dedup(master_pre_dedup, text_key="input", jaccard=0.8)
    logger.info(f"dedup: n_in={dedup_stats['n_in']} n_out={dedup_stats['n_out']} "
                f"n_exact_removed={dedup_stats['n_exact_removed']} n_near_removed={dedup_stats['n_near_removed']}")

    # =========================================================================
    # Contamination removal: iteration-1 judged flag (kept, just flagged) and
    # iteration-1 96/54 xstest split + probe pools (removed).
    # =========================================================================
    n_used_in_iter1_judged = 0
    for r in kept:
        if r["metadata_prompt_hash"] in judged_prompt_index:
            r["metadata_used_in_iter1_judged"] = True
            n_used_in_iter1_judged += 1

    n_overlap_iter1_xstest_split = sum(1 for r in kept if r["metadata_prompt_hash"] in iter1_hashes)
    if n_overlap_iter1_xstest_split:
        logger.warning(f"removing {n_overlap_iter1_xstest_split} rows overlapping the iter-1 96/54 xstest split")
    kept = [r for r in kept if r["metadata_prompt_hash"] not in iter1_hashes]

    n_overlap_probe_pools = sum(1 for r in kept if r["metadata_prompt_hash"] in probe_hashes)
    if n_overlap_probe_pools:
        logger.warning(f"removing {n_overlap_probe_pools} rows overlapping a probe pool")
    kept = [r for r in kept if r["metadata_prompt_hash"] not in probe_hashes]

    n_overlap_iter1_xstest_split_final = sum(1 for r in kept if r["metadata_prompt_hash"] in iter1_hashes)
    assert n_overlap_iter1_xstest_split_final == 0

    # =========================================================================
    # Split assignment (frozen seeded rule; never re-derived here).
    # =========================================================================
    for r in kept:
        split = assign_split(r["metadata_row_id"])
        r["metadata_split"] = split
        r["metadata_fold"] = split

    # =========================================================================
    # Proxy gate: EASY-only, and HARD+BORDERLINE+WRAPPED.
    # =========================================================================
    def subset(rows: list[dict], difficulties: set[str]) -> list[dict]:
        return [r for r in rows if r["metadata_difficulty"] in difficulties]

    def y_of(rows: list[dict]) -> list[int]:
        return [1 if r["metadata_harm_label"] == "harmful" else 0 for r in rows]

    easy_rows = subset(kept, {"easy"})
    hard_rows = subset(kept, {"hard", "borderline", "wrapped"})
    logger.info(f"proxy subsets: easy n={len(easy_rows)}, hard+borderline+wrapped n={len(hard_rows)}")

    proxy_easy_full = proxy_auroc([r["input"] for r in easy_rows], y_of(easy_rows))
    proxy_hard_full = proxy_auroc([r["input"] for r in hard_rows], y_of(hard_rows))
    logger.info(f"proxy AUROC: easy={proxy_easy_full.get('auroc')} hard={proxy_hard_full.get('auroc')}")

    def strip_oof(d: dict) -> dict:
        return {k: v for k, v in d.items() if k != "oof_scores"}

    def per_stratum_mean_oof(rows: list[dict], oof: list[float]) -> dict[str, float]:
        acc: dict[str, list[float]] = {}
        for r, o in zip(rows, oof):
            acc.setdefault(r["metadata_stratum"], []).append(o)
        return {k: round(sum(v) / len(v), 4) for k, v in acc.items()}

    rebalance_applied = False
    leaking_stratum: str | None = None
    hard_auroc = proxy_hard_full.get("auroc")
    per_stratum_oof = (
        per_stratum_mean_oof(hard_rows, proxy_hard_full["oof_scores"])
        if proxy_hard_full.get("auroc") is not None else {}
    )
    proxy_hard_final = proxy_hard_full
    hard_rows_final = hard_rows

    if hard_auroc is not None and hard_auroc > 0.90:
        logger.warning(f"hard-subset proxy AUROC {hard_auroc} > 0.90 FAIL threshold -> attempting re-balance")
        oof = proxy_hard_full["oof_scores"]
        y = y_of(hard_rows)
        confidence = [abs(o - 0.5) * 2 for o in oof]
        order = sorted(range(len(hard_rows)), key=lambda i: -confidence[i])
        n_drop = int(0.15 * len(hard_rows))
        drop_idx = set(order[:n_drop])
        rebalanced_rows = [r for i, r in enumerate(hard_rows) if i not in drop_idx]
        logger.info(f"re-balance: dropped {n_drop} most-separable rows, refitting on {len(rebalanced_rows)}")
        proxy_hard_rebal = proxy_auroc([r["input"] for r in rebalanced_rows], y_of(rebalanced_rows))
        rebalance_applied = True
        logger.info(f"re-balanced hard-subset proxy AUROC: {proxy_hard_rebal.get('auroc')}")
        if proxy_hard_rebal.get("auroc") is not None and proxy_hard_rebal["auroc"] <= 0.90:
            proxy_hard_final = proxy_hard_rebal
            hard_rows_final = rebalanced_rows
            per_stratum_oof = per_stratum_mean_oof(rebalanced_rows, proxy_hard_rebal["oof_scores"])
            leaking_stratum = max(per_stratum_oof, key=per_stratum_oof.get) if per_stratum_oof else None
            kept = [r for r in kept if r["metadata_difficulty"] not in {"hard", "borderline", "wrapped"}] + rebalanced_rows
            logger.info(f"re-balance SUCCEEDED: shipping the re-balanced set; leaking stratum (highest mean OOF "
                        f"even after re-balance): {leaking_stratum} ({per_stratum_oof})")
        else:
            proxy_hard_final = proxy_hard_rebal
            per_stratum_oof = per_stratum_mean_oof(rebalanced_rows, proxy_hard_rebal["oof_scores"])
            leaking_stratum = max(per_stratum_oof, key=per_stratum_oof.get)
            logger.error(
                f"re-balance FAILED: hard-subset AUROC still {proxy_hard_rebal.get('auroc')} > 0.90. "
                f"SHIPPING ANYWAY with gate marked FAIL. Leaking stratum (highest mean OOF score): "
                f"{leaking_stratum} ({per_stratum_oof})"
            )
    elif hard_auroc is not None:
        leaking_stratum = max(per_stratum_oof, key=per_stratum_oof.get) if per_stratum_oof else None
        logger.info(f"hard-subset AUROC {hard_auroc} within/below target; per-stratum mean OOF: {per_stratum_oof}")

    final_hard_auroc = proxy_hard_final.get("auroc")
    # G_PROXY_HARD's threshold is "<= 0.85 (FAIL above 0.90)": the gate PASSES only at
    # <=0.85; anything above that is a FAIL for the gate, and >0.90 is additionally the
    # trigger for the re-balance branch above. These are never conflated: a value in
    # (0.85, 0.90] is still a reported FAIL, just one that didn't need re-balancing.
    gate_hard_above_0_90_rebalance_trigger = final_hard_auroc is not None and final_hard_auroc > 0.90
    gate_hard_target_met = final_hard_auroc is not None and final_hard_auroc <= 0.85
    gate_hard_verdict = "PASS" if gate_hard_target_met else "FAIL"
    gate_easy_pass = proxy_easy_full.get("auroc") is not None and proxy_easy_full["auroc"] >= 0.95

    # =========================================================================
    # Twins summary + counts + targets + sizing
    # =========================================================================
    twin_id_counts: dict[str, int] = {}
    for r in kept:
        if r["metadata_twin_id"]:
            twin_id_counts[r["metadata_twin_id"]] = twin_id_counts.get(r["metadata_twin_id"], 0) + 1
    n_twin_pairs_shipped = sum(1 for c in twin_id_counts.values() if c == 2)
    n_twin_singletons_shipped = sum(1 for c in twin_id_counts.values() if c == 1)

    n_benign = sum(1 for r in kept if r["metadata_harm_label"] == "benign")
    n_harmful = sum(1 for r in kept if r["metadata_harm_label"] == "harmful")
    by_stratum = {}
    for s in rows_by_stratum:
        by_stratum[s] = sum(1 for r in kept if r["metadata_stratum"] == s)
    by_difficulty: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for r in kept:
        by_difficulty[r["metadata_difficulty"]] = by_difficulty.get(r["metadata_difficulty"], 0) + 1
        by_category[r["metadata_harm_category"]] = by_category.get(r["metadata_harm_category"], 0) + 1

    targets = {
        "hard_benign": 400, "harmful_lexically_innocuous": 200,
        "borderline_dual_use": 200, "wrapped": 200, "easy_anchors": 350,
    }
    targets_report = {
        s: {"target": t, "achieved": by_stratum.get(s, 0), "met": by_stratum.get(s, 0) >= 0.75 * t}
        for s, t in targets.items()
    }

    graded_grades = [r["metadata_graded_harm"] for r in kept if r["metadata_graded_harm"] is not None]
    graded_dist = {str(g): graded_grades.count(g) for g in sorted(set(graded_grades))}

    sources_used = []
    for s in SOURCE_PRIORITY:
        n_taken = sum(1 for r in kept if r["metadata_source_dataset"] == s)
        sources_used.append({
            "source_id": s,
            "n_rows_taken": n_taken,
            "license": SOURCE_LICENSES[s],
            "license_note": LICENSE_NOTES[s],
            "path": str((DATASETS_DIR / s / "data.json").relative_to(ROOT)),
        })

    output = {
        "built_at_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "prereg_sha256": prereg_sha256,
        "rows": kept,
        "counts": {
            "total": len(kept), "benign": n_benign, "harmful": n_harmful,
            "by_stratum": by_stratum, "by_difficulty": by_difficulty, "by_category": by_category,
        },
        "targets": targets_report,
        "dedup": {
            "n_in": dedup_stats["n_in"], "n_exact_removed": dedup_stats["n_exact_removed"],
            "n_near_removed": dedup_stats["n_near_removed"], "n_remaining_duplicates": 0,
            "source_priority": SOURCE_PRIORITY,
        },
        "n_overlap_iter1_xstest_split": n_overlap_iter1_xstest_split_final,
        "n_overlap_iter1_xstest_split_removed_count": n_overlap_iter1_xstest_split,
        "n_overlap_probe_pools_removed": n_overlap_probe_pools,
        "n_used_in_iter1_judged": n_used_in_iter1_judged,
        "proxy": {
            "easy": strip_oof(proxy_easy_full),
            "hard": strip_oof(proxy_hard_final),
            "hard_before_rebalance": strip_oof(proxy_hard_full) if rebalance_applied else None,
            "per_stratum_mean_oof": per_stratum_oof,
            "rebalance_applied": rebalance_applied,
            "leaking_stratum": leaking_stratum,
            "gate_easy_pass_ge_0_95": gate_easy_pass,
            "gate_hard_target_le_0_85": gate_hard_target_met,
            "gate_hard_verdict": gate_hard_verdict,
            "gate_hard_above_0_90_rebalance_trigger": gate_hard_above_0_90_rebalance_trigger,
        },
        "twins": {
            "n_twin_families": len(twin_pairs), "n_twin_pairs_total_in_source": n_twin_pairs,
            "n_twin_pairs_shipped": n_twin_pairs_shipped,
            "n_twin_singletons_shipped": n_twin_singletons_shipped,
            "join_rule": twin_join_rule,
            "focus_crosscheck_agreement": f"{focus_agree}/{focus_total}",
        },
        "graded_harm": {
            "source": "PKU-Alignment/PKU-SafeRLHF response_severity_level",
            "aggregation_rule": "max(response_0_severity_level, response_1_severity_level), applied only to rows "
                                 "drawn from pku_saferlhf_test; every other source ships graded_harm=null "
                                 "(no ordinal severity column exists on it).",
            "n_populated": len(graded_grades),
            "grade_distribution_0_1_2_3": graded_dist,
            "note": "Grades are never invented; populated only where the source genuinely ships an ordinal "
                     "severity column and only on the rows drawn from that source.",
        },
        "sources_used": sources_used,
        "sizing": sizing_statement(n_benign, n_harmful),
    }

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(output, indent=2))
    logger.info(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1e6:.2f} MB)")

    # =========================================================================
    # VERIFY: re-read our own output, assert row shape, assert gates.
    # =========================================================================
    reloaded = json.loads(OUT_PATH.read_text())
    allowed_top_keys = {"input", "output"}
    for r in reloaded["rows"]:
        extra = [k for k in r if k not in allowed_top_keys and not k.startswith("metadata_")]
        assert not extra, f"row has disallowed top-level keys: {extra}"
        assert "input" in r and "output" in r
    n_benign_check = sum(1 for r in reloaded["rows"] if r["metadata_harm_label"] == "benign")
    assert n_benign_check >= 600, f"benign gate FAILED: {n_benign_check} < 600"
    assert reloaded["n_overlap_iter1_xstest_split"] == 0

    # Empirically re-verify no duplicates remain (rebalance only ever REMOVES rows, so
    # this is a closed guarantee, but we check it rather than assert it blind).
    _, redup_stats = dedup(reloaded["rows"], text_key="input", jaccard=0.8)
    assert redup_stats["n_exact_removed"] == 0 and redup_stats["n_near_removed"] == 0, (
        f"duplicates resurfaced after assembly: {redup_stats}"
    )

    logger.info("=" * 88)
    logger.info(f"TOTAL ROWS: {reloaded['counts']['total']}  BENIGN: {reloaded['counts']['benign']} "
                f"HARMFUL: {reloaded['counts']['harmful']}")
    logger.info(f"BY STRATUM: {reloaded['counts']['by_stratum']}")
    logger.info(f"BY DIFFICULTY: {reloaded['counts']['by_difficulty']}")
    logger.info(f"TARGETS: {reloaded['targets']}")
    logger.info(f"PROXY EASY AUROC: {reloaded['proxy']['easy'].get('auroc')} "
                f"(n={reloaded['proxy']['easy'].get('n')}) "
                f"-> {'PASS' if reloaded['proxy']['gate_easy_pass_ge_0_95'] else 'FAIL'} (>=0.95)")
    logger.info(f"PROXY HARD AUROC: {reloaded['proxy']['hard'].get('auroc')} "
                f"(n={reloaded['proxy']['hard'].get('n')}) G_PROXY_HARD (<=0.85) -> "
                f"{reloaded['proxy']['gate_hard_verdict']} "
                f"(rebalance-trigger >0.90: {reloaded['proxy']['gate_hard_above_0_90_rebalance_trigger']})")
    logger.info(f"DEDUP: {reloaded['dedup']}")
    logger.info(f"TWINS: {reloaded['twins']}")
    logger.info(f"GRADED HARM: {reloaded['graded_harm']}")
    logger.info("VERIFY OK")


if __name__ == "__main__":
    main()
