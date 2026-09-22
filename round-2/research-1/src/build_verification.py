import json, os
from pathlib import Path

BATCHES = ["phase2/verify_orch.json","phase2/verify_batch2.json","phase2/verify_batch3.json"]
recs=[]
for b in BATCHES:
    if os.path.exists(b): recs += json.load(open(b))

# Quotes that failed the page-level occurrence check but were INDEPENDENTLY re-confirmed
# by a full-document regex retrieval at a different rung. Reclassified ANCHOR, not deleted.
ANCHORS = {
 "P08": ("https://arxiv.org/pdf/2604.09544","Appendix H","pdf",
         "Re-confirmed at the pdf rung at char ~130,026 of 166,397. Page-level fetch of the html stops at 50,276 chars."),
 "P47": ("https://aclanthology.org/2026.acl-long.1334.pdf","Appendix, Table 7","acl-pdf",
         "Re-confirmed at char ~58,981 of 76,240 by full-document regex."),
 "P51": ("https://arxiv.org/html/2512.13655v2","Section 4.2, Table 3","html",
         "Re-confirmed at char ~32,188 of 58,000 by full-document regex."),
 "P53": ("https://arxiv.org/html/2604.09544","Appendix A.2.4","html",
         "Re-confirmed at char ~83,802 of 169,694 by full-document regex."),
 "C05": ("https://arxiv.org/html/2406.11717v3","Appendix, direction-selection filters","html",
         "Re-confirmed at char ~78,960 of 135,787 by full-document regex."),
 "C06": ("https://arxiv.org/html/2607.14147v1","Section 4.3 / Appendix E","html",
         "Re-confirmed at char ~109,515 of 135,421 by full-document regex."),
  "A04": ("https://arxiv.org/html/2607.00572v1","Appendix A.3","html",
         "Re-confirmed at char ~72,429 of 106,276 by full-document regex."),
 "A05": ("https://arxiv.org/html/2607.00572v1","Appendix A.2","html",
         "Re-confirmed at char ~71,582 of 106,276 by full-document regex."),
}
NEGATIVE_GREPS = {
 "A09": ("https://arxiv.org/html/2608.17843v1","onset layer|depth-fraction|fraction of depth|layers apart|difference in layer|layer gap",
         "0 matches in 65,151 chars. Independently reproduced by the orchestrator on 2026-09-21. Supports X8 PARTIAL: the nearest multi-model decodability-vs-actionability paper does not quantify the depth lag."),
 "A16": ("https://arxiv.org/html/2606.24952v1","abliterat|uncensor",
         "0 matches in 64,440 chars. Independently reproduced by the orchestrator on 2026-09-21. Supports the claim that 2606.24952 evaluates no abliterated checkpoint."),
 "A21": ("https://arxiv.org/html/2603.05773v2","abliterat|uncensor",
         "0 matches in 84,213 chars. Independently reproduced by the orchestrator on 2026-09-21. Supports the claim that DSH evaluates no abliterated checkpoint."),
}
# Quotes DELETED because the string as written is not present at the source.
DELETIONS = [{
 "id":"C07",
 "source_url":"https://arxiv.org/html/2607.14147v1",
 "quote_as_submitted":"But the instruct model routes the freed mass to refusal far more than the base model (concentration 0.24 vs 0.03; prefill-specific p_refuse gain +1.3pp vs matched +0.1pp)... Instruct 60 prompts; base as anchor.",
 "reason":"DELETED. The string is a composite: the exact literal 'concentration 0.24 vs 0.03' returns 0 matches on the full 135,421-character html (the source renders it as 'concentration 0.240.24 vs 0.030.03'), and the clause 'Instruct 60 prompts; base as anchor' occurs ~1,000 characters later in a different paragraph. Replaced by the verbatim sentence, independently verified at the html rung: 'when the knockout frees probability mass off the compliance continuation, the instruct model routes it to refusal tokens about 8x more than the base model does (concentration 0.240.24 vs 0.030.03, App. E).' The substantive claim (0.24 vs 0.03; instruct vs base; one matched pair; n=60) is UNCHANGED and independently confirmed.",
 "substantive_claim_affected": False,
}]

out=[]
for r in recs:
    rid=r.get("id")
    if rid in ANCHORS:
        u,loc,rung,note=ANCHORS[rid]
        out.append({"id":rid,"class":"anchor","source_url":u,"locator":loc,"quote":r["quote"],
                    "status":"valid","match_type":"full-document-regex","retrieval_rung":rung,
                    "context":None,"note":note+" Beyond the page-fetch horizon, so it did NOT pass the page-level occurrence check; provenance-grade, not quote-grade."})
    elif rid in NEGATIVE_GREPS:
        u,pat,note=NEGATIVE_GREPS[rid]
        out.append({"id":rid,"class":"negative_grep","source_url":u,"locator":f"full-document regex /{pat}/",
                    "quote":None,"status":"valid","match_type":"zero-match (negative result)",
                    "retrieval_rung":"html","context":None,"note":note})
    elif rid=="C07":
        continue
    else:
        out.append({"id":rid,"class":"passage","source_url":r["source_url"],"locator":r.get("locator"),
                    "quote":r["quote"],"status":r["status"],"match_type":r.get("match_type"),
                    "context":(r.get("context") or None),"note":r.get("note")})

passages=[r for r in out if r["class"]=="passage"]
anchors=[r for r in out if r["class"]=="anchor"]
negs=[r for r in out if r["class"]=="negative_grep"]
valid=sum(1 for r in passages if r["status"]=="valid")
doc={
 "artifact":"gen_art_research_1 (iteration 2) — which safety readouts are still unclaimed",
 "date":"2026-09-21",
 "passage_check_scope":("Case/whitespace-normalized text occurrence at the source URL (or archive fallback). "
   "Not claim entailment, locator verification, or author/year verification. status=error means unverified, "
   "not a misquotation. Each passage's OWN url was independently re-fetched in a fresh call, paged in 60,000-character "
   "windows, before this file was written. match_type='normalized' means the whole quote was found; "
   "match_type='partial-Nw' means the longest contiguous N-word window of the quote was found (used where the source "
   "renders LaTeX inline, which duplicates numerals and symbols)."),
 "anchor_class_scope":("ANCHOR entries are numbers or sentences recovered by FULL-DOCUMENT REGEX beyond the ~50 KB "
   "page-fetch truncation horizon. They carry their locator and their retrieval rung and were each re-confirmed by an "
   "independent retrieval, but they never passed the page-level occurrence check and are kept visibly separate from "
   "quote-grade passages, exactly as iteration 1 did."),
 "negative_grep_class_scope":("NEGATIVE_GREP entries are NOT quotes. They are zero-match results of a full-document "
   "regex over a named source, used as evidence that a construct is absent. Each was independently reproduced by the "
   "orchestrator in a separate call on 2026-09-21. They are recorded separately so no reader mistakes a tool message "
   "for source text."),
 "counts":{"passages_checked":len(passages),"passages_valid":valid,
           "passages_failed":len(passages)-valid,
           "anchors":len(anchors),"negative_greps":len(negs),"deletions":len(DELETIONS)},
 "pass_rate":f"{valid}/{len(passages)}",
 "deletions":DELETIONS,
 "records":out,
}
Path("research_verification.json").write_text(json.dumps(doc,indent=1))
print("passages",valid,"/",len(passages),"| anchors",len(anchors),"| negative_greps",len(negs),"| deletions",len(DELETIONS))
for r in passages:
    if r["status"]!="valid": print("  STILL-FAILING:",r["id"],r["source_url"],"|",r["quote"][:90])
