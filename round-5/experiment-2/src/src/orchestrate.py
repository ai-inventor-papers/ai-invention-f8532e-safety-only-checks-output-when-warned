#!/usr/bin/env python3
"""Commit-then-harvest orchestrator for the PANEL tags (HG__*).

Runs beside the generation sweep and the judge watcher. Each cycle it:
  1. finds panel tags that are JUDGED but not yet covered by a valid (non-retracted,
     hash-verified, N >= 1) graded_truth commit, and commits them together as the next
     stage s<N>, which appends the stage file's sha256 to logs/chain.jsonl -- the ORDER GATE;
  2. ONLY IF the instrument selftests have passed (results/T3_GATE.json says so), harvests
     gated-but-unharvested tags in frozen sweep order, one long-lived process per cycle so
     torch is imported once. pipeline.py harvest itself refuses any ungated tag, so this
     loop can never harvest ahead of the gate even if it had a bug.

Part-B tags (PB__*) are committed and harvested by src/partb.py, not here.

    python orchestrate.py [--deadline-utc 2026-09-22T05:15:00Z] [--max-tags 28] [--once]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "src"))

from loguru import logger  # noqa: E402

import judgeflow as jf  # noqa: E402

PY = str(WS / ".venv_gpu" / "bin" / "python")
GENS = WS / "private" / "gens"
RESULTS = WS / "results"
ARRAYS = WS / "arrays"
T3_GATE = RESULTS / "T3_GATE.json"
ENV = {**os.environ, "TORCH_DISABLE_NATIVE_JIT": "1",
       "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True", "OMP_NUM_THREADS": "4",
       "OPENBLAS_NUM_THREADS": "4", "MKL_NUM_THREADS": "4", "TOKENIZERS_PARALLELISM": "false",
       "HF_HUB_DISABLE_TELEMETRY": "1"}


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sweep_tags(max_tags: int) -> list[str]:
    order = json.loads((RESULTS / "sweep_order.json").read_text())["order"]
    return ["HG__" + r["repo"].replace("/", "--") for r in order][:max_tags]


def next_stage() -> int:
    nums = []
    for p in RESULTS.glob("graded_truth_s*.json"):
        tail = p.stem.split("_s")[-1]
        if tail.isdigit() and int(tail) < 900:        # s9NN is reserved for Part B
            nums.append(int(tail))
    return max([0, *nums]) + 1


def cycle(max_tags: int, harvest_ok: bool) -> dict:
    tags = sweep_tags(max_tags)
    judged = [t for t in tags if (GENS / f"{t}.JUDGED").exists()]
    to_commit = [t for t in judged if not jf.order_gate_ok(t)]
    out = {"utc": utc(), "judged": len(judged), "committed_now": [], "harvested_now": []}
    if to_commit:
        st = next_stage()
        rc = subprocess.run([PY, str(WS / "src" / "judgeflow.py"), "commit", "--stage", str(st),
                             "--tags", *to_commit], cwd=WS, env=ENV).returncode
        logger.info(f"commit s{st}: {len(to_commit)} tag(s) rc={rc}")
        if rc == 0:
            out["committed_now"] = to_commit
    if harvest_ok:
        todo = [t for t in tags if jf.order_gate_ok(t) and not (ARRAYS / t / "DONE").exists()]
        if todo:
            logger.info(f"harvest {len(todo)} gated tag(s): {todo}")
            with open(WS / "logs" / "harvest_sweep.log", "a") as lf:
                rc = subprocess.run([PY, str(WS / "src" / "pipeline.py"), "harvest", "--tags", *todo,
                                     "--tier2", "--r-draws-p", "5"],
                                    cwd=WS, env=ENV, stdout=lf, stderr=subprocess.STDOUT).returncode
            logger.info(f"harvest rc={rc}")
            out["harvested_now"] = [t for t in todo if (ARRAYS / t / "DONE").exists()]
    return out


@logger.catch(reraise=True)
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-tags", type=int, default=28)
    ap.add_argument("--deadline-utc", default=None)
    ap.add_argument("--poll", type=int, default=60)
    ap.add_argument("--once", action="store_true")
    ns = ap.parse_args()
    logger.remove()
    logger.add(sys.stdout, format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(WS / "logs" / "orchestrate.log", rotation="20 MB")
    while True:
        gate = json.loads(T3_GATE.read_text()) if T3_GATE.exists() else {}
        harvest_ok = bool(gate.get("harvest_allowed"))
        rec = cycle(ns.max_tags, harvest_ok)
        logger.info(f"cycle: judged={rec['judged']} committed_now={len(rec['committed_now'])} "
                    f"harvested_now={len(rec['harvested_now'])} harvest_allowed={harvest_ok}")
        if ns.once:
            return 0
        if ns.deadline_utc and utc() >= ns.deadline_utc:
            logger.warning("deadline reached; orchestrator exiting")
            return 0
        time.sleep(ns.poll)


if __name__ == "__main__":
    sys.exit(main())
