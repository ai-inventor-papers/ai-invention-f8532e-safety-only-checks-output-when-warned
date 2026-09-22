#!/usr/bin/env python3
"""The artifact's own self-check, enforcing the run invariant as a COLUMN.

A table that omits READOUT_CLASS is REJECTED here rather than being caught by a
reviewer, and no summary sentence is allowed to name a BASELINE_ONLY row as the
study's answer.
"""

from __future__ import annotations

import re

from loguru import logger

from .prereg import PREREG

VALID = set(PREREG["run_invariant"]["readout_classes"])
RESULT_ELIGIBLE = set(PREREG["run_invariant"]["result_eligible"])
BASELINE_ONLY = set(PREREG["run_invariant"]["baseline_only"])

BANNED_FRAMINGS = (
    "attack success", "attack-success", "asr", "jailbreak rate",
    "attack selection", "jailbreak evaluation",
)


def check_table(name: str, rows: list[dict]) -> dict:
    """Reject a table that cannot state the readout class of every row."""
    problems: list[str] = []
    if not rows:
        return {"table": name, "n_rows": 0, "status": "EMPTY",
                "note": "reported as EMPTY, never silently omitted", "problems": []}
    missing = [i for i, r in enumerate(rows) if "READOUT_CLASS" not in r]
    if missing:
        problems.append(f"{len(missing)} rows omit READOUT_CLASS "
                        f"(first at index {missing[0]})")
    bad = sorted({r.get("READOUT_CLASS") for r in rows
                  if r.get("READOUT_CLASS") not in VALID and "READOUT_CLASS" in r})
    if bad:
        problems.append(f"READOUT_CLASS values outside the registered set: {bad}")
    inconsistent = [i for i, r in enumerate(rows)
                    if "BASELINE_ONLY" in r and "READOUT_CLASS" in r
                    and bool(r["BASELINE_ONLY"]) != (r["READOUT_CLASS"] in BASELINE_ONLY)]
    if inconsistent:
        problems.append(f"{len(inconsistent)} rows whose BASELINE_ONLY flag "
                        f"contradicts their READOUT_CLASS")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("READOUT_CLASS", "<MISSING>")] = \
            counts.get(r.get("READOUT_CLASS", "<MISSING>"), 0) + 1
    return {
        "table": name, "n_rows": len(rows),
        "readout_class_counts": counts,
        "n_result_eligible": sum(v for k, v in counts.items() if k in RESULT_ELIGIBLE),
        "n_baseline_only": sum(v for k, v in counts.items() if k in BASELINE_ONLY),
        "status": "REJECTED" if problems else "ACCEPTED",
        "problems": problems,
    }


def check_prose(name: str, text: str) -> dict:
    """No summary sentence may name a baseline-class readout as the answer, and
    nothing may be framed as jailbreak evaluation or attack selection."""
    low = text.lower()
    negations = ("no ", "not ", "never", "nothing", "rather than", "neither",
                 "must not", "may not", "cannot", "is not an outcome")
    hits = []
    for b in BANNED_FRAMINGS:
        for m in re.finditer(re.escape(b), low):
            window = low[max(0, m.start() - 90): m.start()]
            # a sentence that PROHIBITS a framing is not an instance of it
            if not any(n in window for n in negations):
                hits.append(b)
                break
    answer_claims = []
    for marker in ("the answer is", "our answer", "the study's answer",
                   "the winning readout", "the best readout is"):
        idx = low.find(marker)
        if idx >= 0:
            window = low[idx: idx + 220]
            for token in ("b4", "logit", "regex", "model-card", "refusal rate",
                          "judge"):
                if token in window:
                    answer_claims.append({"marker": marker, "token": token,
                                          "window": text[idx: idx + 220]})
    problems = []
    if hits:
        problems.append(f"banned framing present: {hits}")
    if answer_claims:
        problems.append("a BASELINE_ONLY readout is named as the answer")
    return {"prose": name, "status": "REJECTED" if problems else "ACCEPTED",
            "problems": problems, "banned_framing_hits": hits,
            "answer_claims": answer_claims}


def run_all(tables: dict[str, list[dict]], prose: dict[str, str]) -> dict:
    tab = [check_table(k, v) for k, v in tables.items()]
    pro = [check_prose(k, v) for k, v in prose.items()]
    rejected = [t for t in tab if t["status"] == "REJECTED"] + \
               [p for p in pro if p["status"] == "REJECTED"]
    out = {"tables": tab, "prose": pro,
           "n_tables": len(tab), "n_rejected": len(rejected),
           "status": "PASS" if not rejected else "FAIL",
           "rule": ("Every row of every table carries READOUT_CLASS. Rows tagged "
                    "activation or weight are RESULT-ELIGIBLE; rows tagged logit, "
                    "text or metadata are printed in the same table under a "
                    "permanent BASELINE_ONLY tag and no summary sentence may name "
                    "one as the study's answer.")}
    logger.info("self-check: {} ({} tables, {} rejected)",
                out["status"], out["n_tables"], out["n_rejected"])
    return out
