"""Collect every quoted passage + its URL from all lane outputs into verify/quotes_to_verify.json.

Block V's verifier (a DIFFERENT agent from whoever found each quote) re-fetches each URL and
regex-matches the quote. Absence claims (zero-match + positive control) are collected separately.
"""
import json
import re
from pathlib import Path

WS = Path(__file__).parent
SOURCES = {
    "lane_SA": WS / "blockS/lane_SA.json",
    "lane_SBC": WS / "blockS/lane_SBC.json",
    "blockT": WS / "blockT/target_cell_table.json",
    "blockD": WS / "blockD/dimensionality.json",
}
SKIP_PREFIXES = ("(carried", "(iter-", "No matches", "ZERO MATCHES", "grep ", "carried", "DELETED_COMPOSITE")

quotes, absences = [], []
seen = set()

def is_real_quote(q):
    return isinstance(q, str) and len(q.strip()) >= 25 and not q.strip().startswith(SKIP_PREFIXES)

def walk(obj, lane, path=""):
    if isinstance(obj, dict):
        q = obj.get("quote") or obj.get("verbatim_quote") or obj.get("verbatim_abstract_sentence") \
            or obj.get("verbatim_sentence") or obj.get("deciding_quote")
        url = obj.get("quote_url") or obj.get("url") or obj.get("arxiv_id_or_url")
        if is_real_quote(q) and isinstance(url, str) and url.startswith("http"):
            key = (q.strip()[:120], url)
            if key not in seen:
                seen.add(key)
                quotes.append({"id": f"Q{len(quotes)+1:03d}", "lane": lane, "path": path,
                               "quote": q.strip(), "url": url.split(" ;")[0].strip()})
        if "positive_control" in obj and ("regex_used" in obj or "regex" in obj):
            pc = obj.get("positive_control")
            if isinstance(pc, str) and re.search(r"\d+\s*(match|hit)", pc or "", re.I) \
               and re.search(r"0\s*(match|hit)|zero|No matches", str(obj.get("quote", "")) + str(obj.get("matches", "")), re.I):
                absences.append({"lane": lane, "path": path, "url": obj.get("quote_url") or obj.get("url"),
                                 "regex": obj.get("regex_used") or obj.get("regex"), "positive_control": pc})
        for k, v in obj.items():
            walk(v, lane, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            walk(v, lane, f"{path}[{i}]")

for lane, p in SOURCES.items():
    if p.exists():
        d = json.loads(p.read_text())
        walk(d, lane)
        for a in d.get("absence_claims", []) if isinstance(d, dict) else []:
            absences.append({"lane": lane, **a})
    else:
        print(f"MISSING (not yet landed): {p.relative_to(WS)}")

(WS / "verify").mkdir(exist_ok=True)
(WS / "verify/quotes_to_verify.json").write_text(json.dumps(quotes, indent=1))
(WS / "verify/absences_to_verify.json").write_text(json.dumps(absences, indent=1))
print(f"quotes: {len(quotes)}  absence claims: {len(absences)}")
from collections import Counter
print("by lane:", dict(Counter(q['lane'] for q in quotes)))
