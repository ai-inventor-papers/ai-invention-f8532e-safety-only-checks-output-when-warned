#!/usr/bin/env python3
"""Append a prereg AMENDMENT record (own hash, stated reason) and chain it (stage S1-amend).

Usage: .venv_gpu/bin/python src/amend.py <amendments.json-fragment>
Amendments never alter results/prereg.json (it stays byte-identical to its hash)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import canonical_json, chain_append, sha256_text, utc_now  # noqa: E402

RES = WS / "results"


def main() -> None:
    new = json.loads(Path(sys.argv[1]).read_text())
    path = RES / "prereg_amendments.json"
    doc = json.loads(path.read_text()) if path.exists() else {"prereg_sha256": (RES / "prereg.sha256").read_text().strip(), "amendments": []}
    for a in new:
        a = dict(a, utc=utc_now())
        a["sha256"] = sha256_text(canonical_json({k: v for k, v in a.items() if k != "sha256"}))
        doc["amendments"].append(a)
    doc["note"] = "cumulative VIEW (not chained); the chained, immutable records are prereg_amendments_b*.json"
    path.write_text(canonical_json(doc))
    n_b = len(list(RES.glob("prereg_amendments_b*.json"))) + 1
    bpath = RES / f"prereg_amendments_b{n_b}.json"
    bdoc = {"prereg_sha256": doc["prereg_sha256"], "batch": f"b{n_b}", "amendments": doc["amendments"][-len(new):]}
    bpath.write_text(canonical_json(bdoc))
    digest = sha256_text(canonical_json(json.loads(bpath.read_text())))
    chain_append(RES / "hashchain.jsonl", "S1-amend", bpath, digest, extra={"ids": [a["id"] for a in new]})
    print("amendments now", len(doc["amendments"]), bpath.name, digest)


if __name__ == "__main__":
    main()
