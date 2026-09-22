"""CONFIRMATION -- run ONCE, after the screen is FROZEN.

Discipline (Section 10): survivor.json is written and hashed FIRST; nothing after that
point may change any screen number.  Then the survivor is scored ONLY on evidence that is
genuinely untouched.

The two 'sealed' families do NOT qualify: their truth values leaked into Lane C's
results/s3/s3_results.json, which every lane reads.  The clean tiers are

  (i)  assets/reserved_54.json -- 54 XSTest pairs, hash-split BEFORE any activation was
       collected, and loaded by no other module. THIS FILE IS OPENED ONLY HERE.
  (ii) HELD-OUT CHECKPOINTS -- families never used to fit or select anything in the screen.
       For a LABEL-FREE survivor such as X10 this is the right axis of confirmation, because
       the thing to generalise over is checkpoints, not prompts.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import (  # noqa: E402
    ASSETS, DEVIATIONS, HARVEST, LANE_C, RESULTS, WS, Deadline, jdump, jload, jload_maybe,
    load_npy_maybe_split, sha256_file, setup_logging, slug,
)
from loguru import logger  # noqa: E402
import numerics as nm  # noqa: E402
import score_panel as sp  # noqa: E402
from score_ckpt import CkptCache, compute_candidates, compute_x10  # noqa: E402

RESERVED_54 = LANE_C / "assets" / "reserved_54.json"


def freeze_survivor(name: str, rationale: str, s_table: list) -> dict:
    doc = {"survivor": name, "rationale": rationale,
           "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "s_table_at_freeze": s_table}
    p = jdump(doc, WS / "survivor.json")
    h = sha256_file(p)
    (WS / "survivor.sha256").write_text(h + "\n")
    logger.info(f"SURVIVOR FROZEN = {name}; survivor.json SHA-256 = {h}")
    doc["sha256"] = h
    return doc


def load_reserved_prompts() -> dict:
    """THE ONE CLEAN SEAL.  Opened only inside this module, after the freeze."""
    if not RESERVED_54.exists():
        return {"error": f"missing {RESERVED_54}"}
    rows = jload(RESERVED_54)
    if isinstance(rows, dict):
        rows = rows.get("pairs") or rows.get("rows") or []
    harm = [r["harmful_request"] for r in rows if r.get("harmful_request")]
    ben = [r["benign_request"] for r in rows if r.get("benign_request")]
    return {"harmful": harm, "benign": ben, "n_pairs": len(rows),
            "source": str(RESERVED_54)}


def confirm_label_free(survivor: str, screen_tags: set[str], cfg: dict) -> dict:
    """HELD-OUT CHECKPOINTS for a weights-only survivor: the frozen rule is applied,
    without recalibration, to checkpoints the screen never touched."""
    held = []
    for p in sorted(HARVEST.glob("*/W_DONE")):
        tag = p.parent.name
        if tag in screen_tags:
            continue
        try:
            c = _wcache(tag)
            r = compute_x10(c, cfg)
            held.append({"checkpoint": tag, survivor: r.get(survivor),
                         f"{survivor}_abs": r.get(f"{survivor}_abs"),
                         "argmax_layer": r.get(f"{survivor}_argmax_layer")})
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"confirm: {tag} failed ({exc})")
    return {"tier": "HELD_OUT_CHECKPOINTS", "n": len(held), "rows": held}


def _wcache(tag: str):
    class _W:
        def __init__(self, t):
            self.tag = t
            self.dir = HARVEST / t
            wm = jload_maybe(self.dir / "w_meta.json", {}) or {}
            self.meta = {"w": {"parts": wm.get("parts", {})},
                         "n_layers": wm.get("n_layers_found", 0), "hidden_size": 0}

        def arr(self, name):
            p = self.dir / f"{name}.npy"
            return np.load(p) if p.exists() else None
    return _W(tag)


def confirm_label_dependent(survivor: str, pairs: list[dict], cfg: dict,
                            dl: Deadline, budget_min: float = 25.0) -> dict:
    """Harvest the RESERVED-54 prompts (never seen by any lane) on the cheapest pair whose
    members are already in the panel, refit the survivor on them, and apply the frozen rule
    once.  ONE test: same sign and CI excluding zero."""
    res = load_reserved_prompts()
    if "error" in res:
        return {"tier": "RESERVED_54", "status": "UNAVAILABLE", **res}
    from harvest import harvest_one

    stim = ([{"text": t, "y": 1, "set_id": 0, "stim_id": f"C{i}"}
             for i, t in enumerate(res["harmful"])]
            + [{"text": t, "y": 0, "set_id": 0, "stim_id": f"C{i}b"}
               for i, t in enumerate(res["benign"])])
    order = sorted(pairs, key=lambda p: {"P1": 0, "P3": 1, "P2": 2, "P6": 3}.get(p["pair"], 9))
    for p in order:
        if not dl.have(budget_min):
            return {"tier": "RESERVED_54", "status": "SKIPPED_TIME",
                    "reason": f"less than {budget_min} min left at the confirmation gate"}
        tags = []
        try:
            for repo in (p["parent"], p["child"]):
                tag = slug(repo) + "--confirm54"
                harvest_one(repo, cfg, stim, None, tag=tag, do_c_harvest=False,
                            do_w_summary=False)
                tags.append(tag)
        except Exception as exc:  # noqa: BLE001
            DEVIATIONS.add("confirm_harvest_failed", p["pair"], repr(exc)[:300])
            continue
        vals = {}
        for tag, role in zip(tags, ("parent", "child")):
            c = CkptCache(tag)
            # the weight summary lives under the SCREEN tag, not the confirm tag
            c.dir_w = HARVEST / tag.replace("--confirm54", "")
            y = np.array([s["y"] for s in stim])
            try:
                vals[role] = compute_candidates(_merge(c), y, cfg, seed=1)
            except Exception as exc:  # noqa: BLE001
                DEVIATIONS.add("confirm_score_failed", tag, repr(exc)[:300])
        if "parent" in vals and "child" in vals:
            vp, vc = vals["parent"].get(survivor), vals["child"].get(survivor)
            return {"tier": "RESERVED_54", "status": "RUN", "pair": p["pair"],
                    "n_prompts": len(stim), "parent": vp, "child": vc,
                    "delta": (vc - vp) if (vp is not None and vc is not None) else None,
                    "source": res["source"], "n_reserved_pairs": res["n_pairs"],
                    "rule": "ONE test: same sign as the screen and CI excluding zero. If it "
                            "fails, the candidate is DEAD -- no re-screen, no subgroup search."}
    return {"tier": "RESERVED_54", "status": "NO_PAIR_AVAILABLE"}


def _merge(c):
    """Let a confirm-tag cache read the weight summary written under the screen tag."""
    base = getattr(c, "dir_w", None)
    if base is None or not base.exists():
        return c
    wm = jload_maybe(base / "w_meta.json", {}) or {}
    if wm:
        c.meta = dict(c.meta)
        c.meta["w"] = {"parts": wm.get("parts", {})}
    orig_arr = c.arr
    orig_dir = c.dir

    def arr(name):
        # single <name>.npy or the numbered parts written for GitHub's 100 MiB limit
        a = load_npy_maybe_split(orig_dir, name)
        return a if a is not None else load_npy_maybe_split(base, name)
    c.arr = arr

    class _G:
        def __get__(self, *_):
            return []
    try:
        gd = base / "gram"
        c._G = [np.load(f) for f in sorted(gd.glob("G_*.npy"))] if gd.exists() else []
    except Exception:  # noqa: BLE001
        c._G = []
    return c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline-min", type=float, default=30.0)
    args = ap.parse_args()
    setup_logging("confirm")
    dl = Deadline(args.deadline_min)
    cfg = dict(jload(WS / "prereg.json")["config"])
    cfg["primary_fpr_level"] = jload(WS / "prereg.json")["stimuli_meta"]["primary_fpr_level"]
    cfg["token_sets"] = {k: v for k, v in jload(ASSETS / "token_sets.json").items()
                         if k != "meta"}
    cfg["x5_cell_index"] = []

    etests = jload_maybe(RESULTS / "e_tests.json", {}) or {}
    e_tables = etests.get("e_tables", {})
    scored = jload_maybe(RESULTS / "scored_checkpoints.json", {}) or {}
    pairs = (jload_maybe(RESULTS / "pairs_effective.json", None)
             or jload(ASSETS / "pairs.json"))["pairs"]

    s_table = []
    for k, e in e_tables.items():
        s_table.append({"candidate": k, "e1_pass": (e.get("E1") or {}).get("e1_pass"),
                        "e2_pass": (e.get("E2") or {}).get("e2_pass"),
                        "e3_pass": (e.get("E3") or {}).get("e3_pass"),
                        "e3_margin": (e.get("E3") or {}).get("e3_margin_vs_BL1")})
    for r in s_table:
        e = e_tables.get(r["candidate"], {})
        r["e1_status"] = (e.get("E1") or {}).get("e1_status")
        r["e1_effect"] = abs(float(np.nanmedian(
            ((e.get("E1") or {}).get("e1a_sensitivity") or {}).get("deltas") or [np.nan])))
        r["excluded_by_prior_art"] = sp.SURVIVOR_EXCLUDED.get(r["candidate"])
    eligible = [r for r in s_table if r["candidate"] in sp.HEADLINE
                and not r["excluded_by_prior_art"]]
    cands = [r for r in eligible if r.get("e1_pass") and (r.get("e2_pass") or r.get("e3_pass"))]
    # ties: larger E3 margin, then larger E1 effect size (registered)
    cands.sort(key=lambda r: (-(r.get("e3_margin") if r.get("e3_margin") is not None else -9),
                              -(r.get("e1_effect") if np.isfinite(r.get("e1_effect", np.nan))
                                else -9)))
    survivor = cands[0]["candidate"] if cands else "NONE"
    closed_passing = [r["candidate"] for r in s_table
                      if r["excluded_by_prior_art"] and r.get("e1_pass")]
    n_under = sum(1 for r in eligible if r.get("e1_status") == "UNDER_POWERED")
    rationale = ("passes E1 and at least one of E2/E3, and is not CLOSED by prior art"
                 if cands else
                 "NO ELIGIBLE CANDIDATE passes E1 AND (E2 or E3). "
                 + (f"{n_under} of {len(eligible)} eligible headline candidates are E1 "
                    "UNDER-POWERED: no edit-recipe stratum reaches the registered minimum of 4 "
                    "EFFECTIVE pairs, so E1(a) cannot be met by construction of the panel that "
                    "could be harvested. " if n_under else "")
                 + "Reported plainly, with the MDE per row so a reader can see what the design "
                   "could have detected. No subgroup hunting."
                 + (f" Candidates CLOSED by prior art that nevertheless pass E1 (reported, "
                    f"not eligible): {closed_passing}." if closed_passing else ""))
    doc = freeze_survivor(survivor, rationale, s_table)

    out = {"survivor": survivor, "survivor_sha256": doc["sha256"], "rationale": rationale}
    if survivor == "NONE":
        out["confirmation"] = {"status": "NOT APPLICABLE -- no survivor to confirm"}
        out["seal_discipline"] = ("reserved_54.json was NOT opened: with no survivor there is "
                                 "nothing to confirm, and the seal is left clean for a later "
                                 "iteration.")
    elif survivor in sp.LABEL_FREE:
        screen = {t for t in scored}
        out["confirmation"] = confirm_label_free(survivor, screen, cfg)
        out["seal_discipline"] = ("the survivor is LABEL-FREE, so confirmation generalises "
                                  "over CHECKPOINTS, not prompts; reserved_54.json was left "
                                  "unopened and stays clean.")
    else:
        out["confirmation"] = confirm_label_dependent(survivor, pairs, cfg, dl)
        out["seal_discipline"] = "reserved_54.json opened HERE and nowhere else."
    out["sealed_families_note"] = (
        "The stablelm and smollm2 'sealed' families are NOT used as confirmation: their "
        "truth values leaked into Lane C's results/s3/s3_results.json. They serve only as "
        "ANOMALOUS specificity controls in E1(b).")
    out["heldout_cells_note"] = (
        "gen_art_dataset_1/heldout_cells.json (1,350 sealed cells) was NOT opened: it needs "
        "the teacher-forced C-harvest, which this box could not afford, so the seal is left "
        "clean rather than half-used.")
    jdump(out, RESULTS / "confirmation.json")
    logger.info(f"confirmation written: survivor={survivor}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
