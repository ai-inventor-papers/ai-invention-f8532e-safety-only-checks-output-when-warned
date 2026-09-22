# Iteration-5 evaluation: recheck every blocking number from disk

A pure re-derivation-and-audit artifact for the Qwen3-4B cheap-safety-metric run. It closes the eleven BLOCKING reviewer must-fixes by recomputing every contested number from files already written by iterations 2-4, answers part 3 of the original commission (can this be a few-prompt metric?), and leaves a backstop copy of the iteration-5 confirmation join.

**It implements no new method and collects no new data.** Zero GPU, zero API spend ($0).

Headline: **claim_match_rate = 0.6866** over 67 verifiable claims (21 contradictions found); 1 UNVERIFIABLE and 0 SOURCE_ABSENT are reported separately and are never folded into the denominator.

## Layout

| path | what it is |
|---|---|
| `SUMMARY.md` | Results write-up. Opens with the contradictions list and the claim match rate. |
| `eval_out.json` | Machine-readable output in the `exp_eval_sol_out` schema. |
| `prereg_eval.json` / `.sha256` | Analysis plan frozen and hashed before the first numeric load. |
| `build_log.txt` | Append-only, UTC-stamped record of the freeze and each stage. |
| `results/source_manifest.json` | Path, size, mtime and sha256 of every source file read. |
| `results/contradictions.json` | The full claim ledger and the match rate. |
| `results/self_check_gate.json` | Programmatic gate report (rules a-f). |
| `results/table_composition.json` | D1. Composition table - every NOOP and EFFECTIVE pair, recipe histogram re-derived |
| `results/table_degeneracy.json` | D2. Structural degeneracy and exact McNemar on both denominators |
| `results/table_bl1_variants.json` | D3. Baseline-variant flip across the five Qwen3-4B arms |
| `results/table_candidates32.json` | D4. All candidate readouts: false alarms against sensitivity |
| `results/table_causal_grid.json` | D5. Full causal depth x site grid, Holm-18 recomputed within model |
| `results/table_equivalence.json` | D6. Equivalence bound on judged refusal and the arm-0 floor |
| `results/table_fewprompt.json` | D7. Few-prompt feasibility: k-curve and the required panel size |
| `results/table_displacement.json` | D8. Measured displacement replacing the bitwise explanation |
| `results/table_geometry.json` | D9. Rotation-versus-magnitude geometry of the safety directions |
| `results/table_setup_deviations.json` | D10. Experimental setup, appendix content and deviations |
| `results/join_backstop.json` | D11. Backstop confirmation join with hash-order verification |
| `results/table_sensitivity_denominators.json` | D4+. Addendum: sensitivity at the 10- and 11-pair effective sets the frozen count rule implies |
| `results/table_panel_power.json` | D7+. Addendum: power for the paired correlation difference (Williams' t) |
| `results/panel_size_curve.json` | Monte-Carlo permutation critical rho against panel size n. |
| `src/sources.py` | Registry of every source path, read strictly read-only. |
| `src/stats_lib.py` | Exact McNemar, bootstrap, permutation helpers. Seed 20260921. |
| `src/d1_d2_d4.py`, `src/d3_d7_d9.py`, `src/d5_d6.py`, `src/d8_d10.py` | Deliverable scripts. |
| `src/d11_join.py` | Backstop confirmation join. |
| `src/d4_denominators.py` | D4 addendum: sensitivity at the 10- and 11-pair effective sets, validated against the official 9. |
| `src/d7_power.py` | D7 addendum: power for the paired correlation difference (Williams' t). |
| `src/adjudicate_ledger.py` | Merges the four claim ledgers under ONE frozen rule; every override explained. |
| `results/ledger_adjudicated.json` | The adjudicated ledger with duplicates, withdrawals and overrides listed. |
| `results/table_sensitivity_denominators.json` | D4 addendum output. |
| `results/table_panel_power.json` | D7 addendum output. |
| `eval.py` | Top-level driver. |
| `pyproject.toml` | Exact pinned dependencies. |
| `src/assemble.py` | Merges the ledger and runs the self-check gate. |
| `src/build_eval_out.py` | Builds `eval_out.json` after the gate passes. |
| `src/write_summary.py` | Generates `SUMMARY.md` and this README. |
| `figures/` | Generated figures. |

## How to run

```bash
bash restore.sh            # uv venv + pinned install from pyproject.toml
.venv/bin/python eval.py   # every stage, in dependency order
```

`eval.py` runs the deliverable scripts, the two addenda, the ledger adjudication, the self-check gate, `eval_out.json` and this write-up. A stage that fails is recorded and the rest still run. Thread counts are pinned to 4 because scipy crawls when the cgroup quota disagrees with the visible CPU count.

The scripts read the iteration-2/3/4 workspaces **strictly read-only**. Nothing outside this directory is written. No model weights are loaded and no HuggingFace cache is created.

## Restoring removed files

`.aii/manifest.yaml` marks two paths for deletion after the round. Both are regenerable:

| path | why | restore with |
|---|---|---|
| `.venv/` | regenerable (957 MB interpreter + wheels) | `uv venv --python 3.12 && uv pip install -r pyproject.toml` |
| `src/__pycache__/` | regenerable bytecode cache | created automatically by `.venv/bin/python eval.py` |

`pyproject.toml` pins every dependency to the exact version that produced these results. `restore.sh` rebuilds the environment. Everything else in this directory is a deliverable and is kept.

