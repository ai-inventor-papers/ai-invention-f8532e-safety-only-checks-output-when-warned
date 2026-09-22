"""Tests for the sharded-npz path added to keep every file under the 100MB limit.

run:  .venv/bin/python -u tests/test_sharding.py
"""
from __future__ import annotations
import sys, tempfile
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from common import save_sharded, ShardedNpz, shard_paths, WINDOWS   # noqa: E402
import run_lineage                                                   # noqa: E402


def test_pathlib_suffix_trap():
    """Path("L2_a0.00").suffix is ".00", so with_suffix(".npz") silently gives the
    WRONG name. ShardedNpz must still find a single-file harvest."""
    p = Path("L2_a0.00")
    assert p.suffix == ".00" and str(p.with_suffix(".npz")) == "L2_a0.npz"
    with tempfile.TemporaryDirectory() as td:
        stem = Path(td) / "L2_a0.00"
        np.savez(Path(str(stem) + ".npz"), k=np.arange(10))
        z = ShardedNpz(stem)
        assert np.array_equal(z["k"], np.arange(10))
        assert z.parts[0].name == "L2_a0.00.npz"
    print("  ok  pathlib suffix trap: single-file fallback resolves correctly")


def test_roundtrip_and_split():
    rng = np.random.default_rng(0)
    arrays = {f"a{i}": rng.random((200, 200), dtype=np.float32).astype(np.float16) for i in range(40)}
    with tempfile.TemporaryDirectory() as td:
        stem = Path(td) / "x_a0.00"
        parts = save_sharded(stem, arrays, max_bytes=300_000)
        assert len(parts) > 1, "should have split"
        assert all(p.stat().st_size < 400_000 for p in parts)
        assert shard_paths(stem) == parts
        z = ShardedNpz(stem)
        assert set(z.files) == set(arrays)
        assert all(np.array_equal(z[k], arrays[k]) for k in arrays)
    print(f"  ok  round-trip EXACT over {len(arrays)} keys across {len(parts)} parts")


def test_save_state_shape():
    """save_state must store K4 PROJECTIONS, never the raw per-position vectors."""
    n, d, cont = 24, 2560, 128
    band, k4L = [13, 14, 15], [13, 15]
    rng = np.random.default_rng(1)

    def blk(perpos=False):
        o = {"win": {w: {li: rng.random((n, d), dtype=np.float32).astype(np.float16) for li in band}
                     for w in WINDOWS},
             "last_prompt": {li: rng.random((n, d), dtype=np.float32).astype(np.float16) for li in band},
             "nll_cont": rng.random(n, dtype=np.float32),
             "norm": rng.random(n, dtype=np.float32)}
        if perpos:
            o["perpos"] = {li: rng.random((n, cont, d), dtype=np.float32).astype(np.float16) for li in k4L}
        return o

    H = {k: blk() for k in ("item", "fit_content", "ladder", "neutral", "domain")}
    H["k4"] = blk(perpos=True)
    for k in ("fit_ablit", "damage", "damage_matched"):
        H[k] = blk()
    k4_proj = {li: rng.random((n, cont, 23), dtype=np.float32) for li in k4L}
    names = ["r_content_parent", "r_content_state", "r_ablit"] + [f"null{j}" for j in range(20)]
    with tempfile.TemporaryDirectory() as td:
        stem = Path(td) / "LX_a0.50"
        run_lineage.save_state(stem, None, H, band, k4L, k4_proj=k4_proj, k4_proj_names=names)
        z = ShardedNpz(stem)
        assert np.array_equal(z["item|win|EARLY|13"], H["item"]["win"]["EARLY"][13])
        assert np.array_equal(z["k4|perposproj|15"], k4_proj[15])
        assert [str(x) for x in z["k4|projdir_names"]] == names
        assert "k4|perpos|13" not in z.files, "raw per-position vectors must NOT be stored"
        biggest = max(p.stat().st_size for p in shard_paths(stem))
        assert biggest <= 90_000_000
    print(f"  ok  save_state: {len(z.files)} keys, projections stored, raw vectors excluded")


if __name__ == "__main__":
    test_pathlib_suffix_trap()
    test_roundtrip_and_split()
    test_save_state_shape()
    print("ALL SHARDING TESTS PASSED")
