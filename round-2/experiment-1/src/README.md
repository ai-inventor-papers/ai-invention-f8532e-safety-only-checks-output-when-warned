# Does the model act on harm, or only see it?

**Iteration 2, Lane A (the SCREEN)** of the Qwen3-4B safety mechanistic-interpretability run.

One mechanistic question, not a leaderboard: **is the axis that separates a base model, its
safety-tuned child and its abliterated child a RECOGNITION axis — the model still sees the
harm — or an EXECUTION axis — the model stops acting on it?** Six parent-free, single-checkpoint
readouts (X1, X2, X3, X5, X8, X10) plus two carried ones (X9, X11) are raced against the
recognition axis `R` and seven named baselines (BL1–BL7) on ONE shared harvest per checkpoint,
over instruct-parent / abliterated-child pairs and the commissioned Qwen3-4B lineage
(Base, instruct, official SafeRL, the community `mlabonne/Qwen3-4B-abliterated`, and a
non-safety fine-tune of Base as control).

> **Results live in [`out/SUMMARY.md`](out/SUMMARY.md) (human-readable) and
> `method_out.json` / `out/method_out.json` (machine-readable, `exp_gen_sol_out` schema).**
> The headline is summarised in [Results](#results) below.

## The invariant

> Every candidate is computable from the activations and/or weights of **ONE** checkpoint —
> no parent, no reference model, no generation, no judge, no benchmark.

Parent weights appear in exactly two places, both DIAGNOSTIC and excluded from scoring: the
edit-recipe fingerprint (which assigns strata) and the `X2_parent` identity row. Logit-only and
text-only readouts (BL1 final-layer refusal logit gap, BL5 model-card regex) are **baselines**,
never the deliverable.

## Architecture: harvest once, score offline

1. Each checkpoint is loaded **once** and reduced to *sufficient statistics* on disk
   (`harvest/<tag>/`): last-prompt-token hidden states at every layer (`A_prompt.npy`), the
   per-layer logit-lens refusal / hedge / control drives, the unembedding summary (token-set rows,
   vocab mean and second moment), and — in a second pass — the teacher-forced response-site
   states for the 2×2 XSTest cells (`A_resp.npy`, and the per-position residual writes
   `D_resp_parts/`: a 120–290 MB tensor stored as numbered ≤90 MiB parts with an `index.json`,
   because GitHub rejects files above 100 MiB; `aii_common.load_npy_maybe_split` reassembles it,
   verified bit-identical in `results/split_report.json`).
2. Weights are summarised separately with **zero prompts** (`gram/`, σ_min and the near-null
   singular vector per layer of the stacked residual-write matrix `[o_proj | down_proj]`).
3. Everything else — every candidate, every baseline, 20 shuffled-label null draws per
   checkpoint, 20 random directions, a 100-replicate item bootstrap, the prompt-budget curve —
   is **pure offline NumPy** over those caches.

Two Gram identities make the weight side one cached matrix per layer:

```
||uᵀM||²   = uᵀ(MMᵀ)u = uᵀGu     →  X2 write mass, for ANY direction u
σ_min(M)²  = λ_min(MMᵀ)          →  X10 orthogonality scar, from the same G
```

Both are asserted numerically before any model is loaded (`src/t1_tests.py`).

## Panel

| pair | parent → child | family | stratum (weight fingerprint) | registered label |
|---|---|---|---|---|
| P0 | Qwen/Qwen3-4B → mlabonne/Qwen3-4B-abliterated (**commissioned**) | qwen3 | B per-layer rank-1 | EFFECTIVE (ΔHC +0.733, judged by this lane) |
| P1 | Qwen/Qwen3-0.6B → huihui-ai/Huihui-Qwen3-0.6B-abliterated-v2 | qwen3 | A global rank-1 | EFFECTIVE (+0.467) |
| P2 | Qwen/Qwen3-1.7B → huihui-ai/Huihui-Qwen3-1.7B-abliterated-v2 | qwen3 | A global rank-1 | EFFECTIVE (+0.667) |
| P3 | Qwen/Qwen2.5-1.5B-Instruct → Goekdeniz-Guelmez/Josiefied-…-abliterated-v3 | qwen2.5 | C other operator (α 3.5, embed edited) | EFFECTIVE (+0.467) |
| P4 | HuggingFaceTB/SmolLM3-3B → mlx-community/SmolLM3-3B-abliterated-bf16 | smollm3 | A global rank-1 | EFFECTIVE (+0.289) |
| P5 | microsoft/Phi-4-mini-instruct → lunahr/Phi-4-mini-instruct-abliterated | phi | B per-layer rank-1 | EFFECTIVE (+0.244) |
| P6 | ibm-granite/granite-3.2-2b-instruct → Damien420/granite-…-abliterated | granite | C (1 of 80 matrices edited) | **NULL_EDIT** — the specificity control |
| S1 | stabilityai/stablelm-2-1_6b-chat → hereticness/heretic_stablelm-2-1_6b-chat | stablelm | C | ANOMALOUS (leaked seal → control only) |
| S2 | HuggingFaceTB/SmolLM2-1.7B-Instruct → venkycs/SmolLM2-1.7B-Instruct-Abliterated | smollm2 | C (quanto FP8 upload) | ANOMALOUS (leaked seal → control only) |

Singles: Qwen3-4B-Base (chat template), Qwen3-4B-SafeRL, the CohenQu non-safety fine-tune of
Base (E2 control), TinyLlama-1.1B-Chat and OLMo-2-0425-1B (+Instruct) for the E3 family panel,
and an architecture-identical **random-init** Qwen3-0.6B (handbook rule d). The TinyLlama
"abliterated" child is a broken upload with missing shards and is excluded.

The registered effectiveness rule (fixed before any label was assigned): EFFECTIVE if
ΔHC ≥ +0.20; NULL_EDIT if |ΔHC| < 0.10 and |ΔOR| < 0.10; ANOMALOUS otherwise. Behavioural
columns are iteration-1 Lane C's (45 harmful + 45 benign, two LLM judges); the commissioned child
had none and was judged by this lane with Lane C's **exact** prompts, generation settings, rubric
and judges (`src/judge_ext_lanec.py`, $0.0087; the parent row recomputes to Lane C's exactly).

## Candidates, baselines and their prior-art status

| code | what it reads | prior art (same-iteration research lane) | survivor-eligible |
|---|---|---|---|
| X1 | accumulator gain: peak harm-gap / gap at the model's own first 0.95-AUROC layer | PARTIALLY SCOOPED (HPD 2609.13534, Geometry-Lite 2605.20241 are per-input) | yes |
| X2 | write mass of `[o_proj|down_proj]` along the model's own harm axis | **CLOSED** (Jorak Model Scanner ships it; non-peer-reviewed) | no |
| X3 | closed-form percept-to-refusal gain through the RMSNorm Jacobian and unembedding | PARTIALLY SCOOPED | yes |
| X5 | response-site write concentration at onset positions, harmful − benign twin | PARTIALLY SCOOPED (2607.14147 App. E) | yes |
| X8 | execution depth margin: (layer where refusal drive rises fastest − first decodable layer)/L | PARTIALLY SCOOPED (lag published off-concept 3×) | yes |
| X10 | weights-only orthogonality scar: σ_min vs a shape- and norm-matched Marchenko–Pastur baseline | **CLOSED** (Jorak ships the idea; reimplemented as BL7) | no |
| X9, X11 | benign-only footprint; 2×2 arming interaction on the stable axis | carried re-tests | no |
| BL1 | final-layer refusal-token logit gap (logit-only) | — | baseline |
| BL2 | full-d cross-validated probe on raw hidden states (supervised ceiling) | — | baseline |
| BL3 / BL4 | held-out diff-in-means Cohen's d / Fisher ratio + silhouette | — | baseline |
| BL5 | model-card regex, term-swept AND name-free | — | baseline |
| BL6 | HRCI_repr (2606.16349 Eq 9; k=8 and CCA-on-PCs are OUR choices) | — | baseline |
| BL7 | Jorak A = σ₁(U)/‖U‖_F over the stacked least-singular vectors (the incumbent for X10) | — | baseline |

Not implemented, on purpose: N-GLARE JSS / JR-Min-Max (no public code) and every
parent-requiring audit (GFS / Skin-Deep, the two-signal z-sum audit 2607.01854, CANARY).

## Registered decision rules

- **E1** (a) ≥ 4 EFFECTIVE pairs *within one edit-recipe stratum*, same-signed Δ, item-bootstrap
  95% CI excluding 0; (b) the NULL_EDIT pair's Δ inside its shuffled band. E1 = (a) AND (b).
  If no stratum reaches 4, E1 is **UNDER_POWERED** (not failed) and the pooled-across-strata row
  is reported only as a labelled SECONDARY reading.
- **E2** training order Base < Qwen3-4B ≤ SafeRL and (Qwen3-4B − max(Base, CohenQu)) > 0.50
  pooled shuffled-label SD with a bootstrap CI excluding 0.
- **E3** leave-one-family-out transfer (ridge, no recalibration) ≥ BL1 + 0.10 pairwise-order
  accuracy on safe-engagement, with oracle / random / shuffled-truth machinery controls.
- **E4** joined from the sibling causal lane if it delivered; otherwise NOT_EVALUATED and the
  word EXECUTION is withheld from any survivor (it is called a READOUT).
- **Survivor** = E1 AND (E2 or E3), not CLOSED by prior art. "No survivor" is a reportable result.
- Every label-dependent candidate is scored against its **own shuffled-label band** (20 refits
  on permuted labels); the random-direction SD is reported as a unit only, never as a test.
  Label-free candidates (X10, BL7, BL5) use their declared alternative null (Marchenko–Pastur
  baseline, within-model layer distribution, parent reference band / parent presence test).

## Results

Final scoring run: 25 activation-harvested checkpoints (18 with the teacher-forced C-harvest),
29 weight summaries, 20 shuffled-label nulls and a 100-replicate item bootstrap per checkpoint,
T7 determinism PASS, 6/6 leakage audits PASS, OpenRouter spend $0.0087. Every table is in
[`out/SUMMARY.md`](out/SUMMARY.md).

**The answer to the one question — EXECUTION, at the level of a readout.** Across the 6
EFFECTIVE instruct → abliterated pairs (P0–P5):

- **Recognition is largely kept.** Held-out TPR@5%FPR on the HARD set (lexically matched XSTest
  twins + OR-Bench) changes by a median of −0.05 (registered margin ±0.10); the first layer where
  harm becomes decodable moves by a median of 0 layers. All six TOST verdicts are INCONCLUSIVE:
  with 80 benign HARD items the intervals are wide. The qualification: P2 (huihui Qwen3-1.7B)
  loses 0.21 TPR, with the whole 90% interval above zero, and P3 (Josiefied Qwen2.5) sits at the
  boundary ([0.000, 0.358]). The recognition instrument can see a loss when there is one: the
  broken venkycs child falls from 0.825 to 0.138 (DIFFERENT), and random init reads 0.075.
- **Execution falls in every pair.** The peak over depth of the harm-conditioned logit-lens
  refusal drive (an activation readout through the model's own unembedding) falls in 6/6 pairs
  (median Δ −2.98). The write mass of `[o_proj|down_proj]` along the model's own harm axis (X2)
  falls in 6/6 (median −0.093), and the closed-form percept-to-refusal gain (X3) in 5/6.
- **The harm direction agrees shallow and diverges deep.** Parent and child harm directions,
  each refit parent-free, agree at median |cos| 0.992 in the shallowest quarter of layers and
  0.459 in the deepest half. They split at 37–61% of depth in every rank-one pair. The NULL-EDIT
  granite pair stays aligned throughout (0.984 / 0.997); random init vs trained reads 0.014.

**The commissioned Qwen3-4B lineage** (behaviour from iteration-1 Lane C; the abliterated row
from this lane's judge extension with the same protocol):

| arm | harmful compliance | over-refusal | R (TPR@5%FPR) | HARD-set recognition onset | peak refusal-drive gap (layer) | final-layer gap (BL1) | X5 |
|---|---|---|---|---|---|---|---|
| Qwen3-4B-Base | 0.022 | 0.156 | 0.475 | layer 33 | 1.57 (31) | −0.30 | 0.007 |
| CohenQu non-safety fine-tune of Base | — | — | 0.713 | layer 23 | 2.57 (35) | 1.96 | −0.018 |
| Qwen3-4B (instruct) | 0.000 | 0.444 | 0.875 | layer 19 | 4.92 (36) | 4.92 | 0.218 |
| Qwen3-4B-SafeRL | 0.000 | 0.333 | 0.850 | layer 19 | **8.78** (32) | 3.60 | 0.108 |
| mlabonne/Qwen3-4B-abliterated | **0.733** | 0.000 | 0.838 | layer 19 | 1.92 (21) | −1.96 | −0.031 |

Instruction tuning moves hard-set harm recognition from layer 33 up to layer 19, and
abliteration leaves that untouched (0.838 vs 0.875). What abliteration removes is the refusal
drive: its peak falls from 4.92 to 1.92, and at the last layer the drive is inverted (−1.96).
SafeRL shows the largest drive of all, peaking at layer 32 rather than the final layer.

**The screen: no survivor.** Under the registered rules no candidate survives, and the reason is
structural. The weight fingerprints split the effective pairs into three edit recipes
(A global rank-1: P1, P2, P4; B per-layer rank-1: P0, P5; C other: P3), so no stratum reaches the
4 EFFECTIVE pairs E1(a) requires. E1 is therefore UNDER_POWERED for every candidate, which is
fallback 7/8, reported as such and not as a failure. No candidate passes E2 (X2: order right and
margin 0.83 SD, but the bootstrap CI includes 0; X5: margin 2.82 SD, but SafeRL (0.108) < instruct
(0.218)). None passes E3: nothing beats the BL1 logit baseline by +0.10 in leave-one-family-out
transfer over 27 checkpoints and 9 families; the machinery controls are clean (oracle 1.0,
shuffled truth 0.498). E4 was NOT_EVALUATED: no sibling causal lane delivered in this iteration.
X2 and X10 are CLOSED by prior art (the Jorak Model Scanner) and excluded from selection.

Descriptive readings (the pooled-across-strata SECONDARY row, never a verdict):

| readout | same sign across 6 effective pairs | CI≠0 (or outside the parent band) | dose-response ρ vs ΔHC (n=7, exact p) |
|---|---|---|---|
| BL1 final-layer refusal logit gap (logit-only baseline) | yes | 5/6 | −0.07 (0.88) |
| X1 accumulator gain | yes | 3/6 | −0.52 (0.24) |
| X2 write mass | yes | 0/6 | −0.22 (0.64) |
| X5 response-onset write concentration | no | 2/6 | **−0.87 (0.016)** |
| X10_abs weights-only scar (zero prompts) | no | 6/6 outside | 0.47 (0.29) |
| BL5 name-free card regex (text-only baseline) | no | — | 0.87 (0.029) |

- **The logit-only baseline is the most consistent abliteration detector,** and we say so. BL1
  moves in the same direction in every effective pair, with 5/6 CIs excluding zero. The strongest
  activation-level dose-response is X5 (ρ −0.87), but it fails E2's ordering because SafeRL
  concentrates less than instruct. A text-only card regex also tracks dose (ρ 0.87).
- **Weights-only, zero prompts:** X10_abs puts every effective child outside the parent reference
  band. The incumbent Jorak statistic (BL7) reads A = 1.00 on global rank-1 edits but misses
  per-layer ones (mlabonne 0.41). It also fires on an UNEDITED parent (stablelm-2-1_6b-chat,
  0.99), so it fails the parent-presence test.
- **Few prompts:** the pair difference is reported at k = 0, 4, 8, 16, 32 and 128 fitting prompts
  (`out/SUMMARY.md`); no curve's maximum is reported as a result. Counts of effective pairs whose
  mean Δ is negative, at k = 4 / 8 / 16 / 32 / 128:
  - BL1: 6/6 at every k. But it also moves on the NULL-EDIT granite pair by about −1.0 pooled SD
    at every k, so it is not specific at this scale.
  - X5: 6 / 6 / 6 / 6 / 5.
  - X3: 6 / 6 / 5 / 5 / 5.
  - X2: 4 / 5 / 6 / 5 / 6 (non-monotone in k).
  - X8: 3 / 4 / 2 / 3 / 3 (no signal).

**Facts about the hub supply found on the way:** `venkycs/SmolLM2-1.7B-Instruct-Abliterated` is an
optimum-quanto FP8 upload with no quantization config. A standard load leaves all 168 linear
layers randomly initialised, so the model Lane C judged ("over-refusal 1.000") is a random network
with trained embeddings, not an uncensored one. The TinyLlama "abliterated" child is missing shards.
The granite "abliterated" child edits 1 of 80 matrices and is a behavioural no-op.

## Hardware and the two sessions

No GPU in either session. **Session 1** (03:36–04:47 UTC, 2 cores of a Threadripper 7960X)
wrote the code, the prereg and three 4B harvests before its container ended. **Session 2**
(from 07:10 UTC) resumed in a NEW container — an AMD EPYC 9655 cpuset of two hyperthreads of ONE
physical core, 16 GB cgroup memory, host load ~200 — and found the run-shared HF cache EMPTY and
the `.venv` gone; everything was re-fetched and rebuilt, and session-1 caches were reused
byte-for-byte via the DONE / W_DONE sentinels. Every change, cut and cast is in
`results/deviations.json` (also `metadata.deviations`), including four statistical/engineering
bugs in the session-1 code that were fixed **before any result was scored** (a ledger that
overwrote itself, NaN serialisation, confidence intervals that shrank with the number of null
draws, an OOM in the fingerprint), and the registered drops taken for wall-clock (the 4B
random-init arm, the Base plain-format re-run, four extra base singles, and the C-harvest of the
anomalous controls and singles).

## Layout

```
method.py                 orchestrator: uv run method.py --stages <stage ...>
prereg.json / .sha256     the registered design (SHA-256 printed before the first forward pass)
survivor.json / .sha256   written ONLY after the screen is frozen
e4_interface.json         what the sibling causal lane must provide for E4
method_out.json           THE DELIVERABLE (+ full_/mini_/preview_ variants; copies in out/)
finish2.sh                session-2 closing sequence: analyze -> T7 -> confirm -> leak -> outputs -> validate
emit.sh                   re-emit method_out.json + SUMMARY + full/mini/preview from final results (no scoring)
supervise_sweep.sh        restarts the resumable prompt sweep if it is OOM-killed
run_judge_then_resume.sh  paused the sweep between checkpoints for the judge extension (memory)
run_tail_control.sh       the time gate: stopped the prompt sweep after the E3 singles, ran the C-harvest
run_weight_tail.sh        random-init weight summary, failed-summary retry, S2 fingerprint retry
ops/obsolete/             superseded session-1 helpers (provenance only)
tests/                    profiling / bootstrap sanity scripts used while debugging

src/
  aii_common.py           paths, logging, atomic JSON (NaN-safe), seeds, cost ledger, deviations
  panel.py                paired-lineage registry + the registered effectiveness rule
  assets_build.py         STAGE 0: stimuli (96 EASY fit + 160 HARD measure), cells, token sets, prereg
  fetch_models.py         (session 2) re-download the panel into the run-shared cache
  fetch_cards.py          (session 2) model cards for BL5
  numerics.py             every candidate / baseline / null formula (pure NumPy)
  t1_tests.py             T1 arithmetic unit tests
  t2_lesion_control.py    T2/T3 ground-truth lesion control for X2 / X10
  harvest.py              the prompt harvest kernel (records missing/unexpected keys at load)
  c_harvest2.py           the teacher-forced C-harvest: per-tokenizer slot rule, exact causal truncation
  wsummary.py             weights-only statistics (quanto-FP8 aware; extremes-only eigensolver)
  randinit_wsummary.py    weight summary of the random-init arm
  weightfp.py             edit-recipe fingerprints -> strata (row-chunked embedding diff)
  sweep.py                resumable, deadline-gated prompt sweep
  judge_ext_lanec.py      behavioural row for the commissioned child with Lane C's exact protocol
  score_ckpt.py           per-checkpoint candidates, baselines, recognition axis R
  score_panel.py          nulls, item bootstrap, pair deltas, E1/E2/E3, budget curve, X2_parent rows
  analyze.py              offline scoring driver (per-checkpoint score cache)
  score_watch.py          incremental scorer (scores each checkpoint once all its inputs exist)
  t7_determinism.py       T7: score one checkpoint twice from scratch and byte-compare
  split_large_arrays.py   converts >100 MiB arrays to verified <=90 MiB parts (GitHub limit)
  confirm.py              freeze the survivor, then confirm on untouched evidence only
  leak_audit.py           T5 leakage audits as code assertions
  session2_deviations.py  writes the session-2 deviations into the ledger (idempotent)
  make_outputs.py         method_out.json + out/SUMMARY.md + out/released/

assets/                   stimuli.json, cells.json, token_sets.json, pairs.json (hash-registered)
harvest/<tag>/            per-checkpoint sufficient statistics (see manifest)
results/                  every intermediate table, the deviations ledger, the audits, score cache
out/SUMMARY.md            the human-readable report
out/released/             prereg, assets, per-layer curves (CSV), fitted directions (.npy)
logs/                     every run log
```

## How to run

```bash
./install.sh                                    # CPU torch env in .venv (uv only)
uv run method.py --stages fetch stage0 t1 t2    # weights into $HF_HOME, assets + prereg, unit tests
uv run method.py --stages wsummary randinit_w weightfp   # zero-prompt weight side + strata
uv run method.py --stages sweep judge csweep    # activation harvests + the commissioned child's label
./finish2.sh                                    # score, T7, freeze + confirm, leak audit, outputs, schema
```

Every stage is resumable (`DONE`, `W_DONE`, `C_DONE` sentinels; a per-checkpoint score cache
keyed on every input file and the scoring-code version) and deadline-gated.

## What the pipeline validated (checks, not findings)

- **T1 7/7**: Gram identities to 1e-15, X2 normalisation 1.00 ± 0.05 for a random direction,
  RMSNorm Jacobian vs finite differences 3e-5, Marchenko–Pastur vs an empirical draw.
- **T2/T3** on real Qwen3-0.6B weights with a KNOWN rank-one orthogonalisation at swept α: X2
  tracks (1−α)² to 1.9e-4; X10 does not fire on the unedited model; detection floor α ≈ 0.75;
  X10's registered primary (within-model z) form is blind to a UNIFORM all-layer edit, which is
  why X10_abs is carried beside it.
- **C-harvest exactness**: truncating each cell at prompt + 56 tokens leaves D_resp bit-identical
  and A_resp within bf16 rounding (1.3e-4 relative); every tokenizer family keeps 96/96 cells.
- **Judge-extension parity**: the parent's behavioural columns recompute to Lane C's exactly.
- **T5 leakage audits**, **T7 determinism** and the E3 **machinery controls** are re-run by
  `finish2.sh` and reported in `metadata`.

## Seal discipline

- `gen_art_experiment_3/assets/reserved_54.json` is opened only by `src/confirm.py`, after
  `survivor.json` is written and hashed; with no survivor it stays unopened.
- `gen_art_dataset_1/heldout_cells.json` is never opened.
- The "sealed" stablelm and smollm2 families are NOT blind held-out evidence (their truth values
  leaked into Lane C's `s3_results.json`); they are ANOMALOUS controls only.
- `assets/*.json` are never rewritten after registration (their object hashes are in
  `prereg.json`); the judge-extended pair registry is written to `results/pairs_effective.json`.

## Restoring removed files

`.aii/manifest.yaml` marks the regenerable bulk for deletion after the round. To rebuild:

| path | command |
|---|---|
| `.venv/` | `./install.sh` (= `uv venv --python 3.12 .venv` + `uv pip install … -r pyproject.toml` with the CPU torch index) |
| `harvest/*/gram/` | `uv run method.py --stages wsummary randinit_w` (re-derives every per-layer Gram from the HF snapshots; zero prompts) |
| `harvest/*/D_resp_parts/` | `uv run method.py --stages csweep` (teacher-forced C-harvest, ~1 h on one CPU core; written directly as ≤90 MiB parts) |
| `src/__pycache__/` | regenerated automatically on the next import |

Model weights are never stored here: they live in the run-shared `$HF_HOME` and are
re-downloadable with `uv run method.py --stages fetch` (or `huggingface-cli download <repo>` for
every repo in `assets/pairs.json`). `restore.sh` rebuilds the environment and the weights-only
statistics.
