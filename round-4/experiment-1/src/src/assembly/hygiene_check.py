#!/usr/bin/env python3
"""T6 HYGIENE: no raw harmful completion text may appear in any released file.

Draws 5 random harm items with a harmful-compliance label from the judged generations (seeded), takes a 48-character
substring from the middle of each response, and searches every released text file (everything under WS except
private/, the venvs and __pycache__) for it. Requires 0 hits. Writes results/hygiene_check.json with the item ids,
the tags and the hit counts only (never the text).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WS / "src"))
from common import RESULTS, SEED, jdump, utc_now  # noqa: E402

SKIP_DIRS = {"private", ".venv", ".venv_gpu", ".venv_ams", "__pycache__", ".git", "hf_cache"}
TEXT_EXT = {".json", ".jsonl", ".md", ".txt", ".log", ".out", ".csv", ".py", ".sh", ".yaml", ".yml", ".tex", ".svg"}


def released_files():
    for p in WS.rglob("*"):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(WS).parts):
            continue
        if p.suffix in TEXT_EXT and p.stat().st_size < 200_000_000:
            yield p


def main() -> None:
    judged = sorted((WS / "private" / "judged").glob("*.jsonl"))
    pool = []
    for f in judged:
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            jp = r.get("judge_primary") or {}
            if r.get("set") == "harm" and isinstance(jp, dict) and jp.get("harmful_content") and len(r.get("response", "")) > 120:
                pool.append((f.stem, r["item_id"], r["response"]))
    rng = np.random.default_rng(SEED)
    pick = [pool[i] for i in rng.choice(len(pool), size=min(5, len(pool)), replace=False)] if pool else []
    probes = [(t, i, resp[len(resp) // 2 - 24: len(resp) // 2 + 24]) for t, i, resp in pick]
    hits = {f"{t}:{i}": [] for t, i, _ in probes}
    n_files = 0
    for p in released_files():
        n_files += 1
        try:
            txt = p.read_text(errors="ignore")
        except OSError:
            continue
        for t, i, s in probes:
            if s and s in txt:
                hits[f"{t}:{i}"].append(str(p.relative_to(WS)))
    doc = {"utc": utc_now(), "n_harmful_pool": len(pool), "probes": [f"{t}:{i}" for t, i, _ in probes],
           "n_released_text_files_searched": n_files, "hits": hits,
           "pass": bool(probes) and all(len(v) == 0 for v in hits.values())}
    jdump(doc, RESULTS / "hygiene_check.json")
    print(json.dumps({k: v for k, v in doc.items() if k != "hits"}), {k: len(v) for k, v in hits.items()})


if __name__ == "__main__":
    main()
