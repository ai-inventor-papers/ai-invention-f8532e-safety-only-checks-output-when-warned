#!/bin/bash
# RESUME (session 2, 2026-09-21 ~13:55 UTC): the first session's harvest chain died at 13:24 UTC when its
# scratchpad venv was reaped (Vikhr-Instruct DONE; Vikhr-abliterated partial -> deleted and redone).
# Truth + prereg are already committed (hash_chain.jsonl); harvest_panel.py re-verifies the order gate
# for every panel checkpoint. Panel first, then the full random-init control.
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1
export HF_HOME=$PWD/hf_cache HF_HUB_CACHE=$PWD/hf_cache PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_PROGRESS_BARS=1
echo "[resume] start $(date -u +%T)"
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HARVEST_THREADS=2 .venv/bin/python -u src/harvest_panel.py
echo "[resume] panel harvest finished $(date -u +%T) exit=$?"
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HARVEST_THREADS=2 .venv/bin/python -u src/harvest_panel.py --smoke
echo "[resume] random-init control finished $(date -u +%T) exit=$?"
