#!/usr/bin/env python3
"""Figures for the causal depth x site grid (reads results/<prefix>analysis.json, writes figures/).

matplotlib Agg backend; PNG @200dpi + PDF (Type-42 / embeddable fonts); Okabe-Ito colourblind-safe
palette for the categorical (site) encoding and a diverging colormap centred at 0 for the heatmaps.
Never loads a model. Any missing section renders a "NOT RUN" panel instead of crashing.

Usage:
  WS/.venv/bin/python src/figures.py --prefix smoke_
  WS/.venv/bin/python src/figures.py --prefix ""
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from loguru import logger  # noqa: E402

from common import FIGS, RESULTS, jload, setup_logging  # noqa: E402

plt.rcParams["pdf.fonttype"] = 42     # Type-42 (embeddable, editable) fonts in the PDF output
plt.rcParams["ps.fonttype"] = 42
plt.rcParams["font.size"] = 9

# Okabe-Ito colourblind-safe palette
OKABE_ITO = {"P": "#0072B2", "Dprime": "#D55E00", "E": "#009E73"}
SITE_LABEL = {"P": "P", "Dprime": "D'", "E": "E"}
BANDS6 = [f"B{k}" for k in range(1, 7)]
SITES3 = ("P", "Dprime", "E")


def savefig(fig, path_no_ext: Path) -> None:
    path_no_ext.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(path_no_ext) + ".png", dpi=200, bbox_inches="tight")
    fig.savefig(str(path_no_ext) + ".pdf", bbox_inches="tight")
    plt.close(fig)
    logger.info(f"wrote {path_no_ext}.png / .pdf")


def not_run_panel(ax, msg: str = "NOT RUN") -> None:
    ax.text(0.5, 0.5, msg, ha="center", va="center", fontsize=12, color="0.45", transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def cell_effect(grid: dict, outcome: str, arm: str, site: str, band: str):
    fam = grid.get(outcome, {}).get(arm, {})
    cell = fam.get("cells", {}).get(f"{site}_{band}")
    if not cell or cell.get("status") != "OK":
        return None, False
    ev = cell.get("effect_vsR", {})
    e = ev.get("effect")
    if e is None or not np.isfinite(e):
        return None, False
    return e, bool(cell.get("CAUSAL"))


# ================================================================================================
# (a) 6x3 heatmaps: rows B1-B6, cols P/D'/E, arm F on {refused_harm, harmful_compliance_harm,
#     over_refusal_hb} and arm N6 on over_refusal_hb; one figure (4-panel) per model
# ================================================================================================
def heatmap_panel(ax, grid: dict, outcome: str, arm: str, vmax: float):
    data = np.full((6, 3), np.nan)
    causal = np.zeros((6, 3), dtype=bool)
    any_ok = False
    for i, band in enumerate(BANDS6):
        for j, site in enumerate(SITES3):
            e, c = cell_effect(grid, outcome, arm, site, band)
            if e is not None:
                data[i, j] = e
                causal[i, j] = c
                any_ok = True
    ax.set_title(f"{arm}: {outcome}", fontsize=9)
    if not any_ok:
        not_run_panel(ax)
        return None
    im = ax.imshow(data, cmap="RdBu_r", vmin=-vmax, vmax=vmax, aspect="auto")
    ax.set_xticks(range(3))
    ax.set_xticklabels([SITE_LABEL[s] for s in SITES3])
    ax.set_yticks(range(6))
    ax.set_yticklabels(BANDS6)
    for i in range(6):
        for j in range(3):
            v = data[i, j]
            if not np.isfinite(v):
                ax.text(j, i, "-", ha="center", va="center", fontsize=8, color="0.6")
                continue
            ax.text(j, i, f"{v:+.2f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(v) > vmax * 0.6 else "black")
            if causal[i, j]:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, edgecolor="black", linewidth=2))
    return im


def fig_heatmaps(analysis: dict, prefix: str) -> None:
    panels = [("F", "refused_harm"), ("F", "harmful_compliance_harm"), ("F", "over_refusal_hb"),
              ("N6", "over_refusal_hb")]
    for model, res in analysis.get("per_model", {}).items():
        fig, axes = plt.subplots(2, 2, figsize=(9, 9.5))
        ok = res.get("status") == "OK"
        grid = res.get("causal_grid_judged", {}) if ok else {}
        vals = [abs(cell_effect(grid, o, a, s, b)[0]) for a, o in panels for b in BANDS6 for s in SITES3
               if ok and cell_effect(grid, o, a, s, b)[0] is not None]
        vmax = max(vals) if vals else 1.0
        im = None
        for ax, (arm, outcome) in zip(axes.flat, panels):
            if not ok:
                not_run_panel(ax)
                ax.set_title(f"{arm}: {outcome}", fontsize=9)
                continue
            r = heatmap_panel(ax, grid, outcome, arm, vmax)
            im = r if r is not None else im
        fig.suptitle(f"{model}: effect_FR (T vs R), judged 6x3 grid; R = matched displacement (P) / "
                    f"own-coefficient x-(x.v)u (D', E)\n"
                    f"rows B1 (shallow) .. B6 (deep); black outline = CAUSAL (Holm < .05)", fontsize=10)
        if im is not None:
            fig.colorbar(im, ax=list(axes.flat), shrink=0.7, label="effect_FR", pad=0.02)
        savefig(fig, FIGS / f"{prefix}heatmap_{model}")


# ================================================================================================
# (b) decodability AUROC vs |effect_FR| scatter: colour = site, filled = CAUSAL
# ================================================================================================
def fig_decod_scatter(analysis: dict, prefix: str) -> None:
    fig, ax = plt.subplots(figsize=(6, 5))
    any_pt = False
    for model, res in analysis.get("per_model", {}).items():
        if res.get("status") != "OK":
            continue
        grid = res.get("causal_grid_judged", {})
        decod = res.get("decodability", {})
        for site in SITES3:
            for band in BANDS6:
                e, c = cell_effect(grid, "refused_harm", "F", site, band)
                d = decod.get(site, {}).get("by_band", {}).get(band, {})
                auc = (d.get("auroc") or {}).get("auroc")
                if e is None or auc is None or not np.isfinite(auc):
                    continue
                ax.scatter(abs(e), auc, marker=("o" if c else "^"), s=55,
                          facecolors=(OKABE_ITO[site] if c else "none"), edgecolors=OKABE_ITO[site], linewidths=1.3)
                any_pt = True
    if not any_pt:
        not_run_panel(ax)
    else:
        ax.axhline(0.60, color="0.6", linestyle="--", linewidth=1)
        ax.set_xlabel("|effect_FR| (arm F, refused_harm)")
        ax.set_ylabel("decodability AUROC")
        handles = [plt.Line2D([0], [0], marker="s", linestyle="", color=OKABE_ITO[s], label=f"site {SITE_LABEL[s]}")
                  for s in SITES3]
        handles += [plt.Line2D([0], [0], marker="o", linestyle="", markerfacecolor="0.3", color="0.3",
                                label="CAUSAL"),
                   plt.Line2D([0], [0], marker="^", linestyle="", markerfacecolor="none", color="0.3",
                              label="not CAUSAL")]
        ax.legend(handles=handles, fontsize=7, loc="best")
    ax.set_title("Decodability vs |causal effect| (one point per model x cell)")
    savefig(fig, FIGS / f"{prefix}decod_vs_effect")


# ================================================================================================
# (c) SafeRL-minus-instruct DiD forest plot: N6 on over_refusal_hb, F on refused_harm (per cell)
# ================================================================================================
def _forest_panel(ax, rows, title):
    if not rows:
        not_run_panel(ax)
        ax.set_title(title, fontsize=9)
        return
    y = np.arange(len(rows))[::-1]
    for yi, (lab, did, lo, hi, color) in zip(y, rows):
        ax.plot([lo, hi], [yi, yi], color=color, linewidth=2)
        ax.plot([did], [yi], "o", color=color, markersize=5)
    ax.axvline(0, color="0.3", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=6.5)
    ax.set_xlabel("DiD = [T-R](SafeRL) - [T-R](instruct)")
    ax.set_title(title, fontsize=9)


def fig_did_forest(analysis: dict, prefix: str) -> None:
    ts = analysis.get("two_sidedness", {})
    grid_did = ts.get("judged_grid_DiD", {}) if isinstance(ts, dict) else {}
    rows = []
    for label, color in (("N6_over_refusal", OKABE_ITO["P"]), ("F_refused_harm", OKABE_ITO["Dprime"])):
        for key in sorted(grid_did.keys()):
            cell = grid_did[key].get(label, {})
            if cell.get("status") == "OK" and cell.get("did") is not None and np.isfinite(cell["did"]):
                rows.append((f"{label} | {key}", cell["did"], cell["ci_lo"], cell["ci_hi"], color))

    ga = ts.get("two_sidedness_global_ablation", {}).get("per_band_set", {}) if isinstance(ts, dict) else {}
    ga_rows = []
    ga_colors = {"F_refused_harm": OKABE_ITO["Dprime"], "F_over_refusal": OKABE_ITO["P"],
                "N6_over_refusal": OKABE_ITO["E"]}
    for label, color in ga_colors.items():
        for bk in sorted(ga.keys(), key=lambda x: (x != "ALL", x)):
            cell = ga[bk].get(label, {})
            if cell.get("status") == "OK" and cell.get("did") is not None and np.isfinite(cell["did"]):
                ga_rows.append((f"{label} | {bk}", cell["did"], cell["ci_lo"], cell["ci_hi"], color))

    fig, axes = plt.subplots(1, 2, figsize=(13, max(3, 0.28 * max(len(rows), len(ga_rows)) + 1.5)))
    _forest_panel(axes[0], rows, "Site-P/D'/E judged grid DiD: N6/over_refusal_hb, F/refused_harm")
    _forest_panel(axes[1], ga_rows, "genG global-ablation DiD (EXPLORATORY, T3): F & N6 by band-set")
    fig.suptitle("DiD forest: SafeRL minus instruct", fontsize=10)
    savefig(fig, FIGS / f"{prefix}did_forest")


# ================================================================================================
# (d) Delta_BL1(F) - Delta_BL1(RF1) per band, EASY vs HARD stimuli (readouts under intervention)
# ================================================================================================
def fig_delta_bl1(analysis: dict, prefix: str) -> None:
    models = list(analysis.get("per_model", {}).keys())
    n = max(len(models), 1)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 4.5), squeeze=False)
    axes = axes[0]
    if not models:
        not_run_panel(axes[0])
    for ax, model in zip(axes, models):
        res = analysis["per_model"][model]
        stim = res.get("readouts_stimuli", {}) if res.get("status") == "OK" else {}
        per_band = stim.get("per_band", {}) if stim.get("status") == "OK" else {}
        if not per_band:
            not_run_panel(ax)
            ax.set_title(model, fontsize=9)
            continue
        bands = [b for b in BANDS6 if b in per_band]
        easy_pts, hard_pts = [], []
        for b in bands:
            fmr = per_band[b].get("Delta_BL1_F_minus_RF1", {})
            e_, h_ = fmr.get("easy", {}).get("delta"), fmr.get("hard", {}).get("delta")
            easy_pts.append(e_ if e_ is not None and np.isfinite(e_) else np.nan)
            hard_pts.append(h_ if h_ is not None and np.isfinite(h_) else np.nan)
        if all(np.isnan(easy_pts)) and all(np.isnan(hard_pts)):
            not_run_panel(ax)
            ax.set_title(model, fontsize=9)
            continue
        x = np.arange(len(bands))
        w = 0.35
        ax.bar(x - w / 2, easy_pts, width=w, label="EASY stimuli", color=OKABE_ITO["P"])
        ax.bar(x + w / 2, hard_pts, width=w, label="HARD stimuli", color=OKABE_ITO["Dprime"])
        ax.axhline(0, color="0.3", linewidth=1)
        ax.set_xticks(x)
        ax.set_xticklabels(bands)
        ax.set_title(model, fontsize=9)
        ax.set_ylabel("Delta_BL1(F) - Delta_BL1(RF1)")
        ax.legend(fontsize=7)
    fig.suptitle("Readouts under intervention: Delta_BL1(F) vs RF1 by band (A_prompt stimuli, site P)", fontsize=10)
    savefig(fig, FIGS / f"{prefix}delta_bl1")


# ================================================================================================
# (e) exploratory extras: genU (FperpU-minus-F, judged refused_harm) and e2x2_E (site-E LATE-window
#     F-minus-meanRF / N6-minus-RN6 contrasts, N1-analogue and N6-analogue readouts) per band
# ================================================================================================
def fig_exploratory(analysis: dict, prefix: str) -> None:
    models = list(analysis.get("per_model", {}).keys())
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    ax = axes[0]
    any_pt = False
    for k, model in enumerate(models):
        res = analysis["per_model"][model]
        genU = res.get("genU_exploratory_FperpU", {}) if res.get("status") == "OK" else {}
        per_band = genU.get("per_band", {}) if genU.get("status") == "OK" else {}
        xs, ys = [], []
        for bi, band in enumerate(BANDS6):
            cell = per_band.get(band, {}).get("refused_harm", {}).get("FperpU_minus_F_paired_same_pass", {})
            if cell.get("status") == "OK":
                xs.append(bi)
                ys.append(cell["delta_FperpU_minus_F"])
        if xs:
            ax.plot(xs, ys, marker="o", label=model, color=list(OKABE_ITO.values())[k % 3])
            any_pt = True
    if not any_pt:
        not_run_panel(ax)
    else:
        ax.axhline(0, color="0.3", linewidth=1)
        ax.set_xticks(range(6))
        ax.set_xticklabels(BANDS6)
        ax.set_ylabel("FperpU - F (refused_harm, paired, same pass)")
        ax.legend(fontsize=7)
    ax.set_title("genU (exploratory): does refusal survive removing FperpU?", fontsize=9)

    ax = axes[1]
    any_pt = False
    for k, model in enumerate(models):
        res = analysis["per_model"][model]
        e2x2 = res.get("e2x2_E_site_readout", {}) if res.get("status") == "OK" else {}
        block = e2x2.get("N1_analogue_F_at_lstar", {}) if e2x2.get("status") == "OK" else {}
        per_band = block.get("per_band", {}) if block.get("status") == "OK" else {}
        xs, ys = [], []
        for bi, band in enumerate(BANDS6):
            cell = per_band.get(band, {}).get("F_minus_meanRF", {})
            if cell.get("status") == "OK":
                xs.append(bi)
                ys.append(cell["value"])
        if xs:
            ax.plot(xs, ys, marker="s", label=f"{model} (N1-analogue)", color=list(OKABE_ITO.values())[k % 3])
            any_pt = True
    if not any_pt:
        not_run_panel(ax)
    else:
        ax.axhline(0, color="0.3", linewidth=1)
        ax.set_xticks(range(6))
        ax.set_xticklabels(BANDS6)
        ax.set_ylabel("Delta_d(F) - mean(Delta_d(RF1,RF2))")
        ax.legend(fontsize=7)
    ax.set_title("e2x2_E (site-E LATE window): does an EARLY edit survive to tokens 40-55?", fontsize=9)

    fig.suptitle("Exploratory extras: genU FperpU contrast and e2x2_E site-E late readout", fontsize=10)
    savefig(fig, FIGS / f"{prefix}exploratory_extras")


# ================================================================================================
# (f) local (site-P) vs global (all-position, genG) ablation: refused_harm rate under arm 0 / site-P F /
#     all-position F / all-position RFo, across B1-B6 plus ALL
# ================================================================================================
def fig_global_ablation(analysis: dict, prefix: str) -> None:
    models = list(analysis.get("per_model", {}).keys())
    n = max(len(models), 1)
    fig, axes = plt.subplots(1, n, figsize=(5.5 * n, 4.5), squeeze=False)
    axes = axes[0]
    band_keys = BANDS6 + ["ALL"]
    if not models:
        not_run_panel(axes[0])
    for ax, model in zip(axes, models):
        res = analysis["per_model"][model]
        genG = res.get("genG_global_ablation_control", {}) if res.get("status") == "OK" else {}
        per_band = genG.get("per_band", {}) if genG.get("status") == "OK" else {}
        xs, arm0, site_p_f, allpos_f, allpos_rfo = [], [], [], [], []
        for bi, bk in enumerate(band_keys):
            bo = per_band.get(bk, {}).get("refused_harm", {})
            fcell = bo.get("F_global_ablation", {})
            spcell = bo.get("F_site_P_for_comparison", {})
            if fcell.get("status") != "OK":
                continue
            xs.append(bi)
            arm0.append(fcell.get("mean_0"))
            allpos_f.append(fcell.get("mean_T"))
            allpos_rfo.append(fcell.get("mean_R"))
            site_p_f.append(spcell.get("mean_T") if spcell.get("status") == "OK" else np.nan)
        if not xs:
            not_run_panel(ax)
            ax.set_title(model, fontsize=9)
            continue
        ax.plot(xs, arm0, marker="o", label="arm 0", color="0.35")
        ax.plot(xs, site_p_f, marker="s", label="site-P F", color=OKABE_ITO["P"])
        ax.plot(xs, allpos_f, marker="^", label="all-position F (genG)", color=OKABE_ITO["Dprime"])
        ax.plot(xs, allpos_rfo, marker="x", label="all-position RFo (genG)", color=OKABE_ITO["E"])
        ax.set_xticks(range(len(band_keys)))
        ax.set_xticklabels(band_keys)
        ax.set_ylim(-0.05, 1.05)
        ax.set_ylabel("refused_harm rate")
        ax.set_title(model, fontsize=9)
        ax.legend(fontsize=6.5)
    fig.suptitle("T3 disambiguation: local (site-P) vs global (all-position) ablation of F, refused_harm rate",
                fontsize=10)
    savefig(fig, FIGS / f"{prefix}global_ablation_control")


# ================================================================================================
# (g) three-model comparison: site-P effect_FR by band (F/refused_harm, F/over_refusal_hb) as lines
#     with CI bands, one line per model; plus arm-0 refusal / over-refusal bars per model
# ================================================================================================
MODEL_COLORS = {"instruct": OKABE_ITO["P"], "saferl": OKABE_ITO["Dprime"], "abliterated": OKABE_ITO["E"]}


def fig_three_model_comparison(analysis: dict, prefix: str) -> None:
    models = [m for m in analysis.get("models", []) if m != "smoke"]
    if not models:
        models = [m for m in analysis.get("per_model", {}) if m != "smoke"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    for ax, (outcome, arm, title) in zip(axes[:2], (("refused_harm", "F", "site-P F: refused_harm"),
                                                     ("over_refusal_hb", "F", "site-P F: over_refusal_hb"))):
        any_line = False
        for model in models:
            res = analysis.get("per_model", {}).get(model, {})
            if res.get("status") != "OK":
                continue
            jg = res.get("causal_grid_judged", {})
            xs, ys, los, his = [], [], [], []
            for bi, band in enumerate(BANDS6):
                cell = jg.get(outcome, {}).get(arm, {}).get("cells", {}).get(f"P_{band}")
                if not cell or cell.get("status") != "OK":
                    continue
                ev = cell["effect_vsR"]
                if ev.get("effect") is None or not np.isfinite(ev["effect"]):
                    continue
                xs.append(bi)
                ys.append(ev["effect"])
                los.append(ev["ci_lo"])
                his.append(ev["ci_hi"])
            if xs:
                c = MODEL_COLORS.get(model, "0.3")
                ax.plot(xs, ys, marker="o", label=model, color=c)
                ax.fill_between(xs, los, his, color=c, alpha=0.2)
                any_line = True
        if not any_line:
            not_run_panel(ax)
        else:
            ax.axhline(0, color="0.3", linewidth=1)
            ax.set_xticks(range(6))
            ax.set_xticklabels(BANDS6)
            ax.set_ylabel("effect_FR")
            ax.legend(fontsize=7)
        ax.set_title(title, fontsize=9)

    ax = axes[2]
    tmc = analysis.get("three_model_comparison", {})
    labels, ref_v, ref_lo, ref_hi, or_v, or_lo, or_hi = [], [], [], [], [], [], []
    for model in models:
        e = tmc.get(model, {})
        r = e.get("arm0_baseline_rates_genP", {}) if isinstance(e, dict) else {}
        rh = r.get("refused_harm", {}) if r.get("status") == "OK" else {}
        orr = r.get("over_refusal_hb", {}) if r.get("status") == "OK" else {}
        labels.append(model)
        ref_v.append(rh.get("rate"))
        ref_lo.append(rh.get("ci_lo"))
        ref_hi.append(rh.get("ci_hi"))
        or_v.append(orr.get("rate"))
        or_lo.append(orr.get("ci_lo"))
        or_hi.append(orr.get("ci_hi"))
    if any(v is not None for v in ref_v) or any(v is not None for v in or_v):
        x = np.arange(len(labels))
        w = 0.35

        def err(v, lo, hi):
            return [[(vv - l) if vv is not None and l is not None and np.isfinite(l) else 0
                    for vv, l in zip(v, lo)],
                   [(h - vv) if vv is not None and h is not None and np.isfinite(h) else 0
                    for vv, h in zip(v, hi)]]

        rv = [v if v is not None else 0 for v in ref_v]
        ov = [v if v is not None else 0 for v in or_v]
        ax.bar(x - w / 2, rv, width=w, yerr=err(ref_v, ref_lo, ref_hi), label="arm-0 refused_harm",
              color=OKABE_ITO["P"], capsize=3)
        ax.bar(x + w / 2, ov, width=w, yerr=err(or_v, or_lo, or_hi), label="arm-0 over_refusal_hb",
              color=OKABE_ITO["Dprime"], capsize=3)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=15)
        ax.set_ylim(0, 1.05)
        ax.legend(fontsize=7)
    else:
        not_run_panel(ax)
    ax.set_title("Arm-0 baseline rates (genP)", fontsize=9)

    fig.suptitle("Three-model comparison: instruct vs SafeRL vs abliterated", fontsize=10)
    savefig(fig, FIGS / f"{prefix}three_model_comparison")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="", help="matches --out-prefix used by analyze.py")
    a = ap.parse_args()
    setup_logging("figures" + (f"_{a.prefix.rstrip('_')}" if a.prefix else ""))
    p = RESULTS / f"{a.prefix}analysis.json"
    if not p.exists():
        logger.error(f"{p} missing; run analyze.py first")
        return 1
    analysis = jload(p)
    fig_heatmaps(analysis, a.prefix)
    fig_decod_scatter(analysis, a.prefix)
    fig_did_forest(analysis, a.prefix)
    fig_delta_bl1(analysis, a.prefix)
    fig_exploratory(analysis, a.prefix)
    fig_global_ablation(analysis, a.prefix)
    fig_three_model_comparison(analysis, a.prefix)
    logger.info("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
