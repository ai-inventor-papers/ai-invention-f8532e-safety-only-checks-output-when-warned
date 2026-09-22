"""Write .terminal_claude_agent_struct_out.json from the final on-disk results."""

from __future__ import annotations

import json
from pathlib import Path

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
m = json.loads((WS / "eval_out.json").read_text())["metrics_agg"]
g = json.loads((WS / "results" / "self_check_gate.json").read_text())
j = json.loads((WS / "results" / "join_backstop.json").read_text())
c = g["claim_counts"]


def r(x: float, nd: int = 3) -> str:
    return f"{x:.{nd}f}"


summary = (
    "Zero-GPU, $0 re-derivation audit of every blocking number in the iteration-4 draft, recomputed from "
    "iteration-2/3/4 JSON and .npy on disk (disk wins over prose). PRIMARY METRIC: claim_match_rate = "
    f"{r(m['claim_match_rate'], 4)} ({c['MATCH']}/{c['MATCH'] + c['MISMATCH']} verifiable claims, frozen prereg "
    f"tolerances; {c['UNVERIFIABLE']} UNVERIFIABLE, {c['SOURCE_ABSENT']} SOURCE_ABSENT reported separately). Post-hoc "
    f"rounding-aware secondary {r(m['claim_match_rate_rounding_aware_posthoc'], 4)}. Four deliverable ledgers were "
    "adjudicated under ONE rule (duplicates dropped, 3 category errors withdrawn, 5 verdicts reversed by the frozen rule). "
    f"Self-check gate PASSED on all 6 rules: 11/11 deliverables, {g['total_table_rows']} rows all with "
    "source_file+readout_class, 32 candidate rows, 0 sentences naming a baseline as the deliverable (gate regex "
    "unit-tested), prereg sha unchanged. Full pipeline reruns deterministically. KEY CORRECTIONS: "
    "(1) the frozen count rule makes the effective set 10, not 9 (AMD-OLMo SFT->DPO; 11 under a literal reading). "
    "The iter-3/iter-4 disagreement on it is GENERATION PROVENANCE, not item sets. Re-scoring changes only B7 "
    "(7/9->8/10, the OLMo all-ones-null artefact). "
    f"(2) The defensible false-alarm test is BL1_easy 4/12 vs N1 1/12, exact McNemar p={r(m['mcnemar12_p_exact'])}: "
    "UNDERPOWERED, not negative. "
    f"(3) No FA/sensitivity trade-off: Spearman is POSITIVE ({r(m['spearman_fa_sens_activation_excl_ams'])} within "
    f"the activation class, {r(m['spearman_fa_sens_all32'])} across all 32). "
    f"(4) Judged refusal is BOUNDED: max |effect| {r(m['max_abs_effect_FR_judged_refusal'])} vs MDE80 "
    f"{r(m['median_mde80_instruct'])}/{r(m['median_mde80_saferl'])}/{r(m['median_mde80_abliterated'])}, TOST "
    "equivalent in all 3 models. The Holm survivor ranks 4th by |effect|; global ablation is B4, not B5; the "
    "registered DiD is NOT SUPPORTED (8/18). R displaces 2.5x/2.0x MORE than F off site P. "
    "(5) Bitwise explanation deleted: 25.6% text identity vs 96.5% label agreement across devices; BL1 moves "
    f"{r(m['ratio_bl1_easy_over_activation'], 2)}x more than activation readouts. "
    "(6) Commission part 3: request-axis d detects abliteration 8/8 (verified from per-pair CIs), but N1 "
    "REVERSES on mylesgoose; 'few' means ~32 prompts; RANKING needs about "
    f"{int(m['panel_n80_power_observed_margin'])}-{int(m['panel_n80_power_half_margin'])} checkpoints (Williams' "
    f"power; prereg rule says {int(m['panel_n_prereg_rule'])}), not 10. "
    "(7) Abliteration ROTATES N6 (cos 0.02-0.06 at B4-B6); magnitude is NOT preserved (-16%). "
    "Contribution 2 corrected to 11/12 inert. "
    f"(8) BL1 ranking flip withdrawn as variant- and panel-specific. D11 join: {j['join_status']} (no survivor "
    "committed; substrate manifest n=0; labels never opened). Read SUMMARY.md first; "
    "results/contradictions.json holds the ledger."
)

out = {
    "title": "Rechecking every disputed number from saved data",
    "layman_summary": (
        "Recomputes every contested number in an AI-safety study from files already saved on disk, checks "
        "which published claims hold up, and fixes the ones that do not."
    ),
    "summary": summary,
    "out_expected_files": {
        "script": "eval.py",
        "full_output": "full_eval_out.json",
        "mini_output": "mini_eval_out.json",
        "preview_output": "preview_eval_out.json",
    },
    "upload_ignore_regexes": [r"(^|/)\.venv/", r"(^|/)__pycache__/", r"(^|/)\.repl_agent\.ptylog$"],
}
assert 500 <= len(summary) <= 5000, len(summary)
assert 80 <= len(out["layman_summary"]) <= 250, len(out["layman_summary"])
assert 12 <= len(out["title"]) <= 90
(WS / ".terminal_claude_agent_struct_out.json").write_text(json.dumps(out, indent=2))
print(f"struct_out written: summary {len(summary)} chars, layman {len(out['layman_summary'])} chars")
