#!/usr/bin/env bash
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
OLD=$(cat logs/gen_sweep.pid)
until grep -q "GEN DONE HG__EleutherAI--pythia-410m" logs/gen_sweep.log || ! kill -0 "$OLD" 2>/dev/null; do sleep 2; done
sleep 1
kill "$OLD" 2>/dev/null
echo "$(date -u +%T) restart at tag boundary (guard: buckets accepted when padded fails)" >> logs/gen_sweep.log
export TORCH_DISABLE_NATIVE_JIT=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True OMP_NUM_THREADS=4 \
       OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1
nohup ./.venv_gpu/bin/python src/pipeline.py gen --from-sweep 28 --batch 16 --max-new-harm 140 \
      --max-new-benign 96 >> logs/gen_sweep.log 2>&1 &
echo $! > logs/gen_sweep.pid
echo "$(date -u +%T) new gen pid $(cat logs/gen_sweep.pid)" >> logs/gen_sweep.log
