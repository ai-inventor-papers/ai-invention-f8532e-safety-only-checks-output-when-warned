#!/usr/bin/env python3
"""A3 variance decomposition across the SCREEN panel (reported whether or not A3 survives).

For each panel checkpoint, g_dom = per-domain Cohen's d of the request-axis projection (harmful vs
benign HARD items of that OR-Bench domain, S32 fit-fold items excluded), averaged over the two
cross-fit folds. Var_within = mean over checkpoints of Var_dom(g_dom); Var_between = Var over
checkpoints of mean_dom(g_dom). A3 'wins outright' (prereg) iff within > between. Array-derived
only (reads results/screen/tierA/*.json); no outcome is read."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

WS = Path(__file__).resolve().parents[1]
RES = WS / "results"


def main() -> None:
    panel = json.loads((RES / "panel.json").read_text())["included"]
    per = {}
    for t in panel:
        r = json.loads((RES / f"screen/tierA/{t}.json").read_text())
        doms: dict[str, list[float]] = {}
        for f, dd in (r.get("A3_domains") or {}).items():
            for dm, v in (dd or {}).items():
                if v.get("g") is not None:
                    doms.setdefault(dm, []).append(float(v["g"]))
        per[t] = {dm: float(np.mean(v)) for dm, v in doms.items()}
    common = sorted(set.intersection(*[set(v) for v in per.values()])) if per else []
    G = np.array([[per[t][d] for d in common] for t in panel])          # ckpt x domain
    within = float(np.mean(G.var(axis=1, ddof=1)))
    between = float(np.var(G.mean(axis=1), ddof=1))
    dom_means = {d: float(G[:, j].mean()) for j, d in enumerate(common)}
    out = {"n_checkpoints": len(panel), "domains_common": common, "n_domains": len(common),
           "var_within_checkpoint": within, "var_between_checkpoints": between,
           "ratio_within_over_between": within / between if between > 0 else None,
           "A3_wins_outright (within > between)": bool(within > between),
           "domain_mean_g_across_panel": dom_means,
           "per_checkpoint_g": {t: {d: per[t][d] for d in common} for t in panel},
           "caveat": "XSTest is violence-skewed; thin domains are OR-Bench non-twin items (twin_available=false); per-domain n is 4-15 per class"}
    (RES / "screen/a3_variance_decomposition.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("n_checkpoints", "n_domains", "domains_common", "var_within_checkpoint",
                                          "var_between_checkpoints", "ratio_within_over_between",
                                          "A3_wins_outright (within > between)")}, indent=1))


if __name__ == "__main__":
    main()
