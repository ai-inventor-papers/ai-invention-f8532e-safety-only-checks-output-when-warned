"""Pre-draw CPU benchmark deciding the second no-op variant (rule step 3): float16 vs bfloat16 matmul
+ a tiny transformer-like forward on this box. fp16_ok iff fp16 time <= 2x bf16 time."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, jdump, utc_now  # noqa: E402

torch.set_num_threads(2)


def bench(dtype, M=45, K=2048, N=2048, reps=20):
    a = torch.randn(M, K).to(dtype)
    w = torch.randn(N, K).to(dtype)
    lin = torch.nn.functional.linear
    for _ in range(3):
        lin(a, w)
    t = time.perf_counter()
    for _ in range(reps):
        lin(a, w)
    return (time.perf_counter() - t) / reps


res = {"utc": utc_now(), "cpu": "AMD EPYC 9655P (avx512_bf16, no avx512_fp16)", "shape": "45x2048 @ 2048x2048"}
for name, dt in (("bf16", torch.bfloat16), ("fp16", torch.float16), ("fp32", torch.float32)):
    res[f"t_{name}_s"] = bench(dt)
res["fp16_over_bf16"] = res["t_fp16_s"] / res["t_bf16_s"]
res["fp32_over_bf16"] = res["t_fp32_s"] / res["t_bf16_s"]
res["fp16_ok"] = bool(res["fp16_over_bf16"] <= 2.0)
jdump(res, RESULTS / "fp16_benchmark.json")
print(json.dumps(res, indent=1))
