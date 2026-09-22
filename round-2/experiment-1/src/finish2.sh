#!/usr/bin/env bash
# SESSION-2 closing sequence: score, test determinism, freeze + confirm, emit, audit, validate.
# Run AFTER the prompt sweep, the C-harvest pass and the weight summaries have finished.
# Every stage is independently re-runnable; analyze caches per-checkpoint scores.
set -uo pipefail
cd "$(dirname "$0")"
ANALYZE_MIN="${1:-90}"
PY=.venv/bin/python
run () { local name="$1"; shift; echo; echo "== $name  ($(date +%H:%M:%S)) =="
  OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false \
  PYTHONUNBUFFERED=1 "$PY" -u "$@"; }

echo "== state: harvested $(ls harvest/*/DONE 2>/dev/null | wc -l), w-summarised $(ls harvest/*/W_DONE 2>/dev/null | wc -l), c-harvested $(ls harvest/*/C_DONE 2>/dev/null | wc -l) =="

run "session-2 deviations" src/session2_deviations.py 2>&1 | tail -2
run "analyze"  src/analyze.py --deadline-min "$ANALYZE_MIN" --budget-resamples 10 2>&1 | grep -v "Loading" | tail -30
run "T7 determinism" src/t7_determinism.py --tag Qwen--Qwen3-0.6B --n-null 5 --n-boot 20 2>&1 | tail -3
run "confirm"  src/confirm.py --deadline-min 20 2>&1 | tail -6
run "leak"     src/leak_audit.py 2>&1 | tail -8
run "outputs"  src/make_outputs.py 2>&1 | tail -4

echo; echo "== root copies of the deliverable (the verifier reads the workspace root) =="
cp out/method_out.json method_out.json

SKILL_DIR=/ai-inventor/.claude/skills/aii-json
SPY="$SKILL_DIR/../.ability_client_venv/bin/python"
echo; echo "== schema validation =="
"$SPY" "$SKILL_DIR/scripts/aii_json_validate_schema.py" --format exp_gen_sol_out \
  --file "$PWD/method_out.json" 2>&1 | grep -E "PASSED|FAILED|Error|Path" | head -20
echo; echo "== full / mini / preview =="
"$SPY" "$SKILL_DIR/scripts/aii_json_format_mini_preview.py" --input "$PWD/method_out.json" 2>&1 | tail -4
cp full_method_out.json mini_method_out.json preview_method_out.json out/ 2>/dev/null
echo; echo "== sizes =="; ls -la *method_out.json out/*.json | awk '{print $5, $9}'
echo "done at $(date +%H:%M:%S)"
