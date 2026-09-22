"""Validate the RELEASED ams-scanner CLI (ams-scanner==0.1.3, installed in WS/.venv_ams) against
our numpy reimplementation (WS/src/reuse/ams_reimpl.py, via WS/src/reuse/ncands.py), on a small
validation subset: the 3 panel models F1__ref (Qwen/Qwen3-0.6B), F2__ref
(unsloth/Llama-3.2-1B-Instruct), HG__tiiuae--Falcon3-1B-Base (tiiuae/Falcon3-1B-Base).

For each model:
  - runs `ams scan <repo> --mode standard --batch-size 1 --json` (CLI's bug-free, no-padding
    setting) and `--batch-size 8` (CLI's own default, subject to the known padding_side="right"-
    without-override last-token bug on batch>1 documented in iter_4's ams_package_notes.md),
  - extracts the harmful_content concept's separation ("sigma"), optimal_layer, and wall time,
  - records the tokenizer's default padding_side (queried directly, no model forward pass),
  - loads that model's already-harvested A_ams.npy (iter_4 harvest, read-only) via ncands.Ckpt +
    ams_reimpl.ams_tier1 to get the reimpl's own harmful_content-only sigma (apples-to-apples with
    the CLI's single-concept number), AND records the mean-of-3-concepts bars.AMS_T1_sigma value
    already on disk (WS/results/screen/tierA/<tag>.json) as the task explicitly asks to diff
    against.
  - diffs (abs/rel) both reimpl numbers against cli_b1 and cli_b8.

Also runs ONE cheap Tier-2 (identity verification) pair on CPU: `ams baseline create` for
Qwen/Qwen3-0.6B (F1__ref's repo), then `ams scan huihui-ai/Huihui-Qwen3-0.6B-abliterated-v2
--verify Qwen/Qwen3-0.6B --json`, both batch-size 8 standard mode (Tier-2 has no batch-size-1 mode
of its own in the package).

CPU only (CUDA_VISIBLE_DEVICES="" set below, before any torch import happens in this process or
its subprocesses), <=3 threads, one model resident at a time (the CLI is always invoked as a
fresh subprocess so nothing but this driver script itself is resident between calls).

Per-model time budget: 12 minutes (720s) for the two `ams scan` calls combined; if exceeded, the
model's CLI entries are recorded as "TIMEOUT" and the script moves on. Total script time budget:
40 minutes (soft; enforced only between models, never mid-subprocess-call other than the per-call
subprocess timeout itself).

Writes WS/results/ams_cli_validation.json after each model (resumable / partial-safe).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["OMP_NUM_THREADS"] = "3"
os.environ["MKL_NUM_THREADS"] = "3"

WS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WS / "src"))
sys.path.insert(0, str(WS / "src" / "reuse"))

from loguru import logger  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(str(WS / "logs" / "ams_cli_validation.log"), rotation="5 MB", level="DEBUG")

AMS_BIN = WS / ".venv_ams" / "bin" / "ams"
AMS_PY = WS / ".venv_ams" / "bin" / "python"
ITER4 = WS.parent.parent.parent / "iter_4" / "gen_art" / "gen_art_experiment_1"
HARVEST_DIR = ITER4 / "harvest"
BASELINES_DIR = WS / "private" / "ams_cli_validation_baselines"
TIERA_DIR = WS / "results" / "screen" / "tierA"
OUT_PATH = WS / "results" / "ams_cli_validation.json"

PANEL = [
    ("F1__ref", "Qwen/Qwen3-0.6B"),
    ("F2__ref", "unsloth/Llama-3.2-1B-Instruct"),
    ("HG__tiiuae--Falcon3-1B-Base", "tiiuae/Falcon3-1B-Base"),
]
TIER2_PARENT = "Qwen/Qwen3-0.6B"           # == F1__ref's repo
TIER2_CHILD = "huihui-ai/Huihui-Qwen3-0.6B-abliterated-v2"

PER_MODEL_BUDGET_S = 12 * 60
CONCEPT = "harmful_content"


def _run_ams_cli(args: list[str], timeout: int) -> tuple[int | str, str, str, float, list[str]]:
    env = dict(os.environ)
    env["OMP_NUM_THREADS"] = "3"
    env["MKL_NUM_THREADS"] = "3"
    env["CUDA_VISIBLE_DEVICES"] = ""
    cmd = [str(AMS_BIN), *args]
    logger.info(f"running: {' '.join(cmd)}")
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        logger.warning(f"  TIMEOUT after {dt:.1f}s (limit {timeout}s)")
        return "TIMEOUT", "", "", dt, cmd
    dt = time.time() - t0
    logger.info(f"  exit={proc.returncode} in {dt:.1f}s")
    if proc.returncode != 0:
        # cli.py:306-312 (cmd_scan) encodes overall_level in the exit code (1/2/3 =
        # CRITICAL/WARNING/verify_failed), AFTER already printing valid --json -- not a crash.
        logger.info(f"  non-zero exit (may be the scan/verify result-encoding convention): "
                    f"stderr tail: {proc.stderr[-1000:]}")
    return proc.returncode, proc.stdout, proc.stderr, dt, cmd


def _extract_json(stdout: str) -> dict:
    idx = stdout.find("{")
    if idx == -1:
        raise ValueError(f"no JSON object in CLI stdout: {stdout[:800]!r}")
    return json.loads(stdout[idx:])


def _padding_side(repo: str) -> dict:
    script = (
        "import json\n"
        "from transformers import AutoTokenizer\n"
        f"tok = AutoTokenizer.from_pretrained({repo!r})\n"
        "print(json.dumps({'padding_side': tok.padding_side, "
        "'pad_token_was_none': tok.pad_token is None}))\n"
    )
    proc = subprocess.run(
        [str(AMS_PY), "-c", script], capture_output=True, text=True,
        env={**os.environ, "CUDA_VISIBLE_DEVICES": "", "OMP_NUM_THREADS": "3", "MKL_NUM_THREADS": "3"},
        timeout=180,
    )
    if proc.returncode != 0:
        return {"error": proc.stderr[-800:]}
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _reimpl_harmful_content_sigma(tag: str) -> dict:
    """Pure-numpy reimpl sigma for JUST harmful_content, computed from the tag's already-harvested
    A_ams.npy (iter_4 harvest, read-only) -- apples-to-apples with the CLI's single-concept number.
    Uses .venv_ams's python (has numpy; this reimpl code imports numpy only, no torch)."""
    tag_dir = HARVEST_DIR / tag
    script = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(WS / 'src' / 'reuse')!r})\n"
        "import ncands, ams_reimpl\n"
        f"ckpt = ncands.Ckpt.load({tag!r}, {str(tag_dir)!r})\n"
        "prompts = ams_reimpl.ams_prompts()\n"
        "res = ams_reimpl.ams_tier1(ckpt.A_ams, prompts, ckpt.L)\n"
        "c = res['per_concept']['harmful_content']\n"
        "print(json.dumps({'sigma': c['sigma'], 'optimal_layer': c['optimal_layer'], "
        "'L': ckpt.L, 'mean_sigma_3concepts': res['mean_sigma']}))\n"
    )
    proc = subprocess.run([str(AMS_PY), "-c", script], capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        return {"error": proc.stderr[-1200:]}
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _bars_ams_t1_sigma(tag: str) -> dict:
    p = TIERA_DIR / f"{tag}.json"
    if not p.exists():
        return {"error": f"{p} not found"}
    d = json.loads(p.read_text())
    return {"AMS_T1_sigma": d["bars"].get("AMS_T1_sigma"), "meta": d["bars"].get("AMS_T1_sigma_meta")}


def _load_checkpoint() -> dict:
    if OUT_PATH.exists():
        try:
            return json.loads(OUT_PATH.read_text())
        except Exception as e:  # noqa: BLE001
            logger.warning(f"could not parse existing {OUT_PATH}: {e!r}, starting fresh")
    return {}


def _write(result: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=2))
    tmp.replace(OUT_PATH)
    logger.info(f"checkpointed {OUT_PATH}")


def _process_model(tag: str, repo: str) -> dict:
    row: dict = {"repo": repo}
    row["padding_side"] = _padding_side(repo)
    row["reimpl_harmful_content"] = _reimpl_harmful_content_sigma(tag)
    row["bars_AMS_T1_sigma_mean3concepts"] = _bars_ams_t1_sigma(tag)

    t_model0 = time.time()
    for bs_tag, bs in [("cli_b1", 1), ("cli_b8", 8)]:
        remaining = PER_MODEL_BUDGET_S - (time.time() - t_model0)
        if remaining <= 5:
            row[bs_tag] = "TIMEOUT (per-model budget exhausted before this call started)"
            row[f"{bs_tag}_layer"] = None
            row[f"{bs_tag}_runtime_s"] = None
            continue
        rc, out, err, dt, cmd = _run_ams_cli(
            ["-q", "--device", "cpu", "--dtype", "float32",
             "--baselines-dir", str(BASELINES_DIR),
             "scan", repo, "--mode", "standard", "--batch-size", str(bs), "--json"],
            timeout=int(min(remaining, PER_MODEL_BUDGET_S)),
        )
        row[f"{bs_tag}_cmd"] = " ".join(cmd)
        row[f"{bs_tag}_runtime_s"] = dt
        if rc == "TIMEOUT":
            row[bs_tag] = "TIMEOUT"
            row[f"{bs_tag}_layer"] = None
            continue
        try:
            pkg = _extract_json(out)
        except ValueError as e:
            row[bs_tag] = f"ERROR: {e}; stderr tail: {err[-1000:]}"
            row[f"{bs_tag}_layer"] = None
            continue
        cres = pkg["safety_report"]["concept_results"][CONCEPT]
        row[bs_tag] = cres["separation"]
        row[f"{bs_tag}_layer"] = cres["optimal_layer"]
        row[f"{bs_tag}_overall_level"] = pkg["safety_report"]["overall_level"]
        logger.info(f"  {tag} {bs_tag}: sigma={cres['separation']:.4f} layer={cres['optimal_layer']}")

    # diffs: reimpl (harmful_content-only AND the mean-of-3 bars value) vs cli_b1 / cli_b8
    reimpl_hc = row["reimpl_harmful_content"].get("sigma") if isinstance(row["reimpl_harmful_content"], dict) else None
    bars_v = row["bars_AMS_T1_sigma_mean3concepts"].get("AMS_T1_sigma") if isinstance(row["bars_AMS_T1_sigma_mean3concepts"], dict) else None

    def _diff(cli_val, ref_val):
        if not isinstance(cli_val, (int, float)) or ref_val is None:
            return None
        d = abs(cli_val - ref_val)
        rel = d / abs(ref_val) if abs(ref_val) > 1e-8 else float("inf")
        return {"abs": d, "rel": rel}

    row["diff_b1_vs_reimpl_harmful_content"] = _diff(row.get("cli_b1"), reimpl_hc)
    row["diff_b8_vs_reimpl_harmful_content"] = _diff(row.get("cli_b8"), reimpl_hc)
    row["diff_b1_vs_bars_AMS_T1_sigma"] = _diff(row.get("cli_b1"), bars_v)
    row["diff_b8_vs_bars_AMS_T1_sigma"] = _diff(row.get("cli_b8"), bars_v)
    row["total_model_runtime_s"] = time.time() - t_model0
    return row


def _tier2() -> dict:
    logger.info("Tier-2: baseline create (parent) + scan --verify (child), batch-size 8 standard")
    rc_c, out_c, err_c, dt_c, cmd_c = _run_ams_cli(
        ["--device", "cpu", "--dtype", "float32", "--baselines-dir", str(BASELINES_DIR),
         "baseline", "create", TIER2_PARENT, "--mode", "standard", "--batch-size", "8"],
        timeout=PER_MODEL_BUDGET_S,
    )
    if rc_c != 0:
        return {"error": f"baseline create failed (rc={rc_c}): {err_c[-1000:]}", "runtime_s": dt_c}
    rc_v, out_v, err_v, dt_v, cmd_v = _run_ams_cli(
        ["-q", "--device", "cpu", "--dtype", "float32", "--baselines-dir", str(BASELINES_DIR),
         "scan", TIER2_CHILD, "--verify", TIER2_PARENT, "--mode", "standard", "--batch-size", "8",
         "--json"],
        timeout=PER_MODEL_BUDGET_S,
    )
    if rc_v == "TIMEOUT":
        return {"error": "TIMEOUT on verify scan", "baseline_create_runtime_s": dt_c}
    try:
        pkg = _extract_json(out_v)
    except ValueError as e:
        return {"error": f"{e}; stderr tail: {err_v[-1000:]}",
                "baseline_create_runtime_s": dt_c, "verify_runtime_s": dt_v}
    vr = pkg["verification_report"]
    return {
        "parent": TIER2_PARENT, "child": TIER2_CHILD,
        "baseline_create_runtime_s": dt_c, "verify_runtime_s": dt_v,
        "exit_code": rc_v, "verified": vr["verified"], "checks": vr["checks"],
        "cmd_baseline_create": " ".join(cmd_c), "cmd_verify": " ".join(cmd_v),
    }


def main():
    BASELINES_DIR.mkdir(parents=True, exist_ok=True)
    result = _load_checkpoint()
    result.setdefault("objective", (
        "Compare the RELEASED ams-scanner CLI (0.1.3) Tier-1 harmful_content scan at "
        "batch-size 1 vs 8 against our numpy reimpl (ams_reimpl.ams_tier1) and the "
        "pre-computed bars.AMS_T1_sigma (mean of 3 standard concepts), on 3 panel models."
    ))
    result.setdefault("per_model", {})
    result.setdefault("notes", [])
    t_script0 = time.time()

    for tag, repo in PANEL:
        if result["per_model"].get(tag, {}).get("_complete"):
            logger.info(f"skipping {tag} (already complete)")
            continue
        logger.info(f"=== {tag} ({repo}) === elapsed so far {time.time()-t_script0:.0f}s")
        row = _process_model(tag, repo)
        row["_complete"] = True
        result["per_model"][tag] = row
        _write(result)

    if "tier2" not in result or not result["tier2"].get("_complete"):
        result["tier2"] = _tier2()
        result["tier2"]["_complete"] = True
        _write(result)

    result["notes"].append(
        "Falcon3 model used is tiiuae/Falcon3-1B-BASE (per task spec), NOT the -Instruct variant "
        "iter_4's validate_ams.py used -- Base's harvest under iter_4/harvest/HG__tiiuae--Falcon3-1B-Base "
        "was reused read-only for the reimpl side; the CLI side scans the Base repo directly."
    )
    result["notes"].append(
        "reimpl comparison is reported TWO ways: (a) reimpl_harmful_content (single-concept, "
        "apples-to-apples with the CLI's own harmful_content separation) computed fresh from the "
        "harvested A_ams.npy via ams_reimpl.ams_tier1; (b) bars_AMS_T1_sigma_mean3concepts, the "
        "task-specified WS/results/screen/tierA/<tag>.json bars.AMS_T1_sigma value, which is a MEAN "
        "over harmful_content+injection_resistance+refusal_capability, not harmful_content alone -- "
        "expect it to differ from the CLI's single-concept number even when the reimpl formula is "
        "bit-identical to the package's, and diff_*_vs_bars_AMS_T1_sigma reflects that scope mismatch, "
        "not disagreement."
    )
    result["total_runtime_s"] = time.time() - t_script0
    _write(result)
    logger.info(f"DONE in {result['total_runtime_s']:.0f}s -> {OUT_PATH}")


if __name__ == "__main__":
    main()
