#!/usr/bin/env python3
"""Blind held-out panel for the safety screen -- the orchestrating entry point.

PRODUCER-ONLY, BLIND. This artifact grades behaviour, saves activation arrays and
commits a SHA-256 hash-chained manifest. It computes NO candidate score: no
W1-W8 / G1-G4 / A1-A3 quantity, no Spearman or Pearson statistic, no ranking, no
"best band", no survivor. A sibling screen artifact freezes its candidates
before opening anything written here; a third artifact re-runs the join.

THE METHOD AND ITS BASELINES, side by side in one pipeline
-----------------------------------------------------------
The *method substrate* is activation-level and reads a single model:
  per-layer residuals at the prompt site (A_prompt*), at the decode site
  (A_dec, A_dec_tok1), a per-checkpoint direction bank fitted from the model's
  OWN activations (F_b, N6_b, matched-norm orthogonalised R_b over six
  depth-fraction bands, plus split-half fits), a forward-only intervention grid
  (site-local, random-control, nested-ladder cells) and self-lesion re-fits.
The *baselines* are produced by the same code path on the same prompts, so no
implementation-level confound separates them from the method substrate:
  (1) TEXT-ONLY -- the onset-anchored keyword-refusal proxy on every behavioural
      set (proxy_refusal_<SET> columns): the judge-free bar any readout must beat;
  (2) LOGIT-ONLY -- softmax mass on the refusal / hedge / control unembedding
      rows at the next-token position (logits.npy in every intervention cell,
      WU_ref/WU_hed/WU_ctl.npy per tag);
  (3) PUBLISHED ACTIVATION INSTRUMENT -- the AMS separation sigma, reimplemented
      and run at batch 1 AND batch 8 because the released CLI's padding bug moves
      one family by > 5 sigma (ams_sigma_bs1 / ams_sigma_bs8).
The TARGET all of them will later be scored against is the graded behaviour:
harmful compliance on HARM, over-refusal on TWO named benign sets
(OR_XSTEST54, OR_HARDBENIGN), and safe engagement, each with a Wilson 95% CI.
Comparing method against baselines is the scorer's job, deliberately not done
here.

STAGES (each resumable; re-running skips completed work)
  A  panel rule + seeded draw ............ src/panel.py        (already frozen: chain 0-1)
  B  frozen item sets .................... src/items_build.py  (chain: item_sets_frozen)
  C  greedy generation ................... src/pipeline.py gen
  D  judging + staged graded_truth commit  src/judgeflow.py watch / commit   <- ORDER GATE
  E  harvest + direction bank + grid ..... src/pipeline.py harvest (refuses ungated tags)
  F  in-house no-op / effective arms ..... src/partb.py
  G  manifest, diagnostics, lint, output . src/manifest.py, src/rates.py,
                                           src/hygiene_check.py, src/build_method_out.py

    python method.py                       # resume everything with defaults
    python method.py --n-tags 24           # widen the panel
    python method.py --stage G             # only rebuild the outputs
    python method.py --status              # report, change nothing
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

WS = Path(__file__).resolve().parent
SRC = WS / "src"
PY = str(WS / ".venv_gpu" / "bin" / "python")
SYS_PY = sys.executable

ENV = {
    **os.environ,
    # HF_HOME and friends are deliberately NOT overridden: they point at the run's
    # shared cache, and overriding them stores every weight twice (deviation D01).
    "TORCH_DISABLE_NATIVE_JIT": "1",
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    "OMP_NUM_THREADS": "4",
    "OPENBLAS_NUM_THREADS": "4",
    "MKL_NUM_THREADS": "4",
    "TOKENIZERS_PARALLELISM": "false",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO",
               format="{time:HH:mm:ss}|{level:<7}|{message}")
    (WS / "logs").mkdir(exist_ok=True)
    logger.add(WS / "logs" / "method.log", rotation="30 MB", level="DEBUG")


def run(args: list[str], *, check: bool = True, log: str | None = None,
        python: str = PY) -> int:
    """Run one stage as a subprocess (each stage is its own long-lived process so torch
    is imported once per stage, never per item)."""
    cmd = [python, *args]
    logger.info("$ " + " ".join(cmd[1:]))
    out = open(WS / "logs" / log, "a") if log else None
    try:
        rc = subprocess.run(cmd, cwd=WS, env=ENV, stdout=out or None,
                            stderr=subprocess.STDOUT if out else None).returncode
    finally:
        if out:
            out.close()
    if check and rc != 0:
        raise RuntimeError(f"stage failed rc={rc}: {' '.join(args)}")
    return rc


def n_markers(pattern: str) -> int:
    return len(list((WS / "private" / "gens").glob(pattern)))


def stage_A() -> None:
    if (WS / "results" / "panel.json").exists():
        logger.info("A: panel rule + draw already frozen (chain records 0-1) -- skipping")
        return
    run([str(SRC / "panel.py"), "rule"])
    run([str(SRC / "panel.py"), "draw"])


def stage_B() -> None:
    if (WS / "results" / "item_sets.json").exists():
        logger.info("B: item sets already frozen and chained -- skipping")
        return
    run([str(SRC / "items_build.py")], python=SYS_PY)


def stages_CD(n_tags: int, deadline_utc: str | None) -> None:
    """Generation sweep with the judge watcher running concurrently."""
    watch_cmd = [PY, str(SRC / "judgeflow.py"), "watch", "--poll", "20",
                 "--soft-stop-usd", "4.5"]
    if deadline_utc:
        watch_cmd += ["--deadline-utc", deadline_utc]
    wlog = open(WS / "logs" / "judge_watch.log", "a")
    watcher = subprocess.Popen(watch_cmd, cwd=WS, env=ENV, stdout=wlog,
                               stderr=subprocess.STDOUT)
    logger.info(f"C/D: judge watcher pid={watcher.pid}")
    try:
        run([str(SRC / "pipeline.py"), "gen", "--from-sweep", str(n_tags),
             "--batch", "16", "--max-new-harm", "140", "--max-new-benign", "96"],
            log="gen_sweep.log", check=False)
        # let the watcher drain everything generation produced
        for _ in range(180):
            done, judged = n_markers("*.GEN_DONE"), n_markers("*.JUDGED")
            if judged >= done:
                break
            time.sleep(20)
        logger.info(f"C/D: generated={n_markers('*.GEN_DONE')} judged={n_markers('*.JUDGED')}")
    finally:
        if watcher.poll() is None:
            watcher.send_signal(signal.SIGTERM)
            try:
                watcher.wait(timeout=60)
            except subprocess.TimeoutExpired:
                watcher.kill()
        wlog.close()


def stage_D_commit() -> None:
    """Commit every judged-but-uncommitted tag as the next stage (s1, s2, ...).

    graded_truth_s0.json is a retracted smoke stub (deviation D06), so real
    stages start at 1."""
    existing = sorted(int(p.stem.split("_s")[-1])
                      for p in (WS / "results").glob("graded_truth_s*.json")
                      if p.stem.split("_s")[-1].isdigit())
    nxt = max([0, *existing]) + 1
    run([str(SRC / "judgeflow.py"), "commit", "--stage", str(nxt)], check=False,
        log="commit.log")


def stage_E(n_tags: int, r_draws_p: int, with_c5: bool) -> None:
    args = [str(SRC / "pipeline.py"), "harvest", "--from-sweep", str(n_tags),
            "--tier2", "--r-draws-p", str(r_draws_p)]
    if with_c5:
        args.append("--with-c5")
    run(args, log="harvest_sweep.log", check=False)


def stage_F() -> None:
    if not (SRC / "partb.py").exists():
        logger.warning("F: src/partb.py absent -- skipping the in-house arms")
        return
    run([str(SRC / "partb.py"), "all"], log="partb.log", check=False)


def stage_G() -> None:
    run([str(SRC / "manifest.py"), "rebuild"], python=SYS_PY, check=False)
    run([str(SRC / "rates.py"), "diagnostics"], check=False)
    run([str(SRC / "hygiene_check.py"), "all"], python=SYS_PY, check=False)
    run([str(SRC / "build_method_out.py")], python=SYS_PY)


def status() -> None:
    subprocess.run(["bash", str(WS / "logs" / "relaunch.sh"), "status"], cwd=WS)


@logger.catch(reraise=True)
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n-tags", type=int, default=24,
                    help="panel checkpoints to take from results/sweep_order.json")
    ap.add_argument("--r-draws-p", type=int, default=5,
                    help="C3 random draws at site P (reduction-ladder rung 1: 10 -> 5)")
    ap.add_argument("--with-c5", action="store_true",
                    help="include decode-site intervention cells (rung 2 drops them)")
    ap.add_argument("--deadline-utc", default=None)
    ap.add_argument("--stage", choices=list("ABCDEFG"), default=None,
                    help="run only this stage")
    ap.add_argument("--status", action="store_true")
    ns = ap.parse_args()
    setup_logging()

    if ns.status:
        status()
        return 0

    stages = {
        "A": stage_A,
        "B": stage_B,
        "C": lambda: stages_CD(ns.n_tags, ns.deadline_utc),
        "D": stage_D_commit,
        "E": lambda: stage_E(ns.n_tags, ns.r_draws_p, ns.with_c5),
        "F": stage_F,
        "G": stage_G,
    }
    order = [ns.stage] if ns.stage else list("ABCDEFG")
    for s in order:
        logger.info(f"===== stage {s} =====")
        stages[s]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
