#!/usr/bin/env bash
# Run the teacher-forced C-harvest (X5, X11) as ONE sequential process AFTER the prompt sweep
# has finished, so two resident models never share the 16 GB cgroup. Order = the tests that
# need it most: the commissioned Qwen3-4B arm (E2), then stratum-A pairs, the null-edit
# control, the other pairs, the anomalous controls, the random-init arm, then the E3 singles.
cd "$(dirname "$0")"
DEADLINE_MIN="${1:-80}"
echo "[c] $(date +%T) waiting for the prompt sweep supervisor to finish"
# PID-based wait (never by name): the judge-then-resume wrapper runs the sweep supervisor in
# its foreground, so it exits exactly when the supervised prompt sweep is over.
JR=$(cat logs/judge_resume.pid 2>/dev/null)
while [ -n "$JR" ] && kill -0 "$JR" 2>/dev/null; do sleep 20; done
while kill -0 "$(cat logs/sweep.pid 2>/dev/null)" 2>/dev/null; do sleep 20; done
echo "[c] $(date +%T) prompt sweep finished; starting C-sweep"
ORDER="Qwen--Qwen3-4B mlabonne--Qwen3-4B-abliterated Qwen--Qwen3-4B-Base Qwen--Qwen3-4B-SafeRL \
CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 \
Qwen--Qwen3-0.6B huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2 \
Qwen--Qwen3-1.7B huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2 \
HuggingFaceTB--SmolLM3-3B mlx-community--SmolLM3-3B-abliterated-bf16 \
ibm-granite--granite-3.2-2b-instruct Damien420--granite-3.2-2b-instruct-abliterated \
microsoft--Phi-4-mini-instruct lunahr--Phi-4-mini-instruct-abliterated \
Qwen--Qwen2.5-1.5B-Instruct Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3 \
stabilityai--stablelm-2-1_6b-chat hereticness--heretic_stablelm-2-1_6b-chat \
HuggingFaceTB--SmolLM2-1.7B-Instruct venkycs--SmolLM2-1.7B-Instruct-Abliterated \
RandInit-Qwen3-0.6B TinyLlama--TinyLlama-1.1B-Chat-v1.0 allenai--OLMo-2-0425-1B-Instruct \
allenai--OLMo-2-0425-1B Qwen--Qwen3-0.6B-Base Qwen--Qwen3-1.7B-Base Qwen--Qwen2.5-1.5B \
HuggingFaceTB--SmolLM2-1.7B"
TAGS=""
for t in $ORDER; do [ -f "harvest/$t/DONE" ] && TAGS="$TAGS $t"; done
echo "[c] tags with a prompt harvest: $TAGS"
OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false PYTHONUNBUFFERED=1 \
  .venv/bin/python -u src/c_harvest2.py --tags $TAGS --deadline-min "$DEADLINE_MIN" \
  --keep-cont-tokens 56 --cells all >> logs/c_sweep_main.log 2>&1
echo "[c] $(date +%T) C-sweep ended rc=$?"
