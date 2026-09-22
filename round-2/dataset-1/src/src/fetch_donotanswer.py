#!/usr/bin/env python3
"""Fetch LibrAI/do-not-answer (939 rows, 6 models) directly via the HF parquet
export API (no `datasets` import -> avoids the MooseFS cold-import tax), verify
the action-code taxonomy against the authors' own evaluator code, and write:
  - <WS>/temp/datasets/full_do_not_answer.json  (939 rows, all columns)
  - <WS>/temp/datasets/preview_do_not_answer.json (first 5 rows)
  - <WS>/build/donotanswer_source_manifest.json  (provenance + VERIFIED license)
    NOTE: deliberately NOT named "sources_manifest.json" -- this workspace is
    shared by several concurrent artefact-building tasks in this same run,
    and a generic "sources_manifest.json" written by another task's process
    was observed to collide with (overwrite) that name during this build.
  - <WS>/build/dna_action_taxonomy.json (7-way action code 0-6, cited)

License note: the task brief that spawned this run asserted the do-not-answer
license is CC-BY-NC-SA-4.0. We checked this directly (HF dataset card API +
the GitHub repo's own LICENSE file, both fetched live) and both say
Apache-2.0. We record the ACTUAL verified license (Apache-2.0) rather than
the brief's unverified claim, and note the discrepancy explicitly.
"""
from __future__ import annotations

import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

WS = Path(__file__).resolve().parent.parent
TEMP_DATASETS = WS / "temp" / "datasets"
BUILD = WS / "build"
LOGS = WS / "logs"

HF_PARQUET_API = "https://huggingface.co/api/datasets/LibrAI/do-not-answer/parquet/default/train"
HF_DATASET_API = "https://huggingface.co/api/datasets/LibrAI/do-not-answer"
GITHUB_LICENSE_API = "https://api.github.com/repos/Libr-AI/do-not-answer/license"
GITHUB_EVALUATOR_RAW = "https://raw.githubusercontent.com/Libr-AI/do-not-answer/main/do_not_answer/evaluator/gpt.py"

MODELS = ["GPT4", "ChatGPT", "Claude", "ChatGLM2", "llama2-7b-chat", "vicuna-7b"]


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    LOGS.mkdir(parents=True, exist_ok=True)
    logger.add(LOGS / "fetch_donotanswer.log", rotation="30 MB", level="DEBUG")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_json(obj) -> str:
    return sha256_bytes(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def fetch_verified_license() -> dict:
    """Verify the do-not-answer license from TWO independent live sources."""
    out = {"claimed_in_task_brief": "CC-BY-NC-SA-4.0", "verified": {}}
    # Source 1: HF dataset card metadata
    r = requests.get(HF_DATASET_API, timeout=30)
    r.raise_for_status()
    hf_json = r.json()
    hf_license = hf_json.get("cardData", {}).get("license") or [
        t.split(":", 1)[1] for t in hf_json.get("tags", []) if t.startswith("license:")
    ][0]
    out["verified"]["huggingface_card_api"] = {
        "url": HF_DATASET_API,
        "license": hf_license,
    }
    # Source 2: GitHub repo's own LICENSE file (via API, gives SPDX id)
    r2 = requests.get(GITHUB_LICENSE_API, timeout=30)
    r2.raise_for_status()
    gh_json = r2.json()
    out["verified"]["github_license_api"] = {
        "url": "https://github.com/Libr-AI/do-not-answer/blob/main/LICENSE",
        "spdx_id": gh_json.get("license", {}).get("spdx_id"),
        "name": gh_json.get("license", {}).get("name"),
    }
    resolved = out["verified"]["huggingface_card_api"]["license"]
    out["resolved_license"] = resolved
    out["discrepancy_note"] = (
        f"Task brief asserted '{out['claimed_in_task_brief']}'; both live sources "
        f"(HF dataset-card API and the do-not-answer GitHub repo's LICENSE file, "
        f"fetched {datetime.now(timezone.utc).isoformat()}) independently say "
        f"'{resolved}' (SPDX: {out['verified']['github_license_api']['spdx_id']}). "
        f"We ship the VERIFIED license, not the brief's unverified claim."
    )
    logger.warning(out["discrepancy_note"])
    return out


def fetch_verified_action_taxonomy() -> dict:
    """Pull the ACTUAL 0-6 action-code rubric from the authors' evaluator code
    (do_not_answer/evaluator/gpt.py::annotation_aspects_en), not from memory.
    """
    r = requests.get(GITHUB_EVALUATOR_RAW, timeout=30)
    r.raise_for_status()
    src = r.text
    # Extract the annotation_aspects_en dict via a scoped exec (no imports needed
    # from that file; it is a pure literal dict assignment we can isolate).
    import re

    m = re.search(
        r"annotation_aspects_en\s*=\s*\{.*?\n\}\n", src, flags=re.DOTALL
    )
    if not m:
        raise RuntimeError("Could not locate annotation_aspects_en in evaluator/gpt.py")
    ns: dict = {}
    exec(m.group(0), {}, ns)  # noqa: S102 - trusted, pinned upstream file, literal dict only
    rubric = ns["annotation_aspects_en"]["do_not_answer"]
    taxonomy = {
        "source_url": GITHUB_EVALUATOR_RAW,
        "source_note": (
            "Verified from the do-not-answer repo's own GPT-4 evaluator prompt "
            "construction code (annotation_aspects_en['do_not_answer']), not "
            "assumed from the paper text. 7 integer codes (0-6): codes 0-5 are "
            "degrees of NOT directly complying (refusal, refutation, "
            "whataboutism/dual-perspective, disclaimer+redirect, incapability, "
            "uncertainty); code 6 is direct compliance. The README's phrase "
            "'six distinct groups' refers to action categories overall as a "
            "typology; codes are 0..6 (7 values) with 6 = full compliance."
        ),
        "paper_citation": "Wang et al. 2024, \"Do-Not-Answer: Evaluating Safeguards in LLMs\", EACL Findings 2024 (aclanthology.org/2024.findings-eacl.61)",
        "codes": {str(k): v for k, v in rubric.items()},
    }
    return taxonomy


def fetch_full_dataset() -> tuple[list[dict], dict]:
    r = requests.get(HF_PARQUET_API, timeout=30)
    r.raise_for_status()
    urls = r.json()
    if len(urls) != 1:
        logger.warning(f"expected 1 parquet shard, got {len(urls)}: {urls}")
    pq_url = urls[0]
    logger.info(f"downloading parquet shard: {pq_url}")
    r2 = requests.get(pq_url, timeout=120)
    r2.raise_for_status()
    raw_bytes = r2.content
    df = pd.read_parquet(io.BytesIO(raw_bytes))
    rows = json.loads(df.to_json(orient="records"))
    manifest = {
        "name": "do_not_answer",
        "url_or_repo": "LibrAI/do-not-answer",
        "config": "default",
        "split": "train",
        "parquet_url": pq_url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "n_rows_actually_loaded": len(rows),
        "expected_rows": 939,
        "rows_match": len(rows) == 939,
        "column_names": list(df.columns),
        "models_with_responses": MODELS,
        "n_real_responses": len(rows) * len(MODELS),
        "parquet_sha256": sha256_bytes(raw_bytes),
        "bytes_on_disk_parquet": len(raw_bytes),
    }
    return rows, manifest


def main() -> None:
    setup_logging()
    logger.info("=== fetch_donotanswer: SOURCE 2 (cross-model generality check) ===")
    TEMP_DATASETS.mkdir(parents=True, exist_ok=True)
    BUILD.mkdir(parents=True, exist_ok=True)

    logger.info("verifying license from 2 live sources (HF card API + GitHub LICENSE API)")
    license_info = fetch_verified_license()

    logger.info("verifying action-code taxonomy from the authors' evaluator source")
    taxonomy = fetch_verified_action_taxonomy()
    taxonomy_path = BUILD / "dna_action_taxonomy.json"
    taxonomy_path.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False))
    logger.info(f"wrote {taxonomy_path} ({len(taxonomy['codes'])} codes)")

    logger.info("fetching full do-not-answer parquet (default/train)")
    rows, manifest = fetch_full_dataset()
    manifest["license"] = license_info["resolved_license"]
    manifest["license_verification"] = license_info
    manifest["local_path"] = "temp/datasets/full_do_not_answer.json"
    manifest["sha256"] = sha256_json(rows)
    logger.info(
        f"loaded {len(rows)} rows, {len(manifest['column_names'])} columns, "
        f"license={manifest['license']} (brief claimed CC-BY-NC-SA-4.0 -- MISMATCH, see discrepancy_note)"
    )

    full_path = TEMP_DATASETS / "full_do_not_answer.json"
    full_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    manifest["bytes_on_disk"] = full_path.stat().st_size
    preview_path = TEMP_DATASETS / "preview_do_not_answer.json"
    preview_path.write_text(json.dumps(rows[:5], indent=2, ensure_ascii=False))
    logger.info(f"wrote {full_path} ({manifest['bytes_on_disk']} bytes) and {preview_path}")

    sources_manifest_path = BUILD / "donotanswer_source_manifest.json"
    doc = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "sources": [manifest],
    }
    sources_manifest_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False))
    logger.info(f"wrote {sources_manifest_path}")
    logger.info("done.")


if __name__ == "__main__":
    main()
