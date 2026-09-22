#!/usr/bin/env bash
# Validate the deliverable: schema compliance, file sizes, mini/preview variants.
set -uo pipefail
cd "$(dirname "$0")/.."
SKILL_DIR="/ai-inventor/.claude/skills/aii-json"
PY="/ai-inventor/.claude/skills/.ability_client_venv/bin/python"

echo "== sizes =="
ls -lh out/method_out.json out/SUMMARY.md 2>/dev/null
du -sh out/released 2>/dev/null
find out -type f -size +45M 2>/dev/null | sed 's/^/OVERSIZED: /'

echo "== schema =="
"$PY" "$SKILL_DIR/scripts/aii_json_validate_schema.py" --format exp_gen_sol_out \
  --file "$PWD/out/method_out.json"
