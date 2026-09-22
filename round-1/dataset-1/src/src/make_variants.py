#!/usr/bin/env python3
"""Emit full / mini / preview variants.

The aii-json format script requires a top-level ARRAY; these deliverables are
exp_sel_data_out objects, so the same three variants are produced here with the
same semantics: full = identical, mini = first 3 examples per dataset,
preview = mini with every string truncated to 200 characters.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/variants.log", rotation="10 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
LIMIT_MB = 10.0
# data_out.json is the stimulus substrate. Its variants are named *_stimulus_cells.json so they do
# not collide with mini_/preview_data_out.json, which belong to data.py's source-corpora output.
TARGETS = {"data_out.json": "stimulus_cells", "heldout_cells.json": "heldout_cells"}


def truncate(o: Any, n: int = 200) -> Any:
    if isinstance(o, str):
        return o if len(o) <= n else o[:n] + "...[truncated]"
    if isinstance(o, list):
        return [truncate(x, n) for x in o]
    if isinstance(o, dict):
        return {k: truncate(v, n) for k, v in o.items()}
    return o


def mini(obj: dict[str, Any], k: int = 3) -> dict[str, Any]:
    out = json.loads(json.dumps(obj))
    for d in out["datasets"]:
        d["examples"] = d["examples"][:k]
    return out


@logger.catch(reraise=True)
def main() -> None:
    for name, base in TARGETS.items():
        src = ROOT / name
        if not src.exists():
            logger.error(f"{name} missing")
            continue
        obj = json.loads(src.read_text())
        # No full_<base> copy: the base file IS the full version, and writing one
        # would collide with full_data_out.json, which data.py owns.
        (ROOT / f"mini_{base}.json").write_text(json.dumps(mini(obj), ensure_ascii=False, indent=1))
        (ROOT / f"preview_{base}.json").write_text(json.dumps(truncate(mini(obj)), ensure_ascii=False, indent=1))
        for p in (src, ROOT / f"mini_{base}.json", ROOT / f"preview_{base}.json"):
            mb = p.stat().st_size / 1e6
            flag = "  <-- OVER THE LIMIT, SPLIT REQUIRED" if mb > LIMIT_MB else ""
            logger.info(f"{p.name:34s} {mb:7.2f} MB{flag}")


if __name__ == "__main__":
    main()
