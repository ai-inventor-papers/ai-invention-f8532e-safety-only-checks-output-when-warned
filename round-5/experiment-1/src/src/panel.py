#!/usr/bin/env python3
"""S2.1: apply the prereg panel-inclusion rule MECHANICALLY, before any score exists.

Reads only item-id COUNTS (results/items/gt_tag_counts.json, built by the recon step from
graded_truth.json keys), harvest DONE/MANIFEST status, and exact parameter counts summed
from local safetensors headers. Never reads an HC/OR/SE value.
Writes results/panel.json.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

from loguru import logger

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import sha256_file, utc_now  # noqa: E402

RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
H4 = RUN / "iter_4/gen_art/gen_art_experiment_1/harvest"
H2 = RUN / "iter_2/gen_art/gen_art_experiment_1/harvest"
HUB = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/.shared_cache/hf/hub")
RES = WS / "results"
MAX_PARAMS = 2.2e9
QUARTET = ["Qwen--Qwen3-4B-Base", "Qwen--Qwen3-4B", "Qwen--Qwen3-4B-SafeRL", "mlabonne--Qwen3-4B-abliterated",
           "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6"]
CONTROLS = ["RandInit-Qwen3-0.6B"]
BLANKET = {"F1__cautious": "OR .976 (plan text)", "F3__cautious": "OR .843 (plan text)"}

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(WS / "logs/panel.log", rotation="30 MB", level="DEBUG")


def safetensors_numel(snapshot: Path) -> int | None:
    """Exact element count from safetensors headers (dtype-independent)."""
    files = sorted(snapshot.glob("*.safetensors"))
    idx = snapshot / "model.safetensors.index.json"
    if idx.exists():
        wm = json.loads(idx.read_text()).get("weight_map", {})
        files = sorted({snapshot / f for f in wm.values()})
    if not files:
        return None
    total = 0
    for f in files:
        with f.open("rb") as fh:
            n = struct.unpack("<Q", fh.read(8))[0]
            hdr = json.loads(fh.read(n))
        for k, v in hdr.items():
            if k == "__metadata__":
                continue
            numel = 1
            for s in v["shape"]:
                numel *= int(s)
            total += numel
    return total


def snapshot_of(repo: str) -> Path | None:
    d = HUB / ("models--" + repo.replace("/", "--")) / "snapshots"
    if not d.is_dir():
        return None
    snaps = sorted(d.iterdir(), key=lambda p: p.stat().st_mtime)
    return snaps[-1] if snaps else None


def manifest_ok(tag_dir: Path) -> tuple[bool, str]:
    man = tag_dir / "MANIFEST.sha256.json"
    if not (tag_dir / "DONE").exists():
        return False, "no DONE marker"
    if not man.exists():
        return False, "no MANIFEST.sha256.json"
    m = json.loads(man.read_text())
    files = m.get("files", m)
    bad = []
    for name, dig in (files.items() if isinstance(files, dict) else []):
        if isinstance(dig, dict):
            dig = dig.get("sha256")
        p = tag_dir / name
        if not p.exists() or (isinstance(dig, str) and sha256_file(p) != dig):
            bad.append(name)
    return (not bad), ("verified" if not bad else f"mismatch: {bad[:3]}")


def main() -> None:
    counts = json.loads((RES / "items/gt_tag_counts.json").read_text())
    params_cache: dict[str, int | None] = {}
    included, excluded, table = [], [], {}
    for tag_dir in sorted(p for p in H4.iterdir() if p.is_dir()):
        tag = tag_dir.name
        meta = json.loads((tag_dir / "meta.json").read_text())
        repo = (meta.get("build_info") or {}).get("repo")
        if repo not in params_cache:
            snap = snapshot_of(repo) if repo else None
            params_cache[repo] = safetensors_numel(snap) if snap else None
        nparams = params_cache[repo]
        c = counts.get(tag, {})
        reasons = []
        if c.get("n_harm_graded", 0) < 20 or c.get("n_hardbenign_graded", 0) < 20:
            reasons.append(f"graded items harm={c.get('n_harm_graded')} hard-benign={c.get('n_hardbenign_graded')} (<20)")
        if nparams is None:
            reasons.append("parameter count unavailable")
        elif nparams > MAX_PARAMS:
            reasons.append(f"params {nparams / 1e9:.3f}B > 2.2B")
        ok, why = manifest_ok(tag_dir)
        if not ok:
            reasons.append(why)
        table[tag] = {"repo": repo, "params_exact": nparams, "n_layers": meta.get("n_layers"),
                      "hidden": meta.get("hidden_size"), "manifest": why, "arm": meta.get("variant"),
                      "fk": meta.get("fk")}
        (excluded if reasons else included).append(tag if not reasons else {"tag": tag, "reasons": reasons})
    # graded-truth keys with no harvest tag of their own
    for key, c in counts.items():
        if (H4 / key).is_dir():
            continue
        dup = c.get("duplicate_of_F_arm") or (f"HG__{key}" if (H4 / f"HG__{key}").is_dir() else None)
        excluded.append({"tag": key, "reasons": [f"duplicate re-grading (45/43 item set) of harvest tag {dup}" if dup
                                                  else "no iteration-4 harvest tag"]})
    blocks = {"quartet": [t for t in QUARTET if (H2 / t).is_dir()],
              "control": [t for t in CONTROLS if (H2 / t).is_dir()]}
    out = {"utc": utc_now(), "rule": "prereg a_panel_inclusion_rule", "expected": "40-51",
           "achieved": len(included), "included": included, "excluded": excluded,
           "flags": {t: BLANKET[t] for t in BLANKET if t in included},
           "blocks": blocks, "params_table": table,
           "note": "quartet/control rows are array-only (iteration-2 harvest) and excluded from screen statistics"}
    (RES / "panel.json").write_text(json.dumps(out, indent=1))
    logger.info(f"panel: {len(included)} included, {len(excluded)} excluded; blocks={blocks}")
    for e in excluded:
        logger.info(f"  excluded {e['tag']}: {e['reasons']}")


if __name__ == "__main__":
    main()
