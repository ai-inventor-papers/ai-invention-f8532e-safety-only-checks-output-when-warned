"""PHASE A (behaviour first) -- greedy generation on the 90 Lane C items. NO hooks, no hidden states.

Adapted from src/ref_i3/gen.py (the iteration-3 panel protocol = Lane C lc_harvest.py generate():
MAX_LEN=224 prompt truncation, MAX_NEW=140, greedy, left-padded batches, chat-template fallback chain
for instruct roles (add_generation_prompt=True, enable_thinking=False -> without enable_thinking ->
request+"\\n"), base / instruct_noformat roles = request+"\\n" with add_special_tokens=True).
Iteration-4 additions:
  * in-house NO-OP variants of the no-op parents: NOOP_sysprompt (template + fixed neutral system prompt)
    and NOOP_fp32 (same weights loaded in float32); tags <slug>__NOOP_*;
  * pure greedy everywhere: greedy_shrink (EOS rows dropped from batch + KV) for attention-only models,
    HF generate with every logits processor OFF for hybrids / remote-code models (recorded);
  * trust_remote_code tried once for repos that need it (rule e4); a second failure excludes the repo;
  * the TIME rule of assets/panel_rule.json, applied mechanically after runs 1, 5, 10, 15, ...
CPU-only box (no GPU): 2 threads. ONE long-lived process; the next repo is prefetched in a thread.
Outputs: private/gens/<tag>.jsonl (never released), results/gen_timings.json, results/time_rule.json,
results/panel_trim.json.
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ASSETS, GENS, HF_CACHE, PRIVATE, RESULTS, Deviations, jdump, jload,  # noqa: E402
                    setup_logging, slug, utc_now)

TEST_MODE = bool(os.environ.get("GEN_TEST"))
if TEST_MODE:  # smoke tests never touch the real gens / timings / trim files
    GENS = PRIVATE / "gens_test"
    GENS.mkdir(parents=True, exist_ok=True)
from loguru import logger  # noqa: E402

MAX_LEN = 224     # lc_harvest.py:57
MAX_NEW = 140     # lc_harvest.py:60
DL_PATTERNS = ["*.json", "*.safetensors", "*.model", "*.txt", "*.jinja", "*.tiktoken", "tokenizer*", "*.py"]
NEUTRAL_SYSPROMPT = "You are a helpful assistant."
DEADLINE_UTC = datetime(2026, 9, 21, 20, 30, tzinfo=timezone.utc)
HYBRID_TYPES = {"zamba2", "falcon_h1", "lfm2", "mamba", "mamba2", "jamba", "bamba", "nemotron_h"}
FP32_COST = 4.0   # results/fp16_benchmark.json: fp32 matmul ~4x bf16 on this CPU


def download(repo: str) -> str:
    from huggingface_hub import snapshot_download
    last = None
    for attempt in range(3):
        try:
            return snapshot_download(repo, cache_dir=str(HF_CACHE), allow_patterns=DL_PATTERNS)
        except Exception as e:  # noqa: BLE001
            last = e
            logger.warning(f"download {repo} attempt {attempt}: {e!r}"[:300])
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"download failed: {repo}: {last!r}"[:300])


def chat_text(tok, request: str, system: str | None = None) -> str:
    """lc_harvest.py:239-249 fallback chain (verbatim via judge_ext_lanec._chat_text); optional system turn."""
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": request}]
    for kw in (dict(add_generation_prompt=True, enable_thinking=False, tokenize=False),
               dict(add_generation_prompt=True, tokenize=False)):
        try:
            return tok.apply_chat_template(msgs, **kw)
        except Exception:  # noqa: BLE001
            continue
    return ((system + "\n\n") if system else "") + request + "\n"


def run_list(panel: list[dict], second_variant: str) -> list[dict]:
    """Generation order of the rule: mandatory (draw order) -> 2nd no-op variants -> FILL -> NOOP_fp32."""
    mand = [dict(p, variant="canonical") for p in panel if p["mandatory"]]
    fill = [dict(p, variant="canonical") for p in panel if not p["mandatory"]]
    v2 = [dict(p, variant=second_variant) for p in panel if p.get("noop_variants")]
    v32 = [dict(p, variant="NOOP_fp32") for p in panel if p.get("noop_variants")]
    out = mand + v2 + fill + v32
    for r in out:
        r["tag"] = slug(r["repo"]) + ("" if r["variant"] == "canonical" else f"__{r['variant']}")
    return out


def load(repo: str, local: str, dtype_name: str, trust: bool):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dt = {"bfloat16": torch.bfloat16, "float32": torch.float32, "float16": torch.float16}[dtype_name]
    tok = AutoTokenizer.from_pretrained(local, trust_remote_code=trust)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model, info = AutoModelForCausalLM.from_pretrained(local, dtype=dt, low_cpu_mem_usage=True,
                                                       output_loading_info=True, trust_remote_code=trust)
    model.eval()
    miss = list((info or {}).get("missing_keys", []) or [])
    return model, tok, miss


def _eos_ids(model, tok) -> set[int]:
    e = getattr(model.generation_config, "eos_token_id", None)
    if e is None:
        e = tok.eos_token_id
    return set(e if isinstance(e, (list, tuple)) else [e]) - {None}


def greedy_shrink(model, enc, max_new: int, eos: set[int], pad_id: int):
    """Greedy decoding (argmax, no logits processors) with EOS rows DROPPED from the batch and its KV cache
    (Cache.batch_select_indices). Verbatim from src/ref_i3/gen.py (token-identical to HF generate on 8/8
    rows in iteration 3). Returns [B, max_new] token ids (pad after EOS)."""
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


def render(tok, request: str, role: str, variant: str) -> tuple[str, bool]:
    """(text, add_special_tokens)."""
    if role in ("base", "instruct_noformat"):
        return request + "\n", True
    return chat_text(tok, request, NEUTRAL_SYSPROMPT if variant == "NOOP_sysprompt" else None), False


def generate_all(model, tok, items: list[dict], role: str, variant: str, batch: int, shrink: bool):
    import torch
    tok.padding_side = "left"
    rows = []
    t_all = time.time()
    with torch.no_grad():
        for b0 in range(0, len(items), batch):
            chunk = items[b0:b0 + batch]
            rendered = [render(tok, x["prompt"], role, variant) for x in chunk]
            texts = [t for t, _ in rendered]
            enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=MAX_LEN,
                      add_special_tokens=rendered[0][1])
            enc = {k: v for k, v in enc.items() if k in ("input_ids", "attention_mask")}
            t0 = time.time()
            P = enc["input_ids"].shape[1]
            if shrink:
                newtok, nsteps = greedy_shrink(model, enc, MAX_NEW, _eos_ids(model, tok), tok.pad_token_id)
            else:
                gen = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False, pad_token_id=tok.pad_token_id,
                                     repetition_penalty=1.0, no_repeat_ngram_size=0, temperature=None,
                                     top_p=None, top_k=None, min_new_tokens=0)
                newtok, nsteps = gen[:, P:], gen.shape[1] - P
            dt = time.time() - t0
            eos = _eos_ids(model, tok)
            for r, x in enumerate(chunk):
                new = newtok[r].tolist()
                # count up to (and including) the first EOS; pad ids after EOS are not new tokens
                n_new = 0
                for t in new:
                    n_new += 1
                    if t in eos:
                        break
                rows.append({"item_id": x["item_id"], "set": x["set"], "subset": x["subset"],
                             "prompt": x["prompt"],
                             "response": tok.decode(newtok[r][:n_new], skip_special_tokens=True).strip(),
                             "n_new_tokens": n_new, "prompt_tokens_padded": int(P)})
            logger.info(f"    gen {min(b0 + batch, len(items))}/{len(items)} batch {dt:.0f}s "
                        f"(steps {nsteps}, shrink={shrink}, total {time.time() - t_all:.0f}s)")
    tok.padding_side = "right"
    return rows, time.time() - t_all


def has_logits_processors(model) -> list[str]:
    gc_ = model.generation_config
    bad = []
    if (getattr(gc_, "repetition_penalty", 1.0) or 1.0) != 1.0:
        bad.append(f"repetition_penalty={gc_.repetition_penalty}")
    if getattr(gc_, "no_repeat_ngram_size", 0):
        bad.append(f"no_repeat_ngram_size={gc_.no_repeat_ngram_size}")
    if getattr(gc_, "bad_words_ids", None):
        bad.append("bad_words_ids")
    if getattr(gc_, "suppress_tokens", None):
        bad.append("suppress_tokens")
    if getattr(gc_, "begin_suppress_tokens", None):
        bad.append("begin_suppress_tokens")
    return bad


# ----------------------------------------------------------------------------------------------
# TIME RULE
# ----------------------------------------------------------------------------------------------
def apply_time_rule(runs: list[dict], done_tags: set[str], timings: dict, trim: dict, n_done: int) -> dict:
    """Mechanical: project the rest (gen + judge + core harvest) with the measured s/param; drop
    NOOP_fp32 variants (reverse draw order) then FILL members (reverse draw order, never breaking the
    >= 8 family quota) until the projection ends before DEADLINE_UTC."""
    fin = [timings[r["tag"]] for r in runs if r["tag"] in done_tags and r["tag"] in timings
           and "t_gen_s" in timings[r["tag"]]]
    if not fin:
        return trim
    spp = sum(t["t_gen_s"] / (FP32_COST if t.get("dtype") == "float32" else 1.0) for t in fin) / \
        max(sum(t["params"] for t in fin), 1)
    ov = sorted(t.get("t_download_s", 0) + t.get("t_load_s", 0) for t in fin)
    if len(ov) > 1:
        ov = ov[:-1]  # the largest value carries a process's one-time start-up (imports from MooseFS)
    over = ov[len(ov) // 2]
    harvest_ratio = float(trim.get("harvest_ratio_measured") or 1.0)
    dropped = set(trim.get("dropped", []))
    failed_repos = {f["repo"] for f in trim.get("failed", [])}

    def cost(r):
        c = r["params_total"] * spp * (FP32_COST if r["variant"] == "NOOP_fp32" else 1.0)
        return c + over

    def projection():
        rem = [r for r in runs if r["tag"] not in done_tags and r["tag"] not in dropped
               and r["repo"] not in failed_repos]
        gen = sum(cost(r) for r in rem)
        harv = sum(cost(r) for r in runs if r["tag"] not in dropped and r["repo"] not in failed_repos) * harvest_ratio
        return gen + harv, rem

    now = datetime.now(timezone.utc)
    budget = (DEADLINE_UTC - now).total_seconds()
    proj, rem = projection()
    log = {"utc": utc_now(), "after_n_runs": n_done, "sec_per_param": spp, "overhead_s": over,
           "harvest_ratio": harvest_ratio, "budget_s": budget, "projection_s_before": proj, "dropped_now": []}
    failed_repos = {f["repo"] for f in trim.get("failed", [])}
    fams_after = lambda: {r["family"] for r in runs if r["variant"] == "canonical" and r["tag"] not in dropped
                          and r["repo"] not in failed_repos}
    while proj > budget:
        cand = [r for r in reversed(runs) if r["variant"] == "NOOP_fp32" and r["tag"] not in done_tags
                and r["tag"] not in dropped]
        if not cand:
            cand = []
            for r in reversed(runs):
                if r["variant"] != "canonical" or r["mandatory"] or r["tag"] in done_tags or r["tag"] in dropped:
                    continue
                fam_left = {x["family"] for x in runs if x["variant"] == "canonical" and x["tag"] not in dropped
                            and x["tag"] != r["tag"] and x["repo"] not in failed_repos}
                if len(fam_left) < 8 and r["family"] not in fam_left:
                    continue
                cand.append(r)
        if not cand:
            log["note"] = "nothing droppable left (mandatory / family quota); projection still over budget"
            break
        dropped.add(cand[0]["tag"])
        log["dropped_now"].append(cand[0]["tag"])
        proj, rem = projection()
    # v2 (deviation time_rule_v2_restore): the n=1 evaluation carried one-time process start-up
    # (transformers import from MooseFS) in the per-checkpoint overhead. When the projection shows
    # slack, previously dropped members are RESTORED mechanically in the reverse of the drop order
    # (FILL in draw order first, NOOP_fp32 last), each only if the projection with it still fits.
    # Timing-only: no outcome or activation is read.
    log["restored_now"] = []
    if proj <= budget and dropped:
        rest_order = [r for r in runs if r["tag"] in dropped and r["variant"] == "canonical"] + \
                     [r for r in runs if r["tag"] in dropped and r["variant"] == "NOOP_fp32"]
        for r in rest_order:
            dropped.discard(r["tag"])
            p2, _ = projection()
            if p2 <= budget:
                proj = p2
                log["restored_now"].append(r["tag"])
            else:
                dropped.add(r["tag"])
                break
    log["projection_s_after"] = proj
    log["families_after"] = sorted(fams_after())
    trim["dropped"] = sorted(dropped)
    trim.setdefault("log", []).append(log)
    if not TEST_MODE:
        jdump(trim, RESULTS / "panel_trim.json")
        jdump(trim["log"], RESULTS / "time_rule.json")
    logger.info(f"TIME RULE after {n_done} runs: s/param {spp:.2e}, projection {proj / 60:.0f} min vs budget "
                f"{budget / 60:.0f} min; dropped now {log['dropped_now']}")
    return trim


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None, help="tags (default: whole run list in rule order)")
    ap.add_argument("--batch", type=int, default=45)
    ap.add_argument("--limit-items", type=int, default=None)
    ap.add_argument("--no-time-rule", action="store_true")
    a = ap.parse_args()
    setup_logging("gen")
    import torch
    torch.set_num_threads(int(os.environ.get("GEN_THREADS", "2")))
    torch.manual_seed(0)
    pj = jload(RESULTS / "panel.json")
    panel = pj["panel"]
    amend_p = RESULTS / "panel_amend.json"
    excluded_by_amend = {}
    if amend_p.exists():  # hash-chained amendments applying the frozen rule (e4 exclusions, no-op replacement)
        for am in jload(amend_p)["amendments"]:
            if am["type"] == "exclude":
                excluded_by_amend[am["repo"]] = am
            elif am["type"] == "noop_parent_replacement":
                for q in panel:
                    if q["repo"] == am["old"]:
                        q.pop("noop_variants", None)
                    if q["repo"] == am["new"]:
                        q["noop_variants"] = ["NOOP_fp32", pj["noop_second_variant"]]
                        q["mandatory"] = True
                        q["noop_parent_via_amendment"] = True
        panel = [q for q in panel if q["repo"] not in excluded_by_amend]
    runs = run_list(panel, pj["noop_second_variant"])
    jdump([{k: r[k] for k in ("tag", "repo", "variant", "role", "family", "mandatory", "draw_index", "params_total")}
           for r in runs], RESULTS / "run_list.json")
    items = [x for x in jload(ASSETS / "behaviour_items.json")["items"] if x["subset"] == "laneC"]
    if a.limit_items:
        items = items[: a.limit_items]
    tim_p = RESULTS / ("test/gen_timings_test.json" if TEST_MODE else "gen_timings.json")
    timings = jload(tim_p) if tim_p.exists() else {}
    trim_p = RESULTS / ("test/panel_trim_test.json" if TEST_MODE else "panel_trim.json")
    trim = jload(trim_p) if trim_p.exists() else {"dropped": [], "failed": [], "log": []}
    for repo, am in excluded_by_amend.items():
        if repo not in {f["repo"] for f in trim.get("failed", [])}:
            trim.setdefault("failed", []).append({"repo": repo, "tag": slug(repo), "stage": "precheck (rule e4)",
                                                  "reason": am.get("evidence"), "utc": utc_now()})
    if not TEST_MODE:
        jdump(trim, trim_p)
    if a.only:
        runs = [r for r in runs if r["tag"] in set(a.only)]
    done_tags = {r["tag"] for r in runs if (GENS / f"{r['tag']}.jsonl").exists()}
    logger.info(f"generation: {len(runs)} runs ({len(done_tags)} already done), {len(items)} items, batch {a.batch}")
    local_paths: dict[str, str] = {}
    prefetch: dict[str, threading.Thread] = {}

    def _pf(repo):
        try:
            local_paths[repo] = download(repo)
        except Exception as e:  # noqa: BLE001
            logger.error(f"prefetch failed {repo}: {e!r}")

    n_run = len(done_tags)
    if not a.no_time_rule and n_run and (RESULTS / "gen_timings.json").exists() and not TEST_MODE:
        trim = apply_time_rule(runs, done_tags, timings, trim, n_run)
    while True:
        trim = jload(trim_p) if trim_p.exists() else trim
        failed_repos = {f["repo"] for f in trim.get("failed", [])}
        pend = [(i, x) for i, x in enumerate(runs) if x["tag"] not in done_tags
                and x["tag"] not in set(trim.get("dropped", [])) and x["repo"] not in failed_repos]
        if not pend:
            break
        i, r = pend[0]
        tag, repo = r["tag"], r["repo"]
        t0 = time.time()
        if repo in prefetch:
            prefetch[repo].join()
        try:
            local = local_paths.get(repo) or download(repo)
        except Exception as e:  # noqa: BLE001
            trim.setdefault("failed", []).append({"repo": repo, "tag": tag, "stage": "download", "reason": repr(e)[:300]})
            jdump(trim, trim_p)
            continue
        t_dl = time.time() - t0
        nxt = next((x["repo"] for x in runs[i + 1:] if x["repo"] != repo and x["tag"] not in done_tags
                    and x["tag"] not in set(trim.get("dropped", []))), None)
        if nxt and nxt not in prefetch:
            th = threading.Thread(target=_pf, args=(nxt,), daemon=True)
            th.start()
            prefetch[nxt] = th
        dtype = "float32" if r["variant"] == "NOOP_fp32" else "bfloat16"
        trust = bool(r.get("trust_remote_code"))
        attempts = [("greedy_shrink", trust), ("hf_generate", True if trust else False)]
        mt = (r.get("model_type") or "").lower()
        if mt in HYBRID_TYPES or trust:
            attempts = [("hf_generate", trust)]
        err_log = []
        ok = False
        for decoder, trust_now in attempts:
            try:
                t1 = time.time()
                model, tok, miss = load(repo, local, dtype, trust_now)
                t_load = time.time() - t1
                if miss:
                    raise RuntimeError(f"{len(miss)} missing tensors at load: {miss[:5]}")
                lp = has_logits_processors(model)
                use_shrink = decoder == "greedy_shrink"
                ex_text = render(tok, items[0]["prompt"], r["role"], r["variant"])[0]
                rows, t_gen = generate_all(model, tok, items, r["role"], r["variant"], a.batch, shrink=use_shrink)
                for row in rows:
                    row["tag"], row["repo"], row["variant"] = tag, repo, r["variant"]
                out = GENS / f"{tag}.jsonl"
                tmp = Path(str(out) + ".tmp")
                with open(tmp, "w") as f:
                    for row in rows:
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                tmp.replace(out)
                n_tok = sum(x["n_new_tokens"] for x in rows)
                timings[tag] = {"repo": repo, "variant": r["variant"], "dtype": dtype, "t_download_s": t_dl,
                                "t_load_s": t_load, "t_gen_s": t_gen, "n_items": len(rows), "n_new_tokens": n_tok,
                                "tok_per_s": n_tok / max(t_gen, 1e-9),
                                "params": sum(x.numel() for x in model.parameters()),
                                "batch": a.batch, "decoder": decoder, "trust_remote_code": trust_now,
                                "generation_config_logits_processors_turned_off": lp,
                                "model_type": getattr(model.config, "model_type", None),
                                "prompt_render_example": ex_text[:400], "utc_done": utc_now(),
                                "failed_attempts": err_log}
                jdump(timings, tim_p)
                logger.info(f"DONE {tag}: gen {t_gen:.0f}s, {n_tok} new tokens ({n_tok / t_gen:.1f} tok/s), "
                            f"load {t_load:.0f}s, dl {t_dl:.0f}s, decoder {decoder}")
                del model, tok
                gc.collect()
                ok = True
                break
            except Exception as e:  # noqa: BLE001
                logger.exception(f"attempt {decoder} (trust={trust_now}) FAILED {tag}: {e!r}")
                err_log.append({"decoder": decoder, "trust_remote_code": trust_now, "error": repr(e)[:400]})
                gc.collect()
        if not ok:
            trim.setdefault("failed", []).append({"repo": repo, "tag": tag, "stage": "load/generate",
                                                  "attempts": err_log, "utc": utc_now()})
            jdump(trim, trim_p)
            Deviations.add("checkpoint_failed", f"{tag}: excluded after {len(err_log)} attempts",
                           "rule e4 / plan fallback 3", "excluded with its reason; quotas recomputed")
            done_tags.add(tag)  # never retried in this process
            continue
        done_tags.add(tag)
        n_run += 1
        if not a.no_time_rule and (n_run == 1 or n_run % 5 == 0):
            trim = apply_time_rule(runs, done_tags, timings, trim, n_run)
    if not TEST_MODE:
        (RESULTS / "gen_sweep_finished.flag").write_text(utc_now())
    logger.info("generation sweep finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
