# Does the model act on harm, or only see it?

**One mechanistic question.** Is the axis that separates a base model, its safety-tuned child and its abliterated child a RECOGNITION axis -- the model still sees the harm -- or an EXECUTION axis -- the model stops acting on it? The candidate table is the INSTRUMENT for answering that; it is not a leaderboard of readouts.

- prereg SHA-256 `92d4ef7ff127ab7c87f9a35a69da04e9130adccd1bb52c8a9e88de4f0817399e`
- survivor: **NONE** — NO ELIGIBLE CANDIDATE passes E1 AND (E2 or E3). 4 of 4 eligible headline candidates are E1 UNDER-POWERED: no edit-recipe stratum reaches the registered minimum of 4 EFFECTIVE pairs, so E1(a) cannot be met by construction of the panel that could be harvested. Reported plainly, with the MDE per row so a reader can see what the design could have detected. No subgroup hunting.
- E4: **NOT_EVALUATED** — E4 is NOT_EVALUATED, so the word EXECUTION is WITHHELD from any survivor; it is called a READOUT.
- OpenRouter spend: **$0.0087**
- hardware: NO GPU in either session. SESSION 1 (03:36-04:47 UTC): 2 visible cores of an AMD Ryzen Threadripper 7960X at an external load average near 40 on 24 cores; it harvested Qwen3-4B, mlabonne/Qwen3-4B-abliterated and Qwen3-4B-Base (8-20 min per 4B checkpoint) and 12 weight summaries before the container ended. SESSION 2 (from 07:10 UTC): a NEW container on an AMD EPYC 9655 whose cpuset is the two hyperthreads of ONE physical core, host load ~200 on 192 threads, a 16 GB cgroup memory ceiling, and the run-shared HF cache found EMPTY (re-created 07:02) and the .venv gone, so every checkpoint was re-downloaded (~500 MB/s) and the environment rebuilt. Measured there: bf16 GEMM 245 GFLOPS, fp32 112 GFLOPS (AVX512-BF16), a 4B prompt harvest ~4-5 min. Every harvested number is scoped to what actually ran; session-1 caches were reused byte-for-byte (the harvest is resumable by DONE sentinels), not recomputed.

## The answer to the one mechanistic question

**EXECUTION (at the level of a READOUT): the children keep their parents' recognition -- the same onset depth and a median held-out TPR change inside the registered margin -- while the harm-conditioned refusal drive that the model's own unembedding reads from its activations falls in most effective pairs. What abliteration removes is acting on harm, not seeing it. Qualification: in 1 of 6 effective pairs (P2) the child's recognition is PARTIALLY lower -- the whole 90% TOST interval of parent-minus-child TPR lies above zero, though not beyond the equivalence margin -- so recognition is largely, not uniformly, preserved.**

- EFFECTIVE pairs: 6 (P0, P1, P2, P3, P4, P5).
- Recognition: median child−parent ΔR (TPR@5%FPR, HARD set) = -0.050 over 6 pairs; TOST verdicts {'INCONCLUSIVE': 6}; pairs whose 90% interval shows the child recognising less: ['P2']; median shift of the first decodable layer = 0.0 layers.
- Execution (PRIMARY, activations): the peak over depth of the harm-conditioned logit-lens refusal drive falls in 6/6 pairs (median Δ -2.98). Baseline BL1 (final layer only, logit-only): falls in 6/6 (median Δ -2.86); X2 write mass falls in 6/6 (median Δ -0.093); X3 falls in 5/6 (median Δ -0.320).
- Harm-direction agreement parent vs child: shallow quarter median |cos| 0.992, deep half 0.459.

> Descriptive: E1(a) is UNDER-POWERED by construction (no edit-recipe stratum holds 4 EFFECTIVE pairs), the TOST intervals on TPR@5%FPR with 80 benign HARD items are wide, and E4 (the causal write-handle test) was not evaluated, so 'execution' names a readout, not a demonstrated mechanism.

## Ground truth first: do X2 and X10 measure what they claim?

A KNOWN rank-one orthogonalisation at a known direction `u0` and a swept `alpha`, applied to real Qwen3-0.6B weights.

| alpha | X2 write mass along u0 | algebraic prediction (1−α)² | X10 max z | cos(vmin, u0) |
|---|---|---|---|---|
| 0.00 | 0.9999 | 1.0000 | 2.04 | 0.023 |
| 0.05 | 0.9025 | 0.9025 | 2.04 | 0.024 |
| 0.10 | 0.8101 | 0.8100 | 2.04 | 0.026 |
| 0.25 | 0.5627 | 0.5625 | 2.04 | 0.034 |
| 0.50 | 0.2502 | 0.2500 | 2.04 | 0.090 |
| 0.75 | 0.0626 | 0.0625 | 3.76 | 0.861 |
| 1.00 | -0.0000 | 0.0000 | 1.12 | 1.000 |

- **X2 is exact on real weights**: max |write mass − (1−α)²| = 0.000188.
- **Detection floor**: the scar only appears at α ≥ **0.75** (z jump) / **0.75** (the near-null direction becoming the deleted one). Below that, a partial abliteration strips write mass exactly as predicted yet leaves **no weights-only scar** — it would be missed.
- **The registered PRIMARY form of X10 fails this control under a UNIFORM edit.** X10's REGISTERED PRIMARY form is max_l z(scar_l), where z is taken against the MEDIAN AND MAD OF THE MODEL'S OWN LAYERS. That normalisation asks 'which layer is anomalous relative to this model's other layers', so it is BLIND BY CONSTRUCTION to an edit applied uniformly to every layer: when all layers are scarred the median moves with them and the z-score collapses (2.039772949424378 unedited -> 1.1230032769835137 at alpha=1.0 on ALL layers), even though cos(vmin, u0) = 0.9999999808413642, i.e. the near-null direction IS exactly the deleted one. The HALF-LAYER localisation control confirms the mechanism is intact when the edit is localised: mean scar 9.641291287409205 on edited layers versus 0.4250684013206217 on unedited ones, with cos(vmin, u0) 0.9999999829701015 versus 0.02777206086154495.
  - Community abliterations edit EVERY layer, so the registered primary is the wrong statistic for the very case this lane screens. The registered SECONDARY, X10_abs = max_l scar_l (no within-model normalisation), is the form that survives a uniform edit. We report BOTH, we do NOT retroactively promote the secondary to primary, and any X10 result is read with this control beside it. This is the kind of thing a ground-truth positive control exists to catch, and it would have been invisible without the alpha sweep.
- **T3 negative control**: on the unedited model X10 max z = 2.04 and cos(vmin,u0) = 0.023 — it does **not** fire.

## The premise: is RECOGNITION preserved?

| checkpoint | TPR@FPR | n benign | AUROC (SATURATED — not a test) | layer |
|---|---|---|---|---|
| CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 | 0.713 @ 0.05 | 80 | 0.951 | 23 |
| Damien420--granite-3.2-2b-instruct-abliterated | 0.875 @ 0.05 | 80 | 0.976 | 40 |
| Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3 | 0.512 @ 0.05 | 80 | 0.929 | 19 |
| HuggingFaceTB--SmolLM2-1.7B-Instruct | 0.825 @ 0.05 | 80 | 0.961 | 17 |
| HuggingFaceTB--SmolLM3-3B | 0.838 @ 0.05 | 80 | 0.967 | 19 |
| Qwen--Qwen2.5-1.5B-Instruct | 0.762 @ 0.05 | 80 | 0.947 | 19 |
| Qwen--Qwen3-0.6B | 0.425 @ 0.05 | 80 | 0.901 | 24 |
| Qwen--Qwen3-1.7B | 0.863 @ 0.05 | 80 | 0.961 | 18 |
| Qwen--Qwen3-4B | 0.875 @ 0.05 | 80 | 0.975 | 24 |
| Qwen--Qwen3-4B-Base | 0.475 @ 0.05 | 80 | 0.907 | 33 |
| Qwen--Qwen3-4B-SafeRL | 0.850 @ 0.05 | 80 | 0.971 | 24 |
| RandInit-Qwen3-0.6B | 0.075 @ 0.05 | 80 | 0.539 | 4 |
| TinyLlama--TinyLlama-1.1B-Chat-v1.0 | 0.537 @ 0.05 | 80 | 0.893 | 14 |
| allenai--OLMo-2-0425-1B | 0.738 @ 0.05 | 80 | 0.942 | 9 |
| allenai--OLMo-2-0425-1B-Instruct | 0.838 @ 0.05 | 80 | 0.969 | 9 |
| hereticness--heretic_stablelm-2-1_6b-chat | 0.762 @ 0.05 | 80 | 0.942 | 14 |
| huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2 | 0.588 @ 0.05 | 80 | 0.902 | 16 |
| huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2 | 0.650 @ 0.05 | 80 | 0.934 | 16 |
| ibm-granite--granite-3.2-2b-instruct | 0.825 @ 0.05 | 80 | 0.975 | 40 |
| lunahr--Phi-4-mini-instruct-abliterated | 0.875 @ 0.05 | 80 | 0.969 | 15 |
| microsoft--Phi-4-mini-instruct | 0.938 @ 0.05 | 80 | 0.981 | 21 |
| mlabonne--Qwen3-4B-abliterated | 0.838 @ 0.05 | 80 | 0.975 | 20 |
| mlx-community--SmolLM3-3B-abliterated-bf16 | 0.825 @ 0.05 | 80 | 0.971 | 18 |
| stabilityai--stablelm-2-1_6b-chat | 0.713 @ 0.05 | 80 | 0.917 | 24 |
| venkycs--SmolLM2-1.7B-Instruct-Abliterated | 0.138 @ 0.05 | 80 | 0.613 | 24 |

### Parent vs child equivalence (TOST on PAIRED bootstrap draws)

| pair | effectiveness | parent TPR | child TPR | verdict | TOST interval |
|---|---|---|---|---|---|
| P0 | EFFECTIVE | 0.875 | 0.838 | **INCONCLUSIVE** | [-0.116, 0.156] |
| P1 | EFFECTIVE | 0.425 | 0.588 | **INCONCLUSIVE** | [-0.306, 0.012] |
| P2 | EFFECTIVE | 0.863 | 0.650 | **INCONCLUSIVE** | [0.045, 0.393] |
| P3 | EFFECTIVE | 0.762 | 0.512 | **INCONCLUSIVE** | [0.000, 0.358] |
| P6 | NULL_EDIT | 0.825 | 0.875 | **INCONCLUSIVE** | [-0.114, 0.047] |
| P4 | EFFECTIVE | 0.838 | 0.825 | **INCONCLUSIVE** | [-0.039, 0.110] |
| P5 | EFFECTIVE | 0.938 | 0.875 | **INCONCLUSIVE** | [-0.100, 0.215] |
| S1 | ANOMALOUS | 0.713 | 0.762 | **INCONCLUSIVE** | [-0.370, 0.229] |
| S2 | ANOMALOUS | 0.825 | 0.138 | **DIFFERENT** | [0.461, 0.805] |

> R is the PREMISE and is reported FIRST. If R separates parent from child beyond the registered equivalence margin in most pairs, the hypothesis's premise is wrong and two published results are contradicted -- that is the finding, not a failure, and the recognition set is NOT re-tuned to restore the expected answer.

## The commissioned comparison: base, instruct, safety-RL, abliterated

| arm | harmful compl. | over-refusal | R TPR@5%FPR | recognition onset l_dec (frac) | HARD-set onset | execution onset l_act (frac) | peak refusal-drive gap (layer) | final-layer gap (BL1) | X3 | X2 | X10_abs | BL7 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| pretrained base | 0.022 | 0.156 | 0.475 | 6 (0.17) | 33 | 30 (0.83) | 1.57 (31) | -0.30 | 0.305 | 0.032 | 0.728 | 0.474 |
| NON-safety fine-tune of Base (control) | n/a | n/a | 0.713 | 6 (0.17) | 23 | 31 (0.86) | 2.57 (35) | 1.96 | 0.105 | 0.017 | 0.728 | 0.474 |
| official instruct | 0.000 | 0.444 | 0.875 | 5 (0.14) | 19 | 29 (0.81) | 4.92 (36) | 4.92 | 0.227 | 0.089 | 0.678 | 0.477 |
| official safety RL | 0.000 | 0.333 | 0.850 | 5 (0.14) | 19 | 31 (0.86) | 8.78 (32) | 3.60 | 0.572 | 0.129 | 0.678 | 0.477 |
| community abliterated child of Qwen3-4B | 0.733 | 0.000 | 0.838 | 5 (0.14) | 19 | 32 (0.89) | 1.92 (21) | -1.96 | 0.366 | -0.001 | 1.344 | 0.413 |

> RECOGNITION is read where harm first becomes decodable and on the HARD held-out set; EXECUTION is read as the logit-lens refusal drive that harm produces at each depth. If the abliterated child keeps the instruct model's recognition onset and R while its refusal drive collapses, the axis that separates them is EXECUTION, not RECOGNITION. The logit-lens drive is a readout of activations through the model's own unembedding; the final-layer value alone (BL1) is a logit-only BASELINE, never the deliverable.

## Recognition versus execution, as a depth profile

Per-layer |cos| between each parent's harm direction and its child's, both refit parent-free.

| pair | effectiveness | ΔHC | shallow-quarter |cos| | deep-half |cos| | divergence layer | depth frac |
|---|---|---|---|---|---|---|
| P0 qwen3 | EFFECTIVE | 0.733 | 0.999 | 0.336 | 19 | 0.528 |
| P1 qwen3 | EFFECTIVE | 0.467 | 0.985 | 0.620 | 17 | 0.607 |
| P2 qwen3 | EFFECTIVE | 0.667 | 0.990 | 0.454 | 13 | 0.464 |
| P3 qwen2.5 | EFFECTIVE | 0.467 | 0.590 | 0.240 | 7 | 0.250 |
| P6 granite | NULL_EDIT | 0.000 | 0.984 | 0.997 | None | n/a |
| P4 smollm3 | EFFECTIVE | 0.289 | 0.999 | 0.600 | 19 | 0.528 |
| P5 phi | EFFECTIVE | 0.244 | 0.994 | 0.464 | 12 | 0.375 |
| S1 stablelm | ANOMALOUS | -0.111 | 1.000 | 0.880 | None | n/a |
| S2 smollm2 | ANOMALOUS | -0.200 | 0.014 | 0.021 | 6 | 0.250 |

Across EFFECTIVE pairs: shallow-quarter median |cos| = **0.992**, deep-half median |cos| = **0.459**.

> Per-layer |cos| between an instruct parent's harm direction and its abliterated child's, both refit parent-free on that checkpoint's own activations. High SHALLOW agreement with low DEEP agreement is the recognition-versus-execution dissociation in its most direct form: the child still encodes harm the same way where harm is first decodable, and differently where the model would act on it. Reported for NULL_EDIT and ANOMALOUS pairs too, so a reader can see whether the profile is specific to pairs that actually changed behaviour.

## How the checkpoints differ IN ACTIVATION SPACE

Per-layer |cos| between each checkpoint's OWN parent-free harm direction.

| a | b | median |cos| | deep-half median | min | max |
|---|---|---|---|---|---|
| CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 | Qwen--Qwen3-4B | 0.484 | 0.605 | 0.000 | 0.880 |
| CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 | Qwen--Qwen3-4B-Base | 0.680 | 0.638 | 0.000 | 0.999 |
| CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 | Qwen--Qwen3-4B-SafeRL | 0.439 | 0.506 | 0.000 | 0.878 |
| CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 | mlabonne--Qwen3-4B-abliterated | 0.320 | 0.350 | 0.000 | 0.880 |
| Damien420--granite-3.2-2b-instruct-abliterated | ibm-granite--granite-3.2-2b-instruct | 0.995 | 0.997 | 0.000 | 1.000 |
| Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3 | Qwen--Qwen2.5-1.5B-Instruct | 0.385 | 0.240 | 0.000 | 0.636 |
| HuggingFaceTB--SmolLM2-1.7B-Instruct | venkycs--SmolLM2-1.7B-Instruct-Abliterated | 0.014 | 0.021 | 0.000 | 0.052 |
| HuggingFaceTB--SmolLM3-3B | mlx-community--SmolLM3-3B-abliterated-bf16 | 0.751 | 0.600 | 0.000 | 1.000 |
| Qwen--Qwen3-0.6B | RandInit-Qwen3-0.6B | 0.014 | 0.011 | 0.000 | 0.047 |
| Qwen--Qwen3-0.6B | huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2 | 0.885 | 0.620 | 0.000 | 0.998 |
| Qwen--Qwen3-1.7B | huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2 | 0.511 | 0.454 | 0.000 | 0.997 |
| Qwen--Qwen3-4B | Qwen--Qwen3-4B-Base | 0.348 | 0.379 | 0.000 | 0.884 |
| Qwen--Qwen3-4B | Qwen--Qwen3-4B-SafeRL | 0.908 | 0.886 | 0.000 | 1.000 |
| Qwen--Qwen3-4B | mlabonne--Qwen3-4B-abliterated | 0.612 | 0.336 | 0.000 | 1.000 |
| Qwen--Qwen3-4B-Base | Qwen--Qwen3-4B-SafeRL | 0.316 | 0.354 | 0.000 | 0.882 |
| Qwen--Qwen3-4B-Base | mlabonne--Qwen3-4B-abliterated | 0.227 | 0.227 | 0.000 | 0.884 |
| Qwen--Qwen3-4B-SafeRL | mlabonne--Qwen3-4B-abliterated | 0.451 | 0.260 | 0.000 | 1.000 |
| RandInit-Qwen3-0.6B | huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2 | 0.023 | 0.031 | 0.000 | 0.061 |
| allenai--OLMo-2-0425-1B | allenai--OLMo-2-0425-1B-Instruct | 0.012 | 0.008 | 0.000 | 0.021 |
| hereticness--heretic_stablelm-2-1_6b-chat | stabilityai--stablelm-2-1_6b-chat | 0.916 | 0.880 | 0.000 | 1.000 |
| lunahr--Phi-4-mini-instruct-abliterated | microsoft--Phi-4-mini-instruct | 0.517 | 0.464 | 0.000 | 1.000 |

> A HIGH per-layer |cos| between an instruct parent and its abliterated child says the two still represent harm along the SAME axis -- the uncensoring did not move the direction, so whatever it changed is downstream of the representation. A LOW one says the direction itself moved. The same comparison across Qwen3-4B-Base, Qwen3-4B, Qwen3-4B-SafeRL and the abliterated child IS the commissioned activation-level comparison, reduced to one number per layer per pair. Raw per-layer curves ship in released/per_layer_candidate_curves.csv.

## The edit recipes are NOT one operator

| pair | stratum | implied alpha (median) | rank-1 share | cos(shallow, deep) | embed edited |
|---|---|---|---|---|---|
| P0 | **B_PER_LAYER_RANK1** | 0.9727 | 0.9945 | 0.0164 | False |
| P1 | **A_GLOBAL_RANK1** | 1.0024 | 0.9975 | 1.0000 | False |
| P2 | **A_GLOBAL_RANK1** | 1.0046 | 0.9952 | 1.0000 | False |
| P3 | **C_OTHER_OPERATOR** | 3.5270 | 0.0779 | 0.9913 | True |
| P4 | **A_GLOBAL_RANK1** | 1.0024 | 0.9956 | 1.0000 | False |
| P5 | **B_PER_LAYER_RANK1** | 0.8314 | 0.9928 | 0.0090 | False |
| P6 | **C_OTHER_OPERATOR** | 14.9732 | 1.0000 | n/a | False |
| S1 | **C_OTHER_OPERATOR** | 1.2188 | 1.0000 | 0.0522 | False |
| S2 | **C_OTHER_OPERATOR** | 1.5069 | 0.4380 | 0.0415 | True |

> A GLOBAL_RANK1 edit removes ONE direction shared across all layers; a PER_LAYER_RANK1 edit removes a different direction at every layer. Pooling the two would average two different operators, which is why E1(a) is never pooled across strata.

## The screen (S-table)

E1 status is PASS / FAIL / UNDER_POWERED (no stratum reaches 4 EFFECTIVE pairs). The pooled row is the labelled SECONDARY reading and never decides E1. MDE is in pooled shuffled-label SD units, beside the 0.50-SD E2 rule.

| candidate | E1 status | largest stratum (n) | pooled secondary: same sign / CI≠0 of n | E1(b) spec | E2 | E2 margin (SD) | E3 margin vs BL1 | E4 | escapes band | MDE (SD) | prior art | survivor-eligible |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **X1** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | True / 3 of 6 | True | False | 0.08 | -0.333 | NOT_EVALUATED | 0/9 | 0.12 | PARTIALLY_SCOOPED | yes |
| **X2** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | True / 0 of 6 | True | False | 0.83 | -0.079 | NOT_EVALUATED | 0/9 | 2.98 | CLOSED | NO (CLOSED) |
| **X3** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 2 of 6 | True | False | -0.22 | -0.327 | NOT_EVALUATED | 0/9 | 1.49 | PARTIALLY_SCOOPED | yes |
| **X5** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 2 of 6 | True | False | 2.82 | -0.202 | NOT_EVALUATED | 0/7 | 3.39 | PARTIALLY_SCOOPED | yes |
| **X8** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 1 of 6 | True | False | -0.08 | -0.439 | NOT_EVALUATED | 0/9 | 0.63 | PARTIALLY_SCOOPED | yes |
| **X10** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 0 of 6 | False | False | n/a | 0.028 | NOT_EVALUATED | N/A -- label-free candidate, see null_used | n/a | CLOSED | NO (CLOSED) |
| **X10_abs** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 6 of 6 | True | False | n/a | -0.097 | NOT_EVALUATED | N/A -- label-free candidate, see null_used | n/a | None | carried / secondary |
| **X10_median** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | True / 4 of 6 | False | False | n/a | -0.019 | NOT_EVALUATED | N/A -- label-free candidate, see null_used | n/a | None | carried / secondary |
| **X11** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 1 of 6 | True | False | 0.07 | -0.183 | NOT_EVALUATED | 0/7 | 1.23 | PARTIALLY_SCOOPED | carried / secondary |
| **BL1_REFLOGIT** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | True / 5 of 6 | True | False | 3.77 | 0.000 | NOT_EVALUATED | 3/9 | 2.68 | None | baseline |
| **BL2_RAWHID** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 0 of 6 | False | False | n/a | -0.345 | NOT_EVALUATED | 0/9 | n/a | None | baseline |
| **BL3_DIFFMEAN** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | True / 3 of 6 | True | False | 23.12 | 0.049 | NOT_EVALUATED | 4/9 | 11.58 | None | baseline |
| **BL6_HRCI** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 0 of 6 | False | False | n/a | -0.093 | NOT_EVALUATED | 0/9 | n/a | None | baseline |
| **BL7_JORAK_A** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 4 of 6 | True | False | n/a | -0.052 | NOT_EVALUATED | N/A -- label-free candidate, see null_used | n/a | None | baseline |
| **BL5_CARDREGEX** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 0 of 6 | False | False | n/a | -0.366 | NOT_EVALUATED | N/A -- label-free candidate, see null_used | n/a | None | baseline |
| **BL5_CARDREGEX_NAMEFREE** | UNDER_POWERED | A_GLOBAL_RANK1 (3) | False / 0 of 6 | False | False | n/a | -0.448 | NOT_EVALUATED | N/A -- label-free candidate, see null_used | n/a | None | baseline |

## Zero-to-few prompts: the pair difference at every prompt budget k

Delta(k) = child minus parent with u refit on k fitting prompts (k/2 per class; draw r uses the SAME prompts in both checkpoints), in pooled shuffled-label SD, with the share of draws agreeing in sign. k=0 rows are weights-only. Reported at EVERY k, never as a scan maximum; k=128 exceeds the 96-prompt fitting set, so every draw uses all 96.

| pair | label | k=0: ΔX10_abs / ΔBL7 | k=4: X2 / X3 / X8 / BL1_REFLOGIT | k=16: X2 / X3 / X8 / BL1_REFLOGIT | k=128: X2 / X3 / X8 / BL1_REFLOGIT |
|---|---|---|---|---|---|
| P0 | EFFECTIVE | 0.67 / -0.06 | -0.6(0.8) / -0.0(0.5) / 0.1(0.4) / -5.3(1.0) | -0.2(0.6) / 0.1(0.7) / 0.1(0.5) / -5.8(1.0) | -1.2(1.0) / 0.4(1.0) / 0.2(1.0) / -6.1(1.0) |
| P1 | EFFECTIVE | 1.48 / 0.51 | 0.1(0.7) / -1.0(0.9) / -0.1(0.5) / -1.3(0.8) | -0.2(0.4) / -1.0(1.0) / 0.1(0.6) / -0.4(0.5) | -0.4(1.0) / -0.0(1.0) / 0.1(1.0) / -0.6(1.0) |
| P2 | EFFECTIVE | 1.31 / 0.47 | -0.7(0.8) / -0.5(0.5) / 0.1(0.3) / -3.7(0.8) | -0.8(0.6) / -0.4(0.4) / 0.1(0.3) / -4.4(1.0) | -2.6(1.0) / -1.3(1.0) / -0.1(1.0) / -4.4(1.0) |
| P3 | EFFECTIVE | 0.13 / 0.49 | -0.8(0.8) / -1.0(0.6) / -0.1(0.3) / -9.0(0.9) | -1.1(0.9) / -0.9(0.8) / -0.4(0.6) / -6.5(1.0) | -1.4(1.0) / -1.2(1.0) / -0.4(0.6) / -7.1(1.0) |
| P6 | NULL_EDIT | 0.00 / -0.00 | -0.1(0.6) / -0.2(0.7) / -0.3(0.8) / -1.0(1.0) | 0.2(0.6) / -0.1(0.5) / 0.0(0.3) / -1.0(1.0) | 3.0(1.0) / 0.5(1.0) / -0.0(0.2) / -0.8(1.0) |
| P4 | EFFECTIVE | 1.40 / 0.36 | 0.2(0.7) / -0.6(0.6) / 0.3(0.4) / -2.0(0.9) | -1.3(0.6) / -1.2(1.0) / 0.1(0.3) / -2.7(1.0) | -1.4(1.0) / -1.5(1.0) / 0.5(1.0) / -3.1(1.0) |
| P5 | EFFECTIVE | -0.00 / -0.00 | -0.9(0.5) / -0.6(0.8) / -0.7(1.0) / -12.3(1.0) | -2.0(0.9) / -0.5(0.7) / -0.7(1.0) / -12.4(1.0) | -5.0(1.0) / -0.7(1.0) / -0.7(1.0) / -12.5(1.0) |
| S1 | ANOMALOUS | -0.00 / -0.02 | -0.3(0.7) / -0.1(0.5) / 0.3(0.3) / -3.2(1.0) | -0.1(0.8) / -0.1(0.7) / 0.3(0.4) / -0.9(0.7) | -0.2(1.0) / -0.7(1.0) / 0.0(1.0) / -1.6(1.0) |
| S2 | ANOMALOUS | 0.81 / 0.57 | -2.0(1.0) / -0.6(0.7) / -1.3(0.9) / 2.1(0.6) | -2.1(0.9) / -1.1(0.6) / -1.2(1.0) / 0.6(0.6) | 0.1(1.0) / -2.9(1.0) / -1.8(1.0) / -1.4(1.0) |

### Response-site readouts (X5, X11): where they are defined

- **X5** — COMPUTED on 18 checkpoint(s) from the session-2 C-harvest pass (per-tokenizer slot rule applied); see 'undefined' and 'not_harvested' for the rest. Undefined: none; not harvested: ['HuggingFaceTB--SmolLM2-1.7B-Instruct', 'TinyLlama--TinyLlama-1.1B-Chat-v1.0', 'allenai--OLMo-2-0425-1B', 'allenai--OLMo-2-0425-1B-Instruct', 'hereticness--heretic_stablelm-2-1_6b-chat', 'stabilityai--stablelm-2-1_6b-chat', 'venkycs--SmolLM2-1.7B-Instruct-Abliterated'].
- **X11** — COMPUTED on 18 checkpoint(s) from the session-2 C-harvest pass (per-tokenizer slot rule applied); see 'undefined' and 'not_harvested' for the rest. Undefined: none; not harvested: ['HuggingFaceTB--SmolLM2-1.7B-Instruct', 'TinyLlama--TinyLlama-1.1B-Chat-v1.0', 'allenai--OLMo-2-0425-1B', 'allenai--OLMo-2-0425-1B-Instruct', 'hereticness--heretic_stablelm-2-1_6b-chat', 'stabilityai--stablelm-2-1_6b-chat', 'venkycs--SmolLM2-1.7B-Instruct-Abliterated'].

## Declared empty or missing blocks

- Iteration 1's self-audit missed an entirely empty causal results block and a paper then asserted a claim with zero evidence. This list exists so that cannot recur: every empty block above is declared here AND in SUMMARY.md.

## Leakage audits (6/6 pass)

- PASS `T5a_reserved_54_not_in_fitting_path` — reserved_54 may be referenced only by confirm.py (and the output builder's prose); it is referenced by ['confirm.py']
- PASS `T5a_heldout_cells_not_in_fitting_path` — heldout_cells may be referenced only by confirm.py (and the output builder's prose); it is referenced by ['confirm.py']
- PASS `T5b_lstar_and_band_from_EASY_only` — score_checkpoint restricts every candidate fit to sid==0 (the EASY set); the HARD set is used only inside recognition_axis().
- PASS `T5c_probe_C_chosen_on_inner_fold` — cv_auroc_per_layer and cv_probe_scores select C on an inner split of the TRAINING fold; logistic_probe_direction selects C on inner folds of the data it is given (group-aware when a bootstrap duplicated items), and is only ever given the EASY set.
- PASS `T5d_E3_impute_and_z_on_train_fold_only` — _impute_and_z takes (Xtr, Xte) and computes the median and the z-scaling from Xtr alone; machinery_controls() reports the shuffled-truth control that would expose any leak.
- PASS `T5e_sealed_families_used_only_as_anomalous_controls` — the two leaked-seal pairs carry effectiveness=ANOMALOUS, and e1_test() consumes ANOMALOUS pairs only through anomalous_controls, never through e1a_sensitivity (which filters on EFFECTIVE) or e1b_specificity (NULL_EDIT).

## Arithmetic unit tests (7/7 pass)

- PASS `T1a_X2_normalisation`
- PASS `T1b_gram_identities`
- PASS `T1c_X3_closed_form`
- PASS `T1d_rmsnorm_jacobian`
- PASS `T1f_auroc_tpr`
- PASS `T1g_x2_rank1_deletion`
- PASS `T1e_marchenko_pastur`

## Inherited-claims audit

- **D6_i_raw_hidden_states_saved_nowhere** — PARTLY FALSE. Lane B kept a 104-file .npz harvest (~7.6 GB) under out/harvest/, but its arrays are WINDOW-POOLED vectors keyed item|win|{EARLY,LATE}|{layer} over the 2x2 cell substrate under lesion alphas, for a subset of layers only -- not per-item per-layer PROMPT hidden states for the pairs. They are therefore NOT reusable as this lane's P-harvest, and were not reused. Lane C saved none (a glob for .npy/.npz/.pt returns zero).
- **D6_ii_abliterated_in_no_metric_table** — FALSE, AND VERIFIED FALSE. Lane A's out/released/directions/ holds 14 .npy files = 2 per checkpoint over 7 checkpoints including Qwen3-4B-abliterated and a RandInit-4B arm, and Lane A's method_out.json carries a 'checkpoint_panel_readouts' dataset with one row per checkpoint. THE TRUE STATEMENT, which this lane acts on: the abliterated checkpoint has RECOGNITION-side readouts in Lane A, but (1) no EXECUTION-side readout was computed on it or on any other pair, (2) the pairs were never analysed AS pairs, and (3) it appears in no CROSS-FAMILY panel. Those three are the genuine gaps and they are what this lane fills.
- **D6_iii_two_families_sealed** — THE SEAL IS LEAKED. Lane C's prereg.json lists sealed_families = [stablelm, smollm2] and lc_output.py does restrict the EXPORT to scored families -- but results/s3/s3_results.json computes behavioural_columns straight from results/judged/*.jsonl with no sealed filter, so both families' real truth values sit in it (stablelm-2-1_6b-chat 0.467 -> heretic 0.356; SmolLM2-1.7B-Instruct 0.200 -> venkycs 0.000 at over_refusal 1.000). Both also REVERSE the expected direction. They are therefore used ONLY as ANOMALOUS specificity controls, never as confirmation.
- **D6_iv_five_size_anomalies** — IT IS TWO. (i) philippefunk/TinyLlama-1.1B-Chat-v1.0-abliterated: 0.81 GB vs 2.20 GB and 630,759,982 vs 1,100,048,384 params -- a BROKEN upload with missing shards, dropped, not repairable. (ii) venkycs/SmolLM2-1.7B-Instruct-Abliterated: 1.82 GB vs 3.42 GB with a params ratio of ~1.0004 and float16 vs bfloat16 -- it loads and produces judged rows, and its judged profile (harmful compliance 0.000, over-refusal 1.000) says BROKEN-BEHAVING, not uncensored, so it is labelled ANOMALOUS. CAUSE, VERIFIED IN SESSION 2: it is an optimum-quanto FP8 upload (<key>._data float8_e4m3fn + per-channel <key>._scale) with no quantization_config, so a standard transformers load reports 168 MISSING tensors -- every linear layer of all 24 blocks is left at RANDOM init. What Lane C judged is a random network with trained embeddings; its recognition R collapses (0.825 -> 0.138) exactly as a broken model's should. allenai/OLMo-2-0425-1B at 0.501x is purely float32 vs bfloat16 and is a base-vs-instruct pair, not an abliteration pair.
- **D6_v_tinyllama_repairable** — IT CANNOT. The weights are not there. It is DROPPED as EXCLUDED: BROKEN UPLOAD. Worth one sentence in any write-up: a hub checkpoint labelled 'abliterated' is simply broken, which is a fact about the supply of these uploads.
- **conflict_1_which_families_are_sealed** — RESOLVED IN FAVOUR OF LANE C, ON EVIDENCE. The registry names the Josiefied -v1 revision; the panel and Lane C use -v3, and Lane C did score it -- results/per_ckpt/Goekdeniz-Guelmez__Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3.json EXISTS, and qwen2.5 is in Lane C's scored_families. The registry's seal therefore applies to a DIFFERENT revision. P3 IS USABLE and is kept as an EFFECTIVE pair (0.000 -> 0.467).
- **conflict_2_routing_concentration_0p24_vs_0p03** — RESOLVED AGAINST THIS LANE'S OWN PLANNING-TIME SCEPTICISM. A full-text search of this run's research_out.json for 'routing concentration', 'concentration' and '0.24' returns ZERO matches, which is why the figure was initially treated as unverifiable. A direct check of arXiv:2607.14147 ('Breaking Refusal in the First Half', Kwon) then found the verbatim string 'concentration 0.24 vs 0.03, App. E' in Appendix E. THE NUMBER IS REAL; the planning-time note that it could not be verified was wrong and is withdrawn. What is NOT real is the label: the paper's term is logit-trace / generative concentration, and 'routing concentration' never occurs in it. Consequence: X5 is a re-operationalisation of a PUBLISHED concentration measure, not a new one, and its prior-art verdict is upgraded to PARTIALLY_SCOOPED. X5 was not computed in this run, so this is recorded for the next iteration.
- **D6_extra_embed_tokens_claim** — FALSE for this checkpoint pair, VERIFIED DIRECTLY. see embed_tokens_check.json for the measured norms

## Cross-iteration reproducibility of the harm direction

panel median |cos| vs iteration 1 Lane A's released directions: **0.645**

| checkpoint | median |cos| | deep-half median | max |
|---|---|---|---|
| Qwen--Qwen3-4B | 0.687 | 0.935 | 0.945 |
| mlabonne--Qwen3-4B-abliterated | 0.764 | 0.819 | 0.837 |
| Qwen--Qwen3-4B-SafeRL | 0.632 | 0.892 | 0.910 |
| Qwen--Qwen3-4B-Base | 0.645 | 0.789 | 0.835 |
| CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 | 0.584 | 0.760 | 0.837 |

> This lane's direction is refit from a DIFFERENT prompt set and substrate than iteration 1 Lane A's. A high per-layer |cos| means the parent-free harm axis is a property of the CHECKPOINT rather than of the prompt set that fitted it; a low one means it is prompt-set dependent, which would undercut every candidate built on it. Reported either way, with no threshold chosen after the fact.

## Citation hygiene: what was checked, corrected and withdrawn

Every arXiv id this lane cites was checked two ways: against this run's own research_out.json (32 sources that were actually fetched) and by an independent live lookup on arxiv.org. Four ids used here -- 2511.06390, 2604.15557, 2609.13534 and 2406.11717 -- are absent from research_out.json and were verified only by this lane's live lookup; that is stated rather than hidden. One attribution (2406.11717) was found to be backwards and was withdrawn, and one of this lane's own sceptical notes (the 0.24-vs-0.03 figure) was found to be wrong and was withdrawn. No id used anywhere in this output failed to resolve.

- **`2605.16600`** — named as: owning X2's algebra, via a Relative Subspace Fraction identity. **NOT CITED -- absent from this run's evidence base** full-text search of this run's research_out.json returns ZERO hits for this id; it was not independently fetched by this lane either. It is therefore neither asserted nor denied: it is simply not used as support for anything.
- **`2609.01936`** — named as: 'Sparse Readout Prism', likely CLOSING X3. **VERIFIED by the same-iteration research lane [15]; does NOT close X3** Fetched by iter_2/gen_art/gen_art_research_1: it explains logit-lens scores in features instead of tokens, and its safety application appears as future work, not as a result. X3 stays PARTIALLY_SCOOPED and eligible.
- **`2606.24952`** — named as: publishing a weight-computable knowing-versus-steering cosine. **VERIFIED by the same-iteration research lane [3]** 'Perfect Detection, Failed Control: The Geometry of Knowing vs. Steering in Language Models'. Right STRUCTURE (a per-checkpoint weight-computable cosine over 4 models) but on HALLUCINATION, not harm, and it concludes the cosine is not a predictor of steerability. It evaluates no abliterated checkpoint.
- **`2406.11717`** — named as: already projecting the refusal direction through the unembedding (X3 prior art). **RESOLVES, BUT THE ATTRIBUTION WAS WRONG AND IS WITHDRAWN** The id is real -- 'Refusal in Language Models Is Mediated by a Single Direction' (Arditi, Obeso, Syed, Paleka, Panickssery, Gurnee, Nanda). But the paper does NOT use an unembedding projection as its method: it ablates a difference-in-means direction and explicitly EXCLUDES late-layer directions close to the unembedding (an l < 0.8L filter) to avoid a trivial token-level effect. Citing it for X3's mechanism reversed what the paper actually does, so the citation is withdrawn.
- **`0.24 vs 0.03 (routing concentration)`** — named as: the figure motivating X5. **VERIFIED REAL -- this lane's own earlier scepticism was WRONG and is withdrawn** A direct check of arXiv:2607.14147 ('Breaking Refusal in the First Half', Kwon) finds the verbatim string 'concentration 0.24 vs 0.03, App. E', confirmed in Appendix E. The NUMBER is real. What is not real is the LABEL: the paper's own term is logit-trace / generative concentration of a refusal attractor, and the phrase 'routing concentration' never occurs in it. We therefore report the quantity as published and drop the invented label.

## Deviations (22)

- `prereg_rewritten` prereg.json was written three times before the first forward pass was SCORED: v1 (912619b5) registered float32 forward passes and 352 stimuli; v2 switched the forward dtype to bfloat16 after a measured 1.8x speedup on this AVX512-BF16 CPU; v3 (92d4ef7f) cut the stimulus set from 352 to 256 (EASY 96 + HARD 160) after measuring per-checkpoint harvest cost on a GPU-less, externa
- `harvest_order_revised` sweep ORDER v1 -> v2 after the weight fingerprints landed: The edit-recipe fingerprint is a weights-only DIAGNOSTIC, excluded from every metric, but it assigns strata and E1(a) requires >=4 EFFECTIVE pairs WITHIN ONE stratum. Measured: P1/P2/P4 = A_GLOBAL_RANK1; P0 = B (alone); P3 = C (implied alpha 3.53, rank-1 share 0.078 -- not a rank-one abliteration); 
- `c_harvest_dropped` the teacher-forced C-harvest was dropped for every checkpoint: Measured at ~1.8x the cost of the entire prompt harvest per checkpoint on a box with no GPU, 2 visible cores and an external load average near 40 on 24 cores. X5 and X11 are therefore NOT COMPUTED and are reported as such rather than computed on a degraded substrate without saying so. This is the re
- `gram_precision` the per-layer Gram is accumulated in float32 and eigendecomposed in float64: Full float64 was measured at ~72 s/layer on this 2-core box, which would have cost more than the entire time budget for the panel. For these matrices the exact-arithmetic condition number is tiny -- a Gaussian [d,n] with n >> d spans only (sqrt(n)-sqrt(d))^2 to (sqrt(n)+sqrt(d))^2, a ratio near 6 at
- `logit_lens_denominator` the per-layer full-vocabulary logsumexp was not computed at every layer: Every downstream use of the logit-lens drive is a DIFFERENCE between two token sets at the same layer and item (X8 and BL1 both), so the full-vocabulary denominator CANCELS EXACTLY and never enters any reported number. Computing it at all 37 layers would have cost a [chunk, 151936] logit tensor per 
- `dtype_cast_split` forward passes run in bfloat16; the WEIGHT side is read in native precision: The plan required the F32 mlabonne/Qwen3-4B-abliterated checkpoint to be cast to bf16, a stated deviation. Here the cast applies ONLY to the forward passes: the W-summary reads every tensor straight from the safetensors shards and upcasts to float32, so the spectrum that X10 and X2 are computed from
- `citation_corrections` two citation errors found and withdrawn by a live arXiv check: (1) The artifact direction cited arXiv:2406.11717 (Arditi et al.) as already projecting the refusal direction through the unembedding, as X3 prior art. The paper does NOT do that -- it ablates a difference-in-means direction and explicitly excludes late-layer directions close to the unembedding. The
- `cgroup_memory_ceiling` the real memory ceiling is a ~15 GB cgroup limit, not the 251 GB free(1) reports: /sys/fs/cgroup/memory/memory.limit_in_bytes = 16000000000 (cgroup v1). free(1) shows the HOST 251 GB and is misleading. A 4B model in bfloat16 is ~8 GB resident, so two concurrent 4B loads exceed the ceiling. This actually happened: the edit-recipe fingerprint process was OOM-KILLED (SIGKILL, so its
- `session_restart` session 1 ended at ~04:47 UTC; session 2 resumed the workspace at 07:10 UTC in a NEW container: Session 1 had harvested Qwen3-4B, mlabonne/Qwen3-4B-abliterated and Qwen3-4B-Base, 12 weight summaries and 6 edit-recipe fingerprints; its Qwen3-4B-SafeRL harvest was at 192/256 prompts when the container ended and was redone from scratch. All session-1 caches were reused byte-for-byte (resumable by
- `ci_method_corrected` pair-delta and E2 confidence intervals re-derived from an ITEM-LEVEL BOOTSTRAP: The session-1 code built the per-pair Delta CI as a normal interval with SE = sqrt(sd_p^2/n_null + sd_c^2/n_null) and the E2 CI with SE = pooled*sqrt(2/n_null): both divide the shuffled-label SD by the NUMBER OF NULL DRAWS, so the interval would shrink to zero as more null draws were taken. That is 
- `bootstrap_B` item bootstrap uses B=100 replicates, not the 2000 the plan names: Each replicate refits the harm axis and recomputes every candidate, ~0.5-3 s on one contended core; 2000 x ~25 checkpoints was not affordable. Percentile CIs from 100 draws are coarse at the 2.5/97.5 tails; every CI in the output is labelled with its B.
- `w_summary_extremes_only` session-2 weight summaries compute only the extreme eigenpairs: Only sigma_min (= sqrt(lambda_min(MM^T))) and the near-null left singular vector are read by any statistic (X10, BL7, cos(vmin,u)). Session-2 W-summaries therefore use LAPACK dsyevr with a one-index subset for (lambda_min, vmin) and 60 power iterations for lambda_max, measured 5.8x faster at d=2560 
- `prior_art_update` X2 and X10 re-labelled CLOSED and excluded from survivor selection; X8 OPEN -> PARTIALLY_SCOOPED: The same-iteration execution-side research lane (iter_2/gen_art/gen_art_research_1, 2026-09-21) screened exactly these candidates and found 0 OPEN: the Jorak Model Scanner (github.com/JolanMc/Jorak; non-peer-reviewed, validated 4/4 on Qwen2.5-0.5B derivatives) ships X2's suppression statistic and X1
- `stratum_shortfall` no edit-recipe stratum can reach the 4 EFFECTIVE pairs E1(a) requires: The Phi-4-mini pair P5 fingerprints as B_PER_LAYER_RANK1 (like the commissioned P0), not A_GLOBAL_RANK1, so stratum A holds three EFFECTIVE pairs (P1, P2, P4), B holds P5 (+P0 if its judged label is EFFECTIVE) and C holds P3 plus the null-edit granite P6. E1(a) is therefore UNDER-POWERED by construc
- `quanto_checkpoint` venkycs/SmolLM2-1.7B-Instruct-Abliterated is an optimum-quanto FP8 upload with no quantization_config: Its linear weights are stored as <key>._data (float8_e4m3fn) + a per-output-channel <key>._scale, and config.json declares float16 with quantization_config=None, so a plain transformers load cannot bind them. The weight-side summaries dequantise exactly (W = _data * _scale); the harvest records the 
- `sweep_paused_for_judge` the harvest sweep was paused between checkpoints while the judge extension ran: Generating 90 responses with mlabonne/Qwen3-4B-abliterated needs ~9 GB resident; beside a 3-4B harvest model that exceeds the 16 GB cgroup. The sweep was stopped right after Qwen3-1.7B finished and resumed after the judge job, so no checkpoint was lost or redone.
- `registered_drop` the 4B random-init arm was dropped; the 0.6B random-init arm is kept: Registered drop order (Section 12): '... -> the 4B random-init arm (keep the 0.6B one)'. Its forward passes cost as much as a real 4B checkpoint on one CPU core, and the 0.6B random-init arm already provides the untrained-representation control for every activation candidate plus (via an independent
- `c_harvest_restored` the teacher-forced C-harvest (X5, X11) was RESTORED in session 2, with the registered per-tokenizer slot rule: Session 1 dropped it on a slower box; its harvest.c_harvest also tested slot-in-window with the STORED Qwen token spans for every model and never dropped a failing cell, contrary to the registered rule. Session 2's src/c_harvest2.py re-tokenises each cell per model, maps the action slots from charac
- `judge_extension_run` the commissioned child mlabonne/Qwen3-4B-abliterated was judged with Lane C's exact protocol: Same 45 harmful + 45 benign prompt ids/texts as Lane C's Qwen/Qwen3-4B row, same generation settings (greedy, max_new 140, batch 16, enable_thinking=False), same rubric and judges (google/gemini-2.5-flash-lite primary, openai/gpt-5-mini second on a 20% audit), same aggregation. Differences: CPU inst
- `recognition_layer_selection_corrected` R now uses the REGISTERED nested layer selection on the HARD set, not the session-1 EASY-set shortcut: The plan (Section 5) chooses R's layer by inner-fold AUROC on the HARD set. Session-1 code chose it on the EASY fitting set instead, whose cross-fitted AUROC saturates at 1.0 over many layers, so the argmax took the FIRST saturated layer -- for huihui-ai/Huihui-Qwen3-0.6B-abliterated-v2 that was lay
- `time_gate_tail_dropped` prompt sweep stopped after the E3 family singles; C-harvest restricted to the checkpoints the registered tests need: At 08:20 the measured pace (granite-3.2-2b alone took 8 min under host load ~220: its and SmolLM3's chat templates prepend long system headers) projected the full queue plus the C-harvest past a safe margin. Registered drop order applied: the Qwen3-4B-Base plain-completion re-run (the chat-template 
- `github_file_size_split` the per-position C-harvest tensors are stored as numbered parts below GitHub's 100 MiB limit: harvest/<tag>/D_resp.npy (120-290 MB for the 1.5B-4B checkpoints) was split along the cell axis into harvest/<tag>/D_resp_parts/D_resp_part_NNN.npy (<= 90 MiB each) + index.json by src/split_large_arrays.py, which verified every reassembled array BIT-IDENTICAL to the original before deleting it (res
