#!/usr/bin/env bash
# Wait for the T2 lesion control to exit, then run the edit-recipe fingerprints.
# Keeps at most 3 CPU-bound processes alive at once on this 2-core box.
cd "$(dirname "$0")"
T2PID=$(cat logs/t2.pid)
while kill -0 "$T2PID" 2>/dev/null; do sleep 15; done
echo "[chain] t2 finished, starting weightfp at $(date +%H:%M:%S)"
OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONUNBUFFERED=1 \
  .venv/bin/python -u src/weightfp.py --deadline-min 60 > logs/weightfp.log 2>&1
echo "[chain] weightfp finished at $(date +%H:%M:%S)"
