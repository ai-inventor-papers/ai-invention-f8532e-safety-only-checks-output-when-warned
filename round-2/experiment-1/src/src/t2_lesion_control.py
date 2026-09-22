"""T2/T3 -- GROUND-TRUTH POSITIVE AND NEGATIVE CONTROL FOR X2 AND X10.

Before trusting X2 and X10 on real community edits, apply a KNOWN rank-one
orthogonalisation to a clean model at a known direction u0 and a known alpha, and check:

  (i)   X2(u0) collapses to ~0 on the edited layers -- the ALGEBRAIC IDENTITY. This is a
        sanity check, NOT a result, and the X2_parent row is labelled as such everywhere.
  (ii)  X10's scar fires at EXACTLY the edited layers and nowhere else.
  (iii) cos(vmin, u0) ~ 1 at the edited layers: the near-null direction IS the deleted one.
  (iv)  ALPHA SWEEP -> the DETECTION FLOOR, the smallest alpha at which X10 still fires.
        That number is what you quote when a community edit is missed.

T3 NEGATIVE CONTROL: the same statistic on the UNEDITED model and on a RANDOM-INIT model.
If X10 fires on an unedited model its baseline is miscalibrated and every E1 pass it earns
is spurious.

The edit is exactly the operator iteration-1 Lane B's `engine.Lesion` applies, in its
weight-space form:  W <- W - alpha * u (u^T W)  on o_proj and down_proj of every layer,
which is the standard community abliteration recipe.
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import RESULTS, jdump, setup_logging  # noqa: E402
from loguru import logger  # noqa: E402
import numerics as nm  # noqa: E402
from wsummary import _find_keys, get, open_repo  # noqa: E402


def spectrum_of(M, u0: np.ndarray | None):
    """(sigma_min, sigma_1, fro2, cos(vmin,u0)) for a [d, n] matrix, via the Gram."""
    import torch

    G = (M @ M.T).double()
    fro2 = float(torch.diagonal(G).sum().item())
    ev, V = torch.linalg.eigh(G)
    ev = torch.clamp(ev, min=0.0)
    vmin = V[:, 0].float().numpy()
    s_min = float(np.sqrt(max(float(ev[0].item()), 0.0)))
    s_1 = float(np.sqrt(max(float(ev[-1].item()), 0.0)))
    cos = float(abs(vmin @ u0)) if u0 is not None else None
    del G, ev, V
    return s_min, s_1, fro2, cos, vmin


def run(repo: str, alphas: list[float], edited_layers: list[int] | None,
        seed: int = 0, max_layers: int = 0) -> dict:
    import torch

    handles, wmap, _ = open_repo(repo)
    keys = _find_keys(wmap)
    layers = sorted(keys)
    if max_layers:
        layers = layers[:max_layers]
    d = int(get(handles, wmap, keys[layers[0]]["o_proj"]).shape[0])
    rng = np.random.default_rng(seed)
    u0 = nm.unit(rng.standard_normal(d)).astype(np.float32)
    u0_t = torch.from_numpy(u0)
    edited = set(edited_layers if edited_layers is not None else layers)

    out: dict = {"repo": repo, "hidden_size": d, "n_layers": len(layers),
                 "edited_layers": sorted(edited), "alphas": alphas, "per_alpha": {}}

    Ms: dict[int, "torch.Tensor"] = {}
    for li in layers:
        Wo = get(handles, wmap, keys[li]["o_proj"])
        Wd = get(handles, wmap, keys[li]["down_proj"])
        Ms[li] = torch.cat([Wo, Wd], dim=1)
        del Wo, Wd

    for a in alphas:
        t0 = time.time()
        scar, wm, cosv, smin, smp = [], [], [], [], []
        for li in layers:
            M = Ms[li]
            if a > 0 and li in edited:
                M = M - a * torch.outer(u0_t, u0_t @ M)
            s_min, s_1, fro2, cos, _ = spectrum_of(M, u0)
            n = int(M.shape[1])
            mp = nm.sigma_mp_analytic(fro2, d, n)
            scar.append(float(np.log10(max(mp, 1e-12) / max(s_min, 1e-12))))
            smin.append(s_min)
            smp.append(mp)
            cosv.append(cos)
            G = (M @ M.T).double().numpy()
            wm.append(nm.write_mass(G, fro2, u0, d))
            del G
            if a > 0 and li in edited:
                del M
        scar_a = np.array(scar)
        med = float(np.median(scar_a))
        mad = float(np.median(np.abs(scar_a - med)))
        z = (scar_a - med) / (1.4826 * mad) if mad > 1e-12 else np.zeros_like(scar_a)
        ed = np.array([li in edited for li in layers])
        out["per_alpha"][str(a)] = {
            "X10_max_z": float(np.max(z)),
            "X10_argmax_layer": int(layers[int(np.argmax(z))]),
            "X10_argmax_is_edited_layer": bool(ed[int(np.argmax(z))]),
            "X10_abs_max_scar": float(np.max(scar_a)),
            "mean_scar_edited": float(scar_a[ed].mean()) if ed.any() else None,
            "mean_scar_unedited": float(scar_a[~ed].mean()) if (~ed).any() else None,
            "X2_write_mass_u0_mean": float(np.mean(wm)),
            "X2_write_mass_u0_edited_mean": float(np.mean(np.array(wm)[ed])) if ed.any() else None,
            "X2_log10_write_mass_edited": float(np.mean(np.log10(
                np.maximum(np.array(wm)[ed], 1e-30)))) if ed.any() else None,
            "cos_vmin_u0_mean_edited": float(np.mean(np.array(cosv)[ed])) if ed.any() else None,
            "cos_vmin_u0_mean_unedited": float(np.mean(np.array(cosv)[~ed])) if (~ed).any() else None,
            "sigma_min_mean": float(np.mean(smin)), "sigma_mp_mean": float(np.mean(smp)),
            "elapsed_s": time.time() - t0,
        }
        logger.info(f"alpha={a}: X10_max_z={out['per_alpha'][str(a)]['X10_max_z']:.2f} "
                    f"write_mass(u0)={out['per_alpha'][str(a)]['X2_write_mass_u0_mean']:.3e} "
                    f"cos(vmin,u0)={out['per_alpha'][str(a)]['cos_vmin_u0_mean_edited']} "
                    f"({time.time()-t0:.0f}s)")
        gc.collect()

    base = out["per_alpha"][str(alphas[0])] if alphas and alphas[0] == 0.0 else None
    floor = None
    for a in alphas:
        if a <= 0:
            continue
        r = out["per_alpha"][str(a)]
        if r["cos_vmin_u0_mean_edited"] is not None and r["cos_vmin_u0_mean_edited"] > 0.9:
            floor = a
            break
    out["detection_floor_alpha"] = floor
    out["detection_floor_note"] = (
        f"the smallest swept alpha at which the near-null direction of the edited matrices is "
        f"the deleted direction (cos > 0.9) is {floor}. Below it, a community edit of that "
        "strength would be MISSED by a weights-only scar, and that is the number to quote when "
        "one is.")
    out["T3_negative_control"] = {
        "unedited_X10_max_z": base["X10_max_z"] if base else None,
        "unedited_cos_vmin_u0": base["cos_vmin_u0_mean_edited"] if base else None,
        "rule": ("X10 must NOT fire on an unedited model. If it does, its baseline is "
                 "miscalibrated and every E1 pass it earns is spurious."),
    }
    del Ms, handles
    gc.collect()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--alphas", nargs="*", type=float,
                    default=[0.0, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0])
    ap.add_argument("--max-layers", type=int, default=0)
    ap.add_argument("--edited", nargs="*", type=int, default=None)
    args = ap.parse_args()
    setup_logging("t2_lesion")
    res = {"positive_control": run(args.repo, args.alphas, args.edited,
                                   max_layers=args.max_layers)}
    # T2(ii): a HALF-EDITED model -- the scar must localise to the edited half only
    n = res["positive_control"]["n_layers"]
    half = list(range(n // 2))
    res["localisation_control"] = run(args.repo, [0.0, 1.0], half, max_layers=args.max_layers)
    res["localisation_verdict"] = _loc(res["localisation_control"])
    jdump(res, RESULTS / "t2_lesion_control.json")
    logger.info(f"T2/T3 written -> {RESULTS / 't2_lesion_control.json'}")
    logger.info(f"detection floor alpha = {res['positive_control']['detection_floor_alpha']}")
    return 0


def _loc(r: dict) -> dict:
    a1 = r["per_alpha"].get("1.0", {})
    return {
        "scar_fires_on_edited_layers_only": bool(
            a1.get("X10_argmax_is_edited_layer") and
            (a1.get("mean_scar_edited") or 0) > (a1.get("mean_scar_unedited") or 0)),
        "mean_scar_edited": a1.get("mean_scar_edited"),
        "mean_scar_unedited": a1.get("mean_scar_unedited"),
        "cos_vmin_u0_edited": a1.get("cos_vmin_u0_mean_edited"),
        "cos_vmin_u0_unedited": a1.get("cos_vmin_u0_mean_unedited"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
