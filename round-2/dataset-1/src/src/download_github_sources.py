#!/usr/bin/env python
"""Download the two non-HF primary sources directly from their original
GitHub repos (plain HTTP CSV fetch), because the HF mirrors we were told
to prefer are either missing required columns (natolambert/xstest-v2-copy
lacks `focus`/`label`) or now gated (walledai/AdvBench returned
gated='auto' when checked live on 2026-09-21).

Usage:
    .venv/bin/python src/download_github_sources.py
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import requests
from loguru import logger

WS = Path(__file__).resolve().parents[1]
OUT_DIR = WS / "temp" / "datasets"

SOURCES = [
    {
        "source_id": "xstest_github",
        "url": "https://raw.githubusercontent.com/paul-rottger/exaggerated-safety/main/xstest_prompts.csv",
        "safe_dir": "xstest_github",
        "expected_header": ["id", "prompt", "type", "label", "focus", "note"],
        "expected_rows": 450,
        "notes": (
            "Primary source per task spec: paul-rottger/exaggerated-safety GitHub repo "
            "(XSTest paper: Rottger et al. 2024, NAACL, https://aclanthology.org/2024.naacl-long.301/). "
            "Chosen over HF mirrors: Paul/XSTest (HF) ships the same file but the GitHub repo is the "
            "canonical source; natolambert/xstest-v2-copy is explicitly excluded per task instructions "
            "because it lacks the `focus` and `label` columns."
        ),
    },
    {
        "source_id": "advbench_github",
        "url": "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv",
        "safe_dir": "advbench_github",
        "expected_header": ["goal", "target"],
        "expected_rows": 520,
        "notes": (
            "walledai/AdvBench (the task's suggested source) was verified LIVE on 2026-09-21 and returned "
            "gated='auto' (401 on datasets-server), so per hard rule 2 it is unusable without authenticating. "
            "Fell back to the ORIGINAL AdvBench source: llm-attacks/llm-attacks GitHub repo "
            "(Zou et al. 2023, 'Universal and Transferable Adversarial Attacks on Aligned Language Models', "
            "arXiv:2307.15043 -- the same arXiv id cited in walledai/AdvBench's own HF tags, confirming "
            "provenance). Row count (520) matches the community mirror carl213/advbench (ungated, 520 rows) "
            "used as a cross-check."
        ),
    },
]


def main() -> None:
    for src in SOURCES:
        logger.info(f"Fetching {src['source_id']} from {src['url']}")
        resp = requests.get(src["url"], timeout=60)
        resp.raise_for_status()
        text = resp.text
        reader = csv.DictReader(io.StringIO(text))
        header = reader.fieldnames
        rows = list(reader)

        out_dir = OUT_DIR / src["safe_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)
        data_path = out_dir / "data.json"
        data_path.write_text(json.dumps(rows, indent=None))
        n_bytes = data_path.stat().st_size

        header_match = header == src["expected_header"]
        rows_match = len(rows) == src["expected_rows"]
        if not header_match:
            logger.warning(f"  HEADER MISMATCH: got {header}, expected {src['expected_header']}")
        if not rows_match:
            logger.warning(f"  ROW COUNT MISMATCH: got {len(rows)}, expected {src['expected_rows']}")

        meta = {
            "source_id": src["source_id"],
            "source_url": src["url"],
            "config": None,
            "split": "n/a (single CSV file)",
            "n_rows_downloaded": len(rows),
            "header": header,
            "header_matches_expected": header_match,
            "n_rows_matches_expected": rows_match,
            "local_path": str(data_path),
            "bytes_on_disk": n_bytes,
            "download_command": f"requests.get({src['url']!r})",
            "notes": src["notes"],
        }
        (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2))
        logger.info(f"  -> {len(rows)} rows, {n_bytes/1e6:.3f} MB -> {data_path} (header_ok={header_match}, rows_ok={rows_match})")


if __name__ == "__main__":
    main()
