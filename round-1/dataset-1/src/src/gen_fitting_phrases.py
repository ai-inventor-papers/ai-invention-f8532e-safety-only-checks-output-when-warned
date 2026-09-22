#!/usr/bin/env python3
"""Build the ACTION PHRASE pool for a fitting corpus, provably DISJOINT from XSTest.

Selects 64 harmful action sources (StrongREJECT-small, topped up from AdvBench)
and 64 benign action sources (Databricks Dolly-15k imperative/how-to instructions),
extracts gerund/infinitive/noun_phrase surface forms with a batched OpenRouter pass,
then enforces and reports two disjointness checks against XSTest:
  (a) no shared head-verb lemma (candidate infinitive vs XSTest action lemma set)
  (b) no shared word 4-gram (candidate source prompt vs the 450 XSTest prompts)
Rejects are replaced from the remaining pool until 64 clean items/side or pool
exhaustion, which is reported honestly rather than relaxing the checks.
"""
from __future__ import annotations

import asyncio
import csv
import itertools
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Callable

import aiohttp
from loguru import logger

sys.path.insert(0, "src")
from or_client import ORClient, parse_json  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/fitting.log", rotation="30 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
TEMP = ROOT / "temp" / "datasets"
RESULTS = ROOT / "results"

SEED = 20260920
N_PER_SIDE = 64
PRIMARY_MODEL = "google/gemini-3.8-flash"
SECOND_MODEL = "openai/gpt-5-nano"
BATCH_SIZE = 16
CAP_USD = 0.25
MAX_ROUNDS = 8  # replacement rounds per side, safety cap against runaway cost

FIXED_NEUTRAL_REQUEST = "Continue the following passage."

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

# ---------------------------------------------------------------------------
# Deterministic lemmatiser (no heavy NLP deps).
#
# RULE: lowercase the word, then:
#   1. look it up in a small irregular-verb table (common English irregulars,
#      covering past tense / past participle / 3sg / -ing forms);
#   2. else strip a regular inflectional suffix in this priority order:
#        -ies  -> -y            (e.g. "supplies" -> "supply")
#        -ing  -> "" (undouble a doubled final consonant, e.g. "running"->"run")
#        -ed   -> "" (same undoubling rule, e.g. "stopped"->"stop")
#        -es   -> ""            (e.g. "washes" -> "wash")
#        -s    -> "" (unless the word ends "ss")   (e.g. "kills" -> "kill")
#   3. else return the word unchanged (already a base form).
# ---------------------------------------------------------------------------
_IRREGULAR = {
    "is": "be", "are": "be", "was": "be", "were": "be", "been": "be", "being": "be", "am": "be",
    "has": "have", "had": "have", "having": "have",
    "does": "do", "did": "do", "doing": "do", "done": "do",
    "goes": "go", "went": "go", "going": "go", "gone": "go",
    "made": "make", "making": "make", "makes": "make",
    "took": "take", "taken": "take", "taking": "take", "takes": "take",
    "wrote": "write", "written": "write", "writing": "write", "writes": "write",
    "said": "say", "saying": "say", "says": "say",
    "bought": "buy", "buying": "buy", "buys": "buy",
    "sold": "sell", "selling": "sell", "sells": "sell",
    "built": "build", "building": "build", "builds": "build",
    "stole": "steal", "stolen": "steal", "stealing": "steal", "steals": "steal",
    "killed": "kill", "killing": "kill", "kills": "kill",
    "got": "get", "getting": "get", "gotten": "get", "gets": "get",
    "ran": "run", "running": "run", "runs": "run",
    "cutting": "cut", "cuts": "cut",
    "putting": "put", "puts": "put",
    "setting": "set", "sets": "set",
    "hitting": "hit", "hits": "hit",
    "shot": "shoot", "shooting": "shoot", "shoots": "shoot",
    "broke": "break", "breaking": "break", "broken": "break", "breaks": "break",
    "fought": "fight", "fighting": "fight", "fights": "fight",
    "sent": "send", "sending": "send", "sends": "send",
    "spent": "spend", "spending": "spend", "spends": "spend",
    "found": "find", "finding": "find", "finds": "find",
    "told": "tell", "telling": "tell", "tells": "tell",
    "led": "lead", "leading": "lead", "leads": "lead",
    "stood": "stand", "standing": "stand", "stands": "stand",
    "held": "hold", "holding": "hold", "holds": "hold",
    "kept": "keep", "keeping": "keep", "keeps": "keep",
    "left": "leave", "leaving": "leave", "leaves": "leave",
    "meant": "mean", "meaning": "mean", "means": "mean",
    "met": "meet", "meeting": "meet", "meets": "meet",
    "paid": "pay", "paying": "pay", "pays": "pay",
    "lost": "lose", "losing": "lose", "loses": "lose",
    "drew": "draw", "drawing": "draw", "draws": "draw", "drawn": "draw",
    "threw": "throw", "throwing": "throw", "throws": "throw", "thrown": "throw",
    "grew": "grow", "growing": "grow", "grows": "grow", "grown": "grow",
    "knew": "know", "knowing": "know", "knows": "know", "known": "know",
    "saw": "see", "seeing": "see", "sees": "see", "seen": "see",
    "came": "come", "coming": "come", "comes": "come",
    "gave": "give", "giving": "give", "gives": "give", "given": "give",
    "wearing": "wear", "wore": "wear", "worn": "wear", "wears": "wear",
    "hacking": "hack", "hacked": "hack", "hacks": "hack",
    "writing": "write",
}


def lemmatize(word: str) -> str:
    w = word.lower().strip()
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ing") and len(w) > 5:
        stem = w[:-3]
        if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            stem = stem[:-1]
        return stem
    if w.endswith("ed") and len(w) > 4:
        stem = w[:-2]
        if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] not in "aeiou":
            stem = stem[:-1]
        return stem
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and len(w) > 3 and not w.endswith("ss"):
        return w[:-1]
    return w


_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    t = _PUNCT_RE.sub(" ", text.lower())
    t = _WS_RE.sub(" ", t).strip()
    return t


def word_4grams(norm_text: str) -> set[tuple[str, ...]]:
    words = norm_text.split(" ")
    return {tuple(words[i : i + 4]) for i in range(len(words) - 3)} if len(words) >= 4 else set()


def head_verb_lemma(infinitive: str) -> str:
    norm = normalize_text(infinitive)
    if not norm:
        return ""
    first = norm.split(" ")[0]
    return lemmatize(first)


# ---------------------------------------------------------------------------
# Benign-source filter: imperative / how-to style, 5-25 words.
# ---------------------------------------------------------------------------
_IMPERATIVE_VERBS = {
    "list", "write", "give", "describe", "explain", "identify", "name", "summarize", "summarise",
    "provide", "generate", "create", "make", "compare", "classify", "convert", "calculate", "find",
    "determine", "rank", "sort", "translate", "design", "draft", "build", "construct", "come", "tell",
    "extract", "categorize", "categorise", "count", "define", "suggest", "recommend", "outline",
    "develop", "plan", "analyze", "analyse", "evaluate", "discuss", "highlight", "show", "illustrate",
    "demonstrate", "pick", "choose", "select", "arrange", "organize", "organise", "format", "edit",
    "rewrite", "paraphrase", "simplify", "expand", "shorten", "combine", "separate", "distinguish",
    "contrast", "state", "estimate", "predict", "propose", "review", "check", "assess", "add",
    "remove", "change", "modify", "correct", "fix", "improve", "explain", "draw", "plot", "outline",
    "brainstorm",
}


def is_imperative_or_howto(instruction: str, min_words: int = 5, max_words: int = 25) -> bool:
    words = instruction.strip().split()
    n = len(words)
    if not (min_words <= n <= max_words):
        return False
    first = re.sub(r"[^\w]", "", words[0]).lower() if words else ""
    is_imperative = first in _IMPERATIVE_VERBS
    is_howto = "how to" in instruction.lower()
    return is_imperative or is_howto


# ---------------------------------------------------------------------------
# Batched extraction helper
# ---------------------------------------------------------------------------
async def _run_batch(
    client: ORClient, session: aiohttp.ClientSession, model: str, batch: list[dict]
) -> list[dict]:
    items = "\n".join(f'{b["i"]}. {b["prompt"]}' for b in batch)
    r = await client.call(session, model=model, system=SYSTEM, user=TEMPLATE.format(items=items), max_tokens=4000)
    if r is None:
        logger.error(f"[{model}] batch starting at i={batch[0]['i']} returned None (budget or failure)")
        return []
    out = parse_json(r["text"])
    if not isinstance(out, list):
        logger.error(f"[{model}] batch i={batch[0]['i']}: unparseable reply: {r['text'][:200]!r}")
        return []
    return [o for o in out if isinstance(o, dict) and "i" in o]


async def extract_forms(
    client: ORClient, session: aiohttp.ClientSession, candidates: list[dict]
) -> dict[int, dict]:
    """candidates: list of {"i": int, "prompt": str, ...}. Returns {i: {gerund,infinitive,noun_phrase}}."""
    if not candidates:
        return {}
    batches = [candidates[k : k + BATCH_SIZE] for k in range(0, len(candidates), BATCH_SIZE)]
    sem = asyncio.Semaphore(8)

    async def guarded(b: list[dict]) -> list[dict]:
        async with sem:
            return await _run_batch(client, session, PRIMARY_MODEL, b)

    results = await asyncio.gather(*[guarded(b) for b in batches], return_exceptions=True)
    by_i: dict[int, dict] = {}
    for res in results:
        if isinstance(res, Exception):
            logger.error(f"primary batch raised {res}")
            continue
        for o in res:
            by_i[int(o["i"])] = o

    missing = [c for c in candidates if c["i"] not in by_i]
    if missing:
        logger.warning(f"primary missed {len(missing)}/{len(candidates)}; retrying individually on {SECOND_MODEL}")

        async def guarded2(b: list[dict]) -> list[dict]:
            async with sem:
                return await _run_batch(client, session, SECOND_MODEL, b)

        res2 = await asyncio.gather(*[guarded2([m]) for m in missing], return_exceptions=True)
        for res in res2:
            if isinstance(res, list):
                for o in res:
                    by_i[int(o["i"])] = o

    still_missing = [c for c in candidates if c["i"] not in by_i]
    for c in still_missing:
        logger.error(f"DECLINED BY BOTH FAMILIES: i={c['i']} prompt={c['prompt'][:120]!r}")

    return by_i


# ---------------------------------------------------------------------------
# Selection pipeline for one side (harmful / benign)
# ---------------------------------------------------------------------------
async def select_clean_side(
    *,
    name: str,
    initial: list[dict],
    next_fn: Callable[[], dict | None],
    xstest_4gram: set[tuple[str, ...]],
    xstest_action_lemmas: set[str],
    client: ORClient,
    session: aiohttp.ClientSession,
    id_counter: itertools.count,
) -> tuple[list[dict], int, int]:
    """Returns (accepted[<=64], n_rejected_4gram, n_rejected_lemma) for this side."""
    n_rejected_4gram = 0
    n_rejected_lemma = 0
    accepted: list[dict] = []

    def take_4gram_clean(n: int, pending: list[dict]) -> list[dict]:
        """Fill `n` slots with candidates passing the raw-prompt 4-gram check, pulling
        from `pending` first then from next_fn(); mutates n_rejected_4gram."""
        nonlocal n_rejected_4gram
        out: list[dict] = []
        pending_local = list(pending)
        while len(out) < n:
            if pending_local:
                cand = pending_local.pop(0)
            else:
                cand = next_fn()
                if cand is None:
                    break
            grams = word_4grams(normalize_text(cand["prompt"]))
            if grams & xstest_4gram:
                n_rejected_4gram += 1
                logger.debug(f"{name}: 4gram-reject source_row_id={cand.get('source_row_id')}")
                continue
            out.append(cand)
        return out

    round_candidates = take_4gram_clean(N_PER_SIDE, initial)
    round_no = 0
    while round_candidates and len(accepted) < N_PER_SIDE and round_no < MAX_ROUNDS:
        round_no += 1
        for c in round_candidates:
            c["i"] = next(id_counter)
        by_i = await extract_forms(client, session, round_candidates)

        need_more = 0
        for c in round_candidates:
            o = by_i.get(c["i"])
            if o is None:
                need_more += 1  # declined by both families -> dropped, needs replacement
                continue
            infinitive = (o.get("infinitive") or "").strip()
            gerund = (o.get("gerund") or "").strip()
            noun_phrase = (o.get("noun_phrase") or "").strip()
            if not infinitive:
                need_more += 1
                continue
            lemma = head_verb_lemma(infinitive)
            if lemma in xstest_action_lemmas:
                n_rejected_lemma += 1
                logger.debug(f"{name}: lemma-reject '{lemma}' source_row_id={c.get('source_row_id')} infinitive={infinitive!r}")
                need_more += 1
                continue
            c["gerund"], c["infinitive"], c["noun_phrase"] = gerund, infinitive, noun_phrase
            accepted.append(c)
            if len(accepted) >= N_PER_SIDE:
                break

        remaining_needed = N_PER_SIDE - len(accepted)
        if remaining_needed <= 0:
            break
        round_candidates = take_4gram_clean(remaining_needed, [])
        if not round_candidates:
            logger.warning(f"{name}: pool exhausted with {len(accepted)}/{N_PER_SIDE} accepted")
            break

    if len(accepted) < N_PER_SIDE:
        logger.warning(f"{name}: FINAL SHORTFALL {len(accepted)}/{N_PER_SIDE} after {round_no} rounds")
    return accepted[:N_PER_SIDE], n_rejected_4gram, n_rejected_lemma


@logger.catch(reraise=True)
async def amain() -> None:
    # ---- load inputs -----------------------------------------------------
    sr = json.loads((TEMP / "full_strongreject_small.json").read_text())
    adv = json.loads((TEMP / "full_advbench_harmful_behaviors.json").read_text())
    dolly = json.loads((TEMP / "full_databricks_dolly_15k.json").read_text())
    with (TEMP / "xstest_prompts.csv").open(newline="", encoding="utf-8") as f:
        xstest_rows = list(csv.DictReader(f))
    action_slots = json.loads((RESULTS / "action_slots.json").read_text())["slots"]

    logger.info(f"loaded sr={len(sr)} adv={len(adv)} dolly={len(dolly)} xstest_prompts={len(xstest_rows)} action_slots={len(action_slots)}")
    assert "forbidden_prompt" in sr[0], f"strongreject cols: {list(sr[0].keys())}"
    assert "goal" in adv[0], f"advbench cols: {list(adv[0].keys())}"
    assert "instruction" in dolly[0], f"dolly cols: {list(dolly[0].keys())}"
    assert "prompt" in xstest_rows[0], f"xstest cols: {list(xstest_rows[0].keys())}"

    # ---- build XSTest disjointness reference ------------------------------
    xstest_prompts = [r["prompt"] for r in xstest_rows]
    xstest_4gram: set[tuple[str, ...]] = set()
    for p in xstest_prompts:
        xstest_4gram |= word_4grams(normalize_text(p))
    xstest_action_lemmas: set[str] = set()
    for slot in action_slots:
        inf = (slot.get("infinitive") or "").strip()
        if inf:
            xstest_action_lemmas.add(head_verb_lemma(inf))
        ger = (slot.get("gerund") or "").strip()
        if ger:
            # gerund head verb: strip trailing 'ing' word then lemmatize via same rule
            first = normalize_text(ger).split(" ")[0] if normalize_text(ger) else ""
            if first:
                xstest_action_lemmas.add(lemmatize(first))
    logger.info(
        f"xstest reference built: {len(xstest_prompts)} prompts, {len(xstest_4gram)} 4-grams, "
        f"{len(action_slots)} action entries -> {len(xstest_action_lemmas)} unique head-verb lemmas"
    )

    # ---- build harmful pool: 60 SR + AdvBench top-up/replacement ----------
    sr_candidates = [
        {"source": "strongreject_small", "source_row_id": idx, "prompt": row["forbidden_prompt"]}
        for idx, row in enumerate(sr)
    ]
    adv_rng = random.Random(SEED)
    adv_order = adv_rng.sample(range(len(adv)), len(adv))
    adv_ptr = [0]

    def next_advbench() -> dict | None:
        if adv_ptr[0] >= len(adv_order):
            return None
        idx = adv_order[adv_ptr[0]]
        adv_ptr[0] += 1
        return {"source": "advbench", "source_row_id": idx, "prompt": adv[idx]["goal"]}

    harmful_initial = list(sr_candidates)
    while len(harmful_initial) < N_PER_SIDE:
        c = next_advbench()
        if c is None:
            break
        harmful_initial.append(c)
    logger.info(f"harmful initial pool: {len(sr_candidates)} SR + {len(harmful_initial) - len(sr_candidates)} AdvBench top-up = {len(harmful_initial)}")

    # ---- build benign pool: filtered Dolly instructions --------------------
    dolly_filtered_idx = [i for i, row in enumerate(dolly) if is_imperative_or_howto(row["instruction"])]
    logger.info(f"dolly rows passing imperative/how-to 5-25 word filter: {len(dolly_filtered_idx)}/{len(dolly)}")
    dolly_rng = random.Random(SEED)
    dolly_order = dolly_rng.sample(dolly_filtered_idx, len(dolly_filtered_idx))
    dolly_ptr = [0]

    def next_dolly() -> dict | None:
        if dolly_ptr[0] >= len(dolly_order):
            return None
        idx = dolly_order[dolly_ptr[0]]
        dolly_ptr[0] += 1
        return {"source": "databricks_dolly_15k", "source_row_id": idx, "prompt": dolly[idx]["instruction"]}

    benign_initial = []
    while len(benign_initial) < N_PER_SIDE:
        c = next_dolly()
        if c is None:
            break
        benign_initial.append(c)
    logger.info(f"benign initial pool: {len(benign_initial)} from Dolly")

    # ---- run OpenRouter pipeline -------------------------------------------
    client = ORClient(cap_usd=CAP_USD)
    id_counter = itertools.count()
    async with aiohttp.ClientSession() as session:
        await client.load_catalog(session)

        harmful_accepted, harm_rej_4g, harm_rej_lem = await select_clean_side(
            name="harmful",
            initial=harmful_initial,
            next_fn=next_advbench,
            xstest_4gram=xstest_4gram,
            xstest_action_lemmas=xstest_action_lemmas,
            client=client,
            session=session,
            id_counter=id_counter,
        )
        logger.info(f"harmful: {len(harmful_accepted)}/{N_PER_SIDE} accepted; spend so far ${client.spent:.4f}")

        benign_accepted, ben_rej_4g, ben_rej_lem = await select_clean_side(
            name="benign",
            initial=benign_initial,
            next_fn=next_dolly,
            xstest_4gram=xstest_4gram,
            xstest_action_lemmas=xstest_action_lemmas,
            client=client,
            session=session,
            id_counter=id_counter,
        )
        logger.info(f"benign: {len(benign_accepted)}/{N_PER_SIDE} accepted; spend so far ${client.spent:.4f}")

    n_rejected_shared_4gram = harm_rej_4g + ben_rej_4g
    n_rejected_shared_lemma = harm_rej_lem + ben_rej_lem

    # ---- final verification on the ACCEPTED sets ---------------------------
    def final_check(accepted: list[dict]) -> tuple[int, int]:
        shared_lemmas = 0
        shared_4grams = 0
        for c in accepted:
            lemma = head_verb_lemma(c["infinitive"])
            if lemma in xstest_action_lemmas:
                shared_lemmas += 1
            grams = word_4grams(normalize_text(c["prompt"]))
            if grams & xstest_4gram:
                shared_4grams += 1
        return shared_lemmas, shared_4grams

    h_lem, h_4g = final_check(harmful_accepted)
    b_lem, b_4g = final_check(benign_accepted)
    final_shared_lemmas = h_lem + b_lem
    final_shared_4grams = h_4g + b_4g
    logger.info(f"FINAL VERIFICATION: shared_lemmas={final_shared_lemmas} shared_4grams={final_shared_4grams}")

    def to_out(c: dict, idx: int) -> dict:
        return {
            "idx": idx,
            "source": c["source"],
            "source_row_id": c["source_row_id"],
            "prompt": c["prompt"],
            "gerund": c["gerund"],
            "infinitive": c["infinitive"],
            "noun_phrase": c["noun_phrase"],
        }

    output = {
        "fixed_neutral_request": FIXED_NEUTRAL_REQUEST,
        "disjointness": {
            "lemma_rule": (
                "lowercase; irregular-verb lookup table first; else strip regular suffixes in order "
                "-ies->-y, -ing/-ed (undoubling a doubled final consonant), -es, -s (unless -ss); "
                "compared on each candidate's INFINITIVE head verb vs. the head-verb lemma of every "
                "gerund/infinitive in the 300 XSTest action_slots.json entries"
            ),
            "n_rejected_shared_lemma": n_rejected_shared_lemma,
            "n_rejected_shared_4gram": n_rejected_shared_4gram,
            "final_shared_lemmas": final_shared_lemmas,
            "final_shared_4grams": final_shared_4grams,
            "xstest_reference_n_prompts": len(xstest_prompts),
            "xstest_reference_n_actions": len(action_slots),
        },
        "n_harmful": len(harmful_accepted),
        "n_benign": len(benign_accepted),
        "spend_usd": round(client.spent, 6),
        "n_calls": client.n_calls,
        "harmful": [to_out(c, i) for i, c in enumerate(harmful_accepted)],
        "benign": [to_out(c, i) for i, c in enumerate(benign_accepted)],
    }

    out_path = RESULTS / "fitting_phrases.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    logger.info(f"wrote {out_path}: n_harmful={output['n_harmful']} n_benign={output['n_benign']} spend=${output['spend_usd']} calls={output['n_calls']}")

    if output["n_harmful"] < N_PER_SIDE:
        logger.warning(f"SHORTFALL: only {output['n_harmful']}/{N_PER_SIDE} harmful items reached the clean set")
    if output["n_benign"] < N_PER_SIDE:
        logger.warning(f"SHORTFALL: only {output['n_benign']}/{N_PER_SIDE} benign items reached the clean set")


if __name__ == "__main__":
    asyncio.run(amain())
