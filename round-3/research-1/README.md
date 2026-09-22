# Is our depth-and-site safety metric already taken?

`demo/` — Self-contained demo (Colab-ready notebook or markdown). Run without setup.  
`src/` — Full source code, data, and outputs from the experiment execution.

**Type:** research  
**ID:** `art_d7zKf99Ok-2i`

## Layman Summary

Checks whether anyone has already built a cheap safety score that reads a model's internal activations, and finds that a Google tool already does most of it, leaving only the during-the-reply reading and over-refusal open.

## Full Summary

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

## Dependencies

- `art_ZNITuuQab6Nz` — extends
- `art_CC5kC0-E3lXW` — extends

## Output Files

- `research_out.json`

## Demo Files

- **research_report.md** — Research report markdown (auto-generated from artifact)

---
*Generated by AI Inventor Pipeline*
