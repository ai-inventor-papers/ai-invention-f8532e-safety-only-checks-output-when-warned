# Data Sourcing Report — LLM Safety / Refusal Frozen Dataset

Workspace: `gen_art_dataset_1` · Generated: 2026-09-21

## Summary

- **64** distinct HF dataset searches run (target was 50+), saved to `build/hf_search_log.json` (294 unique dataset ids surfaced).
- **25** candidates previewed (configs/splits/features + live gated/license check + 3 sample rows per config), saved to `build/hf_candidates.json`.
- **25/25** candidates researched with a cited provenance paragraph each, saved to `build/hf_candidate_research.json`.
- **17 downloaded artifacts** from **15 distinct benchmarks/repos** kept, saved under `temp/datasets/<name>/data.json` + `_meta.json`.
- **Total downloaded bytes: 120.84 MB** (well under the 250 MB hard cap). Breakdown in `build/sources_manifest.json`.
- **Graded harm severity source found**: `PKU-Alignment/PKU-SafeRLHF` (`response_0_severity_level` / `response_1_severity_level`, ordinal 0-3, verified against real downloaded rows: counts {0: 3835/3998, 1: 540/515, 2: 3151/3163, 3: 685/535} across the two response slots). We do **not** need to ship `graded_harm=null`.

## KEEP / DISCARD table

| # | Source | Verdict | Rows kept | Reason |
|---|---|---|---|---|
| 1 | XSTest (GitHub `paul-rottger/exaggerated-safety`) | KEEP | 450 | Primary source per spec; header + row count matched exactly live (`id,prompt,type,label,focus,note`) |
| 2 | `bench-llm/or-bench` (hard-1k) | KEEP | 1,319 | Matches spec exactly |
| 3 | `bench-llm/or-bench` (toxic) | KEEP | 655 | Matches spec exactly |
| 4 | `bench-llm/or-bench` (80k) | KEEP (sampled) | 8,000 / 80,359 | Sampled to stay under byte budget per hard rule 1 |
| 5 | `furonghuang-lab/PHTest` | KEEP | 3,269 | Matches spec exactly; ungated |
| 6 | `AmazonScience/FalseReject` (train) | KEEP | 14,624 | Primary source resolved ungated live (contrary to needing a fallback) |
| 7 | `AmazonScience/FalseReject` (test) | KEEP | 1,187 | Human-annotated eval split |
| 8 | SORRY-Bench WRAPPED (`SillyTilly/SorryBench`) | KEEP (fallback #1) | 9,450 | Official `sorry-bench/sorry-bench-202406` **and** `-202503` both confirmed `gated='auto'` live; first ungated fallback in the specified order matched expected columns/shape exactly (450 base Qs × 21 `prompt_style` variants including `base`); vintage = **202406** (per `sorry_bench_202406.csv` sibling file) |
| 9 | `JailbreakBench/JBB-Behaviors` (behaviors/harmful) | KEEP | 100 | Matches spec |
| 10 | `JailbreakBench/JBB-Behaviors` (behaviors/benign) | KEEP | 100 | Matches spec |
| 11 | `JailbreakBench/JBB-Behaviors` (judge_comparison/test) | KEEP | 300 | Matches spec |
| 12 | AdvBench (GitHub `llm-attacks/llm-attacks`) | KEEP (fallback) | 520 | `walledai/AdvBench` verified **gated='auto' live** (contradicts task assumption) → fell back to the original GCG-paper GitHub CSV; cross-checked against ungated mirror `carl213/advbench` (520 rows, same schema) |
| 13 | `LibrAI/do-not-answer` | KEEP | 939 | Matches spec exactly (939 rows, 23 columns) |
| 14 | `allenai/ai2_arc` (ARC-Easy/test) | KEEP | 2,376 | Matches spec exactly, matches original paper's own Easy-Test count |
| 15 | `openai/gsm8k` (main/test) | KEEP | 1,319 | Canonical GSM8K test split |
| 16 | `PKU-Alignment/PKU-SafeRLHF` (test) | KEEP | 8,211 | **Graded harm severity source** — ordinal `severity_level` field |
| 17 | `PKU-Alignment/BeaverTails` (30k_test) | KEEP (extra, item #12) | 3,021 | Additional strong, independently-curated harmful/harmless QA source (NeurIPS 2023); small split chosen to stay in budget |
| — | `sorry-bench/sorry-bench-202503` | DISCARD | 0 | **Gated='auto'**, verified live |
| — | `sorry-bench/sorry-bench-202406` | DISCARD | 0 | **Gated='auto'**, verified live |
| — | `AIM-Harvard/sorrybench` | DISCARD | 0 | Not needed — fallback #1 (SillyTilly) already matched spec; also thin documentation |
| — | `AlignmentResearch/SorryBench` | DISCARD | 0 | Not needed; repackaged into pos/neg splits, thin documentation |
| — | `kylelovesllms/sorry-bench-with-refusals` | DISCARD | 0 | **Verified**: `refusal` column is 1 identical template string across all 100 sampled rows |
| — | `chcleung/sorry_bench_with_refusals` | DISCARD | 0 | **Verified**: `refusal` column drawn from only 15 fixed templates, uncorrelated with prompt content |
| — | `walledai/AdvBench` | DISCARD | 0 | **Gated='auto'**, verified live — see fallback above |
| — | `carl213/advbench` | DISCARD (cross-check only) | 0 | Unofficial re-upload; used only to confirm row count, not downloaded as the source of record |
| — | `Locutusque/FalseReject-sharegpt` | DISCARD | 0 | Not needed — primary FalseReject resolved ungated |
| — | `Brantliu/FalseReject` | DISCARD | 0 | Not needed (not even previewed — primary resolved fine) |
| — | `allenai/wildguardmix` | EXCLUDE | 0 | **Gated='auto'**, verified live |
| — | `allenai/wildjailbreak` | EXCLUDE | 0 | **Gated='auto'**, verified live |
| — | `walledai/HarmBench` | DISCARD | 0 | **Gated='auto'**, verified live (whole `walledai/*` namespace we sampled is now gated); not in required-12, GitHub fallback not chased this iteration |
| — | `walledai/StrongREJECT` | DISCARD | 0 | **Gated='auto'**, verified live; not in required-12 |
| — | `tau/commonsense_qa` | DISCARD | 0 | Auto-gradable benign pool already covered by ARC-Easy + GSM8K |
| — | `nvidia/Aegis-AI-Content-Safety-Dataset-2.0` | DISCARD (documented for later) | 0 | Green flags across the board (peer-reviewed, ungated, CC-BY-4.0); not pulled in to stay in scope |
| — | `allenai/real-toxicity-prompts` | DISCARD | 0 | Overlaps with or-bench-toxic / PKU-SafeRLHF severity for the toxicity axis |
| — | `deepset/prompt-injections` | DISCARD | 0 | Out of scope (prompt injection, not refusal/over-refusal) |
| — | `natolambert/xstest-v2-copy` | DISCARD | 0 | **Verified**: lacks `focus`/`label` columns, excluded per task instructions |

## Failures and fallbacks taken (in order)

1. **SORRY-Bench**: `sorry-bench/sorry-bench-202503` → GATED (auto). `sorry-bench/sorry-bench-202406` → GATED (auto). `SillyTilly/SorryBench` → **ungated, used** (vintage 202406, exact expected schema).
2. **AdvBench**: `walledai/AdvBench` → GATED (auto) — this **contradicts the task brief's assumption** that it was a plain ungated mirror; verified live via both `HfApi.dataset_info` (`gated: 'auto'`) and a 401 from `datasets-server.huggingface.co/first-rows`. Fell back to the **original GitHub source** (`llm-attacks/llm-attacks`, the GCG paper's own repo), which is ungated and matches the paper's released `harmful_behaviors.csv` (520 rows) exactly; cross-checked against the community HF mirror `carl213/advbench` (520 rows, same columns).
3. **FalseReject**: `AmazonScience/FalseReject` verified **ungated** live — no fallback needed, downloaded directly (both train and test splits, since budget allowed).
4. **wildguardmix / wildjailbreak**: both verified **gated='auto'** live, excluded as instructed.
5. **walledai/HarmBench, walledai/StrongREJECT**: both discovered **gated='auto'** live during the wide screen. Not part of the required-12 sources, so no GitHub fallback was pursued this iteration (their original GitHub sources — `centerforaisafety/HarmBench` and the StrongREJECT NeurIPS repo — are reachable and would be the natural fallback for a future pass).

## Notable corrections to the task brief (all independently verified, not assumed)

- **`LibrAI/do-not-answer` license**: the task brief said CC-BY-NC-SA-4.0. Verified live from both the HF dataset card's YAML front-matter and the GitHub repo's own `LICENSE` file (`github.com/Libr-AI/do-not-answer`): the actual license is **Apache-2.0**. Recorded as such in `sources_manifest.json`.
- **`walledai/AdvBench` gating**: the task brief assumed this was a plain ungated mirror; live verification on 2026-09-21 shows it (and its sibling `walledai/HarmBench`, `walledai/StrongREJECT`) now returns `gated='auto'`. See fallback #2 above.
- **Do-Not-Answer action taxonomy**: the paper's prose (Section 5.1) describes 6 categories (0-5), but the dataset's own generation code (`do_not_answer/evaluator/gpt.py` in the GitHub repo, both the Chinese and English `annotation_aspects` dicts) defines **7** codes, **0-6** — code 5 (uncertainty) and code 6 (direct compliance) are distinct from the paper's compressed prose description. `build/dna_action_taxonomy.json` was corrected to the code-verified 0-6 taxonomy, sourced directly from the evaluator source file (confirmed by fetching `https://raw.githubusercontent.com/Libr-AI/do-not-answer/main/do_not_answer/evaluator/gpt.py` and reading `annotation_aspects_en["do_not_answer"]`), rather than the paper's summarized text.

## Graded harm severity

**Found and downloaded.** `PKU-Alignment/PKU-SafeRLHF` (test split, 8,211 rows) carries `response_0_severity_level` / `response_1_severity_level`, an ordinal field over the paper's three named tiers (Minor / Moderate / Severe, plus a 0 = no/safe-harm level), verified against 19 harm categories. Live value counts from the actual downloaded rows: `response_0_severity_level` = {0: 3835, 1: 540, 2: 3151, 3: 685}; `response_1_severity_level` = {0: 3998, 1: 515, 2: 3163, 3: 535}. This is the only ordinal harm-severity column found across all 25 screened candidates (RealToxicityPrompts has a *continuous* toxicity score, not an ordinal grade, and was not downloaded — see candidate research). We therefore do **not** need to ship `graded_harm=null`.

## Total downloaded bytes

**120,839,439 bytes ≈ 120.84 MB** across all 17 downloaded artifacts (well under the 250 MB hard cap; see `build/download_summary.json` for the HF-side total and `temp/datasets/{xstest_github,advbench_github}/_meta.json` for the two GitHub-side downloads).

## Strata we could NOT find an ungated source for

- None of the 12 required strata are unfilled. The two gated-official sources (SORRY-Bench vintages, AdvBench mirror) both have working ungated fallbacks in place, documented above.
- Two optional/wide-screen candidates (`walledai/HarmBench`, `walledai/StrongREJECT`) are gated with no fallback pursued this iteration — flagged for a future iteration if their coverage is needed (GitHub originals are reachable and ungated).

## Files

- `build/hf_search_log.json` — all 64 raw search results
- `build/hf_candidates.json` — 25 candidate previews (metadata + sample rows)
- `build/hf_candidate_research.json` — 25 provenance paragraphs with URLs
- `build/repo_meta/*.json` — per-repo gated/license/siblings checks (22 repos)
- `build/dna_action_taxonomy.json` — Do-Not-Answer action code taxonomy, source-code-verified
- `build/sources_manifest.json` — one entry per downloaded artifact
- `build/download_summary.json` — raw download job log (HF-side sources)
- `temp/datasets/<name>/data.json` + `_meta.json` — the 17 downloaded artifacts
- `src/run_hf_searches.py`, `src/check_repo_meta.py`, `src/preview_candidates.py`, `src/download_sources.py`, `src/download_github_sources.py`, `src/build_manifest.py` — all scripts used, runnable end to end
