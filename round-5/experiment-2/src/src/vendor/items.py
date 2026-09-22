#!/usr/bin/env python3
"""STEP 0/2 -- every prompt set this artifact uses, built ONCE, hash-disjoint, before any model is loaded.

behaviour items (assets/behaviour_items.json)
    harm   = Lane C gt_harm (45, subset laneC)  + XSTest UNSAFE twin members (subset xs)
    benign = Lane C gt_benign (45, subset laneC) + the matching XSTest SAFE twin members (subset xs)
    XSTest twins come from D1 data_out.json table safety_2x2, rows with metadata_confirmatory==True AND
    metadata_qc_fail==False (85 pairs); CPU fallback F-1 keeps the FIRST 40 pairs by pair uid after the hash
    filters. D1 heldout_cells.json and Lane C reserved_54.json are NEVER opened.
side sets (assets/side_sets.json), all hash-disjoint from the H2 readout stimuli (EASY/HARD) and the behaviour items:
    lesion_fit (64 AdvBench + 64 Dolly), lesion_val (16 + 16), hbar_32 (Dolly, W_U edits),
    sanity_32 (Dolly, fp16/int8 first-token agreement), lora_rows (1,200 Dolly, 5 categories, harm-regex clean),
    dpo_rows (400 Dolly; recorded, unused on the CPU fallback).
"""
from __future__ import annotations

import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ASSETS, D1, D2, H2, I3, LANEC, RESULTS, SEED, jdump, jload, prompt_hash,  # noqa: E402
                    setup_logging, sha256_file, sha256_str, utc_now)
from loguru import logger  # noqa: E402

N_XS_PAIRS_CPU = 40
HARM_RE = re.compile(r"weapon|drug|kill|bomb|hack|poison|suicide|explos|steal", re.I)
LORA_CATS = {"closed_qa", "information_extraction", "summarization", "classification", "open_qa"}


def xstest_twins() -> list[dict]:
    d1 = jload(D1 / "data_out.json")
    rows = next(D["examples"] for D in d1["datasets"] if D["dataset"].endswith("::safety_2x2"))
    pairs: dict[str, dict] = {}
    for r in rows:
        if str(r.get("metadata_confirmatory")) != "True" or str(r.get("metadata_qc_fail")) != "False":
            continue
        if str(r.get("metadata_sealed")) == "True":
            continue
        uid = r["metadata_pair_uid"]
        lvl = r["metadata_request_level"]
        p = pairs.setdefault(uid, {"pair_uid": uid, "family": r.get("metadata_family"),
                                   "harm_domain": r.get("metadata_harm_domain"),
                                   "minimal_edit_tier": r.get("metadata_minimal_edit_tier")})
        key = "unsafe" if lvl == "harmful" else "safe"
        if key in p and p[key] != r["metadata_request_text"]:
            raise ValueError(f"pair {uid}: two different {key} texts")
        p[key] = r["metadata_request_text"]
    out = [p for p in pairs.values() if "unsafe" in p and "safe" in p]
    return sorted(out, key=lambda p: p["pair_uid"])


def main() -> None:
    setup_logging("items")
    rng = random.Random(SEED)
    harm = jload(LANEC / "assets/gt_harm.json")
    ben = jload(LANEC / "assets/gt_benign.json")
    stim = jload(H2 / "assets/stimuli.json")["rows"]
    stim_h = {prompt_hash(s["text"]) for s in stim}
    items = []
    for r in harm:
        items.append({"item_id": r["gt_id"], "set": "harm", "subset": "laneC", "harmful": 1,
                      "prompt": r["prompt"], "category": r.get("category")})
    for r in ben:
        items.append({"item_id": r["gt_id"], "set": "benign", "subset": "laneC", "harmful": 0,
                      "prompt": r["prompt"], "category": r.get("category")})
    seen = {prompt_hash(x["prompt"]) for x in items}
    overlap_laneC_stim = [x["item_id"] for x in items if prompt_hash(x["prompt"]) in stim_h]
    dropped = {"xs_pair_overlaps_laneC": [], "xs_pair_overlaps_stimuli": [], "laneC_overlaps_stimuli": overlap_laneC_stim}
    twins = xstest_twins()
    n_twins_available = len(twins)
    kept_pairs = []
    for p in twins:
        hu, hs = prompt_hash(p["unsafe"]), prompt_hash(p["safe"])
        if hu in seen or hs in seen:
            dropped["xs_pair_overlaps_laneC"].append(p["pair_uid"])
            continue
        if hu in stim_h or hs in stim_h:
            dropped["xs_pair_overlaps_stimuli"].append(p["pair_uid"])
            continue
        kept_pairs.append(p)
        seen |= {hu, hs}
    n_xs_eligible = len(kept_pairs)
    kept_pairs = kept_pairs[:N_XS_PAIRS_CPU]
    for k, p in enumerate(kept_pairs):
        items.append({"item_id": f"xs{k:03d}_u", "set": "harm", "subset": "xs", "harmful": 1, "prompt": p["unsafe"],
                      "category": p["family"], "pair_uid": p["pair_uid"], "harm_domain": p["harm_domain"]})
    for k, p in enumerate(kept_pairs):
        items.append({"item_id": f"xs{k:03d}_s", "set": "benign", "subset": "xs", "harmful": 0, "prompt": p["safe"],
                      "category": p["family"], "pair_uid": p["pair_uid"], "harm_domain": p["harm_domain"]})
    # Lane C items that collide with the readout stimuli are DROPPED from the behaviour set (plan section 2)
    if overlap_laneC_stim:
        items = [x for x in items if x["item_id"] not in set(overlap_laneC_stim)]
    ids = [x["item_id"] for x in items]
    assert len(ids) == len(set(ids)), "duplicate item ids"
    beh_h = {prompt_hash(x["prompt"]) for x in items}
    assert not (beh_h & stim_h), "behaviour items overlap the readout stimuli"

    # ---- side sets from D1 full corpora (AdvBench 520, Dolly 2000)
    d1f = jload(D1 / "full_data_out.json")
    dsx = {D["dataset"]: D["examples"] for D in d1f["datasets"]}
    adv = [r["input"] for r in dsx["advbench_harmful_behaviors"]]
    dolly = dsx["databricks_dolly_15k"]
    used = set(stim_h) | beh_h
    adv_pool = [t for t in adv if prompt_hash(t) not in used]
    rng.shuffle(adv_pool)
    dolly_short = [r for r in dolly if len(r["input"]) <= 600]
    dolly_pool = [r for r in dolly_short if prompt_hash(r["input"]) not in used and not HARM_RE.search(r["input"])]
    rng.shuffle(dolly_pool)
    take = lambda pool, n: [pool.pop() for _ in range(n)]  # noqa: E731
    lesion_fit_h, lesion_val_h = take(adv_pool, 64), take(adv_pool, 16)
    dp = list(dolly_pool)
    lesion_fit_b = [r["input"] for r in take(dp, 64)]
    lesion_val_b = [r["input"] for r in take(dp, 16)]
    hbar_32 = [r["input"] for r in take(dp, 32)]
    sanity_32 = [r["input"] for r in take(dp, 32)]
    lora_pool = [r for r in dp if r.get("metadata_dolly_category") in LORA_CATS
                 and not HARM_RE.search(r["input"] + " " + r["output"])]
    lora_rows = [{"prompt": r["input"], "response": r["output"], "category": r["metadata_dolly_category"]}
                 for r in lora_pool[:1200]]
    lora_h = {prompt_hash(r["prompt"]) for r in lora_rows}
    dpo_rows = [{"prompt": r["input"], "response": r["output"]} for r in lora_pool[1200:1600]]
    side = {"lesion_fit": {"harm": lesion_fit_h, "benign": lesion_fit_b},
            "lesion_val": {"harm": lesion_val_h, "benign": lesion_val_b},
            "hbar_32": hbar_32, "sanity_32": sanity_32, "lora_rows": lora_rows, "dpo_rows": dpo_rows}
    all_side = set()
    for lst in (lesion_fit_h, lesion_val_h, lesion_fit_b, lesion_val_b, hbar_32, sanity_32):
        hs = {prompt_hash(t) for t in lst}
        assert not (hs & used), "side set overlaps stimuli/behaviour"
        assert not (hs & all_side), "side sets overlap each other"
        all_side |= hs
    assert not (lora_h & (used | all_side)), "LoRA rows overlap"

    doc = {"n_items": len(items), "n_harm": sum(x["harmful"] for x in items),
           "n_benign": sum(1 - x["harmful"] for x in items),
           "n_laneC": sum(x["subset"] == "laneC" for x in items), "n_xs": sum(x["subset"] == "xs" for x in items),
           "n_xs_pairs_available_confirmatory_qc_ok": n_twins_available, "n_xs_pairs_eligible_after_hash_filters": n_xs_eligible,
           "n_xs_pairs_used": len(kept_pairs), "cpu_fallback_rule": f"first {N_XS_PAIRS_CPU} eligible pairs by pair_uid",
           "dropped": dropped, "item_id_list_sha256": sha256_str("\n".join(ids)), "items": items,
           "never_opened": ["D1/heldout_cells.json", "LANEC/assets/reserved_54.json"], "utc": utc_now()}
    jdump(doc, ASSETS / "behaviour_items.json")
    jdump({"sizes": {k: (len(v) if isinstance(v, list) else {kk: len(vv) for kk, vv in v.items()}) for k, v in side.items()},
           "harm_regex": HARM_RE.pattern, "lora_categories": sorted(LORA_CATS), "seed": SEED, **side},
          ASSETS / "side_sets.json")
    logger.info(f"behaviour items {len(items)} (harm {doc['n_harm']}, benign {doc['n_benign']}); "
                f"xs pairs available {n_twins_available}, eligible {n_xs_eligible}, used {len(kept_pairs)}; dropped {dropped}")
    logger.info(f"side sets: {doc and {k: (len(v) if isinstance(v, list) else 2 * len(v['harm'])) for k, v in side.items()}}")

    srcs = {
        "LANEC/lc_judge.py": LANEC / "lc_judge.py", "LANEC/assets/gt_harm.json": LANEC / "assets/gt_harm.json",
        "LANEC/assets/gt_benign.json": LANEC / "assets/gt_benign.json",
        "D1/data_out.json": D1 / "data_out.json", "D1/full_data_out.json": D1 / "full_data_out.json",
        "D2/full_data_out.json": D2 / "full_data_out.json",
        "H2/assets/stimuli.json": H2 / "assets/stimuli.json", "H2/assets/token_sets.json": H2 / "assets/token_sets.json",
        "H2/assets/cells.json": H2 / "assets/cells.json", "H2/prereg.json": H2 / "prereg.json",
        "I3/assets/c11_items.json": I3 / "assets/c11_items.json", "I3/prereg.json": I3 / "prereg.json",
        "I3/results/graded_truth.json": I3 / "results/graded_truth.json",
    }
    for sub in ("src_i3", "src_i3/h2", "src_h2"):
        for p in sorted((ASSETS.parent / sub).glob("*.py")):
            orig = (I3 / "src" / p.name) if sub == "src_i3" else (I3 / "src/h2" / p.name) if sub == "src_i3/h2" else (H2 / "src" / p.name)
            srcs[f"{sub}/{p.name} (copy of {orig})"] = p
    prov = {"utc": utc_now(), "files": {}}
    for k, p in srcs.items():
        prov["files"][k] = {"path": str(p), "sha256": sha256_file(p) if p.exists() else None, "exists": p.exists()}
    jdump(prov, RESULTS / "provenance.json")
    logger.info(f"provenance: {sum(v['exists'] for v in prov['files'].values())}/{len(srcs)} files hashed")


if __name__ == "__main__":
    main()
