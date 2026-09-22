"""Runner for the RELEASED AMS CLI (`ams scan`, pip package `ams-scanner` 0.1.3), installed in the
separate venv WS/.venv_ams. Shells out to `WS/.venv_ams/bin/ams scan <path> --json --device cpu`,
parses the JSON robustly (the CLI's banner/progress text can share stdout with the JSON blob
unless --quiet is passed), and returns/writes a small summary dict.

Usage as a library:
    from ams_run import run_ams_cli
    result = run_ams_cli("/path/to/local/hf/snapshot", mode=None, batch_size=8, timeout=600)

Usage as a CLI:
    WS/.venv/bin/python src/ams_run.py <snapshot_dir> --out <json_path> [--mode standard] \
        [--batch-size 8] [--timeout 600] [--device cpu]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from loguru import logger

WS = Path(__file__).resolve().parents[1]
AMS_BIN = WS / ".venv_ams" / "bin" / "ams"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)


def _extract_json_object(text: str) -> Optional[dict]:
    """Find the first well-formed JSON object in `text`, robust to banner/progress noise before
    or after it (rich's Console can still emit ANSI codes when writing to a pipe in some
    terminals, so we strip those first)."""
    text = _strip_ansi(text)
    decoder = json.JSONDecoder()
    start = 0
    while True:
        idx = text.find("{", start)
        if idx == -1:
            return None
        try:
            obj, _end = decoder.raw_decode(text, idx)
            return obj
        except json.JSONDecodeError:
            start = idx + 1


def run_ams_cli(
    model_path: str | Path,
    mode: Optional[str] = None,
    batch_size: int = 8,
    device: str = "cpu",
    dtype: Optional[str] = None,
    timeout: int = 600,
    ams_bin: Path = AMS_BIN,
    extra_args: Optional[list[str]] = None,
) -> dict:
    """Run `ams scan` on a local HF snapshot dir (or a HuggingFace hub id) and parse its --json
    output.

    mode: None -> use the CLI's own default ("standard": harmful_content, injection_resistance,
          refusal_capability). Pass "quick" or "full" to override.
    Returns a dict: {sigma_per_concept, overall, verdict, raw_json, elapsed_s, cmd, returncode}.
    """
    model_path = str(model_path)
    cmd = [str(ams_bin), "--device", device]
    if dtype:
        cmd += ["--dtype", dtype]
    cmd += ["--quiet", "scan", model_path, "--json", "--batch-size", str(batch_size)]
    if mode:
        cmd += ["--mode", mode]
    if extra_args:
        cmd += extra_args

    logger.info(f"Running: {' '.join(cmd)}")
    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - t0
        logger.error(f"ams scan timed out after {elapsed:.1f}s (limit {timeout}s)")
        return {
            "ok": False,
            "error": f"timeout after {timeout}s",
            "cmd": cmd,
            "elapsed_s": elapsed,
            "stdout_tail": (e.stdout or "")[-4000:] if e.stdout else "",
            "stderr_tail": (e.stderr or "")[-4000:] if e.stderr else "",
        }
    elapsed = time.time() - t0

    raw_json = _extract_json_object(proc.stdout)
    if raw_json is None:
        logger.error("Could not find a JSON object in `ams scan` stdout.")
        return {
            "ok": False,
            "error": "no JSON object found in stdout",
            "cmd": cmd,
            "elapsed_s": elapsed,
            "returncode": proc.returncode,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }

    safety_report = raw_json.get("safety_report", {})
    concept_results = safety_report.get("concept_results", {})
    sigma_per_concept = {
        name: {
            "separation": r.get("separation"),
            "threshold": r.get("threshold"),
            "passed": r.get("passed"),
            "optimal_layer": r.get("optimal_layer"),
            "safety_level": r.get("safety_level"),
        }
        for name, r in concept_results.items()
    }

    result = {
        "ok": True,
        "cmd": cmd,
        "elapsed_s": elapsed,
        "returncode": proc.returncode,
        "model_path": model_path,
        "scan_mode": safety_report.get("scan_mode"),
        "sigma_per_concept": sigma_per_concept,
        "overall_level": safety_report.get("overall_level"),
        "overall_safe": safety_report.get("overall_safe"),
        "recommendation": safety_report.get("recommendation"),
        "model_info": safety_report.get("model_info"),
        "scan_time_reported_by_ams": safety_report.get("scan_time"),
        "raw_json": raw_json,
    }
    sep_key = "separation"
    concept_summary = ", ".join(
        f"{k}={v[sep_key]:.2f}sigma" for k, v in sigma_per_concept.items()
    )
    logger.info(
        f"ams scan done in {elapsed:.1f}s: overall={result['overall_level']} ({concept_summary})"
    )
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the released AMS CLI and parse its JSON output.")
    ap.add_argument("model_path", help="Local HF snapshot dir or HuggingFace hub id")
    ap.add_argument("--out", type=Path, default=None, help="Write result JSON here")
    ap.add_argument("--mode", choices=["quick", "standard", "full"], default=None)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--dtype", default=None)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    result = run_ams_cli(
        args.model_path,
        mode=args.mode,
        batch_size=args.batch_size,
        device=args.device,
        dtype=args.dtype,
        timeout=args.timeout,
    )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2))
        logger.info(f"Wrote {args.out}")
    else:
        print(json.dumps(result, indent=2))

    if not result.get("ok"):
        sys.exit(1)


if __name__ == "__main__":
    main()
