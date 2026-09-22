"""Write SUMMARY.md (contradictions FIRST) and README.md from the emitted results.

Both files are generated, never hand-edited, so they cannot drift from the tables.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
RES = WS / "results"

DELIV = {
    "D1": ("table_composition.json", "Composition table - every NOOP and EFFECTIVE pair, recipe histogram re-derived"),
    "D2": ("table_degeneracy.json", "Structural degeneracy and exact McNemar on both denominators"),
    "D3": ("table_bl1_variants.json", "Baseline-variant flip across the five Qwen3-4B arms"),
    "D4": ("table_candidates32.json", "All candidate readouts: false alarms against sensitivity"),
    "D5": ("table_causal_grid.json", "Full causal depth x site grid, Holm-18 recomputed within model"),
    "D6": ("table_equivalence.json", "Equivalence bound on judged refusal and the arm-0 floor"),
    "D7": ("table_fewprompt.json", "Few-prompt feasibility: k-curve and the required panel size"),
    "D8": ("table_displacement.json", "Measured displacement replacing the bitwise explanation"),
    "D9": ("table_geometry.json", "Rotation-versus-magnitude geometry of the safety directions"),
    "D10": ("table_setup_deviations.json", "Experimental setup, appendix content and deviations"),
    "D11": ("join_backstop.json", "Backstop confirmation join with hash-order verification"),
    "D4+": ("table_sensitivity_denominators.json", "Addendum: sensitivity at the 10- and 11-pair effective sets the frozen count rule implies"),
    "D7+": ("table_panel_power.json", "Addendum: power for the paired correlation difference (Williams' t)"),
}


def fmt(v: Any) -> str:
    if isinstance(v, float):
        return "n/a" if not math.isfinite(v) else f"{v:.4g}"
    return str(v)


def main() -> None:
    gate = json.loads((RES / "self_check_gate.json").read_text())
    led = json.loads((RES / "contradictions.json").read_text())
    counts = led["counts"]
    rate = led["claim_match_rate"]

    L: list[str] = []
    A = L.append
    A("# Recheck every blocking number from disk")
    A("")
    A("Iteration-5 evaluation artifact. **Zero GPU, zero API spend ($0).** No new method, no new "
      "data: every number below is re-derived from the JSON and `.npy` files already written by "
      "iterations 2-4.")
    A("")
    A("> **Governing rule.** The DISK is authoritative. Where a re-derived value disagrees with a "
      "value quoted in the hypothesis, the artifact direction or an earlier paper draft, the disk "
      "value wins, the prose value is recorded as a CONTRADICTION, and nothing on disk is edited "
      "to match prose.")
    A("")

    # ---------------- 1. CONTRADICTIONS FIRST ----------------
    A("## 1. Contradictions ledger and claim match rate")
    A("")
    A(f"**claim_match_rate = {fmt(rate)}**  ({counts['MATCH']} MATCH / "
      f"{counts['MATCH'] + counts['MISMATCH']} verifiable claims)")
    A("")
    A(f"- MATCH: {counts['MATCH']}")
    A(f"- MISMATCH: {counts['MISMATCH']}")
    A(f"- UNVERIFIABLE: {counts['UNVERIFIABLE']} *(reported separately, never in the denominator)*")
    A(f"- SOURCE_ABSENT: {counts['SOURCE_ABSENT']} *(reported separately, never in the denominator)*")
    A(f"- claims checked in total: {led['n_claims']}")
    A("")
    A("Tolerances fixed in `prereg_eval.json` before the first numeric load: counts EXACT; rates and "
      "effect sizes |delta| <= 5e-4; nats <= 1e-3; correlations <= 5e-3.")
    A("")
    sec = led.get("secondary_rounding_aware") or {}
    if sec:
        sc = sec.get("counts", {})
        A(f"*Post-hoc secondary, NOT the primary metric:* under a rounding-aware rule (a value quoted to k "
          f"decimals matches if the re-derived value rounds to it) the rate is **{fmt(sec.get('claim_match_rate'))}** "
          f"({sc.get('MATCH')} / {sc.get('MATCH', 0) + sc.get('MISMATCH', 0)}). The gap between the two rates is "
          "the share of frozen-rule mismatches that are rounding of quoted prose; the remainder are substantive.")
        A("")
    adj = led.get("adjudication") or {}
    if adj:
        A(f"*Ledger adjudication* (`src/adjudicate_ledger.py`, full record in `results/ledger_adjudicated.json`): "
          f"{len(adj.get('duplicates_dropped', []))} duplicate claim(s) dropped, "
          f"{len(adj.get('claims_withdrawn', []))} withdrawn as category errors, "
          f"{len(adj.get('explicit_overrides', []))} explicit overrides with stated reasons, and "
          f"{len(adj.get('frozen_rule_reversed_agent_verdict', []))} agent verdicts reversed by applying the frozen "
          "tolerance uniformly. One rule, applied to every claim.")
        A("")

    mism = [c for c in led["claims"] if str(c.get("verdict", "")).upper() == "MISMATCH"]
    A(f"### 1.1 The {len(mism)} contradictions")
    A("")
    if mism:
        A("| # | claim | published value | re-derived value | source |")
        A("|---|---|---|---|---|")
        for i, c in enumerate(mism, 1):
            A(f"| {i} | {str(c.get('claim_text',''))[:150]} | `{fmt(c.get('claimed_value'))}` | "
              f"`{fmt(c.get('rederived_value'))}` | `{str(c.get('source_file',''))[:70]}` |")
    else:
        A("No MISMATCH verdicts were recorded.")
    A("")

    unv = [c for c in led["claims"] if str(c.get("verdict", "")).upper() in ("UNVERIFIABLE", "SOURCE_ABSENT")]
    A(f"### 1.2 The {len(unv)} claims that could not be checked")
    A("")
    if unv:
        A("| # | claim | verdict | reason |")
        A("|---|---|---|---|")
        for i, c in enumerate(unv, 1):
            A(f"| {i} | {str(c.get('claim_text',''))[:150]} | {c.get('verdict')} | "
              f"{str(c.get('note',''))[:180]} |")
    else:
        A("Every claim in the ledger resolved to MATCH or MISMATCH.")
    A("")

    # ---------------- key findings (generated by src/key_findings.py) ----------------
    kf = RES / "key_findings.md"
    if kf.exists():
        body = kf.read_text().strip().splitlines()
        # demote its '## Key findings' heading to a numbered section
        if body and body[0].startswith("## "):
            body[0] = "## 1b. Key findings"
        L.extend(body)
        A("")

    # ---------------- 2. gate ----------------
    A("## 2. Self-check gate")
    A("")
    A(f"- gate passed: **{gate['gate_passed']}**")
    A(f"- deliverables produced: {len(gate['deliverables_present'])} / 11 "
      f"({', '.join(sorted(gate['deliverables_present']))})")
    if gate["deliverables_missing"]:
        A(f"- deliverables MISSING: {gate['deliverables_missing']}")
    A(f"- table rows emitted: {gate['total_table_rows']}; rows missing provenance: "
      f"{sum(gate['rows_missing_provenance'].values())}")
    A(f"- candidate table rows: {gate['candidate_table_rows']} (gate requires >= 32)")
    A(f"- prereg sha256 re-asserted: `{gate['prereg_sha256_now']}` "
      f"({'unchanged' if gate['prereg_sha256_now'] == gate['prereg_sha256_frozen'] else 'CHANGED - HARD FAILURE'})")
    A(f"- model-weight-sized files in the workspace: {len(gate['oversized_weight_files'])}")
    A(f"- sentences naming a baseline-class readout as the deliverable: {len(gate['gate_b_hits'])}")
    if gate["failures"]:
        A("")
        A("**Gate failures:**")
        for f in gate["failures"]:
            A(f"- {f}")
    if gate["warnings"]:
        A("")
        A("**Gate warnings:**")
        for w in gate["warnings"]:
            A(f"- {w}")
    A("")
    A("Gate rule (b) enforces the run invariant: the deliverable is the activation-level comparison "
      "of the three Qwen3-4B models, and any metric built from it reads activations or weights of a "
      "single model. Logit-only and text-only readouts are treated throughout as baselines.")
    A("")

    # ---------------- 3. deliverables ----------------
    A("## 3. Deliverables")
    A("")
    for did, (fname, desc) in DELIV.items():
        p = RES / fname
        status = "produced" if p.exists() else "NOT PRODUCED"
        A(f"### {did}. {desc}")
        A("")
        A(f"`results/{fname}` - {status}")
        if p.exists():
            try:
                obj = json.loads(p.read_text())
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict):
                for k in ("headline", "headline_statement", "summary", "conclusion", "statement",
                          "mechanism_statement", "bound_statement", "discussion", "corrected_claim",
                          "answer", "reason", "join_status"):
                    if isinstance(obj.get(k), str):
                        A("")
                        A(f"> **{k}:** {obj[k][:1200]}")
                for k, v in obj.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        A(f"- `{k}` = {fmt(v)}")
        A("")

    A("## 4. Provenance")
    A("")
    A("- `prereg_eval.json` was frozen and hashed BEFORE the first numeric load; "
      "`build_log.txt` is append-only and records the order.")
    A("- `results/source_manifest.json` records absolute path, size, mtime and sha256 for every "
      "source file read.")
    A("- Every emitted table row carries `source_file`, `source_key` and `readout_class`.")
    A("")
    (WS / "SUMMARY.md").write_text("\n".join(L) + "\n")

    # ---------------- README ----------------
    R: list[str] = []
    B = R.append
    B("# Iteration-5 evaluation: recheck every blocking number from disk")
    B("")
    B("A pure re-derivation-and-audit artifact for the Qwen3-4B cheap-safety-metric run. It closes "
      "the eleven BLOCKING reviewer must-fixes by recomputing every contested number from files "
      "already written by iterations 2-4, answers part 3 of the original commission (can this be a "
      "few-prompt metric?), and leaves a backstop copy of the iteration-5 confirmation join.")
    B("")
    B("**It implements no new method and collects no new data.** Zero GPU, zero API spend ($0).")
    B("")
    B(f"Headline: **claim_match_rate = {fmt(rate)}** over {counts['MATCH'] + counts['MISMATCH']} "
      f"verifiable claims ({counts['MISMATCH']} contradictions found); "
      f"{counts['UNVERIFIABLE']} UNVERIFIABLE and {counts['SOURCE_ABSENT']} SOURCE_ABSENT are "
      "reported separately and are never folded into the denominator.")
    B("")
    B("## Layout")
    B("")
    B("| path | what it is |")
    B("|---|---|")
    B("| `SUMMARY.md` | Results write-up. Opens with the contradictions list and the claim match rate. |")
    B("| `eval_out.json` | Machine-readable output in the `exp_eval_sol_out` schema. |")
    B("| `prereg_eval.json` / `.sha256` | Analysis plan frozen and hashed before the first numeric load. |")
    B("| `build_log.txt` | Append-only, UTC-stamped record of the freeze and each stage. |")
    B("| `results/source_manifest.json` | Path, size, mtime and sha256 of every source file read. |")
    B("| `results/contradictions.json` | The full claim ledger and the match rate. |")
    B("| `results/self_check_gate.json` | Programmatic gate report (rules a-f). |")
    for did, (fname, desc) in DELIV.items():
        B(f"| `results/{fname}` | {did}. {desc} |")
    B("| `results/panel_size_curve.json` | Monte-Carlo permutation critical rho against panel size n. |")
    B("| `src/sources.py` | Registry of every source path, read strictly read-only. |")
    B("| `src/stats_lib.py` | Exact McNemar, bootstrap, permutation helpers. Seed 20260921. |")
    B("| `src/d1_d2_d4.py`, `src/d3_d7_d9.py`, `src/d5_d6.py`, `src/d8_d10.py` | Deliverable scripts. |")
    B("| `src/d11_join.py` | Backstop confirmation join. |")
    B("| `src/d4_denominators.py` | D4 addendum: sensitivity at the 10- and 11-pair effective sets, validated against the official 9. |")
    B("| `src/d7_power.py` | D7 addendum: power for the paired correlation difference (Williams' t). |")
    B("| `src/adjudicate_ledger.py` | Merges the four claim ledgers under ONE frozen rule; every override explained. |")
    B("| `results/ledger_adjudicated.json` | The adjudicated ledger with duplicates, withdrawals and overrides listed. |")
    B("| `results/table_sensitivity_denominators.json` | D4 addendum output. |")
    B("| `results/table_panel_power.json` | D7 addendum output. |")
    B("| `eval.py` | Top-level driver. |")
    B("| `pyproject.toml` | Exact pinned dependencies. |")
    B("| `src/assemble.py` | Merges the ledger and runs the self-check gate. |")
    B("| `src/build_eval_out.py` | Builds `eval_out.json` after the gate passes. |")
    B("| `src/write_summary.py` | Generates `SUMMARY.md` and this README. |")
    B("| `figures/` | Generated figures. |")
    B("")
    B("## How to run")
    B("")
    B("```bash")
    B("bash restore.sh            # uv venv + pinned install from pyproject.toml")
    B(".venv/bin/python eval.py   # every stage, in dependency order")
    B("```")
    B("")
    B("`eval.py` runs the deliverable scripts, the two addenda, the ledger adjudication, the self-check "
      "gate, `eval_out.json` and this write-up. A stage that fails is recorded and the rest still run. "
      "Thread counts are pinned to 4 because scipy crawls when the cgroup quota disagrees with the "
      "visible CPU count.")
    B("")
    B("The scripts read the iteration-2/3/4 workspaces **strictly read-only**. Nothing outside this "
      "directory is written. No model weights are loaded and no HuggingFace cache is created.")
    B("")
    B("## Restoring removed files")
    B("")
    B("`.aii/manifest.yaml` marks two paths for deletion after the round. Both are regenerable:")
    B("")
    B("| path | why | restore with |")
    B("|---|---|---|")
    B("| `.venv/` | regenerable (957 MB interpreter + wheels) | `uv venv --python 3.12 && uv pip install -r pyproject.toml` |")
    B("| `src/__pycache__/` | regenerable bytecode cache | created automatically by `.venv/bin/python eval.py` |")
    B("")
    B("`pyproject.toml` pins every dependency to the exact version that produced these results. "
      "`restore.sh` rebuilds the environment. Everything else in this directory is a deliverable and is kept.")
    B("")
    (WS / "README.md").write_text("\n".join(R) + "\n")

    (WS / "restore.sh").write_text(
        "#!/usr/bin/env bash\n"
        "# Rebuild the only deleted path in this workspace.\n"
        "set -euo pipefail\n"
        'cd "$(dirname "$0")"\n'
        "uv venv --python 3.12\n"
        "uv pip install -r pyproject.toml\n"
    )
    (WS / "restore.sh").chmod(0o755)
    print("wrote SUMMARY.md, README.md, restore.sh")


if __name__ == "__main__":
    main()
