import sys, time
sys.path.insert(0, "src")
import numpy as np
import ncands as nc
import pairs as pr
from pathlib import Path

RUN_ROOT = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
ITER2 = RUN_ROOT / "iter_2/gen_art/gen_art_experiment_1/harvest"
tag = "Qwen--Qwen3-1.7B"
ck = nc.Ckpt.load(tag, ITER2 / tag)
nc.precompute(ck)

# NEW (current on-disk) proj_curve/auroc_w already imported as nc.proj_curve / nc.auroc_w
EPS = nc.EPS

def proj_curve_OLD(K, G_EE, c):
    num = np.einsum("lmn,n->lm", K, c, optimize=True)
    den2 = np.einsum("n,lnk,k->l", c, G_EE, c, optimize=True)
    den = np.sqrt(np.maximum(den2, EPS))
    return num / den[:, None]

def auroc_w_OLD(P, y, w):
    P = np.asarray(P, dtype=np.float64)
    y = np.asarray(y).astype(int)
    w = np.asarray(w, dtype=np.float64)
    m1, m0 = y == 1, y == 0
    n1, n0 = float(w[m1].sum()), float(w[m0].sum())
    if n1 < EPS or n0 < EPS:
        return np.full(P.shape[:-1], np.nan)
    Pp, Pn = P[..., m1], P[..., m0]
    wp, wn = w[m1], w[m0]
    diff = Pp[..., :, None] - Pn[..., None, :]
    ind = (diff > 0).astype(np.float64) + 0.5 * (diff == 0).astype(np.float64)
    U = np.einsum("...ab,a,b->...", ind, wp, wn)   # no optimize kwarg (the pre-fix code)
    return U / (n1 * n0)

draws = pr.build_global_draws(B=25, seed=333)

max_diff_values = 0.0
max_diff_proj = 0.0
max_diff_auroc = 0.0

nc_proj_curve_new = nc.proj_curve
nc_auroc_new = nc.auroc_w

for d in draws:
    v_new = nc.values(ck, w_stim=d["w_stim"])
    # monkeypatch to old implementations, recompute, restore
    nc.proj_curve = proj_curve_OLD
    nc.auroc_w = auroc_w_OLD
    v_old = nc.values(ck, w_stim=d["w_stim"])
    nc.proj_curve = nc_proj_curve_new
    nc.auroc_w = nc_auroc_new

    for k in v_new:
        if k.startswith("_"):
            continue
        a, b = v_new.get(k), v_old.get(k)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and np.isfinite(a) and np.isfinite(b):
            max_diff_values = max(max_diff_values, abs(a - b))

print("max abs diff over all scalar candidates, 25 draws:", max_diff_values)
print("PASS (<=1e-9)" if max_diff_values <= 1e-9 else "FAIL")
