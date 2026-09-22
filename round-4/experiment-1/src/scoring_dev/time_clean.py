import sys, time
sys.path.insert(0, "src")
import ncands as nc
import pairs as pr
from pathlib import Path

RUN_ROOT = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
ITER2 = RUN_ROOT / "iter_2/gen_art/gen_art_experiment_1/harvest"
tag = "Qwen--Qwen3-1.7B"
ck = nc.Ckpt.load(tag, ITER2 / tag)
nc.precompute(ck)
N = 100
draws = pr.build_global_draws(B=N, seed=77)
t0 = time.time(); t0c = time.process_time()
for d in draws:
    nc.values(ck, w_stim=d["w_stim"])
t1 = time.time(); t1c = time.process_time()
print(f"wall {1000*(t1-t0)/N:.2f} ms/draw, cpu {1000*(t1c-t0c)/N:.2f} ms/draw over {N} draws")
