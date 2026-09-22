#!/usr/bin/env python3
"""Exercise run_analysis end-to-end (gates -> S1 -> judge -> method_out.json -> SUMMARY.md)
against the SMOKE harvest, so write_outputs and the schema are validated before the real
panel finishes.  Writes to out_test/ and cleans up the temporary harvest tags."""
import json, shutil, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
from loguru import logger
import run_analysis as RA

SRC = HERE / "harvest" / "_smoke" / "Qwen3-0.6B"
TAGS = ["ZZTEST-target", "ZZTEST-arm1", "ZZTEST-arm2"]

# stage three copies of the smoke harvest so the arm logic has something to compare
for t in TAGS:
    d = HERE / "harvest" / t
    if d.exists():
        shutil.rmtree(d)
    shutil.copytree(SRC, d)
    m = json.loads((d / "meta.json").read_text())
    m["tag"] = t
    m["role"] = f"TEST {t}"
    (d / "meta.json").write_text(json.dumps(m, indent=2))

RA.BAND_TARGET_TAG = TAGS[0]
RA.NON_SAFETY_ARMS = (TAGS[1], TAGS[2])
RA.TARGET_MAP = {"Qwen3-4B": TAGS[0], "Qwen3-4B-SafeRL": TAGS[0]}
RA.OUT = HERE / "out_test"
RA.REL = RA.OUT / "released"
RA.REL.mkdir(parents=True, exist_ok=True)

# the substrate must be trimmed to the smoke's 8 items for the row maths to line up
sub_path = HERE / "items" / "substrate.json"
orig = sub_path.read_text()
sub = json.loads(orig)
n = json.loads((SRC / "meta.json").read_text())["n_items"]
keep = {t["item_id"] for t in sub["confirmatory_items"][:n]}
sub["confirmatory_items"] = sub["confirmatory_items"][:n]
sub["pilot_item_ids"] = [i for i in sub["pilot_item_ids"] if i in keep]
sub["ladder"] = [r for r in sub["ladder"] if r["item_id"] in keep]
sub_path.write_text(json.dumps(sub, indent=2))

try:
    res = RA.run_analysis(skip_judge=False)
    print("\nS1:", [(r["candidate"], r.get("S1")) for r in res["s1_table"]])
    print("judge:", {k: v for k, v in res["G8_judge"].items() if k != "per_item"})
    mo = RA.OUT / "method_out.json"
    print("method_out.json bytes:", mo.stat().st_size)
    d = json.loads(mo.read_text())
    print("datasets:", [(x["dataset"], len(x["examples"])) for x in d["datasets"]])
    print("SUMMARY.md bytes:", (RA.OUT / "SUMMARY.md").stat().st_size)
    print("\nFULL OUTPUT TEST OK")
finally:
    sub_path.write_text(orig)
    for t in TAGS:
        shutil.rmtree(HERE / "harvest" / t, ignore_errors=True)
