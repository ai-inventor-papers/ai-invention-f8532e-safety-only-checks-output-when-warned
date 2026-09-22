import sys, time
sys.path.insert(0, "src")
import ncands as nc
import pairs as pr
from pathlib import Path

RUN_ROOT = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
ITER2 = RUN_ROOT / "iter_2/gen_art/gen_art_experiment_1/harvest"
tag = "Qwen--Qwen3-0.6B"
ck = nc.Ckpt.load(tag, ITER2 / tag)
nc.precompute(ck)
t0=time.time()
kc = nc.k_curve_summary(ck, n_seeds=20)
t1=time.time()
print(f"k_curve_summary: {t1-t0:.2f}s")
t0=time.time()
nsd = nc.null_sd(ck, n_draws=50, seed=1)
t1=time.time()
print(f"null_sd(50): {t1-t0:.2f}s -> {1000*(t1-t0)/50:.2f} ms/draw")
