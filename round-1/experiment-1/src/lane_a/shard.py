#!/usr/bin/env python3
"""Row-sharded .npz I/O.

The harvest writes a few arrays that are far larger than the 100 MB per-file ceiling this
repository is deployed under (the main grid is ~833 MB per checkpoint). Rather than compress
them -- which would still leave one opaque blob and cost a decompression pass on every read
-- each oversized archive is split along AXIS 0, the request axis, into parts that are each
a valid ``.npz`` in their own right, plus a small JSON manifest listing them.

``load_npz`` hides the difference: it returns the same ``{name: array}`` mapping whether the
archive was written whole or in parts, so call sites never branch on it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

# 90 MB leaves headroom under the 100 MB ceiling for npz container overhead.
MAX_SHARD_BYTES = 90 * 1024 ** 2
PART_SUFFIX = ".part{:03d}.npz"


def manifest_path(path: Path) -> Path:
    return path.with_name(path.stem + ".shards.json")


def part_paths(path: Path) -> list[Path]:
    mp = manifest_path(path)
    if not mp.exists():
        return []
    man = json.loads(mp.read_text())
    return [path.with_name(n) for n in man["parts"]]


def exists(path: Path) -> bool:
    """True if the archive is readable, whole or sharded."""
    return path.exists() or manifest_path(path).exists()


def _clear(path: Path) -> None:
    for p in part_paths(path):
        p.unlink(missing_ok=True)
    manifest_path(path).unlink(missing_ok=True)


def save_npz(path: Path, *, max_bytes: int = MAX_SHARD_BYTES, **arrays: np.ndarray) -> list[str]:
    """Write arrays to ``path``, splitting along axis 0 if they would exceed ``max_bytes``.

    Every array in one archive must share its axis-0 length, which is true of every archive
    this pipeline writes: axis 0 is always the request index.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    arrays = {k: np.asarray(v) for k, v in arrays.items()}
    total = sum(a.nbytes for a in arrays.values())
    if total <= max_bytes:
        _clear(path)
        np.savez(path, **arrays)
        return [path.name]

    rows = {a.shape[0] for a in arrays.values() if a.ndim >= 1}
    if len(rows) != 1:
        raise ValueError(f"{path.name}: cannot shard, axis-0 lengths differ: "
                         f"{ {k: v.shape for k, v in arrays.items()} }")
    n = rows.pop()
    per_row = max(total / max(n, 1), 1.0)
    rows_per_part = max(1, int(max_bytes // per_row))

    _clear(path)
    parts: list[str] = []
    for i, start in enumerate(range(0, n, rows_per_part)):
        sl = slice(start, min(start + rows_per_part, n))
        p = path.with_name(path.stem + PART_SUFFIX.format(i))
        np.savez(p, **{k: v[sl] for k, v in arrays.items()})
        parts.append(p.name)
    biggest = max((path.with_name(nm).stat().st_size for nm in parts), default=0)
    # A single row is the atomic unit, so a budget smaller than one row cannot be met.
    # Say so loudly instead of silently shipping an oversized part.
    row_too_big = rows_per_part == 1 and biggest > max_bytes
    if row_too_big:
        logger.warning(f"{path.name}: one row is {per_row / 1024 ** 2:.1f} MB, larger than the "
                       f"{max_bytes / 1024 ** 2:.1f} MB budget -- parts are {biggest / 1024 ** 2:.1f} MB "
                       f"and CANNOT be made smaller by row splitting")
    manifest_path(path).write_text(json.dumps({
        "sharded": True,
        "whole_name": path.name,
        "n_rows": int(n),
        "rows_per_part": int(rows_per_part),
        "max_part_bytes": int(biggest),
        "budget_bytes": int(max_bytes),
        "budget_met": bool(not row_too_big),
        "parts": parts,
        "arrays": {k: {"dtype": str(v.dtype), "shape": list(v.shape)} for k, v in arrays.items()},
        "note": ("Split along axis 0 (the request axis) so no single file exceeds the "
                 "deployment size ceiling. Read it with lane_a.shard.load_npz, which "
                 "concatenates the parts back in order."),
    }, indent=2))
    path.unlink(missing_ok=True)
    return parts


def load_npz(path: Path) -> dict[str, np.ndarray]:
    """Return ``{name: array}`` for an archive written whole or in row shards."""
    mp = manifest_path(path)
    if mp.exists():
        man = json.loads(mp.read_text())
        chunks: dict[str, list[np.ndarray]] = {}
        for name in man["parts"]:
            p = path.with_name(name)
            if not p.exists():
                raise FileNotFoundError(f"shard {p} listed in {mp.name} is missing")
            with np.load(p, allow_pickle=False) as z:
                for k in z.files:
                    chunks.setdefault(k, []).append(z[k])
        out = {k: (np.concatenate(v, axis=0) if v[0].ndim >= 1 else v[0])
               for k, v in chunks.items()}
        for k, spec in man.get("arrays", {}).items():
            if k in out and list(out[k].shape) != spec["shape"]:
                raise ValueError(f"{path.name}: shard reassembly gave {k} shape "
                                 f"{list(out[k].shape)}, manifest says {spec['shape']}")
        return out
    if not path.exists():
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def migrate(path: Path, *, max_bytes: int = MAX_SHARD_BYTES) -> dict[str, Any]:
    """Re-write an already-written oversized archive as shards, in place."""
    if not path.exists():
        return {"path": str(path), "action": "absent"}
    before = path.stat().st_size
    if before <= max_bytes:
        return {"path": str(path), "action": "kept_whole", "bytes": before}
    with np.load(path, allow_pickle=False) as z:
        arrays = {k: z[k] for k in z.files}
    tmp = path.with_name(path.stem + ".migrating.npz")
    parts = save_npz(tmp, max_bytes=max_bytes, **arrays)
    # save_npz wrote tmp.partNNN.npz + tmp.shards.json -- rename onto the real stem
    renamed = []
    for i, name in enumerate(parts):
        src = path.with_name(name)
        dst = path.with_name(path.stem + PART_SUFFIX.format(i))
        src.rename(dst)
        renamed.append(dst.name)
    man = json.loads(manifest_path(tmp).read_text())
    man["parts"] = renamed
    man["whole_name"] = path.name
    manifest_path(path).write_text(json.dumps(man, indent=2))
    manifest_path(tmp).unlink(missing_ok=True)
    tmp.unlink(missing_ok=True)
    path.unlink(missing_ok=True)
    del arrays
    biggest = max(p.stat().st_size for p in [path.with_name(n) for n in renamed])
    return {"path": str(path), "action": "sharded", "bytes_before": before,
            "n_parts": len(renamed), "max_part_bytes": biggest,
            "budget_met": bool(biggest <= max_bytes)}


__all__ = ["MAX_SHARD_BYTES", "save_npz", "load_npz", "exists", "migrate",
           "manifest_path", "part_paths"]
