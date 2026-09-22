"""Per-checkpoint candidate engine for the iter-4 no-op/effective pair scoring study.

Implements WS/specs/scoring_spec.md sections 1-6. Pure numpy, float64 everywhere, vectorised
over layers via the Gram-matrix speed trick of src_i3/extra_analyses.py:PromptModel (section 5):
for any axis fit as a linear combination `c` of the EASY rows, the projection of any target row
set T onto the (implicitly unit-normalised) axis at every layer is

    proj[l, :] = (K_T[l] @ c) / sqrt(c^T G_EE[l] c)

where G_EE[l] = A_easy[:,l,:] @ A_easy[:,l,:].T and K_T[l] = A_T[:,l,:] @ A_easy[:,l,:].T are
precomputed ONCE per checkpoint in float64. A bootstrap draw only changes `c` (and the row
weights used inside T), so every candidate inside a draw costs a handful of small matvecs, never
a [N, d] recomputation.

Conventions (spec section 2, copied from src_i3/candidates.py): l in 0..L indexes hidden_states
(0 = embeddings); lay(f) = floor(f*L + 0.5); axis = unit(mean(y=1) - mean(y=0)); EASY (set_id 0)
FITS, HARD (set_id 1) SCORES.
"""
from __future__ import annotations

import importlib
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

EPS = 1e-12
NOT_AVAILABLE = "NOT_AVAILABLE"

WS = Path(__file__).resolve().parents[2]   # PATCHED iter5: vendored at src/vendor/ (was parents[1] -> src/)
ASSETS = WS / "assets"


# =====================================================================================
# 0. stimuli / c11 loading (fixed order, section 1)
# =====================================================================================
def _jload(p: Path):
    import json
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


@dataclass
class Stimuli:
    rows: list[dict]
    y: np.ndarray            # [256] int
    sid: np.ndarray          # [256] int  (0 EASY, 1 HARD)
    source: np.ndarray       # [256] str
    easy_idx: np.ndarray     # indices into the 256 rows where sid==0 (96,)
    hard_idx: np.ndarray     # indices into the 256 rows where sid==1 (160,)
    y_easy: np.ndarray
    y_hard: np.ndarray
    source_easy: np.ndarray
    source_hard: np.ndarray
    xstest_harm_mask_hard: np.ndarray   # within HARD (160,): xstest_v2_harmful_twin
    xstest_safe_mask_hard: np.ndarray   # within HARD (160,): xstest_v2_benign_twin
    stratum_easy: np.ndarray            # (set_id,y,source) stratum label per EASY row
    stratum_hard: np.ndarray

    def restrict(self, n: int) -> "Stimuli":
        """BUGFIX (spec 8g): a Stimuli view for a REDUCED harvest dir whose A_prompt.npy only
        covers a PREFIX of the canonical 256 rows (e.g. harvest_variants.py --smoke-limit,
        which truncates the exact same `stimuli.json` list: `S = stimuli[:smoke_limit]`).
        Re-derives easy/hard indices, xstest masks and strata from the first `n` rows only, so
        every downstream `stim.*` lookup for that checkpoint stays index-consistent with the
        rows actually present instead of indexing past the end of its arrays. Used via
        `ckpt_stim()`; real (256-row) checkpoints never call this."""
        rows, y, sid, source = self.rows[:n], self.y[:n], self.sid[:n], self.source[:n]
        easy_idx = np.flatnonzero(sid == 0)
        hard_idx = np.flatnonzero(sid == 1)
        source_hard = source[hard_idx]
        xh = source_hard == "xstest_v2_harmful_twin"
        xs = source_hard == "xstest_v2_benign_twin"

        def strat(idx):
            return np.array([f"{sid[i]}|{y[i]}|{source[i]}" for i in idx])

        return Stimuli(
            rows=rows, y=y, sid=sid, source=source, easy_idx=easy_idx, hard_idx=hard_idx,
            y_easy=y[easy_idx], y_hard=y[hard_idx], source_easy=source[easy_idx],
            source_hard=source_hard, xstest_harm_mask_hard=xh, xstest_safe_mask_hard=xs,
            stratum_easy=strat(easy_idx), stratum_hard=strat(hard_idx),
        )


_STIM: Optional[Stimuli] = None


def load_stimuli() -> Stimuli:
    global _STIM
    if _STIM is not None:
        return _STIM
    doc = _jload(ASSETS / "stimuli.json")
    rows = doc["rows"]
    assert len(rows) == 256, f"expected 256 stimuli rows, got {len(rows)}"
    y = np.array([r["y"] for r in rows], dtype=int)
    sid = np.array([r["set_id"] for r in rows], dtype=int)
    source = np.array([r.get("source", "") for r in rows])
    easy_idx = np.flatnonzero(sid == 0)
    hard_idx = np.flatnonzero(sid == 1)
    assert easy_idx.size == 96 and hard_idx.size == 160, (easy_idx.size, hard_idx.size)
    source_hard = source[hard_idx]
    xh = source_hard == "xstest_v2_harmful_twin"
    xs = source_hard == "xstest_v2_benign_twin"
    assert xh.sum() == 40 and xs.sum() == 40, (xh.sum(), xs.sum())

    def strat(idx):
        return np.array([f"{sid[i]}|{y[i]}|{source[i]}" for i in idx])

    _STIM = Stimuli(
        rows=rows, y=y, sid=sid, source=source, easy_idx=easy_idx, hard_idx=hard_idx,
        y_easy=y[easy_idx], y_hard=y[hard_idx], source_easy=source[easy_idx],
        source_hard=source_hard, xstest_harm_mask_hard=xh, xstest_safe_mask_hard=xs,
        stratum_easy=strat(easy_idx), stratum_hard=strat(hard_idx),
    )
    return _STIM


def load_c11_items() -> list[dict]:
    doc = _jload(ASSETS / "c11_items.json")
    return doc["items"]


# =====================================================================================
# 1. small numeric primitives
# =====================================================================================
def lay(f: float, L: int) -> int:
    return int(math.floor(f * L + 0.5))


def unit(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    n = np.linalg.norm(v)
    return v / n if n > EPS else v * 0.0


def stratified_bootstrap_weights(strata: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """One multiplicity-weight vector [len(strata)], resampling WITH replacement independently
    within every unique stratum label, each stratum keeping its own original size."""
    strata = np.asarray(strata)
    w = np.zeros(strata.shape[0], dtype=np.float64)
    for s in np.unique(strata):
        idx = np.flatnonzero(strata == s)
        draw = rng.integers(0, idx.size, size=idx.size)
        counts = np.bincount(draw, minlength=idx.size).astype(np.float64)
        w[idx] = counts
    return w


def axis_weight_vector(y: np.ndarray, w: np.ndarray, mask: Optional[np.ndarray] = None) -> np.ndarray:
    """c_i = w_i/sum(w[y==1]&mask) for y=1, -w_i/sum(w[y==0]&mask) for y=0, else 0.
    unit(sum_i c_i A_i) == unit(weighted_mean_y1 - weighted_mean_y0)."""
    y = np.asarray(y).astype(int)
    w = np.asarray(w, dtype=np.float64)
    if mask is not None:
        w = w * mask.astype(np.float64)
    c = np.zeros(w.shape[0], dtype=np.float64)
    m1 = (y == 1)
    m0 = (y == 0)
    s1 = w[m1].sum()
    s0 = w[m0].sum()
    if s1 > EPS:
        c[m1] = w[m1] / s1
    if s0 > EPS:
        c[m0] = -w[m0] / s0
    return c


# ---- weighted statistics that reduce EXACTLY to src_h2/numerics.py with unit weights --------
def cohens_d_w(P: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """P: [..., N] (any leading shape, e.g. [L1]), y: [N] in {0,1}, w: [N] >= 0 multiplicities.
    Returns [...] Cohen's d. With w == ones this is EXACTLY src_h2.numerics.cohens_d applied
    along the last axis (pooled-SD, ddof=1 via the (sum(w)-1) denominator)."""
    P = np.asarray(P, dtype=np.float64)
    y = np.asarray(y).astype(int)
    w = np.asarray(w, dtype=np.float64)
    m1, m0 = y == 1, y == 0
    x1, x0 = P[..., m1], P[..., m0]
    w1, w0 = w[m1], w[m0]
    n1, n0 = float(w1.sum()), float(w0.sum())
    if n1 < 2 or n0 < 2:
        return np.full(P.shape[:-1], np.nan)
    mu1 = (x1 * w1).sum(-1) / n1
    mu0 = (x0 * w0).sum(-1) / n0
    v1 = (w1 * (x1 - mu1[..., None]) ** 2).sum(-1) / max(n1 - 1, EPS)
    v0 = (w0 * (x0 - mu0[..., None]) ** 2).sum(-1) / max(n0 - 1, EPS)
    sp = np.sqrt(((n1 - 1) * v1 + (n0 - 1) * v0) / max(n1 + n0 - 2, 1.0))
    out = (mu1 - mu0) / sp
    return np.where(sp < EPS, np.nan, out)


def fisher_ratio_w(P: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """(mu1-mu0)^2 / (var1+var0), var ddof=1 weighted; reduces to src_h2.numerics.fisher_ratio."""
    P = np.asarray(P, dtype=np.float64)
    y = np.asarray(y).astype(int)
    w = np.asarray(w, dtype=np.float64)
    m1, m0 = y == 1, y == 0
    x1, x0 = P[..., m1], P[..., m0]
    w1, w0 = w[m1], w[m0]
    n1, n0 = float(w1.sum()), float(w0.sum())
    if n1 < 2 or n0 < 2:
        return np.full(P.shape[:-1], np.nan)
    mu1 = (x1 * w1).sum(-1) / n1
    mu0 = (x0 * w0).sum(-1) / n0
    v1 = (w1 * (x1 - mu1[..., None]) ** 2).sum(-1) / max(n1 - 1, EPS)
    v0 = (w0 * (x0 - mu0[..., None]) ** 2).sum(-1) / max(n0 - 1, EPS)
    within = v1 + v0
    out = (mu1 - mu0) ** 2 / within
    return np.where(within < EPS, np.nan, out)


def auroc_w(P: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted Mann-Whitney AUROC (average-rank tie handling), reduces exactly to
    src_h2.numerics.auroc with unit weights. P: [..., N]."""
    P = np.asarray(P, dtype=np.float64)
    y = np.asarray(y).astype(int)
    w = np.asarray(w, dtype=np.float64)
    m1, m0 = y == 1, y == 0
    n1, n0 = float(w[m1].sum()), float(w[m0].sum())
    if n1 < EPS or n0 < EPS:
        return np.full(P.shape[:-1], np.nan)
    Pp, Pn = P[..., m1], P[..., m0]
    wp, wn = w[m1], w[m0]
    diff = Pp[..., :, None] - Pn[..., None, :]
    ind = (diff > 0).astype(np.float64) + 0.5 * (diff == 0).astype(np.float64)
    U = np.einsum("...ab,a,b->...", ind, wp, wn, optimize=True)
    return U / (n1 * n0)


def _weighted_quantile_higher(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    """The smallest value whose cumulative weight fraction (from the bottom) is >= q; reduces
    to numpy.quantile(..., method='higher') when weights == 1."""
    v = np.asarray(values, dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    ok = w > 0
    v, w = v[ok], w[ok]
    if v.size == 0:
        return float("nan")
    order = np.argsort(v, kind="mergesort")
    v, w = v[order], w[order]
    cw = np.cumsum(w)
    total = cw[-1]
    frac = cw / total
    idx = int(np.searchsorted(frac, q - 1e-12, side="left"))
    idx = min(idx, v.size - 1)
    return float(v[idx])


def tpr_at_fpr_w(P: np.ndarray, y: np.ndarray, w: np.ndarray, fpr_level: float) -> np.ndarray:
    """Vectorised over a leading axis via python loop (cheap: only used at single layers).
    Reduces exactly to src_h2.numerics.tpr_at_fpr with unit weights."""
    P = np.asarray(P, dtype=np.float64)
    y = np.asarray(y).astype(int)
    w = np.asarray(w, dtype=np.float64)
    lead_shape = P.shape[:-1]
    if P.shape[-1] == 0:
        # BUGFIX (spec 8g): an EMPTY target set (e.g. zero HARD rows on a reduced/smoke
        # checkpoint) makes P.reshape(-1, 0) ambiguous (numpy cannot infer the leading dim of a
        # size-0 array against a 0-sized last axis) and raises ValueError. No positive/negative
        # examples -> NaN, same convention as every other length guard in this module.
        return np.full(lead_shape, np.nan) if lead_shape else float("nan")
    flat = P.reshape(-1, P.shape[-1])
    out = np.empty(flat.shape[0], dtype=np.float64)
    for i in range(flat.shape[0]):
        s = flat[i]
        neg_m, pos_m = y == 0, y == 1
        neg, pos = s[neg_m], s[pos_m]
        wneg, wpos = w[neg_m], w[pos_m]
        if neg.size == 0 or pos.size == 0 or wneg.sum() < EPS or wpos.sum() < EPS:
            out[i] = float("nan")
            continue
        thr = _weighted_quantile_higher(neg, wneg, 1.0 - fpr_level)
        above_mask = neg > thr
        realised_fpr = (wneg[neg >= thr].sum()) / wneg.sum()
        if realised_fpr > fpr_level and above_mask.any():
            thr = float(neg[above_mask].min())
        out[i] = float(wpos[pos >= thr].sum() / wpos.sum())
    return out.reshape(lead_shape) if lead_shape else float(out[0])


def spearman_w(x: np.ndarray, yv: np.ndarray, w: np.ndarray) -> float:
    """Weighted Spearman rho via average-rank-of-the-expanded-sample + weighted Pearson;
    reduces to src_h2.numerics.spearman with unit weights (no ties)."""
    x = np.asarray(x, dtype=np.float64)
    yv = np.asarray(yv, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    ok = np.isfinite(x) & np.isfinite(yv) & (w > 0)
    x, yv, w = x[ok], yv[ok], w[ok]
    if x.size < 3 or w.sum() < 3:
        return float("nan")

    def wrank(v: np.ndarray) -> np.ndarray:
        order = np.argsort(v, kind="mergesort")
        vs, ws = v[order], w[order]
        cw = np.cumsum(ws)
        r = np.empty_like(vs)
        i = 0
        n = vs.size
        while i < n:
            j = i
            while j + 1 < n and vs[j + 1] == vs[i]:
                j += 1
            below = cw[i - 1] if i > 0 else 0.0
            weq = cw[j] - below
            r[i:j + 1] = below + (weq + 1.0) / 2.0
            i = j + 1
        out = np.empty_like(v)
        out[order] = r
        return out

    rx, ry = wrank(x), wrank(yv)
    W = w.sum()
    mx = (rx * w).sum() / W
    my = (ry * w).sum() / W
    cov = (w * (rx - mx) * (ry - my)).sum()
    vx = (w * (rx - mx) ** 2).sum()
    vy = (w * (ry - my) ** 2).sum()
    den = math.sqrt(vx * vy)
    return float(cov / den) if den > EPS else float("nan")


# =====================================================================================
# 2. Ckpt: loading + Gram precompute (spec sections 1, 5)
# =====================================================================================
def _load_npy_opt(p: Path) -> Optional[np.ndarray]:
    """Load an optional harvest array. BUGFIX (spec 8g): treat a MISSING file, or a file that
    only holds a pickled placeholder (e.g. `np.save(..., None)` written when a pass produced
    zero rows -- this actually occurs for A_dec.npy/A_dec_tok1.npy on a harvest dir with zero
    HARD stimuli, such as the RANDINIT smoke dir), as 'not available' -- never a crash and
    never imputed to a real array. `np.load` refuses object-dtype payloads unless
    allow_pickle=True, so a plain load first, and only fall back to allow_pickle=True to
    IDENTIFY the placeholder (and immediately discard it as unavailable, never trust its
    content)."""
    if not p.exists():
        return None
    try:
        a = np.load(p)
    except ValueError:
        a = np.load(p, allow_pickle=True)
    if a.dtype == object:
        return None
    return a


@dataclass
class Ckpt:
    tag: str
    dir: Path
    L: int
    d: int
    provenance: str                      # "artifact" (WS/harvest/<tag>) or "ondisk" (iter-2/iter-3)
    A_easy: np.ndarray                   # [96, L1, d] float64
    A_hard: np.ndarray                   # [160, L1, d] float64
    r_refusal: np.ndarray                # [256, L1] float64
    r_control: np.ndarray                # [256, L1] float64
    WU_ref: np.ndarray
    WU_ctl: np.ndarray
    gamma: np.ndarray
    vmin_stacked: Optional[np.ndarray] = None      # [L, d]
    vmin_onesproj: Optional[np.ndarray] = None      # [L, d], artifact dirs only
    gram_dir: Optional[Path] = None                 # ondisk dirs only: dir/gram/G_###.npy
    A_c11: Optional[np.ndarray] = None              # [64, L1, d]
    severity: Optional[np.ndarray] = None
    A_dec: Optional[np.ndarray] = None              # [160, L1, d]
    A_dec_tok1: Optional[np.ndarray] = None
    dec_ntok: Optional[np.ndarray] = None
    A_ams: Optional[np.ndarray] = None               # [96, L1, d]
    A_prompt_p1: Optional[np.ndarray] = None         # [256, L1, d]: plain 'User:...\nAssistant:' render
    A_prompt_p2: Optional[np.ndarray] = None         # [256, L1, d]: helpful-system-prompt render
    A_prompt_p3: Optional[np.ndarray] = None         # [256, L1, d]: other-precision render
    availability: dict = field(default_factory=dict)  # name -> bool, for reporting

    def n5_perturbation_arrays(self) -> dict[str, np.ndarray]:
        """Every N5 (spec 3/e_candidates) perturbation array THIS checkpoint's own dir actually has
        (amendment: N5 is computed for every checkpoint dir with p1/p2/p3, not only parents).
        Missing arrays are simply absent from the dict -- n5_invariance() then reports
        NOT_AVAILABLE for them, never 0."""
        out = {}
        if self.A_prompt_p1 is not None:
            out["p1"] = self.A_prompt_p1
        if self.A_prompt_p2 is not None:
            out["p2"] = self.A_prompt_p2
        if self.A_prompt_p3 is not None:
            out["p3"] = self.A_prompt_p3
        return out
    _stim_view: Optional[Stimuli] = field(default=None, repr=False)  # set for reduced dirs only

    # ---- populated by precompute() ----
    _pc: dict = field(default_factory=dict, repr=False)

    @classmethod
    def load(cls, tag: str, dir: Path) -> "Ckpt":
        dir = Path(dir)
        import json
        meta = json.loads((dir / "meta.json").read_text())
        L = int(meta["n_layers"])
        d = int(meta["hidden_size"])
        A = np.load(dir / "A_prompt.npy").astype(np.float64)     # [N, L1, d], normally N=256
        assert A.shape[1] == L + 1 and A.shape[2] == d, (A.shape, L, d)
        stim_full = load_stimuli()
        if A.shape[0] == 256:
            stim, stim_view = stim_full, None
        else:
            # BUGFIX (spec 8g): a reduced / code-path harvest (e.g. harvest_variants.py
            # --smoke-limit, used by the RANDINIT smoke dir) only covers a PREFIX of the
            # canonical 256 stimuli.json rows. Previously this hard-asserted A.shape==(256,...)
            # and crashed; now build a matching Stimuli view (Stimuli.restrict) so every
            # stim.* lookup for THIS checkpoint (via ckpt_stim()) stays consistent with the
            # rows actually present. Real (256-row) checkpoints take the branch above and are
            # byte-for-byte unaffected.
            stim = stim_full.restrict(A.shape[0])
            stim_view = stim
        A_easy = A[stim.easy_idx]
        A_hard = A[stim.hard_idx]
        r_ref = np.load(dir / "r_refusal.npy").astype(np.float64)
        r_ctl = np.load(dir / "r_control.npy").astype(np.float64)
        WU_ref = np.load(dir / "WU_ref.npy").astype(np.float64)
        WU_ctl = np.load(dir / "WU_ctl.npy").astype(np.float64)
        gamma = np.load(dir / "gamma.npy").astype(np.float64)

        gram_dir = dir / "gram"
        has_gram = gram_dir.exists() and any(gram_dir.glob("G_*.npy"))
        vmin_onesproj = _load_npy_opt(dir / "vmin_onesproj.npy")
        provenance = "artifact" if vmin_onesproj is not None else ("ondisk" if has_gram else "unknown")

        avail = {}
        A_c11 = _load_npy_opt(dir / "A_c11.npy")
        avail["A_c11"] = A_c11 is not None
        severity = None
        if A_c11 is not None:
            items = load_c11_items()
            severity = np.array([it["severity"] for it in items[: A_c11.shape[0]]], dtype=np.float64)
            A_c11 = A_c11.astype(np.float64)

        A_dec = _load_npy_opt(dir / "A_dec.npy")
        A_dec_tok1 = _load_npy_opt(dir / "A_dec_tok1.npy")
        dec_ntok = _load_npy_opt(dir / "dec_ntok.npy")
        avail["A_dec"] = A_dec is not None
        avail["A_dec_tok1"] = A_dec_tok1 is not None
        if A_dec is not None:
            A_dec = A_dec.astype(np.float64)
        if A_dec_tok1 is not None:
            A_dec_tok1 = A_dec_tok1.astype(np.float64)

        A_ams = _load_npy_opt(dir / "A_ams.npy")
        avail["A_ams"] = A_ams is not None
        if A_ams is not None:
            A_ams = A_ams.astype(np.float64)

        A_prompt_p1 = _load_npy_opt(dir / "A_prompt_p1.npy")
        avail["A_prompt_p1"] = A_prompt_p1 is not None
        if A_prompt_p1 is not None:
            A_prompt_p1 = A_prompt_p1.astype(np.float64)

        A_prompt_p2 = _load_npy_opt(dir / "A_prompt_p2.npy")
        avail["A_prompt_p2"] = A_prompt_p2 is not None
        if A_prompt_p2 is not None:
            A_prompt_p2 = A_prompt_p2.astype(np.float64)

        A_prompt_p3 = _load_npy_opt(dir / "A_prompt_p3.npy")
        avail["A_prompt_p3"] = A_prompt_p3 is not None
        if A_prompt_p3 is not None:
            A_prompt_p3 = A_prompt_p3.astype(np.float64)

        vmin_stacked = _load_npy_opt(dir / "vmin_stacked.npy")
        avail["vmin_stacked"] = vmin_stacked is not None
        avail["vmin_onesproj"] = vmin_onesproj is not None
        avail["gram"] = has_gram

        ck = cls(
            tag=tag, dir=dir, L=L, d=d, provenance=provenance, A_easy=A_easy, A_hard=A_hard,
            r_refusal=r_ref, r_control=r_ctl, WU_ref=WU_ref, WU_ctl=WU_ctl, gamma=gamma,
            vmin_stacked=vmin_stacked, vmin_onesproj=vmin_onesproj,
            gram_dir=gram_dir if has_gram else None,
            A_c11=A_c11, severity=severity, A_dec=A_dec, A_dec_tok1=A_dec_tok1, dec_ntok=dec_ntok,
            A_ams=A_ams, A_prompt_p1=A_prompt_p1, A_prompt_p2=A_prompt_p2, A_prompt_p3=A_prompt_p3,
            availability=avail, _stim_view=stim_view,
        )
        return ck


def ckpt_stim(ckpt: Ckpt) -> Stimuli:
    """The Stimuli view for THIS checkpoint: the cached canonical 256-row object for a normal
    harvest dir, or the matching reduced view (Stimuli.restrict, set by Ckpt.load) for a
    smoke/code-path dir whose A_prompt.npy holds fewer rows (spec 8g). Every function below
    that used to call `load_stimuli()` directly now goes through this, with ZERO behaviour
    change for real (256-row) checkpoints."""
    return ckpt._stim_view if ckpt._stim_view is not None else load_stimuli()


def precompute(ckpt: Ckpt, seed_base: int = 20260921, n_splits: int = 20) -> dict:
    """Build the Gram bundle (section 5) and the fixed 2-fold cross-fit splits (section 3).
    Idempotent / cheap to call again; result also stored on ckpt._pc."""
    stim = ckpt_stim(ckpt)
    L1 = ckpt.L + 1
    AE, AH = ckpt.A_easy, ckpt.A_hard   # [96,L1,d] [160,L1,d] float64

    G_EE = np.einsum("nld,mld->lnm", AE, AE, optimize=True)          # [L1,96,96]
    K_EH = np.einsum("nld,mld->lnm", AH, AE, optimize=True)          # [L1,160,96]
    pc: dict[str, Any] = {"G_EE": G_EE, "K_EH": K_EH}

    if ckpt.A_c11 is not None:
        pc["K_Ec11"] = np.einsum("nld,mld->lnm", ckpt.A_c11, AE, optimize=True)   # [L1,64,96]
    if ckpt.A_dec is not None:
        pc["K_Edec"] = np.einsum("nld,mld->lnm", ckpt.A_dec, AE, optimize=True)   # [L1,160,96]
    if ckpt.A_dec_tok1 is not None:
        pc["K_Edec1"] = np.einsum("nld,mld->lnm", ckpt.A_dec_tok1, AE, optimize=True)

    # ---- N2/N3 projected space: Q = orthonormal basis of WU_ref rows (QR), same Q every layer
    M = ckpt.WU_ref.T                                    # [d, n_ref]
    Q, _ = np.linalg.qr(M, mode="reduced")                # [d, r], r = min(d, n_ref)
    pc["Q"] = Q
    AE_perp = AE - np.einsum("nld,dr,sr->nls", AE, Q, Q, optimize=True)
    AH_perp = AH - np.einsum("nld,dr,sr->nls", AH, Q, Q, optimize=True)
    pc["G_EE_perp"] = np.einsum("nld,mld->lnm", AE_perp, AE_perp, optimize=True)
    pc["K_EH_perp"] = np.einsum("nld,mld->lnm", AH_perp, AE_perp, optimize=True)

    # ---- fixed 2-fold stratified splits of EASY (local indices 0..n_easy-1), section 3
    y_easy = stim.y_easy
    n_easy = y_easy.shape[0]
    pos = np.flatnonzero(y_easy == 1)
    neg = np.flatnonzero(y_easy == 0)
    folds = []
    if pos.size == 48 and neg.size == 48:
        # canonical case (every real checkpoint): unchanged, byte-identical RNG stream to
        # before the spec-8g bugfix below.
        half = 24
    else:
        # BUGFIX (spec 8g): a reduced/code-path harvest dir (e.g. a --smoke-limit prefix) can
        # have an EASY class split other than 48/48 -- the old code hard-asserted 48/48 and
        # crashed. Use a proportional half-per-class instead; if either class is too small to
        # split at all (e.g. the RANDINIT smoke dir's 6-row prefix is ALL y=1, so neg.size==0),
        # leave `folds` empty -- crossfit_lstar / n7_two_sided_gap treat that as "no signal",
        # returning NaN rather than crashing on an empty stack.
        half = min(pos.size, neg.size) // 2
    if half >= 1:
        for s in range(n_splits):
            rng = np.random.default_rng(seed_base + s)
            pp = rng.permutation(pos)
            nn = rng.permutation(neg)
            foldA = np.zeros(n_easy, dtype=bool)
            foldA[pp[:half]] = True
            foldA[nn[:half]] = True
            folds.append(foldA)
    pc["folds"] = folds

    # BL1_truelogit's LSE readout does not depend on weights or labels -> cache once (spec 5 speed rule)
    pc["g_easy_tl"] = _lse_rows(AE[:, ckpt.L, :], ckpt.WU_ref) - _lse_rows(AE[:, ckpt.L, :], ckpt.WU_ctl)
    pc["g_hard_tl"] = _lse_rows(AH[:, ckpt.L, :], ckpt.WU_ref) - _lse_rows(AH[:, ckpt.L, :], ckpt.WU_ctl)

    ckpt._pc = pc
    return pc


def proj_curve(K: np.ndarray, G_EE: np.ndarray, c: np.ndarray) -> np.ndarray:
    """K:[L1,m,96], G_EE:[L1,96,96], c:[96] -> [L1,m] projections at every layer at once.
    SPEED (spec section 5): `den2` used to be the 3-operand einsum "n,lnk,k->l", whose per-call
    contraction-path search dominates its cost for this shape; c^T G c = (G c) . c is identical
    to 1e-9 (checked in test_scoring.py check_b) and ~6x faster via a batched matvec + reduce."""
    num = np.einsum("lmn,n->lm", K, c, optimize=True)
    Gc = G_EE @ c                              # [L1,96,96] @ [96] -> [L1,96], batched matvec
    den2 = np.einsum("ln,n->l", Gc, c, optimize=True)
    den = np.sqrt(np.maximum(den2, EPS))
    return num / den[:, None]


def proj_at_layer(K_l: np.ndarray, G_EE_l: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Single-layer version: K_l:[m,96], G_EE_l:[96,96], c:[96] -> [m]."""
    num = K_l @ c
    den = math.sqrt(max(float(c @ G_EE_l @ c), EPS))
    return num / den


# =====================================================================================
# 3. cross-fitted l_star search (spec section 3, "l_star")
# =====================================================================================
def crossfit_lstar(
    G_EE: np.ndarray, folds: list[np.ndarray], y_easy: np.ndarray, w_easy: np.ndarray, L: int,
) -> tuple[int, np.ndarray]:
    """20 seeded 2-fold splits x 2 directions = 40 fits. For each fit: axis on the TRAIN fold
    (weighted), Cohen's d of the TEST fold's projections (weighted). d_cf(l) = mean over the 40
    fits. l_star = argmax over l in 1..L of d_cf(l) (ties -> smallest l). Returns (l_star, d_cf).
    """
    L1 = L + 1
    if not folds:
        # BUGFIX (spec 8g): precompute() leaves `folds` empty when the EASY set has too few
        # items of one class to cross-fit at all (e.g. the RANDINIT smoke dir). No signal, not
        # a crash: report an all-NaN curve and a harmless l_star=1.
        return 1, np.full(L1, np.nan)
    C = []
    test_masks = []
    for foldA in folds:
        for train_mask in (foldA, ~foldA):
            test_mask = ~train_mask
            c = axis_weight_vector(y_easy, w_easy, mask=train_mask)
            C.append(c)
            test_masks.append(test_mask)
    C = np.stack(C, axis=0)                                    # [40, 96]
    M = np.stack(test_masks, axis=0).astype(np.float64)         # [40, 96] test-fold indicator
    proj_batch = np.einsum("lab,kb->lka", G_EE, C, optimize=True)   # [L1, 40, 96]

    # Batched (over layer l AND fit k at once) weighted Cohen's d of the test fold, replacing a
    # 40-iteration python loop over cohens_d_w: this is the dominant per-draw cost (crossfit_lstar
    # is called twice per draw, for N1 and N2), so it is vectorised fully (spec 5's rule).
    y1 = (y_easy == 1).astype(np.float64)
    y0 = (y_easy == 0).astype(np.float64)
    W1 = M * w_easy[None, :] * y1[None, :]          # [40, 96]
    W0 = M * w_easy[None, :] * y0[None, :]
    n1 = W1.sum(axis=1)                              # [40]
    n0 = W0.sum(axis=1)
    num1 = np.einsum("lki,ki->lk", proj_batch, W1, optimize=True)   # [L1, 40]
    num0 = np.einsum("lki,ki->lk", proj_batch, W0, optimize=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        mu1 = num1 / n1[None, :]
        mu0 = num0 / n0[None, :]
        v1 = np.einsum("lki,ki->lk", (proj_batch - mu1[:, :, None]) ** 2, W1, optimize=True) / np.maximum(n1[None, :] - 1, EPS)
        v0 = np.einsum("lki,ki->lk", (proj_batch - mu0[:, :, None]) ** 2, W0, optimize=True) / np.maximum(n0[None, :] - 1, EPS)
        sp = np.sqrt(((n1[None, :] - 1) * v1 + (n0[None, :] - 1) * v0) / np.maximum(n1[None, :] + n0[None, :] - 2, 1.0))
        d_lk = (mu1 - mu0) / sp                        # [L1, 40]
    valid = (n1 >= 2) & (n0 >= 2)
    d_lk = np.where((sp < EPS) | ~valid[None, :], np.nan, d_lk)
    ok = np.isfinite(d_lk)
    counts = ok.sum(axis=1).astype(np.float64)
    d_cf = np.nansum(np.where(ok, d_lk, 0.0), axis=1)
    with np.errstate(invalid="ignore"):
        d_cf = np.where(counts > 0, d_cf / np.maximum(counts, 1), np.nan)
    search = np.where(np.isfinite(d_cf), d_cf, -np.inf)
    search[0] = -np.inf  # l in 1..L only
    l_star = int(np.argmax(search))
    return l_star, d_cf


def d_auroc_fisher_curves(
    K: np.ndarray, G_EE: np.ndarray, c: np.ndarray, y_t: np.ndarray, w_t: np.ndarray,
) -> dict:
    """Per-layer own-EASY-axis curve of a target set T (K:[L1,m,96]) at EVERY layer at once:
    Cohen's d, AUROC, Fisher ratio, and the raw projections (for downstream subsetting, e.g. N6's
    XSTest twin subset or N9's decode set)."""
    P = proj_curve(K, G_EE, c)
    return {
        "P": P,
        "d": cohens_d_w(P, y_t, w_t),
        "auroc": auroc_w(P, y_t, w_t),
        "fisher": fisher_ratio_w(P, y_t, w_t),
    }


# =====================================================================================
# 4. N7 two-sided gap: 20 splits x 2 folds, axis fit at a FIXED layer (l_star of N1;
#    documented ambiguity resolution -- spec does not name a separate l_star for N7)
# =====================================================================================
def _fixed_vs_varying_d(
    proj_fixed_k: np.ndarray, w_fixed: np.ndarray,          # [40,mF], [mF]  (mF group is same every k)
    proj_var_k: np.ndarray, w_var_k: np.ndarray,             # [40,mV], [40,mV] (group varies per k)
) -> np.ndarray:
    """Batched weighted Cohen's d of a FIXED-membership group (A) vs a per-fit-varying-membership
    group (B), one d per fit k. Vectorises n7's 40-fit loop (no python loop over k)."""
    nA = float(w_fixed.sum())
    muA = (proj_fixed_k * w_fixed[None, :]).sum(axis=1) / max(nA, EPS)          # [40]
    vA = ((proj_fixed_k - muA[:, None]) ** 2 * w_fixed[None, :]).sum(axis=1) / max(nA - 1, EPS)
    nB = w_var_k.sum(axis=1)                                                     # [40]
    with np.errstate(invalid="ignore", divide="ignore"):
        muB = (proj_var_k * w_var_k).sum(axis=1) / nB
        vB = ((proj_var_k - muB[:, None]) ** 2 * w_var_k).sum(axis=1) / np.maximum(nB - 1, EPS)
        sp = np.sqrt(((nA - 1) * vA + (nB - 1) * vB) / np.maximum(nA + nB - 2, 1.0))
        d = (muA - muB) / sp
    return np.where((nB < 2) | (sp < EPS), np.nan, d)


def n7_two_sided_gap(
    G_EE_l: np.ndarray, K_EH_l: np.ndarray, folds: list[np.ndarray],
    y_easy: np.ndarray, w_easy: np.ndarray, y_hard: np.ndarray, w_hard: np.ndarray,
    xstest_safe_mask_hard: np.ndarray,
) -> float:
    """20 splits x 2 folds = 40 fits: axis fit on the TRAIN fold (both classes) at this fixed
    layer (= N1's l_star); score = d(HARD y1 vs held-out Dolly) - d(XSTest safe twin vs held-out
    Dolly). Fully vectorised over the 40 fits (spec 5)."""
    if not folds:
        # BUGFIX (spec 8g): see crossfit_lstar -- no cross-fit fold could be built.
        return float("nan")
    y1_hard = (y_hard == 1)
    C, dolly_w = [], []
    for foldA in folds:
        for train_mask in (foldA, ~foldA):
            test_mask = ~train_mask
            C.append(axis_weight_vector(y_easy, w_easy, mask=train_mask))
            dolly_w.append(w_easy * (test_mask & (y_easy == 0)))
    C = np.stack(C, axis=0)                       # [40, 96]
    Wd = np.stack(dolly_w, axis=0)                 # [40, 96]  weight on held-out Dolly per fit
    proj_easy_k = C @ G_EE_l.T                     # [40, 96]  (G_EE_l symmetric)
    proj_hard_k = C @ K_EH_l.T                      # [40, 160]

    w1 = w_hard * y1_hard
    w2 = w_hard * xstest_safe_mask_hard
    d1 = _fixed_vs_varying_d(proj_hard_k[:, y1_hard], w1[y1_hard], proj_easy_k, Wd)
    d2 = _fixed_vs_varying_d(proj_hard_k[:, xstest_safe_mask_hard], w2[xstest_safe_mask_hard], proj_easy_k, Wd)
    diff = d1 - d2
    diff = diff[np.isfinite(diff)]
    return float(diff.mean()) if diff.size else float("nan")


# =====================================================================================
# 5. B7 / B7_nullproj (weights-only; spec section 2 + src_i3/b7_diagnostic.py)
# =====================================================================================
def _b7_from_vecs(vecs: np.ndarray) -> float:
    U = vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-12)
    return float(np.linalg.svd(U, compute_uv=False)[0] / np.sqrt(U.shape[0]))


def _least_vec_from_gram(G: np.ndarray, project_ones: bool) -> np.ndarray:
    import scipy.linalg as sla
    d = G.shape[0]
    if project_ones:
        one = np.ones(d) / np.sqrt(d)
        Gp = G - np.outer(one, one @ G) - np.outer(G @ one, one) + np.outer(one, one) * float(one @ G @ one)
        Gp += np.outer(one, one) * (np.trace(G) / d)
        G = 0.5 * (Gp + Gp.T)
    w, v = sla.eigh(G, subset_by_index=[0, 0], driver="evr")
    return v[:, 0]


def b7_values(ckpt: Ckpt) -> dict:
    """B7 (raw, = iteration-2 BL7_JORAK_A) and B7_nullproj (ones-projected). Weights-only, no
    prompts, so not affected by any prompt bootstrap draw -- computed once at full data."""
    out = {"B7": float("nan"), "B7_nullproj": float("nan")}
    if ckpt.vmin_stacked is not None:
        out["B7"] = _b7_from_vecs(ckpt.vmin_stacked.astype(np.float64))
    else:
        out["B7"] = NOT_AVAILABLE

    if ckpt.provenance == "artifact" and ckpt.vmin_onesproj is not None:
        out["B7_nullproj"] = _b7_from_vecs(ckpt.vmin_onesproj.astype(np.float64))
    elif ckpt.gram_dir is not None:
        gp = sorted(ckpt.gram_dir.glob("G_*.npy"))
        if gp:
            v_proj = np.array([_least_vec_from_gram(np.load(g).astype(np.float64), True) for g in gp])
            out["B7_nullproj"] = _b7_from_vecs(v_proj)
        else:
            out["B7_nullproj"] = NOT_AVAILABLE
    else:
        out["B7_nullproj"] = NOT_AVAILABLE
    return out


# =====================================================================================
# 6. BL1 family (spec e_bars: BL1_easy, BL1_hard, BL1_truelogit)
# =====================================================================================
def bl1_easy_hard(ckpt: Ckpt, w_stim: Optional[np.ndarray] = None,
                   y_easy_override: Optional[np.ndarray] = None) -> dict:
    stim = ckpt_stim(ckpt)
    y_easy = stim.y_easy if y_easy_override is None else y_easy_override
    L = ckpt.L
    drv = ckpt.r_refusal - ckpt.r_control                       # [N, L1]
    drv_easy = drv[stim.easy_idx]
    drv_hard = drv[stim.hard_idx]
    # sizes derived from stim (spec 8g: not hard-coded 96/160, so a reduced/smoke checkpoint's
    # ckpt_stim() view sizes these correctly instead of over- or under-running w_stim)
    w_easy = np.ones(stim.easy_idx.size) if w_stim is None else w_stim[stim.easy_idx]
    w_hard = np.ones(stim.hard_idx.size) if w_stim is None else w_stim[stim.hard_idx]

    def contrast(x, y, w):
        m1, m0 = y == 1, y == 0
        w1, w0 = w[m1], w[m0]
        if w1.sum() < EPS or w0.sum() < EPS:
            return float("nan")
        return float((x[m1] * w1).sum() / w1.sum() - (x[m0] * w0).sum() / w0.sum())

    return {
        "BL1_easy": contrast(drv_easy[:, L], y_easy, w_easy),
        "BL1_hard": contrast(drv_hard[:, L], stim.y_hard, w_hard),
    }


def _lse_rows(H: np.ndarray, W: np.ndarray) -> np.ndarray:
    z = H @ W.T
    m = z.max(1, keepdims=True)
    return (m + np.log(np.exp(z - m).sum(1, keepdims=True)))[:, 0]


def bl1_truelogit(ckpt: Ckpt, w_stim: Optional[np.ndarray] = None,
                   y_easy_override: Optional[np.ndarray] = None) -> dict:
    stim = ckpt_stim(ckpt)
    y_easy = stim.y_easy if y_easy_override is None else y_easy_override
    pc = ckpt._pc
    if pc and "g_easy_tl" in pc:
        g_easy, g_hard = pc["g_easy_tl"], pc["g_hard_tl"]
    else:
        HL_easy = ckpt.A_easy[:, ckpt.L, :]
        HL_hard = ckpt.A_hard[:, ckpt.L, :]
        g_easy = _lse_rows(HL_easy, ckpt.WU_ref) - _lse_rows(HL_easy, ckpt.WU_ctl)
        g_hard = _lse_rows(HL_hard, ckpt.WU_ref) - _lse_rows(HL_hard, ckpt.WU_ctl)
    w_easy = np.ones(stim.easy_idx.size) if w_stim is None else w_stim[stim.easy_idx]
    w_hard = np.ones(stim.hard_idx.size) if w_stim is None else w_stim[stim.hard_idx]

    def contrast(x, y, w):
        m1, m0 = y == 1, y == 0
        w1, w0 = w[m1], w[m0]
        if w1.sum() < EPS or w0.sum() < EPS:
            return float("nan")
        return float((x[m1] * w1).sum() / w1.sum() - (x[m0] * w0).sum() / w0.sum())

    return {
        "BL1_truelogit": contrast(g_easy, y_easy, w_easy),
        "BL1_truelogit_hard": contrast(g_hard, stim.y_hard, w_hard),
    }


# =====================================================================================
# 7. regex baseline (spec section 3 "regex"; e_bars "regex" == iteration-2 BL5_CARDREGEX)
#    reimplemented verbatim from src_h2/score_panel.py:card_regex_baseline / CARD_RE.
# =====================================================================================
CARD_RE = r"abliterat|uncensor|orthogonal|heretic|josiefied|no.?refus|jailbreak"
CARD_RE_NAMEFREE = r"uncensor|no.?refus|jailbreak|derestrict"

RUN_ROOT = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
D2_REGISTRY = RUN_ROOT / "iter_2/gen_art/gen_art_dataset_1/full_data_out.json"
_CARD_TEXT_CACHE: Optional[dict[str, str]] = None


def _card_text_registry() -> dict[str, str]:
    global _CARD_TEXT_CACHE
    if _CARD_TEXT_CACHE is not None:
        return _CARD_TEXT_CACHE
    out: dict[str, str] = {}
    if D2_REGISTRY.exists():
        doc = _jload(D2_REGISTRY)
        for ds in doc.get("datasets", []):
            if ds.get("dataset") == "qwen3_safety_iter2_substrate_v1::paired_lineage_registry":
                for ex in ds.get("examples", []):
                    repo = ex.get("input")
                    txt = ex.get("metadata_card_text_first_20kb")
                    if repo is not None:
                        out[repo] = txt or ""
    _CARD_TEXT_CACHE = out
    return out


def card_regex_baseline(repo: str, card_text: Optional[str] = None) -> dict:
    import re
    if card_text is None:
        card_text = _card_text_registry().get(repo)
    blob = (repo + " " + (card_text or "")).lower()
    name_free_blob = re.sub(r"abliterat\w*", " ", (card_text or "").lower())
    return {
        "regex": float(bool(re.search(CARD_RE, blob))),
        "regex_namefree": float(bool(re.search(CARD_RE_NAMEFREE, name_free_blob))),
        "regex_card_chars": len(card_text or ""),
        "regex_card_found": bool(card_text),
    }


# =====================================================================================
# 8. greedy_refusal_rate (spec section 3): needs WS/results/text_baseline.json (section 1,
#    marked "later" -- not produced by this deliverable). Returns NOT_AVAILABLE cleanly if
#    the file (or the tag's row) is missing.
# =====================================================================================
TEXT_BASELINE_PATH = WS / "results" / "text_baseline.json"


def greedy_refusal_rate(tag: str, harm_item_ids: Optional[list[str]] = None,
                         w_items: Optional[dict[str, float]] = None) -> Any:
    if not TEXT_BASELINE_PATH.exists():
        return NOT_AVAILABLE
    doc = _jload(TEXT_BASELINE_PATH)
    row = doc.get(tag)
    if row is None:
        return NOT_AVAILABLE
    ids = harm_item_ids if harm_item_ids is not None else list(row.keys())
    ids = [i for i in ids if i in row]
    if not ids:
        return NOT_AVAILABLE
    if w_items is None:
        vals = np.array([float(row[i]) for i in ids])
        return float(vals.mean())
    w = np.array([w_items.get(i, 0.0) for i in ids], dtype=np.float64)
    vals = np.array([float(row[i]) for i in ids])
    if w.sum() < EPS:
        return float("nan")
    return float((vals * w).sum() / w.sum())


# =====================================================================================
# 9. AMS (spec section 3: AMS_T1_sigma / AMS_T2_drift). Lazy import; NOT_AVAILABLE if the
#    module or A_ams.npy is missing.
# =====================================================================================
def _ams_module():
    try:
        return importlib.import_module("ams_reimpl")
    except Exception:  # noqa: BLE001
        return None


def ams_prompt_strata() -> Optional[np.ndarray]:
    mod = _ams_module()
    if mod is None:
        return None
    prompts = mod.ams_prompts()
    return np.array([f"{p['concept']}|{p['polarity']}" for p in prompts])


def ams_t1_values(ckpt: Ckpt, w_ams: Optional[np.ndarray] = None) -> Any:
    mod = _ams_module()
    if mod is None or ckpt.A_ams is None:
        return NOT_AVAILABLE
    prompts = mod.ams_prompts()
    res = mod.ams_tier1(ckpt.A_ams, prompts, ckpt.L, weights=w_ams)
    out = {"AMS_T1_sigma": res["mean_sigma"]}
    for c, v in res["per_concept"].items():
        out[f"AMS_T1_sigma_{c}"] = v["sigma"]
    return out


def ams_t2_values(ckpt_child: Ckpt, ckpt_parent: Ckpt, w_ams: Optional[np.ndarray] = None) -> Any:
    mod = _ams_module()
    if mod is None or ckpt_child.A_ams is None or ckpt_parent.A_ams is None:
        return NOT_AVAILABLE
    prompts = mod.ams_prompts()
    res = mod.ams_tier2(ckpt_child.A_ams, ckpt_parent.A_ams, prompts, ckpt_parent.L, weights=w_ams)
    return {"AMS_T2_drift": res["mean_separation_drift"], "AMS_T2_verified": res["verified"],
            "AMS_T2_mean_direction_similarity": res["mean_direction_similarity"]}


# =====================================================================================
# 10. top-level per-checkpoint, per-draw values() (spec section 7: `values(ckpt, weights=None)`)
# =====================================================================================
def values(
    ckpt: Ckpt, w_stim: Optional[np.ndarray] = None, y_easy_override: Optional[np.ndarray] = None,
    parent_l_star_N1: Optional[int] = None, w_c11: Optional[np.ndarray] = None,
) -> dict:
    """One weighted evaluation of every prompt-level candidate (spec section 3), on a checkpoint
    whose precompute() has already been called. `w_stim` is a [256] multiplicity vector over the
    ORIGINAL stimuli.json order (None == all-ones == full data); A_dec rows follow the HARD
    stimulus weights by construction (spec section 5). `y_easy_override` replaces the EASY labels
    (used by null_sd's shuffled-label draws) without touching HARD/c11/dec labels.
    `parent_l_star_N1`, when given, adds the N1_parentL companion (child scored at the PARENT's
    N1 l_star).
    """
    stim = ckpt_stim(ckpt)
    pc = ckpt._pc
    L, L1 = ckpt.L, ckpt.L + 1
    y_easy = stim.y_easy if y_easy_override is None else y_easy_override
    w_easy = np.ones(stim.easy_idx.size) if w_stim is None else np.asarray(w_stim, dtype=np.float64)[stim.easy_idx]
    w_hard = np.ones(stim.hard_idx.size) if w_stim is None else np.asarray(w_stim, dtype=np.float64)[stim.hard_idx]
    y_hard, w_hard_ = stim.y_hard, w_hard

    out: dict[str, Any] = {}

    # ---- full-EASY per-layer own-axis curves (unprojected): serves N1, C4/C7/C13/N4, N6, N11
    c_full = axis_weight_vector(y_easy, w_easy)
    curves = d_auroc_fisher_curves(pc["K_EH"], pc["G_EE"], c_full, y_hard, w_hard_)
    d_l, auc_l, fisher_l, P_hard = curves["d"], curves["auroc"], curves["fisher"], curves["P"]

    # C4 onset (= N4_shape "onset", also the companion needed for N8/C4 checks)
    tpr5_l = np.full(L1, np.nan)
    valid_l = np.arange(1, L1)
    tpr5_l[valid_l] = tpr_at_fpr_w(P_hard[valid_l], y_hard, w_hard_, 0.05)
    hit = [l for l in range(1, L1) if np.isfinite(tpr5_l[l]) and tpr5_l[l] >= 0.5]
    onset_layer = hit[0] if hit else L + 1
    out["C4"] = onset_layer / L
    out["C4_onset_layer"] = onset_layer

    # C7 trapezoid
    f = np.arange(L1) / L
    auc_f = np.nan_to_num(auc_l, nan=0.5)
    out["C7"] = float(np.trapezoid(auc_f, f))

    # C13 / C13_peak_d
    l5 = lay(0.5, L)
    out["C13"] = float(d_l[l5])
    with np.errstate(invalid="ignore"):
        out["C13_peak_d"] = float(np.nanmax(d_l[1:])) if np.isfinite(d_l[1:]).any() else float("nan")
        out["C13_peak_f"] = float((1 + int(np.nanargmax(d_l[1:]))) / L) if np.isfinite(d_l[1:]).any() else float("nan")

    # ---- N1: l_star via cross-fit search, N1 = d_l at l_star (full-EASY axis)
    l_star1, d_cf1 = crossfit_lstar(pc["G_EE"], pc["folds"], y_easy, w_easy, L)
    out["N1_l_star"] = l_star1
    out["_d_l_curve"] = d_l    # raw per-layer own-EASY-axis HARD-d curve (pairs.py uses this to
                                 # compute N1_parentL for the OTHER member of a pair without
                                 # recomputing the whole draw); leading underscore = not a scored
                                 # candidate, stripped before any numeric/JSON candidate listing.
    out["N1"] = float(d_l[l_star1])
    if parent_l_star_N1 is not None:
        out["N1_parentL"] = float(d_l[parent_l_star_N1])

    # ---- N4_shape components (peak_frac, width use the SAME d_l curve as C13/C4)
    out["N4_onset"] = out["C4"]
    out["N4_peak_frac"] = out["C13_peak_f"]
    finite = np.isfinite(d_l[1:])
    if finite.any():
        peak = np.nanmax(d_l[1:])
        width_count = int(np.sum(finite & (d_l[1:] >= 0.5 * peak))) if np.isfinite(peak) and peak > 0 else 0
        out["N4_width"] = width_count / L
    else:
        out["N4_width"] = float("nan")

    # ---- F_clust_raw = fisher_l at N1's l_star (unprojected)
    out["F_clust_raw"] = float(fisher_l[l_star1])

    # ---- N6: xstest harmful-twin(40) vs benign-twin(40), full-EASY axis at l_star1
    xh, xs = stim.xstest_harm_mask_hard, stim.xstest_safe_mask_hard
    p_l1 = P_hard[l_star1]
    out["N6"] = float(cohens_d_w(
        np.concatenate([p_l1[xh], p_l1[xs]]),
        np.concatenate([np.ones(int(xh.sum())), np.zeros(int(xs.sum()))]),
        np.concatenate([w_hard_[xh], w_hard_[xs]]),
    ))

    # ---- N11: mean Fisher ratio over l in [lay(0.4), lay(0.8)] (unprojected, own-axis curve)
    lo11, hi11 = lay(0.4, L), lay(0.8, L)
    band = fisher_l[lo11:hi11 + 1]
    out["N11"] = float(np.nanmean(band)) if np.isfinite(band).any() else float("nan")

    # ---- N7: two-sided gap (axis fit at N1's l_star; see n7_two_sided_gap docstring)
    out["N7"] = n7_two_sided_gap(
        pc["G_EE"][l_star1], pc["K_EH"][l_star1], pc["folds"], y_easy, w_easy, y_hard, w_hard_, xs,
    )

    # ---- N2 / N3 (projected space)
    l_star2, d_cf2 = crossfit_lstar(pc["G_EE_perp"], pc["folds"], y_easy, w_easy, L)
    c_full_perp = axis_weight_vector(y_easy, w_easy)
    curves2 = d_auroc_fisher_curves(pc["K_EH_perp"], pc["G_EE_perp"], c_full_perp, y_hard, w_hard_)
    out["N2_l_star"] = l_star2
    out["N2"] = float(curves2["d"][l_star2])
    out["N3"] = float(curves2["fisher"][l_star2])

    # ---- N8: Spearman(l_star1 projection on c11, severity)
    if "K_Ec11" in pc and ckpt.severity is not None:
        w_c11_ = np.ones(ckpt.A_c11.shape[0]) if w_c11 is None else np.asarray(w_c11, dtype=np.float64)
        p_c11 = proj_at_layer(pc["K_Ec11"][l_star1], pc["G_EE"][l_star1], c_full)
        out["N8"] = spearman_w(p_c11, ckpt.severity, w_c11_)
    else:
        out["N8"] = NOT_AVAILABLE

    # ---- N9 / N9_tok1 (at l_star1) and N10 (dec vs prompt at l75, both on full-EASY per-layer axis)
    l75 = lay(0.75, L)
    if "K_Edec" in pc:
        w_dec = w_hard_  # "A_dec rows follow their HARD stimulus weights" (spec section 5)
        dec_curves = d_auroc_fisher_curves(pc["K_Edec"], pc["G_EE"], c_full, y_hard, w_dec)
        out["N9"] = float(dec_curves["d"][l_star1])
        out["N10"] = float(dec_curves["d"][l75] - d_l[l75])
    else:
        out["N9"] = NOT_AVAILABLE
        out["N10"] = NOT_AVAILABLE
    if "K_Edec1" in pc:
        dec1_curves = d_auroc_fisher_curves(pc["K_Edec1"], pc["G_EE"], c_full, y_hard, w_hard_)
        out["N9_tok1"] = float(dec1_curves["d"][l_star1])
    else:
        out["N9_tok1"] = NOT_AVAILABLE

    # ---- BL1 family
    out.update(bl1_easy_hard(ckpt, w_stim=w_stim, y_easy_override=y_easy_override))
    out.update(bl1_truelogit(ckpt, w_stim=w_stim, y_easy_override=y_easy_override))

    return out


# =====================================================================================
# 11. null_sd (spec section 4)
# =====================================================================================
_NUMERIC_CAND_KEYS = (
    "N1", "N1_l_star", "N2", "N2_l_star", "N3", "F_clust_raw", "N4_onset", "N4_peak_frac",
    "N4_width", "N6", "N7", "N8", "N9", "N9_tok1", "N10", "N11", "C4", "C7", "C13", "C13_peak_d",
    "C13_peak_f",
)


def _signflip_null_sd(x: np.ndarray, y: np.ndarray, n_draws: int, seed: int) -> float:
    """BL1-type null (spec section 4): 'each item's centred contribution times +/-1'. The
    original contrast is sum_i w_i x_i with w_i = +1/n1 (y=1) or -1/n0 (y=0); since sum(w)=0 this
    equals sum_i w_i (x_i - xbar) for ANY constant xbar, so centring then Rademacher-flipping each
    item's contribution and re-summing gives the null draw."""
    x = np.asarray(x, dtype=np.float64)
    w = axis_weight_vector(y, np.ones(x.shape[0]))
    xbar = float(x.mean())
    contrib = w * (x - xbar)
    rng = np.random.default_rng(seed)
    signs = rng.integers(0, 2, size=(n_draws, x.size)) * 2 - 1
    draws = (contrib[None, :] * signs).sum(axis=1)
    return float(draws.std(ddof=1)) if draws.size >= 2 else float("nan")


def null_sd(ckpt: Ckpt, n_draws: int = 50, seed: int = 0) -> dict:
    """SD over 50 shuffled-EASY-label draws through the WHOLE pipeline (class counts kept;
    HARD/c11/dec labels untouched) for every fit-based candidate; BL1-type candidates get the
    random-sign null instead (section 4). Weights-only rows (B7/B7_nullproj) and regex: N/A."""
    stim = ckpt_stim(ckpt)
    n_easy = stim.y_easy.shape[0]   # 96 for every real checkpoint; spec 8g: not hard-coded, so
                                     # a reduced/smoke checkpoint's smaller EASY set still works
    draws: list[dict] = []
    for i in range(n_draws):
        rng = np.random.default_rng(seed * 7919 + i)
        # true label shuffle: reassign the EASY items new labels drawn from the SAME multiset
        # (keeps class counts, permutes assignment)
        y_perm = stim.y_easy[rng.permutation(n_easy)]
        draws.append(values(ckpt, w_stim=None, y_easy_override=y_perm))
    out: dict[str, Any] = {}
    for k in _NUMERIC_CAND_KEYS:
        vals = []
        for d in draws:
            v = d.get(k)
            if isinstance(v, (int, float)) and np.isfinite(v):
                vals.append(float(v))
        out[k] = float(np.std(np.array(vals), ddof=1)) if len(vals) >= 2 else float("nan")

    drv = ckpt.r_refusal - ckpt.r_control
    out["BL1_easy"] = _signflip_null_sd(drv[stim.easy_idx, ckpt.L], stim.y_easy, n_draws, seed + 1)
    out["BL1_hard"] = _signflip_null_sd(drv[stim.hard_idx, ckpt.L], stim.y_hard, n_draws, seed + 2)
    pc = ckpt._pc
    if pc and "g_easy_tl" in pc:
        out["BL1_truelogit"] = _signflip_null_sd(pc["g_easy_tl"], stim.y_easy, n_draws, seed + 3)
        out["BL1_truelogit_hard"] = _signflip_null_sd(pc["g_hard_tl"], stim.y_hard, n_draws, seed + 4)
    return out


# =====================================================================================
# 12. N5_invariance (spec section 3, parents only): max_p |N1(A_p) - N1(A_prompt)| / nullSD_N1
#     over available perturbation arrays. Caller (pairs.py) passes the paths; NOT_AVAILABLE
#     (never 0) when an array is missing.
# =====================================================================================
def n5_invariance(ckpt: Ckpt, n1_l_star: int, n1_value: float, null_sd_n1: float,
                   perturbation_paths: Optional[dict[str, Any]] = None) -> Any:
    """spec section 3 / e_candidates N5_invariance, amended to run on EVERY checkpoint dir that
    has at least one of A_prompt_p1/p2/p3 (not parents only): max_p |N1(A_p) - N1(A_prompt)| /
    nullSD_N1 over the available perturbation arrays, evaluated at THIS checkpoint's own N1
    l_star (ambiguity resolution, same spirit as N7's fixed-layer choice -- re-searching l_star
    on each perturbed render would be a second full crossfit per perturbation for a robustness
    diagnostic that is explicitly about the SAME axis/layer choice). `perturbation_paths` values
    may be a `Path`/str (loaded from disk) or an already-loaded `[256, L1, d]` ndarray (e.g. the
    checkpoint's own `ckpt.n5_perturbation_arrays()`); missing/absent entries -> NOT_AVAILABLE,
    never 0."""
    if not perturbation_paths:
        return NOT_AVAILABLE
    stim = ckpt_stim(ckpt)
    w_easy_ones = np.ones(stim.easy_idx.size)
    w_hard_ones = np.ones(stim.hard_idx.size)
    diffs = {}
    for name, p in perturbation_paths.items():
        if isinstance(p, np.ndarray):
            Ap = p.astype(np.float64)
        else:
            p = Path(p) if p else None
            if p is None or not p.exists():
                diffs[name] = NOT_AVAILABLE
                continue
            Ap = np.load(p).astype(np.float64)     # [256, L1, d], same row order as A_prompt
        if Ap.shape[0] != stim.rows.__len__():
            diffs[name] = NOT_AVAILABLE
            continue
        AE_p, AH_p = Ap[stim.easy_idx], Ap[stim.hard_idx]
        G_EE_p = np.einsum("nd,md->nm", AE_p[:, n1_l_star, :], AE_p[:, n1_l_star, :], optimize=True)
        K_EH_p = np.einsum("nd,md->nm", AH_p[:, n1_l_star, :], AE_p[:, n1_l_star, :], optimize=True)
        c_full = axis_weight_vector(stim.y_easy, w_easy_ones)
        p_hard = proj_at_layer(K_EH_p, G_EE_p, c_full)
        d_p = float(cohens_d_w(p_hard, stim.y_hard, w_hard_ones))
        diffs[name] = d_p - n1_value
    finite = [abs(v) for v in diffs.values() if isinstance(v, (int, float)) and np.isfinite(v)]
    if not finite or not np.isfinite(null_sd_n1) or null_sd_n1 < EPS:
        return {"N5_invariance": NOT_AVAILABLE, "per_perturbation_delta": diffs}
    return {"N5_invariance": float(max(finite) / null_sd_n1), "per_perturbation_delta": diffs}


# =====================================================================================
# 13. k-curve (spec section 6): N1, N2, N3, N6, N7, BL1_easy restricted to k EASY prompts
# =====================================================================================
def _k_subset_mask(y_easy: np.ndarray, k: int, seed: int) -> Optional[np.ndarray]:
    pos = np.flatnonzero(y_easy == 1)
    neg = np.flatnonzero(y_easy == 0)
    kh = k // 2
    if kh > min(pos.size, neg.size):
        return None
    rng = np.random.default_rng(seed)
    ip = rng.choice(pos, kh, replace=False)
    ineg = rng.choice(neg, kh, replace=False)
    m = np.zeros(y_easy.shape[0], dtype=np.float64)
    m[ip] = 1.0
    m[ineg] = 1.0
    return m


def _l_star_in_k(G_EE: np.ndarray, y_easy: np.ndarray, kmask: np.ndarray, L: int,
                  crossfit: bool, seed: int) -> int:
    """In-sample (k<16) or single 2-fold cross-fit (k>=16) l_star search WITHIN the k subset."""
    L1 = L + 1
    if not crossfit:
        c = axis_weight_vector(y_easy, kmask)
        curve = d_auroc_fisher_curves(G_EE, G_EE, c, y_easy, kmask)["d"]
    else:
        idx = np.flatnonzero(kmask > 0)
        rng = np.random.default_rng(seed + 555)
        pos = idx[y_easy[idx] == 1]
        neg = idx[y_easy[idx] == 0]
        pp, nn = rng.permutation(pos), rng.permutation(neg)
        foldA = np.zeros(y_easy.shape[0], dtype=bool)
        foldA[pp[: pos.size // 2]] = True
        foldA[nn[: neg.size // 2]] = True
        curves = []
        for train_mask in (foldA, (~foldA) & (kmask > 0)):
            test_mask = (kmask > 0) & (~train_mask)
            c = axis_weight_vector(y_easy, kmask, mask=train_mask)
            proj = np.einsum("lab,b->la", G_EE, c, optimize=True)
            curves.append(cohens_d_w(proj[:, test_mask], y_easy[test_mask], kmask[test_mask]))
        curve = np.nanmean(np.stack(curves), axis=0)
    search = np.where(np.isfinite(curve), curve, -np.inf)
    search[0] = -np.inf
    return int(np.argmax(search))


def k_curve_point(ckpt: Ckpt, k: int, seed: int) -> dict:
    """One seeded k-subset draw's N1, N2, N3, N6, N7, BL1_easy (spec section 6)."""
    stim = ckpt_stim(ckpt)
    pc = ckpt._pc
    L = ckpt.L
    w_hard_ones = np.ones(stim.hard_idx.size)   # spec 8g: sized from stim, not hard-coded 160
    kmask = _k_subset_mask(stim.y_easy, k, seed)
    out: dict[str, Any] = {}
    if kmask is None:
        return {k_: float("nan") for k_ in ("N1", "N2", "N3", "N6", "N7", "BL1_easy")}
    crossfit = k >= 16

    l1 = _l_star_in_k(pc["G_EE"], stim.y_easy, kmask, L, crossfit, seed)
    c1 = axis_weight_vector(stim.y_easy, kmask)
    curve1 = d_auroc_fisher_curves(pc["K_EH"], pc["G_EE"], c1, stim.y_hard, w_hard_ones)
    out["N1"] = float(curve1["d"][l1])
    xh, xs = stim.xstest_harm_mask_hard, stim.xstest_safe_mask_hard
    p1 = curve1["P"][l1]
    out["N6"] = float(cohens_d_w(
        np.concatenate([p1[xh], p1[xs]]),
        np.concatenate([np.ones(int(xh.sum())), np.zeros(int(xs.sum()))]),
        np.ones(int(xh.sum()) + int(xs.sum())),
    ))

    l2 = _l_star_in_k(pc["G_EE_perp"], stim.y_easy, kmask, L, crossfit, seed)
    c2 = axis_weight_vector(stim.y_easy, kmask)
    curve2 = d_auroc_fisher_curves(pc["K_EH_perp"], pc["G_EE_perp"], c2, stim.y_hard, w_hard_ones)
    out["N2"] = float(curve2["d"][l2])
    out["N3"] = float(curve2["fisher"][l2])

    out["N7"] = n7_two_sided_gap(pc["G_EE"][l1], pc["K_EH"][l1], pc["folds"], stim.y_easy, kmask,
                                  stim.y_hard, w_hard_ones, xs)

    # BL1_easy on the k subset only (drv is layer-L logit-lens gap; restrict to kmask members)
    drv = ckpt.r_refusal - ckpt.r_control
    x = drv[stim.easy_idx, L]
    w1 = kmask * (stim.y_easy == 1)
    w0 = kmask * (stim.y_easy == 0)
    if w1.sum() > EPS and w0.sum() > EPS:
        out["BL1_easy"] = float((x * w1).sum() / w1.sum() - (x * w0).sum() / w0.sum())
    else:
        out["BL1_easy"] = float("nan")
    return out


def k_curve_summary(ckpt: Ckpt, ks=(4, 8, 16, 32), n_seeds: int = 20, seed_base: int = 3000) -> dict:
    out: dict[str, Any] = {}
    for k in ks:
        pts = [k_curve_point(ckpt, k, seed_base + k * 100 + s) for s in range(n_seeds)]
        cand_keys = ("N1", "N2", "N3", "N6", "N7", "BL1_easy")
        row = {}
        for ck_ in cand_keys:
            vals = np.array([p[ck_] for p in pts], dtype=np.float64)
            vals = vals[np.isfinite(vals)]
            if vals.size:
                row[ck_] = {"mean": float(vals.mean()), "p05": float(np.percentile(vals, 5)),
                            "p95": float(np.percentile(vals, 95)), "n_valid": int(vals.size)}
            else:
                row[ck_] = {"mean": float("nan"), "p05": float("nan"), "p95": float("nan"), "n_valid": 0}
        out[str(k)] = row
    return out
