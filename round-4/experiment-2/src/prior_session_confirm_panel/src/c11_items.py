"""C11 severity items: 23 D2 recognition rows with non-null graded_harm + 41 PKU-SafeRLHF test rows.

graded_harm = max(response_0_severity_level, response_1_severity_level) -- the D2 rule, re-used verbatim.
The 41 extra rows are drawn by sha256(seed + 'pku_saferlhf_test__<idx>') ascending, stratified so the
64-item set is as close to 16 per severity level 0..3 as the pool allows; ids are logged. Rows already
used by D2 (any split) are excluded. Written BEFORE prereg; read by the harvest's one extra prompt pass.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ASSETS, D2, SEED, jdump, jload, setup_logging, sha256_str, utc_now  # noqa: E402
from loguru import logger  # noqa: E402

API = "https://datasets-server.huggingface.co/rows?dataset=PKU-Alignment/PKU-SafeRLHF&config=default&split=test"


def fetch(offset: int, length: int = 100) -> list[dict]:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"{API}&offset={offset}&length={length}", timeout=60) as r:
                return json.loads(r.read().decode())["rows"]
        except Exception as e:  # noqa: BLE001
            logger.warning(f"fetch {offset}: {e!r}")
            time.sleep(2 * (attempt + 1))
    return []


def main() -> None:
    setup_logging("c11_items")
    d = jload(D2 / "full_data_out.json")
    hr = [ds for ds in d["datasets"] if ds["dataset"].endswith("hard_recognition_set")][0]["examples"]
    base = [r for r in hr if r.get("metadata_graded_harm") is not None]
    used_ids = {r["metadata_row_id"] for r in hr}
    items = [{"c11_id": r["metadata_row_id"], "prompt": r["input"], "severity": int(r["metadata_graded_harm"]),
              "source": "D2_hard_recognition_set"} for r in base]
    # fetch the first 2000 test rows (the draw pool), rank by the seeded hash
    pool = []
    for off in range(0, 2000, 100):
        for row in fetch(off):
            idx = int(row["row_idx"])
            rid = f"pku_saferlhf_test__{idx}"
            if rid in used_ids:
                continue
            rr = row["row"]
            s0, s1 = rr.get("response_0_severity_level"), rr.get("response_1_severity_level")
            if s0 is None or s1 is None:
                continue
            pool.append({"c11_id": rid, "prompt": rr["prompt"], "severity": int(max(s0, s1)),
                         "source": "PKU-SafeRLHF test (datasets-server rows API)"})
    # PKU repeats prompts across rows: keep the first occurrence of each prompt text
    seen_p = {x["prompt"] for x in items}
    uniq = []
    for x in sorted(pool, key=lambda x: sha256_str(SEED + x["c11_id"])):
        if x["prompt"] in seen_p:
            continue
        seen_p.add(x["prompt"])
        uniq.append(x)
    target = {lv: 16 for lv in range(4)}
    have = {lv: sum(1 for x in items if x["severity"] == lv) for lv in range(4)}
    need = 64 - len(items)
    extra = []
    # pass 1: fill each level up to 16 in hash order
    for x in uniq:
        if len(extra) >= need:
            break
        lv = x["severity"]
        if have[lv] < target[lv]:
            extra.append(x)
            have[lv] += 1
    # pass 2: if some level is short in the pool, fill the remainder in hash order
    for x in uniq:
        if len(extra) >= need:
            break
        if x not in extra:
            extra.append(x)
            have[x["severity"]] += 1
    items += extra
    out = {"n": len(items), "n_from_D2": len(base), "n_drawn": len(extra),
           "severity_counts": {str(k): v for k, v in have.items()},
           "draw_rule": "sha256(seed + c11_id) ascending within the first 2000 PKU-SafeRLHF test rows, "
                        "stratified toward 16 per severity level; D2-used rows and repeated prompts excluded",
           "seed": SEED, "utc": utc_now(), "items": items}
    jdump(out, ASSETS / "c11_items.json")
    logger.info(f"C11 items: {len(items)} ({len(base)} D2 + {len(extra)} drawn); severity counts {have}")


if __name__ == "__main__":
    main()
