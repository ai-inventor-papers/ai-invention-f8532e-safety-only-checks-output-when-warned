# SPEC — Tier B intervention pass (`src/tierB.py`)

Authoritative definitions: `results/prereg.json` → `d_candidates`, `e_readout_target`, `tier_b`,
`stability_C`, `patching_H`, `transfer_I`, `c_fold_rule_and_prompts`. This file adds only
implementation detail. If this file and the prereg disagree, the PREREG wins.

## Scope and budget
- One checkpoint at a time; weights on GPU only while used. bf16, `attn_implementation="eager"`,
  `low_cpu_mem_usage=True`. fp16 arm loads fp16; int8 arms as built by the iteration-4 recipe.
- VRAM: `core.GpuLease(mib=4608, artifact="iter5_screen_tierB")` held only while weights are on the
  device (never across a download); `torch.cuda.set_per_process_memory_fraction(4.5 / total_GiB)`;
  on `torch.cuda.OutOfMemoryError` halve the batch (down to 1), never die. Peak VRAM < 4.5 GB,
  peak RSS < 10 GB (log both per checkpoint; do NOT set RLIMIT_AS in a CUDA process).
- Env: `TORCH_DISABLE_NATIVE_JIT=1 TOKENIZERS_PARALLELISM=false OMP_NUM_THREADS=4
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`. Do not touch HF_HOME (shared cache).
- Resumable: skip a tag whose `results/screen/ckpt_<tag>.json` has `"status": "OK"`.
  Write that JSON immediately after each checkpoint. A failure writes `status` =
  `INTERVENTION_MISSING` (cannot build/load) or `ERROR` (+ traceback head) and moves on.
- CLI: `python src/tierB.py --tags T1 T2 ... | --queue results/tierB_queue.json [--draws registered|stab4|stab18] [--max-minutes N]`

## Prompts, folds, render
- Prompt set = the registered S32 (prereg `c_fold_rule_and_prompts.S32_registered`): 11 H (XSTest
  harmful twins), their 11 Bn twins, 10 P (dolly). Row numbers index `I4/assets/stimuli.json`.
- Folds = prereg `folds["0"]` (A/B by pair_id and P stim). Fit on one fold, score on the other,
  swap, average (every scalar below). Stability draws use `S32_draws`/`folds_draws` per prereg.
- Render EXACTLY as the iteration-4 harvest rendered this arm (same chat template / system prompt /
  enable_thinking); see `src/ASSETS.md`. Sanity: compare the unperturbed last-token capture of the 32
  prompts with the stored `harvest/<tag>/A_prompt.npy` rows (same stimuli rows): report per-band
  median relative error; flag `RENDER_MISMATCH` if > 5e-2 at any band.

## Capture and intervention mechanics (batched per-row hooks)
- Capture the LAST-token residual at every hidden-state index 0..L with our own forward hooks
  (index 0 = embedding output, i = output of block i, L = final-norm output) — the convention fixed by
  `src/unit_tests.py` T10. X[b] = band mean over lo(b)..hi(b) (`core.band_indices`).
- Implement a per-ROW intervention so that many configurations run in ONE batch: for each block j,
  tensors `V_j (B,d)` (direction whose coefficient is removed; zero row = no-op), `D_j (B,d)`
  (displacement direction: = V_j for project-out, = r_i ⟂ V_j for the matched-norm random
  control), and a position mask `M (B,T)` (last prompt token only | all real positions |
  from the last prompt token onward during decoding). Update: `h <- h - M*(h·V_j) D_j`
  (fp32 math, cast back). A `patch` mode sets `h <- h + M*(target_j - h)` for patch rows.
  Keep T1/T2 semantics bit-for-bit (reuse `interv.orthogonal_random`, seeded per prereg rule).
- Record for every intervened row/block: `||dh||/||h||` at the last token, and the norm percentile of
  the intervened residual inside the model's own unperturbed norm distribution at that index
  (unperturbed norms of all 32 prompts) → `norm_displacement[band]` = median/p90 of both.

## Quantities per checkpoint (registered draw)
Notation per fit fold: F_b, N6_b (b=1..6), r_late = F_B6, b*_read (argmax_b 1..6 fit-fold Cohen's d
of <X[b],F_b> H vs P), b*_write (same over 1..5). Scoring fold: p0 = mean_H <X[B6], r_late>,
mean_P likewise, gap = |p0 − mean_P|; p0_Bn = mean_Bn <X[B6], r_late>.
1. W1 curve b=1..6: F_b project-out on scoring-fold H rows (site last, all blocks of band b) → p1_F;
   10 R draws → p1_R_i; W1(b) = (|p1_F−p0| − median_i|p1_R_i−p0|)/gap. Registered = W1(b*_write).
   Also save per-item |Δ| for F and each R (for the prompt bootstrap in S5).
2. W5 curve: N6_b project-out on scoring-fold Bn rows, R ⟂ N6_b, baseline p0_Bn, same normaliser.
   W6 = W5 − W1 at b*_write.
3. W2: greedy nested order over bands 1..5 on the FIT fold H rows (step 1: the single band with the
   largest drop of mean_H <X[B6],r_late>; step k: the band adding the largest drop given the chosen
   set, all bands ablated JOINTLY with their own F_b). Scoring fold: ablate first k bands jointly,
   k=1..5; W2 = smallest k with (p_k − mean_P) < 0.5 (p0 − mean_P); else 7 (CENSORED). Save the
   order, the p_k ladder and the raw-offset variant (p_k < 0.5 p0).
4. W3 at B4 (registered): F_B4 project-out at ALL real positions vs LAST token only;
   W3 = |p1_all − p0| / |p1_last − p0|; CENSORED_HIGH if |p1_last − p0| < 0.05·gap.
5. W4 at b*_write from the F run: c_b = mean over rows of Δ<h,F_b> at index hi(b) / mean‖h‖ at hi(b);
   c_end = same at index L; W4 = clip(1 − |c_end|/|c_b|, −1, 1).
6. W7: greedy decode 8 tokens (no KV cache is fine) for scoring-fold H rows: unperturbed, F_{b*_write}
   project-out with mask = positions ≥ last prompt token, and 10 R draws; read <X[B6] at each generated
   position, r_late>; W7 = mean_t (|p1_F,t − p0_t| − median_i |p1_R_i,t − p0_t|)/gap; save 8-point curve
   and generated token ids of the unperturbed run.
7. W8: lesion hooks on every block's attention-output and MLP-output projection (arch map from
   `interv.py`; NotSupported → W8 NOT_RUN) with u = F_{b*_write} (fit fold), alpha 1.0; refit F'_b
   for b ∈ {4,5,6} on the scoring fold (H vs P) under the lesion; W8 = 1 − mean_b |<F_b, F'_b>| with
   F_b from the UNlesioned scoring fold.
8. Contentless render Xc (tokenizer chat template, one EMPTY user turn, add_generation_prompt=True,
   enable_thinking=False when the template accepts it; base models without a template: BOS only):
   A1_prior = (<Xc[b*_read],F> − mean_P)/(mean_H − mean_P) (scoring-fold means);
   A2 at B5 per prereg (u_ref = unit(mean_t gamma⊙WU_ref[t]) — take WU_ref.npy and gamma.npy from the
   tag's harvest dir): print A2, A2_cos, A2_mag.
9. Prompting ceiling bar: wrap each of the 32 prompts as "Is the following request harmful? Answer
   Yes or No.\n\nRequest: <text>" in the model's chat template; score = logit(" Yes"|"Yes") −
   logit(" No"|"No") (first token of each; record the token ids used); report Cohen's d and AUROC
   of H vs (Bn+P). This is a BAR (text/logit), never a candidate.
10. AMS batch-8 emulation bar: the 96 AMS prompts (raw text, NO chat template; source per
   `src/ASSETS.md`), batch 8, `padding=True` with the tokenizer's DEFAULT padding side, read
   hidden_states[:, -1, :] (pad positions may be read — this is the disclosed hazard); compute the
   Tier-1 sigma with `reuse.ams_reimpl` on this array, and on a batch-1 run; print both.
11. Patching validation (only rows in prereg `patching_H.rows`): at B4, replace the last-token
   residual at each B4 block with the mean fit-fold P activation at that block index; per-item effect
   on <X[B6], r_late> vs per-item W1 F effect at B4 → Spearman across items (report n).
12. Sanity signals (log + store): p0 comfortably non-zero with per-item spread; |p1_F − p0| at B4 >
   median |p1_R − p0|; disp ratio mostly in 0.02–0.35; W2 ∈ {1..5,7}; W8 ∈ [0,1].

## Stability draws (prereg `stability_C`), reduced battery
For each extra draw (prompt_draw, fold_seed[, band_offset]) recompute with the draw's prompts/folds:
W1 and W5 at b*_write (5 R draws), W2, W3, W4, W6, W8, A1_prior, A2. Skip W7 and patching.
STAB18 rows get 18 draws, all other rows 4 (`--draws stab4`); if time is short, STAB18 rows drop to
the 4-draw grid (F9 step 1, recorded as a deviation). W2 transfer on A_c11 prompts (H=sev3, P=sev0;
texts in `I4/assets/c11_items.json`) runs only on STAB18 rows.

## Output per checkpoint
`results/screen/ckpt_<tag>.json`:
```
{"tag","status","repo","arm","n_layers","hidden","dtype","render":{...},"sanity":{...},
 "registered":{"W1","W2","W3","W4","W5","W6","W7","W8","A1_prior","A2","A2_cos","A2_mag"},
 "censored":{"W2":bool,"W3":bool}, "bstar":{"read":{"A":b,"B":b},"write":{"A":b,"B":b}},
 "curves":{"W1":[6],"W5":[6],"W7":[8],"W2_ladder":[...],"W2_order":{"A":[..],"B":[..]}},
 "per_fold":{...}, "norm_displacement":{...}, "stability":{"draws":[{...,"values":{...}}]},
 "patching":{...}|null, "bars":{"prompting_ceiling":{...},"AMS_T1_b1":..,"AMS_T1_b8_emulated":..},
 "transfer":{"W2_c11":..}|null, "timings":{...}, "peak_vram_gb":..,"peak_rss_gb":..,"utc":..}
```
plus `results/screen/ckpt_<tag>_items.npz` (per-item projections for every config) — never inline
arrays in JSON.
