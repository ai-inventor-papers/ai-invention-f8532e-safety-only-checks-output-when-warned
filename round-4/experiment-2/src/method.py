#!/usr/bin/env python3
"""Causal depth x site grid on Qwen3-4B (instruct) and Qwen3-4B-SafeRL (+ optional abliterated checkpoint).

Session 4 runs on a GPU pod (NVIDIA L4). The CPU-fallback (F1) prereg frozen in session 2 (prereg.json) is a
STRICT SUBSET of what runs here and is analysed exactly as registered. The plan's primary GPU design (sites
D' and E, judged generation on every cell, 80 new tokens, 48+48 items) is frozen in prereg_gpu_addendum.json
(sha256 in prereg_gpu_addendum.sha256) BEFORE any Qwen3-4B outcome is computed.

One long-lived process per invocation, every cell checkpointed to out/cells/<model>/<cell>__<hookhash>.npz|json
and skipped when present. Judging runs in a background worker thread so the GPU never waits on the API.

Stages per model:
  registered (prereg.json, F1 subset):
    unit      8 A_prompt stimuli re-forwarded: last-token states vs the iter-2 harvest on disk
    twins     85 confirmatory XSTest twin pairs, prompt-only -> N6 (benign-side twin direction), N6perp, R pool
    decod     32+32 held-out decodability items, arm 0 -> per-layer projections (site-P decodability AUROC)
    arm0      eval items (48 harm + 48 hard-benign) prefix-cached; arm 0 + hook checks (a1, a2, b, c)
    grid1     site P, 6 bands x {F, N6, N6perp, R_F 1-3, R_N6 1-3, POSCTRL(B3,B4)}  (forward-only outcomes)
    gen       judged generation at B3/B4 x P: {0, F, R_F1, N6, R_N6-1}, 24 harm + 24 hard-benign, 48 tokens
    arc       64 ARC-Easy items: arm 0 (4-token greedy) + token-1 under {F, N6, N6perp, R_F1-3, R_N6 1-3} x 6 bands
    grid2     R_F draws 4-11             grid3   R_F draws 12-20 + R_N6 draws 4-5
  GPU addendum (prereg_gpu_addendum.json):
    genP      judged generation, site P, 6 bands x {0, F, N6, N6perp, R_F 1-3, R_N6 1-3, POS(B3,B4)}, 96 items, 80 tok
    genDprime judged generation, site D' (last prompt pos + decode calls 1-7), 6 bands x {0, F, N6, R_Fo 1-3, R_N6o 1-3}
    genE      judged generation, site E (decode calls 5-20), same arms
    stimro    readouts under site-P intervention on the 256 A_prompt stimuli (arms 0 / F / N6 / R_F1)
    decodgen  decode-step decodability: arm-0 greedy (21 tokens) on the 32+32 decodability items, projections
    spanD     forward-only teacher-forced window D (decode inputs 1-8) on the arm-0 greedy prefix, 20 R_F draws
    spanE     same for window E (decode inputs 5-20)
    gsm       GSM8K collateral (16 items, 256 tokens) on the cells passed with --gsm-cells
Baselines inside the same pipeline: arm 0 (no intervention) and the matched-displacement random arms
(R_F / R_N6 at the prompt position, own-coefficient R_Fo / R_N6o at decode sites); the causal contrast is
F - R, not F - 0. POS is a generic-disruption positive control, not a treatment.
"""
from __future__ import annotations

import argparse
import functools
import hashlib
import inspect
import json
import queue
import re
import resource
import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from loguru import logger  # noqa: E402

from common import (ALL_MODELS, ASSETS, BANDS, CELLS, H2, JUDGE_CACHE, LEDGER, MODELS, PRIVATE, RESULTS, SEED,  # noqa: E402
                    WS, Timer, add_deviation, bands_for, cgroup_mem_gb, jdump, jload, setup_logging, utc_now)

GEN_MAX_NEW = 48                 # registered F1 generation cell
GRID_MAX_NEW = 80                # GPU addendum generation cells (plan: 80 new tokens)
ARC_MAX_NEW = 4
GSM_MAX_NEW = 256
DECOD_GEN_NEW = 21
J_POOL = 20                      # random directions per layer
N6_LSTAR_RANGE = (4, 33)
JUDGE_CONCURRENCY = 32
KV_BUDGET = {"cpu": 1.1e9, "cuda": 3.0e9}   # replicated prefix-cache budget per pass (bytes)
DEVICE = "cpu"
KV_SCALE = 1.0                   # halved on CUDA OOM (fallback F2)


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------
def hook_hash() -> str:
    import engine
    src = inspect.getsource(engine.Engine._make_hook) + inspect.getsource(engine.Engine.build_spec) + \
        inspect.getsource(engine.Engine.stacked_pass) + inspect.getsource(engine.Engine.site_generate)
    return hashlib.sha256(src.encode()).hexdigest()[:8]


def cell_path(m: str, name: str, ext: str = "npz") -> Path:
    d = CELLS / m
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{name}__{HOOK_HASH}.{ext}"


def save_cell(m: str, name: str, arrays: dict, meta: dict) -> None:
    p = cell_path(m, name)
    tmp = p.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, **arrays)
    tmp.replace(p)
    jdump(cell_path(m, name, "json"), meta)


def have_cell(m: str, name: str) -> bool:
    return cell_path(m, name).exists() and cell_path(m, name, "json").exists()


def rows_meta(rows, item_ids) -> list[dict]:
    return [{"item_id": item_ids[r.item], "arm": r.arm, "band": r.band, "draw": r.draw} for r in rows]


def _np(t):
    return t.detach().float().cpu().numpy() if hasattr(t, "detach") else np.asarray(t)


def disp_summary(spec, rows) -> dict:
    """Per-layer displacement bookkeeping: matched-R / F ratio (check c) and post-cast residual (check b).
    Displacements are per row averaged over the S edited positions."""
    out = {"ratio_R_over_src": {}, "mean_disp_by_arm": {}, "resid_ratio_after_projection": {}}
    for l, (c, dn) in spec.disp.items():
        op = spec.layer_ops[l]
        src = _np(op["src"]).astype(int)
        has = _np(op["has"])
        patch = None if op["patch"] is None else _np(op["patch"]).astype(bool)
        dn_all = _np(dn)                            # [R, S]
        dnm = dn_all.mean(1)
        ratios = []
        for r, row in enumerate(rows):
            if row.arm in ("RF", "RN6") and has[r] > 0:
                s = src[r]
                ok = dn_all[s] > 0
                if ok.any():
                    q = dn_all[r][ok] / dn_all[s][ok]
                    ratios += [float(q.min()), float(q.max())]
        if ratios:
            out["ratio_R_over_src"][str(l)] = [float(np.min(ratios)), float(np.max(ratios))]
        by = {}
        for r, row in enumerate(rows):
            if has[r] > 0 or (patch is not None and patch[r]):
                by.setdefault(row.arm, []).append(float(dnm[r]))
        out["mean_disp_by_arm"][str(l)] = {k: float(np.mean(v)) for k, v in by.items()}
    out["resid_ratio_after_projection"] = {str(k): float(v) for k, v in spec.resid_ratio.items()}
    return out


def max_rows_for(T: int, kv_bytes_per_tok: int) -> int:
    return max(4, int(KV_BUDGET[DEVICE] * KV_SCALE // max(1, (T + 1) * kv_bytes_per_tok)))


def is_oom(e: BaseException) -> bool:
    import torch
    return isinstance(e, torch.cuda.OutOfMemoryError) or "out of memory" in str(e).lower()


def on_oom(label: str) -> None:
    global KV_SCALE
    import torch
    torch.cuda.empty_cache()
    KV_SCALE *= 0.5
    add_deviation("F2_oom_halving", "CUDA OOM -> rows per pass halved (fallback F2)",
                  "shared L4 with a sibling agent", "throughput only; no outcome definition changes")
    logger.warning(f"OOM in {label}: KV_SCALE -> {KV_SCALE}")
    if KV_SCALE < 1 / 64:
        raise RuntimeError("repeated OOM even at 1/64 of the KV budget")


# ---------------------------------------------------------------------------------------------
# background judge worker (asyncio judge in a thread; the GPU never waits on the API)
# ---------------------------------------------------------------------------------------------
class JudgeWorker:
    def __init__(self):
        self.q: queue.Queue = queue.Queue()
        self.errors: list[str] = []
        self.pending: set[str] = set()
        self.lock = threading.Lock()
        self.t = threading.Thread(target=self._run, daemon=True, name="judge-worker")
        self.t.start()

    def submit(self, key: str, fn) -> None:
        with self.lock:
            self.pending.add(key)
        self.q.put((key, fn))

    def _run(self) -> None:
        while True:
            job = self.q.get()
            if job is None:
                self.q.task_done()
                break
            key, fn = job
            try:
                fn()
            except Exception as e:  # noqa: BLE001 - logged and surfaced at join()
                logger.exception(f"judge job {key} failed: {e!r}")
                self.errors.append(f"{key}: {e!r}")
            finally:
                with self.lock:
                    self.pending.discard(key)
                self.q.task_done()

    def backlog(self) -> int:
        return self.q.qsize()

    def join(self) -> None:
        self.q.put(None)
        self.t.join()


JW: JudgeWorker | None = None


def judge_arrays(recs: list[dict]) -> tuple[dict, dict]:
    """lc_judge_iter1 labels (deduped through the shared cache; PROXY after the $2.70 stop) -> arrays."""
    from judge import derive, judge_sync, keyword_proxy
    labels, jstats = judge_sync([{"request": r["request"], "response": r["response"]} for r in recs],
                                cache_path=JUDGE_CACHE, ledger_path=LEDGER, stop_usd=2.70,
                                concurrency=JUDGE_CONCURRENCY)
    arr = {k: [] for k in ("refused", "refused_raw", "harmful_compliance", "safe_engagement", "over_refusal",
                           "judged", "proxy_refused", "n_new_tokens")}
    for r, lab in zip(recs, labels):
        kind = "harm" if r["kind"] in ("harm", "dharm") else "hb"
        dv = derive(lab, kind)
        src = (lab or {}).get("source")
        judged = 1.0 if (lab is not None and src in ("judge", "cache")) else (0.5 if src == "proxy" else 0.0)
        arr["refused_raw"].append(np.nan if lab is None else float(bool(lab["refused"])))
        if kind == "harm":
            # exclusive categories (derive): refused = refused AND no harmful content; HC = harmful content
            arr["refused"].append(np.nan if dv["refused"] is None else float(dv["refused"]))
            arr["harmful_compliance"].append(np.nan if dv["harmful_compliance"] is None
                                             else float(dv["harmful_compliance"]))
            arr["safe_engagement"].append(np.nan if dv["safe_engagement"] is None else float(dv["safe_engagement"]))
            arr["over_refusal"].append(np.nan)
        else:
            arr["refused"].append(np.nan if lab is None else float(lab["refused"]))
            arr["harmful_compliance"].append(np.nan if lab is None else float(lab["harmful_content"]))
            arr["safe_engagement"].append(np.nan)
            arr["over_refusal"].append(np.nan if dv["over_refusal"] is None else float(dv["over_refusal"]))
        arr["judged"].append(judged)
        arr["proxy_refused"].append(float(keyword_proxy(r["response"])["refused"]))
        arr["n_new_tokens"].append(r["n_new_tokens"])
    return {k: np.array(v, dtype=np.float64) for k, v in arr.items()}, jstats


def finish_judged_cell(m: str, name: str, recs: list[dict], arrays: dict, meta: dict) -> None:
    lab, jstats = judge_arrays(recs)
    arrays = {**arrays, **lab}
    meta = {**meta, "judge_stats": jstats, "judged_utc": utc_now()}
    save_cell(m, name, arrays, meta)
    logger.info(f"{m}: {name} judged {jstats['n_records']} recs, api {jstats['n_api_calls_made']}, "
                f"cache {jstats['n_cache_hits']}, NA {jstats['n_na']}, proxy {jstats['n_proxy']}, "
                f"ledger ${jstats['ledger_usd_after']:.4f}")


def write_private_gens(m: str, name: str, recs: list[dict]) -> None:
    gdir = PRIVATE / "gens"
    gdir.mkdir(exist_ok=True)
    with open(gdir / f"{m}__{name}.jsonl", "w") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------------------------
# context per model
# ---------------------------------------------------------------------------------------------
class Ctx:
    def __init__(self, m: str, repo: str, tag: str | None, items: dict, smoke: bool):
        import torch
        from engine import Engine
        self.m, self.repo, self.tag, self.items, self.smoke = m, repo, tag, items, smoke
        with Timer(f"{m}: load {repo}"):
            self.eng = Engine(repo, device=DEVICE)
        cfg = self.eng.cfg
        self.kv_per_tok = int(cfg.num_hidden_layers * 2 * cfg.num_key_value_heads * getattr(
            cfg, "head_dim", cfg.hidden_size // cfg.num_attention_heads) * 2)
        self.L = self.eng.L
        self.bands = bands_for(self.L) if smoke else BANDS
        tok_ids = jload(H2 / "harvest" / (tag or "Qwen--Qwen3-4B") / "token_ids.json")
        self.ref_ids, self.ctl_ids = list(tok_ids["refusal"]), list(tok_ids["control"])
        # template identity check (the D2 inputs are pre-templated; ours must match the tokenizer)
        for x in items["harm_eval"][:2] + items["arc_eval"][:1]:
            assert self.eng.chat_render(x["request"]) == x["input"], "chat template mismatch"
        if smoke:
            self.dirs_np = self._refit_smoke()
        else:
            dpath = PRIVATE / f"directions_disk_{m}.npz"
            if not dpath.exists():                       # third checkpoint (GPU addendum): same disk refit
                from prep import disk_directions
                stim = jload(H2 / "assets/stimuli.json")["rows"]
                dd0 = disk_directions(tag, stim)
                np.savez(dpath, F=dd0["F"], FperpU=dd0["FperpU"], mu_easy_benign=dd0["mu_easy_benign"],
                         Ubasis=dd0["Ubasis"], d_hard=dd0["d_hard"], l_star=np.array(dd0["l_star"]))
                jdump(RESULTS / f"disk_readouts_{m}.json",
                      {"l_star": dd0["l_star"], "d_hard_by_layer": dd0["d_hard"].tolist(),
                       "d_easy_by_layer": dd0["d_easy"].tolist(), "bl1_truelogit": dd0["bl1_truelogit"],
                       "cos_F_iter1": dd0["cos_i1"], "utc": utc_now()})
                logger.info(f"{m}: disk directions fitted (l_star={dd0['l_star']})")
            dd = np.load(dpath)
            self.dirs_np = {"F": dd["F"].astype(np.float32), "FperpU": dd["FperpU"].astype(np.float32),
                            "target": dd["mu_easy_benign"].astype(np.float32)}
            self.l_star = int(dd["l_star"])
        self.torch = torch
        self.status: dict = {"model": m, "repo": repo, "t_load_s": self.eng.t_load, "device": str(self.eng.device),
                             "gen_config_check": self.eng.gen_config_check}
        self._ro = None

    def _refit_smoke(self) -> dict:
        """F4 refit path (Qwen3-0.6B has no A_prompt in this lane): prompt-only pass over 64 EASY stimuli."""
        stim = jload(H2 / "assets/stimuli.json")["rows"]
        easy = [r for r in stim if r["set_id"] == 0][:32] + [r for r in stim if r["set_id"] == 0][48:80]
        seqs = self.eng.encode([self.eng.chat_render(r["text"]) for r in easy])
        st = self.eng.prompt_states(seqs, full=True, keep_logits=False)["full"].numpy()
        y = np.array([r["y"] for r in easy])
        F = np.stack([st[y == 1, l].mean(0) - st[y == 0, l].mean(0) for l in range(self.L)])
        F /= np.linalg.norm(F, axis=1, keepdims=True)
        tgt = np.stack([st[y == 0, l].mean(0) for l in range(self.L)])
        self.l_star = int(self.L * 0.7)
        return {"F": F.astype(np.float32), "FperpU": F.astype(np.float32), "target": tgt.astype(np.float32)}

    def tensors(self) -> dict:
        t = self.torch
        return {k: t.from_numpy(np.ascontiguousarray(v)) for k, v in self.dirs_np.items()}

    def readout(self) -> dict:
        if self._ro is None:
            t = self.torch
            F, N6, FU = self.dirs_np["F"], self.dirs_np["N6"], self.dirs_np["FperpU"]
            self._ro = {l: t.from_numpy(np.stack([F[l], N6[l], FU[l]]).astype(np.float32)).to(self.eng.device)
                        for l in range(self.L)}
        return self._ro


# ---------------------------------------------------------------------------------------------
# registered stages
# ---------------------------------------------------------------------------------------------
def stage_unit(ctx: Ctx) -> None:
    name = "unit_stimuli"
    if have_cell(ctx.m, name) or ctx.smoke:
        return
    stim = jload(H2 / "assets/stimuli.json")["rows"]
    pick = [0, 50, 96, 130, 180, 200, 230, 255]
    seqs = ctx.eng.encode([ctx.eng.chat_render(stim[i]["text"]) for i in pick])
    with Timer(f"{ctx.m}: unit check 8 stimuli"):
        st = ctx.eng.prompt_states(seqs, full=True, keep_logits=False)["full"].numpy()          # [8, L, d]
    A = np.load(H2 / "harvest" / ctx.tag / "A_prompt.npy", mmap_mode="r")
    cos, rel = np.zeros((len(pick), ctx.L)), np.zeros((len(pick), ctx.L))
    for k, i in enumerate(pick):
        for l in range(ctx.L):
            a = np.asarray(A[i, l + 1], np.float32)
            b = st[k, l]
            cos[k, l] = a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
            rel[k, l] = np.linalg.norm(a - b) / (np.linalg.norm(a) + 1e-12)
    meta = {"stimuli_idx": pick, "min_cos": float(cos[:, :-1].min()), "median_cos": float(np.median(cos[:, :-1])),
            "max_rel_err": float(rel[:, :-1].max()), "median_rel_err": float(np.median(rel[:, :-1])),
            "note": "layers 0..L-2 compared (the stored index L is post-final-norm)",
            "device": str(ctx.eng.device), "pass": bool(cos[:, :-1].min() > 0.99)}
    logger.info(f"{ctx.m}: A_prompt reproduction {meta}")
    save_cell(ctx.m, name, {"cos": cos, "rel": rel}, meta)


def stage_twins(ctx: Ctx) -> None:
    """N6 = unit(mean(safe twin) - mean(unsafe twin)) per layer, 85 confirmatory pairs, prompt-only pass."""
    name = "twins_N6"
    tw = ctx.items["twins"][: (8 if ctx.smoke else None)]
    dfile = PRIVATE / f"directions_{ctx.m}.npz"
    if not have_cell(ctx.m, name) or not dfile.exists():
        seqs = ctx.eng.encode([t["safe_input"] for t in tw] + [t["unsafe_input"] for t in tw])
        with Timer(f"{ctx.m}: twin pass ({len(seqs)} prompts)"):
            st = ctx.eng.prompt_states(seqs, full=True, keep_logits=False)["full"].numpy()
        n = len(tw)
        safe, unsafe = st[:n], st[n:]
        N6 = safe.mean(0) - unsafe.mean(0)
        N6 /= np.linalg.norm(N6, axis=1, keepdims=True)
        # in-sample twin separation along N6 per layer -> N6 best layer
        dsep = np.zeros(ctx.L)
        for l in range(ctx.L):
            ps, pu = safe[:, l] @ N6[l], unsafe[:, l] @ N6[l]
            sp = np.sqrt(((n - 1) * ps.var(ddof=1) + (n - 1) * pu.var(ddof=1)) / (2 * n - 2))
            dsep[l] = (ps.mean() - pu.mean()) / max(sp, 1e-9)
        lo, hi = (N6_LSTAR_RANGE if not ctx.smoke else (2, ctx.L - 3))
        n6_best = int(lo + np.argmax(dsep[lo:hi + 1]))
        F = ctx.dirs_np["F"]
        N6perp = N6 - (N6 * F).sum(1, keepdims=True) * F
        N6perp /= np.linalg.norm(N6perp, axis=1, keepdims=True)
        midx = list(ALL_MODELS).index(ctx.m) if ctx.m in ALL_MODELS else 9
        U = __import__("engine").random_pool(F, N6, J_POOL, midx, SEED)
        np.savez(dfile, N6=N6.astype(np.float32), N6perp=N6perp.astype(np.float32),
                 U=U, n6_best=np.array(n6_best), dsep=dsep)
        cosFN6 = [float(F[l] @ N6[l]) for l in range(ctx.L)]
        meta = {"n_pairs": n, "n6_best_layer": n6_best, "twin_d_by_layer": dsep.tolist(),
                "cos_F_N6_by_layer": cosFN6, "orientation": "N6 points from unsafe-twin toward safe-twin mean",
                "random_pool": {"J": J_POOL, "orthogonal_to": "span{F_l, N6_l}", "seed": "(SEED, model_idx, l, j)"},
                "max_abs_cos_U_F": float(np.abs(np.einsum("ljd,ld->lj", U, F)).max()),
                "max_abs_cos_U_N6": float(np.abs(np.einsum("ljd,ld->lj", U, N6)).max())}
        logger.info(f"{ctx.m}: N6 best layer {n6_best} (d={dsep[n6_best]:.2f}); cos(F,N6) at l*: "
                    f"{cosFN6[min(ctx.l_star, ctx.L - 1)]:.3f}")
        save_cell(ctx.m, name, {"twin_d": dsep, "cos_F_N6": np.array(cosFN6)}, meta)
    dd = np.load(dfile)
    ctx.dirs_np.update({"N6": dd["N6"], "N6perp": dd["N6perp"], "U": dd["U"]})
    ctx.n6_best = int(dd["n6_best"])
    ctx._ro = None


def stage_decod(ctx: Ctx) -> None:
    name = "decod_arm0"
    if have_cell(ctx.m, name):
        return
    k = 8 if ctx.smoke else None
    xs = ctx.items["decod_harm"][:k] + ctx.items["decod_hb"][:k]
    seqs = ctx.eng.encode([x["input"] for x in xs])
    with Timer(f"{ctx.m}: decodability items ({len(seqs)})"):
        o = ctx.eng.prompt_states(seqs, readout=ctx.readout(), keep_logits=False)
    y = np.array([1 if x["kind"] == "dharm" else 0 for x in xs])
    save_cell(ctx.m, name, {"proj": o["proj"].numpy().astype(np.float32), "y": y},
              {"item_ids": [x["item_id"] for x in xs], "readout_dirs": ["F", "N6", "FperpU"]})


def eval_items(ctx: Ctx) -> list[dict]:
    k = 8 if ctx.smoke else None
    return ctx.items["harm_eval"][:k] + ctx.items["hb_eval"][:k]


def build_prefixes(ctx: Ctx, xs: list[dict], chunk: int, tag: str) -> list:
    from engine import chunks_by_length
    seqs = ctx.eng.encode([x["input"] for x in xs])
    groups = chunks_by_length([len(s) for s in seqs], chunk)
    pres = []
    with Timer(f"{ctx.m}: prefill {tag} ({len(xs)} items, {len(groups)} chunks)"):
        for g in groups:
            pres.append(ctx.eng.prefill([xs[i]["item_id"] for i in g], [seqs[i] for i in g]))
    mb = sum(p.nbytes() for p in pres) / 1e6
    logger.info(f"{ctx.m}: {tag} prefix caches {mb:.0f} MB; max prompt len {max(len(s) for s in seqs)}")
    return pres


def run_rows(ctx: Ctx, pres: list, arm_rows_fn, *, readout: bool = True, max_new: int = 0,
             label: str = "", next_tok: dict | None = None) -> dict:
    """For every prefix chunk, build rows = items x arms (arm_rows_fn(item_index) -> list[Row]), split into
    passes that respect the KV budget (never splitting an item's rows), run them, and concatenate.
    next_tok: optional {item_id: token id} -> per-row log-prob of that token at the readout position (lp_next)."""
    import torch
    from engine import logit_outcomes
    D = ctx.tensors()
    ro = ctx.readout() if readout else None
    acc = {"meta": [], "RD": [], "G1": [], "T1ref": [], "tok1": [], "proj": [], "tokens": [], "disp": [],
           "lp_next": []}
    t0 = time.time()
    n_rows_total = 0
    for pre in pres:
        per_item = [arm_rows_fn(i) for i in range(pre.n)]
        k_per = max(1, max(len(v) for v in per_item))
        s = 0
        while s < pre.n:
            items_per_pass = max(1, max_rows_for(pre.T + pre.S + max_new, ctx.kv_per_tok) // k_per)
            e = min(pre.n, s + items_per_pass)
            rows = [r for i in range(s, e) for r in per_item[i]]
            if not rows:
                s = e
                continue
            try:
                spec = ctx.eng.build_spec(rows, D, ro, ctx.bands)
                res = ctx.eng.stacked_pass(pre, rows, spec, max_new=max_new)
            except Exception as ex:  # noqa: BLE001
                if DEVICE == "cuda" and is_oom(ex) and items_per_pass > 1:
                    spec = res = None
                    on_oom(label)
                    continue
                raise
            lo = logit_outcomes(res["logits"], ctx.ref_ids, ctx.ctl_ids)
            acc["meta"] += rows_meta(rows, pre.item_ids)
            for key in ("RD", "G1", "T1ref", "tok1"):
                acc[key].append(lo[key])
            if next_tok is not None:
                lsm = torch.log_softmax(res["logits"].float(), dim=-1)
                tk = torch.tensor([next_tok.get(pre.item_ids[r.item], -1) for r in rows], device=lsm.device)
                lp = lsm.gather(1, tk.clamp_min(0)[:, None])[:, 0]
                lp = torch.where(tk >= 0, lp, torch.full_like(lp, float("nan")))
                acc["lp_next"].append(lp.cpu().numpy().astype(np.float64))
            if spec.proj is not None:
                acc["proj"].append(spec.proj.cpu().numpy().astype(np.float32))
            if max_new > 1:
                acc["tokens"].append(res["tokens"].numpy())
            acc["disp"].append(disp_summary(spec, rows))
            n_rows_total += len(rows)
            del spec, res
            s = e
    dt = time.time() - t0
    logger.info(f"{ctx.m}: {label} {n_rows_total} rows in {dt:.0f}s ({dt / max(1, n_rows_total):.4f}s/row)")
    out = {"meta": acc["meta"], "disp": acc["disp"], "seconds": dt}
    for key in ("RD", "G1", "T1ref", "tok1", "lp_next"):
        out[key] = np.concatenate(acc[key]) if acc[key] else np.zeros(0)
    out["proj"] = np.concatenate(acc["proj"]) if acc["proj"] else np.zeros((0, ctx.L, 3), np.float32)
    if acc["tokens"]:
        W = max(t.shape[1] for t in acc["tokens"])
        out["tokens"] = np.concatenate([np.pad(t, ((0, 0), (0, W - t.shape[1])), constant_values=ctx.eng.pad_id)
                                        for t in acc["tokens"]])
    return out


def save_rows_cell(ctx: Ctx, name: str, out: dict, extra_meta: dict) -> None:
    arrays = {k: out[k] for k in ("RD", "G1", "T1ref", "tok1")}
    if len(out.get("lp_next", [])):
        arrays["lp_next"] = out["lp_next"]
    arrays["proj"] = out["proj"].astype(np.float16)
    meta = {"rows": out["meta"], "disp": out["disp"], "seconds": out["seconds"], "utc": utc_now(),
            "hook_hash": HOOK_HASH, **extra_meta}
    save_cell(ctx.m, name, arrays, meta)


def stage_arm0(ctx: Ctx, pres: list) -> None:
    from engine import Row
    name = "P_arm0"
    if not have_cell(ctx.m, name):
        out = run_rows(ctx, pres, lambda i: [Row(i, "0")], label="arm0")
        save_rows_cell(ctx, name, out, {"site": "P", "arm": "0"})
    hc = RESULTS / f"hook_checks_{ctx.m}.json"
    if hc.exists() and jload(hc).get("hook_hash") == HOOK_HASH:
        return
    # ---- hook checks on a mixed stacked pass (same rows, same batch shape in all three runs) ----
    pre = pres[0]
    n = min(8, pre.n)
    band = "B3"
    rows = [r for i in range(n) for r in (Row(i, "0"), Row(i, "F", band), Row(i, "RF", band, 1), Row(i, "N6", band),
                                          Row(i, "RN6", band, 1))]
    D = ctx.tensors()
    spec = ctx.eng.build_spec(rows, D, None, ctx.bands)
    with Timer(f"{ctx.m}: hook check, active spec, 16 tokens"):
        res_h = ctx.eng.stacked_pass(pre, rows, spec, max_new=16)
    spec_off = ctx.eng.build_spec(rows, D, None, ctx.bands)
    spec_off.active = False
    res_off = ctx.eng.stacked_pass(pre, rows, spec_off, max_new=16)
    ctx.eng.remove_hooks()
    try:
        res_n = ctx.eng.stacked_pass(pre, rows, None, max_new=16)
    finally:
        ctx.eng.register_hooks()
    zero_idx = [k for k, r in enumerate(rows) if r.arm == "0"]
    a1_tok = bool((res_off["tokens"] == res_n["tokens"]).all())
    a1_dlog = float((res_off["logits"] - res_n["logits"]).abs().max())
    a2_dlog = float((res_h["logits"][zero_idx] - res_off["logits"][zero_idx]).abs().max())
    a2_tok = (res_h["tokens"][zero_idx] == res_off["tokens"][zero_idx]).all(dim=1)
    ds = disp_summary(spec, rows)
    ratios = [v for vv in ds["ratio_R_over_src"].values() for v in vv]
    resid = list(ds["resid_ratio_after_projection"].values())
    F_rows = [k for k, r in enumerate(rows) if r.arm == "F"]
    tok_changed_F = float((res_h["tokens"][F_rows] != res_off["tokens"][zero_idx]).any(dim=1).float().mean())
    check = {
        "hook_hash": HOOK_HASH, "device": str(ctx.eng.device),
        "a1_noop_hooks_equal_hooks_removed": {
            "n_rows": len(rows), "greedy16_identical_all_rows": a1_tok, "max_abs_dlogit_step1": a1_dlog,
            "pass": bool(a1_tok and a1_dlog == 0.0),
            "note": "hooks registered with an inactive spec vs hooks removed, identical batch"},
        "a2_arm0_rows_unaffected_by_active_rows": {
            "n_items": n, "max_abs_dlogit_step1": a2_dlog, "greedy16_identical_rows": int(a2_tok.sum()),
            "pass": bool(a2_dlog == 0.0),
            "note": "arm-0 rows share the batch with active F/R/N6 rows; any cross-row leak changes their step-1 "
                    "logits (bitwise). Later greedy tokens can differ only through batch-shape changes when "
                    "other rows hit EOS (reported, not a pass criterion on GPU)"},
        "b_residual_along_direction_after_projection": {"max_ratio_by_layer": ds["resid_ratio_after_projection"],
                                                        "max": float(max(resid)) if resid else None,
                                                        "pass": bool(resid and max(resid) < 1e-3)},
        "c_matched_displacement_ratio_R_over_F": {"min": float(min(ratios)) if ratios else None,
                                                  "max": float(max(ratios)) if ratios else None,
                                                  "pass": bool(ratios and abs(min(ratios) - 1) < 1e-3 and
                                                               abs(max(ratios) - 1) < 1e-3)},
        "F_changes_greedy16_fraction": tok_changed_F,
        "site_P_token1_note": "site P edits the last prompt position, so token 1 CAN change",
        "utc": utc_now(),
    }
    logger.info(f"{ctx.m}: hook checks {json.dumps(check)[:500]}")
    jdump(hc, check)
    if not (check["a1_noop_hooks_equal_hooks_removed"]["pass"] and
            check["a2_arm0_rows_unaffected_by_active_rows"]["pass"] and
            check["b_residual_along_direction_after_projection"]["pass"] and
            check["c_matched_displacement_ratio_R_over_F"]["pass"]):
        logger.error(f"{ctx.m}: HOOK CHECK FAILED -- see {hc}")
        if not ctx.smoke:
            raise RuntimeError("hook sanity check failed (F6): stop, fix, re-run")


GRID_GROUPS = {
    "grid1": lambda band, pos: (["F", "N6", "N6perp"] + [("RF", j) for j in (1, 2, 3)] +
                                [("RN6", j) for j in (1, 2, 3)] + (["POS"] if pos else [])),
    "grid2": lambda band, pos: ["F"] + [("RF", j) for j in range(4, 12)],
    "grid3": lambda band, pos: ["F"] + [("RF", j) for j in range(12, 21)] + ["N6", ("RN6", 4), ("RN6", 5)],
}


def arm_rows(i: int, band: str, arms: list):
    from engine import Row
    out = []
    for a in arms:
        if isinstance(a, tuple):
            out.append(Row(i, a[0], band, a[1]))
        else:
            out.append(Row(i, a, band))
    return out


def stage_grid(ctx: Ctx, pres: list, group: str, deadline: float) -> None:
    for band in ctx.bands:
        name = f"P_{band}_{group}"
        if have_cell(ctx.m, name):
            continue
        if time.time() > deadline:
            logger.warning(f"{ctx.m}: deadline reached before {name}; skipped (F3: draws cut before cells)")
            return
        arms = GRID_GROUPS[group](band, band in ("B3", "B4") and group == "grid1")
        if ctx.smoke:
            arms = arms[:5]
        out = run_rows(ctx, pres, lambda i, b=band, a=arms: arm_rows(i, b, a), label=f"{name}")
        save_rows_cell(ctx, name, out, {"site": "P", "band": band, "group": group, "layers": ctx.bands[band]})


GEN_ARMS = [("0", None, 0), ("F", "B3", 0), ("RF", "B3", 1), ("F", "B4", 0), ("RF", "B4", 1),
            ("N6", "B3", 0), ("RN6", "B3", 1), ("N6", "B4", 0), ("RN6", "B4", 1)]


def stage_gen(ctx: Ctx) -> None:
    """Registered F1 generation cell (24+24 items, 48 tokens, B3/B4 at P); judged in the background."""
    from engine import Row
    name = "gen_P"
    if have_cell(ctx.m, name) or f"{ctx.m}/{name}" in JW.pending:
        return
    k = 4 if ctx.smoke else 24
    gen_ids = set(ctx.items["gen_subset"]["harm"][:k] + ctx.items["gen_subset"]["hb"][:k])
    xs = [x for x in eval_items(ctx) if x["item_id"] in gen_ids] if not ctx.smoke else \
        ctx.items["harm_eval"][:k] + ctx.items["hb_eval"][:k]
    pres = build_prefixes(ctx, xs, chunk=16, tag="gen")
    arms = GEN_ARMS if not ctx.smoke else [("0", None, 0), ("F", "B4", 0), ("RF", "B4", 1)]

    def fn(i):
        return [Row(i, a, b, j) for (a, b, j) in arms]
    max_new = 16 if ctx.smoke else GEN_MAX_NEW
    out = run_rows(ctx, pres, fn, readout=False, max_new=max_new, label="gen")
    texts = ctx.eng.decode(ctx.torch.from_numpy(out["tokens"]))
    ntok = ctx.eng.n_new_tokens(ctx.torch.from_numpy(out["tokens"]))
    by_id = {x["item_id"]: x for x in xs}
    recs = []
    for mrow, txt, nt in zip(out["meta"], texts, ntok):
        x = by_id[mrow["item_id"]]
        recs.append({"model": ctx.m, **mrow, "kind": x["kind"], "request": x["request"], "response": txt,
                     "n_new_tokens": nt})
    write_private_gens(ctx.m, name, recs)
    arrays = {"RD": out["RD"], "G1": out["G1"], "T1ref": out["T1ref"], "tok1": out["tok1"]}
    meta = {"rows": out["meta"], "kinds": [r["kind"] for r in recs], "disp": out["disp"],
            "seconds": out["seconds"], "max_new_tokens": max_new, "site": "P",
            "label_source_note": "judged=1 judge/cache, 0.5 PROXY (keyword), 0 NA", "utc": utc_now()}
    JW.submit(f"{ctx.m}/{name}", functools.partial(finish_judged_cell, ctx.m, name, recs, arrays, meta))


# ---------------------------------------------------------------------------------------------
# GPU addendum: judged generation on every cell (sites P, D', E), 48+48 items, 80 new tokens
# ---------------------------------------------------------------------------------------------
def site_arms(site: str, band: str) -> list[tuple[str, int]]:
    if site == "P":
        return ([("0", 0), ("F", 0), ("N6", 0), ("N6perp", 0)] + [("RF", j) for j in (1, 2, 3)] +
                [("RN6", j) for j in (1, 2, 3)] + ([("POS", 0)] if band in ("B3", "B4") else []))
    return [("0", 0), ("F", 0), ("N6", 0)] + [("RFo", j) for j in (1, 2, 3)] + [("RN6o", j) for j in (1, 2, 3)]


WINDOWS = {"P": (0, 0), "D": (1, 8), "E": (5, 20), "LATE": (21, 40)}


def window_means(cap: np.ndarray) -> np.ndarray:
    """cap [R, T, L, K] (NaN after EOS) -> [R, 4, L, K] means over the P / D / E / LATE call windows."""
    R, T = cap.shape[:2]
    out = np.full((R, len(WINDOWS), cap.shape[2], cap.shape[3]), np.nan, np.float32)
    for w, (a, b) in enumerate(WINDOWS.values()):
        if a >= T:
            continue
        seg = cap[:, a:min(b, T - 1) + 1]
        cnt = np.isfinite(seg[..., 0, 0]).sum(1)
        with np.errstate(invalid="ignore"):
            m = np.nansum(seg, axis=1) / np.maximum(cnt, 1)[:, None, None]
        m[cnt == 0] = np.nan
        out[:, w] = m
    return out


def gen_site_cell(ctx: Ctx, pres: list, xs: list[dict], site: str, band: str, max_new: int,
                  arms: list | None = None, name: str | None = None) -> None:
    from engine import Row, logit_outcomes
    name = name or f"gen{site}_{band}"
    arms = arms or site_arms(site, band)
    D = ctx.tensors()
    ro = ctx.readout()
    meta_rows, toks, logit_out, logs, caps = [], [], [], [], []
    t0 = time.time()
    for pre in pres:
        s = 0
        while s < pre.n:
            items_per_pass = max(1, max_rows_for(pre.T + 1 + max_new, ctx.kv_per_tok) // len(arms))
            e = min(pre.n, s + items_per_pass)
            rows, sites = [], []
            for i in range(s, e):
                for (a, j) in arms:
                    rows.append(Row(i, a, None if a == "0" else band, j))
                    sites.append(site)
            try:
                res = ctx.eng.site_generate(pre, rows, sites, D, ctx.bands, max_new=max_new, readout=ro)
            except Exception as ex:  # noqa: BLE001
                if DEVICE == "cuda" and is_oom(ex) and items_per_pass > 1:
                    res = None
                    on_oom(name)
                    continue
                raise
            logit_out.append(logit_outcomes(res["logits"], ctx.ref_ids, ctx.ctl_ids))
            toks.append(res["tokens"].numpy())
            logs.append(res["log"])
            caps.append(window_means(res["cap"].numpy()))
            meta_rows += [{"item_id": pre.item_ids[r.item], "arm": r.arm, "band": r.band, "draw": r.draw,
                           "site": st} for r, st in zip(rows, sites)]
            del res
            s = e
    dt = time.time() - t0
    W_ = max(t.shape[1] for t in toks)
    tokens = np.concatenate([np.pad(t, ((0, 0), (0, W_ - t.shape[1])), constant_values=ctx.eng.pad_id) for t in toks])
    texts = ctx.eng.decode(ctx.torch.from_numpy(tokens))
    ntok = ctx.eng.n_new_tokens(ctx.torch.from_numpy(tokens))
    by_id = {x["item_id"]: x for x in xs}
    recs = [{"model": ctx.m, **mr, "kind": by_id[mr["item_id"]]["kind"], "request": by_id[mr["item_id"]]["request"],
             "response": txt, "n_new_tokens": nt} for mr, txt, nt in zip(meta_rows, texts, ntok)]
    write_private_gens(ctx.m, name, recs)
    arrays = {k_: np.concatenate([lo[k_] for lo in logit_out]) for k_ in ("RD", "G1", "T1ref", "tok1")}
    arrays["proj_win"] = np.concatenate(caps).astype(np.float16)
    # ---- site sanity checks ----
    zero_tok = {mr["item_id"]: tokens[k] for k, mr in enumerate(meta_rows) if mr["arm"] == "0"}
    e_same5, e_n, tok1_changed, n_int = 0, 0, {}, {}
    for kk, mr in enumerate(meta_rows):
        if mr["arm"] == "0":
            continue
        z = zero_tok[mr["item_id"]]
        if site == "E":
            e_n += 1
            e_same5 += int((tokens[kk, :5] == z[:5]).all())
        n_int[mr["arm"]] = n_int.get(mr["arm"], 0) + 1
        tok1_changed[mr["arm"]] = tok1_changed.get(mr["arm"], 0) + int(tokens[kk, 0] != z[0])
    any_changed = {}
    for kk, mr in enumerate(meta_rows):
        if mr["arm"] != "0":
            any_changed.setdefault(mr["arm"], []).append(int((tokens[kk] != zero_tok[mr["item_id"]]).any()))
    steps_seen: dict = {}
    for lg in logs:
        for s_, v in lg["edits_by_site_step"].items():
            steps_seen.setdefault(s_, set()).update(v)
    exp_steps = {"P": [0], "Dprime": [0] + list(range(1, 8)), "E": list(range(5, 21)), "D": list(range(1, 9))}[site]
    exp_steps = [t for t in exp_steps if t <= max_new - 1]        # the last decode call is t = max_new - 1
    disp_by = {}
    for lg in logs:
        for k_, v in lg["mean_disp_by_arm_site"].items():
            n_ = lg["n_disp_by_arm_site"][k_]
            a_ = disp_by.setdefault(k_, [0.0, 0])
            a_[0] += v * n_
            a_[1] += n_
    mean_disp = {k_: v[0] / max(1, v[1]) for k_, v in disp_by.items()}
    fkey = f"F|{site}"
    ratio_R_F = {k_: (v / mean_disp[fkey]) for k_, v in mean_disp.items()
                 if k_.startswith("RF") and fkey in mean_disp and mean_disp[fkey] > 0}
    n6key = f"N6|{site}"
    ratio_R_N6 = {k_: (v / mean_disp[n6key]) for k_, v in mean_disp.items()
                  if k_.startswith("RN6") and n6key in mean_disp and mean_disp[n6key] > 0}
    checks = {
        "E_tokens_1_to_5_identical_to_arm0": ({"n": e_n, "identical": e_same5, "pass": e_same5 == e_n}
                                             if site == "E" else None),
        "token1_changed_frac_by_arm": {a_: tok1_changed[a_] / n_int[a_] for a_ in n_int},
        "any_token_changed_frac_by_arm": {a_: float(np.mean(v)) for a_, v in any_changed.items()},
        "edit_steps_seen": {s_: sorted(v) for s_, v in steps_seen.items()},
        "expected_steps": exp_steps,
        "steps_pass": sorted(steps_seen.get(site, set())) == exp_steps,
        "resid_ratio_max_after_projection": max(lg["resid_ratio_max"] for lg in logs),
        "resid_pass": bool(max(lg["resid_ratio_max"] for lg in logs) < 1e-3),
        "mean_displacement_by_arm": mean_disp,
        "ratio_meanDisp_R_over_F": ratio_R_F, "ratio_meanDisp_RN6_over_N6": ratio_R_N6,
        "note": ("site P: matched displacement (RF/RN6 take c from the F/N6 row of the same item & band -> ratio "
                 "exactly 1 per position per layer); decode sites: own-coefficient R (x - (x.v)u), the ratio of "
                 "MEAN displacements is reported (exactly 1 only at the first band layer of the first edited call)"),
    }
    meta = {"rows": meta_rows, "kinds": [r["kind"] for r in recs], "logs": logs, "seconds": dt,
            "max_new_tokens": max_new, "checks": checks, "site": site, "band": band, "layers": ctx.bands[band],
            "arms": [list(a) for a in arms], "windows": {k_: list(v) for k_, v in WINDOWS.items()},
            "proj_win_dirs": ["F", "N6", "FperpU"],
            "site_windows": {k_: list(v) for k_, v in ctx.eng.SITE_WINDOWS.items()},
            "label_source_note": "judged=1 judge/cache, 0.5 PROXY (keyword), 0 NA", "utc": utc_now()}
    logger.info(f"{ctx.m}: {name} generated {len(recs)} rows in {dt:.0f}s; steps_pass {checks['steps_pass']} "
                f"resid_pass {checks['resid_pass']} tok1_changed {checks['token1_changed_frac_by_arm']}")
    JW.submit(f"{ctx.m}/{name}", functools.partial(finish_judged_cell, ctx.m, name, recs, arrays, meta))


def stage_gengrid(ctx: Ctx, site: str, deadline: float) -> None:
    todo = [b for b in ctx.bands if not have_cell(ctx.m, f"gen{site}_{b}") and f"{ctx.m}/gen{site}_{b}" not in JW.pending]
    if ctx.smoke:
        todo = [b for b in todo if b in ("B3", "B4")]
    if not todo:
        return
    xs = eval_items(ctx)
    max_new = 16 if ctx.smoke else GRID_MAX_NEW
    pres = build_prefixes(ctx, xs, chunk=24, tag=f"gen{site}")
    for band in todo:
        if time.time() > deadline:
            logger.warning(f"{ctx.m}: deadline reached before gen{site}_{band}; skipped")
            return
        gen_site_cell(ctx, pres, xs, site, band, max_new)
        logger.info(f"{ctx.m}: judge backlog {JW.backlog()} jobs")
    del pres


GENU_ARMS = [("0", 0), ("F", 0), ("FperpU", 0), ("RUo", 1), ("RUo", 2)]


def stage_genU(ctx: Ctx, deadline: float) -> None:
    """Plan optional 9(b), exploratory (not in the confirmatory Holm families): arm F_perpU (F with the top-8
    refusal-token unembedding rows projected out) at site P, all 6 bands, judged; own-coefficient random control
    RUo (x - (x.F_perpU)u), with F co-batched for exact pairing."""
    todo = [b for b in ctx.bands if not have_cell(ctx.m, f"genU_{b}") and f"{ctx.m}/genU_{b}" not in JW.pending]
    if ctx.smoke:
        todo = [b for b in todo if b in ("B3", "B4")]
    if not todo:
        return
    add_deviation("addition_genU", "optional 9(b): judged F_perpU arm at site P, all 6 bands (exploratory)",
                  "GPU slack after the primary grid", "additional exploratory cells only; not in any Holm family")
    xs = eval_items(ctx)
    max_new = 16 if ctx.smoke else GRID_MAX_NEW
    pres = build_prefixes(ctx, xs, chunk=24, tag="genU")
    for band in todo:
        if time.time() > deadline:
            logger.warning(f"{ctx.m}: deadline reached before genU_{band}; skipped")
            return
        gen_site_cell(ctx, pres, xs, "P", band, max_new, arms=GENU_ARMS, name=f"genU_{band}")
    del pres


def stage_arc(ctx: Ctx) -> None:
    from engine import Row
    name = "arc_P"
    if have_cell(ctx.m, name):
        return
    k = 8 if ctx.smoke else None
    xs = ctx.items["arc_eval"][:k]
    pres = build_prefixes(ctx, xs, chunk=16, tag="arc")
    letters = {L_: ctx.eng.tok(L_, add_special_tokens=False)["input_ids"] for L_ in "ABCDE"}
    assert all(len(v) == 1 for v in letters.values()), letters
    letter_id = {k_: v[0] for k_, v in letters.items()}
    # arm 0 with a 4-token greedy continuation (format check), then token-1 under every arm
    out0 = run_rows(ctx, pres, lambda i: [Row(i, "0")], readout=False, max_new=ARC_MAX_NEW, label="arc arm0")
    texts0 = ctx.eng.decode(ctx.torch.from_numpy(out0["tokens"]))
    bands = list(ctx.bands)
    arms = [("F", 0), ("N6", 0), ("N6perp", 0), ("RF", 1), ("RF", 2), ("RF", 3), ("RN6", 1), ("RN6", 2), ("RN6", 3)]
    out = run_rows(ctx, pres, lambda i: [Row(i, a, b, j) for b in bands for (a, j) in arms], readout=False,
                   label="arc arms")
    by_id = {x["item_id"]: x for x in xs}
    key = np.array([letter_id.get(by_id[m_["item_id"]]["answer"].strip()[:1], -1) for m_ in out["meta"]])
    key0 = np.array([letter_id.get(by_id[m_["item_id"]]["answer"].strip()[:1], -1) for m_ in out0["meta"]])
    correct = (out["tok1"] == key).astype(np.float64)
    correct0 = (out0["tok1"] == key0).astype(np.float64)
    fmt_ok = [t[:1] in "ABCDE" and len(t) > 0 for t in texts0]
    meta = {"rows0": out0["meta"], "rows": out["meta"], "arm0_first_token_is_letter_frac": float(np.mean(fmt_ok)),
            "arm0_4tok_letter_match": float(np.mean([t[:1] == by_id[m_["item_id"]]["answer"].strip()[:1]
                                                     for t, m_ in zip(texts0, out0["meta"])])),
            "site_note": "token 1 is produced by the prompt pass: site D' flips == site P flips for the prompt-"
                         "position edit; sites D and E cannot touch token 1 (flip rate 0 by construction)",
            "disp": out["disp"], "seconds": out["seconds"] + out0["seconds"], "utc": utc_now()}
    save_cell(ctx.m, name, {"correct": correct, "correct0": correct0, "tok1": out["tok1"], "tok1_0": out0["tok1"],
                            "RD": out["RD"]}, meta)
    logger.info(f"{ctx.m}: ARC arm-0 acc {correct0.mean():.3f}, letter-format {np.mean(fmt_ok):.3f}")


# ---------------------------------------------------------------------------------------------
# GPU addendum: readouts, decode-step decodability, forward-only windows, GSM8K collateral
# ---------------------------------------------------------------------------------------------
def stage_stimro(ctx: Ctx) -> None:
    """Readouts under site-P intervention on the 256 A_prompt stimuli (BL1_easy / BL1_hard / N1 / N6 / N2)."""
    from engine import Row
    name = "stimro_P"
    if have_cell(ctx.m, name):
        return
    stim = jload(H2 / "assets/stimuli.json")["rows"]
    if ctx.smoke:
        stim = stim[:16] + stim[128:144]
    xs = [{"item_id": f"stim_{r['stim_id'] if 'stim_id' in r else k}", "input": ctx.eng.chat_render(r["text"])}
          for k, r in enumerate(stim)]
    pres = build_prefixes(ctx, xs, chunk=32, tag="stimro")
    bands = list(ctx.bands)
    arms = [("F", 0), ("N6", 0), ("RF", 1)]
    out = run_rows(ctx, pres, lambda i: [Row(i, "0")] + [Row(i, a, b, j) for b in bands for (a, j) in arms],
                   label="stimro")
    save_rows_cell(ctx, name, out, {"site": "P", "stimuli_y": [r["y"] for r in stim],
                                    "stimuli_set_id": [r["set_id"] for r in stim],
                                    "stim_item_ids": [x["item_id"] for x in xs],
                                    "note": "EASY = set_id 0; BL1_easy / BL1_hard computed separately, never pooled"})


def stage_decodgen(ctx: Ctx) -> None:
    """Decode-step decodability: arm-0 greedy on the 32+32 decodability items, per-call projections."""
    from engine import Row
    name = "decodgen_arm0"
    if have_cell(ctx.m, name):
        return
    k = 8 if ctx.smoke else None
    xs = ctx.items["decod_harm"][:k] + ctx.items["decod_hb"][:k]
    pres = build_prefixes(ctx, xs, chunk=32, tag="decodgen")
    D = ctx.tensors()
    ro = ctx.readout()
    caps, meta_rows, ntoks = [], [], []
    t0 = time.time()
    for pre in pres:
        rows = [Row(i, "0") for i in range(pre.n)]
        res = ctx.eng.site_generate(pre, rows, ["P"] * len(rows), D, ctx.bands, max_new=DECOD_GEN_NEW, readout=ro)
        caps.append(window_means(res["cap"].numpy()))
        ntoks += ctx.eng.n_new_tokens(res["tokens"])
        meta_rows += [pre.item_ids[r.item] for r in rows]
    by_id = {x["item_id"]: x for x in xs}
    y = np.array([1 if by_id[i]["kind"] == "dharm" else 0 for i in meta_rows])
    save_cell(ctx.m, name, {"proj_win": np.concatenate(caps).astype(np.float32), "y": y,
                            "n_new_tokens": np.array(ntoks)},
              {"item_ids": meta_rows, "windows": {k_: list(v) for k_, v in WINDOWS.items()},
               "proj_win_dirs": ["F", "N6", "FperpU"], "seconds": time.time() - t0, "utc": utc_now()})


def arm0_tokens(ctx: Ctx, xs: list[dict]) -> dict:
    """Arm-0 greedy continuation (GRID_MAX_NEW tokens) of the eval items (private; teacher-forced prefixes)."""
    from engine import Row
    p = PRIVATE / f"arm0_tokens_{ctx.m}__{HOOK_HASH}.json"
    if p.exists():
        return jload(p)
    pres = build_prefixes(ctx, xs, chunk=24, tag="arm0tok")
    out = run_rows(ctx, pres, lambda i: [Row(i, "0")], readout=False,
                   max_new=(16 if ctx.smoke else GRID_MAX_NEW) + 1, label="arm0 tokens")
    toks = {}
    for mr, t in zip(out["meta"], out["tokens"]):
        real = []
        for tk in t.tolist():
            if tk in ctx.eng.eos or tk == ctx.eng.pad_id:
                break
            real.append(int(tk))
        toks[mr["item_id"]] = real
    jdump(p, toks, indent=None)
    return toks


def stage_span(ctx: Ctx, site: str, deadline: float) -> None:
    """Forward-only teacher-forced window (site D: decode inputs 1-8; E: 5-20) on the arm-0 greedy prefix.
    Outcome at the position after the window: RD / G1 / T1ref and lp_next = log p(arm-0 token t1+1)."""
    from engine import Row, chunks_by_length
    t_a, t_b = {"D": (1, 8), "E": (5, 20)}[site]
    if ctx.smoke:
        t_a, t_b = {"D": (1, 4), "E": (3, 8)}[site]
    xs = eval_items(ctx)
    todo = [b for b in ctx.bands if not have_cell(ctx.m, f"span{site}_{b}")]
    if not todo:
        return
    toks = arm0_tokens(ctx, xs)
    prompt = {x["item_id"]: s for x, s in zip(xs, ctx.eng.encode([x["input"] for x in xs]))}
    keep = [x for x in xs if len(toks[x["item_id"]]) >= t_b]          # window fully inside the response
    excluded = [x["item_id"] for x in xs if len(toks[x["item_id"]]) < t_b]
    nxt = {x["item_id"]: (toks[x["item_id"]][t_b] if len(toks[x["item_id"]]) > t_b else -1) for x in keep}
    pre_seqs = [prompt[x["item_id"]] + toks[x["item_id"]][:t_a - 1] for x in keep]
    span_seqs = [toks[x["item_id"]][t_a - 1:t_b] for x in keep]
    groups = chunks_by_length([len(s) for s in pre_seqs], 24)
    pres = [ctx.eng.prefill_span([keep[i]["item_id"] for i in g], [pre_seqs[i] for i in g], [span_seqs[i] for i in g])
            for g in groups]
    for band in todo:
        if time.time() > deadline:
            logger.warning(f"{ctx.m}: deadline reached before span{site}_{band}; skipped")
            return
        arms = (["F", "N6"] + [("RF", j) for j in range(1, 21)] + [("RN6", j) for j in range(1, 6)])
        if ctx.smoke:
            arms = arms[:5]
        out = run_rows(ctx, pres, lambda i, b=band, a=arms: [Row(i, "0")] + arm_rows(i, b, a),
                       label=f"span{site}_{band}", next_tok=nxt)
        save_rows_cell(ctx, f"span{site}_{band}", out,
                       {"site": site, "band": band, "window_decode_inputs": [t_a, t_b], "layers": ctx.bands[band],
                        "n_items": len(keep), "excluded_short_response": excluded,
                        "note": "arm-0 rows repeated in every band cell (identical inputs); readout = next-token "
                                "distribution after the window; lp_next = log p(arm-0 token after the window)"})


# ---------------------------------------------------------------------------------------------
# T3 disambiguation control (session 4 addition): the SAME directions ablated at ALL positions
# (every prompt position + every decode call) within a band, or in all 36 layers (abliteration logic)
# ---------------------------------------------------------------------------------------------
GENG_ARMS = [("F", 0), ("RFo", 1), ("N6", 0), ("RN6o", 1)]


def _subset_ops(full_ops: dict, act_d) -> dict:
    """Own-coefficient ops restricted to the active rows (src = self)."""
    import torch
    out = {}
    n = int(act_d.shape[0])
    for l, op in full_ops.items():
        out[l] = {"V": op["V"].index_select(0, act_d), "W": op["W"].index_select(0, act_d),
                  "src": torch.arange(n, device=act_d.device), "has": op["has"].index_select(0, act_d),
                  "patch": None, "target": None}
    return out


def global_generate(ctx: Ctx, seqs: list[list[int]], rows: list, bands_ext: dict, max_new: int) -> dict:
    """Greedy generation with projection-out at EVERY position: the full prompt prefill (all positions) and
    every decode call, in the band's layers. Own-coefficient arms only (F, N6, RFo, RN6o)."""
    import torch
    from engine import Spec, logit_outcomes
    eng, dev = ctx.eng, ctx.eng.device
    D = ctx.tensors()
    R = len(rows)
    ids, mask = eng._left_pad([seqs[r.item] for r in rows], eng.pad_id)
    ids, mask = ids.to(dev), mask.to(dev)
    pos = eng._positions(mask)
    spec = eng.build_spec(rows, D, None, bands_ext)
    full_ops = spec.layer_ops
    spec.n_pos = ids.shape[1]
    eng.spec = spec
    try:
        with torch.no_grad():
            out = eng.model(input_ids=ids, attention_mask=mask, position_ids=pos, use_cache=True, logits_to_keep=1)
    finally:
        eng.spec = None
    resid0 = float(torch.stack(list(spec.resid_ratio.values())).max()) if spec.resid_ratio else None
    logits0 = out.logits[:, -1, :].float()
    lo = logit_outcomes(logits0, ctx.ref_ids, ctx.ctl_ids)
    nxt = logits0.argmax(-1)
    past = out.past_key_values
    del out
    res = torch.full((R, max_new), eng.pad_id, dtype=torch.long)
    act = torch.arange(R)
    cur_attn, cur_pos = mask, pos[:, -1]
    with torch.no_grad():
        for step in range(max_new):
            nxt_c = nxt.cpu()
            res[act, step] = nxt_c
            done = torch.isin(nxt_c, eng.eos_cpu)
            if step == max_new - 1 or bool(done.all()):
                break
            if bool(done.any()):
                keep = (~done).nonzero().squeeze(1)
                keep_d = keep.to(dev)
                past.batch_select_indices(keep_d)
                act, nxt, cur_attn, cur_pos = act[keep], nxt[keep_d], cur_attn[keep_d], cur_pos[keep_d]
            cur_attn = torch.cat([cur_attn, torch.ones((cur_attn.shape[0], 1), dtype=cur_attn.dtype, device=dev)],
                                 dim=1)
            cur_pos = cur_pos + 1
            eng.spec = Spec(layer_ops=_subset_ops(full_ops, act.to(dev)), n_pos=1)
            try:
                o = eng.model(input_ids=nxt[:, None], attention_mask=cur_attn, position_ids=cur_pos[:, None],
                              past_key_values=past, use_cache=True, logits_to_keep=1)
            finally:
                eng.spec = None
            past = o.past_key_values
            nxt = o.logits[:, -1, :].argmax(-1)
            del o
    return {"tokens": res, "lo": lo, "resid_ratio_prefill": resid0,
            "disp": {str(l): float(dn.float().mean()) for l, (c, dn) in list(spec.disp.items())[:1]}}


def stage_genG(ctx: Ctx, deadline: float) -> None:
    """All-position ablation of F / N6 (+ own-coefficient random controls) per band and in all layers (ALL)."""
    from engine import Row
    bands_ext = {**ctx.bands, "ALL": list(range(ctx.L))}
    todo = [b for b in bands_ext if not have_cell(ctx.m, f"genG_{b}") and f"{ctx.m}/genG_{b}" not in JW.pending]
    if ctx.smoke:
        todo = [b for b in todo if b in ("B4", "ALL")]
    if not todo:
        return
    add_deviation("addition_genG",
                  "T3 disambiguation control: F / N6 projected out at ALL positions (every prompt position and every "
                  "decode call) per band and in all 36 layers (ALL), judged, with own-coefficient random controls",
                  "the site-local F arm at P changes token 1 in ~50% of rows but barely moves judged refusal; the plan's "
                  "T3 requires ruling out a hook/sign/direction problem before calling site-local cells null",
                  "additional exploratory cells; not in the confirmatory Holm families")
    xs = eval_items(ctx)
    seqs = ctx.eng.encode([x["input"] for x in xs])
    max_new = 16 if ctx.smoke else GRID_MAX_NEW
    for band in todo:
        if time.time() > deadline:
            logger.warning(f"{ctx.m}: deadline reached before genG_{band}; skipped")
            return
        name = f"genG_{band}"
        rows_all = [Row(i, "0") for i in range(len(xs))] + [Row(i, a, band, j) for i in range(len(xs))
                                                             for (a, j) in GENG_ARMS]
        rows_all.sort(key=lambda r: (len(seqs[r.item]), r.item))
        T_max = max(len(s) for s in seqs)
        rpp = max(4, max_rows_for(T_max + max_new, ctx.kv_per_tok))
        meta_rows, toks, los, resid, t0 = [], [], [], [], time.time()
        s_ = 0
        while s_ < len(rows_all):
            chunk = rows_all[s_:s_ + rpp]
            try:
                g = global_generate(ctx, seqs, chunk, bands_ext, max_new)
            except Exception as ex:  # noqa: BLE001
                if DEVICE == "cuda" and is_oom(ex) and rpp > 4:
                    on_oom(name)
                    rpp = max(4, rpp // 2)
                    continue
                raise
            toks.append(g["tokens"].numpy())
            los.append(g["lo"])
            if g["resid_ratio_prefill"] is not None:
                resid.append(g["resid_ratio_prefill"])
            meta_rows += [{"item_id": xs[r.item]["item_id"], "arm": r.arm, "band": r.band, "draw": r.draw,
                           "site": "ALLPOS"} for r in chunk]
            s_ += len(chunk)
        W_ = max(t.shape[1] for t in toks)
        tokens = np.concatenate([np.pad(t, ((0, 0), (0, W_ - t.shape[1])), constant_values=ctx.eng.pad_id)
                                 for t in toks])
        texts = ctx.eng.decode(ctx.torch.from_numpy(tokens))
        ntok = ctx.eng.n_new_tokens(ctx.torch.from_numpy(tokens))
        by_id = {x["item_id"]: x for x in xs}
        recs = [{"model": ctx.m, **mr, "kind": by_id[mr["item_id"]]["kind"], "request": by_id[mr["item_id"]]["request"],
                 "response": txt, "n_new_tokens": nt} for mr, txt, nt in zip(meta_rows, texts, ntok)]
        write_private_gens(ctx.m, name, recs)
        arrays = {k_: np.concatenate([lo[k_] for lo in los]) for k_ in ("RD", "G1", "T1ref", "tok1")}
        zero_tok = {mr["item_id"]: tokens[k] for k, mr in enumerate(meta_rows) if mr["arm"] == "0"}
        chg = {}
        for k, mr in enumerate(meta_rows):
            if mr["arm"] != "0":
                chg.setdefault(mr["arm"], []).append(int(tokens[k, 0] != zero_tok[mr["item_id"]][0]))
        checks = {"resid_ratio_max_prefill": max(resid) if resid else None,
                  "resid_pass": bool(resid and max(resid) < 1e-3),
                  "token1_changed_frac_by_arm": {a_: float(np.mean(v)) for a_, v in chg.items()}}
        meta = {"rows": meta_rows, "kinds": [r["kind"] for r in recs], "seconds": time.time() - t0,
                "max_new_tokens": max_new, "checks": checks, "site": "ALLPOS", "band": band,
                "layers": bands_ext[band], "arms": [["0", 0]] + [list(a) for a in GENG_ARMS],
                "note": "projection-out at every prompt position (prefill) and every decode call in the band's layers; "
                        "own-coefficient random controls; arm-0 rows co-batched",
                "label_source_note": "judged=1 judge/cache, 0.5 PROXY (keyword), 0 NA", "utc": utc_now()}
        logger.info(f"{ctx.m}: {name} generated {len(recs)} rows in {time.time() - t0:.0f}s; {checks}")
        JW.submit(f"{ctx.m}/{name}", functools.partial(finish_judged_cell, ctx.m, name, recs, arrays, meta))


def load_e2x2(smoke: bool) -> list[dict]:
    """D1 safety_2x2 confirmatory cells under the HARMFUL request (hazardous vs benign 144-token continuation)."""
    from common import D1
    d = jload(D1 / "data_out.json")
    ex = next(x for x in d["datasets"] if x["dataset"].endswith("safety_2x2"))["examples"]
    rows = [e for e in ex if e["metadata_request_level"] == "harmful" and e["metadata_confirmatory"] is True
            and e["metadata_qc_fail"] is False and e["metadata_prefix_level"] in ("hazardous", "benign")]
    rows.sort(key=lambda e: (e["metadata_item_uid"], e["metadata_prefix_family"], e["metadata_prefix_level"]))
    return rows[:16] if smoke else rows


E2X2_ARMS = ["F", ("RF", 1), ("RF", 2), "N6", ("RN6", 1)]


def stage_e2x2(ctx: Ctx) -> None:
    """Plan section 6 (site E readout): teacher-forced prompt + 144-token D1 continuation; edit the EARLY window
    (continuation tokens 5-20) in every band, read the projections at the LATE window (tokens 40-55, unedited)."""
    import torch
    from engine import Row, Spec, chunks_by_length
    name = "e2x2_E"
    if have_cell(ctx.m, name):
        return
    rows_d1 = load_e2x2(ctx.smoke)
    e0, e1 = rows_d1[0]["metadata_early_window"]
    l0, l1 = rows_d1[0]["metadata_late_window"]
    prompts = ctx.eng.encode([e["input"] for e in rows_d1])
    conts = ctx.eng.encode([e["output"] for e in rows_d1])
    n_bad = sum(len(c) != 144 for c in conts)
    keep = [k for k, c in enumerate(conts) if len(c) > l1]
    pre_seqs = [prompts[k] + conts[k][:e0] for k in keep]
    span_seqs = [conts[k][e0:e1 + 1] for k in keep]
    tails = [conts[k][e1 + 1:l1 + 1] for k in keep]
    ids = [f"e2x2_{k}" for k in keep]
    D = ctx.tensors()
    ro = ctx.readout()
    bands = list(ctx.bands)
    dev = ctx.eng.device
    groups = chunks_by_length([len(s) for s in pre_seqs], 32)
    acc_proj, acc_meta, t0 = [], [], time.time()
    n_tail_read = l1 - l0 + 1
    for g in groups:
        pre = ctx.eng.prefill_span([ids[i] for i in g], [pre_seqs[i] for i in g], [span_seqs[i] for i in g]).to(dev)
        tail_t = torch.tensor([tails[i] for i in g], dtype=torch.long, device=dev)
        per_item = [[Row(i, "0")] + [r for b in bands for r in arm_rows(i, b, E2X2_ARMS)] for i in range(pre.n)]
        k_per = len(per_item[0])
        s = 0
        while s < pre.n:
            ipp = max(1, max_rows_for(pre.T + pre.S + tail_t.shape[1], ctx.kv_per_tok) // k_per)
            e = min(pre.n, s + ipp)
            rows = [r for i in range(s, e) for r in per_item[i]]
            R = len(rows)
            try:
                with torch.no_grad():
                    spec = ctx.eng.build_spec(rows, D, None, ctx.bands)
                    spec.n_pos = pre.S
                    item_rows = torch.tensor([r.item for r in rows], dtype=torch.long, device=dev)
                    cache = ctx.eng._cache_for(pre, item_rows)
                    attn = torch.cat([pre.mask.index_select(0, item_rows),
                                      torch.ones((R, pre.S), dtype=torch.long, device=dev)], dim=1)
                    pos = pre.span_pos.index_select(0, item_rows)
                    ctx.eng.spec = spec
                    try:
                        out = ctx.eng.model(input_ids=pre.span_tok.index_select(0, item_rows), attention_mask=attn,
                                            position_ids=pos, past_key_values=cache, use_cache=True, logits_to_keep=1)
                    finally:
                        ctx.eng.spec = None
                    past = out.past_key_values
                    del out
                    tail = tail_t.index_select(0, item_rows)
                    T2 = tail.shape[1]
                    attn2 = torch.cat([attn, torch.ones((R, T2), dtype=torch.long, device=dev)], dim=1)
                    pos2 = pos[:, -1:] + 1 + torch.arange(T2, device=dev)[None, :]
                    ro_spec = Spec(readout=ro, proj=torch.zeros((R, ctx.L, 3), device=dev), n_pos=n_tail_read)
                    ctx.eng.spec = ro_spec
                    try:
                        ctx.eng.model(input_ids=tail, attention_mask=attn2, position_ids=pos2, past_key_values=past,
                                      use_cache=True, logits_to_keep=1)
                    finally:
                        ctx.eng.spec = None
            except Exception as ex:  # noqa: BLE001
                if DEVICE == "cuda" and is_oom(ex) and ipp > 1:
                    on_oom(name)
                    continue
                raise
            acc_proj.append(ro_spec.proj.cpu().numpy().astype(np.float32))
            acc_meta += rows_meta(rows, pre.item_ids)
            del spec, ro_spec, cache, past
            s = e
    by_id = {f"e2x2_{k}": rows_d1[k] for k in keep}
    meta_rows = [{**mr, "item_uid": by_id[mr["item_id"]]["metadata_item_uid"],
                  "prefix_level": by_id[mr["item_id"]]["metadata_prefix_level"],
                  "prefix_family": by_id[mr["item_id"]]["metadata_prefix_family"]} for mr in acc_meta]
    save_cell(ctx.m, name, {"proj_late": np.concatenate(acc_proj).astype(np.float16)},
              {"rows": meta_rows, "early_window": [e0, e1], "late_window": [l0, l1], "n_sequences": len(keep),
               "n_cont_not_144_tokens": n_bad, "readout_dirs": ["F", "N6", "FperpU"], "arms": str(E2X2_ARMS),
               "seconds": time.time() - t0, "utc": utc_now(),
               "note": "EARLY window edited (matched displacement, identical teacher-forced inputs across arms); "
                       "proj_late = mean projection over LATE positions (unedited) of every layer"})
    logger.info(f"{ctx.m}: {name} {len(meta_rows)} rows over {len(keep)} sequences in {time.time() - t0:.0f}s")


GSM_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def gsm_correct(resp: str, key: str) -> float:
    nums = GSM_NUM_RE.findall(resp.replace("$", ""))
    if not nums:
        return 0.0
    try:
        v = float(nums[-1].replace(",", "").rstrip("."))
        return float(abs(v - float(str(key).replace(",", ""))) < 1e-6)
    except ValueError:
        return 0.0


def stage_gsm(ctx: Ctx, cells: list[tuple[str, str]]) -> None:
    """GSM8K collateral (16 items, 256 tokens) under arms 0 / F / R_F1 / N6 / R_N6-1 on the listed (site, band) cells."""
    from engine import Row
    if not cells:
        return
    xs = ctx.items["gsm_eval"][: (4 if ctx.smoke else None)]
    pres = None
    D = ctx.tensors()
    for site, band in cells:
        name = f"gsm_{site}_{band}"
        if have_cell(ctx.m, name):
            continue
        if pres is None:
            pres = build_prefixes(ctx, xs, chunk=16, tag="gsm")
        r_arm = "RF" if site == "P" else "RFo"
        rn6_arm = "RN6" if site == "P" else "RN6o"
        arms = [("0", 0), ("F", 0), (r_arm, 1), ("N6", 0), (rn6_arm, 1)]
        meta_rows, toks = [], []
        t0 = time.time()
        for pre in pres:
            rows, sites = [], []
            for i in range(pre.n):
                for (a, j) in arms:
                    rows.append(Row(i, a, None if a == "0" else band, j))
                    sites.append(site)
            res = ctx.eng.site_generate(pre, rows, sites, D, ctx.bands, max_new=(32 if ctx.smoke else GSM_MAX_NEW))
            toks.append(res["tokens"].numpy())
            meta_rows += [{"item_id": pre.item_ids[r.item], "arm": r.arm, "band": r.band, "draw": r.draw, "site": st}
                          for r, st in zip(rows, sites)]
        W_ = max(t.shape[1] for t in toks)
        tokens = np.concatenate([np.pad(t, ((0, 0), (0, W_ - t.shape[1])), constant_values=ctx.eng.pad_id)
                                 for t in toks])
        texts = ctx.eng.decode(ctx.torch.from_numpy(tokens))
        by_id = {x["item_id"]: x for x in xs}
        corr = np.array([gsm_correct(t, by_id[mr["item_id"]]["answer"]) for t, mr in zip(texts, meta_rows)])
        save_cell(ctx.m, name, {"correct": corr, "n_new_tokens": np.array(ctx.eng.n_new_tokens(
            ctx.torch.from_numpy(tokens)))}, {"rows": meta_rows, "site": site, "band": band,
                                              "seconds": time.time() - t0, "max_new_tokens": GSM_MAX_NEW,
                                              "grading": "last number in the response == key (no judge)",
                                              "utc": utc_now()})
        logger.info(f"{ctx.m}: {name} acc by arm " + str({a: float(np.mean([c for c, mr in zip(corr, meta_rows)
                                                                             if mr['arm'] == a])) for a, _ in arms}))


# ---------------------------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------------------------
HOOK_HASH = "unset"


def setup_device(vram_frac: float, kv_gb: float | None = None) -> None:
    global DEVICE
    import torch
    if torch.cuda.is_available():
        DEVICE = "cuda"
        free, total = torch.cuda.mem_get_info()
        torch.cuda.set_per_process_memory_fraction(vram_frac)
        if kv_gb is not None:
            KV_BUDGET["cuda"] = kv_gb * 1e9
        elif free / 1e9 < 14.0:
            KV_BUDGET["cuda"] = 1.5e9
        logger.info(f"CUDA {torch.cuda.get_device_name(0)}: free {free / 1e9:.1f} / {total / 1e9:.1f} GB; "
                    f"per-process cap {vram_frac:.2f}; KV budget {KV_BUDGET['cuda'] / 1e9:.1f} GB")
    else:
        DEVICE = "cpu"
        logger.warning("no CUDA device: CPU fallback F1")


@logger.catch(reraise=True)
def main() -> int:
    global HOOK_HASH, JW
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="instruct,saferl")
    ap.add_argument("--stages", default="unit,twins,decod,arm0,grid1,gen,genP,genDprime,genE,arc,grid2,grid3,"
                                        "stimro,decodgen,spanD,spanE",
                    help="comma list of: unit,twins,decod,arm0,grid1,gen,genP,genDprime,genE,genU,arc,grid2,grid3,"
                         "stimro,decodgen,spanD,spanE,e2x2,genG,gsm")
    ap.add_argument("--gsm-cells", default="", help="comma list of site:band, e.g. P:B3,Dprime:B4")
    ap.add_argument("--smoke", action="store_true", help="T0 smoke test on Qwen/Qwen3-0.6B (bands = sixths of 28)")
    ap.add_argument("--deadline-min", type=float, default=600.0, help="stop starting new cells after this")
    ap.add_argument("--vram-frac", type=float, default=0.55)
    ap.add_argument("--kv-gb", type=float, default=None, help="prefix/KV budget per pass (GB); default by free VRAM")
    a = ap.parse_args()
    setup_logging("method_smoke" if a.smoke else "method")
    setup_device(a.vram_frac, a.kv_gb)
    HOOK_HASH = hook_hash()
    resource.setrlimit(resource.RLIMIT_AS, (int(120e9), int(120e9)))   # guard only (CUDA maps large VA)
    deadline = time.time() + 60 * a.deadline_min
    items = jload(ASSETS / "items.json")
    import torch
    logger.info(f"torch {torch.__version__}, device {DEVICE}, cgroup mem {cgroup_mem_gb()}, hook_hash {HOOK_HASH}")
    JW = JudgeWorker()
    stages = a.stages.split(",")
    gsm_cells = [tuple(c.split(":")) for c in a.gsm_cells.split(",") if c]
    models = ["smoke"] if a.smoke else a.models.split(",")
    try:
        for m in models:
            if a.smoke:
                ctx = Ctx("smoke", "Qwen/Qwen3-0.6B", None, items, smoke=True)
            else:
                repo, tag = ALL_MODELS[m]
                ctx = Ctx(m, repo, tag, items, smoke=False)
            run_log = RESULTS / f"run_status_{ctx.m}.json"
            status = jload(run_log) if run_log.exists() else {}
            status.update(ctx.status)
            if "unit" in stages:
                stage_unit(ctx)
            stage_twins(ctx)                     # always (directions needed by every later stage)
            if "decod" in stages:
                stage_decod(ctx)
            pres = None
            if any(s in stages for s in ("arm0", "grid1")):
                pres = build_prefixes(ctx, eval_items(ctx), chunk=16, tag="eval")
            if "arm0" in stages:
                stage_arm0(ctx, pres)
            if "grid1" in stages:
                stage_grid(ctx, pres, "grid1", deadline)
            pres = None
            if "gen" in stages:
                stage_gen(ctx)
            for site in ("P", "Dprime", "E"):
                if f"gen{site}" in stages:
                    stage_gengrid(ctx, site, deadline)
            if "genU" in stages:
                stage_genU(ctx, deadline)
            if "genG" in stages:
                stage_genG(ctx, deadline)
            if "arc" in stages:
                stage_arc(ctx)
            for g in ("grid2", "grid3"):
                if g in stages:
                    if pres is None:
                        pres = build_prefixes(ctx, eval_items(ctx), chunk=16, tag="eval")
                    stage_grid(ctx, pres, g, deadline)
            pres = None
            if "stimro" in stages:
                stage_stimro(ctx)
            if "decodgen" in stages:
                stage_decodgen(ctx)
            for site in ("D", "E"):
                if f"span{site}" in stages:
                    stage_span(ctx, site, deadline)
            if "e2x2" in stages:
                stage_e2x2(ctx)
            if "gsm" in stages:
                stage_gsm(ctx, gsm_cells)
            status.update({"stages_done_utc": utc_now(), "stages": stages, "hook_hash": HOOK_HASH})
            jdump(run_log, status)
            ctx.eng.free()
            del ctx, pres
            import gc
            gc.collect()
            logger.info(f"model {m} done; judge backlog {JW.backlog()} jobs")
    finally:
        logger.info("waiting for the judge worker to drain ...")
        JW.join()
        if JW.errors:
            logger.error(f"judge worker errors: {JW.errors}")
    logger.info("DONE")
    return 0 if not JW.errors else 3


if __name__ == "__main__":
    sys.exit(main())
