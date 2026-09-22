#!/usr/bin/env python3
"""Statistics primitives for the iteration-5 wide screen.

Everything here is convention-free: it takes plain numpy arrays and returns
plain floats/dicts. Unit-tested against scipy in src/unit_tests.py (T5-T7).

Contents
--------
spearman                 rank correlation (ties -> average ranks), NaN-safe pairwise deletion
partial_spearman         rank-partial correlation of x,y given one or more controls
checkpoint_bootstrap     paired checkpoint-level bootstrap CI for any statistic
paired_margin_ci         CI on |rho(cand,y)| - |rho(bar,y)| (paired by checkpoint)
mcnemar_exact            exact two-sided McNemar from Binomial(b+c, 0.5)
erank                    effective rank: entropy and participation-ratio variants
rho_mde                  minimum detectable Spearman rho at alpha=.05, power=.80
winsorise_high           panel-95th-percentile censoring used by the G2/W3/A3 guards
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np

# --------------------------------------------------------------------------- #
# ranks                                                                        #
# --------------------------------------------------------------------------- #


def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average-rank transform (identical to scipy.stats.rankdata method='average')."""
    a = np.asarray(a, dtype=float)
    n = a.size
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    sa = a[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sa[j + 1] == sa[i]:
            j += 1
        avg = 0.5 * (i + j) + 1.0
        ranks[order[i : j + 1]] = avg
        i = j + 1
    return ranks


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 3:
        return float("nan")
    xc = x - x.mean()
    yc = y - y.mean()
    den = math.sqrt(float(xc @ xc) * float(yc @ yc))
    if den <= 0.0:
        return float("nan")
    return float((xc @ yc) / den)


def _finite_pair(x: Sequence[float], y: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    return x[m], y[m]


def spearman(x: Sequence[float], y: Sequence[float]) -> dict:
    """Spearman rho with pairwise deletion. Returns {rho, n}."""
    xf, yf = _finite_pair(x, y)
    n = int(xf.size)
    if n < 3:
        return {"rho": float("nan"), "n": n}
    return {"rho": _pearson(_rankdata(xf), _rankdata(yf)), "n": n}


def partial_spearman(
    x: Sequence[float], y: Sequence[float], controls: Sequence[Sequence[float]]
) -> dict:
    """Rank-partial correlation of x and y given `controls` (a list of 1-D sequences).

    Ranks everything, then regresses out the control ranks by OLS (with intercept)
    and correlates the residuals. Pairwise deletion over all supplied columns.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ctrl = [np.asarray(c, dtype=float) for c in controls]
    m = np.isfinite(x) & np.isfinite(y)
    for c in ctrl:
        m &= np.isfinite(c)
    n = int(m.sum())
    k = len(ctrl)
    if n < k + 4:
        return {"rho": float("nan"), "n": n, "n_controls": k}
    rx = _rankdata(x[m])
    ry = _rankdata(y[m])
    if k == 0:
        return {"rho": _pearson(rx, ry), "n": n, "n_controls": 0}
    design = np.column_stack([np.ones(n)] + [_rankdata(c[m]) for c in ctrl])
    beta_x, *_ = np.linalg.lstsq(design, rx, rcond=None)
    beta_y, *_ = np.linalg.lstsq(design, ry, rcond=None)
    ex = rx - design @ beta_x
    ey = ry - design @ beta_y
    return {"rho": _pearson(ex, ey), "n": n, "n_controls": k}


# --------------------------------------------------------------------------- #
# resampling                                                                   #
# --------------------------------------------------------------------------- #


def checkpoint_bootstrap(
    stat_fn: Callable[[np.ndarray], float],
    n_items: int,
    *,
    n_boot: int = 2000,
    seed: int = 20260921,
    alpha: float = 0.05,
) -> dict:
    """Percentile bootstrap over CHECKPOINT indices.

    `stat_fn` receives an index array (with replacement) and returns a scalar.
    Every statistic in this artifact is computed on the SAME resampled index
    vector, which is what makes the margins paired.
    """
    rng = np.random.default_rng(seed)
    point = float(stat_fn(np.arange(n_items)))
    draws = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, n_items, size=n_items)
        try:
            draws[b] = float(stat_fn(idx))
        except (ValueError, ZeroDivisionError, np.linalg.LinAlgError):
            draws[b] = np.nan
    good = draws[np.isfinite(draws)]
    if good.size < 50:
        return {
            "point": point,
            "lo": float("nan"),
            "hi": float("nan"),
            "n_boot_ok": int(good.size),
            "excludes_zero": False,
        }
    lo = float(np.quantile(good, alpha / 2.0))
    hi = float(np.quantile(good, 1.0 - alpha / 2.0))
    return {
        "point": point,
        "lo": lo,
        "hi": hi,
        "n_boot_ok": int(good.size),
        "excludes_zero": bool((lo > 0.0) or (hi < 0.0)),
    }


def paired_margin_ci(
    cand: Sequence[float],
    bar: Sequence[float],
    outcome: Sequence[float],
    *,
    n_boot: int = 2000,
    seed: int = 20260921,
) -> dict:
    """Paired checkpoint-bootstrap CI on |rho(cand,outcome)| - |rho(bar,outcome)|."""
    cand = np.asarray(cand, dtype=float)
    bar = np.asarray(bar, dtype=float)
    outcome = np.asarray(outcome, dtype=float)
    m = np.isfinite(cand) & np.isfinite(bar) & np.isfinite(outcome)
    c, b_, o = cand[m], bar[m], outcome[m]
    n = int(c.size)
    if n < 5:
        return {"point": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": n,
                "excludes_zero": False, "rho_cand": float("nan"), "rho_bar": float("nan")}

    def _stat(idx: np.ndarray) -> float:
        rc = spearman(c[idx], o[idx])["rho"]
        rb = spearman(b_[idx], o[idx])["rho"]
        if not (np.isfinite(rc) and np.isfinite(rb)):
            return float("nan")
        return abs(rc) - abs(rb)

    out = checkpoint_bootstrap(_stat, n, n_boot=n_boot, seed=seed)
    out["n"] = n
    out["rho_cand"] = spearman(c, o)["rho"]
    out["rho_bar"] = spearman(b_, o)["rho"]
    return out


# --------------------------------------------------------------------------- #
# exact McNemar                                                                #
# --------------------------------------------------------------------------- #


def _binom_pmf(k: int, n: int, p: float = 0.5) -> float:
    return math.comb(n, k) * (p**k) * ((1.0 - p) ** (n - k))


def mcnemar_exact(b: int, c: int) -> dict:
    """Exact two-sided McNemar test from Binomial(b + c, 0.5).

    b = discordant pairs where method-1 flags and method-2 does not,
    c = the reverse. Two-sided p is the sum of all binomial probabilities
    no larger than the observed one (the standard exact convention; for
    p=0.5 this equals 2*min(tail) capped at 1).
    """
    n = int(b) + int(c)
    if n == 0:
        return {"b": int(b), "c": int(c), "n_discordant": 0, "p_two_sided": 1.0}
    obs = _binom_pmf(int(b), n)
    p = sum(_binom_pmf(k, n) for k in range(n + 1) if _binom_pmf(k, n) <= obs + 1e-12)
    return {"b": int(b), "c": int(c), "n_discordant": n, "p_two_sided": float(min(1.0, p))}


# --------------------------------------------------------------------------- #
# effective rank                                                               #
# --------------------------------------------------------------------------- #


def erank(matrix: np.ndarray) -> dict:
    """Effective rank of a (candidates x checkpoints) matrix.

    Returns both the entropy variant exp(-sum p log p) and the participation
    ratio (sum s^2)^2 / sum s^4, plus the singular-value spectrum and the
    leading right/left singular vectors.
    """
    m = np.asarray(matrix, dtype=float)
    if m.ndim != 2 or min(m.shape) < 2:
        return {"erank_entropy": float("nan"), "erank_participation": float("nan"),
                "singular_values": [], "explained": [], "leading_left": []}
    u, s, _vt = np.linalg.svd(m, full_matrices=False)
    s2 = s**2
    tot = float(s2.sum())
    if tot <= 0.0:
        return {"erank_entropy": float("nan"), "erank_participation": float("nan"),
                "singular_values": s.tolist(), "explained": [], "leading_left": []}
    p = s2 / tot
    nz = p[p > 1e-15]
    ent = float(np.exp(-float(np.sum(nz * np.log(nz)))))
    part = float((tot**2) / float(np.sum(s2**2)))
    return {
        "erank_entropy": ent,
        "erank_participation": part,
        "singular_values": s.tolist(),
        "explained": p.tolist(),
        "leading_left": u[:, 0].tolist(),
    }


# --------------------------------------------------------------------------- #
# power                                                                        #
# --------------------------------------------------------------------------- #


def rho_mde(n: int) -> float:
    """Minimum detectable Spearman rho, two-sided alpha=0.05, power 0.80.

    rho_MDE = tanh(2.80 / sqrt(n - 3))   (Fisher-z, z_{.975}+z_{.80} = 2.80)
    """
    if n is None or n <= 3:
        return float("nan")
    return float(math.tanh(2.80 / math.sqrt(n - 3.0)))


def mde_table(ns: Sequence[int] = (8, 10, 12, 15, 20, 25, 30, 40, 50)) -> dict:
    return {str(int(n)): rho_mde(int(n)) for n in ns}


# --------------------------------------------------------------------------- #
# censoring guard                                                              #
# --------------------------------------------------------------------------- #


def winsorise_high(values: Sequence[float], censored: Sequence[bool]) -> np.ndarray:
    """Replace CENSORED_HIGH cells with the panel's 95th percentile of the
    uncensored finite values. Returns a new array; never mutates the input."""
    v = np.asarray(values, dtype=float).copy()
    cen = np.asarray(censored, dtype=bool)
    ok = np.isfinite(v) & (~cen)
    if ok.sum() >= 3:
        cap = float(np.quantile(v[ok], 0.95))
    elif ok.sum() > 0:
        cap = float(np.nanmax(v[ok]))
    else:
        return v
    v[cen] = cap
    return v
