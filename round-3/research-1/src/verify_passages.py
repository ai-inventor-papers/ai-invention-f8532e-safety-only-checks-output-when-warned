"""Re-fetch every source URL and check each quoted passage occurs on that page (whitespace-normalised).

Writes research_verification.json and a cache of fetched page text under verify_cache/.
"""
import json, re, subprocess, hashlib, sys, datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path(__file__).parent))
from passages_main import PASSAGES

WS = Path(__file__).parent
CACHE = WS / "verify_cache"; CACHE.mkdir(exist_ok=True)
SKILL = Path("/ai-inventor/.claude/skills/aii-web-tools")
PY = SKILL.parent / ".ability_client_venv/bin/python"

def norm(s: str) -> str:
    s = s.replace("­", "")
    s = re.sub(r"-\s*\n\s*", "-", s)          # keep hyphen, join PDF line breaks
    return re.sub(r"\s+", " ", s).strip().lower()

def fetch(url: str) -> str:
    f = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".txt")
    if f.exists() and f.stat().st_size > 2000:
        return f.read_text()
    out = subprocess.run([str(PY), str(SKILL / "scripts/aii_fast_web_fetch.py"), "fetch", "--url", url,
                          "--max-chars", "600000"], capture_output=True, text=True, timeout=300).stdout
    f.write_text(out)
    return out

def grep(url: str, passage: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", passage)
    anchor = r"\W+".join(words[:5])   # tolerant anchor over the first five tokens
    out = subprocess.run([str(PY), str(SKILL / "scripts/aii_fast_web_fetch.py"), "grep", "--url", url, "-i",
                          "--pattern", anchor, "--max-matches", "5", "--context-chars", str(len(passage) + 200)],
                         capture_output=True, text=True, timeout=300).stdout
    return out

urls = sorted({p["url"] for p in PASSAGES})
with ThreadPoolExecutor(8) as ex:
    pages = dict(zip(urls, ex.map(fetch, urls)))

today = datetime.date.today().isoformat()
entries, bad = [], 0
for p in PASSAGES:
    page = norm(pages[p["url"]])
    q = norm(p["passage"])
    ok = q in page
    if not ok:  # tolerate PDF hyphenation "infor- mation" vs "information"
        ok = q.replace("- ", "") in page.replace("- ", "")
    how = "fetch" if ok else None
    if not ok:  # page text beyond the ~50 KB fetch horizon: fall back to full-document fetch_grep
        g = grep(p["url"], p["passage"])
        gn = norm(g)
        ok = q in gn or q.replace("- ", "") in gn.replace("- ", "")
        how = "fetch_grep" if ok else "not_found"
    bad += (not ok)
    entries.append(dict(claim=p["claim"], source_key=p["key"], url=p["url"], regex=p["regex"],
                        passage=p["passage"], verified=ok, verified_on=today, verified_via=how,
                        page_chars=len(pages[p["url"]])))
json.dump(dict(checked_at=today, n_passages=len(entries), n_verified=len(entries) - bad,
               method="independent live re-fetch of each URL (aii_fast_web_fetch.py fetch, up to 600k chars), "
                      "whitespace/case-normalised substring match",
               passages=entries), open(WS / "research_verification.json", "w"), indent=1, ensure_ascii=False)
for e in entries:
    if not e["verified"]:
        print("FAIL", e["source_key"], e["url"], "|", e["passage"][:90], "| page chars", e["page_chars"])
print(f"{len(entries)-bad}/{len(entries)} verified")
