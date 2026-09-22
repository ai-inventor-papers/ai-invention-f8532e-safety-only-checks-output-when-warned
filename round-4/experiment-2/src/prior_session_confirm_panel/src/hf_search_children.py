"""Pool construction helper (run BEFORE the rule freeze; no rank key is computed here).

For every instruct parent in the plan's seed pool, query the Hub search API for community-edited
children whose repo name contains an edit keyword (abliterat / uncensor / heretic / decensor).
Writes results/hf_search_children.json (raw hits, unfiltered by size/gating: eligibility is decided
later by the frozen rule's live probe).
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WS = Path(__file__).resolve().parents[1]
KEY = re.compile(r"abliterat|uncensor|heretic|decensor", re.I)
QUERIES = {
    # parent repo in the pool -> search strings (basename + the original org's name for mirrors)
    "unsloth/gemma-3-1b-it": ["gemma-3-1b-it"],
    "unsloth/gemma-3-270m-it": ["gemma-3-270m-it", "gemma-3-270m"],
    "h2oai/h2o-danube3-500m-chat": ["danube3-500m", "danube3"],
    "baidu/ERNIE-4.5-0.3B-PT": ["ERNIE-4.5-0.3B"],
    "tencent/Hunyuan-0.5B-Instruct": ["Hunyuan-0.5B"],
    "LGAI-EXAONE/EXAONE-4.0-1.2B": ["EXAONE-4.0-1.2B"],
    "openbmb/MiniCPM4-0.5B": ["MiniCPM4-0.5B"],
    "Zyphra/Zamba2-1.2B-instruct": ["Zamba2-1.2B"],
    "tiiuae/Falcon-H1-0.5B-Instruct": ["Falcon-H1-0.5B"],
    "deepseek-ai/deepseek-coder-1.3b-instruct": ["deepseek-coder-1.3b"],
    "bigscience/bloomz-560m": ["bloomz-560m"],
    "bigscience/bloomz-1b1": ["bloomz-1b1"],
    "princeton-nlp/Sheared-LLaMA-1.3B-ShareGPT": ["Sheared-LLaMA-1.3B"],
}


def search(q: str) -> list[dict]:
    url = f"https://huggingface.co/api/models?search={urllib.parse.quote(q)}&limit=500&full=false"
    req = urllib.request.Request(url, headers={"User-Agent": "aii-confirm-panel"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:  # noqa: BLE001
        return [{"__error__": repr(e)[:200]}]


def main() -> None:
    out = {}
    jobs = [(p, q) for p, qs in QUERIES.items() for q in qs]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda pq: (pq, search(pq[1])), jobs))
    for (parent, q), hits in res:
        ids = [h.get("id") or h.get("modelId") for h in hits if isinstance(h, dict) and not h.get("__error__")]
        kids = sorted({i for i in ids if i and KEY.search(i)})
        out.setdefault(parent, {"queries": [], "children": []})
        out[parent]["queries"].append({"q": q, "n_hits": len(ids)})
        out[parent]["children"] = sorted(set(out[parent]["children"]) | set(kids))
    (WS / "results").mkdir(exist_ok=True)
    (WS / "results/hf_search_children.json").write_text(json.dumps(out, indent=1))
    for p, v in out.items():
        print(p, v["queries"], len(v["children"]))
        for c in v["children"]:
            print("    ", c)


if __name__ == "__main__":
    main()
