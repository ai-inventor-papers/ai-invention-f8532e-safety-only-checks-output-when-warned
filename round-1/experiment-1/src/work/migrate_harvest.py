#!/usr/bin/env python3
"""Split every oversized harvest archive into <100 MB row shards, in place, one at a time."""
import gc, json, sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from loguru import logger
from lane_a import shard

logger.remove(); logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{message}")
LIMIT = 100 * 1024 ** 2
report = []
targets = sorted(p for p in (HERE / "harvest").rglob("*.npz")
                 if ".part" not in p.name and p.stat().st_size > shard.MAX_SHARD_BYTES)
logger.info(f"{len(targets)} archive(s) over {shard.MAX_SHARD_BYTES/1024**2:.0f} MB")
for p in targets:
    t0 = time.time()
    r = shard.migrate(p)
    r["secs"] = round(time.time() - t0, 1)
    r["rel"] = str(p.relative_to(HERE))
    report.append(r)
    logger.info(f"  {r['rel']:44s} {r['bytes_before']/1024**2:7.1f} MB -> "
                f"{r['n_parts']:3d} parts, max {r['max_part_bytes']/1024**2:5.1f} MB "
                f"({r['secs']}s) budget_met={r['budget_met']}")
    gc.collect()
(HERE / "work" / "shard_migration.json").write_text(json.dumps(report, indent=2))
over = [p for p in (HERE / "harvest").rglob("*") if p.is_file() and p.stat().st_size > LIMIT]
print(f"\nfiles still over 100 MB in harvest/: {len(over)}")
assert not over, [str(p) for p in over]
print("MIGRATION OK")
