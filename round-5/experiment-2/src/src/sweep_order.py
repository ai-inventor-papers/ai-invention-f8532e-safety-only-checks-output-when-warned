#!/usr/bin/env python3
"""Deterministic sweep order for the blind held-out panel.

The panel DRAW is already frozen (results/panel.json, chain record 1).  This
module does not re-draw and does not drop anybody: it only decides the ORDER in
which the 40 drawn checkpoints are visited, so that if the wall clock runs out
the achieved panel is still maximally useful -- family-diverse, lineage-complete
and containing the edited children -- rather than whatever the draw order
happened to put first.

Ordering key, applied in this order and fully documented so it is auditable:

  1. risk_tier   -- architectures known to need extra runtime deps or known to
                    break under transformers 5.x go LAST, so a late failure
                    costs nothing that an earlier checkpoint would have used.
  2. coverage    -- the first appearance of a family, then of a lineage unit,
                    then of an edited child, comes first.  This front-loads the
                    >=6-never-loaded-families and >=2-edited-children quotas.
  3. bf16_gb     -- smaller downloads first (more checkpoints per unit time).
  4. draw_index  -- the frozen seeded draw order breaks every remaining tie, so
                    nothing here is discretionary.

RESERVE repos (bf16 bytes above the VRAM lease) are always last.

No measured quantity enters this ordering: it is selection bookkeeping over
repositories, computed before any behaviour is read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WS = Path(__file__).resolve().parent.parent
RESULTS = WS / "results"

# Architectures that need runtime deps we did not install, or that prior
# sessions recorded as broken under transformers 5.x.  Going last is a
# scheduling decision, never an exclusion: they stay in the panel and are
# attempted; a failure is recorded as a deviation with its traceback class.
RISK_NOTES: dict[str, str] = {
    "zamba2": "hybrid mamba2 -- upstream asks for mamba-ssm + causal-conv1d, not installed",
    "falcon-h1": "hybrid mamba/attention -- may need mamba kernels; Falcon3 exclusion does NOT apply (different lineage)",
    "minicpm": "MiniCPM4 remote code imports is_torch_fx_available, REMOVED in transformers 5.x (prior session excluded it by amendment)",
    "internlm": "trust_remote_code required; smoke load must pass first",
}
RISK_TIER: dict[str, int] = {"zamba2": 1, "falcon-h1": 1, "internlm": 2, "minicpm": 3}


def build_order(panel: dict[str, Any]) -> list[dict[str, Any]]:
    cps = list(panel["checkpoints"])
    seen_fam: set[str] = set()
    seen_unit: set[str] = set()
    seen_edit: set[str] = set()

    # First pass to mark the "first appearance" bonuses.  The representative of a
    # family / lineage / edited-child slot is its SMALLEST member: a family is
    # covered just as well by its 0.5 GB arm as by its 6 GB arm, and taking the
    # small one first buys more checkpoints inside the same wall clock.  Ties
    # inside a family fall back to the frozen draw order, so nothing here is
    # discretionary.
    for c in sorted(cps, key=lambda x: (round(float(x.get("bf16_gb") or 99.0), 3),
                                        x["draw_index"])):
        c["_first_in_family"] = c["family"] not in seen_fam
        seen_fam.add(c["family"])
        unit = c.get("unit") or "SINGLE"
        c["_first_in_unit"] = unit not in seen_unit and unit != "SINGLE"
        seen_unit.add(unit)
        is_edit = c.get("role") == "edited_child"
        c["_first_edited_child_of_unit"] = is_edit and unit not in seen_edit
        if is_edit:
            seen_edit.add(unit)

    def coverage(c: dict[str, Any]) -> int:
        # lower sorts earlier
        if c["_first_in_family"]:
            return 0
        if c["_first_edited_child_of_unit"]:
            return 1
        if c["_first_in_unit"]:
            return 2
        return 3

    def key(c: dict[str, Any]) -> tuple:
        return (
            1 if c.get("reserve") else 0,
            RISK_TIER.get(c["family"], 0),
            coverage(c),
            round(float(c.get("bf16_gb") or 99.0), 3),
            int(c["draw_index"]),
        )

    ordered = sorted(cps, key=key)
    out = []
    for pos, c in enumerate(ordered):
        out.append(
            {
                "sweep_position": pos,
                "repo": c["repo"],
                "family": c["family"],
                "role": c["role"],
                "unit": c.get("unit"),
                "bf16_gb": c.get("bf16_gb"),
                "n_layers": c.get("n_layers"),
                "hidden_size": c.get("hidden_size"),
                "tie_word_embeddings": c.get("tie_word_embeddings"),
                "trust_remote_code": c.get("trust_remote_code"),
                "has_chat_template": c.get("has_chat_template"),
                "revision_sha": c.get("revision_sha"),
                "reserve": bool(c.get("reserve")),
                "prior_exposure": c.get("prior_exposure"),
                "flags": c.get("flags", []),
                "draw_index": c["draw_index"],
                "risk_tier": RISK_TIER.get(c["family"], 0),
                "risk_note": RISK_NOTES.get(c["family"]),
                "coverage_class": ["first_in_family", "first_edited_child",
                                   "first_in_lineage", "fill"][coverage(c)],
            }
        )
    return out


def main() -> int:
    panel = json.loads((RESULTS / "panel.json").read_text(encoding="utf-8"))
    order = build_order(panel)

    fams, units, edits = [], [], 0
    cum = []
    for row in order:
        if row["family"] not in fams:
            fams.append(row["family"])
        u = row["unit"] or "SINGLE"
        if u != "SINGLE" and u not in units:
            units.append(u)
        if row["role"] == "edited_child":
            edits += 1
        cum.append({"sweep_position": row["sweep_position"],
                    "n_families_so_far": len(fams),
                    "n_lineage_units_so_far": len(units),
                    "n_edited_children_so_far": edits})

    payload = {
        "utc": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "panel_sha256_source": "results/panel.json (chain record 1)",
        "ordering_key": [
            "reserve last",
            "risk_tier ascending (runtime-dep / transformers-5 risk goes last)",
            "coverage class: first_in_family < first_edited_child < first_in_lineage < fill",
            "the representative of each family/lineage/edited-child slot is its SMALLEST member",
            "bf16_gb ascending",
            "frozen draw_index (breaks every remaining tie)",
        ],
        "note": "Ordering only. Nothing is dropped and no measured quantity enters it. "
                "The draw itself is frozen in chain record 1.",
        "risk_notes": RISK_NOTES,
        "n": len(order),
        "order": order,
        "coverage_curve": cum,
    }
    tmp = RESULTS / "sweep_order.json.tmp"
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(RESULTS / "sweep_order.json")

    print(f"{'pos':>3} {'repo':50} {'fam':12} {'role':13} {'GB':>5} {'risk':>4} cov")
    for r in order[:26]:
        print(f"{r['sweep_position']:>3} {r['repo'][:50]:50} {r['family'][:12]:12} "
              f"{r['role'][:13]:13} {r['bf16_gb']:>5.2f} {r['risk_tier']:>4} {r['coverage_class']}")
    for m in (12, 16, 20, 24, 40):
        if m <= len(cum):
            c = cum[m - 1]
            print(f"  after {m:>2} ckpts: families={c['n_families_so_far']:>2} "
                  f"lineages={c['n_lineage_units_so_far']:>2} edited={c['n_edited_children_so_far']:>2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
