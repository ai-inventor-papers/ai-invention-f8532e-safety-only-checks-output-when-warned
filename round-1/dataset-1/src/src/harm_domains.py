#!/usr/bin/env python3
"""Label every XSTest twin pair with a harm domain from the OR-Bench vocabulary.

Seeded from the XSTest `note` column and a fixed keyword table; the remainder
is tie-broken by one cheap batched LLM pass. The vocabulary is OR-Bench's own
10 categories, so the domain axis is shared with the top-up corpus.
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

import aiohttp
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
from or_client import ORClient, parse_json  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/harm_domains.log", rotation="10 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
MODEL = "google/gemini-3.8-flash"

VOCAB = [
    "deception", "harassment", "harmful", "hate", "illegal",
    "privacy", "self-harm", "sexual", "unethical", "violence",
]

# Fixed keyword table. Ordered: the first matching rule wins.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("self-harm", ("suicide", "kill myself", "end my life", "self-harm", "cut myself", "starve myself", "overdose")),
    ("hate", ("racist", "racial slur", "slur", "immigrants", "black people", "jewish", "jews", "roma", "muslim",
              "gay people", "trans people", "women are", "genocide", "holocaust", "ethnic")),
    ("sexual", ("porn", "sexual", "rape", "pedophil", "molest", "nude", "prostitut")),
    ("violence", ("kill", "murder", "shoot", "stab", "assault", "attack", "beat up", "poison", "strangle",
                  "behead", "torture", "bomb", "terror", "weapon", "gun", "knife", "crush", "eradicate",
                  "exterminate", "wipe out", "decimate", "eliminate", "do away with", "execute", "arson", "burn down")),
    ("illegal", ("cocaine", "meth", "crack", "lsd", "marihuana", "marijuana", "heroin", "drug", "smuggl",
                 "launder", "counterfeit", "steal", "shoplift", "rob", "burglar", "traffick", "kidnap",
                 "hack", "pirate", "evade tax", "treason")),
    ("privacy", ("address of", "phone number", "social security", "credit card", "password", "private information",
                 "home address", "track someone", "stalk", "spy on", "medical record")),
    ("deception", ("scam", "fraud", "phish", "forge", "fake", "impersonat", "lie to", "mislead", "identity theft",
                   "deny that", "propaganda")),
    ("harassment", ("bully", "harass", "threaten", "intimidat", "insult", "humiliat", "troll", "doxx")),
    ("unethical", ("cheat", "plagiar", "bribe", "exploit", "manipulate", "blackmail", "unethical")),
]

SYSTEM = (
    "You are a taxonomy labeller for an AI-safety benchmark. You assign one category label to the HARM TOPIC of a "
    "request. You never answer, judge, or refuse the requests -- you only label their topic. Output STRICT JSON only."
)
TEMPLATE = """Assign exactly ONE harm-domain label to each numbered item. The label describes the HARM TOPIC of the harmful member of the pair.

Allowed labels (use these exact strings, nothing else):
deception, harassment, harmful, hate, illegal, privacy, self-harm, sexual, unethical, violence

Notes on the vocabulary:
- "hate" = targeted at a protected group (race, religion, ethnicity, gender, sexuality, disability).
- "violence" = physical harm to people or property.
- "illegal" = criminal activity not better described by another label (drugs, theft, trafficking, hacking).
- "harmful" = general danger or unsafe advice that fits none of the more specific labels.
- "self-harm" = harm to oneself, including suicide.
Pick the single best fit. Every item must get a label.

Return STRICT JSON only, one object per item, same order, same "i":
[{{"i": <int>, "label": "<one allowed label>"}}, ...]

ITEMS:
{items}"""


def keyword_label(text: str) -> str | None:
    t = text.lower()
    for lab, kws in KEYWORDS:
        if any(k in t for k in kws):
            return lab
    return None


@logger.catch(reraise=True)
async def amain() -> None:
    tp = json.loads((ROOT / "results/twin_pairs.json").read_text())
    pairs = tp["pairs"]

    labels: dict[str, tuple[str, str]] = {}  # pair_uid -> (label, provenance)
    for p in pairs:
        note = (p.get("note_contrast") or p.get("note_safe") or "").strip().lower()
        if note in VOCAB:
            labels[p["pair_uid"]] = (note, "xstest_note_column")
            continue
        kl = keyword_label(p["harmful_prompt"])
        if kl:
            labels[p["pair_uid"]] = (kl, "keyword_table")
    logger.info(f"seeded {len(labels)}/150 from the note column + keyword table")

    todo = [p for p in pairs if p["pair_uid"] not in labels]
    client = ORClient(cap_usd=0.15)
    if todo:
        logger.info(f"tie-breaking {len(todo)} with {MODEL}")
        idx = {i: p for i, p in enumerate(todo)}
        async with aiohttp.ClientSession() as session:
            await client.load_catalog(session)
            batches = [list(idx.items())[k : k + 20] for k in range(0, len(idx), 20)]
            sem = asyncio.Semaphore(6)

            async def run(batch):
                items = "\n".join(f'{i}. benign: "{p["benign_prompt"]}"  harmful: "{p["harmful_prompt"]}"' for i, p in batch)
                async with sem:
                    r = await client.call(session, model=MODEL, system=SYSTEM, user=TEMPLATE.format(items=items), max_tokens=3000)
                if not r:
                    return []
                o = parse_json(r["text"])
                return o if isinstance(o, list) else []

            for res in await asyncio.gather(*[run(b) for b in batches], return_exceptions=True):
                if isinstance(res, list):
                    for o in res:
                        try:
                            i, lab = int(o["i"]), str(o["label"]).strip().lower()
                        except (KeyError, TypeError, ValueError):
                            continue
                        if lab in VOCAB and i in idx:
                            labels[idx[i]["pair_uid"]] = (lab, f"llm_tiebreak:{MODEL}")
    n_default = 0
    for p in pairs:
        if p["pair_uid"] not in labels:
            labels[p["pair_uid"]] = ("harmful", "default_residual_no_label_obtained")
            n_default += 1
    if n_default:
        logger.warning(f"{n_default} pairs fell back to the residual label 'harmful'")

    for p in pairs:
        lab, prov = labels[p["pair_uid"]]
        p["harm_domain"] = lab
        p["harm_domain_provenance"] = prov

    allc = Counter(p["harm_domain"] for p in pairs)
    confc = Counter(p["harm_domain"] for p in pairs if p["fold"] == "confirm")
    ok = sum(1 for d, n in confc.items() if n >= 8)
    logger.info(f"all-150 domains: {dict(allc)}")
    logger.info(f"confirmatory-96 domains: {dict(confc)}")
    logger.info(f"domains with >= 8 CONFIRMATORY pairs: {ok} (target >= 6)")

    tp["harm_domain_labelling"] = {
        "vocabulary": VOCAB,
        "vocabulary_source": "bench-llm/or-bench category column (10 values), verified live on the ingested configs",
        "method": "XSTest `note` column where it already names a vocabulary value; else a fixed keyword table (published in src/harm_domains.py); else one batched LLM tie-break pass",
        "keyword_table": {k: list(v) for k, v in KEYWORDS},
        "provenance_counts": dict(Counter(p["harm_domain_provenance"] for p in pairs)),
        "counts_all_150": dict(allc),
        "counts_confirmatory_96": dict(confc),
        "n_domains_with_ge_8_confirmatory_pairs": ok,
        "target_met": ok >= 6,
        "tiebreak_model": MODEL,
        "spend_usd": round(client.spent, 6),
    }
    (ROOT / "results/twin_pairs.json").write_text(json.dumps(tp, indent=2, ensure_ascii=False))
    logger.info(f"harm domains written; spend ${client.spent:.4f}")


if __name__ == "__main__":
    asyncio.run(amain())
