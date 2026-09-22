#!/usr/bin/env bash
# Rebuild the environment this artifact runs in. Requires `uv` on PATH.
set -euo pipefail
cd "$(dirname "$0")"
uv venv .venv --python=3.12
VIRTUAL_ENV="$PWD/.venv" uv pip install -r requirements.txt
echo "done -- run with: .venv/bin/python eval.py"
