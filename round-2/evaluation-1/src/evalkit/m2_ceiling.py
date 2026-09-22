#!/usr/bin/env python3
"""M2 -- ceiling and dynamic-range audit. READOUT_CLASS: mixed, per row.

For every outcome used in an iteration-1 verdict: its theoretical ceiling, its
value in the UNPERTURBED control, the fraction of its range actually used, and
a SATURATED / HAS_HEADROOM flag at the pre-registered threshold.

Two things this table is for:
  * Every verdict resting on a SATURATED outcome is re-labelled INDETERMINATE
    here, beside the claim it qualifies.
  * The INDETERMINATE_NO_MATCHED_POINT verdict that iteration 1 buried in its
    limitations -- every registered damage-signature row returned it, because
    the primary damage variable was flat at ceiling with no matched point -- is
    lifted out of the limitations section and printed next to the claim.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from loguru import logger

from . import paths as P
from .prereg import PREREG, prereg_hash

SAT = PREREG["M2_saturation_threshold"]


def _row(*, outcome: str, lane: str, scope: str, ceiling: float, control: float,
         observed: list[float], source_file: str, json_path: str,
         readout_class: str, verdict_depends: str, floor: float = 0.0,
         note: str = "") -> dict:
    vals = [v for v in observed if v is not None and np.isfinite(v)]
    spread = (max(vals) - min(vals)) if vals else float("nan")
    full = ceiling - floor
    edr = spread / full if full else float("nan")
    used = ((control - floor) / full) if (full and np.isfinite(control)) else float("nan")
    saturated = np.isfinite(control) and abs(ceiling - control) <= SAT
    return {
        "metric": "M2",
        "outcome": outcome,
        "lane": lane,
        "scope": scope,
        "theoretical_floor": floor,
        "theoretical_ceiling": ceiling,
        "value_in_unperturbed_control": control,
        "fraction_of_range_used_by_control": round(used, 6) if np.isfinite(used) else None,
        "observed_min": min(vals) if vals else None,
        "observed_max": max(vals) if vals else None,
        "observed_spread": round(spread, 6) if np.isfinite(spread) else None,
        "effective_dynamic_range": round(edr, 6) if np.isfinite(edr) else None,
        "n_observations": len(vals),
        "saturation_threshold": SAT,
        "flag": "SATURATED" if saturated else "HAS_HEADROOM",
        "verdict_relabel": ("INDETERMINATE (the outcome is at its ceiling in the "
                            "unperturbed control, so it cannot fall)"
                            if saturated else "STANDS"),
        "which_verdict_depends_on_it": verdict_depends,
        "source_file": source_file,
        "json_path": json_path,
        "READOUT_CLASS": readout_class,
        "BASELINE_ONLY": readout_class in PREREG["run_invariant"]["baseline_only"],
        "DESCRIPTIVE": True,
        "note": note,
    }


def run(m1_rows: list[dict] | None = None) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    notes: dict = {"prereg_sha256": prereg_hash(), "sources_used": [], "absent": [],
                   "indeterminate_no_matched_point": [], "cuts_taken": []}

    # ---- Lane B ----------------------------------------------------------- #
    if P.B_ANALYSIS.exists():
        notes["sources_used"].append(P.rel(P.B_ANALYSIS))
        lanes = json.loads(P.B_ANALYSIS.read_text())["lineages"]
        for lin, st in lanes.items():
            repo = st.get("repo", lin)
            for key, ceiling, rclass, dep in (
                ("D_curve", 1.0, "activation",
                 "'the harm representation survives the lesion ENTIRELY' -- the "
                 "headline recognition claim"),
                ("D_matched_probe_curve", 1.0, "activation",
                 "the matched-twin companion to the same recognition claim"),
                ("D_matched_axis_curve", 1.0, "activation",
                 "'removing u post-hoc drops the probe' -- the 1-D axis readout"),
                ("D_axis_1d_curve", 1.0, "activation",
                 "the lesion-exactness verification"),
            ):
                curve = st.get(key)
                if not curve:
                    notes["absent"].append({"quantity": f"{lin}.{key}",
                                            "json_path": f"lineages.{lin}.{key}"})
                    continue
                rows.append(_row(
                    outcome=key, lane="B", scope=f"{lin} ({repo}), alphas 0.00-1.00",
                    ceiling=ceiling, control=float(curve[0]),
                    observed=[float(v) for v in curve],
                    source_file=P.rel(P.B_ANALYSIS),
                    json_path=f"lineages.{lin}.{key}",
                    readout_class=rclass, verdict_depends=dep,
                    floor=0.5 if "auroc" in key.lower() or key.startswith("D_") else 0.0,
                    note="floor 0.5: an AUROC-scale outcome cannot go below chance"))
            if st.get("alpha_star") is None:
                notes["indeterminate_no_matched_point"].append({
                    "lineage": lin, "repo": repo,
                    "alpha_star_source": st.get("alpha_star_source"),
                    "matched_damage_criterion_met": st.get("matched_damage_criterion_met"),
                    "deviations": st.get("deviations"),
                    "json_path": f"lineages.{lin}.alpha_star",
                    "source_file": P.rel(P.B_ANALYSIS),
                })
        verdicts = json.loads(P.B_ANALYSIS.read_text()).get("S2_verdicts", {})
        for cand, v in verdicts.items():
            rows.append({
                "metric": "M2", "outcome": f"S2 verdict: {cand}", "lane": "B",
                "scope": f"{v.get('n_lineages_scored', 0)} of "
                         f"{len(v.get('lineages', []))} lineages scored",
                "theoretical_floor": None, "theoretical_ceiling": None,
                "value_in_unperturbed_control": None,
                "fraction_of_range_used_by_control": None,
                "observed_min": None, "observed_max": None, "observed_spread": None,
                "effective_dynamic_range": None,
                "n_observations": v.get("n_indeterminate", 0),
                "saturation_threshold": SAT,
                "flag": ("INDETERMINATE_NO_MATCHED_POINT"
                         if v.get("verdict", "").startswith("INDETERMINATE")
                         else "SCORED"),
                "verdict_relabel": v.get("verdict"),
                "which_verdict_depends_on_it": (
                    "Every registered damage-signature row returned "
                    "INDETERMINATE_NO_MATCHED_POINT because the primary damage "
                    "variable was FLAT AT CEILING with no matched point. Iteration 1 "
                    "carried this only in its limitations section; it is printed here "
                    "beside the claim it qualifies."),
                "source_file": P.rel(P.B_ANALYSIS),
                "json_path": f"S2_verdicts.{cand}.verdict",
                "READOUT_CLASS": "activation", "BASELINE_ONLY": False,
                "DESCRIPTIVE": True,
                "note": v.get("note", ""),
            })
    else:
        notes["absent"].append({"quantity": "Lane B analysis", "glob": P.rel(P.B_ANALYSIS)})

    # ---- Lane C ----------------------------------------------------------- #
    per_ckpt = sorted(P.C_PER_CKPT.glob("*.json")) if P.C_PER_CKPT.is_dir() else []
    if per_ckpt:
        notes["sources_used"].append(P.rel(P.C_PER_CKPT / "*.json"))
        collected: dict[str, list[float]] = {"rcontent_heldout_auroc": [],
                                             "rcontent_splithalf": [],
                                             "cos_rcontent_rrequest": []}
        for f in per_ckpt:
            inst = json.loads(f.read_text()).get("instrument", {})
            for k in collected:
                v = inst.get(k)
                if isinstance(v, (int, float)):
                    collected[k].append(float(v))
        for k, ceiling, floor, rclass, dep in (
            ("rcontent_heldout_auroc", 1.0, 0.5, "activation",
             "'the content axis is a valid instrument' -- the gate every Lane C "
             "candidate feature is computed through"),
            ("rcontent_splithalf", 1.0, 0.0, "activation",
             "G1 direction stability, which Lane A FAILS and Lane C PASSES under "
             "the same gate name"),
            ("cos_rcontent_rrequest", 1.0, 0.0, "activation",
             "'the two axes are near-orthogonal' -- reported at panel scale"),
        ):
            vals = collected[k]
            if not vals:
                notes["absent"].append({"quantity": f"instrument.{k}",
                                        "glob": P.rel(P.C_PER_CKPT / "*.json")})
                continue
            rows.append(_row(
                outcome=k, lane="C", scope=f"{len(vals)} panel checkpoints",
                ceiling=ceiling, control=float(np.mean(vals)),
                observed=vals, floor=floor,
                source_file=P.rel(P.C_PER_CKPT / "*.json"),
                json_path=f"instrument.{k}", readout_class=rclass,
                verdict_depends=dep,
                note="control taken as the panel MEAN: there is no unperturbed arm "
                     "in a cross-family panel"))
    else:
        notes["absent"].append({"quantity": "Lane C per-checkpoint scalars",
                                "glob": P.rel(P.C_PER_CKPT / "*.json")})

    # ---- Lane A ----------------------------------------------------------- #
    if P.A_COS_CONTENT_ABLIT.exists():
        notes["sources_used"].append(P.rel(P.A_COS_CONTENT_ABLIT))
        cos = json.loads(P.A_COS_CONTENT_ABLIT.read_text())
        at_band = [v["at_band"] for v in cos.values()
                   if isinstance(v, dict) and isinstance(v.get("at_band"), (int, float))]
        if at_band:
            rows.append(_row(
                outcome="|cos(r_content, r_ablit)| at band", lane="A",
                scope=f"{len(at_band)} arms, one family", ceiling=1.0,
                control=float(np.mean(at_band)), observed=at_band,
                source_file=P.rel(P.A_COS_CONTENT_ABLIT),
                json_path="<ckpt>.at_band", readout_class="activation",
                verdict_depends="'the response-site and prompt-site axes are "
                                "NEAR-ORTHOGONAL', and the confound gate that "
                                "licenses the parent-fixed post-edit arm"))

    # ---- M1's own outcomes, for the contrast the whole table exists to make -- #
    if m1_rows:
        aur = [r["auroc_recomputed"] for r in m1_rows
               if r.get("metric") == "M1" and isinstance(r.get("auroc_recomputed"), float)]
        tpr = [r["tpr@1fpr_point"] for r in m1_rows
               if r.get("metric") == "M1" and isinstance(r.get("tpr@1fpr_point"), float)
               and np.isfinite(r.get("tpr@1fpr_point", np.nan))]
        if aur:
            rows.append(_row(
                outcome="M1 recomputed AUROC (the outcome iteration 1 reported)",
                lane="EVAL", scope=f"{len(aur)} arms", ceiling=1.0, floor=0.5,
                control=float(max(aur)), observed=aur,
                source_file="results/m1_recognition_headroom.csv",
                json_path="auroc_recomputed", readout_class="activation",
                verdict_depends="the recognition-invariance premise"))
        if tpr:
            rows.append(_row(
                outcome="M1 TPR@1%FPR (the de-saturated replacement)",
                lane="EVAL", scope=f"{len(tpr)} arms", ceiling=1.0, floor=0.0,
                control=float(max(tpr)), observed=tpr,
                source_file="results/m1_recognition_headroom.csv",
                json_path="tpr@1fpr_point", readout_class="activation",
                verdict_depends="the recognition-invariance premise, re-expressed "
                                "on an outcome with headroom"))

    n_sat = sum(1 for r in rows if r["flag"] == "SATURATED")
    n_scaled = sum(1 for r in rows if r["flag"] in ("SATURATED", "HAS_HEADROOM"))
    n_inm = sum(1 for r in rows if r["flag"] == "INDETERMINATE_NO_MATCHED_POINT")
    notes["n_rows"] = len(rows)
    notes["n_scaled_outcomes"] = n_scaled
    notes["n_saturated"] = n_sat
    notes["n_indeterminate_no_matched_point_rows"] = n_inm
    notes["n_relabelled_indeterminate"] = n_sat + n_inm
    notes["headline"] = (
        f"{n_sat} of {n_scaled} scaled outcomes are SATURATED in their unperturbed "
        f"control at the pre-registered threshold of {SAT}; a further {n_inm} "
        f"registered damage-signature rows returned INDETERMINATE_NO_MATCHED_POINT "
        f"because the primary damage variable was flat at ceiling. Every verdict "
        f"resting on either is re-labelled INDETERMINATE in this table."
    )
    logger.info("M2: {} rows, {} saturated, {} indeterminate-no-matched-point",
                len(rows), n_sat, n_inm)
    return rows, notes
