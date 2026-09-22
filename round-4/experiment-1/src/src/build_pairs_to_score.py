#!/usr/bin/env python3
"""Build a pairs file for src/pairs.py from COMMITTED classifications only (never before them).

Reads every chain-verified classification_s*.json (staged chain, A11/A13), so scoring can start per stage while later
stages are still generating. Pair kinds:
  constructed      -> WS/harvest/<fk>__<variant>/          (both harvests DONE)
  harvested_regen  -> WS/harvest/HG__<slug>/ or F*__ref/   (A13 HG:: pairs, both harvests DONE)
  harvested        -> the on-disk iteration-2 / iteration-3 harvest dirs (read-only; Lane C truth)
N5 perturbation arrays (A_prompt_p1/p2/p3) are read by the engine from each checkpoint dir itself (A13).
--only-new skips pairs already present in <out>/pairs_long.json; --commissioned adds the 4B STaR row (no truth).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H2, HARVEST, I3, PARENTS, RESULTS, WS, chain_records, jdump, jload, setup_logging, sha256_file  # noqa: E402
from loguru import logger  # noqa: E402


def on_disk(tag: str) -> Path | None:
    for root in (I3 / "harvest", H2 / "harvest"):
        d = root / tag
        if (d / "A_prompt.npy").exists():
            return d
    return None


def repo_of(tag: str) -> str:
    if tag.startswith("HG__"):
        return tag[4:].replace("--", "/", 1)
    fk = tag.split("__")[0]
    if fk in PARENTS:
        return PARENTS[fk]["repo"]
    return tag.replace("--", "/", 1)


def committed_rows() -> list[dict]:
    rows, seen = [], set()
    for r in chain_records():
        if r["step"] != "classification" or not r.get("file"):
            continue
        f = WS / r["file"]
        if not f.exists() or sha256_file(f) != r["sha256"]:
            logger.warning(f"{r['file']}: missing or changed after commit -> ignored")
            continue
        for q in jload(f)["pairs"]:
            if q["pair_id"] not in seen:
                rows.append(q)
                seen.add(q["pair_id"])
            elif q.get("observed_class") not in (None, "UNSCORED"):     # a later stage scored an earlier UNSCORED row
                rows = [x for x in rows if x["pair_id"] != q["pair_id"]] + [q]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RESULTS / "pairs_to_score.json"))
    ap.add_argument("--scores", default=str(RESULTS / "scores"))
    ap.add_argument("--only-new", action="store_true")
    ap.add_argument("--kinds", nargs="*", default=["constructed", "harvested_regen", "harvested"])
    ap.add_argument("--families", nargs="*", default=None, help="constructed families to include, e.g. F1 F2")
    ap.add_argument("--commissioned", action="store_true")
    a = ap.parse_args()
    setup_logging("build_pairs")
    done = set()
    pl = Path(a.scores) / "pairs_long.json"
    if a.only_new and pl.exists():
        done = {r["pair_id"] for r in jload(pl)}
    out, skipped = [], []
    for p in committed_rows():
        pid = p["pair_id"]
        if p.get("observed_class") in (None, "UNSCORED"):
            skipped.append({"pair_id": pid, "why": "unscored behaviour"})
            continue
        if p["kind"] not in a.kinds or pid in done:
            continue
        if a.families and p["kind"] == "constructed" and p["parent"].split("__")[0] not in a.families:
            continue
        if p["kind"] in ("constructed", "harvested_regen"):
            pd, cd = HARVEST / p["parent"], HARVEST / p["child"]
            if not (pd / "DONE").exists() or not (cd / "DONE").exists():
                skipped.append({"pair_id": pid, "why": "harvest not DONE"})
                continue
        else:
            pd, cd = on_disk(p["parent"]), on_disk(p["child"])
            if pd is None or cd is None:
                skipped.append({"pair_id": pid, "why": "no on-disk arrays"})
                continue
        out.append({"pair_id": pid, "parent_tag": p["parent"], "parent_dir": str(pd), "child_tag": p["child"],
                    "child_dir": str(cd), "parent_repo": repo_of(p["parent"]), "child_repo": repo_of(p["child"]),
                    "kind": p["kind"], "constructed": p["kind"] == "constructed",
                    "observed_class": p["observed_class"], "intended_stratum": p["intended_stratum"]})
    if a.commissioned:
        # plan section 8: STaR has no Lane C truth (harvested_truth 'missing'); a per-checkpoint row only, scored as a
        # pseudo pair against Qwen3-4B-Base so its bundle is computed -- never enters any aggregate
        star = "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6"
        pd, cd = on_disk("Qwen--Qwen3-4B-Base"), on_disk(star)
        if pd and cd and "COMMISSIONED::STaR" not in done:
            out.append({"pair_id": "COMMISSIONED::STaR", "parent_tag": "Qwen--Qwen3-4B-Base", "parent_dir": str(pd),
                        "child_tag": star, "child_dir": str(cd), "parent_repo": "Qwen/Qwen3-4B-Base",
                        "child_repo": star.replace("--", "/", 1), "kind": "commissioned_row_only", "constructed": False,
                        "observed_class": "NO_TRUTH", "intended_stratum": "COMMISSIONED_ROW_ONLY"})
    jdump(out, Path(a.out))
    jdump(skipped, Path(str(a.out).replace(".json", "_skipped.json")))
    logger.info(f"pairs to score: {len(out)} -> {a.out}; skipped {len(skipped)}")


if __name__ == "__main__":
    main()
