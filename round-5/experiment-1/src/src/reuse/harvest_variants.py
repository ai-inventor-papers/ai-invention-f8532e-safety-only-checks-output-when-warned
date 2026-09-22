#!/usr/bin/env python3
"""PHASE C -- ACTIVATION HARVEST of the constructed arms, ONLY after behaviour truth and pair classification are
hash-committed (logs/chain.jsonl: prereg < graded_truth < classification; every sha re-verified, else exit 2).

Kernels are the iteration-2 ones copied verbatim into src_i3/h2/ (p_harvest, u_summary, _encode_token_sets), so the
arrays share the iteration-2/3 layout and conventions (last real prompt token, right padding, length-sorted batches of
8, max_len 192, fp16 storage, logit-lens logsumexp over the token sets with the final norm re-applied):
  A_prompt, norms, r_refusal, r_hedge, r_control, r_fullV_final   (256 H2 stimuli, the arm's own render_fn)
  WU_ref, WU_hed, WU_ctl, mu_U, gamma, hbar, hbar_all             (u_summary)
  A_c11                                                           (64 PKU severity items, prompt only)
NEW passes: A_dec / A_dec_tok1 / dec_ntok (greedy 8 new tokens on the 160 HARD stimuli; hidden states at the generated
positions, mean over tokens 1..8 stopping before EOS), A_ams (AMS concept prompts, src/ams_reimpl.py), A_prompt_p1
(plain 'User: ...\\nAssistant:' render, parents only, for N5), vmin_stacked / vmin_onesproj (least eigenvector of the
per-block [o_proj | down_proj] Gram, raw and all-ones-projected, for B7 / B7_nullproj).
Arms whose block weights equal the parent's (sysprompt, cautious, wu05, wu20, attn_eager) copy the parent's vmin files;
resave copies ALL parent arrays after a bitwise check of 8 stimuli on the reloaded model.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "src_i3_h2"))
sys.path.insert(0, str(SRC / "i3h2"))  # FIX (iter5 tierB external mode): aii_common lives here, not src_i3/h2
from common import (ASSETS, HARVEST, PRIVATE, RESULTS, SEED, SYS_HELPFUL, WS, Deviations, get_device,  # noqa: E402
                    gpu_guard, jdump, jload, setup_logging, sha256_file, start_rss_watchdog, utc_now, verify_chain)
from loguru import logger  # noqa: E402

CFG = {"max_len_prompt": 192,
       # iter5 confirm-fix: batch_prompt/dec_batch are overridable per-process via env (default unchanged),
       # so one OOM-prone checkpoint can be re-harvested at a smaller batch without raising the harvest's
       # 4.5 GB VRAM cap and without touching every other tag's arrays -- see results/deviations_confirmfix.json.
       "batch_prompt": int(os.environ.get("CONFIRMFIX_BATCH_PROMPT", "8")),
       "lens_chunk": 8, "dec_new": 8,
       "dec_batch": int(os.environ.get("CONFIRMFIX_DEC_BATCH", "32"))}
SAME_BLOCKS_AS_PARENT = {"sysprompt", "cautious", "wu05", "wu20", "attn_eager", "resave"}
SAME_INPUT_AND_BODY = {"wu05", "wu20"}      # A_prompt must be bitwise identical to the parent's

# --------------------------------------------------------------------------- #
# iter5 CONFIRM-FIX (results/deviations_confirmfix.json): three external-      #
# checkpoint harvest failures, patched here (WS-local copy). Schema, battery   #
# and candidate formulas are untouched; only model-loading is repaired.        #
# --------------------------------------------------------------------------- #
import variants as _variants  # noqa: E402
from interv import HookedRunner as _HookedRunner  # noqa: E402
from interv import lesion_module_names as _lesion_module_names  # noqa: E402

_ORIG_LOAD_PARENT = _variants.load_parent


def _blocks_multiarch(model):
    """variants.blocks() was `getattr(model, "model", model).layers` only, which raises
    AttributeError for GPT-NeoX ('GPTNeoXForCausalLM' object has no attribute 'layers':
    the blocks live at gpt_neox.layers) and would do the same for Bloom (transformer.h).
    Reuse interv.HookedRunner._find_blocks -- the plan's already-registered multi-arch
    block finder (model/transformer/gpt_neox/language_model x layers/h/blocks/decoder) --
    instead of hand-rolling a second table. _find_blocks reads only self.model, so a bare
    namespace stands in for the runner instance."""
    from types import SimpleNamespace
    return _HookedRunner._find_blocks(SimpleNamespace(model=model))


def _leaf_module(block, leaf_name):
    """First submodule of `block` whose own (dotted-path-final) name is leaf_name."""
    for name, mod in block.named_modules():
        if name and name.split(".")[-1] == leaf_name:
            return mod
    raise AttributeError(f"no submodule named {leaf_name!r} on {type(block).__name__}")


def _attn_mlp_out_modules(model, block):
    """(attention-output module, MLP-output module) for one block, resolved per-architecture via
    interv.lesion_module_names (ARCH_LESION_MODULES + a leaf-name fallback search) instead of the
    hardcoded block.self_attn.o_proj / block.mlp.down_proj path that only Llama-family blocks have.
    GPT-NeoX ('GPTNeoXLayer' object has no attribute 'self_attn') uses block.attention.dense /
    block.mlp.dense_4h_to_h; Bloom would hit the same AttributeError via transformer blocks named
    .self_attention/.mlp.dense_4h_to_h."""
    attn_name, mlp_name = _lesion_module_names(model, block)
    return _leaf_module(block, attn_name), _leaf_module(block, mlp_name)


def _weight_fingerprint_multiarch(model):
    """variants.weight_fingerprint (sha256 over embed, lm_head, layer0 attn-out, mid mlp-out, last
    attn-out, final norm), but resolving the attn-out/mlp-out projections with
    _attn_mlp_out_modules instead of the hardcoded .self_attn.o_proj / .mlp.down_proj path (same
    AttributeError as _blocks_multiarch fixes, one level deeper: the block itself resolves fine,
    but Llama-only submodule names do not). Formula/order unchanged from the original."""
    import hashlib
    from variants import _lin_weight, _tensor_bytes, lens_parts

    B = _blocks_multiarch(model)
    L = len(B)
    attn0, _ = _attn_mlp_out_modules(model, B[0])
    _, mlp_mid = _attn_mlp_out_modules(model, B[L // 2])
    attnL, _ = _attn_mlp_out_modules(model, B[L - 1])
    ts = [model.get_input_embeddings().weight, _lin_weight(model.lm_head),
          _lin_weight(attn0), _lin_weight(mlp_mid), _lin_weight(attnL)]
    fnw = getattr(lens_parts(model)[1], "weight", None)
    if fnw is not None:          # OLMo(-1) uses a NON-parametric final LayerNorm (no weight): skipped, A13
        ts.append(fnw)
    h = hashlib.sha256()
    for t in ts:
        h.update(_tensor_bytes(t))
    return h.hexdigest()


def _cfg_special_id(model, name: str) -> int | None:
    """model.config.<name> (e.g. eos_token_id), unwrapping the occasional list form."""
    v = getattr(model.config, name, None)
    if isinstance(v, (list, tuple)):
        v = v[0] if v else None
    return int(v) if v is not None else None


def _load_parent_confirmfix(fk, dtype="bfloat16", attn="sdpa", int8_bnb=False, repo=None):
    """(a) force eager attention: GPT-Neo's SDPA path raises unconditionally ('GPTNeoForCausalLM
    does not support ... scaled_dot_product_attention ... load your model with
    attn_implementation="eager"'). tierB.run_tag already reloads every arm eager post-hoc for the
    battery (model.set_attn_implementation("eager")), so loading eager here to begin with only
    makes the harvest match the battery it feeds -- it never diverges from it.
    (b) repair a tokenizer with NEITHER pad_token NOR eos_token NOR bos_token registered (PleIAs/
    Pleias-1.2b-Preview ships an EMPTY special_tokens_map.json / bare tokenizer_config.json even
    though config.json / generation_config.json carry bos_token_id=1, eos_token_id=2): first restore
    eos/bos straight from the model's own config (real vocab ids -- confirmed token@2='<|end_of_text|>'
    round-trips correctly through the tokenizer). variants.load_parent's own 'tok.pad_token =
    tok.eos_token when None' fallback then has a real eos_token to fall back to; if config carried no
    eos_token_id either, fall further back to the literal '[PAD]' token already present in the vocab,
    and only mint a brand-new one as a last resort. Without the bos/eos repair, tierB.run_tag's own
    contentless() ('bos = tok.bos_token_id if ... else tok.eos_token_id; ids=[int(bos)]') raises
    TypeError: int() argument ... not 'NoneType' on this checkpoint -- a battery-side symptom of the
    same missing-special-tokens root cause, not a second bug; the battery's own code is untouched.
    padding_side is left exactly as the rest of the code already sets it (right for p_harvest/c11/
    n5, left for dec_harvest) -- untouched here."""
    model, tok, local = _ORIG_LOAD_PARENT(fk, dtype=dtype, attn="eager", int8_bnb=int8_bnb, repo=repo)
    if tok.eos_token_id is None:
        eid = _cfg_special_id(model, "eos_token_id")
        if eid is not None:
            tok.eos_token_id = eid
    if tok.bos_token_id is None:
        bid = _cfg_special_id(model, "bos_token_id")
        if bid is not None:
            tok.bos_token_id = bid
    if tok.pad_token is None:
        if tok.eos_token is not None:
            tok.pad_token = tok.eos_token
        elif tok.get_vocab().get("[PAD]") is not None:
            tok.pad_token = "[PAD]"
        else:
            tok.add_special_tokens({"pad_token": "[PAD]"})
            model.resize_token_embeddings(len(tok))
    return model, tok, local


_variants.blocks = _blocks_multiarch
_variants.load_parent = _load_parent_confirmfix
_variants.weight_fingerprint = _weight_fingerprint_multiarch


def order_gate(smoke: bool) -> dict:
    if smoke:
        return {"gate": "smoke (random-init / non-study arm): allowed before truth"}
    v = verify_chain(["prereg", "graded_truth", "classification"])
    if not v["ok"]:
        logger.error(f"ORDER GATE FAILED: {v['problems']}")
        raise SystemExit(2)
    return {"gate": "PASS", **v}


def committed_arms() -> dict[str, str]:
    """Per-arm gate (staged chain, amendment A11): an arm may be harvested only if it is the parent or child of a
    SCORED pair inside a classification_s*.json whose chain record verifies. Returns {tag: stage file}."""
    from common import chain_records, sha256_file
    ok = {}
    recs = [r for r in chain_records() if r["step"] == "classification" and r.get("file")]
    for r in recs:
        f = WS / r["file"]
        if not f.exists() or sha256_file(f) != r["sha256"]:
            continue
        for q in jload(f)["pairs"]:
            if q.get("kind") in ("constructed", "harvested_regen") and q.get("observed_class") not in (None, "UNSCORED"):
                ok.setdefault(q["parent"], r["file"])
                ok.setdefault(q["child"], r["file"])
    return ok


def dec_harvest(model, tok, texts: list[str], n_new: int, batch: int, eos: set[int]):
    """Greedy decode n_new tokens; hidden states (all L+1 layers) at the positions of generated tokens 1..n_new.
    A_dec = mean over generated positions before the first EOS; tok1 = first generated position; n_tok per row."""
    import torch
    dev = next(model.parameters()).device
    tok.padding_side = "left"
    N = len(texts)
    A = A1 = None
    ntok = np.zeros(N, dtype=np.int32)
    with torch.no_grad():
        for b0 in range(0, N, batch):
            enc = tok(texts[b0:b0 + batch], return_tensors="pt", padding=True, truncation=True,
                      max_length=CFG["max_len_prompt"], add_special_tokens=False)
            ids, attn = enc["input_ids"].to(dev), enc["attention_mask"].to(dev)
            pos = attn.long().cumsum(-1) - 1
            pos.masked_fill_(attn == 0, 1)
            out = model(input_ids=ids, attention_mask=attn, position_ids=pos, use_cache=True, output_hidden_states=True,
                        logits_to_keep=1)
            last_h = torch.stack([h[:, -1, :] for h in out.hidden_states], 1).float()   # last prompt position
            past = out.past_key_values
            nxt = out.logits[:, -1, :].argmax(-1)
            b = ids.shape[0]
            L1 = len(out.hidden_states)
            d = out.hidden_states[0].shape[-1]
            if A is None:
                A = np.zeros((N, L1, d), dtype=np.float16)
                A1 = np.zeros((N, L1, d), dtype=np.float16)
            acc = torch.zeros((b, L1, d), device=dev)
            cnt = torch.zeros(b, device=dev)
            alive = torch.ones(b, dtype=torch.bool, device=dev)
            first = None
            cur_attn, cur_pos = attn, pos[:, -1]
            for k in range(n_new):
                is_eos = torch.tensor([int(t) in eos for t in nxt.tolist()], dtype=torch.bool, device=dev)
                alive = alive & ~is_eos
                cur_attn = torch.cat([cur_attn, torch.ones((b, 1), dtype=cur_attn.dtype, device=dev)], 1)
                cur_pos = cur_pos + 1
                o = model(input_ids=nxt[:, None], attention_mask=cur_attn, position_ids=cur_pos[:, None],
                          past_key_values=past, use_cache=True, output_hidden_states=True)
                hs = torch.stack([h[:, -1, :] for h in o.hidden_states], 1).float()
                if first is None:
                    first = torch.where(alive[:, None, None], hs, last_h)
                acc += hs * alive[:, None, None].float()
                cnt += alive.float()
                past = o.past_key_values
                nxt = o.logits[:, -1, :].argmax(-1)
                if not bool(alive.any()):
                    break
            mean = torch.where((cnt > 0)[:, None, None], acc / cnt.clamp_min(1)[:, None, None], last_h)
            A[b0:b0 + b] = mean.to(torch.float16).cpu().numpy()
            A1[b0:b0 + b] = first.to(torch.float16).cpu().numpy()
            ntok[b0:b0 + b] = cnt.cpu().numpy().astype(np.int32)
            del out, past
    tok.padding_side = "right"
    return A, A1, ntok


def _dense_weight(mod):
    """float32 dense weight of a Linear, dequantising bitsandbytes LLM.int8 (Linear8bitLt: int8 CB + per-row SCB)."""
    import torch
    from variants import _lin_weight
    W = _lin_weight(mod).detach()
    if W.dtype == torch.int8:
        scb = getattr(mod.weight, "SCB", None)
        if scb is None:
            scb = getattr(getattr(mod, "state", None), "SCB", None)
        if scb is None:
            raise RuntimeError("int8 weight without SCB scales")
        return (W.float() * scb.float()[:, None] / 127.0)
    if hasattr(W, "is_quantized") and W.is_quantized:
        return W.dequantize().float()
    return W.float()


def block_vmins(model):
    """Per block: least eigenvector of G = M M^T (M = [o_proj | down_proj], fp32 Gram, fp64 eigh), raw and with the
    all-ones direction pushed out of the bottom of the spectrum (I3 b7_diagnostic.least_vec)."""
    import scipy.linalg as sla
    import torch
    from variants import _lin_weight, blocks  # noqa: F401  (_lin_weight used by _dense_weight)
    raw, proj, lam = [], [], []
    for b in blocks(model):
        with torch.no_grad():
            attn_mod, mlp_mod = _attn_mlp_out_modules(model, b)
            Wo = _dense_weight(attn_mod)
            Wd = _dense_weight(mlp_mod)
            M = torch.cat([Wo, Wd], 1)
            G = (M.double() @ M.double().T).cpu().numpy()   # fp64 Gram (device-independent to ~1e-12)
        d = G.shape[0]
        w, v = sla.eigh(G, subset_by_index=[0, 0], driver="evr")
        raw.append(v[:, 0])
        lam.append(float(w[0]))
        one = np.ones(d) / np.sqrt(d)
        Gp = G - np.outer(one, one @ G) - np.outer(G @ one, one) + np.outer(one, one) * float(one @ G @ one)
        Gp += np.outer(one, one) * (np.trace(G) / d)
        Gp = 0.5 * (Gp + Gp.T)
        _, vp = sla.eigh(Gp, subset_by_index=[0, 0], driver="evr")
        proj.append(vp[:, 0])
        del G, Gp, M
    return np.array(raw, dtype=np.float32), np.array(proj, dtype=np.float32), np.array(lam)


def harvest_arm(tag: str, stimuli, c11, token_sets, gen_fp: dict, *, with_p1: bool, smoke_limit: int | None = None,
                out_root: Path = HARVEST) -> dict:
    import torch
    from harvest import _encode_token_sets, _tok_len_stats, p_harvest, render_prompt, u_summary
    from variants import build
    fk, variant = tag.split("__")
    out = out_root / tag
    if (out / "DONE").exists():
        logger.info(f"SKIP {tag} (DONE)")
        return jload(out / "meta.json")
    out.mkdir(parents=True, exist_ok=True)
    parent_dir = out_root / f"{fk}__ref"
    t0 = time.time()
    meta = {"tag": tag, "fk": fk, "variant": variant, "harvest_utc_start": utc_now(), "timings": {}, "cfg": CFG}
    if variant == "resave":
        from transformers import AutoModelForCausalLM, AutoTokenizer
        d = PRIVATE / "resave" / fk
        tok = AutoTokenizer.from_pretrained(str(d))
        model = AutoModelForCausalLM.from_pretrained(str(d), dtype=torch.bfloat16, low_cpu_mem_usage=True,
                                                     attn_implementation="sdpa").eval().to(get_device())
        from variants import make_render_fn
        rf = make_render_fn(tok, "ref")
        idx = list(range(0, 256, 32))
        with torch.no_grad():
            ph = p_harvest(model, tok, [rf(stimuli[i]["text"]) for i in idx], max_len=CFG["max_len_prompt"],
                           batch_size=CFG["batch_prompt"], token_ids={}, lens_chunk=CFG["lens_chunk"])
        # the reference harvest ran these 8 prompts inside different length-sorted batches; compare with a same-batch
        # recomputation on the PARENT instead of the stored array to keep the check bitwise
        del model
        gc.collect()
        from variants import load_parent
        pm, ptok, _ = load_parent(fk)
        pm.to(get_device())
        with torch.no_grad():
            pph = p_harvest(pm, ptok, [rf(stimuli[i]["text"]) for i in idx], max_len=CFG["max_len_prompt"],
                            batch_size=CFG["batch_prompt"], token_ids={}, lens_chunk=CFG["lens_chunk"])
        same = bool(np.array_equal(ph["A"], pph["A"]))
        del pm
        gc.collect()
        meta["bitwise_check_8_stimuli"] = same
        if not same:
            raise RuntimeError("resave arm is not bitwise identical on 8 stimuli")
        for f in parent_dir.iterdir():
            if f.is_file() and f.name not in ("DONE", "meta.json", "MANIFEST.sha256.json"):
                shutil.copy2(f, out / f.name)
        meta["arrays"] = f"copied from {parent_dir.name} (bitwise-identical model, verified on 8 stimuli)"
        pmeta = jload(parent_dir / "meta.json")
        for k in ("n_layers", "hidden_size", "vocab_size", "dtype", "tie_word_embeddings", "rms_eps", "weight_fingerprint",
                  "u_summary", "dec", "ams", "n5_perturbations", "device"):
            if k in pmeta:
                meta[k] = pmeta[k]
        meta["timings"]["total_s"] = time.time() - t0
        jdump(meta, out / "meta.json")
        (out / "DONE").write_text(utc_now())
        return meta

    if fk == "RANDINIT":   # pre-truth smoke control: random-init Qwen3-0.6B architecture (not a behaviour checkpoint)
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
        from variants import download, make_render_fn, weight_fingerprint
        local = download("Qwen/Qwen3-0.6B")
        tok = AutoTokenizer.from_pretrained(local)
        torch.manual_seed(0)
        cfg = AutoConfig.from_pretrained(local)
        if os.environ.get("SMOKE_TINY"):   # code-path smoke on a tiny random model (cheap in RAM/CPU)
            cfg.num_hidden_layers, cfg.hidden_size, cfg.intermediate_size = 2, 128, 256
            cfg.num_attention_heads, cfg.num_key_value_heads, cfg.head_dim = 2, 1, 64
            cfg.layer_types = ["full_attention"] * 2 if hasattr(cfg, "layer_types") else None
        model = AutoModelForCausalLM.from_config(cfg, dtype=torch.bfloat16).eval().to(get_device())
        render_fn = make_render_fn(tok, "ref")
        info = {"weight_fingerprint": weight_fingerprint(model), "dtype": "torch.bfloat16", "random_init": True}
    else:
        model, tok, render_fn, info = build(fk, variant, allow_train=False)
    meta["weight_fingerprint"] = info["weight_fingerprint"]
    fp_gen = (gen_fp.get(tag) or {}).get("weight_fingerprint")
    meta["fingerprint_matches_generation"] = (fp_gen == info["weight_fingerprint"]) if fp_gen else None
    if fp_gen and fp_gen != info["weight_fingerprint"]:
        raise RuntimeError(f"{tag}: harvest weights differ from generation weights")
    full_gen = (gen_fp.get(tag) or {}).get("weight_sha_full")
    meta["weight_sha_full_matches_generation"] = (full_gen == info.get("weight_sha_full")) if full_gen else None
    if full_gen and full_gen != info.get("weight_sha_full"):
        raise RuntimeError(f"{tag}: harvest weights (full sha) differ from generation weights")
    conf = model.config
    meta.update({"n_layers": int(conf.num_hidden_layers), "hidden_size": int(conf.hidden_size),
                 "vocab_size": int(getattr(conf, "vocab_size", 0)), "dtype": info.get("dtype"),
                 "tie_word_embeddings": bool(getattr(conf, "tie_word_embeddings", False)),
                 "rms_eps": float(getattr(conf, "rms_norm_eps", None) or 1e-6), "build_info": {k: v for k, v in info.items() if k != "lora"}})
    token_ids = _encode_token_sets(tok, token_sets)
    jdump(token_ids, out / "token_ids.json")
    S = stimuli[:smoke_limit] if smoke_limit else stimuli
    texts = [render_fn(s["text"]) for s in S]
    if variant == "ref":
        assert all(texts[i] == render_prompt(tok, S[i]["text"], "chat") for i in range(len(S))), "ref render != H2 render"
    t = time.time()
    with torch.no_grad():
        ph = p_harvest(model, tok, texts, max_len=CFG["max_len_prompt"], batch_size=CFG["batch_prompt"],
                       token_ids=token_ids, lens_chunk=CFG["lens_chunk"])
    np.save(out / "A_prompt.npy", ph["A"])
    np.save(out / "norms.npy", ph["norms"])
    for k in ("r_refusal", "r_hedge", "r_control", "r_fullV_final"):
        if k in ph:
            np.save(out / f"{k}.npy", ph[k])
    meta["timings"]["p_harvest_s"] = time.time() - t
    meta["prompt_token_lengths"] = _tok_len_stats(tok, texts, CFG["max_len_prompt"])
    meta["prompt_render_example"] = texts[0][:400]
    if variant in SAME_INPUT_AND_BODY and (parent_dir / "A_prompt.npy").exists() and not smoke_limit:
        meta["A_prompt_bitwise_equal_parent"] = bool(np.array_equal(np.load(parent_dir / "A_prompt.npy"), ph["A"]))
    y = np.array([int(s["y"]) for s in S])
    L1 = ph["A"].shape[1]
    hbar = ph["A"][y == 1, L1 - 1, :].astype(np.float32).mean(0)
    hbar_all = ph["A"][:, L1 - 1, :].astype(np.float32).mean(0)
    t = time.time()
    meta.update({"u_summary": u_summary(model, out, token_ids, hbar, hbar_all, meta["rms_eps"])})
    meta["timings"]["u_summary_s"] = time.time() - t
    # ---- c11 (amendment A4: wu arms copy the parent's A_c11 / A_ams -- same inputs, same body weights)
    t = time.time()
    reuse = variant in SAME_INPUT_AND_BODY and (parent_dir / "A_c11.npy").exists() and not smoke_limit
    if reuse:
        for f in ("A_c11.npy", "A_ams.npy"):
            if (parent_dir / f).exists():
                shutil.copy2(parent_dir / f, out / f)
        meta["reused_from_parent"] = ["A_c11.npy", "A_ams.npy", "vmin files"]
    c11_texts = [render_fn(x["prompt"]) for x in (c11[:smoke_limit] if smoke_limit else c11)]
    if not reuse:
        with torch.no_grad():
            np.save(out / "A_c11.npy", p_harvest(model, tok, c11_texts, max_len=CFG["max_len_prompt"],
                                                 batch_size=CFG["batch_prompt"], token_ids={}, lens_chunk=8)["A"])
    meta["timings"]["c11_s"] = time.time() - t
    # ---- decode site (N9/N10)
    t = time.time()
    hard_idx = [i for i, s in enumerate(S) if int(s["set_id"]) == 1]
    from gen_variants import eos_ids
    Ad, Ad1, nt = dec_harvest(model, tok, [texts[i] for i in hard_idx], CFG["dec_new"], CFG["dec_batch"], eos_ids(model, tok))
    np.save(out / "A_dec.npy", Ad)
    np.save(out / "A_dec_tok1.npy", Ad1)
    np.save(out / "dec_ntok.npy", nt)
    meta["dec"] = {"n_rows": len(hard_idx), "mean_ntok": float(nt.mean()) if len(nt) else None,
                   "n_zero_tok": int((nt == 0).sum()), "rows": "HARD stimuli in stimuli.json order"}
    meta["timings"]["dec_s"] = time.time() - t
    # ---- AMS prompts
    t = time.time()
    # AMS prompts are RAW text (no chat template, no system prompt): for sysprompt/cautious/wu arms the inputs and every
    # hidden state are identical to the parent's by construction, so the parent's A_ams is copied (A4 extension)
    if variant in ("sysprompt", "cautious", "wu05", "wu20") and (parent_dir / "A_ams.npy").exists() and not smoke_limit:
        shutil.copy2(parent_dir / "A_ams.npy", out / "A_ams.npy")
    try:
        if (out / "A_ams.npy").exists() and variant in ("sysprompt", "cautious", "wu05", "wu20"):
            raise FileExistsError("reused")
        import ams_reimpl
        if smoke_limit:
            raise FileNotFoundError("smoke run: AMS pass skipped (validated separately in results/ams_validation.json)")
        A_ams = ams_reimpl.harvest_ams(model, tok)
        np.save(out / "A_ams.npy", A_ams)
        meta["ams"] = {"n_prompts": int(A_ams.shape[0]), "source": "src/ams_reimpl.py"}
    except FileExistsError:
        meta["ams"] = {"source": f"copied from {parent_dir.name} (A4)"}
    except (ImportError, FileNotFoundError, AttributeError) as e:
        meta["ams"] = {"error": repr(e)[:300]}
        Deviations.add("ams_harvest_missing", f"{tag}: AMS prompts not harvested ({e!r})"[:300], "ams_reimpl unavailable",
                       "AMS_T1/T2 NOT_AVAILABLE for this arm")
    meta["timings"]["ams_s"] = time.time() - t
    # ---- weights (B7 / B7_nullproj)
    t = time.time()
    if variant in SAME_BLOCKS_AS_PARENT and (parent_dir / "vmin_stacked.npy").exists():
        for f in ("vmin_stacked.npy", "vmin_onesproj.npy", "vmin_lambda.npy"):
            shutil.copy2(parent_dir / f, out / f)
        meta["w_summary"] = f"copied from {parent_dir.name} (block weights identical by construction)"
    else:
        vr, vp, lam = block_vmins(model)
        np.save(out / "vmin_stacked.npy", vr)
        np.save(out / "vmin_onesproj.npy", vp)
        np.save(out / "vmin_lambda.npy", lam)
        meta["w_summary"] = "computed"
    meta["timings"]["w_s"] = time.time() - t
    # ---- N5 perturbation harvests (A13 restores the plan's p1/p2/p3 for EVERY arm on the GPU box):
    #   p1 = plain 'User: ...\nAssistant:' render; p2 = system prompt 'You are a helpful assistant.' via the chat template
    #   (for the sysprompt arm this IS its own render -> A_prompt copied); p3 = the same weights at the other half
    #   precision (bf16 arms -> fp16 cast; fp16 arm -> bf16 cast; int8bnb -> NOT_AVAILABLE). p3 runs LAST (it casts).
    if with_p1 and not smoke_limit:
        from variants import render as _render
        t = time.time()
        n5 = {}
        with torch.no_grad():
            p1 = [render_fn(s_["text"], mode="plain") for s_ in S]
            np.save(out / "A_prompt_p1.npy", p_harvest(model, tok, p1, max_len=CFG["max_len_prompt"],
                                                       batch_size=CFG["batch_prompt"], token_ids={}, lens_chunk=8)["A"])
            n5["p1"] = "plain render"
            if variant == "sysprompt":
                shutil.copy2(out / "A_prompt.npy", out / "A_prompt_p2.npy")
                n5["p2"] = "= own A_prompt (the arm's render already carries the helpful system prompt)"
            else:
                p2 = [_render(tok, s_["text"], SYS_HELPFUL) for s_ in S]
                np.save(out / "A_prompt_p2.npy", p_harvest(model, tok, p2, max_len=CFG["max_len_prompt"],
                                                           batch_size=CFG["batch_prompt"], token_ids={}, lens_chunk=8)["A"])
                n5["p2"] = "helpful system prompt"
            if variant == "int8bnb":
                n5["p3"] = "NOT_AVAILABLE (bitsandbytes int8 weights cannot be re-cast)"
            else:
                tgt = torch.bfloat16 if next(model.parameters()).dtype == torch.float16 else torch.float16
                model.to(tgt)
                np.save(out / "A_prompt_p3.npy", p_harvest(model, tok, texts, max_len=CFG["max_len_prompt"],
                                                           batch_size=CFG["batch_prompt"], token_ids={}, lens_chunk=8)["A"])
                n5["p3"] = f"same weights cast to {tgt}"
        meta["n5_perturbations"] = n5
        meta["timings"]["n5_s"] = time.time() - t
    meta["device"] = str(next(model.parameters()).device)
    meta["timings"]["total_s"] = time.time() - t0
    meta["harvest_utc_end"] = utc_now()
    jdump(meta, out / "meta.json")
    man = {p.name: sha256_file(p) for p in sorted(out.iterdir()) if p.is_file() and p.suffix == ".npy"}
    jdump(man, out / "MANIFEST.sha256.json")
    (out / "DONE").write_text(utc_now())
    logger.info(f"HARVESTED {tag} in {meta['timings']['total_s']:.0f}s ({ {k: round(v) for k, v in meta['timings'].items()} })")
    del model, tok, ph
    gc.collect()
    return meta


def _order_key(t: str):
    fk, v = t.split("__", 1)
    fam = {"F1": 0, "F2": 1, "F3": 2, "HG": 3, "F4": 4}.get(fk, 5)
    return (fam, v != "ref", v == "resave", t)


def watch_loop(stimuli, c11, token_sets) -> int:
    import torch
    failed: dict[str, int] = {}
    oom: dict[str, int] = {}
    while True:
        gen_fp = jload(RESULTS / "gen_timings.json") if (RESULTS / "gen_timings.json").exists() else {}
        allowed = committed_arms()
        todo = [t for t in sorted(allowed, key=_order_key)
                if not (HARVEST / t / "DONE").exists() and failed.get(t, 0) < 2]
        # a child that copies parent arrays needs its parent first
        todo = [t for t in todo if t.endswith("__ref") or t.startswith("HG__") or (HARVEST / f"{t.split('__')[0]}__ref" / "DONE").exists()
                or f"{t.split('__')[0]}__ref" not in allowed]
        if todo:
            jdump({"utc": utc_now(), "allowed": allowed, "todo": todo}, RESULTS / "harvest_gate_watch.json")
        for tag in todo[:1]:
            try:
                harvest_arm(tag, stimuli, c11, token_sets, gen_fp, with_p1=True, smoke_limit=None, out_root=HARVEST)
            except torch.OutOfMemoryError as e:   # the L4 is shared: wait for memory instead of giving up
                oom[tag] = oom.get(tag, 0) + 1
                logger.warning(f"HARVEST OOM {tag} (#{oom[tag]}): waiting 45 s ({str(e)[:160]})")
                gc.collect()
                torch.cuda.empty_cache()
                time.sleep(45)
                if oom[tag] >= 12:
                    failed[tag] = 2
                    Deviations.add(f"harvest_failed_{tag}", f"{tag}: CUDA OOM x{oom[tag]}"[:300], "shared-GPU memory", "arm NOT_SCORED")
            except Exception as e:  # noqa: BLE001
                failed[tag] = failed.get(tag, 0) + 1
                logger.exception(f"HARVEST FAILED {tag} (attempt {failed[tag]}): {e!r}")
                if failed[tag] >= 2:
                    Deviations.add(f"harvest_failed_{tag}", f"{tag}: {e!r}"[:300], "harvest error (2 attempts)", "arm NOT_SCORED")
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        if not todo:
            if (RESULTS / "harvest_stop.flag").exists():
                logger.info("harvest watch: stop flag and nothing left -> exit")
                return 0
            time.sleep(30)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="*", default=None)
    ap.add_argument("--smoke-limit", type=int, default=None)
    ap.add_argument("--watch", action="store_true", help="A13: loop, harvesting every newly committed arm (parents "
                    "first) until results/harvest_stop.flag exists and nothing is left")
    a = ap.parse_args()
    setup_logging("harvest")
    import torch
    torch.set_num_threads(int(os.environ.get("GEN_THREADS", "4")))
    torch.manual_seed(SEED)
    hw = gpu_guard(float(os.environ.get("VRAM_CAP_GB", "7")))
    logger.info(f"device: {hw}")
    start_rss_watchdog(float(os.environ.get("RSS_CAP_GB", "20")))
    smoke = a.smoke_limit is not None
    if a.watch and not smoke:      # A13 watcher: wait (never exit) until the first classification is committed
        while not verify_chain(["prereg", "graded_truth", "classification"])["ok"]:
            time.sleep(30)
    gate = order_gate(smoke)
    jdump(gate, RESULTS / ("harvest_gate_smoke.json" if smoke else "harvest_gate.json"))
    stimuli = jload(ASSETS / "stimuli.json")["rows"]
    c11 = jload(ASSETS / "c11_items.json")
    c11 = c11["items"] if isinstance(c11, dict) else c11
    token_sets = {k: v for k, v in jload(ASSETS / "token_sets.json").items() if k in ("refusal", "hedge", "control")}
    gen_fp = jload(RESULTS / "gen_timings.json") if (RESULTS / "gen_timings.json").exists() else {}
    allowed = committed_arms() if not smoke else {}
    if a.tags:
        tags = a.tags
    else:
        tags = sorted(allowed, key=lambda t: (not t.endswith("__ref"), t.endswith("__resave"), t))
    if not smoke:
        refused = [t for t in tags if t not in allowed]
        if refused:
            logger.error(f"ORDER GATE: no committed classification covers {refused}; they are NOT harvested")
        tags = [t for t in tags if t in allowed]
        jdump({"utc": utc_now(), "allowed": allowed, "requested": a.tags, "refused": refused},
              RESULTS / f"harvest_gate_{int(time.time())}.json")
    out_root = HARVEST if not smoke else (PRIVATE / "smoke_harvest")
    if a.watch and not smoke:
        return watch_loop(stimuli, c11, token_sets)
    for tag in tags:
        try:
            harvest_arm(tag, stimuli, c11, token_sets, gen_fp, with_p1=True,  # A13: p1/p2/p3 for every arm (GPU)
                        smoke_limit=a.smoke_limit, out_root=out_root)
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:  # noqa: BLE001
            logger.exception(f"HARVEST FAILED {tag}: {e!r}")
            Deviations.add(f"harvest_failed_{tag}", f"{tag}: {e!r}"[:300], "harvest error", "arm NOT_SCORED")
            gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
