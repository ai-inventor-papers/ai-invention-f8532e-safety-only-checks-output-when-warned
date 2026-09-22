"""Strict verbatim check: single plain fetch per URL, whitespace-normalised literal containment only.
No markup stripping, no partial-window fallback."""
import json, re, subprocess, unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL="/ai-inventor/.claude/skills/aii-web-tools"
PY=f"{SKILL}/../.ability_client_venv/bin/python"
SCRIPT=f"{SKILL}/scripts/aii_fast_web_fetch.py"
CACHE=Path("strict_cache"); CACHE.mkdir(exist_ok=True)

def ws(s):
    s=unicodedata.normalize("NFC",s)
    return re.sub(r"\s+"," ",s).strip()

def fetch(url):
    p=CACHE/(re.sub(r"[^A-Za-z0-9]+","_",url)[:150]+".txt")
    if p.exists() and p.stat().st_size>200: return p.read_text()
    try:
        r=subprocess.run([PY,SCRIPT,"fetch","--url",url,"--max-chars","200000"],
                         capture_output=True,text=True,timeout=420)
        t=r.stdout.split("--- Content ---",1)[-1]
    except Exception:
        t=""
    p.write_text(t); return t

src=json.load(open("research_out.json"))["sources"]
urls=sorted({s["url"] for s in src if s["supporting_passages"]})
with ThreadPoolExecutor(max_workers=5) as ex:
    docs=dict(zip(urls,ex.map(fetch,urls)))

fails=[]
for s in src:
    d=ws(docs.get(s["url"],""))
    seen=set()
    for p in s["supporting_passages"]:
        q=ws(p["quote"])
        dup = q in seen
        seen.add(q)
        ok = bool(d) and q in d
        if (not ok) or dup or "..." in p["quote"] or "…" in p["quote"]:
            fails.append((s["index"],s["url"],p["quote"],
                          "DUPLICATE" if dup else ("ELLIPSIS-SPLICE" if ("..." in p["quote"] or "…" in p["quote"]) else ("DOC-EMPTY" if not d else "NOT-FOUND"))))
print(f"doc sizes: " + ", ".join(f"{u.split('/')[-1][:28]}={len(docs[u])}" for u in urls))
print(f"\nTOTAL PASSAGES {sum(len(s['supporting_passages']) for s in src)} | FAILING {len(fails)}\n")
for i,u,q,why in fails:
    print(f"[{i}] {why} :: {u}\n     {q[:150]!r}\n")
