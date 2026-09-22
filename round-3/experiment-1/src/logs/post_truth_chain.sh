#!/bin/bash
# waits for all 10 panel checkpoints to be judged, then: commit truth -> freeze prereg -> harvest panel
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1
export HF_HOME=$PWD/hf_cache HF_HUB_CACHE=$PWD/hf_cache PYTHONUNBUFFERED=1 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_PROGRESS_BARS=1
N=$(.venv/bin/python -c "import json; t=json.load(open('results/panel_trim.json')); print(len(t['final_panel']))")
echo "[chain] waiting for $N judged files $(date -u +%T)"
until [ "$(ls private/judged/*.jsonl 2>/dev/null | wc -l)" -ge "$N" ]; do sleep 5; done
echo "[chain] all judged $(date -u +%T)"
OMP_NUM_THREADS=2 .venv/bin/python src/outcomes.py --commit || { echo "[chain] TRUTH FAILED"; exit 1; }
OMP_NUM_THREADS=2 .venv/bin/python src/prereg.py || { echo "[chain] PREREG FAILED"; exit 1; }
echo "[chain] truth+prereg committed $(date -u +%T); starting harvest"
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 HARVEST_THREADS=2 .venv/bin/python -u src/harvest_panel.py
echo "[chain] harvest finished $(date -u +%T)"
