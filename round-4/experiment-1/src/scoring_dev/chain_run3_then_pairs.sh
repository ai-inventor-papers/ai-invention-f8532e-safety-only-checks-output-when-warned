#!/bin/bash
set -x
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
while kill -0 7849 2>/dev/null; do sleep 5; done
echo "=== RUN3 (test_scoring.py) DONE ==="
python3 -c "import json; d=json.load(open('results/scoring_unit_checks.json')); print(json.dumps(d['summary'], indent=1))"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4
echo "=== LAUNCHING pairs.py on dev_pairs.json B=200 ==="
rm -rf scoring_dev/run1
.venv/bin/python src/pairs.py --pairs scoring_dev/dev_pairs.json --B 200 --n-null 50 --out scoring_dev/run1 --seed 42
echo "=== PAIRS RUN DONE rc=$? ==="
