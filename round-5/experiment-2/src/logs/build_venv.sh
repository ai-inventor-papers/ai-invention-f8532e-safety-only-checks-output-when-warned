#!/usr/bin/env bash
set -euo pipefail
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
uv venv --python 3.12 .venv_gpu
uv pip install --python .venv_gpu/bin/python --extra-index-url https://download.pytorch.org/whl/cu128 \
   --index-strategy unsafe-best-match -r env/requirements_gpu.txt
"$WS/.venv_gpu/bin/python" -c "import torch;print('TORCH',torch.__version__,torch.cuda.is_available())"
echo "VENV_BUILD_DONE"
