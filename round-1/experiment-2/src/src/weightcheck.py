"""STAGE 9 - external reproduction check, WEIGHTS ONLY, shard-streamed.

Does the in-house lesion reproduce a real community abliteration?  For every
residual-writing matrix we form Delta = W_child - W_parent and report
  (a) sigma_1^2 / ||Delta||_F^2   - is the real edit rank-one?
  (b) |cos(u_1(Delta), r_ablit)|  - is it OUR direction?
  (c) the implied alpha from ||Delta||.
Weights-only is squarely inside the run invariant. This is DESCRIPTIVE: it checks,
it decides nothing.
"""
from __future__ import annotations
import glob, json, sys, time
from pathlib import Path
import numpy as np
import torch
from safetensors import safe_open

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
HUB = "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/.shared_cache/hf/hub"
CHILD = "mlabonne--Qwen3-4B-abliterated"
PARENT = "Qwen--Qwen3-4B"


def open_repo(name):
    snap = glob.glob(f"{HUB}/models--{name}/snapshots/*")[0]
    idx = json.load(open(f"{snap}/model.safetensors.index.json"))
    handles, wmap = {}, idx["weight_map"]
    for shard in sorted(set(wmap.values())):
        handles[shard] = safe_open(f"{snap}/{shard}", framework="pt")
    return handles, wmap


def get(handles, wmap, key):
    """bf16 has no numpy dtype, so read through torch and up-cast to float32."""
    return handles[wmap[key]].get_tensor(key).to(torch.float32).numpy()


def top_eig(G):
    """top eigenvalue/vector of a symmetric PSD matrix."""
    w, V = np.linalg.eigh(G)
    return float(w[-1]), V[:, -1]


def main():
    t0 = time.time()
    ch, cw = open_repo(CHILD)
    ph, pw = open_repo(PARENT)
    res = {"child": CHILD, "parent": PARENT, "per_matrix": [], "notes": []}

    dirs_path = OUT / "harvest" / "L2_dirs.npz"
    u_ours = None
    if dirs_path.exists():
        u_ours = np.load(dirs_path)["u"].astype(np.float64)
    elif (OUT / "pilot_dirs.npz").exists():
        u_ours = np.load(OUT / "pilot_dirs.npz")["u"].astype(np.float64)
    res["have_r_ablit"] = u_ours is not None

    d_model = 2560
    G_all = np.zeros((d_model, d_model), np.float64)
    fro_all = 0.0
    n_layers = 36
    for li in range(n_layers):
        for mat, shape_note in (("self_attn.o_proj", "[2560,4096]"), ("mlp.down_proj", "[2560,9728]")):
            key = f"model.layers.{li}.{mat}.weight"
            Wc = get(ch, cw, key)
            Wp = get(ph, pw, key)
            D = (Wc - Wp).astype(np.float64)
            G = D @ D.T                       # [2560, 2560]
            fro2 = float(np.trace(G))
            s1sq, u1 = top_eig(G)
            row = {"layer": li, "matrix": mat, "shape": shape_note,
                   "fro2_delta": fro2,
                   "rank1_share": (s1sq / fro2) if fro2 > 0 else float("nan"),
                   "fro_delta": float(np.sqrt(fro2)),
                   "fro_parent": float(np.sqrt((Wp.astype(np.float64) ** 2).sum()))}
            if fro2 > 0:
                v = u1 @ Wp.astype(np.float64)                   # u1^T W_parent
                row["implied_alpha"] = float(np.sqrt(fro2) / (np.linalg.norm(v) + 1e-12))
                if u_ours is not None:
                    row["cos_u1_vs_our_rablit"] = float(abs(u1 @ u_ours))
            G_all += G
            fro_all += fro2
            res["per_matrix"].append(row)
        if li % 9 == 0:
            print(f"  layer {li} done  ({time.time()-t0:.0f}s)", flush=True)

    s1_all, u1_all = top_eig(G_all)
    res["global"] = {
        "fro2_total": fro_all,
        "rank1_share_pooled": s1_all / fro_all if fro_all > 0 else float("nan"),
        "u1_pooled_cos_vs_our_rablit": (float(abs(u1_all @ u_ours)) if u_ours is not None else None),
    }
    np.save(OUT / "mlabonne_u1_pooled.npy", u1_all)

    # embed_tokens: did the community edit touch the (tied) unembed?
    try:
        Ec = get(ch, cw, "model.embed_tokens.weight")
        Ep = get(ph, pw, "model.embed_tokens.weight")
        DE = (Ec - Ep).astype(np.float64)
        fro2 = float((DE * DE).sum())
        res["embed_tokens"] = {
            "fro_delta": float(np.sqrt(fro2)),
            "fro_parent": float(np.sqrt((Ep.astype(np.float64) ** 2).sum())),
            "edited": bool(fro2 > 0),
        }
        if fro2 > 0:
            # rank-1 in the d_model axis: DE is [vocab, d], direction lives in d
            Gd = DE.T @ DE
            s1, ud = top_eig(Gd)
            res["embed_tokens"]["rank1_share"] = s1 / fro2
            res["embed_tokens"]["cos_u1_vs_pooled_u1"] = float(abs(ud @ u1_all))
            if u_ours is not None:
                res["embed_tokens"]["cos_u1_vs_our_rablit"] = float(abs(ud @ u_ours))
            res["notes"].append(
                "mlabonne DOES edit embed_tokens. Qwen3-4B has tie_word_embeddings=True, so that "
                "edit also removes the direction from the UNEMBED. Our primary grid deliberately "
                "does not, which is why our causal-arm logit outcome is uncontaminated.")
        else:
            res["notes"].append("mlabonne leaves embed_tokens untouched.")
    except Exception as e:
        res["embed_tokens"] = {"error": str(e)}

    res["elapsed_s"] = time.time() - t0
    rs = [r["rank1_share"] for r in res["per_matrix"] if np.isfinite(r.get("rank1_share", np.nan))]
    ia = [r["implied_alpha"] for r in res["per_matrix"] if "implied_alpha" in r]
    cs = [r["cos_u1_vs_our_rablit"] for r in res["per_matrix"] if "cos_u1_vs_our_rablit" in r]
    res["summary"] = {
        "n_matrices": len(res["per_matrix"]),
        "rank1_share_median": float(np.median(rs)) if rs else None,
        "rank1_share_min": float(np.min(rs)) if rs else None,
        "implied_alpha_median": float(np.median(ia)) if ia else None,
        "implied_alpha_iqr": [float(np.percentile(ia, 25)), float(np.percentile(ia, 75))] if ia else None,
        "cos_u1_vs_our_rablit_median": float(np.median(cs)) if cs else None,
    }
    (OUT / "stage9_weightcheck.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res["summary"], indent=1))
    print(json.dumps(res["global"], indent=1))
    print(json.dumps(res.get("embed_tokens", {}), indent=1))


if __name__ == "__main__":
    main()
