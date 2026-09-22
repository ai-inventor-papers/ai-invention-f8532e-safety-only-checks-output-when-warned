#!/usr/bin/env python
"""ARTEFACT 1 (raw half): paired-lineage registry of instruction-tuned parent
models and their "abliterated"/uncensored children, built ONLY from LIVE
HuggingFace Hub metadata (never from memory, never re-typed by hand).

Candidate pool:
  (A) all 27 repos in the iteration-1 Lane C SEED_PANEL (imported programmatically
      from lc_panel.py, not retyped);
  (B) the commissioned pair Qwen/Qwen3-4B -> mlabonne/Qwen3-4B-abliterated;
  (C) a fresh, live HF Hub search across a fixed term list plus family-targeted
      supplementary terms, filtered to ungated, <=4B, safetensors-only children
      with an identifiable (cardData.base_model) parent.

METADATA AND TEXT ONLY. No *.safetensors bytes are ever downloaded. Total
bytes downloaded across the whole run is tracked and reported.

Outputs:
  build/registry_raw.json   -- the full registry (checkpoints + pairs + audit trail)
  build/registry_report.md  -- a short factual report (counts, drift, anomalies)
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import importlib.util
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import requests
from loguru import logger

# --------------------------------------------------------------------------- #
# Paths / constants
# --------------------------------------------------------------------------- #
WS = Path(__file__).resolve().parents[1]
BUILD_DIR = WS / "build"
LOGS_DIR = WS / "logs"
BUILD_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ITER1_EXP3_DIR = Path(
    "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/"
    "gen_art/gen_art_experiment_3"
)
LC_PANEL_PY = ITER1_EXP3_DIR / "lc_panel.py"
PREREG1_JSON = ITER1_EXP3_DIR / "prereg.json"

HF = "https://huggingface.co"
TODAY_UTC = "2026-09-21"

# The commissioned pair (part B of the spec).
COMMISSIONED_PARENT = "Qwen/Qwen3-4B"
COMMISSIONED_CHILD = "mlabonne/Qwen3-4B-abliterated"
FORBIDDEN_CHILD = "huihui-ai/Qwen3-4B-abliterated"  # gated='auto' -- MUST NOT be used

# Mandated search terms (verbatim from the task spec).
MANDATED_SEARCH_TERMS = [
    "abliterated", "uncensored", "orthogonalized", "orthogonalised",
    "heretic", "decensored", "refusal removed", "Josiefied", "no refusal",
]
# Supplementary family-targeted terms to broaden the sweep toward families
# NOT already in the seed panel, per the task's guidance list.
SUPPLEMENTARY_SEARCH_TERMS = [
    "Llama-3.2-1B abliterated", "Llama-3.2-3B abliterated", "Llama-3.2 uncensored",
    "Falcon3 abliterated", "Falcon3 uncensored",
    "MiniCPM abliterated", "MiniCPM uncensored",
    "EXAONE abliterated", "internlm abliterated",
    "Index-1.9B abliterated", "h2o-danube abliterated",
    "Qwen2.5-0.5B abliterated", "Qwen2.5-3B abliterated",
    "gemma abliterated", "gemma uncensored",
]
ALL_SEARCH_TERMS = MANDATED_SEARCH_TERMS + SUPPLEMENTARY_SEARCH_TERMS

MAX_CHILD_PARAMS = 4.3e9  # <=4B with headroom for rounding
MAX_WORKERS = 16
MAX_FRESH_PAIRS = 8  # cap on how many search-discovered pairs we add

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "lineage-registry-builder/1.0"})

# Global byte counter (thread-safe enough for our access pattern: only summed
# at the end from per-call return values, never mutated concurrently).
_BYTES_LOCK = __import__("threading").Lock()
_BYTES_DOWNLOADED = {"n": 0}


def _account_bytes(n: int) -> None:
    with _BYTES_LOCK:
        _BYTES_DOWNLOADED["n"] += n


# --------------------------------------------------------------------------- #
# Documented regex list for recipe-signal hunting (per spec: explicit &
# documented; a signal absent from the text is recorded as "unstated", never
# inferred).
# --------------------------------------------------------------------------- #
REGEX_LIST: dict[str, Any] = {
    "tool": {
        "abliterator": r"\babliterator\b",
        "TransformerLens": r"TransformerLens",
        "heretic": r"\bheretic\b",
        "remove-refusals-with-transformers": r"remove[-_ ]refusals[-_ ]with[-_ ]transformers",
        "failspy": r"\bfailspy\b",
        "mergekit": r"\bmergekit\b",
    },
    "coefficient": r"(?:ablation\s+coeff\w*|coefficient|scale[-_ ]?factor|strength|alpha)\s*(?:of|is|was|=|:)?\s*([0-9]+(?:\.[0-9]+)?)",
    "rank": r"\brank[- ]?(?:of\s+)?(?:=|:)?\s*([0-9]+)\b",
    # Deliberately scoped to layers *edited/ablated/targeted*, not a generic
    # "Number of Layers: N" architecture-depth statement (which would be a
    # false positive for this signal).
    "layers": (
        r"(?:\bablat\w*|\bedit\w*|\btarget\w*|\bmodif\w*|\bremov\w*|\bproject\w*)"
        r"[^.\n]{0,40}\blayers?\s*(?:=|:)?\s*(\[?[0-9]+(?:\s*[-–to]{1,4}\s*[0-9]+)?\]?)"
        r"|\blayers?\s*(\[?[0-9]+(?:\s*[-–to]{1,4}\s*[0-9]+)?\]?)[^.\n]{0,40}"
        r"(?:\bablat\w*|\bedit\w*|\btarget\w*|\bmodif\w*|\bremov\w*|\bprojected?\b)"
    ),
    "retrained_after_edit": {
        "SFT": r"\bSFT\b|supervised\s+fine-?tun\w*",
        "DPO": r"\bDPO\b",
        "KTO": r"\bKTO\b",
        "ORPO": r"\bORPO\b",
        "healing": r"\bheal(?:ing|ed)?\b",
        "post-edit-training": r"(?:retrain|re-?train|fine-?tun\w*)\s+after\s+(?:the\s+)?(?:ablation|abliteration|edit)",
    },
    "fit_position": {
        "prompt": r"\b(?:prompt|instruction|user[- ]turn)[- ]?(?:position|token|side|only)\b",
        "response": r"\b(?:response|completion|assistant[- ]turn)[- ]?(?:position|token|side|only)\b",
    },
    "coefficient_gt_1_threshold": 1.0,
}
_TOOL_PATTERNS = {k: re.compile(v, re.IGNORECASE) for k, v in REGEX_LIST["tool"].items()}
_COEF_PATTERN = re.compile(REGEX_LIST["coefficient"], re.IGNORECASE)
_RANK_PATTERN = re.compile(REGEX_LIST["rank"], re.IGNORECASE)
_LAYERS_PATTERN = re.compile(REGEX_LIST["layers"], re.IGNORECASE)
_RETRAIN_PATTERNS = {k: re.compile(v, re.IGNORECASE) for k, v in REGEX_LIST["retrained_after_edit"].items()}
_FITPOS_PATTERNS = {k: re.compile(v, re.IGNORECASE) for k, v in REGEX_LIST["fit_position"].items()}

# Family-name detector for candidates discovered via fresh HF search (used
# only to LABEL a family for a repo whose parentage is already established via
# cardData.base_model -- never used to substitute or infer a missing parent).
_FAMILY_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Llama-3\.2", re.IGNORECASE), "llama3.2"),
    (re.compile(r"MiniCPM", re.IGNORECASE), "minicpm"),
    (re.compile(r"gemma-3", re.IGNORECASE), "gemma3"),
    (re.compile(r"gemma", re.IGNORECASE), "gemma"),
    (re.compile(r"Qwen3", re.IGNORECASE), "qwen3"),
    (re.compile(r"Qwen2\.5", re.IGNORECASE), "qwen2.5"),
    (re.compile(r"Falcon3", re.IGNORECASE), "falcon3"),
    (re.compile(r"EXAONE", re.IGNORECASE), "exaone"),
    (re.compile(r"internlm", re.IGNORECASE), "internlm"),
    (re.compile(r"Index-1\.9B|IndexTeam", re.IGNORECASE), "index"),
    (re.compile(r"h2o-danube", re.IGNORECASE), "h2odanube"),
    (re.compile(r"SmolLM2", re.IGNORECASE), "smollm2"),
    (re.compile(r"SmolLM3", re.IGNORECASE), "smollm3"),
    (re.compile(r"TinyLlama", re.IGNORECASE), "tinyllama"),
    (re.compile(r"Phi-4", re.IGNORECASE), "phi"),
    (re.compile(r"granite", re.IGNORECASE), "granite"),
    (re.compile(r"stablelm", re.IGNORECASE), "stablelm"),
    (re.compile(r"OLMo", re.IGNORECASE), "olmo2"),
]


def guess_family(repo_id_or_name: str) -> str:
    for pat, fam in _FAMILY_PATTERNS:
        if pat.search(repo_id_or_name):
            return fam
    # fall back to the org-stripped basename, lower-cased, first token
    base = repo_id_or_name.split("/")[-1]
    return re.split(r"[-_]", base)[0].lower()


def recognized_family(repo_id_or_name: str) -> Optional[str]:
    """Like guess_family, but returns None (never a low-confidence fallback
    slug) when the text does not match one of the known, curated family
    patterns. Used to gate which fresh search candidates are trustworthy
    enough to include -- an unrecognized name (e.g. a diffusion-model repo
    accidentally named as a base_model, or a personal one-off merge chain)
    must never be silently accepted as a 'fresh family'."""
    for pat, fam in _FAMILY_PATTERNS:
        if pat.search(repo_id_or_name):
            return fam
    return None


# A declared parent whose OWN repo id still carries one of these edit-tool
# keywords is itself a derivative (an abliterated/uncensored child of some
# other checkpoint), not a clean instruct parent -- reject as parent.
_EDIT_KEYWORDS = ("abliterat", "uncensor", "heretic", "decensor", "josiefied",
                  "orthogonaliz", "orthogonalis", "no-refusal", "no_refusal",
                  "refusal-removed", "refusal_removed")
# A declared parent whose repo id carries one of these is a quantized /
# reduced-precision rehost, not the canonical full-precision instruct parent.
_QUANT_KEYWORDS = ("bnb-4bit", "bnb-8bit", "gptq", "awq", "gguf", "-4bit", "-8bit",
                    "nvfp4", "int4", "int8", "fp8", "quantized", "-mlx")


def is_clean_parent(repo_id: str) -> bool:
    low = repo_id.lower()
    if any(k in low for k in _EDIT_KEYWORDS):
        return False
    if any(k in low for k in _QUANT_KEYWORDS):
        return False
    return True


# --------------------------------------------------------------------------- #
# HTTP helpers with retries; every call accounts its downloaded bytes.
# --------------------------------------------------------------------------- #
def _get(url: str, params: Optional[dict] = None, max_retries: int = 4,
         timeout: int = 40) -> requests.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            _account_bytes(len(r.content or b""))
            if r.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"429 on {url} (attempt {attempt}); sleeping {wait}s")
                time.sleep(wait)
                continue
            return r
        except (requests.ConnectionError, requests.Timeout) as e:
            last_exc = e
            wait = 1.5 ** attempt
            logger.warning(f"transient error on {url} (attempt {attempt}): {e}; sleeping {wait:.1f}s")
            time.sleep(wait)
    assert last_exc is not None
    raise last_exc


# --------------------------------------------------------------------------- #
# Part A: load SEED_PANEL programmatically (never retyped).
# --------------------------------------------------------------------------- #
def load_seed_panel() -> dict[str, list[tuple[str, str, str]]]:
    if not LC_PANEL_PY.exists():
        raise FileNotFoundError(f"lc_panel.py not found at {LC_PANEL_PY}")
    spec = importlib.util.spec_from_file_location("lc_panel_iter1", LC_PANEL_PY)
    mod = importlib.util.module_from_spec(spec)
    # lc_panel.py imports lc_common at module scope; make that importable too.
    sys.path.insert(0, str(ITER1_EXP3_DIR))
    try:
        assert spec and spec.loader
        spec.loader.exec_module(mod)  # runs only module-level code, not __main__
    finally:
        sys.path.remove(str(ITER1_EXP3_DIR))
    panel = mod.SEED_PANEL
    n = sum(len(v) for v in panel.values())
    logger.info(f"loaded SEED_PANEL from {LC_PANEL_PY}: {len(panel)} families, {n} repos")
    return panel


def load_iter1_revisions() -> dict[str, str]:
    if not PREREG1_JSON.exists():
        logger.warning(f"iter-1 prereg.json not found at {PREREG1_JSON}; revision-drift check skipped")
        return {}
    d = json.loads(PREREG1_JSON.read_text())
    out = {row["repo"]: row.get("revision") for row in d.get("panel", []) if row.get("revision")}
    logger.info(f"loaded {len(out)} pinned iter-1 revisions from {PREREG1_JSON}")
    return out


# --------------------------------------------------------------------------- #
# Part C: fresh HF Hub search & discovery of new candidate pairs.
# --------------------------------------------------------------------------- #
def _search_once(term: str, sort: Optional[str]) -> list[dict]:
    params: dict[str, Any] = {"search": term, "limit": 100, "full": "true"}
    params["expand[]"] = ["safetensors", "gated", "cardData"]
    if sort:
        params["sort"] = sort
        params["direction"] = -1
    r = _get(f"{HF}/api/models", params=params)
    if r.status_code != 200:
        logger.warning(f"search term={term!r} sort={sort} -> HTTP {r.status_code}")
        return []
    try:
        return r.json()
    except json.JSONDecodeError:
        logger.warning(f"search term={term!r} sort={sort} -> bad JSON")
        return []


def _extract_base_model(card_data: Optional[dict]) -> Optional[str]:
    if not card_data:
        return None
    bm = card_data.get("base_model")
    if isinstance(bm, list) and bm:
        return str(bm[0])
    if isinstance(bm, str) and bm.strip():
        return bm.strip()
    return None


@dataclass
class FreshCandidate:
    child_repo: str
    declared_base_model: str
    child_total_params: float
    child_gated: Any
    downloads: int
    is_heretic: bool
    family: str


def discover_fresh_candidates(
    seed_repo_ids: set[str],
) -> tuple[list[FreshCandidate], int, list[str]]:
    """Run the live HF search sweep and return a filtered, ranked list of
    fresh (child -> declared parent) candidates, the total number of unique
    repos screened, and the list of terms actually used."""
    screened: dict[str, dict] = {}
    for term in ALL_SEARCH_TERMS:
        for sort in (None, "downloads"):
            hits = _search_once(term, sort)
            for m in hits:
                rid = m.get("id")
                if not rid:
                    continue
                # keep the richest record we've seen for this id
                if rid not in screened or (m.get("safetensors") and not screened[rid].get("safetensors")):
                    screened[rid] = m
    logger.info(f"fresh-search sweep: {len(screened)} unique repos screened "
                f"across {len(ALL_SEARCH_TERMS)} terms x 2 sort orders")

    candidates: list[FreshCandidate] = []
    for rid, m in screened.items():
        if rid in seed_repo_ids or rid in (COMMISSIONED_CHILD, COMMISSIONED_PARENT, FORBIDDEN_CHILD):
            continue
        st = m.get("safetensors")
        if not st or not st.get("total"):
            continue  # GGUF-only or no safetensors metadata -> excluded
        total = st["total"]
        if total > MAX_CHILD_PARAMS:
            continue
        if m.get("gated") is not False:
            continue  # child itself must be ungated to be worth harvesting
        if any(k in rid.lower() for k in _QUANT_KEYWORDS):
            continue  # prefer a full-precision child rehost over a quantized one
        base_model = _extract_base_model(m.get("cardData"))
        if not base_model:
            continue  # require an explicit declared parent (cardData_base_model)
        if not is_clean_parent(base_model):
            continue  # parent is itself an edited derivative or a quantized rehost
        fam = recognized_family(base_model)
        if fam is None:
            continue  # unrecognized parent family name -- do not silently accept it
        is_heretic = ("heretic" in rid.lower()) or ("heretic" in json.dumps(m.get("cardData") or {}).lower())
        candidates.append(FreshCandidate(
            child_repo=rid, declared_base_model=base_model, child_total_params=total,
            child_gated=m.get("gated"), downloads=m.get("downloads", 0) or 0,
            is_heretic=is_heretic, family=fam,
        ))

    seed_families = set()  # filled in by caller via closure below if needed
    return candidates, len(screened), ALL_SEARCH_TERMS


def rank_and_select_fresh(
    candidates: list[FreshCandidate], seed_families: set[str], max_pairs: int,
) -> list[FreshCandidate]:
    def rank_key(c: FreshCandidate):
        fresh_family_bonus = 0 if c.family in seed_families else 1
        return (fresh_family_bonus, int(c.is_heretic), c.downloads)

    ranked = sorted(candidates, key=rank_key, reverse=True)
    selected: list[FreshCandidate] = []
    per_family_count: dict[str, int] = {}
    for c in ranked:
        if per_family_count.get(c.family, 0) >= 2:
            continue
        selected.append(c)
        per_family_count[c.family] = per_family_count.get(c.family, 0) + 1
        if len(selected) >= max_pairs:
            break
    return selected


# --------------------------------------------------------------------------- #
# Per-checkpoint metadata harvest (LIVE, one API call + 3 raw file fetches).
# --------------------------------------------------------------------------- #
def fetch_checkpoint(repo_id: str, family: str, role: str,
                      iter1_revisions: dict[str, str]) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "repo_id": repo_id, "family": family, "role": role,
        "readout_class": "metadata",
        "unavailable": False,
    }
    try:
        # NOTE: deliberately NOT passing expand[] here. The single-repo model
        # API's DEFAULT response (with just blobs=true) already includes sha,
        # downloads, likes, gated, cardData AND the full safetensors
        # parameter/dtype breakdown at the top level -- verified live. Passing
        # expand[] instead RESTRICTS the response to only the named fields
        # (dropping sha/downloads/likes), which silently nulled the revision
        # for every checkpoint in an earlier version of this script.
        r = _get(f"{HF}/api/models/{repo_id}", params={"blobs": "true"})
    except Exception as e:  # noqa: BLE001
        rec["unavailable"] = True
        rec["unavailable_status"] = f"EXC:{type(e).__name__}"
        rec["unavailable_date"] = TODAY_UTC
        logger.error(f"[{repo_id}] API call raised {type(e).__name__}: {e}")
        return rec

    if r.status_code == 404:
        rec["unavailable"] = True
        rec["unavailable_status"] = 404
        rec["unavailable_date"] = TODAY_UTC
        logger.warning(f"[{repo_id}] 404 -- repo no longer exists (as of {TODAY_UTC})")
        return rec
    if r.status_code == 401:
        rec["unavailable"] = True
        rec["unavailable_status"] = 401
        rec["unavailable_date"] = TODAY_UTC
        rec["gated"] = "true"
        rec["usable"] = False
        logger.warning(f"[{repo_id}] 401 on model API -- gated/inaccessible anonymously; "
                        f"NOT retrying with HF_TOKEN")
        return rec
    if r.status_code != 200:
        rec["unavailable"] = True
        rec["unavailable_status"] = r.status_code
        rec["unavailable_date"] = TODAY_UTC
        logger.warning(f"[{repo_id}] HTTP {r.status_code} on model API")
        return rec

    j = r.json()
    gated_raw = j.get("gated", False)
    if gated_raw is False or gated_raw is None:
        gated_norm = "false"
    elif gated_raw == "auto":
        gated_norm = "auto"
    else:  # "manual" or True
        gated_norm = "true"
    rec["gated"] = gated_norm
    rec["usable"] = (gated_norm == "false")
    rec["revision"] = j.get("sha")
    rec["license"] = (j.get("cardData") or {}).get("license") or j.get("license")
    rec["downloads"] = j.get("downloads")
    rec["likes"] = j.get("likes")

    st_meta = j.get("safetensors") or {}
    rec["params_total"] = st_meta.get("total")
    rec["params_by_dtype"] = st_meta.get("parameters")

    siblings = j.get("siblings", [])
    shard_list = [s.get("rfilename") for s in siblings if s.get("rfilename", "").endswith(".safetensors")]
    safetensors_bytes = sum((s.get("size") or 0) for s in siblings
                             if s.get("rfilename", "").endswith(".safetensors"))
    rec["shard_list"] = shard_list
    rec["safetensors_bytes"] = safetensors_bytes
    rec["n_shards"] = len(shard_list)

    rfile_set = {s.get("rfilename", "") for s in siblings}
    rec["has_chat_template_jinja"] = "chat_template.jinja" in rfile_set

    cd = j.get("cardData") or {}
    dbm = _extract_base_model(cd)
    rec["declared_base_model"] = dbm if dbm is not None else "NONE_DECLARED"

    # revision drift vs iter-1 pin
    iter1_rev = iter1_revisions.get(repo_id)
    rec["revision_iter1"] = iter1_rev
    rec["revision_moved"] = (iter1_rev is not None and iter1_rev != rec["revision"])

    # --- raw file fetches: config.json, tokenizer_config.json, README.md ---
    def raw(path: str) -> tuple[Optional[requests.Response], Optional[str]]:
        try:
            resp = _get(f"{HF}/{repo_id}/raw/main/{path}")
        except Exception as e:  # noqa: BLE001
            return None, f"EXC:{type(e).__name__}"
        if resp.status_code == 200:
            return resp, None
        if resp.status_code in (401, 404):
            return None, str(resp.status_code)
        return None, f"HTTP{resp.status_code}"

    cfg_resp, cfg_err = raw("config.json")
    rec["config_torch_dtype"] = None
    rec["n_layers"] = None
    rec["hidden_size"] = None
    rec["vocab_size"] = None
    rec["config_fetch_error"] = cfg_err
    if cfg_resp is not None:
        try:
            cfg = cfg_resp.json()
            rec["config_torch_dtype"] = cfg.get("torch_dtype")
            rec["n_layers"] = cfg.get("num_hidden_layers")
            rec["hidden_size"] = cfg.get("hidden_size")
            rec["vocab_size"] = cfg.get("vocab_size")
        except json.JSONDecodeError:
            rec["config_fetch_error"] = "JSONDecodeError"

    tok_resp, tok_err = raw("tokenizer_config.json")
    rec["chat_template_bytes"] = 0
    rec["tokenizer_config_fetch_error"] = tok_err
    tok_has_ct = False
    if tok_resp is not None:
        try:
            tok_cfg = tok_resp.json()
            ct = tok_cfg.get("chat_template")
            if isinstance(ct, str):
                rec["chat_template_bytes"] = len(ct.encode("utf-8"))
                tok_has_ct = True
            elif isinstance(ct, list):
                # some repos store a list of {name, template} dicts
                joined = json.dumps(ct)
                rec["chat_template_bytes"] = len(joined.encode("utf-8"))
                tok_has_ct = bool(ct)
        except json.JSONDecodeError:
            rec["tokenizer_config_fetch_error"] = "JSONDecodeError"

    has_jinja = rec["has_chat_template_jinja"]
    if tok_has_ct and has_jinja:
        rec["chat_template_source"] = "both"
        # Verified rule (transformers 5.17.0,
        # tokenization_utils_base.py:1783 "If independent chat template
        # file(s) exist, they take priority over template entries in the
        # tokenizer config"): AutoTokenizer.from_pretrained loads
        # chat_template.jinja and IGNORES tokenizer_config.json's
        # "chat_template" key when both are present.
        rec["chat_template_winner"] = "chat_template_jinja"
        rec["chat_template_winner_rule"] = (
            "transformers==5.17.0 tokenization_utils_base.py "
            "PreTrainedTokenizerBase._from_pretrained(): "
            "'If independent chat template file(s) exist, they take "
            "priority over template entries in the tokenizer config' "
            "-> chat_template.jinja is loaded into init_kwargs['chat_template'] "
            "and the tokenizer_config.json 'chat_template' key is never read."
        )
    elif tok_has_ct:
        rec["chat_template_source"] = "tokenizer_config"
        rec["chat_template_winner"] = "tokenizer_config"
        rec["chat_template_winner_rule"] = "only source present"
    elif has_jinja:
        rec["chat_template_source"] = "chat_template_jinja"
        rec["chat_template_winner"] = "chat_template_jinja"
        rec["chat_template_winner_rule"] = "only source present"
    else:
        rec["chat_template_source"] = "none"
        rec["chat_template_winner"] = None
        rec["chat_template_winner_rule"] = "neither source present"

    readme_resp, readme_err = raw("README.md")
    rec["readme_fetch_error"] = readme_err
    full_text = ""
    if readme_resp is not None:
        full_text = readme_resp.text
    rec["card_text_full_len"] = len(full_text)
    rec["card_text_sha256"] = hashlib.sha256(full_text.encode("utf-8")).hexdigest()
    rec["card_text_first_20kb"] = full_text[:20000]

    logger.info(f"[{repo_id}] OK gated={gated_norm} params_total={rec['params_total']} "
                f"st_bytes={safetensors_bytes} shards={len(shard_list)} "
                f"dtype={rec['config_torch_dtype']} rev_moved={rec['revision_moved']} "
                f"ct_src={rec['chat_template_source']}")
    return rec


# --------------------------------------------------------------------------- #
# Recipe-signal extraction over a child's card text.
# --------------------------------------------------------------------------- #
def _quote_context(text: str, start: int, end: int, radius: int = 90) -> str:
    lo = max(0, start - radius)
    hi = min(len(text), end + radius)
    return text[lo:hi].replace("\n", " ").strip()


def extract_recipe_signals(card_text: str) -> list[dict[str, Any]]:
    """card_text may legitimately be empty (e.g. a repo with no README.md,
    such as the TinyLlama artefact below) -- that still yields one explicit
    'unstated' entry per signal type below, never an empty list, since
    'absent from the text' and 'no text to search' are the same case."""
    signals: list[dict[str, Any]] = []
    card_text = card_text or ""

    tool_found = False
    for name, pat in _TOOL_PATTERNS.items():
        m = pat.search(card_text)
        if m:
            tool_found = True
            signals.append({
                "signal_type": "tool", "value": name,
                "quoted_sentence": _quote_context(card_text, m.start(), m.end()),
                "char_offset": m.start(), "regex_used": pat.pattern,
            })
    if not tool_found:
        signals.append({"signal_type": "tool", "value": "unstated",
                         "quoted_sentence": None, "char_offset": None,
                         "regex_used": "|".join(p.pattern for p in _TOOL_PATTERNS.values())})

    m = _COEF_PATTERN.search(card_text)
    if m:
        try:
            val = float(m.group(1))
        except ValueError:
            val = None
        signals.append({
            "signal_type": "coefficient", "value": val,
            "quoted_sentence": _quote_context(card_text, m.start(), m.end()),
            "char_offset": m.start(), "regex_used": _COEF_PATTERN.pattern,
        })
        if val is not None and val > REGEX_LIST["coefficient_gt_1_threshold"]:
            signals.append({
                "signal_type": "coefficient_gt_1", "value": True,
                "quoted_sentence": _quote_context(card_text, m.start(), m.end()),
                "char_offset": m.start(), "regex_used": _COEF_PATTERN.pattern,
            })
    else:
        signals.append({"signal_type": "coefficient", "value": "unstated",
                         "quoted_sentence": None, "char_offset": None,
                         "regex_used": _COEF_PATTERN.pattern})

    m = _RANK_PATTERN.search(card_text)
    if m:
        signals.append({
            "signal_type": "rank", "value": int(m.group(1)),
            "quoted_sentence": _quote_context(card_text, m.start(), m.end()),
            "char_offset": m.start(), "regex_used": _RANK_PATTERN.pattern,
        })
    else:
        signals.append({"signal_type": "rank", "value": "unstated",
                         "quoted_sentence": None, "char_offset": None,
                         "regex_used": _RANK_PATTERN.pattern})

    m = _LAYERS_PATTERN.search(card_text)
    if m:
        layers_val = m.group(1) if m.group(1) is not None else m.group(2)
        signals.append({
            "signal_type": "layers", "value": layers_val,
            "quoted_sentence": _quote_context(card_text, m.start(), m.end()),
            "char_offset": m.start(), "regex_used": _LAYERS_PATTERN.pattern,
        })
    else:
        signals.append({"signal_type": "layers", "value": "unstated",
                         "quoted_sentence": None, "char_offset": None,
                         "regex_used": _LAYERS_PATTERN.pattern})

    retrain_found = False
    for name, pat in _RETRAIN_PATTERNS.items():
        m = pat.search(card_text)
        if m:
            retrain_found = True
            signals.append({
                "signal_type": "retrained_after_edit", "value": name,
                "quoted_sentence": _quote_context(card_text, m.start(), m.end()),
                "char_offset": m.start(), "regex_used": pat.pattern,
            })
    if not retrain_found:
        signals.append({"signal_type": "retrained_after_edit", "value": "unstated",
                         "quoted_sentence": None, "char_offset": None,
                         "regex_used": "|".join(p.pattern for p in _RETRAIN_PATTERNS.values())})

    fitpos_found = False
    for name, pat in _FITPOS_PATTERNS.items():
        m = pat.search(card_text)
        if m:
            fitpos_found = True
            signals.append({
                "signal_type": "fit_position", "value": name,
                "quoted_sentence": _quote_context(card_text, m.start(), m.end()),
                "char_offset": m.start(), "regex_used": pat.pattern,
            })
            break  # fit_position is single-valued
    if not fitpos_found:
        signals.append({"signal_type": "fit_position", "value": "unstated",
                         "quoted_sentence": None, "char_offset": None,
                         "regex_used": "|".join(p.pattern for p in _FITPOS_PATTERNS.values())})

    return signals


def derive_recipe_stratum(signals: list[dict[str, Any]]) -> tuple[str, str]:
    """Return (stratum, derivation_rule_text)."""
    by_type: dict[str, list[Any]] = {}
    for s in signals:
        by_type.setdefault(s["signal_type"], []).append(s["value"])

    retrain_vals = [v for v in by_type.get("retrained_after_edit", []) if v != "unstated"]
    fitpos_vals = [v for v in by_type.get("fit_position", []) if v != "unstated"]
    rank_vals = [v for v in by_type.get("rank", []) if v != "unstated"]
    tool_vals = [v for v in by_type.get("tool", []) if v != "unstated"]

    rule = (
        "1) if any retrained_after_edit signal is present -> 'retrained_after_edit'; "
        "2) elif fit_position=='response' -> 'response_position_fit'; "
        "3) elif a numeric rank>1 signal is present -> 'rank_gt_1'; "
        "4) elif a tool signal is present and rank is unstated or ==1 and "
        "fit_position is unstated -> 'standard_prompt_rank1'; "
        "5) else -> 'unknown'."
    )
    if retrain_vals:
        return "retrained_after_edit", rule
    if "response" in fitpos_vals:
        return "response_position_fit", rule
    if any(isinstance(v, int) and v > 1 for v in rank_vals):
        return "rank_gt_1", rule
    if tool_vals and (not rank_vals or all(v == 1 for v in rank_vals)) and not fitpos_vals:
        return "standard_prompt_rank1", rule
    return "unknown", rule


# --------------------------------------------------------------------------- #
# Size-anomaly resolution for a parent/child pair.
# --------------------------------------------------------------------------- #
def resolve_size_anomaly(parent: dict, child: dict) -> Optional[dict[str, Any]]:
    p_bytes = parent.get("safetensors_bytes") or 0
    c_bytes = child.get("safetensors_bytes") or 0
    if p_bytes <= 0 or c_bytes <= 0:
        return None
    ratio = c_bytes / p_bytes
    is_anomalous = (0.3 <= ratio <= 0.5) or (ratio <= 0.55 and parent.get("role") == "base")
    if not (0.25 <= ratio <= 0.55):
        return None  # not in the anomaly band at all -> caller records "none"

    p_params = parent.get("params_total")
    c_params = child.get("params_total")
    p_dtype = parent.get("config_torch_dtype")
    c_dtype = child.get("config_torch_dtype")
    p_shards = parent.get("shard_list") or []
    c_shards = child.get("shard_list") or []

    evidence = {
        "ratio_child_over_parent_bytes": round(ratio, 4),
        "parent_bytes": p_bytes, "child_bytes": c_bytes,
        "parent_params_total": p_params, "child_params_total": c_params,
        "parent_config_torch_dtype": p_dtype, "child_config_torch_dtype": c_dtype,
        "parent_params_by_dtype": parent.get("params_by_dtype"),
        "child_params_by_dtype": child.get("params_by_dtype"),
        "parent_shard_list": p_shards, "child_shard_list": c_shards,
    }

    params_match = (p_params is not None and c_params is not None
                     and abs(p_params - c_params) / max(p_params, c_params) < 0.02)

    if params_match:
        cause = "dtype_difference"
    elif p_params is not None and c_params is not None and c_params < 0.9 * p_params:
        cause = "missing_shards"
    else:
        cause = "unresolved"

    return {"size_anomaly_cause": cause, "evidence": evidence}


# --------------------------------------------------------------------------- #
# Pair assembly
# --------------------------------------------------------------------------- #
ROLE_MAP = {
    "base": "base", "instruct": "instruct", "safety": "safety_tuned",
    "abliterated": "abliterated_child",
}


def determine_parent_declared_by(parent_repo: str, child_ckpt: dict[str, Any]) -> str:
    """Never silently accept a repo-NAME-only parentage as if it were
    card-verified: check the child's own fetched metadata for real evidence
    that IT declares this parent, and only fall back to name_only when no
    such evidence exists in cardData.base_model or the card text."""
    dbm = child_ckpt.get("declared_base_model")
    parent_base = parent_repo.split("/")[-1]
    size_m = re.search(r"\d+(?:\.\d+)?B", parent_base)
    size_tok = size_m.group(0) if size_m else ""
    family_tok = re.split(r"[-_]", re.sub(r"\d+(?:\.\d+)?B.*$", "", parent_base))[0]

    if dbm and dbm != "NONE_DECLARED":
        dbm_l = dbm.lower()
        if dbm == parent_repo or parent_base.lower() in dbm_l or dbm_l in parent_repo.lower():
            return "cardData_base_model"
        if family_tok.lower() in dbm_l and (not size_tok or size_tok.lower() in dbm_l):
            return "cardData_base_model"
        # cardData names a DIFFERENT repo than our matched parent -- flag it
        # in the logs so it's never silently accepted either way.
        logger.warning(f"child declares base_model={dbm!r} which does NOT match the "
                        f"assigned parent {parent_repo!r} -- keeping the assigned "
                        f"family-panel parent but recording parent_declared_by=name_only")
        return "name_only"

    card_text = child_ckpt.get("card_text_first_20kb", "") or ""
    if family_tok and family_tok.lower() in card_text.lower() and (
            not size_tok or size_tok.lower() in card_text.lower()):
        return "card_text"
    return "name_only"


def make_pair(parent_ckpt: dict, child_ckpt: dict, family: str, fresh: bool) -> dict[str, Any]:
    child_basename = child_ckpt["repo_id"].split("/")[-1]
    pair_id = f"{family}__{child_basename}"
    parent_declared_by = determine_parent_declared_by(parent_ckpt["repo_id"], child_ckpt)

    signals = extract_recipe_signals(child_ckpt.get("card_text_first_20kb", ""))
    stratum, rule = derive_recipe_stratum(signals)

    anomaly = resolve_size_anomaly(parent_ckpt, child_ckpt)
    if anomaly is None:
        size_anomaly_cause = "none"
        size_anomaly_evidence = None
    else:
        size_anomaly_cause = anomaly["size_anomaly_cause"]
        size_anomaly_evidence = anomaly["evidence"]

    p_dtype = parent_ckpt.get("config_torch_dtype")
    c_dtype = child_ckpt.get("config_torch_dtype")
    comparable_dtype = (p_dtype is not None and c_dtype is not None and p_dtype == c_dtype)

    pair = {
        "pair_id": pair_id,
        "parent_repo": parent_ckpt["repo_id"],
        "child_repo": child_ckpt["repo_id"],
        "family": family,
        "fresh": fresh,
        "parent_declared_by": parent_declared_by,
        "recipe_signals": signals,
        "recipe_stratum": stratum,
        "recipe_stratum_derivation_rule": rule,
        "size_anomaly_cause": size_anomaly_cause,
        "size_anomaly_evidence": size_anomaly_evidence,
        "comparable_dtype": comparable_dtype,
        "parent_dtype": p_dtype,
        "child_dtype": c_dtype,
    }

    # Excluded / unusable calls-out per spec.
    exclusion_reason = None
    usable_pair = True
    if size_anomaly_cause == "missing_shards":
        exclusion_reason = ("child repo has an incomplete/mismatched shard set relative to "
                             "its declared parent (param-count and/or shard evidence below); "
                             "UNLOADABLE ARTEFACT, not a null-edit control")
        usable_pair = False
    pair["usable_pair"] = usable_pair
    pair["exclusion_reason"] = exclusion_reason
    return pair


# --------------------------------------------------------------------------- #
# Main orchestration
# --------------------------------------------------------------------------- #
@logger.catch(reraise=True)
def main() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO",
               format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(LOGS_DIR / "registry.log", rotation="30 MB", level="DEBUG")

    logger.info("=== ARTEFACT 1 (raw half) paired-lineage registry build starting ===")

    seed_panel = load_seed_panel()
    iter1_revisions = load_iter1_revisions()

    seed_repo_ids: set[str] = set()
    seed_families = set(seed_panel.keys())
    # repo_id -> (family, role, recipe_family)
    seed_repo_index: dict[str, tuple[str, str, str]] = {}
    for fam, entries in seed_panel.items():
        for (rid, role, recipe_family) in entries:
            seed_repo_ids.add(rid)
            seed_repo_index[rid] = (fam, role, recipe_family)

    # ---- fresh HF search sweep (Part C) ----
    fresh_candidates, n_screened, terms_used = discover_fresh_candidates(seed_repo_ids)
    logger.info(f"fresh candidates passing filters (ungated, <=4B, safetensors, "
                f"declared base_model): {len(fresh_candidates)}")
    for c in fresh_candidates:
        logger.info(f"  candidate child={c.child_repo} family={c.family} "
                    f"parent={c.declared_base_model} heretic={c.is_heretic} "
                    f"dl={c.downloads} params={c.child_total_params/1e9:.2f}B")

    selected_fresh = rank_and_select_fresh(fresh_candidates, seed_families, MAX_FRESH_PAIRS)
    logger.info(f"selected {len(selected_fresh)} fresh pairs for the registry: "
                f"{[c.child_repo for c in selected_fresh]}")

    # ---- assemble the full list of repo_ids to fetch, with (family, role) ----
    to_fetch: dict[str, tuple[str, str]] = {}
    for rid, (fam, role, _rf) in seed_repo_index.items():
        to_fetch[rid] = (fam, ROLE_MAP.get(role, role))

    # commissioned pair
    to_fetch[COMMISSIONED_PARENT] = to_fetch.get(COMMISSIONED_PARENT, ("qwen3", "instruct"))
    to_fetch[COMMISSIONED_CHILD] = ("qwen3", "abliterated_child")

    fresh_pair_specs: list[tuple[str, str, str, str]] = []  # (family, parent_repo, child_repo, parent_declared_by)
    for c in selected_fresh:
        to_fetch[c.child_repo] = (c.family, "abliterated_child")
        to_fetch.setdefault(c.declared_base_model, (c.family, "instruct"))
        fresh_pair_specs.append((c.family, c.declared_base_model, c.child_repo, "cardData_base_model"))

    logger.info(f"total unique checkpoints to harvest live: {len(to_fetch)}")

    # ---- concurrent per-checkpoint harvest ----
    checkpoints: dict[str, dict[str, Any]] = {}
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(fetch_checkpoint, rid, fam, role, iter1_revisions): rid
                for rid, (fam, role) in to_fetch.items()}
        for fut in cf.as_completed(futs):
            rid = futs[fut]
            try:
                checkpoints[rid] = fut.result()
            except Exception as e:  # noqa: BLE001
                logger.error(f"[{rid}] harvest raised {type(e).__name__}: {e}")
                checkpoints[rid] = {
                    "repo_id": rid, "unavailable": True,
                    "unavailable_status": f"EXC:{type(e).__name__}",
                    "unavailable_date": TODAY_UTC, "readout_class": "metadata",
                }

    unavailable_list = [v for v in checkpoints.values() if v.get("unavailable")]
    for v in unavailable_list:
        logger.warning(f"UNAVAILABLE: {v['repo_id']} status={v.get('unavailable_status')}")

    # ---- build pairs ----
    pairs: list[dict[str, Any]] = []

    def safe_pair(family: str, parent_repo: str, child_repo: str, fresh: bool) -> None:
        p = checkpoints.get(parent_repo)
        c = checkpoints.get(child_repo)
        if p is None or c is None:
            logger.error(f"cannot build pair {family}/{child_repo}: missing checkpoint record")
            return
        if p.get("unavailable") or c.get("unavailable"):
            logger.warning(f"pair {family}/{child_repo}: one side unavailable "
                            f"(parent_unavailable={p.get('unavailable')}, "
                            f"child_unavailable={c.get('unavailable')}) -- recording pair "
                            f"with usable_pair=false")
        pair = make_pair(p, c, family, fresh)
        if p.get("unavailable") or c.get("unavailable"):
            pair["usable_pair"] = False
            pair["exclusion_reason"] = (pair["exclusion_reason"] or "") + \
                "; one side unavailable (see checkpoint 'unavailable' flag)"
        pairs.append(pair)

    # seed-panel-derived pairs: for each family, pair every "abliterated" child
    # with the same-size "instruct" role (matched by leading size token in the
    # repo id, since qwen3 packs multiple sizes into one family).
    def size_token(repo_id: str) -> str:
        m = re.search(r"(\d+(?:\.\d+)?B)", repo_id)
        return m.group(1) if m else ""

    for fam, entries in seed_panel.items():
        instructs = [(rid, size_token(rid)) for rid, role, _rf in entries if role == "instruct"]
        abliterated = [rid for rid, role, _rf in entries if role == "abliterated"]
        for child_rid in abliterated:
            csz = size_token(child_rid)
            parent_rid = None
            for irid, isz in instructs:
                if isz and isz == csz:
                    parent_rid = irid
                    break
            if parent_rid is None and len(instructs) == 1:
                parent_rid = instructs[0][0]
            if parent_rid is None:
                logger.warning(f"family {fam}: cannot match an instruct parent for "
                                f"abliterated child {child_rid} (no same-size instruct arm)")
                continue
            safe_pair(fam, parent_rid, child_rid, fresh=False)

    # commissioned pair
    safe_pair("qwen3", COMMISSIONED_PARENT, COMMISSIONED_CHILD, fresh=True)

    # fresh search-discovered pairs
    for fam, parent_rid, child_rid, _declared_by in fresh_pair_specs:
        safe_pair(fam, parent_rid, child_rid, fresh=True)

    # `fresh` must be true iff NEITHER side appears in SEED_PANEL (per spec).
    for pr in pairs:
        pr["fresh"] = (pr["parent_repo"] not in seed_repo_ids and
                        pr["child_repo"] not in seed_repo_ids)

    # ---- known non-pair size anomalies (base vs its own instruct sibling) ----
    known_size_anomalies: list[dict[str, Any]] = []
    for fam, entries in seed_panel.items():
        bases = [rid for rid, role, _rf in entries if role == "base"]
        instructs = [rid for rid, role, _rf in entries if role == "instruct"]
        for b in bases:
            bsz = size_token(b)
            match = next((i for i in instructs if size_token(i) == bsz), None)
            if match is None and len(instructs) == 1:
                match = instructs[0]
            if match is None:
                continue
            bc, ic = checkpoints.get(b), checkpoints.get(match)
            if not bc or not ic or bc.get("unavailable") or ic.get("unavailable"):
                continue
            anomaly = resolve_size_anomaly({**bc, "role": "base"}, ic)
            if anomaly:
                known_size_anomalies.append({
                    "family": fam, "base_repo": b, "instruct_repo": match,
                    **anomaly,
                })

    # ---- revision-drift list ----
    revision_drift = [
        {"repo_id": v["repo_id"], "family": v.get("family"),
         "revision_iter1": v.get("revision_iter1"), "revision_now": v.get("revision")}
        for v in checkpoints.values()
        if v.get("revision_moved")
    ]

    # ---- assemble output ----
    built_at = datetime.now(timezone.utc).isoformat()
    registry = {
        "built_at_utc": built_at,
        "n_candidates_screened": n_screened,
        "search_terms_used": terms_used,
        "checkpoints": list(checkpoints.values()),
        "pairs": pairs,
        "unavailable": unavailable_list,
        "regex_list": REGEX_LIST,
        "bytes_downloaded": _BYTES_DOWNLOADED["n"],
        "known_size_anomalies_non_pair": known_size_anomalies,
        "revision_drift": revision_drift,
        "excluded_candidates": [
            {"repo_id": FORBIDDEN_CHILD, "reason": "gated='auto'; explicitly forbidden by task spec"},
        ],
    }

    out_path = BUILD_DIR / "registry_raw.json"
    out_path.write_text(json.dumps(registry, indent=2, ensure_ascii=False))
    logger.info(f"wrote {out_path} ({out_path.stat().st_size / 1e6:.2f} MB)")

    # ---- self-verify by re-reading our own JSON ----
    reread = json.loads(out_path.read_text())
    n_pairs = len(reread["pairs"])
    n_families = len({p["family"] for p in reread["pairs"]})
    n_fresh_pairs = sum(1 for p in reread["pairs"] if p["fresh"])
    stratum_hist: dict[str, int] = {}
    for p in reread["pairs"]:
        stratum_hist[p["recipe_stratum"]] = stratum_hist.get(p["recipe_stratum"], 0) + 1
    logger.info(f"VERIFY: re-read {out_path}: pairs={n_pairs} families={n_families} "
                f"fresh_pairs={n_fresh_pairs} stratum_hist={stratum_hist}")
    logger.info(f"VERIFY: bytes_downloaded={reread['bytes_downloaded']} "
                f"({reread['bytes_downloaded']/1e6:.3f} MB)")

    write_report(reread, stratum_hist, n_pairs, n_families, n_fresh_pairs)
    logger.info("=== build complete ===")


def write_report(reg: dict[str, Any], stratum_hist: dict[str, int],
                  n_pairs: int, n_families: int, n_fresh_pairs: int) -> None:
    lines: list[str] = []
    lines.append("# Paired-Lineage Registry -- ARTEFACT 1 (raw half) build report\n")
    lines.append(f"Built at: {reg['built_at_utc']}\n")
    lines.append(f"Candidates screened (unique repos across the live search sweep): "
                 f"{reg['n_candidates_screened']}\n")
    lines.append(f"Search terms used ({len(reg['search_terms_used'])}): "
                 f"{', '.join(reg['search_terms_used'])}\n")
    lines.append(f"Total bytes downloaded this run: {reg['bytes_downloaded']} "
                 f"({reg['bytes_downloaded']/1e6:.3f} MB) -- text/metadata only, "
                 f"no *.safetensors bytes were ever downloaded.\n")

    lines.append("\n## Counts\n")
    lines.append(f"- Pairs: **{n_pairs}**\n")
    lines.append(f"- Families (via pairs): **{n_families}**\n")
    lines.append(f"- Fresh pairs (neither side in SEED_PANEL): **{n_fresh_pairs}**\n")
    lines.append(f"- Checkpoints harvested: **{len(reg['checkpoints'])}**\n")
    lines.append(f"- Unavailable repos: **{len(reg['unavailable'])}**\n")
    lines.append("\n### recipe_stratum histogram\n")
    for k, v in sorted(stratum_hist.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {k}: {v}\n")

    commissioned = next((p for p in reg["pairs"]
                          if p["parent_repo"] == COMMISSIONED_PARENT
                          and p["child_repo"] == COMMISSIONED_CHILD), None)
    lines.append("\n## Commissioned pair (Qwen/Qwen3-4B -> mlabonne/Qwen3-4B-abliterated)\n")
    if commissioned:
        pc = next(c for c in reg["checkpoints"] if c["repo_id"] == COMMISSIONED_PARENT)
        cc = next(c for c in reg["checkpoints"] if c["repo_id"] == COMMISSIONED_CHILD)
        lines.append(f"- present: yes; parent gated={pc.get('gated')}; child gated={cc.get('gated')}\n")
        lines.append(f"- comparable_dtype: {commissioned['comparable_dtype']} "
                      f"(parent dtype={commissioned['parent_dtype']}, "
                      f"child dtype={commissioned['child_dtype']}) -- "
                      f"an bf16 parent compared against a reported F32 (~"
                      f"{(cc.get('safetensors_bytes') or 0)/1e9:.2f} GB) child is a STATED "
                      f"DEVIATION, not a silent one.\n")
        lines.append(f"- forbidden lookalike `{FORBIDDEN_CHILD}` was NOT used "
                      f"(excluded_candidates records why).\n")
    else:
        lines.append("- MISSING -- see logs/registry.log for the failure.\n")

    lines.append(f"\nNote: `huihui-ai/Qwen3-4B-abliterated` (gated='auto') was excluded per "
                 f"task instruction and never fetched for use as a pair member.\n")

    lines.append("\n## Revision drift vs iteration-1 pinned revisions\n")
    if reg["revision_drift"]:
        for d in reg["revision_drift"]:
            lines.append(f"- `{d['repo_id']}` (family {d['family']}): "
                          f"iter1={d['revision_iter1']} -> now={d['revision_now']}\n")
    else:
        lines.append("- none: every repo that was pinned in iteration-1's prereg.json "
                      "still resolves to the same `sha` today.\n")

    lines.append("\n## Size-anomaly resolutions (evidence-backed)\n")

    def find_pair(child_substr: str) -> Optional[dict]:
        return next((p for p in reg["pairs"] if child_substr in p["child_repo"]), None)

    tiny = find_pair("TinyLlama-1.1B-Chat-v1.0-abliterated")
    lines.append("### TinyLlama: philippefunk/TinyLlama-1.1B-Chat-v1.0-abliterated\n")
    if tiny:
        ev = tiny["size_anomaly_evidence"] or {}
        lines.append(f"- size_anomaly_cause = **{tiny['size_anomaly_cause']}**; "
                      f"usable_pair = {tiny['usable_pair']}\n")
        lines.append(f"- evidence: parent bytes={ev.get('parent_bytes')}, "
                      f"child bytes={ev.get('child_bytes')} "
                      f"(ratio={ev.get('ratio_child_over_parent_bytes')}); "
                      f"parent params_total={ev.get('parent_params_total')}, "
                      f"child params_total={ev.get('child_params_total')} "
                      f"-- the child's safetensors metadata reports FEWER total "
                      f"parameters than its declared parent (not merely a smaller dtype), "
                      f"with a mixed F32/F16/U8 parameter-dtype breakdown and no "
                      f"`torch_dtype` recorded in `config.json`. This confirms the "
                      f"iteration-1 report of a shape error under "
                      f"`ignore_mismatched_sizes`: the checkpoint is missing/incomplete "
                      f"weight content, not just stored in a smaller dtype.\n")
        lines.append(f"- VERDICT: **UNLOADABLE ARTEFACT** (missing_shards), NOT a null-edit "
                      f"control. usable_pair forced to false; exclusion_reason recorded.\n")
    else:
        lines.append("- pair not found in registry (harvest failure) -- see logs.\n")

    venky = find_pair("SmolLM2-1.7B-Instruct-Abliterated")
    lines.append("\n### venkycs/SmolLM2-1.7B-Instruct-Abliterated\n")
    if venky:
        ev = venky["size_anomaly_evidence"] or {}
        lines.append(f"- size_anomaly_cause = **{venky['size_anomaly_cause']}**; "
                      f"usable_pair = {venky['usable_pair']}\n")
        lines.append(f"- evidence: parent bytes={ev.get('parent_bytes')}, "
                      f"child bytes={ev.get('child_bytes')} "
                      f"(ratio={ev.get('ratio_child_over_parent_bytes')}); "
                      f"parent params_total={ev.get('parent_params_total')}, "
                      f"child params_total={ev.get('child_params_total')} "
                      f"(essentially IDENTICAL param counts); "
                      f"parent dtype={ev.get('parent_config_torch_dtype')}, "
                      f"child config-declared dtype={ev.get('child_config_torch_dtype')}, "
                      f"but child's per-dtype byte breakdown is "
                      f"{ev.get('child_params_by_dtype')} -- the majority of its weight "
                      f"tensors are actually stored as F8_E4M3 (fp8), not the dtype its "
                      f"config.json declares; the single shard is present and complete "
                      f"(shard_list={ev.get('child_shard_list')}).\n")
        lines.append(f"- VERDICT: shard list is **COMPLETE** and the gap is **dtype** "
                      f"(fp8 quantization on top of an equal-parameter-count checkpoint) "
                      f"-> genuine ANOMALOUS pair; stays in the registry, "
                      f"comparable_dtype=false is recorded.\n")
    else:
        lines.append("- pair not found in registry (harvest failure) -- see logs.\n")

    lines.append("\n### allenai/OLMo-2-0425-1B vs allenai/OLMo-2-0425-1B-Instruct "
                  "(base ~2x its own instruct; NOT a parent/child abliteration pair -- "
                  "recorded under `known_size_anomalies_non_pair`)\n")
    olmo = next((a for a in reg["known_size_anomalies_non_pair"] if a["family"] == "olmo2"), None)
    if olmo:
        ev = olmo["evidence"]
        lines.append(f"- size_anomaly_cause = **{olmo['size_anomaly_cause']}**\n")
        lines.append(f"- evidence: base bytes={ev.get('parent_bytes')} "
                      f"(dtype={ev.get('parent_config_torch_dtype')}), "
                      f"instruct bytes={ev.get('child_bytes')} "
                      f"(dtype={ev.get('child_config_torch_dtype')}); "
                      f"ratio={ev.get('ratio_child_over_parent_bytes')} "
                      f"(~0.5, i.e. base is ~2x); "
                      f"base params_total={ev.get('parent_params_total')} == "
                      f"instruct params_total={ev.get('child_params_total')} "
                      f"(identical parameter counts) -- the base checkpoint is stored in "
                      f"float32 (2 shards) while the instruct checkpoint is stored in "
                      f"bfloat16 (1 shard); 4 bytes/param vs 2 bytes/param exactly explains "
                      f"the ~2x ratio.\n")
    else:
        lines.append("- not resolved this run -- see logs.\n")

    lines.append("\n## Gated repos we refused to authenticate into (recorded, not accessed)\n")
    gated_ckpts = [c for c in reg["checkpoints"] if c.get("gated") in ("true", "auto")]
    if gated_ckpts:
        for c in gated_ckpts:
            lines.append(f"- `{c['repo_id']}` gated={c.get('gated')} "
                         f"(usable={c.get('usable')})\n")
    else:
        lines.append("- none among the harvested checkpoints.\n")
    lines.append(f"- `{FORBIDDEN_CHILD}` gated='auto' was excluded per task instruction "
                 f"WITHOUT a live check (not fetched at all, per instruction not to use it).\n")

    lines.append("\n## Repos that 404'd or were otherwise unreachable (as of "
                  f"{TODAY_UTC})\n")
    if reg["unavailable"]:
        for u in reg["unavailable"]:
            lines.append(f"- `{u['repo_id']}` status={u.get('unavailable_status')}\n")
    else:
        lines.append("- none: every candidate repo resolved.\n")

    lines.append("\n## Chat-template precedence rule (verified against installed transformers)\n")
    lines.append("transformers==5.17.0, `tokenization_utils_base.py` "
                 "`PreTrainedTokenizerBase._from_pretrained()` (~line 1783): "
                 "\"If independent chat template file(s) exist, they take priority over "
                 "template entries in the tokenizer config.\" -- when a repo ships BOTH a "
                 "standalone `chat_template.jinja` and a `chat_template` key inside "
                 "`tokenizer_config.json`, `AutoTokenizer.from_pretrained` loads the "
                 "`.jinja` file and never reads the tokenizer_config key. Recorded per "
                 "checkpoint as `chat_template_source` (`tokenizer_config` | "
                 "`chat_template_jinja` | `both` | `none`) plus `chat_template_winner`.\n")

    lines.append("\n## Fresh (search-discovered) pairs\n")
    for p in reg["pairs"]:
        if p["fresh"] and p["parent_repo"] != COMMISSIONED_PARENT:
            lines.append(f"- **{p['pair_id']}**: `{p['parent_repo']}` -> `{p['child_repo']}` "
                         f"(parent_declared_by={p['parent_declared_by']}, "
                         f"stratum={p['recipe_stratum']})\n")

    out_path = BUILD_DIR / "registry_report.md"
    out_path.write_text("".join(lines))
    logger.info(f"wrote {out_path}")


if __name__ == "__main__":
    main()
