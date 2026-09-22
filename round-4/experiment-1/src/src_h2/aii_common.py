"""Shared plumbing for iteration-2 Lane A: paths, logging, deterministic IO, seeds.

No heavy imports at module level beyond numpy so that Stage-0 asset work and the
pure-numpy scoring path never pay for torch.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parent.parent
IT1 = Path(
    "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art"
)
LANE_A = IT1 / "gen_art_experiment_1"
LANE_B = IT1 / "gen_art_experiment_2"
LANE_C = IT1 / "gen_art_experiment_3"
DATASET = IT1 / "gen_art_dataset_1"
RESEARCH = IT1 / "gen_art_research_1"

ASSETS = WS / "assets"
HARVEST = WS / "harvest"
RESULTS = WS / "results"
OUT = WS / "out"
RELEASED = OUT / "released"
LOGS = WS / "logs"

for _p in (ASSETS, HARVEST, RESULTS, OUT, RELEASED, LOGS):
    _p.mkdir(parents=True, exist_ok=True)

GLOBAL_SEED = 20260921
SALT = "iter2_laneA_recognition_vs_execution"


def setup_logging(name: str) -> None:
    """stdout + a rotating file sink, per the repo's python conventions."""
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}",
        enqueue=False,
    )
    logger.add(
        LOGS / f"{name}.log",
        level="DEBUG",
        rotation="50 MB",
        retention=5,
        encoding="utf-8",
        enqueue=False,
    )


def set_all_seeds(seed: int = GLOBAL_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed % (2**32 - 1))
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:  # torch is optional on the pure-numpy path
        import torch

        torch.manual_seed(seed)
        torch.use_deterministic_algorithms(False)
    except Exception:  # noqa: BLE001 - torch genuinely may not be importable here
        pass


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()
    )


def stable_hash_unit(key: str, salt: str = SALT) -> float:
    """Deterministic uniform-[0,1) from a string. Used for screen/confirm splits so the
    assignment cannot be chosen after looking at results."""
    h = hashlib.sha256((salt + "::" + key).encode()).hexdigest()
    return int(h[:16], 16) / float(1 << 64)


class NpEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:  # noqa: D102
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            v = float(o)
            if np.isnan(v) or np.isinf(v):
                return None
            return v
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, (set, frozenset)):
            return sorted(o)
        return super().default(o)


def _finite_or_none(obj: Any) -> Any:
    """Recursively replace NaN/inf (Python OR numpy floats, at any depth) with None.

    NpEncoder.default() is only consulted for objects json cannot already serialise, so a
    plain Python float('nan') inside a list slips past it and allow_nan=False then raises.
    Walking the structure once makes every writer strictly valid JSON.
    """
    if isinstance(obj, dict):
        return {k: _finite_or_none(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite_or_none(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _finite_or_none(obj.tolist())
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return v if np.isfinite(v) else None
    return obj


def jdump(obj: Any, path: Path, indent: int = 1) -> Path:
    """Atomic JSON write (tmp + rename) so a killed process never leaves a half file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    obj = _finite_or_none(obj)
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=indent, cls=NpEncoder, allow_nan=False)
    tmp.replace(path)
    return path


def jload(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def jload_maybe(path: Path, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return jload(p)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"could not parse {p}: {exc}")
        return default


# GitHub rejects files above 100 MiB, so any large array is stored as numbered parts
# (<name>_parts/<name>_part_NNN.npy, split along axis 0) with an index.json beside them.
SPLIT_MAX_BYTES = 90 * 1024 ** 2


def save_npy_split(arr: np.ndarray, out_dir: Path, name: str,
                   max_bytes: int = SPLIT_MAX_BYTES) -> Path:
    """Write `arr` as <out_dir>/<name>_parts/<name>_part_001.npy, _002.npy, ... (each part
    below `max_bytes`, split along axis 0) plus an index.json recording shape and dtype."""
    d = Path(out_dir) / f"{name}_parts"
    d.mkdir(parents=True, exist_ok=True)
    for old_part in d.glob(f"{name}_part_*.npy"):
        old_part.unlink()
    n0 = int(arr.shape[0])
    per_row = int(arr[0].nbytes) if n0 else 1
    rows = max(1, int(max_bytes // max(per_row, 1)))
    parts = []
    for k, i0 in enumerate(range(0, max(n0, 1), rows), start=1):
        f = d / f"{name}_part_{k:03d}.npy"
        np.save(f, arr[i0:i0 + rows])
        parts.append(f.name)
    jdump({"name": name, "shape": [int(x) for x in arr.shape], "dtype": str(arr.dtype),
           "split_axis": 0, "rows_per_part": rows, "parts": parts,
           "why": "GitHub's 100 MiB per-file limit; read back with "
                  "aii_common.load_npy_maybe_split"}, d / "index.json")
    return d


def load_npy_maybe_split(out_dir: Path, name: str) -> np.ndarray | None:
    """Load <name>.npy, or reassemble <name>_parts/ written by save_npy_split (validated
    against its index.json). Returns None when neither exists."""
    out_dir = Path(out_dir)
    f = out_dir / f"{name}.npy"
    if f.exists():
        return np.load(f)
    d = out_dir / f"{name}_parts"
    if not d.is_dir():
        return None
    idx = jload_maybe(d / "index.json", {}) or {}
    files = [d / x for x in idx.get("parts", [])] or sorted(d.glob(f"{name}_part_*.npy"))
    if not files:
        return None
    arr = np.concatenate([np.load(x) for x in files], axis=0)
    if idx.get("shape") and list(arr.shape) != list(idx["shape"]):
        raise ValueError(f"{d}: reassembled shape {arr.shape} != index {idx['shape']}")
    return arr


def slug(repo: str) -> str:
    return repo.replace("/", "--")


def clean_float(x: Any) -> Any:
    """NaN/inf -> None so the output JSON is strictly valid."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if np.isnan(v) or np.isinf(v):
        return None
    return v


@dataclass
class Deviations:
    """Append-only ledger. Section 11 requires EVERY failure, cut and cast in the output."""

    path: Path
    items: list[dict] = field(default_factory=list)

    def add(self, kind: str, what: str, detail: str = "", **extra: Any) -> None:
        # Read-modify-write: several processes (sweep, wsummary, weightfp, analyze) share
        # this ledger, and a fresh process starts with an empty `items` list, so appending
        # without re-reading would silently OVERWRITE every earlier entry.
        self.load()
        rec = {
            "kind": kind,
            "what": what,
            "detail": detail,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        rec.update(extra)
        self.items.append(rec)
        logger.warning(f"DEVIATION[{kind}] {what} :: {detail}")
        self.flush()

    def flush(self) -> None:
        jdump(self.items, self.path)

    def load(self) -> None:
        self.items = jload_maybe(self.path, []) or []


DEVIATIONS = Deviations(RESULTS / "deviations.json")


class CostLedger:
    """OpenRouter spend tracker. Nothing outside our own code enforces the cap."""

    def __init__(self, path: Path, cap_usd: float = 2.0) -> None:
        self.path = Path(path)
        self.cap = cap_usd

    def total(self) -> float:
        if not self.path.exists():
            return 0.0
        tot = 0.0
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    tot += float(json.loads(line).get("cost_usd", 0.0) or 0.0)
                except Exception:  # noqa: BLE001
                    continue
        return tot

    def add(self, **rec: Any) -> float:
        rec.setdefault("ts", time.time())
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        return self.total()

    def would_exceed(self, projected: float = 0.0) -> bool:
        return (self.total() + projected) >= self.cap


COST = CostLedger(WS / ".aii_cost_ledger.jsonl", cap_usd=2.0)


class Deadline:
    """Wall-clock ladder with hard gates (design decision D5)."""

    def __init__(self, total_minutes: float) -> None:
        self.t0 = time.time()
        self.total = total_minutes * 60.0

    def elapsed_min(self) -> float:
        return (time.time() - self.t0) / 60.0

    def remaining_min(self) -> float:
        return (self.total - (time.time() - self.t0)) / 60.0

    def past(self, minutes: float) -> bool:
        return self.elapsed_min() >= minutes

    def have(self, minutes: float) -> bool:
        return self.remaining_min() >= minutes


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:3.1f}{unit}"
        n /= 1024.0
    return f"{n:.1f}PB"


def dir_size(p: Path) -> int:
    tot = 0
    for f in Path(p).rglob("*"):
        try:
            if f.is_file() and not f.is_symlink():
                tot += f.stat().st_size
        except OSError:
            continue
    return tot


def cgroup_mem_limit_bytes() -> int | None:
    """The REAL memory ceiling.  `free` reports the host's 251 GB; the cgroup v1 limit on
    this box is 16 GB and is what the OOM killer enforces, shared across every process this
    lane starts.  A 4B model in bfloat16 is ~8 GB, so two of them at once is fatal."""
    for p in ("/sys/fs/cgroup/memory.max",
              "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            v = Path(p).read_text().strip()
            if v and v != "max":
                n = int(v)
                if 0 < n < (1 << 50):
                    return n
        except (OSError, ValueError):
            continue
    return None


def cgroup_mem_used_bytes() -> int | None:
    """ANONYMOUS memory in use, not total usage.

    memory.usage_in_bytes (v1) and memory.current (v2) both INCLUDE the page cache, which on
    this box sits pinned at the limit because the harvest streams gigabytes of safetensors
    through it. Page cache is reclaimable and is not what the OOM killer runs out of, so a
    headroom check against total usage never opens. The right quantity is the anonymous
    working set, read from memory.stat.
    """
    for p, key in (("/sys/fs/cgroup/memory.stat", "anon"),
                   ("/sys/fs/cgroup/memory/memory.stat", "total_rss")):
        try:
            for line in Path(p).read_text().splitlines():
                k, _, v = line.partition(" ")
                if k == key:
                    return int(v)
        except (OSError, ValueError):
            continue
    for p in ("/sys/fs/cgroup/memory.current",
              "/sys/fs/cgroup/memory/memory.usage_in_bytes"):
        try:
            return int(Path(p).read_text().strip())
        except (OSError, ValueError):
            continue
    return None


def wait_for_memory(need_bytes: int, timeout_s: float = 1800.0,
                    poll_s: float = 20.0) -> bool:
    """Block until `need_bytes` of headroom exists inside the cgroup, or time out.

    Used to serialise the few steps that must load a whole model, so they never race the
    harvest sweep into the OOM killer.
    """
    lim = cgroup_mem_limit_bytes()
    if lim is None:
        return True
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        used = cgroup_mem_used_bytes()
        if used is None:
            return True
        if lim - used >= need_bytes:
            return True
        logger.info(f"waiting for memory: need {human_bytes(need_bytes)}, free "
                    f"{human_bytes(lim - used)} of {human_bytes(lim)}")
        time.sleep(poll_s)
    return False
