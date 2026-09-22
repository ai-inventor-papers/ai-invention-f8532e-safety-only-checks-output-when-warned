#!/usr/bin/env python
"""LANE C - cross-family safety-readout payoff screen (test S3).

Does an ACTIVATION-ONLY, single-model safety readout predict real safety across
model families, from few prompts? Build a cross-family panel of ungated <=4B
HuggingFace checkpoints (2 families SEALED before scoring), compute five
activation/weight candidate readouts and seven baselines from ONE teacher-forced
harvest per checkpoint, collect behavioural ground truth by generating and
LLM-judging responses, and run leave-one-family-out prediction with no
recalibration (test S3), with the full k in {4,8,16,32,96} prompt-budget curve.

Per the run invariant: logit-only and text-only readouts are BASELINES, not the
result; this is a mech-interp study of WHERE SAFETY LIVES, not a jailbreak study.

Stages (each resumable):
  assets   -> build prompt/item assets (C1)
  prereg   -> live HF panel sweep + seal 2 families + freeze prereg.json (C2)
  harvest  -> per-checkpoint activation harvest + generation (C3/C4)
  judge    -> LLM-judge the generations (C5)
  analyze  -> S3 LOFO + machinery controls + budget curve (C6)
  output   -> assemble method_out.json (C7)
  all      -> run every stage in order
"""
from __future__ import annotations

import argparse
import sys

from loguru import logger

from lc_common import setup_logging


def main():
    ap = argparse.ArgumentParser()
    # default 'finalize' regenerates method_out.json from the CACHED harvest+judge
    # results (analyze + output) with NO GPU work, so `uv run method.py` just works.
    ap.add_argument("--stage", default="finalize",
                    choices=["assets", "prereg", "harvest", "judge", "analyze", "output",
                             "finalize", "all"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--order", default="small")
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    setup_logging("method")

    if a.stage in ("assets", "all"):
        import lc_assets; lc_assets.build()
    if a.stage in ("prereg", "all"):
        import lc_panel; lc_panel.write_prereg()
    if a.stage in ("harvest", "all"):
        import lc_harvest; lc_harvest.run_all(limit=a.limit, order=a.order, only=a.only)
    if a.stage in ("judge", "all"):
        import lc_judge; lc_judge.run()
    if a.stage in ("analyze", "finalize", "all"):
        import lc_analyze; lc_analyze.run()
    if a.stage in ("output", "finalize", "all"):
        import lc_output; lc_output.build()
    logger.info(f"stage '{a.stage}' complete")


if __name__ == "__main__":
    main()
