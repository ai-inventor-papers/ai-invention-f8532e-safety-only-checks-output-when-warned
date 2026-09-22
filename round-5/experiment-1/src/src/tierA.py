#!/usr/bin/env python3
"""Tier A: array-only screen candidates, computed from activations ALREADY ON DISK.

Candidates (definitions frozen in results/prereg.json -> d_candidates):
    G1  harmful-vs-benign-twin angle            G2  three-cluster margin ratio
    G3  used-ness (signed write cosine)         G4  BL1-orthogonal Fisher separation
    A1_slope  evidence slope on the PKU ladder  A3  domain-profile dispersion
    W7c / W7c_tok1  decode-site readout (correlational half of W7)
    plain_DiM  the mandatory difference-in-means floor (a BAR, never a candidate)

Everything is cross-fitted: directions and the band b* are FIT on one fold and the
quantity is SCORED on the other, then the folds are swapped and averaged.

INV-2: refuses to run unless results/prereg.sha256 exists and matches prereg.json.
INV-3/INV-1: never opens an outcome file (graded truth, classification, aggregates,
or anything under a sibling iteration-5 workspace).

Usage:
    .venv_gpu/bin/python src/tierA.py --all            # panel + quartet + controls
    .venv_gpu/bin/python src/tierA.py --tags F1__ref   # selected tags
    .venv_gpu/bin/python src/tierA.py --pair-boot      # structural-pair prompt bootstrap
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import band_indices, canonical_json, cohens_d_pooled, sha256_text, unit, utc_now  # noqa: E402

RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
I4 = RUN / "iter_4/gen_art/gen_art_experiment_1"
H4 = I4 / "harvest"
H2 = RUN / "iter_2/gen_art/gen_art_experiment_1/harvest"
RES = WS / "results"
OUT = RES / "screen/tierA"
CACHE = WS / "cache/bandmeans"

N_BANDS = 6
N_PERM = 50
PAIR_BOOT_B = 200
FORBIDDEN = ("graded_truth", "classification", "aggregates", "gen_art_experiment_2", "panel_manifest",
             "judge", "heldout", "sealed", "assets/pairs.json", "harvested_truth", "behaviour_items")

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
(WS / "logs").mkdir(exist_ok=True)
logger.add(WS / "logs/tierA.log", rotation="30 MB", level="DEBUG")


# --------------------------------------------------------------------------- #
# prereg (INV-2)                                                               #
# --------------------------------------------------------------------------- #


def load_prereg() -> dict:
    p, s = RES / "prereg.json", RES / "prereg.sha256"
    if not (p.exists() and s.exists()):
        raise SystemExit("INV-2: results/prereg.sha256 does not exist - no candidate may be computed")
    text = p.read_text()
    digest = sha256_text(canonical_json(json.loads(text)))
    if digest != s.read_text().strip():
        raise SystemExit("INV-2: prereg.json does not match prereg.sha256")
    return json.loads(text)


def guard_path(path: Path) -> Path:
    sp = str(path)
    for bad in FORBIDDEN:
        if bad in sp:
            raise PermissionError(f"Tier A must never open outcome/sibling files: {sp}")
    return path


# --------------------------------------------------------------------------- #
# stimuli bookkeeping                                                          #
# --------------------------------------------------------------------------- #


class Stim:
    """Row bookkeeping for the frozen 256-row stimulus file and its side sets."""

    def __init__(self, prereg: dict) -> None:
        items = prereg["c_fold_rule_and_prompts"]
        self.items = items
        self.salt = "iter5_screen_v1"
        rows = json.loads(guard_path(I4 / "assets/stimuli.json").read_text())["rows"]
        self.rows = rows
        self.row_of = {r["stim_id"]: i for i, r in enumerate(rows)}
        self.src = np.array([r["source"] for r in rows])
        self.hard_rows = [i for i, r in enumerate(rows) if int(r["set_id"]) == 1]
        self.dec_index = {row: j for j, row in enumerate(self.hard_rows)}   # A_dec row j <-> stimuli row
        pairs = json.loads(guard_path(RES / "items/twin_pairs.json").read_text())
        self.pairs = {p["pair_id"]: (self.row_of[p["harm_stim_id"]], self.row_of[p["benign_stim_id"]]) for p in pairs}
        self.pair_ids_all = [p["pair_id"] for p in pairs]
        self.dolly_rows = [i for i, r in enumerate(rows) if r["source"] == "databricks_dolly_15k"]
        dom = json.loads(guard_path(RES / "items/hard_domains.json").read_text())
        self.domain = dom.get("stim_id_to_domain", dom)
        self.hard_harm = [i for i in self.hard_rows if rows[i]["source"] in ("xstest_v2_harmful_twin", "or_bench_toxic")]
        self.hard_benign = [i for i in self.hard_rows if rows[i]["source"] in ("xstest_v2_benign_twin", "or_bench_hard_1k")]
        c11 = json.loads(guard_path(I4 / "assets/c11_items.json").read_text())["items"]
        self.c11_sev = np.array([float(c["severity"]) for c in c11])
        self.c11_ids = [str(c["c11_id"]) for c in c11]

    # fold sets ------------------------------------------------------------------
    def fold_sets(self, sel: dict, folds: dict) -> dict:
        """Return {'A': {'H':[rows],'Bn':[rows],'P':[rows]}, 'B': {...}}."""
        out = {}
        for f in ("A", "B"):
            H = [self.pairs[pid][0] for pid in folds[f]["pair_ids"]]
            Bn = [self.pairs[pid][1] for pid in folds[f]["pair_ids"]]
            P = [self.row_of[s] for s in folds[f]["P_stims"]]
            out[f] = {"H": H, "Bn": Bn, "P": P}
        return out

    def registered(self) -> dict:
        return self.fold_sets(self.items["S32_registered"], self.items["folds"]["0"])

    def draw(self, prompt_draw: int, fold_seed: int) -> dict:
        if prompt_draw == 0:
            return self.fold_sets(self.items["S32_registered"], self.items["folds"][str(fold_seed)])
        return self.fold_sets(self.items["S32_draws"][str(prompt_draw)],
                              self.items["folds_draws"][str(prompt_draw)][str(fold_seed)])

    def pool(self) -> dict:
        h = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
        po = sorted(self.pair_ids_all, key=lambda p: h(f"{self.salt}|pool|fold|pair|{p}"))
        qo = sorted(self.dolly_rows, key=lambda r: h(f"{self.salt}|pool|fold|P|{self.rows[r]['stim_id']}"))
        out = {}
        for f, sl in (("A", slice(0, None, 2)), ("B", slice(1, None, 2))):
            out[f] = {"H": [self.pairs[p][0] for p in po[sl]], "Bn": [self.pairs[p][1] for p in po[sl]],
                      "P": list(qo[sl])}
        return out

    def ksubset(self, k: int) -> dict:
        """k-curve subset. k>=16: registered folds restricted to the subset; k<16: in-sample."""
        spec = self.items["k_curve_subsets"][str(k)]
        keep_p, keep_q = set(spec["pair_ids"]), set(spec["P_stims"])
        reg = self.items["folds"]["0"]
        if k >= 16:
            folds = {f: {"pair_ids": [p for p in reg[f]["pair_ids"] if p in keep_p],
                         "P_stims": [s for s in reg[f]["P_stims"] if s in keep_q]} for f in ("A", "B")}
            return self.fold_sets(None, folds)
        allf = {"pair_ids": spec["pair_ids"], "P_stims": spec["P_stims"]}
        fs = self.fold_sets(None, {"A": allf, "B": allf})
        return fs  # fit == score (IN_SAMPLE, flagged by the caller)

    def c11_folds(self) -> dict:
        h = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
        out = {"A": {}, "B": {}}
        for cls, sev in (("H", 3.0), ("Bn", 1.0), ("P", 0.0)):
            idx = [i for i in range(len(self.c11_sev)) if self.c11_sev[i] == sev]
            idx = sorted(idx, key=lambda i: h(f"{self.salt}|c11|{self.c11_ids[i]}"))
            out["A"][cls] = idx[0::2]
            out["B"][cls] = idx[1::2]
        return out


# --------------------------------------------------------------------------- #
# per-checkpoint arrays                                                        #
# --------------------------------------------------------------------------- #


class Ckpt:
    """Band means of one checkpoint's harvest arrays (cached as float32 npz)."""

    def __init__(self, tag: str, tag_dir: Path, *, offset: int = 0) -> None:
        self.tag = tag
        self.dir = guard_path(tag_dir)
        meta_p = tag_dir / "meta.json"
        self.meta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
        A = np.load(guard_path(tag_dir / "A_prompt.npy"), mmap_mode="r")
        self.L = int(self.meta.get("n_layers") or (A.shape[1] - 1))
        if A.shape[1] != self.L + 1:
            raise ValueError(f"{tag}: A_prompt has {A.shape[1]} hidden states but n_layers={self.L}")
        self.d = int(A.shape[2])
        self.n_rows = int(A.shape[0])
        self.offset = offset
        self.X = self._bands(A)                     # (6, n, d) float32
        self.A = A                                  # memmap, used for G3 endpoints
        self.norms = np.linalg.norm(self.X, axis=2)  # (6, n)
        self.c11 = self._bands_opt("A_c11.npy")
        self.dec = self._bands_opt("A_dec.npy", only_b6=True)
        self.dec1 = self._bands_opt("A_dec_tok1.npy", only_b6=True)
        self.WU = self._opt("WU_ref.npy")
        g = self._opt("gamma.npy")
        self.gamma = g if g is not None and g.shape == (self.d,) else np.ones(self.d, dtype=np.float32)

    def _opt(self, name: str) -> np.ndarray | None:
        p = self.dir / name
        return np.asarray(np.load(guard_path(p)), dtype=np.float32) if p.exists() else None

    def _bands(self, arr: np.ndarray) -> np.ndarray:
        out = np.empty((N_BANDS, arr.shape[0], arr.shape[2]), dtype=np.float32)
        for b in range(1, N_BANDS + 1):
            lo, hi = band_indices(self.L, b, offset=self.offset)
            out[b - 1] = np.asarray(arr[:, lo: hi + 1, :], dtype=np.float32).mean(axis=1)
        return out

    def _bands_opt(self, name: str, only_b6: bool = False) -> np.ndarray | None:
        p = self.dir / name
        if not p.exists():
            return None
        arr = np.load(guard_path(p), mmap_mode="r")
        if arr.ndim != 3 or arr.shape[1] != self.L + 1:
            logger.warning(f"{self.tag}: {name} shape {arr.shape} unexpected; skipped")
            return None
        if only_b6:
            lo, hi = band_indices(self.L, 6, offset=self.offset)
            return np.asarray(arr[:, lo: hi + 1, :], dtype=np.float32).mean(axis=1)[None]
        return self._bands(arr)

    def raw(self, rows: list[int], idx: int) -> np.ndarray:
        return np.asarray(self.A[rows, idx, :], dtype=np.float32)


# --------------------------------------------------------------------------- #
# candidate math                                                               #
# --------------------------------------------------------------------------- #


def _proj(x: np.ndarray, v: np.ndarray) -> np.ndarray:
    return np.asarray(x, dtype=np.float64) @ np.asarray(v, dtype=np.float64)


def _mean(x: np.ndarray, rows: list[int]) -> np.ndarray:
    return np.asarray(x[rows], dtype=np.float64).mean(axis=0)


def fit_dirs(ck: Ckpt, fs: dict) -> dict:
    """Fit-fold directions for every band + the fit-fold separation curve."""
    F, N6, dfit = [], [], []
    for b in range(N_BANDS):
        X = ck.X[b]
        f = unit(_mean(X, fs["H"]) - _mean(X, fs["P"]))
        n = unit(_mean(X, fs["H"]) - _mean(X, fs["Bn"]))
        F.append(f)
        N6.append(n)
        dfit.append(cohens_d_pooled(_proj(X[fs["H"]], f), _proj(X[fs["P"]], f)))
    dfit_arr = np.array([v if np.isfinite(v) else -np.inf for v in dfit])
    return {"F": F, "N6": N6, "dfit": dfit, "b_read": int(np.argmax(dfit_arr)) + 1,
            "b_write": int(np.argmax(dfit_arr[:5])) + 1}


def g4_basis(ck: Ckpt) -> np.ndarray | None:
    if ck.WU is None:
        return None
    M = (ck.WU * ck.gamma[None, :]).astype(np.float64).T          # (d, 44)
    q, r = np.linalg.qr(M)
    keep = np.abs(np.diag(r)) > 1e-8 * max(1.0, float(np.abs(np.diag(r)).max()))
    return q[:, keep]


def score_fold(ck: Ckpt, fit: dict, fs_fit: dict, fs_sc: dict, stim: Stim, U: np.ndarray | None,
               *, band: int | None = None, want: set[str] | None = None) -> dict:
    """All Tier-A quantities for one (fit fold, scoring fold) assignment.

    band=None uses the registered b*_read chosen on the fit fold; an integer evaluates the
    candidate at that band instead (band curves)."""
    b = fit["b_read"] if band is None else int(band)
    bi = b - 1
    X = ck.X[bi]
    F = fit["F"][bi]
    out: dict[str, Any] = {"band": b}
    H, Bn, P = fs_sc["H"], fs_sc["Bn"], fs_sc["P"]
    w = want or {"G1", "G2", "G3", "G4", "A1_slope", "A3", "W7c", "plain_DiM"}
    mH, mBn, mP = _mean(X, H), _mean(X, Bn), _mean(X, P)
    projH, projP = _proj(X[H], F), _proj(X[P], F)
    gapF = float(projH.mean() - projP.mean())
    if "G1" in w:
        f_sc, n_sc = unit(mH - mP), unit(mH - mBn)
        if np.linalg.norm(f_sc) < 0.5 or np.linalg.norm(n_sc) < 0.5:
            out["G1"] = float("nan")
        else:
            out["G1"] = float(np.degrees(np.arccos(np.clip(abs(float(f_sc @ n_sc)), 0.0, 1.0))))
    if "G2" in w:
        num = float(np.linalg.norm(mH - mBn))
        den = float(np.linalg.norm(mBn - mP))
        ref = float(np.linalg.norm(mH - mP))
        out["G2_censored"] = bool(den < 0.05 * ref)
        out["G2"] = float(num / den) if den > 0 else float("inf")
    if "G3" in w:
        lo, hi = band_indices(ck.L, b, offset=ck.offset)
        top = min(hi, ck.L - 1)
        if top <= lo - 1:
            out["G3"] = float("nan")
        else:
            D = (ck.raw(H, top) - ck.raw(H, lo - 1)).astype(np.float64).mean(axis=0)
            out["G3"] = float(unit(D) @ F) if np.linalg.norm(D) > 1e-8 else float("nan")
    if "G4" in w:
        if U is None:
            out["G4"] = out["G4_ratio"] = float("nan")
        else:
            def resid(Z: np.ndarray) -> np.ndarray:
                Z = np.asarray(Z, dtype=np.float64)
                return Z - (Z @ U) @ U.T
            Yf_H, Yf_P = resid(X[fs_fit["H"]]), resid(X[fs_fit["P"]])
            wv = unit(Yf_H.mean(0) - Yf_P.mean(0))
            d = cohens_d_pooled(resid(X[H]) @ wv, resid(X[P]) @ wv)
            out["G4"] = float(d)
            out["G4_ratio"] = float(d * d) if np.isfinite(d) else float("nan")
    if "A1_slope" in w:
        if ck.c11 is None or abs(gapF) < 1e-12:
            out["A1_slope"] = float("nan")
        else:
            s = _proj(ck.c11[bi], F)
            sev = stim.c11_sev
            slope = float(np.polyfit(sev, s, 1)[0])
            out["A1_slope"] = slope / gapF
    if "A3" in w:
        excl = set(fs_fit["H"]) | set(fs_fit["Bn"]) | set(fs_fit["P"])
        by_dom: dict[str, dict[str, list[int]]] = {}
        for r in stim.hard_harm:
            if r in excl:
                continue
            dm = stim.domain.get(stim.rows[r]["stim_id"])
            if dm:
                by_dom.setdefault(dm, {"h": [], "b": []})["h"].append(r)
        for r in stim.hard_benign:
            if r in excl:
                continue
            dm = stim.domain.get(stim.rows[r]["stim_id"])
            if dm:
                by_dom.setdefault(dm, {"h": [], "b": []})["b"].append(r)
        g = {}
        for dm, v in sorted(by_dom.items()):
            if len(v["h"]) >= 4 and len(v["b"]) >= 4:
                g[dm] = cohens_d_pooled(_proj(X[v["h"]], F), _proj(X[v["b"]], F))
        vals = np.array([x for x in g.values() if np.isfinite(x)])
        out["A3_domains"] = {k: {"g": float(v), "n_harm": len(by_dom[k]["h"]), "n_benign": len(by_dom[k]["b"])}
                             for k, v in g.items()}
        if vals.size >= 3:
            sd = float(vals.std(ddof=1))
            mu = float(vals.mean())
            out["A3_sd"] = sd
            out["A3_censored"] = bool(abs(mu) < 0.05 * float(np.abs(vals).max()))
            out["A3"] = sd / abs(mu) if abs(mu) > 0 else float("inf")
        else:
            out["A3"] = out["A3_sd"] = float("nan")
            out["A3_censored"] = False
    if "W7c" in w:
        r_late = fit["F"][5]
        excl = set(fs_fit["H"]) | set(fs_fit["Bn"]) | set(fs_fit["P"])
        hh = [stim.dec_index[r] for r in stim.hard_harm if r not in excl]
        hb = [stim.dec_index[r] for r in stim.hard_benign if r not in excl]
        for key, arr in (("W7c", ck.dec), ("W7c_tok1", ck.dec1)):
            if arr is None:
                out[key] = float("nan")
            else:
                out[key] = cohens_d_pooled(_proj(arr[0][hh], r_late), _proj(arr[0][hb], r_late))
    if "plain_DiM" in w:
        out["plain_DiM"] = cohens_d_pooled(projH, projP)
    return out


SCALARS = ("G1", "G2", "G3", "G4", "G4_ratio", "A1_slope", "A3", "A3_sd", "W7c", "W7c_tok1", "plain_DiM")


def crossfit(ck: Ckpt, fs: dict, stim: Stim, U: np.ndarray | None, *, band: int | None = None,
             in_sample: bool = False, want: set[str] | None = None) -> dict:
    """Registered cross-fitted value: fit A -> score B, fit B -> score A, averaged."""
    per = {}
    for f, g in (("A", "B"), ("B", "A")):
        fs_fit, fs_sc = fs[f], (fs[f] if in_sample else fs[g])
        fit = fit_dirs(ck, fs_fit)
        per[f] = score_fold(ck, fit, fs_fit, fs_sc, stim, U, band=band, want=want)
        per[f]["b_read"], per[f]["b_write"] = fit["b_read"], fit["b_write"]
        per[f]["dfit"] = [float(x) if np.isfinite(x) else None for x in fit["dfit"]]
        if in_sample:
            break
    folds = list(per.values())
    reg: dict[str, Any] = {}
    for k in SCALARS:
        vals = [p.get(k) for p in folds if p.get(k) is not None]
        vals = [float(v) for v in vals if v is not None]
        fin = [v for v in vals if np.isfinite(v)]
        reg[k] = float(np.mean(fin)) if len(fin) == len(vals) and fin else (float("nan") if not fin else float(np.mean(fin)))
    reg["G2_censored"] = any(p.get("G2_censored", False) for p in folds)
    reg["A3_censored"] = any(p.get("A3_censored", False) for p in folds)
    return {"registered": reg, "per_fold": per}


# --------------------------------------------------------------------------- #
# per-tag driver                                                               #
# --------------------------------------------------------------------------- #


def c11_transfer(ck: Ckpt, stim: Stim) -> float:
    if ck.c11 is None:
        return float("nan")
    fsc = stim.c11_folds()
    vals = []
    for f, g in (("A", "B"), ("B", "A")):
        dfit = []
        for b in range(N_BANDS):
            X = ck.c11[b]
            F = unit(_mean(X, fsc[f]["H"]) - _mean(X, fsc[f]["P"]))
            dfit.append(cohens_d_pooled(_proj(X[fsc[f]["H"]], F), _proj(X[fsc[f]["P"]], F)))
        dfa = np.array([v if np.isfinite(v) else -np.inf for v in dfit])
        bi = int(np.argmax(dfa))
        X = ck.c11[bi]
        mH, mBn, mP = _mean(X, fsc[g]["H"]), _mean(X, fsc[g]["Bn"]), _mean(X, fsc[g]["P"])
        den = float(np.linalg.norm(mBn - mP))
        vals.append(float(np.linalg.norm(mH - mBn)) / den if den > 0 else float("inf"))
    return float(np.mean(vals))


def shuffled_band(ck: Ckpt, fs: dict, stim: Stim, U: np.ndarray | None, tag: str) -> dict:
    """Permutation band: class labels permuted among the 32 registered items (sizes kept)."""
    rows_by_f = {f: fs[f]["H"] + fs[f]["Bn"] + fs[f]["P"] for f in ("A", "B")}
    sizes = {f: (len(fs[f]["H"]), len(fs[f]["Bn"]), len(fs[f]["P"])) for f in ("A", "B")}
    draws: dict[str, list[float]] = {k: [] for k in ("G1", "G2", "G3", "G4", "A1_slope", "plain_DiM")}
    want = set(draws)
    for i in range(N_PERM):
        seed = int(hashlib.sha256(f"iter5_screen_v1|{tag}|perm|{i}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        perm_fs = {}
        for f in ("A", "B"):
            rr = list(rng.permutation(rows_by_f[f]))
            nh, nb, _ = sizes[f]
            perm_fs[f] = {"H": rr[:nh], "Bn": rr[nh: nh + nb], "P": rr[nh + nb:]}
        res = crossfit(ck, perm_fs, stim, U, want=want)["registered"]
        for k in draws:
            draws[k].append(res.get(k, float("nan")))
    return {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] if np.isfinite(v).any() else [None, None]
            for k, v in ((k, np.array(v, dtype=float)) for k, v in draws.items())}


def tag_dir_of(tag: str) -> tuple[Path, str]:
    if (H4 / tag).is_dir():
        return H4 / tag, "H4"
    if (H2 / tag).is_dir():
        return H2 / tag, "H2"
    raise FileNotFoundError(tag)


def run_tag(tag: str, group: str, stim: Stim, prereg: dict, *, stab: str) -> dict:
    t0 = time.time()
    tdir, root = tag_dir_of(tag)
    ck = Ckpt(tag, tdir)
    if ck.n_rows != len(stim.rows):
        raise ValueError(f"{tag}: A_prompt has {ck.n_rows} rows, stimuli.json has {len(stim.rows)} (order unverifiable)")
    U = g4_basis(ck)
    fs = stim.registered()
    main = crossfit(ck, fs, stim, U)
    rec: dict[str, Any] = {
        "tag": tag, "group": group, "root": root, "repo": (ck.meta.get("build_info") or {}).get("repo") or ck.meta.get("repo"),
        "n_layers": ck.L, "hidden": ck.d, "registered": main["registered"],
        "censored": {"G2": main["registered"]["G2_censored"], "A3": main["registered"]["A3_censored"]},
        "bstar_read": {f: main["per_fold"][f]["b_read"] for f in main["per_fold"]},
        "bstar_write": {f: main["per_fold"][f]["b_write"] for f in main["per_fold"]},
        "per_fold": main["per_fold"], "flags": {},
    }
    if U is None:
        rec["flags"]["G4"] = ["no WU_ref"]
    if ck.dec is None:
        rec["flags"]["W7c"] = ["no A_dec"]
    if ck.c11 is None:
        rec["flags"]["A1_slope"] = ["no A_c11"]
    # band curves
    rec["band_curves"] = {k: [] for k in ("G1", "G2", "G3", "G4", "A1_slope", "A3", "plain_DiM")}
    for b in range(1, N_BANDS + 1):
        r = crossfit(ck, fs, stim, U, band=b, want={"G1", "G2", "G3", "G4", "A1_slope", "A3", "plain_DiM"})["registered"]
        for k in rec["band_curves"]:
            rec["band_curves"][k].append(r.get(k))
    # k-curve
    kc: dict[str, dict[str, Any]] = {k: {} for k in SCALARS}
    for k in (4, 8, 16, 32):
        if k == 32:
            r = main["registered"]
        else:
            r = crossfit(ck, stim.ksubset(k), stim, U, in_sample=(k < 16))["registered"]
        for c in SCALARS:
            kc[c][str(k)] = r.get(c)
    rpool = crossfit(ck, stim.pool(), stim, U)["registered"]
    for c in SCALARS:
        kc[c]["pool"] = rpool.get(c)
        kc[c]["0"] = "N/A"
    rec["k_curve"] = kc
    rec["k_curve_notes"] = {"4": "IN_SAMPLE", "8": "IN_SAMPLE", "16": "cross-fitted", "32": "registered", "pool": "40 pairs + 48 P, cross-fitted", "0": "N/A (no k=0 point for Tier A)"}
    # stability
    draws = []
    if stab == "stab18":
        grid = [(d, s, o) for d in (0, 1, 2) for s in (0, 1, 2) for o in (-1, 1)]
    else:
        grid = [(d, s, 0) for d in (0, 1) for s in (1, 2)]
    ck_off: dict[int, Ckpt] = {0: ck}
    for d, s, o in grid:
        if o not in ck_off:
            ck_off[o] = Ckpt(tag, tdir, offset=o)
        ckd = ck_off[o]
        r = crossfit(ckd, stim.draw(d, s), stim, U)["registered"]
        draws.append({"prompt_draw": d, "fold_seed": s, "band_offset": o,
                      "values": {c: r.get(c) for c in SCALARS}})
    for o in [k for k in ck_off if k != 0]:
        del ck_off[o]
    rec["stability"] = {"grid": stab, "draws": draws}
    # shuffled-label band
    band = shuffled_band(ck, fs, stim, U, tag)
    rec["shuffled_band"] = {k: {"lo": v[0], "hi": v[1],
                                "outside": (None if v[0] is None or not np.isfinite(main["registered"].get(k, np.nan))
                                            else bool(main["registered"][k] < v[0] or main["registered"][k] > v[1]))}
                            for k, v in band.items()}
    # transfer (field norm I)
    rec["transfer"] = {"G2_c11": c11_transfer(ck, stim)}
    rec["A3_domains"] = {f: main["per_fold"][f].get("A3_domains") for f in main["per_fold"]}
    rec["utc"] = utc_now()
    rec["runtime_s"] = round(time.time() - t0, 2)
    del ck
    gc.collect()
    return rec


def _clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return f if math.isfinite(f) else (None if math.isnan(f) else ("inf" if f > 0 else "-inf"))
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def add_bars(rec: dict, tag: str) -> None:
    try:
        import bars  # noqa: PLC0415
        tdir, _ = tag_dir_of(tag)
        rec["bars"] = bars.compute_bars(tdir)
    except Exception as exc:  # noqa: BLE001 - bars are reported, never fatal to the screen
        logger.error(f"{tag}: bars failed: {exc!r}")
        rec["bars"] = {"error": repr(exc)[:400]}


# --------------------------------------------------------------------------- #
# structural-pair prompt bootstrap (for S5 false alarms / sensitivity)         #
# --------------------------------------------------------------------------- #


STRUCTURAL_HUB_PAIRS = [
    ("F1__ref", "HG__huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2"),
    ("HG__Qwen--Qwen3-1.7B", "HG__huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2"),
    ("HG__Qwen--Qwen2.5-1.5B-Instruct", "HG__Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3"),
    ("HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct", "HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct-abliterated"),
    ("F2__ref", "HG__mylesgoose--Llama-3.2-1B-Instruct-abliterated2"),
    ("HG__amd--AMD-OLMo-1B", "HG__amd--AMD-OLMo-1B-SFT"),
    ("HG__amd--AMD-OLMo-1B-SFT", "HG__amd--AMD-OLMo-1B-SFT-DPO"),
    ("HG__tiiuae--Falcon3-1B-Base", "F3__ref"),
]


def structural_pairs(panel_tags: list[str]) -> list[tuple[str, str, str]]:
    """Pair STRUCTURE by rule from tag names only (prereg amendment A2): every in-house arm vs its
    family ref, plus the 8 Hub lineage pairs. Never read from I4/assets/pairs.json (it embeds
    behaviour rates)."""
    pairs = []
    for t in panel_tags:
        if "__" in t and not t.startswith("HG__"):
            fk, arm = t.split("__", 1)
            if arm != "ref" and f"{fk}__ref" in panel_tags:
                pairs.append((f"{fk}__ref->{t}", f"{fk}__ref", t))
    for par, chi in STRUCTURAL_HUB_PAIRS:
        pairs.append((f"{par}->{chi}", par, chi))
    return pairs


def pair_bootstrap(stim: Stim, panel_tags: list[str]) -> dict:
    pairs = structural_pairs(panel_tags)
    fs = stim.registered()
    out = {}
    cache: dict[str, Ckpt] = {}

    def get(tag: str) -> Ckpt | None:
        if tag not in cache:
            try:
                tdir, _ = tag_dir_of(tag)
                cache[tag] = Ckpt(tag, tdir)
            except (FileNotFoundError, ValueError) as exc:
                logger.warning(f"pair boot: {tag} unavailable ({exc})")
                return None
        return cache[tag]

    keys = ("G1", "G2", "G3", "G4", "A1_slope", "A3", "W7c", "plain_DiM")
    for pid, par, chi in pairs:
        tp = par if par in panel_tags else None
        tc = chi if chi in panel_tags else None
        if tp is None or tc is None:
            out[pid] = {"parent": par, "child": chi, "status": "NOT_IN_PANEL"}
            continue
        cp, cc = get(tp), get(tc)
        if cp is None or cc is None:
            out[pid] = {"parent": tp, "child": tc, "status": "ARRAYS_MISSING"}
            continue
        Up, Uc = g4_basis(cp), g4_basis(cc)
        base_p = crossfit(cp, fs, stim, Up)["registered"]
        base_c = crossfit(cc, fs, stim, Uc)["registered"]
        seed = int(hashlib.sha256(f"iter5_screen_v1|pairboot|{pid}".encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        deltas = {k: [] for k in keys}
        for _ in range(PAIR_BOOT_B):
            rs = {}
            for f in ("A", "B"):
                npair = len(fs[f]["H"])
                ip = rng.integers(0, npair, npair)
                iq = rng.integers(0, len(fs[f]["P"]), len(fs[f]["P"]))
                rs[f] = {"H": [fs[f]["H"][i] for i in ip], "Bn": [fs[f]["Bn"][i] for i in ip],
                         "P": [fs[f]["P"][i] for i in iq]}
            vp = crossfit(cp, rs, stim, Up, want=set(keys))["registered"]
            vc = crossfit(cc, rs, stim, Uc, want=set(keys))["registered"]
            for k in keys:
                deltas[k].append(float(vc.get(k, np.nan)) - float(vp.get(k, np.nan)))
        out[pid] = {"parent": tp, "child": tc, "status": "OK", "B": PAIR_BOOT_B,
                    "delta": {k: float(base_c.get(k, np.nan)) - float(base_p.get(k, np.nan)) for k in keys},
                    "ci95": {k: ([float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))]
                                 if np.isfinite(np.array(v)).any() else [None, None]) for k, v in deltas.items()}}
        logger.info(f"pair boot {pid}: done")
        for t in list(cache):
            if t not in (tp, tc):
                del cache[t]
        gc.collect()
    return out


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #


def panel_tags() -> tuple[list[str], dict[str, list[str]]]:
    panel = json.loads((RES / "panel.json").read_text())
    return list(panel["included"]), {k: list(v) for k, v in panel.get("blocks", {}).items()}


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--tags", nargs="*", default=[])
    ap.add_argument("--pair-boot", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-bars", action="store_true")
    args = ap.parse_args()
    os.environ.setdefault("OMP_NUM_THREADS", "4")
    prereg = load_prereg()
    stim = Stim(prereg)
    OUT.mkdir(parents=True, exist_ok=True)
    stab18 = set(prereg["stability_C"]["STAB18_rows"])
    panel, blocks = panel_tags()
    jobs: list[tuple[str, str]] = []
    if args.all:
        jobs += [(t, "panel") for t in panel]
        for g, ts in blocks.items():
            jobs += [(t, g) for t in ts]
    for t in args.tags:
        grp = "panel" if t in panel else next((g for g, ts in blocks.items() if t in ts), "extra")
        jobs.append((t, grp))
    seen = set()
    for tag, group in jobs:
        if tag in seen:
            continue
        seen.add(tag)
        outp = OUT / f"{tag}.json"
        if outp.exists() and not args.force:
            logger.info(f"skip {tag} (exists)")
            continue
        try:
            rec = run_tag(tag, group, stim, prereg, stab="stab18" if tag in stab18 else "stab4")
            if not args.no_bars:
                add_bars(rec, tag)
            outp.write_text(json.dumps(_clean(rec), indent=1))
            r = rec["registered"]
            logger.info(f"{tag} [{group}] {rec['runtime_s']}s b*={rec['bstar_read']} G1={r['G1']:.2f} "
                        f"G2={r['G2']:.3f} G3={r['G3']:.3f} G4={r['G4']:.3f} A1s={r['A1_slope']:.3f} "
                        f"A3={r['A3']:.3f} W7c={r['W7c']:.3f}")
        except (FileNotFoundError, ValueError, KeyError) as exc:
            logger.error(f"{tag}: FAILED {exc!r}")
            outp.write_text(json.dumps({"tag": tag, "group": group, "status": "ERROR", "error": repr(exc)[:500]}))
    if args.pair_boot:
        res = pair_bootstrap(stim, panel)
        (RES / "screen/pair_boot_tierA.json").write_text(json.dumps(_clean(res), indent=1))
        logger.info(f"pair bootstrap: {sum(1 for v in res.values() if v.get('status') == 'OK')} pairs")


if __name__ == "__main__":
    main()
