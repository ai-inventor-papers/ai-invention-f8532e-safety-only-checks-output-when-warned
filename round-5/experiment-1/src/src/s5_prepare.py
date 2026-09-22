#!/usr/bin/env python3
"""S5 step 0: discover the held-out substrate manifest(s) and build the confirmation queue.

`--list-only` (allowed at ANY time) globs for the manifest and reports existence/size/mtime WITHOUT
opening it. Without that flag the script requires results/survivor.sha256 (the freeze) and then
reads the manifest through join.py's schema-adaptive loader, writing results/confirm/queue.json
(tag, repo, arrays dir if the iteration-4 27-file schema is present, outcome fields, order).
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))

RES = WS / "results"
PATTERN = "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/*/results/panel_manifest.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--pattern", default=PATTERN)
    ap.add_argument("--results-dir", type=Path, default=RES)
    args = ap.parse_args()
    paths = [Path(p) for p in sorted(glob.glob(args.pattern)) if WS not in Path(p).parents]
    rec = [{"path": str(p), "exists": p.exists(), "size": p.stat().st_size if p.exists() else None,
            "mtime_utc": (__import__("datetime").datetime.utcfromtimestamp(p.stat().st_mtime).isoformat() + "Z")
            if p.exists() else None} for p in paths]
    (args.results_dir / "confirm").mkdir(parents=True, exist_ok=True)
    (args.results_dir / "confirm/manifest_sightings.json").write_text(json.dumps(
        {"pattern": args.pattern, "utc": __import__("datetime").datetime.utcnow().isoformat() + "Z",
         "manifests": rec, "read": not args.list_only}, indent=1))
    print(json.dumps(rec, indent=1))
    if args.list_only:
        return
    import confirm_score  # noqa: PLC0415  (freeze gate + loguru ordering)
    confirm_score.assert_frozen(args.results_dir)
    import join  # noqa: PLC0415
    cks, schema = join.load_confirmation_checkpoints(args.pattern, WS, args.results_dir)
    out = {"utc": __import__("datetime").datetime.utcnow().isoformat() + "Z", "n": len(cks),
           "schema_records": schema, "checkpoints": cks}
    (args.results_dir / "confirm/queue.json").write_text(json.dumps(out, indent=1, default=str))
    print(f"confirmation queue: {len(cks)} checkpoints -> results/confirm/queue.json")
    for c in cks:
        print("  ", c.get("tag"), c.get("repo"), "arrays:", bool(c.get("dir")), "OR:", c.get("OR"))


if __name__ == "__main__":
    main()
