#!/bin/bash
# L4's harvest process was started BEFORE the sharded writer existed, so it still emits
# single ~386MB files. Convert each one as soon as it is safely stale, until the whole
# followup pipeline is finished.
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_2
export OMP_NUM_THREADS=4 PYTHONUNBUFFERED=1
for i in $(seq 1 240); do
  .venv/bin/python -u src/shard_harvest.py --min-age-sec 90 2>&1 | grep -E "CONVERTED|STILL|remaining over" 
  if grep -q "ALL FOLLOWUP DONE" logs/followup.log 2>/dev/null; then
    echo "followup finished; final pass"
    .venv/bin/python -u src/shard_harvest.py --min-age-sec 5 2>&1 | tail -6
    break
  fi
  sleep 45
done
echo "SHARD WATCH EXIT $(date +%H:%M:%S)"
