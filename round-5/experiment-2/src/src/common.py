"""Shared utilities for the blind held-out panel artifact (iteration 5, experiment 2).

BLINDNESS CONTRACT: nothing in this artifact computes a candidate score, a rank, a
correlation or a survivor.  This module therefore holds only I/O, hashing, the
append-only hash chain, Wilson intervals and small numerics.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

WS = Path(__file__).resolve().parent.parent
SRC = WS / "src"
RESULTS = WS / "results"
ARRAYS = WS / "arrays"
PRIVATE = WS / "private"
LOGS = WS / "logs"
ASSETS = WS / "assets"

RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D")
H1 = RUN / "3_invention_loop/iter_4/gen_art/gen_art_experiment_1"
P = RUN / "3_invention_loop/iter_4/gen_art/gen_art_experiment_2/prior_session_confirm_panel"
D1 = RUN / "3_invention_loop/iter_1/gen_art/gen_art_dataset_1"
D2 = RUN / "3_invention_loop/iter_2/gen_art/gen_art_dataset_1"
RESEARCH = RUN / "3_invention_loop/iter_4/gen_art/gen_art_research_1"
LC_JUDGE = RUN / "3_invention_loop/iter_1/gen_art/gen_art_experiment_3/lc_judge.py"
SHARED_HUB = RUN / ".shared_cache/hf/hub"
LEASE_DIR = RUN / "3_invention_loop/iter_5/gpu_lease"

SEED = "iter5_heldout_panel_v1"
CHAIN = LOGS / "chain.jsonl"
DEVIATIONS = RESULTS / "deviations.json"

for _d in (RESULTS, ARRAYS, PRIVATE, LOGS, ASSETS):
    _d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- logging
def setup_logging(name: str = "run") -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO",
               format="{time:HH:mm:ss}|{level:<7}|{message}", enqueue=False)
    logger.add(LOGS / f"{name}.log", rotation="30 MB", level="DEBUG", enqueue=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- json / hash
def jdump(path: Path, obj: Any) -> Path:
    """Atomic write: tmp + os.replace, so a parallel reader never sees a truncated file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=False, default=str))
    os.replace(tmp, path)
    return path


def jload(path: Path) -> Any:
    return json.loads(Path(path).read_text())


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_ids(ids: list[str]) -> str:
    """Canonical id-list digest used for every frozen item set here."""
    return sha256_text("\n".join(sorted(ids)))


def hash_rank_key(repo: str, seed: str = SEED) -> str:
    return hashlib.sha256((seed + "|" + repo).encode()).hexdigest()


# --------------------------------------------------------------------------- hash chain
def chain_read() -> list[dict]:
    if not CHAIN.exists():
        return []
    return [json.loads(ln) for ln in CHAIN.read_text().splitlines() if ln.strip()]


def chain_append(event: str, payload_path: Path | None, note: str = "",
                 payload_sha: str | None = None) -> dict:
    """Append-only.  chain_sha256 = sha256(prev_chain_sha256 + payload_sha256)."""
    recs = chain_read()
    prev = recs[-1]["chain_sha256"] if recs else ""
    if payload_sha is None:
        payload_sha = sha256_file(Path(payload_path)) if payload_path else sha256_text(note)
    rel = str(Path(payload_path).relative_to(WS)) if payload_path else None
    rec = {"i": len(recs), "utc": utc_now(), "event": event, "payload_path": rel,
           "payload_sha256": payload_sha, "prev_chain_sha256": prev,
           "chain_sha256": sha256_text(prev + payload_sha), "note": note}
    with open(CHAIN, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def chain_verify(check_payloads: bool = True) -> dict:
    recs = chain_read()
    prev = ""
    bad: list[dict] = []
    for r in recs:
        if r["prev_chain_sha256"] != prev:
            bad.append({"i": r["i"], "why": "prev_chain_sha256 mismatch"})
        if r["chain_sha256"] != sha256_text(prev + r["payload_sha256"]):
            bad.append({"i": r["i"], "why": "chain_sha256 mismatch"})
        if check_payloads and r["payload_path"]:
            fp = WS / r["payload_path"]
            if not fp.exists():
                bad.append({"i": r["i"], "why": f"payload missing: {r['payload_path']}"})
            elif sha256_file(fp) != r["payload_sha256"]:
                bad.append({"i": r["i"], "why": f"payload tampered: {r['payload_path']}"})
        prev = r["chain_sha256"]
    return {"n_records": len(recs), "ok": not bad, "failures": bad,
            "head": recs[-1]["chain_sha256"] if recs else None}


def chain_find(event_prefix: str) -> list[dict]:
    return [r for r in chain_read() if r["event"].startswith(event_prefix)]


# --------------------------------------------------------------------------- deviations
def deviation(code: str, detail: str, stage: str = "") -> dict:
    """Numbered, committed, never silent."""
    devs = jload(DEVIATIONS) if DEVIATIONS.exists() else {"deviations": []}
    n = len(devs["deviations"]) + 1
    rec = {"n": n, "code": code, "stage": stage, "detail": detail, "utc": utc_now()}
    devs["deviations"].append(rec)
    jdump(DEVIATIONS, devs)
    logger.warning(f"DEVIATION {n} [{code}] {detail}")
    return rec


# --------------------------------------------------------------------------- stats (instrument only)
def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    """Wilson score interval.  A property of the INSTRUMENT, never a candidate score."""
    if n <= 0:
        return (float("nan"), float("nan"), float("nan"))
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (p, max(0.0, c - hw), min(1.0, c + hw))


def atomic_append_jsonl(path: Path, rec: dict) -> None:
    """O_APPEND writes below PIPE_BUF are atomic on Linux; used by the panel manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(rec, default=str) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode())
    finally:
        os.close(fd)


def free_gb(path: Path = WS) -> float:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / 1e9


def wait_file(path: Path, timeout_s: float, poll: float = 5.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if Path(path).exists():
            return True
        time.sleep(poll)
    return Path(path).exists()
