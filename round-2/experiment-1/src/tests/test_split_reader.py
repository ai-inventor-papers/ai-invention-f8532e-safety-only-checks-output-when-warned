"""Regression test for the GitHub-size split: X5 / X11 recomputed from D_resp PARTS must equal
the values cached from the ORIGINAL single-file D_resp.npy (same code path, same seeds)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import numpy as np  # noqa: E402

from aii_common import ASSETS, RESULTS, WS, jload  # noqa: E402
import score_ckpt as sc  # noqa: E402

prereg = jload(WS / "prereg.json")
cfg = dict(prereg["config"])
stim = jload(ASSETS / "stimuli.json")["rows"]
y = np.array([s["y"] for s in stim]); sid = np.array([s["set_id"] for s in stim])
easy = np.flatnonzero(sid == 0)
ok_all = True
for tag in ["Qwen--Qwen3-4B", "mlabonne--Qwen3-4B-abliterated", "microsoft--Phi-4-mini-instruct",
            "Qwen--Qwen3-0.6B"]:
    cached = json.load(open(RESULTS / "scored_cache" / f"{tag}.json"))["scored"]["real"]
    use_probe = cached.get("primary_axis") == "probe"
    cache = sc.CkptCache(tag)
    assert not (cache.dir / "D_resp.npy").exists() and (cache.dir / "D_resp_parts").is_dir()
    D = cache.arr("D_resp")
    real = sc.compute_candidates(cache, y, cfg, seed=cfg["seed"] % 1000, use_probe_axis=use_probe,
                                 subset=easy, with_curves=True)
    for k in ("X5", "X11", "X11_early", "X5_conc_harmful_mean"):
        a, b = real.get(k), cached.get(k)
        same = (a is None and b is None) or (a is not None and b is not None and a == b)
        ok_all &= bool(same)
        print(f"{tag[:36]:38s} {k:22s} parts={a!r:>24} cached={b!r:>24} {'EQUAL' if same else 'DIFF'}")
    print(f"{'':38s} D_resp from parts: shape {D.shape} dtype {D.dtype}")
    cache.free()
print("ALL EQUAL" if ok_all else "MISMATCH")
sys.exit(0 if ok_all else 1)
