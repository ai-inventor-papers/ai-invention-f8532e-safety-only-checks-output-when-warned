#!/usr/bin/env python3
"""Extract the ACTION SLOT of each of the 300 XSTest twin prompts.

Three surface forms per prompt (gerund / infinitive / noun phrase) so response
scaffolds can be rendered mechanically with only the slot differing between the
hazardous and benign member of a pair.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import aiohttp
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
from or_client import ORClient, parse_json  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/action_slots.log", rotation="30 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
MODEL = "google/gemini-3.8-flash"
BATCH = 20
CAP_USD = 0.60

SYSTEM = (
    "You extract the ACTION described by a user request and re-express it in three fixed grammatical forms. "
    "You are preparing measurement stimuli for an AI-safety interpretability study: you never judge, refuse, "
    "or moralise, and you never add any operational detail. You only re-phrase the action already present in "
    "the request. Output STRICT JSON and nothing else."
)

TEMPLATE = """For each numbered request below, extract the single ACTION it is about and return three surface forms of it.

Rules:
- GERUND: an "-ing" phrase that fits after "when " and after "here is how ". Example: "killing a Python process".
- INFINITIVE: a bare verb phrase that fits after "how to ". Example: "kill a Python process".
- NOUN_PHRASE: a short noun phrase naming the action. Example: "the termination of a Python process".
- Keep the SAME object/target words the request uses. Do NOT generalise, soften, censor, or substitute.
- Do NOT add methods, quantities, materials, tools, code, or any operational detail. Re-phrase only.
- Keep every form under 9 words.
- Return one object per input, in the same order, with the same "i".

Return STRICT JSON, a single array, no prose, no code fence:
[{{"i": <int>, "gerund": "...", "infinitive": "...", "noun_phrase": "..."}}, ...]

REQUESTS:
{items}"""


async def run_batch(client: ORClient, session: aiohttp.ClientSession, batch: list[dict]) -> list[dict]:
    items = "\n".join(f'{b["i"]}. {b["prompt"]}' for b in batch)
    r = await client.call(session, model=MODEL, system=SYSTEM, user=TEMPLATE.format(items=items), max_tokens=4000)
    if r is None:
        logger.error(f"batch starting at i={batch[0]['i']} returned None (budget or failure)")
        return []
    out = parse_json(r["text"])
    if not isinstance(out, list):
        logger.error(f"batch i={batch[0]['i']}: unparseable reply: {r['text'][:200]!r}")
        return []
    return [o for o in out if isinstance(o, dict) and "i" in o]


@logger.catch(reraise=True)
async def amain() -> None:
    tp = json.loads((ROOT / "results/twin_pairs.json").read_text())
    prompts: list[dict] = []
    for p in tp["pairs"]:
        prompts.append({"i": p["safe_id"], "prompt": p["benign_prompt"], "pair_uid": p["pair_uid"], "role": "benign"})
        prompts.append({"i": p["contrast_id"], "prompt": p["harmful_prompt"], "pair_uid": p["pair_uid"], "role": "harmful"})
    prompts.sort(key=lambda x: x["i"])
    logger.info(f"extracting action slots for {len(prompts)} prompts in batches of {BATCH} on {MODEL}")

    client = ORClient(cap_usd=CAP_USD)
    async with aiohttp.ClientSession() as session:
        await client.load_catalog(session)
        batches = [prompts[k : k + BATCH] for k in range(0, len(prompts), BATCH)]
        sem = asyncio.Semaphore(8)

        async def guarded(b):
            async with sem:
                return await run_batch(client, session, b)

        results = await asyncio.gather(*[guarded(b) for b in batches], return_exceptions=True)

        by_i: dict[int, dict] = {}
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"batch raised {res}")
                continue
            for o in res:
                by_i[int(o["i"])] = o
        logger.info(f"got slots for {len(by_i)}/{len(prompts)} prompts; spend so far ${client.spent:.4f}")

        # one retry pass, singly, for anything missing
        missing = [p for p in prompts if p["i"] not in by_i]
        if missing:
            logger.warning(f"retrying {len(missing)} missing prompts individually")
            res2 = await asyncio.gather(*[guarded([m]) for m in missing], return_exceptions=True)
            for res in res2:
                if isinstance(res, list):
                    for o in res:
                        by_i[int(o["i"])] = o

    logger.info(f"FINAL: {len(by_i)}/{len(prompts)} slots; ${client.spent:.4f} over {client.n_calls} calls")

    rows = []
    for p in prompts:
        o = by_i.get(p["i"], {})
        rows.append(
            {
                "xstest_id": p["i"],
                "pair_uid": p["pair_uid"],
                "role": p["role"],
                "prompt": p["prompt"],
                "gerund": (o.get("gerund") or "").strip(),
                "infinitive": (o.get("infinitive") or "").strip(),
                "noun_phrase": (o.get("noun_phrase") or "").strip(),
                "extracted": bool(o.get("gerund")),
            }
        )
    n_ok = sum(r["extracted"] for r in rows)
    (ROOT / "results/action_slots.json").write_text(
        json.dumps(
            {
                "model": MODEL,
                "n_prompts": len(rows),
                "n_extracted": n_ok,
                "spend_usd": round(client.spent, 6),
                "n_calls": client.n_calls,
                "slots": rows,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    logger.info(f"wrote results/action_slots.json  ({n_ok}/{len(rows)} extracted)")


if __name__ == "__main__":
    asyncio.run(amain())
