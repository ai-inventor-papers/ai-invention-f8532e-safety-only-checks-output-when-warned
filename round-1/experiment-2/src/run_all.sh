#!/bin/bash
# LANE B driver: harvest every lineage across the alpha grid.
# L2/L3 first - the Instruct/SafeRL parent-child contrast is the whole point (cut C5).
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_2
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8
export PYTHONUNBUFFERED=1
for LG in "$@"; do
  echo "=== START $LG $(date +%H:%M:%S) ==="
  .venv/bin/python -u src/run_lineage.py "$LG" > "logs/${LG}.log" 2>&1
  rc=$?
  grep -vE "Loading weights|it/s\]" "logs/${LG}.log" | tail -30
  echo "=== END $LG $(date +%H:%M:%S) rc=$rc ==="
  if [ $rc -ne 0 ]; then echo "LINEAGE $LG FAILED rc=$rc"; fi
done
echo "ALL LINEAGES DONE"
