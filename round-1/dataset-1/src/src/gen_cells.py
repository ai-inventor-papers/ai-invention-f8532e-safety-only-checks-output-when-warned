#!/usr/bin/env python3
"""Render every stimulus cell of the frozen substrate.

Within one ITEM and one prefix family, all continuations are the SAME scaffold
and have IDENTICAL token counts at EVERY index, differing only inside the two
action-slot regions -- which is what lets O, CB and A be read at matched
response positions.
"""
from __future__ import annotations

import json
import random
import re
import statistics as st
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spans  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/gen_cells.log", rotation="30 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
SEED = 20260920
FAMILIES = ["F1_announced", "F2_enacted"]
LADDER_FAMILY = "F1_announced"
FITTING_FAMILY = "F2_enacted"

XSTEST_URL = "https://raw.githubusercontent.com/paul-rottger/exaggerated-safety/main/xstest_prompts.csv"
_WORD = re.compile(r"[a-z0-9']+")


def toks(s: str) -> list[str]:
    return _WORD.findall(s.lower())


def lev(a: list[str], b: list[str]) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def phrase(g: str) -> str:
    """Normalise an extracted gerund into a slot string with a leading space."""
    return " " + g.strip().strip(".").strip()


def row(**kw: Any) -> dict[str, Any]:
    """Build one schema-conformant example row (input/output + metadata_* only)."""
    r = {"input": kw.pop("input"), "output": kw.pop("output")}
    for k, v in kw.items():
        r[f"metadata_{k}"] = v
    return r


BASE_META = dict(
    source="XSTest v2 (Rottger et al. 2024) minimal-edit twins",
    source_sha256="11783fb294ed017473ee53c207d71f2161c7672c8d0b037501e78387f801cb5a",
    license="CC-BY-4.0",
    judge_labels=None,
)


def cell_meta(c: spans.Cell) -> dict[str, Any]:
    d = c.to_dict()
    return {
        "n_tokens": d["n_tokens"],
        "action_slot_spans": d["action_slot_spans"],
        "early_window": d["early_window"],
        "late_window": d["late_window"],
        "slot1_intersects_early": d["slot1_intersects_early"],
        "slot2_intersects_late": d["slot2_intersects_late"],
        "qc_fail": d["qc_fail"],
        "qc_reason": d["qc_reason"],
    }


@logger.catch(reraise=True)
def main() -> None:
    rng = random.Random(SEED)
    tp = json.loads((RES / "twin_pairs.json").read_text())
    slots = {s["xstest_id"]: s for s in json.loads((RES / "action_slots.json").read_text())["slots"]}
    ladder = {r["pair_uid"]: r for r in json.loads((RES / "ladder_rungs.json").read_text())["rungs"]}
    pairs = tp["pairs"]

    # ---------- placebo selection: benign action at matched token-edit distance ----------
    # The placebo must differ from the benign prefix in a SAFETY-IRRELEVANT direction.
    # The admissible pool is the benign action of every DEED family -- homonyms,
    # figurative_language, safe_targets, safe_contexts -- whose safe members name ordinary
    # everyday acts ("killing a Python process", "killing weeds", "stealing the show").
    # The two Tier-B families are EXCLUDED: their benign slots are explanatory acts ABOUT a
    # harmful topic ("defining murder"), which is not a safety-irrelevant control.
    # An earlier, far stricter filter -- disjointness from the whole harmful vocabulary --
    # admitted only 2 of 150 candidates and collapsed the factor, so it was replaced.
    DEED_FAMILIES = {"homonyms", "figurative_language", "safe_targets", "safe_contexts"}

    benign_pool = [(q["pair_uid"], phrase(slots[q["safe_id"]]["gerund"])) for q in pairs]
    safe_pool = [(q["pair_uid"], phrase(slots[q["safe_id"]]["gerund"]))
                 for q in pairs if q["family"] in DEED_FAMILIES]
    logger.info(f"placebo pool: {len(safe_pool)}/{len(benign_pool)} benign actions are deed-family (safety-irrelevant)")

    placebo_of: dict[str, str] = {}
    for p in pairs:
        b = phrase(slots[p["safe_id"]]["gerund"])
        h = phrase(slots[p["contrast_id"]]["gerund"])
        d_target = lev(toks(b), toks(h))
        best, best_key = None, None
        for uid, cand in (safe_pool or benign_pool):
            if uid == p["pair_uid"]:
                continue
            key = (abs(lev(toks(b), toks(cand)) - d_target), abs(spans.n_tok(cand) - spans.n_tok(h)))
            if best_key is None or key < best_key:
                best, best_key = cand, key
        placebo_of[p["pair_uid"]] = best
    d_haz = [lev(toks(phrase(slots[p["safe_id"]]["gerund"])), toks(phrase(slots[p["contrast_id"]]["gerund"]))) for p in pairs]
    d_pla = [lev(toks(phrase(slots[p["safe_id"]]["gerund"])), toks(placebo_of[p["pair_uid"]])) for p in pairs]
    m_h, m_p = st.median(d_haz), st.median(d_pla)
    ratio = m_p / m_h if m_h else float("nan")
    logger.info(f"placebo edit-distance match: median benign<->hazardous={m_h}, benign<->placebo={m_p}, ratio={ratio:.3f}")
    placebo_ok = abs(ratio - 1.0) <= 0.10

    # ---------- coherence control: item's own benign topic vs another item's benign topic ----------
    order = list(range(len(pairs)))
    topicB_of, topicB_req = {}, {}
    for i, p in zip(order, pairs):
        other = pairs[(i + 75) % len(pairs)]
        topicB_of[p["pair_uid"]] = phrase(slots[other["safe_id"]]["gerund"])
        topicB_req[p["pair_uid"]] = other["benign_prompt"]

    confirm = set(json.loads((RES / "confirm_ids.json").read_text()))
    rows_open: list[dict[str, Any]] = []
    rows_sealed: list[dict[str, Any]] = []
    qc_fail_items: list[str] = []
    widths: list[int] = []

    for p in pairs:
        uid = p["pair_uid"]
        sealed = uid not in confirm
        sink = rows_sealed if sealed else rows_open
        b_ph = phrase(slots[p["safe_id"]]["gerund"])
        h_ph = phrase(slots[p["contrast_id"]]["gerund"])
        pl_ph = placebo_of[uid]
        tb_ph = topicB_of[uid]
        width = max(spans.n_tok(x) for x in (b_ph, h_ph, pl_ph, tb_ph))
        widths.append(width)

        common = dict(
            BASE_META,
            item_uid=uid,
            pair_uid=uid,
            family=p["family"],
            minimal_edit_tier=p["minimal_edit_tier"],
            harm_domain=p["harm_domain"],
            harm_domain_provenance=p["harm_domain_provenance"],
            action_phrase_harm=h_ph.strip(),
            action_phrase_benign=b_ph.strip(),
            action_phrase_placebo=pl_ph.strip(),
            jaccard_twin=p["jaccard_twin"],
            levenshtein_twin=p["levenshtein_twin"],
            slot_width_tokens=width,
            twin_available=True,
            sealed=sealed,
            chat_templated=True,
        )
        reqs = {"harmful": p["harmful_prompt"], "benign_twin": p["benign_prompt"]}
        prefixes = {"hazardous": h_ph, "benign": b_ph, "placebo": pl_ph}
        rendered: dict[tuple[str, str], spans.Cell] = {}
        for fam in FAMILIES:
            for pl, ph in prefixes.items():
                rendered[(fam, pl)] = spans.render(fam, ph, width)
        if any(not c.ok for c in rendered.values()):
            qc_fail_items.append(uid)

        for fam in FAMILIES:
            for rl, rtext in reqs.items():
                for pl in ("hazardous", "benign", "placebo"):
                    c = rendered[(fam, pl)]
                    sink.append(
                        row(
                            input=spans.chat_wrap(rtext),
                            output=c.text,
                            fold="heldout" if sealed else "confirm",
                            table="placebo" if pl == "placebo" else "safety_2x2",
                            request_level=rl,
                            request_text=rtext,
                            prefix_level=pl,
                            prefix_family=fam,
                            harm_rung=4 if rl == "harmful" else 0,
                            plain_prompt=rtext,
                            levenshtein_to_benign_prefix=lev(toks(b_ph), toks(prefixes[pl])),
                            **cell_meta(c),
                            **common,
                        )
                    )
            # coherence control: same shape, safety-irrelevant attribute
            for rl, rph in (("topicA", b_ph), ("topicB", tb_ph)):
                rtext = p["benign_prompt"] if rl == "topicA" else topicB_req[uid]
                for pl, pph in (("topicA", b_ph), ("topicB", tb_ph)):
                    c = spans.render(fam, pph, width)
                    sink.append(
                        row(
                            input=spans.chat_wrap(rtext),
                            output=c.text,
                            fold="heldout" if sealed else "confirm",
                            table="coherence_control",
                            request_level=rl,
                            request_text=rtext,
                            prefix_level=pl,
                            prefix_family=fam,
                            harm_rung=None,
                            plain_prompt=rtext,
                            levenshtein_to_benign_prefix=lev(toks(b_ph), toks(pph)),
                            **cell_meta(c),
                            **common,
                        )
                    )
        # graded-harm ladder, all rungs against the hazardous prefix
        lr = ladder.get(uid, {})
        c = rendered[(LADDER_FAMILY, "hazardous")]
        for k in range(5):
            rtext = lr.get(f"rung{k}")
            if not rtext:
                continue
            sink.append(
                row(
                    input=spans.chat_wrap(rtext),
                    output=c.text,
                    fold="heldout" if sealed else "confirm",
                    table="graded_harm_ladder",
                    request_level=f"ladder_{k}",
                    request_text=rtext,
                    prefix_level="hazardous",
                    prefix_family=LADDER_FAMILY,
                    harm_rung=k,
                    ladder_generated=bool(lr.get("generated")),
                    plain_prompt=rtext,
                    levenshtein_to_benign_prefix=lev(toks(b_ph), toks(h_ph)),
                    **cell_meta(c),
                    **common,
                )
            )

    logger.info(f"slot width: median={st.median(widths)} min={min(widths)} max={max(widths)}")
    logger.info(f"items with any qc_fail cell: {len(qc_fail_items)}")
    logger.info(f"open rows so far={len(rows_open)}  sealed rows={len(rows_sealed)}")

    meta = {
        "placebo_pool": {
            "rule": "admissible placebo candidates are the benign actions of the four DEED families "
                    "(homonyms, figurative_language, safe_targets, safe_contexts), which name ordinary everyday "
                    "acts; the two Tier-B families are excluded because their benign slots are explanatory acts "
                    "ABOUT a harmful topic ('defining murder') and so are not safety-irrelevant",
            "n_admissible": len(safe_pool),
            "n_total_benign_actions": len(benign_pool),
            "rejected_alternative": "requiring disjointness from the ENTIRE harmful action vocabulary admitted only "
                                    "2 of 150 candidates and collapsed the factor to two phrases; sharing a verb "
                                    "with a harmful action is not itself disqualifying, since 'killing weeds' is "
                                    "benign and the hazardous edit often preserves the verb too",
        },
        "placebo_calibration": {
            "median_edit_benign_to_hazardous": m_h,
            "median_edit_benign_to_placebo": m_p,
            "ratio": round(ratio, 4),
            "within_10_percent": placebo_ok,
            "note": "per-item distances ship as metadata_levenshtein_to_benign_prefix so a downstream lane can "
            "regress on them instead of subtracting a constant",
        },
        "qc_fail_items": qc_fail_items,
        "slot_width_tokens": {"median": st.median(widths), "min": min(widths), "max": max(widths)},
    }
    (RES / "_cells_twin_open.json").write_text(json.dumps(rows_open, ensure_ascii=False))
    (RES / "_cells_twin_sealed.json").write_text(json.dumps(rows_sealed, ensure_ascii=False))
    (RES / "_cells_meta.json").write_text(json.dumps(meta, indent=2))
    logger.info("wrote twin-derived cells")


if __name__ == "__main__":
    main()
