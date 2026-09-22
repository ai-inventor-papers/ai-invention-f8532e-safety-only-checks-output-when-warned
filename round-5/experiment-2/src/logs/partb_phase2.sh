#!/usr/bin/env bash
# Phase 2 for the in-house arms: wait for the gen/judge/commit phase to finish, then harvest
# every committed arm (pipeline.harvest_one refuses any ungated tag) and classify the set.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
export TORCH_DISABLE_NATIVE_JIT=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True OMP_NUM_THREADS=4 \
       OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1
P1=$(cat logs/partb_run.pid)
while kill -0 "$P1" 2>/dev/null; do sleep 10; done
echo "$(date -u +%T) phase 1 (gen/judge/commit) ended; starting harvest phase" >> logs/partb_run.log
./.venv_gpu/bin/python src/partb.py run --arms fp16 int8wo resave wu_nonref sysprompt a10 a05 lora dpo \
    >> logs/partb_run.log 2>&1
echo "$(date -u +%T) harvest phase rc=$?" >> logs/partb_run.log
./.venv_gpu/bin/python src/partb.py classify >> logs/partb_classify.log 2>&1
echo "$(date -u +%T) classify rc=$?" >> logs/partb_run.log
