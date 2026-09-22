#!/usr/bin/env bash
# Keep generation running until the first 20 panel tags all have GEN_DONE (or the deadline).
# A gen process fixes its tag list at launch, so any tag that becomes pending later (e.g. one
# discarded for a data-integrity fault) needs a fresh launch; this supplies it.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
export TORCH_DISABLE_NATIVE_JIT=1 PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True OMP_NUM_THREADS=4 \
       OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1
DEADLINE="2026-09-22T04:20:00Z"
while :; do
  N=$(ls private/gens/HG__*.GEN_DONE 2>/dev/null | wc -l)
  [ "$N" -ge 20 ] && { echo "$(date -u +%T) supervisor: 20/20 generated" >> logs/gen_sweep.log; break; }
  [[ "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$DEADLINE" ]] && { echo "$(date -u +%T) supervisor: deadline" >> logs/gen_sweep.log; break; }
  P=$(cat logs/gen_sweep.pid 2>/dev/null || echo 0)
  if ! kill -0 "$P" 2>/dev/null; then
    echo "$(date -u +%T) supervisor: relaunching gen (have $N/20)" >> logs/gen_sweep.log
    nohup ./.venv_gpu/bin/python src/pipeline.py gen --from-sweep 20 --batch 48 \
          --max-new-harm 140 --max-new-benign 96 >> logs/gen_sweep.log 2>&1 &
    echo $! > logs/gen_sweep.pid
  fi
  sleep 30
done
