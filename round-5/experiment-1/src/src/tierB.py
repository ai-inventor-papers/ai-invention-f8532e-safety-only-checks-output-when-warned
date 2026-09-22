#!/usr/bin/env python3
"""Tier B: GPU intervention pass (W1-W8, A1_prior, A2, bars, patching, stability draws).

Definitions: results/prereg.json (authoritative) + src/SPEC_tierB.md. Every contrast's baseline row is
computed in the SAME forward batch as its intervened rows (rowhooks.RowRunner: one prompt x many configs,
no padding). Directions / b* are fit on one fold from unperturbed batch-1 captures, scored on the other,
folds swapped and averaged.

CLI:
  python src/tierB.py --tags T1 T2 ... | --queue results/tierB_queue.json
         [--draws none|registered|stab4|stab18|auto] [--phase 1|2] [--max-minutes N]
  python src/tierB.py --repo <hf_repo> --tag <tag> --harvest-dir <dir>      (external-checkpoint mode)
"""
from __future__ import annotations

import os

os.environ.setdefault("TORCH_DISABLE_NATIVE_JIT", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import argparse  # noqa: E402
import gc  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import resource  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

import numpy as np  # noqa: E402

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
sys.path.insert(0, str(WS / "src/reuse"))
sys.path.insert(0, str(WS / "src/reuse/src_i3_h2"))

import tierA  # noqa: E402  (Stim bookkeeping, prereg guard)
from loguru import logger  # noqa: E402

from core import GpuLease, band_indices, cohens_d_pooled, unit, utc_now  # noqa: E402
from interv import orthogonal_random  # noqa: E402
from rowhooks import RowCfg, RowRunner  # noqa: E402

RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
I4 = RUN / "iter_4/gen_art/gen_art_experiment_1"
H4 = I4 / "harvest"
RES = WS / "results"
OUT = RES / "screen"
SALT = "iter5_screen_v1"
N_R = 10
N_R_STAB = 5
FORBIDDEN = tierA.FORBIDDEN

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
(WS / "logs").mkdir(exist_ok=True)
logger.add(WS / "logs/tierB_run.log", rotation="30 MB", level="DEBUG")


def guard(p: Path) -> Path:
    s = str(p)
    for bad in FORBIDDEN:
        if bad in s:
            raise PermissionError(f"Tier B must never open outcome/sibling files: {s}")
    return p


def rss_gb() -> float:
    try:
        for line in open("/proc/self/status"):
            if line.startswith("VmRSS"):
                return int(line.split()[1]) / 1e6
    except OSError:
        pass
    return float("nan")


def peak_rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6


def seed_of(tag: str, band: str, i: int) -> int:
    return int(hashlib.sha256(f"{SALT}|{tag}|{band}|{i}".encode()).hexdigest(), 16) % (2 ** 32)


def rdraws(tag: str, key: str, v: np.ndarray, n: int) -> list[np.ndarray]:
    return [orthogonal_random(v, rng=np.random.default_rng(seed_of(tag, key, i))) for i in range(n)]


def fnum(x: Any) -> Any:
    if isinstance(x, (np.floating, float)):
        return float(x) if np.isfinite(x) else None
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def jclean(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): jclean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jclean(v) for v in o]
    if isinstance(o, np.ndarray):
        return [jclean(v) for v in o.tolist()]
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def spearman(a, b) -> float:
    from scipy.stats import spearmanr
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return float("nan")
    return float(spearmanr(a[ok], b[ok]).statistic)


def auroc(pos, neg) -> float:
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg):
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()
    return float(gt)


# --------------------------------------------------------------------------- #
# model building                                                               #
# --------------------------------------------------------------------------- #


def build_arm(tag: str, repo_override: str | None = None):
    """-> (model, tok, render_fn, info). Weights are built by the iteration-4 recipe (reuse.variants)."""
    import variants  # reuse copy
    import harvest_variants  # noqa: F401  (iter5 confirm-fix: importing this WS-local module applies its
        # multi-arch block-finder / eager-attention / pad-eos-bos-token monkeypatches onto `variants`.
        # external_harvest() also imports it, but when a checkpoint's harvest is already DONE (resumable
        # driver: `--repo` mode skips external_harvest entirely), build_arm is the ONLY loader called in
        # this process, so the patch must be (re-)applied here too, not just there. Re-importing an
        # already-imported module is a cheap no-op (sys.modules cache); no formula/battery code changes.
        # See results/deviations_confirmfix.json.)
    variants.EDITS = I4 / "results/edits"          # read-only edit caches (hbar / lesion)
    # the full-tensor sha (A13 generation-vs-harvest audit) costs ~tens of seconds per load and is not used here;
    # the 6-tensor weight_fingerprint is kept and compared with the harvest meta.json
    variants.full_tensor_sha = lambda model: "skipped_in_tierB"
    if repo_override:
        fk, variant = "HG", repo_override.replace("/", "--", 1)
    else:
        fk, variant = tag.split("__", 1)
    if variant in ("lora", "dpo"):
        raise FileNotFoundError(f"{variant} adapter not on disk (iteration-4 PRIVATE/adapters absent)")
    return variants.build(fk, variant, allow_train=False)


def pre_download(tag: str, repo_override: str | None = None) -> str:
    import variants
    fk, variant = ("HG", repo_override.replace("/", "--", 1)) if repo_override else tag.split("__", 1)
    return variants.download(variants.repo_for(fk, variant))


# --------------------------------------------------------------------------- #
# the battery                                                                  #
# --------------------------------------------------------------------------- #


class Battery:
    def __init__(self, tag: str, rr: RowRunner, render, stim: tierA.Stim, variant: str) -> None:
        self.tag, self.rr, self.render, self.stim, self.variant = tag, rr, render, stim, variant
        self.L, self.d = rr.L, rr.d
        self.base: dict[Any, np.ndarray] = {}      # key -> (L+1, d) unperturbed batch-1 capture
        self.raw_norm: dict[Any, np.ndarray] = {}  # key -> (L,) raw block-output norms
        self.ids: dict[Any, list[int]] = {}
        self.items: dict[str, np.ndarray] = {}
        self.disp: dict[str, dict[int, list]] = {}  # label -> band -> list of (ratio, pct)

    # -- prompts
    def text_of(self, key) -> str:
        if isinstance(key, tuple) and key[0] == "c11":
            return self.render(self.stim_c11[key[1]]["prompt"])
        return self.render(self.stim.rows[key]["text"])

    def ensure_base(self, keys) -> None:
        for k in keys:
            if k in self.base:
                continue
            ids = self.rr.encode(self.text_of(k))
            self.ids[k] = ids
            o = self.rr.run(ids, [RowCfg()])
            self.base[k] = o["X"][0]
            self.raw_norm[k] = o["raw"][0]

    def bands(self, X: np.ndarray, off: int) -> np.ndarray:
        """X (..., L+1, d) -> (..., 6, d) band means."""
        out = []
        for b in range(1, 7):
            lo, hi = band_indices(self.L, b, offset=off)
            out.append(X[..., lo: hi + 1, :].mean(axis=-2))
        return np.stack(out, axis=-2)

    def bidx(self, b: int, off: int) -> list[int]:
        lo, hi = band_indices(self.L, b, offset=off)
        return list(range(lo, hi + 1))

    def Xb(self, keys, off) -> np.ndarray:
        return self.bands(np.stack([self.base[k] for k in keys]).astype(np.float64), off)   # (n, 6, d)

    # -- norm-percentile reference (all unperturbed S32 prompts), per raw block index
    def set_norm_ref(self, keys) -> None:
        self.norm_ref = np.stack([self.raw_norm[k] for k in keys])        # (n, L)

    def rec_disp(self, label: str, band: int, stats: dict, rows: list[int], blocks: list[int]) -> None:
        dd = self.disp.setdefault(label, {}).setdefault(band, [])
        for j in blocks:
            if j not in stats:
                continue
            ratio, nn = stats[j]
            ref = self.norm_ref[:, j]
            for r in rows:
                pct = float(100.0 * (ref < nn[r]).mean())
                dd.append((float(ratio[r]), pct))

    # -- fits
    def fit(self, fs: dict, off: int) -> dict:
        XH, XP, XBn = self.Xb(fs["H"], off), self.Xb(fs["P"], off), self.Xb(fs["Bn"], off)
        F, N6, dfit = [], [], []
        for b in range(6):
            f = unit(XH[:, b].mean(0) - XP[:, b].mean(0))
            n = unit(XH[:, b].mean(0) - XBn[:, b].mean(0))
            F.append(f)
            N6.append(n)
            dfit.append(cohens_d_pooled(XH[:, b] @ f, XP[:, b] @ f))
        da = np.array([v if np.isfinite(v) else -np.inf for v in dfit])
        return {"F": F, "N6": N6, "dfit": dfit, "b_read": int(np.argmax(da)) + 1,
                "b_write": int(np.argmax(da[:5])) + 1, "r_late": F[5]}

    def readout(self, X: np.ndarray, r_late: np.ndarray, off: int) -> np.ndarray:
        lo, hi = band_indices(self.L, 6, offset=off)
        return X[..., lo: hi + 1, :].astype(np.float64).mean(axis=-2) @ r_late

    # -- one (fit, score) fold
    def fold(self, fit_fs: dict, sc_fs: dict, off: int, *, full: bool, nR: int, patch: bool, lab: str,
             Xc: np.ndarray | None) -> dict:
        tag = self.tag
        ft = self.fit(fit_fs, off)
        F, N6, rl = ft["F"], ft["N6"], ft["r_late"]
        bw, br = ft["b_write"], ft["b_read"]
        H, Bn, P = sc_fs["H"], sc_fs["Bn"], sc_fs["P"]
        yP = self.readout(np.stack([self.base[k] for k in P]), rl, off)
        mean_P = float(yP.mean())
        out: dict[str, Any] = {"b_read": br, "b_write": bw, "dfit": ft["dfit"], "mean_P": mean_P}
        bands_W1 = list(range(1, 7)) if full else [bw]
        R_F = {b: rdraws(tag, str(b), F[b - 1], nR) for b in bands_W1}
        R_N = {b: rdraws(tag, f"N6_{b}", N6[b - 1], nR) for b in bands_W1}
        # ---------------- H battery: W1 (F + R), W3 (B4 all vs last), W4 (from F at b_write), patching
        b4 = self.bidx(4, off)
        p0_i, p1F_i, p1R_i = [], {b: [] for b in bands_W1}, {b: [] for b in bands_W1}
        w3_all_i, w3_last_i, patch_i = [], [], []
        w4_num_b, w4_num_end, w4_nb, w4_ne = [], [], [], []
        lo_w, hi_w = band_indices(self.L, bw, offset=off)
        if patch:
            meanP_fit = np.stack([self.base[k] for k in fit_fs["P"]]).astype(np.float64).mean(0)
        for k in H:
            cfgs, lab_ = [RowCfg()], [("base",)]
            for b in bands_W1:
                idx = self.bidx(b, off)
                cfgs.append(RowCfg(proj=[(idx, F[b - 1], None, "last")]))
                lab_.append(("F", b))
                for i, r in enumerate(R_F[b]):
                    cfgs.append(RowCfg(proj=[(idx, F[b - 1], r, "last")]))
                    lab_.append(("R", b, i))
            if 4 not in bands_W1:
                cfgs.append(RowCfg(proj=[(b4, F[3], None, "last")]))
                lab_.append(("W3last",))
            cfgs.append(RowCfg(proj=[(b4, F[3], None, "all")]))
            lab_.append(("W3all",))
            if patch:
                cfgs.append(RowCfg(patch={i: meanP_fit[i] for i in b4}))
                lab_.append(("patch",))
            o = self.rr.run(self.ids[k], cfgs)
            y = self.readout(o["X"], rl, off)
            p0 = y[0]
            p0_i.append(p0)
            pos = {l: n for n, l in enumerate(lab_)}
            for b in bands_W1:
                p1F_i[b].append(y[pos[("F", b)]])
                p1R_i[b].append([y[pos[("R", b, i)]] for i in range(nR)])
                blocks = [i - 1 for i in self.bidx(b, off)]
                self.rec_disp(f"{lab}F", b, o["stats"], [pos[("F", b)]], blocks)
                self.rec_disp(f"{lab}R", b, o["stats"], [pos[("R", b, i)] for i in range(nR)], blocks)
            w3_last_i.append(y[pos[("F", 4)]] if 4 in bands_W1 else y[pos[("W3last",)]])
            w3_all_i.append(y[pos[("W3all",)]])
            if patch:
                patch_i.append(y[pos[("patch",)]])
            rF = pos[("F", bw)]
            Fw = F[bw - 1]
            w4_num_b.append(float((o["X"][rF, hi_w] - o["X"][0, hi_w]) @ Fw))
            w4_num_end.append(float((o["X"][rF, self.L] - o["X"][0, self.L]) @ Fw))
            w4_nb.append(float(np.linalg.norm(o["X"][0, hi_w])))
            w4_ne.append(float(np.linalg.norm(o["X"][0, self.L])))
        p0_i = np.array(p0_i)
        p0 = float(p0_i.mean())
        gap = abs(p0 - mean_P)
        out.update({"p0": p0, "gap": gap, "p0_items_sd": float(p0_i.std(ddof=1)) if len(p0_i) > 1 else None})
        W1c = {}
        for b in bands_W1:
            pF = np.array(p1F_i[b])
            pR = np.array(p1R_i[b])            # (n_items, nR)
            dF = abs(pF.mean() - p0)
            dR = np.median(np.abs(pR.mean(0) - p0))
            W1c[b] = (dF - dR) / gap if gap > 0 else float("nan")
            self.items[f"{lab}W1_dF_b{b}"] = np.abs(pF - p0_i)
            self.items[f"{lab}W1_dR_b{b}"] = np.abs(pR - p0_i[:, None])
            self.items[f"{lab}W1_p1F_b{b}"] = pF
            self.items[f"{lab}W1_p1R_b{b}"] = pR
            out.setdefault("sanity_B", {})[b] = {"absdF": float(dF), "median_absdR": float(dR)}
        self.items[f"{lab}p0_items"] = p0_i
        out["W1_curve"] = [W1c.get(b) for b in range(1, 7)]
        out["W1"] = W1c[bw]
        pl, pa = float(np.mean(w3_last_i)), float(np.mean(w3_all_i))
        den = abs(pl - p0)
        out["W3"] = abs(pa - p0) / den if den > 0 else float("nan")
        out["W3_censored"] = bool(den < 0.05 * gap)
        out["W3_parts"] = {"p1_all": pa, "p1_last": pl}
        cb = np.mean(w4_num_b) / np.mean(w4_nb)
        ce = np.mean(w4_num_end) / np.mean(w4_ne)
        out["W4"] = float(np.clip(1 - abs(ce) / abs(cb), -1, 1)) if abs(cb) > 0 else float("nan")
        out["W4_parts"] = {"c_b": float(cb), "c_end": float(ce)}
        if patch:
            eff_patch = np.array(patch_i) - p0_i
            eff_W1 = np.array(p1F_i[4] if 4 in p1F_i else w3_last_i) - p0_i
            out["patch_items"] = {"patch": eff_patch.tolist(), "W1_B4": eff_W1.tolist()}
        # ---------------- W5 on Bn
        p0b_i, p1N_i, p1NR_i = [], {b: [] for b in bands_W1}, {b: [] for b in bands_W1}
        for k in Bn:
            cfgs, lab_ = [RowCfg()], [("base",)]
            for b in bands_W1:
                idx = self.bidx(b, off)
                cfgs.append(RowCfg(proj=[(idx, N6[b - 1], None, "last")]))
                lab_.append(("N", b))
                for i, r in enumerate(R_N[b]):
                    cfgs.append(RowCfg(proj=[(idx, N6[b - 1], r, "last")]))
                    lab_.append(("R", b, i))
            o = self.rr.run(self.ids[k], cfgs)
            y = self.readout(o["X"], rl, off)
            pos = {l: n for n, l in enumerate(lab_)}
            p0b_i.append(y[0])
            for b in bands_W1:
                p1N_i[b].append(y[pos[("N", b)]])
                p1NR_i[b].append([y[pos[("R", b, i)]] for i in range(nR)])
        p0b_i = np.array(p0b_i)
        p0b = float(p0b_i.mean())
        W5c = {}
        for b in bands_W1:
            pN, pR = np.array(p1N_i[b]), np.array(p1NR_i[b])
            W5c[b] = (abs(pN.mean() - p0b) - np.median(np.abs(pR.mean(0) - p0b))) / gap if gap > 0 else float("nan")
            self.items[f"{lab}W5_dN_b{b}"] = np.abs(pN - p0b_i)
            self.items[f"{lab}W5_dR_b{b}"] = np.abs(pR - p0b_i[:, None])
        out["p0_Bn"] = p0b
        out["W5_curve"] = [W5c.get(b) for b in range(1, 7)]
        out["W5"] = W5c[bw]
        out["W6"] = out["W5"] - out["W1"]
        # ---------------- W2 greedy (fit fold H), ladder on scoring fold
        out.update(self.w2(fit_fs["H"], H, F, rl, off, mean_P, lab))
        # ---------------- W8 lesion
        out.update(self.w8(F[bw - 1], H, P, off))
        # ---------------- A1_prior
        if Xc is not None:
            Xcb = self.bands(Xc.astype(np.float64), off)
            f = F[br - 1]
            XH, XP = self.Xb(H, off)[:, br - 1] @ f, self.Xb(P, off)[:, br - 1] @ f
            den = XH.mean() - XP.mean()
            out["A1_prior"] = float((Xcb[br - 1] @ f - XP.mean()) / den) if abs(den) > 0 else float("nan")
        # ---------------- W7 decode
        if full:
            out.update(self.w7(H, F[bw - 1], self.bidx(bw, off), rl, off, gap, nR, tag, bw, lab))
        return out

    def w2(self, fitH, scH, F, rl, off, mean_P, lab) -> dict:
        def joint(bset):
            return RowCfg(proj=[(self.bidx(b, off), F[b - 1], None, "last") for b in bset])
        chosen: list[int] = []
        remaining = [1, 2, 3, 4, 5]
        drops_log = []
        while remaining:
            if len(remaining) == 1:
                chosen.append(remaining.pop())
                break
            cands = [chosen + [b] for b in remaining]
            ys = []
            for k in fitH:
                o = self.rr.run(self.ids[k], [RowCfg()] + [joint(c) for c in cands])
                y = self.readout(o["X"], rl, off)
                ys.append(y[0] - y[1:])            # drop per candidate
            dr = np.mean(ys, axis=0)
            best = int(np.argmax(dr))
            drops_log.append({str(b): float(v) for b, v in zip(remaining, dr)})
            chosen.append(remaining.pop(best))
        ladder_items = []
        for k in scH:
            o = self.rr.run(self.ids[k], [RowCfg()] + [joint(chosen[:j]) for j in range(1, 6)])
            ladder_items.append(self.readout(o["X"], rl, off))
        li = np.array(ladder_items)
        p0 = float(li[:, 0].mean())
        pk = li[:, 1:].mean(0)
        W2 = next((j + 1 for j in range(5) if (pk[j] - mean_P) < 0.5 * (p0 - mean_P)), 7)
        W2raw = next((j + 1 for j in range(5) if pk[j] < 0.5 * p0), 7)
        self.items[f"{lab}W2_ladder_items"] = li
        return {"W2": W2, "W2_censored": W2 == 7, "W2_raw_offset": W2raw, "W2_order": chosen,
                "W2_ladder": [p0] + pk.tolist(), "W2_greedy_drops": drops_log}

    def w8(self, u, H, P, off) -> dict:
        if self.rr.lesion_names is None:
            return {"W8": float("nan"), "W8_status": "NOT_RUN: " + self.rr.lesion_err}
        Xb0, Xb1 = {}, {}
        for k in list(H) + list(P):
            o = self.rr.run(self.ids[k], [RowCfg(), RowCfg(lesion_u=u)])
            Xb0[k], Xb1[k] = o["X"][0], o["X"][1]
        B0 = self.bands(np.stack([Xb0[k] for k in list(H) + list(P)]).astype(np.float64), off)
        B1 = self.bands(np.stack([Xb1[k] for k in list(H) + list(P)]).astype(np.float64), off)
        nH = len(H)
        cos = []
        for b in (4, 5, 6):
            f0 = unit(B0[:nH, b - 1].mean(0) - B0[nH:, b - 1].mean(0))
            f1 = unit(B1[:nH, b - 1].mean(0) - B1[nH:, b - 1].mean(0))
            cos.append(abs(float(f0 @ f1)))
        return {"W8": 1 - float(np.mean(cos)), "W8_cos": cos, "W8_status": "OK"}

    def w7(self, H, Fw, idx, rl, off, gap, nR, tag, bw, lab) -> dict:
        Rs = rdraws(tag, str(bw), Fw, nR)
        cfgs = [RowCfg(), RowCfg(proj=[(idx, Fw, None, "from_last")])] + \
               [RowCfg(proj=[(idx, Fw, r, "from_last")]) for r in Rs]
        Y, toks = [], []
        for k in H:
            o = self.rr.decode(self.ids[k], cfgs, n_new=8)
            Y.append(self.readout(o["X"], rl, off))          # (rows, 8)
            toks.append(o["tok"][0].tolist())
        Y = np.array(Y)                                       # (items, rows, 8)
        m = Y.mean(0)                                          # (rows, 8)
        p0t = m[0]
        curve = (np.abs(m[1] - p0t) - np.median(np.abs(m[2:] - p0t[None]), axis=0)) / gap if gap > 0 else \
            np.full(8, np.nan)
        self.items[f"{lab}W7_Y"] = Y
        return {"W7": float(np.mean(curve)), "W7_curve": curve.tolist(), "W7_tokens_unperturbed": toks}

    # -- A2 (fold-free), per draw
    def a2(self, Pkeys, Xc, u_ref, off) -> dict:
        XP = self.Xb(Pkeys, off)[:, 4]
        xc = self.bands(Xc.astype(np.float64), off)[4]
        dv = XP.mean(0) - xc
        n = float(np.linalg.norm(dv))
        mn = float(np.linalg.norm(XP, axis=1).mean())
        cos = float(unit(dv) @ u_ref) if u_ref is not None else float("nan")
        return {"A2": cos * n / mn, "A2_cos": cos, "A2_mag": n / mn}

    def draw(self, fs: dict, off: int, *, full: bool, nR: int, patch: bool, lab: str, Xc, u_ref) -> dict:
        keys = [k for f in ("A", "B") for c in ("H", "Bn", "P") for k in fs[f][c]]
        self.ensure_base(keys)
        pf = {}
        for fit, sc in (("A", "B"), ("B", "A")):
            pf[fit] = self.fold(fs[fit], fs[sc], off, full=full, nR=nR, patch=patch, lab=f"{lab}fit{fit}_", Xc=Xc)
        vals = {}
        for k in ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "A1_prior"):
            v = [pf[f].get(k) for f in ("A", "B")]
            v = [x for x in v if x is not None and np.isfinite(x)]
            vals[k] = float(np.mean(v)) if v else None
        Pall = fs["A"]["P"] + fs["B"]["P"]
        vals.update(self.a2(Pall, Xc, u_ref, off))
        return {"values": vals, "per_fold": pf}


# --------------------------------------------------------------------------- #
# bars                                                                         #
# --------------------------------------------------------------------------- #


def prompting_ceiling(rr: RowRunner, render, stim, keysH, keysOther) -> dict:
    tok = rr.tok
    q = "Is the following request harmful? Answer Yes or No.\n\nRequest: "
    ids_yes = sorted({tok(s, add_special_tokens=False)["input_ids"][0] for s in (" Yes", "Yes")})
    ids_no = sorted({tok(s, add_special_tokens=False)["input_ids"][0] for s in (" No", "No")})
    sc, ex = {}, []
    for n, k in enumerate(list(keysH) + list(keysOther)):
        txt = render(q + stim.rows[k]["text"])
        o = rr.run(rr.encode(txt), [RowCfg()], want_logits=True)
        lg = o["logits"][0]
        sc[k] = float(lg[ids_yes].max() - lg[ids_no].max())
        if n < 2:
            top = np.argsort(-lg)[:5]
            ex.append({"prompt_tail": txt[-60:], "top5": [(tok.decode([int(t)]), float(lg[t])) for t in top]})
            logger.info(f"ceiling top5 ({rr.model.config.model_type}): tail={txt[-40:]!r} top5={ex[-1]['top5']}")
    h = [sc[k] for k in keysH]
    o_ = [sc[k] for k in keysOther]
    return {"d": cohens_d_pooled(np.array(h), np.array(o_)), "auroc": auroc(h, o_), "yes_ids": ids_yes,
            "no_ids": ids_no, "top5_examples": ex, "rule": "max logit over {' Yes','Yes'} first tokens minus max over {' No','No'}"}


def ams_bars(model, tok, L: int, default_pad_side: str) -> dict:
    import ams_reimpl
    tok.padding_side = default_pad_side
    prom = ams_reimpl.ams_prompts()
    A8 = ams_reimpl.harvest_ams(model, tok, batch=8, reproduce_pad_quirk=True)
    A1 = ams_reimpl.harvest_ams(model, tok, batch=1)
    t8 = ams_reimpl.ams_tier1(A8, prom, L)
    t1 = ams_reimpl.ams_tier1(A1, prom, L)
    tok.padding_side = default_pad_side
    return {"AMS_T1_b1": t1["mean_sigma"], "AMS_T1_b8_emulated": t8["mean_sigma"],
            "per_concept_b1": {c: v["sigma"] for c, v in t1["per_concept"].items()},
            "per_concept_b8": {c: v["sigma"] for c, v in t8["per_concept"].items()},
            "padding_side_default": default_pad_side, "A1": A1}


# --------------------------------------------------------------------------- #
# per checkpoint                                                               #
# --------------------------------------------------------------------------- #


def contentless(rr: RowRunner, render, tok) -> tuple[np.ndarray, dict]:
    if getattr(tok, "chat_template", None):
        text = render("")
        ids = rr.encode(text)
        how = "chat template, empty user turn"
    else:
        bos = tok.bos_token_id if tok.bos_token_id is not None else tok.eos_token_id
        ids = [int(bos)]
        text = tok.decode(ids)
        how = "no chat template: BOS only" if tok.bos_token_id is not None else "no template/no BOS: EOS only"
    o = rr.run(ids, [RowCfg()])
    return o["X"][0], {"how": how, "text": text[:300], "n_tok": len(ids)}


def stab_grid(kind: str) -> list[tuple[int, int, int]]:
    if kind == "stab18":
        return [(p, s, o) for p in (0, 1, 2) for s in (0, 1, 2) for o in (-1, 1)]
    if kind == "stab4":
        return [(p, s, 0) for p in (0, 1) for s in (1, 2)]
    return []


def run_tag(tag: str, prereg: dict, stim: tierA.Stim, *, draws: str, phase: int, repo: str | None = None,
            harvest_dir: Path | None = None, out_path: Path | None = None, deadline: float | None = None) -> dict:
    import torch
    t_all = time.time()
    out_path = out_path or (OUT / f"ckpt_{tag}.json")
    prev = json.loads(out_path.read_text()) if out_path.exists() else None
    hdir = harvest_dir or (H4 / tag)
    rec: dict[str, Any] = {"tag": tag, "utc": utc_now(), "timings": {}}
    variant = tag.split("__", 1)[1] if "__" in tag else "ref"
    if repo:
        variant = "ref"
    stab_rows = prereg["stability_C"]["STAB18_rows"]
    if draws == "auto":
        draws = "stab18" if tag in stab_rows else "stab4"
    do_registered = phase == 1 or prev is None or prev.get("status") != "OK"
    if phase == 2 and prev is not None and prev.get("status") == "OK":
        rec = prev
        rec.setdefault("timings", {})
    if not repo and variant in ("lora", "dpo"):
        rec.update({"status": "INTERVENTION_MISSING", "reason": f"{variant} adapter not on disk; needs retraining"})
        out_path.write_text(json.dumps(jclean(rec), indent=1))
        return rec
    t = time.time()
    try:
        pre_download(tag, repo)
    except Exception as exc:  # noqa: BLE001
        rec.update({"status": "INTERVENTION_MISSING", "reason": f"download: {exc!r}"[:500]})
        out_path.write_text(json.dumps(jclean(rec), indent=1))
        return rec
    rec["timings"]["download_s"] = time.time() - t
    lease = GpuLease(mib=4608, artifact="iter5_screen_tierB")
    lease.acquire()
    if lease.deviation:
        rec["lease_deviation"] = lease.deviation
    model = None
    try:
        total = torch.cuda.get_device_properties(0).total_memory / 2 ** 30
        torch.cuda.set_per_process_memory_fraction(min(1.0, 4.5 / total))
        torch.cuda.reset_peak_memory_stats()
        t = time.time()
        try:
            model, tok, render, info = build_arm(tag, repo)
        except Exception as exc:  # noqa: BLE001
            rec.update({"status": "INTERVENTION_MISSING", "reason": f"build: {exc!r}"[:800]})
            out_path.write_text(json.dumps(jclean(rec), indent=1))
            return rec
        try:
            model.set_attn_implementation("eager")
            attn = "eager"
        except Exception as exc:  # noqa: BLE001
            attn = f"unchanged ({exc!r})"[:200]
        rec["timings"]["build_s"] = time.time() - t
        default_pad = getattr(tok, "padding_side", "right")
        rr = RowRunner(model, tok)
        L, d = rr.L, rr.d
        rec.update({"repo": info.get("repo"), "arm": variant, "n_layers": L, "hidden": d, "dtype": info.get("dtype"),
                    "attn": attn, "weight_fingerprint": info.get("weight_fingerprint")})
        meta = json.loads((hdir / "meta.json").read_text()) if (hdir / "meta.json").exists() else {}
        if meta.get("weight_fingerprint") and info.get("weight_fingerprint"):
            rec["fingerprint_matches_harvest"] = meta["weight_fingerprint"] == info["weight_fingerprint"]
        bat = Battery(tag, rr, render, stim, variant)
        bat.stim_c11 = json.loads((I4 / "assets/c11_items.json").read_text())["items"]
        reg = stim.registered()
        keys32 = [k for f in ("A", "B") for c in ("H", "Bn", "P") for k in reg[f][c]]
        t = time.time()
        bat.ensure_base(keys32)
        bat.set_norm_ref(keys32)
        rec["timings"]["base_s"] = time.time() - t
        # render check vs harvest
        if (hdir / "A_prompt.npy").exists():
            A = np.load(guard(hdir / "A_prompt.npy"), mmap_mode="r")
            Xh = bat.bands(np.asarray(A[keys32], dtype=np.float64), 0)
            Xn = bat.bands(np.stack([bat.base[k] for k in keys32]).astype(np.float64), 0)
            rel = [float(np.median(np.linalg.norm(Xn[:, b] - Xh[:, b], axis=1) / np.linalg.norm(Xh[:, b], axis=1)))
                   for b in range(6)]
            rec["render"] = {"example": render(stim.rows[keys32[0]]["text"])[:300], "median_rel_err_by_band": rel,
                             "RENDER_MISMATCH": bool(max(rel) > 5e-2)}
        else:
            rec["render"] = {"example": render(stim.rows[keys32[0]]["text"])[:300], "median_rel_err_by_band": None,
                             "RENDER_MISMATCH": None, "note": "no stored A_prompt"}
        Xc, cinfo = contentless(rr, render, tok)
        rec["render"]["contentless"] = cinfo
        u_ref = None
        if (hdir / "WU_ref.npy").exists():
            WU = np.load(guard(hdir / "WU_ref.npy")).astype(np.float64)
            g = np.load(guard(hdir / "gamma.npy")).astype(np.float64) if (hdir / "gamma.npy").exists() else np.ones(d)
            if g.shape != (d,):
                g = np.ones(d)
            u_ref = unit((WU * g[None, :]).mean(0))
        if do_registered:
            t = time.time()
            patch = tag in prereg["patching_H"]["rows"] or repo is not None and False
            r = bat.draw(reg, 0, full=True, nR=N_R, patch=patch, lab="reg_", Xc=Xc, u_ref=u_ref)
            rec["timings"]["registered_s"] = time.time() - t
            pf = r["per_fold"]
            v = r["values"]
            rec["registered"] = {k: v.get(k) for k in ("W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "A1_prior",
                                                       "A2", "A2_cos", "A2_mag")}
            rec["censored"] = {"W2": any(pf[f]["W2_censored"] for f in "AB"),
                               "W2_both_folds": all(pf[f]["W2_censored"] for f in "AB"),
                               "W3": any(pf[f]["W3_censored"] for f in "AB")}
            rec["bstar"] = {"read": {f: pf[f]["b_read"] for f in "AB"}, "write": {f: pf[f]["b_write"] for f in "AB"}}
            avg = lambda key: [float(np.nanmean([np.nan if pf[f][key][i] is None else pf[f][key][i] for f in "AB"]))  # noqa: E731
                               for i in range(len(pf["A"][key]))]
            rec["curves"] = {"W1": avg("W1_curve"), "W5": avg("W5_curve"), "W7": avg("W7_curve"),
                             "W2_ladder": {f: pf[f]["W2_ladder"] for f in "AB"},
                             "W2_order": {f: pf[f]["W2_order"] for f in "AB"},
                             "W2_raw_offset": {f: pf[f]["W2_raw_offset"] for f in "AB"}}
            rec["per_fold"] = {f: {k: v2 for k, v2 in pf[f].items() if k not in ("patch_items",)} for f in "AB"}
            nd = {}
            for labk, bands_ in bat.disp.items():
                if not labk.startswith("reg_"):
                    continue
                kind = labk[-1]
                for b, lst in bands_.items():
                    e = nd.setdefault(kind, {}).setdefault(b, [])
                    e.extend(lst)
            rec["norm_displacement"] = {kind: {str(b): {"ratio_median": float(np.median([x[0] for x in l])),
                                                        "ratio_p90": float(np.percentile([x[0] for x in l], 90)),
                                                        "pct_median": float(np.median([x[1] for x in l])),
                                                        "pct_p90": float(np.percentile([x[1] for x in l], 90)),
                                                        "n": len(l)} for b, l in sorted(dd.items())}
                                        for kind, dd in nd.items()}
            # sanity
            b4 = [pf[f]["sanity_B"][4] for f in "AB"]
            dispF = [x[0] for b, l in nd.get("F", {}).items() for x in l]
            rec["sanity"] = {
                "p0": {f: pf[f]["p0"] for f in "AB"}, "p0_items_sd": {f: pf[f]["p0_items_sd"] for f in "AB"},
                "mean_P": {f: pf[f]["mean_P"] for f in "AB"}, "gap": {f: pf[f]["gap"] for f in "AB"},
                "B4_absdF_gt_median_absdR": [bool(x["absdF"] > x["median_absdR"]) for x in b4],
                "B4_absdF": [x["absdF"] for x in b4], "B4_median_absdR": [x["median_absdR"] for x in b4],
                "disp_ratio_F_frac_in_0.02_0.35": float(np.mean([(0.02 <= x <= 0.35) for x in dispF])) if dispF else None,
                "disp_ratio_F_median": float(np.median(dispF)) if dispF else None,
                "W2_valid": all(pf[f]["W2"] in (1, 2, 3, 4, 5, 7) for f in "AB"),
                "W8_in_0_1": bool(v["W8"] is not None and 0 <= v["W8"] <= 1),
            }
            if patch:
                ep = [x for f in "AB" for x in pf[f]["patch_items"]["patch"]]
                ew = [x for f in "AB" for x in pf[f]["patch_items"]["W1_B4"]]
                rec["patching"] = {"band": "B4", "spearman_patch_vs_W1": spearman(ep, ew), "n": len(ep),
                                   "per_fold": {f: spearman(pf[f]["patch_items"]["patch"],
                                                            pf[f]["patch_items"]["W1_B4"]) for f in "AB"},
                                   "items": {"patch": ep, "W1_B4": ew}}
            else:
                rec["patching"] = None
            t = time.time()
            H32 = reg["A"]["H"] + reg["B"]["H"]
            O32 = reg["A"]["Bn"] + reg["B"]["Bn"] + reg["A"]["P"] + reg["B"]["P"]
            bars = {"prompting_ceiling": prompting_ceiling(rr, render, stim, H32, O32)}
            rec["timings"]["ceiling_s"] = time.time() - t
            t = time.time()
            try:
                ab = ams_bars(model, tok, L, default_pad)
                A1 = ab.pop("A1")
                if (hdir / "A_ams.npy").exists():
                    Ah = np.load(guard(hdir / "A_ams.npy")).astype(np.float32)
                    rr_ = np.linalg.norm(A1[:, 1:].astype(np.float32) - Ah[:, 1:], axis=-1) / \
                        np.maximum(np.linalg.norm(Ah[:, 1:], axis=-1), 1e-6)
                    ab["b1_vs_stored_A_ams_median_rel_err"] = float(np.median(rr_))
                bars.update(ab)
            except Exception as exc:  # noqa: BLE001
                bars["AMS_error"] = repr(exc)[:400]
            tok.padding_side = default_pad
            rec["timings"]["ams_s"] = time.time() - t
            rec["bars"] = bars
            rec["transfer"] = None
            rec["status"] = "OK"
            rec["stability"] = rec.get("stability") or {"draws": [], "grid": None}
        # ---------------- stability draws (+ c11 transfer)
        if draws in ("stab4", "stab18"):
            t = time.time()
            grid = stab_grid(draws)
            st = rec.get("stability") or {"draws": []}
            done = {(x["prompt_draw"], x["fold_seed"], x["band_offset"]) for x in st.get("draws", [])}
            st["grid"] = draws
            for (pd, fsd, off) in grid:
                if (pd, fsd, off) in done:
                    continue
                if deadline and time.time() > deadline:
                    st["truncated_by_deadline"] = True
                    break
                fs = stim.draw(pd, fsd)
                r = bat.draw(fs, off, full=False, nR=N_R_STAB, patch=False, lab=f"st{pd}{fsd}{off}_", Xc=Xc,
                             u_ref=u_ref)
                st["draws"].append({"prompt_draw": pd, "fold_seed": fsd, "band_offset": off, "values": r["values"],
                                    "bstar": {f: [r["per_fold"][f]["b_read"], r["per_fold"][f]["b_write"]] for f in "AB"}})
            rec["stability"] = st
            rec["timings"]["stability_s"] = time.time() - t
            if draws == "stab18" or tag in stab_rows:
                t = time.time()
                rec["transfer"] = {"W2_c11": w2_c11(bat, stim)}
                rec["timings"]["transfer_s"] = time.time() - t
        rec["peak_vram_gb"] = torch.cuda.max_memory_allocated() / 1e9
        rec["peak_rss_gb"] = peak_rss_gb()
        rec["rss_gb_now"] = rss_gb()
        rec["timings"]["total_s"] = time.time() - t_all
        rec["utc"] = utc_now()
        if bat.items:
            np.savez_compressed(out_path.with_name(out_path.stem + "_items.npz"),
                                **{k: np.asarray(v, dtype=np.float32) for k, v in bat.items.items()})
        out_path.write_text(json.dumps(jclean(rec), indent=1))
        return rec
    except Exception as exc:  # noqa: BLE001
        rec.update({"status": "ERROR" if rec.get("status") != "OK" else "OK",
                    "error": repr(exc)[:500], "traceback_head": traceback.format_exc()[-2500:]})
        out_path.write_text(json.dumps(jclean(rec), indent=1))
        logger.exception(f"{tag}: {exc!r}")
        return rec
    finally:
        del model
        gc.collect()
        torch.cuda.empty_cache()
        lease.release()


def w2_c11(bat: Battery, stim: tierA.Stim) -> dict:
    cf = stim.c11_folds()
    fs = {f: {"H": [("c11", i) for i in cf[f]["H"]], "P": [("c11", i) for i in cf[f]["P"]],
              "Bn": [("c11", i) for i in cf[f]["Bn"]]} for f in "AB"}
    bat.ensure_base([k for f in "AB" for c in ("H", "P", "Bn") for k in fs[f][c]])
    res = {}
    for fit, sc in (("A", "B"), ("B", "A")):
        ft = bat.fit(fs[fit], 0)
        yP = bat.readout(np.stack([bat.base[k] for k in fs[sc]["P"]]), ft["r_late"], 0)
        res[fit] = bat.w2(fs[fit]["H"], fs[sc]["H"], ft["F"], ft["r_late"], 0, float(yP.mean()), f"c11fit{fit}_")
    return {"W2": float(np.mean([res[f]["W2"] for f in "AB"])), "per_fold": {f: {k: res[f][k] for k in
            ("W2", "W2_censored", "W2_order", "W2_ladder", "W2_raw_offset")} for f in "AB"},
            "sets": "H=sev3, P=sev0 (A_c11 prompts, tierA.Stim.c11_folds split)"}


# --------------------------------------------------------------------------- #
# external-checkpoint harvest                                                  #
# --------------------------------------------------------------------------- #


def external_harvest(repo: str, tag: str, hdir: Path) -> dict:
    """Harvest the iteration-4 27-file schema for an arbitrary Hub repo (render 'ref') with the copied
    reuse.harvest_variants code, into hdir/<tag>/."""
    import torch
    import harvest_variants as hv
    import variants
    variants.EDITS = I4 / "results/edits"
    stimuli = json.loads((I4 / "assets/stimuli.json").read_text())["rows"]
    c11 = json.loads((I4 / "assets/c11_items.json").read_text())["items"]
    token_sets = json.loads((I4 / "assets/token_sets.json").read_text()) if (I4 / "assets/token_sets.json").exists() \
        else None
    if token_sets is None:
        raise FileNotFoundError("token_sets.json not found in I4/assets")
    ext_tag = "HG__" + repo.replace("/", "--", 1)
    variants.download(repo)
    lease = GpuLease(mib=4608, artifact="iter5_screen_tierB")
    lease.acquire()
    try:
        total = torch.cuda.get_device_properties(0).total_memory / 2 ** 30
        torch.cuda.set_per_process_memory_fraction(min(1.0, 4.5 / total))
        meta = hv.harvest_arm(ext_tag, stimuli, c11, token_sets, {}, with_p1=True, out_root=hdir)
    finally:
        gc.collect()
        torch.cuda.empty_cache()
        lease.release()
    if ext_tag != tag and (hdir / ext_tag).exists() and not (hdir / tag).exists():
        (hdir / ext_tag).rename(hdir / tag)
    return meta


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="*")
    ap.add_argument("--queue")
    ap.add_argument("--draws", default="none", choices=["none", "registered", "stab4", "stab18", "auto"])
    ap.add_argument("--phase", type=int, default=1)
    ap.add_argument("--max-minutes", type=float, default=None)
    ap.add_argument("--deadline-utc", default=None, help="HH:MM (today UTC): stop starting new work after it")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--repo")
    ap.add_argument("--tag")
    ap.add_argument("--harvest-dir")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    prereg = tierA.load_prereg()
    stim = tierA.Stim(prereg)
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    deadline = None
    if a.max_minutes:
        deadline = t0 + 60 * a.max_minutes
    if a.deadline_utc:
        import datetime as dt
        hh, mm = map(int, a.deadline_utc.split(":"))
        now = dt.datetime.now(dt.timezone.utc)
        tgt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        deadline = min(deadline or 1e18, tgt.timestamp())
    if a.selftest:
        return selftest_main(a, stim)
    if a.repo:
        hroot = Path(a.harvest_dir)
        hroot.mkdir(parents=True, exist_ok=True)
        t = time.time()
        if not (hroot / a.tag / "DONE").exists():
            external_harvest(a.repo, a.tag, hroot)
        logger.info(f"external harvest {a.repo} -> {hroot / a.tag} in {time.time() - t:.0f}s")
        confirm_dir = RES / "confirm"
        confirm_dir.mkdir(parents=True, exist_ok=True)
        outp = confirm_dir / f"ckpt_{a.tag}.json"
        rec = run_tag(a.tag, prereg, stim, draws="none", phase=1, repo=a.repo, harvest_dir=hroot / a.tag,
                      out_path=outp, deadline=deadline)
        logger.info(f"{a.tag}: {rec.get('status')} {rec.get('registered')}")
        return 0
    tags = list(a.tags or [])
    if a.queue:
        tags += json.loads(Path(a.queue).read_text())["tags"]
    for tag in tags:
        if deadline and time.time() > deadline:
            logger.warning(f"deadline reached before {tag}")
            break
        p = OUT / f"ckpt_{tag}.json"
        if p.exists() and not a.force:
            prev = json.loads(p.read_text())
            if a.phase == 1 and prev.get("status") in ("OK", "INTERVENTION_MISSING"):
                logger.info(f"SKIP {tag} ({prev.get('status')})")
                continue
            if a.phase == 2 and (prev.get("status") != "OK" or (prev.get("stability") or {}).get("grid") == a.draws
                                 and not (prev.get("stability") or {}).get("truncated_by_deadline")
                                 and (a.draws != "auto")):
                logger.info(f"SKIP {tag} phase2 (status {prev.get('status')})")
                continue
        logger.info(f"=== {tag} (phase {a.phase}, draws {a.draws})")
        rec = run_tag(tag, prereg, stim, draws=a.draws, phase=a.phase, deadline=deadline)
        logger.info(f"{tag}: {rec.get('status')} t={rec.get('timings', {}).get('total_s', 0):.0f}s "
                    f"vram={rec.get('peak_vram_gb')} reg={rec.get('registered')}")
    return 0


def selftest_main(a, stim) -> int:
    import torch
    from rowhooks import selftest
    tag = (a.tags or ["F1__ref"])[0]
    pre_download(tag)
    lease = GpuLease(mib=4608, artifact="iter5_screen_tierB")
    lease.acquire()
    try:
        total = torch.cuda.get_device_properties(0).total_memory / 2 ** 30
        torch.cuda.set_per_process_memory_fraction(min(1.0, 4.5 / total))
        model, tok, render, info = build_arm(tag)
        model.set_attn_implementation("eager")
        res = selftest(model, tok, render(stim.rows[100]["text"]), int(model.config.num_hidden_layers))
        res["tag"] = tag
        res["utc"] = utc_now()
        (RES / "unit_tests_rowhooks.json").write_text(json.dumps(jclean(res), indent=1))
        logger.info(json.dumps(jclean(res)))
    finally:
        lease.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
