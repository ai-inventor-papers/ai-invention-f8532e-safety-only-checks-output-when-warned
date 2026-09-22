import json, re
from pathlib import Path

answer = Path('answer.md').read_text()
sources = json.load(open('sources_draft.json'))

TITLE = "Which safety readouts are still unclaimed"
LAYMAN = ("Checks whether seven proposed cheap safety measurements for AI models have already been published by someone "
          "else, and finds that two are already shipped in a public tool and the other five are partly taken.")

SUMMARY = """Dated web-only saturation and verification pass, 2026-09-21, $0.00 spend, no cuts taken. Self-verification: 105/105 quote-grade passages re-confirmed by an independent live re-fetch of their own URL; 1 quote deleted as a composite (logged, substantive claim unaffected); 8 anchors recovered beyond the ~50 KB page-fetch horizon kept visibly separate; 3 zero-match regexes used as absence evidence kept separate again and each independently reproduced. Bibliography regenerated from live arXiv metadata: 65/65 ids resolved, 0 UNRESOLVED.

VERDICTS on the seven EXECUTION-side candidates, none OPEN: X2 (weight-space write mass) and X10 (weights-only orthogonality scar) are CLOSED - not by arXiv:2607.01854, which this pass proves is REFERENCE-ANCHORED on BOTH signals ("The audit rests entirely on the reference"), but by the Jorak Model Scanner, a live NON-PEER-REVIEWED open-source tool that ships the exact normalised ||r^T W|| suppression statistic with r fitted from the candidate's OWN activations and a weights-only zero-inference SVD subspace-alignment scar test (A/B/S), calibrated cross-model. X1 PARTIAL (per-input vs per-checkpoint; nearest HPD/HERALD 2609.13534 and Geometry-Lite 2605.20241 scalarise depth profiles per PROMPT). X3 PARTIAL (concept + lexical-token dependence; nearest Logit-Gap Steering 2506.24056). X5 PARTIAL (parent-requiring, only 2 checkpoints; 2607.14147's 0.24-vs-0.03 concentration is a knockout-conditioned instruct-vs-base pair, n=60). X6 PARTIAL on the thinnest margin in the table. X8 PARTIAL (concept).

TWO ADVERSE PRIORS ITERATION 1 DID NOT HAVE, and they own this iteration's axis. (1) arXiv:2604.09544 (Orgad, Wei, Zheng, Wattenberg, Henderson, Goldfarb-Tarrant, Belinkov) - iteration 1 mis-filed it as a pruning-only paper; its abstract publishes "harmful response generation is dissociable from the ability to recognize and reason about harmfulness", a DOUBLE DISSOCIATION between harm generation and refusal, and separability GRADED along the OLMo3-7B alignment ladder (emerging at DPO). (2) arXiv:2603.05773 "Knowing without Acting" names the axes Recognition (v_H) and Execution (v_R) and demonstrates a causal double dissociation on harm. (3) arXiv:2606.24952 publishes a per-checkpoint weight-computable detection-vs-control cosine over four models (0.12/0.20/0.16/0.13; 0.1197 vs 0.1200 across instruction tuning) and concludes it is "not a predictor of how steerable a behavior is". NONE of the three evaluates an abliterated checkpoint (grep abliterat|uncensor = 0 matches on 2606.24952 and on 2603.05773) - that is the one genuinely empty cell.

N-GLARE ALREADY RUNS THIS RUN'S PANEL: ACL 2026 Long 1334 s1 illustrates JSS on "RL-aligned, base, and safety-removed versions of Qwen3-4B". Its margin is input cost only (four constructed dialogue families per model). Re-checked 2026-09-21: STILL NO CODE, and NO numeric Kendall's tau anywhere (Appendix Tables 6-8 are per-model benchmark values) - iteration 1's prohibition stands permanently.

CLEAN NOT-FOUND worth more than any candidate: NO prior work scores a SAFE-COMPLETION model (declines without a lexical refusal) with an INTERNAL readout; OpenAI's 2508.09224 and OpenSafeIntent 2607.02047 are purely behavioural. Every lexical-refusal-keyed internal readout is undefined on GPT-5-class safety training.

CORRECTIONS FORCED ON THE DRAFT: the hypothesis mis-states Basu 2603.18353 (zero-and-zero is the SAE arm ONLY; Arm 1 corrected 17/85 and disrupted 25/47; TSV 19/79 and 4/65); the planner's dose figures for 2512.13655 (minimum effective dose, >=30% bypass, 0.028 MMLU) are FABRICATED and absent across all three rungs; SRP's safety-audit mention is Future Work not abstract; Arditi does NOT logit-lens the refusal direction. Bibliography: Arditi = 7 authors + NeurIPS 2024, 2606.16349 = 6 authors not 1, 2606.22676 = 8 not 1, 2604.18901 MUST BE ADDED. HRCI_repr (G10) is NOT reimplementable as specified - Eq 8's k is never stated; Table 1 implies k=3, which must be declared. NO published behavioural dose curve over abliteration strength exists; the run's causal lane would be first.

KILL X2, X10, and X5-for-novelty. SCREEN ORDER: (1) R-E gap on the abliterated checkpoint, (2) X1, (3) the safe-completion cell of X3."""

FOLLOWUPS = [
 "Does the harm-concept knowing-vs-steering cosine actually VARY across the three Qwen3-4B checkpoints, where arXiv:2606.24952's hallucination-concept version is flat (0.1197 base vs 0.1200 instruct, difference 0.0003)? This is the single load-bearing empirical question left: if it is flat too, X6 collapses into a replication of a published invariance and the run must sell a signature rather than a predictor. Closes by measuring it on the harvest, with 2606.24952's four-model table (0.12/0.20/0.16/0.13) as the comparison scale.",
 "Does arXiv:2603.05773 (DSH) report its Recognition/Execution cosine as a DIFFERENTIATED per-model number anywhere, or only as the universal 'Reflex-to-Dissociation' convergence to a random-vector baseline? Its Figure 1 and Figure 4 show the layer-wise trajectory but its differentiating numbers appear to be behavioural ASR tables. If a per-model cosine table exists in its appendix, X6 drops from PARTIAL to CLOSED and the screen order must change. Closes by a table-aware parse of arxiv.org/html/2603.05773v2 appendices and the anonymous.4open.science/r/DSH release.",
 "Can arXiv:2604.09544's separability be reduced to a single comparable per-model scalar, and has anyone done it? Their Figure 4 and Figure 14 report utility-harmfulness TRADE-OFF CURVES per checkpoint, not a scalar, and Figure 13 reports only a Pearson r=0.656 between harmfulness reduction and post-pruning refusal increase. If the area under that trade-off curve is a usable per-checkpoint safety scalar, it is both the strongest baseline this run faces and a possible reformulation of X1. Closes by reading Appendices G and H and the B-TAP release for per-checkpoint aggregate numbers.",
 "Is the Jorak Model Scanner's 4-model validation reproducible at the 273-checkpoint scale of arXiv:2607.01854, and does its parent-free suppression signal survive the recipes that audit's failure map misses? The CLOSED verdicts on X2 and X10 rest on a 17-commit non-peer-reviewed repository validated 4/4 on Qwen2.5-0.5B derivatives. A reviewer may not accept that as prior art. Closes by running Jorak's Plan-1 signals over a public abliteration registry and comparing against the audit's reported AUROC 0.95 and its 4-of-57 misses."
]

out={"title":TITLE,"layman_summary":LAYMAN,"summary":SUMMARY,"answer":answer,
     "sources":sources,"follow_up_questions":FOLLOWUPS}
Path('research_out.json').write_text(json.dumps(out,indent=1))

struct={"title":TITLE,"layman_summary":LAYMAN,"summary":SUMMARY,
        "out_expected_files":{"output":"research_out.json"},
        "upload_ignore_regexes":["(^|/)verify_cache/","(^|/)phase3/raw/"],
        "answer":answer,"sources":sources,"follow_up_questions":FOLLOWUPS}
Path('.terminal_claude_agent_struct_out.json').write_text(json.dumps(struct,indent=1))

# validation
assert 12<=len(TITLE)<=90, len(TITLE)
assert 80<=len(LAYMAN)<=250, len(LAYMAN)
assert 500<=len(SUMMARY)<=5000, len(SUMMARY)
idx={s['index'] for s in sources}
assert idx=={i+1 for i in range(len(sources))}, "index gap"
cited=set(int(n) for m in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]",answer) for n in re.split(r"\s*,\s*",m))
bad=cited-idx
for s in sources:
    assert s['url'] and s['title'] and s['summary'], s['index']
    for p in s['supporting_passages']:
        assert p['quote'], s['index']
print("title",len(TITLE),"| layman",len(LAYMAN),"| summary",len(SUMMARY))
print("sources",len(sources),"| cited",sorted(cited),"| unresolved citations",sorted(bad))
print("uncited sources",sorted(idx-cited))
