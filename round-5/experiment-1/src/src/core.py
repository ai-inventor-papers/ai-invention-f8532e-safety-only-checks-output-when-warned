#!/usr/bin/env python3
"""Conventions shared by every phase: bands, folds, hash chain, canonical JSON.

INV-4  Bands are ALWAYS a fraction of depth, never a layer index.
INV-2  Stage order is proved by a SHA-256 hash chain.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np

N_BANDS = 6

# --------------------------------------------------------------------------- #
# bands  (INV-4)                                                               #
# --------------------------------------------------------------------------- #


def band_indices(n_layers: int, b: int, *, offset: int = 0) -> tuple[int, int]:
    """Hidden-state index range [lo, hi] (inclusive) covered by band b in 1..6.

    Hidden states are indexed 0..L where 0 is the embedding output and index i
    is the output of block i.  Band b covers
        lo(b) = floor((b-1)*L/6) + 1
        hi(b) = floor(b*L/6)
    so the six bands are contiguous, non-overlapping, and cover 1..L exactly.
    Index 0 (embeddings) belongs to no band.

    `offset` is the +/-1 band-boundary jitter used as a stability draw; it moves
    the interior boundaries only and is clipped so the band stays non-empty and
    inside 1..L.
    """
    if not 1 <= b <= N_BANDS:
        raise ValueError(f"band must be in 1..{N_BANDS}, got {b}")
    if n_layers < N_BANDS:
        raise ValueError(f"n_layers={n_layers} is too small for {N_BANDS} bands")
    lo = (b - 1) * n_layers // N_BANDS + 1
    hi = b * n_layers // N_BANDS
    if offset:
        if b > 1:
            lo = lo + offset
        if b < N_BANDS:
            hi = hi + offset
        lo = max(1, min(lo, n_layers))
        hi = max(lo, min(hi, n_layers))
    return int(lo), int(hi)


def all_bands(n_layers: int, *, offset: int = 0) -> list[tuple[int, int]]:
    return [band_indices(n_layers, b, offset=offset) for b in range(1, N_BANDS + 1)]


def band_mean(arr: np.ndarray, n_layers: int, b: int, *, offset: int = 0) -> np.ndarray:
    """Mean over the hidden-state indices of band b.

    arr : (n_items, L+1, d) -> returns (n_items, d), float32.
    """
    lo, hi = band_indices(n_layers, b, offset=offset)
    if arr.shape[1] < hi + 1:
        raise ValueError(f"array has {arr.shape[1]} hidden states, band {b} needs index {hi}")
    return np.asarray(arr[:, lo : hi + 1, :], dtype=np.float32).mean(axis=1)


# --------------------------------------------------------------------------- #
# folds  (S1.1c)                                                               #
# --------------------------------------------------------------------------- #


def fold_of(item_id: str | int, salt: str) -> int:
    """Deterministic 0/1 fold from sha256(salt || item_id). Never depends on order."""
    h = hashlib.sha256(f"{salt}|{item_id}".encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 2


def fold_masks(item_ids: Sequence[str | int], salt: str) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks (fold A, fold B) over the supplied item ids."""
    f = np.array([fold_of(i, salt) for i in item_ids], dtype=int)
    return f == 0, f == 1


# --------------------------------------------------------------------------- #
# vector helpers                                                               #
# --------------------------------------------------------------------------- #


def unit(v: np.ndarray, *, eps: float = 1e-12) -> np.ndarray:
    v = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(v))
    if not np.isfinite(n) or n < eps:
        return np.zeros_like(v)
    return v / n


def diff_of_means(x: np.ndarray, pos: np.ndarray, neg: np.ndarray) -> np.ndarray:
    """Unit-normalised difference of class means. x: (n_items, d); pos/neg boolean."""
    if pos.sum() == 0 or neg.sum() == 0:
        return np.zeros(x.shape[1], dtype=np.float64)
    return unit(np.asarray(x[pos], dtype=np.float64).mean(0) - np.asarray(x[neg], dtype=np.float64).mean(0))


def cohens_d_pooled(a: np.ndarray, b: np.ndarray) -> float:
    """1-D Cohen's d with the AMS pooled-std convention sqrt((var+ + var-)/2)."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if a.size < 2 or b.size < 2:
        return float("nan")
    sd = math.sqrt((float(a.var(ddof=1)) + float(b.var(ddof=1))) / 2.0)
    if not np.isfinite(sd) or sd <= 0.0:
        return float("nan")
    return float((a.mean() - b.mean()) / sd)


# --------------------------------------------------------------------------- #
# canonical json + hash chain  (INV-2)                                         #
# --------------------------------------------------------------------------- #


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=True, default=_jdefault)


def _jdefault(o: Any) -> Any:
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, Path):
        return str(o)
    raise TypeError(f"not JSON serialisable: {type(o)}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path, *, head_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        if head_bytes is None:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        else:
            h.update(fh.read(head_bytes))
    return h.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def write_json(path: Path, obj: Any, *, indent: int = 1) -> str:
    """Write JSON and return the sha256 of its CANONICAL serialisation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=indent, default=_jdefault, allow_nan=True))
    return sha256_text(canonical_json(obj))


def chain_append(chain_path: Path, stage: str, file_path: Path, digest: str,
                 extra: dict | None = None) -> dict:
    rec = {
        "stage": stage,
        "file": file_path.name,
        "sha256": digest,
        "utc": utc_now(),
        "mtime": float(file_path.stat().st_mtime) if file_path.exists() else None,
    }
    if extra:
        rec.update(extra)
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    with chain_path.open("a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def verify_chain(chain_path: Path, results_dir: Path, expected_order: Sequence[str]) -> dict:
    """Verify: every recorded digest still matches the file on disk, the stages
    appear in `expected_order`, and both UTC timestamps and file mtimes are monotone."""
    if not chain_path.exists():
        return {"ok": False, "reason": "no hashchain.jsonl"}
    recs = [json.loads(ln) for ln in chain_path.read_text().splitlines() if ln.strip()]
    checks: list[dict] = []
    ok = True
    for r in recs:
        f = results_dir / r["file"]
        if not f.exists():
            checks.append({"file": r["file"], "ok": False, "reason": "missing"})
            ok = False
            continue
        try:
            cur = sha256_text(canonical_json(json.loads(f.read_text())))
        except (json.JSONDecodeError, UnicodeDecodeError):
            cur = sha256_file(f)
        good = cur == r["sha256"]
        checks.append({"file": r["file"], "ok": good,
                       "recorded": r["sha256"][:16], "current": cur[:16]})
        ok = ok and good
    stages = [r["stage"] for r in recs]
    order_ok = _subsequence(expected_order, stages)
    times = [r["utc"] for r in recs]
    mono_utc = all(times[i] <= times[i + 1] for i in range(len(times) - 1))
    mts = [r.get("mtime") for r in recs if r.get("mtime") is not None]
    mono_mtime = all(mts[i] <= mts[i + 1] + 1e-6 for i in range(len(mts) - 1))
    return {
        "ok": bool(ok and order_ok and mono_utc and mono_mtime),
        "digests_ok": ok,
        "stage_order_ok": order_ok,
        "monotone_utc": mono_utc,
        "monotone_mtime": mono_mtime,
        "stages_seen": stages,
        "expected_order": list(expected_order),
        "n_records": len(recs),
        "checks": checks,
    }


def _subsequence(needle: Sequence[str], haystack: Sequence[str]) -> bool:
    it = iter(haystack)
    return all(any(h == n for h in it) for n in needle)


# --------------------------------------------------------------------------- #
# open() audit shim  (INV-3, S3.1)                                             #
# --------------------------------------------------------------------------- #


class OpenAudit:
    """Wrap builtins.open, io.open AND os.open; record every path opened, abort on
    forbidden paths.

    HARDENED (backwards-compatible extension): the original shim patched only
    `builtins.open`, which `pathlib.Path.read_text`/`Path.open` and `numpy.load`
    do not always go through at the point of syscall -- `pathlib` calls `io.open`
    directly by module attribute, and code that opens a raw file descriptor
    (some numpy/mmap paths) calls `os.open`. This class now patches all three
    entry points, in a single `with OpenAudit(...) as audit:` block, and restores
    all three on exit. Constructor signature and public attributes
    (`log_path`, `forbidden`, `records`, `violations`) are unchanged, so any
    existing caller of the old (builtins-only) shim keeps working unmodified.
    """

    def __init__(self, log_path: Path, forbidden_substrings: Iterable[str]) -> None:
        self.log_path = Path(log_path)
        self.forbidden = [s for s in forbidden_substrings]
        self.records: list[str] = []
        self._orig = None          # kept for backwards compatibility (== builtins.open original)
        self._origs: dict[str, Any] = {}
        self.violations: list[str] = []

    def _make_audited_open(self, orig):  # noqa: ANN001, ANN202
        """Wrap a builtins/io-style open(file, *a, **kw)."""
        rec = self.records
        forb = self.forbidden
        viol = self.violations

        def _audited(file, *a, **kw):  # noqa: ANN001, ANN202
            s = _path_str(file)
            rec.append(s)
            for bad in forb:
                if bad in s:
                    viol.append(s)
                    raise PermissionError(f"INV-3 VIOLATION: phase S3 tried to open {s}")
            return orig(file, *a, **kw)

        return _audited

    def _make_audited_os_open(self, orig):  # noqa: ANN001, ANN202
        """Wrap os.open(path, flags, mode=...) -> low-level fd open, different signature."""
        rec = self.records
        forb = self.forbidden
        viol = self.violations

        def _audited(path, flags, *a, **kw):  # noqa: ANN001, ANN202
            s = _path_str(path)
            rec.append(f"os.open:{s}")
            for bad in forb:
                if bad in s:
                    viol.append(s)
                    raise PermissionError(f"INV-3 VIOLATION: phase S3 tried to os.open {s}")
            return orig(path, flags, *a, **kw)

        return _audited

    def __enter__(self) -> "OpenAudit":
        import builtins
        import io as _io

        self._origs = {
            "builtins.open": builtins.open,
            "io.open": _io.open,
            "os.open": os.open,
        }
        self._orig = self._origs["builtins.open"]  # backwards-compatible alias

        builtins.open = self._make_audited_open(self._origs["builtins.open"])
        _io.open = self._make_audited_open(self._origs["io.open"])
        os.open = self._make_audited_os_open(self._origs["os.open"])
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        import builtins
        import io as _io

        if self._origs:
            builtins.open = self._origs["builtins.open"]
            _io.open = self._origs["io.open"]
            os.open = self._origs["os.open"]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("\n".join(self.records) + "\n")


def _path_str(file: Any) -> str:
    try:
        s = os.fspath(file)
        if isinstance(s, bytes):
            s = s.decode("utf-8", "replace")
        return s
    except TypeError:
        return repr(file)


# --------------------------------------------------------------------------- #
# GPU lease  (S2.4)                                                            #
# --------------------------------------------------------------------------- #

LEASE_DIR = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gpu_lease")
LEASE_SAFETY_MARGIN_MIB = 600
STALE_AGE_S = 20 * 60


def _alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        return False
    return True


def _device0_total_mib() -> int | None:
    """Total VRAM of CUDA device 0 in MiB, via nvidia-smi first, then torch.

    Returns None if neither is available (e.g. no GPU visible at all).
    """
    import subprocess

    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits",
             "-i", "0"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        line = out.stdout.strip().splitlines()[0].strip()
        return int(float(line))
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    try:
        import torch

        if torch.cuda.is_available():
            total_bytes = torch.cuda.get_device_properties(0).total_memory
            return int(total_bytes // (1024 * 1024))
    except Exception:  # noqa: BLE001 - torch import/CUDA probing must never crash a lease
        pass
    return None


def _record_age_s(rec: dict, now: float) -> float:
    """Age of a lease record in seconds, from 'ts' (epoch float) if present,
    else parsed from 'utc' (ISO-8601 'Z' string). Unparseable -> +inf (treat as
    arbitrarily old, so a dead-pid record with no usable timestamp is reclaimable)."""
    ts = rec.get("ts")
    if ts is not None:
        try:
            return max(0.0, now - float(ts))
        except (TypeError, ValueError):
            pass
    utc = rec.get("utc")
    if utc:
        try:
            s = str(utc).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return max(0.0, now - dt.timestamp())
        except (ValueError, TypeError):
            pass
    return float("inf")


class GpuLease:
    """flock-guarded co-tenancy lease. Never held across a download.

    card_mib: if None (default), computed fresh on every acquire attempt as
    (device-0 total VRAM MiB) - LEASE_SAFETY_MARGIN_MIB, so the cap always
    matches the actual card this process sees, never a stale hardcoded value.
    """

    def __init__(self, mib: int, artifact: str, *, timeout_s: int = 1800,
                 card_mib: int | None = None, lease_dir: Path | None = None) -> None:
        self.mib = int(mib)
        self.artifact = artifact
        self.timeout_s = timeout_s
        self._card_mib_fixed = card_mib
        self.card_mib = card_mib  # populated lazily below if None
        self.lease_dir = Path(lease_dir) if lease_dir is not None else LEASE_DIR
        self.acquired = False
        self.deviation: str | None = None

    def _resolve_card_mib(self) -> int:
        if self._card_mib_fixed is not None:
            return int(self._card_mib_fixed)
        total = _device0_total_mib()
        if total is None:
            # No way to query the card; fall back to a conservative default
            # rather than crash the lease. This should not happen on a
            # machine with a visible CUDA device.
            self.deviation = (self.deviation or "") + " card VRAM unqueryable; used 8000 MiB fallback cap"
            return 8000
        return max(0, int(total) - LEASE_SAFETY_MARGIN_MIB)

    def _attempt(self) -> bool:
        import fcntl

        self.card_mib = self._resolve_card_mib()

        self.lease_dir.mkdir(parents=True, exist_ok=True)
        lock = self.lease_dir / "leases.lock"
        leases = self.lease_dir / "leases.json"
        with lock.open("a+") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX)
            try:
                try:
                    recs = json.loads(leases.read_text()) if leases.exists() else []
                except (json.JSONDecodeError, OSError):
                    recs = []
                now = time.time()
                # Drop a record ONLY if its pid is dead AND its age exceeds
                # STALE_AGE_S. Records from other artifacts may carry only
                # 'utc' (no 'ts'); _record_age_s falls back to parsing that.
                recs = [r for r in recs
                        if _alive(r.get("pid", -1)) or _record_age_s(r, now) <= STALE_AGE_S]
                used = sum(int(r.get("mib", 0)) for r in recs if not r.get("waiting"))  # queued reservations of other artifacts are not in use
                if used + self.mib <= self.card_mib:
                    recs.append({"pid": os.getpid(), "artifact": self.artifact,
                                 "mib": self.mib, "ts": now, "utc": utc_now()})
                    tmp = leases.with_suffix(".json.tmp")
                    tmp.write_text(json.dumps(recs, indent=1))
                    tmp.replace(leases)
                    try:
                        os.chmod(leases, 0o666)
                    except OSError:
                        pass
                    return True
                return False
            finally:
                fcntl.flock(fh, fcntl.LOCK_UN)

    def acquire(self) -> bool:
        t0 = time.time()
        rng = np.random.default_rng(os.getpid())
        while time.time() - t0 < self.timeout_s:
            try:
                if self._attempt():
                    self.acquired = True
                    return True
            except OSError as exc:  # lease dir unwritable -> proceed, log
                self.deviation = f"lease unavailable ({exc}); proceeding without a lease"
                return False
            time.sleep(20.0 + float(rng.uniform(0, 8)))
        self.deviation = "lease timeout after 30 min; proceeding at HALF BATCH (F2)"
        return False

    def release(self) -> None:
        if not self.acquired:
            return
        import fcntl

        lock = self.lease_dir / "leases.lock"
        leases = self.lease_dir / "leases.json"
        try:
            with lock.open("a+") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                try:
                    recs = json.loads(leases.read_text()) if leases.exists() else []
                    recs = [r for r in recs if r.get("pid") != os.getpid()]
                    tmp = leases.with_suffix(".json.tmp")
                    tmp.write_text(json.dumps(recs, indent=1))
                    tmp.replace(leases)
                finally:
                    fcntl.flock(fh, fcntl.LOCK_UN)
        except OSError:
            pass
        self.acquired = False

    def __enter__(self) -> "GpuLease":
        self.acquire()
        return self

    def __exit__(self, *exc) -> None:  # noqa: ANN002
        self.release()
