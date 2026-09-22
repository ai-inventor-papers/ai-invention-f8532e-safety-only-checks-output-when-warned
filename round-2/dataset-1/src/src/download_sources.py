#!/usr/bin/env python
"""Download the KEEP list of HF-hosted datasets for the frozen safety /
refusal dataset build. Each source is written to
temp/datasets/<safe_name>/<split_or_config>.json plus a sibling _meta.json
recording repo id, config, split, row count, columns, license, gated
status, revision, local path, download bytes and the exact command run.

Two non-HF sources (XSTest, AdvBench) are fetched directly from their
original GitHub repos via download_github_sources.py (kept separate
because they are plain HTTP CSV fetches, not `datasets.load_dataset`
calls).

Usage:
    .venv/bin/python src/download_sources.py
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

WS = Path(__file__).resolve().parents[1]
OUT_DIR = WS / "temp" / "datasets"

logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(WS / "logs" / "download_sources_{time}.log", rotation="10 MB")


@dataclass
class Job:
    source_id: str
    repo_id: str
    config: str | None
    split: str
    safe_dir: str
    max_rows: int | None = None
    notes: str = ""
    license_hint: str | None = None


JOBS: list[Job] = [
    # --- 1. OR-Bench: 3 configs ---
    Job("or_bench_hard_1k", "bench-llm/or-bench", "or-bench-hard-1k", "train", "or_bench_hard_1k",
        notes="Full download, expected 1319 rows."),
    Job("or_bench_toxic", "bench-llm/or-bench", "or-bench-toxic", "train", "or_bench_toxic",
        notes="Full download, expected 655 rows."),
    Job("or_bench_80k_sample", "bench-llm/or-bench", "or-bench-80k", "train", "or_bench_80k_sample",
        max_rows=8000, notes="Sampled first 8000 of 80359 rows to keep bytes down per hard rule 1."),
    # --- 3. PHTest ---
    Job("phtest", "furonghuang-lab/PHTest", None, "train", "phtest",
        notes="Expected ~3269 rows, columns ID/Request/Harmfulness."),
    # --- 4. FalseReject (ungated primary; both splits, small) ---
    Job("falsereject_train", "AmazonScience/FalseReject", None, "train", "falsereject_train",
        notes="14,624 rows, synthetic instruct/cot responses."),
    Job("falsereject_test", "AmazonScience/FalseReject", None, "test", "falsereject_test",
        notes="1,187 human-annotated rows."),
    # --- 5. SORRY-Bench WRAPPED mirror ---
    Job("sorrybench_sillytilly", "SillyTilly/SorryBench", None, "train", "sorrybench_sillytilly",
        notes="Ungated mirror; vintage 202406 per sorry_bench_202406.csv sibling file. 9450 rows = 450 base Qs x 21 prompt_style variants."),
    # --- 6. JailbreakBench ---
    Job("jbb_behaviors", "JailbreakBench/JBB-Behaviors", "behaviors", "harmful", "jbb_behaviors_harmful"),
    Job("jbb_behaviors_benign", "JailbreakBench/JBB-Behaviors", "behaviors", "benign", "jbb_behaviors_benign"),
    Job("jbb_judge_comparison", "JailbreakBench/JBB-Behaviors", "judge_comparison", "test", "jbb_judge_comparison"),
    # --- 8. do-not-answer ---
    Job("do_not_answer", "LibrAI/do-not-answer", None, "train", "do_not_answer",
        notes="Expected 939 rows, 23 columns. License is apache-2.0 per HF card + GitHub LICENSE (NOT CC-BY-NC-SA-4.0)."),
    # --- 9. ARC-Easy ---
    Job("arc_easy_test", "allenai/ai2_arc", "ARC-Easy", "test", "arc_easy_test",
        notes="Expected 2376 rows."),
    # --- 10. GSM8K ---
    Job("gsm8k_main_test", "openai/gsm8k", "main", "test", "gsm8k_main_test"),
    # --- 11. Graded harm severity ---
    Job("pku_saferlhf_test", "PKU-Alignment/PKU-SafeRLHF", "default", "test", "pku_saferlhf_test",
        notes="8211 rows; response_0_severity_level/response_1_severity_level are the ordinal graded-harm field."),
    # --- 12. Additional strong source ---
    Job("beavertails_30k_test", "PKU-Alignment/BeaverTails", "default", "30k_test", "beavertails_30k_test",
        notes="Additional strong harmful/harmless QA source (NeurIPS 2023, 15.5k HF downloads); 30k_test split chosen to stay small (3021 rows)."),
]


def load_and_dump(job: Job) -> dict[str, Any]:
    from datasets import load_dataset

    logger.info(f"Loading {job.repo_id} config={job.config} split={job.split}")
    t0 = time.time()
    ds = load_dataset(job.repo_id, job.config, split=job.split)
    n_total = len(ds)
    if job.max_rows is not None and n_total > job.max_rows:
        ds = ds.select(range(job.max_rows))
    rows = ds.to_list()
    columns = list(ds.features.keys())
    elapsed = time.time() - t0

    out_dir = OUT_DIR / job.safe_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    data_path = out_dir / "data.json"
    data_path.write_text(json.dumps(rows, indent=None, default=str))
    n_bytes = data_path.stat().st_size

    meta = {
        "source_id": job.source_id,
        "hf_repo": job.repo_id,
        "config": job.config,
        "split": job.split,
        "n_rows_downloaded": len(rows),
        "n_rows_total_upstream": n_total,
        "sampled": job.max_rows is not None and n_total > job.max_rows,
        "columns": columns,
        "local_path": str(data_path),
        "bytes_on_disk": n_bytes,
        "download_command": f"datasets.load_dataset({job.repo_id!r}, {job.config!r}, split={job.split!r})",
        "elapsed_seconds": round(elapsed, 2),
        "notes": job.notes,
    }
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2))
    logger.info(f"  -> {len(rows)} rows, {n_bytes/1e6:.2f} MB -> {data_path}")
    return meta


def main() -> None:
    all_meta = []
    total_bytes = 0
    for job in JOBS:
        try:
            meta = load_and_dump(job)
            all_meta.append(meta)
            total_bytes += meta["bytes_on_disk"]
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"FAILED: {job.source_id} ({job.repo_id})")
            all_meta.append({"source_id": job.source_id, "hf_repo": job.repo_id, "error": str(exc), "failed": True})

    summary_path = WS / "build" / "download_summary.json"
    summary_path.write_text(json.dumps({"total_bytes": total_bytes, "jobs": all_meta}, indent=2))
    logger.info(f"TOTAL downloaded bytes (this script): {total_bytes/1e6:.2f} MB")
    logger.info(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
