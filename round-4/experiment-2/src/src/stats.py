"""Pure-numpy statistics utilities for paired per-item causal-intervention contrasts.

All public functions are deterministic given a `seed` (they build their own
`np.random.default_rng(seed)` internally) and return plain Python
floats/ints/lists/dicts (JSON-serialisable; NaN is returned as `float('nan')`).

Design notes
------------
- NaNs are dropped *pairwise*: for a contrast between two (or more) arrays, an
  item is used only if every array involved in that contrast is finite for it.
- Bootstraps and the sign-flip permutation test are vectorised: resample
  index matrices / sign matrices are built in one call (chunked when the
  full matrix would be large), never via a Python loop over resamples.
- scipy is used only for two exact building blocks that are not worth
  re-deriving by hand: the normal quantile (`scipy.stats.norm.ppf`, for the
  Wilson interval) and the exact binomial two-sided p-value
  (`scipy.stats.binomtest`, for McNemar's exact test). Everything else is
  pure numpy.
"""

from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
from scipy.stats import binomtest, norm

__all__ = [
    "paired_effect",
    "holm",
    "holm_ci_level",
    "bootstrap_ci_at",
    "empirical_p",
    "auroc",
    "auroc_ci",
    "cohens_d",
    "d_null_sd",
    "d_z",
    "did_paired",
    "rate_ci",
    "newcombe_diff_ci",
    "mean_ci",
    "mcnemar_exact",
]

# ---------------------------------------------------------------------------
# internal helpers
# ---------------------------------------------------------------------------

_Z80 = 0.8416212335729143  # Phi^-1(0.9), power = 0.80
_Z95 = 1.959963984540054   # Phi^-1(0.975), alpha = 0.05 (two-sided)


def _finite1d(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float).reshape(-1)
    return x[np.isfinite(x)]


def _bootstrap_means(x: np.ndarray, B: int, seed: int, max_elems: int = 20_000_000) -> np.ndarray:
    """Vectorised percentile-bootstrap: means of B resamples (with replacement) of x."""
    n = x.size
    if n == 0 or B <= 0:
        return np.full(max(B, 0), np.nan)
    rng = np.random.default_rng(seed)
    out = np.empty(B, dtype=float)
    chunk = max(1, min(B, max_elems // max(1, n)))
    start = 0
    while start < B:
        end = min(B, start + chunk)
        idx = rng.integers(0, n, size=(end - start, n))
        out[start:end] = x[idx].mean(axis=1)
        start = end
    return out


def _signflip_p(diff: np.ndarray, seed: int, n_perm: int = 10000, chunk_size: int = 2000) -> float:
    """Two-sided sign-flip permutation p-value on per-item differences `diff`."""
    n = diff.size
    if n == 0:
        return float("nan")
    if np.all(diff == 0):
        return 1.0
    obs = abs(float(diff.mean()))
    rng = np.random.default_rng(seed)
    count = 0
    start = 0
    while start < n_perm:
        end = min(n_perm, start + chunk_size)
        b = end - start
        signs = rng.integers(0, 2, size=(b, n)).astype(np.int8) * 2 - 1
        perm_means = (diff[None, :] * signs).mean(axis=1)
        count += int(np.sum(np.abs(perm_means) >= obs))
        start = end
    return (1.0 + count) / (1.0 + n_perm)


def _rankdata_average(a: np.ndarray) -> np.ndarray:
    """Average (mid-)ranks, 1-indexed, ties handled by averaging (pure numpy)."""
    n = a.size
    sorter = np.argsort(a, kind="mergesort")
    a_sorted = a[sorter]
    ordinal = np.arange(1, n + 1, dtype=float)
    is_new = np.empty(n, dtype=bool)
    is_new[0] = True
    if n > 1:
        is_new[1:] = a_sorted[1:] != a_sorted[:-1]
    group_id = np.cumsum(is_new) - 1
    n_groups = int(group_id[-1]) + 1
    sums = np.bincount(group_id, weights=ordinal, minlength=n_groups)
    counts = np.bincount(group_id, minlength=n_groups)
    avg_rank_per_group = sums / counts
    avg_rank_sorted = avg_rank_per_group[group_id]
    ranks = np.empty(n, dtype=float)
    ranks[sorter] = avg_rank_sorted
    return ranks


# ---------------------------------------------------------------------------
# 1. paired_effect
# ---------------------------------------------------------------------------


def paired_effect(
    y_a: np.ndarray,
    y_b: Optional[np.ndarray] = None,
    *,
    y_b_draws: Optional[np.ndarray] = None,
    B: int = 2000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict:
    """Paired per-item effect of y_a vs. a reference, with bootstrap CI and sign-flip p.

    Effect = mean_i[y_a,i - ref_i]. ref_i = y_b[i], or, if `y_b_draws` (shape
    [K, n]) is given instead of `y_b`, ref_i = nanmean over the K draws of
    y_b_draws[:, i] (an item whose draws are all NaN is dropped). NaNs are
    then dropped pairwise between y_a and ref.

    Returns
    -------
    dict with keys: effect, ci_lo, ci_hi (percentile bootstrap over items),
    p_signflip (two-sided sign-flip permutation test, 10000 flips), n,
    sd_diff, mde_80 (paired MDE at alpha=0.05, power=0.8).
    """
    y_a = np.asarray(y_a, dtype=float).reshape(-1)
    if y_b_draws is not None:
        draws = np.asarray(y_b_draws, dtype=float)
        if draws.ndim == 1:
            draws = draws[None, :]
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Mean of empty slice")
            all_nan = np.all(np.isnan(draws), axis=0)
            ref = np.where(all_nan, np.nan, np.nanmean(draws, axis=0))
    else:
        ref = np.asarray(y_b, dtype=float).reshape(-1)

    mask = np.isfinite(y_a) & np.isfinite(ref)
    diff = y_a[mask] - ref[mask]
    n = int(diff.size)

    if n == 0:
        return {
            "effect": float("nan"),
            "ci_lo": float("nan"),
            "ci_hi": float("nan"),
            "p_signflip": float("nan"),
            "n": 0,
            "sd_diff": float("nan"),
            "mde_80": float("nan"),
        }

    effect = float(diff.mean())
    ci_lo, ci_hi = bootstrap_ci_at(diff, alpha, B=B, seed=seed)
    p_signflip = _signflip_p(diff, seed=seed)
    sd_diff = float(diff.std(ddof=1)) if n > 1 else float("nan")
    mde_80 = float((_Z95 + _Z80) * sd_diff / np.sqrt(n)) if n > 1 else float("nan")

    return {
        "effect": effect,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "p_signflip": p_signflip,
        "n": n,
        "sd_diff": sd_diff,
        "mde_80": mde_80,
    }


# ---------------------------------------------------------------------------
# 2/3. holm, holm_ci_level, bootstrap_ci_at
# ---------------------------------------------------------------------------


def holm(pvals: list) -> list:
    """Holm step-down adjusted p-values. Monotone non-decreasing, capped at 1.

    NaN-safe: NaN entries stay NaN and are excluded from the family size m.
    """
    p = np.asarray(pvals, dtype=float)
    finite_mask = np.isfinite(p)
    m = int(finite_mask.sum())
    out = np.full(p.shape, np.nan, dtype=float)
    if m == 0:
        return out.tolist()

    finite_idx = np.where(finite_mask)[0]
    finite_p = p[finite_idx]
    order = np.argsort(finite_p, kind="mergesort")  # ascending
    sorted_p = finite_p[order]
    multipliers = np.arange(m, 0, -1, dtype=float)  # m, m-1, ..., 1
    adj_sorted = np.minimum(sorted_p * multipliers, 1.0)
    adj_sorted = np.maximum.accumulate(adj_sorted)  # enforce monotonicity

    adj = np.empty(m, dtype=float)
    adj[order] = adj_sorted
    out[finite_idx] = adj
    return out.tolist()


def holm_ci_level(pvals: list) -> list:
    """Family-wise alpha actually applied to each p-value in Holm step-down.

    For the p-value with ascending rank r (1 = smallest) out of family size
    m, the applied level is alpha / (m - r + 1), at alpha = 0.05.
    """
    p = np.asarray(pvals, dtype=float)
    finite_mask = np.isfinite(p)
    m = int(finite_mask.sum())
    out = np.full(p.shape, np.nan, dtype=float)
    if m == 0:
        return out.tolist()

    finite_idx = np.where(finite_mask)[0]
    finite_p = p[finite_idx]
    order = np.argsort(finite_p, kind="mergesort")  # ascending
    ranks = np.empty(m, dtype=int)
    ranks[order] = np.arange(1, m + 1)
    level = 0.05 / (m - ranks + 1)
    out[finite_idx] = level
    return out.tolist()


def bootstrap_ci_at(diff: np.ndarray, level_alpha: float, B: int = 2000, seed: int = 0):
    """Percentile bootstrap CI of the mean of per-item differences `diff`, at `level_alpha`."""
    d = _finite1d(diff)
    if d.size == 0:
        return (float("nan"), float("nan"))
    means = _bootstrap_means(d, B, seed)
    lo, hi = np.percentile(means, [100.0 * level_alpha / 2.0, 100.0 * (1.0 - level_alpha / 2.0)])
    return (float(lo), float(hi))


# ---------------------------------------------------------------------------
# 4. empirical_p
# ---------------------------------------------------------------------------


def empirical_p(effect_f: float, effects_r: np.ndarray) -> float:
    """One-sided empirical p-value of `effect_f` against a null draw pool `effects_r`."""
    r = _finite1d(np.asarray(effects_r, dtype=float))
    K = int(r.size)
    if K == 0:
        return float("nan")
    if effect_f >= 0:
        count = int(np.sum(r >= effect_f))
    else:
        count = int(np.sum(r <= effect_f))
    return (1.0 + count) / (1.0 + K)


# ---------------------------------------------------------------------------
# 5. auroc, auroc_ci
# ---------------------------------------------------------------------------


def auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    """AUROC via the Mann-Whitney rank-sum formula (tie-corrected). labels: 1 = positive."""
    scores = np.asarray(scores, dtype=float).reshape(-1)
    labels = np.asarray(labels).reshape(-1)
    finite = np.isfinite(scores)
    scores = scores[finite]
    labels = labels[finite]
    pos_mask = labels == 1
    neg_mask = labels == 0
    n1 = int(pos_mask.sum())
    n0 = int(neg_mask.sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    ranks = _rankdata_average(scores)
    sum_ranks_pos = float(ranks[pos_mask].sum())
    auc = (sum_ranks_pos - n1 * (n1 + 1) / 2.0) / (n1 * n0)
    return float(auc)


def auroc_ci(scores: np.ndarray, labels: np.ndarray, B: int = 2000, seed: int = 0, alpha: float = 0.05) -> dict:
    """AUROC with a stratified (resample positives and negatives separately) bootstrap CI."""
    scores = np.asarray(scores, dtype=float).reshape(-1)
    labels = np.asarray(labels).reshape(-1)
    finite = np.isfinite(scores)
    scores = scores[finite]
    labels = labels[finite]
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    n1 = int(pos.size)
    n0 = int(neg.size)
    if n1 == 0 or n0 == 0:
        return {
            "auroc": float("nan"),
            "ci_lo": float("nan"),
            "ci_hi": float("nan"),
            "n_pos": n1,
            "n_neg": n0,
        }

    point = auroc(scores, labels)
    rng = np.random.default_rng(seed)
    aucs = np.empty(B, dtype=float)
    max_elems = 2_000_000  # cap on B_chunk * n1 * n0 tensor size
    chunk = max(1, min(B, max_elems // max(1, n1 * n0)))
    start = 0
    while start < B:
        end = min(B, start + chunk)
        b = end - start
        p = pos[rng.integers(0, n1, size=(b, n1))]
        ng = neg[rng.integers(0, n0, size=(b, n0))]
        diff = p[:, :, None] - ng[:, None, :]
        greater = (diff > 0).sum(axis=(1, 2))
        equal = (diff == 0).sum(axis=(1, 2))
        aucs[start:end] = (greater + 0.5 * equal) / (n1 * n0)
        start = end

    lo, hi = np.percentile(aucs, [100.0 * alpha / 2.0, 100.0 * (1.0 - alpha / 2.0)])
    return {
        "auroc": float(point),
        "ci_lo": float(lo),
        "ci_hi": float(hi),
        "n_pos": n1,
        "n_neg": n0,
    }


# ---------------------------------------------------------------------------
# 6. cohens_d, d_null_sd, d_z
# ---------------------------------------------------------------------------


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """Pooled-SD Cohen's d = (mean(a) - mean(b)) / sqrt(pooled variance). NaN-safe."""
    a = _finite1d(a)
    b = _finite1d(b)
    na, nb = a.size, b.size
    if na < 2 or nb < 2:
        return float("nan")
    va = a.var(ddof=1)
    vb = b.var(ddof=1)
    pooled = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    with np.errstate(invalid="ignore", divide="ignore"):
        d = (a.mean() - b.mean()) / pooled
    return float(d)


def d_null_sd(x: np.ndarray, labels: np.ndarray, n_shuffle: int = 200, seed: int = 0) -> float:
    """SD of Cohen's d under label shuffles (permute labels, class sizes fixed)."""
    x = np.asarray(x, dtype=float).reshape(-1)
    labels = np.asarray(labels).reshape(-1)
    finite = np.isfinite(x)
    x = x[finite]
    labels = labels[finite]
    n = x.size
    n_pos = int(np.sum(labels == 1))
    n_neg = int(np.sum(labels == 0))
    if n < 4 or n_pos < 2 or n_neg < 2:
        return float("nan")

    rng = np.random.default_rng(seed)
    keys = rng.random((n_shuffle, n))
    perm_idx = np.argsort(keys, axis=1)
    labels_shuffled = labels[perm_idx]  # [n_shuffle, n]

    pos_mask = (labels_shuffled == 1).astype(float)
    neg_mask = (labels_shuffled == 0).astype(float)
    count_pos = pos_mask.sum(axis=1)
    count_neg = neg_mask.sum(axis=1)

    x_row = x[None, :]
    mean_pos = (x_row * pos_mask).sum(axis=1) / count_pos
    mean_neg = (x_row * neg_mask).sum(axis=1) / count_neg

    ss_pos = (((x_row - mean_pos[:, None]) ** 2) * pos_mask).sum(axis=1)
    ss_neg = (((x_row - mean_neg[:, None]) ** 2) * neg_mask).sum(axis=1)
    var_pos = ss_pos / (count_pos - 1)
    var_neg = ss_neg / (count_neg - 1)

    pooled = np.sqrt(((count_pos - 1) * var_pos + (count_neg - 1) * var_neg) / (count_pos + count_neg - 2))
    with np.errstate(invalid="ignore", divide="ignore"):
        ds = (mean_pos - mean_neg) / pooled

    ds = ds[np.isfinite(ds)]
    if ds.size < 2:
        return float("nan")
    return float(ds.std(ddof=1))


def d_z(x: np.ndarray, labels: np.ndarray, n_shuffle: int = 200, seed: int = 0) -> dict:
    """{"d": observed Cohen's d, "null_sd": SD of d under label shuffles, "z": d / null_sd}."""
    x = np.asarray(x, dtype=float).reshape(-1)
    labels = np.asarray(labels).reshape(-1)
    finite = np.isfinite(x)
    xf = x[finite]
    labf = labels[finite]
    d = cohens_d(xf[labf == 1], xf[labf == 0])
    null_sd = d_null_sd(x, labels, n_shuffle=n_shuffle, seed=seed)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = d / null_sd
    return {"d": float(d), "null_sd": float(null_sd), "z": float(z)}


# ---------------------------------------------------------------------------
# 7. did_paired
# ---------------------------------------------------------------------------


def did_paired(diff_model_a: np.ndarray, diff_model_b: np.ndarray, *, B: int = 2000, seed: int = 0, alpha: float = 0.05) -> dict:
    """Difference-in-differences of two index-aligned per-item within-model contrasts."""
    a = np.asarray(diff_model_a, dtype=float).reshape(-1)
    b = np.asarray(diff_model_b, dtype=float).reshape(-1)
    mask = np.isfinite(a) & np.isfinite(b)
    d = a[mask] - b[mask]
    n = int(d.size)
    if n == 0:
        return {"did": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"), "p_signflip": float("nan"), "n": 0}

    did = float(d.mean())
    ci_lo, ci_hi = bootstrap_ci_at(d, alpha, B=B, seed=seed)
    p_signflip = _signflip_p(d, seed=seed)
    return {"did": did, "ci_lo": ci_lo, "ci_hi": ci_hi, "p_signflip": p_signflip, "n": n}


# ---------------------------------------------------------------------------
# 8. rate_ci, newcombe_diff_ci
# ---------------------------------------------------------------------------


def rate_ci(k: int, n: int, alpha: float = 0.05):
    """Wilson score interval for a binomial rate k/n."""
    if n <= 0:
        return (float("nan"), float("nan"))
    z = float(norm.ppf(1.0 - alpha / 2.0))
    phat = k / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    margin = z * np.sqrt(phat * (1.0 - phat) / n + z * z / (4.0 * n * n)) / denom
    lo = max(0.0, center - margin)
    hi = min(1.0, center + margin)
    return (float(lo), float(hi))


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int, alpha: float = 0.05):
    """Newcombe hybrid score CI for p1 - p2 (two independent, unpaired proportions)."""
    if n1 <= 0 or n2 <= 0:
        return (float("nan"), float("nan"))
    p1 = k1 / n1
    p2 = k2 / n2
    l1, u1 = rate_ci(k1, n1, alpha)
    l2, u2 = rate_ci(k2, n2, alpha)
    diff = p1 - p2
    lo = diff - np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    hi = diff + np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    lo = max(-1.0, float(lo))
    hi = min(1.0, float(hi))
    return (lo, hi)


# ---------------------------------------------------------------------------
# 9. mean_ci
# ---------------------------------------------------------------------------


def mean_ci(x: np.ndarray, B: int = 2000, seed: int = 0, alpha: float = 0.05) -> dict:
    """Percentile bootstrap CI of a mean (NaN dropped)."""
    xf = _finite1d(x)
    n = int(xf.size)
    if n == 0:
        return {"mean": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"), "n": 0}
    m = float(xf.mean())
    ci_lo, ci_hi = bootstrap_ci_at(xf, alpha, B=B, seed=seed)
    return {"mean": m, "ci_lo": ci_lo, "ci_hi": ci_hi, "n": n}


# ---------------------------------------------------------------------------
# 10. mcnemar_exact
# ---------------------------------------------------------------------------


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value on the discordant-pair counts b, c."""
    n = int(b) + int(c)
    if n == 0:
        return 1.0
    k = int(min(b, c))
    return float(binomtest(k, n, 0.5, alternative="two-sided").pvalue)
