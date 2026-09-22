"""Fidelity check: compare the released `ams scan` CLI (WS/.venv_ams) against our in-process
reimplementation (ams_reimpl.ams_forward + ams_sigma_from_acts, run under WS/.venv) on
Qwen/Qwen3-0.6B -- a small cached model that is NOT a panel checkpoint. Writes
WS/results/ams_fidelity_check.json with both outputs side by side, per-concept absolute
differences, and CPU elapsed times for both paths.

Run with: WS/.venv/bin/python src/ams_fidelity_check.py
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loguru import logger

from common import RESULTS, WS, jdump, setup_logging  # noqa: E402
from ams_reimpl import ams_sigma_from_acts, ams_forward  # noqa: E402
from ams_run import run_ams_cli  # noqa: E402

MODE = "full"  # exercise all 4 AMS_PAIRS concepts (CLI default `standard` only covers 3)
BATCH_SIZE = 8


def find_qwen3_06b_snapshot() -> Path:
    hf_home = Path(os.environ.get("HF_HOME", str(WS / "hf_cache")))
    hub_dir = hf_home / "hub" / "models--Qwen--Qwen3-0.6B"
    snaps_dir = hub_dir / "snapshots"
    if not snaps_dir.exists():
        raise FileNotFoundError(f"No snapshots dir at {snaps_dir} (HF_HOME={hf_home})")
    snaps = sorted(p for p in snaps_dir.iterdir() if p.is_dir())
    if not snaps:
        raise FileNotFoundError(f"No snapshot dirs under {snaps_dir}")
    return snaps[0]


def main() -> None:
    setup_logging("ams_fidelity_check")
    torch.set_num_threads(1)

    snap = find_qwen3_06b_snapshot()
    logger.info(f"Qwen3-0.6B snapshot: {snap}")

    # 1) Released CLI, full mode (all 4 concepts), cpu, json.
    logger.info("Running released `ams scan` CLI (.venv_ams) ...")
    # NOTE: this host is heavily shared (load average frequently 80-90+ from unrelated concurrent
    # jobs), so a `full`-mode (4-concept) CPU scan can take much longer than on a quiet box; use a
    # generous timeout here even though ams_run.run_ams_cli's own CLI default is 600s.
    cli_result = run_ams_cli(snap, mode=MODE, batch_size=BATCH_SIZE, device="cpu", timeout=1800)
    if not cli_result.get("ok"):
        logger.error(f"CLI run failed: {cli_result.get('error')}")

    # 2) Our reimplementation, loaded + run under OUR venv (.venv), same dtype AMS uses on cpu
    #    (float32 -- ams/extractor.py:434-437 forces this even though the CLI default --dtype is
    #    float16).
    from transformers import AutoModelForCausalLM, AutoTokenizer

    logger.info("Loading model+tokenizer for reimplementation ...")
    tok = AutoTokenizer.from_pretrained(str(snap))
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    t_load0 = time.time()
    model = AutoModelForCausalLM.from_pretrained(str(snap), torch_dtype=torch.float32, device_map="cpu")
    model = model.to("cpu")
    model.eval()
    load_s = time.time() - t_load0

    logger.info("Running ams_forward ...")
    t0 = time.time()
    store = ams_forward(model, tok, batch_size=BATCH_SIZE)
    forward_s = time.time() - t0

    logger.info("Running ams_sigma_from_acts ...")
    t1 = time.time()
    reimpl_result = ams_sigma_from_acts(store, mode=MODE)
    score_s = time.time() - t1

    # 3) Compare
    diffs = {}
    cli_concepts = cli_result.get("sigma_per_concept", {}) if cli_result.get("ok") else {}
    for name, r in reimpl_result["concept_results"].items():
        cli_r = cli_concepts.get(name, {})
        cli_sep = cli_r.get("separation")
        re_sep = r["separation"]
        diffs[name] = {
            "cli_separation": cli_sep,
            "reimpl_separation": re_sep,
            "abs_diff": None if cli_sep is None else abs(cli_sep - re_sep),
            "cli_optimal_layer": cli_r.get("optimal_layer"),
            "reimpl_optimal_layer": r["optimal_layer"],
            "cli_safety_level": cli_r.get("safety_level"),
            "reimpl_safety_level": r["safety_level"],
            "cli_passed": cli_r.get("passed"),
            "reimpl_passed": r["passed"],
        }

    max_abs_diff = max((d["abs_diff"] for d in diffs.values() if d["abs_diff"] is not None), default=None)

    out = {
        "model": "Qwen/Qwen3-0.6B",
        "snapshot_dir": str(snap),
        "mode": MODE,
        "batch_size": BATCH_SIZE,
        "cli": cli_result,
        "reimpl": {
            "concept_results": reimpl_result["concept_results"],
            "overall_level": reimpl_result["overall_level"],
            "overall_safe": reimpl_result["overall_safe"],
            "n_layers": store["n_layers"],
            "hidden_size": store["hidden_size"],
            "layers_used": store["layers_used"],
            "render_example": store["render_example"],
        },
        "diffs": diffs,
        "max_abs_diff_sigma": max_abs_diff,
        "timings_s": {
            "cli_elapsed_s": cli_result.get("elapsed_s"),
            "cli_scan_time_reported_by_ams": cli_result.get("scan_time_reported_by_ams"),
            "reimpl_model_load_s": load_s,
            "reimpl_forward_s": forward_s,
            "reimpl_score_s": score_s,
            "reimpl_total_s": load_s + forward_s + score_s,
        },
        "dtype_used": {
            "cli": "float32 (cpu override, ams/extractor.py:434-437, despite --dtype default float16)",
            "reimpl": "float32 (matched deliberately)",
        },
        "overall_level_match": cli_result.get("overall_level") == reimpl_result["overall_level"],
    }
    out_path = RESULTS / "ams_fidelity_check.json"
    jdump(out, out_path)
    logger.info(f"Wrote {out_path}")
    for name, d in diffs.items():
        logger.info(
            f"{name}: cli={d['cli_separation']} reimpl={d['reimpl_separation']:.4f} "
            f"|diff|={d['abs_diff']}"
        )
    logger.info(
        f"overall: cli={cli_result.get('overall_level')} reimpl={reimpl_result['overall_level']} "
        f"match={out['overall_level_match']}"
    )
    logger.info(
        f"timings: cli={cli_result.get('elapsed_s'):.1f}s reimpl_total={out['timings_s']['reimpl_total_s']:.1f}s "
        f"(load={load_s:.1f}s forward={forward_s:.1f}s score={score_s:.2f}s)"
    )


if __name__ == "__main__":
    main()
