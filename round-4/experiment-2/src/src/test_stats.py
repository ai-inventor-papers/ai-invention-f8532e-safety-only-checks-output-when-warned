"""Self-test for stats.py. Run: cd WS && .venv/bin/python src/test_stats.py"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stats  # noqa: E402


def check(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(f"FAILED: {msg}")
    print(f"ok: {msg}")


# ---------------------------------------------------------------------------
# (a) paired_effect
# ---------------------------------------------------------------------------

rng = np.random.default_rng(12345)
n = 48
y_b = rng.normal(size=n)
y_a = y_b + 0.5 + rng.normal(scale=1.0, size=n)
res = stats.paired_effect(y_a, y_b, seed=0)
check(abs(res["effect"] - 0.5) < 0.35, f"paired_effect effect ~0.5 (got {res['effect']:.3f})")
check(res["ci_lo"] > 0.0, f"paired_effect CI excludes 0 (lo={res['ci_lo']:.3f})")
check(res["p_signflip"] < 0.01, f"paired_effect p_signflip < 0.01 (got {res['p_signflip']:.4f})")
check(res["n"] == n, "paired_effect n matches")
check(np.isfinite(res["sd_diff"]) and np.isfinite(res["mde_80"]), "paired_effect sd_diff/mde_80 finite")

# pure noise: false-positive rate should be low over 20 seeds
false_pos = 0
for s in range(20):
    r = np.random.default_rng(1000 + s)
    a = r.normal(size=48)
    b = r.normal(size=48)
    out = stats.paired_effect(a, b, seed=s)
    if out["p_signflip"] <= 0.05:
        false_pos += 1
check(false_pos <= 3, f"paired_effect false-positive rate <=0.15 over 20 seeds (got {false_pos}/20)")

# binary 0/1 inputs
rb = np.random.default_rng(7)
y_a_bin = rb.integers(0, 2, size=30).astype(float)
y_b_bin = rb.integers(0, 2, size=30).astype(float)
out_bin = stats.paired_effect(y_a_bin, y_b_bin, seed=0)
check(out_bin["n"] == 30 and np.isfinite(out_bin["effect"]), "paired_effect works on binary 0/1 inputs")

# y_b_draws path with NaNs
rk = np.random.default_rng(3)
n2 = 20
y_a2 = rk.normal(size=n2)
draws = rk.normal(size=(5, n2))
draws[:, 0] = np.nan  # item 0 fully missing -> dropped
draws[0, 1] = np.nan  # item 1 partially missing -> still usable via nanmean
out_draws = stats.paired_effect(y_a2, y_b_draws=draws, seed=0)
check(out_draws["n"] == n2 - 1, f"paired_effect y_b_draws drops fully-NaN item (n={out_draws['n']})")
check(np.isfinite(out_draws["effect"]), "paired_effect y_b_draws effect finite")

# ---------------------------------------------------------------------------
# (b) holm
# ---------------------------------------------------------------------------

pvals = [0.01, 0.04, 0.03, 0.005]
expected = [0.03, 0.06, 0.06, 0.02]
got = stats.holm(pvals)
check(all(abs(g - e) < 1e-12 for g, e in zip(got, expected)), f"holm matches hand example (got {got})")

# NaN-safety
pvals_nan = [0.01, float("nan"), 0.03, 0.005]
got_nan = stats.holm(pvals_nan)
check(np.isnan(got_nan[1]), "holm keeps NaN in place")
check(all(np.isfinite(g) for i, g in enumerate(got_nan) if i != 1), "holm finite for non-NaN entries")

# holm_ci_level sanity: level for smallest p in family of m=4 should be 0.05/4
levels = stats.holm_ci_level(pvals)
smallest_idx = int(np.argmin(pvals))
check(abs(levels[smallest_idx] - 0.05 / 4) < 1e-12, f"holm_ci_level smallest-p level = alpha/m (got {levels[smallest_idx]})")

# bootstrap_ci_at basic sanity
diff = rng.normal(loc=1.0, size=100)
lo, hi = stats.bootstrap_ci_at(diff, 0.05, B=2000, seed=0)
check(lo < 1.0 < hi, f"bootstrap_ci_at CI brackets true mean region (lo={lo:.3f}, hi={hi:.3f})")

# ---------------------------------------------------------------------------
# (c) auroc
# ---------------------------------------------------------------------------

check(stats.auroc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0, "auroc perfectly separated = 1.0")
check(stats.auroc([1, 2, 3, 4], [1, 1, 0, 0]) == 0.0, "auroc reversed = 0.0")
check(stats.auroc([1, 1, 2, 2], [0, 1, 0, 1]) == 0.5, "auroc with ties = 0.5")

try:
    from sklearn.metrics import roc_auc_score

    rr = np.random.default_rng(99)
    for _ in range(10):
        nn = rr.integers(20, 80)
        sc = rr.normal(size=nn)
        lb = rr.integers(0, 2, size=nn)
        if lb.sum() == 0 or lb.sum() == nn:
            continue
        mine = stats.auroc(sc, lb)
        theirs = roc_auc_score(lb, sc)
        check(abs(mine - theirs) < 1e-12, f"auroc matches sklearn to 1e-12 (mine={mine}, theirs={theirs})")
except ImportError:
    print("skip: sklearn not installed, skipping cross-check")

ci = stats.auroc_ci([1, 2, 3, 4, 5, 6], [0, 0, 0, 1, 1, 1], B=500, seed=0)
check(ci["auroc"] == 1.0 and ci["n_pos"] == 3 and ci["n_neg"] == 3, "auroc_ci basic sanity")

# ---------------------------------------------------------------------------
# (d) cohens_d
# ---------------------------------------------------------------------------

a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
b = np.array([2.0, 3.0, 4.0, 5.0, 6.0])
va = a.var(ddof=1)
vb = b.var(ddof=1)
pooled = np.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb) / (len(a) + len(b) - 2))
manual_d = (a.mean() - b.mean()) / pooled
got_d = stats.cohens_d(a, b)
check(abs(got_d - manual_d) < 1e-12, f"cohens_d matches manual computation ({got_d} vs {manual_d})")
check(np.isnan(stats.cohens_d([1.0], [1.0, 2.0])), "cohens_d NaN when a group has <2 items")

dz = stats.d_z(np.concatenate([a, b]), np.array([1, 1, 1, 1, 1, 0, 0, 0, 0, 0]), n_shuffle=200, seed=0)
check(np.isfinite(dz["d"]) and np.isfinite(dz["null_sd"]) and np.isfinite(dz["z"]), "d_z returns finite d/null_sd/z")

# ---------------------------------------------------------------------------
# (e) empirical_p
# ---------------------------------------------------------------------------

p = stats.empirical_p(1.0, [0.0, 0.5, 2.0])
check(abs(p - 0.5) < 1e-12, f"empirical_p example ({p})")

# ---------------------------------------------------------------------------
# (f) did_paired
# ---------------------------------------------------------------------------

same = rng.normal(size=40)
did_res = stats.did_paired(same, same, seed=0)
check(did_res["did"] == 0.0, "did_paired identical arrays -> did=0")
check(did_res["p_signflip"] == 1.0, "did_paired identical arrays -> p_signflip=1")
check(did_res["ci_lo"] == 0.0 and did_res["ci_hi"] == 0.0, "did_paired identical arrays -> CI degenerate at 0")

# ---------------------------------------------------------------------------
# (g) rate_ci (Wilson)
# ---------------------------------------------------------------------------

lo_w, hi_w = stats.rate_ci(0, 48)
check(abs(lo_w) < 1e-9, f"wilson(0,48) lower ~ 0 (got {lo_w})")
check(hi_w > 0.0, "wilson(0,48) upper > 0")

# newcombe_diff_ci sanity
nlo, nhi = stats.newcombe_diff_ci(10, 20, 10, 20)
check(abs(nlo - (-nhi)) < 1e-9, "newcombe_diff_ci symmetric for equal proportions")

# ---------------------------------------------------------------------------
# extra: mean_ci, mcnemar_exact
# ---------------------------------------------------------------------------

mc = stats.mean_ci(np.array([1.0, 2.0, np.nan, 3.0]), B=1000, seed=0)
check(mc["n"] == 3 and abs(mc["mean"] - 2.0) < 1e-12, "mean_ci drops NaN and computes mean")

p_mcnemar_sym = stats.mcnemar_exact(5, 5)
check(abs(p_mcnemar_sym - 1.0) < 1e-9, f"mcnemar_exact symmetric -> p=1 (got {p_mcnemar_sym})")
p_mcnemar_asym = stats.mcnemar_exact(0, 10)
check(p_mcnemar_asym < 0.01, f"mcnemar_exact very asymmetric -> small p (got {p_mcnemar_asym})")

print("\nALL STATS TESTS PASSED")
