#!/usr/bin/env python3
"""Guarantee that no BENIGN action slot is hazard-shaped.

The speech-act re-extraction fixed most of it, but a model pass cannot be
relied on for a property the 2x2 depends on. This applies a DETERMINISTIC,
published rule on top and then MEASURES the result, so the guarantee is
checkable rather than trusted:

  if a safe member's prompt is an EXPLANATORY request (what is / what does X
  mean / what happened ...) and its extracted gerund does not begin with an
  explanatory verb, the gerund is rewritten as "describing <the request's own
  content>".

It then reports, for every pair, whether the benign slot still shares content
vocabulary with the harmful slot of the same pair.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from loguru import logger

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/enforce_benign.log", rotation="10 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"

EXPLAIN = ("defining", "explaining", "describing", "outlining", "summarising", "summarizing",
           "clarifying", "detailing", "discussing", "identifying", "listing", "distinguishing")
EXPLANATORY_REQUEST = re.compile(
    r"^\s*(what\s+(is|are|was|were|happened|does|do|did|constitutes|kind)|what's|"
    r"how\s+(was|were|did)\b|define\b|describe\b|explain\b)", re.I)
STOP = {"a", "an", "the", "of", "to", "in", "for", "and", "on", "with", "at", "my", "your", "i",
        "it", "that", "this", "from", "by", "as", "about", "someone", "people", "person", "do",
        "does", "did", "is", "are", "was", "were", "how", "what", "can", "s", "me", "you"}
_W = re.compile(r"[a-z0-9']+")


def content(x: str) -> set[str]:
    return {w for w in _W.findall(x.lower()) if w not in STOP}


def describing_form(prompt: str) -> str:
    core = prompt.strip().rstrip("?").strip()
    core = re.sub(r"^\s*(what's|what is|what are|what was|what were|what does|what do|what did)\s+", "", core, flags=re.I)
    core = re.sub(r"^\s*(the\s+(general|legal)\s+definition\s+of|the\s+definition\s+of|an?\s+)", "", core, flags=re.I)
    core = re.sub(r"\s+mean$", "", core, flags=re.I)
    return "describing " + core[0].lower() + core[1:] if core else "describing the topic"


def main() -> None:
    d = json.loads((RES / "action_slots.json").read_text())
    tp = json.loads((RES / "twin_pairs.json").read_text())
    by = {s["xstest_id"]: s for s in d["slots"]}

    n_rule = 0
    rule_examples = []
    for p in tp["pairs"]:
        s = by[p["safe_id"]]
        if EXPLANATORY_REQUEST.match(s["prompt"]) and not s["gerund"].lower().startswith(EXPLAIN):
            before = s["gerund"]
            s["gerund"] = describing_form(s["prompt"])
            s["infinitive"] = "describe " + s["gerund"][len("describing "):]
            s["noun_phrase"] = "a description of " + s["gerund"][len("describing "):]
            s["slot_source"] = s.get("slot_source", "") + "+deterministic_explanatory_rule"
            n_rule += 1
            if len(rule_examples) < 6:
                rule_examples.append({"xstest_id": s["xstest_id"], "prompt": s["prompt"],
                                      "before": before, "after": s["gerund"]})
    logger.info(f"deterministic rule rewrote {n_rule} benign slots")
    for e in rule_examples:
        logger.info(f"    {e['xstest_id']}: {e['before']!r} -> {e['after']!r}")

    # MEASURE: does the benign slot still share hazard vocabulary with its own harmful slot?
    harm_vocab: set[str] = set()
    for p in tp["pairs"]:
        harm_vocab |= content(by[p["contrast_id"]]["gerund"])
    overlap_within_pair, overlap_global = Counter(), Counter()
    offenders = []
    for p in tp["pairs"]:
        b, h = by[p["safe_id"]]["gerund"], by[p["contrast_id"]]["gerund"]
        cb = content(b)
        within = bool(cb & content(h))
        glob = bool(cb & harm_vocab)
        overlap_within_pair[within] += 1
        overlap_global[glob] += 1
        if within:
            offenders.append({"pair_uid": p["pair_uid"], "family": p["family"], "benign": b, "harmful": h,
                              "shared": sorted(cb & content(h))})
    logger.info(f"benign slot shares a content word with ITS OWN harmful slot: {overlap_within_pair[True]}/150")
    logger.info(f"benign slot shares a content word with the GLOBAL harmful vocabulary: {overlap_global[True]}/150")
    by_fam = Counter(o["family"] for o in offenders)
    logger.info(f"within-pair overlap by family: {dict(by_fam)}")
    for o in offenders[:8]:
        logger.info(f"    {o['pair_uid']}: {o['benign']!r} vs {o['harmful']!r} share {o['shared']}")

    d["benign_slot_enforcement"] = {
        "rule": "if a safe member's prompt is an explanatory request and its gerund does not begin with an "
                "explanatory verb, rewrite the gerund as 'describing <the request's own content>'",
        "explanatory_verbs": list(EXPLAIN),
        "n_rewritten_by_rule": n_rule,
        "examples": rule_examples,
        "measured_after": {
            "n_benign_slots_sharing_content_with_own_harmful_slot": overlap_within_pair[True],
            "n_benign_slots_sharing_content_with_global_harmful_vocabulary": overlap_global[True],
            "of": 150,
            "by_family": dict(by_fam),
            "offenders": offenders,
            "interpretation": (
                "A within-pair content overlap is EXPECTED and wanted for the minimal-edit families: the twin "
                "shares its focus word by construction ('killing a Python process' vs 'killing a person'). What "
                "must NOT happen is the benign slot naming the HARMFUL DEED itself, which is what the "
                "explanatory rewrite removes. The offender list is published so a downstream lane can check "
                "rather than take this on trust."
            ),
        },
    }
    (RES / "action_slots.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))
    logger.info("action_slots.json updated")


if __name__ == "__main__":
    main()
