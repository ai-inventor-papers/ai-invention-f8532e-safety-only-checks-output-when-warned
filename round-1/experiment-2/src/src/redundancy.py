"""How MANY directions carry the harmful-request signal?

The lesion removes ONE direction from every residual-stream write and the held-out
probe does not move at all. That raises the obvious question the lesion cannot answer:
is the harm percept spread over 2 directions, or 200?

This measures it directly, and entirely offline from the alpha=0 harvest. Directions are
fitted on the r_ablit FITTING requests and projected out of the HELD-OUT request
activations, then the 5-fold cross-validated probe is re-scored. Greedy orthogonal
class-direction removal (diff-in-means, re-fitted after each removal) is compared against
removing the same number of RANDOM directions.

This is a REPRESENTATIONAL measurement at one read site, not a weight lesion: it says how
many dimensions carry the signal there, not what the model would do if it could re-encode.
Activations of a SINGLE model; no text, no logits.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import OUT, unit, cv_probe_auroc, rng_for, auroc, shard_paths
from readouts import State

HARV = OUT / "harvest"


def state_exists(stem) -> bool:
    """A harvested state is either sharded parts or a single legacy npz."""
    from pathlib import Path
    return bool(shard_paths(stem)) or Path(str(stem) + ".npz").exists()
KS = [0, 1, 2, 4, 8, 16, 32, 64, 128]


def greedy_class_dirs(X, y, k):
    """k orthogonal diff-in-means directions, each re-fitted after the previous removal."""
    Xc = X.copy()
    dirs = []
    for _ in range(k):
        d = unit(Xc[y == 1].mean(0) - Xc[y == 0].mean(0))
        for e in dirs:
            d = d - (d @ e) * e
        n = np.linalg.norm(d)
        if n < 1e-8:
            break
        d = d / n
        dirs.append(d)
        Xc = Xc - np.outer(Xc @ d, d)
    return dirs


def project_out(X, dirs):
    Xo = X.copy()
    for d in dirs:
        Xo = Xo - np.outer(Xo @ d, d)
    return Xo


def run_lineage(tag, alpha=None):
    meta = json.loads((HARV / f"{tag}_meta.json").read_text())
    a0 = meta["alphas"][0] if alpha is None else alpha
    pick = meta["r_ablit_layer"]
    st = State(tag, a0, meta["band"], meta["k4_layers"])
    Xf = st.lastp("fit_ablit", pick)
    yf = np.array([m["label"] for m in st.idx["fit_ablit"]])
    Xh = st.lastp("damage", pick)
    yh = np.array([m["label"] for m in st.idx["damage"]])
    d_model = Xf.shape[1]
    g = rng_for(f"redund|{tag}")

    res = {"tag": tag, "alpha": a0, "repo": meta["repo"], "layer": pick, "d_model": int(d_model),
           "n_fit": int(len(yf)), "n_heldout": int(len(yh)), "ks": KS,
           "class_removal_auroc": [], "random_removal_auroc": [],
           "class_removal_variance_kept": [], "u_cos_with_first_dir": None}
    u = np.load(HARV / f"{tag}_dirs.npz")["u"].astype(np.float32)
    v0 = Xh.var(0).sum()
    for k in KS:
        if k > min(len(yf) - 2, d_model):
            break
        cd = greedy_class_dirs(Xf, yf, k) if k else []
        Xhk = project_out(Xh, cd)
        res["class_removal_auroc"].append(cv_probe_auroc(Xhk, yh, tag=f"red|{tag}|{k}"))
        res["class_removal_variance_kept"].append(float(Xhk.var(0).sum() / v0))
        R = g.normal(size=(k, d_model)).astype(np.float32) if k else np.zeros((0, d_model), np.float32)
        rd = []
        for r in R:
            for e in rd:
                r = r - (r @ e) * e
            rd.append(unit(r))
        res["random_removal_auroc"].append(cv_probe_auroc(project_out(Xh, rd), yh,
                                                          tag=f"redr|{tag}|{k}"))
        if k == 1:
            res["u_cos_with_first_dir"] = float(abs(cd[0] @ u))
    # ---- IS THE POST-LESION SEPARABILITY JUST A NORM ARTEFACT? ----
    # The lesion removes a CLASS-CORRELATED component, which changes the residual NORM in a
    # class-correlated way; RMSNorm then turns that into a class-correlated rescaling of every
    # other coordinate. That would manufacture separability without any re-encoding. Test it:
    # score the probe on L2-NORMALISED activations, and score the norm ALONE as a 1-D feature.
    nh = np.linalg.norm(Xh, axis=1, keepdims=True)
    res["auroc_on_unit_normalised_activations"] = cv_probe_auroc(
        Xh / np.maximum(nh, 1e-9), yh, tag=f"redn|{tag}")
    res["auroc_of_residual_norm_alone"] = auroc(nh[:, 0], yh)
    nhf = np.linalg.norm(Xf, axis=1, keepdims=True)
    res["norm_mean_harmful"] = float(nh[yh == 1].mean())
    res["norm_mean_harmless"] = float(nh[yh == 0].mean())
    res["fit_norm_mean_harmful"] = float(nhf[yf == 1].mean())
    res["fit_norm_mean_harmless"] = float(nhf[yf == 0].mean())
    # and the same greedy class-direction removal AFTER unit-normalising
    Xhn = Xh / np.maximum(nh, 1e-9)
    Xfn = Xf / np.maximum(nhf, 1e-9)
    res["unitnorm_class_removal_auroc"] = []
    for k in (0, 1, 2, 4, 8):
        cd = greedy_class_dirs(Xfn, yf, k) if k else []
        res["unitnorm_class_removal_auroc"].append(
            cv_probe_auroc(project_out(Xhn, cd), yh, tag=f"redun|{tag}|{k}"))
    res["unitnorm_ks"] = [0, 1, 2, 4, 8]
    res["ks_run"] = KS[:len(res["class_removal_auroc"])]
    # the smallest k at which the held-out probe drops below 0.75
    drop = [kk for kk, a in zip(res["ks_run"], res["class_removal_auroc"]) if a < 0.75]
    res["k_to_break_below_0p75"] = drop[0] if drop else None
    drop9 = [kk for kk, a in zip(res["ks_run"], res["class_removal_auroc"]) if a < 0.90]
    res["k_to_break_below_0p90"] = drop9[0] if drop9 else None
    return res


def depth_profile(tag):
    """WHERE does the replacement code appear? Per band layer, compare the intact model
    and the fully lesioned one: held-out probe AUROC, diff-in-means separation, and the
    cosine between the two states' class directions at the SAME layer."""
    meta = json.loads((HARV / f"{tag}_meta.json").read_text())
    if 1.0 not in meta["alphas"]:
        return None
    layers = meta.get("band_plus_pick") or sorted(set(meta["band"] + [meta["r_ablit_layer"]]))
    u = np.load(HARV / f"{tag}_dirs.npz")["u"].astype(np.float32)
    s0 = State(tag, meta["alphas"][0], meta["band"], meta["k4_layers"])
    s1 = State(tag, 1.0, meta["band"], meta["k4_layers"])
    yf = np.array([m["label"] for m in s0.idx["fit_ablit"]])
    yh = np.array([m["label"] for m in s0.idx["damage"]])
    out = {"layers": layers, "auroc_alpha0": [], "auroc_alpha1": [],
           "cos_classdir_a0_vs_a1": [], "cos_classdir_a1_vs_pinned_u": [],
           "cos_classdir_a0_vs_pinned_u": [],
           "u_component_gap_a0": [], "u_component_gap_a1": []}
    for li in layers:
        X0f, X1f = s0.lastp("fit_ablit", li), s1.lastp("fit_ablit", li)
        X0h, X1h = s0.lastp("damage", li), s1.lastp("damage", li)
        d0 = unit(X0f[yf == 1].mean(0) - X0f[yf == 0].mean(0))
        d1 = unit(X1f[yf == 1].mean(0) - X1f[yf == 0].mean(0))
        out["auroc_alpha0"].append(cv_probe_auroc(X0h, yh, tag=f"dp0|{tag}|{li}"))
        out["auroc_alpha1"].append(cv_probe_auroc(X1h, yh, tag=f"dp1|{tag}|{li}"))
        out["cos_classdir_a0_vs_a1"].append(float(abs(d0 @ d1)))
        out["cos_classdir_a1_vs_pinned_u"].append(float(abs(d1 @ u)))
        out["cos_classdir_a0_vs_pinned_u"].append(float(abs(d0 @ u)))
        g0 = float(abs((X0h[yh == 1] @ u).mean() - (X0h[yh == 0] @ u).mean()))
        g1v = float(abs((X1h[yh == 1] @ u).mean() - (X1h[yh == 0] @ u).mean()))
        out["u_component_gap_a0"].append(g0)
        out["u_component_gap_a1"].append(g1v)
        # SCALE-NORMALISED twin. Residual norms differ a lot BETWEEN checkpoints, so a raw
        # cross-checkpoint gap comparison is a scale artefact. Always report this beside it.
        n0 = float(np.linalg.norm(X0h, axis=1).mean())
        n1 = float(np.linalg.norm(X1h, axis=1).mean())
        out.setdefault("mean_norm_a0", []).append(n0)
        out.setdefault("mean_norm_a1", []).append(n1)
        out.setdefault("u_gap_over_norm_a0", []).append(g0 / max(n0, 1e-9))
        out.setdefault("u_gap_over_norm_a1", []).append(g1v / max(n1, 1e-9))
    return out


def main():
    tags = sys.argv[1:] or [p.stem.replace("_meta", "") for p in sorted(HARV.glob("*_meta.json"))]
    out = {}
    for t in tags:
        if not (HARV / f"{t}_meta.json").exists():
            continue
        meta = json.loads((HARV / f"{t}_meta.json").read_text())
        for al in ([meta["alphas"][0], 1.0] if 1.0 in meta["alphas"] else [meta["alphas"][0]]):
            # after sharding the state lives in {stem}.partNNN.npz, not {stem}.npz
            if not state_exists(HARV / f"{t}_a{al:.2f}"):
                continue
            r = run_lineage(t, al)
            key = f"{t}_a{al:.2f}"
            out[key] = r
            print(f"[{key}] layer {r['layer']}  cos(first class dir, pinned u) = {r['u_cos_with_first_dir']}")
            print(f"   k          {r['ks_run']}")
            print(f"   class-dir  {[round(x,4) for x in r['class_removal_auroc']]}")
            print(f"   random-dir {[round(x,4) for x in r['random_removal_auroc']]}")
            print(f"   var kept   {[round(x,4) for x in r['class_removal_variance_kept']]}")
            print(f"   k to break below 0.90 / 0.75: "
                  f"{r['k_to_break_below_0p90']} / {r['k_to_break_below_0p75']}")
            print(f"   NORM-ARTEFACT CHECK: probe on unit-normalised acts = "
                  f"{r['auroc_on_unit_normalised_activations']:.4f} | norm ALONE as 1-D feature = "
                  f"{r['auroc_of_residual_norm_alone']:.4f} | mean||h|| harmful/harmless = "
                  f"{r['norm_mean_harmful']:.1f}/{r['norm_mean_harmless']:.1f}")
            print(f"   unit-norm class removal k={r['unitnorm_ks']} -> "
                  f"{[round(x,4) for x in r['unitnorm_class_removal_auroc']]}", flush=True)
        dp = depth_profile(t)
        if dp:
            out[f"{t}_depth_profile"] = dp
            print(f"   DEPTH PROFILE {t}: layers {dp['layers']}")
            print(f"     AUROC a=0   {[round(x,4) for x in dp['auroc_alpha0']]}")
            print(f"     AUROC a=1   {[round(x,4) for x in dp['auroc_alpha1']]}")
            print(f"     cos(d0,d1)  {[round(x,3) for x in dp['cos_classdir_a0_vs_a1']]}")
            print(f"     cos(d1,u)   {[round(x,3) for x in dp['cos_classdir_a1_vs_pinned_u']]}")
            print(f"     u-gap a=0   {[round(x,2) for x in dp['u_component_gap_a0']]}")
            print(f"     u-gap a=1   {[round(x,3) for x in dp['u_component_gap_a1']]}")
            print(f"     u-gap/||h|| a=0 {[round(x,4) for x in dp['u_gap_over_norm_a0']]}  "
                  f"<- the SCALE-NORMALISED twin; raw gaps are not comparable across checkpoints",
                  flush=True)
    (OUT / "redundancy.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
