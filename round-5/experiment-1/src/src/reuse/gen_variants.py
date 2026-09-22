#!/usr/bin/env python3
"""PHASE A -- BEHAVIOUR FIRST: greedy generation for every (parent, variant) arm. NO hidden states, NO hooks.

One long-lived process (MooseFS import latency); arms run in the prereg'd priority order; finished arms are skipped
(resumable). Per arm: build the variant (src/variants.py), T1 sanity against the parent's cached sanity logits,
greedy decode (I3 greedy_shrink when the generation config has no logits processors, else HF generate) with
max_new_tokens=96 on the behaviour items in the parent's fixed length-sorted chunks, write private/gens/<tag>.jsonl.
The lesion/W_U edits use hooks ONLY inside variant construction on side sets (never on behaviour items); during
generation `output_hidden_states` is False and no hook is registered (asserted).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ASSETS, GENS, PARENTS, PRIVATE, RESULTS, SEED, Deviations, get_device, gpu_guard,  # noqa: E402
                    jdump, jload, setup_logging, start_rss_watchdog, to_dev, utc_now)
from loguru import logger  # noqa: E402

MAX_LEN = 224
MAX_NEW = 96
CHUNK = 42
# prereg amendment A6: per-family protocol (pairs are always within one family, so each pair has ONE protocol)
# prereg amendment A13 (GPU box): A6's reduced F2/F3 protocol is withdrawn (no F2/F3 arm had been generated); every
# family uses the registered F1 protocol (168 items x 96 new tokens, length-sorted chunks of 42)
PROTO = {fk: {"items": "all", "max_new": 96, "chunk": 42} for fk in ("F1", "F2", "F3", "F4")}


def proto(fk: str) -> dict:
    return PROTO.get(fk, PROTO["F1"])       # HG tags (A13) use the same registered protocol


def items_for(fk: str, items: list[dict]) -> list[dict]:
    if proto(fk)["items"] == "all":
        return items
    keep_xs = {f"xs{k:03d}_{s}" for k in range(20) for s in ("u", "s")}
    return [x for x in items if x["subset"] == "laneC" or x["item_id"] in keep_xs]
EDITS = PRIVATE / "edits"
CORE = ["ref", "a10", "int8wo", "sysprompt", "fp16", "wu05", "lora"]
HG_SLUGS = ["huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2", "mylesgoose--Llama-3.2-1B-Instruct-abliterated2",
            "Qwen--Qwen3-1.7B", "huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2",
            "Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct", "Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct-abliterated",
            "amd--AMD-OLMo-1B", "amd--AMD-OLMo-1B-SFT", "amd--AMD-OLMo-1B-SFT-DPO", "tiiuae--Falcon3-1B-Base",
            "Qwen--Qwen2.5-1.5B-Instruct", "Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3"]
EXTRA = ["cautious", "wu20", "a05", "dpo"]
LATE = ["int8bnb"]      # bitsandbytes LLM.int8 decodes ~40x slower than bf16 on the shared L4 -> after the HG checkpoints
DEFAULT_ORDER = (  # prereg amendment A13: core arms of F1, F2, F3 (GPU), resaves, then the extras, then optional F4
    [f"F1__{v}" for v in CORE] + ["F1__resave"] + [f"F2__{v}" for v in CORE] + ["F2__resave"]
    + [f"F3__{v}" for v in CORE] + ["F3__resave"]
    + [f"{fk}__{v}" for v in EXTRA for fk in ("F1", "F2", "F3")]
    + [f"HG__{s}" for s in HG_SLUGS]
    + [f"{fk}__{v}" for v in LATE for fk in ("F1", "F2", "F3")]
    + [f"F4__{v}" for v in CORE] + ["F4__resave"] + [f"F4__{v}" for v in EXTRA + LATE]
)
_PROC_FIELDS = ("repetition_penalty", "no_repeat_ngram_size", "bad_words_ids", "forced_bos_token_id",
                "forced_eos_token_id", "min_length", "min_new_tokens", "suppress_tokens", "begin_suppress_tokens",
                "sequence_bias", "exponential_decay_length_penalty", "encoder_repetition_penalty")


def has_logits_processors(model) -> list[str]:
    gc_ = model.generation_config
    bad = []
    for f in _PROC_FIELDS:
        v = getattr(gc_, f, None)
        if v is None:
            continue
        if f in ("repetition_penalty", "encoder_repetition_penalty") and float(v) == 1.0:
            continue
        if f in ("no_repeat_ngram_size", "min_length", "min_new_tokens") and int(v) == 0:
            continue
        if isinstance(v, (list, tuple, dict)) and len(v) == 0:
            continue
        bad.append(f"{f}={v}")
    return bad


def eos_ids(model, tok) -> set[int]:
    e = getattr(model.generation_config, "eos_token_id", None)
    if e is None:
        e = tok.eos_token_id
    return set(e if isinstance(e, (list, tuple)) else [e]) - {None}


def greedy_shrink(model, enc, max_new: int, eos: set[int], pad_id: int):
    """I3 src/gen.py greedy_shrink, verbatim logic: greedy decoding identical to generate(do_sample=False) for configs
    without logits processors, except that EOS rows are dropped from the batch and the KV cache."""
    import torch
    ids, attn = enc["input_ids"], enc["attention_mask"]
    dev = ids.device
    B = ids.shape[0]
    pos = attn.long().cumsum(-1) - 1
    pos.masked_fill_(attn == 0, 1)
    out = model(input_ids=ids, attention_mask=attn, position_ids=pos, use_cache=True, logits_to_keep=1)
    past = out.past_key_values
    nxt = out.logits[:, -1, :].argmax(-1)
    active = torch.arange(B, device=dev)
    res = torch.full((B, max_new), pad_id, dtype=torch.long, device=dev)
    cur_attn, cur_pos = attn, pos[:, -1]
    steps = 0
    for step in range(max_new):
        res[active, step] = nxt
        steps = step + 1
        done = torch.tensor([int(t) in eos for t in nxt.tolist()], dtype=torch.bool, device=dev)
        if step == max_new - 1 or bool(done.all()):
            break
        if bool(done.any()):
            keep = (~done).nonzero().squeeze(1)
            past.batch_select_indices(keep)
            active, nxt, cur_attn, cur_pos = active[keep], nxt[keep], cur_attn[keep], cur_pos[keep]
        cur_attn = torch.cat([cur_attn, torch.ones((cur_attn.shape[0], 1), dtype=cur_attn.dtype, device=dev)], dim=1)
        cur_pos = cur_pos + 1
        out = model(input_ids=nxt[:, None], attention_mask=cur_attn, position_ids=cur_pos[:, None],
                    past_key_values=past, use_cache=True, logits_to_keep=1)
        past = out.past_key_values
        nxt = out.logits[:, -1, :].argmax(-1)
    return res.cpu(), steps


def chunks_for(fk: str, tok, items: list[dict]) -> list[list[int]]:
    """Fixed per-parent batching: items sorted by the REFERENCE render's token length, chunks of CHUNK.
    HG tags pass fk='HG_<slug>' (per-checkpoint tokenizer)."""
    p = EDITS / f"{fk}_chunks_n{len(items)}_c{proto(fk.split('_')[0] if fk.startswith('HG_') else fk)['chunk']}.json"
    if p.exists():
        return jload(p)
    from variants import render
    lens = [len(tok(render(tok, x["prompt"]), add_special_tokens=False)["input_ids"]) for x in items]
    order = [int(i) for i in np.argsort(lens, kind="mergesort")]
    c = proto(fk)["chunk"]
    ch = [order[i:i + c] for i in range(0, len(order), c)]
    jdump(ch, p)
    return ch


def generate(model, tok, render_fn, items, chunks, shrink: bool, max_new: int = MAX_NEW,
             partial_dir: Path | None = None):
    """Chunk-resumable (session 3): each finished chunk is persisted to partial_dir/<ci>.json, so a pod restart
    loses at most one chunk. Chunks are fixed per parent, so a resumed arm equals an uninterrupted one."""
    import torch
    tok.padding_side = "left"
    rows = [None] * len(items)
    t_all = time.time()
    n_tok = 0
    with torch.no_grad():
        for ci, ch in enumerate(chunks):
            pf = partial_dir / f"{ci}.json" if partial_dir is not None else None
            if pf is not None and pf.exists():
                prev = jload(pf)
                if [r["item_id"] for r in prev] == [items[i]["item_id"] for i in ch]:
                    for r, i in zip(prev, ch):
                        rows[i] = r
                        n_tok += int(r["n_new_tokens"])
                    logger.info(f"    chunk {ci + 1}/{len(chunks)}: RESUMED from {pf.name}")
                    continue
            texts = [render_fn(items[i]["prompt"]) for i in ch]
            enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LEN,
                      add_special_tokens=False)
            enc = to_dev(enc, next(model.parameters()).device)
            t0 = time.time()
            P = enc["input_ids"].shape[1]
            if shrink:
                newtok, nsteps = greedy_shrink(model, enc, max_new, eos_ids(model, tok), tok.pad_token_id)
            else:
                gen = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=tok.pad_token_id,
                                     output_hidden_states=False)
                newtok, nsteps = gen[:, P:].cpu(), gen.shape[1] - P
            for r, i in enumerate(ch):
                new = newtok[r]
                eos = eos_ids(model, tok)
                toks = [int(t) for t in new.tolist()]
                cut = next((k for k, t in enumerate(toks) if t in eos), None)
                n_new = (cut + 1) if cut is not None else sum(t != tok.pad_token_id for t in toks)
                n_tok += n_new
                rows[i] = {"item_id": items[i]["item_id"], "set": items[i]["set"], "subset": items[i]["subset"],
                           "prompt": items[i]["prompt"], "response": tok.decode(new, skip_special_tokens=True).strip(),
                           "n_new_tokens": int(n_new), "hit_max_new": cut is None}
            if pf is not None:
                partial_dir.mkdir(parents=True, exist_ok=True)
                jdump([rows[i] for i in ch], pf)
            logger.info(f"    chunk {ci + 1}/{len(chunks)}: {time.time() - t0:.0f}s (P={P}, steps {nsteps}, total {time.time() - t_all:.0f}s)")
    tok.padding_side = "right"
    return rows, time.time() - t_all, n_tok


def sanity_logits(model, tok, render_fn):
    """Last-token logits on the 32 held-aside Dolly sanity prompts (NOT behaviour items)."""
    import torch
    side = jload(ASSETS / "side_sets.json")
    tok.padding_side = "right"
    outs = []
    with torch.no_grad():
        for i in range(0, 32, 16):
            texts = [render_fn(t) for t in side["sanity_32"][i:i + 16]]
            enc = to_dev(tok(texts, return_tensors="pt", padding=True, add_special_tokens=False),
                         next(model.parameters()).device)
            lg = model(**enc, use_cache=False).logits
            last = enc["attention_mask"].sum(1) - 1
            outs.append(lg[torch.arange(lg.shape[0], device=lg.device), last].float().cpu())
    return torch.cat(outs)


def t1_sanity(fk: str, variant: str, model, tok, render_fn, info: dict) -> dict:
    import torch
    if fk == "HG":
        return {"variant": variant, "skipped": "A13 harvested checkpoint: no constructed-parent sanity reference"}
    ref_p = EDITS / f"{fk}_sanity_ref.pt"
    lg = sanity_logits(model, tok, render_fn)
    res = {"variant": variant}
    if variant == "ref":
        torch.save(lg.to(torch.float32), ref_p)
        res["stored_reference"] = True
        return res
    if not ref_p.exists():
        return {"variant": variant, "error": "no ref sanity logits"}
    ref = torch.load(ref_p)
    diff = (lg - ref).abs()
    res.update({"max_abs_logit_diff": float(diff.max()), "mean_abs_logit_diff": float(diff.mean()),
                "first_token_agreement": float((lg.argmax(-1) == ref.argmax(-1)).float().mean()),
                "bitwise_identical": bool(torch.equal(lg, ref))})
    if variant == "resave":
        res["pass"] = res["bitwise_identical"] and bool(info.get("tensor_sha_equal"))
    elif variant in ("fp32", "fp16", "int8dyn", "int8wo", "int8bnb", "attn_eager"):
        res["pass_fp_rule"] = res["max_abs_logit_diff"] < 0.5 and res["first_token_agreement"] >= 0.95
    elif variant in ("wu05", "wu20"):
        z = np.load(EDITS / f"{fk}_hbar.npz")
        hbar = torch.tensor(z["hbar"], dtype=torch.float32)
        T = torch.tensor([int(x) for x in z["T"]], dtype=torch.long)
        W_new = model.lm_head.weight.detach()[T.to(model.lm_head.weight.device)].float().cpu()
        W_old = (model.get_input_embeddings().weight.detach()[T.to(model.lm_head.weight.device)].float().cpu()
                 if info.get("was_tied") else None)
        if W_old is not None:
            shift = (W_new - W_old) @ hbar
            res["realised_shift_on_hbar_mean"] = float(shift.mean())
            res["realised_shift_on_hbar_sd"] = float(shift.std())
            res["target_shift"] = -float(info["delta_nat"])
            res["pass_shift_rule_bf16"] = abs(float(shift.mean()) + float(info["delta_nat"])) < 0.05
        res["embed_bit_identical"] = info.get("embed_bit_identical")
        others = torch.ones(ref.shape[1], dtype=torch.bool)
        others[T] = False
        res["non_edited_logits_max_abs_diff"] = float(diff[:, others].max())
    elif variant in ("a05", "a10"):
        from variants import last_token_states
        les = np.load(EDITS / f"{fk}_lesion.npz")
        r = torch.tensor(les["r"], dtype=torch.float32)
        side = jload(ASSETS / "side_sets.json")
        H, _ = last_token_states(model, tok, [render_fn(t) for t in side["lesion_val"]["harm"][:8]])
        proj = (H[:, 1:, :] @ r).abs().mean(0)
        res["post_edit_mean_abs_proj_by_layer"] = proj.tolist()
        res["l_abl"] = int(les["l_abl"])
    return res


def pre_edit_projection(fk: str, model, tok, render_fn) -> list[float]:
    """Parent's |h.r| per layer on the 8 lesion-val prompts (for the alpha=1.0 <1% check)."""
    import torch
    from variants import last_token_states
    les = np.load(EDITS / f"{fk}_lesion.npz")
    r = torch.tensor(les["r"], dtype=torch.float32)
    side = jload(ASSETS / "side_sets.json")
    H, _ = last_token_states(model, tok, [render_fn(t) for t in side["lesion_val"]["harm"][:8]])
    return (H[:, 1:, :] @ r).abs().mean(0).tolist()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=None)
    ap.add_argument("--limit-items", type=int, default=None)
    ap.add_argument("--stop-flag", default=str(RESULTS / "gen_stop.flag"))
    ap.add_argument("--out-dir", default=None, help="smoke runs write elsewhere (never private/gens)")
    a = ap.parse_args()
    global GENS
    smoke = a.out_dir is not None
    if smoke:
        GENS = Path(a.out_dir)
        GENS.mkdir(parents=True, exist_ok=True)
    else:
        (RESULTS / "gen_sweep_finished.flag").unlink(missing_ok=True)
    setup_logging("gen")
    import torch
    torch.set_num_threads(int(os.environ.get("GEN_THREADS", "4")))
    torch.manual_seed(SEED)
    hw = gpu_guard(float(os.environ.get("VRAM_CAP_GB", "7")))
    logger.info(f"device: {hw}")
    start_rss_watchdog(float(os.environ.get("RSS_CAP_GB", "20")))
    from variants import build, fit_lesion, load_parent, make_render_fn
    items = jload(ASSETS / "behaviour_items.json")["items"]
    if a.limit_items:
        items = items[: a.limit_items]
    arms = a.arms or DEFAULT_ORDER
    tim_p, san_p = (RESULTS / "gen_timings.json", RESULTS / "variant_sanity.json") if not smoke else \
        (GENS / "smoke_timings.json", GENS / "smoke_sanity.json")
    for tag in arms:
        if Path(a.stop_flag).exists():
            logger.warning(f"stop flag present -> stopping before {tag}")
            break
        fk, variant = tag.split("__")
        out = GENS / f"{tag}.jsonl"
        if out.exists():
            logger.info(f"SKIP {tag} (gens exist)")
            continue
        lock = GENS / f"{tag}.lock"
        if lock.exists():
            try:
                lpid = int(lock.read_text().split()[0])
                os.kill(lpid, 0)
                alive = lpid != os.getpid()
            except (ValueError, IndexError, ProcessLookupError, PermissionError):
                alive = False
            if alive:
                logger.info(f"SKIP {tag} (another generation process holds {lock.name})")
                continue
            logger.warning(f"{tag}: stale lock {lock.read_text().strip()!r} (holder dead: pod restart) -> removed")
            lock.unlink(missing_ok=True)
        lock.write_text(f"{os.getpid()} {utc_now()}")
        ref_gens = GENS / f"{fk}__ref.jsonl"
        if variant != "ref" and fk != "HG" and not ref_gens.exists():
            logger.error(f"{tag}: parent reference not generated yet; skipping")
            continue
        t0 = time.time()
        try:
            if variant in ("a05", "a10") and not (PRIVATE / "edits" / f"{fk}_lesion.npz").exists():
                pm, ptok, _ = load_parent(fk)
                pm.to(get_device())
                les = fit_lesion(fk, pm, ptok)
                pre = pre_edit_projection(fk, pm, ptok, make_render_fn(ptok, "ref"))
                jdump({"fk": fk, "l_abl": les["l_abl"], "table": les["table"], "pre_edit_mean_abs_proj_by_layer": pre,
                       "kl_filter_failed": les.get("kl_filter_failed"), "baseline_refusal_logmass": les.get("baseline_refusal_logmass")},
                      RESULTS / f"lesion_fit_{fk}.json")
                del pm, ptok
                gc.collect()
            model, tok, render_fn, info = build(fk, variant)
            t_build = time.time() - t0
            assert not getattr(model.config, "output_hidden_states", False)
            n_hooks = sum(len(m._forward_hooks) + len(m._forward_pre_hooks) for m in model.modules())
            assert n_hooks == 0, f"{n_hooks} hooks registered during generation"
            san = t1_sanity(fk, variant, model, tok, render_fn, info)
            san["weight_fingerprint"] = info["weight_fingerprint"]
            san["info"] = {k: v for k, v in info.items() if k not in ("lora", "dpo")}
            for tv in ("lora", "dpo"):
                if tv in info:
                    san[f"{tv}_train"] = {k: v for k, v in info[tv].items() if k not in ("losses", "reward_margins")}
                    san[f"{tv}_loss_falls"] = info[tv].get("loss_last5", 9e9) < info[tv].get("loss_first5", -9e9)
            if "dpo" in info:
                san["dpo_margin_positive_finite"] = bool(info["dpo"].get("margin_finite")) and \
                    info["dpo"].get("margin_last10_mean", -1) > 0
            sd = jload(san_p) if san_p.exists() else {}
            sd[tag] = san
            jdump(sd, san_p)
            logger.info(f"{tag}: built in {t_build:.0f}s; sanity {json.dumps({k: v for k, v in san.items() if k not in ('info', 'post_edit_mean_abs_proj_by_layer')})[:400]}")
            if variant == "resave":
                # bitwise-identical model => greedy outputs are the parent's by construction (CPU fallback F-1)
                if not san.get("pass"):
                    raise RuntimeError(f"resave sanity failed: {san}")
                rows = [dict(json.loads(l), by_construction_from=f"{fk}__ref") for l in ref_gens.read_text().splitlines() if l.strip()]
                t_gen, n_tok, dec = 0.0, 0, "none (bitwise-identical model; parent's generations by construction)"
            else:
                procs = has_logits_processors(model)
                shrink = not procs
                fitems = items_for(fk, items)
                chunks = chunks_for(fk if fk != "HG" else f"HG_{variant}", tok, fitems)
                rows, t_gen, n_tok = generate(model, tok, render_fn, fitems, chunks, shrink, proto(fk)["max_new"],
                                              partial_dir=GENS / f"{tag}.partial")
                dec = "greedy_shrink" if shrink else f"hf_generate (processors: {procs})"
            tmp = Path(str(out) + ".tmp")
            with open(tmp, "w") as f:
                for r in rows:
                    f.write(json.dumps(dict(r, tag=tag), ensure_ascii=False) + "\n")
            tmp.replace(out)
            pdir = GENS / f"{tag}.partial"
            if pdir.exists():
                for q in pdir.glob("*.json"):
                    q.unlink()
                pdir.rmdir()
            tim = jload(tim_p) if tim_p.exists() else {}
            tim[tag] = {"t_build_s": t_build, "t_gen_s": t_gen, "n_items": len(rows), "n_new_tokens": n_tok,
                        "tok_per_s": n_tok / max(t_gen, 1e-9), "decoder": dec, "max_new_tokens": proto(fk)["max_new"],
                        "protocol": proto(fk),
                        "weight_fingerprint": info["weight_fingerprint"], "dtype": info.get("dtype"),
                        "weight_sha_full": info.get("weight_sha_full"), "device": info.get("device"),
                        "example_render": render_fn(items[0]["prompt"])[:400], "utc_done": utc_now()}
            jdump(tim, tim_p)
            logger.info(f"DONE {tag}: gen {t_gen:.0f}s, {n_tok} tok ({n_tok / max(t_gen, 1e-9):.1f} tok/s), total {time.time() - t0:.0f}s")
            lock.unlink(missing_ok=True)
            del model, tok
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception as e:  # noqa: BLE001
            logger.exception(f"FAILED {tag}: {e!r}")
            tim = jload(tim_p) if tim_p.exists() else {}
            tim[tag] = {"failed": repr(e)[:500], "utc": utc_now()}
            jdump(tim, tim_p)
            lock.unlink(missing_ok=True)
            gc.collect()
    if not smoke:
        (RESULTS / "gen_sweep_finished.flag").write_text(utc_now())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
