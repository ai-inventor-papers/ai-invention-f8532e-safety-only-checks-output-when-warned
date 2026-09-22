#!/usr/bin/env python
"""Background model fetcher (session 2): the run-shared $HF_HOME was found EMPTY at 07:02 on
2026-09-21 (re-created by the harness), so every panel checkpoint must be re-downloaded.

Downloads ONLY what the harvest / W-summary / fingerprint need: safetensors shards (or .bin
when a repo ships no safetensors), configs, tokenizer files and chat templates. Priority
order follows src/sweep.py ORDER so downloads stay ahead of the harvest. Writes one JSON
line per repo to results/fetch_log.jsonl (bytes, seconds, MB/s, error).

Usage: python src/fetch_models.py [--repos r1 r2 ...]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

WS = Path(__file__).resolve().parent.parent
LOG = WS / "results" / "fetch_log.jsonl"

DEFAULT_ORDER = [
    "Qwen/Qwen3-4B-SafeRL",
    "Qwen/Qwen3-0.6B",
    "huihui-ai/Huihui-Qwen3-0.6B-abliterated-v2",
    "Qwen/Qwen3-1.7B",
    "huihui-ai/Huihui-Qwen3-1.7B-abliterated-v2",
    "ibm-granite/granite-3.2-2b-instruct",
    "Damien420/granite-3.2-2b-instruct-abliterated",
    "HuggingFaceTB/SmolLM3-3B",
    "mlx-community/SmolLM3-3B-abliterated-bf16",
    "microsoft/Phi-4-mini-instruct",
    "lunahr/Phi-4-mini-instruct-abliterated",
    "Qwen/Qwen2.5-1.5B-Instruct",
    "Goekdeniz-Guelmez/Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3",
    "Qwen/Qwen3-4B-Base",
    "CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6",
    "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
    "stabilityai/stablelm-2-1_6b-chat",
    "hereticness/heretic_stablelm-2-1_6b-chat",
    "HuggingFaceTB/SmolLM2-1.7B-Instruct",
    "venkycs/SmolLM2-1.7B-Instruct-Abliterated",
]

BASE_PATTERNS = ["*.json", "*.txt", "*.model", "*.jinja", "tokenizer*", "*.py"]
SKIP_DIRS = ("original/", "onnx/", "gguf/", "openvino/", "coreml/", "flax/", "tf/")


def pick_patterns(api: HfApi, repo: str) -> tuple[list[str], int]:
    info = api.model_info(repo, files_metadata=True)
    files = [(s.rfilename, s.size or 0) for s in (info.siblings or [])]
    files = [(f, n) for f, n in files if not f.startswith(SKIP_DIRS)]
    st = [(f, n) for f, n in files if f.endswith(".safetensors")]
    pats = list(BASE_PATTERNS)
    if st:
        pats.append("*.safetensors")
        wbytes = sum(n for _, n in st)
    else:
        pats.append("*.bin")
        wbytes = sum(n for f, n in files if f.endswith(".bin"))
    return pats, wbytes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    repos = a.repos or DEFAULT_ORDER
    api = HfApi()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    for repo in repos:
        t0 = time.time()
        rec = {"repo": repo, "t_start": time.strftime("%H:%M:%S")}
        try:
            pats, wbytes = pick_patterns(api, repo)
            rec["weight_bytes"] = wbytes
            path = snapshot_download(repo, allow_patterns=pats,
                                     ignore_patterns=[d + "*" for d in SKIP_DIRS],
                                     max_workers=a.workers)
            dt = time.time() - t0
            rec.update(ok=True, path=path, seconds=round(dt, 1),
                       mb_per_s=round(wbytes / 1e6 / max(dt, 1e-3), 1))
        except Exception as exc:  # noqa: BLE001 - one repo must never stop the rest
            rec.update(ok=False, error=repr(exc)[:500], tb=traceback.format_exc()[-1500:],
                       seconds=round(time.time() - t0, 1))
        rec["t_end"] = time.strftime("%H:%M:%S")
        with LOG.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        print(json.dumps({k: v for k, v in rec.items() if k != "tb"}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
