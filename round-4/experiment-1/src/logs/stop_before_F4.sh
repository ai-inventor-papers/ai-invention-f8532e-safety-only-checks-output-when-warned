#!/bin/bash
# A13: F4 (Qwen3-1.7B, optional) is NOT run -- time budget; the sweep stops once the LATE int8bnb arms are finished.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
cd "$WS" || exit 1
until grep -q "DONE F3__int8bnb\|FAILED F3__int8bnb" logs/gen_s4.out; do sleep 20; done
touch results/gen_stop.flag
echo "$(date -u) stop flag set after F3__int8bnb: F4 (optional) NOT_RUN" >> logs/stages.log
