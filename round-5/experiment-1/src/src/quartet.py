#!/usr/bin/env python3
"""Commissioned four-way Qwen3-4B activation comparison (array-only, no GPU).

Arms (iteration-2 harvest, same 256-row stimuli order as iteration 4):
    Base = Qwen/Qwen3-4B-Base, instruct = Qwen/Qwen3-4B, SafeRL = Qwen/Qwen3-4B-SafeRL,
    abliterated = mlabonne/Qwen3-4B-abliterated, CONTROL = CohenQu STaR non-safety fine-tune of Base.
Per band (prereg band rule): request axis F (XSTest harmful twins vs dolly), benign-twin axis N6
(harmful twins vs their benign twins), the standard abliteration-recipe axis F_easy (advbench vs
dolly), their raw and residual-norm-relative magnitudes, cross-arm |cos|, and cross-projection
separations (how well each arm's activations separate H from P along ANOTHER arm's axis).
Descriptive geometry of the commissioned models; no outcome is read. Writes
results/screen/quartet_tierA.json.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import band_indices, cohens_d_pooled, unit, utc_now  # noqa: E402

RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
H2 = RUN / "iter_2/gen_art/gen_art_experiment_1/harvest"
I4 = RUN / "iter_4/gen_art/gen_art_experiment_1"
RES = WS / "results"
ARMS = {"Base": "Qwen--Qwen3-4B-Base", "instruct": "Qwen--Qwen3-4B", "SafeRL": "Qwen--Qwen3-4B-SafeRL",
        "abliterated": "mlabonne--Qwen3-4B-abliterated", "STaR_control": "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6"}
PAIRS = [("instruct", "SafeRL"), ("instruct", "abliterated"), ("Base", "instruct"), ("Base", "SafeRL"),
         ("Base", "abliterated"), ("instruct", "STaR_control"), ("Base", "STaR_control"), ("SafeRL", "abliterated")]

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(WS / "logs/quartet.log", rotation="30 MB", level="DEBUG")


def main() -> None:
    stim = json.loads((I4 / "assets/stimuli.json").read_text())["rows"]
    src = np.array([r["source"] for r in stim])
    row_of = {r["stim_id"]: i for i, r in enumerate(stim)}
    pairs = json.loads((RES / "items/twin_pairs.json").read_text())
    H = [row_of[p["harm_stim_id"]] for p in pairs]
    Bn = [row_of[p["benign_stim_id"]] for p in pairs]
    P = list(np.where(src == "databricks_dolly_15k")[0])
    He = list(np.where(src == "advbench_harmful_behaviors")[0])
    arm_data: dict[str, dict] = {}
    for arm, tag in ARMS.items():
        d = H2 / tag
        A = np.load(d / "A_prompt.npy", mmap_mode="r")
        L = A.shape[1] - 1
        per_band = []
        for b in range(1, 7):
            lo, hi = band_indices(L, b)
            X = np.asarray(A[:, lo: hi + 1, :], dtype=np.float32).mean(axis=1).astype(np.float64)
            mH, mBn, mP, mHe = X[H].mean(0), X[Bn].mean(0), X[P].mean(0), X[He].mean(0)
            rn = float(np.linalg.norm(X[P + H + Bn], axis=1).mean())
            per_band.append({"band": b, "lo": lo, "hi": hi, "X": X,
                             "F": mH - mP, "N6": mH - mBn, "F_easy": mHe - mP, "resid_norm": rn})
        arm_data[arm] = {"tag": tag, "L": L, "d": A.shape[2], "bands": per_band}
        logger.info(f"{arm}: L={L} d={A.shape[2]}")
    out: dict = {"utc": utc_now(), "arms": ARMS,
                 "classes": {"H": "40 XSTest harmful twins", "Bn": "their 40 benign twins", "P": "48 dolly",
                             "H_easy": "48 advbench (standard abliteration-recipe contrast)"},
                 "per_arm": {}, "cross_arm": {}, "cross_projection": {}}
    for arm, ad in arm_data.items():
        rows = []
        for bd in ad["bands"]:
            X = bd["X"]
            rec = {"band": bd["band"], "hidden_idx": [bd["lo"], bd["hi"]], "resid_norm_mean": bd["resid_norm"]}
            for k in ("F", "N6", "F_easy"):
                v = bd[k]
                rec[f"|{k}|"] = float(np.linalg.norm(v))
                rec[f"|{k}|/resid"] = float(np.linalg.norm(v) / bd["resid_norm"])
            u = unit(bd["F"])
            rec["d_F(H vs P)"] = cohens_d_pooled(X[H] @ u, X[P] @ u)
            un = unit(bd["N6"])
            rec["d_N6(H vs Bn)"] = cohens_d_pooled(X[H] @ un, X[Bn] @ un)
            rec["cos(F,N6)"] = float(abs(unit(bd["F"]) @ unit(bd["N6"])))
            rec["cos(F,F_easy)"] = float(abs(unit(bd["F"]) @ unit(bd["F_easy"])))
            rows.append(rec)
        out["per_arm"][arm] = rows
    for a, b in PAIRS:
        rows = []
        for ba, bb in zip(arm_data[a]["bands"], arm_data[b]["bands"]):
            rec = {"band": ba["band"]}
            for k in ("F", "N6", "F_easy"):
                rec[f"cos_{k}"] = float(abs(unit(ba[k]) @ unit(bb[k])))
                na, nb = float(np.linalg.norm(ba[k])), float(np.linalg.norm(bb[k]))
                rec[f"norm_ratio_{k}({b}/{a})"] = nb / na if na > 0 else None
            rows.append(rec)
        out["cross_arm"][f"{a}~{b}"] = rows
    # cross-projection: separation of arm B's activations along arm A's F axis vs its own axis
    for a, b in PAIRS:
        rows = []
        for ba, bb in zip(arm_data[a]["bands"], arm_data[b]["bands"]):
            ua, ub = unit(ba["F"]), unit(bb["F"])
            Xb = bb["X"]
            rows.append({"band": ba["band"],
                         f"d_H_vs_P of {b} along own F": cohens_d_pooled(Xb[H] @ ub, Xb[P] @ ub),
                         f"d_H_vs_P of {b} along {a}'s F": cohens_d_pooled(Xb[H] @ ua, Xb[P] @ ua)})
        out["cross_projection"][f"{b}_on_{a}"] = rows
    # tier-A candidates and bars of each arm (already computed by tierA.py)
    out["tierA_candidates"] = {}
    for arm, tag in ARMS.items():
        p = RES / f"screen/tierA/{tag}.json"
        if p.exists():
            r = json.loads(p.read_text())
            out["tierA_candidates"][arm] = {"registered": r.get("registered"), "bstar_read": r.get("bstar_read"),
                                            "bars": {k: v for k, v in (r.get("bars") or {}).items()
                                                     if k in ("BL1_easy", "BL1_hard", "BL1_truelogit", "N1", "N6",
                                                              "C7", "C13_peak_d", "N11", "AMS_T1_sigma", "plain_diffmeans")}}
    (RES / "screen").mkdir(parents=True, exist_ok=True)
    (RES / "screen/quartet_tierA.json").write_text(json.dumps(out, indent=1, default=float))
    ab = out["cross_arm"]["instruct~abliterated"]
    logger.info("instruct~abliterated cos_F per band: " + ", ".join(f"{r['cos_F']:.3f}" for r in ab))
    logger.info("instruct~abliterated |F| ratio per band: " + ", ".join(f"{r['norm_ratio_F(abliterated/instruct)']:.3f}" for r in ab))
    isr = out["cross_arm"]["instruct~SafeRL"]
    logger.info("instruct~SafeRL cos_F per band: " + ", ".join(f"{r['cos_F']:.3f}" for r in isr))


if __name__ == "__main__":
    main()
