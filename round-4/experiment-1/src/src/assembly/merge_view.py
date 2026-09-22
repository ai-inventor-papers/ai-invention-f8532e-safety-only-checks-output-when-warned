"""FINAL-ASSEMBLY helper (method.py only): in-memory equivalents of src/truth_classify.py's merge(),
plus pairs_long.json normalisation to canonical prereg candidate names (prereg amendment A13).

merge() is NEVER called or imported for its side effects here: this module re-derives the same union
purely by reading the already-committed results/{classification,graded_truth}_s*.json stage files (and
results/classification.json / results/graded_truth.json only when that merged file is newer than every
stage file), so method.py stays runnable on partial data without racing a live truth_classify.py process.

Only src/truth_classify.py's pure `all_pairs()` helper is imported (read-only; not run as __main__), to
get the exact canonical pair set (prereg c_pairs + every amendment's added_pairs/hg_pairs) for the
'not_run' list, matching merge()'s own computation.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import RESULTS, jload, utc_now  # noqa: E402
from truth_classify import all_pairs as _all_pairs  # noqa: E402  (read-only import; module has no import-time side effects)

# ---------------------------------------------------------------------------------------------- canonical names
# short pairs_long candidate -> canonical prereg e_candidates name (required change 1). Everything not
# listed here keeps its short name (it already matches the canonical / prereg-bar name).
CANON = {
    "N1": "N1_d_lstar",
    "N2": "N2_d_lstar_perpWU",
    "N3": "N3_F_clust_perpWU",
    "N4_onset": "N4_shape_onset",
    "N4_peak_frac": "N4_shape_peak_frac",
    "N4_width": "N4_shape_width",
    "N6": "N6_benign_sep",
    "N7": "N7_two_sided_gap",
    "N8": "N8_severity_rho",
    "N9": "N9_decode_d",
    "N10": "N10_dec_minus_prompt",
    "N11": "N11_ams_window_fisher",
    "N12_DEFAULT_WEIGHTS": "N12_combo_DEFAULT_WEIGHTS",
}
N4_COMPONENTS = {"N4_shape_onset", "N4_shape_peak_frac", "N4_shape_width"}


def canon(short: str) -> str:
    return CANON.get(short, short)


def _fnum(x):
    try:
        v = float(x)
        return None if (math.isnan(v) or math.isinf(v)) else v
    except (TypeError, ValueError):
        return None


def _sgn(x) -> int:
    v = _fnum(x)
    return 0 if v is None or v == 0 else (1 if v > 0 else -1)


def normalize_row(r: dict, prereg: dict) -> dict:
    """One pairs_long.json row -> canonical-name row with signed units and the AMS_T2_drift
    ci_excludes_0 override (required changes 1-2)."""
    exp_hc = prereg["e_expected_sign_vs_HC"]
    short = r.get("candidate")
    c = canon(short)
    if c in N4_COMPONENTS:
        esign = 0
    elif c in exp_hc:
        esign = exp_hc[c]
    else:
        esign = r.get("expected_sign")  # fallback: the row's own expected sign (pairs.py EXPECTED_SIGN_VS_HC)
    delta = _fnum(r.get("Delta"))
    a_par = _fnum(r.get("abs_delta_over_nullSD_parent"))
    a_chi = _fnum(r.get("abs_delta_over_nullSD_child"))
    ci_lo, ci_hi = r.get("ci_lo"), r.get("ci_hi")
    ci_excl_raw = r.get("ci_excludes_0")
    ci_excl = ci_excl_raw
    note = r.get("note")
    if c == "AMS_T2_drift":
        # required change 2: AMS_T2_drift has no bootstrap CI; its alarm is the AMS package's own
        # Tier-2 verify rule -- ci_excludes_0 is SET TO ams_alarm and the override is documented here
        # (also in method_out metadata['decision_rules']).
        ci_excl = r.get("ams_alarm")
        add = "ci_excludes_0 OVERRIDDEN to ams_alarm (package verify rule: fails iff any concept's direction similarity < 0.8 or drift > 0.2 vs the parent baseline); this candidate carries no bootstrap CI"
        note = f"{note}; {add}" if note else add
    return {
        "candidate": c, "candidate_raw": short, "pair_id": r.get("pair_id"),
        "delta": delta, "ci_lo": ci_lo, "ci_hi": ci_hi,
        "ci_excludes_0": ci_excl, "ci_excludes_0_raw": ci_excl_raw,
        "se_boot": r.get("se_boot"), "mde": r.get("mde"),
        "abs_delta_over_nullsd_parent": a_par, "abs_delta_over_nullsd_child": a_chi,
        "signed_units_parent": (_sgn(delta) * a_par) if (delta is not None and a_par is not None) else None,
        "observed_sign": r.get("observed_sign"), "expected_sign_vs_HC": esign,
        "parent_value": r.get("parent_value"), "child_value": r.get("child_value"),
        "n_valid_draws": r.get("n_valid_draws"), "note": note,
        "ams_verified": r.get("ams_verified"), "ams_alarm": r.get("ams_alarm"),
        "ams_mean_direction_similarity": r.get("ams_mean_direction_similarity"),
    }


# ---------------------------------------------------------------------------------------------- staged-file union
def _stage_files(kind: str) -> list[Path]:
    return sorted(RESULTS.glob(f"{kind}_s*.json"), key=lambda q: int(q.stem.split("_s")[-1]))


def _hfam(tag: str) -> str:
    """Verbatim copy of truth_classify._hfam (family-name fallback for harvested checkpoints)."""
    t = tag.lower()
    for k, f in (("qwen3", "qwen3"), ("qwen2.5", "qwen2.5"), ("llama-3.2", "llama3.2"), ("olmo", "amd-olmo"),
                 ("granite", "granite"), ("falcon3", "falcon3")):
        if k in t:
            return f
    return t.split("--")[0]


def build_classification_view(prereg: dict) -> dict:
    """Union of every committed results/classification_s*.json (truth_classify.merge()'s pairs / union /
    count-check logic, replicated in memory -- merge() itself is never called). Uses results/classification.json
    only if it exists AND is newer than every classification_s*.json (per the task's instructions)."""
    merged_path = RESULTS / "classification.json"
    s_files = _stage_files("classification")
    if merged_path.exists() and (not s_files or merged_path.stat().st_mtime >= max(f.stat().st_mtime for f in s_files)):
        doc = jload(merged_path)
        doc["source"] = "results/classification.json (newer than every classification_s*.json)"
        return doc
    rows: list[dict] = []
    seen: set[str] = set()
    stages = []
    for f in s_files:
        d = jload(f)
        stages.append({"file": f.name, "stage": d.get("stage"), "utc": d.get("utc")})
        for r in d["pairs"]:
            # merge()'s exact rule: a later-stage row replaces an earlier one UNLESS the later row is
            # itself UNSCORED/None and something is already recorded for this pair_id.
            if r["pair_id"] in seen and r.get("observed_class") in (None, "UNSCORED"):
                continue
            rows = [x for x in rows if x["pair_id"] != r["pair_id"]] + [dict(r, stage=d.get("stage"))]
            seen.add(r["pair_id"])
    prim_noop = [r for r in rows if r["kind"] == "constructed" and r["intended_stratum"] in ("NOOP", "EFFECTIVE_LESION")
                 and r.get("observed_class") == "NOOP"]
    hg_children = {r["child"].replace("HG__", "") for r in rows if r["kind"] == "harvested_regen"
                   and r.get("observed_class") not in (None, "UNSCORED")}
    prim_eff = [r for r in rows if r.get("observed_class") == "EFFECTIVE" and (
        (r["kind"] == "constructed" and r["intended_stratum"] in ("NOOP", "EFFECTIVE_LESION")) or
        (r["kind"] == "harvested_regen" and r["intended_stratum"] in ("EFFECTIVE_HARVESTED", "SENSITIVITY_AMD")) or
        (r["kind"] == "harvested" and r["intended_stratum"] in ("EFFECTIVE_HARVESTED", "SENSITIVITY_AMD")
         and r["child"] not in hg_children))]
    fam_eff = sorted({(r.get("family") or _hfam(r["child"])) for r in prim_eff})
    count = {"n_NOOP_nontrivial": len(prim_noop), "families_NOOP": sorted({r["family"] for r in prim_noop}),
             "n_EFFECTIVE": len(prim_eff), "families_EFFECTIVE": fam_eff,
             "noop_ok": len(prim_noop) >= 8 and len({r["family"] for r in prim_noop}) >= 3,
             "effective_ok": len(prim_eff) >= 8 and len(fam_eff) >= 3}
    count["status"] = "OK" if count["noop_ok"] and count["effective_ok"] else "UNDERPOWERED"
    have_ids = {r["pair_id"] for r in rows}
    return {"utc": utc_now(), "stages_used": stages, "pairs": rows,
            "primary_noop_pairs": [r["pair_id"] for r in prim_noop],
            "primary_effective_pairs": [r["pair_id"] for r in prim_eff], "count_check": count,
            "not_run": [p["pair_id"] for p in _all_pairs(prereg) if p["pair_id"].replace("int8dyn", "int8wo") not in have_ids],
            "source": "in-memory union of classification_s*.json (merge() not called)"}


def _ledger_usd() -> float:
    p = RESULTS / "judge_cost_ledger.jsonl"
    if not p.exists():
        return 0.0
    tot = 0.0
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            tot += float(json.loads(line).get("cost_usd") or 0)
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
            continue
    return tot


def build_graded_truth_view() -> dict:
    """Union of every committed results/graded_truth_s*.json (truth_classify.merge()'s per_ckpt union,
    replicated in memory). Uses results/graded_truth.json only if newer than every stage file."""
    merged_path = RESULTS / "graded_truth.json"
    s_files = _stage_files("graded_truth")
    if merged_path.exists() and (not s_files or merged_path.stat().st_mtime >= max(f.stat().st_mtime for f in s_files)):
        doc = jload(merged_path)
        doc["source"] = "results/graded_truth.json (newer than every graded_truth_s*.json)"
        return doc
    per: dict = {}
    stages = []
    for f in s_files:
        d = jload(f)
        per.update(d["per_ckpt"])
        stages.append({"file": f.name, "utc": d.get("utc")})
    return {"utc": utc_now(), "stages": stages, "ledger_usd": _ledger_usd(), "per_ckpt": per,
            "source": "in-memory union of graded_truth_s*.json (merge() not called)"}
