#!/usr/bin/env bash
# Rebuild the environment and re-fetch everything marked `delete` in .aii/manifest.yaml.
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/3  python environment =="
uv venv .venv --python=3.12
uv pip install --python=.venv/bin/python torch \
  --index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match
uv pip install --python=.venv/bin/python -r requirements.txt

echo "== 2/3  input corpora (pinned; SHA-256s are recorded in work/prereg.json) =="
mkdir -p items
curl -sL -o items/xstest_prompts.csv \
  "https://raw.githubusercontent.com/paul-rottger/exaggerated-safety/main/xstest_prompts.csv"
curl -sL -o items/advbench_harmful_behaviors.csv \
  "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv"
curl -sL -o items/orbench_hard1k.parquet \
  "https://huggingface.co/api/datasets/bench-llm/or-bench/parquet/or-bench-hard-1k/train/0.parquet"
curl -sL -o items/orbench_toxic.parquet \
  "https://huggingface.co/api/datasets/bench-llm/or-bench/parquet/or-bench-toxic/train/0.parquet"
curl -sL -o items/jbb_benign.parquet \
  "https://huggingface.co/api/datasets/JailbreakBench/JBB-Behaviors/parquet/behaviors/benign/0.parquet"
curl -sL -o items/alpaca.parquet \
  "https://huggingface.co/api/datasets/tatsu-lab/alpaca/parquet/default/train/0.parquet"

echo "== 3/3  model panel into the HF cache (~60 GB, all ungated) =="
.venv/bin/python prefetch.py

echo "Done. Now run:  .venv/bin/python method.py --stage all"
