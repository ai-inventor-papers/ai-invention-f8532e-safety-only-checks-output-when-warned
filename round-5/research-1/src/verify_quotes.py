"""Block V: independently re-fetch every quoted passage against its OWN URL and regex-match it.

The finder of each quote was a subagent; this re-fetch is run by the orchestrator, satisfying the
two-touch rule. A quote passes if a whitespace-flexible regex built from a distinctive 6-9 word
window of the quote matches >=1 time on a fresh fetch of the quote's URL. Two windows are tried
(middle, then start) so a single PDF hyphenation or ligature break does not cause a false fail.

Usage: uv run verify_quotes.py  (or python3)  -> verify/quote_results.json
"""
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

WS = Path(__file__).parent
SKILL = Path("/ai-inventor/.claude/skills/aii-web-tools")
PY = str(SKILL.parent / ".ability_client_venv/bin/python")
FETCH = str(SKILL / "scripts/aii_fast_web_fetch.py")


def windows(q: str) -> list[str]:
    # strip markdown/escapes, normalise quotes/dashes, keep word tokens
    q = q.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    # word tokens only: %, backslashes, LaTeX ($\to$), em-dashes and markdown are absorbed by the
    # [\W_]{0,12} separators, so '0.42%' matches a page's '0.42\%' and 'to' matches '$\to$'
    words = re.findall(r"[A-Za-z0-9.']+", q)
    words = [w.strip(".'") for w in words]
    words = [w for w in words if w]  # keep single letters: dropping 'a' breaks 'as a recovery
    if len(words) < 6:
        return [" ".join(words)] if words else []
    n = min(8, len(words))
    mid = max(0, len(words) // 2 - n // 2)
    out = [words[mid:mid + n], words[:n]]
    return [" ".join(w) for w in out]


def to_regex(win: str) -> str:
    # each token escaped; between tokens allow any run of non-word chars (spaces, newlines, hyphen breaks, punctuation)
    # straight and curly apostrophes are interchangeable (arXiv abs pages render unit's as unit\u2019s)
    toks = [re.escape(t).replace("'", "['\u2019]") for t in win.split()]
    return r"[\W_]{0,12}".join(toks)


def grep(url: str, pattern: str) -> tuple[int, str]:
    try:
        r = subprocess.run([PY, FETCH, "grep", "--url", url, "--pattern", pattern, "-i",
                            "--max-matches", "3", "--context-chars", "80"],
                           capture_output=True, text=True, timeout=150)
    except subprocess.TimeoutExpired:
        return -1, "TIMEOUT"
    txt = r.stdout
    m = re.search(r"\((\d+) matches in (\d+) chars\)", txt)
    if m:
        return int(m.group(1)), f"doc_chars={m.group(2)}"
    if "No matches" in txt:
        m2 = re.search(r"in (\d+) chars", txt)
        return 0, f"doc_chars={m2.group(1) if m2 else '?'}"
    return -1, (txt[-300:] or r.stderr[-300:]).replace("\n", " ")


def check(item: dict) -> dict:
    res = {**item, "attempts": []}
    for win in windows(item["quote"]):
        pat = to_regex(win)
        n, info = grep(item["url"], pat)
        res["attempts"].append({"window": win, "matches": n, "info": info})
        if n and n > 0:
            res["status"] = "REVERIFIED"
            return res
    fetch_failed = all(a["matches"] == -1 for a in res["attempts"])
    if fetch_failed:
        res["status"] = "FETCH_FAILED"
        return res
    # FALLBACK for PDF line-wraps / hyphenation that defeat an 8-word window: slide 4-word
    # windows across the quote and require >=2 DISTINCT windows to match on the fresh fetch.
    toks = re.findall(r"[A-Za-z0-9.']+", item["quote"])
    toks = [t.strip(".'") for t in toks if t.strip(".'")]
    wins = [" ".join(toks[i:i + 4]) for i in range(0, max(0, len(toks) - 3), 3)]
    hits = []
    for w in wins[:8]:
        n, _ = grep(item["url"], to_regex(w))
        if n and n > 0:
            hits.append(w)
        if len(hits) >= 2:
            break
    res["anchor_windows_matched"] = hits
    res["status"] = "REVERIFIED_BY_ANCHOR" if len(hits) >= 2 else "NOT_REPRODUCED"
    return res


def main() -> None:
    src = WS / (sys.argv[1] if len(sys.argv) > 1 else "verify/quotes_to_verify.json")
    items = json.loads(src.read_text())
    with ThreadPoolExecutor(max_workers=4) as ex:
        results = list(ex.map(check, items))
    out = WS / "verify/quote_results.json"
    prev = json.loads(out.read_text()) if out.exists() else []
    merged = {(r["quote"][:120], r["url"]): r for r in prev}
    for r in results:
        merged[(r["quote"][:120], r["url"])] = r
    allr = list(merged.values())
    out.write_text(json.dumps(allr, indent=1))
    from collections import Counter
    c = Counter(r["status"] for r in allr)
    print("THIS BATCH:", dict(Counter(r["status"] for r in results)))
    print("CUMULATIVE:", dict(c), " total:", len(allr))
    for r in results:
        if r["status"] != "REVERIFIED":
            print(f"  [{r['status']}] {r['id']} {r['url']}\n      {r['quote'][:140]}")


if __name__ == "__main__":
    main()
