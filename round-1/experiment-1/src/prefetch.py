#!/usr/bin/env python3
"""Pre-fetch the model panel into the shared HF cache, in priority order."""
import os, sys, time, json, traceback
from pathlib import Path
from huggingface_hub import snapshot_download

REPOS = [
    "Qwen/Qwen3-0.6B",
    "Qwen/Qwen3-4B",
    "Qwen/Qwen3-4B-SafeRL",
    "Qwen/Qwen3-4B-Base",
    "CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6",
    "mlabonne/Qwen3-4B-abliterated",
]
ALLOW = ["*.json", "*.safetensors", "*.txt", "*.model", "*.jinja", "*.md"]
status_path = Path(__file__).parent / "work" / "prefetch_status.json"
status = {}
for r in REPOS:
    t0 = time.time()
    try:
        p = snapshot_download(repo_id=r, allow_patterns=ALLOW, max_workers=8)
        status[r] = {"ok": True, "path": p, "secs": round(time.time() - t0, 1)}
        print(f"OK {r} in {time.time()-t0:.1f}s -> {p}", flush=True)
    except Exception as e:
        status[r] = {"ok": False, "error": f"{type(e).__name__}: {e}", "secs": round(time.time() - t0, 1)}
        print(f"FAIL {r}: {e}", flush=True)
        traceback.print_exc()
    status_path.write_text(json.dumps(status, indent=2))
print("PREFETCH_DONE", flush=True)
