#!/usr/bin/env python3
"""Source-agnostic machinery for the HARD RECOGNITION SET: normalisation, exact and
near-duplicate removal, the seeded fit/screen/sealed_holdout split, the TF-IDF text
proxy gate, and the sizing statement.  All rules are the ones frozen in prereg.json
(sha256 b3849ae0...); this module implements them, it does not choose them.
"""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion, Pipeline

SEED = "iter2/run_YqmEFECOIR3D/gen_art_dataset_1/v1"


def norm_text(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s


def phash(s: str) -> str:
    return hashlib.sha256(norm_text(s).encode()).hexdigest()[:32]


def shingles(s: str, n: int = 5) -> set[str]:
    w = norm_text(s).split()
    if len(w) < n:
        return {" ".join(w)} if w else set()
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def dedup(rows: list[dict], text_key: str = "input", jaccard: float = 0.8) -> tuple[list[dict], dict]:
    """Exact-normalised dedup, then word 5-gram Jaccard >= `jaccard` near-dup removal.

    Rows are consumed in the order given (the caller fixes the source priority), so the
    FIRST occurrence of a duplicate group survives.  Near-dup candidates are found via a
    shingle inverted index, so this is linear-ish rather than O(n^2).
    """
    kept: list[dict] = []
    seen_exact: dict[str, int] = {}
    index: dict[str, list[int]] = {}
    kept_shingles: list[set[str]] = []
    n_exact = n_near = 0
    near_examples: list[dict] = []
    for r in rows:
        h = phash(r[text_key])
        if h in seen_exact:
            n_exact += 1
            continue
        sh = shingles(r[text_key])
        cand: dict[int, int] = {}
        for g in sh:
            for j in index.get(g, ()):
                cand[j] = cand.get(j, 0) + 1
        dup_of = None
        for j, ov in sorted(cand.items(), key=lambda kv: -kv[1]):
            other = kept_shingles[j]
            union = len(sh | other)
            if union and ov / union >= jaccard:
                dup_of = j
                break
        if dup_of is not None:
            n_near += 1
            if len(near_examples) < 25:
                near_examples.append({"dropped": r[text_key][:160],
                                      "kept": kept[dup_of][text_key][:160]})
            continue
        seen_exact[h] = len(kept)
        idx = len(kept)
        for g in sh:
            index.setdefault(g, []).append(idx)
        kept_shingles.append(sh)
        kept.append(r)
    return kept, {"n_in": len(rows), "n_out": len(kept), "n_exact_removed": n_exact,
                  "n_near_removed": n_near, "jaccard_threshold": jaccard,
                  "near_dup_examples": near_examples}


def assign_split(row_id: str) -> str:
    h = hashlib.sha256(f"{SEED}|split|{row_id}".encode()).hexdigest()
    u = int(h[:16], 16) / 2 ** 64
    return "fit" if u < 0.30 else ("screen" if u < 0.80 else "sealed_holdout")


def metadata_fold(row_id: str) -> str:
    return assign_split(row_id)


def _proxy_pipeline() -> Pipeline:
    return Pipeline([
        ("feats", FeatureUnion([
            ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2,
                                     sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2,
                                     sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(C=1.0, solver="liblinear", max_iter=2000)),
    ])


def proxy_auroc(texts: Sequence[str], labels: Sequence[int], n_splits: int = 5,
                seed: int = 0) -> dict:
    """5-fold stratified CV AUROC of a pure-text TF-IDF + logistic-regression proxy.

    This is a TEXTUAL proxy.  The activation-level headroom check belongs to the
    experiment lanes, not here.
    """
    y = np.asarray(labels)
    X = list(texts)
    if len(set(y.tolist())) < 2 or min(np.bincount(y)) < n_splits:
        return {"auroc": None, "n": len(X), "reason": "insufficient rows or one class only"}
    oof = np.zeros(len(X))
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for tr, te in skf.split(X, y):
        pipe = _proxy_pipeline()
        pipe.fit([X[i] for i in tr], y[tr])
        oof[te] = pipe.predict_proba([X[i] for i in te])[:, 1]
    auc = float(roc_auc_score(y, oof))
    full = _proxy_pipeline().fit(X, y)
    names = full.named_steps["feats"].get_feature_names_out()
    coef = full.named_steps["clf"].coef_[0]
    order = np.argsort(-np.abs(coef))[:20]
    top = [{"feature": str(names[i]), "coef": round(float(coef[i]), 4)} for i in order]
    return {"auroc": round(auc, 4), "n": len(X), "n_positive": int(y.sum()),
            "top20_features": top, "oof_scores": oof.tolist()}


def sizing_statement(n_benign: int, n_harmful: int) -> dict:
    above = max(1, int(round(0.01 * n_benign)))
    return {
        "n_benign": n_benign,
        "n_harmful": n_harmful,
        "fpr_grid_resolution": round(1.0 / n_benign, 6) if n_benign else None,
        "smallest_resolvable_tpr_step": round(1.0 / n_harmful, 6) if n_harmful else None,
        "n_benign_above_1pct_fpr_threshold": above,
        "note": (f"TPR@1%FPR at this size is an ORDER STATISTIC - the threshold is set by the "
                 f"{above}-th highest benign score out of {n_benign} - and must be reported with "
                 f"a bootstrap interval over BOTH classes, never as a point estimate."),
    }
