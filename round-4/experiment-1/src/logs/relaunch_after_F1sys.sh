#!/bin/bash
# A7/A8/A10: once F1__sysprompt exists, stop the first sweep (PID 14883, old order + old F2/F3 repos in memory) before F2__ref
# and relaunch with the A7 order and the A8 parents; the old sweep writes gen_sweep_finished.flag on exit, so the flag is
# removed and the judge watcher restarted if it quit.
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
until [ -f private/gens/F1__sysprompt.jsonl ]; do sleep 15; done
touch results/gen_stop.flag
while kill -0 14883 2>/dev/null; do sleep 3; done
rm -f results/gen_stop.flag results/gen_sweep_finished.flag
nohup /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-4-gen-art-gen-art-experiment-1/3c45c2e0-6b4c-4b03-ad27-13fd166c1366/scratchpad/venv/bin/python src/gen_variants.py >> logs/gen_sweep2.out 2>&1 &
echo "sweep2 PID $!" > logs/sweep2.pid
sleep 45
if ! kill -0 14881 2>/dev/null; then
  nohup /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-4-gen-art-gen-art-experiment-1/3c45c2e0-6b4c-4b03-ad27-13fd166c1366/scratchpad/venv/bin/python src/judge.py watch >> logs/judge_watch2.out 2>&1 &
  echo "judge2 PID $!" > logs/judge2.pid
fi
