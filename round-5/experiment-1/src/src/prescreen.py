#!/usr/bin/env python3
"""S3: pre-screen (S3.2) + effective-rank (S3.3), run under a hardened open() audit (INV-3).

Its own process. FIRST statement of main() hardens+self-tests core.OpenAudit, THEN installs it
for the entire S3.2/S3.3 computation. Only inputs read inside the audited block: prereg.json,
screen_table.json (both under --results-dir). Never opens graded_truth / classification /
aggregates / panel_manifest / anything under gen_art_experiment_2 / judge / truth / sealed / heldout.

Outputs (under --results-dir): s3_audit_selftest.json, prescreen.json (chain S3a),
rank_analysis.json (chain S3b). Audit trail: <logs-dir>/s3_open_audit.txt (+ a separate
s3_open_audit_selftest.txt for the self-test).

CLI:
    .venv_gpu/bin/python src/prescreen.py [--results-dir DIR] [--logs-dir DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import OpenAudit, canonical_json, chain_append, sha256_text, utc_now, write_json  # noqa: E402
import statlib  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")

FORBIDDEN = ["graded_truth", "classification", "aggregates", "panel_manifest",
             "gen_art_experiment_2", "judge", "truth", "sealed", "heldout"]

CANDIDATES = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "G1", "G2", "G3", "G4", "A1", "A2", "A3"]
TIER_A_CANDS = {"G1", "G2", "G3", "G4", "A3"}  # available from the array-only pass on the full panel


# --------------------------------------------------------------------------- #
# self-test (proves the hardened shim actually blocks pathlib / numpy / open) #
# --------------------------------------------------------------------------- #


def self_test(logs_dir: Path) -> dict:
    logs_dir.mkdir(parents=True, exist_ok=True)
    audit_log = logs_dir / "s3_open_audit_selftest.txt"
    tests = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        planted = tmp / "graded_truth.json"
        planted.write_text("{}")
        planted_npy = tmp / "graded_truth_arr.npy"
        np.save(planted_npy, np.arange(4))
        control = tmp / "not_forbidden.json"
        control.write_text("{}")

        with OpenAudit(audit_log, forbidden_substrings=FORBIDDEN) as audit:
            # 1. pathlib
            try:
                Path(planted).read_text()
                tests.append({"mechanism": "pathlib.Path.read_text", "raised_permission_error": False})
            except PermissionError:
                tests.append({"mechanism": "pathlib.Path.read_text", "raised_permission_error": True})
            # 2. numpy
            try:
                np.load(planted_npy)
                tests.append({"mechanism": "numpy.load", "raised_permission_error": False})
            except PermissionError:
                tests.append({"mechanism": "numpy.load", "raised_permission_error": True})
            # 3. builtins.open
            try:
                open(planted)  # noqa: SIM115
                tests.append({"mechanism": "builtins.open", "raised_permission_error": False})
            except PermissionError:
                tests.append({"mechanism": "builtins.open", "raised_permission_error": True})
            # 4. io.open directly
            import io as _io
            try:
                _io.open(planted)
                tests.append({"mechanism": "io.open", "raised_permission_error": False})
            except PermissionError:
                tests.append({"mechanism": "io.open", "raised_permission_error": True})
            # 5. os.open (low-level fd)
            import os as _os
            try:
                _os.open(str(planted), _os.O_RDONLY)
                tests.append({"mechanism": "os.open", "raised_permission_error": False})
            except PermissionError:
                tests.append({"mechanism": "os.open", "raised_permission_error": True})
            # negative control: a NON-forbidden path must still open fine
            try:
                txt = control.read_text()
                tests.append({"mechanism": "negative_control (non-forbidden path)",
                               "opened_ok": txt == "{}"})
            except Exception as exc:  # noqa: BLE001
                tests.append({"mechanism": "negative_control (non-forbidden path)",
                               "opened_ok": False, "error": repr(exc)})
            violations_seen = list(audit.violations)
            records_seen = list(audit.records)

    all_blocked = all(t.get("raised_permission_error", False) for t in tests if "raised_permission_error" in t)
    control_ok = next((t["opened_ok"] for t in tests if t["mechanism"].startswith("negative_control")), False)
    result = {
        "utc": utc_now(),
        "tests": tests,
        "n_violations_logged": len(violations_seen),
        "violations_sample": violations_seen[:5],
        "n_records_logged": len(records_seen),
        "all_forbidden_mechanisms_blocked": bool(all_blocked),
        "negative_control_ok": bool(control_ok),
        "PASS": bool(all_blocked and control_ok),
        "audit_log": str(audit_log),
    }
    return result


# --------------------------------------------------------------------------- #
# S3.2 pre-screen                                                              #
# --------------------------------------------------------------------------- #


def _row_values(rows: list[dict], cand: str, panel: list[str]) -> dict[str, dict]:
    """tag -> {'value':.., 'censored':bool} for a candidate, panel rows only."""
    out = {}
    for r in rows:
        if r["candidate"] != cand or r["tag"] not in panel:
            continue
        out[r["tag"]] = {"value": r["value"], "censored": bool(r.get("censored", False))}
    return out


def _expected_sign(prereg: dict, cand: str) -> str | None:
    d = prereg.get("d_candidates", {}).get(cand, {})
    es = d.get("expected_sign", {})
    hc = es.get("HC")
    if hc is None:
        return None
    hc = str(hc).strip()
    if hc.startswith("-"):
        return "-"
    if hc.startswith("+"):
        return "+"
    return hc[:1] if hc else None


def _sign_stability(rows: list[dict], cand: str, panel: list[str]) -> dict:
    """From screen_table stability draws (when present): fraction of (row, draw) pairs
    whose sign matches the row's registered value sign."""
    n_agree, n_total = 0, 0
    for r in rows:
        if r["candidate"] != cand or r["tag"] not in panel:
            continue
        reg = r.get("value")
        draws = r.get("stability")
        if reg is None or not isinstance(draws, list) or not draws:
            continue
        reg_sign = np.sign(reg)
        if reg_sign == 0:
            continue
        for d in draws:
            v = d.get("value")
            if v is None or not np.isfinite(v):
                continue
            n_total += 1
            if np.sign(v) == reg_sign:
                n_agree += 1
    if n_total == 0:
        return {"sign_agree_frac": None, "n_draws": 0}
    return {"sign_agree_frac": n_agree / n_total, "n_draws": n_total}


def run_s3_2(prereg: dict, screen_table: dict) -> dict:
    panel = list(screen_table.get("panel", []))
    rows = screen_table.get("rows", [])

    # BL1_easy per tag, from the bars table (bar == "BL1_easy").
    bl1 = {}
    for b in screen_table.get("bars", []):
        if b.get("bar") == "BL1_easy" and b.get("tag") not in bl1:
            bl1[b["tag"]] = b.get("value")

    out = {}
    n_dropped = n_kept = n_not_evaluable = 0
    for cand in CANDIDATES:
        vals = _row_values(rows, cand, panel)
        tags_ordered = [t for t in panel if t in vals]
        raw = np.array([vals[t]["value"] if vals[t]["value"] is not None else np.nan for t in tags_ordered], dtype=float)
        cen = np.array([vals[t]["censored"] for t in tags_ordered], dtype=bool)
        y_raw = np.array([bl1.get(t, np.nan) for t in tags_ordered], dtype=float)

        # censoring rule: winsorise at panel-95th-pct of uncensored values, EXCEPT W2 keeps its
        # sentinel 7 (never winsorised -- it is a meaningful ceiling code, not an outlier).
        if cand == "W2":
            wins = raw.copy()
        else:
            wins = statlib.winsorise_high(raw, cen) if cen.any() else raw

        sp_w = statlib.spearman(wins, y_raw)
        n = sp_w["n"]

        def _stat(idx, a=wins, b=y_raw):
            return statlib.spearman(a[idx], b[idx])["rho"]

        ci = statlib.checkpoint_bootstrap(_stat, len(wins), n_boot=2000,
                                           seed=prereg["operationalisation_seed"]) if len(wins) >= 5 else \
            {"point": sp_w["rho"], "lo": float("nan"), "hi": float("nan"), "n_boot_ok": 0, "excludes_zero": False}

        # censored-dropped variant
        keep = ~cen
        sp_dropped = statlib.spearman(raw[keep], y_raw[keep])

        mde = statlib.rho_mde(n) if n and n > 3 else float("nan")
        expected = _expected_sign(prereg, cand)
        stability = _sign_stability(rows, cand, panel)

        evaluable = n >= 3 and np.isfinite(sp_w["rho"])
        if not evaluable:
            status = "NOT_EVALUABLE"
            n_not_evaluable += 1
        elif abs(sp_w["rho"]) >= 0.50:
            status = "DROPPED"
            n_dropped += 1
        else:
            status = "KEPT"
            n_kept += 1

        out[cand] = {
            "rho": sp_w["rho"], "ci": {"lo": ci["lo"], "hi": ci["hi"], "n_boot_ok": ci.get("n_boot_ok")},
            "n": n, "mde": mde, "status": status,
            "rho_censored_dropped": sp_dropped["rho"], "n_censored_dropped": sp_dropped["n"],
            "n_censored": int(cen.sum()), "tier": "Tier-A-only" if cand in TIER_A_CANDS else "mixed/Tier-B",
            "stable_flags": stability, "expected_sign_HC": expected,
        }

    return {
        "utc": utc_now(),
        "threshold": 0.50,
        "prescreen_rule": "|Spearman(candidate, BL1_easy)| over screen-panel rows with both finite >= 0.50 -> DROPPED",
        "candidates": out,
        "n_dropped": n_dropped, "n_kept": n_kept, "n_not_evaluable": n_not_evaluable,
        "n_panel": len(panel),
    }


# --------------------------------------------------------------------------- #
# S3.3 effective rank                                                         #
# --------------------------------------------------------------------------- #


def _zscore_impute(mat: np.ndarray) -> tuple[np.ndarray, int]:
    """z-score each ROW (candidate) over its finite entries; NaN -> 0 AFTER z-scoring
    (mean imputation). Returns (matrix, n_imputed)."""
    m = mat.copy()
    n_imputed = 0
    for i in range(m.shape[0]):
        row = m[i]
        finite = np.isfinite(row)
        if finite.sum() >= 2:
            mu = row[finite].mean()
            sd = row[finite].std(ddof=0) or 1.0
            m[i] = (row - mu) / sd
        else:
            m[i] = 0.0
        bad = ~np.isfinite(m[i])
        n_imputed += int(bad.sum())
        m[i, bad] = 0.0
    return m, n_imputed


def _partial_out_bl1(mat_z: np.ndarray, y_z: np.ndarray) -> np.ndarray:
    """Replace each row by its OLS residual on z(BL1_easy) (with intercept)."""
    out = np.zeros_like(mat_z)
    design = np.column_stack([np.ones_like(y_z), y_z])
    for i in range(mat_z.shape[0]):
        beta, *_ = np.linalg.lstsq(design, mat_z[i], rcond=None)
        out[i] = mat_z[i] - design @ beta
    return out


def _build_matrix(rows: list[dict], cands: list[str], tags: list[str]) -> np.ndarray:
    idx = {(r["tag"], r["candidate"]): r["value"] for r in rows}
    m = np.full((len(cands), len(tags)), np.nan, dtype=float)
    for i, c in enumerate(cands):
        for j, t in enumerate(tags):
            v = idx.get((t, c))
            if v is not None:
                m[i, j] = v
    return m


def _spearman_matrix(mat_raw: np.ndarray, cands: list[str]) -> dict:
    n = len(cands)
    out = {}
    for i in range(n):
        for j in range(n):
            r = statlib.spearman(mat_raw[i], mat_raw[j])
            out[f"{cands[i]}|{cands[j]}"] = r["rho"]
    return out


def _rank_block(rows: list[dict], cands: list[str], tags: list[str], bl1_by_tag: dict) -> dict:
    mat_raw = _build_matrix(rows, cands, tags)
    mat_z, n_imputed = _zscore_impute(mat_raw)
    y_raw = np.array([bl1_by_tag.get(t, np.nan) for t in tags], dtype=float)
    y_finite = np.isfinite(y_raw)
    y_z = np.zeros_like(y_raw)
    if y_finite.sum() >= 2:
        mu, sd = y_raw[y_finite].mean(), (y_raw[y_finite].std(ddof=0) or 1.0)
        y_z[y_finite] = (y_raw[y_finite] - mu) / sd
    # y NaNs -> 0 too (same imputation convention)

    full = statlib.erank(mat_z)
    mat_partial = _partial_out_bl1(mat_z, y_z)
    partial = statlib.erank(mat_partial)

    # leading right singular vector (checkpoint loadings) -> |cos| with z(BL1_easy)
    if mat_z.shape[0] >= 2 and mat_z.shape[1] >= 2:
        _u, _s, vt = np.linalg.svd(mat_z, full_matrices=False)
        v1 = vt[0]
        denom = (np.linalg.norm(v1) * np.linalg.norm(y_z)) or 1.0
        cos_ckpt_bl1 = abs(float(np.dot(v1, y_z) / denom)) if denom else float("nan")
    else:
        cos_ckpt_bl1 = float("nan")

    return {
        "n_candidates": len(cands), "n_checkpoints": len(tags), "n_imputed": n_imputed,
        "candidates": cands, "checkpoints": tags,
        "erank_full": {"erank_entropy": full["erank_entropy"], "erank_participation": full["erank_participation"],
                        "singular_values": full["singular_values"], "leading_left_loadings": full["leading_left"]},
        "erank_partial_BL1": {"erank_entropy": partial["erank_entropy"],
                               "erank_participation": partial["erank_participation"],
                               "singular_values": partial["singular_values"],
                               "leading_left_loadings": partial["leading_left"]},
        "leading_eigenvector_loading_pattern": dict(zip(cands, full["leading_left"])) if full["leading_left"] else {},
        "abs_cos_leading_right_singvec_vs_zBL1": cos_ckpt_bl1,
        "spearman_matrix": _spearman_matrix(mat_raw, cands),
    }


def run_s3_3(prereg: dict, screen_table: dict) -> dict:
    panel = list(screen_table.get("panel", []))
    rows = screen_table.get("rows", [])
    bl1 = {}
    for b in screen_table.get("bars", []):
        if b.get("bar") == "BL1_easy" and b.get("tag") not in bl1:
            bl1[b["tag"]] = b.get("value")

    full_panel_block = _rank_block(rows, CANDIDATES, panel, bl1)

    tierA_block = _rank_block(rows, sorted(TIER_A_CANDS), panel, bl1)

    # complete-Tier-B-coverage: checkpoints where EVERY candidate (incl. Tier-B) is finite
    idx = {(r["tag"], r["candidate"]): r["value"] for r in rows}
    complete_tags = [t for t in panel
                     if all(idx.get((t, c)) is not None and np.isfinite(idx[(t, c)]) for c in CANDIDATES)]
    if len(complete_tags) >= 2:
        complete_block = _rank_block(rows, CANDIDATES, complete_tags, bl1)
    else:
        complete_block = {"note": f"only {len(complete_tags)} checkpoints have complete Tier-B coverage "
                                   f"(need >=2 for SVD); block skipped", "n_checkpoints": len(complete_tags)}

    ent = full_panel_block["erank_full"]["erank_entropy"]
    cos = full_panel_block["abs_cos_leading_right_singvec_vs_zBL1"]
    if np.isfinite(ent) and np.isfinite(cos) and ent <= 1.5 and cos >= 0.8:
        verdict = "P1-consistent: one coordinate, BL1-aligned"
    elif np.isfinite(ent) and np.isfinite(cos):
        verdict = (f"P1 NOT supported by the rank structure: erank_entropy={ent:.3f} "
                   f"(threshold <=1.5), |cos(leading ckpt singvec, z(BL1_easy))|={cos:.3f} (threshold >=0.8)")
    else:
        verdict = "erank/cos not computable (insufficient finite data)"

    return {
        "utc": utc_now(),
        "full_panel_all_candidates": full_panel_block,
        "tier_A_only_full_panel": tierA_block,
        "complete_tierB_coverage": complete_block,
        "verdict": verdict,
    }


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=WS / "results")
    ap.add_argument("--logs-dir", type=Path, default=WS / "logs")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    results_dir = args.results_dir.resolve()
    logs_dir = args.logs_dir.resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.add(logs_dir / "prescreen.log", rotation="10 MB", level="DEBUG")

    # FIRST statement of business: harden + self-test the shim before trusting it.
    logger.info("running OpenAudit self-test (pathlib / numpy / builtins.open / io.open / os.open)")
    st = self_test(logs_dir)
    st_path = results_dir / "s3_audit_selftest.json"
    st_path.parent.mkdir(parents=True, exist_ok=True)
    st_path.write_text(json.dumps(st, indent=1))
    logger.info(f"self-test PASS={st['PASS']} -> {st_path}")
    if not st["PASS"]:
        raise SystemExit("OpenAudit self-test FAILED -- refusing to run S3 with an unproven audit shim")

    for name in ("prescreen.json", "rank_analysis.json"):
        p = results_dir / name
        if p.exists() and not args.force:
            raise SystemExit(f"refusing to overwrite existing {p} (pass --force)")

    audit_log = logs_dir / "s3_open_audit.txt"
    with OpenAudit(audit_log, forbidden_substrings=FORBIDDEN) as audit:
        prereg = json.loads((results_dir / "prereg.json").read_text())
        screen_table = json.loads((results_dir / "screen_table.json").read_text())
        prereg["operationalisation_seed"] = prereg.get("f_selection_rule_verbatim", {}) \
            .get("operationalisation", {}).get("bootstrap", {}).get("seed", 20260922)

        logger.info(f"S3.2 pre-screen over {len(screen_table.get('panel', []))} panel rows")
        prescreen_result = run_s3_2(prereg, screen_table)
        logger.info(f"S3.2: dropped={prescreen_result['n_dropped']} kept={prescreen_result['n_kept']} "
                    f"not_evaluable={prescreen_result['n_not_evaluable']}")

        logger.info("S3.3 effective rank")
        rank_result = run_s3_3(prereg, screen_table)
        logger.info(f"S3.3 verdict: {rank_result['verdict']}")

        digest1 = write_json(results_dir / "prescreen.json", prescreen_result)
        rec1 = chain_append(results_dir / "hashchain.jsonl", "S3a", results_dir / "prescreen.json", digest1)
        digest2 = write_json(results_dir / "rank_analysis.json", rank_result)
        rec2 = chain_append(results_dir / "hashchain.jsonl", "S3b", results_dir / "rank_analysis.json", digest2)
        logger.info(f"wrote prescreen.json {digest1[:16]} chain={rec1['stage']}")
        logger.info(f"wrote rank_analysis.json {digest2[:16]} chain={rec2['stage']}")

    if audit.violations:
        raise SystemExit(f"INV-3 VIOLATION during S3 main pass: {audit.violations}")
    logger.info(f"S3 open-audit clean: {len(audit.records)} opens recorded, 0 violations -> {audit_log}")


if __name__ == "__main__":
    main()
