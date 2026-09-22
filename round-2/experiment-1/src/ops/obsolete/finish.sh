#!/usr/bin/env bash
# Closing sequence: stop the harvest, then score, freeze, confirm and emit.
# Every stage is deadline-gated and independently re-runnable.
set -uo pipefail
cd "$(dirname "$0")"
ANALYZE_MIN="${1:-45}"

echo "== stopping the harvest and its supervisor =="
for f in supervise sweep wsum weightfp; do
  P=$(cat "logs/$f.pid" 2>/dev/null) || true
  [ -n "${P:-}" ] && kill "$P" 2>/dev/null && echo "  stopped $f (pid $P)"
done
sleep 5

echo "== harvested: $(ls harvest/*/DONE 2>/dev/null | wc -l)  w-summarised: $(ls harvest/*/W_DONE 2>/dev/null | wc -l) =="

run () { echo; echo "== $1 =="; shift; OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1 .venv/bin/python -u "$@"; }

run "analyze"  src/analyze.py  --deadline-min "$ANALYZE_MIN"  2>&1 | tail -25
run "confirm"  src/confirm.py  --deadline-min 12               2>&1 | tail -10
run "outputs"  src/make_outputs.py                             2>&1 | tail -6
run "leak"     src/leak_audit.py                               2>&1 | tail -8

echo
echo "== schema validation =="
SKILL_DIR=/ai-inventor/.claude/skills/aii-json
"$SKILL_DIR/../.ability_client_venv/bin/python" \
  "$SKILL_DIR/scripts/aii_json_validate_schema.py" \
  --format exp_gen_sol_out --file "$PWD/out/method_out.json" 2>&1 | grep -E "PASSED|FAILED|Error|Path"

echo
echo "== mini / preview =="
"$SKILL_DIR/../.ability_client_venv/bin/python" \
  "$SKILL_DIR/scripts/aii_json_format_mini_preview.py" --input "$PWD/out/method_out.json" 2>&1 | tail -4

echo
echo "== sizes =="
ls -la out/*.json | awk '{print $5, $9}'
echo "done at $(date +%H:%M:%S)"
