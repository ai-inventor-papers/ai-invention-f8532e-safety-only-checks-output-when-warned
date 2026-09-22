#!/bin/bash
# Staged order chain (prereg amendment A11), session-2 runner (uses the WS .venv; session 1's scratchpad venv is gone).
# usage: logs/stage_runner.sh <stage> <tag> [<tag> ...]
#   1. waits until every listed arm is judged (resave arms: until their by-construction gens file exists);
#      an arm whose generation FAILED (gen_timings.json 'failed') or that is still missing after MAX_WAIT_S is dropped
#      from the stage and logged (never imputed);
#   2. commits graded_truth_s<stage>.json -> classification_s<stage>.json (src/truth_classify.py both);
#   3. harvests the arms of the stage (src/harvest_variants.py re-verifies the chain and the per-arm gate itself).
set -u
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
cd "$WS" || exit 1
PY="$WS/.venv/bin/python"
S=$1; shift
MAX_WAIT_S=${MAX_WAIT_S:-7200}
t0=$(date +%s)
KEEP=""
for t in "$@"; do
  while true; do
    if [[ "$t" == *__resave ]]; then f="private/gens/$t.jsonl"; else f="private/judged/$t.jsonl"; fi
    if [ -f "$f" ]; then KEEP="$KEEP $t"; break; fi
    failed=$("$PY" -c "import json,sys;d=json.load(open('results/gen_timings.json'));print(1 if 'failed' in d.get('$t',{}) else 0)" 2>/dev/null || echo 0)
    if [ "$failed" = "1" ]; then echo "$(date -u) stage $S: $t generation FAILED -> dropped" >> logs/stages.log; break; fi
    if [ $(( $(date +%s) - t0 )) -gt "$MAX_WAIT_S" ]; then echo "$(date -u) stage $S: $t not ready after ${MAX_WAIT_S}s -> dropped" >> logs/stages.log; break; fi
    sleep 20
  done
done
if [ -z "$KEEP" ]; then echo "$(date -u) stage $S: nothing to commit" >> logs/stages.log; exit 1; fi
echo "$(date -u) stage $S truth/classify:$KEEP" >> logs/stages.log
"$PY" src/truth_classify.py both --stage "$S" --tags $KEEP >> "logs/stage_$S.out" 2>&1 || { echo "$(date -u) stage $S truth/classify FAILED (see logs/stage_$S.out)" >> logs/stages.log; exit 1; }
echo "$(date -u) stage $S harvest:$KEEP" >> logs/stages.log
GEN_THREADS=${HARV_THREADS:-1} "$PY" src/harvest_variants.py --tags $KEEP >> "logs/harvest_s$S.out" 2>&1
echo "$(date -u) stage $S harvest exit $?" >> logs/stages.log
