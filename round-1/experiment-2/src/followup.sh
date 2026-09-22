#!/bin/bash
# Registered STAGE 7 first, then the DECLARED per-layer secondary grid.
# alpha=1 is not arbitrary: STAGE 9 measures the real community abliteration's
# implied strength at alpha = 0.973, so alpha=1 IS the community operating point.
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_2
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8 PYTHONUNBUFFERED=1
while pgrep -f "run_all[.]sh" > /dev/null; do sleep 20; done
echo "=== registered grid finished $(date +%H:%M:%S) ==="
for LG in L2 L3 L1 L4; do
  for AL in 0.0 1.0; do
    echo "=== STAGE7 causal $LG a=$AL $(date +%H:%M:%S) ==="
    .venv/bin/python -u src/causal.py "$LG" --alpha "$AL" --items 48 > "logs/causal_${LG}_${AL}.log" 2>&1
    rc=$?
    grep -vE "Loading weights|it/s]" "logs/causal_${LG}_${AL}.log" | tail -24
    echo "=== END causal $LG a=$AL rc=$rc ==="
  done
done
echo "=== CAUSAL DONE, starting PER-LAYER grid $(date +%H:%M:%S) ==="
for LG in L2 L3 L1 L4; do
  echo "=== START ${LG}PL $(date +%H:%M:%S) ==="
  .venv/bin/python -u src/run_lineage.py "$LG" --perlayer > "logs/${LG}PL.log" 2>&1
  rc=$?
  grep -vE "Loading weights|it/s]" "logs/${LG}PL.log" | tail -10
  echo "=== END ${LG}PL $(date +%H:%M:%S) rc=$rc ==="
done
echo "ALL FOLLOWUP DONE"
