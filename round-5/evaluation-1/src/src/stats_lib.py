"""Statistical primitives for the iteration-5 re-derivation audit.

Every routine here is deterministic given the prereg seed (20260921). Nothing
reads prose: callers pass numbers pulled from source JSON.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Sequence

import numpy as np
from scipy import stats

SEED = 20260921
B_BOOT = 2000
N_PERM = 20000


def rng(offset: int = 0) -> np.random.Generator:
    return np.random.default_rng(SEED + offset)


# --------------------------------------------------------------------------- #
# Exact McNemar on paired false-alarm counts
# --------------------------------------------------------------------------- #
def mcnemar_exact(a_flags: Sequence[int], b_flags: Sequence[int]) -> dict[str, Any]:
    """Exact McNemar for paired binary outcomes (1 = false alarm).

    b = count(a fires, b silent); c = count(a silent, b fires). The exact test is
    binomtest(min(b,c), b+c, 0.5, two-sided). With small b+c no p can reach 0.05,
    so the result is labelled UNDERPOWERED rather than reported as a negative.
    """
    a = np.asarray(a_flags, dtype=int)
    b_arr = np.asarray(b_flags, dtype=int)
    if a.shape != b_arr.shape:
        raise ValueError(f"shape mismatch {a.shape} vs {b_arr.shape}")
    b = int(np.sum((a == 1) & (b_arr == 0)))
    c = int(np.sum((a == 0) & (b_arr == 1)))
    n_disc = b + c
    if n_disc == 0:
        return {
            "b": 0, "c": 0, "n_discordant": 0, "p_exact": 1.0,
            "n_pairs": int(a.size), "a_count": int(a.sum()), "b_count": int(b_arr.sum()),
            "power_note": "NO_DISCORDANT_PAIRS", "underpowered": True,
            "min_attainable_p": 1.0,
        }
    res = stats.binomtest(min(b, c), n_disc, 0.5, alternative="two-sided")
    # smallest two-sided p attainable at this discordant count (all on one side)
    min_p = float(stats.binomtest(0, n_disc, 0.5, alternative="two-sided").pvalue)
    return {
        "b": b, "c": c, "n_discordant": n_disc, "p_exact": float(res.pvalue),
        "n_pairs": int(a.size), "a_count": int(a.sum()), "b_count": int(b_arr.sum()),
        "min_attainable_p": min_p,
        "underpowered": bool(min_p > 0.05),
        "power_note": (
            f"UNDERPOWERED: with {n_disc} discordant pairs the smallest attainable "
            f"two-sided p is {min_p:.4f} > 0.05, so no result at this n can be "
            "significant; this is not evidence of no difference."
        ) if min_p > 0.05 else "adequately powered at alpha=0.05",
    }


# --------------------------------------------------------------------------- #
# Holm-Bonferroni, recomputed within a family (never a reused stored flag)
# --------------------------------------------------------------------------- #
def holm(pvals: Sequence[float], alpha: float = 0.05) -> dict[str, Any]:
    """Holm-Bonferroni step-down over a family of m p-values."""
    p = np.asarray(pvals, dtype=float)
    m = p.size
    order = np.argsort(p, kind="stable")
    adj = np.empty(m, dtype=float)
    running = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * p[idx]
        running = max(running, val)
        adj[idx] = min(1.0, running)
    return {
        "m": int(m),
        "p_adj": [float(x) for x in adj],
        "reject": [bool(x <= alpha) for x in adj],
        "alpha": alpha,
        "n_reject": int(np.sum(adj <= alpha)),
    }


# --------------------------------------------------------------------------- #
# Bootstrap
# --------------------------------------------------------------------------- #
def boot_ci(
    values: Sequence[float],
    stat: Callable[[np.ndarray], float] = np.mean,
    b: int = B_BOOT,
    offset: int = 0,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Percentile bootstrap CI over items."""
    x = np.asarray(values, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return {"point": None, "lo": None, "hi": None, "n": 0, "B": b}
    g = rng(offset)
    idx = g.integers(0, x.size, size=(b, x.size))
    draws = np.array([stat(x[row]) for row in idx], dtype=float)
    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "point": float(stat(x)), "lo": float(lo), "hi": float(hi),
        "n": int(x.size), "B": int(b), "sd": float(np.std(draws, ddof=1)),
    }


# --------------------------------------------------------------------------- #
# Correlations
# --------------------------------------------------------------------------- #
def spearman(x: Sequence[float], y: Sequence[float]) -> dict[str, Any]:
    xa, ya = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(xa) & np.isfinite(ya)
    xa, ya = xa[ok], ya[ok]
    if xa.size < 3:
        return {"rho": None, "p": None, "n": int(xa.size), "note": "n<3"}
    r = stats.spearmanr(xa, ya)
    return {"rho": float(r.statistic), "p": float(r.pvalue), "n": int(xa.size)}


def kendall(x: Sequence[float], y: Sequence[float]) -> dict[str, Any]:
    xa, ya = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(xa) & np.isfinite(ya)
    xa, ya = xa[ok], ya[ok]
    if xa.size < 3:
        return {"tau": None, "p": None, "n": int(xa.size), "note": "n<3"}
    r = stats.kendalltau(xa, ya)
    return {"tau": float(r.statistic), "p": float(r.pvalue), "n": int(xa.size)}


# --------------------------------------------------------------------------- #
# Monte-Carlo permutation critical |rho| and required panel size
# --------------------------------------------------------------------------- #
def perm_critical_rho(n: int, n_perm: int = N_PERM, alpha: float = 0.05,
                      offset: int = 0) -> float:
    """Two-sided critical |Spearman rho| at sample size n by permutation.

    Under H0 the ranks are exchangeable, so the null distribution of rho depends
    only on n. We permute rank vectors directly, which is exact for untied data.
    """
    g = rng(offset + n)
    base = np.arange(1, n + 1, dtype=float)
    base_c = base - base.mean()
    denom = float(np.sum(base_c**2))
    draws = np.empty(n_perm, dtype=float)
    for i in range(n_perm):
        perm = g.permutation(base)
        draws[i] = float(np.dot(base_c, perm - perm.mean()) / denom)
    return float(np.percentile(np.abs(draws), 100 * (1 - alpha)))


def required_panel_size(
    targets: dict[str, float],
    grid: Sequence[int],
    n_perm: int = 4000,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Smallest n on the grid at which critical |rho| falls below each target."""
    crit = {int(n): perm_critical_rho(int(n), n_perm=n_perm, alpha=alpha) for n in grid}
    out: dict[str, Any] = {"critical_rho_by_n": crit, "alpha": alpha,
                           "n_perm": n_perm, "grid": [int(n) for n in grid]}
    answers: dict[str, Any] = {}
    for label, target in targets.items():
        if target is None or not math.isfinite(target):
            answers[label] = {"target": target, "required_n": None,
                              "note": "target UNAVAILABLE"}
            continue
        hit = next((n for n in sorted(crit) if crit[n] < abs(target)), None)
        answers[label] = {
            "target_abs": float(abs(target)),
            "required_n": hit,
            "note": (f"critical |rho| drops below {abs(target):.3f} at n={hit}"
                     if hit is not None
                     else f"no n<= {max(crit)} on the grid reaches |rho|<{abs(target):.3f}"),
        }
    out["answers"] = answers
    return out


# --------------------------------------------------------------------------- #
# Equivalence (TOST) on a bounded effect
# --------------------------------------------------------------------------- #
def tost_bound(effects: Sequence[float], margin: float) -> dict[str, Any]:
    """Two one-sided tests for equivalence of a mean effect to zero.

    Reported alongside the plain bound (max |effect| vs median MDE80), which is
    the form of a null a reviewer can act on.
    """
    x = np.asarray(effects, dtype=float)
    x = x[np.isfinite(x)]
    if x.size < 2 or margin <= 0:
        return {"verdict": "UNAVAILABLE", "n": int(x.size), "margin": margin}
    mean = float(np.mean(x))
    se = float(np.std(x, ddof=1) / math.sqrt(x.size))
    if se == 0:
        return {"verdict": "EQUIVALENT" if abs(mean) < margin else "NOT_EQUIVALENT",
                "n": int(x.size), "margin": float(margin), "mean": mean,
                "note": "zero variance"}
    df = x.size - 1
    t_lo = (mean + margin) / se
    t_hi = (mean - margin) / se
    p_lo = float(stats.t.sf(t_lo, df))
    p_hi = float(stats.t.cdf(t_hi, df))
    p = max(p_lo, p_hi)
    return {
        "verdict": "EQUIVALENT" if p < 0.05 else "NOT_EQUIVALENT",
        "p_tost": p, "mean": mean, "se": se, "n": int(x.size),
        "margin": float(margin), "df": int(df),
    }


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int,
                     alpha: float = 0.05) -> tuple[float, float, float]:
    """Newcombe hybrid-score CI for a difference of two proportions."""
    z = float(stats.norm.ppf(1 - alpha / 2))

    def wilson(k: int, n: int) -> tuple[float, float]:
        if n == 0:
            return (0.0, 1.0)
        p = k / n
        d = 1 + z**2 / n
        c = p + z**2 / (2 * n)
        h = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
        return ((c - h) / d, (c + h) / d)

    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    p1 = k1 / n1 if n1 else 0.0
    p2 = k2 / n2 if n2 else 0.0
    diff = p1 - p2
    lo = diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return float(diff), float(lo), float(hi)


def median_or_none(vals: Sequence[float]) -> float | None:
    x = np.asarray([v for v in vals if v is not None], dtype=float)
    x = x[np.isfinite(x)]
    return float(np.median(x)) if x.size else None
