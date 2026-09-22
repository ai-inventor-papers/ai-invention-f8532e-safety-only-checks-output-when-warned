"""T1 -- ARITHMETIC UNIT TESTS, before any model is loaded (seconds, pure numpy).

Every identity here is load-bearing for design decisions D1/D2: if one fails, the whole
offline-scoring architecture is invalid and the numbers it produces are uninterpretable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import RESULTS, jdump, setup_logging  # noqa: E402
from numerics import (  # noqa: E402
    auroc,
    rmsnorm_jacobian_apply,
    sigma_mp_analytic,
    tpr_at_fpr,
    unit,
    write_mass,
    write_mass_many,
)
from loguru import logger  # noqa: E402


def t1a_x2_normalisation(rng) -> dict:
    """mean over random unit u of d*(u^T M M^T u)/||M||_F^2 must be 1.00 +/- 0.05."""
    d, n = 256, 1024
    M = rng.standard_normal((d, n)).astype(np.float64)
    G = M @ M.T
    fro2 = float((M**2).sum())
    U = unit(rng.standard_normal((1000, d)), axis=1)
    vals = write_mass_many(G, fro2, U, d)
    m = float(vals.mean())
    ok = abs(m - 1.0) <= 0.05
    return {"name": "T1a_X2_normalisation", "mean": m, "sd": float(vals.std()),
            "tolerance": 0.05, "pass": bool(ok)}


def t1b_gram_identities(rng) -> dict:
    """sigma_min(M)^2 == lambda_min(M M^T) and ||u^T M||^2 == u^T G u."""
    d, n = 96, 240
    M = rng.standard_normal((d, n)).astype(np.float64)
    G = M @ M.T
    sv = np.linalg.svd(M, compute_uv=False)
    ev = np.linalg.eigvalsh(G)
    rel_sigma = abs(sv[-1] ** 2 - ev[0]) / max(abs(ev[0]), 1e-12)
    u = unit(rng.standard_normal(d))
    lhs = float(((u @ M) ** 2).sum())
    rhs = float(u @ (G @ u))
    rel_quad = abs(lhs - rhs) / max(abs(lhs), 1e-12)
    # and the full spectrum, since we recover svals from eigh(G) in the harvest
    rel_spec = float(np.max(np.abs(np.sqrt(np.maximum(ev[::-1], 0)) - sv) / np.maximum(sv, 1e-12)))
    ok = (rel_sigma < 1e-4) and (rel_quad < 1e-6) and (rel_spec < 1e-4)
    return {"name": "T1b_gram_identities", "rel_sigma_min": float(rel_sigma),
            "rel_quadratic_form": float(rel_quad), "rel_full_spectrum": rel_spec,
            "pass": bool(ok)}


def t1c_x3_closed_form(rng) -> dict:
    """dot(mu_U, Ju) and (Ju)^T S_U (Ju)/V must reproduce mean(delta) and E[delta^2]."""
    V, d = 5000, 128
    WU = rng.standard_normal((V, d)).astype(np.float64) * 0.05
    Ju = rng.standard_normal(d)
    delta = WU @ Ju
    mu_U = WU.mean(0)
    S_U = WU.T @ WU
    m_hat = float(mu_U @ Ju)
    e2_hat = float(Ju @ (S_U @ Ju)) / V
    rel_m = abs(m_hat - float(delta.mean())) / max(abs(float(delta.mean())), 1e-9)
    rel_e2 = abs(e2_hat - float((delta**2).mean())) / max(abs(float((delta**2).mean())), 1e-9)
    ok = rel_m < 1e-5 and rel_e2 < 1e-5
    return {"name": "T1c_X3_closed_form", "rel_mean": float(rel_m),
            "rel_second_moment": float(rel_e2), "pass": bool(ok)}


def t1d_rmsnorm_jacobian(rng) -> dict:
    """Finite-difference check of the RMSNorm Jacobian at eps_step = 1e-3."""
    d = 64
    h = rng.standard_normal(d) * 2.0
    u = unit(rng.standard_normal(d))
    gamma = rng.uniform(0.5, 1.5, size=d)
    rms_eps = 1e-6

    def f(x):
        return gamma * x / np.sqrt(np.mean(x * x) + rms_eps)

    step = 1e-3
    fd = (f(h + step * u) - f(h)) / step
    an = rmsnorm_jacobian_apply(h, u, gamma, rms_eps)
    err = float(np.max(np.abs(fd - an)) / max(float(np.max(np.abs(an))), 1e-12))
    return {"name": "T1d_rmsnorm_jacobian", "max_rel_err": err, "tolerance": 1e-3,
            "pass": bool(err < 1e-3)}


def t1e_marchenko_pastur(rng) -> dict:
    """Analytic sigma_MP within 10% of the empirical sigma_min over 3 Gaussian draws
    at the panel's real shape."""
    out = []
    for (d, n) in [(2560, 13824), (1024, 5504), (2048, 8192)]:
        emp = []
        for _ in range(3):
            # scale so ||M||_F^2 == d*n (the analytic formula is norm-matched)
            M = rng.standard_normal((d, n)).astype(np.float32)
            fro2 = float((M.astype(np.float64) ** 2).sum())
            G = (M @ M.T).astype(np.float64)
            ev = np.linalg.eigvalsh(G)
            emp.append(float(np.sqrt(max(ev[0], 0.0))))
            del M, G
        an = sigma_mp_analytic(fro2, d, n)
        med = float(np.median(emp))
        rel = abs(an - med) / max(med, 1e-12)
        out.append({"shape": [d, n], "analytic": an, "empirical_median": med, "rel_err": rel,
                    "within_10pct": bool(rel < 0.10)})
    return {"name": "T1e_marchenko_pastur", "cases": out,
            "pass": bool(all(c["within_10pct"] for c in out))}


def t1f_auroc_tpr(rng) -> dict:
    """AUROC/TPR sanity: perfect separation -> 1.0; identical distributions -> ~0.5."""
    y = np.r_[np.ones(200), np.zeros(200)].astype(int)
    perfect = np.r_[rng.normal(10, 0.1, 200), rng.normal(0, 0.1, 200)]
    noise = rng.normal(0, 1, 400)
    a1, a0 = auroc(perfect, y), auroc(noise, y)
    t1 = tpr_at_fpr(perfect, y, 0.01)
    t0 = tpr_at_fpr(noise, y, 0.01)
    ok = abs(a1 - 1.0) < 1e-9 and abs(a0 - 0.5) < 0.12 and t1 > 0.99 and t0 < 0.12
    return {"name": "T1f_auroc_tpr", "auroc_perfect": a1, "auroc_noise": a0,
            "tpr1_perfect": t1, "tpr1_noise": t0, "pass": bool(ok)}


def t1g_x2_rank1_deletion(rng) -> dict:
    """Ground-truth algebra behind X2/T2: orthogonalising M against u0 must drive
    ||u0^T M||^2 to ~0, and the resulting matrix must have a new near-null direction
    ALIGNED with u0 -- which is exactly what X10 detects."""
    d, n = 256, 1024
    M = rng.standard_normal((d, n)).astype(np.float64)
    u0 = unit(rng.standard_normal(d))
    M_ed = M - np.outer(u0, u0 @ M)  # alpha = 1 full abliteration of direction u0
    G0, G1 = M @ M.T, M_ed @ M_ed.T
    f0, f1 = float((M**2).sum()), float((M_ed**2).sum())
    wm_before = write_mass(G0, f0, u0, d)
    wm_after = write_mass(G1, f1, u0, d)
    ev, V = np.linalg.eigh(G1)
    vmin = V[:, 0]
    cos_vmin_u0 = abs(float(vmin @ u0))
    ok = wm_before > 0.3 and wm_after < 1e-8 and cos_vmin_u0 > 0.99
    return {"name": "T1g_x2_rank1_deletion", "write_mass_before": wm_before,
            "write_mass_after": wm_after, "cos_vmin_u0": cos_vmin_u0, "pass": bool(ok)}


def main() -> int:
    setup_logging("t1_tests")
    rng = np.random.default_rng(20260921)
    tests = [
        t1a_x2_normalisation(rng),
        t1b_gram_identities(rng),
        t1c_x3_closed_form(rng),
        t1d_rmsnorm_jacobian(rng),
        t1f_auroc_tpr(rng),
        t1g_x2_rank1_deletion(rng),
        t1e_marchenko_pastur(rng),
    ]
    for t in tests:
        logger.info(f"{'PASS' if t['pass'] else 'FAIL'}  {t['name']}  {
            {k: v for k, v in t.items() if k not in ('name', 'pass', 'cases')}}")
    n_pass = sum(1 for t in tests if t["pass"])
    res = {"n_tests": len(tests), "n_pass": n_pass, "all_pass": n_pass == len(tests),
           "tests": tests}
    jdump(res, RESULTS / "t1_unit_tests.json")
    logger.info(f"T1: {n_pass}/{len(tests)} pass -> {RESULTS / 't1_unit_tests.json'}")
    return 0 if res["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
