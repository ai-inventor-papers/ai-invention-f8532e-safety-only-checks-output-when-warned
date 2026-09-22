#!/usr/bin/env bash
# Final window (plan: D11 hard-scheduled at the end, regardless of upstream progress).
# Re-runs the backstop join against the parallel iteration-5 artifacts, then the
# ledger, the self-check gate, eval_out.json and the write-up, and re-validates.
# Usage: bash finalize.sh [HH:MM UTC to wait for; omit to run now]
set -uo pipefail
cd "$(dirname "$0")"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
if [ -n "${1:-}" ]; then
  target=$(date -u -d "$1" +%s); now=$(date -u +%s)
  [ "$target" -gt "$now" ] && sleep $(( target - now ))
fi
PY=.venv/bin/python
echo "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)  FINAL_WINDOW_START" >> build_log.txt
for s in d11_join adjudicate_ledger assemble build_eval_out key_findings write_summary assemble build_eval_out write_summary; do
  $PY src/$s.py > logs/finalize_$s.log 2>&1; echo "$s exit $?"
done
SK=/ai-inventor/.claude/skills/aii-json
$SK/../.ability_client_venv/bin/python $SK/scripts/aii_json_format_mini_preview.py --input eval_out.json > logs/finalize_format.log 2>&1
for f in eval_out.json full_eval_out.json mini_eval_out.json preview_eval_out.json; do
  echo "$f: $($SK/../.ability_client_venv/bin/python $SK/scripts/aii_json_validate_schema.py --format exp_eval_sol_out --file $f 2>&1 | grep -oE 'PASSED|FAILED')"
done
$PY src/write_struct_out.py
echo "$(date -u +%Y-%m-%dT%H:%M:%S+00:00)  FINAL_WINDOW_END" >> build_log.txt
