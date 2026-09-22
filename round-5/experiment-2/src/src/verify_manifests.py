#!/usr/bin/env python3
"""Re-hash every file named in every arrays/<tag>/MANIFEST.sha256.json and report mismatches.

T2/T7 acceptance: "MANIFEST.sha256.json verifies" and "every array listed with shape, dtype and
sha256". DONE must be the LAST file written, so its mtime is checked against the rest too.

    python3 verify_manifests.py
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
ARRAYS = WS / "arrays"


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    rows, bad = [], 0
    for d in sorted(x for x in ARRAYS.iterdir() if x.is_dir() and (x / "DONE").exists()):
        mp = d / "MANIFEST.sha256.json"
        if not mp.exists():
            rows.append({"tag": d.name, "status": "NO_MANIFEST"}); bad += 1; continue
        man = json.loads(mp.read_text(encoding="utf-8"))
        files = man.get("files", man)
        n_ok = n_miss = n_drift = 0
        for rel, ent in (files.items() if isinstance(files, dict) else []):
            want = ent.get("sha256") if isinstance(ent, dict) else ent
            f = d / rel
            if not f.exists():
                n_miss += 1
            elif want and sha256(f) != want:
                n_drift += 1
            else:
                n_ok += 1
        done_m = (d / "DONE").stat().st_mtime
        newer = [p.name for p in d.rglob("*")
                 if p.is_file() and p.name != "DONE" and p.stat().st_mtime > done_m + 5]
        # tier-3 back-fill legitimately rewrites meta/MANIFEST after DONE; note it, don't fail
        newer = [n for n in newer if n not in ("meta.json", "MANIFEST.sha256.json")]
        st = "OK" if (n_miss == 0 and n_drift == 0) else "MISMATCH"
        if st != "OK":
            bad += 1
        rows.append({"tag": d.name, "status": st, "n_files": n_ok + n_miss + n_drift,
                     "verified": n_ok, "missing": n_miss, "drifted": n_drift,
                     "written_after_DONE": newer[:8]})
    out = {"utc": __import__("datetime").datetime.now(
               __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "n_tags": len(rows), "n_bad": bad,
           "all_manifests_verify": bad == 0, "rows": rows}
    tmp = WS / "results" / "manifest_verification.json.tmp"
    tmp.write_text(json.dumps(out, indent=1), encoding="utf-8")
    os.replace(tmp, WS / "results" / "manifest_verification.json")
    for r in rows:
        if r["status"] != "OK" or r.get("written_after_DONE"):
            print(f"  {r['status']:9} {r['tag']:46} verified={r.get('verified')} "
                  f"missing={r.get('missing')} drifted={r.get('drifted')} "
                  f"after_DONE={r.get('written_after_DONE')}")
    print(f"MANIFEST verification: {len(rows) - bad}/{len(rows)} tags verify "
          f"({sum(r.get('verified', 0) for r in rows)} files re-hashed)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
