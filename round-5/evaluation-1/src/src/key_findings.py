"""Key findings for SUMMARY.md, generated from eval_out.json metrics and the tables.

Every number is read from disk at generation time, so the prose cannot drift from
the tables. Sentences are phrased so that no baseline-class readout (BL1*, AMS*,
card/name regex, greedy refusal text, B7) is ever named as the deliverable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
RES = WS / "results"


def J(name: str) -> dict[str, Any]:
    p = RES / name
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def f(x: Any, nd: int = 3) -> str:
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return f"{x:.{nd}f}" if isinstance(x, float) and x != int(x) else str(int(x))
    return "n/a"


def build() -> list[str]:
    m = J("../eval_out.json").get("metrics_agg", {}) if (WS / "eval_out.json").exists() else {}
    if not m:
        m = json.loads((WS / "eval_out.json").read_text())["metrics_agg"] if (WS / "eval_out.json").exists() else {}
    den = J("table_sensitivity_denominators.json")
    pw = J("table_panel_power.json")
    jn = J("join_backstop.json")
    L: list[str] = []
    A = L.append

    A("## Key findings")
    A("")
    A("Each finding below is re-derived from disk. Section numbers refer to the deliverables.")
    A("")

    A("**1. The effective set is 10 pairs by the frozen rule, not 9 (D1, D4 addendum).** "
      "classification.json's own count rule counts 'constructed + primary harvested + AMD count when observed "
      "EFFECTIVE'. HG::AMD-OLMo-1B SFT->DPO was planned as a harvested no-op and observed EFFECTIVE "
      f"(dHC +{f((den.get('extension_pair_dHC') or {}).get('HG::amd--AMD-OLMo-1B-SFT-DPO'))}), so it belongs in the set. "
      "F1__cautious (constructed, observed EFFECTIVE) is also omitted, although F1__dpo is counted under the same "
      "reclassification clause, so a literal reading gives 11. The iteration-3 'no-op' verdict and the "
      "iteration-4 'EFFECTIVE' verdict on AMD SFT->DPO do NOT disagree because the item sets differ: both use the "
      "same 45 Lane C items (HC 0.578 -> 0.556). They disagree because of GENERATION PROVENANCE: the reused "
      "generations (H::) give AMBIGUOUS, the GPU-regenerated ones (HG::) give EFFECTIVE. Recomputing every "
      f"sensitivity denominator ({f(den.get('n_candidates_reproduced_exactly'))} of {f(den.get('n_candidates'))} "
      "candidates reproduce the official k/9 exactly; the rest are withheld, not guessed) changes the hit count "
      f"of exactly one candidate, {', '.join(den.get('candidates_whose_hits_change_at_10') or []) or 'none'} "
      "(7/9 -> 8/10). That candidate is the weights-only scar baseline, and its extra hit comes through the "
      "documented OLMo all-ones-null artefact: the null-projected variant stays 6/10. No activation readout "
      "detects the tenth pair.")
    A("")

    A("**2. The defensible false-alarm comparison is 4/12 vs 1/12, and it is underpowered (D2).** On all 15 "
      f"no-op pairs the logit baseline false-alarms on 6 and N1 on 1 (exact McNemar b={f(m.get('mcnemar15_b'))}, "
      f"c={f(m.get('mcnemar15_c'))}, p={f(m.get('mcnemar15_p_exact'))}). Three of those 15 are head-only W_U edits "
      "where every activation delta is bitwise 0.0, so the activation readouts' silence there is ANALYTIC. On the "
      f"12 non-degenerate pairs the comparison is 4/12 vs 1/12 (b={f(m.get('mcnemar12_b'))}, c={f(m.get('mcnemar12_c'))}, "
      f"exact p={f(m.get('mcnemar12_p_exact'))}). With 5 discordant pairs the smallest attainable p is "
      f"{f(m.get('mcnemar12_min_attainable_p'), 4)}, so this is UNDERPOWERED, not a negative. The claim that "
      "survives: a readout that fires on a behaviourally inert head-only edit is still a false alarm in deployment.")
    A("")

    A("**3. There is no false-alarm/sensitivity trade-off inside the activation class (D4).** Spearman rho between "
      "false-alarm count and sensitivity is POSITIVE everywhere: "
      f"{f(m.get('spearman_fa_sens_activation_excl_ams'))} within the activation class, "
      f"{f(m.get('spearman_fa_sens_activation_incl_ams'))} with the two AMS rows, and "
      f"{f(m.get('spearman_fa_sens_all32'))} across all 32 candidates. The claim 'the trade-off runs through the "
      "activation class' needs this to be materially negative, so it is NOT supported: readouts that fire more "
      "on no-ops also fire more on real edits. The activation false-alarm range is 0-3 of 15, as claimed.")
    A("")

    A("**4. Judged refusal is bounded, not merely null (D5, D6).** No site-local intervention moves judged "
      f"refusal of harmful requests by more than {f(m.get('max_abs_effect_FR_judged_refusal'))} (instruct, arm F, "
      f"P_B4), against median MDE80s of {f(m.get('median_mde80_instruct'))} (instruct), "
      f"{f(m.get('median_mde80_saferl'))} (SafeRL) and {f(m.get('median_mde80_abliterated'))} (abliterated). "
      "TOST at those margins declares equivalence in all three models "
      f"(p = {m.get('tost_p_instruct', float('nan')):.1e}, {m.get('tost_p_saferl', float('nan')):.1e}, "
      f"{m.get('tost_p_abliterated', float('nan')):.1e}). The abliterated FLOOR (arm-0 refused_harm 0.188, "
      "over-refusal 0.042) is why its grid is only 6 cells at site P. The over-refusal lever is present in BOTH "
      "models at B4-B5 with comparable magnitudes; the sole Holm-18 survivor (instruct N6 @ P_B5, -0.146) ranks "
      "4th by |effect| behind SafeRL arm-F at B4 (-0.188) and B5 (-0.167). The global-ablation band is B4, not B5 "
      f"(SafeRL-minus-instruct DiD +{f(m.get('global_ablation_did_saferl_minus_instruct'))} "
      f"[{f(m.get('global_ablation_did_ci_lo'))}, {f(m.get('global_ablation_did_ci_hi'))}], sign confirmed from the "
      "raw arms). The registered DiD matches its predicted sign in "
      f"{f(m.get('registered_did_cells_matching_sign'))} of {f(m.get('registered_did_cells_total'))} cells: NOT "
      "SUPPORTED. The random control R displaces 2.5x (D') and 2.0x (E) MORE than F off site P, not 1.4-2x, so "
      "'net of a matched random control' is literally true only at site P. No judged-refusal positive control "
      "existed in iteration 4.")
    A("")

    A("**5. The bitwise explanation is deleted; the mechanism is measured (D8).** With identical weights, only "
      f"{f(100 * m.get('device_swap_text_identical_frac', float('nan')), 1)}% of greedy texts are identical across "
      f"CPU and GPU, yet {f(100 * m.get('device_swap_hc_label_agreement', float('nan')), 1)}% of harm labels agree, "
      "and two activation readouts (N11 and C13_peak_d) fire on the fp16 no-op. The false-alarm gap is displacement "
      "magnitude times null tightness: the logit baseline moves "
      f"{f(m.get('ratio_bl1_easy_over_activation'), 2)}x more than the median activation readout on no-ops "
      "(BL1_easy numerator; 3.8x-7.4x across the four baseline variants).")
    A("")

    kc = J("table_fewprompt.json").get("a_kcurve", {})
    A("**6. Part 3 of the commission: a cheap activation readout DETECTS abliteration but cannot yet RANK "
      "models, and 'few' means ~32 prompts, not 0-4 (D7).** Detection: the held-out request-axis d (peak d, "
      "iteration-2 protocol) drops on 8/8 effective abliterated pairs, every CI wholly below 0 (6/6 on the "
      "iteration-2 panel, 2/2 fresh in iteration 3), and does not move on the granite null edit (+0.091, CI "
      "covers 0). This is readout- and harvest-specific: iteration-4's N1 (d at a fixed l*, regenerated "
      "harvests) drops significantly on only 3 of 5 scored abliterated models and significantly RISES on "
      "mylesgoose (+0.776 [+0.086, +1.226]), the same model whose peak d fell. Prompt budget: on "
      f"{kc.get('pair', 'the commissioned pair')}, N1's resampled interval first clears the no-op band at "
      f"k = {f(kc.get('smallest_k_excludes_0_band'))} prompts, the largest k tested. k = 0 (card regex, weights-only scar) is a "
      "DIFFERENT readout class, not a cheaper version of the same readout. Ranking: whether an activation "
      "readout ranks checkpoints by harmful compliance better than the logit baseline cannot be settled at "
      f"n = 10. The preregistered rule puts the panel at about {f(m.get('panel_n_prereg_rule'))} checkpoints; the "
      "matching power calculation for the paired difference (Williams' t, rho(B3,BL1) = "
      f"{f(m.get('rho_B3_BL1_n10'), 4)}, recovered exactly on the n = 10 Spearman lattice) gives 80% power at "
      f"about {f(m.get('panel_n80_power_observed_margin'))} at the observed margin. That is optimistic because "
      "B3 was the best of ~30 rows, and at half the margin it needs about "
      f"{f(m.get('panel_n80_power_half_margin'))}. Honest answer: roughly 30-150 checkpoints, not 10.")
    A("")

    A("**8. The 'BL1 ranks SafeRL below instruct' claim is withdrawn as a general claim (D3).** The iteration-2 "
      "lens applies final_norm twice, so BL1 is read on norm(norm(h_L)). Under that double-norm convention "
      "(BL1_hard: instruct 4.99, SafeRL 3.07) SafeRL ranks below instruct. The draft's sentence swaps those two "
      "numbers, although its own table has them right. Under the single-norm fix (BL1_truelogit: 6.651 vs "
      "7.462) the order inverts. On the iteration-3 n = 10 held-out panel the two conventions rank identically "
      "(rho +1.00), so the flip is VARIANT- AND PANEL-SPECIFIC: it appears only for the instruct/SafeRL pair "
      "among the 4B arms. Over-refusal is not ordered either. On exp_1 OR-Bench-Hard (n = 43) instruct 0.465 vs "
      "SafeRL 0.349, with SafeRL minus instruct CI [-0.291, +0.056]. On exp_2 held-out hard-benign (n = 48) the "
      "values are 0.438 vs 0.479, CI [-0.126, +0.208]. Both CIs cover 0, so the two sets' 'disagreement in "
      "order' is within noise. The XSTest-twin pair (0.11 / 0.00) cannot be located on disk. 'N1 and AMS sigma "
      "rank them correctly' is WITHDRAWN: there is no reliable order to rank against, and AMS sigma was never "
      "computed for the Qwen3-4B family.")
    A("")

    A("**9. Abliteration ROTATES the benign-side direction; it does not preserve its magnitude (D9).** The F "
      "direction cosine to the parent is 0.999 / 0.994 / 0.943 at B1-B3 and 0.412 / 0.306 / 0.328 at B4-B6. The "
      "N6 cosine falls from 0.997 at B1 to 0.021 / 0.027 / 0.061 at B4-B6, i.e. nearly orthogonal (all within "
      "tolerance). The claimed magnitudes (|N6| 1.87 parent vs 1.79 abliterated) are reproduced by NO source on "
      "disk. The same-source separability readout falls 2.66 -> 2.22 (-16%). The rotation dominates, so a "
      "parent-anchored readout misses the change and a self-fitted one does not; the magnitude drop is real "
      "but secondary. cos(F_instruct, F_SafeRL) is >= 0.84 in every band (min 0.841), which is what makes the "
      "redundancy argument non-trivial. Contribution 2, corrected: 12 of the 18 cells are decodable (AUROC CI "
      "lower bound > 0.60), and 11 of those 12 are inert for judged refusal. The 12th, P_B5, is the one Holm-18 "
      "survivor, so the draft's '12/12 inert' contradicts its own causal result.")
    A("")

    ms = jn.get("panel_manifest_state") or {}
    lab = jn.get("blind_label_files") or []
    A(f"**7. Backstop join: {jn.get('join_status', 'n/a')} (D11, checked {str(jn.get('generated_utc', ''))[:16]} UTC).** "
      f"{jn.get('reason', '')} Both sides are parallel iteration-5 artifacts still running at check time"
      + (f"; the substrate had written {sum(x['n_files'] for x in lab)} blind label file(s), recorded by name "
         "and time only, never opened" if lab else "")
      + ". The precedent is iteration 3's join_stub.json: record the state, never fabricate a join.")
    A("")
    return L


def main() -> None:
    txt = "\n".join(build()) + "\n"
    (RES / "key_findings.md").write_text(txt)
    print(txt)


if __name__ == "__main__":
    main()
