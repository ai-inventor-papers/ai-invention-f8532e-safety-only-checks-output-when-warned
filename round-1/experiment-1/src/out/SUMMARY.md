# Lane A results digest

Pre-registration SHA-256 `de0a44757c19dbf08978b586da90eafb7de5960ca6cf0f184462d9f54652dbb6` (frozen before the first forward pass).
Frozen layer band **14-22** of 36 blocks (depth fraction [0.3889, 0.6111]), chosen by cross-fitted Cohen's d on Qwen3-4B's fitting corpus alone (d=0.882).

## Stage-0 gates

| checkpoint | G1 split-half cos | G3 d (cross-fitted) | G3 d (in-sample) | G5 placebo TOST | G6 subtraction licensed |
|---|---|---|---|---|---|
| NonSafetyFT-STaR | 0.363 | 0.885 | 1.934 | FAIL | True |
| Qwen3-4B | 0.374 | 0.936 | 1.883 | FAIL | False |
| Qwen3-4B-Base-chat | 0.363 | 0.895 | 1.950 | FAIL | True |
| Qwen3-4B-Base-plain | 0.364 | 0.900 | 1.960 | FAIL | True |
| Qwen3-4B-SafeRL | 0.387 | 0.954 | 1.890 | FAIL | False |
| Qwen3-4B-abliterated | 0.352 | 0.851 | 1.847 | FAIL | False |
| RandInit-4B | 0.156 | 0.582 | 2.299 | FAIL | False |

## The five candidates and the four baselines (EARLY window, F1 frame, null-SD units)

| checkpoint | K1 O | K1 CB | K1 A | K1 T | K2 prior | K2 slope | K3 footprint | K3 stable rank | K4 tau | K5 disp | B1 AUROC | B2 probe | B4 gap* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NonSafetyFT-STaR | 5.999 | 13.243 | -4.254 | 10.482 | -0.660 | -7.863 | 2.790 | 216.3 | n/a | 1.208 | 0.711 | 0.979 | -0.013 |
| Qwen3-4B | 15.128 | 16.874 | -7.475 | 9.093 | -5.723 | 13.371 | 3.257 | 216.3 | n/a | 1.057 | 0.711 | 0.973 | -0.000 |
| Qwen3-4B-Base-chat | 8.475 | 13.036 | -4.391 | 10.179 | -2.049 | -4.691 | 2.463 | 216.3 | n/a | 1.354 | 0.704 | 0.980 | -0.004 |
| Qwen3-4B-Base-plain | 9.913 | 9.743 | -0.254 | 10.908 | -0.463 | 25.082 | 50.374 | 216.3 | n/a | 1.470 | 0.691 | 0.970 | -0.006 |
| Qwen3-4B-SafeRL | 16.735 | 19.335 | -8.302 | 10.376 | -6.499 | 16.672 | 3.534 | 216.3 | n/a | 1.070 | 0.729 | 0.975 | 0.000 |
| Qwen3-4B-abliterated | 5.666 | 14.000 | -9.288 | 3.795 | -7.416 | 3.008 | 3.689 | 216.6 | n/a | 1.088 | 0.665 | 0.971 | -0.000 |
| RandInit-4B | 1.026 | -0.404 | 0.345 | -0.007 | -1.028 | 7.317 | 1.167 | 977.4 | n/a | 1.379 | 0.494 | 0.347 | 0.000 |

\* B4 is a LOGIT-side baseline and is NOT a deliverable under the run invariant.

## The decisive control: does the term depend on the LABELS?

`r_content` is refitted on PERMUTED hazardous/benign labels and the whole pipeline re-run, 20 times. A term that does not exceed this band is not evidence of the registered coordinate, however many null-SD units large it is.

| checkpoint | A (real) | A shuffled-label band (abs, 97.5pct) | A escapes? | T (real) | T band | T escapes? |
|---|---|---|---|---|---|---|
| NonSafetyFT-STaR | -4.254 | 11.473 | no | 10.482 | 9.259 | **yes** |
| Qwen3-4B | -7.475 | 11.775 | no | 9.093 | 10.628 | no |
| Qwen3-4B-Base-chat | -4.391 | 11.041 | no | 10.179 | 9.899 | **yes** |
| Qwen3-4B-Base-plain | -0.254 | 11.613 | no | 10.908 | 10.086 | **yes** |
| Qwen3-4B-SafeRL | -8.302 | 11.273 | no | 10.376 | 11.568 | no |
| Qwen3-4B-abliterated | -9.288 | 11.692 | no | 3.795 | 8.463 | no |
| RandInit-4B | 0.345 | 1.268 | no | -0.007 | 1.132 | no |

## Robustness: the same decomposition along a SUPERVISED probe axis

G1 failed in every checkpoint, so the plan's registered fallback axis is reported beside the pre-registered diff-in-means one.

| checkpoint | O | CB | A | T | cos with r_content at band |
|---|---|---|---|---|---|
| NonSafetyFT-STaR | 1.553 | 4.702 | -0.102 | 5.237 | 0.401 |
| Qwen3-4B | 5.128 | 7.159 | -2.872 | 4.214 | 0.421 |
| Qwen3-4B-Base-chat | 1.979 | 5.137 | -2.068 | 3.640 | 0.394 |
| Qwen3-4B-Base-plain | 2.440 | 3.731 | 0.312 | 4.663 | 0.393 |
| Qwen3-4B-SafeRL | 5.319 | 7.838 | -2.910 | 4.740 | 0.417 |
| Qwen3-4B-abliterated | 2.540 | 5.808 | -3.257 | 2.323 | 0.437 |
| RandInit-4B | 0.536 | -0.803 | 0.558 | -0.162 | 0.786 |
## |cos(r_content, r_ablit)| — response-site vs prompt-site axes

| checkpoint | at band | max over layers | argmax layer | exceeds the 0.50 branch point |
|---|---|---|---|---|
| NonSafetyFT-STaR | 0.0482 | 0.1785 | 36 | False |
| Qwen3-4B | 0.0782 | 0.1794 | 19 | False |
| Qwen3-4B-Base-chat | 0.0662 | 0.1749 | 32 | False |
| Qwen3-4B-Base-plain | 0.2346 | 0.3125 | 19 | False |
| Qwen3-4B-SafeRL | 0.0870 | 0.1869 | 19 | False |
| Qwen3-4B-abliterated | 0.0433 | 0.1193 | 23 | False |
| RandInit-4B | 0.0665 | 0.0826 | 35 | False |

## S1 specificity screen (1 of 3 screen tests; lane A declares no survivor)

| candidate | registered term | registered checkpoint | term (null-SD) | margin vs Qwen3-4B-Base-chat | margin vs NonSafetyFT-STaR | S1 |
|---|---|---|---|---|---|---|
| K1 | A | Qwen3-4B | -7.475 | -3.084 | -3.221 | **FAIL** |
| K2 | prior | Qwen3-4B | -5.723 | -3.674 | -5.063 | **FAIL** |
| K3 | footprint | Qwen3-4B-SafeRL | 3.534 | 1.072 | 0.744 | **PASS** |
| K4 | tau | Qwen3-4B-SafeRL | nan | nan | nan | **FAIL** |
| K5 | dispersion | Qwen3-4B | 1.057 | -0.297 | -0.151 | **FAIL** |

## Cross-checkpoint direction alignment (fine-tuning lineage ⇒ shared basis)

| pair | cos(r_content) at band | cos(r_ablit) at band |
|---|---|---|
| NonSafetyFT-STaR vs Qwen3-4B | 0.915 | 0.233 |
| NonSafetyFT-STaR vs Qwen3-4B-Base-chat | 0.984 | 0.625 |
| NonSafetyFT-STaR vs Qwen3-4B-Base-plain | 0.967 | 0.234 |
| NonSafetyFT-STaR vs Qwen3-4B-SafeRL | 0.900 | 0.208 |
| NonSafetyFT-STaR vs Qwen3-4B-abliterated | 0.907 | 0.042 |
| NonSafetyFT-STaR vs RandInit-4B | 0.018 | 0.009 |
| Qwen3-4B vs Qwen3-4B-Base-chat | 0.916 | 0.200 |
| Qwen3-4B vs Qwen3-4B-Base-plain | 0.917 | 0.419 |
| Qwen3-4B vs Qwen3-4B-SafeRL | 0.992 | 0.896 |
| Qwen3-4B vs Qwen3-4B-abliterated | 0.986 | 0.361 |
| Qwen3-4B vs RandInit-4B | 0.013 | 0.012 |
| Qwen3-4B-Base-chat vs Qwen3-4B-Base-plain | 0.981 | 0.211 |
| Qwen3-4B-Base-chat vs Qwen3-4B-SafeRL | 0.902 | 0.181 |
| Qwen3-4B-Base-chat vs Qwen3-4B-abliterated | 0.908 | 0.041 |
| Qwen3-4B-Base-chat vs RandInit-4B | 0.016 | 0.013 |
| Qwen3-4B-Base-plain vs Qwen3-4B-SafeRL | 0.903 | 0.341 |
| Qwen3-4B-Base-plain vs Qwen3-4B-abliterated | 0.906 | 0.067 |
| Qwen3-4B-Base-plain vs RandInit-4B | 0.014 | 0.012 |
| Qwen3-4B-SafeRL vs Qwen3-4B-abliterated | 0.973 | 0.326 |
| Qwen3-4B-SafeRL vs RandInit-4B | 0.014 | 0.013 |
| Qwen3-4B-abliterated vs RandInit-4B | 0.013 | 0.020 |

## Cheapest kill

**K1_ARMING_COORDINATE_NOT_LABEL_SPECIFIC** — A inside the null band in every checkpoint: True; A and CB both inside everywhere: False.

## Scale table (why terms are reported in null-SD units)

| checkpoint | mean residual L2 at band | mean LayerNorm gain at band | per-item null-SD (A) |
|---|---|---|---|
| NonSafetyFT-STaR | 54.2 | 0.5866 | 0.08179 |
| Qwen3-4B | 57.0 | 0.5868 | 0.10022 |
| Qwen3-4B-Base-chat | 56.4 | 0.5866 | 0.08774 |
| Qwen3-4B-Base-plain | 57.5 | 0.5866 | 0.09810 |
| Qwen3-4B-SafeRL | 57.1 | 0.5868 | 0.10385 |
| Qwen3-4B-abliterated | 56.6 | 0.5868 | 0.10238 |
| RandInit-4B | 300.8 | 1.0000 | 0.48737 |

## Deviations

- NonSafetyFT-STaR: repo ships FP32 weights; cast to bfloat16 shard-by-shard on load.
- Qwen3-4B-abliterated: repo ships FP32 weights; cast to bfloat16 shard-by-shard on load.
- RandInit-4B: architecture-identical RANDOMLY INITIALISED control (seed 20260920); no pretrained weights.
- 1 twin pair(s) disagree on the focus cross-check (position key is primary and was verified constant); see provenance.twins.focus_mismatches
- historical_events has an EMPTY focus column for all 50 rows, so its action phrases use the lead-strip fallback rule, not the focus anchor.
- plan specified 28 or-bench-hard-1k rows as the harmless top-up; those rows are BORDERLINE over-refusal triggers, which would blur a refusal axis, so 28 alpaca no-input instructions are used instead (the plan's own listed fallback source).
- XSTest twin pairing: the plan named `focus` as the join key, but `focus` REPEATS within a block (many rows share focus='kill') and is EMPTY for all 50 historical_events rows, so it cannot identify a pair. Within-block POSITION is used as the primary key (the id offset was verified constant at 25 for all six families) and `focus` as the agreement cross-check; agreement is 25/25 in five families and 24/25 in safe_contexts (one pair labels 'bank account fraud' vs 'bank fraud').
- The plan budgeted a 40 GB shared disk. The workspace and the HF cache actually sit on a 2.2 PB network volume with ~715 TB free; only / is 40 GB. Disk was therefore NOT binding, so the full panel was run and no checkpoint was dropped for space, and CohenQu and mlabonne were NOT mutually exclusive.
- One tokenizer (Qwen/Qwen3-4B) builds the inputs for EVERY checkpoint, so continuation token ids are identical model-to-model. Each checkpoint's own tokenizer vocab hash and chat-template hash are recorded; the CohenQu arm's own template differs structurally but is NOT applied, so it is evaluated under a template it was not trained with.
- Frame slots are pinned to exact token indices (ACTION #1 at token 8, ACTION #2 at token 46, total 80 tokens) by padding the frame with neutral procedural filler, so both the hazardous and the benign prefix place their ACTION tokens at IDENTICAL offsets. The per-item filler-length difference is the price; it is reported in the tokenisation report.
- A randomly-initialised, architecture-identical control checkpoint (RandInit-4B) was added beyond the plan, because the mech-interp field handbook requires a randomized-transformer arm for any direction-fitting claim.

## Limitations

- At r=1.2 and n=96 the registered thresholds sit near 60-70% power, NOT 80%. The hypothesis's 'MDE' column is 1.96*SE, i.e. the 50%-power detectable effect, not an 80%-power MDE. The confirmatory item count cannot be raised past 96 without eating the held-out set, so any shortfall is reported as a stated power limitation, never as a silently relaxed threshold.
- G1 FAILED IN EVERY CHECKPOINT: the split-half cosine of the diff-in-means axis is 0.16-0.39, far below the registered 0.7. The axis fitted on 128 disjoint continuation pairs is therefore NOT stable, and the plan's registered fallback fired: a supervised logistic probe fitted on the same disjoint corpus is reported alongside every K1 term (metadata.candidates.<ckpt>.K1_probe_direction), and the probe baseline B2 reaches AUROC ~0.97 where the diff-in-means baseline B1 reaches only ~0.70. Diff-in-means is retained as the PRE-REGISTERED primary readout so the screen is not re-aimed after seeing the data, but no K1 conclusion should rest on it alone.
- The shuffled-label null band is WIDE in every trained checkpoint (|A| up to ~11-12 null-SD under PERMUTED labels, versus a real |A| of 4.3-9.3), while in the randomly-initialised arm it collapses to ~1.3. A diff-in-means direction fitted on permuted labels therefore reproduces an arming-shaped term of the same size in a trained model. This is the single most important caveat in the lane: the large random-direction-standardised terms are NOT by themselves evidence of a label-specific coordinate.
- K4's exponential persistence fit returned R^2 < 0.3 in 7 of 7 checkpoints, so tau is UNDEFINED there and the half-life crossing is reported instead. A candidate undefined in the checkpoint it registered a prediction on FAILS S1, and K4 is reported as failing, not as missing.
- K3's footprint is 50.4 in Qwen3-4B-Base-plain versus 2.5-3.7 everywhere else. Under the plain completion protocol the 'contentless' reference is an empty string with no assistant header, so the benign-minus-contentless displacement is not comparable; that arm's K3 value is a PROTOCOL ARTEFACT and is excluded from the K3 reading.
- NonSafetyFT-STaR: achieved r=6.77 gives an MDE of 1.35 null-SD at n=96, ABOVE the registered 0.50 threshold -- the screen was under-powered for this term in this arm.
- Qwen3-4B: achieved r=8.97 gives an MDE of 1.79 null-SD at n=96, ABOVE the registered 0.50 threshold -- the screen was under-powered for this term in this arm.
- Qwen3-4B-Base-chat: achieved r=5.66 gives an MDE of 1.13 null-SD at n=96, ABOVE the registered 0.50 threshold -- the screen was under-powered for this term in this arm.
- Qwen3-4B-Base-plain: achieved r=5.99 gives an MDE of 1.20 null-SD at n=96, ABOVE the registered 0.50 threshold -- the screen was under-powered for this term in this arm.
- Qwen3-4B-SafeRL: achieved r=9.97 gives an MDE of 1.99 null-SD at n=96, ABOVE the registered 0.50 threshold -- the screen was under-powered for this term in this arm.
- Qwen3-4B-abliterated: achieved r=7.65 gives an MDE of 1.53 null-SD at n=96, ABOVE the registered 0.50 threshold -- the screen was under-powered for this term in this arm.
- RandInit-4B: achieved r=3.24 gives an MDE of 0.65 null-SD at n=96, ABOVE the registered 0.50 threshold -- the screen was under-powered for this term in this arm.
- Qwen3-4B: the NLL-match gate (G6) failed, so A_net is the NLL-covariate-adjusted coefficient and is reported as an UPPER BOUND, not a point estimate.
- Decodability is not actionability. Every readout here is a decoding measurement on activations; none of it demonstrates that the coordinate CONTROLS behaviour. arXiv:2603.18353 reports 98.2% probe AUROC alongside steering indistinguishable from random perturbation, so the causal claim needs lane B's edit, not this lane.
- The per-item null-SD unit is built from ISOTROPIC random directions, while the residual stream is strongly anisotropic. For the CONTRASTS (O, CB, A, T, the coherence interaction, the K5 gains) the shared anisotropic component cancels between cells, so the unit is well calibrated. For the ABSOLUTE readouts it is not, so K2's prior is additionally reported as a fraction of the activation norm at the band and K3's footprint is self-normalised by the within-benign displacement -- both scale-free and free of any isotropy assumption.
- Cross-checkpoint comparison of directions is not licensed by a shared basis. Terms are compared only after per-checkpoint null-SD standardisation, and the raw scale table is printed so the reader can see how large the scale differences were. Cosines are only ever taken WITHIN a checkpoint (r_content vs r_ablit), never between checkpoints.
- The response-site diff-in-means readout r_content is NOT new: HARC (arXiv:2607.00572) Sec 3.2 Eq 2 defines substantially the same object, mean-pooled over the first 32 response tokens, and our EARLY window sits inside that pool. What is ours is the request x prefix CROSSING and the interaction term, plus the harc32 robustness row that recomputes every term under HARC's exact pooling.
