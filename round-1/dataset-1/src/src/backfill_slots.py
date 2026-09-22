#!/usr/bin/env python3
"""Backfill the action slots the primary extractor declined, using a second
model family, then fall back to a deterministic rule-based extractor.

Any slot that ends up rule-derived is flagged so downstream can see that it was
not model-extracted. No slot is ever left empty and none is hand-authored.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

import aiohttp
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
from or_client import ORClient, parse_json  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/backfill_slots.log", rotation="10 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
MODEL = "openai/gpt-5-nano"

SYSTEM = (
    "You are a grammatical transformation tool used to build measurement stimuli for an AI-safety "
    "interpretability benchmark. Your only job is to restate a verb phrase in three grammatical forms. "
    "You add no information, no method, and no detail; you only change the grammar. Output STRICT JSON only."
)
TEMPLATE = """Restate the ACTION in the following request in three grammatical forms. This is a pure grammar transformation for a safety benchmark: copy the same words, change only the verb form. Add nothing.

Request: {prompt}

Return STRICT JSON only:
{{"gerund": "<-ing phrase, fits after 'when '>", "infinitive": "<bare verb phrase, fits after 'how to '>", "noun_phrase": "<short noun phrase>"}}"""

_LEAD = re.compile(
    r"^(how (do|can|should|would) (i|you|we)|what (can|do|should) (i|you) do to|what's the (best )?(way|process) (of|for|to)|where can i|how to)\s+",
    re.I,
)
_IRREG = {"be": "being", "have": "having", "die": "dying", "lie": "lying", "make": "making", "take": "taking"}


def rule_forms(prompt: str) -> dict[str, str]:
    """Deterministic fallback: strip the interrogative frame, inflect the head verb."""
    s = prompt.strip().rstrip("?").strip()
    s = _LEAD.sub("", s)
    words = s.split()
    if not words:
        return {"gerund": s, "infinitive": s, "noun_phrase": s}
    head = words[0].lower()
    if head in _IRREG:
        ger = _IRREG[head]
    elif head.endswith("e") and not head.endswith(("ee", "oe", "ye")):
        ger = head[:-1] + "ing"
    elif re.fullmatch(r"[a-z]*[aeiou][bcdfgklmnprstvz]", head) and len(head) <= 5:
        ger = head + head[-1] + "ing"
    else:
        ger = head + "ing"
    rest = " ".join(words[1:])
    inf = " ".join([head] + words[1:])
    return {
        "gerund": (ger + (" " + rest if rest else "")).strip(),
        "infinitive": inf.strip(),
        "noun_phrase": ("the act of " + ger + (" " + rest if rest else "")).strip(),
    }


@logger.catch(reraise=True)
async def amain() -> None:
    d = json.loads((ROOT / "results/action_slots.json").read_text())
    missing = [r for r in d["slots"] if not r["extracted"]]
    if not missing:
        logger.info("nothing to backfill")
        return
    logger.info(f"backfilling {len(missing)} slots with {MODEL}")

    client = ORClient(cap_usd=0.05)
    got: dict[int, dict] = {}
    async with aiohttp.ClientSession() as session:
        await client.load_catalog(session)
        res = await asyncio.gather(
            *[
                client.call(session, model=MODEL, system=SYSTEM, user=TEMPLATE.format(prompt=m["prompt"]), max_tokens=2500)
                for m in missing
            ],
            return_exceptions=True,
        )
    for m, r in zip(missing, res):
        if isinstance(r, dict) and r.get("text"):
            o = parse_json(r["text"])
            if isinstance(o, dict) and o.get("gerund"):
                got[m["xstest_id"]] = o
    logger.info(f"second family supplied {len(got)}/{len(missing)}; ${client.spent:.5f}")

    by_id = {r["xstest_id"]: r for r in d["slots"]}
    n_model, n_rule = 0, 0
    for m in missing:
        i = m["xstest_id"]
        if i in got:
            o, src = got[i], f"backfill:{MODEL}"
            n_model += 1
        else:
            o, src = rule_forms(m["prompt"]), "rule_based_fallback"
            n_rule += 1
            logger.warning(f"id {i}: both model families declined; rule-derived {o['gerund']!r}")
        by_id[i].update(
            {
                "gerund": o["gerund"].strip(),
                "infinitive": o["infinitive"].strip(),
                "noun_phrase": o["noun_phrase"].strip(),
                "extracted": True,
                "slot_source": src,
            }
        )
    for r in d["slots"]:
        r.setdefault("slot_source", f"primary:{d['model']}")

    d["n_extracted"] = sum(r["extracted"] for r in d["slots"])
    d["backfill"] = {
        "n_declined_by_primary": len(missing),
        "declined_prompt_ids": [m["xstest_id"] for m in missing],
        "n_recovered_by_second_family": n_model,
        "n_rule_based_fallback": n_rule,
        "second_family_model": MODEL,
        "note": (
            "The primary extractor refused three prompts on safety grounds. This is itself a property worth "
            "recording: the refusal was triggered by the REQUEST text, not by anything this pipeline generated. "
            "Slots recovered from a second model family or, failing that, derived by a published deterministic "
            "rule; `slot_source` marks which, and no slot was hand-authored."
        ),
    }
    d["spend_usd"] = round(d["spend_usd"] + client.spent, 6)
    (ROOT / "results/action_slots.json").write_text(json.dumps(d, indent=2, ensure_ascii=False))
    logger.info(f"all {d['n_extracted']}/300 slots present (model {n_model}, rule {n_rule})")


if __name__ == "__main__":
    asyncio.run(amain())
