#!/usr/bin/env bash
# Rebuild every shipped file from the frozen prereg, in dependency order.
# NOTE: src/phase_a_prereg.py REFUSES to overwrite an existing prereg.json - the freeze
# is deliberately not re-runnable. Delete prereg.json only if you intend to create a NEW
# freeze with a NEW hash, and log the reason in build_log.txt.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python

# --- PHASE A: freeze the rules before any label, split or proxy exists
[ -f prereg.json ] || $PY src/phase_a_prereg.py

# --- PHASE B: recompute the iteration-1 rates, contamination + disjointness bookkeeping
$PY src/behavioural_join.py

# --- source acquisition (skip if temp/datasets/ is already populated)
$PY src/run_hf_searches.py          # 64 HF dataset searches
$PY src/preview_candidates.py       # preview + research the 25 candidates
$PY src/download_sources.py         # the HuggingFace corpora
$PY src/download_github_sources.py  # XSTest and AdvBench CSVs
$PY src/fetch_donotanswer.py        # LibrAI/do-not-answer + its action taxonomy
$PY src/build_manifest.py           # build/sources_manifest.json

# --- ARTEFACT 1 metadata (live Hub; no weights)
$PY src/build_registry.py

# --- ARTEFACT 2
$PY src/build_recognition_set.py

# --- ARTEFACTS 3 + 6, then the hedge re-mine that supersedes pass 1
$PY src/mine_tokens.py
$PY src/remine_hedge.py
$PY src/write_report.py

# --- PHASE C/D/E
$PY src/phase_c_label.py            # join the behavioural delta, apply the frozen labels
$PY src/phase_d_probes.py           # the four disjoint probe pools
$PY src/phase_e_assemble.py         # full_data_out.json + gates.json

# --- docs and the structured summary
$PY src/write_readme.py
$PY src/write_struct_out.py
