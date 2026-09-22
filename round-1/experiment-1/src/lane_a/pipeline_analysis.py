#!/usr/bin/env python3
"""Full offline analysis: Stage-0 gates, the five candidate readouts, the baselines and
the S1 specificity table.  Pure numpy/scipy/sklearn over the saved harvest; no GPU.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
from loguru import logger

from .analysis import (
    BAND_WIDTH, BOOT_B, COH_CELLS, GRID_CELLS, N_RAND_DIRS, N_SHUFFLE, SAFETY_CELLS,
    auroc, boot_ci, cohens_d, coherence_interaction, fisher_ratio, fit_dim, fit_tau, holm,
    k1_terms, paired_boot_ci, probe_auroc, project, project_multi, silhouette_two,
    standardised, tost, unit,
)
from . import shard
from .harvest import seeded_random_dirs

POOLS = ("early", "late", "harc32", "prompt")


def _seed(s: str) -> int:
    """Deterministic seed from a string. Python's builtin hash() is salted per
    process, so using it here would make the bootstrap irreproducible."""
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)
RAND_SEED = 20260920


# ---------------------------------------------------------------------------

def _cells_dict(vecs: np.ndarray, n_items: int) -> dict[str, np.ndarray]:
    """(n_items*12, n_hs, D) -> {cell: (n_items, n_hs, D)}"""
    out = {}
    for k, c in enumerate(GRID_CELLS):
        out[c] = vecs[np.arange(n_items) * len(GRID_CELLS) + k]
    return out


def _proj_cells(cells: dict[str, np.ndarray], direction: np.ndarray,
                band: tuple[int, int]) -> dict[str, np.ndarray]:
    return {c: project(v, direction, band) for c, v in cells.items()}


def _proj_cells_multi(cells: dict[str, np.ndarray], dirs: np.ndarray,
                      band: tuple[int, int]) -> dict[str, np.ndarray]:
    return {c: project_multi(v, dirs, band) for c, v in cells.items()}


def _contrast_fns(fam: str) -> dict[str, Callable[[dict[str, np.ndarray]], np.ndarray]]:
    def mk(term: str):
        def f(s):
            hh, hb = s[f"saf|{fam}|H|haz"], s[f"saf|{fam}|H|ben"]
            bh, bb = s[f"saf|{fam}|B|haz"], s[f"saf|{fam}|B|ben"]
            if term == "O":
                return 0.5 * ((hh + hb) - (bh + bb))
            if term == "CB":
                return bh - bb
            if term == "A":
                return (hh - hb) - (bh - bb)
            return (bh - bb) + ((hh - hb) - (bh - bb))  # T
        return f
    return {t: mk(t) for t in ("O", "CB", "A", "T")}


def _coh_fn(s: dict[str, np.ndarray]) -> np.ndarray:
    return (s["coh|F1|A|A"] - s["coh|F1|A|B"]) - (s["coh|F1|B|A"] - s["coh|F1|B|B"])


# ---------------------------------------------------------------------------
# Stage-0 gate helpers
# ---------------------------------------------------------------------------

def split_half_cosine(fit_vecs: np.ndarray, labels: np.ndarray, pair_ids: np.ndarray,
                      band: tuple[int, int], *, n: int = 20, seed: int = 11) -> dict[str, float]:
    """G1: split the fitting PAIRS in half n times; mean cos(r_half1, r_half2) at the band."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(pair_ids)
    cos = []
    for _ in range(n):
        perm = rng.permutation(uniq)
        h1 = set(perm[: len(perm) // 2].tolist())
        m1 = np.array([p in h1 for p in pair_ids])
        if labels[m1].sum() < 2 or (~labels[m1]).sum() < 2:
            continue
        if labels[~m1].sum() < 2 or (~labels[~m1]).sum() < 2:
            continue
        r1 = fit_dim(fit_vecs[m1], labels[m1])
        r2 = fit_dim(fit_vecs[~m1], labels[~m1])
        lo, hi = band
        c = float(np.mean([float(np.dot(r1[L], r2[L])) for L in range(lo, hi + 1)]))
        cos.append(c)
    a = np.asarray(cos)
    return {"mean_cosine": float(a.mean()) if len(a) else float("nan"),
            "min_cosine": float(a.min()) if len(a) else float("nan"),
            "n_splits": int(len(a))}


def positive_control(fit_vecs: np.ndarray, labels: np.ndarray, pair_ids: np.ndarray,
                     band: tuple[int, int], *, seed: int = 13) -> dict[str, Any]:
    """G3: in-sample AND cross-fitted (out-of-sample) separation of hazardous vs benign
    continuations on the fitting corpus.

    The out-of-sample number is the one that matters: an in-sample diff-in-means direction
    can reach AUROC 1.0 on pure noise, so the in-sample figure is reported for transparency
    only and is NEVER used as the gate.
    """
    r_in = fit_dim(fit_vecs, labels)
    s_in = project(fit_vecs, r_in, band)
    d_in = cohens_d(s_in[labels], s_in[~labels])
    a_in = auroc(s_in[labels], s_in[~labels])

    rng = np.random.default_rng(seed)
    uniq = np.unique(pair_ids)
    ds, aus = [], []
    for _ in range(10):
        perm = rng.permutation(uniq)
        h1 = set(perm[: len(perm) // 2].tolist())
        m1 = np.array([p in h1 for p in pair_ids])
        r = fit_dim(fit_vecs[m1], labels[m1])
        s = project(fit_vecs[~m1], r, band)
        ds.append(cohens_d(s[labels[~m1]], s[~labels[~m1]]))
        aus.append(auroc(s[labels[~m1]], s[~labels[~m1]]))
    return {"d_in_sample": d_in, "auroc_in_sample": a_in,
            "d_cross_fitted": float(np.nanmean(ds)), "auroc_cross_fitted": float(np.nanmean(aus)),
            "d_cross_fitted_sd": float(np.nanstd(ds, ddof=1))}


def choose_band(fit_vecs: np.ndarray, labels: np.ndarray, pair_ids: np.ndarray,
                n_hs: int, *, seed: int = 17) -> dict[str, Any]:
    """G2: pick the 9-layer band by CROSS-FITTED Cohen's d on the FITTING CORPUS ONLY, in
    Qwen3-4B ONLY.  Evaluation items are never touched by this choice.  Bands run over the
    36 transformer blocks (hidden_states index 1..36); index 0 is the embeddings.
    """
    rng = np.random.default_rng(seed)
    uniq = np.unique(pair_ids)
    n_blocks = n_hs - 1
    starts = list(range(1, n_blocks - BAND_WIDTH + 2))
    scores = np.zeros(len(starts))
    for _ in range(6):
        perm = rng.permutation(uniq)
        h1 = set(perm[: len(perm) // 2].tolist())
        m1 = np.array([p in h1 for p in pair_ids])
        r = fit_dim(fit_vecs[m1], labels[m1])
        for bi, st in enumerate(starts):
            s = project(fit_vecs[~m1], r, (st, st + BAND_WIDTH - 1))
            scores[bi] += cohens_d(s[labels[~m1]], s[~labels[~m1]]) / 6.0
    best = int(np.nanargmax(scores))
    st = starts[best]
    return {"band": [st, st + BAND_WIDTH - 1],
            "band_fraction_of_depth": [round(st / n_blocks, 4), round((st + BAND_WIDTH - 1) / n_blocks, 4)],
            "cross_fitted_d_by_band": {f"{s}-{s + BAND_WIDTH - 1}": float(scores[i])
                                       for i, s in enumerate(starts)},
            "n_bands": len(starts), "selected_d": float(scores[best])}


# ---------------------------------------------------------------------------
# per-checkpoint analysis
# ---------------------------------------------------------------------------

def fit_probe_direction(fit_vecs: np.ndarray, labels: np.ndarray, band: tuple[int, int],
                        n_hs: int, d_model: int, *, seed: int = 0) -> np.ndarray:
    """Per-layer direction from a supervised logistic probe fitted on the DISJOINT fitting
    corpus, as a robustness variant of (and pre-registered fallback for) diff-in-means."""
    from sklearn.linear_model import LogisticRegression
    lo, hi = band
    X = fit_vecs[:, lo:hi + 1].astype(np.float32).reshape(len(fit_vecs), -1)
    y = np.asarray(labels).astype(int)
    out = np.zeros((n_hs, d_model), dtype=np.float32)
    if len(np.unique(y)) < 2:
        return out
    mu, sd = X.mean(0), X.std(0) + 1e-6
    clf = LogisticRegression(max_iter=3000, C=1.0, random_state=seed)
    clf.fit((X - mu) / sd, y)
    w = (clf.coef_.ravel() / sd).reshape(hi - lo + 1, d_model)
    out[lo:hi + 1] = unit(w)
    return out


def analyse_checkpoint(tag: str, hdir: Path, band: tuple[int, int], sub: dict[str, Any],
                       prereg: dict[str, Any]) -> dict[str, Any]:
    logger.info(f"[{tag}] analysing at band {band}")
    meta = json.loads((hdir / "meta.json").read_text())
    n_hs, d_model = meta["n_hs"], meta["d_model"]
    n_items = meta["n_items"]

    z = shard.load_npz(hdir / "dirs.npz")
    r_content = z["r_content"].astype(np.float32)
    r_ablit = z["r_ablit"].astype(np.float32)
    z = shard.load_npz(hdir / "fit.npz")
    fit_early = z["early"]
    fit_harc = z["harc32"]
    fit_lab = z["labels"].astype(bool)
    fit_pair = z["pair_ids"]
    fit_half = z["halves"]
    prim = fit_half == 0  # primary half of the fitting corpus

    rand_dirs = seeded_random_dirs(n_hs, d_model, N_RAND_DIRS, RAND_SEED)

    res: dict[str, Any] = {"tag": tag, "meta": meta, "band": list(band)}

    # ---- G1 / G3 direction quality
    res["G1_split_half_cosine"] = split_half_cosine(fit_early[prim], fit_lab[prim], fit_pair[prim], band)
    res["G1_split_half_cosine_full_corpus"] = split_half_cosine(fit_early, fit_lab, fit_pair, band)
    res["G3_positive_control"] = positive_control(fit_early[prim], fit_lab[prim], fit_pair[prim], band)
    res["G3_positive_control_harc32_pool"] = positive_control(fit_harc[prim], fit_lab[prim], fit_pair[prim], band)

    # ---- scale table (the reason null-SD units exist)
    z = shard.load_npz(hdir / "scalars.npz")
    resid_norm = z["grid_resid_norm"]
    nll = z["grid_nll"]
    logit_gap = z["grid_logit_gap"]
    logit_gap_post = z["grid_logit_gap_post"] if "grid_logit_gap_post" in z else np.full_like(logit_gap, np.nan)
    z = shard.load_npz(hdir / "weights.npz")
    ln_gain = z["ln_gain"]
    sr_down = z["sr_down_proj"]
    sr_o = z["sr_o_proj"]
    lo, hi = band
    res["scale_table"] = {
        "mean_resid_L2_at_band": float(np.nanmean(resid_norm[:, lo:hi + 1])),
        "mean_resid_L2_by_layer": [float(x) for x in np.nanmean(resid_norm, axis=0)],
        "mean_layernorm_gain_at_band": float(np.nanmean(ln_gain[max(lo - 1, 0):hi])),
        "mean_layernorm_gain_by_layer": [float(x) for x in ln_gain],
    }

    # ---- cosine curve between the RESPONSE-fitted content axis and the PROMPT-fitted
    #      request-refusal axis (HARC arXiv:2607.00572 asserts these stay aligned but
    #      prints no number; this is a PRIMARY result of lane A)
    cos_layer = [abs(float(np.dot(r_content[L], r_ablit[L]))) for L in range(n_hs)]
    res["cos_content_ablit"] = {
        "per_layer_abs": cos_layer,
        "at_band": float(np.mean(cos_layer[lo:hi + 1])),
        "max_over_layers": float(np.max(cos_layer)),
        "argmax_layer": int(np.argmax(cos_layer)),
        "gate_0.50_exceeded_at_band": bool(np.mean(cos_layer[lo:hi + 1]) > 0.50),
    }

    # ---- the grid
    z = shard.load_npz(hdir / "grid.npz")
    grid = {p: z[p] for p in POOLS}
    cells_by_pool = {p: _cells_dict(grid[p], n_items) for p in POOLS}

    res["candidates"] = {}
    res["nullsd_table"] = {}
    k1: dict[str, Any] = {}
    for pool in ("early", "late", "harc32"):
        cells = cells_by_pool[pool]
        s_real = _proj_cells(cells, r_content, band)
        s_rand = _proj_cells_multi(cells, rand_dirs, band)
        for fam in ("F1", "F2"):
            fns = _contrast_fns(fam)
            for term, fn in fns.items():
                c_real = fn(s_real)
                c_rand = fn(s_rand)                       # (n_items, K)
                null_sd = float(np.sqrt(np.nanmean(np.nanvar(c_rand, axis=1, ddof=1))))
                pooled_sd = float(np.nanstd(c_rand.ravel(), ddof=1))
                key = f"{pool}|{fam}|{term}"
                st = standardised(c_real, null_sd, seed=_seed(key))
                st["null_sd_per_item"] = null_sd
                st["null_sd_pooled"] = pooled_sd
                st["per_item_values_std"] = [round(float(x), 5) for x in (c_real / null_sd)]
                k1[key] = st
                res["nullsd_table"][key] = {"per_item": null_sd, "pooled": pooled_sd}
        # identity check T == CB + A (decisive test that the four cells are wired right)
        for fam in ("F1", "F2"):
            t = k1_terms(s_real, fam)
            res.setdefault("identity_checks", {})[f"{pool}|{fam}|T_eq_CB_plus_A_maxabs"] = \
                float(np.max(np.abs(t["T"] - (t["CB"] + t["A"]))))
    res["candidates"]["K1"] = k1

    # ---- ROBUSTNESS / pre-registered fallback: the same decomposition read along a
    #      SUPERVISED probe direction fitted on the same disjoint corpus. If the
    #      diff-in-means axis is too noisy (G1/G3), this is the axis the plan switches to.
    r_probe = fit_probe_direction(fit_early[prim], fit_lab[prim], band, n_hs, d_model)
    cells_e0 = cells_by_pool["early"]
    s_probe = _proj_cells(cells_e0, r_probe, band)
    s_rand0 = _proj_cells_multi(cells_e0, rand_dirs, band)
    k1p: dict[str, Any] = {}
    for term, fn in _contrast_fns("F1").items():
        c_real = fn(s_probe)
        nsd = float(np.sqrt(np.nanmean(np.nanvar(fn(s_rand0), axis=1, ddof=1))))
        st = standardised(c_real, nsd, seed=_seed("probe" + term))
        st["null_sd_per_item"] = nsd
        st.pop("per_item_values_std", None)
        k1p[f"early|F1|{term}"] = st
    sp_in = project(fit_early[prim], r_probe, band)
    k1p["cos_with_r_content_at_band"] = float(np.mean(
        [abs(float(np.dot(r_probe[L], r_content[L]))) for L in range(band[0], band[1] + 1)]))
    k1p["fitting_corpus_d_in_sample"] = cohens_d(sp_in[fit_lab[prim]], sp_in[~fit_lab[prim]])
    k1p["note"] = ("BASELINE/ROBUSTNESS axis: supervised logistic probe fitted on the disjoint "
                   "fitting corpus, band-flattened then unit-normalised per layer. The plan's "
                   "registered fallback if the diff-in-means axis fails G1/G3.")
    res["candidates"]["K1_probe_direction"] = k1p

    # ---- G4b shuffled-label null band, at the primary pool/family
    cells_e = cells_by_pool["early"]
    fn_A = _contrast_fns("F1")["A"]
    fn_T = _contrast_fns("F1")["T"]
    null_sd_A = res["nullsd_table"]["early|F1|A"]["per_item"]
    null_sd_T = res["nullsd_table"]["early|F1|T"]["per_item"]
    rng = np.random.default_rng(23)
    shuf = {"A": [], "T": []}
    fv, fl = fit_early[prim], fit_lab[prim]
    for _ in range(N_SHUFFLE):
        lab = rng.permutation(fl)
        r = fit_dim(fv, lab)
        s = _proj_cells(cells_e, r, band)
        shuf["A"].append(float(np.nanmean(fn_A(s))) / null_sd_A)
        shuf["T"].append(float(np.nanmean(fn_T(s))) / null_sd_T)
    res["G4_shuffled_label_null"] = {
        k: {"terms_std": [round(x, 4) for x in v], "mean": float(np.mean(v)),
            "sd": float(np.std(v, ddof=1)), "abs_p975": float(np.percentile(np.abs(v), 97.5))}
        for k, v in shuf.items()}
    res["G4_random_direction_null_centres"] = {
        f"early|F1|{t}": float(np.nanmean(_contrast_fns("F1")[t](
            _proj_cells_multi(cells_e, rand_dirs, band))) / res["nullsd_table"][f"early|F1|{t}"]["per_item"])
        for t in ("O", "CB", "A", "T")}

    # ---- G5 placebo equivalence (coherence 2x2 interaction)
    s_real_e = _proj_cells(cells_e, r_content, band)
    s_rand_e = _proj_cells_multi(cells_e, rand_dirs, band)
    coh_real = _coh_fn(s_real_e)
    coh_rand = _coh_fn(s_rand_e)
    coh_null_sd = float(np.sqrt(np.nanmean(np.nanvar(coh_rand, axis=1, ddof=1))))
    coh_std = coh_real / coh_null_sd
    res["G5_placebo"] = {
        "interaction_std": standardised(coh_real, coh_null_sd, seed=5),
        "tost_margin_0.40": tost(coh_std, 0.40, alpha=0.05),
        "null_sd_per_item": coh_null_sd,
    }

    # ---- G6 NLL match diagnostic (licenses or forbids the coherence subtraction)
    def cellwise(arr: np.ndarray) -> dict[str, float]:
        return {c: float(np.nanmean(arr[np.arange(n_items) * len(GRID_CELLS) + k]))
                for k, c in enumerate(GRID_CELLS)}
    nll_cells = cellwise(nll)
    saf_pen = ((nll_cells["saf|F1|H|ben"] + nll_cells["saf|F1|B|haz"]) / 2
               - (nll_cells["saf|F1|H|haz"] + nll_cells["saf|F1|B|ben"]) / 2)
    coh_pen = ((nll_cells["coh|F1|A|B"] + nll_cells["coh|F1|B|A"]) / 2
               - (nll_cells["coh|F1|A|A"] + nll_cells["coh|F1|B|B"]) / 2)
    licensed = bool(coh_pen <= saf_pen + 1e-9) and bool(abs(coh_pen) >= 0.5 * abs(saf_pen))
    res["G6_nll_match"] = {
        "cell_mean_prefix_logprob": nll_cells,
        "safety_offdiagonal_penalty": saf_pen,
        "coherence_offdiagonal_penalty": coh_pen,
        "subtraction_licensed": licensed,
        "note": ("penalty = mean logprob on the off-diagonal (mismatched) cells minus the "
                 "matched cells; more negative = a harsher mismatch penalty. Subtraction is "
                 "licensed only when the coherence crossing's penalty is at least as severe "
                 "as the safety crossing's."),
    }
    # A_net, both ways
    a_std = np.asarray(k1["early|F1|A"]["per_item_values_std"], dtype=np.float64)
    if licensed:
        a_net_vals = a_std - coh_std
        a_net_kind = "placebo_subtracted"
        upper_bound = False
    else:
        # covariate-adjusted: regress the per-item readout on the per-item NLL penalty
        pen_i = ((nll[np.arange(n_items) * len(GRID_CELLS) + GRID_CELLS.index("saf|F1|H|ben")]
                  + nll[np.arange(n_items) * len(GRID_CELLS) + GRID_CELLS.index("saf|F1|B|haz")]) / 2
                 - (nll[np.arange(n_items) * len(GRID_CELLS) + GRID_CELLS.index("saf|F1|H|haz")]
                    + nll[np.arange(n_items) * len(GRID_CELLS) + GRID_CELLS.index("saf|F1|B|ben")]) / 2)
        ok = np.isfinite(pen_i) & np.isfinite(a_std)
        if ok.sum() > 5 and np.nanstd(pen_i[ok]) > 0:
            X = np.column_stack([np.ones(ok.sum()), pen_i[ok]])
            beta, *_ = np.linalg.lstsq(X, a_std[ok], rcond=None)
            resid = a_std[ok] - X @ beta
            a_net_vals = np.full_like(a_std, np.nan)
            a_net_vals[ok] = resid + beta[0]
        else:
            a_net_vals = a_std.copy()
        a_net_kind = "nll_covariate_adjusted_UPPER_BOUND"
        upper_bound = True
    res["A_net"] = standardised(a_net_vals[np.isfinite(a_net_vals)], 1.0, seed=6)
    res["A_net"].update({"kind": a_net_kind, "is_upper_bound": upper_bound})
    # The coherence 2x2 uses a DIFFERENT topic pair per item, so the item-wise pairing
    # between A_i and the placebo interaction is arbitrary and subtracting per item adds
    # the placebo's own variance to A_net. The mean-subtracted variant removes the same
    # bias without that variance inflation, so both are reported.
    if licensed:
        res["A_net_mean_subtracted"] = standardised(a_std - float(np.nanmean(coh_std)), 1.0, seed=7)
        res["A_net_mean_subtracted"]["kind"] = "placebo_mean_subtracted"
    else:
        res["A_net_mean_subtracted"] = {"kind": "not_applicable_G6_failed"}

    # ---- K2 prior + graded-harm slope (PROMPT-site readout)
    z = shard.load_npz(hdir / "aux.npz")
    aux_prompt = z["prompt"]
    aux_group = z["groups"].astype(str)
    aux_rung = z["rungs"]
    aux_item = z["items"].astype(str)
    aux_kind = z["kinds"].astype(str)
    s_aux = project(aux_prompt, r_content, band)
    is_cl = aux_group == "contentless"
    empty_val = float(s_aux[is_cl & (aux_kind == "empty")][0]) if (is_cl & (aux_kind == "empty")).any() else float("nan")
    neutral_vals = s_aux[is_cl & (aux_kind == "neutral")]
    # null-SD for the prompt-site readout from the random directions
    s_aux_rand = project_multi(aux_prompt, rand_dirs, band)
    prior_null_sd = float(np.nanstd(s_aux_rand[is_cl].ravel(), ddof=1))
    is_l = aux_group == "ladder"
    slopes = []
    for iid in sorted(set(aux_item[is_l].tolist())):
        m = is_l & (aux_item == iid)
        x = aux_rung[m].astype(np.float64)
        y = s_aux[m].astype(np.float64)
        if len(x) >= 3 and x.std() > 0:
            slopes.append(float(np.polyfit(x, y, 1)[0]))
    slope_arr = np.asarray(slopes)
    # slope null: same OLS on random-direction projections
    slope_null = []
    for k in range(rand_dirs.shape[1]):
        sk = s_aux_rand[:, k]
        vals = []
        for iid in sorted(set(aux_item[is_l].tolist())):
            m = is_l & (aux_item == iid)
            x = aux_rung[m].astype(np.float64)
            if len(x) >= 3 and x.std() > 0:
                vals.append(float(np.polyfit(x, sk[m].astype(np.float64), 1)[0]))
        slope_null.append(np.mean(vals))
    slope_null_sd = float(np.std(slope_null, ddof=1))
    # An absolute projection (unlike a contrast) does not cancel the residual stream's
    # strong anisotropy, so it is ALSO reported as a fraction of the activation norm at the
    # band -- a scale-free quantity that makes no isotropy assumption at all.
    cl_norm = float(np.nanmean(np.linalg.norm(
        aux_prompt[is_cl][:, lo:hi + 1].astype(np.float32), axis=-1)))
    res["candidates"]["K2"] = {
        "prior": {**standardised(neutral_vals, prior_null_sd, seed=2),
                  "prior_as_fraction_of_activation_norm": float(np.nanmean(neutral_vals)) / max(cl_norm, 1e-9),
                  "mean_activation_norm_at_band": cl_norm,
                  "empty_message_value_raw": empty_val,
                  "empty_message_value_std": empty_val / prior_null_sd if prior_null_sd > 0 else float("nan"),
                  "null_sd_per_item": prior_null_sd},
        "slope": {**standardised(slope_arr, slope_null_sd, seed=3),
                  "null_sd_per_item": slope_null_sd,
                  "rung_means_raw": {int(r): float(np.nanmean(s_aux[is_l & (aux_rung == r)]))
                                     for r in sorted(set(aux_rung[is_l].tolist()))}},
    }

    # ---- K3 benign-only footprint (no harmful text anywhere in its own pipeline)
    is_b = aux_group == "benign_only"
    B = aux_prompt[is_b].astype(np.float32)[:, lo:hi + 1].reshape(int(is_b.sum()), -1)
    C = aux_prompt[is_cl].astype(np.float32)[:, lo:hi + 1].reshape(int(is_cl.sum()), -1)
    disp = float(np.linalg.norm(B.mean(0) - C.mean(0)))
    rng2 = np.random.default_rng(31)
    within = []
    for _ in range(20):
        p = rng2.permutation(len(B))
        h = len(B) // 2
        within.append(float(np.linalg.norm(B[p[:h]].mean(0) - B[p[h:2 * h]].mean(0))))
    within_med = float(np.median(within))
    foot_boot = []
    for _ in range(2000):
        idx = rng2.integers(0, len(B), len(B))
        foot_boot.append(float(np.linalg.norm(B[idx].mean(0) - C.mean(0))) / max(within_med, 1e-9))
    res["candidates"]["K3"] = {
        "footprint": {
            "value": disp / max(within_med, 1e-9),
            "ci95": [float(np.percentile(foot_boot, 2.5)), float(np.percentile(foot_boot, 97.5))],
            "raw_displacement_L2": disp,
            "within_benign_median_displacement": within_med,
            "definition": ("||mean(benign-set acts) - mean(contentless acts)||_2 at the frozen band, "
                           "divided by the median half-split displacement WITHIN the benign set. "
                           "Self-normalising, single-model, parent-free, no harmful text."),
        },
        "stable_rank": {
            "down_proj_mean_at_band": float(np.nanmean(sr_down[max(lo - 1, 0):hi])),
            "o_proj_mean_at_band": float(np.nanmean(sr_o[max(lo - 1, 0):hi])),
            "mean_at_band": float(np.nanmean([np.nanmean(sr_down[max(lo - 1, 0):hi]),
                                              np.nanmean(sr_o[max(lo - 1, 0):hi])])),
            "down_proj_by_layer": [float(x) for x in sr_down],
            "o_proj_by_layer": [float(x) for x in sr_o],
            "definition": "mean stable rank ||W||_F^2/||W||_2^2 over the frozen band, WEIGHTS ONLY, 0 prompts.",
        },
    }

    # ---- K4 persistence
    z = shard.load_npz(hdir / "k4.npz")
    k4_proj = z["proj"]            # (48, n_hs, 128, K)
    k4_lab = z["labels"].astype(str)
    k4_item = z["items"].astype(str)
    band_proj = k4_proj[:, lo:hi + 1, :, 0].mean(axis=1)     # channel 0 = r_content
    haz = band_proj[k4_lab == "haz"]
    ben = band_proj[k4_lab == "ben"]
    n_pair = min(len(haz), len(ben))
    d_t = (haz[:n_pair] - ben[:n_pair])
    res["candidates"]["K4"] = {
        **fit_tau(np.nanmean(d_t, axis=0)),
        "d_of_t": [float(x) for x in np.nanmean(d_t, axis=0)],
        "n_items": int(n_pair),
        "tau_bootstrap_ci": None,
    }
    taus = []
    rng3 = np.random.default_rng(41)
    for _ in range(200):
        idx = rng3.integers(0, n_pair, n_pair)
        f = fit_tau(np.nanmean(d_t[idx], axis=0))
        if f.get("tau") is not None:
            taus.append(f["tau"])
    if taus:
        res["candidates"]["K4"]["tau_bootstrap_ci"] = [float(np.percentile(taus, 2.5)),
                                                       float(np.percentile(taus, 97.5))]
        res["candidates"]["K4"]["tau_bootstrap_n_ok"] = len(taus)

    # ---- K5 domain profile
    fams = [t["family"] for t in sub["confirmatory_items"]]
    fam_arr = np.asarray(fams)
    gain_by_fam, se_by_fam = {}, {}
    hh, hb = s_real_e["saf|F1|H|haz"], s_real_e["saf|F1|H|ben"]
    bh, bb = s_real_e["saf|F1|B|haz"], s_real_e["saf|F1|B|ben"]
    gain_i = 0.5 * ((hh - hb) + (bh - bb))          # hazardous-minus-benign prefix, pooled over requests
    gain_rand = 0.5 * ((s_rand_e["saf|F1|H|haz"] - s_rand_e["saf|F1|H|ben"])
                       + (s_rand_e["saf|F1|B|haz"] - s_rand_e["saf|F1|B|ben"]))
    gain_null_sd = float(np.sqrt(np.nanmean(np.nanvar(gain_rand, axis=1, ddof=1))))
    for f in sorted(set(fams)):
        m = fam_arr == f
        g = gain_i[m] / gain_null_sd
        mean, lo_, hi_, draws = boot_ci(g, b=2000, seed=_seed(f))
        gain_by_fam[f] = mean
        se_by_fam[f] = float(np.std(draws, ddof=1)) if len(draws) else float("nan")
    gvals = [v for v in gain_by_fam.values() if np.isfinite(v)]
    svals = [v for v in se_by_fam.values() if np.isfinite(v)]
    disp_val = (float(np.std(gvals, ddof=1) / max(float(np.mean(svals)), 1e-12))
                if len(gvals) >= 2 and svals else float("nan"))
    res["candidates"]["K5"] = {
        "profile": gain_by_fam,
        "bootstrap_se_by_family": se_by_fam,
        "dispersion": disp_val,
        "n_families": len(gvals),
        "gain_null_sd": gain_null_sd,
        "definition": "SD across the 6 XSTest harm families of the null-SD-standardised hazardous-minus-benign prefix gain, divided by the mean bootstrap SE of those gains.",
    }

    # ---- BASELINES (clearly labelled; the logit one is NOT a deliverable)
    y = np.array([1] * n_items * 2 + [0] * n_items * 2)
    X = np.concatenate([cells_e["saf|F1|H|haz"], cells_e["saf|F1|B|haz"],
                        cells_e["saf|F1|H|ben"], cells_e["saf|F1|B|ben"]])
    Xb = X[:, lo:hi + 1].astype(np.float32).reshape(len(X), -1)
    pos = np.concatenate([s_real_e["saf|F1|H|haz"], s_real_e["saf|F1|B|haz"]])
    neg = np.concatenate([s_real_e["saf|F1|H|ben"], s_real_e["saf|F1|B|ben"]])
    gap_cells = cellwise(logit_gap)
    gap_post_cells = cellwise(logit_gap_post)
    res["baselines"] = {
        "B1_diff_in_means_score": {
            "label": "BASELINE -- plain r_content projection, no decomposition",
            "auroc_haz_vs_ben_prefix": auroc(pos, neg),
            "cohens_d": cohens_d(pos, neg),
            "mean_difference_null_sd": float((pos.mean() - neg.mean()) / gain_null_sd),
        },
        "B2_raw_hidden_probe": {
            "label": "BASELINE -- non-featurised control: 5-fold CV logistic probe on the RAW pooled band vectors",
            **probe_auroc(Xb, y, seed=1),
        },
        "B3_cluster_separation": {
            "label": "BASELINE -- activation cluster separation at the band",
            "fisher_ratio": fisher_ratio(Xb[y == 1], Xb[y == 0]),
            "silhouette": silhouette_two(Xb[y == 1], Xb[y == 0]),
        },
        "B4_refusal_logit_gap": {
            "label": "BASELINE -- LOGIT-SIDE, NOT-A-DELIVERABLE under the run invariant",
            "note": ("Two read sites. (a) REQUEST-side, at the first response token: it has not "
                     "seen the continuation, so its continuation contrast is STRUCTURALLY zero and "
                     "it is only a fair baseline for the orientation term O. (b) POST-continuation, "
                     "at the token following the teacher-forced continuation: this one has seen the "
                     "continuation and is the fair logit-side analogue of CB, A and T."),
            "request_site_cell_means": gap_cells,
            "request_site_orientation_analogue": float(
                0.5 * ((gap_cells["saf|F1|H|haz"] + gap_cells["saf|F1|H|ben"])
                       - (gap_cells["saf|F1|B|haz"] + gap_cells["saf|F1|B|ben"]))),
            "post_continuation_cell_means": gap_post_cells,
            "post_continuation_arming_analogue": float(
                (gap_post_cells["saf|F1|H|haz"] - gap_post_cells["saf|F1|H|ben"])
                - (gap_post_cells["saf|F1|B|haz"] - gap_post_cells["saf|F1|B|ben"])),
            "post_continuation_T_analogue": float(
                gap_post_cells["saf|F1|H|haz"] - gap_post_cells["saf|F1|H|ben"]),
            "post_continuation_haz_minus_ben_prefix": float(
                0.5 * ((gap_post_cells["saf|F1|H|haz"] - gap_post_cells["saf|F1|H|ben"])
                       + (gap_post_cells["saf|F1|B|haz"] - gap_post_cells["saf|F1|B|ben"]))),
        },
    }

    # ---- position curve A(early) vs A(late), and the genuine per-position map
    res["position_curve"] = {
        "A_early_std": k1["early|F1|A"]["term_std"],
        "A_late_std": k1["late|F1|A"]["term_std"],
        "A_harc32_std": k1["harc32|F1|A"]["term_std"],
        "T_early_std": k1["early|F1|T"]["term_std"],
        "T_late_std": k1["late|F1|T"]["term_std"],
    }
    pmap = hdir / "proj.npz"
    if shard.exists(pmap):
        z = shard.load_npz(pmap)
        pr = z["proj"]        # (n_items*12, n_hs, npos, K)
        idx = {c: np.arange(n_items) * len(GRID_CELLS) + k for k, c in enumerate(GRID_CELLS)}
        def band_pos(cell):
            return pr[idx[cell]][:, lo:hi + 1, :, 0].mean(axis=1)   # (n_items, npos)
        a_pos = ((band_pos("saf|F1|H|haz") - band_pos("saf|F1|H|ben"))
                 - (band_pos("saf|F1|B|haz") - band_pos("saf|F1|B|ben")))
        t_pos = band_pos("saf|F1|H|haz") - band_pos("saf|F1|H|ben")
        res["position_curve"]["A_by_position"] = [float(x) for x in np.nanmean(a_pos, axis=0)]
        res["position_curve"]["T_by_position"] = [float(x) for x in np.nanmean(t_pos, axis=0)]
        # layer x position map of the hazardous-minus-benign prefix contrast
        lp = (pr[idx["saf|F1|H|haz"]][:, :, :, 0] - pr[idx["saf|F1|H|ben"]][:, :, :, 0]).mean(axis=0)
        res["layer_by_position_map"] = [[round(float(v), 5) for v in row] for row in lp]
    return res


# ---------------------------------------------------------------------------
# S1 table
# ---------------------------------------------------------------------------

def _term_vector(ck: dict[str, Any], candidate: str, term: str) -> np.ndarray | None:
    """Per-unit standardised values for the candidate's registered term, or None if the
    candidate is not a per-unit quantity in this checkpoint."""
    if candidate == "K1":
        v = ck["candidates"]["K1"].get(f"early|F1|{term}")
        if not v or "per_item_values_std" not in v:
            return None
        return np.asarray(v["per_item_values_std"], dtype=np.float64)
    return None


def _term_scalar(ck: dict[str, Any], candidate: str, term: str) -> tuple[float, list[float] | None]:
    c = ck["candidates"][candidate]
    if candidate == "K1":
        v = c[f"early|F1|{term}"]
        return v["term_std"], v.get("ci95")
    if candidate == "K2":
        v = c[term]
        return v["term_std"], v.get("ci95")
    if candidate == "K3":
        if term == "footprint":
            return c["footprint"]["value"], c["footprint"]["ci95"]
        return c["stable_rank"]["mean_at_band"], None
    if candidate == "K4":
        t = c.get("tau")
        return (float(t) if t is not None else float("nan")), c.get("tau_bootstrap_ci")
    if candidate == "K5":
        return c["dispersion"], None
    raise KeyError(candidate)


def build_s1_table(per_ckpt: dict[str, dict[str, Any]], prereg: dict[str, Any],
                   target_map: dict[str, str], arms: Sequence[str],
                   band_artefact: dict[str, dict[str, bool]]) -> list[dict[str, Any]]:
    rows = []
    thr = prereg["thresholds"]["s1_margin_null_sd"]
    for cand, spec in prereg["candidates"].items():
        term = spec["registered_term"]
        tgt_tag = target_map.get(spec["registered_checkpoint"])
        row: dict[str, Any] = {
            "candidate": cand, "name": spec["name"],
            "registered_checkpoint": spec["registered_checkpoint"],
            "registered_term": term,
            "registered_arm_ordering": spec["registered_arm_ordering"],
            "clustering_unit": spec["clustering_unit"],
            "margins": {}, "pass_per_arm": {}, "band_artefact_flag": {},
        }
        if tgt_tag is None or tgt_tag not in per_ckpt:
            row.update({"S1": "UNMET_BY_UNAVAILABILITY",
                        "reason": f"registered checkpoint {spec['registered_checkpoint']} not harvested"})
            rows.append(row)
            continue
        tv, tci = _term_scalar(per_ckpt[tgt_tag], cand, term)
        row["target_term_std"] = tv
        row["target_ci95"] = tci
        row["achieved_r"] = per_ckpt[tgt_tag]["candidates"]["K1"][f"early|F1|{term}"]["achieved_r"] \
            if cand == "K1" else None
        row["mde_1.96se"] = per_ckpt[tgt_tag]["candidates"]["K1"][f"early|F1|{term}"]["mde_1.96se"] \
            if cand == "K1" else None
        tvec = _term_vector(per_ckpt[tgt_tag], cand, term)
        n_arms_present = 0
        for arm in arms:
            if arm not in per_ckpt:
                row["margins"][arm] = None
                row["pass_per_arm"][arm] = "ARM_UNAVAILABLE"
                continue
            n_arms_present += 1
            av, _ = _term_scalar(per_ckpt[arm], cand, term)
            avec = _term_vector(per_ckpt[arm], cand, term)
            if tvec is not None and avec is not None and len(tvec) == len(avec):
                m, lo, hi = paired_boot_ci(tvec, avec, seed=_seed(cand + arm))
                ci_excl = bool(lo * hi > 0)
            else:
                m = float(tv - av)
                lo = hi = float("nan")
                ci_excl = False
            row["margins"][arm] = {"arm_term_std": av, "margin": m, "ci95": [lo, hi],
                                   "ci_excludes_zero": ci_excl,
                                   "paired_item_clustered": tvec is not None and avec is not None}
            ok = bool(m >= thr) and (ci_excl if (tvec is not None and avec is not None) else True)
            row["pass_per_arm"][arm] = "PASS" if ok else "FAIL"
            row["band_artefact_flag"][arm] = band_artefact.get(arm, {}).get(f"{cand}|{term}", False)
        verdicts = [v for v in row["pass_per_arm"].values() if v != "ARM_UNAVAILABLE"]
        if not verdicts:
            row["S1"] = "UNMET_BY_UNAVAILABILITY"
        elif len(verdicts) < len(arms):
            row["S1"] = ("SINGLE_ARM_PASS" if all(v == "PASS" for v in verdicts) else "FAIL")
            row["caveat"] = "criterion requires BOTH non-safety arms; only one was available"
        else:
            row["S1"] = "PASS" if all(v == "PASS" for v in verdicts) else "FAIL"
        rows.append(row)
    return rows


__all__ = ["analyse_checkpoint", "build_s1_table", "choose_band", "split_half_cosine",
           "positive_control", "POOLS", "RAND_SEED"]
