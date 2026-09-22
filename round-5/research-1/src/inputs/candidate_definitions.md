 /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_2 (src/engine.py hooks, src/prep.py directions, src/judge.py, prereg_gpu_addendum.json) rather than rewriting it; fitted directions and harvests are at /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_experiment_1/harvest and /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_1/out/released. Freeze prereg.json with SHA-256 BEFORE the first 4B outcome. Smoke-test one cell on Qwen3-0.6B, checkpoint per cell, cut R draws before cutting cells. Judge spend tracked after every batch, planned at $1-2 of the $10 cap. VRAM budget 12.5 GB under the lease protocol -- the executed iteration-4 grid ran with a per-process cap of 0.55 of the card (about 13 GB) and a 2.5-3.0 GB KV budget, with the largest observed prefix cache at 1,312 MB and NO OOM events, so 10 GB would not have been enough and 12.5 is the measured requirement. Hygiene: release rates and statistics only, no edited weights, no raw harmful completions.


THE SCREENED POPULATION (15 scored candidates in three families, plus P1 as a meta-test).
Every candidate reads ACTIVATIONS OR WEIGHTS OF ONE MODEL, needs no parent and no judge, and uses
at most 32 prompts. Logit and text quantities appear only as bars. Each candidate is defined here
completely enough to code from, because a vague definition is how four screens collapsed onto one
coordinate.

READOUT TARGET used by W1-W7, stated once so nobody drifts to logits: fit a LATE-BAND refusal
representation vector r_late on band B6 from the model's own harmful-vs-benign contrast, on prompt
FOLD A only. All write-gain quantities are the change in the mean projection onto r_late, measured
on FOLD B, caused by an intervention applied at an EARLIER band. Activation in, activation out.
Fold A and fold B are disjoint halves of the 32-prompt set, and the two folds are swapped and
averaged (cross-fitted), so no quantity is fitted and scored on the same prompts.

FAMILY I -- WRITE-HANDLE AND REDUNDANCY. Every one is reported NET OF a matched-norm
orthogonalised random direction R applied at IDENTICAL displacement (>=10 draws), and as a
distribution over prompt draws, direction-fit seeds and band boundaries, never as a bare mean.
 W1 SITE-LOCAL WRITE GAIN. Project the model's own fitted request axis F out at band b at the last
    prompt token; record |delta proj onto r_late| minus the R-control value. The registered scalar
    is W1 at the band chosen on FOLD A alone; the full 6-band curve is printed beside it. No
    post-hoc argmax.
 W2 REDUNDANCY DEPTH. Smallest k in 1..6 such that JOINT ablation of the k bands (in a greedy
    nested order fixed on fold A) drives the r_late projection below 0.5x its unperturbed value.
    Undefined -> reported as 7 (censored), never dropped. Predicted ordering Base < instruct < SafeRL.
 W3 POSITIONAL REDUNDANCY RATIO. All-position ablation effect divided by last-prompt-token-only
    effect in the same band. Registered directly off the executed instruct 0.917->0.667 vs SafeRL
    DiD +0.229 [+0.083,+0.375] contrast at band B4.
 W4 SELF-REPAIR COEFFICIENT. After ablating the F component at band b, the fraction of that removed
    component that the layers ABOVE b write back by the end of the stack. Positioned explicitly as a
    per-checkpoint scalarisation of the known backup / hydra-effect phenomenon, never as its discovery.
 W5 BENIGN-SIDE WRITE GAIN. W1 computed for the XSTest benign-twin axis N6 on hard-benign prompts.
 W6 SIGNED TWO-SIDED GAIN = W5 - W1. Two-sided by construction; BL1 cannot have this quantity.
 W7 DECODE-SITE WRITE GAIN. W1 read at the model's own first 1-8 greedy decode positions.
 W8 ROTATION UNDER SELF-LESION. Cosine between the model's own F before and after its OWN
    fixed-strength rank-one self-lesion (W <- W - a u u^T W on o_proj and down_proj, applied as an
    output projection so alpha=0 is a bitwise no-op and the restore is exact). Parent-free by
    construction. Registered off the executed abliterated rotations 0.412/0.306/0.328 (F) and
    0.021/0.027/0.061 (N6) at B4-B6.

FAMILY II -- DIMENSIONLESS GEOMETRY OF USE (ratios and angles, so they escape both the null-SD
scaling problem and the level collinearity).
 G1 HARMFUL-VERSUS-BENIGN-TWIN ANGLE at the model's own best band (chosen on fold A).
 G2 THREE-CLUSTER MARGIN RATIO d(harmful, hard-benign) / d(hard-benign, plain-benign). A blanket
    refuser sits near zero; this is the internal analogue of safe engagement.
 G3 USED-NESS. Cosine between the fitted axis and the residual delta the band's OWN layers actually
    add on harmful prompts: does the model write along the axis it can be read on.
 G4 BL1-ORTHOGONAL FISHER RATIO. Separation computed in the subspace orthogonal to the unembedding's
    refusal-token rows; carried as the one level-family candidate that is BL1-residual by construction.

FAMILY III -- COMPETING MECHANISMS, carried from the hypothesis's own runner-up answers so the
screen can genuinely disagree with itself. These are DIFFERENT answers to the same ask, not
variants of family I.
 A1 PRIOR + EVIDENCE SLOPE. The input-independent refusal PRIOR read from a contentless forward pass
    (BOS / empty chat template only, literally zero prompts) plus the EVIDENCE SLOPE, the per-unit
    movement of the internal readout along the graded-harm ladder. Two numbers, scored jointly and
    separately. This is the extreme point of the commission's "0- to few prompts" ask.
 A2 BENIGN-ONLY FOOTPRINT. The shift of the model's benign computation against its own benign
    baseline, with NO harmful text anywhere in the pipeline. K3 was the only candidate that passed
    iteration 1's S1 gate, and it is only PARTIALLY scooped (LatentBiopsy 2603.27412), so it is the
    cheapest live competitor and is deployable where harmful prompts are not.
 A3 DOMAIN-PROFILE DISPERSION. Within-checkpoint dispersion of the per-harm-domain gain across the
    OR-Bench 10-domain vocabulary. Wins outright if within-checkpoint variance exceeds
    between-checkpoint variance, which would mean the field's single safety number is the wrong
    object however it is measured.

FAMILY IV -- P1, THE COMPETING CLAIM, tested by the pre-screen and by an explicit dimensionality
analysis rather than by a new readout: a cheap single-model readout has only ONE usable coordinate,
the request axis, which AMS and the logit gap already read. P1 wins if the pre-screen drops every
candidate. Its quantitative form is the EFFECTIVE RANK of the candidate x checkpoint score matrix
after standardisation, with and without BL1 partialled out, plus the leading eigenvector's loading
pattern. If effective rank is ~1 and the leading eigenvector is BL1-aligned, the paper's deliverable
is the BOUND, and that is a result the field would act on.

INCUMBENT BARS, printed beside every row and NEVER eligible to win under the run invariant:
BL1_easy, BL1_hard and BL1_truelogit, always labelled separately and with the prompt set named
(the instruct/SafeRL ordering FLIPS between them: 6.650 vs 7.498 on EASY, 6.21 vs 4.65 on HARD);
AMS Tier-1 sigma at batch 1 AND batch 8 (the released CLI's padding bug shifts Falcon3 by 5 sigma);
AMS Tier-2; N1, N6, C7, C13_peak_d, N11; B7_nullproj; the model-card/name regex (0/15 false alarms,
5/9 sensitivity, zero forward passes) and the greedy refusal-text rate (2/15, 7/8); plain
difference-in-means; and a prompting ceiling. The last two are the mech-interp field's mandatory
baseline floor for any direction-based unit.


FIELD-NORM REQUIREMENTS, binding on every candidate (mechanistic-interpretability handbook).
 (A) The decodable-but-inert result is the field's KNOWLEDGE-ACTION GAP (Basu 2603.18353: probes at
     98.2% AUROC against 45.1% output sensitivity; the zero-and-zero figure is the SAE arm ONLY).
     It is a cited PREMISE here, never a finding.
 (B) A write-handle scalar may not be called actionable without output-level correction AND
     collateral disruption on already-correct cases against a random-perturbation control. Where only
     the readout half is run, the claim is stated as READOUT-ONLY.
 (C) Directional and circuit-level quantities swing under small changes of prompts, seeds and
     hyperparameters, so every candidate is a DISTRIBUTION over prompt draws, direction-fit seeds and
     band boundaries, with the per-sample effect distribution and the failure regime printed beside
     any mean. A candidate whose sign is not stable across those draws is reported as UNSTABLE, not
     as an effect.
 (D) Difference-in-means and a prompting ceiling are reported beside every candidate, in addition to
     BL1 and AMS sigma.
 (E) NO SAE substrate and no circuit-discovery framing. These are raw-activation directional
     quantities and must stay outside both of the field's two most-worked lanes.
 (F) MAP-SILENCE IS NOT OPEN. The handbook contains ZERO mentions of self-repair, hydra effect,
     backup behaviour or redundancy, and it states that map-silence means not-yet-checked, with a
     measured base rate of 11 of 11 unchecked lanes turning out to be occupied. So
     redundancy-as-a-per-checkpoint-scalar and self-repair-as-a-per-checkpoint-coefficient may NOT be
     called novel until the research lane's fresh dated saturation search returns. Plan for the
     search coming back OCCUPIED: W2 and W4 are then reported as measurements positioned against
     that work, and the paper's novelty rests on the over-refusal target and the graded-no-op audit.
 (G) STEERING-RELIABILITY IS A CROWDED LANE and W1, W3, W4 and G3 sit next to it. Per-sample
     unreliability and the linear-approximation limit of steering are already characterised. No
     candidate is presented as a new steering method or as a steering-reliability diagnostic; the
     defensible framing is HOW THE DIRECTION IS USED BY THE MODEL'S OWN DOWNSTREAM COMPUTATION, and
     that distinction must be made explicitly in the text rather than left implicit.
 (H) ACTIVATION PATCHING IS THE GOLD-STANDARD CAUSAL METRIC and the first-order gradient-based
     approximation's dominant error comes from downstream NON-LINEARITY, not local curvature. W1 and
     G3 both assume a roughly linear local effect, so on a declared subset of cells they must be
