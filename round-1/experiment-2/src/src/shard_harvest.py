"""Convert any single-file harvest npz that exceeds the per-file deployment limit
into numbered parts, verifying the round-trip EXACTLY before deleting the original.

Only touches lineages whose {tag}_meta.json exists, so a harvest still being
written is never converted mid-flight.

usage: python -u src/shard_harvest.py [--limit-mb 100] [--dry-run]
"""
from __future__ import annotations
import argparse, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, save_sharded, ShardedNpz, shard_paths

HARV = OUT / "harvest"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-mb", type=float, default=100.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-age-sec", type=float, default=None,
                    help="also convert files from a still-running lineage, provided the file has "
                         "not been modified for this many seconds (i.e. the writer has moved on). "
                         "A 400MB np.savez completes in well under a second on this mount, so a "
                         "file older than ~60s is certainly complete.")
    a = ap.parse_args()
    limit = a.limit_mb * 1_000_000
    done_tags = {p.stem.replace("_meta", "") for p in HARV.glob("*_meta.json")}
    converted, skipped = [], []
    for f in sorted(HARV.glob("*.npz")):
        if ".part" in f.name:
            continue
        size = f.stat().st_size
        if size <= limit:
            continue
        tag = f.stem.split("_a")[0]
        if tag not in done_tags:
            age = time.time() - f.stat().st_mtime
            if a.min_age_sec is None or age < a.min_age_sec:
                skipped.append((f.name, f"lineage still harvesting (file age {age:.0f}s)"))
                continue
            print(f"   (lineage {tag} still harvesting, but {f.name} is {age:.0f}s stale "
                  f"-> safe to convert)", flush=True)
        stem = f.with_suffix("")
        print(f"{f.name}  {size/1e6:.1f} MB -> sharding", flush=True)
        if a.dry_run:
            continue
        z = np.load(f)
        arrays = {k: z[k] for k in z.files}
        z.close()
        parts = save_sharded(stem, arrays)
        # VERIFY EXACTLY before deleting anything
        back = ShardedNpz(stem)
        assert set(back.files) == set(arrays), f"{f.name}: key set changed"
        for k in arrays:
            assert np.array_equal(back[k], arrays[k]), f"{f.name}: {k} differs"
        biggest = max(p.stat().st_size for p in parts)
        assert biggest <= limit, f"{f.name}: a part is still {biggest/1e6:.1f} MB"
        f.unlink()
        converted.append((f.name, len(parts), biggest / 1e6))
        print(f"   -> {len(parts)} parts, largest {biggest/1e6:.1f} MB, verified exact, "
              f"original deleted", flush=True)
        del arrays
    print()
    for n, k, mb in converted:
        print(f"CONVERTED {n}: {k} parts, largest {mb:.1f} MB")
    for n, why in skipped:
        print(f"SKIPPED   {n}: {why}")
    over = [f for f in HARV.glob("*.npz") if f.stat().st_size > limit]
    print(f"\nremaining over {a.limit_mb:.0f} MB in out/harvest: {len(over)}")
    for f in over:
        print("  ", f.name, f"{f.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()
