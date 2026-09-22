#!/bin/bash
# waits for the F1 reference run (PID 13527), then runs the full prereg'd generation sweep in one long-lived process
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
while kill -0 13527 2>/dev/null; do sleep 5; done
exec /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-4-gen-art-gen-art-experiment-1/3c45c2e0-6b4c-4b03-ad27-13fd166c1366/scratchpad/venv/bin/python src/gen_variants.py >> logs/gen_sweep.out 2>&1
