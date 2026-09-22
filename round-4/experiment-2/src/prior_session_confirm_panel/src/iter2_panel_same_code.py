"""ADDITIONAL ANALYSIS (not a selection step): score THIS artifact's exact candidate code on the
iteration-2 SCREEN panel's saved activations (read-only), so every candidate has a same-code Spearman
rho on the screen panel beside its rho on the held-out panel. No winner is named; the table is a
two-panel sign/size comparison for every candidate and bar.

Behaviour on the iteration-2 panel = the Lane C 45/45 columns recorded in H2 results/pairs_effective.json
(the screen's own outcome source; mlabonne from the judge extension). venkycs (INVALID_LOAD: 168
random-init linears) and CohenQu (no behaviour) are excluded; the leaked StableLM/SmolLM2 rows are kept
and flagged, and a SELECTION-16 subset (graded + A_resp + valid, the screen plan's panel) is reported too.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import H2, RESULTS, jdump, jload, setup_logging, slug, utc_now  # noqa: E402
from loguru import logger  # noqa: E402

INVALID = {"venkycs/SmolLM2-1.7B-Instruct-Abliterated"}
LEAKED = {"stabilityai/stablelm-2-1_6b-chat", "hereticness/heretic_stablelm-2-1_6b-chat",
          "HuggingFaceTB/SmolLM2-1.7B-Instruct"}


def panel_rows() -> list[dict]:
    pe = jload(H2 / "results/pairs_effective.json")
    rows = {}
    for p in pe["pairs"]:
        for side in ("parent", "child"):
            b = p.get(f"{side}_behaviour")
            rows[p[side]] = {"repo": p[side], "family": p["family"], "role": "instruct" if side == "parent" else "edited_child",
                             "behaviour": b}
    for s in pe["singles"]:
        rows.setdefault(s["repo"], {"repo": s["repo"], "family": s["family"], "role": s["role"], "behaviour": s.get("behaviour")})
    return list(rows.values())


def main() -> None:
    setup_logging("iter2_same_code")
    import candidates as cand
    import stats_panel as sp
    stim = jload(H2 / "assets/stimuli.json")["rows"]
    cells = jload(H2 / "assets/cells.json")["cells"]
    root = H2 / "harvest"
    out_rows, feats = [], {}
    cache_p = RESULTS / "iter2_panel_features_cache.json"
    cache = jload(cache_p) if cache_p.exists() else {}
    for r in panel_rows():
        tag = slug(r["repo"])
        if r["repo"] in INVALID or not r.get("behaviour") or not (root / tag / "DONE").exists():
            out_rows.append({**{k: r[k] for k in ("repo", "family", "role")}, "scored": False,
                             "reason": "INVALID_LOAD" if r["repo"] in INVALID else ("no behaviour" if not r.get("behaviour") else "not harvested")})
            continue
        if tag in cache:
            f = cache[tag]
        else:
            logger.info(f"scoring iteration-2 tag {tag}")
            f = cand.compute_all(tag, stim, cells, None, root=root)
            f["C1_k4"] = f["C1_kcurve"]["4"]["mean"]
            f["C1_k8"] = f["C1_kcurve"]["8"]["mean"]
            f.pop("curves", None)
            cache[tag] = f
            jdump(cache, cache_p)
        feats[r["repo"]] = f
        out_rows.append({**{k: r[k] for k in ("repo", "family", "role")}, "scored": True,
                         "has_A_resp": (root / tag / "A_resp.npy").exists(), "leaked_family": r["repo"] in LEAKED,
                         "behaviour": r["behaviour"]})
    names = [x for x in __import__("score").FEATURES]
    outc = {r["repo"]: {"harmful_compliance": r["behaviour"]["harmful_compliance_rate"],
                        "over_refusal": r["behaviour"]["over_refusal_rate"],
                        "safe_engagement": r["behaviour"]["safe_engagement_rate"]}
            for r in out_rows if r.get("scored")}
    fams = {r["repo"]: r["family"] for r in out_rows if r.get("scored")}
    tab_all = sp.table(feats, outc, fams, names, ["harmful_compliance", "over_refusal", "safe_engagement"],
                       cand.READOUT_CLASS, cand.EXPECTED_SIGN_VS_HC, None, set(), B=2000)
    sel = {k: v for k, v in feats.items() if k not in LEAKED and (root / slug(k) / "A_resp.npy").exists()}
    tab_sel = sp.table(sel, {k: outc[k] for k in sel}, {k: fams[k] for k in sel}, names, ["harmful_compliance"],
                       cand.READOUT_CLASS, cand.EXPECTED_SIGN_VS_HC, None, set(), B=2000)
    jdump({"utc": utc_now(), "note": "same candidate code as the held-out panel; no selection, no winner",
           "n_scored_all": len(feats), "n_selection_like": len(sel), "panel": out_rows,
           "table_all_graded": tab_all, "table_selection_like": tab_sel}, RESULTS / "iter2_panel_same_code.json")
    logger.info(f"iteration-2 panel scored with held-out code: {len(feats)} checkpoints ({len(sel)} selection-like)")


if __name__ == "__main__":
    main()
