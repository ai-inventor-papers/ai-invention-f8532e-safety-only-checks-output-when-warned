#!/usr/bin/env bash
# Rebuild the environments of this artifact inside the workspace.
# usage: bash restore.sh [gpu|ams|all]
# (the recipe mirrors iteration 4's restore.sh, but builds HERE; --index-strategy is required)
set -euo pipefail
cd "$(dirname "$0")"
what="${1:-all}"
if [[ "$what" == "gpu" || "$what" == "all" ]]; then
  uv venv --python 3.12 .venv_gpu
  uv pip install --python .venv_gpu/bin/python \
      --extra-index-url https://download.pytorch.org/whl/cu128 \
      --index-strategy unsafe-best-match -r env/requirements_gpu.txt
fi
if [[ "$what" == "ams" || "$what" == "all" ]]; then
  uv venv --python 3.12 .venv_ams
  uv pip install --python .venv_ams/bin/python \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      --index-strategy unsafe-best-match 'ams-scanner[cli]==0.1.3' 'torch==2.9.1+cpu'
fi
echo "restored: $what"
