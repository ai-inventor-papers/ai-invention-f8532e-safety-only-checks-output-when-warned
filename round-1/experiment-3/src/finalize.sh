#!/bin/bash
# Finalize LANE C: analyze -> assemble method_out.json -> validate -> mini/preview.
set -e
cd "$(dirname "$0")"
WS="$PWD"
echo "=== C6 analyze (S3 LOFO + controls + budget curve) ==="
.venv/bin/python lc_analyze.py 2>&1 | grep -aE "S3 target|strongest|VERDICT|acc=|machinery|complete" | tail -40
echo "=== C7 assemble method_out.json ==="
.venv/bin/python lc_output.py 2>&1 | grep -aE "written|footprint" | tail -5
echo "=== validate against exp_gen_sol_out ==="
SKILL=/ai-inventor/.claude/skills/aii-json
$SKILL/../.ability_client_venv/bin/python $SKILL/scripts/aii_json_validate_schema.py \
  --format exp_gen_sol_out --file "$WS/method_out.json" 2>&1 | tail -8
echo "=== mini/preview variants ==="
$SKILL/../.ability_client_venv/bin/python $SKILL/scripts/aii_json_format_mini_preview.py \
  --input method_out.json 2>&1 | tail -6
echo "=== sizes ==="
ls -lh method_out.json full_method_out.json mini_method_out.json preview_method_out.json 2>/dev/null
