#!/usr/bin/env python3
"""Quick acceptance check: every expected JSON exists, parses, and has no
literal NaN/Infinity tokens (which are invalid JSON but which Python's
json.dumps will happily emit unless guarded -- jsafe() in laneb.py guards
against this, this script double-checks it from the raw bytes)."""
import json
import sys
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
EXPECTED = [
    "laneb_reconcile.json", "laneb_cells.json", "laneb_tests.json",
    "laneb_contrasts.json", "laneb_power.json", "laneb_accum.json",
    "laneb_inventory.json", "laneb_deviations.json",
]

ok = True
for name in EXPECTED:
    p = RESULTS / name
    if not p.exists():
        print(f"MISSING: {name}")
        ok = False
        continue
    raw = p.read_text()
    bad_tokens = [t for t in ("NaN", "Infinity", "-Infinity") if t in raw]
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"INVALID JSON: {name}: {e}")
        ok = False
        continue
    size = p.stat().st_size
    print(f"OK: {name} ({size} bytes){' -- WARNING literal ' + str(bad_tokens) if bad_tokens else ''}")
    if bad_tokens:
        ok = False

npz = RESULTS / "laneb_scores_band.npz"
if npz.exists():
    print(f"OK: laneb_scores_band.npz ({npz.stat().st_size} bytes)")
else:
    print("MISSING: laneb_scores_band.npz")
    ok = False

sys.exit(0 if ok else 1)
