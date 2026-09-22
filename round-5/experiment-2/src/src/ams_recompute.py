#!/usr/bin/env python3
"""Recompute the AMS Tier-1 baseline from each tag's harvested A_ams.npy. CPU only, no model.

A BASELINE INSTRUMENT, not a candidate score: it is the published activation-separation
statistic the artifact is meant to sit beside. Runs over any tag whose A_ams.npy came from the
AMS prompt set but whose meta.json lacks the sigma (e.g. harvested before the aggregate key was
fixed). Writes results/ams_baseline.json and updates each meta.json.

    python ams_recompute.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "src"))
sys.path.insert(0, str(WS / "src" / "vendor"))

import numpy as np  # noqa: E402

import ams_reimpl  # noqa: E402


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def refresh_manifest_entry(tag_dir: Path, rel: str) -> None:
    """Re-hash one file in MANIFEST.sha256.json after rewriting it.

    Updating meta.json without this leaves its recorded sha256 stale, which is exactly what
    results/manifest_verification.json then reports as a drift (585 of 586 files verifying).
    The manifest must always describe what is on disk."""
    import hashlib
    mp = tag_dir / "MANIFEST.sha256.json"
    f = tag_dir / rel
    if not mp.exists() or not f.exists():
        return
    man = json.loads(mp.read_text(encoding="utf-8"))
    files = man.get("files") if isinstance(man.get("files"), dict) else man
    if not isinstance(files, dict) or rel not in files:
        return
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    ent = files[rel]
    if isinstance(ent, dict):
        ent["sha256"] = h
        if "bytes" in ent:
            ent["bytes"] = f.stat().st_size
    else:
        files[rel] = h
    mp.write_text(json.dumps(man, indent=1), encoding="utf-8")


def main() -> int:
    rows = []
    prompts = ams_reimpl.ams_prompts()
    for d in sorted(x for x in (WS / "arrays").iterdir() if x.is_dir()):
        ap, mp = d / "A_ams.npy", d / "meta.json"
        if not ap.exists() or not mp.exists():
            continue
        meta = jload(mp)
        if meta.get("ams_row_set") != "ams_prompts":
            rows.append({"tag": d.name, "skipped": "A_ams not from the AMS prompt set"})
            continue
        try:
            res = ams_reimpl.ams_tier1(np.load(ap), prompts, int(meta["n_layers"]))
            per = {k: (v.get("sigma") if isinstance(v, dict) else v)
                   for k, v in (res.get("per_concept") or {}).items()}
            vals = [v for v in per.values() if isinstance(v, (int, float))]
            sig = min(vals) if vals else None
            meta["ams_sigma_bs1"] = sig
            meta["ams_tier1"] = {"min_concept_sigma": sig, "mean_sigma": res.get("mean_sigma"),
                                 "overall_level": res.get("overall_level"), "per_concept": per}
            mp.write_text(json.dumps(meta, indent=1), encoding="utf-8")
            refresh_manifest_entry(d, "meta.json")
            rows.append({"tag": d.name, "min_concept_sigma": sig,
                         "mean_sigma": res.get("mean_sigma"),
                         "overall_level": res.get("overall_level"), "per_concept": per})
            print(f"  {d.name:46} min_sigma={sig:.3f} mean={res.get('mean_sigma'):.3f} "
                  f"{res.get('overall_level')}")
        except Exception as exc:                      # noqa: BLE001
            rows.append({"tag": d.name, "error": repr(exc)[:200]})
            print(f"  {d.name:46} ERROR {exc!r}"[:140])
    ok = [r for r in rows if r.get("min_concept_sigma") is not None]
    out = {"utc": __import__("datetime").datetime.now(
               __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "instrument": "AMS Tier-1 separation sigma, reimplementation (src/vendor/ams_reimpl.py)",
           "role": "BASELINE INSTRUMENT reported beside the activation substrate; NOT a candidate score",
           "rendering": "raw text, NO chat template, last position, batch 1 (padding-free)",
           "batch8_variant": "not computed; this artifact never pads, see deviation on ams_sigma_bs8",
           "n_tags_with_sigma": len(ok), "n_tags_seen": len(rows), "rows": rows}
    (WS / "results" / "ams_baseline.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"AMS baseline: {len(ok)}/{len(rows)} tag(s) with a sigma -> results/ams_baseline.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
