# JOIN CONTRACT — `HG__deepseek-ai--deepseek-coder-1.3b-instruct`

`deepseek-ai/deepseek-coder-1.3b-instruct` @ `e063262dac83` · L = 24 layers (so **L+1 = 25** hidden indices, 0 = embedding output,
i+1 = output of block i) · d = 2048 · params 1346471936 · tie_word_embeddings = `False` ·
forward batching = `batch1 (every forward-only pass; padding-free, single kernel path)`

This directory is **substrate only**. It holds activations, a direction bank and a
forward-only intervention grid. It contains **no candidate score, no ranking and no
correlation** — by design, because the sibling screen artifact freezes its candidate list
before it opens anything here. Below, each array is paired with what a later GPU-free scorer
could compute *from* it. **None of those quantities is computed in this artifact.**

## Bands are fractions of depth, never layer indices

Band `b` (1..6) = blocks `[floor((b-1)L/6), floor(bL/6))`. L differs across the panel
(640/1024/1152/2048/2560/3072/3840 hidden sizes; 18–54 layers), so any join across
checkpoints must use the band index, never an absolute layer number.

## Base arrays

| file | shape | dtype | what it is | what it supports computing |
|---|---|---|---|---|
| `A_prompt.npy` | [256, 25, 2048] | <f2 | last-prompt-token residual at every layer over the frozen 256 prompt-site stimuli (`assets/stimuli.json`, `y=1` harmful) | a prompt-site read of any direction; the recognition axis; per-layer separation |
| `A_prompt_p1/p2/p3.npy` | [256, 25, 2048] | <f2 | the same stimuli under three EXPRESSION-ONLY perturbations (p1 plain render, p2 helpful system prompt, p3 the same weights cast to float16) | expression-invariance of any prompt-site readout: it must move under a template change only as much as behaviour does |
| `A_dec.npy` / `A_dec_tok1.npy` | [160, 25, 2048] | <f2 | decode-site residuals: mean over generated positions before the first EOS, and the FIRST generated position | a decode-site readout, and the prompt-site vs decode-site contrast |
| `dec_ntok.npy` | [160] | <i4 | tokens actually generated per row before EOS | the denominator for any decode-site mean; a degenerate-generation filter |
| `A_c11.npy` | [64, 25, 2048] | <f2 | 64 graded-severity prompts (`assets/c11_items.json`) | severity monotonicity of a readout |
| `A_ams.npy` | [96, 25, 2048] | <f2 | the 96 rows of `ams_prompts()` (3 concepts × 16 pairs × 2 polarities) in that exact order, RAW text with NO chat template, as the AMS code path pins | the AMS Tier-1 separation sigma, the published baseline instrument, side by side with any activation readout (`results/ams_baseline.json`) |
| `A_cells96.npy` | [96, 25, 2048] | <f2 | the 96 XSTest 2×2 cells (`assets/cells.json`), chat-templated | a cell-level read of the 2×2 design; NOT the AMS row set |
| `WU_ref/WU_hed/WU_ctl.npy` | [22, 2048] / [8, 2048] / [26, 2048] | <f4 | unembedding rows for refusal / hedge / control tokens, resolved through THIS checkpoint's own tokenizer (kept counts in `meta.json`, never padded) | the LOGIT-ONLY baseline: refusal-token mass, and the logit gap |
| `r_refusal/r_hedge/r_control/r_fullV_final.npy` | [256, 25] | <f4 | per-layer logit-lens drives on the 256 stimuli | a logit-lens trajectory; where refusal drive appears in depth |
| `norms.npy` | [256, 25] | <f4 | residual norms | dimensionless ratios, so a readout is not a norm artefact |

## Direction bank — fitted from THIS checkpoint's own activations, parent-free

| file | shape | what it is | what it supports computing |
|---|---|---|---|
| `dirs_F.npy` | [6, 2048] | per-band harmful-vs-benign request axis, unit-normalised band-mean difference-in-means at the last prompt token | the site-local read/write direction per band |
| `dirs_N6.npy` | [6, 2048] | per-band XSTest benign-twin axis | the over-refusal-relevant axis, distinct from raw harmfulness |
| `dirs_R.npy` | [6, 5, 2048] | matched random directions per band, Gram–Schmidt orthogonalised against BOTH F and N6, seeded `sha256(seed+tag+band)` | the null distribution for any direction-specific claim |
| `fit_halves.npy` | [6, 2, 2048] | the TWO split-half fits of F per band | direction stability = the cosine between the halves. **The halves are saved; the cosine is NOT taken here.** |

## Intervention grid — `cells/<cell_id>/`, catalogue in `cells_index.json`

An intervention projects a direction out of the residual stream at every layer of a band, at a
SITE (`P` = last prompt token, `A` = all prompt positions), then continues the forward pass.
The 32 prompts (16 harmful / 16 hard-benign) and their hash are in `cells_32.json`; row order
is preserved exactly.

Cell families: `arm0` (no intervention, both sites) · `C2` site-local 6 bands × {F, N6} ×
{P, A} · `C3` matched-displacement random controls · `C4` the nested cumulative ladder
S1={B4} … S6={B1..B6}. Per cell: `proj.npy` (projection of each layer's residual onto the
fixed K-direction bank; for site A two slices, position-mean and last token), `norms.npy`,
`logits.npy` (softmax mass on WU_ref / WU_hed / WU_ctl at the next-token position),
`topk_ids.npy` / `topk_probs.npy`, and `full.npy` (the whole residual, f16) for arm0, the C2
F/N6 cells and the C4 ladder cells only.

**The R cells are MATCHED-DISPLACEMENT, not matched-norm-direction**: the edit is
`h ← h − (h·f̂)·r̂`, so the displacement magnitude equals the F cell's `|h·f̂|` token by token
(verified by selftest T3d at 1.0002×). Projecting out a random *unit* direction would remove
only `|h·r̂|`, which is negligible in high dimension, and would not be a matched control.

What the grid supports computing, and this artifact does not:

- a **site-local write-gain** statistic: contrast `proj.npy` of a C2 cell against `arm0` at
  layers ABOVE the ablated band, net of the C3 cells at identical displacement;
- a **redundancy-depth** statistic: the C4 ladder S1→S6 read as the cumulative change in
  refusal-token mass in `logits.npy` relative to `arm0`;
- a **specificity** statistic: the same contrasts on the benign half of `cells_32.json`;
- a **direction-vs-magnitude** test: any F/N6 effect must exceed its matched-displacement C3
  null, which is what makes the effect attributable to the direction rather than to the kick.

## Provenance and gating

`meta.json` carries the repo, revision sha, depth, width, dtype, tie_word_embeddings,
chat-template sha, trust_remote_code, load format, transformers version, the 6-tensor
`weight_fingerprint` AND `weight_sha_full` (the fingerprint cannot see q/v LoRA merges),
per-stage timings, the WU kept counts and the peak VRAM. `MANIFEST.sha256.json` hashes every
file, and `DONE` is written last.

This directory exists only because `HG__deepseek-ai--deepseek-coder-1.3b-instruct` appeared in a `graded_truth_s<N>.json` whose sha256
was already in `logs/chain.jsonl` when the harvest started — the ORDER GATE. The behaviour was
graded before the activations were read, never the other way round, and
`src/hygiene_check.py all` re-audits that ordering.

_Generated 2026-09-22T04:53:25Z by `src/join_readme.py`._
