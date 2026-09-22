#!/usr/bin/env python
"""Assemble build/sources_manifest.json from the per-source _meta.json files
under temp/datasets/, enriched with license/gated/revision metadata pulled
from build/hf_candidates.json (or a fresh HfApi call for GitHub-only
sources) and a provenance URL per source.

Usage:
    .venv/bin/python src/build_manifest.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger

WS = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = Path("/ai-inventor/.claude/skills/aii-hf-datasets/scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))

logger.remove()
logger.add(sys.stderr, level="INFO")

# repo_id -> provenance URL (paper / benchmark page), used when not a plain
# GitHub source (those carry their own provenance_url already).
PROVENANCE = {
    "bench-llm/or-bench": "https://arxiv.org/abs/2405.20947",
    "furonghuang-lab/PHTest": "https://arxiv.org/abs/2409.00598",
    "AmazonScience/FalseReject": "https://arxiv.org/html/2505.08054v1",
    "SillyTilly/SorryBench": "https://arxiv.org/abs/2406.14598",
    "JailbreakBench/JBB-Behaviors": "https://proceedings.neurips.cc/paper_files/paper/2024/file/63092d79154adebd7305dfd498cbff70-Paper-Datasets_and_Benchmarks_Track.pdf",
    "LibrAI/do-not-answer": "https://aclanthology.org/2024.findings-eacl.61/",
    "allenai/ai2_arc": "https://arxiv.org/abs/1803.05457",
    "openai/gsm8k": "https://arxiv.org/abs/2110.14168",
    "PKU-Alignment/PKU-SafeRLHF": "https://arxiv.org/html/2406.15513v1",
    "PKU-Alignment/BeaverTails": "https://arxiv.org/abs/2307.04657",
}


def get_hf_revision(repo_id: str) -> str | None:
    try:
        from huggingface_hub import HfApi

        api = HfApi()
        info = api.dataset_info(repo_id, files_metadata=False)
        return info.sha
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"could not fetch revision for {repo_id}: {exc}")
        return None


def main() -> None:
    candidates = json.loads((WS / "build" / "hf_candidates.json").read_text())
    cand_by_id = {c["repo_id"]: c for c in candidates["candidates"]}

    now = datetime.now(timezone.utc).isoformat()
    manifest = []

    dataset_dirs = sorted((WS / "temp" / "datasets").iterdir())
    for d in dataset_dirs:
        meta_path = d / "_meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        repo = meta.get("hf_repo")
        entry: dict[str, Any] = {
            "source_id": meta["source_id"],
            "hf_repo_or_url": repo or meta.get("source_url"),
            "config": meta.get("config"),
            "split": meta.get("split"),
            "n_rows": meta.get("n_rows_downloaded"),
            "columns": meta.get("columns") or meta.get("header"),
            "local_path": meta["local_path"],
            "bytes": meta["bytes_on_disk"],
            "verified_at_utc": now,
            "notes": meta.get("notes", ""),
        }
        if repo:
            cand = cand_by_id.get(repo, {})
            hf_api = cand.get("hf_api", {})
            entry["license"] = hf_api.get("license")
            entry["gated"] = hf_api.get("gated")
            entry["revision"] = get_hf_revision(repo)
            entry["provenance_url"] = PROVENANCE.get(repo, f"https://huggingface.co/datasets/{repo}")
        else:
            # GitHub-only source
            entry["license"] = "CC-BY-4.0 (XSTest paper license)" if "xstest" in meta["source_id"] else "MIT (AdvBench repo license)"
            entry["gated"] = False
            entry["revision"] = "main (GitHub, not pinned to a commit SHA)"
            entry["provenance_url"] = meta.get("source_url")

        manifest.append(entry)
        logger.info(f"Added {entry['source_id']}")

    out_path = WS / "build" / "sources_manifest.json"
    out_path.write_text(json.dumps(manifest, indent=2, default=str))
    total_bytes = sum(e["bytes"] for e in manifest)
    logger.info(f"Wrote {len(manifest)} entries, total {total_bytes/1e6:.2f} MB, to {out_path}")


if __name__ == "__main__":
    main()
