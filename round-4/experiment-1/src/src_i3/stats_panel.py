"""STEP 5b -- panel statistics: one row per (feature, outcome); NO ranking, NO winner field.

Per row: Spearman rho over panel checkpoints (random-init excluded, NaN never zero-filled), checkpoint
bootstrap 95% CI (B=10000, degenerate resamples with < 4 distinct values skipped and counted),
family-cluster bootstrap 95% CI, sign, declared expected sign, paired difference from BL1 with a paired
bootstrap CI on the same resamples, rank-based partial Spearman given BL1 (with its bootstrap CI),
minimum detectable |rho| (alpha .05 two-sided, power .8; Fisher z with the 1.06 Spearman variance
factor) and the exact permutation critical |rho| for this n, family-disjoint sensitivity row, and the
random-init value's position against the panel (flag 'prompt-driven' if inside the panel IQR).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm, rankdata, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))

B_BOOT = 10000


def _rho(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 4 or len(np.unique(x[ok])) < 2 or len(np.unique(y[ok])) < 2:
        return float("nan"), int(ok.sum())
    return float(spearmanr(x[ok], y[ok]).statistic), int(ok.sum())


def partial_spearman(x, y, z):
    x, y, z = (np.asarray(v, float) for v in (x, y, z))
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    if ok.sum() < 5:
        return float("nan")
    rx, ry, rz = rankdata(x[ok]), rankdata(y[ok]), rankdata(z[ok])
    Z = np.c_[np.ones(ok.sum()), rz]
    ex = rx - Z @ np.linalg.lstsq(Z, rx, rcond=None)[0]
    ey = ry - Z @ np.linalg.lstsq(Z, ry, rcond=None)[0]
    if ex.std() < 1e-12 or ey.std() < 1e-12:
        return float("nan")
    return float(np.corrcoef(ex, ey)[0, 1])


def mde_rho(n: int, alpha: float = 0.05, power: float = 0.8) -> float:
    if n <= 3:
        return float("nan")
    z = (norm.ppf(1 - alpha / 2) + norm.ppf(power)) * math.sqrt(1.06 / (n - 3))
    return float(math.tanh(z))


_CRIT: dict[int, float] = {}


def critical_rho(n: int, alpha: float = 0.05, n_perm: int = 200000, seed: int = 0) -> float:
    """Exact-by-simulation permutation critical |rho| (two-sided) for n untied ranks."""
    if n in _CRIT:
        return _CRIT[n]
    if n < 4:
        return float("nan")
    rng = np.random.default_rng(seed)
    r = np.arange(1, n + 1, dtype=float)
    P = np.argsort(rng.random((n_perm, n)), axis=1).astype(float) + 1
    d2 = ((P - r) ** 2).sum(1)
    rho = np.round(1 - 6 * d2 / (n * (n * n - 1)), 10)
    a = np.abs(rho)
    vals = np.unique(a)
    # conservative critical value: the smallest c with P(|rho| >= c) <= alpha under H0
    tail = np.array([(a >= v).mean() for v in vals])
    okv = vals[tail <= alpha]
    _CRIT[n] = float(okv.min()) if okv.size else float("nan")
    return _CRIT[n]


def _rank_rows(M):
    return rankdata(M, axis=1)


def _pearson_rows(A, B):
    A = A - A.mean(1, keepdims=True)
    B = B - B.mean(1, keepdims=True)
    den = np.sqrt((A * A).sum(1) * (B * B).sum(1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 1e-12, (A * B).sum(1) / den, np.nan)


def _partial_rows(RX, RY, RZ):
    def resid(R):
        zc = RZ - RZ.mean(1, keepdims=True)
        rc = R - R.mean(1, keepdims=True)
        beta = (zc * rc).sum(1, keepdims=True) / np.maximum((zc * zc).sum(1, keepdims=True), 1e-12)
        return rc - beta * zc
    return _pearson_rows(resid(RX), resid(RY))


def boot_rows(x, y, bl1, fams, B=B_BOOT, seed=0, B_family=2000):
    """Checkpoint bootstrap (vectorised, B draws) + family-cluster bootstrap (B_family draws)."""
    x, y, bl1 = (np.asarray(v, float) for v in (x, y, bl1))
    fams = np.asarray(fams)
    ok = np.isfinite(x) & np.isfinite(y) & np.isfinite(bl1)
    idx_all = np.flatnonzero(ok)
    n = idx_all.size
    rng = np.random.default_rng(seed)
    I = rng.choice(idx_all, size=(B, n), replace=True)
    X, Y, Z = x[I], y[I], bl1[I]
    def nuniq(M):
        Ms = np.sort(M, axis=1)
        return 1 + (np.diff(Ms, axis=1) != 0).sum(1)
    good = (nuniq(X) >= 4) & (nuniq(Y) >= 4) & (nuniq(Z) >= 4)
    RX, RY, RZ = _rank_rows(X[good]), _rank_rows(Y[good]), _rank_rows(Z[good])
    r_c = _pearson_rows(RX, RY)
    rb = _pearson_rows(RZ, RY)
    d_c = r_c - rb
    dabs_c = np.abs(r_c) - np.abs(rb)          # orientation-free: |rho(C)| - |rho(BL1)|
    p_c = _partial_rows(RX, RY, RZ)
    skipped = int((~good).sum())
    uf = np.unique(fams[idx_all])
    r_f, d_f = [], []
    sk_f = 0
    members = {f: idx_all[fams[idx_all] == f] for f in uf}
    for _ in range(B_family):
        pick = rng.choice(uf, len(uf), replace=True)
        i = np.concatenate([members[f] for f in pick])
        if len(np.unique(x[i])) < 4 or len(np.unique(y[i])) < 4 or len(np.unique(bl1[i])) < 4:
            sk_f += 1
            continue
        rx = np.corrcoef(rankdata(x[i]), rankdata(y[i]))[0, 1]
        rbb = np.corrcoef(rankdata(bl1[i]), rankdata(y[i]))[0, 1]
        r_f.append(rx)
        d_f.append(rx - rbb)

    def ci(v):
        v = np.asarray([t for t in np.asarray(v, float) if np.isfinite(t)])
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size >= 20 else [None, None]
    return {"ci95_ckpt": ci(r_c), "d_BL1_ci95_ckpt": ci(d_c), "dabs_BL1_ci95_ckpt": ci(dabs_c),
            "partial_ci95_ckpt": ci(p_c),
            "n_boot_ckpt": B, "n_boot_skipped_ckpt": skipped, "ci95_family": ci(r_f),
            "d_BL1_ci95_family": ci(d_f), "n_boot_family": B_family, "n_boot_skipped_family": sk_f,
            "n_families": int(len(uf))}


def table(features: dict[str, dict], outcomes: dict[str, dict[str, float]], families: dict[str, str],
          feature_names: list[str], outcome_names: list[str], readout_class: dict, expected: dict,
          randinit: dict | None, family_overlap: set[str], B=B_BOOT) -> list[dict]:
    ck = sorted(features)
    fams = [families[c] for c in ck]
    rows = []
    for on in outcome_names:
        yv = np.array([outcomes[c].get(on, np.nan) for c in ck], dtype=float)
        bl1 = np.array([features[c].get("BL1", np.nan) for c in ck], dtype=float)
        rho_bl1, _ = _rho(bl1, yv)
        for fn in feature_names:
            xv = np.array([_num(features[c].get(fn)) for c in ck], dtype=float)
            rho, n = _rho(xv, yv)
            n_undef = int((~np.isfinite(xv)).sum())
            row = {"feature": fn, "readout_class": readout_class.get(fn.split("_")[0], readout_class.get(fn, "activation")),
                   "outcome": on, "n": n, "n_undefined": n_undef, "rho": rho,
                   "sign": (0 if not np.isfinite(rho) else int(np.sign(rho))),
                   "expected_sign": expected.get(fn.split("_")[0], expected.get(fn, 0)),
                   "rho_BL1_same_rows": rho_bl1, "d_BL1": (rho - rho_bl1) if np.isfinite(rho) and np.isfinite(rho_bl1) else float("nan"),
                   "dabs_BL1": (abs(rho) - abs(rho_bl1)) if np.isfinite(rho) and np.isfinite(rho_bl1) else float("nan"),
                   "partial_rho_given_BL1": partial_spearman(xv, yv, bl1) if fn != "BL1" else float("nan"),
                   "mde_rho_power80": mde_rho(n), "critical_rho_alpha05": critical_rho(n)}
            if np.isfinite(rho) and fn != "BL1":
                row.update(boot_rows(xv, yv, bl1, fams, B=B, seed=17))
            elif np.isfinite(rho):
                b = boot_rows(xv, yv, bl1, fams, B=B, seed=17)
                row.update({k: v for k, v in b.items() if not k.startswith("d_BL1") and not k.startswith("partial")})
            es = row["expected_sign"]
            row["sign_matches_expected"] = (None if (es == 0 or not np.isfinite(rho)) else bool(np.sign(rho) == es))
            keep = [i for i, c in enumerate(ck) if c not in family_overlap]
            row["family_disjoint_rho"] = _rho(xv[keep], yv[keep])[0] if len(keep) < len(ck) else "identical (no family_overlap members)"
            if randinit is not None:
                rv = _num(randinit.get(fn))
                fin = xv[np.isfinite(xv)]
                if np.isfinite(rv) and fin.size:
                    q1, q3 = np.percentile(fin, [25, 75])
                    row["random_init_value"] = rv
                    row["panel_min_max"] = [float(fin.min()), float(fin.max())]
                    row["panel_iqr"] = [float(q1), float(q3)]
                    row["random_init_inside_iqr_prompt_driven_flag"] = bool(q1 <= rv <= q3)
                    row["random_init_position"] = ("below_min" if rv < fin.min() else "above_max" if rv > fin.max()
                                                   else "inside_IQR" if q1 <= rv <= q3 else "inside_range")
                else:
                    row["random_init_value"] = None
            rows.append(row)
    return rows


def _num(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")
