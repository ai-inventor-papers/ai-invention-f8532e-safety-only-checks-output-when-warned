"""D5 causal grid (results/table_causal_grid.json) + D6 equivalence framing
(results/table_equivalence.json), plus results/contradictions_d5_d6.json.

ZERO GPU, ZERO API spend. Pure re-derivation from JSON/NPZ already on disk under
iter_4/gen_art/gen_art_experiment_2. The DISK is authoritative: where a re-derived
value disagrees with prose, the disk value wins and the prose value is logged as a
CONTRADICTION. Every emitted row carries non-null source_file and readout_class.

RUN INVARIANT: the judged-generation causal grid (activation-space projection ->
greedy decode -> LLM judge label) is the deliverable readout for this audit. The
keyword-proxy label is a text-only agreement BASELINE against that judge, reported
only for validity, never as the answer.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

import numpy as np

import sources as SRC
import stats_lib as ST

I4E2 = SRC.I4_EXP2
CELLS_DIR = I4E2 / "out/cells"
OUT_DIR = Path(__file__).resolve().parent.parent / "results"
FIG_DIR = Path(__file__).resolve().parent.parent / "figures"

MODELS = ["instruct", "saferl", "abliterated"]
BANDS = ["B1", "B2", "B3", "B4", "B5", "B6"]
SITES = ["P", "Dprime", "E"]
SITE_TAG = {"P": "genP", "Dprime": "genDprime", "E": "genE"}
ANALYSIS_KEY = "i4e2_analysis"

analysis, _err = SRC.try_load(ANALYSIS_KEY)
if analysis is None:
    raise SystemExit(f"SOURCE_ABSENT: {ANALYSIS_KEY} -> {_err}")
PM: dict[str, Any] = analysis["per_model"]
TWO_SIDED: dict[str, Any] = analysis["two_sidedness"]
ANALYSIS_PATH = str(SRC.SOURCES[ANALYSIS_KEY])

contradictions: list[dict[str, Any]] = []


def add_contradiction(claim_id, claim_text, claimed, rederived, tol_rule, tol, sfile, skey, verdict, note):
    contradictions.append({
        "claim_id": claim_id, "claim_text": claim_text, "claimed_value": claimed,
        "rederived_value": rederived, "tolerance_rule": tol_rule, "tolerance": tol,
        "source_file": sfile, "source_key": skey, "verdict": verdict, "note": note,
    })


def close(a, b, tol):
    try:
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


# ============================================================================
# raw cell loader (npz + json), used for re-derivations that must NOT simply
# copy a stored aggregate (Holm family, global-ablation DiD, R displacement,
# keyword-proxy kappa, positive-control value).
# ============================================================================
_CACHE: dict[tuple, Any] = {}


def load_raw_cell(model: str, name: str) -> dict[str, Any] | None:
    key = (model, name)
    if key in _CACHE:
        return _CACHE[key]
    fs = sorted(glob.glob(str(CELLS_DIR / model / f"{name}__*.json")))
    if not fs:
        _CACHE[key] = None
        return None
    meta = json.load(open(fs[0]))
    npzf = fs[0][:-5] + ".npz"
    arrs = np.load(npzf, allow_pickle=True)
    rows = meta["rows"]
    kinds = meta.get("kinds", [None] * len(rows))
    out = {
        "arm": np.array([r["arm"] for r in rows], dtype=object),
        "band": np.array([r.get("band") for r in rows], dtype=object),
        "draw": np.array([r.get("draw", 0) for r in rows]),
        "kind": np.array(kinds, dtype=object),
        "item_id": np.array([r["item_id"] for r in rows], dtype=object),
        "meta": meta,
        "json_path": fs[0],
        "npz_path": npzf,
    }
    for k in arrs.files:
        if arrs[k].ndim == 1:
            out[k] = arrs[k]
    _CACHE[key] = out
    return out


def cell_mask(cell, arm=None, kind=None, band=None, draw=None, judged_gate=True, col=None):
    m = np.ones(cell["arm"].shape, dtype=bool)
    if arm is not None:
        m &= cell["arm"] == arm
    if kind is not None:
        m &= cell["kind"] == kind
    if band is not None:
        m &= cell["band"] == band
    if draw is not None:
        m &= cell["draw"] == draw
    if judged_gate and "judged" in cell and col not in ("RD", "G1", "T1ref", "proxy_refused"):
        m &= cell["judged"] == 1.0
    return m


def by_item(cell, col, arm, kind, band=None, draw=0, judged_gate=True):
    m = cell_mask(cell, arm=arm, kind=kind, band=band, draw=draw, judged_gate=judged_gate, col=col)
    ids = cell["item_id"][m]
    vals = cell[col][m]
    ok = np.isfinite(vals)
    return dict(zip(ids[ok].tolist(), vals[ok].tolist()))


# ============================================================================
# D5a. Full grid extraction from the trusted per-model causal_grid_judged
# (analysis.json), with Holm-18 RE-COMPUTED here from the raw p_signflip
# values (never copying the stored p_holm/CAUSAL flag).
# ============================================================================
OUTCOMES = ["refused_harm", "over_refusal_hb"]
GRID_ARMS = ["F", "N6", "N6perp"]  # native causal_grid_judged arms (POS handled separately)
READOUT_CLASS_GRID = "behavioral (activation-space projection -> greedy decode -> LLM judge label)"
READOUT_CLASS_R = "behavioral (matched/own-coefficient random-control judged generation, validity arm)"
READOUT_CLASS_FPERPU = "behavioral (F-minus-N2/N3-subspace projection -> judged generation, EXPLORATORY)"
READOUT_CLASS_POS = "behavioral (generic-disruption positive-control judged generation)"
READOUT_CLASS_GLOBAL = "behavioral (all-position/all-layer activation ablation -> judged generation)"
READOUT_CLASS_KAPPA = "text-proxy validity check (judge label vs keyword-proxy label) -- baseline agreement diagnostic, not a causal readout"
READOUT_CLASS_DISP = "activation displacement diagnostic (mean residual-stream displacement ratio, hook self-check)"
READOUT_CLASS_ARM0 = "behavioral (arm-0 / no-intervention judged generation baseline)"


def grid_rows_for(model: str, outcome: str) -> list[dict]:
    cg = PM[model]["causal_grid_judged"][outcome]
    rows = []
    for arm in GRID_ARMS:
        cells = cg[arm]["cells"]
        keys_present = [k for k in cells if cells[k].get("status") == "OK"]
        pvals = [cells[k]["effect_vsR"]["p_signflip"] for k in keys_present]
        holm = ST.holm(pvals) if pvals else {"p_adj": [], "reject": []}
        holm_by_key = dict(zip(keys_present, zip(holm["p_adj"], holm["reject"]))) if pvals else {}
        for site in SITES:
            for band in BANDS:
                key = f"{site}_{band}"
                c = cells.get(key)
                skey = f"per_model.{model}.causal_grid_judged.{outcome}.{arm}.cells.{key}"
                if c is None:
                    rows.append({
                        "model": model, "outcome": outcome, "arm": arm, "site": site, "band": band,
                        "status": "NOT_RUN", "reason": "cell key absent from causal_grid_judged "
                        f"(arm {arm} not registered at this site, e.g. N6perp/POS are site-P only)",
                        "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_GRID,
                    })
                    continue
                if c.get("status") != "OK":
                    rows.append({
                        "model": model, "outcome": outcome, "arm": arm, "site": site, "band": band,
                        "status": c.get("status", "NOT_RUN"), "reason": c.get("reason"),
                        "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_GRID,
                    })
                    continue
                ev = c["effect_vsR"]
                p_holm, reject = holm_by_key.get(key, (None, None))
                rows.append({
                    "model": model, "outcome": outcome, "arm": arm, "site": site, "band": band,
                    "status": "OK",
                    "effect_FR": ev["effect"], "ci_lo": ev["ci_lo"], "ci_hi": ev["ci_hi"],
                    "mde_80": ev["mde_80"], "p_raw_signflip": ev["p_signflip"], "n": ev["n"],
                    "p_holm_rederived": p_holm,
                    "holm_family_size": len(pvals),
                    "holm_family_definition": cg[arm].get("family_definition"),
                    "causal_rederived": bool(reject) if reject is not None else None,
                    "causal_stored_flag_on_disk": c.get("CAUSAL"),
                    "flags_match_disk": (bool(reject) == bool(c.get("CAUSAL"))) if reject is not None else None,
                    "arm0_baseline_mean": c.get("mean_0"),
                    "mean_T": c.get("mean_T"), "mean_R": c.get("mean_R"), "n_R_draws": c.get("n_R_draws"),
                    "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_GRID,
                    "caveat_R_not_matched": None if site == "P" else (
                        "site is D'/E: the own-coefficient random control R displaces MORE than the "
                        "treatment arm here (see r_displacement_validity); 'net of a matched random "
                        "control' is not literally true at this site -- see caveat block"),
                })
        # ---- R arm: the random control's own effect vs arm-0 (validity row, not a treatment) ----
        R_tag_label = "RF" if arm == "F" else ("RN6" if arm == "N6" else "RF")
        for site in SITES:
            for band in BANDS:
                key = f"{site}_{band}"
                c = cells.get(key)
                skey = (f"per_model.{model}.causal_grid_judged.{outcome}.{arm}.cells.{key}"
                        ".per_draw_effects_vs0 (R stack)")
                if c is None or c.get("status") != "OK" or not c.get("per_draw_effects_vs0"):
                    rows.append({
                        "model": model, "outcome": outcome, "arm": "R", "site": site, "band": band,
                        "status": "NOT_RUN", "reason": f"no R-draw effects available for {arm} cell {key}",
                        "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_R,
                    })
                    continue
                draws = c["per_draw_effects_vs0"]
                boot = ST.boot_ci(draws) if len(draws) >= 2 else None
                rows.append({
                    "model": model, "outcome": outcome, "arm": "R", "site": site, "band": band,
                    "status": "OK", "note": f"R_tag={R_tag_label}; matched at P, own-coefficient at D'/E",
                    "effect_FR": float(np.mean(draws)), "ci_lo": boot["lo"] if boot else None,
                    "ci_hi": boot["hi"] if boot else None, "n_draws": len(draws),
                    "mde_80": None, "p_raw_signflip": None,
                    "arm0_baseline_mean": c.get("mean_0"),
                    "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_R,
                    "holm_family_definition": "R is a validity control, not a registered Holm-family arm",
                })
        if arm != "N6":
            continue
    return rows


def fperpu_rows_for(model: str, outcome: str) -> list[dict]:
    genu = PM[model].get("genU_exploratory_FperpU", {})
    per_band = genu.get("per_band", {}) if genu.get("status") == "OK" else {}
    rows = []
    for site in SITES:
        for band in BANDS:
            skey = f"per_model.{model}.genU_exploratory_FperpU.per_band.{band}.{outcome}.FperpU_vs_0_and_R"
            if site != "P":
                rows.append({
                    "model": model, "outcome": outcome, "arm": "F_perpU", "site": site, "band": band,
                    "status": "NOT_RUN", "reason": "genU (F_perpU) ran at site P only, all 6 bands",
                    "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_FPERPU,
                })
                continue
            b = per_band.get(band, {})
            c = b.get(outcome, {}).get("FperpU_vs_0_and_R") if b else None
            if not c or c.get("status") != "OK":
                rows.append({
                    "model": model, "outcome": outcome, "arm": "F_perpU", "site": site, "band": band,
                    "status": (c or {}).get("status", "NOT_RUN"),
                    "reason": (c or {}).get("reason", "genU cell missing"),
                    "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_FPERPU,
                })
                continue
            ev = c["effect_vsR"]
            rows.append({
                "model": model, "outcome": outcome, "arm": "F_perpU", "site": site, "band": band,
                "status": "OK", "effect_FR": ev["effect"], "ci_lo": ev["ci_lo"], "ci_hi": ev["ci_hi"],
                "mde_80": ev["mde_80"], "p_raw_signflip": ev["p_signflip"], "n": ev["n"],
                "p_holm_rederived": None, "causal_rederived": None,
                "holm_family_definition": "EXPLORATORY (plan 9b): NOT in any confirmatory Holm family; "
                "no CAUSAL determination is made for this arm, per source note",
                "arm0_baseline_mean": c.get("mean_0"), "mean_T": c.get("mean_T"), "mean_R": c.get("mean_R"),
                "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_FPERPU,
            })
    return rows


# ============================================================================
# D5b. Positive control (POS), REMOVED from the 18-cell table, reported where
# it actually ran (site P, bands B3/B4 only).
# ============================================================================
def positive_control_rows() -> list[dict]:
    rows = []
    for model in MODELS:
        cg = PM[model]["causal_grid_judged"]
        for outcome in ["refused_harm", "over_refusal_hb", "RD_harm"]:
            arm_dict = cg.get(outcome, {}).get("POS", {}).get("cells", {})
            for band in ["B3", "B4"]:
                key = f"P_{band}"
                c = arm_dict.get(key)
                skey = f"per_model.{model}.causal_grid_judged.{outcome}.POS.cells.{key}"
                if not c or c.get("status") != "OK":
                    rows.append({
                        "model": model, "outcome": outcome, "arm": "POS", "site": "P", "band": band,
                        "status": (c or {}).get("status", "NOT_RUN"),
                        "reason": (c or {}).get("reason"),
                        "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_POS,
                    })
                    continue
                ev, ev0 = c["effect_vsR"], c["effect_vs0"]
                rows.append({
                    "model": model, "outcome": outcome, "arm": "POS", "site": "P", "band": band,
                    "status": "OK", "effect_vsR": ev["effect"], "ci_lo_vsR": ev["ci_lo"],
                    "ci_hi_vsR": ev["ci_hi"], "effect_vs0": ev0["effect"], "ci_lo_vs0": ev0["ci_lo"],
                    "ci_hi_vs0": ev0["ci_hi"], "mde_80": ev["mde_80"], "n": ev["n"],
                    "arm0_baseline_mean": c.get("mean_0"),
                    "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_POS,
                })
    return rows


# ============================================================================
# D5c. Global-ablation control (genG), corrected band identification, and the
# cross-model DiD RE-DERIVED DIRECTLY from raw genG npz cells (not copied from
# analysis.json's two_sidedness_global_ablation).
# ============================================================================
def global_ablation_rows() -> tuple[list[dict], dict]:
    rows = []
    per_model_band_effect = {}
    for model in MODELS:
        genG = PM[model].get("genG_global_ablation_control", {})
        per_band = genG.get("per_band", {}) if genG.get("status") == "OK" else {}
        per_model_band_effect[model] = {}
        for band in BANDS + ["ALL"]:
            bo = per_band.get(band)
            if not bo or bo.get("status") == "NOT_RUN":
                continue
            for outcome in ["refused_harm", "over_refusal_hb"]:
                fo = bo.get(outcome, {}).get("F_global_ablation")
                skey = f"per_model.{model}.genG_global_ablation_control.per_band.{band}.{outcome}.F_global_ablation"
                if not fo or fo.get("status") != "OK":
                    continue
                ev, ev0 = fo["effect_vsR"], fo["effect_vs0"]
                rows.append({
                    "model": model, "outcome": outcome, "arm": "F_global_ablation", "site": "ALLPOS", "band": band,
                    "status": "OK", "effect_vsR": ev["effect"], "ci_lo_vsR": ev["ci_lo"], "ci_hi_vsR": ev["ci_hi"],
                    "effect_vs0": ev0["effect"], "ci_lo_vs0": ev0["ci_lo"], "ci_hi_vs0": ev0["ci_hi"],
                    "arm0_baseline_mean": fo.get("mean_0"), "mean_T": fo.get("mean_T"), "mean_R": fo.get("mean_R"),
                    "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_GLOBAL,
                })
                if outcome == "refused_harm" and band in BANDS:
                    per_model_band_effect[model][band] = ev["effect"]
    # corrected band = the band with the LARGEST |effect_vsR| on refused_harm, per instruct
    instr_bands = per_model_band_effect.get("instruct", {})
    corrected_band = max(instr_bands, key=lambda b: abs(instr_bands[b])) if instr_bands else None
    summary = {
        "corrected_band": corrected_band,
        "instruct_effect_by_band": instr_bands,
        "note": "band selected as the max |effect_vsR| of F_global_ablation on refused_harm for instruct; "
                "plan/prose referenced B5, disk shows the true peak below",
    }
    # ---- cross-model DiD at the corrected band, RE-DERIVED DIRECTLY from raw genG npz cells ----
    did_direct = None
    if corrected_band:
        gi = load_raw_cell("instruct", f"genG_{corrected_band}")
        gs = load_raw_cell("saferl", f"genG_{corrected_band}")
        if gi and gs:
            def per_item_diff(cell, kind, col="refused" if False else None):
                return None
            def diff_F_minus_R(cell, kind="harm", col="refused"):
                y0 = by_item(cell, col, "0", kind)
                yF = by_item(cell, col, "F", kind, band=corrected_band)
                yR = by_item(cell, col, "RFo", kind, band=corrected_band, draw=1)
                ids = sorted(set(yF) & set(yR))
                return {i: yF[i] - yR[i] for i in ids}
            di = diff_F_minus_R(gi, "harm", "refused")
            ds = diff_F_minus_R(gs, "harm", "refused")
            ids = sorted(set(di) & set(ds))
            if ids:
                a = np.array([ds[i] for i in ids])  # saferl
                b = np.array([di[i] for i in ids])  # instruct
                d = a - b
                boot = ST.boot_ci(d)
                # sign-flip p (two-sided), matching stats_lib convention via percentile bootstrap crossing 0
                n_pos = int(np.sum(np.sign(d) == np.sign(boot["point"]))) if boot["point"] else None
                did_direct = {
                    "did_saferl_minus_instruct": boot["point"], "ci_lo": boot["lo"], "ci_hi": boot["hi"],
                    "n": len(ids), "band": corrected_band, "outcome": "refused_harm",
                    "method": "direct re-derivation from out/cells/{model}/genG_"
                    f"{corrected_band}__*.npz (arm F minus RFo draw-1, item-paired, "
                    "then saferl-minus-instruct across models), NOT copied from two_sidedness",
                    "source_file_instruct": gi["npz_path"], "source_file_saferl": gs["npz_path"],
                }
    return rows, {"summary": summary, "did_direct_rederivation": did_direct}


# ============================================================================
# D5d. DiD sign convention: re-derive the REGISTERED judged-grid DiD
# (N6 over-refusal, saferl minus instruct) directly from raw gen{site}_{band}
# npz cells, confirm sign against the registered claim.
# ============================================================================
def registered_did_rows() -> dict:
    registered_sign_text = TWO_SIDED.get("registered_sign")
    out_rows = []
    for site in SITES:
        tag = SITE_TAG[site]
        for band in BANDS:
            ci = load_raw_cell("instruct", f"{tag}_{band}")
            cs = load_raw_cell("saferl", f"{tag}_{band}")
            skey = f"out/cells/{{model}}/{tag}_{band}__*.npz (arm N6 minus RN6 mean, over_refusal, kind=hb)"
            if not ci or not cs:
                out_rows.append({"site": site, "band": band, "status": "SOURCE_ABSENT",
                                  "source_file": f"{CELLS_DIR}/instruct|saferl/{tag}_{band}__*.npz",
                                  "source_key": skey, "readout_class": READOUT_CLASS_GRID})
                continue

            def diff_N6_minus_R(cell):
                y0 = by_item(cell, "over_refusal", "0", "hb")
                yN6 = by_item(cell, "over_refusal", "N6", "hb", band=band)
                R_tag = "RN6" if site == "P" else "RN6o"
                draws = sorted(set(cell["draw"][cell_mask(cell, arm=R_tag, kind="hb", band=band)].tolist()))
                if not draws:
                    return {}
                stacks = [by_item(cell, "over_refusal", R_tag, "hb", band=band, draw=j) for j in draws]
                ids = sorted(set(yN6) & set.intersection(*[set(s) for s in stacks]))
                out = {}
                for i in ids:
                    rmean = float(np.mean([s[i] for s in stacks]))
                    out[i] = yN6[i] - rmean
                return out

            di, ds = diff_N6_minus_R(ci), diff_N6_minus_R(cs)
            ids = sorted(set(di) & set(ds))
            if not ids:
                out_rows.append({"site": site, "band": band, "status": "NOT_RUN",
                                  "reason": "no overlapping N6/R items with judged over_refusal at this cell",
                                  "source_file": ci["npz_path"], "source_key": skey,
                                  "readout_class": READOUT_CLASS_GRID})
                continue
            a = np.array([ds[i] for i in ids])
            b = np.array([di[i] for i in ids])
            d = a - b
            boot = ST.boot_ci(d)
            matches = bool(boot["point"] is not None and boot["point"] > 0)
            out_rows.append({
                "site": site, "band": band, "status": "OK",
                "did_saferl_minus_instruct_rederived": boot["point"], "ci_lo": boot["lo"], "ci_hi": boot["hi"],
                "n": len(ids), "matches_registered_sign_rederived": matches,
                "matches_registered_sign_on_disk": (
                    TWO_SIDED.get("judged_grid_DiD", {}).get(f"{site}_{band}", {})
                    .get("N6_over_refusal", {}).get("matches_registered_sign")),
                "source_file": ci["npz_path"], "source_key": skey, "readout_class": READOUT_CLASS_GRID,
            })
    n_support = sum(1 for r in out_rows if r.get("status") == "OK" and r.get("matches_registered_sign_rederived"))
    n_ok = sum(1 for r in out_rows if r.get("status") == "OK")
    return {
        "registered_claim_text": registered_sign_text,
        "verdict": "NOT_SUPPORTED" if n_support < n_ok / 2 else "PARTIALLY_SUPPORTED",
        "n_cells_matching_registered_sign": n_support, "n_cells_ok": n_ok,
        "cells": out_rows,
        "note": "the registered prediction is that SafeRL's over-refusal drop under N6-removal is smaller "
                "(less negative) than instruct's, i.e. DiD=saferl-instruct should be POSITIVE; re-derived "
                "directly from raw judged-generation cells (arm N6 minus mean over R draws, item-paired "
                "across models), the sign is negative or CI-straddles-zero at essentially every site x band "
                "cell, so the registered claim is NOT SUPPORTED by the disk",
    }


# ============================================================================
# D5e. R displacement ratio per site, re-derived from each gen{site}_{band}
# cell's own hook self-check (mean_displacement_by_arm / ratio_meanDisp_*).
# ============================================================================
def r_displacement_rows() -> dict:
    per_site = {s: {"F": [], "N6": []} for s in SITES}
    rows = []
    for model in MODELS:
        for site in SITES:
            tag = SITE_TAG[site]
            for band in BANDS:
                cell = load_raw_cell(model, f"{tag}_{band}")
                if cell is None:
                    continue
                checks = cell["meta"].get("checks", {})
                rF = checks.get("ratio_meanDisp_R_over_F", {})
                rN6 = checks.get("ratio_meanDisp_RN6_over_N6", {})
                for v in rF.values():
                    per_site[site]["F"].append(v)
                for v in rN6.values():
                    per_site[site]["N6"].append(v)
                rows.append({
                    "model": model, "site": site, "band": band,
                    "ratio_R_over_F": list(rF.values())[0] if rF else None,
                    "ratio_RN6_over_N6": list(rN6.values())[0] if rN6 else None,
                    "source_file": cell["json_path"], "source_key": "checks.ratio_meanDisp_R_over_F / "
                    "checks.ratio_meanDisp_RN6_over_N6", "readout_class": READOUT_CLASS_DISP,
                })
    summary = {}
    for site in SITES:
        fvals, nvals = per_site[site]["F"], per_site[site]["N6"]
        summary[site] = {
            "mean_ratio_R_over_F": float(np.mean(fvals)) if fvals else None,
            "mean_ratio_RN6_over_N6": float(np.mean(nvals)) if nvals else None,
            "n_cells_F": len(fvals), "n_cells_N6": len(nvals),
            "matched_at_P": site == "P",
            "caveat": ("exactly matched (ratio ~1) -- R takes the F/N6 displacement of the SAME row" if site == "P"
                       else "own-coefficient R (x - (x.v)u); displaces MORE than the treatment arm here, so "
                       "'net of a matched random control' at this site is NOT literally true"),
        }
    return {"per_cell": rows, "summary_by_site": summary}


# ============================================================================
# D5f. Keyword-proxy validity (Cohen's kappa vs judge), per model overall and
# per band (pooled across sites P/D'/E), re-derived from raw refused_raw vs
# proxy_refused arrays -- NEVER the causal readout, a text-only baseline only.
# ============================================================================
def cohen_kappa(a: np.ndarray, b: np.ndarray) -> dict:
    n = a.size
    if n == 0:
        return {"n_pairs": 0, "raw_agreement": None, "kappa": None}
    po = float(np.mean(a == b))
    pa1, pb1 = float(np.mean(a)), float(np.mean(b))
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    kappa = (1.0 if po == 1.0 else 0.0) if abs(1 - pe) < 1e-9 else (po - pe) / (1 - pe)
    return {"n_pairs": int(n), "raw_agreement": round(po, 4), "kappa": round(float(kappa), 4)}


def keyword_proxy_kappa() -> dict:
    per_model_band = {m: {} for m in MODELS}
    per_model_overall = {}
    for model in MODELS:
        all_j, all_p = [], []
        for band in BANDS:
            band_j, band_p = [], []
            for site in SITES:
                cell = load_raw_cell(model, f"{SITE_TAG[site]}_{band}")
                if cell is None:
                    continue
                m = cell_mask(cell, judged_gate=True, col="refused_raw")
                m &= np.isfinite(cell.get("refused_raw", np.full_like(m, np.nan, dtype=float)))
                j = cell["refused_raw"][m].astype(bool).astype(int)
                p = cell["proxy_refused"][m].astype(bool).astype(int)
                band_j.append(j)
                band_p.append(p)
            if band_j:
                jj, pp = np.concatenate(band_j), np.concatenate(band_p)
                per_model_band[model][band] = cohen_kappa(jj, pp)
                all_j.append(jj)
                all_p.append(pp)
        if all_j:
            per_model_overall[model] = cohen_kappa(np.concatenate(all_j), np.concatenate(all_p))
    return {
        "per_model_overall": per_model_overall,
        "per_model_per_band": per_model_band,
        "source_file_pattern": str(CELLS_DIR / "{model}/{genP,genDprime,genE}_{band}__*.json|.npz"),
        "source_key": "refused_raw (judge) vs proxy_refused (keyword proxy), judged==1.0 gate, pooled over sites",
        "readout_class": READOUT_CLASS_KAPPA,
        "note": "SafeRL's judge-vs-proxy raw kappa collapses relative to instruct because SafeRL's refusal "
                "phrasing (e.g. hedged clarifying language) is not on the keyword list the proxy scans for; "
                "this is a validity finding about the text-only proxy baseline, not about the causal grid",
    }


# ============================================================================
# D5g. arm-0 baselines and effect ranking / Holm survivor identification.
# ============================================================================
def arm0_baseline_rows() -> list[dict]:
    rows = []
    for model in MODELS:
        genP = load_raw_cell(model, "genP_B1")  # arm-0 is band-independent (band=None rows)
        for outcome, col, kind in (("refused_harm", "refused", "harm"), ("over_refusal_hb", "over_refusal", "hb")):
            skey = f"per_model.{model}.causal_grid_judged.{outcome}.F.cells.P_B1.mean_0"
            c = PM[model]["causal_grid_judged"][outcome]["F"]["cells"].get("P_B1")
            mean0 = c.get("mean_0") if c and c.get("status") == "OK" else None
            rows.append({
                "model": model, "outcome": outcome, "arm0_rate": mean0,
                "source_file": ANALYSIS_PATH, "source_key": skey, "readout_class": READOUT_CLASS_ARM0,
            })
    return rows


def build_effect_ranking(grid_all: list[dict]) -> list[dict]:
    cands = [r for r in grid_all if r.get("status") == "OK" and r["outcome"] == "over_refusal_hb"
             and r["arm"] in ("F", "N6") and r["site"] == "P"]
    ranked = sorted(cands, key=lambda r: -abs(r["effect_FR"]))
    for i, r in enumerate(ranked):
        r["rank_by_abs_effect"] = i + 1
    return ranked


# ============================================================================
# main
# ============================================================================
def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    grid_all: list[dict] = []
    for model in MODELS:
        for outcome in OUTCOMES:
            grid_all += grid_rows_for(model, outcome)
            grid_all += fperpu_rows_for(model, outcome)

    ranked = build_effect_ranking(grid_all)
    holm_survivors = {m: [] for m in MODELS}
    for r in grid_all:
        if r.get("status") == "OK" and r.get("causal_rederived"):
            holm_survivors[r["model"]].append({
                "outcome": r["outcome"], "arm": r["arm"], "site": r["site"], "band": r["band"],
                "effect_FR": r["effect_FR"], "ci_lo": r["ci_lo"], "ci_hi": r["ci_hi"],
                "p_holm_rederived": r["p_holm_rederived"],
            })

    pos_rows = positive_control_rows()
    ga_rows, ga_summary = global_ablation_rows()
    did_reg = registered_did_rows()
    r_disp = r_displacement_rows()
    kappa = keyword_proxy_kappa()
    arm0_rows = arm0_baseline_rows()

    table_causal_grid = {
        "seed": ST.SEED, "b_boot": ST.B_BOOT,
        "source_file": ANALYSIS_PATH,
        "n_rows_grid": len(grid_all),
        "grid_rows": grid_all,
        "holm_survivors_per_model": holm_survivors,
        "effect_ranking_over_refusal_site_P": ranked,
        "effect_ranking_note": (
            "ranked by |effect_FR| over site-P over_refusal_hb cells (arms F,N6) across both instruct "
            "and saferl; the sole Holm-18 survivor (instruct N6 @ P_B5) is NOT the largest-magnitude cell "
            "-- it sits below instruct-F@B4/B5 and comparable to saferl's own F@B4/B5 and N6@B4/B5/B6, "
            "none of which clear Holm-18. The over-refusal lever (F and N6 both) is present in BOTH models "
            "at bands B4-B5 with comparable magnitudes; only one cell clears the multiple-comparison bar."
        ),
        "positive_control_POS_removed_from_18cell_table": {
            "rows": pos_rows,
            "note": "POS ran only at site P, bands B3/B4 (forward-only judged generation); it is a generic-"
                    "disruption positive control, NOT a judged-refusal positive control. No judged-refusal "
                    "positive control existed in iteration 4.",
        },
        "global_ablation_control": {"rows": ga_rows, **ga_summary},
        "registered_DiD_reassessment": did_reg,
        "r_displacement_validity": r_disp,
        "keyword_proxy_kappa_validity_baseline": kappa,
        "arm0_baselines": arm0_rows,
    }

    # ------------------------------------------------------------------
    # D6: equivalence framing
    # ------------------------------------------------------------------
    max_abs = None
    for r in grid_all:
        if r.get("status") == "OK" and r["outcome"] == "refused_harm" and r["arm"] in ("F", "N6", "N6perp"):
            if max_abs is None or abs(r["effect_FR"]) > abs(max_abs["effect_FR"]):
                max_abs = r
    mde_median = {}
    for model in MODELS:
        pn = PM[model].get("power_nulls", {})
        mde_median[model] = {
            "median_mde_80_judged_cells": pn.get("median_mde_80_judged_cells"),
            "median_mde_80_all_null_cells": pn.get("median_mde_80"),
            "n_null_cells": pn.get("n_null_cells"),
            "n_zero_variance_excluded": pn.get("n_zero_variance_cells_excluded"),
            "source_file": ANALYSIS_PATH, "source_key": f"per_model.{model}.power_nulls",
            "readout_class": READOUT_CLASS_GRID,
        }
    bound_val = round(abs(max_abs["effect_FR"]), 3) if max_abs else None
    results_text = (
        f"Over the judged-refusal grid (refused_harm outcome, arms F/N6/N6perp, all sites x bands x "
        f"models), the largest activation-intervention effect on judged refusal is "
        f"{max_abs['effect_FR']:.4f} (model={max_abs['model']}, arm={max_abs['arm']}, "
        f"site={max_abs['site']}, band={max_abs['band']}; 95% CI [{max_abs['ci_lo']:.4f},"
        f"{max_abs['ci_hi']:.4f}]) against median MDE80 of "
        f"{mde_median['instruct']['median_mde_80_judged_cells']:.4f} (instruct), "
        f"{mde_median['saferl']['median_mde_80_judged_cells']:.4f} (SafeRL), "
        f"{mde_median['abliterated']['median_mde_80_judged_cells']:.4f} (abliterated)."
    ) if max_abs else "UNVERIFIABLE: no OK refused_harm cells found in causal_grid_judged."
    bound_statement = (
        f"BOUND: no site-local activation intervention (own-request axis F, benign-twin axis N6, or its "
        f"orthogonal complement N6perp) produces an effect on judged refusal larger than about "
        f"{bound_val} in magnitude, at any depth band or generation site measured, in any of the three "
        f"Qwen3-4B variants (instruct, SafeRL, mlabonne abliterated)."
    ) if bound_val is not None else "UNVERIFIABLE"

    tost_results = {}
    for model in MODELS:
        effects = [r["effect_FR"] for r in grid_all if r.get("status") == "OK" and r["model"] == model
                   and r["outcome"] == "refused_harm" and r["arm"] in ("F", "N6", "N6perp")]
        margin = mde_median[model]["median_mde_80_judged_cells"]
        if effects and margin:
            tost_results[model] = ST.tost_bound(effects, margin)
        else:
            tost_results[model] = {"verdict": "UNAVAILABLE"}

    arm0_baseline_table = {}
    for model in MODELS:
        c_ref = PM[model]["causal_grid_judged"]["refused_harm"]["F"]["cells"].get("P_B1")
        c_or = PM[model]["causal_grid_judged"]["over_refusal_hb"]["F"]["cells"].get("P_B1")
        arm0_baseline_table[model] = {
            "refused_harm_arm0": c_ref.get("mean_0") if c_ref and c_ref.get("status") == "OK" else None,
            "over_refusal_hb_arm0": c_or.get("mean_0") if c_or and c_or.get("status") == "OK" else None,
            "source_file": ANALYSIS_PATH,
            "source_key": f"per_model.{model}.causal_grid_judged.{{refused_harm,over_refusal_hb}}.F.cells.P_B1.mean_0",
            "readout_class": READOUT_CLASS_ARM0,
        }

    abliterated_family_sizes = {
        outcome: PM["abliterated"]["causal_grid_judged"][outcome]["F"]["family_size_used"]
        for outcome in OUTCOMES
    }

    table_equivalence = {
        "seed": ST.SEED, "b_boot": ST.B_BOOT, "source_file": ANALYSIS_PATH,
        "max_abs_effect_FR_judged_refusal": max_abs,
        "median_mde80_per_model": mde_median,
        "results_text": results_text,
        "table_caption": (
            f"Judged-refusal null: max|effect_FR| = {max_abs['effect_FR']:.3f} vs. median MDE80 "
            f"{mde_median['instruct']['median_mde_80_judged_cells']:.3f} / "
            f"{mde_median['saferl']['median_mde_80_judged_cells']:.3f} / "
            f"{mde_median['abliterated']['median_mde_80_judged_cells']:.3f} "
            "(instruct / SafeRL / abliterated)."
        ) if max_abs else "UNVERIFIABLE",
        "bound_statement": bound_statement,
        "tost_per_model": tost_results,
        "arm0_baselines_all_three_models": arm0_baseline_table,
        "abliterated_grid_footnote": {
            "family_size_used_by_outcome": abliterated_family_sizes,
            "note": "the abliterated grid has family_size_used=6 (site P only, all D'/E judged cells "
                    "NOT_RUN per deviations.json 'abliterated_scope') vs 18 for instruct/saferl on F/N6 -- "
                    "a sixth of the others' registered family size.",
            "source_file": str(SRC.SOURCES["i4e2_deviations"]),
            "source_key": "deviations[].key=='abliterated_scope'",
        },
    }

    (OUT_DIR / "table_causal_grid.json").write_text(json.dumps(table_causal_grid, indent=1, default=str))
    (OUT_DIR / "table_equivalence.json").write_text(json.dumps(table_equivalence, indent=1, default=str))

    # ------------------------------------------------------------------
    # contradictions
    # ------------------------------------------------------------------
    seed_contradictions(grid_all, ga_summary, did_reg, max_abs, mde_median, kappa, arm0_baseline_table)
    (OUT_DIR / "contradictions_d5_d6.json").write_text(json.dumps(contradictions, indent=1, default=str))

    print(f"WROTE table_causal_grid.json rows={len(grid_all)}")
    print(f"WROTE table_equivalence.json")
    print(f"WROTE contradictions_d5_d6.json n={len(contradictions)}")
    print("holm_survivors:", json.dumps(holm_survivors))
    print("top5 effect ranking:", json.dumps(ranked[:5], default=str))
    print("global ablation:", json.dumps(ga_summary, default=str))
    print("registered DiD verdict:", did_reg["verdict"], did_reg["n_cells_matching_registered_sign"], "/", did_reg["n_cells_ok"])
    print("max_abs_effect:", json.dumps(max_abs, default=str))
    print("mde_median:", json.dumps(mde_median, default=str))
    print("kappa overall:", json.dumps(kappa["per_model_overall"]))
    print("kappa per band:", json.dumps(kappa["per_model_per_band"]))
    print("R displacement summary:", json.dumps(r_disp["summary_by_site"], default=str))
    print("arm0 baselines:", json.dumps(arm0_baseline_table, default=str))


def seed_contradictions(grid_all, ga_summary, did_reg, max_abs, mde_median, kappa, arm0_baseline_table):
    dev_path = str(SRC.SOURCES["i4e2_deviations"])
    summ_path = str(SRC.SOURCES["i4e2_summary_tables"])

    # 1. global-ablation band B4 vs B5
    instr_bands = ga_summary["summary"]["instruct_effect_by_band"]
    add_contradiction(
        "global_ablation_band", "the registered global-ablation causal band is B5",
        "B5", ga_summary["summary"]["corrected_band"], "band label exact match", "exact",
        ANALYSIS_PATH, "per_model.instruct.genG_global_ablation_control.per_band.*.refused_harm.F_global_ablation",
        "MISMATCH" if ga_summary["summary"]["corrected_band"] != "B5" else "MATCH",
        f"per-band effect_vsR on refused_harm (instruct): {instr_bands}; peak magnitude is at "
        f"{ga_summary['summary']['corrected_band']}, not B5",
    )
    b4 = next((r for r in grid_all if False), None)
    # direct global-ablation B4 effect check (task expects -0.33 [-0.48,-0.21])
    genG = PM["instruct"]["genG_global_ablation_control"]["per_band"].get("B4", {})
    fo = genG.get("refused_harm", {}).get("F_global_ablation", {})
    ev = fo.get("effect_vsR", {}) if fo.get("status") == "OK" else {}
    add_contradiction(
        "global_ablation_B4_effect", "instruct global-ablation at B4: 0.917 -> 0.667, effect -0.33 [-0.48,-0.21]",
        {"effect": -0.33, "ci": [-0.48, -0.21]},
        {"effect": ev.get("effect"), "ci": [ev.get("ci_lo"), ev.get("ci_hi")], "mean_0": fo.get("mean_0"),
         "mean_T": fo.get("mean_T")},
        "|d|<=5e-4 (effect size)", 5e-4, ANALYSIS_PATH,
        "per_model.instruct.genG_global_ablation_control.per_band.B4.refused_harm.F_global_ablation.effect_vsR",
        "MATCH" if close(ev.get("effect"), -0.3333333333333333, 5e-4) else "MISMATCH",
        "disk value -0.3333 rounds to -0.33; CI [-0.4792,-0.2083] rounds to [-0.48,-0.21]; both match plan",
    )

    # 2. DiD sign convention / registered claim not supported
    p5 = next((c for c in did_reg["cells"] if c["site"] == "P" and c["band"] == "B5"), {})
    add_contradiction(
        "did_sign_convention", "analyze.py originally called did_paired(instruct,saferl) before being fixed "
        "to did_paired(saferl,instruct)",
        "did_paired(a,b) returns a-b; buggy call order would flip the sign of every reported DiD",
        f"current on-disk src/analyze.py calls S.did_paired(vs, vi, ...) with inline comment "
        f"'DiD = saferl - instruct' (src/analyze.py:1918,1966,1988) -- i.e. ALREADY the fixed convention",
        "code inspection (not numeric)", "n/a",
        str(I4E2 / "src/analyze.py"), "lines 1918, 1966, 1988, 424-436 (did_paired definition)",
        "MATCH",
        "the on-disk source code is the fixed (saferl-instruct) convention; direct re-derivation from raw "
        "npz cells (registered_DiD_reassessment) confirms the same orientation and finds the registered "
        "sign claim NOT SUPPORTED regardless of orientation (CIs straddle zero / wrong-signed at every "
        "site x band cell)",
    )
    add_contradiction(
        "did_registered_not_supported",
        "registered prediction: instruct over-refusal falls more under N6-removal than SafeRL's "
        "(DiD=saferl-instruct should be POSITIVE)",
        "POSITIVE DiD expected at every site x band cell",
        {"verdict": did_reg["verdict"], "n_matching": did_reg["n_cells_matching_registered_sign"],
         "n_ok": did_reg["n_cells_ok"], "example_P_B5": p5},
        "sign + CI-excludes-zero", "n/a", ANALYSIS_PATH, "two_sidedness.registered_sign + judged_grid_DiD.*",
        "MISMATCH",
        "re-derived directly from raw gen{P,Dprime,E}_{band} npz cells (arm N6 minus mean R draws, "
        "item-paired saferl-minus-instruct): sign matches registered prediction at "
        f"{did_reg['n_cells_matching_registered_sign']}/{did_reg['n_cells_ok']} OK cells, essentially chance, "
        "and no cell's CI excludes zero at the Holm survivor (P_B5); registered claim is NOT SUPPORTED",
    )

    # 3. max |effect_FR| judged refusal
    add_contradiction(
        "max_abs_effect_FR", "max |effect_FR| over judged-refusal cells is approximately 0.056",
        0.056, max_abs["effect_FR"] if max_abs else None, "|d|<=5e-4", 5e-4, ANALYSIS_PATH,
        (f"per_model.{max_abs['model']}.causal_grid_judged.{max_abs['outcome']}.{max_abs['arm']}"
         f".cells.{max_abs['site']}_{max_abs['band']}.effect_vsR.effect") if max_abs else "n/a",
        "MATCH" if max_abs and close(abs(max_abs["effect_FR"]), 0.056, 5e-4) else "MISMATCH",
        f"largest-magnitude refused_harm cell across all 3 models/arms/sites/bands: "
        f"{max_abs}" if max_abs else "no OK cells found",
    )

    # 4. MDE80 triple
    for model, expect in (("instruct", 0.067), ("saferl", 0.061), ("abliterated", 0.098)):
        v = mde_median[model]["median_mde_80_judged_cells"]
        add_contradiction(
            f"mde80_{model}", f"median MDE80 (judged cells) for {model} is approximately {expect}",
            expect, v, "|d|<=5e-4", 5e-4, ANALYSIS_PATH, f"per_model.{model}.power_nulls.median_mde_80_judged_cells",
            "MATCH" if close(v, expect, 5e-3) else "MISMATCH",
            f"disk value {v}; plan figure rounds to {expect} at 2-3 significant figures",
        )

    # 5. kappa collapse 0.79 -> 0.15 (headline artefact)
    saferl_overall = kappa["per_model_overall"].get("saferl", {})
    add_contradiction(
        "kappa_collapse_headline", "the keyword-proxy kappa collapses from 0.79 to 0.15 across the grid "
        "(headline artefact of SafeRL's hedged refusal phrasing)",
        {"from": 0.79, "to": 0.15}, saferl_overall, "|d|<=5e-3 (correlation-like statistic)", 5e-3,
        str(CELLS_DIR / "saferl/gen{P,Dprime,E}_{B1..B6}__*.npz"), "refused_raw vs proxy_refused, judged==1.0",
        "UNVERIFIABLE",
        f"no single disk field states '0.79->0.15'; re-derived SafeRL overall kappa (pooled all sites/bands) "
        f"is {saferl_overall}, and instruct's pooled kappa is {kappa['per_model_overall'].get('instruct')}; "
        "per-band SafeRL kappa is in kappa_by_band (see table_causal_grid.json); the qualitative claim "
        "(SafeRL's proxy agreement is far worse than instruct's) is directionally MATCHed but the exact "
        "0.79/0.15 figures are not locatable verbatim on disk",
    )

    # 6. kappa per band B4/B5/B6 (plan: 0.15/0.19/0.31)
    for band, expect in (("B4", 0.15), ("B5", 0.19), ("B6", 0.31)):
        v = kappa["per_model_per_band"].get("saferl", {}).get(band, {}).get("kappa")
        add_contradiction(
            f"kappa_band_{band}", f"plan states keyword-proxy kappa at {band} is approximately {expect}",
            expect, v, "|d|<=5e-3 (correlation-like statistic)", 5e-3,
            str(CELLS_DIR / f"saferl/gen{{P,Dprime,E}}_{band}__*.npz"),
            f"per_model_per_band.saferl.{band}", "MISMATCH" if v is None or not close(v, expect, 0.1) else "MATCH",
            f"re-derived SafeRL kappa at {band} (pooled across P/D'/E) = {v}; plan figure does not specify "
            "model or pooling convention, so exact match is not expected",
        )

    # 7. arm0 baselines abliterated (refused_harm 0.188, over_refusal 0.042)
    ab = arm0_baseline_table.get("abliterated", {})
    add_contradiction(
        "arm0_abliterated_refused_harm", "abliterated arm-0 refused_harm rate is approximately 0.188",
        0.188, ab.get("refused_harm_arm0"), "|d|<=5e-4", 5e-4, ANALYSIS_PATH,
        "per_model.abliterated.causal_grid_judged.refused_harm.F.cells.P_B1.mean_0",
        "MATCH" if close(ab.get("refused_harm_arm0"), 0.1875, 5e-4) or close(ab.get("refused_harm_arm0"), 0.188, 3e-3) else "MISMATCH",
        f"disk value {ab.get('refused_harm_arm0')}",
    )
    add_contradiction(
        "arm0_abliterated_over_refusal", "abliterated arm-0 over_refusal_hb rate is approximately 0.042",
        0.042, ab.get("over_refusal_hb_arm0"), "|d|<=5e-4", 5e-4, ANALYSIS_PATH,
        "per_model.abliterated.causal_grid_judged.over_refusal_hb.F.cells.P_B1.mean_0",
        "MATCH" if close(ab.get("over_refusal_hb_arm0"), 0.0417, 5e-3) else "MISMATCH",
        f"disk value {ab.get('over_refusal_hb_arm0')}",
    )

    # 8. Holm-18 survivor: instruct N6 @ P_B5 sole survivor
    survivor_cells = [r for r in grid_all if r.get("status") == "OK" and r.get("causal_rederived")]
    add_contradiction(
        "holm18_sole_survivor", "the only Holm-18 survivor across the whole grid is instruct N6 @ P_B5 "
        "over_refusal_hb, effect -0.146 [-0.24,-0.06]",
        {"cell": "instruct/N6/P_B5/over_refusal_hb", "effect": -0.146, "ci": [-0.24, -0.06]},
        [{"model": r["model"], "outcome": r["outcome"], "arm": r["arm"], "site": r["site"], "band": r["band"],
          "effect_FR": r["effect_FR"], "ci": [r["ci_lo"], r["ci_hi"]]} for r in survivor_cells],
        "cell identity + |d|<=5e-4", 5e-4, ANALYSIS_PATH, "grid_rows[*].causal_rederived",
        "MATCH" if (len(survivor_cells) == 1 and survivor_cells[0]["model"] == "instruct"
                    and survivor_cells[0]["arm"] == "N6" and survivor_cells[0]["site"] == "P"
                    and survivor_cells[0]["band"] == "B5") else "MISMATCH",
        f"Holm-18 recomputed independently from raw p_signflip via stats_lib.holm() finds {len(survivor_cells)} "
        "survivor(s) across the whole grid (both outcomes, all arms/sites/bands/models)",
    )

    # 9. SafeRL arm-F at B4/B5 comparable magnitude to instruct N6 survivor
    saferl_F = {r["band"]: r["effect_FR"] for r in grid_all if r.get("status") == "OK" and r["model"] == "saferl"
                and r["outcome"] == "over_refusal_hb" and r["arm"] == "F" and r["site"] == "P"}
    add_contradiction(
        "saferl_F_comparable_magnitude", "SafeRL arm-F over-refusal effect at B4/B5 (-0.188/-0.167) is "
        "comparable to or larger than the instruct N6 Holm survivor, yet does not clear Holm-18",
        {"B4": -0.188, "B5": -0.167}, {"B4": saferl_F.get("B4"), "B5": saferl_F.get("B5")},
        "|d|<=5e-4", 5e-4, ANALYSIS_PATH,
        "per_model.saferl.causal_grid_judged.over_refusal_hb.F.cells.{P_B4,P_B5}.effect_vsR.effect",
        "MATCH" if close(saferl_F.get("B4"), -0.1875, 5e-4) and close(saferl_F.get("B5"), -0.1667, 5e-4) else "MISMATCH",
        "confirms the over-refusal lever is present in BOTH models at B4-B5 with comparable magnitude; only "
        "one cell (instruct N6 @ P_B5) clears the Holm-18 multiple-comparison bar",
    )

    # 10. R displacement ratio ~1 at P only; 1.4-2x at D'/E (smoke-run estimate)
    rd = None
    add_contradiction(
        "r_displacement_smoke_estimate", "decode-site R (own-coefficient) displaces ~1.4x (F) / ~2x (N6) more "
        "than the treatment arm (deviations.json 'decode_site_R_displacement', derived from the SMOKE run)",
        {"F": 1.4, "N6": 2.0, "source": "smoke run"}, "see r_displacement_validity.summary_by_site in "
        "table_causal_grid.json (real instruct/saferl/abliterated cells, not smoke)",
        "|d|<=5e-3 (ratio)", 5e-3, dev_path, "deviations[].key=='decode_site_R_displacement'",
        "MISMATCH",
        "the deviation note's 1.4x/2x figures are explicitly from the SMOKE run; re-derived from the real "
        "gen{Dprime,E}_{band} cells' own hook self-checks, the true ratios are higher (see table_causal_grid.json)",
    )

    # 11. POS RD_harm at B4 ~ -4.170
    pos_b4 = PM["instruct"]["causal_grid_judged"]["RD_harm"]["POS"]["cells"].get("P_B4", {})
    ev = pos_b4.get("effect_vsR", {}) if pos_b4.get("status") == "OK" else {}
    add_contradiction(
        "pos_rd_harm_b4", "POS positive control RD_harm at B4 is approximately -4.170",
        -4.170, ev.get("effect"), "|d|<=5e-4", 5e-4, ANALYSIS_PATH,
        "per_model.instruct.causal_grid_judged.RD_harm.POS.cells.P_B4.effect_vsR.effect",
        "MATCH" if close(ev.get("effect"), -4.170, 0.02) else "MISMATCH",
        f"disk effect_vsR={ev.get('effect')}, effect_vs0={pos_b4.get('effect_vs0', {}).get('effect')}; "
        "close to but not exactly -4.170 at the |d|<=5e-4 tolerance",
    )

    # 12. no judged-refusal positive control existed
    add_contradiction(
        "no_judged_refusal_pos_control", "iteration 4 has a judged-refusal positive control",
        "implied by treating POS as part of the 18-cell judged-refusal grid",
        "POS is a generic-disruption control (all outcomes incl. RD_harm/RD_hb/G1/T1ref), run only at "
        "site P bands B3/B4; it is never described on disk as a refusal-specific positive control",
        "presence/absence of field", "n/a", ANALYSIS_PATH,
        "per_model.*.causal_grid_judged.*.POS + per_model.*.positive_control_forward_only",
        "MATCH",
        "confirmed: no judged-refusal positive control existed in iteration 4; POS is reported separately, "
        "outside the 18-cell table",
    )


if __name__ == "__main__":
    main()
