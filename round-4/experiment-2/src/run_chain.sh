#!/usr/bin/env bash
# GPU queue after the main run. Each step is resumable: re-running skips finished cells
# (out/cells/<model>/<cell>__<hookhash>.*); the judge cache makes re-judging free.
#   1. genG (all-position ablation, T3 disambiguation control) on instruct + SafeRL
#   2. the third checkpoint (mlabonne/Qwen3-4B-abliterated): forward-only grids, judged site-P grid,
#      readouts, decode-window decodability, forward-only windows, site-E late readout (genG and genU skipped for GPU time)
#   3. F_perpU arm (genU) + site-E late readout (e2x2) on instruct + SafeRL
set -u
cd "$(dirname "$0")"
MAIN_PID=$(cat logs/main_gpu.pid)
while kill -0 "$MAIN_PID" 2>/dev/null; do sleep 10; done
echo "$(date -u +%H:%M:%S) main run ended" >> logs/chain.log
.venv_gpu/bin/python method.py --models instruct,saferl --stages genG \
  --deadline-min 60 --kv-gb 2.5 > logs/genG_gpu.out 2>&1
echo "$(date -u +%H:%M:%S) genG exit $?" >> logs/chain.log
.venv_gpu/bin/python method.py --models abliterated \
  --stages unit,twins,decod,arm0,grid1,genP,arc,grid2,grid3,stimro,decodgen,spanD,spanE,e2x2 \
  --deadline-min 90 --kv-gb 2.5 > logs/abliterated_gpu.out 2>&1
echo "$(date -u +%H:%M:%S) abliterated exit $?" >> logs/chain.log
.venv_gpu/bin/python method.py --models instruct,saferl --stages genU,e2x2 \
  --deadline-min 60 --kv-gb 2.5 > logs/genU_e2x2_gpu.out 2>&1
echo "$(date -u +%H:%M:%S) genU+e2x2 exit $?" >> logs/chain.log
