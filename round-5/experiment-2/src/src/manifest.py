#!/usr/bin/env python3
"""STAGE G -- the per-checkpoint panel manifest.

One record per checkpoint that has completed the GATED pipeline (graded ->
committed -> harvested).  Written atomically (tmp + os.replace) after each
checkpoint so a parallel scorer can consume a PARTIAL panel safely and never
observe a truncated read.

It reports measured columns and array provenance.  It reports no candidate
value, no ranking and no correlation -- see src/hygiene_check.py, which lints
this file along with everything else under results/.

    python manifest.py rebuild     # recompute every record from disk
    python manifest.py show
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

WS = Path(__file__).resolve().parent.parent
RESULTS = WS / "results"
ARRAYS = WS / "arrays"
OUT = RESULTS / "panel_manifest.json"


def jload(p: Path, default: Any = None) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _npy_header(p: Path) -> tuple[tuple[int, ...] | None, str | None]:
    """Read shape+dtype from a .npy header without importing numpy."""
    try:
        with p.open("rb") as f:
            if f.read(6) != b"\x93NUMPY":
                return None, None
            major = f.read(1)[0]
            f.read(1)
            hlen = int.from_bytes(f.read(2 if major == 1 else 4), "little")
            hdr = f.read(hlen).decode("latin1")
        d = eval(hdr, {"__builtins__": {}}, {"False": False, "True": True})  # noqa: S307
        return tuple(d.get("shape", ())), str(d.get("descr"))
    except (OSError, ValueError, SyntaxError, KeyError, TypeError):
        return None, None


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def graded_index() -> dict[str, dict]:
    """tag -> its row from a COMMITTED graded_truth stage file."""
    idx: dict[str, dict] = {}
    for p in sorted(RESULTS.glob("graded_truth_s*.json")):
        for r in (jload(p, {}) or {}).get("per_ckpt", []):
            if r.get("tag"):
                r = dict(r)
                r["_stage_file"] = p.name
                idx[r["tag"]] = r
    return idx


def sweep_index() -> dict[str, dict]:
    """tag -> descriptor, for BOTH panel tags (from the frozen sweep order) and the in-house
    Part-B arms (from the a-priori declaration file), so every manifest row carries its family
    and lineage role."""
    out: dict[str, dict] = {}
    for row in (jload(RESULTS / "sweep_order.json", {}) or {}).get("order", []):
        out["HG__" + row["repo"].replace("/", "--")] = row
    arms = jload(RESULTS / "partb_arms.json", {}) or {}
    for a in (arms.get("arms", []) if isinstance(arms, dict) else []):
        if not isinstance(a, dict) or not a.get("tag"):
            continue
        intended = str(a.get("intended_stratum") or "")
        out[a["tag"]] = {
            "repo": a.get("parent") or arms.get("parent"),
            "family": a.get("family") or "ernie",
            "role": ("inhouse_effective" if "EFFECTIVE" in intended else "inhouse_noop"),
            "unit": "PARTB_INHOUSE",
            "prior_exposure": "IN_HOUSE_CONSTRUCTED",
            "flags": [f for f in (("structurally_degenerate",) if a.get("structurally_degenerate")
                                  else ())],
            "bf16_gb": a.get("bf16_gb"),
            "arm": a.get("arm"),
            "intended_stratum": a.get("intended_stratum"),
            "can_move_activation": a.get("can_move_activation"),
            "can_move_logit": a.get("can_move_logit"),
        }
    return out


def chain_index_of(tag: str, stage_file: str | None) -> int | None:
    chain = WS / "logs" / "chain.jsonl"
    if not chain.exists() or not stage_file:
        return None
    for line in chain.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if str(r.get("payload_path", "")).endswith(stage_file):
            return r.get("i")
    return None


def build_records(full_hash: bool = True) -> list[dict[str, Any]]:
    gi, si = graded_index(), sweep_index()
    recs: list[dict[str, Any]] = []
    if not ARRAYS.exists():
        return recs
    for d in sorted(ARRAYS.iterdir()):
        if not d.is_dir() or not (d / "DONE").exists():
            continue
        tag = d.name
        meta = jload(d / "meta.json", {}) or {}
        g = gi.get(tag, {})
        s = si.get(tag, {})

        arrays: dict[str, Any] = {}
        for f in sorted(d.rglob("*.npy")):
            shape, dtype = _npy_header(f)
            rel = f.relative_to(d).as_posix()
            arrays[rel] = {"shape": list(shape) if shape else None, "dtype": dtype,
                           "bytes": f.stat().st_size,
                           "sha256": sha256_file(f) if full_hash else None}

        pooled = g.get("pooled", {}) or {}
        rates = g.get("rates", pooled) or {}
        recs.append({
            "tag": tag,
            "repo_id": meta.get("repo") or s.get("repo"),
            "revision_sha": meta.get("revision_sha") or s.get("revision_sha"),
            "family": s.get("family") or g.get("family"),
            "lineage_role": s.get("role") or g.get("role"),
            "unit": s.get("unit"),
            "prior_exposure": s.get("prior_exposure"),
            "flags": s.get("flags"),
            "n_params": meta.get("n_params"),
            "L": meta.get("n_layers"),
            "d": meta.get("hidden_size"),
            "vocab_size": meta.get("vocab_size"),
            "tie_word_embeddings": meta.get("tie_word_embeddings"),
            "load_format": meta.get("load_format"),
            "trust_remote_code": meta.get("trust_remote_code"),
            "transformers_version": meta.get("transformers_version"),
            "weight_fingerprint": meta.get("weight_fingerprint"),
            "weight_sha_full": meta.get("weight_sha_full"),
            "draw_hash": s.get("rank_key") or s.get("draw_hash"),
            "rates": rates,
            "n_items_generated": g.get("n_items_generated"),
            "item_sets": g.get("item_sets"),
            "ams_sigma_bs1": meta.get("ams_sigma_bs1"),
            "ams_sigma_bs8": meta.get("ams_sigma_bs8"),
            "degeneracy_flags": meta.get("degeneracy_flags") or s.get("flags"),
            "arm": s.get("arm"),
            "intended_stratum": s.get("intended_stratum"),
            "can_move_activation": s.get("can_move_activation"),
            "can_move_logit": s.get("can_move_logit"),
            "max_memory_allocated_mib": meta.get("max_memory_allocated_mib"),
            "timings_s": meta.get("timings"),
            "array_paths": arrays,
            "n_arrays": len(arrays),
            "graded_truth_stage_file": g.get("_stage_file"),
            "chain_index": chain_index_of(tag, g.get("_stage_file")),
            "order_gate_ok": bool(g),
            "utc": meta.get("utc"),
        })
    return recs


def write(recs: list[dict[str, Any]]) -> Path:
    doc = {
        "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n": len(recs),
        "note": ("One record per checkpoint that completed the GATED pipeline "
                 "(graded -> committed -> harvested). Measured columns and array "
                 "provenance only; no candidate value, ranking or correlation."),
        "checkpoints": recs,
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, OUT)
    return OUT


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rebuild")
    r.add_argument("--no-hash", action="store_true", help="skip per-file sha256 (faster)")
    sub.add_parser("show")
    ns = ap.parse_args()

    if ns.cmd == "rebuild":
        recs = build_records(full_hash=not ns.no_hash)
        write(recs)
        print(f"panel_manifest.json: {len(recs)} checkpoints")
        for x in recs:
            print(f"  {x['tag']:48} fam={str(x['family'])[:12]:12} "
                  f"role={str(x['lineage_role'])[:13]:13} L={x['L']} d={x['d']} "
                  f"arrays={x['n_arrays']} gate={x['order_gate_ok']}")
        ungated = [x["tag"] for x in recs if not x["order_gate_ok"]]
        if ungated:
            print(f"  !! {len(ungated)} harvested tag(s) with NO committed graded_truth: {ungated}")
            return 1
        return 0

    doc = jload(OUT, {"checkpoints": []})
    print(json.dumps({k: v for k, v in doc.items() if k != "checkpoints"}, indent=1))
    print(f"n={len(doc.get('checkpoints', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
