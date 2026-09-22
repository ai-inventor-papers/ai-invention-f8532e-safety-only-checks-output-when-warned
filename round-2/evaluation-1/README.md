# Re-checking the numbers we already have

`demo/` — Self-contained demo (Colab-ready notebook or markdown). Run without setup.  
`src/` — Full source code, data, and outputs from the experiment execution.

**Type:** evaluation  
**ID:** `art_G5pqEoRFZ75t`

## Layman Summary

Re-audits last round's three experiments using only files already saved, and finds the headline safety result was measured on a scale that had no room to move.

## Full Summary

ZERO-GPU, ZERO-API RE-ADJUDICATION of iteration 1's three lanes (M0-M8), computed only from files already on disk. Pre-registration frozen and hashed BEFORE the first number: SHA-256 7f6a38d94007c3a7d07b40cadfc79863cdd504f1115e2cf47e12511c4d77966b. Self-check PASS (12 tables, 0 rejected), 0 stage failures, CLAIM MATCH RATE 0.8229 (79/96 numbers), 5 contradictions, 19 corrections.

M0 KILLS THE INHERITED CLAIM THAT GATED EVERYTHING. 'Raw hidden states were saved nowhere' is FALSE: LANE_B/out/harvest holds 104 npz (NOT the claimed 109), containing 4200 arrays of shape (1152, 2560) float16 keyed `item|win|{EARLY,LATE}|{13..22}`, for 4 lineages x 5 lesion strengths. M1 therefore got its STRONG form (probe fitted on alpha=0.00, scored on alpha>0) at zero GPU cost. Stored curves reproduce: D_curve EXACT_MATCH at 1.000 for L1-L3, D_matched_probe_curve RECONCILED within 0.005-0.015. Read site is per-lineage (lastp 29/22/23/29), not constant.

HEADLINE (M1) - A SITE DISSOCIATION AUROC CANNOT SHOW. The 1.000 belongs to the crude `damage` corpus and is AT ITS CEILING in the unperturbed control, so it could not fall. Re-expressed as TPR@1%FPR on the SAME activations (alpha 0 -> 1, mean over 4 lineages): EARLY/prompt site dAUROC -0.0068, dTPR@1%FPR +0.0007 (FLAT - the harmful REQUEST is still recognised); LATE/response site dAUROC -0.0137, dTPR@1%FPR -0.1439, a 10.5x larger movement in the operating point than in AUROC. So 'the representation survives the lesion' is TRUE at the prompt site and FALSE at the response site - recognition-vs-execution made measurable. Equivalence (TOST, margin 0.05 TPR units, both windows, Holm on the primary window): EQUIVALENT at alpha<=0.50, NOT_EQUIVALENT at 0.75-1.00. Lineage pairs: base->instruct +0.245 NOT_EQUIVALENT, instruct->SafeRL +0.063 NOT_EQUIVALENT, base->NON-safety-FT +0.029 INCONCLUSIVE (the load-bearing control behaves).

THE COMMISSIONED FEW-PROMPT AXIS WORKS. Restricted-budget AUROC at k=16 (unlesioned): Base 0.528 ~ NonSafetyFT-STaR 0.540 << Instruct 0.679 < SafeRL 0.698. Tracks SAFETY tuning, not fine-tuning as such, from 16 labelled items.

M6 SPECIFICITY FAILURE. All 19 quoted judged behavioural numbers recomputed MATCH. But K1/A moves 4.14 null-SD on the granite pair, a behavioural NO-OP (d harmful-compliance 0.000) whose child only carries 'abliterated' in its repo name: scored on the label it looks right, scored on the MEASURED delta it is caught. T1 is INCONCLUSIVE_UNDERPOWERED (n=5, achieved margin 28.4 null-SD), T2 rho -0.103 against a min-resolvable |rho| 0.878, T4 SATISFIED. UNIT MISMATCH DISCLOSED: the prereg margin is in TPR units (M1) while M6's outcome is in null-SD, so no cross-scale equivalence verdict is licensed or claimed.

REPAIRS. M2: 9 of 20 scaled outcomes SATURATED, plus 8 INDETERMINATE_NO_MATCHED_POINT rows lifted out of the limitations. M3: three protocols, not one - A at-band 0.0433-0.2346 (NOT the quoted '0.04-0.09'), Lane B 0.139-0.186, Lane C 0.057-0.603 over 7 families; HARC contradiction WITHDRAWN (a cross-concept pair REPLICATES HARC); the 1596-row rotation matrix shows instruction tuning rotates the request axis MORE (|cos| 0.200) than abliteration (0.361), content axis 0.90-0.99 across trained pairs, RandInit null 0.009-0.020. M4: 112 gate rows, compliance A 0.44 / B 1.00 / C 0.69; three lanes fit three different axes under one name and reach OPPOSITE stability verdicts; K3 re-scored FAIL under its own rule -> no candidate passes S1. M5: all 6 k rungs, k=0 explicit as NOT_RUN_BY_LANE_C (never imputed); the 0.882 scan located, MATCHED, non-monotonic. M7: 70 rows, attenuation ceilings, regex-vs-judge recomputed, B7 below the random floor. M8: substrate provenance (TOTAL_L=80, slots 8/46, NOT 144), dataset gates located in gen_art_dataset_1 (hazard 0.9429 vs 0.95; 96->85; placebo median ratio 1.25 vs 1.10), causal arm EMPTY (1 of 8 jobs), shuffled band 11.04-11.78 trained vs 1.268 RandInit with A escaping 0/7.

RUN INVARIANT ENFORCED AS A COLUMN. Every row of all 12 tables carries READOUT_CLASS; 2039 rows are result-eligible (activation/weight), 309 are BASELINE_ONLY (logit/text/metadata). evalkit/selfcheck.py REJECTS a table missing the column, and prose naming a baseline-class readout as the answer. Nothing is framed as jailbreak or attack-success reporting.

HANDOFF to the experiment lanes: (1) generated text from the lesioned models - needs a RE-RUN; (2) operating-point statistics for the 21-checkpoint panel - Lane C stored only AUROC scalars; (3) a scored mlabonne/Qwen3-4B-abliterated row, present in every Lane A table but absent from Lane C's panel and Lane B's harvest.

ARTEFACTS: eval.py + evalkit/ (paths, prereg, stats, selfcheck, laneb_substrate, m0-m8); EVAL_REPORT.md opening with CONTRADICTIONS then the claim match rate; eval_out.json (exp_eval_sol_out, 23 metrics_agg, 12 datasets) + full/mini/preview; 12 CSVs and 8 JSONs under results/, EVERY ROW CARRYING ITS SOURCE FILE PATH.

## Dependencies

- `art_2QM9uBviY4Wk` — re-analyses
- `art_2sz7g3MD4_y3` — re-analyses
- `art_rpTmjn5qclSY` — re-analyses

## Output Files

- `eval.py`
- `full_eval_out.json`
- `mini_eval_out.json`
- `preview_eval_out.json`

## Demo Files

- **eval.py** — Evaluation script with metrics computation

---
*Generated by AI Inventor Pipeline*
