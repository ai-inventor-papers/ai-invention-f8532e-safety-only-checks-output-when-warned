#!/bin/bash
# Rebuild the environments deleted after the round (see .aii/manifest.yaml). Usage: bash restore.sh [cpu|gpu|ams|all]
set -e
WS="$(cd "$(dirname "$0")" && pwd)"
cd "$WS"
what=${1:-all}
if [ "$what" = cpu ] || [ "$what" = all ]; then
  # scoring + assembly environment (CPU torch; src/pairs.py, method.py, src/judge.py, src/truth_classify.py)
  uv venv --python 3.12 .venv
  uv pip install --python .venv/bin/python --extra-index-url https://download.pytorch.org/whl/cpu \
     --index-strategy unsafe-best-match -r pyproject.toml
fi
if [ "$what" = gpu ] || [ "$what" = all ]; then
  # generation + harvest environment (CUDA 12.8 torch, bitsandbytes for the LLM.int8 arm)
  uv venv --python 3.12 .venv_gpu
  uv pip install --python .venv_gpu/bin/python --extra-index-url https://download.pytorch.org/whl/cu128 \
     --index-strategy unsafe-best-match -r env/requirements_gpu.txt
fi
if [ "$what" = ams ] || [ "$what" = all ]; then
  # the published AMS scanner (arXiv 2608.05578), only for src/validate_ams.py (reimplementation check)
  uv venv --python 3.12 .venv_ams
  uv pip install --python .venv_ams/bin/python --extra-index-url https://download.pytorch.org/whl/cpu \
     --index-strategy unsafe-best-match "ams-scanner[cli]==0.1.3" "torch==2.9.1+cpu"
fi
