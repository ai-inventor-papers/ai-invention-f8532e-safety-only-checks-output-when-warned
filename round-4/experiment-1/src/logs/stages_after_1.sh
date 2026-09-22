#!/bin/bash
# Stages 2..7 of the staged order chain (amendment A11/A10 arm order), run strictly one after another so that at most
# ONE harvest process (1 thread) runs beside the generation sweep. Launched only after stage 1 committed and harvested.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
cd "$WS" || exit 1
R=logs/stage_runner.sh
$R 2 F2__ref F2__a10 F2__int8wo F2__sysprompt F2__wu05
$R 3 F3__ref F3__a10 F3__int8wo F3__sysprompt F3__wu05
$R 4 F1__resave F1__wu05 F1__cautious F2__resave F3__resave
$R 5 F1__lora F1__wu20 F2__cautious F1__a05
$R 6 F2__wu20 F3__cautious F3__wu20 F2__a05 F3__a05
MAX_WAIT_S=${EXTRA_WAIT_S:-5400} $R 7 F1__fp32 F1__attn_eager F2__attn_eager F3__attn_eager
echo "$(date -u) stages 2-7 finished" >> logs/stages.log
