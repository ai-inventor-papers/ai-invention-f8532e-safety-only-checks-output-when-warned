#!/usr/bin/env python3
"""Incremental Phase-D scoring (A13): score committed pairs as soon as a whole parent group is harvested.

Every cycle: committed pairs (chain-verified classification_s*.json) not yet in results/scores/pairs_long.json are
grouped by parent tag; a group is READY when every pair's parent and child harvest is DONE (on-disk dirs for the
Lane-C harvested pairs are always ready). Ready groups are written to a pairs file and scored by src/pairs.py (B=1000,
50 shuffled-label nulls, k-curves), which appends to pairs_long.json; k-curves are MERGED across runs. Exits when
results/score_stop.flag exists and nothing is pending. One scoring subprocess at a time (pairs_long.json has one writer).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_pairs_to_score import committed_rows, on_disk, repo_of  # noqa: E402
from common import HARVEST, LOGS, RESULTS, WS, jdump, jload, setup_logging, utc_now  # noqa: E402
from loguru import logger  # noqa: E402

SCORES = RESULTS / "scores"
PY = str(WS / ".venv" / "bin" / "python")


def ready_groups(done: set) -> tuple[list[dict], list[str]]:
    groups: dict[str, list[dict]] = {}
    for p in committed_rows():
        if p.get("observed_class") in (None, "UNSCORED") or p["pair_id"] in done:
            continue
        groups.setdefault(p["parent"], []).append(p)
    out, waiting = [], []
    for parent, ps in groups.items():
        rows, ok = [], True
        for p in ps:
            if p["kind"] in ("constructed", "harvested_regen"):
                pd, cd = HARVEST / p["parent"], HARVEST / p["child"]
                failed = (RESULTS / "deviations.json").exists() and any(
                    d.get("key") in (f"harvest_failed_{p['parent']}", f"harvest_failed_{p['child']}")
                    for d in jload(RESULTS / "deviations.json"))
                if failed:
                    continue                      # a failed harvest never blocks the rest of its group
                if not ((pd / "DONE").exists() and (cd / "DONE").exists()):
                    ok = False
                    break
            else:
                pd, cd = on_disk(p["parent"]), on_disk(p["child"])
                if pd is None or cd is None:
                    continue
            rows.append({"pair_id": p["pair_id"], "parent_tag": p["parent"], "parent_dir": str(pd),
                         "child_tag": p["child"], "child_dir": str(cd), "parent_repo": repo_of(p["parent"]),
                         "child_repo": repo_of(p["child"]), "kind": p["kind"], "constructed": p["kind"] == "constructed",
                         "observed_class": p["observed_class"], "intended_stratum": p["intended_stratum"]})
        if ok and rows:
            out.extend(rows)
        elif not ok:
            waiting.append(parent)
    return out, waiting


def merge_kcurves(run_dir: Path) -> None:
    k_new = run_dir / "kcurves.json"
    if not k_new.exists():
        return
    k_all = SCORES / "kcurves_all.json"
    cur = jload(k_all) if k_all.exists() else {}
    cur.update(jload(k_new))
    jdump(cur, k_all)


def main() -> int:
    setup_logging("score_watch")
    SCORES.mkdir(parents=True, exist_ok=True)
    commissioned_done = False
    n_run = 0
    while True:
        pl = SCORES / "pairs_long.json"
        done = {r["pair_id"] for r in jload(pl)} if pl.exists() else set()
        todo, waiting = ready_groups(done)
        if not commissioned_done and "COMMISSIONED::STaR" not in done:
            star = "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6"
            pd, cd = on_disk("Qwen--Qwen3-4B-Base"), on_disk(star)
            if pd and cd:
                todo.append({"pair_id": "COMMISSIONED::STaR", "parent_tag": "Qwen--Qwen3-4B-Base", "parent_dir": str(pd),
                             "child_tag": star, "child_dir": str(cd), "parent_repo": "Qwen/Qwen3-4B-Base",
                             "child_repo": star.replace("--", "/", 1), "kind": "commissioned_row_only",
                             "constructed": False, "observed_class": "NO_TRUTH", "intended_stratum": "COMMISSIONED_ROW_ONLY"})
            commissioned_done = True
        if todo:
            n_run += 1
            pf = SCORES / f"pairs_run{n_run:02d}.json"
            jdump(todo, pf)
            t0 = time.time()
            logger.info(f"run {n_run}: {len(todo)} pairs, {len({t for p in todo for t in (p['parent_tag'], p['child_tag'])})} "
                        f"checkpoints; waiting groups: {waiting}")
            env = dict(os.environ, OMP_NUM_THREADS=os.environ.get("SCORE_THREADS", "4"),
                       MKL_NUM_THREADS=os.environ.get("SCORE_THREADS", "4"),
                       OPENBLAS_NUM_THREADS=os.environ.get("SCORE_THREADS", "4"))
            with open(LOGS / f"score_run{n_run:02d}.log", "w") as lf:
                rc = subprocess.run([PY, str(WS / "src" / "pairs.py"), "--pairs", str(pf), "--B", os.environ.get("SCORE_B", "1000"),
                                     "--n-null", "50", "--out", str(SCORES), "--seed", "42"],
                                    stdout=lf, stderr=subprocess.STDOUT, env=env).returncode
            merge_kcurves(SCORES)
            logger.info(f"run {n_run}: exit {rc} in {time.time() - t0:.0f}s")
            jdump({"utc": utc_now(), "run": n_run, "rc": rc, "pairs": [p["pair_id"] for p in todo], "s": time.time() - t0},
                  SCORES / f"run{n_run:02d}_status.json")
            if rc != 0:
                logger.error(f"pairs.py failed (see logs/score_run{n_run:02d}.log); retrying next cycle")
                time.sleep(60)
            continue
        if (RESULTS / "score_stop.flag").exists():
            logger.info(f"stop flag, nothing ready; waiting groups left: {waiting}")
            return 0
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
