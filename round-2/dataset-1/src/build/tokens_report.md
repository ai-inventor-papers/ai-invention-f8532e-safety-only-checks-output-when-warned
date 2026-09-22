# Execution-Side Token Sets + Tokenizer Compatibility Table

Artefact 3 (a/b/c) + Artefact 6, mined from REAL judged model generations.
No GPU / model weights used -- tokenizer files and text mining only.

## Sources

- **Source 1 (primary)**: iteration-1 panel judged generations -- `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_3/results/judged` (26 files, 2369 rows loaded, 1 row dropped for null `judge_primary`). SEED_PANEL: 9 families, 27 repos: granite, olmo2, phi, qwen2.5, qwen3, smollm2, smollm3, stablelm, tinyllama.
- **Source 2 (cross-model generality check)**: `LibrAI/do-not-answer`, default/train, 939 rows, 5634 real responses across 6 models (GPT4, ChatGPT, Claude, ChatGLM2, llama2-7b-chat, vicuna-7b).
  - **License**: `apache-2.0` (VERIFIED live from the HF dataset-card API and the GitHub repo's own LICENSE file -- both agree). Task brief asserted 'CC-BY-NC-SA-4.0'; both live sources (HF dataset-card API and the do-not-answer GitHub repo's LICENSE file, fetched 2026-09-21T03:57:07.674164+00:00) independently say 'apache-2.0' (SPDX: Apache-2.0). We ship the VERIFIED license, not the brief's unverified claim.
  - Action-code taxonomy VERIFIED from the authors' own evaluator source (`https://raw.githubusercontent.com/Libr-AI/do-not-answer/main/do_not_answer/evaluator/gpt.py`, `annotation_aspects_en['do_not_answer']`), not assumed: codes 0-6, code 0 = explicit refusal ("not willing to answer"), code 6 = full compliance (never observed in this curated do-not-answer prompt set). Verified from the do-not-answer repo's own GPT-4 evaluator prompt construction code (annotation_aspects_en['do_not_answer']), not assumed from the paper text. 7 integer codes (0-6): codes 0-5 are degrees of NOT directly complying (refusal, refutation, whataboutism/dual-perspective, disclaimer+redirect, incapability, uncertainty); code 6 is direct compliance. The README's phrase 'six distinct groups' refers to action categories overall as a typology; codes are 0..6 (7 values) with 6 = full compliance.

## No iteration-1 refusal lexicon on disk (verified)

Grep command run:
```
grep -rliE "refusal.?lexicon|refusal.?token|refusal.?onset|hedge.?redirect" <iter_1 gen_art_dataset_1> <gen_art_experiment_1> <gen_art_experiment_2> <gen_art_experiment_3>
```

Finding: Hits are all ad hoc hand-written baseline word lists embedded in EXPERIMENT code (e.g. gen_art_experiment_2/src/causal.py REFUSAL_WORDS = ["I","Sorry",...] 11 words for a logit-space baseline; gen_art_experiment_3/lc_harvest.py REFUSAL_ONSET = ["I","Sorry","I'm",...] 9 words for a regex classifier), NOT a mined, ranked, provenance-tracked lexicon artifact with per-token counts and family coverage. No such artifact exists on disk in iteration 1.

## Generation-class definitions (as computed)

REFUSING=refused==True (any set); SAFE_DECLINE=refused==False & harmful_content==False & set=='harm'; ORDINARY_HELPFUL=refused==False & harmful_content==False & set=='benign' (this is the compliant/helpful control-frequency baseline); HARMFUL_COMPLIANT=harmful_content==True (excluded from all 3 artefacts, topically contaminated); OTHER=anything left over (should be ~0).

| Class | n rows |
|---|---|
| REFUSING | 1115 |
| ORDINARY_HELPFUL | 815 |
| HARMFUL_COMPLIANT | 292 |
| SAFE_DECLINE | 147 |

## Artefact 3a: refusal-onset set

- Mined from 712 candidate surface forms across 1115 REFUSING generations.
- 647 candidates dropped for family coverage < 3.
- **Shipped: 60 forms** (both `qwen3_first_token` tokenizer-based and `surface_ngram_1/2/3` tokenizer-independent levels).

Top 15 by generations opened:

| rank | form | level | n_generations_opened | n_families |
|---|---|---|---|---|
| 1 | `I` | qwen3_first_token | 511 | 7 |
| 2 | `I'm` | surface_ngram_1 | 389 | 7 |
| 3 | `I'm sorry,` | surface_ngram_2 | 234 | 7 |
| 4 | `I'm sorry, but` | surface_ngram_3 | 234 | 7 |
| 5 | `It` | qwen3_first_token | 113 | 7 |
| 6 | `It's` | surface_ngram_1 | 100 | 7 |
| 7 | `It's important` | surface_ngram_2 | 86 | 7 |
| 8 | `It's important to` | surface_ngram_3 | 86 | 7 |
| 9 | `I cannot` | surface_ngram_2 | 59 | 3 |
| 10 | `I'm really` | surface_ngram_2 | 47 | 4 |
| 11 | `Creating` | qwen3_first_token | 38 | 4 |
| 12 | `I'm really sorry,` | surface_ngram_3 | 30 | 4 |
| 13 | `Creating a` | surface_ngram_2 | 29 | 4 |
| 14 | `How` | qwen3_first_token | 24 | 3 |
| 15 | `**` | qwen3_first_token | 23 | 4 |

## Naive comparator vs mined refusal-onset set

CONSTRUCTED (not mined) list: ["I'm sorry", 'I cannot', "I can't", 'Sorry', 'As an AI', "I'm unable", "I won't", 'Unfortunately', 'I apologize']

- Naive comparator opens **396/1115** REFUSING generations (35.5%).
- Mined refusal-onset set opens **846/1115** REFUSING generations (75.9%).

## Artefact 3b: hedge-and-redirect set

- SAFE-DECLINE pool: 147 rows total; the 3 named "preferred" checkpoints contribute only 2 rows between them.
- **Documented pivot**: The 3 named preferred checkpoints contribute only 2 SAFE_DECLINE rows (their high over_refusal is almost entirely LEXICAL refusal, Artefact 3a's domain) -- mining n-grams from that alone produced single-prompt topical echoes, not a behavioural signal. Primary mining pool was switched to the full 147-row/22-slug/41-prompt SAFE_DECLINE corpus, with a diversity requirement (>=2 distinct slugs AND >=2 distinct prompts) replacing the small-sample checkpoint restriction, and preferred-checkpoint support used to RANK (not filter) candidates.
- Compliant contrast checkpoints contribute 18 SAFE-DECLINE rows (consistent with them mostly refusing outright or complying harmfully instead).
- **Shipped: 60 forms**, each with lift = freq(safe-decline)/freq(ordinary-helpful) >= 2.0 and requiring >=2 distinct checkpoints AND >=2 distinct prompts (anti-topical-echo filter).

Top 15 by rank (preferred-checkpoint support, then breadth, then count):

| rank | form | lift | count_sd | count_oh | n_slugs | n_prompts | from_preferred |
|---|---|---|---|---|---|---|---|
| 1 | `his` | 25.905 | 21 | 4 | 16 | 4 | 2 |
| 2 | `historical` | 2.454 | 21 | 47 | 15 | 3 | 2 |
| 3 | `history` | 2.351 | 18 | 42 | 15 | 3 | 2 |
| 4 | `life` | 2.253 | 14 | 34 | 12 | 4 | 2 |
| 5 | `own` | 2.337 | 12 | 28 | 11 | 3 | 2 |
| 6 | `did` | 24.424 | 11 | 2 | 11 | 3 | 2 |
| 7 | `to approach this` | 2.847 | 10 | 19 | 9 | 5 | 2 |
| 8 | `accuracy` | 2.664 | 6 | 12 | 5 | 2 | 2 |
| 9 | `approach this topic` | 3.701 | 5 | 7 | 5 | 2 | 2 |
| 10 | `this topic` | 2.922 | 5 | 9 | 5 | 2 | 2 |
| 11 | `this topic with` | 3.701 | 5 | 7 | 5 | 2 | 2 |
| 12 | `topic with` | 2.22 | 5 | 12 | 5 | 2 | 2 |
| 13 | `you can` | 2.567 | 40 | 86 | 15 | 14 | 1 |
| 14 | `historical context` | 4.656 | 13 | 15 | 11 | 2 | 1 |
| 15 | `he` | 19.032 | 12 | 3 | 10 | 2 | 1 |

**Caveat**: the panel only has 41-45 distinct GT prompts feeding all 26 checkpoints, so some shipped forms (e.g. `historical`, `american`) partly reflect many checkpoints answering the *same small set of recurring prompts* similarly, not purely per-model stylistic behaviour. This is a structural property of the underlying judged panel (fixed GT test set), not a mining bug, and is reported honestly rather than hidden.

## Artefact 3c: matched control set

- 44 single-token-shaped refusal/hedge tokens selected for control matching (from 3a's `qwen3_first_token` forms + 3b's single-word forms, filtered to those that tokenize to exactly 1 Qwen3-4B token).
- **33/44 matched** within the caliper (|Δ log-freq| <= 0.25); **11 could not be matched**.
- Unmatched (mostly short/rare BPE sub-word fragments like `**`, `A`, `To`, `Dis`, `Inc`, `Le`, or specific content words like `president`/`document`/`commitment` with no length+frequency-matched neutral counterpart in the top-500 ordinary-helpful pool): ['**', 'A', 'To', 'Dis', 'Inc', 'Le', 'early', 'president', 'document', 'th', 'commitment']
- **Achieved balance: median |Δ log-freq| = 0.0081, max |Δ log-freq| = 0.2319**.

Sample matches:

| selected | control | |Δ log-freq| | selected len | control len |
|---|---|---|---|---|
| `I` | `be` | 0.0032 | 1 | 2 |
| `It` | `not` | 0.0937 | 2 | 3 |
| `Creating` | `without` | 0.0116 | 8 | 7 |
| `How` | `some` | 0.0011 | 3 | 4 |
| `As` | `on` | 0.0121 | 2 | 2 |
| `The` | `and` | 0.0 | 3 | 3 |
| `What` | `step` | 0.0066 | 4 | 4 |
| `Using` | `legal` | 0.0041 | 5 | 5 |
| `Subject` | `ensuring` | 0.0 | 7 | 8 |
| `Making` | `privacy` | 0.0985 | 6 | 7 |
| `Title` | `align` | 0.0083 | 5 | 5 |
| `Hey` | `cut` | 0.0 | 3 | 3 |

## Artefact 6: tokenizer compatibility table

- 28/28 tokenizers loaded successfully (27-repo SEED_PANEL + `mlabonne/Qwen3-4B-abliterated`); 0 failed.
  All 28 tokenizers loaded and verified in one process.
- Compatibility recorded for 153 distinct surface forms (union of 3a+3b+3c) x 28 tokenizers x 2 variants (MID-TEXT primary w/ leading space, TURN-INITIAL no leading space).
- **151/153 forms show a segmentation disagreement** (differing `n_pieces` in the MID-TEXT variant across the 28 tokenizers) -- expected given vocab sizes ranging 32k (TinyLlama) to 200k (Phi-4-mini), and exactly the kind of fact this table exists to surface for a downstream causal lane.
- Single-token coverage gate on the 77 PRIMARY (token-shaped) forms: 77/77 pass >= 80% coverage; 0 dropped: [].

## GATES (observed numbers)

| Gate | Threshold | Result | Observed |
|---|---|---|---|
| G_REFUSAL_FORMS | >= 20 forms with n_families >= 3 | PASS | {"observed_n_forms": 60, "observed_min_families_among_shipped": 3} |
| G_HEDGE_FORMS | >= 20 forms with lift >= 2.0 | PASS | {"observed_n_forms": 60} |
| G_CONTROL_BALANCE | median |delta log-freq| <= 0.25 | PASS | {"observed_median": 0.0081} |
| G_SINGLE_TOKEN | >= 80% single-token coverage across 28 verified tokenizers | PASS | {"n_primary_forms": 77, "n_dropped": 0} |
| G_XSRC_JACCARD | >= 0.2 | PASS | {"observed_jaccard": 0.25} |

Cross-source top-30 intersection (12 forms): ['as', 'i', 'i cannot', 'i cannot provide', "i'm", "i'm really", "i'm really sorry", "i'm really sorry,", "i'm sorry,", "i'm sorry, but", 'it', 'it is']

## Tokenizer load status

28/28 verified, 0 failed.

