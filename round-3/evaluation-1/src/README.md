# Fix the three-model comparison tables (iter-3 evaluation, run_YqmEFECOIR3D)

A CPU-only re-analysis of activation arrays that earlier steps already saved. There is no forward pass, no model load, no GPU and no LLM call ($0). It closes the reviewer's open must-fixes for the commissioned comparison: Qwen3-4B-Base, Qwen3-4B (instruct), Qwen3-4B-SafeRL, the CohenQu STaR non-safety fine-tune of Base, and mlabonne/Qwen3-4B-abliterated.

- **Step 1: the abliterated row and every effective child** (`src/panel.py`). For all 25 checkpoints whose iter-2 `A_prompt` exists, it computes:
  - the held-out request-axis Cohen's d (fitted on EASY, scored on HARD) at every layer;
  - the k-restricted-budget curve (k = 4 to 64, 200 draws, layer chosen inside the subset);
  - the prompt-site and response-site depth profiles, the registered onsets and the logit-lens peak drive;
  - BL1 on both the EASY and HARD prompt sets. The iter-2 BL1, peak drive, onsets, B3, BL7 and X10_abs are asserted equal to their stored values;
  - pair deltas with paired 1000-replicate bootstraps and TOST, set beside the MEASURED behavioural delta.
- **Step 2: accumulator controls**, in two places:
  - `src/panel.py` freezes an axis at a shallow layer and reads it forward, compared against an own axis refit at every layer;
  - `src/laneb.py` runs the same test on Lane B's band-limited arrays and re-derives the forced post-lesion cosine.
- **Step 3: site dissociation per lineage, three sites** (`src/laneb.py`). The sites are PROMPT (`item|lastp`), RESPONSE-EARLY and RESPONSE-LATE, for each of L1–L4 and each α. Every cell has scenario-bootstrap CIs, and the section adds Holm-corrected scenario permutation tests, TOST, and the safety-minus-L4 contrasts. The iter-2 "prompt site" was in fact the EARLY response window.
- **Step 4: power for saturated probes** (`src/laneb.py`). For each saturated cell it reports TPR at 1% FPR, the smallest resolvable FPR, the MDE (three ways) and the margin-to-threshold.
- **Steps 5 and 6: tables** (`eval.py`, `src/gates.py`, `src/notation.py`, `src/behaviour.py`). These build the master, claims, notation and gates tables and a deviations ledger in which every upstream quoted number is re-derived.

## Key results
See `SUMMARY.md` → *Key findings*. In short:
- **Ledger.** 58 of 69 comparable quoted numbers reproduce.
- **Abliteration.** The held-out request-axis d falls in all 6 effective abliterated children but not on the granite null edit, while BL1 and peak drive both move on that null edit. The HARD-refit recognition probe does not move for mlabonne.
- **Safety training.** Safety training raises HARD recognition, from TPR@5%FPR 0.475 to 0.875.
- **STaR.** The non-safety STaR fine-tune matches Base only on d.
- **Accumulation.** It is not supported: the growth is a layer-specific direction.
- **Execution reading.** The late-response lesion drop is as large in the non-refusing lineage L4, so the 'execution' reading is withdrawn.

## Layout
| path | what |
|---|---|
| `eval.py` | assembler: reads `results/*.json`, writes every table, `eval_out.json`, `SUMMARY.md` |
| `src/panel.py` | A_prompt/A_resp panel over 25 checkpoints (steps 1, 2a, 2c, STaR fractions) |
| `src/laneb.py` | Lane B lesion arrays, streamed one key at a time (steps 2b, 2d, 3, 4) |
| `src/gates.py`, `src/notation.py`, `src/behaviour.py` | gates table, notation table, judged HC/OR recompute + K1 granite |
| `src/laneb_resume.py`, `src/laneb_addendum.py`, `src/validate_outputs.py` | Lane B tasks 5-7 resume driver (coarsened bootstrap-shift MDE), k=16 iter-2 M5 reproduction + ledger values, JSON validity check |
| `src/iter2_numerics.py` | verbatim copy of iter-2 `numerics.py` (the exact AUROC / TPR@FPR / Cohen's d / cross-fit definitions) |
| `src/figures.py` | the four data figures |
| `results/panel_ckpt/<tag>.json` | per-checkpoint curves and scalars (cached) |
| `results/panel_pairs.json`, `panel_star.json`, `panel_reconcile.json` | pair deltas, STaR fractions, quoted-vs-recomputed rows |
| `results/laneb_*.json`, `laneb_scores_band.npz` | Lane B cells, tests, contrasts, power, accumulator, reconciliation, per-row band scores |
| `results/*_table.csv`, `results/tables.json`, `results/deviations_ledger.json` | every table as CSV/JSON |
| `eval_out.json` (+ `full_`/`mini_`/`preview_`) | schema `exp_eval_sol_out` |
| `SUMMARY.md` | the tables in this order: master, claims, site, accumulator, power, gates, notation, deviations |
| `figures/fig1..fig4.{pdf,png}` | site curves, fixed vs own axis, per-layer d, k-budget |

## How to run
```bash
uv venv .venv --python=3.12
VIRTUAL_ENV=$PWD/.venv uv pip install numpy scipy scikit-learn pandas loguru tabulate matplotlib
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
.venv/bin/python src/behaviour.py; .venv/bin/python src/gates.py; .venv/bin/python src/notation.py
.venv/bin/python src/panel.py      # ~20 min on 1 core (25 checkpoints)
.venv/bin/python src/laneb.py      # tasks 1-4 ~8 min on 1 core (streams ~7.6 GB of Lane B npz)
.venv/bin/python src/laneb_resume.py; .venv/bin/python src/laneb_addendum.py   # tasks 5-7 + addenda, ~3 min
.venv/bin/python eval.py           # seconds
.venv/bin/python src/figures.py
```
All inputs are read-only paths inside `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_{1,2}/gen_art/...`.

## Restoring removed files
- `src/__pycache__/` is marked `delete: regenerable`. Python recreates it automatically.
- `.venv/` is marked `delete: regenerable`. Rebuild it with `uv venv .venv --python=3.12 && VIRTUAL_ENV=$PWD/.venv uv pip install numpy scipy scikit-learn pandas loguru tabulate matplotlib`.

Nothing else is deleted. Everything under `results/` and `figures/` is kept.
