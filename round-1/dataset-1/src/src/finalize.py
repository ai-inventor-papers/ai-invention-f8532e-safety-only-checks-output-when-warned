#!/usr/bin/env python3
"""Fold the judge gates and the final file hashes into prereg.json, then
re-hash it and print the SHA-256 that downstream artifacts must quote."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/finalize.log", rotation="10 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent


def canon(o: Any) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@logger.catch(reraise=True)
def main() -> None:
    pre = json.loads((ROOT / "prereg.json").read_text())

    jv = ROOT / "judge_validation.json"
    if jv.exists():
        j = json.loads(jv.read_text())
        pre["judge_validation"] = {
            "raters": j.get("raters"),
            "spend_usd": j.get("spend_usd"),
            "budget_exhausted": j.get("budget_exhausted"),
            "cohens_kappa": j.get("cohens_kappa"),
            "gates": j.get("gates"),
            "n_gates_passed": j.get("n_gates_passed"),
            "n_gates_failed": j.get("n_gates_failed"),
            "n_gates_not_evaluated": j.get("n_gates_not_evaluated"),
            "judge_validation_sha256": hashlib.sha256(jv.read_bytes()).hexdigest(),
        }
        logger.info(f"judge gates folded in: {j.get('n_gates_passed')} passed, "
                    f"{j.get('n_gates_failed')} failed, {j.get('n_gates_not_evaluated')} not evaluated")
    else:
        pre["judge_validation"] = {"status": "NOT_EVALUATED", "reason": "judge_validation.json absent at finalize time"}
        logger.warning("judge_validation.json absent -- recorded as NOT_EVALUATED")

    for f in ["data_out.json", "heldout_cells.json", "templates.json", "rubric.md", "full_data_out.json", "data.py",
              "verification_report.json", "judge_validation.json", "sources_manifest.json"]:
        p = ROOT / f
        if p.exists():
            pre["file_hashes"][f] = hashlib.sha256(p.read_bytes()).hexdigest()

    pc = ROOT / "results/placebo_calibration.json"
    if pc.exists():
        c = json.loads(pc.read_text())
        pre["placebo_calibration_full"] = {k: v for k, v in c.items() if k != "per_item"}
        pre["placebo_calibration_full"]["per_item_distances_ship_as"] = "metadata_levenshtein_to_benign_prefix"
        pre["file_hashes"]["results/placebo_calibration.json"] = hashlib.sha256(pc.read_bytes()).hexdigest()
        logger.info(f"placebo gate {c['status']}: median ratio {c['median_ratio']}, mean ratio {c['mean_ratio']}")

    qc = ROOT / "results/qc_exclusions.json"
    if qc.exists():
        q = json.loads(qc.read_text())
        pre["qc_exclusions"] = {k: v for k, v in q.items() if k != "per_item"}
        pre["split"]["confirmatory_n_after_qc_exclusion"] = q["confirmatory_n_after"]
        pre["file_hashes"]["results/qc_exclusions.json"] = hashlib.sha256(qc.read_bytes()).hexdigest()
        logger.info(f"qc exclusions folded in: confirmatory n {q['confirmatory_n_before']} -> {q['confirmatory_n_after']}")

    vr = ROOT / "verification_report.json"
    if vr.exists():
        v = json.loads(vr.read_text())
        pre["verification_summary"] = {"n_checks": v["n_checks"], "n_pass": v["n_pass"], "n_fail": v["n_fail"],
                                       "failed": [c["criterion"] for c in v["checks"] if c["status"] == "FAIL"]}

    (ROOT / "prereg.json").write_text(json.dumps(pre, indent=2, ensure_ascii=False))
    digest = hashlib.sha256(canon(pre)).hexdigest()
    (ROOT / "prereg.sha256").write_text(
        digest + "  prereg.json (sha256 over json.dumps(obj, sort_keys=True, separators=(',',':'), ensure_ascii=False).encode('utf-8'))\n")
    logger.info("=" * 78)
    logger.info(f"FINAL PREREG SHA-256: {digest}")
    logger.info("=" * 78)


if __name__ == "__main__":
    main()
