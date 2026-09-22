#!/usr/bin/env bash
# Re-render every cell and re-assemble, after a change to slots or templates.
set -euo pipefail
cd "$(dirname "$0")"
PY=.venv/bin/python
$PY src/gen_cells.py
$PY src/gen_aux.py
$PY src/assemble.py
echo "rebuild complete"
