#!/bin/bash
# Session 4 (A13, GPU box): staged truth -> classification commits, strictly in order; each stage waits until its arms
# are judged (resave: until its by-construction gens file exists); failed / never-ready arms are dropped and logged.
# Harvesting is done by the separate harvest watcher (src/harvest_variants.py --watch), which only ever sees arms
# covered by a committed classification (per-arm gate).
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
cd "$WS" || exit 1
PY="$WS/.venv/bin/python"
commit_stage () {
  S=$1; shift
  if [ -f "results/classification_s$S.json" ]; then return 0; fi
  MAX_WAIT_S=${MAX_WAIT_S:-5400}
  t0=$(date +%s); KEEP=""
  for t in "$@"; do
    while true; do
      if [[ "$t" == *__resave ]]; then f="private/gens/$t.jsonl"; else f="private/judged/$t.jsonl"; fi
      if [ -f "$f" ]; then KEEP="$KEEP $t"; break; fi
      failed=$("$PY" -c "import json;d=json.load(open('results/gen_timings.json'));print(1 if 'failed' in d.get('$t',{}) else 0)" 2>/dev/null || echo 0)
      if [ "$failed" = "1" ]; then echo "$(date -u) stage $S: $t generation FAILED -> dropped" >> logs/stages.log; break; fi
      if [ $(( $(date +%s) - t0 )) -gt "$MAX_WAIT_S" ]; then echo "$(date -u) stage $S: $t not ready after ${MAX_WAIT_S}s -> dropped" >> logs/stages.log; break; fi
      sleep 15
    done
  done
  if [ -z "$KEEP" ]; then echo "$(date -u) stage $S: nothing to commit" >> logs/stages.log; return 1; fi
  if [ -f "results/graded_truth_s$S.json" ]; then
    echo "$(date -u) stage $S classify (truth already committed)" >> logs/stages.log
    "$PY" src/truth_classify.py classify --stage "$S" >> "logs/stage_$S.out" 2>&1
  else
    echo "$(date -u) stage $S truth/classify:$KEEP" >> logs/stages.log
    "$PY" src/truth_classify.py both --stage "$S" --tags $KEEP >> "logs/stage_$S.out" 2>&1
  fi
  echo "$(date -u) stage $S exit $?" >> logs/stages.log
}
C="a10 int8wo sysprompt fp16 wu05 lora"
commit_stage 1 F1__ref $(for v in $C; do echo F1__$v; done) F1__resave
commit_stage 2 F2__ref $(for v in $C; do echo F2__$v; done) F2__resave
commit_stage 3 F3__ref $(for v in $C; do echo F3__$v; done) F3__resave
E="cautious wu20 a05 dpo"
commit_stage 4 $(for v in $E; do for f in F1 F2 F3; do echo ${f}__$v; done; done)
commit_stage 5 HG__huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2 HG__mylesgoose--Llama-3.2-1B-Instruct-abliterated2 \
  HG__Qwen--Qwen3-1.7B HG__huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2 HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct \
  HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct-abliterated HG__amd--AMD-OLMo-1B HG__amd--AMD-OLMo-1B-SFT \
  HG__amd--AMD-OLMo-1B-SFT-DPO HG__tiiuae--Falcon3-1B-Base HG__Qwen--Qwen2.5-1.5B-Instruct \
  HG__Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3
MAX_WAIT_S=3000 commit_stage 6 F1__int8bnb F2__int8bnb F3__int8bnb
commit_stage 7 F4__ref $(for v in $C; do echo F4__$v; done) F4__resave $(for v in $E; do echo F4__$v; done) F4__int8bnb
echo "$(date -u) commit_s4 all stages attempted" >> logs/stages.log
