# Which safety readouts are still unclaimed

## Summary

Dated web-only saturation and verification pass, 2026-09-21, $0.00 spend, no cuts taken. Self-verification: 105/105 quote-grade passages re-confirmed by an independent live re-fetch of their own URL; 1 quote deleted as a composite (logged, substantive claim unaffected); 8 anchors recovered beyond the ~50 KB page-fetch horizon kept visibly separate; 3 zero-match regexes used as absence evidence kept separate again and each independently reproduced. Bibliography regenerated from live arXiv metadata: 65/65 ids resolved, 0 UNRESOLVED.

VERDICTS on the seven EXECUTION-side candidates, none OPEN: X2 (weight-space write mass) and X10 (weights-only orthogonality scar) are CLOSED - not by arXiv:2607.01854, which this pass proves is REFERENCE-ANCHORED on BOTH signals ("The audit rests entirely on the reference"), but by the Jorak Model Scanner, a live NON-PEER-REVIEWED open-source tool that ships the exact normalised ||r^T W|| suppression statistic with r fitted from the candidate's OWN activations and a weights-only zero-inference SVD subspace-alignment scar test (A/B/S), calibrated cross-model. X1 PARTIAL (per-input vs per-checkpoint; nearest HPD/HERALD 2609.13534 and Geometry-Lite 2605.20241 scalarise depth profiles per PROMPT). X3 PARTIAL (concept + lexical-token dependence; nearest Logit-Gap Steering 2506.24056). X5 PARTIAL (parent-requiring, only 2 checkpoints; 2607.14147's 0.24-vs-0.03 concentration is a knockout-conditioned instruct-vs-base pair, n=60). X6 PARTIAL on the thinnest margin in the table. X8 PARTIAL (concept).

TWO ADVERSE PRIORS ITERATION 1 DID NOT HAVE, and they own this iteration's axis. (1) arXiv:2604.09544 (Orgad, Wei, Zheng, Wattenberg, Henderson, Goldfarb-Tarrant, Belinkov) - iteration 1 mis-filed it as a pruning-only paper; its abstract publishes "harmful response generation is dissociable from the ability to recognize and reason about harmfulness", a DOUBLE DISSOCIATION between harm generation and refusal, and separability GRADED along the OLMo3-7B alignment ladder (emerging at DPO). (2) arXiv:2603.05773 "Knowing without Acting" names the axes Recognition (v_H) and Execution (v_R) and demonstrates a causal double dissociation on harm. (3) arXiv:2606.24952 publishes a per-checkpoint weight-computable detection-vs-control cosine over four models (0.12/0.20/0.16/0.13; 0.1197 vs 0.1200 across instruction tuning) and concludes it is "not a predictor of how steerable a behavior is". NONE of the three evaluates an abliterated checkpoint (grep abliterat|uncensor = 0 matches on 2606.24952 and on 2603.05773) - that is the one genuinely empty cell.

N-GLARE ALREADY RUNS THIS RUN'S PANEL: ACL 2026 Long 1334 s1 illustrates JSS on "RL-aligned, base, and safety-removed versions of Qwen3-4B". Its margin is input cost only (four constructed dialogue families per model). Re-checked 2026-09-21: STILL NO CODE, and NO numeric Kendall's tau anywhere (Appendix Tables 6-8 are per-model benchmark values) - iteration 1's prohibition stands permanently.

CLEAN NOT-FOUND worth more than any candidate: NO prior work scores a SAFE-COMPLETION model (declines without a lexical refusal) with an INTERNAL readout; OpenAI's 2508.09224 and OpenSafeIntent 2607.02047 are purely behavioural. Every lexical-refusal-keyed internal readout is undefined on GPT-5-class safety training.

CORRECTIONS FORCED ON THE DRAFT: the hypothesis mis-states Basu 2603.18353 (zero-and-zero is the SAE arm ONLY; Arm 1 corrected 17/85 and disrupted 25/47; TSV 19/79 and 4/65); the planner's dose figures for 2512.13655 (minimum effective dose, >=30% bypass, 0.028 MMLU) are FABRICATED and absent across all three rungs; SRP's safety-audit mention is Future Work not abstract; Arditi does NOT logit-lens the refusal direction. Bibliography: Arditi = 7 authors + NeurIPS 2024, 2606.16349 = 6 authors not 1, 2606.22676 = 8 not 1, 2604.18901 MUST BE ADDED. HRCI_repr (G10) is NOT reimplementable as specified - Eq 8's k is never stated; Table 1 implies k=3, which must be declared. NO published behavioural dose curve over abliteration strength exists; the run's causal lane would be first.

KILL X2, X10, and X5-for-novelty. SCREEN ORDER: (1) R-E gap on the abliterated checkpoint, (2) X1, (3) the safe-completion cell of X3.

## Research Findings

# Verdict in one line

**Not one of the seven execution-side candidates is OPEN: two are CLOSED and five are PARTIAL** — and the pass surfaced two papers that between them already publish this iteration's governing axis (recognition versus execution, on harm, with a causal double dissociation), plus confirmation that the published incumbent already runs this run's exact Qwen3-4B panel.

## 1. The seven verdicts

Under iteration 1's verdict rule held identical — CLOSED = same quantity, over >1 model, presented as a cross-model score; PARTIAL = right construct at a different level, per-input rather than per-checkpoint, parent-requiring rather than parent-free, or on a different concept; OPEN = nothing found after the full five-kind query protocol — the screen returns:

- **X1 accumulator gain — PARTIAL**, escape hatch *per-input vs per-checkpoint*. Nearest work is HPD/HERALD, which "extracts a seven-dimensional feature record, slope, curvature, monotonicity, onset layer, and related statistics from the cross-layer projection sequence" — almost exactly X1's operations — but as a per-instance record fed to a 288-parameter input moderator [17]. Geometry-Lite does the same scalarisation over nine backbones, again per prompt, "summarizes the resulting margin profiles by boundary position, layer-to-layer change, and coarse shape" [16]. HARC's Appendix A.3, the very object X1 ratios over, stays heat-map-only [31]. Nobody reduces a harm-projection depth profile to one number per checkpoint and ranks models on it. Confidence: medium.
- **X2 weight-space write mass — CLOSED.** Confidence: high.
- **X3 analytic percept-to-refusal gain — PARTIAL**, escape hatch *concept plus lexical-token dependence*. The nearest relative computes "the difference between the top refusal-token logit and the top affirmative-token logit at the first decoding step" [14] — a fixed per-prompt gap over pre-identified vocabulary, not an analytic slope with respect to a continuous harm projection, and undefined for a model with no lexical refusal token. Confidence: medium-high.
- **X5 routing concentration — PARTIAL**, escape hatch *parent-requiring plus only two checkpoints*. The exact statistic is defined and printed — "when the knockout frees probability mass off the compliance continuation, the instruct model routes it to refusal tokens about 8× more than the base model does (concentration 0.24 vs 0.03, App. E)" — but only for one instruct checkpoint against its own base anchor, n = 60, and only conditional on a causal knockout [13]. The nearest cross-model relative measures a different construct: a subspace-RANK causal-transfer share (76% of refusal's causal input outside the rank-16 moral basis) reported for one model, OLMo-3, with the other families described qualitatively [37]. Confidence: high.
- **X6 the gap itself — PARTIAL**, escape hatch *concept*, and the thinnest margin in the table. Confidence: medium.
- **X8 execution depth margin — PARTIAL**, escape hatch *concept*. The readable-before-usable depth lag is published at least three times off-concept [18, 20], and the nearest multi-model paper never quantifies it (full-document grep for `onset layer|depth-fraction|fraction of depth|layers apart|difference in layer|layer gap`: 0 matches in 65,151 characters) [20]. Confidence: medium.
- **X10 weights-only orthogonality scar — CLOSED.** Confidence: high.

## 2. X2 and X10 are closed by a shipped tool, not by the paper everyone expected

The planning step expected arXiv:2607.01854, the 273-checkpoint abliteration audit, to be the closer. **It is not, and the reason is decisive: it is reference-anchored on both signals.** Its own abstract says it combines "a reference-anchored activation refusal-gap and a weight-recovery energy of the base-to-candidate weight difference, into a threshold-free checkpoint audit" [9], concedes that "The audit is effective triage, not tamper-proofing: it presumes an attested reference, and its claims are bounded by the registry we evaluate it on" [9], and records that "a spoofed reference evades both axes with no training" [9]. Its weight signal is the rank-one spectral energy of ΔW = W_base − W_candidate. Parent-freeness therefore *is* a real margin over that audit.

It is not a margin over the **Jorak Model Scanner**, a live open-source repository verified today, whose stated purpose is "**Reference-free** detection of **abliteration** in open-source LLMs… **without access to the original model**" [7]. Its metric documentation defines X2's exact quantity — "`suppression_ℓ = ‖r̂ᵀW‖ / (‖r̂‖·‖W‖_F)` pour `W ∈ {o_proj, down_proj}`, par couche" — and calibrates it cross-model: "Calibration mesurée : censuré ≈ `0.038` vs abliteré ≈ `2e-8`" [8]. Its stated rationale is explicitly parent-free: "on n'a pas besoin de générer ni de comparer à un original pour séparer *censuré* de *ablated*" [8]. It also ships X10's exact test, weights-only and inference-free ("NumPy pur, sans inférence" [8]), stacking each layer's least-singular-vector into U and taking "**A = σ₁(U) / ‖U‖_F**" [8], with worked values of "`A = 0.184` ≈ le plancher 0.167 → `u_min` dispersés" for censored Qwen3-8B against "`A = 0.705` → forte direction commune → poids sectionnés" for Josiefied-Qwen3-8B-abliterated-v1 [8]. It even pre-empts the rank-one objection with a bottom-k subspace statistic built for multi-direction ablations [8], which is precisely what the concept-cone and affine-function lines predict is needed [35, 36]. The community method literature on *performing* bounded ablation supplies the same geometric intuition but no detector [40]. A separate candidate closer, arXiv:2608.05578, was checked and does not close the lane: it scores activation geometry for safety-training modification but carries no weight-side companion signal [38].

**Honest caveat.** Jorak is a 17-commit repository validated "on a real matrix of 4 models derived from `Qwen2.5-0.5B` — accuracy 4/4" [7], and it is **non-peer-reviewed**. Under the run's own rule it closes both lanes; under a reviewer's eye it might not. The defensible reading is that **X2 and X10 are closed as ideas** — public, documented, implemented, calibrated — even though the empirical bar is low, so re-running them would be replication at larger n, not novelty.

## 3. The two adverse priors iteration 1 did not have, and they are the story

**arXiv:2604.09544 (Orgad, Wei, Zheng, Wattenberg, Henderson, Goldfarb-Tarrant, Belinkov).** Iteration 1 filed this id as "a real paper but about parameter-level pruning, not the harmfulness/refusal split". That is wrong, and the correction matters more than any verdict in the table. Its abstract states: "We further show that harmful response generation is dissociable from the ability to recognize and reason about harmfulness" [1]. It reports a **double dissociation** between harm generation and refusal on Llama-3.1-8B-Instruct and Qwen-2.5-14B-Instruct — "impairing one leaves the other intact, indicating a double dissociation" [1] — with pruned models that "can still recognize harmful requests, refuse, and explain their risks" [1]. And it grades the dissociation along an alignment ladder: "Across the OLMo3-7B checkpoint sequence (base → mid-train → long-context → SFT → DPO → RL), separability emerges gradually with alignment training, especially after preference optimization" [1], a phenomenon they name **mechanistic compression** [1].

**arXiv:2603.05773 (Wu, Xie, Lin, Zhao, Chen), *Knowing without Acting*.** It names the axes: safety computation "operates on two distinct subspaces: a *Recognition Axis* (v_H, 'Knowing') and an *Execution Axis* (v_R, 'Acting')", and it "demonstrate[s] a causal double dissociation, effectively creating a state of 'Knowing without Acting'" [2].

DSH's own full text shows why X6 nevertheless survives as PARTIAL rather than CLOSED: its Recognition/Execution cosine is presented as a *universal* pattern — the abstract calls it a "universal ``Reflex-to-Dissociation'' evolution, where these signals transition from antagonistic entanglement in early layers to structural independence in deep layers" [2] — and its Figure 4 reports that "In deep layers, the safety axes' similarity converges to this random baseline" against a 1000-random-vector-pair band, on three aligned models (Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.2, Qwen2.5-7B-Instruct), rather than as a differentiated per-checkpoint score [41]. Note also that DSH is a cs.CR paper whose payload is an attack — the Refusal Erasure Attack, "surgically lobotomizing the refusal mechanism" [2] — so it should be cited as a geometry precedent and its framing must not be inherited, since this run's invariant forbids reframing the study as attack selection.

A fourth independent statement of the same pattern arrives from the roleplay-jailbreak side: "Successful attacks retain the measured harmful-versus-benign distinction at the request, while its refusal-associated expression weakens where the answer begins, a pattern we call safety-relay attenuation" [27].

Together with **arXiv:2606.24952**, which publishes a per-checkpoint weight-computable detection-versus-control cosine across four models (0.12 / 0.20 / 0.16 / 0.13) and finds it "identical before and after instruction tuning" at 0.1197 vs 0.1200 [3], the recognition-versus-execution axis is occupied from three directions at once. What is *not* occupied, in any of the three, is the abliterated checkpoint: a full-document regex for `abliterat|uncensor` returns **0 matches** on 2606.24952 (64,440 chars) and **0 matches** on 2603.05773 (84,213 chars), each independently reproduced.

## 4. The single most dangerous sentence found

arXiv:2606.24952 closes with: "What the cosine *is* is a robust, weight-computable signature of the dissociation, invariant across four models — **not a predictor of how steerable a behavior is**" [3], under a section headed "The shortcut that fails: a weight-cosine is not a steerability oracle". This is an *a priori* argument, not a scope limit, and it is reinforced independently: across the Pythia suite "a linear probe can read a target variable from the residual stream as early as step 1,000 at every scale — yet steering along that same reading direction remains **null-equivalent in 43 of 48 model-checkpoint cells**" [19]. Iteration 2 must either show the harm-concept version varies discriminatively across the three Qwen3-4B checkpoints where theirs is flat, or drop the predictive framing and sell a signature — which 2606.24952 already did.

## 5. The incumbent already runs this run's panel

N-GLARE's introduction reads: "when comparing multiple variants of the same base model (e.g., **RL-aligned, base, and safety-removed versions of Qwen3-4B**), we observe that better-aligned variants exhibit more pronounced geometric separation between different trajectories in latent space" [4]. The base / safety-tuned / abliterated Qwen3-4B triple is N-GLARE's own illustrative example. The remaining differentiator is input cost, and it is genuine: N-GLARE requires **four constructed dialogue families per model** — "benign (B), jailbreak (J), plainquery (P) and an idealized refusal counterfactual (R)" [4] — so it is not a few-prompt method. Two standing constraints re-confirmed today: **no numeric Kendall's τ exists in the paper** (the running text says only that τ "remains consistently high, with p-values far below conventional significance thresholds" [4], and a table-aware read of Appendix Tables 6–8 shows they are per-model safety-benchmark values, not rank correlations), and **there is still no code** (full-PDF regex for `github|code|available at|released|reproduc` yields 7 matches, none a repository or availability statement).

## 6. The one clean NOT-FOUND, and it is worth more than any of the seven

**No prior work scores a safe-completion model — one that declines without emitting a lexical refusal — with an internal readout.** Five logged queries in both vocabularies returned only behavioural work: OpenAI's own safe-completions paper reports that "safe-completion training improves safety (especially on dual-use prompts), reduces the severity of residual safety failures, and substantially increases model helpfulness" through "production comparisons and internally controlled experiments" [29], and the follow-on evaluation concludes that "safe completion should be evaluated as intent-calibrated behavior over controlled task variants" [30]. Neither reports any activation, probe or logit-lens readout of the safe-completion decision. Every lexical-refusal-keyed internal safety readout in the literature is therefore **undefined** on a GPT-5-class model trained this way. That is a dated, falsifiable gap and the natural motivation for X3's lexicon-free formulation. Confidence: medium-high — a NOT-FOUND over five logged queries plus two fetched primary sources, not a proof of absence.

## 7. The incumbent bars, with their exact numbers and their input requirements

- **HRCI_repr** [10]: Eq. 9 is `HRCI_repr = ½·C_cos + ½·C_sub`; it falls 0.0784 → 0.0205 while ASR rises 0 → 0.25 and XSTest refusal falls 1.00 → 0.228 — and the authors state "so low coupling is not itself a safety score" (note: iteration 1's quoted wording "Thus low coupling is not a safety score" is not what is printed). **Follow-up (c) answered: G10 is not reimplementable exactly as specified** — Eq. 8 introduces k principal angles without ever stating k or the local-subspace estimator, and the only trace is Table 1's three printed angles per anchor, so **k = 3 must be assumed and declared**.
- **IRT for AI Safety** [11]: "roughly ten adaptively chosen items suffice for several individual benchmarks, cutting evaluation cost by 97-99%", fit over eight benchmarks and 192 models, with three latent factors — refusal strictness, truthfulness, contextual harm. Text-only, so a baseline here, but it owns the few-prompt regime outright.
- **The 273-checkpoint audit** [9]: AUROC 0.95 combined, 57 abliterations vs 37 benign negatives — and reference-anchored, as above.
- **N-GLARE** [4]: as above.

## 8. Corrections this pass forces on the current draft

1. **Basu et al. is mis-stated in the hypothesis text.** "Zero corrections and zero disruptions, indistinguishable from random" is true of **the SAE arm only** — "SAE feature steering produced zero corrections and zero disruptions despite identifying 3,695 significant hazard-associated features" [12]. Arm 1 "corrected 17 of 85 missed hazards (20%) but disrupted 25 of 47 correct detections (53%), indistinguishable from random perturbation" [12], and TSV "corrected 19 of 79 missed hazards (24%) while disrupting 4 of 65 correct detections (6%)" [12]. The 65/144 = 45% figure is correct and both forms are printed, but it is Qwen 2.5 7B's baseline sensitivity [12], against a 98.2% probe AUROC and a 53-point gap [12].
2. **The planner's dose-curve figures for arXiv:2512.13655 are fabricated.** No "minimum effective dose", no "≥30% refusal bypass" threshold and no "0.028 MMLU degradation" appear anywhere: all three retrieval rungs were cleared (abs; html v2 full-document regex over 58,000 chars; pdf full-document regex over 53,670 chars, **0 matches**). What the paper actually reports is a four-**tool** comparison with no intensity sweep [22].
3. **Two planner seeds about X3 do not hold.** SRP's abstract contains no mention of safety, refusal or harm — the safety-audit application is in its Section 6 Future Work and is proposed, not executed [15]. And Arditi et al. do not logit-lens the refusal direction to show it decodes to refusal words; unembedding directions appear only as an exclusion filter in the direction-selection procedure [32].
4. **Five bibliography entries and two omissions are fixed from live metadata**, and all 65 cited ids resolve (0 unresolved): Arditi et al. is seven authors, not three, and is NeurIPS 2024 [32, 33]; 2502.17420 is six authors with diacritics [35]; N-GLARE's real title reads "An Non-Generative…" [4]; 2603.27412's live title is the one the direction gave, so it is the draft that is wrong [5]; 2507.11878 gets its five authors [34]; and **2604.18901 must be added — it is absent from the reference list although it is one of the two scooping papers** [6]. Two further author-list errors carried from iteration 1: 2606.16349 is six authors, not one [10], and 2606.22676 is eight, not one.

## 9. No published behavioural dose curve over abliteration strength exists

Four targeted papers and three dated searches found none. 2512.13655 varies the tool, not the dose [22]. 2607.17427 has exactly two arms per family [23]. 2505.19056 compares defended against undefended models [24]. 2603.10012 applies Heretic once [25]. A non-peer-reviewed industry report gives baseline versus post-abliteration only [26]. **The run's causal lane would be first.** Confidence: medium — a NOT-FOUND, not a proof.

## 10. What this means for the screen

**Kill X10 and X2** (shipped and closed). **Kill X5 for novelty** — its only margin is removing a knockout and adding checkpoints, which is close to the re-parameterisation the run's own rule refuses to credit. **Demote X3 and X8.** **Run first the one genuinely empty cell in the whole space: the R−E gap measured on an abliterated checkpoint**, which none of 2604.09544, 2603.05773 or 2606.24952 evaluates. **Run X1 second**, because per-input → per-checkpoint is the cleanest escape hatch found, and guard it by showing the per-model number ranks checkpoints in a way pooled per-prompt AUROC does not. **Then the safe-completion cell of X3.**

Two housekeeping items for the write-up. Iteration 1's open follow-up about a companion methods note with no standalone arXiv id is **closed: it has one, arXiv:2609.14754**, *Calibrating Interpretability Instruments Before Trusting Their Verdicts*, explicitly a companion to the harm-keyed-routing paper, with code and per-unit arrays released [28, 37] — directly relevant to this run's null-band and instrument-integrity machinery. And the non-arXiv artefact `DrExe/qwen3-safety-vectors` returns **HTTP 401** on both its model page and the API endpoint as of 2026-09-21, i.e. gated or private, so nothing about its contents should be asserted [39].

And one constraint on how r_ablit may be described: it is fitted at the last prompt token, which is exactly the readout diagnosed as failing in arXiv:2605.12726 — "probe-visible unsafe evidence often appears earlier in the sequence but is not exposed at the final-token readout, while naive max-pooling over token positions overfires on safe prompts" [21]. r_ablit may be called a clean-harmful readout; it may not be called jailbreak-robust, and the XSTest/twin arm is precisely where its false-positive mode bites.

## Confidence and limits

High confidence in: the two CLOSED verdicts (verified live, with formulae); the reference-anchored status of 2607.01854 (settling quote); N-GLARE's Qwen3-4B panel, its missing code and its missing numeric τ; every extracted number in Section 7. Medium confidence in: the three PARTIAL verdicts resting on a concept escape hatch (X6, X8, and X1's level hatch), because a concept boundary is a judgement call a reviewer may draw differently — X6's in particular is thin. Medium confidence in the two NOT-FOUNDs (safe-completion internal readouts; abliteration dose curves), which are bounded searches, not proofs of absence. **What would change these verdicts:** for X6, any paper reporting a harm-concept knowing-versus-steering cosine across checkpoints, or a differentiated per-model version of DSH's axis cosine; for X1, any per-model scalarisation of a depth profile used to rank models; for the safe-completion NOT-FOUND, a single internal readout on a safe-completion-trained model; for X2/X10, nothing — they are closed.

**Self-verification: 105 of 105 quote-grade passages passed an independent live re-fetch of their own URL. One quote was deleted as a composite (logged, substantive claim unaffected); eight numbers recovered beyond the ~50 KB page-fetch truncation horizon are kept separately as anchors; three zero-match regexes used as absence evidence are kept separately again and were each independently reproduced. Spend: $0.00.**


## Sources

[1] [Large Language Models Generate Harmful Responses Using a Distinct Mechanism, Shared Across Harm Types](https://arxiv.org/html/2604.09544) (Hadas Orgad, Boyi Wei, Kaden Zheng, Martin Wattenberg, Peter Henderson, Seraphina Goldfarb-Tarrant, Yonatan Belinkov; 2026) — THE most important adverse prior found. Publishes the recognition-vs-execution dissociation on harm at the parameter level, a double dissociation between harm generation and refusal, and a separability-vs-alignment ladder over OLMo3-7B. Iteration 1 mis-filed it as a pruning-only paper.

> We further show that harmful response generation is dissociable from the ability to recognize and reason about harmfulness.

Locator: Abstract

> Crucially, the identified parameters support the generation of harmful responses, not the underlying knowledge: pruned models can still recognize harmful requests, refuse, and explain their risks, dissociating generation from harmfulness recognition and reasoning.

Locator: Section 1 (Introduction)

> concentrating harmful-response dependence onto a smaller and more separable set of parameters—a phenomenon we call mechanistic compression.

Locator: Section 1 (Introduction)

> Across the OLMo3-7B checkpoint sequence (base → mid-train → long-context → SFT → DPO → RL), separability emerges gradually with alignment training, especially after preference optimization.

Locator: Section 3.3 / Figure 4 caption

> pruning approximately 0.0005%–0.001% of total parameters substantially reduces the model’s ability to comply with harmful requests under jailbreaks, while largely preserving performance on general-purpose benchmarks.

Locator: Section 3.1

> Our main experiments are performed on Llama3.1-8B-Instruct (Grattafiori et al., 2024), Qwen2.5-14B-Instruct and Qwen2.5-32B-Instruct (Yang et al., 2025), and we expand this set when a deeper analysis is required.

Locator: Section 2.2 (Models)

> Metrics are StrongREJECT score (generation), refusal rate (keyword-based), LLM-judged (explanation), and accuracy on harmful/benign pairs (detection). (b) Harm generation and Refusal are double-dissociated.

Locator: Section 4 / Figure 5 caption

> We also observe a symmetric relationship between response-generation and refusal: impairing one leaves the other intact, indicating a double dissociation

Locator: Section 4

> Lastly, these results provide insight rather than a deployable defense: practical applications would require scaling beyond the models tested here

Locator: Section 7 (Discussion)

[2] [Knowing without Acting: The Disentangled Geometry of Safety Mechanisms in Large Language Models](https://arxiv.org/abs/2603.05773) (Jinman Wu, Yi Xie, Shen Lin, Shiqian Zhao, Xiaofeng Chen; 2026) — Names this iteration's two axes outright - Recognition Axis v_H ('Knowing') and Execution Axis v_R ('Acting') - and demonstrates a causal double dissociation on harm, with a layer-wise cosine between them. Tests no abliterated checkpoint. Framed as an attack paper (cs.CR), which the run's invariant forbids inheriting.

> Safety alignment is often conceptualized as a monolithic process wherein harmfulness detection automatically triggers refusal. However, the persistence of jailbreak attacks suggests a fundamental mechanistic decoupling.

Locator: Abstract

> positing that safety computation operates on two distinct subspaces

Locator: Abstract

> Our geometric analysis reveals a universal ``Reflex-to-Dissociation'' evolution, where these signals transition from antagonistic entanglement in early layers to structural independence in deep layers.

Locator: Abstract

> we demonstrate a causal double dissociation, effectively creating a state of ``Knowing without Acting.''

Locator: Abstract

> which achieves State-of-the-Art attack success rates by surgically lobotomizing the refusal mechanism

Locator: Abstract

[3] [Perfect Detection, Failed Control: The Geometry of Knowing vs. Steering in Language Models](https://arxiv.org/html/2606.24952) (Cosimo Galeone, Anna Ettorre, Minsu Park, Giuseppe Ettorre, Daniele Ligorio; 2026) — Publishes a per-checkpoint, weight-computable detection-vs-control cosine table over four models (0.12/0.20/0.16/0.13) and an instruction-tuning invariance (0.1197 vs 0.1200), on hallucination and output format rather than harm - plus the explicit negative result that the angle does not predict steerability. Grep for abliterat|uncensor: 0 matches.

> The gap generalizes. Across four models from three families and two scales (1B–9B),

Locator: Abstract

> What the cosine _is_ is a robust, weight-computable signature of the dissociation, invariant across four models — not a predictor of how steerable a behavior is.

Locator: Abstract

> a 15∘ rotation from the detection direction toward the intervention direction partially bridges the gap — 73% and 60% refusal on two held-out entity categories, at 1.8% false positives (N=115).

Locator: Abstract

> the intervention (refusal) direction is hand-picked from lm_head alone

Locator: Section 2.2

[4] [N-GLARE (ACL 2026 Long 1334): N-GLARE: An Non-Generative Latent Representation-Efficient LLM Safety Evaluator](https://aclanthology.org/2026.acl-long.1334.pdf) (Zheyu Lin, Jirui Yang, Yukui Qiu, Hengqi Guo, Yubing Bao, Yao Guan; 2025) — The deliverable-level incumbent. Its illustrative example is EXACTLY this run's panel - base, RL-aligned and safety-removed Qwen3-4B. Needs four constructed dialogue families per model, so it is not a few-prompt method. Eq. 9 gives JR Min/Max. No numeric Kendall tau is printed anywhere; still no code as of 2026-09-21.

> A higher value of JR Min/Max indicates that
> Jailbreak–Ideal Refusal separability remains stable
> across the entire trajectory

Locator: Section 3.5 / Eq. (9)

> when com-
> paring multiple variants of the same base model
> (e.g., RL-aligned, base, and safety-removed ver-
> sions of Qwen3-4B), we observe that better-aligned
> variants exhibit more pronounced geometric sepa-
> ration between different trajectories in latent space.

Locator: Section 1 (Introduction)

> remains consistently high, with p-values far be-
> low conventional significance thresholds

Locator: Section 4 (Results)

> benign (B), jailbreak (J), plainquery (P)

Locator: Section 2 (Method overview)

[5] [The Geometry of Harmful Intent: Training-Free Anomaly Detection via Angular Deviation in LLM Residual Streams](https://arxiv.org/html/2603.27412) (Isaac Llorente-Saguer; 2026) — One of the two papers that already publish the recognition-invariance headline: abliterated variants detect harm within 0.015 AUROC of their instruction-tuned parents, on Qwen3.5-0.8B and Qwen2.5-0.5B triplets. Crucially it measures NOTHING on the execution side (full-document grep, 9 matches, none a quantity).

> First, geometry survives refusal ablation: both abliterated variants achieve AUROC at most 0.015 below their instruction-tuned counterparts, establishing a geometric dissociation between harmful-intent representation and the downstream generative refusal mechanism.

Locator: Abstract

> We evaluate two complete model triplets from the Qwen3.5-0.8B and Qwen2.5-0.5B families: base, instruction-tuned, and _abliterated_ (refusal direction surgically removed via orthogonalisation).

Locator: Abstract

> The model’s internal encoding of harmful semantic intent is geometrically distinct from the circuits that generate refusal text. Harm recognition and refusal generation are separable mechanisms.

Locator: Section 1 (Introduction)

> LatentBiopsy builds a normative reference exclusively from 200 safe activations and scores every prompt by the negative log-likelihood of its angular deviation

Locator: Contributions (1)

> Our findings suggest that such interventions address the generative mechanism without altering the representational geometry; the latent signal persists even when the direction has been mathematically erased.

Locator: Section 8 (Discussion)

[6] [Harmful Intent as a Geometrically Recoverable Feature of LLM Residual Streams](https://arxiv.org/html/2604.18901) (Isaac Llorente-Saguer; 2026) — The second scooping paper, absent from the current draft's reference list. Abliterated variants match their instruction-tuned counterparts within +/-0.003 AUROC across 12 models. Confirms iteration 1's four-quantity reading of the repeated 0.003 and 73 figures. Supplies the low-FPR reporting argument and the 100-labelled-examples budget.

> matches its instruction-tuned counterpart within ±0.003\pm 0.003 AUROC in abliterated variants from which the refusal mechanism has been removed.

Locator: Abstract

> their TPR@1%FPR varies by more than ten times the AUROC gap; a deployed 9B safety classifier shows the same pattern at AUROC 0.94 and TPR 0.30, motivating low-FPR reporting as a default in safety-adjacent detection evaluation.

Locator: Abstract

> two pooling choices applied to the same chat-templated activations at the same residual-stream layer (max-pool over content tokens versus last-token at the post-instruction position) recover harm directions 73

Locator: Abstract

> Gemma-3 is the exception: alignment rotates the harm direction by 73

Locator: Section 3.2

> Abliterated variants are community-produced via the weight-orthogonalisation procedure of Arditi et al. (2024) and sourced from HuggingFace under the huihui-ai organisation.

Locator: Section 2.1

> A mean-difference direction fitted from 100 examples per class achieves mean effective AUROC 0.9820.982 across 12 models

Locator: Section 1 (Contributions 1)

> Across all four families, instruct-to-abliterated transfer is substantially cleaner than base-to-instruct

Locator: Section 3.2

> The recovered direction is also nearly orthogonal to the leading principal component of benign-prompt activations

Locator: Section 1, Contributions (3)

[7] [Jorak Model Scanner (modelscanner) - reference-free detection of abliteration in open-source LLMs](https://github.com/JolanMc/Jorak) — NON-PEER-REVIEWED shipped open-source tool, verified live 2026-09-21. CLOSES BOTH X2 and X10: its 'suppression' signal is the normalised ||r^T W|| over o_proj/down_proj with r fitted from the candidate's OWN activations, and its Plan-1 A/B/S signals are a weights-only, zero-inference SVD subspace-alignment scar test. Validated 4/4 on a Qwen2.5-0.5B-derived matrix.

> **Reference-free** detection of **abliteration** in open-source LLMs — determining whether a model has been "uncensored" through directional ablation (Arditi et al. 2024 ; Heretic / Reaper / mlabonne) **without access to the original model**.

Locator: README.md, top of file

> Detector **complete and validated** on a real matrix of 4 models derived from `Qwen2.5-0.5B` — **accuracy 4/4**

Locator: README.md, Status (v0.1.0)

[8] [Jorak docs/METRICS.md - metric definitions and calibration](https://raw.githubusercontent.com/JolanMc/Jorak/main/docs/METRICS.md) — NON-PEER-REVIEWED. Gives the exact formulae and calibrated thresholds: suppression = ||r^T W||/(||r||*||W||_F) with censored ~0.038 vs abliterated ~2e-8; global alignment A = sigma_1(U)/||U||_F with Qwen3-8B base A=0.184 vs Josiefied-Qwen3-8B-abliterated-v1 A=0.705; and a bottom-k subspace alignment S built for multi-direction ablations.

> `suppression_ℓ = ‖r̂ᵀW‖ / (‖r̂‖·‖W‖_F)` pour `W ∈ {o_proj, down_proj}`, par couche.

Locator: docs/METRICS.md, Plan 1 metric table

> Calibration mesurée : censuré ≈ `0.038` vs abliteré ≈ `2e-8`. Le seuil `≤ 1e-2` les sépare nettement (0.038 > 0.01 > 2e-8).

Locator: docs/METRICS.md, suppression calibration

> C'est **le cœur** du projet (« la technique mise en avant »). NumPy pur, sans inférence.

Locator: docs/METRICS.md, Section 1 (Plan 1 - JORAK)

> Pour chaque couche, on prend `u_min` = le vecteur singulier gauche de **plus petite** valeur singulière de `W` (la direction « la moins écrite »). On empile les `u_min` en `U ∈ ℝ^{n×d_model}`, puis **A = σ₁(U) / ‖U‖_F**

Locator: docs/METRICS.md, Section 1.1 svd_alignment

> **Qwen/Qwen3-8B (base, censuré)** : `A = 0.184` ≈ le plancher 0.167 → `u_min` dispersés, **aucune** direction partagée → poids intacts.

Locator: docs/METRICS.md, Section 1.1 worked values

> **Josiefied-Qwen3-8B-abliterated-v1** : `A = 0.705` → forte direction commune → poids sectionnés.

Locator: docs/METRICS.md, Section 1.1 worked values

> Gabliteration) retirent un **sous-espace de k directions** (`n_directions ≈ 4`), pas une seule.

Locator: docs/METRICS.md, Section 1.3 subspace_alignment

> On agrège les projecteurs `M = Σ_ℓ B_ℓ B_ℓᵀ`, puis **S = (somme des k plus grandes valeurs propres de M) / (n·k)**.

Locator: docs/METRICS.md, Section 1.3 subspace_alignment

> L'idée-clé **reference-free** : on n'a pas besoin de générer ni de comparer à un original pour séparer *censuré* de *ablated*

Locator: docs/METRICS.md, reference-free rationale

[9] [Has This Checkpoint Been Abliterated? A Two-Signal Audit and Its Failure Map](https://arxiv.org/abs/2607.01854) (Gabriel Hurtado; 2026) — The 273-checkpoint abliteration audit. THE DECIDING QUESTION IS ANSWERED: it is REFERENCE-ANCHORED on both signals - the activation refusal-gap fits directions on the base model, and the weight-recovery energy is computed on Delta W = W_base - W_candidate. AUROC 0.95 combined; 57 abliterations vs 37 benign negatives. It does NOT close X2 or X10.

> We combine two cheap internal signals, a reference-anchored activation refusal-gap and a weight-recovery energy of the base-to-candidate weight difference, into a threshold-free checkpoint audit.

Locator: Abstract

> The audit is effective triage, not tamper-proofing: it presumes an attested reference, and its claims are bounded by the registry we evaluate it on.

Locator: Abstract

> a spoofed reference evades both axes with no training

Locator: Abstract

[10] [From Refusal Geometry to Safety Geometry: Harmfulness--Refusal Coupling under Dynamic Adversarial Fine-Tuning](https://arxiv.org/html/2606.16349) (Wenhao Lan, Shan Li, Xinhua Lai, Meiqi Wu, Junbin Yang, Haihua Shen; 2026) — Baseline G10 and a headline adverse prior. Eq. 9 defines HRCI_repr = 1/2 C_cos + 1/2 C_sub; the authors state plainly that low coupling is not itself a safety score. Eq. 8's subspace dimension k is NEVER stated - only Table 1's three printed principal angles imply k=3 - so G10 is not reimplementable exactly as specified.

> SFT supplies the negative control: its direct-coupling change is much smaller, and it remains high-ASR, so low coupling is not itself a safety score.

Locator: Abstract

> drops from 0.0784 at step 50 to 0.0205 at step 500, while fixed-source attack success rate (ASR) rises from 0 to 0.25, XSTest refusal falls from 1.00 to 0.228, and benign helpfulness recovers from 0 to 1.12 on a 0–2 scale.

Locator: Abstract

> For subspaces, let

Locator: Section 3.3, Eq. (8)

> Principal angles | 86.1, 88.7, 89.4 | 82.3, 88.1, 89.7

Locator: Section 4.1, Table 1

> It was not optimized against ASR, refusal, or utility outcomes

Locator: Section 3.3 after Eq. (9)

[11] [Item Response Theory for AI Safety](https://arxiv.org/abs/2608.05086) (Joshua Fonseca Rivera, Neil Shah, David Demitri Africa, Konstantinos Voudouris; 2026) — The few-prompts incumbent that must be conceded by name: roughly ten adaptive items recover several individual benchmarks at 97-99% cost reduction, fit over 8 benchmarks and 192 models. Text-only, hence a baseline under the run's invariant, but it owns the few-prompt regime.

> roughly ten adaptively chosen items suffice for several individual benchmarks, cutting evaluation cost by 97-99%

Locator: Abstract

> We fit IRT models to eight safety benchmarks across 192 language models, the largest psychometric analysis of LLM safety evaluations to date

Locator: Abstract

> three interpretable factors of refusal strictness, truthfulness, and contextual harm explain most of the variance between models across benchmarks

Locator: Abstract

[12] [Interpretability without actionability: mechanistic methods cannot correct language model errors despite near-perfect internal representations](https://arxiv.org/html/2603.18353) (Sanjay Basu, Sadiq Y. Patel, Parth Sheth, Bhairavi Muralidharan, Namrata Elamaran, Aakriti Kinra, John Morgan, Rajaie Batniji; 2026) — The knowledge-action gap paper. 98.2% probe AUROC vs 45% output sensitivity, a 53-point gap, across four intervention arms. CORRECTS the hypothesis text: 'zero corrections and zero disruptions' is true of the SAE arm only; Arm 1 corrected 17/85 and disrupted 25/47 (that is the random-indistinguishable arm), and TSV corrected 19/79 while disrupting 4/65.

> At baseline, Steerling-8B detected 51 of 144 hazards (35% sensitivity) and Qwen 2.5 7B detected 65 of 144 (45%).

Locator: Abstract (Findings)

> Linear probes trained on Qwen’s internal representations discriminated hazardous from benign cases with 98.2% AUROC (95% CI 0.968 to 0.993), demonstrating a 53-percentage-point gap between internal knowledge and output behaviour.

Locator: Abstract (Findings)

> Concept bottleneck steering corrected 17 of 85 missed hazards (20%) but disrupted 25 of 47 correct detections (53%), indistinguishable from random perturbation

Locator: Abstract (Findings)

> SAE feature steering produced zero corrections and zero disruptions despite identifying 3,695 significant hazard-associated features. TSV steering at high strength corrected 19 of 79 missed hazards (24%) while disrupting 4 of 65 correct detections (6%), but left 76% of errors uncorrected.

Locator: Abstract (Findings)

> for correcting false-negative triage errors using 400 physician-adjudicated clinical vignettes (144 hazards, 256 benign)

Locator: Abstract (Methods)

> Hazard-feature steering at

Locator: Section 3.4

[13] [Breaking Refusal in the First Half: A Mechanistic Study of the Prefill Jailbreak](https://arxiv.org/html/2607.14147v1) (Alex Kwon; 2026) — Defines the exact X5 statistic - concentration = delta p_refuse / (-delta p_comply) - but computes it only as a knockout-conditioned paired contrast between one instruct checkpoint and its base anchor (Qwen2.5-1.5B, n=60), never as a parent-free per-checkpoint score. Instruct routes ~8x more freed mass to refusal than base (0.24 vs 0.03).

> the instruct model routes it to refusal tokens about 8

Locator: Section 4.3

[14] [Logit-Gap Steering: A Forward-Pass Diagnostic for Alignment Robustness](https://arxiv.org/abs/2506.24056) (Tung-Ling Li, Hongliang Liu; 2025) — X3's nearest relative: a per-prompt refusal-minus-affirmative logit GAP at the first decoding step, over pre-identified lexical refusal and affirmative tokens. Not an analytic slope with respect to a continuous harm projection, and undefined for a safe-completion model with no lexical refusal token.

> We introduce the refusal-affirmation logit gap: the difference between the top refusal-token logit and the top affirmative-token logit at the first decoding step. This single scalar quantifies the per-prompt safety margin that alignment provides.

Locator: Abstract

[15] [Sparse Readout Prism: Explaining Logit-Lens Scores in Features Instead of Tokens](https://arxiv.org/abs/2609.01936) (Matteo He, William F. Shen, Xinchi Qiu, Nicholas D. Lane; 2026) — Decomposes the readout using only its weights and expresses any token logit or logit difference as a sum of sparse-feature contributions - structurally close to X3. CORRECTION to the planning seed: its abstract contains no mention of safety, refusal or harm; the safety-audit application appears only in Section 6 Future Work and is proposed, not executed.

> we introduce Sparse Readout Prism (SRP), which decomposes the readout using only its weights and expresses any token logit or logit difference as a sum of contributions from sparse readout features.

Locator: Abstract

[16] [Geometry-Lite: Interpretable Safety Probing via Layer-Wise Margin Geometry](https://arxiv.org/abs/2605.20241) (Woo Seob Sim, Yu Rang Park; 2026) — X1's runner-up. Summarises layer-wise margin profiles by boundary position, layer-to-layer change and coarse shape, across nine instruction-tuned backbones and seven benchmarks - but per prompt, then pooled into detection AUROC, never as a per-model number used to rank checkpoints.

> then summarizes the resulting margin profiles by boundary position, layer-to-layer change, and coarse shape. Across nine instruction-tuned backbones

Locator: Abstract

[17] [Harmfulness Propagation Dynamics: Layer-wise Trajectories of Adversarial Intent in Large Language Models](https://arxiv.org/abs/2609.13534) (Noor Islam S. Mohammad, Uluğ Bayazıt; 2026) — X1's single nearest work: extracts slope, curvature, monotonicity and onset layer from the cross-layer harm projection sequence - almost exactly X1's operations - but as a seven-dimensional PER-INSTANCE feature record fed to a 288-parameter MLP input moderator, not a per-checkpoint score.

> This lightweight input moderator extracts a seven-dimensional feature record, slope, curvature, monotonicity, onset layer, and related statistics from the cross-layer projection sequence and classifies it with a 288-parameter MLP.

Locator: abstract

[18] [Encoded Early, Used Late: Where Transformers Begin to Act on an Inferred Partner's Expertise](https://arxiv.org/abs/2609.07139) (Mika Okamoto, Gabriele Sarti; 2026) — X8's single nearest work: decodability peaks early and falls to near chance before the midpoint while causal efficacy arrives late - the readable-before-usable depth lag - but on inferred partner expertise, one model, a synthetic corpus, and with no numeric per-model lag.

> partner expertise is most decodable in the early layers and falls to near chance before the midpoint of the network.

Locator: Abstract

> An inferred relational attribute is therefore represented well before it becomes causally active

Locator: Abstract

> We use one model on a synthetic corpus as an initial demonstration.

Locator: Abstract

[19] [Lagged Coupling: Internal Representations Become Readable Before They Become Causal](https://arxiv.org/abs/2609.01048) (Xining Xun; 2026) — A strong general adverse prior on any read-vs-act construct: across the Pythia suite a probe reads the target from step 1,000 at every scale, yet steering along that same direction is null-equivalent in 43 of 48 model-checkpoint cells. Note its axis is TRAINING STEP, not depth, so it does not close X8.

> Across the full Pythia suite (160M-12B, eight checkpoints, four task families), a linear probe can read a target variable from the residual stream as early as step 1,000 at every scale -- yet steering along that same reading direction remains null-equivalent in 43 of 48 model-checkpoint cells.

Locator: abstract

[20] [Encoded but Not Actionable: Auditing the Decode-Generate-Steer Gap in Frozen LLMs for Geometric Constraints](https://arxiv.org/abs/2608.17843) (Man Liang, Xinzhao Cheng, Faizan Wajid; 2026) — Multi-backbone decode-generate-steer gap on geometric constraints: decodable information is not always actionable. Off-concept, and a full-document grep confirms it never quantifies the depth lag numerically (0 matches for onset layer / depth-fraction / layers apart / layer gap).

> Further analyses show that decodable information is not always actionable. Generation often fails to express this information, and on the two intervention-tested backbones, activation-restoration effects at the patched entity position vanish while decodability persists across depth.

Locator: abstract

[21] [Before the Last Token: Diagnosing Final-Token Safety Probe Failures](https://arxiv.org/abs/2605.12726) (Shravan Doda; 2026) — The adverse prior constraining how the run may describe r_ablit, which is fitted at the last prompt token: last-token probes keep high recall on clean harmful prompts but miss many jailbreaks and false-positive on safety-adjacent benign prompts. ICML 2026 Mechanistic Interpretability Workshop.

> Token-level prefill analyses reveal that probe-visible unsafe evidence often appears earlier in the sequence but is not exposed at the final-token readout, while naive max-pooling over token positions overfires on safe prompts.

Locator: Abstract

[22] [Comparative Analysis of LLM Abliteration Methods: A Cross-Architecture Evaluation](https://arxiv.org/abs/2512.13655) (Richard J. Young; 2025) — Target 5. The planner's attributed figures (a 'minimum effective dose' at >=30% refusal bypass, MMLU max degradation 0.028) are NOT PRINTED - confirmed absent across all three retrieval rungs. What it actually reports is a four-TOOL comparison over 16 models with no intensity sweep and no dose axis.

> Single-pass methods demonstrated superior capability preservation on the benchmarked subset (avg GSM8K change across three models: ErisForge -0.28 pp; DECCP -0.13 pp), while Bayesian-optimized abliteration produced variable distribution shift (KL divergence: 0.043-1.646)

Locator: Abstract

[23] [Abliteration Is Not a Scalpel: Off-Target Effects of Refusal Removal on Decision Disposition Across Model Families](https://arxiv.org/abs/2607.17427) (Aleksander Fafuła; 2026) — Preregistered off-target study of abliteration with exactly two arms per family (base vs abliterated; Gemma-4-26B-A4B-it and Qwen3-30B-A3B), 21,600 decisions. Not a dose curve. Also documents two toolchain contamination channels in community-modified checkpoints.

> abliterated models are systematically more optimistic (+12.2 pp Gemma, +7.4 pp Qwen; the confirmed preregistered endpoint), justify themselves at greater length, and use fewer explicit uncertainty words in forced self-critiques

Locator: Abstract

[24] [An Embarrassingly Simple Defense Against LLM Abliteration Attacks](https://arxiv.org/abs/2505.19056) (Harethah Abu Shairah, Hasan Abed Al Kader Hammoud, Bernard Ghanem, George Turkiyyah; 2025) — The extended-refusal defence: refusal rates drop by at most 10% under abliteration versus 70-80% in baseline models. Compares defended vs undefended models, not abliteration strengths, so it is not the dose curve either.

> refusal rates drop by at most 10%, compared to 70-80% drops in baseline models

Locator: Abstract

[25] [Measuring and Eliminating Refusals in Military Large Language Models](https://arxiv.org/abs/2603.10012) (Jack FitzGerald, Dylan Bates, Aristotelis Lazaridis, Aman Sharma, Vincent Lu, Brian King, Yousif Azami, Sean Bailey, Jeremy Cao, Peter Damianov, Kevin de Haan, Joseph Madigan, Jeremy McLaurin, Luke Kerbs, Jonathan Tainer, Dave Anderson, Jonathan Beck, Jamie Cuticello, Colton Malkerson, Tyler Saltsman; 2026) — Applies Heretic once to a military-tuned gpt-oss-20b: +66.5 points absolute answer rate, -2% average relative on other military tasks. A single abliteration operating point, not a graded curve.

> showing an absolute increase in answer rate of 66.5 points but an average relative decrease of 2% on other military tasks

Locator: Abstract

[26] [One Pass to Break Them All: Empirical Analysis of Activation-Space Abliteration on LLM Safety Alignment (Alice Research)](https://go.alice.io/hubfs/alice-abliteration-report-april2026.pdf) (2026) — NON-PEER-REVIEWED industry report, March 2026. Reports baseline vs post-abliteration only (five safety-trained models, 94.2% -> 98.0% compliance over 550 prompts) - again no dose axis - and independently states that safety training succeeded at harm detection but failed at harm refusal, calling them separable functions.

> training succeeded at harm detection but failed at harm refusal. These
> appear to be separable functions.

Locator: Section 5.1

[27] [The Safety Relay in Roleplay Jailbreaks: A Component-Resolved Causal Analysis of Harm Recognition and Refusal](https://arxiv.org/abs/2608.30585) (Md Mokarram Chowdhury, Ernie Chang, Yang Li; 2026) — A fourth independent statement of the same pattern, from the roleplay-jailbreak side: successful attacks retain the harmful-vs-benign distinction at the request while its refusal-associated expression weakens where the answer begins - 'safety-relay attenuation'. Matched harmful/benign x wrapper design confirmed; per-condition numeric tables not extracted within budget.

> Successful attacks retain the measured harmful-versus-benign distinction at the request, while its refusal-associated expression weakens where the answer begins, a pattern we call safety-relay attenuation.

Locator: Abstract

[28] [Calibrating Interpretability Instruments Before Trusting Their Verdicts](https://arxiv.org/abs/2609.14754) (Orion Reblitz-Richardson; 2026) — CLOSES iteration 1's follow-up (d): the companion methods note DOES have a standalone arXiv id. Directly relevant to this run's null-band and instrument-integrity machinery. Code at github.com/deepsteer/deepsteer.

> Calibrating Interpretability Instruments Before Trusting Their Verdicts

Locator: arXiv listing

[29] [From Hard Refusals to Safe-Completions: Toward Output-Centric Safety Training](https://arxiv.org/abs/2508.09224) (Yuan Yuan, Tina Sriskandarajah, Anna-Luisa Brakman, Alec Helyar, Alex Beutel, Andrea Vallone, Saachi Jain; 2025) — OpenAI's own safe-completions paper, incorporated into GPT-5. Evaluated entirely at the output level - production comparisons and internally controlled experiments - with no internal activation, probe or logit-lens readout. Supports the clean NOT-FOUND on internally scoring a safe-completion model.

> We incorporated this approach into GPT-5 and find that across both production comparisons and internally controlled experiments, safe-completion training improves safety (especially on dual-use prompts), reduces the severity of residual safety failures, and substantially increases model helpfulness.

[30] [OpenSafeIntent: Evaluating Intent-Calibrated Safe Completion Across Dual-Use Prompt Sets](https://arxiv.org/abs/2607.02047) (Rheeya Uppaal, Seungwoo Lyu, Selina Sung, Junjie Hu; 2026) — The follow-on safe-completion evaluation, again purely behavioural: it recommends evaluating safe completion as intent-calibrated behaviour over controlled task variants. Second primary source behind the NOT-FOUND for an internal safe-completion readout.

> Our results suggest that safe completion should be evaluated as intent-calibrated behavior over controlled task variants, not as a single safety-helpfulness tradeoff over independent prompts.

[31] [HARC: HARC: Coupling Harmfulness and Refusal Directions for Robust Safety Alignment](https://arxiv.org/html/2607.00572v1) (Shei Pern Chua, Hao Wu, Qianli Ma, Fangzhao Wu; 2026) — Appendix A.3's cross-layer projection profiles - the exact object X1 ratios over - are reported as heat-map FIGURES only and are never reduced to a per-model scalar, which is why X1 survives as PARTIAL. HARC's one per-model scalar is a single-layer v_harm/v_ref coupling, a different quantity.

[32] [Refusal in Language Models Is Mediated by a Single Direction](https://arxiv.org/abs/2406.11717) (Andy Arditi, Oscar Obeso, Aaquib Syed, Daniel Paleka, Nina Panickssery, Wes Gurnee, Neel Nanda; 2024) — The foundational refusal-direction paper, with its full seven-author list recovered and its NeurIPS 2024 venue cross-checked against the proceedings PDF. CORRECTION to a planning seed: it does not logit-lens the refusal direction to show it decodes to refusal words; unembedding directions appear only as an exclusion filter in its direction-selection procedure.

> In this work, we show that refusal is mediated by a one-dimensional subspace, across 13 popular open-source chat models up to 72B parameters in size.

Locator: Abstract

[33] [Refusal in Language Models Is Mediated by a Single Direction (NeurIPS 2024 proceedings PDF)](https://proceedings.neurips.cc/paper_files/paper/2024/file/f545448535dfde4f9786555403ab7c49-Paper-Conference.pdf) (Andy Arditi, Oscar Obeso, Aaquib Syed, Daniel Paleka, Nina Panickssery, Wes Gurnee, Neel Nanda; 2024) — Venue cross-check for the bibliography correction: the proceedings first page carries the same seven authors with affiliations (Independent, ETH Zurich, University of Maryland, ETH Zurich, Anthropic, MIT).

[34] [LLMs Encode Harmfulness and Refusal Separately](https://arxiv.org/abs/2507.11878) (Jiachen Zhao, Jing Huang, Zhengxuan Wu, David Bau, Weiyan Shi; 2025) — The correct citation for the harmfulness/refusal split, currently cited in the draft with no authors. Full author list recovered.

[35] [The Geometry of Refusal in Large Language Models: Concept Cones and Representational Independence](https://arxiv.org/abs/2502.17420) (Tom Wollschläger, Jannes Elstner, Simon Geisler, Vincent Cohen-Addad, Stephan Günnemann, Johannes Gasteiger; 2025) — Bibliography correction: full six-author list recovered with correct diacritics (Wollschlaeger, Guennemann). Part of the abliteration-dimensionality line predicting that a rank-one scar is incomplete - a prediction Jorak's bottom-k subspace signal already acts on.

[36] [Refusal in LLMs is an Affine Function](https://arxiv.org/abs/2411.09003) (Thomas Marshall, Adam Scherlis, Nora Belrose; 2024) — Bibliography entry confirmed correct as printed. Part of the affine/multi-dimensional refusal line.

[37] [Refusal Reads Only a Slice of What the Model Knows: Harm-Keyed Routing and Its Exceptions Across Model Families](https://arxiv.org/abs/2609.14759) (Orion Reblitz-Richardson; 2026) — The closest thing to a cross-model routing statistic, but a different construct: a subspace-RANK causal-transfer share (76% of refusal's causal input outside the rank-16 moral basis), reported for one model (OLMo-3) only, with the other families described qualitatively.

> The central result is causal and comes from one model, OLMo-3.

Locator: Abstract

> about three-quarters of refusal's causal input lies outside the moral subspace altogether.

Locator: Abstract

> The picture is not uniform across families. Llama reads broad moral content; Qwen reads beyond the single harm cue but is unresolved at our sample size; GPT-OSS reads harm, and its refusals can be argued in either direction by its own reasoning trace.

Locator: Abstract

[38] [Detecting Safety Training Modification in Language Models via Activation Analysis](https://arxiv.org/abs/2608.05578) (Glen Messenger; 2026) — Checked as a possible X2 closer. Scores activation geometry for safety-training modification but carries no weight-side companion signal that would close the weight-space write-mass lane.

[39] [DrExe/qwen3-safety-vectors (HuggingFace)](https://huggingface.co/DrExe/qwen3-safety-vectors) — Checked per the plan. Returns HTTP 401 on both the model page and the api/models endpoint as of 2026-09-21, i.e. gated or private. Existence and contents could not be confirmed from an unauthenticated fetch, so nothing about it should be asserted.

[40] [ORBA: Orthogonal Reflection Bounded Ablation](https://huggingface.co/blog/grimjim/orthogonal-reflection-bounded-ablation) (2026) — NON-PEER-REVIEWED community post. A method for PERFORMING bounded directional ablation, not a detection metric; supplies the geometric background for why rank-one weight interventions leave a detectable scar but does not itself close X2 or X10.

[41] [Knowing without Acting: The Disentangled Geometry of Safety Mechanisms in Large Language Models (full text)](https://arxiv.org/html/2603.05773v2) (Jinman Wu, Yi Xie, Shen Lin, Shiqian Zhao, Xiaofeng Chen; 2026) — Full text of DSH. Establishes that its Recognition/Execution cosine is reported as a UNIVERSAL 'Reflex-to-Dissociation' pattern converging to a random-vector baseline in deep layers for every model, not as a differentiated per-checkpoint score - which is why X6 survives as PARTIAL rather than CLOSED. Its panel is three aligned models; a full-document grep for abliterat|uncensor returns 0 matches.

> The dashed line and grey band represent the mean and 95% confidence interval of 1000 random vector pairs, respectively. In deep layers, the safety axes’ similarity converges to this random baseline, confirming the “Reflex-to-Dissociation” pattern.

Locator: Section 4, Figure 4 caption

> Models. We evaluate three aligned models spanning distinct architectural lineages: Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.2, and Qwen2.5-7B-Instruct.

Locator: Section 3 (Models)

## Verification

Numbered citations resolve to unique listed sources. Passage checks test text occurrence, not claim truth or entailment. Author/year metadata and locators are not independently verified. Details: `research_verification.json`.

- Source [1]: text found — We further show that harmful response generation is dissociable from the ability to recognize and re
- Source [1]: text found — Crucially, the identified parameters support the generation of harmful responses, not the underlying
- Source [1]: text found — concentrating harmful-response dependence onto a smaller and more separable set of parameters—a phen
- Source [1]: text found — Across the OLMo3-7B checkpoint sequence (base → mid-train → long-context → SFT → DPO → RL), separabi
- Source [1]: text found — pruning approximately 0.0005%–0.001% of total parameters substantially reduces the model’s ability t
- Source [1]: text found — Our main experiments are performed on Llama3.1-8B-Instruct (Grattafiori et al., 2024), Qwen2.5-14B-I
- Source [1]: text found — Metrics are StrongREJECT score (generation), refusal rate (keyword-based), LLM-judged (explanation),
- Source [1]: text found — We also observe a symmetric relationship between response-generation and refusal: impairing one leav
- Source [1]: text found — Lastly, these results provide insight rather than a deployable defense: practical applications would
- Source [2]: text found — Safety alignment is often conceptualized as a monolithic process wherein harmfulness detection autom
- Source [2]: text found — positing that safety computation operates on two distinct subspaces
- Source [2]: text found — Our geometric analysis reveals a universal ``Reflex-to-Dissociation'' evolution, where these signals
- Source [2]: text found — we demonstrate a causal double dissociation, effectively creating a state of ``Knowing without Actin
- Source [2]: text found — which achieves State-of-the-Art attack success rates by surgically lobotomizing the refusal mechanis
- Source [3]: text found — The gap generalizes. Across four models from three families and two scales (1B–9B),
- Source [3]: text found — What the cosine _is_ is a robust, weight-computable signature of the dissociation, invariant across 
- Source [3]: text found — a 15∘ rotation from the detection direction toward the intervention direction partially bridges the 
- Source [3]: text found — the intervention (refusal) direction is hand-picked from lm_head alone
- Source [4]: text found — A higher value of JR Min/Max indicates that
Jailbreak–Ideal Refusal separability remains stable
acro
- Source [4]: text found — when com-
paring multiple variants of the same base model
(e.g., RL-aligned, base, and safety-remove
- Source [4]: text found — remains consistently high, with p-values far be-
low conventional significance thresholds
- Source [4]: text found — benign (B), jailbreak (J), plainquery (P)
- Source [5]: text found — First, geometry survives refusal ablation: both abliterated variants achieve AUROC at most 0.015 bel
- Source [5]: text found — We evaluate two complete model triplets from the Qwen3.5-0.8B and Qwen2.5-0.5B families: base, instr
- Source [5]: text found — The model’s internal encoding of harmful semantic intent is geometrically distinct from the circuits
- Source [5]: text found — LatentBiopsy builds a normative reference exclusively from 200 safe activations and scores every pro
- Source [5]: text found — Our findings suggest that such interventions address the generative mechanism without altering the r
- Source [6]: text found — matches its instruction-tuned counterpart within ±0.003\pm 0.003 AUROC in abliterated variants from 
- Source [6]: text found — their TPR@1%FPR varies by more than ten times the AUROC gap; a deployed 9B safety classifier shows t
- Source [6]: text found — two pooling choices applied to the same chat-templated activations at the same residual-stream layer
- Source [6]: text found — Gemma-3 is the exception: alignment rotates the harm direction by 73
- Source [6]: text found — Abliterated variants are community-produced via the weight-orthogonalisation procedure of Arditi et 
- Source [6]: text found — A mean-difference direction fitted from 100 examples per class achieves mean effective AUROC 0.9820.
- Source [6]: text found — Across all four families, instruct-to-abliterated transfer is substantially cleaner than base-to-ins
- Source [6]: text found — The recovered direction is also nearly orthogonal to the leading principal component of benign-promp
- Source [7]: text found — **Reference-free** detection of **abliteration** in open-source LLMs — determining whether a model h
- Source [7]: text found — Detector **complete and validated** on a real matrix of 4 models derived from `Qwen2.5-0.5B` — **acc
- Source [8]: text found — `suppression_ℓ = ‖r̂ᵀW‖ / (‖r̂‖·‖W‖_F)` pour `W ∈ {o_proj, down_proj}`, par couche.
- Source [8]: text found — Calibration mesurée : censuré ≈ `0.038` vs abliteré ≈ `2e-8`. Le seuil `≤ 1e-2` les sépare nettement
- Source [8]: text found — C'est **le cœur** du projet (« la technique mise en avant »). NumPy pur, sans inférence.
- Source [8]: text found — Pour chaque couche, on prend `u_min` = le vecteur singulier gauche de **plus petite** valeur singuli
- Source [8]: text found — **Qwen/Qwen3-8B (base, censuré)** : `A = 0.184` ≈ le plancher 0.167 → `u_min` dispersés, **aucune** 
- Source [8]: text found — **Josiefied-Qwen3-8B-abliterated-v1** : `A = 0.705` → forte direction commune → poids sectionnés.
- Source [8]: text found — Gabliteration) retirent un **sous-espace de k directions** (`n_directions ≈ 4`), pas une seule.
- Source [8]: text found — On agrège les projecteurs `M = Σ_ℓ B_ℓ B_ℓᵀ`, puis **S = (somme des k plus grandes valeurs propres d
- Source [8]: text found — L'idée-clé **reference-free** : on n'a pas besoin de générer ni de comparer à un original pour sépar
- Source [9]: text found — We combine two cheap internal signals, a reference-anchored activation refusal-gap and a weight-reco
- Source [9]: text found — The audit is effective triage, not tamper-proofing: it presumes an attested reference, and its claim
- Source [9]: text found — a spoofed reference evades both axes with no training
- Source [10]: text found — SFT supplies the negative control: its direct-coupling change is much smaller, and it remains high-A
- Source [10]: text found — drops from 0.0784 at step 50 to 0.0205 at step 500, while fixed-source attack success rate (ASR) ris
- Source [10]: text found — For subspaces, let
- Source [10]: text found — Principal angles | 86.1, 88.7, 89.4 | 82.3, 88.1, 89.7
- Source [10]: text found — It was not optimized against ASR, refusal, or utility outcomes
- Source [11]: text found — roughly ten adaptively chosen items suffice for several individual benchmarks, cutting evaluation co
- Source [11]: text found — We fit IRT models to eight safety benchmarks across 192 language models, the largest psychometric an
- Source [11]: text found — three interpretable factors of refusal strictness, truthfulness, and contextual harm explain most of
- Source [12]: text found — At baseline, Steerling-8B detected 51 of 144 hazards (35% sensitivity) and Qwen 2.5 7B detected 65 o
- Source [12]: text found — Linear probes trained on Qwen’s internal representations discriminated hazardous from benign cases w
- Source [12]: text found — Concept bottleneck steering corrected 17 of 85 missed hazards (20%) but disrupted 25 of 47 correct d
- Source [12]: text found — SAE feature steering produced zero corrections and zero disruptions despite identifying 3,695 signif
- Source [12]: text found — for correcting false-negative triage errors using 400 physician-adjudicated clinical vignettes (144 
- Source [12]: text found — Hazard-feature steering at
- Source [13]: text found — the instruct model routes it to refusal tokens about 8
- Source [14]: text found — We introduce the refusal-affirmation logit gap: the difference between the top refusal-token logit a
- Source [15]: text found — we introduce Sparse Readout Prism (SRP), which decomposes the readout using only its weights and exp
- Source [16]: text found — then summarizes the resulting margin profiles by boundary position, layer-to-layer change, and coars
- Source [17]: text found — This lightweight input moderator extracts a seven-dimensional feature record, slope, curvature, mono
- Source [18]: text found — partner expertise is most decodable in the early layers and falls to near chance before the midpoint
- Source [18]: text found — An inferred relational attribute is therefore represented well before it becomes causally active
- Source [18]: text found — We use one model on a synthetic corpus as an initial demonstration.
- Source [19]: text found — Across the full Pythia suite (160M-12B, eight checkpoints, four task families), a linear probe can r
- Source [20]: text found — Further analyses show that decodable information is not always actionable. Generation often fails to
- Source [21]: text found — Token-level prefill analyses reveal that probe-visible unsafe evidence often appears earlier in the 
- Source [22]: text found — Single-pass methods demonstrated superior capability preservation on the benchmarked subset (avg GSM
- Source [23]: text found — abliterated models are systematically more optimistic (+12.2 pp Gemma, +7.4 pp Qwen; the confirmed p
- Source [24]: text found — refusal rates drop by at most 10%, compared to 70-80% drops in baseline models
- Source [25]: text found — showing an absolute increase in answer rate of 66.5 points but an average relative decrease of 2% on
- Source [26]: text found — training succeeded at harm detection but failed at harm refusal. These
appear to be separable functi
- Source [27]: text found — Successful attacks retain the measured harmful-versus-benign distinction at the request, while its r
- Source [28]: text found — Calibrating Interpretability Instruments Before Trusting Their Verdicts
- Source [29]: text found — We incorporated this approach into GPT-5 and find that across both production comparisons and intern
- Source [30]: text found — Our results suggest that safe completion should be evaluated as intent-calibrated behavior over cont
- Source [32]: text found — In this work, we show that refusal is mediated by a one-dimensional subspace, across 13 popular open
- Source [37]: text found — The central result is causal and comes from one model, OLMo-3.
- Source [37]: text found — about three-quarters of refusal's causal input lies outside the moral subspace altogether.
- Source [37]: text found — The picture is not uniform across families. Llama reads broad moral content; Qwen reads beyond the s
- Source [41]: text found — The dashed line and grey band represent the mean and 95% confidence interval of 1000 random vector p
- Source [41]: text found — Models. We evaluate three aligned models spanning distinct architectural lineages: Llama-3.1-8B-Inst

## Follow-up Questions

- Does the harm-concept knowing-vs-steering cosine actually VARY across the three Qwen3-4B checkpoints, where arXiv:2606.24952's hallucination-concept version is flat (0.1197 base vs 0.1200 instruct, difference 0.0003)? This is the single load-bearing empirical question left: if it is flat too, X6 collapses into a replication of a published invariance and the run must sell a signature rather than a predictor. Closes by measuring it on the harvest, with 2606.24952's four-model table (0.12/0.20/0.16/0.13) as the comparison scale.
- Does arXiv:2603.05773 (DSH) report its Recognition/Execution cosine as a DIFFERENTIATED per-model number anywhere, or only as the universal 'Reflex-to-Dissociation' convergence to a random-vector baseline? Its Figure 1 and Figure 4 show the layer-wise trajectory but its differentiating numbers appear to be behavioural ASR tables. If a per-model cosine table exists in its appendix, X6 drops from PARTIAL to CLOSED and the screen order must change. Closes by a table-aware parse of arxiv.org/html/2603.05773v2 appendices and the anonymous.4open.science/r/DSH release.
- Can arXiv:2604.09544's separability be reduced to a single comparable per-model scalar, and has anyone done it? Their Figure 4 and Figure 14 report utility-harmfulness TRADE-OFF CURVES per checkpoint, not a scalar, and Figure 13 reports only a Pearson r=0.656 between harmfulness reduction and post-pruning refusal increase. If the area under that trade-off curve is a usable per-checkpoint safety scalar, it is both the strongest baseline this run faces and a possible reformulation of X1. Closes by reading Appendices G and H and the B-TAP release for per-checkpoint aggregate numbers.
- Is the Jorak Model Scanner's 4-model validation reproducible at the 273-checkpoint scale of arXiv:2607.01854, and does its parent-free suppression signal survive the recipes that audit's failure map misses? The CLOSED verdicts on X2 and X10 rest on a 17-commit non-peer-reviewed repository validated 4/4 on Qwen2.5-0.5B derivatives. A reviewer may not accept that as prior art. Closes by running Jorak's Plan-1 signals over a public abliteration registry and comparing against the audit's reported AUROC 0.95 and its 4-of-57 misses.

---
*Generated by AI Inventor Pipeline*
