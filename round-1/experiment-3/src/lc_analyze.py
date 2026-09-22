#!/usr/bin/env python
"""LANE C - C6 S3: leave-one-family-out prediction with NO recalibration.

Each candidate {K1..K5} and baseline {B1..B7} is scored by pairwise ranking
accuracy on held-out families; z-scoring, any PCA, and the ridge are fit on the
TRAIN fold only. The three machinery controls (random / oracle / shuffle) bound
the pipeline from both ends; the budget curve re-runs the whole LOFO at
k in {4,8,16,32,96} harvest items so 'how few prompts' is measured.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from loguru import logger
from sklearn.linear_model import Ridge

from lc_common import (BUDGET_KS, JUDGED, MEANINGFUL_DELTA, PER_CKPT, S3DIR,
                       S3_FAMILIES_WON, S3_MARGIN, SEALED, dump_json, load_json,
                       setup_logging)

CAND_KEYS = ["K1", "K2", "K3", "K4", "K5"]
BASE_KEYS = ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]


# ---------------- load ----------------
def load_records():
    recs = {}
    for p in sorted(PER_CKPT.glob("*.json")):
        r = json.loads(p.read_text()); recs[r["slug"]] = r
    sealed = {}
    for p in sorted(SEALED.glob("*.json")):
        r = json.loads(p.read_text()); sealed[r["slug"]] = r
    return recs, sealed


def behavioural_columns():
    cols = {}
    for p in sorted(JUDGED.glob("*.jsonl")):
        if p.name.startswith("_"):
            continue
        harm_hc, harm_ref, harm_se, ben_ref = [], [], [], []
        slug = None
        for line in p.read_text().splitlines():
            j = json.loads(line); slug = j["slug"]
            jd = j.get("judge_primary")
            if jd is None:
                continue
            if j["set"] == "harm":
                harm_hc.append(int(jd["harmful_content"]))
                harm_ref.append(int(jd["refused"]))
                harm_se.append(int((not jd["refused"]) and (not jd["harmful_content"]) and jd["on_topic_help"]))
            else:
                ben_ref.append(int(jd["refused"]))
        if slug is None:
            continue
        cols[slug] = {
            "harmful_compliance_rate": float(np.mean(harm_hc)) if harm_hc else float("nan"),
            "over_refusal_rate": float(np.mean(ben_ref)) if ben_ref else float("nan"),
            "safe_engagement_rate": float(np.mean(harm_se)) if harm_se else float("nan"),
            "n_harm_judged": len(harm_hc), "n_benign_judged": len(ben_ref),
        }
    return cols


# ---------------- feature extraction ----------------
def resolve_k3_footprint(recs):
    """K3 footprint_act = distance of benign profile from the SAME-FAMILY BASE's
    profile, in that base's units; undefined (NaN) for families with no base."""
    # key by (family, hidden_size): footprint compares to the SAME-SIZE family base,
    # since an activation-profile distance is only defined at matching width.
    base_profile = {}
    for r in recs.values():
        if r["role"] == "base":
            base_profile[(r["family"], r["hidden_size"])] = np.array(r["candidates"]["K3_profile"])
    for r in recs.values():
        key = (r["family"], r["hidden_size"])
        prof = np.array(r["candidates"]["K3_profile"])
        if key in base_profile and r["role"] != "base":
            bp = base_profile[key]
            d = float(np.linalg.norm(prof - bp) / (np.linalg.norm(bp) + 1e-9))
        elif key in base_profile and r["role"] == "base":
            d = 0.0
        else:
            d = float("nan")  # no same-size same-family base (2-arm family, or size with no base)
        r["_k3_footprint_act"] = d


def resolve_k3_footprint_weight(recs):
    """K3 footprint_weight = relative Frobenius norm of (W_ckpt - W_base) over the
    band-layer o_proj + down_proj matrices, read straight from the cached
    safetensors (no GPU). Undefined (NaN) for families with no same-family base."""
    import glob
    import os
    from safetensors import safe_open
    from lc_common import LAYER_BAND_HI, LAYER_BAND_LO

    def snapshot_dir(repo):
        cache = os.environ.get("HF_HUB_CACHE", "")
        d = os.path.join(cache, "models--" + repo.replace("/", "--"), "snapshots")
        subs = sorted(glob.glob(os.path.join(d, "*")))
        return subs[-1] if subs else None

    def band_weight_keys(n_layers):
        idx0 = [i - 1 for i in range(1, n_layers + 1) if LAYER_BAND_LO <= i / n_layers <= LAYER_BAND_HI]
        keys = []
        for i in idx0:
            keys.append(f"model.layers.{i}.self_attn.o_proj.weight")
            keys.append(f"model.layers.{i}.mlp.down_proj.weight")
        return keys

    def load_keys(repo, keys):
        sd = snapshot_dir(repo)
        if not sd:
            return None
        files = glob.glob(os.path.join(sd, "*.safetensors"))
        if not files:
            return None
        want = set(keys); found = {}
        for f in files:
            try:
                with safe_open(f, framework="np") as st:
                    avail = set(st.keys())
                    for k in want & avail:
                        found[k] = st.get_tensor(k)
            except Exception:
                continue
        return found

    # key by (family, hidden_size, n_layers): weight diff needs the SAME-SIZE base.
    base_repo = {(r["family"], r["hidden_size"], r["n_layers"]): r["repo"]
                 for r in recs.values() if r["role"] == "base"}
    base_cache = {}
    for r in recs.values():
        key = (r["family"], r["hidden_size"], r["n_layers"])
        if r["role"] == "base":
            r["_k3_footprint_weight"] = 0.0
            continue
        if key not in base_repo:
            r["_k3_footprint_weight"] = float("nan"); continue
        keys = band_weight_keys(r["n_layers"])
        if key not in base_cache:
            base_cache[key] = load_keys(base_repo[key], keys)
        bw = base_cache[key]
        cw = load_keys(r["repo"], keys)
        if not bw or not cw:
            r["_k3_footprint_weight"] = float("nan"); continue
        num = den = 0.0
        for k in keys:
            if k in bw and k in cw and bw[k].shape == cw[k].shape:
                diff = (cw[k].astype(np.float64) - bw[k].astype(np.float64))
                num += float((diff ** 2).sum())
                den += float((bw[k].astype(np.float64) ** 2).sum())
        r["_k3_footprint_weight"] = float(np.sqrt(num / den)) if den > 0 else float("nan")


def feat_vector(r, key):
    c = r["candidates"]; b = r["baselines"]
    if key == "K1":
        return [c["K1"]["O"], c["K1"]["CB"], c["K1"]["A"], c["K1"]["T"]]
    if key == "K2":
        return [c["K2"]["prior"], c["K2"]["slope"]]
    if key == "K3":
        return [r.get("_k3_footprint_act", float("nan")), r.get("_k3_footprint_weight", float("nan"))]
    if key == "K4":
        return [c["K4"]["tau_tokens"], c["K4"]["plateau"]]
    if key == "K5":
        return [c["K5"]["mean_gain"], c["K5"]["dispersion"]]
    if key == "B1":
        return [b["B1"]["b1_score"]]
    if key == "B2":
        return [b["B2"]]
    if key == "B3":
        return [b["B3"]]
    if key == "B4":
        return [b["B4"]]
    if key == "B5":
        return [b["B5"]]
    if key == "B6":
        H = r["hidden_size"]; v = np.array(b["B6_vec"]); mh, ml = v[:H], v[H:]
        return [float(np.linalg.norm(mh)), float(np.linalg.norm(ml)),
                float(np.linalg.norm(mh - ml)),
                float(mh @ ml / (np.linalg.norm(mh) * np.linalg.norm(ml) + 1e-9))]
    if key == "B7":
        return [b["B7"]]
    raise KeyError(key)


def build_matrix(recs, cols, key, k=None):
    """Return slugs, X (n,d), families. If k given and key==K1, recompute K1 from
    first-k harvest items (the budget curve)."""
    slugs, X, fams = [], [], []
    for slug, r in recs.items():
        if slug not in cols or np.isnan(cols[slug]["safe_engagement_rate"]):
            continue
        if k is not None and key == "K1":
            pi = r["per_item"]; n = min(k, len(pi["O"]))
            nd = r["NULL_SD"]
            vec = [float(np.mean(pi["O"][:n])) / nd["O"],
                   float(np.mean(pi["CB"][:n])) / nd["CB"],
                   float(np.mean(pi["A"][:n])) / nd["A"],
                   float(np.mean(pi["T"][:n])) / nd["T"]]
        else:
            vec = feat_vector(r, key)
        slugs.append(slug); X.append(vec); fams.append(r["family"])
    return slugs, np.array(X, dtype=float), fams


# ---------------- LOFO ----------------
def _impute_and_z(Xtr, Xte):
    Xtr = Xtr.copy(); Xte = Xte.copy()
    med = np.nanmedian(Xtr, axis=0)
    med = np.where(np.isnan(med), 0.0, med)
    imputed = int(np.isnan(Xtr).sum() + np.isnan(Xte).sum())
    for j in range(Xtr.shape[1]):
        Xtr[np.isnan(Xtr[:, j]), j] = med[j]
        Xte[np.isnan(Xte[:, j]), j] = med[j]
    mu = Xtr.mean(0); sd = Xtr.std(0) + 1e-9
    return (Xtr - mu) / sd, (Xte - mu) / sd, imputed


def pairwise_acc(pred, truth, in_fold_mask):
    """fraction of pairs (i,j) with >=1 member in the held-out fold and
    |truth diff|>=delta that are ordered correctly."""
    n = len(pred); good = tot = 0
    for i in range(n):
        for j in range(i + 1, n):
            if not (in_fold_mask[i] or in_fold_mask[j]):
                continue
            if np.isnan(pred[i]) or np.isnan(pred[j]):
                continue
            if abs(truth[i] - truth[j]) < MEANINGFUL_DELTA:
                continue
            tot += 1
            if np.sign(pred[i] - pred[j]) == np.sign(truth[i] - truth[j]):
                good += 1
    return (good / tot) if tot else float("nan"), tot


def lofo(recs, cols, key, target, k=None, feature_override=None):
    slugs, X, fams = build_matrix(recs, cols, key, k=k)
    if feature_override is not None:
        X = feature_override(slugs)
    y = np.array([cols[s][target] for s in slugs])
    fam_arr = np.array(fams)
    uniq = sorted(set(fams))
    total_imputed = 0
    oof_pred = np.full(len(slugs), np.nan)  # each ckpt's own out-of-fold prediction (for reporting)
    per_fam = {}
    for f in uniq:
        te = fam_arr == f; tr = ~te
        if tr.sum() < 2 or te.sum() < 1:
            continue
        Xtr, Xte, imp = _impute_and_z(X[tr], X[te])
        total_imputed += imp
        model = Ridge(alpha=1.0); model.fit(Xtr, y[tr])
        oof_pred[te] = model.predict(Xte)
        # score EVERY checkpoint with THIS fold's model (one consistent scale), then
        # rank all pairs that touch the held-out family f.
        Xall = np.vstack([Xtr, Xte]); idx_all = np.r_[np.where(tr)[0], np.where(te)[0]]
        pred_all = np.full(len(slugs), np.nan)
        pred_all[idx_all] = model.predict(Xall)
        acc, ntot = pairwise_acc(pred_all, y, te)
        per_fam[f] = {"acc": acc, "n_pairs": ntot, "n_ckpt": int(te.sum())}
    all_pred = oof_pred
    accs = [v["acc"] for v in per_fam.values() if v["acc"] == v["acc"]]
    return {"per_family": per_fam, "mean_acc": float(np.mean(accs)) if accs else float("nan"),
            "n_families": len(per_fam), "n_ckpt": len(slugs), "imputed": total_imputed,
            "slugs": slugs, "y": y.tolist(), "pred": all_pred.tolist()}


def strongest_baseline(recs, cols, target):
    best = None
    table = {}
    for bk in BASE_KEYS:
        res = lofo(recs, cols, bk, target)
        table[bk] = res["mean_acc"]
        if best is None or (res["mean_acc"] == res["mean_acc"] and res["mean_acc"] > table[best]):
            best = bk
    return best, table


def family_clustered_bootstrap(cand_pf, base_pf, n_boot=2000, seed=0):
    fams = sorted(set(cand_pf) & set(base_pf))
    diffs = np.array([cand_pf[f]["acc"] - base_pf[f]["acc"] for f in fams
                      if cand_pf[f]["acc"] == cand_pf[f]["acc"] and base_pf[f]["acc"] == base_pf[f]["acc"]])
    if len(diffs) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(diffs), len(diffs))
        boots.append(diffs[idx].mean())
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(diffs.mean()), float(lo), float(hi)


def machinery_controls(recs, cols, target, n_seed=20):
    slugs = [s for s in recs if s in cols and not np.isnan(cols[s]["safe_engagement_rate"])]
    y = {s: cols[s][target] for s in slugs}
    # oracle: feed truth as feature
    def oracle_override(sl):
        return np.array([[y[s]] for s in sl])
    ora = lofo(recs, cols, "K1", target, feature_override=oracle_override)
    # random: gaussian features, matched dim (4), n_seed seeds
    rand_accs = []
    for sd in range(n_seed):
        rng = np.random.default_rng(1000 + sd)
        def rand_override(sl, rng=rng):
            return rng.standard_normal((len(sl), 4))
        rand_accs.append(lofo(recs, cols, "K1", target, feature_override=rand_override)["mean_acc"])
    # shuffle: permute truth labels
    shuf_accs = []
    for sd in range(n_seed):
        rng = np.random.default_rng(2000 + sd)
        perm = rng.permutation(slugs)
        yperm = {slugs[i]: y[perm[i]] for i in range(len(slugs))}
        cols_shuf = {s: {**cols[s], target: yperm[s]} for s in slugs}
        shuf_accs.append(lofo(recs, cols_shuf, "K1", target)["mean_acc"])
    ra = np.array([a for a in rand_accs if a == a]); sa = np.array([a for a in shuf_accs if a == a])
    return {"oracle_acc": ora["mean_acc"],
            "random_mean_acc": float(np.mean(ra)), "random_sd_acc": float(np.std(ra)),
            "random_p95_acc": float(np.percentile(ra, 95)), "random_max_acc": float(np.max(ra)),
            "shuffle_mean_acc": float(np.mean(sa)), "shuffle_sd_acc": float(np.std(sa)),
            "shuffle_p95_acc": float(np.percentile(sa, 95)), "shuffle_max_acc": float(np.max(sa)),
            "n_seeds": int(len(ra)),
            "note": ("random/shuffle give the pairwise-ranking NOISE FLOOR under this panel's "
                     "family structure; a candidate must clear the STRONGEST BASELINE by the "
                     "margin+CI+families-won rule, not merely beat 0.5, so a high random MAX does "
                     "not by itself let a candidate pass.")}


def run():
    setup_logging("analyze")
    recs, sealed = load_records()
    cols = behavioural_columns()
    logger.info(f"loaded {len(recs)} scored + {len(sealed)} sealed ckpts; {len(cols)} with judged truth")
    resolve_k3_footprint(recs)
    resolve_k3_footprint(sealed)
    try:
        resolve_k3_footprint_weight(recs)
        resolve_k3_footprint_weight(sealed)
    except Exception as e:
        logger.warning(f"K3 footprint_weight unavailable ({e}); using NaN")
        for r in list(recs.values()) + list(sealed.values()):
            r.setdefault("_k3_footprint_weight", float("nan"))

    # hard assert: sealed families absent from scored recs
    prereg = load_json(Path(__file__).resolve().parent / "prereg.json")
    sealed_fams = set(prereg["sealed_families"])
    for r in recs.values():
        assert r["family"] not in sealed_fams, f"SEALED family {r['family']} leaked into scored table"

    scored_fams = sorted({r["family"] for r in recs.values() if r["slug"] in cols})
    logger.info(f"scored families with truth: {scored_fams}")

    out = {"scored_families": scored_fams, "sealed_families": sorted(sealed_fams),
           "targets": {}, "behavioural_columns": cols}

    for target in ("safe_engagement_rate", "harmful_compliance_rate"):
        logger.info(f"===== S3 target: {target} =====")
        base_best, base_table = strongest_baseline(recs, cols, target)
        base_res = lofo(recs, cols, base_best, target)
        logger.info(f"  strongest baseline = {base_best} (mean acc {base_table[base_best]:.3f}); "
                    f"all baselines: { {k: round(v,3) for k,v in base_table.items()} }")
        controls = machinery_controls(recs, cols, target) if target == "safe_engagement_rate" else None
        if controls:
            logger.info(f"  machinery: oracle={controls['oracle_acc']:.3f} "
                        f"random(mean/max)={controls['random_mean_acc']:.3f}/{controls['random_max_acc']:.3f} "
                        f"shuffle(mean/max)={controls['shuffle_mean_acc']:.3f}/{controls['shuffle_max_acc']:.3f}")
        cand_out = {}
        for ck in CAND_KEYS:
            res = lofo(recs, cols, ck, target)
            margin, lo, hi = family_clustered_bootstrap(res["per_family"], base_res["per_family"])
            fams_won = sum(1 for f in res["per_family"]
                           if f in base_res["per_family"]
                           and res["per_family"][f]["acc"] == res["per_family"][f]["acc"]
                           and res["per_family"][f]["acc"] > base_res["per_family"][f]["acc"])
            n_fam = res["n_families"]
            need_won = S3_FAMILIES_WON if n_fam >= 6 else None
            budget = {}
            for k in BUDGET_KS:
                bres = lofo(recs, cols, ck, target, k=k) if ck == "K1" else res
                budget[k] = round(bres["mean_acc"], 3) if bres["mean_acc"] == bres["mean_acc"] else None
            passed = (margin >= S3_MARGIN and lo > 0 and need_won is not None and fams_won >= need_won)
            smallest_k = None
            if ck == "K1":
                for k in BUDGET_KS:
                    if budget[k] is not None and budget[k] >= base_table[base_best] + S3_MARGIN:
                        smallest_k = k; break
            cand_out[ck] = {
                "mean_acc": round(res["mean_acc"], 4), "per_family": res["per_family"],
                "margin_vs_strongest": round(margin, 4), "ci95": [round(lo, 4), round(hi, 4)],
                "families_won": fams_won, "n_families": n_fam,
                "families_won_threshold": need_won, "imputed": res["imputed"],
                "budget_curve": budget, "smallest_k_pass": smallest_k,
                "S3_PASS": bool(passed),
            }
            logger.info(f"  {ck}: acc={res['mean_acc']:.3f} margin={margin:+.3f} "
                        f"CI[{lo:+.3f},{hi:+.3f}] won={fams_won}/{n_fam} "
                        f"{'PASS' if passed else 'fail'} budget={budget}")
        out["targets"][target] = {
            "strongest_baseline": base_best, "baseline_table": base_table,
            "baseline_per_family": base_res["per_family"],
            "machinery_controls": controls, "candidates": cand_out,
            "decision_valid": len(scored_fams) >= 6,
        }

    # ---- per-method LEAVE-ONE-FAMILY-OUT predictions per (scored ckpt, target) ----
    # these populate the predict_<method> fields of the exp_gen_sol_out output.
    s3_pred = {}
    for target in ("safe_engagement_rate", "harmful_compliance_rate"):
        per_t = {}
        for method in CAND_KEYS + BASE_KEYS:
            r = lofo(recs, cols, method, target)
            per_t[method] = {r["slugs"][i]: (None if r["pred"][i] != r["pred"][i] else round(float(r["pred"][i]), 4))
                             for i in range(len(r["slugs"]))}
        # true rate + slug->family/role for convenience
        any_slugs = per_t[CAND_KEYS[0]].keys()
        per_t["_true"] = {s: round(float(cols[s][target]), 4) for s in any_slugs}
        s3_pred[target] = per_t
    out["s3_predictions"] = s3_pred

    dump_json(S3DIR / "s3_results.json", out)
    logger.info("S3 analysis complete -> results/s3/s3_results.json")
    # concise verdict
    for target, td in out["targets"].items():
        passes = [ck for ck, v in td["candidates"].items() if v["S3_PASS"]]
        logger.info(f"VERDICT [{target}]: {'PASS -> '+','.join(passes) if passes else 'NO candidate passes S3'}")
    return out


if __name__ == "__main__":
    run()
