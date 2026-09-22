"""Build eval_out.json in the exp_eval_sol_out schema from the emitted tables.

Runs AFTER src/assemble.py's gate. Every example carries its provenance, so the
downstream paper step can trace any number back to the file it was derived from.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
RES = WS / "results"

DELIVERABLES = {
    "D1": ("table_composition.json", "Composition table: every NOOP and EFFECTIVE pair"),
    "D2": ("table_degeneracy.json", "Structural degeneracy and exact McNemar"),
    "D3": ("table_bl1_variants.json", "Baseline-variant flip across the five Qwen3-4B arms"),
    "D4": ("table_candidates32.json", "All candidate readouts: false alarms vs sensitivity"),
    "D5": ("table_causal_grid.json", "Full causal depth x site grid with Holm-18 recomputed"),
    "D6": ("table_equivalence.json", "Equivalence bound and arm-0 floor"),
    "D7": ("table_fewprompt.json", "Few-prompt feasibility: k-curve and required panel size"),
    "D8": ("table_displacement.json", "Measured displacement replacing the bitwise explanation"),
    "D9": ("table_geometry.json", "Rotation-versus-magnitude geometry of the safety directions"),
    "D10": ("table_setup_deviations.json", "Experimental setup, appendix content and deviations"),
    "D11": ("join_backstop.json", "Backstop confirmation join with hash-order verification"),
    "D4plus": ("table_sensitivity_denominators.json", "Sensitivity at the 10- and 11-pair effective sets"),
    "D7plus": ("table_panel_power.json", "Power for the paired correlation difference"),
}

MAX_EX_PER_DS = 400

# Curated headline metrics: (metric name, results file, dotted key path).
# Read by explicit path so a renamed key surfaces as a missing metric (listed in
# metadata.curated_metrics_missing) instead of being silently mis-read.
CURATED = [
    # D2: exact McNemar, BL1_easy vs N1, on both denominators
    ("mcnemar15_b", "table_degeneracy.json", "mcnemar_BL1_easy_vs_N1.denominator_15_all_noop.b"),
    ("mcnemar15_c", "table_degeneracy.json", "mcnemar_BL1_easy_vs_N1.denominator_15_all_noop.c"),
    ("mcnemar15_p_exact", "table_degeneracy.json", "mcnemar_BL1_easy_vs_N1.denominator_15_all_noop.p_exact"),
    ("mcnemar12_b", "table_degeneracy.json", "mcnemar_BL1_easy_vs_N1.denominator_12_non_degenerate_activation.b"),
    ("mcnemar12_c", "table_degeneracy.json", "mcnemar_BL1_easy_vs_N1.denominator_12_non_degenerate_activation.c"),
    ("mcnemar12_p_exact", "table_degeneracy.json", "mcnemar_BL1_easy_vs_N1.denominator_12_non_degenerate_activation.p_exact"),
    ("mcnemar12_min_attainable_p", "table_degeneracy.json", "mcnemar_BL1_easy_vs_N1.denominator_12_non_degenerate_activation.min_attainable_p"),
    # D4: FA-vs-sensitivity trade-off
    ("spearman_fa_sens_activation_excl_ams", "table_candidates32.json", "tradeoff.within_activation_class_excl_AMS_baseline.rho"),
    ("spearman_fa_sens_activation_incl_ams", "table_candidates32.json", "tradeoff.within_activation_class_incl_AMS_baseline.rho"),
    ("spearman_fa_sens_all32", "table_candidates32.json", "tradeoff.across_all_32_rows.rho"),
    # D5/D6: causal grid bound, floor, controls
    ("max_abs_effect_FR_judged_refusal", "table_equivalence.json", "max_abs_effect_FR_judged_refusal.effect_FR"),
    ("median_mde80_instruct", "table_equivalence.json", "median_mde80_per_model.instruct.median_mde_80_judged_cells"),
    ("median_mde80_saferl", "table_equivalence.json", "median_mde80_per_model.saferl.median_mde_80_judged_cells"),
    ("median_mde80_abliterated", "table_equivalence.json", "median_mde80_per_model.abliterated.median_mde_80_judged_cells"),
    ("tost_p_instruct", "table_equivalence.json", "tost_per_model.instruct.p_tost"),
    ("tost_p_saferl", "table_equivalence.json", "tost_per_model.saferl.p_tost"),
    ("tost_p_abliterated", "table_equivalence.json", "tost_per_model.abliterated.p_tost"),
    ("global_ablation_did_saferl_minus_instruct", "table_causal_grid.json", "global_ablation_control.did_direct_rederivation.did_saferl_minus_instruct"),
    ("global_ablation_did_ci_lo", "table_causal_grid.json", "global_ablation_control.did_direct_rederivation.ci_lo"),
    ("global_ablation_did_ci_hi", "table_causal_grid.json", "global_ablation_control.did_direct_rederivation.ci_hi"),
    ("registered_did_cells_matching_sign", "table_causal_grid.json", "registered_DiD_reassessment.n_cells_matching_registered_sign"),
    ("registered_did_cells_total", "table_causal_grid.json", "registered_DiD_reassessment.n_cells_ok"),
    # D8: the refuted bitwise explanation
    ("device_swap_text_identical_frac", "table_displacement.json", "refuting_evidence.ii_device_swap_reference_pair_F1__ref.identical_frac_rederived"),
    ("device_swap_hc_label_agreement", "table_displacement.json", "refuting_evidence.ii_device_swap_reference_pair_F1__ref.HC_label_agreement_rederived"),
    ("ratio_bl1_hard_over_activation", "table_displacement.json", "ratio_bl1_over_activation"),
    # D7: few-prompt feasibility
    ("critical_rho_n10_mc", "table_fewprompt.json", "d_required_panel_size_HEADLINE.critical_rho_by_n.10"),
    ("panel_n_prereg_rule", "table_fewprompt.json", "d_required_panel_size_HEADLINE.answers.observed_margin_vs_BL1.required_n"),
    ("rho_B3_BL1_n10", "table_panel_power.json", "rho_B3_BL1_true_root"),
    # secondary ledger rate (post hoc, labelled)
    ("claim_match_rate_rounding_aware_posthoc", "contradictions.json", "secondary_rounding_aware.claim_match_rate"),
]


def dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def claim_value(ledger: dict[str, Any], claim_id: str) -> float | None:
    for c in ledger.get("claims", []):
        if c.get("claim_id") == claim_id:
            v = c.get("rederived_value")
            return float(v) if is_num(v) else None
    return None


def power_n(doc: dict[str, Any], prefix: str) -> float | None:
    root = doc.get("rho_B3_BL1_true_root")
    for sc in doc.get("scenarios", []):
        if sc.get("scenario", "").startswith(prefix) and sc.get("rho_B3_BL1_implied") == root:
            v = sc.get("n_for_80pct_power")
            return float(v) if is_num(v) else None
    return None


def is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def rows_of(obj: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    stack = [obj]
    seen: set[int] = set()
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, dict):
            if "source_file" in cur or "readout_class" in cur:
                out.append(cur)
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return out


def describe(row: dict[str, Any]) -> str:
    for k in ("claim_text", "pair_id", "candidate_id", "cell_id", "row_id", "arm", "id", "name", "model", "metric", "item"):
        if row.get(k):
            head = f"{k}={row[k]}"
            break
    else:
        head = "row"
    extra = [f"{k}={row[k]}" for k in ("model", "band", "site", "arm", "readout_class", "family", "recipe")
             if k in row and f"{k}=" not in head]
    return "; ".join([head] + extra[:5])[:900]


def main() -> None:
    gate = json.loads((RES / "self_check_gate.json").read_text())
    ledger = json.loads((RES / "contradictions.json").read_text())

    metrics: dict[str, float] = {
        "claim_match_rate": float(ledger["claim_match_rate"]) if is_num(ledger.get("claim_match_rate")) else 0.0,
        "n_claims_total": float(ledger["n_claims"]),
        "n_claims_match": float(ledger["counts"]["MATCH"]),
        "n_claims_mismatch": float(ledger["counts"]["MISMATCH"]),
        "n_claims_unverifiable": float(ledger["counts"]["UNVERIFIABLE"]),
        "n_claims_source_absent": float(ledger["counts"]["SOURCE_ABSENT"]),
        "n_deliverables_produced": float(len(gate["deliverables_present"])),
        "n_deliverables_missing": float(len(gate["deliverables_missing"])),
        "n_table_rows_total": float(gate["total_table_rows"]),
        "n_candidate_rows": float(gate["candidate_table_rows"]),
        "n_rows_missing_provenance": float(sum(gate["rows_missing_provenance"].values())),
        "gate_passed": 1.0 if gate["gate_passed"] else 0.0,
        "gpu_hours_spent": 0.0,
        "usd_api_spend": 0.0,
    }

    # ---- curated headline metrics, read by explicit key path -----------------
    missing_curated: list[str] = []
    cache: dict[str, Any] = {}
    for name, fname, path in CURATED:
        if fname not in cache:
            fp = RES / fname
            cache[fname] = json.loads(fp.read_text()) if fp.exists() else {}
        v = dig(cache[fname], path)
        if is_num(v):
            # a metric NAMED as a magnitude stores the magnitude; the signed value
            # is kept beside it so the direction is not lost
            if "_abs_" in f"_{name}_":
                metrics[name] = abs(float(v))
                metrics[name.replace("max_abs_", "signed_")] = float(v)
            else:
                metrics[name] = float(v)
        else:
            missing_curated.append(f"{name} <- {fname}:{path}")
    for name, cid in (("ratio_bl1_easy_over_activation", "C6"), ("falcon3_batch8_sigma_shift", "C11a")):
        v = claim_value(ledger, cid)
        if v is not None:
            metrics[name] = v
        else:
            missing_curated.append(f"{name} <- contradictions.json claim {cid}")
    pw = RES / "table_panel_power.json"
    if pw.exists():
        pdoc = json.loads(pw.read_text())
        for name, prefix in (("panel_n80_power_observed_margin", "observed"),
                             ("panel_n80_power_half_margin", "margin shrunk")):
            v = power_n(pdoc, prefix)
            if v is not None:
                metrics[name] = v
            else:
                missing_curated.append(f"{name} <- table_panel_power.json")

    datasets: list[dict[str, Any]] = []

    # ---- ledger dataset: the primary audit product -------------------------
    ex: list[dict[str, Any]] = []
    for c in ledger["claims"][:MAX_EX_PER_DS]:
        v = str(c.get("verdict", "")).upper()
        ex.append({
            "input": str(c.get("claim_text", c.get("claim_id", "claim")))[:1500],
            "output": str(c.get("rederived_value", ""))[:1500],
            "predict_published_prose": str(c.get("claimed_value", ""))[:1500],
            "metadata_claim_id": str(c.get("claim_id", "")),
            "metadata_verdict": v,
            "metadata_source_file": str(c.get("source_file", "")),
            "metadata_source_key": str(c.get("source_key", "")),
            "metadata_tolerance_rule": str(c.get("tolerance_rule", "")),
            "metadata_note": str(c.get("note", ""))[:800],
            "eval_match": 1.0 if v == "MATCH" else 0.0,
            "eval_mismatch": 1.0 if v == "MISMATCH" else 0.0,
            "eval_verifiable": 1.0 if v in ("MATCH", "MISMATCH") else 0.0,
        })
    if ex:
        datasets.append({"dataset": "contradictions_ledger", "examples": ex})

    # ---- one dataset per deliverable ---------------------------------------
    for did, (fname, desc) in DELIVERABLES.items():
        p = RES / fname
        if not p.exists():
            continue
        try:
            obj = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        # top-level scalars become aggregate metrics
        if isinstance(obj, dict):
            for k, v in obj.items():
                if is_num(v):
                    key = f"{did}_{k}"[:60].replace("-", "_")
                    if key.replace("_", "").isalnum():
                        metrics[key] = float(v)
        rws = rows_of(obj)[:MAX_EX_PER_DS]
        exs: list[dict[str, Any]] = []
        for r in rws:
            num = {k: v for k, v in r.items() if is_num(v)}
            exs.append({
                "input": f"[{did}] {desc} :: {describe(r)}",
                "output": json.dumps({k: v for k, v in r.items() if k not in ("source_file", "source_key")},
                                     default=str)[:4000],
                "metadata_deliverable": did,
                "metadata_source_file": str(r.get("source_file", "")),
                "metadata_source_key": str(r.get("source_key", "")),
                "metadata_readout_class": str(r.get("readout_class", "")),
                **{f"eval_{k}": float(v) for k, v in list(num.items())[:8]
                   if k.replace("_", "").isalnum() and k[0].isalpha()},
            })
        if exs:
            datasets.append({"dataset": f"{did}_{fname[:-5]}", "examples": exs})

    if not datasets:
        raise SystemExit("no datasets assembled - refusing to write an empty eval_out.json")

    out = {
        "metadata": {
            "evaluation_name": "Iteration-5 re-derivation audit of every blocking number",
            "description": (
                "Every contested number in the iteration-4 draft re-derived from the JSON and .npy "
                "files written by iterations 2-4. No new data, no new method, no GPU, $0 API spend. "
                "The DISK is authoritative: where a re-derived value disagrees with published prose, "
                "the disk value stands and the prose value is logged as a contradiction."
            ),
            "primary_metric": "claim_match_rate = MATCH / (MATCH + MISMATCH)",
            "prereg_sha256": gate["prereg_sha256_now"],
            "self_check_gate_passed": gate["gate_passed"],
            "self_check_failures": gate["failures"],
            "run_invariant": (
                "The deliverable is the activation-level comparison of the three Qwen3-4B models and "
                "any metric built from it reads activations or weights of a SINGLE model. Logit-only "
                "and text-only readouts are baselines, not the result."
            ),
            "curated_metrics_missing": missing_curated,
            "deliverables_produced": gate["deliverables_present"],
            "deliverables_missing": gate["deliverables_missing"],
            "seed": 20260921,
            "bootstrap_B": 2000,
            "n_permutations": 20000,
        },
        "metrics_agg": metrics,
        "datasets": datasets,
    }
    (WS / "eval_out.json").write_text(json.dumps(out, indent=2))
    print(f"wrote eval_out.json: {len(metrics)} metrics, {len(datasets)} datasets, "
          f"{sum(len(d['examples']) for d in datasets)} examples")


if __name__ == "__main__":
    main()
