#!/usr/bin/env bash
# Wait for the first generation sweep to exit, then immediately launch the rest of
# the frozen sweep order so the GPU never sits idle between the two halves.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
export TORCH_DISABLE_NATIVE_JIT=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True OMP_NUM_THREADS=4 \
       OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1
FIRST=$(cat logs/gen_sweep.pid)
while kill -0 "$FIRST" 2>/dev/null; do sleep 10; done
echo "$(date -u +%T) first sweep (pid $FIRST) exited; launching --from-sweep 40" >> logs/gen_sweep.log
./.venv_gpu/bin/python src/pipeline.py gen --from-sweep 40 --batch 16 --max-new-harm 140 --max-new-benign 96 >> logs/gen_sweep.log 2>&1 &
echo $! > logs/gen_sweep.pid
echo "$(date -u +%T) second sweep pid $(cat logs/gen_sweep.pid)" >> logs/gen_sweep.log
wait
