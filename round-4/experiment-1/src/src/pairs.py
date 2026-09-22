"""CLI: paired prompt bootstrap over a pairs json (spec section 5, 7).

    python src/pairs.py --pairs <json> --B 1000 --out WS/results/scores

Input pairs json: a list of
    {pair_id, parent_tag, parent_dir, child_tag, child_dir, parent_repo, child_repo,
     n5_paths (optional: {p1,p2,p3} -> array paths)}

Writes (all under --out, default WS/results/scores):
    ckpt_<tag>.json    per-checkpoint full-data values, null_sd, B7/regex/AMS_T1, l_star, k-curve
    pairs_long.json    one row per (pair, candidate): Delta, CI, CI_excludes_0, |Delta|/nullSD,
                        expected sign, observed sign, MDE, observed class, n_valid_draws
    kcurves.json        k-curve summaries per checkpoint (N1,N2,N3,N6,N7,BL1_easy)
    timing.json         measured ms/(checkpoint,draw) and the projected wall time
    cache/<tag>.npz     per-checkpoint per-draw candidate arrays (deletable; resumability)

ORDER RULE (frozen for this deliverable): per-checkpoint values are computed for whichever
checkpoints appear in --pairs; the CALLER is responsible for only ever passing the 3 T0
checkpoints and identity pairs until told otherwise (see specs/scoring_spec.md section 8's
restriction note). This script does not itself special-case checkpoint identities.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
import ncands as nc  # noqa: E402

RESULTS = SRC.parent / "results"

# candidates that are SCALAR per (checkpoint, draw) and get the full paired-bootstrap treatment
BOOT_CANDIDATES = (
    "N1", "N2", "N3", "F_clust_raw", "N4_onset", "N4_peak_frac", "N4_width", "N6", "N7", "N8",
    "N9", "N9_tok1", "N10", "N11", "C4", "C7", "C13", "C13_peak_d",
    "BL1_easy", "BL1_hard", "BL1_truelogit", "BL1_truelogit_hard",
)
# candidates constant across draws (weights-only / card-text-only): CI == [Delta, Delta]
CONSTANT_CANDIDATES = ("B7", "B7_nullproj", "regex", "regex_namefree")


def jload(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def jdump(obj, p: Path):
    p.parent.mkdir(parents=True, exist_ok=True)

    def clean(o):
        if isinstance(o, float):
            return None if (np.isnan(o) or np.isinf(o)) else o
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, np.generic):
            return clean(o.item())
        if isinstance(o, np.ndarray):
            return clean(o.tolist())
        return o

    tmp = Path(str(p) + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(clean(obj), f, ensure_ascii=False, indent=1)
    tmp.replace(p)


def build_global_draws(B: int, seed: int) -> list[dict]:
    """ONE global seeded list of draws, reused for EVERY pair (spec section 5)."""
    stim = nc.load_stimuli()
    strat_full = np.array([f"{stim.sid[i]}|{stim.y[i]}|{stim.source[i]}" for i in range(256)])
    draws = []
    for b in range(B):
        rng = np.random.default_rng(seed * 100003 + b)
        w_stim = nc.stratified_bootstrap_weights(strat_full, rng)
        draws.append({"w_stim": w_stim, "seed": seed * 100003 + b})
    return draws


def load_ckpt(tag: str, dir_: str) -> nc.Ckpt:
    ck = nc.Ckpt.load(tag, Path(dir_))
    nc.precompute(ck)
    return ck


def per_ckpt_bundle(
    ck: nc.Ckpt, draws: list[dict], repo: Optional[str], n_null: int, null_seed: int,
    do_kcurve: bool,
) -> dict:
    """Full-data values, null_sd, B7/regex/AMS_T1 (once), then values() at every global draw."""
    stim = nc.load_stimuli()
    full = nc.values(ck)
    b7 = nc.b7_values(ck)
    regex = nc.card_regex_baseline(repo) if repo else {"regex": nc.NOT_AVAILABLE, "regex_namefree": nc.NOT_AVAILABLE}
    nsd = nc.null_sd(ck, n_draws=n_null, seed=null_seed)

    ams_strata = nc.ams_prompt_strata()
    ams_t1_full = nc.ams_t1_values(ck)

    # N5_invariance (amendment: EVERY checkpoint dir with >=1 of A_prompt_p1/p2/p3, not parents
    # only): full-data N1/l_star/nullSD_N1 already computed above -- no extra prompt-level work.
    n5_arrays = ck.n5_perturbation_arrays()
    n5 = (nc.n5_invariance(ck, full["N1_l_star"], full["N1"], nsd.get("N1", float("nan")),
                            perturbation_paths=n5_arrays)
          if n5_arrays else nc.NOT_AVAILABLE)

    draw_vals: list[dict] = []
    draw_ams: list[Any] = []
    for d in draws:
        v = nc.values(ck, w_stim=d["w_stim"])
        draw_vals.append(v)
        if ams_strata is not None and ck.A_ams is not None:
            rng = np.random.default_rng(d["seed"] + 555001)
            w_ams = nc.stratified_bootstrap_weights(ams_strata, rng)
            draw_ams.append(nc.ams_t1_values(ck, w_ams=w_ams))
        else:
            draw_ams.append(nc.NOT_AVAILABLE)

    kcurve = nc.k_curve_summary(ck, n_seeds=20) if do_kcurve else None

    return {
        "tag": ck.tag, "dir": str(ck.dir), "L": ck.L, "d": ck.d, "provenance": ck.provenance,
        "availability": ck.availability, "repo": repo,
        "values_full": {k: v for k, v in full.items() if not str(k).startswith("_") or k == "_d_l_curve"},
        "null_sd": nsd, "B7": b7, "regex": regex,
        "AMS_T1_full": ams_t1_full, "N5": n5,
        "N1_l_star_full": full.get("N1_l_star"), "N2_l_star_full": full.get("N2_l_star"),
        "kcurve": kcurve,
        "_draw_vals": draw_vals, "_draw_ams": draw_ams,   # kept in-memory for pairs.py, not written raw
    }


def cache_path(out: Path, tag: str) -> Path:
    return out / "cache" / f"{tag}.npz"


def save_cache(out: Path, tag: str, draw_vals: list[dict]) -> None:
    keys = sorted({k for v in draw_vals for k in v if not str(k).startswith("_") and isinstance(v.get(k), (int, float))})
    curve_len = len(draw_vals[0].get("_d_l_curve", [])) if draw_vals else 0
    arrs = {k: np.array([float(v.get(k, np.nan)) if isinstance(v.get(k), (int, float)) else np.nan
                          for v in draw_vals], dtype=np.float64) for k in keys}
    if curve_len:
        arrs["_d_l_curve"] = np.array([v.get("_d_l_curve", [np.nan] * curve_len) for v in draw_vals], dtype=np.float64)
    p = cache_path(out, tag)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, **arrs)


def pair_row(cand: str, parent_full: float, child_full: float, deltas_b: np.ndarray,
             null_sd_parent: float, null_sd_child: float, expected_sign: int,
             hc_sign: int = 1) -> dict:
    deltas_b = deltas_b[np.isfinite(deltas_b)]
    n_valid = int(deltas_b.size)
    if n_valid == 0:
        return {"candidate": cand, "Delta": None, "ci_lo": None, "ci_hi": None,
                "ci_excludes_0": None, "se_boot": None, "mde": None,
                "abs_delta_over_nullSD_child": None, "abs_delta_over_nullSD_parent": None,
                "observed_sign": None, "expected_sign": None, "parent_value": parent_full,
                "child_value": child_full, "n_valid_draws": 0}
    delta_full = (child_full - parent_full) if (np.isfinite(child_full) and np.isfinite(parent_full)) else float("nan")
    ci_lo, ci_hi = float(np.percentile(deltas_b, 2.5)), float(np.percentile(deltas_b, 97.5))
    se_boot = float(deltas_b.std(ddof=1)) if n_valid >= 2 else float("nan")
    mde = 2.8 * se_boot if np.isfinite(se_boot) else float("nan")
    obs_sign = int(np.sign(delta_full)) if np.isfinite(delta_full) else None
    exp_sign = int(np.sign(hc_sign) * expected_sign) if expected_sign is not None else None
    return {
        "candidate": cand, "Delta": delta_full, "ci_lo": ci_lo, "ci_hi": ci_hi,
        "ci_excludes_0": bool(ci_lo > 0 or ci_hi < 0),
        "se_boot": se_boot, "mde": mde,
        "abs_delta_over_nullSD_child": (abs(delta_full) / null_sd_child
                                         if np.isfinite(null_sd_child) and null_sd_child > 1e-12 else None),
        "abs_delta_over_nullSD_parent": (abs(delta_full) / null_sd_parent
                                          if np.isfinite(null_sd_parent) and null_sd_parent > 1e-12 else None),
        "observed_sign": obs_sign, "expected_sign": exp_sign,
        "parent_value": parent_full if np.isfinite(parent_full) else None,
        "child_value": child_full if np.isfinite(child_full) else None,
        "n_valid_draws": n_valid,
    }


EXPECTED_SIGN_VS_HC = {
    "N1": -1, "N2": -1, "N3": -1, "N4_onset": 0, "N4_peak_frac": 0, "N4_width": 0, "N6": -1,
    "N7": -1, "N8": -1, "N9": -1, "N9_tok1": -1, "N10": 1, "N11": -1,
    "BL1_easy": -1, "BL1_hard": -1, "BL1_truelogit": -1, "BL1_truelogit_hard": -1,
    "C4": 1, "C7": -1, "C13": -1, "C13_peak_d": -1, "F_clust_raw": -1,
    "B7": 1, "B7_nullproj": 1, "regex": 1, "regex_namefree": 1,
    "N5_invariance": 0, "AMS_T1_sigma": -1, "AMS_T2_drift": 1,
}

# spec section 7 per-row fields, for every candidate row (BOOT_CANDIDATES, CONSTANT_CANDIDATES,
# and the ad-hoc AMS_T1_sigma/AMS_T2_drift/N5_invariance rows below) -- NOT_AVAILABLE/missing-data
# rows must still carry every field (as None), never omit them (spec section 7's "NaN/NOT_AVAILABLE
# are explicit strings/nulls, never zeros" + the CLI dry-run's check_h regression check).
_SPEC5_FIELDS = ("Delta", "ci_lo", "ci_hi", "ci_excludes_0", "se_boot", "mde",
                  "abs_delta_over_nullSD_child", "abs_delta_over_nullSD_parent",
                  "observed_sign", "expected_sign", "parent_value", "child_value", "n_valid_draws")


def _blank_row(cand: str, pid: str, note: Any) -> dict:
    row: dict[str, Any] = {"candidate": cand, "pair_id": pid, "note": note}
    row.update({k: None for k in _SPEC5_FIELDS})
    row["n_valid_draws"] = 0
    return row


def process_pair(pair: dict, bundles: dict[str, dict], done_ids: set, out: Path) -> list[dict]:
    pid = pair["pair_id"]
    if pid in done_ids:
        return []
    ptag, ctag = pair["parent_tag"], pair["child_tag"]
    pb, cb = bundles[ptag], bundles[ctag]
    rows = []

    n_draws = min(len(pb["_draw_vals"]), len(cb["_draw_vals"]))
    for cand in BOOT_CANDIDATES:
        pvals = np.array([pb["_draw_vals"][b].get(cand, np.nan) if isinstance(pb["_draw_vals"][b].get(cand), (int, float)) else np.nan
                           for b in range(n_draws)])
        cvals = np.array([cb["_draw_vals"][b].get(cand, np.nan) if isinstance(cb["_draw_vals"][b].get(cand), (int, float)) else np.nan
                           for b in range(n_draws)])
        deltas = cvals - pvals
        pf = pb["values_full"].get(cand, float("nan"))
        cf = cb["values_full"].get(cand, float("nan"))
        pf = pf if isinstance(pf, (int, float)) else float("nan")
        cf = cf if isinstance(cf, (int, float)) else float("nan")
        row = pair_row(cand, pf, cf, deltas, pb["null_sd"].get(cand, float("nan")),
                        cb["null_sd"].get(cand, float("nan")), EXPECTED_SIGN_VS_HC.get(cand))
        row["pair_id"] = pid
        rows.append(row)

    # N1_parentL: child's d_l_curve read at the PARENT's per-draw l_star (spec companion)
    pl_curve = [pb["_draw_vals"][b].get("_d_l_curve") for b in range(n_draws)]
    pl_lstar = [pb["_draw_vals"][b].get("N1_l_star") for b in range(n_draws)]
    cl_curve = [cb["_draw_vals"][b].get("_d_l_curve") for b in range(n_draws)]
    n1pl_parent = np.array([pl_curve[b][pl_lstar[b]] if pl_curve[b] is not None else np.nan for b in range(n_draws)])
    n1pl_child = np.array([cl_curve[b][pl_lstar[b]] if cl_curve[b] is not None and pl_lstar[b] < len(cl_curve[b]) else np.nan for b in range(n_draws)])
    deltas = n1pl_child - n1pl_parent
    pf_curve, pf_lstar = pb["values_full"].get("_d_l_curve"), pb.get("N1_l_star_full")
    cf_curve = cb["values_full"].get("_d_l_curve")
    pf = pf_curve[pf_lstar] if pf_curve is not None else float("nan")
    cf = cf_curve[pf_lstar] if cf_curve is not None and pf_lstar is not None and pf_lstar < len(cf_curve) else float("nan")
    row = pair_row("N1_parentL", pf, cf, deltas, pb["null_sd"].get("N1", float("nan")),
                    cb["null_sd"].get("N1", float("nan")), EXPECTED_SIGN_VS_HC.get("N1"))
    row["pair_id"] = pid
    rows.append(row)

    # constant (weights-only / card) candidates: no bootstrap, CI == [Delta, Delta]
    for cand in CONSTANT_CANDIDATES:
        pv, cv = pb["B7"].get(cand) if cand.startswith("B7") else pb["regex"].get(cand), None
        if cand.startswith("B7"):
            pv, cv = pb["B7"].get(cand), cb["B7"].get(cand)
        else:
            pv, cv = pb["regex"].get(cand), cb["regex"].get(cand)
        pv = pv if isinstance(pv, (int, float)) else float("nan")
        cv = cv if isinstance(cv, (int, float)) else float("nan")
        delta = cv - pv if (np.isfinite(pv) and np.isfinite(cv)) else float("nan")
        rows.append({"candidate": cand, "pair_id": pid, "Delta": delta if np.isfinite(delta) else None,
                     "ci_lo": delta if np.isfinite(delta) else None, "ci_hi": delta if np.isfinite(delta) else None,
                     "ci_excludes_0": bool(delta != 0) if np.isfinite(delta) else None,
                     "se_boot": 0.0, "mde": 0.0, "abs_delta_over_nullSD_child": None,
                     "abs_delta_over_nullSD_parent": None,
                     "observed_sign": int(np.sign(delta)) if np.isfinite(delta) else None,
                     "expected_sign": EXPECTED_SIGN_VS_HC.get(cand), "parent_value": pv if np.isfinite(pv) else None,
                     "child_value": cv if np.isfinite(cv) else None, "n_valid_draws": n_draws,
                     "note": "weights-only/card-only: constant across every prompt draw by construction"})

    # AMS_T1_sigma
    p_ams_full = pb["AMS_T1_full"]
    c_ams_full = cb["AMS_T1_full"]
    if isinstance(p_ams_full, dict) and isinstance(c_ams_full, dict):
        p_draws = np.array([d["AMS_T1_sigma"] if isinstance(d, dict) else np.nan for d in pb["_draw_ams"]])
        c_draws = np.array([d["AMS_T1_sigma"] if isinstance(d, dict) else np.nan for d in cb["_draw_ams"]])
        deltas = c_draws - p_draws
        row = pair_row("AMS_T1_sigma", p_ams_full["AMS_T1_sigma"], c_ams_full["AMS_T1_sigma"], deltas,
                        float("nan"), float("nan"), EXPECTED_SIGN_VS_HC.get("AMS_T1_sigma", -1))
        row["pair_id"] = pid
        rows.append(row)
    else:
        rows.append(_blank_row("AMS_T1_sigma", pid, nc.NOT_AVAILABLE))

    # AMS_T2_drift (pair-level, needs both A_ams arrays; computed once at full data, no bootstrap CI yet)
    t2 = nc.ams_t2_values(cb.get("_ckpt_obj"), pb.get("_ckpt_obj")) if ("_ckpt_obj" in cb and "_ckpt_obj" in pb) else nc.NOT_AVAILABLE
    if isinstance(t2, dict):
        row = _blank_row("AMS_T2_drift", pid, "full-data only; unsigned relative drift (>=0) -> the alarm is the "
                                               "package's own verify rule (fails iff any concept has direction "
                                               "similarity < 0.8 or drift > 0.2), not a CI")
        row["Delta"] = t2.get("AMS_T2_drift")
        row["expected_sign"] = EXPECTED_SIGN_VS_HC.get("AMS_T2_drift")
        row["ams_verified"] = t2.get("AMS_T2_verified")
        row["ams_alarm"] = (not bool(t2.get("AMS_T2_verified"))) if t2.get("AMS_T2_verified") is not None else None
        row["ams_mean_direction_similarity"] = t2.get("AMS_T2_mean_direction_similarity")
        rows.append(row)
    else:
        rows.append(_blank_row("AMS_T2_drift", pid, t2))

    # N12_DEFAULT_WEIGHTS (no screen-sibling survivor file exists at scoring time): per checkpoint and draw,
    # N12 = N1 / sd0_N1 + N7 / sd0_N7 with sd0 = that checkpoint's own shuffled-label null SD (fixed across draws)
    def _n12(bundle, vals):
        s1, s7 = bundle["null_sd"].get("N1", float("nan")), bundle["null_sd"].get("N7", float("nan"))
        a, b = vals.get("N1"), vals.get("N7")
        if not all(isinstance(x, (int, float)) and np.isfinite(x) for x in (s1, s7, a, b)) or s1 < 1e-12 or s7 < 1e-12:
            return float("nan")
        return a / s1 + b / s7
    p12 = np.array([_n12(pb, pb["_draw_vals"][b]) for b in range(n_draws)])
    c12 = np.array([_n12(cb, cb["_draw_vals"][b]) for b in range(n_draws)])
    row = pair_row("N12_DEFAULT_WEIGHTS", _n12(pb, pb["values_full"]), _n12(cb, cb["values_full"]), c12 - p12,
                   float("nan"), float("nan"), -1)
    row["pair_id"] = pid
    row["note"] = "N12 = z(N1) + z(N7), equal default weights (no survivor/weights file from the screen sibling)"
    rows.append(row)

    # N5_invariance pair delta (spec 3/amendment: p1/p2/p3 render-and-precision robustness of N1;
    # computed once per checkpoint at full data -- see per_ckpt_bundle -- so no prompt-bootstrap CI
    # on the delta itself yet, same status as AMS_T2_drift above).
    p_n5 = pb.get("N5")
    c_n5 = cb.get("N5")
    if isinstance(p_n5, dict) and isinstance(c_n5, dict):
        pv, cv = p_n5.get("N5_invariance"), c_n5.get("N5_invariance")
        row = _blank_row("N5_invariance", pid,
                       "per-checkpoint scalar (max over available p1/p2/p3 perturbations, in "
                       "nullSD_N1 units); no prompt-bootstrap CI on the pair delta yet")
        if isinstance(pv, (int, float)) and isinstance(cv, (int, float)):
            row["Delta"] = cv - pv
        row["parent_value"] = pv if isinstance(pv, (int, float)) else None
        row["child_value"] = cv if isinstance(cv, (int, float)) else None
        row["expected_sign"] = EXPECTED_SIGN_VS_HC.get("N5_invariance")
        rows.append(row)
    else:
        rows.append(_blank_row("N5_invariance", pid, nc.NOT_AVAILABLE))

    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--B", type=int, default=1000)
    ap.add_argument("--out", default=str(RESULTS / "scores"))
    ap.add_argument("--n-null", type=int, default=50)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-kcurve", action="store_true")
    ap.add_argument("--timing-only-checkpoints", type=int, default=0,
                     help="if >0, only run this many bootstrap draws (for the timing measurement in section 8f)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pairs = jload(Path(args.pairs))
    if isinstance(pairs, dict):
        pairs = pairs["pairs"]

    B = args.timing_only_checkpoints if args.timing_only_checkpoints else args.B
    draws = build_global_draws(B, args.seed)

    tags: dict[str, dict] = {}
    for p in pairs:
        tags[p["parent_tag"]] = {"dir": p["parent_dir"], "repo": p.get("parent_repo")}
        tags[p["child_tag"]] = {"dir": p["child_dir"], "repo": p.get("child_repo")}

    pairs_long_path = out / "pairs_long.json"
    existing_rows = jload(pairs_long_path) if pairs_long_path.exists() else []
    done_ids = {r["pair_id"] for r in existing_rows}

    timing = {"per_checkpoint": {}}
    bundles: dict[str, dict] = {}
    kcurves_out: dict[str, Any] = {}
    for tag, info in tags.items():
        t0 = time.time()
        ck = load_ckpt(tag, info["dir"])
        t_load = time.time() - t0
        t1 = time.time()
        bundle = per_ckpt_bundle(ck, draws, info.get("repo"), args.n_null, args.seed, not args.no_kcurve)
        bundle["_ckpt_obj"] = ck
        t_bundle = time.time() - t1
        bundles[tag] = bundle
        save_cache(out, tag, bundle["_draw_vals"])
        jdump({k: v for k, v in bundle.items() if not str(k).startswith("_")}, out / f"ckpt_{tag}.json")
        if bundle.get("kcurve") is not None:
            kcurves_out[tag] = bundle["kcurve"]
        timing["per_checkpoint"][tag] = {
            "load_s": t_load, "bundle_s": t_bundle, "n_draws": B,
            "ms_per_draw": (t_bundle / max(B, 1)) * 1000,
        }
        print(f"[{tag}] load {t_load:.2f}s, bundle {t_bundle:.2f}s ({(t_bundle / max(B, 1)) * 1000:.2f} ms/draw)",
              file=sys.stderr)

    new_rows = []
    for p in pairs:
        new_rows.extend(process_pair(p, bundles, done_ids, out))
    all_rows = existing_rows + new_rows
    jdump(all_rows, pairs_long_path)
    if kcurves_out:
        jdump(kcurves_out, out / "kcurves.json")

    ms_vals = [v["ms_per_draw"] for v in timing["per_checkpoint"].values()]
    timing["mean_ms_per_checkpoint_draw"] = float(np.mean(ms_vals)) if ms_vals else None
    timing["projected_wall_time_s_for_40_pairs_B1000"] = (
        float(np.mean(ms_vals)) / 1000.0 * 1000 * max(len({t for p in pairs for t in (p["parent_tag"], p["child_tag"])}), 1)
        if ms_vals else None
    )
    timing["note"] = ("projection assumes ~1 unique checkpoint per pair on average is an "
                       "UNDER-estimate for 40 real pairs sharing parents; see report for the real "
                       "per-checkpoint number and a corrected 40-pair/B=1000 projection")
    jdump(timing, out / "timing.json")
    print(json.dumps(timing, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
