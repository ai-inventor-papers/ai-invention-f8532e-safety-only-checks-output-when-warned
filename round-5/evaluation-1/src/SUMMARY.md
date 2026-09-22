# Recheck every blocking number from disk

Iteration-5 evaluation artifact. **Zero GPU, zero API spend ($0).** No new method, no new data: every number below is re-derived from the JSON and `.npy` files already written by iterations 2-4.

> **Governing rule.** The DISK is authoritative. Where a re-derived value disagrees with a value quoted in the hypothesis, the artifact direction or an earlier paper draft, the disk value wins, the prose value is recorded as a CONTRADICTION, and nothing on disk is edited to match prose.

## 1. Contradictions ledger and claim match rate

**claim_match_rate = 0.6866**  (46 MATCH / 67 verifiable claims)

- MATCH: 46
- MISMATCH: 21
- UNVERIFIABLE: 1 *(reported separately, never in the denominator)*
- SOURCE_ABSENT: 0 *(reported separately, never in the denominator)*
- claims checked in total: 68

Tolerances fixed in `prereg_eval.json` before the first numeric load: counts EXACT; rates and effect sizes |delta| <= 5e-4; nats <= 1e-3; correlations <= 5e-3.

*Post-hoc secondary, NOT the primary metric:* under a rounding-aware rule (a value quoted to k decimals matches if the re-derived value rounds to it) the rate is **0.7612** (51 / 67). The gap between the two rates is the share of frozen-rule mismatches that are rounding of quoted prose; the remainder are substantive.

*Ledger adjudication* (`src/adjudicate_ledger.py`, full record in `results/ledger_adjudicated.json`): 3 duplicate claim(s) dropped, 3 withdrawn as category errors, 6 explicit overrides with stated reasons, and 5 agent verdicts reversed by applying the frozen tolerance uniformly. One rule, applied to every claim.

### 1.1 The 21 contradictions

| # | claim | published value | re-derived value | source |
|---|---|---|---|---|
| 1 | The primary_effective_pairs list (9 pairs) is the complete EFFECTIVE set under the frozen count rule. | `9` | `{'primary_effective_pairs': 9, 'frozen_count_rule': 10, 'literal_reclassification_clause': 11}` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 2 | iteration-3 called the AMD-OLMo SFT->DPO stage a behavioural NO-OP. | `NOOP (behavioural description)` | `AMBIGUOUS` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 3 | prereg_eval.json's run_invariant classifies AMS as a WEIGHTS-only baseline readout (grouped with B7). | `weights-only` | `activation (reads hidden-state activations at raw-text prompts via ams_reimpl.py/harvest_ams; A_ams.npy is an activation array, not a weight tensor)` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 4 | instruct (parent) |N6| magnitude claimed 1.87 (paper Table qwen_arms), same-source comparison with the abliterated value below | `1.87` | `2.66` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 5 | abliterated |N6| magnitude claimed 1.79 (paper Table qwen_arms), same-source file as the parent | `1.79` | `2.223` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 6 | [separately labelled, exp_1 pipeline only] abliterated |N6| (Cohen's d, no-op/effective screen own-fit axis) claimed 1.79 | `1.79` | `1.781` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 7 | [separately labelled, exp_1 pipeline only] instruct (parent) |N6| (Cohen's d, no-op/effective screen own-fit axis) claimed 1.87 | `1.87` | `4.127` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 8 | Contribution 2 restated as '12 of the 18 cells in which the direction is decodable are inert' (instruct model, N6-on-over-refusal 18-cell grid) | `{'decodable': 12, 'inert_of_decodable': 12}` | `{'decodable': 12, 'inert_of_decodable': 11, 'causal_of_decodable': 1, 'causal_cells': ['P_B5']}` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 9 | Paper text: 'this decodable but inert pattern holds in 12/12 instruct cells ... at the prompt site' (F_on_refused_harm P-band cells + N6_on_over_refus | `12/12 decodable-but-inert` | `{'n_decodable': 12, 'n_inert': 11, 'n_causal': 1, 'causal_cells': ['P_B5']}` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 10 | Paper table caption/prose: BL1 (double-norm, iteration-2 lens) reads 3.07 for Instruct and 4.99 for SafeRL -- checked against BOTH BL1_easy and BL1_ha | `{'instruct': 3.07, 'SafeRL': 4.99}` | `{'instruct': 4.9917748928070065, 'SafeRL': 3.073007822036743}` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 11 | BL1_truelogit (single-norm fix), literal EASY gap, claimed 7.498 (SafeRL) | `7.498` | `7.462` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 12 | The expected permutation critical |rho| at n=10 is 0.648 (should match results/panel_size_curve.json critical_rho_by_n['10'] and this module's own re- | `0.648` | `{'disk_panel_size_curve_json': 0.6363636363636364, 'this_modules_independent_rerun': 0.6363636363636364}` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/ge` |
| 13 | The expected 80%-power MDE at n=10 is 0.80 | `0.8` | `0.82` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/ge` |
| 14 | the registered global-ablation causal band is B5 | `B5` | `B4` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 15 | The keyword proxy falsely reports harmful-request refusal falling 0.79 -> 0.15 (instruct, arm F, site P). | `{'from': 0.79, 'to': 0.15}` | `{'from': 0.7916666666666666, 'to': 0.14583333333333334}` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 16 | decode-site R (own-coefficient) displaces ~1.4x (F) / ~2x (N6) more than the treatment arm (deviations.json 'decode_site_R_displacement', derived from | `{'F': 1.4, 'N6': 2.0, 'source': 'smoke run'}` | `see r_displacement_validity.summary_by_site in table_causal_grid.json (real instruct/saferl/abliterated cells, not smoke)` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 17 | POS positive control RD_harm at B4 is approximately -4.170 | `-4.17` | `-4.16` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 18 | BL1's median no-op displacement is 0.150-0.178 null SD | `[0.15, 0.178]` | `{'BL1_easy': 0.150046515957551, 'BL1_hard': 0.17429153814908704, 'BL1_truelogit': 0.1780189144831297, 'BL1_truelogit_hard': 0.09179908019558866}` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 19 | BL1's median no-op displacement is 'near 6x' the activation readouts' (BL1_easy numerator). | `6` | `6.228` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 20 | Falcon3 batch-8 padding bug shifts AMS by 5.3 sigma (iteration-4 execution record). | `5.3` | `5.283` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |
| 21 | Falcon3 batch-8 padding bug shifts AMS by 5.0 sigma (artifact direction). | `5` | `5.283` | `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/ge` |

### 1.2 The 1 claims that could not be checked

| # | claim | verdict | reason |
|---|---|---|---|
| 1 | Paper Table qwen_arms OR column ('XSTest twins'): Instruct=0.11, SafeRL=0.00 | UNVERIFIABLE | Searched graded_truth.json / graded_truth_s1.json per_ckpt labels for both checkpoints: the only benign item ids present are 'orh_*' (OR-Bench-Hard, n=45); no 'xstest'/'xs_*'-prefi |

## 1b. Key findings

Each finding below is re-derived from disk. Section numbers refer to the deliverables.

**1. The effective set is 10 pairs by the frozen rule, not 9 (D1, D4 addendum).** classification.json's own count rule counts 'constructed + primary harvested + AMD count when observed EFFECTIVE'. HG::AMD-OLMo-1B SFT->DPO was planned as a harvested no-op and observed EFFECTIVE (dHC +0.318), so it belongs in the set. F1__cautious (constructed, observed EFFECTIVE) is also omitted, although F1__dpo is counted under the same reclassification clause, so a literal reading gives 11. The iteration-3 'no-op' verdict and the iteration-4 'EFFECTIVE' verdict on AMD SFT->DPO do NOT disagree because the item sets differ: both use the same 45 Lane C items (HC 0.578 -> 0.556). They disagree because of GENERATION PROVENANCE: the reused generations (H::) give AMBIGUOUS, the GPU-regenerated ones (HG::) give EFFECTIVE. Recomputing every sensitivity denominator (26 of 32 candidates reproduce the official k/9 exactly; the rest are withheld, not guessed) changes the hit count of exactly one candidate, B7 (7/9 -> 8/10). That candidate is the weights-only scar baseline, and its extra hit comes through the documented OLMo all-ones-null artefact: the null-projected variant stays 6/10. No activation readout detects the tenth pair.

**2. The defensible false-alarm comparison is 4/12 vs 1/12, and it is underpowered (D2).** On all 15 no-op pairs the logit baseline false-alarms on 6 and N1 on 1 (exact McNemar b=6, c=1, p=0.125). Three of those 15 are head-only W_U edits where every activation delta is bitwise 0.0, so the activation readouts' silence there is ANALYTIC. On the 12 non-degenerate pairs the comparison is 4/12 vs 1/12 (b=4, c=1, exact p=0.375). With 5 discordant pairs the smallest attainable p is 0.0625, so this is UNDERPOWERED, not a negative. The claim that survives: a readout that fires on a behaviourally inert head-only edit is still a false alarm in deployment.

**3. There is no false-alarm/sensitivity trade-off inside the activation class (D4).** Spearman rho between false-alarm count and sensitivity is POSITIVE everywhere: 0.406 within the activation class, 0.482 with the two AMS rows, and 0.596 across all 32 candidates. The claim 'the trade-off runs through the activation class' needs this to be materially negative, so it is NOT supported: readouts that fire more on no-ops also fire more on real edits. The activation false-alarm range is 0-3 of 15, as claimed.

**4. Judged refusal is bounded, not merely null (D5, D6).** No site-local intervention moves judged refusal of harmful requests by more than 0.056 (instruct, arm F, P_B4), against median MDE80s of 0.067 (instruct), 0.061 (SafeRL) and 0.098 (abliterated). TOST at those margins declares equivalence in all three models (p = 3.7e-24, 1.3e-25, 9.7e-10). The abliterated FLOOR (arm-0 refused_harm 0.188, over-refusal 0.042) is why its grid is only 6 cells at site P. The over-refusal lever is present in BOTH models at B4-B5 with comparable magnitudes; the sole Holm-18 survivor (instruct N6 @ P_B5, -0.146) ranks 4th by |effect| behind SafeRL arm-F at B4 (-0.188) and B5 (-0.167). The global-ablation band is B4, not B5 (SafeRL-minus-instruct DiD +0.229 [0.083, 0.375], sign confirmed from the raw arms). The registered DiD matches its predicted sign in 8 of 18 cells: NOT SUPPORTED. The random control R displaces 2.5x (D') and 2.0x (E) MORE than F off site P, not 1.4-2x, so 'net of a matched random control' is literally true only at site P. No judged-refusal positive control existed in iteration 4.

**5. The bitwise explanation is deleted; the mechanism is measured (D8).** With identical weights, only 25.6% of greedy texts are identical across CPU and GPU, yet 96.5% of harm labels agree, and two activation readouts (N11 and C13_peak_d) fire on the fp16 no-op. The false-alarm gap is displacement magnitude times null tightness: the logit baseline moves 6.23x more than the median activation readout on no-ops (BL1_easy numerator; 3.8x-7.4x across the four baseline variants).

**6. Part 3 of the commission: a cheap activation readout DETECTS abliteration but cannot yet RANK models, and 'few' means ~32 prompts, not 0-4 (D7).** Detection: the held-out request-axis d (peak d, iteration-2 protocol) drops on 8/8 effective abliterated pairs, every CI wholly below 0 (6/6 on the iteration-2 panel, 2/2 fresh in iteration 3), and does not move on the granite null edit (+0.091, CI covers 0). This is readout- and harvest-specific: iteration-4's N1 (d at a fixed l*, regenerated harvests) drops significantly on only 3 of 5 scored abliterated models and significantly RISES on mylesgoose (+0.776 [+0.086, +1.226]), the same model whose peak d fell. Prompt budget: on H::mlabonne--Qwen3-4B-abliterated (child) vs Qwen--Qwen3-4B (parent), N1's resampled interval first clears the no-op band at k = 32 prompts, the largest k tested. k = 0 (card regex, weights-only scar) is a DIFFERENT readout class, not a cheaper version of the same readout. Ranking: whether an activation readout ranks checkpoints by harmful compliance better than the logit baseline cannot be settled at n = 10. The preregistered rule puts the panel at about 55 checkpoints; the matching power calculation for the paired difference (Williams' t, rho(B3,BL1) = 0.6485, recovered exactly on the n = 10 Spearman lattice) gives 80% power at about 30 at the observed margin. That is optimistic because B3 was the best of ~30 rows, and at half the margin it needs about 150. Honest answer: roughly 30-150 checkpoints, not 10.

**8. The 'BL1 ranks SafeRL below instruct' claim is withdrawn as a general claim (D3).** The iteration-2 lens applies final_norm twice, so BL1 is read on norm(norm(h_L)). Under that double-norm convention (BL1_hard: instruct 4.99, SafeRL 3.07) SafeRL ranks below instruct. The draft's sentence swaps those two numbers, although its own table has them right. Under the single-norm fix (BL1_truelogit: 6.651 vs 7.462) the order inverts. On the iteration-3 n = 10 held-out panel the two conventions rank identically (rho +1.00), so the flip is VARIANT- AND PANEL-SPECIFIC: it appears only for the instruct/SafeRL pair among the 4B arms. Over-refusal is not ordered either. On exp_1 OR-Bench-Hard (n = 43) instruct 0.465 vs SafeRL 0.349, with SafeRL minus instruct CI [-0.291, +0.056]. On exp_2 held-out hard-benign (n = 48) the values are 0.438 vs 0.479, CI [-0.126, +0.208]. Both CIs cover 0, so the two sets' 'disagreement in order' is within noise. The XSTest-twin pair (0.11 / 0.00) cannot be located on disk. 'N1 and AMS sigma rank them correctly' is WITHDRAWN: there is no reliable order to rank against, and AMS sigma was never computed for the Qwen3-4B family.

**9. Abliteration ROTATES the benign-side direction; it does not preserve its magnitude (D9).** The F direction cosine to the parent is 0.999 / 0.994 / 0.943 at B1-B3 and 0.412 / 0.306 / 0.328 at B4-B6. The N6 cosine falls from 0.997 at B1 to 0.021 / 0.027 / 0.061 at B4-B6, i.e. nearly orthogonal (all within tolerance). The claimed magnitudes (|N6| 1.87 parent vs 1.79 abliterated) are reproduced by NO source on disk. The same-source separability readout falls 2.66 -> 2.22 (-16%). The rotation dominates, so a parent-anchored readout misses the change and a self-fitted one does not; the magnitude drop is real but secondary. cos(F_instruct, F_SafeRL) is >= 0.84 in every band (min 0.841), which is what makes the redundancy argument non-trivial. Contribution 2, corrected: 12 of the 18 cells are decodable (AUROC CI lower bound > 0.60), and 11 of those 12 are inert for judged refusal. The 12th, P_B5, is the one Holm-18 survivor, so the draft's '12/12 inert' contradicts its own causal result.

**7. Backstop join: COULD_NOT_COMPLETE (D11, checked 2026-09-22T00:47 UTC).** Two independent gaps. (1) SCREEN: no survivor.json exists anywhere under iteration 5; the screen artifact (gen_art_experiment_1) has an EMPTY results/screen/ directory, so no hashed survivor has been committed. (2) SUBSTRATE: panel_manifest.json is committed but lists n=0 checkpoints that completed the gated pipeline. A join needs both sides and cannot be formed; a survivor is NEVER guessed. Both sides are parallel iteration-5 artifacts still running at check time; the substrate had written 6 blind label file(s), recorded by name and time only, never opened. The precedent is iteration 3's join_stub.json: record the state, never fabricate a join.

## 2. Self-check gate

- gate passed: **True**
- deliverables produced: 11 / 11 (D1, D10, D11, D2, D3, D4, D5, D6, D7, D8, D9)
- table rows emitted: 1324; rows missing provenance: 0
- candidate table rows: 32 (gate requires >= 32)
- prereg sha256 re-asserted: `3e9b77b5eef00369ab1aa62dd1dd09ae8051a46f69183d10e3e156dad9681482` (unchanged)
- model-weight-sized files in the workspace: 0
- sentences naming a baseline-class readout as the deliverable: 0

Gate rule (b) enforces the run invariant: the deliverable is the activation-level comparison of the three Qwen3-4B models, and any metric built from it reads activations or weights of a single model. Logit-only and text-only readouts are treated throughout as baselines.

## 3. Deliverables

### D1. Composition table - every NOOP and EFFECTIVE pair, recipe histogram re-derived

`results/table_composition.json` - produced
- `n_primary_noop` = 15
- `n_primary_effective` = 9
- `n_pairs_total` = 56

### D2. Structural degeneracy and exact McNemar on both denominators

`results/table_degeneracy.json` - produced

> **discussion:** The activation-readout invariance on the wu05/wu20 and sysprompt/cautious cells is ANALYTIC, not empirical: it follows deductively from which array is edited (the unembedding matrix, or the chat-template wrapper) versus which array a given readout consumes (pre-unembedding hidden states, or raw-text-only AMS activations). No amount of additional data collection would move these deltas off exactly 0.0, so they carry zero evidential weight for either 'the readout is well-behaved' or 'the readout is broken'. What DOES survive this concession: a false alarm rejects a checkpoint that a human auditor would call unchanged. A readout that fires on ANY cell here -- including cells outside this degenerate set, such as BL1_easy's non-degenerate false alarms on F1__int8wo, F1__sysprompt, F3__int8wo and F1__int8bnb -- is a false alarm in deployment regardless of whether the underlying delta was analytically forced to zero or was a genuine near-zero measurement; the degenerate cells matter only for correctly SIZING the false-alarm denominator (15 vs 12), not for excusing false alarms elsewhere.

### D3. Baseline-variant flip across the five Qwen3-4B arms

`results/table_bl1_variants.json` - produced

### D4. All candidate readouts: false alarms against sensitivity

`results/table_candidates32.json` - produced
- `n_rows` = 32

### D5. Full causal depth x site grid, Holm-18 recomputed within model

`results/table_causal_grid.json` - produced
- `seed` = 20260921
- `b_boot` = 2000
- `n_rows_grid` = 756

### D6. Equivalence bound on judged refusal and the arm-0 floor

`results/table_equivalence.json` - produced

> **bound_statement:** BOUND: no site-local activation intervention (own-request axis F, benign-twin axis N6, or its orthogonal complement N6perp) produces an effect on judged refusal larger than about 0.056 in magnitude, at any depth band or generation site measured, in any of the three Qwen3-4B variants (instruct, SafeRL, mlabonne abliterated).
- `seed` = 20260921
- `b_boot` = 2000

### D7. Few-prompt feasibility: k-curve and the required panel size

`results/table_fewprompt.json` - produced

### D8. Measured displacement replacing the bitwise explanation

`results/table_displacement.json` - produced

> **mechanism_statement:** No-op edits are NOT bitwise identical at the activation level (except the two structurally-degenerate wu05/wu20 arms, whose input and residual body are unchanged by construction). Numerical-precision, system-prompt and re-save edits move most activation readouts by a small but measurable amount, and a minority of activation- and weight-class readouts do cross their own bootstrap CI on individual no-op pairs (e.g. F1__fp16, F3__dpo). The false-alarm gap between the logit-only baseline (BL1) and the activation readouts is therefore NOT explained by bitwise identity; it is explained by (a) MAGNITUDE -- BL1's median no-op displacement is 0.174 null SD (BL1_hard) vs a median of 0.024 null SD across activation-class candidates, roughly 7.2x larger -- combined with (b) a TIGHTER NULL -- the activation readouts' own bootstrap null distribution is narrower relative to their displacement, so fewer of their no-op CIs cross the false-alarm threshold even though the underlying displacements are nonzero.
- `ratio_bl1_over_activation` = 7.234
- `n_rows` = 32
- `n_noop_pairs` = 15

### D9. Rotation-versus-magnitude geometry of the safety directions

`results/table_geometry.json` - produced

### D10. Experimental setup, appendix content and deviations

`results/table_setup_deviations.json` - produced

### D11. Backstop confirmation join with hash-order verification

`results/join_backstop.json` - produced

> **reason:** Two independent gaps. (1) SCREEN: no survivor.json exists anywhere under iteration 5; the screen artifact (gen_art_experiment_1) has an EMPTY results/screen/ directory, so no hashed survivor has been committed. (2) SUBSTRATE: panel_manifest.json is committed but lists n=0 checkpoints that completed the gated pipeline. A join needs both sides and cannot be formed; a survivor is NEVER guessed.

> **join_status:** COULD_NOT_COMPLETE

### D4+. Addendum: sensitivity at the 10- and 11-pair effective sets the frozen count rule implies

`results/table_sensitivity_denominators.json` - produced
- `official_effective_n` = 9
- `effective_n_under_frozen_count_rule` = 10
- `effective_n_literal_reclassification` = 11
- `n_candidates` = 32
- `n_candidates_reproduced_exactly` = 26

### D7+. Addendum: power for the paired correlation difference (Williams' t)

`results/table_panel_power.json` - produced

> **statement:** Preregistered rule (D7d): the permutation critical |rho| falls below the observed margin 0.270 at n=55. The matching power calculation for the paired difference (Williams' t for dependent correlations sharing HC; Gaussian copula at the observed correlations; rho(B3,BL1) = 0.6485, the root of the partial-correlation equation that lies on the n=10 Spearman lattice) gives 80% power at about 30 checkpoints and 50% power at about 15. So at the OBSERVED margin the preregistered rule is conservative: B3 and BL1 are strongly correlated with each other, which shrinks the variance of their difference. But the observed margin is optimistic, because B3 was the best of ~30 rows on a 10-checkpoint panel. If the true margin is half the observed one, 80% power needs about 150 checkpoints. The honest range is therefore about 30 checkpoints (optimistic) to about 150 (margin halved), against the 10 that were run: the ranking question cannot be settled at n=10.
- `rho_B3_BL1_true_root` = 0.6485

## 4. Provenance

- `prereg_eval.json` was frozen and hashed BEFORE the first numeric load; `build_log.txt` is append-only and records the order.
- `results/source_manifest.json` records absolute path, size, mtime and sha256 for every source file read.
- Every emitted table row carries `source_file`, `source_key` and `readout_class`.

