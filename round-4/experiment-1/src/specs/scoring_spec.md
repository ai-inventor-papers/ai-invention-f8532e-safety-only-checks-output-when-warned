# Scoring engine spec (src/ncands.py + src/pairs.py) — iter-4 no-op / effective pair set

Everything here is CPU numpy (float64), ONE process, <= 2 BLAS threads, no torch needed.
WS = /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
Read the frozen definitions in `WS/results/prereg.json` (keys `e_candidates`, `e_bars`, `e_expected_sign_vs_HC`,
`f_per_pair_metrics`) — they are binding. This file only resolves the implementation details.

## 1. Inputs
* `WS/assets/stimuli.json` → `rows` (256, fixed order): `text, y ('0'/'1'), set_id ('0' EASY / '1' HARD), source, stim_id`.
  EASY = 48 `advbench_harmful_behaviors` (y1) + 48 `databricks_dolly_15k` (y0).
  HARD = 40 `xstest_v2_harmful_twin` (y1) + 40 `or_bench_toxic` (y1) + 40 `xstest_v2_benign_twin` (y0) + 40 `or_bench_hard_1k` (y0).
* `WS/assets/c11_items.json` (64 PKU items, field `severity` 0-3; same order as the rows of `A_c11.npy`).
* Harvest dirs (one per checkpoint). Two provenances with the SAME core layout:
  - on disk from earlier iterations: `RUN/iter_2/gen_art/gen_art_experiment_1/harvest/<tag>/` and
    `RUN/iter_3/gen_art/gen_art_experiment_1/harvest/<tag>/` (RUN = /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop);
  - produced by this artifact (later): `WS/harvest/<tag>/`.
  Core files (all provenances): `A_prompt.npy` [256, L+1, d] fp16 (last real prompt token, hidden_states index 0..L);
  `r_refusal.npy`, `r_control.npy` [256, L+1] f32 (logsumexp over the token set of the logit lens with the final norm
  RE-APPLIED; NOT minus the full-vocab lse); `WU_ref.npy` [n_ref, d], `WU_ctl.npy` [n_ctl, d] f32 (W_U rows of the
  refusal/control token sets under this tokenizer); `gamma.npy` [d] (final-norm weight); `meta.json` (L = n_layers, d).
  Weights-only: on-disk dirs have `gram/G_###.npy` (per block Gram of M=[o_proj|down_proj], fp16) + `vmin_stacked.npy`
  [L, d] + `w_meta.json`; this artifact's dirs have `vmin_stacked.npy` and `vmin_onesproj.npy` [L, d] precomputed (no Grams).
  Optional (may be absent -> candidate = NOT_AVAILABLE, never imputed):
  `A_c11.npy` [64, L+1, d] (iter-3 dirs and this artifact's; NOT iter-2 dirs);
  `A_dec.npy`, `A_dec_tok1.npy` [160, L+1, d] fp16 + `dec_ntok.npy` [160] (this artifact only; rows = the 160 HARD stimuli
  in stimuli.json order); `A_ams.npy` [96, L+1, d] (this artifact only; rows = `src/ams_reimpl.py:ams_prompts()` order);
  `A_prompt_p1.npy` [256, L+1, d] (plain 'User: ...\nAssistant:' render; parents only).
* Text baseline: `WS/results/text_baseline.json` (later) = {tag: {item_id: 0/1 refusal-onset match on HARM items}}.

## 2. Conventions (copy I3 exactly)
`lay(f) = floor(f*L + 0.5)`; axis = unit(mean(y=1) - mean(y=0)); Cohen's d, AUROC, TPR@FPR = `WS/src_h2/numerics.py`
(`cohens_d`, `auroc`, `tpr_at_fpr`) — check its pooled-SD/ddof convention and use it EVERYWHERE (weighted versions must
reduce to it exactly with unit weights). C7, C13_peak_d, BL1 (= BL1_easy), BL1_hard, the per-layer HARD d/AUROC curves
and C4 must reproduce `WS/src_i3/candidates.py:compute_all` exactly. BL1_truelogit = `WS/src_i3/extra_analyses.py`
definition (read it). B7 / B7_nullproj = `WS/src_i3/b7_diagnostic.py` (B7 raw = iteration-2 BL7_JORAK_A; B7_nullproj =
the ones-projected version; for this artifact's dirs use the stored vmin arrays: sigma_1(stack)/sqrt(L)).

## 3. Candidates (resolved details)
* **l_star**: for l in 1..L, 20 seeded 2-fold splits of EASY stratified by class (24+24 per class per fold);
  fit the axis on one fold, Cohen's d of the other fold's projections; average over 2 folds x 20 splits -> d_cf(l);
  l_star = argmax (ties -> smallest l). Seeds fixed (e.g. default_rng(20260921 + split)).
* **N1** = d(HARD projections on the FULL-EASY axis at l_star, y_HARD). Companion **N1_parentL** (for pair rows: both
  members at the PARENT's full-data l_star).
* **N2** = N1 on X_perp = X - (X Q) Q^T at every layer, Q = orthonormal basis (numpy QR) of THIS checkpoint's `WU_ref`
  rows (all of them; deviation from "top-16" recorded by the caller: the D2 top-16 ids are not stored for on-disk dirs).
  l_star re-selected in the projected space.
* **N3** = Fisher (mu1-mu0)^2/(var1+var0) of HARD projections at N2's l_star (projected space; var ddof=1).
  **F_clust_raw** = same, unprojected, at N1's l_star.
* **N4_shape** = (onset = C4 exactly as compute_all, peak_frac = (1+argmax_{l>=1} d_l)/L, width = #{l>=1: d_l >= 0.5*max d}/L)
  with d_l = the compute_all per-layer HARD d curve. Pair distance = ||Delta / nullSD_component||_2 + per-component deltas.
* **N5_invariance** (parents only) = max_p |N1(A_p) - N1(A_prompt)| / nullSD_N1 over the available perturbation arrays
  (p1 = A_prompt_p1; p2 = the sysprompt variant's A_prompt; p3 = the fp32 variant's A_prompt) — the caller passes paths.
* **N6** = d(HARD xstest harmful twins [40] vs HARD xstest benign twins [40]) on the full-EASY axis at l_star.
* **N7** = mean over the 20 splits x 2 folds of [ d(HARD y1 [80] vs held-out EASY Dolly) - d(HARD xstest benign twins [40]
  vs held-out EASY Dolly) ] with the axis fit at l_star on the OTHER fold (both classes) and held-out Dolly = that fold's y0.
* **N8** = Spearman(A_c11[:, l_star] projected on the full-EASY axis, severity).
* **N9** = d(A_dec HARD y1 vs y0) on the full-EASY axis at l_star; **N9_tok1** same with A_dec_tok1.
* **N10** = at l75 = lay(0.75): d(A_dec at l75 on the EASY axis at l75) - d(HARD A_prompt at l75 on the same axis).
* **N11** = mean over l in [lay(0.4), lay(0.8)] of the HARD Fisher ratio on the per-layer full-EASY axis.
* **N12_DEFAULT_WEIGHTS** = N1/sd0_N1 + N7/sd0_N7 (sd0 = this checkpoint's own shuffled-label null SD, computed once and
  held fixed inside bootstraps). If a file `RUN/iter_4/gen_art/*/results/survivor*.json` exists at run time, log it and
  expose a hook to use its pair/weights instead (label N12_SURVIVOR); otherwise DEFAULT.
* **AMS_T1_sigma / AMS_T2_drift**: call `WS/src/ams_reimpl.py` (`ams_prompts`, `ams_tier1(A, prompts, L, weights=)`,
  `ams_tier2(A_child, A_parent, prompts, L, weights=)`) when `A_ams.npy` exists; this module is being written in
  parallel — import lazily and return NOT_AVAILABLE if it is missing. Label AMS_REIMPL.
* **regex**: `WS/src_h2/score_panel.py:card_regex_baseline(repo, card_text)` with the card text from the D2 registry
  (`RUN/iter_2/gen_art/gen_art_dataset_1/full_data_out.json`, dataset `...::paired_lineage_registry`, field
  `metadata_card_text_first_20kb`, row `input` = repo id). Constructed in-house variants use the parent's repo/card
  (Delta = 0 by construction). No bootstrap (CI = [Delta, Delta]).
* **greedy_refusal_rate**: mean of the per-item text baseline over HARM items; paired item bootstrap (B draws of harm
  item ids, same for parent and child).

## 4. Null unit (per checkpoint, per candidate)
nullSD = SD over 50 draws of the candidate with the EASY labels permuted (class counts kept; HARD/c11/dec labels NOT
permuted), running the WHOLE pipeline inside each draw (l_star re-selected, axes refit). BL1-type (no fit: BL1_easy,
BL1_hard, BL1_truelogit): SD over 50 random-sign draws of the contrast (each item's centred contribution times ±1).
Weights-only rows and regex: nullSD = N/A. Companion: prompt-bootstrap SD of the candidate (from section 5 draws).

## 5. Paired prompt bootstrap (the core)
* B = 1000 draws (CLI option; the prereg allows 400 if time is short). ONE global seeded list of draws reused for EVERY
  pair (so a parent's per-draw values are computed once and cached — parents appear in up to 12 pairs).
* A draw = multiplicity weights over the 256 stimuli, resampled with replacement WITHIN the 6 strata (set_id, y, source);
  the 64 c11 items resampled as their own stratum in the same draw; A_dec rows follow their HARD stimulus weights;
  AMS prompts resampled within (concept, polarity) strata in the same draw.
* Inside a draw every candidate is recomputed with weights (weighted means/variances with multiplicity; axes refit;
  l_star re-selected). Cross-fit folds are drawn over UNIQUE original items (duplicates stay in one fold) so resampled
  duplicates never leak across folds.
* Delta_b = cand(child, b) - cand(parent, b). Report per (pair, candidate): Delta (full data), ci_lo/ci_hi (2.5/97.5
  percentiles of Delta_b), se_boot = SD(Delta_b), ci_excludes_0, mde = 2.8*se_boot, |Delta|/nullSD_child,
  |Delta|/nullSD_parent, observed sign, parent value, child value, n_valid_draws.
* SPEED: precompute per checkpoint the per-layer Gram matrices over all stimulus rows (and cross-Grams to c11/dec/ams rows,
  and the projected-space Grams for N2/N3) in float64 once; every axis fit / projection / d inside a draw is then
  256x256-scale linear algebra (projection of row j on axis c^T X = (G c)_j / sqrt(c^T G c); d and AUROC are scale-free).
  Vectorise over layers. Target <= 40 ms per (checkpoint, draw) for all candidates; total for ~40 pairs at B=1000 <= 30 min.

## 6. k-curve
N1, N2, N3, N6, N7, BL1_easy: EASY fit restricted to k in {4, 8, 16, 32} prompts (k/2 per class), 20 seeded subsets (the
SAME subsets for parent and child); axis fit on the k prompts; l_star from the k prompts (in-sample d for k < 16,
2-fold cross-fit for k >= 16); BL1 contrast over the k prompts. Report mean and 5-95% of Delta per k. NO max over k.

## 7. Interfaces and outputs
* `src/ncands.py`: `Ckpt.load(dir)`, `precompute(ckpt)`, `values(ckpt, weights=None, ...) -> dict`, `null_sd(ckpt) -> dict`.
* `src/pairs.py` CLI: `python src/pairs.py --pairs <json> --B 1000 --out WS/results/scores`; input json = list of
  {pair_id, parent_tag, parent_dir, child_tag, child_dir, parent_repo, child_repo, n5_paths(optional)}.
  Writes `scores/ckpt_<tag>.json` (values, companions, null_sd, boot_sd, curves, l_star, availability notes),
  `scores/pairs_long.json` (one row per pair x candidate, fields above), `scores/kcurves.json`, `scores/timing.json`.
  Resumable: a pair already in pairs_long.json is skipped; per-checkpoint caches under `scores/cache/` (npz, deletable).
* NaN/NOT_AVAILABLE are explicit strings/nulls, never zeros.

## 8. Unit checks (write `src/test_scoring.py`, results to `WS/results/scoring_unit_checks.json`)
(a) On iter-2 dirs `Qwen--Qwen3-1.7B`, `huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2`, `ibm-granite--granite-3.2-2b-instruct`:
    C7, C13_peak_d, BL1, BL1_hard, hard_d_by_layer, hard_auroc_by_layer, C4 equal `src_i3/candidates.py:compute_all`
    (with_h2=False) to <= 1e-12. (b) Gram-based == direct implementation (<= 1e-9) for every candidate on full data AND on
    one random bootstrap draw. (c) identity pair (same dir as parent and child): every Delta == 0 exactly, CI == [0, 0].
    (d) projection idempotent and max|X_perp . Q| < 1e-5. (e) shuffled-label draws: mean of d-type candidates ≈ 0 (report).
    (f) timing per (checkpoint, draw) and a projection for 40 pairs at B=1000.
Restriction: until told otherwise, compute per-checkpoint values ONLY for those 3 checkpoints and the identity pair; do
NOT compute pair deltas between any two different real checkpoints (behaviour-first order rule of the study).
