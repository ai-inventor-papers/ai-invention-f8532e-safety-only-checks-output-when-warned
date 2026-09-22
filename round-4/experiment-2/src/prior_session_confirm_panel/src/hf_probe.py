"""Probe HF Hub metadata for candidate repos: gated, safetensors bytes/dtype, arch, chat template, base_model."""
import json, sys, urllib.request, urllib.error, concurrent.futures as cf

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "aii-probe"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"__error__": f"HTTP {e.code}"}
    except Exception as e:
        return {"__error__": repr(e)[:200]}

def raw(repo, fn):
    url = f"https://huggingface.co/{repo}/raw/main/{fn}"
    req = urllib.request.Request(url, headers={"User-Agent": "aii-probe"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return f"__HTTP {e.code}__"
    except Exception as e:
        return f"__ERR {e!r}__"

def probe(repo):
    m = get(f"https://huggingface.co/api/models/{repo}?blobs=true")
    if "__error__" in m:
        return {"repo": repo, "error": m["__error__"]}
    sib = m.get("siblings", [])
    st = [s for s in sib if s["rfilename"].endswith(".safetensors")]
    st_bytes = sum(int(s.get("size") or 0) for s in st)
    bins = [s for s in sib if s["rfilename"].endswith(".bin") and "pytorch_model" in s["rfilename"]]
    sf = m.get("safetensors") or {}
    params = sf.get("parameters") or {}
    total = sf.get("total")
    cfg = m.get("config") or {}
    card = m.get("cardData") or {}
    tc = raw(repo, "tokenizer_config.json")
    has_ct = False; ct_len = 0
    try:
        tj = json.loads(tc); ct = tj.get("chat_template"); has_ct = bool(ct); ct_len = len(json.dumps(ct)) if ct else 0
    except Exception:
        pass
    has_jinja = any(s["rfilename"] == "chat_template.jinja" for s in sib)
    conf_raw = raw(repo, "config.json")
    try:
        cj = json.loads(conf_raw)
    except Exception:
        cj = {}
    return {"repo": repo, "gated": m.get("gated"), "private": m.get("private"), "disabled": m.get("disabled"),
            "st_bytes": st_bytes, "n_st": len(st), "n_bin": len(bins), "params_by_dtype": params, "params_total": total,
            "architectures": cj.get("architectures") or cfg.get("architectures"), "model_type": cj.get("model_type") or cfg.get("model_type"),
            "auto_map": bool(cj.get("auto_map")), "torch_dtype": cj.get("torch_dtype") or cj.get("dtype"),
            "n_layers": cj.get("num_hidden_layers") or cj.get("n_layers"), "hidden": cj.get("hidden_size") or cj.get("d_model"),
            "vocab": cj.get("vocab_size"), "tie": cj.get("tie_word_embeddings"),
            "has_chat_template": has_ct or has_jinja, "ct_len": ct_len, "has_jinja": has_jinja,
            "base_model": card.get("base_model"), "license": card.get("license"), "sha": m.get("sha"),
            "lastModified": m.get("lastModified"), "downloads": m.get("downloads"), "tags": [t for t in m.get("tags", []) if t.startswith("base_model")][:6]}

def search(q, limit=40):
    r = get(f"https://huggingface.co/api/models?search={q}&limit={limit}&sort=downloads")
    if isinstance(r, dict):
        return []
    return [x["id"] for x in r]

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "probe":
        repos = sys.argv[2:]
        with cf.ThreadPoolExecutor(8) as ex:
            res = list(ex.map(probe, repos))
        for r in res:
            print(json.dumps(r))
    elif mode == "search":
        for q in sys.argv[2:]:
            print(q, "=>", json.dumps(search(q)))
