#!/usr/bin/env python3
"""Reported sensitivity for the CONFIRMATION panel: lineage-cluster bootstrap of the primary margin.

The held-out panel mixes independent Hub checkpoints with several in-house edits of ONE parent
(the substrate's ERNIE-0.3B arms), so the registered checkpoint bootstrap over-counts independent
observations there too. This recomputes, for every candidate present in results/confirmation.json:
  rho(candidate, OR), rho(BL1_easy, OR), the margin |rho_cand| - |rho_BL1|,
under a bootstrap that resamples LINEAGES (all rows of a drawn lineage are kept). Registered
decisions continue to use the frozen rule; this is reported beside them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import utc_now  # noqa: E402
from statlib import rho_mde, spearman  # noqa: E402

RES = WS / "results"
B = 2000
SEED = 20260922


def lineage_of(tag: str) -> str:
    if tag.startswith("PB__"):
        return "L_" + tag.split("__")[1]          # every in-house arm of one parent -> one lineage
    t = tag[4:] if tag.startswith("HG__") else tag
    org = t.split("--")[0]
    name = t.split("--", 1)[1] if "--" in t else t
    base = name.lower().replace("-abliterated", "").replace("-heretic", "").replace("huihui-", "")
    return f"L_{org.lower()}_{base}" if "ernie" not in base else "L_ernie03b"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=RES)
    args = ap.parse_args()
    conf = json.loads((args.results_dir / "confirmation.json").read_text())
    table = conf.get("confirmation_table") or []
    rows = [r for r in table if isinstance(r.get("OR"), (int, float))]
    lin: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        lin.setdefault(lineage_of(r["tag"]), []).append(i)
    keys = sorted(lin)
    cands = [c for c in ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "G1", "G2", "G3", "G4", "A1", "A2", "A3")
             if any(isinstance(r.get(c), (int, float)) for r in rows)]
    rng = np.random.default_rng(SEED)
    out = {"utc": utc_now(), "B": B, "seed": SEED, "n_rows": len(rows), "n_lineages": len(keys),
           "lineages": {k: [rows[i]["tag"] for i in v] for k, v in lin.items()},
           "mde_by_lineage_count": {"n_rows": rho_mde(len(rows)) if len(rows) > 4 else None,
                                    "n_lineages": rho_mde(len(keys)) if len(keys) > 4 else None},
           "note": "registered decisions use the checkpoint bootstrap in results/confirmation.json; this is a reported sensitivity",
           "candidates": {}}
    orv = [r["OR"] for r in rows]
    bl = [r.get("BL1_easy") for r in rows]
    for c in cands:
        cv = [r.get(c) for r in rows]
        ok = [i for i in range(len(rows)) if isinstance(cv[i], (int, float)) and isinstance(orv[i], (int, float))]
        if len(ok) < 5:
            out["candidates"][c] = {"status": "TOO_FEW", "n": len(ok)}
            continue
        rho_c = spearman([cv[i] for i in ok], [orv[i] for i in ok])["rho"]
        okb = [i for i in ok if isinstance(bl[i], (int, float))]
        rho_b = spearman([bl[i] for i in okb], [orv[i] for i in okb])["rho"] if len(okb) >= 5 else None
        margins, rcs = [], []
        for _ in range(B):
            pick = rng.integers(0, len(keys), len(keys))
            idx = [i for j in pick for i in lin[keys[j]]]
            ii = [i for i in idx if isinstance(cv[i], (int, float))]
            if len(set(ii)) < 5:
                continue
            rc = spearman([cv[i] for i in ii], [orv[i] for i in ii])["rho"]
            ib = [i for i in idx if isinstance(bl[i], (int, float))]
            rb = spearman([bl[i] for i in ib], [orv[i] for i in ib])["rho"] if len(set(ib)) >= 5 else None
            if rc is None or not np.isfinite(rc):
                continue
            rcs.append(rc)
            if rb is not None and np.isfinite(rb):
                margins.append(abs(rc) - abs(rb))
        out["candidates"][c] = {
            "n": len(ok), "rho_point": rho_c, "rho_BL1_easy_point": rho_b,
            "cluster_ci95_rho": [float(np.percentile(rcs, 2.5)), float(np.percentile(rcs, 97.5))] if len(rcs) > 50 else None,
            "margin_point": (abs(rho_c) - abs(rho_b)) if (rho_c is not None and rho_b is not None) else None,
            "cluster_ci95_margin_vs_BL1": [float(np.percentile(margins, 2.5)), float(np.percentile(margins, 97.5))] if len(margins) > 50 else None,
            "n_boot_ok": len(rcs)}
    # DISCLOSED post-hoc robustness check (not a registered rule): drop rows whose harmful-vs-benign
    # readout is degenerate (plain_DiM < 1.0 Cohen's d), because the W-family normaliser `gap` becomes
    # tiny there and inflates the candidate (e.g. pythia-410m, Pleias-1.2b: base models with no
    # refusal behaviour). Both versions are reported; the registered statistic is the full-panel one.
    keep = [i for i, r in enumerate(rows)
            if isinstance(r.get("plain_DiM"), (int, float)) and abs(r["plain_DiM"]) >= 1.0]
    dropped = [rows[i]["tag"] for i in range(len(rows)) if i not in keep]
    nd = {"rule": "drop rows with |plain_DiM| < 1.0 (degenerate harmful-vs-benign readout)",
          "n_kept": len(keep), "dropped_rows": dropped, "candidates": {}}
    for c in cands:
        ok = [i for i in keep if isinstance(rows[i].get(c), (int, float)) and isinstance(orv[i], (int, float))]
        if len(ok) < 5:
            nd["candidates"][c] = {"status": "TOO_FEW", "n": len(ok)}
            continue
        rc = spearman([rows[i][c] for i in ok], [orv[i] for i in ok])["rho"]
        okb = [i for i in ok if isinstance(bl[i], (int, float))]
        rb = spearman([bl[i] for i in okb], [orv[i] for i in okb])["rho"] if len(okb) >= 5 else None
        nd["candidates"][c] = {"n": len(ok), "rho": rc, "rho_BL1_easy": rb,
                               "margin_vs_BL1": (abs(rc) - abs(rb)) if (rc is not None and rb is not None) else None,
                               "mde": rho_mde(len(ok)) if len(ok) > 4 else None}
    out["non_degenerate_readout_sensitivity"] = nd
    (args.results_dir / "confirm_cluster_sensitivity.json").write_text(json.dumps(out, indent=1))
    for c, v in out["candidates"].items():
        print(c, v.get("rho_point"), v.get("cluster_ci95_rho"), "margin", v.get("margin_point"),
              v.get("cluster_ci95_margin_vs_BL1"))


if __name__ == "__main__":
    main()
