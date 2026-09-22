#!/usr/bin/env python3
"""Exercise the whole analysis path against the smoke harvest, before the 4B panel runs."""
import json, sys, traceback
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import numpy as np
from loguru import logger
from lane_a.pipeline_analysis import analyse_checkpoint, choose_band, build_s1_table
from lane_a.prereg import verify
import run_analysis as RA

tag = "Qwen3-0.6B"
hdir = HERE / "harvest" / "_smoke" / tag
sub = json.loads((HERE / "items" / "substrate.json").read_text())
meta = json.loads((hdir / "meta.json").read_text())
sub["confirmatory_items"] = sub["confirmatory_items"][: meta["n_items"]]
prereg, sha = verify(HERE / "work")

z = shard.load_npz(hdir / "fit.npz")
fe, lab, half, pair = z["early"], z["labels"].astype(bool), z["halves"], z["pair_ids"]
prim = half == 0
g2 = choose_band(fe[prim], lab[prim], pair[prim], meta["n_hs"])
band = (g2["band"][0], g2["band"][1])
print("band:", band, "d:", round(g2["selected_d"], 3))

res = analyse_checkpoint(tag, hdir, band, sub, prereg)
res["stability_A"] = RA.stability(hdir, band, "A")
print("G1 split-half cosine:", round(res["G1_split_half_cosine"]["mean_cosine"], 3))
print("G3 d in-sample:", round(res["G3_positive_control"]["d_in_sample"], 3),
      "cross-fitted:", round(res["G3_positive_control"]["d_cross_fitted"], 3))
print("K1 terms (early|F1):", {t: round(res["candidates"]["K1"][f"early|F1|{t}"]["term_std"], 3)
                               for t in ("O", "CB", "A", "T")})
print("identity T==CB+A maxabs:", res["identity_checks"]["early|F1|T_eq_CB_plus_A_maxabs"])
print("nullSD early|F1|A:", round(res["nullsd_table"]["early|F1|A"]["per_item"], 5))
print("K2 prior/slope:", round(res["candidates"]["K2"]["prior"]["term_std"], 3),
      round(res["candidates"]["K2"]["slope"]["term_std"], 3))
print("K3 footprint:", round(res["candidates"]["K3"]["footprint"]["value"], 3),
      "stable_rank:", round(res["candidates"]["K3"]["stable_rank"]["mean_at_band"], 2))
print("K4:", {k: res["candidates"]["K4"][k] for k in ("tau", "r2", "method")})
print("K5 dispersion:", round(res["candidates"]["K5"]["dispersion"], 3))
print("baselines B1 auroc:", round(res["baselines"]["B1_diff_in_means_score"]["auroc_haz_vs_ben_prefix"], 3),
      "B2 probe:", round(res["baselines"]["B2_raw_hidden_probe"]["auroc"], 3))
print("cos(r_content,r_ablit) at band:", round(res["cos_content_ablit"]["at_band"], 4))
print("G5 TOST:", res["G5_placebo"]["tost_margin_0.40"])
print("G6 licensed:", res["G6_nll_match"]["subtraction_licensed"],
      "saf_pen", round(res["G6_nll_match"]["safety_offdiagonal_penalty"], 4),
      "coh_pen", round(res["G6_nll_match"]["coherence_offdiagonal_penalty"], 4))
print("A_net:", res["A_net"]["kind"], round(res["A_net"]["term_std"], 3))
print("position curve A early/late:", round(res["position_curve"]["A_early_std"], 3),
      round(res["position_curve"]["A_late_std"], 3),
      "n_pos:", len(res["position_curve"].get("A_by_position", [])))
print("stability A:", res["stability_A"])

bs = RA.band_search(hdir, sub, "A")
print("band search best:", bs["best_band"], round(bs["best_term_std"], 3),
      "n_sig_holm:", bs["n_bands_significant_holm"])
s1 = build_s1_table({tag: res}, prereg, {"Qwen3-4B": tag, "Qwen3-4B-SafeRL": tag},
                    (tag,), {tag: {}})
print("S1 rows:", [(r["candidate"], r.get("S1")) for r in s1])
print("\nANALYSIS SMOKE OK")
