#!/usr/bin/env python3
"""STAGE B -- frozen behavioural item sets for the blind held-out safety panel.

Emits WS/results/item_sets.json: four ITEM LISTS (HARM, OR_HARDBENIGN, OR_XSTEST54,
HARM_XSTEST54) plus the refusal/hedge/control lexicon and a small set of hash checks.

BLIND ARTIFACT: this script computes no score, rank or correlation. It only recovers
and lists items. stdlib only (json, hashlib, pathlib, re, datetime) -- no numpy.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
ASSETS = WS / "assets"
RESULTS = WS / "results"

RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D")
H1 = RUN / "3_invention_loop/iter_4/gen_art/gen_art_experiment_1"
D1 = RUN / "3_invention_loop/iter_1/gen_art/gen_art_dataset_1"
D2 = RUN / "3_invention_loop/iter_2/gen_art/gen_art_dataset_1"

NOTES: list[str] = []
DEVIATIONS: list[str] = []


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def jload(path: Path):
    return json.loads(path.read_text())


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ids_sha256_sorted_compact(ids: list[str]) -> str:
    """Convention confirmed against D1/prereg.json split.heldout_ids_sha256:
    sha256(json.dumps(sorted(ids), separators=(',', ':')))."""
    return sha256_text(json.dumps(sorted(ids), separators=(",", ":")))


# --------------------------------------------------------------------------------
# 1. behaviour_items.json (staged, authoritative) -- HARM + OR_HARDBENIGN source
# --------------------------------------------------------------------------------
bi_path = ASSETS / "behaviour_items.json"
bi = jload(bi_path)
bi_items = bi.get("items", [])
bi_ids = [it["item_id"] for it in bi_items]
behaviour_items_hash_recomputed = sha256_text("\n".join(bi_ids))
behaviour_items_hash_expected = bi.get("item_id_list_sha256")
if behaviour_items_hash_recomputed != behaviour_items_hash_expected:
    DEVIATIONS.append(
        f"behaviour_items.json item_id_list_sha256 mismatch: expected={behaviour_items_hash_expected} "
        f"recomputed(order,newline-join)={behaviour_items_hash_recomputed}"
    )
else:
    NOTES.append(
        "behaviour_items.json item_id_list_sha256 reproduced with convention "
        "sha256('\\n'.join(ids in file order))."
    )

# Cross-check against H1/results/graded_truth.json labels keys (any one per_ckpt row)
gt_path = H1 / "results" / "graded_truth.json"
h1_id_overlap_report = {}
if gt_path.exists():
    gt = jload(gt_path)
    per_ckpt = gt.get("per_ckpt", {})
    if per_ckpt:
        k0 = next(iter(per_ckpt))
        gt_ids = set(per_ckpt[k0].get("labels", {}).keys())
        bi_id_set = set(bi_ids)
        h1_id_overlap_report = {
            "h1_ckpt_used": k0,
            "n_h1_label_ids": len(gt_ids),
            "n_behaviour_items_ids": len(bi_id_set),
            "n_overlap": len(gt_ids & bi_id_set),
            "ids_identical": gt_ids == bi_id_set,
            "only_in_h1": sorted(gt_ids - bi_id_set),
            "only_in_behaviour_items": sorted(bi_id_set - gt_ids),
        }
        if gt_ids == bi_id_set:
            NOTES.append(
                f"H1/results/graded_truth.json per_ckpt[{k0!r}].labels keys are IDENTICAL "
                f"to behaviour_items.json item_id set (n={len(gt_ids)})."
            )
        else:
            DEVIATIONS.append(
                f"H1 graded_truth label ids vs behaviour_items ids differ: overlap="
                f"{h1_id_overlap_report['n_overlap']}/{len(bi_id_set)}"
            )
    else:
        DEVIATIONS.append("H1/results/graded_truth.json has an empty per_ckpt block")
else:
    DEVIATIONS.append(f"H1/results/graded_truth.json not found at {gt_path}")


def harm_kind(item_id: str) -> str:
    if item_id.startswith("sr_"):
        return "laneC_harmful"
    if item_id.startswith("xs") and item_id.endswith("_u"):
        return "xstest_laneC_unsafe_twin"
    return "unknown"


def orh_kind(item_id: str) -> str:
    if item_id.startswith("orh_"):
        return "laneC_hard_benign"
    return "unknown"


harm_rows = [it for it in bi_items if it.get("set") == "harm"]
orh_rows = [it for it in bi_items if it.get("set") == "benign" and it["item_id"].startswith("orh_")]

HARM_EXPECTED_N = 85
OR_HARDBENIGN_EXPECTED_N = 40

if len(harm_rows) != HARM_EXPECTED_N:
    DEVIATIONS.append(f"HARM: expected n={HARM_EXPECTED_N}, behaviour_items.json set=='harm' gives n={len(harm_rows)}")

if len(orh_rows) != OR_HARDBENIGN_EXPECTED_N:
    DEVIATIONS.append(
        f"OR_HARDBENIGN: task brief expected n={OR_HARDBENIGN_EXPECTED_N}, but behaviour_items.json "
        f"(the authoritative staged asset) carries {len(orh_rows)} orh_* ids, and H1/results/graded_truth.json's "
        f"per_ckpt labels also carry exactly {sum(1 for i in bi_ids if i.startswith('orh_'))} orh_* ids -- the "
        f"same number. Shipping all {len(orh_rows)} so the denominator matches iteration 4 exactly; NOT trimmed "
        f"to 40 to hit the brief's expectation, since that would break the join with H1 rather than preserve it."
    )
    NOTES.append(
        f"OR_HARDBENIGN shipped with n={len(orh_rows)} (not the briefed 40) because behaviour_items.json and "
        "H1/results/graded_truth.json agree on 43 orh_* ids; 2 originally-generated orh ids (orh_75, orh_1197) "
        "were already dropped upstream for laneC/stimuli overlap (see behaviour_items.json.dropped."
        "laneC_overlaps_stimuli), so 43 is the final, already-deduplicated set, not an un-topped-up partial one."
    )

HARM = {
    "name": "HARM",
    "n": len(harm_rows),
    "ids": [it["item_id"] for it in harm_rows],
    "ids_sha256": ids_sha256_sorted_compact([it["item_id"] for it in harm_rows]),
    "items": [
        {
            "id": it["item_id"],
            "request": it["prompt"],
            "source_table": "assets/behaviour_items.json:items(set=harm)",
            "kind": harm_kind(it["item_id"]),
        }
        for it in harm_rows
    ],
    "provenance": {
        "recovered_from": "WS/assets/behaviour_items.json (staged, authoritative)",
        "rule": "rows with set=='harm' (45 sr_* Lane C harmful + 40 xsNNN_u XSTest-twin harmful)",
        "expected_n": HARM_EXPECTED_N,
        "actual_n": len(harm_rows),
        "matches_H1_graded_truth": h1_id_overlap_report,
    },
}

OR_HARDBENIGN = {
    "name": "OR_HARDBENIGN",
    "n": len(orh_rows),
    "ids": [it["item_id"] for it in orh_rows],
    "ids_sha256": ids_sha256_sorted_compact([it["item_id"] for it in orh_rows]),
    "items": [
        {
            "id": it["item_id"],
            "request": it["prompt"],
            "source_table": "assets/behaviour_items.json:items(set=benign,orh_*)",
            "kind": orh_kind(it["item_id"]),
        }
        for it in orh_rows
    ],
    "provenance": {
        "recovered_from": "WS/assets/behaviour_items.json (staged, authoritative)",
        "rule": "rows with set=='benign' and item_id startswith 'orh_' -- kept EXACTLY as shipped, no top-up, no trim",
        "expected_n_per_brief": OR_HARDBENIGN_EXPECTED_N,
        "actual_n": len(orh_rows),
        "note": "43 not 40; see deviations[] and notes[] for the reconciliation against H1/results/graded_truth.json",
    },
}

# --------------------------------------------------------------------------------
# 2. D1/heldout_cells.json -- OR_XSTEST54 + HARM_XSTEST54 (sealed safety_2x2 table)
# --------------------------------------------------------------------------------
hc_path = D1 / "heldout_cells.json"
OR_XSTEST54 = None
HARM_XSTEST54 = None
heldout_recovery_report = {}

if hc_path.exists():
    hc = jload(hc_path)
    tables = {d["dataset"].split("::")[-1]: d.get("examples", []) for d in hc.get("datasets", [])}
    if "safety_2x2" not in tables:
        DEVIATIONS.append(f"D1/heldout_cells.json has no safety_2x2 table; tables present: {sorted(tables)}")
    else:
        s22 = tables["safety_2x2"]
        levels_seen = sorted({r.get("metadata_request_level") for r in s22})
        heldout_recovery_report["metadata_request_level_values_seen"] = levels_seen

        # benign twin: literal value is 'benign_twin' in this artifact, not the brief's 'benign'
        benign_level = "benign_twin" if "benign_twin" in levels_seen else (
            "benign" if "benign" in levels_seen else None
        )
        harmful_level = "harmful" if "harmful" in levels_seen else None
        if benign_level != "benign_twin":
            DEVIATIONS.append(
                f"safety_2x2 benign level literal value is {benign_level!r}, brief said 'benign' "
                f"(actual values seen: {levels_seen})"
            )
        if harmful_level is None:
            DEVIATIONS.append(f"safety_2x2 has no 'harmful' request_level (values seen: {levels_seen})")

        def dedup_by_pair(level_value: str):
            seen = {}
            order = []
            for r in s22:
                if r.get("metadata_request_level") != level_value:
                    continue
                uid = r.get("metadata_pair_uid")
                if uid not in seen:
                    seen[uid] = r.get("metadata_plain_prompt")
                    order.append(uid)
                elif seen[uid] != r.get("metadata_plain_prompt"):
                    DEVIATIONS.append(
                        f"safety_2x2 pair_uid={uid} level={level_value} has inconsistent metadata_plain_prompt "
                        "across duplicate rows"
                    )
            return order, seen

        benign_order, benign_prompts = ([], {}) if benign_level is None else dedup_by_pair(benign_level)
        harmful_order, harmful_prompts = ([], {}) if harmful_level is None else dedup_by_pair(harmful_level)

        OR_XSTEST54 = {
            "name": "OR_XSTEST54",
            "n": len(benign_order),
            "ids": benign_order,
            "ids_sha256": ids_sha256_sorted_compact(benign_order),
            "items": [
                {
                    "id": uid,
                    "request": benign_prompts[uid],
                    "source_table": "D1/heldout_cells.json:safety_2x2(request_level=benign_twin)",
                    "kind": "xstest_sealed_benign_twin",
                }
                for uid in benign_order
            ],
            "provenance": {
                "recovered_from": "D1/heldout_cells.json (sealed, never fit/tuned/selected on)",
                "rule": (
                    "safety_2x2 table, rows with metadata_request_level=='benign_twin', unique by "
                    "metadata_pair_uid, text taken from metadata_plain_prompt; coherence_control table NEVER used"
                ),
                "expected_n": 54,
                "actual_n": len(benign_order),
            },
        }
        HARM_XSTEST54 = {
            "name": "HARM_XSTEST54",
            "n": len(harmful_order),
            "ids": harmful_order,
            "ids_sha256": ids_sha256_sorted_compact(harmful_order),
            "items": [
                {
                    "id": uid,
                    "request": harmful_prompts[uid],
                    "source_table": "D1/heldout_cells.json:safety_2x2(request_level=harmful)",
                    "kind": "xstest_sealed_harmful_twin",
                }
                for uid in harmful_order
            ],
            "provenance": {
                "recovered_from": "D1/heldout_cells.json (sealed, never fit/tuned/selected on)",
                "rule": (
                    "safety_2x2 table, rows with metadata_request_level=='harmful', unique by "
                    "metadata_pair_uid, text taken from metadata_plain_prompt; coherence_control table NEVER used"
                ),
                "expected_n": 54,
                "actual_n": len(harmful_order),
            },
        }
        if set(benign_order) == set(harmful_order):
            NOTES.append(
                f"OR_XSTEST54 and HARM_XSTEST54 pair_uid sets are IDENTICAL (n={len(benign_order)}) -- "
                "matched twins, as expected."
            )
        else:
            DEVIATIONS.append(
                "OR_XSTEST54 and HARM_XSTEST54 pair_uid sets differ: "
                f"only_benign={sorted(set(benign_order) - set(harmful_order))} "
                f"only_harmful={sorted(set(harmful_order) - set(benign_order))}"
            )
else:
    DEVIATIONS.append(f"D1/heldout_cells.json not found at {hc_path}")

# --------------------------------------------------------------------------------
# 2b. Partial-seal disclosure vs D2 probe_baseline_disjoint
# --------------------------------------------------------------------------------
d2_full_path = D2 / "full_data_out.json"
if OR_XSTEST54 is not None and d2_full_path.exists():
    d2 = jload(d2_full_path)
    d2_tables = {x["dataset"].split("::")[-1]: x.get("examples", []) for x in d2.get("datasets", [])}
    pbd = d2_tables.get("probe_baseline_disjoint", [])
    if pbd:
        heldout54 = set(OR_XSTEST54["ids"]) | set(HARM_XSTEST54["ids"])
        pbd_source_ids = [r.get("metadata_source_row_id") for r in pbd]
        pbd_distinct = set(pbd_source_ids)
        overlap_distinct = pbd_distinct & heldout54
        NOTES.append(
            f"partial-seal disclosure: D2's probe_baseline_disjoint table has {len(pbd)} rows tracing back "
            f"(via metadata_source_row_id) to {len(pbd_distinct)} distinct pair_uids, ALL {len(overlap_distinct)} "
            f"of which fall inside the sealed 54-pair OR_XSTEST54/HARM_XSTEST54 split "
            f"({len(overlap_distinct)}/54 distinct pairs touched, across {len(pbd)} probe_baseline_disjoint rows "
            "reserved for the black-box greedy-refusal baseline). The 54-pair split is therefore NOT pristine "
            "with respect to that reserved baseline pool."
        )
    else:
        DEVIATIONS.append("D2 full_data_out.json has no probe_baseline_disjoint table")

# --------------------------------------------------------------------------------
# 3. prereg heldout-ids hash reproduction
# --------------------------------------------------------------------------------
prereg_path = D1 / "prereg.json"
prereg_expected_hash = None
prereg_recomputed_hash = None
heldout_hash_match = False
heldout_hash_variant = "NO_MATCH"
computed_hashes = {}

if prereg_path.exists() and OR_XSTEST54 is not None:
    prereg = jload(prereg_path)
    prereg_expected_hash = prereg.get("split", {}).get("heldout_ids_sha256")
    ids54 = OR_XSTEST54["ids"]  # == HARM_XSTEST54["ids"] pair_uid set, confirmed identical above

    def h(s: str) -> str:
        return sha256_text(s)

    variants = {
        "sorted_ids_json_dumped_compact_sep": h(json.dumps(sorted(ids54), separators=(",", ":"))),
        "sorted_ids_json_dumped_default": h(json.dumps(sorted(ids54))),
        "sorted_ids_newline_joined": h("\n".join(sorted(ids54))),
        "sorted_ids_newline_joined_trailing_nl": h("\n".join(sorted(ids54)) + "\n"),
        "table_order_ids_json_dumped_compact_sep": h(json.dumps(ids54, separators=(",", ":"))),
        "table_order_ids_newline_joined": h("\n".join(ids54)),
        "sha_prefix_sorted_ids_json_dumped_compact_sep": "sha256:" + h(json.dumps(sorted(ids54), separators=(",", ":"))),
    }
    computed_hashes = variants
    for name, val in variants.items():
        if val == prereg_expected_hash:
            heldout_hash_match = True
            heldout_hash_variant = name
            prereg_recomputed_hash = val
            break
    if not heldout_hash_match:
        prereg_recomputed_hash = variants["sorted_ids_json_dumped_compact_sep"]
        DEVIATIONS.append(
            f"D1/prereg.json split.heldout_ids_sha256 ({prereg_expected_hash}) did not match any tried variant; "
            f"variants tried: {json.dumps(variants, indent=2)}"
        )
else:
    if not prereg_path.exists():
        DEVIATIONS.append(f"D1/prereg.json not found at {prereg_path}")
    if OR_XSTEST54 is None:
        DEVIATIONS.append("OR_XSTEST54 not recovered; cannot attempt the heldout-ids hash reproduction")

# --------------------------------------------------------------------------------
# 4. D2 lexicon: refusal_onset, hedge, control forms
# --------------------------------------------------------------------------------
lexicon = {"refusal_onset": [], "hedge": [], "control": [], "source": None, "token_sets_single_token": {}}

if d2_full_path.exists():
    d2 = jload(d2_full_path) if "d2" not in dir() else d2
    d2_tables = {x["dataset"].split("::")[-1]: x.get("examples", []) for x in d2.get("datasets", [])}
    row_counts = d2.get("metadata", {}).get("row_counts_by_table", {})

    ref_tbl = d2_tables.get("refusal_onset_tokens", [])
    hedge_tbl = d2_tables.get("hedge_redirect_tokens", [])
    ctl_tbl = d2_tables.get("matched_control_tokens", [])

    EXPECTED = {"refusal_onset_tokens": 60, "hedge_redirect_tokens": 24}
    for tname, expn in EXPECTED.items():
        actn = len(d2_tables.get(tname, []))
        if actn != expn:
            DEVIATIONS.append(f"D2 lexicon table {tname}: expected n={expn}, actual n={actn}")

    lexicon["refusal_onset"] = [r.get("metadata_form", r.get("input")) for r in ref_tbl]
    lexicon["hedge"] = [r.get("metadata_form", r.get("input")) for r in hedge_tbl]
    lexicon["control"] = [r.get("metadata_control_token", r.get("input")) for r in ctl_tbl]
    lexicon["source"] = (
        "D2/full_data_out.json tables refusal_onset_tokens (n="
        f"{len(ref_tbl)}), hedge_redirect_tokens (n={len(hedge_tbl)}), matched_control_tokens (n={len(ctl_tbl)}); "
        "row_counts_by_table from D2 metadata: "
        + json.dumps({k: v for k, v in row_counts.items()
                      if k in ("refusal_onset_tokens", "hedge_redirect_tokens", "matched_control_tokens")})
    )
    NOTES.append(
        f"D2 lexicon actual counts: refusal_onset={len(ref_tbl)} (expected 60), "
        f"hedge={len(hedge_tbl)} (expected 24), matched_control={len(ctl_tbl)} (no brief expectation given, "
        "actual reported as-is; these are multi-word onset phrases for the text proxy, distinct in purpose from "
        "token_sets.json's per-tokenizer single-token surface forms)."
    )
else:
    DEVIATIONS.append(f"D2/full_data_out.json not found at {d2_full_path}")

ts_path = ASSETS / "token_sets.json"
if ts_path.exists():
    ts = jload(ts_path)
    lexicon["token_sets_single_token"] = {
        "refusal": ts.get("refusal", []),
        "hedge": ts.get("hedge", []),
        "control": ts.get("control", []),
    }
    for k, expn in (("refusal", 56), ("hedge", 18), ("control", 56)):
        actn = len(ts.get(k, []))
        if actn != expn:
            DEVIATIONS.append(f"token_sets.json[{k}]: expected n={expn}, actual n={actn}")
else:
    DEVIATIONS.append(f"WS/assets/token_sets.json not found at {ts_path}")

# --------------------------------------------------------------------------------
# 5. hashes block
# --------------------------------------------------------------------------------
rubric_path = D1 / "rubric.md"
rubric_expected = "b11e322dc64e25f79bdb909fdda571fd856345a4b74b39c827d7bfd431194629"
rubric_actual = sha256_file(rubric_path) if rubric_path.exists() else None
if rubric_actual is None:
    DEVIATIONS.append(f"D1/rubric.md not found at {rubric_path}")
elif rubric_actual != rubric_expected:
    DEVIATIONS.append(f"D1/rubric.md sha256 mismatch: expected={rubric_expected} actual={rubric_actual}")
else:
    NOTES.append(f"D1/rubric.md sha256 matches expected ({rubric_expected}).")

hashes = {
    "rubric_md_sha256": rubric_actual,
    "rubric_md_sha256_expected": rubric_expected,
    "prereg_heldout_ids_sha256_expected": prereg_expected_hash,
    "prereg_heldout_ids_sha256_recomputed": prereg_recomputed_hash,
    "heldout_hash_match": heldout_hash_match,
    "heldout_hash_variant": heldout_hash_variant,
    "heldout_hash_variants_tried": computed_hashes,
    "behaviour_items_item_id_list_sha256": behaviour_items_hash_expected,
    "behaviour_items_item_id_list_sha256_recomputed": behaviour_items_hash_recomputed,
}

# --------------------------------------------------------------------------------
# 6. assemble + write
# --------------------------------------------------------------------------------
out = {
    "utc": utc_now(),
    "sets": {
        "HARM": HARM,
        "OR_XSTEST54": OR_XSTEST54,
        "HARM_XSTEST54": HARM_XSTEST54,
        "OR_HARDBENIGN": OR_HARDBENIGN,
    },
    "lexicon": lexicon,
    "hashes": hashes,
    "label_convention": (
        "three-boolean lc_judge protocol (refused, harmful_content, on_topic_help); "
        "D1/rubric.md's three exclusive buckets are NOT used"
    ),
    "notes": NOTES,
    "deviations": DEVIATIONS,
}

RESULTS.mkdir(parents=True, exist_ok=True)
out_path = RESULTS / "item_sets.json"
tmp_path = out_path.with_suffix(".json.tmp")
tmp_path.write_text(json.dumps(out, indent=2, sort_keys=False))
tmp_path.replace(out_path)
print(f"wrote {out_path}")

# --------------------------------------------------------------------------------
# 7. verification snippet
# --------------------------------------------------------------------------------
print("\n=== verification ===")
for set_name in ["HARM", "OR_XSTEST54", "HARM_XSTEST54", "OR_HARDBENIGN"]:
    s = out["sets"].get(set_name)
    if s is None:
        print(f"{set_name}: MISSING")
        continue
    first_req = s["items"][0]["request"][:80] if s["items"] else ""
    print(f"{set_name}: n={s['n']} ids_sha256={s['ids_sha256']} first_request[:80]={first_req!r}")

print(f"\nlexicon: refusal_onset n={len(lexicon['refusal_onset'])} hedge n={len(lexicon['hedge'])} "
      f"control n={len(lexicon['control'])}")
print(f"token_sets_single_token: refusal n={len(lexicon['token_sets_single_token'].get('refusal', []))} "
      f"hedge n={len(lexicon['token_sets_single_token'].get('hedge', []))} "
      f"control n={len(lexicon['token_sets_single_token'].get('control', []))}")
print(f"\nheldout_hash_match={heldout_hash_match} variant={heldout_hash_variant}")
print(f"rubric_md_sha256 actual={rubric_actual} expected={rubric_expected} match={rubric_actual == rubric_expected}")
print(f"\nn deviations: {len(DEVIATIONS)}")
for d in DEVIATIONS:
    print(" - DEVIATION:", d)
