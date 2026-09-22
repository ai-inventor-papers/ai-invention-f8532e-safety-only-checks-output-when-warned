"""Variant construction (plan section 3): build(fk, variant) -> (model, tok, render_fn, info). Deterministic, seed 20260921.

The reference arm is the parent at bf16 with its stock chat template and NO system prompt (Qwen3: enable_thinking=False).
Every edit is computed from hash-disjoint side sets (assets/side_sets.json) and cached under private/edits/ so the
generation phase and the harvest phase rebuild the SAME weights (weight_fingerprint asserted equal in both).
No behaviour item and no readout stimulus is ever used to construct a variant.
"""
from __future__ import annotations

import gc
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ADAPTERS, ASSETS, D2, PARENTS, PRIVATE, RESULTS, SEED, SYS_CAUTIOUS, SYS_HELPFUL,  # noqa: E402
                    Deviations, get_device, jdump, jload, utc_now)
from loguru import logger  # noqa: E402

EDITS = PRIVATE / "edits"
EDITS.mkdir(parents=True, exist_ok=True)
DL_PATTERNS = ["*.json", "*.safetensors", "*.model", "*.txt", "*.jinja", "*.tiktoken", "tokenizer*"]
SYSTEM_OF = {"sysprompt": SYS_HELPFUL, "cautious": SYS_CAUTIOUS}


def lay(f: float, L: int) -> int:
    return int(math.floor(f * L + 0.5))


def torch_mod():
    import torch
    return torch


def repo_for(fk: str, variant: str | None = None) -> str:
    """Constructed parents come from PARENTS; A13 HG tags ('HG__<org>--<name>') name a harvested checkpoint."""
    if fk == "HG":
        return variant.replace("--", "/", 1)
    return PARENTS[fk]["repo"]


def download(repo: str) -> str:
    from huggingface_hub import snapshot_download
    for attempt in range(4):
        try:
            local = snapshot_download(repo, allow_patterns=DL_PATTERNS)
            if not list(Path(local).glob("*.safetensors")):
                local = snapshot_download(repo, allow_patterns=DL_PATTERNS + ["*.bin", "*.py"])
            return local
        except Exception as e:  # noqa: BLE001
            logger.warning(f"download {repo} attempt {attempt}: {e!r}"[:300])
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"download failed: {repo}")


# ------------------------------------------------------------------------------------------------ rendering
def render(tok, text: str, system: str | None = None, mode: str = "chat") -> str:
    """I3 gen.chat_text fallback chain, with an optional system message. mode='plain' is the N5 p1 perturbation."""
    if mode == "plain":
        return f"User: {text}\nAssistant:"
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": text}]
    for kw in (dict(add_generation_prompt=True, enable_thinking=False, tokenize=False),
               dict(add_generation_prompt=True, tokenize=False)):
        try:
            return tok.apply_chat_template(msgs, **kw)
        except Exception:  # noqa: BLE001
            continue
    return ((system + "\n\n") if system else "") + text + "\n"


def make_render_fn(tok, variant: str):
    sysmsg = SYSTEM_OF.get(variant)
    return lambda text, mode="chat": render(tok, text, sysmsg if mode == "chat" else None, mode)


# ------------------------------------------------------------------------------------------------ loading
def load_parent(fk: str, dtype: str = "bfloat16", attn: str = "sdpa", int8_bnb: bool = False, repo: str | None = None):
    """Loads on CPU (weights are constructed/edited on CPU so they do not depend on the device, amendment A13);
    int8_bnb=True loads LLM.int8 (bitsandbytes) straight onto the GPU (fp16 compute), as the plan registered."""
    torch = torch_mod()
    from transformers import AutoModelForCausalLM, AutoTokenizer
    repo = repo or PARENTS[fk]["repo"]
    local = download(repo)
    tok = AutoTokenizer.from_pretrained(local)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    dt = {"bfloat16": torch.bfloat16, "float32": torch.float32, "float16": torch.float16}[dtype]
    kw = dict(dtype=dt, low_cpu_mem_usage=True, attn_implementation=attn, output_loading_info=True)
    if int8_bnb:
        from transformers import BitsAndBytesConfig
        kw.update(quantization_config=BitsAndBytesConfig(load_in_8bit=True), device_map={"": 0}, dtype=torch.float16)
    model, info = AutoModelForCausalLM.from_pretrained(local, **kw)
    model.eval()
    miss = list((info or {}).get("missing_keys", []) or [])
    if miss:
        raise RuntimeError(f"{repo}: {len(miss)} missing tensors at load")
    return model, tok, local


def lens_parts(model):
    head = getattr(model, "lm_head", None)
    W_U = head.weight if head is not None and getattr(head, "weight", None) is not None else model.get_input_embeddings().weight
    inner = getattr(model, "model", model)
    fn = getattr(inner, "norm", None) or getattr(inner, "final_layernorm", None)
    return W_U, fn


def blocks(model):
    return getattr(model, "model", model).layers


# ------------------------------------------------------------------------------------------------ fingerprints
def _tensor_bytes(t) -> bytes:
    torch = torch_mod()
    if hasattr(t, "is_quantized") and t.is_quantized:
        parts = [t.int_repr().contiguous().numpy().tobytes()]
        try:
            parts.append(t.q_per_channel_scales().float().numpy().tobytes())
        except RuntimeError:
            parts.append(np.float32(t.q_scale()).tobytes())
        return b"".join(parts)
    x = t.detach().contiguous()
    if x.dtype == torch.bfloat16:
        x = x.view(torch.int16)
    return x.cpu().numpy().tobytes()


def _lin_weight(mod):
    w = getattr(mod, "weight", None)
    return w() if callable(w) else w


def weight_fingerprint(model) -> str:
    """sha256 over embed, lm_head, layer0 o_proj, mid down_proj, last o_proj, final norm (plan section 3)."""
    B = blocks(model)
    L = len(B)
    ts = [model.get_input_embeddings().weight, _lin_weight(model.lm_head),
          _lin_weight(B[0].self_attn.o_proj), _lin_weight(B[L // 2].mlp.down_proj),
          _lin_weight(B[L - 1].self_attn.o_proj)]
    fnw = getattr(lens_parts(model)[1], "weight", None)
    if fnw is not None:          # OLMo(-1) uses a NON-parametric final LayerNorm (no weight): skipped, A13
        ts.append(fnw)
    h = hashlib.sha256()
    for t in ts:
        h.update(_tensor_bytes(t))
    return h.hexdigest()


def full_tensor_sha(model) -> str:
    h = hashlib.sha256()
    for name, t in sorted(model.state_dict().items()):
        h.update(name.encode())
        h.update(_tensor_bytes(t))
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ forward helpers
def last_token_states(model, tok, texts: list[str], batch: int = 16, max_len: int = 192):
    """[N, L+1, d] float32 hidden states at the last real prompt token (right padding) + next-token log-probs [N, V]."""
    torch = torch_mod()
    dev = next(model.parameters()).device
    tok.padding_side = "right"
    H, LP = [], []
    with torch.no_grad():
        for i in range(0, len(texts), batch):
            enc = tok(texts[i:i + batch], return_tensors="pt", padding=True, truncation=True, max_length=max_len,
                      add_special_tokens=False)
            enc = {k: v.to(dev) for k, v in enc.items()}
            out = model(**enc, output_hidden_states=True, use_cache=False)
            last = enc["attention_mask"].sum(1) - 1
            ar = torch.arange(enc["input_ids"].shape[0], device=dev)
            H.append(torch.stack([h[ar, last] for h in out.hidden_states], 1).float().cpu())
            LP.append(torch.log_softmax(out.logits[ar, last].float(), -1).cpu())
            del out
    return torch.cat(H), torch.cat(LP)


def refusal_first_token_ids(tok) -> list[int]:
    """Union of first-token ids of the 60 D2 refusal-onset forms: mid-text (' '+form) and start-of-text (form)."""
    d2 = jload(D2 / "full_data_out.json")
    rows = next(D["examples"] for D in d2["datasets"] if D["dataset"].endswith("::refusal_onset_tokens"))
    forms = [r["metadata_form"] for r in rows]
    ids = set()
    for f in forms:
        for s in (" " + f, f):
            enc = tok(s, add_special_tokens=False)["input_ids"]
            if enc:
                ids.add(int(enc[0]))
    return sorted(ids)


def refusal_topk_ids(tok, k: int = 16) -> list[int]:
    """N2: top-k refusal-onset forms in D2 rank order, mid-text variant first token, deduplicated."""
    d2 = jload(D2 / "full_data_out.json")
    rows = next(D["examples"] for D in d2["datasets"] if D["dataset"].endswith("::refusal_onset_tokens"))
    rows = sorted(rows, key=lambda r: int(r["metadata_rank"]))
    out = []
    for r in rows:
        enc = tok(" " + r["metadata_form"], add_special_tokens=False)["input_ids"]
        if enc and int(enc[0]) not in out:
            out.append(int(enc[0]))
        if len(out) == k:
            break
    return out


# ------------------------------------------------------------------------------------------------ W_U edits
def hbar_and_T(fk: str, model, tok) -> tuple[np.ndarray, list[int]]:
    p = EDITS / f"{fk}_hbar.npz"
    if p.exists():
        z = np.load(p)
        return z["hbar"], [int(x) for x in z["T"]]
    side = jload(ASSETS / "side_sets.json")
    texts = [render(tok, t) for t in side["hbar_32"]]
    H, _ = last_token_states(model, tok, texts)
    hbar = H[:, -1, :].mean(0).numpy().astype(np.float64)   # hidden_states[-1] = post final norm (HF convention)
    T = refusal_first_token_ids(tok)
    np.savez(p, hbar=hbar, T=np.array(T))
    return hbar, T


def untie_head(model) -> bool:
    torch = torch_mod()
    tied = bool(getattr(model.config, "tie_word_embeddings", False)) or \
        model.lm_head.weight.data_ptr() == model.get_input_embeddings().weight.data_ptr()
    if tied:
        model.lm_head.weight = torch.nn.Parameter(model.lm_head.weight.detach().clone())
        model.config.tie_word_embeddings = False
    return tied


def apply_wu_edit(fk: str, model, tok, delta: float) -> dict:
    torch = torch_mod()
    hbar, T = hbar_and_T(fk, model, tok)
    emb_before = model.get_input_embeddings().weight.detach().clone()
    tied = untie_head(model)
    W = model.lm_head.weight
    hb = torch.tensor(hbar, dtype=torch.float64)
    step = (delta * hb / hb.dot(hb)).float()
    with torch.no_grad():
        idx = torch.tensor(T, dtype=torch.long)
        rows = W.data.index_select(0, idx).float() - step[None, :]
        W.data.index_copy_(0, idx, rows.to(W.dtype))
    emb_same = bool(torch.equal(emb_before, model.get_input_embeddings().weight))
    # realised shift on h_bar with the STORED (bf16) rows vs the parent rows
    realised = None
    return {"delta_nat": delta, "n_tokens_edited": len(T), "was_tied": tied, "embed_bit_identical": emb_same,
            "hbar_norm": float(np.linalg.norm(hbar)), "realised_shift_on_hbar": realised}


# ------------------------------------------------------------------------------------------------ lesion (Arditi)
def _ablation_hooks(model, r):
    torch = torch_mod()
    handles = []

    def hook(_m, _i, out):
        o = out[0] if isinstance(out, tuple) else out
        rr = r.to(device=o.device, dtype=o.dtype)
        o2 = o - (o @ rr)[..., None] * rr
        return (o2,) + tuple(out[1:]) if isinstance(out, tuple) else o2

    handles.append(model.get_input_embeddings().register_forward_hook(hook))
    for b in blocks(model):
        handles.append(b.self_attn.o_proj.register_forward_hook(hook))
        handles.append(b.mlp.down_proj.register_forward_hook(hook))
    return handles


def fit_lesion(fk: str, model, tok) -> dict:
    """Candidate directions on lesion_fit; selection by refusal log-mass drop on lesion_val (KL filter on Dolly val)."""
    p = EDITS / f"{fk}_lesion.npz"
    if p.exists():
        z = np.load(p, allow_pickle=True)
        return {"r": z["r"], "l_abl": int(z["l_abl"]), "table": json.loads(str(z["table"])), "cos_parent_axis": None}
    torch = torch_mod()
    side = jload(ASSETS / "side_sets.json")
    t0 = time.time()
    fit_h = [render(tok, t) for t in side["lesion_fit"]["harm"]]
    fit_b = [render(tok, t) for t in side["lesion_fit"]["benign"]]
    Hh, _ = last_token_states(model, tok, fit_h)
    Hb, _ = last_token_states(model, tok, fit_b)
    L = Hh.shape[1] - 1
    cands = list(range(lay(0.3, L), lay(0.7, L) + 1))
    val_h = [render(tok, t) for t in side["lesion_val"]["harm"]]
    val_b = [render(tok, t) for t in side["lesion_val"]["benign"]]
    T = torch.tensor(refusal_first_token_ids(tok), dtype=torch.long)
    _, lp_h0 = last_token_states(model, tok, val_h)
    _, lp_b0 = last_token_states(model, tok, val_b)
    mass0 = torch.logsumexp(lp_h0[:, T], -1).mean().item()
    table = []
    # amendment A12: a candidate table computed earlier for this family (before any lesion-arm behaviour existed) is
    # reused verbatim instead of recomputed (deterministic model + data; saves ~6 CPU-min)
    cached = EDITS / f"{fk}_lesion_literal_rule_table.json"
    if cached.exists():
        table = jload(cached)["table"]
        logger.info(f"    lesion {fk}: reusing the pre-behaviour candidate table {cached.name} ({len(table)} rows)")
    for l in ([] if table else cands):
        r = Hh[:, l].double().mean(0) - Hb[:, l].double().mean(0)
        r = (r / r.norm()).float()
        hs = _ablation_hooks(model, r)
        try:
            _, lp_h = last_token_states(model, tok, val_h)
            _, lp_b = last_token_states(model, tok, val_b)
        finally:
            for h in hs:
                h.remove()
        mass = torch.logsumexp(lp_h[:, T], -1).mean().item()
        kl = (lp_b0.exp() * (lp_b0 - lp_b)).sum(-1).mean().item()
        table.append({"layer": l, "refusal_logmass_drop": mass0 - mass, "kl_dolly": kl, "passes_kl": kl < 0.1})
        logger.info(f"    lesion cand l={l}: drop {mass0 - mass:+.3f} KL {kl:.4f}")
    # amendment A12: kept = KL filter passed AND positive refusal log-mass drop (a lesion must reduce refusal);
    # none kept -> the registered fallback (max drop over all candidates, flag KL_FILTER_FAILED)
    ok = [t for t in table if t["passes_kl"] and t["refusal_logmass_drop"] > 0]
    pick = max(ok or table, key=lambda t: t["refusal_logmass_drop"])
    if not ok:
        Deviations.add(f"lesion_kl_filter_failed_{fk}", f"{fk}: no candidate passed KL<0.1 with a positive refusal drop (A12); max-drop candidate over all used",
                       "prereg'd fallback", "flag KL_FILTER_FAILED")
    l_abl = pick["layer"]
    r = Hh[:, l_abl].double().mean(0) - Hb[:, l_abl].double().mean(0)
    r = (r / r.norm()).numpy()
    np.savez(p, r=r, l_abl=l_abl, table=json.dumps(table))
    logger.info(f"  lesion {fk}: l_abl={l_abl} ({len(cands)} cands, {time.time() - t0:.0f}s)")
    return {"r": r, "l_abl": l_abl, "table": table, "cos_parent_axis": None, "kl_filter_failed": not ok,
            "baseline_refusal_logmass": mass0}


def apply_lesion(model, r: np.ndarray, alpha: float) -> None:
    """A13: the rank-one orthogonalisation is computed in float64 on CPU (then rounded to the model dtype), so the edited
    weights -- and the weight fingerprint asserted between generation and harvest -- do not depend on the device or
    on BLAS threading."""
    torch = torch_mod()
    rr = torch.tensor(r, dtype=torch.float64)
    with torch.no_grad():
        E = model.get_input_embeddings().weight
        assert E.device.type == "cpu", "lesion edit must run on CPU (A13)"
        Ef = E.data.double()
        E.data.copy_((Ef - alpha * (Ef @ rr)[:, None] * rr[None, :]).to(E.dtype))
        del Ef
        for b in blocks(model):
            for W in (b.self_attn.o_proj.weight, b.mlp.down_proj.weight):
                Wf = W.data.double()
                W.data.copy_((Wf - alpha * rr[:, None] * (rr[None, :] @ Wf)).to(W.dtype))
                del Wf


# ------------------------------------------------------------------------------------------------ int8 dynamic
def quantize_int8_dynamic(model):
    torch = torch_mod()
    from torch.ao.nn.quantized.dynamic import Linear as QLinear
    from torch.ao.quantization import per_channel_dynamic_qconfig
    n = 0
    for _name, mod in list(model.named_modules()):
        for cname, child in list(mod.named_children()):
            if isinstance(child, torch.nn.Linear) and not isinstance(child, QLinear):
                f = torch.nn.Linear(child.in_features, child.out_features, bias=child.bias is not None)
                with torch.no_grad():
                    f.weight.copy_(child.weight.detach().float())
                    if child.bias is not None:
                        f.bias.copy_(child.bias.detach().float())
                f.qconfig = per_channel_dynamic_qconfig
                setattr(mod, cname, QLinear.from_float(f))
                n += 1
                del f
    gc.collect()
    model.float()
    return n


def quantize_int8_weight_only(model) -> int:
    """int8 WEIGHT-ONLY round trip (W8A16): every nn.Linear weight (incl. lm_head, untied first) is quantised per output
    channel, symmetric absmax to int8 (scale = max|W_row|/127, round-half-even, clamp [-127,127]) and dequantised back
    to the model dtype; compute stays bf16. This mirrors what LLM.int8 preserves (vector-wise weight quantisation with
    outlier-safe activations); per-tensor dynamic ACTIVATION quantisation destroyed Qwen3-0.6B (first-token agreement
    6%, max |logit diff| 32.7 in the smoke test) and is recorded as a failed construction."""
    torch = torch_mod()
    untie_head(model)
    n = 0
    with torch.no_grad():
        for mod in model.modules():
            if isinstance(mod, torch.nn.Linear):
                W = mod.weight.data
                Wf = W.float()
                s = Wf.abs().amax(dim=1, keepdim=True).clamp_min(1e-12) / 127.0
                q = torch.clamp(torch.round(Wf / s), -127, 127)
                mod.weight.data.copy_((q * s).to(W.dtype))
                n += 1
    return n


# ------------------------------------------------------------------------------------------------ LoRA / DPO (A13: GPU)
LORA_RECIPE = {"r": 8, "lora_alpha": 16, "lora_dropout": 0.05, "target_modules": ["q_proj", "v_proj"], "steps": 150,
               "micro_batch": 4, "grad_accum": 2, "max_len": 384, "lr": 1e-4, "schedule": "cosine", "loss": "response tokens only"}
DPO_RECIPE = {"r": 8, "lora_alpha": 16, "lora_dropout": 0.05, "target_modules": ["q_proj", "v_proj"], "steps": 100,
              "batch": 4, "max_len": 384, "lr": 5e-5, "beta": 0.1, "n_pairs": 400,
              "pairs": "Dolly (side_sets.lora_rows, seeded SEED+1 shuffle, responses with >=2 sentences): chosen = reference "
                       "response; rejected = the same response with its sentence order shuffled and its second half dropped",
              "reference": "same model with the adapter disabled (peft disable_adapter)", "start": "the PARENT (not the lora arm)"}


def _encode_pr(tok, prompt_text: str, response: str, max_len: int):
    prompt = render(tok, prompt_text)
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    r_ids = tok(response + (tok.eos_token or ""), add_special_tokens=False)["input_ids"]
    ids = (p_ids + r_ids)[:max_len]
    lab = ([-100] * len(p_ids) + r_ids)[:max_len]
    return ids, lab


def _pad_batch(encs, pad_id, dev):
    torch = torch_mod()
    T = max(len(e[0]) for e in encs)
    ids = torch.tensor([e[0] + [pad_id] * (T - len(e[0])) for e in encs], device=dev)
    lab = torch.tensor([e[1] + [-100] * (T - len(e[1])) for e in encs], device=dev)
    att = torch.tensor([[1] * len(e[0]) + [0] * (T - len(e[0])) for e in encs], device=dev)
    return ids, lab, att


def _peft_on_device(model, recipe):
    torch = torch_mod()
    from peft import LoraConfig, get_peft_model
    dev = get_device()
    model.to(dev)
    model.config.use_cache = False
    if dev.type == "cuda":
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    cfg = LoraConfig(r=recipe["r"], lora_alpha=recipe["lora_alpha"], lora_dropout=recipe["lora_dropout"],
                     target_modules=recipe["target_modules"], task_type="CAUSAL_LM")
    torch.manual_seed(SEED)
    pm = get_peft_model(model, cfg)
    pm.train()
    return pm, dev


def _merge_on_cpu(fk: str, adir: Path):
    """Adapter merged into a FRESH CPU copy of the parent (device-independent weights, A13)."""
    base, _tok, _ = load_parent(fk)
    from peft import PeftModel
    pm = PeftModel.from_pretrained(base, str(adir))
    merged = pm.merge_and_unload()
    merged.eval()
    for p_ in merged.parameters():
        p_.requires_grad_(False)
    return merged


def train_lora(fk: str, model, tok, cap_s: float = 1200.0):
    torch = torch_mod()
    R = LORA_RECIPE
    adir = ADAPTERS / f"{fk}_lora"
    side = jload(ASSETS / "side_sets.json")
    rows = list(side["lora_rows"])
    rng = np.random.default_rng(SEED)
    rng.shuffle(rows)
    pm, dev = _peft_on_device(model, R)
    params = [p for p in pm.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=R["lr"], weight_decay=0.0)
    tok.padding_side = "right"
    losses, t_step = [], []
    k, step, planned = 0, 0, R["steps"]
    t0 = time.time()
    while step < planned:
        ts = time.time()
        lr_now = R["lr"] * 0.5 * (1 + math.cos(math.pi * step / max(planned, 1)))
        for g in opt.param_groups:
            g["lr"] = lr_now
        tot = 0.0
        for _ in range(R["grad_accum"]):
            chunk = [rows[(k + j) % len(rows)] for j in range(R["micro_batch"])]
            k += R["micro_batch"]
            ids, lab, att = _pad_batch([_encode_pr(tok, rw["prompt"], rw["response"], R["max_len"]) for rw in chunk],
                                       tok.pad_token_id, dev)
            out = pm(input_ids=ids, attention_mask=att, labels=lab)
            (out.loss / R["grad_accum"]).backward()
            tot += float(out.loss.item()) / R["grad_accum"]
        opt.step()
        opt.zero_grad(set_to_none=True)
        losses.append(tot)
        t_step.append(time.time() - ts)
        step += 1
        if step == 3 and np.mean(t_step) * planned > cap_s:
            planned = max(3, int(cap_s / np.mean(t_step)))
            Deviations.add(f"lora_steps_capped_{fk}", f"LoRA {fk}: {planned} steps instead of {R['steps']}",
                           "wall-clock cap", "cosine schedule re-spanned")
        if step % 25 == 0:
            logger.info(f"    lora {fk} step {step}/{planned} loss {losses[-1]:.3f} ({np.mean(t_step):.2f}s/step)")
    pm.save_pretrained(str(adir))
    info = {"recipe": R, "steps_planned": R["steps"], "steps_done": planned, "losses": losses,
            "loss_first5": float(np.mean(losses[:5])), "loss_last5": float(np.mean(losses[-5:])),
            "sec_per_step": float(np.mean(t_step)), "train_s": time.time() - t0, "device": str(dev),
            "adapter_dir": str(adir.relative_to(PRIVATE.parent))}
    jdump(info, EDITS / f"{fk}_lora_train.json")
    del pm, opt, model
    gc.collect()
    if dev.type == "cuda":
        torch.cuda.empty_cache()
    return _merge_on_cpu(fk, adir), info


def dpo_pairs() -> list[dict]:
    import re
    side = jload(ASSETS / "side_sets.json")
    rows = list(side["lora_rows"])
    rng = np.random.default_rng(SEED + 1)
    rng.shuffle(rows)
    out = []
    for rw in rows:
        sents = [x for x in re.split(r"(?<=[.!?])\s+", str(rw["response"]).strip()) if x.strip()]
        if len(sents) < 2:
            continue
        perm = list(rng.permutation(len(sents)))
        if perm == list(range(len(sents))):
            perm = perm[1:] + perm[:1]
        shuf = [sents[i] for i in perm]
        rej = " ".join(shuf[: max(1, len(shuf) // 2)])
        out.append({"prompt": rw["prompt"], "chosen": rw["response"], "rejected": rej})
        if len(out) == DPO_RECIPE["n_pairs"]:
            break
    return out


def _seq_logp(pm, ids, lab, att):
    torch = torch_mod()
    logits = pm(input_ids=ids, attention_mask=att).logits[:, :-1].float()
    tgt = lab[:, 1:]
    mask = tgt != -100
    lp = torch.log_softmax(logits, -1).gather(-1, tgt.clamp_min(0)[..., None]).squeeze(-1)
    return (lp * mask).sum(-1)


def train_dpo(fk: str, model, tok, cap_s: float = 1200.0):
    torch = torch_mod()
    import torch.nn.functional as F
    R = DPO_RECIPE
    adir = ADAPTERS / f"{fk}_dpo"
    pairs = dpo_pairs()
    pm, dev = _peft_on_device(model, R)
    params = [p for p in pm.parameters() if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=R["lr"], weight_decay=0.0)
    tok.padding_side = "right"
    losses, margins, t_step = [], [], []
    k, step, planned = 0, 0, R["steps"]
    t0 = time.time()
    while step < planned:
        ts = time.time()
        chunk = [pairs[(k + j) % len(pairs)] for j in range(R["batch"])]
        k += R["batch"]
        n = len(chunk)
        zs, lsum = [], 0.0
        for q in chunk:     # one (chosen, rejected) pair per micro-step: full-vocab logits of 8 x 384 do not fit the cap
            ids, lab, att = _pad_batch([_encode_pr(tok, q["prompt"], q["chosen"], R["max_len"]),
                                        _encode_pr(tok, q["prompt"], q["rejected"], R["max_len"])], tok.pad_token_id, dev)
            with torch.no_grad():
                with pm.disable_adapter():
                    ref = _seq_logp(pm, ids, lab, att)
            pol = _seq_logp(pm, ids, lab, att)
            z = R["beta"] * ((pol[0] - ref[0]) - (pol[1] - ref[1]))
            loss_i = -F.logsigmoid(z) / n
            loss_i.backward()
            zs.append(float(z.item()))
            lsum += float(loss_i.item())
            del pol, ref, loss_i
        opt.step()
        opt.zero_grad(set_to_none=True)
        losses.append(lsum)
        margins.append(float(np.mean(zs)))
        t_step.append(time.time() - ts)
        step += 1
        if step == 3 and np.mean(t_step) * planned > cap_s:
            planned = max(3, int(cap_s / np.mean(t_step)))
            Deviations.add(f"dpo_steps_capped_{fk}", f"DPO {fk}: {planned} steps instead of {R['steps']}", "wall-clock cap", "")
        if step % 25 == 0:
            logger.info(f"    dpo {fk} step {step}/{planned} loss {losses[-1]:.4f} margin {margins[-1]:+.4f} ({np.mean(t_step):.2f}s/step)")
    pm.save_pretrained(str(adir))
    info = {"recipe": R, "steps_done": planned, "n_pairs": len(pairs), "losses": losses, "reward_margins": margins,
            "loss_first5": float(np.mean(losses[:5])), "loss_last5": float(np.mean(losses[-5:])),
            "margin_last10_mean": float(np.mean(margins[-10:])), "margin_finite": bool(np.all(np.isfinite(margins))),
            "sec_per_step": float(np.mean(t_step)), "train_s": time.time() - t0, "device": str(dev),
            "adapter_dir": str(adir.relative_to(PRIVATE.parent))}
    jdump(info, EDITS / f"{fk}_dpo_train.json")
    del pm, opt, model
    gc.collect()
    if dev.type == "cuda":
        torch.cuda.empty_cache()
    return _merge_on_cpu(fk, adir), info


# ------------------------------------------------------------------------------------------------ build
def build(fk: str, variant: str, allow_train: bool = True):
    """-> (model, tok, render_fn, info). Weights are constructed on CPU (edits in float64 / elementwise; adapters merged
    on CPU) and only then moved to the compute device (A13), so generation and harvest rebuild bit-identical weights.
    info carries the recipe details and the weight fingerprint."""
    torch = torch_mod()
    torch.manual_seed(SEED)
    dev = get_device()
    info = {"fk": fk, "variant": variant, "repo": repo_for(fk, variant), "utc": utc_now(), "device": str(dev)}
    if fk == "HG":      # A13: a harvested checkpoint, loaded as-is (bf16, stock template, no system prompt)
        model, tok, local = load_parent(fk, repo=repo_for(fk, variant))
        info["local_snapshot"] = local
        model.to(dev)
        model.eval()
        info["weight_fingerprint"] = weight_fingerprint(model)
        info["weight_sha_full"] = full_tensor_sha(model)
        info["dtype"] = str(next(model.parameters()).dtype)
        return model, tok, make_render_fn(tok, "ref"), info
    if variant == "fp32":
        model, tok, local = load_parent(fk, dtype="float32")
    elif variant == "fp16":
        model, tok, local = load_parent(fk, dtype="float16")
    elif variant == "int8bnb":
        if dev.type != "cuda":
            raise RuntimeError("int8bnb needs CUDA (bitsandbytes LLM.int8)")
        model, tok, local = load_parent(fk, int8_bnb=True)
    elif variant == "attn_eager":
        model, tok, local = load_parent(fk, attn="eager")
    else:
        model, tok, local = load_parent(fk)
    info["local_snapshot"] = local
    # caches (h_bar, lesion direction) are computed ONCE on a separate fresh parent instance: an output_hidden_states
    # forward makes transformers 5 attach its (pass-through) output-recorder hooks, and the generation model must stay
    # hook-free (asserted in gen_variants)
    if variant in ("wu05", "wu20") and not (EDITS / f"{fk}_hbar.npz").exists():
        pm, _t, _ = load_parent(fk)
        pm.to(dev)
        hbar_and_T(fk, pm, tok)
        del pm
        gc.collect()
    if variant in ("a05", "a10") and not (EDITS / f"{fk}_lesion.npz").exists():
        pm, _t, _ = load_parent(fk)
        pm.to(dev)
        fit_lesion(fk, pm, tok)
        del pm
        gc.collect()
    if variant in ("ref", "sysprompt", "cautious", "fp32", "fp16", "attn_eager", "int8bnb"):
        pass
    elif variant == "resave":
        d = PRIVATE / "resave" / fk
        sha_before = full_tensor_sha(model)
        model.save_pretrained(str(d), safe_serialization=True)
        tok.save_pretrained(str(d))
        del model
        gc.collect()
        from transformers import AutoModelForCausalLM
        model = AutoModelForCausalLM.from_pretrained(str(d), dtype=torch.bfloat16, low_cpu_mem_usage=True,
                                                     attn_implementation="sdpa")
        model.eval()
        info["tensor_sha_equal"] = full_tensor_sha(model) == sha_before
        if not info["tensor_sha_equal"]:
            raise RuntimeError("resave: tensor sha changed")
    elif variant == "int8dyn":
        info["n_linear_quantized"] = quantize_int8_dynamic(model)
    elif variant == "int8wo":
        info["n_linear_quantized"] = quantize_int8_weight_only(model)
        info["was_tied_untied"] = True
    elif variant in ("wu05", "wu20"):
        info.update(apply_wu_edit(fk, model, tok, {"wu05": 0.5, "wu20": 2.0}[variant]))
    elif variant in ("a05", "a10"):
        les = fit_lesion(fk, model, tok)
        apply_lesion(model, les["r"], {"a05": 0.5, "a10": 1.0}[variant])
        info.update({"l_abl": les["l_abl"], "alpha": {"a05": 0.5, "a10": 1.0}[variant]})
    elif variant in ("lora", "dpo"):
        adir = ADAPTERS / f"{fk}_{variant}"
        tj = EDITS / f"{fk}_{variant}_train.json"
        if (adir / "adapter_config.json").exists():
            del model
            gc.collect()
            model = _merge_on_cpu(fk, adir)
            info[variant] = jload(tj) if tj.exists() else {}
        elif allow_train:
            model, tinfo = (train_lora if variant == "lora" else train_dpo)(fk, model, tok)
            info[variant] = tinfo
        else:
            raise RuntimeError(f"{variant} adapter missing and training not allowed")
    else:
        raise ValueError(f"unknown variant {variant}")
    if variant != "int8bnb":
        model.to(dev)
    model.eval()
    info["weight_fingerprint"] = weight_fingerprint(model)
    info["weight_sha_full"] = full_tensor_sha(model)      # A13: the 6-tensor fingerprint cannot see q/v-only merges
    info["dtype"] = str(next(model.parameters()).dtype) if variant != "int8bnb" else "int8 (bnb LLM.int8) / fp16 compute"
    return model, tok, make_render_fn(tok, variant), info
