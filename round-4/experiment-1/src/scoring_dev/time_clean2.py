import sys, time
sys.path.insert(0, "src")
import ncands as nc
import pairs as pr
from pathlib import Path

RUN_ROOT = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
ITER2 = RUN_ROOT / "iter_2/gen_art/gen_art_experiment_1/harvest"
tag = "Qwen--Qwen3-4B"
t_load0 = time.time()
ck = nc.Ckpt.load(tag, ITER2 / tag)
t_load1 = time.time()
nc.precompute(ck)
t_pc1 = time.time()
print(f"L={ck.L} d={ck.d}; load {t_load1-t_load0:.2f}s precompute {t_pc1-t_load1:.2f}s")
N = 60
draws = pr.build_global_draws(B=N, seed=77)
t0 = time.time()
for d in draws:
    nc.values(ck, w_stim=d["w_stim"])
t1 = time.time()
print(f"wall {1000*(t1-t0)/N:.2f} ms/draw over {N} draws")
