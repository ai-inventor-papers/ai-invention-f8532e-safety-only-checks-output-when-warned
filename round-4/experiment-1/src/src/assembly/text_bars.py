"""FINAL-ASSEMBLY helper (method.py only): text bars (required change 3).

greedy_refusal_rate / greedy_refusal_rate_onset pair deltas from results/text_baseline.json, on HARM
items, child minus parent, paired item bootstrap (B=2000, numpy default_rng(20260921 + stable hash of
pair_id)), 95% percentile CI. Expected sign vs HC = -1. Readout class = 'text (generations; shares
generations with the truth)'. Only pairs whose parent AND child tags both appear in
text_baseline['per_tag'] get a row; other pairs get no row here (their absence is the NOT_AVAILABLE
status -- aggregate() already treats a missing (pair, candidate) as simply not-scored, never imputed).
"""
from __future__ import annotations

import hashlib

import numpy as np

B = 2000
BASE_SEED = 20260921
EXPECTED_SIGN_VS_HC = -1
READOUT_CLASS_TEXT = "text (generations; shares generations with the truth)"
CANDIDATES = (("greedy_refusal_rate", "harm"), ("greedy_refusal_rate_onset", "harm_onset"))


def _stable_hash(s: str) -> int:
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)


def text_bar_rows(pairs: list[dict], text_baseline: dict | None) -> list[dict]:
    if not text_baseline:
        return []
    per_tag = text_baseline.get("per_tag", {})
    rows: list[dict] = []
    for p in pairs:
        pid, ptag, ctag = p.get("pair_id"), p.get("parent"), p.get("child")
        if ptag not in per_tag or ctag not in per_tag:
            continue
        prec, crec = per_tag[ptag], per_tag[ctag]
        for cand, key in CANDIDATES:
            pd, cd = prec.get(key) or {}, crec.get(key) or {}
            items = sorted(set(pd) & set(cd))
            if not items:
                continue
            pv = np.array([pd[i] for i in items], dtype=float)
            cv = np.array([cd[i] for i in items], dtype=float)
            d = cv - pv
            delta_full = float(d.mean())
            rng = np.random.default_rng(BASE_SEED + _stable_hash(pid))
            idx = rng.integers(0, len(items), size=(B, len(items)))
            boot = d[idx].mean(axis=1)
            ci_lo, ci_hi = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))
            se = float(boot.std(ddof=1)) if boot.size > 1 else None
            rows.append({
                "candidate": cand, "candidate_raw": cand, "pair_id": pid,
                "delta": delta_full, "ci_lo": ci_lo, "ci_hi": ci_hi,
                "ci_excludes_0": bool(ci_lo > 0 or ci_hi < 0), "ci_excludes_0_raw": bool(ci_lo > 0 or ci_hi < 0),
                "se_boot": se, "mde": (1.96 + 0.84) * se if se is not None else None,
                "abs_delta_over_nullsd_parent": None, "abs_delta_over_nullsd_child": None,
                "signed_units_parent": None,
                "observed_sign": int(np.sign(delta_full)) if delta_full != 0 else 0,
                "expected_sign_vs_HC": EXPECTED_SIGN_VS_HC,
                "parent_value": float(pv.mean()) if pv.size else None, "child_value": float(cv.mean()) if cv.size else None,
                "n_valid_draws": B,
                "note": f"text bar (paired item bootstrap, B={B}, seed={BASE_SEED}+hash(pair_id)): "
                        f"{len(items)} HARM items shared by text_baseline per_tag[{ptag}] and [{ctag}]",
                "ams_verified": None, "ams_alarm": None, "ams_mean_direction_similarity": None,
            })
    return rows
