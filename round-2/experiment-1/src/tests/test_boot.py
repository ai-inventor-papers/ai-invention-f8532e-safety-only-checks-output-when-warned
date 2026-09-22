"""Timing + sanity for the item bootstrap on one harvested checkpoint."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import numpy as np
from aii_common import ASSETS, WS, jload
import score_ckpt as sc
import score_panel as sp

tag = sys.argv[1] if len(sys.argv) > 1 else "Qwen--Qwen3-4B"
nb = int(sys.argv[2]) if len(sys.argv) > 2 else 6
prereg = jload(WS / "prereg.json"); cfg = dict(prereg["config"])
stim = jload(ASSETS / "stimuli.json")["rows"]
y = np.array([s["y"] for s in stim]); sid = np.array([s["set_id"] for s in stim])
easy = np.flatnonzero(sid == 0)
cache = sc.CkptCache(tag); _ = cache.A; _ = cache.G
t = time.time()
b = sp.item_bootstrap(cache, y, easy, cfg, use_probe=True, n_boot=nb)
dt = time.time() - t
print(f"{nb} replicates in {dt:.1f}s = {dt/nb:.2f}s each")
for k in ("X1", "X2", "X3", "X8", "BL1_REFLOGIT", "BL3_DIFFMEAN", "l_star", "l_dec", "l_act"):
    v = np.array(b["reps"][k]); print(k, np.round(v, 3).tolist())
