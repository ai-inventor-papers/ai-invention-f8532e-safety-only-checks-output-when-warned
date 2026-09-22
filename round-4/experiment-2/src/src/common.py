"""Shared paths, logging, hashing, JSON I/O and resource helpers for the causal depth x site grid.

Every file this module writes lives under the workspace WS (the directory above src/).
Inputs from earlier iterations are READ-ONLY.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parents[1]
RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
H2 = RUN / "iter_2/gen_art/gen_art_experiment_1"          # iter-2 harvest (A_prompt, token ids, stimuli)
D2 = RUN / "iter_2/gen_art/gen_art_dataset_1"             # iter-2 probe sets + judge assets
D1 = RUN / "iter_1/gen_art/gen_art_dataset_1"             # iter-1 XSTest twins + safety_2x2
I1_DIRS = RUN / "iter_1/gen_art/gen_art_experiment_1/out/released/directions"

ASSETS = WS / "assets"
RESULTS = WS / "results"
LOGS = WS / "logs"
OUT = WS / "out"
CELLS = OUT / "cells"
PRIVATE = OUT / "private"          # responses + directions: never released, deleted before submission
FIGS = WS / "figures"
for _d in (ASSETS, RESULTS, LOGS, CELLS, PRIVATE, FIGS):
    _d.mkdir(parents=True, exist_ok=True)

LEDGER = WS / ".aii_cost_ledger.jsonl"
JUDGE_CACHE = PRIVATE / "judge_cache.jsonl"
DEVIATIONS = RESULTS / "deviations.json"

MODELS = {  # short name -> (hub repo, iter-2 harvest tag)
    "instruct": ("Qwen/Qwen3-4B", "Qwen--Qwen3-4B"),
    "saferl": ("Qwen/Qwen3-4B-SafeRL", "Qwen--Qwen3-4B-SafeRL"),
}
# plan section 9(c) optional third checkpoint (GPU addendum); kept out of MODELS so the frozen
# two-model prereg code paths (prep.py) are unchanged
EXTRA_MODELS = {
    "abliterated": ("mlabonne/Qwen3-4B-abliterated", "mlabonne--Qwen3-4B-abliterated"),
}
ALL_MODELS = {**MODELS, **EXTRA_MODELS}
SEED_STR = "iter4_causal_grid_v1"
SEED = int(hashlib.sha256(SEED_STR.encode()).hexdigest()[:16], 16)


def setup_logging(name: str) -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(str(LOGS / f"{name}.log"), rotation="30 MB", level="DEBUG")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def norm_text(t: str) -> str:
    return re.sub(r"\s+", " ", t.strip().lower())


def text_hash(t: str) -> str:
    """Normalised request-text hash used for every disjointness assertion."""
    return sha256_str(norm_text(t))


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating,)):
        o = float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return _clean(o.tolist())
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        return None
    return o


def jdump(p: Path, obj: Any, indent: int | None = 1) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(_clean(obj), indent=indent, ensure_ascii=False))
    tmp.replace(p)


def jload(p: Path) -> Any:
    return json.loads(Path(p).read_text())


def add_deviation(key: str, what: str, why: str, impact: str) -> None:
    devs = jload(DEVIATIONS) if DEVIATIONS.exists() else []
    if any(d.get("key") == key for d in devs):
        return
    devs.append({"key": key, "what": what, "why": why, "impact": impact, "utc": utc_now()})
    jdump(DEVIATIONS, devs)


def cgroup_mem_gb() -> tuple[float, float]:
    """(current, limit) GB of the container cgroup (shared with sibling agents)."""
    try:
        cur = int(Path("/sys/fs/cgroup/memory.current").read_text()) / 1e9
        lim_s = Path("/sys/fs/cgroup/memory.max").read_text().strip()
        lim = float("inf") if lim_s == "max" else int(lim_s) / 1e9
        return cur, lim
    except (FileNotFoundError, ValueError):
        pass
    try:  # cgroup v1 (this box)
        cur = int(Path("/sys/fs/cgroup/memory/memory.usage_in_bytes").read_text()) / 1e9
        lim = int(Path("/sys/fs/cgroup/memory/memory.limit_in_bytes").read_text()) / 1e9
        return cur, lim
    except (FileNotFoundError, ValueError):
        return float("nan"), float("nan")


def detect_cpus() -> int:
    try:
        parts = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if parts[0] != "max":
            return math.ceil(int(parts[0]) / int(parts[1]))
    except (FileNotFoundError, ValueError):
        pass
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 1


class Timer:
    def __init__(self, label: str):
        self.label = label

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *a):
        self.dt = time.time() - self.t0
        logger.info(f"[time] {self.label}: {self.dt:.1f}s")


# ---------------------------------------------------------------------------------------------
# depth bands (1-indexed B1..B6, sixths of the 36 decoder layers; layer l = hidden index l+1)
# ---------------------------------------------------------------------------------------------
N_LAYERS = 36
BANDS = {f"B{k}": list(range(6 * (k - 1), 6 * k)) for k in range(1, 7)}


def bands_for(n_layers: int) -> dict[str, list[int]]:
    """Sixths of n_layers (used for the 28-layer Qwen3-0.6B smoke test)."""
    edges = [round(n_layers * k / 6) for k in range(7)]
    return {f"B{k + 1}": list(range(edges[k], edges[k + 1])) for k in range(6)}
