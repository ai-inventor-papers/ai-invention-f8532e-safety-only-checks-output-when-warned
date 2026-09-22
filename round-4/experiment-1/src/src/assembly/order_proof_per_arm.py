#!/usr/bin/env python3
"""Per-arm ORDER PROOF for the staged chain (A11/A13): for every harvested arm, the classification record that first
covered it must be committed BEFORE its harvest started, and the graded truth of that stage must precede the
classification. The prereg and every amendment must precede the first generation of the arm's stage.
Writes results/order_proof_per_arm.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WS / "src"))
from common import HARVEST, RESULTS, chain_records, jdump, jload, sha256_file, utc_now, verify_chain  # noqa: E402


def main() -> None:
    recs = chain_records()
    v = verify_chain(["prereg", "graded_truth", "classification"])
    cover: dict[str, dict] = {}
    truth_utc: dict[str, str] = {}
    for r in recs:
        if r["step"] == "graded_truth" and r.get("file"):
            truth_utc[Path(r["file"]).stem.replace("graded_truth_", "")] = r["utc"]
        if r["step"] != "classification" or not r.get("file"):
            continue
        f = WS / r["file"]
        if not f.exists() or sha256_file(f) != r["sha256"]:
            continue
        stage = Path(r["file"]).stem.replace("classification_", "")
        for q in jload(f)["pairs"]:
            if q.get("kind") in ("constructed", "harvested_regen") and q.get("observed_class") not in (None, "UNSCORED"):
                for t in (q["parent"], q["child"]):
                    cover.setdefault(t, {"stage": stage, "classification_utc": r["utc"], "truth_utc": truth_utc.get(stage)})
    last_amend = max((r["utc"] for r in recs if r["step"] in ("prereg", "prereg_amendment")), default=None)
    rows, bad = [], []
    for d in sorted(HARVEST.iterdir()):
        if not (d / "DONE").exists() or not (d / "meta.json").exists():
            continue
        m = jload(d / "meta.json")
        start = m.get("harvest_utc_start")
        c = cover.get(d.name)
        ok = bool(c and start and c["truth_utc"] and c["truth_utc"] < c["classification_utc"] < start)
        rows.append({"tag": d.name, "harvest_utc_start": start, **(c or {"stage": None}), "ok": ok})
        if not ok:
            bad.append(d.name)
    doc = {"utc": utc_now(), "chain_verifies": v["ok"], "chain_problems": v["problems"], "n_records": len(recs),
           "last_prereg_or_amendment_utc": last_amend, "n_harvested_arms": len(rows), "n_ok": len(rows) - len(bad),
           "violations": bad, "all_ok": v["ok"] and not bad, "per_arm": rows}
    jdump(doc, RESULTS / "order_proof_per_arm.json")
    print(f"per-arm order proof: {doc['n_ok']}/{doc['n_harvested_arms']} ok; chain verifies {v['ok']}; violations {bad}")


if __name__ == "__main__":
    main()
