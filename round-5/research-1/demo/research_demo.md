# Is our redundancy safety metric already taken?

## Summary

Dated web-only prior-art closure pass, 2026-09-22, $0.00 spend. SATURATION: none of the 12 candidates is CLOSED. W1, W3, W4, G2, G4 OPEN; W5, W6 OPEN on inherited evidence only; W2, W7, W8, G1, G3 PARTIAL. Nearest neighbours: SafeSeek 2603.23268 (W2, per-scenario joint-ablation circuit size), Conditional Co-Ablation 2607.01940 (W4, per-unit self-repair score, 0 checkpoint-framing matches vs 143 control), Any-Depth Alignment 2510.18081 (W3/W7), Jorak (re-located live, github.com/JolanMc/Jorak) and OBLITERATUS (W8), Galeone 2606.24952 (G3). W4 attribution sentence written against verified anchors: Hydra Effect 2307.15771 and Rushing & Nanda 2402.15390 (ICML 2024). Forward-citation sweep of 136 citing papers found no per-model self-repair scalar. OVER-REFUSAL-AS-TARGET: OPEN across 14 scored papers. Nearest miss 2609.18471 fails the target test and N>=3; 2609.00760 has over-refusal and probe columns never correlated; 2606.08044 never correlates its LVS with over-refusal ('correlat' 0 matches, controls 4/49). DIMENSIONALITY: no factor-analytic/effective-rank treatment of a family of INTERNAL safety scores exists, so the P1 bound is a contribution. Position it against IRT-for-AI-Safety 2608.05086 (output-level, 3 factors, 77% variance) and The Hidden Dimensions of LLM Alignment 2502.09674; a verbatim sentence separating score-family rank from refusal-subspace rank is supplied. AMS: repo and PyPI unchanged; the padding hazard is now established from code AND measurement. All 4 Qwen3-4B tokenizers and Falcon3 omit padding_side, so they inherit HF's 'right'. Measured batch-8 shift is up to 5.283 sigma on Falcon3 (PASS->CRITICAL); left-padded Llama shifts 1.4e-06. Rule: batch-1 is the bar, batch-8 is footnoted. CORRECTIONS: 'Spagliardi' is REAL (arXiv:2606.20626), so do NOT substitute 2608.05086; the handbook DOES name Basu 2603.18353; no JailbreakBench/Mazeika misattribution existed (both benchmarks were absent, now added); a composite quote had turned 'last generated token' into 'last prompt token' and was deleted; reimplementation agreement is 7.3e-05 relative, not <1e-4 absolute. Verification: 48/48 quotes re-fetched by a non-finder; 4 composites deleted; 5 paraphrases relabelled; 8 absences reproduced with controls; 23/23 ids resolved. Bibliography: 61 entries (7 added, 4 pruned, 0.016 deleted). Must-not-claim ledger: 23 items with owners.

## Research Findings

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


## Sources

[1] [AMS: Detecting Safety Training Modification in Language Models via Activation Analysis](https://arxiv.org/abs/2608.05578) (Glen Messenger; 2026) — Incumbent bar; single-model INT4 drift <=4.4%; no over-refusal target; names token-level decoding analysis its principal open problem.

[2] [AMS source repository (activation-model-scanner)](https://github.com/GoogleCloudPlatform/activation-model-scanner) (2026) — Code-line evidence for the eight pinned facts and the padding hazard (extractor.py:130, 167-173).

[3] [transformers tokenization_utils_base.py](https://raw.githubusercontent.com/huggingface/transformers/main/src/transformers/tokenization_utils_base.py) — Class attribute padding_side: str = "right" -- the default inherited when tokenizer_config.json omits the key.

> padding_side: str = "right"

Locator: orchestrator re-fetch 2026-09-22

[4] [Qwen/Qwen3-4B tokenizer_config.json](https://huggingface.co/Qwen/Qwen3-4B/raw/main/tokenizer_config.json) — padding_side key ABSENT (control: model_max_length, pad_token present); pad_token <|endoftext|>.

[5] [Qwen/Qwen3-4B-Base tokenizer_config.json](https://huggingface.co/Qwen/Qwen3-4B-Base/raw/main/tokenizer_config.json) — padding_side ABSENT; pad_token and eos both <|endoftext|>.

[6] [Qwen/Qwen3-4B-SafeRL tokenizer_config.json](https://huggingface.co/Qwen/Qwen3-4B-SafeRL/raw/main/tokenizer_config.json) — padding_side ABSENT; pad_token <|endoftext|>.

[7] [mlabonne/Qwen3-4B-abliterated tokenizer_config.json](https://huggingface.co/mlabonne/Qwen3-4B-abliterated/raw/main/tokenizer_config.json) — padding_side ABSENT; pad_token <|endoftext|>.

[8] [tiiuae/Falcon3-1B-Instruct tokenizer_config.json](https://huggingface.co/tiiuae/Falcon3-1B-Instruct/raw/main/tokenizer_config.json) — padding_side ABSENT (control regex returned 2 matches); pad_token <|pad|>.

[9] [The Hydra Effect: Emergent Self-repair in Language Model Computations](https://arxiv.org/abs/2307.15771) (Thomas McGrath, Matthew Rahtz, Janos Kramar, Vladimir Mikulik, Shane Legg; 2023) — Canonical self-repair anchor 1 for the W4 attribution sentence.

[10] [Explorations of Self-Repair in Language Models](https://arxiv.org/abs/2402.15390) (Cody Rushing, Neel Nanda; 2024) — Canonical self-repair anchor 2 (ICML 2024); per-head/per-prompt self-repair, never one number per model.

> We further show that on the full training distribution self-repair is imperfect, as the original direct effect of the head is not fully restored, and noisy, since the degree of self-repair varies significantly across different prompts (sometimes overcorrecting beyond the original effect).

Locator: re-fetched https://arxiv.org/abs/2402.15390 (Block V, REVERIFIED)

[11] [Interpretability in the Wild: a Circuit for Indirect Object Identification in GPT-2 small](https://arxiv.org/abs/2211.00593) (Kevin Wang, Alexandre Variengien, Arthur Conmy, Buck Shlegeris, Jacob Steinhardt; 2022) — Origin of backup name-mover heads.

> In this work, we bridge this gap by presenting an explanation for how GPT-2 small performs a natural language task called indirect object identification (IOI).

Locator: re-fetched https://arxiv.org/abs/2211.00593 (Block V, REVERIFIED)

[12] [Conditional Co-Ablation: Recovering Self-Repair Backups in Transformer Circuits](https://arxiv.org/abs/2607.01940) (Zhiren Gong, Zihao Zeng, Chau Yuen, Wei Yang Bryan Lim; 2026) — Nearest W4 neighbour: a self-repair score per unit/circuit, never per checkpoint (0 checkpoint-framing matches, control 'ablation' 143).

> We recast this failure as a recovery task, conditional circuit completion, and introduce Conditional Co-Ablation (CoAx), a label-free, output-grounded score that asks how much each remaining unit's ablation effect grows once a primary set has been removed.

Locator: re-fetched https://arxiv.org/abs/2607.01940 (Block V, REVERIFIED)

[13] [SafeSeek: Universal Attribution of Safety Circuits in Language Models](https://arxiv.org/abs/2603.23268) (2026) — Nearest W2 neighbour: minimal joint-ablation safety circuits per scenario (0.42%; 3.03% heads + 0.79% neurons), not a k-band depth scored across checkpoints.

[14] [Any-Depth Alignment: Unlocking Innate Safety Alignment of LLMs to Any-Depth](https://arxiv.org/abs/2510.18081) (2025) — Nearest W3/W7 neighbour; inference-time defence; no all-position/last-token ablation ratio.

[15] [Perfect Detection, Failed Control](https://arxiv.org/abs/2606.24952) (2026) — Per-checkpoint weight-computable detection-vs-intervention cosine over four models; nearest G3/W1 neighbour.

[16] [Logit-Gap Steering](https://arxiv.org/abs/2506.24056) (2025) — Reads the refusal-affirmation logit gap directly; nearest G4 neighbour.

[17] [There Is More to Refusal in Large Language Models than a Single Direction](https://arxiv.org/abs/2602.02132) (2026) — Pairwise cosines among 11 refusal-category directions; nearest G1 neighbour; G2 absence control.

[18] [OBLITERATUS toolkit (CrossLayerAlignmentAnalyzer)](https://github.com/elder-plinius/OBLITERATUS) (2026) — Cross-layer consistency / angular-drift scalar, explicitly NOT a joint-ablation redundancy scalar.

[19] [Jorak Model Scanner](https://github.com/JolanMc/Jorak) (2026) — Re-located live: weights-only r^T W suppression and SVD subspace-alignment scar test; parent-free; W8 neighbour.

[20] [First Token Matters](https://arxiv.org/abs/2609.18471) (2026) — Nearest over-refusal-as-target miss: decode-site score + XSTest outcome, but over-refusal is its own defence's outcome column on 2 checkpoint families.

[21] [Locating and Steering Refusal (2609.04721)](https://arxiv.org/abs/2609.04721) (2026) — XSTest over-refusal outcome with orthogonalised-random controls; outcome of a defence, not a target.

[22] [Do Activation Monitors Survive Model Updates? (Duan)](https://arxiv.org/abs/2606.15980) (2026) — Frozen probes across twelve update conditions; per-cell Spearman prediction of monitor staleness, not over-refusal.

[23] [N-GLARE](https://arxiv.org/abs/2511.14195) (2026) — Scores base/RL/safety-removed Qwen3-4B; refusal rate is keyword refusal on HARMFUL prompts, not over-refusal.

[24] [RAS / SafeVec](https://arxiv.org/abs/2606.25750) (2026) — Reference-anchored; no over-refusal target.

[25] [Aligned Probing](https://arxiv.org/abs/2503.13390) (2025) — Layer-wise internals vs graded toxicity across 20+ models; no over-refusal target.

[26] [Has This Checkpoint Been Abliterated? (Hurtado)](https://arxiv.org/abs/2607.01854) (2026) — 273-checkpoint registry, benign fine-tunes as hard negatives, reference-anchored; fails the benign-PROMPT axis.

[27] [Over-Refusal and Representation (2603.27518)](https://arxiv.org/abs/2603.27518) (2026) — Over-refusal directions are task/intent dependent; over-refusal an outcome, not a per-checkpoint target.

[28] [Measuring the Wrong Thing: Internal scores (2608.09624)](https://arxiv.org/abs/2608.09624) (2026) — Internal scores anti-rank; benign set used only as false-positive calibration.

[29] [When Behavioral Safety Evaluation Fails (2606.08044)](https://arxiv.org/abs/2606.08044) (2026) — Latent Vulnerability Score + per-model over-refusal column; the two are NEVER correlated ('correlat' 0 matches; controls 4 and 49).

[30] [Safe responses matter: Output-aware safety guardrail mitigate over-refusal in MLLMs](https://arxiv.org/abs/2607.09697) (2026) — Over-refusal as an outcome of a guardrail.

[31] [RISA: Response Inspection and Selective Actions for Refusal Calibration](https://arxiv.org/abs/2609.00790) (2026) — Per-base-model thresholds; over-refusal rate an outcome of its method.

[32] [A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals](https://arxiv.org/abs/2609.00760) (2026) — Secondary nearest miss: XSTest over-refusal column AND probe-accuracy column in one paper, never correlated.

[33] [Item Response Theory for AI Safety](https://arxiv.org/abs/2608.05086) (Joshua Fonseca Rivera, Neil Shah, David Demitri Africa, Konstantinos Voudouris; 2026) — P1's nearest cousin: factor analysis of BENCHMARK OUTPUTS (8 benchmarks, 5,255 items, 192 models, 3 factors, 77% variance).

[34] [Efficient Safety Benchmarking via Item Response Theory](https://arxiv.org/abs/2606.20626) (Fabio Spagliardi, Mirian Silva, Ayan Datta, Aiden Zhou, Vamshi Bonagiri, Diogo Cruz; 2026) — The real 'Spagliardi' paper: few-item behavioural safety evaluation; assumes (never tests) unidimensionality.

> Efficient Safety Benchmarking via Item Response Theory

Locator: orchestrator re-fetch 2026-09-22

[35] [Refusal in Language Models Is Mediated by a Single Direction](https://arxiv.org/abs/2406.11717) (2024) — Rank-of-the-refusal-direction debate: single direction.

> In this work, we show that refusal is mediated by a one-dimensional subspace, across 13 popular open-source chat models up to 72B parameters in size.

Locator: re-fetched https://arxiv.org/abs/2406.11717 (Block V, REVERIFIED)

[36] [Refusal in LLMs is an Affine Function](https://arxiv.org/abs/2411.09003) (2024) — Rank debate: affine.

> We begin with an affine decomposition of model activation vectors and show that prior methods for steering model behavior correspond to subsets of terms of this decomposition.

Locator: re-fetched https://arxiv.org/abs/2411.09003 (Block V, REVERIFIED)

[37] [The Geometry of Refusal in Large Language Models: Concept Cones and Representational Independence](https://arxiv.org/abs/2502.17420) (2025) — Rank debate: multiple independent directions and cones (ICML 2025).

> Contrary to prior work, we uncover multiple independent directions and even multi-dimensional concept cones that mediate refusal.

Locator: re-fetched https://arxiv.org/abs/2502.17420 (Block V, REVERIFIED)

[38] [Fast Multi-dimensional Refusal Subspaces via RFM-AGOP](https://arxiv.org/abs/2607.02396) (2026) — Rank debate: multi-dimensional refusal subspaces.

> Early work assumed behaviours are encoded along single linear directions, but recent findings suggest complex behaviours, such as the refusal to answer harmful queries, live in multi-dimensional subspaces.

Locator: re-fetched https://arxiv.org/abs/2607.02396 (Block V, REVERIFIED)

[39] [The Hidden Dimensions of LLM Alignment](https://arxiv.org/abs/2502.09674) (2025) — Most dangerous P1 near-miss: 'safety residual space is low-rank' -- about one model's internal subspace, not a score family.

[40] [JailbreakBench: An Open Robustness Benchmark for Jailbreaking Large Language Models](https://arxiv.org/abs/2404.01318) (Patrick Chao, Edoardo Debenedetti, Alexander Robey, Maksym Andriushchenko, Francesco Croce, Vikash Sehwag, Edgar Dobriban, Nicolas Flammarion, George J. Pappas, Florian Tramer, Hamed Hassani, Eric Wong; 2024) — Bib fix: Chao et al., NeurIPS 2024 D&B.

[41] [HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal](https://arxiv.org/abs/2402.04249) (Mantas Mazeika, Long Phan, Xuwang Yin, Andy Zou, Zifan Wang, Norman Mu, Elham Sakhaee, Nathaniel Li, Steven Basart, Bo Li, David Forsyth, Dan Hendrycks; 2024) — Bib fix: Mazeika et al.

[42] [Interpretability without actionability (Basu et al.)](https://arxiv.org/abs/2603.18353) (2026) — Knowledge-action gap premise; the handbook DOES name Basu and 2603.18353 (SOURCES.md row S3).

[43] [Large Language Models Generate Harmful Responses Using a Distinct Mechanism, Shared Across Harm Types (Orgad et al.)](https://arxiv.org/abs/2604.09544) (2026) — Owns recognition-vs-generation dissociation (carried fence).

[44] [Overcoming Sparsity Artifacts in Crosscoders to Interpret Chat-Tuning](https://arxiv.org/abs/2504.02922) (Julian Minder, Clement Dumas, Bilal Chughtai, Neel Nanda; 2025) — Crosscoder L1 misattribution artefact -- fence for the four-way comparison.

[45] [Evolution of Concepts in Language Model Pre-Training](https://arxiv.org/abs/2509.17196) (2025) — Training-dynamics checkpoint tracking with crosscoders (ICLR 2026) -- fence.

[46] [Semantic Scholar forward citations of the Hydra Effect](https://api.semanticscholar.org/graph/v1/paper/arXiv:2307.15771/citations?fields=title,abstract,year,externalIds&limit=100) — Forward-citation sweep: 100 citing papers screened (API cap).

[47] [Semantic Scholar forward citations of Rushing & Nanda](https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.15390/citations?fields=title,abstract,year,externalIds&limit=100) — Forward-citation sweep: all 36 citing papers screened.

[48] [PyPI ams-scanner metadata](https://pypi.org/pypi/ams-scanner/json) — Version 0.1.3 unchanged since 2026-04-28.

[49] [AMS GitHub commits API](https://api.github.com/repos/GoogleCloudPlatform/activation-model-scanner/commits?per_page=5) — HEAD e7ca0d1a... dated 2026-08-27, unchanged.

[50] [LessWrong: refusal mediated redundantly across layers](https://www.lesswrong.com/posts/Sj92Atv6qwNn5JxbF/) — W2 near-miss: joint ablation of 31/32 layers on one model; not a k-search scored across checkpoints.

[51] [How much self-repair is in GPT2 without LayerNorm? (blog)](https://jdunbar.net/pages/self_repair/) — Informal W4 near-miss: compares two GPT-2 variants, never scalarised per model, not peer-reviewed.

## Verification

Numbered citations resolve to unique listed sources. Passage checks test text occurrence, not claim truth or entailment. Author/year metadata and locators are not independently verified. Details: `research_verification.json`.

- Source [3]: text found — padding_side: str = "right"
- Source [10]: text found — We further show that on the full training distribution self-repair is imperfect, as the original dir
- Source [11]: text found — In this work, we bridge this gap by presenting an explanation for how GPT-2 small performs a natural
- Source [12]: text found — We recast this failure as a recovery task, conditional circuit completion, and introduce Conditional
- Source [34]: text found — Efficient Safety Benchmarking via Item Response Theory
- Source [35]: text found — In this work, we show that refusal is mediated by a one-dimensional subspace, across 13 popular open
- Source [36]: text found — We begin with an affine decomposition of model activation vectors and show that prior methods for st
- Source [37]: text found — Contrary to prior work, we uncover multiple independent directions and even multi-dimensional concep
- Source [38]: text found — Early work assumed behaviours are encoded along single linear directions, but recent findings sugges

## Follow-up Questions

- Does any paper posted after 2026-09-22 score >=3 checkpoints with a single internal number against XSTest/OR-Bench over-refusal? Re-sweep arXiv cs.CL/cs.LG weekly until submission. That one paper would move the study to Branch 3 and demote the correlation table to a replication.
- Do W5 and W6 survive a dedicated search? Their OPEN verdict is inherited from W1's single Galeone control. A W5-specific query family (benign-twin / XSTest-safe axis ablation gain per model) should be run before either is called a contribution.
- Is W2's SafeSeek neighbour closer than it looks on a model panel? Check whether SafeSeek's released code reports circuit sparsity for more than one model and whether that number is ever compared across checkpoints; if so, W2 moves from PARTIAL to CLOSED and contribution (iii) weakens to Branch 2.

---
*Generated by AI Inventor Pipeline*
