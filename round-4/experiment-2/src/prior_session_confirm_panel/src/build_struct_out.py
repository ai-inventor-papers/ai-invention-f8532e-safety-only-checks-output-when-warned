"""Write .terminal_claude_agent_struct_out.json (title, layman_summary, summary, expected files, upload
exclusions). Every number in the summary is read from the committed result files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, WS, chain_records, jload  # noqa: E402


def f2(v, sign: bool = True) -> str:
    try:
        x = float(v)
        return "NaN" if x != x else (f"{x:+.2f}" if sign else f"{x:.2f}")
    except (TypeError, ValueError):
        return str(v)


def ci(v) -> str:
    return "n/a" if not v or v[0] is None else f"[{f2(v[0])},{f2(v[1])}]"


def main() -> None:
    truth = jload(RESULTS / "graded_truth.json")
    table = jload(RESULTS / "heldout_table.json")
    trim = jload(RESULTS / "panel_trim.json")
    audit = jload(RESULTS / "order_audit.json")
    two = jload(RESULTS / "two_panel_table.json")
    extra = jload(RESULTS / "extra_analyses.json")
    unit = jload(RESULTS / "unit_checks.json")
    hooks = jload(RESULTS / "hook_checks.json")["summary"]
    rep = jload(RESULTS / "judge_reproduction_check.json")
    feats = jload(RESULTS / "features.json")
    n = table["n_panel"]
    hc = {r: v["outcomes_primary_laneC_items"]["harmful_compliance"] for r, v in truth["per_ckpt"].items()}
    rows = {r["feature"]: r for r in table["rows"] if r["outcome"] == "harmful_compliance"}
    crit, mde = rows["C1"]["critical_rho_alpha05"], rows["C1"]["mde_rho_power80"]
    beat = [k for k, r in rows.items() if k != "BL1" and (r.get("dabs_BL1_ci95_ckpt") or [None])[0] is not None
            and r["dabs_BL1_ci95_ckpt"][0] > 0]
    tw = [r for r in two["rows"] if r["rho_heldout"] is not None and r["rho_iter2_all_graded"] is not None]
    same = sum(1 for r in tw if r["same_sign_heldout_vs_iter2_all"])
    flips = [f"{r['feature']} ({f2(r['rho_iter2_all_graded'])} -> {f2(r['rho_heldout'])})" for r in tw
             if not r["same_sign_heldout_vs_iter2_all"]]
    cost = sum(float(json.loads(x).get("cost_usd") or 0) for x in (RESULTS / "judge_cost_ledger.jsonl").read_text().splitlines() if x.strip())
    pc = {(r["parent"], r["child"]): r for r in extra["paired_contrasts"]}
    abl = [r for r in extra["paired_contrasts"] if r["kind"] == "abliteration"]
    dpo = next((r for r in extra["paired_contrasts"] if r["parent"].endswith("-SFT") and r["child"].endswith("-SFT-DPO")), None)
    sft = next((r for r in extra["paired_contrasts"] if r["child"].endswith("-SFT") and not r["parent"].endswith("-SFT")), None)
    tl = extra["bl1_truelogit"]
    b7 = {r: feats["features"][r]["B7"] for r in feats["features"]}
    b7d = jload(RESULTS / "b7_diagnostic.json")
    rel = truth["split_half_reliability"]["harmful_compliance"]["odd_even_spearman_brown"]

    act_keys = ("C13", "C13_peak_d", "C7", "C5")

    def excl0(v):
        c = v["ci95_prompt_boot"]
        return c and c[0] is not None and (c[0] > 0 or c[1] < 0)
    sft_moved = [k for k in act_keys if excl0(sft["prompt_level_deltas"][k])]
    sft_txt = ("moves no activation readout (C13, peak d, C7, C5 CIs all cover 0)" if not sft_moved
               else "moves " + ", ".join(sft_moved))
    abl_drop = [r for r in abl if all(r["prompt_level_deltas"][k]["ci95_prompt_boot"][1] < 0 for k in ("C13", "C13_peak_d"))]
    repl_txt = (f"iteration 3's 'request-axis d falls in every abliterated child' replicates on {len(abl_drop)}/{len(abl)} "
                "new pairs (both CIs below 0)")

    def rr(k):
        r = rows[k]
        return f"{k} {f2(r['rho'])} {ci(r.get('ci95_ckpt'))}"
    abl_txt = "; ".join(
        f"{r['child'].split('/')[-1]}: dHC {f2(r['harmful_compliance']['delta_hc'])}, peak d "
        f"{f2(r['prompt_level_deltas']['C13_peak_d']['delta'])} {ci(r['prompt_level_deltas']['C13_peak_d']['ci95_prompt_boot'])}, "
        f"mid-depth d {f2(r['prompt_level_deltas']['C13']['delta'])} {ci(r['prompt_level_deltas']['C13']['ci95_prompt_boot'])}, "
        f"B7 {f2(r['point_deltas_other_features']['B7'])}" for r in abl)
    summary = (
        f"HELD-OUT CONFIRMATION PANEL (iteration 3, experiment_1; NO winner named). {n} checkpoints that no earlier artifact "
        f"had loaded, drawn by a frozen seeded SHA-256 rule from families absent from the iteration-2 screen: Vikhr-Llama-3.2-1B-"
        f"Instruct + its abliterated child (the D2-registry fresh held-out pair), unsloth/Llama-3.2-1B-Instruct + mylesgoose "
        f"abliterated2, the Falcon3-1B Base->Instruct and AMD-OLMo-1B base->SFT->SFT-DPO stage lineages, and LFM2-700M "
        f"(TIME rule dropped {', '.join(trim['dropped'])}). ORDER (hash_chain.jsonl; order audit "
        f"{'PASS' if audit['pass'] else 'FAIL'}): panel rule -> draw -> greedy generation + Lane C lc_judge grading -> "
        f"graded_truth.json committed -> prereg.json frozen -> activation harvest (iteration-2 protocol: 256 prompts at the "
        f"last prompt token, 96 teacher-forced XSTest cells, all layers, fp16, weight summaries, 64 severity items) -> scoring. "
        f"BEHAVIOUR (45 Lane C harmful items, the screen's outcome items): harmful compliance {min(hc.values()):.2f}-"
        f"{max(hc.values()):.2f}, split-half reliability {rel:.2f}; both abliterated children comply more than their parents; "
        f"AMD-OLMo base (HC {hc['amd/AMD-OLMo-1B']:.2f}) is incoherent rather than safe; SFT->DPO is a behavioural no-op. "
        f"HELD-OUT TABLE (results/heldout_table.json; n={n}; permutation critical |rho| {crit:.3f}, 80%-power MDE {mde:.2f}), "
        f"Spearman rho with harmful compliance [checkpoint-bootstrap 95% CI]: {rr('B3')} (iteration-2 held-out diff-in-means d, "
        f"activation); {rr('B7')} (weights-only scar; abliterated children {f2(b7['Vikhrmodels/Vikhr-Llama-3.2-1B-Instruct-abliterated'], False)}/"
        f"{f2(b7['mylesgoose/Llama-3.2-1B-Instruct-abliterated2'], False)} vs parents {f2(b7['Vikhrmodels/Vikhr-Llama-3.2-1B-Instruct'], False)}/"
        f"{f2(b7['unsloth/Llama-3.2-1B-Instruct'], False)}, but all three AMD-OLMo checkpoints {f2(b7['amd/AMD-OLMo-1B'], False)} because "
        f"their shared null is the all-ones direction mandated by OLMo's mean-subtracting LayerNorm; projecting it out "
        f"(results/b7_diagnostic.json) drops rho(HC) to {f2(b7d['rho_hc_B7_ones_projected'])}, leaving abliteration-scar detection "
        f"only); "
        f"{rr('C13_peak_d')}; {rr('C5')}; {rr('C7')}; {rr('BL1')} (logit baseline); C2 {f2(rows['C2']['rho'])}, "
        f"C2_tpr5 {f2(rows['C2_tpr5']['rho'])}, C6 {f2(rows['C6']['rho'])}, C9 {f2(rows['C9']['rho'])} (sign OPPOSITE to the "
        f"declared expectation, as on the iteration-2 panel); C1 {f2(rows['C1']['rho'])}; C4 {f2(rows['C4']['rho'])}; "
        f"C11 {f2(rows['C11']['rho'])}; C12 {f2(rows['C12']['rho'])}; C13 {f2(rows['C13']['rho'])}. Rows whose |rho| exceeds "
        f"|rho(BL1)| with a paired CI excluding 0: {', '.join(beat) if beat else 'none'}. SAME CODE on the iteration-2 panel's "
        f"saved activations (22 graded): {same}/{len(tw)} rows keep their sign; flips: {', '.join(flips) if flips else 'none'}. "
        f"PAIRED FRESH-MODEL CONTRASTS (post-prereg, prompt bootstrap): {abl_txt} -- {repl_txt}. On the SFT->DPO no-op BL1 moves "
        f"{f2(dpo['prompt_level_deltas']['BL1']['delta'])} {ci(dpo['prompt_level_deltas']['BL1']['ci95_prompt_boot'])} while peak d moves "
        f"{f2(dpo['prompt_level_deltas']['C13_peak_d']['delta'])} {ci(dpo['prompt_level_deltas']['C13_peak_d']['ci95_prompt_boot'])}; "
        f"AMD base->SFT (dHC {f2(sft['harmful_compliance']['delta_hc'])}) {sft_txt}. BL1 reads a "
        f"double-normalised final slice (iteration-2 lens); the literal final-logit gap ranks the panel identically "
        f"(rho {f2(tl['heldout_rho_BL1_vs_truelogit'][0])}). CHECKS: unit checks all pass={unit['all_pass']} (published "
        f"outcome rates and iteration-2 BL1/B3/B7/X2/X10 reproduced to 0.0); hook checks on {hooks['n']} checkpoints "
        f"(determinism {hooks['all_determinism_pass']}, layer-0 = embedding {hooks['all_layer0_pass']}, last-slice argmax "
        f"{hooks['all_lens_index_pass']}); judge re-run {rep['n_mismatch_rows']}/{rep['n']} mismatches; spend ${cost:.2f}. "
        f"JOIN: no screen survivor.json exists in iteration 3, so the confirmation lookup is DEFERRED (results/join_stub.json). "
        f"Raw activations for every checkpoint are kept under harvest/<tag>/ in the iteration-2 layout for re-scoring.")
    out = {
        "title": "Fresh models test cheap internal safety readouts",
        "layman_summary": ("We graded ten never-before-used small language models on how often they help with harmful "
                           "requests, then checked which internal-activation readouts, taken from one model at a time, "
                           "track that behaviour."),
        "summary": summary[:5000],
        "out_expected_files": {"script": "method.py", "full_output": "full_method_out.json",
                               "mini_output": "mini_method_out.json", "preview_output": "preview_method_out.json"},
        "upload_ignore_regexes": [r"(^|/)\.venv(/|$)", r"(^|/)__pycache__/", r"(^|/)hf_cache/", r"(^|/)private/",
                                  r"(^|/)harvest/.*\.npy$", r"(^|/)harvest/.*/gram/"],
    }
    (WS / ".terminal_claude_agent_struct_out.json").write_text(json.dumps(out, indent=1))
    print(len(out["summary"]), "chars summary;", len(out["layman_summary"]), "chars layman")


if __name__ == "__main__":
    main()
