#!/usr/bin/env python3
"""Resume laneb.py from task5 onward.

The first full run (this same laneb.py) already wrote laneb_reconcile.json,
laneb_cells.json, laneb_scores_band.npz, laneb_tests.json and
laneb_contrasts.json (tasks 1-4) to disk and was progressing through task5
(power for saturated cells) when it was killed for wall-clock reasons: a live
pilot on the real 152 qualifying cells showed method (c)'s nominal 200x200
bootstrap-shift grid would not finish in time on this shared 2-CPU box.
laneb.py's bootstrap_shift_mde was then coarsened (40x100, 6-point grid) and
this script resumes from task5 using the ALREADY-COMPUTED task2 cells (no
part of the main grid is recomputed).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import laneb as L  # noqa: E402
from loguru import logger


@L.logger.catch(reraise=True)
def main() -> None:
    t0 = time.time()
    L.note_deviation(
        "Pipeline was RESTARTED at task5: the original laneb.py process (PID "
        "started at the first run) had already written laneb_reconcile.json "
        "(task1), laneb_cells.json + laneb_scores_band.npz (task2), "
        "laneb_tests.json (task3) and laneb_contrasts.json (task4) to disk "
        "and was progressing through task5's 152 qualifying cells when it was "
        "killed (by this same agent, by PID) after >14 minutes with no sign "
        "of finishing method (c)'s bootstrap-shift search inside the wall-"
        "clock budget on a 2-CPU box shared with another job. Tasks 1-4's "
        "outputs are UNCHANGED or recomputed from this restart; this script "
        "(laneb_resume.py) recomputes only tasks 5, 6, 7 with a coarsened "
        "method (c), reusing laneb_cells.json rather than rerunning the main "
        "grid."
    )

    cells_obj = json.loads((L.RESULTS / "laneb_cells.json").read_text())
    cells = cells_obj["cells"]
    logger.info("loaded {} cells from disk", len(cells))

    power = L.task5_power(cells)
    L.dump_json(L.RESULTS / "laneb_power.json", power)
    logger.info("[{:.1f}s] task5 done", time.time() - t0)

    accum = L.task6_accumulator()
    L.dump_json(L.RESULTS / "laneb_accum.json", accum)
    logger.info("[{:.1f}s] task6 done", time.time() - t0)

    inventory = L.task7_inventory()
    L.dump_json(L.RESULTS / "laneb_inventory.json", inventory)
    logger.info("[{:.1f}s] task7 done", time.time() - t0)

    L.dump_json(L.RESULTS / "laneb_deviations.json", {"deviations": L.DEVIATIONS})
    logger.info("RESUME DONE in {:.1f}s", time.time() - t0)


if __name__ == "__main__":
    main()
