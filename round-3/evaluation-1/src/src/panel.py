"""Iter-3 CPU-only re-derivation / extension panel over iter-2's harvested activations.

No forward pass, no GPU. Pure numpy/sklearn over the cached A_prompt / A_resp / logit-lens
arrays iter-2 already wrote. Imports iter-2's exact numerics from iter2_numerics.py verbatim;
never re-derives auroc / cohens_d / crossfit_* / bootstrap definitions.
"""

from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

W = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_evaluation_1")
E = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_experiment_1")
HARVEST = E / "harvest"
RESULTS = W / "results"
CKPT_DIR = RESULTS / "panel_ckpt"
CACHE_DIR = RESULTS / "panel_cache"
LOG_DIR = W / "logs"
for p in (RESULTS, CKPT_DIR, CACHE_DIR, LOG_DIR):
    p.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(W / "src"))
import iter2_numerics as nm  # noqa: E402

logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(LOG_DIR / "panel.log", level="DEBUG", rotation="50 MB")

SEED = 921
FPR = 0.05
EPS = 1e-12

PRIORITY = [
    "Qwen--Qwen3-4B-Base", "Qwen--Qwen3-4B", "Qwen--Qwen3-4B-SafeRL",
    "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6", "mlabonne--Qwen3-4B-abliterated",
]
COMMISSIONED = list(PRIORITY)  # the 5 arms, in order


def jdump(obj: Any, path: Path) -> None:
    def clean(o):
        if isinstance(o, float):
            return None if not np.isfinite(o) else o
        if isinstance(o, (np.floating,)):
            v = float(o)
            return None if not np.isfinite(v) else v
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return clean(o.tolist())
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.bool_,)):
            return bool(o)
        return o
    path.write_text(json.dumps(clean(obj), indent=1))


def jload(path: Path) -> Any:
    return json.loads(path.read_text())


# ----------------------------------------------------------------------------------------
# Global, shared-across-checkpoints inputs
# ----------------------------------------------------------------------------------------
def load_stimuli() -> tuple[np.ndarray, np.ndarray]:
    d = jload(E / "out" / "released" / "stimuli.json")
    rows = d["rows"]
    y = np.array([r["y"] for r in rows], dtype=int)
    sid = np.array([r["set_id"] for r in rows], dtype=int)
    return y, sid


def load_cells() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    d = jload(E / "assets" / "cells.json")
    cells = d["cells"]
    req = np.array([1 if c["request_level"] == "harmful" else 0 for c in cells], dtype=int)
    cont = np.array([1 if c["prefix_level"] == "hazardous" else 0 for c in cells], dtype=int)
    uid = np.array([c["item_uid"] for c in cells])
    _, uid_codes = np.unique(uid, return_inverse=True)
    return req, cont, uid_codes


Y_ALL, SID_ALL = load_stimuli()
EASY = np.flatnonzero(SID_ALL == 0)
HARD = np.flatnonzero(SID_ALL == 1)
Y_EASY, Y_HARD = Y_ALL[EASY], Y_ALL[HARD]
REQ_LAB, CONT_LAB, UID_CODES = load_cells()

SCORED_CKPTS = jload(E / "results" / "scored_checkpoints.json")
RECOGNITION = jload(E / "results" / "recognition.json")
PAIRS_TABLE = jload(E / "results" / "pairs_table.json")


def all_tags() -> list[str]:
    tags = sorted(p.name for p in HARVEST.iterdir()
                  if p.is_dir() and (p / "A_prompt.npy").exists())
    pri = [t for t in PRIORITY if t in tags]
    rest = [t for t in tags if t not in PRIORITY]
    return pri + rest


def repo_to_tag(repo: str) -> str:
    return repo.replace("/", "--")


# ----------------------------------------------------------------------------------------
# Per-checkpoint loader
# ----------------------------------------------------------------------------------------
class Ckpt:
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.dir = HARVEST / tag
        self.meta = jload(self.dir / "meta.json")
        self.L = int(self.meta["n_layers"])
        self.d = int(self.meta["hidden_size"])
        self.A = np.load(self.dir / "A_prompt.npy").astype(np.float32)  # [256, L+1, d]
        self.L1 = self.A.shape[1]
        self.r_ref = self._maybe("r_refusal")
        self.r_ctl = self._maybe("r_control")
        self.gamma = self._maybe("gamma")
        self.WU_ref = self._maybe("WU_ref")
        self.WU_ctl = self._maybe("WU_ctl")
        self.rms_eps = float(self.meta.get("rms_eps", 1e-6))
        self.has_A_resp = (self.dir / "A_resp.npy").exists()

    def _maybe(self, name: str) -> np.ndarray | None:
        f = self.dir / f"{name}.npy"
        return np.load(f).astype(np.float32) if f.exists() else None

    def free(self) -> None:
        self.A = None
        gc.collect()


# ----------------------------------------------------------------------------------------
# (0) reproduction
# ----------------------------------------------------------------------------------------
def rmsnorm(h: np.ndarray, gamma: np.ndarray, eps: float) -> np.ndarray:
    h64 = h.astype(np.float64)
    var = np.mean(h64 * h64, axis=-1, keepdims=True)
    hn = h64 / np.sqrt(var + eps)
    return (hn * gamma.astype(np.float64))


def logsumexp(x: np.ndarray, axis: int = -1) -> np.ndarray:
    m = np.max(x, axis=axis, keepdims=True)
    return (m + np.log(np.sum(np.exp(x - m), axis=axis, keepdims=True))).squeeze(axis)


def reproduce_section0(ck: Ckpt, stored: dict) -> dict:
    out: dict[str, Any] = {}
    A, L1, L = ck.A, ck.L1, ck.L
    # BL1_easy
    if ck.r_ref is not None and ck.r_ctl is not None:
        drv = ck.r_ref - ck.r_ctl  # [256, L1]
        drv_easy = drv[EASY]
        bl1_easy = float(drv_easy[Y_EASY == 1, -1].mean() - drv_easy[Y_EASY == 0, -1].mean())
        out["BL1_easy_recomputed"] = bl1_easy
        out["BL1_easy_stored"] = stored.get("BL1_REFLOGIT")
        out["BL1_easy_assert_ok"] = (
            stored.get("BL1_REFLOGIT") is not None
            and abs(bl1_easy - stored["BL1_REFLOGIT"]) < 1e-3)
        # drive-gap curve (x8), EASY: harmful mean - benign mean at every layer, NOT smoothed
        gap_easy = drv_easy[Y_EASY == 1].mean(0) - drv_easy[Y_EASY == 0].mean(0)
        out["drive_gap_easy_curve"] = gap_easy
        peak_drive = float(np.max(gap_easy))
        out["peak_drive_recomputed"] = peak_drive
        stored_curve = stored.get("x8_drive_gap_curve")
        out["peak_drive_stored"] = float(np.max(stored_curve)) if stored_curve else None
        out["peak_drive_assert_ok"] = (
            stored_curve is not None
            and abs(peak_drive - float(np.max(stored_curve))) < 1e-3)
        out["peak_drive_layer"] = int(np.argmax(gap_easy))
        out["peak_is_final"] = bool(int(np.argmax(gap_easy)) == L1 - 1)
        # HARD drive gap
        drv_hard = drv[HARD]
        gap_hard = drv_hard[Y_HARD == 1].mean(0) - drv_hard[Y_HARD == 0].mean(0)
        out["drive_gap_hard_curve"] = gap_hard
        out["BL1_hard"] = float(gap_hard[-1])
        out["peak_drive_hard"] = float(np.max(gap_hard))
        out["peak_drive_hard_layer"] = int(np.argmax(gap_hard))
    else:
        drv = drv_easy = drv_hard = None
        out["BL1_easy_recomputed"] = None

    # l_dec (EASY, crossfit diffmeans AUROC >= 0.95, seed=921)
    au_easy = nm.crossfit_diffmeans_auroc_per_layer(A[EASY], Y_EASY, seed=SEED)
    ok = np.flatnonzero(np.nan_to_num(au_easy, nan=-1.0) >= 0.95)
    l_dec = int(ok[0]) if ok.size else int(np.nanargmax(au_easy))
    out["l_dec_recomputed"] = l_dec
    out["l_dec_stored"] = stored.get("l_dec")
    out["l_dec_assert_ok"] = (stored.get("l_dec") is not None and l_dec == stored["l_dec"])
    out["auroc_by_layer_easy"] = au_easy

    # l_star: in-sample EASY Cohen's d argmax
    U0 = nm.diffmeans_directions(A[EASY], Y_EASY)  # [L1,d]
    P0 = nm.project(A[EASY], U0)
    d_by_layer = np.array([nm.cohens_d(P0[Y_EASY == 1, l], P0[Y_EASY == 0, l]) for l in range(L1)])
    l_star = int(np.nanargmax(np.nan_to_num(d_by_layer, nan=-np.inf)))
    out["l_star_recomputed"] = l_star
    out["l_star_stored"] = stored.get("l_star")
    out["l_star_assert_ok"] = (stored.get("l_star") is not None and l_star == stored["l_star"])
    out["cohen_by_layer_easy_insample"] = d_by_layer
    out["d_cohen_lstar_recomputed"] = float(d_by_layer[l_star])
    out["d_cohen_lstar_stored"] = stored.get("d_cohen_lstar")

    # BL4_CLUSTSEP = fisher_ratio(crossfit_diffmeans_scores(A[easy,l_star], y, seed=921))
    s_dm = nm.crossfit_diffmeans_scores(A[EASY][:, l_star, :], Y_EASY, seed=SEED)
    okm = np.isfinite(s_dm)
    bl4 = nm.fisher_ratio(s_dm[okm], Y_EASY[okm])
    out["BL4_CLUSTSEP_recomputed"] = bl4
    out["BL4_CLUSTSEP_stored"] = stored.get("BL4_CLUSTSEP")
    out["BL4_CLUSTSEP_assert_ok"] = (
        stored.get("BL4_CLUSTSEP") is not None
        and np.isfinite(bl4) and abs(bl4 - stored["BL4_CLUSTSEP"]) < 1e-2 * max(1.0, abs(stored["BL4_CLUSTSEP"])))

    # BL7 = sigma1(row-normalised vmin_stacked) / sqrt(#layers)
    vmin = ck._maybe("vmin_stacked")
    if vmin is not None and vmin.ndim == 2 and vmin.shape[0] >= 2:
        Uv = vmin.astype(np.float64)
        Uv = Uv / np.maximum(np.linalg.norm(Uv, axis=1, keepdims=True), 1e-12)
        s1 = float(np.linalg.svd(Uv, compute_uv=False)[0])
        bl7 = s1 / float(np.sqrt(Uv.shape[0]))
        out["BL7_recomputed"] = bl7
        out["BL7_stored"] = stored.get("BL7_JORAK_A")
        out["BL7_assert_ok"] = (stored.get("BL7_JORAK_A") is not None
                                and abs(bl7 - stored["BL7_JORAK_A"]) < 1e-3)
    else:
        out["BL7_recomputed"] = None

    # X10_abs via x10_scar
    wmeta_f = ck.dir / "w_meta.json"
    svals = ck._maybe("svals_stacked")
    if wmeta_f.exists() and svals is not None:
        wm = jload(wmeta_f)
        part = wm.get("parts", {}).get("stacked")
        if part:
            svl = [svals[i] for i in range(svals.shape[0])]
            res = nm.x10_scar(svl, part["fro2"], [tuple(s) for s in part["shapes"]])
            out["X10_abs_recomputed"] = res["X10_abs"]
            out["X10_abs_stored"] = stored.get("X10_abs")
            out["X10_abs_assert_ok"] = (
                stored.get("X10_abs") is not None
                and abs(res["X10_abs"] - stored["X10_abs"]) < 1e-3)
    else:
        out["X10_abs_recomputed"] = None

    # RMSNorm reproduction test of r_refusal[:, l] for every layer
    if ck.r_ref is not None and ck.gamma is not None and ck.WU_ref is not None:
        err_a, err_b = [], []
        for l in range(L1):
            h = A[:, l, :]
            va = logsumexp(h.astype(np.float64) @ ck.WU_ref.T.astype(np.float64), axis=-1)
            hn = rmsnorm(h, ck.gamma, ck.rms_eps)
            vb = logsumexp(hn @ ck.WU_ref.T.astype(np.float64), axis=-1)
            true = ck.r_ref[:, l].astype(np.float64)
            err_a.append(float(np.mean(np.abs(va - true))))
            err_b.append(float(np.mean(np.abs(vb - true))))
        out["rmsnorm_test_mean_abs_err_variant_A_already_normed"] = float(np.mean(err_a))
        out["rmsnorm_test_mean_abs_err_variant_B_apply_gamma_rms"] = float(np.mean(err_b))
        out["rmsnorm_test_winner"] = (
            "B_apply_gamma_rms" if np.mean(err_b) < np.mean(err_a) else "A_already_normed")
    return out


# ----------------------------------------------------------------------------------------
# (1a) request-axis Cohen's d per layer, held out on HARD
# ----------------------------------------------------------------------------------------
def section1a(ck: Ckpt) -> dict:
    A, L1, L = ck.A, ck.L1, ck.L
    out: dict[str, Any] = {}
    U = nm.diffmeans_directions(A[EASY], Y_EASY)  # [L1,d], EASY-fit
    P_hard = nm.project(A[HARD], U)  # [160, L1]
    P_easy = nm.project(A[EASY], U)
    heldout_d = np.array([nm.cohens_d(P_hard[Y_HARD == 1, l], P_hard[Y_HARD == 0, l]) for l in range(L1)])
    insample_d = np.array([nm.cohens_d(P_easy[Y_EASY == 1, l], P_easy[Y_EASY == 0, l]) for l in range(L1)])
    heldout_auroc = np.array([nm.auroc(P_hard[:, l], Y_HARD) for l in range(L1)])
    heldout_tpr5 = np.array([nm.tpr_at_fpr(P_hard[:, l], Y_HARD, 0.05) for l in range(L1)])
    heldout_tpr1 = np.array([nm.tpr_at_fpr(P_hard[:, l], Y_HARD, 0.01) for l in range(L1)])
    peak_layer = int(np.nanargmax(np.nan_to_num(heldout_d, nan=-np.inf)))
    # DEGENERATE-TIE GUARD (see section1c): flag layers whose projection is exactly tied across
    # all HARD items (AUROC==0.5 to machine precision) -- their tpr5/tpr1 entries can read 1.0 as
    # a quantile-threshold artifact of a fully-tied score vector, not real detection.
    degenerate = [int(l) for l in range(L1) if abs(heldout_auroc[l] - 0.5) < 1e-9]
    out.update({
        "heldout_d": heldout_d, "insample_d": insample_d, "heldout_auroc": heldout_auroc,
        "heldout_tpr5": heldout_tpr5, "heldout_tpr1": heldout_tpr1, "degenerate_layers": degenerate,
        "peak_layer": peak_layer, "peak_depth": float(peak_layer / max(L, 1)),
        "peak_d": float(heldout_d[peak_layer]),
    })
    # item bootstrap B=1000, resample EASY (refit u) & HARD (rescore), stratified by class
    rng = np.random.default_rng(SEED)
    i1e, i0e = EASY[Y_EASY == 1], EASY[Y_EASY == 0]
    i1h, i0h = HARD[Y_HARD == 1], HARD[Y_HARD == 0]
    B = 1000
    d_draws = np.empty(B)
    tpr_draws = np.empty(B)
    for b in range(B):
        e1 = rng.choice(i1e, i1e.size, replace=True)
        e0 = rng.choice(i0e, i0e.size, replace=True)
        h1 = rng.choice(i1h, i1h.size, replace=True)
        h0 = rng.choice(i0h, i0h.size, replace=True)
        Ae = np.concatenate([A[e1, peak_layer, :], A[e0, peak_layer, :]])
        ye = np.concatenate([np.ones(e1.size), np.zeros(e0.size)])
        ub = nm.unit(Ae[ye == 1].mean(0) - Ae[ye == 0].mean(0))
        Ah = np.concatenate([A[h1, peak_layer, :], A[h0, peak_layer, :]])
        yh = np.concatenate([np.ones(h1.size), np.zeros(h0.size)])
        sc = Ah @ ub
        d_draws[b] = nm.cohens_d(sc[yh == 1], sc[yh == 0])
        tpr_draws[b] = nm.tpr_at_fpr(sc, yh, 0.05)
    out["peak_d_ci"] = [float(np.nanmean(d_draws)), float(np.nanquantile(d_draws, 0.025)),
                        float(np.nanquantile(d_draws, 0.975))]
    out["peak_tpr5_ci"] = [float(np.nanmean(tpr_draws)), float(np.nanquantile(tpr_draws, 0.025)),
                           float(np.nanquantile(tpr_draws, 0.975))]
    out["_U_easy"] = U  # kept internally for downstream sections / cross-ckpt cache
    return out


# ----------------------------------------------------------------------------------------
# (1b) k-budget curve
# ----------------------------------------------------------------------------------------
def section1b(ck: Ckpt, n_draws: int = 200) -> dict:
    A, L1 = ck.A, ck.L1
    out: dict[str, Any] = {}
    i1e, i0e = EASY[Y_EASY == 1], EASY[Y_EASY == 0]
    Ah = A[HARD]
    for k in (4, 8, 16, 32, 64):
        aurocs, tprs = [], []
        for r in range(n_draws):
            rng = np.random.default_rng(hash((ck.tag, k, r)) % (2**32))
            i1 = rng.choice(i1e, min(k, i1e.size), replace=False)
            i0 = rng.choice(i0e, min(k, i0e.size), replace=False)
            Asub = A[np.concatenate([i1, i0])]
            ysub = np.concatenate([np.ones(i1.size), np.zeros(i0.size)])
            best_l, best_d = 1, -np.inf
            for l in range(1, L1):
                m1 = Asub[ysub == 1, l, :].mean(0)
                m0 = Asub[ysub == 0, l, :].mean(0)
                u = nm.unit(m1 - m0)
                sc = Asub[:, l, :] @ u
                dd = nm.cohens_d(sc[ysub == 1], sc[ysub == 0])
                if np.isfinite(dd) and dd > best_d:
                    best_d, best_l = dd, l
            m1 = Asub[ysub == 1, best_l, :].mean(0)
            m0 = Asub[ysub == 0, best_l, :].mean(0)
            u = nm.unit(m1 - m0)
            sc_hard = Ah[:, best_l, :] @ u
            aurocs.append(nm.auroc(sc_hard, Y_HARD))
            tprs.append(nm.tpr_at_fpr(sc_hard, Y_HARD, 0.05))
        aurocs, tprs = np.array(aurocs), np.array(tprs)
        out[f"k{k}_auroc_mean"] = float(np.nanmean(aurocs))
        out[f"k{k}_auroc_p5"] = float(np.nanquantile(aurocs, 0.05))
        out[f"k{k}_auroc_p95"] = float(np.nanquantile(aurocs, 0.95))
        out[f"k{k}_tpr5_mean"] = float(np.nanmean(tprs))
        out[f"k{k}_tpr5_p5"] = float(np.nanquantile(tprs, 0.05))
        out[f"k{k}_tpr5_p95"] = float(np.nanquantile(tprs, 0.95))
    return out


# ----------------------------------------------------------------------------------------
# (1c) prompt-site depth profile + response site
# ----------------------------------------------------------------------------------------
def _hard_onset(au) -> int | None:
    v = np.asarray([float(x) if np.isfinite(x) else np.nan for x in (au if au is not None else [])])
    if v.size == 0 or not np.isfinite(np.nanmax(v)):
        return None
    thr = 0.5 + 0.9 * (np.nanmax(v) - 0.5)
    idx = np.flatnonzero(np.isfinite(v) & (v >= thr))
    return int(idx[0]) if idx.size else None


def cv_standardised_diffmeans(A_l: np.ndarray, y: np.ndarray, seed: int = SEED) -> np.ndarray:
    """5-fold stratified CV diff-in-means; each fold's held-out projection standardised by
    that fold's TRAINING portion mean/SD before pooling (per Section 1c spec)."""
    out = np.full(len(y), np.nan)
    for tr, te in nm._folds(y, 5, seed):
        u = nm.unit(A_l[tr][y[tr] == 1].mean(0) - A_l[tr][y[tr] == 0].mean(0))
        s_tr = A_l[tr] @ u
        s_te = A_l[te] @ u
        out[te] = (s_te - s_tr.mean()) / max(float(s_tr.std()), 1e-12)
    return out


def section1c(ck: Ckpt) -> dict:
    A, L1 = ck.A, ck.L1
    out: dict[str, Any] = {}
    Ah = A[HARD]
    cv_tpr1, cv_tpr5, cv_auroc = [], [], []
    for l in range(L1):
        s = cv_standardised_diffmeans(Ah[:, l, :], Y_HARD)
        ok = np.isfinite(s)
        cv_auroc.append(nm.auroc(s[ok], Y_HARD[ok]))
        cv_tpr5.append(nm.tpr_at_fpr(s[ok], Y_HARD[ok], 0.05))
        cv_tpr1.append(nm.tpr_at_fpr(s[ok], Y_HARD[ok], 0.01))
    cv_tpr5 = np.array(cv_tpr5)
    cv_auroc = np.array(cv_auroc)
    # DEGENERATE-TIE GUARD: a layer whose CV diff-means score is exactly constant (e.g. layer 0,
    # the pre-block embedding, whose diff-in-means direction can collapse to the zero vector)
    # reads AUROC==0.5 (chance) but iter-2's tpr_at_fpr quantile-threshold rule can still return
    # TPR==1.0 on a fully-tied score vector (the "higher" quantile of a tied negative sample
    # lands on the tie value itself, so every tied positive clears it too, at a REALISED FPR far
    # above the nominal 5%). Such layers are excluded from the onset search below and flagged,
    # never silently used to date the recognition onset one layer earlier than it really starts.
    degenerate = np.array([abs(cv_auroc[l] - 0.5) < 1e-9 for l in range(L1)])
    out["degenerate_layers"] = [int(l) for l in np.flatnonzero(degenerate)]
    onset_idx = np.flatnonzero((np.nan_to_num(cv_tpr5, nan=-1.0) >= 0.5) & ~degenerate)
    out["cv_auroc"] = cv_auroc
    out["cv_tpr5"] = cv_tpr5
    out["cv_tpr1"] = np.array(cv_tpr1)
    out["onset_tpr"] = int(onset_idx[0]) if onset_idx.size else None

    au_hard = nm.crossfit_diffmeans_auroc_per_layer(Ah, Y_HARD, seed=SEED)
    out["auroc_by_layer_hard"] = au_hard
    out["onset_hard"] = _hard_onset(au_hard)

    # response site
    if ck.has_A_resp:
        Ar = np.load(ck.dir / "A_resp.npy").astype(np.float32)  # [96, L1, 2, d]
        kf = ck.dir / "cell_kept.npy"
        kept = np.load(kf).astype(bool) if kf.exists() else np.ones(Ar.shape[0], bool)
        resp: dict[str, Any] = {}
        for w, wname in ((0, "EARLY"), (1, "LATE")):
            for lab, name, primary in ((REQ_LAB, "REQUEST", True), (CONT_LAB, "CONTINUATION", False)):
                aur, t5, t1 = [], [], []
                for l in range(Ar.shape[1]):
                    Xl = Ar[kept, l, w, :].astype(np.float32)
                    yl = lab[kept]
                    gl = UID_CODES[kept]
                    s = nm.crossfit_diffmeans_scores(Xl, yl, seed=SEED, groups=gl)
                    ok = np.isfinite(s)
                    aur.append(nm.auroc(s[ok], yl[ok]))
                    t5.append(nm.tpr_at_fpr(s[ok], yl[ok], 0.05))
                    t1.append(nm.tpr_at_fpr(s[ok], yl[ok], 0.01))
                n_neg = int((lab[kept] == 0).sum())
                resp[f"{wname}_{name}"] = {
                    "auroc": aur, "tpr5": t5,
                    "tpr1": t1 if n_neg >= 100 else "NOT_RESOLVABLE (n_neg<100)",
                    "n_neg": n_neg, "best_layer": int(np.nanargmax(np.nan_to_num(aur, nan=-1))),
                    "best_auroc": float(np.nanmax(aur)), "primary": primary,
                }
        out["resp"] = resp
        del Ar
        gc.collect()
    return out


# ----------------------------------------------------------------------------------------
# (1e) reproduce iter-2 R_TPR (nested HARD-set protocol)
# ----------------------------------------------------------------------------------------
def recognition_axis_repro(ck: Ckpt, seed: int = SEED) -> dict:
    from sklearn.model_selection import StratifiedKFold
    A = ck.A
    Ah, yh = A[HARD], Y_HARD
    outer = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed + 101)
    nest = np.full(len(yh), np.nan)
    chosen = []
    for tr, te in outer.split(np.zeros(len(yh)), yh):
        au_tr = nm.crossfit_diffmeans_auroc_per_layer(Ah[tr], yh[tr], seed=seed)
        l_o = int(np.nanargmax(np.nan_to_num(au_tr, nan=-np.inf)))
        chosen.append(l_o)
        u_o = nm.logistic_probe_direction(Ah[tr][:, l_o, :], yh[tr], seed=seed)
        s_tr = Ah[tr][:, l_o, :].astype(np.float64) @ u_o.astype(np.float64)
        s_te = Ah[te][:, l_o, :].astype(np.float64) @ u_o.astype(np.float64)
        nest[te] = (s_te - s_tr.mean()) / max(float(s_tr.std()), 1e-12)
    okn = np.isfinite(nest)
    l_mode = int(np.bincount(np.asarray(chosen)).argmax())
    return {
        "R_TPR5_repro": nm.tpr_at_fpr(nest[okn], yh[okn], 0.05),
        "R_TPR1_repro": nm.tpr_at_fpr(nest[okn], yh[okn], 0.01),
        "R_AUROC_repro": nm.auroc(nest[okn], yh[okn]),
        "R_layer_mode": l_mode,
        "probe_scores_repro": nest,
        "y_hard": yh,
    }


# ----------------------------------------------------------------------------------------
# (2a) fixed vs own axis accumulation test
# ----------------------------------------------------------------------------------------
def section2a(ck: Ckpt, U_easy: np.ndarray) -> dict:
    A, L1, L = ck.A, ck.L1, ck.L
    Ah = A[HARD]
    out: dict[str, Any] = {}
    for frac, key in ((0.25, "s25"), (0.36, "s36")):
        s = int(round(frac * L))
        s = max(0, min(s, L1 - 1))
        u_s = U_easy[s]
        rows = []
        cos_curve = []
        for l in range(s, L1):
            proj = Ah[:, l, :] @ u_s
            gap = float(proj[Y_HARD == 1].mean() - proj[Y_HARD == 0].mean())
            mean_norm = float(np.linalg.norm(Ah[:, l, :], axis=-1).mean())
            d_fixed = nm.cohens_d(proj[Y_HARD == 1], proj[Y_HARD == 0])
            u_l = U_easy[l]
            proj_own = Ah[:, l, :] @ u_l
            d_own = nm.cohens_d(proj_own[Y_HARD == 1], proj_own[Y_HARD == 0])
            cos = float(abs(u_s @ u_l))
            rows.append({"layer": l, "raw_gap": gap, "norm_gap": gap / max(mean_norm, EPS),
                        "d_fixed": d_fixed, "d_own": d_own, "cos": cos})
            cos_curve.append(cos)
        layers = np.array([r["layer"] for r in rows])
        norm_gap = np.array([r["norm_gap"] for r in rows])
        d_own = np.array([r["d_own"] for r in rows])
        raw_gap = np.array([r["raw_gap"] for r in rows])
        g_fixed_ratio = norm_gap / max(abs(norm_gap[0]), EPS)
        g_own_ratio = d_own / max(abs(d_own[0]), EPS)
        raw_ratio = raw_gap / max(abs(raw_gap[0]), EPS)
        rho = nm.spearman(layers.astype(float), norm_gap)
        # bootstrap B=500 resample HARD prompts stratified
        rng = np.random.default_rng(SEED + 1)
        i1, i0 = HARD[Y_HARD == 1], HARD[Y_HARD == 0]
        rho_draws, ratio_draws, start_d_draws = [], [], []
        peak_over_start_max = float(np.max(g_fixed_ratio))
        for b in range(500):
            r1 = rng.choice(i1, i1.size, replace=True)
            r0 = rng.choice(i0, i0.size, replace=True)
            idx = np.concatenate([r1, r0])
            ys = Y_ALL[idx]
            ng = []
            for l in layers:
                proj = A[idx, l, :] @ u_s
                gap_b = float(proj[ys == 1].mean() - proj[ys == 0].mean())
                mn = float(np.linalg.norm(A[idx, l, :], axis=-1).mean())
                ng.append(gap_b / max(mn, EPS))
                if l == layers[0]:
                    start_d_draws.append(nm.cohens_d(proj[ys == 1], proj[ys == 0]))
            ng = np.array(ng)
            rho_draws.append(nm.spearman(layers.astype(float), ng))
            ratio_draws.append(np.max(ng) / max(abs(ng[0]), EPS))
        rho_draws, ratio_draws = np.array(rho_draws), np.array(ratio_draws)
        start_d_draws = np.array(start_d_draws)
        rho_ci = [float(np.nanquantile(rho_draws, 0.025)), float(np.nanquantile(rho_draws, 0.975))]
        ratio_ci = [float(np.nanquantile(ratio_draws, 0.025)), float(np.nanquantile(ratio_draws, 0.975))]
        start_d = float(d_fixed if (d_fixed := rows[0]["d_fixed"]) is not None else np.nan)
        start_d_ci = [float(np.nanquantile(start_d_draws, 0.025)), float(np.nanquantile(start_d_draws, 0.975))]
        # START-GAP GATE: a peak/start RATIO is meaningless when the start value is not reliably
        # positive (sign can flip under resampling, blowing the ratio up or negative); on HARD
        # the EASY-fit axis at the deeper split (s36, layer ~13) reads a NEGATIVE start d for
        # every 4B arm, so the ratio there is UNDEFINED rather than reported as a number.
        gate_fail = bool(not np.isfinite(start_d) or start_d <= 0
                        or (start_d_ci[0] <= 0 <= start_d_ci[1]))
        cos_decay = bool(cos_curve[-1] < 0.8 * cos_curve[0]) if cos_curve else False
        own_grows = bool(np.isfinite(g_own_ratio[-1]) and g_own_ratio[-1] > 1.2 and d_own[0] != 0)
        if gate_fail:
            verdict = "UNDEFINED_START_GAP_NOT_POSITIVE"
            peak_over_start_out, ratio_ci_out = None, [None, None]
            raw_ratio_out = None
        elif rho_ci[0] > 0 and ratio_ci[0] > 1:
            verdict = "ACCUMULATION"
            peak_over_start_out, ratio_ci_out = peak_over_start_max, ratio_ci
            raw_ratio_out = float(np.max(raw_ratio))
        elif own_grows and cos_decay:
            verdict = "LAYER_SPECIFIC_DIRECTION"
            peak_over_start_out, ratio_ci_out = peak_over_start_max, ratio_ci
            raw_ratio_out = float(np.max(raw_ratio))
        else:
            verdict = "NO_GROWTH"
            peak_over_start_out, ratio_ci_out = peak_over_start_max, ratio_ci
            raw_ratio_out = float(np.max(raw_ratio))
        out[key] = {
            "s_layer": s, "spearman_normgap_layer": rho, "spearman_ci": rho_ci,
            "start_d": start_d, "start_d_ci": start_d_ci,
            "fixed_axis_peak_over_start_normgap": peak_over_start_out,
            "fixed_axis_peak_over_start_ci": ratio_ci_out,
            "fixed_axis_raw_gap_ratio_max_over_start": raw_ratio_out,
            "own_axis_d_ratio_max_over_start": float(np.max(g_own_ratio)),
            "cos_start": float(cos_curve[0]) if cos_curve else None,
            "cos_end": float(cos_curve[-1]) if cos_curve else None,
            "verdict": verdict,
            "fixed_axis_normgap_curve": norm_gap.tolist(),
            "own_axis_d_curve": d_own.tolist(),
            "cos_curve": cos_curve,
        }
        out[key]["easy_cv"] = section2a_easy_cv(A, U_easy, s, L1, layers, cos_curve)
    return out


EASY_FOLDS = None


def _easy_folds():
    global EASY_FOLDS
    if EASY_FOLDS is None:
        EASY_FOLDS = nm._folds(Y_EASY, 5, SEED)
    return EASY_FOLDS


def section2a_easy_cv(A: np.ndarray, U_easy: np.ndarray, s: int, L1: int,
                      layers: np.ndarray, cos_curve: list) -> dict:
    """In-distribution counterpart of the fixed-vs-own axis test: 5-fold stratified CV on the
    96 EASY prompts themselves (u_s and u_l refit on TRAIN folds only at layer s / l), pooled
    out-of-fold projections of the held-out EASY prompts. Cheap: no refitting inside the
    bootstrap -- the bootstrap resamples the already-pooled OOF scores directly."""
    Ae = A[EASY]
    folds = _easy_folds()
    n = Ae.shape[0]
    pooled_fixed = np.full((n, L1), np.nan)
    pooled_own = np.full((n, L1), np.nan)
    for tr, te in folds:
        ytr = Y_EASY[tr]
        u_s_fold = nm.unit(Ae[tr][ytr == 1, s, :].mean(0) - Ae[tr][ytr == 0, s, :].mean(0))
        for l in layers:
            pooled_fixed[te, l] = Ae[te, l, :] @ u_s_fold
            u_l_fold = nm.unit(Ae[tr][ytr == 1, l, :].mean(0) - Ae[tr][ytr == 0, l, :].mean(0))
            pooled_own[te, l] = Ae[te, l, :] @ u_l_fold
    raw_gap, norm_gap, d_fixed, d_own = [], [], [], []
    for l in layers:
        f, o = pooled_fixed[:, l], pooled_own[:, l]
        gap = float(f[Y_EASY == 1].mean() - f[Y_EASY == 0].mean())
        mn = float(np.linalg.norm(Ae[:, l, :], axis=-1).mean())
        raw_gap.append(gap)
        norm_gap.append(gap / max(mn, EPS))
        d_fixed.append(nm.cohens_d(f[Y_EASY == 1], f[Y_EASY == 0]))
        d_own.append(nm.cohens_d(o[Y_EASY == 1], o[Y_EASY == 0]))
    raw_gap, norm_gap = np.array(raw_gap), np.array(norm_gap)
    d_fixed, d_own = np.array(d_fixed), np.array(d_own)
    rho = nm.spearman(layers.astype(float), norm_gap)
    start_d = float(d_fixed[0]) if d_fixed.size else float("nan")
    # cheap bootstrap: resample the POOLED out-of-fold scores directly, no CV refit per draw
    rng = np.random.default_rng(SEED + 2)
    i1, i0 = np.flatnonzero(Y_EASY == 1), np.flatnonzero(Y_EASY == 0)
    rho_draws, ratio_draws, start_d_draws = [], [], []
    for b in range(500):
        r1 = rng.choice(i1, i1.size, replace=True)
        r0 = rng.choice(i0, i0.size, replace=True)
        idx = np.concatenate([r1, r0])
        ng, sd = [], None
        for j, l in enumerate(layers):
            f = pooled_fixed[idx, l]
            gap_b = float(f[Y_EASY[idx] == 1].mean() - f[Y_EASY[idx] == 0].mean())
            mn = float(np.linalg.norm(Ae[idx, l, :], axis=-1).mean())
            ng.append(gap_b / max(mn, EPS))
            if j == 0:
                sd = nm.cohens_d(f[Y_EASY[idx] == 1], f[Y_EASY[idx] == 0])
        ng = np.array(ng)
        rho_draws.append(nm.spearman(layers.astype(float), ng))
        ratio_draws.append(np.max(ng) / max(abs(ng[0]), EPS))
        start_d_draws.append(sd)
    rho_draws, ratio_draws = np.array(rho_draws), np.array(ratio_draws)
    start_d_draws = np.array(start_d_draws)
    rho_ci = [float(np.nanquantile(rho_draws, 0.025)), float(np.nanquantile(rho_draws, 0.975))]
    ratio_ci = [float(np.nanquantile(ratio_draws, 0.025)), float(np.nanquantile(ratio_draws, 0.975))]
    start_d_ci = [float(np.nanquantile(start_d_draws, 0.025)), float(np.nanquantile(start_d_draws, 0.975))]
    peak_over_start = float(np.max(norm_gap) / max(abs(norm_gap[0]), EPS)) if norm_gap.size else None
    gate_fail = bool(not np.isfinite(start_d) or start_d <= 0
                    or (start_d_ci[0] <= 0 <= start_d_ci[1]))
    own_ratio = float(np.max(d_own) / max(abs(d_own[0]), EPS)) if d_own.size and d_own[0] != 0 else None
    cos_decay = bool(cos_curve[-1] < 0.8 * cos_curve[0]) if cos_curve else False
    own_grows = bool(own_ratio is not None and np.isfinite(own_ratio) and own_ratio > 1.2)
    if gate_fail:
        verdict = "UNDEFINED_START_GAP_NOT_POSITIVE"
        peak_over_start_out, ratio_ci_out = None, [None, None]
    elif rho_ci[0] > 0 and ratio_ci[0] > 1:
        verdict = "ACCUMULATION"
        peak_over_start_out, ratio_ci_out = peak_over_start, ratio_ci
    elif own_grows and cos_decay:
        verdict = "LAYER_SPECIFIC_DIRECTION"
        peak_over_start_out, ratio_ci_out = peak_over_start, ratio_ci
    else:
        verdict = "NO_GROWTH"
        peak_over_start_out, ratio_ci_out = peak_over_start, ratio_ci
    return {
        "protocol": "5-fold stratified CV on the 96 EASY prompts; bootstrap resamples the "
                    "pooled out-of-fold scores directly (no per-draw refit) for speed.",
        "start_d": start_d, "start_d_ci": start_d_ci,
        "spearman_normgap_layer": rho, "spearman_ci": rho_ci,
        "fixed_axis_peak_over_start_normgap": peak_over_start_out,
        "fixed_axis_peak_over_start_ci": ratio_ci_out,
        "own_axis_d_ratio_max_over_start": own_ratio,
        "verdict": verdict,
        "fixed_axis_normgap_curve": norm_gap.tolist(),
        "own_axis_d_curve": d_own.tolist(),
    }


# ----------------------------------------------------------------------------------------
# Per-checkpoint driver
# ----------------------------------------------------------------------------------------
def process_ckpt(tag: str, do_1e: bool = True, k_draws: int = 200) -> dict:
    out_path = CKPT_DIR / f"{tag}.json"
    if out_path.exists():
        logger.info(f"{tag}: cached, skipping")
        return jload(out_path)
    t0 = time.time()
    logger.info(f"{tag}: loading")
    ck = Ckpt(tag)
    stored = ((SCORED_CKPTS.get(tag) or {}).get("real")) or {}
    result: dict[str, Any] = {
        "tag": tag, "n_layers": ck.L, "L1": ck.L1, "d_model": ck.d, "has_A_resp": ck.has_A_resp,
    }
    try:
        result["reproduction_asserts"] = reproduce_section0(ck, stored)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"{tag}: section0 failed")
        result["reproduction_asserts"] = {"error": repr(exc)}

    try:
        s1a = section1a(ck)
        U_easy = s1a.pop("_U_easy")
        result["section1a"] = s1a
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"{tag}: section1a failed")
        result["section1a"] = {"error": repr(exc)}
        U_easy = nm.diffmeans_directions(ck.A[EASY], Y_EASY)

    try:
        result["section1b_kbudget"] = section1b(ck, n_draws=k_draws)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"{tag}: section1b failed")
        result["section1b_kbudget"] = {"error": repr(exc)}

    try:
        result["section1c"] = section1c(ck)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"{tag}: section1c failed")
        result["section1c"] = {"error": repr(exc)}

    if do_1e:
        try:
            result["recognition_repro"] = recognition_axis_repro(ck)
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"{tag}: recognition_repro failed")
            result["recognition_repro"] = {"error": repr(exc)}

    try:
        result["section2a"] = section2a(ck, U_easy)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"{tag}: section2a failed")
        result["section2a"] = {"error": repr(exc)}

    # cross-checkpoint cache (.npz, small)
    try:
        peak_layer = result["section1a"]["peak_layer"]
        common_layer = int(round(0.5 * ck.L))
        A = ck.A
        drv = (ck.r_ref - ck.r_ctl) if (ck.r_ref is not None and ck.r_ctl is not None) else None
        np.savez_compressed(
            CACHE_DIR / f"{tag}.npz",
            y_hard=Y_HARD, y_easy=Y_EASY,
            hard_scores_peak=(A[HARD, peak_layer, :] @ U_easy[peak_layer]),
            hard_scores_common=(A[HARD, common_layer, :] @ U_easy[common_layer]),
            peak_layer=peak_layer, common_layer=common_layer, L=ck.L,
            drv_easy=(drv[EASY] if drv is not None else np.zeros((EASY.size, ck.L1))),
            drv_hard=(drv[HARD] if drv is not None else np.zeros((HARD.size, ck.L1))),
            U_easy=U_easy,
            l_star=result["reproduction_asserts"].get("l_star_recomputed", -1),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"{tag}: npz cache failed")

    result["runtime_s"] = time.time() - t0
    jdump(result, out_path)
    ck.free()
    del ck
    gc.collect()
    logger.info(f"{tag}: done in {result['runtime_s']:.1f}s")
    return result


# ----------------------------------------------------------------------------------------
# Cross-checkpoint stage
# ----------------------------------------------------------------------------------------
def paired_bootstrap(a: np.ndarray, b: np.ndarray, stat_fn, n_boot: int = 1000, seed: int = SEED,
                     ya: np.ndarray | None = None) -> dict:
    """Paired bootstrap over shared indices, stratified by class if ya given."""
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    if ya is not None:
        i1 = np.flatnonzero(ya[:n] == 1)
        i0 = np.flatnonzero(ya[:n] == 0)
        for k in range(n_boot):
            r1 = rng.choice(i1, i1.size, replace=True)
            r0 = rng.choice(i0, i0.size, replace=True)
            idx = np.concatenate([r1, r0])
            draws[k] = stat_fn(a[idx], b[idx], ya[idx])
    else:
        for k in range(n_boot):
            idx = rng.integers(0, n, n)
            draws[k] = stat_fn(a[idx], b[idx], None)
    point = stat_fn(a, b, ya)
    return {"point": float(point), "ci": [float(np.nanquantile(draws, 0.05)),
                                          float(np.nanquantile(draws, 0.95))],
           "ci95": [float(np.nanquantile(draws, 0.025)), float(np.nanquantile(draws, 0.975))],
           "draws": draws}


def cross_checkpoint(tags_done: list[str]) -> None:
    logger.info("cross-checkpoint stage starting")
    cache: dict[str, dict] = {}
    for t in tags_done:
        f = CACHE_DIR / f"{t}.npz"
        if f.exists():
            cache[t] = dict(np.load(f, allow_pickle=True))
    panel = {t: jload(CKPT_DIR / f"{t}.json") for t in tags_done if (CKPT_DIR / f"{t}.json").exists()}

    # -------- (3) pairs --------
    def score_pair(pair_id: str, parent_repo: str, child_repo: str, meta: dict) -> dict:
        p_tag, c_tag = repo_to_tag(parent_repo), repo_to_tag(child_repo)
        if p_tag not in cache or c_tag not in cache:
            return {"pair": pair_id, "status": "MISSING_HARVEST",
                    "parent": parent_repo, "child": child_repo}
        cp, cc = cache[p_tag], cache[c_tag]
        entry: dict[str, Any] = {"pair": pair_id, "parent": parent_repo, "child": child_repo, **meta}

        # held-out peak d, each at its own peak layer (already fixed) -> use hard_scores_peak
        yh = cp["y_hard"]
        r = paired_bootstrap(cc["hard_scores_peak"], cp["hard_scores_peak"],
                             lambda a, b, y: nm.cohens_d(a[y == 1], a[y == 0]) - nm.cohens_d(b[y == 1], b[y == 0]),
                             ya=yh)
        entry["delta_peak_d"] = r
        r = paired_bootstrap(cc["hard_scores_peak"], cp["hard_scores_peak"],
                             lambda a, b, y: nm.tpr_at_fpr(a, y, 0.05) - nm.tpr_at_fpr(b, y, 0.05),
                             ya=yh)
        entry["delta_tpr5_own_peak"] = r

        rc = (RECOGNITION.get(c_tag) or {})
        rp = (RECOGNITION.get(p_tag) or {})
        if rc.get("probe_scores") and rp.get("probe_scores") and rc.get("y_hard") and rp.get("y_hard"):
            sc, yc = np.array(rc["probe_scores"]), np.array(rc["y_hard"])
            sp_, yp = np.array(rp["probe_scores"]), np.array(rp["y_hard"])
            n = min(len(sc), len(sp_))
            rng = np.random.default_rng(SEED)
            i1 = np.flatnonzero(yc[:n] == 1)
            i0 = np.flatnonzero(yc[:n] == 0)
            draws = np.empty(1000)
            for k in range(1000):
                r1 = rng.choice(i1, i1.size, replace=True)
                r0 = rng.choice(i0, i0.size, replace=True)
                idx = np.concatenate([r1, r0])
                draws[k] = nm.tpr_at_fpr(sc[idx], yc[idx], 0.05) - nm.tpr_at_fpr(sp_[idx], yp[idx], 0.05)
            point = nm.tpr_at_fpr(sc[:n], yc[:n], 0.05) - nm.tpr_at_fpr(sp_[:n], yp[:n], 0.05)
            lo90, hi90 = float(np.quantile(draws, 0.05)), float(np.quantile(draws, 0.95))
            if lo90 > -0.05 and hi90 < 0.05:
                verdict = "EQUIVALENT"
            elif lo90 > 0.05 or hi90 < -0.05:
                verdict = "NOT_EQUIVALENT_SUPPORTED_CHANGE"
            elif not (lo90 <= 0 <= hi90):
                verdict = "NOT_EQUIVALENT_SUPPORTED_CHANGE"
            else:
                verdict = "INCONCLUSIVE_UNDERPOWERED"
            entry["delta_tpr5_recognition_json"] = {
                "point": float(point), "ci90": [lo90, hi90], "tost_verdict": verdict}

        r = paired_bootstrap(cc["drv_easy"], cp["drv_easy"],
                             lambda a, b, y: float(np.max(a[y == 1].mean(0) - a[y == 0].mean(0))
                                                   - np.max(b[y == 1].mean(0) - b[y == 0].mean(0))),
                             ya=Y_EASY)
        entry["delta_peak_drive_easy"] = r
        r = paired_bootstrap(cc["drv_easy"], cp["drv_easy"],
                             lambda a, b, y: float((a[y == 1].mean(0) - a[y == 0].mean(0))[-1]
                                                   - (b[y == 1].mean(0) - b[y == 0].mean(0))[-1]),
                             ya=Y_EASY)
        entry["delta_BL1_easy"] = r
        r = paired_bootstrap(cc["drv_hard"], cp["drv_hard"],
                             lambda a, b, y: float((a[y == 1].mean(0) - a[y == 0].mean(0))[-1]
                                                   - (b[y == 1].mean(0) - b[y == 0].mean(0))[-1]),
                             ya=Y_HARD)
        entry["delta_BL1_hard"] = r

        # |cos| parent-child harm direction: shallow quarter / deep half
        Up, Uc = cp["U_easy"], cc["U_easy"]
        if Up.shape == Uc.shape:
            cos = np.abs(np.einsum("ld,ld->l", Up, Uc))
            L1 = cos.size
            start = max(1, L1 // 4)
            half = L1 // 2
            entry["abs_cos_shallow_quarter_median"] = float(np.median(cos[1:start])) if start > 1 else None
            entry["abs_cos_deep_half_median"] = float(np.median(cos[half:]))
        return entry

    pairs_out = []
    for row in PAIRS_TABLE:
        pairs_out.append(score_pair(row["pair"], row["parent"], row["child"],
                                    {"effectiveness": row.get("effectiveness"),
                                     "delta_HC": row.get("delta_HC"),
                                     "delta_OR": row.get("delta_OR")}))
    LINEAGE = [
        ("Base->instruct", "Qwen/Qwen3-4B-Base", "Qwen/Qwen3-4B"),
        ("instruct->SafeRL", "Qwen/Qwen3-4B", "Qwen/Qwen3-4B-SafeRL"),
        ("Base->STaR", "Qwen/Qwen3-4B-Base", "CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6"),
    ]
    for pid, p_repo, c_repo in LINEAGE:
        pairs_out.append(score_pair(pid, p_repo, c_repo, {"kind": "lineage_contrast"}))
    jdump({"pairs": pairs_out}, RESULTS / "panel_pairs.json")

    # -------- (5) effective pairs summary + reconcile --------
    eff_rows = [r for r in pairs_out if r.get("effectiveness") == "EFFECTIVE"]
    d_peak = [r["delta_peak_drive_easy"]["point"] for r in eff_rows if "delta_peak_drive_easy" in r]
    d_bl1 = [r["delta_BL1_easy"]["point"] for r in eff_rows if "delta_BL1_easy" in r]
    rho_pd_bl1 = nm.spearman(np.array(d_peak), np.array(d_bl1)) if d_peak and d_bl1 else float("nan")
    reconcile = []

    def qr(name, quoted, recomputed):
        reconcile.append({"quantity": name, "quoted": quoted, "recomputed": recomputed})

    base_t, star_t, instr_t, saferl_t, abl_t = (
        "Qwen--Qwen3-4B-Base", "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6",
        "Qwen--Qwen3-4B", "Qwen--Qwen3-4B-SafeRL", "mlabonne--Qwen3-4B-abliterated")

    def get_repro(tag):
        return (panel.get(tag) or {}).get("recognition_repro") or {}

    qr("TPR@5%FPR HARD (Base/instruct/SafeRL/abliterated)", [0.475, 0.875, 0.850, 0.838],
      [get_repro(base_t).get("R_TPR5_repro"), get_repro(instr_t).get("R_TPR5_repro"),
       get_repro(saferl_t).get("R_TPR5_repro"), get_repro(abl_t).get("R_TPR5_repro")])
    qr("HARD onset layer (Base/instruct/SafeRL/abliterated)", [33, 19, 19, 19],
      [((panel.get(base_t) or {}).get("section1c") or {}).get("onset_hard"),
       ((panel.get(instr_t) or {}).get("section1c") or {}).get("onset_hard"),
       ((panel.get(saferl_t) or {}).get("section1c") or {}).get("onset_hard"),
       ((panel.get(abl_t) or {}).get("section1c") or {}).get("onset_hard")])

    def peak_drive_of(tag):
        return ((panel.get(tag) or {}).get("reproduction_asserts") or {}).get("peak_drive_recomputed")

    qr("peak drive (Base/instruct/SafeRL) + abliterated final(BL1)", [1.57, 4.92, 8.78, -1.96],
      [peak_drive_of(base_t), peak_drive_of(instr_t), peak_drive_of(saferl_t),
       ((panel.get(abl_t) or {}).get("reproduction_asserts") or {}).get("BL1_easy_recomputed")])
    qr("STaR peak drive", 2.57, peak_drive_of(star_t))
    qr("BL1 (Base / STaR)", [-0.30, 1.96],
      [((panel.get(base_t) or {}).get("reproduction_asserts") or {}).get("BL1_easy_recomputed"),
       ((panel.get(star_t) or {}).get("reproduction_asserts") or {}).get("BL1_easy_recomputed")])

    def k16(tag):
        return ((panel.get(tag) or {}).get("section1b_kbudget") or {}).get("k16_auroc_mean")

    qr("k=16 AUROC (Base/STaR/instruct/SafeRL) [iter-2 def may use Lane B arrays; ours = EASY-budget/HARD-score]",
      [0.528, 0.540, 0.679, 0.698],
      [k16(base_t), k16(star_t), k16(instr_t), k16(saferl_t)])

    med_bl1 = float(np.median(d_bl1)) if d_bl1 else None
    med_pd = float(np.median(d_peak)) if d_peak else None
    qr("BL1 median delta vs peak-drive median delta over EFFECTIVE pairs", [-2.86, -2.98],
      [med_bl1, med_pd])
    shal = [r["abs_cos_shallow_quarter_median"] for r in pairs_out
           if r.get("pair") == "P0" and r.get("abs_cos_shallow_quarter_median") is not None]
    deep = [r["abs_cos_deep_half_median"] for r in pairs_out
           if r.get("pair") == "P0" and r.get("abs_cos_deep_half_median") is not None]
    granite = [r for r in pairs_out if r.get("pair") == "P6"]
    qr("|cos| parent-child harm direction shallow/deep (P0 mlabonne) + granite (P6) shallow/deep",
      [0.992, 0.459, 0.984, 0.997],
      [shal[0] if shal else None, deep[0] if deep else None,
       granite[0].get("abs_cos_shallow_quarter_median") if granite else None,
       granite[0].get("abs_cos_deep_half_median") if granite else None])

    jdump({"reconcile": reconcile,
          "effective_pairs_delta_peak_drive_median": med_pd,
          "effective_pairs_delta_BL1_median": med_bl1,
          "spearman_delta_peakdrive_vs_deltaBL1": rho_pd_bl1,
          "n_effective_pairs": len(eff_rows)}, RESULTS / "panel_reconcile.json")

    # -------- (4) STaR panel --------
    star_out: dict[str, Any] = {}
    if base_t in cache and star_t in cache and instr_t in cache:
        cb, cs, ci = cache[base_t], cache[star_t], cache[instr_t]
        n = min(len(cb["hard_scores_peak"]), len(cs["hard_scores_peak"]), len(ci["hard_scores_peak"]))
        yh = cb["y_hard"][:n]
        rng = np.random.default_rng(SEED)
        i1, i0 = np.flatnonzero(yh == 1), np.flatnonzero(yh == 0)

        def resample():
            r1 = rng.choice(i1, i1.size, replace=True)
            r0 = rng.choice(i0, i0.size, replace=True)
            return np.concatenate([r1, r0])

        d_draws = np.empty(1000)
        for k in range(1000):
            idx = resample()
            db = nm.cohens_d(cb["hard_scores_peak"][:n][idx][yh[idx] == 1], cb["hard_scores_peak"][:n][idx][yh[idx] == 0])
            ds = nm.cohens_d(cs["hard_scores_peak"][:n][idx][yh[idx] == 1], cs["hard_scores_peak"][:n][idx][yh[idx] == 0])
            d_draws[k] = ds - db
        point = (nm.cohens_d(cs["hard_scores_peak"][:n][yh == 1], cs["hard_scores_peak"][:n][yh == 0])
                - nm.cohens_d(cb["hard_scores_peak"][:n][yh == 1], cb["hard_scores_peak"][:n][yh == 0]))
        lo, hi = float(np.quantile(d_draws, 0.05)), float(np.quantile(d_draws, 0.95))
        verdict = "EQUIVALENT" if (lo > -0.5 and hi < 0.5) else (
            "DIFFERENT" if (lo > 0.5 or hi < -0.5) else "INCONCLUSIVE")
        star_out["heldout_peak_d_diff_STaR_minus_Base"] = {
            "point": float(point), "ci90": [lo, hi], "tost_margin": 0.5, "tost_verdict": verdict}

        ne = min(len(cb["drv_easy"]), len(cs["drv_easy"]), len(ci["drv_easy"]))
        ye = Y_EASY[:ne]
        rng2 = np.random.default_rng(SEED + 1)
        j1, j0 = np.flatnonzero(ye == 1), np.flatnonzero(ye == 0)
        ratios = {"heldout_peak_d": [], "peak_drive": [], "BL1_easy": [], "BL1_hard": []}
        nh = min(len(cb["drv_hard"]), len(cs["drv_hard"]), len(ci["drv_hard"]))
        yhh = Y_HARD[:nh]
        for k in range(1000):
            re1 = rng2.choice(j1, j1.size, replace=True)
            re0 = rng2.choice(j0, j0.size, replace=True)
            idxe = np.concatenate([re1, re0])
            gb = cb["drv_easy"][:ne][idxe][ye[idxe] == 1].mean(0) - cb["drv_easy"][:ne][idxe][ye[idxe] == 0].mean(0)
            gs = cs["drv_easy"][:ne][idxe][ye[idxe] == 1].mean(0) - cs["drv_easy"][:ne][idxe][ye[idxe] == 0].mean(0)
            gi = ci["drv_easy"][:ne][idxe][ye[idxe] == 1].mean(0) - ci["drv_easy"][:ne][idxe][ye[idxe] == 0].mean(0)
            denom_pd = float(np.max(gi) - np.max(gb))
            ratios["peak_drive"].append((np.max(gs) - np.max(gb)) / denom_pd if abs(denom_pd) > 1e-9 else np.nan)
            denom_bl1e = float(gi[-1] - gb[-1])
            ratios["BL1_easy"].append((gs[-1] - gb[-1]) / denom_bl1e if abs(denom_bl1e) > 1e-9 else np.nan)
            idxh = np.concatenate([rng2.choice(np.flatnonzero(yhh == 1), int((yhh == 1).sum()), replace=True),
                                   rng2.choice(np.flatnonzero(yhh == 0), int((yhh == 0).sum()), replace=True)])
            # held-out peak-d fraction: same HARD resample applied to each ckpt's own cached
            # peak-layer scores (n is the pre-truncated common length used above)
            idxh_n = idxh[idxh < n]
            if idxh_n.size >= 4:
                yb_ = yh[idxh_n]
                db_ = nm.cohens_d(cb["hard_scores_peak"][:n][idxh_n][yb_ == 1], cb["hard_scores_peak"][:n][idxh_n][yb_ == 0])
                ds_ = nm.cohens_d(cs["hard_scores_peak"][:n][idxh_n][yb_ == 1], cs["hard_scores_peak"][:n][idxh_n][yb_ == 0])
                di_ = nm.cohens_d(ci["hard_scores_peak"][:n][idxh_n][yb_ == 1], ci["hard_scores_peak"][:n][idxh_n][yb_ == 0])
                denom_hd = float(di_ - db_)
                ratios["heldout_peak_d"].append((ds_ - db_) / denom_hd if abs(denom_hd) > 1e-9 else np.nan)
            hb = cb["drv_hard"][:nh][idxh][yhh[idxh] == 1].mean(0) - cb["drv_hard"][:nh][idxh][yhh[idxh] == 0].mean(0)
            hs = cs["drv_hard"][:nh][idxh][yhh[idxh] == 1].mean(0) - cs["drv_hard"][:nh][idxh][yhh[idxh] == 0].mean(0)
            hi_ = ci["drv_hard"][:nh][idxh][yhh[idxh] == 1].mean(0) - ci["drv_hard"][:nh][idxh][yhh[idxh] == 0].mean(0)
            denom_bl1h = float(hi_[-1] - hb[-1])
            ratios["BL1_hard"].append((hs[-1] - hb[-1]) / denom_bl1h if abs(denom_bl1h) > 1e-9 else np.nan)
        for k, v in ratios.items():
            v = np.array(v)
            star_out[f"fraction_{k}"] = {
                "mean": float(np.nanmean(v)), "ci90": [float(np.nanquantile(v, 0.05)),
                                                       float(np.nanquantile(v, 0.95))],
                "note": "ratio CI may be unstable per spec"}
    jdump(star_out, RESULTS / "panel_star.json")
    logger.info("cross-checkpoint stage done")


def second_pass_section2a(tags: list[str]) -> None:
    """Cheap re-pass: reload A_prompt one checkpoint at a time (~5s each), recompute ONLY
    section2a (now with the easy_cv variant and the start-gap gate) and patch it into the
    already-written per-checkpoint JSON. Leaves every other section untouched."""
    for t in tags:
        f = CKPT_DIR / f"{t}.json"
        if not f.exists():
            continue
        t0 = time.time()
        try:
            ck = Ckpt(t)
            U_easy = nm.diffmeans_directions(ck.A[EASY], Y_EASY)
            new_s2a = section2a(ck, U_easy)
            doc = jload(f)
            doc["section2a"] = new_s2a
            jdump(doc, f)
            ck.free()
            del ck
            gc.collect()
            logger.info(f"{t}: second-pass section2a done in {time.time()-t0:.1f}s")
        except Exception:
            logger.exception(f"{t}: second-pass section2a FAILED")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="*", default=None)
    ap.add_argument("--k-draws", type=int, default=200)
    ap.add_argument("--no-1e", action="store_true")
    ap.add_argument("--cross-only", action="store_true")
    ap.add_argument("--second-pass-2a", action="store_true")
    args = ap.parse_args()

    tags = args.tags if args.tags else all_tags()
    done = []
    if args.second_pass_2a:
        done = [t for t in tags if (CKPT_DIR / f"{t}.json").exists()]
        second_pass_section2a(done)
        cross_checkpoint(done)
        return 0
    if not args.cross_only:
        for t in tags:
            try:
                process_ckpt(t, do_1e=not args.no_1e, k_draws=args.k_draws)
            except Exception:
                logger.exception(f"{t}: FATAL, skipping")
            done.append(t)
    else:
        done = [t.stem for t in CKPT_DIR.glob("*.json")]
    cross_checkpoint([t for t in done if (CKPT_DIR / f"{t}.json").exists()])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
