#!/usr/bin/env python3
"""Pure-numpy analysis over the saved harvest.  No GPU, re-runnable in seconds.

Everything here reads ``harvest/<ckpt_tag>/*.npz`` and the hash-verified prereg.  The
registered term of every candidate is READ FROM the prereg, never chosen here.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from loguru import logger

BOOT_B = 5000
N_RAND_DIRS = 20
N_SHUFFLE = 20
BAND_WIDTH = 9

SAFETY_CELLS: tuple[str, ...] = tuple(
    f"saf|{f}|{r}|{p}" for f in ("F1", "F2") for r in ("H", "B") for p in ("haz", "ben")
)
COH_CELLS: tuple[str, ...] = tuple(
    f"coh|F1|{r}|{p}" for r in ("A", "B") for p in ("A", "B")
)
GRID_CELLS: tuple[str, ...] = SAFETY_CELLS + COH_CELLS


# ---------------------------------------------------------------------------
# small statistical helpers
# ---------------------------------------------------------------------------

def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    sp = math.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / max(na + nb - 2, 1))
    return float((a.mean() - b.mean()) / sp) if sp > 0 else float("nan")


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    """Rank-based AUROC with tie handling."""
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    x = np.concatenate([pos, neg])
    r = np.argsort(np.argsort(x, kind="mergesort"), kind="mergesort").astype(np.float64) + 1.0
    # average ranks for ties
    order = np.argsort(x, kind="mergesort")
    xs = x[order]
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        if j > i:
            r[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg)))


def boot_ci(vals: np.ndarray, *, b: int = BOOT_B, seed: int = 0,
            stat=np.mean) -> tuple[float, float, float, np.ndarray]:
    """Item-clustered (i.e. resample the unit of analysis) percentile bootstrap."""
    vals = np.asarray(vals, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    if len(vals) < 2:
        return float("nan"), float("nan"), float("nan"), np.array([])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(vals), size=(b, len(vals)))
    draws = stat(vals[idx], axis=1)
    return float(stat(vals)), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5)), draws


def paired_boot_ci(a: np.ndarray, bvals: np.ndarray, *, b: int = BOOT_B,
                   seed: int = 0) -> tuple[float, float, float]:
    """Paired item-clustered bootstrap of mean(a) - mean(bvals) over SHARED items."""
    a = np.asarray(a, dtype=np.float64)
    bvals = np.asarray(bvals, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(bvals)
    a, bvals = a[ok], bvals[ok]
    if len(a) < 2:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(b, len(a)))
    draws = a[idx].mean(axis=1) - bvals[idx].mean(axis=1)
    return float(a.mean() - bvals.mean()), float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))


def tost(vals: np.ndarray, margin: float, *, alpha: float = 0.05) -> dict[str, float]:
    """Two one-sided tests for equivalence within +/- margin (90% CI <=> alpha=0.05 each side)."""
    from scipy import stats
    vals = np.asarray(vals, dtype=np.float64)
    vals = vals[np.isfinite(vals)]
    n = len(vals)
    if n < 3:
        return {"p_lower": float("nan"), "p_upper": float("nan"), "equivalent": False}
    se = vals.std(ddof=1) / math.sqrt(n)
    if se == 0:
        return {"p_lower": 0.0, "p_upper": 0.0, "equivalent": True}
    t1 = (vals.mean() + margin) / se
    t2 = (vals.mean() - margin) / se
    p1 = float(stats.t.sf(t1, n - 1))
    p2 = float(stats.t.cdf(t2, n - 1))
    return {"p_lower": p1, "p_upper": p2, "equivalent": bool(max(p1, p2) < alpha),
            "mean": float(vals.mean()), "se": float(se)}


def holm(pvals: Sequence[float]) -> list[float]:
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.zeros(m)
    running = 0.0
    for rank, i in enumerate(order):
        val = (m - rank) * pvals[i]
        running = max(running, val)
        adj[i] = min(1.0, running)
    return adj.tolist()


def unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    n = np.where(n == 0, 1.0, n)
    return v / n


# ---------------------------------------------------------------------------
# checkpoint container
# ---------------------------------------------------------------------------

@dataclass
class Ckpt:
    tag: str
    root: Path
    meta: dict[str, Any]

    def npz(self, name: str) -> dict[str, np.ndarray]:
        from . import shard
        p = self.root / f"{name}.npz"
        if not shard.exists(p):
            raise FileNotFoundError(p)
        return shard.load_npz(p)


def load_ckpt(root: Path, tag: str) -> Ckpt:
    d = root / tag
    meta = json.loads((d / "meta.json").read_text())
    return Ckpt(tag=tag, root=d, meta=meta)


# ---------------------------------------------------------------------------
# projection machinery
# ---------------------------------------------------------------------------

def project(vecs: np.ndarray, direction: np.ndarray, band: tuple[int, int]) -> np.ndarray:
    """(N, n_hs, D) x (n_hs, D) -> (N,) averaged over the frozen layer band."""
    lo, hi = band
    v = vecs[:, lo:hi + 1].astype(np.float32)
    d = direction[lo:hi + 1].astype(np.float32)
    return np.einsum("nld,ld->n", v, d) / (hi - lo + 1)


def project_multi(vecs: np.ndarray, dirs: np.ndarray, band: tuple[int, int]) -> np.ndarray:
    """(N, n_hs, D) x (n_hs, K, D) -> (N, K) averaged over the band."""
    lo, hi = band
    v = vecs[:, lo:hi + 1].astype(np.float32)
    d = dirs[lo:hi + 1].astype(np.float32)
    return np.einsum("nld,lkd->nk", v, d) / (hi - lo + 1)


def fit_dim(vecs: np.ndarray, labels: np.ndarray) -> np.ndarray:
    v = vecs.astype(np.float32)
    return unit(v[labels].mean(axis=0) - v[~labels].mean(axis=0))


# ---------------------------------------------------------------------------
# K1 arming decomposition
# ---------------------------------------------------------------------------

def grid_index(n_items: int) -> dict[str, np.ndarray]:
    """Row indices into the (n_items * len(GRID_CELLS)) grid, by cell name."""
    return {c: np.arange(n_items) * len(GRID_CELLS) + k for k, c in enumerate(GRID_CELLS)}


def k1_terms(s: dict[str, np.ndarray], fam: str = "F1") -> dict[str, np.ndarray]:
    """s[cell] -> (n_items,) projections.  Returns per-item O, CB, A, T."""
    hh = s[f"saf|{fam}|H|haz"]
    hb = s[f"saf|{fam}|H|ben"]
    bh = s[f"saf|{fam}|B|haz"]
    bb = s[f"saf|{fam}|B|ben"]
    O = 0.5 * ((hh + hb) - (bh + bb))
    CB = bh - bb
    A = (hh - hb) - (bh - bb)
    T = CB + A
    return {"O": O, "CB": CB, "A": A, "T": T}


def coherence_interaction(s: dict[str, np.ndarray]) -> np.ndarray:
    aa = s["coh|F1|A|A"]
    ab = s["coh|F1|A|B"]
    ba = s["coh|F1|B|A"]
    bb = s["coh|F1|B|B"]
    # the 2x2 interaction, same algebraic shape as K1's A
    return (aa - ab) - (ba - bb)


# ---------------------------------------------------------------------------
# null machinery
# ---------------------------------------------------------------------------

def null_sd_per_item(contrast_fn, s_rand: dict[str, np.ndarray]) -> tuple[float, float]:
    """PER-ITEM null SD: sqrt(mean_i[var_d(c_{i,d})]).  n-independent by construction.

    Returns (per_item_null_sd, pooled_null_sd).  `s_rand[cell]` is (n_items, K).
    """
    c = contrast_fn(s_rand)                      # (n_items, K)
    per_item = float(np.sqrt(np.nanmean(np.nanvar(c, axis=1, ddof=1))))
    pooled = float(np.nanstd(c.ravel(), ddof=1))
    return per_item, pooled


def shuffled_label_band(fit_vecs: np.ndarray, fit_labels: np.ndarray,
                        eval_vecs: dict[str, np.ndarray], band: tuple[int, int],
                        contrast_fn, *, n: int = N_SHUFFLE, seed: int = 7,
                        null_sd: float = 1.0) -> dict[str, Any]:
    """Permute hazardous/benign labels in the FITTING corpus, refit, push the whole
    pipeline through.  The null band is the central 95% of the resulting term values."""
    rng = np.random.default_rng(seed)
    terms = []
    for _ in range(n):
        lab = rng.permutation(fit_labels)
        r = fit_dim(fit_vecs, lab)
        s = {c: project(v, r, band) for c, v in eval_vecs.items()}
        terms.append(float(np.nanmean(contrast_fn(s))) / null_sd)
    t = np.asarray(terms)
    return {"terms": t.tolist(), "mean": float(t.mean()), "sd": float(t.std(ddof=1)),
            "lo95": float(np.percentile(t, 2.5)), "hi95": float(np.percentile(t, 97.5)),
            "abs_p975": float(np.percentile(np.abs(t), 97.5))}


def standardised(vals: np.ndarray, null_sd: float, *, seed: int = 0) -> dict[str, Any]:
    v = np.asarray(vals, dtype=np.float64)
    v = v[np.isfinite(v)]
    n = len(v)
    if n == 0 or null_sd <= 0:
        return {"n": n, "term_raw": float("nan"), "term_std": float("nan")}
    std_vals = v / null_sd
    m, lo, hi, _ = boot_ci(std_vals, seed=seed)
    r = float(std_vals.std(ddof=1))
    return {
        "n": n,
        "term_raw": float(v.mean()),
        "term_std": m,
        "ci95": [lo, hi],
        "achieved_r": r,
        "se": r / math.sqrt(n),
        "mde_1.96se": 1.96 * r / math.sqrt(n),
        "per_item_quantiles": {q: float(np.percentile(std_vals, q)) for q in (5, 25, 50, 75, 95)},
        "sign_stable": bool(lo * hi > 0),
    }


# ---------------------------------------------------------------------------
# K4 exponential persistence fit
# ---------------------------------------------------------------------------

def fit_tau(d: np.ndarray) -> dict[str, Any]:
    """d(t) = a*exp(-t/tau) + c, tau in tokens.  Falls back to a half-life crossing."""
    from scipy.optimize import curve_fit
    t = np.arange(len(d), dtype=np.float64)
    ok = np.isfinite(d)
    if ok.sum() < 5:
        return {"tau": None, "r2": None, "method": "insufficient_data"}

    def f(x, a, tau, c):
        return a * np.exp(-x / tau) + c

    try:
        p0 = [float(d[ok][0] - d[ok][-1]), 20.0, float(d[ok][-1])]
        popt, _ = curve_fit(f, t[ok], d[ok], p0=p0,
                            bounds=([-np.inf, 0.5, -np.inf], [np.inf, 500.0, np.inf]),
                            maxfev=20000)
        pred = f(t[ok], *popt)
        ss_res = float(((d[ok] - pred) ** 2).sum())
        ss_tot = float(((d[ok] - d[ok].mean()) ** 2).sum())
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    except (RuntimeError, ValueError) as e:
        return {"tau": None, "r2": None, "method": f"fit_failed:{type(e).__name__}"}
    out = {"tau": float(popt[1]), "a": float(popt[0]), "c": float(popt[2]),
           "r2": float(r2), "method": "exponential"}
    if not np.isfinite(r2) or r2 < 0.3:
        d0 = float(d[ok][0])
        cross = None
        for i in range(len(d)):
            if np.isfinite(d[i]) and abs(d[i]) < 0.5 * abs(d0):
                cross = int(i)
                break
        out.update({"tau": None, "tau_undefined_reason": "R2<0.3",
                    "half_life_crossing": cross, "method": "half_life_fallback"})
    return out


# ---------------------------------------------------------------------------
# baselines
# ---------------------------------------------------------------------------

def probe_auroc(X: np.ndarray, y: np.ndarray, *, folds: int = 5, seed: int = 0) -> dict[str, float]:
    """B2 -- cross-validated logistic probe on RAW pooled band vectors (non-featurised).

    The handbook's required ceiling baseline: a supervised probe on the same activations.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y).astype(int)
    if len(np.unique(y)) < 2 or len(y) < folds * 2:
        return {"auroc": float("nan"), "n": int(len(y))}
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    scores = np.zeros(len(y), dtype=np.float64)
    for tr, te in skf.split(X, y):
        clf = make_pipeline(StandardScaler(),
                            LogisticRegression(max_iter=2000, C=1.0))
        clf.fit(X[tr], y[tr])
        scores[te] = clf.predict_proba(X[te])[:, 1]
    return {"auroc": auroc(scores[y == 1], scores[y == 0]), "n": int(len(y))}


def fisher_ratio(a: np.ndarray, b: np.ndarray) -> float:
    """B3 -- between/within scatter ratio of two activation clusters at the band."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if len(a) < 2 or len(b) < 2:
        return float("nan")
    mu_a, mu_b = a.mean(0), b.mean(0)
    between = float(((mu_a - mu_b) ** 2).sum())
    within = float(((a - mu_a) ** 2).sum(1).mean() + ((b - mu_b) ** 2).sum(1).mean())
    return between / within if within > 0 else float("nan")


def silhouette_two(a: np.ndarray, b: np.ndarray, *, seed: int = 0, cap: int = 400) -> float:
    from sklearn.metrics import silhouette_score
    rng = np.random.default_rng(seed)
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    if len(a) > cap:
        a = a[rng.choice(len(a), cap, replace=False)]
    if len(b) > cap:
        b = b[rng.choice(len(b), cap, replace=False)]
    X = np.vstack([a, b])
    y = np.array([0] * len(a) + [1] * len(b))
    if len(np.unique(y)) < 2 or len(y) < 3:
        return float("nan")
    return float(silhouette_score(X, y))


__all__ = [
    "BOOT_B", "N_RAND_DIRS", "N_SHUFFLE", "BAND_WIDTH", "SAFETY_CELLS", "COH_CELLS",
    "GRID_CELLS", "cohens_d", "auroc", "boot_ci", "paired_boot_ci", "tost", "holm",
    "unit", "Ckpt", "load_ckpt", "project", "project_multi", "fit_dim", "grid_index",
    "k1_terms", "coherence_interaction", "null_sd_per_item", "shuffled_label_band",
    "standardised", "fit_tau", "probe_auroc", "fisher_ratio", "silhouette_two",
]
