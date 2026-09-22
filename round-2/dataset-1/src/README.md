# Iteration-2 dataset substrate — model pairs, hard prompts, refusal tokens

Twelve frozen artefacts for the iteration-2 execution screen of run `run_YqmEFECOIR3D`
(*cheap activation-level safety metric for Qwen3-4B and friends*). Everything here is
**metadata, tokenizers and text**. No model weights were downloaded, no forward pass was
run, no activations were read, and no deliverable metric was computed — those belong to
the experiment lanes.

**Prereg SHA-256: `b3849ae02159573c253b85644bb2a4c7fd9712db531bbccf03e8917f40d11f12`**
(recomputed from `prereg.json` on disk at assembly time: `b3849ae02159573c253b85644bb2a4c7fd9712db531bbccf03e8917f40d11f12` — gate `G_PREREG_HASH`)

## Gates — 22 PASS / 3 FAIL / 0 N/A

Every failed gate is named here with its number, in the artifact's own summary:

- **G_EFFECTIVE_IN_STRATUM FAILED** — threshold `>= 4`, observed `2`
- **G_NONEFFECTIVE FAILED** — threshold `>= 2`, observed `0`
- **G_PROXY_HARD FAILED** — threshold `<= 0.85 (FAIL above 0.90)`, observed `0.8852`

| gate | threshold | observed | status |
|---|---|---|---|
| `G_COMMISSIONED_PAIR` | present | qwen3__Qwen3-4B-abliterated | **PASS** |
| `G_CONTROL_BALANCE` | <= 0.25 | 0.0081 | **PASS** |
| `G_DEDUP` | 0 remaining | 0 | **PASS** |
| `G_DISJOINT_ITER1` | empty intersection | 0 | **PASS** |
| `G_DOWNLOAD_BUDGET` | < 300 MB | 125.49 | **PASS** |
| `G_EFFECTIVE_IN_STRATUM` | >= 4 | 2 | **FAIL** |
| `G_FAMILIES` | >= 8 | 13 | **PASS** |
| `G_FRESH_HELDOUT` | >= 3 | 3 | **PASS** |
| `G_HEDGE_FORMS` | >= 20 | 24 | **PASS** |
| `G_JOIN_CONSISTENCY` | max abs difference < 1e-9 | 0.0 | **PASS** |
| `G_NONEFFECTIVE` | >= 2 | 0 | **FAIL** |
| `G_NO_WEIGHTS` | 0 files | 0 | **PASS** |
| `G_PAIRS_TOTAL` | >= 12 | 18 | **PASS** |
| `G_PREREG_HASH` | exact string equality | b3849ae02159573c253b85644bb2a4c7fd9712db531bbccf03e8917f40d11f12 | **PASS** |
| `G_PROBE_DISJOINT` | empty | 0 | **PASS** |
| `G_PROBE_NS` | all met | {"probe_harmful": 160, "probe_hard_benign": 154, "probe_already_correct_benign": 200, "... | **PASS** |
| `G_PROXY_EASY` | >= 0.95 | 0.9561 | **PASS** |
| `G_PROXY_HARD` | <= 0.85 (FAIL above 0.90) | 0.8852 | **FAIL** |
| `G_RECOG_BENIGN` | >= 600 | 771 | **PASS** |
| `G_RECOG_TOTAL` | >= 1300 | 1509 | **PASS** |
| `G_REFUSAL_FORMS` | >= 20 | 60 | **PASS** |
| `G_RUBRIC_HASH` | present and byte-identical | {"rubric_md_sha256": "b11e322dc64e25f79bdb909fdda571fd856345a4b74b39c827d7bfd431194629"... | **PASS** |
| `G_SINGLE_TOKEN` | >= 0.80 | {"n_primary_forms": 77, "n_dropped": 0, "dropped_forms": [], "n_tokenizers_verified": 2... | **PASS** |
| `G_TINYLLAMA` | resolved | [{"pair_id": "tinyllama__TinyLlama-1.1B-Chat-v1.0-abliterated", "cause": "missing_shard... | **PASS** |
| `G_XSRC_JACCARD` | >= 0.20 | 0.25 | **PASS** |

## What is shipped

| set | rows |
|---|---|
| `paired_lineage_registry` | 60 |
| `hard_recognition_set` | 1509 |
| `refusal_onset_tokens` | 60 |
| `hedge_redirect_tokens` | 24 |
| `matched_control_tokens` | 33 |
| `tokenizer_compatibility_table` | 8568 |
| `probe_harmful` | 160 |
| `probe_hard_benign` | 154 |
| `probe_already_correct_benign` | 200 |
| `probe_baseline_disjoint` | 40 |

Side files: `prereg.json` + `prereg.sha256` (the Phase-A freeze), `prereg_addendum.json`
(binds the sealed-truth hash to the frozen prereg), `sealed_truth.json` +
`sealed_truth.sha256`, `gates.json`, `build_log.txt` (timestamped, append-only, proving
the freeze preceded every label and split).

## Layout

```
prereg.json / prereg.sha256      PHASE A freeze: thresholds, split rules, gate list
prereg_addendum.json             sealed_truth hash, bound to the prereg it extends
full_data_out.json               the ten in-file sets (exp_sel_data_out schema)
full_/mini_/preview_data_out.json  size variants
gates.json                       every gate with its observed number and status
sealed_truth.json                the two sealed families' true deltas (DISCLOSED_UPSTREAM)
build_log.txt                    append-only ordering proof
assets/rubric_iter1.md           iteration-1 grading rubric, verbatim
assets/lc_judge_iter1.py         iteration-1 judge script, verbatim
src/                             every build step, in dependency order
build/                           intermediate JSON each step hands to the next
temp/datasets/                   the downloaded public corpora
logs/                            loguru run logs
```

## How to run

```bash
./install.sh     # uv venv + deps
./rebuild.sh     # every phase in dependency order
```

`src/phase_a_prereg.py` **refuses to overwrite an existing `prereg.json`**. The freeze is
deliberately not re-runnable: a changed rule means a new file with a new hash and a logged
reason.

## Things a reader should know before using this

1. **Precision.** Every behavioural rate rests on n=45 harm / 45 benign judged items
   (60/60 for `Qwen__Qwen3-0.6B-Base`, 45/44 for `microsoft__Phi-4-mini-instruct`). A
   point estimate of 0.156 carries a Wilson 95% interval of roughly [0.08, 0.29], and the
   +0.15 effectiveness threshold is of the same order as that interval width. Every pair
   therefore ships `delta_ci95` (Newcombe) and `label_robust`; a pair whose interval
   straddles its deciding threshold is relabelled `AMBIGUOUS` whatever the point estimate
   says. This artifact cannot enlarge n — that needs new generations and a GPU.
2. **The seal is already compromised.** The iteration-2 strategy text prints both sealed
   pairs' judged deltas. `seal_status` is `DISCLOSED_UPSTREAM` for them. The only
   genuinely blind confirmation material is the seeded-hash FRESH held-out pairs and the
   never-loaded 54-scenario XSTest split.
3. **Readout class.** Every row carries `readout_class`. The registry and the raw card
   text are `metadata`/`text` and are therefore **baseline** material by construction. The
   run's deliverable metric must read activations or weights; nothing here may be promoted
   into that role by a later table.
4. **Denominator convention.** One of the 2,370 iteration-1 judged rows (Phi-4-mini benign
   `orh_244`) has an unparsable primary judge output. Iteration 1's published columns drop
   it from the denominator; this rebuild adopts the same convention, which is why
   `G_JOIN_CONSISTENCY` reads exactly 0 and not 1.46e-2. `build_log.txt` records both runs.
5. **Hardness is measured, not claimed.** The TF-IDF text proxy is reported on the easy
   anchors and on the hard subset, with the top-20 leaking features. It is a *textual*
   proxy; the activation-level headroom check is the experiment lanes' job.
6. **No iteration-1 refusal lexicon exists.** A targeted grep across `gen_art_dataset_1`
   and all three iteration-1 experiment lanes found none. The token sets are built from
   nothing, and a constructed naive comparator ships alongside them so the screen can
   quantify what mining adds over the obvious guess.

## Restoring removed files

Only two paths are marked for deletion in `.aii/manifest.yaml`, and both come straight
back:

| deleted path | how to restore |
|---|---|
| `.venv/` (2.4 GB, redownloadable) | `./install.sh` |
| `**/__pycache__/` (regenerable) | nothing to run — Python rewrites it on the next `./rebuild.sh` |

Everything else is kept: `build/` (9.7 MB of intermediate JSON each phase hands to the
next) and `temp/datasets/` (144 MB of corpus snapshots) are what the frozen row ids point
at, and re-downloading them later could pick up a changed upstream revision.

`temp/datasets/` is nevertheless EXCLUDED FROM THE PUBLIC REPOSITORY via
`upload_ignore_regexes`: these are third-party corpora and four of the downloaded files
(BeaverTails, FalseReject train, FalseReject test, PKU-SafeRLHF) are CC-BY-NC, so this
artifact should not redistribute them. `build/sources_manifest.json`
records the repo id, config, split, revision, license and byte count of every one, so any
reader can re-fetch them:

```bash
.venv/bin/python src/download_sources.py        # HuggingFace corpora
.venv/bin/python src/download_github_sources.py # XSTest and AdvBench CSVs
```

Per-row `metadata_license` is carried throughout so downstream release decisions stay
auditable.
