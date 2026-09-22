#!/usr/bin/env python
"""Check HF repo metadata (gated status, license, configs, siblings) for a
fixed list of dataset repo ids, plus datasets-server info/size for row
counts and column schema. Writes one JSON blob per repo under
build/repo_meta/<safe_name>.json and retries on HF 429s.

Usage:
    .venv/bin/python src/check_repo_meta.py repo1 repo2 ...
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

_RETRY_AFTER_RE = re.compile(r"Retry after (\d+) seconds")


def safe_name(repo_id: str) -> str:
    return repo_id.replace("/", "__")


def hf_api_meta(repo_id: str, max_retries: int = 6) -> dict[str, Any]:
    """Use huggingface_hub.HfApi.dataset_info to get gated/license/siblings."""
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
                "siblings": [s.rfilename for s in (info.siblings or [])][:50],
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
    return {"exists": None, "error": "max retries exceeded"}


def ds_server_info(repo_id: str) -> dict[str, Any]:
    try:
        r = requests.get(
            "https://datasets-server.huggingface.co/info",
            params={"dataset": repo_id},
            timeout=30,
        )
        return {"status_code": r.status_code, "body": r.json()}
    except Exception as exc:  # noqa: BLE001
        return {"status_code": None, "error": str(exc)}


def ds_server_size(repo_id: str) -> dict[str, Any]:
    try:
        r = requests.get(
            "https://datasets-server.huggingface.co/size",
            params={"dataset": repo_id},
            timeout=30,
        )
        return {"status_code": r.status_code, "body": r.json()}
    except Exception as exc:  # noqa: BLE001
        return {"status_code": None, "error": str(exc)}


def main() -> None:
    repos = sys.argv[1:]
    if not repos:
        logger.error("usage: check_repo_meta.py repo1 repo2 ...")
        sys.exit(1)

    out_dir = WS / "build" / "repo_meta"
    out_dir.mkdir(parents=True, exist_ok=True)

    for repo_id in repos:
        logger.info(f"Checking {repo_id}")
        result = {
            "repo_id": repo_id,
            "hf_api": hf_api_meta(repo_id),
            "datasets_server_info": ds_server_info(repo_id),
            "datasets_server_size": ds_server_size(repo_id),
        }
        out_path = out_dir / f"{safe_name(repo_id)}.json"
        out_path.write_text(json.dumps(result, indent=2, default=str))
        logger.info(f"  -> {out_path} (gated={result['hf_api'].get('gated')})")


if __name__ == "__main__":
    main()
