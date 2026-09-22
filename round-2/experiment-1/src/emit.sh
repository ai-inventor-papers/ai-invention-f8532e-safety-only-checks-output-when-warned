#!/usr/bin/env bash
# Re-emit the deliverable from the final results/ (no scoring): outputs -> root copy -> schema -> full/mini/preview.
set -uo pipefail
cd "$(dirname "$0")"
OMP_NUM_THREADS=2 PYTHONUNBUFFERED=1 .venv/bin/python -u src/make_outputs.py 2>&1 | grep -E "wrote|ERROR|Traceback" | tail -3
cp out/method_out.json method_out.json
SKILL_DIR=/ai-inventor/.claude/skills/aii-json
SPY="$SKILL_DIR/../.ability_client_venv/bin/python"
"$SPY" "$SKILL_DIR/scripts/aii_json_validate_schema.py" --format exp_gen_sol_out --file "$PWD/method_out.json" 2>&1 | grep -E "PASSED|FAILED|Error|Path" | head -10
"$SPY" "$SKILL_DIR/scripts/aii_json_format_mini_preview.py" --input "$PWD/method_out.json" 2>&1 | tail -3
cp full_method_out.json mini_method_out.json preview_method_out.json out/
ls -la *method_out.json | awk '{print $5, $9}'
