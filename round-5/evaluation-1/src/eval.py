"""Top-level driver for the iteration-5 re-derivation audit.

Runs every deliverable script in order, then the contradictions ledger, the S12
self-check gate, eval_out.json and the write-up. Each stage is independent and a
failure in one is recorded rather than aborting the rest, so a late-running
deliverable never costs the artifact the ones that already finished.

    .venv/bin/python eval.py
"""

from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
SRC = WS / "src"
PY = str(WS / ".venv" / "bin" / "python")

# scipy crawls when the cgroup quota disagrees with the visible CPU count.
ENV = {
    **os.environ,
    "OMP_NUM_THREADS": "4",
    "OPENBLAS_NUM_THREADS": "4",
    "MKL_NUM_THREADS": "4",
    "NUMEXPR_NUM_THREADS": "4",
    "PYTHONPATH": str(SRC),
}

# Order matters where one stage reads another's output:
#   d4_denominators augments D4 and needs d1_d2_d4;
#   adjudicate_ledger reads D4-addendum, D8 and D10 tables.
DELIVERABLE_STAGES = [
    ("D1/D2/D4  composition, degeneracy, candidates", "d1_d2_d4.py"),
    ("D4 add.   sensitivity at 10 and 11 effective pairs", "d4_denominators.py"),
    ("D3/D7/D9  variants, few-prompt, geometry", "d3_d7_d9.py"),
    ("D7 add.   power for the paired correlation difference", "d7_power.py"),
    ("D5/D6     causal grid, equivalence", "d5_d6.py"),
    ("          fig2 causal effects", "fig2_causal_effects.py"),
    ("D8/D10    displacement, setup and deviations", "d8_d10.py"),
    ("D11       backstop confirmation join", "d11_join.py"),
]

FINAL_STAGES = [
    ("S13       ledger adjudication under the frozen rule", "adjudicate_ledger.py"),
    ("S13/S12   ledger merge and self-check gate", "assemble.py"),
    ("          eval_out.json", "build_eval_out.py"),
    ("          key findings from the metrics", "key_findings.py"),
    ("          SUMMARY.md and README.md", "write_summary.py"),
    # Gate rule (b) scans SUMMARY.md, which only exists in final form after
    # write_summary. Re-run the gate on the final text, then rebuild eval_out.json
    # so its recorded gate verdict is the verdict on what actually ships.
    ("S12       FINAL gate on the finished SUMMARY.md", "assemble.py"),
    ("          eval_out.json with the final gate verdict", "build_eval_out.py"),
    ("          SUMMARY.md with the final gate verdict", "write_summary.py"),
]


def run(label: str, script: str, *, required: bool) -> bool:
    path = SRC / script
    if not path.exists():
        print(f"[SKIP] {label}: {script} not present")
        return False
    print(f"[RUN ] {label}  ({script})", flush=True)
    proc = subprocess.run([PY, str(path)], cwd=str(WS), env=ENV, check=False)
    ok = proc.returncode == 0
    # assemble.py exits non-zero when the gate fails; that is a reportable
    # outcome, not a crash, so it never stops the pipeline.
    print(f"[{'OK  ' if ok else 'FAIL'}] {label} (exit {proc.returncode})", flush=True)
    if not ok and required:
        print(f"       continuing: {script} failed but later stages still produce output")
    return ok


def main() -> int:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    with (WS / "build_log.txt").open("a") as fh:
        fh.write(f"{stamp}  EVAL_DRIVER_START\n")

    results: dict[str, bool] = {}
    for i, (label, script) in enumerate(DELIVERABLE_STAGES):
        results[f"{i:02d}:{script}"] = run(label, script, required=False)
    for i, (label, script) in enumerate(FINAL_STAGES):
        results[f"F{i:02d}:{script}"] = run(label, script, required=True)

    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    ok_n = sum(results.values())
    with (WS / "build_log.txt").open("a") as fh:
        fh.write(f"{stamp}  EVAL_DRIVER_END  {ok_n}/{len(results)} stages exited 0\n")

    print(f"\n{ok_n}/{len(results)} stages exited 0")
    print("Read SUMMARY.md for the contradictions list and the claim match rate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
