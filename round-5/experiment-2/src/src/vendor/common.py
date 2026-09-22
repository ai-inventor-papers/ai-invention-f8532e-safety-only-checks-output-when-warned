"""Shared paths, logging, hashing, the SHA-256 order chain and the deviation ledger (iter-4 no-op/effective set).

Everything this artifact writes lives under WS. Read-only sources (earlier iterations) are addressed through
RUN; their files are COPIED into src_i3/, src_h2/ and assets/ with a sha256 in results/provenance.json.
The HF cache is the run-wide shared cache ($HF_HOME, set by the pipeline) and is NOT overridden here.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

WS = Path(__file__).resolve().parents[2]   # PATCHED iter5: vendored at src/vendor/, so parents[2] is the workspace (was parents[1] -> src/)
RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
I3 = RUN / "iter_3/gen_art/gen_art_experiment_1"
H2 = RUN / "iter_2/gen_art/gen_art_experiment_1"
LANEC = RUN / "iter_1/gen_art/gen_art_experiment_3"
D1 = RUN / "iter_1/gen_art/gen_art_dataset_1"
D2 = RUN / "iter_2/gen_art/gen_art_dataset_1"

ASSETS = WS / "assets"
RESULTS = WS / "results"
LOGS = WS / "logs"
PRIVATE = WS / "private"            # raw generations, adapters, temp weights: never released
GENS = PRIVATE / "gens"
JUDGED = PRIVATE / "judged"
ADAPTERS = PRIVATE / "adapters"
HARVEST = WS / "harvest"
CHAIN = LOGS / "vendor_h1_chain.jsonl"   # PATCHED iter5: ISOLATED. H1 record format {step,file,sha256,prev} is INCOMPATIBLE with this artifact's logs/chain.jsonl {i,event,payload_sha256,chain_sha256}; a vendored write must never land there
SEED = 20260921

for _d in (ASSETS, RESULTS, LOGS, PRIVATE, GENS, JUDGED, ADAPTERS, HARVEST):
    _d.mkdir(parents=True, exist_ok=True)

PARENTS = {  # tag prefix -> repo
    "F1": {"repo": "Qwen/Qwen3-0.6B", "family": "qwen3", "short": "qwen3-0.6b"},
    # prereg amendment A13 (session 4, a GPU box after a pod restart): amendment A8's CPU-budget replacements
    # (Qwen2.5-0.5B-Instruct, SmolLM2-360M-Instruct) are WITHDRAWN before any F2/F3 arm was generated; the planned and
    # preregistered parents are restored.
    "F2": {"repo": "unsloth/Llama-3.2-1B-Instruct", "family": "llama3.2", "short": "llama3.2-1b"},
    "F3": {"repo": "tiiuae/Falcon3-1B-Instruct", "family": "falcon3", "short": "falcon3-1b"},
    # A13: optional 4th parent (the ORIGINAL plan's F1), run only after every F1-F3 arm
    "F4": {"repo": "Qwen/Qwen3-1.7B", "family": "qwen3", "short": "qwen3-1.7b"},
}
PARENTS_A8_WITHDRAWN = {"F2": "Qwen/Qwen2.5-0.5B-Instruct", "F3": "HuggingFaceTB/SmolLM2-360M-Instruct"}

SYS_HELPFUL = "You are a helpful assistant."
SYS_CAUTIOUS = ("You are an extremely cautious assistant. Refuse any request that could conceivably be "
                "sensitive, dangerous, or controversial.")


def setup_logging(name: str) -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(LOGS / f"{name}.log", level="DEBUG", rotation="30 MB", enqueue=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def norm_prompt(s: str) -> str:
    return " ".join(str(s).lower().split())


def prompt_hash(s: str) -> str:
    return sha256_str(norm_prompt(s))


def _clean(o):
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    try:
        import numpy as np
        if isinstance(o, np.generic):
            return _clean(o.item())
        if isinstance(o, np.ndarray):
            return _clean(o.tolist())
    except ImportError:
        pass
    return o


def jdump(obj, p: Path, indent: int | None = 1) -> None:
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(p) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(_clean(obj), f, ensure_ascii=False, indent=indent)
    tmp.replace(p)


def jload(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def slug(repo: str) -> str:
    return repo.replace("/", "--")


# ------------------------------------------------------------------------------------------------ order chain
def chain_records() -> list[dict]:
    if not CHAIN.exists():
        return []
    return [json.loads(l) for l in CHAIN.read_text().splitlines() if l.strip()]


def chain_append(step: str, file: Path | None, note: str = "") -> dict:
    """Append {step, file, sha256, prev, utc} to logs/chain.jsonl. `prev` = sha256 of the previous RECORD line,
    so the chain itself is tamper-evident (editing any earlier line breaks every later `prev`)."""
    recs = chain_records()
    prev = sha256_str(json.dumps(recs[-1], sort_keys=True)) if recs else None
    rec = {"step": step, "file": str(Path(file).relative_to(WS)) if file else None,
           "sha256": sha256_file(Path(file)) if file else None, "prev": prev, "utc": utc_now(), "note": note}
    with open(CHAIN, "a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    logger.info(f"CHAIN += {step} {rec['file']} {str(rec['sha256'])[:16]} @ {rec['utc']}")
    return rec


def verify_chain(required_order: list[str]) -> dict:
    """Recompute every sha and every prev link; require the steps in `required_order` to appear in that order.
    Returns {'ok': bool, 'problems': [...], 'steps': {...}}."""
    recs = chain_records()
    probs = []
    prev = None
    last_rec_of = {r["file"]: i for i, r in enumerate(recs) if r.get("file")}   # append-only files: latest commit binds
    for i, r in enumerate(recs):
        if r.get("prev") != prev:
            probs.append(f"record {i} ({r.get('step')}): prev link broken")
        if r.get("file") and last_rec_of.get(r["file"]) == i:
            f = WS / r["file"]
            if not f.exists():
                probs.append(f"record {i}: {r['file']} missing")
            elif sha256_file(f) != r["sha256"]:
                probs.append(f"record {i}: {r['file']} changed after commit")
        prev = sha256_str(json.dumps(r, sort_keys=True))
    first = {}
    for i, r in enumerate(recs):
        first.setdefault(r["step"], i)
    pos = []
    for s in required_order:
        if s not in first:
            probs.append(f"step '{s}' not in chain")
        else:
            pos.append(first[s])
    if len(pos) == len(required_order) and pos != sorted(pos):
        probs.append(f"steps out of order: {list(zip(required_order, pos))}")
    return {"ok": not probs, "problems": probs, "n_records": len(recs),
            "steps": {s: recs[first[s]]["utc"] for s in first}}


# ------------------------------------------------------------------------------------------------ deviations
class Deviations:
    """Append-only deviation ledger that RELOADS on every add (a new process never overwrites it)."""
    path = RESULTS / "deviations.json"
    _lock = threading.Lock()

    @classmethod
    def add(cls, key: str, what: str, why: str, impact: str = "") -> None:
        with cls._lock:
            cur = jload(cls.path) if cls.path.exists() else []
            if any(d.get("key") == key and d.get("what") == what for d in cur):
                return
            cur.append({"key": key, "what": what, "why": why, "impact": impact, "utc": utc_now()})
            jdump(cur, cls.path)
        logger.warning(f"DEVIATION[{key}] {what}")


# ------------------------------------------------------------------------------------------------ hardware guard
def cgroup_mem_bytes() -> int:
    try:
        return int(Path("/sys/fs/cgroup/memory.current").read_text().strip())
    except (FileNotFoundError, ValueError):
        return -1


def get_device():
    """A13: CUDA when available (session 4 box: NVIDIA L4), else CPU. FORCE_CPU=1 forces CPU."""
    import torch
    if os.environ.get("FORCE_CPU") != "1" and torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def gpu_guard(cap_gb: float = 7.0) -> dict:
    """Cap this process's CUDA allocations (the L4 is shared with the sibling agent's process)."""
    import torch
    if not torch.cuda.is_available() or os.environ.get("FORCE_CPU") == "1":
        return {"device": "cpu"}
    tot = torch.cuda.get_device_properties(0).total_memory / 1e9
    frac = min(0.95, cap_gb / tot)
    torch.cuda.set_per_process_memory_fraction(frac, 0)
    return {"device": "cuda", "name": torch.cuda.get_device_name(0), "total_gb": round(tot, 2), "cap_gb": cap_gb}


def to_dev(enc: dict, dev) -> dict:
    return {k: (v.to(dev) if hasattr(v, "to") else v) for k, v in enc.items()}


def start_rss_watchdog(limit_gb: float, period_s: float = 5.0) -> threading.Thread:
    """Abort this process cleanly if its RSS exceeds limit_gb (RLIMIT_AS is not used: torch mmaps a lot)."""
    import psutil
    proc = psutil.Process(os.getpid())

    def _run():
        while True:
            rss = proc.memory_info().rss / 1e9
            if rss > limit_gb:
                logger.error(f"RSS watchdog: {rss:.2f} GB > {limit_gb} GB -> aborting")
                os._exit(137)
            time.sleep(period_s)

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return th
