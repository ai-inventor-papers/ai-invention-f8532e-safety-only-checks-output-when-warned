"""S13 ledger adjudication: one rule, applied uniformly, every override explained.

The four deliverable scripts each wrote their own contradictions_*.json. Read
together they were inconsistent: some claims were duplicated, some verdicts used
tolerances that are not in the frozen prereg (e.g. '|d|<=1.5', '|d|<=5e-2'), some
used the wrong tolerance CLASS (logit gaps are nats, not effect sizes), one
compared a claim against a different quantity (a per-band proxy refusal RATE
against kappa), and one compared a registered HYPOTHESIS instead of the published
claim. This script fixes that without editing any agent file:

  1. dedupe by claim_id (first occurrence wins, later ones are listed);
  2. apply the documented ADJUDICATIONS below, each with its reason;
  3. re-derive the verdict of every numeric claim under the FROZEN prereg rule
     (counts exact; rates / effect sizes 5e-4; nats 1e-3; correlations 5e-3);
  4. add a SECONDARY, explicitly post-hoc 'rounding-aware' verdict: a published
     value quoted to k decimals matches if the re-derived value rounds to it.

The PRIMARY claim match rate is the frozen-rule rate. The secondary rate is never
substituted for it; it is reported beside it so a reader can see how much of the
mismatch count is rounding of quoted prose rather than a substantive error.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import math
from decimal import Decimal
from pathlib import Path
from typing import Any

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
RES = WS / "results"
LEDGERS = ["contradictions_d1_d2_d4.json", "contradictions_d3_d7_d9.json",
           "contradictions_d5_d6.json", "contradictions_d8_d10.json"]

TOL = {"count": 0.0, "rate": 5e-4, "effect_size": 5e-4, "nats": 1e-3, "correlation": 5e-3}
I4E2 = "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_2"
I4E1 = "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1"


def load_json(p: Path) -> Any | None:
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def tol_class(rule: Any) -> str | None:
    r = str(rule or "").lower()
    if "nat" in r:
        return "nats"
    if "corr" in r or "rho" in r or "cos" in r:
        return "correlation"
    if "count" in r or "exact" in r and "string" not in r:
        return "count"
    if "rate" in r:
        return "rate"
    if "effect" in r:
        return "effect_size"
    return None


def as_num(x: Any) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)) and math.isfinite(float(x)):
        return float(x)
    return None


def decimals_of(x: float) -> int:
    d = Decimal(repr(x)).normalize()
    return max(0, -d.as_tuple().exponent)


def num_pairs(claimed: Any, rederived: Any) -> list[tuple[float, float]] | None:
    """Scalar-vs-scalar, or flat dict-vs-dict on shared keys; else None."""
    c, r = as_num(claimed), as_num(rederived)
    if c is not None and r is not None:
        return [(c, r)]
    if isinstance(claimed, dict) and isinstance(rederived, dict):
        out = []
        for k, v in claimed.items():
            cv, rv = as_num(v), as_num(rederived.get(k))
            if cv is None or rv is None:
                return None
            out.append((cv, rv))
        return out or None
    return None


def strict_verdict(pairs: list[tuple[float, float]], cls: str) -> str:
    t = TOL[cls]
    return "MATCH" if all(abs(c - r) <= t + 1e-12 for c, r in pairs) else "MISMATCH"


def rounding_verdict(pairs: list[tuple[float, float]], cls: str) -> str:
    ok = True
    for c, r in pairs:
        if abs(c - r) <= TOL[cls] + 1e-12:
            continue
        k = decimals_of(c)
        if round(r, k) != round(c, k):
            ok = False
    return "MATCH" if ok else "MISMATCH"


# --------------------------------------------------------------------------- #
# Documented adjudications. Each entry: claim_id -> (patch, reason).
# "__REMOVE__" withdraws a claim from the ledger (listed, never silently lost).
# --------------------------------------------------------------------------- #
def adjudications(res: dict[str, Any]) -> dict[str, tuple[Any, str]]:
    den = res.get("den") or {}
    kp = res.get("kp_band") or {}
    disp = res.get("disp") or {}
    A: dict[str, tuple[Any, str]] = {}

    A["C03"] = ({
        "claim_text": "The primary_effective_pairs list (9 pairs) is the complete EFFECTIVE set under the frozen count rule.",
        "claimed_value": 9,
        "rederived_value": {
            "primary_effective_pairs": den.get("official_effective_n", 9),
            "frozen_count_rule": den.get("effective_n_under_frozen_count_rule", 10),
            "literal_reclassification_clause": den.get("effective_n_literal_reclassification", 11),
        },
        "tolerance_rule": "count", "tolerance": 0,
        "source_file": f"{I4E1}/results/classification.json",
        "source_key": "rule.count_check + rule.reclassification + pairs[*].observed_class",
        "verdict": "MISMATCH",
        "note": ("The frozen count rule counts 'constructed + primary harvested + AMD count when observed "
                 "EFFECTIVE'. HG::amd--AMD-OLMo-1B-SFT-DPO (intended NOOP_HARVESTED) was observed EFFECTIVE "
                 "(dHC +0.318), so the rule makes the set 10. F1__cautious (constructed, observed EFFECTIVE, "
                 "dHC -0.106) is omitted although F1__dpo is counted under the same reclassification clause: "
                 "11 under a literal reading. Adding the 10th pair changes the hit count of exactly one "
                 "candidate (B7 7/9 -> 8/10), through the documented OLMo all-ones-null artefact; B7_nullproj "
                 "stays 6/10 and no activation candidate detects it. See results/table_sensitivity_denominators.json."),
    }, "The agent's re-derived value 29 counted OR_EFFECTIVE pairs and H::/HG:: duplicates of the same "
       "transition; it is not the quantity the claim is about. Re-derived here from the rule text itself.")

    for b in ("B4", "B5", "B6"):
        A[f"kappa_band_{b}"] = ("__REMOVE__",
            f"Category error. The published per-band values (0.15/0.19/0.31) are the keyword proxy's reported "
            f"refusal RATE under arm F, not Cohen's kappa. They were compared against kappa (~0 for SafeRL). The "
            f"claim is tested against the right quantity by d8_d10 C12. The per-band kappa values remain in "
            f"results/table_causal_grid.json as a separate, valid finding.")

    A["kappa_collapse_headline"] = ({
        "claim_text": "The keyword proxy falsely reports harmful-request refusal falling 0.79 -> 0.15 (instruct, arm F, site P).",
        "claimed_value": {"from": 0.79, "to": 0.15},
        "rederived_value": {"from": kp.get("B1"), "to": kp.get("B4")},
        "tolerance_rule": "rate", "tolerance": 5e-4,
        "source_file": f"{I4E2}/results/analysis.json",
        "source_key": "keyword-proxy proxy_refused_harm per band (instruct, arm F, site P); see results/table_setup_deviations.json",
        "verdict": "RECOMPUTE",
        "note": ("0.79 is the B1 value and 0.15 the B4 value of the proxy's reported refusal rate. Headline "
                 "compresses a per-band profile (B4 0.146, B5 0.188, B6 0.313) into one number, while judged "
                 "refusal stays flat (max |effect_FR| 0.056)."),
    }, "The agent marked this UNVERIFIABLE for want of a verbatim source; the per-band proxy rates that "
       "d8_d10 re-derived make it checkable (B1 0.7917 -> B4 0.1458).")

    A["did_registered_not_supported"] = ({
        "claim_text": "Published: the registered DiD 'instruct over-refusal falls more' is NOT supported.",
        "claimed_value": "NOT_SUPPORTED",
        "rederived_value": "NOT_SUPPORTED (registered sign in 8/18 cells, chance level; at the Holm-18 survivor "
                           "cell P_B5 the DiD is -0.014 [-0.174, +0.146])",
        "tolerance_rule": "string", "tolerance": 0, "verdict": "MATCH",
        "note": "The published conclusion is confirmed by disk.",
    }, "The agent compared the registered HYPOTHESIS ('positive DiD expected') against the result. The claim "
       "under audit is the published conclusion, which disk confirms.")

    A["pos_rd_harm_b4"] = ({
        "tolerance_rule": "nats", "tolerance": 1e-3,
        "note": ("RD_harm is a logit difference in nats: |(-4.170) - (-4.1597)| = 0.0103 > 1e-3. It does not "
                 "round to the quoted value either (-4.16 at 2 dp)."),
    }, "The agent logged MATCH under a 'relaxed tolerance' that is not in the frozen prereg.")

    easy = disp.get("BL1_easy")
    med_act = disp.get("median_activation")
    ratio_easy = (easy / med_act) if (easy and med_act) else None
    A["C6"] = ({
        "claim_text": "BL1's median no-op displacement is 'near 6x' the activation readouts' (BL1_easy numerator).",
        "claimed_value": 6.0,
        "rederived_value": ratio_easy,
        "tolerance_rule": "effect_size", "tolerance": 5e-4,
        "note": (f"Ratio depends on the BL1 variant in the numerator: easy {disp.get('ratio_easy')}, hard "
                 f"{disp.get('ratio_hard')}, truelogit {disp.get('ratio_truelogit')}, truelogit_hard "
                 f"{disp.get('ratio_truelogit_hard')} (median activation displacement {med_act}). BL1_easy is "
                 "the baseline used in the paper's primary false-alarm comparison, so it is the numerator here."),
    }, "The agent used a '|d|<=1.5 (order of magnitude)' tolerance that is not in the frozen prereg, and "
       "BL1_hard as the numerator where the paper's primary comparison uses BL1_easy.")

    I3EV = "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_evaluation_1/results/tables.json"
    I3X1 = "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1/results/extra_analyses.json"
    A["d7_8of8_abliterated_ddrop"] = ({
        "claim_text": ("Request-axis d (held-out peak d, iteration-2 protocol) drops on 8/8 effective abliterated "
                       "pairs: 6/6 on the iteration-2 panel plus 2/2 fresh iteration-3 pairs."),
        "claimed_value": 8,
        "rederived_value": 8,
        "tolerance_rule": "count", "tolerance": 0,
        "source_file": f"{I3EV} ; {I3X1}",
        "source_key": ("tables.json pairs[P0..P5].delta_peak_d_ci95 (6/6 wholly below 0; granite null edit P6 "
                       "+0.091 [-0.013,+0.204] does not move) ; extra_analyses.json abliteration_replication.rows "
                       "(Vikhr -0.904 [-1.384,-0.550], mylesgoose -0.606 [-0.883,-0.358])"),
        "verdict": "RECOMPUTE",
        "note": ("Re-derived numerically from per-pair CIs on disk: 6/6 + 2/2 = 8/8, every CI wholly below 0. "
                 "Two caveats. (1) P4 SmolLM3 and P5 Phi-4-mini are AMBIGUOUS under the frozen label_robust rule, "
                 "so 6 of the 8 are robustly effective; all 8 drop regardless. (2) The finding is READOUT- and "
                 "HARVEST-specific: iteration-4's N1 (d at a fixed l*, on regenerated harvests) drops in sign on "
                 "4 of 5 scored abliterated models, significantly on 3, and significantly RISES on mylesgoose "
                 "(+0.776 [+0.086,+1.226]), the same model whose iteration-3 peak d fell. The agent's '4/12' and "
                 "'1/6' re-derivation used N1 and counted unscored (null) rows as non-drops; it is superseded."),
    }, "The agent re-derived the claim on a different readout (iteration-4 N1) and put unscored rows in the "
       "denominator. The claim's own readout and source are the iteration-3 peak-d contrasts, re-derived here.")

    return A


def split_c11(c: dict[str, Any]) -> list[dict[str, Any]]:
    """C11 bundled two different published values; test each separately."""
    r = as_num(c.get("rederived_value"))
    out = []
    for suffix, val, who in (("a", 5.3, "iteration-4 execution record"), ("b", 5.0, "artifact direction")):
        d = copy.deepcopy(c)
        d.update(claim_id=f"C11{suffix}",
                 claim_text=f"Falcon3 batch-8 padding bug shifts AMS by {val} sigma ({who}).",
                 claimed_value=val, rederived_value=r,
                 tolerance_rule="effect_size", tolerance=5e-4,
                 note=f"Re-derived max |sigma shift| {r}. Split from the bundled C11, which tested both values "
                      "against a '|d|<=5e-2' tolerance that is not in the frozen prereg.")
        out.append(d)
    return out


def main() -> None:
    # context numbers the adjudications need, all read from disk
    den = load_json(RES / "table_sensitivity_denominators.json") or {}
    sd = load_json(RES / "table_setup_deviations.json") or {}
    kp_band: dict[str, float] = {}
    stack = [sd]
    while stack:  # find the per-band proxy rate block wherever the D10 script put it
        cur = stack.pop()
        if isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(v, dict) and {"B1", "B4"} <= set(v) and all(as_num(v[b]) is not None for b in ("B1", "B4")) \
                        and "kappa" not in k.lower() and not kp_band:
                    kp_band = {b: float(v[b]) for b in v if as_num(v[b]) is not None}
                stack.append(v)
        elif isinstance(cur, list):
            stack.extend(cur)
    disp_doc = load_json(RES / "table_displacement.json") or {}
    rows = disp_doc.get("rows") or disp_doc.get("candidates") or []
    bl1 = {r.get("candidate_id"): as_num(r.get("median_noop_displacement_in_null_SD")) for r in rows if isinstance(r, dict)}
    act = sorted(v for r in rows if isinstance(r, dict) and r.get("readout_class") == "activation"
                 for v in [as_num(r.get("median_noop_displacement_in_null_SD"))] if v is not None)
    med_act = act[len(act) // 2] if len(act) % 2 else (0.5 * (act[len(act) // 2 - 1] + act[len(act) // 2]) if act else None)
    disp: dict[str, Any] = {"median_activation": med_act}
    for v in ("easy", "hard", "truelogit", "truelogit_hard"):
        x = bl1.get(f"BL1_{v}")
        disp[f"BL1_{v}"] = x
        disp[f"ratio_{v}"] = round(x / med_act, 3) if (x and med_act) else None
    ctx = {"den": den, "kp_band": kp_band, "disp": disp}
    ADJ = adjudications(ctx)

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    duplicates: list[dict[str, str]] = []
    withdrawn: list[dict[str, str]] = []
    overrides: list[dict[str, Any]] = []
    missing_ledgers: list[str] = []

    for fname in LEDGERS:
        obj = load_json(RES / fname)
        if obj is None:
            missing_ledgers.append(fname)
            continue
        claims = obj if isinstance(obj, list) else obj.get("claims", [])
        for c0 in claims:
            if not isinstance(c0, dict) or "claim_id" not in c0:
                continue
            batch = split_c11(c0) if (c0["claim_id"] == "C11" and fname.endswith("d8_d10.json")) else [c0]
            for c in batch:
                cid = str(c["claim_id"])
                if cid in seen:
                    duplicates.append({"claim_id": cid, "ledger_file": fname})
                    continue
                seen.add(cid)
                c = copy.deepcopy(c)
                c["ledger_file"] = fname
                c["verdict_agent"] = c.get("verdict")
                if cid in ADJ:
                    patch, reason = ADJ[cid]
                    if patch == "__REMOVE__":
                        withdrawn.append({"claim_id": cid, "ledger_file": fname, "reason": reason})
                        continue
                    before = {k: c.get(k) for k in patch}
                    c.update(patch)
                    overrides.append({"claim_id": cid, "ledger_file": fname, "reason": reason,
                                      "changed_fields": sorted(patch), "before": before})
                merged.append(c)

    # ---- uniform frozen-rule re-derivation of every numeric verdict ----
    rule_disagreements: list[dict[str, Any]] = []
    for c in merged:
        cls = tol_class(c.get("tolerance_rule"))
        pairs = num_pairs(c.get("claimed_value"), c.get("rederived_value"))
        if "abs" in str(c.get("claim_id", "")).lower() and pairs:
            pairs = [(abs(a), abs(b)) for a, b in pairs]
        terminal = str(c.get("verdict", "")).upper() in ("UNVERIFIABLE", "SOURCE_ABSENT")
        if terminal:
            c["verdict_rule_class"] = cls or "n/a"
            c["verdict_rounding_aware"] = str(c["verdict"]).upper()
        elif cls and pairs:
            strict = strict_verdict(pairs, cls)
            rnd = rounding_verdict(pairs, cls)
            c["verdict_rule_class"] = cls
            c["verdict_rounding_aware"] = rnd
            explicit = any(o["claim_id"] == c["claim_id"] and "verdict" in o["changed_fields"] for o in overrides)
            if str(c.get("verdict")).upper() in ("MATCH", "MISMATCH") and c["verdict"] != strict and not explicit:
                rule_disagreements.append({"claim_id": c["claim_id"], "ledger_file": c["ledger_file"],
                                           "agent_verdict": c["verdict"], "frozen_rule_verdict": strict,
                                           "rule_class": cls, "pairs": pairs})
            c["verdict"] = strict
        else:
            c["verdict_rule_class"] = "non-numeric (agent verdict kept)"
            c["verdict_rounding_aware"] = c.get("verdict")
        c["verdict"] = str(c.get("verdict", "")).upper()

    def tally(key: str) -> dict[str, int]:
        t = {"MATCH": 0, "MISMATCH": 0, "UNVERIFIABLE": 0, "SOURCE_ABSENT": 0}
        for c in merged:
            v = str(c.get(key, "")).upper()
            if v in t:
                t[v] += 1
        return t

    prim = tally("verdict")
    sec = tally("verdict_rounding_aware")
    rate = prim["MATCH"] / (prim["MATCH"] + prim["MISMATCH"]) if (prim["MATCH"] + prim["MISMATCH"]) else float("nan")
    rate2 = sec["MATCH"] / (sec["MATCH"] + sec["MISMATCH"]) if (sec["MATCH"] + sec["MISMATCH"]) else float("nan")

    out = {
        "definition": ("claim_match_rate = MATCH / (MATCH + MISMATCH) under the FROZEN prereg tolerance rule. "
                       "UNVERIFIABLE and SOURCE_ABSENT are reported separately and are NEVER folded into the "
                       "denominator."),
        "tolerance_rule": {"counts": "EXACT", "rates_and_effect_sizes": "|delta| <= 5e-4",
                           "nats": "<= 1e-3", "correlations": "<= 5e-3"},
        "counts": prim,
        "n_claims": len(merged),
        "claim_match_rate": rate,
        "secondary_rounding_aware": {
            "label": "POST-HOC SECONDARY. Not the primary metric.",
            "rule": ("a published value quoted to k decimals MATCHES if the re-derived value rounds to it at k "
                     "decimals (or already satisfies the frozen tolerance)"),
            "counts": sec,
            "claim_match_rate": rate2,
            "why_reported": ("Prose quotes values to 2-3 decimals while the frozen tolerances are 5e-4 to 5e-3, "
                             "so some frozen-rule mismatches are rounding of quoted prose. Reporting both rates "
                             "separates rounding from substantive error without relaxing the primary rule."),
        },
        "adjudication": {
            "duplicates_dropped": duplicates,
            "claims_withdrawn": withdrawn,
            "explicit_overrides": overrides,
            "frozen_rule_reversed_agent_verdict": rule_disagreements,
            "missing_ledgers": missing_ledgers,
        },
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "claims": merged,
    }
    (RES / "ledger_adjudicated.json").write_text(json.dumps(out, indent=2, default=str))
    print(f"claims {len(merged)} | dup dropped {len(duplicates)} | withdrawn {len(withdrawn)} | "
          f"explicit overrides {len(overrides)} | frozen rule reversed agent {len(rule_disagreements)}")
    print(f"PRIMARY  {prim}  rate={rate:.4f}")
    print(f"SECONDARY(rounding-aware, post hoc) {sec}  rate={rate2:.4f}")
    for d in rule_disagreements:
        print(f"   reversed: {d['claim_id']:32s} agent={d['agent_verdict']:9s} -> {d['frozen_rule_verdict']:9s} [{d['rule_class']}] {d['pairs']}")
    print("context:", json.dumps({"kp_band": kp_band, "disp": disp}, default=str)[:400])


if __name__ == "__main__":
    main()
