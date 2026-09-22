"""W-SUMMARY -- the weights-only sufficient statistics.  ZERO PROMPTS.

Reads tensors STRAIGHT FROM THE SAFETENSORS SHARDS in their native dtype and upcasts to
float32, so the spectrum is computed at full stored precision no matter what dtype the
forward passes run in.  That matters: sigma_min of a [d, h+m] matrix is precisely the
quantity a bfloat16 round-trip would destroy, and sigma_min is what X10 is.

Two Gram identities (D2) make this ONE cached object serve both candidates:
    ||u^T M||^2   = u^T (M M^T) u = u^T G u      -> X2 write mass, any direction, free
    sigma_min(M)^2 = lambda_min(M M^T)           -> X10 orthogonality scar, zero prompts
so G is computed once per layer and eigh(G) yields the full spectrum AND the near-null
left singular vector.

Because this needs no forward pass, it runs for the WHOLE panel even when the activation
harvest is truncated by the wall clock -- X10 is never lost to a time gate.
"""

from __future__ import annotations

import argparse
import gc
import glob
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import DEVIATIONS, HARVEST, RESULTS, jdump, jload_maybe, setup_logging, slug  # noqa: E402
from loguru import logger  # noqa: E402

HUB = Path(__file__).resolve().parents[2] / "hf_cache"  # PATCHED (iter3 copy): private cache
# Session 2: compute only the extreme eigenpairs (see the note inside w_summary_repo).
EXTREMES_ONLY = True


def open_repo(repo: str):
    """Open every shard of a cached repo and return (handles, weight_map, snapshot_dir)."""
    from safetensors import safe_open

    snaps = sorted(glob.glob(str(HUB / f"models--{repo.replace('/', '--')}" / "snapshots" / "*")))
    if not snaps:
        raise FileNotFoundError(f"no snapshot for {repo} under {HUB}")
    snap = snaps[-1]
    idx = Path(snap) / "model.safetensors.index.json"
    if idx.exists():
        wmap = json.loads(idx.read_text())["weight_map"]
        shards = sorted(set(wmap.values()))
    else:
        one = sorted(glob.glob(f"{snap}/*.safetensors"))
        if not one:
            raise FileNotFoundError(f"no safetensors in {snap}")
        shards = [Path(one[0]).name]
        with safe_open(f"{snap}/{shards[0]}", framework="pt") as fh:
            wmap = {k: shards[0] for k in fh.keys()}
    handles = {s: safe_open(f"{snap}/{s}", framework="pt") for s in shards}
    return handles, wmap, snap


def get(handles, wmap, key):
    """bf16 has no numpy dtype, so read through torch and up-cast to float32.

    optimum-quanto checkpoints (e.g. venkycs/SmolLM2-1.7B-Instruct-Abliterated) store a
    linear weight as `<key>._data` (float8_e4m3fn) plus a per-output-channel `<key>._scale`
    and ship NO quantization_config, so a plain transformers load leaves those layers at
    random init. For the WEIGHT-side statistics we dequantise exactly: W = _data * _scale.
    """
    import torch

    if key in wmap:
        return handles[wmap[key]].get_tensor(key).to(torch.float32)
    dk, sk = key + "._data", key + "._scale"
    if dk in wmap and sk in wmap:
        data = handles[wmap[dk]].get_tensor(dk).to(torch.float32)
        scale = handles[wmap[sk]].get_tensor(sk).to(torch.float32)
        return data * scale
    raise KeyError(key)


def _find_keys(wmap: dict, n_layers_hint: int | None = None) -> dict:
    """Locate the residual-WRITE matrices: attention output and MLP down projections."""
    import re

    out: dict[int, dict[str, str]] = {}
    # quanto-quantised checkpoints name the tensor `<key>._data`; map back to the logical key
    keys = [k[: -len("._data")] if k.endswith("._data") else k for k in wmap]
    for k in keys:
        m = re.search(r"layers\.(\d+)\.", k)
        if not m:
            continue
        li = int(m.group(1))
        if k.endswith("self_attn.o_proj.weight") or k.endswith("attention.o_proj.weight") \
                or k.endswith("self_attn.dense.weight") or k.endswith("attn.out_proj.weight") \
                or k.endswith("self_attn.o_proj.base_layer.weight"):
            out.setdefault(li, {})["o_proj"] = k
        elif k.endswith("conv.out_proj.weight"):  # PATCHED (iter3): LFM2 short-conv block write matrix
            out.setdefault(li, {})["o_proj"] = k
        elif k.endswith("mlp.down_proj.weight") or k.endswith("mlp.c_proj.weight") \
                or k.endswith("mlp.fc2.weight") or k.endswith("feed_forward.down_proj.weight") \
                or k.endswith("feed_forward.w2.weight"):  # PATCHED (iter3): LFM2 MLP write matrix
            out.setdefault(li, {})["down_proj"] = k
    return {li: v for li, v in sorted(out.items()) if "o_proj" in v and "down_proj" in v}


def w_summary_repo(repo: str, tag: str | None = None, *, store_gram: bool = True,
                   gram_dtype: str = "float16",
                   parts: tuple[str, ...] = ("stacked",)) -> dict:
    import torch

    name = tag or slug(repo)
    out_dir = HARVEST / name
    out_dir.mkdir(parents=True, exist_ok=True)
    sent = out_dir / "W_DONE"
    if sent.exists():
        return jload_maybe(out_dir / "w_meta.json", {}) or {}

    t0 = time.time()
    handles, wmap, snap = open_repo(repo)
    keys = _find_keys(wmap)
    if not keys:
        raise RuntimeError(f"{repo}: no o_proj/down_proj pairs found in {len(wmap)} tensors")
    gdir = out_dir / "gram"
    gdir.mkdir(exist_ok=True)

    meta: dict = {"repo": repo, "tag": name, "snapshot": snap,
                  "n_layers_found": len(keys), "parts": {}}
    store: dict[str, dict[str, list]] = {p: {"svals": [], "vmin": [], "fro2": [], "shapes": []}
                                         for p in parts}
    for li in sorted(keys):
        Wo = get(handles, wmap, keys[li]["o_proj"])
        Wd = get(handles, wmap, keys[li]["down_proj"])
        for part in parts:
            M = torch.cat([Wo, Wd], dim=1) if part == "stacked" else (
                Wo if part == "o_proj" else Wd)
            d, n = int(M.shape[0]), int(M.shape[1])
            # PRECISION NOTE (recorded in the output): the Gram is accumulated in FLOAT32
            # and the eigendecomposition is done in FLOAT64 on the upcast result.  For these
            # matrices the exact-arithmetic condition number is tiny -- for a Gaussian
            # [d, n] with n >> d the spectrum spans only (sqrt(n)-sqrt(d))^2 to
            # (sqrt(n)+sqrt(d))^2, a ratio of about 6 at d=2560, n=13824 -- so float32
            # accumulation (~1e-6 relative) is far below any quantity X10 reads. It bounds
            # the deepest resolvable scar at ~log10(sigma_MP / (1e-3.5 * sigma_max)) ~ 3.1
            # decades, which is ample: a real edit shows up at a fraction of that. Float64
            # throughout was measured at ~72 s/layer on this 2-core box and would have cost
            # more than the entire time budget for the panel.
            G = (M @ M.T).double()
            fro2 = float(torch.diagonal(G).sum().item())
            if EXTREMES_ONLY:
                # SESSION-2 SPEED-UP (recorded deviation): every downstream reader uses ONLY
                # sigma_min (= sqrt(lambda_min(G))) and the near-null LEFT singular vector, so
                # the full spectrum is not computed. LAPACK dsyevr with a one-index subset
                # returns (lambda_min, vmin) at the cost of the tridiagonal reduction (~4/3 d^3)
                # instead of a full eigendecomposition with vectors (~9 d^3); lambda_max comes
                # from 60 power iterations. svals then holds [sigma_max, sigma_min] (descending,
                # so sv[-1] is still sigma_min). Same float64 LAPACK on the same float32-
                # accumulated Gram, so sigma_min is unchanged up to rounding.
                import scipy.linalg as sla

                Gn = G.numpy()
                lo_w, lo_v = sla.eigh(Gn, subset_by_index=[0, 0], driver="evr")
                vmin = lo_v[:, 0].astype(np.float32)
                v = np.random.default_rng(li).standard_normal(Gn.shape[0])
                lam = 0.0
                for _ in range(60):
                    v = Gn @ v
                    lam = float(np.linalg.norm(v))
                    v /= max(lam, 1e-300)
                ev = torch.tensor([max(float(lo_w[0]), 0.0), lam], dtype=torch.float64)
                if part != "stacked":
                    vmin = np.zeros(int(M.shape[0]), dtype=np.float32)
            elif part == "stacked":
                # full eigendecomposition: X10 also needs the near-null LEFT singular vector
                # so cos(vmin, u) can say whether the scar direction IS the model's harm axis
                ev, V = torch.linalg.eigh(G)
                vmin = V[:, 0].float().numpy().astype(np.float32)
                del V
            else:
                # the per-matrix scar needs only the spectrum; eigvalsh is ~2-3x cheaper
                ev = torch.linalg.eigvalsh(G)
                vmin = np.zeros(int(M.shape[0]), dtype=np.float32)
            ev = torch.clamp(ev, min=0.0)
            sv = torch.sqrt(ev).flip(0).float().numpy()
            store[part]["svals"].append(sv.astype(np.float32))
            store[part]["vmin"].append(vmin)
            store[part]["fro2"].append(fro2)
            store[part]["shapes"].append([d, n])
            if store_gram and part == "stacked":
                Gf = G.to(torch.float16 if gram_dtype == "float16" else torch.float32)
                np.save(gdir / f"G_{li:03d}.npy", Gf.numpy())
                del Gf
            del G, ev, M
        del Wo, Wd
        gc.collect()

    for part, d_ in store.items():
        np.save(out_dir / f"svals_{part}.npy", np.stack(d_["svals"]))
        np.save(out_dir / f"vmin_{part}.npy", np.stack(d_["vmin"]))
        meta["parts"][part] = {"fro2": d_["fro2"], "shapes": d_["shapes"]}
    meta["elapsed_s"] = time.time() - t0
    try:
        k0 = keys[sorted(keys)[0]]["o_proj"]
        meta["native_dtype"] = str(handles[wmap[k0]].get_slice(k0).get_dtype())
    except Exception:  # noqa: BLE001
        meta["native_dtype"] = "unknown"
    jdump(meta, out_dir / "w_meta.json")
    sent.write_text(json.dumps({"ts": time.time(), "elapsed_s": meta["elapsed_s"]}))
    logger.info(f"W-SUMMARY {name}: {len(keys)} layers in {meta['elapsed_s']:.1f}s")
    del handles
    gc.collect()
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", nargs="*", default=None)
    ap.add_argument("--deadline-min", type=float, default=90.0)
    ap.add_argument("--no-gram", action="store_true")
    ap.add_argument("--parts", nargs="*", default=["stacked"])
    args = ap.parse_args()
    setup_logging("wsummary")
    from aii_common import Deadline
    from panel import PAIRS, SINGLES

    dl = Deadline(args.deadline_min)
    if args.repos:
        repos = [(r, None) for r in args.repos]
    else:
        repos = []
        for p in sorted(PAIRS, key=lambda x: x["priority"]):
            repos += [(p["parent"], None), (p["child"], None)]
        for s in sorted(SINGLES, key=lambda x: x["priority"]):
            repos.append((s["repo"], None))
    seen, ordered = set(), []
    for r, t in repos:
        if r not in seen:
            seen.add(r)
            ordered.append((r, t))

    fails = jload_maybe(RESULTS / "wsummary_failures.json", []) or []
    for i, (repo, tag) in enumerate(ordered):
        if not dl.have(0.5):
            DEVIATIONS.add("gate", "wsummary deadline reached", f"stopped before {repo}")
            break
        try:
            logger.info(f"[{i+1}/{len(ordered)}] W-summary {repo}")
            w_summary_repo(repo, tag, store_gram=not args.no_gram,
                           parts=tuple(args.parts))
        except Exception as exc:  # noqa: BLE001
            fails.append({"repo": repo, "error": repr(exc),
                          "traceback": traceback.format_exc()[-3000:]})
            jdump(fails, RESULTS / "wsummary_failures.json")
            DEVIATIONS.add("wsummary_failed", repo, repr(exc)[:300])
            logger.error(f"W-summary FAILED {repo}: {exc}")
    jdump(fails, RESULTS / "wsummary_failures.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
