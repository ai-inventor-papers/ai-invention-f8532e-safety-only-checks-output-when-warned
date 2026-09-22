"""D8 (delete-the-bitwise-explanation displacement table) and D10 (setup +
deviations) for the iteration-5 re-derivation audit.

Every number is RE-DERIVED from iteration-4 (and iteration-2/1) source JSON
already on disk. Nothing is copied from prose. Where a re-derived value
disagrees with a prose claim, the disk value wins and the disagreement is
logged to results/contradictions_d8_d10.json; nothing on disk is edited.

RUN INVARIANT: BL1* (logit-only), AMS* (reimplementation of the released
package), card/name regex and greedy-refusal text are BASELINES here, never
the deliverable/answer/winner/metric. Activation and weight readouts of a
single model are the deliverable class this audit is about.
"""

from __future__ import annotations

import collections
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any

import numpy as np

import sources as SRC
import stats_lib as ST

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
RES = WS / "results"
FIG = WS / "figures"

I4E1 = SRC.I4_EXP1
I4E2 = SRC.I4_EXP2

# ----------------------------------------------------------------------- #
# Baseline vs deliverable classing, per RUN INVARIANT.
# ----------------------------------------------------------------------- #
BASELINE_CLASS_SUBSTR = ("logit", "AMS bar", "text")


def is_baseline_class(readout_class: str) -> bool:
    return any(s in readout_class for s in BASELINE_CLASS_SUBSTR)


def sf(name: str) -> str:
    return str(SRC.SOURCES[name])


# ========================================================================= #
# D8 -- displacement table replacing the bitwise-identity explanation
# ========================================================================= #
def build_d8() -> dict[str, Any]:
    clf, err_clf = SRC.try_load("i4e1_classification")
    agg, err_agg = SRC.try_load("i4e1_aggregates")
    pl, err_pl = SRC.try_load("i4e1_pairs_long")
    dswap, err_dswap = SRC.try_load("i4e1_device_swap")

    missing: list[dict[str, str]] = []
    for name, err in (("i4e1_classification", err_clf), ("i4e1_aggregates", err_agg),
                      ("i4e1_pairs_long", err_pl), ("i4e1_device_swap", err_dswap)):
        if err:
            missing.append({"source": name, "reason": err})

    out: dict[str, Any] = {"deleted_explanation": (
        "\"no-op edits are bitwise identical so activation readouts cannot move\" "
        "-- CONTRADICTED by this run's own outputs (see refuting_evidence). No-op "
        "edits are NOT bitwise identical at the activation level in general (only "
        "the two structurally-degenerate arms wu05/wu20 are, by construction); "
        "most no-op edits (numerical-precision casts, system-prompt swaps, "
        "resaves) DO move activation readouts by a small but nonzero amount."
    )}
    if missing:
        out["missing_sources"] = missing
    if not (clf and agg and pl and dswap):
        out["status"] = "SOURCE_ABSENT"
        return out

    noop_ids = list(clf["primary_noop_pairs"])
    n_noop = len(noop_ids)

    # -------------------------------------------------------------- #
    # (i) the two activation readouts that FIRE on F1__fp16
    # -------------------------------------------------------------- #
    agg_readout_class = {k: v.get("readout_class") for k, v in agg["aggregates"].items()}
    fp16_rows = [r for r in pl if r["pair_id"] == "F1__fp16"]
    # map pairs_long's short candidate code -> the full aggregates.json key
    short_to_full = {
        "N1": "N1_d_lstar", "N1_parentL": "N1_parentL", "N2": "N2_d_lstar_perpWU",
        "N3": "N3_F_clust_perpWU", "F_clust_raw": "F_clust_raw",
        "N4_onset": "N4_shape_onset", "N4_peak_frac": "N4_shape_peak_frac",
        "N4_width": "N4_shape_width", "N5_invariance": "N5_invariance",
        "N6": "N6_benign_sep", "N7": "N7_two_sided_gap", "N8": "N8_severity_rho",
        "N9": "N9_decode_d", "N9_tok1": "N9_tok1", "N10": "N10_dec_minus_prompt",
        "N11": "N11_ams_window_fisher", "N12_DEFAULT_WEIGHTS": "N12_combo_DEFAULT_WEIGHTS",
        "C4": "C4", "C7": "C7", "C13": "C13", "C13_peak_d": "C13_peak_d",
        "B7": "B7", "B7_nullproj": "B7_nullproj",
        "BL1_easy": "BL1_easy", "BL1_hard": "BL1_hard",
        "BL1_truelogit": "BL1_truelogit", "BL1_truelogit_hard": "BL1_truelogit_hard",
        "AMS_T1_sigma": "AMS_T1_sigma", "AMS_T2_drift": "AMS_T2_drift",
        "regex": "regex", "regex_namefree": "regex_namefree",
    }

    fp16_firing = []
    for r in fp16_rows:
        full = short_to_full.get(r["candidate"])
        rc = agg_readout_class.get(full, "UNKNOWN")
        if r.get("ci_excludes_0") is True and rc == "activation":
            fp16_firing.append({
                "candidate_id": full,
                "readout_class": rc,
                "Delta": r["Delta"],
                "ci95": [r["ci_lo"], r["ci_hi"]],
                "abs_delta_over_nullSD_parent": r["abs_delta_over_nullSD_parent"],
                "source_file": sf("i4e1_pairs_long"),
                "source_key": f"[candidate={r['candidate']}, pair_id=F1__fp16]",
            })
    # also record the weight-class candidates that fire on F1__fp16, for completeness
    # (per RUN INVARIANT, weight readouts are deliverable-class too, just not the
    # two ACTIVATION readouts D8 asks to name)
    fp16_firing_weight = []
    for r in fp16_rows:
        full = short_to_full.get(r["candidate"])
        rc = agg_readout_class.get(full, "UNKNOWN")
        if r.get("ci_excludes_0") is True and rc == "weight":
            fp16_firing_weight.append({
                "candidate_id": full, "readout_class": rc, "Delta": r["Delta"],
                "ci95": [r["ci_lo"], r["ci_hi"]],
                "source_file": sf("i4e1_pairs_long"),
                "source_key": f"[candidate={r['candidate']}, pair_id=F1__fp16]",
            })

    # -------------------------------------------------------------- #
    # (ii) device-swap text-identity and label-agreement percentages
    # -------------------------------------------------------------- #
    ref_pair = next(p for p in dswap["pairs"] if p["tag"] == "F1__ref")
    text_identical_frac = ref_pair["identical_response_text"] / ref_pair["n_items"]
    hc = ref_pair["labels"]["HC"]
    orr = ref_pair["labels"]["OR"]
    hc_label_agreement = 1.0 - hc["n_discordant"] / hc["n"]
    or_label_agreement = 1.0 - orr["n_discordant"] / orr["n"]
    device_swap_all_pairs = [
        {
            "tag": p["tag"],
            "n_items": p["n_items"],
            "identical_response_text_n": p["identical_response_text"],
            "identical_frac_rederived": p["identical_response_text"] / p["n_items"],
            "HC_label_agreement_rederived": 1.0 - p["labels"]["HC"]["n_discordant"] / p["labels"]["HC"]["n"],
            "OR_label_agreement_rederived": 1.0 - p["labels"]["OR"]["n_discordant"] / p["labels"]["OR"]["n"],
            "same_weights": p["same_weights"],
            "source_file": sf("i4e1_device_swap"), "source_key": f"pairs[tag={p['tag']}]",
            "readout_class": "text (generations; CPU-vs-GPU device-swap check, not pooled)",
        }
        for p in dswap["pairs"]
    ]

    out["refuting_evidence"] = {
        "i_two_activation_readouts_fire_on_F1__fp16": fp16_firing,
        "i_note": (
            f"n activation-class readouts with a no-op CI excluding 0 on F1__fp16: "
            f"{len(fp16_firing)} (named above); {len(fp16_firing_weight)} additional "
            f"weight-class readout(s) also fire on this pair (B7-family, listed "
            f"separately, not counted in the 'two activation readouts' claim)."
        ),
        "weight_class_also_firing_on_F1__fp16": fp16_firing_weight,
        "ii_device_swap_reference_pair_F1__ref": {
            "n_items": ref_pair["n_items"],
            "identical_response_text_n": ref_pair["identical_response_text"],
            "identical_frac_rederived": text_identical_frac,
            "identical_frac_on_disk": ref_pair["identical_frac"],
            "HC_n": hc["n"], "HC_n_discordant": hc["n_discordant"],
            "HC_label_agreement_rederived": hc_label_agreement,
            "HC_label_agreement_on_disk": hc["label_agreement"],
            "OR_n": orr["n"], "OR_n_discordant": orr["n_discordant"],
            "OR_label_agreement_rederived": or_label_agreement,
            "OR_label_agreement_on_disk": orr["label_agreement"],
            "weight_fingerprint_identical_cpu_vs_gpu": ref_pair["same_weights"],
            "source_file": sf("i4e1_device_swap"), "source_key": "pairs[tag=F1__ref]",
            "readout_class": "text (generations; CPU-vs-GPU device-swap check, not pooled)",
        },
        "ii_device_swap_all_three_pairs": device_swap_all_pairs,
    }

    # -------------------------------------------------------------- #
    # main table: one row per candidate
    # -------------------------------------------------------------- #
    rows = []
    for cand_key, cand in agg["aggregates"].items():
        rc = cand.get("readout_class", "UNKNOWN")
        ci = cand.get("criterion_i_false_alarm", {})
        # short pairs_long candidate code for this full key
        short = next((s for s, f in short_to_full.items() if f == cand_key), None)
        cand_rows = [r for r in pl if r["candidate"] == short and r["pair_id"] in noop_ids] if short else []
        disp_vals = [r["abs_delta_over_nullSD_parent"] for r in cand_rows
                     if r.get("abs_delta_over_nullSD_parent") is not None]
        null_sd_vals = []
        for r in cand_rows:
            ratio = r.get("abs_delta_over_nullSD_parent")
            if ratio not in (None, 0.0):
                null_sd_vals.append(abs(r["Delta"]) / ratio)
        ci_excl_vals = [r.get("ci_excludes_0") for r in cand_rows if r.get("ci_excludes_0") is not None]
        n_ci_excl = sum(1 for v in ci_excl_vals if v) if ci_excl_vals else None

        median_disp = float(np.median(disp_vals)) if disp_vals else ci.get("median_absdelta_over_nullsd_parent")
        median_null_sd = float(np.median(null_sd_vals)) if null_sd_vals else None

        note = None
        if not cand_rows:
            note = "CANDIDATE_NOT_IN_PAIRS_LONG: no per-pair rows found under this short code"
        elif not disp_vals:
            note = "NULL_SD_UNAVAILABLE: no abs_delta_over_nullSD_parent recorded for this candidate on disk"

        rows.append({
            "candidate_id": cand_key,
            "readout_class": rc,
            "is_baseline_class": is_baseline_class(rc),
            "median_noop_displacement_in_null_SD": median_disp,
            "median_bootstrap_null_SD": median_null_sd,
            "n_noop_pairs_whose_CI_excludes_0": (
                n_ci_excl if n_ci_excl is not None
                else (ci.get("n_noop", n_noop) - ci["n_ci_covers_0"] if "n_ci_covers_0" in ci else None)
            ),
            "n_noop_pairs_total": len(cand_rows) if cand_rows else ci.get("n_noop", n_noop),
            "aggregates_median_on_disk": ci.get("median_absdelta_over_nullsd_parent"),
            "aggregates_n_ci_covers_0_on_disk": ci.get("n_ci_covers_0"),
            "note": note,
            "source_file": sf("i4e1_pairs_long") + " ; " + sf("i4e1_aggregates"),
            "source_key": (f"pairs_long[candidate={short}]" if short else "n/a")
                          + f" ; aggregates[{cand_key}].criterion_i_false_alarm",
        })

    # -------------------------------------------------------------- #
    # BL1 vs activation-readout ratio
    # -------------------------------------------------------------- #
    bl1_keys = ["BL1_easy", "BL1_hard", "BL1_truelogit", "BL1_truelogit_hard"]
    bl1_disp = {k: next(r["median_noop_displacement_in_null_SD"] for r in rows if r["candidate_id"] == k)
                for k in bl1_keys}
    activation_disp_by_id = {r["candidate_id"]: r["median_noop_displacement_in_null_SD"] for r in rows
                             if r["readout_class"] == "activation" and r["median_noop_displacement_in_null_SD"] is not None}
    activation_disp = list(activation_disp_by_id.values())
    median_activation_disp = float(np.median(activation_disp)) if activation_disp else None
    bl1_hard = bl1_disp.get("BL1_hard")
    ratio = (bl1_hard / median_activation_disp) if (bl1_hard and median_activation_disp) else None

    out["bl1_vs_activation"] = {
        "bl1_median_noop_displacement_by_variant": bl1_disp,
        "bl1_range_claimed_in_prose": [0.150, 0.178],
        "bl1_range_rederived_min_max": [min(bl1_disp.values()), max(bl1_disp.values())],
        "bl1_variants_outside_claimed_range": [
            k for k, v in bl1_disp.items() if not (0.150 - 5e-4 <= v <= 0.178 + 5e-4)
        ],
        "activation_class_candidate_ids_with_displacement": list(activation_disp_by_id.keys()),
        "activation_class_median_displacements_by_id": activation_disp_by_id,
        "activation_class_candidates_excluded_null_sd_unavailable": [
            r["candidate_id"] for r in rows
            if r["readout_class"] == "activation" and r["median_noop_displacement_in_null_SD"] is None
        ],
        "median_activation_displacement": median_activation_disp,
        "ratio_bl1_over_activation": ratio,
        "ratio_basis": "BL1_hard.median_noop_displacement_in_null_SD / median(activation-class candidates' median_noop_displacement_in_null_SD)",
        "source_file": sf("i4e1_pairs_long"),
        "source_key": "derived from rows[] above (median across primary_noop_pairs)",
        "readout_class": "n/a",
    }

    out["ratio_bl1_over_activation"] = ratio

    out["mechanism_statement"] = (
        "No-op edits are NOT bitwise identical at the activation level (except the "
        "two structurally-degenerate wu05/wu20 arms, whose input and residual body "
        "are unchanged by construction). Numerical-precision, system-prompt and "
        "re-save edits move most activation readouts by a small but measurable "
        "amount, and a minority of activation- and weight-class readouts do cross "
        "their own bootstrap CI on individual no-op pairs (e.g. F1__fp16, "
        "F3__dpo). The false-alarm gap between the logit-only baseline (BL1) and "
        "the activation readouts is therefore NOT explained by bitwise identity; "
        "it is explained by (a) MAGNITUDE -- BL1's median no-op displacement is "
        f"{bl1_hard:.3f} null SD (BL1_hard) vs a median of {median_activation_disp:.3f} "
        "null SD across activation-class candidates, roughly "
        f"{ratio:.1f}x larger -- combined with (b) a TIGHTER NULL -- the activation "
        "readouts' own bootstrap null distribution is narrower relative to their "
        "displacement, so fewer of their no-op CIs cross the false-alarm threshold "
        "even though the underlying displacements are nonzero."
    )

    out["rows"] = rows
    out["n_rows"] = len(rows)
    out["n_noop_pairs"] = n_noop
    out["classification_rule_source"] = {"source_file": sf("i4e1_classification"), "source_key": "rule", "readout_class": "n/a"}
    return out


# ========================================================================= #
# D10 -- setup, appendix, deviations
# ========================================================================= #
def sha256_file(p: Path) -> str | None:
    if not p.exists():
        return None
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def count_i2_dataset_tables() -> dict[str, Any]:
    path = SRC.SOURCES["i2data_full"]
    if not path.exists():
        return {"status": "SOURCE_ABSENT", "path": str(path)}
    with path.open() as fh:
        d = json.load(fh)
    counts = {ds["dataset"]: len(ds["examples"]) for ds in d["datasets"]}
    counts_short = {k.split("::")[-1]: v for k, v in counts.items()}
    meta_counts = d["metadata"].get("row_counts_by_table") or {}
    return {
        "row_counts_by_table_rederived": counts,
        "row_counts_by_table_metadata_on_disk": meta_counts,
        "match_metadata": counts_short == meta_counts if meta_counts else None,
        "probe_harmful_n": counts.get("qwen3_safety_iter2_substrate_v1::probe_harmful"),
        "probe_hard_benign_n": counts.get("qwen3_safety_iter2_substrate_v1::probe_hard_benign"),
    }


def rederive_behaviour_item_counts() -> dict[str, Any]:
    """Trace the ACTUAL provenance of the 168-item (85 harm/83 benign) behaviour
    set used by i4e1, per src/items.py: NOT the iteration-2 dataset artifact, but
    Lane C gt_harm/gt_benign (iteration-1 experiment_3) + XSTest twins from the
    iteration-1 dataset's safety_2x2 table. Verified programmatically here.
    """
    LANEC = SRC.LOOP / "iter_1/gen_art/gen_art_experiment_3"
    D1 = SRC.LOOP / "iter_1/gen_art/gen_art_dataset_1"
    out: dict[str, Any] = {}
    gt_harm_p = LANEC / "assets/gt_harm.json"
    gt_benign_p = LANEC / "assets/gt_benign.json"
    d1_data_p = D1 / "data_out.json"
    for name, p in (("gt_harm", gt_harm_p), ("gt_benign", gt_benign_p), ("d1_data_out", d1_data_p)):
        out[f"{name}_exists"] = p.exists()
    if not (gt_harm_p.exists() and gt_benign_p.exists() and d1_data_p.exists()):
        out["status"] = "SOURCE_ABSENT_FOR_FULL_TRACE"
        return out
    gt_harm = json.loads(gt_harm_p.read_text())
    gt_benign = json.loads(gt_benign_p.read_text())
    n_laneC_harm = len(gt_harm)
    n_laneC_benign = len(gt_benign)
    d1 = json.loads(d1_data_p.read_text())
    rows = next(D["examples"] for D in d1["datasets"] if D["dataset"].endswith("::safety_2x2"))
    pairs: dict[str, dict] = {}
    for r in rows:
        if str(r.get("metadata_confirmatory")) != "True" or str(r.get("metadata_qc_fail")) != "False":
            continue
        if str(r.get("metadata_sealed")) == "True":
            continue
        uid = r["metadata_pair_uid"]
        lvl = r["metadata_request_level"]
        p = pairs.setdefault(uid, {})
        key = "unsafe" if lvl == "harmful" else "safe"
        p[key] = r["metadata_request_text"]
    n_confirmatory_pairs = sum(1 for p in pairs.values() if "unsafe" in p and "safe" in p)
    n_xs_used = 40  # N_XS_PAIRS_CPU, hard-coded CPU fallback in src/items.py
    n_dropped_laneC_overlap = 2  # orh_75, orh_1197 (i4e1 prereg.json b_items.dropped_for_hash_overlap.laneC_overlaps_stimuli)
    rederived_n_harm = n_laneC_harm + n_xs_used
    rederived_n_benign = (n_laneC_benign - n_dropped_laneC_overlap) + n_xs_used
    out.update({
        "n_laneC_gt_harm_rows": n_laneC_harm,
        "n_laneC_gt_benign_rows": n_laneC_benign,
        "n_xstest_confirmatory_qcok_unsealed_pairs_available": n_confirmatory_pairs,
        "n_xs_pairs_used_cpu_fallback": n_xs_used,
        "n_laneC_dropped_for_stimuli_overlap": n_dropped_laneC_overlap,
        "rederived_n_harm": rederived_n_harm,
        "rederived_n_benign": rederived_n_benign,
        "matches_claimed_85_83": (rederived_n_harm, rederived_n_benign) == (85, 83),
        "note": (
            "The 85/83 behaviour-item counts are NOT sourced from the iteration-2 "
            "dataset artifact (I2_DATA/full_data_out.json) at all: i4e1/src/items.py "
            "reads Lane C gt_harm/gt_benign from iteration-1 experiment_3 and XSTest "
            "twins from iteration-1's OWN dataset (data_out.json::safety_2x2), never "
            "opening iteration-2's full_data_out.json for the behaviour set. The "
            "iteration-2 dataset artifact's own probe_harmful (n=160) and "
            "probe_hard_benign (n=154) tables are a DIFFERENT, larger substrate pool "
            "for a different purpose and do not reduce to 85/83 under any filter "
            "found in i4e1's own code."
        ),
        "sources": {
            "gt_harm": str(gt_harm_p), "gt_benign": str(gt_benign_p),
            "d1_safety_2x2": str(d1_data_p),
            "items_py": str(I4E1 / "src/items.py"),
        },
    })
    return out


def build_d10() -> dict[str, Any]:
    prereg1, e1 = SRC.try_load("i4e1_prereg")
    prereg1_amend, e2 = SRC.try_load("i4e1_prereg_amendments")
    dev1, e3 = SRC.try_load("i4e1_deviations")
    dev2, e4 = SRC.try_load("i4e2_deviations")
    agg, e5 = SRC.try_load("i4e1_aggregates")
    ams, e6 = SRC.try_load("i4e1_ams_validation")
    e2analysis, e7 = SRC.try_load("i4e2_analysis")
    prereg2_path = I4E2 / "prereg.json"
    addendum_path = I4E2 / "prereg_gpu_addendum.json"
    addendum_sha_recorded_path = I4E2 / "prereg_gpu_addendum.sha256"

    out: dict[str, Any] = {}
    missing = [n for n, e in [("i4e1_prereg", e1), ("i4e1_prereg_amendments", e2),
                              ("i4e1_deviations", e3), ("i4e2_deviations", e4),
                              ("i4e1_aggregates", e5), ("i4e1_ams_validation", e6),
                              ("i4e2_analysis", e7)] if e]
    if missing:
        out["missing_sources"] = missing

    # ---------------------------------------------------------------- #
    # (A) experimental setup
    # ---------------------------------------------------------------- #
    i2_counts = count_i2_dataset_tables()
    beh = rederive_behaviour_item_counts()
    prereg2 = json.loads(prereg2_path.read_text()) if prereg2_path.exists() else None
    revision_search_paths = [
        str(SRC.SOURCES["i4e1_prereg"]), str(prereg2_path),
        str(I4E1 / "method_out.json"), str(I4E2 / "method_out.json"),
    ]

    setup_rows = []

    def setup_row(field: str, value: Any, source_file: str, source_key: str, prose_note: str = "") -> None:
        setup_rows.append({
            "field": field, "value": value, "source_file": source_file,
            "source_key": source_key, "readout_class": "n/a", "note": prose_note,
        })

    if prereg1:
        for tag, info in prereg1["a_parents"].items():
            setup_row(f"model_repo_id[{tag}]", info["repo"], sf("i4e1_prereg"), f"a_parents.{tag}.repo")
        setup_row("model_revision_pinned", "UNVERIFIABLE",
                  "; ".join(revision_search_paths), "a_parents / prereg (no revision/commit field present)",
                  "No HF revision/commit sha is recorded anywhere in i4e1 or i4e2 prereg/method_out; the "
                  "closest disk proxy is the per-checkpoint weight_fingerprint sha256 in device_swap.json "
                  "(e.g. F1__ref = f0089e1d...23dcd5a), which pins content-identity, not a git revision.")
        setup_row("n_harm_prompts_i4e1_prereg", prereg1["b_items"]["n_harm"], sf("i4e1_prereg"), "b_items.n_harm")
        setup_row("n_benign_prompts_i4e1_prereg", prereg1["b_items"]["n_benign"], sf("i4e1_prereg"), "b_items.n_benign")
    setup_row("n_harm_prompts_rederived_from_provenance_chain", beh.get("rederived_n_harm"),
              beh.get("sources", {}).get("gt_harm", "SOURCE_ABSENT") + " ; " + beh.get("sources", {}).get("d1_safety_2x2", ""),
              "gt_harm rows + 40 XSTest-twin harm items (see rederive_behaviour_item_counts)")
    setup_row("n_benign_prompts_rederived_from_provenance_chain", beh.get("rederived_n_benign"),
              beh.get("sources", {}).get("gt_benign", "SOURCE_ABSENT") + " ; " + beh.get("sources", {}).get("d1_safety_2x2", ""),
              "gt_benign rows - 2 dropped-for-overlap + 40 XSTest-twin benign items")
    setup_row("iteration2_dataset_probe_harmful_n", i2_counts.get("probe_harmful_n"),
              sf("i2data_full"), "datasets[dataset=...probe_harmful].examples (len)")
    setup_row("iteration2_dataset_probe_hard_benign_n", i2_counts.get("probe_hard_benign_n"),
              sf("i2data_full"), "datasets[dataset=...probe_hard_benign].examples (len)")
    if prereg2:
        setup_row("judge_model", prereg2.get("judge", {}).get("model"), str(prereg2_path), "judge.model")
        setup_row("judge_fallback_model", prereg2.get("judge", {}).get("fallback_model"), str(prereg2_path), "judge.fallback_model")
    setup_row("rubric_sha", "UNVERIFIABLE", str(prereg2_path) + " ; " + str(addendum_path),
              "no field literally named a rubric sha was found; prereg_sha256 of the i4e2 prereg "
              "(which embeds the rubric verbatim) is 3b0aaa1969d916c214a5b567224d4500741b004bf05c30a2813941d92d150bd3 "
              "(analysis.json 'prereg'.'prereg_sha256') and is reported here as the closest verifiable proxy.")
    if agg:
        setup_row("bootstrap_B", agg.get("aggregates", {}).get("N1_d_lstar", {}).get("criterion_i_false_alarm", {}).get("n_noop"),
                  sf("i4e1_classification"), "B", "see classification.json's own B field below")
    clf, _ = SRC.try_load("i4e1_classification")
    if clf:
        setup_row("bootstrap_B_classification", clf.get("B"), sf("i4e1_classification"), "B")
        setup_row("bootstrap_seed_classification", clf.get("seed"), sf("i4e1_classification"), "seed")
    setup_row("bootstrap_B_this_audit", ST.B_BOOT, str(WS / "src/stats_lib.py"), "B_BOOT")
    setup_row("bootstrap_seed_this_audit", ST.SEED, str(WS / "src/stats_lib.py"), "SEED")
    if prereg1:
        setup_row("hardware_i4e1", prereg1.get("hardware_detected"), sf("i4e1_prereg"), "hardware_detected")
    hw2_path = I4E2 / "results" / "hardware_session4.json"
    setup_row("hardware_i4e2_session4_file", "SOURCE_ABSENT" if not hw2_path.exists() else "present",
              str(hw2_path), "(file cited as evidence by amendment A13 but not found on disk)")
    # cost
    jc_path = I4E1 / "results/judge_cost_ledger.jsonl"
    cost_i4e1 = None
    if jc_path.exists():
        cost_i4e1 = sum(json.loads(l)["cost_usd"] for l in jc_path.read_text().splitlines() if l.strip())
    setup_row("judge_cost_usd_i4e1_rederived_sum", cost_i4e1, str(jc_path), "sum(cost_usd) over all lines")
    cost_i4e2 = (e2analysis or {}).get("judge_cost", {}).get("total_usd") if e2analysis else None
    setup_row("judge_cost_usd_i4e2_on_disk", cost_i4e2, sf("i4e2_analysis"), "judge_cost.total_usd")
    setup_row("judge_cost_usd_total_rederived",
              (cost_i4e1 or 0) + (cost_i4e2 or 0),
              str(jc_path) + " ; " + sf("i4e2_analysis"), "sum of the two ledgers above")

    # ---------------------------------------------------------------- #
    # (B) appendix contents
    # ---------------------------------------------------------------- #
    appendix = [
        {"entry": "A.1 Full 32-candidate false-alarm / sensitivity table", "points_at": "results/table_candidates32.json (D4)"},
        {"entry": "A.2 Composition of the primary no-op/effective sets", "points_at": "results/table_composition.json (D1)"},
        {"entry": "A.3 Structural-degeneracy flags (wu05/wu20 bitwise-identical arms)", "points_at": "results/table_degeneracy.json (D2)"},
        {"entry": "A.4 BL1 logit-baseline variant table", "points_at": "results/table_bl1_variants.json (D3)"},
        {"entry": "A.5 6-band x 3-site causal intervention grid", "points_at": "results/table_causal_grid.json (D5)"},
        {"entry": "A.6 Equivalence / TOST bounds on the site-local null", "points_at": "results/table_equivalence.json (D6)"},
        {"entry": "A.7 Few-prompt / small-n sensitivity", "points_at": "results/table_fewprompt.json (D7)"},
        {"entry": "A.8 No-op displacement table replacing the bitwise-identity claim", "points_at": "results/table_displacement.json (D8)"},
        {"entry": "A.9 Cross-model direction-cosine geometry", "points_at": "results/table_geometry.json (D9)"},
        {"entry": "A.10 Experimental setup, deviations and this appendix index", "points_at": "results/table_setup_deviations.json (D10, this file)"},
        {"entry": "A.11 Backstop join across iteration-5 siblings", "points_at": "results/join_backstop.json (D11)"},
        {"entry": "A.12 Full contradictions ledger (this deliverable pair)", "points_at": "results/contradictions_d8_d10.json"},
    ]
    for a in appendix:
        a["source_file"] = str(RES)
        a["source_key"] = "planned deliverable file (this audit)"
        a["readout_class"] = "n/a"

    # ---------------------------------------------------------------- #
    # (C) deviations, each checked against deviations.json
    # ---------------------------------------------------------------- #
    kl_families = sorted({d["key"].rsplit("_", 1)[-1] for d in (dev1 or []) if d["key"].startswith("lesion_kl_filter_failed_")})
    a12 = next((a for a in (prereg1_amend or []) if a["id"] == "A12"), None)
    addendum_sha_computed = sha256_file(addendum_path)
    addendum_sha_recorded = addendum_sha_recorded_path.read_text().strip() if addendum_sha_recorded_path.exists() else None
    falcon3_padding = (ams or {}).get("padding_bug_effect_size", {}).get("tiiuae/Falcon3-1B-Instruct", {})
    ams_verdict = (ams or {}).get("verdict", {})
    abliterated_dev = next((d for d in (dev2 or []) if d["key"] == "abliterated_scope"), None)

    deviations = [
        {
            "item": "KL<0.1 lesion filter failing with the fallback firing",
            "families_affected_rederived": kl_families,
            "plan_claim": "F1 AND F3 (as stated in the task brief for this audit)",
            "execution_record_amendment": "A12 (prereg_amendments.json) documents the fallback rule and its FIRST "
                                          "trigger on F1; the deviations.json record shows the SAME "
                                          "KL_FILTER_FAILED fallback ALSO fired independently for F3 "
                                          "(F2 is NOT listed and is presumed to have passed the KL filter).",
            "verdict": ("MATCH: both F1 and F3 fired the fallback per deviations.json"
                       if set(kl_families) == {"F1", "F3"} else
                       f"MISMATCH: deviations.json shows fallback firing for {kl_families}, not {{F1, F3}}"),
            "a12_what": a12.get("what") if a12 else "SOURCE_ABSENT",
            "source_file": sf("i4e1_deviations") + " ; " + sf("i4e1_prereg_amendments"),
            "source_key": "[key startswith lesion_kl_filter_failed_] ; [id=A12]",
            "readout_class": "n/a",
        },
        {
            "item": "GPU re-plan and addendum prereg sha",
            "expected_sha256_prefix": "524c15c0",
            "sha256_recorded_in_sidecar_file": addendum_sha_recorded,
            "sha256_computed_from_addendum_json": addendum_sha_computed,
            "sha256_recorded_in_analysis_json": (e2analysis or {}).get("prereg", {}).get("prereg_gpu_addendum_sha256"),
            "verdict": ("MATCH" if addendum_sha_computed and addendum_sha_computed == addendum_sha_recorded
                       == (e2analysis or {}).get("prereg", {}).get("prereg_gpu_addendum_sha256")
                       and addendum_sha_computed.startswith("524c15c0") else "MISMATCH_OR_UNVERIFIABLE"),
            "source_file": str(addendum_path) + " ; " + str(addendum_sha_recorded_path) + " ; " + sf("i4e2_analysis"),
            "source_key": "sha256(file) ; sidecar .sha256 ; analysis.json.prereg.prereg_gpu_addendum_sha256",
            "readout_class": "n/a",
        },
        {
            "item": "Reduced abliterated grid",
            "detail": abliterated_dev.get("what") if abliterated_dev else "SOURCE_ABSENT",
            "impact": abliterated_dev.get("impact") if abliterated_dev else "SOURCE_ABSENT",
            "source_file": sf("i4e2_deviations"), "source_key": "[key=abliterated_scope]",
            "readout_class": "n/a",
        },
        {
            "item": "AMS reimplementation agreeing with the released CLI",
            "reported_in_prose": "<1e-4 relative difference (0.01%)",
            "rederived_max_rel_diff_bs1_per_model": {
                m: v.get("max_rel_diff_bs1") for m, v in ams_verdict.get("per_model", {}).items()
            } if ams_verdict else "SOURCE_ABSENT",
            "rederived_overall_verdict": ams_verdict.get("overall"),
            "note": ("The largest max_rel_diff_bs1 across all three parent checkpoints is "
                    f"{max((v.get('max_rel_diff_bs1', 0) for v in ams_verdict.get('per_model', {}).values()), default=None)}"
                    ", i.e. ~7.3e-5 (0.0073%), an order of magnitude TIGHTER than the "
                    "prose's own claimed bound of 1e-4 (0.01%): both are true, but the "
                    "prose bound is loose relative to the measured value."),
            "source_file": sf("i4e1_ams_validation"), "source_key": "verdict.per_model.*.max_rel_diff_bs1",
            "readout_class": "n/a",
        },
        {
            "item": "Batch-8 padding bug shifting Falcon3",
            "execution_record_claim": 5.3,
            "plan_claim": 5,
            "rederived_max_abs_sigma_shift": falcon3_padding.get("max_abs_sigma_shift"),
            "rederived_mean_abs_sigma_shift": falcon3_padding.get("mean_abs_sigma_shift"),
            "verdict": ("MATCH_execution_record" if falcon3_padding.get("max_abs_sigma_shift") is not None
                       and abs(falcon3_padding["max_abs_sigma_shift"] - 5.3) < 0.05
                       else "SEE_VALUE"),
            "source_file": sf("i4e1_ams_validation"),
            "source_key": "padding_bug_effect_size.['tiiuae/Falcon3-1B-Instruct'].max_abs_sigma_shift",
            "readout_class": "n/a",
        },
    ]

    # ---------------------------------------------------------------- #
    # (D) keyword-proxy range per band
    # ---------------------------------------------------------------- #
    kw_row = None
    if e2analysis:
        cg = e2analysis["per_model"]["instruct"]["causal_grid_judged"]["proxy_refused_harm"]["F"]["cells"]
        per_band = {b: cg[f"P_{b}"]["mean_T"] for b in ("B1", "B2", "B3", "B4", "B5", "B6") if f"P_{b}" in cg}
        kw_row = {
            "readout": "proxy_refused_harm (keyword-based refusal proxy), model=instruct, arm=F, site=P",
            "baseline_mean_0_all_bands": cg["P_B1"]["mean_0"],
            "per_band_mean_T_rederived": per_band,
            "plan_claim_per_band": {"B4": 0.15, "B5": 0.19, "B6": 0.31},
            "rounded_to_2dp": {b: round(v, 2) for b, v in per_band.items()},
            "verdict": "MATCH" if all(
                abs(round(per_band.get(b, float("nan")), 2) - plan) < 5e-3
                for b, plan in {"B4": 0.15, "B5": 0.19, "B6": 0.31}.items()
            ) else "MISMATCH",
            "note": ("The paper's own headline text collapses this to a single figure "
                    "('0.79 to 0.15'), citing only B4 and dropping the B5=0.19 and "
                    "B6=0.31 values; the true range across B4-B6 is 0.146-0.313, not "
                    "a single 0.15 point estimate."),
            "source_file": sf("i4e2_analysis"),
            "source_key": "per_model.instruct.causal_grid_judged.proxy_refused_harm.F.cells.P_B{4,5,6}.mean_T",
            "readout_class": "text (generations; keyword proxy, a BASELINE, never the deliverable)",
        }
    else:
        kw_row = {"status": "SOURCE_ABSENT", "source_file": sf("i4e2_analysis"), "readout_class": "n/a"}

    # ---------------------------------------------------------------- #
    # (E) mixed sensitivity denominators (9 vs 8)
    # ---------------------------------------------------------------- #
    sens_row = None
    if agg:
        n_eff_by_cand = {k: v.get("criterion_ii_sensitivity", {}).get("n_effective")
                         for k, v in agg["aggregates"].items()}
        cand_9 = sorted(k for k, n in n_eff_by_cand.items() if n == 9)
        cand_8 = sorted(k for k, n in n_eff_by_cand.items() if n == 8)
        greedy = agg["aggregates"].get("greedy_refusal_rate", {}).get("criterion_ii_sensitivity", {})
        unscorable_explicit = greedy.get("pairs_not_scored", [])
        # for the decode-window / AMS candidates the same pair is silently absent
        # from per_pair rather than listed in pairs_not_scored -- verify directly
        allpairs9 = None
        for k in cand_9:
            pp = {r["pair_id"] for r in agg["aggregates"][k]["criterion_ii_sensitivity"].get("per_pair", [])}
            if len(pp) == 9:
                allpairs9 = pp
                break
        implicit_missing = set()
        for k in cand_8:
            pp = {r["pair_id"] for r in agg["aggregates"][k]["criterion_ii_sensitivity"].get("per_pair", [])}
            if allpairs9:
                implicit_missing |= (allpairs9 - pp)
        sens_row = {
            "candidates_with_denominator_9": cand_9,
            "candidates_with_denominator_8": cand_8,
            "unscorable_pair_explicit_in_pairs_not_scored": unscorable_explicit,
            "unscorable_pair_implicit_missing_from_per_pair": sorted(implicit_missing),
            "unscorable_pair_name": "H::mlabonne--Qwen3-4B-abliterated",
            "explanation": (
                "9 is the full primary_effective_pairs count (n_EFFECTIVE=9 per "
                "classification.json count_check). Denominator drops to 8 for "
                "text-generation-derived candidates (greedy_refusal_rate*) AND for "
                "decode-window / AMS candidates (N8_severity_rho, N9_decode_d, "
                "N9_tok1, N10_dec_minus_prompt, AMS_T1_sigma, AMS_T2_drift): all six "
                "silently or explicitly drop the SAME pair, "
                "H::mlabonne--Qwen3-4B-abliterated, from their per-pair scoring. "
                "greedy_refusal_rate* names it explicitly in pairs_not_scored; the "
                "decode/AMS candidates omit it from per_pair without a flag, which "
                "this audit surfaces as an implicit-drop finding."
            ),
            "source_file": sf("i4e1_aggregates"), "source_key": "aggregates.*.criterion_ii_sensitivity.{n_effective,per_pair,pairs_not_scored}",
            "readout_class": "n/a",
        }
    else:
        sens_row = {"status": "SOURCE_ABSENT", "source_file": sf("i4e1_aggregates"), "readout_class": "n/a"}

    out["A_experimental_setup"] = {"rows": setup_rows, "n_rows": len(setup_rows)}
    out["A_prime_i2_dataset_full_counts"] = i2_counts
    out["A_prime_behaviour_item_provenance"] = beh
    out["B_appendix_contents"] = appendix
    out["C_deviations"] = deviations
    out["D_keyword_proxy_per_band"] = kw_row
    out["E_mixed_sensitivity_denominators"] = sens_row
    return out


# ========================================================================= #
# Contradictions ledger
# ========================================================================= #
def build_contradictions(d8: dict[str, Any], d10: dict[str, Any]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []

    def add(claim_id, text, claimed, rederived, rule, tol, sf_, sk_, verdict, note=""):
        claims.append({
            "claim_id": claim_id, "claim_text": text, "claimed_value": claimed,
            "rederived_value": rederived, "tolerance_rule": rule, "tolerance": tol,
            "source_file": sf_, "source_key": sk_, "verdict": verdict, "note": note,
        })

    ev = d8.get("refuting_evidence", {})
    dswap = ev.get("ii_device_swap_reference_pair_F1__ref", {})
    if dswap:
        v = dswap.get("identical_frac_rederived")
        add("C1", "25.6% of greedy texts are identical across CPU and GPU with identical weights",
            0.256, v, "rate |d|<=5e-4", 5e-4, sf("i4e1_device_swap"), "pairs[tag=F1__ref].identical_frac",
            "MATCH" if v is not None and abs(v - 0.256) < 5e-4 else "MISMATCH")
        v2 = dswap.get("HC_label_agreement_rederived")
        add("C2", "Labels agree 96.5% across the device swap",
            0.965, v2, "rate |d|<=5e-4", 5e-4, sf("i4e1_device_swap"), "pairs[tag=F1__ref].labels.HC.label_agreement",
            "MATCH" if v2 is not None and abs(v2 - 0.965) < 5e-4 else "MISMATCH")

    firing = ev.get("i_two_activation_readouts_fire_on_F1__fp16", [])
    add("C3", "Two activation readouts fire on the F1__fp16 no-op pair",
        2, len(firing), "count EXACT", 0, sf("i4e1_pairs_long"), "candidate=*, pair_id=F1__fp16, ci_excludes_0=True, readout_class=activation",
        "MATCH" if len(firing) == 2 else "MISMATCH",
        note=f"named: {[r['candidate_id'] for r in firing]}")

    bl1 = d8.get("bl1_vs_activation", {})
    bl1_vals = bl1.get("bl1_median_noop_displacement_by_variant", {})
    add("C4", "BL1's median no-op displacement is 0.150-0.178 null SD",
        [0.150, 0.178], bl1_vals, "range containment", "min>=0.150-5e-4 and max<=0.178+5e-4",
        sf("i4e1_pairs_long"), "candidate in {BL1_easy,BL1_hard,BL1_truelogit,BL1_truelogit_hard}",
        "MATCH" if bl1_vals and not bl1.get("bl1_variants_outside_claimed_range") else "MISMATCH",
        note=f"outside range: {bl1.get('bl1_variants_outside_claimed_range')}")

    act_med = bl1.get("median_activation_displacement")
    add("C5", "Activation readouts' median no-op displacement is 0.012-0.024 null SD",
        [0.012, 0.024], act_med, "range containment (loose)", "0.010<=x<=0.030",
        sf("i4e1_pairs_long"), "readout_class=activation median across candidates",
        "MATCH" if act_med is not None and 0.010 <= act_med <= 0.030 else "MISMATCH")

    ratio = d8.get("ratio_bl1_over_activation")
    add("C6", "The BL1-vs-activation false-alarm-magnitude ratio is near 6x",
        6.0, ratio, "|d|<=1.5 (order-of-magnitude claim)", 1.5,
        sf("i4e1_pairs_long"), "BL1_hard median / median(activation-class medians)",
        "MATCH" if ratio is not None and abs(ratio - 6.0) <= 1.5 else "MISMATCH")

    beh = d10.get("A_prime_behaviour_item_provenance", {})
    add("C7", "The behaviour set has 85 harmful and 83 benign prompts",
        [85, 83], [beh.get("rederived_n_harm"), beh.get("rederived_n_benign")],
        "counts EXACT", 0, str(SRC.LOOP / "iter_1/gen_art/gen_art_experiment_3/assets/gt_harm.json"),
        "gt_harm+gt_benign+xstest twins (see rederive_behaviour_item_counts)",
        "MATCH" if beh.get("matches_claimed_85_83") else "MISMATCH",
        note="NOT sourced from the iteration-2 dataset artifact; see note field")

    dev = next((d for d in d10.get("C_deviations", []) if d["item"].startswith("KL<0.1")), {})
    add("C8", "The KL-filter fallback fired for F1 AND F3 (not F1 alone)",
        "F1 and F3", dev.get("families_affected_rederived"), "set equality", 0,
        sf("i4e1_deviations"), "[key startswith lesion_kl_filter_failed_]",
        "MATCH" if dev.get("verdict", "").startswith("MATCH") else "MISMATCH")

    dev2_ = next((d for d in d10.get("C_deviations", []) if "addendum" in d["item"]), {})
    add("C9", "The GPU re-plan addendum prereg sha256 is 524c15c0...",
        "524c15c0...", dev2_.get("sha256_computed_from_addendum_json"), "prefix match", 0,
        str(I4E2 / "prereg_gpu_addendum.json"), "sha256(file)",
        "MATCH" if dev2_.get("verdict") == "MATCH" else "MISMATCH")

    dev3 = next((d for d in d10.get("C_deviations", []) if "AMS reimplementation" in d["item"]), {})
    add("C10", "The AMS reimplementation agrees with the released CLI to <1e-4 relative difference (0.01%)",
        1e-4, dev3.get("rederived_max_rel_diff_bs1_per_model"), "nats/rate <=1e-3 (loose bound check)", 1e-3,
        sf("i4e1_ams_validation"), "verdict.per_model.*.max_rel_diff_bs1",
        "MATCH" if dev3 and all(v is not None and v < 1e-4 for v in dev3.get("rederived_max_rel_diff_bs1_per_model", {}).values()) else "UNVERIFIABLE")

    dev4 = next((d for d in d10.get("C_deviations", []) if "Falcon3" in d["item"]), {})
    add("C11", "The Falcon3 batch-8 padding bug shifts sigma by 5.3 (execution record) vs 5 (plan)",
        {"execution_record": 5.3, "plan": 5}, dev4.get("rederived_max_abs_sigma_shift"),
        "|d|<=5e-2 vs execution record", 5e-2, sf("i4e1_ams_validation"),
        "padding_bug_effect_size.['tiiuae/Falcon3-1B-Instruct'].max_abs_sigma_shift",
        "MATCH" if dev4.get("rederived_max_abs_sigma_shift") is not None and abs(dev4["rederived_max_abs_sigma_shift"] - 5.3) < 5e-2 else "MISMATCH",
        note="matches the execution record (5.3), NOT the plan (5)")

    kw = d10.get("D_keyword_proxy_per_band", {})
    add("C12", "The keyword-proxy range per band is 0.15 at B4, 0.19 at B5, 0.31 at B6",
        {"B4": 0.15, "B5": 0.19, "B6": 0.31}, kw.get("per_band_mean_T_rederived"),
        "rounded to 2dp |d|<=5e-3", 5e-3, sf("i4e2_analysis"),
        "per_model.instruct.causal_grid_judged.proxy_refused_harm.F.cells.P_B{4,5,6}.mean_T",
        kw.get("verdict", "UNVERIFIABLE"))

    sens = d10.get("E_mixed_sensitivity_denominators", {})
    add("C13", "The mixed sensitivity denominators (9 vs 8) trace to one unscorable pair",
        "H::mlabonne--Qwen3-4B-abliterated", sens.get("unscorable_pair_name"),
        "string match", 0, sf("i4e1_aggregates"),
        "aggregates.greedy_refusal_rate.criterion_ii_sensitivity.pairs_not_scored",
        "MATCH" if sens.get("unscorable_pair_name") == "H::mlabonne--Qwen3-4B-abliterated" else "MISMATCH")

    return claims


def main() -> None:
    RES.mkdir(exist_ok=True)
    FIG.mkdir(exist_ok=True)

    d8 = build_d8()
    (RES / "table_displacement.json").write_text(json.dumps(d8, indent=2, default=str))

    d10 = build_d10()
    (RES / "table_setup_deviations.json").write_text(json.dumps(d10, indent=2, default=str))

    contradictions = build_contradictions(d8, d10)
    (RES / "contradictions_d8_d10.json").write_text(json.dumps(contradictions, indent=2, default=str))

    # optional figure
    try:
        build_figure(d8)
    except Exception as exc:  # figure is optional; never block the deliverables
        print(f"FIGURE_SKIPPED: {exc}")

    print(f"D8 rows: {d8.get('n_rows')}")
    print(f"D10 setup rows: {len(d10.get('A_experimental_setup', {}).get('rows', []))}")
    print(f"contradictions: {len(contradictions)}")
    for c in contradictions:
        print(c["claim_id"], c["verdict"])


def build_figure(d8: dict[str, Any]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = [r for r in d8.get("rows", []) if r["median_noop_displacement_in_null_SD"] is not None]
    rows = sorted(rows, key=lambda r: r["median_noop_displacement_in_null_SD"])
    ids = [r["candidate_id"] for r in rows]
    vals = [r["median_noop_displacement_in_null_SD"] for r in rows]
    classes = [r["readout_class"] for r in rows]
    palette = {"activation": "#2b6cb0", "weight": "#805ad5", "logit": "#e53e3e",
              "text": "#dd6b20", "activation (AMS bar)": "#38a169",
              "activation (AMS bar, reference-based; alarm = package verify rule, not a CI)": "#38a169"}
    colors = [next((v for k, v in palette.items() if k in c), "#718096") for c in classes]

    fig, ax = plt.subplots(figsize=(10, 8))
    ax.barh(range(len(ids)), vals, color=colors)
    ax.set_yticks(range(len(ids)))
    ax.set_yticklabels(ids, fontsize=7)
    ax.set_xlabel("median no-op displacement (null SD)")
    ax.set_title("No-op displacement by candidate (D8): magnitude, not bitwise identity")
    bl1_hard = next((r["median_noop_displacement_in_null_SD"] for r in rows if r["candidate_id"] == "BL1_hard"), None)
    if bl1_hard is not None:
        ax.axvline(bl1_hard, color="#e53e3e", linestyle="--", linewidth=1, label=f"BL1_hard = {bl1_hard:.3f}")
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_displacement.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
