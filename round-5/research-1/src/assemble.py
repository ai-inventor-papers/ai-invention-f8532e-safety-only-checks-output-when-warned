"""Assemble research_out.json, research_report.md and .terminal_claude_agent_struct_out.json."""
import json, re
from pathlib import Path
WS = Path(__file__).parent
answer = (WS / "blockP/answer.md").read_text()
sources = json.loads((WS / "verify/_sources.json").read_text())
n = len(sources)
cited = set()
for m in re.finditer(r"\[([\d,\s–-]+)\]", answer):
    for part in m.group(1).split(","):
        part = part.strip()
        if re.fullmatch(r"\d+[–-]\d+", part):
            a, b = map(int, re.split(r"[–-]", part)); cited.update(range(a, b + 1))
        elif part.isdigit():
            cited.add(int(part))
bad = sorted(c for c in cited if c < 1 or c > n)
assert not bad, f"unresolvable citations: {bad}"
print(f"citations used: {len(cited)} distinct, all resolve to 1..{n}; uncited sources: {sorted(set(range(1,n+1))-cited)}")

title = "Is our redundancy safety metric already taken?"
summary = (
 "Dated web-only prior-art closure pass, 2026-09-22, $0.00 spend. SATURATION: none of the 12 candidates is CLOSED. "
 "W1, W3, W4, G2, G4 OPEN; W5, W6 OPEN on inherited evidence only; W2, W7, W8, G1, G3 PARTIAL. "
 "Nearest neighbours: SafeSeek 2603.23268 (W2, per-scenario joint-ablation circuit size), Conditional Co-Ablation 2607.01940 "
 "(W4, per-unit self-repair score, 0 checkpoint-framing matches vs 143 control), Any-Depth Alignment 2510.18081 (W3/W7), "
 "Jorak (re-located live, github.com/JolanMc/Jorak) and OBLITERATUS (W8), Galeone 2606.24952 (G3). "
 "W4 attribution sentence written against verified anchors: Hydra Effect 2307.15771 and Rushing & Nanda 2402.15390 (ICML 2024). "
 "Forward-citation sweep of 136 citing papers found no per-model self-repair scalar. "
 "OVER-REFUSAL-AS-TARGET: OPEN across 14 scored papers. Nearest miss 2609.18471 fails the target test and N>=3; "
 "2609.00760 has over-refusal and probe columns never correlated; 2606.08044 never correlates its LVS with over-refusal "
 "('correlat' 0 matches, controls 4/49). DIMENSIONALITY: no factor-analytic/effective-rank treatment of a family of INTERNAL "
 "safety scores exists, so the P1 bound is a contribution. Position it against IRT-for-AI-Safety 2608.05086 (output-level, 3 factors, 77% variance) "
 "and The Hidden Dimensions of LLM Alignment 2502.09674; a verbatim sentence separating score-family rank from refusal-subspace rank is supplied. "
 "AMS: repo and PyPI unchanged; the padding hazard is now established from code AND measurement. All 4 Qwen3-4B tokenizers and Falcon3 "
 "omit padding_side, so they inherit HF's 'right'. Measured batch-8 shift is up to 5.283 sigma on Falcon3 (PASS->CRITICAL); left-padded Llama shifts 1.4e-06. "
 "Rule: batch-1 is the bar, batch-8 is footnoted. CORRECTIONS: 'Spagliardi' is REAL (arXiv:2606.20626), so do NOT substitute 2608.05086; the "
 "handbook DOES name Basu 2603.18353; no JailbreakBench/Mazeika misattribution existed (both benchmarks were absent, now added); a composite "
 "quote had turned 'last generated token' into 'last prompt token' and was deleted; reimplementation agreement is 7.3e-05 relative, not <1e-4 absolute. "
 "Verification: 48/48 quotes re-fetched by a non-finder; 4 composites deleted; 5 paraphrases relabelled; 8 absences reproduced with controls; 23/23 ids resolved. "
 "Bibliography: 61 entries (7 added, 4 pruned, 0.016 deleted). Must-not-claim ledger: 23 items with owners."
)
follow = [
 "Does any paper posted after 2026-09-22 score >=3 checkpoints with a single internal number against XSTest/OR-Bench over-refusal? Re-sweep arXiv cs.CL/cs.LG weekly until submission. That one paper would move the study to Branch 3 and demote the correlation table to a replication.",
 "Do W5 and W6 survive a dedicated search? Their OPEN verdict is inherited from W1's single Galeone control. A W5-specific query family (benign-twin / XSTest-safe axis ablation gain per model) should be run before either is called a contribution.",
 "Is W2's SafeSeek neighbour closer than it looks on a model panel? Check whether SafeSeek's released code reports circuit sparsity for more than one model and whether that number is ever compared across checkpoints; if so, W2 moves from PARTIAL to CLOSED and contribution (iii) weakens to Branch 2.",
]
out = {"title": title, "summary": summary, "answer": answer, "sources": sources, "follow_up_questions": follow}
(WS / "research_out.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))

struct = {
 "title": title,
 "layman_summary": "Checks whether the new safety measurements this project wants to publish have already been invented by someone else, and fixes the citations and tool settings the paper relies on.",
 "summary": summary,
 "out_expected_files": {"output": "research_out.json"},
 "upload_ignore_regexes": [],
 "answer": answer,
 "sources": [{k: s[k] for k in ("index", "url", "title", "summary", "authors", "year", "supporting_passages")} for s in sources],
 "follow_up_questions": follow,
}
(WS / ".terminal_claude_agent_struct_out.json").write_text(json.dumps(struct, indent=1, ensure_ascii=False))
print("summary chars:", len(summary), "| answer words:", len(answer.split()), "| sources:", n)
