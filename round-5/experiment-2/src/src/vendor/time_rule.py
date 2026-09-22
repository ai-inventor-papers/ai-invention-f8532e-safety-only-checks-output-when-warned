"""The pre-registered TIME RULE (assets/panel_rule.json), applied mechanically after stage-1 timing.

Projection: every remaining checkpoint's generation time = the measured seconds of the completed
checkpoint(s) scaled by parameter count (s per parameter from the completed ones), plus the measured
per-checkpoint judging lag for the last one. If the projected generation + judging for the drawn panel
exceeds 150 min, FILL members are dropped in REVERSE draw order, never a mandatory member and never
below a quota (a fill member that carries the >=4-family quota is kept), until the projection is
<= 150 min or only the quota-satisfying prefix remains. Items are never cut.
Writes results/panel_trim.json and appends it to the hash chain.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, chain_append, jdump, jload, setup_logging, utc_now  # noqa: E402
from loguru import logger  # noqa: E402

BUDGET_MIN = 150.0


def main() -> None:
    setup_logging("time_rule")
    pan = jload(RESULTS / "panel.json")
    panel = pan["panel"]
    tim = jload(RESULTS / "gen_timings.json")
    done = {r: v for r, v in tim.items() if "t_gen_s" in v}
    if not done:
        raise SystemExit("no completed checkpoint yet")
    s_per_param = sum(v["t_gen_s"] for v in done.values()) / sum(v["params"] for v in done.values())
    judge_lag_s = 180.0  # judging overlaps generation; only the last checkpoint's judging adds to the wall
    def proj(members):
        tot = 0.0
        for p in members:
            if p["repo"] in done:
                tot += done[p["repo"]]["t_gen_s"] + done[p["repo"]].get("t_load_s", 0)
            else:
                tot += s_per_param * float(p["params_total"]) + 30.0
        return (tot + judge_lag_s) / 60.0
    families_needed = 4
    cur = list(panel)
    dropped, log = [], []
    t0 = proj(cur)
    log.append({"step": "initial", "n": len(cur), "projected_min": t0})
    fills = [p for p in reversed(panel) if not p["mandatory"]]
    for p in fills:
        if proj(cur) <= BUDGET_MIN:
            break
        others = [q for q in cur if q["repo"] != p["repo"]]
        fams = {q["family"] for q in others}
        if len(fams) < families_needed:
            log.append({"step": "keep", "repo": p["repo"], "reason": "carries the >=4-family quota"})
            continue
        if len(others) < 8:
            log.append({"step": "keep", "repo": p["repo"], "reason": "n would fall below 8"})
            continue
        cur = others
        dropped.append(p["repo"])
        log.append({"step": "drop", "repo": p["repo"], "projected_min_after": proj(cur)})
    out = {"utc": utc_now(), "budget_min": BUDGET_MIN, "s_per_param_measured": s_per_param,
           "measured_on": {r: {"t_gen_s": v["t_gen_s"], "params": v["params"], "tok_per_s": v.get("tok_per_s")}
                           for r, v in done.items()},
           "projected_initial_min": t0, "projected_final_min": proj(cur), "dropped": dropped,
           "final_panel": [p["repo"] for p in cur], "n_final": len(cur),
           "families_final": sorted({p["family"] for p in cur}), "log": log,
           "context": ("CPU-only box: 2 hyperthreads shared with the two sibling gen_art agents of this "
                       "iteration (the screen's CPU scoring runs concurrently), so measured throughput "
                       "already includes that contention.")}
    jdump(out, RESULTS / "panel_trim.json")
    chain_append(RESULTS / "panel_trim.json", "TIME rule applied mechanically after stage-1 timing")
    logger.info(f"TIME rule: projected {t0:.0f} -> {proj(cur):.0f} min; dropped {dropped}; n={len(cur)}")


if __name__ == "__main__":
    main()
