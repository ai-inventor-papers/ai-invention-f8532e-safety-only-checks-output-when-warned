"""STEP 1 -- seeded, logged CONFIRMATION-panel selection, BEFORE any generation (iteration 4).

Two phases, each hash-committed (adapted from src/ref_i3/panel.py):
  rule : write assets/panel_rule.json (pool, eligibility tests, quotas, seed, draw order, TIME rule)
         and append it to hash_chain.jsonl BEFORE any repo is ranked.
  draw : verify every pool repo LIVE on the Hub, apply the exclusions, rank by
         sha256(seed + repo_id) and apply the quotas -> results/panel.json (one row per repo,
         including every exclusion and its reason) + results/hf_probe_pool.jsonl.
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
from common import (ASSETS, H2, I3, LANEC, RESULTS, RUN, SEED, chain_append, hash_rank_key,  # noqa: E402
                    jdump, jload, setup_logging, utc_now)
from loguru import logger  # noqa: E402

# CPU fallback 1 of the plan (no GPU on the box): the pool is restricted to <=1.3B-class models.
# Operationalised as <= 1.40e9 parameters (so nominal "1.3B" repos with 1.35B params stay eligible).
SIZE_CAP_PARAMS = 1.40e9
MAX_CHILDREN_PER_PARENT = 2          # CPU-mode cap (deviation cpu_mode_max2_children_per_parent)
SHARED_HUB = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/.shared_cache/hf/hub")

# (i) the direction's list; (ii) is derived mechanically from the 32 screen checkpoints in do_rule().
EXCLUDED_FAMILIES_DIRECTION = ["qwen3", "qwen2.5", "smollm2", "smollm3", "tinyllama", "phi", "granite",
                               "stablelm", "olmo2", "llama3.2", "falcon3", "amd-olmo", "lfm2"]
# repo-id -> family map used to derive the families of the screen checkpoints
SCREEN_FAMILY_PATTERNS = [
    (r"qwen3", "qwen3"), (r"qwen2\.5", "qwen2.5"), (r"smollm2", "smollm2"), (r"smollm3", "smollm3"),
    (r"tinyllama", "tinyllama"), (r"phi-", "phi"), (r"granite", "granite"), (r"stablelm", "stablelm"),
    (r"olmo-2", "olmo2"), (r"llama-3\.2", "llama3.2"), (r"falcon3", "falcon3"), (r"amd-olmo", "amd-olmo"),
    (r"lfm2", "lfm2"),
]
QUANT_OR_CONVERTED = re.compile(r"gguf|mlx|[0-9]bit|q[0-9]_|w4a16|awq|gptq|exl2|onnx|-int[48]|fp8", re.I)

# ---------------------------------------------------------------------------------------------
# THE POOL (the plan's seed candidate pool restricted to <=1.3B-class, plus the community children
# found by results/hf_search_children.json on 2026-09-21 (Hub search '<parent basename>' filtered to
# abliterat|uncensor|heretic|decensor, quantised/converted formats removed).
# google/* originals are gated: the ungated unsloth mirrors are used (parent_named records the original).
# ---------------------------------------------------------------------------------------------
STAGE_LINEAGES = [
    {"unit": "LIN_gemma3_270m", "family": "gemma", "parent_named": "google/gemma-3-270m(-it)",
     "members": [("unsloth/gemma-3-270m", "base"), ("unsloth/gemma-3-270m-it", "instruct")]},
    {"unit": "LIN_gemma3_1b", "family": "gemma", "parent_named": "google/gemma-3-1b-pt/-it",
     "members": [("unsloth/gemma-3-1b-pt", "base"), ("unsloth/gemma-3-1b-it", "instruct")]},
    {"unit": "LIN_danube3_500m", "family": "h2o-danube",
     "members": [("h2oai/h2o-danube3-500m-base", "base"), ("h2oai/h2o-danube3-500m-chat", "instruct")]},
    {"unit": "LIN_bloom_560m", "family": "bloom",
     "members": [("bigscience/bloom-560m", "base"), ("bigscience/bloomz-560m", "instruct_noformat")]},
    {"unit": "LIN_bloom_1b1", "family": "bloom",
     "members": [("bigscience/bloom-1b1", "base"), ("bigscience/bloomz-1b1", "instruct_noformat")]},
    {"unit": "LIN_ernie45_03b", "family": "ernie",
     "members": [("baidu/ERNIE-4.5-0.3B-Base-PT", "base"), ("baidu/ERNIE-4.5-0.3B-PT", "instruct")]},
    {"unit": "LIN_hunyuan_05b", "family": "hunyuan",
     "members": [("tencent/Hunyuan-0.5B-Pretrain", "base"), ("tencent/Hunyuan-0.5B-Instruct", "instruct")]},
    {"unit": "LIN_zamba2_12b", "family": "zamba2",
     "members": [("Zyphra/Zamba2-1.2B", "base"), ("Zyphra/Zamba2-1.2B-instruct", "instruct")]},
    {"unit": "LIN_falconh1_05b", "family": "falcon-h1", "flag": "FAMILY_ADJACENT_TO_EXCLUDED",
     "members": [("tiiuae/Falcon-H1-0.5B-Base", "base"), ("tiiuae/Falcon-H1-0.5B-Instruct", "instruct")]},
    {"unit": "LIN_dscoder_13b", "family": "deepseek-coder",
     "members": [("deepseek-ai/deepseek-coder-1.3b-base", "base"),
                 ("deepseek-ai/deepseek-coder-1.3b-instruct", "instruct")]},
]
EDITED_PAIRS = [
    {"unit": "PAIR_gemma3_1b", "family": "gemma", "parent": "unsloth/gemma-3-1b-it",
     "parent_named": "google/gemma-3-1b-it",
     "children": ["mlabonne/gemma-3-1b-it-abliterated", "mlabonne/gemma-3-1b-it-abliterated-v2",
                  "lunahr/gemma-3-1b-it-abliterated", "prithivMLmods/gemma-3-1b-it-abliterated",
                  "DavidAU/gemma-3-1b-it-heretic-extreme-uncensored-abliterated",
                  "huihui-ai/gemma-3-1b-it-abliterated"]},
    {"unit": "PAIR_gemma3_270m", "family": "gemma", "parent": "unsloth/gemma-3-270m-it",
     "parent_named": "google/gemma-3-270m-it", "children": ["huihui-ai/Huihui-gemma-3-270m-it-abliterated"]},
    {"unit": "PAIR_ernie45_03b", "family": "ernie", "parent": "baidu/ERNIE-4.5-0.3B-PT",
     "parent_named": "baidu/ERNIE-4.5-0.3B-PT", "children": ["AiAsistent/ERNIE-4.5-0.3B-PT-heretic"]},
    {"unit": "PAIR_hunyuan_05b", "family": "hunyuan", "parent": "tencent/Hunyuan-0.5B-Instruct",
     "parent_named": "tencent/Hunyuan-0.5B-Instruct", "children": ["hereticness/heretic_Hunyuan-0.5B-Instruct"]},
    {"unit": "PAIR_exaone4_12b", "family": "exaone", "parent": "LGAI-EXAONE/EXAONE-4.0-1.2B",
     "parent_named": "LGAI-EXAONE/EXAONE-4.0-1.2B",
     "children": ["RichardErkhov/EXAONE-4.0-1.2B-heretic", "huihui-ai/Huihui-EXAONE-4.0-1.2B-abliterated"]},
    {"unit": "PAIR_falconh1_05b", "family": "falcon-h1", "parent": "tiiuae/Falcon-H1-0.5B-Instruct",
     "parent_named": "tiiuae/Falcon-H1-0.5B-Instruct", "children": ["megabytes/Falcon-H1-0.5B-Instruct-heretic"]},
]
SINGLES = [  # extra instruct / base repos (FILL singletons)
    ("EleutherAI/pythia-410m", "pythia", "base"), ("EleutherAI/pythia-1b", "pythia", "base"),
    ("openbmb/MiniCPM4-0.5B", "minicpm", "instruct"),
    ("LGAI-EXAONE/EXAONE-4.0-1.2B", "exaone", "instruct"),
]
FALLBACK_TIER = [  # plan fallback 4: used ONLY if < 8 families are reachable from the pool above
    ("allenai/OLMo-1B-hf", "olmo1-allenai", "base", "ARCH_SHARED_WITH_AMD_OLMO"),
    ("allenai/OLMo-1B-0724-hf", "olmo1-allenai", "base", "ARCH_SHARED_WITH_AMD_OLMO"),
    ("princeton-nlp/Sheared-LLaMA-1.3B", "sheared-llama", "base", "LLAMA2_LINEAGE"),
    ("princeton-nlp/Sheared-LLaMA-1.3B-ShareGPT", "sheared-llama", "instruct", "LLAMA2_LINEAGE"),
]
N_NOOP_FAMILIES = 4
NOOP_VARIANTS_PLAN = ["NOOP_fp16", "NOOP_int8"]

RULE_TEXT = f"""SELECTION RULE (frozen and hashed before any rank is computed).
seed = '{SEED}'; rank key of a repo = sha256(seed + repo_id) as hex, ascending = draw order.
ELIGIBILITY of a repo (verified LIVE on https://huggingface.co/api/models/<id>?blobs=true today):
  (e1) gated == False and not private/disabled; (e2) ships *.safetensors in HF-transformers layout
  (quantised / converted formats -- GGUF, MLX, AWQ, GPTQ, EXL2, ONNX, n-bit -- are not checkpoints of this
  study); (e3) CPU MODE (plan fallback 1, no GPU on the box): parameters <= {SIZE_CAP_PARAMS:.2e}
  ("<=1.3B-class"; params from the Hub safetensors metadata, else bytes/2); (e4) architectures resolve
  (a trust_remote_code repo is TRIED ONCE at load; if generation or output_hidden_states fail it is
  excluded with its reason and replaced by the next FILL member); (e5) instruct roles need a chat
  template, except role 'instruct_noformat' (bloomz: xP3 multitask fine-tune without a chat format ->
  plain request+newline prompt, recorded); (e6) family not excluded: the direction's list
  {EXCLUDED_FAMILIES_DIRECTION} UNION the family of every one of the 32 screen checkpoints (derived
  mechanically from iter_2 harvest tags + iter_3 panel.json); (e7) repo never loaded by an earlier artifact
  of this run (shared HF cache, iter-1..iter-4 harvest / gens / per_ckpt dir names).
  Family = pretraining lineage (org + pretraining run), NOT architecture; gemma2+gemma3 = 'gemma',
  bloom+bloomz = 'bloom'; Falcon-H1 = its own family 'falcon-h1', flagged FAMILY_ADJACENT_TO_EXCLUDED.
UNITS: a stage lineage is eligible iff ALL members are; an edited pair is eligible iff its parent is and
  at least one child is. Children of a parent are ranked by their own rank key; at most
  {MAX_CHILDREN_PER_PARENT} eligible children per parent are taken (CPU-mode cap).
DRAW ORDER:
  (1) stage lineages ranked by the rank key of their BASE repo: the first 3 eligible (mandatory);
  (2) edited pairs ranked by the rank key of their PARENT: ALL eligible pairs (children capped as above),
      parents included (mandatory; >= 2 pairs required);
  (3) no-op families: the eligible role-'instruct' repos of the pool (lineage instruct members, pair
      parents, singleton instruct repos) in rank-key order, taking the first of each new family until
      {N_NOOP_FAMILIES} distinct families are covered; each such repo is a panel member (mandatory) and gets
      2 in-house no-op variants (NOT counted in n): NOOP_fp32 (the same bf16 weights loaded in float32;
      replaces NOOP_int8, bitsandbytes needs a GPU) and NOOP_fp16 (same weights loaded in float16) --
      NOOP_fp16 is replaced by NOOP_sysprompt (chat template + the fixed neutral system prompt
      'You are a helpful assistant.') iff a pre-draw CPU benchmark shows float16 matmul > 2x slower
      than bfloat16 on this box (results/fp16_benchmark.json, measured before the draw);
  (4) FILL: every remaining eligible repo (singletons, members of undrawn lineages, parents of undrawn
      pairs) as a singleton in rank-key order: first any needed to reach >= 8 families (target 10),
      then up to 40 distinct checkpoints. The FALLBACK_TIER (olmo1-allenai, sheared-llama) is used only if
      < 8 families are reachable otherwise.
QUOTAS: >= 30 distinct checkpoints (no-op variants not counted), >= 8 families, >= 3 lineages,
  >= 2 edited pairs, >= 4 no-op families.
GENERATION ORDER (phase A): mandatory members in draw order -> NOOP_sysprompt/NOOP_fp16 variants ->
  FILL members in draw order -> NOOP_fp32 variants (float32 matmul is ~4x slower than bfloat16 on this
  CPU, results/fp16_benchmark.json).
TIME RULE (plan fallbacks 1 and 10; applied mechanically, logged to results/time_rule.json): after
  checkpoints 1, 5, 10, 15, ... of the generation sweep, project the remaining generation + judging +
  core harvest with the measured seconds-per-parameter of the finished checkpoints (float32 variants
  x4; harvest = measured ratio, 1.0x generation until measured); if the projection ends after the
  compute deadline (UTC 20:30 on 2026-09-21), NOOP_fp32 variants are dropped first (reverse draw
  order; a no-op family keeps its other variant, so the >= 4 no-op-family quota holds), then FILL
  members in REVERSE draw order (never a mandatory member, never one whose removal breaks the >= 8
  family quota) until it fits. In CPU mode the n >= 30 quota is NOT
  protected by the TIME rule: if n < 30 the table is labelled UNDERPOWERED_CONFIRMATION with its MDE and
  the verdict can only be FAILED / INCONCLUSIVE / DEFERRED, never CONFIRMED. Items are never cut.
RANDOM-INIT CONTROL: AutoModelForCausalLM.from_config(config of the first included instruct model in
  draw order), torch seed 0; harvested only (never in any rho).
"""


def _get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "aii-confirm-panel"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"__error__": f"HTTP {e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"__error__": repr(e)[:200]}


def _raw(repo: str, fn: str):
    req = urllib.request.Request(f"https://huggingface.co/{repo}/raw/main/{fn}",
                                 headers={"User-Agent": "aii-confirm-panel"})
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
        except Exception:  # noqa: BLE001
            cj = {}
    tc = _raw(repo, "tokenizer_config.json")
    has_ct = False
    if tc:
        try:
            has_ct = bool(json.loads(tc).get("chat_template"))
        except Exception:  # noqa: BLE001
            pass
    has_ct = has_ct or any(s["rfilename"] in ("chat_template.jinja", "chat_template.json") for s in sib)
    card = m.get("cardData") or {}
    return {"repo": repo, "sha": m.get("sha"), "gated": m.get("gated"), "private": m.get("private"),
            "disabled": m.get("disabled"), "st_bytes": st_bytes, "n_safetensors": len(st),
            "params_by_dtype": params, "params_total": n_params, "bf16_bytes": bf16_bytes,
            "bf16_gb": round(bf16_bytes / 1e9, 3), "architectures": cj.get("architectures"),
            "model_type": cj.get("model_type"), "trust_remote_code": bool(cj.get("auto_map")),
            "n_layers": cj.get("num_hidden_layers") or cj.get("n_layer"),
            "hidden_size": cj.get("hidden_size") or cj.get("n_embed"),
            "vocab_size": cj.get("vocab_size"), "tie_word_embeddings": cj.get("tie_word_embeddings"),
            "has_chat_template": has_ct, "declared_base_model": card.get("base_model"),
            "license": card.get("license"), "lastModified": m.get("lastModified"),
            "library_name": m.get("library_name"), "tags": (m.get("tags") or [])[:30]}


def screen_repos() -> list[str]:
    """The 32 screen checkpoints: iteration-2 harvest tags (graded) + iteration-3 held-out panel."""
    reps = []
    for p in sorted((H2 / "harvest").iterdir()):
        if p.is_dir() and not p.name.startswith("RandInit"):
            reps.append(p.name.replace("--", "/", 1))
    # iteration-3 held-out panel = the checkpoints actually harvested (its panel.json also lists two
    # TIME-rule-dropped members that were never generated or loaded: they are not screen checkpoints)
    for p in sorted((I3 / "harvest").iterdir()):
        if p.is_dir() and not p.name.startswith("RandInit"):
            reps.append(p.name.replace("--", "/", 1))
    return sorted(set(reps))


def family_of_screen(repo: str) -> str:
    r = repo.lower()
    for pat, fam in SCREEN_FAMILY_PATTERNS:
        if re.search(pat, r):
            return fam
    return "UNMAPPED:" + repo


def previously_loaded() -> set[str]:
    seen: set[str] = set()
    if SHARED_HUB.exists():
        for p in SHARED_HUB.iterdir():
            if p.name.startswith("models--"):
                seen.add(p.name[len("models--"):].replace("--", "/", 1))
    dirs = [H2 / "harvest", I3 / "harvest", I3 / "private/gens", LANEC / "results/per_ckpt", LANEC / "results/gens"]
    for it in ("iter_1", "iter_2", "iter_3", "iter_4"):
        base = RUN / it / "gen_art"
        if not base.exists():
            continue
        for art in base.iterdir():
            if it == "iter_4" and art.name == "gen_art_experiment_2":
                continue  # this artifact's own workspace
            for sub in ("harvest", "gens", "private/gens", "results/per_ckpt", "results/gens", "hf_cache"):
                d = art / sub
                if d.exists() and d.is_dir() and d not in dirs:
                    dirs.append(d)
    for d in dirs:
        if not d.exists():
            continue
        try:
            for p in d.iterdir():
                n = p.name.replace(".jsonl", "").replace(".json", "")
                if n.startswith("models--"):
                    n = n[len("models--"):]
                n = n.replace("__", "/", 1) if "__" in n else n.replace("--", "/", 1)
                seen.add(n)
        except Exception:  # noqa: BLE001
            continue
    return seen


def eligibility(pr: dict, role: str, fam: str, seen: set[str], excluded: list[str]) -> str | None:
    if "api_error" in pr:
        return f"hub api {pr['api_error']} (gated/private/absent; never authenticate)"
    if pr["gated"] not in (False, None, "false"):
        return f"gated={pr['gated']}"
    if pr.get("private") or pr.get("disabled"):
        return "private/disabled"
    if QUANT_OR_CONVERTED.search(pr["repo"]):
        return "quantised/converted format (not an HF-transformers checkpoint)"
    if pr["n_safetensors"] == 0:
        return "no *.safetensors (pickle .bin only or adapter-only)"
    if not pr.get("architectures"):
        return "config.json has no architectures (adapter-only / not a full checkpoint)"
    if pr["params_total"] > SIZE_CAP_PARAMS:
        return f"params {pr['params_total'] / 1e9:.2f}B > CPU-mode cap {SIZE_CAP_PARAMS / 1e9:.2f}B"
    if fam in excluded:
        return f"family {fam} is in the screen panel / direction exclusion list"
    if pr["repo"] in seen:
        return "loaded by an earlier artifact of this run"
    if role in ("instruct", "edited_child") and not pr["has_chat_template"]:
        return "instruct-role checkpoint ships no chat template"
    return None


def do_rule() -> None:
    scr = screen_repos()
    fam_ii = sorted({family_of_screen(r) for r in scr})
    added = [f for f in fam_ii if f not in EXCLUDED_FAMILIES_DIRECTION]
    excluded = sorted(set(EXCLUDED_FAMILIES_DIRECTION) | set(fam_ii))
    bench_p = RESULTS / "fp16_benchmark.json"
    bench = jload(bench_p) if bench_p.exists() else None
    rule = {"seed": SEED, "rule_version": 2,
            "rule_version_note": "v1 (hash_chain line 1) derived the screen checkpoints from iter_3 panel.json, "
                                 "which also lists 2 TIME-rule-dropped, never-loaded repos (h2o-danube3-500m-chat, "
                                 "LFM2-1.2B) and so added a spurious family 'UNMAPPED:h2oai/h2o-danube3-500m-chat'; "
                                 "v2 derives them from the iter_3 harvest dirs. No rank key had been computed.",
            "rule_text": RULE_TEXT, "size_cap_params": SIZE_CAP_PARAMS,
            "max_children_per_parent": MAX_CHILDREN_PER_PARENT,
            "excluded_families_direction": EXCLUDED_FAMILIES_DIRECTION,
            "screen_checkpoints": scr, "screen_families_derived": fam_ii,
            "families_added_by_screen_derivation": added, "excluded_families": excluded,
            "stage_lineages": STAGE_LINEAGES, "edited_pairs": EDITED_PAIRS, "singles": SINGLES,
            "fallback_tier": FALLBACK_TIER, "n_noop_families": N_NOOP_FAMILIES,
            "fp16_benchmark": bench, "written_utc": utc_now()}
    p = ASSETS / "panel_rule.json"
    jdump(rule, p)
    chain_append(p, "panel selection rule, frozen BEFORE any rank key is computed")
    logger.info(f"rule frozen: {len(scr)} screen checkpoints -> families {fam_ii}; added {added}")


def do_draw() -> None:
    rule = jload(ASSETS / "panel_rule.json")
    assert rule["seed"] == SEED
    excluded = rule["excluded_families"]
    seen = previously_loaded()
    allr = [m for L in STAGE_LINEAGES for m, _ in L["members"]]
    allr += [p["parent"] for p in EDITED_PAIRS] + [c for p in EDITED_PAIRS for c in p["children"]]
    allr += [r for r, _, _ in SINGLES] + [r for r, _, _, _ in FALLBACK_TIER]
    from concurrent.futures import ThreadPoolExecutor
    uniq = sorted(set(allr))
    repos: dict[str, dict] = {}
    with ThreadPoolExecutor(8) as ex:
        for pr in ex.map(probe, uniq):
            repos[pr["repo"]] = pr
    with open(RESULTS / "hf_probe_pool.jsonl", "w") as f:
        for r in uniq:
            f.write(json.dumps(repos[r], ensure_ascii=False) + "\n")
    elig = {}  # (repo, role, fam) -> reason
    fam_of: dict[str, str] = {}
    role_of: dict[str, str] = {}
    for L in STAGE_LINEAGES:
        for m, role in L["members"]:
            fam_of[m], role_of[m] = L["family"], role
    for P in EDITED_PAIRS:
        fam_of[P["parent"]] = P["family"]
        role_of.setdefault(P["parent"], "instruct")
        for c in P["children"]:
            fam_of[c], role_of[c] = P["family"], "edited_child"
    for r, fam, role in SINGLES:
        fam_of.setdefault(r, fam)
        role_of.setdefault(r, role)
    for r, fam, role, _flag in FALLBACK_TIER:
        fam_of[r], role_of[r] = fam, role

    def why(r):
        if r not in elig:
            elig[r] = eligibility(repos[r], role_of[r], fam_of[r], seen, excluded)
        return elig[r]

    panel: list[dict] = []
    rows: dict[str, dict] = {}

    def add(repo, role, unit, parent, stage, mandatory, extra=None):
        if any(p["repo"] == repo for p in panel):
            return
        e = {"repo": repo, "family": fam_of[repo], "role": role, "unit": unit, "parent": parent,
             "draw_stage": stage, "mandatory": mandatory, "hash_rank_key": hash_rank_key(repo)}
        if extra:
            e.update(extra)
        panel.append(e)

    # (1) lineages
    lin_sorted = sorted(STAGE_LINEAGES, key=lambda L: hash_rank_key(L["members"][0][0]))
    lin_selected, lin_unselected = [], []
    for L in lin_sorted:
        reasons = {m: why(m) for m, _ in L["members"]}
        ok = all(v is None for v in reasons.values())
        if ok and len(lin_selected) < 3:
            lin_selected.append(L["unit"])
            prev = None
            for m, role in L["members"]:
                add(m, role, L["unit"], prev, "1_lineage", True,
                    {"lineage_rank_key": hash_rank_key(L["members"][0][0]), "flag": L.get("flag")})
                prev = m
        else:
            lin_unselected.append(L)
        rows[L["unit"]] = {"kind": "lineage", "eligible": ok, "selected": L["unit"] in lin_selected,
                           "reasons": reasons, "rank_key": hash_rank_key(L["members"][0][0])}

    # (2) edited pairs (all eligible; children capped per parent)
    pair_sorted = sorted(EDITED_PAIRS, key=lambda P: hash_rank_key(P["parent"]))
    pairs_taken = []
    pair_unselected = []
    for P in pair_sorted:
        rp = why(P["parent"])
        kids = sorted(P["children"], key=hash_rank_key)
        ok_kids = [c for c in kids if why(c) is None]
        take_kids = ok_kids[:MAX_CHILDREN_PER_PARENT]
        ok = rp is None and len(take_kids) > 0
        rows[P["unit"]] = {"kind": "edited_pair", "eligible": ok, "parent_reason": rp,
                           "children": {c: (why(c) or ("ELIGIBLE_TAKEN" if c in take_kids else
                                                       "ELIGIBLE_NOT_TAKEN (per-parent cap)")) for c in kids},
                           "rank_key": hash_rank_key(P["parent"])}
        if ok:
            add(P["parent"], role_of[P["parent"]], P["unit"], None, "2_pair_parent", True,
                {"parent_named": P.get("parent_named")})
            for c in take_kids:
                add(c, "edited_child", P["unit"], P["parent"], "2_pair_child", True,
                    {"child_rank_in_pair": kids.index(c)})
                pairs_taken.append({"unit": P["unit"], "parent": P["parent"], "child": c})
        else:
            pair_unselected.append(P)

    # (3) no-op families
    inst_pool = sorted({r for r in fam_of if role_of[r] == "instruct" and why(r) is None
                        and r not in [x[0] for x in FALLBACK_TIER]}, key=hash_rank_key)
    noop_fams, noop_parents = [], []
    for r in inst_pool:
        if fam_of[r] in noop_fams:
            continue
        noop_fams.append(fam_of[r])
        noop_parents.append(r)
        if len(noop_fams) >= N_NOOP_FAMILIES:
            break
    bench = jload(RESULTS / "fp16_benchmark.json") if (RESULTS / "fp16_benchmark.json").exists() else {}
    second_variant = "NOOP_fp16" if bench.get("fp16_ok", False) else "NOOP_sysprompt"
    for r in noop_parents:
        add(r, role_of[r], "NOOP_" + fam_of[r], None, "3_noop_parent", True)
        for p in panel:
            if p["repo"] == r:
                p["noop_variants"] = ["NOOP_fp32", second_variant]

    # (4) FILL
    in_panel = {p["repo"] for p in panel}
    fill_pool = [r for r in fam_of if r not in in_panel and r not in [x[0] for x in FALLBACK_TIER]]
    fill_sorted = sorted(set(fill_pool), key=hash_rank_key)
    families = {p["family"] for p in panel}
    chosen = []
    for r in fill_sorted:  # reach >= 8 families
        if len(families) >= 8:
            break
        if fam_of[r] in families or why(r) is not None:
            continue
        chosen.append((r, "family_quota"))
        families.add(fam_of[r])
    used_fallback = False
    if len(families) < 8:
        used_fallback = True
        for r in sorted([x[0] for x in FALLBACK_TIER], key=hash_rank_key):
            if len(families) >= 8:
                break
            if fam_of[r] in families or why(r) is not None:
                continue
            chosen.append((r, "family_quota_fallback_tier"))
            families.add(fam_of[r])
    for r in fill_sorted:  # target 10 families, then up to 40
        if len(families) >= 10:
            break
        if fam_of[r] in families or why(r) is not None or any(r == c[0] for c in chosen):
            continue
        chosen.append((r, "family_target_10"))
        families.add(fam_of[r])
    for r in fill_sorted:
        if len(panel) + len(chosen) >= 40:
            break
        if why(r) is not None or any(r == c[0] for c in chosen):
            continue
        chosen.append((r, "fill_to_40"))
    order = {r: i for i, r in enumerate(fill_sorted)}
    for r, reason in chosen:
        add(r, role_of[r], "FILL", None, "4_fill", False, {"fill_reason": reason, "fill_rank": order.get(r)})

    for i, p in enumerate(panel):
        p["draw_index"] = i
        pr = repos[p["repo"]]
        p.update({k: pr.get(k) for k in ("bf16_gb", "params_total", "n_layers", "hidden_size", "vocab_size",
                                          "architectures", "model_type", "sha", "trust_remote_code",
                                          "has_chat_template", "license", "declared_base_model")})
    fams = sorted({p["family"] for p in panel})
    n_variants = sum(len(p.get("noop_variants", [])) for p in panel)
    all_rows = []
    for r in uniq:
        inc = r in {p["repo"] for p in panel}
        all_rows.append({"repo": r, "family": fam_of.get(r), "role": role_of.get(r), "included": inc,
                         "exclusion_reason": None if inc else (why(r) or "eligible, not drawn"),
                         "hash_rank_key": hash_rank_key(r), "params_total": repos[r].get("params_total"),
                         "model_type": repos[r].get("model_type")})
    out = {"seed": SEED, "drawn_utc": utc_now(),
           "rule_sha256": (ASSETS / "panel_rule.json.sha256").read_text().strip(),
           "n_panel": len(panel), "n_noop_variants": n_variants, "families": fams, "n_families": len(fams),
           "stage_lineages": lin_selected, "n_stage_lineages": len(lin_selected),
           "edited_pairs": pairs_taken, "n_edited_pairs": len(pairs_taken),
           "noop_families": noop_fams, "noop_parents": noop_parents, "noop_second_variant": second_variant,
           "used_fallback_tier": used_fallback,
           "quota_check": {"n>=30": len(panel) >= 30, "families>=8": len(fams) >= 8,
                           "lineages>=3": len(lin_selected) >= 3, "pairs>=2": len(pairs_taken) >= 2,
                           "noop_families>=4": len(noop_fams) >= 4},
           "units": rows, "panel": panel, "all_rows": all_rows, "previously_loaded_n": len(seen)}
    p = RESULTS / "panel.json"
    jdump(out, p)
    chain_append(p, "panel drawn by the frozen rule (before any generation)")
    logger.info(f"PANEL n={len(panel)} (+{n_variants} no-op variants) families={fams} lineages={lin_selected} "
                f"pairs={len(pairs_taken)} noop={noop_fams} quota={out['quota_check']}")
    for q in panel:
        logger.info(f"  [{q['draw_index']:2d}] {q['repo']:60s} {q['role']:17s} {q['family']:14s} "
                    f"{(q['params_total'] or 0) / 1e9:.2f}B {q['model_type']} "
                    f"{'MANDATORY' if q['mandatory'] else 'fill'} {q.get('noop_variants', '')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["rule", "draw"])
    a = ap.parse_args()
    setup_logging("panel")
    {"rule": do_rule, "draw": do_draw}[a.phase]()
