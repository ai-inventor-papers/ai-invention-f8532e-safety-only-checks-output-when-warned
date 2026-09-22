#!/usr/bin/env bash
# The running sweep read ORDER v1. Once it finishes the checkpoint it is mid-way through,
# restart it so ORDER v2 (revised after the weight fingerprints) takes effect. The sweep is
# resumable by DONE sentinels, so nothing already harvested is redone.
cd "$(dirname "$0")"
OLD=$(cat logs/sweep.pid)
for i in $(seq 1 300); do
  [ -f harvest/Qwen--Qwen3-4B/DONE ] && break
  sleep 10
done
echo "[relaunch] Qwen3-4B done at $(date +%H:%M:%S); restarting sweep with ORDER v2"
kill "$OLD" 2>/dev/null
sleep 5
nohup env OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1 \
  .venv/bin/python -u src/sweep.py --max-priority 4 --deadline-min 195 >> logs/sweep.log 2>&1 &
echo $! > logs/sweep.pid
echo "[relaunch] new sweep pid $(cat logs/sweep.pid) at $(date +%H:%M:%S)"
