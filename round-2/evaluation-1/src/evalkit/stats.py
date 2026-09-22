#!/usr/bin/env python3
"""Statistical machinery shared by every metric in this artifact.

One implementation of each procedure so that no two tables can silently use
different conventions:

* ``bca_bootstrap``      -- bias-corrected-and-accelerated percentile intervals.
* ``cluster_bootstrap``  -- the same, resampling CLUSTERS (families), never members.
* ``tost``               -- two-one-sided-tests equivalence, the only way this
  artifact is allowed to claim two things are the SAME.
* ``clopper_pearson``    -- exact binomial interval for TPR at a fixed FPR.
* ``tpr_at_fpr``         -- operating-point statistic with its resolution floor.
* ``holm``               -- Holm step-down, applied to confirmatory rows only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Callable, Sequence

import numpy as np
from scipy import stats as sps

BOOT_DRAWS = 10_000
ALPHA = 0.05


# --------------------------------------------------------------------------- #
# intervals
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Interval:
    point: float
    low: float
    high: float
    n: int
    method: str

    def as_dict(self) -> dict:
        return asdict(self)

    def fmt(self, digits: int = 4) -> str:
        if not np.isfinite(self.point):
            return "NaN"
        if not (np.isfinite(self.low) and np.isfinite(self.high)):
            return f"{self.point:.{digits}f} [NaN, NaN]"
        return f"{self.point:.{digits}f} [{self.low:.{digits}f}, {self.high:.{digits}f}]"


def _percentile_fallback(theta_hat: float, boots: np.ndarray, n: int, why: str) -> Interval:
    if boots.size == 0:
        return Interval(theta_hat, float("nan"), float("nan"), n, f"degenerate:{why}")
    lo, hi = np.percentile(boots, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
    return Interval(theta_hat, float(lo), float(hi), n, f"percentile:{why}")


def bca_bootstrap(
    data: np.ndarray,
    statistic: Callable[[np.ndarray], float],
    *,
    draws: int = BOOT_DRAWS,
    seed: int = 20260921,
    alpha: float = ALPHA,
) -> Interval:
    """BCa interval for ``statistic`` over rows of ``data`` (axis 0 is the unit).

    Falls back to the percentile interval, with the reason recorded in
    ``Interval.method``, whenever the acceleration or bias correction is not
    estimable (all-identical resamples, or a jackknife with fewer than 2 units).
    """
    data = np.asarray(data)
    n = data.shape[0]
    theta_hat = float(statistic(data))
    if n < 2 or not np.isfinite(theta_hat):
        return Interval(theta_hat, float("nan"), float("nan"), n, "n<2")

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(draws, n))
    boots = np.empty(draws, dtype=float)
    for b in range(draws):
        boots[b] = statistic(data[idx[b]])
    boots = boots[np.isfinite(boots)]
    if boots.size < draws // 2:
        return _percentile_fallback(theta_hat, boots, n, "unstable_statistic")

    prop = float(np.mean(boots < theta_hat))
    if prop <= 0.0 or prop >= 1.0:
        return _percentile_fallback(theta_hat, boots, n, "z0_undefined")
    z0 = sps.norm.ppf(prop)

    jack = np.empty(n, dtype=float)
    keep = np.ones(n, dtype=bool)
    for i in range(n):
        keep[i] = False
        jack[i] = statistic(data[keep])
        keep[i] = True
    jack = jack[np.isfinite(jack)]
    if jack.size < 2:
        return _percentile_fallback(theta_hat, boots, n, "jackknife_undefined")
    jbar = jack.mean()
    num = float(np.sum((jbar - jack) ** 3))
    den = 6.0 * float(np.sum((jbar - jack) ** 2)) ** 1.5
    acc = 0.0 if den == 0 else num / den

    out = []
    for q in (alpha / 2, 1 - alpha / 2):
        zq = sps.norm.ppf(q)
        adj = z0 + (z0 + zq) / max(1e-12, (1 - acc * (z0 + zq)))
        out.append(float(np.percentile(boots, 100 * sps.norm.cdf(adj))))
    return Interval(theta_hat, out[0], out[1], n, "bca")


def cluster_bootstrap(
    clusters: Sequence[np.ndarray],
    statistic: Callable[[np.ndarray], float],
    *,
    draws: int = BOOT_DRAWS,
    seed: int = 20260921,
    alpha: float = ALPHA,
) -> Interval:
    """BCa interval resampling whole CLUSTERS with replacement.

    Every interval in this artifact that spans checkpoints uses this, with the
    clusters being FAMILIES: checkpoints inside a family are not independent, so
    resampling checkpoints would understate the interval.
    """
    clusters = [np.asarray(c) for c in clusters if np.asarray(c).size > 0]
    k = len(clusters)
    if k == 0:
        return Interval(float("nan"), float("nan"), float("nan"), 0, "no_clusters")
    pooled = np.concatenate(clusters, axis=0)
    theta_hat = float(statistic(pooled))
    if k < 2:
        return Interval(theta_hat, float("nan"), float("nan"), k, "n_clusters<2")

    rng = np.random.default_rng(seed)
    boots = np.empty(draws, dtype=float)
    for b in range(draws):
        pick = rng.integers(0, k, size=k)
        boots[b] = statistic(np.concatenate([clusters[j] for j in pick], axis=0))
    boots = boots[np.isfinite(boots)]
    if boots.size < draws // 2:
        return _percentile_fallback(theta_hat, boots, k, "unstable_statistic")

    prop = float(np.mean(boots < theta_hat))
    if prop <= 0.0 or prop >= 1.0:
        return _percentile_fallback(theta_hat, boots, k, "z0_undefined")
    z0 = sps.norm.ppf(prop)

    jack = np.empty(k, dtype=float)
    for i in range(k):
        rest = [clusters[j] for j in range(k) if j != i]
        jack[i] = statistic(np.concatenate(rest, axis=0))
    jack = jack[np.isfinite(jack)]
    if jack.size < 2:
        return _percentile_fallback(theta_hat, boots, k, "jackknife_undefined")
    jbar = jack.mean()
    num = float(np.sum((jbar - jack) ** 3))
    den = 6.0 * float(np.sum((jbar - jack) ** 2)) ** 1.5
    acc = 0.0 if den == 0 else num / den

    out = []
    for q in (alpha / 2, 1 - alpha / 2):
        zq = sps.norm.ppf(q)
        adj = z0 + (z0 + zq) / max(1e-12, (1 - acc * (z0 + zq)))
        out.append(float(np.percentile(boots, 100 * sps.norm.cdf(adj))))
    return Interval(theta_hat, out[0], out[1], k, "bca_cluster")


def paired_bootstrap_se(
    diffs: np.ndarray, *, draws: int = BOOT_DRAWS, seed: int = 20260921
) -> float:
    """Bootstrap SE of the mean paired difference, used to invert R5's power sentence."""
    d = np.asarray(diffs, dtype=float)
    d = d[np.isfinite(d)]
    if d.size < 2:
        return float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, d.size, size=(draws, d.size))
    return float(np.std(d[idx].mean(axis=1), ddof=1))


# --------------------------------------------------------------------------- #
# equivalence
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class TostResult:
    verdict: str
    diff: float
    se: float
    margin: float
    p_lower: float
    p_upper: float
    p_tost: float
    ci90_low: float
    ci90_high: float
    achieved_margin: float
    n: int

    def as_dict(self) -> dict:
        return asdict(self)


def tost(diffs: np.ndarray, margin: float, *, alpha: float = ALPHA) -> TostResult:
    """Two-one-sided-tests equivalence on a paired difference.

    Returns EQUIVALENT only when the whole 1-2*alpha interval lies inside
    (-margin, +margin). NOT_EQUIVALENT means the difference is itself
    significantly non-zero; INCONCLUSIVE -- a real and expected verdict at these
    sample sizes -- means neither, and is never to be reported as EQUIVALENT.
    """
    d = np.asarray(diffs, dtype=float)
    d = d[np.isfinite(d)]
    n = d.size
    nan = float("nan")
    if n < 2:
        return TostResult("INCONCLUSIVE_N_TOO_SMALL", float(d.mean()) if n else nan,
                          nan, margin, nan, nan, nan, nan, nan, nan, n)
    mean = float(d.mean())
    se = float(d.std(ddof=1) / math.sqrt(n))
    if se == 0.0:
        verdict = "EQUIVALENT" if abs(mean) < margin else "NOT_EQUIVALENT"
        return TostResult(verdict, mean, 0.0, margin, 0.0, 0.0, 0.0, mean, mean,
                          abs(mean), n)
    df = n - 1
    t_lo = (mean + margin) / se
    t_hi = (mean - margin) / se
    p_lower = float(sps.t.sf(t_lo, df))      # H0: diff <= -margin
    p_upper = float(sps.t.cdf(t_hi, df))     # H0: diff >= +margin
    p_tost = max(p_lower, p_upper)
    crit = sps.t.ppf(1 - alpha, df)
    lo, hi = mean - crit * se, mean + crit * se
    p_two = float(2 * sps.t.sf(abs(mean) / se, df))

    if p_tost < alpha:
        verdict = "EQUIVALENT"
    elif p_two < alpha:
        verdict = "NOT_EQUIVALENT"
    else:
        verdict = "INCONCLUSIVE"
    # smallest margin at which this data would have read EQUIVALENT
    achieved = float(abs(mean) + crit * se)
    return TostResult(verdict, mean, se, margin, p_lower, p_upper, p_tost,
                      float(lo), float(hi), achieved, n)


def power_sentence(diffs: np.ndarray, *, label: str, power: float = 0.80,
                   alpha: float = ALPHA) -> tuple[str, float]:
    """R5. Invert the paired bootstrap SE into the effect detectable at 80% power."""
    se = paired_bootstrap_se(diffs)
    n = int(np.isfinite(np.asarray(diffs, dtype=float)).sum())
    if not np.isfinite(se) or se == 0.0:
        why = "n<2" if n < 2 else "bootstrap SE is exactly zero (degenerate outcome)"
        return (f"with this outcome and n = {n}, no detectable effect is "
                f"computable: {why}"), float("nan")
    mde = float((sps.norm.ppf(1 - alpha / 2) + sps.norm.ppf(power)) * se)
    return (f"with this outcome and n = {n}, a degradation of {mde:.4f} "
            f"{label} would have been detected at power 0.80"), mde


# --------------------------------------------------------------------------- #
# operating points
# --------------------------------------------------------------------------- #
def clopper_pearson(k: int, n: int, *, alpha: float = ALPHA) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    lo = 0.0 if k == 0 else float(sps.beta.ppf(alpha / 2, k, n - k + 1))
    hi = 1.0 if k == n else float(sps.beta.ppf(1 - alpha / 2, k + 1, n - k))
    return lo, hi


@dataclass(frozen=True)
class OperatingPoint:
    fpr_target: float
    tpr: float
    ci_low: float
    ci_high: float
    threshold: float
    n_pos: int
    n_neg: int
    smallest_resolvable_step: float
    estimable: bool
    note: str

    def as_dict(self) -> dict:
        return asdict(self)

    def fmt(self) -> str:
        if not self.estimable:
            return f"NOT_ESTIMABLE_AT_{self.fpr_target:.0%}(n_neg={self.n_neg})"
        return f"{self.tpr:.4f} [{self.ci_low:.4f}, {self.ci_high:.4f}]"


def tpr_at_fpr(pos: np.ndarray, neg: np.ndarray, fpr: float,
               *, min_neg_for_estimability: int | None = None) -> OperatingPoint:
    """TPR at a fixed FPR, with its exact interval and its resolution floor.

    The threshold is the (1-fpr) quantile of the NEGATIVE scores. If there are
    fewer negatives than 1/fpr the operating point is not estimable at all --
    reported as such rather than interpolated, because interpolating a threshold
    the data cannot support is how a saturated outcome gets a spurious number.
    """
    pos = np.asarray(pos, dtype=float)
    neg = np.asarray(neg, dtype=float)
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    n_pos, n_neg = pos.size, neg.size
    step = 1.0 / n_neg if n_neg else float("nan")
    need = min_neg_for_estimability if min_neg_for_estimability is not None else int(round(1 / fpr))
    if n_neg < need or n_pos == 0:
        return OperatingPoint(fpr, float("nan"), float("nan"), float("nan"),
                              float("nan"), n_pos, n_neg, step, False,
                              f"n_neg={n_neg} < {need} required to resolve FPR={fpr}")
    thr = float(np.quantile(neg, 1.0 - fpr, method="higher"))
    k = int(np.sum(pos > thr))
    tpr = k / n_pos
    lo, hi = clopper_pearson(k, n_pos)
    realised = float(np.mean(neg > thr))
    return OperatingPoint(fpr, tpr, lo, hi, thr, n_pos, n_neg, step, True,
                          f"realised_fpr={realised:.4f}")


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Mann-Whitney AUROC with ties at 0.5, no sklearn dependency in hot loops."""
    pos = np.asarray(pos, dtype=float)
    neg = np.asarray(neg, dtype=float)
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    ranks = sps.rankdata(allv)
    r_pos = ranks[: pos.size].sum()
    return float((r_pos - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size))


# --------------------------------------------------------------------------- #
# multiplicity
# --------------------------------------------------------------------------- #
def holm(pvalues: dict[str, float], *, alpha: float = ALPHA) -> dict[str, dict]:
    """Holm step-down. Applied to the confirmatory rows of M1 and M6 only."""
    items = [(k, v) for k, v in pvalues.items() if np.isfinite(v)]
    items.sort(key=lambda kv: kv[1])
    m = len(items)
    out: dict[str, dict] = {}
    rejected_so_far = True
    for i, (key, p) in enumerate(items):
        thr = alpha / (m - i)
        if rejected_so_far and p <= thr:
            decision = "REJECT_NULL"
        else:
            rejected_so_far = False
            decision = "RETAIN_NULL"
        out[key] = {"p_raw": float(p), "holm_threshold": float(thr),
                    "rank": i + 1, "n_confirmatory": m, "decision": decision}
    for key, p in pvalues.items():
        if key not in out:
            out[key] = {"p_raw": float(p) if p is not None else float("nan"),
                        "holm_threshold": float("nan"), "rank": -1,
                        "n_confirmatory": m, "decision": "NOT_APPLICABLE_NONFINITE_P"}
    return out


def spearman_with_resolvability(x: np.ndarray, y: np.ndarray,
                                *, alpha: float = ALPHA) -> dict:
    """Spearman rho plus the SMALLEST |rho| that is distinguishable from zero at n.

    At 5 or 6 pairs only very large correlations are resolvable, so a naked rho
    is never reported without this companion.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = np.isfinite(x) & np.isfinite(y)
    x, y = x[ok], y[ok]
    n = x.size
    if n < 3:
        return {"rho": float("nan"), "p": float("nan"), "n": int(n),
                "min_resolvable_abs_rho": float("nan"),
                "note": "n<3, Spearman undefined"}
    rho, p = sps.spearmanr(x, y)
    # critical |rho| at alpha via the t approximation
    tcrit = sps.t.ppf(1 - alpha / 2, n - 2)
    rcrit = float(tcrit / math.sqrt(tcrit**2 + n - 2))
    return {"rho": float(rho), "p": float(p), "n": int(n),
            "min_resolvable_abs_rho": rcrit,
            "note": (f"at n={n}, only |rho| >= {rcrit:.3f} is distinguishable "
                     f"from zero at alpha={alpha}")}
