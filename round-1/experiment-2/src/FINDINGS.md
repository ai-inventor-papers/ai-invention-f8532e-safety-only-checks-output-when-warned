# LANE B — findings as they land  (fill numbers from out/*.json; do not quote from memory)

## F1. The two safety axes are nearly ORTHOGONAL  (STAGE 6 gate G1, but reported as a RESULT)
|cos(r_content, r_ablit)| = **0.159 pooled / 0.175 max** over the frozen band (layers 13-21).
- r_content = RESPONSE-position hazard-content axis, fitted on a disjoint 64-pair corpus.
- r_ablit  = PROMPT-position harmful-vs-harmless REQUEST axis at the last prompt token,
             Cohen's d = 11.16 at its best layer (22).
The pre-registered kill-risk was HARC (arXiv 2607.00572), reported to find prompt- and
response-site harm directions STAY ALIGNED. At <=0.175 the gate PASSES: what the model
represents about the REQUEST and what it represents about the RESPONSE CONTENT are
different directions. Instrument valid; and the number itself is new for this pairing.

## F2. A real community abliteration is per-matrix rank-one at FULL strength (STAGE 9, weights only)
mlabonne/Qwen3-4B-abliterated vs its parent Qwen/Qwen3-4B, all 72 residual-write matrices:
- sigma_1^2 / ||Delta||_F^2  median **0.9945** (min 0.650)  -> yes, rank-one per matrix
- implied alpha              median **0.973** (IQR 0.54-1.42) -> alpha=1 IS the community operating point
- embed_tokens **NOT edited** -> contrary to the plan's expectation. Qwen3-4B has
  tie_word_embeddings=True, so had it been edited the (tied) UNEMBED would have moved too.

## F3. But the direction ROTATES WITH DEPTH — safety is not ONE direction (STAGE 9b)
- pooled rank-one share across all 72 matrices = **0.433** while per-matrix = 0.994.
  Both can only hold if each matrix gets its OWN direction.
- adjacent-layer |cos| median **0.773** (smooth drift)
- shallowest vs deepest |cos| = **0.016** — layer 0's edit direction is ORTHOGONAL to layer 35's
- o_proj and down_proj give IDENTICAL drift numbers -> the two write matrices INSIDE a layer
  share one direction. The recipe is: ONE DIRECTION PER LAYER.
- our per-layer r_ablit matches the community direction at |cos| median **0.646** (max 0.883),
  versus only **0.265** for a single pinned direction.

## F4. Consequence: a single-pinned-direction lesion barely bites (registered grid)
At alpha 0 -> 0.25 on Qwen3-4B: held-out CV probe AUROC 1.000 -> 1.000; |CB| 23.7 -> 23.8
null-SD; |A| 9.86 -> 9.70; K3 benign-only footprint 0 -> 0.342 (so the edit IS changing
activations). Pre-registered failure mode F1 (no matched-damage point) is LIVE.
NOTE ON THE DIAGNOSTIC: AUROC along u is INVARIANT to a positive rescaling of the
u-component, and the lesion rescales exactly that component by (1-alpha). So the AUROC
cannot move for alpha<1 however well the edit works — the raw projection GAP is the
sensitive companion, and both are reported.

## F5. Held-out probing is mandatory (validated here, not asserted)
On PURE NOISE at d=2560, n=256: in-sample difference-in-means AUROC = **1.000**;
5-fold cross-validated probe AUROC = **0.464**. Every damage number uses the CV probe.

## F6. Instrument checks
- band [13..21] = depth fraction 0.36-0.61, chosen on the FITTING CORPUS ONLY then frozen
- r_content split-half cosine **0.927** (gate 0.70) -> stable axis
- hooks: determinism exactly 0.0, batch-invariance 1.3e-3 (bf16 noise)
- alpha=0 is a BITWISE no-op; embed_tokens provably unmodified; lm_head IS embed_tokens
- hook-lesion vs a genuine bf16 weight mutation agree to 1.6% of max |logit| at alpha=1,
  against an edit effect of 13.4 logits (the hook is the higher-precision implementation)
- achieved r = SD_item(real)/SD_item(null) = **6.07**, far above the r~1.2 the registered
  thresholds were sized at, so power is better than the prereg's stated 60-70%

## F7. THE HEADLINE (Qwen3-4B, registered single-pinned-direction grid, alpha 0 -> 1)
The lesion is verified to work EXACTLY as specified, and the harm representation survives it ENTIRELY.

  alpha                      0.00    0.25    0.50    0.75    1.00
  raw projection gap on u   47.05   35.03   22.69   10.74    0.01     <- the lesion
    normalised               1.000   0.744   0.482   0.228   0.0002
    predicted (1 - alpha)    1.000   0.750   0.500   0.250   0.000    <- matches to ~1%
  held-out CV probe AUROC    1.000   1.000   1.000   1.000   1.000    <- the representation
  JBB behaviour-matched      0.970   0.972   0.971   0.976   0.976
  1-D AUROC along u          0.9993  0.9993  0.9993  0.9992  0.590
  benign continuation NLL     4.138   4.105   4.072   4.045   4.017   <- model stays coherent

Read this row by row. At alpha=1 the component along the fitted request axis is GONE
(gap 47.05 -> 0.01, i.e. 0.02% of baseline) in every residual-stream write of all 36 layers.
The 1-D readout along that very axis duly collapses, 0.9993 -> 0.590. And a held-out
cross-validated probe on the SAME hidden states still separates harmful from harmless
requests at AUROC **1.000**, and a behaviour-matched probe at 0.976. The model has not been
broken - benign NLL does not rise.
=> Removing the harmful-request direction COMPLETELY does not remove the model's ability to
   tell harmful requests from harmless ones. The percept is redundantly encoded in the
   orthogonal complement. What a rank-one abliteration removes is the refusal ACTION, not
   the harm PERCEPT.

## F8. The registered K1 signature is HALF-satisfied, and cannot be scored by the registered rule
  |A| arming interaction (null-SD)  11.95  11.56  11.00  10.31   9.43   <- FALLS 21%, monotone
  |CB| content main effect          25.51  25.51  25.54  25.53  25.38   <- HOLDS (-0.5%)
That IS the registered signature "A collapses INTO the null band while CB SURVIVES", in sign.
But the registered matched-damage variable never moves, so alpha* does not exist and every
S2 row is scored INDETERMINATE, exactly as failure mode F1 prescribes. The threshold was NOT
relaxed. A labelled FULL-ANNIHILATION companion is reported alongside, because alpha=1 IS a
well-defined common operating point (gap -> 0.02% in every lineage; the real community edit
sits at implied alpha 0.973).
Other readouts at alpha 0 -> 1:  K2 prior -3.518 -> -3.224 | K3 footprint 0 -> 2.072 |
K4 tau 39.7 -> 47.7 tokens (LENGTHENS - the registered signature predicted SHORTENS, so K4's
sign is OPPOSITE to prediction) | K5 dispersion 0.174 -> 0.145 | G2 87.5 -> 77.1 (passes) |
G3 cos(r_parent, r_child) 1.000 -> 0.978.

## F8b. S2 read correctly: the registered wording is a LEVEL test, not a change test
"A collapses INTO the null band while CB SURVIVES" asks WHERE each term ENDS UP, not which way
it moved. Scored that way on Qwen3-4B at full annihilation (alpha=1, the labelled companion):
  K1_A_arming                 FAIL  |A| 11.95 -> 9.43 null-SD. It attenuates, it does NOT
                                    collapse into the null band (9.4 SD is nowhere near 1 SD).
  K1_CB_survives              PASS  |CB| 25.51 -> 25.38 null-SD, CI [-0.35,+0.09] covers 0.
  K1_A_attenuation (descr.)   PASS  the 21% fall is real: CI [-2.88,-2.16] excludes 0.
  K2_prior                    PASS(sign) |prior| 3.518 -> 3.224
  K2_slope                    PASS  0.2152 -> 0.1571, still 73% of pre (rule: >50%)
  K3_footprint                PASS(sign) 0 -> 2.072 raw L2
  K4_tau                      FAIL  39.7 -> 47.7 tokens. The registered signature says SHORTENS;
                                    it LENGTHENS. Reported as the opposite sign, not reinterpreted.
  K5_profile                  PASS(sign) dispersion 0.174 -> 0.145
Every one of these is a COMPANION. The REGISTERED rows are all INDETERMINATE_NO_MATCHED_POINT
because the registered damage variable is flat and alpha* does not exist.

## F9. *** THE HEADLINE *** The orthogonal complement gets BETTER after the lesion
Measured offline from the alpha=0 and alpha=1 harvests. Directions are fitted on the r_ablit
FITTING requests and projected out of the HELD-OUT request activations at the last prompt
token; the 5-fold CV probe is then re-scored. Control = removing the same number of RANDOM
orthonormal directions.

  Qwen3-4B, layer 22, held-out 128+128 requests
  k directions removed        0      1      2      4      8     16     32     64    128
  ---- alpha = 0 (intact) ----
  greedy class directions   1.000  0.800  0.813  0.810  0.820  0.812  0.819  0.791  0.822
  random directions         1.000  1.000  1.000  1.000  1.000  1.000  1.000  1.000  1.000
  variance kept             1.000  0.515  ...
  ---- alpha = 1 (u deleted from all 72 write matrices, all 36 layers) ----
  greedy class directions   1.000  0.778  0.806  0.807  0.800  0.782  0.807  0.777  0.797
  random directions         1.000  1.000  1.000  1.000  1.000  1.000  1.000  1.000  1.000
  variance kept             1.000  0.773  ...
  |cos( top class direction at alpha=1 , the deleted u )| = 0.00016
  ^^ NOTE, stated plainly: this orthogonality is FORCED BY CONSTRUCTION, not discovered.
     At alpha=1 the residual stream has no u-component left, so ANY direction fitted on those
     activations must be orthogonal to u. It is not the finding and is not reported as one.

THE FINDING IS THE k=0 vs k=1 COMPARISON ACROSS THE TWO STATES, not the orthogonality.
Both rows live in the 2559-dim orthogonal complement of u. In the INTACT model that complement
is NOT enough: project u out post hoc and the held-out probe falls 1.000 -> 0.800. In the
LESIONED model - where the model was never allowed to write u at all - the complement reads
1.000. The same subspace carries MORE class information after the lesion than before it.
Removing 128 RANDOM directions costs nothing in either state, so the drop is specific to the
class direction.

=> Safety-relevant harm recognition does not live in a fixed direction. It lives in something
   the forward pass can RE-DERIVE. A rank-one orthogonalisation removes the coordinate, not the
   computation; the model routes around it inside a single frozen forward pass, with no
   retraining. This is why abliteration changes what a model DOES without changing what it KNOWS,
   and it bounds the whole family of prompt-fitted rank-one interventions.

## F9b. It is NOT a normalisation artefact - the obvious alternative, tested and rejected
The lesion removes a CLASS-CORRELATED component, so it changes the residual NORM in a
class-correlated way, and RMSNorm would then turn that into a class-correlated rescaling of
every other coordinate - manufacturing separability with no re-encoding at all. Tested directly:

                                         alpha=0 (intact)   alpha=1 (lesioned)
  probe on UNIT-NORMALISED activations        1.0000             1.0000
  residual NORM alone, as a 1-D feature       0.9846             0.1672
  mean ||h||, harmful / harmless            82.1 / 74.5        71.9 / 75.0
  unit-normalised, k=1 class dir removed      0.8066             0.8179

The separability survives unit-normalisation completely (1.0000), so it is not carried by the
norm. And the norm itself does the OPPOSITE of what the artefact story needs: in the intact
model ||h|| is a 0.985-AUROC harm detector on its own (harmful prompts are bigger), and the
lesion FLIPS it to 0.167 (harmful prompts end up smaller, because they had more u to remove).
The artefact would have to make the norm MORE predictive; it makes it anti-predictive.

CAVEAT, stated: this is a representational measurement at ONE read site (last prompt token,
layer 22). It says how many dimensions carry the linearly-decodable signal there and that the
orthogonal complement carries it better after the lesion. It does not by itself say the model
USES that code - that is what the STAGE 7 causal arm tests.

## F10. The mechanism: u is an ACCUMULATOR the model writes into, not where the percept lives
Depth profile on Qwen3-4B, held-out 128+128 requests, last prompt token, band layers 13-22:

  layer                      13     14     15     16     17     18     19     20     21     22
  held-out AUROC, alpha=0  .9996  .9996  .9998  .9998  .9999  1.000  1.000  1.000  1.000  1.000
  held-out AUROC, alpha=1  .9998  .9993  .9996  .9996  1.000  .9998  1.000  .9998  1.000  1.000
  |gap| along u, alpha=0    0.34   0.53   0.77   0.96   1.97   6.28  13.24  20.57  26.28  47.05
  |gap| along u, alpha=1   0.003  0.004  0.004  0.005  0.008  0.008  0.007  0.009  0.009   0.01
  cos(class dir a=0, a=1)   .985   .983   .979   .976   .960   .883   .815   .663   .461   .000
  cos(class dir a=1, u)     .000   .000   .000   .000   .000   .000   .000   .000   .000   .000

Four things at once:
 1. The harmful/harmless distinction is already at AUROC ~1.000 by layer 13 and stays there in
    BOTH the intact and the fully lesioned model. Depth adds no decodability.
 2. In the INTACT model the signal along u GROWS 138-fold with depth (0.34 -> 47.05). u is where
    the model progressively CONCENTRATES a distinction it already has.
 3. The lesion zeroes that concentration at every depth (0.003-0.01, i.e. ~0.02% of baseline).
 4. The lesioned model's class direction is nearly IDENTICAL to the intact one at shallow layers
    (cos 0.985 at L13) and rotates away only as depth increases, reaching exact orthogonality at
    layer 22 - the layer u was fitted at.

=> u is an ACCUMULATOR COORDINATE, not the locus of the representation. Abliteration deletes the
   accumulator. The percept was computed earlier, in a code the edit never touches, and the deep
   layers simply stop pouring it into the deleted coordinate. That is the mechanism behind F9,
   and it is why "where does safety live?" has the answer: not where abliteration cuts.

## F11. Causal-arm instrumentation note (found in a pilot, fixed before the real runs)
Hook sanity all passes on a tiny-model pilot: null patch self->self is BITWISE identical, a
matched-norm random direction at beta=+1 moves refusal drive by -7.8e-08 (~0), beta=0 is exactly
0, and the LABELLED full-residual positive control does move it. But refusal-onset mass measured
at the registered position - immediately after the WHOLE 128-token forced span - sits at ~1e-6
for every condition. That is a FLOOR, and a null read there would be uninterpretable.
So a SHORT-SPAN variant (intervene on the first 8 response tokens, read immediately after) runs
ALONGSIDE the registered one, same token set, same beta grid, same control. In the pilot it had
~100x the dynamic range. Both are reported; the registered one is not replaced.

## F12. It REPLICATES on the extra-safety-tuned lineage (L3 = Qwen3-4B-SafeRL, r_ablit layer 23)
                                        L2 Instruct        L3 SafeRL
  k=1 class dir removed, alpha=0       1.000 -> 0.800    1.000 -> 0.799
  k=1 class dir removed, alpha=1       1.000 -> 0.778    1.000 -> 0.788
  128 RANDOM directions removed         1.000             1.000
  probe on unit-normalised, alpha=1     1.0000            1.0000
  residual NORM alone, alpha=0          0.985             0.997
  residual NORM alone, alpha=1          0.167             0.261   (flips in both)
  |gap| along u, layer 13 -> fit layer  0.34 -> 47.05     0.25 -> 62.49
  growth factor along depth              ~138x             ~250x
  cos(class dir a=0, a=1) L13 -> fit     .985 -> .000      .990 -> .000

Same structure, same controls, same norm-artefact rejection, in both the Instruct model and the
model given EXTRA safety RL on top of it.

CORRECTION TO AN OBVIOUS MISREADING OF THE TABLE. The raw u-gap looks bigger in SafeRL (62.5 vs
47.1), which invites "extra safety RL builds a bigger accumulator". It does NOT: SafeRL's whole
residual stream is larger. Divide the gap by that checkpoint's own mean ||h||:
    L2 Instruct  47.05 / 78.30 = 0.601
    L3 SafeRL    62.49 / 105.25 = 0.594
The two are the same to within 1%. This is exactly the cross-checkpoint SCALE problem the plan
flags, and it is why the registered readouts are expressed in per-item null-SD units and why K4's
tau is in TOKENS. Raw-scale cross-checkpoint comparisons are reported ONLY beside their
normalised twin.

## F13. *** THE METRIC *** Two numbers from 256 prompt-only forwards separate safety tuning
Fit the request axis r_ablit (difference in means, harmful vs harmless REQUESTS, at the LAST
PROMPT TOKEN) at every layer of ONE model, and report (a) the best layer's Cohen's d and (b) that
layer's DEPTH FRACTION. No generation, no benchmark, no reference model, no judge.

  checkpoint                                    safety-tuned?   best layer  depth frac   d
  Qwen/Qwen3-4B-Base                    (L1)         no             29        0.806     5.68
  CohenQu/...HintGen-STaR (FT of Base)  (L4)         no             29        0.806     5.74
  Qwen/Qwen3-4B                         (L2)        yes             22        0.611    11.15
  Qwen/Qwen3-4B-SafeRL                  (L3)        yes             23        0.639    11.41

Both coordinates separate the two groups cleanly and in the same direction: safety tuning roughly
DOUBLES the request-axis separation (5.7 -> 11.2) and moves it about SEVEN LAYERS EARLIER
(depth .81 -> .62). The load-bearing control is L4: it is a fine-tune of L1 on a NON-safety
objective, and it lands exactly on top of its base parent (5.74 vs 5.68, same layer 29). So the
readout is not detecting "this model was fine-tuned" - it is detecting safety tuning specifically.

COST: 128 harmful + 128 harmless requests, prompt-only, teacher-forced, single forward pass each.
CAVEAT, stated: n = 4 checkpoints. This is a demonstration with one clean negative control, not a
validated metric. The prompt-budget curve in the outputs reports how few items the paired
lineage contrasts actually need.
