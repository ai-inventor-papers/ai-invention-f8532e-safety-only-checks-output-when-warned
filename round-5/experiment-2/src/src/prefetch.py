#!/usr/bin/env python3
"""Prefetch panel snapshots ahead of the GPU queue.

Download is otherwise serialised with GPU work: the card sits idle while a
checkpoint comes off the Hub.  This walks results/sweep_order.json in order and
pulls each repo at its FROZEN revision_sha, skipping anything already cached.
It touches no model weights beyond writing them to the shared cache, computes
nothing, and is safe to run concurrently with the sweep.

    python prefetch.py --n 8 [--max-gb 12]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "src"))

ALLOW = ["*.safetensors", "*.json", "*.model", "*.txt", "tokenizer*", "*.jinja", "*.py"]
IGNORE = ["*.bin", "*.pth", "*.h5", "*.msgpack", "*.onnx", "*.gguf", "*.md",
          "*.png", "*.jpg", "*.jpeg", "*.gif", "*.pdf"]


def main() -> int:
    from huggingface_hub import snapshot_download
    from huggingface_hub.errors import HfHubHTTPError

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--max-gb", type=float, default=14.0)
    ns = ap.parse_args()

    order = json.loads((WS / "results" / "sweep_order.json").read_text())["order"]
    got, gb, rows = 0, 0.0, []
    for row in order:
        if got >= ns.n or gb >= ns.max_gb:
            break
        if row.get("reserve"):
            continue
        repo, rev = row["repo"], row.get("revision_sha")
        size = float(row.get("bf16_gb") or 0.0)
        if gb + size > ns.max_gb:
            continue
        t0 = time.time()
        try:
            p = snapshot_download(repo_id=repo, revision=rev, allow_patterns=ALLOW,
                                  ignore_patterns=IGNORE)
            dt = time.time() - t0
            gb += size
            got += 1
            rows.append({"repo": repo, "revision": rev, "gb": size,
                         "seconds": round(dt, 1), "path": p, "status": "OK"})
            print(f"OK    {repo:52} {size:5.2f} GB  {dt:6.1f}s", flush=True)
        except (HfHubHTTPError, OSError, ValueError) as e:
            rows.append({"repo": repo, "revision": rev, "gb": size,
                         "status": "FAILED", "error": f"{type(e).__name__}: {e}"[:400]})
            print(f"FAIL  {repo:52} {type(e).__name__}: {str(e)[:120]}", flush=True)

    out = WS / "results" / "prefetch_log.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"n_ok": sum(r["status"] == "OK" for r in rows),
                               "n_failed": sum(r["status"] == "FAILED" for r in rows),
                               "gb": round(gb, 2), "rows": rows}, indent=1), encoding="utf-8")
    tmp.replace(out)
    print(f"prefetched {got} repos, {gb:.1f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
