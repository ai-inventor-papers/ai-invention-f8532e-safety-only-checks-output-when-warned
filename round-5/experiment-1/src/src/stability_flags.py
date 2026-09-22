#!/usr/bin/env python3
"""Registered stability verdicts, EXACTLY per results/prereg.json stability_C.unstable_rule:

    "signed candidates: a row is sign-unstable if < 80% of its draws share the registered
     sign; a candidate is UNSTABLE if > 20% of rows are sign-unstable.
     All candidates: RANK_UNSTABLE if the median over draws of Spearman(registered, draw)
     across rows < 0.5"

Sign rule applies only to SIGNED candidates (a bidirectional contrast). G1, G2, G4, W2, W3, W8,
A3 are positive-by-construction (an angle, a ratio, a CV, a censored ladder step) and report
RANK stability only, stated as such (no UNSTABLE / frac_rows_sign_unstable value).

Rank rule ("Spearman(registered, draw) across rows", median over draws): draws are grouped by
their exact (prompt_draw, fold_seed, band_offset) key; for every such key shared by >=3 panel
rows, Spearman(registered-value-vector, that-draw's-value-vector) is computed across those rows;
RANK_UNSTABLE iff the MEDIAN of these per-draw-key rho's < 0.5.

Sources: results/screen/tierA/*.json (`stability.draws[].values`) and
results/screen/ckpt_*.json (`stability.draws[].values`). A1's own stability is read off its
Tier-A component (A1_slope draws) -- see the "A1_note" in the output; A1_prior/A1_joint's
per-draw PCA is not reconstructed here (that would need re-fitting the PC1 loading on every
draw, out of scope for this diagnostic). W7's Tier-B draws are skipped by SPEC_tierB
("Skip W7 and patching" in the stability battery); when a row has none, its Tier-A W7c draws
are used as a proxy, flagged, mirroring the W7c freeze-time fallback.

CLI:
    .venv_gpu/bin/python src/stability_flags.py [--results-dir DIR] [--logs-dir DIR]
                                                 [--force] [--self-test]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import chain_append, utc_now, write_json  # noqa: E402
import statlib  # noqa: E402

CANDIDATES = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "G1", "G2", "G3", "G4", "A1", "A2", "A3"]
POSITIVE_BY_CONSTRUCTION = {"G1", "G2", "G4", "W2", "W3", "W8", "A3"}
SIGN_THRESHOLD = 0.80
CAND_UNSTABLE_ROW_FRAC = 0.20
RANK_THRESHOLD = 0.50

TIERA_KEY = {"G1": "G1", "G2": "G2", "G3": "G3", "G4": "G4", "A3": "A3", "A1": "A1_slope"}
CKPTB_KEY = {"A2": "A2", "W1": "W1", "W2": "W2", "W3": "W3", "W4": "W4", "W5": "W5", "W6": "W6",
             "W7": "W7", "W8": "W8"}


def load_dir(results_dir: Path, sub: str, prefix: str = "") -> dict[str, dict]:
    out = {}
    d = results_dir / sub
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        if prefix and not f.stem.startswith(prefix):
            continue
        try:
            rec = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        tag = rec.get("tag", f.stem[len(prefix):] if prefix else f.stem)
        out[tag] = rec
    return out


def _draws_for(row: dict | None, key: str) -> list[dict]:
    if row is None:
        return []
    out = []
    for d in row.get("stability", {}).get("draws", []):
        v = d.get("values", {}).get(key)
        if v is not None and np.isfinite(v):
            out.append({"prompt_draw": d.get("prompt_draw"), "fold_seed": d.get("fold_seed"),
                        "band_offset": d.get("band_offset"), "value": float(v)})
    return out


def gather_candidate(cand: str, tierA: dict[str, dict], ckpt: dict[str, dict],
                      panel: list[str]) -> tuple[dict[str, float], dict[str, list[dict]], list[str]]:
    """Returns (registered_by_tag, draws_by_tag, flags)."""
    flags = []
    registered: dict[str, float] = {}
    draws: dict[str, list[dict]] = {}

    if cand in TIERA_KEY:
        src_key = TIERA_KEY[cand]
        for tag in panel:
            row = tierA.get(tag)
            if row is None:
                continue
            reg = row.get("registered", {}).get(src_key)
            if reg is not None and np.isfinite(reg):
                registered[tag] = float(reg)
                draws[tag] = _draws_for(row, src_key)
        if cand == "A1":
            flags.append("A1 stability computed on its A1_slope (Tier-A) component only; "
                          "A1_joint/A1_prior per-draw PCA is not reconstructed here")
    elif cand == "W7":
        for tag in panel:
            crow = ckpt.get(tag)
            reg = crow.get("registered", {}).get("W7") if crow else None
            d = _draws_for(crow, "W7") if crow else []
            if not d:
                arow = tierA.get(tag)
                d = _draws_for(arow, "W7c")
                if d and reg is None and arow is not None:
                    reg = arow.get("registered", {}).get("W7c")
                if d:
                    flags.append(f"{tag}: no Tier-B W7 stability draws (skipped by SPEC_tierB) "
                                 f"-> used Tier-A W7c draws as a proxy")
            if reg is not None and np.isfinite(reg) and d:
                registered[tag] = float(reg)
                draws[tag] = d
    else:  # Tier-B candidates
        src_key = CKPTB_KEY[cand]
        for tag in panel:
            row = ckpt.get(tag)
            if row is None or row.get("status") != "OK":
                continue
            reg = row.get("registered", {}).get(src_key)
            if reg is not None and np.isfinite(reg):
                registered[tag] = float(reg)
                draws[tag] = _draws_for(row, src_key)

    return registered, draws, flags


def sign_rule(registered: dict[str, float], draws: dict[str, list[dict]]) -> dict:
    per_row = {}
    n_sign_unstable = 0
    n_rows = 0
    for tag, reg in registered.items():
        d = draws.get(tag, [])
        if not d:
            continue
        reg_sign = np.sign(reg)
        if reg_sign == 0:
            per_row[tag] = {"registered": reg, "n_draws": len(d), "frac_sign_agree": None,
                            "sign_unstable": None, "excluded": "registered value is exactly 0"}
            continue
        agree = sum(1 for x in d if np.sign(x["value"]) == reg_sign)
        frac = agree / len(d)
        unstable = frac < SIGN_THRESHOLD
        per_row[tag] = {"registered": reg, "n_draws": len(d), "frac_sign_agree": frac,
                        "sign_unstable": unstable}
        n_rows += 1
        if unstable:
            n_sign_unstable += 1
    frac_rows_unstable = (n_sign_unstable / n_rows) if n_rows else None
    unstable_cand = (frac_rows_unstable is not None) and (frac_rows_unstable > CAND_UNSTABLE_ROW_FRAC)
    return {"per_row": per_row, "n_rows_evaluable_for_sign": n_rows,
            "frac_rows_sign_unstable": frac_rows_unstable, "UNSTABLE": unstable_cand}


def rank_rule(registered: dict[str, float], draws: dict[str, list[dict]]) -> dict:
    # group all draws, across rows, by exact (prompt_draw, fold_seed, band_offset)
    by_key: dict[tuple, dict[str, float]] = {}
    for tag, dlist in draws.items():
        for d in dlist:
            key = (d["prompt_draw"], d["fold_seed"], d["band_offset"])
            by_key.setdefault(key, {})[tag] = d["value"]

    per_draw_rho = {}
    rhos = []
    for key, tag_vals in by_key.items():
        tags = [t for t in tag_vals if t in registered]
        if len(tags) < 3:
            continue
        reg_vec = [registered[t] for t in tags]
        draw_vec = [tag_vals[t] for t in tags]
        rho = statlib.spearman(reg_vec, draw_vec)["rho"]
        per_draw_rho[str(key)] = {"n_rows": len(tags), "rho": (rho if np.isfinite(rho) else None)}
        if np.isfinite(rho):
            rhos.append(rho)

    median_rho = float(np.median(rhos)) if rhos else None
    rank_unstable = (median_rho is not None) and (median_rho < RANK_THRESHOLD)
    return {"per_draw_key_rho": per_draw_rho, "n_draw_keys_evaluable": len(rhos),
            "median_rank_corr": median_rho, "RANK_UNSTABLE": rank_unstable}


def run_for_candidate(cand: str, tierA: dict, ckpt: dict, panel: list[str]) -> dict:
    registered, draws, flags = gather_candidate(cand, tierA, ckpt, panel)
    n_rows_with_draws = sum(1 for t in draws if draws[t])
    out = {"n_rows_with_draws": n_rows_with_draws, "flags": flags}
    rr = rank_rule(registered, draws)
    out.update(rr)
    if cand in POSITIVE_BY_CONSTRUCTION:
        out["sign_rule_applicable"] = False
        out["note"] = ("positive-by-construction candidate (angle/ratio/CV/censored step): the "
                       "prereg's sign rule does not apply; only rank stability is reported")
        out["frac_rows_sign_unstable"] = None
        out["UNSTABLE"] = None
        out["per_row"] = {t: {"registered": registered.get(t), "n_draws": len(draws.get(t, []))}
                          for t in registered}
    else:
        out["sign_rule_applicable"] = True
        sr = sign_rule(registered, draws)
        out["frac_rows_sign_unstable"] = sr["frac_rows_sign_unstable"]
        out["UNSTABLE"] = sr["UNSTABLE"]
        out["per_row"] = sr["per_row"]
        out["n_rows_evaluable_for_sign"] = sr["n_rows_evaluable_for_sign"]
    return out


# --------------------------------------------------------------------------- #
# unit tests on synthetic draws                                               #
# --------------------------------------------------------------------------- #


def run_unit_tests() -> dict:
    results = {}

    # sign rule: 5 rows, row A has 4/5 draws matching sign (80%, NOT unstable, >= threshold),
    # rows B,C,D,E each have 1/5 matching (20%, unstable) -> frac_rows_unstable = 4/5=0.8 > 0.2 -> UNSTABLE True
    registered = {"A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0, "E": 1.0}
    draws = {
        "A": [{"value": v, "prompt_draw": i, "fold_seed": 0, "band_offset": 0} for i, v in
              enumerate([1, 1, 1, 1, -1])],
        "B": [{"value": v, "prompt_draw": i, "fold_seed": 0, "band_offset": 0} for i, v in
              enumerate([-1, -1, -1, -1, 1])],
        "C": [{"value": v, "prompt_draw": i, "fold_seed": 0, "band_offset": 0} for i, v in
              enumerate([-1, -1, -1, -1, 1])],
        "D": [{"value": v, "prompt_draw": i, "fold_seed": 0, "band_offset": 0} for i, v in
              enumerate([-1, -1, -1, -1, 1])],
        "E": [{"value": v, "prompt_draw": i, "fold_seed": 0, "band_offset": 0} for i, v in
              enumerate([-1, -1, -1, -1, 1])],
    }
    sr = sign_rule(registered, draws)
    ok_sign = (sr["per_row"]["A"]["sign_unstable"] is False and sr["per_row"]["B"]["sign_unstable"] is True
               and abs(sr["frac_rows_sign_unstable"] - 0.8) < 1e-9 and sr["UNSTABLE"] is True)
    results["sign_rule"] = {"pass": bool(ok_sign), "detail": sr}

    # sign rule: all rows 100% agreement -> not unstable
    draws_stable = {t: [{"value": 1.0, "prompt_draw": i, "fold_seed": 0, "band_offset": 0} for i in range(5)]
                    for t in registered}
    sr2 = sign_rule(registered, draws_stable)
    ok_sign2 = sr2["frac_rows_sign_unstable"] == 0.0 and sr2["UNSTABLE"] is False
    results["sign_rule_stable_case"] = {"pass": bool(ok_sign2), "detail": sr2}

    # rank rule: registered perfectly tracked by every draw (same draw key across all rows) -> rho=1, median=1, not unstable
    reg2 = {"T1": 1.0, "T2": 2.0, "T3": 3.0, "T4": 4.0}
    draws2 = {t: [{"value": v, "prompt_draw": 0, "fold_seed": 0, "band_offset": 0}] for t, v in
              zip(reg2, [1.1, 2.1, 3.1, 4.1])}
    rr = rank_rule(reg2, draws2)
    ok_rank = rr["median_rank_corr"] == 1.0 and rr["RANK_UNSTABLE"] is False
    results["rank_rule_stable"] = {"pass": bool(ok_rank), "detail": rr}

    # rank rule: draws uncorrelated with registered (reversed rank) -> rho=-1, median=-1 < 0.5 -> RANK_UNSTABLE True
    draws3 = {t: [{"value": v, "prompt_draw": 0, "fold_seed": 0, "band_offset": 0}] for t, v in
              zip(reg2, [4.0, 3.0, 2.0, 1.0])}
    rr2 = rank_rule(reg2, draws3)
    ok_rank2 = rr2["median_rank_corr"] == -1.0 and rr2["RANK_UNSTABLE"] is True
    results["rank_rule_unstable"] = {"pass": bool(ok_rank2), "detail": rr2}

    results["ALL_PASS"] = bool(all(v["pass"] for v in results.values() if isinstance(v, dict) and "pass" in v))
    return results


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=WS / "results")
    ap.add_argument("--logs-dir", type=Path, default=WS / "logs")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    logs_dir = args.logs_dir.resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(logs_dir / "stability_flags.log", rotation="10 MB", level="DEBUG")

    if args.self_test:
        ut = run_unit_tests()
        logger.info(f"unit tests: ALL_PASS={ut['ALL_PASS']}")
        for k, v in ut.items():
            if isinstance(v, dict) and "pass" in v:
                logger.info(f"  {k}: {'PASS' if v['pass'] else 'FAIL'}")
        if not ut["ALL_PASS"]:
            raise SystemExit("stability_flags.py --self-test FAILED")
        return

    results_dir = args.results_dir.resolve()
    out_path = results_dir / "stability_flags.json"
    if out_path.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing {out_path} (pass --force)")

    panel_path = results_dir / "panel.json"
    panel = json.loads(panel_path.read_text()).get("included", []) if panel_path.exists() else []
    tierA = load_dir(results_dir, "screen/tierA")
    ckpt = load_dir(results_dir, "screen", prefix="ckpt_")
    if not panel:
        panel = sorted(set(tierA) | set(ckpt))
    logger.info(f"panel={len(panel)} tierA_files={len(tierA)} ckpt_files={len(ckpt)}")

    out = {"utc": utc_now(),
           "unstable_rule_source": "results/prereg.json stability_C.unstable_rule (verbatim, see module docstring)",
           "sign_threshold": SIGN_THRESHOLD, "cand_unstable_row_frac_threshold": CAND_UNSTABLE_ROW_FRAC,
           "rank_threshold": RANK_THRESHOLD, "positive_by_construction": sorted(POSITIVE_BY_CONSTRUCTION),
           "candidates": {}}
    for cand in CANDIDATES:
        rec = run_for_candidate(cand, tierA, ckpt, panel)
        out["candidates"][cand] = rec
        tag_str = ("UNSTABLE" if rec.get("UNSTABLE") else ("stable" if rec.get("UNSTABLE") is False else "n/a"))
        logger.info(f"{cand}: n_rows_with_draws={rec['n_rows_with_draws']} sign={tag_str} "
                    f"median_rank_corr={rec['median_rank_corr']} RANK_UNSTABLE={rec['RANK_UNSTABLE']}")

    digest = write_json(out_path, out)
    logger.info(f"wrote {out_path} sha256={digest[:16]}")


if __name__ == "__main__":
    main()
