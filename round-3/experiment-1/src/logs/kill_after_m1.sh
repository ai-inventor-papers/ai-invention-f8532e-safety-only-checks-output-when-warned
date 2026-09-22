#!/bin/bash
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1
until [ -f private/gens/Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct.jsonl ] && grep -q "Vikhr-Llama-3.2-1B-Instruct\"" results/gen_timings.json 2>/dev/null; do sleep 3; done
if ps -o args= -p 21818 | grep -q "src/gen.py"; then kill 21818; echo "killed 21818 at $(date -u +%H:%M:%S)"; fi
