#!/usr/bin/env bash
# Wait until the 20-tag panel is harvested (or 04:15), then back-fill the tier-3 arrays and the
# AMS baseline onto every harvested tag, with a hard deadline so the wrap window is protected.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
export TORCH_DISABLE_NATIVE_JIT=1 PYTORCH_ALLOC_CONF=expandable_segments:True OMP_NUM_THREADS=4 \
       OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1
while :; do
  n=$(ls arrays/HG__*/DONE 2>/dev/null | wc -l)
  [ "$n" -ge 20 ] && break
  [ "$(date -u +%H%M)" -ge 0415 ] && break
  sleep 45
done
echo "$(date -u +%T) tier3 back-fill starting (panel harvested=$(ls arrays/HG__*/DONE 2>/dev/null|wc -l))" >> logs/tier3_backfill.log
./.venv_gpu/bin/python src/tier3_backfill.py --deadline-utc 2026-09-22T04:45:00Z >> logs/tier3_backfill.log 2>&1
echo "$(date -u +%T) tier3 back-fill rc=$? " >> logs/tier3_backfill.log
