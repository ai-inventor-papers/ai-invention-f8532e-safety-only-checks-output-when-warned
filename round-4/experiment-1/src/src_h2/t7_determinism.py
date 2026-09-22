#!/usr/bin/env python
"""T7 -- REPRODUCIBILITY: score one checkpoint twice from the same caches, from scratch (no
score cache), and assert the real values, the shuffled-label bands and the item-bootstrap CIs
are byte-identical. The determinism IS the claim that every candidate was scored on the same
evidence.

    uv run src/t7_determinism.py --tag Qwen--Qwen3-0.6B --n-null 5 --n-boot 20
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402

from aii_common import ASSETS, RESULTS, WS, jdump, jload, setup_logging  # noqa: E402
from loguru import logger  # noqa: E402
import score_panel as sp  # noqa: E402


def _canon(s: dict) -> str:
    keep = {"real": {k: v for k, v in s["real"].items()
                     if isinstance(v, (int, float, str, bool)) or v is None},
            "nulls": s["nulls"], "boot_ci95": s["boot"]["ci95"],
            "escapes": s["escapes_own_band"]}
    return json.dumps(keep, sort_keys=True, default=lambda o: float(o))


@logger.catch(reraise=True)
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="Qwen--Qwen3-0.6B")
    ap.add_argument("--n-null", type=int, default=5)
    ap.add_argument("--n-boot", type=int, default=20)
    a = ap.parse_args()
    setup_logging("t7_determinism")
    prereg = jload(WS / "prereg.json")
    cfg = dict(prereg["config"])
    cfg["primary_fpr_level"] = prereg["stimuli_meta"]["primary_fpr_level"]
    cfg["n_boot_items"] = a.n_boot
    stim = jload(ASSETS / "stimuli.json")["rows"]
    runs = []
    for i in range(2):
        s = sp.score_checkpoint(a.tag, cfg, stim, n_null=a.n_null, n_rand=5,
                                seed=cfg["seed"] % 1000)
        s.pop("_cache", None)
        runs.append(_canon(s))
        logger.info(f"run {i + 1}: {len(runs[-1])} bytes canonical")
    same = runs[0] == runs[1]
    out = {"test": "T7_scoring_byte_identical", "tag": a.tag, "n_null": a.n_null,
           "n_boot": a.n_boot, "pass": bool(same),
           "bytes": len(runs[0]),
           "note": ("two independent from-scratch scorings of the same harvest caches: real "
                    "values, shuffled-label bands, bootstrap CIs and escape flags compared as "
                    "canonical JSON")}
    jdump(out, RESULTS / "t7_determinism.json")
    logger.info(f"T7 {'PASS' if same else 'FAIL'} on {a.tag}")
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
