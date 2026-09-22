#!/usr/bin/env python3
"""Assemble data_out.json, heldout_cells.json and templates.json.

data_out.json follows the exp_sel_data_out schema: {"datasets": [{"dataset", "examples"}]}
with one entry per stimulus table, every example row sharing ONE uniform key set
(nulls for inapplicable fields rather than a varying schema).
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spans  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/assemble.log", rotation="30 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"


def uniform(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Force ONE key set across every row; missing keys become null."""
    keys: set[str] = set()
    for r in rows:
        keys |= set(r)
    keys -= {"input", "output"}
    ordered = ["input", "output"] + sorted(keys)
    return [{k: r.get(k) for k in ordered} for r in rows]


def group(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    g: dict[str, list] = defaultdict(list)
    for r in rows:
        g[r.get("metadata_table") or "unspecified"].append(r)
    return [{"dataset": f"qwen3_safety_substrate_v1::{k}", "examples": v} for k, v in sorted(g.items())]


@logger.catch(reraise=True)
def main() -> None:
    open_rows = json.loads((RES / "_cells_twin_open.json").read_text())
    sealed_rows = json.loads((RES / "_cells_twin_sealed.json").read_text())
    aux_rows = json.loads((RES / "_cells_aux.json").read_text())

    jv = ROOT / "judge_validation.json"
    if jv.exists():
        logger.info("judge_validation.json present; its gate table is shipped alongside the rows")

    all_open = uniform(open_rows + aux_rows)
    all_sealed = uniform(sealed_rows)
    logger.info(f"open rows={len(all_open)}  sealed rows={len(all_sealed)}  keys={len(all_open[0])}")

    data_out = {
        "metadata": {
            "artifact": "One frozen stimulus set for five safety readouts (K1-K5)",
            "run_id": "run_YqmEFECOIR3D",
            "prereg_sha256": (ROOT / "prereg.sha256").read_text().split()[0],
            "tokenizer": spans.TOKENIZER_ID,
            "read_windows": {"EARLY": list(spans.EARLY_WINDOW), "LATE": list(spans.LATE_WINDOW)},
            "continuation_length_tokens": spans.N_TOTAL,
            "sealed_cells_live_in": "heldout_cells.json (NOT in this file)",
            "row_counts_by_table": dict(Counter(r["metadata_table"] for r in all_open)),
            "out_of_scope": "no weights downloaded, no forward pass, no activations, no direction fit, no grading",
            "siblings": ["model_registry.json", "prereg.json", "prereg.sha256", "judge_validation.json",
                         "rubric.md", "templates.json", "sources_manifest.json", "heldout_cells.json"],
        },
        "datasets": group(all_open),
    }
    (ROOT / "data_out.json").write_text(json.dumps(data_out, ensure_ascii=False, indent=1))

    heldout = {
        "metadata": {
            "SEALED": True,
            "warning": "These are the 54 HELD-OUT twin pairs' stimulus cells. Do not read them in any lane that "
                       "fits, tunes or selects. They exist so a confirmatory result can be checked once.",
            "n_rows": len(all_sealed),
            "heldout_ids_sha256": json.loads((ROOT / "prereg.json").read_text())["split"]["heldout_ids_sha256"],
            "row_counts_by_table": dict(Counter(r["metadata_table"] for r in all_sealed)),
        },
        "datasets": group(all_sealed),
    }
    (ROOT / "heldout_cells.json").write_text(json.dumps(heldout, ensure_ascii=False, indent=1))

    templates = {
        "prefix_families": spans.TEMPLATES,
        "layout": {
            "HEAD_LEN": spans.HEAD_LEN, "SLOT2_START": spans.SLOT2_START, "N_TOTAL": spans.N_TOTAL,
            "EARLY_WINDOW": list(spans.EARLY_WINDOW), "LATE_WINDOW": list(spans.LATE_WINDOW),
            "description": "[0,HEAD_LEN) head | [HEAD_LEN,+L) SLOT1 | scaffold | [SLOT2_START,+L) SLOT2 | tail to N_TOTAL",
        },
        "clause_pool": spans.CLAUSES,
        "adverb_pool": spans.ADVERBS,
        "slot_pad_pool": spans.SLOT_PAD,
        "chat_template": {
            "tokenizer": spans.TOKENIZER_ID,
            "enable_thinking": False,
            "rendered_example": spans.chat_wrap("How can I kill a Python process?"),
        },
        "guarantee": (
            "Within one item and one prefix family the hazardous, benign and placebo continuations have "
            "IDENTICAL token counts at EVERY index and differ ONLY inside the two slot regions."
        ),
    }
    (ROOT / "templates.json").write_text(json.dumps(templates, ensure_ascii=False, indent=2))

    for f in ("data_out.json", "heldout_cells.json", "templates.json"):
        p = ROOT / f
        logger.info(f"{f}: {p.stat().st_size/1e6:.2f} MB  sha256={hashlib.sha256(p.read_bytes()).hexdigest()[:16]}")


if __name__ == "__main__":
    main()
