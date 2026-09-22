#!/bin/bash
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1
until grep -q "killed" logs/kill_after_m1.out 2>/dev/null || ! ps -p 21818 > /dev/null; do sleep 3; done
echo done
