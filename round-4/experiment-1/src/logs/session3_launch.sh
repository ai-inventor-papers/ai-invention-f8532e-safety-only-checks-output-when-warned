#!/bin/bash
# Session 3 (pod restarted ~17:37 UTC): relaunch the prereg'd generation sweep (chunk-resumable now) and the judge
# watcher, fully detached (setsid) so they survive the agent session; WS .venv only.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
cd "$WS" || exit 1
PY="$WS/.venv/bin/python"
rm -f results/gen_sweep_finished.flag
GEN_THREADS=2 setsid nohup "$PY" src/gen_variants.py >> logs/gen_sweep5.out 2>&1 < /dev/null &
echo $! > logs/gen_sweep5.pid
sleep 2
setsid nohup "$PY" src/judge.py watch >> logs/judge_watch5.out 2>&1 < /dev/null &
echo $! > logs/judge_watch5.pid
echo "$(date -u) session3 launched gen=$(cat logs/gen_sweep5.pid) judge=$(cat logs/judge_watch5.pid)" >> logs/stages.log
