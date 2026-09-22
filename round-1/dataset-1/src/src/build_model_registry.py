#!/usr/bin/env python3
"""Weights-free HuggingFace model registry builder.

Fetches ONLY HTTP metadata (never model weight bytes) for a fixed panel of
repo ids via the HF REST API and raw-file endpoints:
  A) GET /api/models/<id>?blobs=true          (anonymous)
  B) GET /<id>/raw/main/config.json
  C) GET /<id>/raw/main/tokenizer_config.json  (chat_template key)
  D) GET /<id>/raw/main/chat_template.jinja    (standalone template, may 404)

Honours four verified traps:
  1. `usedStorage` is TOTAL repo storage across revisions/formats -- never a
     download-size proxy. download_bytes_min is computed by summing
     siblings[].size over *.safetensors, config.json, tokenizer*, *.jinja,
     generation_config.json.
  2. The `config` sub-object inside /api/models is often truncated to just
     model_type + architectures. num_hidden_layers / hidden_size come ONLY
     from /raw/main/config.json.
  3. A gated="manual" repo still returns full /api/models metadata
     anonymously, but /raw/main/config.json 401s.
  4. An anonymous 401 from /api/models/<id> means the id does NOT RESOLVE
     (this is not a gating signal -- gating is only readable from the
     `gated` field on a 200). A 404 is recorded as DELETED with the status.
"""

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
from loguru import logger

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE = SCRIPT_DIR.parent
LOG_DIR = WORKSPACE / "logs"
OUTPUT_PATH = WORKSPACE / "model_registry.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(LOG_DIR / "registry.log", rotation="30 MB", level="DEBUG")

HF_HOST = "https://huggingface.co"
CONCURRENCY = 8
MAX_RETRIES = 4
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)

# ---------------------------------------------------------------------------
# Repo manifest: (repo_id, family, role)
# ---------------------------------------------------------------------------

CORE_ARMS: list[tuple[str, str, str]] = [
    ("Qwen/Qwen3-4B-Base", "Qwen3-4B", "base"),
    ("Qwen/Qwen3-4B", "Qwen3-4B", "instruct"),
    ("Qwen/Qwen3-4B-SafeRL", "Qwen3-4B", "safety_ft"),
    ("mlabonne/Qwen3-4B-abliterated", "Qwen3-4B", "abliterated"),
    ("huihui-ai/Qwen3-4B-abliterated", "Qwen3-4B", "abliterated"),
    ("huihui-ai/Huihui-Qwen3-4B-abliterated-v2", "Qwen3-4B", "abliterated"),
    ("Qwen/Qwen3-4B-Instruct-2507", "Qwen3-4B", "instruct"),
    ("Qwen/Qwen3-4B-Thinking-2507", "Qwen3-4B", "instruct"),
]

NONSAFETY_LADDER: list[tuple[str, str, str]] = [
    ("CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6", "Qwen3-4B", "nonsafety_ft"),
    ("CohenQu/Qwen3-4B-Base_HintGen-STaR.04.00_1e-6_no_think", "Qwen3-4B", "nonsafety_ft"),
    ("shjondhale/AzureML-Qwen3-4B-Base-GRPO", "Qwen3-4B", "nonsafety_ft"),
    ("HikariLight/Qwen3_4B_Base__COMP_ACI_DAMT_SFT_Merged", "Qwen3-4B", "nonsafety_ft"),
]

FAMILY_PANEL: list[tuple[str, str, str]] = [
    ("Qwen/Qwen3-1.7B", "Qwen3-1.7B", "instruct"),
    ("Qwen/Qwen3-1.7B-Base", "Qwen3-1.7B", "base"),
    ("Qwen/Qwen3-0.6B", "Qwen3-0.6B", "instruct"),
    ("Qwen/Qwen3-0.6B-Base", "Qwen3-0.6B", "base"),
    ("mlabonne/Qwen3-1.7B-abliterated", "Qwen3-1.7B", "abliterated"),
    ("huihui-ai/Qwen3-1.7B-abliterated", "Qwen3-1.7B", "abliterated"),
    ("Qwen/Qwen2.5-1.5B-Instruct", "Qwen2.5-1.5B", "instruct"),
    ("Qwen/Qwen2.5-1.5B", "Qwen2.5-1.5B", "base"),
    ("Goekdeniz-Guelmez/Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v1", "Qwen2.5-1.5B", "abliterated"),
    ("Qwen/Qwen2.5-3B-Instruct", "Qwen2.5-3B", "instruct"),
    ("Pew404/Qwen2.5-3B-Instruct-abliterated", "Qwen2.5-3B", "abliterated"),
    ("HuggingFaceTB/SmolLM2-1.7B-Instruct", "SmolLM2-1.7B", "instruct"),
    ("HuggingFaceTB/SmolLM2-1.7B", "SmolLM2-1.7B", "base"),
    ("venkycs/SmolLM2-1.7B-Instruct-Abliterated", "SmolLM2-1.7B", "abliterated"),
    ("HuggingFaceTB/SmolLM3-3B", "SmolLM3-3B", "instruct"),
    ("HuggingFaceTB/SmolLM3-3B-Base", "SmolLM3-3B", "base"),
    ("TinyLlama/TinyLlama-1.1B-Chat-v1.0", "TinyLlama-1.1B", "instruct"),
    ("TinyLlama/TinyLlama_v1.1", "TinyLlama-1.1B", "base"),
    ("stabilityai/stablelm-2-1_6b-chat", "StableLM-2-1.6B", "instruct"),
    ("stabilityai/stablelm-2-1_6b", "StableLM-2-1.6B", "base"),
    ("microsoft/Phi-4-mini-instruct", "Phi-4-mini", "instruct"),
    ("lunahr/Phi-4-mini-instruct-abliterated", "Phi-4-mini", "abliterated"),
    ("ibm-granite/granite-3.2-2b-instruct", "granite-3.2-2b", "instruct"),
    ("Damien420/granite-3.2-2b-instruct-abliterated", "granite-3.2-2b", "abliterated"),
    ("allenai/OLMo-2-0425-1B-Instruct", "OLMo-2-0425-1B", "instruct"),
    ("allenai/OLMo-2-0425-1B", "OLMo-2-0425-1B", "base"),
    ("google/gemma-2-2b-it", "gemma-2-2b", "instruct"),
    ("meta-llama/Llama-3.2-1B-Instruct", "Llama-3.2-1B", "instruct"),
]

DOWNLOAD_SIZE_EXTS = (".safetensors", ".jinja")
DOWNLOAD_SIZE_EXACT = {"config.json", "generation_config.json"}


def matches_download_pattern(filename: str) -> bool:
    if filename.endswith(DOWNLOAD_SIZE_EXTS):
        return True
    if filename in DOWNLOAD_SIZE_EXACT:
        return True
    if filename.startswith("tokenizer"):
        return True
    return False


def compute_recipe_family(repo_id: str, role: str) -> str:
    if "-abliterated-SFT" in repo_id:
        return "abliteration+SFT"
    if "heretic" in repo_id.lower():
        return "heretic_tool"
    if repo_id.startswith("mlx-community/"):
        return "format_conversion"
    if re.search(r"(?i)abliterated|uncensored", repo_id):
        return "abliteration"
    if role == "base":
        return "base"
    if role == "instruct":
        return "instruct_rlhf"
    if role == "safety_ft":
        return "safety_rlhf"
    if role == "nonsafety_ft":
        return "sft"
    return "instruct_rlhf"


async def fetch(session: aiohttp.ClientSession, url: str) -> tuple[int, bytes]:
    """GET url with bounded retries on transient errors/5xx/429. Terminal
    statuses (200/401/403/404) are returned immediately without retry."""
    attempt = 0
    while True:
        attempt += 1
        try:
            async with session.get(url, timeout=REQUEST_TIMEOUT) as resp:
                status = resp.status
                if status in RETRYABLE_STATUSES and attempt <= MAX_RETRIES:
                    delay = min(2**attempt, 20)
                    logger.warning(
                        f"retryable status {status} for {url} (attempt {attempt}/{MAX_RETRIES}), sleeping {delay}s"
                    )
                    await asyncio.sleep(delay)
                    continue
                content = await resp.read()
                return status, content
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            if attempt <= MAX_RETRIES:
                delay = min(2**attempt, 20)
                logger.warning(
                    f"transient error {exc!r} for {url} (attempt {attempt}/{MAX_RETRIES}), sleeping {delay}s"
                )
                await asyncio.sleep(delay)
                continue
            logger.error(f"giving up on {url} after {attempt} attempts: {exc!r}")
            return -1, b""


async def fetch_json(session: aiohttp.ClientSession, url: str) -> tuple[int, dict[str, Any] | None]:
    status, content = await fetch(session, url)
    if status == 200:
        try:
            return status, json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"invalid JSON from {url}")
            return status, None
    return status, None


async def fetch_text(session: aiohttp.ClientSession, url: str) -> tuple[int, str | None]:
    status, content = await fetch(session, url)
    if status == 200:
        try:
            return status, content.decode("utf-8")
        except UnicodeDecodeError:
            return status, content.decode("utf-8", errors="replace")
    return status, None


async def build_record(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    repo_id: str,
    family: str,
    role: str,
) -> dict[str, Any]:
    async with sem:
        logger.info(f"fetching {repo_id}")
        notes: list[str] = []

        api_url = f"{HF_HOST}/api/models/{repo_id}?blobs=true"
        api_status, api_json = await fetch_json(session, api_url)
        resolves = api_status == 200

        if api_status == 404:
            notes.append("DELETED: repo id does not resolve (HTTP 404)")
        elif api_status == 401:
            notes.append(
                "anonymous 401 from /api/models: id does NOT RESOLVE (this is not a gating signal per se)"
            )
        elif api_status == -1:
            notes.append("network failure: /api/models request never completed")
        elif api_status != 200:
            notes.append(f"unexpected /api/models status {api_status}")

        gated: bool | str | None = None
        if resolves and api_json is not None:
            raw_gated = api_json.get("gated", False)
            if raw_gated is True:
                gated = "manual"
                notes.append("gated field was boolean true; normalized to 'manual'")
            elif raw_gated in (False, "auto", "manual"):
                gated = raw_gated
            else:
                gated = raw_gated
                notes.append(f"unexpected gated value {raw_gated!r}; passed through verbatim")

        usable = bool(resolves and gated is False)

        siblings = (api_json or {}).get("siblings", []) if resolves else []
        card_data = (api_json or {}).get("cardData", {}) or {} if resolves else {}
        safetensors_info = (api_json or {}).get("safetensors", {}) or {} if resolves else {}

        download_bytes_min = sum(
            s.get("size", 0) or 0 for s in siblings if matches_download_pattern(s.get("rfilename", ""))
        )
        download_gb_min = round(download_bytes_min / (1024**3), 6)

        safetensors_total_params = safetensors_info.get("total")
        safetensors_dtype_breakdown = safetensors_info.get("parameters", {}) or {}

        if safetensors_total_params is not None:
            dtype_sum = sum(safetensors_dtype_breakdown.values())
            if dtype_sum != safetensors_total_params:
                notes.append(
                    f"safetensors.total ({safetensors_total_params}) disagrees with sum of "
                    f"per-dtype parameter counts ({dtype_sum}); download_bytes_min was derived "
                    "from siblings[].size, never from this field"
                )

        if repo_id == "Qwen/Qwen3-4B-SafeRL":
            bf16_count = safetensors_dtype_breakdown.get("BF16")
            notes.append(
                f"Qwen3-4B-SafeRL check: safetensors.total={safetensors_total_params}, "
                f"per-dtype BF16 count={bf16_count}, "
                f"{'DISAGREE' if bf16_count != safetensors_total_params else 'agree'}; "
                "download_bytes_min always derived from siblings[].size, not from safetensors.total"
            )

        # -- raw config.json (trap #2: num_hidden_layers/hidden_size ONLY from here) --
        n_layers = hidden_size = model_type = architectures = None
        if resolves:
            cfg_status, cfg_json = await fetch_json(session, f"{HF_HOST}/{repo_id}/raw/main/config.json")
            if cfg_status == 200 and cfg_json is not None:
                n_layers = cfg_json.get("num_hidden_layers")
                hidden_size = cfg_json.get("hidden_size")
                model_type = cfg_json.get("model_type")
                architectures = cfg_json.get("architectures")
            else:
                api_cfg = (api_json or {}).get("config", {}) or {}
                model_type = api_cfg.get("model_type")
                architectures = api_cfg.get("architectures")
                notes.append(
                    f"raw/main/config.json returned {cfg_status}; num_hidden_layers/hidden_size "
                    "left null (never taken from the truncated /api/models config sub-object); "
                    "model_type/architectures fell back to that truncated sub-object"
                )
                if cfg_status == 401:
                    notes.append(
                        "gated repo trap confirmed: /api/models returned 200 anonymously but "
                        "raw/main/config.json 401'd"
                    )
        else:
            notes.append("skipped raw/main/config.json fetch: repo did not resolve")

        # -- tokenizer_config.json chat_template --
        chat_template_tok: str | None = None
        if resolves:
            tok_status, tok_text = await fetch_text(session, f"{HF_HOST}/{repo_id}/raw/main/tokenizer_config.json")
            if tok_status == 200 and tok_text is not None:
                try:
                    tok_json = json.loads(tok_text)
                    chat_template_tok = tok_json.get("chat_template")
                except json.JSONDecodeError:
                    notes.append("tokenizer_config.json fetched but was not valid JSON")
            else:
                notes.append(f"raw/main/tokenizer_config.json returned {tok_status}")
        else:
            notes.append("skipped tokenizer_config.json fetch: repo did not resolve")

        # -- standalone chat_template.jinja (may 404) --
        jinja_text: str | None = None
        if resolves:
            jinja_status, jinja_text = await fetch_text(session, f"{HF_HOST}/{repo_id}/raw/main/chat_template.jinja")
            if jinja_status != 200:
                jinja_text = None
        else:
            notes.append("skipped chat_template.jinja fetch: repo did not resolve")

        sources: list[str] = []
        chat_template_bytes = 0
        if chat_template_tok:
            sources.append("tokenizer_config")
            chat_template_bytes += len(chat_template_tok.encode("utf-8"))
        if jinja_text:
            sources.append("chat_template.jinja")
            chat_template_bytes += len(jinja_text.encode("utf-8"))
        if len(sources) == 2:
            chat_template_source = "both"
        elif len(sources) == 1:
            chat_template_source = sources[0]
        else:
            chat_template_source = "none"

        record = {
            "repo_id": repo_id,
            "http_status": api_status,
            "resolves": resolves,
            "gated": gated,
            "usable": usable,
            "download_bytes_min": download_bytes_min,
            "download_gb_min": download_gb_min,
            "safetensors_total_params": safetensors_total_params,
            "safetensors_dtype_breakdown": safetensors_dtype_breakdown,
            "n_layers": n_layers,
            "hidden_size": hidden_size,
            "model_type": model_type,
            "architectures": architectures,
            "chat_template_source": chat_template_source,
            "chat_template_bytes": chat_template_bytes,
            "declared_base_model": card_data.get("base_model"),
            "license": card_data.get("license"),
            "downloads": (api_json or {}).get("downloads") if resolves else None,
            "likes": (api_json or {}).get("likes") if resolves else None,
            "lastModified": (api_json or {}).get("lastModified") if resolves else None,
            "family": family,
            "role": role,
            "recipe_family": compute_recipe_family(repo_id, role),
            "sealed": False,
            "notes": notes,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.debug(f"{repo_id}: status={api_status} gated={gated} usable={usable}")
        return record


def pick_sealed_families(family_panel_records: list[dict[str, Any]]) -> list[str]:
    """Pick exactly two non-Qwen3 families with a complete, cleanly-resolved
    ungated lineage (base + instruct + abliterated all usable)."""
    by_family: dict[str, list[dict[str, Any]]] = {}
    for rec in family_panel_records:
        by_family.setdefault(rec["family"], []).append(rec)

    candidates: list[tuple[str, list[dict[str, Any]]]] = []
    for family, recs in by_family.items():
        if "qwen3" in family.lower():
            continue
        roles_present = {r["role"] for r in recs}
        if not {"base", "instruct", "abliterated"}.issubset(roles_present):
            continue
        all_usable = all(r["usable"] for r in recs)
        if not all_usable:
            continue
        candidates.append((family, recs))

    # Prefer families where the whole lineage resolved cleanly; break ties by
    # more members present, then alphabetically for determinism.
    candidates.sort(key=lambda fc: (-len(fc[1]), fc[0]))
    chosen = [family for family, _ in candidates[:2]]
    logger.info(f"sealed-family candidates (complete ungated non-Qwen3 lineage): {[c[0] for c in candidates]}")
    return chosen


def build_summary(all_records: list[dict[str, Any]], sealed_families: list[str]) -> dict[str, Any]:
    n_queried = len(all_records)
    n_resolved = sum(1 for r in all_records if r["resolves"])
    n_ungated = sum(1 for r in all_records if r["resolves"] and r["gated"] is False)

    families: dict[str, Any] = {}
    for rec in all_records:
        fam = families.setdefault(
            rec["family"],
            {"n_members": 0, "n_resolved": 0, "n_usable": 0, "roles": set(), "ungated_instruct_arm": False},
        )
        fam["n_members"] += 1
        if rec["resolves"]:
            fam["n_resolved"] += 1
        if rec["usable"]:
            fam["n_usable"] += 1
        fam["roles"].add(rec["role"])
        if rec["role"] == "instruct" and rec["usable"]:
            fam["ungated_instruct_arm"] = True

    for fam in families.values():
        fam["roles"] = sorted(fam["roles"])

    n_families_with_ungated_instruct_arm = sum(1 for fam in families.values() if fam["ungated_instruct_arm"])

    return {
        "n_queried": n_queried,
        "n_resolved": n_resolved,
        "n_ungated": n_ungated,
        "n_families_with_ungated_instruct_arm": n_families_with_ungated_instruct_arm,
        "families": families,
        "sealed_families": sealed_families,
    }


@logger.catch(reraise=True)
def main() -> None:
    asyncio.run(_main())


async def _main() -> None:
    all_manifest = CORE_ARMS + NONSAFETY_LADDER + FAMILY_PANEL
    logger.info(f"querying {len(all_manifest)} repos ({len(CORE_ARMS)} core, {len(NONSAFETY_LADDER)} ladder, {len(FAMILY_PANEL)} family panel)")

    sem = asyncio.Semaphore(CONCURRENCY)
    headers = {"User-Agent": "weights-free-model-registry/1.0 (metadata only, anonymous)"}
    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = {
            repo_id: asyncio.create_task(build_record(session, sem, repo_id, family, role))
            for repo_id, family, role in all_manifest
        }
        results = await asyncio.gather(*tasks.values())

    records_by_id = dict(zip(tasks.keys(), results))
    core_arms_records = [records_by_id[rid] for rid, _, _ in CORE_ARMS]
    nonsafety_ladder_records = [records_by_id[rid] for rid, _, _ in NONSAFETY_LADDER]
    family_panel_records = [records_by_id[rid] for rid, _, _ in FAMILY_PANEL]
    all_records = core_arms_records + nonsafety_ladder_records + family_panel_records

    sealed_families = pick_sealed_families(family_panel_records)
    for rec in all_records:
        if rec["family"] in sealed_families:
            rec["sealed"] = True

    summary = build_summary(all_records, sealed_families)

    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "method": "HuggingFace REST API only, zero weight bytes downloaded",
        "summary": summary,
        "core_arms": core_arms_records,
        "nonsafety_ladder": nonsafety_ladder_records,
        "family_panel": family_panel_records,
        "excluded": [],
    }

    OUTPUT_PATH.write_text(json.dumps(output, indent=2, default=str))
    logger.info(f"wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size} bytes)")

    n_families_ungated_instruct = summary["n_families_with_ungated_instruct_arm"]
    print("\n=== Weights-free HF model registry: summary ===")
    print(f"Repos queried:              {summary['n_queried']}")
    print(f"Repos resolved (HTTP 200):  {summary['n_resolved']}")
    print(f"Repos ungated:              {summary['n_ungated']}")
    print(f"Families w/ ungated usable instruct arm: {n_families_ungated_instruct}")
    if n_families_ungated_instruct < 6:
        print(
            f"WARNING: only {n_families_ungated_instruct} families have an ungated usable instruct arm "
            "(fewer than 6) -- NOT substituting a gated repo to compensate."
        )
    print(f"Sealed families (non-Qwen3, complete ungated lineage): {sealed_families}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
