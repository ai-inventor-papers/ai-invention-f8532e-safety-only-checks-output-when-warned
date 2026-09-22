#!/usr/bin/env python3
"""Re-run the FULL per-checkpoint analysis on a real sharded checkpoint and compare every
key number against work/analysis_raw.json, which was produced from the un-sharded files."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import numpy as np
from lane_a import shard
from lane_a.pipeline_analysis import analyse_checkpoint, choose_band
from lane_a.prereg import verify
import run_analysis as RA

TAG = "Qwen3-4B"
raw = json.loads((HERE / "work" / "analysis_raw.json").read_text())
old = raw["per_checkpoint"][TAG]
band = tuple(raw["band"]["frozen"])
sub = json.loads((HERE / "items" / "substrate.json").read_text())
prereg, _ = verify(HERE / "work")

# the band choice itself re-runs off the sharded fit.npz
z = shard.load_npz(HARV := HERE / "harvest" / TAG / "fit.npz")
meta = json.loads((HERE / "harvest" / TAG / "meta.json").read_text())
prim = z["halves"] == 0
g2 = choose_band(z["early"][prim], z["labels"].astype(bool)[prim], z["pair_ids"][prim], meta["n_hs"])
assert tuple(g2["band"]) == band, (g2["band"], band)
print(f"band re-chosen off shards: {g2['band']} (matches frozen {list(band)}), d={g2['selected_d']:.4f}")

new = analyse_checkpoint(TAG, HERE / "harvest" / TAG, band, sub, prereg)
new["stability_A"] = RA.stability(HERE / "harvest" / TAG, band, "A")

checks = [
    ("G1 split-half cos", old["G1_split_half_cosine"]["mean_cosine"], new["G1_split_half_cosine"]["mean_cosine"]),
    ("G3 d cross-fitted", old["G3_positive_control"]["d_cross_fitted"], new["G3_positive_control"]["d_cross_fitted"]),
    ("K1 O", old["candidates"]["K1"]["early|F1|O"]["term_std"], new["candidates"]["K1"]["early|F1|O"]["term_std"]),
    ("K1 CB", old["candidates"]["K1"]["early|F1|CB"]["term_std"], new["candidates"]["K1"]["early|F1|CB"]["term_std"]),
    ("K1 A", old["candidates"]["K1"]["early|F1|A"]["term_std"], new["candidates"]["K1"]["early|F1|A"]["term_std"]),
    ("K1 T", old["candidates"]["K1"]["early|F1|T"]["term_std"], new["candidates"]["K1"]["early|F1|T"]["term_std"]),
    ("shuffled-label band A", old["G4_shuffled_label_null"]["A"]["abs_p975"], new["G4_shuffled_label_null"]["A"]["abs_p975"]),
    ("K2 prior", old["candidates"]["K2"]["prior"]["term_std"], new["candidates"]["K2"]["prior"]["term_std"]),
    ("K3 footprint", old["candidates"]["K3"]["footprint"]["value"], new["candidates"]["K3"]["footprint"]["value"]),
    ("K5 dispersion", old["candidates"]["K5"]["dispersion"], new["candidates"]["K5"]["dispersion"]),
    ("B1 AUROC", old["baselines"]["B1_diff_in_means_score"]["auroc_haz_vs_ben_prefix"],
                 new["baselines"]["B1_diff_in_means_score"]["auroc_haz_vs_ben_prefix"]),
    ("B2 probe AUROC", old["baselines"]["B2_raw_hidden_probe"]["auroc"], new["baselines"]["B2_raw_hidden_probe"]["auroc"]),
    ("cos(r_content,r_ablit)", old["cos_content_ablit"]["at_band"], new["cos_content_ablit"]["at_band"]),
    ("T==CB+A err", old["identity_checks"]["early|F1|T_eq_CB_plus_A_maxabs"],
                    new["identity_checks"]["early|F1|T_eq_CB_plus_A_maxabs"]),
    ("stability A cross-fit", old["stability_A"]["variants_term_std"]["cross_fitted_reserve_half"],
                              new["stability_A"]["variants_term_std"]["cross_fitted_reserve_half"]),
]
bad = 0
for name, a, b in checks:
    ok = (a is None and b is None) or np.isclose(a, b, rtol=0, atol=1e-9, equal_nan=True)
    bad += (not ok)
    print(f"  {'OK ' if ok else 'MISMATCH'}  {name:24s} before={a!r:>24}  after={b!r}")

# the per-position curve too (it comes from the sharded proj.npz)
pa, pb = old["position_curve"]["A_by_position"], new["position_curve"]["A_by_position"]
same = len(pa) == len(pb) and np.allclose(pa, pb, atol=1e-9, equal_nan=True)
print(f"  {'OK ' if same else 'MISMATCH'}  position curve ({len(pb)} positions from sharded proj.npz)")
bad += (not same)

# band search reads the sharded grid across all 28 bands
bs = RA.band_search(HERE / "harvest" / TAG, sub, "A")
print(f"  OK   band search over shards: best {bs['best_band']} term={bs['best_term_std']:.4f} "
      f"n_sig_holm={bs['n_bands_significant_holm']}")

assert bad == 0, f"{bad} mismatch(es)"
print("\nANALYSIS-OVER-SHARDS REPRODUCES THE UN-SHARDED RESULTS EXACTLY")
