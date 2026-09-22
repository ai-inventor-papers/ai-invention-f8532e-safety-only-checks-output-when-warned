import sys, time, cProfile, pstats, io
sys.path.insert(0, "src")
import ncands as nc
import pairs as pr

RUN_ROOT = __import__("pathlib").Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
ITER2 = RUN_ROOT / "iter_2/gen_art/gen_art_experiment_1/harvest"
tag = "Qwen--Qwen3-1.7B"
ck = nc.Ckpt.load(tag, ITER2 / tag)
nc.precompute(ck)
draws = pr.build_global_draws(B=30, seed=55)

pr_ = cProfile.Profile()
pr_.enable()
for d in draws:
    nc.values(ck, w_stim=d["w_stim"])
pr_.disable()
st = pstats.Stats(pr_, stream=sys.stdout).sort_stats("cumulative")
st.print_stats(25)
