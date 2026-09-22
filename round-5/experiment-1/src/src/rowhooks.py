#!/usr/bin/env python3
"""Per-ROW batched interventions for the Tier-B pass.

Every forward batch holds ONE prompt repeated over B rows (no padding at all), each row carrying its own
intervention configuration. Row 0 is (by convention of the caller) the unperturbed baseline, so every
contrast's baseline lives in the SAME forward batch as its intervened rows (unit test T11 lesson).

Per block j (hidden-state index j+1) the hook applies, in fp32 and cast back:
    project : h <- h - M_j * (h . V_j) D_j        (V_j (B,d) unit or zero; D_j = V_j or r _|_ V_j)
    patch   : h_last <- h_last + pm * (P_j - h_last)
and then CAPTURES the post-intervention last-token state (same hook => capture always sees the intervened
activation). A zero row in V_j / pm is an exact no-op (bf16 -> fp32 -> bf16 round trip is lossless).
Index convention (T10 / amendment A1): 0 = embeddings, i (1..L-1) = output of block i-1,
L = final_norm(output of last block).
Lesion (W8): y <- y - (y . u_row) u_row on every attention-out / MLP-out projection, per row (zero = no-op).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np
import torch

from interv import HookedRunner, lesion_module_names


@dataclass
class RowCfg:
    # list of (hidden_idx_list, v (d,), dvec (d,) or None, site in {'last','all','from_last'})
    proj: list = field(default_factory=list)
    # {hidden_idx: target (d,)} applied at the last token
    patch: dict = field(default_factory=dict)
    lesion_u: np.ndarray | None = None


class RowRunner:
    def __init__(self, model: Any, tok: Any, *, device: str = "cuda", max_rows: int = 16,
                 max_len: int = 192) -> None:
        pad_side = getattr(tok, "padding_side", "right")
        self.hr = HookedRunner(model, tok, device=device, batch_size=max_rows, max_len=max_len)
        tok.padding_side = pad_side      # HookedRunner forces left; we never pad, keep the default
        self.model, self.tok, self.device = model, tok, device
        self.L, self.d = self.hr.n_layers, self.hr.hidden
        self.blocks, self.embed, self.fnorm = self.hr._blocks, self.hr._embed, self.hr._final_norm
        self.max_rows = int(max_rows)
        self.max_len = int(max_len)
        try:
            self.lesion_names = lesion_module_names(model, self.blocks[0])
        except Exception as exc:  # noqa: BLE001 - NotSupported
            self.lesion_names = None
            self.lesion_err = repr(exc)
        self.cur: dict | None = None
        self.mdtype = next(model.parameters()).dtype

    def encode(self, text: str) -> list[int]:
        enc = self.tok(text, add_special_tokens=False, truncation=True, max_length=self.max_len)
        return list(enc["input_ids"])

    # ------------------------------------------------------------------ hooks
    def _block_hook(self, j: int):
        def hook(_m, _inp, out):  # noqa: ANN001, ANN202
            c = self.cur
            is_tuple = isinstance(out, tuple)
            h = out[0] if is_tuple else out
            ent = c["blk"].get(j)
            pat = c["pat"].get(j)
            hnew = None
            if ent is not None or pat is not None:
                hf = h.float()
                if ent is not None:
                    V, D, M = ent
                    coeff = torch.einsum("btd,bd->bt", hf, V) * M
                    delta = coeff.unsqueeze(-1) * D.unsqueeze(1)
                    hn0 = torch.linalg.norm(hf[:, -1, :], dim=-1).clamp_min(1e-9)
                    hf = hf - delta
                    c["stats"][j] = (torch.linalg.norm(delta[:, -1, :], dim=-1) / hn0,
                                     torch.linalg.norm(hf[:, -1, :], dim=-1))
                if pat is not None:
                    P, pm = pat
                    last = hf[:, -1, :]
                    hf = hf.clone()
                    hf[:, -1, :] = last + pm.unsqueeze(-1) * (P - last)
                hnew = hf.to(h.dtype)
            hh = hnew if hnew is not None else h
            c["cap"][j + 1] = hh[:, -1, :].float()
            c["raw"][j] = torch.linalg.norm(hh[:, -1, :].float(), dim=-1)
            if hnew is None:
                return out
            return (hnew,) + tuple(out[1:]) if is_tuple else hnew
        return hook

    def _embed_hook(self, _m, _inp, out):  # noqa: ANN001, ANN202
        h = out[0] if isinstance(out, tuple) else out
        self.cur["cap"][0] = h[:, -1, :].float()

    def _norm_hook(self, _m, _inp, out):  # noqa: ANN001, ANN202
        h = out[0] if isinstance(out, tuple) else out
        self.cur["norm"] = h[:, -1, :].float()

    def _lesion_hook(self, _m, _inp, out):  # noqa: ANN001, ANN202
        U = self.cur.get("LU")
        if U is None:
            return out
        is_tuple = isinstance(out, tuple)
        y = out[0] if is_tuple else out
        yf = y.float()
        yf = yf - torch.einsum("btd,bd->bt", yf, U).unsqueeze(-1) * U.unsqueeze(1)
        yn = yf.to(y.dtype)
        return (yn,) + tuple(out[1:]) if is_tuple else yn

    def _install(self, with_lesion: bool) -> list:
        hs = [self.embed.register_forward_hook(self._embed_hook)]
        for j, blk in enumerate(self.blocks):
            hs.append(blk.register_forward_hook(self._block_hook(j)))
        if self.fnorm is not None:
            hs.append(self.fnorm.register_forward_hook(self._norm_hook))
        if with_lesion:
            if self.lesion_names is None:
                raise RuntimeError("lesion not supported: " + self.lesion_err)
            for blk in self.blocks:
                for name, mod in blk.named_modules():
                    if name and name.split(".")[-1] in self.lesion_names:
                        hs.append(mod.register_forward_hook(self._lesion_hook))
        return hs

    # ------------------------------------------------------------------ batch construction
    def _build(self, cfgs: Sequence[RowCfg], T: int, from_idx: int) -> dict:
        B, d, dev = len(cfgs), self.d, self.device
        blk: dict[int, list] = {}
        pat: dict[int, list] = {}
        for r, cf in enumerate(cfgs):
            for (idxs, v, dv, site) in cf.proj:
                v = np.asarray(v, dtype=np.float64)
                nv = np.linalg.norm(v)
                if nv <= 0:
                    continue
                v = v / nv
                dv = v if dv is None else np.asarray(dv, dtype=np.float64) / np.linalg.norm(dv)
                for idx in idxs:
                    j = idx - 1
                    if j not in blk:
                        blk[j] = [np.zeros((B, d), np.float32), np.zeros((B, d), np.float32),
                                  np.zeros((B, T), np.float32)]
                    if np.any(blk[j][0][r]):
                        raise ValueError("two projections on the same row/block")
                    blk[j][0][r] = v
                    blk[j][1][r] = dv
                    if site == "last":
                        blk[j][2][r, T - 1] = 1.0
                    elif site == "all":
                        blk[j][2][r, :] = 1.0
                    elif site == "from_last":
                        blk[j][2][r, from_idx:] = 1.0
                    else:
                        raise ValueError(site)
            for idx, tgt in cf.patch.items():
                j = idx - 1
                if j not in pat:
                    pat[j] = [np.zeros((B, d), np.float32), np.zeros((B,), np.float32)]
                pat[j][0][r] = np.asarray(tgt, np.float32)
                pat[j][1][r] = 1.0
        tt = lambda a: torch.as_tensor(a, device=dev)  # noqa: E731
        out = {"blk": {j: (tt(a[0]), tt(a[1]), tt(a[2])) for j, a in blk.items()},
               "pat": {j: (tt(a[0]), tt(a[1])) for j, a in pat.items()},
               "cap": [None] * (self.L + 1), "raw": [None] * self.L, "norm": None, "stats": {}}
        if any(cf.lesion_u is not None for cf in cfgs):
            U = np.zeros((B, d), np.float32)
            for r, cf in enumerate(cfgs):
                if cf.lesion_u is not None:
                    u = np.asarray(cf.lesion_u, np.float64)
                    U[r] = u / np.linalg.norm(u)
            out["LU"] = tt(U)
        return out

    def _collect(self) -> dict:
        c = self.cur
        seq = list(c["cap"][: self.L]) + [c["norm"] if c["norm"] is not None else c["cap"][self.L]]
        X = torch.stack(seq, dim=1).cpu().numpy().astype(np.float32)     # (B, L+1, d)
        raw = torch.stack(c["raw"], dim=1).cpu().numpy()                    # (B, L) raw block-out norms
        st = {j: (a.cpu().numpy(), b.cpu().numpy()) for j, (a, b) in c["stats"].items()}
        return {"X": X, "raw": raw, "stats": st}

    # ------------------------------------------------------------------ public
    @torch.no_grad()
    def run(self, ids: Sequence[int], cfgs: Sequence[RowCfg], *, want_logits: bool = False) -> dict:
        """One prompt, many configs. Returns X (n_cfg, L+1, d), raw (n_cfg, L), stats {block: (ratio, newnorm)}."""
        outs: list[dict] = []
        bs = self.max_rows
        i = 0
        while i < len(cfgs):
            chunk = list(cfgs[i: i + bs])
            try:
                o = self._run_chunk(ids, chunk, want_logits)
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache()
                if bs == 1:
                    raise
                bs = max(1, bs // 2)
                self.max_rows = bs
                continue
            outs.append(o)
            i += len(chunk)
        res = {"X": np.concatenate([o["X"] for o in outs]), "raw": np.concatenate([o["raw"] for o in outs])}
        st: dict[int, list] = {}
        n0 = 0
        for o in outs:
            nb = o["X"].shape[0]
            for j, (a, b) in o["stats"].items():
                if j not in st:
                    st[j] = [np.full(len(cfgs), np.nan), np.full(len(cfgs), np.nan)]
                st[j][0][n0:n0 + nb] = a
                st[j][1][n0:n0 + nb] = b
            n0 += nb
        res["stats"] = st
        if want_logits:
            res["logits"] = np.concatenate([o["logits"] for o in outs])
        return res

    def _run_chunk(self, ids, cfgs, want_logits):
        T = len(ids)
        inp = torch.tensor([list(ids)] * len(cfgs), device=self.device)
        self.cur = self._build(cfgs, T, T - 1)
        hs = self._install("LU" in self.cur)
        try:
            res = self.model(input_ids=inp, attention_mask=torch.ones_like(inp), use_cache=False, logits_to_keep=1)
            o = self._collect()
            if want_logits:
                o["logits"] = res.logits[:, -1, :].float().cpu().numpy()
        finally:
            for h in hs:
                h.remove()
            self.cur = None
        return o

    @torch.no_grad()
    def decode(self, ids: Sequence[int], cfgs: Sequence[RowCfg], n_new: int = 8) -> dict:
        """Greedy decode n_new tokens for every row (no KV cache, no padding: all rows share the prompt length
        and grow by one token per step). 'from_last' masks = the last PROMPT token and every later position.
        Returns X (n_cfg, n_new, L+1, d) read at the last position of each step's forward (step 0 = last prompt
        token, step t = t-th generated token) and tok (n_cfg, n_new) generated ids."""
        assert len(cfgs) <= self.max_rows
        T0 = len(ids)
        cur_ids = torch.tensor([list(ids)] * len(cfgs), device=self.device)
        Xs, toks = [], []
        for _t in range(n_new):
            T = cur_ids.shape[1]
            self.cur = self._build(cfgs, T, T0 - 1)
            hs = self._install("LU" in self.cur)
            try:
                res = self.model(input_ids=cur_ids, attention_mask=torch.ones_like(cur_ids), use_cache=False,
                                 logits_to_keep=1)
                o = self._collect()
            finally:
                for h in hs:
                    h.remove()
                self.cur = None
            nxt = res.logits[:, -1, :].argmax(-1, keepdim=True)
            Xs.append(o["X"])
            toks.append(nxt.cpu().numpy()[:, 0])
            cur_ids = torch.cat([cur_ids, nxt], dim=1)
            del res
        return {"X": np.stack(Xs, axis=1), "tok": np.stack(toks, axis=1)}


def selftest(model, tok, text: str, n_layers: int) -> dict:
    """Per-row batching == single-config HookedRunner (within bf16 tolerance); T1/T2 semantics exact."""
    from core import band_indices
    from interv import Intervention, orthogonal_random
    rr = RowRunner(model, tok)
    ids = rr.encode(text)
    rng = np.random.default_rng(0)
    v = rng.standard_normal(rr.d)
    v /= np.linalg.norm(v)
    r = orthogonal_random(v, rng=rng)
    lo, hi = band_indices(n_layers, 3)
    idxs = list(range(lo, hi + 1))
    cfgs = [RowCfg(), RowCfg(proj=[(idxs, v, None, "last")]), RowCfg(proj=[(idxs, v, r, "last")]),
            RowCfg(proj=[(idxs, v, None, "all")])]
    out = rr.run(ids, cfgs)
    hr = rr.hr
    hr.tok.padding_side = "left"
    ref = []
    for cf, site, rep in ((None, None, None), (1, "last", None), (1, "last", r), (1, "all", None)):
        ivs = None if cf is None else [Intervention(lo=lo, hi=hi, v=v, site=site, repl=rep)]
        X1, _ = hr.hidden_last([text], interventions=ivs)
        ref.append(X1[0])
    rr.tok.padding_side = "right"
    rel = [float(np.median(np.linalg.norm(out["X"][k] - ref[k], axis=-1) /
                           np.maximum(np.linalg.norm(ref[k], axis=-1), 1e-9))) for k in range(4)]
    # delta agreement: (intervened - baseline) per engine, compared across engines
    drel = []
    for k in (1, 2, 3):
        a = out["X"][k][hi:] - out["X"][0][hi:]
        b = ref[k][hi:] - ref[0][hi:]
        drel.append(float(np.linalg.norm(a - b) / max(np.linalg.norm(b), 1e-9)))
    # T1: after projection the captured state at hi has (h.v) ~ 0 ; T2: R displacement norm == |h.v|
    dot_after = float(abs(out["X"][1][hi] @ v))
    base_dot = float(abs(out["X"][0][hi] @ v))
    ratio_F = out["stats"][hi - 1][0][1]
    ratio_R = out["stats"][hi - 1][0][2]
    return {"median_rel_err_vs_HookedRunner": rel, "delta_rel_err_vs_HookedRunner_from_hi": drel, "T1_dot_after_at_hi": dot_after, "baseline_dot_at_hi": base_dot,
            "disp_ratio_F_equals_R_first_block": [float(out["stats"][lo - 1][0][1]), float(out["stats"][lo - 1][0][2])],
            "disp_ratio_F_R_last_block": [float(ratio_F), float(ratio_R)],
            "note": "row 0 (unhooked) differs from batch-1 by the bf16 batch-shape effect (T11 ~2%)",
            "PASS": bool(max(rel) < 3e-2 and dot_after < 0.05 * max(base_dot, 1e-6) + 0.05)}
