"""Pre-truth ARCHITECTURE check on RANDOM-INIT, truncated (2-layer) copies of the risky panel architectures
(remote-code / hybrid): does output_hidden_states give L+1 (b, s, d) tensors, and do the harvest code paths
(p_harvest, decode_pass with its greedy_shrink -> HF generate fallback) run? No trained weights are loaded and
no activation of any panel checkpoint is read, so this is allowed before the graded-truth commit."""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "h2"))
import torch  # noqa: E402

from common import RESULTS, jdump, utc_now  # noqa: E402

torch.set_num_threads(1)


def check(repo: str, trust: bool, role: str) -> dict:
    from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer

    from gen import download
    from harvest import p_harvest
    from harvest_confirm import decode_pass, hook_check
    t0 = time.time()
    local = download(repo)
    tok = AutoTokenizer.from_pretrained(local, trust_remote_code=trust)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token or tok.unk_token
    tok.padding_side = "right"
    conf = AutoConfig.from_pretrained(local, trust_remote_code=trust)
    L0 = conf.num_hidden_layers
    try:
        conf.num_hidden_layers = 2
        for k in ("layer_types", "hybrid_layer_ids", "attn_layer_indices", "mamba_layers"):
            if isinstance(getattr(conf, k, None), list):
                setattr(conf, k, getattr(conf, k)[:2])
    except Exception:  # noqa: BLE001  (read-only derived properties: keep the full depth)
        conf = AutoConfig.from_pretrained(local, trust_remote_code=trust)
    torch.manual_seed(0)
    model = AutoModelForCausalLM.from_config(conf, dtype=torch.bfloat16, trust_remote_code=trust).eval()
    out = {"repo": repo, "orig_layers": L0}
    out["hook"] = hook_check(model, tok, "canonical")
    ph = p_harvest(model, tok, ["How do I bake bread?", "Hello there"], max_len=64, batch_size=2,
                   token_ids={"refusal": [1, 2]}, lens_chunk=2)
    out["p_harvest_shape"] = list(ph["A"].shape)
    D, nv, g = decode_pass(model, tok, ["How do I bake bread?", "Tell me a joke"], role, "canonical", 4, True)
    out["decode_shape"] = list(D.shape) if D is not None else None
    out["n_valid"] = nv
    out["elapsed_s"] = time.time() - t0
    out["ok"] = bool(out["hook"]["L_plus_1_ok"] and out["hook"]["shape_ok"])
    return out


res = {"utc": utc_now(), "checks": {}}
import os
REPOS = [x.split(":") for x in os.environ.get("PRECHECK", "tiiuae/Falcon-H1-0.5B-Instruct:0:instruct").split(",")]
prev = (RESULTS / "arch_precheck.json")
if prev.exists():
    res = json.loads(prev.read_text())
    res["utc_updated"] = utc_now()
for repo, trust, role in [(a, b == "1", c) for a, b, c in REPOS]:
    try:
        res["checks"][repo] = check(repo, trust, role)
    except Exception as e:  # noqa: BLE001
        res["checks"][repo] = {"ok": False, "error": repr(e)[:500], "tb": traceback.format_exc()[-2000:]}
    print(repo, json.dumps(res["checks"][repo])[:600])
jdump(res, RESULTS / "arch_precheck.json")
