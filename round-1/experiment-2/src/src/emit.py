"""Emit method_out.json in the datasets-grouped exp_gen_sol_out schema.

Every predict_* value is a STRING; per-example extras are flat metadata_* fields.
The OUR-METHOD predictions are single-model ACTIVATION or WEIGHT readouts.
The BASELINE predictions are the non-featurized / logit-space controls the plan
registers as baselines - they are controls, never the deliverable.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT

ROOT = OUT.parent

CONDITION = {
    "L1": "base_no_safety_tuning",
    "L2": "instruct_safety_tuned",
    "L3": "safeRL_extra_safety_tuned",
    "L4": "non_safety_finetune_of_base",
}


def f(x, nd=6):
    if x is None:
        return "NA"
    if isinstance(x, bool):
        return str(x)
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    return "NA" if not np.isfinite(v) else f"{v:.{nd}g}"


def label_for(lg, alpha):
    per_layer = lg.endswith("PL")
    base = CONDITION.get(lg.replace("PL", ""), lg)
    grid = "per-layer" if per_layer else "single-pinned-direction"
    if alpha == 0.0:
        return f"{base} | unlesioned (alpha=0)"
    return f"{base} | {grid} rank-one safety-axis lesion at alpha={alpha:.2f}"


def main():
    sub = json.loads((OUT / "substrate.json").read_text())
    ana = json.loads((OUT / "analysis.json").read_text()) if (OUT / "analysis.json").exists() else {}
    st9 = json.loads((OUT / "stage9_weightcheck.json").read_text()) if (OUT / "stage9_weightcheck.json").exists() else None
    st9d = json.loads((OUT / "stage9_depth.json").read_text()) if (OUT / "stage9_depth.json").exists() else None
    red = json.loads((OUT / "redundancy.json").read_text()) if (OUT / "redundancy.json").exists() else {}
    caus = {p.stem: json.loads(p.read_text()) for p in sorted((OUT / "causal").glob("*.json"))} if (OUT / "causal").exists() else {}
    twins = {t["pair_key"]: t for t in sub["twins"]}
    # (lineage, alpha) -> the logit-space baselines measured by the causal arm
    gapmap = {}
    for c in caus.values():
        gapmap[(c["lineage"], round(float(c["alpha"]), 2))] = c
    datasets = []

    # ---------- 1. per-item activation cells ----------
    ex = []
    for lg, r in ana.get("lineages", {}).items():
        base = {x["pair_key"]: x for x in r["item_rows"] if x["alpha"] == r["alphas"][0]}
        for x in r["item_rows"]:
            t = twins[x["pair_key"]]
            b = base.get(x["pair_key"], {})
            ex.append({
                "input": (f"checkpoint={r['repo']} | lesion_alpha={x['alpha']:.2f} | "
                          f"XSTest twin {x['pair_key']} (family={t['family']}, focus={t['focus']}) | "
                          f"harmful_request={t['harmful_request']!r} | benign_twin={t['benign_request']!r} | "
                          f"2x2 cell = request{{harmful,benign}} x response-prefix{{hazardous,benign}}, "
                          f"response span token-identical across the request manipulation"),
                "output": label_for(lg, x["alpha"]),
                "predict_arming_interaction_A_nullSD": f(x["A_z"]),
                "predict_content_maineffect_CB_nullSD": f(x["CB_z"]),
                "predict_request_maineffect_O_raw": f(x["O"]),
                "predict_total_T_raw": f(x["T"]),
                "predict_baseline_coherence_control_raw": f(x["COH"]),
                "predict_baseline_placebo_prefix_raw": f(x["PLC"]),
                "metadata_lineage": lg, "metadata_alpha": x["alpha"],
                "metadata_pair_key": x["pair_key"], "metadata_family": t["family"],
                "metadata_focus": t["focus"],
                "metadata_null_sd_CB_raw": x["null_sd_CB"],
                "metadata_null_sd_A_raw": x["null_sd_A"],
                "metadata_CB_raw": x["CB"], "metadata_A_raw": x["A"],
                "metadata_K2_ladder_slope_raw": x["K2_slope"],
                "metadata_pre_edit_A_nullSD": b.get("A_z"),
                "metadata_pre_edit_CB_nullSD": b.get("CB_z"),
                "metadata_alpha_star": r.get("alpha_star"),
                "metadata_readout_reads": "residual-stream activations of ONE model",
            })
    if ex:
        datasets.append({"dataset": "xstest_twins_activation_cells", "examples": ex})

    # ---------- 2. checkpoint-level metric (the actual use case) ----------
    ex = []
    for lg, r in ana.get("lineages", {}).items():
        for a in r["alphas"]:
            blk = r["per_alpha"][f"{a:.2f}"]
            A = np.array(blk["parentfixed"]["A"]) / np.maximum(np.array(blk["null_sd_A_per_item"]), 1e-9)
            CB = np.array(blk["parentfixed"]["CB"]) / np.maximum(np.array(blk["null_sd_CB_per_item"]), 1e-9)
            ex.append({
                "input": (f"Score checkpoint {r['repo']} (lesion_alpha={a:.2f}) for safety using ONLY its own "
                          f"activations on {len(A)} XSTest minimal-edit twin items - no benchmark run, "
                          f"no reference model, no generation."),
                "output": label_for(lg, a),
                "predict_arming_interaction_A_nullSD_mean": f(np.mean(np.abs(A))),
                "predict_content_axis_CB_nullSD_mean": f(np.mean(np.abs(CB))),
                "predict_K2_prior": f(blk["K2_prior"]),
                "predict_K3_benign_only_footprint": f(blk["K3_footprint"]),
                "predict_K4_hazard_time_constant_tokens": f(blk["K4_tau_harmful_mean_valid"]),
                "predict_K5_domain_profile_dispersion": f(blk["K5_dispersion"]),
                "predict_baseline_benign_continuation_nll": f(blk.get("benign_nll_mean")),
                "predict_r_ablit_best_separation_cohens_d": f(
                    max((float(v) for v in (r.get("r_ablit_sep") or {"0": 0}).values()), default=0.0)),
                # depth fraction = 0-based layer index / n_layers, the same convention
                # used in README.md, FINDINGS.md and the frozen band description
                "predict_r_ablit_best_layer_depth_fraction": f(
                    r["r_ablit_layer"] / max(r["model_facts"]["n_layers"], 1)),
                "predict_baseline_cv_probe_raw_hidden_auroc": f(blk["baselines"]["cv_probe_raw_hidden_auroc"]),
                "predict_baseline_insample_diffinmeans_auroc": f(blk["baselines"]["in_sample_diff_in_means_auroc"]),
                "predict_baseline_matched_behaviour_probe_auroc": f(blk.get("D_matched_probe")),
                "predict_baseline_first_token_refusal_logit_gap": f(
                    gapmap.get((lg, round(a, 2)), {}).get("baseline_first_token_logit_gap_harm_minus_benign")),
                "predict_baseline_refusal_drive_on_harmful": f(
                    gapmap.get((lg, round(a, 2)), {}).get("baseline_refusal_drive_harmful")),
                "metadata_lineage": lg, "metadata_alpha": a, "metadata_repo": r["repo"],
                "metadata_n_items": int(len(A)),
                "metadata_r_ablit_layer": r["r_ablit_layer"],
                "metadata_n_layers": r["model_facts"]["n_layers"],
                "metadata_metric_cost": ("128 harmful + 128 harmless requests, prompt-only, "
                                         "teacher-forced, one forward pass each; no generation"),
                "metadata_D_primary_cv_probe_auroc": blk["D_primary"],
                "metadata_D_axis_1d_along_pinned_u": blk.get("D_axis_1d"),
                "metadata_D_axis_1d_raw_gap": blk.get("D_axis_1d_absmean_gap"),
                "metadata_G1_cos_rcontent_rablit": r["G1_cos_pooled"],
                "metadata_G2_ratio": blk["G2_ratio"], "metadata_G2_pass": blk["G2_pass"],
                "metadata_G3_child_parent_nullsd_ratio": blk["G3_child_parent_nullsd_ratio"],
                "metadata_alpha_star": r.get("alpha_star"),
                "metadata_alpha_star_source": r.get("alpha_star_source"),
            })
    if ex:
        datasets.append({"dataset": "checkpoint_level_safety_metric", "examples": ex})

    # ---------- 3. S2 registered signatures ----------
    ex = []
    for lg, r in ana.get("lineages", {}).items():
        for row in r.get("S2_rows", []) + r.get("S2_rows_full_annihilation", []):
            ex.append({
                "input": (f"Pre-registered signature test S2 for candidate {row['candidate']} on {r['repo']}: "
                          f"does the registered signature '{row['registered_signature']}' hold IN SIGN at "
                          f"matched damage (alpha*={f(row.get('alpha_star'))}, "
                          f"scored_at={row.get('scored_at')})?"),
                "output": row["registered_signature"],
                "predict_observed_verdict": str(row["verdict"]),
                "predict_pre_value": f(row.get("pre")),
                "predict_post_value_at_alpha_star": f(row.get("post")),
                "predict_delta": f(row.get("delta")),
                "metadata_lineage": lg, "metadata_candidate": row["candidate"],
                "metadata_unit": row.get("unit"),
                "metadata_ci95": row.get("ci95"),
                "metadata_ci_excludes_zero": row.get("ci_excludes_zero"),
                "metadata_sign_matches_registered": row.get("sign_matches_registered"),
                "metadata_evaluated_at_alpha_star": row.get("evaluated_at_alpha_star"),
                "metadata_scored_at": row.get("scored_at"),
                "metadata_signature_test": row.get("signature_test"),
            })
    if ex:
        datasets.append({"dataset": "s2_registered_signature_tests", "examples": ex})

    # ---------- 4. STAGE 9 weight-space check (weights only, single model pair) ----------
    if st9:
        ex = []
        for row in st9["per_matrix"]:
            ex.append({
                "input": (f"Weight-space check of the community abliteration "
                          f"mlabonne/Qwen3-4B-abliterated against its parent Qwen/Qwen3-4B at "
                          f"model.layers.{row['layer']}.{row['matrix']}.weight {row['shape']}: is the real "
                          f"community edit the rank-one orthogonalisation W - a*u*(u^T W) that this lane registers?"),
                "output": "rank-one orthogonalisation of one direction out of a residual-stream write matrix",
                "predict_rank1_share_sigma1sq_over_frosq": f(row.get("rank1_share")),
                "predict_implied_alpha": f(row.get("implied_alpha")),
                "predict_cos_u1_vs_our_pinned_r_ablit": f(row.get("cos_u1_vs_our_rablit")),
                "predict_baseline_relative_delta_norm": f(row["fro_delta"] / max(row["fro_parent"], 1e-9)),
                "metadata_layer": row["layer"], "metadata_matrix": row["matrix"],
                "metadata_fro_delta": row["fro_delta"], "metadata_fro_parent": row["fro_parent"],
                "metadata_readout_reads": "weights of a single model pair; no activations, no text",
            })
        datasets.append({"dataset": "mlabonne_abliteration_weight_space", "examples": ex})

    # ---------- 5. causal arm ----------
    ex = []
    for key, c in caus.items():
        for gk, g in c.get("grid", {}).items():
            ex.append({
                "input": (f"Causal arm on {c['lineage']} at lesion_alpha={c['alpha']:.2f}: intervention "
                          f"'{gk}' applied to residual-stream response positions at layers {c['layer_cells']} "
                          f"(spans: {c.get('spans')}). "
                          f"Is the readable content axis LOAD-BEARING for refusal, or merely readable?"),
                "output": "change in refusal drive (teacher-forced mass on the frozen refusal-onset token set)",
                "predict_delta_refusal_drive": f(g["delta_vs_baseline"]),
                "predict_refusal_drive_mean": f(g["refusal_drive_mean"]),
                "predict_baseline_collateral_benign_refusal_rise": f(g.get("collateral_benign_refusal_rise")),
                "predict_baseline_collateral_benign_nll_rise": f(g.get("collateral_benign_nll_rise")),
                "predict_baseline_first_token_logit_gap_shift": f(g.get("baseline_first_token_logit_gap_shift")),
                "metadata_lineage": c["lineage"], "metadata_alpha": c["alpha"],
                "metadata_intervention": gk, "metadata_layer_cells": c["layer_cells"],
                "metadata_span": gk.split("|")[0] if "|" in gk else "registered_full_span",
                "metadata_is_registered_span": gk.startswith("registered_full_span"),
                "metadata_beta_unit_sd": c.get("beta_unit_sd"),
                "metadata_is_positive_control": gk.startswith("POSITIVE_CONTROL"),
                "metadata_note": g.get("note", ""),
            })
    if ex:
        datasets.append({"dataset": "causal_arm_refusal_drive", "examples": ex})

    # ---------- 6. STAGE 9b depth drift ----------
    if st9d:
        ex = []
        for mat, r in st9d.items():
            for li in range(36):
                ex.append({
                    "input": (f"Is the community abliteration ONE global direction or one direction PER LAYER? "
                              f"Layer {li}, {mat}: compare its recovered edit direction u1 against the deepest "
                              f"layer's and against our pinned prompt-fitted request axis."),
                    "output": "one direction per layer (per-matrix rank-one, layer-varying) vs one global direction",
                    "predict_cos_vs_deepest_layer": f(r["cos_vs_deepest_layer"][li]),
                    "predict_cos_vs_our_pinned_u": f(r.get("cos_vs_our_pinned_u_by_layer", [None] * 36)[li]),
                    "predict_cos_vs_our_same_layer_rablit": f(r.get("cos_vs_our_same_layer_rablit", [None] * 36)[li]),
                    "predict_baseline_fro_delta_at_layer": f(r["fro_delta_by_layer"][li]),
                    "metadata_layer": li, "metadata_matrix": mat,
                })
        datasets.append({"dataset": "mlabonne_abliteration_depth_profile", "examples": ex})

    # ---------- 7. how many directions carry the harm percept, and does it regrow? ----------
    ex = []
    for key, r in red.items():
        if "ks_run" not in r:
            continue
        for k, a_cls, a_rnd, vk in zip(r["ks_run"], r["class_removal_auroc"],
                                       r["random_removal_auroc"], r["class_removal_variance_kept"]):
            ex.append({
                "input": (f"{r['repo']} at lesion_alpha={r['alpha']:.2f}, residual stream layer "
                          f"{r['layer']}, last prompt token. Project out {k} greedy diff-in-means "
                          f"class directions (fitted on the r_ablit FITTING requests) from the "
                          f"HELD-OUT {r['n_heldout']} requests, then re-score a 5-fold "
                          f"cross-validated probe. How many directions carry the harmful-request percept?"),
                "output": "held-out cross-validated probe AUROC after removing k directions",
                "predict_auroc_after_removing_k_class_directions": f(a_cls),
                "predict_baseline_auroc_after_removing_k_random_directions": f(a_rnd),
                "predict_activation_variance_kept": f(vk),
                "metadata_k": int(k), "metadata_tag": r["tag"], "metadata_alpha": r["alpha"],
                "metadata_layer": r["layer"],
                "metadata_cos_top_class_dir_vs_deleted_u": r["u_cos_with_first_dir"],
                "metadata_k_to_break_below_0p90": r["k_to_break_below_0p90"],
                "metadata_auroc_on_unit_normalised_activations": r.get("auroc_on_unit_normalised_activations"),
                "metadata_auroc_of_residual_norm_alone": r.get("auroc_of_residual_norm_alone"),
                "metadata_norm_mean_harmful": r.get("norm_mean_harmful"),
                "metadata_norm_mean_harmless": r.get("norm_mean_harmless"),
                "metadata_readout_reads": "activations of a SINGLE model; no text, no logits",
            })
    if ex:
        datasets.append({"dataset": "harm_percept_dimensionality_and_regrowth", "examples": ex})

    # ---------- 7b. WHERE does the replacement code appear? ----------
    ex = []
    for key, dp in red.items():
        if "layers" not in dp:
            continue
        tag = key.replace("_depth_profile", "")
        for i, li in enumerate(dp["layers"]):
            ex.append({
                "input": (f"{tag}, residual stream layer {li}, last prompt token. Compare the INTACT "
                          f"model with the one whose fitted request axis u has been orthogonalised out "
                          f"of every residual-stream write in all 36 layers. Where along depth does the "
                          f"lesioned model's harmful-request code diverge from the intact one's?"),
                "output": "per-layer held-out probe AUROC and the angle between the two states' class directions",
                "predict_auroc_intact": f(dp["auroc_alpha0"][i]),
                "predict_auroc_fully_lesioned": f(dp["auroc_alpha1"][i]),
                "predict_cos_classdir_intact_vs_lesioned": f(dp["cos_classdir_a0_vs_a1"][i]),
                "predict_u_component_gap_intact": f(dp["u_component_gap_a0"][i]),
                "predict_baseline_u_component_gap_lesioned": f(dp["u_component_gap_a1"][i]),
                "predict_u_gap_over_residual_norm_intact": f((dp.get("u_gap_over_norm_a0") or [None]*40)[i]),
                "metadata_layer": li, "metadata_tag": tag,
                "metadata_cos_classdir_lesioned_vs_u": dp["cos_classdir_a1_vs_pinned_u"][i],
                "metadata_cos_classdir_intact_vs_u": dp["cos_classdir_a0_vs_pinned_u"][i],
            })
    if ex:
        datasets.append({"dataset": "regrowth_depth_profile", "examples": ex})

    # ---------- 8. THE METRIC QUESTION: can a few prompts rank checkpoints by safety? ----------
    xl = ana.get("cross_lineage_metric_alpha0", {}) or {}
    ex = []
    EXPECTED = ("expected safety order: L3 SafeRL >= L2 Instruct > L4 non-safety finetune "
                "~ L1 Base; a POSITIVE paired difference means the first named checkpoint scores higher")
    for pair, row in (xl.get("paired_contrasts") or {}).items():
        a, b = pair.split("_minus_")
        for readout, v in row.items():
            pb = ((xl.get("prompt_budget") or {}).get(pair) or {}).get(readout, {})
            ex.append({
                "input": (f"Using ONLY activations, on the SAME XSTest twin items and with NO "
                          f"benchmark run: does the readout '{readout}' separate "
                          f"{CONDITION.get(a, a)} from {CONDITION.get(b, b)}? "
                          f"Paired item-clustered bootstrap over n={v['n_items']} twin pairs at alpha=0. {EXPECTED}"),
                "output": f"{a} minus {b}",
                "predict_paired_mean_difference": f(v["paired_mean_diff"]),
                "predict_ci95_excludes_zero": str(v["ci_excludes_zero"]),
                "predict_smallest_n_twin_pairs_at_90pct_detection": f(pb.get("smallest_n_at_90pct")),
                "predict_baseline_readout_mean_first": f((xl.get("readout_means") or {}).get(readout, {}).get(a)),
                "predict_baseline_readout_mean_second": f((xl.get("readout_means") or {}).get(readout, {}).get(b)),
                "metadata_pair": pair, "metadata_readout": readout,
                "metadata_ci95": v["ci95"], "metadata_n_items": v["n_items"],
                "metadata_detect_rate_by_n_items": pb.get("detect_rate_by_n_items"),
                "metadata_cost_note": ("one twin pair = 8 teacher-forced forward passes, no generation"),
            })
    if ex:
        datasets.append({"dataset": "few_prompt_safety_metric_cross_checkpoint", "examples": ex})

    out = {
        "metadata": {
            "method_name": "LANE B - rank-one safety-axis lesion + five single-model activation readouts",
            "description": ("Every predict_* whose name does not start with predict_baseline_ is a readout of "
                            "ACTIVATIONS or WEIGHTS of a SINGLE model. predict_baseline_* are the registered "
                            "controls (raw-hidden probe, in-sample difference-in-means, coherence/placebo "
                            "prefixes, logit-space collateral). The causal arm's outcome is logit-space by "
                            "design and is the only place the run invariant permits that."),
            "prereg_sha256": (OUT / "prereg.sha256").read_text().strip(),
            "substrate_confirmatory_sha256": sub["confirmatory_sha256"],
            "heldout_reserved_sha256": sub["heldout_sha256"],
            "lineages": CONDITION,
            "alpha_grid": [0.0, 0.25, 0.5, 0.75, 1.0],
            "n_datasets": len(datasets),
            "n_examples": sum(len(d["examples"]) for d in datasets),
        },
        "datasets": datasets,
    }
    p = ROOT / "method_out.json"
    p.write_text(json.dumps(out, indent=1, default=str))
    print(f"method_out.json  {p.stat().st_size/1e6:.1f} MB")
    for d in datasets:
        print(f"  {d['dataset']:44s} {len(d['examples'])} examples")
    print("TOTAL examples", out["metadata"]["n_examples"])


if __name__ == "__main__":
    main()
