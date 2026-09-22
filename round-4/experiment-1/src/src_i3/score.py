"""STEP 5 -- SCORE (CPU only, no model loaded): features.json, heldout_table.json, join_stub/result.

Runs only after the order audit passes (graded truth -> prereg -> every panel harvest started after
the prereg commit). Reports every candidate and bar; names no winner.
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "h2"))
from common import (ASSETS, H2, HARVEST, RESULTS, RUN, WS, chain_records, jdump, jload, setup_logging,  # noqa: E402
                    sha256_file, slug, utc_now)
from loguru import logger  # noqa: E402

FEATURES = ["C1", "C1_k4", "C1_k8", "C2", "C2_tpr5", "C2_screenrule", "C3", "C3_screenrule", "C4", "C4_screenrule",
            "C5", "C6", "C6_screenrule", "C7", "C8", "C9", "C10", "C10_screenrule", "C11", "C12", "C12_topsv",
            "C12_screenrule", "C13", "C13_peak_d", "C13_peak_f", "BL1", "BL1_hard", "B3", "B7", "X2", "X10_abs"]
OUTCOMES = ["harmful_compliance", "over_refusal", "safe_engagement"]   # all on the 90 Lane C items


def order_audit() -> dict:
    recs = chain_records()
    names = [r["file"] for r in recs]
    res = {"utc": utc_now(), "checks": []}
    ok = True
    try:
        i_t, i_p = names.index("results/graded_truth.json"), names.index("prereg.json")
    except ValueError as e:
        return {"pass": False, "error": f"missing chain record {e}"}
    for i in (i_t, i_p):
        good = sha256_file(WS / recs[i]["file"]) == recs[i]["sha256"]
        res["checks"].append({"file": recs[i]["file"], "rehash_matches": good, "utc": recs[i]["utc"]})
        ok &= good
    res["truth_before_prereg"] = i_t < i_p
    ok &= i_t < i_p
    from datetime import datetime
    t_pre = datetime.strptime(recs[i_p]["utc"], "%Y-%m-%dT%H:%M:%S.%fZ").timestamp()
    panel = final_panel()
    res["per_ckpt"] = []
    for p in panel:
        d = HARVEST / slug(p["repo"])
        files = [f for f in d.rglob("*") if f.is_file()]
        if not files:
            res["per_ckpt"].append({"repo": p["repo"], "harvested": False})
            continue
        earliest = min(f.stat().st_mtime for f in files)
        meta = jload(d / "meta.json") if (d / "meta.json").exists() else {}
        start = meta.get("harvest_utc_start")
        good = earliest > t_pre
        res["per_ckpt"].append({"repo": p["repo"], "harvested": True, "earliest_file_mtime": earliest,
                                "prereg_commit_ts": t_pre, "harvest_utc_start": start,
                                "gate": (meta.get("order_gate") or {}).get("gate"), "after_prereg": good})
        ok &= good
    res["pass"] = bool(ok)
    return res


def final_panel() -> list[dict]:
    panel = jload(RESULTS / "panel.json")["panel"]
    trim = RESULTS / "panel_trim.json"
    dropped = set(jload(trim)["dropped"]) if trim.exists() else set()
    return [p for p in panel if p["repo"] not in dropped]


def outcome_table(truth: dict) -> dict:
    out = {}
    for repo, v in truth["per_ckpt"].items():
        a = v["outcomes_primary_laneC_items"]
        out[repo] = {"harmful_compliance": a["harmful_compliance"], "over_refusal": a["over_refusal"],
                     "safe_engagement": a["safe_engagement"]}
    return out


def find_screen_survivor() -> dict | None:
    for p in sorted(glob.glob(str(RUN / "iter_3/gen_art/*/survivor.json"))):
        if "gen_art_experiment_1" in p:
            continue
        try:
            sv = json.loads(Path(p).read_text())
        except Exception:  # noqa: BLE001
            continue
        shp = Path(p + ".sha256") if Path(p + ".sha256").exists() else Path(p).with_name("survivor.sha256")
        rec_sha = shp.read_text().split()[0] if shp.exists() else None
        return {"path": p, "content": sv, "sha256_now": sha256_file(Path(p)), "sha256_recorded": rec_sha,
                "hash_consistent": (rec_sha == sha256_file(Path(p))) if rec_sha else None}
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-audit", action="store_true", help="testing only")
    ap.add_argument("--boot", type=int, default=10000)
    a = ap.parse_args()
    setup_logging("score")
    import candidates as cand
    import stats_panel as sp
    audit = order_audit()
    jdump(audit, RESULTS / "order_audit.json")
    if not audit.get("pass") and not a.skip_audit:
        raise SystemExit(f"ORDER AUDIT FAILED: {audit}")
    stim = jload(H2 / "assets/stimuli.json")["rows"]
    cells = jload(H2 / "assets/cells.json")["cells"]
    c11 = jload(ASSETS / "c11_items.json")["items"]
    truth = jload(RESULTS / "graded_truth.json")
    outc = outcome_table(truth)
    panel = final_panel()
    feats, fams, roles = {}, {}, {}
    for p in panel:
        tag = slug(p["repo"])
        if not (HARVEST / tag / "DONE").exists():
            logger.warning(f"{p['repo']}: not harvested -> excluded from rho (counted)")
            continue
        if p["repo"] not in outc:
            logger.warning(f"{p['repo']}: no graded outcome -> excluded")
            continue
        logger.info(f"scoring {tag}")
        f = cand.compute_all(tag, stim, cells, c11)
        f["C1_k4"] = f["C1_kcurve"]["4"]["mean"]
        f["C1_k8"] = f["C1_kcurve"]["8"]["mean"]
        feats[p["repo"]] = f
        fams[p["repo"]] = p["family"]
        roles[p["repo"]] = p["role"]
    ri = None
    ri_tags = [Path(x).parent.name for x in glob.glob(str(HARVEST / "RandInit-*/DONE")) if "_SMOKE" not in x]
    if ri_tags:
        ri = cand.compute_all(ri_tags[0], stim, cells, c11)
        ri["C1_k4"] = ri["C1_kcurve"]["4"]["mean"]
        ri["C1_k8"] = ri["C1_kcurve"]["8"]["mean"]
    # screen join
    sv = find_screen_survivor()
    rows = sp.table(feats, outc, fams, FEATURES, OUTCOMES, cand.READOUT_CLASS, cand.EXPECTED_SIGN_VS_HC,
                    ri, family_overlap=set(), B=a.boot)
    jdump({"utc": utc_now(), "n_panel_scored": len(feats), "panel": list(feats), "families": fams, "roles": roles,
           "features": feats, "random_init": ri, "random_init_tag": ri_tags[0] if ri_tags else None},
          RESULTS / "features.json")
    jdump({"utc": utc_now(), "note": "one row per feature x outcome; NO ranking, NO winner",
           "n_panel": len(feats), "rows": rows}, RESULTS / "heldout_table.json")
    stub = {"utc": utc_now(), "confirmation_criterion": jload(WS / "prereg.json")["confirmation_criterion"],
            "how_to_join": ("read the screen's survivor.json (id or NONE) and its sign; look up the row "
                            "(feature=<id>, outcome=harmful_compliance) in results/heldout_table.json; "
                            "confirmed iff same sign AND screen-oriented rho exceeds BL1's"),
            "screen_survivor_found": bool(sv)}
    jdump(stub, RESULTS / "join_stub.json")
    if sv:
        c = sv["content"]
        sid = c.get("survivor") or c.get("survivor_id") or c.get("id") or c.get("name")
        res = {"utc": utc_now(), "screen_survivor_path": sv["path"], "screen_survivor_sha256": sv["sha256_now"],
               "screen_survivor_sha256_recorded": sv["sha256_recorded"], "hash_consistent": sv["hash_consistent"],
               "heldout_table_sha256": sha256_file(RESULTS / "heldout_table.json"),
               "prereg_sha256": sha256_file(WS / "prereg.json"), "survivor": sid, "screen_content_head": json.dumps(c)[:1500]}
        if not sid or str(sid).upper() == "NONE":
            res["verdict"] = "NOTHING_TO_CONFIRM (screen survivor = NONE)"
        else:
            row = next((r for r in rows if r["feature"] == sid and r["outcome"] == "harmful_compliance"), None)
            bl1 = next((r for r in rows if r["feature"] == "BL1" and r["outcome"] == "harmful_compliance"), None)
            s_c = c.get("sign") or c.get("rho_sign")
            if row is None or s_c is None:
                res["verdict"] = "LOOKUP_INCOMPLETE (feature row or screen sign unavailable)"
            else:
                s_c = int(np.sign(float(s_c)))
                s_b = int(np.sign(float(c.get("bl1_sign", -1))))
                res["row"] = row
                res["verdict"] = ("CONFIRMED" if (np.sign(row["rho"]) == s_c and s_c * row["rho"] > s_b * bl1["rho"])
                                  else "NOT_CONFIRMED")
        jdump(res, RESULTS / "join_result.json")
    # ---- two-panel sign/size table (ADDITIONAL; no selection): held-out rho beside the same-code rho on the
    # iteration-2 screen panel's saved activations (src/iter2_panel_same_code.py)
    i2p = RESULTS / "iter2_panel_same_code.json"
    if i2p.exists():
        i2 = jload(i2p)
        two = []
        for fn in FEATURES:
            h = next((r for r in rows if r["feature"] == fn and r["outcome"] == "harmful_compliance"), None)
            a_ = next((r for r in i2["table_all_graded"] if r["feature"] == fn and r["outcome"] == "harmful_compliance"), None)
            s_ = next((r for r in i2["table_selection_like"] if r["feature"] == fn and r["outcome"] == "harmful_compliance"), None)
            if h is None:
                continue
            sgn = lambda v: (0 if v is None or v != v else int(np.sign(v)))  # noqa: E731
            two.append({"feature": fn, "readout_class": h["readout_class"], "expected_sign": h["expected_sign"],
                        "rho_heldout": h["rho"], "n_heldout": h["n"], "ci95_heldout": h.get("ci95_ckpt"),
                        "rho_iter2_all_graded": a_["rho"] if a_ else None, "n_iter2_all": a_["n"] if a_ else None,
                        "ci95_iter2_all": a_.get("ci95_ckpt") if a_ else None,
                        "rho_iter2_selection_like": s_["rho"] if s_ else None, "n_iter2_sel": s_["n"] if s_ else None,
                        "same_sign_heldout_vs_iter2_all": (sgn(h["rho"]) == sgn(a_["rho"]) and sgn(h["rho"]) != 0) if a_ else None,
                        "same_sign_heldout_vs_iter2_sel": (sgn(h["rho"]) == sgn(s_["rho"]) and sgn(h["rho"]) != 0) if s_ else None})
        jdump({"utc": utc_now(), "note": ("held-out rho vs same-code rho on the iteration-2 screen panel, outcome = harmful "
                                          "compliance; NO winner, NO selection -- a replication/sign table for every row"),
               "rows": two}, RESULTS / "two_panel_table.json")
    logger.info(f"scored {len(feats)} checkpoints; {len(rows)} table rows; screen survivor found: {bool(sv)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
