"""D11 backstop join: independently re-run the iteration-5 confirmation lookup.

Reads the screen's hashed survivor.json and the substrate's panel manifest from
the two PARALLEL iteration-5 artifacts, verifies the HASH ORDER (the survivor
hash must be committed BEFORE any panel label is read), and reports the join.

NEVER guesses a survivor and NEVER fabricates a join. Iteration 3 correctly
wrote a join_stub.json when no survivor existed; that is the precedent.
"""

from __future__ import annotations

import datetime as dt
import glob
import hashlib
import json
import os
from pathlib import Path
from typing import Any

WS = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_evaluation_1")
ITER5 = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5")

SURVIVOR_GLOBS = [
    "gen_art/*/results/survivor.json",
    "gen_art/*/results/*/survivor.json",
    "gen_art/*/results/screen/*.json",
    "gen_art/*/survivor.json",
    "gen_art/*/results/survivor*.json",
    "gen_art/*/out/survivor*.json",
    "**/results/survivor*.json",
]
PANEL_GLOBS = [
    "gen_art/*/results/panel_manifest.json",
    "gen_art/*/results/panel.json",
    "gen_art/*/results/panel_rule.json",
    "gen_art/*/results/*/panel_manifest.json",
    "gen_art/*/panel_manifest.json",
    "**/results/panel_manifest*.json",
]
CHAIN_GLOBS = [
    "gen_art/*/hash_chain.jsonl",
    "gen_art/*/results/hash_chain.jsonl",
    "gen_art/*/build_log.txt",
    "gen_art/*/results/*hash*.json*",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(globs: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    searched: list[str] = []
    found: list[dict[str, Any]] = []
    for g in globs:
        pat = str(ITER5 / g)
        searched.append(pat)
        for hit in sorted(glob.glob(pat, recursive=True)):
            hp = Path(hit)
            if not hp.is_file() or ".venv" in hit:
                continue
            if any(f["path"] == hit for f in found):
                continue
            st = hp.stat()
            found.append({
                "path": hit,
                "size_bytes": st.st_size,
                "mtime_utc": dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).isoformat(),
                "mtime_epoch": st.st_mtime,
                "sha256": sha256_file(hp),
            })
    return searched, found


def main() -> None:
    searched_all: list[str] = []
    s_pat, survivors = resolve(SURVIVOR_GLOBS)
    p_pat, panels = resolve(PANEL_GLOBS)
    c_pat, chains = resolve(CHAIN_GLOBS)
    searched_all = s_pat + p_pat + c_pat

    out: dict[str, Any] = {
        "deliverable": "D11",
        "title": "Backstop join of the iteration-5 screen survivor against the blind substrate panel",
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "paths_searched": searched_all,
        "survivor_files_found": survivors,
        "panel_files_found": panels,
        "hash_order_evidence_found": chains,
        "precedent": (
            "iteration 3 wrote results/join_stub.json when no screen survivor existed; "
            "this artifact follows that precedent rather than guessing a survivor."
        ),
    }

    # ---- substrate side: committed panel manifest (a POINTER file, safe to read) ----
    manifest_state: dict[str, Any] = {"present": False}
    for pf in panels:
        if pf["path"].endswith("panel_manifest.json"):
            try:
                pm = json.loads(Path(pf["path"]).read_text())
                ck = pm.get("checkpoints") or []
                manifest_state = {"present": True, "path": pf["path"], "sha256": pf["sha256"],
                                  "committed_utc": pm.get("utc"), "n_committed_checkpoints": pm.get("n", len(ck))}
            except (OSError, json.JSONDecodeError) as exc:
                manifest_state = {"present": True, "path": pf["path"], "error": str(exc)}
    out["panel_manifest_state"] = manifest_state

    # ---- blind labels: record EXISTENCE and TIMING only; contents are never opened ----
    label_dirs = sorted(glob.glob(str(ITER5 / "gen_art" / "*" / "results" / "labels")))
    lab: list[dict[str, Any]] = []
    for d in label_dirs:
        files = [Path(x) for x in glob.glob(d + "/*") if Path(x).is_file()]
        if files:
            mt = sorted(f.stat().st_mtime for f in files)
            lab.append({"dir": d, "n_files": len(files),
                        "earliest_write_utc": dt.datetime.fromtimestamp(mt[0], dt.timezone.utc).isoformat(),
                        "latest_write_utc": dt.datetime.fromtimestamp(mt[-1], dt.timezone.utc).isoformat()})
    out["blind_label_files"] = lab
    out["blind_label_policy"] = ("Label files are listed by name and write time ONLY; their contents are never "
                                 "opened by this artifact, so this backstop cannot leak a label into a survivor "
                                 "choice.")
    out["order_audit_note"] = (
        "Labels WRITTEN before a survivor exists is by design (the substrate grades blind). The invariant is "
        "that the survivor hash is committed before any label is READ by the join. A future join must show a "
        "committed survivor sha256 whose commit time precedes the join's first label read; a label file's write "
        "time is not evidence either way."
    )

    if not survivors:
        out["join_status"] = "COULD_NOT_COMPLETE"
        n_ck = manifest_state.get("n_committed_checkpoints")
        out["reason"] = (
            "Two independent gaps. (1) SCREEN: no survivor.json exists anywhere under iteration 5; the screen "
            "artifact (gen_art_experiment_1) has an EMPTY results/screen/ directory, so no hashed survivor has "
            "been committed. (2) SUBSTRATE: panel_manifest.json "
            + (f"is committed but lists n={n_ck} checkpoints that completed the gated pipeline"
               if manifest_state.get("present") else "is absent")
            + ". A join needs both sides and cannot be formed; a survivor is NEVER guessed."
        )
        out["hash_order_verified"] = False
        out["hash_order_note"] = (
            "Hash-order verification is VACUOUS while no survivor hash exists: the invariant "
            "'survivor hash committed before any panel label is read' cannot be checked, "
            "let alone satisfied."
        )
        out["panel_side_status"] = (
            "PRESENT" if panels else "ABSENT"
        )
        if panels:
            out["panel_side_note"] = (
                f"The substrate has committed its panel rule and draw ({len(panels)} file(s)) and is producing "
                "blind labels, but its manifest does not yet list completed checkpoints. Both sides are still "
                "in progress in parallel iteration-5 artifacts; this backstop records their state at run time."
            )
    else:
        out["join_status"] = "PARTIAL"
        out["reason"] = "Survivor file(s) located; see survivor_files_found. Join assembled below."
        # order check: survivor mtime must precede panel-label mtime
        s_m = min(f["mtime_epoch"] for f in survivors)
        p_m = min(f["mtime_epoch"] for f in panels) if panels else None
        out["hash_order_verified"] = bool(p_m is not None and s_m <= p_m)
        out["hash_order_note"] = (
            f"survivor earliest mtime {s_m} vs panel earliest mtime {p_m}; "
            "mtime is WEAK evidence — a committed hash_chain entry is the strong form."
        )
        joined = []
        for sf in survivors:
            try:
                joined.append({"survivor_file": sf["path"], "content": json.loads(Path(sf["path"]).read_text())})
            except (OSError, json.JSONDecodeError) as exc:
                joined.append({"survivor_file": sf["path"], "error": str(exc)})
        out["join"] = joined

    dest = WS / "results" / "join_backstop.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    with (WS / "build_log.txt").open("a") as fh:
        fh.write(
            f"{dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S+00:00')}  "
            f"D11_JOIN  status={out['join_status']}  survivors={len(survivors)}  panels={len(panels)}\n"
        )
    print(json.dumps({k: out[k] for k in ("join_status", "reason", "hash_order_verified")}, indent=2))
    print(f"survivor files: {len(survivors)}  panel files: {len(panels)}  chain files: {len(chains)}")


if __name__ == "__main__":
    main()
