#!/usr/bin/env python3
"""Adjudicate the focus/+25 pairing against the plan's max-Jaccard fallback.

The plan sets a median-Jaccard >= 0.5 guard. XSTest prompts are short (median
~9 tokens), so a genuine 5-token minimal edit lands well below 0.5 by
construction. This script runs the prescribed fallback (Hungarian assignment
on 1 - Jaccard, within family) and reports whether it actually moves any pair.
"""
from __future__ import annotations

import json
import re
import statistics as st
import sys
from pathlib import Path

import numpy as np
from loguru import logger
from scipy.optimize import linear_sum_assignment

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/pairing_diagnostic.log", rotation="10 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
_TOKEN_RE = re.compile(r"[a-z0-9']+")


def toks(s: str) -> list[str]:
    return _TOKEN_RE.findall(s.lower())


def jac(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


@logger.catch(reraise=True)
def main() -> None:
    d = json.loads((ROOT / "results/twin_pairs.json").read_text())
    pairs = d["pairs"]
    fams = d["twin_families_kept"]

    lens = [p["n_tokens_benign_prompt"] for p in pairs] + [p["n_tokens_harmful_prompt"] for p in pairs]
    logger.info(f"prompt length (tokens): median={st.median(lens)} mean={st.mean(lens):.1f} min={min(lens)} max={max(lens)}")

    # normalised edit distance: Levenshtein / max(len)
    norm = [p["levenshtein_twin"] / max(p["n_tokens_benign_prompt"], p["n_tokens_harmful_prompt"]) for p in pairs]
    logger.info(f"normalised token edit distance: median={st.median(norm):.3f} mean={st.mean(norm):.3f}")

    n_moved_total = 0
    per_fam = {}
    for fam in fams:
        fp = [p for p in pairs if p["family"] == fam]
        b = [toks(p["benign_prompt"]) for p in fp]
        h = [toks(p["harmful_prompt"]) for p in fp]
        n = len(fp)
        cost = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                cost[i, j] = 1.0 - jac(b[i], h[j])
        ri, ci = linear_sum_assignment(cost)
        moved = int(sum(1 for i, j in zip(ri, ci) if i != j))
        n_moved_total += moved
        cur_med = st.median([p["jaccard_twin"] for p in fp])
        alt_med = st.median([1.0 - cost[i, j] for i, j in zip(ri, ci)])
        per_fam[fam] = {
            "n": n,
            "n_pairs_max_jaccard_would_move": moved,
            "median_jaccard_focus_pairing": round(cur_med, 4),
            "median_jaccard_max_jaccard_pairing": round(float(alt_med), 4),
        }
        logger.info(f"{fam:22s} n={n} max-Jaccard would move {moved:2d} pairs | median J focus={cur_med:.3f} vs maxJ={alt_med:.3f}")

    verdict = (
        "KEEP_FOCUS_PAIRING" if n_moved_total <= 2 else "SWITCH_TO_MAX_JACCARD"
    )
    logger.info(f"TOTAL pairs the fallback would move: {n_moved_total}/150  ->  VERDICT {verdict}")

    out = {
        "guard": "plan criterion: median token Jaccard >= 0.5 across the 150 pairs",
        "observed_median_jaccard": d["pairing"]["median_jaccard"],
        "guard_tripped": True,
        "why_the_guard_is_miscalibrated_here": (
            f"XSTest prompts are short (median {st.median(lens)} tokens). A genuine minimal edit of "
            f"{d['pairing']['median_levenshtein']} tokens on a ~{st.median(lens)}-token prompt cannot reach Jaccard 0.5 "
            "arithmetically. Jaccard is the wrong scale-free statistic at this prompt length; the normalised "
            f"token edit distance (median {st.median(norm):.3f}) is the informative one."
        ),
        "independent_evidence_the_pairing_is_correct": {
            "focus_and_+25_offset_agree": d["pairing"]["n_focus_and_positional_agree"],
            "of": len(pairs),
            "disagreements": d["pairing"]["notes"],
        },
        "prescribed_fallback_run": "scipy.optimize.linear_sum_assignment on (1 - Jaccard) within each family",
        "n_pairs_fallback_would_move": n_moved_total,
        "per_family": per_fam,
        "verdict": verdict,
        "decision": (
            "The fallback was RUN as the plan requires. It re-assigns "
            f"{n_moved_total}/150 pairs, i.e. it reproduces the focus/+25 pairing almost exactly, so the pairing is "
            "not the problem -- the 0.5 threshold is. The focus/+25 pairing is RETAINED and the per-pair Jaccard and "
            "Levenshtein columns ship so downstream can condition on them. This deviation is recorded in prereg.json."
        )
        if verdict == "KEEP_FOCUS_PAIRING"
        else "Switch to max-Jaccard pairing.",
        "normalised_edit_distance": {
            "median": round(st.median(norm), 4),
            "mean": round(st.mean(norm), 4),
        },
        "prompt_token_length": {"median": st.median(lens), "mean": round(st.mean(lens), 2), "min": min(lens), "max": max(lens)},
    }
    (ROOT / "results/pairing_diagnostic.json").write_text(json.dumps(out, indent=2))
    logger.info("wrote results/pairing_diagnostic.json")


if __name__ == "__main__":
    main()
