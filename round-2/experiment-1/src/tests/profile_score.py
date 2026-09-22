"""Profile one checkpoint's offline scoring path (real labels + a few nulls + R)."""
import sys, time, cProfile, pstats
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import numpy as np
from aii_common import ASSETS, WS, jload
import score_ckpt as sc
import score_panel as sp

tag = sys.argv[1] if len(sys.argv) > 1 else "Qwen--Qwen3-4B"
prereg = jload(WS / "prereg.json"); cfg = dict(prereg["config"])
cfg["primary_fpr_level"] = prereg["stimuli_meta"]["primary_fpr_level"]
stim = jload(ASSETS / "stimuli.json")["rows"]
y = np.array([s["y"] for s in stim]); sid = np.array([s["set_id"] for s in stim])
easy = np.flatnonzero(sid == 0)
t = time.time(); cache = sc.CkptCache(tag); _ = cache.A; _ = cache.G
print("load", round(time.time() - t, 1), "s  A", cache.A.shape, "G", len(cache.G))
t = time.time(); r = sc.compute_candidates(cache, y, cfg, seed=0, subset=easy, with_curves=True)
print("compute_candidates(real, dm axis)", round(time.time() - t, 2), "s")
print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items() if not isinstance(v, (list, dict, str))})
t = time.time(); r2 = sc.compute_candidates(cache, y, cfg, seed=0, subset=easy, use_probe_axis=True)
print("compute_candidates(probe axis)", round(time.time() - t, 2), "s", "X2", r2.get("X2"), "X1", r2.get("X1"))
pr = cProfile.Profile(); pr.enable()
t = time.time(); x = sc.compute_x10(cache, cfg); print("x10", round(time.time() - t, 2), "s", {k: x[k] for k in x if k.startswith("X10") and not isinstance(x[k], (list, str))})
t = time.time(); R = sc.recognition_axis(cache, stim, cfg); print("R", round(time.time() - t, 1), "s", {k: R[k] for k in ("R_TPR", "R_TPR_fpr_level", "R_AUROC", "best_layer", "n_benign_hard", "headroom_tpr_points")})
t = time.time(); b2 = sc.bl2_rawhid(cache, y[easy], r["l_star"], subset=easy); print("BL2", round(time.time() - t, 1), "s", b2)
t = time.time(); b6 = sc.bl6_hrci(cache, y[easy], r["l_star"], cfg, subset=easy); print("BL6", round(time.time() - t, 1), "s", {k: b6[k] for k in b6 if k != "BL6_note"})
pr.disable()
pstats.Stats(pr).sort_stats("cumulative").print_stats(12)
