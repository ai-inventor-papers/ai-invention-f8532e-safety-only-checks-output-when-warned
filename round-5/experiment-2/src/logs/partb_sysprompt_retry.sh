#!/usr/bin/env bash
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
export TORCH_DISABLE_NATIVE_JIT=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True OMP_NUM_THREADS=4 \
       OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1
P=$(cat logs/partb_run.pid)
while kill -0 "$P" 2>/dev/null; do sleep 15; done
echo "$(date -u +%T) retrying sysprompt after the _dl fix" >> logs/partb_run.log
./.venv_gpu/bin/python src/partb.py run --arms sysprompt >> logs/partb_run.log 2>&1
./.venv_gpu/bin/python src/partb.py classify >> logs/partb_classify.log 2>&1
echo "$(date -u +%T) sysprompt retry + classify rc=$?" >> logs/partb_run.log
