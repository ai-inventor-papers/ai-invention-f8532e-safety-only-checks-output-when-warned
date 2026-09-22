#!/usr/bin/env python
"""ITERATION 2, LANE A -- orchestrator.

Does the model ACT on harm, or only SEE it?

Stages (each is independently runnable and resumable):
    fetch      download every panel checkpoint into the run-shared $HF_HOME (session 2)
    stage0     assets, panel, stimuli, token sets, prereg + SHA-256
    t1         arithmetic unit tests (must pass before anything is trusted)
    t2         ground-truth lesion control for X2 / X10 (known rank-one edit, swept alpha)
    wsummary   weights-only sufficient statistics  (ZERO PROMPTS -- gives X10/BL7 for the panel)
    randinit_w weight summary of the random-init arm (fresh initialiser draw)
    sweep      the prompt (P) activation harvest
    judge      behavioural row for the commissioned child with Lane C's exact protocol
    csweep     the teacher-forced C-harvest (X5, X11), per-tokenizer slot rule, causal truncation
    weightfp   edit-recipe fingerprints -> strata
    analyze    offline scoring: candidates, baselines, nulls, bootstrap, E1/E2/E3/E4, budget curve
    t7         determinism: score one checkpoint twice from scratch, byte-compare
    confirm    freeze the survivor, then score it on genuinely untouched evidence
    session2   write the session-2 deviations into the ledger (idempotent)
    outputs    method_out.json, SUMMARY.md, released/
    leak       leakage audits

    uv run method.py --stages stage0 t1 wsummary sweep weightfp analyze confirm outputs leak
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
PY = str(WS / ".venv" / "bin" / "python")
ENV = {"OMP_NUM_THREADS": "2", "MKL_NUM_THREADS": "2", "TOKENIZERS_PARALLELISM": "false",
       "PYTHONUNBUFFERED": "1"}

C_TAGS = ("Qwen--Qwen3-4B mlabonne--Qwen3-4B-abliterated Qwen--Qwen3-4B-Base "
          "Qwen--Qwen3-4B-SafeRL CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 "
          "Qwen--Qwen3-0.6B huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2 Qwen--Qwen3-1.7B "
          "huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2 HuggingFaceTB--SmolLM3-3B "
          "mlx-community--SmolLM3-3B-abliterated-bf16 ibm-granite--granite-3.2-2b-instruct "
          "Damien420--granite-3.2-2b-instruct-abliterated microsoft--Phi-4-mini-instruct "
          "lunahr--Phi-4-mini-instruct-abliterated Qwen--Qwen2.5-1.5B-Instruct "
          "Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3 "
          "stabilityai--stablelm-2-1_6b-chat hereticness--heretic_stablelm-2-1_6b-chat "
          "HuggingFaceTB--SmolLM2-1.7B-Instruct venkycs--SmolLM2-1.7B-Instruct-Abliterated "
          "RandInit-Qwen3-0.6B").split()

STAGES = {
    "fetch": [PY, "src/fetch_models.py"],
    "stage0": [PY, "src/assets_build.py"],
    "t1": [PY, "src/t1_tests.py"],
    "t2": [PY, "src/t2_lesion_control.py"],
    "wsummary": [PY, "src/wsummary.py"],
    "randinit_w": [PY, "src/randinit_wsummary.py"],
    "sweep": [PY, "src/sweep.py"],
    "judge": [PY, "src/judge_ext_lanec.py", "--repo", "mlabonne/Qwen3-4B-abliterated"],
    "csweep": [PY, "src/c_harvest2.py", "--keep-cont-tokens", "56", "--cells", "all",
               "--tags", *C_TAGS],
    "weightfp": [PY, "src/weightfp.py"],
    "analyze": [PY, "src/analyze.py"],
    "t7": [PY, "src/t7_determinism.py"],
    "confirm": [PY, "src/confirm.py"],
    "session2": [PY, "src/session2_deviations.py"],
    "outputs": [PY, "src/make_outputs.py"],
    "leak": [PY, "src/leak_audit.py"],
}


def main() -> int:
    import os

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stages", nargs="*", default=list(STAGES))
    ap.add_argument("--extra", nargs=argparse.REMAINDER, default=[])
    a = ap.parse_args()
    env = dict(os.environ)
    env.update(ENV)
    rc = 0
    for s in a.stages:
        if s not in STAGES:
            print(f"unknown stage {s}; choose from {list(STAGES)}")
            return 2
        cmd = STAGES[s] + (a.extra if a.extra else [])
        print(f"\n=== STAGE {s}: {' '.join(cmd)}", flush=True)
        r = subprocess.run(cmd, cwd=WS, env=env)
        if r.returncode != 0:
            print(f"stage {s} exited {r.returncode}")
            rc = r.returncode
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
