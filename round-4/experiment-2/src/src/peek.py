#!/usr/bin/env python3
"""Quick progress table of the judged grid (rates per arm per cell) while the run is going.

Usage: .venv/bin/python src/peek.py [--models instruct,saferl] [--hook 6e406f7f]
Prints refused_harm / harmful_compliance_harm / over_refusal_hb rates for arms 0 / F / R_F(mean) / N6 / R_N6(mean)
and the paired F-R and N6-R differences with a naive bootstrap CI; this is a monitoring aid, the registered
statistics are in src/analyze.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parents[1]


def load(m: str, name: str, hook: str):
    p = WS / "out/cells" / m / f"{name}__{hook}.npz"
    if not p.exists():
        return None
    return dict(np.load(p)), json.loads(p.with_suffix(".json").read_text())


def per_item(arrs, meta, col, kind, arm_set, band=None):
    out: dict[str, list[float]] = {}
    for i, r in enumerate(meta["rows"]):
        if meta["kinds"][i] != kind or r["arm"] not in arm_set:
            continue
        v = arrs[col][i]
        if np.isfinite(v):
            out.setdefault(r["item_id"], []).append(float(v))
    return {k: float(np.mean(v)) for k, v in out.items()}


def boot(d: np.ndarray, B: int = 2000, seed: int = 0) -> tuple[float, float]:
    if len(d) == 0:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    bs = d[rng.integers(0, len(d), (B, len(d)))].mean(1)
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="instruct,saferl")
    ap.add_argument("--hook", default="6e406f7f")
    a = ap.parse_args()
    for m in a.models.split(","):
        print(f"=== {m}")
        for site in ("P", "Dprime", "E"):
            rfo = {"P": ("RF",), "Dprime": ("RFo",), "E": ("RFo",)}[site]
            rn6 = {"P": ("RN6",), "Dprime": ("RN6o",), "E": ("RN6o",)}[site]
            for b in [f"B{k}" for k in range(1, 7)]:
                c = load(m, f"gen{site}_{b}", a.hook)
                if c is None:
                    continue
                arrs, meta = c
                line = f"{site:6s} {b}"
                for col, kind in (("refused", "harm"), ("harmful_compliance", "harm"), ("over_refusal", "hb")):
                    z = per_item(arrs, meta, col, kind, {"0"})
                    f = per_item(arrs, meta, col, kind, {"F"})
                    r = per_item(arrs, meta, col, kind, set(rfo))
                    n6 = per_item(arrs, meta, col, kind, {"N6"})
                    rn = per_item(arrs, meta, col, kind, set(rn6))
                    ids = sorted(set(z) & set(f) & set(r))
                    dfr = np.array([f[i] - r[i] for i in ids])
                    ids6 = sorted(set(n6) & set(rn))
                    dnr = np.array([n6[i] - rn[i] for i in ids6])
                    lo, hi = boot(dfr)
                    lo6, hi6 = boot(dnr)
                    tag = {"refused": "REF", "harmful_compliance": "HC", "over_refusal": "OR"}[col]
                    line += (f" | {tag} 0={np.mean([z[i] for i in ids]):.2f} F={np.mean([f[i] for i in ids]):.2f} "
                             f"R={np.mean([r[i] for i in ids]):.2f} F-R={dfr.mean():+.2f}[{lo:+.2f},{hi:+.2f}] "
                             f"N6-R={dnr.mean():+.2f}[{lo6:+.2f},{hi6:+.2f}]")
                print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
