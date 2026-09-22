#!/usr/bin/env python3
"""DEVICE_SWAP check (amendment A13): the same checkpoint and weights generated on the session-3 CPU box vs the
session-4 GPU box (greedy, identical items / chunks / 96 new tokens). Behaviour-only and never pooled into the
criteria: it measures how much a pure device/kernel change moves greedy text and the judged labels -- an
expression-level no-op with no weight change at all.

Pairs: F1__ref (CPU) vs F1__ref (GPU); F1__int8wo (CPU) vs F1__int8wo (GPU) -- int8wo is an elementwise weight map, so
both boxes build bit-identical weights (fingerprint compared). F1__a10 is NOT a clean swap (session 3 applied the lesion
in float32, session 4 in float64) and is reported only as such.
Writes results/device_swap.json (rates and agreement counts only, never text).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PRIVATE, RESULTS, SEED, jdump, jload, setup_logging, utc_now  # noqa: E402
from loguru import logger  # noqa: E402

CPU_G, CPU_J = PRIVATE / "gens_cpu_s3", PRIVATE / "judged_cpu_s3"
GPU_G, GPU_J = PRIVATE / "gens", PRIVATE / "judged"


def _rows(p: Path) -> dict:
    return {r["item_id"]: r for r in (json.loads(l) for l in p.read_text().splitlines() if l.strip())}


def _lab(r: dict | None, key: str):
    if not r:
        return None
    jp = r.get("judge_primary") or {}
    return jp.get(key) if isinstance(jp, dict) else None


def compare(tag: str, fp_cpu: str | None, fp_gpu: str | None) -> dict:
    gc_, gg = _rows(CPU_G / f"{tag}.jsonl"), _rows(GPU_G / f"{tag}.jsonl")
    jc, jg = _rows(CPU_J / f"{tag}.jsonl"), _rows(GPU_J / f"{tag}.jsonl")
    ids = sorted(set(gc_) & set(gg))
    same_text = [i for i in ids if gc_[i]["response"] == gg[i]["response"]]
    out = {"tag": tag, "n_items": len(ids), "identical_response_text": len(same_text),
           "identical_frac": len(same_text) / max(len(ids), 1),
           "weight_fingerprint_cpu": fp_cpu, "weight_fingerprint_gpu": fp_gpu,
           "same_weights": (fp_cpu == fp_gpu) if (fp_cpu and fp_gpu) else None}
    harm = [i for i in ids if gg[i]["set"] == "harm"]
    ben = [i for i in ids if gg[i]["set"] == "benign"]
    res = {}
    for name, sel, key in (("HC", harm, "harmful_content"), ("OR", ben, "refused")):
        a = [(_lab(jc.get(i), key), _lab(jg.get(i), key)) for i in sel]
        a = [(int(bool(x)), int(bool(y))) for x, y in a if x is not None and y is not None]
        if not a:
            res[name] = None
            continue
        x, y = np.array(a).T
        rng = np.random.default_rng(SEED)
        boots = [float((y[idx] - x[idx]).mean()) for idx in (rng.integers(0, len(x), len(x)) for _ in range(2000))]
        res[name] = {"n": len(a), "rate_cpu": float(x.mean()), "rate_gpu": float(y.mean()), "delta_gpu_minus_cpu": float((y - x).mean()),
                     "ci95": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
                     "label_agreement": float((x == y).mean()), "n_discordant": int((x != y).sum())}
    out["labels"] = res
    return out


def main() -> None:
    setup_logging("device_swap")
    tim_cpu = jload(RESULTS / "cpu_s3_archive" / "gen_timings.json") if (RESULTS / "cpu_s3_archive" / "gen_timings.json").exists() else {}
    tim_gpu = jload(RESULTS / "gen_timings.json") if (RESULTS / "gen_timings.json").exists() else {}
    doc = {"utc": utc_now(), "what": __doc__.strip().splitlines()[0], "pairs": []}
    for tag in ("F1__ref", "F1__int8wo", "F1__a10"):
        if not all((d / f"{tag}.jsonl").exists() for d in (CPU_G, GPU_G, CPU_J, GPU_J)):
            doc["pairs"].append({"tag": tag, "status": "NOT_AVAILABLE"})
            continue
        r = compare(tag, (tim_cpu.get(tag) or {}).get("weight_fingerprint"), (tim_gpu.get(tag) or {}).get("weight_fingerprint"))
        r["clean_device_swap"] = tag != "F1__a10"
        doc["pairs"].append(r)
        logger.info(json.dumps(r)[:400])
    jdump(doc, RESULTS / "device_swap.json")


if __name__ == "__main__":
    main()
