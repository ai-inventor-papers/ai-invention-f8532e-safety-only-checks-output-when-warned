#!/usr/bin/env python3
"""GPU driver for the BLIND held-out safety panel (iteration 5, experiment 2).

THREE subcommands, in the order the artifact runs them:

    pipeline.py gen      --tags T... | --from-sweep N     PHASE A: behaviour first.
    pipeline.py harvest  --tags T... [--tier2] [--tier3]  PHASE C: arrays, AFTER the order gate.
    pipeline.py selftest --tag T                          T3a-T3d / T4 instrument checks.

BLINDNESS CONTRACT.  This module PRODUCES arrays, manifests and timings.  It computes no
correlation, no ranking, no candidate score and no survivor set, and it never reads a
graded outcome other than to answer the yes/no question "was this tag graded and committed
before I harvested it?".  `src/hygiene_check.py lint` enforces the naming half of that
contract over everything written under results/ and arrays/.

ORDER GATE (non-negotiable).  `harvest` refuses any tag that is not listed in a COMMITTED
`results/graded_truth_s*.json` whose sha256 appears in `logs/chain.jsonl`.  Behaviour is
graded before activations are ever looked at, so no array can have steered the grading.

HARDWARE.  The artifact plan assumed a 23,034 MiB L4.  The real device is an NVIDIA
RTX 2000 Ada with 16,380 MiB; the declared budget stays 7.5 GB
(`set_per_process_memory_fraction(7500/16380)`) and every forward is wrapped in an
OOM-halving retry down to batch 1.  `torch.cuda.max_memory_allocated()` is sampled per
stage and recorded, because the run kills a process tree that exceeds its declaration.
"""
from __future__ import annotations

import os

# ---------------------------------------------------------------------------------------
# Environment MUST be set before torch / transformers are imported.
# HF_HOME / HF_HUB_CACHE / TRANSFORMERS_CACHE / HF_DATASETS_CACHE / TORCH_HOME /
# PIP_CACHE_DIR / UV_CACHE_DIR are NEVER touched: they point at the shared run cache
# (deviation `hf_home_left_at_shared_cache`).
# ---------------------------------------------------------------------------------------
_ENV = {
    "TORCH_DISABLE_NATIVE_JIT": "1",
    "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
    "OMP_NUM_THREADS": "4",
    "OPENBLAS_NUM_THREADS": "4",
    "MKL_NUM_THREADS": "4",
    "TOKENIZERS_PARALLELISM": "false",
    "HF_HUB_DISABLE_TELEMETRY": "1",
}
for _k, _v in _ENV.items():
    os.environ[_k] = _v

import argparse  # noqa: E402
import contextlib  # noqa: E402
import fcntl  # noqa: E402
import gc  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Callable, Iterable, Sequence  # noqa: E402

import numpy as np  # noqa: E402
from loguru import logger  # noqa: E402

SRC = Path(__file__).resolve().parent
# SRC must win over vendor/ (both carry a common.py), so force the order.
for _p in (str(SRC / "vendor"), str(SRC)):
    while _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)

from common import (  # noqa: E402
    ARRAYS, ASSETS, LOGS, PRIVATE, RESULTS, SEED, WS, chain_read, deviation, free_gb,
    jdump, jload, setup_logging, sha256_file, sha256_text, utc_now,
)

GENS = PRIVATE / "gens"
TIMING = LOGS / "timing.json"
VRAM_TOTAL_MIB = 16380
VRAM_DECLARED_MIB = 7500          # the ARTIFACT's declaration: the cap on ALL our processes together


def lease_mib_for(bf16_gb: float | None) -> int:
    """VRAM to reserve for ONE visit to a checkpoint of `bf16_gb` weights.

    The artifact declares 7500 MiB TOTAL, and src/lease.py enforces that sum across this
    workspace's processes. Reserving the whole declaration for every visit serialised the
    generation sweep, the harvest sweep and the Part-B runner even though measured peaks are
    far smaller (gemma-3-270m 641 MiB, ERNIE-0.3B 801 MiB, gpt-neo-1.3B 3289 MiB, i.e. about
    1.0-1.25x the bf16 weight bytes). Reserving 1.5x weights + 700 MiB of headroom keeps every
    visit comfortably above its measured peak while letting two or three SMALL visits hold
    leases at once -- strictly inside the same 7500 MiB declaration, which is what the
    declaration governs. Anything at or above the cap simply takes the whole budget and runs
    alone, exactly as before.
    """
    if not bf16_gb or bf16_gb <= 0:
        return VRAM_DECLARED_MIB
    est = int(1.5 * float(bf16_gb) * 1024 + 700)
    return max(1800, min(VRAM_DECLARED_MIB, est))

CFG: dict[str, Any] = {
    "max_len_prompt": 192,
    "max_len_gen": 224,
    "batch_prompt": 16,
    "lens_chunk": 8,
    "dec_new": 8,
    "dec_batch": 1,        # padding-free by construction (T4 padding corruption)
    "n_bands": 6,
    "n_cells_32": 32,
    "topk": 20,
}

SET_MAXNEW = {"HARM": "harm", "OR_XSTEST54": "benign", "HARM_XSTEST54": "benign",
              "OR_HARDBENIGN": "benign"}


# =========================================================================================
# tags, sweep order, small utilities
# =========================================================================================
def tag_of(repo: str) -> str:
    """The ONE tag function.  e.g. HG__tiiuae--Falcon-H1-0.5B-Instruct"""
    return "HG__" + repo.replace("/", "--")


def pb_tag(parent_repo: str, arm: str) -> str:
    """Part-B arm tag: PB__<parent>__<arm>."""
    return f"PB__{parent_repo.replace('/', '--')}__{arm}"


def load_sweep() -> list[dict]:
    p = RESULTS / "sweep_order.json"
    if not p.exists():
        logger.error(f"missing frozen visit order {p}")
        raise SystemExit(3)
    rows = jload(p)["order"]
    for r in rows:
        r["tag"] = tag_of(r["repo"])
    return rows


def sweep_index() -> dict[str, dict]:
    return {r["tag"]: r for r in load_sweep()}


def seeded_rng(*parts: str) -> np.random.Generator:
    h = hashlib.sha256(("|".join((SEED,) + parts)).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def seeded_order(ids: Sequence[str], *parts: str) -> list[str]:
    """Deterministic, tag-free-by-default hashed ordering of an id list."""
    pre = "|".join((SEED,) + parts)
    return sorted(ids, key=lambda i: hashlib.sha256((pre + "|" + i).encode()).hexdigest())


def atomic_npy(path: Path, arr: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp{os.getpid()}")
    with open(tmp, "wb") as f:                 # np.save(path) would append a second ".npy"
        np.save(f, arr, allow_pickle=False)
    os.replace(tmp, path)
    return path


def record_timing(tag: str, stage: str, payload: dict) -> None:
    """Read-modify-write logs/timing.json under an flock; the single most important artifact
    deliverable after working code."""
    LOGS.mkdir(parents=True, exist_ok=True)
    lock = LOGS / "timing.lock"
    lock.touch(exist_ok=True)
    with open(lock, "r+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            data = jload(TIMING) if TIMING.exists() else {"utc": utc_now(), "tags": {}}
            data.setdefault("tags", {}).setdefault(tag, {})[stage] = {**payload, "utc": utc_now()}
            data["utc"] = utc_now()
            jdump(TIMING, data)
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# =========================================================================================
# GPU helpers
# =========================================================================================
def set_memory_fraction(mib: int) -> None:
    """Hold this process to its GRANTED share, so concurrent visits of this artifact cannot
    together exceed the 7500 MiB declaration even if one of them misbehaves."""
    import torch
    try:
        torch.cuda.set_per_process_memory_fraction(min(1.0, mib / VRAM_TOTAL_MIB))
    except (RuntimeError, ValueError) as exc:      # never fail a visit over a cap hint
        logger.warning(f"set_per_process_memory_fraction({mib}) failed: {exc!r}")


def gpu_setup() -> dict:
    import torch
    info: dict[str, Any] = {"cuda": bool(torch.cuda.is_available())}
    if not info["cuda"]:
        logger.error("CUDA not available; this driver is GPU-only")
        raise SystemExit(4)
    torch.cuda.set_per_process_memory_fraction(VRAM_DECLARED_MIB / VRAM_TOTAL_MIB)
    torch.cuda.reset_peak_memory_stats()
    torch.manual_seed(0)
    props = torch.cuda.get_device_properties(0)
    info.update({"device": props.name, "total_mib": int(props.total_memory / 2**20),
                 "declared_mib": VRAM_DECLARED_MIB,
                 "memory_fraction": VRAM_DECLARED_MIB / VRAM_TOTAL_MIB})
    logger.info(f"GPU {info['device']} {info['total_mib']} MiB; declared {VRAM_DECLARED_MIB} MiB")
    return info


def peak_mib() -> float:
    import torch
    return float(torch.cuda.max_memory_allocated() / 2**20) if torch.cuda.is_available() else float("nan")


def reset_peak() -> None:
    import torch
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()


def empty_cache() -> None:
    import torch
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def oom_retry(fn: Callable[[int], Any], batch: int, what: str = "") -> tuple[Any, int]:
    """Run fn(batch); on CUDA OOM halve the batch, empty the cache and retry down to 1."""
    import torch
    b = max(1, int(batch))
    while True:
        try:
            return fn(b), b
        except torch.cuda.OutOfMemoryError:
            empty_cache()
            if b == 1:
                logger.error(f"OOM at batch 1 ({what}) -- giving up")
                raise
            b = max(1, b // 2)
            logger.warning(f"CUDA OOM ({what}) -> batch {b}")
        except RuntimeError as exc:
            if "out of memory" not in str(exc).lower():
                raise
            empty_cache()
            if b == 1:
                raise
            b = max(1, b // 2)
            logger.warning(f"OOM-like RuntimeError ({what}) -> batch {b}")


# =========================================================================================
# model acquisition / loading / teardown
# =========================================================================================
DL_PATTERNS = ["*.json", "*.safetensors", "*.model", "*.txt", "*.jinja", "*.tiktoken",
               "tokenizer*", "*.py"]


def download_snapshot(repo: str, revision: str | None) -> str:
    from huggingface_hub import snapshot_download
    last: Exception | None = None
    for attempt in range(3):
        try:
            return snapshot_download(repo, revision=revision, allow_patterns=DL_PATTERNS)
        except Exception as exc:  # noqa: BLE001
            last = exc
            logger.warning(f"download {repo} attempt {attempt}: {exc!r}"[:300])
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"download failed for {repo}: {last!r}"[:400])


def delete_snapshot(repo: str) -> dict:
    """Delete this repo's HF snapshot from the SHARED cache and report freed bytes."""
    out: dict[str, Any] = {"repo": repo, "freed_bytes": 0, "revisions": 0, "error": None}
    try:
        from huggingface_hub import scan_cache_dir
        cache = scan_cache_dir()
        revs = [rev.commit_hash for r in cache.repos if r.repo_id == repo for rev in r.revisions]
        if revs:
            strat = cache.delete_revisions(*revs)
            out["freed_bytes"] = int(strat.expected_freed_size)
            out["revisions"] = len(revs)
            strat.execute()
    except Exception as exc:  # noqa: BLE001
        out["error"] = repr(exc)[:300]
        logger.warning(f"snapshot delete failed for {repo}: {exc!r}"[:300])
    out["free_gb_after"] = free_gb()
    logger.info(f"snapshot {repo}: {out['revisions']} revision(s) deleted, "
                f"{out['freed_bytes'] / 1e9:.2f} GB freed, {out['free_gb_after']:.0f} GB free")
    return out


def resolve_pad(tok, model) -> str:
    """Pad-token resolution WITHOUT ever adding a token (a new [PAD] would resize the
    embedding matrix and corrupt WU_* rows and weight_sha_full).  With zero-pad buckets and
    left padding + attention mask the pad identity is masked out, so any existing id works.
    Order: tokenizer pad -> tokenizer eos -> model eos id (generation_config, then config;
    first element of a list) -> unk -> bos.  Returns the rule that fired."""
    if tok.pad_token is not None and tok.pad_token_id is not None:
        return "tokenizer_pad_token"
    if tok.eos_token is not None and tok.eos_token_id is not None:
        tok.pad_token = tok.eos_token
        return "tokenizer_eos_token"
    for src_name, src in (("generation_config.eos_token_id", getattr(model, "generation_config", None)),
                          ("config.eos_token_id", getattr(model, "config", None))):
        e = getattr(src, "eos_token_id", None) if src is not None else None
        if isinstance(e, (list, tuple)):
            e = e[0] if e else None
        if e is not None:
            tok.pad_token_id = int(e)
            try:
                tok.pad_token = tok.convert_ids_to_tokens(int(e))
            except Exception:  # noqa: BLE001
                pass
            return f"model_{src_name}"
    for attr in ("unk_token", "bos_token"):
        t = getattr(tok, attr, None)
        if t is not None:
            tok.pad_token = t
            return f"tokenizer_{attr}"
    raise RuntimeError("no usable pad token (refusing to add a new token)")


def load_model(local: str, trust: bool, dtype_name: str = "bfloat16", to_cuda: bool = True,
               attn_impl: str | None = None):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    dt = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[dtype_name]
    tok = AutoTokenizer.from_pretrained(local, trust_remote_code=trust)
    kw: dict[str, Any] = {"dtype": dt, "low_cpu_mem_usage": True, "trust_remote_code": trust}
    if attn_impl:
        kw["attn_implementation"] = attn_impl
    model = AutoModelForCausalLM.from_pretrained(local, **kw)
    model.eval()
    if to_cuda:
        model.to("cuda")
    pad_src = resolve_pad(tok, model)
    return model, tok, {"pad_token_source": pad_src, "pad_token": tok.pad_token,
                        "pad_token_id": tok.pad_token_id, "dtype": str(dt),
                        "trust_remote_code": bool(trust),
                        "attn_implementation": getattr(model.config, "_attn_implementation", attn_impl)}


def load_with_fallback(local: str, want_trust: bool, dtype_name: str = "bfloat16",
                       attn_impl: str | None = None):
    """trust_remote_code is tried as declared, then once the other way (defensive on repos
    whose config needs remote code but whose sweep row says otherwise, and vice versa)."""
    errors: list[dict] = []
    for trust in ([want_trust] if want_trust else [False, True]):
        try:
            return (*load_model(local, trust, dtype_name, attn_impl=attn_impl), errors)
        except Exception as exc:  # noqa: BLE001
            errors.append({"trust_remote_code": trust, "error": repr(exc)[:400]})
            logger.warning(f"load(trust={trust}, attn={attn_impl}) failed: {exc!r}"[:300])
            empty_cache()
    raise RuntimeError(f"model load failed: {errors}")


def acquire_model(repo: str, revision: str | None, want_trust: bool,
                  dtype_name: str = "bfloat16", attn_impl: str | None = None) -> tuple:
    """download + load, called INSIDE the VRAM lease.  The HF cache is SHARED and every
    process of this artifact deletes a repo's snapshot after its visit, so a snapshot that
    was present at download time can vanish before the load; one forced re-download covers
    that race.  Returns (model, tok, load_info, load_errors, t_download_s, t_load_s)."""
    t0 = time.time()
    local = download_snapshot(repo, revision)
    t_dl = time.time() - t0
    t0 = time.time()
    try:
        model, tok, info, errs = load_with_fallback(local, want_trust, dtype_name, attn_impl)
    except RuntimeError as exc:
        logger.warning(f"load after download failed ({exc!r}"[:200] + ") -> forced re-download")
        t1 = time.time()
        from huggingface_hub import snapshot_download
        local = snapshot_download(repo, revision=revision, allow_patterns=DL_PATTERNS,
                                  force_download=True)
        t_dl += time.time() - t1
        model, tok, info, errs = load_with_fallback(local, want_trust, dtype_name, attn_impl)
        errs = [{"note": "first load failed; recovered by forced re-download",
                 "error": repr(exc)[:300]}] + errs
    info["local_snapshot"] = local
    return model, tok, info, errs, t_dl, time.time() - t0


def unload(model) -> None:
    try:
        model.to("cpu")
    except Exception:  # noqa: BLE001
        pass
    del model
    empty_cache()


def get_layers(model):
    """The decoder-block ModuleList, across the architectures on the panel."""
    for path in ("model.layers", "model.decoder.layers", "transformer.h", "transformer.blocks",
                 "gpt_neox.layers", "model.transformer.h", "layers", "model.model.layers"):
        obj = model
        ok = True
        for part in path.split("."):
            obj = getattr(obj, part, None)
            if obj is None:
                ok = False
                break
        if ok and hasattr(obj, "__len__") and len(obj) > 0:
            return obj
    raise RuntimeError(f"cannot locate decoder blocks on {type(model).__name__}")


def resolve_depth(model) -> int:
    """True depth from the LOADED model.  sweep_order.n_layers is null for
    EleutherAI/gpt-neo-1.3B (its config uses `num_layers`), so this never trusts that field."""
    cfg = model.config
    for k in ("num_hidden_layers", "n_layer", "num_layers", "n_layers", "depth"):
        v = getattr(cfg, k, None)
        if isinstance(v, int) and v > 0:
            n = v
            break
    else:
        n = None
    try:
        n_mod = len(get_layers(model))
    except RuntimeError:
        n_mod = None
    if n_mod:
        if n and n != n_mod:
            logger.warning(f"config depth {n} != module depth {n_mod}; using module depth")
        return int(n_mod)
    if n:
        return int(n)
    raise RuntimeError("cannot resolve model depth")


def lens_parts(model):
    """(W_U, final_norm_module), handling tied embeddings.  Verbatim semantics of the
    iteration-2/4 harvest kernel so the r_* arrays stay comparable."""
    head = getattr(model, "lm_head", None)
    if head is not None and getattr(head, "weight", None) is not None:
        w_u = head.weight
    else:
        w_u = model.get_input_embeddings().weight
    inner = getattr(model, "model", model)
    fn = (getattr(inner, "norm", None) or getattr(inner, "final_layernorm", None)
          or getattr(inner, "ln_f", None) or getattr(getattr(inner, "transformer", inner), "ln_f", None))
    return w_u, fn


def weight_fingerprints(model) -> tuple[str, str]:
    """(6-tensor fingerprint, full weight sha).  Both over CPU bytes in sorted key order."""
    import torch
    sd = model.state_dict()
    keys = sorted(sd.keys())
    if not keys:
        return "", ""
    idx = [int(round(i * (len(keys) - 1) / 5)) for i in range(6)] if len(keys) >= 6 else list(range(len(keys)))
    h6 = hashlib.sha256()
    for i in sorted(set(idx)):
        k = keys[i]
        with torch.no_grad():
            h6.update(k.encode())
            h6.update(sd[k].detach().to("cpu", torch.float32).contiguous().numpy().tobytes())
    hfull = hashlib.sha256()
    with torch.no_grad():
        for k in keys:
            hfull.update(k.encode())
            hfull.update(sd[k].detach().to("cpu").contiguous().view(torch.uint8).numpy().tobytes()
                         if sd[k].dtype not in (torch.bool,) else sd[k].detach().cpu().numpy().tobytes())
    return h6.hexdigest(), hfull.hexdigest()


# =========================================================================================
# rendering + encoding (LEFT padding everywhere, explicit position_ids)
# =========================================================================================
def render_one(tok, text: str, system: str | None = None) -> tuple[str, str, bool]:
    """(rendered, render_format, add_special_tokens).

    Chat template when the tokenizer carries one, PLAIN COMPLETION otherwise (base arms).
    """
    tmpl = getattr(tok, "chat_template", None)
    if not tmpl:
        return (((system + "\n\n") if system else "") + text + "\n", "plain_completion", True)
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": text}]
    for kw in (dict(add_generation_prompt=True, enable_thinking=False, tokenize=False),
               dict(add_generation_prompt=True, tokenize=False)):
        try:
            return (tok.apply_chat_template(msgs, **kw), "chat_template", False)
        except Exception:  # noqa: BLE001
            continue
    logger.warning("chat template present but unusable; falling back to plain completion")
    return (((system + "\n\n") if system else "") + text + "\n", "plain_completion_fallback", True)


def encode_left(tok, texts: Sequence[str], max_len: int, add_special_tokens: bool):
    """LEFT padding with the tokenizer's own pad token, so position -1 is always the last
    real token.  Returns (ids, attn, position_ids) on cuda."""
    import torch
    prev = tok.padding_side
    tok.padding_side = "left"
    try:
        enc = tok(list(texts), return_tensors="pt", padding=True, truncation=True,
                  max_length=max_len, add_special_tokens=add_special_tokens)
    finally:
        tok.padding_side = prev
    ids = enc["input_ids"].to("cuda")
    attn = enc["attention_mask"].to("cuda")
    pos = attn.long().cumsum(-1) - 1
    pos = pos.masked_fill(attn == 0, 1)
    return ids, attn, pos


def model_forward(model, ids, attn, pos, *, hidden: bool, keep_last_logit: bool = True):
    """Forward with position_ids where the architecture accepts them (hybrids such as
    falcon_h1 / zamba2 may not), hidden states optional."""
    import torch
    kw: dict[str, Any] = {"input_ids": ids, "attention_mask": attn, "use_cache": False,
                          "output_hidden_states": bool(hidden)}
    with torch.no_grad():
        try:
            return model(**kw, position_ids=pos)
        except TypeError:
            return model(**kw)


# =========================================================================================
# generation
# =========================================================================================
def eos_ids(model, tok) -> set[int]:
    e = getattr(getattr(model, "generation_config", None), "eos_token_id", None)
    if e is None:
        e = tok.eos_token_id
    return {int(x) for x in (e if isinstance(e, (list, tuple)) else [e]) if x is not None}


def logits_processor_overrides(model) -> list[str]:
    """Explicit precondition check for greedy_shrink: ANY logits processor in the repo's
    generation_config makes argmax decoding differ from model.generate."""
    gc_ = getattr(model, "generation_config", None)
    if gc_ is None:
        return []
    bad: list[str] = []
    if (getattr(gc_, "repetition_penalty", 1.0) or 1.0) != 1.0:
        bad.append(f"repetition_penalty={gc_.repetition_penalty}")
    if getattr(gc_, "no_repeat_ngram_size", 0):
        bad.append(f"no_repeat_ngram_size={gc_.no_repeat_ngram_size}")
    for attr in ("bad_words_ids", "suppress_tokens", "begin_suppress_tokens",
                 "forced_decoder_ids", "sequence_bias", "exponential_decay_length_penalty"):
        if getattr(gc_, attr, None):
            bad.append(attr)
    if getattr(gc_, "do_sample", False):
        bad.append("do_sample=True")
    for attr in ("temperature", "top_p", "top_k", "typical_p", "min_p", "epsilon_cutoff", "eta_cutoff"):
        v = getattr(gc_, attr, None)
        if v is None:
            continue
        default = {"temperature": 1.0, "top_p": 1.0, "top_k": 0, "typical_p": 1.0,
                   "min_p": None, "epsilon_cutoff": 0.0, "eta_cutoff": 0.0}[attr]
        if attr == "top_k" and v in (0, 50):      # 50 is the HF default, inert under do_sample=False
            continue
        if default is not None and v != default:
            bad.append(f"{attr}={v}")
        elif default is None and v:
            bad.append(f"{attr}={v}")
    if getattr(gc_, "min_new_tokens", 0):
        bad.append(f"min_new_tokens={gc_.min_new_tokens}")
    return bad


def greedy_shrink(model, enc: dict, max_new: int, eos: set[int], pad_id: int):
    """Greedy decoding (pure argmax, no logits processors) with EOS rows dropped from the
    batch AND its KV cache.  Semantics copied from P/src/gen.py; falls back to keeping the
    full batch when the Cache class has no batch_select_indices."""
    import torch
    ids, attn = enc["input_ids"], enc["attention_mask"]
    b0 = ids.shape[0]
    pos = attn.long().cumsum(-1) - 1
    pos = pos.masked_fill(attn == 0, 1)
    with torch.no_grad():
        try:
            out = model(input_ids=ids, attention_mask=attn, position_ids=pos,
                        use_cache=True, logits_to_keep=1)
        except TypeError:
            out = model(input_ids=ids, attention_mask=attn, use_cache=True)
        past = out.past_key_values
        nxt = out.logits[:, -1, :].argmax(-1)
        active = torch.arange(b0, device=ids.device)
        res = torch.full((b0, max_new), pad_id, dtype=torch.long, device=ids.device)
        cur_attn, cur_pos = attn, pos[:, -1]
        steps = 0
        for step in range(max_new):
            res[active, step] = nxt
            steps = step + 1
            done = torch.tensor([int(t) in eos for t in nxt.tolist()],
                                dtype=torch.bool, device=ids.device)
            if step == max_new - 1 or bool(done.all()):
                break
            if bool(done.any()) and hasattr(past, "batch_select_indices"):
                keep = (~done).nonzero().squeeze(1)
                past.batch_select_indices(keep)
                active, nxt = active[keep], nxt[keep]
                cur_attn, cur_pos = cur_attn[keep], cur_pos[keep]
            cur_attn = torch.cat(
                [cur_attn, torch.ones((cur_attn.shape[0], 1), dtype=cur_attn.dtype,
                                      device=cur_attn.device)], dim=1)
            cur_pos = cur_pos + 1
            try:
                out = model(input_ids=nxt[:, None], attention_mask=cur_attn,
                            position_ids=cur_pos[:, None], past_key_values=past,
                            use_cache=True, logits_to_keep=1)
            except TypeError:
                out = model(input_ids=nxt[:, None], attention_mask=cur_attn,
                            past_key_values=past, use_cache=True)
            past = out.past_key_values
            nxt = out.logits[:, -1, :].argmax(-1)
    return res, steps


def token_lengths(tok, texts: Sequence[str], max_len: int, add_special: bool) -> list[int]:
    return [min(len(tok(t, add_special_tokens=add_special)["input_ids"]), max_len) for t in texts]


def zero_pad_buckets(tok, texts: Sequence[str], max_len: int, add_special: bool,
                     batch: int) -> list[list[int]]:
    """Index groups whose (truncated) token lengths are IDENTICAL, so a batch built from one
    group contains ZERO pad tokens.  bf16 forwards over padded batches were measured to move
    last-token states by 10-290% relative (gemma-3, pythia) while exact-length buckets
    reproduce batch 1 exactly; every forward-only pass of this driver therefore uses these."""
    groups: dict[int, list[int]] = {}
    for i, n in enumerate(token_lengths(tok, texts, max_len, add_special)):
        groups.setdefault(n, []).append(i)
    out: list[list[int]] = []
    for n in sorted(groups):
        idx = groups[n]
        for s in range(0, len(idx), max(1, batch)):
            out.append(idx[s:s + batch])
    return out


def run_bucketed(tok, texts: Sequence[str], max_len: int, add_special: bool, batch: int,
                 fn: Callable[[list[str]], dict], what: str) -> dict[str, np.ndarray]:
    """Apply fn(sub_texts) -> {name: array with leading dim len(sub)} over zero-pad buckets,
    OOM-halving within a bucket, results scattered back to the ORIGINAL row order."""
    out: dict[str, np.ndarray] = {}
    for bidx in zero_pad_buckets(tok, texts, max_len, add_special, batch):
        pos = 0
        while pos < len(bidx):
            rest = bidx[pos:]
            res, used = oom_retry(lambda bs, _r=rest: fn([texts[j] for j in _r[:bs]]),
                                  len(rest), what=what)
            take = rest[:used]
            for k, v in res.items():
                if v is None:
                    continue
                if k not in out:
                    out[k] = np.zeros((len(texts),) + tuple(v.shape[1:]), dtype=v.dtype)
                out[k][take] = v[:len(take)]
            pos += len(take)
    return out


def assert_no_pad(attn) -> None:
    if not bool(attn.bool().all()):
        raise RuntimeError("zero-pad invariant violated: a bucket contains pad tokens")


def generate_batch(model, tok, texts: Sequence[str], add_special: bool, max_new: int,
                   batch: int, use_shrink: bool,
                   batching: str = "padded") -> tuple[list[list[int]], float]:
    """Greedy generation.  batching='padded' = left-padded contiguous chunks (only used when
    the per-tag padding guard passed); 'zero_pad_buckets' = exact-length groups, no pad at
    all; 'batch1' = one prompt at a time.  Returns (new token ids in input order, seconds)."""
    import torch
    eos = eos_ids(model, tok)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else (tok.eos_token_id or 0)
    t0 = time.time()
    prev_side = tok.padding_side
    tok.padding_side = "left"

    def _gen(sub: list[str]) -> list[list[int]]:
        enc = tok(sub, return_tensors="pt", padding=True, truncation=True,
                  max_length=CFG["max_len_gen"], add_special_tokens=add_special)
        enc = {k: v.to("cuda") for k, v in enc.items() if k in ("input_ids", "attention_mask")}
        p_len = enc["input_ids"].shape[1]
        if use_shrink:
            newtok, _ = greedy_shrink(model, enc, max_new, eos, pad_id)
        else:
            with torch.no_grad():
                gen = model.generate(**enc, max_new_tokens=max_new, do_sample=False,
                                     pad_token_id=pad_id, repetition_penalty=1.0,
                                     no_repeat_ngram_size=0, temperature=None,
                                     top_p=None, top_k=None, min_new_tokens=0)
            newtok = gen[:, p_len:]
        return newtok.detach().cpu().tolist()

    out: list[list[int] | None] = [None] * len(texts)
    try:
        if batching == "padded":
            groups = [list(range(i, min(i + batch, len(texts)))) for i in range(0, len(texts), max(1, batch))]
        elif batching == "zero_pad_buckets":
            groups = zero_pad_buckets(tok, texts, CFG["max_len_gen"], add_special, batch)
        elif batching == "batch1":
            groups = [[i] for i in range(len(texts))]
        else:
            raise ValueError(batching)
        done = 0
        for g in groups:
            pos = 0
            while pos < len(g):
                rest = g[pos:]
                rows, used = oom_retry(lambda bs, _r=rest: _gen([texts[j] for j in _r[:bs]]),
                                       len(rest), what=f"generate({batching})")
                for j, r in zip(rest[:used], rows):
                    out[j] = r
                pos += used
            done += len(g)
        logger.info(f"    gen {done}/{len(texts)} ({time.time() - t0:.0f}s, {batching}, {len(groups)} groups)")
    finally:
        tok.padding_side = prev_side
    return [r or [] for r in out], time.time() - t0


GUARD_ROWS_REQUIRED = 7          # of 8: one row of slack for a legitimate bf16 near-tie flip


def guard_prompts(tok) -> tuple[list[str], bool, dict]:
    """8 FIXED prompts of deliberately varied length from cells_32 (tag-free hashed subset):
    the 32 rows sorted by character length, every 4th taken."""
    stim = jload(ASSETS / "stimuli.json")["rows"]
    rows = sorted(cells_32(stim)["rows"], key=lambda r: (len(r["text"]), r["stim_id"]))
    pick = [rows[i] for i in range(0, 32, 4)][:8]
    rendered = [render_one(tok, r["text"]) for r in pick]
    ids = [r["stim_id"] for r in pick]
    return ([x[0] for x in rendered], rendered[0][2],
            {"stim_ids": ids, "prompts_sha256": sha256_text("\n".join(ids))})


def guard_test(model, tok, texts: list[str], add_special: bool, use_shrink: bool,
               batching: str, batch: int = 8, max_new: int = 16) -> int:
    """Rows (of len(texts)) whose greedy continuation under `batching` is token-identical
    to the batch-1 continuation."""
    eos = eos_ids(model, tok)
    a, _ = generate_batch(model, tok, texts, add_special, max_new, batch, use_shrink, batching)
    b, _ = generate_batch(model, tok, texts, add_special, max_new, 1, use_shrink, "batch1")
    return sum(int(trim_to_eos(x, eos) == trim_to_eos(y, eos)) for x, y in zip(a, b))


def padding_guard(model, tok, local: str, trust: bool, use_shrink: bool) -> tuple[Any, Any, dict]:
    """PER-TAG runtime guard, run right after load and before any sweep item:
      1. padded batch-8 vs batch-1 at the native attention implementation;
      2. on failure reload with attn_implementation='eager' and re-test padded;
      3. on failure test exact-length zero-pad buckets;
      4. on failure use batch 1.
    Returns (model, tok, record); the model may have been reloaded."""
    texts, add_special, pinfo = guard_prompts(tok)
    native = getattr(model.config, "_attn_implementation", None)
    rec: dict[str, Any] = {"prompts_sha256": pinfo["prompts_sha256"], "stim_ids": pinfo["stim_ids"],
                           "n_rows": len(texts), "rows_required": GUARD_ROWS_REQUIRED,
                           "decoder": "greedy_shrink" if use_shrink else "hf_generate",
                           "native_attn_implementation": native, "trials": []}
    n = guard_test(model, tok, texts, add_special, use_shrink, "padded")
    rec["rows_identical_first_try"] = n
    rec["trials"].append({"config": f"padded_{native}", "rows_identical": n})
    if n >= GUARD_ROWS_REQUIRED:
        rec.update(config_chosen="padded", attn_implementation=native, rows_identical_final=n)
        return model, tok, rec
    if native != "eager":
        try:
            unload(model)
            model, tok, _info = load_model(local, trust, attn_impl="eager")
            n = guard_test(model, tok, texts, add_special, use_shrink, "padded")
            rec["trials"].append({"config": "padded_eager", "rows_identical": n})
            if n >= GUARD_ROWS_REQUIRED:
                rec.update(config_chosen="padded", attn_implementation="eager", rows_identical_final=n)
                return model, tok, rec
        except Exception as exc:  # noqa: BLE001
            rec["trials"].append({"config": "padded_eager", "error": repr(exc)[:300]})
            empty_cache()
            model, tok, _info = load_model(local, trust, attn_impl=native)
    cur = getattr(model.config, "_attn_implementation", None)
    # Zero-pad buckets contain NO pad token, so the masking bug this guard exists to catch
    # cannot occur in them. Any residual disagreement with batch 1 is ordinary bf16 GEMM
    # nondeterminism across batch shapes -- both are valid greedy decodes -- so buckets are
    # ACCEPTED here whatever their agreement, which is recorded as a diagnostic, not a gate.
    # (Requiring 7/8 here sent pythia-410m to batch 1 at ~5x the cost for no correctness gain.)
    try:
        n = guard_test(model, tok, texts, add_special, use_shrink, "zero_pad_buckets")
    except Exception as exc:  # noqa: BLE001 -- only an execution failure demotes to batch 1
        rec["trials"].append({"config": f"zero_pad_buckets_{cur}", "error": repr(exc)[:300]})
        rec.update(config_chosen="batch1", attn_implementation=cur, rows_identical_final=len(texts))
        return model, tok, rec
    rec["trials"].append({"config": f"zero_pad_buckets_{cur}", "rows_identical": n,
                          "role": "diagnostic (no pad tokens, so no masking bug is possible)"})
    rec.update(config_chosen="zero_pad_buckets", attn_implementation=cur, rows_identical_final=n,
               bucket_agreement_with_batch1=n)
    return model, tok, rec


def trim_to_eos(ids: list[int], eos: set[int]) -> list[int]:
    out: list[int] = []
    for t in ids:
        out.append(int(t))
        if int(t) in eos:
            break
    return out


# =========================================================================================
# item sets
# =========================================================================================
def load_item_sets(path: Path | None = None) -> dict:
    p = Path(path) if path else (RESULTS / "item_sets.json")
    if not p.exists():
        logger.error(
            f"{p} is absent.  It is written concurrently by the items_build agent; this "
            f"driver never invents items.  Re-run `gen` once that file exists.")
        raise SystemExit(5)
    d = jload(p)
    if "sets" not in d:
        logger.error(f"{p} has no 'sets' key -- schema mismatch, refusing to guess")
        raise SystemExit(5)
    return d


def gen_rows_for(item_sets: dict, limit: int | None) -> list[dict]:
    rows: list[dict] = []
    for set_name in ("HARM", "OR_XSTEST54", "HARM_XSTEST54", "OR_HARDBENIGN"):
        blk = item_sets["sets"].get(set_name)
        if not blk:
            logger.warning(f"item_sets.json has no set {set_name}; skipping it")
            continue
        items = blk["items"][:limit] if limit else blk["items"]
        for it in items:
            rows.append({"item_id": it["id"], "set_name": set_name, "request": it["request"],
                         "kind": it.get("kind"), "source_table": it.get("source_table")})
    return rows


# =========================================================================================
# PHASE A -- generation
# =========================================================================================
def gen_one(row: dict, item_sets: dict, args: argparse.Namespace) -> dict:
    from lease import vram_lease
    tag, repo = row["tag"], row["repo"]
    out_jsonl = GENS / f"{tag}.jsonl"
    done_marker = GENS / f"{tag}.GEN_DONE"
    if done_marker.exists():
        logger.info(f"{tag}: GEN_DONE present -> skip")
        return {"tag": tag, "skipped": True}
    GENS.mkdir(parents=True, exist_ok=True)
    items = gen_rows_for(item_sets, args.limit_items or args.smoke)
    t_all = time.time()
    reset_peak()
    timings: dict[str, Any] = {"repo": repo, "n_items": len(items)}
    lease_mib = lease_mib_for(row.get("bf16_gb"))
    timings["lease_mib"] = lease_mib
    with vram_lease(mib=lease_mib, artifact=f"exp2_gen_{tag}") as grant:
        set_memory_fraction(lease_mib)
        model, tok, load_info, load_errs, t_dl, t_load = acquire_model(
            repo, row.get("revision_sha"), bool(row.get("trust_remote_code")))
        timings["t_download_s"] = t_dl
        try:
            lp = logits_processor_overrides(model)
            use_shrink = not lp
            batch = max(1, (args.batch // 2) if grant.get("half_batch") else args.batch)
            # The chunk files are named by INDEX for the CURRENT chunk size, so resuming a tag
            # after the batch size changed made a new 48-item chunk 0000 collide with an old
            # 16-item one, skipping items (one tag ended with 112 of 236 rows). The layout is
            # therefore part of the directory name, and this must sit AFTER `batch` is known.
            part_dir = GENS / f"{tag}.partial.b{batch}"
            for other in GENS.glob(f"{tag}.partial*"):
                if other.is_dir() and other != part_dir:
                    shutil.rmtree(other, ignore_errors=True)
            part_dir.mkdir(parents=True, exist_ok=True)
            for stale in part_dir.glob("*.lock"):
                stale.unlink(missing_ok=True)
            # PER-TAG PADDING GUARD (T4 found left-padded batched generation corrupts some
            # architectures: gemma-3 0/8 rows identical vs batch 1). Every tag self-certifies
            # its batching before any sweep item: padded@native -> padded@eager ->
            # zero-pad length buckets -> batch 1. The model may be reloaded (eager).
            t_guard = time.time()
            model, tok, guard = padding_guard(model, tok, load_info["local_snapshot"],
                                              bool(row.get("trust_remote_code")), use_shrink)
            guard["t_guard_s"] = time.time() - t_guard
            batching = guard["config_chosen"]
            timings["padding_guard"] = guard
            logger.info(f"  {tag}: padding guard -> {batching} "
                        f"(attn={guard.get('attn_implementation')}, "
                        f"{guard.get('rows_identical_final')}/{guard.get('n_rows')} rows identical; "
                        f"first try {guard.get('rows_identical_first_try')})")
            eos = eos_ids(model, tok)
            chunks: list[list[dict]] = [items[i:i + batch] for i in range(0, len(items), batch)]
            written = 0
            t_gen = 0.0
            n_new_total = 0
            for ci, chunk in enumerate(chunks):
                cp = part_dir / f"{ci:04d}.json"
                if cp.exists():
                    try:
                        written += len(jload(cp))
                        continue
                    except (json.JSONDecodeError, OSError):
                        cp.unlink(missing_ok=True)
                by_budget: dict[str, list[dict]] = {"harm": [], "benign": []}
                for it in chunk:
                    by_budget[SET_MAXNEW[it["set_name"]]].append(it)
                recs: list[dict] = []
                for budget, group in by_budget.items():
                    if not group:
                        continue
                    max_new = args.max_new_harm if budget == "harm" else args.max_new_benign
                    rendered = [render_one(tok, it["request"]) for it in group]
                    texts = [r[0] for r in rendered]
                    add_special = rendered[0][2]
                    new_ids, dt = generate_batch(model, tok, texts, add_special, max_new,
                                                 batch, use_shrink, batching)
                    t_gen += dt
                    for it, (rtext, rfmt, _), nid in zip(group, rendered, new_ids):
                        kept = trim_to_eos(nid, eos)
                        n_new_total += len(kept)
                        recs.append({
                            "item_id": it["item_id"], "set_name": it["set_name"],
                            "request": it["request"], "rendered": rtext, "render_format": rfmt,
                            "completion": tok.decode(kept, skip_special_tokens=True).strip(),
                            "n_new": len(kept), "tag": tag, "repo": repo,
                            "revision_sha": row.get("revision_sha"), "utc": utc_now(),
                            "gen_batching": batching,
                            "gen_attn_implementation": guard.get("attn_implementation")})
                jdump(cp, recs)
                written += len(recs)
                logger.info(f"  {tag}: chunk {ci + 1}/{len(chunks)} ({written}/{len(items)} items)")
            rows_out: list[dict] = []
            for cp in sorted(part_dir.glob("*.json")):
                rows_out.extend(jload(cp))
            tmp = out_jsonl.with_suffix(f".jsonl.tmp{os.getpid()}")
            with open(tmp, "w") as f:
                for r in rows_out:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
            os.replace(tmp, out_jsonl)
            timings.update({
                "t_load_s": t_load, "t_gen_s": t_gen, "n_rows": len(rows_out),
                "n_new_tokens": n_new_total,
                "sec_per_item": t_gen / max(len(rows_out), 1),
                "tok_per_s": n_new_total / max(t_gen, 1e-9),
                "decoder": "greedy_shrink" if use_shrink else "hf_generate",
                "logits_processor_overrides": lp, "batch": batch,
                "n_params": int(sum(p.numel() for p in model.parameters())),
                "model_type": getattr(model.config, "model_type", None),
                "load_info": load_info, "load_failed_attempts": load_errs,
                "lease_granted": bool(grant.get("granted")),
                "max_memory_allocated_mib": peak_mib(),
                "render_format_example": rows_out[0]["render_format"] if rows_out else None,
            })
        finally:
            unload(model)
            # deleted INSIDE the lease: no other lease holder can be mid-load on it
            timings["snapshot_delete"] = delete_snapshot(repo)
    timings["t_total_s"] = time.time() - t_all
    free = free_gb()
    if free < 5:
        deviation("low_disk_after_snapshot_delete", f"{free:.1f} GB free after {tag}", "gen")
    timings["free_gb_after"] = free
    n_exp = sum(len(v.get("items", [])) for v in item_sets.get("sets", {}).values()) \
        if not (args.limit_items or args.smoke) else None
    if n_exp and len(rows_out) != n_exp:
        raise RuntimeError(f"{tag}: wrote {len(rows_out)} rows, expected {n_exp} -- refusing to "
                           f"mark GEN_DONE on an incomplete generation")
    done_marker.write_text(utc_now())
    shutil.rmtree(part_dir, ignore_errors=True)
    record_timing(tag, "gen", timings)
    logger.info(f"GEN DONE {tag}: dl {t_dl:.0f}s, load {timings['t_load_s']:.0f}s, "
                f"gen {timings['t_gen_s']:.0f}s ({timings['sec_per_item']:.2f} s/item), "
                f"peak {timings['max_memory_allocated_mib']:.0f} MiB")
    return timings


def cmd_gen(args: argparse.Namespace) -> int:
    gpu_setup()
    item_sets = load_item_sets(Path(args.item_sets) if args.item_sets else None)
    idx = sweep_index()
    if args.tags:
        rows = []
        for t in args.tags:
            if t not in idx:
                logger.error(f"unknown tag {t} (not in results/sweep_order.json)")
                return 3
            rows.append(idx[t])
    else:
        allrows = load_sweep()
        pend = [r for r in allrows if not (GENS / f"{r['tag']}.GEN_DONE").exists()]
        rows = pend[:args.from_sweep] if args.from_sweep else pend
    logger.info(f"gen: {len(rows)} tag(s)")
    failures: list[dict] = []
    for r in rows:
        try:
            gen_one(r, item_sets, args)
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"gen failed for {r['tag']}")
            failures.append({"tag": r["tag"], "error": repr(exc)[:400]})
            deviation("gen_failed", f"{r['tag']}: {exc!r}"[:300], "gen")
            empty_cache()
    if failures:
        jdump(RESULTS / "gen_failures.json", {"utc": utc_now(), "failures": failures})
    return 0 if not failures else 1


# =========================================================================================
# ORDER GATE
# =========================================================================================
def _local_order_gate_ok(tag: str) -> bool:
    """A tag may be harvested only if it appears in a graded_truth_s*.json whose CURRENT
    sha256 equals the sha256 recorded for it in logs/chain.jsonl."""
    chain_sha = {}
    for rec in chain_read():
        pp = str(rec.get("payload_path") or "")
        if "graded_truth_s" in pp:
            chain_sha[pp] = rec.get("payload_sha256")
    for pp, sha in chain_sha.items():
        if Path(pp).name == "graded_truth_s0.json":
            # chain record 3 is a NON-AUTHORITATIVE acceptance-smoke stub (retracted in the
            # chain); real staged commits start at s1, so s0 can never open the gate.
            continue
        f = WS / pp
        if not f.exists():
            logger.warning(f"order gate: chained {pp} is missing on disk")
            continue
        if sha256_file(f) != sha:
            logger.warning(f"order gate: {pp} sha256 drifted from its chain record -- ignored")
            continue
        try:
            gt = jload(f)
        except (json.JSONDecodeError, OSError):
            continue
        tags = {str(r.get("tag")) for r in gt.get("per_ckpt", []) if r.get("tag")}
        if tag in tags:
            logger.info(f"order gate PASS: {tag} committed in {pp}")
            return True
    return False


def order_gate_ok(tag: str) -> bool:
    """Prefer judgeflow's implementation when that module exposes one; identical semantics."""
    try:
        import judgeflow  # type: ignore
        fn = getattr(judgeflow, "order_gate_ok", None)
        if callable(fn):
            return bool(fn(tag))
    except Exception:  # noqa: BLE001
        pass
    return _local_order_gate_ok(tag)


# =========================================================================================
# PHASE C -- harvest kernels
# =========================================================================================
def encode_token_sets(tok, token_sets: dict) -> dict[str, list[int]]:
    """Resolve the surface forms PER TOKENIZER.  NEVER padded: the kept count is the truth."""
    out: dict[str, list[int]] = {}
    for key in ("refusal", "hedge", "control"):
        ids: list[int] = []
        for s in token_sets.get(key, []):
            enc = tok(s, add_special_tokens=False)["input_ids"]
            if enc:
                ids.append(int(enc[0]))
        out[key] = sorted(set(ids))
    return out


def logit_lens_drives(stack, w_u, final_norm, sets: dict, chunk: int) -> dict[str, np.ndarray]:
    """Per-layer logit-lens drive per token set as a LOG-SUM-EXP over that set only, plus
    the true full-vocab denominator at the FINAL layer (iteration-2/4 convention: every
    downstream use is a difference between two sets at the same layer, so the denominator
    cancels; it is stored at the last layer so a normalised form stays available)."""
    import torch
    b, l1, _ = stack.shape
    out = {k: np.zeros((b, l1), dtype=np.float32) for k in sets}
    out["fullV_final"] = np.zeros((b, l1), dtype=np.float32)
    with torch.no_grad():
        rows = {k: w_u.detach().index_select(0, ids.to(w_u.device)).float() for k, ids in sets.items()}
        for l in range(l1):
            h = stack[:, l, :]
            if final_norm is not None:
                try:
                    h = final_norm(h.to(w_u.dtype)).float()
                except Exception:  # noqa: BLE001
                    pass
            for k, rmat in rows.items():
                out[k][:, l] = torch.logsumexp(h @ rmat.T, dim=-1).float().cpu().numpy()
            if l == l1 - 1:
                wf = w_u.detach().float()
                for s in range(0, b, chunk):
                    z = h[s:s + chunk] @ wf.T
                    out["fullV_final"][s:s + chunk, l] = torch.logsumexp(z, dim=-1).float().cpu().numpy()
                    del z
    return out


def p_harvest(model, tok, texts: Sequence[str], *, max_len: int, batch: int,
              token_ids: dict[str, list[int]], add_special: bool,
              lens_chunk: int = 8) -> dict[str, np.ndarray]:
    """Last-prompt-token hidden states at every layer + per-layer logit-lens drives.

    LEFT padding with explicit position_ids (so index -1 is always the last real token) --
    a deliberate departure from the iteration-2 right-padded kernel, recorded in meta.json
    as `pad_side`, because several panel families use absolute position embeddings and the
    generation pass is left-padded too.
    """
    import torch
    n = len(texts)
    order = np.argsort([len(t) for t in texts], kind="mergesort")   # length-sorted batching
    w_u, final_norm = lens_parts(model)
    sets = {k: torch.tensor(v, dtype=torch.long) for k, v in token_ids.items() if v}
    a_out: np.ndarray | None = None
    nrm_out: np.ndarray | None = None
    r_out: dict[str, np.ndarray] = {}
    i = 0
    b = max(1, batch)
    while i < n:
        idx = order[i:i + b]

        def _run(bs: int, _idx=idx):
            sub = [texts[j] for j in _idx[:bs]]
            ids, attn, pos = encode_left(tok, sub, max_len, add_special)
            out = model_forward(model, ids, attn, pos, hidden=True)
            hs = out.hidden_states
            stack = torch.stack([h[:, -1, :] for h in hs], dim=1).float()
            res = {"stack": stack, "n": len(sub)}
            del out, hs
            return res
        res, used = oom_retry(_run, b, what="p_harvest")
        stack = res["stack"]
        take = idx[:res["n"]]
        l1, d = int(stack.shape[1]), int(stack.shape[2])
        if a_out is None:
            a_out = np.zeros((n, l1, d), dtype=np.float16)
            nrm_out = np.zeros((n, l1), dtype=np.float32)
            for k in list(sets) + ["fullV_final"]:
                r_out[k] = np.zeros((n, l1), dtype=np.float32)
        a_out[take] = stack.to(torch.float16).cpu().numpy()
        nrm_out[take] = stack.norm(dim=-1).float().cpu().numpy()
        if sets:
            drv = logit_lens_drives(stack, w_u, final_norm, sets, lens_chunk)
            for k, v in drv.items():
                r_out[k][take] = v
        del stack, res
        i += len(take)
        b = used
    res_out: dict[str, np.ndarray] = {"A": a_out, "norms": nrm_out}
    res_out.update({f"r_{k}": v for k, v in r_out.items()})
    return res_out


def save_wu(model, token_ids: dict[str, list[int]], out_dir: Path) -> dict[str, int]:
    """WU_ref / WU_hed / WU_ctl: the unembedding rows of the resolved ids.  NEVER padded."""
    import torch
    w_u, _ = lens_parts(model)
    kept: dict[str, int] = {}
    with torch.no_grad():
        wb = w_u.detach()
        vocab, d = int(wb.shape[0]), int(wb.shape[1])
        for key, name in (("refusal", "WU_ref"), ("hedge", "WU_hed"), ("control", "WU_ctl")):
            ids = [i for i in (token_ids.get(key) or []) if 0 <= i < vocab]
            rows = (wb.index_select(0, torch.tensor(ids, dtype=torch.long, device=wb.device))
                    .float().cpu().numpy() if ids else np.zeros((0, d), dtype=np.float32))
            atomic_npy(out_dir / f"{name}.npy", rows.astype(np.float32))
            kept[name] = int(rows.shape[0])
    return kept


# =========================================================================================
# E2 -- direction bank (Tier 1), parent-free, fitted from the checkpoint's OWN activations
# =========================================================================================
def band_ranges(depth: int, n_bands: int = 6) -> list[tuple[int, int]]:
    """B_k = decoder blocks [floor((k-1)L/6), floor(kL/6)).  FRACTION OF DEPTH, never an
    absolute layer index: L differs per family (18..38) and d per family (640..3840)."""
    out = []
    for k in range(1, n_bands + 1):
        lo = int(np.floor((k - 1) * depth / n_bands))
        hi = int(np.floor(k * depth / n_bands))
        out.append((lo, max(hi, lo + 1)))
    return out


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return (v / n).astype(np.float32) if n > 1e-12 else np.zeros_like(v, dtype=np.float32)


def _orthonormal_basis(vecs: list[np.ndarray]) -> np.ndarray:
    """Orthonormal basis (d, r) of span(vecs) via QR; rank-deficient columns dropped."""
    m = np.stack([np.asarray(v, dtype=np.float64) for v in vecs], 1)
    q, r = np.linalg.qr(m)
    keep = np.abs(np.diag(r)) > 1e-10
    return q[:, keep]


def _remove_span(v: np.ndarray, q: np.ndarray) -> np.ndarray:
    return v - q @ (q.T @ v)


def _band_axis(a_rows: np.ndarray, y: np.ndarray, lo: int, hi: int) -> np.ndarray:
    """Band-mean of the per-layer difference-in-means at the last prompt token.

    Each per-layer difference is unit-normalised BEFORE the band mean (residual norms grow
    with depth, so an unnormalised mean would be the deepest layer of the band and nothing
    else), and the mean is unit-normalised again.  Recorded in meta as `band_aggregation`.
    """
    from ncands import axis_weight_vector
    c = axis_weight_vector(y, np.ones(len(y), dtype=np.float64))
    per = []
    for l in range(lo + 1, hi + 1):          # hidden_states index l = output of block l-1
        per.append(_unit(c @ a_rows[:, l, :].astype(np.float64)))
    return _unit(np.mean(np.stack(per, 0), 0))


def fit_direction_bank(a_prompt: np.ndarray, stimuli: list[dict], depth: int, tag: str,
                       n_draws: int) -> dict[str, np.ndarray]:
    """dirs_F / dirs_N6 / dirs_R / fit_halves / bank_R.  No cosine between the halves is
    computed here -- the halves are SAVED and a separate blind scorer consumes them."""
    src = np.array([r["source"] for r in stimuli])
    y = np.array([int(r["y"]) for r in stimuli])
    easy = np.where(np.array([int(r["set_id"]) for r in stimuli]) == 0)[0]
    xs = np.where(np.char.startswith(src, "xstest_v2_"))[0]
    d = int(a_prompt.shape[2])
    bands = band_ranges(depth, CFG["n_bands"])

    a_easy, y_easy = a_prompt[easy].astype(np.float32), y[easy]
    a_xs, y_xs = a_prompt[xs].astype(np.float32), y[xs]

    dirs_f = np.stack([_band_axis(a_easy, y_easy, lo, hi) for lo, hi in bands])
    dirs_n6 = np.stack([_band_axis(a_xs, y_xs, lo, hi) for lo, hi in bands])

    # split-half fits of F_b (stratified by y, seeded per tag)
    rng = seeded_rng(tag, "fit_halves")
    half_idx: list[np.ndarray] = [[], []]
    for cls in (0, 1):
        pool = np.where(y_easy == cls)[0]
        perm = rng.permutation(pool)
        cut = len(perm) // 2
        half_idx[0] = np.concatenate([half_idx[0], perm[:cut]]).astype(int)
        half_idx[1] = np.concatenate([half_idx[1], perm[cut:]]).astype(int)
    halves = np.zeros((len(bands), 2, d), dtype=np.float32)
    for bi, (lo, hi) in enumerate(bands):
        for h in (0, 1):
            sel = half_idx[h]
            halves[bi, h] = _band_axis(a_easy[sel], y_easy[sel], lo, hi)

    # matched-norm random controls, Gram-Schmidt against BOTH F_b and N6_b, rescaled to the
    # norm of the direction they control (F_b and N6_b are unit, so the controls are unit).
    dirs_r = np.zeros((len(bands), n_draws, d), dtype=np.float32)
    for bi in range(len(bands)):
        rg = seeded_rng(tag, f"B{bi + 1}", "R")
        q = _orthonormal_basis([dirs_f[bi], dirs_n6[bi]])   # F_b and N6_b are NOT orthogonal
        for j in range(n_draws):
            v = rg.standard_normal(d).astype(np.float64)
            v = _remove_span(_remove_span(v, q), q)          # twice: numerically clean
            dirs_r[bi, j] = _unit(v) * float(np.linalg.norm(dirs_f[bi]))

    # the 3 FIXED R directions of the K = 15 projection bank (band-independent)
    rgb = seeded_rng(tag, "bankR")
    basis_all = [dirs_f[i] for i in range(len(bands))] + [dirs_n6[i] for i in range(len(bands))]
    bank_r = np.zeros((3, d), dtype=np.float32)
    for j in range(3):
        q = _orthonormal_basis(basis_all + [bank_r[i] for i in range(j)])
        v = rgb.standard_normal(d).astype(np.float64)
        v = _remove_span(_remove_span(v, q), q)
        bank_r[j] = _unit(v)
    return {"dirs_F": dirs_f, "dirs_N6": dirs_n6, "dirs_R": dirs_r,
            "fit_halves": halves, "bank_R": bank_r}


def projection_bank(arr_dir: Path) -> tuple[np.ndarray, list[str]]:
    """K = 6 F_b + 6 N6_b + 3 fixed R = 15 directions, in a FIXED, recorded order."""
    f = np.load(arr_dir / "dirs_F.npy")
    n6 = np.load(arr_dir / "dirs_N6.npy")
    br = np.load(arr_dir / "bank_R.npy")
    bank = np.concatenate([f, n6, br], 0).astype(np.float32)
    names = ([f"F_b{i + 1}" for i in range(f.shape[0])]
             + [f"N6_b{i + 1}" for i in range(n6.shape[0])]
             + [f"Rfixed_{i + 1}" for i in range(br.shape[0])])
    return bank, names


# =========================================================================================
# Tier 2 / Tier 3 harvest passes
# =========================================================================================
def dec_harvest(model, tok, texts: Sequence[str], n_new: int, batch: int, eos: set[int],
                add_special: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Greedy decode n_new tokens; hidden states at the generated positions 1..n_new.
    A_dec = mean over generated positions before the first EOS, tok1 = the first generated
    position, dec_ntok = the per-row count.  Semantics of vendor/harvest_variants.dec_harvest,
    re-expressed against this module's left-padded encoder."""
    import torch
    n = len(texts)
    a_mean = a_first = None
    ntok = np.zeros(n, dtype=np.int32)
    i = 0
    b = max(1, batch)
    while i < n:
        chunk = list(texts[i:i + b])

        def _run(bs: int, _chunk=chunk):
            sub = _chunk[:bs]
            ids, attn, pos = encode_left(tok, sub, CFG["max_len_prompt"], add_special)
            with torch.no_grad():
                try:
                    out = model(input_ids=ids, attention_mask=attn, position_ids=pos,
                                use_cache=True, output_hidden_states=True, logits_to_keep=1)
                except TypeError:
                    out = model(input_ids=ids, attention_mask=attn, use_cache=True,
                                output_hidden_states=True)
                last_h = torch.stack([h[:, -1, :] for h in out.hidden_states], 1).float()
                past = out.past_key_values
                nxt = out.logits[:, -1, :].argmax(-1)
                bb, l1, d = last_h.shape[0], last_h.shape[1], last_h.shape[2]
                acc = torch.zeros((bb, l1, d), device=last_h.device)
                cnt = torch.zeros(bb, device=last_h.device)
                alive = torch.ones(bb, dtype=torch.bool, device=last_h.device)
                first = None
                cur_attn, cur_pos = attn, pos[:, -1]
                for _k in range(n_new):
                    is_eos = torch.tensor([int(t) in eos for t in nxt.tolist()],
                                          dtype=torch.bool, device=last_h.device)
                    alive = alive & ~is_eos
                    cur_attn = torch.cat([cur_attn, torch.ones((bb, 1), dtype=cur_attn.dtype,
                                                               device=cur_attn.device)], 1)
                    cur_pos = cur_pos + 1
                    try:
                        o = model(input_ids=nxt[:, None], attention_mask=cur_attn,
                                  position_ids=cur_pos[:, None], past_key_values=past,
                                  use_cache=True, output_hidden_states=True)
                    except TypeError:
                        o = model(input_ids=nxt[:, None], attention_mask=cur_attn,
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
                mean = torch.where((cnt > 0)[:, None, None],
                                   acc / cnt.clamp_min(1)[:, None, None], last_h)
                return {"mean": mean.to(torch.float16).cpu().numpy(),
                        "first": first.to(torch.float16).cpu().numpy(),
                        "cnt": cnt.cpu().numpy().astype(np.int32), "n": bb}
        res, used = oom_retry(_run, b, what="dec_harvest")
        k = res["n"]
        if a_mean is None:
            a_mean = np.zeros((n, res["mean"].shape[1], res["mean"].shape[2]), dtype=np.float16)
            a_first = np.zeros_like(a_mean)
        a_mean[i:i + k] = res["mean"]
        a_first[i:i + k] = res["first"]
        ntok[i:i + k] = res["cnt"]
        i += k
        b = used
    return a_mean, a_first, ntok


def simple_prompt_harvest(model, tok, texts: Sequence[str], batch: int,
                          add_special: bool) -> np.ndarray:
    """A_c11 / A_ams style pass: last-prompt-token hidden states only, no lens."""
    import torch
    n = len(texts)
    out_a: np.ndarray | None = None
    i = 0
    b = max(1, batch)
    while i < n:
        chunk = list(texts[i:i + b])

        def _run(bs: int, _chunk=chunk):
            sub = _chunk[:bs]
            ids, attn, pos = encode_left(tok, sub, CFG["max_len_prompt"], add_special)
            out = model_forward(model, ids, attn, pos, hidden=True)
            st = torch.stack([h[:, -1, :] for h in out.hidden_states], 1).to(torch.float16).cpu().numpy()
            del out
            return st
        st, used = oom_retry(_run, b, what="prompt_harvest")
        if out_a is None:
            out_a = np.zeros((n, st.shape[1], st.shape[2]), dtype=np.float16)
        out_a[i:i + st.shape[0]] = st
        i += st.shape[0]
        b = used
    return out_a


# =========================================================================================
# manifest / DONE
# =========================================================================================
def write_manifest(out_dir: Path) -> Path:
    man = {"utc": utc_now(), "files": {}}
    for p in sorted(out_dir.rglob("*")):
        if p.is_dir() or p.name in ("MANIFEST.sha256.json", "DONE") or p.name.endswith(".tmp"):
            continue
        man["files"][p.relative_to(out_dir).as_posix()] = {
            "sha256": sha256_file(p), "bytes": p.stat().st_size}
    return jdump(out_dir / "MANIFEST.sha256.json", man)


def verify_manifest(out_dir: Path) -> dict:
    mp = out_dir / "MANIFEST.sha256.json"
    if not mp.exists():
        return {"ok": False, "why": "no manifest"}
    man = jload(mp)
    bad = []
    for rel, rec in man["files"].items():
        f = out_dir / rel
        if not f.exists():
            bad.append(f"missing {rel}")
        elif sha256_file(f) != rec["sha256"]:
            bad.append(f"drifted {rel}")
    return {"ok": not bad, "n_files": len(man["files"]), "problems": bad}


# =========================================================================================
# PHASE C -- harvest driver
# =========================================================================================
def cells_32(stimuli: list[dict]) -> dict:
    """The FIXED 16-harmful / 16-hard-benign intervention subset.  Hashed, tag-free (so the
    same 32 prompts are used for every checkpoint) and committed with its sha256."""
    hard = [r for r in stimuli if int(r["set_id"]) == 1]
    by = {1: [r for r in hard if int(r["y"]) == 1], 0: [r for r in hard if int(r["y"]) == 0]}
    chosen: list[dict] = []
    for cls in (1, 0):
        ids = seeded_order([r["stim_id"] for r in by[cls]], "cells32", f"y{cls}")[:16]
        keep = {i for i in ids}
        chosen.extend([r for r in by[cls] if r["stim_id"] in keep])
    chosen = sorted(chosen, key=lambda r: r["stim_id"])
    ids = [r["stim_id"] for r in chosen]
    return {"n": len(chosen), "ids": ids,
            "ids_sha256": sha256_text("\n".join(sorted(ids))),
            "y": [int(r["y"]) for r in chosen],
            "rows": [{"stim_id": r["stim_id"], "y": int(r["y"]), "source": r["source"],
                      "text": r["text"]} for r in chosen],
            "rule": "hashed sha256(SEED|cells32|y<cls>|stim_id) over the HARD stimuli, "
                    "first 16 per class, then sorted by stim_id"}


def harvest_one(row: dict, args: argparse.Namespace) -> dict:
    from lease import vram_lease
    import torch
    tag, repo = row["tag"], row["repo"]
    out_dir = ARRAYS / tag
    if (out_dir / "DONE").exists() and not args.force:
        logger.info(f"{tag}: DONE present -> skip")
        return {"tag": tag, "skipped": True}
    if not order_gate_ok(tag):
        logger.error("=" * 78)
        logger.error(f"ORDER GATE REFUSED: {tag} is not in any COMMITTED graded_truth_s*.json "
                     f"whose sha256 appears in logs/chain.jsonl.  Behaviour must be graded and "
                     f"hash-committed BEFORE any activation of this checkpoint is looked at.")
        logger.error("=" * 78)
        raise SystemExit(2)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "DONE").unlink(missing_ok=True)

    stimuli = jload(ASSETS / "stimuli.json")["rows"]
    token_sets = jload(ASSETS / "token_sets.json")
    if args.limit_items:
        stimuli = stimuli[:args.limit_items]

    t_all = time.time()
    reset_peak()
    timings: dict[str, float] = {}
    meta: dict[str, Any] = {"tag": tag, "repo": repo, "revision_sha": row.get("revision_sha"),
                            "utc": utc_now(), "cfg": dict(CFG), "seed": SEED}
    snap: dict = {}
    lease_mib = lease_mib_for(row.get("bf16_gb"))
    timings["lease_mib"] = lease_mib
    with vram_lease(mib=lease_mib, artifact=f"exp2_harvest_{tag}") as grant:
        set_memory_fraction(lease_mib)
        model, tok, load_info, load_errs, t_dl, t_ld = acquire_model(
            repo, row.get("revision_sha"), bool(row.get("trust_remote_code")))
        timings["t_download_s"] = t_dl
        timings["t_load_s"] = t_ld
        try:
            depth = resolve_depth(model)
            t0 = time.time()
            fp6, fpfull = weight_fingerprints(model)      # bf16 weights, before any recast
            timings["t_fingerprint_s"] = time.time() - t0
            batch = max(1, (args.batch // 2) if grant.get("half_batch") else args.batch)
            # EVERY forward-only pass of the harvest runs at batch 1: no pad token can exist and
            # one kernel path is used throughout. Selftest T4 measured left-padded batches moving
            # last-token states 10-290% relative (gemma-3, pythia), and bf16 GEMM kernels also
            # differ by batch shape, so batch 1 is the only configuration that is both padding-free
            # and bit-reproducible (it also makes T3a's arm-0 vs plain-forward check exact).
            batch = 1
            token_ids = encode_token_sets(tok, token_sets)
            jdump(out_dir / "token_ids.json", {
                "utc": utc_now(), "per_tokenizer": token_ids,
                "n_surface_forms": {k: len(token_sets.get(k, [])) for k in ("refusal", "hedge", "control")},
                "n_kept": {k: len(v) for k, v in token_ids.items()},
                "note": "resolved PER TOKENIZER at harvest time; NEVER padded"})

            rendered = [render_one(tok, r["text"]) for r in stimuli]
            texts = [r[0] for r in rendered]
            add_special = rendered[0][2]
            render_format = rendered[0][1]

            # ---- TIER 1: prompt-site harvest
            t0 = time.time()
            ph = p_harvest(model, tok, texts, max_len=CFG["max_len_prompt"], batch=batch,
                           token_ids=token_ids, add_special=add_special,
                           lens_chunk=CFG["lens_chunk"])
            timings["t_p_harvest_s"] = time.time() - t0
            atomic_npy(out_dir / "A_prompt.npy", ph["A"])
            atomic_npy(out_dir / "norms.npy", ph["norms"])
            for key, name in (("r_refusal", "r_refusal"), ("r_hedge", "r_hedge"),
                              ("r_control", "r_control"), ("r_fullV_final", "r_fullV_final")):
                arr = ph.get(key)
                if arr is None:
                    arr = np.zeros((len(texts), ph["A"].shape[1]), dtype=np.float32)
                    deviation("empty_token_set", f"{tag}: {key} has no resolved ids", "harvest")
                atomic_npy(out_dir / f"{name}.npy", arr.astype(np.float32))

            t0 = time.time()
            kept = save_wu(model, token_ids, out_dir)
            timings["t_wu_s"] = time.time() - t0

            # ---- TIER 1: E2 direction bank
            t0 = time.time()
            bank = fit_direction_bank(ph["A"], stimuli, depth, tag, args.r_draws_p)
            for k, v in bank.items():
                atomic_npy(out_dir / f"{k}.npy", v)
            timings["t_directions_s"] = time.time() - t0

            c32 = cells_32(stimuli)
            jdump(out_dir / "cells_32.json", c32)

            # ---- TIER 2
            if args.tier2:
                t0 = time.time()
                hard = [r for r in stimuli if int(r["set_id"]) == 1]
                dtexts = [render_one(tok, r["text"])[0] for r in hard]
                # batch 1: dec_harvest left-pads multi-row batches, and T4 showed padded
                # batches move last-token states by 10-290% on some architectures.
                a_mean, a_first, ntok = dec_harvest(model, tok, dtexts, CFG["dec_new"],
                                                    1, eos_ids(model, tok), add_special)
                atomic_npy(out_dir / "A_dec.npy", a_mean)
                atomic_npy(out_dir / "A_dec_tok1.npy", a_first)
                atomic_npy(out_dir / "dec_ntok.npy", ntok)
                meta["dec"] = {"n_rows": int(len(hard)), "mean_ntok": float(ntok.mean()),
                               "n_zero_tok": int((ntok == 0).sum()),
                               "rows": "HARD stimuli (set_id==1) in stimuli.json order",
                               "rows_source": "assets/stimuli.json",
                               "note": "ASSET_MAP names behaviour_items.json as the A_dec source "
                                       "but does not say which 8 of its 168 rows are dropped; the "
                                       "iteration-4 reference harvest meta.json states 'HARD stimuli "
                                       "in stimuli.json order' (exactly 160), which is unambiguous "
                                       "and is what is used here."}
                timings["t_dec_s"] = time.time() - t0

            # ---- TIER 3
            if args.tier3:
                t0 = time.time()
                c11 = jload(ASSETS / "c11_items.json")["items"]
                atomic_npy(out_dir / "A_c11.npy", simple_prompt_harvest(
                    model, tok, [render_one(tok, x["prompt"])[0] for x in c11], batch, add_special))
                timings["t_c11_s"] = time.time() - t0
                t0 = time.time()
                cells = jload(ASSETS / "cells.json")["cells"]
                atomic_npy(out_dir / "A_ams.npy", simple_prompt_harvest(
                    model, tok, [render_one(tok, c["plain_prompt"])[0] for c in cells],
                    batch, add_special))
                timings["t_ams_s"] = time.time() - t0
                t0 = time.time()
                for name, sys_p, plain in (("A_prompt_p1.npy", None, True),
                                           ("A_prompt_p2.npy", "You are a helpful assistant.", False)):
                    tx = ([r["text"] + "\n" for r in stimuli] if plain
                          else [render_one(tok, r["text"], sys_p)[0] for r in stimuli])
                    atomic_npy(out_dir / name, simple_prompt_harvest(model, tok, tx, batch, plain or add_special))
                timings["t_p1p2_s"] = time.time() - t0

            # ---- E3 intervention grid
            if not args.no_cells:
                import interventions
                t0 = time.time()
                cell_stats = interventions.run_grid(
                    model, tok, out_dir, depth, c32, token_ids, add_special,
                    r_draws_p=args.r_draws_p, with_c5=args.with_c5, tier2=args.tier2,
                    batch=min(batch, 16), max_cells=args.max_cells)
                timings["t_cells_s"] = time.time() - t0
                meta["cells"] = cell_stats

            # ---- TIER 3, LAST: A_prompt_p3 = the same weights recast to float16.  Runs after
            # every bf16 pass because it mutates the loaded model (which is unloaded next).
            if args.tier3:
                t0 = time.time()
                model_dtype_before = str(next(model.parameters()).dtype)
                model.half()
                atomic_npy(out_dir / "A_prompt_p3.npy",
                           simple_prompt_harvest(model, tok, texts, batch, add_special))
                timings["t_p3_fp16_s"] = time.time() - t0
                meta["n5_perturbations"] = {"p1": "plain render", "p2": "helpful system prompt",
                                            "p3": f"same weights recast {model_dtype_before} -> float16"}
            cfgo = model.config
            tmpl = getattr(tok, "chat_template", None)
            meta.update({
                "n_layers": int(depth), "hidden_size": int(ph["A"].shape[2]),
                "n_hidden_states": int(ph["A"].shape[1]),
                "n_params": int(sum(p.numel() for p in model.parameters())),
                "dtype": "torch.bfloat16",
                "tie_word_embeddings": bool(getattr(cfgo, "tie_word_embeddings", False)),
                "vocab_size": int(getattr(cfgo, "vocab_size", 0) or 0),
                "model_type": getattr(cfgo, "model_type", None),
                "chat_template_sha": sha256_text(tmpl) if tmpl else None,
                "has_chat_template": bool(tmpl),
                "trust_remote_code": bool(load_info.get("trust_remote_code")),
                "load_format": "AutoModelForCausalLM.from_pretrained(dtype=bfloat16, "
                               "low_cpu_mem_usage=True).to('cuda')",
                "load_info": load_info, "load_failed_attempts": load_errs,
                "transformers_version": __import__("transformers").__version__,
                "torch_version": torch.__version__,
                "weight_fingerprint": fp6, "weight_sha_full": fpfull,
                "pad_side": "left_with_explicit_position_ids",
                "render_format": render_format,
                "prompt_render_example": texts[0][:600],
                "prompt_token_lengths": _tok_len_stats(tok, texts, CFG["max_len_prompt"]),
                "wu_kept_counts": kept,
                "token_ids_kept": {k: len(v) for k, v in token_ids.items()},
                "band_ranges": [list(b) for b in band_ranges(depth, CFG["n_bands"])],
                "band_rule": "B_k = decoder blocks [floor((k-1)L/6), floor(kL/6)); FRACTION OF "
                             "DEPTH, never an absolute layer index",
                "band_aggregation": "per-layer diff-in-means unit-normalised, band-mean, "
                                    "unit-normalised again",
                "r_control_mode": "matched_displacement (see interventions.py)",
                "harvest_batching": "batch1 (every forward-only pass; padding-free, single kernel path)",
                "tiers": {"tier1": True, "tier2": bool(args.tier2), "tier3": bool(args.tier3),
                          "with_c5": bool(args.with_c5)},
                "lease_granted": bool(grant.get("granted")),
            })
        finally:
            unload(model)
            if not args.keep_snapshot:
                snap = delete_snapshot(repo)       # INSIDE the lease

    timings["t_total_s"] = time.time() - t_all
    meta["timings"] = timings
    meta["max_memory_allocated_mib"] = peak_mib()
    jdump(out_dir / "meta.json", meta)
    write_manifest(out_dir)
    ver = verify_manifest(out_dir)
    if not ver["ok"]:
        logger.error(f"MANIFEST verify failed for {tag}: {ver['problems']}")
        raise SystemExit(6)
    (out_dir / "DONE").write_text(utc_now())        # DONE is written LAST
    timings["snapshot_delete_freed_bytes"] = snap.get("freed_bytes", 0)
    record_timing(tag, "harvest", {**timings, "n_manifest_files": ver["n_files"],
                                   "max_memory_allocated_mib": meta["max_memory_allocated_mib"]})
    logger.info(f"HARVEST DONE {tag}: total {timings['t_total_s']:.0f}s, "
                f"peak {meta['max_memory_allocated_mib']:.0f} MiB, {ver['n_files']} files")
    return meta


def _tok_len_stats(tok, texts: Sequence[str], max_len: int) -> dict:
    lens = [len(tok(t, add_special_tokens=False)["input_ids"]) for t in texts[:min(64, len(texts))]]
    return {"mean": float(np.mean(lens)), "p50": float(np.median(lens)),
            "p95": float(np.quantile(lens, 0.95)), "max": int(np.max(lens)),
            "truncation_cap": int(max_len)}


def cmd_harvest(args: argparse.Namespace) -> int:
    gpu_setup()
    idx = sweep_index()
    rows = []
    for t in (args.tags or []):
        if t not in idx:
            logger.error(f"unknown tag {t}")
            return 3
        rows.append(idx[t])
    if not rows:
        logger.error("harvest needs --tags")
        return 3
    rc = 0
    for r in rows:
        try:
            harvest_one(r, args)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"harvest failed for {r['tag']}")
            deviation("harvest_failed", f"{r['tag']}: {exc!r}"[:300], "harvest")
            rc = 1
            empty_cache()
    return rc


# =========================================================================================
# SELFTESTS
# =========================================================================================
def cmd_selftest(args: argparse.Namespace) -> int:
    import interventions
    gpu_setup()
    idx = sweep_index()
    tag = args.tag
    if tag not in idx:
        logger.error(f"unknown tag {tag}")
        return 3
    row = idx[tag]
    out_dir = ARRAYS / tag
    if not (out_dir / "dirs_F.npy").exists():
        logger.error(f"{out_dir}/dirs_F.npy missing -- run `harvest` for {tag} first")
        return 3
    from lease import vram_lease
    results: dict[str, Any] = {"utc": utc_now(), "tag": tag, "repo": row["repo"]}
    with vram_lease(mib=VRAM_DECLARED_MIB, artifact=f"exp2_selftest_{tag}"):
        model, tok, load_info, _, _, _ = acquire_model(
            row["repo"], row.get("revision_sha"), bool(row.get("trust_remote_code")))
        try:
            depth = resolve_depth(model)
            c32 = jload(out_dir / "cells_32.json")
            token_ids = jload(out_dir / "token_ids.json")["per_tokenizer"]
            add_special = render_one(tok, "x")[2]
            results["T3"] = interventions.selftests_t3(
                model, tok, out_dir, depth, c32, token_ids, add_special, batch=args.batch)
            results["T4"] = selftest_t4(model, tok, out_dir, n_rows=8)
            results["max_memory_allocated_mib"] = peak_mib()
        finally:
            unload(model)
    p = RESULTS / "selftests.json"
    prev = jload(p) if p.exists() else {"runs": []}
    prev.setdefault("runs", []).append(results)
    prev["utc"] = utc_now()
    jdump(p, prev)
    logger.info(json.dumps({k: v for k, v in results.items() if k not in ("repo",)}, default=str)[:2000])
    return 0


def selftest_t4(model, tok, out_dir: Path, n_rows: int = 8) -> dict:
    """T4 GENERATION FIDELITY: greedy_shrink token-identical to model.generate on n_rows
    (precondition: no logits processors), and batch-16 identical to batch-1 on n_rows."""
    import torch
    rows = jload(out_dir / "cells_32.json")["rows"][:n_rows]
    rendered = [render_one(tok, r["text"]) for r in rows]
    texts = [x[0] for x in rendered]
    add_special = rendered[0][2]
    lp = logits_processor_overrides(model)
    out: dict[str, Any] = {"precondition_no_logits_processors": not lp,
                           "logits_processor_overrides": lp, "n_rows": len(rows),
                           "max_new": 16}
    if lp:
        out["verdict"] = "SKIPPED (generation_config carries logits processors; hf_generate path used)"
        return out
    eos = eos_ids(model, tok)
    pad_id = tok.pad_token_id if tok.pad_token_id is not None else (tok.eos_token_id or 0)
    prev = tok.padding_side
    tok.padding_side = "left"
    try:
        enc = tok(texts, return_tensors="pt", padding=True, truncation=True,
                  max_length=CFG["max_len_gen"], add_special_tokens=add_special)
        enc = {k: v.to("cuda") for k, v in enc.items() if k in ("input_ids", "attention_mask")}
        shrink, _ = greedy_shrink(model, enc, 16, eos, pad_id)
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=16, do_sample=False, pad_token_id=pad_id,
                                 repetition_penalty=1.0, no_repeat_ngram_size=0, temperature=None,
                                 top_p=None, top_k=None, min_new_tokens=0)
        hf = gen[:, enc["input_ids"].shape[1]:]
        agree = 0
        for i in range(len(texts)):
            a = trim_to_eos(shrink[i].tolist(), eos)
            b = trim_to_eos(hf[i].tolist(), eos)
            agree += int(a == b)
        out["shrink_vs_generate_rows_identical"] = f"{agree}/{len(texts)}"
        out["shrink_vs_generate_pass"] = bool(agree == len(texts))

        b16, _ = generate_batch(model, tok, texts, add_special, 16, 16, use_shrink=True)
        b1, _ = generate_batch(model, tok, texts, add_special, 16, 1, use_shrink=True)
        agree2 = sum(int(trim_to_eos(x, eos) == trim_to_eos(y, eos)) for x, y in zip(b16, b1))
        out["batch16_vs_batch1_rows_identical"] = f"{agree2}/{len(texts)}"
        out["batch16_vs_batch1_pass"] = bool(agree2 == len(texts))
    finally:
        tok.padding_side = prev
    out["verdict"] = "PASS" if (out.get("shrink_vs_generate_pass") and
                                out.get("batch16_vs_batch1_pass")) else "FAIL"
    return out


# =========================================================================================
# main
# =========================================================================================
@logger.catch(reraise=True)
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="pipeline.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen", help="PHASE A: greedy generation, behaviour first")
    g.add_argument("--tags", nargs="*", default=None)
    g.add_argument("--from-sweep", type=int, default=None,
                   help="take the first N still-pending tags of results/sweep_order.json")
    g.add_argument("--limit-items", type=int, default=None)
    g.add_argument("--max-new-harm", type=int, default=140)
    g.add_argument("--max-new-benign", type=int, default=96)
    g.add_argument("--batch", type=int, default=16)
    g.add_argument("--smoke", type=int, default=None, help="cap items PER SET (smoke runs)")
    g.add_argument("--item-sets", default=None, help="override results/item_sets.json")
    g.set_defaults(fn=cmd_gen)

    h = sub.add_parser("harvest", help="PHASE C: arrays, behind the ORDER GATE")
    h.add_argument("--tags", nargs="*", default=None)
    h.add_argument("--tier2", action="store_true")
    h.add_argument("--tier3", action="store_true")
    h.add_argument("--r-draws-p", type=int, default=5)
    h.add_argument("--with-c5", action="store_true")
    h.add_argument("--no-cells", action="store_true", help="skip the E3 grid entirely")
    h.add_argument("--max-cells", type=int, default=None, help="cap the number of E3 cells (smoke)")
    h.add_argument("--batch", type=int, default=16)
    h.add_argument("--limit-items", type=int, default=None)
    h.add_argument("--force", action="store_true", help="re-harvest even if DONE exists")
    h.add_argument("--keep-snapshot", action="store_true",
                   help="do not delete the HF snapshot after the visit (e.g. selftest next)")
    h.set_defaults(fn=cmd_harvest)

    s = sub.add_parser("selftest", help="T3a-T3d and T4 instrument checks")
    s.add_argument("--tag", required=True)
    s.add_argument("--batch", type=int, default=16)
    s.set_defaults(fn=cmd_selftest)

    a = ap.parse_args(argv)
    setup_logging(f"pipeline_{a.cmd}")
    logger.info(f"pipeline {a.cmd}  WS={WS}  free={free_gb():.0f} GB")
    return int(a.fn(a) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
