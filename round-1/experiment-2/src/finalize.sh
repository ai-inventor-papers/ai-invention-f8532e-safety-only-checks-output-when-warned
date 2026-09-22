#!/bin/bash
# analyze -> emit -> assemble -> aii-json format + validate -> size check
set -u
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_2
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8 PYTHONUNBUFFERED=1
TAGS="${1:-}"
if [ -z "$TAGS" ]; then
  TAGS=$(ls out/harvest/*_meta.json 2>/dev/null | sed 's|.*/||; s|_meta.json||' | paste -sd,)
fi
echo "### analysing tags: $TAGS"
.venv/bin/python -u src/analyze.py --lineages "$TAGS" 2>&1 | tail -60 || exit 1
echo "### shard any oversized harvest npz (100MB deployment limit)"
.venv/bin/python -u src/shard_harvest.py 2>&1 | tail -25 || exit 1
echo "### redundancy"
.venv/bin/python -u src/redundancy.py 2>&1 | tail -40 || exit 1
echo "### emit"
.venv/bin/python -u src/emit.py || exit 1
echo "### assemble"
.venv/bin/python -u src/assemble.py || exit 1
echo "### aii-json format (full / mini / preview)"
SKILL_DIR=/ai-inventor/.claude/skills/aii-json
$SKILL_DIR/../.ability_client_venv/bin/python \
  $SKILL_DIR/scripts/aii_json_format_mini_preview.py --input method_out.json || exit 1
echo "### aii-json validate"
for F in method_out.json full_method_out.json mini_method_out.json preview_method_out.json; do
  $SKILL_DIR/../.ability_client_venv/bin/python \
    $SKILL_DIR/scripts/aii_json_validate_schema.py --format exp_gen_sol_out --file "$F"
done
echo "### TODO 2: file size check, 100MB limit (aii-file-size-limit procedure)"
ls -lh method_out.json full_method_out.json
for F in method_out.json full_method_out.json; do
  B=$(stat -c%s "$F"); MB=$((B/1000000))
  if [ "$B" -gt 100000000 ]; then echo "  $F = ${MB}MB  EXCEEDS 100MB -> MUST SPLIT"; else echo "  $F = ${MB}MB  OK (<100MB, no split needed)"; fi
done
echo "### TODO 1 verification: the three variants exist"
ls -lh full_method_out.json mini_method_out.json preview_method_out.json
echo "### struct out"
.venv/bin/python -u src/structout.py || exit 1
echo "### all deliverables"
ls -lh method.py pyproject.toml results.json method_out.json full_method_out.json \
       mini_method_out.json preview_method_out.json .terminal_claude_agent_struct_out.json 2>&1
echo "### FINAL SWEEP: any file over 100MB anywhere in the workspace (excluding .venv)"
BIG=$(find . -path ./.venv -prune -o -type f -size +100M -print 2>/dev/null)
if [ -n "$BIG" ]; then
  echo "STILL OVERSIZED:"; echo "$BIG" | while read -r f; do echo "  $(du -h "$f" | cut -f1) $f"; done
  exit 1
else
  echo "  none - every file is under 100MB"
fi
echo "### DONE"
