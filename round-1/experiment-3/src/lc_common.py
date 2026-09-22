#!/usr/bin/env python
"""LANE C - shared config, paths, logging, small utilities.

This module holds only cheap, dependency-light helpers so that the asset build
and the analysis stages can run without importing torch.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

from loguru import logger

WORKSPACE = Path(__file__).resolve().parent
ASSETS = WORKSPACE / "assets"
RESULTS = WORKSPACE / "results"
PER_CKPT = RESULTS / "per_ckpt"
SEALED = RESULTS / "sealed"
GENS = RESULTS / "gens"
JUDGED = RESULTS / "judged"
S3DIR = RESULTS / "s3"
LOGS = WORKSPACE / "logs"
PREREG = WORKSPACE / "prereg.json"
PREREG_SHA = WORKSPACE / "prereg.sha256"

for d in (ASSETS, RESULTS, PER_CKPT, SEALED, GENS, JUDGED, S3DIR, LOGS):
    d.mkdir(parents=True, exist_ok=True)

# ---- the fixed salt for all hash-ordering / sealing (frozen into prereg) ----
SALT = "lane-c/run_YqmEFECOIR3D/iter1/v1"

# ---- layer band as a DEPTH FRACTION (transferable across depths) ----
LAYER_BAND_LO = 0.45
LAYER_BAND_HI = 0.70

# ---- read windows on the continuation (token indices within the response) ----
WIN_EARLY = (5, 20)
WIN_LATE = (40, 55)
MIN_CONT_TOKENS = 64

# ---- harvest / ground-truth sizes (pre-registered; cut-ladder may shrink) ----
N_HARVEST = 96          # confirmatory twin quadruples
N_RESERVED = 54         # remaining XSTest twin pairs -> reserved evidence
N_FIT_PAIRS = 64        # r_content fitting corpus pairs (128 texts)
N_GT_HARM = 45          # cut-ladder R1 (60->45) for wall-clock under shared-GPU contention
N_GT_BENIGN = 45
N_PROBE = 20            # JBB probe (B2/B3 only), disjoint from GT
BUDGET_KS = [4, 8, 16, 32, 96]

# ---- the shared 10-value harm vocabulary (OR-Bench standard) ----
HARM_VOCAB = ["deception", "harassment", "harmful", "hate", "illegal",
              "privacy", "self-harm", "sexual", "unethical", "violence"]

# ---- S3 decision rule (frozen) ----
S3_MARGIN = 0.15
S3_FAMILIES_WON = 5     # of 6 (relaxed only if <6 scored families -> UNDECIDED)
MEANINGFUL_DELTA = 0.05  # |truth_i - truth_j| filter for pairwise ranking

# ---- judges ----
PRIMARY_JUDGE = "google/gemini-2.5-flash-lite"
SECOND_JUDGE = "openai/gpt-5-mini"
COST_CAP_USD = 10.0
COST_DROP_AUDIT_USD = 6.0
COST_STOP_USD = 8.0


def setup_logging(name: str) -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | {message}")
    logger.add(LOGS / f"{name}.log", level="DEBUG", rotation="50 MB", enqueue=True)


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_canonical(obj) -> str:
    return sha256_str(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def hash_order(items, keyfn):
    """Deterministically order `items` by sha256(keyfn(item) + '|' + SALT)."""
    return sorted(items, key=lambda x: sha256_str(keyfn(x) + "|" + SALT))


def load_json(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(p: Path, obj) -> None:
    tmp = Path(str(p) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    tmp.replace(p)


def read_prereg_sha() -> str | None:
    if PREREG_SHA.exists():
        return PREREG_SHA.read_text().strip()
    return None


def slug_of(repo_id: str) -> str:
    return repo_id.replace("/", "__")
