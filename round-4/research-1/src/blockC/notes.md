# Bibliography verification notes (2026-09-21, web-only)

## Method
Batch-queried the arXiv API (`export.arxiv.org/api/query`) for all ~35 arXiv ids already present
in `iter3_references.bib`, then resolved every stub entry lacking an id (Yamaguchi2025, Orgad2026,
Luo2026, Muhamed2026, Aremu2026, Lan2026, Son2026, Chang2026, Du2026, Meng2022, Han2025) by exact
title search against the arXiv API. Fetched the ACL Anthology's own `.bib` exports directly for
N-GLARE (2026.acl-long.1334) and Aligned Probing (2026.tacl-1.14) — authoritative and required no
inference. Used the GitHub REST API for commit/license/tree verification on OBLITERATUS and Jorak,
and downloaded all 282 `.md`/`.py` files at OBLITERATUS commit `cb4aec45` to grep exhaustively for
`0.016`. Used `aii_fast_web_fetch.py grep` directly against arXiv PDF text (not HTML abstracts) for
all verbatim quotes, so every quote below is copy-pasted from actual paper text, not a summary.

## Headline results
1. **Orgad2026** = arXiv:2604.09544 confirmed, all 7 authors exactly as hypothesized. No formal
   venue found yet (arXiv-only as of today).
2. **Yamaguchi2025**: the hypothesis arXiv id **2507.03167 is CORRECT** (title-search-confirmed).
   The original bib stub had no volume/doi/venue at all; added venue "ICML 2025 Workshop on
   Reliable and Responsible Foundation Models (R2FM)" from the arXiv comment field.
3. **OBLITERATUS**: commit `cb4aec45` verified (full sha `cb4aec453284a226801aec4f3bb0a023dd7ba1fb`,
   authored by Joseph Magly, repo owned by handle `elder-plinius`, AGPL-3.0 licensed). The file
   `obliteratus/analysis/cross_layer.py` defines `CrossLayerAlignmentAnalyzer` (computes
   `(D @ D.T).abs()` pairwise cosine matrix, "refusal direction clusters", and cumulative
   "angular drift"/geodesic distance) — this is a real, on-topic tool for the cross-layer
   refusal-direction claim. Full docstrings quoted verbatim in `bib_report.json.obliteratus`.
4. **Wollschlager2025** = arXiv:2502.17420, ICML 2025 (confirmed via ICML virtual poster page and
   ML Anthology). Verbatim abstract quote captured supporting "multiple independent directions
   and...multi-dimensional concept cones."
5. **LlorenteSaguer2026a/b** both confirmed (2604.18901, 2603.27412), single-author
   (Isaac Llorente-Saguer). Both papers explicitly report that harmful-intent geometry/detection
   **survives abliteration** — verbatim numbers pulled (±0.003 AUROC gap in 2604.18901; ≤0.015
   AUROC gap and σθ≈0.03 rad vs 0.27 rad in 2603.27412).
6. **The "0.016" figure is UNSOURCED — verdict DELETE.** Downloaded and grepped every `.md`/`.py`
   file in the OBLITERATUS repo (282 files at commit cb4aec45): the only hit for `0.016` is a false
   positive (an arXiv id substring `1610.01644` inside a citation list, not a cosine value). The
   `cross_layer.py` module itself has no hardcoded example numbers — it's a generic library with no
   worked example anywhere in the repo, README, or docs. Also grepped the raw PDF text of
   arXiv:2406.11717 (Arditi), 2606.24952 (Galeone), and 2502.17420 (Wollschlager): zero matches in
   all three. A general web search for the exact figure also came up empty. Replacement sentence
   proposed in `bib_report.json.figure_0016.replacement_sentence`, using OBLITERATUS's genuine
   cross-layer-drift framing plus Galeone et al.'s verified numbers (cos(d_det,d_ref) = 0.1197 base
   vs 0.1200 instruction-tuned, range [0.12, 0.20] across 4 models).
7. **Keep/prune (15 uncited entries reviewed)**: 11 KEEP (Basu2026, Chua2026, Han2025, Huang2026,
   Kwon2026, Li2026, Shairah2025, Wollschlager2025, Yu2026, Zhang2025, Zhao2025) and 4 PRUNE
   (Li2023/ITI — about truthfulness, not refusal; Meng2022/ROME — factual-knowledge editing,
   unrelated to safety/refusal; Wei2023/"Jailbroken" — generic jailbreak taxonomy, redundant
   background; Yuan2024 — a training-recipe paper, not an activation-readout/geometry paper).
   Diverged from the task's "likely PRUNE" hint for **Yu2026** (SafeSeek): its actual content —
   universal cross-model attribution of safety circuits — is directly on-topic for a
   specificity-across-checkpoints claim, so it was judged KEEP instead (reasoning in the json).
8. **8 stub `@Inproceedings` entries with no ids** (Luo2026, Muhamed2026, Aremu2026, Lan2026,
   Son2026, Chang2026, Du2026 — 7 total, task lists exactly these) all resolved to real, very recent
   (Aug–Sep 2026) arXiv preprints via exact title search + arXiv API confirmation. Several had wrong
   author names in the original stub (Huang2026's "Changhui" should be "Chang-Chieh"; Du2026's
   "Yudeng" should be "Yucheng"; Son2026's "Yu-Sin" should be "Yuri"; Lan2026's "Xin Lai" should be
   "Xinhua Lai").
9. **Missing entries added**: AMS turned out to be a **duplicate** of the already-present
   Messenger2026 IEEE Access entry (identical title, single author) — merged rather than duplicated,
   by adding `eprint = 2608.05578` to Messenger2026. Aligned Probing (TACL 2026), IRT (2608.05086,
   real title "Item Response Theory for AI Safety", 4 authors), Jorak (@misc, commit `8147de3`
   verified, Apache-2.0, repo description quoted), RAS turned out to already be present as Huang2026
   (only needed a name fix, not a new entry), Qwen3-4B-SafeRL model card (verified live on HF,
   Apache-2.0, cross-links arXiv:2510.14276), and the Qwen3 Technical Report (arXiv:2505.09388, all
   60 authors pulled from the arXiv API) were all added as new entries. Note: the tech-report key had
   to be `Yang2025` rather than `Yang2026` because `Yang2026` was already taken by an unrelated paper
   (Kia-Jüng Yang et al., 2605.26772) — a naming collision that would otherwise have silently
   overwritten an existing entry.
10. **Other defects found by the full-bib arXiv sanity sweep** (beyond what was asked): Rottger2023
    (XSTest) had `year=2023` but its own arXiv comment says "Accepted at NAACL 2024" — year
    corrected to 2024. Cui2024 (OR-Bench) had `year=2024` but its own arXiv comment says "Accepted
    to ICML 2025" — year corrected to 2025. Both had a real booktitle/year mismatch that would read
    as an anachronism if left uncorrected (e.g. citing an ICML 2024 paper for content that only
    appeared at ICML 2025).

## What was NOT independently verified
- The claim in Han2025's `note` that "Recognition-Refusal Misalignment" (Du2026) or SafeSeek
  (Yu2026) etc. are *currently uncited* in the actual paper draft — that's outside this task's
  web-only scope; `keep_prune` verdicts are recommendations for the paper author, not confirmed
  citation-graph facts.
- Whether Orgad2026, Luo2026, Muhamed2026, Aremu2026, Lan2026, Son2026 (beyond its LinkedIn
  announcement), Chang2026, Du2026, or Jiang2026 have since been accepted at a venue beyond arXiv —
  all are very recent (2026) preprints; only venues explicitly stated in an arXiv comment field, an
  ACL/TACL Anthology page, a NeurIPS/ICML virtual-poster page, or a first-party
  announcement (Son2026's LinkedIn post) were treated as confirmed.

## Files
- `blockC/bib_verified.bib` — 47 entries, all keys from the input bib plus 7 new ones
  (FonsecaRivera2026, Waldis2026, Yang2025, QwenSafeRL2026, Jorak2026, Obliteratus2026 — 6 new,
  since AMS merged into Messenger2026 rather than adding a 7th).
- `blockC/bib_report.json` — full per-entry verdicts, keep/prune table, OBLITERATUS quotes,
  Wollschläger/Llorente-Saguer quotes, the 0.016 verdict+replacement sentence, and an
  `other_defects` list for issues found outside the explicit task list.
