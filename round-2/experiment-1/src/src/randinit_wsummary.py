#!/usr/bin/env python
"""Weight summary for the RANDOM-INIT arm (handbook rule d; plan 7.3: X10 must NOT fire here).

A random-init checkpoint has no safetensors on disk, so src/wsummary.py cannot read it. This
builds an architecture-identical model from the config with the library's own initialiser
(float32, fixed seed) and runs the SAME per-layer Gram / spectrum routine the harvest kernel
uses (harvest.w_summary), writing the files CkptCache expects into harvest/<tag>/.

NOTE, recorded in the output: this is an INDEPENDENT DRAW from the same initialiser as the
activation-harvest draw (that draw was not persisted). Any weight-side statistic of a random
init is a property of the initialiser's distribution, not of one draw, so this is the right
negative control; it is labelled as such.

    uv run src/randinit_wsummary.py --tag RandInit-Qwen3-0.6B --repo Qwen/Qwen3-0.6B
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import GLOBAL_SEED, HARVEST, jdump, setup_logging  # noqa: E402
from loguru import logger  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="RandInit-Qwen3-0.6B")
    ap.add_argument("--repo", default="Qwen/Qwen3-0.6B")
    args = ap.parse_args()
    setup_logging("randinit_wsummary")
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM

    from harvest import w_summary

    out_dir = HARVEST / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "W_DONE").exists():
        logger.info(f"SKIP {args.tag} (W_DONE)")
        return 0
    t0 = time.time()
    torch.manual_seed(GLOBAL_SEED + 17)
    conf = AutoConfig.from_pretrained(args.repo)
    model = AutoModelForCausalLM.from_config(conf, dtype=torch.float32).eval()
    meta = w_summary(model, out_dir, store_gram=True, gram_dtype="float16")
    wm = {"repo": args.repo, "tag": args.tag, "random_init": True,
          "n_layers_found": meta["n_layers"], "parts": meta["parts"],
          "native_dtype": "float32 (fresh random init)",
          "draw_note": ("independent draw from the library initialiser (seed "
                        f"{GLOBAL_SEED + 17}); the activation-harvest draw was not persisted, "
                        "and a weight-side statistic of a random init is a property of the "
                        "initialiser's distribution, not of one draw"),
          "elapsed_s": time.time() - t0}
    jdump(wm, out_dir / "w_meta.json")
    (out_dir / "W_DONE").write_text(json.dumps({"ts": time.time(), "elapsed_s": wm["elapsed_s"]}))
    logger.info(f"W-SUMMARY {args.tag} (random init): {meta['n_layers']} layers in "
                f"{wm['elapsed_s']:.1f}s")
    del model
    gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
