"""TESTING PLAN items 2-4, per panel checkpoint (run AFTER the harvest; post-prereg, so hooks are allowed).

For every harvested panel checkpoint (loaded exactly as src/harvest_panel.py loads it):
  determinism  -- re-run the prompt-site pass (h2 harvest.p_harvest) on the harvest's FIRST batch (the 8
                  shortest prompts, i.e. the identical batch composition) and compare with the saved
                  A_prompt / r_refusal / r_control rows: max abs diff (plan threshold 1e-2 in fp16).
  layer-0      -- hidden_states[0] at the last prompt token equals the input-embedding lookup.
  lens/index   -- (i) hidden_states[-1] equals final_norm(raw output of the last decoder block) (captured by
                  a forward hook), i.e. the last slice is POST-norm; (ii) argmax(hidden_states[-1] @ W_U^T)
                  equals the model's own next-token argmax on 8/8 prompts (layer indexing is right);
                  (iii) agreement of the iteration-2 lens at the final slice, which applies final_norm to
                  hidden_states[-1] again (BL1 is defined on that slice -- recorded, not changed).
Peak RSS of this process (VmHWM) is recorded. Writes results/hook_checks.json.
"""
from __future__ import annotations

import gc
import os
import sys
import time
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "h2"))
from common import H2, HARVEST, RESULTS, jdump, jload, setup_logging, slug, utc_now  # noqa: E402
from loguru import logger  # noqa: E402


def vmhwm_gb() -> float:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmHWM:"):
            return int(line.split()[1]) / 1024 / 1024
    return float("nan")


def check_one(entry: dict, stimuli: list[dict], token_sets: dict) -> dict:
    import torch
    from harvest import _encode_token_sets, _lens_parts, encode_batch, p_harvest, render_prompt
    from harvest_panel import CFG, load_model
    repo = entry["repo"]
    tag = slug(repo)
    d = HARVEST / tag
    t0 = time.time()
    model, tok, local, _ = load_model(repo, random_init=False)
    if entry.get("template_borrowed_from_sibling") and not getattr(tok, "chat_template", None):
        from gen import sibling_template
        tmpl = sibling_template(entry, jload(RESULTS / "panel.json")["panel"])
        if tmpl:
            tok.chat_template = tmpl
    token_ids = _encode_token_sets(tok, token_sets)
    texts = [render_prompt(tok, s["text"], "chat") for s in stimuli]
    order = np.argsort([len(t) for t in texts], kind="mergesort")
    first = order[: CFG["batch_prompt"]]
    sub = [texts[i] for i in first]
    row = {"repo": repo, "tag": tag, "model_type": model.config.model_type,
           "n_layers": int(model.config.num_hidden_layers), "t_load_s": time.time() - t0}
    # ---- determinism on the identical first batch
    with torch.no_grad():
        ph = p_harvest(model, tok, sub, max_len=CFG["max_len_prompt"], batch_size=len(sub),
                       token_ids=token_ids, lens_chunk=CFG["lens_chunk"], progress_every=0)
    A_old = np.load(d / "A_prompt.npy", mmap_mode="r")[first].astype(np.float32)
    A_new = ph["A"].astype(np.float32)
    row["determinism_max_abs_diff_A"] = float(np.abs(A_new - A_old).max())
    row["determinism_exact_A"] = bool(np.array_equal(A_new, A_old))
    for k in ("r_refusal", "r_control"):
        old = np.load(d / f"{k}.npy")[first]
        row[f"determinism_max_abs_diff_{k}"] = float(np.abs(ph[k] - old).max())
    row["determinism_pass"] = bool(row["determinism_max_abs_diff_A"] < 1e-2)
    # ---- layer-0, post-norm last slice, logit-lens argmax
    cap = {}
    layers = model.model.layers

    def hook(_m, _inp, out):
        cap["raw_last"] = (out[0] if isinstance(out, (tuple, list)) else out).detach()

    h = layers[-1].register_forward_hook(hook)
    try:
        ids, mask = encode_batch(tok, sub, CFG["max_len_prompt"])
        with torch.no_grad():
            out = model(input_ids=ids, attention_mask=mask, output_hidden_states=True, use_cache=False)
    finally:
        h.remove()
    hs = out.hidden_states
    b = ids.shape[0]
    last = mask.sum(dim=1) - 1
    ar = torch.arange(b)
    with torch.no_grad():
        emb = model.get_input_embeddings()(ids)
        row["layer0_equals_embedding_max_abs_diff"] = float((hs[0][ar, last].float() - emb[ar, last].float()).abs().max())
        W_U, fn = _lens_parts(model)
        raw = cap["raw_last"][ar, last]
        normed = fn(raw) if fn is not None else raw
        row["last_slice_is_post_norm_max_abs_diff"] = float((hs[-1][ar, last].float() - normed.float()).abs().max())
        row["last_slice_equals_raw_block_output"] = bool(torch.equal(hs[-1][ar, last], raw))
        logits = out.logits[ar, last].float()
        z1 = hs[-1][ar, last].float() @ W_U.float().T
        z2 = fn(hs[-1][ar, last].to(W_U.dtype)).float() @ W_U.float().T if fn is not None else z1
        am = logits.argmax(-1)
        row["argmax_agree_lens_single_norm"] = int((z1.argmax(-1) == am).sum())
        row["argmax_agree_h2_lens_final_slice"] = int((z2.argmax(-1) == am).sum())
        row["n_prompts"] = int(b)
        row["logits_vs_hs_last_WU_max_abs_diff"] = float((z1 - logits).abs().max())
        row["logits_scale"] = float(logits.abs().max())
    row["layer0_pass"] = bool(row["layer0_equals_embedding_max_abs_diff"] < 1e-3)
    row["lens_index_pass"] = bool(row["argmax_agree_lens_single_norm"] == b)
    row["final_slice_note"] = ("hidden_states[-1] is post-final-norm; the iteration-2 lens applies final_norm again "
                               "at l = L, so BL1 / fullV_final are read on norm(norm(h_L)) -- identical to the "
                               "iteration-2 definition (kept for comparability)"
                               if row["last_slice_is_post_norm_max_abs_diff"] < 1e-2 and not row["last_slice_equals_raw_block_output"]
                               else "see numbers")
    row["peak_rss_gb_vmhwm"] = vmhwm_gb()
    row["t_total_s"] = time.time() - t0
    del model, out, hs, ph
    gc.collect()
    return row


def main() -> int:
    setup_logging("verify_hooks")
    import torch
    torch.set_num_threads(int(os.environ.get("HARVEST_THREADS", "2")))
    stimuli = jload(H2 / "assets/stimuli.json")["rows"]
    token_sets = jload(H2 / "assets/token_sets.json")
    token_sets = {k: v for k, v in token_sets.items() if k in ("refusal", "hedge", "control")} \
        if isinstance(token_sets, dict) and "refusal" in token_sets else token_sets.get("sets", token_sets)
    panel = jload(RESULTS / "panel.json")["panel"]
    dropped = set(jload(RESULTS / "panel_trim.json")["dropped"])
    todo = [p for p in panel if p["repo"] not in dropped and (HARVEST / slug(p["repo"]) / "DONE").exists()]
    out_p = RESULTS / "hook_checks.json"
    prev = jload(out_p) if out_p.exists() else {"rows": []}
    done = {r["repo"] for r in prev["rows"] if "error" not in r}
    rows = [r for r in prev["rows"] if r["repo"] in done]
    for p in todo:
        if p["repo"] in done:
            continue
        try:
            r = check_one(p, stimuli, token_sets)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"hook check failed for {p['repo']}")
            r = {"repo": p["repo"], "error": repr(e)[:400]}
        logger.info(f"{p['repo']}: " + ", ".join(f"{k}={v}" for k, v in r.items()
                                                 if k.endswith(("pass", "diff_A", "single_norm", "final_slice", "error"))))
        rows.append(r)
        jdump({"utc": utc_now(), "rows": rows}, out_p)
        gc.collect()
    ok = [r for r in rows if "error" not in r]
    summ = {"n": len(rows), "n_error": len(rows) - len(ok),
            "all_determinism_pass": all(r["determinism_pass"] for r in ok),
            "all_layer0_pass": all(r["layer0_pass"] for r in ok),
            "all_lens_index_pass": all(r["lens_index_pass"] for r in ok),
            "max_peak_rss_gb": max((r["peak_rss_gb_vmhwm"] for r in ok), default=None)}
    jdump({"utc": utc_now(), "summary": summ, "rows": rows}, out_p)
    logger.info(f"hook checks: {summ}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
