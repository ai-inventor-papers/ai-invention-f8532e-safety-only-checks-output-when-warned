#!/usr/bin/env python3
"""S2.6: assemble results/screen_table.json from Tier-A + Tier-B per-checkpoint outputs.

Reads ONLY: results/panel.json, results/screen/tierA/*.json, results/screen/ckpt_*.json.
Never opens graded_truth / classification / aggregates / any sibling-artifact file (INV-1/INV-3).

Implements SPEC_tail.md S2.6:
  - the 15 REGISTERED candidate scalars (W1..W8, G1..G4, A1(=A1_joint), A2, A3)
  - A1_joint = PC1 of z-scored (A1_prior, A1_slope) across screen-panel rows with both finite,
    loading fixed on the screen panel, oriented so the A1_prior loading > 0; A1_prior missing
    everywhere -> A1 = A1_slope (flagged "A1_prior_missing_everywhere")
  - W7c fallback into the W7 slot when a row's Tier-B W7 is NOT_RUN/missing (flagged "W7_is_W7c")
  - "N/A" strings (never 0) for k-curve points that were not computed
  - a coverage table, a bars table (every tierA bar + every Tier-B bar), and sub-columns.

CLI:
    .venv_gpu/bin/python src/assemble_screen.py [--results-dir DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import canonical_json, chain_append, sha256_text, utc_now, write_json  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
# the DEBUG file sink is added inside main() once --logs-dir is known (keeps synthetic-test
# runs isolated to WS/tests_tmp/ instead of always writing into the shared WS/logs/).

# The 15 registered candidate scalars, in prereg d_candidates order.
CANDIDATES = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "G1", "G2", "G3", "G4", "A1", "A2", "A3"]
TIER_A_ONLY = {"G1", "G2", "G3", "G4", "A3"}          # read straight from results/screen/tierA/<tag>.json
TIER_B_ONLY = {"A2", "W1", "W2", "W3", "W4", "W5", "W6", "W8"}  # read from results/screen/ckpt_<tag>.json
# A1 and W7 are handled specially (joint PCA / W7c fallback).

READ_BAND_CANDS = {"G1", "G2", "G3", "G4", "A1", "A3"}   # scored at b*_read
WRITE_BAND_CANDS = {"W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "A2"}  # scored at b*_write

# Best-effort item counts per candidate (documented simplification; see
# results/proposed_amendments_tail.json -- the prereg does not give a single
# canonical "n_prompts" definition per candidate for this summary table).
# distinct prompts each REGISTERED candidate forwards (fit + scoring folds; prereg amendment A4)
N_PROMPTS = {
    "G1": 32, "G2": 32, "G3": 32, "G4": 32, "A3": 170,   # A3: S32 + the 160 HARD rows (22 overlap)
    "A1": 97, "A2": 11, "W1": 32, "W2": 32, "W3": 32, "W4": 32, "W5": 32,   # A1: S32 + 64 c11 + contentless
    "W6": 32, "W7": 32, "W8": 32,                                           # A2: 10 plain-benign + contentless
}


def load_panel(results_dir: Path) -> dict:
    p = results_dir / "panel.json"
    if not p.exists():
        raise FileNotFoundError(f"missing {p}")
    return json.loads(p.read_text())


def load_tierA(results_dir: Path) -> dict[str, dict]:
    out = {}
    d = results_dir / "screen/tierA"
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            rec = json.loads(f.read_text())
        except json.JSONDecodeError:
            logger.warning(f"skip unreadable tierA file {f}")
            continue
        tag = rec.get("tag", f.stem)
        out[tag] = rec
    return out


def load_ckpt(results_dir: Path) -> dict[str, dict]:
    out = {}
    d = results_dir / "screen"
    if not d.exists():
        return out
    for f in sorted(d.glob("ckpt_*.json")):
        try:
            rec = json.loads(f.read_text())
        except json.JSONDecodeError:
            logger.warning(f"skip unreadable ckpt file {f}")
            continue
        tag = rec.get("tag", f.stem[len("ckpt_"):])
        out[tag] = rec
    return out


def _na_if_missing(v: Any) -> Any:
    """Never a silent 0: a genuinely-not-computed k-curve point is the string 'N/A'."""
    if v is None:
        return "N/A"
    return v


def build_k_curve(cand: str, tierA_row: dict | None, ckpt_row: dict | None) -> dict | str:
    if cand in TIER_A_ONLY or cand == "A1":
        src_key = "A1_slope" if cand == "A1" else cand
        if tierA_row is None:
            return "N/A"
        kc = tierA_row.get("k_curve", {}).get(src_key)
        if kc is None:
            return "N/A"
        return {k: _na_if_missing(v) for k, v in kc.items()}
    # Tier-B sourced: SPEC_tierB only registers k=32; other points are N/A by construction.
    if ckpt_row is None:
        return "N/A"
    val = ckpt_row.get("registered", {}).get(cand)
    return {"0": "N/A", "4": "N/A", "8": "N/A", "16": "N/A", "32": _na_if_missing(val), "pool": "N/A"}


def build_stability(cand: str, tierA_row: dict | None, ckpt_row: dict | None) -> Any:
    src_key = "A1_slope" if cand == "A1" else cand
    draws_out = []
    if tierA_row is not None:
        for d in tierA_row.get("stability", {}).get("draws", []):
            if src_key in d.get("values", {}):
                draws_out.append({k: d[k] for k in ("prompt_draw", "fold_seed", "band_offset") if k in d}
                                  | {"value": d["values"][src_key]})
    if ckpt_row is not None:
        for d in ckpt_row.get("stability", {}).get("draws", []):
            if cand in d.get("values", {}):
                draws_out.append({k: d[k] for k in ("prompt_draw", "fold_seed", "band_offset") if k in d}
                                  | {"value": d["values"][cand]})
    if not draws_out:
        return "N/A"
    return draws_out


def flatten_bars(bars: dict) -> list[dict]:
    """Turn a (possibly nested) bars dict into a flat list of {bar, value[, meta]}."""
    out = []
    skip_top = {"tag", "dir", "provenance", "L", "availability"}
    for k, v in bars.items():
        if k in skip_top or k.endswith("_meta"):
            continue
        meta = bars.get(f"{k}_meta")
        if isinstance(v, dict):
            for kk, vv in v.items():
                if isinstance(vv, (int, float, str, bool)) or vv is None:
                    out.append({"bar": f"{k}.{kk}", "value": vv, "meta": meta})
        elif isinstance(v, (int, float, str, bool)) or v is None:
            out.append({"bar": k, "value": v, "meta": meta})
    return out


def compute_a1_joint(rows: list[str], tierA: dict, ckpt: dict) -> tuple[dict[str, float | None], dict, list[str]]:
    """PC1 of z-scored (A1_prior, A1_slope) across SCREEN-panel rows with both finite.

    Loading is fixed on this (screen-panel) computation and oriented so the
    A1_prior loading is positive. Returns {tag: A1_joint or None}, the loading
    record, and a list of global flags.
    """
    flags: list[str] = []
    prior = {}
    slope = {}
    for tag in rows:
        a_row = tierA.get(tag)
        if a_row is not None:
            v = a_row.get("registered", {}).get("A1_slope")
            if v is not None and np.isfinite(v):
                slope[tag] = float(v)
        c_row = ckpt.get(tag)
        if c_row is not None:
            v = c_row.get("registered", {}).get("A1_prior")
            if v is not None and np.isfinite(v):
                prior[tag] = float(v)

    both = [t for t in rows if t in prior and t in slope]
    loading_rec = {"n_both_finite": len(both), "tags_used": both}

    if not prior:
        flags.append("A1_prior_missing_everywhere: A1 = A1_slope")
        values = {t: slope.get(t) for t in rows}
        loading_rec.update({"mode": "A1_slope_fallback", "loading": None})
        return values, loading_rec, flags

    if len(both) < 3:
        flags.append(f"A1_joint: only {len(both)} panel rows have both A1_prior and A1_slope finite; "
                      f"falling back to A1_slope everywhere")
        values = {t: slope.get(t) for t in rows}
        loading_rec.update({"mode": "A1_slope_fallback_insufficient_n", "loading": None})
        return values, loading_rec, flags

    P = np.array([prior[t] for t in both], dtype=float)
    S = np.array([slope[t] for t in both], dtype=float)
    Pz = (P - P.mean()) / (P.std(ddof=0) or 1.0)
    Sz = (S - S.mean()) / (S.std(ddof=0) or 1.0)
    M = np.column_stack([Pz, Sz])  # (n, 2): columns = (A1_prior, A1_slope)
    u, s, vt = np.linalg.svd(M - M.mean(axis=0), full_matrices=False)
    loading = vt[0]  # (2,) loading on (A1_prior_z, A1_slope_z)
    if loading[0] < 0:
        loading = -loading
    loading_rec.update({
        "mode": "pc1_joint",
        "loading_A1_prior": float(loading[0]),
        "loading_A1_slope": float(loading[1]),
        "explained_var_ratio": float((s[0] ** 2) / float((s ** 2).sum())) if s.sum() else None,
        "prior_mean": float(P.mean()), "prior_sd": float(P.std(ddof=0)),
        "slope_mean": float(S.mean()), "slope_sd": float(S.std(ddof=0)),
    })

    values: dict[str, float | None] = {}
    for t in rows:
        if t in prior and t in slope:
            pz = (prior[t] - loading_rec["prior_mean"]) / (loading_rec["prior_sd"] or 1.0)
            sz = (slope[t] - loading_rec["slope_mean"]) / (loading_rec["slope_sd"] or 1.0)
            values[t] = float(loading[0] * pz + loading[1] * sz)
        elif t in slope:
            values[t] = None  # A1_prior missing for this row only -> no joint score (reported via coverage)
        else:
            values[t] = None
    return values, loading_rec, flags


def assemble(results_dir: Path) -> dict:
    panel = load_panel(results_dir)
    tierA = load_tierA(results_dir)
    ckpt = load_ckpt(results_dir)

    panel_tags = list(panel.get("included", []))
    logger.info(f"panel: {len(panel_tags)} included tags; tierA files={len(tierA)}; ckpt files={len(ckpt)}")

    a1_values, a1_loading, a1_flags = compute_a1_joint(panel_tags, tierA, ckpt)

    rows = []
    bars_out = []
    coverage: dict[str, dict] = {c: {"n_panel_finite": 0, "n_tierB_missing": 0, "reasons": []} for c in CANDIDATES}
    subcolumns = []

    all_tags = list(dict.fromkeys(panel_tags + [t for t in tierA if t not in panel_tags]))
    for tag in all_tags:
        a_row = tierA.get(tag)
        c_row = ckpt.get(tag)
        in_panel = tag in panel_tags

        if a_row is not None:
            for bar in flatten_bars(a_row.get("bars", {})):
                bars_out.append({"tag": tag, **bar})
        if c_row is not None:
            for bar in flatten_bars(c_row.get("bars", {})):
                bars_out.append({"tag": tag, **bar})

        for cand in CANDIDATES:
            flags: list[str] = []
            censored = False
            value = None
            tier = None
            band = None

            if cand in TIER_A_ONLY:
                tier = "A"
                if a_row is not None:
                    value = a_row.get("registered", {}).get(cand)
                    censored = bool(a_row.get("censored", {}).get(cand, False))
                    flags += a_row.get("flags", {}).get(cand, []) or []
                    band = a_row.get("bstar_read")
                else:
                    coverage[cand]["reasons"].append(f"{tag}: no tierA file")
            elif cand in TIER_B_ONLY:
                tier = "B"
                if c_row is not None and c_row.get("status") == "OK":
                    value = c_row.get("registered", {}).get(cand)
                    censored = bool(c_row.get("censored", {}).get(cand, False))
                    flags += c_row.get("flags", {}).get(cand, []) or []
                    band = c_row.get("bstar", {}).get("write")
                elif c_row is not None:
                    flags.append(f"tierB status={c_row.get('status')}")
                    coverage[cand]["n_tierB_missing"] += 1
                else:
                    coverage[cand]["n_tierB_missing"] += 1
                    coverage[cand]["reasons"].append(f"{tag}: no ckpt file (Tier B not run)")
            elif cand == "A1":
                tier = "A+B"
                value = a1_values.get(tag)
                band = a_row.get("bstar_read") if a_row is not None else None
                if value is None and a_row is not None:
                    # fell back or missing prior for this row; report A1_slope for continuity
                    value = a_row.get("registered", {}).get("A1_slope")
                    flags.append("A1_prior_missing_this_row: reported A1_slope")
            elif cand == "W7":
                tier = "B"
                c_val = None
                if c_row is not None and c_row.get("status") == "OK":
                    c_val = c_row.get("registered", {}).get("W7")
                if c_val is not None:
                    value = c_val
                    band = c_row.get("bstar", {}).get("write")
                elif a_row is not None:
                    value = a_row.get("registered", {}).get("W7c")
                    flags.append("W7_is_W7c")
                    tier = "A (W7c fallback)"
                    band = a_row.get("bstar_read")
                    coverage[cand]["n_tierB_missing"] += 1
                    why = "Tier-B W7 NOT_RUN" if (c_row is not None) else "no ckpt file (Tier B not run)"
                    coverage[cand]["reasons"].append(f"{tag}: {why} -> W7c fallback")
                else:
                    coverage[cand]["n_tierB_missing"] += 1
                    coverage[cand]["reasons"].append(f"{tag}: neither Tier-B W7 nor Tier-A W7c available")

            if value is not None and np.isfinite(value) and in_panel:
                coverage[cand]["n_panel_finite"] += 1

            rows.append({
                "tag": tag, "candidate": cand, "value": (float(value) if value is not None else None),
                "tier": tier, "censored": censored, "flags": flags, "band": band,
                "n_prompts": N_PROMPTS.get(cand), "k_curve": build_k_curve(cand, a_row, c_row),
                "stability": build_stability(cand, a_row, c_row),
            })

        # sub-columns
        if a_row is not None:
            subcolumns.append({"tag": tag, "subcolumn": "A1_slope", "value": a_row.get("registered", {}).get("A1_slope")})
            subcolumns.append({"tag": tag, "subcolumn": "W7c", "value": a_row.get("registered", {}).get("W7c")})
            subcolumns.append({"tag": tag, "subcolumn": "W7c_tok1", "value": a_row.get("registered", {}).get("W7c_tok1")})
            subcolumns.append({"tag": tag, "subcolumn": "G4_ratio", "value": a_row.get("registered", {}).get("G4_ratio")})
            subcolumns.append({"tag": tag, "subcolumn": "A3_sd", "value": a_row.get("registered", {}).get("A3_sd")})
        if c_row is not None and c_row.get("status") == "OK":
            subcolumns.append({"tag": tag, "subcolumn": "A1_prior", "value": c_row.get("registered", {}).get("A1_prior")})
            # W7_strict: the INTERVENTION-only W7 (None where Tier B did not run), reported beside the
            # registered W7 slot whose prereg rule lets W7c carry rows without an intervention pass.
            subcolumns.append({"tag": tag, "subcolumn": "W7_strict", "value": c_row.get("registered", {}).get("W7")})
            subcolumns.append({"tag": tag, "subcolumn": "A2_cos", "value": c_row.get("registered", {}).get("A2_cos")})
            subcolumns.append({"tag": tag, "subcolumn": "A2_mag", "value": c_row.get("registered", {}).get("A2_mag")})
            w2_raw = None
            curves = c_row.get("curves", {})
            if "W2_ladder" in curves:
                w2_raw = curves.get("W2_order")
            subcolumns.append({"tag": tag, "subcolumn": "W2_raw", "value": w2_raw})

    table = {
        "utc": utc_now(),
        "panel": panel_tags,
        "blocks": panel.get("blocks", {}),
        "rows": rows,
        "bars": bars_out,
        "subcolumns": subcolumns,
        "a1_joint_loading": {**a1_loading, "flags": a1_flags},
        "coverage": coverage,
        "n_tierA_files": len(tierA),
        "n_tierB_files": len(ckpt),
        "n_tierB_ok": sum(1 for v in ckpt.values() if v.get("status") == "OK"),
    }
    return table


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=WS / "results")
    ap.add_argument("--logs-dir", type=Path, default=WS / "logs")
    ap.add_argument("--force", action="store_true", help="overwrite an existing screen_table.json")
    args = ap.parse_args()

    logs_dir = args.logs_dir.resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.add(logs_dir / "assemble_screen.log", rotation="10 MB", level="DEBUG")

    results_dir = args.results_dir.resolve()
    out_path = results_dir / "screen_table.json"
    if out_path.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing {out_path} (pass --force)")

    logger.info(f"assemble_screen: results_dir={results_dir}")
    table = assemble(results_dir)
    digest = write_json(out_path, table)
    chain_path = results_dir / "hashchain.jsonl"
    rec = chain_append(chain_path, "S2", out_path, digest)
    logger.info(f"wrote {out_path} sha256={digest[:16]} chain={rec}")
    logger.info(f"rows={len(table['rows'])} bars={len(table['bars'])} subcolumns={len(table['subcolumns'])}")


if __name__ == "__main__":
    main()
