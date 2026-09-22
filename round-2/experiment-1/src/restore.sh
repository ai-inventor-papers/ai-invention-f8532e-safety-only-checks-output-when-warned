#!/usr/bin/env bash
# Rebuild everything the manifest marks as regenerable.
set -euo pipefail
cd "$(dirname "$0")"

echo "== 1/3 environment =="
uv venv --python 3.12 .venv
UV_INDEX_STRATEGY=unsafe-best-match uv pip install --python .venv/bin/python \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match -r pyproject.toml

echo "== 2/3 assets + arithmetic unit tests =="
uv run method.py --stages stage0 t1

echo "== 3/3 weights-only sufficient statistics (ZERO PROMPTS -> X10, strata) =="
uv run method.py --stages fetch wsummary randinit_w weightfp

echo
echo "Done. To rebuild the ACTIVATION harvest as well (hours on CPU):"
echo "    uv run method.py --stages sweep judge csweep"
echo "Then:"
echo "    ./finish2.sh"
