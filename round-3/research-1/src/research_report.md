# Is our depth-and-site safety metric already taken?

## Summary

Web-only saturation pass for iteration 3's widened claim, run 2026-09-21. Cost: $0, no cuts. 87 of 87 quoted passages were re-verified by an independent live re-fetch of their own URL; 45 sources, all fetched.

HEADLINE: THE WIDENED CLAIM IS CLOSED. The closer is arXiv:2608.05578, AMS (Google Cloud Activation-based Model Scanner). The code is open under Apache-2.0 and installs with `pip install ams-scanner`. Iteration 2 had this paper but filed it only under the weights-only lane.
- Tier 1 is reference-free and uses 16 contrastive pairs (32 prompts) per concept.
- It reads the final prompt token at 40-80% depth.
- It scores 14 checkpoints across 4 families, including 2 abliterated and 3 uncensored models.
- Its sigma predicts JailbreakBench compliance at Pearson r=-0.546 (p=0.043). The Spearman correlation is not significant (rho=-0.423, p=0.13).
- Leave-one-out threshold accuracy is 71%.
- It has no logit baseline, no response-site readout, no over-refusal outcome, and no Qwen3 or Qwen-abliterated checkpoint.
- It names decode-time analysis as its own 'principal open problem'.

Also covering this cell:
- N-GLARE (ACL 2026). CORRECTION: Figure 7 does print layer-group Pearson/Spearman couplings of JSS with unsafe rate and refusal rate across DPO steps. Still no cross-model tau and still no code.
- RAS/SafeVec 2606.25750: reference-anchored, 3 families, separates abliterated and uncensored models, tracks ASR.
- Aligned Probing (TACL 2026): layer-wise internals vs graded toxicity across 20+ models.

GROUP VERDICTS (C1-C14):
- B8 weights-only: CLOSED (Jorak, 273-checkpoint audit, OBLITERATUS toolkit).
- B1 onset depth: PARTIAL, high risk. CLS 2606.22686 ties family onset depth (Llama late 95%, Qwen ~40%) to robustness qualitatively.
- B2 response vs prompt site: PARTIAL, lowest risk. Response-site readouts exist only per input (HARC, Mitra 2606.29441, ForeSight); every per-checkpoint score is prompt-site.
- B3 cross-depth direction consistency: PARTIAL. The OBLITERATUS toolkit already computes the cross-layer refusal cosine matrix and angular drift.
- B4 accumulation: PARTIAL (detect-aggregate-express staging; per-prompt HPD and Geometry-Lite).
- B5 decodable-to-actionable lag: PARTIAL, medium-high (refusal gated downstream of where it is computed; Pythia lag).
- B6 over-refusal internals: PARTIAL, low-medium. No per-checkpoint internal predictor of XSTest over-refusal rate exists.
- B7 severity monotonicity: PARTIAL (graded toxicity encoding in Aligned Probing; harm organised by category, not severity).
- B9 budget and two-feature score: PARTIAL, high for C1 (AMS 16 pairs, ICS 10 pairs, IRT 10 items); an early+late model-level combination was not found.
- Causal check: random-direction controls are standard; applying the check at the response site on an abliterated checkpoint is open.

LEDGER: all 10 items CONFIRMED.
- Jorak is live (commit 8147de3, 2026-07-24, Apache-2.0, 0 stars; cite as a non-peer-reviewed tool).
- Safe Basu sentence: 98.2% AUROC vs 65/144 detected; zero corrections and zero disruptions for the SAE arm ONLY; TSV corrected 19/79 and disrupted 4/65.
- Kwon (0.24 vs 0.03) and anti-rank AUROC 0.220 confirmed.

BLOCK D: the knowledge-action gap is REPLICATED IN SAFETY and IN OTHER DOMAINS.
- In safety: 2606.24952 detection AUC 1.000 vs control direction ~83 degrees away; 2606.08044 dissociated models defeat static probes; recognition survives abliteration; AMS class-(iv) model has sigma 5.45 but 97% compliance.
- Other domains: Pythia steering null in 43/48 cells; CAD; truth-probe vs causal SAE features overlap ~12%; arithmetic.
- Counter-example: 2608.29109, where recognition-direction steering works.
- Basu's exact four-arm protocol is NOT replicated.

POSITIONING:
- Frame the paper as ONE mechanistic question: at what depth and site does safety become readable in a single model, and is the readout causal there?
- AMS sigma (open code) plus a final-layer logit gap are the bars every candidate must beat.
- Surviving contribution sentences:
  (1) Prompt-site vs response-site per-checkpoint readouts, abliterated included (conditional on results).
  (2) A logit-baseline and AMS-sigma margin, which none of the incumbents reports.
  (3) Over-refusal as a per-checkpoint internal outcome, plus a site-local matched-norm vs random-direction causal test.
- MUST NOT CLAIM:
  - a first cross-family few-prompt activation safety metric;
  - a first internal scoring of abliterated checkpoints;
  - reference-free or <=16 prompts as novelty;
  - recognition/execution naming;
  - recognition surviving abliteration;
  - any weights-only statistic;
  - 'N-GLARE has no correlations'.

## Research Findings

# Verdict in one paragraph

**The widened claim is CLOSED, and the closer is a paper this run already had in hand but filed under the wrong lane.** arXiv:2608.05578 (AMS, the Activation-based Model Scanner from Google Cloud, with open Apache-2.0 code) predicts a graded behavioural rate across model families from one model's own activations, using 16 contrastive prompt pairs per concept, and it scores abliterated checkpoints [1, 43, 2]. Iteration 2 checked it only as a candidate closer for the weights-only lane. Read against the widened claim, it meets five of the six components. Only the logit-baseline comparison is absent. Two more incumbents cover most of the same ground from different angles: N-GLARE (per-model latent scalar, 40+ models, the run's own Qwen3-4B trio in Figure 1, layer-group correlations with unsafe and refusal rates) [3], and RAS/SafeVec (reference-anchored, three families, separates abliterated and uncensored variants) [4]. A fourth, Aligned Probing (TACL 2026), has already published the "layer-resolved internal quantity correlates with graded behaviour across 20+ models" design in the toxicity domain [5].

**What is still empty is narrow but real.** (i) The response site: all three safety incumbents read only the final prompt token [43, 4, 3]. AMS itself names decode-time analysis as "the principal open problem motivated by the present work" [43]. (ii) A per-checkpoint internal predictor of over-refusal: AMS has zero XSTest or over-refusal matches, and RAS's only outcome is ASR [43, 4]. (iii) A logit-baseline margin: none of AMS, RAS or N-GLARE compares against a logit readout. (iv) The causal check at the survivor's layer and site. The paper should therefore be framed as one mechanistic question ("at what depth and site does safety become readable, and is it causal there?") with AMS's σ as the incumbent bar. It must not be framed as a new cheap safety metric.

## A. The widened claim, scored on the six components

The rule from the plan: a work CLOSES the cell only if it has (1) a graded behavioural rate, (2) ≥3 families, (3) the model's own activations with no reference model, and (5) abliterated checkpoints scored. It is PARTIAL with 2–4 of the six.

- **AMS [1, 43, 2]: 5/6, CLOSES.** (1) It measures "behavioral compliance on 20 stratified JailbreakBench prompts per model", and σ on the harmful-content concept "predicts compliance with Pearson r = -0.546 (p = 0.043), directionally but with meaningful noise" [1]. The rank correlation "is weaker" [43] (ρ = −0.423, p = 0.13). (2) and (5): "14 model configurations spanning 4 architecture families (Llama, Gemma, Qwen, Mistral) and four safety-modification categories (instruction-tuned, base, abliterated, uncensored fine-tunes)" [1]. (3) Tier 1 needs "(No baseline required)" [2]. (4) "Run 16 contrastive pairs through model, extract activations at layers 40-80% depth" [43], and "Each concept uses 16 pairs (32 prompts)" [43]. So it is depth-swept, but read only at the "final token position" [43]. (6) There is no logit baseline: logits appear only in AMS's discussion of its blind spot. The weak points are the incumbent bar the run must beat. Leave-one-out threshold accuracy is only "71% accuracy (10/14)" [1]. There is a class of behavioural fine-tunes that "is undetectable by activation-only probing of mid-residual-stream representations" (DarkIdol-Uncensored: σ = 5.45 but 97% compliance) [43]. The only Qwen checkpoint is Qwen2.5-7B-Instruct, and there is no Qwen abliterated checkpoint and no Qwen3.
- **N-GLARE [3]: 4/6 (1, 2, 3, 5), also CLOSES by the rule but at high input cost.** It uses the Qwen3-4B "RL-aligned, base, and safety-removed" trio as its illustration [3]. It reports that "the JSS metric exhibits high consistency with Red Teaming safety r[ankings]" over 40+ models [3], reads "the hidden states of the last token across all layers at the decision-making cross-section" [3], and aggregates "JSDs across all slices and layer groups" [3]. **Correction to iteration 2:** N-GLARE does print numeric correlations. Figure 7 shows layer-group Pearson and Spearman couplings of JSS with Unsafe Rate and Refusal Rate across DPO steps ("JSS exhibits strong step-wise coupling with both UR and RR across layers") [3]. The earlier finding still holds that there is no cross-model Kendall τ and no code. Its Refusal Rate "is based on refusal-style keyword matching" [3], and it needs four constructed dialogue families per model.
- **RAS/SafeVec [4]: 3/6 (1, 2, 5), PARTIAL, high risk.** "RAS separates aligned models from uncensored and abliterated variants, correlates with output-level attack success rate" [4]. However, it assumes "access to a safety-aligned reference model" per family plus calibration models [4]. It reads last-token activations in fixed windows (Qwen: layers 22–26 of Qwen2.5-7B) [4]. It prints no correlation coefficient, has no over-refusal outcome and no logit baseline, and "is also calibrated within model families" [4].
- **Aligned Probing [5]: the cross-model design in the toxicity domain.** It correlates "the average information strength at each layer with the resulting output toxicity (EMT) across different LMs" [5], finds "less toxic models encode more infor[mation]" [5], and locates the signal in "lower layers" [5]. It trains probes on many labelled inputs and scores no abliterated checkpoint.
- **Baselines and neighbours.** Behavioural IRT owns the ~10-item regime ("roughly ten adaptively chosen items suffice", 192 models) [6]. 2607.02714 predicts abliteration susceptibility over 24 models from metadata, not activations [40]. 2608.30748 shows within one model that refusal-axis projections "strongly predict jailbreak outcomes" across operational states [41]. 2506.12913 shows cross-model representational similarity predicts jailbreak transfer [42].
- **Adverse prior that limits every static readout.** A deliberately dissociated model passes every static audit, and "a strong fixed probe on clean activations cannot tell it from the base". Only an intervention-based score separates them (2.5–3.1×) [7]. This is the same blind spot as AMS's class (iv) [43].

## B. The nine candidate groups (C1–C14)

| Group (candidates) | Verdict | Nearest work: what it owns | Still empty |
|---|---|---|---|
| B1 early recognition / onset depth (C1, C4, C13) | **PARTIAL, high risk** | Family-level onset depth tied to robustness: Llama-3.1 processes harmful and safe queries "identically for 95% of their layers", while Qwen-2.5 diverges at ~40% depth and is "significantly more robust to linear steering" [19]. AMS sweeps 40–80% depth and keeps the max-separation layer [43]. Mid-depth "safety layers" [21]; early-layer identification [20]; refusal decodable "well before the final layer" [22]. Recognition survives abliteration [10, 11], so recognition-type readouts are expected **not** to separate abliterated from instruct. | Onset depth as a quantitative per-checkpoint predictor with a correlation across ≥3 families; the k ∈ {4, 8, 16} TPR@5%FPR curve. |
| B2 response site vs prompt site (C2, C9) | **PARTIAL, lowest risk of all groups** | The response-site readout is owned per input: HARC [25]; Mitra's first-generated-token probe, where "prompt-time activation defenses are structurally blind to prefilling attacks" [23]; ForeSight's "first-token hidden states" [24]. Per-checkpoint scores are all prompt-site [43, 4, 3]. | A response-site readout, or the response-minus-prompt site gap, as a **per-checkpoint** predictor. AMS names decode-time analysis as its principal open problem [43]. |
| B3 harm-direction self-consistency across depth (C3, C12) | **PARTIAL** | A public abliteration toolkit already computes "pairwise cosine similarities between refusal directions across all layers" and "cumulative angular drift per layer" [27]. Deception directions "rotate gradually across layers" [26]. Harm directions come out "73" degrees apart under two pooling choices [11]. Layer-wise Recognition/Execution geometry [13]. | Use as a per-checkpoint predictor of behaviour. The quantity itself is not novel. |
| B4 fixed-axis accumulation (C6, C7) | **PARTIAL** | Staging as "input-side harmfulness detection, aggregation along the refusal direction, and late-layer expression" [28]; refinement to "reject tokens" [20]; per-prompt slope and onset records [30, 31]; N-GLARE's layer-group JSS [3]. | A per-checkpoint accumulation scalar that ranks models. |
| B5 decodable-to-actionable depth lag (C8) | **PARTIAL, medium–high risk** | Refusal "is therefore gated at the late-layer expression stage, downstream of where it is computed" [28]. Where refusal "must be read" differs from where it is steered [29]. Readable-before-causal in Pythia [33]. | The harm-concept lag measured on an abliterated vs instruct checkpoint as a per-checkpoint score. |
| B6 benign-side / over-refusal internals (C10) | **PARTIAL, low–medium risk (the second-best open cell)** | Over-refusal directions "are task-dependent" and separable "from the early transformer layers" in one model, per input [37]. Steering along any refusal direction acts as "a shared one-dimensional control knob" for the refusal/over-refusal trade-off [38]. HRCI tracks XSTest refusal in one fine-tuning run [18]. N-GLARE's keyword RR is step-wise within one run [3]. | An internal per-checkpoint predictor of XSTest over-refusal **rate** across families. AMS and RAS have no over-refusal outcome [43, 4]. |
| B7 severity monotonicity (C11) | **PARTIAL, medium–high risk** | Graded (continuous) toxicity-level encoding, measured as "the Pearson correlation between the predicted" and actual toxicity, across 20+ models [5]. Harm is otherwise organised by category ("55 distinct harmfulness subconcepts") [39]. | Within-model Spearman against **ordinal harm-severity** tiers (0–3) for refusal-type harm. |
| B8 weights-only geometry (C12 zero-prompt) | **CLOSED** | Parent-free Jorak, where "on n'a pas besoin de générer ni de comparer à un original" (no generation and no original model needed) [9]; the reference-anchored 273-checkpoint audit [8]; the cross-layer cosine toolkit [27]. | Nothing citable as novel. |
| B9 restricted-budget operating point + two-feature score (C1, C14) | **PARTIAL, high risk for C1, medium for C14** | 16-pair budget [43]; a 10-pair diff-in-means readout "calibrated from ten labelled pairs" that a "bag-of-words model matches" [32]; ~10 behavioural items [6]; multi-layer ensembles [26]. | No work found that combines one early and one late feature into a single model-level score (absence over 3 logged queries). |
| Causal check (matched-norm projection vs random orthogonal direction at the survivor's layer and site) | **Method standard; application open** | Random-direction controls are routine: "projecting out a random direction does not" [28]; "a random direction of the same size does far less" [29]. | Running the check at the response site on an abliterated vs instruct checkpoint. |

## C. Standing ledger, re-verified 2026-09-21

All ten items are CONFIRMED by live fetch. **Jorak** is live (Apache-2.0, latest commit 8147de3 on 2026-07-24, 0 stars, non-peer-reviewed). METRICS.md still states the parent-free rationale [9] and the worked value "`A = 0.705`" for an abliterated Qwen3-8B [9]. Keep the citation, labelled as a tool. **LatentBiopsy**: "Geometry survives refusal ablation in both tested model families" [10]. **2604.18901** covers "three alignment variants (base, instruction-tuned, abliterated)" [11]. **Orgad** owns "harmful response generation is dissociable from the ability to recognize and reason about harmfulness" [12]. **DSH** owns "two distinct subspaces: a Recognition Axis" [13]. **2606.24952**: the weight cosine "is identical before and after instruction tuning (0.1197 vs 0.1200)" and is "not a predictor of how steerable a behavior is" [14]. **2607.01854**: "it presumes an attested reference" [8]. **N-GLARE**: still no code, and now known to print step-wise correlations (Section A) [3]. **Kwon**: "the instruct model routes it to refusal tokens about 8" times more (concentration 0.24 vs 0.03) [16]. **Anti-rank**: "outcome AUROC of 0.220" [17]. **HRCI_repr**: "so low coupling is not itself a safety score" [18].

**The one sentence the paper may safely say about Basu et al.:** In a single clinical-triage study on Qwen 2.5 7B Instruct, linear probes separated hazardous from benign vignettes at "98.2% AUROC" while the model's own output "detected 65 of 144 hazards overall (sensitivity 0.451"). SAE-feature steering produced "zero corrections and zero disruptions", whereas the other steering arms moved behaviour: TSV "corrected 19 of 79 false negatives" while disrupting 4 of 65 [15]. The "zero-and-zero, indistinguishable from random" wording must not be applied to all arms.

## D. Knowledge-action gap outside the clinic: REPLICATED, in safety and in other domains

- **In safety.** Detection at "perfect linear separability (AUC = 1.000 from layer 5)" coexists with a refusal-control direction about 83° away [14]. Dissociated models defeat static probes [7]. Harm recognition survives abliteration while refusal is gone [10, 11]. Internal harm scores anti-rank successful jailbreaks [17]. AMS's class-(iv) model keeps σ = 5.45 yet complies 97% of the time [43].
- **Other domains.** In Pythia, probes read targets from step 1,000, yet "steering along that same reading direction remains null-equivalent in 43 of 48" cells, and the authors "caution against inferring steerability from probe accuracy" [33]. CAD geometry: "decodable information is not always actionable" [34]. Truth and deception: probe-weighted and causal SAE features "overlap only weakly (about 12" %, ρ = 0.10) [35]. Arithmetic: near-perfect probes do not predict failures [36].
- **Counter-evidence.** In structural-impossibility math and code, steering along the recognition direction does work, dose-responsively, against random directions [45]. The gap is therefore not universal.
- **What is not replicated:** Basu's exact four-arm design (probe vs output vs steering vs SAE in one study). The pieces exist separately [33, 35]. Verdict: **REPLICATED-IN-SAFETY and REPLICATED-OTHER-DOMAIN for the gap; NOT-FOUND for the four-arm protocol.**

## E. Positioning

**Scoop risk.** Widened claim: **HIGH, closed** [1, 3]. B8: **HIGH, closed** [9]. B1, B9 (C1), B7, B5: **medium–high**. B3, B4: **medium** (the quantity is public [27], the per-checkpoint use is not). B6: **low–medium** [37, 43]. B2: **lowest** [43]. Causal check: low novelty as a method [28, 29], medium as the confirmation of a response-site survivor.

**Framing.** "At what depth, and at which site (prompt vs response), does safety behaviour become readable in a single model, and is the readout causal there?" This is one mechanistic question answered on a panel that contains base, safety-tuned and abliterated Qwen3-4B. It is not a bake-off of readout methods. AMS σ (open code) [2], a final-layer logit gap, and N-GLARE/RAS where reproducible are the bars that every internal candidate is printed beside.

**Contribution sentences that survive, each with its nearest competitor and distinguishing component.** The first and third are **conditional on the screen's results**.
1. *"We compare prompt-site and response-site activation readouts on the same checkpoints, abliterated included, and show where along depth each becomes predictive of harmful compliance."* Nearest: AMS, RAS and N-GLARE, all final-prompt-token [43, 4, 3]; HARC and Mitra, per input only [25, 23]. Distinguishing component: the response site at the per-checkpoint level. AMS itself names this as its principal open problem [43].
2. *"Every internal readout is reported beside AMS's σ and a logit-only baseline, and is counted as a result only if it beats both."* Nearest: AMS, RAS and N-GLARE, which report no logit baseline [1, 4, 3]. Distinguishing component: the baseline margin.
3. *"We test whether benign-twin internals predict over-refusal rate across checkpoints, and whether the best readout is causal at its own layer and site under a matched-norm vs random-direction control."* Nearest: per-input, single-model over-refusal geometry [37] and intervention-based audit scores [7]. Distinguishing component: over-refusal as a per-checkpoint outcome, plus the site-local causal test.

**Sentences the paper must NOT say.**
- "First activation-based safety metric that predicts behaviour across model families from few prompts" (AMS [1]).
- "First to score abliterated checkpoints from activations" [1, 4, 3, 11].
- "Reference-free" or "≤16 prompts" as novelty [2, 9, 32, 6].
- "Recognition vs execution" as new naming [12, 13].
- "Harm recognition survives abliteration" as new [10, 11].
- Any weights-only or zero-prompt statistic as novel [9, 8].
- "N-GLARE reports no correlations" (Figure 7 does [3]).
- "Our readout is a safety score" without beating AMS σ and the logit gap.
- The zero-and-zero Basu wording for arms other than SAE [15].

**Confidence.** High that the widened cell is closed (AMS and N-GLARE read in full text, 87/87 quoted passages re-verified by live fetch). Medium on the B-group verdicts, because searches cannot prove absence. The B2 and B6 openings would fall if a per-checkpoint response-site or over-refusal paper appears after 2026-09-21. The safe-completion internal-readout gap from iteration 2 still stands: the one new hit is behavioural only [44].


## Sources

[1] [Detecting Safety Training Modification in Language Models via Activation Analysis (AMS: Activation-based Model Scanner)](https://arxiv.org/abs/2608.05578) (2026) — THE CLOSER of the widened claim. Reference-free (Tier 1) activation scanner: 16 contrastive pairs per concept, final prompt token, 40-80% depth sweep, 14 checkpoints / 4 families incl. 2 abliterated and 3 uncensored; sigma predicts JailbreakBench compliance at Pearson r=-0.546 (p=0.043); LOO threshold accuracy 71%.

> We validate AMS across 14 model configurations spanning 4 architecture families (Llama, Gemma, Qwen, Mistral) and four safety-modification categories (instruction-tuned, base, abliterated, uncensored fine-tunes).

Locator: regex: 14 model configurations

> We measure behavioral compliance on 20 stratified JailbreakBench prompts per model and find that sigma on the harmful-content concept predicts compliance with Pearson r = -0.546 (p = 0.043), directionally but with meaningful noise.

Locator: regex: Pearson r

> Leave-one-out cross-validation of thresholds achieves 71% accuracy (10/14)

Locator: regex: 71%

[2] [AMS - Activation-based Model Scanner (GoogleCloudPlatform/activation-model-scanner README)](https://raw.githubusercontent.com/GoogleCloudPlatform/activation-model-scanner/main/README.md) (2026) — Open-source (Apache-2.0, pip ams-scanner) implementation of AMS; Tier 1 needs no baseline; README table: instruct 4.7-8.4 sigma, abliterated 3.3 sigma, uncensored 1.1-1.3 sigma, base 0.7 sigma. Repo live, 69 commits, latest commit e7ca0d1 on 2026-08-27, 33 stars.

> (No baseline required)

Locator: regex: No baseline required

> show collapsed safety directions that AMS can detect in seconds

Locator: regex: collapsed safety directions

[3] [N-GLARE: A Non-Generative Latent Representation-Efficient LLM Safety Evaluator (ACL 2026 Long 1334)](https://aclanthology.org/2026.acl-long.1334.pdf) (2026) — Per-model latent JSS scalar over 40+ models, last token across all layers before the response, four constructed dialogue families; Figure 1 uses the RL-aligned/base/safety-removed Qwen3-4B trio; Figure 7 prints layer-group Pearson/Spearman couplings of JSS with Unsafe Rate and keyword Refusal Rate across DPO steps. Still no code.

> RL-aligned, base, and safety-removed ver

Locator: regex: safety-removed

> demonstrate that the JSS metric exhibits high consistency with Red Teaming safety r

Locator: regex: JSS metric exhibits

> we extract the hidden states of the last token across all layers at the decision-making cross-section

Locator: regex: hidden states of the last token across all layers

> JSS exhibits strong step-wise coupling with both UR and RR across layers

Locator: regex: step-wise coupling

> aggregate JSDs across all slices and layer groups

Locator: regex: aggregate JSDs across all slices and layer groups

[4] [RAS: Measuring LLM Safety Through Refusal Alignment (SafeVec)](https://arxiv.org/html/2606.25750) (2026) — White-box 0-100 safety score from last-token refusal-direction alignment in a fixed family-specific layer window; needs a per-family aligned reference model and a calibration set; three families (Llama-3.1-8B, Gemma-3-4B, Qwen2.5-7B); separates aligned from uncensored/abliterated and tracks HEx-PHI ASR; no correlation coefficient, no over-refusal outcome, no logit baseline.

> Across Llama, Gemma, and Qwen families, RAS separates aligned models from uncensored and abliterated variants, correlates with output-level attack success rate, and is substantially faster than judge-based evaluation.

Locator: regex: SafeVec

> For each architecture family aa, we assume access to a safety-aligned reference model

Locator: regex: reference model

> The reference model defines the refusal direction, while calibration models define how raw cosine similarities should be mapped into a comparable RAS scale.

Locator: regex: calibration models

> We extract last-token residual-stream activations at each decoder layer.

Locator: regex: last-token residual-stream

> For Llama, we use layers 22–30. For Gemma, we use layers 27–29. For Qwen, we use layers 22–26.

Locator: regex: For Qwen, we use layers

[5] [Aligned Probing: Relating Toxic Behavior and Model Internals (TACL 2026)](https://aclanthology.org/2026.tacl-1.14.pdf) (Andreas Waldis, Vagrant Gautam, Anne Lauscher, Dietrich Klakow, Iryna Gurevych; 2026) — Across 20+ OLMo/Llama/Mistral LMs, layer-wise toxicity-encoding strength (graded, Pearson of probe-predicted vs actual toxicity) correlates with output toxicity (EMT) across models; signal in lower layers; causal interventions; 6 OLMo pretraining checkpoints. Toxicity domain, not refusal; no abliterated checkpoints.

> and find that less toxic models encode more infor-

Locator: regex: less toxic models encode

> we correlate the average information strength at each layer with the resulting output toxicity (EMT) across different LMs.

Locator: regex: correlate the average information

> mation about the toxicity of text in lower layers.

Locator: regex: lower layers

> We then approximate the encoding strength (s) as the Pearson correlation between the predicted

Locator: regex: encoding strength

[6] [Item Response Theory for AI Safety](https://arxiv.org/abs/2608.05086) (2026) — Behavioural IRT over 8 safety benchmarks and 192 models; ~10 adaptively chosen items suffice. Owns the few-item regime behaviourally (a baseline, not an activation competitor).

> roughly ten adaptively chosen items suffice for several individual benchmarks, cutting evaluation cost by 97-99%

Locator: regex: ten adaptively

> We fit IRT models to eight safety benchmarks across 192 language models

Locator: regex: 192 language models

[7] [When Behavioral Safety Evaluation Fails: A Representation-Level Perspective](https://arxiv.org/html/2606.08044) (Enyi Jiang, Anders Gjølbye, Yibo Jacky Zhang, Sanmi Koyejo; 2026) — Adverse prior: constructed 'dissociated' models pass every static audit including a strong fixed activation probe; only an intervention-based Latent Vulnerability Score (2.5-3.1x) separates them.

> a strong fixed probe on clean activations cannot tell it from the base

Locator: regex: strong fixed probe

> At the targeted mid layer the dissociated models score 2.5 to 3.1 times higher LVS than their bases.

Locator: regex: 2.5 to 3.1

[8] [Has This Checkpoint Been Abliterated? A Two-Signal Audit and Its Failure Map](https://arxiv.org/abs/2607.01854) (2026) — 273-checkpoint registry, AUROC 0.95 for 57 abliterations vs 37 benign; presumes an attested reference (reference-anchored). Re-verified today.

> it presumes an attested reference

Locator: regex: attested reference

> separates 57 public abliterations from 37 benign fine-tunes, merges, and instruction-tunes at AUROC 0.95

Locator: regex: AUROC 0.95

[9] [Jorak Model Scanner docs/METRICS.md](https://raw.githubusercontent.com/JolanMc/Jorak/main/docs/METRICS.md) (2026) — Parent-free, weights-only abliteration detector (suppression statistic, SVD alignment A=sigma1(U)/||U||_F). Repo live today: Apache-2.0, latest commit 8147de3 (2026-07-24), 0 stars, non-peer-reviewed.

> on n'a pas besoin de générer ni de comparer à un original pour séparer *censuré* de *ablated*

Locator: regex: reference-free

> `A = 0.705`

Locator: regex: A = 0.705

[10] [The Geometry of Harmful Intent: Training-Free Anomaly Detection via Angular Deviation in LLM Residual Streams (LatentBiopsy)](https://arxiv.org/html/2603.27412) (Isaac Llorente-Saguer; 2026) — Harm geometry survives abliteration (Qwen3.5-0.8B, Qwen2.5-0.5B; AUROC within 0.015).

> Geometry survives refusal ablation in both tested model families.

Locator: regex: Geometry survives

[11] [Harmful Intent as a Geometrically Recoverable Feature of LLM Residual Streams](https://arxiv.org/html/2604.18901) (2026) — 12 models, 4 families, base/instruct/abliterated; harm detection within +/-0.003 AUROC across variants; two pooling choices recover harm directions 73 degrees apart.

> three alignment variants (base, instruction-tuned, abliterated)

Locator: regex: abliterated

> recover harm directions 73

Locator: regex: 73°

[12] [Large Language Models Generate Harmful Responses Using a Distinct Mechanism, Shared Across Harm Types](https://arxiv.org/html/2604.09544) (Hadas Orgad, Boyi Wei, Kaden Zheng, Martin Wattenberg, Peter Henderson, Seraphina Goldfarb-Tarrant, Yonatan Belinkov; 2026) — Harm generation dissociable from harm recognition; double dissociation; separability emerges along the OLMo-3-7B ladder at DPO.

> harmful response generation is dissociable from the ability to recognize and reason about harmfulness

Locator: regex: dissociable

[13] [Knowing without Acting: The Disentangled Geometry of Safety Mechanisms in Large Language Models](https://arxiv.org/html/2603.05773v2) (Jinman Wu, Yi Xie, Shen Lin, Shiqian Zhao, Xiaofeng Chen; 2026) — Owns the Recognition-Axis / Execution-Axis naming and a causal double dissociation (attack framing: Refusal Erasure Attack).

> two distinct subspaces: a Recognition Axis

Locator: regex: Recognition Axis

[14] [Perfect Detection, Failed Control: The Geometry of Knowing vs. Steering in Language Models](https://arxiv.org/html/2606.24952) (2026) — Detection AUC 1.000 yet the refusal-control direction sits ~83 degrees away; weight cosine 0.1197 vs 0.1200 across instruction tuning; 'not a predictor of how steerable a behavior is'.

> it is identical before and after instruction tuning (0.1197 vs 0.1200)

Locator: regex: 0.1197

> not a predictor of how steerable a behavior is

Locator: regex: not a predictor

> perfect linear separability (AUC = 1.000 from layer 5)

Locator: regex: AUC = 1.000

[15] [Interpretability without actionability: mechanistic methods cannot correct language model errors despite near-perfect internal representations](https://arxiv.org/html/2603.18353) (Sanjay Basu, Sadiq Y. Patel, Parth Sheth, Bhairavi Muralidharan, Namrata Elamaran, Aakriti Kinra, John Morgan, Rajaie Batniji; 2026) — Clinical triage, Qwen 2.5 7B Instruct: probe AUROC 98.2% vs output sensitivity 65/144 (45%); SAE arm zero corrections/zero disruptions; concept-bottleneck 17/85 corrected, 25/47 disrupted; TSV 19/79 corrected, 4/65 disrupted.

> 98.2% AUROC

Locator: regex: 98.2

> detected 65 of 144 hazards overall (sensitivity 0.451

Locator: regex: 65 of 144

> zero corrections and zero disruptions

Locator: regex: zero corrections

> corrected 19 of 79 false negatives

Locator: regex: 19 of 79

[16] [Breaking Refusal in the First Half: A Mechanistic Study of the Prefill Jailbreak](https://arxiv.org/html/2607.14147v1) (2026) — Logit-trace concentration 0.24 vs 0.03 (instruct vs base, knockout-conditioned). Re-verified.

> the instruct model routes it to refusal tokens about 8

Locator: regex: 0.24 vs 0.03

[17] [Measuring the Wrong Thing: Internal Harmfulness Scores Anti-Rank Successful Jailbreaks](https://arxiv.org/html/2608.09624) (2026) — Outcome AUROC 0.220 among wrapped harmful prompts: internal harm scores rank successful attacks below failed ones. Re-verified.

> outcome AUROC of 0.220

Locator: regex: 0.220

[18] [From Refusal Geometry to Safety Geometry: Harmfulness-Refusal Coupling under Dynamic Adversarial Fine-Tuning (HRCI_repr)](https://arxiv.org/html/2606.16349) (2026) — Parent-free coupling index whose authors state low coupling is not itself a safety score; tracks XSTest refusal during adversarial fine-tuning.

> so low coupling is not itself a safety score

Locator: regex: not itself a safety score

[19] [The Geometry of Refusal: Linear Instability in Safety-Aligned LLMs (Contrastive Logit Steering)](https://arxiv.org/html/2606.22686v2) (2026) — Seven families: harmful/safe hidden-state KL divergence onset depth differs by family ('Late Decision' Llama-3.1 at the final head vs 'Early Divergence' Qwen-2.5 at ~40% depth), qualitatively tied to robustness. TrustNLP 2026.

> Models like Llama-3.1 process harmful and safe queries identically for 95% of their layers, diverging only at the final output head.

Locator: regex: Late Decision

> making them significantly more robust to linear steering.

Locator: regex: Early Divergence

> We investigated where in the network the refusal decision occurs by measuring KL Divergence between hidden states of safe vs. harmful trajectories across network depth

Locator: regex: KL Divergence between hidden states

[20] [How Alignment and Jailbreak Work: Explain LLM Safety through Intermediate Hidden States](https://arxiv.org/abs/2406.05644) (2024) — 2024 anchor: malicious vs normal inputs identified in early layers; alignment maps them via middle layers to reject tokens.

> can identify malicious and normal inputs in the early layers

Locator: regex: early layers

> refines them to the specific reject tokens for safe generations

Locator: regex: reject tokens

[21] [Safety Layers in Aligned Large Language Models: The Key to LLM Security](https://arxiv.org/abs/2408.17003) (Shen Li, Liuyi Yao, Lan Zhang, Yaliang Li; 2024) — Contiguous mid-depth 'safety layers' distinguish malicious from normal queries.

> identifying a small set of contiguous layers in the middle of the model that are crucial for distinguishing malicious queries from normal ones

Locator: regex: safety layers

[22] [Refusal Before Decoding: Detecting and Exploiting Refusal Signals in Intermediate LLM Activations](https://arxiv.org/html/2605.28553) (2026) — Refusal linearly decodable well before the final layer (per-input probes, used for attack search).

> We find that refusal is linearly decodable well before the final layer

Locator: regex: well before the final layer

[23] [Closing the Activation-Cone Blind Spot: Response-Time Probing and Unified Defense](https://arxiv.org/html/2606.29441) (2026) — Seven models: prompt-time activation defenses are structurally blind to prefilling; response-time probe at the first generated tokens (AUROC 0.97-1.00), per input.

> Our central finding is that prompt-time activation defenses are structurally blind to prefilling attacks

Locator: regex: structurally blind

> a linear probe on the model’s hidden state at the first few generated tokens

Locator: regex: first few generated tokens

[24] [ForeSight: Enhancing Risk Monitoring via Early Safety Signal Distillation](https://arxiv.org/abs/2609.13737) (2026) — First-response-token hidden states forecast output harm (two target models, per input). Findings of EMNLP 2026.

> relying solely on first-token hidden states

Locator: regex: first-token hidden states

[25] [HARC: Coupling Harmfulness and Refusal Directions for Robust Safety Alignment](https://arxiv.org/abs/2607.00572) (Shei Pern Chua, Hao Wu, Qianli Ma, Fangzhao Wu; 2026) — Owns the response-site harmfulness readout (model recognises harm while generating it even when the prompt side missed it).

> Extending the analysis to response-token positions, we find that the model recognizes harmful content while it is generating that content, even when it failed to recognize the input as harmful at the prompt side.

Locator: regex: response-token positions

[26] [Linear Probe Accuracy Scales with Model Size and Benefits from Multi-Layer Ensembling](https://arxiv.org/html/2604.13386) (2026) — Deception directions rotate gradually across layers (12 models); multi-layer ensembles fix single-layer brittleness.

> deception directions rotate gradually across layers rather than appearing at one location

Locator: regex: rotate gradually

[27] [OBLITERATUS toolkit, analysis/cross_layer.py (community abliteration tool)](https://raw.githubusercontent.com/elder-plinius/OBLITERATUS/cb4aec45/obliteratus/analysis/cross_layer.py) — Non-peer-reviewed public code that already computes the pairwise cross-layer refusal-direction cosine matrix, direction clusters and cumulative angular drift per layer.

> computing pairwise cosine similarities between refusal directions across all layers

Locator: regex: pairwise cosine

> angular_drift: list[float] # cumulative angular drift per layer

Locator: regex: angular_drift

[28] [Refusal Lives Downstream of Persona in Chat Models](https://arxiv.org/html/2606.26161) (2026) — Refusal staged as detection -> aggregation -> late-layer expression; refusal is gated at the late expression stage, downstream of where it is computed; random-direction control. ICML 2026 MI workshop.

> This mediation unfolds across layers in three stages: input-side harmfulness detection, aggregation along the refusal direction, and late-layer expression (Lee et al., 2025).

Locator: regex: three stages

> Refusal is therefore gated at the late-layer expression stage, downstream of where it is computed.

Locator: regex: downstream of where

[29] [Locating and Steering Refusal Beyond Attention](https://arxiv.org/abs/2609.04721) (2026) — Where refusal must be read (write site) is architecture-specific while where it is steered is not; matched-size random-direction control.

> What is architecture-specific is not where the direction is steered but where it must be read.

Locator: regex: write site

[30] [Harmfulness Propagation Dynamics: Layer-wise Trajectories of Adversarial Intent in Large Language Models](https://arxiv.org/abs/2609.13534) (Noor Islam S. Mohammad, Uluğ Bayazıt; 2026) — Per-prompt depth-profile scalarisation (slope, curvature, monotonicity, onset layer) fed to a 288-parameter MLP.

> This lightweight input moderator extracts a seven-dimensional feature record, slope, curvature, monotonicity, onset layer, and related statistics from the cross-layer projection sequence and classifies it with a 288-parameter MLP.

Locator: regex: seven-dimensional

[31] [Geometry-Lite: Interpretable Safety Probing via Layer-Wise Margin Geometry](https://arxiv.org/abs/2605.20241) (Woo Seob Sim, Yu Rang Park; 2026) — Per-prompt layer-wise margin-profile summaries over nine backbones.

> then summarizes the resulting margin profiles by boundary position, layer-to-layer change, and coarse shape. Across nine instruction-tuned backbones

Locator: regex: margin profiles

[32] [What Do Compliance Detectors Read? An Audit of Activation Probes and Guard Models](https://arxiv.org/html/2608.16852) (2026) — 10-pair training-free diff-in-means activation readout (Internal Compliance Score); fails its pre-registered bar and ties a bag-of-words model.

> a training-free activation readout calibrated from ten labelled pairs and scored by a single projection

Locator: regex: ten labelled pairs

> a bag-of-words model matches its pooled generalisation exactly

Locator: regex: bag-of-words

[33] [Lagged Coupling: Internal Representations Become Readable Before They Become Causal](https://arxiv.org/pdf/2609.01048v1) (2026) — Pythia 160M-12B, 8 checkpoints: probes read targets from step 1,000 yet steering is null-equivalent in 43 of 48 model x checkpoint cells.

> steering along that same reading direction remains null-equivalent in 43 of 48

Locator: regex: 43 of 48

> Our results caution against inferring steerability from probe accuracy

Locator: regex: caution against inferring steerability

[34] [Encoded but Not Actionable: Auditing the Decode-Generate-Steer Gap in Frozen LLMs for Geometric Constraints](https://arxiv.org/html/2608.17843v1) (2026) — Non-safety (CAD geometry), six models: decodable information is not always actionable; patching effects vanish while decodability persists.

> Further analyses show that decodable information is not always actionable.

Locator: regex: not always actionable

[35] [Decodability is Not Causality: Dissociating Probe Readouts from Behavioral Drivers via SAE Decomposition](https://arxiv.org/html/2609.18080v1) (2026) — Truth/deception: probe-weighted and behaviourally causal SAE features overlap only ~12% (Spearman rho=0.10); ablation dissociates them.

> the two rankings overlap only weakly (about 12

Locator: regex: Spearman

[36] [The Knowing-Saying Gap: When Probes See Errors that Confidence Misses](https://arxiv.org/html/2608.07528) (2026) — Near-perfect corruption probes do not predict failures; probe-based interventions are model-dependent.

> Linear probes detect corrupted context in language models with near-perfect accuracy, yet this does not translate into reliable failure prediction.

Locator: regex: near-perfect accuracy

[37] [Over-Refusal and Representation Subspaces: A Mechanistic Analysis of Task-Conditioned Refusal in Aligned LLMs](https://arxiv.org/abs/2603.27518) (2026) — Over-refusal directions are task-dependent and representationally distinct from harmful refusal from early layers; single model, per input. EMNLP 2026 Main.

> whereas over-refusal directions are task-dependent

Locator: regex: task-dependent

> Linear probing suggests that the two refusal types are representationally distinct from the early transformer layers.

Locator: regex: early transformer layers

[38] [There Is More to Refusal in Large Language Models than a Single Direction](https://arxiv.org/abs/2602.02132) (2026) — Distinct refusal directions but steering along any gives nearly identical refusal/over-refusal trade-offs (one shared control knob).

> acting as a shared one-dimensional control knob

Locator: regex: one-dimensional control knob

[39] [The Geometry of Harmfulness in LLMs through Subconcept Probing](https://arxiv.org/pdf/2507.21141v1.pdf) (2025) — 55 harmfulness sub-concept directions: harm organised by category, not ordinal severity.

> 55 distinct harmfulness subconcepts

Locator: regex: 55 distinct harmfulness subconcepts

[40] [Not All Refusals Are Equal: How Safety Alignment Fails Cybersecurity at Scale](https://arxiv.org/html/2607.02714) (2026) — Abliteration over 24 open models; susceptibility predicted from safety-training type and architecture (metadata), not activations.

> large scale abliteration experiment on 24 open-source LLMs

Locator: regex: 24 open-source

> identifying that the type of safety training and architecture are the most reliable predictors

Locator: regex: most reliable predictors

[41] [The Fragility of Jailbreak Robustness Across Operational States](https://arxiv.org/html/2608.30748) (2026) — Within a model, projection on a refusal-related axis predicts ASR across operational states (per condition, not per checkpoint).

> projections onto this axis strongly predict jailbreak outcomes

Locator: regex: strongly predict jailbreak outcomes

[42] [Jailbreak Transferability Emerges from Shared Representations](https://arxiv.org/abs/2506.12913) (2025) — Across 20 models, benign-prompt representational similarity predicts jailbreak transfer (attack-side; not a safety score).

> representational similarity under benign prompts

Locator: regex: representational similarity under benign prompts

[43] [Detecting Safety Training Modification in Language Models via Activation Analysis (AMS) - full text](https://arxiv.org/html/2608.05578) (2026) — Full-text anchors: 16 pairs (32 prompts) per concept, final-token extraction, 40-80% depth; Spearman weaker (rho=-0.423, p=0.13); class-(iv) blind spot (DarkIdol sigma 5.45 with 97% compliance) and decode-time analysis named as the principal open problem; zero XSTest/over-refusal matches.

> the rank-order Spearman correlation is weaker

Locator: regex: Spearman correlation is weaker

> Run 16 contrastive pairs through model, extract activations at layers 40-80% depth

Locator: regex: 16 contrastive pairs

> Each concept uses 16 pairs (32 prompts).

Locator: regex: 16 pairs \(32 prompts\)

> capture hidden states at the final token position

Locator: regex: final token position

> This case is undetectable by activation-only probing of mid-residual-stream representations.

Locator: regex: undetectable by activation-only probing

[44] [Refuse without Refusal: A Structural Analysis of Safety-Tuning Responses for Reducing False Refusals in Language Models](https://arxiv.org/abs/2609.04714) (Minji Kim, Hyounghun Kim; 2026) — Behavioural only: rationale-only safety tuning reduces false refusals. Checked for the safe-completion internal-readout cell; it has no activation readout, so that NOT-FOUND stands.

[45] [Recognition-Refusal Misalignment in LLMs: Why Models Answer Structurally Unanswerable Questions](https://arxiv.org/abs/2608.29109) (2026) — Non-safety knowledge-action gap (impossible math/code): a recognition direction exists before generation and is nearly orthogonal to safety refusal, yet steering along it works dose-responsively vs random directions. Counter-example to 'readable implies not actionable'.

## Verification

Numbered citations resolve to unique listed sources. Passage checks test text occurrence, not claim truth or entailment. Author/year metadata and locators are not independently verified. Details: `research_verification.json`.

- Source [1]: text found — We validate AMS across 14 model configurations spanning 4 architecture families (Llama, Gemma, Qwen,
- Source [1]: text found — We measure behavioral compliance on 20 stratified JailbreakBench prompts per model and find that sig
- Source [1]: text found — Leave-one-out cross-validation of thresholds achieves 71% accuracy (10/14)
- Source [2]: text found — (No baseline required)
- Source [2]: text found — show collapsed safety directions that AMS can detect in seconds
- Source [3]: text found — RL-aligned, base, and safety-removed ver
- Source [3]: text found — demonstrate that the JSS metric exhibits high consistency with Red Teaming safety r
- Source [3]: text found — we extract the hidden states of the last token across all layers at the decision-making cross-sectio
- Source [3]: text found — JSS exhibits strong step-wise coupling with both UR and RR across layers
- Source [3]: text found — aggregate JSDs across all slices and layer groups
- Source [4]: text found — Across Llama, Gemma, and Qwen families, RAS separates aligned models from uncensored and abliterated
- Source [4]: text found — For each architecture family aa, we assume access to a safety-aligned reference model
- Source [4]: text found — The reference model defines the refusal direction, while calibration models define how raw cosine si
- Source [4]: text found — We extract last-token residual-stream activations at each decoder layer.
- Source [4]: text found — For Llama, we use layers 22–30. For Gemma, we use layers 27–29. For Qwen, we use layers 22–26.
- Source [5]: text found — and find that less toxic models encode more infor-
- Source [5]: text found — we correlate the average information strength at each layer with the resulting output toxicity (EMT)
- Source [5]: text found — mation about the toxicity of text in lower layers.
- Source [5]: text found — We then approximate the encoding strength (s) as the Pearson correlation between the predicted
- Source [6]: text found — roughly ten adaptively chosen items suffice for several individual benchmarks, cutting evaluation co
- Source [6]: text found — We fit IRT models to eight safety benchmarks across 192 language models
- Source [7]: text found — a strong fixed probe on clean activations cannot tell it from the base
- Source [7]: text found — At the targeted mid layer the dissociated models score 2.5 to 3.1 times higher LVS than their bases.
- Source [8]: text found — it presumes an attested reference
- Source [8]: text found — separates 57 public abliterations from 37 benign fine-tunes, merges, and instruction-tunes at AUROC 
- Source [9]: text found — on n'a pas besoin de générer ni de comparer à un original pour séparer *censuré* de *ablated*
- Source [9]: text found — `A = 0.705`
- Source [10]: text found — Geometry survives refusal ablation in both tested model families.
- Source [11]: text found — three alignment variants (base, instruction-tuned, abliterated)
- Source [11]: text found — recover harm directions 73
- Source [12]: text found — harmful response generation is dissociable from the ability to recognize and reason about harmfulnes
- Source [13]: text found — two distinct subspaces: a Recognition Axis
- Source [14]: text found — it is identical before and after instruction tuning (0.1197 vs 0.1200)
- Source [14]: text found — not a predictor of how steerable a behavior is
- Source [14]: text found — perfect linear separability (AUC = 1.000 from layer 5)
- Source [15]: text found — 98.2% AUROC
- Source [15]: text found — detected 65 of 144 hazards overall (sensitivity 0.451
- Source [15]: text found — zero corrections and zero disruptions
- Source [15]: text found — corrected 19 of 79 false negatives
- Source [16]: text found — the instruct model routes it to refusal tokens about 8
- Source [17]: text found — outcome AUROC of 0.220
- Source [18]: text found — so low coupling is not itself a safety score
- Source [19]: text found — Models like Llama-3.1 process harmful and safe queries identically for 95% of their layers, divergin
- Source [19]: text found — making them significantly more robust to linear steering.
- Source [19]: text found — We investigated where in the network the refusal decision occurs by measuring KL Divergence between 
- Source [20]: text found — can identify malicious and normal inputs in the early layers
- Source [20]: text found — refines them to the specific reject tokens for safe generations
- Source [21]: text found — identifying a small set of contiguous layers in the middle of the model that are crucial for disting
- Source [22]: text found — We find that refusal is linearly decodable well before the final layer
- Source [23]: text found — Our central finding is that prompt-time activation defenses are structurally blind to prefilling att
- Source [23]: text found — a linear probe on the model’s hidden state at the first few generated tokens
- Source [24]: text found — relying solely on first-token hidden states
- Source [25]: text found — Extending the analysis to response-token positions, we find that the model recognizes harmful conten
- Source [26]: text found — deception directions rotate gradually across layers rather than appearing at one location
- Source [27]: text found — computing pairwise cosine similarities between refusal directions across all layers
- Source [27]: text found — angular_drift: list[float] # cumulative angular drift per layer
- Source [28]: text found — This mediation unfolds across layers in three stages: input-side harmfulness detection, aggregation 
- Source [28]: text found — Refusal is therefore gated at the late-layer expression stage, downstream of where it is computed.
- Source [29]: text found — What is architecture-specific is not where the direction is steered but where it must be read.
- Source [30]: text found — This lightweight input moderator extracts a seven-dimensional feature record, slope, curvature, mono
- Source [31]: text found — then summarizes the resulting margin profiles by boundary position, layer-to-layer change, and coars
- Source [32]: text found — a training-free activation readout calibrated from ten labelled pairs and scored by a single project
- Source [32]: text found — a bag-of-words model matches its pooled generalisation exactly
- Source [33]: text found — steering along that same reading direction remains null-equivalent in 43 of 48
- Source [33]: text found — Our results caution against inferring steerability from probe accuracy
- Source [34]: text found — Further analyses show that decodable information is not always actionable.
- Source [35]: text found — the two rankings overlap only weakly (about 12
- Source [36]: text found — Linear probes detect corrupted context in language models with near-perfect accuracy, yet this does 
- Source [37]: text found — whereas over-refusal directions are task-dependent
- Source [37]: text found — Linear probing suggests that the two refusal types are representationally distinct from the early tr
- Source [38]: text found — acting as a shared one-dimensional control knob
- Source [39]: text found — 55 distinct harmfulness subconcepts
- Source [40]: text found — large scale abliteration experiment on 24 open-source LLMs
- Source [40]: text found — identifying that the type of safety training and architecture are the most reliable predictors
- Source [41]: text found — projections onto this axis strongly predict jailbreak outcomes
- Source [42]: text found — representational similarity under benign prompts
- Source [43]: text found — the rank-order Spearman correlation is weaker
- Source [43]: text found — Run 16 contrastive pairs through model, extract activations at layers 40-80% depth
- Source [43]: text found — Each concept uses 16 pairs (32 prompts).
- Source [43]: text found — capture hidden states at the final token position
- Source [43]: text found — This case is undetectable by activation-only probing of mid-residual-stream representations.

## Follow-up Questions

- Does a response-site readout (first generated tokens) beat the AMS harmful-content sigma and a final-layer logit gap at predicting harmful-compliance rate on a panel that includes the Qwen3-4B base / instruct / abliterated trio, and which of AMS's four modification classes does the community Qwen3-4B abliterated checkpoint fall into?
- Can any internal readout rank checkpoints by XSTest over-refusal rate across at least three families, a behaviour none of AMS, RAS or N-GLARE scores?
- At the surviving layer and site, does a matched-norm projection along the readout direction move behaviour more than a norm-matched random orthogonal direction on the instruct checkpoint and fail to on the abliterated one? That would turn the readout into the mechanistic answer rather than a correlate.

---
*Generated by AI Inventor Pipeline*
