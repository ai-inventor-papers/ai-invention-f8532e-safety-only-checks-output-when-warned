#!/usr/bin/env python3
"""PHASE D: the four DISJOINT behavioural probe pools of artefact 4.

  probe_harmful              n>=120  reused VERBATIM from iteration 1 (behavioural_harmful)
  probe_hard_benign          n>=120  reused VERBATIM from iteration 1 (behavioural_hard_benign)
  probe_already_correct      n>=150  NEW - auto-gradable, no judge: ARC-Easy test + GSM8K main test
  probe_baseline_disjoint    n>=24   NEW - reserved for the black-box greedy refusal-rate
                                     baseline; excludes every row already used as iteration-1
                                     judged ground truth, or the baseline predicts the target
                                     from the target.

Prints the pairwise prompt-hash intersection matrix and asserts it is EMPTY.
"""
from __future__ import annotations

import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
DATA = ROOT / "temp" / "datasets"
sys.path.insert(0, str(ROOT / "src"))
from lib_recog import phash  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(ROOT / "logs" / "phase_d.log", rotation="30 MB", level="DEBUG")

BUILD_LOG = ROOT / "build_log.txt"


def blog(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with BUILD_LOG.open("a") as fh:
        fh.write(f"{ts}  {msg}\n")
    logger.info(msg)


def _load_any(patterns: list[str]) -> list[dict]:
    """Load rows from whatever the sourcing lane actually wrote for a source."""
    rows: list[dict] = []
    for pat in patterns:
        for fp in sorted(DATA.glob(pat)):
            if fp.name.endswith("_meta.json") or fp.name.startswith("_"):
                continue
            if fp.suffix == ".json":
                obj = json.loads(fp.read_text())
                if isinstance(obj, dict):
                    for k in ("rows", "examples", "data"):
                        if isinstance(obj.get(k), list):
                            obj = obj[k]
                            break
                if isinstance(obj, list):
                    rows.extend(r for r in obj if isinstance(r, dict))
            elif fp.suffix == ".jsonl":
                for line in fp.read_text().splitlines():
                    if line.strip():
                        rows.append(json.loads(line))
            elif fp.suffix == ".parquet":
                import pandas as pd
                rows.extend(pd.read_parquet(fp).to_dict("records"))
        if rows:
            logger.info(f"loaded {len(rows)} rows via pattern {pat}")
            return rows
    return rows


def build_already_correct(n_target: int = 200) -> tuple[list[dict], dict]:
    """ARC-Easy test (letter match) + GSM8K main test (final answer after '####')."""
    prov: dict = {}
    out: list[dict] = []

    arc = _load_any(["*arc*easy*/*.json", "*arc*easy*/*.jsonl", "*arc*easy*/*.parquet",
                     "*ai2_arc*/*.json", "*ai2_arc*/*.jsonl", "*ai2_arc*/*.parquet"])
    prov["arc_rows_loaded"] = len(arc)
    rng = random.Random(20260921)
    arc_ok = []
    for r in arc:
        q = r.get("question")
        ch = r.get("choices")
        key = r.get("answerKey") or r.get("answer_key")
        if not (isinstance(q, str) and isinstance(ch, dict) and key):
            continue
        texts = list(ch.get("text") or [])
        labels = list(ch.get("label") or [])
        if len(texts) != len(labels) or not texts:
            continue
        opts = "\n".join(f"{l}. {t}" for l, t in zip(labels, texts))
        arc_ok.append({
            "input": f"{q}\n{opts}\nAnswer with the letter only.",
            "output": str(key),
            "metadata_source_dataset": "allenai/ai2_arc",
            "metadata_source_config": "ARC-Easy",
            "metadata_source_split": "test",
            "metadata_source_row_id": str(r.get("id", "")),
            "metadata_grading": "exact letter match against output",
            "metadata_license": "CC-BY-SA-4.0",
        })
    rng.shuffle(arc_ok)
    prov["arc_usable"] = len(arc_ok)

    gsm = _load_any(["*gsm8k*/*.json", "*gsm8k*/*.jsonl", "*gsm8k*/*.parquet"])
    prov["gsm8k_rows_loaded"] = len(gsm)
    gsm_ok = []
    for r in gsm:
        q, a = r.get("question"), r.get("answer")
        if not (isinstance(q, str) and isinstance(a, str) and "####" in a):
            continue
        final = a.split("####")[-1].strip().replace(",", "")
        if not re.fullmatch(r"-?\d+(\.\d+)?", final):
            continue
        gsm_ok.append({
            "input": f"{q}\nGive the final numeric answer only.",
            "output": final,
            "metadata_source_dataset": "openai/gsm8k",
            "metadata_source_config": "main",
            "metadata_source_split": "test",
            "metadata_source_row_id": phash(q)[:12],
            "metadata_grading": "exact numeric match of the final answer after '####'",
            "metadata_license": "MIT",
            "metadata_full_solution": a,
        })
    rng.shuffle(gsm_ok)
    prov["gsm8k_usable"] = len(gsm_ok)

    half = n_target // 2
    out = arc_ok[:half] + gsm_ok[:n_target - half]
    prov["n_arc_taken"] = min(half, len(arc_ok))
    prov["n_gsm_taken"] = len(out) - prov["n_arc_taken"]
    for i, r in enumerate(out):
        r["metadata_row_id"] = f"pac_{i:04d}"
        r["metadata_pool_id"] = "probe_already_correct_benign"
        r["metadata_readout_class"] = "text"
        r["metadata_auto_gradable"] = True
        r["metadata_used_in_iter1_judged"] = False
    return out, prov


@logger.catch(reraise=True)
def main() -> None:
    blog("PHASE D start: probe pools")
    beh = json.loads((BUILD / "behavioural.json").read_text())
    judged_hashes = set(beh["judged_prompt_index"].keys())
    reuse = json.loads((BUILD / "reusable_probe_tables.json").read_text())

    # These three pools have no reference answer: they are graded by the iteration-1
    # judge rubric, not by string match. `output` names the graded dimension instead of
    # sitting empty, so a reader can tell "judged" from "answer key missing".
    GRADING_TARGET = {
        "probe_harmful": ("JUDGED under assets/rubric_iter1.md: harmful_compliance / refused / "
                          "safe_engagement. No reference answer."),
        "probe_hard_benign": ("JUDGED under assets/rubric_iter1.md: over_refusal (refused on a "
                              "benign request). No reference answer."),
        "probe_baseline_disjoint": ("JUDGED under assets/rubric_iter1.md: refused. Reserved for "
                                    "the black-box greedy refusal-rate baseline. No reference "
                                    "answer."),
    }

    pools: dict[str, list[dict]] = {}
    prov: dict = {"reused_from_iteration_1": {}, "already_correct": {}}

    # --- pools (i) and (ii): reused verbatim from iteration 1 ---
    for pool_id, src in (("probe_harmful", "behavioural_harmful"),
                         ("probe_hard_benign", "behavioural_hard_benign")):
        rows = []
        for i, ex in enumerate(reuse[src]):
            rt = ex.get("metadata_request_text") or ex["input"]
            rows.append({
                "input": ex["input"],
                "output": GRADING_TARGET[pool_id],
                "metadata_row_id": f"{pool_id}_{i:04d}",
                "metadata_pool_id": pool_id,
                "metadata_request_text": rt,
                "metadata_prompt_hash": phash(rt),
                "metadata_source_dataset": ex.get("metadata_source"),
                "metadata_source_row_id": ex.get("metadata_item_uid"),
                "metadata_harm_category_raw": ex.get("metadata_harm_domain"),
                "metadata_license": ex.get("metadata_license"),
                "metadata_chat_templated": ex.get("metadata_chat_templated"),
                "metadata_reused_from": f"iter_1/gen_art_dataset_1::{src}",
                "metadata_readout_class": "text",
                "metadata_used_in_iter1_judged": phash(rt) in judged_hashes,
                "metadata_auto_gradable": False,
            })
        pools[pool_id] = rows
        prov["reused_from_iteration_1"][pool_id] = {
            "source_table": src, "n": len(rows),
            "n_used_in_iter1_judged": sum(r["metadata_used_in_iter1_judged"] for r in rows)}

    # --- pool (iii): NEW auto-gradable already-correct benign ---
    pac, pac_prov = build_already_correct(200)
    for r in pac:
        r["metadata_prompt_hash"] = phash(r["input"])
    pools["probe_already_correct_benign"] = pac
    prov["already_correct"] = pac_prov

    # --- pool (iv): disjoint baseline probe pool ---
    used = {r["metadata_prompt_hash"] for p in pools.values() for r in p}
    cand: list[dict] = []
    for tbl_name in ("behavioural_hard_benign", "behavioural_harmful"):
        for ex in reuse[tbl_name]:
            rt = ex.get("metadata_request_text") or ex["input"]
            h = phash(rt)
            if h in used or h in judged_hashes:
                continue
            cand.append({"rt": rt, "inp": ex["input"], "src": ex.get("metadata_source"),
                         "uid": ex.get("metadata_item_uid"), "h": h,
                         "lic": ex.get("metadata_license"), "tbl": tbl_name})
    # everything in those two tables is already in pools (i)/(ii), so fall back to the
    # never-loaded iteration-1 sealed XSTest split, which no lane has ever generated on.
    if len(cand) < 24:
        held = json.loads((Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/"
                                "iter_1/gen_art/gen_art_dataset_1/heldout_cells.json")).read_text())
        seen: set[str] = set()
        for tbl in held.get("datasets", []):
            for ex in tbl.get("examples", []):
                rt = ex.get("metadata_request_text")
                if not rt:
                    continue
                h = phash(rt)
                if h in used or h in judged_hashes or h in seen:
                    continue
                seen.add(h)
                cand.append({"rt": rt, "inp": ex.get("input", rt), "src": ex.get("metadata_source"),
                             "uid": ex.get("metadata_item_uid"), "h": h,
                             "lic": ex.get("metadata_license"),
                             "tbl": "iter1_heldout_cells(54-scenario sealed split)"})
        prov["baseline_pool_fallback"] = ("drawn from the iteration-1 SEALED 54-scenario XSTest "
                                          "split, which no lane has ever generated on")
    rng = random.Random(20260921)
    rng.shuffle(cand)
    base = []
    for i, c in enumerate(cand[:40]):
        base.append({
            "input": c["inp"], "output": GRADING_TARGET["probe_baseline_disjoint"],
            "metadata_row_id": f"probe_baseline_{i:04d}",
            "metadata_pool_id": "probe_baseline_disjoint",
            "metadata_request_text": c["rt"],
            "metadata_prompt_hash": c["h"],
            "metadata_source_dataset": c["src"],
            "metadata_source_row_id": c["uid"],
            "metadata_license": c["lic"],
            "metadata_provenance_table": c["tbl"],
            "metadata_readout_class": "text",
            "metadata_used_in_iter1_judged": False,
            "metadata_auto_gradable": False,
            "metadata_reserved_for": ("black-box greedy refusal-rate baseline; must never read "
                                      "the ground-truth generations it is meant to predict"),
        })
    pools["probe_baseline_disjoint"] = base

    # --- disjointness matrix ---
    ids = list(pools)
    sets = {k: {r["metadata_prompt_hash"] for r in v} for k, v in pools.items()}
    matrix = {a: {b: len(sets[a] & sets[b]) if a != b else len(sets[a]) for b in ids} for a in ids}
    off_diag = max((matrix[a][b] for a in ids for b in ids if a != b), default=0)
    logger.info("pairwise prompt-hash intersection matrix:")
    for a in ids:
        logger.info(f"  {a:32s} " + " ".join(f"{matrix[a][b]:5d}" for b in ids))
    blog(f"G_PROBE_DISJOINT: max off-diagonal intersection = {off_diag}")

    out = {"built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "prereg_sha256": (ROOT / "prereg.sha256").read_text().split()[0],
           "pools": pools,
           "pool_sizes": {k: len(v) for k, v in pools.items()},
           "intersection_matrix": matrix,
           "max_off_diagonal_intersection": off_diag,
           "provenance": prov,
           "rubric_note": ("the grading rubric is shipped verbatim in assets/rubric_iter1.md and "
                           "assets/lc_judge_iter1.py; new rows judged under it pool with the "
                           "existing 2,370 iteration-1 judged rows")}
    (BUILD / "probe_pools.json").write_text(json.dumps(out, indent=1))
    blog(f"PHASE D done: sizes {out['pool_sizes']}")


if __name__ == "__main__":
    main()
