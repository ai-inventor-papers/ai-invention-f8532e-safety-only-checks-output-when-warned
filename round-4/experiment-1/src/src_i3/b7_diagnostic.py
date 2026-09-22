"""ADDITIONAL DIAGNOSTIC (post-prereg, not pre-registered): is B7's weights-only 'shared null direction' an
abliteration scar or an architecture artefact?

B7 (= iteration-2 BL7_JORAK_A, the Jorak Model Scanner's A statistic) stacks every block's least-singular left
vector of the write matrix M_l = [o_proj | down_proj] and reports sigma_1(stack) / sqrt(L): 1 when every block
shares one null direction. results/b7_null_direction_diagnostic.json shows that in AMD-OLMo (base, SFT, SFT-DPO)
every block's null vector IS the all-ones direction 1/sqrt(d) (|cos| 0.999): OLMo-1 uses a parameter-free,
mean-subtracting LayerNorm before every read, so the residual component along 1 is invisible downstream and no
block is trained to write along it. That is an architecture-mandated null, not an edit.

B7_ones_projected repeats B7 after removing that direction from every block's Gram: G'_l = P G_l P + c 11^T/d
with P = I - 11^T/d and c = trace(G_l)/d (pushes the all-ones eigenvalue out of the bottom of the spectrum), then
the least eigenvector of G'_l per block, stacked, sigma_1 / sqrt(L). For a model whose nulls are not along 1 the
value is essentially unchanged. Writes results/b7_diagnostic.json.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import scipy.linalg as sla

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import HARVEST, RESULTS, jdump, jload, setup_logging, utc_now  # noqa: E402
from loguru import logger  # noqa: E402


def least_vec(G: np.ndarray, project_ones: bool) -> np.ndarray:
    d = G.shape[0]
    if project_ones:
        one = np.ones(d) / np.sqrt(d)
        Gp = G - np.outer(one, one @ G) - np.outer(G @ one, one) + np.outer(one, one) * float(one @ G @ one)
        Gp += np.outer(one, one) * (np.trace(G) / d)
        G = 0.5 * (Gp + Gp.T)
    w, v = sla.eigh(G, subset_by_index=[0, 0], driver="evr")
    return v[:, 0]


def b7_from(vecs: np.ndarray) -> float:
    U = vecs / np.maximum(np.linalg.norm(vecs, axis=1, keepdims=True), 1e-12)
    return float(np.linalg.svd(U, compute_uv=False)[0] / np.sqrt(U.shape[0]))


def main() -> int:
    setup_logging("b7_diagnostic")
    feats = jload(RESULTS / "features.json")
    truth = jload(RESULTS / "graded_truth.json")
    tags = {r: r.replace("/", "--") for r in feats["features"]}
    if feats.get("random_init_tag"):
        tags["RANDOM_INIT"] = feats["random_init_tag"]
    rows = {}
    for repo, tag in tags.items():
        t0 = time.time()
        gp = sorted((HARVEST / tag / "gram").glob("G_*.npy"))
        v_raw, v_proj = [], []
        for g in gp:
            G = np.load(g).astype(np.float64)
            v_raw.append(least_vec(G, False))
            v_proj.append(least_vec(G, True))
        v_raw, v_proj = np.array(v_raw), np.array(v_proj)
        d = v_raw.shape[1]
        one = np.ones(d) / np.sqrt(d)
        rows[repo] = {"tag": tag, "L": len(gp), "B7_recomputed_from_gram": b7_from(v_raw),
                      "B7_preregistered": (feats["features"].get(repo) or feats.get("random_init") or {}).get("B7"),
                      "B7_ones_projected": b7_from(v_proj),
                      "mean_abs_cos_null_with_all_ones": float(np.abs(v_raw @ one).mean()),
                      "harmful_compliance": (truth["per_ckpt"].get(repo) or {}).get("outcomes_primary_laneC_items", {}).get("harmful_compliance")}
        logger.info(f"{repo}: B7 {rows[repo]['B7_recomputed_from_gram']:.3f} -> ones-projected {rows[repo]['B7_ones_projected']:.3f} "
                    f"({time.time() - t0:.0f}s)")
    from scipy.stats import spearmanr
    panel = [r for r in rows if r != "RANDOM_INIT"]
    hc = [rows[r]["harmful_compliance"] for r in panel]
    res = {"utc": utc_now(), "status": "ADDITIONAL, post-prereg, not pre-registered; diagnostic of a prereg'd bar",
           "rows": rows,
           "rho_hc_B7_preregistered": float(spearmanr([rows[r]["B7_preregistered"] for r in panel], hc).statistic),
           "rho_hc_B7_recomputed": float(spearmanr([rows[r]["B7_recomputed_from_gram"] for r in panel], hc).statistic),
           "rho_hc_B7_ones_projected": float(spearmanr([rows[r]["B7_ones_projected"] for r in panel], hc).statistic),
           "n": len(panel),
           "note": "B7_recomputed_from_gram uses the stored fp16 Gram (eigh), the preregistered B7 uses the harvest's "
                   "vmin_stacked (float32 Gram from the native-precision weights); small differences are precision"}
    jdump(res, RESULTS / "b7_diagnostic.json")
    logger.info(f"rho(HC): prereg B7 {res['rho_hc_B7_preregistered']:.3f}, recomputed {res['rho_hc_B7_recomputed']:.3f}, "
                f"ones-projected {res['rho_hc_B7_ones_projected']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
