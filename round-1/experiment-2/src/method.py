#!/usr/bin/env python
"""LANE B - "Erase the safety signal, remeasure".

Where does safety live inside a model, and can it be read from ONE model's
activations without running a benchmark?

METHOD (all five readouts read activations or weights of a SINGLE model):
  STAGE 0  Rebuild the item substrate deterministically and FREEZE a prereg.
           150 XSTest minimal-edit twin pairs from the six genuine contrast
           families; a sha256-ordered 96/54 split; a 2x2 of
           request{harmful, matched benign twin} x response-prefix{hazardous,
           benign} with the response span token-identical across the request
           manipulation; a disjoint 64-pair corpus for the response-site axis;
           and a disjoint held-out request set for the damage curve.
  STAGE 1  Pilot on Qwen3-4B: tokenisation/span tests, hook tests, band
           selection on the fitting corpus only, then freeze the band.
  STAGE 2  Harvest window-mean residual VECTORS (not scalars) so every
           direction-based re-analysis - parent-fixed, per-state refit, the 20
           random-direction nulls - is free and needs no re-run.
  STAGE 3  Five candidate readouts K1..K5 plus the registered baselines.
  STAGE 4  THE LESION. W(a) = W0 - a*u*(u^T W0) on every residual-stream write
           matrix (o_proj, down_proj, all 36 layers), five strengths.
           Qwen3 gives those matrices no bias, so for y = W0 x this is exactly
           y -> y - a*u*(u^T y): we apply it as an output projection, which makes
           alpha=0 a bitwise no-op, the restore exact, and embed_tokens provably
           untouched (it is TIED to lm_head, so editing it would contaminate the
           causal arm's logit-space outcome).
  STAGE 5  Matched damage: nothing is compared unmatched.
  STAGE 6  Integrity gates G1/G2/G3, evaluated BEFORE any post-edit number.
  STAGE 7  Causal arm: readable is not the same as load-bearing.
  STAGE 8  S2 scoring, with the T = CB + A entailment disclosed.
  STAGE 9  External check against a real community abliteration, WEIGHTS ONLY.

usage:
  uv run method.py                  # full pipeline
  uv run method.py --stage emit     # just re-emit the outputs
  uv run method.py --lineages L2,L3 # restrict the panel
"""
from __future__ import annotations
import argparse, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = str(ROOT / ".venv" / "bin" / "python")
SRC = ROOT / "src"
ENV = {**os.environ, "OMP_NUM_THREADS": "8", "OPENBLAS_NUM_THREADS": "8",
       "MKL_NUM_THREADS": "8", "PYTHONUNBUFFERED": "1"}

STAGES = ["substrate", "addendum", "pilot", "harvest", "weightcheck", "depth",
          "analyze", "redundancy", "causal", "emit", "assemble", "shard", "structout"]


def run(args: list[str], name: str) -> int:
    t = time.time()
    print(f"\n===== {name} =====", flush=True)
    rc = subprocess.call([PY, "-u", *args], cwd=ROOT, env=ENV)
    print(f"===== {name} rc={rc} in {time.time()-t:.0f}s =====", flush=True)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", help="one of " + ",".join(STAGES) + " or 'all'")
    ap.add_argument("--lineages", default="L2,L3,L1,L4")
    ap.add_argument("--causal-alphas", default="0.0,1.0")
    a = ap.parse_args()
    want = STAGES if a.stage == "all" else [a.stage]
    lgs = a.lineages.split(",")
    rc = 0

    if "substrate" in want:
        rc |= run([str(SRC / "substrate.py")], "STAGE 0 substrate + prereg (T0)")
    if "addendum" in want:
        rc |= run([str(SRC / "addendum.py")], "STAGE 0b declared diagnostic addendum")
    if "pilot" in want:
        rc |= run([str(SRC / "pilot.py")], "STAGE 1 pilot + T1/T2/T3 + band selection")
    if "harvest" in want:
        for lg in lgs:
            rc |= run([str(SRC / "run_lineage.py"), lg], f"STAGE 2-6 harvest {lg}")
    if "weightcheck" in want:
        rc |= run([str(SRC / "weightcheck.py")], "STAGE 9 weight-space external check")
    if "depth" in want:
        rc |= run([str(SRC / "stage9_depth.py")], "STAGE 9b depth profile of the community edit")
    if "analyze" in want:
        rc |= run([str(SRC / "analyze.py"), "--lineages", ",".join(lgs)],
                  "STAGE 3/5/6/8 readouts, matched damage, gates, S2")
    if "redundancy" in want:
        rc |= run([str(SRC / "redundancy.py")], "how many directions carry the harm percept")
    if "causal" in want:
        for lg in lgs:
            for al in a.causal_alphas.split(","):
                rc |= run([str(SRC / "causal.py"), lg, "--alpha", al], f"STAGE 7 causal arm {lg} a={al}")
    if "emit" in want:
        rc |= run([str(SRC / "emit.py")], "emit method_out.json (exp_gen_sol_out schema)")
    if "assemble" in want:
        rc |= run([str(SRC / "assemble.py")], "assemble results.json + T7")
    if "shard" in want:
        rc |= run([str(SRC / "shard_harvest.py")], "shard oversized harvest npz (100MB limit)")
    if "structout" in want:
        rc |= run([str(SRC / "structout.py")], "write the artifact struct-out")
    return rc


if __name__ == "__main__":
    sys.exit(main())
