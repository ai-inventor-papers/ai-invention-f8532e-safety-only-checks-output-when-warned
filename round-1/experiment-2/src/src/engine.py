"""Harvest + edit engine for LANE B.

THE EDIT (STAGE 4), implemented exactly.
  The registered lesion is   W(a) = W0 - a * u (u^T W0)   on every residual-stream
  WRITE matrix (o_proj, down_proj, all 36 layers). Qwen3 gives these matrices NO
  bias, so for y = W0 x,
        W(a) x = W0 x - a u (u^T W0 x) = y - a u (u^T y).
  The weight edit is therefore ALGEBRAICALLY IDENTICAL to projecting u out of each
  matrix's OUTPUT. We apply it as an output hook instead of mutating weights:
    * alpha = 0 is a bitwise no-op (T3), not a restored approximation;
    * the restore is exact by construction - no bf16 round-trip error;
    * embed_tokens is provably untouched (T3 tied-embedding check);
    * the weight-space twin needed by K3 is available in closed form,
      ||W(a) - W(0)||_F = a * ||u^T W0||_2 , computed once from the real weights.
  equivalence_check() verifies this against a genuine weight mutation.
"""
from __future__ import annotations

import gc
import json
import os

os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
DEV = "cuda"
DTYPE = torch.bfloat16


# ------------------------------------------------------------------ model
def load_model(repo: str):
    tok = AutoTokenizer.from_pretrained(repo)
    model = AutoModelForCausalLM.from_pretrained(
        repo, dtype=DTYPE, device_map=None, low_cpu_mem_usage=True,
    ).to(DEV).eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model, tok


def model_facts(model, tok) -> dict:
    emb = model.get_input_embeddings().weight
    head = model.get_output_embeddings().weight
    return {
        "n_layers": model.config.num_hidden_layers,
        "d_model": model.config.hidden_size,
        "tie_word_embeddings_config": bool(model.config.tie_word_embeddings),
        "lm_head_is_embed_tokens": emb.data_ptr() == head.data_ptr(),
        "o_proj_has_bias": model.model.layers[0].self_attn.o_proj.bias is not None,
        "down_proj_has_bias": model.model.layers[0].mlp.down_proj.bias is not None,
        "vocab": int(model.config.vocab_size),
        "dtype": str(next(model.parameters()).dtype),
    }


# ------------------------------------------------------------------ the edit
class Lesion:
    """alpha-strength rank-one orthogonalisation of `u` from every residual write.

    `u` is either ONE global direction (the registered primary grid) or a dict
    {layer_index: direction} (the declared PER-LAYER grid). STAGE 9 shows the real
    community abliteration is per-matrix rank-one with a direction that ROTATES with
    depth - layer 0's direction is orthogonal to layer 35's - so the per-layer grid
    is the faithful replica and the single-direction grid is the registered one.
    """

    def __init__(self, model, u, include_embed: bool = False):
        self.model = model
        self.per_layer = isinstance(u, dict)
        if self.per_layer:
            self.u = {int(k): (v / v.norm()).to(DEV, torch.float32) for k, v in u.items()}
        else:
            self.u = (u / u.norm()).to(DEV, torch.float32)
        self.alpha = 0.0
        self.include_embed = include_embed
        self._handles = []
        self._depth = 0          # re-entrant: nesting must NOT apply the edit twice
        mods = []
        for li, lyr in enumerate(model.model.layers):
            mods.append((li, lyr.self_attn.o_proj))
            mods.append((li, lyr.mlp.down_proj))
        if include_embed:
            mods.append((-1, model.get_input_embeddings()))
        self.modules = mods

    def _dir_for(self, li):
        return self.u if not self.per_layer else self.u.get(li)

    def _mk_hook(self, li):
        def hook(mod, inp, out):
            if self.alpha == 0.0:
                return out
            d = self._dir_for(li)
            if d is None:
                return out
            u = d.to(out.dtype)
            coef = torch.matmul(out, u)
            return out - self.alpha * coef.unsqueeze(-1) * u
        return hook

    def _hook(self, mod, inp, out):
        return self._mk_hook(0)(mod, inp, out)

    def __enter__(self):
        self._depth += 1
        if self._depth == 1:
            for li, m in self.modules:
                self._handles.append(m.register_forward_hook(self._mk_hook(li)))
        return self

    def __exit__(self, *a):
        self._depth -= 1
        if self._depth <= 0:
            for h in self._handles:
                h.remove()
            self._handles = []
            self._depth = 0

    def set_alpha(self, a: float):
        self.alpha = float(a)

    def weight_space_norms(self) -> dict:
        """K3's weight-space twin, in closed form: ||W(a)-W(0)||_F = a*||u^T W0||_2."""
        out = {}
        for name in ("o_proj", "down_proj"):
            tot_sq, base_sq = 0.0, 0.0
            for li, lyr in enumerate(self.model.model.layers):
                u32 = self._dir_for(li)
                if u32 is None:
                    continue
                W = (lyr.self_attn.o_proj if name == "o_proj" else lyr.mlp.down_proj).weight
                v = torch.matmul(u32, W.to(torch.float32))       # [in_dim]
                tot_sq += float((v * v).sum())
                base_sq += float((W.to(torch.float32) ** 2).sum())
            out[name] = {"uT_W_fro": math.sqrt(tot_sq), "W_fro": math.sqrt(base_sq),
                         "rel_per_alpha": math.sqrt(tot_sq) / math.sqrt(base_sq)}
        return out


def equivalence_check(model, u: torch.Tensor, alpha: float, ids, mask) -> dict:
    """Verify hook-lesion == genuine weight mutation on a real forward pass."""
    with torch.inference_mode():
        base = model(input_ids=ids, attention_mask=mask).logits.float()
        les = Lesion(model, u)
        les.set_alpha(alpha)
        with les:
            hooked = model(input_ids=ids, attention_mask=mask).logits.float()
        # genuine weight mutation
        u32 = (u / u.norm()).to(DEV, torch.float32)
        saved = []
        for lyr in model.model.layers:
            for mod in (lyr.self_attn.o_proj, lyr.mlp.down_proj):
                W = mod.weight
                saved.append((mod, W.detach().clone()))
                W32 = W.to(torch.float32)
                v = torch.matmul(u32, W32)
                W.copy_((W32 - alpha * torch.outer(u32, v)).to(W.dtype))
        mutated = model(input_ids=ids, attention_mask=mask).logits.float()
        for mod, W0 in saved:
            mod.weight.copy_(W0)
        restored = model(input_ids=ids, attention_mask=mask).logits.float()
    d_hm = float((hooked - mutated).abs().max())
    scale = float(mutated.abs().max())
    return {
        "alpha": alpha,
        "max_abs_diff_hook_vs_weightedit": d_hm,
        "rel_diff_hook_vs_weightedit": d_hm / max(scale, 1e-9),
        "max_abs_diff_base_vs_edited": float((base - mutated).abs().max()),
        "weight_restore_bitwise_exact": bool(torch.equal(base, restored)),
    }


# ------------------------------------------------------------------ tokenisation
@dataclass
class Seq:
    sid: str
    kind: str
    input_ids: list
    prompt_len: int
    cont_len: int
    meta: dict = field(default_factory=dict)


class Planner:
    """Builds input_ids = prompt_ids + cont_ids with EXACT control of the span."""

    def __init__(self, tok, is_instruct: bool, cont_len: int = 128):
        self.tok = tok
        self.is_instruct = is_instruct
        self.cont_len = cont_len
        self.think_close_id = None
        ids = tok.encode("</think>", add_special_tokens=False)
        if len(ids) == 1:
            self.think_close_id = ids[0]

    def prompt_ids(self, request: str) -> list:
        if self.is_instruct:
            txt = self.tok.apply_chat_template(
                [{"role": "user", "content": request}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
        else:
            txt = f"User: {request}\nAssistant:"
        return self.tok.encode(txt, add_special_tokens=False)

    def cont_ids(self, text: str, n: int | None = None) -> list:
        n = n or self.cont_len
        ids = self.tok.encode(" " + text.strip(), add_special_tokens=False)
        if len(ids) < n:
            raise ValueError(f"continuation too short: {len(ids)} < {n}")
        return ids[:n]

    def make(self, sid, kind, request, continuation=None, meta=None, cont_len=None) -> Seq:
        p = self.prompt_ids(request)
        c = self.cont_ids(continuation, cont_len) if continuation is not None else []
        return Seq(sid, kind, p + c, len(p), len(c), meta or {})


# ------------------------------------------------------------------ harvest
class Harvester:
    def __init__(self, model, layers: list[int]):
        self.model = model
        self.layers = layers
        self.buf = {}
        self._h = []

    def _mk(self, li):
        def hook(mod, inp, out):
            h = out[0] if isinstance(out, tuple) else out
            self.buf[li] = h.detach()
        return hook

    def __enter__(self):
        for li in self.layers:
            self._h.append(self.model.model.layers[li].register_forward_hook(self._mk(li)))
        return self

    def __exit__(self, *a):
        for h in self._h:
            h.remove()
        self._h = []


def batches(seqs: list[Seq], token_budget: int = 12000, max_bs: int = 8):
    order = sorted(range(len(seqs)), key=lambda i: len(seqs[i].input_ids))
    cur, curmax = [], 0
    for i in order:
        L = len(seqs[i].input_ids)
        newmax = max(curmax, L)
        if cur and ((len(cur) + 1) * newmax > token_budget or len(cur) + 1 > max_bs):
            yield cur
            cur, curmax = [i], L
        else:
            cur.append(i)
            curmax = newmax
    if cur:
        yield cur


@torch.inference_mode()
def run_harvest(model, tok, seqs, layers, windows, lesion=None, alpha=0.0,
                per_pos_layers=None, want_logits_at=None, token_budget=12000, max_bs=8):
    """Returns dict of numpy arrays keyed by what STAGE 3 needs.

    win[w][layer] : [n_seq, d]  fp16 window-mean residual vectors
    last_prompt[layer] : [n_seq, d] residual at the LAST PROMPT TOKEN
    perpos[layer] : [n_seq, cont_len, d] only for per_pos_layers (fp16)
    logits_next : [n_seq, vocab] float16 logits at the position right after the span
    """
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    n = len(seqs)
    d = model.config.hidden_size
    out = {
        "win": {w: {li: np.zeros((n, d), np.float16) for li in layers} for w in windows},
        "last_prompt": {li: np.zeros((n, d), np.float16) for li in layers},
        "norm": np.zeros(n, np.float32),
        "nll_cont": np.zeros(n, np.float32),
    }
    if per_pos_layers:
        maxc = max(s.cont_len for s in seqs)
        out["perpos"] = {li: np.zeros((n, maxc, d), np.float16) for li in per_pos_layers}
    if want_logits_at is not None:
        out["logits_next"] = np.zeros((n, model.config.vocab_size), np.float16)

    if lesion is not None:
        lesion.set_alpha(alpha)
    ctx_l = lesion if lesion is not None else _null_ctx()
    bs_cap = max_bs
    with ctx_l, Harvester(model, layers) as H:
        blist = list(batches(seqs, token_budget, bs_cap))
        for bidx in blist:
            # OOM -> keep halving, recursively, until batch=1. The GPU is shared with
            # sibling artifacts, so headroom is not ours to assume.
            pending = [bidx]
            while pending:
                cur = pending.pop()
                try:
                    _run_batch(model, tok, seqs, cur, layers, windows, H, out,
                               per_pos_layers, want_logits_at, pad)
                except torch.cuda.OutOfMemoryError:
                    torch.cuda.empty_cache()
                    if len(cur) == 1:
                        raise
                    half = len(cur) // 2
                    pending.extend([cur[half:], cur[:half]])
    return out


class _null_ctx:
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _run_batch(model, tok, seqs, bidx, layers, windows, H, out, per_pos_layers, want_logits_at, pad):
    B = len(bidx)
    L = max(len(seqs[i].input_ids) for i in bidx)
    ids = torch.full((B, L), pad, dtype=torch.long)
    mask = torch.zeros((B, L), dtype=torch.long)
    for r, i in enumerate(bidx):
        s = seqs[i]
        ids[r, :len(s.input_ids)] = torch.tensor(s.input_ids)
        mask[r, :len(s.input_ids)] = 1
    ids, mask = ids.to(DEV), mask.to(DEV)
    res = model(input_ids=ids, attention_mask=mask)
    logits = res.logits
    for li in layers:
        h = H.buf[li].float()                      # [B, L, d]
        for r, i in enumerate(bidx):
            s = seqs[i]
            out["last_prompt"][li][i] = h[r, s.prompt_len - 1].cpu().numpy().astype(np.float16)
            for wname, (a, b) in windows.items():
                if s.cont_len > a:
                    lo = s.prompt_len + a
                    hi = min(s.prompt_len + b, s.prompt_len + s.cont_len)
                    if hi > lo:
                        out["win"][wname][li][i] = h[r, lo:hi].mean(0).cpu().numpy().astype(np.float16)
            if per_pos_layers and li in per_pos_layers and s.cont_len > 0:
                seg = h[r, s.prompt_len:s.prompt_len + s.cont_len]
                out["perpos"][li][i, :s.cont_len] = seg.cpu().numpy().astype(np.float16)
    lastlayer = H.buf[layers[-1]].float()
    for r, i in enumerate(bidx):
        s = seqs[i]
        out["norm"][i] = float(lastlayer[r, :len(s.input_ids)].norm(dim=-1).mean())
        if s.cont_len > 1:
            lg = logits[r, s.prompt_len - 1: s.prompt_len + s.cont_len - 1].float()
            tgt = ids[r, s.prompt_len: s.prompt_len + s.cont_len]
            out["nll_cont"][i] = float(torch.nn.functional.cross_entropy(lg, tgt))
        if want_logits_at is not None:
            pos = len(s.input_ids) - 1
            out["logits_next"][i] = logits[r, pos].float().cpu().numpy().astype(np.float16)
    del res, logits
