#!/usr/bin/env bash
# SESSION-2 TIME GATE (registered drop order, Section 12 / fallback 16): stop the prompt sweep
# once the E3 family singles (TinyLlama, OLMo-2 x2) are harvested, dropping the Base
# plain-format re-run and the four extra base singles; then run the C-harvest on the checkpoints
# the registered tests need (E2 arms, every pair member, the random-init arm), one process.
cd "$(dirname "$0")"
SUP=8575
echo "[t] $(date +%T) waiting for allenai--OLMo-2-0425-1B/DONE"
until [ -f harvest/allenai--OLMo-2-0425-1B/DONE ]; do
  kill -0 "$(cat logs/sweep.pid 2>/dev/null)" 2>/dev/null || kill -0 "$SUP" 2>/dev/null || break
  sleep 15
done
kill "$SUP" 2>/dev/null && echo "[t] $(date +%T) supervisor $SUP stopped"
SW=$(cat logs/sweep.pid 2>/dev/null)
kill "$SW" 2>/dev/null && echo "[t] $(date +%T) sweep $SW stopped (tail dropped by the time gate)"
sleep 5
TAGS=""
for t in Qwen--Qwen3-4B mlabonne--Qwen3-4B-abliterated Qwen--Qwen3-4B-Base Qwen--Qwen3-4B-SafeRL \
  CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 Qwen--Qwen3-0.6B huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2 \
  Qwen--Qwen3-1.7B huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2 ibm-granite--granite-3.2-2b-instruct \
  Damien420--granite-3.2-2b-instruct-abliterated HuggingFaceTB--SmolLM3-3B mlx-community--SmolLM3-3B-abliterated-bf16 \
  microsoft--Phi-4-mini-instruct lunahr--Phi-4-mini-instruct-abliterated Qwen--Qwen2.5-1.5B-Instruct \
  Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3 RandInit-Qwen3-0.6B; do
  [ -f "harvest/$t/DONE" ] && TAGS="$TAGS $t"
done
echo "[t] $(date +%T) C-sweep over:$TAGS"
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1 \
  .venv/bin/python -u src/c_harvest2.py --tags $TAGS --deadline-min 85 \
  --keep-cont-tokens 56 --cells all >> logs/c_sweep_main.log 2>&1
echo "[t] $(date +%T) C-sweep ended rc=$?"
