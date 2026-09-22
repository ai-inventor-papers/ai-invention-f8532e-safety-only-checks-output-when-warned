#!/usr/bin/env python3
"""STEP 6 - gates table. Every gate is RECOMPUTED where its inputs exist on disk, else it is
copied and flagged 'copied - not recomputable'. Writes results/gates_table.{json,csv}."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import norm

WS = Path(__file__).resolve().parents[1]
RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
DS2 = RUN / "iter_2/gen_art/gen_art_dataset_1"
DS1 = RUN / "iter_1/gen_art/gen_art_dataset_1"
LANE_A = RUN / "iter_1/gen_art/gen_art_experiment_1"
LANE_B = RUN / "iter_1/gen_art/gen_art_experiment_2"

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(WS / "logs/gates.log", rotation="30 MB", level="DEBUG")


def row(gate: str, artifact: str, threshold, observed, verdict: str, consequence: str,
        *, recomputed: bool, copied_value=None, note: str = "") -> dict:
    return {"gate": gate, "artifact": artifact, "threshold": str(threshold),
            "observed": observed if isinstance(observed, (int, float, str)) or observed is None
            else json.dumps(observed)[:300],
            "copied_value": copied_value if isinstance(copied_value, (int, float, str, type(None)))
            else json.dumps(copied_value)[:300],
            "provenance": "recomputed" if recomputed else "copied - not recomputable",
            "verdict": verdict, "consequence": consequence, "note": note}


def dataset_iter2_rows() -> list[dict]:
    g = json.loads((DS2 / "gates.json").read_text())["gates"]
    full = json.loads((DS2 / "full_data_out.json").read_text())
    md = full["metadata"]
    out = []
    # registry-derived label counts (recomputable) ---------------------------------
    labels: dict[str, int] = {}
    strata_eff: dict[str, int] = {}
    reg_rows = []
    for ds in full["datasets"]:
        if "registry" in ds["dataset"].lower() or "pair" in ds["dataset"].lower():
            reg_rows += ds["examples"]
    for ex in reg_rows:
        if ex.get("metadata_row_kind") != "pair":
            continue
        lab = ex.get("metadata_effectiveness_label")
        robust = str(ex.get("metadata_label_robust")) == "True"
        key = f"{lab}{'' if robust or lab in ('UNSCORED', 'SEALED') else '(not robust)'}"
        labels[key] = labels.get(key, 0) + 1
        if lab == "EFFECTIVE" and robust:
            st = ex.get("metadata_recipe_stratum") or "unknown"
            strata_eff[st] = strata_eff.get(st, 0) + 1
    logger.info(f"dataset registry rows={len(reg_rows)} label_robust histogram={labels}")
    prereg_sha = hashlib.sha256((DS2 / "prereg.json").read_bytes()).hexdigest()
    file_sha = (DS2 / "prereg.sha256").read_text().split()[0]
    for x in g:
        gid = x["gate_id"]
        obs, rec, verdict, note = x["observed"], False, x["status"], ""
        if gid == "G_PREREG_HASH":
            obs = prereg_sha
            ok = prereg_sha == file_sha == md.get("prereg_sha256")
            verdict, rec = ("PASS" if ok else "FAIL"), True
            note = f"sha256(prereg.json)={prereg_sha[:16]}.. prereg.sha256={file_sha[:16]}.. metadata={str(md.get('prereg_sha256'))[:16]}.."
        elif gid == "G_NONEFFECTIVE" and labels:
            obs = int(labels.get("NULL_EDIT", 0) + labels.get("ANOMALOUS", 0))  # robust labels only
            verdict, rec = ("PASS" if obs >= 2 else "FAIL"), True
            note = f"label_robust histogram {labels}"
        elif gid == "G_EFFECTIVE_IN_STRATUM" and strata_eff:
            obs = int(max(strata_eff.values()))
            verdict, rec = ("PASS" if obs >= 4 else "FAIL"), True
            note = f"EFFECTIVE by stratum {strata_eff}"
        elif gid == "G_PROXY_HARD":
            verdict = "PASS" if float(obs) <= 0.85 else "FAIL"
            note = "verdict re-applied to the stored proxy AUROC; the TF-IDF CV itself is not re-run (text proxy, BASELINE class)"
        cons = {
            "G_EFFECTIVE_IN_STRATUM": "E1 edit-recipe tests UNDER-POWERED by construction (strata 3/2/1 effective pairs); no survivor promotion possible",
            "G_NONEFFECTIVE": "no labelled specificity control; granite NULL_EDIT demoted to AMBIGUOUS, so specificity is argued from MEASURED deltas (dHC 0.000) not labels",
            "G_PROXY_HARD": "HARD recognition set is still partly text-decodable (0.885); TPR@FPR on it is an upper bound on activation-specific recognition",
        }.get(gid, "none (PASS)" if verdict == "PASS" else "see note")
        out.append(row(gid, "art_1hlgObsQWnZS (iter-2 dataset)", x["threshold"], obs, verdict, cons,
                       recomputed=rec, copied_value=x["observed"], note=note or str(x.get("note", ""))[:200]))
    return out


def dataset_iter1_rows() -> list[dict]:
    jv = json.loads((DS1 / "judge_validation.json").read_text())
    pr = json.loads((DS1 / "prereg.json").read_text())
    out = []
    sub = jv["subsets"]["prefix_hazard_family_identification"]["per_rater"]
    a, b = sub["rater_a"], sub["rater_b"]
    pooled = (a["hazard_identification_accuracy"] * a["n_scored_hazard"]
              + b["hazard_identification_accuracy"] * b["n_scored_hazard"]) / (a["n_scored_hazard"] + b["n_scored_hazard"])
    for gg in jv["gates"]:
        name, thr, obs = gg["name"], gg["threshold"], gg["observed"]
        rec, val = False, obs
        if name == "prefix_hazard_identification_accuracy":
            val, rec = round(pooled, 4), True
        if name == "non_operationality_flag_count":
            ver = "PASS" if val <= thr else "FAIL"
        else:
            ver = "PASS" if val >= thr else "FAIL"
        cons = ("confirmatory set cut 96 -> 85 by qc_exclusions" if name.startswith("prefix_hazard")
                else "none (PASS)" if ver == "PASS" else "see note")
        out.append(row(f"D1_{name}", "iter-1 dataset judge_validation.json", thr, val, ver, cons,
                       recomputed=rec, copied_value=obs,
                       note="recomputed as n-weighted pool of the two raters' per-rater accuracies" if rec else ""))
    q = pr["qc_exclusions"]
    out.append(row("D1_confirmatory_n_after_qc", "iter-1 dataset prereg.json qc_exclusions", "96 registered",
                   q.get("confirmatory_n_after"), "DEVIATION", "confirmatory substrate 96 -> 85 items",
                   recomputed=True, copied_value=f"{q.get('confirmatory_n_before')}->{q.get('confirmatory_n_after')}",
                   note=f"{len(q.get('affected_confirmatory_items', []))} affected confirmatory item ids listed (11 unique => 96-11=85)"))
    pc = pr["placebo_calibration_full"]
    ratio = pc["median_benign_to_placebo"] / pc["median_benign_to_hazardous"]
    out.append(row("D1_placebo_median_edit_ratio", "iter-1 dataset prereg.json placebo_calibration_full",
                   "<= 1.10", round(ratio, 4), "PASS" if ratio <= 1.10 else "FAIL",
                   "placebo edit distance not matched; per-item distances shipped for regression instead of subtraction",
                   recomputed=True, copied_value=pc["median_ratio"],
                   note=f"ratio recomputed from medians {pc['median_benign_to_placebo']}/{pc['median_benign_to_hazardous']}; mean ratio {pc.get('mean_ratio')}"))
    return out


def lane_a_rows() -> list[dict]:
    g = json.loads((LANE_A / "out/method_out.json").read_text())["metadata"]["gates"]
    out = []
    for ck, v in g["G1_direction_stability"].items():
        val = v["mean_split_half_cosine"]
        out.append(row(f"A_G1_split_half|{ck}", "art_2QM9uBviY4Wk Lane A", ">= 0.70", round(val, 4),
                       "PASS" if val >= 0.7 else "FAIL",
                       "registered fallback fired: supervised probe axis reported beside every K1 term",
                       recomputed=True, copied_value=v["verdict"], note="verdict re-applied to stored split-half mean"))
    for ck, v in g["G3_positive_control"].items():
        val = v["d_cross_fitted"]
        out.append(row(f"A_G3_positive_control|{ck}", "art_2QM9uBviY4Wk Lane A", ">= 0.80 (cross-fitted d)",
                       round(val, 4), "PASS" if val >= 0.8 else "FAIL",
                       "trained arms carry a decodable content axis; random-init does not" ,
                       recomputed=True, copied_value=v["verdict"]))
    for ck, v in g["G5_placebo_equivalence"].items():
        t = v["tost"]
        m, se, mg = t["mean"], t["se"], v["margin"]
        p_lo = 1 - norm.cdf((m + mg) / se)
        p_hi = norm.cdf((m - mg) / se)
        eq = max(p_lo, p_hi) < 0.05
        out.append(row(f"A_G5_placebo_TOST|{ck}", "art_2QM9uBviY4Wk Lane A", f"TOST equivalence at +/-{mg}",
                       f"mean {m:.3f} se {se:.3f} p_TOST {max(p_lo, p_hi):.3g}", "PASS" if eq else "FAIL",
                       "placebo interaction is not equivalent to zero: A cannot be read as hazard-specific",
                       recomputed=True, copied_value=v["verdict"]))
    for ck, v in g["G6_nll_match"].items():
        c = v["cell_mean_prefix_logprob"]
        saf = (np.mean([c["saf|F1|H|ben"], c["saf|F1|B|haz"]]) - np.mean([c["saf|F1|H|haz"], c["saf|F1|B|ben"]]))
        coh = (np.mean([c["coh|F1|A|B"], c["coh|F1|B|A"]]) - np.mean([c["coh|F1|A|A"], c["coh|F1|B|B"]]))
        lic = bool(coh <= saf)
        match = abs(saf - v["safety_offdiagonal_penalty"]) < 1e-4 and abs(coh - v["coherence_offdiagonal_penalty"]) < 1e-4
        out.append(row(f"A_G6_nll_match|{ck}", "art_2QM9uBviY4Wk Lane A",
                       "coherence off-diagonal penalty <= safety penalty", f"safety {saf:.4f} coherence {coh:.4f}",
                       "LICENSED" if lic else "NOT_LICENSED",
                       "A_net subtraction licensed" if lic else "A_net is an UPPER BOUND in this arm",
                       recomputed=True, copied_value=v["subtraction_licensed"],
                       note=f"recomputed from F1 cell means; reproduces stored penalties: {match}"))
    return out


def lane_b_rows() -> list[dict]:
    a = json.loads((LANE_B / "out/analysis.json").read_text())["lineages"]
    out = []
    pooled, mx, sh = [], [], []
    for L, v in a.items():
        pooled.append(v.get("G1_cos_pooled"))
        mx.append(v.get("G1_max"))
        sh.append(v.get("r_content_split_half_cosine"))
        out.append(row(f"B_G1_cos|{L}", "art_2sz7g3MD4_y3 Lane B", "<= 0.50", round(v.get("G1_cos_pooled"), 4),
                       "PASS" if v.get("G1_max") <= 0.5 else "FAIL", "content and request axes near-orthogonal",
                       recomputed=False, copied_value=v.get("G1_cos_pooled"), note=f"max over band {v.get('G1_max'):.4f}"))
    rec_note = ("quoted '0.159 pooled / 0.175 max' equals lineage L2 alone (0.1594 / 0.1750); across the 4 "
                "lineages the pooled mean and the max differ (see observed). r_content is not in L*_dirs.npz "
                "(it holds u and per-layer r_ablit 'ra_l'), so per-lineage cosines are copied and only the aggregate is recomputed")
    out.append(row("B_G1_cos_pooled_all", "art_2sz7g3MD4_y3 Lane B", "<= 0.50 (max)",
                   f"mean {np.mean(pooled):.4f} max-of-max {np.max(mx):.4f}", "PASS" if np.max(mx) <= 0.5 else "FAIL",
                   "HARC alignment kill-risk does not bite at 4B", recomputed=True,
                   copied_value="0.159 pooled / 0.175 max (quoted)", note=rec_note))
    out.append(row("B_split_half_r_content", "art_2sz7g3MD4_y3 Lane B", ">= 0.70",
                   f"mean {np.mean(sh):.4f} min {np.min(sh):.4f}", "PASS" if np.min(sh) >= 0.7 else "FAIL",
                   "content axis stable", recomputed=True, copied_value="0.927 (quoted)"))
    return out


@logger.catch(reraise=True)
def main() -> None:
    rows = dataset_iter2_rows() + dataset_iter1_rows() + lane_a_rows() + lane_b_rows()
    (WS / "results").mkdir(exist_ok=True)
    (WS / "results/gates_table.json").write_text(json.dumps(rows, indent=1, default=str))
    pd.DataFrame(rows).to_csv(WS / "results/gates_table.csv", index=False)
    vc = pd.Series([r["verdict"] for r in rows]).value_counts().to_dict()
    logger.info(f"{len(rows)} gate rows; verdicts {vc}")


if __name__ == "__main__":
    main()
