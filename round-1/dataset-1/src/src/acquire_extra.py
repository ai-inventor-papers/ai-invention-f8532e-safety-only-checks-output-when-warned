#!/usr/bin/env python3
"""Acquire 5 ADDITIONAL vetted HuggingFace safety datasets and append them to
the existing sources_manifest.json (does not overwrite existing entries).

Targets (all previewed first to discover real config/split names, then
loaded, per the task instructions):

  1. swiss-ai/harmbench                              -- ungated HarmBench mirror
  2. SillyTilly/SorryBench                            -- SORRY-Bench 44-category harmful requests
  3. LibrAI/do-not-answer                             -- refusal-worthy prompts + pre-computed responses
  4. PKU-Alignment/BeaverTails-Evaluation              -- 700 held-out prompts, 14 categories
  5. nvidia/Aegis-AI-Content-Safety-Dataset-2.0        -- human-LLM interactions + hazard taxonomy

Each dataset is saved as temp/datasets/full_<safe_name>.json (list of row
objects) plus temp/datasets/preview_<safe_name>.json (first 3 rows). If the
full JSON would exceed 60MB, a seeded 5000-row subsample is saved instead
(random.Random(20260920)).

One manifest entry per dataset (mirroring the exact key set already used by
sources_manifest.json) is APPENDED to its existing "sources" list; the
top-level "total_bytes" is updated to include the new bytes; existing
entries and top-level keys are preserved untouched.

Loads for the 5 datasets are parallelised with a ThreadPoolExecutor.
"""

from __future__ import annotations

import hashlib
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from datasets import load_dataset
from huggingface_hub import HfApi, hf_hub_download
from huggingface_hub.utils import GatedRepoError, HfHubHTTPError
from loguru import logger

# --------------------------------------------------------------------------
# Paths / constants
# --------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parents[1]
DATASETS_DIR = WORKSPACE / "temp" / "datasets"
LOGS_DIR = WORKSPACE / "logs"
MANIFEST_PATH = WORKSPACE / "sources_manifest.json"

FULL_FILE_KEEP_LIMIT_BYTES = 60 * 1024 * 1024  # keep full file only if <60MB
SAMPLE_SEED = 20260920
SAMPLE_SIZE = 5000

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logger.add(LOGS_DIR / "acquire_extra.log", rotation="30 MB", level="DEBUG")


@dataclass
class SourceResult:
    name: str
    url_or_repo: str
    config: str | None
    split: str | None
    revision: str | None
    fetched_at: str
    n_rows_actually_loaded: int | None
    expected_rows: int | None
    rows_match: bool | None
    column_names: list[str]
    license: str
    sha256: str
    local_path: str
    bytes_on_disk: int
    status: str = "ok"
    notes: str = ""


def safe_name(name: str) -> str:
    return name.replace("/", "_").replace("-", "_").replace(" ", "_").lower()


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, obj: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, indent=2, default=str, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def save_rows(name_safe: str, rows: list[dict]) -> tuple[Path, int, str]:
    """Save full JSON (or a seeded 5000-row subsample if >60MB) + 3-row preview.

    Returns (saved_path, bytes_on_disk, notes_suffix).
    """
    full_path = DATASETS_DIR / f"full_{name_safe}.json"
    preview_path = DATASETS_DIR / f"preview_{name_safe}.json"
    write_json(preview_path, rows[:3])

    full_bytes_estimate = len(json.dumps(rows, default=str, ensure_ascii=False).encode("utf-8"))
    if full_bytes_estimate > FULL_FILE_KEEP_LIMIT_BYTES:
        rng = random.Random(SAMPLE_SEED)
        sample_n = min(SAMPLE_SIZE, len(rows))
        sample_rows = rng.sample(rows, sample_n)
        sample_path = DATASETS_DIR / f"full_{name_safe}_sample{sample_n}.json"
        written_bytes = write_json(sample_path, sample_rows)
        note = (
            f"Full JSON would have been {full_bytes_estimate / 1e6:.1f}MB (>60MB) — "
            f"saved a seeded (random.Random({SAMPLE_SEED})) {sample_n}-row subsample instead "
            f"of the full {len(rows)} rows."
        )
        logger.warning(f"{name_safe}: {note}")
        return sample_path, written_bytes, note

    written_bytes = write_json(full_path, rows)
    return full_path, written_bytes, ""


# --------------------------------------------------------------------------
# Gating check (mirrors src/acquire_sources.py convention)
# --------------------------------------------------------------------------
def check_gated(api: HfApi, repo_id: str) -> tuple[bool, str]:
    """Return (is_actually_gated_for_anon_access, note)."""
    try:
        info = api.dataset_info(repo_id)
        gated_flag = info.gated
        if not gated_flag:
            return False, "gated=False per dataset_info"
        siblings = info.siblings or []
        if not siblings:
            return True, f"gated={gated_flag}, no files listed"
        target = next(
            (s.rfilename for s in siblings if s.rfilename.endswith((".parquet", ".json", ".jsonl", ".csv"))),
            siblings[0].rfilename,
        )
        try:
            hf_hub_download(repo_id=repo_id, filename=target, repo_type="dataset", token=False)
            return False, f"gated={gated_flag} but anonymous file download succeeded"
        except GatedRepoError as e:
            return True, f"gated={gated_flag}, anonymous download returned 401: {str(e)[:150]}"
        except HfHubHTTPError as e:
            if "401" in str(e):
                return True, f"gated={gated_flag}, anonymous download returned 401: {str(e)[:150]}"
            raise
    except Exception as e:
        logger.exception(f"Gate check failed for {repo_id}")
        return True, f"gate check errored: {e}"


def get_license(api: HfApi, repo_id: str) -> str:
    try:
        info = api.dataset_info(repo_id)
        card = info.cardData or {}
        lic = card.get("license") if hasattr(card, "get") else None
        if isinstance(lic, list):
            lic = ", ".join(lic)
        return lic if lic else "unverified"
    except Exception:
        logger.exception(f"Could not resolve license for {repo_id}")
        return "unverified"


def get_revision(api: HfApi, repo_id: str) -> str | None:
    try:
        info = api.dataset_info(repo_id)
        return info.sha
    except Exception:
        logger.exception(f"Could not resolve revision for {repo_id}")
        return None


# --------------------------------------------------------------------------
# Per-dataset load specs
# --------------------------------------------------------------------------
@dataclass
class HFSpec:
    name: str
    repo_id: str
    config: str | None
    splits: list[str]  # loaded and concatenated (order preserved); manifest "split" = "+".join(splits)
    expected_rows: int | None
    config_choice_note: str = ""


SPECS: list[HFSpec] = [
    HFSpec(
        name="harmbench",
        repo_id="swiss-ai/harmbench",
        config="DirectRequest",
        splits=["val", "test"],
        expected_rows=400,
        config_choice_note=(
            "swiss-ai/harmbench has 2 configs: 'DirectRequest' (clean, unwrapped harmful "
            "behavior/request text in the 'Behavior' column) and 'HumanJailbreaks' (the SAME "
            "behaviors re-wrapped inside jailbreak templates, 4x larger). Took 'DirectRequest' "
            "because it carries the prompt/request text directly, per instructions. Combined "
            "the 'val' and 'test' splits (both are held-out behavior partitions, not an ML "
            "train/test split) for full coverage of the 400 behaviors."
        ),
    ),
    HFSpec(
        name="sorrybench",
        repo_id="SillyTilly/SorryBench",
        config="default",
        splits=["train"],
        expected_rows=9450,
        config_choice_note="Only one config ('default') and split ('train') exist; 'turns' holds the harmful request text across 44 categories x multiple prompt_style perturbations.",
    ),
    HFSpec(
        name="do_not_answer",
        repo_id="LibrAI/do-not-answer",
        config="default",
        splits=["train"],
        expected_rows=939,
        config_choice_note="Only one config ('default') and split ('train') exist; 'question' holds the prompt text, with pre-computed *_response columns from 5 LLMs.",
    ),
    HFSpec(
        name="beavertails_evaluation",
        repo_id="PKU-Alignment/BeaverTails-Evaluation",
        config="default",
        splits=["test"],
        expected_rows=700,
        config_choice_note="Only one config ('default'); the single populated split is 'test' (700 held-out prompts, 14 categories) — matches the task's row-count expectation exactly.",
    ),
    HFSpec(
        name="aegis_content_safety_2_0",
        repo_id="nvidia/Aegis-AI-Content-Safety-Dataset-2.0",
        config="default",
        splits=["train"],
        expected_rows=30007,
        config_choice_note="Only one config ('default'); took the 'train' split (validation/test also exist but 'train' alone carries the bulk of the human-LLM prompt/response rows with the hazard-category labels).",
    ),
]


def load_one(spec: HFSpec, api: HfApi) -> SourceResult:
    logger.info(f"[preview] {spec.name} <- {spec.repo_id} (discovering config/split before load)")
    is_gated, gate_note = check_gated(api, spec.repo_id)
    fetched_at = datetime.now(timezone.utc).isoformat()
    revision = get_revision(api, spec.repo_id)
    license_str = get_license(api, spec.repo_id)

    if is_gated:
        logger.warning(f"{spec.name} ({spec.repo_id}) is GATED for anonymous access ({gate_note}) — skipping, no auth attempted")
        return SourceResult(
            name=spec.name,
            url_or_repo=spec.repo_id,
            config=spec.config,
            split="+".join(spec.splits),
            revision=revision,
            fetched_at=fetched_at,
            n_rows_actually_loaded=None,
            expected_rows=spec.expected_rows,
            rows_match=None,
            column_names=[],
            license=license_str,
            sha256="",
            local_path="",
            bytes_on_disk=0,
            status="skipped_gated",
            notes=gate_note,
        )

    logger.info(f"[load] {spec.name} <- {spec.repo_id} config={spec.config} splits={spec.splits}")
    try:
        rows: list[dict] = []
        for split in spec.splits:
            ds = load_dataset(spec.repo_id, spec.config, split=split, revision=revision)
            split_rows = [dict(r) for r in ds]
            for r in split_rows:
                r["_source_split"] = split
            rows.extend(split_rows)
            logger.info(f"[load] {spec.name}: split={split} -> {len(split_rows)} rows")
    except (GatedRepoError,) as e:
        note = f"anonymous download returned 401 during load: {str(e)[:200]}"
        logger.warning(f"{spec.name} ({spec.repo_id}) turned out GATED at load time — {note}")
        return SourceResult(
            name=spec.name, url_or_repo=spec.repo_id, config=spec.config, split="+".join(spec.splits),
            revision=revision, fetched_at=fetched_at, n_rows_actually_loaded=None, expected_rows=spec.expected_rows,
            rows_match=None, column_names=[], license=license_str, sha256="", local_path="", bytes_on_disk=0,
            status="skipped_gated", notes=note,
        )
    except HfHubHTTPError as e:
        if "401" in str(e):
            note = f"anonymous download returned 401 during load: {str(e)[:200]}"
            logger.warning(f"{spec.name} ({spec.repo_id}) turned out GATED at load time — {note}")
            return SourceResult(
                name=spec.name, url_or_repo=spec.repo_id, config=spec.config, split="+".join(spec.splits),
                revision=revision, fetched_at=fetched_at, n_rows_actually_loaded=None, expected_rows=spec.expected_rows,
                rows_match=None, column_names=[], license=license_str, sha256="", local_path="", bytes_on_disk=0,
                status="skipped_gated", notes=note,
            )
        raise

    n_rows = len(rows)
    expected = spec.expected_rows
    rows_match = (n_rows == expected) if expected is not None else None
    if rows_match is False:
        logger.warning(f"[load] {spec.name}: row count mismatch — got {n_rows}, expected {expected}")

    name_s = safe_name(spec.name)
    saved_path, bytes_on_disk, subsample_note = save_rows(name_s, rows)

    saved_rows = json.loads(saved_path.read_text(encoding="utf-8"))
    raw_bytes = saved_path.read_bytes()
    digest = sha256_of_bytes(raw_bytes)
    columns = list(saved_rows[0].keys()) if saved_rows else []

    notes = spec.config_choice_note
    if subsample_note:
        notes = f"{notes} | {subsample_note}"

    return SourceResult(
        name=spec.name,
        url_or_repo=spec.repo_id,
        config=spec.config,
        split="+".join(spec.splits),
        revision=revision,
        fetched_at=fetched_at,
        n_rows_actually_loaded=len(saved_rows) if subsample_note else n_rows,
        expected_rows=expected,
        rows_match=rows_match,
        column_names=columns,
        license=license_str,
        sha256=digest,
        local_path=str(saved_path.relative_to(WORKSPACE)),
        bytes_on_disk=bytes_on_disk,
        notes=notes,
    )


def load_all(specs: list[HFSpec]) -> list[SourceResult]:
    api = HfApi()
    results: list[SourceResult] = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(load_one, spec, api): spec for spec in specs}
        for fut in as_completed(futures):
            spec = futures[fut]
            try:
                results.append(fut.result())
            except Exception:
                logger.exception(f"[load] FAILED to load {spec.name} ({spec.repo_id})")
                raise
    # preserve SPECS order in the output for a stable/readable manifest & report
    order = {s.name: i for i, s in enumerate(specs)}
    results.sort(key=lambda r: order[r.name])
    return results


# --------------------------------------------------------------------------
# Manifest append
# --------------------------------------------------------------------------
def append_to_manifest(new_results: list[SourceResult]) -> tuple[int, int]:
    """Read the existing manifest, append new entries, write it back.

    Returns (n_existing_entries_before, n_entries_after).
    """
    existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    n_before = len(existing["sources"])
    existing_keys = set(existing["sources"][0].keys()) if existing["sources"] else None

    new_entries = [asdict(r) for r in new_results]
    if existing_keys is not None:
        for e in new_entries:
            if set(e.keys()) != existing_keys:
                raise ValueError(f"Key-set mismatch for {e['name']}: {set(e.keys())} != {existing_keys}")

    existing["sources"].extend(new_entries)
    existing["total_bytes"] = int(existing.get("total_bytes", 0)) + sum(r.bytes_on_disk for r in new_results)
    # keep original top-level "fetched_at" untouched (append-only semantics);
    # existing top-level keys are otherwise preserved as-is.
    write_json(MANIFEST_PATH, existing)
    n_after = len(existing["sources"])
    return n_before, n_after


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
@logger.catch(reraise=True)
def main() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()

    logger.info(f"=== Loading {len(SPECS)} additional HF datasets (thread pool, parallel) ===")
    for s in SPECS:
        logger.info(f"  - {s.name}: {s.repo_id}")

    results = load_all(SPECS)

    logger.info("=== Appending to existing sources_manifest.json ===")
    n_before, n_after = append_to_manifest(results)
    logger.info(f"sources_manifest.json: {n_before} existing entries -> {n_after} total entries (+{n_after - n_before})")

    logger.info("=== FINAL TABLE: dataset | config | split | rows | bytes | license | status ===")
    header = f"{'name':<26} {'config':<16} {'split':<10} {'rows':>8} {'bytes':>10} {'license':<16} status"
    logger.info(header)
    logger.info("-" * len(header))
    for r in results:
        rows_disp = r.n_rows_actually_loaded if r.n_rows_actually_loaded is not None else "-"
        logger.info(
            f"{r.name:<26} {str(r.config):<16} {str(r.split):<10} {str(rows_disp):>8} "
            f"{r.bytes_on_disk:>10} {r.license:<16} [{r.status}]"
        )

    gated = [r for r in results if r.status != "ok"]
    if gated:
        logger.warning(f"GATED / skipped datasets: {[r.name for r in gated]}")
    else:
        logger.info("No datasets were gated — all 5 loaded successfully.")

    elapsed = time.time() - started
    logger.info(f"Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
