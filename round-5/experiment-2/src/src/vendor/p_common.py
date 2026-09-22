"""Shared paths, logging, hashing and the hash chain for the iteration-4 CONFIRMATION panel
(adapted from the iteration-3 held-out panel code, src/ref_i3/common.py)."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

WS = Path(__file__).resolve().parents[2]   # PATCHED iter5: vendored at src/vendor/ (was parents[1] -> src/)
RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
LANEC = RUN / "iter_1/gen_art/gen_art_experiment_3"
H2 = RUN / "iter_2/gen_art/gen_art_experiment_1"
D2 = RUN / "iter_2/gen_art/gen_art_dataset_1"
D1 = RUN / "iter_1/gen_art/gen_art_dataset_1"
STRAT = RUN / "iter_4/gen_strat/gen_strat_1/.terminal_claude_agent_struct_out.json"
I3 = RUN / "iter_3/gen_art/gen_art_experiment_1"
PLAN = RUN / "iter_4/gen_plan/gen_plan_experiment_2/.terminal_claude_agent_struct_out.json"

ASSETS = WS / "assets"
RESULTS = WS / "results"
LOGS = WS / "logs"
PRIVATE = WS / "private"          # raw generations: never released
GENS = PRIVATE / "gens"
JUDGED = PRIVATE / "judged"       # full judged rows incl. text (private); labels-only copy is released
HARVEST = WS / "harvest"
HF_CACHE = WS / "hf_cache"
HASH_CHAIN = WS / "hash_chain.jsonl"
SEED = "iter4_confirm_panel_v1"

for _d in (ASSETS, RESULTS, LOGS, PRIVATE, GENS, JUDGED, HARVEST, HF_CACHE):
    _d.mkdir(parents=True, exist_ok=True)


def setup_logging(name: str) -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
    logger.add(LOGS / f"{name}.log", level="DEBUG", rotation="50 MB", enqueue=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def hash_rank_key(repo_id: str) -> str:
    """The seeded SHA-256 rank key: sha256(seed + repo_id), ascending order = draw order."""
    return sha256_str(SEED + repo_id)


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
    except Exception:  # noqa: BLE001
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


def chain_append(file: Path, note: str) -> dict:
    """Append {file, sha256, utc, note} to hash_chain.jsonl; also write <file>.sha256."""
    file = Path(file)
    h = sha256_file(file)
    rec = {"file": str(file.relative_to(WS)), "sha256": h, "utc": utc_now(), "note": note}
    Path(str(file) + ".sha256").write_text(h + "\n")
    with open(HASH_CHAIN, "a") as f:
        f.write(json.dumps(rec) + "\n")
    logger.info(f"HASH-CHAIN += {rec['file']} {h[:16]} @ {rec['utc']} ({note})")
    return rec


def chain_records() -> list[dict]:
    if not HASH_CHAIN.exists():
        return []
    return [json.loads(l) for l in HASH_CHAIN.read_text().splitlines() if l.strip()]


class Deviations:
    """Append-only deviation ledger that RELOADS on every add (iter-2 bug: a new process overwrote it)."""
    path = RESULTS / "deviations.json"

    @classmethod
    def add(cls, key: str, what: str, why: str, impact: str = "") -> None:
        cur = jload(cls.path) if cls.path.exists() else []
        cur.append({"key": key, "what": what, "why": why, "impact": impact, "utc": utc_now()})
        jdump(cur, cls.path)
        logger.warning(f"DEVIATION[{key}] {what}")
