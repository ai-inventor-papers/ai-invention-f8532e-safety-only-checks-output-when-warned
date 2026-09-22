"""Intervention engine for the causal depth x site grid (bf16; CUDA when available, CPU fallback).

Design:
  * PREFIX CACHE. Site P intervenes ONLY at the last prompt position, and no earlier position attends to it,
    so the prompt minus its last token is prefilled ONCE per item (K/V kept per layer) and every arm
    re-runs only the last prompt token (q_len = 1) over that cache. Teacher-forced SPAN passes (sites D/E,
    forward-only) generalise this: the prefix is prompt + arm-0 response tokens before the window and the
    window's S tokens are re-run (q_len = S) for every arm.
  * ROW STACKING. A pass is a batch of rows, one row per (item, arm, band); each item's prefix K/V is
    replicated per row, so every arm of an item sees bit-identical inputs.
  * PER-ROW OPS inside ONE forward hook per decoder layer (output = residual after block l), applied to the
    last S positions of the current call (S = 1 for the prompt pass and for every decode call):
        c_r = x_{src(r)} . V_{src(r)}          (measured on the SOURCE row at the same position, before its edit)
        x_r <- x_r - c_r W_r                   (projection-out: V=W=direction, src=self;
                                                matched random: W=u_{l,j}, src = the F (or N6) row of the same
                                                item and band in the same pass -> identical displacement
                                                magnitude |c| per position per layer;
                                                own-coefficient random (decode sites): V=F, W=u, src=self)
        x_r <- target_l                        (positive-control patch rows)
    fp32 math, cast back to bf16. The same hook records per-row projections of the (post-edit) residual on
    the readout directions (F_l, N6_l, F_perpU_l) for every layer (mean over the S positions).
Session 4 (GPU pod): device-aware port of the session-3 CPU engine + S-position hook + all arms at decode sites.
"""
from __future__ import annotations

import gc
import math
import time
from dataclasses import dataclass, field

import numpy as np
import torch
from loguru import logger


@dataclass
class Prefix:
    """Prefilled K/V of the prefix for a chunk of items (left-padded to T) + the S tokens re-run per arm."""
    item_ids: list[str]
    K: list[torch.Tensor]            # per layer [n, kvh, T, hd] bf16
    V: list[torch.Tensor]
    mask: torch.Tensor               # [n, T] long
    span_tok: torch.Tensor           # [n, S] long (S = 1: the last prompt token)
    span_pos: torch.Tensor           # [n, S] long position ids of the span tokens

    @property
    def n(self) -> int:
        return len(self.item_ids)

    @property
    def T(self) -> int:
        return int(self.mask.shape[1])

    @property
    def S(self) -> int:
        return int(self.span_tok.shape[1])

    def nbytes(self) -> int:
        return sum(k.numel() * k.element_size() * 2 for k in self.K)

    def to(self, device) -> "Prefix":
        """Chunk-level residency: prefixes live on the host and one chunk at a time is moved to the GPU."""
        if self.mask.device == torch.device(device):
            return self
        nb = torch.device(device).type == "cuda"
        return Prefix(item_ids=self.item_ids, K=[k.to(device, non_blocking=nb) for k in self.K],
                      V=[v.to(device, non_blocking=nb) for v in self.V], mask=self.mask.to(device),
                      span_tok=self.span_tok.to(device), span_pos=self.span_pos.to(device))


@dataclass
class Row:
    item: int                        # index into the Prefix chunk
    arm: str                         # "0","F","N6","N6perp","RF","RN6","RFo","RN6o","POS"
    band: str | None = None          # "B1".."B6" (None for arm 0)
    draw: int = 0                    # R draw index (1-based) for RF / RN6 / RFo / RN6o


@dataclass
class Spec:
    """Active intervention + capture specification for one forward call."""
    layer_ops: dict = field(default_factory=dict)       # l -> dict(V, W, src, has, patch, target)
    readout: dict | None = None                          # l -> [K, d] fp32 readout directions (device)
    proj: torch.Tensor | None = None                     # [R, L, K] fp32 capture of projections (device)
    full: torch.Tensor | None = None                     # [R, L, d] fp32 capture of last-position residuals
    disp: dict = field(default_factory=dict)             # l -> (c [R,S], dnorm_fp32 [R,S])
    check_rows: torch.Tensor | None = None               # rows (arm F / N6 / N6perp) for the post-cast check
    check_dirs: dict = field(default_factory=dict)       # l -> [C, d] direction to test residual along
    resid_ratio: dict = field(default_factory=dict)      # l -> max |x.v|/|x| over check rows (0-d tensor)
    n_pos: int = 1                                       # number of trailing positions edited (span length)
    active: bool = True


# own-coefficient arms: (V key, W key); "U" = the random pool draw u_{l,j}
OWN_ARMS = {"F": ("F", "F"), "N6": ("N6", "N6"), "N6perp": ("N6perp", "N6perp"), "FperpU": ("FperpU", "FperpU"),
            "RFo": ("F", "U"), "RN6o": ("N6", "U"), "RUo": ("FperpU", "U")}
# matched-displacement arms: the coefficient comes from the source row (F / N6 row of the same item & band)
MATCHED_ARMS = {"RF": "F", "RN6": "N6"}


class Engine:
    def __init__(self, repo: str, n_threads: int = 2, device: str | None = None):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.device = torch.device(device if device else ("cuda" if torch.cuda.is_available() else "cpu"))
        if self.device.type == "cpu":
            torch.set_num_threads(n_threads)
        t0 = time.time()
        self.repo = repo
        self.tok = AutoTokenizer.from_pretrained(repo)
        kw = dict(dtype=torch.bfloat16, low_cpu_mem_usage=True)
        if self.device.type == "cuda":
            kw["device_map"] = f"cuda:{self.device.index or 0}"
        self.model = AutoModelForCausalLM.from_pretrained(repo, **kw)
        self.model.eval()
        self.t_load = time.time() - t0
        cfg = self.model.config
        self.cfg = cfg
        self.L = int(cfg.num_hidden_layers)
        self.d = int(cfg.hidden_size)
        self.layers = self.model.model.layers
        gcfg = self.model.generation_config
        eos = gcfg.eos_token_id if gcfg.eos_token_id is not None else self.tok.eos_token_id
        self.eos = set(eos if isinstance(eos, (list, tuple)) else [eos]) - {None}
        self.eos_cpu = torch.tensor(sorted(self.eos), dtype=torch.long)
        self.pad_id = self.tok.pad_token_id if self.tok.pad_token_id is not None else min(self.eos)
        # the custom greedy loop == HF greedy generate only if no logits processor alters the argmax
        proc = {k: getattr(gcfg, k, None) for k in ("repetition_penalty", "no_repeat_ngram_size", "min_length",
                                                   "min_new_tokens", "bad_words_ids", "suppress_tokens",
                                                   "begin_suppress_tokens", "sequence_bias",
                                                   "encoder_repetition_penalty", "forced_bos_token_id",
                                                   "forced_eos_token_id")}
        bad = {k: v for k, v in proc.items() if v not in (None, 1.0, 0, [], {}) and not (k == "min_length" and v == 0)}
        self.gen_config_check = {"argmax_altering_processors": bad, "sampling_params_ignored": {
            k: getattr(gcfg, k, None) for k in ("do_sample", "temperature", "top_p", "top_k")}}
        assert not bad, f"generation_config has argmax-altering processors: {bad}"
        self.spec: Spec | None = None
        self.handles: list = []
        self.register_hooks()
        logger.info(f"loaded {repo} in {self.t_load:.1f}s on {self.device}  L={self.L} d={self.d} "
                    f"eos={sorted(self.eos)}")

    # ------------------------------------------------------------------------------------------
    # hooks
    # ------------------------------------------------------------------------------------------
    def register_hooks(self) -> None:
        if self.handles:
            return
        self.handles = [layer.register_forward_hook(self._make_hook(l)) for l, layer in enumerate(self.layers)]

    def remove_hooks(self) -> None:
        for h in self.handles:
            h.remove()
        self.handles = []

    def _make_hook(self, l: int):
        def hook(module, args, output):
            spec = self.spec
            if spec is None or not spec.active:
                return None
            h = output[0] if isinstance(output, tuple) else output
            S = spec.n_pos
            x = h[:, -S:, :].float()                                     # [R, S, d] site positions
            op = spec.layer_ops.get(l)
            modified = False
            if op is not None:
                c_all = torch.einsum("rsd,rd->rs", x, op["V"])            # measured on each row
                c = c_all[op["src"]] * op["has"][:, None]                 # coefficient from the source row
                dx = c[..., None] * op["W"][:, None, :]
                x = x - dx
                dn = dx.norm(dim=-1)                                      # [R, S]
                if op["patch"] is not None:
                    pm = op["patch"]
                    tgt = op["target"][None, None, :].expand_as(x)
                    dn = torch.where(pm[:, None], (tgt - x).norm(dim=-1), dn)
                    x = torch.where(pm[:, None, None], tgt, x)
                spec.disp[l] = (c.detach(), dn.detach())
                modified = True
            xb = x.to(h.dtype)
            if modified and spec.check_rows is not None and l in spec.check_dirs:
                xr = xb[spec.check_rows].float()                          # [C, S, d]
                v = spec.check_dirs[l]                                    # [C, d]
                spec.resid_ratio[l] = (torch.einsum("csd,cd->cs", xr, v).abs() /
                                       xr.norm(dim=-1).clamp_min(1e-9)).max()
            if spec.readout is not None and spec.proj is not None:
                spec.proj[:, l, :] = torch.einsum("rsd,kd->rk", xb.float(), spec.readout[l]) / S
            if spec.full is not None:
                spec.full[:, l, :] = xb[:, -1, :].float()
            if modified:
                h[:, -S:, :] = xb
                return output
            return None
        return hook

    # ------------------------------------------------------------------------------------------
    # tokenisation
    # ------------------------------------------------------------------------------------------
    def encode(self, texts: list[str]) -> list[list[int]]:
        return [self.tok(t, add_special_tokens=False)["input_ids"] for t in texts]

    def chat_render(self, text: str) -> str:
        return self.tok.apply_chat_template([{"role": "user", "content": text}], tokenize=False,
                                            add_generation_prompt=True, enable_thinking=False)

    @staticmethod
    def _left_pad(seqs: list[list[int]], pad: int) -> tuple[torch.Tensor, torch.Tensor]:
        T = max(len(s) for s in seqs)
        ids = torch.full((len(seqs), T), pad, dtype=torch.long)
        mask = torch.zeros((len(seqs), T), dtype=torch.long)
        for i, s in enumerate(seqs):
            if len(s):
                ids[i, T - len(s):] = torch.tensor(s, dtype=torch.long)
                mask[i, T - len(s):] = 1
        return ids, mask

    @staticmethod
    def _positions(mask: torch.Tensor) -> torch.Tensor:
        pos = mask.long().cumsum(-1) - 1
        pos.masked_fill_(mask == 0, 1)
        return pos

    # ------------------------------------------------------------------------------------------
    # full-prompt forward (arm 0, capture only): twins, decodability items, stimuli check
    # ------------------------------------------------------------------------------------------
    @torch.no_grad()
    def prompt_states(self, seqs: list[list[int]], *, readout: dict | None = None, full: bool = False,
                      chunk: int = 24, keep_logits: bool = True) -> dict:
        dev = self.device
        n = len(seqs)
        order = np.argsort([len(s) for s in seqs], kind="mergesort")
        K = 0 if readout is None else next(iter(readout.values())).shape[0]
        proj = torch.zeros((n, self.L, K)) if readout is not None else None
        fullb = torch.zeros((n, self.L, self.d)) if full else None
        logits_last = torch.zeros((n, self.model.config.vocab_size)) if keep_logits else None
        for s in range(0, n, chunk):
            idx = order[s:s + chunk]
            ids, mask = self._left_pad([seqs[i] for i in idx], self.pad_id)
            ids, mask = ids.to(dev), mask.to(dev)
            spec = Spec(readout=readout,
                        proj=torch.zeros((len(idx), self.L, K), device=dev) if readout is not None else None,
                        full=torch.zeros((len(idx), self.L, self.d), device=dev) if full else None)
            self.spec = spec
            try:
                out = self.model(input_ids=ids, attention_mask=mask, position_ids=self._positions(mask),
                                 use_cache=False, logits_to_keep=1)
            finally:
                self.spec = None
            it = torch.as_tensor(idx)
            if proj is not None:
                proj[it] = spec.proj.cpu()
            if fullb is not None:
                fullb[it] = spec.full.cpu()
            if logits_last is not None:
                logits_last[it] = out.logits[:, -1, :].float().cpu()
            del out, spec
        return {"proj": proj, "full": fullb, "logits": logits_last}

    # ------------------------------------------------------------------------------------------
    # prefix cache
    # ------------------------------------------------------------------------------------------
    @torch.no_grad()
    def prefill(self, item_ids: list[str], seqs: list[list[int]]) -> Prefix:
        """Site-P prefix: prompt[:-1] prefilled, the last prompt token re-run per arm (S = 1)."""
        return self.prefill_span(item_ids, [s[:-1] for s in seqs], [[s[-1]] for s in seqs])

    @torch.no_grad()
    def prefill_span(self, item_ids: list[str], prefix_seqs: list[list[int]], span_seqs: list[list[int]]) -> Prefix:
        """Generic prefix: prefix_seqs prefilled once; span_seqs (all of length S) re-run per arm."""
        dev = self.device
        S = len(span_seqs[0])
        assert all(len(x) == S for x in span_seqs), "span lengths differ within a chunk"
        ids, mask = self._left_pad(prefix_seqs, self.pad_id)
        ids, mask = ids.to(dev), mask.to(dev)
        out = self.model(input_ids=ids, attention_mask=mask, position_ids=self._positions(mask),
                         use_cache=True, logits_to_keep=1)
        cache = out.past_key_values
        host = dev.type == "cuda"             # store on the (pinned) host; Prefix.to(dev) per chunk
        Ks = [(cache.layers[l].keys.contiguous().cpu().pin_memory() if host else cache.layers[l].keys.contiguous())
              for l in range(self.L)]
        Vs = [(cache.layers[l].values.contiguous().cpu().pin_memory() if host else cache.layers[l].values.contiguous())
              for l in range(self.L)]
        plen = mask.sum(-1).long()          # real prefix length == position id of the first span token
        span_pos = plen[:, None] + torch.arange(S, device=dev)[None, :]
        span_tok = torch.tensor(span_seqs, dtype=torch.long)
        del out, cache
        return Prefix(item_ids=list(item_ids), K=Ks, V=Vs, mask=mask.cpu(), span_tok=span_tok,
                      span_pos=span_pos.cpu())

    def _cache_for(self, pre: Prefix, item_rows: torch.Tensor):
        from transformers import DynamicCache
        cache = DynamicCache(config=self.model.config)
        for l in range(self.L):
            lay = cache.layers[l]
            k = pre.K[l].index_select(0, item_rows)
            v = pre.V[l].index_select(0, item_rows)
            if hasattr(lay, "lazy_initialization"):
                lay.lazy_initialization(k, v)
                lay.keys, lay.values = k, v
                lay.is_initialized = True
            else:  # pragma: no cover - older cache API
                lay.update(k, v)
        return cache

    # ------------------------------------------------------------------------------------------
    # stacked pass (site P, or a teacher-forced span) + optional greedy continuation
    # ------------------------------------------------------------------------------------------
    def _to_dev_ops(self, ops: dict) -> dict:
        dev = self.device
        out = {}
        for l, op in ops.items():
            out[l] = {k: (v.to(dev) if isinstance(v, torch.Tensor) else v) for k, v in op.items()}
        return out

    def build_spec(self, rows: list[Row], dirs: dict, readout: dict | None, bands: dict) -> Spec:
        """dirs: {'F': [L,d], 'N6': [L,d], 'N6perp': [L,d], 'FperpU': [L,d], 'U': [L, J, d], 'target': [L,d]}
        fp32 CPU tensors. Built on CPU, moved to the engine device once."""
        R = len(rows)
        layer_rows: dict[int, list[int]] = {}
        for r, row in enumerate(rows):
            if row.arm == "0" or row.band is None:
                continue
            for l in bands[row.band]:
                layer_rows.setdefault(l, []).append(r)
        # source rows for matched random arms: the F / N6 row of the same item and band
        src_of: dict[tuple, int] = {}
        for r, row in enumerate(rows):
            if row.arm in ("F", "N6"):
                src_of.setdefault((row.item, row.band, row.arm), r)
        ops = {}
        check_rows = [r for r, row in enumerate(rows) if row.arm in ("F", "N6", "N6perp", "FperpU")]
        check_dirs = {}
        for l, rl in layer_rows.items():
            Vm = torch.zeros((R, self.d))
            Wm = torch.zeros((R, self.d))
            src = torch.arange(R)
            has = torch.zeros(R)
            patch = torch.zeros(R, dtype=torch.bool)
            cd = torch.zeros((len(check_rows), self.d)) if check_rows else None
            for r in rl:
                row = rows[r]
                if row.arm in OWN_ARMS:
                    vk, wk = OWN_ARMS[row.arm]
                    Vm[r] = dirs[vk][l]
                    Wm[r] = dirs["U"][l, row.draw - 1] if wk == "U" else dirs[wk][l]
                    has[r] = 1.0
                elif row.arm in MATCHED_ARMS:
                    key = (row.item, row.band, MATCHED_ARMS[row.arm])
                    assert key in src_of, f"matched arm {row} has no source row in this pass"
                    src[r] = src_of[key]
                    Wm[r] = dirs["U"][l, row.draw - 1]
                    has[r] = 1.0
                elif row.arm == "POS":
                    patch[r] = True
                else:
                    raise ValueError(f"unknown arm {row.arm}")
            if cd is not None:
                for k, r in enumerate(check_rows):
                    if rows[r].band is not None and l in bands[rows[r].band]:
                        cd[k] = dirs[rows[r].arm][l]
                check_dirs[l] = cd.to(self.device)
            ops[l] = {"V": Vm, "W": Wm, "src": src, "has": has, "patch": patch if bool(patch.any()) else None,
                      "target": dirs["target"][l] if bool(patch.any()) else None}
        K = 0 if readout is None else next(iter(readout.values())).shape[0]
        return Spec(layer_ops=self._to_dev_ops(ops), readout=readout,
                    proj=torch.zeros((R, self.L, K), device=self.device) if readout is not None else None,
                    check_rows=torch.tensor(check_rows, dtype=torch.long, device=self.device) if check_rows else None,
                    check_dirs=check_dirs)

    @torch.no_grad()
    def stacked_pass(self, pre: Prefix, rows: list[Row], spec: Spec | None, *, max_new: int = 0,
                     keep_logits: bool = True) -> dict:
        """One pass of the S span tokens for every row (hooks per spec; S = 1 at site P), optionally continued
        by greedy decoding for max_new-1 further tokens with hooks INACTIVE (site P leaves decode untouched)."""
        dev = self.device
        pre = pre.to(dev)
        R = len(rows)
        S = pre.S
        item_rows = torch.tensor([r.item for r in rows], dtype=torch.long, device=dev)
        cache = self._cache_for(pre, item_rows)
        attn = torch.cat([pre.mask.index_select(0, item_rows), torch.ones((R, S), dtype=torch.long, device=dev)],
                         dim=1)
        pos = pre.span_pos.index_select(0, item_rows)
        ids = pre.span_tok.index_select(0, item_rows)
        if spec is not None:
            spec.n_pos = S
        self.spec = spec
        try:
            out = self.model(input_ids=ids, attention_mask=attn, position_ids=pos, past_key_values=cache,
                             use_cache=True, logits_to_keep=1)
        finally:
            self.spec = None
        logits = out.logits[:, -1, :].float()
        res = {"logits": logits if keep_logits else None, "first_tok": logits.argmax(-1)}
        if max_new > 1:
            res["tokens"], res["steps"] = self._greedy_continue(out.past_key_values, attn, pos[:, -1],
                                                                res["first_tok"], max_new)
        del out, cache
        return res

    @torch.no_grad()
    def _greedy_continue(self, past, attn: torch.Tensor, pos_last: torch.Tensor, first: torch.Tensor,
                         max_new: int) -> tuple[torch.Tensor, int]:
        """iter-3 greedy_shrink: identical to greedy generate (no logits processors), finished rows are
        dropped from the batch and the KV cache. Returns CPU tokens [B, max_new]."""
        dev = self.device
        B = first.shape[0]
        res = torch.full((B, max_new), self.pad_id, dtype=torch.long)
        active = torch.arange(B)
        nxt = first
        cur_attn, cur_pos = attn, pos_last
        steps = 0
        for step in range(max_new):
            nxt_c = nxt.cpu()
            res[active, step] = nxt_c
            steps = step + 1
            done = torch.isin(nxt_c, self.eos_cpu)
            if step == max_new - 1 or bool(done.all()):
                break
            if bool(done.any()):
                keep = (~done).nonzero().squeeze(1)
                keep_d = keep.to(dev)
                past.batch_select_indices(keep_d)
                active, nxt, cur_attn, cur_pos = active[keep], nxt[keep_d], cur_attn[keep_d], cur_pos[keep_d]
            cur_attn = torch.cat([cur_attn, torch.ones((cur_attn.shape[0], 1), dtype=cur_attn.dtype, device=dev)],
                                 dim=1)
            cur_pos = cur_pos + 1
            out = self.model(input_ids=nxt[:, None], attention_mask=cur_attn, position_ids=cur_pos[:, None],
                             past_key_values=past, use_cache=True, logits_to_keep=1)
            past = out.past_key_values
            nxt = out.logits[:, -1, :].argmax(-1)
            del out
        return res, steps

    # ------------------------------------------------------------------------------------------
    # site generation (sites P, D, D', E): interventions INSIDE the greedy loop
    # ------------------------------------------------------------------------------------------
    # site -> (edit the last prompt position?, first decode call, last decode call); decode call t has
    # generated token t as INPUT and predicts token t+1 (token 1 comes from the prompt pass).
    SITE_WINDOWS = {"P": (True, 0, -1), "D": (False, 1, 8), "Dprime": (True, 1, 7), "E": (False, 5, 20)}

    @torch.no_grad()
    def site_generate(self, pre: Prefix, rows: list[Row], sites: list[str], dirs: dict, bands: dict, *,
                      max_new: int, readout: dict | None = None) -> dict:
        """Greedy generation (greedy_shrink) where each row carries a site window.

        Arms: "0" (none); own-coefficient arms F / N6 / N6perp (x <- x - (x.v)v); RFo / RN6o (x <- x - (x.v)u:
        the plan's random control with the displacement magnitude |x.v| of the SAME row; used at decode sites
        because an F row's trajectory diverges/terminates, so a cross-row source is undefined there);
        RF / RN6 (prompt-pass-only sites: matched displacement c taken from the F / N6 row of the same
        item/band/site in the same pass, identical to stacked_pass); POS (site P: residual patch to target).
        readout: optional per-layer [K,d] directions -> per-call projections captured into cap[R, max_new, L, K]
        (call t = input token t; t = 0 is the prompt pass); NaN where a row has finished."""
        dev = self.device
        pre = pre.to(dev)
        assert pre.S == 1, "site_generate starts from a site-P prefix"
        R = len(rows)
        win = self.SITE_WINDOWS
        L_used = sorted({l for r in rows if r.band is not None and r.arm != "0" for l in bands[r.band]})
        V = {l: torch.zeros((R, self.d)) for l in L_used}
        W = {l: torch.zeros((R, self.d)) for l in L_used}
        on = {l: torch.zeros(R) for l in L_used}
        pat = {l: torch.zeros(R, dtype=torch.bool) for l in L_used}
        src = torch.arange(R)
        src_of: dict[tuple, int] = {}
        for r, (row, s) in enumerate(zip(rows, sites)):
            if row.arm in ("F", "N6"):
                src_of.setdefault((row.item, row.band, s, row.arm), r)
        for r, (row, s) in enumerate(zip(rows, sites)):
            if row.arm == "0":
                continue
            for l in bands[row.band]:
                if row.arm in OWN_ARMS:
                    vk, wk = OWN_ARMS[row.arm]
                    V[l][r] = dirs[vk][l]
                    W[l][r] = dirs["U"][l, row.draw - 1] if wk == "U" else dirs[wk][l]
                    on[l][r] = 1.0
                elif row.arm in MATCHED_ARMS:
                    assert win[s][1] > win[s][2], "matched-source R is defined for prompt-pass-only sites"
                    key = (row.item, row.band, s, MATCHED_ARMS[row.arm])
                    assert key in src_of, f"matched row {row} has no source row in this pass"
                    src[r] = src_of[key]
                    W[l][r] = dirs["U"][l, row.draw - 1]
                    on[l][r] = 1.0
                elif row.arm == "POS":
                    assert s == "P", "POS is a site-P arm"
                    pat[l][r] = True
                else:
                    raise ValueError(f"arm {row.arm} not supported")
        V = {l: v.to(dev) for l, v in V.items()}
        W = {l: v.to(dev) for l, v in W.items()}
        tgt = {l: dirs["target"][l].to(dev) for l in L_used} if any(bool(p.any()) for p in pat.values()) else {}
        chk_arm = np.array([row.arm in ("F", "N6", "N6perp", "FperpU") for row in rows])
        at_prompt = torch.tensor([1.0 if win[s][0] else 0.0 for s in sites])
        # displacement bookkeeping by (arm|site)
        keys = sorted({f"{row.arm}|{s}" for row, s in zip(rows, sites) if row.arm != "0"})
        kidx = np.array([keys.index(f"{row.arm}|{s}") if row.arm != "0" else -1 for row, s in zip(rows, sites)])
        dsum, dcnt = np.zeros(len(keys)), np.zeros(len(keys))
        site_arr = np.array(sites)
        log = {"resid_ratio_max": 0.0, "n_edit_calls": 0, "edits_by_site_step": {}}
        K = 0 if readout is None else next(iter(readout.values())).shape[0]
        cap = torch.full((R, max_new, self.L, K), float("nan")) if readout is not None else None

        def gate_for(t: int) -> torch.Tensor:
            return torch.tensor([1.0 if win[s][1] <= t <= win[s][2] else 0.0 for s in sites])

        def make_spec(act: torch.Tensor, gate: torch.Tensor) -> Spec | None:
            g = gate[act]
            any_edit = float(g.sum()) > 0.0
            if not any_edit and readout is None:
                return None
            act_d = act.to(dev)
            ops, cdirs = {}, {}
            chk: list[int] = []
            if any_edit:
                loc = {int(a): k for k, a in enumerate(act.tolist())}
                s_loc = torch.tensor([loc.get(int(src[a]), k) for k, a in enumerate(act.tolist())],
                                     dtype=torch.long, device=dev)
                chk = [k for k, a in enumerate(act.tolist()) if chk_arm[a] and float(gate[a]) > 0]
                for l in L_used:
                    has = on[l][act] * g
                    pm = pat[l][act] & (g > 0)
                    if float(has.sum()) == 0.0 and not bool(pm.any()):
                        continue
                    ops[l] = {"V": V[l].index_select(0, act_d), "W": W[l].index_select(0, act_d), "src": s_loc,
                              "has": has.to(dev), "patch": pm.to(dev) if bool(pm.any()) else None,
                              "target": tgt.get(l) if bool(pm.any()) else None}
                    if chk:
                        idx = torch.tensor([int(act[k]) for k in chk], dtype=torch.long, device=dev)
                        cdirs[l] = V[l].index_select(0, idx) * on[l][act[chk]].to(dev)[:, None]
            return Spec(layer_ops=ops, readout=readout,
                        proj=torch.zeros((len(act), self.L, K), device=dev) if readout is not None else None,
                        check_rows=torch.tensor(chk, dtype=torch.long, device=dev) if chk else None,
                        check_dirs=cdirs)

        def book(spec: Spec | None, act: torch.Tensor, gate: torch.Tensor, t: int) -> None:
            if spec is None:
                return
            if cap is not None:
                cap[act, t] = spec.proj.cpu()
            if not spec.layer_ops:
                return
            log["n_edit_calls"] += 1
            if spec.resid_ratio:
                log["resid_ratio_max"] = max(log["resid_ratio_max"],
                                             float(torch.stack(list(spec.resid_ratio.values())).max()))
            a_np = act.numpy()
            for l, (c, dn) in spec.disp.items():
                has = (spec.layer_ops[l]["has"] > 0).cpu().numpy()
                pm = spec.layer_ops[l]["patch"]
                if pm is not None:
                    has = has | pm.cpu().numpy()
                d_np = dn[:, -1].float().cpu().numpy()
                ks = kidx[a_np[has]]
                np.add.at(dsum, ks, d_np[has])
                np.add.at(dcnt, ks, 1)
            gs = gate[act].numpy() > 0
            for s_ in np.unique(site_arr[a_np[gs]]):
                log["edits_by_site_step"].setdefault(str(s_), set()).add(t)

        item_rows = torch.tensor([r.item for r in rows], dtype=torch.long, device=dev)
        cache = self._cache_for(pre, item_rows)
        attn = torch.cat([pre.mask.index_select(0, item_rows), torch.ones((R, 1), dtype=torch.long, device=dev)],
                         dim=1)
        pos = pre.span_pos.index_select(0, item_rows)[:, 0]
        ids = pre.span_tok.index_select(0, item_rows)[:, 0]
        act = torch.arange(R)
        spec = make_spec(act, at_prompt)
        self.spec = spec
        try:
            out = self.model(input_ids=ids[:, None], attention_mask=attn, position_ids=pos[:, None],
                             past_key_values=cache, use_cache=True, logits_to_keep=1)
        finally:
            self.spec = None
        book(spec, act, at_prompt, 0)
        logits0 = out.logits[:, -1, :].float()
        nxt = logits0.argmax(-1)
        past = out.past_key_values
        del out
        res = torch.full((R, max_new), self.pad_id, dtype=torch.long)
        cur_attn, cur_pos = attn, pos
        steps = 0
        for step in range(max_new):
            nxt_c = nxt.cpu()
            res[act, step] = nxt_c
            steps = step + 1
            done = torch.isin(nxt_c, self.eos_cpu)
            if step == max_new - 1 or bool(done.all()):
                break
            if bool(done.any()):
                keep = (~done).nonzero().squeeze(1)
                keep_d = keep.to(dev)
                past.batch_select_indices(keep_d)
                act, nxt, cur_attn, cur_pos = act[keep], nxt[keep_d], cur_attn[keep_d], cur_pos[keep_d]
            cur_attn = torch.cat([cur_attn, torch.ones((cur_attn.shape[0], 1), dtype=cur_attn.dtype, device=dev)],
                                 dim=1)
            cur_pos = cur_pos + 1
            t = step + 1                       # this decode call's INPUT is generated token t
            gate = gate_for(t)
            spec = make_spec(act, gate)
            self.spec = spec
            try:
                out = self.model(input_ids=nxt[:, None], attention_mask=cur_attn, position_ids=cur_pos[:, None],
                                 past_key_values=past, use_cache=True, logits_to_keep=1)
            finally:
                self.spec = None
            book(spec, act, gate, t)
            past = out.past_key_values
            nxt = out.logits[:, -1, :].argmax(-1)
            del out
        log["edits_by_site_step"] = {k: sorted(v) for k, v in log["edits_by_site_step"].items()}
        log["mean_disp_by_arm_site"] = {k: float(dsum[i] / dcnt[i]) for i, k in enumerate(keys) if dcnt[i] > 0}
        log["n_disp_by_arm_site"] = {k: int(dcnt[i]) for i, k in enumerate(keys) if dcnt[i] > 0}
        return {"logits": logits0, "first_tok": logits0.argmax(-1), "tokens": res, "steps": steps, "log": log,
                "cap": cap}

    def decode(self, toks: torch.Tensor) -> list[str]:
        outs = []
        for row in toks.tolist():
            cut = []
            for t in row:
                if t in self.eos or t == self.pad_id:
                    break
                cut.append(t)
            outs.append(self.tok.decode(cut, skip_special_tokens=True).strip())
        return outs

    def n_new_tokens(self, toks: torch.Tensor) -> list[int]:
        out = []
        for row in toks.tolist():
            n = 0
            for t in row:
                n += 1
                if t in self.eos or t == self.pad_id:
                    break
            out.append(n)
        return out

    def free(self) -> None:
        self.remove_hooks()
        del self.model
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()


def logit_outcomes(logits: torch.Tensor, ref_ids: list[int], ctl_ids: list[int]) -> dict[str, np.ndarray]:
    """Per-row forward-only outcomes at the first response position (or after a teacher-forced span)."""
    logits = logits.float()
    dev = logits.device
    ref_t = torch.tensor(ref_ids, dtype=torch.long, device=dev)
    ctl_t = torch.tensor(ctl_ids, dtype=torch.long, device=dev)
    lse_all = torch.logsumexp(logits, dim=-1)
    lse_ref = torch.logsumexp(logits.index_select(1, ref_t), dim=-1)
    lse_ctl = torch.logsumexp(logits.index_select(1, ctl_t), dim=-1)
    tok1 = logits.argmax(-1)
    ref_set = torch.tensor(sorted(set(ref_ids)), dtype=torch.long, device=dev)
    return {"RD": (lse_ref - lse_all).cpu().numpy().astype(np.float64),
            "G1": (lse_ref - lse_ctl).cpu().numpy().astype(np.float64),
            "tok1": tok1.cpu().numpy().astype(np.int64),
            "T1ref": torch.isin(tok1, ref_set).cpu().numpy().astype(np.float64)}


def unit_np(v: np.ndarray) -> np.ndarray:
    return v / max(float(np.linalg.norm(v)), 1e-12)


def random_pool(F: np.ndarray, N6: np.ndarray, J: int, model_idx: int, seed: int) -> np.ndarray:
    """u[l, j] = unit Gaussian draw seeded (seed, model, l, j), orthogonalised against span{F_l, N6_l}."""
    L, d = F.shape
    U = np.zeros((L, J, d), np.float32)
    for l in range(L):
        Q, _ = np.linalg.qr(np.stack([F[l], N6[l]], 1).astype(np.float64))
        for j in range(J):
            g = np.random.default_rng([seed % (2 ** 32), model_idx, l, j]).standard_normal(d)
            g = g - Q @ (Q.T @ g)
            U[l, j] = unit_np(g)
    return U


def mem_ok(limit_gb: float = 14.2) -> bool:
    from common import cgroup_mem_gb
    cur = cgroup_mem_gb()[0]
    return not (cur == cur) or cur < limit_gb


def chunks_by_length(lengths: list[int], max_items: int) -> list[list[int]]:
    order = list(np.argsort(lengths, kind="mergesort"))
    return [order[i:i + max_items] for i in range(0, len(order), max_items)]


def safe_float(x) -> float:
    try:
        f = float(x)
        return f if math.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")
