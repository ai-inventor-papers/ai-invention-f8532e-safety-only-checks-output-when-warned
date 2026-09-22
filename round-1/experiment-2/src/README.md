# Erase the safety signal, remeasure

**Lane B** of a mechanistic-interpretability study of *where safety lives* in the Qwen3-4B
family. We take the single rank-one direction that community "abliteration" tools delete,
delete it completely and verifiably, and then ask what the model can still do.

Short answer: **uncensoring a model does not blind it to harm.** The deletion works — the
component along that direction falls to 0.02% of baseline in every residual-stream write of
all 36 layers — and a held-out probe on the same hidden states still separates harmful from
harmless requests at **AUROC 1.000**.

> This is a lesion study used to *localise* a function, the way a lesion localises one in
> neuroscience. Nothing here selects, ranks, or optimises an attack, and no readout is a
> jailbreak. Every candidate metric reads **activations or weights of a single model**;
> logit-space quantities appear only as registered baselines and as the causal arm's outcome.

## What was done

A rank-one, prompt-fitted orthogonalisation `W <- W - a*u*(u^T W)` is applied to every
residual-stream write matrix (`o_proj` + `down_proj`, all 36 layers) of four Qwen3-4B
lineages at five strengths, and five candidate safety readouts are recomputed before and
after. Qwen3 gives those matrices no bias, so for `y = W0 x` the edit is *exactly*
`y -> y - a*u*(u^T y)`; applying it as an output projection makes `alpha=0` a **bitwise**
no-op, makes the restore exact, and leaves `embed_tokens` — which **is** `lm_head` on all
four lineages — provably untouched, so the causal arm's logit outcome is uncontaminated.

| lineage | checkpoint | safety-tuned |
|---|---|---|
| L1 | `Qwen/Qwen3-4B-Base` | no |
| L2 | `Qwen/Qwen3-4B` (Instruct) | yes |
| L3 | `Qwen/Qwen3-4B-SafeRL` | yes |
| L4 | `CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6` | no (fine-tune of L1) |

The item substrate is 150 XSTest minimal-edit twin pairs from the six genuine contrast
families, split 96 confirmatory / 54 held-out-reserved by `sha256`, crossed into a 2x2 of
request{harmful, matched benign twin} x response-prefix{hazardous, benign} with the
response span **token-identical** across the request manipulation. `out/prereg.json` was
frozen before the first forward pass and is verified byte-identical at the end.

## Headline results

**The lesion is exact, and the representation survives it.** On Qwen3-4B:

| alpha | 0.00 | 0.25 | 0.50 | 0.75 | 1.00 |
|---|---|---|---|---|---|
| projection gap along `u` (normalised) | 1.000 | 0.744 | 0.482 | 0.228 | **0.0002** |
| predicted `(1 - alpha)` | 1.000 | 0.750 | 0.500 | 0.250 | 0.000 |
| held-out CV probe AUROC | 1.000 | 1.000 | 1.000 | 1.000 | **1.000** |
| benign continuation NLL | 4.138 | 4.105 | 4.072 | 4.045 | 4.017 |

**The orthogonal complement gets *better* after the lesion.** Removing `u` post hoc from the
*intact* model's activations drops the probe 1.000 -> 0.80; removing 128 *random* directions
costs nothing. But the *lesioned* model — which was never allowed to write `u` at all —
reads 1.000 from that same complement. Replicated on all four lineages. The obvious
alternative (the lesion changes residual norms class-correlatedly and RMSNorm manufactures
the separability) is **rejected**: the probe still reads 1.000 on unit-normalised
activations, and the norm alone flips from a 0.985-AUROC harm detector to 0.167
(anti-predictive). The post-lesion orthogonality itself is *forced by construction* and is
not claimed as a result.

**Mechanism.** Held-out AUROC is already ~1.000 by layer 13 in both states, while the signal
along `u` grows ~138x with depth in the intact model and is zeroed at every depth in the
lesioned one. `u` is an **accumulator coordinate**, not where the percept lives.

**A few-prompt safety metric, with a clean negative control.** Fit the request axis at every
layer of one model from 128 harmful + 128 harmless *prompt-only* forwards — no generation,
no benchmark, no judge, no reference model:

| checkpoint | safety-tuned | best layer | depth fraction | Cohen's d |
|---|---|---|---|---|
| Qwen3-4B-Base (L1) | no | 29 | 0.81 | 5.68 |
| CohenQu FT-of-Base (L4) | no | 29 | 0.81 | 5.74 |
| Qwen3-4B (L2) | yes | 22 | 0.61 | 11.15 |
| Qwen3-4B-SafeRL (L3) | yes | 23 | 0.64 | 11.41 |

L4 is a fine-tune of L1 on a *non-safety* objective and lands on top of its parent, so this
tracks safety tuning rather than fine-tuning as such. n = 4 checkpoints: a demonstration with
one clean negative control, not a validated metric.

**What the community actually does (weights only).** `mlabonne/Qwen3-4B-abliterated` vs its
parent: per-matrix rank-one (median share 0.994) at implied `alpha` 0.973, `embed_tokens`
untouched — but **one direction per layer**: pooled rank-one share is only 0.433, and the
shallowest and deepest layers' edit directions are orthogonal (|cos| = 0.016).

**Honest limits.** The pre-registered *primary* damage variable is flat at ceiling, so no
matched-damage point exists and every registered S2 row is `INDETERMINATE` (failure mode F1);
the threshold was not relaxed. Read as the level test its wording specifies, K1 is
half-satisfied: CB survives, but A attenuates *without* collapsing into the null band. K4's
observed sign is **opposite** to its registered signature. All departures are enumerated in
the `deviations` list of `results.json`.

## Layout

| path | what it is |
|---|---|
| `method.py` | entry point; runs any stage or the whole pipeline |
| `pyproject.toml` | all 71 dependencies pinned to the versions this run executed with |
| `src/substrate.py` | STAGE 0 — builds the 150 twins, the 2x2 cells, the disjoint corpora, freezes `prereg.json` |
| `src/lexicon.py` | the fixed, mechanical, non-operational prefix lexicons |
| `src/engine.py` | model loading, the `Lesion` (exact output-projection edit), harvest hooks, OOM-halving batching |
| `src/seqbuild.py` | turns the substrate into token-level sequences with exact span control |
| `src/run_lineage.py` | STAGES 2-6 — harvests the full battery at every alpha for one lineage |
| `src/readouts.py` | STAGE 3 — the five candidate readouts, vectorised, plus `State` (sharded npz reader) |
| `src/analyze.py` | STAGES 3/5/6/8 — matched damage, integrity gates G1/G2/G3, S2 scoring, cross-lineage metric |
| `src/causal.py` | STAGE 7 — the causal arm: add/remove `r_content`, matched-norm control, labelled positive control |
| `src/redundancy.py` | how many directions carry the harm percept, and the depth profile of the regrowth |
| `src/weightcheck.py` | STAGE 9 — weights-only check against a real community abliteration |
| `src/stage9_depth.py` | STAGE 9b — is that edit one direction, or one per layer? |
| `src/emit.py` | writes `method_out.json` in the datasets-grouped `exp_gen_sol_out` schema |
| `src/assemble.py` | writes `results.json` and runs the T7 end-to-end validation |
| `src/shard_harvest.py` | converts oversized harvest `.npz` into verified parts under the size limit |
| `tests/test_sharding.py` | tests for the sharded-npz path |
| `out/prereg.json` | the frozen pre-registration (hash checked at the end) |
| `out/substrate.json` | the 150 twins, cells and corpora the results were computed on |
| `out/released_directions/` | the fitted `r_ablit` (all 36 layers) and `r_content` vectors |
| `results.json` | the full record: damage curves, gates, S2 table, causal arm, deviations, ledger |
| `method_out.json` + `full`/`mini`/`preview` | schema-validated example-level outputs |
| `FINDINGS.md` | the findings as they landed, including corrections I made to my own readings |
| `data/` | the two small source CSVs (XSTest with the `focus` join key; ungated AdvBench mirror) |

## How to run

```bash
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python --index-strategy unsafe-best-match \
    --extra-index-url https://download.pytorch.org/whl/cu124 -r pyproject.toml

uv run method.py                      # the whole pipeline
uv run method.py --stage substrate    # or one stage at a time
uv run method.py --stage harvest --lineages L2,L3
uv run method.py --stage analyze
.venv/bin/python tests/test_sharding.py
./finalize.sh                         # analyze -> shard -> redundancy -> emit -> assemble -> validate
```

Needs one ~20 GB GPU. Peak VRAM was 9.7 GB per lineage; the whole registered grid
(4 lineages x 5 strengths) took about 53 minutes of GPU time.

## Restoring removed files

Everything below is deleted from the published repo because it is regenerable. Each command
recreates it from scratch.

**`out/harvest/` — 100 files, 7.5 GB** of per-(lineage, alpha) activation harvests:

```bash
uv run method.py --stage substrate && uv run method.py --stage pilot && \
uv run method.py --stage harvest --lineages L2,L3,L1,L4
```

**`.venv/` — 5.3 GB** virtualenv:

```bash
uv venv .venv --python 3.12 && \
uv pip install --python .venv/bin/python --index-strategy unsafe-best-match \
    --extra-index-url https://download.pytorch.org/whl/cu124 -r pyproject.toml
```

**`src/__pycache__/`, `tests/__pycache__/`** — bytecode caches, recreated on any run:

```bash
python -c 'import compileall; compileall.compile_dir("src"); compileall.compile_dir("tests")'
```
