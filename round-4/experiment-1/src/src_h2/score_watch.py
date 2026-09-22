#!/usr/bin/env python
"""Incremental per-checkpoint scorer: score each checkpoint as soon as ALL of its inputs exist.

A checkpoint is READY when its prompt harvest (DONE), its weight summary (W_DONE) and its
teacher-forced C-harvest (C_DONE, or a recorded C-harvest failure) are all on disk. Scoring
goes through analyze.score_one(), i.e. the same code path and the same per-checkpoint cache
the final `analyze.py` run reads, so the final run only has to do the panel-level tests. The
cache key covers every input file, so nothing stale is ever reused.

    uv run src/score_watch.py --until 11:30
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import ASSETS, HARVEST, RESULTS, WS, jload, jload_maybe, setup_logging  # noqa: E402
from loguru import logger  # noqa: E402


def _ready(tag: str, c_failed: set[str]) -> bool:
    d = HARVEST / tag
    if not (d / "DONE").exists() or not (d / "W_DONE").exists():
        return False
    # C_SKIPPED marks a checkpoint the time-gated C-harvest deliberately does not cover
    return (d / "C_DONE").exists() or (d / "C_SKIPPED").exists() or tag in c_failed


@logger.catch(reraise=True)
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default="11:30", help="HH:MM (UTC) to stop polling")
    ap.add_argument("--poll-s", type=float, default=45.0)
    a = ap.parse_args()
    setup_logging("score_watch")
    import analyze as an

    prereg = jload(WS / "prereg.json")
    cfg = dict(prereg["config"])
    cfg["primary_fpr_level"] = prereg["stimuli_meta"]["primary_fpr_level"]
    stim = jload(ASSETS / "stimuli.json")["rows"]
    hh, mm = (int(x) for x in a.until.split(":"))
    done: set[str] = set()
    while True:
        now = time.gmtime()
        if (now.tm_hour, now.tm_min) >= (hh, mm):
            logger.info("deadline reached; stopping")
            break
        fails = jload_maybe(RESULTS / "c_harvest_failures.json", []) or []
        c_failed = {f.get("tag") for f in fails if isinstance(f, dict)}
        todo = [p.parent.name for p in sorted(HARVEST.glob("*/DONE"))
                if not p.parent.name.startswith("_") and p.parent.name not in done
                and _ready(p.parent.name, c_failed)]
        for tag in todo:
            t0 = time.time()
            try:
                _, _, cached = an.score_one(tag, cfg, stim)
                done.add(tag)
                logger.info(f"{'cached' if cached else 'SCORED'} {tag} in {time.time()-t0:.0f}s")
            except Exception as exc:  # noqa: BLE001 - one checkpoint must not stop the watcher
                logger.error(f"scoring failed for {tag}: {exc!r}")
                done.add(tag)
        time.sleep(a.poll_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
