"""Behavioural items = Lane C gt_harm + gt_benign (same ids, same order) + reserved_54 unsafe + safe.

Writes assets/behaviour_items.json and records every source file's SHA-256 in results/provenance.json.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ASSETS, D1, D2, H2, LANEC, RESULTS, STRAT, jdump, jload, setup_logging,  # noqa: E402
                    sha256_file, utc_now)
from loguru import logger  # noqa: E402


def main() -> None:
    setup_logging("items")
    harm = jload(LANEC / "assets/gt_harm.json")
    ben = jload(LANEC / "assets/gt_benign.json")
    r54 = jload(LANEC / "assets/reserved_54.json")
    items = []
    for r in harm:
        items.append({"item_id": r["gt_id"], "set": "harm", "subset": "laneC", "harmful": 1,
                      "prompt": r["prompt"], "category": r.get("category")})
    for r in ben:
        items.append({"item_id": r["gt_id"], "set": "benign", "subset": "laneC", "harmful": 0,
                      "prompt": r["prompt"], "category": r.get("category")})
    for r in r54:
        items.append({"item_id": f"{r['pair_id']}_h", "set": "harm", "subset": "r54", "harmful": 1,
                      "prompt": r["harmful_request"], "category": r.get("family"), "pair_id": r["pair_id"]})
    for r in r54:
        items.append({"item_id": f"{r['pair_id']}_b", "set": "benign", "subset": "r54", "harmful": 0,
                      "prompt": r["benign_request"], "category": r.get("family"), "pair_id": r["pair_id"]})
    ids = [x["item_id"] for x in items]
    assert len(ids) == len(set(ids)), "duplicate item ids"
    jdump({"n_items": len(items), "n_harm": sum(x["harmful"] for x in items),
           "n_benign": sum(1 - x["harmful"] for x in items),
           "n_laneC": sum(x["subset"] == "laneC" for x in items), "n_r54": sum(x["subset"] == "r54" for x in items),
           "items": items}, ASSETS / "behaviour_items.json")
    logger.info(f"items: {len(items)} (harm {sum(x['harmful'] for x in items)}, benign "
                f"{sum(1 - x['harmful'] for x in items)}); laneC {len(harm)}+{len(ben)}, r54 {len(r54)}x2")

    srcs = {
        "LANEC/lc_judge.py": LANEC / "lc_judge.py", "LANEC/lc_common.py": LANEC / "lc_common.py",
        "LANEC/lc_harvest.py": LANEC / "lc_harvest.py", "LANEC/lc_panel.py": LANEC / "lc_panel.py",
        "LANEC/lc_analyze.py": LANEC / "lc_analyze.py", "LANEC/prereg.json": LANEC / "prereg.json",
        "LANEC/assets/gt_harm.json": LANEC / "assets/gt_harm.json",
        "LANEC/assets/gt_benign.json": LANEC / "assets/gt_benign.json",
        "LANEC/assets/reserved_54.json": LANEC / "assets/reserved_54.json",
        "H2/src/harvest.py": H2 / "src/harvest.py", "H2/src/c_harvest2.py": H2 / "src/c_harvest2.py",
        "H2/src/wsummary.py": H2 / "src/wsummary.py", "H2/src/score_ckpt.py": H2 / "src/score_ckpt.py",
        "H2/src/analyze.py": H2 / "src/analyze.py", "H2/src/numerics.py": H2 / "src/numerics.py",
        "H2/src/judge_ext.py": H2 / "src/judge_ext.py", "H2/src/judge_ext_lanec.py": H2 / "src/judge_ext_lanec.py",
        "H2/src/aii_common.py": H2 / "src/aii_common.py", "H2/src/score_panel.py": H2 / "src/score_panel.py",
        "H2/assets/stimuli.json": H2 / "assets/stimuli.json", "H2/assets/token_sets.json": H2 / "assets/token_sets.json",
        "H2/assets/cells.json": H2 / "assets/cells.json",
        "H2/results/scored_checkpoints.json": H2 / "results/scored_checkpoints.json",
        "H2/prereg.json": H2 / "prereg.json",
        "D2/full_data_out.json": D2 / "full_data_out.json", "D2/assets/rubric_iter1.md": D2 / "assets/rubric_iter1.md",
        "D2/assets/lc_judge_iter1.py": D2 / "assets/lc_judge_iter1.py",
        "D1/rubric.md": D1 / "rubric.md", "D1/model_registry.json": D1 / "model_registry.json",
        "STRAT/struct_out.json": STRAT,
    }
    prov = {"utc": utc_now(), "files": {}}
    for k, p in srcs.items():
        prov["files"][k] = {"path": str(p), "sha256": sha256_file(p) if p.exists() else None,
                            "exists": p.exists()}
    jdump(prov, RESULTS / "provenance.json")
    logger.info(f"provenance: {sum(v['exists'] for v in prov['files'].values())}/{len(srcs)} source files hashed")


if __name__ == "__main__":
    main()
