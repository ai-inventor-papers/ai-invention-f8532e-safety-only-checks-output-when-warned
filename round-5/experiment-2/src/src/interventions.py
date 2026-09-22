#!/usr/bin/env python3
"""E3 -- forward-only intervention grid for the blind held-out panel (iteration 5, exp 2).

An INTERVENTION here is a set of forward hooks that modify the residual stream at the
output of every decoder block inside a band, at a SITE, and then let the forward pass
continue.  Two sites:

    P   the last prompt token only
    A   all (non-pad) prompt positions

Two kinds of edit:

    project               h <- h - (h . u) u                  (u unit; F_b or N6_b)
    matched_displacement  h <- h - |h . u_ref| * u_r          (u_r unit, GS-orthogonal to
                          BOTH F_b and N6_b, rescaled to the norm of the direction it
                          controls).  This is what makes the random controls MATCHED: the
                          displacement magnitude applied at the first modified layer is
                          exactly the one the F_b cell applies there, while the F_b
                          projection itself is (by orthogonality) untouched.  A plain
                          unit-norm random projection would displace the state by a tiny,
                          direction-dependent amount and every control would be void
                          (self-test T3d is precisely this check).

Cells:
    C1  arm0, no intervention, both sites
    C2  6 bands x {F, N6} x {P, A}                                        = 24
    C3  6 bands x --r-draws-p draws x site P, plus 3 draws x site A       = 6R + 18
    C4  cumulative band sets S1={B4} .. S6={B1..B6} x {F, N6} x site A,
        plus S1..S6 x 3 R draws                                           = 12 + 18
    C5  (flag) band ablation held DURING greedy decoding of 8 tokens

Saved per cell and nothing else:
    proj.npy    (32, L+1, K) f32       site A: (32, 2, L+1, K) = [mean-over-positions, last]
    norms.npy   (32, L+1)    f32       site A: (32, 2, L+1)
    logits.npy  (32, 3)      f32       softmax mass on WU_ref / WU_hed / WU_ctl, next token
    topk_ids.npy / topk_probs.npy (32, 20)
    full.npy    (32, L+1, d) f16       ONLY for arm0, the C2 F/N6 cells and the C4 ladder cells

BLINDNESS: no correlation, no ranking, no candidate score, no cosine between pre/post
directions.  Arrays and an index; a separate blind scorer consumes them later.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from loguru import logger

SRC = Path(__file__).resolve().parent
# SRC must win over vendor/ (both carry a common.py), so force the order.
for _p in (str(SRC / "vendor"), str(SRC)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from common import jdump, jload, utc_now  # noqa: E402
import pipeline as PL  # noqa: E402

FULL_CELL_PREFIXES = ("C1__arm0", "C2__", "C4__S")   # cells that also keep full residuals
FULL_CELL_EXCLUDE = ("__R",)                          # ...but never the random-control ones


# =========================================================================================
# hook machinery
# =========================================================================================
class Ablator:
    """Forward hooks on a chosen set of decoder blocks.

    spec maps block_index -> (u, u_ref).  u is the unit direction actually subtracted.
    u_ref is None for a projection edit, or the direction whose removed component sets the
    displacement magnitude for a matched_displacement edit.
    """

    def __init__(self, model, spec: dict[int, tuple[np.ndarray, np.ndarray | None]],
                 site: str, mode: str) -> None:
        import torch
        self.model = model
        self.site = site
        self.mode = mode
        self.handles: list[Any] = []
        self.posmask = None            # (B, T, 1) float on device, set before every forward
        self.fired = 0
        blocks = PL.get_layers(model)
        dev = next(model.parameters()).device
        self.spec_t: dict[int, tuple[Any, Any]] = {}
        for bi, (u, uref) in spec.items():
            ut = torch.as_tensor(np.asarray(u, dtype=np.float32), device=dev)
            rt = (torch.as_tensor(np.asarray(uref, dtype=np.float32), device=dev)
                  if uref is not None else None)
            self.spec_t[int(bi)] = (ut, rt)
        for bi in sorted(self.spec_t):
            if bi < 0 or bi >= len(blocks):
                raise IndexError(f"block {bi} outside 0..{len(blocks) - 1}")
            # prepend=True: transformers >= 5 records hidden_states with ITS OWN forward hook
            # (utils/output_capturing.py), installed lazily at the first output_hidden_states
            # call -- i.e. before this hook exists.  Hooks run in registration order and each
            # sees the previous hook's returned output, so without prepend the recorded
            # hidden_states would be the PRE-edit block output (caught by self-test T3b/T3d).
            self.handles.append(blocks[bi].register_forward_hook(self._make_hook(bi), prepend=True))

    # -- context ---------------------------------------------------------------------
    def set_positions(self, attn) -> None:
        """Recompute the position mask for the forward that is about to run."""
        import torch
        if attn is None:
            self.posmask = None
            return
        if self.site == "P":
            m = torch.zeros(attn.shape + (1,), dtype=torch.float32, device=attn.device)
            m[:, -1, 0] = 1.0
        else:
            m = attn.to(torch.float32).unsqueeze(-1)
        self.posmask = m

    def set_positions_all(self, batch: int, n_pos: int, device) -> None:
        """Every position selected (used for the single-token steps of a C5 decode)."""
        import torch
        self.posmask = torch.ones((batch, n_pos, 1), dtype=torch.float32, device=device)

    def _make_hook(self, bi: int) -> Callable:
        def hook(_module, _inputs, output):
            istuple = isinstance(output, (tuple, list))
            h = output[0] if istuple else output
            if not hasattr(h, "dim") or h.dim() != 3:
                return output
            u, uref = self.spec_t[bi]
            if float(u.abs().sum()) == 0.0:
                self.fired += 1                       # inert direction: fires, changes nothing
                return output
            m = self.posmask
            if m is None or m.shape[1] != h.shape[1]:
                # single-token decode step, or an unexpected length: select every position
                m = None
            hf = h.float()
            if self.mode == "project":
                delta = (hf * u).sum(-1, keepdim=True) * u
            else:
                mag = (hf * uref).sum(-1, keepdim=True).abs()
                delta = mag * u
            if m is not None:
                delta = delta * m
            new = (hf - delta).to(h.dtype)
            self.fired += 1
            if istuple:
                return (new,) + tuple(output[1:])
            return new
        return hook

    def remove(self) -> None:
        for h in self.handles:
            h.remove()
        self.handles = []

    def __enter__(self) -> "Ablator":
        return self

    def __exit__(self, *_exc) -> None:
        self.remove()


# =========================================================================================
# one forward pass over the 32 cell prompts
# =========================================================================================
def _forward_once(model, ids, attn, pos, ablator: Ablator | None):
    import torch
    if ablator is not None:
        ablator.set_positions(attn)
    kw: dict[str, Any] = {"input_ids": ids, "attention_mask": attn, "use_cache": False,
                          "output_hidden_states": True}
    with torch.no_grad():
        for extra in ({"position_ids": pos, "logits_to_keep": 1},
                      {"position_ids": pos}, {"logits_to_keep": 1}, {}):
            try:
                return model(**kw, **extra)
            except TypeError:
                continue
    raise RuntimeError("no accepted forward signature")


def _slices(out, attn, site: str):
    """(stack_last, stack_mean_or_None) as float32 [B, L+1, d]."""
    import torch
    hs = out.hidden_states
    last = torch.stack([h[:, -1, :] for h in hs], 1).float()
    mean = None
    if site == "A":
        m = attn.to(torch.float32).unsqueeze(-1)
        denom = m.sum(1).clamp_min(1.0)
        mean = torch.stack([(h.float() * m).sum(1) / denom for h in hs], 1)
    return last, mean


def _readout(out, bank_t, token_id_t: dict, topk: int):
    """proj / norms from the last-token stack, plus next-token set masses and top-k."""
    import torch
    logits = out.logits[:, -1, :].float()
    probs = torch.softmax(logits, dim=-1)
    masses = []
    for key in ("refusal", "hedge", "control"):
        idx = token_id_t.get(key)
        masses.append(probs.index_select(1, idx).sum(-1) if idx is not None and idx.numel()
                      else torch.zeros(probs.shape[0], device=probs.device))
    mass = torch.stack(masses, 1).float().cpu().numpy().astype(np.float32)
    tp, ti = torch.topk(probs, k=min(topk, probs.shape[-1]), dim=-1)
    return mass, ti.cpu().numpy().astype(np.int32), tp.float().cpu().numpy().astype(np.float32)


def run_cell(model, tok, prompts: Sequence[str], add_special: bool, ablator: Ablator | None,
             site: str, bank_t, token_id_t: dict, batch: int, want_full: bool,
             topk: int = 20) -> dict[str, np.ndarray]:
    """One intervention cell: forward, projections, norms, next-token readout.

    PADDING-FREE BY CONSTRUCTION. Prompts are grouped into exact-token-length buckets
    (pipeline.zero_pad_buckets), so no batch ever contains a pad token; results are scattered
    back to the ORIGINAL prompt order (row i <-> cells_32.json row i). Selftest T4 showed
    left-padded batches move last-token states by 10-290% relative on some architectures
    (gemma-3, pythia), which would have corrupted every cell of the grid."""
    import torch
    n = len(prompts)
    keys = ("proj", "norms", "logits", "topk_ids", "topk_probs", "full")
    out: dict[str, np.ndarray] = {}
    groups = PL.zero_pad_buckets(tok, list(prompts), PL.CFG["max_len_prompt"], add_special,
                                 max(1, batch))
    for gidx in groups:
        done = 0
        while done < len(gidx):
            rest = gidx[done:]

            def _run(bs: int, _rest=rest):
                sub = [prompts[j] for j in _rest[:bs]]
                ids, attn, pos = PL.encode_left(tok, sub, PL.CFG["max_len_prompt"], add_special)
                PL.assert_no_pad(attn)
                o = _forward_once(model, ids, attn, pos, ablator)
                last, mean = _slices(o, attn, site)
                mass, ti, tp = _readout(o, bank_t, token_id_t, topk)
                pj_last = (last @ bank_t.T).cpu().numpy().astype(np.float32)
                nm_last = last.norm(dim=-1).cpu().numpy().astype(np.float32)
                res = {"logits": mass, "topk_ids": ti, "topk_probs": tp,
                       "full": last.to(torch.float16).cpu().numpy() if want_full else None}
                if site == "A":
                    pj_mean = (mean @ bank_t.T).cpu().numpy().astype(np.float32)
                    nm_mean = mean.norm(dim=-1).cpu().numpy().astype(np.float32)
                    res["proj"] = np.stack([pj_mean, pj_last], 1)
                    res["norms"] = np.stack([nm_mean, nm_last], 1)
                else:
                    res["proj"] = pj_last
                    res["norms"] = nm_last
                res["n"] = len(sub)
                del o, last, mean
                return res

            res, _used = PL.oom_retry(_run, len(rest), what="cell forward")
            take = rest[:res["n"]]
            for k in keys:
                v = res.get(k)
                if v is None:
                    continue
                v = np.asarray(v)
                if k not in out:
                    out[k] = np.zeros((n,) + tuple(v.shape[1:]), dtype=v.dtype)
                out[k][take] = v[:len(take)]
            done += res["n"]
    return {k: out.get(k) for k in keys}


# =========================================================================================
# cell catalogue
# =========================================================================================
def band_blocks(depth: int, band_1based: int) -> list[int]:
    lo, hi = PL.band_ranges(depth, PL.CFG["n_bands"])[band_1based - 1]
    return list(range(lo, hi))


LADDER = {1: [4], 2: [4, 5], 3: [4, 5, 6], 4: [3, 4, 5, 6], 5: [2, 3, 4, 5, 6],
          6: [1, 2, 3, 4, 5, 6]}


def build_catalogue(depth: int, dirs: dict[str, np.ndarray], r_draws_p: int,
                    with_c5: bool, tier2: bool) -> list[dict]:
    """Every cell as a pure description; nothing is run here."""
    cells: list[dict] = []
    nb = PL.CFG["n_bands"]
    for site in ("P", "A"):
        cells.append({"cell_id": f"C1__arm0__{site}", "family": "C1", "site": site,
                      "mode": "none", "bands": [], "spec": {}})
    for b in range(1, nb + 1):
        blocks = band_blocks(depth, b)
        for dname, key in (("F", "dirs_F"), ("N6", "dirs_N6")):
            for site in ("P", "A"):
                cells.append({"cell_id": f"C2__b{b}__{dname}__{site}", "family": "C2",
                              "site": site, "mode": "project", "bands": [b],
                              "direction": dname,
                              "spec": {i: (dirs[key][b - 1], None) for i in blocks}})
    if tier2:
        for b in range(1, nb + 1):
            blocks = band_blocks(depth, b)
            for j in range(r_draws_p):
                cells.append({"cell_id": f"C3__b{b}__R{j + 1}__P", "family": "C3", "site": "P",
                              "mode": "matched_displacement", "bands": [b],
                              "direction": f"R{j + 1}", "matched_to": "F",
                              "spec": {i: (dirs["dirs_R"][b - 1, j], dirs["dirs_F"][b - 1])
                                       for i in blocks}})
            for j in range(min(3, r_draws_p)):
                cells.append({"cell_id": f"C3__b{b}__R{j + 1}__A", "family": "C3", "site": "A",
                              "mode": "matched_displacement", "bands": [b],
                              "direction": f"R{j + 1}", "matched_to": "F",
                              "spec": {i: (dirs["dirs_R"][b - 1, j], dirs["dirs_F"][b - 1])
                                       for i in blocks}})
        for s, bset in LADDER.items():
            spec_f: dict[int, tuple] = {}
            spec_n: dict[int, tuple] = {}
            for b in bset:
                for i in band_blocks(depth, b):
                    spec_f[i] = (dirs["dirs_F"][b - 1], None)
                    spec_n[i] = (dirs["dirs_N6"][b - 1], None)
            cells.append({"cell_id": f"C4__S{s}__F__A", "family": "C4", "site": "A",
                          "mode": "project", "bands": bset, "direction": "F", "spec": spec_f})
            cells.append({"cell_id": f"C4__S{s}__N6__A", "family": "C4", "site": "A",
                          "mode": "project", "bands": bset, "direction": "N6", "spec": spec_n})
            for j in range(min(3, r_draws_p)):
                spec_r = {}
                for b in bset:
                    for i in band_blocks(depth, b):
                        spec_r[i] = (dirs["dirs_R"][b - 1, j], dirs["dirs_F"][b - 1])
                cells.append({"cell_id": f"C4__S{s}__R{j + 1}__A", "family": "C4", "site": "A",
                              "mode": "matched_displacement", "bands": bset,
                              "direction": f"R{j + 1}", "matched_to": "F", "spec": spec_r})
    if with_c5:
        cells.append({"cell_id": "C5__arm0__dec", "family": "C5", "site": "A", "mode": "none",
                      "bands": [], "spec": {}})
        for b in range(1, nb + 1):
            blocks = band_blocks(depth, b)
            for dname, key in (("F", "dirs_F"), ("N6", "dirs_N6")):
                cells.append({"cell_id": f"C5__b{b}__{dname}__dec", "family": "C5", "site": "A",
                              "mode": "project", "bands": [b], "direction": dname,
                              "spec": {i: (dirs[key][b - 1], None) for i in blocks}})
    return cells


def wants_full(cell_id: str) -> bool:
    if any(x in cell_id for x in FULL_CELL_EXCLUDE):
        return False
    return cell_id.startswith(FULL_CELL_PREFIXES)


# =========================================================================================
# C5 -- ablation held during greedy decoding
# =========================================================================================
def run_cell_decode(model, tok, prompts: Sequence[str], add_special: bool,
                    ablator: Ablator | None, bank_t, token_id_t: dict, n_new: int,
                    batch: int) -> dict[str, np.ndarray]:
    """dec_proj (N, n_new, L+1, K) and dec_logits (N, n_new, 3): the ablation is HELD at
    every generated position as well as over the prompt."""
    import torch
    n = len(prompts)
    proj_all: list[np.ndarray] = []
    logit_all: list[np.ndarray] = []
    i = 0
    b = max(1, batch)
    while i < n:
        chunk = list(prompts[i:i + b])

        def _run(bs: int, _chunk=chunk):
            sub = _chunk[:bs]
            ids, attn, pos = PL.encode_left(tok, sub, PL.CFG["max_len_prompt"], add_special)
            if ablator is not None:
                ablator.set_positions(attn)
            with torch.no_grad():
                try:
                    out = model(input_ids=ids, attention_mask=attn, position_ids=pos,
                                use_cache=True, output_hidden_states=True, logits_to_keep=1)
                except TypeError:
                    out = model(input_ids=ids, attention_mask=attn, use_cache=True,
                                output_hidden_states=True)
                past = out.past_key_values
                nxt = out.logits[:, -1, :].argmax(-1)
                bb = ids.shape[0]
                cur_attn, cur_pos = attn, pos[:, -1]
                pj, lg = [], []
                for _k in range(n_new):
                    cur_attn = torch.cat([cur_attn, torch.ones((bb, 1), dtype=cur_attn.dtype,
                                                               device=cur_attn.device)], 1)
                    cur_pos = cur_pos + 1
                    if ablator is not None:
                        ablator.set_positions_all(bb, 1, ids.device)
                    try:
                        o = model(input_ids=nxt[:, None], attention_mask=cur_attn,
                                  position_ids=cur_pos[:, None], past_key_values=past,
                                  use_cache=True, output_hidden_states=True)
                    except TypeError:
                        o = model(input_ids=nxt[:, None], attention_mask=cur_attn,
                                  past_key_values=past, use_cache=True, output_hidden_states=True)
                    st = torch.stack([h[:, -1, :] for h in o.hidden_states], 1).float()
                    pj.append((st @ bank_t.T).cpu().numpy().astype(np.float32))
                    mass, _, _ = _readout(o, bank_t, token_id_t, 5)
                    lg.append(mass)
                    past = o.past_key_values
                    nxt = o.logits[:, -1, :].argmax(-1)
                return {"proj": np.stack(pj, 1), "logits": np.stack(lg, 1), "n": bb}
        res, used = PL.oom_retry(_run, b, what="C5 decode")
        proj_all.append(res["proj"])
        logit_all.append(res["logits"])
        i += res["n"]
        b = used
    return {"dec_proj": np.concatenate(proj_all, 0), "dec_logits": np.concatenate(logit_all, 0)}


# =========================================================================================
# the grid
# =========================================================================================
def _load_dirs(out_dir: Path) -> dict[str, np.ndarray]:
    return {k: np.load(out_dir / f"{k}.npy")
            for k in ("dirs_F", "dirs_N6", "dirs_R", "bank_R")}


def _prompts_for(tok, c32: dict) -> tuple[list[str], bool]:
    rendered = [PL.render_one(tok, r["text"]) for r in c32["rows"]]
    return [r[0] for r in rendered], rendered[0][2]


def _token_id_tensors(token_ids: dict, device):
    import torch
    out = {}
    for k in ("refusal", "hedge", "control"):
        ids = token_ids.get(k) or []
        out[k] = torch.tensor(ids, dtype=torch.long, device=device) if ids else None
    return out


def run_grid(model, tok, out_dir: Path, depth: int, c32: dict, token_ids: dict,
             add_special: bool, *, r_draws_p: int = 5, with_c5: bool = False,
             tier2: bool = False, batch: int = 16, max_cells: int | None = None) -> dict:
    """Run every catalogued cell and write arrays/<tag>/cells/<cell_id>/."""
    import torch
    dirs = _load_dirs(out_dir)
    bank, bank_names = PL.projection_bank(out_dir)
    dev = next(model.parameters()).device
    bank_t = torch.as_tensor(bank, device=dev)
    token_id_t = _token_id_tensors(token_ids, dev)
    prompts, add_sp = _prompts_for(tok, c32)
    if add_special != add_sp:
        add_special = add_sp
    cells = build_catalogue(depth, dirs, r_draws_p, with_c5, tier2)
    if max_cells:
        cells = cells[:max_cells]
    cdir = out_dir / "cells"
    cdir.mkdir(parents=True, exist_ok=True)
    index: list[dict] = []
    per_cell_s: list[float] = []
    logger.info(f"E3 grid: {len(cells)} cells, K={bank.shape[0]} bank directions, "
                f"{len(prompts)} prompts")
    for ci, cell in enumerate(cells):
        t0 = time.time()
        d = cdir / cell["cell_id"]
        d.mkdir(parents=True, exist_ok=True)
        ab = None
        try:
            if cell["spec"]:
                ab = Ablator(model, cell["spec"], cell["site"], cell["mode"])
            if cell["family"] == "C5":
                res = run_cell_decode(model, tok, prompts, add_special, ab, bank_t,
                                      token_id_t, PL.CFG["dec_new"], batch)
                PL.atomic_npy(d / "dec_proj.npy", res["dec_proj"])
                PL.atomic_npy(d / "dec_logits.npy", res["dec_logits"])
            else:
                res = run_cell(model, tok, prompts, add_special, ab, cell["site"], bank_t,
                               token_id_t, batch, wants_full(cell["cell_id"]), PL.CFG["topk"])
                PL.atomic_npy(d / "proj.npy", res["proj"])
                PL.atomic_npy(d / "norms.npy", res["norms"])
                PL.atomic_npy(d / "logits.npy", res["logits"])
                PL.atomic_npy(d / "topk_ids.npy", res["topk_ids"])
                PL.atomic_npy(d / "topk_probs.npy", res["topk_probs"])
                if res.get("full") is not None:
                    PL.atomic_npy(d / "full.npy", res["full"])
        finally:
            if ab is not None:
                ab.remove()
        dt = time.time() - t0
        per_cell_s.append(dt)
        index.append({"cell_id": cell["cell_id"], "family": cell["family"], "site": cell["site"],
                      "mode": cell["mode"], "bands": cell["bands"],
                      "direction": cell.get("direction"), "matched_to": cell.get("matched_to"),
                      "blocks": sorted(cell["spec"].keys()), "seconds": dt,
                      "full_saved": bool(wants_full(cell["cell_id"]) and cell["family"] != "C5")})
        if (ci + 1) % 10 == 0 or ci == len(cells) - 1:
            logger.info(f"  cells {ci + 1}/{len(cells)} ({np.mean(per_cell_s):.2f} s/cell)")
    stats = {"n_cells": len(cells), "bank_names": bank_names, "bank_K": int(bank.shape[0]),
             "n_prompts": len(prompts), "cells_32_sha256": c32["ids_sha256"],
             "mean_seconds_per_cell": float(np.mean(per_cell_s)) if per_cell_s else 0.0,
             "total_seconds": float(np.sum(per_cell_s)),
             "proj_slices": {"P": ["last_token"], "A": ["mean_over_positions", "last_token"]},
             "topk_files": ["topk_ids.npy", "topk_probs.npy"],
             "utc": utc_now()}
    jdump(cdir / "index.json", {"cells": index, **stats})
    jdump(out_dir / "bank_index.json",
          {"names": bank_names, "K": int(bank.shape[0]),
           "order": "6 x F_b, then 6 x N6_b, then 3 fixed R (band-independent)"})
    return stats


# =========================================================================================
# SELF-TESTS T3a - T3d
# =========================================================================================
def _stack_for(model, tok, prompts, add_special, ablator, batch):
    """[N, L+1, d] float32 last-token residuals under one (possibly None) ablator."""
    import torch
    outs = []
    i = 0
    b = max(1, batch)
    while i < len(prompts):
        chunk = list(prompts[i:i + b])

        def _run(bs: int, _chunk=chunk):
            sub = _chunk[:bs]
            ids, attn, pos = PL.encode_left(tok, sub, PL.CFG["max_len_prompt"], add_special)
            out = _forward_once(model, ids, attn, pos, ablator)
            st = torch.stack([h[:, -1, :] for h in out.hidden_states], 1).float().cpu().numpy()
            del out
            return {"st": st, "n": len(sub)}
        res, used = PL.oom_retry(_run, b, what="selftest stack")
        outs.append(res["st"])
        i += res["n"]
        b = used
    return np.concatenate(outs, 0)


def selftests_t3(model, tok, out_dir: Path, depth: int, c32: dict, token_ids: dict,
                 add_special: bool, batch: int = 16) -> dict:
    """T3a identity, T3b ablation effectiveness, T3c control inertness, T3d displacement
    matching.  Numbers, not adjectives."""
    import torch
    dirs = _load_dirs(out_dir)
    bank, bank_names = PL.projection_bank(out_dir)
    prompts, add_sp = _prompts_for(tok, c32)
    add_special = add_sp
    res: dict[str, Any] = {"n_prompts": len(prompts), "depth": depth,
                           "bank_K": int(bank.shape[0])}

    # ---------------- T3a ARM-0 IDENTITY ----------------------------------------------
    arm0 = _stack_for(model, tok, prompts, add_special, None, batch)
    proj_arm0 = arm0 @ bank.T
    stim = jload(PL.ASSETS / "stimuli.json")["rows"]
    pos_of = {r["stim_id"]: i for i, r in enumerate(stim)}
    rows = [pos_of[i] for i in c32["ids"]]
    a_prompt = np.load(out_dir / "A_prompt.npy", mmap_mode="r")
    proj_harv = a_prompt[rows].astype(np.float32) @ bank.T
    den = np.abs(proj_harv).max() + 1e-12
    abs_d = float(np.abs(proj_arm0 - proj_harv).max())
    rel_d = float((np.abs(proj_arm0 - proj_harv) / den).max())
    # a hook that is registered but carries a zero direction must change NOTHING
    inert = {i: (np.zeros(arm0.shape[2], dtype=np.float32), None) for i in range(min(4, depth))}
    ab = Ablator(model, inert, "P", "project")
    try:
        arm0_inert = _stack_for(model, tok, prompts, add_special, ab, batch)
    finally:
        fired = ab.fired
        ab.remove()
    # The grid's OWN code path for the arm-0 cell (zero-pad bucketing, scatter back to
    # cells_32 order, readout) must reproduce a plain hook-free forward on the SAME prompts.
    dev = next(model.parameters()).device
    bank_t = torch.as_tensor(bank, device=dev)
    token_id_t = _token_id_tensors(token_ids, dev)
    cell0 = run_cell(model, tok, prompts, add_special, None, "P", bank_t, token_id_t, batch,
                     False, PL.CFG["topk"])
    proj_plain_last = (arm0 @ bank.T)                     # [N, L+1, K] from the plain forward
    den_g = float(np.abs(proj_plain_last).max() + 1e-12)
    rel_g = float((np.abs(cell0["proj"] - proj_plain_last) / den_g).max())
    ok_a = rel_g < 1e-3 and np.array_equal(arm0, arm0_inert)
    res["T3a"] = {
        "max_rel_diff_grid_arm0_vs_plain_forward": rel_g,
        "proj_scale": den_g,
        "inert_hooks_fired": int(fired),
        "inert_hook_bitwise_identical": bool(np.array_equal(arm0, arm0_inert)),
        "inert_hook_max_abs_diff": float(np.abs(arm0 - arm0_inert).max()),
        "threshold": 1e-3,
        "verdict": "PASS" if ok_a else "FAIL",
        "context_max_rel_diff_vs_stored_A_prompt": rel_d,
        "context_max_abs_diff_vs_stored_A_prompt": abs_d,
        "note": ("VERDICT legs: (1) the grid's arm-0 cell, through run_cell's bucketing and "
                 "scatter, reproduces a plain hook-free forward on the same 32 prompts; (2) a "
                 "registered hook carrying a zero direction changes nothing, bitwise. The "
                 "comparison against the STORED f16 A_prompt is context only: it is exact "
                 "only when that file was produced by the current batch-1 harvest code."),
    }

    # ---------------- band under test: the middle band B4 ------------------------------
    b_test = 4
    lo, hi = PL.band_ranges(depth, PL.CFG["n_bands"])[b_test - 1]
    inside = list(range(lo + 1, min(hi, depth - 1) + 1)) or [hi]
    u_f = dirs["dirs_F"][b_test - 1]
    blocks = list(range(lo, hi))

    def stack_with(spec, site, mode):
        ab_ = Ablator(model, spec, site, mode)
        try:
            return _stack_for(model, tok, prompts, add_special, ab_, batch)
        finally:
            ab_.remove()

    # ---------------- T3b ABLATION EFFECTIVENESS --------------------------------------
    st_f = stack_with({i: (u_f, None) for i in blocks}, "P", "project")
    p0 = np.abs(arm0[:, inside, :] @ u_f)
    pf = np.abs(st_f[:, inside, :] @ u_f)
    ratio_b = float(pf.mean() / (p0.mean() + 1e-12))
    res["T3b"] = {"band": b_test, "blocks": blocks, "hidden_indices_checked": inside,
                  "mean_abs_proj_arm0": float(p0.mean()),
                  "mean_abs_proj_ablated": float(pf.mean()),
                  "ratio": ratio_b, "threshold": 1e-2,
                  "verdict": "PASS" if ratio_b < 1e-2 else "FAIL"}

    # ---------------- T3c CONTROL INERTNESS -------------------------------------------
    u_r = dirs["dirs_R"][b_test - 1, 0]
    st_r = stack_with({i: (u_r, u_f) for i in blocks}, "P", "matched_displacement")
    first_c = lo + 1                      # first modified hidden index (same incoming state)
    p0_first = np.abs(arm0[:, first_c, :] @ u_f)
    pr_first = np.abs(st_r[:, first_c, :] @ u_f)
    ratio_c = float(pr_first.mean() / (p0_first.mean() + 1e-12))
    pr_band = np.abs(st_r[:, inside, :] @ u_f)
    res["T3c"] = {"band": b_test, "r_draw": 1, "first_modified_hidden_index": first_c,
                  "mean_abs_proj_arm0_first": float(p0_first.mean()),
                  "mean_abs_proj_control_first": float(pr_first.mean()),
                  "ratio": ratio_c, "deviation_pct": abs(ratio_c - 1.0) * 100.0,
                  "control_norm": float(np.linalg.norm(u_r)),
                  "orthogonality_to_F": float(abs(u_r @ u_f)),
                  "threshold_pct": 1.0,
                  "verdict": "PASS" if abs(ratio_c - 1.0) <= 0.01 else "FAIL",
                  "context_band_mean_ratio": float(pr_band.mean() / (p0.mean() + 1e-12)),
                  "note": ("At the first modified layer a matched-displacement R edit moves the "
                           "state only along r_hat, which is orthogonal to f_hat, so the F "
                           "projection must be unchanged (exact up to float). Later in-band "
                           "layers legitimately respond nonlinearly to the displaced state; "
                           "that band-mean drift is reported as context, not as the verdict.")}

    # ---------------- T3d DISPLACEMENT MATCHING ---------------------------------------
    first = lo + 1                       # the FIRST modified hidden index: both cells share
    dsp_f = np.linalg.norm(st_f[:, first, :] - arm0[:, first, :], axis=-1)   # the same input
    dsp_r = np.linalg.norm(st_r[:, first, :] - arm0[:, first, :], axis=-1)   # there
    ratio_d = float(dsp_r.mean() / (dsp_f.mean() + 1e-12))
    acc_f = np.linalg.norm(st_f[:, inside[-1], :] - arm0[:, inside[-1], :], axis=-1)
    acc_r = np.linalg.norm(st_r[:, inside[-1], :] - arm0[:, inside[-1], :], axis=-1)
    res["T3d"] = {"first_modified_hidden_index": first,
                  "mean_displacement_F": float(dsp_f.mean()),
                  "mean_displacement_R": float(dsp_r.mean()),
                  "ratio_at_first_modified_index": ratio_d,
                  "deviation_pct": abs(ratio_d - 1.0) * 100.0,
                  "accumulated_index": inside[-1],
                  "mean_accumulated_displacement_F": float(acc_f.mean()),
                  "mean_accumulated_displacement_R": float(acc_r.mean()),
                  "accumulated_ratio": float(acc_r.mean() / (acc_f.mean() + 1e-12)),
                  "threshold_pct": 5.0,
                  "verdict": "PASS" if abs(ratio_d - 1.0) <= 0.05 else "FAIL",
                  "note": "the matching is DEFINED at the first modified layer, where the F "
                          "and R cells still see the same incoming state; the accumulated "
                          "figure at the end of the band is reported for context only."}
    res["verdict"] = ("PASS" if all(res[k]["verdict"] == "PASS" for k in ("T3a", "T3b", "T3c", "T3d"))
                      else "FAIL")
    return res


if __name__ == "__main__":  # pragma: no cover - the driver is pipeline.py
    print(__doc__)
