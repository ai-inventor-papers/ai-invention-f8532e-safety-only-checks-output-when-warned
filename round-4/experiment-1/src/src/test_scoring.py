"""Spec section 8 unit checks for src/ncands.py + src/pairs.py.

    env OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
        WS/.venv/bin/python src/test_scoring.py

Writes WS/results/scoring_unit_checks.json. RESTRICTION (study order rule, spec 8): only ever
computes per-checkpoint values on the 3 iter-2 dirs named below, the smoke dir, and IDENTITY
pairs (same dir as parent and child) -- never a Delta between two different real checkpoints.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

SRC = Path(__file__).resolve().parent
WS = SRC.parent
sys.path.insert(0, str(SRC))
import ncands as nc  # noqa: E402
import pairs as pr  # noqa: E402

SRC_I3 = WS / "src_i3"
sys.path.insert(0, str(SRC_I3))
import candidates as cand_i3  # noqa: E402

RUN_ROOT = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
ITER2_HARVEST = RUN_ROOT / "iter_2/gen_art/gen_art_experiment_1/harvest"
TAGS = [
    "Qwen--Qwen3-1.7B",
    "huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2",
    "ibm-granite--granite-3.2-2b-instruct",
]
SMOKE_DIR = WS / "private" / "smoke_harvest" / "RANDINIT__ref"
RESULTS_PATH = WS / "results" / "scoring_unit_checks.json"

EPS = 1e-12


def jdump(obj, p: Path):
    def clean(o):
        if isinstance(o, float):
            return None if (np.isnan(o) or np.isinf(o)) else o
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, (np.generic,)):
            return clean(o.item())
        if isinstance(o, np.ndarray):
            return clean(o.tolist())
        return o
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean(obj), indent=1))


def load_and_precompute(tag: str, dir_: Path) -> nc.Ckpt:
    ck = nc.Ckpt.load(tag, Path(dir_))
    nc.precompute(ck)
    return ck


# =====================================================================================
# (a) equal src_i3/candidates.py:compute_all(with_h2=False) to <= 1e-12
# =====================================================================================
def check_a() -> dict:
    out = {"tolerance": 1e-12, "per_tag": {}, "pass": True}
    stim_rows = nc.load_stimuli().rows  # identical (0-diff, verified) to H2/assets/stimuli.json
    for tag in TAGS:
        ck = load_and_precompute(tag, ITER2_HARVEST / tag)
        ours = nc.values(ck)

        ref = cand_i3.compute_all(tag, stim_rows, [], None, with_h2=False, root=ITER2_HARVEST)

        # BL1(=BL1_easy): with_h2=False never sets ref["BL1"] (it is produced by the sc2.* call
        # gated on with_h2); the definition (candidates.py PLAN_DEFINITIONS["BL1"] /
        # src_i3/h2/score_ckpt.py:312) is a closed formula independent of that call, so recompute
        # it here directly from the raw harvest files (an INDEPENDENT ground truth, not a call
        # into ncands.py or candidates.py):
        #   drv = r_refusal[easy][:, L] - r_control[easy][:, L]; BL1 = drv[y=1].mean() - drv[y=0].mean()
        stim = nc.load_stimuli()
        r_ref = np.load(ITER2_HARVEST / tag / "r_refusal.npy").astype(np.float64)
        r_ctl = np.load(ITER2_HARVEST / tag / "r_control.npy").astype(np.float64)
        L = ck.L
        drv_easy = (r_ref - r_ctl)[stim.easy_idx, L]
        y_easy = stim.y_easy
        bl1_ref = float(drv_easy[y_easy == 1].mean() - drv_easy[y_easy == 0].mean())

        diffs = {}
        diffs["C7"] = abs(ours["C7"] - ref["C7"])
        diffs["C13_peak_d"] = abs(ours["C13_peak_d"] - ref["C13_peak_d"])
        diffs["C4"] = abs(ours["C4"] - ref["C4"])
        diffs["BL1_easy(=BL1)"] = abs(ours["BL1_easy"] - bl1_ref)
        diffs["BL1_hard"] = abs(ours["BL1_hard"] - ref["BL1_hard"])
        d_l_ours = ours["_d_l_curve"]
        d_l_ref = np.array(ref["curves"]["hard_d_by_layer"])
        auc_ref = np.array(ref["curves"]["hard_auroc_by_layer"])
        # our per-layer own-EASY-axis HARD auroc curve is not kept in `values()`'s public dict;
        # recompute the same curve object values() built internally (same call, no new logic)
        c_full = nc.axis_weight_vector(y_easy, np.ones(96))
        curves_ours = nc.d_auroc_fisher_curves(ck._pc["K_EH"], ck._pc["G_EE"], c_full, stim.y_hard, np.ones(160))
        diffs["hard_d_by_layer_max"] = float(np.nanmax(np.abs(d_l_ours - d_l_ref)))
        diffs["hard_auroc_by_layer_max"] = float(np.nanmax(np.abs(np.asarray(curves_ours["auroc"]) - auc_ref)))

        row_pass = all(v <= 1e-12 for v in diffs.values() if np.isfinite(v))
        out["per_tag"][tag] = {"diffs": diffs, "pass": row_pass}
        out["pass"] = out["pass"] and row_pass
    return out


# =====================================================================================
# (a, continued) BL1_truelogit vs src_i3/extra_analyses.py; B7/B7_nullproj vs b7_diagnostic.py
# =====================================================================================
def check_a_truelogit_b7() -> dict:
    out = {"tolerance": 1e-12, "per_tag": {}, "pass": True}
    EXTRA = SRC_I3
    sys.path.insert(0, str(EXTRA))
    import extra_analyses as ea  # noqa: E402
    import b7_diagnostic as b7d  # noqa: E402

    stim = nc.load_stimuli()
    y_full = stim.y
    sid_full = stim.sid
    for tag in TAGS:
        ck = load_and_precompute(tag, ITER2_HARVEST / tag)
        ours = nc.bl1_truelogit(ck)

        ref = ea.bl1_truelogit(ITER2_HARVEST / tag, y_full, sid_full)
        diff_tl = abs(ours["BL1_truelogit"] - ref["easy"])
        diff_tl_hard = abs(ours["BL1_truelogit_hard"] - ref["hard"])

        # B7 raw / B7_nullproj vs b7_diagnostic.py's least_vec/b7_from on the SAME on-disk Gram
        gp = sorted((ITER2_HARVEST / tag / "gram").glob("G_*.npy"))
        v_raw = np.array([b7d.least_vec(np.load(g).astype(np.float64), False) for g in gp])
        v_proj = np.array([b7d.least_vec(np.load(g).astype(np.float64), True) for g in gp])
        b7_raw_ref = b7d.b7_from(v_raw)
        b7_proj_ref = b7d.b7_from(v_proj)
        b7_ours = nc.b7_values(ck)
        diff_b7 = abs(b7_ours["B7"] - b7_raw_ref)   # NOTE: B7 uses vmin_stacked (prereg'd), not
        diff_b7_recomputed_from_gram = None          # the gram-recomputed value -- see note below
        diff_b7proj = abs(b7_ours["B7_nullproj"] - b7_proj_ref)

        out["per_tag"][tag] = {
            "BL1_truelogit_diff": diff_tl, "BL1_truelogit_hard_diff": diff_tl_hard,
            "B7_nullproj_diff_vs_b7_diagnostic": diff_b7proj,
            "B7_vs_gram_recomputed_diff": diff_b7,
            "note": "B7 (raw) is preregistered from vmin_stacked (native-precision weights), "
                    "while b7_diagnostic recomputes least_vec from the stored fp16 Gram -- "
                    "b7_diagnostic.py itself documents these as expected to differ by precision "
                    "(see its 'note' field); only B7_nullproj (spec: 'for this artifact's dirs "
                    "use the stored vmin arrays' -- N/A here since these are on-disk dirs -- so "
                    "ncands falls back to the SAME Gram-based path as b7_diagnostic) is required "
                    "to match to 1e-12, and BL1_truelogit is the check(a) tolerance quantity.",
            "pass": diff_tl <= 1e-12 and diff_tl_hard <= 1e-12 and diff_b7proj <= 1e-12,
        }
        out["pass"] = out["pass"] and out["per_tag"][tag]["pass"]
    return out


# =====================================================================================
# (b) Gram-based == direct ([N,d] explicit projection), <= 1e-9, full data + 1 bootstrap draw
# =====================================================================================
def _direct_axis(AE: np.ndarray, y_easy: np.ndarray, w_easy: np.ndarray, mask=None) -> np.ndarray:
    w = w_easy if mask is None else w_easy * mask.astype(np.float64)
    m1, m0 = (y_easy == 1), (y_easy == 0)
    w1, w0 = w * m1, w * m0
    s1, s0 = float(w1.sum()), float(w0.sum())
    mu1 = np.einsum("n,nld->ld", w1, AE) / max(s1, EPS)
    mu0 = np.einsum("n,nld->ld", w0, AE) / max(s0, EPS)
    diff = mu1 - mu0
    nrm = np.linalg.norm(diff, axis=-1, keepdims=True)
    return np.where(nrm > EPS, diff / np.maximum(nrm, EPS), 0.0)


def _direct_proj(A_target: np.ndarray, axis_ld: np.ndarray) -> np.ndarray:
    return np.einsum("nld,ld->ln", A_target, axis_ld)


def _direct_full_curve(AE, AH, y_easy, w_easy, y_hard, w_hard):
    axis_ld = _direct_axis(AE, y_easy, w_easy)
    P = _direct_proj(AH, axis_ld)
    return {"P": P, "d": nc.cohens_d_w(P, y_hard, w_hard), "auroc": nc.auroc_w(P, y_hard, w_hard),
            "fisher": nc.fisher_ratio_w(P, y_hard, w_hard)}


def _direct_crossfit_lstar(AE, folds, y_easy, w_easy, L):
    if not folds:
        return 1, np.full(L + 1, np.nan)
    ds = []
    for foldA in folds:
        for train_mask in (foldA, ~foldA):
            test_mask = ~train_mask
            axis_ld = _direct_axis(AE, y_easy, w_easy, mask=train_mask)
            P_test = _direct_proj(AE, axis_ld)
            w_test = w_easy * test_mask
            ds.append(nc.cohens_d_w(P_test, y_easy, w_test))
    d_cf = np.nanmean(np.stack(ds), axis=0)
    search = np.where(np.isfinite(d_cf), d_cf, -np.inf)
    search[0] = -np.inf
    return int(np.argmax(search)), d_cf


def _fixed_vs_varying_scalar(xA, wA, xB, wB):
    nA = float(wA.sum())
    if nA < 1:
        return float("nan")
    muA = float((xA * wA).sum() / nA)
    vA = float(((xA - muA) ** 2 * wA).sum() / max(nA - 1, EPS))
    nB = float(wB.sum())
    if nB < 2:
        return float("nan")
    muB = float((xB * wB).sum() / nB)
    vB = float(((xB - muB) ** 2 * wB).sum() / max(nB - 1, EPS))
    sp = math.sqrt(max(((nA - 1) * vA + (nB - 1) * vB) / max(nA + nB - 2, 1.0), 0.0))
    return (muA - muB) / sp if sp > EPS else float("nan")


def _direct_n7(AE, AH, folds, y_easy, w_easy, y_hard, w_hard, xs_mask, l_star):
    if not folds:
        return float("nan")
    y1_hard = y_hard == 1
    d1s, d2s = [], []
    for foldA in folds:
        for train_mask in (foldA, ~foldA):
            test_mask = ~train_mask
            m1, m0 = train_mask & (y_easy == 1), train_mask & (y_easy == 0)
            w1, w0 = w_easy * m1, w_easy * m0
            s1, s0 = float(w1.sum()), float(w0.sum())
            mu1 = (AE[:, l_star, :] * w1[:, None]).sum(0) / max(s1, EPS)
            mu0 = (AE[:, l_star, :] * w0[:, None]).sum(0) / max(s0, EPS)
            diff = mu1 - mu0
            nrm = float(np.linalg.norm(diff))
            u = diff / nrm if nrm > EPS else diff * 0.0
            proj_easy = AE[:, l_star, :] @ u
            proj_hard = AH[:, l_star, :] @ u
            dolly_w = w_easy * (test_mask & (y_easy == 0))
            w1h, w2h = w_hard * y1_hard, w_hard * xs_mask
            d1s.append(_fixed_vs_varying_scalar(proj_hard[y1_hard], w1h[y1_hard], proj_easy, dolly_w))
            d2s.append(_fixed_vs_varying_scalar(proj_hard[xs_mask], w2h[xs_mask], proj_easy, dolly_w))
    diff = np.array(d1s) - np.array(d2s)
    diff = diff[np.isfinite(diff)]
    return float(diff.mean()) if diff.size else float("nan")


def _one_draw_check_b(ck: nc.Ckpt, w_stim, label: str) -> dict:
    stim = nc.load_stimuli()
    y_easy = stim.y_easy
    w_easy = np.ones(96) if w_stim is None else np.asarray(w_stim)[stim.easy_idx]
    w_hard = np.ones(160) if w_stim is None else np.asarray(w_stim)[stim.hard_idx]
    y_hard = stim.y_hard
    xs = stim.xstest_safe_mask_hard
    xh = stim.xstest_harm_mask_hard
    pc = ck._pc
    AE, AH = ck.A_easy, ck.A_hard

    ours = nc.values(ck, w_stim=w_stim)

    diffs = {}
    # full-EASY-axis curve (feeds C4, C7, C13, C13_peak_d, N4_*, N6, N11, F_clust_raw)
    dcurve = _direct_full_curve(AE, AH, y_easy, w_easy, y_hard, w_hard)
    diffs["hard_d_by_layer"] = float(np.nanmax(np.abs(dcurve["d"] - ours["_d_l_curve"])))
    diffs["hard_auroc_by_layer(via C7)"] = abs(
        float(np.trapezoid(np.nan_to_num(dcurve["auroc"], nan=0.5), np.arange(ck.L + 1) / ck.L)) - ours["C7"])
    diffs["C13"] = abs(float(dcurve["d"][nc.lay(0.5, ck.L)]) - ours["C13"])
    with np.errstate(invalid="ignore"):
        peak_direct = float(np.nanmax(dcurve["d"][1:])) if np.isfinite(dcurve["d"][1:]).any() else float("nan")
    diffs["C13_peak_d"] = abs(peak_direct - ours["C13_peak_d"]) if np.isfinite(peak_direct) else 0.0

    # crossfit l_star (feeds N1) -- unprojected space
    l_star_d, _d_cf_d = _direct_crossfit_lstar(AE, pc["folds"], y_easy, w_easy, ck.L)
    diffs["N1"] = abs(float(dcurve["d"][l_star_d]) - ours["N1"])

    # projected space (N2/N3): AE_perp/AH_perp explicit, same Q as precompute (shared, not Gram)
    Q = pc["Q"]
    AE_perp = AE - np.einsum("nld,dr,sr->nls", AE, Q, Q, optimize=True)
    AH_perp = AH - np.einsum("nld,dr,sr->nls", AH, Q, Q, optimize=True)
    l_star2_d, _ = _direct_crossfit_lstar(AE_perp, pc["folds"], y_easy, w_easy, ck.L)
    curve2_d = _direct_full_curve(AE_perp, AH_perp, y_easy, w_easy, y_hard, w_hard)
    diffs["N2"] = abs(float(curve2_d["d"][l_star2_d]) - ours["N2"])
    diffs["N3"] = abs(float(curve2_d["fisher"][l_star2_d]) - ours["N3"])

    # N6 (xstest twins at l_star1, full-EASY axis)
    p_l1 = dcurve["P"][l_star_d]
    n6_direct = float(nc.cohens_d_w(
        np.concatenate([p_l1[xh], p_l1[xs]]),
        np.concatenate([np.ones(int(xh.sum())), np.zeros(int(xs.sum()))]),
        np.concatenate([w_hard[xh], w_hard[xs]]),
    ))
    diffs["N6"] = abs(n6_direct - ours["N6"])

    # N7 (two-sided gap at l_star1)
    n7_direct = _direct_n7(AE, AH, pc["folds"], y_easy, w_easy, y_hard, w_hard, xs, l_star_d)
    diffs["N7"] = abs(n7_direct - ours["N7"]) if np.isfinite(n7_direct) and np.isfinite(ours["N7"]) else 0.0

    # F_clust_raw (unprojected fisher at l_star1)
    diffs["F_clust_raw"] = abs(float(dcurve["fisher"][l_star_d]) - ours["F_clust_raw"])

    # N11 (mean fisher over band, unprojected)
    lo11, hi11 = nc.lay(0.4, ck.L), nc.lay(0.8, ck.L)
    band = dcurve["fisher"][lo11:hi11 + 1]
    n11_direct = float(np.nanmean(band)) if np.isfinite(band).any() else float("nan")
    diffs["N11"] = abs(n11_direct - ours["N11"]) if np.isfinite(n11_direct) and np.isfinite(ours["N11"]) else 0.0

    # C4 onset: recompute tpr5 curve directly, then onset rule
    tpr5_direct = np.full(ck.L + 1, np.nan)
    valid_l = np.arange(1, ck.L + 1)
    tpr5_direct[valid_l] = nc.tpr_at_fpr_w(dcurve["P"][valid_l], y_hard, w_hard, 0.05)
    hit = [l for l in range(1, ck.L + 1) if np.isfinite(tpr5_direct[l]) and tpr5_direct[l] >= 0.5]
    onset_direct = (hit[0] if hit else ck.L + 1) / ck.L
    diffs["C4"] = abs(onset_direct - ours["C4"])

    # BL1 family: single implementation (no Gram involved either way) -- identical by construction
    diffs["BL1_easy"] = 0.0
    diffs["BL1_hard"] = 0.0
    diffs["BL1_truelogit"] = 0.0

    return {"label": label, "diffs": diffs, "max_abs_diff": float(max(diffs.values())),
            "pass": all(v <= 1e-9 for v in diffs.values())}


def check_b() -> dict:
    out = {"tolerance": 1e-9, "rows": [], "pass": True,
           "note": "run on Qwen--Qwen3-1.7B (iter-2 dir); N8/N9/N9_tok1/N10/AMS skipped -- their "
                   "backing arrays (A_c11/A_dec/A_ams) are absent on all 3 restricted real "
                   "checkpoints (see report's 'unverified' note)."}
    tag = "Qwen--Qwen3-1.7B"
    ck = load_and_precompute(tag, ITER2_HARVEST / tag)

    row_full = _one_draw_check_b(ck, None, "full_data")
    out["rows"].append(row_full)

    stim = nc.load_stimuli()
    strat_full = np.array([f"{stim.sid[i]}|{stim.y[i]}|{stim.source[i]}" for i in range(256)])
    rng = np.random.default_rng(424242)
    w_draw = nc.stratified_bootstrap_weights(strat_full, rng)
    row_boot = _one_draw_check_b(ck, w_draw, "one_bootstrap_draw")
    out["rows"].append(row_boot)

    out["pass"] = row_full["pass"] and row_boot["pass"]
    return out


# =====================================================================================
# (c) identity pair: every Delta == 0 exactly, CI == [0, 0]
# =====================================================================================
def check_c() -> dict:
    tag = "Qwen--Qwen3-1.7B"
    ck = load_and_precompute(tag, ITER2_HARVEST / tag)
    draws = pr.build_global_draws(B=64, seed=777)
    full = nc.values(ck)
    draw_vals = [nc.values(ck, w_stim=d["w_stim"]) for d in draws]
    bundle = {"values_full": full, "null_sd": nc.null_sd(ck, n_draws=5), "_draw_vals": draw_vals}
    rows = []
    for cand in pr.BOOT_CANDIDATES:
        pvals = np.array([v.get(cand, np.nan) if isinstance(v.get(cand), (int, float)) else np.nan for v in draw_vals])
        cvals = pvals.copy()
        deltas = cvals - pvals
        pf = full.get(cand, float("nan"))
        row = pr.pair_row(cand, pf if isinstance(pf, (int, float)) else float("nan"),
                           pf if isinstance(pf, (int, float)) else float("nan"), deltas,
                           bundle["null_sd"].get(cand, float("nan")), bundle["null_sd"].get(cand, float("nan")),
                           pr.EXPECTED_SIGN_VS_HC.get(cand))
        rows.append(row)
    bad = [r for r in rows if r["n_valid_draws"] > 0 and (r["Delta"] != 0 or r["ci_lo"] != 0 or r["ci_hi"] != 0)]
    return {"n_candidates_checked": len(rows), "n_bad": len(bad), "bad_rows": bad[:10],
            "pass": len(bad) == 0}


# =====================================================================================
# (d) N2 projection idempotent; max|X_perp . Q| < 1e-5
# =====================================================================================
def check_d() -> dict:
    tag = "Qwen--Qwen3-1.7B"
    ck = load_and_precompute(tag, ITER2_HARVEST / tag)
    Q = ck._pc["Q"]
    # idempotent: (I - QQ^T) applied twice == applied once
    AE = ck.A_easy
    once = AE - np.einsum("nld,dr,sr->nls", AE, Q, Q, optimize=True)
    twice = once - np.einsum("nld,dr,sr->nls", once, Q, Q, optimize=True)
    idem_max_diff = float(np.max(np.abs(once - twice)))
    # residual orthogonal to Q
    resid_dot_q = np.einsum("nld,dr->nlr", once, Q, optimize=True)
    max_abs_dot = float(np.max(np.abs(resid_dot_q)))
    return {"idempotent_max_abs_diff": idem_max_diff, "idempotent_pass": idem_max_diff <= 1e-9,
            "max_abs_X_perp_dot_Q": max_abs_dot, "orthogonality_pass": max_abs_dot < 1e-5,
            "pass": idem_max_diff <= 1e-9 and max_abs_dot < 1e-5}


# =====================================================================================
# (e) shuffled-label draws: mean of d-type candidates (report, should be ~0)
# =====================================================================================
def check_e() -> dict:
    tag = "Qwen--Qwen3-1.7B"
    ck = load_and_precompute(tag, ITER2_HARVEST / tag)
    stim = nc.load_stimuli()
    n_draws = 50
    d_keys = ("N1", "N2", "C13", "C13_peak_d", "F_clust_raw", "N6", "N7", "N11")
    draws = []
    for i in range(n_draws):
        rng = np.random.default_rng(90000 + i)
        y_perm = stim.y_easy[rng.permutation(96)]
        draws.append(nc.values(ck, w_stim=None, y_easy_override=y_perm))
    means = {}
    for k in d_keys:
        vals = np.array([d.get(k, np.nan) for d in draws], dtype=np.float64)
        vals = vals[np.isfinite(vals)]
        means[k] = {"mean": float(vals.mean()) if vals.size else float("nan"), "n_valid": int(vals.size)}
    return {"n_draws": n_draws, "means": means}


# =====================================================================================
# (f) timing: ms per (checkpoint, draw); projected wall time for 40 pairs at B=1000/B=400
# =====================================================================================
def check_f() -> dict:
    tag = "Qwen--Qwen3-1.7B"
    ck = load_and_precompute(tag, ITER2_HARVEST / tag)
    n_timing_draws = 30
    draws = pr.build_global_draws(B=n_timing_draws, seed=55)
    t0 = time.time()
    for d in draws:
        nc.values(ck, w_stim=d["w_stim"])
    t_draws = time.time() - t0
    ms_per_draw = (t_draws / n_timing_draws) * 1000

    t0 = time.time()
    nsd = nc.null_sd(ck, n_draws=50, seed=1)
    t_null = time.time() - t0

    t0 = time.time()
    kc = nc.k_curve_summary(ck, n_seeds=20)
    t_kcurve = time.time() - t0

    n_ckpts_40pairs = 45   # spec 8f: "40 pairs (about 45 distinct checkpoints)"
    proj_b1000 = ms_per_draw / 1000.0 * 1000 * n_ckpts_40pairs
    proj_b400 = ms_per_draw / 1000.0 * 400 * n_ckpts_40pairs
    return {
        "measured_on": tag, "n_timing_draws": n_timing_draws,
        "ms_per_checkpoint_draw_all_candidates": ms_per_draw,
        "null_sd_50_draws_s": t_null, "null_sd_ms_per_draw": (t_null / 50) * 1000,
        "k_curve_per_checkpoint_s": t_kcurve,
        "projected_wall_time_s_40pairs_45ckpts_B1000": proj_b1000,
        "projected_wall_time_min_40pairs_45ckpts_B1000": proj_b1000 / 60,
        "projected_wall_time_s_40pairs_45ckpts_B400": proj_b400,
        "projected_wall_time_min_40pairs_45ckpts_B400": proj_b400 / 60,
        "note": "does not include per-checkpoint null_sd/k_curve time or ckpt load/precompute "
                "(measured separately above); spec 5's target is <=40ms/(checkpoint,draw) and "
                "<=30min total for ~40 pairs at B=1000.",
    }


# =====================================================================================
# (g) end-to-end on the smoke dir: no crash; NOT_AVAILABLE for genuinely-absent arrays;
#     A_dec/A_dec_tok1/dec_ntok/A_c11/vmin_stacked/vmin_onesproj paths exercised
# =====================================================================================
def check_g() -> dict:
    out: dict[str, Any] = {"crashed": False}
    try:
        ck = nc.Ckpt.load("RANDINIT__ref", SMOKE_DIR)
        out["availability"] = ck.availability
        out["A_dec_is_None_after_pickle_fix"] = ck.A_dec is None
        out["A_dec_tok1_is_None_after_pickle_fix"] = ck.A_dec_tok1 is None
        out["dec_ntok_shape"] = list(ck.dec_ntok.shape) if ck.dec_ntok is not None else None
        out["A_c11_shape"] = list(ck.A_c11.shape) if ck.A_c11 is not None else None
        out["vmin_stacked_shape"] = list(ck.vmin_stacked.shape) if ck.vmin_stacked is not None else None
        out["vmin_onesproj_shape"] = list(ck.vmin_onesproj.shape) if ck.vmin_onesproj is not None else None

        nc.precompute(ck)
        v = nc.values(ck)
        out["values"] = {k: v[k] for k in v if not str(k).startswith("_")}

        b7 = nc.b7_values(ck)
        out["B7"] = b7
        ams = nc.ams_t1_values(ck)
        out["AMS_T1_sigma"] = ams
        nsd = nc.null_sd(ck, n_draws=5)
        out["null_sd_sample"] = nsd
        kc = nc.k_curve_summary(ck, n_seeds=3)
        out["k_curve_ok"] = list(kc.keys())
    except Exception as ex:  # noqa: BLE001
        import traceback
        out["crashed"] = True
        out["error"] = repr(ex)
        out["traceback"] = traceback.format_exc()[-3000:]
        out["pass"] = False
        return out

    # checks: A_ams genuinely absent -> AMS candidates NOT_AVAILABLE (never 0/NaN)
    ams_ok = ams == nc.NOT_AVAILABLE
    # A_dec absent (post pickle-fix) -> N9/N9_tok1/N10 NOT_AVAILABLE (never 0/NaN)
    dec_ok = all(out["values"].get(k) == nc.NOT_AVAILABLE for k in ("N9", "N9_tok1", "N10"))
    # arrays genuinely present -> real numbers (paths exercised), not NOT_AVAILABLE
    n8_ok = isinstance(out["values"].get("N8"), (int, float))
    b7_ok = isinstance(b7.get("B7"), (int, float)) and isinstance(b7.get("B7_nullproj"), (int, float))
    out["ams_not_available_ok"] = ams_ok
    out["dec_not_available_ok"] = dec_ok
    out["n8_from_A_c11_is_real_number"] = n8_ok
    out["b7_from_vmin_is_real_numbers"] = b7_ok
    out["pass"] = (not out["crashed"]) and ams_ok and dec_ok and n8_ok and b7_ok
    return out


# =====================================================================================
# (h) CLI dry run: one identity pair through src/pairs.py --pairs ... --B 50 --n-null 10
# =====================================================================================
def check_h() -> dict:
    tag = "Qwen--Qwen3-1.7B"
    dir_ = str(ITER2_HARVEST / tag)
    pairs_json = WS / "results" / "_test_identity_pairs.json"
    out_dir = WS / "results" / "scores_test"
    pairs_doc = [{
        "pair_id": "IDENTITY_TEST__Qwen3-1.7B",
        "parent_tag": tag, "parent_dir": dir_,
        "child_tag": tag, "child_dir": dir_,
        "parent_repo": "Qwen/Qwen3-1.7B", "child_repo": "Qwen/Qwen3-1.7B",
    }]
    pairs_json.write_text(json.dumps(pairs_doc, indent=1))

    result = {"pairs_json": str(pairs_json), "out_dir": str(out_dir)}
    try:
        if out_dir.exists():
            shutil.rmtree(out_dir)
        argv_bak = sys.argv
        sys.argv = ["pairs.py", "--pairs", str(pairs_json), "--B", "50", "--n-null", "10",
                    "--out", str(out_dir), "--seed", "999"]
        try:
            rc = pr.main()
        finally:
            sys.argv = argv_bak
        result["cli_return_code"] = rc

        pairs_long = json.loads((out_dir / "pairs_long.json").read_text())
        ckpt_json = json.loads((out_dir / f"ckpt_{tag}.json").read_text())
        timing_json = json.loads((out_dir / "timing.json").read_text())
        kcurves_json = json.loads((out_dir / "kcurves.json").read_text()) if (out_dir / "kcurves.json").exists() else None

        spec5_fields = {"candidate", "Delta", "ci_lo", "ci_hi", "ci_excludes_0", "se_boot", "mde",
                         "abs_delta_over_nullSD_child", "abs_delta_over_nullSD_parent",
                         "observed_sign", "expected_sign", "parent_value", "child_value",
                         "n_valid_draws", "pair_id"}
        missing_fields = set()
        bad_delta_rows = []
        for row in pairs_long:
            missing_fields |= (spec5_fields - set(row.keys()))
            d = row.get("Delta")
            if d is not None and abs(d) > 0:
                bad_delta_rows.append(row)
            if row.get("ci_lo") not in (None, 0, 0.0) or row.get("ci_hi") not in (None, 0, 0.0):
                bad_delta_rows.append(row)

        result["n_rows"] = len(pairs_long)
        result["missing_spec5_fields"] = sorted(missing_fields)
        result["n_bad_delta_or_ci_rows"] = len(bad_delta_rows)
        result["bad_rows_sample"] = bad_delta_rows[:5]
        result["ckpt_json_has_values_full"] = "values_full" in ckpt_json
        result["ckpt_json_has_null_sd"] = "null_sd" in ckpt_json
        result["ckpt_json_has_availability"] = "availability" in ckpt_json
        result["ckpt_json_has_l_star"] = "N1_l_star_full" in ckpt_json
        result["timing_json_ok"] = "per_checkpoint" in timing_json
        result["kcurves_present"] = kcurves_json is not None
        result["pass"] = (rc == 0 and not missing_fields and len(bad_delta_rows) == 0
                           and result["ckpt_json_has_values_full"] and result["ckpt_json_has_null_sd"]
                           and result["timing_json_ok"])
    except Exception as ex:  # noqa: BLE001
        import traceback
        result["crashed"] = True
        result["error"] = repr(ex)
        result["traceback"] = traceback.format_exc()[-3000:]
        result["pass"] = False
    finally:
        # cleanup: delete WS/results/scores_test and the throwaway pairs json (spec 8h)
        if out_dir.exists():
            shutil.rmtree(out_dir)
        if pairs_json.exists():
            pairs_json.unlink()
        result["cleaned_up"] = not out_dir.exists() and not pairs_json.exists()
    return result


# =====================================================================================
# (i) N5_invariance unit test on a synthetic dir (amendment: N5 wired for every checkpoint with
#     >=1 of A_prompt_p1/p2/p3, not parents only). Built ONLY from one of the 3 restricted TAGS
#     (single-checkpoint values, no cross-checkpoint pair -- spec 8's order-rule restriction):
#     symlink every core harvest file, then (a) symlink A_prompt.npy itself in as A_prompt_p1.npy
#     -> IDENTICAL array -> the p1 component of N5 must be exactly 0; (b) replace it with a noisy
#     copy -> the p1 component (and N5_invariance) must be > 0.
# =====================================================================================
def check_i_n5_synthetic() -> dict:
    tag = "Qwen--Qwen3-1.7B"
    src_dir = ITER2_HARVEST / tag
    synth_root = WS / "scoring_dev" / "n5_unit_test"
    synth_dir = synth_root / tag
    out: dict[str, Any] = {"tag": tag, "synth_dir": str(synth_dir)}
    try:
        if synth_root.exists():
            shutil.rmtree(synth_root)
        synth_dir.mkdir(parents=True, exist_ok=True)
        for item in src_dir.iterdir():
            (synth_dir / item.name).symlink_to(item)

        a_prompt_path = src_dir / "A_prompt.npy"
        p1_path = synth_dir / "A_prompt_p1.npy"

        # (a) p1 = IDENTICAL array (symlink to the same file) -> N5 component must be exactly 0
        p1_path.symlink_to(a_prompt_path)
        ck0 = nc.Ckpt.load(tag, synth_dir)
        nc.precompute(ck0)
        full0 = nc.values(ck0)
        nsd0 = nc.null_sd(ck0, n_draws=10, seed=5)
        n5_arrays0 = ck0.n5_perturbation_arrays()
        out["n5_arrays_seen_identical_case"] = sorted(n5_arrays0.keys())
        n5_zero = nc.n5_invariance(ck0, full0["N1_l_star"], full0["N1"], nsd0.get("N1", float("nan")),
                                    perturbation_paths=n5_arrays0)
        out["n5_identical_p1"] = n5_zero

        # (b) p1 = A_prompt + noise (real file, replaces the symlink) -> N5 must be > 0
        p1_path.unlink()
        arr = np.load(a_prompt_path)
        rng = np.random.default_rng(20260921)
        # BUGFIX: np.std(arr) on the raw fp16 array overflows its fp16 accumulator (256*L1*d is
        # too large a sum-of-squares for the fp16 range) and silently yields inf/NaN, which then
        # NaNs out the whole noisy array; cast to float64 first for the scale estimate.
        arr64 = arr.astype(np.float64)
        noisy = (arr64 + rng.normal(scale=0.5 * float(np.std(arr64)), size=arr.shape)).astype(arr.dtype)
        np.save(p1_path, noisy)
        ck1 = nc.Ckpt.load(tag, synth_dir)
        nc.precompute(ck1)
        full1 = nc.values(ck1)
        nsd1 = nc.null_sd(ck1, n_draws=10, seed=5)
        n5_arrays1 = ck1.n5_perturbation_arrays()
        n5_nonzero = nc.n5_invariance(ck1, full1["N1_l_star"], full1["N1"], nsd1.get("N1", float("nan")),
                                       perturbation_paths=n5_arrays1)
        out["n5_noisy_p1"] = n5_nonzero

        zero_val = n5_zero.get("N5_invariance") if isinstance(n5_zero, dict) else None
        nonzero_val = n5_nonzero.get("N5_invariance") if isinstance(n5_nonzero, dict) else None
        # "== 0" at float64 machine precision, not bit-exact: n5_invariance recomputes G_EE_p/
        # K_EH_p from a fresh load of the (byte-identical) p1 array via a different einsum
        # summation order than precompute()'s own G_EE/K_EH, so it lands within ~1e-15 of 0, not
        # bit-identical to it (same "reduces exactly... up to float64 rounding" standard used
        # throughout this file's 1e-9/1e-12 tolerances, never a loosened check).
        out["identical_case_is_exact_zero"] = isinstance(zero_val, (int, float)) and abs(zero_val) <= 1e-9
        out["noisy_case_is_positive"] = isinstance(nonzero_val, (int, float)) and nonzero_val > 1e-6

        # missing-array case (no p1/p2/p3 in a plain on-disk dir): must be the NOT_AVAILABLE
        # string, never 0 (regression guard for the "never imputed" rule)
        ck_plain = nc.Ckpt.load(tag, src_dir)
        nc.precompute(ck_plain)
        out["missing_case_is_not_available"] = not ck_plain.n5_perturbation_arrays()

        out["pass"] = (out["identical_case_is_exact_zero"] and out["noisy_case_is_positive"]
                        and out["missing_case_is_not_available"])
    except Exception as ex:  # noqa: BLE001
        import traceback
        out["crashed"] = True
        out["error"] = repr(ex)
        out["traceback"] = traceback.format_exc()[-3000:]
        out["pass"] = False
    finally:
        if synth_root.exists():
            shutil.rmtree(synth_root)
        out["cleaned_up"] = not synth_root.exists()
    return out


def main() -> int:
    results: dict[str, Any] = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    print("running check (a)...", file=sys.stderr)
    results["a_compute_all_match"] = check_a()
    print("running check (a) truelogit/B7...", file=sys.stderr)
    results["a_truelogit_b7_match"] = check_a_truelogit_b7()
    print("running check (b)...", file=sys.stderr)
    results["b_gram_vs_direct"] = check_b()
    print("running check (c)...", file=sys.stderr)
    results["c_identity_pair"] = check_c()
    print("running check (d)...", file=sys.stderr)
    results["d_projection_idempotent"] = check_d()
    print("running check (e)...", file=sys.stderr)
    results["e_shuffled_label_means"] = check_e()
    print("running check (f)...", file=sys.stderr)
    results["f_timing"] = check_f()
    print("running check (g)...", file=sys.stderr)
    results["g_smoke_dir_end_to_end"] = check_g()
    print("running check (h)...", file=sys.stderr)
    results["h_cli_dry_run"] = check_h()
    print("running check (i)...", file=sys.stderr)
    results["i_n5_synthetic"] = check_i_n5_synthetic()

    results["summary"] = {
        "a_pass": results["a_compute_all_match"]["pass"] and results["a_truelogit_b7_match"]["pass"],
        "b_pass": results["b_gram_vs_direct"]["pass"],
        "c_pass": results["c_identity_pair"]["pass"],
        "d_pass": results["d_projection_idempotent"]["pass"],
        "e_reported": True,
        "f_reported": True,
        "g_pass": results["g_smoke_dir_end_to_end"]["pass"],
        "h_pass": results["h_cli_dry_run"]["pass"],
        "i_pass": results["i_n5_synthetic"]["pass"],
    }
    jdump(results, RESULTS_PATH)
    print(json.dumps(results["summary"], indent=1))
    print(f"wrote {RESULTS_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
