#!/usr/bin/env python
"""Preview 25 shortlisted HF dataset candidates: pull configs/splits/features
from the datasets-server `/info` endpoint and 3 sample rows from
`/first-rows`, plus gated/license/downloads/likes from HfApi. Saves one
combined JSON to build/hf_candidates.json.

Usage:
    .venv/bin/python src/preview_candidates.py
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests
from loguru import logger

WS = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = Path("/ai-inventor/.claude/skills/aii-hf-datasets/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))

logger.remove()
logger.add(sys.stderr, level="INFO")

CANDIDATES = [
    "bench-llm/or-bench",
    "Paul/XSTest",
    "furonghuang-lab/PHTest",
    "AmazonScience/FalseReject",
    "Locutusque/FalseReject-sharegpt",
    "SillyTilly/SorryBench",
    "AIM-Harvard/sorrybench",
    "AlignmentResearch/SorryBench",
    "kylelovesllms/sorry-bench-with-refusals",
    "chcleung/sorry_bench_with_refusals",
    "JailbreakBench/JBB-Behaviors",
    "walledai/AdvBench",
    "carl213/advbench",
    "LibrAI/do-not-answer",
    "allenai/ai2_arc",
    "openai/gsm8k",
    "PKU-Alignment/PKU-SafeRLHF",
    "PKU-Alignment/BeaverTails",
    "tau/commonsense_qa",
    "nvidia/Aegis-AI-Content-Safety-Dataset-2.0",
    "allenai/real-toxicity-prompts",
    "walledai/HarmBench",
    "walledai/StrongREJECT",
    "deepset/prompt-injections",
    "natolambert/xstest-v2-copy",
]

_RETRY_AFTER_RE = re.compile(r"Retry after (\d+) seconds")


def hf_api_meta(repo_id: str, max_retries: int = 5) -> dict[str, Any]:
    from huggingface_hub import HfApi
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError

    api = HfApi()
    for attempt in range(1, max_retries + 1):
        try:
            info = api.dataset_info(repo_id, files_metadata=False)
            card = info.cardData or {}
            return {
                "exists": True,
                "gated": info.gated,
                "private": info.private,
                "license": card.get("license"),
                "downloads": info.downloads,
                "likes": info.likes,
                "siblings": [s.rfilename for s in (info.siblings or [])][:60],
                "tags": info.tags[:15] if info.tags else [],
            }
        except GatedRepoError as e:
            return {"exists": True, "gated": True, "error": str(e)}
        except RepositoryNotFoundError as e:
            return {"exists": False, "error": str(e)}
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            m = _RETRY_AFTER_RE.search(msg)
            if m and attempt < max_retries:
                wait_s = int(m.group(1)) + 3
                logger.warning(f"{repo_id}: 429'd (attempt {attempt}), sleeping {wait_s}s")
                time.sleep(wait_s)
                continue
            return {"exists": None, "error": msg}
    return {"exists": None, "error": "max retries"}


def ds_server_info(repo_id: str) -> dict[str, Any]:
    try:
        r = requests.get("https://datasets-server.huggingface.co/info", params={"dataset": repo_id}, timeout=30)
        return {"status_code": r.status_code, "body": r.json()}
    except Exception as exc:  # noqa: BLE001
        return {"status_code": None, "error": str(exc)}


def ds_server_first_rows(repo_id: str, config: str, split: str, n: int = 3) -> dict[str, Any]:
    try:
        r = requests.get(
            "https://datasets-server.huggingface.co/first-rows",
            params={"dataset": repo_id, "config": config, "split": split},
            timeout=30,
        )
        body = r.json()
        rows = body.get("rows", [])[:n]
        return {"status_code": r.status_code, "rows": [row.get("row") for row in rows], "error": body.get("error")}
    except Exception as exc:  # noqa: BLE001
        return {"status_code": None, "error": str(exc)}


def preview_one(repo_id: str) -> dict[str, Any]:
    logger.info(f"Previewing {repo_id}")
    meta = hf_api_meta(repo_id)
    info = ds_server_info(repo_id)
    sample_rows = {}
    if info.get("status_code") == 200:
        dinfo = info["body"].get("dataset_info", {})
        for config_name, cfg in list(dinfo.items())[:5]:
            splits = list(cfg.get("splits", {}).keys())
            split = "train" if "train" in splits else (splits[0] if splits else None)
            if split:
                sample_rows[config_name] = ds_server_first_rows(repo_id, config_name, split)
    return {
        "repo_id": repo_id,
        "hf_api": meta,
        "datasets_server_info": info,
        "sample_rows": sample_rows,
    }


def main() -> None:
    results = []
    for repo_id in CANDIDATES:
        results.append(preview_one(repo_id))
    out_path = WS / "build" / "hf_candidates.json"
    out_path.write_text(json.dumps({"n_candidates": len(results), "candidates": results}, indent=2, default=str))
    logger.info(f"Saved {len(results)} candidate previews to {out_path}")


if __name__ == "__main__":
    main()
