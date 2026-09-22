#!/usr/bin/env python3
"""Append-only numbered deviation log.

Every relaxation, fallback and surprise is recorded here with a number, never
silently applied.  The two rules that may NEVER be relaxed are the
family-exclusion rule and the order gate (no harvest before graded_truth is
committed); a deviation claiming to relax either is rejected.

    python deviations.py add --id D07 --title "..." --detail "..." [--rung 2]
    python deviations.py list
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any

WS = Path(__file__).resolve().parent.parent
OUT = WS / "results" / "deviations.json"

FORBIDDEN_RELAXATIONS = ("family-exclusion", "family exclusion", "order gate", "order-gate")


def _utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load() -> dict[str, Any]:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"utc_created": _utc(), "policy": (
        "Append-only. Every fallback is numbered and stated. The family-exclusion "
        "rule and the order gate are NEVER relaxed; an attempt to log such a "
        "relaxation is refused by this module."), "deviations": []}


def add(dev_id: str, title: str, detail: str, rung: int | None = None,
        stage: str | None = None) -> dict[str, Any]:
    low = f"{title} {detail}".lower()
    for bad in FORBIDDEN_RELAXATIONS:
        if bad in low and ("relax" in low or "waive" in low or "skip" in low or "bypass" in low):
            raise SystemExit(
                f"REFUSED: deviation {dev_id} appears to relax a never-relaxable rule "
                f"({bad!r}). The family-exclusion rule and the order gate are absolute."
            )
    doc = load()
    taken = {str(d.get("id") or d.get("code")) for d in doc["deviations"]}
    if dev_id == "auto" or dev_id in taken:
        # Several processes append here concurrently; never fail on a collision, take the
        # next free D-number instead (ids stay append-only and unique).
        nums = [int(t[1:]) for t in taken if t.startswith("D") and t[1:].isdigit()]
        dev_id = f"D{(max(nums) + 1) if nums else 1:02d}"
    # Emit BOTH key sets: this module's (id/title) and common.deviation()'s
    # (n/code), so either reader works against one shared results/deviations.json.
    rec = {"n": len(doc["deviations"]) + 1, "code": dev_id, "id": dev_id,
           "utc": _utc(), "title": title, "detail": detail,
           "reduction_ladder_rung": rung, "stage": stage or ""}
    doc["deviations"].append(rec)
    doc["n"] = len(doc["deviations"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("--id", required=True)
    a.add_argument("--title", required=True)
    a.add_argument("--detail", required=True)
    a.add_argument("--rung", type=int, default=None)
    a.add_argument("--stage", default=None)
    sub.add_parser("list")
    ns = ap.parse_args()
    if ns.cmd == "add":
        print(json.dumps(add(ns.id, ns.title, ns.detail, ns.rung, ns.stage), indent=1))
    else:
        doc = load()
        for d in doc["deviations"]:
            print(f"{d.get('id') or d.get('code')}  {d.get('utc')}  "
                  f"{d.get('title') or str(d.get('detail'))[:90]}")
        print(f"n={len(doc['deviations'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
