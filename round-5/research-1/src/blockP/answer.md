**L1 — SATURATION VERDICT, dated 2026-09-22: W1 OPEN, W2 PARTIAL, W3 OPEN, W4 OPEN, W5 OPEN (inherited evidence), W6 OPEN (inherited evidence), W7 PARTIAL, W8 PARTIAL, G1 PARTIAL, G2 OPEN, G3 PARTIAL, G4 OPEN; the CLOSED ones are NONE.** No published paper or live tool computes any of the twelve as one parent-free number per checkpoint used to compare checkpoints. The nearest neighbours are SafeSeek for W2 [13], Conditional Co-Ablation for W4 [12], Any-Depth Alignment for W3/W7 [14], Jorak and OBLITERATUS for W8 [19, 18], and Galeone for G3 [15].

**L2 — OVER-REFUSAL-AS-TARGET: OPEN, dated 2026-09-22.** None of 14 scored papers relates a per-checkpoint internal number to over-refusal across ≥3 checkpoints as a predicted target. The nearest miss is "First Token Matters" [20]. The decisive paper 2606.08044 never correlates its latent score with its over-refusal column [29].

**L3 — DIMENSIONALITY: no factor-analytic or effective-rank treatment of a family of INTERNAL safety scores exists as of 2026-09-22.** The P1 bound is therefore a contribution. P1 must still be positioned against the output-level IRT factor analysis [33] and against the refusal-subspace rank debate [35, 36, 37, 38, 39].

**L4 — Self-verification:** 48/48 quoted passages re-fetched against their own URL by a different agent from the finder (44 full-sentence, 4 by ≥2 anchor windows after PDF line-wraps). 4 composite quotes deleted and 5 paraphrases relabelled out of quote fields (logged). 8 zero-match absence claims reproduced with same-URL positive controls, kept separate. 3 screening regexes found misfiled as absences and reclassified. 23/23 arXiv ids resolved, 0 NOT_FOUND. 3 anchors recovered beyond the fetch horizon, kept separate.

## Corrections this pass forces (read first)

1. **"Spagliardi" is real, and the plan's fallback is wrong.** Fabio Spagliardi is first author of arXiv:2606.20626, "Efficient Safety Benchmarking via Item Response Theory" (2026-05-26) [34]. The plan said to record NOT_FOUND and substitute 2608.05086. Do not do that. The two papers are distinct and each owns a different claim:
   - 2606.20626 owns *few-item behavioural safety evaluation*. It cuts cost by ≥80% where Spearman ρ>90% is attainable, and by up to 99.9% on AIR-Bench 2024 [34].
   - 2608.05086 owns the *factor structure* of safety benchmarks [33].
   There is no name mismatch to flag.
2. **The Basu caution is false.** The handbook does print "Basu et al., 'Interpretability without actionability', arXiv 2603.18353" (SOURCES.md row S3). The attribution checks out [42]. Use it as a premise, scoped to its single clinical domain.
3. **The JailbreakBench premise is false.** No existing entry misattributes JailbreakBench to Mazeika: iter-4's bibliography had neither benchmark. Both are now added, verified: JailbreakBench is Chao et al., 2404.01318, NeurIPS 2024 D&B [40]; HarmBench is Mazeika et al., 2402.04249 [41].
4. **A composite quote distorted a source on the exact point W3 turns on.** A lane quote from Any-Depth Alignment ended "…the last [prompt token do not]". The actual Figure 3 caption says features "from the last generated token (top) remain entangled" [14]. It was deleted and replaced with the verbatim sentence.
5. **The reimplementation agreement figure needs rewording.** "<1e-4" holds for the *relative* difference (max 7.3e-05) but not the absolute one (max 3.8e-04 σ). Write: "agreement to within 7.3e-05 relative (3.8e-04 σ absolute) at batch 1".
6. **The workspace bibliography base was wrong.** A prior session had copied iter-4's 47-entry intermediate file, which dropped the Duan and First-Token entries. It is now rebased on the final 54-entry file and amended to 61.

## W4 attribution sentence (use verbatim)

"Self-repair / backup behaviour under ablation is established in the circuits literature (McGrath et al. 2023, arXiv:2307.15771; Rushing & Nanda 2024, arXiv:2402.15390, ICML 2024) [9, 10]; W4 is a per-checkpoint scalarisation of that known phenomenon, not its discovery."

Also cite:
- backup name-mover heads [11];
- Conditional Co-Ablation as the nearest quantitative neighbour [12]. It is "a label-free, output-grounded score that asks how much each remaining unit's ablation effect grows once a primary set has been removed", and it is per-unit and per-circuit. An informal blog comparison of self-repair between two GPT-2 variants [51] is likewise never scalarised per model and is not peer-reviewed.

Checkpoint-framing regex on its PDF: 0 matches, against a control of 143 matches for "ablation" [12]. The forward-citation sweep screened 100 citing papers of the Hydra Effect (API-capped) and all 36 citing Rushing & Nanda [46, 47]. It found no per-model self-repair scalar. Rushing & Nanda themselves stress that self-repair "is imperfect" and "noisy" across prompts [10]. So W4 must be reported as a distribution over prompt draws, never as a bare mean.

## The saturation table, candidate by candidate

- **W2 PARTIAL.** SafeSeek localises "an alignment circuit with 3.03% heads and 0.79% neurons, whose removal spikes ASR from 0.8% to 96.9%" [13]. That is a joint-ablation circuit size per scenario, not a k-of-6-band depth scored across checkpoints. A LessWrong post finds refusal "mediated redundantly across layers" on one model [50].
  - Write W2 as *applying* a redundancy notion to safety bands against a new target, and cite both.
- **W3 OPEN.** Any-Depth Alignment finds safety concentrated in assistant-header tokens but never computes an all-position/last-token ablation ratio (zero-match with a token-count control) [14].
- **W7 PARTIAL.** The same paper reads decode-depth separability via probes and re-injection, not ablation with a random control [14].
- **W8 PARTIAL.** Neither Jorak nor OBLITERATUS self-administers a lesion and refits:
  - Jorak ships "Weights — spectral signature (SVD) (the smoking-gun, CPU, no inference)" with global, band and subspace alignment signals, parent-free [19];
  - OBLITERATUS computes cross-layer consistency and angular drift, explicitly not a joint-ablation scalar [18].
  Jorak was re-located live at github.com/JolanMc/Jorak, so iter-2's kills on it stand.
- **G1 PARTIAL.** 2602.02132 computes cosines among 11 refusal-category directions, not harmful-vs-benign-twin [17].
- **G2 OPEN.** Zero-match on 2602.02132, with a control of 236 matches [17].
- **G3 PARTIAL.** Galeone's cosine "is computable from the weights and consistent across four models (cos ∈ [0.12, 0.20]…)" and is shown not to predict steerability [15]. It is a different pair of directions from G3's fitted axis versus the model's own written residual update.
- **G4 OPEN.** Logit-Gap Steering reads the refusal–affirmation rows directly, never their orthogonal complement [16].
- **W1, W5, W6 OPEN.** No work ablates an early-band axis, reads the late-band projection change and nets a matched-norm random control. W5 and W6 have **no own zero-match**: their support is inherited from W1's Galeone control, so hold them to a weaker standard than W1.

The handbook's silence was checked as a fact, not assumed: 0 matches on all nine redundancy and self-repair terms, against positive controls of 8, 16, 29 and 11 on other terms. Its directive holds — "Map-silence means *not-yet-checked*, NOT *open*" — and "the measured base rate for unchecked lanes in this forge is 11/11 occupied." An OPEN result runs against that stated base rate, which is a reason for extra scrutiny: the verdicts here rest on dated, logged, control-backed searches, and a CLOSED paper surfacing later would flip them.

## Over-refusal-as-target: the three-part test

A paper closes the cell only if it does all three: (i) one internal number per checkpoint for N≥3 checkpoints; (ii) that number related to those checkpoints' benign-set over-refusal; (iii) over-refusal treated as a target, not a side-effect check.

- **2609.18471 fails (iii), and (i) as well.** It measures over-refusal "using the XSTest dataset… employing DeepSeek-Chat" as the outcome of its own steering defence [20]. It covers two checkpoint families, so it also misses N≥3.
- **2609.00760 is the secondary miss.** It has an XSTest-safe over-refusal column ("Safe Ref.↓ measures the fraction of safe prompts…") and a probe-accuracy column in the same paper. The two are never correlated (zero-match "correlat", with a control) [32].
- **2606.08044, special attention — does not close.** "correlat" returns 0 matches, against controls of 4 for over-refusal and 49 for LVS. Its over-refusal column (0.00–0.04) is used as an *insensitive* static audit, i.e. a negative control, not a predicted target [29].
- **Other rows:**
  - Duan predicts monitor staleness, not over-refusal [22];
  - Hurtado's hard negatives are benign *fine-tunes*, not benign prompts [26];
  - AMS [1], N-GLARE [23] (keyword refusal on harmful prompts), RAS [24], Aligned Probing [25], 2603.27518 [27], 2608.09624 [28], 2607.09697 [30] and RISA [31] all report over-refusal as an outcome or not at all.
- Bonus: JailbreakBench's camera-ready itself ships "an over-refusal evaluation dataset" [40]. It is usable as a third benign set.

## Dimensionality (Block D)

IRT for AI Safety covers 8 benchmarks, 5,255 items and 192 models. Its three factors (refusal strictness, truthfulness, contextual harm) explain 77% of variance. Verbatim: "aggregated benchmark scores are hard to trust and interpret, because benchmarks duplicate one another, correlate heavily, and models may sandbag when they detect evaluation" [33].
- It is a factor analysis of BENCHMARK OUTPUTS, never of internal ones: an activation-terms regex returns 0, against 8 control matches.
- It is P1's nearest cousin and its strongest supporting analogy, one level up.
- 2606.20626 *assumes* a "unidimensional latent safety ability" per benchmark and never tests it [34].
- The most dangerous near-miss is "The Hidden Dimensions of LLM Alignment" [39]. Its low-rank safety residual space is one model's internal subspace, not a score family.

**The sentence the write-up must use:** "The dimensionality debated by Arditi et al. (2406.11717), Marshall et al. (2411.09003), Wollschläger et al. (2502.17420) and Winninger (2607.02396) is the rank of the refusal-mediating activation SUBSPACE inside a single model's residual stream, whereas the rank P1 measures is the effective rank of the CANDIDATE-READOUT-by-CHECKPOINT score matrix; a model can have a genuinely multi-dimensional refusal subspace while every cheap scalar readout still collapses onto one usable coordinate, and vice versa" [35, 36, 37, 38].

The four sides of that debate, verbatim:
- Arditi: "refusal is mediated by a one-dimensional subspace" [35];
- Marshall: an "affine decomposition" [36];
- Wollschläger: "multiple independent directions" [37];
- RFM-AGOP: behaviours are not encoded "along single linear directions" [38].

## Contribution branches

Blocks S and T both came back favourable, so **Branch 1 applies:**

- **(i)** A per-checkpoint false-alarm audit on BEHAVIOURALLY GRADED no-ops. It must survive three papers:
  - Duan: frozen probes "across twelve quantization, LoRA, merged-LoRA, and QLoRA update conditions", per-input, ungraded [22];
  - AMS: one-model INT4 drift "4.4%" [1];
  - Hurtado: a reference-anchored registry [26].
- **(ii)** Over-refusal as the TARGET of a per-checkpoint internal readout, reported beside the logit gap and AMS σ. Nearest miss: [20, 32].
- **(iii)** A per-checkpoint scalarisation of redundancy and self-repair, attributed as above.

**Branch 2**, if a later check closes W2 or W4: (iii) degrades to "applying <closer>'s quantity to safety bands against over-refusal". It must be written as weaker; (i) and (ii) stand.

**Branch 3**, if T closes: only (i) and the P1 bound survive. The correlation table demotes to a replication, and P1 becomes the headline. Full text: blockP/contribution_branches.md.

The only two novelty sentences the paper may assert:
- (a) "Nobody grades behaviour before calling a variant a no-op."
- (b) "Nobody uses over-refusal as the TARGET of a per-checkpoint internal readout."

## Must-not-claim ledger (23 items; must_not_claim.json)

Every carried iter-2/3/4 fence stands, with its owner:
- AMS [1] for few-prompt / reference-free / abliterated scoring;
- Orgad [43] for recognition vs generation;
- Jorak [19], Hurtado [26] and OBLITERATUS [18] for weights-only statistics;
- 2609.18471 [20] for decode-site readouts;
- Galeone [15] for logit-vs-activation comparison;
- 2609.04721 [21] and 2606.08044 [29] for random-direction controls;
- Basu [42] for the knowledge-action gap, as a premise only;
- "N-GLARE has no correlations" is false [23];
- the "0.016" figure is deleted.

New this pass:
1. No steering method or steering-reliability diagnostic (handbook: "Per-sample unreliability and the linear-approximation limit are characterized").
2. No SAE substrate and no circuit-discovery framing ("The most-worked lane in the field"). This is sharper now that W4's nearest neighbour is a circuits paper [12].
3. The four-way comparison must be distinguished from crosscoder diffing [44] and checkpoint tracking [45]. Sentence to use: *"Unlike crosscoder model diffing and training-dynamics checkpoint tracking, every quantity reported here is self-fitted and parent-free: no shared dictionary is trained across models, no checkpoint is compared against another checkpoint's basis, and each number is computable from one arbitrary HuggingFace repository alone."*
4. Few-item behavioural evaluation is owned by Spagliardi [34] and must be cited as the behavioural counterpart.

## AMS batch-1-vs-batch-8 instruction (hazard now measured, not inferred)

AMS HEAD is unchanged (e7ca0d1a…, 2026-08-27; PyPI 0.1.3) [48, 49]. It tokenizes with `padding=True` and no `padding_side`, then hooks `hidden_states[:, -1, :]` [2]. Transformers defaults to `padding_side: str = "right"` [3]. All five panel tokenizers omit the key [4, 5, 6, 7, 8].

**Instruction:** "AMS sigma must be reported at batch 1 AND at the released batch 8. The batch-1 number is the bar. Any batch-1/batch-8 difference is a padding artefact, observed up to 5.283σ on Falcon3-1B-Instruct (6.460→1.177, PASS→CRITICAL); the batch-8 number is footnoted, not used."

- With right padding and a last-position hook, every prompt shorter than the batch maximum is read at a PAD position. That is a bug in the released tool, not in our reimplementation.
- Qwen3-0.6B shifts 0.82σ.
- Left-padded Llama-3.2-1B shifts 1.4e-06σ. It is the natural control.
- These measurements are from iter-4 experiment_1's `ams_validation.json`, read, not run, by this lane.

## Bibliography rulings (references_iter5.bib, 61 entries; bib_changelog.json)

- **ADD:** Chao2024 [40], Mazeika2024 [41], Spagliardi2026 [34], McGrath2023 [9], Rushing2024 [10], Wang2022 [11], Gong2026 [12].
- **KEEP:**
  - Wollschlager2025 (already present) — cite wherever refusal is called a single direction;
  - Yamaguchi2025 — cite in the decode-site (W7) motivation.
- **PRUNE:** Li2023 (steering method; fence 1), Wei2023 (jailbreak framing, which the run invariant forbids), Meng2022, Yuan2024.
- **DELETE** the 0.016 figure. Do not substitute Galeone's 0.12–0.20.

## Confidence

- **High:**
  - AMS facts, which are code-read and measured;
  - bibliography, from live API metadata;
  - the 2606.08044 ruling, which rests on a control-backed zero.
- **Medium-high:** the W4 OPEN verdict, backed by a complete sweep of 136 citing papers.
- **Medium:**
  - W1/W3/G2/G4 OPEN, each backed by one nearest-neighbour control;
  - over-refusal OPEN. September-2026 arXiv volume is high, and a paper posted after 2026-09-22 could close it.
- **Low-medium:** W5/W6, whose evidence is inherited.
- **What would change the verdicts:** any paper scoring ≥3 checkpoints with one internal number against XSTest/OR-Bench over-refusal, or any tool emitting a per-model self-repair or joint-ablation depth.
