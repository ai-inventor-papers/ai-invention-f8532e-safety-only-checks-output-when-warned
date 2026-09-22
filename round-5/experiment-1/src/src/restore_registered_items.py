#!/usr/bin/env python3
"""Restore the REGISTERED-draw per-item arrays that the Phase-2 stability pass overwrote.

Phase 2 re-saved ckpt_<tag>_items.npz with only that run's stability items, so 36/42 rows lost the
registered per-item arrays the pair bootstrap needs (the registered JSON scalars are unaffected).
For each affected tag this script:
  1. keeps a copy of the current JSON (stability / patching / transfer / bars blocks),
  2. re-runs `src/tierB.py --tags <tag> --draws none --force` (the registered battery; deterministic,
     so the registered scalars must come back identical),
  3. merges the saved blocks back into the new JSON and records any registered-scalar drift,
  4. merges the old npz's stability items back beside the restored registered arrays.
Stops starting new tags at --deadline-utc. Tags left unrestored are reported, never imputed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parents[1]
RES = WS / "results"
SCREEN = RES / "screen"
PY = str(WS / ".venv_gpu/bin/python")
KEEP_BLOCKS = ("stability", "patching", "transfer", "bars", "norm_displacement", "curves", "per_fold", "sanity")
PRIORITY = (
    ["F1__ref", "F2__ref", "F3__ref", "HG__Qwen--Qwen3-1.7B", "HG__Qwen--Qwen2.5-1.5B-Instruct",
     "HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct", "HG__amd--AMD-OLMo-1B", "HG__amd--AMD-OLMo-1B-SFT",
     "HG__tiiuae--Falcon3-1B-Base"]
    + [f"{f}__{a}" for a in ("fp16", "int8wo", "int8bnb", "wu05", "sysprompt", "a05", "a10", "cautious", "wu20")
       for f in ("F1", "F2", "F3")]
)


def has_registered(npz: Path) -> bool:
    if not npz.exists():
        return False
    with np.load(npz) as z:
        return any(not k.startswith("st") and not k.startswith("c11") for k in z.files)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline-utc", default="03:50")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    hh, mm = (int(x) for x in args.deadline_utc.split(":"))
    now = datetime.now(timezone.utc)
    deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    todo = [p.name[5:-10] for p in sorted(SCREEN.glob("ckpt_*_items.npz")) if not has_registered(p)]
    todo.sort(key=lambda t: (PRIORITY.index(t) if t in PRIORITY else 999, t))
    print(f"{len(todo)} tags need restoration; deadline {args.deadline_utc}Z")
    log = []
    if args.dry_run:
        print(todo)
        return
    for tag in todo:
        if datetime.now(timezone.utc) >= deadline:
            log.append({"tag": tag, "status": "NOT_RESTORED_DEADLINE"})
            continue
        jp, np_p = SCREEN / f"ckpt_{tag}.json", SCREEN / f"ckpt_{tag}_items.npz"
        old = json.loads(jp.read_text())
        with np.load(np_p) as z:
            old_items = {k: z[k] for k in z.files}
        t0 = time.time()
        p = subprocess.run([PY, str(WS / "src/tierB.py"), "--tags", tag, "--draws", "none", "--force"],  # noqa: S603
                           capture_output=True, text=True, timeout=1500)
        new = json.loads(jp.read_text())
        drift = {k: [old.get("registered", {}).get(k), v] for k, v in (new.get("registered") or {}).items()
                 if isinstance(v, (int, float)) and isinstance(old.get("registered", {}).get(k), (int, float))
                 and abs(v - old["registered"][k]) > 1e-9 * max(1.0, abs(v))}
        for b in KEEP_BLOCKS:
            if b in old and (b not in new or not new.get(b)):
                new[b] = old[b]
        if "stability" in old and old["stability"].get("draws"):
            new["stability"] = old["stability"]
        new["registered_items_restored_utc"] = datetime.now(timezone.utc).isoformat()
        jp.write_text(json.dumps(new, indent=1))
        with np.load(np_p) as z:
            merged = {k: z[k] for k in z.files}
        for k, v in old_items.items():
            merged.setdefault(k, v)
        np.savez_compressed(np_p, **merged)
        ok = has_registered(np_p)
        log.append({"tag": tag, "status": "RESTORED" if ok else "FAILED", "seconds": round(time.time() - t0, 1),
                    "rc": p.returncode, "registered_drift": drift,
                    "stderr_tail": "" if ok else p.stderr[-300:]})
        print(f"{tag}: {'RESTORED' if ok else 'FAILED'} {round(time.time()-t0,1)}s drift={len(drift)}", flush=True)
    (RES / "registered_items_restore_log.json").write_text(json.dumps(
        {"utc": datetime.now(timezone.utc).isoformat(), "log": log,
         "n_restored": sum(1 for r in log if r["status"] == "RESTORED"), "n_todo": len(todo)}, indent=1))
    print(f"restored {sum(1 for r in log if r['status'] == 'RESTORED')}/{len(todo)}")


if __name__ == "__main__":
    main()
