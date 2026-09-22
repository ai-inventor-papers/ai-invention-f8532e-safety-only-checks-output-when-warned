"""EDIT-RECIPE FINGERPRINT -- stratification diagnostic ONLY, never enters any metric.

This is the ONE place (with the X2_parent identity row) where parent weights are read.
It exists to assign each pair to a STRATUM, because pooling a global-rank-one edit with a
per-layer-rotating one would average two different operators.

Parameterised from iteration-1 Lane B's `src/weightcheck.py`, whose CHILD/PARENT were
module-level constants hardcoded to one pair.  The quantities and key names are kept
identical so the two runs' tables line up:
    fro2_delta, rank1_share = sigma1^2/||D||_F^2, fro_delta, fro_parent,
    implied_alpha = ||D||_F / ||u1^T W_parent||, and the pooled global row.

One change of substance: the top eigenpair is found by POWER ITERATION ON D directly
(u <- D (D^T u)) instead of forming the [d,d] Gram and calling eigh.  That is
mathematically the same top singular pair at a tiny fraction of the cost, which is what
makes the fingerprint affordable for nine pairs on a CPU-only box instead of one pair on
a GPU.  The equivalence is asserted against a full eigh on the first matrix of each pair.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import traceback
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import (  # noqa: E402
    DEVIATIONS, RESULTS, cgroup_mem_limit_bytes, cgroup_mem_used_bytes, human_bytes,
    jdump, jload_maybe, setup_logging, wait_for_memory,
)
from loguru import logger  # noqa: E402
from wsummary import _find_keys, get, open_repo  # noqa: E402


def top_singular_pair(D, n_iter: int = 60, tol: float = 1e-9, seed: int = 0):
    """Top (sigma1, u1) of D [d, n] by power iteration on D D^T, without forming it."""
    import torch

    g = torch.Generator().manual_seed(seed)
    u = torch.randn(D.shape[0], generator=g, dtype=D.dtype)
    u /= u.norm()
    s_prev = 0.0
    for _ in range(n_iter):
        v = D.T @ u
        u_new = D @ v
        s = u_new.norm()
        if s <= 0:
            return 0.0, u.numpy()
        u_new /= s
        if abs(float(s) - s_prev) <= tol * max(float(s), 1e-12):
            u = u_new
            s_prev = float(s)
            break
        u, s_prev = u_new, float(s)
    return float(np.sqrt(max(s_prev, 0.0))), u.numpy()


def fingerprint_pair(parent: str, child: str, u_ours: np.ndarray | None = None,
                     verify_first: bool = True) -> dict:
    import torch

    t0 = time.time()
    ph, pw, _ = open_repo(parent)
    ch, cw, _ = open_repo(child)
    pk, ck = _find_keys(pw), _find_keys(cw)
    layers = sorted(set(pk) & set(ck))
    res: dict = {"parent": parent, "child": child, "per_matrix": [], "notes": [],
                 "n_layers": len(layers)}
    if not layers:
        res["error"] = "no shared o_proj/down_proj layers"
        return res

    u1_by_layer: dict[int, np.ndarray] = {}
    fro2_total = 0.0
    verified = None
    for li in layers:
        for mat in ("o_proj", "down_proj"):
            kc, kp = ck[li][mat], pk[li][mat]
            Wc, Wp = get(ch, cw, kc), get(ph, pw, kp)
            if tuple(Wc.shape) != tuple(Wp.shape):
                res["notes"].append(f"layer {li} {mat}: shape mismatch "
                                    f"{tuple(Wc.shape)} vs {tuple(Wp.shape)}")
                del Wc, Wp
                continue
            D = (Wc - Wp).double()
            fro2 = float((D * D).sum().item())
            row = {"layer": li, "matrix": mat, "shape": list(Wp.shape),
                   "fro2_delta": fro2, "fro_delta": float(np.sqrt(fro2)),
                   "fro_parent": float(Wp.double().norm().item())}
            if fro2 > 0:
                s1, u1 = top_singular_pair(D, seed=li)
                row["rank1_share"] = float(s1**2 / fro2)
                v = torch.from_numpy(u1).double() @ Wp.double()
                row["implied_alpha"] = float(np.sqrt(fro2) / (float(v.norm().item()) + 1e-12))
                if u_ours is not None and u1.shape[0] == u_ours.shape[0]:
                    row["cos_u1_vs_our_rablit"] = float(abs(u1 @ u_ours))
                if mat == "o_proj":
                    u1_by_layer[li] = u1
                if verify_first and verified is None and D.shape[0] <= 4096:
                    ev = torch.linalg.eigvalsh(D @ D.T)
                    verified = {"layer": li, "matrix": mat,
                                "sigma1_power": s1,
                                "sigma1_eigh": float(np.sqrt(max(float(ev[-1].item()), 0.0))),
                                }
                    verified["rel_err"] = abs(verified["sigma1_power"]
                                              - verified["sigma1_eigh"]) / max(
                        verified["sigma1_eigh"], 1e-12)
                    del ev
            fro2_total += fro2
            res["per_matrix"].append(row)
            del D, Wc, Wp
        gc.collect()

    res["power_iteration_verification"] = verified
    # cos between u1 at the shallowest and deepest edited layer -- what separates A from B
    edited = sorted(u1_by_layer)
    if len(edited) >= 2:
        res["cos_shallow_deep"] = float(abs(u1_by_layer[edited[0]] @ u1_by_layer[edited[-1]]))
        pair_cos = []
        for i in range(len(edited)):
            for j in range(i + 1, len(edited)):
                pair_cos.append(abs(float(u1_by_layer[edited[i]] @ u1_by_layer[edited[j]])))
        res["median_pairwise_abs_cos_u1"] = float(np.median(pair_cos)) if pair_cos else None
    else:
        res["cos_shallow_deep"] = None
        res["median_pairwise_abs_cos_u1"] = None

    # embed_tokens: did the edit touch the (possibly tied) unembed?
    try:
        ek = next((k for k in pw if k.endswith("embed_tokens.weight")), None)
        if ek and ek in cw:
            # ROW-CHUNKED: a 200k-vocab embedding (Phi-4-mini) is ~2.5 GB in float32, and the
            # un-chunked parent+child+float64-difference (~10 GB) is what OOM-killed this
            # stage inside the 16 GB cgroup. Streaming 8192-row slices holds the peak at
            # ~0.4 GB and is exact up to summation order (float64 accumulators).
            import torch
            slc, slp = ch[cw[ek]].get_slice(ek), ph[pw[ek]].get_slice(ek)
            shc, shp = tuple(slc.get_shape()), tuple(slp.get_shape())
            if shc == shp:
                f2 = fp2 = 0.0
                for i0 in range(0, shc[0], 8192):
                    a = slc[i0:i0 + 8192].to(torch.float64)
                    b = slp[i0:i0 + 8192].to(torch.float64)
                    f2 += float(((a - b) ** 2).sum().item())
                    fp2 += float((b * b).sum().item())
                    del a, b
                res["embed_tokens"] = {"fro_delta": float(np.sqrt(f2)),
                                       "fro_parent": float(np.sqrt(fp2)),
                                       "edited": bool(f2 > 0), "computed": "row-chunked"}
            else:
                res["embed_tokens"] = {"shape_mismatch": [list(shc), list(shp)]}
    except Exception as exc:  # noqa: BLE001
        res["embed_tokens"] = {"error": str(exc)}

    rs = [r["rank1_share"] for r in res["per_matrix"] if "rank1_share" in r]
    ia = [r["implied_alpha"] for r in res["per_matrix"] if "implied_alpha" in r]
    res["global"] = {"fro2_total": fro2_total,
                     "n_matrices_edited": int(sum(1 for r in res["per_matrix"]
                                                  if r["fro2_delta"] > 0))}
    res["summary"] = {
        "n_matrices": len(res["per_matrix"]),
        "rank1_share_median": float(np.median(rs)) if rs else None,
        "rank1_share_min": float(np.min(rs)) if rs else None,
        "implied_alpha_median": float(np.median(ia)) if ia else None,
        "implied_alpha_iqr": [float(np.percentile(ia, 25)), float(np.percentile(ia, 75))]
        if ia else None,
        "cos_shallow_deep": res["cos_shallow_deep"],
        "median_pairwise_abs_cos_u1": res["median_pairwise_abs_cos_u1"],
    }
    res["stratum"] = assign_stratum(res)
    res["elapsed_s"] = time.time() - t0
    del ph, ch
    gc.collect()
    return res


def assign_stratum(res: dict) -> str:
    """REGISTERED stratum rule (2.6).  NEVER pool across strata for E1(a)."""
    s = res.get("summary") or {}
    med_cos = s.get("median_pairwise_abs_cos_u1")
    alpha = s.get("implied_alpha_median")
    r1 = s.get("rank1_share_median")
    emb = (res.get("embed_tokens") or {}).get("edited")
    if r1 is None or alpha is None:
        return "UNKNOWN"
    if alpha > 1.05 or r1 < 0.5 or emb:
        return "C_OTHER_OPERATOR"
    if med_cos is not None and med_cos >= 0.80 and alpha <= 1.05:
        return "A_GLOBAL_RANK1"
    return "B_PER_LAYER_RANK1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--deadline-min", type=float, default=45.0)
    ap.add_argument("--pairs", nargs="*", default=None)
    ap.add_argument("--need-gb", type=float, default=2.5,
                    help="cgroup headroom required before starting a pair")
    ap.add_argument("--wait-s", type=float, default=2400.0)
    args = ap.parse_args()
    setup_logging("weightfp")
    from aii_common import Deadline
    from panel import PAIRS

    dl = Deadline(args.deadline_min)
    lim, used = cgroup_mem_limit_bytes(), cgroup_mem_used_bytes()
    if lim:
        logger.info(f"cgroup memory: {human_bytes(used or 0)} used of {human_bytes(lim)}")
    out = jload_maybe(RESULTS / "weight_fingerprints.json", {}) or {}
    todo = [p for p in sorted(PAIRS, key=lambda x: x["priority"])
            if (args.pairs is None or p["pair"] in set(args.pairs))]
    for p in todo:
        if p["pair"] in out:
            continue
        if not dl.have(1.0):
            DEVIATIONS.add("gate", "weightfp deadline reached", f"stopped before {p['pair']}")
            break
        # An earlier run of this stage was OOM-KILLED reading the Phi pair while the harvest
        # sweep held a 4B model. SIGKILL cannot be caught, so the only defence is not to
        # start until there is headroom inside the ~15 GB cgroup.
        if not wait_for_memory(args.need_gb * (1 << 30), timeout_s=args.wait_s):
            DEVIATIONS.add("memory_gate", f"weightfp skipped {p['pair']}",
                           f"never saw {args.need_gb} GB of cgroup headroom within "
                           f"{args.wait_s}s")
            continue
        try:
            logger.info(f"fingerprint {p['pair']}: {p['parent']} -> {p['child']}")
            r = fingerprint_pair(p["parent"], p["child"])
            r["pair"] = p["pair"]
            out[p["pair"]] = r
            logger.info(f"  stratum={r.get('stratum')} alpha_med="
                        f"{(r.get('summary') or {}).get('implied_alpha_median')} "
                        f"rank1_med={(r.get('summary') or {}).get('rank1_share_median')} "
                        f"cos_sd={(r.get('summary') or {}).get('cos_shallow_deep')}")
        except Exception as exc:  # noqa: BLE001
            out[p["pair"]] = {"pair": p["pair"], "error": repr(exc),
                              "traceback": traceback.format_exc()[-2500:]}
            DEVIATIONS.add("weightfp_failed", p["pair"], repr(exc)[:300])
            logger.error(f"fingerprint FAILED {p['pair']}: {exc}")
        jdump(out, RESULTS / "weight_fingerprints.json")
    jdump(out, RESULTS / "weight_fingerprints.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
