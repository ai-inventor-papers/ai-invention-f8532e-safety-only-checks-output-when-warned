"""STEP 2a -- BEHAVIOUR FIRST: greedy generation on the behavioural items. NO hooks, no hidden states.

Replicates Lane C's lc_harvest.py generate() protocol (transcribed via H2 judge_ext_lanec.py, which
cites the source lines): MAX_LEN=224 prompt truncation, MAX_NEW=140, greedy (do_sample=False),
left-padded batches, chat-template fallback chain for instruct roles (add_generation_prompt=True,
enable_thinking=False -> without enable_thinking -> request+"\\n"), base roles = request+"\\n" with
add_special_tokens=True. CPU-only box (no GPU): bf16 weights, 2 threads. ONE long-lived process for the
whole panel (MooseFS import latency), the NEXT checkpoint is prefetched in a thread while this one runs.

Outputs: private/gens/<slug>.jsonl (never released) + results/gen_timings.json.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ASSETS, GENS, HF_CACHE, RESULTS, Deviations, jdump, jload, setup_logging,  # noqa: E402
                    slug, utc_now)
from loguru import logger  # noqa: E402

MAX_LEN = 224     # lc_harvest.py:57
MAX_NEW = 140     # lc_harvest.py:60
DL_PATTERNS = ["*.json", "*.safetensors", "*.model", "*.txt", "*.jinja", "*.tiktoken", "tokenizer*"]


def download(repo: str) -> str:
    from huggingface_hub import snapshot_download
    for attempt in range(3):
        try:
            return snapshot_download(repo, cache_dir=str(HF_CACHE), allow_patterns=DL_PATTERNS)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"download {repo} attempt {attempt}: {e!r}"[:300])
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"download failed: {repo}")


def chat_text(tok, request: str) -> str:
    """lc_harvest.py:239-249 fallback chain (verbatim via judge_ext_lanec._chat_text)."""
    msgs = [{"role": "user", "content": request}]
    for kw in (dict(add_generation_prompt=True, enable_thinking=False, tokenize=False),
               dict(add_generation_prompt=True, tokenize=False)):
        try:
            return tok.apply_chat_template(msgs, **kw)
        except Exception:  # noqa: BLE001
            continue
    return request + "\n"


def sibling_template(entry: dict, panel: list[dict]) -> str | None:
    """AMD-OLMo-1B-SFT ships no chat template; its SFT-DPO sibling (same tokenizer) does."""
    if not entry.get("template_borrowed_from_sibling"):
        return None
    from transformers import AutoTokenizer
    for p in panel:
        if p["unit"] == entry["unit"] and p["repo"] != entry["repo"] and p["role"] != "base":
            t = AutoTokenizer.from_pretrained(download(p["repo"]))
            if getattr(t, "chat_template", None):
                return t.chat_template
    return None


def load(repo: str, local: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(local)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model, info = AutoModelForCausalLM.from_pretrained(local, dtype=torch.bfloat16, low_cpu_mem_usage=True,
                                                       output_loading_info=True)
    model.eval()
    miss = list((info or {}).get("missing_keys", []) or [])
    return model, tok, miss


def _eos_ids(model, tok) -> set[int]:
    e = getattr(model.generation_config, "eos_token_id", None)
    if e is None:
        e = tok.eos_token_id
    return set(e if isinstance(e, (list, tuple)) else [e]) - {None}


def greedy_shrink(model, enc, max_new: int, eos: set[int], pad_id: int):
    """Greedy decoding identical to model.generate(do_sample=False) for configs with no logits
    processors (verified for every panel checkpoint: none sets repetition/length penalties), except
    that a row that has emitted EOS is DROPPED from the batch and its KV cache (Cache.batch_select_indices)
    instead of being padded to the batch's longest row. Returns [B, max_new] token ids (pad after EOS)."""
    import torch
    ids, attn = enc["input_ids"], enc["attention_mask"]
    B = ids.shape[0]
    pos = attn.long().cumsum(-1) - 1
    pos.masked_fill_(attn == 0, 1)
    out = model(input_ids=ids, attention_mask=attn, position_ids=pos, use_cache=True, logits_to_keep=1)
    past = out.past_key_values
    nxt = out.logits[:, -1, :].argmax(-1)
    active = torch.arange(B)
    res = torch.full((B, max_new), pad_id, dtype=torch.long)
    cur_attn, cur_pos = attn, pos[:, -1]
    steps = 0
    for step in range(max_new):
        res[active, step] = nxt
        steps = step + 1
        done = torch.tensor([int(t) in eos for t in nxt.tolist()], dtype=torch.bool)
        if step == max_new - 1 or bool(done.all()):
            break
        if bool(done.any()):
            keep = (~done).nonzero().squeeze(1)
            past.batch_select_indices(keep)
            active, nxt, cur_attn, cur_pos = active[keep], nxt[keep], cur_attn[keep], cur_pos[keep]
        cur_attn = torch.cat([cur_attn, torch.ones((cur_attn.shape[0], 1), dtype=cur_attn.dtype)], dim=1)
        cur_pos = cur_pos + 1
        out = model(input_ids=nxt[:, None], attention_mask=cur_attn, position_ids=cur_pos[:, None],
                    past_key_values=past, use_cache=True, logits_to_keep=1)
        past = out.past_key_values
        nxt = out.logits[:, -1, :].argmax(-1)
    return res, steps


def generate_all(model, tok, items: list[dict], instruct: bool, batch: int, log_every: int = 1,
                 shrink: bool = False):
    import torch
    tok.padding_side = "left"
    rows = []
    t_all = time.time()
    with torch.no_grad():
        for b0 in range(0, len(items), batch):
            chunk = items[b0:b0 + batch]
            texts = [chat_text(tok, x["prompt"]) if instruct else x["prompt"] + "\n" for x in chunk]
            enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LEN,
                      add_special_tokens=not instruct)
            t0 = time.time()
            P = enc["input_ids"].shape[1]
            if shrink:
                newtok, nsteps = greedy_shrink(model, enc, MAX_NEW, _eos_ids(model, tok), tok.pad_token_id)
            else:
                gen = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=tok.pad_token_id)
                newtok, nsteps = gen[:, P:], gen.shape[1] - P
            dt = time.time() - t0
            for r, x in enumerate(chunk):
                new = newtok[r]
                n_new = int((new != tok.pad_token_id).sum().item()) if tok.pad_token_id is not None else int(new.numel())
                rows.append({"item_id": x["item_id"], "set": x["set"], "subset": x["subset"],
                             "prompt": x["prompt"], "response": tok.decode(new, skip_special_tokens=True).strip(),
                             "n_new_tokens": n_new, "prompt_tokens_padded": int(P)})
            if (b0 // batch) % log_every == 0:
                logger.info(f"    gen {min(b0 + batch, len(items))}/{len(items)} batch {dt:.0f}s "
                            f"(steps {nsteps}, shrink={shrink}, total {time.time() - t_all:.0f}s)")
    tok.padding_side = "right"
    return rows, time.time() - t_all


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="repo ids (default: whole panel in draw order)")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--limit-items", type=int, default=None)
    ap.add_argument("--no-shrink", action="store_true")
    ap.add_argument("--order", nargs="*", default=None, help="repo ids in the generation order to use")
    a = ap.parse_args()
    setup_logging("gen")
    import torch
    torch.set_num_threads(int(os.environ.get("GEN_THREADS", "2")))
    torch.manual_seed(0)
    panel = jload(RESULTS / "panel.json")["panel"]
    trim_p = RESULTS / "panel_trim.json"
    if trim_p.exists():
        dropped = set(jload(trim_p).get("dropped", []))
        panel = [p for p in panel if p["repo"] not in dropped]
    if a.only:
        panel = [p for p in panel if p["repo"] in set(a.only)]
    items = jload(ASSETS / "behaviour_items.json")["items"]
    if a.limit_items:
        items = items[: a.limit_items]
    tim_p = RESULTS / "gen_timings.json"
    timings = jload(tim_p) if tim_p.exists() else {}

    todo = [p for p in panel if not (GENS / f"{slug(p['repo'])}.jsonl").exists()]
    if a.order:
        rank = {r: i for i, r in enumerate(a.order)}
        todo = sorted(todo, key=lambda p: rank.get(p["repo"], 10_000))
    logger.info(f"generation: {len(todo)} checkpoints to do, {len(items)} items, batch {a.batch}")
    prefetch: dict[str, threading.Thread] = {}
    local_paths: dict[str, str] = {}

    def _pf(repo):
        try:
            local_paths[repo] = download(repo)
        except Exception as e:  # noqa: BLE001
            logger.error(f"prefetch failed {repo}: {e!r}")

    for i, p in enumerate(todo):
        repo = p["repo"]
        if trim_p.exists() and repo in set(jload(trim_p).get("dropped", [])):
            logger.warning(f"SKIP {repo}: dropped by the TIME rule (results/panel_trim.json)")
            continue
        t0 = time.time()
        if repo in prefetch:
            prefetch[repo].join()
        local = local_paths.get(repo) or download(repo)
        t_dl = time.time() - t0
        if i + 1 < len(todo):
            nxt = todo[i + 1]["repo"]
            th = threading.Thread(target=_pf, args=(nxt,), daemon=True)
            th.start()
            prefetch[nxt] = th
        try:
            t1 = time.time()
            model, tok, miss = load(repo, local)
            t_load = time.time() - t1
            if miss:
                Deviations.add("missing_tensors", f"{repo}: {len(miss)} missing tensors at load",
                               "weights did not bind", "checkpoint EXCLUDED")
                raise RuntimeError(f"{len(miss)} missing tensors")
            instruct = p["role"] != "base"
            borrowed = None
            if instruct and not getattr(tok, "chat_template", None):
                borrowed = sibling_template(p, jload(RESULTS / "panel.json")["panel"])
                if borrowed:
                    tok.chat_template = borrowed
                    Deviations.add("template_borrowed", f"{repo} ships no chat template; used its lineage "
                                   "sibling's template (same tokenizer)",
                                   "an SFT stage prompted without its chat format behaves like a base model",
                                   "applied identically at generation and harvest")
            texts_example = chat_text(tok, items[0]["prompt"]) if instruct else items[0]["prompt"] + "\n"
            use_shrink = (not a.no_shrink) and getattr(model.config, "model_type", "") != "lfm2"
            rows, t_gen = generate_all(model, tok, items, instruct, a.batch, shrink=use_shrink)
            for r in rows:
                r["slug"] = slug(repo)
                r["repo"] = repo
            out = GENS / f"{slug(repo)}.jsonl"
            tmp = Path(str(out) + ".tmp")
            with open(tmp, "w") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            tmp.replace(out)
            n_tok = sum(r["n_new_tokens"] for r in rows)
            timings[repo] = {"t_download_s": t_dl, "t_load_s": t_load, "t_gen_s": t_gen, "n_items": len(rows),
                             "n_new_tokens": n_tok, "tok_per_s": n_tok / max(t_gen, 1e-9),
                             "params": sum(x.numel() for x in model.parameters()), "batch": a.batch,
                             "decoder": "greedy_shrink (EOS rows dropped from batch+KV)" if use_shrink else "hf_generate",
                             "instruct_format": instruct, "template_borrowed": bool(borrowed),
                             "prompt_render_example": texts_example[:400], "utc_done": utc_now()}
            jdump(timings, tim_p)
            logger.info(f"DONE {repo}: gen {t_gen:.0f}s, {n_tok} new tokens ({n_tok / t_gen:.1f} tok/s), "
                        f"load {t_load:.0f}s, dl {t_dl:.0f}s")
            del model, tok
            gc.collect()
        except Exception as e:  # noqa: BLE001
            logger.exception(f"FAILED {repo}: {e!r}")
            timings[repo] = {"failed": repr(e)[:500], "utc": utc_now()}
            jdump(timings, tim_p)
            gc.collect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
