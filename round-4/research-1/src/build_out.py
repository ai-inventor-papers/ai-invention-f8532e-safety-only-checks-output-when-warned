"""Assemble research_out.json, research_report.md and .terminal_claude_agent_struct_out.json."""
import json, re
from pathlib import Path
from sources_passages import SOURCES
WS = Path(__file__).parent
ver = json.load(open(WS / "research_verification.json"))
ok = {(p["source_index"], p["passage"]) for p in ver["passages"] if p["verified"]}
answer = (WS / "answer.md").read_text()
bib = (WS / "references_verified.bib").read_text()
keys = ["Orgad2026", "Yamaguchi2025", "Obliteratus2026", "Wollschlager2025", "LlorenteSaguer2026a", "LlorenteSaguer2026b",
        "Messenger2026", "Waldis2026", "FonsecaRivera2026", "Jorak2026", "QwenSafeRL2026", "Duan2026", "YangFirstToken2026", "Bosco2026", "Kadadekar2026"]
ents = {m.group(1): m.group(0) for m in re.finditer(r"(?ms)^@\w+\{([^,]+),.*?^\}", bib)}
missing = [k for k in keys if k not in ents]; assert not missing, missing
answer += "\n\n## Appendix: key BibTeX entries (full file: references_verified.bib)\n```bibtex\n" + "\n".join(ents[k] for k in keys) + "\n```\n"
cited = {int(x) for grp in re.findall(r"\[([\d,\s\-]+)\]", answer) for part in grp.split(",") for x in
         ([part] if "-" not in part else range(int(part.split("-")[0]), int(part.split("-")[1]) + 1)) if str(x).strip().isdigit()}
idx = {s["i"] for s in SOURCES}
assert cited <= idx, cited - idx
sources = [dict(index=s["i"], url=s["url"], title=s["title"], summary=s["summary"], authors=s["authors"], year=s["year"],
                supporting_passages=[dict(quote=q, locator=l) for q, l in s["passages"] if (s["i"], q) in ok]) for s in SOURCES]
title = "Is our safety-readout audit still unclaimed?"
summary = (
 "Web-only prior-art and bibliography pass, 2026-09-21, $0 spend. 62/62 quoted passages re-verified by independent live re-fetch; 36 sources.\n"
 "VERDICT: the iteration-4 empty cell is OPEN but NARROWER. No paper has both C1 (no-op/false-alarm controls) and C2 (over-refusal) CLOSED. "
 "Closest new paper: arXiv:2609.18471 'First Token Matters' (2026-09-16), which has a decode-site readout at generated tokens, Logit-Lens, two-sided steering and XSTest, "
 "but no no-op controls; its XSTest is a behavioural outcome of defences and it covers only 2 R1-distilled checkpoints. "
 "New C1 neighbour: Duan arXiv:2606.15980 freezes probes (incl. an XSTest refusal-compliance probe) across 12 quantisation/LoRA/QLoRA updates on Qwen2.5-7B/Gemma-2-2B. "
 "It scores per-input AUC, not a per-checkpoint score, and does not grade behaviour. Other C1 PARTIALs: AMS (single-model FP16/INT8/INT4, drift ≤4.4%), "
 "Aligned Probing (toxicity quantisation, OLMo), Hurtado 2607.01854 (37 benign fine-tunes, FPR 0.11, reference-anchored). "
 "Also new: 2609.04721 (XSTest+OR-Bench gate, orthogonalised-random controls). N-GLARE's Refusal Rate is keyword refusal on HARMFUL prompts, so it is NOT over-refusal. "
 "'Messenger 2026 IEEE Access' IS AMS 2608.05578.\n"
 "SURVIVING CLAIM: per-checkpoint false-alarm audit on BEHAVIOURALLY GRADED no-ops (casts, re-downloads, non-safety LoRA/DPO; template on/off as a graded expression arm) "
 "+ over-refusal as the TARGET of internal readouts (OPEN everywhere) + logit gap AND AMS σ side by side + site-local matched-norm vs orthogonal-random test.\n"
 "SPECIFICITY PRECEDENT: none direct. Adjacent: template/system prompt change BEHAVIOUR (Arditi: Llama-2 22.6 vs 79.9% ASR; Qwen flat; ChatBug), "
 "quantisation usually preserves refusal but not always (SmolLM3; Kadadekar 12-68 pt drops). So every no-op must be graded. "
 "Frozen probes go stale under LoRA (43.2-53.8% big-drop), so activation readouts may FAIL specificity; pre-register both outcomes.\n"
 "AMS BAR (code-pinned): in-sample argmax σ over layers int(0.4L)..int(0.8L) (Qwen3-4B: 14-27); last position hidden_states[:,-1,:]; raw text, NO chat template; "
 "1-D diff-of-means, pooled_std=sqrt((var+ + var-)/2); fp16 default, CPU forces fp32; harmful_content 16 pairs (no verbatim XSTest/AdvBench/JBB overlap); Tier-2 cos≥0.8 & drift≤0.2 (code). "
 "HAZARD: batch 8 + padding=True + no padding_side, and Qwen3 configs leave padding_side unset, so pad positions may be read. Run both batch 8 (as released) and batch 1.\n"
 "BIB: references_verified.bib (54 entries). Orgad=2604.09544 (7 authors); Yamaguchi=2507.03167 (Kureha Yamaguchi, Benjamin Etheridge, Andy Arditi; ICML'25 R2FM); "
 "OBLITERATUS @misc cb4aec45 AGPL-3.0 CrossLayerAlignmentAnalyzer; stub ids added; author/year fixes. '0.016' = DELETE (unsourced across 282 repo files and 3 PDFs); "
 "do not substitute Galeone's 0.12-0.20. PRUNE Li2023, Meng2022, Wei2023, Yuan2024; KEEP the other 11.\n"
 "MUST-NOT-CLAIM adds: first readout-under-quantisation, first benign-fine-tune FPR, first decode-site readout, first logit-vs-activation comparison, first random-direction control, "
 "'logit metrics known template-sensitive', AMS weight hashing, AMS applies templates.")
assert len(summary) <= 5000, len(summary)
follow = [
 "Does the refusal-logit gap or the activation readout raise more false alarms on Qwen3-4B under non-safety LoRA/DPO, where Duan finds frozen probes go stale at 43-54% big-drop rates, when behaviour is graded unchanged?",
 "How much does AMS σ on Qwen3-4B change between the released batch-8 right-padded path and a pad-safe batch-1 run, and does the gap flip any PASS/WARNING/CRITICAL level across base/instruct/SafeRL/abliterated?",
 "Does any per-checkpoint internal readout predict XSTest over-refusal rate across the panel beyond what the logit gap explains, and does the answer survive the chat-template expression arm?",
]
layman = "Checks whether anyone has already published our planned test of cheap internal safety scores for AI models, pins down how the main rival tool really works, and fixes the paper's reference list."
out = dict(title=title, layman_summary=layman, summary=summary, answer=answer, sources=sources, follow_up_questions=follow)
json.dump(out, open(WS / "research_out.json", "w"), indent=1, ensure_ascii=False)
struct = dict(out, out_expected_files={"output": "research_out.json"}, upload_ignore_regexes=[r"(^|/)verify_cache/", r"(^|/)__pycache__/"])
json.dump(struct, open(WS / ".terminal_claude_agent_struct_out.json", "w"), indent=1, ensure_ascii=False)
rep = f"# {title}\n\n{summary}\n\n---\n\n{answer}\n\n## Sources\n" + "\n".join(
    f"[{s['index']}] {s['title']} — {s['url']}\n    {s['summary']}" + "".join(f"\n    > \"{p['quote']}\" ({p['locator']})" for p in s['supporting_passages']) for s in sources)
rep += "\n\n## Follow-up questions\n" + "\n".join(f"- {q}" for q in follow) + "\n"
(WS / "research_report.md").write_text(rep)
print("ok", len(answer), len(summary), len(sources), sum(len(s['supporting_passages']) for s in sources), sorted(idx - cited))
