"""S1. Prereg freeze for the iteration-5 evaluation audit.

Writes prereg_eval.json, hashes it into prereg_eval.sha256 and appends a
UTC-stamped line to the append-only build_log.txt. MUST run before the first
numeric load. Re-asserted at the end of eval.py; a mismatch is a hard failure.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

WS = Path(__file__).resolve().parent

PREREG = {
    "artifact_id": "gen_plan_evaluation_1_idx4",
    "title": "Recheck every blocking number from disk",
    "frozen_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    "governing_rule": (
        "The DISK is authoritative. Every number is RE-DERIVED from source files, "
        "never copied from prose. Where a re-derived value disagrees with prose, the "
        "disk value wins, the prose value is recorded as a CONTRADICTION, and nothing "
        "on disk is edited to match prose."
    ),
    "scope": {
        "gpu_hours": 0,
        "api_spend_usd": 0.0,
        "new_data_collected": False,
        "new_method_implemented": False,
    },
    "deliverables": {
        "D1": "Composition table: all 15 NOOP + all 9 EFFECTIVE rows + appendix of remaining pairs of 56; recipe histogram re-derived; AMD-OLMo SFT->DPO discrepancy resolved.",
        "D2": "Structural degeneracy derived from data; ANALYTIC_ZERO cells daggered; exact McNemar on 15-pair and 12-pair non-degenerate denominators.",
        "D3": "BL1 variant flip: 5 Qwen3-4B arms x 7 readout variants; Kendall tau across orderings; over-refusal reconciliation across two benign sets.",
        "D4": "All 32 candidates with FA_15/FA_12/sensitivity/median null-SD displacement; name-collision audit; fig1; Spearman FA-vs-sensitivity within activation class and across all rows.",
        "D5": "Full 18-cell causal grid per model per arm with Holm-18 recomputed within model; effect-size ranking; global-ablation band correction; DiD sign verification; POS removed from the 18-cell table; R displacement-ratio validity check; keyword-proxy kappa per model.",
        "D6": "Equivalence framing: max |effect_FR| vs median MDE80 per model; bound statement; optional TOST; arm-0 baselines incl. abliterated floor.",
        "D7": "Few-prompt metric question: k-curve, what it detects reliably, what it does not, REQUIRED PANEL SIZE by Monte-Carlo permutation, Qwen3-4B four-way comparison.",
        "D8": "Delete the bitwise explanation; replace with measured displacements + null tightness + threshold-crossing counts.",
        "D9": "N6 rotation-vs-magnitude paragraph; contribution 2 restated with decodability criterion re-derived.",
        "D10": "Experimental setup + appendix content; deviations paragraph each verified against deviations.json; keyword-proxy range per band; mixed sensitivity denominators explained and unscorable pair named.",
        "D11": "Backstop join from the two parallel iteration-5 artifacts with hash-order verification; COULD_NOT_COMPLETE with reasons if absent.",
    },
    "claim_ledger_schema": {
        "fields": [
            "claim_id",
            "claim_text",
            "claimed_value",
            "rederived_value",
            "tolerance_rule",
            "tolerance",
            "source_file",
            "source_key",
            "verdict",
            "note",
        ],
        "verdicts": ["MATCH", "MISMATCH", "UNVERIFIABLE", "SOURCE_ABSENT"],
    },
    "match_tolerance_rule": {
        "count": {"kind": "exact", "tol": 0.0},
        "rate": {"kind": "abs", "tol": 5e-4},
        "effect_size": {"kind": "abs", "tol": 5e-4},
        "nats": {"kind": "abs", "tol": 1e-3},
        "correlation": {"kind": "abs", "tol": 5e-3},
        "string": {"kind": "exact_string", "tol": 0.0},
    },
    "claim_match_rate_definition": (
        "claim_match_rate = MATCH / (MATCH + MISMATCH). UNVERIFIABLE and SOURCE_ABSENT "
        "are reported separately and NEVER folded into the denominator."
    ),
    "min_ledger_claims": 35,
    "statistics": {
        "mcnemar": "scipy.stats.binomtest(min(b,c), b+c, 0.5, alternative='two-sided') on discordant pairs; report b, c, exact p; declare UNDERPOWERED when no attainable p can reach 0.05.",
        "holm": "Holm-Bonferroni recomputed WITHIN each model over its 18 registered cells; stored flags are not reused.",
        "bootstrap_B": 2000,
        "seed": 20260921,
        "permutation_reps": 20000,
        "kcurve": {"k_values": [0, 4, 8, 16, 32], "resamples_per_k": 200, "replacement": False},
        "panel_size_grid": [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80],
        "decodability_criterion": "AUROC bootstrap CI lower bound > 0.60",
        "analytic_zero_rule": "A (pair, readout-class) cell is ANALYTIC_ZERO iff the underlying delta is bitwise 0.0 for every prompt.",
    },
    "s12_gate_rules": {
        "a": "every emitted table row has non-null source_file AND readout_class, else ABORT naming the offending table",
        "b": "regex-scan SUMMARY.md and all prose fields for any sentence naming a baseline-class readout (BL1*, AMS*, card/name regex, greedy refusal text, B7) as the deliverable/answer/winner/metric - any hit FAILS the gate",
        "c": "prereg sha256 still matches",
        "d": "all 11 deliverables produced a non-empty artifact",
        "e": "the candidate table has >= 32 rows",
        "f": "no model-weight cache exists anywhere in the workspace",
    },
    "run_invariant": (
        "The deliverable is the activation-level comparison. Logit-only (BL1*) and "
        "text-only (card/name regex, greedy refusal text) and weights-only (B7, AMS) "
        "readouts are BASELINES, not the result."
    ),
    "failure_scenarios": {
        "source_missing": "verdict SOURCE_ABSENT; the deliverable is still emitted with the gap named.",
        "kcurve_arrays_missing": "fall back to harvest/<tag>/*.npy; if absent, report k-curve UNAVAILABLE with the reason and STILL produce the panel-size calculation.",
        "prose_disagrees": "disk wins; log CONTRADICTION; do not edit the source.",
        "number_not_locatable": "UNVERIFIABLE with the exact paths searched; never substitute the prose value.",
        "late": "D1-D6 priority 1, D7-D10 priority 2, D11 hard-scheduled in the final 30 minutes.",
    },
}


def main() -> None:
    target = WS / "prereg_eval.json"
    if target.exists():
        raise SystemExit(f"REFUSING TO OVERWRITE existing freeze: {target}")
    payload = json.dumps(PREREG, indent=2, sort_keys=True)
    target.write_text(payload, encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (WS / "prereg_eval.sha256").write_text(digest + "\n", encoding="utf-8")
    stamp = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    with (WS / "build_log.txt").open("a", encoding="utf-8") as fh:
        fh.write(f"{stamp}  PREREG_FROZEN  sha256={digest}  file=prereg_eval.json\n")
    print(f"FROZEN sha256={digest}")


if __name__ == "__main__":
    main()
