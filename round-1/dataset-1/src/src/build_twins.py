#!/usr/bin/env python3
"""Build the XSTest v2 minimal-edit twin table and freeze the confirm/heldout split.

Pairs the six genuine minimal-edit contrast families on the `focus` column,
cross-checks against the +25 positional offset, measures the minimal-edit
property (token Jaccard + token Levenshtein), then writes a seeded stratified
hash split BEFORE any stimulus cell text exists.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/build_twins.log", rotation="30 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
CSV = ROOT / "temp/datasets/xstest_prompts.csv"
OUT = ROOT / "results"

SALT = "run_YqmEFECOIR3D/iter1/dataset/v1"
TWIN_FAMILIES = [
    "homonyms",
    "figurative_language",
    "safe_targets",
    "safe_contexts",
    "definitions",
    "historical_events",
]
EXCLUDED_CONTRAST = {
    "contrast_discr": "pairs to BOTH nons_group_real_discr and real_group_nons_discr; topically parallel only",
    "contrast_privacy": "pairs to BOTH privacy_public and privacy_fictional; topically parallel only",
}
N_CONFIRM_PER_FAMILY = 16
N_HELDOUT_PER_FAMILY = 9

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def toks(s: str) -> list[str]:
    return _TOKEN_RE.findall(s.lower())


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def levenshtein(a: list[str], b: list[str]) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def pair_family(safe: pd.DataFrame, contrast: pd.DataFrame, family: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Pair on `focus`, cross-check +25 positional offset. Returns (pairs, disagreements)."""
    notes: list[str] = []
    # positional map: contrast id == safe id + 25
    pos_map = {int(r.id): int(r.id) + 25 for r in safe.itertuples()}
    contrast_ids = set(int(x) for x in contrast.id)

    # focus join, order-preserving within duplicated focus values
    by_focus: dict[str, list[int]] = defaultdict(list)
    for r in contrast.itertuples():
        by_focus[str(r.focus)].append(int(r.id))
    cursor: Counter[str] = Counter()

    pairs: list[dict[str, Any]] = []
    for r in safe.sort_values("id").itertuples():
        sid = int(r.id)
        f = str(r.focus)
        cand = by_focus.get(f, [])
        k = cursor[f]
        focus_cid = cand[k] if k < len(cand) else None
        cursor[f] += 1
        pos_cid = pos_map[sid] if pos_map[sid] in contrast_ids else None
        if focus_cid is None and pos_cid is None:
            notes.append(f"{family}: safe id {sid} focus={f!r} has NO contrast partner by either method")
            continue
        method = "focus+positional_agree"
        if focus_cid is None:
            cid, method = pos_cid, "positional_only(focus_missing)"
            notes.append(f"{family}: safe id {sid} focus={f!r} unmatched by focus; used +25 offset -> {cid}")
        elif pos_cid is None:
            cid, method = focus_cid, "focus_only(no_positional)"
            notes.append(f"{family}: safe id {sid} has no id+25 in contrast block; used focus -> {cid}")
        elif focus_cid != pos_cid:
            cid, method = pos_cid, "DISAGREE_used_positional"
            notes.append(
                f"{family}: DISAGREEMENT safe id {sid} focus={f!r}: focus-join -> {focus_cid}, +25 offset -> {pos_cid}; used positional"
            )
        else:
            cid = focus_cid
        crow = contrast[contrast.id == cid].iloc[0]
        st, ct = toks(str(r.prompt)), toks(str(crow.prompt))
        pairs.append(
            {
                "family": family,
                "safe_id": sid,
                "contrast_id": int(cid),
                "pair_uid": f"{family}:{sid}:{int(cid)}",
                "benign_prompt": str(r.prompt),
                "harmful_prompt": str(crow.prompt),
                "focus_safe": f,
                "focus_contrast": str(crow.focus),
                "note_safe": None if pd.isna(r.note) else str(r.note),
                "note_contrast": None if pd.isna(crow.note) else str(crow.note),
                "pairing_method": method,
                "jaccard_twin": round(jaccard(st, ct), 4),
                "levenshtein_twin": levenshtein(st, ct),
                "n_tokens_benign_prompt": len(st),
                "n_tokens_harmful_prompt": len(ct),
            }
        )
    return pairs, notes


@logger.catch(reraise=True)
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = CSV.read_bytes()
    csv_sha = hashlib.sha256(raw).hexdigest()
    df = pd.read_csv(CSV)
    logger.info(f"XSTest loaded: {df.shape} cols={list(df.columns)} sha256={csv_sha}")

    assert list(df.columns) == ["id", "prompt", "type", "label", "focus", "note"], "unexpected header"
    assert len(df) == 450 and df.id.nunique() == 450, "expected 450 unique-id rows"
    tc = df["type"].value_counts()
    assert set(tc.values) == {25}, f"expected 25 rows per type, got {sorted(set(tc.values))}"
    logger.info(f"18 types x 25 rows verified; label counts={df.label.value_counts().to_dict()}")

    all_pairs: list[dict[str, Any]] = []
    all_notes: list[str] = []
    for fam in TWIN_FAMILIES:
        safe = df[df["type"] == fam]
        contrast = df[df["type"] == f"contrast_{fam}"]
        assert len(safe) == 25 and len(contrast) == 25
        assert set(safe.label) == {"safe"} and set(contrast.label) == {"unsafe"}, f"{fam}: label check failed"
        p, n = pair_family(safe, contrast, fam)
        logger.info(f"{fam}: {len(p)} pairs, {len(n)} pairing notes")
        all_pairs.extend(p)
        all_notes.extend(n)

    assert len(all_pairs) == 150, f"expected 150 twin pairs, got {len(all_pairs)}"
    n_agree = sum(1 for p in all_pairs if p["pairing_method"] == "focus+positional_agree")
    jac = sorted(p["jaccard_twin"] for p in all_pairs)
    med_jac = jac[len(jac) // 2]
    lev = sorted(p["levenshtein_twin"] for p in all_pairs)
    logger.info(f"pairing: {n_agree}/150 focus and +25 offset AGREE; median Jaccard={med_jac:.3f} median Levenshtein={lev[len(lev)//2]}")
    low = [p["pair_uid"] for p in all_pairs if p["jaccard_twin"] < 0.5]
    logger.info(f"pairs with Jaccard < 0.5: {len(low)}")
    if med_jac < 0.5:
        logger.error("median Jaccard < 0.5 -- focus/positional pairing is suspect; see FALLBACK in plan")

    # ---- FREEZE THE SPLIT (before any cell text exists) ----
    for p in all_pairs:
        p["split_hash"] = sha256_text(SALT + "|" + p["pair_uid"])
    confirm, heldout = [], []
    per_family_counts = {}
    for fam in TWIN_FAMILIES:
        fp = sorted([p for p in all_pairs if p["family"] == fam], key=lambda x: x["split_hash"])
        confirm.extend(fp[:N_CONFIRM_PER_FAMILY])
        heldout.extend(fp[N_CONFIRM_PER_FAMILY:])
        per_family_counts[fam] = {
            "n_pairs": len(fp),
            "n_confirm": min(N_CONFIRM_PER_FAMILY, len(fp)),
            "n_heldout": max(0, len(fp) - N_CONFIRM_PER_FAMILY),
        }
    for p in confirm:
        p["fold"] = "confirm"
    for p in heldout:
        p["fold"] = "heldout"
    assert len(confirm) == 96 and len(heldout) == 54, f"split sizes {len(confirm)}/{len(heldout)}"

    confirm_ids = sorted(p["pair_uid"] for p in confirm)
    heldout_ids = sorted(p["pair_uid"] for p in heldout)
    canon = lambda o: json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    confirm_sha = hashlib.sha256(canon(confirm_ids)).hexdigest()
    heldout_sha = hashlib.sha256(canon(heldout_ids)).hexdigest()

    (OUT / "confirm_ids.json").write_text(json.dumps(confirm_ids, indent=2))
    (OUT / "heldout_ids.json").write_text(json.dumps(heldout_ids, indent=2))
    logger.info(f"SPLIT FROZEN  salt={SALT!r}")
    logger.info(f"  confirm n=96  sha256={confirm_sha}")
    logger.info(f"  heldout n=54  sha256={heldout_sha}")

    out = {
        "source": {
            "url": "https://raw.githubusercontent.com/paul-rottger/exaggerated-safety/main/xstest_prompts.csv",
            "sha256": csv_sha,
            "n_rows": int(len(df)),
            "columns": list(df.columns),
            "license": "CC-BY-4.0",
            "paper": "Rottger et al. 2024, XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours in LLMs (NAACL 2024), arXiv:2308.01263",
        },
        "twin_families_kept": TWIN_FAMILIES,
        "contrast_families_excluded": EXCLUDED_CONTRAST,
        "hard_ceiling_note": (
            "150 is a HARD CEILING on the genuine minimal-edit twin count. OR-Bench cannot supply twins: its "
            "hard-benign and toxic rows live in separate splits with no row-level correspondence."
        ),
        "pairing": {
            "method": "join on (family, focus) with order-preserving disambiguation of duplicate focus values; cross-checked against the +25 positional offset",
            "n_pairs": len(all_pairs),
            "n_focus_and_positional_agree": n_agree,
            "n_disagreements": len(all_pairs) - n_agree,
            "notes": all_notes,
            "median_jaccard": med_jac,
            "median_levenshtein": lev[len(lev) // 2],
            "n_pairs_jaccard_below_0.5": len(low),
            "pairs_jaccard_below_0.5": low,
        },
        "split": {
            "salt": SALT,
            "rule": "sort each family's pairs by sha256(SALT + '|' + pair_uid); first 16 -> confirm, remaining 9 -> heldout",
            "n_confirm": 96,
            "n_heldout": 54,
            "confirm_ids_sha256": confirm_sha,
            "heldout_ids_sha256": heldout_sha,
            "per_family": per_family_counts,
            "frozen_before_any_cell_text": True,
        },
        "pairs": sorted(all_pairs, key=lambda p: (p["family"], p["safe_id"])),
    }
    (OUT / "twin_pairs.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    logger.info(f"wrote {OUT/'twin_pairs.json'}  ({(OUT/'twin_pairs.json').stat().st_size/1e3:.1f} KB)")


if __name__ == "__main__":
    main()
