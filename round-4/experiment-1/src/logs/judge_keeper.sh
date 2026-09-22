#!/bin/bash
# keeps exactly one judge watcher alive while any generation file lacks a judged file (generation processes write
# gen_sweep_finished.flag when THEY finish, which lets a watcher exit although another generator is still running)
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
JPID=14881
while true; do
  if ! kill -0 $JPID 2>/dev/null; then
    pending=0
    for g in private/gens/*.jsonl; do
      b=$(basename $g .jsonl)
      case "$b" in *__resave) continue;; esac
      [ -f private/judged/$b.jsonl ] || pending=1
    done
    gen_alive=$(pgrep -f "src/gen_variants.py" | wc -l)
    if [ $pending = 1 ] || [ $gen_alive -gt 0 ]; then
      rm -f results/gen_sweep_finished.flag
      nohup /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-4-gen-art-gen-art-experiment-1/3c45c2e0-6b4c-4b03-ad27-13fd166c1366/scratchpad/venv/bin/python src/judge.py watch >> logs/judge_watch_keeper.out 2>&1 &
      JPID=$!
      echo "$(date -u) restarted judge PID $JPID" >> logs/judge_keeper.log
    fi
  fi
  sleep 60
done
