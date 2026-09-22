"""STAGE 3 - the five readouts, computed from saved harvest vectors (pure numpy)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import (WINDOWS, unit, diff_in_means, cohens_d, random_unit_dirs,
                    N_NULL_DIRS, auroc, cv_probe_auroc, ShardedNpz)

HARV = Path(__file__).resolve().parent.parent / "out" / "harvest"


class State:
    """One (lineage, alpha) harvest, with indexed access."""

    def __init__(self, lineage: str, alpha: float, band: list[int], k4_layers: list[int]):
        self.lg, self.a, self.band, self.k4_layers = lineage, alpha, band, k4_layers
        self.z = ShardedNpz(HARV / f"{lineage}_a{alpha:.2f}")
        self.idx = json.loads((HARV / f"{lineage}_index.json").read_text())

    _cache: dict = None

    def win(self, kind, w, li):
        if self._cache is None:
            self._cache = {}
        k = (kind, w, li)
        if k not in self._cache:
            self._cache[k] = self.z[f"{kind}|win|{w}|{li}"].astype(np.float32)
        return self._cache[k]

    # ---- vectorised grouping: (prefix, request) -> [n_pk, n_family] index matrix ----
    def item_groups(self):
        if getattr(self, "_grp", None) is None:
            pks = sorted({m["pair_key"] for m in self.idx["item"]})
            pos = {pk: i for i, pk in enumerate(pks)}
            buckets: dict = {}
            for i, m in enumerate(self.idx["item"]):
                buckets.setdefault((m["prefix"], m["request"]), {}).setdefault(m["pair_key"], []).append(i)
            grp = {}
            for key, d in buckets.items():
                width = max(len(v) for v in d.values())
                M = np.full((len(pks), width), -1, dtype=int)
                for pk, v in d.items():
                    M[pos[pk], :len(v)] = v
                grp[key] = M
            self._grp, self._pks = grp, pks
        return self._grp, self._pks

    def band_proj_all(self, kind, w, dirs):
        """One scalar per row of `kind`: mean over band layers of the projection."""
        return np.mean([self.win(kind, w, li) @ dirs[li] for li in self.band], 0)
    def lastp(self, kind, li):   return self._get(f"{kind}|lastp|{li}")
    def _get(self, key, cast=np.float32):
        if self._cache is None:
            self._cache = {}
        if key not in self._cache:
            self._cache[key] = self.z[key].astype(cast)
        return self._cache[key]

    def perposproj(self, li):    return self._get(f"k4|perposproj|{li}")
    def projnames(self):         return [str(x) for x in self.z["k4|projdir_names"]]
    def nll(self, kind):         return self._get(f"{kind}|nll")
    def rows(self, kind):        return self.idx[kind]

    def sel(self, kind, **kw):
        return np.array([i for i, m in enumerate(self.idx[kind])
                         if all(m.get(k) == v for k, v in kw.items())], dtype=int)

    # ---- directions ----
    def fit_rcontent(self, window="EARLY", subset=None):
        haz = self.sel("fit_content", prefix="hazardous")
        ben = self.sel("fit_content", prefix="benign")
        if subset is not None:
            ss = set(subset)
            haz = np.array([i for i in haz if self.idx["fit_content"][i]["fit_id"] in ss])
            ben = np.array([i for i in ben if self.idx["fit_content"][i]["fit_id"] in ss])
        return {li: unit(diff_in_means(self.win("fit_content", window, li)[haz],
                                       self.win("fit_content", window, li)[ben]))
                for li in self.band}

    def band_proj(self, kind, w, idxs, dirs):
        """mean over band layers of the projection - one scalar per selected row."""
        return np.mean([self.win(kind, w, li)[idxs] @ dirs[li] for li in self.band], 0)


def per_item_contrast(st, dirs, w, pk, prefix_a, prefix_b, request):
    ia = st.sel("item", pair_key=pk, prefix=prefix_a, request=request)
    ib = st.sel("item", pair_key=pk, prefix=prefix_b, request=request)
    return float(st.band_proj("item", w, ia, dirs).mean() - st.band_proj("item", w, ib, dirs).mean())


def per_item_request_contrast(st, dirs, w, pk, prefix):
    ih = st.sel("item", pair_key=pk, prefix=prefix, request="harmful")
    ib = st.sel("item", pair_key=pk, prefix=prefix, request="benign")
    return float(st.band_proj("item", w, ih, dirs).mean() - st.band_proj("item", w, ib, dirs).mean())


def k1_terms(st, dirs, w="EARLY"):
    """O (request main effect), CB (content under benign request), A (interaction), T=CB+A.

    Fully vectorised: the 20 random-direction nulls run through the same code, so
    the null band is pushed through the ENTIRE pipeline, not approximated.
    """
    grp, pks = st.item_groups()
    p = st.band_proj_all("item", w, dirs)

    def cell(prefix, request):
        M = grp[(prefix, request)]
        vals = np.where(M >= 0, p[np.maximum(M, 0)], np.nan)
        return np.nanmean(vals, 1)

    h_b = cell("hazardous", "benign"); b_b = cell("benign", "benign")
    h_h = cell("hazardous", "harmful"); b_h = cell("benign", "harmful")
    cb = h_b - b_b
    cbh = h_h - b_h
    o = 0.5 * ((h_h - h_b) + (b_h - b_b))
    a = cbh - cb
    coh = cell("coherence", "benign") - b_b
    plc = cell("placebo", "benign") - b_b
    return {"O": o, "CB": cb, "A": a, "T": cb + a, "CB_harm": cbh,
            "COH": coh, "PLC": plc}, pks


def null_sd_per_item(st, w, nulls, term="CB"):
    """per-ITEM SD of the SAME contrast under >=20 random unit directions."""
    pks = sorted({m["pair_key"] for m in st.idx["item"]})
    vals = np.zeros((len(pks), len(nulls)))
    for k, nd in enumerate(nulls):
        dirs = {li: nd for li in st.band}
        t, _ = k1_terms(st, dirs, w)
        vals[:, k] = t[term]
    return vals.std(1, ddof=1), vals


def k2_prior_slope(st, dirs, w="EARLY"):
    prior = float(st.band_proj_all("neutral", w, dirs).mean())
    if getattr(st, "_lad", None) is None:
        pks = sorted({m["pair_key"] for m in st.idx["ladder"]})
        pos = {pk: i for i, pk in enumerate(pks)}
        n_r = 1 + max(m["rung"] for m in st.idx["ladder"])
        M = np.full((len(pks), n_r), -1, dtype=int)
        for i, m in enumerate(st.idx["ladder"]):
            M[pos[m["pair_key"]], m["rung"]] = i
        st._lad, st._ladpks = M, pks
    M, pks = st._lad, st._ladpks
    y = st.band_proj_all("ladder", w, dirs)
    Y = np.where(M >= 0, y[np.maximum(M, 0)], np.nan)
    r = np.arange(Y.shape[1], dtype=float)
    rm = r.mean()
    slopes = np.nansum((r - rm) * (Y - np.nanmean(Y, 1, keepdims=True)), 1) / np.sum((r - rm) ** 2)
    return prior, slopes, pks


def k3_footprint(st, st0, w="EARLY"):
    """Benign-only activation footprint vs this lineage's OWN alpha=0 baseline.
    NO harmful text anywhere: neutral set + benign-request/benign-prefix cells only."""
    parts = []
    ni = st.sel("neutral"); ni0 = st0.sel("neutral")
    bi = st.sel("item", prefix="benign", request="benign")
    bi0 = st0.sel("item", prefix="benign", request="benign")
    for li in st.band:
        a = np.concatenate([st.win("neutral", w, li)[ni], st.win("item", w, li)[bi]])
        b = np.concatenate([st0.win("neutral", w, li)[ni0], st0.win("item", w, li)[bi0]])
        parts.append(np.linalg.norm(a.mean(0) - b.mean(0)))
    return float(np.mean(parts))


def k4_tau(st, dirs_pp, request="harmful", which="r_content_parent"):
    """Exponential decay of the hazard projection over the FIXED 128-token continuation."""
    taus, r2s, pks = [], [], []
    ii = st.sel("k4", request=request)
    names = st.projnames()
    k = names.index(which)
    P = np.mean([st.perposproj(li)[:, :, k] for li in st.k4_layers], 0)   # [n_seq, cont]
    Y = P[ii]
    taus, r2s = _fit_exp_batch(np.arange(Y.shape[1], dtype=float), Y)
    pks = [st.idx["k4"][i]["pair_key"] for i in ii]
    return taus, r2s, pks


def _fit_exp_batch(t, Y):
    """s(t) = s_inf + (s0 - s_inf) exp(-t/tau), fitted for EVERY row of Y at once.

    The tau grid is shared, so each candidate tau needs one 2x2 normal-equation solve
    reused across all rows - the same estimator as _fit_exp, ~200x faster.
    """
    n, T = Y.shape
    ok = np.isfinite(Y).all(1)
    Yc = np.where(np.isfinite(Y), Y, 0.0)
    ybar = Yc.mean(1, keepdims=True)
    sst = ((Yc - ybar) ** 2).sum(1)
    best_r2 = np.full(n, -np.inf)
    best_tau = np.full(n, np.nan)
    ones = np.ones(T)
    for tau in np.geomspace(1.0, 400.0, 60):
        e = np.exp(-t / tau)
        X = np.column_stack([ones, e])                  # [T, 2]
        G = X.T @ X                                      # [2, 2]
        try:
            B = np.linalg.solve(G, X.T @ Yc.T)           # [2, n]
        except np.linalg.LinAlgError:
            continue
        R = Yc - (X @ B).T
        rss = (R ** 2).sum(1)
        with np.errstate(divide="ignore", invalid="ignore"):
            r2 = np.where(sst > 0, 1.0 - rss / sst, 0.0)
        upd = r2 > best_r2
        best_r2[upd] = r2[upd]
        best_tau[upd] = tau
    best_tau[~ok] = np.nan
    best_r2[~ok] = np.nan
    return best_tau, best_r2


def _fit_exp(t, y):
    """s(t) = s_inf + (s0 - s_inf) exp(-t/tau); grid on tau, closed form on the rest."""
    best = (np.nan, -np.inf)
    ybar = y.mean(); sst = float(((y - ybar) ** 2).sum())
    for tau in np.geomspace(1.0, 400.0, 60):
        e = np.exp(-t / tau)
        X = np.column_stack([np.ones_like(t), e])
        try:
            c, *_ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            continue
        r = y - X @ c
        r2 = 1.0 - float((r ** 2).sum()) / sst if sst > 0 else 0.0
        if r2 > best[1]:
            best = (float(tau), r2)
    return best


def k5_profile(st, dirs, w="EARLY"):
    doms = sorted({m["domain"] for m in st.idx["domain"]})
    y = st.band_proj_all("domain", w, dirs)
    dl = np.array([m["domain"] for m in st.idx["domain"]])
    prof = {}
    for d in doms:
        prof[d] = float(y[dl == d].mean())
    v = np.array([prof[d] for d in doms])
    return prof, doms, float(v.std(ddof=1))


def damage_auroc(st, layer, folds=5, tag="fold|0"):
    X = st.lastp("damage", layer)
    y = np.array([m["label"] for m in st.idx["damage"]])
    return cv_probe_auroc(X, y, folds=folds, tag=tag)


def damage_null(st, layer, tag="fold|shuf"):
    X = st.lastp("damage", layer)
    y = np.array([m["label"] for m in st.idx["damage"]])
    from common import rng_for
    g = rng_for(tag)
    return float(np.mean([cv_probe_auroc(X, g.permutation(y), tag=f"{tag}|{k}") for k in range(3)]))


def baseline_scores(st, layer):
    """BASELINES ONLY - never the deliverable."""
    X = st.lastp("damage", layer)
    y = np.array([m["label"] for m in st.idx["damage"]])
    d = unit(diff_in_means(X[y == 1], X[y == 0]))
    return {
        "in_sample_diff_in_means_auroc": auroc(X @ d, y),
        "cv_probe_raw_hidden_auroc": cv_probe_auroc(X, y, tag="fold|base"),
    }
