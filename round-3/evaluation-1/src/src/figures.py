#!/usr/bin/env python3
"""Four data figures, drawn from the cached result JSONs (numbers in, pictures out):
fig1 per-lineage site curves (TPR@1%FPR vs lesion alpha, scenario-bootstrap CIs, 3 sites)
fig2 fixed-axis vs own-axis growth per commissioned arm
fig3 per-layer held-out request-axis Cohen's d for the 5 commissioned arms
fig4 restricted-budget (k) curve: HARD AUROC and TPR@5%FPR vs k."""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

WS = Path(__file__).resolve().parents[1]
RES, FIG = WS / "results", WS / "figures"
SK = Path("/ai-inventor/.claude/skills/aii-data-fig-gen/scripts")
sys.path.insert(0, str(SK))
try:
    from chart_style import apply_house_style, place_legend, fit_legends, clear_legends_of_data, fit_titles  # noqa: E402
    HOUSE = True
except ImportError:  # pragma: no cover
    HOUSE = False

ARMS = [("Qwen--Qwen3-4B-Base", "Base"), ("Qwen--Qwen3-4B", "instruct"), ("Qwen--Qwen3-4B-SafeRL", "SafeRL"),
        ("CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6", "STaR (non-safety FT)"),
        ("mlabonne--Qwen3-4B-abliterated", "mlabonne abliterated")]
LIN = {"L1": "L1 Base", "L2": "L2 instruct", "L3": "L3 SafeRL", "L4": "L4 STaR (non-safety)"}


def _j(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _finish(fig, name: str) -> None:
    if HOUSE:
        try:
            fit_legends(fig)
            clear_legends_of_data(fig)
            fit_titles(fig)
        except Exception as exc:  # noqa: BLE001
            print(f"house-style fitter skipped on {name}: {exc}")
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f"{name}.pdf")
    fig.savefig(FIG / f"{name}.png", dpi=200)
    plt.close(fig)
    print(f"wrote figures/{name}.pdf/.png")


def _leg(ax, **kw):
    if HOUSE:
        place_legend(ax, **kw)
    else:
        ax.legend(**kw)


def fig_sites() -> None:
    cells = _j(RES / "laneb_cells.json")
    if isinstance(cells, dict):
        cells = cells.get("cells") or cells.get("rows")
    if not cells:
        print("fig1 skipped: no laneb_cells")
        return
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), layout="constrained", sharey=True)
    for ax, site in zip(axes, ("PROMPT", "EARLY", "LATE")):
        for L in ("L1", "L2", "L3", "L4"):
            rr = sorted([c for c in cells if c.get("lineage") == L and str(c.get("site")).upper() == site
                         and str(c.get("layer")) == "band" and c.get("probe") in ("logistic", "logreg", "lr")
                         and str(c.get("cls", "")).upper() == "REQUEST"], key=lambda c: float(c["alpha"]))
            if not rr:
                continue
            a = [float(c["alpha"]) for c in rr]
            y = [c["tpr1"] for c in rr]
            lo = [(c.get("tpr1_ci") or [np.nan, np.nan])[-2] for c in rr]
            hi = [(c.get("tpr1_ci") or [np.nan, np.nan])[-1] for c in rr]
            ax.plot(a, y, marker="o", label=LIN[L])
            ax.fill_between(a, lo, hi, alpha=0.15)
        ax.set_title({"PROMPT": "PROMPT site (lastp)", "EARLY": "RESPONSE-EARLY (tokens 5-20)",
                      "LATE": "RESPONSE-LATE (tokens 40-55)"}[site])
        ax.set_xlabel("lesion strength alpha")
    axes[0].set_ylabel("TPR @ 1% FPR (request class)")
    _leg(axes[2], loc="best")
    _finish(fig, "fig1_site_curves")


def fig_accum() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), layout="constrained")
    for tag, name in ARMS:
        p = _j(RES / "panel_ckpt" / f"{tag}.json")
        if not p:
            continue
        s = (p.get("section2a") or {}).get("s36") or {}
        fx, own = s.get("fixed_axis_normgap_curve"), s.get("own_axis_d_curve")
        if not fx or not own:
            continue
        l0 = s.get("s_layer", 13)
        xs = np.arange(l0, l0 + len(fx))
        axes[0].plot(xs, np.asarray(fx, float) / (abs(fx[0]) if fx[0] else 1.0), label=name)
        axes[1].plot(xs, np.asarray(own, float), label=name)
    axes[0].set_title("FIXED axis u_13, normalised gap / |gap(13)|")
    axes[1].set_title("OWN axis refit per layer: held-out Cohen's d")
    for ax in axes:
        ax.set_xlabel("layer")
    axes[0].axhline(1.0, color="grey", lw=0.8, ls=":")
    _leg(axes[1], loc="best")
    _finish(fig, "fig2_fixed_vs_own_axis")


def fig_dcurves() -> None:
    fig, ax = plt.subplots(figsize=(7, 3.9), layout="constrained")
    for tag, name in ARMS:
        p = _j(RES / "panel_ckpt" / f"{tag}.json")
        if not p:
            continue
        d = [np.nan if v is None else v for v in p["section1a"]["heldout_d"]]
        ax.plot(np.arange(len(d)) / (len(d) - 1), d, label=name)
    ax.set_xlabel("depth fraction l/L")
    ax.set_ylabel("held-out Cohen's d (EASY-fit, HARD-scored)")
    ax.set_title("Request-axis separation by depth, 5 commissioned arms (prompt site)")
    _leg(ax, loc="best")
    _finish(fig, "fig3_layer_d_curves")


def fig_kbudget() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), layout="constrained")
    ks = [4, 8, 16, 32, 64]
    for tag, name in ARMS:
        p = _j(RES / "panel_ckpt" / f"{tag}.json")
        if not p:
            continue
        b = p["section1b_kbudget"]
        for ax, m in zip(axes, ("auroc", "tpr5")):
            y = [b.get(f"k{k}_{m}_mean") for k in ks]
            lo = [b.get(f"k{k}_{m}_p5") for k in ks]
            hi = [b.get(f"k{k}_{m}_p95") for k in ks]
            ax.plot(ks, y, marker="o", label=name)
            ax.fill_between(ks, lo, hi, alpha=0.10)
    axes[0].set_ylabel("HARD AUROC (mean, 5-95% over 200 draws)")
    axes[1].set_ylabel("HARD TPR @ 5% FPR")
    for ax in axes:
        ax.set_xscale("log", base=2)
        ax.set_xlabel("k prompts per class (EASY fit)")
    _leg(axes[1], loc="best")
    _finish(fig, "fig4_k_budget")


def main() -> None:
    if HOUSE:
        apply_house_style()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fig_sites()
        fig_accum()
        fig_dcurves()
        fig_kbudget()


if __name__ == "__main__":
    main()
