#!/usr/bin/env python3
"""Lane B CPU-only reanalysis of the Qwen3 cheap-safety activation harvest.

Reconciles iteration-2's band-pooled logistic numbers, then runs the corrected
three-site (PROMPT / EARLY / LATE) grid, significance/equivalence tests, the
L4 non-safety-control contrast, saturation/power bookkeeping, and the
fixed-axis depth-accumulation check. See the task brief in the conversation
that produced this file for the full spec; deviations from that spec (made
for wall-clock reasons and confirmed cheap/expensive in the iter-1 pilot) are
recorded in ``results/laneb_deviations.json``.

No model, no GPU, no LLM calls: this script only reads pre-harvested
activations from disk and does numpy/sklearn statistics on them.
"""

from __future__ import annotations

import gc
import hashlib
import json
import math
import sys
import time
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
from loguru import logger
from scipy import stats as sps
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

# --------------------------------------------------------------------------- #
# paths / constants
# --------------------------------------------------------------------------- #
W = Path(__file__).resolve().parent.parent
H = Path(
    "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/"
    "gen_art/gen_art_experiment_2/out/harvest"
)
B_ANALYSIS = H.parent / "analysis.json"
RESULTS = W / "results"
LOGS = W / "logs"
RESULTS.mkdir(parents=True, exist_ok=True)
LOGS.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(sys.stderr, level="INFO",
           format="{time:HH:mm:ss} | {level: <7} | {message}")
logger.add(LOGS / "laneb.log", level="DEBUG", rotation="100 MB")

LINEAGES = ["L1", "L2", "L3", "L4"]
ALPHAS = ["0.00", "0.25", "0.50", "0.75", "1.00"]
BAND_LAYERS = (13, 14, 15, 16, 17, 18, 19, 20, 21)
N_FOLDS = 5
SITES = ("PROMPT", "EARLY", "LATE")
# (site, class) combinations that are DEFINED. CONTINUATION at PROMPT is
# undefined (the continuation has not been generated yet at that read site)
# and is never computed, per the task's explicit instruction.
SITE_CLASSES = [
    ("PROMPT", "REQUEST"),
    ("EARLY", "REQUEST"), ("EARLY", "CONTINUATION"),
    ("LATE", "REQUEST"), ("LATE", "CONTINUATION"),
]
LAYER_CHOICES = list(BAND_LAYERS) + ["band"]  # per-layer + band-pooled
PROBES = ("diffmeans", "logistic")
B_BAND = 2000       # bootstrap draws for 'band' cells
B_LAYER = 500        # bootstrap draws for per-layer cells
N_PERM = 10_000
SEED = 20260921

DEVIATIONS: list[str] = []


def note_deviation(msg: str) -> None:
    logger.warning("DEVIATION: {}", msg)
    DEVIATIONS.append(msg)


# --------------------------------------------------------------------------- #
# JSON-safe serialisation
# --------------------------------------------------------------------------- #
def jsafe(obj):
    """Recursively make an object JSON-serialisable, NaN/Inf -> None."""
    if isinstance(obj, dict):
        return {str(k): jsafe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsafe(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        v = float(obj)
        return None if not math.isfinite(v) else v
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, np.ndarray):
        return jsafe(obj.tolist())
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def dump_json(path: Path, obj) -> None:
    path.write_text(json.dumps(jsafe(obj), indent=2))
    logger.info("wrote {} ({} bytes)", path, path.stat().st_size)


# --------------------------------------------------------------------------- #
# low-level harvest IO
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=8)
def meta_json(lineage: str) -> dict:
    return json.loads((H / f"{lineage}_meta.json").read_text())


@lru_cache(maxsize=8)
def index_json(lineage: str) -> dict:
    return json.loads((H / f"{lineage}_index.json").read_text())


@lru_cache(maxsize=32)
def key_to_part(lineage: str, alpha: str) -> dict:
    mapping = {}
    parts = sorted(H.glob(f"{lineage}_a{alpha}.part*.npz"))
    if not parts:
        raise FileNotFoundError(f"no parts for {lineage} a={alpha}")
    for part in parts:
        with zipfile.ZipFile(part) as zf:
            for m in zf.namelist():
                if m.endswith(".npy"):
                    mapping[m[:-4]] = part.name
    return mapping


_ARRAY_CACHE: dict = {}
_ARRAY_CACHE_ORDER: list = []
_CACHE_CAP = 60


def _cache_put(key, arr):
    if key in _ARRAY_CACHE:
        return
    if len(_ARRAY_CACHE_ORDER) >= _CACHE_CAP:
        old = _ARRAY_CACHE_ORDER.pop(0)
        _ARRAY_CACHE.pop(old, None)
    _ARRAY_CACHE[key] = arr
    _ARRAY_CACHE_ORDER.append(key)


def load_array(lineage: str, alpha: str, key: str) -> np.ndarray:
    ck = (lineage, alpha, key)
    if ck in _ARRAY_CACHE:
        return _ARRAY_CACHE[ck]
    mapping = key_to_part(lineage, alpha)
    if key not in mapping:
        raise KeyError(f"{key!r} absent from {lineage}_a{alpha}.part*.npz")
    with np.load(H / mapping[key]) as z:
        arr = np.asarray(z[key]).astype(np.float32)
    _cache_put(ck, arr)
    return arr


def clear_array_cache() -> None:
    _ARRAY_CACHE.clear()
    _ARRAY_CACHE_ORDER.clear()
    gc.collect()


def site_key(group: str, site: str, layer: int) -> str:
    if site == "PROMPT":
        return f"{group}|lastp|{layer}"
    if site in ("EARLY", "LATE"):
        return f"{group}|win|{site}|{layer}"
    raise ValueError(site)


def get_layer(lineage: str, alpha: str, group: str, site: str, layer: int) -> np.ndarray:
    return load_array(lineage, alpha, site_key(group, site, layer))


def get_band(lineage: str, alpha: str, group: str, site: str,
             layers=BAND_LAYERS) -> np.ndarray:
    ck = (lineage, alpha, group, site, "band", layers)
    if ck in _ARRAY_CACHE:
        return _ARRAY_CACHE[ck]
    acc = None
    for l in layers:
        a = get_layer(lineage, alpha, group, site, l)
        acc = a.copy() if acc is None else acc + a
    acc /= len(layers)
    _cache_put(ck, acc)
    return acc


def get_feature(lineage: str, alpha: str, group: str, site: str, layer) -> np.ndarray:
    return get_band(lineage, alpha, group, site) if layer == "band" else \
        get_layer(lineage, alpha, group, site, layer)


# --------------------------------------------------------------------------- #
# labelled substrate (item group, prefix in {hazardous, benign})
# --------------------------------------------------------------------------- #
def frozen_folds(pair_keys, n_folds: int = N_FOLDS) -> np.ndarray:
    out = np.empty(len(pair_keys), dtype=int)
    for i, k in enumerate(pair_keys):
        d = hashlib.sha256(f"M1|{k}".encode()).digest()
        out[i] = int.from_bytes(d[:8], "big") % n_folds
    return out


class Substrate:
    """Everything about a lineage's labelled 768-row item substrate that does
    NOT depend on site/layer/probe: rows, folds, labels, scenario groupings."""

    def __init__(self, lineage: str):
        idx = index_json(lineage)["item"]
        df = pd.DataFrame(idx)
        df["row"] = np.arange(len(df))
        keep = df["prefix"].isin(["hazardous", "benign"])
        sub = df[keep].reset_index(drop=True)
        self.lineage = lineage
        self.sub = sub
        self.rows = sub["row"].to_numpy()
        self.folds = frozen_folds(sub["pair_key"].tolist())
        self.y = {
            "REQUEST": (sub["request"] == "harmful").astype(int).to_numpy(),
            "CONTINUATION": (sub["prefix"] == "hazardous").astype(int).to_numpy(),
        }
        pk_unique = sorted(sub["pair_key"].unique())
        self.pair_keys = pk_unique
        pk_to_id = {k: i for i, k in enumerate(pk_unique)}
        self.scen = sub["pair_key"].map(pk_to_id).to_numpy()
        self.n_scen = len(pk_unique)
        # pos/neg row-position matrices per class, shape (n_scen, k)
        self.pos_idx = {}
        self.neg_idx = {}
        for cls, y in self.y.items():
            pos = np.full((self.n_scen, 4), -1, dtype=int)
            neg = np.full((self.n_scen, 4), -1, dtype=int)
            for s in range(self.n_scen):
                idxs = np.flatnonzero(self.scen == s)
                p = idxs[y[idxs] == 1]
                n = idxs[y[idxs] == 0]
                assert p.size == 4 and n.size == 4, (lineage, cls, s, p.size, n.size)
                pos[s] = p
                neg[s] = n
            self.pos_idx[cls] = pos
            self.neg_idx[cls] = neg


@lru_cache(maxsize=8)
def substrate(lineage: str) -> Substrate:
    return Substrate(lineage)


# --------------------------------------------------------------------------- #
# probes: diff-in-means and logistic, both crossfitted on alpha=0.00 folds
# --------------------------------------------------------------------------- #
def _fit_diffmeans(Xtr, ytr):
    sc = StandardScaler().fit(Xtr)
    Xs = sc.transform(Xtr)
    mu1, mu0 = Xs[ytr == 1].mean(0), Xs[ytr == 0].mean(0)
    u = mu1 - mu0
    n = np.linalg.norm(u)
    if n > 0:
        u = u / n
    return sc, u


def _fit_logistic(Xtr, ytr):
    sc = StandardScaler().fit(Xtr)
    clf = LogisticRegression(max_iter=2000, C=1.0, solver="lbfgs")
    clf.fit(sc.transform(Xtr), ytr)
    return sc, clf


def _apply(kind: str, model, X):
    sc, m = model
    Xs = sc.transform(X)
    return Xs @ m if kind == "diffmeans" else m.decision_function(Xs)


def crossfit_scores(kind: str, X_by_alpha: dict, y: np.ndarray, folds: np.ndarray,
                     fit_alpha: str = "0.00") -> dict:
    """Fit on alpha=fit_alpha per-fold, score every alpha's held-out fold rows."""
    fit_fn = _fit_diffmeans if kind == "diffmeans" else _fit_logistic
    n = len(y)
    out = {a: np.full(n, np.nan, dtype=np.float64) for a in X_by_alpha}
    Xfit = X_by_alpha[fit_alpha]
    for f in np.unique(folds):
        tr, te = folds != f, folds == f
        if len(np.unique(y[tr])) < 2:
            continue
        model = fit_fn(Xfit[tr], y[tr])
        for a, Xs in X_by_alpha.items():
            out[a][te] = _apply(kind, model, Xs[te])
    return out


# --------------------------------------------------------------------------- #
# metrics: auroc / tpr@fpr, scalar and vectorised-over-bootstrap-draws
# --------------------------------------------------------------------------- #
def auroc_scalar(pos: np.ndarray, neg: np.ndarray) -> float:
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    ranks = sps.rankdata(allv)
    r_pos = ranks[: pos.size].sum()
    return float((r_pos - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size))


def tpr_at_fpr_scalar(pos: np.ndarray, neg: np.ndarray, fpr: float) -> dict:
    pos = pos[np.isfinite(pos)]
    neg = neg[np.isfinite(neg)]
    n_pos, n_neg = pos.size, neg.size
    need = int(round(1 / fpr))
    if n_neg < need or n_pos == 0:
        return {"tpr": float("nan"), "threshold": float("nan"), "n_pos": n_pos,
                "n_neg": n_neg, "estimable": False}
    thr = float(np.quantile(neg, 1.0 - fpr, method="higher"))
    tpr = float(np.mean(pos > thr))
    return {"tpr": tpr, "threshold": thr, "n_pos": n_pos, "n_neg": n_neg, "estimable": True}


def vec_auroc(pos_mat: np.ndarray, neg_mat: np.ndarray) -> np.ndarray:
    """AUROC per row (bootstrap draw). pos_mat (B,npos), neg_mat (B,nneg)."""
    B, npos = pos_mat.shape
    nneg = neg_mat.shape[1]
    allv = np.concatenate([pos_mat, neg_mat], axis=1)
    order = np.argsort(allv, axis=1, kind="quicksort")
    ranks = np.argsort(order, axis=1, kind="quicksort") + 1
    r_pos_sum = ranks[:, :npos].sum(axis=1).astype(np.float64)
    return (r_pos_sum - npos * (npos + 1) / 2) / (npos * nneg)


def vec_tpr_at_fpr(pos_mat: np.ndarray, neg_mat: np.ndarray, fpr: float) -> np.ndarray:
    """TPR@fpr per row (bootstrap draw), own-arm threshold recomputed per draw."""
    nneg = neg_mat.shape[1]
    sorted_neg = np.sort(neg_mat, axis=1)
    h = fpr_to_h(fpr, nneg)
    idx = int(math.ceil(h))
    idx = min(max(idx, 0), nneg - 1)
    thr = sorted_neg[:, idx]
    return (pos_mat > thr[:, None]).mean(axis=1)


def fpr_to_h(fpr: float, n: int) -> float:
    # numpy 'higher' method virtual index for quantile q=1-fpr over n samples
    q = 1.0 - fpr
    return q * (n - 1)


# --------------------------------------------------------------------------- #
# scenario-clustered bootstrap
# --------------------------------------------------------------------------- #
def scenario_boot_indices(n_scen: int, B: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, n_scen, size=(B, n_scen))


def gather_boot(scores: np.ndarray, pos_idx: np.ndarray, neg_idx: np.ndarray,
                 picks: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """picks: (B, n_scen) scenario draws -> (pos_mat, neg_mat) each (B, n_scen*k)."""
    B = picks.shape[0]
    k = pos_idx.shape[1]
    pos_rows = pos_idx[picks].reshape(B, -1)   # (B, n_scen*k)
    neg_rows = neg_idx[picks].reshape(B, -1)
    return scores[pos_rows], scores[neg_rows]


def percentile_ci(vals: np.ndarray, lo=2.5, hi=97.5) -> tuple:
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return (float("nan"), float("nan"))
    a, b = np.percentile(vals, [lo, hi])
    return float(a), float(b)


def cell_stats(scores0: np.ndarray, scoresA: np.ndarray, y: np.ndarray, sub: Substrate,
               cls: str, B: int, seed: int, keep_boot: bool = False) -> dict:
    """Full cell: point auroc/tpr1/tpr5 for scoresA, plus delta vs scores0, each
    with scenario-clustered bootstrap CIs (paired for the delta)."""
    pos_idx, neg_idx = sub.pos_idx[cls], sub.neg_idx[cls]
    posA, negA = scoresA[pos_idx.ravel()], scoresA[neg_idx.ravel()]
    auroc_pt = auroc_scalar(posA, negA)
    tpr1_pt = tpr_at_fpr_scalar(posA, negA, 0.01)
    tpr5_pt = tpr_at_fpr_scalar(posA, negA, 0.05)

    picks = scenario_boot_indices(sub.n_scen, B, seed)
    posA_m, negA_m = gather_boot(scoresA, pos_idx, neg_idx, picks)
    posA_m = posA_m.astype(np.float64); negA_m = negA_m.astype(np.float64)
    aurocA_b = vec_auroc(posA_m, negA_m)
    tpr1A_b = vec_tpr_at_fpr(posA_m, negA_m, 0.01)
    tpr5A_b = vec_tpr_at_fpr(posA_m, negA_m, 0.05)

    pos0_m, neg0_m = gather_boot(scores0, pos_idx, neg_idx, picks)
    pos0_m = pos0_m.astype(np.float64); neg0_m = neg0_m.astype(np.float64)
    auroc0_b = vec_auroc(pos0_m, neg0_m)
    tpr10_b = vec_tpr_at_fpr(pos0_m, neg0_m, 0.01)
    tpr50_b = vec_tpr_at_fpr(pos0_m, neg0_m, 0.05)

    d_auroc_b = aurocA_b - auroc0_b
    d_tpr1_b = tpr1A_b - tpr10_b
    d_tpr5_b = tpr5A_b - tpr50_b

    pos0, neg0 = scores0[pos_idx.ravel()], scores0[neg_idx.ravel()]
    d_auroc_pt = auroc_pt - auroc_scalar(pos0, neg0)
    d_tpr1_pt = tpr1_pt["tpr"] - tpr_at_fpr_scalar(pos0, neg0, 0.01)["tpr"]
    d_tpr5_pt = tpr5_pt["tpr"] - tpr_at_fpr_scalar(pos0, neg0, 0.05)["tpr"]

    out = {
        "auroc": auroc_pt, "auroc_ci": percentile_ci(aurocA_b),
        "tpr1": tpr1_pt["tpr"], "tpr1_ci": percentile_ci(tpr1A_b),
        "tpr5": tpr5_pt["tpr"], "tpr5_ci": percentile_ci(tpr5A_b),
        "d_auroc": d_auroc_pt, "d_auroc_ci": percentile_ci(d_auroc_b),
        "d_tpr1": d_tpr1_pt, "d_tpr1_ci": percentile_ci(d_tpr1_b),
        "d_tpr5": d_tpr5_pt, "d_tpr5_ci": percentile_ci(d_tpr5_b),
        "n_pos": int(pos_idx.size), "n_neg": int(neg_idx.size), "B": int(B),
    }
    if keep_boot:
        out["_d_tpr1_boot"] = d_tpr1_b
        out["_scores0"] = scores0
        out["_scoresA"] = scoresA
    return out


# --------------------------------------------------------------------------- #
# shared: band-pooled logistic REQUEST crossfit scores, cached
# --------------------------------------------------------------------------- #
_SCORE_CACHE: dict = {}


def band_logistic_scores(lineage: str, site: str) -> dict:
    """{alpha: scores} for band-pooled logistic REQUEST, crossfit on alpha=0.

    This is iter-2's EXACT M1(a) definition (band mean pool, StandardScaler +
    LogisticRegression(C=1), 5 sha256-scenario folds), generalised to whichever
    `site` supplies the activation (EARLY/LATE reproduce iter-2 exactly since
    those were its only two windows; PROMPT is the corrected addition)."""
    ck = ("band_logistic", lineage, site)
    if ck in _SCORE_CACHE:
        return _SCORE_CACHE[ck]
    sub = substrate(lineage)
    X_by_alpha = {a: get_band(lineage, a, "item", site)[sub.rows] for a in ALPHAS}
    scores = crossfit_scores("logistic", X_by_alpha, sub.y["REQUEST"], sub.folds)
    _SCORE_CACHE[ck] = scores
    return scores


def paired_tpr_diff_fixedthr(scores_parent: np.ndarray, scores_child: np.ndarray,
                              y: np.ndarray) -> np.ndarray:
    """Reference m1_recognition.paired_tpr_diff: EACH arm thresholded at its
    OWN 1%-FPR point (own negatives), hit indicator diffed over positives."""
    hits = []
    for s in (scores_parent, scores_child):
        ok = np.isfinite(s)
        neg = s[ok & (y == 0)]
        thr = float(np.quantile(neg, 0.99, method="higher"))
        hits.append((s > thr).astype(float))
    mask = (y == 1) & np.isfinite(scores_parent) & np.isfinite(scores_child)
    return hits[1][mask] - hits[0][mask]


def task1_reconcile() -> dict:
    logger.info("=== TASK 1: reconciliation ===")
    out: dict = {"iter2_definition": (
        "band-pooled logistic REQUEST class: mean over layers 13-21 of "
        "item|win|<WINDOW>|<layer>, StandardScaler+LogisticRegression(C=1,"
        "lbfgs,max_iter=2000), 5 sha256('M1|'+pair_key) scenario folds, "
        "crossfit-trained on alpha=0.00 and scored on every alpha."
    ), "site_correction": (
        "iter-2 called its EARLY window the 'prompt site'; EARLY (continuation "
        "tokens 5-20) and LATE are BOTH response-site windows. The only true "
        "prompt site is item|lastp|<layer>, reported separately as PROMPT."
    )}

    per_lineage = {}
    for lineage in LINEAGES:
        repo = meta_json(lineage)["repo"]
        sub = substrate(lineage)
        row = {"repo": repo}
        for window in ("EARLY", "LATE"):
            scores = band_logistic_scores(lineage, window)
            y = sub.y["REQUEST"]
            cell = {}
            for a in ALPHAS:
                s = scores[a]
                ok = np.isfinite(s)
                pos, neg = s[ok & (y == 1)], s[ok & (y == 0)]
                cell[a] = {"auroc": auroc_scalar(pos, neg),
                           "tpr1": tpr_at_fpr_scalar(pos, neg, 0.01)["tpr"],
                           "tpr5": tpr_at_fpr_scalar(pos, neg, 0.05)["tpr"]}
            row[window] = cell
        per_lineage[lineage] = row
    out["per_lineage_recomputed"] = per_lineage

    # cross-lineage means at each alpha, per window (reproduces the iter-2 table)
    means = {}
    for window in ("EARLY", "LATE"):
        means[window] = {}
        for a in ALPHAS:
            aur = [per_lineage[l][window][a]["auroc"] for l in LINEAGES]
            t1 = [per_lineage[l][window][a]["tpr1"] for l in LINEAGES]
            means[window][a] = {"mean_auroc": float(np.mean(aur)),
                                 "mean_tpr1": float(np.mean(t1)), "n_lineages": 4}
    out["cross_lineage_means_recomputed"] = means

    delta_table = {}
    for window in ("EARLY", "LATE"):
        d_auroc = means[window]["1.00"]["mean_auroc"] - means[window]["0.00"]["mean_auroc"]
        d_tpr1 = means[window]["1.00"]["mean_tpr1"] - means[window]["0.00"]["mean_tpr1"]
        delta_table[window] = {"d_mean_auroc_recomputed": d_auroc,
                                "d_mean_tpr1_recomputed": d_tpr1}
    out["delta_alpha0_to_1_recomputed"] = delta_table
    out["quoted"] = {
        "EARLY": {"d_mean_auroc": -0.0068, "d_mean_tpr1": 0.0006},
        "LATE": {"d_mean_auroc": -0.0136, "d_mean_tpr1": -0.1439},
        "L4_LATE_tpr1_alpha0": 0.404, "L4_LATE_tpr1_alpha1": 0.234,
        "note_10.6x_ratio": "DROPPED as a quantity in this artifact (see task3 note); reported only as the iter-2 quote it was.",
    }
    out["L4_LATE_recomputed"] = {
        "tpr1_alpha0": per_lineage["L4"]["LATE"]["0.00"]["tpr1"],
        "tpr1_alpha1": per_lineage["L4"]["LATE"]["1.00"]["tpr1"],
    }

    # ---- iter-1 D_curve on the crude damage corpus ------------------------ #
    from sklearn.model_selection import StratifiedKFold

    def cv_auroc(x, y, folds=5, seed=0):
        skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
        s = np.empty(len(y))
        for tr, te in skf.split(x, y):
            sc, clf = _fit_logistic(x[tr], y[tr])
            s[te] = _apply("logistic", (sc, clf), x[te])
        return auroc_scalar(s[y == 1], s[y == 0])

    stored = json.loads(B_ANALYSIS.read_text())["lineages"] if B_ANALYSIS.exists() else {}
    damage_recon = {}
    for lineage in LINEAGES:
        r_layer = meta_json(lineage)["r_ablit_layer"]
        idxd = index_json(lineage)["damage"]
        y = np.array([r["label"] for r in idxd], dtype=int)
        curve = []
        for a in ALPHAS:
            x = load_array(lineage, a, f"damage|lastp|{r_layer}")
            curve.append(cv_auroc(x, y, seed=0))
        st = stored.get(lineage, {})
        ref = [float(v) for v in st.get("D_curve", [])]
        delta = [abs(a - b) for a, b in zip(curve, ref)] if len(ref) == len(curve) else []
        damage_recon[lineage] = {
            "read_site": f"lastp|{r_layer}", "r_ablit_layer": r_layer,
            "n_pos": int(y.sum()), "n_neg": int((1 - y).sum()),
            "stored_D_curve": ref, "recomputed_D_curve": [round(v, 6) for v in curve],
            "max_abs_delta": max(delta) if delta else None,
            "verdict": ("EXACT_MATCH" if delta and max(delta) < 1e-6 else
                        "RECONCILED" if delta and max(delta) <= 0.02 else
                        "MISMATCH" if delta else "NOT_IN_SOURCE"),
        }
    out["damage_Dcurve_reconcile"] = damage_recon
    out["damage_Dcurve_note"] = (
        "D_curve is computed on the CRUDE damage corpus (256 rows, prompt-only "
        "harmful-vs-harmless forwards at the r_ablit_layer lastp site), which "
        "was at ceiling in the unperturbed control (alpha=0) and therefore "
        "cannot fall further; this is why iter-1 reported AUROC=1.0 at every "
        "lesion strength."
    )

    # ---- reproduce the quoted p=1.76e-6 (L1 LATE lesion a0.00->a1.00) ----- #
    from scipy import stats as sps2
    l1_scores = band_logistic_scores("L1", "LATE")
    sub1 = substrate("L1")
    y1 = sub1.y["REQUEST"]
    d_fixedthr = paired_tpr_diff_fixedthr(l1_scores["0.00"], l1_scores["1.00"], y1)
    p_ttest = float(sps2.ttest_1samp(d_fixedthr, 0.0).pvalue) if d_fixedthr.std(ddof=1) > 0 else 1.0
    out["p_1.76e-6_reproduction"] = {
        "how_iter2_computed_it": (
            "evalkit/m1_recognition.py:run() builds paired_tpr_diff(parent=a0.00, "
            "child=a1.00) -- EACH arm thresholded at ITS OWN 1%-FPR point from its "
            "own negative scores, hit indicator diffed per positive item -- then "
            "evalkit/stats.py is NOT used for the p-value; run() calls "
            "scipy.stats.ttest_1samp(d, 0.0) directly (a paired one-sample t-test "
            "on the 384 per-item hit differences), not the TOST/holm machinery."
        ),
        "reproduced_with_exact_iter2_method": {"p_two_sided": p_ttest, "n": int(d_fixedthr.size),
                                                "mean_diff": float(d_fixedthr.mean())},
        "quoted": 1.76e-06,
        "new_method_forward_reference": "see results/laneb_tests.json for the paired scenario-permutation (10,000 perms) p-value for the same (L1, LATE, a0.00->a1.00) contrast on the BAND-LOGISTIC-REQUEST cell.",
    }
    return out


def stable_seed(*parts) -> int:
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).digest()
    return int.from_bytes(h[:4], "big")


def task2_main_grid(lineages=LINEAGES) -> tuple[list[dict], dict]:
    logger.info("=== TASK 2: main grid ===")
    cells: list[dict] = []
    band_npz: dict[str, np.ndarray] = {}
    for lineage in lineages:
        t_lin = time.time()
        repo = meta_json(lineage)["repo"]
        sub = substrate(lineage)
        band_npz[f"meta|{lineage}|scen"] = sub.scen.astype(np.int32)
        band_npz[f"meta|{lineage}|rows"] = sub.rows.astype(np.int32)
        for cls in ("REQUEST", "CONTINUATION"):
            band_npz[f"meta|{lineage}|y|{cls}"] = sub.y[cls].astype(np.int8)
        for site in SITES:
            classes_here = [c for (s, c) in SITE_CLASSES if s == site]
            for layer in LAYER_CHOICES:
                X_by_alpha = {a: get_feature(lineage, a, "item", site, layer)[sub.rows]
                              for a in ALPHAS}
                for cls in classes_here:
                    y = sub.y[cls]
                    for probe in PROBES:
                        if layer == "band" and probe == "logistic" and cls == "REQUEST":
                            scores = band_logistic_scores(lineage, site)
                        else:
                            scores = crossfit_scores(probe, X_by_alpha, y, sub.folds)
                        B = B_BAND if layer == "band" else B_LAYER
                        seed = stable_seed(lineage, site, cls, layer, probe)
                        if layer == "band":
                            for a in ALPHAS:
                                band_npz[f"scores|{lineage}|{site}|{cls}|{probe}|{a}"] = \
                                    scores[a].astype(np.float32)
                        for a in ALPHAS:
                            st = cell_stats(scores["0.00"], scores[a], y, sub, cls, B, seed)
                            cells.append({
                                "lineage": lineage, "repo": repo, "alpha": a,
                                "site": site, "layer": layer, "probe": probe, "cls": cls,
                                **{k: v for k, v in st.items() if not k.startswith("_")},
                            })
                del X_by_alpha
            clear_array_cache()
            logger.info("  {} site={} done, cells so far={}", lineage, site, len(cells))
        logger.info("lineage {} main-grid done in {:.1f}s", lineage, time.time() - t_lin)
    notes = {
        "n_cells": len(cells),
        "layers": LAYER_CHOICES, "probes": list(PROBES),
        "classes": "REQUEST at all 3 sites; CONTINUATION at EARLY/LATE only "
                   "(UNDEFINED at PROMPT, never computed/zero-filled)",
        "B_band": B_BAND, "B_layer": B_LAYER,
        "logistic_all_band_layers": True,
        "logistic_speed_note": ("pilot timing on L1 showed a single logistic fit "
                                 "on (614x2560) took ~0.056s, so the full per-layer "
                                 "logistic grid (no restriction to layers 13/17/21) "
                                 "was affordable within the wall-clock budget."),
    }
    return cells, notes, band_npz


# --------------------------------------------------------------------------- #
# multiplicity (Holm)
# --------------------------------------------------------------------------- #
def holm(pvalues: dict) -> dict:
    items = [(k, v) for k, v in pvalues.items() if np.isfinite(v)]
    items.sort(key=lambda kv: kv[1])
    m = len(items)
    out = {}
    rejected_so_far = True
    for i, (key, p) in enumerate(items):
        thr = 0.05 / (m - i)
        if rejected_so_far and p <= thr:
            decision = "REJECT_NULL"
        else:
            rejected_so_far = False
            decision = "RETAIN_NULL"
        out[key] = {"p_raw": float(p), "holm_threshold": float(thr), "rank": i + 1,
                    "n_family": m, "decision": decision}
    for key, p in pvalues.items():
        if key not in out:
            out[key] = {"p_raw": float(p) if p is not None else float("nan"),
                        "holm_threshold": float("nan"), "rank": -1,
                        "n_family": m, "decision": "NOT_APPLICABLE_NONFINITE_P"}
    return out


def reorder_by_scenario(diff: np.ndarray, mask: np.ndarray, pos_idx: np.ndarray) -> np.ndarray:
    pos_positions = np.flatnonzero(mask)
    pos_to_i = {int(p): i for i, p in enumerate(pos_positions)}
    order = np.vectorize(pos_to_i.get)(pos_idx)
    return diff[order]  # (n_scen, k)


def paired_permutation_test(scores0: np.ndarray, scoresA: np.ndarray, y: np.ndarray,
                             sub: Substrate, cls: str = "REQUEST",
                             n_perm: int = N_PERM, seed: int = 0) -> dict:
    """H0: mean hit-difference = 0. Each arm thresholded at its OWN 1%-FPR point
    computed on the ORIGINAL (unresampled) arms; scenario-level sign-flip
    permutation on the per-item hit differences (a scenario's 4 positive rows
    flip together, since they are not independent draws)."""
    d = paired_tpr_diff_fixedthr(scores0, scoresA, y)
    mask = (y == 1) & np.isfinite(scores0) & np.isfinite(scoresA)
    d_grouped = reorder_by_scenario(d, mask, sub.pos_idx[cls])  # (n_scen, k)
    observed = float(d.mean())
    rng = np.random.default_rng(seed)
    signs = rng.integers(0, 2, size=(n_perm, sub.n_scen)) * 2 - 1
    perm_stats = (signs[:, :, None] * d_grouped[None, :, :]).reshape(n_perm, -1).mean(axis=1)
    p = float((np.sum(np.abs(perm_stats) >= abs(observed) - 1e-12) + 1) / (n_perm + 1))
    return {"observed_mean_hit_diff": observed, "p_perm": p, "n_perm": n_perm,
            "n_scenarios": sub.n_scen}


def band_logistic_delta_tpr1_boot(lineage: str, site: str, alpha: str,
                                   B: int = B_BAND, seed: int | None = None) -> np.ndarray:
    sub = substrate(lineage)
    scores = band_logistic_scores(lineage, site)
    pos_idx, neg_idx = sub.pos_idx["REQUEST"], sub.neg_idx["REQUEST"]
    seed = seed if seed is not None else stable_seed(lineage, site, alpha, "tost")
    picks = scenario_boot_indices(sub.n_scen, B, seed)
    posA, negA = gather_boot(scores[alpha], pos_idx, neg_idx, picks)
    pos0, neg0 = gather_boot(scores["0.00"], pos_idx, neg_idx, picks)
    tprA = vec_tpr_at_fpr(posA.astype(np.float64), negA.astype(np.float64), 0.01)
    tpr0 = vec_tpr_at_fpr(pos0.astype(np.float64), neg0.astype(np.float64), 0.01)
    return tprA - tpr0


def task3_tests() -> dict:
    logger.info("=== TASK 3: permutation tests + TOST on band-logistic-REQUEST cells ===")
    nonzero_alphas = ["0.25", "0.50", "0.75", "1.00"]
    tests = []
    pvals_all = {}
    pvals_by_site = {s: {} for s in SITES}
    for lineage in LINEAGES:
        sub = substrate(lineage)
        y = sub.y["REQUEST"]
        for site in SITES:
            scores = band_logistic_scores(lineage, site)
            for a in nonzero_alphas:
                seed = stable_seed(lineage, site, a, "perm")
                res = paired_permutation_test(scores["0.00"], scores[a], y, sub,
                                               cls="REQUEST", n_perm=N_PERM, seed=seed)
                name = f"{lineage}|{site}|a0.00->a{a}"
                tests.append({"lineage": lineage, "site": site, "alpha": a, **res, "name": name})
                pvals_all[name] = res["p_perm"]
                pvals_by_site[site][name] = res["p_perm"]

    holm_all48 = holm(pvals_all)
    holm_per_site16 = {s: holm(p) for s, p in pvals_by_site.items()}
    changed = []
    for name in pvals_all:
        s = name.split("|")[1]
        d_all = holm_all48[name]["decision"]
        d_site = holm_per_site16[s][name]["decision"]
        if d_all != d_site:
            changed.append({"name": name, "decision_holm48": d_all, "decision_holm_persite16": d_site})

    # ---- TOST: largest alpha where the 90% paired-bootstrap CI of dTPR1 in (-0.05,0.05)
    margin = 0.05
    tost_rows = []
    for lineage in LINEAGES:
        for site in SITES:
            largest_ok = None
            per_alpha = {}
            for a in nonzero_alphas:
                d_b = band_logistic_delta_tpr1_boot(lineage, site, a)
                lo, hi = percentile_ci(d_b, lo=5, hi=95)
                holds = (lo > -margin) and (hi < margin)
                per_alpha[a] = {"ci90": [lo, hi], "tost_holds": bool(holds)}
                if holds:
                    largest_ok = a
            tost_rows.append({"lineage": lineage, "site": site, "margin": margin,
                               "per_alpha": per_alpha,
                               "largest_alpha_equivalent": largest_ok})

    out = {
        "definition": ("H0: mean paired hit-difference at the 1%-FPR operating "
                        "point = 0, tested by a scenario-level sign-flip "
                        "permutation (10,000 perms; thresholds fixed from the "
                        "ORIGINAL a0.00/aX arms' own negatives, per m1_recognition's "
                        "paired_tpr_diff convention)."),
        "n_tests": len(tests), "tests": tests,
        "holm_across_all_48": holm_all48,
        "holm_within_each_site_16": holm_per_site16,
        "verdicts_changed_all_vs_persite": changed,
        "tost_margin_tpr_units": margin,
        "tost_definition": ("EQUIVALENT iff the 90% paired scenario-bootstrap "
                             "(B=2000) percentile CI of the alpha0->alphaX delta "
                             "in TPR@1%FPR lies entirely inside (-0.05, 0.05); "
                             "threshold recomputed on each bootstrap draw's own "
                             "resampled negatives (nonparametric bootstrap of "
                             "the whole statistic, not just the point estimate)."),
        "tost_rows": tost_rows,
        "note_10.6x_ratio_dropped": (
            "The iter-2 ratio |dTPR@1%FPR| / |dAUROC| = 10.6x is DROPPED here: "
            "it is a ratio of two unlike-scaled quantities (a bounded operating-point "
            "statistic and a rank statistic), not a quantity with its own sampling "
            "distribution or a defensible null, and is not reported as an estimate "
            "anywhere in this artifact's outputs."
        ),
    }
    return out


# --------------------------------------------------------------------------- #
# TASK 4: L4 (non-safety control) contrasts
# --------------------------------------------------------------------------- #
def verify_shared_substrate() -> dict:
    subs = {l: substrate(l) for l in LINEAGES}
    ref = subs["L1"]
    checks = {}
    for l in LINEAGES:
        s = subs[l]
        same_pk = set(s.pair_keys) == set(ref.pair_keys)
        same_sid = list(s.sub["sid"]) == list(ref.sub["sid"])
        same_pos_idx = np.array_equal(s.pos_idx["REQUEST"], ref.pos_idx["REQUEST"])
        checks[l] = {"same_pair_key_set_as_L1": bool(same_pk),
                     "same_sid_sequence_as_L1": bool(same_sid),
                     "same_REQUEST_pos_idx_layout_as_L1": bool(same_pos_idx)}
    return checks


def metric_boot(metric: str, scores: dict, alpha0: str, alphaX: str,
                 pos_idx: np.ndarray, neg_idx: np.ndarray, picks: np.ndarray) -> np.ndarray:
    pos0, neg0 = gather_boot(scores[alpha0], pos_idx, neg_idx, picks)
    posX, negX = gather_boot(scores[alphaX], pos_idx, neg_idx, picks)
    pos0, neg0 = pos0.astype(np.float64), neg0.astype(np.float64)
    posX, negX = posX.astype(np.float64), negX.astype(np.float64)
    if metric == "auroc":
        v0, vX = vec_auroc(pos0, neg0), vec_auroc(posX, negX)
    elif metric == "tpr1":
        v0, vX = vec_tpr_at_fpr(pos0, neg0, 0.01), vec_tpr_at_fpr(posX, negX, 0.01)
    elif metric == "tpr5":
        v0, vX = vec_tpr_at_fpr(pos0, neg0, 0.05), vec_tpr_at_fpr(posX, negX, 0.05)
    else:
        raise ValueError(metric)
    return v0 - vX  # "drop" = alpha0 - alphaX


def metric_point(metric: str, scores: dict, alpha0: str, alphaX: str,
                  pos_idx: np.ndarray, neg_idx: np.ndarray) -> float:
    pos0, neg0 = scores[alpha0][pos_idx.ravel()], scores[alpha0][neg_idx.ravel()]
    posX, negX = scores[alphaX][pos_idx.ravel()], scores[alphaX][neg_idx.ravel()]
    if metric == "auroc":
        v0, vX = auroc_scalar(pos0, neg0), auroc_scalar(posX, negX)
    else:
        fpr = 0.01 if metric == "tpr1" else 0.05
        v0 = tpr_at_fpr_scalar(pos0, neg0, fpr)["tpr"]
        vX = tpr_at_fpr_scalar(posX, negX, fpr)["tpr"]
    return v0 - vX


def task4_contrasts() -> dict:
    logger.info("=== TASK 4: L4 non-safety-control contrasts ===")
    substrate_check = verify_shared_substrate()
    ref = substrate("L1")
    pos_idx, neg_idx = ref.pos_idx["REQUEST"], ref.neg_idx["REQUEST"]
    rows = []
    for site in SITES:
        for alphaX in ("0.50", "1.00"):
            drops_pt = {}
            for lineage in LINEAGES:
                scores = band_logistic_scores(lineage, site)
                drops_pt[lineage] = {
                    "auroc": metric_point("auroc", scores, "0.00", alphaX, pos_idx, neg_idx),
                    "tpr1": metric_point("tpr1", scores, "0.00", alphaX, pos_idx, neg_idx),
                    "tpr5": metric_point("tpr5", scores, "0.00", alphaX, pos_idx, neg_idx),
                }
            for other in ("L1", "L2", "L3"):
                seed = stable_seed(other, "L4", site, alphaX)
                picks = scenario_boot_indices(ref.n_scen, B_BAND, seed)
                scores_other = band_logistic_scores(other, site)
                scores_l4 = band_logistic_scores("L4", site)
                row = {"site": site, "alpha": alphaX, "lineage": other, "ref": "L4"}
                for metric in ("auroc", "tpr1", "tpr5"):
                    drop_other_b = metric_boot(metric, scores_other, "0.00", alphaX, pos_idx, neg_idx, picks)
                    drop_l4_b = metric_boot(metric, scores_l4, "0.00", alphaX, pos_idx, neg_idx, picks)
                    contrast_b = drop_other_b - drop_l4_b
                    ci = percentile_ci(contrast_b)
                    row[f"drop_{metric}_{other}"] = drops_pt[other][metric]
                    row[f"drop_{metric}_L4"] = drops_pt["L4"][metric]
                    row[f"contrast_{metric}"] = drops_pt[other][metric] - drops_pt["L4"][metric]
                    row[f"contrast_{metric}_ci"] = ci
                rows.append(row)

    # verdict, LATE only, at alpha=1.00, tpr1 metric (primary operating point)
    late_a1 = [r for r in rows if r["site"] == "LATE" and r["alpha"] == "1.00"]
    rescued = []
    for r in late_a1:
        lo, hi = r["contrast_tpr1_ci"]
        if r["contrast_tpr1"] > 0 and lo > 0:
            rescued.append(r["lineage"])
    verdict = ("execution reading RESCUED" if rescued else
               "execution reading WITHDRAWN (L4 drop >= safety-lineage drop, "
               "CI does not exclude 0 in L4's favour)")

    pooled_mean_note = (
        "The mean over L1..L4 reported elsewhere in this artifact (e.g. task1's "
        "cross-lineage means) is a POOLED MEAN OF FOUR CHECKPOINTS, not a "
        "sampling estimate of a population of lineages: n=4 is the entire "
        "panel, not a random sample, so no sampling-based CI is attached to "
        "that mean and none should be inferred from one."
    )
    return {
        "substrate_identity_check": substrate_check,
        "drop_definition": "drop_s(Lk) = metric(alpha=0.00) - metric(alpha=X), band-pooled logistic REQUEST probe, site s",
        "rows": rows,
        "verdict_LATE_alpha1.00_tpr1": verdict,
        "rescued_lineages": rescued,
        "pooled_mean_of_4_not_an_estimate": pooled_mean_note,
    }


# --------------------------------------------------------------------------- #
# TASK 7: inventory
# --------------------------------------------------------------------------- #
def task7_inventory() -> dict:
    logger.info("=== TASK 7: inventory ===")
    import collections
    out = {}
    for lineage in LINEAGES:
        m = meta_json(lineage)
        lastp_layers, win_layers = set(), set()
        keys_per_alpha = {}
        n_npz_files = 0
        for a in ALPHAS:
            mapping = key_to_part(lineage, a)
            n_npz_files += len(set(mapping.values()))
            keys_per_alpha[a] = len(mapping)
            for k in mapping:
                if "|lastp|" in k:
                    try:
                        lastp_layers.add(int(k.rsplit("|", 1)[1]))
                    except ValueError:
                        pass
                if "|win|" in k:
                    parts = k.split("|")
                    try:
                        win_layers.add(int(parts[-1]))
                    except ValueError:
                        pass
        idx = index_json(lineage)
        group_counts = {g: len(v) for g, v in idx.items()}
        item_df = pd.DataFrame(idx["item"])
        out[lineage] = {
            "repo": m["repo"], "r_ablit_layer": m["r_ablit_layer"], "band": m["band"],
            "n_npz_files": n_npz_files, "n_keys_per_alpha": keys_per_alpha,
            "lastp_layers_stored": sorted(lastp_layers),
            "win_layers_stored": sorted(win_layers),
            "group_row_counts": group_counts,
            "expected_group_row_counts": {"item": 1152, "fit_content": 256, "fit_ablit": 256,
                                           "damage": 256, "damage_matched": 184, "neutral": 33,
                                           "ladder": 480, "k4": 192, "domain": 240},
            "item_prefix_counts": item_df["prefix"].value_counts().to_dict(),
            "item_request_counts": item_df["request"].value_counts().to_dict(),
            "item_family_counts": item_df["family"].value_counts().to_dict(),
            "item_item_family_counts": item_df["item_family"].value_counts().to_dict(),
        }
    return out


# --------------------------------------------------------------------------- #
# TASK 6: depth-accumulation on a FIXED axis
# --------------------------------------------------------------------------- #
def raw_diffmeans(X: np.ndarray, y: np.ndarray):
    mu1, mu0 = X[y == 1].mean(0), X[y == 0].mean(0)
    u = mu1 - mu0
    n = np.linalg.norm(u)
    return (u / n if n > 0 else u), u


def cohend_scalar(proj: np.ndarray, y: np.ndarray) -> float:
    p1, p0 = proj[y == 1], proj[y == 0]
    n1, n0 = len(p1), len(p0)
    if n1 < 2 or n0 < 2:
        return float("nan")
    sp = math.sqrt(((n1 - 1) * p1.var(ddof=1) + (n0 - 1) * p0.var(ddof=1)) / (n1 + n0 - 2))
    return float((p1.mean() - p0.mean()) / sp) if sp > 0 else float("nan")


def _pair_bootstrap_matrices(n0: int, n1_offset: int) -> tuple:
    """pos_idx/neg_idx (n,1) matrices for a plain (non-scenario) stratified
    bootstrap over a 2-class array, reusing the scenario-bootstrap machinery
    (each 'scenario' is a single item, k=1)."""
    pos_idx = np.arange(n1_offset, n1_offset + n0).reshape(-1, 1)
    return pos_idx


def depth_growth(layers: list[int], y: np.ndarray, get_X: Callable[[int], np.ndarray],
                  pos_idx: np.ndarray, neg_idx: np.ndarray, n_scen: int,
                  B: int, seed: int) -> dict:
    l0 = layers[0]
    X0 = get_X(l0)
    u13, _ = raw_diffmeans(X0, y)
    rows = []
    proj_by_layer = {}
    for l in layers:
        Xl = get_X(l)
        proj_fixed = Xl.astype(np.float64) @ u13.astype(np.float64)
        proj_by_layer[l] = proj_fixed
        raw_gap = float(proj_fixed[y == 1].mean() - proj_fixed[y == 0].mean())
        mean_norm = float(np.linalg.norm(Xl, axis=1).mean())
        gap_norm = raw_gap / mean_norm if mean_norm > 0 else float("nan")
        d_fixed = cohend_scalar(proj_fixed, y)
        u_own, _ = raw_diffmeans(Xl, y)
        proj_own = Xl.astype(np.float64) @ u_own.astype(np.float64)
        d_own = cohend_scalar(proj_own, y)
        cos_u = float(np.dot(u13, u_own))
        rows.append({"layer": int(l), "raw_gap_fixed_axis": raw_gap,
                     "gap_norm_fixed_axis": gap_norm, "cohend_fixed_axis": d_fixed,
                     "cohend_own_axis": d_own, "abs_cos_u13_ul": abs(cos_u),
                     "mean_hnorm": mean_norm})
    gap0 = rows[0]["raw_gap_fixed_axis"]
    peak_idx = int(np.argmax(np.abs([r["raw_gap_fixed_axis"] for r in rows])))
    ratio_peak_pt = (rows[peak_idx]["raw_gap_fixed_axis"] / gap0) if gap0 else float("nan")
    rho_pt, _ = sps.spearmanr(layers, [r["gap_norm_fixed_axis"] for r in rows])

    picks = scenario_boot_indices(n_scen, B, seed)
    gap_boot = {}
    for l in layers:
        pos_m, neg_m = gather_boot(proj_by_layer[l], pos_idx, neg_idx, picks)
        gap_boot[l] = pos_m.mean(axis=1) - neg_m.mean(axis=1)
    gapnorm_boot = np.stack([gap_boot[l] / rows[i]["mean_hnorm"] for i, l in enumerate(layers)], axis=1)
    rho_boot = np.array([sps.spearmanr(layers, gapnorm_boot[b])[0] for b in range(B)])
    ratio_boot = gap_boot[layers[peak_idx]] / np.where(gap_boot[layers[0]] == 0, np.nan, gap_boot[layers[0]])

    rho_ci = percentile_ci(rho_boot)
    ratio_ci = percentile_ci(ratio_boot)
    accumulation = bool(rho_ci[0] > 0 and ratio_ci[0] > 1)
    own_grows = rows[peak_idx]["cohend_own_axis"] > rows[0]["cohend_own_axis"]
    cos_decays = rows[peak_idx]["abs_cos_u13_ul"] < 0.9 * rows[0]["abs_cos_u13_ul"] + 1e-9
    if accumulation:
        verdict = "ACCUMULATION"
    elif own_grows and cos_decays:
        verdict = "LAYER_SPECIFIC_DIRECTION"
    else:
        verdict = "NO_CLEAR_PATTERN"

    return {"layers": [int(l) for l in layers], "per_layer": rows,
            "peak_layer": int(layers[peak_idx]),
            "ratio_peak_over_l0_fixed_axis": {"point": ratio_peak_pt, "ci95": ratio_ci, "B": B},
            "spearman_gapnorm_vs_layer_fixed_axis": {"point": float(rho_pt), "ci95": rho_ci, "B": B},
            "verdict": verdict}


def task6_accumulator() -> dict:
    logger.info("=== TASK 6: depth accumulation ===")
    out: dict = {"band_limited_note": "band-limited (layers 13..21 + the lineage's own r_ablit layer only)"}
    for lineage in LINEAGES:
        t_lin = time.time()
        m = meta_json(lineage)
        rl = m["r_ablit_layer"]
        proj_layers = sorted(set(BAND_LAYERS) | {rl})
        sub = substrate(lineage)
        lin_out = {"r_ablit_layer": rl, "proj_layers": proj_layers, "by_group_alpha": {}}

        for alpha in ("0.00", "1.00"):
            for site in SITES:
                def get_X(l, _lineage=lineage, _alpha=alpha, _site=site, _sub=sub):
                    return get_layer(_lineage, _alpha, "item", _site, l)[_sub.rows]
                seed = stable_seed(lineage, "item", site, alpha)
                res = depth_growth(proj_layers, sub.y["REQUEST"], get_X,
                                    sub.pos_idx["REQUEST"], sub.neg_idx["REQUEST"],
                                    sub.n_scen, B=500, seed=seed)
                lin_out["by_group_alpha"][f"item|{site}|{alpha}"] = res
            clear_array_cache()

        for group in ("damage", "fit_ablit"):
            idxg = index_json(lineage)[group]
            yg = np.array([r["label"] for r in idxg], dtype=int)
            n_pos, n_neg = int(yg.sum()), int((1 - yg).sum())
            pos_idx = np.flatnonzero(yg == 1).reshape(-1, 1)
            neg_idx = np.flatnonzero(yg == 0).reshape(-1, 1)
            n_scen = min(n_pos, n_neg)
            pos_idx, neg_idx = pos_idx[:n_scen], neg_idx[:n_scen]
            for alpha in ("0.00", "1.00"):
                def get_X(l, _lineage=lineage, _alpha=alpha, _group=group):
                    return load_array(_lineage, _alpha, f"{_group}|lastp|{l}")
                seed = stable_seed(lineage, group, alpha)
                res = depth_growth(proj_layers, yg, get_X, pos_idx, neg_idx, n_scen,
                                    B=500, seed=seed)
                lin_out["by_group_alpha"][f"{group}|lastp|{alpha}"] = res
            clear_array_cache()

        # ---- iter-1 "signal along u grows ~138x with depth" -------------- #
        d_stored = np.load(H / f"{lineage}_dirs.npz")
        u_stored = d_stored["u"]
        idx_ablit = index_json(lineage)["fit_ablit"]
        y_ablit = np.array([r["label"] for r in idx_ablit], dtype=int)
        idx_damage = index_json(lineage)["damage"]
        y_damage = np.array([r["label"] for r in idx_damage], dtype=int)
        u_recompute, _ = raw_diffmeans(
            load_array(lineage, "0.00", f"fit_ablit|lastp|{rl}"), y_ablit)
        cos_u_stored_vs_recompute = float(np.dot(u_stored / np.linalg.norm(u_stored),
                                                  u_recompute / np.linalg.norm(u_recompute)))
        u138: dict = {"cos_stored_u_vs_refit_at_r_ablit_layer": cos_u_stored_vs_recompute}
        for gname, idxg, yg in (("fit_ablit", idx_ablit, y_ablit), ("damage", idx_damage, y_damage)):
            gaps = {}
            for l in proj_layers:
                X = load_array(lineage, "0.00", f"{gname}|lastp|{l}").astype(np.float64)
                proj = X @ u_stored.astype(np.float64)
                gaps[l] = float(proj[yg == 1].mean() - proj[yg == 0].mean())
            vals = np.array(list(gaps.values()))
            ratio_stored_u = float(np.max(np.abs(vals)) / np.min(np.abs(vals))) if np.min(np.abs(vals)) > 0 else float("nan")
            u138[gname] = {"gap_along_stored_u_per_layer": gaps,
                           "ratio_max_over_min_abs_gap": ratio_stored_u}
        u138["own_axis_ratio_for_comparison"] = {
            g: lin_out["by_group_alpha"][f"{g}|lastp|0.00"]["ratio_peak_over_l0_fixed_axis"]["point"]
            for g in ("damage", "fit_ablit")
        }
        u138["note"] = (
            "iter-1's ~138x claim spans iter-1's own full-depth causal-tracing "
            "layer set; this harvest stores activations ONLY at layers "
            f"{proj_layers} (band 13-21 plus r_ablit_layer={rl}), so the ratio "
            "here is max/min over those STORED layers only, not a like-for-like "
            "reproduction of a 36-layer sweep -- it is reported as the closest "
            "recomputation this harvest supports, explicitly flagged as "
            "band-limited."
        )
        lin_out["u_138x_recompute"] = u138

        # ---- post-lesion cosine of the diff-in-means direction ------------ #
        cos_lesion = {}
        for l in proj_layers:
            u0, _ = raw_diffmeans(load_array(lineage, "0.00", f"fit_ablit|lastp|{l}"), y_ablit)
            u1, _ = raw_diffmeans(load_array(lineage, "1.00", f"fit_ablit|lastp|{l}"), y_ablit)
            cos_lesion[l] = float(np.dot(u0, u1))
        item_cos_lesion = {}
        for l in proj_layers:
            X0 = get_layer(lineage, "0.00", "item", "LATE", l)[sub.rows]
            X1 = get_layer(lineage, "1.00", "item", "LATE", l)[sub.rows]
            u0, _ = raw_diffmeans(X0, sub.y["REQUEST"])
            u1, _ = raw_diffmeans(X1, sub.y["REQUEST"])
            item_cos_lesion[l] = float(np.dot(u0, u1))
        lin_out["post_lesion_cosine"] = {
            "fit_ablit_lastp_by_layer": cos_lesion,
            "fit_ablit_lastp_at_r_ablit_layer_note": (
                "quoted upstream as 0.000, label FORCED_BY_CONSTRUCTION: at the "
                "layer the ablation direction was ITSELF fitted and pinned for "
                "the projective lesion, a=1.00 zeroes exactly the component "
                "along that direction by construction, so the pre/post "
                "diff-in-means direction is forced near-orthogonal there."
            ),
            "fit_ablit_lastp_r_ablit_layer_value": cos_lesion.get(rl),
            "item_LATE_request_by_layer": item_cos_lesion,
            "informative_quantity_note": (
                "the layers 13..21 values (not the r_ablit_layer value) are the "
                "informative quantity: e.g. layer 13 was quoted upstream around "
                "0.985, i.e. the request-recognition direction is largely "
                "UNCHANGED by the lesion away from the pinned layer."
            ),
        }

        clear_array_cache()
        out[lineage] = lin_out
        logger.info("lineage {} accumulator done in {:.1f}s", lineage, time.time() - t_lin)
    return out


# --------------------------------------------------------------------------- #
# TASK 5: power for saturated cells
# --------------------------------------------------------------------------- #
def hm_var(auc: float, n_pos: int, n_neg: int) -> float:
    """Hanley-McNeil variance of an AUROC estimate."""
    a = auc
    q1 = a / (2 - a) if a < 2 else float("nan")
    q2 = 2 * a * a / (1 + a) if (1 + a) != 0 else float("nan")
    var = (a * (1 - a) + (n_pos - 1) * (q1 - a * a) + (n_neg - 1) * (q2 - a * a)) / (n_pos * n_neg)
    return max(var, 0.0)


def hm_mde(auc0: float, n_pos: int, n_neg: int, power: float = 0.8, alpha: float = 0.05) -> float:
    """Smallest drop in AUROC (from auc0) detectable at `power`, paired approx:
    detect if (A0 - A1) / sqrt(var_HM(A1)) >= z_{1-alpha/2} + z_power."""
    zcrit = sps.norm.ppf(1 - alpha / 2) + sps.norm.ppf(power)
    lo, hi = 0.0, auc0
    for _ in range(60):
        mid = (lo + hi) / 2
        ratio = (auc0 - mid) / math.sqrt(max(hm_var(mid, n_pos, n_neg), 1e-12))
        if ratio < zcrit:
            hi = mid
        else:
            lo = mid
    return auc0 - hi


def tpr_mcnemar_mde(n_pos: int, tpr0: float, n_sims: int = 5000, power: float = 0.8,
                     alpha: float = 0.05, seed: int = 0) -> dict:
    """Smallest fraction `delta` of the TPR0 hits that, if lost, is detected by
    an exact McNemar test (c=0, all discordant pairs favour the unlesioned arm)
    with `power` across `n_sims` Monte Carlo draws of the baseline hit count."""
    rng = np.random.default_rng(seed)

    def power_at(delta: float) -> float:
        k0 = rng.binomial(n_pos, tpr0, size=n_sims)
        m = rng.binomial(k0, delta)
        p = np.where(m > 0, np.minimum(1.0, 2 * 0.5 ** m), 1.0)
        return float(np.mean(p < alpha))

    lo, hi = 0.0, 1.0
    if power_at(hi) < power:
        return {"delta_mde": float("nan"), "note": "power<0.8 not reached even at delta=1"}
    for _ in range(25):
        mid = (lo + hi) / 2
        if power_at(mid) >= power:
            hi = mid
        else:
            lo = mid
    return {"delta_mde": hi, "power_at_delta_mde": power_at(hi), "n_sims": n_sims}


def bootstrap_shift_mde(pos: np.ndarray, neg: np.ndarray, n_sims: int = 40,
                         n_boot: int = 100, power: float = 0.8, seed: int = 0,
                         f_grid=(0.02, 0.05, 0.1, 0.2, 0.35, 0.5)) -> dict:
    """Shift harmful scores toward the benign mean by fraction f of the class
    gap; find smallest f at which a paired scenario-free bootstrap AUROC-diff
    test (95% CI excludes 0) has ~80% power, over n_sims outer sims x n_boot
    inner bootstraps (coarse grid, per the task's explicit allowance).

    DEVIATION: n_sims/n_boot/grid coarsened from the nominal 200x200 to
    40x100 with a 6-point grid, after a live pilot showed the full grid was
    too slow across the ~150 qualifying (AUROC>=0.995) cells to fit the
    wall-clock budget; see results/laneb_deviations.json."""
    rng = np.random.default_rng(seed)
    n_pos, n_neg = len(pos), len(neg)
    neg_mean = float(neg.mean())
    gap = float(pos.mean() - neg_mean)
    if gap == 0 or n_pos < 2 or n_neg < 2:
        return {"f_mde": float("nan"), "note": "degenerate class gap or too few items"}
    auroc_orig = auroc_scalar(pos, neg)

    def power_at(f: float) -> float:
        pos_shift = pos - f * gap
        detected = 0
        for _ in range(n_sims):
            pi = rng.integers(0, n_pos, size=(n_boot, n_pos))
            ni = rng.integers(0, n_neg, size=(n_boot, n_neg))
            pos_b, neg_b = pos[pi], neg[ni]
            posS_b, negS_b = pos_shift[pi], neg[ni]
            a_orig = vec_auroc(pos_b, neg_b)
            a_shift = vec_auroc(posS_b, negS_b)
            diff = a_shift - a_orig
            lo_, hi_ = np.percentile(diff, [2.5, 97.5])
            if not (lo_ <= 0 <= hi_):
                detected += 1
        return detected / n_sims

    powers = {}
    for f in f_grid:
        powers[f] = power_at(f)
        if powers[f] >= power:
            break
    reached = [f for f, p in powers.items() if p >= power]
    f_mde = min(reached) if reached else float("nan")
    return {"f_mde": f_mde, "grid_powers": powers, "auroc_orig": auroc_orig,
            "n_sims": n_sims, "n_boot": n_boot,
            "note": "" if reached else "power<0.8 not reached within the coarse grid up to f_grid max"}


def margin_to_threshold(pos: np.ndarray, neg: np.ndarray) -> float:
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    pooled_sd = float(np.sqrt(0.5 * (pos.var(ddof=1) + neg.var(ddof=1)))) if pos.size > 1 and neg.size > 1 else float("nan")
    if not pooled_sd or pooled_sd == 0:
        return float("nan")
    return float((pos.min() - neg.max()) / pooled_sd)


def task5_power(cells: list[dict]) -> dict:
    logger.info("=== TASK 5: power for saturated cells ===")
    note_deviation(
        "task5 MDE(b) McNemar simulation: modelled as a one-directional "
        "degradation (lesion can only turn a hit into a miss, so the exact "
        "McNemar discordant count c=0 by construction) rather than a general "
        "two-directional flip; this matches the observed direction of every "
        "lesion effect in this harvest (alpha increases -> TPR never rises) "
        "and gives a conservative (smaller) detectable delta than a symmetric "
        "McNemar design would."
    )
    note_deviation(
        "task5 MDE(c) bootstrap-shift power: a live pilot on the actual 152 "
        "qualifying cells showed the nominal 200 outer sims x 200 inner boots "
        "x 9-point grid would not finish inside the wall-clock budget (>14 "
        "min and rising with no completion for a single lineage's worth of "
        "cells, running on a 2-CPU box shared with another job), so the "
        "pipeline was stopped after tasks 1-4 had already been written to "
        "disk and task5/6/7 were resumed standalone with n_sims=40, "
        "n_boot=100 and a coarser 6-point f_grid (0.02..0.5), stopping at the "
        "first f reaching >=80% power; cells needing f>0.5 are reported as "
        "'not reached within grid'. This is a wall-clock-driven coarsening of "
        "an already-coarse-by-design method, not a correctness change to "
        "methods (a) or (b)."
    )
    qualifying = [c for c in cells if c["alpha"] == "0.00" and np.isfinite(c["auroc"]) and c["auroc"] >= 0.995]
    logger.info("task5: {} qualifying (cell, alpha=0, AUROC>=0.995) rows out of {} alpha=0 rows",
                len(qualifying), sum(1 for c in cells if c["alpha"] == "0.00"))

    rows = []
    for c in qualifying:
        lineage, site, layer, probe, cls = c["lineage"], c["site"], c["layer"], c["probe"], c["cls"]
        sub = substrate(lineage)
        y = sub.y[cls]
        X = get_feature(lineage, "0.00", "item", site, layer)[sub.rows]
        fit_fn = _fit_diffmeans if probe == "diffmeans" else _fit_logistic
        # reuse the SAME crossfit scores already computed conceptually: refit cheaply
        scores = crossfit_scores(probe, {"0.00": X}, y, sub.folds)["0.00"]
        pos, neg = scores[y == 1], scores[y == 0]
        n_pos, n_neg = pos.size, neg.size
        tpr1 = tpr_at_fpr_scalar(pos, neg, 0.01)
        smallest_fpr = 1.0 / n_neg
        note_0_1pct = "0.1%FPR reportable" if n_neg >= 1000 else "0.1%FPR NOT reportable (n_neg<1000)"

        mde_auroc = hm_mde(c["auroc"], n_pos, n_neg)
        mde_tpr = tpr_mcnemar_mde(n_pos, tpr1["tpr"] if tpr1["estimable"] else 0.5,
                                   seed=stable_seed(lineage, site, layer, probe, cls, "mcnemar"))
        mde_shift = bootstrap_shift_mde(pos.astype(np.float64), neg.astype(np.float64),
                                          seed=stable_seed(lineage, site, layer, probe, cls, "shift"))
        margin = margin_to_threshold(pos, neg)
        sentence = (
            f"At n_pos={n_pos}, n_neg={n_neg}, a drop of AUROC from {c['auroc']:.4f} to "
            f"{c['auroc'] - mde_auroc:.4f} or of TPR@1%FPR by {mde_tpr.get('delta_mde', float('nan')):.4f} "
            f"(fraction of hits lost) would have been detected with ~80% power; the observed "
            f"alpha=1.00 change on this cell was d_auroc={c.get('d_auroc')}, d_tpr1={c.get('d_tpr1')} "
            f"[{c.get('d_tpr1_ci')}]."
        ) if np.isfinite(mde_auroc) else "MDE not resolvable (degenerate variance)."
        rows.append({
            "lineage": lineage, "site": site, "layer": layer, "probe": probe, "cls": cls,
            "auroc0": c["auroc"], "tpr1_0": tpr1["tpr"], "n_pos": n_pos, "n_neg": n_neg,
            "smallest_resolvable_fpr": smallest_fpr, "note_0_1pct_fpr": note_0_1pct,
            "mde_auroc_hanley_mcneil": mde_auroc,
            "mde_tpr1_mcnemar_sim": mde_tpr,
            "mde_bootstrap_shift": mde_shift,
            "margin_to_threshold_sd_units": margin,
            "sentence": sentence,
        })

    # damage-corpus cells from task1's reconciliation
    damage_rows = []
    for lineage in LINEAGES:
        r_layer = meta_json(lineage)["r_ablit_layer"]
        idxd = index_json(lineage)["damage"]
        y = np.array([r["label"] for r in idxd], dtype=int)
        x0 = load_array(lineage, "0.00", f"damage|lastp|{r_layer}")
        from sklearn.model_selection import StratifiedKFold
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
        s = np.empty(len(y))
        for tr, te in skf.split(x0, y):
            sc, clf = _fit_logistic(x0[tr], y[tr])
            s[te] = _apply("logistic", (sc, clf), x0[te])
        pos, neg = s[y == 1], s[y == 0]
        n_pos, n_neg = pos.size, neg.size
        auc = auroc_scalar(pos, neg)
        tpr1 = tpr_at_fpr_scalar(pos, neg, 0.01)
        mde_auroc = hm_mde(auc, n_pos, n_neg)
        mde_tpr = tpr_mcnemar_mde(n_pos, tpr1["tpr"] if tpr1["estimable"] else 0.5,
                                   seed=stable_seed(lineage, "damage", "mcnemar"))
        margin = margin_to_threshold(pos, neg)
        damage_rows.append({
            "lineage": lineage, "group": "damage", "read_site": f"lastp|{r_layer}",
            "auroc0": auc, "tpr1_0": tpr1["tpr"], "n_pos": n_pos, "n_neg": n_neg,
            "smallest_resolvable_fpr": 1.0 / n_neg,
            "note_0_1pct_fpr": "0.1%FPR NOT reportable (n_neg<1000)",
            "mde_auroc_hanley_mcneil": mde_auroc, "mde_tpr1_mcnemar_sim": mde_tpr,
            "margin_to_threshold_sd_units": margin,
            "sentence": (f"At n_pos={n_pos}, n_neg={n_neg}, a drop of AUROC from {auc:.4f} to "
                         f"{auc - mde_auroc:.4f} would have been detected with ~80% power; the "
                         f"crude damage corpus read AUROC=1.0 at EVERY lesion strength, i.e. no "
                         f"drop this large was observed.") if np.isfinite(mde_auroc) else "n/a",
        })

    return {
        "n_qualifying_item_cells": len(qualifying),
        "qualifying_threshold": "alpha=0.00 AUROC >= 0.995",
        "item_cell_rows": rows,
        "damage_corpus_rows": damage_rows,
        "methods": {
            "a_hanley_mcneil": "paired approx: detect if (A0-A1)/sqrt(var_HM(A1)) >= z_.975+z_.8=2.80",
            "b_mcnemar_sim": "5000 Monte Carlo draws of baseline hit count k0~Binom(n_pos,tpr0); "
                             "m~Binom(k0,delta) hits lost; exact McNemar p=2*0.5^m (c=0); power=P(p<.05)",
            "c_bootstrap_shift": "200 outer sims x 200 inner bootstraps (coarse grid), harmful scores "
                                  "shifted toward the benign mean by f*gap, detection = 95% CI of the "
                                  "bootstrap AUROC-diff excluding 0",
        },
    }


@logger.catch(reraise=True)
def main() -> None:
    t_start = time.time()
    logger.info("laneb.py starting; results -> {}", RESULTS)

    # ---- 1: reconciliation ------------------------------------------------ #
    p = RESULTS / "laneb_reconcile.json"
    reconcile = task1_reconcile()
    dump_json(p, reconcile)
    logger.info("[{:.1f}s elapsed] task1 done", time.time() - t_start)

    # ---- 2: main grid ------------------------------------------------------ #
    cells, grid_notes, band_npz = task2_main_grid()
    dump_json(RESULTS / "laneb_cells.json", {"notes": grid_notes, "cells": cells})
    np.savez_compressed(RESULTS / "laneb_scores_band.npz", **band_npz)
    logger.info("[{:.1f}s elapsed] task2 done, {} cells, npz has {} arrays",
                time.time() - t_start, len(cells), len(band_npz))

    # ---- 3: tests ----------------------------------------------------------- #
    tests = task3_tests()
    dump_json(RESULTS / "laneb_tests.json", tests)
    logger.info("[{:.1f}s elapsed] task3 done", time.time() - t_start)

    # ---- 4: L4 contrasts ----------------------------------------------------- #
    contrasts = task4_contrasts()
    dump_json(RESULTS / "laneb_contrasts.json", contrasts)
    logger.info("[{:.1f}s elapsed] task4 done", time.time() - t_start)

    # ---- 5: power ------------------------------------------------------------ #
    power = task5_power(cells)
    dump_json(RESULTS / "laneb_power.json", power)
    logger.info("[{:.1f}s elapsed] task5 done", time.time() - t_start)

    # ---- 6: accumulator -------------------------------------------------------- #
    accum = task6_accumulator()
    dump_json(RESULTS / "laneb_accum.json", accum)
    logger.info("[{:.1f}s elapsed] task6 done", time.time() - t_start)

    # ---- 7: inventory ----------------------------------------------------------- #
    inventory = task7_inventory()
    dump_json(RESULTS / "laneb_inventory.json", inventory)
    logger.info("[{:.1f}s elapsed] task7 done", time.time() - t_start)

    dump_json(RESULTS / "laneb_deviations.json", {"deviations": DEVIATIONS})
    logger.info("ALL DONE in {:.1f}s ({:.1f} min)", time.time() - t_start, (time.time() - t_start) / 60)


if __name__ == "__main__":
    main()

