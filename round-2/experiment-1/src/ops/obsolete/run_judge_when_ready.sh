#!/usr/bin/env bash
# The commissioned child mlabonne/Qwen3-4B-abliterated carries NO judged behavioural row
# from iteration 1, so its effectiveness label is UNKNOWN and it cannot enter E1. Generate
# and grade a reduced behavioural set for it as soon as its harvest finishes.
cd "$(dirname "$0")"
for i in $(seq 1 240); do
  [ -f harvest/mlabonne--Qwen3-4B-abliterated/DONE ] && break
  sleep 20
done
if [ ! -f harvest/mlabonne--Qwen3-4B-abliterated/DONE ]; then
  echo "[judge-chain] mlabonne never harvested; skipping"; exit 0
fi
echo "[judge-chain] starting at $(date +%H:%M:%S)"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1 \
  .venv/bin/python -u src/judge_ext.py --repos mlabonne/Qwen3-4B-abliterated \
  --n 25 --max-new 48 > logs/judge_ext.log 2>&1
echo "[judge-chain] done at $(date +%H:%M:%S)"
