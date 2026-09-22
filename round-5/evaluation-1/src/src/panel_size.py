"""D7(d). Required panel size by Monte-Carlo permutation.

The commission asked for a metric readable from 0-to-few prompts on an arbitrary
checkpoint. At n=10 the permutation critical |rho| is large enough that no
candidate can beat the logit baseline. This module solves for the n at which the
critical value falls below the observed effect, which converts that failure into
actionable guidance about the panel size the field would need.

Vectorised: the null distribution of Spearman rho depends only on n, so we
permute rank vectors directly (exact for untied data).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import numpy as np

SEED = 20260921


def crit_rho_curve(ns: Sequence[int], n_perm: int = 20000,
                   alpha: float = 0.05) -> dict[int, float]:
    """Two-sided critical |Spearman rho| for each n, by permutation."""
    out: dict[int, float] = {}
    for n in ns:
        g = np.random.default_rng(SEED + int(n))
        base = np.arange(1, n + 1, dtype=float)
        bc = base - base.mean()
        denom = float(np.sum(bc**2))
        # (n_perm, n) matrix of independent permutations
        perms = np.argsort(g.random((n_perm, n)), axis=1).astype(float) + 1.0
        pc = perms - perms.mean(axis=1, keepdims=True)
        rhos = (pc @ bc) / denom
        out[int(n)] = float(np.percentile(np.abs(rhos), 100 * (1 - alpha)))
    return out


def power_mde(n: int, crit: float, n_sim: int = 4000, power: float = 0.80,
              grid: Sequence[float] | None = None) -> float | None:
    """Smallest true |rho| detectable with `power` at sample size n.

    Simulates bivariate-normal data at each candidate rho, ranks it, and asks how
    often |Spearman rho| exceeds the permutation critical value.
    """
    if grid is None:
        grid = np.round(np.arange(0.30, 0.996, 0.02), 3)
    g = np.random.default_rng(SEED + 7919 + n)
    base = np.arange(1, n + 1, dtype=float)
    bc = base - base.mean()
    denom = float(np.sum(bc**2))
    for r in grid:
        z1 = g.standard_normal((n_sim, n))
        z2 = g.standard_normal((n_sim, n))
        y = r * z1 + np.sqrt(max(0.0, 1 - r * r)) * z2
        rx = np.argsort(np.argsort(z1, axis=1), axis=1).astype(float) + 1.0
        ry = np.argsort(np.argsort(y, axis=1), axis=1).astype(float) + 1.0
        rxc = rx - rx.mean(axis=1, keepdims=True)
        ryc = ry - ry.mean(axis=1, keepdims=True)
        rho = np.sum(rxc * ryc, axis=1) / denom
        if float(np.mean(np.abs(rho) >= crit)) >= power:
            return float(r)
    return None


def solve(targets: dict[str, float | None], grid: Sequence[int],
          n_perm: int = 20000) -> dict[str, Any]:
    crit = crit_rho_curve(grid, n_perm=n_perm)
    answers: dict[str, Any] = {}
    for label, target in targets.items():
        if target is None:
            answers[label] = {"target_abs": None, "required_n": None,
                              "note": "target UNAVAILABLE from disk"}
            continue
        t = abs(float(target))
        hit = next((n for n in sorted(crit) if crit[n] < t), None)
        answers[label] = {
            "target_abs": t,
            "required_n": hit,
            "note": (f"permutation critical |rho| falls below {t:.3f} at n={hit}"
                     if hit is not None else
                     f"no n up to {max(crit)} on the grid reaches critical |rho| < {t:.3f}"),
        }
    return {"critical_rho_by_n": crit, "n_perm": n_perm, "alpha": 0.05,
            "answers": answers}


if __name__ == "__main__":
    grid = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80]
    crit = crit_rho_curve(grid)
    mde10 = power_mde(10, crit[10])
    out = {"critical_rho_by_n": crit, "mde80_at_n10": mde10,
           "n_perm": 20000, "seed": SEED}
    Path("results").mkdir(exist_ok=True)
    Path("results/panel_size_curve.json").write_text(json.dumps(out, indent=2))
    print("crit n=10:", round(crit[10], 4), " MDE80 at n=10:", mde10)
    print({n: round(v, 3) for n, v in crit.items()})
