"""PHASE B -- ACTIVATION HARVEST of the confirmation panel, AFTER prereg.json and graded_truth.json are
hash-committed (in that order). Adapted from src/ref_i3/harvest_panel.py (iteration-2 kernels in src/h2).

Per tag (canonical checkpoint or in-house no-op variant), one model load:
  CORE   P-harvest (256 stimuli, last prompt token, all L+1 layers, fp16; logit-lens set drives),
         U-summary (W_U token-set rows, final-norm gamma), C11 prompt pass (64 severity items),
         N9 decode pass (the frozen 32 HARD prompts: 8 greedy tokens, residuals at generated tokens 1-8,
         all layers), GREEDY_REFUSAL decode (16 EASY AdvBench prompts not in Lane C, 32 greedy tokens,
         lexicon flags only), AMS_REIMPL prompt pass (src/ams_reimpl.py, if present), hook checks,
         then W-summary (weights only, canonical tags; variants share the parent's weights) + card regex.
  EXTRAS (--extras, a later sweep): N5 P_notemplate pass (A_prompt_notemplate + its r_* drives) and the
         teacher-forced A_resp cells (iteration-5 re-scoring substrate).
Variants: NOOP_fp32 = float32 load; NOOP_sysprompt = chat template with the fixed neutral system prompt
(generation and harvest rendered identically).
ORDER GATE: refuses any panel tag unless hash_chain.jsonl holds prereg.json THEN results/graded_truth.json
and both still hash to the recorded values; a tag must also be present in the committed graded truth.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import re
import shutil
import sys
import time
import traceback
import urllib.request
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "h2"))
from common import (ASSETS, HARVEST, PRIVATE, RESULTS, WS, Deviations, chain_records, jdump,  # noqa: E402
                    jload, setup_logging, sha256_file, slug, utc_now)
from loguru import logger  # noqa: E402

CFG = {  # H2 prereg.json config values that the kernels read (verbatim; iteration-3 panel values)
    "dtype": "bfloat16", "attn": "sdpa", "max_len_prompt": 192, "max_len_cell": 288,
    "batch_prompt": 8, "batch_cell": 4, "lens_chunk": 8, "early_window": [5, 20], "late_window": [40, 55],
    "x5_positions": 32, "keep_cont_tokens": 56, "cells_mode": "all", "x5_cell_index": [],
}
NEUTRAL_SYSPROMPT = "You are a helpful assistant."
N9_TOKENS = 8
GREEDY_TOKENS = 32
HOOK_CHECKS = RESULTS / "hook_checks.json"


def order_gate(tag: str, truth: dict) -> dict:
    recs = chain_records()
    names = [r["file"] for r in recs]
    try:
        i_p = names.index("prereg.json")
        i_t = names.index("results/graded_truth.json")
    except ValueError as e:
        raise SystemExit(f"ORDER GATE: missing chain record ({e}); refusing to hook a panel checkpoint")
    if not i_p < i_t:
        raise SystemExit("ORDER GATE: graded truth was committed before the prereg")
    for i in (i_p, i_t):
        f = WS / recs[i]["file"]
        if sha256_file(f) != recs[i]["sha256"]:
            raise SystemExit(f"ORDER GATE: {f} changed after commit")
    if tag not in truth["per_ckpt"]:
        raise SystemExit(f"ORDER GATE: {tag} has no committed graded truth")
    return {"gate": "PASS", "prereg_utc": recs[i_p]["utc"], "truth_utc": recs[i_t]["utc"]}


def render_variant(tok, text: str, variant: str, mode: str = "chat") -> str:
    """Canonical harvest rendering = iteration-2 render_prompt(chat); NOOP_sysprompt adds the system turn."""
    from harvest import render_prompt
    if mode == "plain":
        return text
    if variant == "NOOP_sysprompt" and getattr(tok, "chat_template", None):
        msgs = [{"role": "system", "content": NEUTRAL_SYSPROMPT}, {"role": "user", "content": text}]
        for kw in (dict(tokenize=False, add_generation_prompt=True, enable_thinking=False),
                   dict(tokenize=False, add_generation_prompt=True)):
            try:
                return tok.apply_chat_template(msgs, **kw)
            except Exception:  # noqa: BLE001
                continue
    return render_prompt(tok, text, mode)


def load_model(repo: str, dtype_name: str, trust: bool, random_init: bool = False, seed: int = 0):
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
    from gen import download
    local = download(repo)
    tok = AutoTokenizer.from_pretrained(local, trust_remote_code=trust)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token or tok.unk_token
    tok.padding_side = "right"
    dt = {"bfloat16": torch.bfloat16, "float32": torch.float32}[dtype_name]
    info = {}
    if random_init:
        torch.manual_seed(seed)
        np.random.seed(seed)
        conf = AutoConfig.from_pretrained(local, trust_remote_code=trust)
        model = AutoModelForCausalLM.from_config(conf, dtype=dt, trust_remote_code=trust)
    else:
        model, info = AutoModelForCausalLM.from_pretrained(local, dtype=dt, low_cpu_mem_usage=True,
                                                           output_loading_info=True, trust_remote_code=trust)
    model.eval()
    return model, tok, local, info


def hook_check(model, tok, variant: str) -> dict:
    """output_hidden_states gives L+1 tensors (b, s, d); is the final hidden state already post-norm?
    (compare logits at the last position with hidden_states[-1] @ W_U^T (+ bias))."""
    import torch
    from harvest import _lens_parts
    conf = model.config
    texts = [render_variant(tok, "How do I bake bread?", variant), render_variant(tok, "Tell me a fact about the moon.", variant)]
    enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False)
    with torch.no_grad():
        out = model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"], output_hidden_states=True,
                    use_cache=False)
    hs = out.hidden_states
    last = enc["attention_mask"].sum(1) - 1
    b = enc["input_ids"].shape[0]
    W_U, fn = _lens_parts(model)
    h_last = hs[-1][torch.arange(b), last].float()
    lg = out.logits[torch.arange(b), last].float()
    head = getattr(model, "lm_head", None)
    bias = getattr(head, "bias", None) if head is not None else None
    Wd = W_U.detach()
    z = torch.cat([h_last @ Wd[i:i + 32768].float().T for i in range(0, Wd.shape[0], 32768)], 1)  # vocab chunks
    if bias is not None:
        z = z + bias.detach().float()
    rel = float((z - lg).abs().max() / max(float(lg.abs().max()), 1e-9))
    corr = float(np.corrcoef(z.flatten().numpy(), lg.flatten().numpy())[0, 1])
    zn = None
    if fn is not None:
        try:
            hn = fn(h_last.to(W_U.dtype)).float()
            z2 = torch.cat([hn @ Wd[i:i + 32768].float().T for i in range(0, Wd.shape[0], 32768)], 1)
            zn = float((z2 - lg).abs().max() / max(float(lg.abs().max()), 1e-9))
        except Exception:  # noqa: BLE001
            zn = None
    norm_types = sorted({type(m).__name__ for n, m in model.named_modules() if "norm" in type(m).__name__.lower()})
    n_layers = int(getattr(conf, "num_hidden_layers", 0) or getattr(conf, "n_layer", 0) or 0)
    return {"n_hidden_states": len(hs), "num_hidden_layers": n_layers, "L_plus_1_ok": len(hs) == n_layers + 1,
            "shape_ok": all(t.dim() == 3 and t.shape[0] == b for t in hs), "d": int(hs[0].shape[-1]),
            "final_hidden_is_post_norm_rel_err": rel, "final_hidden_logit_corr": corr,
            "renormed_rel_err": zn, "final_hidden_is_post_norm": bool(rel < 0.02 or corr > 0.999),
            "final_norm_module": type(fn).__name__ if fn is not None else None, "norm_module_types": norm_types,
            "mean_subtracting_layernorm": any(t in ("LayerNorm",) or "LayerNorm" == t for t in norm_types),
            "final_logit_softcapping": getattr(conf, "final_logit_softcapping", None),
            "model_type": getattr(conf, "model_type", None)}


def decode_pass(model, tok, prompts: list[str], role: str, variant: str, n_new: int, want_hidden: bool,
                batch: int = 32):
    """Greedy-decode n_new tokens with the GENERATION rendering (gen.render); optionally return the
    residual stream at generated tokens 1..n_new (all layers) from one forward over prompt+generated."""
    import torch
    from gen import _eos_ids, greedy_shrink, render
    eos = _eos_ids(model, tok)
    tok.padding_side = "left"
    texts, gens, n_valid, H = [], [], [], []
    try:
        for b0 in range(0, len(prompts), batch):
            chunk = prompts[b0:b0 + batch]
            rendered = [render(tok, p, role, variant) for p in chunk]
            enc = tok([t for t, _ in rendered], return_tensors="pt", padding=True, truncation=True, max_length=224,
                      add_special_tokens=rendered[0][1])
            enc = {k: v for k, v in enc.items() if k in ("input_ids", "attention_mask")}
            with torch.no_grad():
                try:
                    newtok, _ = greedy_shrink(model, enc, n_new, eos, tok.pad_token_id)
                except Exception:  # noqa: BLE001  (hybrid caches: plain HF greedy)
                    g = model.generate(**enc, max_new_tokens=n_new, do_sample=False, pad_token_id=tok.pad_token_id,
                                       repetition_penalty=1.0, temperature=None, top_p=None, top_k=None)
                    newtok = g[:, enc["input_ids"].shape[1]:]
                    if newtok.shape[1] < n_new:
                        newtok = torch.cat([newtok, torch.full((newtok.shape[0], n_new - newtok.shape[1]),
                                                               tok.pad_token_id, dtype=newtok.dtype)], 1)
            nv = []
            for r in range(newtok.shape[0]):
                k = 0
                for t in newtok[r].tolist():
                    k += 1
                    if t in eos:
                        break
                nv.append(k)
                gens.append(tok.decode(newtok[r][:k], skip_special_tokens=True))
            n_valid += nv
            if want_hidden:
                ids = torch.cat([enc["input_ids"], newtok], 1)
                att = torch.cat([enc["attention_mask"], torch.ones_like(newtok)], 1)
                pos = att.long().cumsum(-1) - 1
                pos.masked_fill_(att == 0, 1)
                with torch.no_grad():
                    out = model(input_ids=ids, attention_mask=att, position_ids=pos, output_hidden_states=True,
                                use_cache=False)
                P = enc["input_ids"].shape[1]
                hs = torch.stack([h[:, P:P + n_new, :] for h in out.hidden_states], 2)  # [b, n_new, L+1, d]
                H.append(hs.float().to(torch.float16).numpy())
                del out, hs
    finally:
        tok.padding_side = "right"
    return (np.concatenate(H, 0) if H else None), n_valid, gens


def card_regex(repo: str, lex: dict) -> dict:
    txt = ""
    try:
        req = urllib.request.Request(f"https://huggingface.co/{repo}/raw/main/README.md",
                                     headers={"User-Agent": "aii-confirm-panel"})
        with urllib.request.urlopen(req, timeout=40) as r:
            txt = r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        txt = ""
        err = repr(e)[:200]
    else:
        err = None
    blob = (repo + "\n" + txt).lower()
    name_free = re.sub(r"abliterat\w*", " ", txt.lower())
    return {"REGEX": float(bool(re.search(lex["card_regex"], blob))),
            "REGEX_NAMEFREE": float(bool(re.search(lex["card_regex_namefree"], name_free))),
            "card_chars": len(txt), "card_sha256": __import__("hashlib").sha256(txt.encode()).hexdigest(),
            "fetch_error": err, "utc": utc_now()}


def manifest(out_dir: Path) -> dict:
    m = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.name not in ("MANIFEST.sha256.json", "DONE"):
            m[str(p.relative_to(out_dir))] = sha256_file(p)
    jdump(m, out_dir / "MANIFEST.sha256.json")
    return m


def harvest_core(r: dict, entry: dict, truth: dict, stimuli, c11, token_sets, subsets, *, random_init: bool = False,
                 tag_override: str | None = None, p_rows: list[int] | None = None) -> dict:
    import torch
    from harvest import _encode_token_sets, _tok_len_stats, p_harvest, u_summary
    tag = tag_override or r["tag"]
    variant = r["variant"]
    out_dir = HARVEST / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "DONE").exists():
        logger.info(f"SKIP {tag} (DONE)")
        return jload(out_dir / "meta.json")
    gate = order_gate(tag, truth) if not random_init else {"gate": "random-init control (not a panel member)"}
    t0 = time.time()
    dtype = "float32" if variant == "NOOP_fp32" else "bfloat16"
    trust = bool(entry.get("trust_remote_code"))
    model, tok, local, info = load_model(r["repo"], dtype, trust, random_init=random_init)
    t_load = time.time() - t0
    conf = model.config
    L = int(getattr(conf, "num_hidden_layers", 0) or getattr(conf, "n_layer", 0))
    meta = {"repo": r["repo"], "tag": tag, "variant": variant, "random_init": bool(random_init),
            "role": entry.get("role"), "family": entry.get("family"), "unit": entry.get("unit"),
            "n_layers": L, "hidden_size": int(getattr(conf, "hidden_size", 0) or getattr(conf, "n_embed", 0)),
            "vocab_size": int(getattr(conf, "vocab_size", 0)), "model_type": getattr(conf, "model_type", None),
            "tie_word_embeddings": bool(getattr(conf, "tie_word_embeddings", False)),
            "dtype_loaded": dtype, "trust_remote_code": trust,
            "rms_eps": float(getattr(conf, "rms_norm_eps", None) or getattr(conf, "layer_norm_eps", None)
                             or getattr(conf, "layer_norm_epsilon", None) or 1e-6),
            "t_load_s": t_load, "timings": {}, "order_gate": gate, "local_snapshot": str(local),
            "has_chat_template": bool(getattr(tok, "chat_template", None)), "harvest_utc_start": utc_now()}
    if not random_init:
        miss = list((info or {}).get("missing_keys", []) or [])
        meta["load_missing_keys_n"] = len(miss)
    # hook check (every tag; cheap)
    try:
        hc = hook_check(model, tok, variant)
    except Exception as e:  # noqa: BLE001
        hc = {"error": repr(e)[:300]}
    meta["hook_check"] = hc
    allhc = jload(HOOK_CHECKS) if HOOK_CHECKS.exists() else {}
    allhc[tag] = hc
    jdump(allhc, HOOK_CHECKS)
    token_ids = _encode_token_sets(tok, token_sets)
    meta["token_ids"] = {k: len(v) for k, v in token_ids.items()}
    jdump(token_ids, out_dir / "token_ids.json")

    # ---- P-HARVEST (256 stimuli)
    t = time.time()
    p_stim = stimuli if p_rows is None else [stimuli[i] for i in p_rows]
    texts = [render_variant(tok, s["text"], variant) for s in p_stim]
    with torch.no_grad():
        ph = p_harvest(model, tok, texts, max_len=CFG["max_len_prompt"], batch_size=CFG["batch_prompt"],
                       token_ids=token_ids, lens_chunk=CFG["lens_chunk"])
    np.save(out_dir / "A_prompt.npy", ph["A"])
    np.save(out_dir / "norms.npy", ph["norms"])
    for k in ("r_refusal", "r_hedge", "r_control", "r_fullV_final"):
        if k in ph:
            np.save(out_dir / f"{k}.npy", ph[k])
    meta["timings"]["p_harvest_s"] = time.time() - t
    meta["prompt_token_lengths"] = _tok_len_stats(tok, texts, CFG["max_len_prompt"])
    meta["prompt_render_example"] = texts[0][:400]
    y = np.array([s["y"] for s in p_stim], dtype=np.int8)
    L1 = ph["A"].shape[1]
    hbar = ph["A"][y == 1, L1 - 1, :].astype(np.float32).mean(0)
    hbar_all = ph["A"][:, L1 - 1, :].astype(np.float32).mean(0)
    n_nan = int(np.isnan(ph["A"].astype(np.float32)).sum())
    meta["n_nan_A_prompt"] = n_nan

    # ---- U-SUMMARY
    t = time.time()
    meta.update(u_summary(model, out_dir, token_ids, hbar, hbar_all, meta["rms_eps"]))
    meta["timings"]["u_summary_s"] = time.time() - t

    # ---- C11 (64 severity items)
    t = time.time()
    c11_texts = [render_variant(tok, x["prompt"], variant) for x in c11]
    with torch.no_grad():
        pc = p_harvest(model, tok, c11_texts, max_len=CFG["max_len_prompt"], batch_size=CFG["batch_prompt"],
                       token_ids={}, lens_chunk=CFG["lens_chunk"])
    np.save(out_dir / "A_c11.npy", pc["A"])
    meta["timings"]["c11_s"] = time.time() - t
    del ph, pc
    gc.collect()

    # ---- N9 decode pass (32 HARD prompts, 8 own greedy tokens, residuals all layers)
    t = time.time()
    role = entry.get("role") or "instruct"
    try:
        idx = subsets["n9_subset_stim_idx"]
        D, nv, gtxt = decode_pass(model, tok, [stimuli[i]["text"] for i in idx], role, variant, N9_TOKENS, True)
        np.save(out_dir / "D_dec.npy", D)
        jdump({"stim_idx": idx, "y": subsets["n9_subset_y"], "n_valid": nv, "n_new": N9_TOKENS,
               "rendering": "generation rendering (gen.render): chat template for instruct roles, plain for base"},
              out_dir / "dec_meta.json")
        meta["n9_status"] = "OK"
    except Exception as e:  # noqa: BLE001
        meta["n9_status"] = f"FAILED: {e!r}"[:300]
        logger.error(f"N9 decode failed {tag}: {e!r}")
    meta["timings"]["n9_decode_s"] = time.time() - t

    # ---- GREEDY_REFUSAL (16 EASY AdvBench prompts not in Lane C, 32 greedy tokens)
    t = time.time()
    try:
        gidx = subsets["greedy_refusal_stim_idx"]
        _, nv, gtxt = decode_pass(model, tok, [stimuli[i]["text"] for i in gidx], role, variant, GREEDY_TOKENS, False)
        prim = [any(w.lower() in g.lower() for w in subsets["greedy_refusal_lexicon_primary"]) for g in gtxt]
        comp = [any(w in g.lower() for w in subsets["greedy_refusal_lexicon_companion"]) for g in gtxt]
        jdump({"stim_idx": gidx, "match_primary": prim, "match_companion": comp, "n_new": GREEDY_TOKENS,
               "rate_primary": float(np.mean(prim)), "rate_companion": float(np.mean(comp))},
              out_dir / "greedy_refusal.json")
        (PRIVATE / "greedy").mkdir(parents=True, exist_ok=True)
        jdump({"tag": tag, "texts": gtxt}, PRIVATE / "greedy" / f"{tag}.json")   # never released
        meta["greedy_status"] = "OK"
    except Exception as e:  # noqa: BLE001
        meta["greedy_status"] = f"FAILED: {e!r}"[:300]
        logger.error(f"greedy refusal decode failed {tag}: {e!r}")
    meta["timings"]["greedy_s"] = time.time() - t

    # ---- AMS_REIMPL prompt pass
    t = time.time()
    try:
        import ams_reimpl
        std = ams_reimpl.AMS_META["scan_modes"]["standard"] if "scan_modes" in ams_reimpl.AMS_META else \
            ["harmful_content", "injection_resistance", "refusal_capability"]
        res = ams_reimpl.ams_forward(model, tok, concepts=std)   # `ams scan` default mode = standard
        np.save(out_dir / "A_ams.npy", res["acts"])
        jdump({k: v for k, v in res.items() if k != "acts"}, out_dir / "ams_meta.json")
        sig = ams_reimpl.ams_sigma_from_acts(res, mode="standard")
        per = {c: float(v["separation"]) for c, v in sig["concept_results"].items()}
        jdump({"overall": float(min(per.values())) if per else None,
               "overall_rule": "min separation over the standard-mode concepts (the released verdict takes the worst concept)",
               "per_concept": per, "overall_level": sig.get("overall_level"), "raw": sig,
               "dtype_note": "our forward runs in the harvest dtype (bf16 / fp32 variant); the released CLI forces fp32 on CPU"},
              out_dir / "ams_reimpl.json")
        meta["ams_status"] = "OK"
    except Exception as e:  # noqa: BLE001
        meta["ams_status"] = f"NOT_RUN: {e!r}"[:300]
        logger.warning(f"AMS_REIMPL not run for {tag}: {e!r}"[:300])
    meta["timings"]["ams_s"] = time.time() - t
    meta["harvest_utc_end_forward"] = utc_now()
    del model
    gc.collect()

    # ---- W-SUMMARY (weights only; canonical tags) + card regex
    t = time.time()
    parent_dir = HARVEST / slug(r["repo"])
    if random_init:
        meta["w_summary"] = {"status": "NOT_RUN (random-init control)"}
    elif variant == "canonical":
        try:
            from wsummary import w_summary_repo
            wm = w_summary_repo(r["repo"], tag=tag, store_gram=True, gram_dtype="float16", parts=("stacked",))
            meta["w_summary"] = {"n_layers_found": wm.get("n_layers_found"), "elapsed_s": wm.get("elapsed_s")}
        except Exception as e:  # noqa: BLE001
            meta["w_summary"] = {"error": repr(e)[:400]}
            Deviations.add("w_summary_failed", f"{r['repo']}: {e!r}"[:300], "weight-only rows NaN for this checkpoint")
        try:
            jdump(card_regex(r["repo"], subsets), out_dir / "card_regex.json")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"card regex failed {tag}: {e!r}")
    else:  # same weights as the canonical parent (dtype cast / system prompt only)
        for fn in ("svals_stacked.npy", "vmin_stacked.npy", "w_meta.json", "W_DONE", "card_regex.json"):
            if (parent_dir / fn).exists():
                shutil.copyfile(parent_dir / fn, out_dir / fn)
        meta["w_summary"] = {"status": f"COPIED from {parent_dir.name} (identical weights by construction)"}
    meta["timings"]["w_summary_s"] = time.time() - t
    meta["timings"]["total_s"] = time.time() - t0
    meta["harvest_utc_end"] = utc_now()
    jdump(meta, out_dir / "meta.json")
    manifest(out_dir)
    (out_dir / "DONE").write_text(json.dumps({"ts": time.time(), "utc": utc_now(), "total_s": meta["timings"]["total_s"]}))
    logger.info(f"HARVESTED {tag} in {meta['timings']['total_s']:.0f}s " + " ".join(
        f"{k[:-2]} {v:.0f}s" for k, v in meta["timings"].items() if k != "total_s"))
    del tok
    gc.collect()
    return meta


def harvest_extras(r: dict, entry: dict, truth: dict, stimuli, cells_doc, char_spans, which: list[str]) -> dict:
    """Second sweep: N5 P_notemplate pass (+ its logit-lens drives) and teacher-forced A_resp cells."""
    import torch
    from harvest import _encode_token_sets, p_harvest
    tag, variant = r["tag"], r["variant"]
    out_dir = HARVEST / tag
    if not (out_dir / "DONE").exists():
        return {"status": "core not done"}
    todo = [w for w in which if not (out_dir / f"EXTRA_{w}_DONE").exists()]
    if not todo:
        return {"status": "done"}
    order_gate(tag, truth)
    t0 = time.time()
    dtype = "float32" if variant == "NOOP_fp32" else "bfloat16"
    model, tok, local, info = load_model(r["repo"], dtype, bool(entry.get("trust_remote_code")))
    token_ids = jload(out_dir / "token_ids.json")
    res = {}
    if "notemplate" in todo:
        t = time.time()
        texts = [s["text"] for s in stimuli]   # raw text, no chat template (expression-only perturbation)
        with torch.no_grad():
            ph = p_harvest(model, tok, texts, max_len=CFG["max_len_prompt"], batch_size=CFG["batch_prompt"],
                           token_ids=token_ids, lens_chunk=CFG["lens_chunk"])
        np.save(out_dir / "A_prompt_notemplate.npy", ph["A"])
        for k in ("r_refusal", "r_hedge", "r_control", "r_fullV_final"):
            if k in ph:
                np.save(out_dir / f"{k}_notemplate.npy", ph[k])
        (out_dir / "EXTRA_notemplate_DONE").write_text(utc_now())
        res["notemplate_s"] = time.time() - t
        del ph
    if "aresp" in todo:
        t = time.time()
        from c_harvest2 import _render_cells_local, c_harvest_v2
        cells_r = _render_cells_local(tok, cells_doc["cells"], "chat")
        with torch.no_grad():
            ch = c_harvest_v2(model, tok, cells_r, char_spans, dict(CFG))
        np.save(out_dir / "A_resp.npy", ch["A_resp"])
        np.save(out_dir / "cell_kept.npy", ch["kept"])
        np.save(out_dir / "cell_slot_ok.npy", ch["slot_ok"])
        jdump({"n_cells": len(cells_doc["cells"]), "n_kept": int(ch["kept"].sum()), "t_s": ch["elapsed_s"]},
              out_dir / "c_meta.json")
        (out_dir / "EXTRA_aresp_DONE").write_text(utc_now())
        res["aresp_s"] = time.time() - t
    del model, tok
    gc.collect()
    manifest(out_dir)
    res["total_s"] = time.time() - t0
    m = jload(out_dir / "meta.json")
    m.setdefault("extras", {}).update({k: v for k, v in res.items()})
    jdump(m, out_dir / "meta.json")
    logger.info(f"EXTRAS {tag}: {res}")
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--extras", nargs="*", default=None, help="notemplate aresp")
    ap.add_argument("--randinit", action="store_true")
    ap.add_argument("--smoke", type=int, default=0,
                    help="pre-truth pipeline smoke test on the RANDOM-INIT control with N stimuli per group")
    ap.add_argument("--deadline-utc", default="2026-09-21T20:55:00Z")
    a = ap.parse_args()
    setup_logging("harvest")
    import torch
    torch.set_num_threads(int(os.environ.get("HARVEST_THREADS", "2")))
    from datetime import datetime, timezone
    deadline = datetime.fromisoformat(a.deadline_utc.replace("Z", "+00:00"))
    stimuli = jload(ASSETS / "stimuli.json")["rows"]
    token_sets = jload(ASSETS / "token_sets.json")
    token_sets = {k: v for k, v in token_sets.items() if k in ("refusal", "hedge", "control")}
    c11 = jload(ASSETS / "c11_items.json")["items"]
    subsets = jload(ASSETS / "prereg_subsets.json")
    panel = {p["repo"]: p for p in jload(RESULTS / "panel.json")["panel"]}
    if a.smoke:  # random-init control only (not a panel member; allowed before the truth commit)
        first = sorted([p for p in panel.values() if p["role"] == "instruct"], key=lambda p: p["draw_index"])[0]
        keep = []
        for g in sorted({(s["set_id"], s["y"]) for s in stimuli}):
            keep += [i for i, s in enumerate(stimuli) if (s["set_id"], s["y"]) == g][:a.smoke]
        sub = dict(subsets, n9_subset_stim_idx=subsets["n9_subset_stim_idx"][:2] + subsets["n9_subset_stim_idx"][16:18],
                   n9_subset_y=[1, 1, 0, 0], greedy_refusal_stim_idx=subsets["greedy_refusal_stim_idx"][:2])
        r = {"tag": "RandInit-" + first["repo"].split("/")[-1] + "_SMOKE", "repo": first["repo"], "variant": "canonical"}
        harvest_core(r, first, {"per_ckpt": {}}, stimuli, c11[:a.smoke], token_sets, sub, random_init=True,
                     tag_override=r["tag"], p_rows=keep)
        return 0
    truth = jload(RESULTS / "graded_truth.json")
    runs = [r for r in jload(RESULTS / "run_list.json") if r["tag"] in truth["per_ckpt"]]
    if a.only:
        runs = [r for r in runs if r["tag"] in set(a.only)]
    fails = jload(RESULTS / "harvest_failures.json") if (RESULTS / "harvest_failures.json").exists() else []
    if a.randinit:
        first = [p for p in panel.values() if p["role"] == "instruct" and
                 any(r["repo"] == p["repo"] for r in runs)]
        first = sorted(first, key=lambda p: p["draw_index"])[0]
        r = {"tag": "RandInit-" + first["repo"].split("/")[-1], "repo": first["repo"], "variant": "canonical"}
        harvest_core(r, first, truth, stimuli, c11, token_sets, subsets, random_init=True, tag_override=r["tag"])
        return 0
    if a.extras is not None:
        cells_doc = jload(ASSETS / "cells.json")
        char_spans = None
        if "aresp" in a.extras:
            char_spans = jload(ASSETS / "cell_char_spans.json")["char_spans"]
        for r in runs:
            if datetime.now(timezone.utc) > deadline:
                logger.warning("extras deadline reached")
                break
            try:
                harvest_extras(r, panel[r["repo"]], truth, stimuli, cells_doc, char_spans, a.extras)
            except SystemExit:
                raise
            except Exception as e:  # noqa: BLE001
                logger.error(f"EXTRAS FAILED {r['tag']}: {e!r}")
            gc.collect()
        return 0
    for r in runs:
        if datetime.now(timezone.utc) > deadline:
            logger.warning("core-harvest deadline reached; remaining tags NOT harvested")
            break
        try:
            harvest_core(r, panel[r["repo"]], truth, stimuli, c11, token_sets, subsets)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"HARVEST FAILED {r['tag']}: {e!r}")
            fails.append({"tag": r["tag"], "error": repr(e)[:500], "tb": traceback.format_exc()[-3000:],
                          "utc": utc_now()})
            jdump(fails, RESULTS / "harvest_failures.json")
        gc.collect()
    jdump(fails, RESULTS / "harvest_failures.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
