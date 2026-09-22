#!/usr/bin/env python3
"""T0 PATH AUDIT -- os.path.exists() every absolute path the artifact plan names.

Run BEFORE planning around any of these paths.  None of them is a declared
dependency, so none is handed to us; they are read from disk read-only.  Any
MISSING entry must be logged as a deviation before it is worked around.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path

WS = Path(__file__).resolve().parent.parent
RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D")
IL = RUN / "3_invention_loop"
P = IL / "iter_4/gen_art/gen_art_experiment_2/prior_session_confirm_panel"
H1 = IL / "iter_4/gen_art/gen_art_experiment_1"
D1 = IL / "iter_1/gen_art/gen_art_dataset_1"
D2 = IL / "iter_2/gen_art/gen_art_dataset_1"
RES4 = IL / "iter_4/gen_art/gen_art_research_1"

PATHS: list[tuple[str, Path]] = [
    ("P.tree", P), ("P.src", P / "src"),
    ("P.src/panel.py", P / "src/panel.py"), ("P.src/gen.py", P / "src/gen.py"),
    ("P.src/harvest_confirm.py", P / "src/harvest_confirm.py"),
    ("P.src/harvest_panel.py (MUST NOT RUN)", P / "src/harvest_panel.py"),
    ("P.src/judge.py", P / "src/judge.py"),
    ("P.src/time_rule.py", P / "src/time_rule.py"),
    ("P.src/unit_checks.py", P / "src/unit_checks.py"),
    ("P.src/verify_hooks.py", P / "src/verify_hooks.py"),
    ("P.src/ams_reimpl.py", P / "src/ams_reimpl.py"),
    ("P.pyproject.toml", P / "pyproject.toml"),
    ("H1.tree", H1), ("H1.restore.sh", H1 / "restore.sh"), ("H1.src", H1 / "src"),
    ("H1.src/ncands.py", H1 / "src/ncands.py"),
    ("H1.src/harvest_variants.py", H1 / "src/harvest_variants.py"),
    ("H1.src/judge.py", H1 / "src/judge.py"),
    ("H1.src/truth_classify.py", H1 / "src/truth_classify.py"),
    ("H1.src/gen_variants.py", H1 / "src/gen_variants.py"),
    ("H1.src/ams_reimpl.py", H1 / "src/ams_reimpl.py"),
    ("H1.harvest", H1 / "harvest"), ("H1.harvest/F1__ref", H1 / "harvest/F1__ref"),
    ("H1.results/graded_truth.json", H1 / "results/graded_truth.json"),
    ("H1.results/classification.json", H1 / "results/classification.json"),
    ("H1.env/requirements_gpu.txt", H1 / "env/requirements_gpu.txt"),
    ("H1.assets/stimuli.json", H1 / "assets/stimuli.json"),
    ("H1.assets/cells.json", H1 / "assets/cells.json"),
    ("H1.assets/c11_items.json", H1 / "assets/c11_items.json"),
    ("H1.assets/behaviour_items.json", H1 / "assets/behaviour_items.json"),
    ("H1.assets/token_sets.json", H1 / "assets/token_sets.json"),
    ("H1.assets/side_sets.json", H1 / "assets/side_sets.json"),
    ("D1.data_out.json", D1 / "data_out.json"),
    ("D1.heldout_cells.json", D1 / "heldout_cells.json"),
    ("D1.rubric.md", D1 / "rubric.md"),
    ("D1.prereg.json", D1 / "prereg.json"),
    ("D1.model_registry.json", D1 / "model_registry.json"),
    ("D1.full_data_out.json", D1 / "full_data_out.json"),
    ("D2.full_data_out.json", D2 / "full_data_out.json"),
    ("J.lc_judge.py", IL / "iter_1/gen_art/gen_art_experiment_3/lc_judge.py"),
    ("RESEARCH.research_out.json", RES4 / "research_out.json"),
    ("USER_UPLOADS", RUN / "user_uploads"),
]


def main() -> int:
    rows = []
    for name, p in PATHS:
        ok = p.exists()
        size = None
        if ok:
            try:
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.is_dir() else p.stat().st_size
            except OSError:
                size = None
        rows.append({"name": name, "path": str(p), "status": "PASS" if ok else "MISSING",
                     "is_dir": p.is_dir() if ok else None, "bytes": size})

    du = {}
    for label, mp in (("workspace_mount", WS), ("container_root", Path("/"))):
        try:
            t, u, f = shutil.disk_usage(mp)
            du[label] = {"total_gb": round(t / 2**30, 1), "used_gb": round(u / 2**30, 1),
                         "free_gb": round(f / 2**30, 1)}
        except OSError as e:
            du[label] = {"error": str(e)}

    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,driver_version",
             "--format=csv,noheader"], capture_output=True, text=True, timeout=60)
        gpu = smi.stdout.strip() or smi.stderr.strip()
    except (OSError, subprocess.SubprocessError) as e:
        gpu = f"ERROR {e}"

    missing = [r["name"] for r in rows if r["status"] == "MISSING"]
    payload = {
        "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_checked": len(rows), "n_pass": len(rows) - len(missing), "n_missing": len(missing),
        "missing": missing, "rows": rows, "disk": du, "nvidia_smi": gpu,
        "cpu_count_os": os.cpu_count(),
        "note": "Every MISSING entry must have a numbered deviation in results/deviations.json "
                "BEFORE it is planned around. P.src/harvest_panel.py is expected to PASS and is "
                "listed only so the record shows it was found and deliberately NOT run (it is "
                "iteration-3 leftover with the order gate REVERSED).",
    }
    out = WS / "results" / "asset_audit.json"
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    os.replace(tmp, out)
    for r in rows:
        if r["status"] == "MISSING":
            print(f"  MISSING  {r['name']}  {r['path']}")
    print(f"T0 asset audit: {payload['n_pass']}/{payload['n_checked']} PASS, "
          f"{payload['n_missing']} MISSING")
    print(f"disk: {json.dumps(du)}")
    print(f"gpu: {gpu}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
