"""STEP 4 -- ACTIVATION HARVEST, iteration-2 protocol, AFTER graded truth + prereg are hash-committed.

Re-uses the iteration-2 kernels VERBATIM (copied into src/h2/, sha256 of each original in
results/provenance.json): harvest.p_harvest (last prompt token, all L+1 hidden-state slices, fp16,
per-layer logit-lens set log-sum-exps), harvest.u_summary (unembedding rows / moments),
c_harvest2.c_harvest_v2 (teacher-forced 96 XSTest cells, early/late response windows, per-model
re-tokenised action-slot check, exact causal truncation), wsummary.w_summary_repo (weights only).
Output layout = the iteration-2 harvest layout, so the screen's code can re-score this panel as is:
    harvest/<tag>/{A_prompt,norms,r_refusal,r_hedge,r_control,r_fullV_final,A_resp,cell_kept,
                   cell_slot_ok,S_U,WU_ref,WU_hed,WU_ctl,mu_U,gamma,hbar,hbar_all,svals_stacked,
                   vmin_stacked}.npy, gram/G_###.npy, meta.json, c_meta.json, w_meta.json,
                   token_ids.json, A_c11.npy (+ DONE, C_DONE, W_DONE, MANIFEST.sha256.json)

ORDER GATE: a panel checkpoint is refused unless hash_chain.jsonl holds graded_truth.json THEN
prereg.json and both files still hash to the recorded values. The random-init control is not a panel
member, so it may run before truth as the pipeline smoke test (`--smoke`).
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import time
import traceback
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "h2"))
from common import (ASSETS, H2, HARVEST, HF_CACHE, RESULTS, WS, Deviations, chain_records,  # noqa: E402
                    jdump, jload, setup_logging, sha256_file, slug, utc_now)
from loguru import logger  # noqa: E402

CFG = {  # H2 prereg.json config values that the kernels read (verbatim), except where noted
    "dtype": "bfloat16", "attn": "sdpa", "max_len_prompt": 192, "max_len_cell": 288,
    "batch_prompt": 8, "batch_cell": 4, "lens_chunk": 8, "early_window": [5, 20], "late_window": [40, 55],
    "x5_positions": 32, "keep_cont_tokens": 56, "cells_mode": "all",
    "x5_cell_index": [],  # DEVIATION: D_resp (48 x L x 32 x d) is not harvested -- not read by C1-C14
}


def order_gate(tag_is_panel: bool) -> dict:
    """graded_truth then prereg in hash_chain.jsonl, both re-verified."""
    if not tag_is_panel:
        return {"gate": "not a panel member (random-init control)"}
    recs = chain_records()
    names = [r["file"] for r in recs]
    try:
        i_t = names.index("results/graded_truth.json")
        i_p = names.index("prereg.json")
    except ValueError as e:
        raise SystemExit(f"ORDER GATE: missing chain record ({e}); refusing to hook a panel checkpoint")
    if not i_t < i_p:
        raise SystemExit("ORDER GATE: prereg was committed before graded truth")
    for i in (i_t, i_p):
        f = WS / recs[i]["file"]
        if sha256_file(f) != recs[i]["sha256"]:
            raise SystemExit(f"ORDER GATE: {f} changed after commit")
    return {"gate": "PASS", "truth_utc": recs[i_t]["utc"], "prereg_utc": recs[i_p]["utc"]}


def load_model(repo: str, random_init: bool, seed: int = 0):
    import torch
    from harvest import DTYPE_MAP, _torch
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer
    _torch()
    from gen import download
    local = download(repo)
    tok = AutoTokenizer.from_pretrained(local, trust_remote_code=False)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token or tok.unk_token
    tok.padding_side = "right"
    info = {}
    if random_init:
        torch.manual_seed(seed)
        np.random.seed(seed)
        conf = AutoConfig.from_pretrained(local)
        model = AutoModelForCausalLM.from_config(conf, dtype=DTYPE_MAP["bfloat16"])
    else:
        model, info = AutoModelForCausalLM.from_pretrained(local, dtype=DTYPE_MAP["bfloat16"],
                                                           low_cpu_mem_usage=True, attn_implementation="sdpa",
                                                           output_loading_info=True)
    model.eval()
    return model, tok, local, info


def c11_pass(model, tok, texts, max_len: int, batch: int) -> np.ndarray:
    """One extra prompt-only pass (last prompt token, all layers) on the 64 severity items."""
    from harvest import p_harvest
    ph = p_harvest(model, tok, texts, max_len=max_len, batch_size=batch, token_ids={}, lens_chunk=8)
    return ph["A"]


def manifest(out_dir: Path) -> dict:
    m = {}
    for p in sorted(out_dir.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.sha256.json":
            m[str(p.relative_to(out_dir))] = sha256_file(p)
    jdump(m, out_dir / "MANIFEST.sha256.json")
    return m


def harvest_one(entry: dict, stimuli: list[dict], cells_doc: dict, char_spans: dict, c11: list[dict],
                token_sets: dict, *, random_init: bool = False, tag: str | None = None) -> dict:
    import torch
    from c_harvest2 import _render_cells_local, c_harvest_v2
    from harvest import _encode_token_sets, _tok_len_stats, p_harvest, render_prompt, u_summary

    repo = entry["repo"]
    name = tag or slug(repo)
    out_dir = HARVEST / name
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "DONE").exists():
        logger.info(f"SKIP {name} (DONE)")
        return jload(out_dir / "meta.json")
    gate = order_gate(tag_is_panel=not random_init)
    t0 = time.time()
    model, tok, local, info = load_model(repo, random_init)
    t_load = time.time() - t0
    conf = model.config
    borrowed = False
    if entry.get("template_borrowed_from_sibling") and not getattr(tok, "chat_template", None):
        from gen import sibling_template
        tmpl = sibling_template(entry, jload(RESULTS / "panel.json")["panel"])
        if tmpl:
            tok.chat_template = tmpl
            borrowed = True
    meta = {"repo": repo, "tag": name, "template_mode": "chat", "random_init": bool(random_init),
            "role": entry.get("role"), "family": entry.get("family"),
            "n_layers": int(conf.num_hidden_layers), "hidden_size": int(conf.hidden_size),
            "vocab_size": int(getattr(conf, "vocab_size", 0)),
            "tie_word_embeddings": bool(getattr(conf, "tie_word_embeddings", False)),
            "dtype_loaded": "torch.bfloat16", "dtype_config": str(getattr(conf, "torch_dtype", None)),
            "rms_eps": float(getattr(conf, "rms_norm_eps", None) or getattr(conf, "layer_norm_eps", None) or 1e-6),
            "t_load_s": t_load, "timings": {}, "order_gate": gate, "local_snapshot": str(local),
            "chat_template_borrowed_from_sibling": borrowed,
            "has_chat_template": bool(getattr(tok, "chat_template", None)), "harvest_utc_start": utc_now()}
    if not random_init:
        miss = list((info or {}).get("missing_keys", []) or [])
        meta["load_missing_keys_n"] = len(miss)
        meta["weights_fully_bound"] = len(miss) == 0
    token_ids = _encode_token_sets(tok, token_sets)
    meta["token_ids"] = {k: len(v) for k, v in token_ids.items()}
    jdump(token_ids, out_dir / "token_ids.json")

    # ---- P-HARVEST (256 stimuli)
    t = time.time()
    texts = [render_prompt(tok, s["text"], "chat") for s in stimuli]
    with torch.no_grad():
        ph = p_harvest(model, tok, texts, max_len=CFG["max_len_prompt"], batch_size=CFG["batch_prompt"],
                       token_ids=token_ids, lens_chunk=CFG["lens_chunk"])
    np.save(out_dir / "A_prompt.npy", ph["A"])
    np.save(out_dir / "norms.npy", ph["norms"])
    for k in ("r_refusal", "r_hedge", "r_control", "r_fullV_final"):
        if k in ph:
            np.save(out_dir / f"{k}.npy", ph[k])
    meta["timings"]["p_harvest_s"] = time.time() - t
    meta["n_prompts"] = len(stimuli)
    meta["prompt_token_lengths"] = _tok_len_stats(tok, texts, CFG["max_len_prompt"])
    meta["prompt_render_example"] = texts[0][:400]
    y = np.array([s["y"] for s in stimuli], dtype=np.int8)
    L1 = ph["A"].shape[1]
    hbar = ph["A"][y == 1, L1 - 1, :].astype(np.float32).mean(0)
    hbar_all = ph["A"][:, L1 - 1, :].astype(np.float32).mean(0)

    # ---- U-SUMMARY
    t = time.time()
    meta.update(u_summary(model, out_dir, token_ids, hbar, hbar_all, meta["rms_eps"]))
    meta["timings"]["u_summary_s"] = time.time() - t

    # ---- C-HARVEST v2 (96 teacher-forced XSTest cells)
    t = time.time()
    cells_r = _render_cells_local(tok, cells_doc["cells"], "chat")
    with torch.no_grad():
        ch = c_harvest_v2(model, tok, cells_r, char_spans, dict(CFG))
    np.save(out_dir / "A_resp.npy", ch["A_resp"])
    np.save(out_dir / "cell_kept.npy", ch["kept"])
    np.save(out_dir / "cell_slot_ok.npy", ch["slot_ok"])
    n_cells = len(cells_doc["cells"])
    n_kept = int(ch["kept"].sum())
    c_meta = {"tag": name, "repo": repo, "template_mode": "chat", "random_init": bool(random_init),
              "n_cells": n_cells, "n_kept": n_kept, "n_slot_ok": int(ch["slot_ok"].sum()),
              "drop_frac": 1.0 - n_kept / n_cells, "x5_undefined": bool(1.0 - n_kept / n_cells > 0.20),
              "cells_harvested": "all", "D_resp": "NOT_HARVESTED (recorded deviation; not read by C1-C14)",
              "causal_truncation": {"kept_continuation_tokens": CFG["keep_cont_tokens"]},
              "timings": {"t_c_harvest_s": ch["elapsed_s"]},
              "n_plen_mismatches": len(ch["plen_mismatches"]), "plen_mismatches": ch["plen_mismatches"],
              "per_cell": ch["per_cell"], "ts": time.time()}
    jdump(c_meta, out_dir / "c_meta.json")
    (out_dir / "C_DONE").write_text(json.dumps({"ts": time.time()}))
    meta["timings"]["c_harvest_s"] = time.time() - t
    meta["n_cells"] = n_cells
    meta["n_cells_kept"] = n_kept

    # ---- C11 prompt pass (64 severity items)
    t = time.time()
    c11_texts = [render_prompt(tok, x["prompt"], "chat") for x in c11]
    with torch.no_grad():
        A_c11 = c11_pass(model, tok, c11_texts, CFG["max_len_prompt"], CFG["batch_prompt"])
    np.save(out_dir / "A_c11.npy", A_c11)
    meta["timings"]["c11_s"] = time.time() - t
    meta["n_c11"] = len(c11)
    meta["harvest_utc_end_forward"] = utc_now()
    del model, ph, ch
    gc.collect()

    # ---- W-SUMMARY (weights only, straight from the safetensors in native precision)
    t = time.time()
    if not random_init:
        try:
            from wsummary import w_summary_repo
            wm = w_summary_repo(repo, tag=name, store_gram=True, gram_dtype="float16", parts=("stacked",))
            meta["w_summary"] = {"n_layers_found": wm.get("n_layers_found"), "elapsed_s": wm.get("elapsed_s")}
        except Exception as e:  # noqa: BLE001
            meta["w_summary"] = {"error": repr(e)[:400]}
            Deviations.add("w_summary_failed", f"{repo}: {e!r}"[:300], "weight-only rows NaN for this checkpoint")
    else:
        try:
            _w_summary_live_random(repo, out_dir)
            meta["w_summary"] = {"source": "live random-init weights (seed 0)"}
        except Exception as e:  # noqa: BLE001
            meta["w_summary"] = {"error": repr(e)[:400]}
    meta["timings"]["w_summary_s"] = time.time() - t
    meta["timings"]["total_s"] = time.time() - t0
    meta["harvest_utc_end"] = utc_now()
    jdump(meta, out_dir / "meta.json")
    manifest(out_dir)
    (out_dir / "DONE").write_text(json.dumps({"ts": time.time(), "utc": utc_now(), "total_s": meta["timings"]["total_s"]}))
    logger.info(f"HARVESTED {name} in {meta['timings']['total_s']:.0f}s "
                f"(P {meta['timings']['p_harvest_s']:.0f}s, C {meta['timings']['c_harvest_s']:.0f}s, "
                f"C11 {meta['timings']['c11_s']:.0f}s, W {meta['timings']['w_summary_s']:.0f}s)")
    del tok
    gc.collect()
    return meta


def _w_summary_live_random(repo: str, out_dir: Path) -> None:
    """Random-init control: same Gram/extreme-eigenpair summary, from the live seeded random weights."""
    import scipy.linalg as sla
    import torch
    from transformers import AutoConfig, AutoModelForCausalLM
    from gen import download
    conf = AutoConfig.from_pretrained(download(repo))
    torch.manual_seed(0)
    model = AutoModelForCausalLM.from_config(conf, dtype=torch.float32)
    gdir = out_dir / "gram"
    gdir.mkdir(exist_ok=True)
    svals, vmins, fro2s, shapes = [], [], [], []
    for li, lyr in enumerate(model.model.layers):
        Wo = lyr.self_attn.o_proj.weight.detach().float()
        Wd = lyr.mlp.down_proj.weight.detach().float()
        M = torch.cat([Wo, Wd], dim=1)
        G = (M @ M.T).double()
        Gn = G.numpy()
        lo_w, lo_v = sla.eigh(Gn, subset_by_index=[0, 0], driver="evr")
        v = np.random.default_rng(li).standard_normal(Gn.shape[0])
        lam = 0.0
        for _ in range(60):
            v = Gn @ v
            lam = float(np.linalg.norm(v))
            v /= max(lam, 1e-300)
        svals.append(np.sqrt(np.clip([lam, float(lo_w[0])], 0, None)).astype(np.float32))
        vmins.append(lo_v[:, 0].astype(np.float32))
        fro2s.append(float(np.trace(Gn)))
        shapes.append([int(M.shape[0]), int(M.shape[1])])
        np.save(gdir / f"G_{li:03d}.npy", G.to(torch.float16).numpy())
    np.save(out_dir / "svals_stacked.npy", np.stack(svals))
    np.save(out_dir / "vmin_stacked.npy", np.stack(vmins))
    jdump({"repo": repo, "tag": out_dir.name, "random_init": True, "n_layers_found": len(svals),
           "parts": {"stacked": {"fro2": fro2s, "shapes": shapes}}}, out_dir / "w_meta.json")
    (out_dir / "W_DONE").write_text(json.dumps({"ts": time.time()}))
    del model
    gc.collect()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="random-init control only (allowed pre-truth)")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--smoke-limit", type=int, default=0, help="quick code-path test on a few items")
    a = ap.parse_args()
    setup_logging("harvest")
    import torch
    torch.set_num_threads(int(os.environ.get("HARVEST_THREADS", "2")))
    from c_harvest2 import slot_char_spans
    stimuli = jload(H2 / "assets/stimuli.json")["rows"]
    cells_doc = jload(H2 / "assets/cells.json")
    token_sets = jload(H2 / "assets/token_sets.json")
    token_sets = {k: v for k, v in token_sets.items() if k in ("refusal", "hedge", "control")} \
        if isinstance(token_sets, dict) and "refusal" in token_sets else token_sets.get("sets", token_sets)
    c11 = jload(ASSETS / "c11_items.json")["items"]
    sc_p = RESULTS / "cell_char_spans.json"
    if sc_p.exists():
        char_spans = jload(sc_p)["char_spans"]
    else:
        from huggingface_hub import snapshot_download
        qdir = snapshot_download("Qwen/Qwen3-4B", cache_dir=str(HF_CACHE),
                                 allow_patterns=["tokenizer*", "vocab.json", "merges.txt", "*.jinja", "config.json"])
        import c_harvest2
        sc = c_harvest2.slot_char_spans(cells_doc["cells"], tokenizer_repo=qdir)
        jdump(sc, sc_p)
        char_spans = sc["char_spans"]
    panel = jload(RESULTS / "panel.json")["panel"]
    trim_p = RESULTS / "panel_trim.json"
    dropped = set(jload(trim_p).get("dropped", [])) if trim_p.exists() else set()
    if a.smoke:
        first_instruct = [p for p in panel if p["role"] != "base" and p["repo"] not in dropped][0]
        entry = dict(first_instruct)
        tag = "RandInit-" + first_instruct["repo"].split("/")[-1]
        if a.smoke_limit:
            n = a.smoke_limit
            keep = []
            for g in sorted({(s["set_id"], s["y"]) for s in stimuli}):
                keep += [s for s in stimuli if (s["set_id"], s["y"]) == g][:n]
            stimuli = keep
            cells_doc = dict(cells_doc, cells=cells_doc["cells"][:n])
            c11 = c11[:n]
            tag += "_SMOKE"
        harvest_one(entry, stimuli, cells_doc, char_spans, c11, token_sets, random_init=True, tag=tag)
        return 0
    todo = [p for p in panel if p["repo"] not in dropped]
    if a.only:
        todo = [p for p in todo if p["repo"] in set(a.only)]
    fails = []
    for p in todo:
        try:
            harvest_one(p, stimuli, cells_doc, char_spans, c11, token_sets)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"HARVEST FAILED {p['repo']}: {e!r}")
            fails.append({"repo": p["repo"], "error": repr(e)[:500], "tb": traceback.format_exc()[-3000:]})
            jdump(fails, RESULTS / "harvest_failures.json")
        gc.collect()
    jdump(fails, RESULTS / "harvest_failures.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
