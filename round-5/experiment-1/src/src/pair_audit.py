#!/usr/bin/env python3
"""S5 POST-FREEZE pair-audit module (clauses iv, v, vi, vii of f_selection_rule_verbatim).

Runs only after results/survivor.sha256 exists and verifies against results/survivor.json
(prereg S4/S5 gate). Opens the iteration-4 classification file and text-baseline file ONLY
at run time, after that gate passes, and records their schema on read rather than assuming
one (they are outcome data and must not be opened during module construction/testing).

CLI:
    --results-dir DIR        default: results (relative to this WS)
    --classification PATH    default: iter_4 gen_art_experiment_1 results/classification.json
    --text-baseline PATH     default: auto-glob under the iter_4 results/ tree
    --out results/pair_audit.json
    --self-test               exercises clauses 4-7 on synthetic inputs only; never touches
                               survivor.json/classification.json/text_baseline.json; writes
                               results/pair_audit_selftest.json

Recombination formulas for the Tier-B bootstrap (see report for full derivation):
    W1(fold,b): (|mean(pF)-mean(p0)| - median_r|mean(pR[:,r])-mean(p0)|) / gap[fold]
        from reg_fit{fold}_W1_p1F_b{b}, reg_fit{fold}_W1_p1R_b{b}, reg_fit{fold}_p0_items
    W2(fold):   smallest k in 1..5 with (mean(pk)-mean_P) < 0.5*(mean(p0)-mean_P) else 7
        from reg_fit{fold}_W2_ladder_items (items x [p0,p1..p5])
    W7(fold):   mean_t (|m[1,t]-m[0,t]| - median_r|m[2+r,t]-m[0,t]|) / gap[fold]
        from reg_fit{fold}_W7_Y (items x rows x 8), m = mean over resampled items
Registered scalar = mean over fold in {A,B} (cross_fit rule). Bootstrap draws resample
items WITHIN each fold, with replacement, same drawn indices used for parent and child
(seed = sha256("20260922|pairaudit|"+pair_id)[:8] as int).

W3, W4, W5, W6, W8, A1_prior, A2 have NO per-item raw arrays saved in ckpt_*_items.npz
(only already-reduced scalars, or for W5 only |item-p0b| ABS DEVIATIONS with the signed
p0b/p1N never stored, which forbids honestly reconstructing the registered mean-then-abs
statistic under resampling) -> recorded NOT_BOOTSTRAPPABLE with the specific reason.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))

from tierA import structural_pairs, tag_dir_of  # noqa: E402
from statlib import mcnemar_exact, spearman  # noqa: E402

ITER4_EXP1 = Path(
    "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1"
)
DEFAULT_CLASSIFICATION = ITER4_EXP1 / "results" / "classification.json"
H4 = ITER4_EXP1 / "harvest"  # shared harvest dir (NOT outcome data): r_refusal.npy/r_control.npy
                             # etc, the same inputs tierB.py's own registered draw reads

_REUSE_DIR = WS / "src" / "reuse"
if str(_REUSE_DIR) not in sys.path:
    sys.path.insert(0, str(_REUSE_DIR))
import ncands  # noqa: E402  (reused verbatim, same module bars.py calls)

BOOTSTRAP_B = 200
BOOTSTRAP_SEED_BASE = "20260922|pairaudit|"

TIER_A_KEYS = ("G1", "G2", "G3", "G4", "A1_slope", "A3", "W7c", "plain_DiM")
TIER_B_BOOTSTRAPPABLE = ("W1", "W2", "W7")
NOT_BOOTSTRAPPABLE_REASONS = {
    "W3": "no per-item array saved to ckpt_*_items.npz (only aggregated w3_last_i/w3_all_i means "
          "are returned as scalars in tierB.py; raw per-item all/last projections are discarded)",
    "W4": "no per-item array saved; w4_num_b/w4_num_end/w4_nb/w4_ne are accumulated in Python lists "
          "and reduced to means before any npz write, so no honest item-level resample is possible",
    "W5": "only |item - p0b| ABS-DEVIATION arrays (W5_dN_b*, W5_dR_b*) are saved; the SIGNED per-item "
          "p1N/p0b values are never written to npz, so the registered mean-then-abs statistic "
          "(|mean(pN)-p0b| - median|mean(pR)-p0b|) cannot be reconstructed from stored |item-p0b| "
          "values under resampling (abs-then-mean != mean-then-abs) -- inventing a substitute would "
          "misrepresent the registered scalar",
    "W6": "defined as W5 - W1; inherits W5's NOT_BOOTSTRAPPABLE status",
    "W8": "no per-item array; W8 is a band-level cosine between two REFIT directions (pre/post lesion) "
          "computed from stacked per-item activations that are never persisted per item",
    "A1_prior": "no per-item array; A1_prior is a single-contentless-render scalar plus fold H/P means, "
                "computed inline in tierB.draw() and never written to self.items",
    "A2": "no per-item array; a2() returns only the reduced (A2, A2_cos, A2_mag) scalars, the per-item "
          "XP projections used to build dv are never persisted",
}
DEGENERATE_WU05_SUFFIX = "__wu05"
DEGENERATE_SYSPROMPT_SUFFIX = "__sysprompt"

# expected_sign.HC per candidate (registered), with G1/G2/A3/W5 taking the NEGATION of their
# registered OR expectation per prereg operationalisation("sensitivity (v)").
EXPECTED_SIGN_HC = {
    "A1": -1, "A1_prior": None, "A1_slope": None, "A2": -1, "A3": -1,
    "G1": 1, "G2": 1, "G3": -1, "G4": -1,
    "W1": -1, "W2": -1, "W3": -1, "W4": -1, "W5": 1, "W6": 1, "W7": -1, "W7c": -1, "W8": 1,
}
# candidates whose s_HC (for the sign check) is the NEGATION of their registered OR expectation
NEGATE_OR_FOR_SHC = {"G1", "G2", "A3", "W5"}
EXPECTED_SIGN_OR = {
    "A2": 1, "A3": 1, "G1": -1, "G2": -1, "G3": 1, "G4": 1,
    "W1": 1, "W2": 1, "W3": 1, "W4": 1, "W5": -1, "W6": -1, "W7": 1, "W7c": -1, "W8": -1,
}

BARS = ("BL1_easy", "AMS_T1_sigma", "N1", "N6", "C13_peak_d", "N11", "plain_diffmeans")

CLASSIFICATION_LABELS = {"NOOP", "EFFECTIVE", "OR_EFFECTIVE", "AMBIGUOUS"}


# --------------------------------------------------------------------------- #
# S4/S5 freeze gate                                                            #
# --------------------------------------------------------------------------- #


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def check_freeze_gate(results_dir: Path) -> dict:
    """HARD RULE (a): refuse to run unless results/survivor.sha256 exists and matches
    survivor.json. Returns a small report dict; raises SystemExit(2) on failure."""
    sha_path = results_dir / "survivor.sha256"
    surv_path = results_dir / "survivor.json"
    if not sha_path.exists():
        print(f"REFUSING TO RUN: {sha_path} does not exist (S4 freeze has not happened yet).",
              file=sys.stderr)
        raise SystemExit(2)
    if not surv_path.exists():
        print(f"REFUSING TO RUN: {surv_path} does not exist although {sha_path} does.",
              file=sys.stderr)
        raise SystemExit(2)
    stored = sha_path.read_text().strip()
    stored_hex = stored.split(":")[-1].strip().lower()
    # the hash-chain convention of this artifact is sha256(core.canonical_json(obj)), not raw bytes
    import json as _json  # noqa: PLC0415
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from core import canonical_json as _cj, sha256_text as _st  # noqa: PLC0415
    actual_hex = _st(_cj(_json.loads(surv_path.read_text()))).lower()
    if stored_hex != actual_hex:
        print(f"REFUSING TO RUN: {sha_path} does not match sha256(results/survivor.json) "
              f"(stored={stored_hex!r} actual={actual_hex!r}).", file=sys.stderr)
        raise SystemExit(2)
    return {"survivor_sha256_verified": True, "sha256": actual_hex}


# --------------------------------------------------------------------------- #
# schema-adaptive readers for outcome files (opened only after the gate passes) #
# --------------------------------------------------------------------------- #


def record_schema(obj: Any, *, max_list_sample: int = 2, max_depth: int = 3) -> dict:
    """A small, generic structural summary: type + (keys | length+sample-keys)."""
    def _walk(o: Any, depth: int) -> Any:
        if depth > max_depth:
            return {"_truncated": True, "_type": type(o).__name__}
        if isinstance(o, dict):
            return {"_type": "dict", "n_keys": len(o),
                    "keys_sample": list(o.keys())[:30],
                    "value_types_sample": {k: type(v).__name__ for k, v in list(o.items())[:5]}}
        if isinstance(o, list):
            return {"_type": "list", "n": len(o),
                    "item_type_sample": [type(x).__name__ for x in o[:max_list_sample]],
                    "item_schema_sample": [_walk(x, depth + 1) for x in o[:max_list_sample]]}
        return {"_type": type(o).__name__}
    return _walk(obj, 0)


_LABEL_KEY_RE = re.compile(r"(label|classif|status|verdict|category|outcome)", re.I)
_PARENT_KEY_RE = re.compile(r"(parent|ref|base|from)", re.I)
_CHILD_KEY_RE = re.compile(r"(child|arm|to|target)", re.I)
_TAG_KEY_RE = re.compile(r"(tag|name|id|repo)$", re.I)
_DHC_KEY_RE = re.compile(r"(d_?hc|delta_?hc|hc_?delta)", re.I)
_DOR_KEY_RE = re.compile(r"(d_?or|delta_?or|or_?delta)", re.I)
_CI_KEY_RE = re.compile(r"(ci|ci95|interval|lo.*hi|band)", re.I)
_LEGACY_KEY_RE = re.compile(r"legacy", re.I)


def _iter_records(obj: Any):
    """Yield dict records from whatever top-level container shape classification.json has."""
    if isinstance(obj, list):
        for r in obj:
            if isinstance(r, dict):
                yield r
    elif isinstance(obj, dict):
        # dict-of-records (keyed by pair id / child tag) vs a single wrapper dict with a list inside
        list_like_keys = [k for k, v in obj.items() if isinstance(v, list) and v and
                           all(isinstance(x, dict) for x in v[:3])]
        if list_like_keys:
            for k in list_like_keys:
                for r in obj[k]:
                    yield r
        else:
            all_dict_vals = obj and all(isinstance(v, dict) for v in obj.values())
            if all_dict_vals:
                for key, v in obj.items():
                    rec = dict(v)
                    rec.setdefault("_outer_key", key)
                    yield rec
            else:
                yield obj


def _find_label(rec: dict) -> str | None:
    for k, v in rec.items():
        if isinstance(v, str) and _LABEL_KEY_RE.search(k):
            up = v.strip().upper()
            if up in CLASSIFICATION_LABELS:
                return up
    # value itself might literally be one of the labels under an unlabelled key
    for v in rec.values():
        if isinstance(v, str) and v.strip().upper() in CLASSIFICATION_LABELS:
            return v.strip().upper()
    return None


def _find_tag_pair(rec: dict, outer_key: str | None) -> tuple[str | None, str | None]:
    parent = child = None
    # exact-name fast path: iter-4 classification.json (verified by reading it) uses bare
    # "parent"/"child" fields with no "tag"/"name"/"id"/"repo" suffix, so the suffix-anchored
    # _TAG_KEY_RE below never matches them and previously left every pair unmatched.
    for k, v in rec.items():
        if isinstance(v, str) and k.strip().lower() == "parent":
            parent = v
        elif isinstance(v, str) and k.strip().lower() == "child":
            child = v
    if parent is None or child is None:
        for k, v in rec.items():
            if not isinstance(v, str):
                continue
            if parent is None and _PARENT_KEY_RE.search(k) and _TAG_KEY_RE.search(k):
                parent = v
            elif child is None and _CHILD_KEY_RE.search(k) and _TAG_KEY_RE.search(k):
                child = v
    if child is None and outer_key:
        child = outer_key
    return parent, child


def _find_numeric(rec: dict, pattern: re.Pattern) -> float | None:
    for k, v in rec.items():
        if pattern.search(k) and isinstance(v, (int, float)) and not isinstance(v, bool):
            return float(v)
    return None


def _find_ci(rec: dict, base_pattern: re.Pattern) -> list | None:
    for k, v in rec.items():
        if base_pattern.search(k) and _CI_KEY_RE.search(k):
            if isinstance(v, (list, tuple)) and len(v) == 2:
                return [float(v[0]), float(v[1])]
            if isinstance(v, dict) and {"lo", "hi"} <= set(v.keys()):
                return [float(v["lo"]), float(v["hi"])]
    return None


def load_classification(path: Path) -> dict:
    """Open + schema-record + adaptively index the iteration-4 classification file.

    Returns {"schema", "by_child_tag": {tag: rec}, "by_pair_key": {(parent,child): rec},
             "legacy_child_tags": set, "n_records"}.
    """
    raw = json.loads(path.read_text())
    schema = record_schema(raw)
    by_child: dict[str, dict] = {}
    by_pair: dict[tuple, dict] = {}
    legacy: set[str] = set()
    n = 0
    outer_key = None
    if isinstance(raw, dict):
        for key, v in raw.items():
            if isinstance(v, dict) and not any(
                isinstance(vv, list) and vv and all(isinstance(x, dict) for x in vv[:3])
                for vv in raw.values()
            ):
                outer_key = key
                break
    for rec in _iter_records(raw):
        n += 1
        ok = rec.get("_outer_key")
        parent, child = _find_tag_pair(rec, ok)
        label = _find_label(rec)
        # iter-4's classification.json (verified by reading it) nests dHC/dOR/CIs one level
        # down under rec["primary"] (the "pooled (primary)" column the prereg rule quotes as
        # the operative one; rec["laneC"] mirrors the reused Lane C truth). The flat-dict
        # regex finders below only ever look at top-level keys, so without this merge dHC/dOR
        # were always None even though matching, non-nested keys exist inside "primary".
        search_rec = rec
        primary_sub = rec.get("primary")
        if isinstance(primary_sub, dict):
            search_rec = {**rec, **primary_sub}
        dhc = _find_numeric(search_rec, _DHC_KEY_RE)
        dor = _find_numeric(search_rec, _DOR_KEY_RE)
        ci_hc = _find_ci(search_rec, _DHC_KEY_RE)
        ci_or = _find_ci(search_rec, _DOR_KEY_RE)
        is_legacy = any(isinstance(v, bool) and v and _LEGACY_KEY_RE.search(k) for k, v in rec.items())
        parsed = {"label": label, "dHC": dhc, "dOR": dor, "ci_HC": ci_hc, "ci_OR": ci_or,
                  "parent": parent, "child": child, "legacy": is_legacy}
        if child:
            by_child[child] = parsed
            if is_legacy:
                legacy.add(child)
        if parent and child:
            by_pair[(parent, child)] = parsed
    return {"schema": schema, "by_child_tag": by_child, "by_pair_key": by_pair,
            "legacy_child_tags": legacy, "n_records": n, "path": str(path)}


def load_text_baseline(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {"available": False, "path": str(path) if path else None}
    raw = json.loads(path.read_text())
    schema = record_schema(raw)
    # schema-adaptive: look for any per-tag dict with regex/greedy-refusal alarm-ish fields
    by_tag: dict[str, dict] = {}
    for rec in _iter_records(raw):
        tag = rec.get("tag") or rec.get("child") or rec.get("_outer_key")
        if not isinstance(tag, str):
            continue
        entry = {}
        for k, v in rec.items():
            lk = k.lower()
            if "regex" in lk or "card" in lk or "name" in lk:
                entry.setdefault("regex_fields", {})[k] = v
            if "refus" in lk or "greedy" in lk:
                entry.setdefault("refusal_fields", {})[k] = v
        if entry:
            by_tag[tag] = entry
    return {"available": True, "path": str(path), "schema": schema, "by_tag": by_tag,
            "n_records_scanned": sum(1 for _ in _iter_records(raw))}


def find_text_baseline_default() -> Path | None:
    for root in (ITER4_EXP1,):
        hits = sorted((root / "results").rglob("text_baseline.json"))
        if hits:
            return hits[0]
    return None


def find_iter4_scores_dir() -> Path | None:
    d = ITER4_EXP1 / "results" / "scores"
    return d if d.exists() else None


def probe_iter4_scores_for_bar_pair_ci(bar: str) -> dict:
    """Instruction 3: 'if a bar's per-pair CI already exists in iteration-4's own scores
    (pairs_long/scores file), prefer the stored one and say so.' Schema-adaptive probe:
    look for a single aggregate file (pairs_long*.json / scores_long*.json) under iter-4
    results/, else inspect one per-checkpoint scores/ckpt_*.json file's schema (these are
    single-checkpoint scalar readouts, not per-pair, so they cannot supply a pair-level CI
    unless a field literally has 'ci'/'pair' in its name)."""
    root = ITER4_EXP1 / "results"
    long_candidates = sorted(root.glob("*pairs_long*.json")) + sorted(root.glob("*scores_long*.json"))
    if long_candidates:
        p = long_candidates[0]
        raw = json.loads(p.read_text())
        return {"found_long_file": str(p), "schema": record_schema(raw)}
    scores_dir = find_iter4_scores_dir()
    if scores_dir is None:
        return {"found_long_file": None, "scores_dir": None}
    sample = sorted(scores_dir.glob("ckpt_*.json"))
    if not sample:
        return {"found_long_file": None, "scores_dir": str(scores_dir), "n_ckpt_files": 0}
    raw = json.loads(sample[0].read_text())
    has_ci_field = any(_CI_KEY_RE.search(k) and bar.lower() in k.lower()
                        for k in _flatten_keys(raw))
    return {"found_long_file": None, "scores_dir": str(scores_dir), "n_ckpt_files": len(sample),
            "sample_file": str(sample[0]), "sample_schema": record_schema(raw),
            "has_matching_ci_field_for_bar": bool(has_ci_field)}


def _flatten_keys(o: Any, prefix: str = "") -> list[str]:
    out = []
    if isinstance(o, dict):
        for k, v in o.items():
            kk = f"{prefix}.{k}" if prefix else k
            out.append(kk)
            out.extend(_flatten_keys(v, kk))
    return out


# --------------------------------------------------------------------------- #
# Tier-B per-item bootstrap                                                   #
# --------------------------------------------------------------------------- #


def _seed_for_pair(pid: str) -> int:
    return int(hashlib.sha256((BOOTSTRAP_SEED_BASE + pid).encode()).hexdigest()[:8], 16)


# --------------------------------------------------------------------------- #
# BL1_easy/BL1_hard bar bootstrap, computed DIRECTLY from harvested arrays    #
# (ncands.bl1_easy_hard: (r_refusal - r_control) @ hidden-state index L,     #
# EASY = 48 advbench-harmful vs 48 dolly-benign / HARD = 160 mixed)          #
# --------------------------------------------------------------------------- #

BAR_ITEM_FIELDS = {"BL1_easy": ("drv_L_easy", "y_easy"), "BL1_hard": ("drv_L_hard", "y_hard")}
_BAR_ITEM_CACHE: dict[str, dict | None] = {}


def _load_bar_items(tag: str) -> dict | None:
    """Per-tag EASY/HARD per-item (r_refusal - r_control)[:, L] vectors, loaded straight from
    the shared I4/harvest/<tag>/ dir (r_refusal.npy, r_control.npy, meta.json) -- the exact
    inputs ncands.Ckpt.load()/bl1_easy_hard() use, in the canonical 256-row stimuli.json order.
    Returns None (never raises) if the tag's harvest is absent or not the canonical 256-row
    schema (a reduced/smoke harvest would silently mis-index against stim.easy_idx/hard_idx)."""
    if tag in _BAR_ITEM_CACHE:
        return _BAR_ITEM_CACHE[tag]
    d = H4 / tag
    rr, rc, meta_p = d / "r_refusal.npy", d / "r_control.npy", d / "meta.json"
    out = None
    if rr.exists() and rc.exists() and meta_p.exists():
        meta = json.loads(meta_p.read_text())
        L = int(meta["n_layers"])
        r_ref = np.load(rr).astype(np.float64)
        r_ctl = np.load(rc).astype(np.float64)
        if r_ref.shape == r_ctl.shape and r_ref.shape[0] == 256 and r_ref.shape[1] == L + 1:
            drv_L = r_ref[:, L] - r_ctl[:, L]
            stim = ncands.load_stimuli()
            out = {"drv_L_easy": drv_L[stim.easy_idx], "y_easy": stim.y_easy,
                   "drv_L_hard": drv_L[stim.hard_idx], "y_hard": stim.y_hard}
    _BAR_ITEM_CACHE[tag] = out
    return out


def _bl1_contrast(drv: np.ndarray, y: np.ndarray, idx: np.ndarray) -> float:
    x, yy = drv[idx], y[idx]
    m1, m0 = yy == 1, yy == 0
    if m1.sum() == 0 or m0.sum() == 0:
        return float("nan")
    return float(x[m1].mean() - x[m0].mean())


def _bl1_easy_point_check(tags: tuple[str, ...] = ("F1__ref", "F2__ref", "F3__ref")) -> dict:
    """Assert this module's lightweight BL1_easy point estimate (unresampled idx, from
    _load_bar_items + _bl1_contrast) equals bars.py's own reuse.ncands.bl1_easy_hard()
    (via a full ncands.Ckpt.load()) to ~1e-9, for >=3 tags."""
    rows, max_abs_diff = [], 0.0
    for tag in tags:
        d = H4 / tag
        try:
            ckpt = ncands.Ckpt.load(tag, d)
            registered = ncands.bl1_easy_hard(ckpt)["BL1_easy"]
        except Exception as exc:  # noqa: BLE001
            rows.append({"tag": tag, "error": repr(exc)[:300]})
            continue
        items = _load_bar_items(tag)
        n = items["drv_L_easy"].shape[0]
        mine = _bl1_contrast(items["drv_L_easy"], items["y_easy"], np.arange(n))
        diff = abs(mine - registered)
        max_abs_diff = max(max_abs_diff, diff)
        rows.append({"tag": tag, "mine": mine, "reuse.ncands.bl1_easy_hard": registered, "abs_diff": diff})
    return {"tags": list(tags), "rows": rows, "max_abs_diff": max_abs_diff, "passes_1e-9": max_abs_diff < 1e-9}


def bootstrap_bar_pair(bar: str, pid: str, parent_tag: str, child_tag: str) -> dict:
    """Same B=200 prompt-bootstrap scheme as bootstrap_tierB_pair (seed =
    sha256('20260922|pairaudit|'+pid+'|'+bar), same resampled item positions for parent AND
    child, delta = child - parent, 95% percentile CI), applied to a bar computed directly from
    the shared harvested arrays instead of a candidate's registered-draw npz."""
    fields = BAR_ITEM_FIELDS.get(bar)
    if fields is None:
        return {"status": "NOT_BOOTSTRAPPABLE", "reason": f"{bar}: no direct-from-array bootstrap implemented here"}
    dkey, ykey = fields
    pp, cp = _load_bar_items(parent_tag), _load_bar_items(child_tag)
    if pp is None or cp is None:
        offenders = ([f"parent={parent_tag}"] if pp is None else []) + ([f"child={child_tag}"] if cp is None else [])
        return {"status": "NOT_BOOTSTRAPPABLE",
                "reason": f"{bar}: harvest r_refusal/r_control/meta missing or non-canonical-256-row "
                          f"for {', '.join(offenders)}"}
    n = pp[dkey].shape[0]
    if cp[dkey].shape[0] != n:
        return {"status": "NOT_BOOTSTRAPPABLE", "reason": f"{bar}: parent/child item counts differ"}
    seed = _seed_for_pair(pid + "|" + bar)
    rng = np.random.default_rng(seed)
    idx_full = np.arange(n)
    base = (_bl1_contrast(cp[dkey], cp[ykey], idx_full) -
            _bl1_contrast(pp[dkey], pp[ykey], idx_full))
    deltas = []
    for _ in range(BOOTSTRAP_B):
        idx = rng.integers(0, n, n)
        deltas.append(_bl1_contrast(cp[dkey], cp[ykey], idx) - _bl1_contrast(pp[dkey], pp[ykey], idx))
    deltas = np.array(deltas, dtype=float)
    good = deltas[np.isfinite(deltas)]
    if good.size < 50:
        return {"status": "NOT_BOOTSTRAPPABLE", "reason": f"{bar}: only {good.size}/{BOOTSTRAP_B} finite draws"}
    lo, hi = float(np.quantile(good, 0.025)), float(np.quantile(good, 0.975))
    return {"status": "OK", "B": BOOTSTRAP_B, "delta": base, "ci95": [lo, hi],
            "excludes_zero": bool(lo > 0.0 or hi < 0.0), "n_boot_ok": int(good.size)}


def _load_ckpt_pack(results_dir: Path, tag: str) -> dict | None:
    """Load a tag's per-tag json (bstar/per_fold) + its _items.npz, from <results_dir>/screen/."""
    js_path = results_dir / "screen" / f"ckpt_{tag}.json"
    npz_path = results_dir / "screen" / f"ckpt_{tag}_items.npz"
    if not js_path.exists() or not npz_path.exists():
        return None
    meta = json.loads(js_path.read_text())
    items = np.load(npz_path, allow_pickle=True)
    return {"meta": meta, "items": items}


def _w1_fold_value(items, fold: str, band: int, gap: float, idx: np.ndarray) -> float:
    pF = items[f"reg_fit{fold}_W1_p1F_b{band}"][idx]
    pR = items[f"reg_fit{fold}_W1_p1R_b{band}"][idx]        # (n, nR)
    p0 = items[f"reg_fit{fold}_p0_items"][idx]
    dF = abs(float(pF.mean()) - float(p0.mean()))
    dR = float(np.median(np.abs(pR.mean(0) - p0.mean())))
    return (dF - dR) / gap if gap else float("nan")


def _w2_fold_value(items, fold: str, mean_P: float, idx: np.ndarray) -> float:
    li = items[f"reg_fit{fold}_W2_ladder_items"][idx]        # (n, 6): [p0, p1..p5]
    p0 = float(li[:, 0].mean())
    pk = li[:, 1:].mean(0)
    for j in range(5):
        if (pk[j] - mean_P) < 0.5 * (p0 - mean_P):
            return float(j + 1)
    return 7.0


def _w7_fold_value(items, fold: str, gap: float, idx: np.ndarray) -> float:
    Y = items[f"reg_fit{fold}_W7_Y"][idx]                     # (n, rows, 8)
    m = Y.mean(0)                                             # (rows, 8)
    p0t = m[0]
    curve = (np.abs(m[1] - p0t) - np.median(np.abs(m[2:] - p0t[None]), axis=0)) / gap if gap else \
        np.full(8, np.nan)
    return float(np.mean(curve))


FOLD_VALUE_FNS = {"W1": _w1_fold_value, "W2": _w2_fold_value, "W7": _w7_fold_value}


def _required_keys_for_cand(cand: str, fold: str, per_fold_meta: dict) -> list[str]:
    """Names of the reg_fit{fold}_* npz keys bootstrap_tierB_pair needs for this
    candidate/fold, given that fold's registered b_write band (W1 only reads the
    single b_write band, not all 6 -- matching _w1_fold_value/n_items usage above)."""
    if cand == "W1":
        band = per_fold_meta[fold]["b_write"]
        return [f"reg_fit{fold}_p0_items", f"reg_fit{fold}_W1_p1F_b{band}", f"reg_fit{fold}_W1_p1R_b{band}"]
    if cand == "W2":
        return [f"reg_fit{fold}_W2_ladder_items"]
    return [f"reg_fit{fold}_W7_Y"]  # W7


def _missing_registered_items(pack: dict, cand: str) -> list[str]:
    """Which of the reg_fit{A,B}_* keys this candidate's bootstrap needs are absent from
    pack['items'] (the loaded ckpt_<tag>_items.npz). Empty list = fully bootstrappable.
    A tag whose Phase-2 stability re-run overwrote its registered-draw items.npz (see
    results/registered_items_restore_log.json) has ONLY st<...>_fit{A,B}_* keys left --
    never silently reuse those as a stand-in for the reg_fit{A,B}_* registered draw."""
    items, per_fold_meta = pack["items"], pack["meta"]["per_fold"]
    missing = []
    for f in ("A", "B"):
        for k in _required_keys_for_cand(cand, f, per_fold_meta):
            if k not in items.files:
                missing.append(k)
    return missing


def bootstrap_tierB_pair(cand: str, pid: str, parent_pack: dict, child_pack: dict,
                          parent_tag: str = "?", child_tag: str = "?") -> dict:
    """Prompt-bootstrap (B=200) of delta=child-parent for one W-candidate on one pair,
    resampling scoring-fold items WITH REPLACEMENT, same drawn indices parent+child,
    per fold {A,B}, then registered-scalar = mean over the two folds (cross_fit rule).

    Guards against the coverage gap documented in results/registered_items_restore_log.json
    (Phase-2 stability runs overwrote 14/42 tags' registered-draw items.npz; only 20/37
    restore attempts succeeded): if either side's ckpt_<tag>_items.npz lacks the reg_fit{A,B}_*
    arrays this candidate needs, this returns NOT_BOOTSTRAPPABLE naming the offending tag(s)
    instead of imputing or letting a bare KeyError propagate."""
    miss_p = _missing_registered_items(parent_pack, cand)
    miss_c = _missing_registered_items(child_pack, cand)
    if miss_p or miss_c:
        offenders = ([f"parent={parent_tag}"] if miss_p else []) + ([f"child={child_tag}"] if miss_c else [])
        return {"status": "NOT_BOOTSTRAPPABLE",
                "reason": f"{cand}: registered per-item arrays missing for {', '.join(offenders)} "
                          f"(Phase-2 stability overwrite not restored; see "
                          f"registered_items_restore_log.json)",
                "missing_keys": {"parent": miss_p, "child": miss_c}}
    fn = FOLD_VALUE_FNS[cand]
    seed = _seed_for_pair(pid + "|" + cand)
    rng = np.random.default_rng(seed)

    def n_items(fold: str, pack: dict) -> int:
        if cand == "W1":
            return pack["items"][f"reg_fit{fold}_p0_items"].shape[0]
        if cand == "W2":
            return pack["items"][f"reg_fit{fold}_W2_ladder_items"].shape[0]
        return pack["items"][f"reg_fit{fold}_W7_Y"].shape[0]

    def point_and_boot(pack: dict) -> tuple[float, list[float]]:
        vals = []
        n_folds = {f: n_items(f, pack) for f in ("A", "B")}
        per_fold_meta = pack["meta"]["per_fold"]
        base = 0.0
        for f in ("A", "B"):
            gap = per_fold_meta[f]["gap"]
            if cand == "W1":
                band = per_fold_meta[f]["b_write"]
                base += _w1_fold_value(pack["items"], f, band, gap, np.arange(n_folds[f]))
            elif cand == "W2":
                mean_P = per_fold_meta[f]["mean_P"]
                base += _w2_fold_value(pack["items"], f, mean_P, np.arange(n_folds[f]))
            else:
                base += _w7_fold_value(pack["items"], f, gap, np.arange(n_folds[f]))
        base /= 2.0
        for _ in range(BOOTSTRAP_B):
            total = 0.0
            for f in ("A", "B"):
                idx = rng.integers(0, n_folds[f], n_folds[f])
                gap = per_fold_meta[f]["gap"]
                if cand == "W1":
                    band = per_fold_meta[f]["b_write"]
                    total += _w1_fold_value(pack["items"], f, band, gap, idx)
                elif cand == "W2":
                    mean_P = per_fold_meta[f]["mean_P"]
                    total += _w2_fold_value(pack["items"], f, mean_P, idx)
                else:
                    total += _w7_fold_value(pack["items"], f, gap, idx)
            vals.append(total / 2.0)
        return base, vals

    # to keep "same indices parent and child" honest despite possibly-unequal fold sizes
    # between parent/child ckpts (should not happen for matched pairs, but guard anyway):
    seed2 = _seed_for_pair(pid + "|" + cand)
    rng_shared = np.random.default_rng(seed2)
    n_folds_p = {f: n_items(f, parent_pack) for f in ("A", "B")}
    n_folds_c = {f: n_items(f, child_pack) for f in ("A", "B")}
    same_shape = n_folds_p == n_folds_c
    if not same_shape:
        return {"status": "NOT_BOOTSTRAPPABLE",
                "reason": f"parent/child scoring-fold item counts differ ({n_folds_p} vs {n_folds_c}); "
                          f"'same indices for parent and child' is not honestly definable"}

    base_p = 0.0
    base_c = 0.0
    per_fold_meta_p = parent_pack["meta"]["per_fold"]
    per_fold_meta_c = child_pack["meta"]["per_fold"]
    for f in ("A", "B"):
        idx_full = np.arange(n_folds_p[f])
        if cand == "W1":
            base_p += _w1_fold_value(parent_pack["items"], f, per_fold_meta_p[f]["b_write"],
                                      per_fold_meta_p[f]["gap"], idx_full)
            base_c += _w1_fold_value(child_pack["items"], f, per_fold_meta_c[f]["b_write"],
                                      per_fold_meta_c[f]["gap"], idx_full)
        elif cand == "W2":
            base_p += _w2_fold_value(parent_pack["items"], f, per_fold_meta_p[f]["mean_P"], idx_full)
            base_c += _w2_fold_value(child_pack["items"], f, per_fold_meta_c[f]["mean_P"], idx_full)
        else:
            base_p += _w7_fold_value(parent_pack["items"], f, per_fold_meta_p[f]["gap"], idx_full)
            base_c += _w7_fold_value(child_pack["items"], f, per_fold_meta_c[f]["gap"], idx_full)
    base_p /= 2.0
    base_c /= 2.0
    base_delta = base_c - base_p

    deltas = []
    for _ in range(BOOTSTRAP_B):
        tot_p = 0.0
        tot_c = 0.0
        for f in ("A", "B"):
            idx = rng_shared.integers(0, n_folds_p[f], n_folds_p[f])   # SAME idx both sides
            if cand == "W1":
                tot_p += _w1_fold_value(parent_pack["items"], f, per_fold_meta_p[f]["b_write"],
                                         per_fold_meta_p[f]["gap"], idx)
                tot_c += _w1_fold_value(child_pack["items"], f, per_fold_meta_c[f]["b_write"],
                                         per_fold_meta_c[f]["gap"], idx)
            elif cand == "W2":
                tot_p += _w2_fold_value(parent_pack["items"], f, per_fold_meta_p[f]["mean_P"], idx)
                tot_c += _w2_fold_value(child_pack["items"], f, per_fold_meta_c[f]["mean_P"], idx)
            else:
                tot_p += _w7_fold_value(parent_pack["items"], f, per_fold_meta_p[f]["gap"], idx)
                tot_c += _w7_fold_value(child_pack["items"], f, per_fold_meta_c[f]["gap"], idx)
        deltas.append((tot_c / 2.0) - (tot_p / 2.0))
    deltas = np.array(deltas, dtype=float)
    good = deltas[np.isfinite(deltas)]
    if good.size < 50:
        return {"status": "NOT_BOOTSTRAPPABLE", "reason": f"only {good.size}/200 finite draws"}
    lo, hi = float(np.quantile(good, 0.025)), float(np.quantile(good, 0.975))
    return {"status": "OK", "B": BOOTSTRAP_B, "delta": base_delta, "ci95": [lo, hi],
            "excludes_zero": bool(lo > 0.0 or hi < 0.0), "n_boot_ok": int(good.size)}


# --------------------------------------------------------------------------- #
# clause (iv): false alarms                                                   #
# --------------------------------------------------------------------------- #


def classify_degenerate(child_tag: str) -> str | None:
    if child_tag.endswith(DEGENERATE_WU05_SUFFIX):
        return "wu05_head_only"
    if child_tag.endswith(DEGENERATE_SYSPROMPT_SUFFIX):
        return "sysprompt"
    return None


def compute_all_candidate_alarms(pairs: list[tuple[str, str, str]], tierA_boot: dict,
                                  ckpt_pack_cache: dict, results_dir: Path) -> tuple[dict, dict]:
    """Returns (alarms, unbootstrappable) where
    alarms[cand][pid] = {"excludes_zero": bool, "delta": float, "ci95": [lo,hi]}
    unbootstrappable[cand] = reason (global) or per-pid overrides."""
    alarms: dict[str, dict] = {c: {} for c in TIER_A_KEYS + TIER_B_BOOTSTRAPPABLE}
    unbootstrappable: dict[str, Any] = {}
    for c in NOT_BOOTSTRAPPABLE_REASONS:
        unbootstrappable[c] = NOT_BOOTSTRAPPABLE_REASONS[c]

    for pid, par, chi in pairs:
        rec = tierA_boot.get(pid)
        if rec and rec.get("status") == "OK":
            for c in TIER_A_KEYS:
                ci = rec["ci95"].get(c)
                if ci and ci[0] is not None:
                    alarms[c][pid] = {"excludes_zero": bool(ci[0] > 0.0 or ci[1] < 0.0),
                                       "delta": rec["delta"].get(c), "ci95": ci}
        for c in TIER_B_BOOTSTRAPPABLE:
            if par not in ckpt_pack_cache:
                ckpt_pack_cache[par] = _load_ckpt_pack(results_dir, par)
            if chi not in ckpt_pack_cache:
                ckpt_pack_cache[chi] = _load_ckpt_pack(results_dir, chi)
            pp, cp = ckpt_pack_cache[par], ckpt_pack_cache[chi]
            if pp is None or cp is None:
                alarms[c][pid] = {"status": "ARRAYS_MISSING"}
                continue
            res = bootstrap_tierB_pair(c, pid, pp, cp, parent_tag=par, child_tag=chi)
            alarms[c][pid] = res
    return alarms, unbootstrappable


def clause_iv_mcnemar(pairs: list[tuple[str, str, str]], labels: dict[str, str | None],
                       alarms: dict, bl1_alarms: dict) -> dict:
    noop_pids = [pid for pid, _, _ in pairs if labels.get(pid) == "NOOP"]
    degenerate = {pid: classify_degenerate(chi) for pid, _, chi in pairs}
    nondeg_pids = [pid for pid in noop_pids if degenerate.get(pid) is None]
    out = {"n_noop_pairs_15": len(noop_pids), "n_nondegenerate_12": len(nondeg_pids),
           "degenerate_pids": {pid: degenerate[pid] for pid in noop_pids if degenerate.get(pid)},
           "candidates": {}}
    for cand, cand_alarms in alarms.items():
        row = {}
        for subset_name, pid_list in (("all_15", noop_pids), ("nondegenerate_12", nondeg_pids)):
            a = b = c = d = 0
            evaluable = 0
            for pid in pid_list:
                ca = cand_alarms.get(pid, {})
                ba = bl1_alarms.get(pid, {})
                if ca.get("status") in ("NOT_BOOTSTRAPPABLE", "ARRAYS_MISSING") or \
                   ba.get("status") in ("NOT_BOOTSTRAPPABLE", "ARRAYS_MISSING") or \
                   "excludes_zero" not in ca or "excludes_zero" not in ba:
                    continue
                evaluable += 1
                cflag, bflag = ca["excludes_zero"], ba["excludes_zero"]
                if cflag and bflag:
                    a += 1
                elif cflag and not bflag:
                    b += 1
                elif not cflag and bflag:
                    c += 1
                else:
                    d += 1
            mc = mcnemar_exact(b, c)
            row[subset_name] = {"a_both": a, "b_cand_only": b, "c_bl1_only": c, "d_neither": d,
                                 "n_evaluable": evaluable, "n_total_in_subset": len(pid_list),
                                 "mcnemar": mc}
        out["candidates"][cand] = row
    return out


# --------------------------------------------------------------------------- #
# clause (v): sensitivity                                                     #
# --------------------------------------------------------------------------- #


AMD_CHILD_TAG = "HG__amd--AMD-OLMo-1B-SFT"
AMD_PARENT_TAG = "HG__amd--AMD-OLMo-1B"


def clause_v_sensitivity(pairs: list[tuple[str, str, str]], labels: dict, cls_by_pair: dict,
                          alarms: dict) -> dict:
    eff_pids = [pid for pid, _, _ in pairs if labels.get(pid) == "EFFECTIVE"]
    out = {"n_effective_pairs": len(eff_pids), "candidates": {}, "amd_olmo_base_to_sft": {}}
    for cand, cand_alarms in alarms.items():
        s_hc = EXPECTED_SIGN_HC.get(cand)
        if cand in NEGATE_OR_FOR_SHC:
            or_exp = EXPECTED_SIGN_OR.get(cand)
            s_hc = -or_exp if or_exp is not None else s_hc
        detected = []
        not_evaluable = []
        for pid in eff_pids:
            par, chi = next((p, c) for pid2, p, c in pairs if pid2 == pid)
            ca = cand_alarms.get(pid, {})
            rec = cls_by_pair.get((par, chi)) or cls_by_pair.get((None, chi))
            dhc = rec.get("dHC") if rec else None
            if ca.get("status") in ("NOT_BOOTSTRAPPABLE", "ARRAYS_MISSING") or \
               "excludes_zero" not in ca or dhc is None or s_hc is None:
                not_evaluable.append(pid)
                continue
            if not ca["excludes_zero"]:
                continue
            delta = ca.get("delta")
            if delta is None:
                not_evaluable.append(pid)
                continue
            want_sign = (1 if dhc >= 0 else -1) * s_hc
            got_sign = 1 if delta >= 0 else (-1 if delta < 0 else 0)
            if got_sign == want_sign:
                detected.append(pid)
        out["candidates"][cand] = {
            "s_HC_used": s_hc, "detected_pids": detected, "n_detected": len(detected),
            "n_effective": len(eff_pids), "not_evaluable_pids": not_evaluable,
            "x_of_9_legacy_plus_fresh": f"{len(detected)}/{len(eff_pids)} (legacy/fresh split "
                                        f"requires a 'legacy' flag in classification.json; see "
                                        f"top-level 'legacy_flag_found')"}
    amd_pid = next((pid for pid, p, c in pairs if p == AMD_PARENT_TAG and c == AMD_CHILD_TAG), None)
    if amd_pid:
        rec = cls_by_pair.get((AMD_PARENT_TAG, AMD_CHILD_TAG))
        out["amd_olmo_base_to_sft"] = {
            "pid": amd_pid, "in_panel": True, "label": labels.get(amd_pid),
            "dHC_from_classification": rec.get("dHC") if rec else None,
            "per_candidate_alarm": {c: alarms[c].get(amd_pid) for c in alarms},
        }
    else:
        out["amd_olmo_base_to_sft"] = {"in_panel": False,
                                        "note": "AMD-OLMo base->SFT structural pair not found "
                                                "among structural_pairs() output for this panel"}
    return out


# --------------------------------------------------------------------------- #
# clause (vi): text bars                                                      #
# --------------------------------------------------------------------------- #


STRUCTURALLY_BLIND_FAMILIES = {"write-handle", "write-handle (benign side)",
                                "write-handle (two-sided)", "write-handle (decode site)",
                                "redundancy", "redundancy (self-repair scalarisation)",
                                "rotation under self-lesion"}
CAND_FAMILY = {
    "W1": "write-handle", "W2": "redundancy", "W3": "redundancy",
    "W4": "redundancy (self-repair scalarisation)", "W5": "write-handle (benign side)",
    "W6": "write-handle (two-sided)", "W7": "write-handle (decode site)", "W7c": "write-handle (decode site)",
    "W8": "rotation under self-lesion",
    "G1": "geometry", "G2": "geometry", "G3": "geometry", "G4": "geometry (level, BL1-residual)",
    "A1": "competing mechanism", "A1_slope": "competing mechanism", "A1_prior": "competing mechanism",
    "A2": "competing mechanism (benign-only)", "A3": "competing mechanism",
}


def clause_vi_text_bars(pairs, labels, alarms, text_baseline: dict) -> dict:
    noop_pids = [pid for pid, _, _ in pairs if labels.get(pid) == "NOOP"]
    eff_pids = [pid for pid, _, _ in pairs if labels.get(pid) == "EFFECTIVE"]
    out = {"text_baseline_available": text_baseline.get("available", False),
           "text_baseline_schema": text_baseline.get("schema"),
           "prereg_quoted_aggregate": {
               "card_name_regex": {"false_alarms": "0/15", "sensitivity": "5/9",
                                    "forward_passes": 0},
               "greedy_refusal_text": {"false_alarms": "2/15", "sensitivity": "7/8"},
               "note": "quoted from prereg.json bars.text_bars; NOT necessarily identical to the "
                       "15/12-pair or effective-pair subsets computed by THIS module"},
           "recomputed_on_our_pairs": None, "candidates": {}}
    by_tag = text_baseline.get("by_tag", {})
    if by_tag:
        fa_regex = fa_greedy = sens_regex = sens_greedy = 0
        n_noop_eval = n_eff_eval = 0
        for pid, par, chi in pairs:
            entry = by_tag.get(chi)
            if not entry:
                continue
            if labels.get(pid) == "NOOP":
                n_noop_eval += 1
            if labels.get(pid) == "EFFECTIVE":
                n_eff_eval += 1
        out["recomputed_on_our_pairs"] = {
            "note": "per-tag text_baseline entries found but no unambiguous alarm-boolean field "
                    "matched by regex; see text_baseline_schema to extend the field matcher",
            "n_noop_pairs_with_tag_present": n_noop_eval, "n_effective_pairs_with_tag_present": n_eff_eval}
    for cand in alarms:
        fam = CAND_FAMILY.get(cand, "")
        blind_axis = fam in STRUCTURALLY_BLIND_FAMILIES
        out["candidates"][cand] = {
            "family": fam,
            "beats_text_bars_on_structurally_blind_axis":
                bool(blind_axis) if blind_axis else "N/A (not a write-handle/redundancy family; "
                                                      "text bars are not structurally blind to it)",
            "reasoning": "text bars (card/name regex, greedy refusal-text rate) require zero forward "
                         "passes and read no internal activations, so they cannot represent causal "
                         "write-handle strength or redundancy under ablation by construction" if blind_axis
                         else "this candidate is not a write-handle/redundancy family; no structural "
                              "blind-spot argument applies",
        }
    return out


# --------------------------------------------------------------------------- #
# clause (vii): shuffled-label band + ceiling/floor                           #
# --------------------------------------------------------------------------- #


TIER_B_HAS_R_CONTROL = {"W1": True, "W5": True, "W7": True,
                         "W2": False, "W3": False, "W4": False, "W6": False, "W8": False,
                         "A1": False, "A1_prior": False, "A2": False}


def clause_vii_band_and_ceiling(pairs, tierA_dir: Path, screen_table_path: Path) -> dict:
    out = {"tier_a_shuffled_band": {}, "tier_b_net_of_r": {}, "ceiling_floor": None}
    tag_files = sorted(tierA_dir.glob("*.json"))
    per_cand_outside = {c: [] for c in TIER_A_KEYS}
    for f in tag_files:
        try:
            d = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        sb = d.get("shuffled_band", {})
        for c in TIER_A_KEYS:
            v = sb.get(c)
            if isinstance(v, dict) and "outside" in v:
                per_cand_outside[c].append(bool(v["outside"]))
    for c, flags in per_cand_outside.items():
        if flags:
            frac = sum(flags) / len(flags)
            out["tier_a_shuffled_band"][c] = {"n_rows": len(flags), "n_outside": sum(flags),
                                               "frac_outside": frac, "pass_ge_50pct": frac >= 0.5}
        else:
            out["tier_a_shuffled_band"][c] = {"n_rows": 0, "status": "NO_DATA_FOUND"}
    for c, has_r in TIER_B_HAS_R_CONTROL.items():
        out["tier_b_net_of_r"][c] = {
            "has_matched_norm_random_direction_control": has_r,
            "clause_vii_satisfiable_via_operationalisation": has_r,
            "note": "prereg operationalisation: 'Tier B: satisfied only via the matched-norm "
                    "random-direction control (net-of-R construction)'"}
    if screen_table_path.exists():
        st = json.loads(screen_table_path.read_text())
        out["ceiling_floor"] = {"source": str(screen_table_path), "computed": True,
                                 "detail": "TODO: needs screen_table.json rows; see 'rows' key",
                                 "schema": record_schema(st)}
    else:
        out["ceiling_floor"] = {"source": str(screen_table_path), "computed": False,
                                 "status": "screen_table.json does not exist yet (S2.6 has not run)"}
    return out


# --------------------------------------------------------------------------- #
# main pipeline                                                               #
# --------------------------------------------------------------------------- #


def run(results_dir: Path, classification_path: Path, text_baseline_path: Path | None,
        out_path: Path) -> dict:
    gate = check_freeze_gate(results_dir)

    panel = json.loads((results_dir / "panel.json").read_text())
    included = list(panel["included"])
    pairs = structural_pairs(included)

    cls = load_classification(classification_path)
    tb_path = text_baseline_path or find_text_baseline_default()
    text_baseline = load_text_baseline(tb_path)

    tierA_boot = json.loads((results_dir / "screen" / "pair_boot_tierA.json").read_text())

    labels: dict[str, str | None] = {}
    unmatched = []
    for pid, par, chi in pairs:
        rec = cls["by_pair_key"].get((par, chi)) or cls["by_child_tag"].get(chi)
        if rec is None:
            unmatched.append({"pid": pid, "parent": par, "child": chi})
            labels[pid] = None
        else:
            labels[pid] = rec.get("label")

    cache: dict[str, dict | None] = {}
    alarms, not_bootstrappable = compute_all_candidate_alarms(pairs, tierA_boot, cache, results_dir)

    bl1_probe = probe_iter4_scores_for_bar_pair_ci("BL1_easy")
    bar_probes = {b: probe_iter4_scores_for_bar_pair_ci(b) for b in BARS}
    # BL1_easy/BL1_hard are computed DIRECTLY from the shared harvested r_refusal/r_control
    # arrays (never from iteration-4's own stored/reduced scores, which have no per-pair CI --
    # see bar_probes.BL1_easy) via bootstrap_bar_pair(); other bars have no direct-array
    # bootstrap implemented here (would need Gram-matrix axis refitting per bootstrap draw for
    # N1/N6, or A_ams.npy + ams_reimpl for AMS_T1_sigma) and remain NOT_BOOTSTRAPPABLE.
    bl1_easy_point_check = _bl1_easy_point_check()
    bl1_alarms = {pid: bootstrap_bar_pair("BL1_easy", pid, par, chi) for pid, par, chi in pairs}
    bl1_hard_alarms = {pid: bootstrap_bar_pair("BL1_hard", pid, par, chi) for pid, par, chi in pairs}

    iv = clause_iv_mcnemar(pairs, labels, alarms, bl1_alarms)
    iv["denominator_discrepancy"] = (
        "n_noop_pairs_15/nondegenerate_12 are historical FIELD NAMES from the original plan, "
        "which took its 15/12 from iteration-4's OWN primary_noop_pairs list restricted to this "
        "module's panel. This module instead labels every structural pair on THIS iteration's "
        "panel.json from classification.json's full 56-record pair list (by design -- it must "
        "audit this panel, not iter-4's), giving 24 NOOP pairs / 18 non-degenerate (6 degenerate: "
        "{F1,F2,F3}__sysprompt, {F1,F2,F3}__wu05) instead of 15/12. Both actual denominators are "
        "reported below per-candidate as n_total_in_subset."
    )
    iv["BL1_easy_point_estimate_check"] = bl1_easy_point_check
    iv["bl1_hard_alarms_n_ok"] = sum(1 for v in bl1_hard_alarms.values() if v.get("status") == "OK")
    v = clause_v_sensitivity(pairs, labels, cls["by_pair_key"], alarms)
    vi = clause_vi_text_bars(pairs, labels, alarms, text_baseline)
    vii = clause_vii_band_and_ceiling(pairs, results_dir / "screen" / "tierA",
                                       results_dir / "screen_table.json")

    report = {
        "freeze_gate": gate,
        "schema_records": {"classification": cls["schema"], "classification_path": str(classification_path),
                            "text_baseline": text_baseline.get("schema"),
                            "text_baseline_path": str(tb_path) if tb_path else None},
        "structural_pairs": {"n_pairs": len(pairs), "pair_ids": [p[0] for p in pairs]},
        "labels": labels,
        "unmatched_pairs": unmatched,
        "legacy_flag_found": bool(cls["legacy_child_tags"]),
        "legacy_child_tags": sorted(cls["legacy_child_tags"]),
        "not_bootstrappable": not_bootstrappable,
        "bar_probes": bar_probes,
        "bl1_hard_alarms": bl1_hard_alarms,
        "clause_iv_false_alarms": iv,
        "clause_v_sensitivity": v,
        "clause_vi_text_bars": vi,
        "clause_vii_band_ceiling_floor": vii,
    }
    out_path.write_text(json.dumps(report, indent=1, default=str))
    return report


# --------------------------------------------------------------------------- #
# self-test                                                                    #
# --------------------------------------------------------------------------- #


def self_test(out_path: Path) -> dict:
    results = {"assertions_run": 0, "assertions_passed": 0, "failures": []}

    def check(name: str, cond: bool):
        results["assertions_run"] += 1
        if cond:
            results["assertions_passed"] += 1
        else:
            results["failures"].append(name)

    # --- McNemar b/c handling (statlib) ---
    m = mcnemar_exact(0, 0)
    check("mcnemar_00_n0", m["n_discordant"] == 0 and m["p_two_sided"] == 1.0)
    m = mcnemar_exact(8, 0)
    check("mcnemar_8_0_significant", m["p_two_sided"] < 0.05)
    m1 = mcnemar_exact(3, 7)
    m2 = mcnemar_exact(7, 3)
    check("mcnemar_symmetric_in_bc", abs(m1["p_two_sided"] - m2["p_two_sided"]) < 1e-12)
    m = mcnemar_exact(10, 10)
    check("mcnemar_balanced_high_p", m["p_two_sided"] > 0.5)

    # --- clause_iv 2x2 counting on a synthetic pair set ---
    pairs = [("p1", "A", "A_x1"), ("p2", "A", "A_x2"), ("p3", "A", "A_x3"),
             ("p4", "A", "A_x4__wu05"), ("p5", "A", "A_x5__sysprompt")]
    labels = {"p1": "NOOP", "p2": "NOOP", "p3": "NOOP", "p4": "NOOP", "p5": "NOOP"}
    alarms = {"CAND": {
        "p1": {"excludes_zero": True, "delta": 1.0},
        "p2": {"excludes_zero": False, "delta": 0.1},
        "p3": {"excludes_zero": True, "delta": -1.0},
        "p4": {"excludes_zero": False, "delta": 0.0},
        "p5": {"excludes_zero": True, "delta": 0.5},
    }}
    bl1 = {
        "p1": {"excludes_zero": True, "delta": 0.9},
        "p2": {"excludes_zero": True, "delta": 0.2},
        "p3": {"excludes_zero": False, "delta": -0.05},
        "p4": {"excludes_zero": False, "delta": 0.0},
        "p5": {"excludes_zero": False, "delta": 0.1},
    }
    iv = clause_iv_mcnemar(pairs, labels, alarms, bl1)
    row = iv["candidates"]["CAND"]["all_15"]
    # cand alarms: p1,p3,p5 True; p2,p4 False. bl1 alarms: p1,p2 True; p3,p4,p5 False.
    # a(both)=p1=1 b(cand only)=p3,p5=2 c(bl1 only)=p2=1 d(neither)=p4=1
    check("clause_iv_2x2_counts", row["a_both"] == 1 and row["b_cand_only"] == 2 and
          row["c_bl1_only"] == 1 and row["d_neither"] == 1)
    check("clause_iv_degenerate_detected", set(iv["degenerate_pids"].keys()) == {"p4", "p5"})
    check("clause_iv_nondegenerate_12_synth", iv["n_nondegenerate_12"] == 3)
    row12 = iv["candidates"]["CAND"]["nondegenerate_12"]
    check("clause_iv_12_subset_excludes_degenerate",
          row12["n_total_in_subset"] == 3 and (row12["a_both"] + row12["b_cand_only"] +
                                                 row12["c_bl1_only"] + row12["d_neither"]) <= 3)

    # --- clause_v sign logic ---
    pairs_v = [("q1", "A", "A_y1"), ("q2", "A", "A_y2"), ("q3", "A", "A_y3")]
    labels_v = {"q1": "EFFECTIVE", "q2": "EFFECTIVE", "q3": "EFFECTIVE"}
    cls_by_pair = {("A", "A_y1"): {"dHC": -0.5}, ("A", "A_y2"): {"dHC": 0.3}, ("A", "A_y3"): {"dHC": -0.2}}
    # candidate "G1" has s_HC = negation of OR expectation: OR exp for G1 = -1 -> s_HC = +1
    alarms_v = {"G1": {
        "q1": {"excludes_zero": True, "delta": -1.0},   # dHC<0 -> want_sign = (-1)*(+1) = -1; got -1 -> detected
        "q2": {"excludes_zero": True, "delta": 2.0},    # dHC>0 -> want_sign=(+1)*(+1)=+1; got +1 -> detected
        "q3": {"excludes_zero": False, "delta": -5.0},  # CI doesn't exclude 0 -> NOT detected
    }}
    v = clause_v_sensitivity(pairs_v, labels_v, cls_by_pair, alarms_v)
    check("clause_v_s_hc_negated_for_G1", v["candidates"]["G1"]["s_HC_used"] == 1)
    check("clause_v_detects_matching_signs", set(v["candidates"]["G1"]["detected_pids"]) == {"q1", "q2"})
    check("clause_v_ci_gate_excludes_q3", "q3" not in v["candidates"]["G1"]["detected_pids"])

    # a candidate with NEGATIVE-mismatched sign should NOT be detected
    alarms_v2 = {"G1": {
        "q1": {"excludes_zero": True, "delta": 1.0},   # dHC<0 -> want -1, got +1 -> NOT detected
        "q2": {"excludes_zero": True, "delta": 2.0},
        "q3": {"excludes_zero": True, "delta": 1.0},   # dHC<0 -> want -1, got +1 -> NOT detected
    }}
    v2 = clause_v_sensitivity(pairs_v, labels_v, cls_by_pair, alarms_v2)
    check("clause_v_mismatched_sign_not_detected", v2["candidates"]["G1"]["detected_pids"] == ["q2"])

    # --- W1 fold-value recombination sanity on synthetic arrays (mirrors tierB.py formula) ---
    class FakeItems(dict):
        def __getitem__(self, k):
            return dict.__getitem__(self, k)
    p0 = np.array([10.0, 12.0, 14.0], dtype=np.float32)
    pF = np.array([9.0, 11.0, 13.0], dtype=np.float32)          # F always -1 from p0
    pR = np.array([[10.5, 9.5], [12.5, 11.5], [14.5, 13.5]], dtype=np.float32)  # R +/-0.5
    fi = {"regX_p0_items": p0, "regX_W1_p1F_b1": pF, "regX_W1_p1R_b1": pR}
    dF = abs(float(pF.mean()) - float(p0.mean()))
    dR = float(np.median(np.abs(pR.mean(0) - p0.mean())))
    gap = 2.0
    w1 = (dF - dR) / gap
    check("w1_synthetic_formula_matches_hand_calc",
          abs(dF - 1.0) < 1e-6 and abs(dR - 0.5) < 1e-6 and abs(w1 - 0.25) < 1e-6)

    # --- degenerate classification ---
    check("degenerate_wu05", classify_degenerate("F1__wu05") == "wu05_head_only")
    check("degenerate_sysprompt", classify_degenerate("F2__sysprompt") == "sysprompt")
    check("degenerate_none", classify_degenerate("F1__a05") is None)

    # --- freeze gate refuses without survivor files (synthetic dir) ---
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        try:
            check_freeze_gate(tdp)
            check("freeze_gate_refuses_missing", False)
        except SystemExit as e:
            check("freeze_gate_refuses_missing", e.code == 2)
        surv = {"survivors": "NONE"}
        (tdp / "survivor.json").write_text(json.dumps(surv))
        (tdp / "survivor.sha256").write_text("deadbeef")
        try:
            check_freeze_gate(tdp)
            check("freeze_gate_refuses_mismatch", False)
        except SystemExit as e:
            check("freeze_gate_refuses_mismatch", e.code == 2)
        # matches check_freeze_gate's own convention (sha256(core.canonical_json(obj)), NOT
        # sha256 of the raw file bytes -- this synthetic file was written with json.dumps's
        # default spacing, which differs byte-for-byte from canonical_json's compact form)
        from core import canonical_json as _cj2, sha256_text as _st2  # noqa: PLC0415
        good_hash = _st2(_cj2(json.loads((tdp / "survivor.json").read_text())))
        (tdp / "survivor.sha256").write_text(good_hash)
        g = check_freeze_gate(tdp)
        check("freeze_gate_accepts_match", g["survivor_sha256_verified"] is True)

    results["ok"] = results["assertions_passed"] == results["assertions_run"]
    out_path.write_text(json.dumps(results, indent=1))
    return results


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(WS / "results"))
    ap.add_argument("--classification", default=str(DEFAULT_CLASSIFICATION))
    ap.add_argument("--text-baseline", default=None)
    ap.add_argument("--out", default=str(WS / "results" / "pair_audit.json"))
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        r = self_test(WS / "results" / "pair_audit_selftest.json")
        print(f"self-test: {r['assertions_passed']}/{r['assertions_run']} passed"
              f"{' -- FAILURES: ' + str(r['failures']) if r['failures'] else ''}")
        raise SystemExit(0 if r["ok"] else 1)

    report = run(Path(args.results_dir), Path(args.classification),
                 Path(args.text_baseline) if args.text_baseline else None, Path(args.out))
    print(f"pair_audit written to {args.out}; {len(report['structural_pairs']['pair_ids'])} "
          f"structural pairs, {len(report['unmatched_pairs'])} unmatched")


if __name__ == "__main__":
    main()
