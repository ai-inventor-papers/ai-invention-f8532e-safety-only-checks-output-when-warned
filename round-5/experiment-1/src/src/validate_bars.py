#!/usr/bin/env python3
"""TASK 4: validate src/bars.py's compute_bars() against iteration-4's OWN PUBLISHED per-tag
values (I4/results/scores/ckpt_<tag>.json: values_full.{N1,N6,C7,C13_peak_d,N11,BL1_*},
B7.B7_nullproj, AMS_T1_full.AMS_T1_sigma) across all 51 I4/harvest tags.

Writes results/bars_validation.json: {bar: {n_compared, max_abs_diff, max_rel_diff, worst_tag}}.
Target: exact or < 1e-6 relative.
"""
from __future__ import annotations

import gc
import json
import math
import resource
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "src"))
from bars import compute_bars  # noqa: E402

I4 = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/gen_art_experiment_1")
I4_HARVEST = I4 / "harvest"
I4_SCORES = I4 / "results" / "scores"

# bar_name -> path into the ckpt_<tag>.json published record
PUBLISHED_PATH = {
    "N1": ("values_full", "N1"),
    "N6": ("values_full", "N6"),
    "C7": ("values_full", "C7"),
    "C13_peak_d": ("values_full", "C13_peak_d"),
    "N11": ("values_full", "N11"),
    "BL1_easy": ("values_full", "BL1_easy"),
    "BL1_hard": ("values_full", "BL1_hard"),
    "BL1_truelogit": ("values_full", "BL1_truelogit"),
    "BL1_truelogit_hard": ("values_full", "BL1_truelogit_hard"),
    "B7_nullproj": ("B7", "B7_nullproj"),
    "AMS_T1_sigma": ("AMS_T1_full", "AMS_T1_sigma"),
}


def _get(doc: dict, path: tuple[str, str]):
    a, b = path
    sub = doc.get(a)
    if not isinstance(sub, dict):
        return None
    return sub.get(b)


def main() -> None:
    tags = sorted(p.name for p in I4_HARVEST.iterdir() if p.is_dir() and (p / "meta.json").exists())
    assert len(tags) == 51, f"expected 51 I4 tags, found {len(tags)}"

    stats: dict[str, dict] = {b: {"n_compared": 0, "n_skipped": 0, "max_abs_diff": 0.0,
                                   "max_rel_diff": 0.0, "worst_tag": None, "diffs": []}
                               for b in PUBLISHED_PATH}
    per_tag_errors: list[str] = []

    for ti, tag in enumerate(tags):
        tag_dir = I4_HARVEST / tag
        score_path = I4_SCORES / f"ckpt_{tag}.json"
        if not score_path.exists():
            per_tag_errors.append(f"{tag}: no published score file")
            continue
        published = json.loads(score_path.read_text())
        try:
            computed = compute_bars(tag_dir)
        except Exception as e:  # noqa: BLE001
            per_tag_errors.append(f"{tag}: compute_bars raised {type(e).__name__}: {e}")
            gc.collect()
            continue

        rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        print(f"[{ti + 1}/{len(tags)}] {tag}  maxrss={rss_mb:.0f}MB", flush=True)

        for bar, path in PUBLISHED_PATH.items():
            pub_val = _get(published, path)
            comp_val = computed.get(bar)
            if pub_val is None or comp_val is None:
                stats[bar]["n_skipped"] += 1
                continue
            if isinstance(pub_val, str) or isinstance(comp_val, str):
                stats[bar]["n_skipped"] += 1
                continue
            pub_f, comp_f = float(pub_val), float(comp_val)
            if not (math.isfinite(pub_f) and math.isfinite(comp_f)):
                if math.isfinite(pub_f) != math.isfinite(comp_f):
                    per_tag_errors.append(f"{tag}/{bar}: finiteness mismatch published={pub_f} computed={comp_f}")
                stats[bar]["n_skipped"] += 1
                continue
            abs_diff = abs(pub_f - comp_f)
            rel_diff = abs_diff / max(abs(pub_f), 1e-12)
            stats[bar]["n_compared"] += 1
            if abs_diff > stats[bar]["max_abs_diff"]:
                stats[bar]["max_abs_diff"] = abs_diff
                stats[bar]["worst_tag"] = tag
            if rel_diff > stats[bar]["max_rel_diff"]:
                stats[bar]["max_rel_diff"] = rel_diff

        del computed, published
        gc.collect()

    for bar in stats:
        stats[bar].pop("diffs", None)
        stats[bar]["target_met"] = (
            stats[bar]["n_compared"] > 0
            and (stats[bar]["max_abs_diff"] == 0.0 or stats[bar]["max_rel_diff"] < 1e-6)
        )

    out = {
        "n_tags": len(tags),
        "published_source": "I4/results/scores/ckpt_<tag>.json (values_full / B7 / AMS_T1_full)",
        "bars": stats,
        "errors": per_tag_errors,
    }
    out_path = WS / "results" / "bars_validation.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
