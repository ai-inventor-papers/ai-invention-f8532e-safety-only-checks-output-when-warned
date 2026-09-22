#!/usr/bin/env python
"""Fetch ONLY the model cards (README.md) of every panel repo into the run-shared HF cache.

BL5_CARDREGEX reads the card text from the cached snapshot; the session-2 weight fetch
(src/fetch_models.py) did not include README.md, so without this the NAME-FREE card baseline
would silently see an empty card. Writes results/card_fetch_log.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "src"))
from panel import PAIRS, SINGLES  # noqa: E402

repos = []
for p in PAIRS:
    repos += [p["parent"], p["child"]]
repos += [s["repo"] for s in SINGLES]
log = {}
for r in dict.fromkeys(repos):
    try:
        f = hf_hub_download(r, "README.md")
        log[r] = {"ok": True, "chars": len(Path(f).read_text(errors="replace"))}
    except Exception as exc:  # noqa: BLE001 - a repo without a card is a fact, not an error
        log[r] = {"ok": False, "error": repr(exc)[:200]}
(WS / "results" / "card_fetch_log.json").write_text(json.dumps(log, indent=1))
print(sum(v["ok"] for v in log.values()), "of", len(log), "cards fetched")
