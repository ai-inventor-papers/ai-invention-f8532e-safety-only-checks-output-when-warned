#!/usr/bin/env python3
"""Prove the shard layer is lossless and that the analysis reads shards transparently.

Runs on a COPY of the smoke harvest with a deliberately tiny shard budget, so every
archive is forced to split into many parts.
"""
import json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import numpy as np
from lane_a import shard

SRC = HERE / "harvest" / "_smoke" / "Qwen3-0.6B"
DST = HERE / "harvest" / "_shardtest"
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)

before = {}
for f in sorted(DST.glob("*.npz")):
    with np.load(f, allow_pickle=False) as z:
        before[f.name] = {k: z[k].copy() for k in z.files}

TINY = 1024 * 1024         # 1 MB: forces every big archive to shard hard, while
                           # still exceeding the largest single row in this harvest
report = []
for f in sorted(DST.glob("*.npz")):
    report.append(shard.migrate(f, max_bytes=TINY))

print("migration:")
for r in report:
    print("   ", Path(r["path"]).name, r["action"],
          f"parts={r.get('n_parts')}" if r.get("n_parts") else "")

# 1) every produced file is under the budget, and any archive that cannot meet it says so
for r in report:
    if r["action"] == "sharded":
        assert r["budget_met"], f"{r['path']} reports budget_met=False unexpectedly"
big = [p for p in DST.rglob("*") if p.is_file() and p.stat().st_size > TINY]
assert not big, f"files still over budget: {[(p.name, p.stat().st_size) for p in big]}"
print(f"\nall {len(list(DST.glob('*.npz')))} part files are under {TINY} bytes")

# 2) reassembly is EXACT, array for array
for name, arrays in before.items():
    got = shard.load_npz(DST / name)
    assert set(got) == set(arrays), (name, set(got) ^ set(arrays))
    for k, v in arrays.items():
        assert got[k].shape == v.shape, (name, k, got[k].shape, v.shape)
        assert got[k].dtype == v.dtype, (name, k, got[k].dtype, v.dtype)
        if v.dtype.kind in "fc":
            assert np.array_equal(got[k], v, equal_nan=True), f"{name}:{k} values differ"
        else:
            assert np.array_equal(got[k], v), f"{name}:{k} values differ"
    print(f"  {name:16s} {len(arrays)} array(s) reassembled byte-identical")

# 3) the analysis actually runs off the shards
from lane_a.pipeline_analysis import analyse_checkpoint, choose_band
from lane_a.prereg import verify
sub = json.loads((HERE / "items" / "substrate.json").read_text())
meta = json.loads((DST / "meta.json").read_text())
sub["confirmatory_items"] = sub["confirmatory_items"][: meta["n_items"]]
prereg, _ = verify(HERE / "work")
z = shard.load_npz(DST / "fit.npz")
prim = z["halves"] == 0
g2 = choose_band(z["early"][prim], z["labels"].astype(bool)[prim], z["pair_ids"][prim], meta["n_hs"])
band = (g2["band"][0], g2["band"][1])
res = analyse_checkpoint("Qwen3-0.6B", DST, band, sub, prereg)
a = res["candidates"]["K1"]["early|F1|A"]["term_std"]
ident = res["identity_checks"]["early|F1|T_eq_CB_plus_A_maxabs"]
print(f"\nanalyse_checkpoint over shards: A={a:.4f}  T==CB+A max err={ident}  "
      f"pos-curve len={len(res['position_curve'].get('A_by_position', []))}")
assert np.isfinite(a) and ident == 0.0

shutil.rmtree(DST)
print("\nSHARD ROUNDTRIP OK")
