"""Block V 8.2: reproduce every zero-match absence claim once more, with its positive control, same URL, same session."""
import json, re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from verify_quotes import grep

WS = Path(__file__).parent
items = json.loads((WS / "verify/absences_to_verify.json").read_text())

def norm(a):
    url = a.get("zero_match_url") or a.get("url") or ""
    zr = a.get("zero_match_regex") or a.get("regex_used") or a.get("regex")
    pc = a.get("positive_control_regex")
    if not pc and isinstance(a.get("positive_control"), str):
        m = re.search(r"""(?:pattern|regex)s?\s*['"`]([^'"`]{2,80})['"`]""", a["positive_control"], re.I) \
            or re.search(r"""['"`]([^'"`]{2,60})['"`]\s*(?:returns?|->|:)?\s*\(?\d+""", a["positive_control"])
        pc = m.group(1) if m else None
    return url.split(" ;")[0].strip(), zr, pc

def run(a):
    url, zr, pc = norm(a)
    rec = {"claim": a.get("claim") or a.get("path"), "lane": a.get("lane"), "url": url, "zero_regex": zr, "control_regex": pc}
    if not (url.startswith("http") and zr and pc):
        rec["status"] = "NOT_REPRODUCIBLE_BY_GREP (search-family or API absence; original evidence carried)"
        return rec
    z, _ = grep(url, zr); c, _ = grep(url, pc)
    rec.update(zero_matches=z, control_matches=c)
    rec["status"] = "REPRODUCED" if (z == 0 and c and c > 0) else ("FETCH_FAILED" if c == -1 or z == -1 else "NOT_REPRODUCED")
    return rec

seen, uniq = set(), []
for a in items:
    k = norm(a)
    if k not in seen:
        seen.add(k); uniq.append(a)
with ThreadPoolExecutor(4) as ex:
    out = list(ex.map(run, uniq))
(WS / "verify/absence_results.json").write_text(json.dumps(out, indent=1))
from collections import Counter
print(len(out), dict(Counter(r["status"][:25] for r in out)))
for r in out:
    if r["status"] in ("NOT_REPRODUCED", "FETCH_FAILED"):
        print(" ", r["status"], r["url"], "| zero:", r.get("zero_regex"), r.get("zero_matches"), "| ctl:", r.get("control_regex"), r.get("control_matches"))
