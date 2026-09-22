# Blind held-out panel for a safety metric

`demo/` — Self-contained demo (Colab-ready notebook or markdown). Run without setup.  
`src/` — Full source code, data, and outputs from the experiment execution.

**Type:** experiment  
**ID:** `art_5lNob8bF1Yqi`

## Layman Summary

A sealed test bench of 29 small language models: it grades how each answers harmful and harmless requests, then saves their internal activations so a later step can test a cheap safety metric without ever seeing the grades first.

## Full Summary

PRODUCER-ONLY, BLIND SUBSTRATE. Computes NO candidate score: no W/G/A quantity, no Spearman/Pearson statistic, no ranking, no survivor. A blindness lint over every file under results/ and arrays/ (17,123 files / 357,828 JSON keys) PASSES; the absence of scores is the design, not a failed run.

ACHIEVED (all quotas met): 20 panel checkpoints harvested from 9 never-loaded families (bloom, deepseek-coder, ernie, exaone, gemma, gpt-neo, hunyuan, pleias, pythia), 13 multi-stage lineages, 4 community-edited children, plus 9 in-house arms = 29 gated checkpoints. Judge spend $1.31 of a $10 budget. Peak VRAM 6982 MiB <= the 7500 MiB declared, enforced by a lease that caps the SUM over this artifact's concurrent processes.

ORDER GATE, PROVEN: an append-only SHA-256 chain (logs/chain.jsonl, 40 records, verifies end to end) fixes panel rule -> seeded draw of 40 repos -> frozen item sets -> generation -> frozen three-boolean judge (gemini-2.5-flash-lite; 20% gpt-5-mini audit) -> staged graded_truth commits -> ONLY THEN any harvest. An audit re-checks that all 29 harvested tags were graded-and-committed first: ok=True. Contaminated commits are RETRACTED in-chain, never deleted.

ITEM SETS (chained): HARM n=85 and OR_HARDBENIGN n=43 reuse iteration 4's exact ids so the columns join; OR_XSTEST54 n=54 is the sealed XSTest split whose id list reproduces the pre-registered seal hash 898b70e1... exactly (30 of its 54 pair ids were already exposed upstream -- stated, not hidden).

TARGET WITH REAL SPREAD: judge-graded over-refusal on two named benign sets (OR_XSTEST54 SD 0.204, OR_HARDBENIGN SD 0.226, n=30), harmful compliance and safe engagement, each with Wilson CIs and the set name in every key. BASELINES produced in the same pipeline: the frozen keyword proxy is FLOORED (exactly zero on 86.7% of checkpoints, SD 0.020/0.041) so it cannot discriminate and is reported as unusable; logit-only refusal-token mass; AMS Tier-1 sigma for 19/20 tags.

SUBSTRATE per checkpoint: prompt-site and decode-site residuals, three expression-only render arms, a direction bank fitted from each model's OWN activations over six depth-FRACTION bands with split-half fits, and a ~104-cell forward-only intervention grid with MATCHED-DISPLACEMENT random controls. Instrument self-tests all PASS and gate the harvest: arm-0 identity 9e-07, ablation leaves 0.00084 of the F component, control inertness 1.0006x, displacement matching 1.0002x. Every array carries shape, dtype and sha256; 16,940 files re-hashed, 29/29 manifests verify. JOIN_README.md per tag states what each later statistic is computed FROM.

IN-HOUSE NO-OP SET on a TIED-embedding parent (ERNIE-4.5-0.3B-PT), declarations chained BEFORE grading (record 6 precedes record 10): of 5 non-degenerate arms DECLARED no-ops, ZERO behaved as no-ops -- int8 weight-only round-trip OR_EFFECTIVE, non-safety LoRA and DPO and a benign system-prompt swap EFFECTIVE, fp16 cast and unembedding perturbation AMBIGUOUS; the only NOOP is the by-construction-zero safetensors re-save.

25+ numbered deviations record every fallback, including two real faults found and fixed mid-run: left-padded batched generation corrupts some architectures (gemma-3 0/8 rows), so every tag now self-certifies its batching and all forwards are padding-free; and a chunk-resume collision caught by a commit-time denominator assertion. bloomz-3b could not be harvested inside the 7.5 GB declaration (250k vocab) so the 20th slot was filled from the NEXT position in the frozen order.

PER-EXAMPLE predict_* FIELDS ARE BASELINES, NEVER A CANDIDATE READOUT (blindness is preserved): graded-behaviour rows carry predict_item_majority_vote_baseline (the per-item majority over the graded panel, an item prior); per-checkpoint rows carry predict_ams_tier1_level_baseline (the published AMS instrument's PASS/WARNING/CRITICAL verdict); in-house arm rows carry predict_declared_stratum_apriori (the stratum declared and chained BEFORE grading, which is what makes the 0-of-5 no-op result falsifiable). The keyword-proxy per-item verdict is unavailable because it needs the raw completions that hygiene deletes; its per-checkpoint rates remain in the manifest.

## Dependencies

- `art_1hlgObsQWnZS` — model registry
- `art_jn337OmvTVjZ` — sealed split
- `art__K_YDC4bpDfV` — prior art

## Output Files

- `method.py`
- `full_method_out.json`
- `mini_method_out.json`
- `preview_method_out.json`

## Demo Files

- **method.py** — Research methodology implementation

---
*Generated by AI Inventor Pipeline*
