#!/usr/bin/env bash
# The cgroup memory ceiling on this box is ~15 GB and a 4B model in bfloat16 is ~8 GB, so an
# OOM kill is a real possibility. An OOM kill is SIGKILL: the sweep's per-checkpoint
# try/except cannot catch it and the whole process dies. The sweep is resumable by DONE
# sentinels, so the right response is to restart it. This supervisor does that until the
# wall-clock budget runs out, and records every restart.
cd "$(dirname "$0")"
END=$(( $(date +%s) + ${1:-10800} ))
RESTARTS=0
while [ "$(date +%s)" -lt "$END" ]; do
  PID=$(cat logs/sweep.pid 2>/dev/null)
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then sleep 30; continue; fi
  # did it finish cleanly?
  if grep -aq "SWEEP END" logs/sweep.log 2>/dev/null; then
    echo "[supervise] sweep reported SWEEP END at $(date +%H:%M:%S); stopping supervisor"
    break
  fi
  REMAIN=$(( (END - $(date +%s)) / 60 ))
  [ "$REMAIN" -lt 3 ] && { echo "[supervise] <3 min left; not restarting"; break; }
  RESTARTS=$((RESTARTS+1))
  echo "[supervise] sweep is gone (restart #$RESTARTS) at $(date +%H:%M:%S); ${REMAIN} min left"
  nohup env OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
    PYTHONUNBUFFERED=1 .venv/bin/python -u src/sweep.py --max-priority 4 \
    --deadline-min "$REMAIN" >> logs/sweep.log 2>&1 &
  echo $! > logs/sweep.pid
  sleep 30
done
echo "[supervise] done at $(date +%H:%M:%S) after $RESTARTS restart(s)"
