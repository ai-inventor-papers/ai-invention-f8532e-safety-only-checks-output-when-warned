#!/usr/bin/env bash
# Environment only. `restore.sh` additionally rebuilds the regenerable artifacts.
set -euo pipefail
cd "$(dirname "$0")"
uv venv --python 3.12 .venv
UV_INDEX_STRATEGY=unsafe-best-match uv pip install --python .venv/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match -r pyproject.toml
.venv/bin/python -c "import torch, transformers, numpy, scipy, sklearn, safetensors; \
print('torch', torch.__version__, 'cuda', torch.cuda.is_available()); \
print('transformers', transformers.__version__)"
