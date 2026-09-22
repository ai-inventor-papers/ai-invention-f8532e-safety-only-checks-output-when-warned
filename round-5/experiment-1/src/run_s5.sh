#!/usr/bin/env bash
# S5: the one-shot join with the blind held-out substrate. Runs ONLY after the freeze.
# usage: bash run_s5.sh [tierb_deadline_HH:MM]
set -uo pipefail
cd "$(dirname "$0")"
PY=.venv_gpu/bin/python
DEADLINE="${1:-05:25}"
export OMP_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false TORCH_DISABLE_NATIVE_JIT=1 \
       PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
test -f results/survivor.sha256 || { echo "REFUSED: no results/survivor.sha256 (freeze first)"; exit 1; }
echo "=== S5.1 discover the substrate manifest and build the confirmation queue"
$PY src/s5_prepare.py 2>&1 | tail -40
echo "=== S5.2 Tier-B registered battery per landed checkpoint (deadline $DEADLINE UTC)"
$PY src/s5_run_tierb.py --deadline-utc "$DEADLINE" 2>&1 | tail -40
echo "=== S5.3 join + selection rule"
$PY src/join.py --results-dir results --logs-dir logs 2>&1 | tail -30
echo "=== S5.4 pair audit (false alarms / sensitivity / text bars / controls)"
$PY src/pair_audit.py --results-dir results 2>&1 | tail -20
echo "=== done"
