"""STAGES 2-6 for ONE lineage: fit the pinned direction, then harvest the whole
battery at every alpha. Saves window-mean VECTORS so every direction-based
re-analysis (parent-fixed, per-state refit, 20 nulls, any post-hoc axis) is free.

usage: python src/run_lineage.py L2 [--alphas 0,0.25,0.5,0.75,1.0] [--items 96]
"""
from __future__ import annotations
import argparse, json, sys, time, gc
from pathlib import Path
import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).parent))
from common import (OUT, WINDOWS, LINEAGES, IS_INSTRUCT, ALPHAS, load_substrate,
                    unit, diff_in_means, cohens_d, cv_probe_auroc, random_unit_dirs,
                    save_sharded)
from engine import load_model, model_facts, Lesion, run_harvest, DEV
from seqbuild import build_all

HARV = OUT / "harvest"; HARV.mkdir(exist_ok=True, parents=True)


def save_state(path, S, H, band, k4_layers, dirs_extra=None, k4_proj=None, k4_proj_names=None):
    """Save exactly the layers each kind was actually harvested with - the damage
    probe needs the r_ablit layer, which sits OUTSIDE the frozen band."""
    d = {}
    for kind in ("item", "fit_content", "ladder", "neutral", "domain", "k4"):
        if kind not in H: continue
        for w in WINDOWS:
            for li in H[kind]["win"][w]:
                d[f"{kind}|win|{w}|{li}"] = H[kind]["win"][w][li]
        for li in H[kind]["last_prompt"]:
            d[f"{kind}|lastp|{li}"] = H[kind]["last_prompt"][li]
        d[f"{kind}|nll"] = H[kind]["nll_cont"]
        d[f"{kind}|norm"] = H[kind]["norm"]
    for kind in ("fit_ablit", "damage", "damage_matched"):
        if kind not in H: continue
        for li in H[kind]["last_prompt"]:
            d[f"{kind}|lastp|{li}"] = H[kind]["last_prompt"][li]
    if "k4" in H and k4_proj is not None:
        for li, P in k4_proj.items():
            d[f"k4|perposproj|{li}"] = P
        d["k4|projdir_names"] = np.array(k4_proj_names)
    if dirs_extra:
        d.update(dirs_extra)
    # Written as numbered parts, each under the 100 MB per-file deployment limit.
    # `path` is the stem; ShardedNpz reads the parts back transparently.
    save_sharded(path, d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lineage")
    ap.add_argument("--alphas", default=",".join(str(a) for a in ALPHAS))
    ap.add_argument("--items", type=int, default=None)
    ap.add_argument("--band", default=None)
    ap.add_argument("--perlayer", action="store_true",
                    help="DECLARED SECONDARY GRID: orthogonalise each layer's OWN r_ablit at that "
                         "layer, the faithful replica of the community recipe (STAGE 9b).")
    ap.add_argument("--tag", default=None, help="output prefix; defaults to the lineage id")
    args = ap.parse_args()
    LG = args.lineage
    TAG = args.tag or (LG + ("PL" if args.perlayer else ""))
    alphas = [float(x) for x in args.alphas.split(",")]
    sub = load_substrate()
    pilot = json.loads((OUT / "pilot.json").read_text())
    band = [int(x) for x in args.band.split(",")] if args.band else pilot["band"]
    k4_layers = [band[0], band[len(band) // 2], band[-1]]

    t0 = time.time()
    meta = {"lineage": LG, "tag": TAG, "repo": LINEAGES[LG], "band": band,
            "k4_layers": k4_layers, "alphas": alphas, "timings": {},
            "grid": "per_layer_r_ablit" if args.perlayer else "single_pinned_r_ablit"}
    model, tok = load_model(LINEAGES[LG])
    meta["model_facts"] = model_facts(model, tok)
    NL = meta["model_facts"]["n_layers"]
    ALL = list(range(NL))
    S, P = build_all(sub, tok, IS_INSTRUCT[LG], n_items=args.items)
    meta["n_seqs"] = {k: len(v) for k, v in S.items()}
    meta["think_close_token_id"] = P.think_close_id
    if IS_INSTRUCT[LG]:
        ok = all(P.think_close_id in s.input_ids[:s.prompt_len] for s in S["item"][:50])
        meta["T1_think_close_present"] = bool(ok)
        assert ok, "F8: no </think> in instruct sequence"
    else:
        meta["T1_think_close_present"] = None
    print(f"[{TAG}] seqs {meta['n_seqs']}  band {band}", flush=True)

    # ---------- r_ablit: fitted on the alpha=0 parent ONLY, then PINNED ----------
    tA = time.time()
    Habl0 = run_harvest(model, tok, S["fit_ablit"], ALL, WINDOWS)
    meta["timings"]["ablit_fit_s"] = time.time() - tA
    y = np.array([s.meta["label"] for s in S["fit_ablit"]])
    ra, rasep = {}, {}
    for li in ALL:
        X = Habl0["last_prompt"][li].astype(np.float32)
        v = unit(diff_in_means(X[y == 1], X[y == 0])); ra[li] = v
        rasep[li] = cohens_d(X[y == 1] @ v, X[y == 0] @ v)
    pick = max(ALL, key=lambda l: rasep[l])
    u = ra[pick]
    meta["r_ablit_layer"] = pick
    meta["r_ablit_sep"] = {str(k): float(v) for k, v in rasep.items()}
    np.savez_compressed(HARV / f"{TAG}_dirs.npz", u=u,
                        **{f"ra_{li}": ra[li] for li in ALL})
    print(f"[{TAG}] r_ablit layer {pick} d={rasep[pick]:.2f}", flush=True)

    rc_parent = [None]                          # r_content of the alpha=0 state, pinned
    bandp = sorted(set(band + [pick]))          # frozen band + the r_ablit layer
    meta["band_plus_pick"] = bandp
    if args.perlayer:
        les = Lesion(model, {li: torch.tensor(ra[li], dtype=torch.float32) for li in ALL})
        meta["perlayer_cos_vs_pinned_u"] = {str(li): float(abs(ra[li] @ u)) for li in ALL}
    else:
        les = Lesion(model, torch.tensor(u, dtype=torch.float32))
    meta["weight_space_norms"] = les.weight_space_norms()
    emb_sum_before = float(model.get_input_embeddings().weight.detach().float().sum())

    # ---------- harvest the battery at every alpha ----------
    for a in alphas:
        ta = time.time()
        H = {}
        H["fit_content"] = run_harvest(model, tok, S["fit_content"], bandp, WINDOWS, lesion=les, alpha=a)
        H["item"] = run_harvest(model, tok, S["item"], bandp, WINDOWS, lesion=les, alpha=a)
        H["damage"] = run_harvest(model, tok, S["damage"], bandp, WINDOWS, lesion=les, alpha=a)
        H["neutral"] = run_harvest(model, tok, S["neutral"], bandp, WINDOWS, lesion=les, alpha=a)
        H["ladder"] = run_harvest(model, tok, S["ladder"], bandp, WINDOWS, lesion=les, alpha=a)
        H["domain"] = run_harvest(model, tok, S["domain"], bandp, WINDOWS, lesion=les, alpha=a)
        H["k4"] = run_harvest(model, tok, S["k4"], bandp, WINDOWS, lesion=les, alpha=a,
                              per_pos_layers=k4_layers)
        H["fit_ablit"] = run_harvest(model, tok, S["fit_ablit"], bandp, WINDOWS,
                                     lesion=les, alpha=a)
        if "damage_matched" in S:
            H["damage_matched"] = run_harvest(model, tok, S["damage_matched"],
                                              bandp, WINDOWS, lesion=les, alpha=a)
        # K4 needs PROJECTIONS over the fixed continuation, not 378 MB of raw vectors.
        # fit_content is harvested first, so this state's r_content is already available.
        haz = [i for i, sq in enumerate(S["fit_content"]) if sq.meta["prefix"] == "hazardous"]
        ben = [i for i, sq in enumerate(S["fit_content"]) if sq.meta["prefix"] == "benign"]
        rc_state = {}
        for li in band:
            A = H["fit_content"]["win"]["EARLY"][li][haz].astype(np.float32)
            B = H["fit_content"]["win"]["EARLY"][li][ben].astype(np.float32)
            v = A.mean(0) - B.mean(0)
            rc_state[li] = v / (np.linalg.norm(v) + 1e-12)
        if rc_parent[0] is None:
            rc_parent[0] = {li: rc_state[li].copy() for li in band}
        nulls = random_unit_dirs(len(u), 20, f"k4nulls|{LG}")
        k4_proj, names = {}, None
        for li in k4_layers:
            P = H["k4"]["perpos"][li].astype(np.float32)            # [n, cont, d]
            dirs = [rc_parent[0][li], rc_state[li], u] + list(nulls)
            names = ["r_content_parent", "r_content_state", "r_ablit"] + [f"null{j}" for j in range(20)]
            k4_proj[li] = np.einsum("ntd,kd->ntk", P, np.stack(dirs)).astype(np.float32)
        save_state(HARV / f"{TAG}_a{a:.2f}", S, H, bandp, k4_layers,
                   k4_proj=k4_proj, k4_proj_names=names)
        meta["timings"][f"alpha_{a:.2f}_s"] = time.time() - ta
        print(f"[{TAG}] alpha {a:.2f} done in {time.time()-ta:.0f}s", flush=True)
        del H; gc.collect(); torch.cuda.empty_cache()

    meta["T3_embed_tokens_unmodified"] = bool(
        emb_sum_before == float(model.get_input_embeddings().weight.detach().float().sum()))
    meta["peak_vram_gb"] = torch.cuda.max_memory_allocated() / 1e9
    meta["total_s"] = time.time() - t0
    # sequence index (sid + meta) so analysis can key-join without the tokenizer
    idx = {k: [{"sid": s.sid, "prompt_len": s.prompt_len, "cont_len": s.cont_len, **s.meta}
               for s in v] for k, v in S.items()}
    (HARV / f"{TAG}_index.json").write_text(json.dumps(idx))
    (HARV / f"{TAG}_meta.json").write_text(json.dumps(meta, indent=1, default=str))
    print(f"[{TAG}] TOTAL {meta['total_s']:.0f}s  peakVRAM {meta['peak_vram_gb']:.1f}GB", flush=True)


if __name__ == "__main__":
    main()
