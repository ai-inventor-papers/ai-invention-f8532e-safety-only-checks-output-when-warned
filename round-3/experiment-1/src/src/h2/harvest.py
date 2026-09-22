"""THE HARVEST KERNEL -- one pass per checkpoint (design decision D1).

Each checkpoint is loaded ONCE and reduced to a small set of SUFFICIENT STATISTICS on
disk.  After that every candidate, every baseline, all shuffled-label null draws, the
random-direction unit and the whole prompt-budget curve are pure offline NumPy.

Four sub-harvests, all in the same model load:
  P-HARVEST  prompt-only last-token hidden states + per-layer logit-lens refusal drives
  W-SUMMARY  per-layer Gram of the stacked residual-write matrices + singular spectrum
  U-SUMMARY  unembedding rows for the token sets, vocab mean and second moment
  C-HARVEST  teacher-forced continuations: window-pooled states + per-position deltas

Structurally derived from iteration-1 Lane A's `lane_a/harvest.py` (length-sorted
batching, OOM halving, window pooling) and Lane C's `lc_harvest.py` (forced dtype,
single-device placement), re-expressed for a CPU-only box.
"""

from __future__ import annotations

import gc
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import HARVEST, RESULTS, jdump, jload, save_npy_split, slug  # noqa: E402
from loguru import logger  # noqa: E402

DTYPE_MAP: dict[str, Any] = {}


def _torch():
    import torch

    if not DTYPE_MAP:
        DTYPE_MAP.update({"float32": torch.float32, "bfloat16": torch.bfloat16,
                          "float16": torch.float16})
    return torch


# ----------------------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------------------
def render_prompt(tok, text: str, mode: str = "chat") -> str:
    """Render one request with THAT model's own chat template, assistant turn opened.

    mode == 'plain' is the base-model protocol (3.1): the same text in plain completion
    format.  Base models are harvested BOTH ways and both are reported.
    """
    if mode == "plain":
        return text
    tmpl = getattr(tok, "chat_template", None)
    if not tmpl:
        return text
    try:
        return tok.apply_chat_template(
            [{"role": "user", "content": text}],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )
    except TypeError:
        return tok.apply_chat_template(
            [{"role": "user", "content": text}], tokenize=False, add_generation_prompt=True
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"chat template failed ({exc}); falling back to plain")
        return text


def encode_batch(tok, texts: Sequence[str], max_len: int):
    torch = _torch()
    enc = tok(
        list(texts),
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=max_len,
        add_special_tokens=False,
    )
    return enc["input_ids"], enc["attention_mask"]


# ----------------------------------------------------------------------------------
# P-HARVEST
# ----------------------------------------------------------------------------------
def p_harvest(
    model,
    tok,
    texts: Sequence[str],
    *,
    max_len: int,
    batch_size: int,
    token_ids: dict[str, list[int]],
    lens_chunk: int = 8,
    progress_every: int = 64,
) -> dict[str, np.ndarray]:
    """Last-prompt-token hidden states at every layer + per-layer logit-lens drives.

    Returns A [N, L+1, d] float16, norms [N, L+1] float32, and r_ref/r_hedge/r_ctrl
    [N, L+1] float32 (logsumexp over the token set minus logsumexp over the full vocab).
    """
    torch = _torch()
    _t_p0 = time.time()
    N = len(texts)
    order = np.argsort([len(t) for t in texts], kind="mergesort")  # length-sorted batching
    A_out: np.ndarray | None = None
    nrm_out: np.ndarray | None = None
    r_out: dict[str, np.ndarray] = {}
    W_U, final_norm = _lens_parts(model)
    sets = {k: torch.tensor(v, dtype=torch.long) for k, v in token_ids.items() if v}

    bs = int(batch_size)
    i = 0
    while i < N:
        idx = order[i : i + bs]
        try:
            ids, mask = encode_batch(tok, [texts[j] for j in idx], max_len)
            with torch.no_grad():
                out = model(input_ids=ids, attention_mask=mask, output_hidden_states=True,
                            use_cache=False)
            hs = out.hidden_states                      # tuple of (L+1) [b, T, d]
            last = mask.sum(dim=1) - 1                  # right-padding -> last real token
            b = ids.shape[0]
            L1 = len(hs)
            d = hs[0].shape[-1]
            if A_out is None:
                A_out = np.zeros((N, L1, d), dtype=np.float16)
                nrm_out = np.zeros((N, L1), dtype=np.float32)
                for k in list(sets) + ["fullV_final"]:
                    r_out[k] = np.zeros((N, L1), dtype=np.float32)
            stack = torch.stack(
                [hs[l][torch.arange(b), last, :] for l in range(L1)], dim=1
            ).float()                                    # [b, L1, d]
            A_out[idx] = stack.to(torch.float16).numpy()
            nrm_out[idx] = stack.norm(dim=-1).numpy()
            if sets:
                drv = _logit_lens_drives(stack, W_U, final_norm, sets, lens_chunk)
                for k, v in drv.items():
                    r_out[k][idx] = v
            del out, hs, stack
            i += bs
            if progress_every and (i // max(bs, 1)) % max(1, progress_every // max(bs, 1)) == 0:
                logger.info(f"    P-harvest {min(i, N)}/{N} prompts "
                            f"({(time.time() - _t_p0):.0f}s)")
        except (torch.OutOfMemoryError, RuntimeError, MemoryError) as exc:  # noqa: PERF203
            if bs > 1 and ("memory" in str(exc).lower() or isinstance(exc, MemoryError)):
                bs = max(1, bs // 2)
                logger.warning(f"P-harvest OOM -> batch_size={bs}")
                gc.collect()
                continue
            raise
    res = {"A": A_out, "norms": nrm_out}
    res.update({f"r_{k}": v for k, v in r_out.items()})
    return res


def _lens_parts(model):
    """(W_U, final_norm_module) handling tied embeddings."""
    torch = _torch()
    head = getattr(model, "lm_head", None)
    if head is not None and getattr(head, "weight", None) is not None:
        W_U = head.weight
    else:
        W_U = model.get_input_embeddings().weight
    inner = getattr(model, "model", model)
    fn = getattr(inner, "norm", None) or getattr(inner, "final_layernorm", None) \
        or getattr(inner, "embedding_norm", None)  # PATCHED (iter3): LFM2 names its FINAL norm embedding_norm
    return W_U, fn


def _logit_lens_drives(stack, W_U, final_norm, sets: dict, chunk: int) -> dict[str, np.ndarray]:
    """Per-layer logit-lens drive for each token set, as a LOG-SUM-EXP over that set only.

    The plan's form is  logsumexp(set) - logsumexp(full vocab).  Every downstream use is a
    DIFFERENCE between two sets at the same layer and item --
        X8:  (r_ref - r_ctrl) for harmful minus the same for benign
        BL1: (r_ref - r_ctrl) for harmful minus the same for benign
    -- so the full-vocab denominator CANCELS EXACTLY and never enters any reported number.
    Computing it per layer would cost a [chunk, 151936] logit tensor at every one of L+1
    layers, which on this CPU-only box is ~20% of the whole harvest for a term that is
    algebraically guaranteed to cancel.  We therefore compute the set-wise log-sum-exps
    directly from the token-set rows of W_U, and additionally store the true full-vocab
    denominator at the FINAL layer only, so a normalised BL1 can still be reported.

    Returned arrays are therefore  logsumexp over the set  (not yet minus the denominator),
    plus 'r_fullV_final' holding logsumexp over the whole vocab at the last layer.
    """
    torch = _torch()
    b, L1, d = stack.shape
    out = {k: np.zeros((b, L1), dtype=np.float32) for k in sets}
    out["fullV_final"] = np.zeros((b, L1), dtype=np.float32)
    with torch.no_grad():
        rows = {k: W_U.detach().index_select(0, ids).float() for k, ids in sets.items()}
        for l in range(L1):
            h = stack[:, l, :]
            if final_norm is not None:
                try:
                    h = final_norm(h.to(W_U.dtype)).float()
                except Exception:  # noqa: BLE001
                    pass
            for k, R in rows.items():
                out[k][:, l] = torch.logsumexp(h @ R.T, dim=-1).numpy()
            if l == L1 - 1:
                Wf = W_U.detach().float()
                for s in range(0, b, chunk):
                    z = h[s : s + chunk] @ Wf.T
                    out["fullV_final"][s : s + chunk, l] = torch.logsumexp(z, dim=-1).numpy()
                    del z
    return out


# ----------------------------------------------------------------------------------
# W-SUMMARY  (zero prompts; serves X2 and X10 and all their nulls)
# ----------------------------------------------------------------------------------
def w_summary(model, out_dir: Path, *, store_gram: bool = True,
              gram_dtype: str = "float16") -> dict:
    """Per layer: G = M M^T for M = [o_proj | down_proj], plus the singular spectrum and
    the near-null left singular vector, for the stacked matrix AND each part separately.

    sigma(M) = sqrt(eig(G)) and vmin = the eigenvector of the smallest eigenvalue, so ONE
    Gram serves both X2 and X10 (design decision D2).
    """
    torch = _torch()
    inner = getattr(model, "model", model)
    layers = inner.layers
    L = len(layers)
    meta: dict[str, Any] = {"n_layers": L, "parts": {}}
    gdir = out_dir / "gram"
    gdir.mkdir(parents=True, exist_ok=True)

    for part in ("stacked", "o_proj", "down_proj"):
        svals, vmins, fro2s, shapes = [], [], [], []
        for li in range(L):
            lyr = layers[li]
            with torch.no_grad():
                Wo = lyr.self_attn.o_proj.weight.detach().float()
                Wd = lyr.mlp.down_proj.weight.detach().float()
                M = {"stacked": lambda: torch.cat([Wo, Wd], dim=1),
                     "o_proj": lambda: Wo, "down_proj": lambda: Wd}[part]()
                d, n = int(M.shape[0]), int(M.shape[1])
                G = (M @ M.T).double()
                fro2 = float(torch.diagonal(G).sum().item())
                ev, V = torch.linalg.eigh(G)
                ev = torch.clamp(ev, min=0.0)
                sv = torch.sqrt(ev).flip(0).float().numpy()      # descending
                vmin = V[:, 0].float().numpy()
                if store_gram and part == "stacked":
                    np.save(gdir / f"G_{li:03d}.npy",
                            G.to(DTYPE_MAP[gram_dtype] if gram_dtype != "float32"
                                 else torch.float32).numpy())
                del G, ev, V, M, Wo, Wd
            svals.append(sv.astype(np.float32))
            vmins.append(vmin.astype(np.float32))
            fro2s.append(fro2)
            shapes.append([d, n])
        np.save(out_dir / f"svals_{part}.npy", np.stack(svals))
        np.save(out_dir / f"vmin_{part}.npy", np.stack(vmins))
        meta["parts"][part] = {"fro2": fro2s, "shapes": shapes}
        gc.collect()
    return meta


# ----------------------------------------------------------------------------------
# U-SUMMARY  (unembedding; serves X3 and its nulls, closed form)
# ----------------------------------------------------------------------------------
def u_summary(model, out_dir: Path, token_ids: dict[str, list[int]],
              hbar: np.ndarray, hbar_all: np.ndarray, rms_eps: float) -> dict:
    torch = _torch()
    W_U, final_norm = _lens_parts(model)
    with torch.no_grad():
        Wb = W_U.detach()
        V, d = int(Wb.shape[0]), int(Wb.shape[1])
        for key, name in (("refusal", "WU_ref"), ("hedge", "WU_hed"), ("control", "WU_ctl")):
            ids = [i for i in (token_ids.get(key) or []) if 0 <= i < V]
            rows = (Wb.index_select(0, torch.tensor(ids, dtype=torch.long)).float().numpy()
                    if ids else np.zeros((0, d), dtype=np.float32))
            np.save(out_dir / f"{name}.npy", rows.astype(np.float32))
        # Accumulate mu_U and S_U = W_U^T W_U in ROW CHUNKS. Materialising a float32 copy of
        # a [151936, 2560] bfloat16 unembedding costs ~1.6 GB on top of an already-resident
        # 8 GB model, which is what OOM-killed this sweep once inside a ~15 GB cgroup.
        # Chunking holds the peak to ~100 MB and is numerically identical up to summation
        # order (the accumulators are float64).
        chunk = 8192
        mu = torch.zeros(d, dtype=torch.float64)
        # PATCHED (iter3): S_U = W_U^T W_U is NOT accumulated -- it is read only by iteration-2's X3, which is
        # neither a C1-C14 candidate nor a bar here, and it costs ~1 TFLOP per checkpoint on this CPU box.
        for i in range(0, V, chunk):
            blk = Wb[i : i + chunk].float()
            mu += blk.sum(dim=0).double()
            del blk
        np.save(out_dir / "mu_U.npy", (mu / V).numpy().astype(np.float32))
        del mu
        gamma = getattr(final_norm, "weight", None)
        g = gamma.detach().float().numpy() if gamma is not None else np.ones(d, dtype=np.float32)
        np.save(out_dir / "gamma.npy", g.astype(np.float32))
    np.save(out_dir / "hbar.npy", np.asarray(hbar, dtype=np.float32))
    np.save(out_dir / "hbar_all.npy", np.asarray(hbar_all, dtype=np.float32))
    return {"vocab_size": V, "hidden_size": d, "rms_eps": float(rms_eps),
            "tie_word_embeddings": bool(getattr(model.config, "tie_word_embeddings", False))}


# ----------------------------------------------------------------------------------
# C-HARVEST  (teacher-forced continuations; serves X5, X11 and the response-site rows)
# ----------------------------------------------------------------------------------
def c_harvest(
    model,
    tok,
    cells: list[dict],
    *,
    max_len: int,
    batch_size: int,
    early: tuple[int, int],
    late: tuple[int, int],
    x5_cell_index: Sequence[int],
    x5_positions: int,
) -> dict:
    """One forward pass per cell over prompt+continuation, no generation.

    Window offsets are RE-DERIVED from the cell TEXT per tokenizer (3.4 / fallback 6):
    the prompt is tokenised alone to get its length, windows are prompt-relative, and a
    cell whose action slot no longer intersects both windows is DROPPED and recorded.
    """
    torch = _torch()
    _t_c0 = time.time()
    n = len(cells)
    A_resp: np.ndarray | None = None
    D_resp: np.ndarray | None = None
    kept = np.zeros(n, dtype=bool)
    slot_ok = np.zeros(n, dtype=bool)
    x5_set = {int(c): k for k, c in enumerate(x5_cell_index)}

    bs = int(batch_size)
    i = 0
    while i < n:
        sel = list(range(i, min(i + bs, n)))
        try:
            prompts = [cells[j]["prompt_text"] for j in sel]
            fulls = [cells[j]["full_text"] for j in sel]
            plens = [len(tok(p, add_special_tokens=False)["input_ids"]) for p in prompts]
            ids, mask = encode_batch(tok, fulls, max_len)
            with torch.no_grad():
                out = model(input_ids=ids, attention_mask=mask, output_hidden_states=True,
                            use_cache=False)
            hs = out.hidden_states
            L1, d = len(hs), hs[0].shape[-1]
            if A_resp is None:
                A_resp = np.zeros((n, L1, 2, d), dtype=np.float16)
                if x5_set:
                    D_resp = np.zeros((len(x5_set), L1 - 1, x5_positions, d), dtype=np.float16)
            H = torch.stack(hs, dim=1).float()            # [b, L1, T, d]
            flens = mask.sum(dim=1).tolist()
            for bi, j in enumerate(sel):
                pl, fl = int(plens[bi]), int(flens[bi])
                cont = fl - pl
                if cont <= 2:
                    continue
                e0, e1 = pl + early[0], pl + min(early[1], cont)
                l0, l1 = pl + late[0], pl + min(late[1], cont)
                if e1 <= e0:
                    continue
                spans = cells[j].get("action_slot_spans") or []
                slot_ok[j] = bool(spans) and any(
                    (s < min(early[1], cont) and e >= early[0]) for s, e in spans
                ) and any((s < min(late[1], cont) and e >= late[0]) for s, e in spans)
                A_resp[j, :, 0, :] = H[bi, :, e0:e1, :].mean(dim=1).to(torch.float16).numpy()
                if l1 > l0:
                    A_resp[j, :, 1, :] = H[bi, :, l0:l1, :].mean(dim=1).to(torch.float16).numpy()
                else:
                    A_resp[j, :, 1, :] = A_resp[j, :, 0, :]
                kept[j] = True
                if j in x5_set and D_resp is not None:
                    p_end = min(pl + x5_positions, fl)
                    npos = p_end - pl
                    if npos > 0:
                        blk = H[bi, :, pl:p_end, :]                 # [L1, npos, d]
                        D_resp[x5_set[j], :, :npos, :] = (
                            (blk[1:] - blk[:-1]).to(torch.float16).numpy()
                        )
            del out, hs, H
            i += bs
            logger.info(f"    C-harvest {min(i, n)}/{n} cells ({(time.time() - _t_c0):.0f}s)")
        except (torch.OutOfMemoryError, RuntimeError, MemoryError) as exc:  # noqa: PERF203
            if bs > 1 and ("memory" in str(exc).lower() or isinstance(exc, MemoryError)):
                bs = max(1, bs // 2)
                logger.warning(f"C-harvest OOM -> batch_size={bs}")
                gc.collect()
                continue
            raise
    return {"A_resp": A_resp, "D_resp": D_resp, "kept": kept, "slot_ok": slot_ok}


# ----------------------------------------------------------------------------------
# the per-checkpoint driver
# ----------------------------------------------------------------------------------
def harvest_one(
    repo: str,
    cfg: dict,
    stimuli: list[dict],
    cells: list[dict] | None,
    *,
    template_mode: str = "chat",
    tag: str | None = None,
    random_init: bool = False,
    do_c_harvest: bool = True,
    do_w_summary: bool = False,
) -> dict:
    """Load once, write sufficient statistics, delete. Resumable via a DONE sentinel."""
    torch = _torch()
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    name = tag or slug(repo)
    out_dir = HARVEST / name
    out_dir.mkdir(parents=True, exist_ok=True)
    done = out_dir / "DONE"
    if done.exists():
        logger.info(f"SKIP {name} (DONE)")
        return jload(out_dir / "meta.json")

    t0 = time.time()
    dtype = DTYPE_MAP.get(cfg["dtype"], torch.bfloat16) if DTYPE_MAP else None
    if dtype is None:
        _torch()
        dtype = DTYPE_MAP.get(cfg["dtype"], torch.bfloat16)

    tok = AutoTokenizer.from_pretrained(repo, trust_remote_code=False)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token or tok.unk_token
    tok.padding_side = "right"

    if random_init:
        conf = AutoConfig.from_pretrained(repo)
        model = AutoModelForCausalLM.from_config(conf, torch_dtype=dtype)
    else:
        # output_loading_info records MISSING / UNEXPECTED tensor names: a checkpoint whose
        # weights do not bind (e.g. an optimum-quanto FP8 upload with no quantization_config)
        # silently runs with randomly initialised layers, and that must be visible.
        model, load_info = AutoModelForCausalLM.from_pretrained(
            repo, dtype=dtype, low_cpu_mem_usage=True,
            attn_implementation=cfg.get("attn", "sdpa"), output_loading_info=True,
        )
    model.eval()
    model.to("cpu")
    t_load = time.time() - t0

    conf = model.config
    meta: dict[str, Any] = {
        "repo": repo, "tag": name, "template_mode": template_mode,
        "random_init": bool(random_init),
        "n_layers": int(conf.num_hidden_layers), "hidden_size": int(conf.hidden_size),
        "vocab_size": int(getattr(conf, "vocab_size", 0)),
        "tie_word_embeddings": bool(getattr(conf, "tie_word_embeddings", False)),
        "dtype_loaded": str(dtype), "dtype_config": str(getattr(conf, "torch_dtype", None)),
        "rms_eps": float(getattr(conf, "rms_norm_eps", 1e-6)),
        "t_load_s": t_load, "timings": {},
    }
    if not random_init:
        li = load_info if isinstance(load_info, dict) else {}
        miss = list(li.get("missing_keys", []) or [])
        unexp = list(li.get("unexpected_keys", []) or [])
        meta["load_missing_keys_n"] = len(miss)
        meta["load_unexpected_keys_n"] = len(unexp)
        meta["load_missing_keys_head"] = [str(k) for k in miss[:12]]
        meta["load_unexpected_keys_head"] = [str(k) for k in unexp[:12]]
        meta["weights_fully_bound"] = bool(len(miss) == 0)
        if miss:
            logger.warning(f"{repo}: {len(miss)} MISSING tensors at load (random init) "
                           f"e.g. {miss[:3]}")

    token_ids = _encode_token_sets(tok, cfg["token_sets"])
    meta["token_ids"] = {k: len(v) for k, v in token_ids.items()}
    jdump(token_ids, out_dir / "token_ids.json")

    # ---- P-HARVEST
    t = time.time()
    texts = [render_prompt(tok, s["text"], template_mode) for s in stimuli]
    ph = p_harvest(model, tok, texts, max_len=cfg["max_len_prompt"],
                   batch_size=cfg["batch_prompt"], token_ids=token_ids,
                   lens_chunk=cfg.get("lens_chunk", 8))
    np.save(out_dir / "A_prompt.npy", ph["A"])
    np.save(out_dir / "norms.npy", ph["norms"])
    for k in ("r_refusal", "r_hedge", "r_control", "r_fullV_final"):
        if k in ph:
            np.save(out_dir / f"{k}.npy", ph[k])
    meta["timings"]["p_harvest_s"] = time.time() - t
    meta["n_prompts"] = len(stimuli)
    meta["prompt_token_lengths"] = _tok_len_stats(tok, texts, cfg["max_len_prompt"])

    y = np.array([s["y"] for s in stimuli], dtype=np.int8)
    L1 = ph["A"].shape[1]
    hbar = ph["A"][y == 1, L1 - 1, :].astype(np.float32).mean(0)
    hbar_all = ph["A"][:, L1 - 1, :].astype(np.float32).mean(0)

    # ---- U-SUMMARY
    t = time.time()
    meta.update(u_summary(model, out_dir, token_ids, hbar, hbar_all, meta["rms_eps"]))
    meta["timings"]["u_summary_s"] = time.time() - t

    # ---- C-HARVEST
    if do_c_harvest and cells:
        t = time.time()
        ch = c_harvest(
            model, tok, cells, max_len=cfg["max_len_cell"], batch_size=cfg["batch_cell"],
            early=tuple(cfg["early_window"]), late=tuple(cfg["late_window"]),
            x5_cell_index=cfg["x5_cell_index"], x5_positions=cfg["x5_positions"],
        )
        np.save(out_dir / "A_resp.npy", ch["A_resp"])
        if ch["D_resp"] is not None:
            # per-position tensor is 120-300 MB: stored as parts below GitHub's 100 MiB limit
            save_npy_split(ch["D_resp"], out_dir, "D_resp")
        np.save(out_dir / "cell_kept.npy", ch["kept"])
        np.save(out_dir / "cell_slot_ok.npy", ch["slot_ok"])
        meta["timings"]["c_harvest_s"] = time.time() - t
        meta["n_cells"] = len(cells)
        meta["n_cells_kept"] = int(ch["kept"].sum())
        meta["n_cells_slot_ok"] = int(ch["slot_ok"].sum())
        meta["cell_drop_frac"] = float(1.0 - ch["kept"].mean())
        meta["x5_undefined"] = bool(meta["cell_drop_frac"] > 0.20)
    else:
        meta["n_cells"] = 0
        meta["x5_undefined"] = True

    # ---- W-SUMMARY
    if do_w_summary:
        t = time.time()
        meta["w"] = w_summary(model, out_dir, store_gram=cfg.get("store_gram", True),
                              gram_dtype=cfg.get("gram_dtype", "float16"))
        meta["timings"]["w_summary_s"] = time.time() - t

    meta["timings"]["total_s"] = time.time() - t0
    jdump(meta, out_dir / "meta.json")
    done.write_text(json.dumps({"ts": time.time(), "total_s": meta["timings"]["total_s"]}))

    del model, tok, ph
    gc.collect()
    logger.info(f"HARVESTED {name} in {meta['timings']['total_s']:.1f}s "
                f"(load {t_load:.1f}s, P {meta['timings'].get('p_harvest_s', 0):.1f}s, "
                f"C {meta['timings'].get('c_harvest_s', 0):.1f}s, "
                f"W {meta['timings'].get('w_summary_s', 0):.1f}s)")
    return meta


def _encode_token_sets(tok, token_sets: dict[str, list[str]]) -> dict[str, list[int]]:
    """Encode every set PER TOKENIZER; a string whose first subword is unstable is still
    stored (the caller reports cross-tokenizer disagreement in the output)."""
    out: dict[str, list[int]] = {}
    for key, strings in token_sets.items():
        ids: list[int] = []
        for s in strings:
            enc = tok(s, add_special_tokens=False)["input_ids"]
            if enc:
                ids.append(int(enc[0]))
        out[key] = sorted(set(ids))
    return out


def _tok_len_stats(tok, texts: Sequence[str], max_len: int) -> dict:
    lens = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in texts[: min(64, len(texts))]]
    return {"mean": float(np.mean(lens)), "p50": float(np.median(lens)),
            "p95": float(np.quantile(lens, 0.95)), "max": int(np.max(lens)),
            "truncation_cap": int(max_len)}
