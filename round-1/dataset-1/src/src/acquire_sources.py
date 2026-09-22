#!/usr/bin/env python3
"""Acquire SOURCE datasets for the safety mech-interp stimulus build.

Downloads real datasets only (never synthesizes rows) from:
  - direct-URL CSVs (StrongREJECT, AdvBench) via aiohttp
  - HuggingFace Hub datasets (or-bench, JBB-Behaviors, PHTest, dolly-15k,
    alpaca, HarmBench-if-ungated, wildguardmix-or-BeaverTails) via the
    `datasets` library, parallelised with a thread pool.

Writes every dataset under temp/datasets/ and a manifest to
sources_manifest.json at the workspace root.
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd
from datasets import load_dataset
from huggingface_hub import HfApi
from huggingface_hub.utils import GatedRepoError, HfHubHTTPError
from loguru import logger

# --------------------------------------------------------------------------
# Paths / constants
# --------------------------------------------------------------------------
WORKSPACE = Path(__file__).resolve().parents[1]
DATASETS_DIR = WORKSPACE / "temp" / "datasets"
LOGS_DIR = WORKSPACE / "logs"
MANIFEST_PATH = WORKSPACE / "sources_manifest.json"

DOWNLOAD_BUDGET_BYTES = 200 * 1024 * 1024  # 200 MB total budget
FULL_FILE_KEEP_LIMIT_BYTES = 60 * 1024 * 1024  # keep full file only if <60MB
SAMPLE_SEED = 20260920
SAMPLE_SIZE = 500
FORBIDDEN_OR_BENCH_CONFIG = "or-bench-80k"

OR_BENCH_EXPECTED = {
    "or-bench-hard-1k": {
        "illegal": 527, "privacy": 199, "unethical": 125, "harmful": 106,
        "deception": 72, "violence": 66, "sexual": 66, "self-harm": 63,
        "hate": 54, "harassment": 41,
    },
    "or-bench-toxic": {
        "self-harm": 92, "deception": 83, "harassment": 76, "sexual": 73,
        "violence": 71, "unethical": 61, "privacy": 61, "hate": 58,
        "illegal": 50, "harmful": 30,
    },
}

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
LOGS_DIR.mkdir(parents=True, exist_ok=True)
logger.add(LOGS_DIR / "acquire.log", rotation="30 MB", level="DEBUG")


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


def save_rows(name_safe: str, rows: list[dict], *, force_sample_only: bool = False) -> tuple[Path, int]:
    """Save full JSON + 3-row preview. Returns (full_path, full_bytes).

    If the full JSON would exceed FULL_FILE_KEEP_LIMIT_BYTES, only a 500-row
    sample is kept (caller decides whether to also request a sample file).
    """
    full_path = DATASETS_DIR / f"full_{name_safe}.json"
    preview_path = DATASETS_DIR / f"preview_{name_safe}.json"

    full_bytes = len(json.dumps(rows, default=str, ensure_ascii=False).encode("utf-8"))
    if force_sample_only or full_bytes > FULL_FILE_KEEP_LIMIT_BYTES:
        rng = random.Random(SAMPLE_SEED)
        sample_n = min(SAMPLE_SIZE, len(rows))
        sample_rows = rng.sample(rows, sample_n)
        sample_path = DATASETS_DIR / f"full_{name_safe}_sample500.json"
        write_json(sample_path, sample_rows)
        logger.warning(
            f"{name_safe}: full JSON would be {full_bytes / 1e6:.1f}MB (>60MB) — "
            f"keeping ONLY the {sample_n}-row seeded sample at {sample_path.name}"
        )
        write_json(preview_path, rows[:3])
        return sample_path, sample_path.stat().st_size

    written_bytes = write_json(full_path, rows)
    write_json(preview_path, rows[:3])
    return full_path, written_bytes


def maybe_write_extra_sample(name_safe: str, rows: list[dict]) -> None:
    """For alpaca/dolly: always also write a seeded 500-row sample file."""
    rng = random.Random(SAMPLE_SEED)
    sample_n = min(SAMPLE_SIZE, len(rows))
    sample_rows = rng.sample(rows, sample_n)
    sample_path = DATASETS_DIR / f"full_{name_safe}_sample500.json"
    write_json(sample_path, sample_rows)
    logger.info(f"{name_safe}: wrote seeded {sample_n}-row sample -> {sample_path.name}")


# --------------------------------------------------------------------------
# Direct-URL CSV sources
# --------------------------------------------------------------------------
DIRECT_URL_SOURCES = [
    {
        "name": "strongreject_small",
        "url": "https://raw.githubusercontent.com/alexandrasouly/strongreject/main/strongreject_dataset/strongreject_small_dataset.csv",
        "expected_rows": 60,
        "license": "MIT",
        "repo_for_license": "alexandrasouly/strongreject",
    },
    {
        "name": "strongreject_full",
        "url": "https://raw.githubusercontent.com/alexandrasouly/strongreject/main/strongreject_dataset/strongreject_dataset.csv",
        "expected_rows": 313,
        "license": "MIT",
        "repo_for_license": "alexandrasouly/strongreject",
    },
    {
        "name": "advbench_harmful_behaviors",
        "url": "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_behaviors.csv",
        "expected_rows": 520,
        "license": "MIT",
        "repo_for_license": "llm-attacks/llm-attacks",
    },
    {
        "name": "advbench_harmful_strings",
        "url": "https://raw.githubusercontent.com/llm-attacks/llm-attacks/main/data/advbench/harmful_strings.csv",
        "expected_rows": None,
        "license": "MIT",
        "repo_for_license": "llm-attacks/llm-attacks",
    },
]


async def fetch_one_url(session: aiohttp.ClientSession, spec: dict) -> SourceResult:
    name = spec["name"]
    url = spec["url"]
    logger.info(f"[URL] fetching {name} <- {url}")
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
        resp.raise_for_status()
        raw = await resp.read()
    fetched_at = datetime.now(timezone.utc).isoformat()
    digest = sha256_of_bytes(raw)

    df = pd.read_csv(io.BytesIO(raw))
    rows = df.to_dict(orient="records")
    n_rows = len(rows)
    expected = spec["expected_rows"]
    rows_match = (n_rows == expected) if expected is not None else None
    if rows_match is False:
        logger.warning(f"[URL] {name}: row count mismatch — got {n_rows}, expected {expected}")

    name_s = safe_name(name)
    full_path, bytes_on_disk = save_rows(name_s, rows)

    return SourceResult(
        name=name,
        url_or_repo=url,
        config=None,
        split=None,
        revision=None,
        fetched_at=fetched_at,
        n_rows_actually_loaded=n_rows,
        expected_rows=expected,
        rows_match=rows_match,
        column_names=list(df.columns),
        license=spec["license"],
        sha256=digest,
        local_path=str(full_path.relative_to(WORKSPACE)),
        bytes_on_disk=bytes_on_disk,
    )


async def fetch_all_urls(specs: list[dict]) -> list[SourceResult]:
    async with aiohttp.ClientSession(headers={"User-Agent": "aii-source-acquire/1.0"}) as session:
        tasks = [fetch_one_url(session, spec) for spec in specs]
        results = []
        for coro in asyncio.as_completed(tasks):
            try:
                results.append(await coro)
            except Exception:
                logger.exception("A direct-URL fetch failed")
                raise
        return results


# --------------------------------------------------------------------------
# HuggingFace sources
# --------------------------------------------------------------------------
@dataclass
class HFSpec:
    name: str
    repo_id: str
    config: str | None
    split: str
    expected_rows: int | None
    row_cap: int | None = None
    force_sample_only: bool = False
    gate_check_only: bool = False  # if True: check gating, don't load
    fallback_note: str = ""


def get_license(api: HfApi, repo_id: str) -> str:
    try:
        info = api.dataset_info(repo_id)
        card = info.cardData or {}
        lic = card.get("license")
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


def check_gated(api: HfApi, repo_id: str) -> tuple[bool, str]:
    """Return (is_actually_gated_for_anon_access, note)."""
    try:
        info = api.dataset_info(repo_id)
        gated_flag = info.gated
        if not gated_flag:
            return False, "gated=False per dataset_info"
        # gated flag is truthy ("auto"/"manual") — verify with an actual
        # anonymous file request, since "auto" can still 401 without a token.
        siblings = info.siblings or []
        if not siblings:
            return True, f"gated={gated_flag}, no files listed"
        from huggingface_hub import hf_hub_download

        target = next((s.rfilename for s in siblings if s.rfilename.endswith((".parquet", ".json", ".jsonl", ".csv"))), siblings[0].rfilename)
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


def load_hf_source(spec: HFSpec, api: HfApi) -> SourceResult | None:
    logger.info(f"[HF] loading {spec.name} <- {spec.repo_id} config={spec.config} split={spec.split}")
    revision = get_revision(api, spec.repo_id)
    license_str = get_license(api, spec.repo_id)
    fetched_at = datetime.now(timezone.utc).isoformat()

    ds = load_dataset(spec.repo_id, spec.config, split=spec.split, revision=revision)
    rows = [dict(r) for r in ds]

    if spec.row_cap is not None and len(rows) > spec.row_cap:
        logger.info(f"[HF] {spec.name}: capping {len(rows)} -> {spec.row_cap} rows")
        rows = rows[: spec.row_cap]

    n_rows = len(rows)
    expected = spec.expected_rows
    rows_match = (n_rows == expected) if expected is not None else None
    if rows_match is False:
        logger.warning(f"[HF] {spec.name}: row count mismatch — got {n_rows}, expected {expected}")

    name_s = safe_name(spec.name)
    full_path, bytes_on_disk = save_rows(name_s, rows, force_sample_only=spec.force_sample_only)

    raw_bytes = json.dumps(rows, default=str, ensure_ascii=False).encode("utf-8")
    digest = sha256_of_bytes(raw_bytes)

    columns = list(rows[0].keys()) if rows else []

    return SourceResult(
        name=spec.name,
        url_or_repo=spec.repo_id,
        config=spec.config,
        split=spec.split,
        revision=revision,
        fetched_at=fetched_at,
        n_rows_actually_loaded=n_rows,
        expected_rows=expected,
        rows_match=rows_match,
        column_names=columns,
        license=license_str,
        sha256=digest,
        local_path=str(full_path.relative_to(WORKSPACE)),
        bytes_on_disk=bytes_on_disk,
        notes=spec.fallback_note,
    )


def build_hf_specs(api: HfApi) -> tuple[list[HFSpec], list[SourceResult]]:
    """Return (specs_to_load, skipped_results_for_gated_sources)."""
    specs: list[HFSpec] = [
        HFSpec("or_bench_toxic", "bench-llm/or-bench", "or-bench-toxic", "train", 655),
        HFSpec("or_bench_hard_1k", "bench-llm/or-bench", "or-bench-hard-1k", "train", 1319),
        HFSpec("jbb_behaviors_harmful", "JailbreakBench/JBB-Behaviors", "behaviors", "harmful", 100),
        HFSpec("jbb_behaviors_benign", "JailbreakBench/JBB-Behaviors", "behaviors", "benign", 100),
        HFSpec("phtest", "furonghuang-lab/PHTest", "default", "train", 3269),
        HFSpec("databricks_dolly_15k", "databricks/databricks-dolly-15k", None, "train", None),
        HFSpec("alpaca", "tatsu-lab/alpaca", None, "train", None),
    ]

    skipped: list[SourceResult] = []

    # --- item 12: walledai/HarmBench, only if ungated ---
    hb_gated, hb_note = check_gated(api, "walledai/HarmBench")
    if hb_gated:
        logger.warning(f"walledai/HarmBench is GATED for anonymous access ({hb_note}) — skipping, no auth attempted")
        skipped.append(
            SourceResult(
                name="harmbench",
                url_or_repo="walledai/HarmBench",
                config=None,
                split=None,
                revision=get_revision(api, "walledai/HarmBench"),
                fetched_at=datetime.now(timezone.utc).isoformat(),
                n_rows_actually_loaded=None,
                expected_rows=None,
                rows_match=None,
                column_names=[],
                license=get_license(api, "walledai/HarmBench"),
                sha256="",
                local_path="",
                bytes_on_disk=0,
                status="skipped_gated",
                notes=hb_note,
            )
        )
    else:
        specs.append(HFSpec("harmbench", "walledai/HarmBench", None, "train", None, fallback_note=hb_note))

    # --- item 13: wildguardmix, fallback to BeaverTails if gated ---
    wg_gated, wg_note = check_gated(api, "allenai/wildguardmix")
    if wg_gated:
        logger.warning(
            f"allenai/wildguardmix is GATED for anonymous access ({wg_note}) — "
            f"falling back to PKU-Alignment/BeaverTails (config=default, split=30k_train, capped 20k rows)"
        )
        skipped.append(
            SourceResult(
                name="wildguardmix",
                url_or_repo="allenai/wildguardmix",
                config=None,
                split=None,
                revision=get_revision(api, "allenai/wildguardmix"),
                fetched_at=datetime.now(timezone.utc).isoformat(),
                n_rows_actually_loaded=None,
                expected_rows=None,
                rows_match=None,
                column_names=[],
                license=get_license(api, "allenai/wildguardmix"),
                sha256="",
                local_path="",
                bytes_on_disk=0,
                status="skipped_gated_fallback_used",
                notes=wg_note,
            )
        )
        specs.append(
            HFSpec(
                "beavertails",
                "PKU-Alignment/BeaverTails",
                "default",
                "30k_train",
                None,
                row_cap=20000,
                fallback_note=(
                    "Fallback for allenai/wildguardmix (gated for anonymous access: "
                    f"{wg_note}). Used PKU-Alignment/BeaverTails default config, "
                    "30k_train split, capped at 20000 rows."
                ),
            )
        )
    else:
        specs.append(HFSpec("wildguardmix", "allenai/wildguardmix", None, "train", None, fallback_note=wg_note))

    return specs, skipped


def load_all_hf(specs: list[HFSpec]) -> list[SourceResult]:
    api = HfApi()
    results: list[SourceResult] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(load_hf_source, spec, api): spec for spec in specs}
        for fut in as_completed(futures):
            spec = futures[fut]
            try:
                res = fut.result()
                if res is not None:
                    results.append(res)
            except Exception:
                logger.exception(f"[HF] failed to load {spec.name} ({spec.repo_id})")
                raise
    return results


# --------------------------------------------------------------------------
# or-bench category-count verification
# --------------------------------------------------------------------------
def verify_or_bench_categories(hf_results: list[SourceResult]) -> None:
    for res in hf_results:
        cfg = res.config
        if cfg not in OR_BENCH_EXPECTED:
            continue
        full_path = WORKSPACE / res.local_path
        rows = json.loads(full_path.read_text(encoding="utf-8"))
        counts: dict[str, int] = {}
        for r in rows:
            cat = r.get("category")
            counts[cat] = counts.get(cat, 0) + 1
        logger.info(f"[or-bench:{cfg}] observed category vocabulary ({len(counts)} categories): {sorted(counts.keys())}")
        logger.info(f"[or-bench:{cfg}] observed counts: {dict(sorted(counts.items(), key=lambda kv: -kv[1]))}")
        expected = OR_BENCH_EXPECTED[cfg]
        mismatches = []
        for cat, exp_n in expected.items():
            got_n = counts.get(cat)
            if got_n != exp_n:
                mismatches.append((cat, exp_n, got_n))
        for cat in counts:
            if cat not in expected:
                mismatches.append((cat, None, counts[cat]))
        if mismatches:
            logger.warning(f"[or-bench:{cfg}] MISMATCHES vs previously-verified numbers: {mismatches}")
        else:
            logger.info(f"[or-bench:{cfg}] all 10 category counts MATCH previously-verified numbers")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
@logger.catch(reraise=True)
def main() -> None:
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    started = time.time()

    logger.info("=== Step 1/4: fetching direct-URL CSV sources (aiohttp, parallel) ===")
    url_results = asyncio.run(fetch_all_urls(DIRECT_URL_SOURCES))

    logger.info("=== Step 2/4: resolving HF specs (gating checks for HarmBench / wildguardmix) ===")
    api = HfApi()
    hf_specs, skipped_gated = build_hf_specs(api)

    logger.info(f"=== Step 3/4: loading {len(hf_specs)} HF datasets (thread pool, parallel) ===")
    hf_results = load_all_hf(hf_specs)

    logger.info("=== Step 4/4: post-processing ===")
    # alpaca / dolly: always also write the seeded 500-row sample, even if
    # the full file was kept.
    for res in hf_results:
        if res.name in ("databricks_dolly_15k", "alpaca") and res.status == "ok":
            full_path = WORKSPACE / res.local_path
            if full_path.name.startswith("full_") and not full_path.name.endswith("_sample500.json"):
                rows = json.loads(full_path.read_text(encoding="utf-8"))
                maybe_write_extra_sample(safe_name(res.name), rows)

    verify_or_bench_categories(hf_results)

    all_results = url_results + hf_results + skipped_gated
    total_bytes = sum(r.bytes_on_disk for r in all_results)

    if total_bytes > DOWNLOAD_BUDGET_BYTES:
        logger.warning(
            f"TOTAL BYTES ON DISK {total_bytes / 1e6:.1f}MB EXCEEDS the 200MB budget!"
        )
    else:
        logger.info(f"Total bytes on disk: {total_bytes / 1e6:.2f}MB (within 200MB budget)")

    manifest = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_bytes": total_bytes,
        "sources": [r.__dict__ for r in all_results],
    }
    write_json(MANIFEST_PATH, manifest)
    logger.info(f"Wrote manifest -> {MANIFEST_PATH} ({len(all_results)} source entries)")

    # Final table
    logger.info("=== FINAL TABLE: source | rows | bytes | license | sha256[:12] ===")
    header = f"{'source':<32} {'rows':>8} {'bytes':>12} {'license':<20} sha256[:12]"
    logger.info(header)
    logger.info("-" * len(header))
    for r in all_results:
        rows_disp = r.n_rows_actually_loaded if r.n_rows_actually_loaded is not None else "-"
        sha_disp = r.sha256[:12] if r.sha256 else "-"
        logger.info(f"{r.name:<32} {str(rows_disp):>8} {r.bytes_on_disk:>12} {r.license:<20} {sha_disp}  [{r.status}]")

    elapsed = time.time() - started
    logger.info(f"Done in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
