#!/usr/bin/env bash
# Recreate the environment this artifact was built with.
set -euo pipefail
cd "$(dirname "$0")"
uv venv .venv --python=3.12
uv pip install --python=.venv/bin/python \
  loguru requests numpy pandas scikit-learn scipy statsmodels \
  datasets huggingface-hub transformers tokenizers
echo "done: .venv/bin/python"
