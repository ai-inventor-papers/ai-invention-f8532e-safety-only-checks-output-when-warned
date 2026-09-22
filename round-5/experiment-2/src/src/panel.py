"""STAGE A -- the seeded held-out PANEL RULE, frozen and hash-committed before any Hub rank.

    python src/panel.py rule    -> results/panel_rule.json         (chain record 1)
    python src/panel.py draw    -> results/panel.json, results/panel_rejects.json,
                                   results/hf_probe_pool.jsonl     (chain record 2)

Mechanism reused verbatim from prior_session_confirm_panel/src/panel.py (probe / eligibility /
previously_loaded / sha256 rank key); the SEED and the SIZE CAP are this artifact's.
NOTHING here scores a candidate.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ASSETS, H1, P, RESULTS, RUN, SEED, SHARED_HUB, chain_append,  # noqa: E402
                    deviation, hash_rank_key, jdump, jload, setup_logging, sha256_file, utc_now)
from loguru import logger  # noqa: E402

# ---- the binding constraints -------------------------------------------------------------
SIZE_CAP_PARAMS = 4.0e9          # direction cap
BF16_GB_CAP = 6.6                # 7.5 GB VRAM lease minus activation/hook headroom
BF16_GB_RESERVE = 8.5            # 6.6..8.5 GB -> RESERVE list, run last under accelerate offload
MAX_CHILDREN_PER_PARENT = 3
TARGET_N = 20
TARGET_FAMILIES = 6
TARGET_LINEAGES = 3
TARGET_EDITED = 2

QUANT_OR_CONVERTED = re.compile(r"gguf|mlx|[0-9]+bit|q[0-9]_|w4a16|awq|gptq|exl2|onnx|-int[48]|fp8|bnb",
                                re.I)

# (i) the direction's hand-written exclusion list.
EXCLUDED_FAMILIES_DIRECTION = ["qwen3", "qwen2.5", "qwen2", "smollm2", "smollm3", "tinyllama", "phi",
                               "granite", "stablelm", "olmo2", "llama3.2", "falcon3", "amd-olmo",
                               "lfm2"]
# repo-id -> family patterns, used both to derive the families of the LOADED checkpoints and to
# classify a pool repo.  Family = pretraining lineage (org + pretraining run), NOT architecture.
FAMILY_PATTERNS = [
    (r"qwen3", "qwen3"), (r"qwen2\.5", "qwen2.5"), (r"qwen2", "qwen2"), (r"smollm2", "smollm2"),
    (r"smollm3", "smollm3"), (r"tinyllama", "tinyllama"), (r"phi-", "phi"), (r"granite", "granite"),
    (r"stablelm", "stablelm"), (r"olmo-2", "olmo2"), (r"amd-olmo", "amd-olmo"),
    (r"llama-3\.2", "llama3.2"), (r"falcon-h1", "falcon-h1"), (r"falcon3", "falcon3"),
    (r"lfm2", "lfm2"),
    (r"bloom", "bloom"), (r"gemma-?3", "gemma"), (r"gemma-?2", "gemma"), (r"gemma", "gemma"),
    (r"pythia", "pythia"), (r"danube", "h2o-danube"), (r"hunyuan", "hunyuan"),
    (r"ernie", "ernie"), (r"zamba", "zamba2"), (r"exaone", "exaone"), (r"minicpm", "minicpm"),
    (r"internlm", "internlm"), (r"index-1", "index"), (r"pleias", "pleias"),
    (r"deepseek-coder", "deepseek-coder"), (r"opt-", "opt"), (r"gpt-neo", "gpt-neo"),
]
# base_model declarations that betray an excluded pretraining lineage however the repo is branded
EXCLUDED_BASE_RE = re.compile(r"qwen\s*[23](\.\d)?|smollm|tinyllama|phi-[34]|granite|stablelm|"
                              r"olmo-2|amd-olmo|llama-3\.2|falcon3|lfm2", re.I)

# Repos whose weights a previous session of THIS run pulled (the 3 generation runs in P).
TOUCHED_UPSTREAM = ["bigscience/bloom-1b1", "bigscience/bloomz-1b1", "unsloth/gemma-3-1b-pt"]
# Present in D2's paired_lineage_registry as metadata + card text only; never downloaded.
REGISTRY_ONLY_FAMILIES = ["gemma", "minicpm"]

# ------------------------------------------------------------------- THE POOL
# Verified live on 2026-09-21 by the planner; re-probed here at the raised 4B cap.
STAGE_LINEAGES = [
    {"unit": "LIN_bloom_1b1", "family": "bloom",
     "members": [("bigscience/bloom-1b1", "base"), ("bigscience/bloomz-1b1", "sft")]},
    {"unit": "LIN_bloom_1b7", "family": "bloom",
     "members": [("bigscience/bloom-1b7", "base"), ("bigscience/bloomz-1b7", "sft")]},
    {"unit": "LIN_bloom_560m", "family": "bloom",
     "members": [("bigscience/bloom-560m", "base"), ("bigscience/bloomz-560m", "sft")]},
    {"unit": "LIN_bloom_3b", "family": "bloom",
     "members": [("bigscience/bloom-3b", "base"), ("bigscience/bloomz-3b", "sft")]},
    {"unit": "LIN_gemma3_1b", "family": "gemma", "parent_named": "google/gemma-3-1b (GATED original)",
     "members": [("unsloth/gemma-3-1b-pt", "base"), ("unsloth/gemma-3-1b-it", "sft")]},
    {"unit": "LIN_gemma3_270m", "family": "gemma",
     "members": [("unsloth/gemma-3-270m", "base"), ("unsloth/gemma-3-270m-it", "sft")]},
    {"unit": "LIN_gemma3_4b", "family": "gemma",
     "members": [("unsloth/gemma-3-4b-pt", "base"), ("unsloth/gemma-3-4b-it", "sft")]},
    {"unit": "LIN_danube3_500m", "family": "h2o-danube",
     "members": [("h2oai/h2o-danube3-500m-base", "base"), ("h2oai/h2o-danube3-500m-chat", "sft")]},
    {"unit": "LIN_danube3_4b", "family": "h2o-danube",
     "members": [("h2oai/h2o-danube3-4b-base", "base"), ("h2oai/h2o-danube3-4b-chat", "sft")]},
    {"unit": "LIN_hunyuan_05b", "family": "hunyuan",
     "members": [("tencent/Hunyuan-0.5B-Pretrain", "base"), ("tencent/Hunyuan-0.5B-Instruct", "sft")]},
    {"unit": "LIN_hunyuan_18b", "family": "hunyuan",
     "members": [("tencent/Hunyuan-1.8B-Pretrain", "base"), ("tencent/Hunyuan-1.8B-Instruct", "sft")]},
    {"unit": "LIN_ernie45_03b", "family": "ernie",
     "members": [("baidu/ERNIE-4.5-0.3B-Base-PT", "base"), ("baidu/ERNIE-4.5-0.3B-PT", "sft")]},
    {"unit": "LIN_zamba2_12b", "family": "zamba2",
     "members": [("Zyphra/Zamba2-1.2B", "base"), ("Zyphra/Zamba2-1.2B-instruct", "sft")]},
    {"unit": "LIN_falconh1_05b", "family": "falcon-h1", "flag": "falcon_h1_vs_falcon3_boundary",
     "members": [("tiiuae/Falcon-H1-0.5B-Base", "base"), ("tiiuae/Falcon-H1-0.5B-Instruct", "sft")]},
    {"unit": "LIN_falconh1_15b", "family": "falcon-h1", "flag": "falcon_h1_vs_falcon3_boundary",
     "members": [("tiiuae/Falcon-H1-1.5B-Base", "base"), ("tiiuae/Falcon-H1-1.5B-Instruct", "sft")]},
    {"unit": "LIN_dscoder_13b", "family": "deepseek-coder",
     "members": [("deepseek-ai/deepseek-coder-1.3b-base", "base"),
                 ("deepseek-ai/deepseek-coder-1.3b-instruct", "sft")]},
    {"unit": "LIN_internlm25_18b", "family": "internlm",
     "members": [("internlm/internlm2_5-1_8b", "base"), ("internlm/internlm2_5-1_8b-chat", "sft")]},
]
EDITED_PAIRS = [
    {"unit": "PAIR_gemma3_1b", "family": "gemma", "parent": "unsloth/gemma-3-1b-it",
     "children": ["mlabonne/gemma-3-1b-it-abliterated-v2", "lunahr/gemma-3-1b-it-abliterated",
                  "mlabonne/gemma-3-1b-it-abliterated", "prithivMLmods/gemma-3-1b-it-abliterated",
                  "DavidAU/gemma-3-1b-it-heretic-extreme-uncensored-abliterated",
                  "huihui-ai/gemma-3-1b-it-abliterated"]},
    {"unit": "PAIR_gemma3_270m", "family": "gemma", "parent": "unsloth/gemma-3-270m-it",
     "children": ["huihui-ai/Huihui-gemma-3-270m-it-abliterated"]},
    {"unit": "PAIR_falconh1_05b", "family": "falcon-h1", "parent": "tiiuae/Falcon-H1-0.5B-Instruct",
     "children": ["megabytes/Falcon-H1-0.5B-Instruct-heretic"]},
    {"unit": "PAIR_hunyuan_05b", "family": "hunyuan", "parent": "tencent/Hunyuan-0.5B-Instruct",
     "children": ["hereticness/heretic_Hunyuan-0.5B-Instruct"]},
    {"unit": "PAIR_ernie45_03b", "family": "ernie", "parent": "baidu/ERNIE-4.5-0.3B-PT",
     "children": ["AiAsistent/ERNIE-4.5-0.3B-PT-heretic"]},
    {"unit": "PAIR_exaone4_12b", "family": "exaone", "parent": "LGAI-EXAONE/EXAONE-4.0-1.2B",
     "children": ["RichardErkhov/EXAONE-4.0-1.2B-heretic",
                  "huihui-ai/Huihui-EXAONE-4.0-1.2B-abliterated"]},
]
SINGLES = [
    ("EleutherAI/pythia-410m", "pythia", "base"), ("EleutherAI/pythia-1b", "pythia", "base"),
    ("EleutherAI/pythia-1.4b", "pythia", "base"), ("EleutherAI/pythia-2.8b", "pythia", "base"),
    ("LGAI-EXAONE/EXAONE-4.0-1.2B", "exaone", "sft"),
    ("PleIAs/Pleias-1.2b-Preview", "pleias", "base"),
    ("PleIAs/Pleias-3b-Preview", "pleias", "base"),
    ("Zyphra/Zamba2-2.7B", "zamba2", "base"),
    ("Zyphra/Zamba2-2.7B-instruct", "zamba2", "sft"),
    ("tencent/Hunyuan-4B-Instruct", "hunyuan", "sft"),
    ("baidu/ERNIE-4.5-0.3B-PT", "ernie", "sft"),
    ("h2oai/h2o-danube3-4b-chat", "h2o-danube", "sft"),
    ("IndexTeam/Index-1.9B-Chat", "index", "sft"),
    ("openbmb/MiniCPM4-0.5B", "minicpm", "sft"),
    ("facebook/opt-1.3b", "opt", "base"),
    ("EleutherAI/gpt-neo-1.3B", "gpt-neo", "base"),
]

RULE_TEXT_TMPL = """SELECTION RULE (frozen and hash-committed BEFORE any repo is ranked or probed for selection).

seed = '{seed}'.  Rank key of a repo r = sha256(seed + '|' + r).hexdigest(); ASCENDING = draw order.

THREE GRADES OF PRIOR EXPOSURE, and this rule names which it excludes:
  (1) LOADED  -- weights pulled and run by an earlier artifact of this run: the {n_loaded} repo ids
      recovered mechanically from the shared HF hub cache, from iteration-4 experiment-1's harvest tag
      list and from the prior_session_confirm_panel generation runs.  EXCLUDED, and so are their
      FAMILIES.  The three TOUCHED_UPSTREAM repos {touched} had weights pulled by a prior session of
      this run but no behaviour ever read out, so their repo ids are excluded while their families
      are NOT burned.
  (2) REGISTRY-ONLY -- present in iteration-2's paired_lineage_registry as metadata and card text with
      zero safetensors ever downloaded ({registry_only}).  ADMISSIBLE, but every such checkpoint
      carries the flag registry_metadata_only_prior_exposure and is NOT the strongest evidence.
  (3) NEVER SEEN -- preferred.  The achieved panel reports its split across these three grades.

EXCLUDED_FAMILIES = direction list {excl_direction}
  UNION the family of every LOADED repo (derived mechanically, asserted to be a subset of the union).
  A repo whose declared base_model matches {excl_base} is EXCLUDED however it is branded
  (this catches Sailor2, DeepSeek-R1-Distill-Qwen, SmallThinker and every re-brand of an excluded base).
  FAMILY BOUNDARY CALLS, made explicitly: Falcon-H1 is a DIFFERENT architecture and pretraining lineage
  from the excluded Falcon3 -- it is ADMITTED and flagged falcon_h1_vs_falcon3_boundary.
  bloom+bloomz = one family 'bloom'; gemma-2+gemma-3 = one family 'gemma'.

ELIGIBILITY PREDICATE (all must hold; verified LIVE, unauthenticated, at draw time):
  (e1) not gated, not private, not disabled (an unauthenticated GET of the model API and of
       config.json must both succeed; never authenticate);
  (e2) ships *.safetensors in HF-transformers layout; a .bin-only repo is INELIGIBLE;
  (e3) not quantised: no quantization_config in config.json and the repo id / tags carry no
       gguf|awq|gptq|bnb|int4|int8|mlx|onnx|exl2|fp8 marker;
  (e4) config.json resolves 'architectures';
  (e5) parameters <= {cap:.2e} AND bf16 safetensors bytes <= {bf16cap} GB (the 7.5 GB VRAM lease is
       the binding constraint).  Repos in ({bf16cap}, {reserve}] GB go on a RESERVE list, run LAST under
       accelerate max_memory offload, or dropped with a logged deviation;
  (e6) licence permits research use (RAIL use-restrictions are recorded, not disqualifying);
  (e7) trust_remote_code is allowed ONLY if a smoke load succeeds, and the flag is recorded per
       checkpoint;
  (e8) an instruct/edited-child role needs a chat template, except role 'sft_noformat' (bloomz is an
       xP3 multitask fine-tune with no chat format -> plain request+newline prompt, recorded per row).

UNITS: a stage lineage is eligible iff ALL of its members are; an edited pair is eligible iff its
  parent is and at least one child is; at most {maxchild} children per parent.

DRAW ORDER (ties -> the smaller download):
  (1) multi-stage lineages, ranked by the rank key of their BASE repo.  A 2-stage base+instruct pair
      COUNTS AS A LINEAGE (the only verified 3-stage chain on the Hub under the cap, MiniCPM-2B
      base->sft->dpo, is .bin-only AND trust_remote_code); the third lineage is topped up from the
      Part-B in-house arms, where parent -> LoRA -> DPO is a genuine multi-stage lineage built here
      with the recipe held fixed.
  (2) community-edited children of drawn parents, ranked by their own rank key;
  (3) one instruct arm per remaining NEW family, in rank-key order, until >= {tfam} families;
  (4) fill to >= {tn} checkpoints by global rank-key order.

QUOTAS: >= {tn} checkpoints, >= {tfam} never-loaded families, >= {tlin} multi-stage lineages,
  >= {ted} community-edited children of panel parents, plus the Part-B in-house family.

TIME RULE: after each checkpoint, re-estimate per-checkpoint wall clock from MEASURED timings and stop
  admitting new checkpoints when the projected finish exceeds the deadline minus 45 min of reserve.
  Post-draw exclusions are applied at RUNTIME through results/panel_amend.json; panel.json is never
  edited after its commit.

EVERY rejected candidate is recorded with its reason in results/panel_rejects.json.  The reject table
is part of the deliverable.
"""


# ------------------------------------------------------------------- live probe (from P/src/panel.py)
def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "aii-heldout-panel"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"__error__": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"__error__": repr(e)[:200]}


def _raw(repo: str, fn: str):
    req = urllib.request.Request(f"https://huggingface.co/{repo}/raw/main/{fn}",
                                 headers={"User-Agent": "aii-heldout-panel"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.read().decode()
    except Exception:  # noqa: BLE001
        return None


def probe(repo: str) -> dict:
    m = _get(f"https://huggingface.co/api/models/{repo}?blobs=true")
    if "__error__" in m:
        return {"repo": repo, "api_error": m["__error__"]}
    sib = m.get("siblings", [])
    st = [s for s in sib if s["rfilename"].endswith(".safetensors")]
    nbin = len([s for s in sib if s["rfilename"].endswith(".bin")])
    st_bytes = sum(int(s.get("size") or 0) for s in st)
    params = (m.get("safetensors") or {}).get("parameters") or {}
    tot = sum(params.values()) if params else 0
    f32 = sum(v for k, v in params.items() if k.upper() == "F32")
    bf16_bytes = st_bytes / 2 if (tot and f32 / tot > 0.5) else st_bytes
    n_params = tot if tot else bf16_bytes / 2
    cj = {}
    raw = _raw(repo, "config.json")
    if raw:
        try:
            cj = json.loads(raw)
        except json.JSONDecodeError:
            cj = {}
    tc = _raw(repo, "tokenizer_config.json")
    has_ct = False
    if tc:
        try:
            has_ct = bool(json.loads(tc).get("chat_template"))
        except json.JSONDecodeError:
            pass
    has_ct = has_ct or any(s["rfilename"] in ("chat_template.jinja", "chat_template.json") for s in sib)
    card = m.get("cardData") or {}
    bm = card.get("base_model")
    if isinstance(bm, list):
        bm = ", ".join(str(x) for x in bm)
    return {"repo": repo, "sha": m.get("sha"), "gated": m.get("gated"), "private": m.get("private"),
            "disabled": m.get("disabled"), "st_bytes": st_bytes, "n_safetensors": len(st),
            "n_bin": nbin, "params_by_dtype": params, "params_total": n_params,
            "bf16_bytes": bf16_bytes, "bf16_gb": round(bf16_bytes / 1e9, 3),
            "config_ok": bool(raw), "architectures": cj.get("architectures"),
            "model_type": cj.get("model_type"), "trust_remote_code": bool(cj.get("auto_map")),
            "quantization_config": bool(cj.get("quantization_config")),
            "n_layers": cj.get("num_hidden_layers") or cj.get("n_layer"),
            "hidden_size": cj.get("hidden_size") or cj.get("n_embed"),
            "vocab_size": cj.get("vocab_size"),
            "tie_word_embeddings": cj.get("tie_word_embeddings"),
            "has_chat_template": has_ct, "declared_base_model": bm,
            "license": card.get("license"), "lastModified": m.get("lastModified"),
            "downloads": m.get("downloads"), "library_name": m.get("library_name"),
            "tags": (m.get("tags") or [])[:30]}


def family_of(repo: str) -> str:
    r = repo.lower()
    for pat, fam in FAMILY_PATTERNS:
        if re.search(pat, r):
            return fam
    return "UNMAPPED:" + repo


def previously_loaded() -> tuple[set[str], list[str]]:
    """Every repo id whose WEIGHTS an earlier artifact of this run pulled.  Sources are logged."""
    seen: set[str] = set()
    srcs: list[str] = []
    snap = RESULTS / "PRE_EXISTING_HUB_SNAPSHOT.txt"
    if snap.exists():
        for ln in snap.read_text().splitlines():
            if ln.strip():
                seen.add(ln.strip())
        srcs.append(f"PRE_EXISTING_HUB_SNAPSHOT.txt ({len(seen)} ids, captured before any download)")
    if SHARED_HUB.exists():
        n0 = len(seen)
        for p in SHARED_HUB.iterdir():
            if p.name.startswith("models--"):
                seen.add(p.name[len("models--"):].replace("--", "/", 1))
        srcs.append(f"shared hub cache (+{len(seen) - n0})")
    h1h = H1 / "harvest"
    if h1h.exists():
        n0 = len(seen)
        for p in sorted(h1h.iterdir()):
            if not p.is_dir():
                continue
            mj = p / "meta.json"
            if mj.exists():
                try:
                    r = json.loads(mj.read_text()).get("repo")
                    if r:
                        seen.add(r)
                except json.JSONDecodeError:
                    pass
            if p.name.startswith("HG__"):
                seen.add(p.name[4:].replace("--", "/", 1))
        srcs.append(f"iter4 exp1 harvest tags (+{len(seen) - n0})")
    for pj in (P / "results/panel.json", P / "results/run_list.json"):
        if pj.exists():
            try:
                txt = pj.read_text()
                for m in re.finditer(r'"repo(?:_id)?"\s*:\s*"([^"]+)"', txt):
                    pass  # panel.json lists CANDIDATES, not loads -> not added here
            except OSError:
                pass
    for r in TOUCHED_UPSTREAM:
        seen.add(r)
    srcs.append(f"TOUCHED_UPSTREAM (+{len(TOUCHED_UPSTREAM)})")
    return seen, srcs


def excluded_families(loaded: set[str]) -> tuple[list[str], list[str]]:
    derived = sorted({family_of(r) for r in loaded})
    derived = [f for f in derived if not f.startswith("UNMAPPED:")]
    # the TOUCHED_UPSTREAM families are NOT burned (no behaviour was ever read out)
    touched_fams = {family_of(r) for r in TOUCHED_UPSTREAM}
    derived = [f for f in derived if f not in touched_fams]
    surprises = [f for f in derived if f not in EXCLUDED_FAMILIES_DIRECTION]
    return sorted(set(EXCLUDED_FAMILIES_DIRECTION) | set(derived)), surprises


def eligibility(pr: dict, role: str, fam: str, loaded: set[str], excl: list[str]) -> str | None:
    if "api_error" in pr:
        return f"hub api {pr['api_error']} (gated/private/absent; never authenticate)"
    if pr["gated"] not in (False, None, "false"):
        return f"gated={pr['gated']}"
    if pr.get("private") or pr.get("disabled"):
        return "private/disabled"
    if not pr.get("config_ok"):
        return "unauthenticated GET of config.json failed"
    if QUANT_OR_CONVERTED.search(pr["repo"]) or any(QUANT_OR_CONVERTED.search(t) for t in pr.get("tags") or []):
        return "quantised/converted format marker in repo id or tags"
    if pr.get("quantization_config"):
        return "config.json carries quantization_config"
    if pr["n_safetensors"] == 0:
        return f"no *.safetensors (.bin files: {pr.get('n_bin')}) -- INELIGIBLE under (e2)"
    if not pr.get("architectures"):
        return "config.json has no architectures (adapter-only / not a full checkpoint)"
    if pr["params_total"] > SIZE_CAP_PARAMS:
        return f"params {pr['params_total'] / 1e9:.2f}B > cap {SIZE_CAP_PARAMS / 1e9:.2f}B"
    if pr["bf16_gb"] > BF16_GB_RESERVE:
        return f"bf16 {pr['bf16_gb']} GB > reserve ceiling {BF16_GB_RESERVE} GB"
    bm = pr.get("declared_base_model") or ""
    if bm and EXCLUDED_BASE_RE.search(bm):
        return f"declared base_model '{bm[:60]}' is an excluded pretraining lineage"
    if fam in excl:
        return f"family '{fam}' is LOADED by this run / on the direction exclusion list"
    if pr["repo"] in loaded:
        return "repo id LOADED by an earlier artifact of this run"
    if role in ("sft", "edited_child") and not pr["has_chat_template"]:
        if "bloomz" in pr["repo"].lower():
            return None            # role is re-labelled sft_noformat by the caller
        return "instruct-role checkpoint ships no chat template"
    return None


# ------------------------------------------------------------------- phases
def do_rule() -> Path:
    loaded, srcs = previously_loaded()
    excl, surprises = excluded_families(loaded)
    if surprises:
        deviation("exclusion_list_superset_violated",
                  f"families derived from LOADED repos but absent from the hand-written direction "
                  f"list: {surprises} -- the union is used", "panel_rule")
    rule_text = RULE_TEXT_TMPL.format(
        seed=SEED, n_loaded=len(loaded), touched=TOUCHED_UPSTREAM,
        registry_only=REGISTRY_ONLY_FAMILIES, excl_direction=EXCLUDED_FAMILIES_DIRECTION,
        excl_base=EXCLUDED_BASE_RE.pattern, cap=SIZE_CAP_PARAMS, bf16cap=BF16_GB_CAP,
        reserve=BF16_GB_RESERVE, maxchild=MAX_CHILDREN_PER_PARENT, tn=TARGET_N,
        tfam=TARGET_FAMILIES, tlin=TARGET_LINEAGES, ted=TARGET_EDITED)
    pool = {"stage_lineages": STAGE_LINEAGES, "edited_pairs": EDITED_PAIRS, "singles": SINGLES}
    obj = {"utc": utc_now(), "seed": SEED, "rule_text": rule_text,
           "rank_key": "sha256(seed + '|' + repo_id).hexdigest(), ascending",
           "size_cap_params": SIZE_CAP_PARAMS, "bf16_gb_cap": BF16_GB_CAP,
           "bf16_gb_reserve_ceiling": BF16_GB_RESERVE,
           "max_children_per_parent": MAX_CHILDREN_PER_PARENT,
           "quotas": {"n_checkpoints": TARGET_N, "families": TARGET_FAMILIES,
                      "multi_stage_lineages": TARGET_LINEAGES, "edited_children": TARGET_EDITED,
                      "inhouse_family": 1},
           "excluded_families": excl, "excluded_families_direction": EXCLUDED_FAMILIES_DIRECTION,
           "excluded_families_derived_surprises": surprises,
           "excluded_base_model_regex": EXCLUDED_BASE_RE.pattern,
           "prior_exposure_grades": {
               "LOADED": sorted(loaded), "LOADED_sources": srcs,
               "TOUCHED_UPSTREAM": TOUCHED_UPSTREAM,
               "REGISTRY_ONLY_families": REGISTRY_ONLY_FAMILIES},
           "pool": pool,
           "known_ineligibilities_not_relitigated": [
               "google/gemma-* is gated (manual) -- the ungated unsloth mirrors are used instead",
               "facebook/MobileLLM-* gated",
               "nvidia/Nemotron-Mini-4B-Instruct, openbmb/MiniCPM-2B-*/MiniCPM3-4B, "
               "IndexTeam/Index-1.9B-Chat, internlm/internlm2_5-1_8b are .bin-only",
               "openbmb/MiniCPM4-0.5B fails under transformers 5.x (remote code imports the removed "
               "is_torch_fx_available)",
               "MiniCPM-1B .bin-only; TinyLlama missing shards; huihui-ai children of Llama/Falcon3 401"],
           "pool_size": (sum(len(u["members"]) for u in STAGE_LINEAGES)
                         + sum(1 + len(u["children"]) for u in EDITED_PAIRS) + len(SINGLES))}
    p = jdump(RESULTS / "panel_rule.json", obj)
    rec = chain_append("panel_rule_frozen", p, note="STAGE A: rule frozen BEFORE any Hub selection")
    logger.info(f"panel_rule.json committed  sha={rec['payload_sha256'][:16]}  "
                f"pool={obj['pool_size']}  excluded_families={len(excl)}")
    return p


def do_draw() -> Path:
    rule = jload(RESULTS / "panel_rule.json")
    assert (RESULTS / "panel_rule.json").exists(), "rule must be frozen first"
    ch = [r for r in jload_chain() if r["event"] == "panel_rule_frozen"]
    if not ch:
        raise RuntimeError("panel_rule_frozen is not in the chain -- refusing to draw")
    if ch[0]["payload_sha256"] != sha256_file(RESULTS / "panel_rule.json"):
        raise RuntimeError("panel_rule.json changed after its commit -- refusing to draw")

    loaded = set(rule["prior_exposure_grades"]["LOADED"])
    excl = rule["excluded_families"]

    todo: list[tuple[str, str, str, str]] = []     # (repo, family, role, unit)
    for u in STAGE_LINEAGES:
        for repo, role in u["members"]:
            todo.append((repo, u["family"], role, u["unit"]))
    for u in EDITED_PAIRS:
        todo.append((u["parent"], u["family"], "sft", u["unit"]))
        for c in u["children"]:
            todo.append((c, u["family"], "edited_child", u["unit"]))
    for repo, fam, role in SINGLES:
        todo.append((repo, fam, role, "SINGLE"))
    seen_repo: dict[str, tuple] = {}
    for t in todo:
        seen_repo.setdefault(t[0], t)
    todo = list(seen_repo.values())
    logger.info(f"probing {len(todo)} pool repos live (unauthenticated)")

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex:
        probes = list(ex.map(lambda t: probe(t[0]), todo))

    pool_path = RESULTS / "hf_probe_pool.jsonl"
    with open(pool_path, "w") as f:
        for pr in probes:
            f.write(json.dumps(pr) + "\n")

    rows: list[dict] = []
    rejects: list[dict] = []
    for (repo, fam, role, unit), pr in zip(todo, probes):
        reason = eligibility(pr, role, fam, loaded, excl)
        eff_role = role
        if role == "sft" and not pr.get("has_chat_template") and "bloomz" in repo.lower():
            eff_role = "sft_noformat"
        rec = {"repo": repo, "family": fam, "role": eff_role, "unit": unit,
               "rank_key": hash_rank_key(repo),
               "bf16_gb": pr.get("bf16_gb"), "params_total": pr.get("params_total"),
               "n_layers": pr.get("n_layers"), "hidden_size": pr.get("hidden_size"),
               "tie_word_embeddings": pr.get("tie_word_embeddings"),
               "trust_remote_code": pr.get("trust_remote_code"),
               "has_chat_template": pr.get("has_chat_template"), "revision_sha": pr.get("sha"),
               "license": pr.get("license"), "declared_base_model": pr.get("declared_base_model"),
               "architectures": pr.get("architectures"), "model_type": pr.get("model_type"),
               "reserve": bool(pr.get("bf16_gb") and pr["bf16_gb"] > BF16_GB_CAP),
               "prior_exposure": ("TOUCHED_UPSTREAM" if repo in TOUCHED_UPSTREAM else
                                  ("REGISTRY_ONLY" if fam in REGISTRY_ONLY_FAMILIES else "NEVER_SEEN")),
               "flags": []}
        if fam in REGISTRY_ONLY_FAMILIES:
            rec["flags"].append("registry_metadata_only_prior_exposure")
        if fam == "falcon-h1":
            rec["flags"].append("falcon_h1_vs_falcon3_boundary")
        if repo in TOUCHED_UPSTREAM:
            rec["flags"].append("TOUCHED_UPSTREAM_weights_pulled_no_behaviour_read")
        if reason is None:
            rows.append(rec)
        else:
            rejects.append({**rec, "reject_reason": reason})

    by_repo = {r["repo"]: r for r in rows}

    # ---- draw, in the committed order
    drawn: list[dict] = []
    taken: set[str] = set()

    def take(r: dict, why: str) -> None:
        if r["repo"] in taken:
            return
        taken.add(r["repo"])
        drawn.append({**r, "draw_reason": why, "draw_index": len(drawn)})

    lin_ok = [u for u in STAGE_LINEAGES
              if all(m[0] in by_repo for m in u["members"])]
    lin_ok.sort(key=lambda u: hash_rank_key(u["members"][0][0]))
    n_lin = 0
    for u in lin_ok:
        for repo, _role in u["members"]:
            take(by_repo[repo], f"lineage:{u['unit']}")
        n_lin += 1

    pairs_ok = [u for u in EDITED_PAIRS
                if u["parent"] in by_repo and any(c in by_repo for c in u["children"])]
    pairs_ok.sort(key=lambda u: hash_rank_key(u["parent"]))
    n_edited = 0
    for u in pairs_ok:
        take(by_repo[u["parent"]], f"edited_pair_parent:{u['unit']}")
        kids = sorted([c for c in u["children"] if c in by_repo], key=hash_rank_key)
        for c in kids[:MAX_CHILDREN_PER_PARENT]:
            take(by_repo[c], f"edited_child:{u['unit']}")
            n_edited += 1

    fams = {r["family"] for r in drawn}
    rest = sorted([r for r in rows if r["repo"] not in taken],
                  key=lambda r: (r["rank_key"], r.get("bf16_gb") or 0))
    for r in rest:
        if len(fams) >= TARGET_FAMILIES:
            break
        if r["family"] not in fams and r["role"] in ("sft", "sft_noformat"):
            take(r, "new_family_instruct_arm")
            fams.add(r["family"])
    for r in rest:
        if len(drawn) >= max(TARGET_N, 40):
            break
        take(r, "fill_by_global_rank_key")

    drawn.sort(key=lambda r: (0 if r["draw_reason"].startswith("lineage") else
                              1 if "edited" in r["draw_reason"] else 2,
                              r.get("reserve", False), r["rank_key"]))
    for i, r in enumerate(drawn):
        r["draw_index"] = i

    obj = {"utc": utc_now(), "seed": SEED,
           "panel_rule_sha256": sha256_file(RESULTS / "panel_rule.json"),
           "n_probed": len(todo), "n_eligible": len(rows), "n_rejected": len(rejects),
           "n_drawn": len(drawn),
           "families": sorted({r["family"] for r in drawn}),
           "n_families": len({r["family"] for r in drawn}),
           "n_lineages_eligible": n_lin, "n_edited_children": n_edited,
           "n_reserve": sum(1 for r in drawn if r["reserve"]),
           "quota_check": {"n_checkpoints": (len(drawn), TARGET_N),
                           "families": (len({r['family'] for r in drawn}), TARGET_FAMILIES),
                           "lineages": (n_lin, TARGET_LINEAGES),
                           "edited_children": (n_edited, TARGET_EDITED)},
           "prior_exposure_split": {g: sum(1 for r in drawn if r["prior_exposure"] == g)
                                    for g in ("NEVER_SEEN", "REGISTRY_ONLY", "TOUCHED_UPSTREAM")},
           "checkpoints": drawn}
    jdump(RESULTS / "panel_rejects.json", {"utc": utc_now(), "n": len(rejects), "rejects": rejects})
    p = jdump(RESULTS / "panel.json", obj)
    chain_append("panel_drawn", p, note=f"STAGE A: {len(drawn)} drawn from "
                                        f"{len(rows)}/{len(todo)} eligible")
    logger.info(f"panel.json: {len(drawn)} checkpoints, {obj['n_families']} families, "
                f"{n_lin} lineages, {n_edited} edited children, {len(rejects)} rejects")
    return p


def jload_chain() -> list[dict]:
    from common import chain_read
    return chain_read()


def main() -> None:
    setup_logging("panel")
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["rule", "draw"])
    a = ap.parse_args()
    if a.phase == "rule":
        do_rule()
    else:
        do_draw()


if __name__ == "__main__":
    main()
