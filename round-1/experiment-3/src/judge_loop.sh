#!/bin/bash
# Run the incremental per-file judge repeatedly WHILE the harvest sweep is alive,
# so each checkpoint is judged as soon as it lands; then a final pass.
cd "$(dirname "$0")"
while pgrep -f "lc_harvest.py --order" >/dev/null; do
  .venv/bin/python lc_judge.py --concurrency 24 >> logs/judge_loop.out 2>&1
  sleep 30
done
.venv/bin/python lc_judge.py --concurrency 24 >> logs/judge_loop.out 2>&1
echo "JUDGE_LOOP_DONE $(date +%H:%M:%S)" >> logs/judge_loop.out
