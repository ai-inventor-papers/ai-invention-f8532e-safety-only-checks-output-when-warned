# Re-checking the numbers we already have

A **zero-GPU, zero-API, zero-download re-adjudication** of iteration 1's three lanes,
computed only from files already on disk. It runs no forward pass, downloads no
checkpoint, and spends nothing on judging. Its outputs are tables, not findings about
new data.

The scientific deliverable is iteration 1's premise re-expressed on an outcome **with
headroom**. Iteration 1's headline recognition outcome read AUROC 1.000 in the
unperturbed control, so "the representation survives the lesion" was never falsifiable
in either direction. It is restated here as TPR at 1% FPR, as restricted-labelled-budget
AUROC, and as a two-one-sided-test equivalence verdict per parent-child pair, each with
an explicit power sentence. Around it sit eight reporting repairs, all re-analysis of
stored numbers rather than missing experiments.

## The run invariant, enforced as a column

> The commissioned comparison and any metric built from it must read **activations or
> weights of a single model**. Logit-only and text-only readouts are baselines, never
> the result.

Every row of every table carries a mandatory `READOUT_CLASS` in
`{activation, weight, logit, text, metadata}`. Rows tagged `activation` or `weight` are
RESULT-ELIGIBLE. Rows tagged `logit`, `text` or `metadata` print in the same table under
a permanent `BASELINE_ONLY` flag, and no summary sentence names one as the study's
answer. `evalkit/selfcheck.py` **rejects** a table that omits the column and rejects
prose that names a baseline-class readout as the answer; its verdict is in
`results/selfcheck.json`.

This is a mechanistic-interpretability study of *where safety lives* — recognition of
harm versus execution of a refusal. Nothing here is framed as jailbreak evaluation or
attack selection; no attack-success rate is an outcome in any table, and behavioural
columns appear only as the ground truth an internal readout is validated against.

## How to run

```bash
./install.sh                    # uv venv + requirements
.venv/bin/python eval.py        # everything (~10 min, 2 CPU, no GPU)
.venv/bin/python eval.py --smoke     # one lineage, no restricted-budget sweep (~1 min)
.venv/bin/python eval.py --reuse-m1  # reuse results/m1_cache.json (~25 s)
./finalize.sh                        # schema validation, mini/preview variants, size check
```

M1's restricted-budget sweep (12,000 probe fits) is the only slow step and dominates the
runtime; it is cached to `results/m1_cache.json`, so iterating on the report costs seconds.
Set `OMP_NUM_THREADS=1` — on a 2-core box that roughly halves the sweep.

The pre-registration is written and SHA-256'd **before the first number is computed**
(`results/prereg_eval.json`, hash in `results/prereg_eval.sha256` and in every output).

## What each metric does

| module | metric | READOUT_CLASS | what it settles |
|---|---|---|---|
| `evalkit/m0_assets.py` | **M0** asset and recomputability ledger | metadata | Opens every file before any claim is made about it. Tests the two inherited claims the planning pass found overstated. Gates everything else. |
| `evalkit/m1_recognition.py` | **M1** recognition with headroom | activation | The scientific deliverable. TPR@1%FPR, TPR@5%FPR, restricted-budget AUROC at k∈{16,32,64}, TOST equivalence per pair, a power sentence per row. |
| `evalkit/m2_ceiling.py` | **M2** ceiling and dynamic-range audit | mixed | Every outcome's ceiling, its unperturbed-control value, and its effective dynamic range. Saturated outcomes are re-labelled INDETERMINATE beside the claim they qualify. |
| `evalkit/m3_cosine.py` | **M3** cosine geometry | activation | Three protocols instead of the smallest one; HARC reconciliation; the **full** 21-pair rotation matrix instead of four hand-picked cells. |
| `evalkit/m4_gates.py` | **M4** the complete gates ledger | metadata | Every registered gate × checkpoint × lane, including the four omitted failures, each with the conclusion that depends on it. |
| `evalkit/m5_budget.py` | **M5** the prompt-budget curve, in full | activation | All six k rungs with family-clustered intervals, a monotonicity test, and k=0 stated explicitly. |
| `evalkit/m6_paired.py` | **M6** the paired-lineage contrast | activation | The only contrast on which recognition and execution make opposite predictions. Formed from stored features plus recomputed judged ground truth. T1–T4. |
| `evalkit/m7_truth.py` | **M7** truth-column and judge integrity | text / metadata | Per-target spread, attenuation ceilings, the regex-versus-judge discrepancy, machinery controls, and the competitor-baseline annotation. BASELINE_ONLY throughout. |
| `evalkit/m8_provenance.py` | **M8** provenance and claim-diff ledger | metadata | One row per number the draft prints, with a **CLAIM MATCH RATE** at the top of the report. |

Shared machinery lives in `evalkit/stats.py` (BCa bootstrap, **family**-clustered
resampling, TOST, Clopper-Pearson, operating points, Holm, Spearman with a
resolvability companion) so no two tables can silently use different conventions.

## Layout

```
eval.py                     orchestrator: runs M0-M8, writes tables, report and eval_out.json
evalkit/
  paths.py                  canonical READ-ONLY paths into iteration 1's lanes
  prereg.py                 the pre-registration and its SHA-256
  stats.py                  one implementation of every statistical procedure
  selfcheck.py              enforces the run invariant as a column
  laneb_substrate.py        reader for Lane B's per-item activation harvest
  m0_assets.py .. m8_provenance.py
EVAL_REPORT.md              CONTRADICTIONS first, then the claim match rate, then the tables
eval_out.json               exp_eval_sol_out schema (+ full/mini/preview variants)
finalize.sh                 schema validation, mini/preview variants, file-size check
results/
  prereg_eval.json/.sha256  the frozen pre-registration
  m0_asset_ledger.csv       one row per quantity, with sha256, size and actual contents
  m0_harvest_inventory.json every npz key, shape and dtype in Lane B's harvest
  m0_causal_logs.json       the causal arm's file count and verbatim log tails
  m1_recognition_headroom.csv
  m1_cache.json             cached M1 rows+notes, so --reuse-m1 skips the 12-min sweep
  m2_ceiling_audit.csv
  m3a_cosine_protocols.csv  m3b_prior_art.csv  m3c_rotation_matrix.csv
  m4_gates_ledger.csv
  m5_budget_curve.csv
  m6_paired_lineage.csv     m6_tests.json
  m7_truth_integrity.csv
  m8_provenance.csv         m8_commissioned_comparison.csv
  eval_notes.json           every module's notes block
  selfcheck.json            the run-invariant verdict
scratch/lane{A,B,C}_schema.md   the structural maps every module was written against
logs/                       run logs
```

Every table row carries its `source_file`, so the write-up cites a computed number
rather than a remembered one.

## Reading the lanes

Lane workspaces are **read-only**; nothing in this repository opens one for writing.

```
ITER1  = .../3_invention_loop/iter_1/gen_art
LANE_A = ITER1/gen_art_experiment_1     (7-arm Qwen3-4B activation harvest)
LANE_B = ITER1/gen_art_experiment_2     (rank-one lesion, 4 lineages x 5 strengths)
LANE_C = ITER1/gen_art_experiment_3     (21-checkpoint cross-family panel)
DATASET= ITER1/gen_art_dataset_1        (the registered stimulus gates)
```

## Restoring removed files

Three paths are marked `delete` in `.aii/manifest.yaml`. All three are build
artefacts — no result, table, figure, log or source file is ever removed.

**`.venv/`** (989 MB) — redownloadable. The Python environment.

```bash
./install.sh
# equivalently:
uv venv .venv --python=3.12
VIRTUAL_ENV="$PWD/.venv" uv pip install -r requirements.txt
```

`requirements.txt` and the `[project].dependencies` list in `pyproject.toml`
pin every package to the exact version this artifact ran on (numpy 2.5.3,
scipy 1.18.1, pandas 3.0.6, scikit-learn 1.9.1, loguru 0.7.3, pyyaml 6.0.3,
tabulate 0.10.0), so the restore is reproducible rather than merely functional.

**`__pycache__/`** and **`evalkit/__pycache__/`** — regenerable bytecode caches.

```bash
.venv/bin/python -m compileall eval.py     # restores __pycache__/
.venv/bin/python -m compileall evalkit     # restores evalkit/__pycache__/
```

Both are also recreated automatically the next time `eval.py` is run.

### Everything else is kept

`results/` (the twelve metric tables plus the pre-registration, harvest
inventory, causal-log capture, M1 cache, M6 tests, notes and self-check),
`eval_out.json` with its full/mini/preview variants, `EVAL_REPORT.md`,
`scratch/` (the three lane schema maps every module was written against),
`logs/`, and all source under `evalkit/` are text and are kept — they are what
the write-up cites and what a later step reads.

## Rebuilding the results from scratch

After restoring the environment:

```bash
.venv/bin/python eval.py     # ~12 min on 2 CPUs, no GPU, no network, no API spend
./finalize.sh                # schema validation, mini/preview variants, size check
```

This reads iteration 1's lane workspaces read-only and rewrites everything
under `results/`, plus `EVAL_REPORT.md` and `eval_out.json`. It is deterministic:
the pre-registration hash
`7f6a38d94007c3a7d07b40cadfc79863cdd504f1115e2cf47e12511c4d77966b` and the
claim match rate `0.8229` reproduce exactly. If the iteration-1 lane
workspaces are gone, nothing here can be rebuilt — which is why `results/` is
kept rather than treated as regenerable.
