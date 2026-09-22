#!/bin/bash
# stop the first sweep (PID 14883) once F1__sysprompt exists (stage-1 arms done); stage-1 truth/classification and the
# F1 harvest are then started by hand, and later generation arms are launched explicitly (memory: <=2 model processes)
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
until [ -f private/gens/F1__sysprompt.jsonl ]; do sleep 15; done
touch results/gen_stop.flag
while kill -0 14883 2>/dev/null; do sleep 3; done
rm -f results/gen_stop.flag
echo "$(date -u) sweep1 stopped after F1__sysprompt" >> logs/stop_after_F1sys.log
