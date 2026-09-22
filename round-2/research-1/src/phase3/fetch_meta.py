import re, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL="/ai-inventor/.claude/skills/aii-web-tools"
PY=f"{SKILL}/../.ability_client_venv/bin/python"
SCRIPT=f"{SKILL}/scripts/aii_fast_web_fetch.py"
OUT=Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_research_1/phase3")
RAW=OUT/"raw"; RAW.mkdir(parents=True, exist_ok=True)

IDS = sys.argv[1].split(",")

def fetch(aid):
    url=f"https://arxiv.org/abs/{aid}"
    p=RAW/f"{aid}.txt"
    if p.exists() and p.stat().st_size>500:
        return aid, p.read_text()
    try:
        r=subprocess.run([PY,SCRIPT,"fetch","--url",url,"--max-chars","9000"],
                         capture_output=True,text=True,timeout=300)
        t=r.stdout
    except Exception as e:
        t=f"ERROR {e}"
    p.write_text(t)
    return aid,t

def parse(aid,t):
    d={"arxiv_id":aid,"url":f"https://arxiv.org/abs/{aid}"}
    if "HTTP 404" in t or "Error:" in t[:200]:
        d["status"]="UNRESOLVED"; d["raw_head"]=t[:200]; return d
    m=re.search(r"# Title:(.+?)\n",t)
    d["title"]=m.group(1).strip() if m else None
    m=re.search(r"Authors:(.+?)\n",t)
    if m:
        d["authors"]=[a.strip() for a in re.findall(r"\[([^\]]+)\]\(https://arxiv\.org/search",m.group(1))]
        d["authors_line_raw"]=m.group(1).strip()[:600]
    m=re.search(r"\[Submitted on ([^\(\]]+?)(?:\s*\(|\])",t)
    d["submitted"]=m.group(1).strip() if m else None
    m=re.search(r"last revised ([^\(\]]+?)(?:\s*\(|\])",t)
    if m: d["last_revised"]=m.group(1).strip()
    m=re.search(r"\*\*Journal ref:\*\*\s*(.+?)\n",t) or re.search(r"Journal ref:\s*\|\s*(.+?)\n",t)
    if m: d["journal_ref"]=m.group(1).strip()
    m=re.search(r"Comments:\s*\|\s*(.+?)\n",t)
    if m: d["comments"]=m.group(1).strip()
    m=re.search(r"> Abstract:(.+?)\n",t,re.S)
    if m: d["abstract"]=re.sub(r"\s+"," ",m.group(1)).strip()[:1400]
    d["status"]="OK" if d.get("title") else "PARSE_FAIL"
    return d

with ThreadPoolExecutor(max_workers=6) as ex:
    res=list(ex.map(fetch, IDS))
out=[parse(a,t) for a,t in res]
(OUT/"bibliography_raw.json").write_text(json.dumps(out,indent=1))
for d in out:
    print(d["status"],"|",d["arxiv_id"],"|",(d.get("title") or "")[:95],"|",", ".join(d.get("authors",[])[:12]),"|",d.get("submitted"),"|",d.get("journal_ref","-"))
