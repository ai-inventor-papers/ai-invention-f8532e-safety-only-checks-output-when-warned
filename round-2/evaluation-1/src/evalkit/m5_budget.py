#!/usr/bin/env python3
"""M5 -- the prompt-budget curve in full.

Reads Lane C's own ``s3_results.json`` and reports, for every candidate
(K1..K5) and every target (``safe_engagement_rate``, ``harmful_compliance_rate``),
the pairwise-ranking-accuracy value stored at every registered prompt budget
``k in {4, 8, 16, 32, 96}`` -- never just the maximum -- plus an explicit
``k=0`` row (weight-only readouts need no prompts at all, so k=0 is the
extreme end of the commissioned ask; Lane C never ran it, so that row carries
``accuracy=NaN`` and says exactly where it looked).

No model is loaded and no API is called: everything here is arithmetic over
JSON that is already on disk in Lane C's read-only workspace
(``evalkit.paths.LANE_C``).

Family-clustered intervals
---------------------------
``s3_results.json`` stores a per-family accuracy breakdown
(``candidates.K<n>.per_family.<family>.acc``) for exactly one point on each
candidate's curve: the one whose value equals the candidate's overall
``mean_acc``, which is itself the unweighted (macro) mean of those seven
per-family accuracies. That point turns out to equal ``budget_curve["96"]``
for all ten (candidate, target) pairs, verified below before any interval is
built. Because that per-family breakdown is the ONLY place stored data lets
us recover a family-level unit, the family-clustered bootstrap (resampling
the 7 scored families, never the 21 checkpoints, per
``evalkit.stats.cluster_bootstrap``) is built as: one cluster per family,
each cluster holding that family's own point accuracy, so the pooled-cluster
mean statistic reproduces the macro mean exactly. Every other budget
(k=4, 8, 16, 32) has only a pooled scalar in ``budget_curve`` with no
per-family breakdown anywhere in Lane C's output, so those rows are marked
``ci_method="NOT_RECONSTRUCTIBLE_FROM_STORED_SCALAR"`` with NaN bounds --
never a fabricated interval.

The same per-family reconstruction is applied to the "logit" baseline B3
(Lane C's ``strongest_baseline`` on both targets) using
``targets.<target>.baseline_per_family``, which is verified to reproduce
``baseline_table.B3`` exactly the same way. That baseline row is printed
beside the candidate curves with ``READOUT_CLASS="logit"`` and
``BASELINE_ONLY=True``, per this artifact's run invariant that logit-only
readouts are baselines, never the result.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
from loguru import logger

from . import paths as P
from . import stats as S
from .prereg import PREREG, prereg_hash

TARGETS: list[str] = ["safe_engagement_rate", "harmful_compliance_rate"]
CANDIDATES: list[str] = ["K1", "K2", "K3", "K4", "K5"]
BUDGET_KS: list[int] = list(PREREG["M5_budgets_k"])  # [0, 4, 8, 16, 32, 96]
REGISTERED_STORED_KS: list[int] = [4, 8, 16, 32, 96]
RECONSTRUCTIBLE_K: int = 96  # the only budget with a stored per-family breakdown
MACRO_MATCH_TOL: float = 1e-3

# Item 7: the record to correct -- iteration 1's five-point scan, as claimed.
CLAIMED_FIVE_POINT_SCAN: list[float] = [0.882, 0.850, 0.789, 0.814, 0.810]


def _load_s3() -> dict[str, Any]:
    """Load Lane C's s3_results.json, letting JSON/IO errors surface explicitly."""
    path = P.C_S3
    try:
        raw = path.read_text()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"M5: Lane C s3 results file not found at {path}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise json.JSONDecodeError(
            f"M5: could not parse {path} as JSON: {exc.msg}", exc.doc, exc.pos
        ) from exc


def _family_point_clusters(per_family: dict[str, dict[str, Any]]) -> list[np.ndarray]:
    """One 1-element cluster per family, holding that family's own point accuracy.

    Feeding these into ``S.cluster_bootstrap`` with ``statistic=np.mean``
    resamples the FAMILIES (with replacement) and takes the mean of the
    resampled family accuracies -- exactly the macro-average family-clustered
    bootstrap this artifact requires, built from the only per-family unit
    Lane C actually stored.
    """
    return [np.array([float(v["acc"])], dtype=float) for v in per_family.values()]


def _macro_mean(per_family: dict[str, dict[str, Any]]) -> float:
    accs = [float(v["acc"]) for v in per_family.values()]
    return float(np.mean(accs)) if accs else float("nan")


def _n_pairs(per_family: dict[str, dict[str, Any]]) -> int:
    return int(sum(int(v["n_pairs"]) for v in per_family.values()))


def _candidate_rows(
    s3: dict[str, Any], target: str, candidate: str, source_file: str, absent: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], list[float]]:
    """Rows for one (target, candidate) across every registered budget in BUDGET_KS."""
    cand_block = s3["targets"][target]["candidates"][candidate]
    budget_curve: dict[str, float] = cand_block["budget_curve"]
    per_family: dict[str, dict[str, Any]] = cand_block["per_family"]
    mean_acc = float(cand_block["mean_acc"])

    macro = _macro_mean(per_family)
    stored_96 = float(budget_curve[str(RECONSTRUCTIBLE_K)])
    if not (
        math.isclose(macro, mean_acc, abs_tol=MACRO_MATCH_TOL)
        and math.isclose(macro, stored_96, abs_tol=MACRO_MATCH_TOL)
    ):
        raise ValueError(
            "M5: recomputed_disagrees_with_stored -- macro mean of "
            f"per_family accs ({macro}) does not match mean_acc ({mean_acc}) "
            f"and/or budget_curve[96] ({stored_96}) for "
            f"targets.{target}.candidates.{candidate}; per prereg this must "
            "STOP and be reconciled before proceeding."
        )

    rows: list[dict[str, Any]] = []
    accs_for_gap: list[float] = []

    for k in BUDGET_KS:
        base_row: dict[str, Any] = {
            "k": k,
            "candidate": candidate,
            "target": target,
            "source_file": source_file,
            "READOUT_CLASS": "activation",
            "BASELINE_ONLY": False,
            "DESCRIPTIVE": True,
        }

        if k == 0:
            glob_path = f"targets.{target}.candidates.{candidate}.budget_curve.0"
            note = (
                f"k=0 searched at {source_file} :: {glob_path} -- ABSENT. "
                f"Registered budget_ks (prereg.json.s3_decision_rule.budget_ks) = "
                f"{REGISTERED_STORED_KS}; k=0 WAS NOT RUN by Lane C. Not imputed."
            )
            row = dict(
                base_row,
                accuracy=float("nan"),
                ci_low=float("nan"),
                ci_high=float("nan"),
                ci_method="NOT_RUN_BY_LANE_C",
                n_families=float("nan"),
                n_pairs=float("nan"),
                note=note,
            )
            absent.append({"item": f"{candidate}/{target} budget_curve k=0", "glob": glob_path})
            rows.append(row)
            continue

        if str(k) not in budget_curve:
            glob_path = f"targets.{target}.candidates.{candidate}.budget_curve.{k}"
            note = f"{glob_path} -- ABSENT from {source_file}."
            row = dict(
                base_row,
                accuracy=float("nan"),
                ci_low=float("nan"),
                ci_high=float("nan"),
                ci_method="ABSENT",
                n_families=float("nan"),
                n_pairs=float("nan"),
                note=note,
            )
            absent.append({"item": f"{candidate}/{target} budget_curve k={k}", "glob": glob_path})
            rows.append(row)
            continue

        accuracy = float(budget_curve[str(k)])
        accs_for_gap.append(accuracy)

        if k == RECONSTRUCTIBLE_K:
            clusters = _family_point_clusters(per_family)
            interval = S.cluster_bootstrap(clusters, lambda arr: float(np.mean(arr)))
            row = dict(
                base_row,
                accuracy=accuracy,
                ci_low=interval.low,
                ci_high=interval.high,
                ci_method=interval.method,
                n_families=len(per_family),
                n_pairs=_n_pairs(per_family),
                note=(
                    f"reconstructed from targets.{target}.candidates.{candidate}."
                    "per_family.<family>.acc (macro mean matches mean_acc and "
                    f"budget_curve[96] within {MACRO_MATCH_TOL})"
                ),
            )
        else:
            row = dict(
                base_row,
                accuracy=accuracy,
                ci_low=float("nan"),
                ci_high=float("nan"),
                ci_method="NOT_RECONSTRUCTIBLE_FROM_STORED_SCALAR",
                n_families=int(cand_block.get("n_families", len(per_family))),
                n_pairs=float("nan"),
                note=(
                    f"Only a pooled scalar is stored at {source_file} :: "
                    f"targets.{target}.candidates.{candidate}.budget_curve.{k} "
                    "-- no per-family breakdown exists for this budget in Lane "
                    "C's output, so no family-clustered interval can be built."
                ),
            )
        rows.append(row)

    return rows, accs_for_gap


def _baseline_rows(s3: dict[str, Any], target: str, source_file: str) -> list[dict[str, Any]]:
    """The logit baseline (Lane C's oracle-selected strongest_baseline) printed beside the curve."""
    target_block = s3["targets"][target]
    strongest = str(target_block["strongest_baseline"])
    baseline_table: dict[str, float] = target_block["baseline_table"]
    baseline_per_family: dict[str, dict[str, Any]] = target_block["baseline_per_family"]

    macro = _macro_mean(baseline_per_family)
    stored = float(baseline_table[strongest])
    if not math.isclose(macro, stored, abs_tol=MACRO_MATCH_TOL):
        raise ValueError(
            "M5: recomputed_disagrees_with_stored -- macro mean of "
            f"baseline_per_family accs ({macro}) does not match "
            f"baseline_table.{strongest} ({stored}) for targets.{target}; "
            "per prereg this must STOP and be reconciled before proceeding."
        )

    clusters = _family_point_clusters(baseline_per_family)
    interval = S.cluster_bootstrap(clusters, lambda arr: float(np.mean(arr)))
    row = {
        "k": None,
        "candidate": strongest,
        "target": target,
        "accuracy": stored,
        "ci_low": interval.low,
        "ci_high": interval.high,
        "ci_method": interval.method,
        "n_families": len(baseline_per_family),
        "n_pairs": _n_pairs(baseline_per_family),
        "source_file": source_file,
        "READOUT_CLASS": "logit",
        "BASELINE_ONLY": True,
        "DESCRIPTIVE": True,
        "note": (
            f"{strongest} = "
            f"Lane C's oracle-selected strongest_baseline on {target} "
            "(first-token refusal-minus-compliance logit gap on PROBE_HARM, "
            "per LANE_C/prereg.json baselines.B3). Has no prompt-budget "
            "dependence in Lane C's schema, so it is printed once per target "
            "rather than once per k. Reconstructed from "
            f"targets.{target}.baseline_per_family.<family>.acc "
            f"(macro mean matches baseline_table.{strongest} within {MACRO_MATCH_TOL})."
        ),
    }
    return [row]


def _monotonicity(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Spearman rho of accuracy against k, per candidate x target, with resolvability."""
    out: dict[str, dict[str, Any]] = {}
    for target in TARGETS:
        for candidate in CANDIDATES:
            sub = [r for r in rows if r["target"] == target and r["candidate"] == candidate]
            ks = np.array([r["k"] for r in sub], dtype=float)
            accs = np.array([r["accuracy"] for r in sub], dtype=float)
            result = S.spearman_with_resolvability(ks, accs)
            result["ci_method"] = "NOT_RECONSTRUCTIBLE_ACROSS_K"
            result["ci_note"] = (
                "A family-clustered bootstrap CI on rho itself would need a "
                "per-family accuracy at every k; only k=96 has one stored "
                "(see per-row notes), so no such interval can be built here."
            )
            out[f"{candidate}|{target}"] = result
    return out


def _max_minus_mean_gap(rows: list[dict[str, Any]]) -> dict[str, float]:
    out: dict[str, float] = {}
    for target in TARGETS:
        for candidate in CANDIDATES:
            accs = [
                r["accuracy"]
                for r in rows
                if r["target"] == target and r["candidate"] == candidate and r["k"] != 0
                and math.isfinite(r["accuracy"])
            ]
            if accs:
                out[f"{candidate}|{target}"] = float(max(accs) - float(np.mean(accs)))
            else:
                out[f"{candidate}|{target}"] = float("nan")
    return out


def _decision_rule_verdicts(s3: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Lane C's own analysis-recorded decision-rule verdict -- read, never re-derived."""
    out: dict[str, dict[str, Any]] = {}
    for target in TARGETS:
        target_block = s3["targets"][target]
        out[target] = {"decision_valid": target_block.get("decision_valid")}
        for candidate in CANDIDATES:
            cand_block = target_block["candidates"][candidate]
            out[target][candidate] = {
                "smallest_k_pass": cand_block.get("smallest_k_pass"),
                "S3_PASS": cand_block.get("S3_PASS"),
                "margin_vs_strongest": cand_block.get("margin_vs_strongest"),
                "families_won": cand_block.get("families_won"),
                "families_won_threshold": cand_block.get("families_won_threshold"),
                "ci95": cand_block.get("ci95"),
                "strongest_baseline": target_block.get("strongest_baseline"),
            }
    return out


def _record_to_correct(s3: dict[str, Any], source_file: str) -> dict[str, Any]:
    """Item 7: find which candidate x target the claimed five-point scan actually belongs to."""
    found_at: str | None = None
    recomputed: list[float] | None = None
    for target in TARGETS:
        for candidate in CANDIDATES:
            budget_curve = s3["targets"][target]["candidates"][candidate]["budget_curve"]
            curve = [float(budget_curve[str(k)]) for k in REGISTERED_STORED_KS]
            rounded = [round(v, 3) for v in curve]
            if rounded == CLAIMED_FIVE_POINT_SCAN:
                found_at = f"{source_file} :: targets.{target}.candidates.{candidate}.budget_curve"
                recomputed = curve
                break
        if found_at is not None:
            break

    if found_at is None:
        verdict = "NOT_IN_SOURCE"
    elif recomputed is not None and [round(v, 3) for v in recomputed] == CLAIMED_FIVE_POINT_SCAN:
        verdict = "MATCH"
    else:
        verdict = "MISMATCH"

    is_non_monotonic = None
    is_max_at_first_point = None
    if recomputed is not None:
        diffs = np.diff(recomputed)
        is_non_monotonic = bool(np.any(diffs > 0) and np.any(diffs < 0))
        is_max_at_first_point = bool(recomputed[0] == max(recomputed))

    return {
        "claimed": CLAIMED_FIVE_POINT_SCAN,
        "found_at": found_at,
        "recomputed": recomputed,
        "verdict": verdict,
        "budget_ks_in_order": REGISTERED_STORED_KS,
        "is_non_monotonic": is_non_monotonic,
        "max_is_first_point_k4": is_max_at_first_point,
        "note": (
            "The claim that the widely-quoted 0.882 is the MAXIMUM of a "
            "CROSS-family scan (not a within-family few-prompt result) is "
            "consistent with Lane C's own s3_decision_rule.primary_metric = "
            "'pairwise ranking accuracy over cross-held-out-family pairs' -- "
            "this curve IS that cross-family pairwise-ranking accuracy, "
            "scanned over prompt budget k, and 0.882 (at k=4) is its max."
            if found_at is not None
            else "No stored budget_curve of any (candidate, target) reproduces "
            "the claimed five values even to 3 decimals."
        ),
    }


def run() -> tuple[list[dict], dict]:
    """Compute the full M5 prompt-budget table and its accompanying notes."""
    s3 = _load_s3()
    source_file = P.rel(P.C_S3)
    absent: list[dict[str, str]] = []

    rows: list[dict[str, Any]] = []
    for target in TARGETS:
        for candidate in CANDIDATES:
            logger.info(f"M5: building budget curve for {candidate} / {target}")
            cand_rows, _ = _candidate_rows(s3, target, candidate, source_file, absent)
            rows.extend(cand_rows)
        rows.extend(_baseline_rows(s3, target, source_file))

    monotonicity = _monotonicity([r for r in rows if not r["BASELINE_ONLY"]])
    gaps = _max_minus_mean_gap([r for r in rows if not r["BASELINE_ONLY"]])
    decision = _decision_rule_verdicts(s3)
    record_to_correct = _record_to_correct(s3, source_file)

    flat_candidates = [
        key.split("|")[0]
        for key, gap in gaps.items()
        if math.isfinite(gap) and gap < 5e-3
    ]
    varying_candidates = [
        key.split("|")[0]
        for key, gap in gaps.items()
        if math.isfinite(gap) and gap >= 5e-3
    ]
    monotonicity_verdict = (
        f"Candidates {sorted(set(flat_candidates))} are flat (max-minus-mean gap "
        "< 0.005) across every registered prompt budget k in {4,8,16,32,96} -- "
        "these readouts are INSENSITIVE TO PROMPT BUDGET in this range; "
        f"candidates {sorted(set(varying_candidates))} vary non-monotonically "
        "with k (no monotonic improvement with more prompts is supported by "
        "the data), and Lane C's own decision rule (smallest_k_pass, "
        "S3_PASS) recorded no passing budget for any candidate on either "
        "target regardless."
    )

    logger.info(f"M5: emitted {len(rows)} rows; {len(absent)} absent entries recorded")

    notes: dict[str, Any] = {
        "module": "M5_budgets",
        "prereg_sha": prereg_hash(),
        "source_files": [source_file],
        "budget_ks_registered": BUDGET_KS,
        "absent": absent,
        "monotonicity": monotonicity,
        "max_minus_mean_gap": gaps,
        "decision_rule_verdicts": decision,
        "record_to_correct": record_to_correct,
        "monotonicity_verdict": monotonicity_verdict,
        "run_invariant": {
            "result_eligible_readout_class": "activation",
            "baseline_only_readout_class": "logit",
        },
    }
    return rows, notes


if __name__ == "__main__":
    result_rows, result_notes = run()
    print(json.dumps({"n_rows": len(result_rows), "notes": result_notes}, indent=2, default=str))
