"""STAGE 9b - is the community edit ONE direction, or one direction PER LAYER?

Per-matrix rank-one share is ~0.994 while the POOLED share is ~0.43. Those two
numbers can only both hold if each matrix gets its own rank-one edit with a
DIFFERENT direction. This quantifies that drift and the depth profile of the
implied strength. Weights only; descriptive.
"""
from __future__ import annotations
import glob, json
from pathlib import Path
import numpy as np
import torch
from safetensors import safe_open

OUT = Path(__file__).resolve().parent.parent / "out"
HUB = "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/.shared_cache/hf/hub"


def open_repo(name):
    snap = glob.glob(f"{HUB}/models--{name}/snapshots/*")[0]
    idx = json.load(open(f"{snap}/model.safetensors.index.json"))
    return {s: safe_open(f"{snap}/{s}", framework="pt") for s in sorted(set(idx["weight_map"].values()))}, idx["weight_map"]


def main():
    ch, cw = open_repo("mlabonne--Qwen3-4B-abliterated")
    ph, pw = open_repo("Qwen--Qwen3-4B")
    U = {}
    for li in range(36):
        for mat in ("self_attn.o_proj", "mlp.down_proj"):
            k = f"model.layers.{li}.{mat}.weight"
            D = (ch[cw[k]].get_tensor(k).to(torch.float32).numpy()
                 - ph[pw[k]].get_tensor(k).to(torch.float32).numpy()).astype(np.float64)
            G = D @ D.T
            w, V = np.linalg.eigh(G)
            U[(li, mat)] = (V[:, -1], float(w[-1]), float(np.trace(G)))
    res = {}
    for mat in ("self_attn.o_proj", "mlp.down_proj"):
        vecs = np.stack([U[(li, mat)][0] for li in range(36)])
        # sign-align then measure drift against the deepest layer
        ref = vecs[-1]
        signs = np.sign(vecs @ ref); signs[signs == 0] = 1
        vecs = vecs * signs[:, None]
        Cm = np.abs(vecs @ vecs.T)
        res[mat] = {
            "cos_adjacent_layers": [float(abs(vecs[i] @ vecs[i + 1])) for i in range(35)],
            "cos_vs_deepest_layer": [float(abs(vecs[i] @ ref)) for i in range(36)],
            "cos_shallowest_vs_deepest": float(abs(vecs[0] @ ref)),
            "mean_offdiag_cos": float((Cm.sum() - np.trace(Cm)) / (36 * 35)),
            "fro_delta_by_layer": [float(np.sqrt(U[(li, mat)][2])) for li in range(36)],
        }
    dirs = OUT / "harvest" / "L2_dirs.npz"
    if dirs.exists():
        z = np.load(dirs)
        u = z["u"].astype(np.float64)
        ra = {int(k.split("_")[1]): z[k].astype(np.float64) for k in z.files if k.startswith("ra_")}
        for mat in ("self_attn.o_proj", "mlp.down_proj"):
            res[mat]["cos_vs_our_pinned_u_by_layer"] = [
                float(abs(U[(li, mat)][0] @ u)) for li in range(36)]
            # and against OUR per-layer request axis at the SAME depth
            res[mat]["cos_vs_our_same_layer_rablit"] = [
                float(abs(U[(li, mat)][0] @ ra[li])) if li in ra else None for li in range(36)]
    (OUT / "stage9_depth.json").write_text(json.dumps(res, indent=1))
    for mat in res:
        r = res[mat]
        print(f"{mat}: adjacent-layer cos median {np.median(r['cos_adjacent_layers']):.3f}  "
              f"shallowest-vs-deepest {r['cos_shallowest_vs_deepest']:.3f}  "
              f"mean off-diag {r['mean_offdiag_cos']:.3f}")
        if "cos_vs_our_same_layer_rablit" in r:
            v = [x for x in r["cos_vs_our_same_layer_rablit"] if x is not None]
            print(f"   vs OUR pinned u: median {np.median(r['cos_vs_our_pinned_u_by_layer']):.3f} "
                  f"max {max(r['cos_vs_our_pinned_u_by_layer']):.3f} | "
                  f"vs OUR same-layer r_ablit: median {np.median(v):.3f} max {max(v):.3f}")


if __name__ == "__main__":
    main()
