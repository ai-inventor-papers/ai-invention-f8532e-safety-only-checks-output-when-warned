"""Cross-artifact VRAM lease on the single shared NVIDIA L4 (23,034 MiB).

Three artifacts of iteration 5 share one card.  A lease record is
{pid, artifact, mib, utc}; stale records (older than STALE_MIN minutes AND whose
pid is dead) are reclaimed.  The lease is held ONLY while weights are on the device.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from common import LEASE_DIR, LOGS, WS, utc_now

CEILING_MIB = 15800          # 16,380 MiB RTX 2000 Ada, ~580 MiB left for driver/context.
                             # The artifact plan assumed a 23,034 MiB L4 and a 22,500 ceiling;
                             # nvidia-smi on this pod reports 16,380 MiB. See deviation D02.
STALE_MIN = 20
WAIT_TIMEOUT_S = 30 * 60
POLL_S = 10
# PER-ARTIFACT CAP. This artifact DECLARES 7.5 GB of VRAM, and the run kills a
# process tree that exceeds its declaration. The panel sweep and the Part-B arms
# are separate processes, so without this cap each could hold a 7.5 GB lease at
# once (15 GB total) while the physical ceiling above still allowed it. Every
# lease is stamped with this workspace; the SUM over all live leases from this
# workspace must stay <= ARTIFACT_CAP_MIB. Other artifacts only count against the
# physical ceiling.
ARTIFACT_CAP_MIB = 7500
WS_STAMP = str(WS)
MIRROR = LOGS / "lease_mirror.jsonl"


def _paths() -> tuple[Path, Path]:
    LEASE_DIR.mkdir(parents=True, exist_ok=True)
    return LEASE_DIR / "leases.json", LEASE_DIR / "leases.lock"


def _alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True


def _age_min(utc: str) -> float:
    try:
        t = datetime.strptime(utc, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 1e9
    return (datetime.now(timezone.utc) - t).total_seconds() / 60.0


def _live(records: list[dict]) -> list[dict]:
    """Drop a record as soon as its pid is gone. All co-tenant artifacts run on this one pod,
    so os.kill(pid, 0) is authoritative; waiting 20 min for a DEAD holder (the old rule) stalled
    every waiter after a killed or crashed visit. Records of LIVE pids are kept whatever their age."""
    return [r for r in records if _alive(r.get("pid", -1))]


def _mirror(action: str, rec: dict) -> None:
    with open(MIRROR, "a") as f:
        f.write(json.dumps({"action": action, "utc": utc_now(), **rec}) + "\n")


def _mutate(fn):
    """Run fn(records) -> (records, result) under an exclusive flock."""
    lj, lk = _paths()
    lk.touch(exist_ok=True)
    with open(lk, "r+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            recs = json.loads(lj.read_text()) if lj.exists() else []
            if not isinstance(recs, list):
                recs = []
            recs = _live(recs)
            recs, result = fn(recs)
            tmp = lj.with_suffix(f".tmp{os.getpid()}")
            tmp.write_text(json.dumps(recs, indent=2))
            os.replace(tmp, lj)
            return result
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def _ours_used(recs: list[dict]) -> int:
    """MiB held by OTHER live processes of THIS workspace (this artifact)."""
    return sum(int(r.get("mib", 0)) for r in recs
               if r.get("pid") != os.getpid() and r.get("ws") == WS_STAMP
               and not r.get("waiting"))


def try_acquire(mib: int, artifact: str, since: str | None = None) -> dict | None:
    """Grant if it fits under the physical ceiling AND this artifact's cap AND no OLDER waiter
    of this workspace is queued (FIFO). Without FIFO, a sweep that releases and immediately
    re-acquires between tags starves every other process of this artifact."""
    me = os.getpid()
    def fn(recs):
        holders = [r for r in recs if not r.get("waiting")]
        used = sum(int(r.get("mib", 0)) for r in holders if r.get("pid") != me)
        ours = _ours_used(holders)
        older = [r for r in recs if r.get("waiting") and r.get("ws") == WS_STAMP
                 and r.get("pid") != me and since is not None
                 and str(r.get("since", "")) < since]
        if used + mib <= CEILING_MIB and ours + mib <= ARTIFACT_CAP_MIB and not older:
            recs = [r for r in recs if not (r.get("waiting") and r.get("pid") == me)]
            rec = {"pid": me, "artifact": artifact, "mib": int(mib),
                   "utc": utc_now(), "ws": WS_STAMP}
            recs.append(rec)
            return recs, rec
        if since is not None and not any(r.get("waiting") and r.get("pid") == me for r in recs):
            recs.append({"pid": me, "artifact": artifact, "mib": int(mib), "utc": utc_now(),
                         "ws": WS_STAMP, "waiting": True, "since": since})
        return recs, None
    return _mutate(fn)


def _withdraw_waiter() -> None:
    me = os.getpid()
    _mutate(lambda recs: ([r for r in recs if not (r.get("waiting") and r.get("pid") == me)], None))


def blocked_by_own_artifact(mib: int) -> bool:
    """True if granting `mib` would push THIS artifact past its own declaration."""
    def fn(recs):
        return recs, _ours_used(recs) + mib > ARTIFACT_CAP_MIB
    return bool(_mutate(fn))


def release(artifact: str) -> None:
    def fn(recs):
        keep = [r for r in recs if not (r.get("pid") == os.getpid() and r.get("artifact") == artifact)]
        return keep, None
    _mutate(fn)
    _mirror("release", {"pid": os.getpid(), "artifact": artifact})


def heartbeat(artifact: str) -> None:
    """Refresh the utc of our own record so a long visit is never reclaimed."""
    def fn(recs):
        for r in recs:
            if r.get("pid") == os.getpid() and r.get("artifact") == artifact:
                r["utc"] = utc_now()
        return recs, None
    _mutate(fn)


@contextmanager
def vram_lease(mib: int = 7500, artifact: str = "exp3_panel", timeout_s: int = WAIT_TIMEOUT_S):
    """Block (polling) until `mib` fits under the ceiling, then yield a dict describing the grant."""
    t0 = time.time()
    since = f"{utc_now()}#{os.getpid()}"   # FIFO ticket (ISO utc sorts lexically)
    rec = None
    while True:
        rec = try_acquire(mib, artifact, since)
        if rec is not None:
            break
        own = blocked_by_own_artifact(mib)
        # The 30-min 'proceed anyway at half batch' fallback exists for CROSS-artifact
        # contention only. If the blocker is THIS artifact's other process, proceeding
        # would exceed our own 7.5 GB declaration, so we keep waiting instead.
        if time.time() - t0 >= timeout_s and not own:
            break
        logger.info(f"lease: waiting for {mib} MiB (ceiling {CEILING_MIB}, artifact cap "
                    f"{ARTIFACT_CAP_MIB}, blocked_by_own_artifact={own})")
        time.sleep(POLL_S)
    granted = rec is not None
    if not granted:
        _withdraw_waiter()
        from common import deviation
        deviation("lease_timeout_proceeded",
                  f"no VRAM lease for {mib} MiB within {timeout_s}s; proceeding at HALF batch", "lease")
        rec = {"pid": os.getpid(), "artifact": artifact, "mib": mib, "utc": utc_now(),
               "granted": False}
    _mirror("acquire", {**rec, "granted": granted})
    try:
        yield {"granted": granted, "mib": mib, "half_batch": not granted}
    finally:
        if granted:
            release(artifact)


def snapshot() -> list[dict]:
    lj, _ = _paths()
    if not lj.exists():
        return []
    try:
        return _live(json.loads(lj.read_text()))
    except (json.JSONDecodeError, OSError):
        return []
