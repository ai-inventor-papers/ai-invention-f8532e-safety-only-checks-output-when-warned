"""C-HARVEST v2 -- the registered per-model action-slot window fix.

`harvest.c_harvest` checks the action-slot-in-window condition using the STORED Qwen3
TOKEN spans for every checkpoint's tokenizer, and keeps every cell regardless of that
check. The REGISTERED rule (config early_window/late_window, action_slot_spans) is:

    re-tokenise PER MODEL, recompute the action-slot token positions from the CELL
    TEXT, assert each cell's action slot intersects BOTH windows, and DROP + RECORD
    any cell where it does not. If more than 20% of cells drop for a checkpoint, X5
    and X11 are UNDEFINED for it.

This module fixes that without touching `harvest.py` (which the prompt-harvest sweep
is using live): the action slots were authored as Qwen3 TOKEN spans, so step 1 maps
those ONCE to CHARACTER spans in the continuation string (tokeniser-independent),
and step 2 re-tokenises prompt+continuation per model and maps those character spans
back to THAT model's token grid.

Two entry points:
  slot_char_spans   -- Qwen3-4B token spans -> character spans (once, no model load)
  c_harvest_v2      -- per-model forward pass + per-cell window/slot bookkeeping

Plus a resumable CLI driver (`main`) that loads one checkpoint at a time exactly the
way `harvest.harvest_one` does, runs c_harvest_v2, and writes A_resp.npy / D_resp.npy /
cell_kept.npy / cell_slot_ok.npy / c_meta.json / a C_DONE sentinel per tag.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import (  # noqa: E402
    ASSETS, HARVEST, RESULTS, WS, Deadline, jdump, jload, jload_maybe,
    set_all_seeds, setup_logging,
    save_npy_split,
)
from harvest import DTYPE_MAP, _torch, render_prompt  # noqa: E402
from loguru import logger  # noqa: E402

QWEN3_TOKENIZER_REPO = "Qwen/Qwen3-4B"


# ----------------------------------------------------------------------------------
# step 1: Qwen3 TOKEN spans (as stored in cells.json) -> CHARACTER spans, once
# ----------------------------------------------------------------------------------
def slot_char_spans(
    cells: list[dict], tokenizer_repo: str = QWEN3_TOKENIZER_REPO
) -> dict[str, Any]:
    """Character spans of each cell's action slot(s) inside its `continuation` string.

    Tokenises the continuation ALONE with the Qwen3-4B tokenizer (return_offsets_mapping,
    add_special_tokens=False -- the same convention the prompt/cell harvest uses), then
    maps the stored Qwen3 TOKEN spans (half-open) to char spans via that offset mapping.
    Also verifies every continuation tokenises to exactly `n_tokens_qwen` (144) Qwen3
    tokens, reporting any cell where it does not (the char-span map would be wrong for
    such a cell, since the stored spans were authored against exactly that tokenisation).
    """
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(tokenizer_repo)
    char_spans: dict[str, list[list[int] | None]] = {}
    mismatches: list[dict] = []
    for c in cells:
        cont = c["continuation"]
        enc = tok(cont, add_special_tokens=False, return_offsets_mapping=True)
        offs = enc["offset_mapping"]
        n = len(offs)
        expect = int(c.get("n_tokens_qwen", 144))
        if n != expect:
            mismatches.append({
                "cell_id": c["cell_id"], "n_tokens_actual": n, "n_tokens_expected": expect,
            })
        spans: list[list[int] | None] = []
        for s, e in c["action_slot_spans"]:
            if s < 0 or e > n or s >= e:
                spans.append(None)
                continue
            spans.append([int(offs[s][0]), int(offs[e - 1][1])])
        char_spans[c["cell_id"]] = spans
    del tok
    logger.info(f"slot_char_spans: {len(cells)} cells, {len(mismatches)} tokenisation "
                f"mismatches under {tokenizer_repo}")
    return {"char_spans": char_spans, "mismatches": mismatches,
            "tokenizer_repo": tokenizer_repo, "n_cells": len(cells)}


# ----------------------------------------------------------------------------------
# step 2: per-model forward pass, re-tokenised window/slot bookkeeping
# ----------------------------------------------------------------------------------
def _clip_window(plen: int, cont: int, w0: int, w1: int) -> tuple[int, int] | None:
    """Continuation-relative window [w0, w1) -> absolute token indices, clipped to the
    (possibly truncated) continuation length. None if the clipped window is empty."""
    cont = max(cont, 0)
    s, e = plen + w0, plen + min(w1, cont)
    return (s, e) if e > s else None


def c_harvest_v2(
    model,
    tok,
    cells_rendered: list[dict],
    char_spans: dict[str, list[list[int] | None]],
    cfg: dict,
) -> dict:
    """One forward pass per cell (batch) over prompt+continuation; per-model
    re-tokenised slot check, with EXACT causal truncation.

    `cells_rendered[j]` must carry `prompt_text` and `full_text` (as
    `sweep._render_cells` / `_render_cells_local` below produce), plus the original cell
    fields (`cell_id`, `action_slot_spans`, ...).

    Every stored quantity only ever reads continuation positions < cfg["keep_cont_tokens"]
    (default 56: early window ends at 20, late window ends at 55, x5 reads 0..31). In a
    causal LM the hidden state at position t depends only on tokens <= t, so truncating
    the tensor fed to the model to `plen + keep_cont_tokens` tokens per cell cannot change
    any hidden state we read -- it only removes compute for tokens whose hidden states are
    never used. Tokenisation for plen/slot-span/slot_ok bookkeeping is always done on the
    FULL (untruncated, up to max_len_cell) text first, so slot_ok is unaffected by
    `keep_cont_tokens`; only the forward pass itself is shortened.

    `cfg["cells_mode"]` == "x5" restricts BOTH the bookkeeping and the forward pass to the
    48 registered x5 cells; every other cell's row in A_resp/D_resp/kept/slot_ok/per_cell
    stays at its zero/False/None default.

    Returns A_resp [n, L+1, 2, d] f16 (mean hidden over the early / late window), D_resp
    [n_x5, L, 32, d] f16 (per-position deltas for the registered x5 cells only), kept and
    slot_ok bool[n], a per-cell diagnostic table, and the plen cross-check mismatches.
    """
    torch = _torch()
    _t0 = time.time()
    n = len(cells_rendered)
    early = tuple(cfg["early_window"])
    late = tuple(cfg["late_window"])
    x5_cell_index = sorted({int(c) for c in cfg["x5_cell_index"]})
    x5_positions = int(cfg["x5_positions"])
    max_len = int(cfg["max_len_cell"])
    min_cont_len = int(late[1])  # "continuation length >= 55 tokens" under the registered
    # config (late_window[1]); kept as a variable, not a literal, so a re-registered
    # late_window still drives this bound consistently.
    keep_cont_tokens = int(cfg.get("keep_cont_tokens", 56))
    cells_mode = cfg.get("cells_mode", "all")
    # clip the windows themselves to the causal-truncation budget: a window whose upper
    # bound reached past keep_cont_tokens would try to read a position the truncated
    # forward pass never computed.
    early = (early[0], min(early[1], keep_cont_tokens))
    late = (late[0], min(late[1], keep_cont_tokens))

    run_indices = x5_cell_index if cells_mode == "x5" else list(range(n))

    A_resp: np.ndarray | None = None
    D_resp: np.ndarray | None = None
    kept = np.zeros(n, dtype=bool)
    slot_ok = np.zeros(n, dtype=bool)
    x5_set = {c: k for k, c in enumerate(x5_cell_index)}
    per_cell: list[dict | None] = [None] * n
    plen_mismatches: list[dict] = []

    bs = int(cfg["batch_cell"])
    i = 0
    while i < len(run_indices):
        sel = run_indices[i : i + bs]
        try:
            prompts = [cells_rendered[j]["prompt_text"] for j in sel]
            fulls = [cells_rendered[j]["full_text"] for j in sel]
            enc = tok(
                fulls, return_tensors="pt", padding=True, truncation=True,
                max_length=max_len, add_special_tokens=False, return_offsets_mapping=True,
            )
            ids, mask = enc["input_ids"], enc["attention_mask"]
            offs = enc["offset_mapping"]  # [b, T, 2]
            flens = mask.sum(dim=1).tolist()

            # ---- phase 1: pure-tokenisation bookkeeping on the FULL text -- plen, slot
            # spans, slot_ok, kept, and each row's causal-truncation keep_len. No model
            # call here, so slot_ok is by construction independent of keep_cont_tokens.
            row_meta = []
            for bi, j in enumerate(sel):
                cell = cells_rendered[j]
                prompt_text = prompts[bi]
                plen_chars = len(prompt_text)
                fl = int(flens[bi])
                row_offs = offs[bi][:fl]
                plen = int((row_offs[:, 0] < plen_chars).sum().item())
                plen_check = len(tok(prompt_text, add_special_tokens=False)["input_ids"])
                if plen != plen_check:
                    plen_mismatches.append({
                        "cell_id": cell["cell_id"], "plen_from_offsets": plen,
                        "plen_from_separate_tok": plen_check,
                    })
                cont = fl - plen

                spans_char = char_spans.get(cell["cell_id"], [])
                row_starts = row_offs[:, 0].tolist()
                row_ends = row_offs[:, 1].tolist()
                slot_tok_spans: list[list[int] | None] = []
                for sp in spans_char:
                    if sp is None:
                        slot_tok_spans.append(None)
                        continue
                    cs, ce = sp
                    fcs, fce = cs + plen_chars, ce + plen_chars
                    tok_idx = [t for t in range(plen, fl)
                               if row_ends[t] > fcs and row_starts[t] < fce]
                    if tok_idx:
                        slot_tok_spans.append([tok_idx[0] - plen, tok_idx[-1] - plen + 1])
                    else:
                        slot_tok_spans.append(None)

                ok_early = any(sp is not None and sp[0] < early[1] and sp[1] > early[0]
                                for sp in slot_tok_spans)
                ok_late = any(sp is not None and sp[0] < late[1] and sp[1] > late[0]
                              for sp in slot_tok_spans)
                ok = bool(ok_early and ok_late)
                slot_ok[j] = ok
                cell_kept = bool(ok and cont >= min_cont_len)
                kept[j] = cell_kept

                keep_len = min(fl, plen + keep_cont_tokens)  # causal truncation point
                row_meta.append({
                    "j": j, "bi": bi, "plen": plen, "fl": fl, "cont": cont,
                    "slot_tok_spans": slot_tok_spans, "ok": ok, "cell_kept": cell_kept,
                    "keep_len": keep_len,
                })

            # ---- phase 2: EXACT causal truncation -- slice the tensor fed to the model
            # down to the longest keep_len in this batch. Positions < keep_len are
            # numerically IDENTICAL to an untruncated pass (causal attention never looks
            # forward), so this only removes wasted compute on unused tail positions.
            batch_max_T = max((rm["keep_len"] for rm in row_meta), default=1)
            batch_max_T = max(batch_max_T, 1)
            ids_t = ids[:, :batch_max_T]
            mask_t = mask[:, :batch_max_T]

            with torch.no_grad():
                out = model(input_ids=ids_t, attention_mask=mask_t,
                            output_hidden_states=True, use_cache=False)
            hs = out.hidden_states
            L1, d = len(hs), hs[0].shape[-1]
            if A_resp is None:
                A_resp = np.zeros((n, L1, 2, d), dtype=np.float16)
                if x5_set:
                    D_resp = np.zeros((len(x5_set), L1 - 1, x5_positions, d), dtype=np.float16)
            H = torch.stack(hs, dim=1).float()          # [b, L1, T_trunc, d]

            for rm in row_meta:
                j, bi, plen, cont, keep_len = (
                    rm["j"], rm["bi"], rm["plen"], rm["cont"], rm["keep_len"]
                )
                cont_extract = min(cont, keep_cont_tokens)  # what's left post-truncation

                ew = _clip_window(plen, cont_extract, early[0], early[1])
                lw = _clip_window(plen, cont_extract, late[0], late[1])
                if ew is not None:
                    A_resp[j, :, 0, :] = (
                        H[bi, :, ew[0]:ew[1], :].mean(dim=1).to(torch.float16).numpy()
                    )
                if lw is not None:
                    A_resp[j, :, 1, :] = (
                        H[bi, :, lw[0]:lw[1], :].mean(dim=1).to(torch.float16).numpy()
                    )
                elif ew is not None:
                    A_resp[j, :, 1, :] = A_resp[j, :, 0, :]

                if j in x5_set and D_resp is not None:
                    p_end = min(plen + x5_positions, keep_len)
                    npos = max(0, p_end - plen)
                    if npos > 0:
                        blk = H[bi, :, plen:p_end, :]           # [L1, npos, d]
                        D_resp[x5_set[j], :, :npos, :] = (
                            (blk[1:] - blk[:-1]).to(torch.float16).numpy()
                        )

                per_cell[j] = {
                    "cell_id": cells_rendered[j]["cell_id"], "plen": plen,
                    "n_cont_tokens": cont, "slot_token_spans": rm["slot_tok_spans"],
                    "slot_ok": rm["ok"], "kept": rm["cell_kept"], "keep_len_tokens": keep_len,
                }
            del out, hs, H
            i += bs
            logger.info(f"    C-harvest2 {min(i, len(run_indices))}/{len(run_indices)} "
                        f"cells ({(time.time() - _t0):.0f}s)")
        except (torch.OutOfMemoryError, RuntimeError, MemoryError) as exc:  # noqa: PERF203
            if bs > 1 and ("memory" in str(exc).lower() or isinstance(exc, MemoryError)):
                bs = max(1, bs // 2)
                logger.warning(f"C-harvest2 OOM -> batch_size={bs}")
                gc.collect()
                continue
            raise

    return {
        "A_resp": A_resp, "D_resp": D_resp, "kept": kept, "slot_ok": slot_ok,
        "per_cell": per_cell, "plen_mismatches": plen_mismatches,
        "elapsed_s": time.time() - _t0, "cells_harvested": cells_mode,
        "keep_cont_tokens": keep_cont_tokens,
    }


# ----------------------------------------------------------------------------------
# rendering (mirrors sweep._render_cells, reusing an already-loaded tokenizer)
# ----------------------------------------------------------------------------------
def _render_cells_local(tok, cells: list[dict], mode: str) -> list[dict]:
    out = []
    for c in cells:
        p = render_prompt(tok, c["plain_prompt"], mode)
        out.append(dict(c, prompt_text=p, full_text=p + c["continuation"]))
    return out


# ----------------------------------------------------------------------------------
# the resumable per-checkpoint driver
# ----------------------------------------------------------------------------------
def run_tag(tag: str, cfg: dict, cells: list[dict], char_spans: dict[str, Any],
           qwen4b_mismatch_n: int) -> dict:
    """Load `tag`'s checkpoint exactly as `harvest.harvest_one` does, run c_harvest_v2,
    write its outputs, mark C_DONE. Resumable: a tag with C_DONE is skipped."""
    torch = _torch()
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    out_dir = HARVEST / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    done = out_dir / "C_DONE"
    if done.exists():
        logger.info(f"SKIP {tag} (C_DONE)")
        return jload(out_dir / "c_meta.json")

    tmeta_path = out_dir / "meta.json"
    if not tmeta_path.exists():
        raise FileNotFoundError(f"no meta.json for tag {tag} at {tmeta_path} "
                                 f"(the prompt harvest for this tag has not run yet)")
    tmeta = jload(tmeta_path)
    repo = tmeta["repo"]
    template_mode = tmeta.get("template_mode", "chat")
    random_init = bool(tmeta.get("random_init", False))

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
        set_all_seeds()  # same global-seed handling harvest_one relies on via sweep.main
        conf = AutoConfig.from_pretrained(repo)
        model = AutoModelForCausalLM.from_config(conf, dtype=dtype)
    else:
        model = AutoModelForCausalLM.from_pretrained(
            repo, dtype=dtype, low_cpu_mem_usage=True,
            attn_implementation=cfg.get("attn", "sdpa"),
        )
    model.eval()
    model.to("cpu")
    t_load = time.time() - t0

    cells_rendered = _render_cells_local(tok, cells, template_mode)

    t = time.time()
    ch = c_harvest_v2(model, tok, cells_rendered, char_spans, cfg)
    t_c = ch["elapsed_s"]

    np.save(out_dir / "A_resp.npy", ch["A_resp"])
    if ch["D_resp"] is not None:
        # per-position tensor is 120-300 MB: stored as parts below GitHub's 100 MiB limit
        save_npy_split(ch["D_resp"], out_dir, "D_resp")
    np.save(out_dir / "cell_kept.npy", ch["kept"])
    np.save(out_dir / "cell_slot_ok.npy", ch["slot_ok"])

    n_cells = len(cells)
    n_kept = int(ch["kept"].sum())
    n_slot_ok = int(ch["slot_ok"].sum())
    drop_frac = 1.0 - (n_kept / n_cells) if n_cells else 1.0
    x5_cell_index = list(cfg["x5_cell_index"])
    n_x5_kept = int(sum(1 for c in x5_cell_index if c < n_cells and ch["kept"][c]))

    c_meta = {
        "tag": tag, "repo": repo, "template_mode": template_mode, "random_init": random_init,
        "n_cells": n_cells, "n_kept": n_kept, "n_slot_ok": n_slot_ok,
        "drop_frac": drop_frac, "x5_undefined": bool(drop_frac > 0.20),
        "n_x5_cells": len(x5_cell_index), "n_x5_kept": n_x5_kept,
        "cells_harvested": ch.get("cells_harvested", cfg.get("cells_mode", "all")),
        "causal_truncation": {
            "kept_continuation_tokens": ch.get("keep_cont_tokens",
                                                cfg.get("keep_cont_tokens", 56)),
            "why": f"exact: causal attention means states at positions < "
                   f"{ch.get('keep_cont_tokens', cfg.get('keep_cont_tokens', 56))} are "
                   f"unaffected by later tokens",
        },
        "timings": {"t_load_s": t_load, "t_c_harvest_s": t_c},
        "n_plen_mismatches": len(ch["plen_mismatches"]),
        "plen_mismatches": ch["plen_mismatches"],
        "qwen4b_tokenization_mismatches": qwen4b_mismatch_n,
        "per_cell": ch["per_cell"],
        "ts": time.time(),
    }
    jdump(c_meta, out_dir / "c_meta.json")
    done.write_text(json.dumps({"ts": time.time(), "t_c_harvest_s": t_c}))

    del model, tok
    gc.collect()
    logger.info(f"C-HARVESTED {tag}: kept {n_kept}/{n_cells} (drop_frac={drop_frac:.3f}, "
                f"slot_ok={n_slot_ok}/{n_cells}, x5_undefined={c_meta['x5_undefined']}, "
                f"x5_kept={n_x5_kept}/{len(x5_cell_index)}) in {t_c:.1f}s (load {t_load:.1f}s)")
    return c_meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", required=True,
                    help="harvest/ dir names, e.g. Qwen--Qwen3-4B")
    ap.add_argument("--deadline-min", type=float, default=110.0)
    ap.add_argument("--limit-cells", type=int, default=0, help="testing only")
    ap.add_argument("--keep-cont-tokens", type=int, default=56,
                    help="EXACT causal truncation: feed the model only the first "
                         "plen+this-many continuation tokens per cell (early window ends "
                         "20, late window ends 55, x5 reads 0..31 -> 56 covers all three "
                         "with no approximation, since causal attention never looks "
                         "forward). Positions < this value are numerically identical to "
                         "an untruncated pass.")
    ap.add_argument("--cells", choices=("all", "x5"), default="all",
                    help="'x5' harvests only the 48 registered x5_cell_index cells; every "
                         "other cell's row stays at its zero/False default.")
    args = ap.parse_args()

    setup_logging("c_sweep")
    set_all_seeds()
    dl = Deadline(args.deadline_min)

    prereg = jload(WS / "prereg.json")
    cfg = dict(prereg["config"])
    cells_doc = jload(ASSETS / "cells.json")
    cells = cells_doc["cells"]
    x5_cell_index = cells_doc["x5_cell_index"]
    if args.limit_cells:
        cells = cells[: args.limit_cells]
        x5_cell_index = [c for c in x5_cell_index if c < len(cells)]
    cfg["x5_cell_index"] = x5_cell_index
    cfg["keep_cont_tokens"] = int(args.keep_cont_tokens)
    cfg["cells_mode"] = args.cells

    sc = slot_char_spans(cells)
    char_spans = sc["char_spans"]
    qwen4b_mismatch_n = len(sc["mismatches"])
    if sc["mismatches"]:
        logger.warning(f"{qwen4b_mismatch_n} cells do not tokenise to n_tokens_qwen under "
                        f"{QWEN3_TOKENIZER_REPO}: {sc['mismatches'][:5]}")

    failures = jload_maybe(RESULTS / "c_harvest_failures.json", []) or []

    logger.info(f"TAGS ({len(args.tags)}): {', '.join(args.tags)}  "
                f"[{len(cells)} cells, {len(x5_cell_index)} x5, cells_mode={args.cells}, "
                f"keep_cont_tokens={args.keep_cont_tokens}]")
    for tag in args.tags:
        if not dl.have(1.0):
            logger.warning(f"deadline reached before {tag}; stopping")
            break
        logger.info(f"HARVEST2 {tag} ({dl.remaining_min():.0f} min left)")
        try:
            run_tag(tag, cfg, cells, char_spans, qwen4b_mismatch_n)
        except Exception as exc:  # noqa: BLE001 - one checkpoint must never kill the sweep
            tb = traceback.format_exc()
            failures.append({"tag": tag, "error": repr(exc), "traceback": tb[-4000:],
                             "ts": time.time()})
            jdump(failures, RESULTS / "c_harvest_failures.json")
            logger.error(f"FAILED {tag}: {exc}")
        finally:
            gc.collect()

    jdump(failures, RESULTS / "c_harvest_failures.json")
    done_tags = sorted(p.parent.name for p in HARVEST.glob("*/C_DONE"))
    logger.info(f"C-SWEEP END: {len(done_tags)} c-harvested total, {len(failures)} failed "
                f"this run, {dl.elapsed_min():.1f} min elapsed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
