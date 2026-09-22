#!/usr/bin/env python3
"""S5: score ONE confirmation checkpoint with EXACTLY the screen's code (prereg amendment A5).

- Tier-A candidates: tierA.crossfit on the registered S32 folds (not a simplified proxy).
- Bars (BL1_easy, AMS_T1_sigma, N1, ...): bars.compute_bars on the SAME arrays, so every
  candidate-vs-bar margin is genuinely paired.
- Tier-B candidates: results/confirm/ckpt_<tag>.json written by `src/tierB.py --repo ...`
  (external-checkpoint mode, same registered battery as the screen).
- A1 (joint): the screen's FROZEN z-scoring + PC1 loading from screen_table.json.
Refuses to run unless results/survivor.sha256 exists and matches survivor.json (INV-2).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import canonical_json, sha256_text  # noqa: E402

RES = WS / "results"
TIER_A_KEYS = ("G1", "G2", "G3", "G4", "G4_ratio", "A1_slope", "A3", "A3_sd", "W7c", "W7c_tok1", "plain_DiM")


def assert_frozen(results_dir: Path = RES) -> None:
    j, s = results_dir / "survivor.json", results_dir / "survivor.sha256"
    if not (j.exists() and s.exists()):
        raise SystemExit("S5 scoring refused: results/survivor.sha256 does not exist")
    if sha256_text(canonical_json(json.loads(j.read_text()))) != s.read_text().strip():
        raise SystemExit("S5 scoring refused: survivor.json does not match survivor.sha256")


def score(tag: str, arr_dir: Path | None, results_dir: Path = RES) -> dict[str, Any]:
    assert_frozen(results_dir)
    import bars  # noqa: PLC0415
    import tierA  # noqa: PLC0415
    # post-freeze: the sibling substrate's arrays may now be read (outcome files still are not)
    tierA.FORBIDDEN = tuple(x for x in tierA.FORBIDDEN if x not in ("gen_art_experiment_2", "panel_manifest"))
    prereg = tierA.load_prereg()
    stim = tierA.Stim(prereg)
    own = results_dir / f"confirm_harvest/{tag}"
    if (own / "A_prompt.npy").exists():
        # prefer OUR OWN 27-file harvest: same render as the Tier-B battery, and it carries
        # gamma / A_c11 / A_ams (so AMS sigma, A1_slope and BL1_truelogit are computable)
        arr_dir, src_used = own, "own_harvest"
    else:
        src_used = "substrate_arrays" if arr_dir else "none"
    out: dict[str, Any] = {"tag": tag, "dir": str(arr_dir) if arr_dir else None, "arrays_source": src_used,
                           "values": {}, "notes": {}, "censored": {}, "bars": {}}
    if arr_dir is not None and Path(arr_dir).is_dir():
        try:
            ck = tierA.Ckpt(tag, Path(arr_dir))
            if ck.n_rows != len(stim.rows):
                raise ValueError(f"A_prompt rows {ck.n_rows} != stimuli rows {len(stim.rows)}")
            U = tierA.g4_basis(ck)
            reg = tierA.crossfit(ck, stim.registered(), stim, U)["registered"]
            for k in TIER_A_KEYS:
                out["values"][k] = reg.get(k)
            out["censored"] = {"G2": bool(reg.get("G2_censored")), "A3": bool(reg.get("A3_censored"))}
            out["bstar_read"] = None
        except (FileNotFoundError, ValueError, KeyError) as exc:
            out["notes"]["tierA"] = f"FAILED: {exc!r}"[:400]
        try:
            import bars_partial  # noqa: PLC0415
            out["bars"] = bars_partial.compute_bars_tolerant(Path(arr_dir), tag)
        except Exception as exc:  # noqa: BLE001 - a bar failure is reported, never fatal
            out["bars"] = {"error": repr(exc)[:400]}
    else:
        out["notes"]["tierA"] = "NO_ARRAYS"
    cb = results_dir / "confirm" / f"ckpt_{tag}.json"
    if cb.exists():
        r = json.loads(cb.read_text())
        if r.get("status") == "OK":
            for k, v in (r.get("registered") or {}).items():
                out["values"][k] = v
            out["censored"].update({k: bool(v) for k, v in (r.get("censored") or {}).items() if isinstance(v, bool)})
            out["tierB_bars"] = r.get("bars")
        else:
            out["notes"]["tierB"] = f"status={r.get('status')}"
    else:
        out["notes"]["tierB"] = "NOT_RUN (no results/confirm/ckpt_<tag>.json)"
    st = json.loads((results_dir / "screen_table.json").read_text())
    lo = st.get("a1_joint_loading") or {}
    pr, sl = out["values"].get("A1_prior"), out["values"].get("A1_slope")
    if lo.get("loading_A1_prior") is not None and pr is not None and sl is not None:
        pz = (pr - lo["prior_mean"]) / (lo.get("prior_sd") or 1.0)
        sz = (sl - lo["slope_mean"]) / (lo.get("slope_sd") or 1.0)
        out["values"]["A1"] = float(lo["loading_A1_prior"] * pz + lo["loading_A1_slope"] * sz)
    elif str(lo.get("mode", "")).startswith("A1_slope_fallback") and sl is not None:
        out["values"]["A1"] = sl
        out["notes"]["A1"] = "A1_slope fallback (screen loading mode)"
    if out["values"].get("W7") is None and out["values"].get("W7c") is not None:
        out["values"]["W7"] = out["values"]["W7c"]
        out["notes"]["W7"] = "W7_is_W7c (same per-row rule as the screen)"
    b = out.get("bars") or {}
    out["BL1_easy"] = b.get("BL1_easy")
    out["AMS_T1"] = b.get("AMS_T1_sigma")
    return out


if __name__ == "__main__":
    print(json.dumps(score(sys.argv[1], Path(sys.argv[2]) if len(sys.argv) > 2 else None), indent=1, default=str)[:4000])
