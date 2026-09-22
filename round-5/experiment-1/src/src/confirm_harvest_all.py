#!/usr/bin/env python3
"""S5 compute: harvest + registered Tier-B battery for every held-out checkpoint (post-freeze).

The substrate's own arrays cover A_prompt / A_dec / r_* but NOT A_c11 or A_ams, so AMS sigma (a
required margin bar) and A1_slope cannot be computed from them. This script therefore runs our own
27-file harvest plus the registered Tier-B battery per checkpoint, via
`src/tierB.py --repo <id> --tag <tag> --harvest-dir results/confirm_harvest/<tag>`.

Checkpoint identity comes from a DIRECTORY LISTING of the substrate's arrays (names only - no
manifest contents, no graded truth, no outcome is opened here); the manifest itself is read later by
src/s5_prepare.py / src/join.py at the registered 04:31Z opening. Order is alphabetical by tag and
recorded. Refuses to run before the freeze.
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
sys.path.insert(0, str(WS / "src"))
RES = WS / "results"
PY = str(WS / ".venv_gpu/bin/python")
SUBSTRATE_ARRAYS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2/arrays")


def repo_of(tag: str) -> str | None:
    t = tag[4:] if tag.startswith("HG__") else tag
    if "--" not in t:
        return None
    org, name = t.split("--", 1)
    return f"{org}/{name}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline-utc", default="05:20")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    import confirm_score  # noqa: PLC0415
    confirm_score.assert_frozen(RES)
    hh, mm = (int(x) for x in args.deadline_utc.split(":"))
    now = datetime.now(timezone.utc)
    deadline = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    tags = sorted(p.name for p in SUBSTRATE_ARRAYS.iterdir() if p.is_dir()) if SUBSTRATE_ARRAYS.is_dir() else []
    if args.only:
        tags = [t for t in tags if t in set(args.only)]
    print(f"{len(tags)} held-out checkpoints seen by directory listing; deadline {args.deadline_utc}Z")
    if args.dry_run:
        for t in tags:
            print("  ", t, "->", repo_of(t))
        return
    log = []
    for tag in tags:
        out = RES / f"confirm/ckpt_{tag}.json"
        repo = repo_of(tag)
        if out.exists():
            log.append({"tag": tag, "status": "SKIP_EXISTS"})
            continue
        if repo is None:
            log.append({"tag": tag, "status": "NO_REPO_ID"})
            continue
        if datetime.now(timezone.utc) >= deadline:
            log.append({"tag": tag, "status": "NOT_RUN_DEADLINE"})
            continue
        hd = RES / f"confirm_harvest/{tag}"
        hd.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        p = subprocess.run([PY, str(WS / "src/tierB.py"), "--repo", repo, "--tag", tag,  # noqa: S603
                            "--harvest-dir", str(hd), "--draws", "none"],
                           capture_output=True, text=True, timeout=2400)
        ok = out.exists()
        log.append({"tag": tag, "repo": repo, "status": "OK" if ok else "FAILED",
                    "seconds": round(time.time() - t0, 1), "rc": p.returncode,
                    "stderr_tail": "" if ok else p.stderr[-500:]})
        print(f"{tag}: {'OK' if ok else 'FAILED'} {round(time.time()-t0,1)}s", flush=True)
        (RES / "confirm/harvest_run_log.json").write_text(json.dumps(
            {"utc": datetime.now(timezone.utc).isoformat(), "order": "alphabetical by tag",
             "source": "directory listing of the substrate arrays (names only)", "log": log}, indent=1))
    n_ok = sum(1 for r in log if r["status"] in ("OK", "SKIP_EXISTS"))
    print(f"confirmation compute: {n_ok}/{len(tags)} checkpoints scored")


if __name__ == "__main__":
    main()
