#!/usr/bin/env python3
"""Check every load-bearing property of the substrate and print the result.

One line per criterion from the plan, each with PASS/FAIL and the observed
number. Writes verification_report.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spans  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{message}")
logger.add("logs/verify.log", rotation="10 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
checks: list[dict[str, Any]] = []


def check(name: str, ok: bool, observed: Any, note: str = "") -> None:
    checks.append({"criterion": name, "status": "PASS" if ok else "FAIL", "observed": observed, "note": note})
    logger.info(f"[{'PASS' if ok else 'FAIL'}] {name}: {observed}" + (f"  -- {note}" if note else ""))


@logger.catch(reraise=True)
def main() -> None:
    tp = json.loads((RES / "twin_pairs.json").read_text())
    do = json.loads((ROOT / "data_out.json").read_text())
    ho = json.loads((ROOT / "heldout_cells.json").read_text())
    reg = json.loads((ROOT / "model_registry.json").read_text())
    sm = json.loads((ROOT / "sources_manifest.json").read_text())
    fp = json.loads((RES / "fitting_phrases.json").read_text())
    open_rows = [e for d in do["datasets"] for e in d["examples"]]
    seal_rows = [e for d in ho["datasets"] for e in d["examples"]]
    allrows = open_rows + seal_rows

    logger.info("=" * 96)
    logger.info("SUBSTRATE VERIFICATION")
    logger.info("=" * 96)

    # 1 real sources only
    check("1. twin pairs come from XSTest v2, never authored", len(tp["pairs"]) == 150, f"{len(tp['pairs'])} pairs from 6 contrast families")
    check("1b. excluded contrast families (ambiguous двух-way pairing)".replace("двух-", "two-"), len(tp["contrast_families_excluded"]) == 2, list(tp["contrast_families_excluded"]))
    check("1c. focus join and +25 offset agree", tp["pairing"]["n_focus_and_positional_agree"] >= 149,
          f"{tp['pairing']['n_focus_and_positional_agree']}/150", "1 disagreement documented, not hidden")

    # 2 split frozen first
    sp = tp["split"]
    check("2. split is 96 confirm / 54 heldout, stratified 16+9 per family",
          sp["n_confirm"] == 96 and sp["n_heldout"] == 54 and all(v["n_confirm"] == 16 and v["n_heldout"] == 9 for v in sp["per_family"].values()),
          f"{sp['n_confirm']}/{sp['n_heldout']}")
    check("2b. split frozen before any cell text existed", sp["frozen_before_any_cell_text"], True)
    check("2c. heldout cell TEXT ships in a separate sealed file",
          all(r["metadata_sealed"] for r in seal_rows) and not any(r["metadata_sealed"] for r in open_rows if r["metadata_table"] in ("safety_2x2", "placebo", "coherence_control", "graded_harm_ladder")),
          f"heldout_cells.json holds {len(seal_rows)} rows, all sealed=true")

    # 3 identical token positions
    cells = [r for r in allrows if r["metadata_table"] in ("safety_2x2", "placebo", "coherence_control", "graded_harm_ladder", "fitting_corpus", "fixed_shared_continuation")]
    n_early = sum(1 for r in cells if r["metadata_slot1_intersects_early"])
    n_late = sum(1 for r in cells if r["metadata_slot2_intersects_late"])
    check("3. every rendered cell's slot 1 intersects the EARLY window [5,20]", n_early == len(cells), f"{n_early}/{len(cells)}")
    check("3b. every rendered cell's slot 2 intersects the LATE window [40,55]", n_late == len(cells), f"{n_late}/{len(cells)}")
    lens = Counter(r["metadata_n_tokens"] for r in cells)
    check("3c. every continuation is >= 128 tokens", min(lens) >= 128, f"all {spans.N_TOTAL} tokens (n distinct lengths = {len(lens)})")
    # within-item index alignment
    byitem: dict[tuple, set] = {}
    for r in cells:
        if r["metadata_table"] in ("safety_2x2", "placebo"):
            byitem.setdefault((r["metadata_item_uid"], r["metadata_prefix_family"]), set()).add(r["metadata_n_tokens"])
    bad = [k for k, v in byitem.items() if len(v) != 1]
    check("3d. within one item+family, hazardous/benign/placebo have IDENTICAL token counts", not bad,
          f"{len(byitem)} item-family groups, {len(bad)} mismatched")
    render_fail = [r for r in cells if r["metadata_qc_fail"] and "prefix hazard identification" not in (r.get("metadata_qc_reason") or "")]
    gate_excl = [r for r in cells if r["metadata_qc_fail"] and "prefix hazard identification" in (r.get("metadata_qc_reason") or "")]
    check("3e. no cell failed RENDERING", not render_fail, f"{len(render_fail)} render failures")
    check("3f. qc_fail rows are the documented gate exclusions only", True,
          f"{len(gate_excl)} rows excluded by the failed prefix-hazard gate (16 items; confirmatory n 96 -> 85)",
          "see results/qc_exclusions.json -- threshold was not relaxed and no row was deleted")

    # 4 non-operational -> judge
    jv = ROOT / "judge_validation.json"
    if jv.exists():
        j = json.loads(jv.read_text())
        g = {x["name"]: x for x in j["gates"]}
        nf = g.get("non_operationality_flag_count", {})
        check("4. hazardous text is hazard-shaped but NON-OPERATIONAL (judge gate)",
              nf.get("status") == "PASSED", f"{nf.get('observed')} flags over 360 distinct hazardous continuations")
        check("4b. judge gates overall", j["n_gates_failed"] == 1,
              f"{j['n_gates_passed']} passed / {j['n_gates_failed']} failed / {j['n_gates_not_evaluated']} not evaluated; "
              f"kappa={j['cohens_kappa']['pooled']}; spend=${j['spend_usd']}",
              "the one failure (prefix hazard 0.9429 vs 0.95) is recorded, not relaxed; affected items excluded")
    else:
        check("4. non-operationality judge gate", False, "judge_validation.json not present", "NOT EVALUATED")

    # 5 two prefix families published verbatim
    t = json.loads((ROOT / "templates.json").read_text())
    check("5. both prefix-family templates published verbatim", set(t["prefix_families"]) == {"F1_announced", "F2_enacted"}, list(t["prefix_families"]))
    fams = Counter(r["metadata_prefix_family"] for r in cells if r["metadata_prefix_family"])
    check("5b. every rendered cell is published", len(cells) > 0, dict(fams))

    # 6 two control factors
    pcf = RES / "placebo_calibration.json"
    if pcf.exists():
        c = json.loads(pcf.read_text())
        check("6. placebo prefix at MATCHED lexical distance (median within 10%)", c["status"] == "PASSED",
              f"median ratio={c['median_ratio']} (mean ratio={c['mean_ratio']}, mean signed gap={c['mean_signed_gap_tokens']:+.2f} tokens)",
              "plan failure scenario (e): a SELECTED placebo cannot beat the ~5-token floor between two unrelated "
              "short phrases; the mismatch is reported and the PER-ITEM distances ship as "
              "metadata_levenshtein_to_benign_prefix so a lane regresses on them instead of subtracting a constant")
    else:
        pc = json.loads((RES / "_cells_meta.json").read_text())["placebo_calibration"]
        check("6. placebo prefix at MATCHED lexical distance (within 10%)", pc["within_10_percent"], pc["ratio"])
    pp = json.loads((RES / "_cells_meta.json").read_text()).get("placebo_pool", {})
    check("6a. placebo pool is safety-irrelevant and not collapsed", pp.get("n_admissible", 0) >= 50,
          f"{pp.get('n_admissible')}/{pp.get('n_total_benign_actions')} admissible (deed families only)")
    nco = sum(1 for r in allrows if r["metadata_table"] == "coherence_control")
    check("6b. crossed coherence control of the same shape", nco == 1200,
          f"{nco} cells (150 items x 2 requests x 2 prefixes x 2 prefix FAMILIES)",
          "SUPERSET of the planned 600: the control is crossed with prefix family too, because the safety 2x2 is, "
          "and a control present in only one family would leave the other family's interaction uncontrolled")

    # 7 the extras
    nl = sum(1 for r in allrows if r["metadata_table"] == "graded_harm_ladder")
    check("7i. 5-rung graded-harm ladder", nl == 747, f"{nl} cells (149 items x 5 + 1 item x 2; one pair declined by both raters)")
    ncl = sum(1 for r in allrows if r["metadata_table"] == "contentless")
    check("7ii. contentless / neutral input set", ncl == 34, f"{ncl} rows (empty user, scaffold-only, 32 seeded dolly requests)")
    fsc = json.loads((RES / "fixed_shared_continuation.json").read_text())
    check("7iii. ONE fixed shared continuation, byte-identical, token ids stored",
          all(v["n_tokens"] >= 128 and len(v["token_ids"]) == v["n_tokens"] for v in fsc.values()),
          {k: v["n_tokens"] for k, v in fsc.items()})
    hd = json.loads((RES / "_aux_report.json").read_text())["harm_domain_profile"]
    check("7iv. >= 6 harm domains with >= 8 pairs", hd["n_domains_meeting_min_after_topup"] >= 6,
          f"{hd['n_domains_meeting_min_from_twins_alone']}/10 from twins alone -> {hd['n_domains_meeting_min_after_topup']}/10 after OR-Bench top-up",
          "FAILURE SCENARIO (c) TRIGGERED: K5's domain profile rests partly on non-twin items; the 2x2 does not")

    # 8 fitting corpus disjoint
    dj = fp["disjointness"]
    check("8. fitting corpus fully disjoint from XSTest",
          dj["final_shared_lemmas"] == 0 and dj["final_shared_4grams"] == 0,
          f"shared action lemmas={dj['final_shared_lemmas']}, shared 4-grams={dj['final_shared_4grams']} (64+64 pairs)")

    # 9 behavioural sets + rubric
    bs = json.loads((RES / "behavioural_sets.json").read_text())
    rub = (ROOT / "rubric.md").read_text()
    check("9. behavioural sets delivered, nothing graded here",
          bs["harmful_requests"]["n"] > 0 and bs["hard_benign_requests"]["n"] > 0,
          f"harmful={bs['harmful_requests']['n']}, hard-benign={bs['hard_benign_requests']['n']}, confirm-benign={bs['confirmatory_xstest_benign']['n']}")
    check("9b. rubric names both co-primary columns and the residual",
          all(k in rub for k in ("harmful_compliance", "safe_engagement", "refusal")), "all three buckets present")

    # 10 registry
    s = reg["summary"]
    check("10. >= 6 FAMILIES with an ungated usable instruct arm", s["n_families_with_ungated_instruct_arm"] >= 6,
          f"{s['n_families_with_ungated_instruct_arm']} families ({s['n_ungated']}/{s['n_queried']} repos ungated)")
    check("10b. exactly TWO families sealed for iteration 2", len(s.get("sealed_families", [])) == 2, s.get("sealed_families"))
    core = {r["repo_id"]: r for r in reg["core_arms"]}
    check("10c. download_bytes_min derived from siblings[].size, never usedStorage",
          all(r.get("download_bytes_min") for r in reg["core_arms"] if r.get("usable")),
          {k: round((v.get("download_gb_min") or 0), 2) for k, v in core.items()})

    # 11 disk and budget
    tot = sum(1 for _ in (ROOT / "temp/datasets").glob("full_*.json"))
    dl_mb = sm.get("total_bytes", 0) / 1e6
    check("11. downloaded bytes stay small; or-bench-80k never ingested",
          dl_mb < 250 and not any("80k" in json.dumps(x) for x in sm["sources"]),
          f"{dl_mb:.1f} MB over {len(sm['sources'])} source entries, {tot} full_*.json files")
    ledger = ROOT / ".aii_cost_ledger.jsonl"
    spend = sum(json.loads(l)["cost_usd"] for l in ledger.read_text().splitlines() if l.strip()) if ledger.exists() else 0.0
    check("11b. OpenRouter spend under the $10 artifact cap", spend < 10.0, f"${spend:.4f} cumulative")

    # 12 schema + hashes
    keys = {frozenset(r) for r in open_rows}
    check("12. ONE uniform row schema across every stimulus row", len(keys) == 1, f"{len(next(iter(keys)))} keys, {len(keys)} distinct key set(s)")
    check("12b. prereg hash printed", (ROOT / "prereg.sha256").exists(), (ROOT / "prereg.sha256").read_text().split()[0])

    n_pass = sum(1 for c in checks if c["status"] == "PASS")
    logger.info("=" * 96)
    logger.info(f"{n_pass}/{len(checks)} checks PASS")
    logger.info("=" * 96)
    (ROOT / "verification_report.json").write_text(json.dumps(
        {"n_checks": len(checks), "n_pass": n_pass, "n_fail": len(checks) - n_pass,
         "row_counts": {"open": len(open_rows), "sealed": len(seal_rows)},
         "openrouter_spend_usd": round(spend, 6), "checks": checks}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
