"""Merge Lane S-A and Lane S-BC into saturation_table.json (iter-4 cell_table row shape).

Re-runnable: reads blockS/lane_SA.json and blockS/lane_SBC.json, writes saturation_table.json.
"""
import json
from pathlib import Path

WS = Path(__file__).parent
sa = json.loads((WS / "blockS/lane_SA.json").read_text())
sbc = json.loads((WS / "blockS/lane_SBC.json").read_text())

ORDER = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "G1", "G2", "G3", "G4"]
DEFS = {
 "W1": "Site-local write gain: project the model's own fitted request axis F out at an early band b (last prompt token); |delta proj onto late-band r_late| minus a matched-norm orthogonalised random-direction control.",
 "W2": "Redundancy depth: smallest k in 1..6 such that JOINT ablation of k bands halves the r_late projection; censored at 7.",
 "W3": "Positional redundancy ratio: all-position ablation effect / last-prompt-token-only ablation effect, same band.",
 "W4": "Self-repair coefficient: after ablating F's component at band b, the fraction of the removed component written back by the layers above b by the end of the stack.",
 "W5": "Benign-side write gain: W1 on the XSTest benign-twin axis N6, on hard-benign prompts.",
 "W6": "Signed two-sided gain = W5 - W1.",
 "W7": "Decode-site write gain: W1 read at the model's own first 1-8 greedy decode positions.",
 "W8": "Rotation under self-lesion: cosine between the model's own F before and after its own fixed-strength rank-one self-lesion of o_proj/down_proj.",
 "G1": "Harmful-versus-benign-twin angle at the model's own best band (chosen on fold A).",
 "G2": "Three-cluster margin ratio d(harmful, hard-benign) / d(hard-benign, plain-benign).",
 "G3": "Used-ness: cosine between the fitted axis and the residual delta the band's own layers write on harmful prompts.",
 "G4": "Fisher ratio in the subspace orthogonal to the unembedding's refusal-token rows.",
}

rows = []
for cid in ORDER:
    if cid == "W4":
        v = dict(sa["verdicts"]["W4"])
        v.setdefault("candidate_id", "W4")
        src = "lane_SA"
    else:
        v = dict(sbc["verdicts"][cid])
        src = "lane_SBC"
    near = [h for h in (sbc.get("hits", []) + sa.get("scalarisation_hits", []))
            if h.get("candidate_id") == cid and h is not v]
    row = {
        "candidate_id": cid,
        "definition": DEFS[cid],
        "verdict": v.get("verdict"),
        "confidence": v.get("confidence"),
        "deciding_paper": v.get("paper"),
        "arxiv_id_or_url": v.get("arxiv_id_or_url"),
        "quantity_described": v.get("quantity_described"),
        "scope": v.get("scope"),
        "needs_parent_or_reference_model": v.get("needs_parent_or_reference_model"),
        "scored_against_behaviour": v.get("scored_against_behaviour"),
        "behaviour_named": v.get("behaviour_named"),
        "domain": v.get("domain"),
        "quote": v.get("quote") or v.get("deciding_quote"),
        "quote_url": v.get("quote_url"),
        "regex_used": v.get("regex_used"),
        "positive_control": v.get("positive_control"),
        "rationale": v.get("rationale"),
        "near_misses": [{"paper": h.get("paper"), "arxiv_id_or_url": h.get("arxiv_id_or_url"),
                         "verdict": h.get("verdict"), "scope": h.get("scope"),
                         "quote": h.get("quote"), "quote_url": h.get("quote_url")} for h in near],
        "source_lane": src,
    }
    rows.append(row)

# Evidence-strength annotations the orchestrator adds on top of the lanes' verdicts.
NOTES = {
 "W5": "OPEN BY INHERITANCE: no W5-specific query family was run and no W5-specific zero-match was recorded; the absence evidence is W1's (Galeone PDF). Treat as OPEN with weaker support than W1.",
 "W6": "OPEN BY INHERITANCE: a composite of W1 and W5. Its absence evidence is W1's. Two-sided by construction, but that construction is not itself evidence of novelty.",
}
for r in rows:
    if r["candidate_id"] in NOTES:
        r["orchestrator_note"] = NOTES[r["candidate_id"]]

summary = {c: next(r["verdict"] for r in rows if r["candidate_id"] == c) for c in ORDER}
closed = [c for c, v in summary.items() if v == "CLOSED"]
out = {
    "date": "2026-09-22",
    "rubric": {
        "CLOSED": "a published paper OR a live public tool computes essentially this quantity as a single number characterising a MODEL, parent-free, and uses it to compare, rank or score checkpoints. Verbatim quote required.",
        "PARTIAL": "the quantity exists but fails exactly one of: per-input rather than per-checkpoint; needs a parent/reference; never scalarised; exists only outside safety; never scored against anything.",
        "OPEN": ">=3 distinct query families with zero relevant hits AND >=1 positive-control-backed zero-match regex on the nearest-neighbour paper. Anything weaker is PARTIAL.",
    },
    "summary": summary,
    "closed": closed or "NONE",
    "rows": rows,
    "tools": sbc.get("tools", {}),
    "absence_claims": sbc.get("absence_claims", []) + sa.get("absence_claims", []),
}
(WS / "saturation_table.json").write_text(json.dumps(out, indent=1))
print(json.dumps(summary))
print("CLOSED:", closed or "NONE")
