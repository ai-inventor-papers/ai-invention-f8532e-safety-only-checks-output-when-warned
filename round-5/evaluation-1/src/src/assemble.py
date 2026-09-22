"""S12 self-check gate + S13 contradictions ledger + eval_out.json assembly.

Merges every results/*.json table emitted by the deliverable scripts, computes
the claim match rate, runs the programmatic gate, and writes eval_out.json in
the exp_eval_sol_out schema. The gate runs BEFORE eval_out.json is written.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
RES = WS / "results"

DELIVERABLE_FILES = {
    "D1": "table_composition.json",
    "D2": "table_degeneracy.json",
    "D3": "table_bl1_variants.json",
    "D4": "table_candidates32.json",
    "D5": "table_causal_grid.json",
    "D6": "table_equivalence.json",
    "D7": "table_fewprompt.json",
    "D8": "table_displacement.json",
    "D9": "table_geometry.json",
    "D10": "table_setup_deviations.json",
    "D11": "join_backstop.json",
}

# Addenda produced beside the 11 deliverables. They are not counted by gate (d),
# but every row they emit is held to gate (a) like any other table.
ADDENDUM_FILES = {
    "D4+": "table_sensitivity_denominators.json",
    "D7+": "table_panel_power.json",
}

# Gate (b): no sentence may name a BASELINE-class readout as the deliverable /
# answer / winner / metric. Baselines are logit-only, text-only and card-only.
BASELINE_NAMES = r"(BL1[A-Za-z_]*|AMS[ _]?(?:T1|T2|sigma)?|card[ /-]?name regex|card regex|name regex|greedy refusal[- ]text|greedy refusal text bar|B7(?:_nullproj)?)"
WINNER_WORDS = r"(is|are|as|remains|becomes|named|chosen|selected)\s+(?:the\s+)?(?:our\s+)?(deliverable|answer|winner|winning|the metric|our metric|proposed metric|the result|headline metric|best (?:candidate|readout|metric)|survivor)"
GATE_B_RE = re.compile(BASELINE_NAMES + r"[^.]{0,120}?" + WINNER_WORDS, re.IGNORECASE)
GATE_B_RE_REV = re.compile(r"(the\s+)?(deliverable|answer|winner|the metric|our metric|proposed metric|headline metric)\s+(is|are)\s+[^.]{0,60}?" + BASELINE_NAMES, re.IGNORECASE)


def load(name: str) -> Any | None:
    p = RES / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def iter_rows(obj: Any) -> list[dict[str, Any]]:
    """Collect every emitted TABLE ROW.

    A ROW is a dict that appears as an ELEMENT OF A LIST and carries provenance
    (source_file) or a readout_class. The top-level container object of a table
    file is not a row even when it carries a file-level source_file, so it is
    never counted against gate rule (a).
    """
    out: list[dict[str, Any]] = []
    # (value, is_list_element)
    stack: list[tuple[Any, bool]] = [(obj, False)]
    seen: set[int] = set()
    while stack:
        cur, is_elem = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, dict):
            if is_elem and ("source_file" in cur or "readout_class" in cur):
                out.append(cur)
            for v in cur.values():
                stack.append((v, False))
        elif isinstance(cur, list):
            for v in cur:
                stack.append((v, True))
    return out


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def collect_ledger() -> list[dict[str, Any]]:
    """Prefer the ADJUDICATED ledger (src/adjudicate_ledger.py): one frozen rule,
    deduplicated, every override explained. Fall back to the raw agent ledgers."""
    adj = RES / "ledger_adjudicated.json"
    if adj.exists():
        try:
            return list(json.loads(adj.read_text())["claims"])
        except (json.JSONDecodeError, KeyError):
            pass
    rows: list[dict[str, Any]] = []
    for p in sorted(RES.glob("contradictions_*.json")):
        try:
            obj = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        cand = obj if isinstance(obj, list) else obj.get("claims") or obj.get("contradictions") or obj.get("ledger") or []
        if isinstance(cand, dict):
            cand = list(cand.values())
        for c in cand:
            if isinstance(c, dict) and "verdict" in c:
                c.setdefault("ledger_file", p.name)
                rows.append(c)
    return rows


def main() -> None:
    report: dict[str, Any] = {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat()}
    failures: list[str] = []
    warnings: list[str] = []

    # ---------------- gate (d): all 11 deliverables produced ----------------
    present: dict[str, Any] = {}
    missing: list[str] = []
    for did, fname in DELIVERABLE_FILES.items():
        obj = load(fname)
        if obj is None or (isinstance(obj, (list, dict)) and len(obj) == 0):
            missing.append(f"{did} ({fname})")
        else:
            present[did] = obj
    report["deliverables_present"] = sorted(present)
    report["deliverables_missing"] = missing
    if missing:
        failures.append(f"GATE_D: deliverables with no non-empty artifact: {missing}")

    # ---------------- gate (a): every table row has source_file + readout_class
    bad_rows: dict[str, int] = {}
    total_rows = 0
    for did, obj in present.items():
        rows = iter_rows(obj)
        total_rows += len(rows)
        n_bad = sum(1 for r in rows if not r.get("source_file") or not r.get("readout_class"))
        if n_bad:
            bad_rows[f"{did}:{DELIVERABLE_FILES[did]}"] = n_bad
    for aid, fname in ADDENDUM_FILES.items():
        obj = load(fname)
        if obj is None:
            continue
        rows = iter_rows(obj)
        total_rows += len(rows)
        n_bad = sum(1 for r in rows if not r.get("source_file") or not r.get("readout_class"))
        if n_bad:
            bad_rows[f"{aid}:{fname}"] = n_bad
    report["total_table_rows"] = total_rows
    report["rows_missing_provenance"] = bad_rows
    if bad_rows:
        failures.append(f"GATE_A: rows missing source_file or readout_class: {bad_rows}")

    # ---------------- gate (e): candidate table has >= 32 rows ----------------
    cand = present.get("D4")
    n_cand = 0
    if cand is not None:
        rows = cand if isinstance(cand, list) else (cand.get("candidates") or cand.get("rows") or cand.get("table") or [])
        if isinstance(rows, dict):
            rows = list(rows.values())
        n_cand = len(rows)
    report["candidate_table_rows"] = n_cand
    if n_cand < 32:
        failures.append(f"GATE_E: candidate table has {n_cand} rows, need >= 32")

    # ---------------- gate (c): prereg sha256 unchanged ----------------
    prereg = WS / "prereg_eval.json"
    frozen = (WS / "prereg_eval.sha256").read_text().split()[0].replace("sha256=", "").strip()
    live = sha256_file(prereg)
    report["prereg_sha256_frozen"] = frozen
    report["prereg_sha256_now"] = live
    if frozen != live:
        failures.append(f"GATE_C: prereg sha256 changed {frozen} -> {live}")

    # ---------------- gate (f): no model-weight cache in the workspace -------
    weight_hits = []
    for pat in ("**/*.safetensors", "**/*.bin", "**/*.gguf", "**/*.pt", "**/*.pth"):
        for p in WS.glob(pat):
            if ".venv" in p.parts:
                continue
            if p.stat().st_size > 100 * 1024 * 1024:
                weight_hits.append(str(p.relative_to(WS)))
    report["oversized_weight_files"] = weight_hits
    if weight_hits:
        failures.append(f"GATE_F: model-weight-sized files present: {weight_hits}")

    # ---------------- S13 ledger + claim match rate ----------------
    ledger = collect_ledger()
    counts = {"MATCH": 0, "MISMATCH": 0, "UNVERIFIABLE": 0, "SOURCE_ABSENT": 0}
    for c in ledger:
        v = str(c.get("verdict", "")).upper()
        if v in counts:
            counts[v] += 1
    denom = counts["MATCH"] + counts["MISMATCH"]
    rate = (counts["MATCH"] / denom) if denom else float("nan")
    ledger_obj = {
        "definition": (
            "claim_match_rate = MATCH / (MATCH + MISMATCH). UNVERIFIABLE and SOURCE_ABSENT "
            "are reported separately and are NEVER folded into the denominator."
        ),
        "tolerance_rule": {
            "counts": "EXACT",
            "rates_and_effect_sizes": "|delta| <= 5e-4",
            "nats": "<= 1e-3",
            "correlations": "<= 5e-3",
        },
        "counts": counts,
        "n_claims": len(ledger),
        "claim_match_rate": rate,
        "claims": ledger,
    }
    adj_doc = json.loads((RES / "ledger_adjudicated.json").read_text()) if (RES / "ledger_adjudicated.json").exists() else {}
    if adj_doc:
        ledger_obj["secondary_rounding_aware"] = adj_doc.get("secondary_rounding_aware")
        ledger_obj["adjudication"] = adj_doc.get("adjudication")
        report["claim_match_rate_rounding_aware_posthoc"] = (adj_doc.get("secondary_rounding_aware") or {}).get("claim_match_rate")
    (RES / "contradictions.json").write_text(json.dumps(ledger_obj, indent=2, default=str))
    report["claim_counts"] = counts
    report["claim_match_rate"] = rate
    if len(ledger) < 35:
        warnings.append(f"S13: ledger has {len(ledger)} claims, target was >= 35")

    # ---------------- gate (b): baseline-as-deliverable regex scan ----------
    gate_b_hits: list[dict[str, str]] = []
    scan_targets = [WS / "SUMMARY.md"] + sorted(RES.glob("*.json"))
    for p in scan_targets:
        if not p.exists() or p.name in {"contradictions.json", "source_manifest.json"}:
            continue
        txt = p.read_text(errors="replace")
        # split into sentences over the raw text; JSON prose fields are covered
        for sent in re.split(r"(?<=[.!?])\s+|\\n", txt):
            if len(sent) > 600:
                continue
            for rx in (GATE_B_RE, GATE_B_RE_REV):
                m = rx.search(sent)
                if m:
                    # exempt explicit negations / baseline-labelling sentences
                    if re.search(r"\b(not|never|baseline|baselines|rather than|instead of|is NOT)\b", sent, re.I):
                        continue
                    gate_b_hits.append({"file": p.name, "sentence": sent.strip()[:300], "match": m.group(0)[:160]})
    report["gate_b_hits"] = gate_b_hits
    if gate_b_hits:
        failures.append(f"GATE_B: {len(gate_b_hits)} sentence(s) name a baseline-class readout as the deliverable")

    report["failures"] = failures
    report["warnings"] = warnings
    report["gate_passed"] = not failures
    (RES / "self_check_gate.json").write_text(json.dumps(report, indent=2))

    print(json.dumps({k: report[k] for k in (
        "gate_passed", "deliverables_present", "deliverables_missing",
        "total_table_rows", "candidate_table_rows", "rows_missing_provenance",
        "claim_counts", "claim_match_rate", "failures", "warnings")}, indent=2, default=str))
    for h in gate_b_hits[:10]:
        print("GATE_B HIT:", h)
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()
