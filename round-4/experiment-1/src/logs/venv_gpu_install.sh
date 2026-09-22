#!/bin/bash
# Session 4 (pod restarted ~18:23 UTC onto a box WITH an NVIDIA L4): CUDA build of the same pinned environment.
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1
cd "$WS" || exit 1
echo "$(date -u) start" 
uv venv --python 3.12 .venv_gpu
uv pip install --python .venv_gpu/bin/python --extra-index-url https://download.pytorch.org/whl/cu128 \
   --index-strategy unsafe-best-match -r env/requirements_gpu.txt
echo "$(date -u) exit $?"
.venv_gpu/bin/python -c "import torch;print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
echo "$(date -u) done"
