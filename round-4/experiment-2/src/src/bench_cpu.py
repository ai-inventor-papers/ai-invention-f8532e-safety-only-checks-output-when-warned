#!/usr/bin/env python3
"""CPU throughput benchmark for Qwen3-4B bf16: load, prefill, cached last-token pass, decode step.
Used ONLY to size the grid (aii-long-running-tasks: extrapolate before scaling)."""
import json
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, DynamicCache

WS = Path(__file__).resolve().parents[1]
repo = sys.argv[1] if len(sys.argv) > 1 else "Qwen/Qwen3-4B"
torch.set_num_threads(2)
t0 = time.time()
tok = AutoTokenizer.from_pretrained(repo)
model = AutoModelForCausalLM.from_pretrained(repo, dtype=torch.bfloat16, low_cpu_mem_usage=True)
model.eval()
t_load = time.time() - t0
print("load_s", t_load, flush=True)
texts = [tok.apply_chat_template([{"role": "user", "content": f"Explain topic number {i} about gardening and soil quality in some detail please."}],
                                 tokenize=False, add_generation_prompt=True, enable_thinking=False) for i in range(96)]
tok.padding_side = "left"
enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False)
ids, attn = enc["input_ids"], enc["attention_mask"]
print("prompt len", ids.shape, flush=True)
res = {"repo": repo, "load_s": t_load, "prompt_len": int(ids.shape[1])}
with torch.no_grad():
    for bs in (16, 48):
        pre = ids[:bs, :-1]; pa = attn[:bs, :-1]
        pos = (pa.long().cumsum(-1) - 1).clamp(min=0)
        t = time.time()
        out = model(input_ids=pre, attention_mask=pa, position_ids=pos, use_cache=True, logits_to_keep=1)
        dt = time.time() - t
        ntok = int(pa.sum())
        res[f"prefill_bs{bs}_s"] = dt; res[f"prefill_bs{bs}_tok_per_s"] = ntok / dt
        print(f"prefill bs{bs} {dt:.1f}s {ntok/dt:.1f} tok/s", flush=True)
        cache = out.past_key_values
        L0 = cache.get_seq_length()
        full_attn = torch.cat([pa, torch.ones(bs, 1, dtype=pa.dtype)], 1)
        lp = pos[:, -1:] + 1
        for rep in range(2):
            t = time.time()
            o2 = model(input_ids=ids[:bs, -1:], attention_mask=full_attn, position_ids=lp, past_key_values=cache,
                       use_cache=True, logits_to_keep=1)
            dt = time.time() - t
            cache.crop(L0)
            res[f"lasttok_bs{bs}_s"] = dt
            print(f"last-token bs{bs} {dt:.2f}s", flush=True)
        # full forward reference for equivalence
        if bs == 16:
            fpos = (attn[:bs].long().cumsum(-1) - 1).clamp(min=0)
            ref = model(input_ids=ids[:bs], attention_mask=attn[:bs], position_ids=fpos, use_cache=False, logits_to_keep=1).logits[:, -1].float()
            o2 = model(input_ids=ids[:bs, -1:], attention_mask=full_attn, position_ids=lp, past_key_values=cache,
                       use_cache=True, logits_to_keep=1)
            cache.crop(L0)
            diff = (o2.logits[:, -1].float() - ref).abs().max().item()
            agree = (o2.logits[:, -1].argmax(-1) == ref.argmax(-1)).float().mean().item()
            res["lasttok_vs_full_maxabs"] = diff; res["lasttok_vs_full_argmax_agree"] = agree
            print("last-token vs full forward max|dlogit|", diff, "argmax agree", agree, flush=True)
        del out, cache
(WS / "results").mkdir(exist_ok=True)
(WS / "results" / "bench_cpu.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res), flush=True)
