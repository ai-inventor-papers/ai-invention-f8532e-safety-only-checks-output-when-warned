"""Phase 4 self-verification: independent live re-fetch of each quoted passage's OWN url."""
import json, re, subprocess, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL="/ai-inventor/.claude/skills/aii-web-tools"
PY=f"{SKILL}/../.ability_client_venv/bin/python"
SCRIPT=f"{SKILL}/scripts/aii_fast_web_fetch.py"
WS=Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_research_1")
CACHE=WS/"verify_cache"; CACHE.mkdir(exist_ok=True)

def norm(s):
    s=unicodedata.normalize("NFKD",s)
    s=s.replace("’","'").replace("‘","'").replace("“",'"').replace("”",'"')
    s=s.replace("—","-").replace("–","-").replace("−","-").replace(" "," ")
    s=re.sub(r"[*_`]","",s)
    s=re.sub(r"\s+"," ",s)
    return s.lower().strip()

def fetch_full(url):
    key=re.sub(r"[^A-Za-z0-9]+","_",url)[:150]
    p=CACHE/(key+".txt")
    if p.exists() and p.stat().st_size>200: return p.read_text()
    chunks=[]
    for off in (0,60000,120000,180000,240000):
        try:
            r=subprocess.run([PY,SCRIPT,"fetch","--url",url,"--max-chars","60000","--char-offset",str(off)],
                             capture_output=True,text=True,timeout=420)
            t=r.stdout
        except Exception as e:
            t=""
        if not t or "Error:" in t[:120]: break
        body=t.split("--- Content ---",1)[-1]
        chunks.append(body)
        if len(body)<55000: break
    out="\n".join(chunks)
    p.write_text(out)
    return out

def check(rec):
    url=rec["source_url"]; q=rec["quote"]
    doc=fetch_full(url)
    if not doc.strip():
        rec["status"]="error"; rec["match_type"]=None; rec["context"]=None
        rec["note"]="source could not be retrieved"
        return rec
    nd=norm(doc); nq=norm(q)
    idx=nd.find(nq)
    mt=None
    if idx>=0: mt="normalized"
    else:
        # try longest contiguous 12-word window of the quote
        words=nq.split()
        for w in range(min(len(words),18), 7, -1):
            found=False
            for i in range(0,len(words)-w+1):
                sub=" ".join(words[i:i+w])
                j=nd.find(sub)
                if j>=0:
                    idx=j; mt=f"partial-{w}w"; found=True; break
            if found: break
    if idx>=0:
        rec["status"]="valid"; rec["match_type"]=mt
        rec["context"]=doc_context(doc,nd,idx)
    else:
        rec["status"]="error"; rec["match_type"]=None; rec["context"]=None
        rec["note"]="string not found in live re-fetch"
    return rec

def doc_context(doc,nd,idx):
    lo=max(0,idx-160); hi=min(len(nd),idx+520)
    return nd[lo:hi]

def main():
    recs=json.load(open(sys.argv[1]))
    with ThreadPoolExecutor(max_workers=4) as ex:
        out=list(ex.map(check,recs))
    ok=sum(1 for r in out if r["status"]=="valid")
    print(f"PASS {ok}/{len(out)}")
    for r in out:
        if r["status"]!="valid": print("  FAIL:",r["source_url"],"|",r["quote"][:90])
    json.dump(out,open(sys.argv[2],"w"),indent=1)

if __name__=="__main__": main()
