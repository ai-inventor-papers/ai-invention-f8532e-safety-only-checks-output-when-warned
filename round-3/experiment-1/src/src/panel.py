"""STEP 1 -- seeded, logged panel selection, BEFORE any generation.

Two phases, each hash-committed:
  rule : write assets/panel_rule.json (pool, eligibility tests, quotas, seed, draw order, TIME rule)
         and append it to hash_chain.jsonl BEFORE any repo is ranked.
  draw : verify every pool repo LIVE on the Hub, apply the exclusions, rank by
         sha256(seed + repo_id) and apply the quotas -> results/panel.json (one row per repo,
         including every exclusion and its reason).
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ASSETS, H2, LANEC, RESULTS, RUN, SEED, chain_append, hash_rank_key,  # noqa: E402
                    jdump, jload, setup_logging, utc_now)
from loguru import logger  # noqa: E402

SIZE_CAP_BF16_BYTES = 3.8e9
SHARED_HUB = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/.shared_cache/hf/hub")

# Families present in the iteration-2 SCREEN panel (H2 results/scored_checkpoints.json + registry scored rows).
EXCLUDED_FAMILIES = ["qwen3", "qwen2.5", "smollm2", "smollm3", "tinyllama", "phi", "granite", "stablelm", "olmo2"]

# ---------------------------------------------------------------------------------------------
# THE POOL (verbatim from the plan's CANDIDATE POOL, plus the D2 registry FRESH held-out pairs and
# the community children found by api/models?search=<parent>+abliterated|uncensored on 2026-09-21).
# ---------------------------------------------------------------------------------------------
REGISTRY_HELDOUT_PAIRS = [  # D2 paired_lineage_registry rows with fresh==True and held_out==True
    {"unit": "REG_minicpm5", "family": "minicpm", "parent": "openbmb/MiniCPM5-2B",
     "child": "huihui-ai/Huihui-MiniCPM5-2B-abliterated"},
    {"unit": "REG_vikhr", "family": "llama3.2", "parent": "Vikhrmodels/Vikhr-Llama-3.2-1B-Instruct",
     "child": "Vikhrmodels/Vikhr-Llama-3.2-1B-Instruct-abliterated"},
    {"unit": "REG_gemma2jpn", "family": "gemma", "parent": "google/gemma-2-2b-jpn-it",
     "child": "ymcki/gemma-2-2b-jpn-it-abliterated-17"},
]
STAGE_LINEAGES = [
    {"unit": "LIN_A_amd_olmo", "family": "amd-olmo",
     "members": [("amd/AMD-OLMo-1B", "base"), ("amd/AMD-OLMo-1B-SFT", "sft"),
                 ("amd/AMD-OLMo-1B-SFT-DPO", "sft_dpo")]},
    {"unit": "LIN_B_danube2", "family": "h2o-danube",
     "members": [("h2oai/h2o-danube2-1.8b-base", "base"), ("h2oai/h2o-danube2-1.8b-sft", "sft"),
                 ("h2oai/h2o-danube2-1.8b-chat", "sft_dpo")]},
    {"unit": "LIN_C_falcon3", "family": "falcon3",
     "members": [("tiiuae/Falcon3-1B-Base", "base"), ("tiiuae/Falcon3-1B-Instruct", "instruct")]},
]
EDITED_PAIRS = [
    {"unit": "PAIR_1_llama32_1b", "family": "llama3.2", "parent": "unsloth/Llama-3.2-1B-Instruct",
     "parent_named": "meta-llama/Llama-3.2-1B-Instruct",
     "children": ["mylesgoose/Llama-3.2-1B-Instruct-abliterated", "mylesgoose/Llama-3.2-1B-Instruct-abliterated2",
                  "mylesgoose/Llama-3.2-1B-Instruct-abliterated3", "STARSPIKE/Llama-3.2-1B-Instruct-abliterated",
                  "Elstuhn/llama-3.2-1B-Instruct-abliterated", "KidIkaros/Llama-3.2-1B-Instruct-abliterated",
                  "nicoboss/Llama-3.2-1B-Instruct-Uncensored", "huihui-ai/Llama-3.2-1B-Instruct-abliterated",
                  "ShuoGZ/llama-3.2-1B-Instruct-abliterated", "uzairkhn/Llama-3.2-1B-Instruct-Uncensored"]},
    {"unit": "PAIR_2_falcon3_1b", "family": "falcon3", "parent": "tiiuae/Falcon3-1B-Instruct",
     "parent_named": "tiiuae/Falcon3-1B-Instruct",
     "children": ["huihui-ai/Falcon3-1B-Instruct-abliterated"]},
    {"unit": "PAIR_3_lfm2_1b", "family": "lfm2", "parent": "LiquidAI/LFM2-1.2B",
     "parent_named": "LiquidAI/LFM2-1.2B", "children": []},
    {"unit": "PAIR_3b_danube2_chat", "family": "h2o-danube", "parent": "h2oai/h2o-danube2-1.8b-chat",
     "parent_named": "h2oai/h2o-danube2-1.8b-chat", "children": []},
]
EXTRA_INSTRUCT = [
    ("LiquidAI/LFM2-1.2B", "lfm2"), ("LiquidAI/LFM2-700M", "lfm2"),
    ("internlm/internlm2_5-1_8b-chat", "internlm2"), ("openbmb/MiniCPM-1B-sft-bf16", "minicpm"),
    ("h2oai/h2o-danube3-500m-chat", "h2o-danube"),
]

RULE_TEXT = f"""SELECTION RULE (frozen and hashed before any rank is computed).
seed = '{SEED}'; rank key of a repo = sha256(seed + repo_id) as hex, ascending = draw order.
ELIGIBILITY of a repo (verified LIVE on https://huggingface.co/api/models/<id>?blobs=true today):
  (e1) gated == False and not private/disabled; (e2) ships *.safetensors; (e3) bf16 size <= 3.8 GB
  (F32-shipped: bytes/2; BF16/F16: bytes); (e4) architectures resolve without trust_remote_code
  (a trust_remote_code repo is TRIED ONCE at load; if model.model.layers[i] hooks / output_hidden_states
  do not give (batch, seq, d) it is excluded); (e5) instruct/sft/chat/edited roles need a chat template
  (tokenizer_config.chat_template or chat_template.jinja) -- except a documented stage checkpoint whose
  sibling stage ships the template for the SAME tokenizer (recorded deviation); (e6) family not in the
  screen panel {EXCLUDED_FAMILIES}; (e7) repo never loaded by an earlier artifact of this run
  (shared HF cache, iter-1/iter-2 per_ckpt/harvest/gens dir names).
UNITS: a stage lineage is eligible iff ALL members are; an edited pair is eligible iff its parent is and
  at least one child is; the child of a pair = the eligible child with the smallest rank key.
DRAW ORDER:
  (1) every D2 registry FRESH held-out pair (fresh==True, held_out==True) that is eligible -- mandatory;
  (2) stage lineages ranked by the rank key of their BASE repo; take the first 2 eligible -- mandatory;
  (3) edited pairs ranked by the rank key of their PARENT repo; take eligible pairs in order until the
      panel holds >= 2 edited pairs counting (1) -- mandatory;
  (4) FILL: the remaining eligible repos (extra instruct repos + members of unselected lineages +
      parents of unselected pairs), each a singleton, in rank-key order; first any needed to reach
      >= 4 families, then up to a total of 12 checkpoints.
QUOTAS: >= 2 stage lineages (a 2-stage base->instruct lineage counts), >= 2 edited parent/child pairs,
  >= 4 families, n >= 8 (below 8: STOP and report).
TIME RULE (from the plan's fallback, applied mechanically after stage-1/3 timing): if projected
  generation + judging for the drawn panel exceeds 150 min, FILL members are dropped in REVERSE draw
  order (never a mandatory member, never below a quota) until the projection is <= 150 min or only the
  quota-satisfying prefix remains. Items are never cut.
RANDOM-INIT CONTROL: AutoModelForCausalLM.from_config(config of the first included instruct model in
  draw order), torch seed 0; harvested only (not in any rho).
"""


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
    st_bytes = sum(int(s.get("size") or 0) for s in st)
    params = (m.get("safetensors") or {}).get("parameters") or {}
    f32 = sum(v for k, v in params.items() if k.upper() == "F32")
    tot = sum(params.values()) if params else 0
    bf16_bytes = st_bytes / 2 if (tot and f32 / tot > 0.5) else st_bytes
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
    has_ct = has_ct or any(s["rfilename"] == "chat_template.jinja" for s in sib)
    card = m.get("cardData") or {}
    return {"repo": repo, "sha": m.get("sha"), "gated": m.get("gated"), "private": m.get("private"),
            "disabled": m.get("disabled"), "st_bytes": st_bytes, "n_safetensors": len(st),
            "params_by_dtype": params, "params_total": tot, "bf16_bytes": bf16_bytes,
            "bf16_gb": round(bf16_bytes / 1e9, 3), "architectures": cj.get("architectures"),
            "model_type": cj.get("model_type"), "trust_remote_code": bool(cj.get("auto_map")),
            "n_layers": cj.get("num_hidden_layers"), "hidden_size": cj.get("hidden_size"),
            "vocab_size": cj.get("vocab_size"), "tie_word_embeddings": cj.get("tie_word_embeddings"),
            "has_chat_template": has_ct, "declared_base_model": card.get("base_model"),
            "license": card.get("license"), "lastModified": m.get("lastModified")}


def previously_loaded() -> set[str]:
    seen: set[str] = set()
    if SHARED_HUB.exists():
        for p in SHARED_HUB.iterdir():
            if p.name.startswith("models--"):
                seen.add(p.name[len("models--"):].replace("--", "/", 1))
    for d in (H2 / "harvest", LANEC / "results/per_ckpt", LANEC / "results/gens"):
        if d.exists():
            for p in d.iterdir():
                n = p.name.replace(".jsonl", "").replace(".json", "")
                n = n.replace("__", "/", 1) if "__" in n else n.replace("--", "/", 1)
                seen.add(n)
    return seen


def eligibility(pr: dict, role: str, fam: str, seen: set[str], template_sibling_ok: bool = False) -> str | None:
    if "api_error" in pr:
        return f"hub api {pr['api_error']} (gated/private/absent; never authenticate)"
    if pr["gated"] not in (False, None, "false"):
        return f"gated={pr['gated']}"
    if pr.get("private") or pr.get("disabled"):
        return "private/disabled"
    if pr["n_safetensors"] == 0:
        return "no *.safetensors (pickle .bin only or adapter-only)"
    if not pr.get("architectures"):
        return "config.json has no architectures (adapter-only / not a full checkpoint)"
    if pr["bf16_bytes"] > SIZE_CAP_BF16_BYTES:
        return f"bf16 size {pr['bf16_gb']} GB > 3.8 GB cap"
    if fam in EXCLUDED_FAMILIES:
        return f"family {fam} is in the screen panel"
    if pr["repo"] in seen:
        return "loaded by an earlier artifact of this run"
    if role != "base" and not pr["has_chat_template"] and not template_sibling_ok:
        return "instruct-role checkpoint ships no chat template"
    return None


def do_rule() -> None:
    rule = {"seed": SEED, "rule_text": RULE_TEXT, "size_cap_bf16_bytes": SIZE_CAP_BF16_BYTES,
            "excluded_families": EXCLUDED_FAMILIES, "registry_heldout_pairs": REGISTRY_HELDOUT_PAIRS,
            "stage_lineages": STAGE_LINEAGES, "edited_pairs": EDITED_PAIRS, "extra_instruct": EXTRA_INSTRUCT,
            "written_utc": utc_now()}
    p = ASSETS / "panel_rule.json"
    jdump(rule, p)
    chain_append(p, "panel selection rule, frozen BEFORE any rank key is computed")


def do_draw() -> None:
    rule = jload(ASSETS / "panel_rule.json")
    assert rule["seed"] == SEED
    seen = previously_loaded()
    repos: dict[str, dict] = {}
    allr = [x["parent"] for x in REGISTRY_HELDOUT_PAIRS] + [x["child"] for x in REGISTRY_HELDOUT_PAIRS]
    allr += [m for L in STAGE_LINEAGES for m, _ in L["members"]]
    allr += [p["parent"] for p in EDITED_PAIRS] + [c for p in EDITED_PAIRS for c in p["children"]]
    allr += [r for r, _ in EXTRA_INSTRUCT]
    from concurrent.futures import ThreadPoolExecutor
    uniq = sorted(set(allr))
    with ThreadPoolExecutor(8) as ex:
        for pr in ex.map(probe, uniq):
            repos[pr["repo"]] = pr
    rows: list[dict] = []
    panel: list[dict] = []

    def row(repo, fam, role, unit, parent, included, reason, extra=None):
        pr = repos[repo]
        r = {"repo": repo, "family": fam, "role": role, "unit": unit, "parent": parent,
             "bf16_gb": pr.get("bf16_gb"), "gated": pr.get("gated"), "arch": pr.get("architectures"),
             "model_type": pr.get("model_type"), "trust_remote_code": pr.get("trust_remote_code"),
             "has_chat_template": pr.get("has_chat_template"), "n_layers": pr.get("n_layers"),
             "hidden_size": pr.get("hidden_size"), "vocab_size": pr.get("vocab_size"),
             "declared_base_model": pr.get("declared_base_model"), "hub_sha": pr.get("sha"),
             "hash_rank_key": hash_rank_key(repo), "included": included, "exclusion_reason": reason}
        if extra:
            r.update(extra)
        rows.append(r)
        return r

    # (1) registry FRESH held-out pairs
    n_pairs = 0
    families: set[str] = set()
    for u in REGISTRY_HELDOUT_PAIRS:
        rp = eligibility(repos[u["parent"]], "instruct", u["family"], seen)
        rc = eligibility(repos[u["child"]], "edited_child", u["family"], seen)
        ok = rp is None and rc is None
        why = None if ok else f"parent: {rp or 'ok'}; child: {rc or 'ok'}"
        row(u["parent"], u["family"], "instruct", u["unit"], None, ok, why, {"draw_stage": "1_registry"})
        row(u["child"], u["family"], "edited_child", u["unit"], u["parent"], ok, why, {"draw_stage": "1_registry"})
        if ok:
            panel += [{"repo": u["parent"], "family": u["family"], "role": "instruct", "unit": u["unit"], "parent": None, "mandatory": True},
                      {"repo": u["child"], "family": u["family"], "role": "edited_child", "unit": u["unit"], "parent": u["parent"], "mandatory": True}]
            n_pairs += 1
            families.add(u["family"])

    # (2) stage lineages ranked by base repo key
    lin_sorted = sorted(STAGE_LINEAGES, key=lambda L: hash_rank_key(L["members"][0][0]))
    n_lin = 0
    lin_selected, lin_unselected = [], []
    for L in lin_sorted:
        # template_sibling_ok: an SFT stage without its own template may borrow the sibling stage's template
        has_sib_ct = any(repos[m]["has_chat_template"] for m, _ in L["members"])
        reasons = {m: eligibility(repos[m], role, L["family"], seen,
                                  template_sibling_ok=(role != "base" and has_sib_ct))
                   for m, role in L["members"]}
        ok = all(v is None for v in reasons.values())
        take = ok and n_lin < 2
        if take:
            n_lin += 1
            lin_selected.append(L["unit"])
            families.add(L["family"])
        else:
            lin_unselected.append(L)
        prev = None
        for m, role in L["members"]:
            why = None if take else (("lineage not drawn (quota of 2 already met)" if ok else
                                      "lineage ineligible: " + "; ".join(f"{k}: {v}" for k, v in reasons.items() if v)))
            row(m, L["family"], role, L["unit"], prev, take, why,
                {"draw_stage": "2_lineage", "lineage_rank_key": hash_rank_key(L["members"][0][0]),
                 "template_borrowed_from_sibling": bool(role != "base" and not repos[m]["has_chat_template"] and has_sib_ct)})
            if take:
                panel.append({"repo": m, "family": L["family"], "role": role, "unit": L["unit"], "parent": prev,
                              "mandatory": True,
                              "template_borrowed_from_sibling": bool(role != "base" and not repos[m]["has_chat_template"] and has_sib_ct)})
            prev = m

    # (3) edited pairs ranked by parent key
    pair_sorted = sorted(EDITED_PAIRS, key=lambda P: hash_rank_key(P["parent"]))
    pair_unselected = []
    in_panel = {p["repo"] for p in panel}
    for P in pair_sorted:
        rp = eligibility(repos[P["parent"]], "instruct", P["family"], seen)
        if P["parent"] in in_panel:
            rp = None  # parent already in the panel through a lineage: the pair re-uses it
        kids = sorted(P["children"], key=hash_rank_key)
        kid_rows = []
        chosen = None
        for c in kids:
            rc = eligibility(repos[c], "edited_child", P["family"], seen)
            kid_rows.append((c, rc))
            if rc is None and chosen is None:
                chosen = c
        ok = rp is None and chosen is not None
        take = ok and n_pairs < 2
        if take:
            n_pairs += 1
            families.add(P["family"])
            if P["parent"] not in in_panel:
                panel.append({"repo": P["parent"], "family": P["family"], "role": "instruct", "unit": P["unit"], "parent": None, "mandatory": True})
                row(P["parent"], P["family"], "instruct", P["unit"], None, True, None, {"draw_stage": "3_pair"})
            panel.append({"repo": chosen, "family": P["family"], "role": "edited_child", "unit": P["unit"], "parent": P["parent"], "mandatory": True})
        else:
            pair_unselected.append(P)
            if P["parent"] not in in_panel:
                row(P["parent"], P["family"], "instruct", P["unit"], None, False,
                    ("pair not drawn (quota met)" if ok else f"pair ineligible: parent: {rp or 'ok'}; "
                     f"no eligible child" if chosen is None else f"parent: {rp}"), {"draw_stage": "3_pair"})
        for c, rc in kid_rows:
            inc = bool(take and c == chosen)
            why = None if inc else (rc or ("a lower-rank eligible child was chosen" if take else "pair not drawn"))
            row(c, P["family"], "edited_child", P["unit"], P["parent"], inc, why,
                {"draw_stage": "3_pair_child", "child_rank_in_pair": [k for k, _ in kid_rows].index(c)})
        in_panel = {p["repo"] for p in panel}

    # (4) FILL singletons in rank-key order
    fill_pool = []
    for r, fam in EXTRA_INSTRUCT:
        fill_pool.append((r, fam, "instruct"))
    for L in lin_unselected:
        for m, role in L["members"]:
            fill_pool.append((m, L["family"], role))
    for P in pair_unselected:
        fill_pool.append((P["parent"], P["family"], "instruct"))
    seen_fill = set()
    fill_pool = [x for x in fill_pool if not (x[0] in seen_fill or seen_fill.add(x[0]))]
    fill_pool = [x for x in fill_pool if x[0] not in in_panel]
    fill_sorted = sorted(fill_pool, key=lambda x: hash_rank_key(x[0]))
    fill_rank = 0
    # first pass: reach >= 4 families
    chosen_fill = []
    for r, fam, role in fill_sorted:
        if len(families) >= 4:
            break
        if fam in families:
            continue
        if eligibility(repos[r], role, fam, seen) is None and not repos[r]["trust_remote_code"]:
            chosen_fill.append((r, fam, role, "family_quota"))
            families.add(fam)
    for r, fam, role in fill_sorted:
        if len(panel) + len(chosen_fill) >= 12:
            break
        if any(r == c[0] for c in chosen_fill):
            continue
        if eligibility(repos[r], role, fam, seen) is None:
            chosen_fill.append((r, fam, role, "fill_to_12"))
    for r, fam, role in fill_sorted:
        c = [x for x in chosen_fill if x[0] == r]
        why = eligibility(repos[r], role, fam, seen)
        inc = bool(c)
        if not inc and why is None:
            why = "fill cap of 12 reached"
        fill_rank += 1
        prev_rows = [x for x in rows if x["repo"] == r]
        extra = {"draw_stage": "4_fill", "fill_rank": fill_rank, "fill_reason": c[0][3] if c else None}
        if prev_rows:  # member of an unselected lineage/pair: update its row
            prev_rows[-1].update({"included": inc, "exclusion_reason": None if inc else why, **extra})
        else:
            row(r, fam, role, "FILL", None, inc, None if inc else why, extra)
        if inc:
            panel.append({"repo": r, "family": fam, "role": role, "unit": "FILL", "parent": None,
                          "mandatory": False, "fill_rank": fill_rank, "fill_reason": c[0][3],
                          "trust_remote_code": repos[r]["trust_remote_code"]})

    # draw order index
    for i, p in enumerate(panel):
        p["draw_index"] = i
        p.update({k: repos[p["repo"]].get(k) for k in ("bf16_gb", "n_layers", "hidden_size", "vocab_size",
                                                        "architectures", "model_type", "sha", "params_total")})
    fams = sorted({p["family"] for p in panel})
    out = {"seed": SEED, "drawn_utc": utc_now(), "rule_sha256": (ASSETS / "panel_rule.json.sha256").read_text().strip(),
           "n_panel": len(panel), "families": fams, "n_families": len(fams),
           "n_stage_lineages": n_lin, "stage_lineages": lin_selected, "n_edited_pairs": n_pairs,
           "quota_ok": bool(n_lin >= 2 and n_pairs >= 2 and len(fams) >= 4 and len(panel) >= 8),
           "panel": panel, "all_rows": rows, "hub_probe": repos,
           "previously_loaded_n": len(seen)}
    p = RESULTS / "panel.json"
    jdump(out, p)
    chain_append(p, "panel drawn by the frozen rule (before any generation)")
    logger.info(f"PANEL n={len(panel)} families={fams} lineages={lin_selected} pairs={n_pairs} quota_ok={out['quota_ok']}")
    for q in panel:
        logger.info(f"  [{q['draw_index']:2d}] {q['repo']:55s} {q['role']:13s} {q['family']:11s} {q['bf16_gb']} GB "
                    f"{'MANDATORY' if q['mandatory'] else 'fill'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["rule", "draw"])
    a = ap.parse_args()
    setup_logging("panel")
    {"rule": do_rule, "draw": do_draw}[a.phase]()
