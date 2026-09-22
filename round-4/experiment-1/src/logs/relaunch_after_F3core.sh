#!/bin/bash
# A7: once F3__sysprompt exists, stop the A2-order sweep (PID 14883) before F3__wu05 and relaunch with the A7 order;
# the old sweep writes gen_sweep_finished.flag on exit, so the flag is removed and the judge watcher restarted if it quit.
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
until [ -f private/gens/F3__sysprompt.jsonl ]; do sleep 20; done
touch results/gen_stop.flag
while kill -0 14883 2>/dev/null; do sleep 5; done
rm -f results/gen_stop.flag results/gen_sweep_finished.flag
nohup /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-4-gen-art-gen-art-experiment-1/3c45c2e0-6b4c-4b03-ad27-13fd166c1366/scratchpad/venv/bin/python src/gen_variants.py >> logs/gen_sweep2.out 2>&1 &
echo "sweep2 PID $!" > logs/sweep2.pid
sleep 60
if ! kill -0 14881 2>/dev/null; then
  nohup /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-4-gen-art-gen-art-experiment-1/3c45c2e0-6b4c-4b03-ad27-13fd166c1366/scratchpad/venv/bin/python src/judge.py watch >> logs/judge_watch2.out 2>&1 &
  echo "judge2 PID $!" > logs/judge2.pid
fi
