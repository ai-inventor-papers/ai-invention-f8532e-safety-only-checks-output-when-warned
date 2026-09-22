import re,json
from pathlib import Path
RAW=Path("phase3/raw")
out=[]
for p in sorted(RAW.glob("*.txt")):
    aid=p.stem; t=p.read_text()
    d={"arxiv_id":aid,"url":f"https://arxiv.org/abs/{aid}"}
    m=re.search(r"# Title:(.+?)\n",t); d["title"]=m.group(1).strip() if m else None
    m=re.search(r"Authors:(.+?)\n",t)
    d["authors"]=[a.strip() for a in re.findall(r"\[([^\]]+)\]\(https://arxiv\.org/search",m.group(1))] if m else []
    m=re.search(r"\[Submitted on ([^\(\]]+?)(?:\s*\(|\])",t); d["submitted"]=m.group(1).strip() if m else None
    m=re.search(r"last revised ([^\(\]]+?)(?:\s*\(|\])",t)
    d["last_revised"]=m.group(1).strip() if m else None
    m=re.search(r"Comments:\s*\|\s*(.+?)\n",t); d["comments"]=m.group(1).strip() if m else None
    m=re.search(r"Journal ref:\s*\|\s*(.+?)\n",t); d["journal_ref"]=m.group(1).strip() if m else None
    d["status"]="OK" if d["title"] else "UNRESOLVED"
    out.append(d)
Path("phase3/bibliography_verified.json").write_text(json.dumps(out,indent=1))
print("n=",len(out))
for d in out:
    yr = "20"+d["arxiv_id"][:2]
    print(f"{d['arxiv_id']} | {d['title']} | {'; '.join(d['authors'])} | {d['submitted']} | rev={d.get('last_revised')} | {d.get('comments') or ''}")
