"""Independent live re-fetch of every source URL; checks each passage occurs (whitespace/case-normalised).
Falls back to fetch_grep over the full document for text beyond the fetch horizon. Writes research_verification.json."""
import json, re, subprocess, hashlib, datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from sources_passages import SOURCES

WS = Path(__file__).parent
CACHE = WS / "verify_cache"; CACHE.mkdir(exist_ok=True)
SKILL = Path("/ai-inventor/.claude/skills/aii-web-tools")
PY = SKILL.parent / ".ability_client_venv/bin/python"

def norm(s):
    s = s.replace("­", "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = re.sub(r"-\s*\n\s*", "-", s)
    return re.sub(r"\s+", " ", s).strip().lower()

def fetch(url):
    f = CACHE / (hashlib.md5(url.encode()).hexdigest() + ".txt")
    if f.exists() and f.stat().st_size > 500:
        return f.read_text()
    out = subprocess.run([str(PY), str(SKILL / "scripts/aii_fast_web_fetch.py"), "fetch", "--url", url, "--max-chars", "800000"],
                         capture_output=True, text=True, timeout=300).stdout
    f.write_text(out); return out

def grep(url, passage):
    words = re.findall(r"[A-Za-z0-9]+", passage)
    anchor = r"\W+".join(words[:5]) if len(words) >= 2 else re.escape(passage)
    return subprocess.run([str(PY), str(SKILL / "scripts/aii_fast_web_fetch.py"), "grep", "--url", url, "-i", "--pattern", anchor,
                           "--max-matches", "5", "--context-chars", str(len(passage) + 300)], capture_output=True, text=True, timeout=300).stdout, anchor

def match(q, text):
    # strict: whitespace/case only (no hyphen or quote repair), mirroring the external checker
    ws = lambda x: re.sub(r"\s+", " ", x).strip().lower()
    return ws(q) in ws(text)

urls = sorted({s["url"] for s in SOURCES if s["passages"]})
with ThreadPoolExecutor(8) as ex:
    pages = dict(zip(urls, ex.map(fetch, urls)))
today = datetime.date.today().isoformat(); entries = []
for s in SOURCES:
    for q, loc in s["passages"]:
        ok = match(q, pages[s["url"]]); how = "fetch" if ok else None; anchor = None
        if not ok:
            g, anchor = grep(s["url"], q); ok = match(q, g); how = "fetch_grep" if ok else "not_found"
        entries.append(dict(source_index=s["i"], url=s["url"], passage=q, locator=loc, regex=anchor, verified=ok,
                            status="VERIFIED" if ok else "UNVERIFIED", verified_via=how, verified_on=today,
                            page_chars=len(pages[s["url"]])))
n_ok = sum(e["verified"] for e in entries)
json.dump(dict(checked_at=today, n_passages=len(entries), n_verified=n_ok,
               method="independent live re-fetch of each URL (aii_fast_web_fetch.py fetch, up to 800k chars) with whitespace/case-normalised substring match; fetch_grep fallback over the full document",
               passages=entries), open(WS / "research_verification.json", "w"), indent=1, ensure_ascii=False)
for e in entries:
    if not e["verified"]: print("FAIL", e["source_index"], e["url"], "|", e["passage"][:80], "| chars", e["page_chars"])
print(f"{n_ok}/{len(entries)} verified")
