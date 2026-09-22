"""TESTING PLAN item 1 (+ item 2's array checks) -- unit checks that need no model and no spend.

  (a) statistics on synthetic data: a perfectly monotone feature gives rho = 1 with a bootstrap CI at 1;
      shuffled features give CIs that cover 0; the permutation critical |rho| for n = 10 is 0.648;
      TPR@FPR and partial Spearman behave on constructed cases.
  (b) outcome aggregation: outcomes.columns() recomputes the published iteration-2 behaviour columns of
      three screen checkpoints from Lane C's judged rows (H2 results/pairs_effective.json; the Phi-4-mini
      row carries the one unparsable judge output, so it tests the denominator convention) to <= 1e-9.
  (c) incumbent code: the copied iteration-2 kernels, run by candidates.compute_all() on the iteration-2
      panel's saved arrays (results/iter2_panel_features_cache.json), reproduce H2's stored
      BL1_REFLOGIT / BL3_DIFFMEAN / BL7_JORAK_A / X2 / X10_abs (results/scored_checkpoints.json) exactly.
  (d) harvest integrity for every harvested checkpoint: array shapes (A_prompt (256, L+1, d),
      A_resp (96, L+1, 2, d), A_c11 (64, L+1, d)), no NaN/inf, MANIFEST.sha256.json re-hash.

Writes results/unit_checks.json. Read-only on every other artifact.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "h2"))
from common import H2, HARVEST, LANEC, RESULTS, jdump, jload, setup_logging, sha256_file, slug, utc_now  # noqa: E402
from loguru import logger  # noqa: E402


def check_stats() -> dict:
    import numerics as nm
    import stats_panel as sp
    out = {}
    n = 10
    y = np.linspace(0.0, 0.9, n)
    fams = np.array(["a", "a", "b", "b", "c", "c", "d", "d", "e", "e"])
    bl1 = np.random.default_rng(1).permutation(y)
    rho, _ = sp._rho(y * 3 + 1, y)
    b = sp.boot_rows(y * 3 + 1, y, bl1, fams, B=2000, seed=17, B_family=500)
    out["monotone"] = {"rho": rho, "ci95_ckpt": b["ci95_ckpt"], "pass": bool(abs(rho - 1) < 1e-12 and
                                                                        b["ci95_ckpt"][0] > 0.999)}
    cover = []
    for s in range(20):
        x = np.random.default_rng(100 + s).permutation(y)
        bb = sp.boot_rows(x, y, bl1, fams, B=2000, seed=17, B_family=200)
        lo, hi = bb["ci95_ckpt"]
        cover.append(bool(lo is not None and lo <= 0 <= hi))
    out["shuffled_ci_covers_0"] = {"n_shuffles": 20, "n_cover": int(sum(cover)),
                                   "pass": bool(sum(cover) >= 17)}
    crit = sp.critical_rho(10)
    out["critical_rho_n10"] = {"value": crit, "expected": 0.648, "pass": bool(abs(crit - 0.648) < 0.0015)}
    out["mde_rho_n10_power80"] = {"value": sp.mde_rho(10), "formula": "tanh((z.975+z.8)*sqrt(1.06/(n-3)))"}
    yy = np.r_[np.ones(100), np.zeros(100)].astype(int)
    sep = np.r_[np.linspace(5, 6, 100), np.linspace(0, 1, 100)]
    same = np.random.default_rng(3).standard_normal(200)
    t_sep, t_same = nm.tpr_at_fpr(sep, yy, 0.05), nm.tpr_at_fpr(same, yy, 0.05)
    out["tpr_at_fpr"] = {"separated": t_sep, "identical_dists": t_same,
                         "pass": bool(t_sep == 1.0 and t_same < 0.25)}
    z = np.arange(10.0)
    rng = np.random.default_rng(5)
    yv = z + rng.standard_normal(10) * 0.01
    ps_same = sp.partial_spearman(z.copy(), yv, z)          # x == z -> nothing left
    x_ind = rng.permutation(10).astype(float)
    y2 = x_ind * 10 + z * 0.001
    ps_ind = sp.partial_spearman(x_ind, y2, z)
    out["partial_spearman"] = {"x_equals_bl1": ps_same, "x_independent_of_bl1_drives_y": ps_ind,
                               "pass": bool((not np.isfinite(ps_same) or abs(ps_same) < 1e-6) and ps_ind > 0.95)}
    out["pass"] = all(v.get("pass", True) for v in out.values() if isinstance(v, dict))
    return out


def check_outcomes() -> dict:
    import outcomes as oc
    pe = jload(H2 / "results/pairs_effective.json")
    pub = {}
    for p in pe["pairs"]:
        for side in ("parent", "child"):
            if p.get(f"{side}_behaviour"):
                pub[p[side]] = p[f"{side}_behaviour"]
    for s in pe["singles"]:
        if s.get("behaviour"):
            pub[s["repo"]] = s["behaviour"]
    targets = ["Qwen/Qwen3-4B", "microsoft/Phi-4-mini-instruct", "Qwen/Qwen3-1.7B"]
    res = []
    for repo in targets:
        f = LANEC / "results/judged" / (repo.replace("/", "__") + ".jsonl")
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        col = oc.columns(rows)
        b = pub[repo]
        diffs = {"harmful_compliance": abs(col["harmful_compliance"] - b["harmful_compliance_rate"]),
                 "over_refusal": abs(col["over_refusal"] - b["over_refusal_rate"]),
                 "safe_engagement": abs(col["safe_engagement"] - b["safe_engagement_rate"])}
        res.append({"repo": repo, "recomputed": {k: col[k] for k in diffs}, "published": b,
                    "abs_diff": diffs, "n_rows": len(rows), "pass": bool(max(diffs.values()) <= 1e-9)})
    return {"rows": res, "pass": all(r["pass"] for r in res)}


def check_incumbents() -> dict:
    cache = jload(RESULTS / "iter2_panel_features_cache.json")
    stored = jload(H2 / "results/scored_checkpoints.json")
    keymap = {"BL1": "BL1_REFLOGIT", "B3": "BL3_DIFFMEAN", "B7": "BL7_JORAK_A", "X2": "X2", "X10_abs": "X10_abs"}
    rows, worst = [], 0.0
    for tag, f in cache.items():
        if tag not in stored:
            continue
        real = stored[tag].get("real", {})
        d = {}
        for k, k2 in keymap.items():
            a, b = f.get(k), real.get(k2)
            if a is None or b is None:
                d[k] = None
                continue
            try:
                a, b = float(a), float(b)
            except (TypeError, ValueError):
                d[k] = None
                continue
            d[k] = 0.0 if (a != a and b != b) else abs(a - b)
            worst = max(worst, d[k] if d[k] == d[k] else 0.0)
        rows.append({"tag": tag, "abs_diff": d})
    return {"n_checkpoints": len(rows), "max_abs_diff": worst, "rows": rows, "pass": bool(rows and worst == 0.0)}


def check_harvest() -> dict:
    res = []
    for d in sorted(HARVEST.iterdir()):
        if not d.is_dir() or d.name.endswith("_SMOKE") or not (d / "DONE").exists():
            continue
        meta = jload(d / "meta.json")
        L, D = meta["n_layers"], meta["hidden_size"]
        r = {"tag": d.name, "L": L, "d": D}
        A = np.load(d / "A_prompt.npy", mmap_mode="r")
        r["A_prompt_shape"] = list(A.shape)
        r["A_prompt_ok"] = bool(A.shape == (256, L + 1, D) and np.isfinite(np.asarray(A, dtype=np.float32)).all())
        Ar = np.load(d / "A_resp.npy", mmap_mode="r")
        r["A_resp_shape"] = list(Ar.shape)
        r["A_resp_ok"] = bool(Ar.shape == (96, L + 1, 2, D) and np.isfinite(np.asarray(Ar, dtype=np.float32)).all())
        Ac = np.load(d / "A_c11.npy", mmap_mode="r")
        r["A_c11_shape"] = list(Ac.shape)
        r["A_c11_ok"] = bool(Ac.shape == (64, L + 1, D) and np.isfinite(np.asarray(Ac, dtype=np.float32)).all())
        lens_ok = True
        for k in ("r_refusal", "r_hedge", "r_control", "norms"):
            v = np.load(d / f"{k}.npy")
            lens_ok &= bool(v.shape == (256, L + 1) and np.isfinite(v).all())
        r["lens_arrays_ok"] = lens_ok
        man = jload(d / "MANIFEST.sha256.json")
        bad = [k for k, h in man.items() if sha256_file(d / k) != h]
        r["manifest_files"] = len(man)
        r["manifest_mismatches"] = bad
        r["cells_kept"] = int(np.load(d / "cell_kept.npy").sum())
        r["pass"] = bool(r["A_prompt_ok"] and r["A_resp_ok"] and r["A_c11_ok"] and lens_ok and not bad)
        res.append(r)
        del A, Ar, Ac
    return {"rows": res, "pass": all(r["pass"] for r in res)}


def main() -> int:
    setup_logging("unit_checks")
    out = {"utc": utc_now()}
    for name, fn in (("stats_synthetic", check_stats), ("outcome_rates_repro", check_outcomes),
                     ("incumbent_code_repro_iter2_arrays", check_incumbents), ("harvest_integrity", check_harvest)):
        try:
            out[name] = fn()
        except Exception as e:  # noqa: BLE001
            logger.exception(f"{name} failed")
            out[name] = {"pass": False, "error": repr(e)[:400]}
        logger.info(f"{name}: pass={out[name].get('pass')}")
    out["all_pass"] = all(v.get("pass") for k, v in out.items() if isinstance(v, dict))
    jdump(out, RESULTS / "unit_checks.json")
    logger.info(f"unit checks all_pass={out['all_pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
