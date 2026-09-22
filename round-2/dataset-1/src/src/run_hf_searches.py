#!/usr/bin/env python
"""Run a batch of HuggingFace dataset searches and save raw results to JSON.

Imports the aii-hf-datasets skill's search script directly (bypassing the
CLI's plain-text output) so we can capture full structured results per query.

Usage:
    .venv/bin/python src/run_hf_searches.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from loguru import logger

WS = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = Path("/ai-inventor/.claude/skills/aii-hf-datasets/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))

logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(WS / "logs" / "run_hf_searches_{time}.log", rotation="10 MB")

QUERIES: list[str] = [
    "refusal",
    "over-refusal",
    "exaggerated safety",
    "false refusal",
    "safety benchmark",
    "jailbreak",
    "red teaming",
    "harmful instructions",
    "harmless prompts",
    "dual use",
    "toxicity prompts",
    "LLM safety evaluation",
    "alignment evaluation",
    "instruction following safety",
    "do not answer",
    "safety guardrails",
    "prompt injection",
    "adversarial prompts",
    "content moderation",
    "harm taxonomy",
    "harm severity",
    "refusal classification",
    "compliance",
    "borderline prompts",
    "pseudo-harmful",
    "safe completion",
    "model refusal responses",
    "chat safety",
    "guard model",
    "policy violation",
    "reasoning benchmark",
    "grade school math",
    "multiple choice science QA",
    "commonsense QA",
    "instruction tuning data",
    "helpful assistant responses",
    "benign instructions",
    "sensitive topics",
    "self-harm",
    "misinformation",
    "privacy prompts",
    "hate speech prompts",
    "illegal activity prompts",
    "wrapped jailbreak templates",
    "persona jailbreak",
    "linguistic mutation prompts",
    "safety refusal pairs",
    "minimal pairs safety",
    "contrast prompts",
    "xstest",
    "or-bench",
    "sorry-bench",
    "advbench",
    "jailbreakbench",
    "wildguard",
    "beavertails",
    "harmbench",
    "aegis safety",
    "salad-bench",
    "strongreject",
    "false reject",
    "dangerous capabilities",
    "toxic comment classification",
    "safe rlhf",
]


_RETRY_AFTER_RE = re.compile(r"Retry after (\d+) seconds")


def run_one(query: str, max_retries: int = 6) -> dict[str, Any]:
    """Run a single search query via the skill's core search function.

    Retries on HF's 429 rate-limit responses, sleeping for the
    server-provided "Retry after N seconds" duration (shared quota across
    concurrent agents on this HF token, so 429s are expected).
    """
    import aii_hf_search_datasets as m

    m.init_search_datasets()
    last_err = None
    for attempt in range(1, max_retries + 1):
        result = m.core_search_datasets(query=query, limit=8, tags="", sort="downloads")
        if result.get("success"):
            result["query"] = query
            return result
        last_err = result.get("error", "")
        match = _RETRY_AFTER_RE.search(last_err or "")
        if match and attempt < max_retries:
            wait_s = int(match.group(1)) + 3
            logger.warning(f"query={query!r} 429'd (attempt {attempt}/{max_retries}), sleeping {wait_s}s")
            time.sleep(wait_s)
            continue
        break
    return {"success": False, "query": query, "error": last_err}


@logger.catch(reraise=True)
def main() -> None:
    out_path = WS / "build" / "hf_search_log.json"
    all_results: list[dict[str, Any]] = []

    # Low concurrency to respect HF API rate limits (each search itself
    # fans out ~8 concurrent calls for card+loadable checks).
    with ThreadPoolExecutor(max_workers=2) as ex:
        futures = {ex.submit(run_one, q): q for q in QUERIES}
        for i, fut in enumerate(as_completed(futures), 1):
            q = futures[fut]
            res = fut.result()
            n = res.get("count", 0) if res.get("success") else "ERR"
            logger.info(f"[{i}/{len(QUERIES)}] query={q!r} -> {n}")
            all_results.append(res)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"queries_run": len(QUERIES), "results": all_results}, indent=2))
    logger.info(f"Saved {len(all_results)} query results to {out_path}")


if __name__ == "__main__":
    main()
