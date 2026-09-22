"""All candidate / baseline / null mathematics for iteration-2 Lane A.

PURE NUMPY over the cached sufficient statistics written by harvest.py.  This is
design decision D1: no candidate, no baseline, no shuffled-label draw and no point of
the prompt-budget curve ever costs a second forward pass.

Two Gram identities (D2) make the weight side collapse to one cached matrix per layer:
    ||u^T M||^2 = u^T (M M^T) u = u^T G u          -> X2 write mass, any direction, free
    sigma_min(M)^2 = lambda_min(M M^T)             -> X10 scar, from the same G
"""

from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

EPS = 1e-12


# ----------------------------------------------------------------------------------
# basic separability
# ----------------------------------------------------------------------------------
def unit(v: np.ndarray, axis: int = -1) -> np.ndarray:
    n = np.linalg.norm(v, axis=axis, keepdims=True)
    return v / np.maximum(n, EPS)


def auroc(scores: np.ndarray, y: np.ndarray) -> float:
    """Rank-based AUROC with tie correction. y in {0,1}."""
    scores = np.asarray(scores, dtype=np.float64).ravel()
    y = np.asarray(y).ravel().astype(int)
    n1 = int((y == 1).sum())
    n0 = int((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    sorted_scores = scores[order]
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i : j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def tpr_at_fpr(scores: np.ndarray, y: np.ndarray, fpr_level: float) -> float:
    """TPR at a target FPR, threshold taken from the NEGATIVE class quantile.

    Conservative: the threshold is the smallest score t such that
    mean(neg >= t) <= fpr_level, then TPR = mean(pos >= t).
    """
    scores = np.asarray(scores, dtype=np.float64).ravel()
    y = np.asarray(y).ravel().astype(int)
    neg = scores[y == 0]
    pos = scores[y == 1]
    if neg.size == 0 or pos.size == 0:
        return float("nan")
    thr = float(np.quantile(neg, 1.0 - fpr_level, method="higher"))
    # nudge above ties so the realised FPR does not exceed the level
    above = neg[neg > thr]
    if (neg >= thr).mean() > fpr_level and above.size:
        thr = float(above.min())
    return float((pos >= thr).mean())


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    if a.size < 2 or b.size < 2:
        return float("nan")
    va, vb = a.var(ddof=1), b.var(ddof=1)
    sp = np.sqrt(((a.size - 1) * va + (b.size - 1) * vb) / max(a.size + b.size - 2, 1))
    if sp < EPS:
        return float("nan")
    return float((a.mean() - b.mean()) / sp)


def fisher_ratio(scores: np.ndarray, y: np.ndarray) -> float:
    """BL4: between-class over within-class scatter of the 1-D projection."""
    s = np.asarray(scores, dtype=np.float64).ravel()
    y = np.asarray(y).ravel().astype(int)
    a, b = s[y == 1], s[y == 0]
    if a.size < 2 or b.size < 2:
        return float("nan")
    within = a.var(ddof=1) + b.var(ddof=1)
    if within < EPS:
        return float("nan")
    return float((a.mean() - b.mean()) ** 2 / within)


def silhouette_1d(scores: np.ndarray, y: np.ndarray) -> float:
    """Mean silhouette of the two label groups on the 1-D projection (cheap, exact)."""
    s = np.asarray(scores, dtype=np.float64).ravel()
    y = np.asarray(y).ravel().astype(int)
    out = np.empty(s.size, dtype=np.float64)
    for k in range(s.size):
        same = s[(y == y[k])]
        other = s[(y != y[k])]
        if same.size < 2 or other.size == 0:
            out[k] = 0.0
            continue
        a = np.abs(same - s[k]).sum() / (same.size - 1)
        b = np.abs(other - s[k]).mean()
        out[k] = (b - a) / max(a, b, EPS)
    return float(out.mean())


def _folds(y: np.ndarray, n_splits: int, seed: int, groups: np.ndarray | None = None):
    """Stratified folds; GROUP-aware when `groups` carries duplicates.

    An item-level bootstrap resamples prompts WITH replacement, so the same prompt can
    appear twice. A plain StratifiedKFold would then put one copy in the training fold and
    the other in the test fold, and a cross-fitted AUROC would read an in-sample number.
    Passing the ORIGINAL item index as `groups` keeps every copy of a prompt on one side.
    """
    from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

    y = np.asarray(y).astype(int)
    n_min = int(min((y == 0).sum(), (y == 1).sum()))
    if groups is not None and len(np.unique(groups)) < len(groups):
        g = np.asarray(groups)
        ug1 = len(np.unique(g[y == 1]))
        ug0 = len(np.unique(g[y == 0]))
        k = int(max(2, min(n_splits, ug1, ug0)))
        skf = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed)
        return list(skf.split(np.zeros(len(y)), y, g))
    k = int(max(2, min(n_splits, n_min)))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
    return list(skf.split(np.zeros(len(y)), y))


# ----------------------------------------------------------------------------------
# the harm axis u (parent-free, refit on the checkpoint's own activations)
# ----------------------------------------------------------------------------------
def diffmeans_directions(A: np.ndarray, y: np.ndarray) -> np.ndarray:
    """A : [N, L1, d] float -> u : [L1, d] unit, pointing benign -> harmful."""
    A = np.asarray(A, dtype=np.float32)
    y = np.asarray(y).astype(int)
    m1 = A[y == 1].mean(axis=0)
    m0 = A[y == 0].mean(axis=0)
    return unit(m1 - m0, axis=-1).astype(np.float32)


def project(A: np.ndarray, U: np.ndarray) -> np.ndarray:
    """A : [N, L1, d], U : [L1, d] -> p : [N, L1]."""
    return np.einsum("nld,ld->nl", A.astype(np.float32), U.astype(np.float32))


def split_half_cosine(
    A: np.ndarray, y: np.ndarray, layer: int, n_rep: int = 20, seed: int = 0
) -> float:
    """DIRECTION-STABILITY GATE.  Mean |cos| between diff-in-means fits on disjoint halves."""
    rng = np.random.default_rng(seed)
    idx1 = np.flatnonzero(y == 1)
    idx0 = np.flatnonzero(y == 0)
    if idx1.size < 4 or idx0.size < 4:
        return float("nan")
    cos = []
    Al = np.asarray(A[:, layer, :], dtype=np.float32)
    for _ in range(n_rep):
        p1, p0 = rng.permutation(idx1), rng.permutation(idx0)
        h1a, h1b = p1[: idx1.size // 2], p1[idx1.size // 2 :]
        h0a, h0b = p0[: idx0.size // 2], p0[idx0.size // 2 :]
        ua = unit(Al[h1a].mean(0) - Al[h0a].mean(0))
        ub = unit(Al[h1b].mean(0) - Al[h0b].mean(0))
        cos.append(abs(float(ua @ ub)))
    return float(np.mean(cos))


def logistic_probe_direction(
    A_layer: np.ndarray, y: np.ndarray, seed: int = 0, C_grid: Sequence[float] = (0.01, 0.1, 1.0),
    groups: np.ndarray | None = None,
) -> np.ndarray:
    """Fallback PRIMARY axis when the split-half gate fails: CV logistic weight vector.

    C is chosen on an INNER fold only (leakage audit T5c).
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    X = np.asarray(A_layer, dtype=np.float64)
    y = np.asarray(y).astype(int)
    best_C, best = C_grid[0], -np.inf
    inner_folds = _folds(y, 3, seed, groups)
    for C in C_grid:
        sc = []
        for tr, te in inner_folds:
            ss = StandardScaler().fit(X[tr])
            clf = LogisticRegression(C=C, max_iter=400, solver="lbfgs").fit(ss.transform(X[tr]), y[tr])
            sc.append(auroc(clf.decision_function(ss.transform(X[te])), y[te]))
        m = float(np.nanmean(sc)) if sc else -np.inf
        if m > best:
            best, best_C = m, C
    ss = StandardScaler().fit(X)
    clf = LogisticRegression(C=best_C, max_iter=600, solver="lbfgs").fit(ss.transform(X), y)
    w = clf.coef_.ravel() / np.maximum(ss.scale_, EPS)
    u = unit(w).astype(np.float32)
    if float(u @ (X[y == 1].mean(0) - X[y == 0].mean(0))) < 0:
        u = -u
    return u


def cv_auroc_per_layer(
    A: np.ndarray, y: np.ndarray, n_splits: int = 5, seed: int = 0, C_grid=(0.01, 0.1, 1.0)
) -> np.ndarray:
    """Cross-validated probe AUROC at every layer. Used for l_dec and for R."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    y = np.asarray(y).astype(int)
    L1 = A.shape[1]
    out = np.full(L1, np.nan, dtype=np.float64)
    n_min = int(min((y == 0).sum(), (y == 1).sum()))
    k = int(max(2, min(n_splits, n_min)))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
    folds = list(skf.split(np.zeros(len(y)), y))
    for l in range(L1):
        X = np.asarray(A[:, l, :], dtype=np.float64)
        sc = np.full(len(y), np.nan)
        for tr, te in folds:
            ytr = y[tr]
            if len(np.unique(ytr)) < 2:
                continue
            # inner-fold choice of C -- never the test fold (leakage audit T5c)
            bC, bv = C_grid[0], -np.inf
            kk = int(max(2, min(3, int(min((ytr == 0).sum(), (ytr == 1).sum())))))
            inner = StratifiedKFold(n_splits=kk, shuffle=True, random_state=seed + 1)
            for C in C_grid:
                vs = []
                for itr, ite in inner.split(np.zeros(len(ytr)), ytr):
                    if len(np.unique(ytr[itr])) < 2:
                        continue
                    ss = StandardScaler().fit(X[tr][itr])
                    clf = LogisticRegression(C=C, max_iter=300, solver="lbfgs").fit(
                        ss.transform(X[tr][itr]), ytr[itr]
                    )
                    vs.append(auroc(clf.decision_function(ss.transform(X[tr][ite])), ytr[ite]))
                v = float(np.nanmean(vs)) if vs else -np.inf
                if v > bv:
                    bv, bC = v, C
            ss = StandardScaler().fit(X[tr])
            clf = LogisticRegression(C=bC, max_iter=400, solver="lbfgs").fit(ss.transform(X[tr]), ytr)
            sc[te] = clf.decision_function(ss.transform(X[te]))
        out[l] = auroc(sc[~np.isnan(sc)], y[~np.isnan(sc)]) if np.isfinite(sc).any() else np.nan
    return out


def cv_probe_scores(
    A_layer: np.ndarray, y: np.ndarray, n_splits: int = 5, seed: int = 0, C_grid=(0.01, 0.1, 1.0)
) -> np.ndarray:
    """Out-of-fold decision scores at one layer (for R_TPR / BL2)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    X = np.asarray(A_layer, dtype=np.float64)
    y = np.asarray(y).astype(int)
    n_min = int(min((y == 0).sum(), (y == 1).sum()))
    k = int(max(2, min(n_splits, n_min)))
    skf = StratifiedKFold(n_splits=k, shuffle=True, random_state=seed)
    sc = np.full(len(y), np.nan)
    for tr, te in skf.split(X, y):
        ytr = y[tr]
        if len(np.unique(ytr)) < 2:
            continue
        bC, bv = C_grid[0], -np.inf
        kk = int(max(2, min(3, int(min((ytr == 0).sum(), (ytr == 1).sum())))))
        inner = StratifiedKFold(n_splits=kk, shuffle=True, random_state=seed + 1)
        for C in C_grid:
            vs = []
            for itr, ite in inner.split(X[tr], ytr):
                if len(np.unique(ytr[itr])) < 2:
                    continue
                ss = StandardScaler().fit(X[tr][itr])
                clf = LogisticRegression(C=C, max_iter=300, solver="lbfgs").fit(
                    ss.transform(X[tr][itr]), ytr[itr]
                )
                vs.append(auroc(clf.decision_function(ss.transform(X[tr][ite])), ytr[ite]))
            v = float(np.nanmean(vs)) if vs else -np.inf
            if v > bv:
                bv, bC = v, C
        ss = StandardScaler().fit(X[tr])
        clf = LogisticRegression(C=bC, max_iter=400, solver="lbfgs").fit(ss.transform(X[tr]), ytr)
        sc[te] = clf.decision_function(ss.transform(X[te]))
    return sc


# ----------------------------------------------------------------------------------
# X1 ACCUMULATOR GAIN
# ----------------------------------------------------------------------------------
def x1_accumulator_gain(
    P: np.ndarray, y: np.ndarray, norms: np.ndarray, auroc_layer: np.ndarray, thr: float = 0.95
) -> dict:
    """P:[N,L1] projections, norms:[L1] mean ||A[:,l,:]||, auroc_layer:[L1] CV AUROC."""
    y = np.asarray(y).astype(int)
    gap = P[y == 1].mean(0) - P[y == 0].mean(0)
    g = gap / np.maximum(norms, EPS)
    if not np.isfinite(np.asarray(auroc_layer, dtype=float)).any():
        # no layer is scorable at this sample size: X1 (and the X8 lag, which needs l_dec) are
        # UNDEFINED rather than a crash that would take every other candidate down with them
        return {"X1": float("nan"), "X1_raw": float("nan"), "l_dec": None, "l_peak": None,
                "f_dec": float("nan"), "x1_no_decodable_layer": True,
                "g_curve": g.tolist(), "gap_curve": gap.tolist()}
    ok = np.flatnonzero(np.nan_to_num(auroc_layer, nan=-1.0) >= thr)
    no_dec = ok.size == 0
    l_dec = int(ok[0]) if not no_dec else int(np.nanargmax(auroc_layer))
    tail = slice(l_dec, len(g))
    l_peak = int(l_dec + np.argmax(g[tail]))
    val = float(np.clip(np.log10(max(g[l_peak], EPS) / max(g[l_dec], 1e-6)), -3.0, 6.0))
    l_peak_raw = int(l_dec + np.argmax(gap[tail]))
    val_raw = float(np.clip(np.log10(max(gap[l_peak_raw], EPS) / max(gap[l_dec], 1e-6)), -3.0, 6.0))
    return {
        "X1": val,
        "X1_raw": val_raw,
        "l_dec": l_dec,
        "l_peak": l_peak,
        "f_dec": float(l_dec / max(len(g) - 1, 1)),
        "x1_no_decodable_layer": bool(no_dec),
        "g_curve": g.tolist(),
        "gap_curve": gap.tolist(),
    }


# ----------------------------------------------------------------------------------
# X2 WRITE MASS  (quadratic form over the cached Gram)
# ----------------------------------------------------------------------------------
def write_mass(G: np.ndarray, fro2: float, u: np.ndarray, d: int) -> float:
    """d * (u^T G u) / ||M||_F^2 .  Expectation 1.0 for a random unit u, any d.

    G is consumed in its stored dtype (float32 after CkptCache casts it once); the
    accumulation of the quadratic form is done in float64 by np.dot's internal promotion of
    the final reduction, and T1a verifies the normalisation reads 1.00 +/- 0.05.
    """
    u32 = np.asarray(u, dtype=np.float32).ravel()
    q = float(np.dot(u32, np.asarray(G, dtype=np.float32) @ u32))
    return float(d * q / max(float(fro2), EPS))


def write_mass_many(G: np.ndarray, fro2: float, U: np.ndarray, d: int) -> np.ndarray:
    """U:[k,d] -> [k] write masses. One GEMM, so 20 nulls cost the same as one direction."""
    U = np.asarray(U, dtype=np.float32)
    GU = np.asarray(G, dtype=np.float32) @ U.T           # [d,k]
    q = np.einsum("kd,dk->k", U, GU).astype(np.float64)
    return d * q / max(float(fro2), EPS)


def x2_from_curve(wm_curve: np.ndarray, band: Sequence[int]) -> dict:
    wm = np.asarray(wm_curve, dtype=np.float64)
    b = np.asarray(band, dtype=int)
    b = b[(b >= 0) & (b < wm.size)]
    if b.size == 0:
        b = np.arange(wm.size)
    lg = np.log10(np.maximum(wm, EPS))
    return {
        "X2": float(np.mean(lg[b])),
        "X2_min": float(np.min(lg)),
        "X2_argmin_layer": int(np.argmin(lg)),
        "wm_curve": wm.tolist(),
    }


# ----------------------------------------------------------------------------------
# X3 PERCEPT-TO-REFUSAL GAIN  (closed form -- no forward pass, so nulls are free)
# ----------------------------------------------------------------------------------
def rmsnorm_jacobian_apply(
    h: np.ndarray, u: np.ndarray, gamma: np.ndarray, eps: float
) -> np.ndarray:
    """J(h) u for y = gamma * h / sqrt(mean(h^2) + eps), evaluated at h."""
    h = np.asarray(h, dtype=np.float64).ravel()
    u = np.asarray(u, dtype=np.float64).ravel()
    g = np.asarray(gamma, dtype=np.float64).ravel()
    d = h.size
    s = float(np.sqrt(np.mean(h * h) + eps))
    return g * (u / s - h * float(h @ u) / (d * s**3))


def x3_gain(
    u: np.ndarray,
    hbar: np.ndarray,
    gamma: np.ndarray,
    rms_eps: float,
    WU_ref: np.ndarray,
    WU_hed: np.ndarray,
    WU_ctl: np.ndarray,
    mu_U: np.ndarray,
    S_U: np.ndarray,
    V: int,
) -> dict:
    Ju = rmsnorm_jacobian_apply(hbar, u, gamma, rms_eps)
    dref = np.asarray(WU_ref, dtype=np.float64) @ Ju
    dhed = np.asarray(WU_hed, dtype=np.float64) @ Ju
    dctl = np.asarray(WU_ctl, dtype=np.float64) @ Ju
    mean_V = float(np.asarray(mu_U, dtype=np.float64) @ Ju)
    E2_V = float(Ju @ (np.asarray(S_U, dtype=np.float64) @ Ju)) / float(V)
    sd_V = float(np.sqrt(max(E2_V - mean_V**2, 1e-12)))
    x3 = (float(dref.mean()) - float(dctl.mean())) / sd_V
    x3h = (float(dhed.mean()) - float(dctl.mean())) / sd_V
    both = np.concatenate([dref, dhed])
    return {
        "X3": float(x3),
        "X3_hedge": float(x3h),
        "X3_two_way": float(x3 - x3h),
        "X3_exec": float((float(both.mean()) - float(dctl.mean())) / sd_V),
        "sd_V": sd_V,
    }


def x3_gain_many(
    U: np.ndarray, hbar, gamma, rms_eps, WU_ref, WU_hed, WU_ctl, mu_U, S_U, V
) -> np.ndarray:
    """Vectorised over k directions so 20 shuffled nulls are one call."""
    return np.array(
        [x3_gain(U[k], hbar, gamma, rms_eps, WU_ref, WU_hed, WU_ctl, mu_U, S_U, V)["X3"]
         for k in range(U.shape[0])],
        dtype=np.float64,
    )


# ----------------------------------------------------------------------------------
# X5 ROUTING CONCENTRATION
# ----------------------------------------------------------------------------------
def x5_concentration(
    D_resp: np.ndarray,
    u_star: np.ndarray,
    band: Sequence[int],
    onset: int = 3,
    n_pos: int | None = None,
) -> np.ndarray:
    """D_resp : [C, L, P, d] per-position residual writes -> conc per cell, shape [C].

    conc = (S_onset/S_all) / (onset/P);  1.0 == flat over positions.
    """
    C, L, P, _ = D_resp.shape
    P = int(n_pos or P)
    b = np.asarray(band, dtype=int)
    b = b[(b >= 0) & (b < L)]
    if b.size == 0:
        b = np.arange(L)
    # slice BEFORE the float32 cast: only the band layers and the first P positions are read
    D = np.asarray(D_resp[:, b, :P, :], dtype=np.float32)
    flow = np.abs(np.einsum("clpd,d->clp", D, np.asarray(u_star, dtype=np.float32)))
    s_on = flow[:, :, :onset].sum(axis=(1, 2))
    s_all = flow.sum(axis=(1, 2))
    return (s_on / np.maximum(s_all, EPS)) / (onset / float(P))


# ----------------------------------------------------------------------------------
# X8 EXECUTION DEPTH MARGIN
# ----------------------------------------------------------------------------------
def moving_average(x: np.ndarray, w: int = 3) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    if w <= 1 or x.size < w:
        return x.copy()
    pad = w // 2
    xp = np.pad(x, (pad, pad), mode="edge")
    k = np.ones(w) / w
    return np.convolve(xp, k, mode="valid")[: x.size]


def x8_depth_margin(
    r_ref: np.ndarray, r_ctrl: np.ndarray, y: np.ndarray, l_dec: int, smooth_w: int = 3
) -> dict:
    """r_* : [N, L1] logit-lens drives.  X8 = (l_act - l_dec)/L, unit-free by construction."""
    y = np.asarray(y).astype(int)
    drv = np.asarray(r_ref, dtype=np.float64) - np.asarray(r_ctrl, dtype=np.float64)
    gap = drv[y == 1].mean(0) - drv[y == 0].mean(0)
    sm = moving_average(gap, smooth_w)
    grad = np.diff(sm, prepend=sm[0])
    l_act = int(np.argmax(grad))
    L = max(len(gap) - 1, 1)
    return {
        "X8": float((l_act - l_dec) / L),
        "l_act": l_act,
        "f_act": float(l_act / L),
        "f_dec": float(l_dec / L),
        "drive_gap_curve": gap.tolist(),
    }


# ----------------------------------------------------------------------------------
# X10 WEIGHTS-ONLY ORTHOGONALITY SCAR  (ZERO PROMPTS)
# ----------------------------------------------------------------------------------
def sigma_mp_analytic(fro2: float, d: int, n: int) -> float:
    """Marchenko-Pastur smallest singular value for a Gaussian matrix of the SAME shape
    AND the same Frobenius norm.  M is [d, n] with n >= d."""
    dd, nn = float(min(d, n)), float(max(d, n))
    scale = np.sqrt(max(float(fro2), EPS) / (dd * nn))
    return float(scale * (np.sqrt(nn) - np.sqrt(dd)))


def x10_scar(
    svals_per_layer: list[np.ndarray],
    fro2_per_layer: Sequence[float],
    shapes: Sequence[tuple[int, int]],
    sigma_mp_override: Sequence[float] | None = None,
) -> dict:
    scar, smp, smin = [], [], []
    for l, sv in enumerate(svals_per_layer):
        sv = np.asarray(sv, dtype=np.float64)
        d, n = shapes[l]
        mp = (
            float(sigma_mp_override[l])
            if sigma_mp_override is not None
            else sigma_mp_analytic(fro2_per_layer[l], d, n)
        )
        s_min = float(max(sv[-1], 1e-12))
        smp.append(mp)
        smin.append(s_min)
        scar.append(float(np.log10(max(mp, EPS) / s_min)))
    scar = np.asarray(scar, dtype=np.float64)
    med = float(np.median(scar))
    mad = float(np.median(np.abs(scar - med)))
    denom = 1.4826 * mad
    z = (scar - med) / denom if denom > EPS else np.zeros_like(scar)
    return {
        "X10": float(np.max(z)) if z.size else float("nan"),
        "X10_abs": float(np.max(scar)) if scar.size else float("nan"),
        "X10_argmax_layer": int(np.argmax(z)) if z.size else -1,
        "scar_curve": scar.tolist(),
        "z_curve": z.tolist(),
        "sigma_min_curve": smin,
        "sigma_mp_curve": smp,
        "scar_median": med,
        "scar_mad": mad,
        "degenerate_mad": bool(denom <= EPS),
    }


# ----------------------------------------------------------------------------------
# X9 BENIGN-ONLY FOOTPRINT (parent-free)   /   X11 ARMING INTERACTION
# ----------------------------------------------------------------------------------
def x9_benign_footprint(A_benign_layer: np.ndarray, n_rand: int = 20, seed: int = 0) -> dict:
    """Top-1 PC variance share on BENIGN prompts only, against a matched random subspace.

    No harmful text anywhere -- the point of the candidate.
    """
    X = np.asarray(A_benign_layer, dtype=np.float64)
    if X.shape[0] < 3:
        return {"X9": float("nan"), "pc1_share": float("nan"), "rand_share": float("nan")}
    Xc = X - X.mean(0, keepdims=True)
    tot = float((Xc**2).sum())
    if tot < EPS:
        return {"X9": float("nan"), "pc1_share": float("nan"), "rand_share": float("nan")}
    # top singular value via a few power iterations on the Gram of the small side
    Gm = Xc @ Xc.T
    ev = np.linalg.eigvalsh(Gm)
    pc1 = float(ev[-1] / tot)
    rng = np.random.default_rng(seed)
    d = Xc.shape[1]
    shares = []
    for _ in range(n_rand):
        v = unit(rng.standard_normal(d))
        shares.append(float(((Xc @ v) ** 2).sum() / tot))
    rs = float(np.mean(shares))
    return {
        "X9": float(np.log10(max(pc1, EPS) / max(rs, EPS))),
        "pc1_share": pc1,
        "rand_share": rs,
    }


def x11_arming(
    s: np.ndarray,
    req_level: np.ndarray,
    pfx_level: np.ndarray,
    item_uid: np.ndarray,
) -> dict:
    """A = (s_haz,hazreq - s_ben,hazreq) - (s_haz,benreq - s_ben,benreq), paired per item."""
    req = np.asarray(req_level)
    pfx = np.asarray(pfx_level)
    uid = np.asarray(item_uid)
    per = []
    for it in np.unique(uid):
        m = uid == it
        def cell(r: str, p: str) -> float:
            k = m & (req == r) & (pfx == p)
            return float(np.mean(s[k])) if k.any() else np.nan
        a = (cell("harmful", "hazardous") - cell("harmful", "benign")) - (
            cell("benign_twin", "hazardous") - cell("benign_twin", "benign")
        )
        if np.isfinite(a):
            per.append(a)
    per = np.asarray(per, dtype=np.float64)
    return {
        "X11": float(per.mean()) if per.size else float("nan"),
        "X11_n_items": int(per.size),
        "X11_per_item": per.tolist(),
    }


# ----------------------------------------------------------------------------------
# BL6 HRCI_repr  (arXiv:2606.16349 Eq 9, reimplementation -- k and subspace protocol OURS)
# ----------------------------------------------------------------------------------
def hrci_repr(
    A_layer: np.ndarray,
    y: np.ndarray,
    r_refuse: np.ndarray,
    k: int = 8,
    seed: int = 0,
) -> dict:
    """0.5 * C_cos + 0.5 * C_sub.

    C_cos = |cos(r_harm, r_refuse)|
    C_sub = mean squared canonical correlation between the top-k PCs of the local
            harmfulness subspace and the local refusal subspace.
    """
    X = np.asarray(A_layer, dtype=np.float64)
    y = np.asarray(y).astype(int)
    r_h = unit(X[y == 1].mean(0) - X[y == 0].mean(0))
    r_r = unit(np.asarray(r_refuse, dtype=np.float64).ravel())
    c_cos = abs(float(r_h @ r_r))

    def topk_basis(M: np.ndarray, kk: int) -> np.ndarray:
        Mc = M - M.mean(0, keepdims=True)
        kk = int(min(kk, min(Mc.shape) - 1))
        if kk < 1:
            return np.zeros((M.shape[1], 0))
        # right singular vectors via the (small) Gram on the sample side
        G = Mc @ Mc.T
        w, V = np.linalg.eigh(G)
        idx = np.argsort(w)[::-1][:kk]
        B = (Mc.T @ V[:, idx]) / np.maximum(np.sqrt(np.maximum(w[idx], EPS)), EPS)
        q, _ = np.linalg.qr(B)
        return q

    B_h = topk_basis(X[y == 1], k)
    B_r_src = X[y == 0] if (y == 0).sum() >= 3 else X
    B_r = topk_basis(B_r_src, k)
    if B_h.shape[1] == 0 or B_r.shape[1] == 0:
        c_sub = float("nan")
    else:
        # canonical correlations between two orthonormal bases == singular values of B_h^T B_r
        sv = np.linalg.svd(B_h.T @ B_r, compute_uv=False)
        c_sub = float(np.mean(np.clip(sv, 0.0, 1.0) ** 2))
    val = 0.5 * c_cos + 0.5 * (c_sub if np.isfinite(c_sub) else 0.0)
    return {"BL6_HRCI": float(val), "C_cos": c_cos, "C_sub": c_sub, "k": int(k)}


# ----------------------------------------------------------------------------------
# resampling / inference
# ----------------------------------------------------------------------------------
def bootstrap_ci(
    values: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = 0, stat=np.mean
) -> tuple[float, float, float]:
    v = np.asarray(values, dtype=np.float64)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan"), float("nan"), float("nan")
    if v.size == 1:
        return float(v[0]), float(v[0]), float(v[0])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, v.size, size=(n_boot, v.size))
    draws = stat(v[idx], axis=1)
    return (
        float(stat(v)),
        float(np.quantile(draws, alpha / 2)),
        float(np.quantile(draws, 1 - alpha / 2)),
    )


def paired_bootstrap_diff_ci(
    a: np.ndarray, b: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float, float]:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    n = min(a.size, b.size)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    d = a[:n] - b[:n]
    draws = d[idx].mean(axis=1)
    return float(d.mean()), float(np.quantile(draws, alpha / 2)), float(np.quantile(draws, 1 - alpha / 2))


def cluster_bootstrap_ci(
    values: np.ndarray, clusters: np.ndarray, n_boot: int = 2000, alpha: float = 0.05, seed: int = 0
) -> tuple[float, float, float]:
    """Family-clustered bootstrap: resample CLUSTERS, not rows."""
    v = np.asarray(values, dtype=np.float64)
    c = np.asarray(clusters)
    ok = np.isfinite(v)
    v, c = v[ok], c[ok]
    if v.size == 0:
        return float("nan"), float("nan"), float("nan")
    uniq = list(dict.fromkeys(c.tolist()))
    groups = [np.flatnonzero(c == g) for g in uniq]
    if len(groups) < 2:
        return bootstrap_ci(v, n_boot, alpha, seed)
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    for b in range(n_boot):
        pick = rng.integers(0, len(groups), size=len(groups))
        sel = np.concatenate([groups[i] for i in pick])
        draws[b] = v[sel].mean()
    return float(v.mean()), float(np.quantile(draws, alpha / 2)), float(np.quantile(draws, 1 - alpha / 2))


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 3:
        return float("nan")
    from scipy.stats import rankdata

    ra, rb = rankdata(a), rankdata(b)
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    den = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / den) if den > EPS else float("nan")


def exact_permutation_p(a: np.ndarray, b: np.ndarray, max_exact: int = 40320) -> dict:
    """Exact (or exhaustively-sampled) permutation p for Spearman rho at small n."""
    import itertools
    import math

    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    n = a.size
    if n < 3:
        return {"rho": float("nan"), "p": float("nan"), "n": int(n), "exact": False,
                "critical_abs_rho_p05": float("nan")}
    obs = spearman(a, b)
    rhos = []
    if math.factorial(n) <= max_exact:
        for perm in itertools.permutations(range(n)):
            rhos.append(spearman(a, b[list(perm)]))
        exact = True
    else:
        rng = np.random.default_rng(7)
        for _ in range(20000):
            rhos.append(spearman(a, rng.permutation(b)))
        exact = False
    rhos = np.asarray(rhos, dtype=np.float64)
    p = float((np.abs(rhos) >= abs(obs) - 1e-12).mean())
    crit = float(np.quantile(np.abs(rhos), 0.95))
    return {"rho": float(obs), "p": p, "n": int(n), "exact": exact,
            "critical_abs_rho_p05": crit, "n_perms": int(rhos.size)}


def tost_equivalence(
    draws_a: np.ndarray, draws_b: np.ndarray, margin: float, alpha: float = 0.05
) -> dict:
    """Two one-sided tests on PAIRED bootstrap draws -> the (1-2a) interval of a-b."""
    d = np.asarray(draws_a, dtype=np.float64) - np.asarray(draws_b, dtype=np.float64)
    d = d[np.isfinite(d)]
    if d.size < 10:
        return {"verdict": "INCONCLUSIVE", "lo": float("nan"), "hi": float("nan"),
                "margin": margin, "point": float("nan")}
    lo = float(np.quantile(d, alpha))
    hi = float(np.quantile(d, 1 - alpha))
    point = float(d.mean())
    if lo > -margin and hi < margin:
        verdict = "EQUIVALENT"
    elif lo > margin or hi < -margin:
        verdict = "DIFFERENT"
    else:
        verdict = "INCONCLUSIVE"
    return {"verdict": verdict, "lo": lo, "hi": hi, "margin": float(margin), "point": point}


def band_escape(value: float, band: tuple[float, float], ci: tuple[float, float]) -> bool:
    """ESCAPE RULE (7.1): |value| outside the shuffled band AND the item-bootstrap CI
    does not overlap the band."""
    if not np.isfinite(value):
        return False
    lo, hi = float(band[0]), float(band[1])
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return False
    m = max(abs(lo), abs(hi))
    if abs(value) <= m:
        return False
    c_lo, c_hi = float(ci[0]), float(ci[1])
    if not (np.isfinite(c_lo) and np.isfinite(c_hi)):
        return False
    return (c_lo > hi) or (c_hi < lo)


def mde(null_sd: float, n: int, z: float = 1.96) -> float:
    """Minimum detectable effect printed BESIDE every threshold (7.4)."""
    if not np.isfinite(null_sd) or n <= 0:
        return float("nan")
    return float(z * null_sd / np.sqrt(n))


def crossfit_diffmeans_auroc_per_layer(
    A: np.ndarray, y: np.ndarray, n_splits: int = 5, seed: int = 0,
    groups: np.ndarray | None = None,
) -> np.ndarray:
    """Held-out AUROC of the diff-in-means projection at EVERY layer, cross-fitted.

    Used for l_dec (X1/X8) and for BL3.  An IN-SAMPLE diff-in-means reads AUROC 1.000 even
    on pure noise, so this must be, and is, cross-fitted: u is fitted on the training folds
    only and scored on the held-out fold.  Cheap enough (one GEMM per fold per layer) that
    all 20 shuffled-label draws use the identical procedure.
    """
    from sklearn.model_selection import StratifiedKFold

    A = np.asarray(A, dtype=np.float32)
    y = np.asarray(y).astype(int)
    N, L1, _ = A.shape
    scores = np.full((N, L1), np.nan, dtype=np.float64)
    for tr, te in _folds(y, n_splits, seed, groups):
        if len(np.unique(y[tr])) < 2:
            continue
        m1 = A[tr][y[tr] == 1].mean(axis=0)
        m0 = A[tr][y[tr] == 0].mean(axis=0)
        U = unit(m1 - m0, axis=-1)
        scores[te] = np.einsum("nld,ld->nl", A[te], U)
    out = np.full(L1, np.nan)
    for l in range(L1):
        s = scores[:, l]
        ok = np.isfinite(s)
        # >= 4 scored items with both classes present: the k=4 prompt budget (2 per class) must
        # be scorable, however coarse its AUROC is
        if ok.sum() >= 4 and len(np.unique(y[ok])) == 2:
            out[l] = auroc(s[ok], y[ok])
    return out


def crossfit_diffmeans_scores(
    A_layer: np.ndarray, y: np.ndarray, n_splits: int = 5, seed: int = 0,
    groups: np.ndarray | None = None,
) -> np.ndarray:
    """Held-out diff-in-means projection scores at ONE layer (BL3's honest form)."""
    from sklearn.model_selection import StratifiedKFold

    X = np.asarray(A_layer, dtype=np.float32)
    y = np.asarray(y).astype(int)
    out = np.full(len(y), np.nan)
    for tr, te in _folds(y, n_splits, seed, groups):
        if len(np.unique(y[tr])) < 2:
            continue
        u = unit(X[tr][y[tr] == 1].mean(0) - X[tr][y[tr] == 0].mean(0))
        out[te] = X[te] @ u
    return out
