"""Render research_report.md: the answer plus every table in full."""
import json
from pathlib import Path
WS = Path(__file__).parent
J = lambda p: json.loads((WS / p).read_text())
out = J("research_out.json"); sat = J("saturation_table.json"); T = J("blockT/target_cell_table.json")
V = J("research_verification.json"); M = J("must_not_claim.json"); B = J("bib_changelog.json"); A = J("ams_spec_iter5.json")
c = lambda x: (str(x) if x is not None else "").replace("|", "\\|").replace("\n", " ")
L = [f"# {out['title']}\n", "_Dated 2026-09-22. Web-only; no model loaded; $0.00 spend._\n", out["answer"], "\n---\n"]
L += ["## Table S — saturation (W1–W8, G1–G4)\n", "| id | verdict | confidence | nearest paper | scope | deciding quote | regex | positive control |", "|---|---|---|---|---|---|---|---|"]
for r in sat["rows"]:
    L.append(f"| {r['candidate_id']} | **{r['verdict']}** | {c(r.get('confidence'))} | {c(r.get('deciding_paper'))[:70]} | {c(r.get('scope'))} | {c(r.get('quote'))[:260]} | `{c(r.get('regex_used'))[:80]}` | {c(r.get('positive_control'))[:120]} |")
L += ["\nOrchestrator notes: " + "; ".join(f"{r['candidate_id']}: {r['orchestrator_note']}" for r in sat["rows"] if r.get("orchestrator_note")), "\n"]
cols = ["no_op_or_expression_only_controls","over_refusal_as_an_outcome","OVER_REFUSAL_AS_TARGET_OF_A_PER_CHECKPOINT_INTERNAL_SCORE","logit_baseline","decode_site_readout","causal_test_with_random_or_orthogonal_control"]
L += ["## Table T — over-refusal-as-target (six columns)\n", f"**{T['verdict_line']}**\n", "| paper | id | no-op ctl | OR outcome | **OR as TARGET** | logit | decode | causal+random |", "|---|---|---|---|---|---|---|---|"]
for r in T["rows"]:
    L.append(f"| {c(r.get('paper'))[:45]} | {r.get('arxiv_id')} | " + " | ".join(c((r['cells'].get(k) or {}).get('verdict')) for k in cols) + " |")
L += [f"\nNearest miss: {c(T['nearest_miss'].get('paper'))}. {c(T['nearest_miss'].get('which_subcondition_fails'))[:900]}\n",
      f"2606.08044 ruling: {c(json.dumps(T.get('ruling_2606_08044')))[:900]}\n"]
L += ["## Table A — AMS operational re-pin\n", "| fact | changed since iter-4 | file / lines |", "|---|---|---|"]
for f in A["eight_pinned_facts"]:
    L.append(f"| {c(f['fact'])[:200]} | {f['changed_since_iter4']} | {c(f['code_line_evidence']['file'])} {c(f['code_line_evidence']['lines'])[:60]} |")
L += ["\n| model | padding_side | measured |shift| σ | verdict flip |", "|---|---|---|---|"]
for m, v in A["padding_hazard"]["measured_effect"].items():
    L.append(f"| {m} | {v['padding_side']} | {v.get('abs_shift_harmful_content', v.get('max_abs_shift'))} | {v['verdict_flip']} |")
L += [f"\n**Instruction:** {A['padding_hazard']['OPERATIONAL_INSTRUCTION_FOR_THE_EXPERIMENT_LANE']}\n"]
L += ["## Table B — bibliography changelog\n", "| key | action | verified | evidence |", "|---|---|---|---|"]
for r in B["records"]:
    L.append(f"| {r['key']} | {r['action']} | {r['verified']} | {c(r['evidence_url'])[:90]} |")
L += ["## Table P — must-not-claim ledger\n", "| forbidden claim | owner | quote |", "|---|---|---|"]
for r in M["items"]:
    L.append(f"| {c(r['claim_forbidden'])[:120]} | {c(r['owner_paper'])[:60]} | {c(r['verbatim_quote'])[:200]} |")
L += ["## Table V — verification\n", f"- quotes re-verified: {V['quotes_reverified']}/{V['quotes_total']} ({V['quote_status_counts']})",
      f"- absence claims reproduced with positive control: {V['absence_count_reproduced']}; reclassified screening regexes: {len(V['screening_regexes_misfiled_as_absences'])}",
      f"- ids resolved: {V['ids_resolved']}/{V['ids_total']}; unresolved: {V['unresolved']}", "\n### Deletions / relabels"]
L += [f"- `{c(d['quote'])[:140]}` — {d['url']} — {c(d['reason'])}" for d in V["deletions"]]
L += ["\n### Beyond the fetch horizon (kept separate)"] + [f"- {b['item']}" for b in V["beyond_horizon"]]
L += ["\n### Absence claims reproduced"] + [f"- {c(a.get('claim'))[:160]} — `{c(a.get('zero_regex'))[:70]}` = {a.get('zero_matches')} vs control `{c(a.get('control_regex'))[:40]}` = {a.get('control_matches')}" for a in V["absence_claims"]]
L += ["\n## Sources\n"] + [f"{s['index']}. [{s['title']}]({s['url']}) — {s['summary']}" for s in out["sources"]]
L += ["\n## Follow-up questions\n"] + [f"- {q}" for q in out["follow_up_questions"]]
(WS / "research_report.md").write_text("\n".join(L))
print("report lines:", len(L))
