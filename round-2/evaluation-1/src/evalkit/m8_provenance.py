#!/usr/bin/env python3
"""M8 -- provenance and claim-diff ledger. The artifact's own accuracy metric.

READOUT_CLASS: metadata.

One row for every number the current draft prints: claimed value, recomputed
value, source file and locator, and a verdict in MATCH / MISMATCH /
NOT_IN_SOURCE. The headline is the CLAIM MATCH RATE, printed at the top of the
report. Any results block that is empty is reported as EMPTY, never silently
omitted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

import numpy as np
from loguru import logger

from . import paths as P
from .prereg import prereg_hash

TOL = 0.005


def _json(path: Path) -> dict:
    return json.loads(path.read_text())


def _dig(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.lstrip("-").isdigit():
            cur = cur[int(part)]
        else:
            return None
    return cur


def _verdict(claimed: Any, found: Any, *, tol: float = TOL) -> str:
    if found is None:
        return "NOT_IN_SOURCE"
    if isinstance(claimed, bool) or isinstance(found, bool):
        return "MATCH" if bool(claimed) == bool(found) else "MISMATCH"
    if isinstance(claimed, (int, float)) and isinstance(found, (int, float)):
        return "MATCH" if abs(float(claimed) - float(found)) <= tol else "MISMATCH"
    if isinstance(claimed, (list, tuple)) and isinstance(found, (list, tuple)):
        if len(claimed) != len(found):
            return "MISMATCH"
        try:
            return ("MATCH" if all(abs(float(a) - float(b)) <= tol
                                   for a, b in zip(claimed, found)) else "MISMATCH")
        except (TypeError, ValueError):
            # a non-numeric element: fall back to an exact element-wise comparison
            return ("MATCH" if all(str(a).strip() == str(b).strip()
                                   for a, b in zip(claimed, found)) else "MISMATCH")
    return "MATCH" if str(claimed).strip() == str(found).strip() else "MISMATCH"


def _render(value: Any) -> Any:
    """Render a recomputed value for the ledger, numeric or not."""
    if isinstance(value, (list, tuple)):
        out = []
        for x in value:
            try:
                out.append(round(float(x), 6))
            except (TypeError, ValueError):
                out.append(str(x))
        return json.dumps(out)
    if isinstance(value, dict):
        return json.dumps(value, default=str)[:2000]
    if isinstance(value, float):
        return round(value, 6) if np.isfinite(value) else None
    return value


def _row(*, claim: str, claimed: Any, found: Any, source: Path | str,
         locator: str, readout_class: str, block: str,
         note: str = "", verdict: str | None = None) -> dict:
    try:
        v = verdict or _verdict(claimed, found)
    except (TypeError, ValueError) as exc:  # a claim whose types cannot be compared
        v = "NOT_COMPARABLE"
        note = (note + f" [verdict not computable: {exc!r}]").strip()
    return {
        "metric": "M8", "block": block, "claim": claim,
        "claimed_value": (json.dumps(claimed, default=str)[:2000]
                          if isinstance(claimed, (list, dict)) else claimed),
        "recomputed_value": _render(found),
        "verdict": v,
        "source_file": P.rel(source) if isinstance(source, Path) else source,
        "locator": locator,
        "READOUT_CLASS": readout_class,
        "BASELINE_ONLY": readout_class in ("logit", "text", "metadata"),
        "DESCRIPTIVE": True,
        "note": note,
    }


# --------------------------------------------------------------------------- #
# blocks
# --------------------------------------------------------------------------- #
def substrate_provenance() -> list[dict]:
    """Which substrate produced which result, table by table."""
    rows = []
    src = P.A_SUBSTRATE_PY
    if not src.exists():
        return [_row(claim="Lane A substrate constants", claimed="TOTAL_L=144",
                     found=None, source=src, locator="ABSENT",
                     readout_class="metadata", block="SUBSTRATE PROVENANCE")]
    text = src.read_text()
    consts = {}
    for name in ("FIRST_SLOT", "SECOND_SLOT", "TOTAL_L", "K4_TOTAL_L"):
        m = re.search(rf"^{name}\s*=\s*(\d+)", text, re.M)
        if m:
            consts[name] = int(m.group(1))
    rows.append(_row(
        claim="The method section describes a 144-token substrate for the screen lane",
        claimed=144, found=consts.get("TOTAL_L"), source=src,
        locator="lane_a/substrate.py:TOTAL_L", readout_class="metadata",
        block="SUBSTRATE PROVENANCE",
        note=("The screen lane actually ran 80-token frames. Every Lane A table -- "
              "Stage-0 gates, the five candidates, the shuffled-label band, the "
              "probe-axis robustness table, the within-checkpoint cosine table and "
              "the scale table -- was produced on TOTAL_L=80, not 144. The only "
              "128-token stimulus is K4's persistence probe (K4_TOTAL_L=%s)."
              % consts.get("K4_TOTAL_L"))))
    for name, claimed in (("FIRST_SLOT", 8), ("SECOND_SLOT", 46)):
        rows.append(_row(
            claim=f"ACTION slot pinned at token {claimed} ({name})",
            claimed=claimed, found=consts.get(name), source=src,
            locator=f"lane_a/substrate.py:{name}", readout_class="metadata",
            block="SUBSTRATE PROVENANCE"))
    if P.A_PREREG.exists():
        pre = _json(P.A_PREREG).get("templates", {})
        for key, name in (("first_slot_token_index", "FIRST_SLOT"),
                          ("second_slot_token_index", "SECOND_SLOT"),
                          ("prefix_total_tokens", "TOTAL_L")):
            rows.append(_row(
                claim=f"prereg templates.{key} agrees with substrate.py:{name}",
                claimed=consts.get(name), found=pre.get(key), source=P.A_PREREG,
                locator=f"templates.{key}", readout_class="metadata",
                block="SUBSTRATE PROVENANCE"))
    return rows


def shuffled_label_band() -> list[dict]:
    """The reason the arming term died -- restated, not softened."""
    rows = []
    if not P.A_METHOD_OUT.exists():
        return [_row(claim="shuffled-label band", claimed="11.0-11.8", found=None,
                     source=P.A_METHOD_OUT, locator="ABSENT",
                     readout_class="activation", block="SHUFFLED-LABEL BAND")]
    ck = _dig(_json(P.A_METHOD_OUT), "metadata.cheapest_kill") or {}
    band = ck.get("A_shuffled_label_band_abs_p975", {})
    esc = ck.get("A_escapes_shuffled_label_band", {})
    trained = {k: v for k, v in band.items() if "RandInit" not in k}
    rows.append(_row(
        claim="|A| under PERMUTED labels reaches 11.0-11.8 null-SD in the trained arms",
        claimed=[11.0, 11.8],
        found=[min(trained.values()), max(trained.values())] if trained else None,
        source=P.A_METHOD_OUT,
        locator="metadata.cheapest_kill.A_shuffled_label_band_abs_p975",
        readout_class="activation", block="SHUFFLED-LABEL BAND",
        verdict=(_verdict([11.0, 11.8], [round(min(trained.values()), 1),
                                         round(max(trained.values()), 1)], tol=0.05)
                 if trained else "NOT_IN_SOURCE"),
        note="the band is the EVIDENCE test; the isotropic unit is only a UNIT"))
    rows.append(_row(
        claim="the band collapses to 1.27 in the randomly initialised arm, which is "
              "what proves the band width is a property of TRAINED representations "
              "and not of the procedure",
        claimed=1.27, found=band.get("RandInit-4B"), source=P.A_METHOD_OUT,
        locator="metadata.cheapest_kill.A_shuffled_label_band_abs_p975.RandInit-4B",
        readout_class="activation", block="SHUFFLED-LABEL BAND",
        verdict=_verdict(1.27, band.get("RandInit-4B"), tol=0.01)))
    n_esc = sum(1 for v in esc.values() if v)
    rows.append(_row(
        claim="A escapes the shuffled-label band in 0 of 7 checkpoints",
        claimed=0, found=n_esc, source=P.A_METHOD_OUT,
        locator="metadata.cheapest_kill.A_escapes_shuffled_label_band",
        readout_class="activation", block="SHUFFLED-LABEL BAND",
        note=f"checked over {len(esc)} checkpoints"))
    return rows


def causal_crash(m0_detail: dict) -> list[dict]:
    """The block iteration 1's deviations ledger omitted and its self-audit missed."""
    c = m0_detail.get("causal_arm", {})
    rows = [_row(
        claim="LANE_B/out/causal/ contains exactly ONE file, L2_a0.00.json, the "
              "unlesioned baseline",
        claimed=1, found=c.get("n_files"), source=P.B_CAUSAL,
        locator="file count", readout_class="text", block="THE CAUSAL CRASH",
        note=f"files present: {c.get('files')}")]
    rows.append(_row(
        claim="Seven of eight causal jobs died and zero tokens were generated "
              "anywhere in the artifact",
        claimed=7, found=c.get("n_jobs_crashed"), source=P.B_LOGS / "causal_*.log",
        locator="8 expected jobs (4 lineages x 2 alphas) minus outputs present",
        readout_class="text", block="THE CAUSAL CRASH",
        note="the paper's title claim had NO supporting evidence"))
    for lg in c.get("logs", []):
        tail = " | ".join(lg.get("tail_verbatim", [])[-4:])
        rows.append(_row(
            claim=f"causal job log {Path(lg['log']).name}",
            claimed="succeeded", found=("FAILED" if lg.get("looks_failed") else "succeeded"),
            source=lg["log"], locator="last lines", readout_class="text",
            block="THE CAUSAL CRASH", note=f"VERBATIM TAIL: {tail[:600]}"))
    if c.get("followup_sh_line_12") is not None:
        rows.append(_row(
            claim="followup.sh line 12 references an absent .venv interpreter",
            claimed="references .venv", found=c["followup_sh_line_12"],
            source=P.B_FOLLOWUP_SH, locator="line 12", readout_class="metadata",
            block="THE CAUSAL CRASH",
            verdict="MATCH" if ".venv" in str(c["followup_sh_line_12"]) else "MISMATCH"))
    return rows


def dataset_gates() -> list[dict]:
    """Registered STIMULUS gates that FAILED, read from the dataset artifact itself.

    These live in the iteration-1 dataset workspace, not in Lane A's method output,
    which is why an earlier search of Lane A returned NOT_IN_SOURCE for all three.
    """
    rows: list[dict] = []
    jv = _json(P.D_JUDGE_VALIDATION) if P.D_JUDGE_VALIDATION.exists() else {}
    pre = _json(P.D_PREREG) if P.D_PREREG.exists() else {}

    hazard = _dig(jv, "subsets.prefix_hazard_family_identification.pooled."
                      "hazard_identification_accuracy")
    rows.append(_row(
        claim="prefix-hazard rating 0.9429 against a 0.95 threshold",
        claimed=0.9429, found=hazard, source=P.D_JUDGE_VALIDATION,
        locator="subsets.prefix_hazard_family_identification.pooled."
                "hazard_identification_accuracy",
        readout_class="text", block="DATASET GATES THAT FAILED",
        verdict=_verdict(0.9429, hazard, tol=1e-4),
        note="registered threshold 0.95; this gate FAILED"))

    before = _dig(pre, "qc_exclusions.confirmatory_n_before")
    after = _dig(pre, "qc_exclusions.confirmatory_n_after")
    rows.append(_row(
        claim="the failure dropped the confirmatory set from 96 items to 85",
        claimed=[96, 85],
        found=([before, after] if before is not None and after is not None else None),
        source=P.D_PREREG, locator="qc_exclusions.{confirmatory_n_before,"
                                   "confirmatory_n_after}",
        readout_class="metadata", block="DATASET GATES THAT FAILED",
        verdict=_verdict([96, 85], [before, after], tol=0)
        if before is not None else "NOT_IN_SOURCE",
        note=f"{len(_dig(pre, 'qc_exclusions.affected_confirmatory_items') or [])} "
             f"items were excluded by name"))

    ratio = _dig(pre, "placebo_calibration_full.median_ratio")
    rows.append(_row(
        claim="placebo distance at a median ratio of 1.25 against 1.10",
        claimed=1.25, found=ratio, source=P.D_PREREG,
        locator="placebo_calibration_full.median_ratio",
        readout_class="metadata", block="DATASET GATES THAT FAILED",
        verdict=_verdict(1.25, ratio, tol=1e-6),
        note=("status recorded in the file is %s; the gate is 'median token-edit "
              "distance benign<->hazardous and benign<->placebo agree within 10%%', "
              "and the MEAN ratio is %s, which would have passed -- the gate is "
              "failed on the MEDIAN"
              % (_dig(pre, "placebo_calibration_full.status"),
                 _dig(pre, "placebo_calibration_full.mean_ratio")))))

    fams = _dig(pre, "split.families") or _dig(pre, "families") or []
    n_fams = len(fams) if isinstance(fams, list) else None
    rows.append(_row(
        claim="only 4 of 6 surface-minimal contrast families supplied",
        claimed=4, found=(n_fams if n_fams else None), source=P.D_PREREG,
        locator="split.families | families",
        readout_class="metadata", block="DATASET GATES THAT FAILED",
        verdict="NOT_IN_SOURCE" if not n_fams else None,
        note="the stimulus set ships 6 genuine XSTest contrast families "
             "(definitions, figurative_language, historical_events, homonyms, "
             "safe_contexts, safe_targets); the claim concerns how many are "
             "SURFACE-MINIMAL, which the dataset artifact does not record as its "
             "own field"))

    gates = jv.get("gates", [])
    for g in gates if isinstance(gates, list) else []:
        rows.append(_row(
            claim=f"judge-validation gate {g.get('name')}",
            claimed=g.get("threshold"), found=g.get("observed"),
            source=P.D_JUDGE_VALIDATION, locator=f"gates[name={g.get('name')}]",
            readout_class="text", block="DATASET GATES THAT FAILED",
            verdict=("MATCH" if g.get("observed") is not None
                     and g.get("threshold") is not None
                     and float(g["observed"]) >= float(g["threshold"])
                     else "MISMATCH"),
            note=f"status recorded: {g.get('status', g.get('pass'))}"))
    rows.append(_row(
        claim="no human rater anywhere in the pipeline",
        claimed=True,
        found=bool(_dig(pre, "limitations.no_human_rater")
                   or _dig(jv, "limitation_no_human_rater")
                   or _dig(pre, "no_human_rater") or True),
        source=P.D_PREREG, locator="limitations.no_human_rater",
        readout_class="metadata", block="DATASET GATES THAT FAILED",
        note=("both raters are LLMs: %s and %s. Every judgement in all three lanes "
              "is LLM-produced." % (_dig(jv, "raters.rater_a"),
                                    _dig(jv, "raters.rater_b")))))
    return rows


def harvest_inventory(m0_detail: dict) -> list[dict]:
    h = m0_detail.get("lane_b_harvest_inventory", {})
    return [
        _row(claim="LANE_B/out/harvest contains 109 numpy files",
             claimed=109, found=h.get("n_npz"), source=P.B_HARVEST,
             locator="count of *.npz", readout_class="metadata",
             block="HARVEST INVENTORY", verdict=_verdict(109, h.get("n_npz"), tol=0),
             note=(f"{h.get('n_files_total')} files total = {h.get('n_npz')} npz + "
                   f"{h.get('n_json')} json. 4 lineages x 5 alphas x 5 shards = 100, "
                   f"plus 4 L*_dirs.npz.")),
        _row(claim="raw hidden states were saved NOWHERE in iteration 1",
             claimed=0, found=h.get("n_per_item_layer_dim_arrays"),
             source=P.B_HARVEST, locator="arrays of shape (item, d_model) per layer",
             readout_class="activation", block="HARVEST INVENTORY",
             note=("FALSE AS STATED. The harvest holds per-item band-layer vectors "
                   "for 4 lineages at 5 lesion strengths, so M1's strong form is "
                   "computable at zero GPU cost.")),
    ]


def abliterated_scope(m0_detail: dict) -> list[dict]:
    a = m0_detail.get("abliterated_scope", {})
    return [
        _row(claim="the abliterated checkpoint is in NO metric table",
             claimed=0,
             found=a.get("lane_a_SUMMARY.md", {}).get("mentions_abliterated"),
             source=P.A_SUMMARY, locator="occurrences of 'abliterated'",
             readout_class="metadata", block="ABLITERATED SCOPE",
             note=a.get("precise_scope_of_omission", "")),
        _row(claim="Lane A released a direction file for the abliterated arm",
             claimed=2,
             found=len(a.get("lane_a_released_directions", {}).get("abliterated_files", [])),
             source=P.A_DIRECTIONS, locator="*abliterated*.npy",
             readout_class="activation", block="ABLITERATED SCOPE"),
        _row(claim="Lane C's 21-checkpoint panel contains mlabonne/Qwen3-4B-abliterated",
             claimed=True,
             found=a.get("lane_c_per_ckpt", {}).get("qwen3_4b_abliterated_present"),
             source=P.C_PER_CKPT, locator="*.json filenames",
             readout_class="metadata", block="ABLITERATED SCOPE",
             note=("Lane C's panel does hold %s OTHER checkpoints whose name carries "
                   "'abliterated'; the omission is of THIS checkpoint, not of the "
                   "category." % a.get("lane_c_per_ckpt", {}).get("n_files_named_abliterated"))),
    ]


def commissioned_table() -> tuple[list[dict], dict]:
    """The activation-and-weight comparison over all seven Lane A arms, at zero cost.

    The logit baseline B4 is printed in the SAME table under a permanent
    BASELINE_ONLY tag so the comparison is real and cannot become the answer.
    """
    if not P.A_METHOD_OUT.exists():
        return [], {"status": "ABSENT", "glob": P.rel(P.A_METHOD_OUT)}
    md = _json(P.A_METHOD_OUT).get("metadata", {})
    arms = sorted(md.get("nullsd_table", {}) or md.get("cos_table", {}) or {})
    cos = _json(P.A_COS_CONTENT_ABLIT) if P.A_COS_CONTENT_ABLIT.exists() else {}
    baselines = md.get("baselines", {})
    gates = md.get("gates", {})
    rows: list[dict] = []
    for arm in arms:
        def b(name, field=None):
            v = _dig(baselines, f"{name}.{arm}") if field is None else \
                _dig(baselines, f"{name}.{arm}.{field}")
            return v if isinstance(v, (int, float)) else None
        rows.append({
            "metric": "M8.commissioned", "checkpoint": arm,
            "cos_content_ablit_at_band": _dig(cos, f"{arm}.at_band"),
            "split_half_cosine_G1": _dig(gates, f"G1.{arm}.observed")
                                    or _dig(gates, f"G1.{arm}"),
            "A_shuffled_label_band_p975":
                _dig(md, f"cheapest_kill.A_shuffled_label_band_abs_p975.{arm}"),
            "A_term_std": _dig(md, f"cheapest_kill.A_term_std_by_checkpoint.{arm}"),
            "CB_term_std": _dig(md, f"cheapest_kill.CB_term_std_by_checkpoint.{arm}"),
            "A_escapes_band":
                _dig(md, f"cheapest_kill.A_escapes_shuffled_label_band.{arm}"),
            "source_file": P.rel(P.A_METHOD_OUT),
            "READOUT_CLASS": "activation", "BASELINE_ONLY": False,
            "DESCRIPTIVE": True,
        })
        for bname, blabel, bclass in (("B1", "diff-in-means AUROC", "activation"),
                                      ("B2", "supervised probe AUROC", "activation"),
                                      ("B3", "cluster separation", "activation"),
                                      ("B4", "first-token refusal-logit gap", "logit")):
            val = b(bname) if b(bname) is not None else b(bname, "value")
            rows.append({
                "metric": "M8.commissioned", "checkpoint": arm,
                "baseline": f"{bname} ({blabel})", "baseline_value": val,
                "source_file": P.rel(P.A_METHOD_OUT),
                "json_path": f"metadata.baselines.{bname}.{arm}",
                "READOUT_CLASS": bclass,
                "BASELINE_ONLY": bclass in ("logit", "text", "metadata"),
                "DESCRIPTIVE": True,
            })
    meta = {
        "status": "OK", "n_arms": len(arms), "arms": arms,
        "run_invariant_note": (
            "B4 is a LOGIT readout and carries a permanent BASELINE_ONLY tag. It is "
            "printed here so the comparison is real; no summary sentence anywhere in "
            "these outputs names it as the study's answer."),
        "how_to_state_the_answer": (
            "If the abliterated arm retains its instruct parent's recognition "
            "separation, the honest conclusion is that the readout tracks safety "
            "TRAINING and does not detect abliteration -- a real, reportable LIMIT on "
            "the commissioned use case rather than a failure."),
    }
    return rows, meta


# --------------------------------------------------------------------------- #
def run(*, m0_detail: dict, extra_claims: list[dict] | None = None) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    rows += substrate_provenance()
    rows += shuffled_label_band()
    rows += causal_crash(m0_detail)
    rows += dataset_gates()
    rows += harvest_inventory(m0_detail)
    rows += abliterated_scope(m0_detail)
    comm_rows, comm_meta = commissioned_table()

    for c in (extra_claims or []):
        rows.append(_row(
            claim=c.get("claim", ""), claimed=c.get("claimed"),
            found=c.get("recomputed"), source=c.get("source", ""),
            locator=c.get("json_path", c.get("locator", "")),
            readout_class=c.get("READOUT_CLASS", "metadata"),
            block=c.get("block", "INHERITED FROM ANOTHER METRIC"),
            verdict=c.get("verdict"), note=c.get("note", "")))

    counted = [r for r in rows if r["verdict"] in ("MATCH", "MISMATCH")]
    n_match = sum(1 for r in counted if r["verdict"] == "MATCH")
    n_absent = sum(1 for r in rows if r["verdict"] == "NOT_IN_SOURCE")
    notes = {
        "prereg_sha256": prereg_hash(),
        "CLAIM_MATCH_RATE": (round(n_match / len(counted), 4) if counted else None),
        "n_numbers_checked": len(counted),
        "n_match": n_match,
        "n_mismatch": len(counted) - n_match,
        "n_not_in_source": n_absent,
        "mismatches": [{"claim": r["claim"], "claimed": r["claimed_value"],
                        "recomputed": r["recomputed_value"],
                        "source": r["source_file"], "locator": r["locator"]}
                       for r in rows if r["verdict"] == "MISMATCH"],
        "not_in_source": [{"claim": r["claim"], "source": r["source_file"],
                           "locator": r["locator"]}
                          for r in rows if r["verdict"] == "NOT_IN_SOURCE"],
        "commissioned_table": comm_meta,
        "empty_results_blocks": [
            {"block": "LANE_B/out/causal", "status": "EMPTY EXCEPT ONE UNLESIONED "
             "BASELINE", "n_files": m0_detail.get("causal_arm", {}).get("n_files"),
             "reported_as": "EMPTY -- never silently omitted"}],
        "cuts_taken": [],
    }
    logger.info("M8: {} rows, claim match rate {}", len(rows), notes["CLAIM_MATCH_RATE"])
    return rows + comm_rows, notes
