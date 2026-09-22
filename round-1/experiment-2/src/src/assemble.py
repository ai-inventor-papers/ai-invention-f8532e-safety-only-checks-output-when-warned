"""Assemble results.json from every stage. Runs T7 end-to-end validation."""
from __future__ import annotations
import hashlib, json, subprocess, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT

ROOT = OUT.parent


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_text().encode()).hexdigest()


def load(p: Path, default=None):
    return json.loads(p.read_text()) if p.exists() else default


def main():
    sub = load(OUT / "substrate.json")
    prereg = load(OUT / "prereg.json")
    t0json = load(OUT / "sanity_T0.json")
    pilot = load(OUT / "pilot.json")
    ana = load(OUT / "analysis.json", {})
    st9 = load(OUT / "stage9_weightcheck.json")
    st9d = load(OUT / "stage9_depth.json")
    causal = {p.stem: load(p) for p in sorted((OUT / "causal").glob("*.json"))} if (OUT / "causal").exists() else {}

    # ---------------- T7 ----------------
    T7 = {}
    T7["prereg_sha256_now"] = sha_file(OUT / "prereg.json")
    T7["prereg_sha256_at_T0"] = (OUT / "prereg.sha256").read_text().strip()
    T7["prereg_unchanged"] = T7["prereg_sha256_now"] == T7["prereg_sha256_at_T0"]

    held = set(sub["heldout_ids"])
    leaked = []
    for lg, r in ana.get("lineages", {}).items():
        for row in r.get("item_rows", []):
            if row["pair_key"] in held:
                leaked.append((lg, row["pair_key"]))
    T7["heldout_54_absent_from_every_record"] = len(leaked) == 0
    T7["heldout_leaks"] = leaked[:10]

    bad_alpha = []
    for lg, r in ana.get("lineages", {}).items():
        for row in r.get("S2_rows", []):
            if row.get("post") is not None and not row.get("evaluated_at_alpha_star"):
                bad_alpha.append((lg, row["candidate"]))
    T7["every_S2_row_evaluated_at_alpha_star"] = len(bad_alpha) == 0

    # ---------------- example-level rows ----------------
    rows = []
    for lg, r in ana.get("lineages", {}).items():
        astar = r.get("alpha_star")
        a0 = r["alphas"][0]
        pre = {x["pair_key"]: x for x in r["item_rows"] if x["alpha"] == a0}
        for a in r["alphas"]:
            for x in r["item_rows"]:
                if x["alpha"] != a:
                    continue
                p = pre.get(x["pair_key"], {})
                rows.append({
                    "lineage": lg, "repo": r["repo"], "alpha": a,
                    "alpha_star": astar, "is_alpha_star_bracket": astar is not None,
                    "pair_key": x["pair_key"],
                    "O_raw": x["O"], "CB_raw": x["CB"], "A_raw": x["A"], "T_raw": x["T"],
                    "CB_under_harmful_request_raw": x["CB_harm"],
                    "coherence_control_raw": x["COH"], "placebo_raw": x["PLC"],
                    "null_sd_CB_raw": x["null_sd_CB"], "null_sd_A_raw": x["null_sd_A"],
                    "CB_nullSD_units": x["CB_z"], "A_nullSD_units": x["A_z"],
                    "K2_slope_raw": x["K2_slope"],
                    "pre_CB_nullSD_units": p.get("CB_z"), "pre_A_nullSD_units": p.get("A_z"),
                    "delta_CB_vs_alpha0_nullSD": (x["CB_z"] - p["CB_z"]) if p else None,
                    "delta_A_vs_alpha0_nullSD": (x["A_z"] - p["A_z"]) if p else None,
                })
    T7["n_example_level_rows"] = len(rows)
    T7["at_least_50_rows"] = len(rows) >= 50

    # ---------------- integrity / damage / S2 blocks ----------------
    integrity, damage, s2_table, readouts = {}, {}, [], {}
    for lg, r in ana.get("lineages", {}).items():
        a0 = f"{r['alphas'][0]:.2f}"
        integrity[lg] = {
            "G1_cos_r_content_vs_r_ablit_pooled": r["G1_cos_pooled"],
            "G1_cos_per_layer": r["G1_cos_per_layer"],
            "G1_max": r["G1_max"], "G1_pass": r["G1_pass"],
            "G1_note": ("This cosine has never been published for a RESPONSE-fitted continuation axis "
                        "against a PROMPT-fitted request axis. It is a RESULT of this lane, not only a gate."),
            "G2_ratio": {a: r["per_alpha"][a]["G2_ratio"] for a in r["per_alpha"]},
            "G2_pass": {a: r["per_alpha"][a]["G2_pass"] for a in r["per_alpha"]},
            "G3_cos_r_parent_vs_r_child": {a: r["per_alpha"][a]["G3_cos_rparent_rchild"] for a in r["per_alpha"]},
            "G3_child_parent_nullsd_ratio": {a: r["per_alpha"][a]["G3_child_parent_nullsd_ratio"] for a in r["per_alpha"]},
            "r_content_split_half_cosine": r["r_content_split_half_cosine"],
            "r_content_stability_gate_pass": r["r_content_stability_gate_pass"],
            "annihilation_residue": not (r["G1_pass"] and all(r["per_alpha"][a]["G2_pass"] for a in r["per_alpha"])),
        }
        damage[lg] = {
            "alphas": r["alphas"],
            "D_primary_registered_cv_probe_auroc": r["D_curve"],
            "D_primary_null": r["D_null"], "D_primary_target": r["D_target"],
            "D_primary_flat": r.get("D_flat"),
            "alpha_star_primary": r.get("alpha_star_primary"),
            "D_secondary_registered_O_term_nullSD": r["D_secondary_curve"],
            "D_secondary_null": r["D_secondary_null"], "D_secondary_target": r["D_secondary_target"],
            "alpha_star_secondary": r.get("alpha_star_secondary"),
            "alpha_star_used": r.get("alpha_star"), "alpha_star_source": r.get("alpha_star_source"),
            "diagnostic_D_axis_1d_along_pinned_u": r.get("D_axis_1d_curve"),
            "diagnostic_D_axis_1d_raw_gap": r.get("D_axis_1d_gap_curve"),
            "diagnostic_D_axis_1d_gap_normalised": r.get("D_axis_1d_gap_normalised"),
            "diagnostic_D_axis_1d_gap_expected_1_minus_alpha": r.get("D_axis_1d_gap_expected_1_minus_alpha"),
            "diagnostic_note": ("AUROC along u is invariant to a positive rescaling of the u-component "
                                "and the lesion rescales exactly that component by (1-alpha), so the "
                                "AUROC cannot move for alpha<1 however well the edit works. The raw gap "
                                "is the sensitive companion."),
            "diagnostic_D_matched_behaviour_probe": r.get("D_matched_probe_curve"),
            "diagnostic_D_matched_behaviour_axis_1d": r.get("D_matched_axis_curve"),
            "monotone_primary": r["D_monotone"], "monotone_secondary": r.get("D_secondary_monotone"),
            "coherence_benign_nll_curve": r.get("coherence_benign_nll_curve"),
            "coherence_neutral_nll_curve": r.get("coherence_neutral_nll_curve"),
            "coherence_note": ("teacher-forced NLL of BENIGN continuations at each alpha. A lesion that "
                               "merely breaks the model raises this; a lesion that removes a safety "
                               "component should not."),
        }
        readouts[lg] = {
            a: {k: v for k, v in blk.items()
                if k in ("K2_prior", "K3_footprint", "K4_tau_harmful_mean_valid",
                         "K4_tau_benign_mean_valid", "K4_valid_frac", "K5_profile",
                         "K5_dispersion", "null_sd_CB_mean", "null_sd_A_mean",
                         "nll_penalty_safety_crossing", "nll_penalty_coherence_crossing",
                         "A_net_licensed", "baselines", "D_primary", "D_secondary_O",
                         "D_axis_1d", "D_matched_probe", "D_matched_axis_1d")}
            for a, blk in r["per_alpha"].items()
        }
        for row in r["S2_rows"]:
            s2_table.append({"lineage": lg, **row})
        for row in r.get("S2_rows_full_annihilation", []):
            s2_table.append({"lineage": lg, **row})

    deviations = []
    for lg, r in ana.get("lineages", {}).items():
        for d in r.get("deviations", []):
            deviations.append(f"[{lg}] {d}")
    deviations += [
        ("THE EDIT IS APPLIED AS AN OUTPUT PROJECTION, NOT A WEIGHT MUTATION. Qwen3 gives o_proj and "
         "down_proj no bias, so for y = W0 x the registered edit W(a) = W0 - a u (u^T W0) satisfies "
         "W(a) x = y - a u (u^T y) EXACTLY. Applying it as an output hook makes alpha=0 a bitwise "
         "no-op and the restore exact, and proves embed_tokens is untouched. Verified against a "
         "genuine weight mutation - see hook_sanity.equivalence."),
        ("DISK LEDGER SUPERSEDED. The plan's 9 GB cap assumed a 40 GB disk; that was `df /` on the "
         "docker overlay. The working tree is on a 2.2 PB MooseFS mount with 715 TB free and all five "
         "checkpoints were already in the shared HF cache, so no checkpoint was downloaded, none was "
         "deleted, and no shard-wise F32->bf16 cast was needed for L4."),
        ("L4 PARENTAGE RESOLVED. CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 ships an lm_head tensor "
         "in its checkpoint but its own config.json sets tie_word_embeddings=true, so the loaded model "
         "ties lm_head to embed_tokens exactly as L1-L3 do. The tied-embedding confound therefore "
         "applies to ALL FOUR lineages, not to L1-L3 only as the plan anticipated."),
        ("walledai/AdvBench is GATED (403). Per F5 it was treated as NOT FOUND and the ungated mirror "
         "S3IC/advbench was used for the harmful request pool instead."),
        ("DECLARED ADDITION (diagnostics only, prereg.json byte-identical): a matched-behaviour request "
         "axis from JailbreakBench JBB-Behaviors, and a one-dimensional readout along the pinned u. "
         "Neither replaces a registered readout."),
        ("BASE-LINEAGE TEMPLATE, stated deviation. The plan asks the BASE arms (L1, and L4 which "
         "is a base fine-tune) to be run BOTH with the instruct chat-template string verbatim and "
         "in plain completion format, with a qualitative-agreement check between the two. Only the "
         "plain completion format was run. Reason and scope: the headline result is a WITHIN-lineage "
         "alpha=0 vs alpha=1 comparison at identical token spans, so it does not rest on "
         "cross-lineage span comparability; the cross-lineage readout table does, and is therefore "
         "labelled as resting on a template difference between the instruct arms (L2, L3) and the "
         "base arms (L1, L4). The '</think>' span assertion is applied to the instruct arms only, "
         "and is asserted, not assumed."),
        ("CAUSAL-ARM SPAN, declared addition (prereg.json byte-identical). The registered "
         "outcome is refusal-onset mass at the position IMMEDIATELY AFTER the intervened span, "
         "and the registered span is the whole 128-token response prefix. That position sits deep "
         "inside a forced expository passage, where refusal-onset mass has a FLOOR (~1e-6 in a "
         "pilot), so a null there could not be told apart from a floor effect. The registered "
         "readout is reported unchanged, and a SHORT-SPAN variant (first 8 response tokens, read "
         "immediately after) is reported ALONGSIDE it under the label short_span_8. Both use the "
         "same frozen refusal-onset token set, the same beta grid and the same matched-norm "
         "orthogonal control."),
        ("DECLARED SECONDARY GRID (prereg.json byte-identical). STAGE 9 was pre-registered as a "
         "descriptive weight-space check, and it returned a fact the registered edit did not "
         "anticipate: the real community abliteration is per-matrix rank-one but its direction "
         "ROTATES WITH DEPTH - the shallowest and deepest layers' edit directions are orthogonal "
         "(|cos| = 0.016), while adjacent layers sit at |cos| = 0.773, and the two write matrices "
         "INSIDE a layer share one direction. A single pinned direction is therefore not the "
         "faithful replica. The registered single-direction grid is reported in full and unchanged; "
         "a per-layer grid is reported ALONGSIDE it, scored under its own >=3-of-4 rule, never pooled "
         "with the registered one."),
    ]

    # ---------------- release the fitted directions (plan: OUTPUTS) ----------------
    import numpy as np
    rel = OUT / "released_directions"
    rel.mkdir(exist_ok=True)
    released = {}
    for f in sorted((OUT / "harvest").glob("*_dirs.npz")):
        z = np.load(f)
        tag = f.stem.replace("_dirs", "")
        np.savez_compressed(rel / f"{tag}_r_ablit.npz", **{k: z[k] for k in z.files})
        released[tag] = {"keys": list(z.files), "d_model": int(z["u"].shape[0]),
                         "u_is": "the pinned prompt-fitted request axis (r_ablit) at the selected layer",
                         "ra_L_is": "r_ablit fitted at layer L (all 36 layers released)"}
    pd = OUT / "pilot_dirs.npz"
    if pd.exists():
        z = np.load(pd)
        np.savez_compressed(rel / "pilot_r_content_band.npz", **{k: z[k] for k in z.files})
        released["pilot_r_content"] = {"keys": list(z.files),
                                       "rc_L_is": "r_content fitted at band layer L on the 64-pair corpus"}
    res_released = released

    res = {
        "artifact": "LANE B - Erase the safety signal, remeasure",
        "run": "run_YqmEFECOIR3D / iter_1 / gen_art_experiment_2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run_invariant": prereg["invariant"],
        "prereg_sha256": T7["prereg_sha256_now"],
        "substrate_sha256": prereg["substrate_sha256"],
        "confirmatory_sha256": sub["confirmatory_sha256"],
        "heldout_sha256": sub["heldout_sha256"],
        "prereg": prereg,
        "substrate_summary": {
            "n_twins": len(sub["twins"]), "n_confirmatory": len(sub["confirmatory_ids"]),
            "n_heldout_reserved": len(sub["heldout_ids"]),
            "families": sub["families"], "sources": sub["sources"],
            "focus_join_disagreements": sub["focus_join_disagreements"],
            "n_fit_content_pairs": len(sub["fit_content"]),
            "n_fit_ablit": {k: len(v) for k, v in sub["fit_ablit"].items()},
            "n_heldout_damage": {k: len(v) for k, v in sub["heldout_damage"].items()},
            "n_domain_rows": len(sub["domain_set"]),
        },
        "sanity": {"T0": t0json, "T1": pilot.get("T1"), "T2": pilot.get("T2"),
                   "T3": pilot.get("T3"), "T7": T7,
                   "band_selection": {
                       "band": pilot.get("band"), "depth_fraction": pilot.get("band_depth_fraction"),
                       "split_half_cosine_band_mean": pilot.get("r_content_split_half_cosine_band_mean"),
                       "selected_on": "the 64-pair fitting corpus ONLY, then frozen for every lineage and alpha"},
                   "pilot_confirmation_CB_nullSD": pilot.get("confirmation_CB_z_mean"),
                   "achieved_r_SDreal_over_SDnull": pilot.get("achieved_r_SDreal_over_SDnull"),
                   "power_note": ("Registered thresholds were sized at r ~ 1.2, n = 96, which is "
                                  "60-70% power, not 80%. The achieved r is reported above whatever it is; "
                                  "no threshold was re-tuned after seeing it.")},
        "integrity_gates": integrity,
        "damage_curves": damage,
        "grid_of": {lg: ("per_layer_r_ablit" if lg.endswith("PL") else "single_pinned_r_ablit")
                    for lg in ana.get("lineages", {})},
        "readouts_by_alpha": readouts,
        "cross_lineage_metric_alpha0": ana.get("cross_lineage_metric_alpha0", {}),
        "prompt_budget": ana.get("cross_lineage_metric_alpha0", {}).get("prompt_budget", {}),
        "S2_table": s2_table,
        "S2_verdicts": ana.get("S2_verdicts", {}),
        "S2_verdicts_perlayer_grid": ana.get("S2_verdicts_perlayer_grid", {}),
        "S2_verdicts_full_annihilation_companion": ana.get("S2_verdicts_full_annihilation_companion", {}),
        "S2_verdicts_full_annihilation_perlayer": ana.get("S2_verdicts_full_annihilation_perlayer", {}),
        "DiD": ana.get("DiD", {}),
        "causal_arm": causal,
        "hook_sanity": {
            "from_pilot_T3": (pilot.get("T3") or {}),
            "per_causal_run": {k: {kk: vv for kk, vv in c.items()
                                   if kk.startswith("hook_sanity") or kk in
                                   ("control_cos_rcontent", "control_cos_rablit",
                                    "cos_rcontent_rablit", "beta_unit_sd", "spans",
                                    "refusal_tokens_decoded", "comply_token_ids")}
                              for k, c in causal.items()},
            "required": ["null patch self->self bitwise identical",
                         "matched-norm random direction ~0 effect",
                         "beta=0 exactly 0",
                         "full-residual patch (LABELLED positive control) moves the outcome"],
            "note": ("The positive control can NEVER carry the claim: patching the mean BENIGN "
                     "residual at the same positions also moves refusal at every layer."),
        },
        "harm_percept_dimensionality_and_regrowth": load(OUT / "redundancy.json", {}),
        "stage9_weight_space": st9,
        "stage9b_depth_profile_of_the_community_edit": st9d,
        "example_rows": rows,
        "released_directions": res_released,
        "deviations": deviations,
        "ledger": {
            "gpu": "1x NVIDIA RTX A4500, 20470 MiB, shared with 3 sibling artifacts",
            "peak_vram_gb_pilot": pilot.get("peak_vram_gb"),
            "disk": "working tree on MooseFS (2.2 PB, 715 TB free); overlay / is 40 GB but unused",
            "lineage_timings_s": {lg: load(OUT / "harvest" / f"{lg}_meta.json", {}).get("total_s")
                                  for lg in ("L1", "L2", "L3", "L4",
                                             "L1PL", "L2PL", "L3PL", "L4PL")},
        },
    }
    p = OUT.parent / "results.json"
    p.write_text(json.dumps(res, indent=1, default=str))
    mb = p.stat().st_size / 1e6
    print(f"results.json  {mb:.1f} MB   example rows {len(rows)}")
    print(json.dumps(T7, indent=1, default=str))
    return res


if __name__ == "__main__":
    main()
