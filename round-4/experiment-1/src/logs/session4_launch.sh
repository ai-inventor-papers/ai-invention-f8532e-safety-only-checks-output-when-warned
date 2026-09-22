#!/bin/bash
# Session 4 (A13): idempotent (re)launcher -- safe to run after a pod restart; each component resumes from files.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
cd "$WS" || exit 1
if nvidia-smi >/dev/null 2>&1 && [ -x .venv_gpu/bin/python ]; then PYG="$WS/.venv_gpu/bin/python"; else PYG="$WS/.venv/bin/python"; fi
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4   # cgroup quota ~5 CPUs but 48 visible: BLAS must not spawn 48 threads
alive () { [ -f "$1" ] && kill -0 "$(cat $1)" 2>/dev/null; }
rm -f results/gen_sweep_finished.flag
if ! alive logs/gen_s4.pid; then
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True GEN_THREADS=4 VRAM_CAP_GB=${VRAM_CAP_GB:-7} setsid nohup "$PYG" src/gen_variants.py >> logs/gen_s4.out 2>&1 < /dev/null &
  echo $! > logs/gen_s4.pid
fi
if ! alive logs/judge_s4.pid; then
  setsid nohup "$WS/.venv/bin/python" src/judge.py watch >> logs/judge_s4.out 2>&1 < /dev/null &
  echo $! > logs/judge_s4.pid
fi
if false && ! alive logs/commit_s4.pid; then   # all 6 stages committed; stage 7 (F4) NOT_RUN
  setsid nohup bash logs/commit_s4.sh >> logs/commit_s4.out 2>&1 < /dev/null &
  echo $! > logs/commit_s4.pid
fi
if ! alive logs/harvest_s4.pid; then
  PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True GEN_THREADS=4 VRAM_CAP_GB=${HARV_VRAM_CAP_GB:-6} setsid nohup "$PYG" src/harvest_variants.py --watch >> logs/harvest_s4.out 2>&1 < /dev/null &
  echo $! > logs/harvest_s4.pid
fi
if ! alive logs/score_s4.pid; then
  SCORE_THREADS=${SCORE_THREADS:-3} setsid nohup nice -n 10 "$WS/.venv/bin/python" src/score_watch.py >> logs/score_s4.out 2>&1 < /dev/null &
  echo $! > logs/score_s4.pid
fi
if [ ! -f results/gen_stop.flag ] && ! alive logs/stop_before_F4.pid; then
  setsid nohup bash logs/stop_before_F4.sh > /dev/null 2>&1 < /dev/null &
  echo $! > logs/stop_before_F4.pid
fi
echo "$(date -u) session4 launch: gen=$(cat logs/gen_s4.pid) judge=$(cat logs/judge_s4.pid) commit=$(cat logs/commit_s4.pid) harvest=$(cat logs/harvest_s4.pid) score=$(cat logs/score_s4.pid) py=$PYG" >> logs/stages.log
tail -1 logs/stages.log
