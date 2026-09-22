"""Optional figure: rank over-refusal cells by |effect_FR| with CIs, Holm-18
survivor marked. Reads results/table_causal_grid.json (written by d5_d6.py).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path(__file__).resolve().parent.parent / "results"
FIGS = Path(__file__).resolve().parent.parent / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

d = json.load(open(RESULTS / "table_causal_grid.json"))
ranked = d["effect_ranking_over_refusal_site_P"][:16]
ranked = ranked[::-1]  # plot largest at top

fig, ax = plt.subplots(figsize=(7.5, 6.0))
ys = range(len(ranked))
for y, r in zip(ys, ranked):
    survivor = bool(r.get("causal_rederived"))
    color = "#1b9e77" if survivor else "#7570b3"
    ax.errorbar(r["effect_FR"], y, xerr=[[r["effect_FR"] - r["ci_lo"]], [r["ci_hi"] - r["effect_FR"]]],
                fmt="o", color=color, ecolor=color, capsize=3,
                markeredgecolor="black" if survivor else color, markeredgewidth=1.4 if survivor else 0)
labels = [f"{r['model']}/{r['arm']}@{r['band']} (rank {r['rank_by_abs_effect']})" for r in ranked]
ax.set_yticks(list(ys))
ax.set_yticklabels(labels, fontsize=8)
ax.axvline(0, color="grey", linewidth=0.8)
ax.set_xlabel("effect_FR (arm minus matched-displacement random control), over_refusal_hb, site P")
ax.set_title("Over-refusal cells ranked by |effect|, site P\n(black outline = Holm-18 survivor)")
fig.tight_layout()
fig.savefig(FIGS / "fig2_causal_effects.png", dpi=150)
print("WROTE", FIGS / "fig2_causal_effects.png")
