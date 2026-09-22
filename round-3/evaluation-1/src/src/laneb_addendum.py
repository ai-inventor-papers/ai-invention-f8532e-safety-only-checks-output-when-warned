#!/usr/bin/env python3
"""Two small additions requested after the main laneb.py run:

(A) exact reproduction of iter-2 M1's restricted-budget AUROC at k=16
    (band-pooled LATE features, REQUEST class, alpha=0.00, repeats=200,
    seed=20260921, EXACTLY reference m1_recognition.restricted_budget_auroc).
(B) a flat 'ledger_values' dict inserted into results/laneb_accum.json.

Does NOT redo the main grid; reads/reuses what laneb.py already wrote and
recomputes only the k=16 budget curve (cheap, ~200 repeats x4 lineages).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import laneb as L  # noqa: E402

RESULTS = L.RESULTS
REPEATS = 200
SEED = 20260921
K = 16
QUOTED = {"L1": 0.528, "L4": 0.540, "L2": 0.679, "L3": 0.698}


def restricted_budget_auroc(x: np.ndarray, y: np.ndarray, k: int, *,
                             repeats: int = REPEATS, seed: int = SEED) -> dict:
    """Verbatim port of iter-2 evalkit/m1_recognition.py:restricted_budget_auroc."""
    rng = np.random.default_rng(seed + k)
    pos_idx = np.flatnonzero(y == 1)
    neg_idx = np.flatnonzero(y == 0)
    half = k // 2
    if min(pos_idx.size, neg_idx.size) <= half:
        return {"k": k, "mean": float("nan"), "p5": float("nan"), "p95": float("nan"),
                "n_repeats": 0, "note": f"k={k} exceeds the smaller class"}
    vals = np.empty(repeats, dtype=float)
    for r in range(repeats):
        tr = np.concatenate([rng.choice(pos_idx, half, replace=False),
                              rng.choice(neg_idx, half, replace=False)])
        mask = np.zeros(y.size, dtype=bool)
        mask[tr] = True
        try:
            sc, clf = L._fit_logistic(x[mask], y[mask])
            s = L._apply("logistic", (sc, clf), x[~mask])
        except ValueError:
            vals[r] = np.nan
            continue
        yy = y[~mask]
        vals[r] = L.auroc_scalar(s[yy == 1], s[yy == 0])
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"k": k, "mean": float("nan"), "p5": float("nan"), "p95": float("nan"),
                "n_repeats": 0, "note": "all repeats degenerate"}
    return {"k": k, "mean": float(vals.mean()), "p5": float(np.percentile(vals, 5)),
            "p95": float(np.percentile(vals, 95)),
            "sd": float(vals.std(ddof=1)) if vals.size > 1 else 0.0,
            "n_repeats": int(vals.size), "note": ""}


def task_A_k16() -> dict:
    logger.info("=== ADDENDUM A: k=16 restricted-budget AUROC reproduction ===")
    out = {}
    for lineage in L.LINEAGES:
        sub = L.substrate(lineage)
        X = L.get_band(lineage, "0.00", "item", "LATE")[sub.rows]
        y = sub.y["REQUEST"]
        res = restricted_budget_auroc(X, y, K)
        out[lineage] = {**res, "quoted": QUOTED[lineage],
                        "abs_delta_vs_quoted": (abs(res["mean"] - QUOTED[lineage])
                                                 if np.isfinite(res["mean"]) else None)}
        logger.info("{}: mean={:.4f} [{:.4f},{:.4f}] quoted={}", lineage,
                    res["mean"], res["p5"], res["p95"], QUOTED[lineage])
    out["_definition"] = ("verbatim port of iter-2 evalkit/m1_recognition.py "
                           "restricted_budget_auroc(x, y, k=16, repeats=200, "
                           "seed=20260921) on the alpha=0.00 band-pooled (layers "
                           "13-21 mean) LATE window, REQUEST class (y=request=="
                           "'harmful'), same 768-row substrate as the main M1(a) "
                           "probe (PREREG['M1_restricted_budgets_k']=[16,32,64], "
                           "PREREG['M1_restricted_budget_repeats']=200).")
    return out


def task_B_ledger() -> dict:
    logger.info("=== ADDENDUM B: ledger_values into laneb_accum.json ===")
    accum_path = RESULTS / "laneb_accum.json"
    accum = json.loads(accum_path.read_text())
    ledger: dict = {}
    for lineage in L.LINEAGES:
        lin = accum[lineage]
        rl = lin["r_ablit_layer"]
        fa = lin["by_group_alpha"][f"fit_ablit|lastp|0.00"]
        per_layer = {row["layer"]: row for row in fa["per_layer"]}
        insample_d = per_layer[rl]["cohend_own_axis"]
        m = L.meta_json(lineage)
        meta_sep = m["r_ablit_sep"][str(rl)]
        u138 = lin["u_138x_recompute"]
        ratio_fixed = u138["fit_ablit"]["ratio_max_over_min_abs_gap"]
        own_ds = np.array([per_layer[l]["cohend_own_axis"] for l in fa["layers"]])
        own_axis_ratio = float(np.max(np.abs(own_ds)) / abs(own_ds[0])) if own_ds[0] else float("nan")
        cos_fit = lin["post_lesion_cosine"]["fit_ablit_lastp_r_ablit_layer_value"]
        cos_l13 = lin["post_lesion_cosine"]["fit_ablit_lastp_by_layer"].get("13")
        ledger[f"insample_d_fit_ablit_at_rablit_layer_{lineage}"] = insample_d
        ledger[f"rablit_layer_{lineage}"] = rl
        ledger[f"meta_r_ablit_sep_at_rablit_layer_{lineage}"] = meta_sep
        ledger[f"u_signal_growth_ratio_fixed_{lineage}"] = ratio_fixed
        ledger[f"own_axis_ratio_{lineage}"] = own_axis_ratio
        ledger[f"cos_a0_a1_fitting_layer_{lineage}"] = cos_fit
        ledger[f"cos_a0_a1_L13_{lineage}"] = cos_l13
        logger.info("{}: insample_d={:.4f} meta_sep={:.4f} ratio_fixed={:.2f} "
                    "own_axis_ratio={:.2f} cos_fit={:.5f} cos_L13={:.4f}",
                    lineage, insample_d, meta_sep, ratio_fixed, own_axis_ratio,
                    cos_fit, cos_l13)
    accum["ledger_values"] = ledger
    accum_path.write_text(json.dumps(L.jsafe(accum), indent=2))
    logger.info("rewrote {} with top-level ledger_values ({} bytes)",
                accum_path, accum_path.stat().st_size)
    return ledger


def main() -> None:
    k16 = task_A_k16()
    (RESULTS / "laneb_k16_repro.json").write_text(json.dumps(L.jsafe(k16), indent=2))
    logger.info("wrote {}", RESULTS / "laneb_k16_repro.json")
    task_B_ledger()


if __name__ == "__main__":
    main()
