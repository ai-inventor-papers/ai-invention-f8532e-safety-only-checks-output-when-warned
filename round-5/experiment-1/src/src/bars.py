#!/usr/bin/env python3
"""BASELINE-BAR computation (TIER A bars, plan S2.3). Tier-A bars are printed beside every
screen row and are NEVER eligible to win (INV-1: only activation/weight candidates can win).

compute_bars(tag_dir) loads one checkpoint's harvested arrays via reuse.ncands.Ckpt.load and
calls ONLY the reused math (reuse.ncands.*, reuse.ams_reimpl.* via reuse.ncands's lazy import) --
no candidate math is reimplemented here, only call sites are adapted (module-relative asset
paths, per-bar metadata, NaN-safe fallbacks for H2-schema dirs that lack some arrays).

Bars returned (each with a "<bar>_meta" sibling: array + layer + prompt set):
  BL1_easy, BL1_hard          reuse.ncands.bl1_easy_hard()   -- r_refusal-r_control @ final layer L
  BL1_truelogit(_hard)        reuse.ncands.bl1_truelogit()   -- LSE(H_L@WU_ref)-LSE(H_L@WU_ctl) @ L
                               NOTE: the iteration-2 "double final RMSNorm" LENS convention
                               (4.99/3.07 on HARD) is WITHDRAWN and is NEVER computed here.
  AMS_T1_sigma                reuse.ncands.ams_t1_values()   -- needs A_ams.npy (I4-schema tags only)
  AMS_T2_drift / _mean_direction_similarity / _verified
                               reuse.ncands.ams_t2_values()  -- PAIR-LEVEL (child vs its parent);
                               only computed when --parent-dir / parent_dir= is supplied.
  N1, N6, C7, C13_peak_d, N11 reuse.ncands.values()
  B7_nullproj                 reuse.ncands.b7_values()       -- vmin_onesproj variant ONLY (registered)
  plain_diffmeans              own-EASY-axis Cohen's d at the FIXED final layer L, NO cross-fit
                               l_star search -- the field-norm-D "plain difference-in-means" floor.

Works on both I4-schema artifact dirs (vmin_onesproj.npy, A_ams.npy, A_c11.npy, A_dec.npy present)
and H2-schema on-disk dirs (gram/G_*.npy present, no vmin_onesproj/A_ams/A_c11/A_dec): every bar
that needs a missing array returns NaN with a "reason" in its _meta dict instead of raising.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Optional

import numpy as np

SRC = Path(__file__).resolve().parent
REUSE = SRC / "reuse"
if str(REUSE) not in sys.path:
    sys.path.insert(0, str(REUSE))
import ncands  # noqa: E402  (reused module, copied verbatim from I4/src/ncands.py)

WS = SRC.parent
NAN = float("nan")


def _meta(array: str, layer: str, prompt_set: str) -> dict:
    return {"array": array, "layer": layer, "prompt_set": prompt_set}


def _is_na(x: Any) -> bool:
    return isinstance(x, str) and x == ncands.NOT_AVAILABLE


def compute_bars(tag_dir: Path, parent_dir: Optional[Path] = None) -> dict[str, Any]:
    """Compute every Tier-A bar for one checkpoint directory. Never raises: any failure is
    recorded as NaN + a reason string next to the affected bar(s)."""
    tag_dir = Path(tag_dir)
    tag = tag_dir.name
    out: dict[str, Any] = {"tag": tag, "dir": str(tag_dir)}
    try:
        ckpt = ncands.Ckpt.load(tag, tag_dir)
    except Exception as e:  # noqa: BLE001
        out["ERROR"] = f"Ckpt.load failed: {type(e).__name__}: {e}"
        return out

    out["provenance"] = ckpt.provenance
    out["L"] = ckpt.L
    out["availability"] = ckpt.availability
    L = ckpt.L
    ncands.precompute(ckpt)

    # ---- BL1 family (logit-gap bars; final layer; NOT the withdrawn double-RMSNorm lens) ----
    try:
        bl1 = ncands.bl1_easy_hard(ckpt)
        out["BL1_easy"] = bl1["BL1_easy"]
        out["BL1_easy_meta"] = _meta(
            "r_refusal - r_control @ hidden-state index L (final layer)", f"L={L}",
            "EASY n=96 (48 advbench-harmful vs 48 dolly-benign)")
        out["BL1_hard"] = bl1["BL1_hard"]
        out["BL1_hard_meta"] = _meta(
            "r_refusal - r_control @ hidden-state index L (final layer)", f"L={L}",
            "HARD n=160 (40 xstest-harmful-twin+40 or_bench_toxic vs 40 xstest-benign-twin+40 or_bench_hard_1k)")
    except Exception as e:  # noqa: BLE001
        out["BL1_easy"] = out["BL1_hard"] = NAN
        out["BL1_easy_meta"] = out["BL1_hard_meta"] = {"reason": f"{type(e).__name__}: {e}"}

    try:
        bl1t = ncands.bl1_truelogit(ckpt)
        out["BL1_truelogit"] = bl1t["BL1_truelogit"]
        out["BL1_truelogit_meta"] = _meta(
            "LSE(H_L @ WU_ref^T) - LSE(H_L @ WU_ctl^T) @ hidden-state index L (final layer)",
            f"L={L}", "EASY n=96 -- WITHDRAWN convention (double final RMSNorm lens) NOT used")
        out["BL1_truelogit_hard"] = bl1t["BL1_truelogit_hard"]
        out["BL1_truelogit_hard_meta"] = _meta(
            "LSE(H_L @ WU_ref^T) - LSE(H_L @ WU_ctl^T) @ hidden-state index L (final layer)",
            f"L={L}", "HARD n=160 -- WITHDRAWN convention (double final RMSNorm lens) NOT used")
    except Exception as e:  # noqa: BLE001
        out["BL1_truelogit"] = out["BL1_truelogit_hard"] = NAN
        out["BL1_truelogit_meta"] = out["BL1_truelogit_hard_meta"] = {"reason": f"{type(e).__name__}: {e}"}

    # ---- N-candidate family (N1, N6, C7, C13_peak_d, N11) + plain diff-in-means floor ----
    try:
        v = ncands.values(ckpt)
        out["N1"] = v["N1"]
        out["N1_l_star"] = v["N1_l_star"]
        out["N1_meta"] = _meta(
            "own-EASY-axis Cohen's d at cross-fitted l_star (20 seeded 2-fold splits x 2 dirs, "
            "NO post-hoc argmax)", f"l_star={v['N1_l_star']}/{L}", "fit=EASY n=96, score=HARD n=160")

        out["N6"] = v["N6"]
        out["N6_meta"] = _meta(
            "own-EASY-axis Cohen's d at N1's l_star, restricted to the XSTest twin rows within HARD",
            f"l_star={v['N1_l_star']}/{L}",
            "XSTest harmful-twin n=40 vs XSTest benign-twin n=40 (subset of HARD n=160)")

        out["C7"] = v["C7"]
        out["C7_meta"] = _meta(
            "trapezoid(AUROC_l over f=l/L, l=0..L) -- own-EASY-axis AUROC curve, area under curve",
            "all layers l=0..L", "fit=EASY n=96, score=HARD n=160")

        out["C13_peak_d"] = v["C13_peak_d"]
        out["C13_peak_f"] = v["C13_peak_f"]
        peak_f = v.get("C13_peak_f", float("nan"))
        out["C13_peak_d_meta"] = _meta(
            "max over l=1..L of own-EASY-axis Cohen's d (post-hoc argmax over the whole curve, "
            "by construction/name -- distinct from N1's cross-fitted l_star)",
            (f"peak at f={peak_f:.4f}" if isinstance(peak_f, float) and math.isfinite(peak_f) else "n/a"),
            "fit=EASY n=96, score=HARD n=160")

        out["N11"] = v["N11"]
        lo11, hi11 = ncands.lay(0.4, L), ncands.lay(0.8, L)
        out["N11_meta"] = _meta(
            "mean Fisher ratio over l in [floor(0.4L), floor(0.8L)] of the own-EASY-axis curve",
            f"[{lo11},{hi11}] (of 0..{L})", "fit=EASY n=96, score=HARD n=160")

        d_l_curve = v.get("_d_l_curve")
        if d_l_curve is not None and np.isfinite(d_l_curve[L]):
            out["plain_diffmeans"] = float(d_l_curve[L])
            out["plain_diffmeans_meta"] = _meta(
                "own-EASY-axis Cohen's d at the FIXED final layer L -- NO cross-fit l_star search, "
                "NO post-hoc argmax (field-norm-D 'plain difference-in-means' baseline floor)",
                f"L={L} (fixed, not searched)", "fit=EASY n=96, score=HARD n=160")
        else:
            out["plain_diffmeans"] = NAN
            out["plain_diffmeans_meta"] = {"reason": "own-axis d curve unavailable/non-finite at final layer"}
    except Exception as e:  # noqa: BLE001
        for k in ("N1", "N6", "C7", "C13_peak_d", "N11", "plain_diffmeans"):
            out[k] = NAN
        out["N_family_ERROR"] = f"{type(e).__name__}: {e}"

    # ---- B7_nullproj (weights-only; vmin_onesproj variant ONLY -- the registered choice) ----
    try:
        b7 = ncands.b7_values(ckpt)
        raw = b7["B7_nullproj"]
        out["B7_nullproj"] = NAN if _is_na(raw) else raw
        out["B7_nullproj_meta"] = _meta(
            "top singular value / sqrt(L) of the unit-normalised, all-ones-null-projected least "
            "Gram-eigenvector stack (vmin_onesproj.npy) -- B7's OTHER variant (raw vmin_stacked / "
            "gram-derived, no ones-projection) is NEVER used here, per the registered choice",
            "all layers stacked", "N/A (weights only, no prompts)")
        if _is_na(raw):
            out["B7_nullproj_meta"]["reason"] = raw
    except Exception as e:  # noqa: BLE001
        out["B7_nullproj"] = NAN
        out["B7_nullproj_meta"] = {"reason": f"{type(e).__name__}: {e}"}

    # ---- AMS Tier-1 sigma ("batch 1": one prompt at a time from the harvested A_ams array, no
    #      padding/batching hazard -- I4-schema tags with A_ams.npy only) ----
    if ckpt.A_ams is not None:
        try:
            t1 = ncands.ams_t1_values(ckpt)
            if _is_na(t1):
                out["AMS_T1_sigma"] = NAN
                out["AMS_T1_sigma_meta"] = {"reason": "ams_reimpl module import failed or A_ams unavailable"}
            else:
                out["AMS_T1_sigma"] = t1["AMS_T1_sigma"]
                out["AMS_T1_sigma_meta"] = _meta(
                    "reuse.ams_reimpl.ams_tier1: in-sample argmax sigma over layers "
                    "int(0.4L)..int(0.8L), last-position hidden state, RAW TEXT (no chat template), "
                    "1-D diff-of-means direction, pooled_std=sqrt((var_pos+var_neg)/2); mean over the "
                    "3 standard AMS concepts ('batch 1': no batching/padding -- reads pre-harvested rows)",
                    "argmax per concept over int(0.4L)..int(0.8L)",
                    "A_ams n=96: AMS package's own harmful_content x3-concept pos/neg prompt set")
        except Exception as e:  # noqa: BLE001
            out["AMS_T1_sigma"] = NAN
            out["AMS_T1_sigma_meta"] = {"reason": f"{type(e).__name__}: {e}"}
    else:
        out["AMS_T1_sigma"] = NAN
        out["AMS_T1_sigma_meta"] = {"reason": "A_ams.npy not present in this tag dir (H2-schema dirs lack it)"}

    # ---- AMS Tier-2: PAIR-LEVEL identity-verification drift/similarity, child vs ITS parent ----
    out["AMS_T2_meta"] = {
        "note": "AMS_T2 is a PAIR-LEVEL check (reuse.ncands.ams_t2_values(child_ckpt, parent_ckpt)), "
                "not a per-checkpoint scalar: it compares one child against its declared parent's "
                "baseline. Computed only when parent_dir is supplied.",
    }
    if parent_dir is not None:
        if ckpt.A_ams is None:
            out["AMS_T2_meta"]["reason"] = "child A_ams.npy missing"
        else:
            try:
                parent_dir = Path(parent_dir)
                parent_ckpt = ncands.Ckpt.load(parent_dir.name, parent_dir)
                out["AMS_T2_meta"]["parent_tag"] = parent_ckpt.tag
                if parent_ckpt.A_ams is None:
                    out["AMS_T2_meta"]["reason"] = "parent A_ams.npy missing"
                else:
                    t2 = ncands.ams_t2_values(ckpt, parent_ckpt)
                    if _is_na(t2):
                        out["AMS_T2_meta"]["reason"] = "ams_reimpl unavailable"
                    else:
                        out["AMS_T2_drift"] = t2["AMS_T2_drift"]
                        out["AMS_T2_mean_direction_similarity"] = t2["AMS_T2_mean_direction_similarity"]
                        out["AMS_T2_verified"] = t2["AMS_T2_verified"]
                        out["AMS_T2_meta"]["formula"] = (
                            "baseline optimal_layer per concept found from PARENT only; child scored at "
                            "that SAME layer (no re-search); direction_similarity=cos(child_dir,parent_dir); "
                            "separation_drift=|child_sigma-parent_sigma|/parent_sigma")
            except Exception as e:  # noqa: BLE001
                out["AMS_T2_meta"]["error"] = f"{type(e).__name__}: {e}"

    return out


# --------------------------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------------------------- #
I4_HARVEST_DEFAULT = Path(
    "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1/harvest"
)


def _i4_tag_dirs(i4_harvest: Path = I4_HARVEST_DEFAULT) -> list[Path]:
    return sorted(p for p in i4_harvest.iterdir() if p.is_dir() and (p / "meta.json").exists())


def main() -> None:
    ap = argparse.ArgumentParser(description="Compute Tier-A BASELINE-BAR values for one or more checkpoints.")
    ap.add_argument("--tags", nargs="*", default=None, help="explicit tag directories (absolute paths)")
    ap.add_argument("--all-h4", "--all-i4", dest="all_h4", action="store_true",
                     help="run on every one of the 51 I4/harvest tags")
    ap.add_argument("--i4-harvest", type=str, default=str(I4_HARVEST_DEFAULT))
    ap.add_argument("--out", type=str, required=True,
                     help="output path; for multiple tags, '<tag>' in the path is replaced per tag "
                          "(e.g. results/bars/<tag>.json); a bare directory writes one file per tag "
                          "named <tag>.json inside it")
    ap.add_argument("--parent-dir", type=str, default=None, help="parent tag dir, for AMS_T2 only")
    args = ap.parse_args()

    if args.all_h4:
        tag_dirs = _i4_tag_dirs(Path(args.i4_harvest))
    elif args.tags:
        tag_dirs = [Path(t) for t in args.tags]
    else:
        ap.error("pass --tags <dir...> or --all-h4")
        return

    out_arg = args.out
    multiple = len(tag_dirs) > 1
    for td in tag_dirs:
        bars = compute_bars(td, parent_dir=Path(args.parent_dir) if args.parent_dir else None)
        if "<tag>" in out_arg:
            out_path = Path(out_arg.replace("<tag>", td.name))
        elif multiple or out_arg.endswith("/"):
            out_path = Path(out_arg) / f"{td.name}.json"
        else:
            out_path = Path(out_arg)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(_sanitize(bars), f, indent=1)
        print(f"[bars] {td.name} -> {out_path}")


def _sanitize(o: Any) -> Any:
    """Recursively replace non-finite floats (NaN/inf) with None so the output is valid JSON."""
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _sanitize(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    if isinstance(o, np.generic):
        return _sanitize(o.item())
    return o


if __name__ == "__main__":
    main()
