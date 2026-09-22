#!/usr/bin/env bash
# After run_chain.sh: GSM8K collateral (16 items, 256 tokens, arms 0/F/R_F1/N6/R_N6-1).
# CAUSAL judged cell (Holm-18): instruct N6 @ P_B5 (over_refusal_hb). The other cells are the strongest nominal
# over-refusal cells in both models (P_B4, Dprime_B4, Dprime_B5), run as DESCRIPTIVE collateral.
set -u
cd "$(dirname "$0")"
CHAIN_PID=$(cat logs/chain.pid)
while kill -0 "$CHAIN_PID" 2>/dev/null; do sleep 10; done
echo "$(date -u +%H:%M:%S) chain1 ended; starting gsm" >> logs/chain.log
.venv_gpu/bin/python method.py --models instruct,saferl --stages gsm --gsm-cells P:B5,P:B4,Dprime:B4,Dprime:B5 \
  --deadline-min 40 --kv-gb 2.5 > logs/gsm_gpu.out 2>&1
echo "$(date -u +%H:%M:%S) gsm exit $?" >> logs/chain.log
