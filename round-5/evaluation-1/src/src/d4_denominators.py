"""D4 addendum: recompute every sensitivity denominator for the 10- and 11-pair
effective sets that the FROZEN iteration-4 count rule implies.

Why this exists. classification.json's count rule counts
    "constructed + primary harvested + AMD count when observed EFFECTIVE".
HG::amd--AMD-OLMo-1B-SFT-DPO was planned as a harvested NO-OP
(intended_stratum NOOP_HARVESTED) and was OBSERVED EFFECTIVE, so by that clause
it belongs in the effective set: 10 pairs, not the 9 of primary_effective_pairs.
The same rule says a constructed pair "is RECLASSIFIED to its observed class and
reported, never dropped"; F1__cautious (constructed, observed EFFECTIVE) is
omitted although F1__dpo, counted under that very clause, is included - so a
literal reading gives 11.

Method. The official per-pair hit is reproduced from pairs_long.json as
    hit = CI excludes 0  AND  sign(Delta) == expected_sign_vs_HC * sign(dHC_pair)
and VALIDATED against aggregates.json's per_pair hits on the official 9 pairs for
every candidate. A candidate's 10/11-pair value is emitted only if its official
9-pair hits reproduce EXACTLY; otherwise it is UNVERIFIABLE, never guessed.

This script is idempotent: it augments results/table_candidates32.json in place
and writes results/table_sensitivity_denominators.json.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
I4 = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1/results")
AGG_F = I4 / "aggregates.json"
CLS_F = I4 / "classification.json"
PL_F = I4 / "scores" / "pairs_long.json"

AMD_DPO = "HG::amd--AMD-OLMo-1B-SFT-DPO"
CAUTIOUS = "F1__cautious"


def sgn(x: float) -> int:
    return (x > 0) - (x < 0)


def pair_dhc(p: dict[str, Any]) -> float | None:
    """dHC of a pair from its own classification record (primary, then laneC)."""
    for block in ("primary", "laneC"):
        b = p.get(block)
        if isinstance(b, dict):
            for k in ("dHC", "delta_HC", "dhc"):
                if isinstance(b.get(k), (int, float)):
                    return float(b[k])
    if isinstance(p.get("primary_dHC"), (int, float)):
        return float(p["primary_dHC"])
    return None


def hit_from_long(row: dict[str, Any], exp_vs_hc: int, dhc: float) -> bool | None:
    if row.get("ci_lo") is None or row.get("ci_hi") is None or row.get("Delta") is None:
        return None
    excl = row["ci_lo"] > 0 or row["ci_hi"] < 0
    return bool(excl and sgn(row["Delta"]) == exp_vs_hc * sgn(dhc))


def main() -> None:
    agg = json.loads(AGG_F.read_text())["aggregates"]
    cls = json.loads(CLS_F.read_text())
    pairs = cls["pairs"] if isinstance(cls["pairs"], list) else [dict(v, pair_id=k) for k, v in cls["pairs"].items()]
    by_id = {p["pair_id"]: p for p in pairs}
    pl = json.loads(PL_F.read_text())
    pl = pl if isinstance(pl, list) else pl.get("rows", pl)
    long_ix = {(r["candidate"], r["pair_id"]): r for r in pl}

    official9 = list(cls["primary_effective_pairs"])
    extra = {AMD_DPO: by_id[AMD_DPO], CAUTIOUS: by_id[CAUTIOUS]}
    extra_dhc = {k: pair_dhc(v) for k, v in extra.items()}

    d4_path = WS / "results" / "table_candidates32.json"
    d4 = json.loads(d4_path.read_text())

    rows_out: list[dict[str, Any]] = []
    n_validated = 0
    for row in d4["rows"]:
        akey = row.get("aggregates_key") or row["candidate_id"]
        a = agg.get(akey)
        rec: dict[str, Any] = {
            "candidate_id": row["candidate_id"],
            "aggregates_key": akey,
            "readout_class": row["readout_class"],
            "source_file": str(PL_F),
            "source_key": f"pairs_long[candidate={row['candidate_id']}|{akey}] validated against aggregates[{akey}].criterion_ii_sensitivity.per_pair",
        }
        if a is None or "criterion_ii_sensitivity" not in a:
            rec.update(status="UNVERIFIABLE", reason=f"aggregates.json has no criterion_ii for key {akey}")
            rows_out.append(rec)
            continue
        c2 = a["criterion_ii_sensitivity"]
        exp_vs_hc = int(a.get("expected_sign_vs_HC", 0) or 0)
        # pairs_long names a candidate by its short id (e.g. N1) while aggregates.json
        # may key it by a long name (e.g. N1_d_lstar); resolve whichever pairs_long uses.
        lkey = next((k for k in (row["candidate_id"], akey) if (k, official9[0]) in long_ix), None)
        rec["pairs_long_candidate"] = lkey
        if lkey is None:
            rec.update(status="UNVERIFIABLE",
                       reason=f"no pairs_long rows under {row['candidate_id']!r} or {akey!r}")
            rows_out.append(rec)
            continue
        per_pair = {pp["pair_id"]: pp for pp in c2.get("per_pair", [])}

        # ---- validation on the official pairs ----
        mism: list[str] = []
        rep_hits = 0
        scored_official = 0
        for pid in official9:
            pp = per_pair.get(pid)
            lr = long_ix.get((lkey, pid))
            if pp is None:
                continue  # official scorer did not score this pair for this candidate
            scored_official += 1
            mine = hit_from_long(lr, exp_vs_hc, pp["dHC"]) if lr else None
            if mine is None or mine != bool(pp["hit"]):
                mism.append(pid)
            rep_hits += int(bool(mine))
        off_hits = int(c2["n_hit_expected_direction"])
        off_n = int(c2["n_effective"])
        validated = (not mism) and rep_hits == off_hits and scored_official == off_n
        rec.update(
            official_hits=off_hits, official_n=off_n,
            reproduced_hits=rep_hits, reproduced_n=scored_official,
            validation="EXACT" if validated else "FAILED",
            validation_mismatched_pairs=mism,
        )
        if not validated:
            rec.update(status="UNVERIFIABLE",
                       reason="official 9-pair hits not reproduced exactly; extension withheld rather than guessed")
            rows_out.append(rec)
            continue
        n_validated += 1

        # ---- extension to 10 and 11 ----
        ext: dict[str, Any] = {}
        for pid in (AMD_DPO, CAUTIOUS):
            lr = long_ix.get((lkey, pid))
            dhc = extra_dhc[pid]
            h = hit_from_long(lr, exp_vs_hc, dhc) if (lr and dhc is not None) else None
            ext[pid] = {"hit": h, "scorable": h is not None,
                        "Delta": lr.get("Delta") if lr else None,
                        "ci": [lr.get("ci_lo"), lr.get("ci_hi")] if lr else None,
                        "dHC": dhc}
        h10, n10 = off_hits, off_n
        if ext[AMD_DPO]["scorable"]:
            h10 += int(ext[AMD_DPO]["hit"]); n10 += 1
        h11, n11 = h10, n10
        if ext[CAUTIOUS]["scorable"]:
            h11 += int(ext[CAUTIOUS]["hit"]); n11 += 1
        rec.update(
            status="OK",
            sensitivity_9=f"{off_hits}/{off_n}",
            sensitivity_10=f"{h10}/{n10}",
            sensitivity_11=f"{h11}/{n11}",
            sensitivity_frac_9=off_hits / off_n if off_n else None,
            sensitivity_frac_10=h10 / n10 if n10 else None,
            sensitivity_frac_11=h11 / n11 if n11 else None,
            extension_pairs=ext,
        )
        rows_out.append(rec)

    # rank stability: does moving from 9 to 10 reorder candidates?
    ok = [r for r in rows_out if r.get("status") == "OK"]
    changed_10 = [r["candidate_id"] for r in ok if r["sensitivity_10"].split("/")[0] != str(r["official_hits"])]
    out = {
        "deliverable": "D4 addendum",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "why": (
            "The frozen count rule in classification.json counts 'constructed + primary harvested + AMD "
            "count when observed EFFECTIVE'. HG::amd--AMD-OLMo-1B-SFT-DPO was planned as a harvested "
            "no-op and observed EFFECTIVE, so the rule puts it in the effective set: 10 pairs, not 9. "
            "F1__cautious (constructed, observed EFFECTIVE) is omitted although F1__dpo is counted "
            "under the same reclassification clause, so a literal reading gives 11."
        ),
        "count_rule_verbatim": cls["rule"].get("count_check"),
        "reclassification_rule_verbatim": cls["rule"].get("reclassification"),
        "official_effective_n": len(official9),
        "effective_n_under_frozen_count_rule": len(official9) + 1,
        "effective_n_literal_reclassification": len(official9) + 2,
        "extension_pair_dHC": extra_dhc,
        "n_candidates": len(rows_out),
        "n_candidates_reproduced_exactly": n_validated,
        "candidates_whose_hits_change_at_10": changed_10,
        "rows": rows_out,
        "source_file": str(CLS_F),
    }
    (WS / "results" / "table_sensitivity_denominators.json").write_text(json.dumps(out, indent=2))

    # augment D4 rows in place (idempotent)
    by_c = {r["candidate_id"]: r for r in rows_out}
    for row in d4["rows"]:
        r = by_c.get(row["candidate_id"], {})
        for k in ("sensitivity_9", "sensitivity_10", "sensitivity_11", "sensitivity_frac_10", "sensitivity_frac_11"):
            row[k] = r.get(k)
        row["sensitivity_10_11_status"] = r.get("status", "UNVERIFIABLE")
    d4["effective_set_denominators"] = {
        "official": len(official9),
        "frozen_count_rule": len(official9) + 1,
        "literal_reclassification": len(official9) + 2,
        "note": "see results/table_sensitivity_denominators.json",
    }
    d4_path.write_text(json.dumps(d4, indent=2))

    print(f"candidates: {len(rows_out)}  reproduced exactly: {n_validated}")
    print(f"extension dHC: {extra_dhc}")
    print(f"hits change at 10: {changed_10}")
    for r in rows_out:
        if r.get("status") == "OK":
            print(f"  {r['candidate_id']:28s} {r['readout_class']:10s} 9:{r['sensitivity_9']:6s} 10:{r['sensitivity_10']:6s} 11:{r['sensitivity_11']}")
        else:
            print(f"  {r['candidate_id']:28s} {r['readout_class']:10s} {r['status']}: {r.get('reason','')[:70]} {r.get('validation_mismatched_pairs','')}")


if __name__ == "__main__":
    main()
