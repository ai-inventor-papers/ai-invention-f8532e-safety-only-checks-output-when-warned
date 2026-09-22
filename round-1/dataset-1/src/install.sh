#!/usr/bin/env bash
# Restore the environment for this artifact. See README.md > Restoring removed files.
set -euo pipefail
cd "$(dirname "$0")"
uv venv .venv --python=3.12
uv pip install --python=.venv/bin/python \
    datasets huggingface_hub transformers pandas numpy requests aiohttp loguru tenacity scipy jinja2
echo "Done. Run: .venv/bin/python src/verify_substrate.py"
