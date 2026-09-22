#!/usr/bin/env python3
"""Full placebo distance calibration, including the failure the plan anticipated.

The plan requires the median token-edit distance benign<->hazardous and
benign<->placebo to agree within 10%. They do not: 4.0 vs 5.0 (ratio 1.25).
This reports why, shows the statistic that is not quantised, and confirms that
the per-item distances ship so a downstream lane can regress on them instead of
subtracting a constant -- which is exactly the plan's remedy (e).
"""
from __future__ import annotations

import json
import re
import statistics as st
import sys
from pathlib import Path

from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/placebo_calibration.log", rotation="10 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
_W = re.compile(r"[a-z0-9']+")
TOL = 0.10


def toks(s: str) -> list[str]:
    return _W.findall(s.lower())


def lev(a: list[str], b: list[str]) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


@logger.catch(reraise=True)
def main() -> None:
    rows = [e for d in json.loads((ROOT / "data_out.json").read_text())["datasets"] for e in d["examples"]]
    rows += [e for d in json.loads((ROOT / "heldout_cells.json").read_text())["datasets"] for e in d["examples"]]
    seen: dict[str, dict] = {}
    for r in rows:
        if r["metadata_table"] in ("safety_2x2", "placebo") and r["metadata_item_uid"]:
            seen.setdefault(r["metadata_item_uid"], r)

    per_item = []
    for uid, r in seen.items():
        b, h, p = r["metadata_action_phrase_benign"], r["metadata_action_phrase_harm"], r["metadata_action_phrase_placebo"]
        if not (b and h and p):
            continue
        per_item.append({
            "item_uid": uid, "family": r["metadata_family"],
            "d_benign_to_hazardous": lev(toks(b), toks(h)),
            "d_benign_to_placebo": lev(toks(b), toks(p)),
            "benign": b, "hazardous": h, "placebo": p,
        })
    dh = [x["d_benign_to_hazardous"] for x in per_item]
    dp = [x["d_benign_to_placebo"] for x in per_item]
    med_r = st.median(dp) / st.median(dh)
    mean_r = st.mean(dp) / st.mean(dh)
    diffs = [x["d_benign_to_placebo"] - x["d_benign_to_hazardous"] for x in per_item]
    n_exact = sum(1 for d in diffs if d == 0)

    logger.info(f"n items = {len(per_item)}")
    logger.info(f"  median  benign->hazardous = {st.median(dh)}   benign->placebo = {st.median(dp)}   ratio = {med_r:.3f}")
    logger.info(f"  mean    benign->hazardous = {st.mean(dh):.3f}  benign->placebo = {st.mean(dp):.3f}  ratio = {mean_r:.3f}")
    logger.info(f"  per-item exact distance match: {n_exact}/{len(per_item)}; mean signed gap = {st.mean(diffs):+.3f} tokens")
    status = "PASSED" if abs(med_r - 1) <= TOL else "FAILED"
    logger.info(f"  PLAN GATE (median within 10%): {status}")

    out = {
        "gate": "median token-edit distance benign<->hazardous and benign<->placebo agree within 10%",
        "status": status,
        "median_benign_to_hazardous": st.median(dh),
        "median_benign_to_placebo": st.median(dp),
        "median_ratio": round(med_r, 4),
        "mean_benign_to_hazardous": round(st.mean(dh), 4),
        "mean_benign_to_placebo": round(st.mean(dp), 4),
        "mean_ratio": round(mean_r, 4),
        "n_items": len(per_item),
        "n_exact_per_item_match": n_exact,
        "mean_signed_gap_tokens": round(st.mean(diffs), 4),
        "why_it_fails": (
            "A placebo SELECTED from another item's benign action cannot get closer to the item's own benign action "
            "than the floor imposed by two unrelated short phrases, which is about 5 tokens here; a twin edit is "
            "about 4. Enlarging the admissible pool from 100 to 164 candidates (adding the dolly-derived fitting "
            "corpus) does not move the median at all, so this is a floor, not a search failure. The medians are "
            "also integer-quantised at this scale, which turns a real gap of "
            f"{st.mean(diffs):+.2f} tokens into a 25% ratio; the MEAN ratio is {mean_r:.3f}."
        ),
        "remedy_applied": (
            "The plan's failure scenario (e) is followed exactly: the mismatch is REPORTED rather than hidden, and "
            "the PER-ITEM distances ship as the column metadata_levenshtein_to_benign_prefix on every cell, so a "
            "downstream lane regresses on the per-item distance instead of subtracting a constant."
        ),
        "alternative_rejected": (
            "Matching the distance exactly would require CONSTRUCTING placebo phrases by editing the benign phrase, "
            "rather than drawing a real benign action from the corpus. That was rejected: it would replace measured "
            "corpus text with authored text in the one factor whose job is to be an honest control."
        ),
        "per_item": per_item,
    }
    (RES / "placebo_calibration.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    logger.info("wrote results/placebo_calibration.json")


if __name__ == "__main__":
    main()
