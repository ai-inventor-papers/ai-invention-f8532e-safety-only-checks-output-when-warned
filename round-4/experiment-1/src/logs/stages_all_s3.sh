#!/bin/bash
# Session 3: stage 1 (F1 core) then stages 2-7 (logs/stages_after_1.sh), strictly sequential, detached.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
cd "$WS" || exit 1
if [ ! -f results/classification_s1.json ]; then
  logs/stage_runner.sh 1 F1__ref F1__int8wo F1__a10 F1__sysprompt
fi
bash logs/stages_after_1.sh
