#!/usr/bin/env bash
# Rebuild the only deleted path in this workspace.
set -euo pipefail
cd "$(dirname "$0")"
uv venv --python 3.12
uv pip install -r pyproject.toml
