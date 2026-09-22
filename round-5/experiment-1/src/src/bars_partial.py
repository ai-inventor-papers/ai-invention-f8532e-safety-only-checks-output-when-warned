#!/usr/bin/env python3
"""Compute bars on an array directory that lacks OPTIONAL-for-us but MANDATORY-for-the-loader files.

The held-out substrate saves A_prompt / A_dec / r_* / WU_* but not gamma.npy (nor A_ams / A_c11 /
vmin_*). reuse.ncands.Ckpt.load requires gamma.npy, so for those directories we build a shim
directory of symlinks plus gamma = ones(d), and mark every bar whose definition actually uses gamma
(BL1_truelogit family) as NaN, because a unit gamma is not that model's final-norm weight.
Bars that only need A_prompt / r_refusal / r_control (BL1_easy, BL1_hard, N1, N6, C7, C13, N11) are
unaffected and are computed exactly as on the screen panel.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
CACHE = WS / "cache/bars_shim"
GAMMA_DEPENDENT = ("BL1_truelogit", "BL1_truelogit_hard")


def shim_dir(arr_dir: Path, tag: str) -> tuple[Path, list[str]]:
    d = CACHE / tag
    d.mkdir(parents=True, exist_ok=True)
    synth = []
    for p in arr_dir.iterdir():
        if p.is_file():
            q = d / p.name
            if not q.exists():
                q.symlink_to(p)
    if not (arr_dir / "gamma.npy").exists():
        A = np.load(arr_dir / "A_prompt.npy", mmap_mode="r")
        np.save(d / "gamma.npy", np.ones(A.shape[2], dtype=np.float32))
        synth.append("gamma.npy=ones")
    return d, synth


def compute_bars_tolerant(arr_dir: Path, tag: str) -> dict:
    import bars  # noqa: PLC0415
    if (arr_dir / "gamma.npy").exists():
        return bars.compute_bars(arr_dir)
    d, synth = shim_dir(arr_dir, tag)
    out = bars.compute_bars(d)
    out["shimmed_arrays"] = synth
    for k in GAMMA_DEPENDENT:
        if k in out:
            out[k] = float("nan")
            out[f"{k}_note"] = "NOT COMPUTED: the substrate arrays carry no gamma (final-norm weight)"
    return out


if __name__ == "__main__":
    b = compute_bars_tolerant(Path(sys.argv[1]), sys.argv[2])
    print(json.dumps({k: v for k, v in b.items() if not isinstance(v, dict)}, indent=1, default=str)[:1500])
