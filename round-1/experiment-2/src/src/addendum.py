"""DECLARED ADDITION (diagnostic only; prereg.json is NOT modified).

The registered PRIMARY damage variable came back FLAT AT CEILING (AUROC 1.000 at
every alpha). Two diagnostics are added to explain why, neither of which replaces
a registered readout:

 A1  A MATCHED-BEHAVIOUR request axis. JailbreakBench JBB-Behaviors ships 100
     harmful and 100 benign goals matched on Behavior and Category, so topic and
     phrasing are controlled in a way AdvBench-vs-Alpaca is not. If the ceiling is
     a corpus property rather than a property of the model, it should drop here.

 A2  THE ONE-DIMENSIONAL AXIS READOUT. AUROC of the held-out requests scored by
     their projection on the PINNED u alone. A rank-one lesion must collapse this
     by construction; a 2560-dimensional probe need not. Reporting both separates
     "the lesion did nothing" from "the probe routed around the lesion".
"""
from __future__ import annotations
import glob, hashlib, json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "out"


def main():
    import datasets
    rows = {}
    for split in ("harmful", "benign"):
        f = glob.glob("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/.shared_cache/hf/datasets/"
                      f"JailbreakBench___jbb-behaviors/behaviors/*/*/jbb-behaviors-{split}.arrow")[0]
        ds = datasets.Dataset.from_file(f)
        rows[split] = [{"prompt": r["Goal"].strip(), "behavior": r["Behavior"],
                        "category": r["Category"], "index": r["Index"]} for r in ds]
    # matched pairs share Index/Behavior across the two splits
    hidx = {r["index"]: r for r in rows["harmful"]}
    bidx = {r["index"]: r for r in rows["benign"]}
    common = sorted(set(hidx) & set(bidx), key=lambda x: int(x))
    pairs = [{"index": i, "harmful": hidx[i]["prompt"], "benign": bidx[i]["prompt"],
              "behavior": hidx[i]["behavior"], "category": hidx[i]["category"],
              "behavior_matched": hidx[i]["behavior"] == bidx[i]["behavior"]} for i in common]
    sub = json.loads((OUT / "substrate.json").read_text())
    twin_strings = {t["benign_request"] for t in sub["twins"]} | {t["harmful_request"] for t in sub["twins"]}
    abl = set(sub["fit_ablit"]["harmful"]) | set(sub["fit_ablit"]["harmless"])
    dmg = set(sub["heldout_damage"]["harmful"]) | set(sub["heldout_damage"]["harmless"])
    used = twin_strings | abl | dmg
    pairs = [p for p in pairs if p["harmful"] not in used and p["benign"] not in used]
    add = {
        "purpose": "diagnostic addition; prereg.json unchanged",
        "n_pairs": len(pairs),
        "behavior_matched_frac": sum(p["behavior_matched"] for p in pairs) / max(len(pairs), 1),
        "disjoint_from_registered_sets": True,
        "pairs": pairs,
        "source": "JailbreakBench/JBB-Behaviors (cached arrow): harmful + benign, matched on Index/Behavior/Category",
    }
    (OUT / "substrate_addendum.json").write_text(json.dumps(add, indent=1))
    print(json.dumps({k: v for k, v in add.items() if k != "pairs"}, indent=1))
    print("example pair:", json.dumps(pairs[0], indent=1))
    # prereg must be untouched
    cur = hashlib.sha256((OUT / "prereg.json").read_text().encode()).hexdigest()
    print("prereg sha now :", cur)
    print("prereg sha orig:", (OUT / "prereg.sha256").read_text().strip())
    assert cur == (OUT / "prereg.sha256").read_text().strip(), "PREREG CHANGED"


if __name__ == "__main__":
    main()
