#!/bin/bash
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_2
OLD=$(pgrep -f "src/gen.py" | head -1)
n0=$(grep -c "DONE " logs/gen.log)
while true; do
  n=$(grep -c "DONE " logs/gen.log)
  if [ "$n" -gt "$n0" ]; then break; fi
  sleep 5
done
kill $OLD; sleep 3
echo "swap2 at $(date -u) (old $OLD)" >> logs/swap_gen.out
nohup setsid .venv/bin/python src/gen.py >> logs/gen_sweep.out 2>&1 &
echo "new pid $!" >> logs/swap_gen.out
