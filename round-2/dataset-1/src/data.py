#!/usr/bin/env python3
"""Top-level builder for the iteration-2 dataset substrate.

Runs the build phases in dependency order and writes full_data_out.json in the
exp_sel_data_out schema: {"datasets": [{"dataset": ..., "examples": [{input, output,
metadata_*}, ...]}, ...]} with one example PER ROW (per checkpoint, per pair, per
prompt, per token, per token-x-tokenizer cell), never one example per dataset.

Run it with the project venv, which install.sh creates:

    ./install.sh && .venv/bin/python data.py

Phases
  A  src/phase_a_prereg.py     freeze the rules (refuses to overwrite an existing freeze)
  B  src/behavioural_join.py   recompute iteration-1 rates, contamination bookkeeping
  -  src/build_registry.py     live Hub metadata for the paired-lineage registry
  -  src/sourcing.py           download the public corpora into temp/datasets/
  -  src/build_recognition_set.py   the hard recognition set
  -  src/build_tokens.py       the three token sets + the tokenizer table
  C  src/phase_c_label.py      join the behavioural delta, apply the frozen labels
  D  src/phase_d_probes.py     the four disjoint probe pools
  E  src/phase_e_assemble.py   assemble full_data_out.json + gates.json
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent
PY = str(ROOT / ".venv" / "bin" / "python")

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(ROOT / "logs" / "data.log", rotation="30 MB", level="DEBUG")

# (script, required, note). `required=False` steps are skipped when a prerequisite
# build artefact is already present, so the pipeline is resumable.
STEPS: list[tuple[str, str]] = [
    ("src/phase_a_prereg.py", "PHASE A freeze"),
    ("src/behavioural_join.py", "PHASE B behavioural recompute"),
    ("src/build_registry.py", "registry metadata"),
    ("src/sourcing.py", "download public corpora"),
    ("src/build_recognition_set.py", "hard recognition set"),
    ("src/build_tokens.py", "token sets + tokenizer table"),
    ("src/phase_c_label.py", "PHASE C labels"),
    ("src/phase_d_probes.py", "PHASE D probe pools"),
    ("src/phase_e_assemble.py", "PHASE E assembly + gates"),
]


@logger.catch(reraise=True)
def main() -> None:
    only = sys.argv[1:]
    for script, note in STEPS:
        if only and not any(o in script for o in only):
            continue
        path = ROOT / script
        if not path.exists():
            logger.warning(f"skip {script} ({note}) - not present")
            continue
        if script.endswith("phase_a_prereg.py") and (ROOT / "prereg.json").exists():
            logger.info("skip PHASE A - prereg.json is already frozen (this is correct; "
                        "the freeze is deliberately not re-runnable)")
            continue
        logger.info(f"=== {note}: {script}")
        r = subprocess.run([PY, str(path)], cwd=ROOT)
        if r.returncode != 0:
            logger.error(f"{script} exited {r.returncode}")
            sys.exit(r.returncode)
    logger.info("build complete -> full_data_out.json, gates.json")


if __name__ == "__main__":
    main()
