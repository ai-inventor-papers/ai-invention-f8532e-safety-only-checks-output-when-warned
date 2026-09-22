#!/usr/bin/env python3
"""HOOK / PIPELINE CHECK: this artifact's F1__ref harvest (Qwen/Qwen3-0.6B, stock chat template) vs the iteration-2
harvest of the SAME checkpoint through the SAME copied kernel (src_i3/h2/harvest.p_harvest). Differences can only come
from library versions / thread count; reported, not hidden. Also checks the structural identities of the constructed arms:
wu arms' A_prompt == parent (bitwise), resave arms' arrays == parent, and the lesion's post-edit projection on r."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H2, HARVEST, RESULTS, jdump, jload, utc_now  # noqa: E402


def cmp(a: np.ndarray, b: np.ndarray) -> dict:
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    d = np.abs(a - b)
    rel = d.max() / max(float(np.abs(b).max()), 1e-12)
    return {"shape_a": list(a.shape), "shape_b": list(b.shape), "max_abs_diff": float(d.max()),
            "mean_abs_diff": float(d.mean()), "frac_bitwise_equal": float((a == b).mean()), "max_rel_to_max_abs": float(rel)}


def main() -> None:
    out = {"utc": utc_now(), "checks": {}}
    mine, old = HARVEST / "F1__ref", H2 / "harvest" / "Qwen--Qwen3-0.6B"
    if (mine / "A_prompt.npy").exists() and (old / "A_prompt.npy").exists():
        for f in ("A_prompt.npy", "r_refusal.npy", "r_control.npy", "norms.npy", "WU_ref.npy", "WU_ctl.npy", "gamma.npy"):
            if (mine / f).exists() and (old / f).exists():
                a, b = np.load(mine / f), np.load(old / f)
                out["checks"][f"F1__ref_vs_iter2_Qwen3-0.6B::{f}"] = cmp(a, b) if a.shape == b.shape else \
                    {"shape_mismatch": [list(a.shape), list(b.shape)]}
    for d in sorted(HARVEST.glob("*__wu*")):
        p = HARVEST / (d.name.split("__")[0] + "__ref")
        if (d / "A_prompt.npy").exists() and (p / "A_prompt.npy").exists():
            out["checks"][f"{d.name}::A_prompt_equals_parent"] = bool(np.array_equal(np.load(d / "A_prompt.npy"),
                                                                                     np.load(p / "A_prompt.npy")))
    for d in sorted(HARVEST.glob("*__resave")):
        p = HARVEST / (d.name.split("__")[0] + "__ref")
        if (d / "meta.json").exists():
            out["checks"][f"{d.name}::bitwise_check_8_stimuli"] = jload(d / "meta.json").get("bitwise_check_8_stimuli")
    for f in sorted(RESULTS.glob("lesion_fit_*.json")):
        fk = f.stem.split("_")[-1]
        san = jload(RESULTS / "variant_sanity.json") if (RESULTS / "variant_sanity.json").exists() else {}
        pre = np.array(jload(f)["pre_edit_mean_abs_proj_by_layer"])
        for v in ("a05", "a10"):
            post = (san.get(f"{fk}__{v}") or {}).get("post_edit_mean_abs_proj_by_layer")
            if post:
                ratio = np.array(post) / np.maximum(pre, 1e-12)
                out["checks"][f"{fk}__{v}::post_over_pre_projection_on_r"] = {
                    "max_ratio_layers_ge1": float(ratio.max()), "median_ratio": float(np.median(ratio)),
                    "pass_alpha1_rule(<1%)": bool(ratio.max() < 0.01) if v == "a10" else None}
    jdump(out, RESULTS / "hook_checks.json")
    for k, v in out["checks"].items():
        print(k, v)


if __name__ == "__main__":
    main()
