#!/usr/bin/env bash
# Post-run finalisation: schema validation, mini/preview variants, size check.
set -euo pipefail
cd "$(dirname "$0")"
SKILL_DIR="/ai-inventor/.claude/skills/aii-json"
PY="$SKILL_DIR/../.ability_client_venv/bin/python"

echo "== schema validation =="
"$PY" "$SKILL_DIR/scripts/aii_json_validate_schema.py" \
  --format exp_eval_sol_out --file "$PWD/eval_out.json"

echo "== mini / preview variants =="
"$PY" "$SKILL_DIR/scripts/aii_json_format_mini_preview.py" --input "$PWD/eval_out.json"

echo "== size check (limit 100MB per file) =="
find . -path ./.venv -prune -o -type f -size +90M -print | sed 's/^/  OVERSIZED: /'
ls -lh eval_out.json full_eval_out.json mini_eval_out.json preview_eval_out.json 2>/dev/null || true
du -sh results
