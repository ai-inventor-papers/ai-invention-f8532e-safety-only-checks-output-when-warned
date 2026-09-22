"""ADDITIONAL ANALYSES -- added AFTER the prereg freeze, NOT pre-registered, descriptive only (no selection,
no winner, nothing here changes a prereg'd number). Reads the committed harvest arrays + graded truth.

1. PAIRED WITHIN-UNIT CONTRASTS (child - parent on the SAME prompts): the two abliterated pairs and the
   stage steps of the Falcon3 / AMD-OLMo lineages. For every prompt-level readout a PAIRED prompt bootstrap
   (B = 2000; EASY fit prompts and HARD score prompts resampled within class, the same indices for both
   models) gives a 95% CI of the delta; the harmful-compliance delta gets a paired item bootstrap over the
   45 Lane C harmful items + an exact McNemar test. This is the fresh-model replication of iteration-3
   evaluation's finding that the held-out request-axis d (EASY fit, HARD score) FALLS in every effective
   abliterated child (6/6) -- here on 2 abliterated pairs no earlier artifact has loaded.
   Readouts: C13 (d at lay(0.5)), C13_peak_d (max over l >= 1), C7 (area under the per-layer AUROC),
   C5 (peak intermediate logit-lens drive gap on HARD), BL1 (iteration-2 lens, EASY), BL1_hard,
   BL1_truelogit (the literal final-logit gap, see 2).
2. BL1_truelogit: results/hook_checks.json shows hidden_states[-1] is already POST final-norm, and the
   iteration-2 lens applies final_norm again at l = L, so BL1 (kept exactly as iteration 2 for
   comparability) is read on norm(norm(h_L)). BL1_truelogit = the same EASY contrast of
   logsumexp(refusal set) - logsumexp(control set) computed on hidden_states[-1] @ W_U^T, i.e. on the
   model's own final logits for those token rows (WU_ref / WU_ctl stored by the harvest). Reported on the
   held-out panel AND on the iteration-2 panel's saved arrays (same code), beside BL1.
3. LEAVE-ONE-FAMILY-OUT Spearman rho with harmful compliance for every feature (4 families), and the
   sign stability of rho across the four deletions.
4. POOLED two-panel descriptive rho (iteration-2 same-code panel + held-out panel), with a family-cluster
   bootstrap -- context only; the held-out rho alone is the confirmation quantity.

Writes results/extra_analyses.json.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, rankdata, spearmanr

SRC = Path(__file__).resolve().parent
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC / "h2"))
from common import H2, HARVEST, RESULTS, jdump, jload, setup_logging, slug, utc_now  # noqa: E402
from loguru import logger  # noqa: E402

B_PAIR = 2000


def lay(f: float, L: int) -> int:
    return int(math.floor(f * L + 0.5))


def lse_rows(H: np.ndarray, W: np.ndarray) -> np.ndarray:
    z = H.astype(np.float64) @ W.astype(np.float64).T
    m = z.max(1, keepdims=True)
    return (m + np.log(np.exp(z - m).sum(1, keepdims=True)))[:, 0]


def bl1_truelogit(tag_dir: Path, y: np.ndarray, sid: np.ndarray) -> dict:
    A = np.load(tag_dir / "A_prompt.npy", mmap_mode="r")
    L = A.shape[1] - 1
    HL = np.asarray(A[:, L, :], dtype=np.float32)
    WR, WC = np.load(tag_dir / "WU_ref.npy"), np.load(tag_dir / "WU_ctl.npy")
    g = lse_rows(HL, WR) - lse_rows(HL, WC)
    out = {}
    for name, m in (("easy", sid == 0), ("hard", sid == 1)):
        out[name] = float(g[m & (y == 1)].mean() - g[m & (y == 0)].mean())
    out["per_prompt"] = g
    return out


class PromptModel:
    """Per-checkpoint precomputation for the paired prompt bootstrap."""

    def __init__(self, tag: str, y: np.ndarray, sid: np.ndarray, root: Path = HARVEST):
        d = root / tag
        A = np.load(d / "A_prompt.npy").astype(np.float32)
        self.L = A.shape[1] - 1
        self.easy = np.flatnonzero(sid == 0)
        self.hard = np.flatnonzero(sid == 1)
        AE, AH = A[self.easy].astype(np.float64), A[self.hard].astype(np.float64)
        # K[l] = AH_l AE_l^T (160 x 96), G[l] = AE_l AE_l^T (96 x 96): projections for any EASY weighting
        self.K = np.einsum("hld,eld->lhe", AH, AE, optimize=True)
        self.G = np.einsum("ald,bld->lab", AE, AE, optimize=True)
        del A, AE, AH
        rr, rc = np.load(d / "r_refusal.npy").astype(np.float64), np.load(d / "r_control.npy").astype(np.float64)
        self.drv = rr - rc                                      # (256, L+1), iteration-2 lens
        self.tl = bl1_truelogit(d, y, sid)["per_prompt"]        # (256,), literal final logits
        self.yE, self.yH = y[self.easy], y[self.hard]

    def proj(self, w: np.ndarray) -> np.ndarray:
        """HARD projections (160, L+1) on the per-layer unit axis sum_e w_e A_e (w: EASY weights)."""
        num = self.K @ w                                        # (L+1, 160)
        den = np.sqrt(np.maximum(np.einsum("a,lab,b->l", w, self.G, w), 1e-30))
        return (num / den[:, None]).T


def _d_cols(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    a, b = P[y == 1], P[y == 0]
    va, vb = a.var(0, ddof=1), b.var(0, ddof=1)
    sp_ = np.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
    return (a.mean(0) - b.mean(0)) / np.maximum(sp_, 1e-12)


def _auc_cols(P: np.ndarray, y: np.ndarray) -> np.ndarray:
    R = rankdata(P, axis=0)
    n1, n0 = (y == 1).sum(), (y == 0).sum()
    return (R[y == 1].sum(0) - n1 * (n1 + 1) / 2) / (n1 * n0)


def readouts(pm: PromptModel, e_pos: np.ndarray, e_neg: np.ndarray, h_idx: np.ndarray) -> dict:
    """All prompt-level readouts for one (resampled) prompt set. e_pos/e_neg index EASY rows (0..95),
    h_idx indexes HARD rows (0..159)."""
    w = np.zeros(len(pm.easy))
    np.add.at(w, e_pos, 1.0 / len(e_pos))
    np.add.at(w, e_neg, -1.0 / len(e_neg))
    P = pm.proj(w)[h_idx]
    yH = pm.yH[h_idx]
    dl = _d_cols(P, yH)
    auc = _auc_cols(P, yH)
    L = pm.L
    f = np.arange(L + 1) / L
    trap = float(np.sum((auc[1:] + auc[:-1]) * np.diff(f)) / 2)
    dH = pm.drv[pm.hard][h_idx]
    g = dH[yH == 1].mean(0) - dH[yH == 0].mean(0)
    easy_rows_pos, easy_rows_neg = pm.easy[e_pos], pm.easy[e_neg]
    bl1 = pm.drv[easy_rows_pos, L].mean() - pm.drv[easy_rows_neg, L].mean()
    bl1t = pm.tl[easy_rows_pos].mean() - pm.tl[easy_rows_neg].mean()
    tlH = pm.tl[pm.hard][h_idx]
    return {"C13": float(dl[lay(0.5, L)]), "C13_peak_d": float(np.nanmax(dl[1:])), "C7": trap,
            "C5": float(np.max(g[1:L])), "BL1": float(bl1), "BL1_hard": float(g[L]),
            "BL1_truelogit": float(bl1t), "BL1_truelogit_hard": float(tlH[yH == 1].mean() - tlH[yH == 0].mean())}


def paired_contrast(pa: PromptModel, pc: PromptModel, B: int = B_PAIR, seed: int = 11) -> dict:
    pos_e, neg_e = np.flatnonzero(pa.yE == 1), np.flatnonzero(pa.yE == 0)
    pos_h, neg_h = np.flatnonzero(pa.yH == 1), np.flatnonzero(pa.yH == 0)
    full_h = np.arange(len(pa.yH))
    base_a, base_c = readouts(pa, pos_e, neg_e, full_h), readouts(pc, pos_e, neg_e, full_h)
    rng = np.random.default_rng(seed)
    deltas = {k: [] for k in base_a}
    for _ in range(B):
        ep, en = rng.choice(pos_e, len(pos_e)), rng.choice(neg_e, len(neg_e))
        hi = np.r_[rng.choice(pos_h, len(pos_h)), rng.choice(neg_h, len(neg_h))]
        ra, rc = readouts(pa, ep, en, hi), readouts(pc, ep, en, hi)
        for k in deltas:
            deltas[k].append(rc[k] - ra[k])
    out = {}
    for k in base_a:
        v = np.asarray(deltas[k])
        v = v[np.isfinite(v)]
        out[k] = {"parent": base_a[k], "child": base_c[k], "delta": base_c[k] - base_a[k],
                  "ci95_prompt_boot": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if v.size > 50 else [None, None],
                  "p_boot_sign": float(min((v <= 0).mean(), (v >= 0).mean()) * 2) if v.size > 50 else None}
    return out


def hc_contrast(labels: dict, parent: str, child: str, B: int = 10000, seed: int = 5) -> dict:
    def vec(repo):
        return {r["item_id"]: int(r["primary"]["harmful_content"]) for r in labels[repo]
                if r["set"] == "harm" and r.get("subset") == "laneC" and r.get("primary") is not None}
    a, c = vec(parent), vec(child)
    ids = sorted(set(a) & set(c))
    xa, xc = np.array([a[i] for i in ids]), np.array([c[i] for i in ids])
    rng = np.random.default_rng(seed)
    I = rng.integers(0, len(ids), size=(B, len(ids)))
    dd = xc[I].mean(1) - xa[I].mean(1)
    n01, n10 = int(((xa == 0) & (xc == 1)).sum()), int(((xa == 1) & (xc == 0)).sum())
    p_mc = binomtest(n01, n01 + n10, 0.5).pvalue if n01 + n10 > 0 else 1.0
    ka, kc, nn = int(xa.sum()), int(xc.sum()), len(ids)
    (la, ua), (lc, uc) = _wilson(ka, nn), _wilson(kc, nn)
    pa_, pc_ = ka / nn, kc / nn
    newc = [pc_ - pa_ - math.sqrt((pc_ - lc) ** 2 + (ua - pa_) ** 2), pc_ - pa_ + math.sqrt((uc - pc_) ** 2 + (pa_ - la) ** 2)]
    return {"n_items": len(ids), "hc_parent": float(xa.mean()), "hc_child": float(xc.mean()),
            "newcombe_ci95_independent": [float(newc[0]), float(newc[1])],
            "delta_hc": float(xc.mean() - xa.mean()), "ci95_item_boot": [float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))],
            "discordant_child_only": n01, "discordant_parent_only": n10, "mcnemar_exact_p": float(p_mc)}


def _wilson(k: int, n: int, z: float = 1.959963984540054):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def sanity_signals(crow: list[dict]) -> dict:
    """Testing-plan item 6: every abliterated child should comply MORE than its parent; every base should comply
    MORE than its later stages; a contrast whose Newcombe CI covers 0 is kept and flagged as a behavioural no-op."""
    rows = []
    for r in crow:
        h = r["harmful_compliance"]
        lo, hi = h["newcombe_ci95_independent"]
        if r["kind"] == "abliteration":
            expect, ok = "child HC > parent HC", h["delta_hc"] > 0
        elif r["parent"].endswith("-SFT") and r["child"].endswith("-SFT-DPO"):
            expect, ok = "no expectation (preference step SFT -> DPO)", None
        else:
            expect, ok = "base HC > later stage HC", h["delta_hc"] < 0
        rows.append({"kind": r["kind"], "parent": r["parent"], "child": r["child"], "expectation": expect,
                     "delta_hc": h["delta_hc"], "newcombe_ci95": [lo, hi], "meets_expectation": ok,
                     "behavioural_no_op_flag": bool(lo <= 0 <= hi)})
    return {"rows": rows, "note": "a failed expectation is reported, never used to drop a checkpoint"}


def contrasts_from_panel(panel: list[dict], present: set[str]) -> list[dict]:
    rows = []
    for p in panel:
        if p.get("parent") and p["repo"] in present and p["parent"] in present:
            kind = "abliteration" if p["role"] == "edited_child" else f"stage:{p['parent'].split('/')[-1]}->{p['repo'].split('/')[-1]}"
            rows.append({"kind": kind, "parent": p["parent"], "child": p["repo"], "unit": p["unit"], "family": p["family"]})
    base = {p["unit"]: p["repo"] for p in panel if p["role"] == "base" and p["repo"] in present}
    for p in panel:
        if p["role"] == "sft_dpo" and p["unit"] in base and p["repo"] in present:
            rows.append({"kind": "stage:base->SFT-DPO (whole lineage)", "parent": base[p["unit"]], "child": p["repo"],
                         "unit": p["unit"], "family": p["family"]})
    return rows


def rho(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 4 or len(np.unique(x[ok])) < 2 or len(np.unique(y[ok])) < 2:
        return float("nan"), int(ok.sum())
    return float(spearmanr(x[ok], y[ok]).statistic), int(ok.sum())


def fam_boot(x, y, fams, B=4000, seed=3):
    x, y, fams = np.asarray(x, float), np.asarray(y, float), np.asarray(fams)
    ok = np.isfinite(x) & np.isfinite(y)
    uf = np.unique(fams[ok])
    mem = {f: np.flatnonzero(ok & (fams == f)) for f in uf}
    rng = np.random.default_rng(seed)
    r = []
    for _ in range(B):
        i = np.concatenate([mem[f] for f in rng.choice(uf, len(uf))])
        if len(np.unique(x[i])) < 4 or len(np.unique(y[i])) < 4:
            continue
        r.append(spearmanr(x[i], y[i]).statistic)
    r = np.asarray(r)
    return [float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))] if r.size >= 20 else [None, None]


def main() -> int:
    setup_logging("extra_analyses")
    stim = jload(H2 / "assets/stimuli.json")["rows"]
    y = np.array([s["y"] for s in stim], dtype=int)
    sid = np.array([s["set_id"] for s in stim], dtype=int)
    feats = jload(RESULTS / "features.json")
    truth = jload(RESULTS / "graded_truth.json")
    labels = jload(RESULTS / "judged_labels_released.json")["labels"]
    panel = jload(RESULTS / "panel.json")["panel"]
    present = set(feats["features"])
    out = {"utc": utc_now(), "status": "ADDITIONAL, post-prereg, not pre-registered; descriptive; no selection",
           "B_pair": B_PAIR}

    # ---- 2. BL1_truelogit on both panels
    hc = {r: v["outcomes_primary_laneC_items"]["harmful_compliance"] for r, v in truth["per_ckpt"].items()}
    tl_rows = []
    for repo in sorted(present):
        t = bl1_truelogit(HARVEST / slug(repo), y, sid)
        tl_rows.append({"repo": repo, "BL1": feats["features"][repo].get("BL1"), "BL1_truelogit": t["easy"],
                        "BL1_hard": feats["features"][repo].get("BL1_hard"), "BL1_truelogit_hard": t["hard"],
                        "harmful_compliance": hc[repo]})
    i2 = jload(RESULTS / "iter2_panel_same_code.json")
    i2_rows = []
    for r in i2["panel"]:
        if not r.get("scored"):
            continue
        d = H2 / "harvest" / slug(r["repo"])
        t = bl1_truelogit(d, y, sid)
        i2_rows.append({"repo": r["repo"], "family": r["family"], "BL1_truelogit": t["easy"], "BL1_truelogit_hard": t["hard"],
                        "harmful_compliance": r["behaviour"]["harmful_compliance_rate"],
                        "BL1": jload(RESULTS / "iter2_panel_features_cache.json")[slug(r["repo"])].get("BL1")})

    def tab(rows, key):
        return rho([r[key] for r in rows], [r["harmful_compliance"] for r in rows])
    out["bl1_truelogit"] = {
        "heldout_rows": tl_rows, "iter2_rows": i2_rows,
        "heldout_rho_hc": {k: tab(tl_rows, k) for k in ("BL1", "BL1_truelogit", "BL1_hard", "BL1_truelogit_hard")},
        "iter2_rho_hc": {k: tab(i2_rows, k) for k in ("BL1", "BL1_truelogit", "BL1_truelogit_hard")},
        "heldout_rho_BL1_vs_truelogit": rho([r["BL1"] for r in tl_rows], [r["BL1_truelogit"] for r in tl_rows]),
        "iter2_rho_BL1_vs_truelogit": rho([r["BL1"] for r in i2_rows], [r["BL1_truelogit"] for r in i2_rows])}
    logger.info(f"BL1_truelogit: held-out rho(HC) {out['bl1_truelogit']['heldout_rho_hc']}")

    # ---- 1. paired within-unit contrasts
    cons = contrasts_from_panel(panel, present)
    cache: dict[str, PromptModel] = {}

    def pm(repo):
        if repo not in cache:
            cache[repo] = PromptModel(slug(repo), y, sid)
        return cache[repo]
    crow = []
    for c in cons:
        logger.info(f"paired contrast {c['kind']}: {c['parent']} -> {c['child']}")
        res = paired_contrast(pm(c["parent"]), pm(c["child"]))
        hcx = hc_contrast(labels, c["parent"], c["child"])
        fa, fc = feats["features"][c["parent"]], feats["features"][c["child"]]
        # the full-sample readouts here must equal candidates.compute_all's values in features.json
        cons_diff = max(abs(res[k][side] - float(f_[k])) for k in ("C13", "C13_peak_d", "C7", "C5", "BL1", "BL1_hard")
                        for side, f_ in (("parent", fa), ("child", fc)))
        c["max_abs_diff_vs_features_json"] = float(cons_diff)
        if cons_diff > 1e-4:
            logger.warning(f"readout mismatch vs features.json: {cons_diff:.3g} ({c['parent']} -> {c['child']})")
        point = {}
        for k in ("C1", "C2", "C3", "C4", "C6", "C8", "C9", "C10", "C11", "C12", "B3", "B7", "X2", "X10_abs"):
            try:
                point[k] = float(fc.get(k)) - float(fa.get(k))
            except (TypeError, ValueError):
                point[k] = None
        crow.append({**c, "harmful_compliance": hcx, "prompt_level_deltas": res, "point_deltas_other_features": point})
    out["paired_contrasts"] = crow
    out["sanity_signals"] = sanity_signals(crow)
    abl = [r for r in crow if r["kind"] == "abliteration"]
    out["abliteration_replication"] = {
        "claim_tested": "iteration-3 evaluation: held-out request-axis d (EASY fit, HARD score) falls in every effective abliterated child (6/6)",
        "rows": [{"child": r["child"], "delta_hc": r["harmful_compliance"]["delta_hc"],
                  "delta_hc_ci95": r["harmful_compliance"]["ci95_item_boot"],
                  **{f"delta_{k}": r["prompt_level_deltas"][k]["delta"] for k in ("C13", "C13_peak_d", "C7", "C5", "BL1", "BL1_truelogit")},
                  **{f"delta_{k}_ci95": r["prompt_level_deltas"][k]["ci95_prompt_boot"] for k in ("C13", "C13_peak_d", "C7", "C5", "BL1", "BL1_truelogit")}}
                 for r in abl]}

    # ---- 3. leave-one-family-out
    from score import FEATURES
    ck = sorted(present)
    fams = np.array([feats["families"][c] for c in ck])
    yv = np.array([hc[c] for c in ck])
    lofo = []
    for fn in FEATURES:
        xv = np.array([_num(feats["features"][c].get(fn)) for c in ck])
        full, n = rho(xv, yv)
        per = {}
        for f in np.unique(fams):
            keep = fams != f
            per[str(f)] = rho(xv[keep], yv[keep])
        signs = {int(np.sign(v[0])) for v in per.values() if np.isfinite(v[0])}
        lofo.append({"feature": fn, "rho_full": full, "n": n, "lofo": {k: {"rho": v[0], "n": v[1]} for k, v in per.items()},
                     "lofo_min": float(np.nanmin([v[0] for v in per.values()])) if per else None,
                     "lofo_max": float(np.nanmax([v[0] for v in per.values()])) if per else None,
                     "sign_stable_across_lofo": bool(len(signs) == 1 and np.isfinite(full) and int(np.sign(full)) in signs)})
    out["leave_one_family_out_hc"] = lofo

    # ---- 4. pooled two-panel descriptive rho (context only)
    i2c = jload(RESULTS / "iter2_panel_features_cache.json")
    pooled = []
    i2_scored = [r for r in i2["panel"] if r.get("scored")]
    for fn in FEATURES:
        xs, ys, fs = [], [], []
        for c in ck:
            xs.append(_num(feats["features"][c].get(fn)))
            ys.append(hc[c])
            fs.append("H:" + feats["families"][c])
        for r in i2_scored:
            xs.append(_num(i2c[slug(r["repo"])].get(fn)))
            ys.append(r["behaviour"]["harmful_compliance_rate"])
            fs.append("I2:" + r["family"])
        rr, n = rho(xs, ys)
        pooled.append({"feature": fn, "rho_pooled": rr, "n": n, "ci95_family_cluster": fam_boot(xs, ys, fs) if np.isfinite(rr) else [None, None]})
    out["pooled_two_panel_hc"] = {"note": "iteration-2 same-code panel (22 graded) + held-out panel (10); context only, "
                                          "the held-out rho alone is the confirmation quantity", "rows": pooled}
    jdump(out, RESULTS / "extra_analyses.json")
    logger.info("extra analyses written")
    return 0


def _num(v):
    try:
        f = float(v)
        return f if np.isfinite(f) else float("nan")
    except (TypeError, ValueError):
        return float("nan")


if __name__ == "__main__":
    raise SystemExit(main())
