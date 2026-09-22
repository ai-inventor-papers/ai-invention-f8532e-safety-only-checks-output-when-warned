#!/usr/bin/env python3
"""Analysis of the causal depth x site grid (iter-4 experiment_2).

Reads ONLY the checkpointed cells under out/cells/<model>/ (+ direction .npz files under
out/private/) written by method.py, and writes:
  results/<prefix>analysis.json     -- everything, nested by model -> section
  results/<prefix>summary_tables.md -- compact human tables
  <prefix>method_out.json           -- exp_gen_sol_out-schema datasets

Never loads a model / torch. Pure numpy + the tested stats helpers in src/stats.py.

Usage:
  WS/.venv/bin/python src/analyze.py --models smoke --out-prefix smoke_
  WS/.venv/bin/python src/analyze.py --models instruct,saferl
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loguru import logger  # noqa: E402

import stats as S  # noqa: E402
from common import (ASSETS, BANDS, CELLS, FIGS, LEDGER, OUT, PRIVATE, RESULTS, WS,  # noqa: E402
                    _clean, bands_for, jdump, jload, setup_logging, utc_now)

B_BOOT = 2000
SEED = 20260921  # analysis-local seed (independent of the experiment's SEED); deterministic.
BAND_NAMES = list(BANDS.keys())  # ["B1",...,"B6"], names are shared across models
OUTCOMES6 = ["RD_harm", "RD_hb", "G1_harm", "G1_hb", "T1ref_harm", "T1ref_hb"]
CAUSAL_OUTCOMES = ["RD_harm", "RD_hb", "T1ref_harm"]  # the causal_rule outcomes named in prereg
L_OF = {"instruct": 36, "saferl": 36, "abliterated": 36, "smoke": 28}
IS_SMOKE = {"instruct": False, "saferl": False, "abliterated": False, "smoke": True}
I1_DIRS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/"
               "gen_art/gen_art_experiment_1/out/released/directions")
IT2_REF_1 = ("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/"
             "gen_art_experiment_3/results/s3/s3_results.json")
IT2_REF_2 = ("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/"
             "gen_art_experiment_1/results/judge_extension.json")


# ================================================================================================
# generic helpers
# ================================================================================================
def bands_of(model: str) -> dict:
    return BANDS if not IS_SMOKE.get(model, False) else bands_for(L_OF[model])


def band_containing(model: str, layer: int) -> str | None:
    for b, ls in bands_of(model).items():
        if layer in ls:
            return b
    return None


def nz(x):
    """NaN -> None recursively handled by jdump's _clean; here just cast numpy scalars."""
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    return x


HOOK_HASH_BY_MODEL: dict[str, str] = {}   # set by main() before analyze_model() runs; hash-filters every cell load


def find_cell_files(model: str, name: str) -> list[Path]:
    d = CELLS / model
    if not d.exists():
        return []
    return sorted(d.glob(f"{name}__*.npz"))


def load_cell(model: str, name: str) -> dict | None:
    cands = find_cell_files(model, name)
    if not cands:
        return None
    expect = HOOK_HASH_BY_MODEL.get(model)
    if expect:
        matched = [p for p in cands if p.stem.rsplit("__", 1)[-1] == expect]
        if matched:
            cands = matched
        else:
            logger.warning(f"{model}/{name}: none of {[p.name for p in cands]} match expected hook_hash "
                            f"{expect!r}; treating as missing")
            return None
    best = max(cands, key=lambda p: p.stat().st_mtime)
    if len(cands) > 1:
        logger.warning(f"{model}/{name}: {len(cands)} hook-hash variants found "
                        f"({[p.name for p in cands]}); using newest mtime {best.name}")
    json_p = best.parent / (best.stem + ".json")
    if not json_p.exists():
        logger.warning(f"{model}/{name}: {best.name} has no matching .json; treating as missing")
        return None
    try:
        arrays = dict(np.load(best))
        meta = json.loads(json_p.read_text())
    except Exception as e:  # noqa: BLE001 - corrupt/partial checkpoint -> NOT_RUN, never crash
        logger.warning(f"{model}/{name}: failed to load ({e}); treating as missing")
        return None
    return {"arrays": arrays, "meta": meta, "path": str(best)}


def rows_records(arrays: dict, rows_meta: list[dict]) -> list[dict]:
    n = len(rows_meta)
    recs = []
    for i in range(n):
        rec = dict(rows_meta[i])
        for k, arr in arrays.items():
            if hasattr(arr, "__len__") and len(arr) == n:
                rec[k] = arr[i]
        recs.append(rec)
    return recs


def vec_from_records(records: list[dict], canon_ids: list[str], col: str):
    """First-seen-wins per item_id (records should be pre-ordered canonical-source-first).
    Returns (vector aligned to canon_ids, max abs diff among duplicate item_ids for that col)."""
    by_id: dict[str, list] = {}
    for r in records:
        by_id.setdefault(r["item_id"], []).append(r[col])
    out = np.full(len(canon_ids), np.nan, dtype=float)
    diffs = []
    for i, iid in enumerate(canon_ids):
        vals = by_id.get(iid)
        if not vals:
            continue
        out[i] = float(vals[0])
        if len(vals) > 1:
            diffs.append(float(max(abs(v - vals[0]) for v in vals[1:])))
    return out, (max(diffs) if diffs else None)


def proj_from_records(records: list[dict], canon_ids: list[str], L: int):
    by_id: dict[str, np.ndarray] = {}
    for r in records:
        if r["item_id"] not in by_id:
            by_id[r["item_id"]] = np.asarray(r["proj"], dtype=float)
    out = np.full((len(canon_ids), L, 3), np.nan, dtype=float)
    for i, iid in enumerate(canon_ids):
        if iid in by_id:
            out[i] = by_id[iid]
    return out


def canon_eval_ids(items: dict, model: str) -> tuple[list[str], np.ndarray, np.ndarray]:
    k = 8 if IS_SMOKE.get(model, False) else None
    ids_h = [x["item_id"] for x in items["harm_eval"][:k]]
    ids_b = [x["item_id"] for x in items["hb_eval"][:k]]
    ids = ids_h + ids_b
    mask_h = np.array([True] * len(ids_h) + [False] * len(ids_b))
    mask_b = ~mask_h
    return ids, mask_h, mask_b


def canon_decod_ids(items: dict, model: str) -> tuple[list[str], np.ndarray]:
    k = 8 if IS_SMOKE.get(model, False) else None
    ids_h = [x["item_id"] for x in items["decod_harm"][:k]]
    ids_b = [x["item_id"] for x in items["decod_hb"][:k]]
    ids = ids_h + ids_b
    y = np.array([1] * len(ids_h) + [0] * len(ids_b))
    return ids, y


def cohens_d_arr(a: np.ndarray, b: np.ndarray) -> float:
    return S.cohens_d(a, b)


def bootstrap_meandiff_delta(harm_arm, hb_arm, harm_0, hb_0, B=B_BOOT, seed=SEED):
    harm_arm = np.asarray(harm_arm, float); hb_arm = np.asarray(hb_arm, float)
    harm_0 = np.asarray(harm_0, float); hb_0 = np.asarray(hb_0, float)
    fh = np.isfinite(harm_arm) & np.isfinite(harm_0)
    fb = np.isfinite(hb_arm) & np.isfinite(hb_0)
    ha, h0, ba, b0 = harm_arm[fh], harm_0[fh], hb_arm[fb], hb_0[fb]
    if ha.size == 0 or ba.size == 0:
        return {"delta": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"), "n_harm": int(ha.size),
                "n_hb": int(ba.size)}
    rng = np.random.default_rng(seed)
    idxH = rng.integers(0, ha.size, size=(B, ha.size))
    idxB = rng.integers(0, ba.size, size=(B, ba.size))
    boots = (ha[idxH].mean(1) - ba[idxB].mean(1)) - (h0[idxH].mean(1) - b0[idxB].mean(1))
    point = (ha.mean() - ba.mean()) - (h0.mean() - b0.mean())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"delta": float(point), "ci_lo": float(lo), "ci_hi": float(hi), "n_harm": int(ha.size),
            "n_hb": int(ba.size)}


def bootstrap_cohend_delta(a_arm, b_arm, a_0, b_0, B=B_BOOT, seed=SEED):
    """d(arm) = cohens_d(a_arm,b_arm); Delta = d(arm) - d(0), independent item resampling of the
    a-side and b-side, paired across arm/0 via the same resample indices."""
    a_arm = np.asarray(a_arm, float); b_arm = np.asarray(b_arm, float)
    a_0 = np.asarray(a_0, float); b_0 = np.asarray(b_0, float)
    fa = np.isfinite(a_arm) & np.isfinite(a_0)
    fb = np.isfinite(b_arm) & np.isfinite(b_0)
    aa, a0, bb, b0 = a_arm[fa], a_0[fa], b_arm[fb], b_0[fb]
    na, nb = aa.size, bb.size
    if na < 2 or nb < 2:
        return {"delta": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"), "n_a": int(na), "n_b": int(nb)}
    rng = np.random.default_rng(seed)
    idxA = rng.integers(0, na, size=(B, na))
    idxB = rng.integers(0, nb, size=(B, nb))

    def d_batch(A, Bm):
        mA, mB = A.mean(1), Bm.mean(1)
        vA, vB = A.var(1, ddof=1), Bm.var(1, ddof=1)
        pooled = np.sqrt(((na - 1) * vA + (nb - 1) * vB) / (na + nb - 2))
        with np.errstate(invalid="ignore", divide="ignore"):
            return (mA - mB) / pooled

    dA = d_batch(aa[idxA], bb[idxB])
    d0 = d_batch(a0[idxA], b0[idxB])
    boots = dA - d0
    boots = boots[np.isfinite(boots)]
    point = cohens_d_arr(aa, bb) - cohens_d_arr(a0, b0)
    if boots.size == 0:
        return {"delta": float(point), "ci_lo": float("nan"), "ci_hi": float("nan"), "n_a": int(na), "n_b": int(nb)}
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"delta": float(point), "ci_lo": float(lo), "ci_hi": float(hi), "n_a": int(na), "n_b": int(nb)}


# ================================================================================================
# grid assembly: per (model, band) -> {"F":..., "N6":..., "N6perp":..., "POS":..., "RF":{j:...}, "RN6":{j:...}}
# ================================================================================================
def assemble_band(model: str, band: str, canon_ids: list[str], L: int) -> dict:
    all_records: list[dict] = []
    group_status = {}
    for g in ("grid1", "grid2", "grid3"):
        c = load_cell(model, f"P_{band}_{g}")
        if c is None:
            group_status[g] = "missing"
            continue
        group_status[g] = "ok"
        arrs = {k: c["arrays"][k] for k in ("RD", "G1", "T1ref", "tok1", "proj") if k in c["arrays"]}
        all_records += rows_records(arrs, c["meta"]["rows"])

    def sub(arm, draw=0):
        return [r for r in all_records if r["arm"] == arm and r.get("draw", 0) == draw]

    out = {"group_status": group_status, "determinism": {}}
    for arm in ("F", "N6", "N6perp", "POS"):
        recs = sub(arm)
        if not recs:
            out[arm] = None
            continue
        entry = {}
        for col in ("RD", "G1", "T1ref"):
            v, dmax = vec_from_records(recs, canon_ids, col)
            entry[col] = v
            if dmax is not None:
                out["determinism"][f"{arm}.{col}"] = dmax
        entry["proj"] = proj_from_records(recs, canon_ids, L)
        entry["n_items_present"] = int(np.isfinite(entry["RD"]).sum())
        out[arm] = entry
    for arm_key, tag in (("RF", "RF"), ("RN6", "RN6")):
        draws = sorted({r["draw"] for r in all_records if r["arm"] == arm_key})
        dd = {}
        for j in draws:
            recs = sub(arm_key, j)
            entry = {}
            for col in ("RD", "G1", "T1ref"):
                v, _ = vec_from_records(recs, canon_ids, col)
                entry[col] = v
            entry["proj"] = proj_from_records(recs, canon_ids, L)
            dd[j] = entry
        out[tag] = dd
    return out


def stack_draws(band_data: dict, tag: str, col: str, canon_ids: list[str]) -> np.ndarray:
    dd = band_data.get(tag) or {}
    if not dd:
        return np.zeros((0, len(canon_ids)))
    return np.stack([dd[j][col] for j in sorted(dd)], axis=0)


def stack_draws_proj(band_data: dict, tag: str, canon_ids: list[str], L: int) -> np.ndarray:
    dd = band_data.get(tag) or {}
    if not dd:
        return np.zeros((0, len(canon_ids), L, 3))
    return np.stack([dd[j]["proj"] for j in sorted(dd)], axis=0)


# ================================================================================================
# causal cell (paired_effect vs0 / vsR, holm, causal rule)
# ================================================================================================
def causal_cell(y_arm: np.ndarray, y0: np.ndarray, R_stack: np.ndarray, seed: int = SEED) -> dict:
    if y_arm is None or np.isfinite(y_arm).sum() == 0:
        return {"status": "NOT_RUN", "reason": "arm/band not present"}
    ev0 = S.paired_effect(y_arm, y0, seed=seed)
    per_draw = []
    if R_stack is not None and R_stack.shape[0] > 0:
        for j in range(R_stack.shape[0]):
            r = R_stack[j]
            if np.isfinite(r).sum() == 0:
                continue
            e = S.paired_effect(r, y0, seed=seed)
            if e["n"] > 0:
                per_draw.append(e["effect"])
    n_r = len(per_draw)
    if n_r > 0:
        evR = S.paired_effect(y_arm, y_b_draws=R_stack, seed=seed)
        emp_p = S.empirical_p(ev0["effect"], np.array(per_draw))
    else:
        evR = {"effect": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"), "p_signflip": float("nan"),
               "n": 0, "sd_diff": float("nan"), "mde_80": float("nan")}
        emp_p = float("nan")
    mean_0 = float(np.nanmean(y0)) if np.isfinite(y0).any() else None
    mean_T = float(np.nanmean(y_arm)) if np.isfinite(y_arm).any() else None
    mean_R = float(np.nanmean(R_stack)) if R_stack is not None and R_stack.size and np.isfinite(R_stack).any() \
        else None
    return {"status": "OK", "effect_vs0": ev0, "effect_vsR": evR, "n_R_draws": n_r,
            "empirical_p_envelope": emp_p, "per_draw_effects_vs0": per_draw,
            "mean_0": mean_0, "mean_T": mean_T, "mean_R": mean_R}


def apply_holm_and_causal(cells_by_band: dict) -> None:
    """cells_by_band: {band: causal_cell(...) result}. Mutates in place: adds p_holm + CAUSAL."""
    bands = list(cells_by_band.keys())
    pvals = [cells_by_band[b]["effect_vsR"]["p_signflip"] if cells_by_band[b]["status"] == "OK"
             else float("nan") for b in bands]
    holm_p = S.holm(pvals)
    for b, ph in zip(bands, holm_p):
        cell = cells_by_band[b]
        if cell["status"] != "OK":
            continue
        cell["p_holm"] = ph
        n_r = cell["n_R_draws"]
        emp_p = cell["empirical_p_envelope"]
        causal = (ph is not None and np.isfinite(ph) and ph < 0.05 and
                  (n_r < 19 or (np.isfinite(emp_p) and emp_p < 0.05)))
        cell["CAUSAL"] = bool(causal)


# ================================================================================================
# per-model analysis
# ================================================================================================
def analyze_model(model: str, items: dict) -> dict:
    L = L_OF[model]
    bands = list(bands_of(model).keys())
    canon_ids, mask_h, mask_b = canon_eval_ids(items, model)
    n_items = len(canon_ids)
    result: dict = {"model": model, "L": L, "n_eval_items": n_items, "bands": bands}

    arm0_cell = load_cell(model, "P_arm0")
    if arm0_cell is None:
        result["status"] = "NOT_RUN"
        result["reason"] = "P_arm0 cell missing"
        y0 = {c: np.full(n_items, np.nan) for c in ("RD", "G1", "T1ref")}
        proj0 = np.full((n_items, L, 3), np.nan)
    else:
        recs0 = rows_records({k: arm0_cell["arrays"][k] for k in ("RD", "G1", "T1ref", "proj")
                              if k in arm0_cell["arrays"]}, arm0_cell["meta"]["rows"])
        y0 = {}
        for col in ("RD", "G1", "T1ref"):
            v, _ = vec_from_records(recs0, canon_ids, col)
            y0[col] = v
        proj0 = proj_from_records(recs0, canon_ids, L)
        result["status"] = "OK"

    def split(v, mask):
        return v[mask]

    band_data = {}
    grid = {}   # grid[outcome][arm][band] = causal_cell dict
    determinism = {}
    n_items_by_band_arm = {}
    for band in bands:
        bd = assemble_band(model, band, canon_ids, L)
        band_data[band] = bd
        for k, v in bd["determinism"].items():
            determinism.setdefault(band, {})[k] = v
        for arm in ("F", "N6", "N6perp", "POS"):
            n_items_by_band_arm.setdefault(arm, {})[band] = (bd[arm]["n_items_present"] if bd[arm] else 0)

    diD_raw: dict = {}   # band -> "{arm}_minus_R_{outcome}" -> {item_id: diff} for cross-model DiD pairing
    diD_needed = {("F", "RD_harm"), ("F", "RD_hb"), ("F", "T1ref_harm"), ("N6", "RD_hb"), ("N6", "T1ref_hb")}
    canon_ids_masked_cache = {"harm": [i for i, m in zip(canon_ids, mask_h) if m],
                              "hb": [i for i, m in zip(canon_ids, mask_b) if m]}
    for outcome in OUTCOMES6:
        base, kind = outcome.rsplit("_", 1)
        mask = mask_h if kind == "harm" else mask_b
        grid[outcome] = {}
        for arm in ("F", "N6", "N6perp"):
            grid[outcome][arm] = {}
            R_tag = "RF" if arm in ("F",) else "RN6"
            for band in bands:
                bd = band_data[band]
                y_arm_full = bd[arm][base] if bd[arm] else None
                y_arm = split(y_arm_full, mask) if y_arm_full is not None else None
                y0_masked = split(y0[base], mask)
                R_full = stack_draws(bd, R_tag, base, canon_ids)
                R_masked = R_full[:, mask] if R_full.size else R_full
                cell = causal_cell(y_arm, y0_masked, R_masked)
                if arm == "N6perp":
                    cell["displacement_not_matched"] = True
                grid[outcome][arm][band] = cell
                if (arm, outcome) in diD_needed and y_arm is not None and R_masked.size:
                    r_mean = np.nanmean(R_masked, axis=0)
                    diff = y_arm - r_mean
                    ids = canon_ids_masked_cache[kind]
                    diD_raw.setdefault(band, {})[f"{arm}_minus_R_{outcome}"] = dict(zip(ids, diff.tolist()))
            apply_holm_and_causal(grid[outcome][arm])

    # ---- positive control: POS at B3,B4 vs 0 AND vs RF (matched displacement), all 6 outcomes ----
    pos_bands = [b for b in bands if b in ("B3", "B4")]
    positive_control = {}
    for outcome in OUTCOMES6:
        base, kind = outcome.rsplit("_", 1)
        mask = mask_h if kind == "harm" else mask_b
        positive_control[outcome] = {}
        for band in pos_bands:
            bd = band_data[band]
            y_arm_full = bd["POS"][base] if bd["POS"] else None
            if y_arm_full is None:
                positive_control[outcome][band] = {"status": "NOT_RUN", "reason": "POS arm not present"}
                continue
            y_arm = split(y_arm_full, mask)
            y0_masked = split(y0[base], mask)
            ev0 = S.paired_effect(y_arm, y0_masked, seed=SEED)
            R_full = stack_draws(bd, "RF", base, canon_ids)
            R_masked = R_full[:, mask] if R_full.size else R_full
            evR = S.paired_effect(y_arm, y_b_draws=R_masked, seed=SEED) if R_masked.size else None
            positive_control[outcome][band] = {"status": "OK", "effect_vs0": ev0, "effect_vsRF": evR,
                                               "label": "POSITIVE_CONTROL_generic_disruption"}

    # ---- lstar / n6_best (shared across readout blocks; never re-derived from a live model) ----
    l_star, l_star_source, n6_best, n6_best_source = load_lstar_n6best(model)

    # ---- gen cache: every gen{P,Dprime,E}_{band} cell present, loaded once ----
    gen_cache: dict = {}
    for site in ("P", "Dprime", "E"):
        for band in bands:
            gc = load_gen_records(model, site, band)
            if gc is not None:
                gen_cache[(model, site, band)] = gc

    # ---- judged 6x3 grid (GPU addendum): site x band x arm in {F,N6,N6perp,POS} ----
    judged_grid, diD_raw_judged = analyze_judged_grid(model, items, canon_ids, mask_h, mask_b, bands, gen_cache)

    # ---- genU_{band} (plan 9b, EXPLORATORY): does F's refusal effect survive removing its FperpU/N2-N3
    # component? ----
    genU = analyze_genU(model, canon_ids, mask_h, mask_b, bands)

    # ---- e2x2_E (plan section 6): site-E LATE-window (unedited, tokens 40-55) readout after an EARLY
    # (tokens 5-20) edit; N1-analogue at l_star, N6-analogue at n6_best ----
    e2x2 = analyze_e2x2E(model, l_star, n6_best, bands)

    # ---- genG_{B1..B6,ALL} (T3 disambiguation, EXPLORATORY): local (site-P) vs global (all-position)
    # ablation ----
    genG, diD_raw_genG = analyze_genG(model, canon_ids, mask_h, mask_b, judged_grid)

    # ---- T1 plan check: our arm-0 judged rates (genP) vs earlier-iteration judged rates ----
    arm0_genP_rates = arm0_rates_from_genP(model, bands)
    t1_plan_check = analyze_t1_plan_check(model, arm0_genP_rates)

    # ---- arm0_stability: arm-0 refused_harm/over_refusal_hb rate range across every judged cell family ----
    arm0_stability = analyze_arm0_stability(model, bands)

    # ---- decodability per site: P (decod_arm0), D'/E (decodgen_arm0 windows) ----
    decod_full = analyze_decodability_full(model, items, L)

    # ---- 2x2 decodable x causal, from the judged grid + per-site decodability ----
    two_by_two_judged = two_by_two_from_judged(decod_full, judged_grid)

    # ---- readouts under intervention: A_prompt stimuli (BL1_easy/hard never pooled; N1/N2/N6/N7) ----
    stim_readouts = analyze_stim_readouts(model, l_star, n6_best)

    # ---- readouts under intervention: eval items (P_{B}_grid1 proj; N1_eval etc.) ----
    readouts = analyze_readouts(model, band_data, y0, proj0, canon_ids, mask_h, mask_b, items)

    # ---- decode-window F-projection readout from gen cells' proj_win (windows D, E) ----
    decode_window_readouts = analyze_decode_window_readout(model, l_star, bands, gen_cache)

    # ---- spanD / spanE forward-only ----
    span_forward_only = {"D": analyze_span(model, "D"), "E": analyze_span(model, "E")}

    # ---- GSM8K collateral ----
    gsm = analyze_gsm(model)

    # ---- registered F1 judged generation cell (gen_P: 24+24 items, 48 tokens, B3/B4 x P) ----
    gen = analyze_gen(model)

    # ---- ARC collateral ----
    arc = analyze_arc(model)

    # ---- displacement summary ----
    disp = analyze_displacement(model, bands)

    # ---- directions / cosines ----
    dirs = analyze_directions(model, L)

    # ---- site sanity checks lifted from the gen{P,Dprime,E} cells' meta["checks"] ----
    site_checks = collect_site_checks(model, bands)

    # ---- judge-vs-keyword-proxy agreement, pooled over the whole judged grid (not just gen_P) ----
    agree_full_grid = judge_vs_proxy_agreement_full(gen_cache)

    result.update({
        "n_items_by_band_arm": n_items_by_band_arm,
        "determinism_max_abs_diff": determinism,
        "causal_grid_forward_only": grid,
        "positive_control_forward_only": positive_control,
        "l_star": l_star, "l_star_source": l_star_source, "n6_best": n6_best, "n6_best_source": n6_best_source,
        "causal_grid_judged": judged_grid,
        "genU_exploratory_FperpU": genU,
        "e2x2_E_site_readout": e2x2,
        "genG_global_ablation_control": genG,
        "t1_arm0_vs_prior_judged": t1_plan_check,
        "arm0_stability": arm0_stability,
        "decodability": decod_full,
        "two_by_two_decodable_causal": two_by_two_judged,
        "readouts_eval_items": readouts,
        "readouts_stimuli": stim_readouts,
        "readouts_decode_window": decode_window_readouts,
        "span_forward_only": span_forward_only,
        "gsm": gsm,
        "judged_generation_registered_gen_P": gen,
        "arc_collateral": arc,
        "displacement": disp,
        "directions": dirs,
        "site_checks_gen_grid": site_checks,
        "judge_vs_proxy_agreement_full_grid": agree_full_grid,
        "_diD_raw_forward": diD_raw,
        "_diD_raw_judged_grid": diD_raw_judged,
        "_diD_raw_genG": diD_raw_genG,
    })
    result["power_nulls"] = power_summary(result)
    return result


# ================================================================================================
# shared direction lookups (l_star, n6_best) -- never re-derived from a live model
# ================================================================================================
def load_lstar_n6best(model: str):
    if model == "smoke":
        l_star, l_star_source = int(28 * 0.7), "smoke formula int(L*0.7), no directions_disk_smoke.npz on disk"
    else:
        p = PRIVATE / f"directions_disk_{model}.npz"
        if p.exists():
            l_star, l_star_source = int(np.load(p)["l_star"]), str(p)
        else:
            l_star, l_star_source = None, "MISSING"
    p6 = PRIVATE / f"directions_{model}.npz"
    if p6.exists():
        n6_best, n6_best_source = int(np.load(p6)["n6_best"]), str(p6)
    else:
        n6_best, n6_best_source = None, "MISSING"
    return l_star, l_star_source, n6_best, n6_best_source


def kind_of_id(item_id: str) -> str | None:
    if item_id.startswith("harm_"):
        return "harm"
    if item_id.startswith("hb_"):
        return "hb"
    return None


# ================================================================================================
# judged generation grid: gen{P,Dprime,E}_{band} -- the GPU-addendum 6x3 judged behavioural grid
# ================================================================================================
GEN_JUDGED_COLS = ("refused", "refused_raw", "harmful_compliance", "safe_engagement", "over_refusal", "judged",
                    "proxy_refused", "RD", "G1", "T1ref")
SITES_JUDGED = ("P", "Dprime", "E")
JUDGED_OUTCOME_COLS = {
    "refused_harm": ("refused", "harm"), "harmful_compliance_harm": ("harmful_compliance", "harm"),
    "safe_engagement_harm": ("safe_engagement", "harm"), "over_refusal_hb": ("over_refusal", "hb"),
    "proxy_refused_harm": ("proxy_refused", "harm"), "proxy_refused_hb": ("proxy_refused", "hb"),
    "RD_harm": ("RD", "harm"), "RD_hb": ("RD", "hb"), "T1ref_harm": ("T1ref", "harm"),
}
PRIMARY_JUDGED_OUTCOMES = ("refused_harm", "harmful_compliance_harm", "over_refusal_hb")
JUDGED_ARMS = ("F", "N6", "N6perp", "POS")
UNJUDGE_GATED_COLS = ("proxy_refused", "RD", "G1", "T1ref")  # not judge-status gated (never PROXY-pooled)


def load_gen_records_named(model: str, cell_name: str) -> dict | None:
    c = load_cell(model, cell_name)
    if c is None:
        return None
    arrays = {k: c["arrays"][k] for k in GEN_JUDGED_COLS if k in c["arrays"]}
    rows, kinds = c["meta"]["rows"], c["meta"]["kinds"]
    recs = []
    for i, (row, kind) in enumerate(zip(rows, kinds)):
        rec = dict(row, kind=kind)
        for k, arr in arrays.items():
            rec[k] = arr[i]
        recs.append(rec)
    return {"recs": recs, "meta": c["meta"]}


def load_gen_records(model: str, site: str, band: str) -> dict | None:
    return load_gen_records_named(model, f"gen{site}_{band}")


def analyze_judged_grid(model: str, items: dict, canon_ids: list[str], mask_h: np.ndarray, mask_b: np.ndarray,
                        bands: list[str], gen_cache: dict) -> tuple[dict, dict]:
    """{outcome: {arm: {"cells": {"site_band": causal_cell(...)}, "family_size_used": n}}}; Holm is applied
    ONCE per (outcome, arm) over every site x band cell in that family (up to 6 bands x 3 sites = 18)."""
    ids_by_kind = {"harm": [i for i, m in zip(canon_ids, mask_h) if m],
                   "hb": [i for i, m in zip(canon_ids, mask_b) if m]}
    grid: dict = {}
    diD_raw: dict = {}
    for outcome, (col, kind) in JUDGED_OUTCOME_COLS.items():
        ids = ids_by_kind[kind]
        grid[outcome] = {}
        for arm in JUDGED_ARMS:
            cells: dict = {}
            for site in SITES_JUDGED:
                if arm in ("N6perp", "POS") and site != "P":
                    continue
                for band in bands:
                    if arm == "POS" and band not in ("B3", "B4"):
                        continue
                    key = f"{site}_{band}"
                    gc = gen_cache.get((model, site, band))
                    if gc is None:
                        cells[key] = {"status": "NOT_RUN", "reason": f"gen{site}_{band} cell missing"}
                        continue
                    recs = gc["recs"]

                    def col_of(a, dr=0, _recs=recs, _band=band, _kind=kind, _col=col):
                        gated = _col not in UNJUDGE_GATED_COLS
                        by = {}
                        for r in _recs:
                            if r["arm"] != a or r["kind"] != _kind or r.get("draw", 0) != dr:
                                continue
                            if r.get("band") != (_band if a != "0" else None):
                                continue
                            if gated and r.get("judged", 0) != 1.0:
                                continue
                            v = r.get(_col)
                            if v is not None and np.isfinite(v):
                                by[r["item_id"]] = float(v)
                        return by

                    y0_by, ya_by = col_of("0"), col_of(arm)
                    if site == "P":
                        R_tag = {"F": "RF", "N6": "RN6", "N6perp": "RF", "POS": "RF"}[arm]
                    else:
                        R_tag = {"F": "RFo", "N6": "RN6o"}[arm]
                    draws = sorted({r["draw"] for r in recs if r["arm"] == R_tag and r["kind"] == kind
                                    and r.get("band") == band})
                    y0 = np.array([y0_by.get(i, np.nan) for i in ids])
                    ya = np.array([ya_by.get(i, np.nan) for i in ids])
                    R_stack = (np.array([[col_of(R_tag, dr=j).get(i, np.nan) for i in ids] for j in draws])
                              if draws else np.zeros((0, len(ids))))
                    cell = causal_cell(ya, y0, R_stack, seed=SEED)
                    cells[key] = cell
                    if arm in ("F", "N6") and cell["status"] == "OK" and R_stack.size:
                        rmean = np.nanmean(R_stack, axis=0)
                        diff = ya - rmean
                        diD_raw.setdefault(key, {})[f"{arm}_minus_R_{outcome}"] = \
                            {i: float(v) for i, v in zip(ids, diff) if np.isfinite(v)}
            family_size = sum(1 for c in cells.values() if c.get("status") == "OK")
            apply_holm_and_causal(cells)
            grid[outcome][arm] = {"cells": cells, "family_size_used": family_size,
                                  "family_definition": "6 bands x 3 sites = 18 (fewer for N6perp/POS, "
                                                       "which are site-P only), NOT_RUN cells excluded"}
    return grid, diD_raw


# ================================================================================================
# genU_{band} (plan optional 9b, EXPLORATORY -- not in any Holm family, no CAUSAL determination):
# site P, arms 0 / F / FperpU / RUo(1,2), RUo = own-coefficient random control x-(x.FperpU)u.
# Does the refusal effect of F survive removing F's component along the N2/N3 (FperpU) axis?
# ================================================================================================
GENU_OUTCOMES = ("refused_harm", "harmful_compliance_harm", "over_refusal_hb", "RD_harm")


def analyze_genU(model: str, canon_ids: list[str], mask_h: np.ndarray, mask_b: np.ndarray,
                 bands: list[str]) -> dict:
    ids_by_kind = {"harm": [i for i, m in zip(canon_ids, mask_h) if m],
                   "hb": [i for i, m in zip(canon_ids, mask_b) if m]}
    out: dict = {}
    for band in bands:
        gc = load_gen_records_named(model, f"genU_{band}")
        if gc is None:
            out[band] = {"status": "NOT_RUN", "reason": f"genU_{band} cell missing"}
            continue
        recs = gc["recs"]
        band_out = {}
        for outcome in GENU_OUTCOMES:
            col, kind = JUDGED_OUTCOME_COLS[outcome]
            ids = ids_by_kind[kind]

            def col_of(a, dr=0, _recs=recs, _band=band, _kind=kind, _col=col):
                gated = _col not in UNJUDGE_GATED_COLS
                by = {}
                for r in _recs:
                    if r["arm"] != a or r["kind"] != _kind or r.get("draw", 0) != dr:
                        continue
                    if r.get("band") != (_band if a != "0" else None):
                        continue
                    if gated and r.get("judged", 0) != 1.0:
                        continue
                    v = r.get(_col)
                    if v is not None and np.isfinite(v):
                        by[r["item_id"]] = float(v)
                return by

            y0_by, yF_by, yU_by = col_of("0"), col_of("F"), col_of("FperpU")
            draws = sorted({r["draw"] for r in recs if r["arm"] == "RUo" and r["kind"] == kind
                            and r.get("band") == band})
            y0 = np.array([y0_by.get(i, np.nan) for i in ids])
            yF = np.array([yF_by.get(i, np.nan) for i in ids])
            yU = np.array([yU_by.get(i, np.nan) for i in ids])
            R_stack = (np.array([[col_of("RUo", dr=j).get(i, np.nan) for i in ids] for j in draws])
                      if draws else np.zeros((0, len(ids))))
            cell_F = causal_cell(yF, y0, R_stack, seed=SEED)
            cell_U = causal_cell(yU, y0, R_stack, seed=SEED)
            mask = np.isfinite(yF) & np.isfinite(yU)
            diff = yU[mask] - yF[mask]
            if diff.size:
                m_ = float(diff.mean())
                lo, hi = S.bootstrap_ci_at(diff, 0.05, B=B_BOOT, seed=SEED)
                contrast = {"status": "OK", "delta_FperpU_minus_F": m_, "ci_lo": lo, "ci_hi": hi, "n": int(diff.size)}
            else:
                contrast = {"status": "NOT_RUN", "reason": "no overlapping finite F/FperpU items"}
            band_out[outcome] = {"F_vs_0_and_R": cell_F, "FperpU_vs_0_and_R": cell_U,
                                 "FperpU_minus_F_paired_same_pass": contrast}
        out[band] = band_out
    return {"status": "OK" if any(v.get("status") != "NOT_RUN" for v in out.values()) else "NOT_RUN",
            "per_band": out, "R_control": "RUo = x - (x.FperpU)u, own-coefficient",
            "note": "EXPLORATORY (plan 9b): not in any Holm family, no CAUSAL flag; tests whether F's "
                    "refusal effect survives removing its component along the top-8 refusal-token "
                    "unembedding rows (the N2/N3 axis)"}


# ================================================================================================
# genG_{B1..B6,ALL} (T3 disambiguation positive control, EXPLORATORY -- not in any Holm family):
# site "ALLPOS" projects F/N6 out at EVERY prompt position and every decode call within the band's
# layers (or all layers for "ALL") -- an inference-time ablation, not a single-site edit. Distinguishes
# "the direction is causal only when removed everywhere" from "hook or direction problem".
# ================================================================================================
def analyze_genG(model: str, canon_ids: list[str], mask_h: np.ndarray, mask_b: np.ndarray,
                 judged_grid: dict) -> tuple[dict, dict]:
    ids_by_kind = {"harm": [i for i, m in zip(canon_ids, mask_h) if m],
                   "hb": [i for i, m in zip(canon_ids, mask_b) if m]}
    band_keys = list(bands_of(model).keys()) + ["ALL"]
    out: dict = {}
    diD_raw: dict = {}   # band_key -> "{arm}_minus_R_{outcome}" -> {item_id: diff}, for cross-model DiD
    for band_key in band_keys:
        gc = load_gen_records_named(model, f"genG_{band_key}")
        if gc is None:
            out[band_key] = {"status": "NOT_RUN", "reason": f"genG_{band_key} cell missing"}
            continue
        recs = gc["recs"]
        band_out = {}
        for outcome in GENU_OUTCOMES:
            col, kind = JUDGED_OUTCOME_COLS[outcome]
            ids = ids_by_kind[kind]

            def col_of(a, dr=0, _recs=recs, _band=band_key, _kind=kind, _col=col):
                gated = _col not in UNJUDGE_GATED_COLS
                by = {}
                for r in _recs:
                    if r["arm"] != a or r["kind"] != _kind or r.get("draw", 0) != dr:
                        continue
                    if r.get("band") != (_band if a != "0" else None):
                        continue
                    if gated and r.get("judged", 0) != 1.0:
                        continue
                    v = r.get(_col)
                    if v is not None and np.isfinite(v):
                        by[r["item_id"]] = float(v)
                return by

            y0 = np.array([col_of("0").get(i, np.nan) for i in ids])
            yF = np.array([col_of("F").get(i, np.nan) for i in ids])
            yN6 = np.array([col_of("N6").get(i, np.nan) for i in ids])
            RFo_stack = np.array([col_of("RFo", dr=1).get(i, np.nan) for i in ids])[None, :]
            RN6o_stack = np.array([col_of("RN6o", dr=1).get(i, np.nan) for i in ids])[None, :]
            cell_F = causal_cell(yF, y0, RFo_stack, seed=SEED)
            cell_N6 = causal_cell(yN6, y0, RN6o_stack, seed=SEED)
            if outcome in ("refused_harm", "over_refusal_hb") and RFo_stack.size:
                rmeanF = np.nanmean(RFo_stack, axis=0)
                diffF = yF - rmeanF
                diD_raw.setdefault(band_key, {})[f"F_minus_R_{outcome}"] = \
                    {i: float(v) for i, v in zip(ids, diffF) if np.isfinite(v)}
            if outcome == "over_refusal_hb" and RN6o_stack.size:
                rmeanN6 = np.nanmean(RN6o_stack, axis=0)
                diffN6 = yN6 - rmeanN6
                diD_raw.setdefault(band_key, {})[f"N6_minus_R_{outcome}"] = \
                    {i: float(v) for i, v in zip(ids, diffN6) if np.isfinite(v)}
            site_p_cell = (judged_grid.get(outcome, {}).get("F", {}).get("cells", {}).get(f"P_{band_key}")
                          if band_key != "ALL" else None)
            band_out[outcome] = {
                "F_global_ablation": cell_F, "N6_global_ablation": cell_N6,
                "F_site_P_for_comparison": site_p_cell or {
                    "status": "NOT_RUN", "reason": "ALL has no site-P analogue" if band_key == "ALL"
                    else "missing from causal_grid_judged"}}
        out[band_key] = band_out
    result = {"status": "OK" if any(isinstance(v, dict) and v.get("status") != "NOT_RUN" for v in out.values())
             else "NOT_RUN", "per_band": out,
              "note": "EXPLORATORY T3 disambiguation positive control: site=ALLPOS projects F/N6 out at every "
                      "prompt position and decode call within the band's layers (B1-B6) or all layers (ALL) -- "
                      "inference-time ablation, not a single-site edit. Not in any Holm family, no CAUSAL "
                      "determination. F_site_P_for_comparison is the matching site-P judged cell (arm F vs RF) "
                      "from causal_grid_judged, for local-vs-global comparison. RFo/RN6o are own-coefficient "
                      "random controls, a single draw (draw 1) each."}
    return result, diD_raw


# ================================================================================================
# arm0_stability: arm-0 refused_harm / over_refusal_hb rates for every judged cell family (each cell
# co-batches its own arm-0 rows -> GPU batch-shape numerics can move greedy arm-0 outputs slightly
# across passes). Every causal contrast is WITHIN-cell (its own co-batched arm 0 + matched R), never
# against a pooled/cross-cell arm-0 baseline; this section documents how much arm-0 itself moves.
# ================================================================================================
def analyze_arm0_stability(model: str, bands: list[str]) -> dict:
    cell_names = ([f"genP_{b}" for b in bands] + [f"genDprime_{b}" for b in bands] +
                 [f"genE_{b}" for b in bands] + [f"genG_{b}" for b in bands] + ["genG_ALL"] +
                 [f"genU_{b}" for b in bands] + ["gen_P"])
    per_cell: dict = {}
    item_refused: dict = {}     # item_id -> {cell_name: 0/1 label}
    item_over_refusal: dict = {}
    for name in cell_names:
        gc = load_gen_records_named(model, name)
        if gc is None:
            per_cell[name] = {"status": "NOT_RUN", "reason": f"{name} cell missing"}
            continue
        arm0 = [r for r in gc["recs"] if r["arm"] == "0"]

        def wilson(col, kind, _arm0=arm0):
            vals = [(r["item_id"], r[col]) for r in _arm0 if r["kind"] == kind and r.get("judged", 0) == 1.0
                   and r.get(col) is not None and np.isfinite(r[col])]
            n, k = len(vals), int(sum(v for _, v in vals))
            lo, hi = S.rate_ci(k, n) if n else (float("nan"), float("nan"))
            return {"k": k, "n": n, "rate": (k / n if n else None), "ci_lo": lo, "ci_hi": hi}, vals

        refh, refh_vals = wilson("refused", "harm")
        orr, orr_vals = wilson("over_refusal", "hb")
        per_cell[name] = {"status": "OK", "refused_harm": refh, "over_refusal_hb": orr}
        for iid, v in refh_vals:
            item_refused.setdefault(iid, {})[name] = v
        for iid, v in orr_vals:
            item_over_refusal.setdefault(iid, {})[name] = v
    ok_cells = {k: v for k, v in per_cell.items() if v.get("status") == "OK"}

    def summarize(key):
        rates = [v[key]["rate"] for v in ok_cells.values() if v[key]["rate"] is not None]
        return {"min": min(rates) if rates else None, "max": max(rates) if rates else None,
                "range": (max(rates) - min(rates)) if rates else None, "n_cells_with_rate": len(rates)}

    def n_unstable(item_labels):
        return sum(1 for labs in item_labels.values() if len(set(labs.values())) > 1)

    return {"status": "OK" if ok_cells else "NOT_RUN", "per_cell": per_cell,
           "refused_harm_rate_range_across_cells": summarize("refused_harm"),
           "over_refusal_hb_rate_range_across_cells": summarize("over_refusal_hb"),
           "n_items_refused_harm_label_unstable_across_cells": n_unstable(item_refused),
           "n_items_over_refusal_hb_label_unstable_across_cells": n_unstable(item_over_refusal),
            "note": "arm-0 greedy outputs can differ slightly across pass structures (GPU batch-shape "
                    "numerics); every causal contrast elsewhere in this analysis is computed WITHIN a cell "
                    "against that cell's own co-batched arm-0 and matched R, never a pooled/cross-cell "
                    "arm-0 baseline"}


# ================================================================================================
# e2x2_E (plan section 6): site-E readout at the unedited LATE window (tokens 40-55) after an EARLY
# (tokens 5-20) edit; N1-analogue at l_star (F-projection) and N6-analogue at n6_best (N6-projection),
# hazardous-vs-benign continuation Cohen's d, bootstrap CI resampling item_uid clusters.
# ================================================================================================
def cluster_delta_d_boot(haz_arm: np.ndarray, ben_arm: np.ndarray, haz_0: np.ndarray, ben_0: np.ndarray,
                         B: int = 500, seed: int = SEED) -> dict:
    """haz_*/ben_* : [U, F] (U item_uid clusters x F prefix families), NaN for missing combos.
    Delta_d = d(hazardous,benign | arm) - d(hazardous,benign | 0); percentile bootstrap resampling
    item_uid rows (both prefix families of a resampled item_uid move together), same draw for arm and 0."""
    U = haz_arm.shape[0]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, U, size=(B, U))

    def dvec(haz, ben):
        H, Bn = haz[idx].reshape(B, -1), ben[idx].reshape(B, -1)
        with np.errstate(invalid="ignore"), warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            meanH, meanB = np.nanmean(H, axis=1), np.nanmean(Bn, axis=1)
            varH, varB = np.nanvar(H, axis=1, ddof=1), np.nanvar(Bn, axis=1, ddof=1)
        nH, nB = np.isfinite(H).sum(1), np.isfinite(Bn).sum(1)
        pooled = np.sqrt(((nH - 1) * varH + (nB - 1) * varB) / np.maximum(nH + nB - 2, 1))
        with np.errstate(invalid="ignore", divide="ignore"):
            return (meanH - meanB) / pooled

    dA, d0 = dvec(haz_arm, ben_arm), dvec(haz_0, ben_0)
    boots = dA - d0
    boots = boots[np.isfinite(boots)]
    point_dA = cohens_d_arr(haz_arm[np.isfinite(haz_arm)], ben_arm[np.isfinite(ben_arm)])
    point_d0 = cohens_d_arr(haz_0[np.isfinite(haz_0)], ben_0[np.isfinite(ben_0)])
    point = point_dA - point_d0
    if boots.size == 0:
        return {"delta": point, "ci_lo": float("nan"), "ci_hi": float("nan"), "d_arm": point_dA, "d_0": point_d0,
                "n_item_uid": U}
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"delta": float(point), "ci_lo": float(lo), "ci_hi": float(hi), "d_arm": float(point_dA),
            "d_0": float(point_d0), "n_item_uid": U}


E2X2_ARMS = {"F": ("F", 0), "RF1": ("RF", 1), "RF2": ("RF", 2), "N6": ("N6", 0), "RN6-1": ("RN6", 1)}


def analyze_e2x2E(model: str, l_star: int | None, n6_best: int | None, bands: list[str]) -> dict:
    c = load_cell(model, "e2x2_E")
    if c is None:
        return {"status": "NOT_RUN", "reason": "e2x2_E cell missing"}
    rows = c["meta"]["rows"]
    proj_late = c["arrays"]["proj_late"].astype(float)   # [R, L, 3]
    L_actual = proj_late.shape[1]
    uids = sorted({r["item_uid"] for r in rows})
    fams = sorted({r["prefix_family"] for r in rows})
    U, Fn = len(uids), len(fams)
    uid_idx = {u: i for i, u in enumerate(uids)}
    fam_idx = {f: i for i, f in enumerate(fams)}

    def build(layer, col, arm, band, draw):
        vals = proj_late[:, layer, col]
        haz, ben = np.full((U, Fn), np.nan), np.full((U, Fn), np.nan)
        for i, r in enumerate(rows):
            if r["arm"] != arm or r.get("band") != band or r.get("draw", 0) != draw:
                continue
            ui, fi = uid_idx[r["item_uid"]], fam_idx[r["prefix_family"]]
            (haz if r["prefix_level"] == "hazardous" else ben)[ui, fi] = vals[i]
        return haz, ben

    def combo_ci(hazF, benF, hazR1, benR1, hazR2, benR2, B=500, seed=SEED):
        """CI of Delta_d(F) - mean(Delta_d(RF1),Delta_d(RF2)); the shared d(0) term cancels exactly, so
        this equals d(F) - mean(d(RF1),d(RF2)). Same resample idx (same seed, same U) as cluster_delta_d_boot."""
        U_ = hazF.shape[0]
        rng = np.random.default_rng(seed)
        idx = rng.integers(0, U_, size=(B, U_))

        def dvec(haz, ben):
            H, Bn = haz[idx].reshape(B, -1), ben[idx].reshape(B, -1)
            with np.errstate(invalid="ignore"), warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=RuntimeWarning)
                meanH, meanB = np.nanmean(H, axis=1), np.nanmean(Bn, axis=1)
                varH, varB = np.nanvar(H, axis=1, ddof=1), np.nanvar(Bn, axis=1, ddof=1)
            nH, nB = np.isfinite(H).sum(1), np.isfinite(Bn).sum(1)
            pooled = np.sqrt(((nH - 1) * varH + (nB - 1) * varB) / np.maximum(nH + nB - 2, 1))
            with np.errstate(invalid="ignore", divide="ignore"):
                return (meanH - meanB) / pooled

        dF, dR1, dR2 = dvec(hazF, benF), dvec(hazR1, benR1), dvec(hazR2, benR2)
        combo = dF - (dR1 + dR2) / 2.0
        combo = combo[np.isfinite(combo)]
        point = (cohens_d_arr(hazF[np.isfinite(hazF)], benF[np.isfinite(benF)]) -
                0.5 * (cohens_d_arr(hazR1[np.isfinite(hazR1)], benR1[np.isfinite(benR1)]) +
                       cohens_d_arr(hazR2[np.isfinite(hazR2)], benR2[np.isfinite(benR2)])))
        if combo.size == 0:
            return {"value": point, "ci_lo": float("nan"), "ci_hi": float("nan")}
        lo, hi = np.percentile(combo, [2.5, 97.5])
        return {"value": float(point), "ci_lo": float(lo), "ci_hi": float(hi)}

    def readout_for(layer, col):
        if layer is None or layer >= L_actual:
            return {"status": "NOT_RUN", "reason": "layer unavailable / out of range for this cell"}
        haz0, ben0 = build(layer, col, "0", None, 0)
        if np.isfinite(haz0).sum() == 0:
            return {"status": "NOT_RUN", "reason": "no arm-0 rows"}
        per_band = {}
        for band in bands:
            band_out = {}
            haz_ben = {}
            for tag, (a_, dr_) in E2X2_ARMS.items():
                hazA, benA = build(layer, col, a_, band, dr_)
                haz_ben[tag] = (hazA, benA)
                if np.isfinite(hazA).sum() == 0:
                    band_out[tag] = {"status": "NOT_RUN", "reason": f"{a_} draw {dr_} not present at {band}"}
                    continue
                band_out[tag] = {"status": "OK", **cluster_delta_d_boot(hazA, benA, haz0, ben0, seed=SEED)}
            dF, dRF1, dRF2 = band_out.get("F", {}), band_out.get("RF1", {}), band_out.get("RF2", {})
            if dF.get("status") == "OK" and dRF1.get("status") == "OK" and dRF2.get("status") == "OK":
                hazF, benF = haz_ben["F"]
                hazR1, benR1 = haz_ben["RF1"]
                hazR2, benR2 = haz_ben["RF2"]
                band_out["F_minus_meanRF"] = {"status": "OK", **combo_ci(hazF, benF, hazR1, benR1, hazR2, benR2)}
            else:
                band_out["F_minus_meanRF"] = {"status": "NOT_RUN"}
            dN6, dRN6 = band_out.get("N6", {}), band_out.get("RN6-1", {})
            band_out["N6_minus_RN6"] = ({"status": "OK", "value": dN6["delta"] - dRN6["delta"]}
                                        if dN6.get("status") == "OK" and dRN6.get("status") == "OK"
                                        else {"status": "NOT_RUN"})
            per_band[band] = band_out
        return {"status": "OK", "layer": layer, "per_band": per_band}

    out_F = readout_for(l_star, 0)
    out_N6 = readout_for(n6_best, 1)
    return {"status": "OK", "n_item_uid": U, "n_families": Fn, "l_star": l_star, "n6_best": n6_best,
            "N1_analogue_F_at_lstar": out_F, "N6_analogue_at_n6best": out_N6,
            "note": "d = Cohen's d(hazardous, benign) of proj_late (LATE window, tokens 40-55, unedited "
                    "continuation) after an EARLY-window (tokens 5-20) edit; Delta_d(arm)=d(arm)-d(0); "
                    "bootstrap resamples item_uid clusters (both prefix families of a resampled item_uid "
                    "move together, same resample used for arm and for 0)"}


# ================================================================================================
# decodability
# ================================================================================================
def analyze_decodability(model: str, items: dict, L: int) -> dict:
    c = load_cell(model, "decod_arm0")
    if c is None:
        return {"status": "NOT_RUN", "reason": "decod_arm0 cell missing"}
    proj = c["arrays"]["proj"].astype(float)   # [n, L_actual, 3]
    y = c["arrays"]["y"].astype(int)           # 1 = dharm, 0 = dhb
    n, L_actual, _ = proj.shape
    if L_actual != L:
        L = L_actual  # trust the data over the nominal layer count

    def zscore_cols(x):
        mu = np.nanmean(x, axis=0, keepdims=True)
        sd = np.nanstd(x, axis=0, ddof=1, keepdims=True)
        sd = np.where(sd < 1e-12, np.nan, sd)
        return (x - mu) / sd

    zF = zscore_cols(proj[:, :, 0])     # [n, L] z-scored per layer across the 64 items
    zN6 = zscore_cols(proj[:, :, 1])
    zFU = zscore_cols(proj[:, :, 2])

    per_layer_auroc = {
        "F": [S.auroc(zF[:, l], y) for l in range(L)],
        "N6_hb_positive": [S.auroc(zN6[:, l], 1 - y) for l in range(L)],
        "FperpU": [S.auroc(zFU[:, l], y) for l in range(L)],
    }
    by_band = {}
    for band, layers in bands_of(model).items():
        layers = [l for l in layers if l < L]
        if not layers:
            by_band[band] = {"status": "NOT_RUN", "reason": "band outside decod proj layer range"}
            continue
        score = np.nanmean(zF[:, layers], axis=1)
        auc = S.auroc_ci(score, y, B=B_BOOT, seed=SEED)
        by_band[band] = {"status": "OK", "auroc": auc, "layers": layers,
                          "DECODABLE": bool(auc["ci_lo"] > 0.60)}
    return {"status": "OK", "n_items": n, "n_pos": int(y.sum()), "n_neg": int((1 - y).sum()),
            "L_used": L, "per_layer_auroc": per_layer_auroc, "by_band": by_band,
            "note": "F/FperpU AUROC uses label 1=dharm; N6 (safe-pointing direction) reported "
                    "as N6_hb_positive with label 1=dhb so all three curves read >0.5 when the "
                    "direction actually separates the classes it is meant to separate."}


def analyze_decodability_full(model: str, items: dict, L: int) -> dict:
    """Decodability per site: P from decod_arm0 (primary, 64 held-out items); D'/E from decodgen_arm0's
    per-call-window projections (arm-0 greedy on the same 64 items). Site D' reports window P AND window D
    (the DECODABLE flag for D' uses window D, per spec); site E uses window E."""
    site_p = analyze_decodability(model, items, L)
    out = {"P": site_p}
    dg = load_cell(model, "decodgen_arm0")
    if dg is None:
        out["Dprime"] = {"status": "NOT_RUN", "reason": "decodgen_arm0 cell missing"}
        out["E"] = {"status": "NOT_RUN", "reason": "decodgen_arm0 cell missing"}
        return out
    proj_win = dg["arrays"]["proj_win"].astype(float)   # [n, 4, L_actual, 3]
    y = dg["arrays"]["y"].astype(int)
    n, _, L_actual, _ = proj_win.shape
    Luse = min(L, L_actual)
    windows_meta = dg["meta"].get("windows", {"P": [0, 0], "D": [1, 8], "E": [5, 20], "LATE": [21, 40]})
    widx = {k: i for i, k in enumerate(windows_meta.keys())}

    def zscore_cols(x):
        mu = np.nanmean(x, axis=0, keepdims=True)
        sd = np.nanstd(x, axis=0, ddof=1, keepdims=True)
        sd = np.where(sd < 1e-12, np.nan, sd)
        return (x - mu) / sd

    def by_window(win_key):
        wi = widx.get(win_key)
        if wi is None or wi >= proj_win.shape[1]:
            return {"status": "NOT_RUN", "reason": f"window {win_key!r} not present"}
        zF = zscore_cols(proj_win[:, wi, :Luse, 0])
        bb = {}
        for band, layers in bands_of(model).items():
            layers = [l for l in layers if l < Luse]
            if not layers:
                bb[band] = {"status": "NOT_RUN", "reason": "band outside decodgen layer range"}
                continue
            score = np.nanmean(zF[:, layers], axis=1)
            auc = S.auroc_ci(score, y, B=B_BOOT, seed=SEED)
            bb[band] = {"status": "OK", "auroc": auc, "layers": layers, "DECODABLE": bool(auc["ci_lo"] > 0.60)}
        return {"status": "OK", "n_items": n, "window": win_key, "by_band": bb}

    win_p, win_d, win_e = by_window("P"), by_window("D"), by_window("E")
    dprime_by_band = (win_d["by_band"] if win_d.get("status") == "OK" else {})
    out["Dprime"] = {"status": win_d.get("status", "NOT_RUN"), "window_P_decodgen": win_p, "window_D": win_d,
                     "by_band": dprime_by_band, "note": "DECODABLE flag for site D' uses window D"}
    out["E"] = win_e
    return out


def two_by_two_from_judged(decod_full: dict, judged_grid: dict) -> dict:
    """2x2 {DECODABLE, not} x {CAUSAL, not} per (site, band) cell: arm F on refused_harm, arm N6 on
    over_refusal_hb. Basu 2603.18353's zero-effect precedent is its SAE arm ONLY (Arm 1 corrected 17/85,
    disrupted 25/47); a decodable-but-inert count here is never read as "mechanistic methods never work"."""
    out = {}
    for label, outcome, arm in (("F_on_refused_harm", "refused_harm", "F"),
                                ("N6_on_over_refusal_hb", "over_refusal_hb", "N6")):
        rows = []
        cells = judged_grid.get(outcome, {}).get(arm, {}).get("cells", {})
        for key, cell in sorted(cells.items()):
            site, band = key.split("_", 1)
            dec_block = decod_full.get(site, {})
            dec_by_band = dec_block.get("by_band", {}) if site != "P" else dec_block.get("by_band", {})
            dec = dec_by_band.get(band, {}).get("DECODABLE")
            causal = cell.get("CAUSAL") if cell.get("status") == "OK" else None
            rows.append({"cell": key, "site": site, "band": band, "DECODABLE": dec, "CAUSAL": causal})
        n_inert = sum(1 for r in rows if r["DECODABLE"] is True and r["CAUSAL"] is False)
        n_dec = sum(1 for r in rows if r["DECODABLE"] is True)
        out[label] = {"rows": rows, "decodable_but_inert_count": n_inert, "decodable_count": n_dec,
                     "note": "Basu-style zero-effect precedent applies to its SAE arm only, not to causal "
                             "intervention methods generally"}
    return out


# ================================================================================================
# readouts under intervention
# ================================================================================================
def analyze_readouts(model: str, band_data: dict, y0: dict, proj0: np.ndarray, canon_ids: list[str],
                     mask_h: np.ndarray, mask_b: np.ndarray, items: dict) -> dict:
    L = proj0.shape[1]
    # l_star, n6_best from disk (never from a live model)
    l_star = None
    n6_dir_status = "NOT_RUN"
    n6_best = None
    if model == "smoke":
        l_star = int(28 * 0.7)  # Ctx._refit_smoke formula, documented in method.py
        l_star_source = "smoke formula int(L*0.7), no directions_disk_smoke.npz on disk"
    else:
        p = PRIVATE / f"directions_disk_{model}.npz"
        if p.exists():
            dd = np.load(p)
            l_star = int(dd["l_star"])
            l_star_source = str(p)
        else:
            l_star_source = "MISSING"
    p6 = PRIVATE / f"directions_{model}.npz"
    if p6.exists():
        dd6 = np.load(p6)
        n6_best = int(dd6["n6_best"])
        n6_dir_status = "OK"
    band_lstar = band_containing(model, l_star) if l_star is not None else None
    band_n6best = band_containing(model, n6_best) if n6_best is not None else None

    harm_idx = np.where(mask_h)[0]
    hb_idx = np.where(mask_b)[0]

    def g1_of(bd, arm):
        if arm == "0":
            return y0["G1"]
        if arm in ("F", "N6", "N6perp", "POS"):
            return bd[arm]["G1"] if bd[arm] else None
        return None

    def proj_of(bd, arm):
        if arm == "0":
            return proj0
        if arm in ("F", "N6", "N6perp", "POS"):
            return bd[arm]["proj"] if bd[arm] else None
        return None

    per_band = {}
    for band, bd in band_data.items():
        entry = {"BL1_eval": {}, "BL1_harm_only": {}, "N1_eval": {}, "N2_eval": {}, "N6_eval": {}, "N7_eval": {}}
        arms_here = ["0", "F", "N6", "N6perp", "POS"]
        for arm in arms_here:
            g1 = g1_of(bd, arm)
            proj = proj_of(bd, arm)
            if g1 is None or np.isfinite(g1).sum() == 0:
                entry["BL1_eval"][arm] = None
                entry["BL1_harm_only"][arm] = None
            else:
                mh, mb = np.nanmean(g1[mask_h]), np.nanmean(g1[mask_b])
                entry["BL1_eval"][arm] = float(mh - mb)
                entry["BL1_harm_only"][arm] = float(mh)
            if proj is None or l_star is None or l_star >= proj.shape[1]:
                entry["N1_eval"][arm] = None
                entry["N2_eval"][arm] = None
            else:
                a, b = proj[harm_idx, l_star, 0], proj[hb_idx, l_star, 0]
                entry["N1_eval"][arm] = float(S.cohens_d(a, b)) if np.isfinite(a).sum() and np.isfinite(b).sum() \
                    else None
                a2, b2 = proj[harm_idx, l_star, 2], proj[hb_idx, l_star, 2]
                entry["N2_eval"][arm] = float(S.cohens_d(a2, b2)) if np.isfinite(a2).sum() and np.isfinite(b2).sum() \
                    else None
            if proj is None or n6_best is None or n6_best >= proj.shape[1]:
                entry["N6_eval"][arm] = None
            else:
                ah, ab = proj[hb_idx, n6_best, 1], proj[harm_idx, n6_best, 1]
                entry["N6_eval"][arm] = float(S.cohens_d(ah, ab)) if np.isfinite(ah).sum() and np.isfinite(ab).sum() \
                    else None
            if proj is not None and l_star is not None and n6_best is not None and \
                    l_star < proj.shape[1] and n6_best < proj.shape[1]:
                labels_harm1 = mask_h.astype(int)
                labels_hb1 = mask_b.astype(int)
                x1 = proj[:, l_star, 0]
                x6 = proj[:, n6_best, 1]
                if np.isfinite(x1).sum() > 4 and np.isfinite(x6).sum() > 4:
                    z1 = S.d_z(x1, labels_harm1, seed=SEED)["z"]
                    z6 = S.d_z(x6, labels_hb1, seed=SEED)["z"]
                    entry["N7_eval"][arm] = float(z1 - z6) if np.isfinite(z1) and np.isfinite(z6) else None
                else:
                    entry["N7_eval"][arm] = None
            else:
                entry["N7_eval"][arm] = None
        entry["MECHANICALLY_FORCED_N1_F"] = bool(band == band_lstar)
        entry["MECHANICALLY_FORCED_N6_N6"] = bool(band == band_n6best)

        # Delta_readout(arm) = readout(arm) - readout(0), with bootstrap CI, for F and N6
        deltas = {}
        g1_0 = y0["G1"]
        proj_0 = proj0
        for arm in ("F", "N6", "N6perp", "POS"):
            g1a = g1_of(bd, arm)
            proja = proj_of(bd, arm)
            d = {}
            if g1a is not None:
                d["BL1_eval"] = bootstrap_meandiff_delta(g1a[mask_h], g1a[mask_b], g1_0[mask_h], g1_0[mask_b])
            if proja is not None and l_star is not None and l_star < proja.shape[1]:
                d["N1_eval"] = bootstrap_cohend_delta(proja[harm_idx, l_star, 0], proja[hb_idx, l_star, 0],
                                                       proj_0[harm_idx, l_star, 0], proj_0[hb_idx, l_star, 0])
                d["N2_eval"] = bootstrap_cohend_delta(proja[harm_idx, l_star, 2], proja[hb_idx, l_star, 2],
                                                       proj_0[harm_idx, l_star, 2], proj_0[hb_idx, l_star, 2])
            if proja is not None and n6_best is not None and n6_best < proja.shape[1]:
                d["N6_eval"] = bootstrap_cohend_delta(proja[hb_idx, n6_best, 1], proja[harm_idx, n6_best, 1],
                                                       proj_0[hb_idx, n6_best, 1], proj_0[harm_idx, n6_best, 1])
            deltas[arm] = d
        # matched-random comparison: Delta(F) vs mean_j Delta(R_F j); Delta(N6) vs mean_j Delta(R_N6 j)
        RF_G1 = stack_draws(bd, "RF", "G1", canon_ids)
        RN6_G1 = stack_draws(bd, "RN6", "G1", canon_ids)
        RF_proj = stack_draws_proj(bd, "RF", canon_ids, L)
        RN6_proj = stack_draws_proj(bd, "RN6", canon_ids, L)
        rf_mean_g1 = np.nanmean(RF_G1, axis=0) if RF_G1.size else None
        rn6_mean_g1 = np.nanmean(RN6_G1, axis=0) if RN6_G1.size else None
        rf_mean_proj = np.nanmean(RF_proj, axis=0) if RF_proj.size else None
        rn6_mean_proj = np.nanmean(RN6_proj, axis=0) if RN6_proj.size else None
        r_compare = {}
        if rf_mean_g1 is not None:
            r_compare["RF_mean_BL1_delta"] = bootstrap_meandiff_delta(
                rf_mean_g1[mask_h], rf_mean_g1[mask_b], g1_0[mask_h], g1_0[mask_b])
        if rn6_mean_g1 is not None:
            r_compare["RN6_mean_BL1_delta"] = bootstrap_meandiff_delta(
                rn6_mean_g1[mask_h], rn6_mean_g1[mask_b], g1_0[mask_h], g1_0[mask_b])
        if rf_mean_proj is not None and l_star is not None and l_star < rf_mean_proj.shape[0]:
            r_compare["RF_mean_N1_delta"] = bootstrap_cohend_delta(
                rf_mean_proj[harm_idx, l_star, 0], rf_mean_proj[hb_idx, l_star, 0],
                proj_0[harm_idx, l_star, 0], proj_0[hb_idx, l_star, 0])
        if rn6_mean_proj is not None and n6_best is not None and n6_best < rn6_mean_proj.shape[0]:
            r_compare["RN6_mean_N6_delta"] = bootstrap_cohend_delta(
                rn6_mean_proj[hb_idx, n6_best, 1], rn6_mean_proj[harm_idx, n6_best, 1],
                proj_0[hb_idx, n6_best, 1], proj_0[harm_idx, n6_best, 1])
        entry["Delta_readout"] = deltas
        entry["Delta_vs_matched_random"] = r_compare
        if "RF_mean_BL1_delta" in r_compare:
            entry["abs_BL1_move_under_RF_matched_random"] = abs(r_compare["RF_mean_BL1_delta"]["delta"]) \
                if np.isfinite(r_compare["RF_mean_BL1_delta"]["delta"]) else None
        per_band[band] = entry

    return {"l_star": l_star, "l_star_source": l_star_source, "band_containing_l_star": band_lstar,
            "n6_best": n6_best, "n6_best_source": (str(p6) if p6.exists() else "MISSING"),
            "band_containing_n6_best": band_n6best, "per_band": per_band}


# ================================================================================================
# readouts under intervention: A_prompt stimuli (stimro_P) -- BL1_easy / BL1_hard NEVER pooled
# ================================================================================================
def analyze_stim_readouts(model: str, l_star: int | None, n6_best: int | None) -> dict:
    c = load_cell(model, "stimro_P")
    if c is None:
        return {"status": "NOT_RUN", "reason": "stimro_P cell missing"}
    meta, arrs = c["meta"], c["arrays"]
    stim_ids = meta["stim_item_ids"]
    y_of = dict(zip(stim_ids, meta["stimuli_y"]))
    set_of = dict(zip(stim_ids, meta["stimuli_set_id"]))
    rows = meta["rows"]
    G1 = arrs.get("G1")
    proj = arrs.get("proj")
    recs = []
    for i, row in enumerate(rows):
        rec = dict(row)
        if G1 is not None:
            rec["G1"] = float(G1[i])
        if proj is not None:
            rec["proj"] = proj[i].astype(float)
        recs.append(rec)

    def group(arm, band, draw=0):
        return [r for r in recs if r["arm"] == arm and r.get("band") == band and r.get("draw", 0) == draw]

    arm0 = group("0", None)
    bands = list(bands_of(model).keys())
    band_lstar = band_containing(model, l_star) if l_star is not None else None
    per_band = {}
    for band in bands:
        arms_here = {"0": arm0, "F": group("F", band), "N6": group("N6", band), "RF1": group("RF", band, 1)}

        def split(recs_a, y_val, set_pred):
            return np.array([r["G1"] for r in recs_a if y_of.get(r["item_id"]) == y_val
                             and set_pred(set_of.get(r["item_id"]))], float)

        def proj_split(recs_a, y_val, layer, col, set_pred=lambda s: s != 0):
            return np.array([r["proj"][layer, col] for r in recs_a if "proj" in r
                             and y_of.get(r["item_id"]) == y_val and set_pred(set_of.get(r["item_id"]))], float)

        bl1, n1, n2, n6r, n7 = {}, {}, {}, {}, {}
        for tag, recs_a in arms_here.items():
            easy_pos, easy_neg = split(recs_a, 1, lambda s: s == 0), split(recs_a, 0, lambda s: s == 0)
            hard_pos, hard_neg = split(recs_a, 1, lambda s: s != 0), split(recs_a, 0, lambda s: s != 0)
            bl1[tag] = {"BL1_easy": float(easy_pos.mean() - easy_neg.mean()) if easy_pos.size and easy_neg.size
                        else None,
                       "BL1_hard": float(hard_pos.mean() - hard_neg.mean()) if hard_pos.size and hard_neg.size
                       else None}
            if l_star is not None:
                hp0, hn0 = proj_split(recs_a, 1, l_star, 0), proj_split(recs_a, 0, l_star, 0)
                n1[tag] = float(S.cohens_d(hp0, hn0)) if hp0.size > 1 and hn0.size > 1 else None
                hp2, hn2 = proj_split(recs_a, 1, l_star, 2), proj_split(recs_a, 0, l_star, 2)
                n2[tag] = float(S.cohens_d(hp2, hn2)) if hp2.size > 1 and hn2.size > 1 else None
            if n6_best is not None:
                hb1, hh1 = proj_split(recs_a, 0, n6_best, 1), proj_split(recs_a, 1, n6_best, 1)
                n6r[tag] = float(S.cohens_d(hb1, hh1)) if hb1.size > 1 and hh1.size > 1 else None
            if l_star is not None and n6_best is not None:
                ids_hard = [r["item_id"] for r in recs_a if "proj" in r and set_of.get(r["item_id"]) != 0]
                x1 = np.array([r["proj"][l_star, 0] for r in recs_a if "proj" in r
                              and set_of.get(r["item_id"]) != 0], float)
                x6 = np.array([r["proj"][n6_best, 1] for r in recs_a if "proj" in r
                              and set_of.get(r["item_id"]) != 0], float)
                lab = np.array([y_of.get(i) for i in ids_hard])
                if x1.size > 4 and x6.size > 4:
                    z1 = S.d_z(x1, lab, seed=SEED)["z"]
                    z6 = S.d_z(x6, 1 - lab, seed=SEED)["z"]
                    n7[tag] = float(z1 - z6) if np.isfinite(z1) and np.isfinite(z6) else None
        # Delta_BL1(F) - Delta_BL1(RF1) == BL1(F) - BL1(RF1) (the BL1(0) term cancels); |Delta_BL1(RF1)| below.
        deltas, f_minus_rf1 = {}, {}
        for tag in ("F", "N6", "RF1"):
            deltas[tag] = {}
            for cls, pred in (("easy", lambda s: s == 0), ("hard", lambda s: s != 0)):
                a_pos, a_neg = split(arms_here[tag], 1, pred), split(arms_here[tag], 0, pred)
                z_pos, z_neg = split(arm0, 1, pred), split(arm0, 0, pred)
                deltas[tag][cls] = bootstrap_meandiff_delta(a_pos, a_neg, z_pos, z_neg)
        for cls, pred in (("easy", lambda s: s == 0), ("hard", lambda s: s != 0)):
            f_minus_rf1[cls] = bootstrap_meandiff_delta(split(arms_here["F"], 1, pred), split(arms_here["F"], 0, pred),
                                                         split(arms_here["RF1"], 1, pred),
                                                         split(arms_here["RF1"], 0, pred))
        per_band[band] = {
            "BL1": bl1, "N1": n1, "N2_FperpU": n2, "N6_readout": n6r, "N7": n7, "Delta_BL1_vs_arm0": deltas,
            "Delta_BL1_F_minus_RF1": f_minus_rf1,
            "abs_Delta_BL1_RF1": {cls: (abs(deltas["RF1"][cls]["delta"])
                                        if np.isfinite(deltas["RF1"][cls]["delta"]) else None)
                                  for cls in ("easy", "hard")},
            "MECHANICALLY_FORCED_N1_F": bool(band_lstar == band),
        }
    return {"status": "OK", "l_star": l_star, "n6_best": n6_best, "band_containing_l_star": band_lstar,
            "per_band": per_band, "note": "BL1_easy (stimuli set_id==0) and BL1_hard (set_id!=0) NEVER pooled; "
                                          "Delta_BL1(arm)=BL1(arm)-BL1(0); Delta_BL1(F)-Delta_BL1(RF1) reduces "
                                          "to BL1(F)-BL1(RF1) since the BL1(0) term cancels."}


# ================================================================================================
# decode-window F-projection readout under intervention (gen cells' proj_win, windows D and E)
# ================================================================================================
def analyze_decode_window_readout(model: str, l_star: int | None, bands: list[str], gen_cache: dict) -> dict:
    """d(harm vs hb) of the F-projection at l_star, in the window matching each decode site's own edit
    (window D for site Dprime, window E for site E) -- does the decode-site readout move under F vs RFo?"""
    out: dict = {}
    if l_star is None:
        return {"status": "NOT_RUN", "reason": "l_star unavailable"}
    for site, win_key in (("Dprime", "D"), ("E", "E")):
        per_band = {}
        for band in bands:
            gc = gen_cache.get((model, site, band))
            if gc is None:
                per_band[band] = {"status": "NOT_RUN", "reason": f"gen{site}_{band} cell missing"}
                continue
            c = load_cell(model, f"gen{site}_{band}")
            if c is None or "proj_win" not in c["arrays"]:
                per_band[band] = {"status": "NOT_RUN", "reason": "proj_win array missing"}
                continue
            proj_win = c["arrays"]["proj_win"].astype(float)         # [R, 4, L, 3]
            windows_meta = gc["meta"].get("windows", {"P": [0, 0], "D": [1, 8], "E": [5, 20], "LATE": [21, 40]})
            widx = list(windows_meta.keys()).index(win_key)
            if l_star >= proj_win.shape[2]:
                per_band[band] = {"status": "NOT_RUN", "reason": "l_star out of range for this cell"}
                continue
            f_at = proj_win[:, widx, l_star, 0]
            rows, kinds = gc["meta"]["rows"], gc["meta"]["kinds"]
            per_arm: dict = {}
            for i, (row, kind) in enumerate(zip(rows, kinds)):
                if not np.isfinite(f_at[i]):
                    continue
                per_arm.setdefault(row["arm"], {"harm": [], "hb": []})[kind].append(float(f_at[i]))
            arm_d = {}
            for a, dd in per_arm.items():
                h, b = np.array(dd["harm"]), np.array(dd["hb"])
                arm_d[a] = {"d_harm_vs_hb": float(S.cohens_d(h, b)) if h.size > 1 and b.size > 1 else None,
                           "n_harm": int(h.size), "n_hb": int(b.size)}
            per_band[band] = {"status": "OK", "window": win_key, "layer": l_star, "d_harm_vs_hb_by_arm": arm_d}
        out[site] = per_band
    return {"status": "OK", "by_site": out,
            "note": "arm-0 baseline and F/N6/RFo(mean of draws)/RN6o rows all reported; compares whether the "
                    "F-projection readout separates harm/hb at the site's own decode window"}


# ================================================================================================
# judged generation
# ================================================================================================
GEN_COLS = ("refused", "refused_raw", "harmful_compliance", "safe_engagement", "over_refusal", "judged",
            "proxy_refused", "n_new_tokens", "RD", "G1", "T1ref")


def analyze_gen(model: str) -> dict:
    c = load_cell(model, "gen_P")
    if c is None:
        return {"status": "NOT_RUN", "reason": "gen_P cell missing"}
    arrays = {k: c["arrays"][k] for k in GEN_COLS if k in c["arrays"]}
    kinds = c["meta"]["kinds"]
    rows = c["meta"]["rows"]
    recs = []
    for i, (row, kind) in enumerate(zip(rows, kinds)):
        rec = dict(row, kind=kind)
        for k, arr in arrays.items():
            rec[k] = arr[i]
        recs.append(rec)

    def group(arm, band, draw=0, kind=None):
        return [r for r in recs if r["arm"] == arm and r.get("band") == band and r.get("draw", 0) == draw
                and (kind is None or r["kind"] == kind)]

    def wilson_rate(sub_recs, col):
        vals = [r[col] for r in sub_recs if r.get("judged", 0) == 1.0 and np.isfinite(r[col])]
        n = len(vals)
        k = int(sum(vals))
        lo, hi = S.rate_ci(k, n) if n else (float("nan"), float("nan"))
        return {"k": k, "n": n, "rate": (k / n if n else None), "ci_lo": lo, "ci_hi": hi}

    def proxy_rate(sub_recs):
        vals = [r["proxy_refused"] for r in sub_recs if np.isfinite(r["proxy_refused"])]
        n = len(vals); k = int(sum(vals))
        lo, hi = S.rate_ci(k, n) if n else (float("nan"), float("nan"))
        return {"k": k, "n": n, "rate": (k / n if n else None), "ci_lo": lo, "ci_hi": hi}

    bands_present = sorted({r["band"] for r in recs if r["band"] is not None})
    per_band = {}
    diD_judged_raw: dict = {}
    for band in bands_present:
        entry = {}
        arm0_harm = group("0", None, kind="harm")
        arm0_hb = group("0", None, kind="hb")
        for arm, tag in (("F", "F"), ("N6", "N6")):
            harm_recs = group(arm, band, kind="harm")
            hb_recs = group(arm, band, kind="hb")
            rf_harm = group("RF" if arm == "F" else "RN6", band, draw=1, kind="harm")
            rf_hb = group("RF" if arm == "F" else "RN6", band, draw=1, kind="hb")
            block = {
                "n_harm": len(harm_recs), "n_hb": len(hb_recs),
                "refusal_harm": wilson_rate(harm_recs, "refused"),
                "harmful_compliance": wilson_rate(harm_recs, "harmful_compliance"),
                "safe_engagement": wilson_rate(harm_recs, "safe_engagement"),
                "over_refusal_hb": wilson_rate(hb_recs, "over_refusal"),
                "proxy_refusal_harm": proxy_rate(harm_recs),
                "proxy_refusal_hb": proxy_rate(hb_recs),
            }
            # paired arm-vs-0 and arm-vs-R1 on refusal (harm) / over_refusal (hb), judged rows only
            def paired01(sub_a, sub_0, col):
                by_a = {r["item_id"]: r[col] for r in sub_a if r.get("judged", 0) == 1.0}
                by_0 = {r["item_id"]: r[col] for r in sub_0 if r.get("judged", 0) == 1.0}
                ids = sorted(set(by_a) & set(by_0))
                if not ids:
                    return {"status": "NOT_RUN", "reason": "no overlapping judged items"}
                a = np.array([by_a[i] for i in ids], float)
                b = np.array([by_0[i] for i in ids], float)
                eff = S.paired_effect(a, b, seed=SEED)
                disc_b = int(np.sum((a == 1) & (b == 0)))
                disc_c = int(np.sum((a == 0) & (b == 1)))
                return {"status": "OK", "effect": eff, "mcnemar_p": S.mcnemar_exact(disc_b, disc_c),
                        "discordant_b": disc_b, "discordant_c": disc_c, "n": len(ids)}

            block["harm_refusal_vs_arm0"] = paired01(harm_recs, arm0_harm, "refused")
            block["over_refusal_vs_arm0"] = paired01(hb_recs, arm0_hb, "over_refusal")
            block["harm_refusal_vs_R1"] = paired01(harm_recs, rf_harm, "refused")
            block["over_refusal_vs_R1"] = paired01(hb_recs, rf_hb, "over_refusal")
            if arm == "F":
                by_a = {r["item_id"]: r["refused"] for r in harm_recs if r.get("judged", 0) == 1.0}
                by_r = {r["item_id"]: r["refused"] for r in rf_harm if r.get("judged", 0) == 1.0}
                ids = sorted(set(by_a) & set(by_r))
                diD_judged_raw.setdefault(band, {})["F_minus_RF1_harm_refusal"] = \
                    {i: by_a[i] - by_r[i] for i in ids}
            if arm == "N6":
                by_a = {r["item_id"]: r["over_refusal"] for r in hb_recs if r.get("judged", 0) == 1.0}
                by_r = {r["item_id"]: r["over_refusal"] for r in rf_hb if r.get("judged", 0) == 1.0}
                ids = sorted(set(by_a) & set(by_r))
                diD_judged_raw.setdefault(band, {})["N6_minus_RN61_over_refusal"] = \
                    {i: by_a[i] - by_r[i] for i in ids}
            per_band.setdefault(band, {})[tag] = block
        per_band[band]["arm0"] = {
            "refusal_harm": wilson_rate(arm0_harm, "refused"),
            "harmful_compliance": wilson_rate(arm0_harm, "harmful_compliance"),
            "safe_engagement": wilson_rate(arm0_harm, "safe_engagement"),
            "over_refusal_hb": wilson_rate(arm0_hb, "over_refusal"),
        }
    # Holm over the bands present, per arm/metric
    for arm in ("F", "N6"):
        for metric in ("harm_refusal_vs_arm0", "over_refusal_vs_arm0"):
            ps = [per_band[b][arm][metric]["effect"]["p_signflip"] if per_band[b][arm][metric]["status"] == "OK"
                  else float("nan") for b in bands_present]
            holm_p = S.holm(ps)
            for b, hp in zip(bands_present, holm_p):
                if per_band[b][arm][metric]["status"] == "OK":
                    per_band[b][arm][metric]["p_holm"] = hp

    # judge-vs-proxy agreement (Cohen kappa) on refusal, pooled over all rows with judged==1
    from judge import agreement
    judge_labels, proxy_labels = [], []
    for r in recs:
        if r.get("judged", 0) == 1.0 and np.isfinite(r["refused_raw"]):
            judge_labels.append({"refused": bool(r["refused_raw"])})
            proxy_labels.append({"refused": bool(r["proxy_refused"])})
    agree = agreement(judge_labels, proxy_labels)

    # T3 check: instruct only, F at B3/B4 lowers judged refusal on harm vs arm0
    t3 = {}
    if model == "instruct":
        for band in ("B3", "B4"):
            if band in per_band:
                eff = per_band[band]["F"]["harm_refusal_vs_arm0"]
                if eff["status"] == "OK":
                    e = eff["effect"]["effect"]
                    ci_hi = eff["effect"]["ci_hi"]
                    t3[band] = {"effect": e, "ci_lo": eff["effect"]["ci_lo"], "ci_hi": ci_hi,
                                "PASS": bool(np.isfinite(e) and e < 0 and ci_hi < 0)}
                else:
                    t3[band] = {"status": "NOT_RUN"}

    proxy_only_note = ("PROXY rows (judged==0.5) are reported only inside *_proxy_* aggregates above; "
                        "wilson_rate()/paired01() restrict to judged==1.0 rows and never pool PROXY with judge rows")
    cost = 0.0
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if not line.strip():
                continue
            try:
                cost += float(json.loads(line).get("cost_usd", 0) or 0)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
    return {"status": "OK", "judge_stats": c["meta"].get("judge_stats"), "per_band": per_band,
            "judge_vs_proxy_agreement": agree, "t3_check": t3, "note": proxy_only_note,
            "judge_cost_usd_total_ledger": cost, "_diD_raw_judged": diD_judged_raw}


# ================================================================================================
# ARC collateral
# ================================================================================================
def analyze_arc(model: str) -> dict:
    c = load_cell(model, "arc_P")
    if c is None:
        return {"status": "NOT_RUN", "reason": "arc_P cell missing"}
    a = c["arrays"]
    correct0 = a["correct0"]
    rows0 = c["meta"]["rows0"]
    rows = c["meta"]["rows"]
    correct = a["correct"]
    acc0 = float(np.mean(correct0))
    ci0 = S.rate_ci(int(correct0.sum()), correct0.size)
    correct0_by_id = {rows0[i]["item_id"]: correct0[i] for i in range(len(rows0))}
    recs = []
    for i, row in enumerate(rows):
        recs.append(dict(row, correct=correct[i]))
    bands = sorted({r["band"] for r in recs if r["band"] is not None})
    flip = {}
    for band in bands:
        flip[band] = {}
        for arm in ("F", "N6", "RF"):
            draw = 1 if arm == "RF" else 0
            sub = [r for r in recs if r["arm"] == arm and r["band"] == band and r.get("draw", 0) == draw]
            base_correct_ids = [r["item_id"] for r in sub if correct0_by_id.get(r["item_id"]) == 1.0]
            if not base_correct_ids:
                flip[band][arm] = {"status": "NOT_RUN", "reason": "no arm-0-correct items"}
                continue
            by_id = {r["item_id"]: r["correct"] for r in sub}
            flips = [1 - by_id[i] for i in base_correct_ids if i in by_id]
            n = len(flips); k = int(sum(flips))
            lo, hi = S.rate_ci(k, n) if n else (float("nan"), float("nan"))
            flip[band][arm] = {"n": n, "k_flipped": k, "flip_rate": (k / n if n else None), "ci_lo": lo, "ci_hi": hi}
    paired = {}
    for band in bands:
        for arm in ("F", "N6"):
            subA = {r["item_id"]: r["correct"] for r in recs if r["arm"] == arm and r["band"] == band}
            subR = {r["item_id"]: r["correct"] for r in recs if r["arm"] == "RF" and r["band"] == band
                   and r.get("draw", 0) == 1}
            ids = sorted(set(subA) & set(subR))
            if not ids:
                paired.setdefault(band, {})[arm] = {"status": "NOT_RUN"}
                continue
            a_v = np.array([subA[i] for i in ids], float)
            r_v = np.array([subR[i] for i in ids], float)
            eff = S.paired_effect(a_v, r_v, seed=SEED)
            paired.setdefault(band, {})[arm] = {"status": "OK", "effect_vs_RF1": eff, "n": len(ids)}
    return {"status": "OK", "arm0_accuracy": acc0, "arm0_accuracy_ci": ci0,
            "arm0_letter_format_frac": c["meta"].get("arm0_first_token_is_letter_frac"),
            "flip_to_wrong_rate": flip, "paired_correctness_F_N6_vs_RF1": paired}


# ================================================================================================
# displacement summary
# ================================================================================================
def analyze_displacement(model: str, bands: list[str]) -> dict:
    ratio_min, ratio_max = [], []
    resid_max = []
    per_band = {}
    for band in bands:
        for g in ("grid1", "grid2", "grid3"):
            c = load_cell(model, f"P_{band}_{g}")
            if c is None:
                continue
            disp_list = c["meta"].get("disp", [])
            for d in disp_list:
                for l, mm in d.get("ratio_R_over_src", {}).items():
                    ratio_min.append(mm[0]); ratio_max.append(mm[1])
                for l, v in d.get("resid_ratio_after_projection", {}).items():
                    resid_max.append(v)
                for arm, val in d.get("mean_disp_by_arm", {}).items():
                    for l, mv in val.items():
                        per_band.setdefault(band, {}).setdefault(arm, {})[l] = float(mv)
    if not ratio_min:
        return {"status": "NOT_RUN", "reason": "no grid cells with disp meta found"}
    return {"status": "OK", "global_min_ratio_R_over_F": float(min(ratio_min)),
            "global_max_ratio_R_over_F": float(max(ratio_max)),
            "max_residual_ratio_after_projection": float(max(resid_max)) if resid_max else None,
            "mean_disp_by_band_arm_layer": per_band}


# ================================================================================================
# directions / cosines
# ================================================================================================
def analyze_directions(model: str, L: int) -> dict:
    out = {}
    c = load_cell(model, "twins_N6")
    if c is not None:
        out["n6_best_layer"] = c["meta"]["n6_best_layer"]
        out["twin_d_by_layer"] = c["meta"]["twin_d_by_layer"]
        out["cos_F_N6_by_layer"] = c["meta"]["cos_F_N6_by_layer"]
    else:
        out["status_twins"] = "NOT_RUN"
    if model == "smoke":
        out["l_star"] = int(28 * 0.7)
    else:
        p = PRIVATE / f"directions_disk_{model}.npz"
        if p.exists():
            out["l_star"] = int(np.load(p)["l_star"])
        else:
            out["l_star"] = None
    # cos(F, iter-1 r_content / r_ablit): only meaningful for instruct/saferl (real Qwen3-4B family)
    tag_map = {"instruct": "Qwen3-4B", "saferl": "Qwen3-4B-SafeRL"}
    if model in tag_map and I1_DIRS.exists():
        pdisk = PRIVATE / f"directions_disk_{model}.npz"
        if pdisk.exists():
            F = np.load(pdisk)["F"].astype(np.float64)  # [L, d]
            for kind in ("r_content", "r_ablit"):
                fp = I1_DIRS / f"{tag_map[model]}__{kind}.npy"
                if fp.exists():
                    R = np.load(fp).astype(np.float64)  # [L+1, d]: row 0 = embedding, row l+1 = decoder layer l
                    cos = []
                    for l in range(min(L, R.shape[0] - 1)):
                        a, b = F[l], R[l + 1]
                        na, nb = np.linalg.norm(a), np.linalg.norm(b)
                        cos.append(float(a @ b / (na * nb)) if na > 0 and nb > 0 else None)
                    out[f"cos_F_iter1_{kind}"] = cos
            out["iter1_indexing_note"] = ("iter-1 released direction arrays have shape [L+1, d]; row 0 is the "
                                          "embedding output and row l+1 is decoder-layer-l's output, matching "
                                          "this experiment's own convention (band_indexing_note: layer l = hidden "
                                          "index l+1); we align iter-1 row l+1 with our layer l.")
    return out


# ================================================================================================
# spanD / spanE: forward-only teacher-forced window on the arm-0 greedy prefix
# ================================================================================================
SPAN_ARM_R = {"F": "RF", "N6": "RN6"}


def analyze_span(model: str, site: str) -> dict:
    """site in {"D","E"}: outcomes RD_{harm,hb}, lp_next_{harm,hb}; Holm over the 6 bands within
    (model, site, outcome, arm) AND (via apply_holm_and_causal/causal_cell) empirical p over the
    up-to-20 RF draws for arm F. Item sets differ per band (excluded_short_response), so items are
    grouped by (band, kind) rather than a fixed canonical order."""
    bands = list(bands_of(model).keys())
    grid: dict = {}
    for oc_base in ("RD", "lp_next"):
        for kind in ("harm", "hb"):
            outcome = f"{oc_base}_{kind}"
            grid[outcome] = {}
            for arm in ("F", "N6"):
                R_tag = SPAN_ARM_R[arm]
                cells: dict = {}
                for band in bands:
                    c = load_cell(model, f"span{site}_{band}")
                    if c is None or oc_base not in c["arrays"]:
                        cells[band] = {"status": "NOT_RUN",
                                       "reason": f"span{site}_{band} missing or no {oc_base} array"}
                        continue
                    col = c["arrays"][oc_base]
                    rows = c["meta"]["rows"]
                    recs = [dict(r, _val=col[i]) for i, r in enumerate(rows)]
                    ids = sorted({r["item_id"] for r in recs if kind_of_id(r["item_id"]) == kind})

                    def vals(a, dr=0, _recs=recs, _ids=ids, _kind=kind):
                        by = {r["item_id"]: r["_val"] for r in _recs if r["arm"] == a and r.get("draw", 0) == dr
                              and kind_of_id(r["item_id"]) == _kind and np.isfinite(r["_val"])}
                        return np.array([by.get(i, np.nan) for i in _ids], float)

                    y0, ya = vals("0"), vals(arm)
                    draws = sorted({r["draw"] for r in recs if r["arm"] == R_tag})
                    R_stack = np.array([vals(R_tag, dr=j) for j in draws]) if draws else np.zeros((0, len(ids)))
                    cells[band] = causal_cell(ya, y0, R_stack, seed=SEED)
                apply_holm_and_causal(cells)
                grid[outcome][arm] = cells
    return grid


# ================================================================================================
# GSM8K collateral
# ================================================================================================
def analyze_gsm(model: str) -> dict:
    d = CELLS / model
    names = sorted({p.stem.rsplit("__", 1)[0] for p in d.glob("gsm_*__*.npz")}) if d.exists() else []
    if not names:
        return {"status": "NOT_RUN", "reason": "no gsm_* cells present (gsm stage not run / --gsm-cells empty)"}
    cells = {}
    for name in names:
        c = load_cell(model, name)
        if c is None:
            continue
        _, site, band = name.split("_", 2)
        correct = c["arrays"]["correct"]
        rows = c["meta"]["rows"]
        recs = [dict(r, correct=correct[i]) for i, r in enumerate(rows)]
        by_arm = {}
        for a in sorted({r["arm"] for r in recs}):
            vals = [r["correct"] for r in recs if r["arm"] == a]
            n, k = len(vals), int(sum(vals))
            lo, hi = S.rate_ci(k, n) if n else (float("nan"), float("nan"))
            by_arm[a] = {"n": n, "k": k, "acc": (k / n if n else None), "ci_lo": lo, "ci_hi": hi}

        def paired(a_tag, r_tag):
            by_a = {r["item_id"]: r["correct"] for r in recs if r["arm"] == a_tag}
            by_r = {r["item_id"]: r["correct"] for r in recs if r["arm"] == r_tag}
            ids = sorted(set(by_a) & set(by_r))
            if not ids:
                return {"status": "NOT_RUN", "reason": "no overlapping items"}
            a = np.array([by_a[i] for i in ids], float)
            b = np.array([by_r[i] for i in ids], float)
            return {"status": "OK", "effect": S.paired_effect(a, b, seed=SEED), "n": len(ids)}

        r_tag = "RF" if site == "P" else "RFo"
        rn6_tag = "RN6" if site == "P" else "RN6o"
        cells[name] = {"site": site, "band": band, "by_arm": by_arm, "F_vs_arm0": paired("F", "0"),
                       "F_vs_R1": paired("F", r_tag), "N6_vs_arm0": paired("N6", "0"),
                       "N6_vs_R1": paired("N6", rn6_tag),
                       "grading": c["meta"].get("grading", "last number in the response == key (no judge)")}
    return {"status": "OK", "cells": cells}


# ================================================================================================
# site sanity checks lifted from gen{P,Dprime,E} cells' meta["checks"]; judge-vs-proxy over the full grid
# ================================================================================================
def collect_site_checks(model: str, bands: list[str]) -> dict:
    out: dict = {}
    for site in ("P", "Dprime", "E"):
        for band in bands:
            c = load_cell(model, f"gen{site}_{band}")
            out.setdefault(site, {})[band] = (c["meta"].get("checks") if c is not None else
                                              {"status": "NOT_RUN", "reason": f"gen{site}_{band} missing"})
    return out


def judge_vs_proxy_agreement_full(gen_cache: dict) -> dict:
    from judge import agreement
    judge_labels, proxy_labels = [], []
    for gc in gen_cache.values():
        for r in gc["recs"]:
            if r.get("judged", 0) == 1.0 and r.get("refused_raw") is not None and np.isfinite(r["refused_raw"]):
                judge_labels.append({"refused": bool(r["refused_raw"])})
                proxy_labels.append({"refused": bool(r["proxy_refused"])})
    return agreement(judge_labels, proxy_labels)


# ================================================================================================
# power statement for nulls (F7): per-item SD of the paired difference and MDE, for non-CAUSAL cells
# ================================================================================================
def power_summary(result: dict) -> dict:
    rows = []

    def walk_forward(grid):
        for outcome, arms in grid.items():
            for arm, bands in arms.items():
                for band, cell in bands.items():
                    if cell.get("status") != "OK" or cell.get("CAUSAL"):
                        continue
                    ev = cell.get("effect_vsR", {})
                    rows.append({"grid": "forward_only", "outcome": outcome, "arm": arm, "cell": band,
                                "sd_diff": ev.get("sd_diff"), "mde_80": ev.get("mde_80"), "n": ev.get("n")})

    def walk_judged(grid):
        for outcome, arms in grid.items():
            for arm, d in arms.items():
                for key, cell in d.get("cells", {}).items():
                    if cell.get("status") != "OK" or cell.get("CAUSAL"):
                        continue
                    ev = cell.get("effect_vsR", {})
                    rows.append({"grid": "judged", "outcome": outcome, "arm": arm, "cell": key,
                                "sd_diff": ev.get("sd_diff"), "mde_80": ev.get("mde_80"), "n": ev.get("n")})

    walk_forward(result.get("causal_grid_forward_only", {}))
    walk_judged(result.get("causal_grid_judged", {}))
    finite_mde = [r["mde_80"] for r in rows if r["mde_80"] is not None and np.isfinite(r["mde_80"])
                  and r.get("sd_diff") is not None and np.isfinite(r["sd_diff"]) and r["sd_diff"] > 0]
    n_zero_var = sum(1 for r in rows if r.get("sd_diff") is not None and np.isfinite(r["sd_diff"])
                     and r["sd_diff"] == 0)
    judged_mde = [r["mde_80"] for r in rows if r["grid"] == "judged" and r["mde_80"] is not None
                  and np.isfinite(r["mde_80"]) and r.get("sd_diff") and r["sd_diff"] > 0]
    return {"n_null_cells": len(rows), "median_mde_80": float(np.median(finite_mde)) if finite_mde else None,
            "median_mde_80_judged_cells": float(np.median(judged_mde)) if judged_mde else None,
            "n_zero_variance_cells_excluded": n_zero_var,
            "zero_variance_note": "cells whose paired differences are all 0 (e.g. refusal at ceiling in every arm) "
                                  "have sd_diff = 0 and an undefined MDE; they are excluded from the medians",
            "formula": "mde_80 ~= (z_.975 + z_.80) * sd_diff / sqrt(n) = 2.80 * sd_diff / sqrt(n), paired, "
                       "alpha=.05, power=.80 (src/stats.py paired_effect)", "rows": rows}


# ================================================================================================
# unit / hook checks
# ================================================================================================
def analyze_unit_hooks(model: str) -> dict:
    out = {}
    hc = RESULTS / f"hook_checks_{model}.json"
    out["hook_checks"] = jload(hc) if hc.exists() else {"status": "NOT_RUN", "reason": f"{hc} missing"}
    c = load_cell(model, "unit_stimuli")
    out["unit_stimuli_A_prompt_check"] = c["meta"] if c is not None else \
        {"status": "NOT_RUN", "reason": "unit_stimuli cell missing (skipped for smoke by design)"}
    rs = RESULTS / f"run_status_{model}.json"
    out["run_status"] = jload(rs) if rs.exists() else {"status": "NOT_RUN", "reason": f"{rs} missing"}
    dr = RESULTS / "disk_readouts.json"
    if dr.exists():
        d = jload(dr)
        out["disk_readouts_T1"] = d.get("models", {}).get(model, "not present for this model")
    else:
        out["disk_readouts_T1"] = {"status": "NOT_RUN", "reason": f"{dr} missing"}
    return out


# ================================================================================================
# two-sidedness (DiD), cell registry -- need both models
# ================================================================================================
def two_sidedness(results: dict) -> dict:
    if "instruct" not in results or "saferl" not in results:
        return {"status": "NOT_RUN", "reason": "both models required"}
    ri, rs = results["instruct"], results["saferl"]
    if ri.get("status") != "OK" or rs.get("status") != "OK":
        return {"status": "NOT_RUN", "reason": "arm-0 data missing for at least one model"}
    bands = [b for b in ri["bands"] if b in rs["bands"]]
    label_to_key = {
        "OR_forward_RD_hb": "N6_minus_R_RD_hb", "OR_forward_T1ref_hb": "N6_minus_R_T1ref_hb",
        "F_RD_harm": "F_minus_R_RD_harm", "F_RD_hb": "F_minus_R_RD_hb",
        "F_T1ref_harm": "F_minus_R_T1ref_harm",
    }
    item_level: dict = {}
    for band in bands:
        item_level[band] = {}
        ri_raw = ri.get("_diD_raw_forward", {}).get(band, {})
        rs_raw = rs.get("_diD_raw_forward", {}).get(band, {})
        for label, key in label_to_key.items():
            di, ds = ri_raw.get(key), rs_raw.get(key)
            if di is None or ds is None:
                item_level[band][label] = (None, None)
                continue
            ids = sorted(set(di) & set(ds))
            if not ids:
                item_level[band][label] = (None, None)
                continue
            item_level[band][label] = (np.array([di[i] for i in ids]), np.array([ds[i] for i in ids]))
        rij = ri.get("judged_generation_registered_gen_P", {}).get("_diD_raw_judged", {}).get(band, {})
        rsj = rs.get("judged_generation_registered_gen_P", {}).get("_diD_raw_judged", {}).get(band, {})
        for label, key in (("judged_OR_N6_vs_RN61", "N6_minus_RN61_over_refusal"),
                           ("judged_harm_refusal_F_vs_RF1", "F_minus_RF1_harm_refusal")):
            di, ds = rij.get(key), rsj.get(key)
            if di is None or ds is None:
                item_level[band][label] = (None, None)
                continue
            ids = sorted(set(di) & set(ds))
            item_level[band][label] = (np.array([di[i] for i in ids]), np.array([ds[i] for i in ids])) \
                if ids else (None, None)

    did_results = two_sidedness_paired(item_level)
    out = {"per_band": did_results}

    # judged 6x3-grid DiD (site x band, GPU addendum): N6 on over_refusal_hb, F on refused_harm, F on
    # over_refusal_hb -- generalises the registered-gen_P DiD above to every site x band cell that ran.
    labels2 = {"N6_over_refusal": ("N6", "over_refusal_hb"), "F_refused_harm": ("F", "refused_harm"),
              "F_over_refusal": ("F", "over_refusal_hb")}
    keys_i = ri.get("_diD_raw_judged_grid", {})
    keys_s = rs.get("_diD_raw_judged_grid", {})
    grid_did = {}
    for ck in sorted(set(keys_i) | set(keys_s)):
        grid_did[ck] = {}
        for label, (arm, outcome) in labels2.items():
            key = f"{arm}_minus_R_{outcome}"
            di, ds = keys_i.get(ck, {}).get(key), keys_s.get(ck, {}).get(key)
            if not di or not ds:
                grid_did[ck][label] = {"status": "NOT_RUN"}
                continue
            ids = sorted(set(di) & set(ds))
            if not ids:
                grid_did[ck][label] = {"status": "NOT_RUN"}
                continue
            vi, vs = np.array([di[i] for i in ids]), np.array([ds[i] for i in ids])
            grid_did[ck][label] = {"status": "OK", **S.did_paired(vs, vi, B=B_BOOT, seed=SEED)}  # DiD = saferl - instruct
    out["judged_grid_DiD"] = grid_did

    # arm-0 baselines side by side
    out["arm0_baselines"] = {
        "instruct": {"BL1_eval_by_band_arm0": {b: ri["readouts_eval_items"]["per_band"][b]["BL1_eval"]["0"]
                                               for b in ri["readouts_eval_items"]["per_band"]},
                    "judged_arm0": (ri["judged_generation_registered_gen_P"].get("per_band", {}).get("B3", {})
                                   .get("arm0") if ri["judged_generation_registered_gen_P"].get("status") == "OK"
                                   else None)},
        "saferl": {"BL1_eval_by_band_arm0": {b: rs["readouts_eval_items"]["per_band"][b]["BL1_eval"]["0"]
                                             for b in rs["readouts_eval_items"]["per_band"]},
                  "judged_arm0": (rs["judged_generation_registered_gen_P"].get("per_band", {}).get("B3", {})
                                 .get("arm0") if rs["judged_generation_registered_gen_P"].get("status") == "OK"
                                 else None)},
        "expected": "prereg expects BL1_eval lower (harm G1 closer to / below hb G1) in SafeRL than instruct",
    }
    out["registered_sign"] = ("instruct over-refusal falls more under N6-removal than SafeRL's, i.e. "
                              "DiD = [N6-R_N6](saferl,OR) - [N6-R_N6](instruct,OR) should be POSITIVE "
                              "(saferl's over-refusal drop is smaller / less negative than instruct's)")
    for band, d in did_results.items():
        for key in ("judged_OR_N6_vs_RN61", "OR_forward_RD_hb"):
            cell = d.get(key, {})
            if cell.get("status") == "OK" and np.isfinite(cell.get("did", float("nan"))):
                cell["matches_registered_sign"] = bool(cell["did"] > 0)
    for ck, d in grid_did.items():
        cell = d.get("N6_over_refusal", {})
        if cell.get("status") == "OK" and np.isfinite(cell.get("did", float("nan"))):
            cell["matches_registered_sign"] = bool(cell["did"] > 0)

    # genG global-ablation DiD (EXPLORATORY, T3): band-sets B1..B6 + ALL, T=F/R=RFo on refused_harm and
    # over_refusal_hb, T=N6/R=RN6o on over_refusal_hb. DiD = [T-R](saferl) - [T-R](instruct), paired items.
    genG_labels = {"F_refused_harm": "F_minus_R_refused_harm", "F_over_refusal": "F_minus_R_over_refusal_hb",
                  "N6_over_refusal": "N6_minus_R_over_refusal_hb"}
    ri_genG, rs_genG = ri.get("_diD_raw_genG", {}), rs.get("_diD_raw_genG", {})
    genG_did = {}
    for band_key in sorted(set(ri_genG) | set(rs_genG)):
        genG_did[band_key] = {}
        for label, key in genG_labels.items():
            di, ds = ri_genG.get(band_key, {}).get(key), rs_genG.get(band_key, {}).get(key)
            if not di or not ds:
                genG_did[band_key][label] = {"status": "NOT_RUN"}
                continue
            ids = sorted(set(di) & set(ds))
            if not ids:
                genG_did[band_key][label] = {"status": "NOT_RUN"}
                continue
            vi, vs = np.array([di[i] for i in ids]), np.array([ds[i] for i in ids])
            genG_did[band_key][label] = {"status": "OK", **S.did_paired(vs, vi, B=B_BOOT, seed=SEED)}  # DiD = saferl - instruct
    out["two_sidedness_global_ablation"] = {
        "per_band_set": genG_did,
        "note": "EXPLORATORY (genG, T3 disambiguation): DiD = [T-R](saferl) - [T-R](instruct), paired on the "
                "same item ids, T=F/R=RFo on refused_harm and over_refusal_hb, T=N6/R=RN6o on over_refusal_hb; "
                "not in any Holm family. Early single-cell numbers suggest SafeRL's refusal is much more "
                "robust to global F ablation than instruct's (e.g. B4: instruct 0.92->0.67 vs R 1.00, saferl "
                "0.96->0.88 vs R 0.98)."}
    return out


def two_sidedness_paired(item_level: dict) -> dict:
    """Proper paired DiD using raw per-item (arm - mean_R) vectors, built by the caller from the
    per-band item vectors stashed in item_level[band][key] -> (vec_instruct, vec_saferl), both
    aligned to the same 96-item canonical order (both models run on the identical eval set)."""
    out = {}
    for band, d in item_level.items():
        out[band] = {}
        for key, (vi, vs) in d.items():
            if vi is None or vs is None:
                out[band][key] = {"status": "NOT_RUN"}
                continue
            r = S.did_paired(vs, vi, B=B_BOOT, seed=SEED)  # DiD = saferl - instruct
            out[band][key] = {"status": "OK", **r}
    return out


def cell_registry(results: dict) -> dict:
    reg = {}
    for m, res in results.items():
        if res.get("status") != "OK":
            reg[m] = {"status": "NOT_RUN", "reason": res.get("reason", "arm-0 missing")}
            continue
        ro = res["readouts_eval_items"]
        bl, bn = ro["band_containing_l_star"], ro["band_containing_n6_best"]
        entry = {"l_star": ro["l_star"], "band_containing_l_star": bl,
                 "n6_best": ro["n6_best"], "band_containing_n6_best": bn}
        if bl is not None:
            entry["N1"] = {o: res["causal_grid_forward_only"][o]["F"].get(bl) for o in ("RD_harm", "RD_hb", "T1ref_harm")}
            entry["N1_decodable"] = res["decodability"].get("P", {}).get("by_band", {}).get(bl)
            entry["N2_N3_FperpU_delta"] = res["readouts_eval_items"]["per_band"].get(bl, {}).get(
                "Delta_readout", {}).get("F", {}).get("N2_eval")
        else:
            entry["N1"] = {"status": "NOT_RUN", "reason": "l_star unknown"}
        if bn is not None:
            entry["N6_N7"] = {o: res["causal_grid_forward_only"][o]["N6"].get(bn) for o in ("RD_harm", "RD_hb", "T1ref_harm")}
            entry["N7_readout"] = res["readouts_eval_items"]["per_band"].get(bn, {}).get("N7_eval")
        else:
            entry["N6_N7"] = {"status": "NOT_RUN", "reason": "n6_best unknown"}
        # N9: (band of l_star, D') judged causal_grid_judged cell + (band of l_star, D) spanD forward-only
        if bl is not None:
            jg_cells = res.get("causal_grid_judged", {}).get("refused_harm", {}).get("F", {}).get("cells", {})
            span_d = res.get("span_forward_only", {}).get("D", {}).get("RD_harm", {}).get("F", {})
            entry["N9"] = {"judged_Dprime": jg_cells.get(f"Dprime_{bl}", {"status": "NOT_RUN"}),
                          "spanD_forward_only": span_d.get(bl, {"status": "NOT_RUN"}), "band": bl}
        else:
            entry["N9"] = {"status": "NOT_RUN", "reason": "l_star unknown"}
        # N10: per band, P minus D' contrast of effect_FR(refused_harm), per-item paired diff, bootstrap CI
        diD_raw = res.get("_diD_raw_judged_grid", {})
        n10 = {}
        for band in res.get("bands", []):
            dP = diD_raw.get(f"P_{band}", {}).get("F_minus_R_refused_harm")
            dD = diD_raw.get(f"Dprime_{band}", {}).get("F_minus_R_refused_harm")
            if not dP or not dD:
                n10[band] = {"status": "NOT_RUN", "reason": "missing P or D' judged refused_harm F-vs-R diffs"}
                continue
            ids = sorted(set(dP) & set(dD))
            if not ids:
                n10[band] = {"status": "NOT_RUN", "reason": "no overlapping items"}
                continue
            vp = np.array([dP[i] for i in ids])
            vd = np.array([dD[i] for i in ids])
            diff = vp - vd
            m_ = float(diff.mean())
            lo, hi = S.bootstrap_ci_at(diff, 0.05, B=B_BOOT, seed=SEED)
            n10[band] = {"status": "OK", "contrast_P_minus_Dprime": m_, "ci_lo": lo, "ci_hi": hi,
                        "abs_contrast": abs(m_), "n": len(ids),
                        "registered_sign_pass_P_ge_Dprime": bool(m_ > 0)}
        entry["N10"] = n10
        if m in ("instruct", "saferl", "abliterated"):
            n11 = {}
            for band, cov in (("B3", "4/6"), ("B4", "6/6"), ("B5", "5/6")):
                jg = res.get("causal_grid_judged", {}).get("refused_harm", {}).get("F", {}).get("cells", {})
                n11[band] = {"coverage_of_AMS_window_L14_L28": cov,
                            "forward_only": {o: res["causal_grid_forward_only"][o]["F"].get(band) for o in
                                            ("RD_harm", "RD_hb", "T1ref_harm")},
                            "judged_site_P": jg.get(f"P_{band}", {"status": "NOT_RUN"}),
                            "decodable_P": res.get("decodability", {}).get("P", {}).get("by_band", {}).get(band)}
            entry["N11"] = n11
        else:
            entry["N11"] = {"status": "NOT_APPLICABLE", "reason": "AMS window L14..L28 is defined for the "
                            "36-layer Qwen3-4B family; smoke (Qwen3-0.6B, 28 layers) has no such mapping"}
        reg[m] = entry
    return reg


# ================================================================================================
# cross-model direction cosines (only cosines leave out/private/directions_disk_*.npz)
# ================================================================================================
def cross_model_direction_cosines(models: list[str]) -> dict:
    out: dict = {}
    Fs = {}
    for m in models:
        if m == "smoke":
            continue
        p = PRIVATE / f"directions_disk_{m}.npz"
        if p.exists():
            Fs[m] = np.load(p)["F"].astype(np.float64)
    for a, b in (("instruct", "saferl"), ("instruct", "abliterated"), ("saferl", "abliterated")):
        label = f"cos_F_{a}_vs_{b}"
        if a in Fs and b in Fs:
            Fa, Fb = Fs[a], Fs[b]
            L = min(Fa.shape[0], Fb.shape[0])
            cos = []
            for l in range(L):
                na, nb = np.linalg.norm(Fa[l]), np.linalg.norm(Fb[l])
                cos.append(float(Fa[l] @ Fb[l] / (na * nb)) if na > 0 and nb > 0 else None)
            out[label] = cos
        else:
            out[label] = {"status": "NOT_RUN", "reason": "one or both directions_disk_<model>.npz missing"}
    dr = RESULTS / "disk_readouts.json"
    if dr.exists():
        d = jload(dr)
        if "cos_F_instruct_vs_saferl" in d:
            out["cos_F_instruct_vs_saferl_from_disk_readouts_json"] = d["cos_F_instruct_vs_saferl"]
    return out


def cross_model_cosines_by_band(models: list[str]) -> dict:
    """cos(F_m,F_m') and cos(N6_m,N6_m') per pair, averaged over each band's layers (real models only;
    BANDS is the 36-layer instruct/saferl/abliterated band map -- smoke is excluded, different L)."""
    F_arrs, N6_arrs = {}, {}
    for m in models:
        if m == "smoke":
            continue
        pF, pN = PRIVATE / f"directions_disk_{m}.npz", PRIVATE / f"directions_{m}.npz"
        if pF.exists():
            F_arrs[m] = np.load(pF)["F"].astype(np.float64)
        if pN.exists():
            N6_arrs[m] = np.load(pN)["N6"].astype(np.float64)
    out = {}
    for a, b in (("instruct", "saferl"), ("instruct", "abliterated"), ("saferl", "abliterated")):
        for dirname, arrs in (("F", F_arrs), ("N6", N6_arrs)):
            key = f"cos_{dirname}_{a}_vs_{b}_by_band"
            if a not in arrs or b not in arrs:
                out[key] = {"status": "NOT_RUN", "reason": "one or both direction npz missing"}
                continue
            Fa, Fb = arrs[a], arrs[b]
            L = min(Fa.shape[0], Fb.shape[0])
            per_band = {}
            for band, layers in BANDS.items():
                layers = [l for l in layers if l < L]
                cvals = []
                for l in layers:
                    na, nb = np.linalg.norm(Fa[l]), np.linalg.norm(Fb[l])
                    if na > 0 and nb > 0:
                        cvals.append(float(Fa[l] @ Fb[l] / (na * nb)))
                per_band[band] = float(np.mean(cvals)) if cvals else None
            out[key] = per_band
    return out


def arm0_rates_from_genP(model: str, bands: list[str]) -> dict:
    """Arm-0 rates (refused_harm, harmful_compliance_harm, safe_engagement_harm, over_refusal_hb) taken
    from one genP_{band} cell's arm-0 rows. Greedy decoding is deterministic (gen_config_check reports
    sampling params ignored), so arm-0 rows are identical across every genP_{band} cell for the same
    item; the first band present (B1 when it exists) is used, and that choice is stated in "source_band"."""
    chosen = None
    gc = None
    for band in bands:
        gc = load_gen_records_named(model, f"genP_{band}")
        if gc is not None:
            chosen = band
            break
    if gc is None:
        return {"status": "NOT_RUN", "reason": "no genP_<band> cell present"}
    arm0 = [r for r in gc["recs"] if r["arm"] == "0"]

    def wilson(col, kind):
        vals = [r[col] for r in arm0 if r["kind"] == kind and r.get("judged", 0) == 1.0
               and r.get(col) is not None and np.isfinite(r[col])]
        n, k = len(vals), int(sum(vals))
        lo, hi = S.rate_ci(k, n) if n else (float("nan"), float("nan"))
        return {"k": k, "n": n, "rate": (k / n if n else None), "ci_lo": lo, "ci_hi": hi}

    return {"status": "OK", "source_band": chosen,
            "method": f"arm-0 rows from genP_{chosen} (greedy/deterministic decoding -> identical across bands)",
            "refused_harm": wilson("refused", "harm"), "harmful_compliance_harm": wilson("harmful_compliance", "harm"),
            "safe_engagement_harm": wilson("safe_engagement", "harm"), "over_refusal_hb": wilson("over_refusal", "hb")}


def arm0_forward_means(model: str, items: dict) -> dict:
    c = load_cell(model, "P_arm0")
    if c is None:
        return {"status": "NOT_RUN", "reason": "P_arm0 cell missing"}
    canon_ids, mask_h, mask_b = canon_eval_ids(items, model)
    recs0 = rows_records({k: c["arrays"][k] for k in ("RD", "G1", "T1ref") if k in c["arrays"]}, c["meta"]["rows"])
    out = {"status": "OK"}
    for col in ("RD", "G1", "T1ref"):
        v, _ = vec_from_records(recs0, canon_ids, col)
        out[f"{col}_harm_mean"] = float(np.nanmean(v[mask_h])) if np.isfinite(v[mask_h]).any() else None
        out[f"{col}_hb_mean"] = float(np.nanmean(v[mask_b])) if np.isfinite(v[mask_b]).any() else None
    return out


def l_star_dhard_n6(model: str, res: dict) -> tuple:
    l_star, n6_best = res.get("l_star"), res.get("n6_best")
    dr = RESULTS / ("disk_readouts.json" if model in ("instruct", "saferl") else f"disk_readouts_{model}.json")
    d_hard = None
    if dr.exists():
        d = jload(dr)
        dh = (d.get("models", {}).get(model, {}) if model in ("instruct", "saferl") else d).get("d_hard_by_layer")
        if dh and l_star is not None and l_star < len(dh):
            d_hard = dh[l_star]
    return l_star, d_hard, n6_best


def three_model_comparison(per_model: dict, models: list[str], items: dict) -> dict:
    """How do the checkpoints differ in activation (baselines, directions) and in causal structure
    (site-P effect_FR)? One entry per model, side by side, plus cross-model direction cosines by band."""
    out: dict = {}
    for m in models:
        res = per_model.get(m, {})
        if res.get("status") != "OK":
            out[m] = {"status": "NOT_RUN", "reason": res.get("reason", "status != OK")}
            continue
        bands = res.get("bands", [])
        l_star, d_hard, n6_best = l_star_dhard_n6(m, res)
        jg = res.get("causal_grid_judged", {})

        def eff(outcome, arm, band, _jg=jg):
            c = _jg.get(outcome, {}).get(arm, {}).get("cells", {}).get(f"P_{band}")
            return c.get("effect_vsR", {}).get("effect") if c and c.get("status") == "OK" else None

        stim = res.get("readouts_stimuli", {})
        pb = stim.get("per_band", {}) if stim.get("status") == "OK" else {}
        first_band = next(iter(pb), None)
        bl1_arm0 = pb.get(first_band, {}).get("BL1", {}).get("0") if first_band else None
        decod_p = res.get("decodability", {}).get("P", {}).get("by_band", {})
        out[m] = {
            "status": "OK",
            "arm0_baseline_rates_genP": arm0_rates_from_genP(m, bands),
            "arm0_forward_means_P_arm0": arm0_forward_means(m, items),
            "BL1_arm0_stimro": bl1_arm0 if bl1_arm0 is not None else {"status": "NOT_RUN"},
            "l_star": l_star, "d_hard_at_lstar": d_hard, "n6_best": n6_best,
            "decodability_P_auroc_by_band": {b: (decod_p.get(b, {}).get("auroc") or {}).get("auroc") for b in bands},
            "site_P_effect_FR_by_band": {
                "F_refused_harm": {b: eff("refused_harm", "F", b) for b in bands},
                "F_over_refusal_hb": {b: eff("over_refusal_hb", "F", b) for b in bands},
                "N6_over_refusal_hb": {b: eff("over_refusal_hb", "N6", b) for b in bands},
            },
        }
    out["_cross_model_direction_cosines_by_band"] = cross_model_cosines_by_band(models)
    return out


# ================================================================================================
# T1 plan check: our arm-0 judged rates (genP) vs the earlier-iteration judged rates for the SAME
# checkpoints (Newcombe difference CI). Different item sample + generation length -> a consistency
# check, not a replication.
# ================================================================================================
T1_REFERENCE = {
    "instruct": {"file": IT2_REF_1, "key_path": ("behavioural_columns", "Qwen__Qwen3-4B")},
    "saferl": {"file": IT2_REF_1, "key_path": ("behavioural_columns", "Qwen__Qwen3-4B-SafeRL")},
    "abliterated": {"file": IT2_REF_2, "key_path": ("mlabonne--Qwen3-4B-abliterated", "columns")},
}
T1_OUTCOME_MAP = {  # our outcome name -> (reference rate key, reference n key)
    "harmful_compliance_harm": ("harmful_compliance_rate", "n_harm_judged"),
    "safe_engagement_harm": ("safe_engagement_rate", "n_harm_judged"),
    "over_refusal_hb": ("over_refusal_rate", "n_benign_judged"),
}


def analyze_t1_plan_check(model: str, our_rates: dict) -> dict:
    spec = T1_REFERENCE.get(model)
    if spec is None:
        return {"status": "NOT_APPLICABLE", "reason": f"no earlier-iteration judged reference defined for "
                                                       f"model {model!r} (only instruct/saferl/abliterated)"}
    fp = Path(spec["file"])
    if not fp.exists():
        return {"status": "NOT_RUN", "reason": f"reference file {fp} missing"}
    try:
        d = json.loads(fp.read_text())
        for key in spec["key_path"]:
            d = d[key]
    except (KeyError, json.JSONDecodeError, TypeError) as e:  # noqa: BLE001 - reference parse failure -> NOT_RUN
        return {"status": "NOT_RUN", "reason": f"failed to read {fp} at {spec['key_path']}: {e!r}"}
    if our_rates.get("status") != "OK":
        return {"status": "NOT_RUN", "reason": "our arm-0 genP rates unavailable",
               "reference_file": str(fp), "reference_key_path": list(spec["key_path"])}
    out = {"status": "OK", "reference_file": str(fp), "reference_key_path": list(spec["key_path"]),
          "note": "item samples differ (our 48/96 eval items vs the reference's 45+45) and generation length "
                  "differs (48/80 our tokens vs 140 reference tokens); this is a CONSISTENCY check against the "
                  "same checkpoint's earlier-iteration judged rates, not a replication"}
    for outcome, (rate_key, n_key) in T1_OUTCOME_MAP.items():
        ours = our_rates.get(outcome, {})
        if ours.get("n") is None or ours.get("k") is None:
            out[outcome] = {"status": "NOT_RUN", "reason": "our arm-0 rate unavailable"}
            continue
        rate2, n2 = d.get(rate_key), d.get(n_key)
        if rate2 is None or not n2:
            out[outcome] = {"status": "NOT_RUN", "reason": "reference rate/n unavailable"}
            continue
        n2 = int(n2)
        k2 = int(round(rate2 * n2))
        k1, n1 = int(ours["k"]), int(ours["n"])
        lo, hi = S.newcombe_diff_ci(k1, n1, k2, n2)
        contains_0 = bool(lo <= 0.0 <= hi) if np.isfinite(lo) and np.isfinite(hi) else None
        out[outcome] = {"status": "OK", "ours": {"k": k1, "n": n1, "rate": ours.get("rate")},
                        "prior_iteration": {"k": k2, "n": n2, "rate": rate2},
                        "diff_ci_newcombe": [lo, hi], "ci_contains_0": contains_0,
                        "CONSISTENT": contains_0}
    return out


# ================================================================================================
# judge cost: main ledger (.aii_cost_ledger.jsonl) + the session-2 judge unit test's own ledger
# (out/test_judge/ledger.jsonl), summed once (not per model)
# ================================================================================================
def _sum_ledger(p: Path) -> float:
    if not p.exists():
        return 0.0
    total = 0.0
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            total += float(json.loads(line).get("cost_usd", 0) or 0)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return total


def total_judge_cost() -> dict:
    test_ledger = OUT / "test_judge" / "ledger.jsonl"
    main_usd, test_usd = _sum_ledger(LEDGER), _sum_ledger(test_ledger)
    return {"main_ledger_usd": main_usd, "main_ledger_path": str(LEDGER),
            "test_judge_ledger_usd": test_usd, "test_judge_ledger_path": str(test_ledger),
            "total_usd": main_usd + test_usd,
            "note": "test_judge_ledger_usd is the session-2 judge unit test cost, reported separately and "
                    "included in total_usd"}


# ================================================================================================
# hook-hash resolution (CLI override -> run_status_<model>.json -> newest hash present)
# ================================================================================================
def resolve_hook_hash(models: list[str], override: str | None) -> str | None:
    if override:
        return override
    for m in models:
        rs = RESULTS / f"run_status_{m}.json"
        if rs.exists():
            h = jload(rs).get("hook_hash")
            if h:
                return h
    cands = []
    for m in models:
        d = CELLS / m
        if d.exists():
            cands += list(d.glob("*__*.json"))
    if cands:
        best = max(cands, key=lambda p: p.stat().st_mtime)
        return best.stem.rsplit("__", 1)[-1]
    return None


# ================================================================================================
# method_out.json (exp_gen_sol_out schema) builders
# ================================================================================================
def _json1(obj) -> str:
    return json.dumps(_clean(obj), ensure_ascii=False)


def _cell_summary(cell: dict) -> dict:
    if cell.get("status") != "OK":
        return {"status": cell.get("status", "NOT_RUN"), "reason": cell.get("reason")}
    ev0, evR = cell["effect_vs0"], cell["effect_vsR"]
    return {"mean_0": cell.get("mean_0"), "mean_T": cell.get("mean_T"), "mean_R": cell.get("mean_R"),
            "effect_T0": [ev0["effect"], ev0["ci_lo"], ev0["ci_hi"]],
            "effect_TR": [evR["effect"], evR["ci_lo"], evR["ci_hi"]],
            "p": evR.get("p_signflip"), "p_holm": cell.get("p_holm"), "CAUSAL": cell.get("CAUSAL"),
            "empirical_p_envelope": cell.get("empirical_p_envelope"), "n_R_draws": cell.get("n_R_draws")}


def _decod_for(res: dict, site: str, band: str) -> dict:
    return res.get("decodability", {}).get(site, {}).get("by_band", {}).get(band, {})


CONTROL_OF = {"F": {"P": "RF", "Dprime": "RFo", "E": "RFo"}, "N6": {"P": "RN6", "Dprime": "RN6o", "E": "RN6o"},
             "N6perp": {"P": "RF"}, "POS": {"P": "RF"}}


def build_causal_grid_judged_dataset(model: str, res: dict) -> list[dict]:
    examples = []
    bmap = bands_of(model)
    jg = res.get("causal_grid_judged", {})
    for site in SITES_JUDGED:
        for band in res.get("bands", []):
            layers = bmap.get(band, [])
            l0, l1 = (layers[0], layers[-1]) if layers else (None, None)
            for arm in JUDGED_ARMS:
                if arm in ("N6perp", "POS") and site != "P":
                    continue
                if arm == "POS" and band not in ("B3", "B4"):
                    continue
                key = f"{site}_{band}"
                control = CONTROL_OF[arm].get(site, "?")
                out_obj, n_harm, n_hb = {}, None, None
                for outcome in ("refused_harm", "harmful_compliance_harm", "safe_engagement_harm", "over_refusal_hb"):
                    cell = jg.get(outcome, {}).get(arm, {}).get("cells", {}).get(key, {"status": "NOT_RUN"})
                    out_obj[outcome] = _cell_summary(cell)
                    if cell.get("status") == "OK":
                        n = cell["effect_vs0"]["n"]
                        if JUDGED_OUTCOME_COLS[outcome][1] == "harm":
                            n_harm = n
                        else:
                            n_hb = n
                rh_cell = jg.get("refused_harm", {}).get(arm, {}).get("cells", {}).get(key, {})
                proxy_cell = jg.get("proxy_refused_harm", {}).get(arm, {}).get("cells", {}).get(key, {})
                dec = _decod_for(res, site, band)
                rh = out_obj["refused_harm"]
                r0 = None
                if rh_cell.get("status") == "OK" and rh_cell.get("mean_R") is not None and \
                        rh_cell.get("mean_0") is not None:
                    r0 = rh_cell["mean_R"] - rh_cell["mean_0"]
                ex = {
                    "input": f"model={model} site={site} band={band} layers={l0}-{l1} arm={arm} control={control} "
                             f"n_harm={n_harm} n_hb={n_hb}",
                    "output": _json1(out_obj),
                    "predict_intervention": f"effect_TR(refused_harm)={rh.get('effect_TR')}; CAUSAL={rh.get('CAUSAL')}",
                    "predict_random_control": f"effect_R0(refused_harm)={r0}",
                    "predict_keyword_proxy": (f"proxy_effect_TR(refused_harm)="
                                              f"{proxy_cell.get('effect_vsR', {}).get('effect')}"
                                              if proxy_cell.get("status") == "OK" else "proxy_effect_TR=NOT_RUN"),
                    "metadata_effect_FR_refused_harm": rh.get("effect_TR", [None, None, None])[0],
                    "metadata_ci_lo_refused_harm": rh.get("effect_TR", [None, None, None])[1],
                    "metadata_ci_hi_refused_harm": rh.get("effect_TR", [None, None, None])[2],
                    "metadata_causal_refused_harm": rh.get("CAUSAL"),
                    "metadata_decodable": dec.get("DECODABLE"),
                    "metadata_auroc": (dec.get("auroc") or {}).get("auroc"),
                }
                examples.append(ex)
    if not examples:
        examples.append({"input": f"model={model} causal_grid_judged", "output": json.dumps({"status": "NOT_RUN"})})
    return examples


def build_causal_grid_forward_dataset(model: str, res: dict) -> list[dict]:
    examples = []
    bmap = bands_of(model)
    fwd = res.get("causal_grid_forward_only", {})
    span = res.get("span_forward_only", {})
    for band in res.get("bands", []):
        layers = bmap.get(band, [])
        l0, l1 = (layers[0], layers[-1]) if layers else (None, None)
        for arm in ("F", "N6", "N6perp"):
            out_obj = {o: _cell_summary(fwd.get(o, {}).get(arm, {}).get(band, {"status": "NOT_RUN"}))
                      for o in ("RD_harm", "RD_hb", "T1ref_harm")}
            examples.append({"input": f"model={model} site=P band={band} layers={l0}-{l1} arm={arm} "
                                      f"(registered F1 forward-only)", "output": _json1(out_obj)})
        for site_key in ("D", "E"):
            sg = span.get(site_key, {})
            for arm in ("F", "N6"):
                out_obj = {o: _cell_summary(sg.get(o, {}).get(arm, {}).get(band, {"status": "NOT_RUN"}))
                          for o in ("RD_harm", "RD_hb", "lp_next_harm", "lp_next_hb")}
                examples.append({"input": f"model={model} site={site_key} band={band} layers={l0}-{l1} arm={arm} "
                                          f"(span{site_key} forward-only)", "output": _json1(out_obj)})
    if not examples:
        examples.append({"input": f"model={model} causal_grid_forward_only",
                         "output": json.dumps({"status": "NOT_RUN"})})
    return examples


def build_readouts_dataset(model: str, res: dict) -> list[dict]:
    examples = []
    stim = res.get("readouts_stimuli", {})
    per_band_stim = stim.get("per_band", {}) if stim.get("status") == "OK" else {}
    ev = res.get("readouts_eval_items", {})
    per_band_eval = ev.get("per_band", {})
    dw = res.get("readouts_decode_window", {})
    dw_by_site = dw.get("by_site", {}) if dw.get("status") == "OK" else {}
    for band in res.get("bands", []):
        obj = {"stimuli_BL1_N1_N6_N7": per_band_stim.get(band, {"status": "NOT_RUN"}),
              "eval_items_BL1_N1_N2_N6_N7": per_band_eval.get(band, {"status": "NOT_RUN"}),
              "decode_window_F_projection": {site: dw_by_site.get(site, {}).get(band) for site in ("Dprime", "E")}}
        examples.append({"input": f"model={model} band={band} readouts_under_intervention", "output": _json1(obj)})
    if not examples:
        examples.append({"input": f"model={model} readouts_under_intervention",
                         "output": json.dumps({"status": "NOT_RUN"})})
    return examples


def build_two_sidedness_dataset(analysis: dict) -> list[dict]:
    ts = analysis.get("two_sidedness", {})
    if "per_band" not in ts:
        return [{"input": "two_sidedness instruct_vs_saferl", "output": _json1(ts)}]
    examples = [{"input": f"two_sidedness band={band} (registered gen_P DiD)", "output": _json1(d)}
               for band, d in ts.get("per_band", {}).items()]
    examples += [{"input": f"two_sidedness cell={key} (judged 6x3 grid DiD)", "output": _json1(d)}
                for key, d in ts.get("judged_grid_DiD", {}).items()]
    if not examples:
        examples.append({"input": "two_sidedness", "output": json.dumps({"status": "NOT_RUN"})})
    return examples


def build_cell_registry_dataset(analysis: dict) -> list[dict]:
    reg = analysis.get("cell_registry", {})
    examples = [{"input": f"cell_registry model={m}", "output": _json1(entry)} for m, entry in reg.items()]
    if not examples:
        examples.append({"input": "cell_registry", "output": json.dumps({"status": "NOT_RUN"})})
    return examples


def build_collateral_dataset(model: str, res: dict) -> list[dict]:
    obj = {"arc": res.get("arc_collateral", {}), "gsm": res.get("gsm", {}),
          "positive_control_forward_only": res.get("positive_control_forward_only", {}),
          "site_checks": res.get("site_checks_gen_grid", {})}
    return [{"input": f"model={model} collateral_arc_gsm", "output": _json1(obj)}]


def build_exploratory_fperpu_dataset(model: str, res: dict) -> list[dict]:
    genU = res.get("genU_exploratory_FperpU", {})
    per_band = genU.get("per_band", {}) if isinstance(genU, dict) else {}
    examples = [{"input": f"model={model} band={band} genU_exploratory_FperpU (plan 9b; NOT in any Holm "
                         f"family, no CAUSAL determination)", "output": _json1(band_out)}
               for band, band_out in per_band.items()]
    if not examples:
        examples.append({"input": f"model={model} genU_exploratory_FperpU",
                         "output": json.dumps({"status": genU.get("status", "NOT_RUN") if isinstance(genU, dict)
                                               else "NOT_RUN"})})
    return examples


def build_site_e_late_dataset(model: str, res: dict) -> list[dict]:
    e2x2 = res.get("e2x2_E_site_readout", {})
    if not isinstance(e2x2, dict) or e2x2.get("status") != "OK":
        return [{"input": f"model={model} e2x2_E_site_readout",
                 "output": _json1(e2x2 if isinstance(e2x2, dict) else {"status": "NOT_RUN"})}]
    examples = []
    for label, block in (("N1_analogue_F_at_lstar", e2x2.get("N1_analogue_F_at_lstar", {})),
                         ("N6_analogue_at_n6best", e2x2.get("N6_analogue_at_n6best", {}))):
        if block.get("status") != "OK":
            examples.append({"input": f"model={model} {label} (site-E LATE-window readout)",
                             "output": _json1(block)})
            continue
        for band, band_out in block.get("per_band", {}).items():
            examples.append({"input": f"model={model} band={band} {label} (site-E LATE-window readout, "
                                      f"tokens 40-55, after EARLY-window edit)", "output": _json1(band_out)})
    if not examples:
        examples.append({"input": f"model={model} e2x2_E_site_readout", "output": json.dumps({"status": "NOT_RUN"})})
    return examples


def build_global_ablation_dataset(model: str, res: dict) -> list[dict]:
    genG = res.get("genG_global_ablation_control", {})
    per_band = genG.get("per_band", {}) if isinstance(genG, dict) else {}
    examples = []
    for band_key, band_out in per_band.items():
        if not isinstance(band_out, dict) or band_out.get("status") == "NOT_RUN":
            examples.append({"input": f"model={model} band={band_key} global_ablation_control "
                                      f"(T3 disambiguation, exploratory)",
                             "output": _json1(band_out if isinstance(band_out, dict) else {"status": "NOT_RUN"})})
            continue
        examples.append({"input": f"model={model} band={band_key} global_ablation_control "
                                  f"(site=ALLPOS local-vs-global comparison, T3 disambiguation, exploratory)",
                         "output": _json1(band_out)})
    if not examples:
        examples.append({"input": f"model={model} global_ablation_control",
                         "output": json.dumps({"status": genG.get("status", "NOT_RUN")
                                               if isinstance(genG, dict) else "NOT_RUN"})})
    return examples


def build_method_out(analysis: dict) -> dict:
    per_model = analysis.get("per_model", {})
    datasets, not_run, causal_counts, inert_counts = [], [], {}, {}
    for model, res in per_model.items():
        if res.get("status") != "OK":
            not_run.append({"model": model, "reason": res.get("reason", "status != OK")})
            continue
        datasets.append({"dataset": f"causal_grid_judged_{model}",
                         "examples": build_causal_grid_judged_dataset(model, res)})
        datasets.append({"dataset": f"causal_grid_forward_only_{model}",
                         "examples": build_causal_grid_forward_dataset(model, res)})
        datasets.append({"dataset": f"readouts_under_intervention_{model}",
                         "examples": build_readouts_dataset(model, res)})
        datasets.append({"dataset": f"collateral_arc_gsm_{model}", "examples": build_collateral_dataset(model, res)})
        datasets.append({"dataset": f"exploratory_FperpU_{model}",
                         "examples": build_exploratory_fperpu_dataset(model, res)})
        datasets.append({"dataset": f"site_E_late_readout_{model}",
                         "examples": build_site_e_late_dataset(model, res)})
        datasets.append({"dataset": f"global_ablation_control_{model}",
                         "examples": build_global_ablation_dataset(model, res)})
        jg = res.get("causal_grid_judged", {})
        for outcome, arms in jg.items():
            for arm, d in arms.items():
                causal_counts[f"{model}.{outcome}.{arm}"] = sum(
                    1 for c in d.get("cells", {}).values() if c.get("CAUSAL"))
        for label, d in res.get("two_by_two_decodable_causal", {}).items():
            inert_counts[f"{model}.{label}"] = d.get("decodable_but_inert_count")
        for site, bb in res.get("site_checks_gen_grid", {}).items():
            for band, chk in bb.items():
                if isinstance(chk, dict) and chk.get("status") == "NOT_RUN":
                    not_run.append({"model": model, "cell": f"gen{site}_{band}", "reason": chk.get("reason")})
    datasets.append({"dataset": "two_sidedness", "examples": build_two_sidedness_dataset(analysis)})
    datasets.append({"dataset": "cell_registry", "examples": build_cell_registry_dataset(analysis)})
    if not datasets:
        datasets = [{"dataset": "status", "examples": [{"input": "run", "output": json.dumps({"status": "NOT_RUN"})}]}]
    judge_cost = analysis.get("judge_cost") or total_judge_cost()
    metadata = {
        "title": "Causal depth x site intervention grid: Qwen3-4B (instruct) vs Qwen3-4B-SafeRL "
                 "(+ optional abliterated checkpoint)",
        "prereg_sha256": analysis.get("prereg", {}).get("prereg_sha256"),
        "prereg_gpu_addendum_sha256": analysis.get("prereg", {}).get("prereg_gpu_addendum_sha256"),
        "hook_hash": analysis.get("hook_hash"), "models": analysis.get("models"),
        "device": {m: per_model[m].get("status") for m in per_model},
        "judge_cost_usd_total": judge_cost["total_usd"],
        "judge_cost_breakdown": judge_cost,
        "headline_causal_cell_counts": causal_counts,
        "decodable_but_inert_counts": inert_counts,
        "deviations": analysis.get("deviations", []),
        "not_run": not_run,
        "generated_utc": analysis.get("generated_utc"),
    }
    return {"metadata": _clean(metadata), "datasets": datasets}


# ================================================================================================
# summary_tables.md
# ================================================================================================
def _fmt_cell(cell: dict) -> str:
    if not cell or cell.get("status") != "OK":
        return (cell or {}).get("status", "NOT_RUN")
    e = cell["effect_vsR"]["effect"]
    star = "*" if cell.get("CAUSAL") else ""
    return f"{e:+.3f}{star}" if np.isfinite(e) else "nan"


def _fmt_num(v, fmt="{:+.3f}") -> str:
    return fmt.format(v) if isinstance(v, (int, float)) and np.isfinite(v) else "-"


def _fmt_boot(d: dict) -> str:
    if not isinstance(d, dict) or d.get("status") not in (None, "OK") or d.get("delta") is None:
        v = d.get("value") if isinstance(d, dict) else None
        lo, hi = (d.get("ci_lo"), d.get("ci_hi")) if isinstance(d, dict) else (None, None)
        if v is None:
            return "NOT_RUN"
        return f"{_fmt_num(v)} [{_fmt_num(lo)},{_fmt_num(hi)}]"
    v, lo, hi = d.get("delta"), d.get("ci_lo"), d.get("ci_hi")
    if v is None or not np.isfinite(v):
        return "NOT_RUN"
    return f"{_fmt_num(v)} [{_fmt_num(lo)},{_fmt_num(hi)}]"


def _append_extra_tables(lines: list, model: str, res: dict, bands: list) -> None:
    """Tables 1-7 requested on top of analysis.json: F1 forward grid, spanD/E, stimro readouts, genU,
    e2x2_E, decode-window, genG -- one block per model, numbers pulled straight from the JSON sections."""
    fwd = res.get("causal_grid_forward_only", {})
    pcfo = res.get("positive_control_forward_only", {})

    # ---- 1. Registered F1 site-P forward-only grid ----
    lines.append("### 1. Registered F1 (site P forward-only): effect_FR by band, * = CAUSAL")
    lines.append("Family = 6 site-P bands per (outcome,arm); CAUSAL also requires empirical p<.05 over the "
                "20 RF draws when n_R_draws>=19 (POS is a positive control, vs RF, no CAUSAL determination).")
    lines.append("| outcome | arm | " + " | ".join(bands) + " |")
    lines.append("|---|---|" + "---|" * len(bands))
    for outcome in ("RD_harm", "RD_hb", "T1ref_harm"):
        for arm in ("F", "N6", "N6perp"):
            row = [outcome, arm] + [_fmt_cell(fwd.get(outcome, {}).get(arm, {}).get(b)) for b in bands]
            lines.append("| " + " | ".join(row) + " |")
        row = [outcome, "POS(vsRF)"]
        for b in bands:
            c = pcfo.get(outcome, {}).get(b, {})
            if c.get("status") != "OK":
                row.append(c.get("status", "NOT_RUN"))
            else:
                e = c.get("effect_vsRF", {}).get("effect")
                row.append(_fmt_num(e) if e is not None else "NOT_RUN")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # ---- 2. spanD / spanE forward-only ----
    lines.append("### 2. spanD / spanE forward-only, arm F: effect_FR by band, * = CAUSAL")
    span = res.get("span_forward_only", {})
    lines.append("| site | outcome | " + " | ".join(bands) + " | n_items (excluded) by band |")
    lines.append("|---|---|" + "---|" * len(bands) + "---|")
    for site in ("D", "E"):
        sg = span.get(site, {})
        for outcome in ("RD_harm", "lp_next_harm", "RD_hb"):
            row = [site, outcome] + [_fmt_cell(sg.get(outcome, {}).get("F", {}).get(b)) for b in bands]
            n_info = []
            for b in bands:
                c = load_cell(model, f"span{site}_{b}")
                if c is None:
                    n_info.append(f"{b}:NOT_RUN")
                else:
                    n_info.append(f"{b}:{c['meta'].get('n_items')}"
                                  f"({len(c['meta'].get('excluded_short_response', []))} excl)")
            row.append("; ".join(n_info))
            lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # ---- 3. Readouts under intervention (stimro_P) ----
    lines.append("### 3. Readouts under intervention (stimro_P): BL1_easy/hard by arm (0/F/N6/RF1), N1, "
                "Delta_BL1(F)-Delta_BL1(RF1), |Delta_BL1(RF1)|")
    stim = res.get("readouts_stimuli", {})
    pb = stim.get("per_band", {}) if stim.get("status") == "OK" else {}
    lines.append("| band | BL1_easy 0/F/N6/RF1 | BL1_hard 0/F/N6/RF1 | N1 0/F/N6/RF1 | "
                "Delta(F-RF1) easy [CI] | \\|RF1\\| easy | Delta(F-RF1) hard [CI] | \\|RF1\\| hard | MECH_FORCED |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for band in bands:
        e = pb.get(band)
        if not e:
            lines.append(f"| {band} | NOT_RUN | | | | | | | |")
            continue
        bl1, n1 = e.get("BL1", {}), e.get("N1", {})
        bl1_easy = "/".join(_fmt_num(bl1.get(t, {}).get("BL1_easy")) for t in ("0", "F", "N6", "RF1"))
        bl1_hard = "/".join(_fmt_num(bl1.get(t, {}).get("BL1_hard")) for t in ("0", "F", "N6", "RF1"))
        n1s = "/".join(_fmt_num(n1.get(t)) for t in ("0", "F", "N6", "RF1"))
        dfe = e.get("Delta_BL1_F_minus_RF1", {}).get("easy", {})
        dfh = e.get("Delta_BL1_F_minus_RF1", {}).get("hard", {})
        absrf1 = e.get("abs_Delta_BL1_RF1", {})
        mech = e.get("MECHANICALLY_FORCED_N1_F")
        lines.append(f"| {band} | {bl1_easy} | {bl1_hard} | {n1s} | {_fmt_boot(dfe)} | "
                    f"{_fmt_num(absrf1.get('easy'))} | {_fmt_boot(dfh)} | {_fmt_num(absrf1.get('hard'))} | "
                    f"{mech} |")
    lines.append("")

    # ---- 4. genU (exploratory FperpU) ----
    lines.append("### 4. genU (exploratory FperpU), per band: rates 0/F/FperpU/RUo, effect_FperpU_R, "
                "FperpU-minus-F paired [CI]")
    genU = res.get("genU_exploratory_FperpU", {})
    genU_pb = genU.get("per_band", {}) if genU.get("status") in ("OK",) else {}
    lines.append("| band | outcome | rate 0 | rate F | rate FperpU | rate RUo | effect_FperpU_R | "
                "FperpU-F paired [CI] |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for band in bands:
        bo = genU_pb.get(band)
        if not isinstance(bo, dict) or bo.get("status") == "NOT_RUN":
            lines.append(f"| {band} | all | NOT_RUN | | | | | |")
            continue
        for outcome in ("refused_harm", "over_refusal_hb", "RD_harm"):
            oc = bo.get(outcome, {})
            cF, cU = oc.get("F_vs_0_and_R", {}), oc.get("FperpU_vs_0_and_R", {})
            contrast = oc.get("FperpU_minus_F_paired_same_pass", {})
            if cF.get("status") != "OK" and cU.get("status") != "OK":
                lines.append(f"| {band} | {outcome} | NOT_RUN | | | | | |")
                continue
            r0 = cF.get("mean_0", cU.get("mean_0"))
            rF = cF.get("mean_T")
            rU = cU.get("mean_T")
            rR = cF.get("mean_R", cU.get("mean_R"))
            eff_r = cU.get("effect_vsR", {}).get("effect") if cU.get("status") == "OK" else None
            contrast_s = (f"{_fmt_num(contrast.get('delta_FperpU_minus_F'))} "
                         f"[{_fmt_num(contrast.get('ci_lo'))},{_fmt_num(contrast.get('ci_hi'))}]"
                         if contrast.get("status") == "OK" else "NOT_RUN")
            lines.append(f"| {band} | {outcome} | {_fmt_num(r0)} | {_fmt_num(rF)} | {_fmt_num(rU)} | "
                        f"{_fmt_num(rR)} | {_fmt_num(eff_r)} | {contrast_s} |")
    lines.append("")

    # ---- 5. e2x2_E (site-E late readout), F-analogue at l_star ----
    lines.append("### 5. e2x2_E site-E LATE-window readout (F-analogue at l_star): d_0, Delta_d(F), "
                "Delta_d(F)-meanDelta_d(RF1,RF2) [CI], Delta_d(N6)")
    e2x2 = res.get("e2x2_E_site_readout", {})
    n1a = e2x2.get("N1_analogue_F_at_lstar", {}) if e2x2.get("status") == "OK" else {}
    n1a_pb = n1a.get("per_band", {}) if n1a.get("status") == "OK" else {}
    lines.append("| band | d_0 | Delta_d(F) [CI] | Delta_d(F)-meanRF [CI] | Delta_d(N6) |")
    lines.append("|---|---|---|---|---|")
    for band in bands:
        bo = n1a_pb.get(band)
        if not bo:
            lines.append(f"| {band} | NOT_RUN | | | |")
            continue
        f_ = bo.get("F", {})
        d0 = f_.get("d_0") if f_.get("status") == "OK" else None
        deltaF = (f"{_fmt_num(f_.get('delta'))} [{_fmt_num(f_.get('ci_lo'))},{_fmt_num(f_.get('ci_hi'))}]"
                  if f_.get("status") == "OK" else "NOT_RUN")
        fmr = bo.get("F_minus_meanRF", {})
        fmr_s = (f"{_fmt_num(fmr.get('value'))} [{_fmt_num(fmr.get('ci_lo'))},{_fmt_num(fmr.get('ci_hi'))}]"
                if fmr.get("status") == "OK" else "NOT_RUN")
        n6_ = bo.get("N6", {})
        deltaN6 = _fmt_num(n6_.get("delta")) if n6_.get("status") == "OK" else "NOT_RUN"
        lines.append(f"| {band} | {_fmt_num(d0)} | {deltaF} | {fmr_s} | {deltaN6} |")
    lines.append("")

    # ---- 6. decode-window readout (proj_win): d(harm vs hb) of the F-projection at l_star ----
    lines.append("### 6. Decode-window readout (proj_win): d(harm vs hb), F-projection at l_star, arms 0/F/R")
    dw = res.get("readouts_decode_window", {})
    dw_site = dw.get("by_site", {}) if dw.get("status") == "OK" else {}
    lines.append("| site (window) | band | d_0 | d_F | d_R |")
    lines.append("|---|---|---|---|---|")
    for site, win in (("Dprime", "D"), ("E", "E")):
        for band in bands:
            bo = dw_site.get(site, {}).get(band, {})
            if bo.get("status") != "OK":
                lines.append(f"| {site}({win}) | {band} | NOT_RUN | | |")
                continue
            arm_d = bo.get("d_harm_vs_hb_by_arm", {})
            d0 = arm_d.get("0", {}).get("d_harm_vs_hb")
            dF = arm_d.get("F", {}).get("d_harm_vs_hb")
            r_tag = "RFo" if "RFo" in arm_d else ("RF" if "RF" in arm_d else None)
            dR = arm_d.get(r_tag, {}).get("d_harm_vs_hb") if r_tag else None
            lines.append(f"| {site}({win}) | {band} | {_fmt_num(d0)} | {_fmt_num(dF)} | {_fmt_num(dR)} |")
    lines.append("")

    # ---- 7. genG (T3 global-ablation control) ----
    lines.append("### 7. genG (T3 global-ablation control, EXPLORATORY): rates by arm, band-set")
    genG = res.get("genG_global_ablation_control", {})
    genG_pb = genG.get("per_band", {}) if genG.get("status") == "OK" else {}
    lines.append("| band-set | outcome | rate 0 | rate F | rate RFo | rate N6 | rate RN6o |")
    lines.append("|---|---|---|---|---|---|---|")
    for bk in [b for b in bands if b in genG_pb] + (["ALL"] if "ALL" in genG_pb else []):
        bo = genG_pb.get(bk)
        if not isinstance(bo, dict) or bo.get("status") == "NOT_RUN":
            lines.append(f"| {bk} | all | NOT_RUN | | | | |")
            continue
        for outcome in ("refused_harm", "harmful_compliance_harm", "over_refusal_hb"):
            oc = bo.get(outcome, {})
            cF, cN6 = oc.get("F_global_ablation", {}), oc.get("N6_global_ablation", {})
            if cF.get("status") != "OK" and cN6.get("status") != "OK":
                lines.append(f"| {bk} | {outcome} | NOT_RUN | | | | |")
                continue
            r0 = cF.get("mean_0", cN6.get("mean_0"))
            rF, rRFo = cF.get("mean_T"), cF.get("mean_R")
            rN6, rRN6o = cN6.get("mean_T"), cN6.get("mean_R")
            lines.append(f"| {bk} | {outcome} | {_fmt_num(r0)} | {_fmt_num(rF)} | {_fmt_num(rRFo)} | "
                        f"{_fmt_num(rN6)} | {_fmt_num(rRN6o)} |")
    lines.append("")


def build_summary_tables(analysis: dict) -> str:
    lines = ["# Summary tables -- causal depth x site grid", "",
            f"Generated {analysis.get('generated_utc')} | hook_hash `{analysis.get('hook_hash')}` | "
            f"models: {', '.join(analysis.get('models', []))}", ""]
    for model, res in analysis.get("per_model", {}).items():
        lines.append(f"## {model}")
        if res.get("status") != "OK":
            lines += [f"NOT_RUN: {res.get('reason')}", ""]
            continue
        bands = res.get("bands", [])
        jg = res.get("causal_grid_judged", {})
        for arm, outcome, title in (("F", "refused_harm", "arm F, refused_harm (site P/D'/E)"),
                                    ("F", "harmful_compliance_harm", "arm F, harmful_compliance_harm"),
                                    ("F", "over_refusal_hb", "arm F, over_refusal_hb"),
                                    ("N6", "over_refusal_hb", "arm N6, over_refusal_hb")):
            fam = jg.get(outcome, {}).get(arm, {})
            lines.append(f"### Judged grid: {title} (effect_FR, * = CAUSAL; family size used = "
                        f"{fam.get('family_size_used')})")
            lines.append("| band | P | D' | E |")
            lines.append("|---|---|---|---|")
            for band in bands:
                row = [band] + [_fmt_cell(fam.get("cells", {}).get(f"{site}_{band}")) for site in ("P", "Dprime", "E")]
                lines.append("| " + " | ".join(row) + " |")
            lines.append("")
        lines.append("### Decodability (AUROC; * = DECODABLE, ci_lo>0.60)")
        lines.append("| band | P | D' (window D) | E |")
        lines.append("|---|---|---|---|")
        for band in bands:
            row = [band]
            for site in ("P", "Dprime", "E"):
                d = _decod_for(res, site, band)
                auc = (d.get("auroc") or {}).get("auroc")
                row.append(f"{auc:.3f}{'*' if d.get('DECODABLE') else ''}" if auc is not None else "NOT_RUN")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")
        for label, d in res.get("two_by_two_decodable_causal", {}).items():
            lines.append(f"2x2 **{label}**: decodable-but-inert = {d.get('decodable_but_inert_count')} / "
                        f"decodable = {d.get('decodable_count')} / total cells = {len(d.get('rows', []))}")
        lines.append("")
        _append_extra_tables(lines, model, res, bands)
        arc = res.get("arc_collateral", {})
        lines.append(f"ARC arm-0 accuracy: {arc.get('arm0_accuracy')} (status {arc.get('status')})")
        lines.append(f"GSM8K collateral status: {res.get('gsm', {}).get('status')}")
        lines.append(f"genU exploratory (FperpU) status: {res.get('genU_exploratory_FperpU', {}).get('status')}")
        lines.append(f"e2x2_E site readout status: {res.get('e2x2_E_site_readout', {}).get('status')}")
        lines.append(f"genG global-ablation control (T3) status: "
                    f"{res.get('genG_global_ablation_control', {}).get('status')}")
        pw = res.get("power_nulls", {})
        lines.append(f"Power (F7, null cells): n={pw.get('n_null_cells')} ({pw.get('n_zero_variance_cells_excluded')} "
                     f"zero-variance cells excluded), median MDE80 (all non-degenerate) = {pw.get('median_mde_80')}, "
                     f"median MDE80 (judged cells) = {pw.get('median_mde_80_judged_cells')}")
        agree = res.get("judge_vs_proxy_agreement_full_grid", {})
        lines.append(f"Judge-vs-keyword-proxy agreement (full grid): kappa={agree.get('kappa')} "
                    f"raw={agree.get('raw_agreement')} n={agree.get('n_pairs')}")
        t1 = res.get("t1_arm0_vs_prior_judged", {})
        if t1.get("status") == "OK":
            parts = []
            for oc in ("harmful_compliance_harm", "safe_engagement_harm", "over_refusal_hb"):
                c = t1.get(oc, {})
                if c.get("status") == "OK":
                    parts.append(f"{oc}: ours={c['ours']['rate']:.3f} prior={c['prior_iteration']['rate']:.3f} "
                                f"diffCI=[{c['diff_ci_newcombe'][0]:.3f},{c['diff_ci_newcombe'][1]:.3f}] "
                                f"consistent={c['CONSISTENT']}")
                else:
                    parts.append(f"{oc}: {c.get('status')}")
            lines.append("T1 plan check (arm0 vs prior-iteration judged rates): " + "; ".join(parts))
        else:
            lines.append(f"T1 plan check status: {t1.get('status')} ({t1.get('reason')})")
        a0s = res.get("arm0_stability", {})
        if a0s.get("status") == "OK":
            rr, orr = a0s["refused_harm_rate_range_across_cells"], a0s["over_refusal_hb_rate_range_across_cells"]
            lines.append(f"Arm0 stability across {rr.get('n_cells_with_rate')} judged cell families: "
                        f"refused_harm rate [{rr.get('min')},{rr.get('max')}] "
                        f"({a0s.get('n_items_refused_harm_label_unstable_across_cells')} items label-unstable); "
                        f"over_refusal_hb rate [{orr.get('min')},{orr.get('max')}] "
                        f"({a0s.get('n_items_over_refusal_hb_label_unstable_across_cells')} items label-unstable)")
        else:
            lines.append(f"Arm0 stability status: {a0s.get('status')}")
        lines.append("")
    jc = analysis.get("judge_cost", {})
    lines.append(f"**Judge cost**: main ledger ${jc.get('main_ledger_usd', 0):.4f} + test_judge ledger "
                f"${jc.get('test_judge_ledger_usd', 0):.4f} = **${jc.get('total_usd', 0):.4f}** total")
    lines.append("")
    lines.append("## Three-model comparison (activation and causal structure)")
    tmc = analysis.get("three_model_comparison", {})
    tmodels = [m for m in analysis.get("models", []) if m in tmc and m != "smoke"] or \
        [m for m in tmc if m != "_cross_model_direction_cosines_by_band"]
    if tmodels:
        rows_spec = [
            ("arm0 refused_harm (genP, source band)", lambda e: (
                f"{e['arm0_baseline_rates_genP'].get('refused_harm', {}).get('rate'):.3f} "
                f"[{e['arm0_baseline_rates_genP'].get('refused_harm', {}).get('ci_lo'):.3f},"
                f"{e['arm0_baseline_rates_genP'].get('refused_harm', {}).get('ci_hi'):.3f}] "
                f"({e['arm0_baseline_rates_genP'].get('source_band')})"
                if e.get("arm0_baseline_rates_genP", {}).get("status") == "OK"
                and e["arm0_baseline_rates_genP"]["refused_harm"].get("rate") is not None else "NOT_RUN")),
            ("arm0 harmful_compliance_harm (genP)", lambda e: (
                f"{e['arm0_baseline_rates_genP']['harmful_compliance_harm'].get('rate')}"
                if e.get("arm0_baseline_rates_genP", {}).get("status") == "OK" else "NOT_RUN")),
            ("arm0 safe_engagement_harm (genP)", lambda e: (
                f"{e['arm0_baseline_rates_genP']['safe_engagement_harm'].get('rate')}"
                if e.get("arm0_baseline_rates_genP", {}).get("status") == "OK" else "NOT_RUN")),
            ("arm0 over_refusal_hb (genP)", lambda e: (
                f"{e['arm0_baseline_rates_genP']['over_refusal_hb'].get('rate')}"
                if e.get("arm0_baseline_rates_genP", {}).get("status") == "OK" else "NOT_RUN")),
            ("arm0 RD/G1/T1ref harm-mean (P_arm0)", lambda e: (
                f"{e['arm0_forward_means_P_arm0'].get('RD_harm_mean')}/"
                f"{e['arm0_forward_means_P_arm0'].get('G1_harm_mean')}/"
                f"{e['arm0_forward_means_P_arm0'].get('T1ref_harm_mean')}"
                if e.get("arm0_forward_means_P_arm0", {}).get("status") == "OK" else "NOT_RUN")),
            ("BL1_easy / BL1_hard (arm0, stimro)", lambda e: (
                f"{e['BL1_arm0_stimro'].get('BL1_easy')}/{e['BL1_arm0_stimro'].get('BL1_hard')}"
                if isinstance(e.get("BL1_arm0_stimro"), dict) and "BL1_easy" in e["BL1_arm0_stimro"] else "NOT_RUN")),
            ("l_star / d_hard(l_star) / n6_best", lambda e: f"{e.get('l_star')} / {e.get('d_hard_at_lstar')} / "
                                                            f"{e.get('n6_best')}"),
        ]
        lines.append("| metric | " + " | ".join(tmodels) + " |")
        lines.append("|---|" + "---|" * len(tmodels))
        for label, fn in rows_spec:
            vals = []
            for m in tmodels:
                e = tmc.get(m, {})
                try:
                    vals.append(str(fn(e)) if e.get("status") == "OK" else "NOT_RUN")
                except Exception:  # noqa: BLE001 - a formatting slip must never break the table
                    vals.append("n/a")
            lines.append(f"| {label} | " + " | ".join(vals) + " |")
        lines.append("")
        lines.append("### 8a. Site-P decodability AUROC by band, per model")
        band_union = sorted({b for m in tmodels for b in tmc.get(m, {}).get("decodability_P_auroc_by_band", {})},
                            key=lambda x: (len(x), x))
        lines.append("| model | " + " | ".join(band_union) + " |")
        lines.append("|---|" + "---|" * len(band_union))
        for m in tmodels:
            d = tmc.get(m, {}).get("decodability_P_auroc_by_band", {})
            lines.append(f"| {m} | " + " | ".join(_fmt_num(d.get(b), "{:.3f}") for b in band_union) + " |")
        lines.append("")
        lines.append("### 8b. Cross-model direction cosines by band (mean over each band's layers)")
        cmc = tmc.get("_cross_model_direction_cosines_by_band", {})
        if cmc:
            lines.append("| pair / direction | " + " | ".join(bands_of(tmodels[0]).keys()) + " |")
            lines.append("|---|" + "---|" * len(bands_of(tmodels[0]).keys()))
            for key in sorted(cmc.keys()):
                v = cmc[key]
                if not isinstance(v, dict) or ("status" in v and v.get("status") == "NOT_RUN"):
                    lines.append(f"| {key} | " + " | ".join(["NOT_RUN"] * len(bands_of(tmodels[0]))) + " |")
                    continue
                row_vals = [_fmt_num(v.get(b), "{:.3f}") for b in bands_of(tmodels[0]).keys()]
                lines.append(f"| {key} | " + " | ".join(row_vals) + " |")
        else:
            lines.append("NOT_RUN: cross-model cosines require directions_disk_<m>.npz / directions_<m>.npz "
                        "for at least two of instruct/saferl/abliterated")
        lines.append("")
    else:
        lines.append("NOT_RUN: fewer than 1 model with status OK")
    lines.append("")
    lines.append("## Two-sidedness (SafeRL - instruct DiD)")
    ts = analysis.get("two_sidedness", {})
    lines.append(f"status: {'OK' if 'per_band' in ts else ts.get('status', 'NOT_RUN')}")
    lines.append("")
    lines.append("### Two-sidedness, global ablation (genG, EXPLORATORY, T3 disambiguation)")
    tga = ts.get("two_sidedness_global_ablation", {}) if isinstance(ts, dict) else {}
    per_bs = tga.get("per_band_set", {})
    if per_bs:
        lines.append("| band-set | F_refused_harm DiD | F_over_refusal DiD | N6_over_refusal DiD |")
        lines.append("|---|---|---|---|")
        for bk in sorted(per_bs, key=lambda x: (x != "ALL", x)):
            d = per_bs[bk]

            def fmt(lab):
                c = d.get(lab, {})
                if c.get("status") != "OK":
                    return "NOT_RUN"
                return f"{c['did']:+.3f} [{c['ci_lo']:+.3f},{c['ci_hi']:+.3f}]"

            lines.append(f"| {bk} | {fmt('F_refused_harm')} | {fmt('F_over_refusal')} | {fmt('N6_over_refusal')} |")
    else:
        lines.append("NOT_RUN: genG cells absent for instruct and/or saferl")
    lines.append("")
    lines.append("## Cell registry")
    for m, entry in analysis.get("cell_registry", {}).items():
        lines.append(f"### {m}")
        if entry.get("status") == "NOT_RUN":
            lines.append(f"NOT_RUN: {entry.get('reason')}")
        else:
            lines.append(f"l_star={entry.get('l_star')} (band {entry.get('band_containing_l_star')}); "
                        f"n6_best={entry.get('n6_best')} (band {entry.get('band_containing_n6_best')})")
        lines.append("")
    return "\n".join(lines) + "\n"


# ================================================================================================
# main
# ================================================================================================
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="instruct,saferl",
                    help="comma list, e.g. instruct,saferl[,abliterated], or 'smoke'")
    ap.add_argument("--out-prefix", default="", help="prefix for the three output files, e.g. smoke_")
    ap.add_argument("--hook-hash", default=None, help="override; default reads run_status_<model>.json, "
                                                       "else the newest hash present among that model's cells")
    a = ap.parse_args()
    setup_logging("analyze" + (f"_{a.out_prefix.rstrip('_')}" if a.out_prefix else ""))
    models = ["smoke"] if a.models.strip() == "smoke" else [m.strip() for m in a.models.split(",") if m.strip()]
    hook_hash = resolve_hook_hash(models, a.hook_hash)
    logger.info(f"analysing models={models} hook_hash={hook_hash!r}")
    for m in models:
        HOOK_HASH_BY_MODEL[m] = hook_hash
    items = jload(ASSETS / "items.json")
    t0 = time.time()
    per_model = {}
    for m in models:
        logger.info(f"--- {m} ---")
        try:
            res = analyze_model(m, items)
        except Exception as e:  # noqa: BLE001 - a single model's failure must never crash the run
            logger.exception(f"{m}: analyze_model raised {e!r}")
            res = {"status": "NOT_RUN", "reason": f"analyze_model raised {e!r}"}
        try:
            res["unit_hooks"] = analyze_unit_hooks(m)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"{m}: analyze_unit_hooks raised {e!r}")
            res["unit_hooks"] = {"status": "NOT_RUN", "reason": f"raised {e!r}"}
        per_model[m] = res
        logger.info(f"{m}: status={res.get('status')} elapsed={time.time() - t0:.1f}s")

    two_sid = two_sidedness(per_model)
    reg = cell_registry(per_model)
    cross_dirs = cross_model_direction_cosines(models)
    tmc = three_model_comparison(per_model, models, items)
    prereg_sha = (WS / "prereg.sha256").read_text().strip() if (WS / "prereg.sha256").exists() else None
    gpu_sha = (WS / "prereg_gpu_addendum.sha256").read_text().strip() \
        if (WS / "prereg_gpu_addendum.sha256").exists() else None
    deviations = jload(RESULTS / "deviations.json") if (RESULTS / "deviations.json").exists() else []

    analysis = {
        "generated_utc": utc_now(), "hook_hash": hook_hash, "models": models,
        "prereg": {"prereg_sha256": prereg_sha, "prereg_gpu_addendum_sha256": gpu_sha},
        "deviations": deviations,
        "per_model": per_model,
        "two_sidedness": two_sid,
        "cell_registry": reg,
        "direction_cosines_cross_model": cross_dirs,
        "three_model_comparison": tmc,
        "judge_cost": total_judge_cost(),
        "runtime_seconds": time.time() - t0,
    }
    # strip the underscore-prefixed raw item-level scratch dicts (large, internal-only) before writing
    for m, res in analysis["per_model"].items():
        for k in list(res.keys()):
            if k.startswith("_diD_raw"):
                res.pop(k, None)

    out_json = RESULTS / f"{a.out_prefix}analysis.json"
    jdump(out_json, analysis)
    logger.info(f"wrote {out_json}")

    md = build_summary_tables(analysis)
    md_path = RESULTS / f"{a.out_prefix}summary_tables.md"
    md_path.write_text(md)
    logger.info(f"wrote {md_path}")

    method_out = build_method_out(analysis)
    mo_path = WS / f"{a.out_prefix}method_out.json"
    jdump(mo_path, method_out)
    logger.info(f"wrote {mo_path}")

    logger.info(f"DONE in {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
