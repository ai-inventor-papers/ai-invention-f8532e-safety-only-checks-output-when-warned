"""Turn the substrate into concrete token-level sequences for one tokenizer."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from engine import Planner, Seq                                   # noqa: E402
from common import CONT_LEN                                        # noqa: E402

FAMS = ("F1", "F2")


def build_all(sub, tok, is_instruct, n_items=None, cont_len=CONT_LEN):
    P = Planner(tok, is_instruct, cont_len)
    items = sub["items"][:n_items] if n_items else sub["items"]
    S = {}

    # ---- item 2x2 cells + coherence + placebo  (kind='item')
    seqs = []
    for it in items:
        pk = it["pair_key"]
        for fam in FAMS:
            for pf, ptag in (("haz", "hazardous"), ("ben", "benign"),
                             ("plc", "placebo"), ("coh", "coherence")):
                cont = it["prefixes"][f"{pf}_{fam}"]
                reqs = [("harmful", it["harmful_request"]), ("benign", it["benign_request"])]
                if pf in ("plc", "coh"):
                    reqs = [("benign", it["benign_request"])]
                for rtag, req in reqs:
                    seqs.append(P.make(f"item|{pk}|{fam}|{ptag}|{rtag}", "item", req, cont,
                                       {"pair_key": pk, "family": fam, "prefix": ptag,
                                        "request": rtag, "item_family": it["family"]}))
    S["item"] = seqs

    # ---- r_content fitting corpus (kind='fit_content')
    seqs = []
    for r in sub["fit_content"]:
        for fam in FAMS:
            for pf, ptag in (("haz_prefix", "hazardous"), ("ben_prefix", "benign")):
                seqs.append(P.make(f"fitc|{r['fit_id']}|{fam}|{ptag}", "fit_content",
                                   r["request"], r[f"{pf}_{fam}"],
                                   {"fit_id": r["fit_id"], "family": fam, "prefix": ptag}))
    S["fit_content"] = seqs

    # ---- r_ablit fitting requests (prompt-only)
    seqs = []
    for lab, key in ((1, "harmful"), (0, "harmless")):
        for i, q in enumerate(sub["fit_ablit"][key]):
            seqs.append(P.make(f"abl|{key}|{i}", "fit_ablit", q, None, {"label": lab, "set": key}))
    S["fit_ablit"] = seqs

    # ---- held-out damage requests (prompt-only)
    seqs = []
    for lab, key in ((1, "harmful"), (0, "harmless")):
        for i, q in enumerate(sub["heldout_damage"][key]):
            seqs.append(P.make(f"dmg|{key}|{i}", "damage", q, None, {"label": lab, "set": key}))
    S["damage"] = seqs

    # ---- DIAGNOSTIC (declared addition): matched-behaviour request axis
    addf = Path(__file__).resolve().parent.parent / "out" / "substrate_addendum.json"
    if addf.exists():
        import json as _json
        add = _json.loads(addf.read_text())
        seqs = []
        for pr in add["pairs"]:
            seqs.append(P.make(f"dmgm|h|{pr['index']}", "damage_matched", pr["harmful"], None,
                               {"label": 1, "index": pr["index"], "category": pr["category"]}))
            seqs.append(P.make(f"dmgm|b|{pr['index']}", "damage_matched", pr["benign"], None,
                               {"label": 0, "index": pr["index"], "category": pr["category"]}))
        S["damage_matched"] = seqs

    # ---- neutral / contentless set (K2 prior, K3 footprint) - NO harmful text
    neutral_cont = sub["items"][0]["prefixes"]["plc_F2"]
    seqs = [P.make("neut|empty", "neutral", "", neutral_cont, {"which": "empty"})]
    for i, q in enumerate(sub["neutral_requests"]):
        seqs.append(P.make(f"neut|{i}", "neutral", q, neutral_cont, {"which": "factual"}))
    S["neutral"] = seqs

    # ---- graded-harm ladder (K2 slope): request varies, continuation fixed per item
    seqs = []
    for it in items:
        cont = it["prefixes"]["ben_F2"]
        for r, q in enumerate(it["ladder"]):
            seqs.append(P.make(f"lad|{it['pair_key']}|{r}", "ladder", q, cont,
                               {"pair_key": it["pair_key"], "rung": r}))
    S["ladder"] = seqs

    # ---- K4: ONE fixed continuation, per-position decay, under both requests
    seqs = []
    for it in items:
        for rtag, req in (("harmful", it["harmful_request"]), ("benign", it["benign_request"])):
            seqs.append(P.make(f"k4|{it['pair_key']}|{rtag}", "k4", req, sub["k4_continuation"],
                               {"pair_key": it["pair_key"], "request": rtag}))
    S["k4"] = seqs

    # ---- K5 domain profile
    seqs = []
    dom_cont = sub["items"][1]["prefixes"]["ben_F2"]
    for i, r in enumerate(sub["domain_set"]):
        seqs.append(P.make(f"dom|{i}", "domain", r["prompt"], dom_cont,
                           {"domain": r["domain"], "i": i}))
    S["domain"] = seqs
    return S, P
