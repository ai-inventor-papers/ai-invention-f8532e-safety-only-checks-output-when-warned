#!/usr/bin/env python3
"""S5 step 1: run the registered Tier-B battery on every landed confirmation checkpoint.

Reads results/confirm/queue.json (written by src/s5_prepare.py after the freeze) and calls
`src/tierB.py --repo <repo> --tag <tag> [--harvest-dir <dir>]` one checkpoint at a time, in the
manifest's own order, skipping any that already has results/confirm/ckpt_<tag>.json, and stopping
cleanly at a wall-clock deadline (achieved n is REPORTED, never padded). No selection happens here.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
RES = WS / "results"
PY = str(WS / ".venv_gpu/bin/python")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline-utc", default="05:25", help="HH:MM UTC: do not START a checkpoint after this")
    ap.add_argument("--results-dir", type=Path, default=RES)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    q = json.loads((args.results_dir / "confirm/queue.json").read_text())
    hh, mm = (int(x) for x in args.deadline_utc.split(":"))
    now = datetime.now(timezone.utc)
    deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if deadline < now:
        deadline = deadline.replace(day=deadline.day + 1)
    log = []
    for i, ck in enumerate(q["checkpoints"]):
        if args.limit and i >= args.limit:
            break
        tag, repo = ck.get("tag"), ck.get("repo")
        out = args.results_dir / f"confirm/ckpt_{tag}.json"
        if out.exists():
            log.append({"tag": tag, "status": "SKIP_EXISTS"})
            continue
        if datetime.now(timezone.utc) >= deadline:
            log.append({"tag": tag, "status": "NOT_RUN_DEADLINE"})
            continue
        cmd = [PY, str(WS / "src/tierB.py"), "--repo", repo, "--tag", tag, "--draws", "none"]
        if ck.get("dir"):
            cmd += ["--harvest-dir", str(ck["dir"])]
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # noqa: S603
        dt = round(time.time() - t0, 1)
        ok = out.exists()
        log.append({"tag": tag, "repo": repo, "status": "OK" if ok else "FAILED", "seconds": dt,
                    "rc": p.returncode, "stderr_tail": p.stderr[-400:] if not ok else ""})
        print(f"{tag}: {'OK' if ok else 'FAILED'} in {dt}s rc={p.returncode}", flush=True)
    (args.results_dir / "confirm/tierb_run_log.json").write_text(json.dumps(
        {"utc": datetime.now(timezone.utc).isoformat(), "deadline_utc": args.deadline_utc, "log": log}, indent=1))
    n_ok = sum(1 for r in log if r["status"] in ("OK", "SKIP_EXISTS"))
    print(f"confirmation Tier-B: {n_ok}/{len(q['checkpoints'])} checkpoints scored")


if __name__ == "__main__":
    main()
