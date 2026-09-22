#!/bin/bash
# DECLARED SECONDARY GRID. STAGE 9b showed the real community abliteration uses one
# direction PER LAYER (layer 0's is orthogonal to layer 35's, cos 0.016). The registered
# single-pinned-direction grid is therefore not the faithful replica; this arm is.
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_2
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8 PYTHONUNBUFFERED=1
while pgrep -f "run_all.sh" > /dev/null; do sleep 20; done
echo "=== main grid finished, starting PER-LAYER grid $(date +%H:%M:%S) ==="
for LG in L2 L3 L1 L4; do
  echo "=== START ${LG}PL $(date +%H:%M:%S) ==="
  .venv/bin/python -u src/run_lineage.py "$LG" --perlayer > "logs/${LG}PL.log" 2>&1
  rc=$?
  grep -vE "Loading weights|it/s\]" "logs/${LG}PL.log" | tail -12
  echo "=== END ${LG}PL $(date +%H:%M:%S) rc=$rc ==="
done
echo "ALL PER-LAYER DONE"
