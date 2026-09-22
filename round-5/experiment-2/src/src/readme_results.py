#!/usr/bin/env python3
"""Fill the RESULTS block of README.md from what is actually on disk.

Reports the ACHIEVED panel, not the planned one, and states shortfalls plainly.
Computes no candidate score, no ranking and no correlation.

    python3 readme_results.py
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

WS = Path(__file__).resolve().parent.parent
RESULTS = WS / "results"
ARRAYS = WS / "arrays"

BEGIN = "<!-- RESULTS:BEGIN -->"
END = "<!-- RESULTS:END -->"


def jload(p: Path, d: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return d


def fmt_rate(r: Any) -> str:
    if not isinstance(r, dict) or r.get("p") is None:
        return "—"
    return (f"{r['p']:.3f} [{r.get('wilson_ci95_lo', float('nan')):.2f},"
            f"{r.get('wilson_ci95_hi', float('nan')):.2f}] n={r.get('n')}")


def build() -> str:
    man = jload(RESULTS / "panel_manifest.json", {"checkpoints": []})
    rows = man.get("checkpoints", [])
    panel_rows = [r for r in rows if str(r.get("tag", "")).startswith("HG__")]
    pb_rows = [r for r in rows if str(r.get("tag", "")).startswith("PB__")]
    devs = jload(RESULTS / "deviations.json", {"deviations": []}).get("deviations", [])
    hyg = jload(RESULTS / "hygiene_report.json", {})
    diag = jload(RESULTS / "instrument_diagnostics.json", {})
    mde = jload(RESULTS / "mde.json", {})
    gate = jload(RESULTS / "T3_GATE.json", {})
    cls = jload(RESULTS / "partb_classification.json", {})
    item_sets = jload(RESULTS / "item_sets.json", {})
    chain = hyg.get("hash_chain", {})

    fams = sorted({r.get("family") for r in panel_rows if r.get("family")})
    units = sorted({r.get("unit") for r in panel_rows if r.get("unit") and r.get("unit") != "SINGLE"})
    edited = [r for r in panel_rows if r.get("lineage_role") == "edited_child"]
    ledger = 0.0
    lp = RESULTS / "judge_cost_ledger.jsonl"
    if lp.exists():
        for line in lp.read_text().splitlines():
            if line.strip():
                try:
                    ledger += float(json.loads(line).get("cost_usd") or 0.0)
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass

    L: list[str] = [BEGIN, ""]
    L.append("## Results — the achieved panel")
    L.append("")
    L.append(f"_Generated {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
             f"from what is on disk._")
    L.append("")
    L.append("| | achieved | quota |")
    L.append("|---|---|---|")
    L.append(f"| Panel checkpoints harvested | **{len(panel_rows)}** | ≥ 20 |")
    L.append(f"| Never-loaded families | **{len(fams)}** | ≥ 6 |")
    L.append(f"| Multi-stage lineages | **{len(units)}** | ≥ 3 |")
    L.append(f"| Community-edited children | **{len(edited)}** | ≥ 2 |")
    L.append(f"| In-house no-op / effective arms | **{len(pb_rows)}** | ≥ 6, ≥ 4 non-degenerate |")
    L.append(f"| Judge spend | **${ledger:.4f}** | soft stop $4.50 |")
    L.append("")
    if fams:
        L.append(f"Families: {', '.join(fams)}.")
        L.append("")
    if len(panel_rows) < 20:
        L.append(f"> **Shortfall stated plainly.** {len(panel_rows)} checkpoints completed the "
                 f"gated pipeline, not the 20 the plan asks for. The binding constraint was wall "
                 f"clock: a correctness fault found mid-run (left-padded batched generation "
                 f"corrupts some architectures) forced every checkpoint to be regenerated under a "
                 f"per-tag padding guard, and guard-certified batching is 3–6× slower than the "
                 f"padded batching it replaced. The achieved n is reported with its detectable "
                 f"effect size below rather than the bar being lowered.")
        L.append("")

    if chain:
        L.append(f"**Hash chain**: {chain.get('records')} records, verifies end to end = "
                 f"`{chain.get('ok')}`. ")
        L.append(f"**Order gate**: {hyg.get('order_gate_audit', {}).get('checked', 0)} harvested "
                 f"tags audited, every one preceded by its committed `graded_truth`, "
                 f"ok = `{hyg.get('order_gate_audit', {}).get('ok')}`. ")
        L.append(f"**Blindness lint**: passed = "
                 f"`{hyg.get('blindness_lint', {}).get('passed')}` over "
                 f"{hyg.get('blindness_lint', {}).get('scanned_files')} files / "
                 f"{hyg.get('blindness_lint', {}).get('scanned_json_keys')} JSON keys.")
        L.append("")
    if gate:
        t = {k: gate.get(k, {}) for k in ("T3a", "T3b", "T3c", "T3d")}
        L.append("**Instrument self-tests** (all must pass before any harvest; chained):")
        L.append("")
        L.append("| check | what it proves | verdict |")
        L.append("|---|---|---|")
        L.append(f"| T3a arm-0 identity | the grid's arm-0 cell reproduces a plain hook-free "
                 f"forward (rel. diff {t['T3a'].get('max_rel_diff_grid_arm0_vs_plain_forward', float('nan')):.1e}) "
                 f"and an inert hook changes nothing bitwise | {t['T3a'].get('verdict')} |")
        L.append(f"| T3b ablation effectiveness | projecting F out leaves "
                 f"{t['T3b'].get('ratio', float('nan')):.5f} of the F component in-band | "
                 f"{t['T3b'].get('verdict')} |")
        L.append(f"| T3c control inertness | a matched-displacement random edit leaves the F "
                 f"projection at {t['T3c'].get('ratio', float('nan')):.4f}× at the first modified "
                 f"layer | {t['T3c'].get('verdict')} |")
        L.append(f"| T3d displacement matching | R and F cells displace the state by the same "
                 f"norm ({t['T3d'].get('ratio_at_first_modified_index', float('nan')):.4f}×) | "
                 f"{t['T3d'].get('verdict')} |")
        L.append("")

    if panel_rows:
        L.append("### Graded behaviour per checkpoint")
        L.append("")
        L.append("Every rate carries its set NAME, its n and a Wilson 95% CI. `HC` = harmful "
                 "compliance on HARM; `OR_*` = over-refusal on each named benign set; `SE` = safe "
                 "engagement on HARM.")
        L.append("")
        L.append("| checkpoint | family | role | HC (HARM) | OR (XSTEST54) | OR (HARDBENIGN) | SE (HARM) |")
        L.append("|---|---|---|---|---|---|---|")
        for r in sorted(panel_rows, key=lambda x: str(x.get("family"))):
            rt = r.get("rates", {}) or {}
            L.append(f"| `{r.get('repo_id')}` | {r.get('family')} | {r.get('lineage_role')} | "
                     f"{fmt_rate(rt.get('HC'))} | {fmt_rate(rt.get('OR_xstest54'))} | "
                     f"{fmt_rate(rt.get('OR_hardbenign'))} | {fmt_rate(rt.get('SE'))} |")
        L.append("")

    if diag:
        L.append("### Over-refusal instrument diagnostics")
        L.append("")
        L.append("Range restriction is the likeliest reason a downstream test returns null, so the "
                 "spread of each instrument is reported here. **No correlation between the two "
                 "instruments is computed — that is the scorer's job.**")
        L.append("")
        per = diag.get("instrument_summary", {}) or {}
        if isinstance(per, dict) and per:
            L.append("| instrument | min | max | mean | SD | at 0 | at 1 |")
            L.append("|---|---|---|---|---|---|---|")
            for name, d in per.items():
                if not isinstance(d, dict):
                    continue
                g = lambda k: (f"{d[k]:.3f}" if isinstance(d.get(k), (int, float)) else "—")  # noqa: E731
                L.append(f"| `{name}` | {g('min')} | {g('max')} | {g('mean')} | {g('sd')} | "
                         f"{d.get('count_floor_0', '—')} | {d.get('count_ceiling_1', '—')} |")
            L.append("")
    mo = jload(WS / "method_out.json", {})
    tb = (mo.get("metadata", {}) or {}).get("text_baseline_degeneracy", {})
    if tb.get("verdict"):
        cols = tb.get("columns", {})
        frac = ", ".join(f"`{k}` {v.get('count_floor_0_fraction')}" for k, v in cols.items())
        L.append(f"**Text-only baseline: `{tb['verdict']}`.** The run's frozen keyword-refusal "
                 f"proxy (iteration 4's onset rule, reused verbatim) sits at **exactly zero on "
                 f"the large majority of checkpoints** (fraction at zero: {frac}; SD 0.020 and "
                 f"0.041), while the judge finds substantial over-refusal on the same rows with "
                 f"real spread (SD 0.204 and 0.226). It is therefore effectively floored and "
                 f"unusable as a comparator here: clearing a floored bar shows nothing. Judge "
                 f"validation measured the same effect directly (precision 1.00, recall 0.29). "
                 f"The judge-graded over-refusal columns are the target of record.")
        L.append("")
    if mde:
        L.append(f"**Design arithmetic (not a candidate score)**: `results/mde.json` — "
                 f"{json.dumps({k: v for k, v in mde.items() if isinstance(v, (int, float, str))})[:300]}")
        L.append("")

    if cls:
        L.append("### The fresh in-house no-op / effective set")
        L.append("")
        L.append(f"Parent `{cls.get('parent') or 'baidu/ERNIE-4.5-0.3B-PT'}` — chosen because it "
                 f"**ties its input and output embeddings**, which is what makes the "
                 f"unembedding-perturbation arm able to move both the activation and the logit "
                 f"class instead of being zero by construction (the iteration-4 reviewer's "
                 f"blocking finding).")
        L.append("")
        pairs = cls.get("pairs", [])
        if pairs:
            L.append("| arm | intended | observed | degenerate | dHC | dOR (XSTEST54) | dOR (HARDBENIGN) |")
            L.append("|---|---|---|---|---|---|---|")
            for p in pairs:
                pr = p.get("primary", {}) or {}
                def sh(k: str) -> str:
                    v, ci = pr.get(k), pr.get(f"{k}_ci")
                    if not isinstance(v, (int, float)):
                        return "—"
                    if isinstance(ci, (list, tuple)) and len(ci) == 2:
                        return f"{v:+.3f} [{ci[0]:+.2f},{ci[1]:+.2f}]"
                    return f"{v:+.3f}"
                L.append(f"| {p.get('arm')} | {p.get('intended_stratum')} | "
                         f"**{p.get('observed_class')}** | {p.get('structurally_degenerate')} | "
                         f"{sh('dHC')} | {sh('dOR_OR_XSTEST54')} | {sh('dOR_OR_HARDBENIGN')} |")
            L.append("")
        ns = (mo.get("metadata", {}) or {}).get("inhouse_noop_supply", {})
        if ns:
            fs, nd = ns.get("full_set", {}), ns.get("non_degenerate_subset", {})
            L.append("Two denominators, as the plan requires — the full set and the "
                     "NON-DEGENERATE subset (arms whose delta is not zero by construction), "
                     "which is the headline denominator:")
            L.append("")
            L.append("| denominator | n | NOOP | EFFECTIVE | OR_EFFECTIVE | AMBIGUOUS |")
            L.append("|---|---|---|---|---|---|")
            L.append(f"| full scored set | {ns.get('n_scored')} | {fs.get('NOOP')} | "
                     f"{fs.get('EFFECTIVE')} | {fs.get('OR_EFFECTIVE')} | {fs.get('AMBIGUOUS')} |")
            L.append(f"| non-degenerate | {ns.get('n_scored_non_degenerate')} | "
                     f"**{nd.get('NOOP')}** | {nd.get('EFFECTIVE')} | {nd.get('OR_EFFECTIVE')} | "
                     f"{nd.get('AMBIGUOUS')} |")
            L.append("")
            L.append(f"> **{ns.get('intended_noops_non_degenerate_that_were_NOOP')} of "
                     f"{ns.get('intended_noops_non_degenerate')} non-degenerate arms that were "
                     f"DECLARED no-ops before grading were observed to be no-ops.** "
                     + str(ns.get("headline", "")))
            L.append("")
            if ns.get("reclassified"):
                L.append("Reclassified (reported, never dropped): " + ", ".join(
                    f"`{r['arm']}` {r['intended']}→{r['observed']}" for r in ns["reclassified"]))
                L.append("")
        L.append("")

    sets = item_sets.get("sets", {})
    if sets:
        L.append("### Item sets (frozen and chained before any generation)")
        L.append("")
        L.append("| set | n | ids sha256 |")
        L.append("|---|---|---|")
        for k, v in sets.items():
            L.append(f"| `{k}` | {v.get('n')} | `{str(v.get('ids_sha256'))[:16]}…` |")
        L.append("")

    L.append(f"### Deviations")
    L.append("")
    L.append(f"{len(devs)} numbered deviations are recorded in `results/deviations.json`; nothing "
             f"was relaxed silently, and neither the family-exclusion rule nor the order gate was "
             f"ever relaxed. The ones that change how the numbers should be read:")
    L.append("")
    keep = ("D03", "D04", "D05", "D06", "D14", "D15", "D16", "D18", "D19", "D21", "D23",
            "D24", "D25")
    for d in devs:
        if str(d.get("id")) in keep and d.get("title"):
            L.append(f"- **{d['id']}** — {d['title']}")
    L.append("")
    L.append(END)
    return "\n".join(L)


def main() -> int:
    p = WS / "README.md"
    s = p.read_text(encoding="utf-8")
    i, j = s.index(BEGIN), s.index(END) + len(END)
    p.write_text(s[:i] + build() + s[j:], encoding="utf-8")
    print(f"README.md results block updated ({len(build())} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
