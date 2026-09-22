"""STAGE 1 pilot on L2 + tests T1/T2/T3 + band selection (frozen for every lineage)."""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from common import (OUT, WINDOWS, CONT_LEN, LINEAGES, IS_INSTRUCT, load_substrate,
                    random_unit_dirs, unit, diff_in_means, cohens_d, N_NULL_DIRS)
from engine import load_model, model_facts, Lesion, equivalence_check, run_harvest, DEV
from seqbuild import build_all

BAND_N = 9


def fit_rcontent_per_layer(H, seqs, layers, window="EARLY", idx_subset=None):
    """diff-in-means (hazardous - benign) of window-mean residuals, unit-normalised."""
    haz = [i for i, s in enumerate(seqs) if s.meta["prefix"] == "hazardous"]
    ben = [i for i, s in enumerate(seqs) if s.meta["prefix"] == "benign"]
    if idx_subset is not None:
        ss = set(idx_subset)
        haz = [i for i in haz if seqs[i].meta["fit_id"] in ss]
        ben = [i for i in ben if seqs[i].meta["fit_id"] in ss]
    dirs = {}
    for li in layers:
        A = H["win"][window][li][haz].astype(np.float32)
        B = H["win"][window][li][ben].astype(np.float32)
        dirs[li] = unit(diff_in_means(A, B))
    return dirs, haz, ben


def sep_on(H, seqs, li, d, window, idx_subset):
    ss = set(idx_subset)
    haz = [i for i, s in enumerate(seqs) if s.meta["prefix"] == "hazardous" and s.meta["fit_id"] in ss]
    ben = [i for i, s in enumerate(seqs) if s.meta["prefix"] == "benign" and s.meta["fit_id"] in ss]
    a = H["win"][window][li][haz].astype(np.float32) @ d
    b = H["win"][window][li][ben].astype(np.float32) @ d
    return cohens_d(a, b)


def main():
    t0 = time.time()
    sub = load_substrate()
    log = {"stage": "pilot", "lineage": "L2", "repo": LINEAGES["L2"]}

    model, tok = load_model(LINEAGES["L2"])
    facts = model_facts(model, tok)
    log["model_facts"] = facts
    print("MODEL FACTS", json.dumps(facts))
    NL, D = facts["n_layers"], facts["d_model"]
    ALL = list(range(NL))

    S, P = build_all(sub, tok, IS_INSTRUCT["L2"], n_items=24)

    # ---------------- T1 TOKENISATION AND SPANS ----------------
    t1 = {}
    think_id = P.think_close_id
    t1["think_close_token_id"] = think_id
    sample = S["item"][:20]
    has_think = [think_id in s.input_ids[:s.prompt_len] for s in sample]
    t1["all_instruct_seqs_have_think_close"] = bool(all(has_think))
    pos = [s.input_ids[:s.prompt_len].index(think_id) for s in sample if think_id in s.input_ids[:s.prompt_len]]
    t1["early_window_strictly_after_think"] = bool(
        all(s.prompt_len + WINDOWS["EARLY"][0] > p for s, p in zip(sample, pos)))
    t1["cont_len_all_equal"] = bool(len({s.cont_len for s in S["item"]}) == 1)
    t1["cont_len"] = S["item"][0].cont_len
    # four cells of an item share token-identical continuation ids
    by_item = {}
    for s in S["item"]:
        if s.meta["prefix"] in ("hazardous", "benign"):
            by_item.setdefault((s.meta["pair_key"], s.meta["family"], s.meta["prefix"]), []).append(s)
    t1["cells_token_identical_within_prefix_level"] = bool(all(
        len({tuple(x.input_ids[x.prompt_len:]) for x in v}) == 1 for v in by_item.values()))
    t1["prefix_token_len_identical_across_all_four_cells"] = bool(len(
        {s.cont_len for s in S["item"] if s.meta["prefix"] in ("hazardous", "benign")}) == 1)
    print("T1", json.dumps(t1))
    log["T1"] = t1

    # ---------------- BAND SELECTION on the FITTING CORPUS ONLY ----------------
    tA = time.time()
    Hfit = run_harvest(model, tok, S["fit_content"], ALL, WINDOWS)
    log["timing_fitpass_s"] = time.time() - tA
    n_fit = len(sub["fit_content"])
    half = n_fit // 2
    ids_a, ids_b = list(range(half)), list(range(half, n_fit))
    dA, _, _ = fit_rcontent_per_layer(Hfit, S["fit_content"], ALL, "EARLY", ids_a)
    dB, _, _ = fit_rcontent_per_layer(Hfit, S["fit_content"], ALL, "EARLY", ids_b)
    split_cos = {li: float(abs(dA[li] @ dB[li])) for li in ALL}
    stable_sep = {li: float(0.5 * (sep_on(Hfit, S["fit_content"], li, dA[li], "EARLY", ids_b)
                                   + sep_on(Hfit, S["fit_content"], li, dB[li], "EARLY", ids_a)))
                  for li in ALL}
    best, best_score = None, -1e9
    for st in range(NL - BAND_N + 1):
        band = list(range(st, st + BAND_N))
        sc = float(np.mean([stable_sep[l] * min(split_cos[l] / 0.70, 1.0) for l in band]))
        if sc > best_score:
            best, best_score = band, sc
    log["band"] = best
    log["band_depth_fraction"] = [best[0] / NL, (best[-1] + 1) / NL]
    log["band_score"] = best_score
    log["split_half_cosine_per_layer"] = split_cos
    log["stable_sep_per_layer"] = stable_sep
    log["r_content_split_half_cosine_band_mean"] = float(np.mean([split_cos[l] for l in best]))
    log["r_content_stability_gate_pass"] = bool(log["r_content_split_half_cosine_band_mean"] >= 0.70)
    print("BAND", best, "score", round(best_score, 3),
          "split-half cos", round(log["r_content_split_half_cosine_band_mean"], 3))

    # full-corpus r_content on the band
    rc, _, _ = fit_rcontent_per_layer(Hfit, S["fit_content"], best, "EARLY")

    # ---------------- r_ablit ----------------
    tA = time.time()
    Habl = run_harvest(model, tok, S["fit_ablit"], ALL, WINDOWS)
    log["timing_ablpass_s"] = time.time() - tA
    ylab = np.array([s.meta["label"] for s in S["fit_ablit"]])
    ra_layer, ra_sep = {}, {}
    for li in ALL:
        X = Habl["last_prompt"][li].astype(np.float32)
        v = unit(diff_in_means(X[ylab == 1], X[ylab == 0]))
        ra_layer[li] = v
        ra_sep[li] = cohens_d(X[ylab == 1] @ v, X[ylab == 0] @ v)
    pick = max(ALL, key=lambda l: ra_sep[l])
    u = ra_layer[pick]
    log["r_ablit_layer"] = pick
    log["r_ablit_sep_per_layer"] = {str(k): float(v) for k, v in ra_sep.items()}
    print("r_ablit layer", pick, "d =", round(ra_sep[pick], 2))

    # ---------------- G1: cos(r_content, r_ablit) -- a RESULT, not only a gate ----
    g1 = {str(li): float(abs(rc[li] @ u)) for li in best}
    pooled = unit(np.mean([rc[li] for li in best], 0))
    g1_pooled = float(abs(pooled @ u))
    log["G1_cos_per_layer"] = g1
    log["G1_cos_pooled"] = g1_pooled
    log["G1_max"] = max(g1.values())
    log["G1_pass"] = bool(log["G1_max"] <= 0.50)
    print("G1 |cos(r_content, r_ablit)| pooled", round(g1_pooled, 3), "max", round(log["G1_max"], 3),
          "PASS" if log["G1_pass"] else "FAIL")

    # ---------------- T2 HARVEST CORRECTNESS ----------------
    t2 = {}
    t2["hooks_fired_shape"] = list(Hfit["win"]["EARLY"][best[0]].shape)
    t2["hooks_nonzero_frac"] = float((np.abs(Hfit["win"]["EARLY"][best[0]]).sum(1) > 0).mean())
    five = S["fit_content"][:5]
    r1 = run_harvest(model, tok, five, best[:2], WINDOWS)
    r2 = run_harvest(model, tok, five, best[:2], WINDOWS)
    a = r1["win"]["EARLY"][best[0]].astype(np.float32); b = r2["win"]["EARLY"][best[0]].astype(np.float32)
    t2["determinism_rel"] = float(np.abs(a - b).max() / (np.abs(a).max() + 1e-9))
    rb1 = run_harvest(model, tok, five, best[:2], WINDOWS, max_bs=1)
    c = rb1["win"]["EARLY"][best[0]].astype(np.float32)
    t2["batch_invariance_rel"] = float(np.abs(a - c).max() / (np.abs(a).max() + 1e-9))
    print("T2", json.dumps({k: (round(v, 5) if isinstance(v, float) else v) for k, v in t2.items()}))
    log["T2"] = t2

    # ---------------- CONFIRMATION SIGNAL (before spending the budget) ----------
    tA = time.time()
    Hit = run_harvest(model, tok, S["item"], best, WINDOWS)
    log["timing_itempass_s"] = time.time() - tA
    log["timing_item_seqs"] = len(S["item"])
    nulls = random_unit_dirs(D, N_NULL_DIRS, "nulls|L2")

    def band_proj(Hd, idxs, d_by_layer):
        return np.mean([Hd["win"]["EARLY"][li][idxs].astype(np.float32) @ d_by_layer[li]
                        for li in best], 0)

    meta = [s.meta for s in S["item"]]
    def sel(**kw):
        return [i for i, m in enumerate(meta) if all(m.get(k) == v for k, v in kw.items())]

    cb_items, cb_null = [], []
    pks = sorted({m["pair_key"] for m in meta})
    for pk in pks:
        h = sel(pair_key=pk, prefix="hazardous", request="benign")
        b_ = sel(pair_key=pk, prefix="benign", request="benign")
        cb_items.append(float(band_proj(Hit, h, rc).mean() - band_proj(Hit, b_, rc).mean()))
        nd = []
        for k in range(N_NULL_DIRS):
            dk = {li: nulls[k] for li in best}
            nd.append(float(band_proj(Hit, h, dk).mean() - band_proj(Hit, b_, dk).mean()))
        cb_null.append(float(np.std(nd, ddof=1)))
    cb_items = np.array(cb_items); cb_null = np.array(cb_null)
    z = cb_items / np.maximum(cb_null, 1e-9)
    log["confirmation_CB_z_mean"] = float(z.mean())
    log["confirmation_CB_z_median"] = float(np.median(z))
    log["confirmation_pass_gt_1_nullSD"] = bool(abs(z.mean()) > 1.0)
    log["achieved_r_SDreal_over_SDnull"] = float(np.std(cb_items, ddof=1) / np.mean(cb_null))
    print("CONFIRMATION: CB in null-SD units, mean z =", round(float(z.mean()), 2),
          "PASS" if log["confirmation_pass_gt_1_nullSD"] else "FAIL")

    # ---------------- T3 EDIT AND HOOK SANITY ----------------
    t3 = {}
    ids = torch.tensor([S["item"][0].input_ids[:80]]).to(DEV)
    msk = torch.ones_like(ids)
    ut = torch.tensor(u, dtype=torch.float32)
    emb_before = model.get_input_embeddings().weight.detach().float().sum().item()
    eq = equivalence_check(model, ut, 1.0, ids, msk)
    t3["equivalence_hook_vs_weight_edit"] = eq
    les = Lesion(model, ut)
    with torch.inference_mode(), les:
        les.set_alpha(0.0)
        l0 = model(input_ids=ids, attention_mask=msk).logits.clone()
    with torch.inference_mode():
        lbase = model(input_ids=ids, attention_mask=msk).logits
    t3["alpha0_is_bitwise_noop"] = bool(torch.equal(l0, lbase))
    emb_after = model.get_input_embeddings().weight.detach().float().sum().item()
    t3["embed_tokens_unmodified"] = bool(emb_before == emb_after)
    t3["lm_head_is_embed_tokens"] = facts["lm_head_is_embed_tokens"]
    t3["weight_norms"] = les.weight_space_norms()
    print("T3", json.dumps({k: v for k, v in t3.items() if k != "weight_norms"}, default=str))

    # monotonicity of D(alpha) on the held-out damage set
    dmg = S["damage"]
    ydm = np.array([s.meta["label"] for s in dmg])
    Dcurve = []
    for a in [0.0, 0.5, 1.0]:
        Hd = run_harvest(model, tok, dmg, [pick], WINDOWS, lesion=les, alpha=a)
        X = Hd["last_prompt"][pick].astype(np.float32)
        Dcurve.append(float(np.mean([__import__("common").cv_probe_auroc(X, ydm, tag=f"fold|{f}")
                                     for f in range(1)])))
    t3["D_alpha_0_05_1"] = Dcurve
    t3["D_monotone_nonincreasing"] = bool(Dcurve[0] >= Dcurve[1] - 1e-6 >= Dcurve[2] - 2e-6)
    print("D(alpha) @ {0,0.5,1} =", [round(x, 4) for x in Dcurve],
          "monotone" if t3["D_monotone_nonincreasing"] else "NON-MONOTONE")
    log["T3"] = t3

    log["timing_total_s"] = time.time() - t0
    log["peak_vram_gb"] = torch.cuda.max_memory_allocated() / 1e9
    (OUT / "pilot.json").write_text(json.dumps(log, indent=1, default=str))
    np.savez_compressed(OUT / "pilot_dirs.npz",
                        u=u, **{f"rc_{li}": rc[li] for li in best})
    print("PEAK VRAM GB", round(log["peak_vram_gb"], 2), "TOTAL s", round(log["timing_total_s"], 1))


if __name__ == "__main__":
    main()
