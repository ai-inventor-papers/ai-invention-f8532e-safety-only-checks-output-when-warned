#!/usr/bin/env python3
"""Two-tier activation harvest engine.

TIER 1 -- mean-pooled residual vectors (float16) per (request, layer, pool).  Keeps the
full hidden geometry, so every direction refit, shuffled-label null, band search,
split-half and probe baseline is recomputable OFFLINE with no second GPU pass.

TIER 2 -- per-position scalar projections onto r_content and K seeded random directions,
for every continuation position and every layer.  This is what produces the genuine
layer-by-position maps and the EARLY-vs-LATE curve that pooling destroys.

Nothing is generated: every continuation is a pre-written, teacher-forced prefix.
"""

from __future__ import annotations

import gc
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np
import torch
from loguru import logger

POOLS: tuple[str, ...] = ("early", "late", "harc32", "prompt")


@dataclass
class Req:
    """One teacher-forced forward pass."""
    key: str
    prompt_ids: list[int]
    prefix_ids: list[int] = field(default_factory=list)
    group: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def ids(self) -> list[int]:
        return self.prompt_ids + self.prefix_ids

    @property
    def plen(self) -> int:
        return len(self.prompt_ids)

    @property
    def flen(self) -> int:
        return len(self.prefix_ids)


def seeded_random_dirs(n_layers: int, d_model: int, k: int, seed: int) -> np.ndarray:
    """(n_layers, k, d_model) unit-norm Gaussian directions, identical in index across checkpoints."""
    rng = np.random.default_rng(seed)
    g = rng.standard_normal((n_layers, k, d_model)).astype(np.float32)
    g /= np.linalg.norm(g, axis=-1, keepdims=True)
    return g


def _window_idx(plen: int, flen: int, pool: str, win: dict[str, tuple[int, int]]) -> list[int]:
    if pool == "prompt":
        return [plen - 1]
    lo, hi = win[pool]
    hi = min(hi, flen - 1)
    if hi < lo:
        return [plen + flen - 1]
    return [plen + j for j in range(lo, hi + 1)]


class Harvester:
    """Runs batched teacher-forced forward passes and extracts tier-1/tier-2 readouts."""

    def __init__(
        self,
        model,
        *,
        windows: dict[str, tuple[int, int]],
        device: torch.device,
        batch_size: int = 8,
        pad_id: int = 0,
        refusal_ids: Sequence[int] = (),
        compliance_ids: Sequence[int] = (),
    ) -> None:
        self.model = model
        self.windows = windows
        self.device = device
        self.bs = batch_size
        self.pad_id = pad_id
        self.refusal_ids = list(refusal_ids)
        self.compliance_ids = list(compliance_ids)
        cfg = model.config
        self.n_layers = cfg.num_hidden_layers
        self.n_hs = cfg.num_hidden_layers + 1  # embeddings + every block
        self.d_model = cfg.hidden_size

    # -- core ---------------------------------------------------------------
    def run(
        self,
        reqs: Sequence[Req],
        *,
        pools: Sequence[str] = POOLS,
        need_logits: bool = False,
        tier2_dirs: np.ndarray | None = None,
        tier2_npos: int = 0,
        progress_every: int = 40,
    ) -> dict[str, Any]:
        """Returns dict with 'keys', 'vecs' {pool: (N, n_hs, D) fp16}, 'scalars', 'proj'."""
        n = len(reqs)
        order = sorted(range(n), key=lambda i: len(reqs[i].ids))
        vecs = {p: np.zeros((n, self.n_hs, self.d_model), dtype=np.float16) for p in pools}
        resid_norm = np.zeros((n, self.n_hs), dtype=np.float32)
        nll = np.full(n, np.nan, dtype=np.float32)
        logit_gap = np.full(n, np.nan, dtype=np.float32)
        logit_gap_post = np.full(n, np.nan, dtype=np.float32)
        proj = None
        if tier2_dirs is not None and tier2_npos > 0:
            proj = np.zeros((n, self.n_hs, tier2_npos, tier2_dirs.shape[1]), dtype=np.float32)
            dirs_t = torch.from_numpy(tier2_dirs).to(self.device)
        bs = self.bs
        i = 0
        t0 = time.time()
        done = 0
        while i < n:
            chunk = order[i:i + bs]
            try:
                self._run_batch(reqs, chunk, pools, vecs, resid_norm, nll, logit_gap,
                                logit_gap_post, proj, dirs_t if proj is not None else None,
                                need_logits, tier2_npos)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if bs == 1:
                    raise
                bs = max(1, bs // 2)
                logger.warning(f"CUDA OOM -> halving batch size to {bs}")
                continue
            i += len(chunk)
            done += len(chunk)
            if progress_every and done % progress_every < len(chunk):
                rate = done / max(1e-6, time.time() - t0)
                logger.debug(f"  harvest {done}/{n} ({rate:.1f} seq/s)")
        return {
            "keys": [r.key for r in reqs],
            "groups": [r.group for r in reqs],
            "vecs": vecs,
            "resid_norm": resid_norm,
            "nll": nll,
            "logit_gap": logit_gap,
            "logit_gap_post": logit_gap_post,
            "proj": proj,
            "secs": round(time.time() - t0, 1),
        }

    def _run_batch(self, reqs, chunk, pools, vecs, resid_norm, nll, logit_gap,
                   logit_gap_post, proj, dirs_t, need_logits, tier2_npos) -> None:
        batch = [reqs[j] for j in chunk]
        maxlen = max(len(r.ids) for r in batch)
        input_ids = torch.full((len(batch), maxlen), self.pad_id, dtype=torch.long)
        attn = torch.zeros((len(batch), maxlen), dtype=torch.long)
        for b, r in enumerate(batch):
            ids = r.ids
            input_ids[b, :len(ids)] = torch.tensor(ids, dtype=torch.long)
            attn[b, :len(ids)] = 1
        input_ids = input_ids.to(self.device)
        attn = attn.to(self.device)
        with torch.no_grad():
            out = self.model(input_ids=input_ids, attention_mask=attn,
                             output_hidden_states=True, use_cache=False)
        hs = out.hidden_states
        if len(hs) != self.n_hs:
            raise RuntimeError(f"hidden_states has {len(hs)} entries, expected {self.n_hs}")

        bidx = torch.arange(len(batch), device=self.device).unsqueeze(1)
        # ---- tier 1 pooled vectors + residual norms
        pos_by_pool = {}
        for pool in pools:
            idxs = [_window_idx(r.plen, r.flen, pool, self.windows) for r in batch]
            width = max(len(x) for x in idxs)
            pad_to = torch.zeros((len(batch), width), dtype=torch.long)
            mask = torch.zeros((len(batch), width), dtype=torch.float32)
            for b, x in enumerate(idxs):
                pad_to[b, :len(x)] = torch.tensor(x, dtype=torch.long)
                mask[b, :len(x)] = 1.0
            pos_by_pool[pool] = (pad_to.to(self.device), mask.to(self.device))

        # Accumulate every layer on the GPU and transfer ONCE per pool: a per-layer
        # .cpu() call here costs ~150 device syncs per batch and dominates runtime.
        acc: dict[str, list] = {p: [] for p in pools}
        # residual norms are read off the primary window when it is present, else off
        # whichever pool this pass does collect (prompt-only passes have no EARLY window)
        norm_pool = "early" if "early" in pools else pools[0]
        nrm_acc: list = []
        proj_acc: list = []
        pidx_t2 = None
        if proj is not None:
            pidx_t2 = torch.stack([
                torch.arange(r.plen, r.plen + tier2_npos, device=self.device).clamp(max=len(r.ids) - 1)
                for r in batch])
        for L in range(self.n_hs):
            h = hs[L]
            if h.device != self.device:          # accelerate CPU-offload puts some blocks elsewhere
                h = h.to(self.device)
            for pool in pools:
                pidx, pmask = pos_by_pool[pool]
                g = h[bidx, pidx].float()                       # (B, P, D)
                m = pmask.unsqueeze(-1)
                acc[pool].append((g * m).sum(1) / m.sum(1).clamp(min=1.0))
                if pool == norm_pool:
                    nrm_acc.append((g.norm(dim=-1) * pmask).sum(1) / pmask.sum(1).clamp(min=1.0))
            if proj is not None:
                g = h[bidx, pidx_t2].float()                    # (B, npos, D)
                proj_acc.append(torch.einsum("bpd,kd->bpk", g, dirs_t[L]))
        for pool in pools:
            arr = torch.stack(acc[pool], 0).to(torch.float16).cpu().numpy()   # (n_hs, B, D)
            for b, j in enumerate(chunk):
                vecs[pool][j] = arr[:, b]
        if nrm_acc:
            nrm = torch.stack(nrm_acc, 0).float().cpu().numpy()                # (n_hs, B)
            for b, j in enumerate(chunk):
                resid_norm[j] = nrm[:, b]
        if proj is not None:
            pr = torch.stack(proj_acc, 0).float().cpu().numpy()               # (n_hs, B, npos, K)
            for b, j in enumerate(chunk):
                proj[j] = pr[:, b]
        del acc, nrm_acc, proj_acc

        # ---- logit-side covariates (BASELINES, never the deliverable)
        if need_logits:
            # Slice per sequence rather than materialising log_softmax over the whole batch:
            # (B, T, 152k) in fp32 is ~1 GB for bs=4, versus ~50 MB for one sequence's span.
            ref_t = torch.tensor(self.refusal_ids, device=self.device) if self.refusal_ids else None
            com_t = torch.tensor(self.compliance_ids, device=self.device) if self.compliance_ids else None
            for b, j in enumerate(chunk):
                r = batch[b]
                lo_p = r.plen - 1
                hi_p = r.plen + r.flen if r.flen > 0 else r.plen
                span = out.logits[b, lo_p:hi_p].to(self.device).float()   # (flen+1, V)
                if ref_t is not None and com_t is not None:
                    pr0 = torch.softmax(span[0], dim=-1)
                    logit_gap[j] = float(pr0[ref_t].sum() - pr0[com_t].sum())
                    if r.flen > 0:
                        prN = torch.softmax(span[-1], dim=-1)
                        logit_gap_post[j] = float(prN[ref_t].sum() - prN[com_t].sum())
                if r.flen > 0:
                    lp = torch.log_softmax(span[:-1], dim=-1)
                    tgt = torch.tensor(r.prefix_ids, device=self.device)
                    nll[j] = float(lp.gather(1, tgt.unsqueeze(1)).mean())
                    del lp
                del span
        del out, hs, input_ids, attn
        # NOTE: no empty_cache() here on purpose -- it is called ~240 times per checkpoint
        # in the hot path and each call synchronises and frees the whole caching allocator.
        # It is called only on the OOM path, where it is actually needed.


# ---------------------------------------------------------------------------
# Direction fitting (done in-memory during the checkpoint's residency)
# ---------------------------------------------------------------------------

def fit_diff_in_means(vecs: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """(N, n_hs, D) float16 + boolean labels -> (n_hs, D) unit directions (positive = True class)."""
    v = vecs.astype(np.float32)
    mu_pos = v[labels].mean(axis=0)
    mu_neg = v[~labels].mean(axis=0)
    d = mu_pos - mu_neg
    nrm = np.linalg.norm(d, axis=-1, keepdims=True)
    nrm[nrm == 0] = 1.0
    return d / nrm


def save_npz(path: Path, **arrays) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def layernorm_gains(model) -> np.ndarray:
    """Mean LayerNorm/RMSNorm weight per layer, read straight from the weights."""
    gains = []
    base = getattr(model, "model", model)
    for lyr in base.layers:
        vals = []
        for nm in ("input_layernorm", "post_attention_layernorm"):
            mod = getattr(lyr, nm, None)
            if mod is not None and hasattr(mod, "weight"):
                vals.append(float(mod.weight.detach().float().mean()))
        gains.append(float(np.mean(vals)) if vals else float("nan"))
    return np.asarray(gains, dtype=np.float32)


def _spectral_norm(W: torch.Tensor, iters: int = 40, seed: int = 0) -> float:
    """Largest singular value by power iteration on W^T W.

    A full SVD of a 2560x9728 matrix, 72 of them per checkpoint, costs minutes; this costs
    milliseconds and is accurate to well under 1% after 40 iterations for these matrices.
    """
    g = torch.Generator(device=W.device).manual_seed(seed)
    v = torch.randn(W.shape[1], device=W.device, dtype=W.dtype, generator=g)
    v = v / v.norm()
    for _ in range(iters):
        u = W @ v
        nu = u.norm()
        if nu == 0:
            return 0.0
        u = u / nu
        v = W.T @ u
        nv = v.norm()
        if nv == 0:
            return 0.0
        v = v / nv
    return float((W @ v).norm())


def stable_ranks(model) -> dict[str, np.ndarray]:
    """K3's weight twin: stable rank ||W||_F^2 / ||W||_2^2 of down_proj and o_proj per layer.

    Computed from the weights alone -- no parent model, no prompts, no forward pass.
    """
    out: dict[str, list[float]] = {"down_proj": [], "o_proj": []}
    base = getattr(model, "model", model)
    for li, lyr in enumerate(base.layers):
        for nm, mod in (("down_proj", lyr.mlp.down_proj), ("o_proj", lyr.self_attn.o_proj)):
            W = mod.weight.detach().float()
            fro2 = float((W * W).sum())
            spec2 = _spectral_norm(W, seed=li) ** 2
            out[nm].append(fro2 / max(spec2, 1e-12))
            del W
    return {k: np.asarray(v, dtype=np.float32) for k, v in out.items()}


__all__ = [
    "Req", "Harvester", "POOLS", "seeded_random_dirs", "fit_diff_in_means",
    "save_npz", "layernorm_gains", "stable_ranks",
]
