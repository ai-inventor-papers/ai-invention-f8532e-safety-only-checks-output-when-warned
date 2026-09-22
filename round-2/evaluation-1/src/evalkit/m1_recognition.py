#!/usr/bin/env python3
"""M1 -- RECOGNITION WITH HEADROOM. The single scientific deliverable.

READOUT_CLASS: activation.

Iteration 1's recognition evidence was a held-out probe reading AUROC 1.000 at
every lesion strength. An outcome saturated BEFORE the manipulation cannot
falsify anything in either direction, so the premise is re-expressed on three
outcomes that still move after AUROC has pinned:

  R1  TPR at 1% FPR   -- operating point, with a Clopper-Pearson interval and
                         the smallest resolvable step 1/n_neg. Guarded: below
                         100 negatives the 1% point is NOT_ESTIMABLE and is
                         reported as such rather than interpolated.
  R2  TPR at 5% FPR   -- the companion that keeps R1's guard honest.
  R3  restricted-labelled-budget AUROC at k in {16,32,64} -- de-saturation along
                         the supervision axis, which is also the commissioned one.
  R4  TOST equivalence per parent-child pair on the paired difference in R1.
  R5  a power sentence attached verbatim to every row.

Source (a), the version with real inferential content, is used wherever M0 found
per-item band activations: the probe is fitted with FROZEN, PRE-DECLARED folds on
the alpha=0.00 arm and SCORES the alpha>0 arms, so the lesion is evaluated by a
probe it never saw. Sources (b) Lane A per-item cell projections and (c) Lane C
stored scalars are reported beside it.
"""

from __future__ import annotations

import gc
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from . import laneb_substrate as LB
from . import paths as P
from . import stats as S
from .prereg import PREREG

MARGIN = PREREG["M1_equivalence_margin_tpr_units"]
BUDGETS = PREREG["M1_restricted_budgets_k"]
REPEATS = PREREG["M1_restricted_budget_repeats"]
MIN_NEG_1PCT = PREREG["M1_min_negatives_for_1pct"]
N_FOLDS = 5
WINDOWS = ("LATE", "EARLY")
PRIMARY_WINDOW = "LATE"

# Sanity bounds printed by iteration 1. A recomputed number that does not land
# near its stored counterpart is a pipeline bug, not a finding.
SANITY = {
    "lane_a_B1_diffmeans_auroc_trained": (0.691, 0.729),
    "lane_a_B1_diffmeans_auroc_randinit": 0.494,
    "lane_a_B2_supervised_probe_trained": (0.970, 0.980),
    "lane_a_B2_supervised_probe_randinit": 0.347,
}


# --------------------------------------------------------------------------- #
# frozen folds
# --------------------------------------------------------------------------- #
def frozen_folds(pair_keys: pd.Series, *, n_folds: int = N_FOLDS) -> np.ndarray:
    """Deterministic fold id per row, assigned by sha256 of the PAIR key.

    Folding on the pair rather than the row keeps a minimal-edit twin's two
    halves on the same side of every split, so no fold can leak its partner.
    The assignment is a pure function of the key, so it is identical for every
    lineage and every lesion strength -- that is what "pre-declared" means here.
    """
    out = np.empty(len(pair_keys), dtype=int)
    for i, key in enumerate(pair_keys):
        digest = hashlib.sha256(f"M1|{key}".encode()).digest()
        out[i] = int.from_bytes(digest[:8], "big") % n_folds
    return out


# --------------------------------------------------------------------------- #
# the probe
# --------------------------------------------------------------------------- #
def _fit_probe(x: np.ndarray, y: np.ndarray) -> tuple[StandardScaler, LogisticRegression]:
    scaler = StandardScaler().fit(x)
    clf = LogisticRegression(max_iter=2000, C=1.0, solver="lbfgs")
    clf.fit(scaler.transform(x), y)
    return scaler, clf


def _score(scaler: StandardScaler, clf: LogisticRegression, x: np.ndarray) -> np.ndarray:
    return clf.decision_function(scaler.transform(x))


def crossfit_scores(x_fit: np.ndarray, y: np.ndarray, folds: np.ndarray,
                    x_score: np.ndarray) -> np.ndarray:
    """Cross-fitted scores: for each fold, fit on the OTHER folds of ``x_fit``
    and score that fold's rows of ``x_score``.

    When ``x_score is x_fit`` this is ordinary cross-fitting. When ``x_score``
    is a LESIONED arm, the probe scoring it was fitted only on unlesioned rows
    it never saw, which is the comparison the lesion is supposed to survive.
    """
    scores = np.full(x_fit.shape[0], np.nan, dtype=float)
    for f in np.unique(folds):
        tr = folds != f
        te = folds == f
        if len(np.unique(y[tr])) < 2:
            continue
        scaler, clf = _fit_probe(x_fit[tr], y[tr])
        scores[te] = _score(scaler, clf, x_score[te])
        del scaler, clf
    return scores


def restricted_budget_auroc(x: np.ndarray, y: np.ndarray, k: int,
                            *, repeats: int = REPEATS, seed: int = 20260921) -> dict:
    """R3. Fit on k label-stratified items, score the held-out remainder."""
    rng = np.random.default_rng(seed + k)
    pos_idx = np.flatnonzero(y == 1)
    neg_idx = np.flatnonzero(y == 0)
    half = k // 2
    if min(pos_idx.size, neg_idx.size) <= half:
        return {"k": k, "mean": float("nan"), "p5": float("nan"), "p95": float("nan"),
                "n_repeats": 0, "note": f"k={k} exceeds the smaller class ({min(pos_idx.size, neg_idx.size)})"}
    vals = np.empty(repeats, dtype=float)
    for r in range(repeats):
        tr = np.concatenate([rng.choice(pos_idx, half, replace=False),
                             rng.choice(neg_idx, half, replace=False)])
        mask = np.zeros(y.size, dtype=bool)
        mask[tr] = True
        try:
            scaler, clf = _fit_probe(x[mask], y[mask])
            s = _score(scaler, clf, x[~mask])
        except ValueError:
            vals[r] = np.nan
            continue
        yy = y[~mask]
        vals[r] = S.auroc(s[yy == 1], s[yy == 0])
        del scaler, clf
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {"k": k, "mean": float("nan"), "p5": float("nan"), "p95": float("nan"),
                "n_repeats": 0, "note": "all repeats degenerate"}
    return {"k": k, "mean": float(vals.mean()),
            "p5": float(np.percentile(vals, 5)),
            "p95": float(np.percentile(vals, 95)),
            "sd": float(vals.std(ddof=1)) if vals.size > 1 else 0.0,
            "n_repeats": int(vals.size), "note": ""}


# --------------------------------------------------------------------------- #
# source (a): Lane B per-item band activations
# --------------------------------------------------------------------------- #
@dataclass
class ArmResult:
    lineage: str
    repo: str
    alpha: str
    window: str
    scores: np.ndarray
    y: np.ndarray
    folds: np.ndarray
    families: np.ndarray
    auroc: float
    r1: S.OperatingPoint
    r2: S.OperatingPoint
    r3: dict = field(default_factory=dict)


def _labelled_rows(lineage: str):
    df = LB.item_frame(lineage)
    keep = df["prefix"].isin(["hazardous", "benign"])
    sub = df[keep].reset_index(drop=True)
    y = (sub["request"] == "harmful").astype(int).to_numpy()
    folds = frozen_folds(sub["pair_key"], n_folds=N_FOLDS)
    fams = sub["item_family"].to_numpy()
    rows = sub["row"].to_numpy()
    return sub, rows, y, folds, fams


def lane_b_arms(lineage: str, *, windows=WINDOWS, do_budget: bool = True) -> list[ArmResult]:
    """Every lesion strength for one lineage, fitted on alpha=0.00 and scored across."""
    m = LB.meta(lineage)
    sub, rows, y, folds, fams = _labelled_rows(lineage)
    logger.info("M1(a) {} [{}] n={} (pos {} / neg {}) folds={} families={}",
                lineage, m.repo, len(rows), int(y.sum()), int((1 - y).sum()),
                len(np.unique(folds)), len(np.unique(fams)))

    out: list[ArmResult] = []
    for window in windows:
        base = LB.band_pool(lineage, "0.00", "item", window)[rows]
        for alpha in m.alphas:
            x = base if alpha == "0.00" else LB.band_pool(lineage, alpha, "item", window)[rows]
            scores = crossfit_scores(base, y, folds, x)
            ok = np.isfinite(scores)
            pos, neg = scores[ok & (y == 1)], scores[ok & (y == 0)]
            res = ArmResult(
                lineage=lineage, repo=m.repo, alpha=alpha, window=window,
                scores=scores, y=y, folds=folds, families=fams,
                auroc=S.auroc(pos, neg),
                r1=S.tpr_at_fpr(pos, neg, 0.01, min_neg_for_estimability=MIN_NEG_1PCT),
                r2=S.tpr_at_fpr(pos, neg, 0.05),
            )
            if do_budget and window == PRIMARY_WINDOW:
                for k in BUDGETS:
                    res.r3[k] = restricted_budget_auroc(x, y, k)
                logger.info("  {} a={} restricted-budget AUROC {}", lineage, alpha,
                            {k: round(v["mean"], 4) for k, v in res.r3.items()})
            out.append(res)
            if alpha != "0.00":
                del x
            gc.collect()
        del base
        gc.collect()
    return out


def paired_tpr_diff(parent: ArmResult, child: ArmResult) -> np.ndarray:
    """Per-positive-item difference in the TPR indicator, each arm at its OWN threshold.

    Pairing is by item, which is legitimate because both arms score the same
    1152-row substrate in the same order.
    """
    out = []
    for arm in (parent, child):
        ok = np.isfinite(arm.scores)
        neg = arm.scores[ok & (arm.y == 0)]
        if neg.size < MIN_NEG_1PCT:
            return np.array([])
        thr = float(np.quantile(neg, 0.99, method="higher"))
        out.append((arm.scores > thr).astype(float))
    mask = (parent.y == 1) & np.isfinite(parent.scores) & np.isfinite(child.scores)
    return out[1][mask] - out[0][mask]


# --------------------------------------------------------------------------- #
# source (b): Lane A per-item cell projections
# --------------------------------------------------------------------------- #
def lane_a_rows() -> tuple[list[dict], dict]:
    """ROC over hazardous versus benign cells within a pool, per checkpoint."""
    if not P.A_PER_ITEM_CELLS.exists():
        return [], {"status": "ABSENT", "glob": P.rel(P.A_PER_ITEM_CELLS)}
    df = pd.read_csv(P.A_PER_ITEM_CELLS)
    cols = list(df.columns)
    score_col = next((c for c in cols if "projection" in c.lower()), None)
    if score_col is None:
        return [], {"status": "NO_PROJECTION_COLUMN", "columns": cols}

    def hazardous_flag(cell: str) -> int | None:
        parts = str(cell).split("|")
        toks = [p.lower() for p in parts]
        if "haz" in toks or "hazardous" in toks:
            return 1
        if "ben" in toks or "benign" in toks:
            return 0
        return None

    df["_haz"] = df["cell"].map(hazardous_flag) if "cell" in cols else None
    rows: list[dict] = []
    pools = sorted(df["pool"].dropna().unique()) if "pool" in cols else [None]
    for ckpt in sorted(df["checkpoint"].unique()):
        for pool in pools:
            sel = df[df["checkpoint"] == ckpt]
            if pool is not None:
                sel = sel[sel["pool"] == pool]
            sel = sel[sel["_haz"].notna()]
            if sel.empty:
                continue
            pos = sel.loc[sel["_haz"] == 1, score_col].to_numpy(dtype=float)
            neg = sel.loc[sel["_haz"] == 0, score_col].to_numpy(dtype=float)
            if pos.size == 0 or neg.size == 0:
                continue
            rows.append({
                "checkpoint": ckpt, "pool": str(pool), "score_col": score_col,
                "n_pos": int(pos.size), "n_neg": int(neg.size),
                "auroc": S.auroc(pos, neg),
                "r1": S.tpr_at_fpr(pos, neg, 0.01, min_neg_for_estimability=MIN_NEG_1PCT),
                "r2": S.tpr_at_fpr(pos, neg, 0.05),
                "pos": pos, "neg": neg,
            })
    meta = {"status": "OK", "n_rows_csv": int(len(df)), "columns": cols,
            "score_col": score_col,
            "checkpoints": sorted(df["checkpoint"].unique().tolist()),
            "pools": [str(p) for p in pools]}
    del df
    gc.collect()
    return rows, meta


# --------------------------------------------------------------------------- #
# source (c): Lane C stored scalars
# --------------------------------------------------------------------------- #
def lane_c_stored(instrument_keys: tuple[str, ...] = (
        "rcontent_heldout_auroc", "rcontent_splithalf", "cos_rcontent_rrequest")) -> list[dict]:
    rows: list[dict] = []
    for f in sorted(P.C_PER_CKPT.glob("*.json")):
        try:
            obj = json.loads(f.read_text())
        except json.JSONDecodeError as exc:
            rows.append({"checkpoint": f.stem, "source_file": P.rel(f),
                         "error": repr(exc)})
            continue
        inst = obj.get("instrument", {}) if isinstance(obj, dict) else {}
        row = {"checkpoint": f.stem, "source_file": P.rel(f)}
        for k in instrument_keys:
            row[k] = inst.get(k)
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- #
# reconciliation against Lane B's STORED curves
# --------------------------------------------------------------------------- #
STORED_PROBE_LAYER = 22  # r_ablit_layer for L2; the lastp read site Lane B used


def deepest_lastp_layer(lineage: str, group: str, *, alpha: str = "0.00") -> int:
    """The deepest ``<group>|lastp|<layer>`` key this lineage actually harvested.

    The read site is NOT the same layer in every lineage -- Lane B's band_plus_pick
    follows each lineage's own r_ablit_layer -- so the layer is resolved from the
    archive rather than hard-coded, and the resolved value is printed in the row.
    """
    prefix = f"{group}|lastp|"
    layers = [int(k[len(prefix):]) for k in LB.key_to_part(lineage, alpha)
              if k.startswith(prefix) and k[len(prefix):].isdigit()]
    if not layers:
        raise KeyError(f"no {prefix}* keys in {lineage}_a{alpha}.part*.npz")
    return max(layers)


def reproduce_stored_lane_b(lineage: str, *, layer: int | None = None) -> dict:
    """Reproduce Lane B's own probe curves before any new number is believed.

    ``D_curve`` is the outcome that read 1.000 at every lesion strength and was
    reported as "the harm representation survives it ENTIRELY". It is computed
    on the CRUDE ``damage`` corpus (256 prompt-only forwards, harmful versus
    harmless). ``D_matched_probe_curve`` is the same probe on the MATCHED twin
    corpus. Reproducing both is what licenses the new operating-point numbers:
    a recomputed value that does not land near its stored counterpart is a
    pipeline bug, not a finding.
    """
    from sklearn.model_selection import StratifiedKFold

    stored = json.loads(P.B_ANALYSIS.read_text())["lineages"][lineage]
    m = LB.meta(lineage)
    resolved = layer if layer is not None else deepest_lastp_layer(lineage, "damage")

    def cv_auroc(x: np.ndarray, y: np.ndarray, *, folds: int = 5, seed: int = 0) -> float:
        skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
        s = np.empty(len(y), dtype=float)
        for tr, te in skf.split(x, y):
            scaler, clf = _fit_probe(x[tr], y[tr])
            s[te] = _score(scaler, clf, x[te])
            del scaler, clf
        return S.auroc(s[y == 1], s[y == 0])

    out: dict = {"lineage": lineage, "repo": m.repo,
                 "read_site": f"lastp|{resolved}",
                 "read_site_resolution": ("deepest lastp layer harvested for this "
                                          "lineage; r_ablit_layer is "
                                          f"{m.r_ablit_layer}"),
                 "source_file": P.rel(P.B_ANALYSIS)}
    for group, stored_key in (("damage", "D_curve"),
                              ("damage_matched", "D_matched_probe_curve")):
        y = np.array([r["label"] for r in LB.index(lineage)[group]], dtype=int)
        recomputed = []
        for alpha in m.alphas:
            lay = (resolved if layer is not None
                   else deepest_lastp_layer(lineage, group))
            x = LB.load_array(lineage, alpha, f"{group}|lastp|{lay}").astype(np.float32)
            recomputed.append(float(cv_auroc(x, y)))
            del x
            gc.collect()
        ref = [float(v) for v in stored.get(stored_key, [])]
        delta = ([abs(a - b) for a, b in zip(recomputed, ref)] if len(ref) == len(recomputed)
                 else [])
        out[group] = {
            "stored_key": stored_key,
            "stored": ref,
            "recomputed": [round(v, 4) for v in recomputed],
            "max_abs_delta": max(delta) if delta else float("nan"),
            "n": int(y.size),
            "n_pos": int(y.sum()),
            "n_neg": int((1 - y).sum()),
            "verdict": ("EXACT_MATCH" if delta and max(delta) < 1e-6
                        else "RECONCILED" if delta and max(delta) <= 0.02
                        else "MISMATCH" if delta else "NOT_IN_SOURCE"),
        }
    out["reconciliation_note"] = (
        "The headline 1.000 belongs to the CRUDE `damage` corpus (prompt-only "
        "harmful-versus-harmless), where the outcome is at its ceiling in the "
        "UNPERTURBED control and therefore cannot fall. On the MATCHED twin "
        "corpus the same probe already reads below ceiling. Neither corpus was "
        "reported with an operating-point statistic, which is what M1 adds."
    )
    return out


def stored_curves(lineage: str) -> dict:
    """The stored Lane B curves M2's ceiling audit needs, read once."""
    st = json.loads(P.B_ANALYSIS.read_text())["lineages"][lineage]
    keys = ("D_curve", "D_null", "D_target", "D_flat", "D_matched_probe_curve",
            "D_matched_axis_curve", "D_axis_1d_curve", "D_axis_1d_gap_normalised",
            "D_axis_1d_gap_expected_1_minus_alpha", "D_secondary_curve",
            "alpha_star", "alpha_star_source", "matched_damage_criterion_met",
            "r_content_split_half_cosine", "G1_cos_pooled", "G1_max", "G1_pass",
            "window", "band", "r_ablit_layer", "deviations")
    return {k: st.get(k) for k in keys}


# --------------------------------------------------------------------------- #
# the parent-child pairs M1 is asked to adjudicate
# --------------------------------------------------------------------------- #
LESION_PAIRS = [(a, "1.00") for a in ("0.00",)] + [("0.00", a) for a in ("0.25", "0.50", "0.75")]
LINEAGE_PAIRS = [
    ("L1", "L2", "base -> instruct (ordinary instruction tuning)"),
    ("L2", "L3", "instruct -> safety RL (safe-completion)"),
    ("L1", "L4", "base -> NON-safety fine-tune (load-bearing control)"),
]
CONFIRMATORY_PREFIX = "M1:"


def _row_from_arm(a: ArmResult, *, source: str) -> dict:
    ok = np.isfinite(a.scores)
    pos, neg = a.scores[ok & (a.y == 1)], a.scores[ok & (a.y == 0)]
    thr_sent, mde = S.power_sentence(
        (a.scores[ok & (a.y == 1)] > (np.quantile(neg, 0.99, method="higher")
                                      if neg.size else np.nan)).astype(float)
        - 0.0,
        label="TPR units")
    row = {
        "metric": "M1",
        "source": source,
        "checkpoint": f"{a.lineage} ({a.repo})",
        "lineage": a.lineage,
        "alpha": a.alpha,
        "window": a.window,
        "source_file": P.rel(P.B_HARVEST / f"{a.lineage}_a{a.alpha}.part*.npz"),
        "n_pos": int(pos.size),
        "n_neg": int(neg.size),
        "auroc_recomputed": round(a.auroc, 6),
        "tpr@1fpr": a.r1.fmt(),
        "tpr@1fpr_point": a.r1.tpr,
        "smallest_resolvable_step": a.r1.smallest_resolvable_step,
        "tpr@5fpr": a.r2.fmt(),
        "tpr@5fpr_point": a.r2.tpr,
        "power_sentence": thr_sent,
        "mde_80pct": mde,
        "READOUT_CLASS": "activation",
        "BASELINE_ONLY": False,
        "DESCRIPTIVE": True,
    }
    for k in BUDGETS:
        b = a.r3.get(k)
        row[f"auroc_k{k}"] = (f"{b['mean']:.4f} [{b['p5']:.4f}, {b['p95']:.4f}]"
                              if b and np.isfinite(b.get("mean", np.nan)) else "")
        row[f"auroc_k{k}_mean"] = b["mean"] if b else float("nan")
    return row


def run(*, lineages: tuple[str, ...] = ("L1", "L2", "L3", "L4"),
        do_budget: bool = True) -> tuple[list[dict], dict]:
    """Compute every M1 row and every M1 confirmatory test."""
    from .prereg import prereg_hash

    rows: list[dict] = []
    notes: dict = {
        "prereg_sha256": prereg_hash(),
        "readout_class": "activation",
        "equivalence_margin_tpr_units": MARGIN,
        "sanity_bounds": SANITY,
        "sources_used": [],
        "absent": [],
        "reconciliation": {},
        "confirmatory": {},
        "cuts_taken": [],
    }

    # ---- source (a) ------------------------------------------------------- #
    arms_by_key: dict[tuple[str, str, str], ArmResult] = {}
    for lineage in lineages:
        notes["reconciliation"][lineage] = reproduce_stored_lane_b(lineage)
        for arm in lane_b_arms(lineage, do_budget=do_budget):
            arms_by_key[(arm.lineage, arm.alpha, arm.window)] = arm
            rows.append(_row_from_arm(arm, source="(a) LANE_B per-item band activations"))
    notes["sources_used"].append(P.rel(P.B_HARVEST))

    # ---- R4: equivalence, lesion pairs ------------------------------------ #
    conf_p: dict[str, float] = {}
    windows_present = sorted({k[2] for k in arms_by_key})
    for lineage in lineages:
      for win in windows_present:
        for pa, pb in LESION_PAIRS:
            key = (lineage, pa, win)
            key2 = (lineage, pb, win)
            if key not in arms_by_key or key2 not in arms_by_key:
                continue
            d = paired_tpr_diff(arms_by_key[key], arms_by_key[key2])
            if d.size == 0:
                continue
            t = S.tost(d, MARGIN)
            sent, mde = S.power_sentence(d, label="TPR units")
            name = f"{CONFIRMATORY_PREFIX}lesion|{lineage}|{win}|a{pa}->a{pb}"
            from scipy import stats as sps
            p_two = float(sps.ttest_1samp(d, 0.0).pvalue) if d.std(ddof=1) > 0 else 1.0
            # only the PRIMARY window's rows are confirmatory; the companion
            # window is reported beside them and labelled DESCRIPTIVE
            if win == PRIMARY_WINDOW:
                conf_p[name] = p_two
            rows.append({
                "metric": "M1.R4",
                "source": "(a) LANE_B per-item band activations",
                "checkpoint": f"{lineage} lesion a={pa} -> a={pb} [{win}]",
                "lineage": lineage, "alpha": f"{pa}->{pb}", "window": win,
                "source_file": P.rel(P.B_HARVEST / f"{lineage}_a*.part*.npz"),
                "n_pos": int(d.size), "n_neg": arms_by_key[key].r1.n_neg,
                "delta_tpr@1fpr": round(float(d.mean()), 6),
                "equivalence_verdict": t.verdict,
                "equivalence_margin": MARGIN,
                "equivalence_margin_achieved": round(t.achieved_margin, 6),
                "p_tost": t.p_tost, "p_two_sided": p_two,
                "power_sentence": sent, "mde_80pct": mde,
                "READOUT_CLASS": "activation", "BASELINE_ONLY": False,
                "DESCRIPTIVE": win != PRIMARY_WINDOW,
            })

    # ---- R4: equivalence, lineage pairs ----------------------------------- #
    for parent, child, label in LINEAGE_PAIRS:
        kp, kc = (parent, "0.00", PRIMARY_WINDOW), (child, "0.00", PRIMARY_WINDOW)
        if kp not in arms_by_key or kc not in arms_by_key:
            continue
        d = paired_tpr_diff(arms_by_key[kp], arms_by_key[kc])
        if d.size == 0:
            continue
        t = S.tost(d, MARGIN)
        sent, mde = S.power_sentence(d, label="TPR units")
        name = f"{CONFIRMATORY_PREFIX}lineage|{parent}->{child}"
        from scipy import stats as sps
        p_two = float(sps.ttest_1samp(d, 0.0).pvalue) if d.std() > 0 else 1.0
        conf_p[name] = p_two
        rows.append({
            "metric": "M1.R4",
            "source": "(a) LANE_B per-item band activations",
            "checkpoint": f"{parent} -> {child}: {label}",
            "lineage": f"{parent}->{child}", "alpha": "0.00", "window": PRIMARY_WINDOW,
            "source_file": P.rel(P.B_HARVEST / "L*_a0.00.part*.npz"),
            "n_pos": int(d.size), "n_neg": arms_by_key[kp].r1.n_neg,
            "delta_tpr@1fpr": round(float(d.mean()), 6),
            "equivalence_verdict": t.verdict,
            "equivalence_margin": MARGIN,
            "equivalence_margin_achieved": round(t.achieved_margin, 6),
            "p_tost": t.p_tost, "p_two_sided": p_two,
            "power_sentence": sent, "mde_80pct": mde,
            "READOUT_CLASS": "activation", "BASELINE_ONLY": False,
            "DESCRIPTIVE": False,
        })

    notes["primary_window"] = {
        "window": PRIMARY_WINDOW,
        "why": ("LATE is the RESPONSE-site window, which is where an EXECUTION "
                "account predicts the lesion should bite. Lane B's own registered "
                "read window is EARLY, so BOTH are computed and reported; only the "
                "primary window's rows enter the Holm family, and the companion "
                "window is labelled DESCRIPTIVE."),
        "windows_computed": windows_present,
    }
    notes["confirmatory"]["holm"] = S.holm(conf_p)
    notes["confirmatory"]["n_confirmatory_rows"] = len(conf_p)

    # ---- source (b) ------------------------------------------------------- #
    b_rows, b_meta = lane_a_rows()
    notes["lane_a_meta"] = b_meta
    if b_meta.get("status") == "OK":
        notes["sources_used"].append(P.rel(P.A_PER_ITEM_CELLS))
        for r in b_rows:
            sent, mde = S.power_sentence(
                (r["pos"] > np.quantile(r["neg"], 0.99, method="higher")).astype(float),
                label="TPR units")
            rows.append({
                "metric": "M1",
                "source": "(b) LANE_A per-item cell projections",
                "checkpoint": r["checkpoint"], "lineage": "", "alpha": "",
                "window": r["pool"],
                "source_file": P.rel(P.A_PER_ITEM_CELLS),
                "n_pos": r["n_pos"], "n_neg": r["n_neg"],
                "auroc_recomputed": round(r["auroc"], 6),
                "tpr@1fpr": r["r1"].fmt(), "tpr@1fpr_point": r["r1"].tpr,
                "smallest_resolvable_step": r["r1"].smallest_resolvable_step,
                "tpr@5fpr": r["r2"].fmt(), "tpr@5fpr_point": r["r2"].tpr,
                "power_sentence": sent, "mde_80pct": mde,
                "READOUT_CLASS": "activation", "BASELINE_ONLY": False,
                "DESCRIPTIVE": True,
            })
    else:
        notes["absent"].append({"quantity": "LANE_A per-item cell projections",
                                "glob": b_meta.get("glob", P.rel(P.A_PER_ITEM_CELLS)),
                                "status": b_meta.get("status")})

    # ---- source (c) ------------------------------------------------------- #
    c_rows = lane_c_stored()
    if c_rows:
        notes["sources_used"].append(P.rel(P.C_PER_CKPT / "*.json"))
    for r in c_rows:
        rows.append({
            "metric": "M1",
            "source": "(c) LANE_C stored scalars",
            "checkpoint": r["checkpoint"], "lineage": "", "alpha": "", "window": "",
            "source_file": r["source_file"],
            "auroc_stored": r.get("rcontent_heldout_auroc"),
            "splithalf_stored": r.get("rcontent_splithalf"),
            "cos_rcontent_rrequest_stored": r.get("cos_rcontent_rrequest"),
            "tpr@1fpr": "NOT_RECOVERABLE_FROM_A_STORED_AUROC",
            "power_sentence": ("no operating-point statistic can be recovered from a "
                               "stored AUROC; this row is reported AS STORED"),
            "READOUT_CLASS": "activation", "BASELINE_ONLY": False,
            "DESCRIPTIVE": True,
        })
    notes["lane_c_stored_only"] = (
        "Lane C supplies pre-reduced scalars. No operating point, no restricted "
        "budget and no equivalence verdict is computable from a stored AUROC, so "
        "these rows are reported as stored and carry no R1/R3/R4."
    )
    return rows, notes
