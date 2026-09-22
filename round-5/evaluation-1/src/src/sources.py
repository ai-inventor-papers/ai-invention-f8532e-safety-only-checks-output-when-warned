"""S2. Source manifest: every file this audit reads, with size, mtime, sha256.

The DISK is authoritative (prereg_eval.json governing_rule). Nothing here writes
to a source tree; every source path is opened read-only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

LOOP = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")

I2_DATA = LOOP / "iter_2/gen_art/gen_art_dataset_1"
I2_EXP1 = LOOP / "iter_2/gen_art/gen_art_experiment_1"
I3_EXP1 = LOOP / "iter_3/gen_art/gen_art_experiment_1"
I3_EVAL1 = LOOP / "iter_3/gen_art/gen_art_evaluation_1"
I4_EXP1 = LOOP / "iter_4/gen_art/gen_art_experiment_1"
I4_EXP2 = LOOP / "iter_4/gen_art/gen_art_experiment_2"
I4_RES1 = LOOP / "iter_4/gen_art/gen_art_research_1"
I5 = LOOP / "iter_5/gen_art"

# logical name -> absolute path
SOURCES: dict[str, Path] = {
    # --- iteration-4 experiment 1 (the specificity / no-op test set) ---
    "i4e1_classification": I4_EXP1 / "results/classification.json",
    "i4e1_aggregates": I4_EXP1 / "results/aggregates.json",
    "i4e1_graded_truth": I4_EXP1 / "results/graded_truth.json",
    "i4e1_deviations": I4_EXP1 / "results/deviations.json",
    "i4e1_ams_validation": I4_EXP1 / "results/ams_validation.json",
    "i4e1_device_swap": I4_EXP1 / "results/device_swap.json",
    "i4e1_order_proof": I4_EXP1 / "results/order_proof.json",
    "i4e1_hygiene_check": I4_EXP1 / "results/hygiene_check.json",
    "i4e1_pairs_long": I4_EXP1 / "results/scores/pairs_long.json",
    "i4e1_kcurves_all": I4_EXP1 / "results/scores/kcurves_all.json",
    "i4e1_kcurves": I4_EXP1 / "results/scores/kcurves.json",
    "i4e1_text_baseline": I4_EXP1 / "results/text_baseline.json",
    "i4e1_prereg": I4_EXP1 / "results/prereg.json",
    "i4e1_prereg_amendments": I4_EXP1 / "results/prereg_amendments.json",
    "i4e1_variant_sanity": I4_EXP1 / "results/variant_sanity.json",
    "i4e1_method_out": I4_EXP1 / "method_out.json",
    "i4e1_ckpt_base": I4_EXP1 / "results/scores/ckpt_Qwen--Qwen3-4B-Base.json",
    "i4e1_ckpt_instruct": I4_EXP1 / "results/scores/ckpt_Qwen--Qwen3-4B.json",
    "i4e1_ckpt_saferl": I4_EXP1 / "results/scores/ckpt_Qwen--Qwen3-4B-SafeRL.json",
    "i4e1_ckpt_abliterated": I4_EXP1 / "results/scores/ckpt_mlabonne--Qwen3-4B-abliterated.json",
    "i4e1_ckpt_star": I4_EXP1 / "results/scores/ckpt_CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6.json",
    # --- iteration-4 experiment 2 (the causal depth x site grid) ---
    "i4e2_analysis": I4_EXP2 / "results/analysis.json",
    "i4e2_deviations": I4_EXP2 / "results/deviations.json",
    "i4e2_direction_cosines": I4_EXP2 / "results/direction_cosines.json",
    "i4e2_summary_tables": I4_EXP2 / "results/summary_tables.md",
    "i4e2_disk_readouts": I4_EXP2 / "results/disk_readouts.json",
    "i4e2_disk_readouts_abl": I4_EXP2 / "results/disk_readouts_abliterated.json",
    "i4e2_method_out": I4_EXP2 / "method_out.json",
    # --- iteration-3 (held-out confirmation panel) ---
    "i3e1_heldout_table": I3_EXP1 / "results/heldout_table.json",
    "i3e1_b7_diagnostic": I3_EXP1 / "results/b7_diagnostic.json",
    "i3e1_b7_null_dir": I3_EXP1 / "results/b7_null_direction_diagnostic.json",
    "i3e1_join_stub": I3_EXP1 / "results/join_stub.json",
    "i3e1_graded_truth": I3_EXP1 / "results/graded_truth.json",
    "i3e1_extra_analyses": I3_EXP1 / "results/extra_analyses.json",
    "i3e1_two_panel_table": I3_EXP1 / "results/two_panel_table.json",
    "i3e1_unit_checks": I3_EXP1 / "results/unit_checks.json",
    "i3eval1_eval_out": I3_EVAL1 / "eval_out.json",
    "i3eval1_tables": I3_EVAL1 / "results/tables.json",
    # --- iteration-4 research lane ---
    "i4r1_research_out": I4_RES1 / "research_out.json",
    "i4r1_research_verification": I4_RES1 / "research_verification.json",
    "i4r1_references_bib": I4_RES1 / "references_verified.bib",
    # --- iteration-2 dataset substrate ---
    "i2data_full": I2_DATA / "full_data_out.json",
    # --- iteration-4 prose (the audited claims live here) ---
    "i4_paper_draft": LOOP / "iter_4/gen_paper_text/gen_paper_text/paper_draft.tex",
    "i4_paper_review": LOOP / "iter_4/review_paper/review_paper/.terminal_claude_agent_struct_out.json",
    "i4e1_readme": I4_EXP1 / "README.md",
    "i4e2_readme": I4_EXP2 / "README.md",
    # --- iteration-5 siblings (D11 backstop join) ---
    "i5_exp1_dir": I5 / "gen_art_experiment_1",
    "i5_exp2_dir": I5 / "gen_art_experiment_2",
    "i5_res1_dir": I5 / "gen_art_research_1",
}

# directories recorded for provenance (not hashed)
SOURCE_DIRS: dict[str, Path] = {
    "i4e1_harvest": I4_EXP1 / "harvest",
    "i4e1_src": I4_EXP1 / "src",
    "i4e2_out_cells": I4_EXP2 / "out/cells",
    "i3e1_harvest": I3_EXP1 / "harvest",
}


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def build_manifest(hash_limit_mb: float = 64.0) -> dict[str, Any]:
    """Record absolute path, size, mtime and sha256 for every source."""
    entries: dict[str, Any] = {}
    for name, path in SOURCES.items():
        rec: dict[str, Any] = {"abs_path": str(path), "exists": path.exists()}
        if path.exists():
            st = path.stat()
            rec["size_bytes"] = st.st_size
            rec["mtime_utc"] = __import__("datetime").datetime.fromtimestamp(
                st.st_mtime, __import__("datetime").timezone.utc
            ).isoformat(timespec="seconds")
            rec["is_dir"] = path.is_dir()
            if path.is_file():
                if st.st_size <= hash_limit_mb * 1024 * 1024:
                    rec["sha256"] = _sha256(path)
                else:
                    rec["sha256"] = "SKIPPED_TOO_LARGE"
        else:
            rec["status"] = "SOURCE_ABSENT"
        entries[name] = rec
    for name, path in SOURCE_DIRS.items():
        rec = {"abs_path": str(path), "exists": path.exists(), "is_dir": True}
        if path.exists():
            children = sorted(p.name for p in path.iterdir())
            rec["n_children"] = len(children)
            rec["children_sample"] = children[:60]
        else:
            rec["status"] = "SOURCE_ABSENT"
        entries[name] = rec
    return entries


def load(name: str) -> Any:
    """Load a JSON source by logical name. Raises if the source is absent."""
    path = SOURCES[name]
    if not path.exists():
        raise FileNotFoundError(f"SOURCE_ABSENT: {name} -> {path}")
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def try_load(name: str) -> tuple[Any | None, str | None]:
    """Load a JSON source, returning (obj, None) or (None, reason)."""
    try:
        return load(name), None
    except FileNotFoundError as exc:
        return None, str(exc)
    except json.JSONDecodeError as exc:
        return None, f"JSON_DECODE_ERROR: {name}: {exc}"


def src_ref(name: str, key_chain: str) -> dict[str, str]:
    """Provenance stamp carried by EVERY emitted table row."""
    return {"source_file": str(SOURCES.get(name, Path(name))), "source_key": key_chain}
