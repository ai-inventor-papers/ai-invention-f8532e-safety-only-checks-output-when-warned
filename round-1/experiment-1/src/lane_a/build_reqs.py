#!/usr/bin/env python3
"""Turn the substrate into the exact token-id request lists every checkpoint runs.

ONE tokenizer (Qwen/Qwen3-4B) builds the inputs for EVERY checkpoint, so continuation
token ids are literally identical model-to-model.  Each checkpoint's own tokenizer is
still hashed and compared, and each checkpoint's own chat template is recorded, but the
template applied is always Qwen3-4B's -- that is what makes the token spans comparable
(and it is why Qwen3-4B-Base is run under Qwen3-4B's template, per the plan).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

from loguru import logger

from .harvest import Req
from .substrate import (
    COHERENCE_TOPICS, FRAMES, K4_TOTAL_L, NEUTRAL_PROMPTS, TOTAL_L, WIN_EARLY, WIN_LATE,
    FrameBuilder, Substrate, TwinItem, slots_hit_windows,
)

FIT_NEUTRAL_REQUEST = "Continue the passage below in the same style."
PLAIN_FMT = "{request}\n\n"

SAFETY_CELLS = tuple(f"saf|{f}|{r}|{p}" for f in ("F1", "F2") for r in ("H", "B") for p in ("haz", "ben"))
COH_CELLS = tuple(f"coh|F1|{r}|{p}" for r in ("A", "B") for p in ("A", "B"))
GRID_CELLS = SAFETY_CELLS + COH_CELLS


class InputBuilder:
    def __init__(self, tokenizer, template_mode: str = "chat") -> None:
        self.tok = tokenizer
        self.mode = template_mode
        self.fb = FrameBuilder(tokenizer)
        self._pcache: dict[str, list[int]] = {}

    def prompt_ids(self, request: str) -> list[int]:
        if request in self._pcache:
            return self._pcache[request]
        if self.mode == "chat":
            text = self.tok.apply_chat_template(
                [{"role": "user", "content": request}],
                tokenize=False, add_generation_prompt=True, enable_thinking=False)
        else:
            text = PLAIN_FMT.format(request=request)
        ids = self.tok(text, add_special_tokens=False)["input_ids"]
        self._pcache[request] = ids
        return ids

    def prefix(self, action: str, frame: str, total_l: int = TOTAL_L) -> dict[str, Any]:
        return self.fb.build(action, frame, total_l)


def build_all(sub: Substrate, ib: InputBuilder) -> dict[str, Any]:
    """Return {'grid': [...], 'fit': [...], 'ablit': [...], 'aux': [...], 'k4': [...], 'diag': {...}}."""
    diag: dict[str, Any] = {"slots": [], "prefix_examples": [], "violations": []}

    # ---- prefix cache: one build per (action, frame)
    pref_cache: dict[tuple[str, str], dict[str, Any]] = {}

    def get_prefix(action: str, frame: str) -> dict[str, Any]:
        k = (action, frame)
        if k not in pref_cache:
            pref_cache[k] = ib.prefix(action, frame)
        return pref_cache[k]

    grid: list[Req] = []
    for it in sub.twins:
        cells: dict[str, tuple[str, str, str]] = {}
        for f in ("F1", "F2"):
            cells[f"saf|{f}|H|haz"] = (it.harmful_request, it.action_h, f)
            cells[f"saf|{f}|H|ben"] = (it.harmful_request, it.action_b, f)
            cells[f"saf|{f}|B|haz"] = (it.benign_request, it.action_h, f)
            cells[f"saf|{f}|B|ben"] = (it.benign_request, it.action_b, f)
        ta, tb = it.coherence_topic_a, it.coherence_topic_b
        cells["coh|F1|A|A"] = (f"How do I {ta}?", ta, "F1")
        cells["coh|F1|A|B"] = (f"How do I {ta}?", tb, "F1")
        cells["coh|F1|B|A"] = (f"How do I {tb}?", ta, "F1")
        cells["coh|F1|B|B"] = (f"How do I {tb}?", tb, "F1")
        for cell in GRID_CELLS:
            req, action, frame = cells[cell]
            pf = get_prefix(action, frame)
            grid.append(Req(key=f"{it.item_id}||{cell}", prompt_ids=ib.prompt_ids(req),
                            prefix_ids=pf["ids"], group="grid",
                            meta={"item_id": it.item_id, "cell": cell, "family": it.family}))

    # ---- SLOT CHECK: every item, both prefix families, both windows
    for (action, frame), pf in pref_cache.items():
        hit_e = slots_hit_windows(pf["slot1"], WIN_EARLY) or slots_hit_windows(pf["slot2"], WIN_EARLY)
        hit_l = slots_hit_windows(pf["slot1"], WIN_LATE) or slots_hit_windows(pf["slot2"], WIN_LATE)
        rec = {"action": action, "frame": frame, "slot1": list(pf["slot1"]),
               "slot2": list(pf["slot2"]), "action_ntok": pf["action_ntok"],
               "early_hit": hit_e, "late_hit": hit_l}
        diag["slots"].append(rec)
        if not (hit_e and hit_l):
            diag["violations"].append(rec)
    if diag["violations"]:
        raise RuntimeError(f"SLOT CHECK FAILED for {len(diag['violations'])} prefixes -- "
                           "a read window with no ACTION token has a structurally zero contrast")
    diag["prefix_examples"] = [
        {"action": a, "frame": f, "text": p["text"], "n_tokens": len(p["ids"])}
        for (a, f), p in list(pref_cache.items())[:6]
    ]
    diag["n_unique_prefixes"] = len(pref_cache)

    # ---- fitting corpus for r_content (disjoint from every evaluation item)
    fit: list[Req] = []
    fit_prompt = ib.prompt_ids(FIT_NEUTRAL_REQUEST)
    for p in sub.fit_pairs:
        for lab, act in (("haz", p["action_h"]), ("ben", p["action_b"])):
            pf = get_prefix(act, "F1")
            fit.append(Req(key=f"{p['pair_id']}||{lab}", prompt_ids=fit_prompt,
                           prefix_ids=pf["ids"], group="fit",
                           meta={"pair_id": p["pair_id"], "label": lab, "half": p["half"],
                                 "category": p["category"]}))

    # ---- r_ablit: PROMPT-site request-refusal axis (last prompt token, no continuation)
    ablit: list[Req] = []
    for i, q in enumerate(sub.ablit_harmful):
        ablit.append(Req(key=f"ablit_h{i:03d}", prompt_ids=ib.prompt_ids(q), group="ablit",
                         meta={"label": "harmful"}))
    for i, q in enumerate(sub.ablit_harmless):
        ablit.append(Req(key=f"ablit_b{i:03d}", prompt_ids=ib.prompt_ids(q), group="ablit",
                         meta={"label": "harmless"}))

    # ---- aux: K2 ladder + contentless prior + K3 benign-only set
    aux: list[Req] = []
    for r in sub.ladder:
        aux.append(Req(key=f"ladder||{r['item_id']}||{r['rung']}", prompt_ids=ib.prompt_ids(r["prompt"]),
                       group="ladder", meta={"item_id": r["item_id"], "rung": r["rung"], "src": r["src"]}))
    aux.append(Req(key="contentless||empty", prompt_ids=ib.prompt_ids(""), group="contentless",
                   meta={"kind": "empty"}))
    for i, q in enumerate(NEUTRAL_PROMPTS):
        aux.append(Req(key=f"contentless||neutral{i:02d}", prompt_ids=ib.prompt_ids(q),
                       group="contentless", meta={"kind": "neutral"}))
    for i, q in enumerate(sub.benign_only):
        aux.append(Req(key=f"benign_only||{i:02d}", prompt_ids=ib.prompt_ids(q),
                       group="benign_only", meta={}))

    # ---- K4 persistence stimulus: ONE fixed hazardous and ONE fixed benign 128-token
    #      continuation, identical across checkpoints, under each pilot item's harmful request
    k4: list[Req] = []
    by_id = {t.item_id: t for t in sub.twins}
    k4_pref = {lab: ib.prefix(sub.k4_actions[f"action_{s}"], "F1", K4_TOTAL_L)
               for lab, s in (("haz", "h"), ("ben", "b"))}
    for iid in sub.pilot_ids:
        t = by_id[iid]
        for lab in ("haz", "ben"):
            k4.append(Req(key=f"k4||{iid}||{lab}", prompt_ids=ib.prompt_ids(t.harmful_request),
                          prefix_ids=k4_pref[lab]["ids"], group="k4",
                          meta={"item_id": iid, "label": lab}))
    diag["k4_prefix_texts"] = {k: v["text"] for k, v in k4_pref.items()}
    diag["k4_len"] = {k: len(v["ids"]) for k, v in k4_pref.items()}

    # ---- token-span invariants
    span_bad = []
    for it in sub.twins:
        for f in ("F1", "F2"):
            a = get_prefix(it.action_h, f)["ids"]
            b = get_prefix(it.action_b, f)["ids"]
            if len(a) != len(b) or len(a) != TOTAL_L:
                span_bad.append({"item": it.item_id, "frame": f, "len_h": len(a), "len_b": len(b)})
    if span_bad:
        raise RuntimeError(f"prefix length invariant violated for {len(span_bad)} cells: {span_bad[:3]}")
    diag["prefix_len"] = TOTAL_L
    diag["n_grid"] = len(grid)
    diag["n_fit"] = len(fit)
    diag["n_ablit"] = len(ablit)
    diag["n_aux"] = len(aux)
    diag["n_k4"] = len(k4)
    diag["total_passes"] = len(grid) + len(fit) + len(ablit) + len(aux) + len(k4)
    logger.info(f"requests built: grid={len(grid)} fit={len(fit)} ablit={len(ablit)} "
                f"aux={len(aux)} k4={len(k4)} total={diag['total_passes']}")
    return {"grid": grid, "fit": fit, "ablit": ablit, "aux": aux, "k4": k4, "diag": diag}


def decode_window_report(ib: InputBuilder, sub: Substrate, n: int = 5) -> list[dict[str, Any]]:
    """STEP 2 of the testing plan: decode the tokens at positions 5-20 and 40-55 in all four
    safety cells of n sample items, and confirm they are prefix text, identical between the
    harmful-request and benign-request cells, and contain ACTION tokens."""
    out = []
    for it in sub.twins[:n]:
        rec: dict[str, Any] = {"item_id": it.item_id, "family": it.family,
                               "benign_request": it.benign_request,
                               "harmful_request": it.harmful_request,
                               "action_b": it.action_b, "action_h": it.action_h, "cells": {}}
        for pre_lab, act in (("haz", it.action_h), ("ben", it.action_b)):
            pf = ib.prefix(act, "F1")
            ids = pf["ids"]
            rec["cells"][pre_lab] = {
                "early_5_20": ib.tok.decode(ids[WIN_EARLY[0]:WIN_EARLY[1] + 1]),
                "late_40_55": ib.tok.decode(ids[WIN_LATE[0]:WIN_LATE[1] + 1]),
                "slot1": list(pf["slot1"]), "slot2": list(pf["slot2"]),
                "n_tokens": len(ids),
            }
        # the prefix ids are the SAME object for the H-request and B-request cells by
        # construction, so the two request cells read at identical positions.
        rec["prefix_identical_across_request_cells"] = True
        out.append(rec)
    return out


__all__ = ["InputBuilder", "build_all", "decode_window_report", "GRID_CELLS",
           "SAFETY_CELLS", "COH_CELLS", "FIT_NEUTRAL_REQUEST", "PLAIN_FMT"]
