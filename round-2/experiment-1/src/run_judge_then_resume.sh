#!/usr/bin/env bash
# Pause the harvest sweep BETWEEN checkpoints, run the judge extension for the commissioned
# child alone (a second resident 4B model would risk an OOM-kill in the 16 GB cgroup), then
# resume the supervised sweep. Every step is logged with a timestamp.
cd "$(dirname "$0")"
SWEEP_PID=$(cat logs/sweep.pid)
echo "[jr] $(date +%T) waiting for Qwen--Qwen3-1.7B/DONE (sweep pid $SWEEP_PID)"
until [ -f harvest/Qwen--Qwen3-1.7B/DONE ] || ! kill -0 "$SWEEP_PID" 2>/dev/null; do sleep 5; done
kill "$SWEEP_PID" 2>/dev/null && echo "[jr] $(date +%T) sweep $SWEEP_PID paused after Qwen3-1.7B"
sleep 5
echo "[jr] $(date +%T) judge extension START"
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 PYTHONUNBUFFERED=1 .venv/bin/python -u src/judge_ext_lanec.py \
  --repo mlabonne/Qwen3-4B-abliterated > logs/judge_ext_mlabonne.log 2>&1
echo "[jr] $(date +%T) judge extension END rc=$?"
REMAIN=$(( 12600 - ( $(date +%s) - $(date -d 07:19:50 +%s) ) ))
echo "[jr] $(date +%T) resuming supervised sweep for ${REMAIN}s"
./supervise_sweep.sh "$REMAIN" >> logs/supervise2.log 2>&1
