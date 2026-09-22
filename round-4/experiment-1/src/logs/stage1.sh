#!/bin/bash
# STAGE 1 (amendment A11): when the four F1 core arms are generated AND judged, commit stage-1 truth + classification
# (this also commits the reused truth of the harvested checkpoints), then harvest those four arms.
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
for t in F1__ref F1__int8wo F1__a10 F1__sysprompt; do
  until [ -f private/judged/$t.jsonl ]; do sleep 20; done
done
while kill -0 14883 2>/dev/null; do sleep 5; done       # sweep 1 must have exited (memory)
echo "$(date -u) stage-1 truth/classify" >> logs/stage1.log
/tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-4-gen-art-gen-art-experiment-1/3c45c2e0-6b4c-4b03-ad27-13fd166c1366/scratchpad/venv/bin/python src/truth_classify.py both --stage 1 --tags F1__ref F1__int8wo F1__a10 F1__sysprompt >> logs/stage1.log 2>&1 || exit 1
echo "$(date -u) stage-1 harvest" >> logs/stage1.log
/tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-4-gen-art-gen-art-experiment-1/3c45c2e0-6b4c-4b03-ad27-13fd166c1366/scratchpad/venv/bin/python src/harvest_variants.py --tags F1__ref F1__a10 F1__int8wo F1__sysprompt >> logs/harvest_s1.out 2>&1
echo "$(date -u) stage-1 harvest exit $?" >> logs/stage1.log
