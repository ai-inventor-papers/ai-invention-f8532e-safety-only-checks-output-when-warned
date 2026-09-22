#!/usr/bin/env python3
"""Reported sensitivity analysis (NOT a selection input): lineage-CLUSTER bootstrap.

The screen panel's 48 rows are not 48 independent models: they are 3 in-house families (one parent
plus 11-12 near-duplicate arms each) and 4 further Hub lineages, i.e. SEVEN independent lineages.
The registered pre-screen uses a checkpoint bootstrap (prereg f_selection_rule_verbatim), which
treats arms of one family as independent. This script recomputes the same |Spearman| vs BL1_easy
with a bootstrap over LINEAGES (resample lineages with replacement, keep every row of a drawn
lineage), and reports the effective sample size, so no reader mistakes n=48 for 48 independent
observations. Registered decisions are untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import utc_now  # noqa: E402
from statlib import spearman  # noqa: E402

RES = WS / "results"
B = 2000
SEED = 20260922

LINEAGE = {  # tag prefix / exact tag -> lineage id (parent + its edited children)
    "F1__": "L_qwen3_0.6b", "F2__": "L_llama3.2_1b", "F3__": "L_falcon3_1b",
    "HG__huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2": "L_qwen3_0.6b",
    "HG__mylesgoose--Llama-3.2-1B-Instruct-abliterated2": "L_llama3.2_1b",
    "HG__tiiuae--Falcon3-1B-Base": "L_falcon3_1b",
    "HG__Qwen--Qwen3-1.7B": "L_qwen3_1.7b",
    "HG__huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2": "L_qwen3_1.7b",
    "HG__Qwen--Qwen2.5-1.5B-Instruct": "L_qwen2.5_1.5b",
    "HG__Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3": "L_qwen2.5_1.5b",
    "HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct": "L_vikhr_llama1b",
    "HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct-abliterated": "L_vikhr_llama1b",
    "HG__amd--AMD-OLMo-1B": "L_amd_olmo", "HG__amd--AMD-OLMo-1B-SFT": "L_amd_olmo",
    "HG__amd--AMD-OLMo-1B-SFT-DPO": "L_amd_olmo",
}


def lineage_of(tag: str) -> str:
    if tag in LINEAGE:
        return LINEAGE[tag]
    for k, v in LINEAGE.items():
        if k.endswith("__") and tag.startswith(k):
            return v
    return f"L_unassigned:{tag}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=RES)
    args = ap.parse_args()
    st = json.loads((args.results_dir / "screen_table.json").read_text())
    panel = st["panel"]
    cand_vals: dict[str, dict[str, float]] = {}
    for r in st["rows"]:
        if r["tag"] in panel and isinstance(r.get("value"), (int, float)):
            cand_vals.setdefault(r["candidate"], {})[r["tag"]] = float(r["value"])
    bl1 = {b["tag"]: b["value"] for b in st["bars"]
           if b.get("bar") == "BL1_easy" and isinstance(b.get("value"), (int, float))}
    lin = {t: lineage_of(t) for t in panel}
    groups: dict[str, list[str]] = {}
    for t, L in lin.items():
        groups.setdefault(L, []).append(t)
    rng = np.random.default_rng(SEED)
    keys = sorted(groups)
    out = {"utc": utc_now(), "B": B, "seed": SEED, "n_rows": len(panel), "n_lineages": len(keys),
           "lineages": {k: sorted(v) for k, v in groups.items()},
           "note": ("registered decisions use the prereg's checkpoint bootstrap; this lineage bootstrap is a "
                    "REPORTED sensitivity: with 7 lineages (3 of them carrying 12-14 near-duplicate arms) the "
                    "effective sample size of the screen panel is ~7, not 48"),
           "candidates": {}}
    for cand, vals in sorted(cand_vals.items()):
        common = [t for t in panel if t in vals and t in bl1]
        if len(common) < 6:
            out["candidates"][cand] = {"status": "TOO_FEW"}
            continue
        rho = spearman([vals[t] for t in common], [bl1[t] for t in common])["rho"]
        draws = []
        for _ in range(B):
            pick = rng.integers(0, len(keys), len(keys))
            tags = [t for i in pick for t in groups[keys[i]] if t in vals and t in bl1]
            if len(set(tags)) < 6:
                continue
            r = spearman([vals[t] for t in tags], [bl1[t] for t in tags])["rho"]
            if r is not None and np.isfinite(r):
                draws.append(r)
        d = np.array(draws, dtype=float)
        out["candidates"][cand] = {
            "rho_point": rho, "n_rows_used": len(common),
            "cluster_ci95": [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))] if d.size > 50 else None,
            "frac_draws_abs_ge_0.5": float(np.mean(np.abs(d) >= 0.5)) if d.size else None,
            "n_boot_ok": int(d.size),
        }
    (args.results_dir / "cluster_sensitivity.json").write_text(json.dumps(out, indent=1))
    for c, v in out["candidates"].items():
        print(c, v.get("rho_point"), v.get("cluster_ci95"), v.get("frac_draws_abs_ge_0.5"))


if __name__ == "__main__":
    main()
