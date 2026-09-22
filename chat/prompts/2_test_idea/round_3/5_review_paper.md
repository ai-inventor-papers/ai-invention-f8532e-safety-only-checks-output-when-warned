# review_paper — test_idea

> Phase: `invention_loop` · round 3 · `review_paper`
> Run: `run_YqmEFECOIR3D` — Specificity and Causality Audits for Activation-Based Safety Readouts
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `review_paper` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-21 15:10:33 UTC

```
 mech interp study of where safety lives, not a jailbreak or attack-selection study; do not reframe it as one.
</prompt>
```

### [2] SYSTEM-USER prompt · 2026-09-21 15:11:50 UTC

```
You are verifying a research paper's numbers against executed artifacts. READ-ONLY: do not modify anything under /ai-inventor/aii_data. Report findings as text (no files needed).

Paper: /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/paper_draft.tex (read it fully first; abstract is in .terminal_claude_agent_struct_out.json next to it).
Artifacts: /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_evaluation_1/ (results/tables.json, SUMMARY.md, README.md, eval_out.json/full_eval_out.json, src/panel.py, src/laneb.py, logs). Earlier-iteration artifacts may be found under /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/ (or find them with `find /ai-inventor/aii_data/runs/run_YqmEFECOIR3D -maxdepth 4 -type d`), e.g. Lane A panel and Lane B harvest code.

Check each of these paper claims — for each give MATCH / MISMATCH / NOT FOUND with the exact artifact file+key+value:
1. Table 1 (tab:main) every cell: HC, d, R, Drive, BL1, Onset, B3 for Base/Instruct/SafeRL/STaR/Abliterated/RandInit. Specifically: is BL1 Instruct=4.99, Base=0.32, Abliterated=1.76 real? Artifacts reportedly have BL1_easy vs BL1_hard with sign flips (mlabonne BL1_easy -1.96, BL1_hard +1.76; also -0.30/1.96 values). Which BL1 variant does each table row use — are they mixed? Is RandInit a Qwen3-0.6B or 4B? B3 values (2.58, 28.14, 33.15, 0.27, 0.54, 4.85) — do they exist, and is B3 really "Fisher-transformed mean cosine of consecutive-layer diff-in-means directions" (check code definition)? Is HC for STaR really NA?
2. Abliteration Δd = -1.73 [-2.35,-1.19]; ΔR=-0.037 90% CI [-0.150,0.125]; base->instruct R +0.40 CI [0.137,0.762]; "six effective parent-child pairs from four families, all 6 d drops CI below zero"; granite null edit Δd=0.09; Granite ΔBL1=-4.83, Δpeak_drive=-2.49.
3. STaR TOST d diff 0.046; 33% and 46% distance.
4. Accumulator: Spearman rho with layer -0.99/-0.82/-0.87/-0.97/-0.88; "fixed-axis peak-to-start ratio 1.00 in all arms"; refit ratio 1.41-2.09; "HARD-scored variant reaches 19.7 for Instruct" — artifacts reportedly say on HARD prompts the EASY-fit layer-13 axis has a NEGATIVE gap, ratio undefined. Also the claim "This pattern holds identically in all four Lane B lineages across all five dose levels and all three activation sites" — was this computed at all?
5. Lane B: Table 3 (tab:site) all 12 cells + the CIs in text and the safety-minus-L4 contrasts; dose levels really {0,.25,.5,.75,1}? lesion at layers 13-21? L2 = "Instruct with different random seed for direction" — what are L1..L4 really? 384 harmful/384 benign, 128 EASY / 256 HARD, AdvBench source? "Sub-threshold doses TOST-equivalent to zero in every lineage at every site" — verify. Site definitions EARLY=tokens 5-20, LATE=40-55, PROMPT=last prompt token; teacher-forced.
6. Table 5 (tab:bl1corr) rho with BL1 and partial rho values (0.767/-0.464, 0.791/+0.017, 0.784/-0.327, 0.715/-0.468, 0.746/-0.390) and "25-checkpoint panel". How many checkpoints does the Lane A panel really have (22? 25?) and how many families? The paper lists Qwen3, Qwen2.5, SmolLM3, SmolLM2, Phi-4-mini, Granite, TinyLlama, OLMo-2, StableLM-2 yet says "five families".
7. "Of 68 pre-registered quality gates, 43 pass and 24 fail" (43+24=67?) G1/G5/G6 statements. "k-prompt AUROC smallest_k_pass = null". "Probe AUROC is 1.00 at every layer and dose level". "TPR@1%FPR resolution 0.0026 with n=384 negatives".
8. Prompts: "45 harmful prompts from XSTest and JailbreakBench each paired with a benign twin"; judge; HC definitions.
Also flag any number in the paper you cannot find anywhere. Be concrete, quote paths/keys. Time limit: ~35 minutes; prioritize items 1,2,4,5,6.
```

### [3] SYSTEM-USER prompt · 2026-09-21 15:12:04 UTC

```
You are verifying a research paper's held-out-panel (Lane C) claims against executed artifacts. READ-ONLY: do not modify anything under /ai-inventor/aii_data. Report findings as text.

Paper: /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/paper_draft.tex (read it fully; abstract + figures in .terminal_claude_agent_struct_out.json next to it).
Artifact: /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1/ (README.md, results/heldout_table.json, results/extra_analyses.json, results/b7_diagnostic.json, results/hook_checks.json, results/graded_truth.json, prereg.json, method_out.json, src/). Also the plan: /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_plan/gen_plan_experiment_1/.

Check, giving MATCH/MISMATCH/NOT FOUND with file+key+value:
1. Paper Sec 3.1 says Lane C = "10 checkpoints ... from four families (Qwen3, SmolLM3, Phi-4-mini, Granite-3.2), including parent and abliterated pairs". What are the actual 10 checkpoints and families? (Reportedly Vikhr-Llama-3.2-1B + abliterated, Falcon3-1B base/instruct, AMD-OLMo-1B base/SFT/SFT-DPO, Llama-3.2-1B-Instruct + abliterated2, LFM2-700M.) 
2. Table 4 (tab:heldout): B3 rho -0.890 CI [-0.951,-0.569]; Δ vs BL1 -0.270; partial rho|BL1 -0.816; C13 peak d -0.656 [-0.975,0.200] Δ -0.037 partial -0.433; BL1 -0.620 [-0.735,0.200]; BL1_hard -0.534 [-0.705,0.413]. Verify each; is CI family-bootstrap? Does the B3−BL1 paired delta CI actually include zero (give it)? Also: Does the paper omit readouts that were preregistered (e.g. B7 rho +0.80 OLMo all-ones artefact, C2/C6/C9 wrong-sign vs prereg, C5, C7)? The paper says "six activation readouts" in Table 4 but lists only 2 — which readouts were registered and what are all their rhos?
3. "Two new abliterated pairs replicate: held-out d drops in both (CIs below zero)" — values (reportedly Vikhr -0.90 [-1.38,-0.55], Llama -0.61 [-0.88,-0.36]).
4. Findings the paper omits: BL1 moves +1.61 [.98,2.29] on AMD SFT->DPO behavioural no-op while activation readouts do not; AMD base->SFT; BL1 double-norm bug (BL1 read on norm(norm(h_L))) and BL1_truelogit; per-prompt Vikhr recognition .85->.81 vs drive .79->.37. Critical value .648, MDE .80 at n=10.
5. HC values on the panel and judge; did the paper's "45 harmful prompts from XSTest and JailbreakBench" match the panel's items (reportedly Lane C 90 items, deviation items_cut_to_laneC90)?
6. Is B3's direction self-consistency definition in code the same as the paper's ("Fisher-transformed mean cosine of consecutive-layer diff-in-means directions")? Sign: higher B3 ↔ lower HC?
7. List all deviations recorded in the artifact and whether the paper discloses them.
8. Was the held-out panel preregistered/hash-committed before truth? Was the screen->join deferred (no survivor.json)?
Be concrete; ~30 min budget.
```

### [4] SYSTEM-USER prompt · 2026-09-21 15:12:14 UTC

```
Verify the bibliography of a research paper against reality (arXiv / Semantic Scholar / web). READ-ONLY on /ai-inventor/aii_data. Report as text.

Files: /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/references.bib and paper_draft.tex (same dir). The run's own prior-art dossier: /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_research_1/research_report.md (and research_out.json) — use it to know which papers the run itself identified as closest prior art.

Tasks:
1. For every bib entry actually \cite'd in paper_draft.tex, check title, authors, year, arXiv id exist and match (use WebFetch on arxiv.org/abs/<id> or export.arxiv.org/api/query?id_list=<id>, or WebSearch). Flag fabricated/wrong titles, authors, ids. Especially: Arditi2024 (real authors: Arditi, Obeso, Syed, Paleka, Panickssery, Gurnee, Nanda; NeurIPS 2024), Yang2026 (should be AMS arXiv:2608.05578), Winninger2026 (N-GLARE), LlorenteSaguer2026a/b (2603.27412 'The Geometry of Harmful Intent' and 2604.18901), Orgad2026, Lin2025, Marshall2024 (claims "harm recognition geometry survives abliteration in two model families" — does such a 2024 paper exist?), Mitra2026 (prefilling / first generated token), Yamaguchi2025, Schirmer2026, Galeone2026 (2606.24952?), Hurtado2026 (273 checkpoints AUROC 0.95), Wu2026 (RAS/SafeVec 2606.25750), Messenger2026 (Aligned Probing TACL), Jiang2026 (IRT 192 models), Rottger2023, Zou2023, Cui2024.
2. Check the paper's characterization of each: e.g. does AMS really report "leave-one-out threshold accuracy 71%" on 14 checkpoints/4 families, "16 contrastive pairs", "40-80% depth"? Does Galeone2026 say "weight cosine between layer-wise directions is not predictive of steerability"? Paper sec 2 says "Public abliteration toolkits already compute pairwise cosine similarities and cumulative angular drift across layers \cite{Arditi2024}" — is citing Arditi for toolkits a miscitation? Paper Sec 5.1 says "consecutive-layer cosines can be as low as 0.016 in deep layers" in public toolkits with no citation — source?
3. Count bib entries never cited; count cited keys missing from bib.
4. Does the paper cite and credit the closest prior art the dossier identifies? In particular, do LlorenteSaguer2026a/b or AMS already publish (a) recognition survives abliteration, (b) layer-wise rotation of harm/refusal direction, (c) activation readouts vs a logit baseline? Quote abstracts.
Budget ~35 minutes. Be concrete with URLs and quotes.
```

### [5] SYSTEM-USER prompt · 2026-09-21 15:15:06 UTC

```
<validation-feedback>
Attempt 1 failed validation.

The output file `.terminal_claude_agent_struct_out.json` does not exist yet. Produce it as JSON matching the schema.

Produce `.terminal_claude_agent_struct_out.json` again so it contains corrected JSON that matches the schema. Do not invent new fields.
</validation-feedback>
```

### [6] SYSTEM-USER prompt · 2026-09-21 15:18:11 UTC

```
<task-notification>
<task-id>a0efa8d6593d2d3f1</task-id>
<tool-use-id>toolu_013hgENqDBGZyPzRbnF5qEm8</tool-use-id>
<output-file>/tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-3-review-paper-review-paper/be466e6a-f427-4f34-a8d4-52c8ae0a11f6/tasks/a0efa8d6593d2d3f1.output</output-file>
<status>completed</status>
<summary>Agent "Verify paper citations live" finished</summary>
<note>A task-notification fires each time this agent stops with no live background children of its own. The user can send it another message and resume it, so the same task-id may notify more than once.</note>
<result># Bibliography Verification Report — run_YqmEFECOIR3D iter_3 paper_draft.tex

**Scope checked:** `references.bib` (41 entries) against `paper_draft.tex` (all `\cite{}` calls), each cited paper's real arXiv record, and the run's own `research_report.md` (prior-art dossier). All arXiv IDs were re-fetched live via `export.arxiv.org/api/query`; several additional real papers were located via web search.

## Headline finding

**Almost none of the bib entries are outright fabricated — nearly every one is a real paper with a correct title/author/arXiv-ID. The paper's actual defect is systematic *citation-key swapping*: specific numeric/descriptive claims in the Introduction and Related Work are attached to the wrong `\cite{}` key, so the reader is pointed at a real but unrelated paper for each claim, while the paper that *actually* made the claim is either cited elsewhere for something else, or is missing from the bibliography entirely.** This affects essentially every sentence in the "Activation-based safety readouts," "Recognition versus execution," and "Depth profiles" paragraphs of Related Work (Sec. 2, lines 28–35).

## 1. Per-entry verification (title/author/id checks, incl. the named suspects)

Verified live against arXiv/IEEE:

| Key | Bib title/authors/id | Real record | Verdict |
|---|---|---|---|
| **Arditi2024** | Arditi, Obeso, Syed, Paleka, **Nina Rimsky**, Gurnee, Nanda; NeurIPS 2024; 2406.11717 | arxiv.org/abs/2406.11717 → same title, authors are Arditi, Obeso, Syed, Paleka, **Nina Panickssery**, Gurnee, Nanda | **Wrong author name.** "Rimsky" should be "Panickssery." Everything else (title, venue, id) correct. |
| **Yang2026** | "Beyond a Single Direction: Chain-of-Thought Disrupts Simple Steering of Refusal," Kia-Jüng Yang et al., 2605.26772 | arxiv.org/abs/2605.26772 → confirmed, exact title/author match, real paper about LRM chain-of-thought disrupting refusal steering | **Bib entry itself is real and correct** — but see §2: in-text it is used to cite AMS, a completely different paper. |
| **Winninger2026** | "Fast Multi-dimensional Refusal Subspaces via RFM-AGOP," Thomas Winninger, 2607.02396 | arxiv.org/abs/2607.02396 → confirmed exact match | **Bib entry correct** — but used in-text to cite N-GLARE (see §2). |
| **LlorenteSaguer2026a** | "Harmful Intent as a Geometrically Recoverable Feature of LLM Residual Streams," 2604.18901 | arxiv.org/abs/2604.18901 → confirmed exact title/author | Correct. |
| **LlorenteSaguer2026b** | "The Geometry of Harmful Intent: Training-Free Anomaly Detection via Angular Deviation…," 2603.27412 | arxiv.org/abs/2603.27412 → confirmed exact title/author | Correct. |
| **Orgad2026** | "…Distinct Mechanism, Shared Across Harm Types," Orgad, Wei, K. Zheng, Wattenberg, Henderson, Goldfarb-Tarrant, Belinkov | Matches arxiv.org/abs/2604.09544 exactly (K. Zheng = Kaden Zheng) | Correct content, though bib entry is missing the arXiv id/volume. |
| **Lin2025** | "N-GLARE…," Zheyu Lin, Jirui Yang, Yupeng Qiu, Yubing Bao, Heng-Qi Guo, Yao Guan, 2511.14195 | arxiv.org/abs/2511.14195 → real title matches; real author list is Zheyu Lin, Jirui Yang, **Yukui** Qiu, **Hengqi** Guo, Yubing Bao, Yao Guan (minor name/order drift, not fabrication) | Bib entry is genuinely N-GLARE — but see §2, it is *never cited for N-GLARE content in the text*. |
| **Marshall2024** | "Refusal in LLMs is an Affine Function," Marshall, Scherlis, Belrose, 2411.09003 | arxiv.org/abs/2411.09003 → confirmed real title/authors; abstract is about **affine concept editing (ACE)** for steering, nothing about abliteration survival | Bib entry itself correct, but the claim attached to it in-text ("harm recognition geometry survives abliteration in two model families," lines 5 &amp; 32) **does not exist in this paper** — see §2. |
| **Mitra2026** | "Closing the Activation-Cone Blind Spot…," Subhadip Mitra, 2606.29441 | arxiv.org/abs/2606.29441 → confirmed; abstract: prompt-time defenses "structurally blind to prefilling attacks," first-generated-token probing | Correct, and correctly cited. |
| **Yamaguchi2025** | "Where Do Reasoning Models Refuse?," Yamaguchi, Etheridge, Arditi | Real paper confirmed at **arxiv.org/abs/2507.03167** (bib entry omits the id/volume) — but its actual content is about *where in a chain-of-thought a reasoning model's refusal decision occurs*, nothing about Qwen-2.5/LLaMA-3.1 divergence depth | Bib entry roughly right (missing id), but see §2 — the claim cited to it is not in the paper. |
| **Schirmer2026** | "Online Safety Monitoring for LLMs," Schirmer, Jazbec, Timans, Naesseth, Waldron, Nalisnick, 2607.02510 | arxiv.org/abs/2607.02510 → confirmed; abstract is about runtime monitoring/alarms for unsafe deployment-time outputs | Bib entry correct — but see §2, the "staging" claim cited to it is from a different, uncited paper. |
| **Galeone2026** | "Perfect Detection, Failed Control…," C. Galeone, A. Ettorre, M. Park, G. Ettorre, D. Ligorio, 2606.24952 | arxiv.org/abs/2606.24952 → confirmed | Correct entry, but see §2 for a mischaracterization of its finding. |
| **Hurtado2026** | "Has This Checkpoint Been Abliterated?…," Gabriel Hurtado, 2607.01854 | Confirmed: "0.95 AUROC across 273 checkpoints," reference-anchored (needs the parent) | Correct, and correctly cited ("AUROC 0.95," "requires access to the unmodified parent"). |
| **Rottger2023** (XSTest), **Zou2023** (RepE), **Cui2024** (OR-Bench), **Wei2023**, **Li2023**, **Yuan2024** | — | All confirmed against arXiv with exact title/author matches (2308.01263, 2310.01405, 2405.20947, 2307.02483, 2306.03341, 2407.09121) | Correct. |
| **Jiang2026** | "When Behavioral Safety Evaluation Fails: A Representation-Level Perspective," Jiang, Gjølbye, Zhang, Koyejo, 2606.08044 | Confirmed real, exact match; about "dissociated" models defeating static probes | Bib entry correct — but see §2, misused for "Behavioural IRT" in-text. |
| **Wu2026 / Huang2026** | Wu2026="Knowing without Acting…" (Recognition/Execution axes), 2603.05773; Huang2026="RAS…," 2606.25750 | Both confirmed real and correctly matched to their bib entries | Both correct entries — but see §2, badly mismatched to in-text claims. |
| **Messenger2026** | "Detecting Safety Training Modification in Language Models via Activation Analysis," Glen Messenger, IEEE Access vol 14, pp 91723–91737 | Confirmed: this is the real title/author of **AMS**, the Google paper also on arXiv as **2608.05578** ("AMS: Activation-based Model Scanner"), IEEE Access publication confirmed via web search (research.google, ieeexplore.ieee.org/…/11568484) | **This is the correct, real AMS citation** — but is never used for AMS content in-text (see §2). |

## 2. The core problem: claims attached to the wrong `\cite{}` key

Cross-checking every specific numeric/descriptive claim against the paper it's cited to (via live abstracts and the dossier's verbatim quotes) turns up a consistent pattern — every one of the following is a *real, uncontested claim from a real paper*, but attached to the wrong bib key. The paper the claim actually belongs to is either present in the bib under a different key, or absent from the bib entirely:

1. **AMS's numbers (16 contrastive pairs, 40–80% depth, 14 configs/4 families, LOO 71% accuracy) — cited as `\cite{Yang2026}`** (Sec 1 &amp; Sec 2, and again at line 233 "AMS achieves leave-one-out threshold accuracy of 71%… \cite{Yang2026}"). Yang2026 is actually "Beyond a Single Direction: Chain-of-Thought Disrupts Simple Steering of Refusal" (2605.26772) — a reasoning-model CoT paper with nothing to do with AMS. **The correct key for these numbers is already in the bib: `Messenger2026`** (real title "Detecting Safety Training Modification in Language Models via Activation Analysis," arXiv 2608.05578 / IEEE Access), which the paper instead misuses for a different claim (below).

2. **N-GLARE's claim ("Jensen–Shannon divergence across layer groups," "high coupling with unsafe and refusal rates") — cited as `\cite{Winninger2026}`** (Sec 1 line 5, Sec 2 line 29). Winninger2026 is actually "Fast Multi-dimensional Refusal Subspaces via RFM-AGOP" (2607.02396) — unrelated. **The correct key is already in the bib: `Lin2025`**, whose real title *is* N-GLARE, but which is never cited for N-GLARE content anywhere in the paper.

3. **RAS's claim ("reference-anchored score calibrated within families… requires a reference model per family") — cited as `\cite{Wu2026}`** (Sec 2 line 29). Wu2026 is actually "Knowing without Acting: The Disentangled Geometry of Safety Mechanisms" (2603.05773), the paper that owns the "Recognition Axis / Execution Axis" terminology — unrelated to RAS. **The correct key is already in the bib: `Huang2026`** ("RAS: Measuring LLM Safety Through Refusal Alignment," 2606.25750) — which is **never cited anywhere in the paper** (it's one of the 22 dead bib entries).

4. **"Lin et al. formalised this as two subspaces, a Recognition Axis and an Execution Axis" — cited as `\cite{Lin2025}`** (Sec 2 line 32; also line 5). This claim actually belongs to `Wu2026` (Jinman Wu, Yi Xie, **Shen Lin**, Shiqian Zhao, Xiaofeng Chen — note the third author is named Lin, likely the source of the mix-up with N-GLARE's first author Zheyu Lin). Confirmed via live fetch of 2603.05773: "Safety alignment is often conceptualized as a monolithic process wherein harmfulness detection automatically triggers refusal. However, the persistence of jailbreak attacks suggests a fundamental mechanistic decoupling" — this is the Recognition/Execution paper, not N-GLARE.

5. **"Aligned Probing correlates per-layer probe accuracy with output toxicity across 20+ models" — cited as `\cite{Messenger2026}`** (Sec 2 line 29). Messenger2026 is actually the AMS paper (see #1 above), which has nothing to do with toxicity probing. **The real Aligned Probing paper (Waldis, Gautam, Lauscher, Klakow, Gurevych, TACL 2026, aclanthology.org/2026.tacl-1.14.pdf) is absent from the bibliography entirely.**

6. **"Behavioural IRT estimates a latent safety trait from roughly ten adaptively chosen items across 192 models" — cited as `\cite{Jiang2026}`** (Sec 2 line 29). Jiang2026 is actually "When Behavioral Safety Evaluation Fails: A Representation-Level Perspective" (2606.08044, confirmed) — about adversarially "dissociated" models defeating static probes, not IRT. **The real IRT paper ("Item Response Theory for AI Safety," arXiv 2608.05086, "roughly ten adaptively chosen items suffice… 192 language models") is absent from the bibliography.**

7. **"Yamaguchi et al. showed that Qwen-2.5 diverges… at approximately 40% depth… more robust to linear steering than LLaMA-3.1, which processes them identically for 95% of layers" — cited as `\cite{Yamaguchi2025}`** (Sec 2 line 35). The real Yamaguchi et al. paper (2507.03167, confirmed via WebSearch, authors Yamaguchi/Etheridge/Arditi) is about *where in a chain-of-thought* a reasoning model decides to refuse — it says nothing about Qwen-vs-LLaMA depth-of-divergence. **The claim actually belongs to a completely different, uncited paper: "The Geometry of Refusal: Linear Instability in Safety-Aligned LLMs" by Shivam Ratnakar &amp; Kartikeya Vats (arXiv 2606.22686), confirmed live: "Models like Llama-3.1 process harmful and safe queries identically for 95% of their layers, diverging only at the final output head"** — this paper is absent from the bibliography.

8. **"Schirmer et al. identified staging of harmfulness detection, aggregation along a refusal direction, and late-layer expression" — cited as `\cite{Schirmer2026}`** (Sec 2 line 34). The real Schirmer et al. paper (2607.02510, confirmed) is about online/runtime safety monitoring and alarms — nothing about layer-staging. **The staging claim belongs to a different, uncited paper: "Refusal Lives Downstream of Persona in Chat Models" by Viola Zhong &amp; Qirui Li (arXiv 2606.26161), confirmed: "This mediation unfolds across layers in three stages: input-side harmfulness detection, aggregation along the refusal direction, and late-layer expression."**

9. **"Marshall showed that geometry associated with harm recognition survives abliteration in two model families" — cited as `\cite{Marshall2024}`** (Sec 2 line 32; also bundled at line 5 with LlorenteSaguer2026a). Confirmed via live fetch (2411.09003): Marshall/Scherlis/Belrose's real paper is "Refusal in LLMs is an Affine Function," about affine concept editing (ACE) for steering — it makes no claim about geometry surviving abliteration across model families. **This is exactly the fabricated attribution the task flagged.** The real source of "geometry survives refusal ablation in both tested model families" is `LlorenteSaguer2026b` (2603.27412, per the dossier's own verbatim quote) — which is already co-cited in the same sentence, making the Marshall2024 addition a spurious extra citation for a claim its paper doesn't make.

## 3. The two specific Sec 2/Sec 5.1 sentences flagged in the task

- **"Public abliteration toolkits already compute pairwise cosine similarities and cumulative angular drift across layers `\cite{Arditi2024}`"** (line 35). This **is a miscitation**. Arditi et al.'s NeurIPS 2024 paper introduces the abliteration method itself; it does not build or describe "public toolkits" with cosine-similarity/angular-drift dashboards. Per the run's own dossier (source [27]), that functionality belongs to a third-party, non-peer-reviewed community tool, the **OBLITERATUS** GitHub repo, whose `analysis/cross_layer.py` computes exactly "pairwise cosine similarities between refusal directions across all layers" and "cumulative angular drift per layer" — this tool is not in the bibliography at all, and Arditi2024 is cited here for something its authors never built or claimed.

- **"consecutive-layer cosines can be as low as 0.016 in deep layers" (Sec 5.1, Discussion, line 227)** — has **no citation whatsoever** in the text, and I could not locate this specific figure ("0.016") in any of the papers checked, the OBLITERATUS repo excerpts in the dossier, or via web search. This appears to be an **unsourced, unverifiable number** inserted into the Discussion without support.

- **"This finding is consistent with Galeone et al.'s report that weight cosines between layer-wise directions are low and do not predict steerability `\cite{Galeone2026}`"** (line 227) — I fetched the actual paper (arxiv.org/abs/2606.24952) and confirmed its cosine finding is **not** about layer-to-layer rotation within a model. Its actual measurement is the cosine between the *detection direction* and the *steering/control direction* (two different directions at the same site), found to be stable — "cos stays in [0.12, 0.20], identical before and after instruction tuning" (i.e., stable across training checkpoints, not across depth). The paper's characterization ("weight cosine between layer-wise directions… not predictive of steerability") **conflates two different geometric comparisons** (cross-layer rotation vs. detection-vs-control-direction stability across training) and mischaracterizes what Galeone2026 actually measured.

## 4. Bib coverage counts

- 41 total `.bib` entries; **19 unique keys actually `\cite`'d**; **0 cited keys missing from the bib** (no undefined references — LaTeX would compile without `??`).
- **22 entries are never cited anywhere in the text**: `Aremu2026, Basu2026, Chang2026, Chua2026, Du2026, Han2025, Huang2026 (RAS!), Kwon2026, Lan2026, Li2023, Li2026, Luo2026, Meng2022, Muhamed2026, Shairah2025, Son2026, Wei2023, Wollschlager2025, Yu2026, Yuan2024, Zhang2025, Zhao2025`. Notably `Huang2026` is the *correct* RAS citation that the text instead misattributes to `Wu2026` (see §2.3), and `Wollschlager2025` ("The Geometry of Refusal: Concept Cones…") is directly on-topic for the Related Work section yet goes entirely unused.

## 5. Does the paper credit the dossier's identified closest prior art?

The dossier (`research_report.md`) names **AMS (Messenger2026/2608.05578)**, **N-GLARE (Lin2025/2511.14195)**, **RAS (Huang2026/2606.25750)**, and the **LlorenteSaguer 2026a/b** pair as the closest incumbents, and states explicitly that the paper "must not claim… recognition surviving abliteration [as new]" and must position itself against "AMS σ (open code) plus a final-layer logit gap."

- **(a) Recognition survives abliteration:** Yes, the paper does state this and attributes it correctly to `LlorenteSaguer2026a` (also, spuriously, to `Marshall2024` — see §2.9). Dossier quote it should be checked against: *"Geometry survives refusal ablation in both tested model families"* (LlorenteSaguer2026b, arXiv 2603.27412) and *"three alignment variants (base, instruction-tuned, abliterated)"* (LlorenteSaguer2026a, arXiv 2604.18901). These are correctly used.
- **(b) Layer-wise rotation of the harm/refusal direction:** The paper's own Contribution 2 ("harm direction is layer-specific, not accumulated") is framed as consistent with Galeone2026's rotation/cosine finding — but as shown in §3, that specific characterization of Galeone2026 mischaracterizes what was measured, and the more directly relevant prior source (OBLITERATUS's per-layer cosine/angular-drift computation) is mis-cited to Arditi2024 rather than credited to the actual tool.
- **(c) Activation readouts vs. a logit baseline:** The dossier explicitly flags this as one of the paper's few surviving distinguishing contributions ("none of AMS, RAS or N-GLARE reports a logit baseline"), and the paper does deliver on this (BL1 throughout Results). This part is handled correctly and is the paper's most defensible original framing.

Net: the paper's *content* broadly reflects the dossier's prior-art landscape and avoids the dossier's explicit "MUST NOT CLAIM" list (it does not claim "first cross-family few-prompt activation metric," does not claim "recognition/execution" as new naming, etc.) — but the **citation apparatus supporting that Related Work section is unreliable**: a reader following the `\cite{}` links to check any specific number (AMS's 71%, N-GLARE's JSD claim, RAS's reference-anchoring, Aligned Probing's toxicity result, IRT's 192 models, the Qwen/LLaMA depth-divergence stat, the detect-aggregate-express staging claim, or the "survives abliteration" claim) will land on the wrong paper in at least 9 of these cases, even though most of the underlying `.bib` entries are themselves real and accurately transcribed.

## Files reviewed
- `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/references.bib`
- `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/paper_draft.tex`
- `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_research_1/research_report.md`</result>
<usage><subagent_tokens>131847</subagent_tokens><tool_uses>15</tool_uses><duration_ms>354599</duration_ms></usage>
</task-notification>
```
