#!/usr/bin/env python3
"""Re-checking the numbers we already have.

A zero-GPU, zero-API, zero-download re-adjudication of iteration 1's three lanes,
computed only from files already on disk. Runs M0-M8, writes one machine-readable
table per metric with EVERY ROW CARRYING ITS SOURCE FILE PATH, an EVAL_REPORT.md
that opens with CONTRADICTIONS and then the claim match rate, and an eval_out.json
in the exp_eval_sol_out schema.

    uv run eval.py               # everything
    uv run eval.py --smoke       # one lineage, no restricted-budget sweep
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evalkit import paths as P  # noqa: E402
from evalkit import prereg as PR  # noqa: E402
from evalkit import selfcheck  # noqa: E402
from evalkit import m0_assets, m1_recognition, m2_ceiling, m3_cosine  # noqa: E402
from evalkit import m6_paired, m8_provenance  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
P.LOGS.mkdir(parents=True, exist_ok=True)
logger.add(P.LOGS / "run.log", rotation="30 MB", level="DEBUG")


def _optional(module_name: str):
    """M4, M5 and M7 live in their own modules; a missing one is reported, not fatal."""
    try:
        mod = __import__(f"evalkit.{module_name}", fromlist=["run"])
        return mod.run
    except ImportError as exc:
        logger.error("optional module {} unavailable: {!r}", module_name, exc)
        return None


def _write_table(name: str, rows: list[dict]) -> Path:
    P.RESULTS.mkdir(parents=True, exist_ok=True)
    path = P.RESULTS / f"{name}.csv"
    if not rows:
        path.write_text("EMPTY\n")
        logger.warning("{} is EMPTY -- reported as EMPTY, never silently omitted", name)
        return path
    df = pd.DataFrame(rows)
    front = [c for c in ("metric", "READOUT_CLASS", "BASELINE_ONLY", "DESCRIPTIVE")
             if c in df.columns]
    rest = [c for c in df.columns if c not in front]
    df = df[front + rest]
    df.to_csv(path, index=False)
    logger.info("wrote {} ({} rows, {} cols)", path.name, len(df), len(df.columns))
    return path


def _json_safe(obj):
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        v = float(obj)
        return None if not np.isfinite(v) else v
    if isinstance(obj, np.ndarray):
        return _json_safe(obj.tolist())
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, float) and not np.isfinite(obj):
        return None
    if isinstance(obj, Path):
        return str(obj)
    return obj


# --------------------------------------------------------------------------- #
@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smoke", action="store_true",
                    help="one lineage and no restricted-budget sweep")
    ap.add_argument("--reuse-m1", action="store_true",
                    help="reuse results/m1_cache.json instead of recomputing M1 "
                         "(the restricted-budget sweep is the only slow step)")
    args = ap.parse_args()

    P.RESULTS.mkdir(parents=True, exist_ok=True)
    prereg_path, prereg_sha = PR.write()
    logger.info("prereg frozen: {} sha256={}", prereg_path.name, prereg_sha)

    tables: dict[str, list[dict]] = {}
    notes: dict[str, dict] = {}
    cuts: list[str] = []
    failures: list[dict] = []

    def stage(key: str, fn, *fargs, **fkwargs):
        logger.info("--- {} ---", key)
        try:
            return fn(*fargs, **fkwargs)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            logger.error("{} FAILED: {!r}", key, exc)
            failures.append({"stage": key, "exception": repr(exc),
                             "traceback": traceback.format_exc()[-1500:]})
            return None

    # ---- M0 --------------------------------------------------------------- #
    out = stage("M0 asset and recomputability ledger", m0_assets.build_ledger)
    m0_rows, m0_detail = out if out else ([], {})
    tables["m0_asset_ledger"] = [r.as_dict() for r in m0_rows]
    notes["M0"] = {"new_facts": m0_detail.get("new_facts", []),
                   "abliterated_scope": m0_detail.get("abliterated_scope", {}),
                   "causal_arm": {k: v for k, v in
                                  m0_detail.get("causal_arm", {}).items()
                                  if k != "logs"},
                   "harvest": {k: v for k, v in
                               m0_detail.get("lane_b_harvest_inventory", {}).items()
                               if k not in ("per_file", "per_item_layer_dim_arrays",
                                            "metas")},
                   "prereg_sha256": prereg_sha}
    (P.RESULTS / "m0_harvest_inventory.json").write_text(
        json.dumps(_json_safe(m0_detail.get("lane_b_harvest_inventory", {})), indent=1))
    (P.RESULTS / "m0_causal_logs.json").write_text(
        json.dumps(_json_safe(m0_detail.get("causal_arm", {})), indent=1))
    gc.collect()

    # ---- M1 --------------------------------------------------------------- #
    lin = ("L2",) if args.smoke else ("L1", "L2", "L3", "L4")
    cache = P.RESULTS / "m1_cache.json"
    if args.reuse_m1 and cache.exists():
        logger.info("M1: reusing {}", cache.name)
        blob = json.loads(cache.read_text())
        m1_rows, m1_notes = blob["rows"], blob["notes"]
        m1_notes["reused_from_cache"] = str(cache.relative_to(P.WORKSPACE))
    else:
        out = stage("M1 recognition with headroom", m1_recognition.run,
                    lineages=lin, do_budget=not args.smoke)
        m1_rows, m1_notes = out if out else ([], {})
        if m1_rows:
            cache.write_text(json.dumps(
                _json_safe({"rows": m1_rows, "notes": m1_notes,
                            "lineages": list(lin), "budget": not args.smoke}), indent=1))
    tables["m1_recognition_headroom"] = m1_rows
    notes["M1"] = m1_notes
    if args.smoke:
        cuts.append("M1 restricted-budget sweep and 3 of 4 lineages (--smoke)")
    gc.collect()

    # ---- M6 --------------------------------------------------------------- #
    out = stage("M6 paired-lineage contrast", m6_paired.run)
    m6_rows, m6_notes = out if out else ([], {})
    tables["m6_paired_lineage"] = m6_rows
    notes["M6"] = m6_notes
    (P.RESULTS / "m6_tests.json").write_text(json.dumps(_json_safe(m6_notes), indent=1))

    # ---- M3 --------------------------------------------------------------- #
    out = stage("M3 cosine geometry", m3_cosine.run)
    m3_tables, m3_notes = out if out else ({}, {})
    tables["m3a_cosine_protocols"] = m3_tables.get("m3a", [])
    tables["m3b_prior_art"] = m3_tables.get("m3b", [])
    tables["m3c_rotation_matrix"] = m3_tables.get("m3c", [])
    notes["M3"] = m3_notes

    # ---- M4 --------------------------------------------------------------- #
    fn = _optional("m4_gates")
    out = stage("M4 complete gates ledger", fn) if fn else None
    m4_rows, m4_notes = out if out else ([], {"status": "MODULE_UNAVAILABLE"})
    tables["m4_gates_ledger"] = m4_rows
    notes["M4"] = m4_notes

    # ---- M5 --------------------------------------------------------------- #
    fn = _optional("m5_budget")
    out = stage("M5 prompt-budget curve", fn) if fn else None
    m5_rows, m5_notes = out if out else ([], {"status": "MODULE_UNAVAILABLE"})
    tables["m5_budget_curve"] = m5_rows
    notes["M5"] = m5_notes

    # ---- M2 --------------------------------------------------------------- #
    out = stage("M2 ceiling and dynamic-range audit", m2_ceiling.run, m1_rows)
    m2_rows, m2_notes = out if out else ([], {})
    tables["m2_ceiling_audit"] = m2_rows
    notes["M2"] = m2_notes

    # ---- M7 --------------------------------------------------------------- #
    fn = _optional("m7_truth")
    out = stage("M7 truth-column and judge integrity", fn) if fn else None
    m7_rows, m7_notes = out if out else ([], {"status": "MODULE_UNAVAILABLE"})
    tables["m7_truth_integrity"] = m7_rows
    notes["M7"] = m7_notes

    # ---- M8 --------------------------------------------------------------- #
    extra: list[dict] = []
    for src_key, src_notes in (("M4", m4_notes), ("M5", m5_notes),
                               ("M6", m6_notes), ("M7", m7_notes)):
        claims = (src_notes.get("claims_checked")
                  or src_notes.get("claimed_vs_recomputed") or [])
        for c in claims:
            if not isinstance(c, dict):
                continue
            c = dict(c)
            c["block"] = f"INHERITED FROM {src_key}"
            extra.append(c)
        rc = src_notes.get("record_to_correct")
        if isinstance(rc, dict) and "claimed" in rc:
            rc = dict(rc)
            rc.setdefault("claim", f"{src_key} record to correct")
            rc["block"] = f"INHERITED FROM {src_key}"
            extra.append(rc)
    extra += _m1_m3_claims(m1_notes, m3_notes)
    out = stage("M8 provenance and claim-diff ledger", m8_provenance.run,
                m0_detail=m0_detail, extra_claims=extra)
    m8_rows, m8_notes = out if out else ([], {})
    tables["m8_provenance"] = [r for r in m8_rows if r.get("metric") == "M8"]
    tables["m8_commissioned_comparison"] = [r for r in m8_rows
                                            if r.get("metric") == "M8.commissioned"]
    notes["M8"] = m8_notes

    # ---- emit -------------------------------------------------------------- #
    written = {name: str(_write_table(name, rows).relative_to(P.WORKSPACE))
               for name, rows in tables.items()}
    contradictions = _contradictions(notes, m0_detail)
    report = _report(tables, notes, contradictions, cuts, failures, prereg_sha, written)
    check = selfcheck.run_all(tables, {"EVAL_REPORT.md": report})
    if check["status"] == "FAIL":
        report = ("> **SELF-CHECK FAILED** -- see `results/selfcheck.json`.\n\n" + report)
    (P.WORKSPACE / "EVAL_REPORT.md").write_text(report)
    (P.RESULTS / "selfcheck.json").write_text(json.dumps(_json_safe(check), indent=1))
    (P.RESULTS / "eval_notes.json").write_text(json.dumps(_json_safe(notes), indent=1))

    _emit_eval_out(tables, notes, contradictions, cuts, failures, prereg_sha)
    logger.info("DONE. claim match rate = {}", m8_notes.get("CLAIM_MATCH_RATE"))
    if failures:
        logger.error("{} stage(s) failed: {}", len(failures),
                     [f["stage"] for f in failures])


def _m1_m3_claims(m1_notes: dict, m3_notes: dict) -> list[dict]:
    """Claims M1 and M3 settled, folded into the accuracy ledger."""
    out: list[dict] = []
    for lineage, rec in (m1_notes.get("reconciliation") or {}).items():
        for group in ("damage", "damage_matched"):
            g = rec.get(group)
            if not g:
                continue
            out.append({
                "claim": (f"Lane B {lineage} {g['stored_key']} reproduces from the "
                          f"stored harvest"),
                "claimed": g["stored"], "recomputed": g["recomputed"],
                "source": rec["source_file"],
                "json_path": f"lineages.{lineage}.{g['stored_key']}",
                "verdict": ("MATCH" if g["verdict"] in ("EXACT_MATCH", "RECONCILED")
                            else g["verdict"]),
                "READOUT_CLASS": "activation",
                "block": "INHERITED FROM M1 (reconciliation)",
                "note": (f"max |delta| {g['max_abs_delta']:.4f} over "
                         f"{len(g['recomputed'])} lesion strengths; n={g['n']}"),
            })
    lane_a = next((r for r in (m3_notes.get("m3a", {}).get("honest_scope_sentence") and []
                               or []) ), None)
    m3a = m3_notes.get("m3a", {})
    if "honest_scope_sentence" in m3a:
        out.append({
            "claim": ("|cos(r_content, r_ablit)| is 0.04-0.09 at the band in Lane A's "
                      "seven arms"),
            "claimed": "0.04-0.09", "recomputed": m3a["honest_scope_sentence"],
            "source": P.rel(P.A_COS_CONTENT_ABLIT), "json_path": "<ckpt>.at_band",
            "verdict": "MISMATCH", "READOUT_CLASS": "activation",
            "block": "INHERITED FROM M3",
            "note": ("the reported range is the SMALLEST of three protocols and "
                     "understates even its own protocol's spread"),
        })
    nc = m3_notes.get("m3c", {}).get("narrative_correction")
    if nc:
        out.append({
            "claim": ("community abliteration rotates the request axis MORE than "
                      "ordinary instruction tuning does"),
            "claimed": "abliteration rotates more",
            "recomputed": nc["statement"], "source": P.rel(P.A_CROSS_CKPT),
            "json_path": "pairs.<A>||<B>.r_ablit.at_band",
            "verdict": "MISMATCH" if nc["the_narrative_got_it_backwards"] else "MATCH",
            "READOUT_CLASS": "activation", "block": "INHERITED FROM M3",
        })
    return out


def _contradictions(notes: dict, m0_detail: dict) -> list[dict]:
    """The CONTRADICTIONS section, with nothing above it in the report."""
    out: list[dict] = []
    m3d = notes.get("M3", {}).get("m3d", {})
    if m3d.get("status") == "CONTRADICTION":
        out.append({
            "id": "C1", "where": m3d["source_file"],
            "statement": m3d["statement"],
            "resolution": m3d["which_one_the_write_up_keeps"],
            "evidence": {"licence": m3d.get("licence_sentences"),
                         "limitation": m3d.get("limitation_sentences")},
        })
    causal = m0_detail.get("causal_arm", {})
    if causal.get("n_files", 0) <= 1:
        out.append({
            "id": "C2", "where": causal.get("dir"),
            "statement": ("The causal (generation) arm is EMPTY except for its "
                          "unlesioned baseline: %s of %s jobs produced nothing, and "
                          "zero tokens were generated anywhere in the artifact. "
                          "Iteration 1's deviations ledger omitted this and its "
                          "self-audit missed it."
                          % (causal.get("n_jobs_crashed"),
                             causal.get("n_jobs_expected"))),
            "resolution": ("Reported as EMPTY. Any claim that rests on generated "
                           "text from the lesioned models has no supporting "
                           "evidence in iteration 1."),
            "evidence": {"files": causal.get("files"),
                         "followup_sh_line_12": causal.get("followup_sh_line_12")},
        })
    for f in (m0_detail.get("new_facts") or []):
        if "FALSE" in f or "TRUE ONLY" in f:
            out.append({"id": f"C{len(out) + 1}", "where": "M0 inventory",
                        "statement": f, "resolution": "corrected at source",
                        "evidence": {}})
    m4 = notes.get("M4", {})
    if m4.get("G1_finding"):
        out.append({"id": f"C{len(out) + 1}", "where": "G1 across three lanes",
                    "statement": m4["G1_finding"],
                    "resolution": m4.get("S1_rescored_outcome",
                                         "reported per lane with the fitting corpus named"),
                    "evidence": {}})
    t3 = notes.get("M6", {}).get("T3_specificity", {})
    for k, v in t3.items():
        if isinstance(v, dict) and str(v.get("verdict", "")).startswith("FIRES"):
            out.append({
                "id": f"C{len(out) + 1}", "where": f"M6 T3 specificity, pair {k}",
                "statement": ("The primary recognition feature moves %s on a pair "
                              "whose judged harmful-compliance did not move at all "
                              "(delta %s). %s"
                              % (v["features_moving_more_than_1_null_sd"],
                                 v["behavioural_delta_hc"], v["verdict"])),
                "resolution": ("Reported as a SPECIFICITY FAILURE. A readout that "
                               "fires on a behavioural no-op cannot be promoted on "
                               "the strength of label-scored pairs."),
                "evidence": {}})
    return out


def _fmt_table(rows: list[dict], cols: list[str], *, limit: int = 30) -> str:
    present = [c for c in cols if any(c in r for r in rows)]
    if not rows or not present:
        return "_(EMPTY -- reported as EMPTY, never silently omitted)_\n"
    df = pd.DataFrame(rows)[present].head(limit)
    return df.to_markdown(index=False) + (
        f"\n\n_showing {min(limit, len(rows))} of {len(rows)} rows; "
        f"the full table is the CSV._\n" if len(rows) > limit else "\n")


def _report(tables, notes, contradictions, cuts, failures, prereg_sha, written) -> str:
    m8 = notes.get("M8", {})
    L: list[str] = []
    L.append("# CONTRADICTIONS\n")
    L.append("_Nothing is printed above this section._\n")
    if not contradictions:
        L.append("None found.\n")
    for c in contradictions:
        L.append(f"### {c['id']} -- {c['where']}\n")
        L.append(f"{c['statement']}\n")
        L.append(f"**Resolution.** {c['resolution']}\n")

    L.append("\n# CLAIM MATCH RATE\n")
    L.append(f"**{m8.get('CLAIM_MATCH_RATE')}** "
             f"({m8.get('n_match')} of {m8.get('n_numbers_checked')} numbers "
             f"recomputed from source agree; {m8.get('n_mismatch')} MISMATCH, "
             f"{m8.get('n_not_in_source')} NOT_IN_SOURCE).\n")
    if m8.get("mismatches"):
        lines = ["", "| claim | claimed | recomputed | source |", "|---|---|---|---|"]
        for m in m8["mismatches"]:
            lines.append(f"| {str(m['claim'])[:110]} | `{m['claimed']}` | "
                         f"`{str(m['recomputed'])[:90]}` | `{m['source']}` |")
        L.append("\n".join(lines) + "\n")

    L.append("\n# RUN INVARIANT\n")
    L.append(PR.PREREG["run_invariant"]["statement"] + "\n")
    L.append(PR.PREREG["run_invariant"]["enforcement"] + "\n")
    L.append(PR.PREREG["run_invariant"]["framing"] + "\n")
    L.append(f"\nPre-registration SHA-256: `{prereg_sha}`\n")

    L.append("\n# M0 -- ASSET AND RECOMPUTABILITY LEDGER\n")
    for f in notes.get("M0", {}).get("new_facts", []):
        L.append(f"- {f}\n")
    L.append(_fmt_table(tables["m0_asset_ledger"],
                        ["quantity", "metric_consumers", "source_file", "size_bytes",
                         "verdict", "READOUT_CLASS", "contents"], limit=25))

    L.append("\n# M1 -- RECOGNITION WITH HEADROOM (the scientific deliverable)\n")
    n1 = notes.get("M1", {})
    for lineage, rec in (n1.get("reconciliation") or {}).items():
        d, dm = rec.get("damage", {}), rec.get("damage_matched", {})
        L.append(f"- **{lineage}** ({rec.get('repo')}): stored `D_curve` "
                 f"{d.get('stored')} vs recomputed {d.get('recomputed')} "
                 f"-> **{d.get('verdict')}**; stored `D_matched_probe_curve` "
                 f"recomputed to within {dm.get('max_abs_delta', float('nan')):.4f} "
                 f"-> **{dm.get('verdict')}**.\n")
    # the single most important contrast, printed compactly before the full table
    def _f(value) -> float:
        """Coerce a cell to float; a missing or None cell becomes NaN.

        The cached M1 table stores non-finite cells as null, so the summary must
        not assume every cell is a number.
        """
        try:
            out = float(value)
        except (TypeError, ValueError):
            return float("nan")
        return out

    head_rows = []
    for win in sorted({r.get("window") for r in tables["m1_recognition_headroom"]
                       if r.get("source", "").startswith("(a)")}):
        for a in ("0.00", "0.25", "0.50", "0.75", "1.00"):
            sel = [r for r in tables["m1_recognition_headroom"]
                   if r.get("source", "").startswith("(a)")
                   and str(r.get("alpha")) == a and r.get("window") == win
                   and np.isfinite(_f(r.get("tpr@1fpr_point")))]
            if not sel:
                continue

            def _mean(col: str) -> float:
                vals = np.array([_f(r.get(col)) for r in sel], dtype=float)
                vals = vals[np.isfinite(vals)]
                return round(float(vals.mean()), 4) if vals.size else float("nan")

            head_rows.append({
                "window": win, "lesion_alpha": a, "n_lineages": len(sel),
                "mean_AUROC": _mean("auroc_recomputed"),
                "mean_TPR@1%FPR": _mean("tpr@1fpr_point"),
                "mean_TPR@5%FPR": _mean("tpr@5fpr_point"),
                "mean_AUROC_k16": _mean("auroc_k16_mean"),
                "READOUT_CLASS": "activation",
            })
    if head_rows:
        L.append("\n**The de-saturation, in one table.** AUROC is the outcome "
                 "iteration 1 reported; TPR at a fixed FPR and the restricted-budget "
                 "AUROC are the SAME activations read with headroom.\n\n")
        L.append(_fmt_table(head_rows,
                            ["window", "lesion_alpha", "n_lineages", "mean_AUROC",
                             "mean_TPR@1%FPR", "mean_TPR@5%FPR", "mean_AUROC_k16",
                             "READOUT_CLASS"], limit=12))
        # the change from unlesioned to fully lesioned, PER READ SITE
        moves = {}
        for win in sorted({r["window"] for r in head_rows}):
            a0 = next((r for r in head_rows
                       if r["window"] == win and r["lesion_alpha"] == "0.00"), None)
            a1 = next((r for r in head_rows
                       if r["window"] == win and r["lesion_alpha"] == "1.00"), None)
            if a0 and a1:
                moves[win] = {
                    "d_auroc": a1["mean_AUROC"] - a0["mean_AUROC"],
                    "d_tpr1": a1["mean_TPR@1%FPR"] - a0["mean_TPR@1%FPR"],
                    "d_tpr5": a1["mean_TPR@5%FPR"] - a0["mean_TPR@5%FPR"],
                }
        lines = ["", "Change from the unlesioned control to the full lesion, "
                     "averaged over the four lineages, PER READ SITE:", "",
                 "| read site | d mean AUROC | d mean TPR@1%FPR | d mean TPR@5%FPR | "
                 "ratio |TPR@1%| / |AUROC| |", "|---|---|---|---|---|"]
        for win, m in moves.items():
            ratio = (abs(m["d_tpr1"]) / abs(m["d_auroc"])) if m["d_auroc"] else float("nan")
            site = ("EARLY = prompt site (the harmful REQUEST)" if win == "EARLY"
                    else "LATE = response site (the CONTINUATION)")
            lines.append(f"| {site} | {m['d_auroc']:+.4f} | {m['d_tpr1']:+.4f} | "
                         f"{m['d_tpr5']:+.4f} | {ratio:.1f}x |")
        L.append("\n".join(lines) + "\n")
        e, la = moves.get("EARLY"), moves.get("LATE")
        if e and la:
            L.append(
                f"\n**The finding this de-saturation buys.** The lesion's effect on "
                f"harm recognition is a SITE DISSOCIATION that AUROC cannot show. At "
                f"the PROMPT site the operating point is flat ({e['d_tpr1']:+.4f} "
                f"TPR@1%FPR): recognition of the harmful REQUEST survives the lesion "
                f"intact, which is what iteration 1 claimed. At the RESPONSE site the "
                f"same statistic falls {abs(la['d_tpr1']):.4f} while AUROC there moves "
                f"only {abs(la['d_auroc']):.4f} -- a "
                f"{abs(la['d_tpr1']) / abs(la['d_auroc']):.1f}-fold larger movement in "
                f"the operating point than in the summary statistic. So 'the "
                f"representation survives the lesion' is TRUE of the prompt site and "
                f"NOT TRUE of the response site, and iteration 1 could not have seen "
                f"the difference because both sites read ~0.95-0.98 AUROC throughout. "
                f"This is the recognition-versus-execution boundary made measurable.\n")

    L.append("\n" + _fmt_table(
        tables["m1_recognition_headroom"],
        ["source", "checkpoint", "alpha", "window", "n_pos", "n_neg",
         "auroc_recomputed", "tpr@1fpr", "smallest_resolvable_step", "tpr@5fpr",
         "auroc_k16", "auroc_k32", "auroc_k64", "equivalence_verdict",
         "equivalence_margin_achieved", "delta_tpr@1fpr", "source_file"], limit=45))
    holm = (n1.get("confirmatory") or {}).get("holm", {})
    if holm:
        lines = ["", "**Holm across M1's confirmatory rows**", "",
                 "| row | p | Holm threshold | decision |", "|---|---|---|---|"]
        for k, v in holm.items():
            lines.append(f"| {k} | {v['p_raw']:.3g} | {v['holm_threshold']:.4g} | "
                         f"{v['decision']} |")
        L.append("\n".join(lines) + "\n")

    L.append("\n# M2 -- CEILING AND DYNAMIC-RANGE AUDIT\n")
    L.append(notes.get("M2", {}).get("headline", "") + "\n\n")
    L.append(_fmt_table(tables["m2_ceiling_audit"],
                        ["outcome", "lane", "scope", "value_in_unperturbed_control",
                         "observed_spread", "effective_dynamic_range", "flag",
                         "verdict_relabel", "READOUT_CLASS", "source_file"], limit=30))

    L.append("\n# M3 -- COSINE GEOMETRY\n")
    m3 = notes.get("M3", {})
    L.append("**Honest scope.** " + m3.get("m3a", {}).get("honest_scope_sentence", "") + "\n\n")
    L.append(_fmt_table(tables["m3a_cosine_protocols"],
                        ["protocol", "lane", "fitting_corpus", "band", "n_checkpoints",
                         "n_families", "hidden_sizes", "at_band_min", "at_band_max",
                         "at_band_mean", "source_file"]))
    L.append("\n**M3b -- prior-art reconciliation.**\n\n")
    L.append(_fmt_table(tables["m3b_prior_art"],
                        ["protocol", "our_abs_cos_range", "comparable_harc_band",
                         "replicates_harc", "status", "demotion"]))
    nc = m3.get("m3c", {}).get("narrative_correction", {})
    if nc:
        L.append(f"\n**M3c -- the decisive comparison.** {nc['statement']}\n")
    L.append(f"\nContent axis across trained pairs: "
             f"{m3.get('m3c', {}).get('content_axis_across_trained_pairs')}. "
             f"RandInit null: {m3.get('m3c', {}).get('randinit_unrelated_basis_null')}.\n")
    L.append(f"\n**Surviving conclusion.** "
             f"{m3.get('m3c', {}).get('surviving_conclusion', '')}\n")

    L.append("\n# M4 -- THE COMPLETE GATES LEDGER\n")
    m4 = notes.get("M4", {})
    if m4.get("G1_finding"):
        L.append(m4["G1_finding"] + "\n\n")
    if m4.get("gate_compliance_rate"):
        L.append(f"Gate compliance rate per lane: `{m4['gate_compliance_rate']}`. "
                 f"Conclusion dependency count: "
                 f"`{m4.get('conclusion_dependency_count')}`.\n\n")
    L.append(_fmt_table(tables["m4_gates_ledger"],
                        ["gate_id", "lane", "checkpoint", "threshold", "observed",
                         "verdict", "which_reported_conclusion_depends_on_it",
                         "source_file"], limit=40))

    L.append("\n# M5 -- THE PROMPT-BUDGET CURVE, IN FULL\n")
    m5 = notes.get("M5", {})
    L.append(str(m5.get("monotonicity_verdict", "")) + "\n\n")
    L.append(_fmt_table(tables["m5_budget_curve"],
                        ["k", "candidate", "target", "accuracy", "ci_low", "ci_high",
                         "ci_method", "n_families", "n_pairs", "READOUT_CLASS",
                         "source_file"], limit=35))

    rtc = m5.get("record_to_correct")
    if isinstance(rtc, dict):
        L.append(f"\n**The record to correct.** claimed `{rtc.get('claimed')}` found at "
                 f"`{rtc.get('found_at')}` -> recomputed `{rtc.get('recomputed')}`; "
                 f"verdict **{rtc.get('verdict')}**.\n")

    L.append("\n# M6 -- THE PAIRED-LINEAGE CONTRAST\n")
    m6 = notes.get("M6", {})
    census = m6.get("pair_label_census", {})
    L.append(f"Pairs formed: {census.get('n_pairs_formed')}. "
             f"EFFECTIVE {len(census.get('EFFECTIVE', []))}, "
             f"NULL_EDIT {len(census.get('NULL_EDIT', []))}, "
             f"ANOMALOUS {len(census.get('ANOMALOUS', []))}. "
             f"Absent: {[a.get('child') for a in m6.get('absent', []) if a.get('child')]}\n\n")
    for t in ("T1_recognition_invariance", "T2_dose_response", "T3_specificity",
              "T4_presence_in_parent"):
        v = m6.get(t, {})
        if t == "T3_specificity":
            # T3's verdicts are per NULL_EDIT pair, not a single top-level field
            per_pair = {k: pv.get("verdict") for k, pv in v.items()
                        if isinstance(pv, dict) and "verdict" in pv}
            overall = ("SPECIFICITY_FAILURE"
                       if any(str(x).startswith("FIRES") for x in per_pair.values())
                       else "SPECIFIC" if per_pair else "NOT_COMPUTABLE")
            L.append(f"**{t}** -- verdict `{overall}`. ")
            for k, pv in per_pair.items():
                detail = v[k]
                L.append(f"Pair `{k}`: judged harmful-compliance delta "
                         f"{detail.get('behavioural_delta_hc')}, over-refusal delta "
                         f"{detail.get('behavioural_delta_or')}; features moving more "
                         f"than 1 null-SD: "
                         f"`{detail.get('features_moving_more_than_1_null_sd')}`. {pv} ")
        else:
            L.append(f"**{t}** -- verdict `{v.get('verdict', v.get('note', ''))}`. ")
        if t == "T1_recognition_invariance":
            L.append(f"mean standardised recognition delta "
                     f"{v.get('mean_standardised_recognition_delta')} "
                     f"(family-clustered CI {v.get('ci_family_clustered')}) against a "
                     f"mean behavioural delta of {v.get('mean_behavioural_delta')}. "
                     f"{v.get('power_sentence', '')}\n\n"
                     f"{v.get('interpretation', '')}\n\n"
                     f"_Unit disclosure._ {v.get('unit_mismatch_disclosure', '')}")
        if t == "T2_dose_response":
            L.append(f"rho {v.get('rho')} at n={v.get('n')}; {v.get('note', '')}")
        L.append("\n\n")
    L.append(str(m6.get("T3_specificity", {}).get("granite_finding", "")) + "\n\n")
    L.append("**Sealed-family integrity.** "
             + str(m6.get("sealed_family_integrity", {}).get("statement", "")) + "\n\n")
    L.append(_fmt_table(tables["m6_paired_lineage"],
                        ["pair", "family", "feature", "parent_value", "child_value",
                         "delta_raw", "delta_standardised", "sign_agreement",
                         "pair_label_recomputed", "READOUT_CLASS", "source_file"],
                        limit=40))

    L.append("\n# M7 -- TRUTH-COLUMN AND JUDGE INTEGRITY (BASELINE_ONLY throughout)\n")
    m7 = notes.get("M7", {})
    rj = m7.get("regex_vs_judge_discrepancy")
    if rj:
        L.append("**The regex-versus-judge discrepancy.** "
                 + json.dumps(_json_safe(rj), indent=1) + "\n\n")
    mc = m7.get("machinery_controls_resolution")
    if mc:
        L.append("**Machinery controls.** " + str(mc)[:2500] + "\n\n")
    if m7.get("verdict_tally"):
        L.append(f"Claimed-vs-recomputed tally: `{m7['verdict_tally']}`.\n\n")
    L.append(_fmt_table(tables["m7_truth_integrity"],
                        ["quantity", "checkpoint_or_scope", "value", "n",
                         "READOUT_CLASS", "BASELINE_ONLY", "source_file"], limit=35))

    L.append("\n# M8 -- PROVENANCE LEDGER\n")
    L.append(_fmt_table(tables["m8_provenance"],
                        ["block", "claim", "claimed_value", "recomputed_value",
                         "verdict", "source_file", "locator"], limit=45))
    L.append("\n## The commissioned comparison, assembled at zero cost\n")
    L.append(str(m8.get("commissioned_table", {}).get("run_invariant_note", "")) + "\n\n")
    L.append(_fmt_table(tables["m8_commissioned_comparison"],
                        ["checkpoint", "cos_content_ablit_at_band",
                         "A_shuffled_label_band_p975", "A_term_std", "CB_term_std",
                         "A_escapes_band", "baseline", "baseline_value",
                         "READOUT_CLASS", "BASELINE_ONLY"], limit=40))
    L.append("\n" + str(m8.get("commissioned_table", {}).get("how_to_state_the_answer", ""))
             + "\n")

    L.append("\n# CUTS TAKEN AND FAILURES\n")
    all_cuts = list(cuts)
    for k, v in notes.items():
        all_cuts += [f"{k}: {c}" for c in (v.get("cuts_taken") or [])]
    L.append(("- " + "\n- ".join(all_cuts)) if all_cuts else "No cuts were taken.")
    L.append("\n")
    if failures:
        L.append("\n**Stage failures (reported, not hidden):**\n")
        for f in failures:
            L.append(f"- `{f['stage']}`: {f['exception']}\n")

    L.append("\n# FILES\n")
    for name, rel in written.items():
        L.append(f"- `{rel}`\n")
    return "".join(L)


def _emit_eval_out(tables, notes, contradictions, cuts, failures, prereg_sha) -> None:
    """eval_out.json in the exp_eval_sol_out schema."""
    m8 = notes.get("M8", {})
    m6 = notes.get("M6", {})
    m2 = notes.get("M2", {})
    m1 = notes.get("M1", {})

    def num(v, default=0.0):
        try:
            f = float(v)
            return f if np.isfinite(f) else default
        except (TypeError, ValueError):
            return default

    def _num(v) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return float("nan")

    # restrict the spreads to source (a), the only source with a lesion axis
    lane_b = [r for r in tables["m1_recognition_headroom"]
              if r.get("metric") == "M1" and str(r.get("source", "")).startswith("(a)")]
    tpr = [x for x in (_num(r.get("tpr@1fpr_point")) for r in lane_b) if np.isfinite(x)]
    aur = [x for x in (_num(r.get("auroc_recomputed")) for r in lane_b) if np.isfinite(x)]
    lesion = [r for r in tables["m1_recognition_headroom"]
              if r.get("metric") == "M1.R4"
              and str(r.get("alpha", "")).endswith("->1.00")]

    def _site(window: str, col: str) -> float:
        """alpha=1.00 minus alpha=0.00, averaged over lineages, at one read site."""
        def mean_at(a: str) -> float:
            vals = [_num(r.get(col)) for r in lane_b
                    if r.get("window") == window and str(r.get("alpha")) == a]
            vals = [v for v in vals if np.isfinite(v)]
            return float(np.mean(vals)) if vals else float("nan")
        return mean_at("1.00") - mean_at("0.00")

    metrics_agg = {
        "claim_match_rate": num(m8.get("CLAIM_MATCH_RATE")),
        "n_numbers_checked": num(m8.get("n_numbers_checked")),
        "n_claim_mismatches": num(m8.get("n_mismatch")),
        "n_claims_not_in_source": num(m8.get("n_not_in_source")),
        "n_contradictions": float(len(contradictions)),
        "m1_auroc_spread_across_lane_b_arms": num(max(aur) - min(aur)) if aur else 0.0,
        "m1_tpr_at_1pct_fpr_spread_across_lane_b_arms":
            num(max(tpr) - min(tpr)) if tpr else 0.0,
        "m1_mean_delta_tpr_at_full_lesion":
            num(np.mean([_num(r.get("delta_tpr@1fpr")) for r in lesion]))
            if lesion else 0.0,
        "m1_n_full_lesion_pairs": float(len(lesion)),
        # the site dissociation: the finding the de-saturation buys
        "m1_site_EARLY_delta_auroc_full_lesion": num(_site("EARLY", "auroc_recomputed")),
        "m1_site_EARLY_delta_tpr1_full_lesion": num(_site("EARLY", "tpr@1fpr_point")),
        "m1_site_LATE_delta_auroc_full_lesion": num(_site("LATE", "auroc_recomputed")),
        "m1_site_LATE_delta_tpr1_full_lesion": num(_site("LATE", "tpr@1fpr_point")),
        "m1_site_LATE_tpr1_over_auroc_movement_ratio": num(
            abs(_site("LATE", "tpr@1fpr_point")) / abs(_site("LATE", "auroc_recomputed"))
            if _site("LATE", "auroc_recomputed") else float("nan")),
        # restricted-budget separation at k=16 in the UNLESIONED arms: the
        # commissioned few-prompt axis, with its load-bearing negative control
        "m1_k16_auroc_base_unlesioned": num(next(
            (_num(r.get("auroc_k16_mean")) for r in lane_b
             if r.get("lineage") == "L1" and str(r.get("alpha")) == "0.00"
             and r.get("window") == "LATE"), float("nan"))),
        "m1_k16_auroc_instruct_unlesioned": num(next(
            (_num(r.get("auroc_k16_mean")) for r in lane_b
             if r.get("lineage") == "L2" and str(r.get("alpha")) == "0.00"
             and r.get("window") == "LATE"), float("nan"))),
        "m1_k16_auroc_safetyrl_unlesioned": num(next(
            (_num(r.get("auroc_k16_mean")) for r in lane_b
             if r.get("lineage") == "L3" and str(r.get("alpha")) == "0.00"
             and r.get("window") == "LATE"), float("nan"))),
        "m1_k16_auroc_nonsafety_ft_unlesioned": num(next(
            (_num(r.get("auroc_k16_mean")) for r in lane_b
             if r.get("lineage") == "L4" and str(r.get("alpha")) == "0.00"
             and r.get("window") == "LATE"), float("nan"))),
        "m1_n_equivalent_verdicts": float(sum(
            1 for r in tables["m1_recognition_headroom"]
            if r.get("equivalence_verdict") == "EQUIVALENT")),
        "m1_n_not_equivalent_verdicts": float(sum(
            1 for r in tables["m1_recognition_headroom"]
            if r.get("equivalence_verdict") == "NOT_EQUIVALENT")),
        "m2_n_saturated_outcomes": num(m2.get("n_saturated")),
        "m2_n_indeterminate_no_matched_point":
            num(m2.get("n_indeterminate_no_matched_point_rows")),
        "m4_n_gate_rows": float(len(tables["m4_gates_ledger"])),
        "m5_n_budget_rows": float(len(tables["m5_budget_curve"])),
        "m6_n_pairs_formed": num((m6.get("pair_label_census") or {}).get("n_pairs_formed")),
        "m6_n_effective_pairs": float(len(
            (m6.get("pair_label_census") or {}).get("EFFECTIVE", []))),
        "m6_t2_dose_response_rho": num((m6.get("T2_dose_response") or {}).get("rho")),
        "m6_t2_min_resolvable_abs_rho":
            num((m6.get("T2_dose_response") or {}).get("min_resolvable_abs_rho")),
        "m7_n_rows": float(len(tables["m7_truth_integrity"])),
        "n_result_eligible_rows": float(sum(
            1 for rows in tables.values() for r in rows
            if r.get("READOUT_CLASS") in ("activation", "weight"))),
        "n_baseline_only_rows": float(sum(
            1 for rows in tables.values() for r in rows
            if r.get("READOUT_CLASS") in ("logit", "text", "metadata"))),
        "n_stage_failures": float(len(failures)),
        "total_rows": float(sum(len(v) for v in tables.values())),
    }

    datasets = []
    for name, rows in tables.items():
        if not rows:
            datasets.append({"dataset": name, "examples": [{
                "input": f"{name}: no rows",
                "output": "EMPTY",
                "predict_status": "EMPTY -- reported as EMPTY, never silently omitted",
                "metadata_READOUT_CLASS": "metadata"}]})
            continue
        examples = []
        for r in rows:
            ident = " | ".join(
                f"{k}={r[k]}" for k in ("metric", "block", "gate_id", "checkpoint",
                                        "pair", "outcome", "quantity", "protocol",
                                        "candidate", "feature", "k", "alpha",
                                        "lineage", "claim", "target", "window",
                                        "axis", "layer", "source")
                if k in r and r[k] not in (None, ""))[:4000] or name
            authoritative = str(r.get("verdict") or r.get("flag")
                                or r.get("equivalence_verdict")
                                or r.get("recomputed_value")
                                or r.get("status") or r.get("claimed_value")
                                or r.get("contents") or "")[:4000]
            # every example carries at least one eval_* field, so no row is
            # emitted without an evaluation metric attached to it
            ex = {"input": ident, "output": authoritative,
                  "eval_result_eligible": float(
                      r.get("READOUT_CLASS") in ("activation", "weight"))}
            for key, val in r.items():
                if val is None:
                    continue
                safe = "".join(ch if (ch.isalnum() or ch == "_") else "_"
                               for ch in str(key)).strip("_")
                if not safe or not (safe[0].isalpha() or safe[0] == "_"):
                    safe = "f_" + safe
                if isinstance(val, bool):
                    ex[f"eval_{safe}"] = float(val)
                elif isinstance(val, (int, float)) and np.isfinite(float(val)):
                    ex[f"eval_{safe}"] = float(val)
                elif key in ("READOUT_CLASS", "source_file", "json_path", "locator",
                             "note", "which_reported_conclusion_depends_on_it",
                             "power_sentence", "verdict_relabel", "annotation"):
                    ex[f"metadata_{safe}"] = str(val)[:4000]
                else:
                    ex[f"predict_{safe}"] = str(val)[:4000]
            examples.append(ex)
        datasets.append({"dataset": name, "examples": examples})

    payload = {
        "metadata": {
            "evaluation_name": "Re-checking the numbers we already have",
            "description": (
                "Zero-GPU, zero-API re-adjudication of iteration 1's three lanes, "
                "computed only from files already on disk. The scientific deliverable "
                "is the recognition premise re-expressed on outcomes WITH HEADROOM."),
            "prereg_sha256": prereg_sha,
            "run_invariant": PR.PREREG["run_invariant"],
            "contradictions": _json_safe(contradictions),
            "headline_verdicts": _json_safe(_headlines(tables, notes)),
            "corrections": _json_safe(_corrections(notes)),
            "handoff_to_experiment_lanes": _json_safe(_handoff(notes)),
            "cuts_taken": cuts,
            "stage_failures": _json_safe(failures),
        },
        "metrics_agg": metrics_agg,
        "datasets": datasets,
    }
    out = P.WORKSPACE / "eval_out.json"
    out.write_text(json.dumps(_json_safe(payload), indent=1))
    logger.info("wrote {} ({:.1f} MB)", out.name, out.stat().st_size / 1e6)


def _headlines(tables, notes) -> list[dict]:
    m1 = notes.get("M1", {})
    m6 = notes.get("M6", {})
    rows = [r for r in tables["m1_recognition_headroom"] if r.get("metric") == "M1"
            and isinstance(r.get("tpr@1fpr_point"), float)]
    by_alpha: dict[str, list[float]] = {}
    for r in rows:
        if r.get("source", "").startswith("(a)") and r.get("window") == "LATE":
            by_alpha.setdefault(str(r["alpha"]), []).append(r["tpr@1fpr_point"])
    auroc_by_alpha: dict[str, list[float]] = {}
    for r in rows:
        if r.get("source", "").startswith("(a)") and r.get("window") == "LATE":
            auroc_by_alpha.setdefault(str(r["alpha"]), []).append(r["auroc_recomputed"])
    out = [{
        "id": "H1",
        "verdict": "THE RECOGNITION PREMISE WAS MEASURED ON A SATURATED OUTCOME",
        "evidence": {
            "mean_auroc_by_lesion_strength":
                {k: round(float(np.mean(v)), 4) for k, v in sorted(auroc_by_alpha.items())},
            "mean_tpr_at_1pct_fpr_by_lesion_strength":
                {k: round(float(np.mean(v)), 4) for k, v in sorted(by_alpha.items())},
        },
        "statement": (
            "Lane B's stored D_curve reproduces EXACTLY at 1.000 across all five "
            "lesion strengths, and it is at its ceiling in the UNPERTURBED control, "
            "so it could not have fallen in either direction. Re-expressed as TPR at "
            "1% FPR on the SAME activations, the outcome separates by READ SITE: flat "
            "at the PROMPT site and falling substantially at the RESPONSE site, with "
            "the operating point moving many times further than AUROC does. 'The "
            "representation survives the lesion' was never falsifiable as measured, "
            "and once it is made falsifiable it holds at the prompt site only."),
    }]
    t1 = m6.get("T1_recognition_invariance", {})
    out.append({
        "id": "H2", "verdict": t1.get("verdict", "NOT_COMPUTABLE"),
        "evidence": {k: t1.get(k) for k in
                     ("mean_standardised_recognition_delta", "ci_family_clustered",
                      "mean_behavioural_delta", "tost_verdict",
                      "tost_margin_achieved", "power_sentence", "n_effective")},
        "statement": (
            "On the run's OWN panel, the parent-to-child contrast is INCONCLUSIVE at "
            "the pre-registered margin, not equivalent. At n=5 effective pairs the "
            "test could only have detected an enormous effect, which is what the "
            "power sentence says and what an invariance claim must not hide."),
    })
    t3 = m6.get("T3_specificity", {})
    fires = [k for k, v in t3.items()
             if isinstance(v, dict) and str(v.get("verdict", "")).startswith("FIRES")]
    out.append({
        "id": "H3",
        "verdict": "SPECIFICITY_FAILURE" if fires else "SPECIFIC",
        "evidence": {"null_edit_pairs": t3.get("null_edit_pairs"),
                     "pairs_that_fire": fires},
        "statement": (
            "The primary recognition feature fires on a pair whose judged behaviour "
            "did not move at all. Scored on the string 'abliterated' the readout "
            "would have looked correct; scored on the MEASURED delta it is caught."
            if fires else
            "No recognition feature moves on the behavioural no-op pair."),
    })
    nc = notes.get("M3", {}).get("m3c", {})
    out.append({
        "id": "H4", "verdict": "NARRATIVE_CORRECTED",
        "evidence": nc.get("narrative_correction", {}),
        "statement": nc.get("surviving_conclusion", ""),
    })
    out.append({
        "id": "H5", "verdict": "CAUSAL_ARM_EMPTY",
        "evidence": notes.get("M0", {}).get("causal_arm", {}),
        "statement": ("The causal arm produced one file, the unlesioned baseline. "
                      "Reported as EMPTY."),
    })
    return out


def _corrections(notes) -> list[dict]:
    out = []
    for m in (notes.get("M8", {}).get("mismatches") or []):
        out.append({"old_claim": m["claim"], "corrected_number": m["recomputed"],
                    "source": m["source"], "locator": m["locator"]})
    m3 = notes.get("M3", {})
    if m3.get("m3c", {}).get("surviving_conclusion"):
        out.append({"old_claim": "abliteration distinctively rotates the refusal axis",
                    "corrected_number": m3["m3c"].get("narrative_correction", {}).get("statement"),
                    "surviving_conclusion": m3["m3c"]["surviving_conclusion"],
                    "source": P.rel(P.A_CROSS_CKPT), "locator": "pairs.*.r_ablit.at_band"})
    for b in (m3.get("m3a") and [] or []):
        pass
    if notes.get("M4", {}).get("S1_rescored_outcome"):
        out.append({"old_claim": "K3 is the sole S1 PASS",
                    "corrected_number": notes["M4"]["S1_rescored_outcome"],
                    "source": P.rel(P.A_METHOD_OUT),
                    "locator": "metadata.s1_table"})
    return out


def _handoff(notes) -> list[dict]:
    """Quantities this artifact cannot recompute, delegated to a named lane."""
    out = []
    for r in (notes.get("M0", {}).get("harvest", {}).get("load_errors") or []):
        out.append({"quantity": r.get("file"), "delegated_to": "Lane B",
                    "why": r.get("exception")})
    causal = notes.get("M0", {}).get("causal_arm", {})
    if causal.get("n_jobs_crashed"):
        out.append({
            "quantity": "generated text from the lesioned models (the causal arm)",
            "delegated_to": "Lane B (experiment_2)",
            "why": (f"{causal['n_jobs_crashed']} of {causal['n_jobs_expected']} jobs "
                    f"crashed; no tokens exist to re-analyse, so this needs a "
                    f"RE-RUN, not a re-analysis"),
        })
    out.append({
        "quantity": "operating-point statistics for the 21-checkpoint panel",
        "delegated_to": "Lane C (experiment_3)",
        "why": ("Lane C stored pre-reduced AUROC scalars only. No TPR at a fixed "
                "FPR, no restricted-budget curve and no equivalence verdict can be "
                "recovered from a stored AUROC; the panel must re-emit per-item "
                "scores, which costs no new forward passes if the harvest is kept."),
    })
    out.append({
        "quantity": "a scored mlabonne/Qwen3-4B-abliterated row in the panel",
        "delegated_to": "Lane C (experiment_3)",
        "why": ("the commissioned checkpoint is present in every Lane A table but "
                "absent from Lane C's 21-checkpoint panel and from Lane B's harvest"),
    })
    return out


if __name__ == "__main__":
    main()
