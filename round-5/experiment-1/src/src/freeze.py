#!/usr/bin/env python3
"""S4: freeze the screen -> results/survivor.json (+ .sha256), chain stage S4.

Refuses to run if:
  - prescreen.json or rank_analysis.json is missing, or
  - the chain built so far (S1..S3b) does not verify (digests / stage order / monotone
    UTC+mtime) against what is currently on disk -- i.e. any chained file changed.

After writing survivor.json, verifies the WHOLE chain with
core.verify_chain(expected_order=["S1","S2","S3a","S3b","S4"]) (an S1-amendment stage may sit
between S1 and S2 -- the subsequence check tolerates that), asserts <logs-dir>/s3_open_audit.txt
contains none of the forbidden substrings, and writes results/order_proof.json.

CLI:
    .venv_gpu/bin/python src/freeze.py [--results-dir DIR] [--logs-dir DIR] [--force]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from loguru import logger

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import canonical_json, chain_append, sha256_text, utc_now, verify_chain, write_json  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")

FORBIDDEN = ["graded_truth", "classification", "aggregates", "panel_manifest",
             "gen_art_experiment_2", "judge", "truth", "sealed", "heldout"]

EXPECTED_ORDER_PRE = ["S1", "S2", "S3a", "S3b"]
EXPECTED_ORDER_FULL = ["S1", "S2", "S3a", "S3b", "S4"]

# module that produces each candidate's registered value, for scoring_ref.
CAND_MODULE = {
    "G1": "src/tierA.py::run_tag", "G2": "src/tierA.py::run_tag", "G3": "src/tierA.py::run_tag",
    "G4": "src/tierA.py::run_tag", "A3": "src/tierA.py::run_tag",
    "A1": "src/assemble_screen.py::compute_a1_joint (PC1 of Tier-A A1_slope + Tier-B A1_prior)",
    "A2": "src/tierB.py::run_checkpoint",
    "W1": "src/tierB.py::run_checkpoint", "W2": "src/tierB.py::run_checkpoint",
    "W3": "src/tierB.py::run_checkpoint", "W4": "src/tierB.py::run_checkpoint",
    "W5": "src/tierB.py::run_checkpoint", "W6": "src/tierB.py::run_checkpoint",
    "W7": "src/tierB.py::run_checkpoint (or src/tierA.py::run_tag W7c fallback -- see flags)",
    "W8": "src/tierB.py::run_checkpoint",
}


def load_required(results_dir: Path) -> tuple[dict, dict, dict]:
    missing = [n for n in ("prescreen.json", "rank_analysis.json") if not (results_dir / n).exists()]
    if missing:
        raise SystemExit(f"refusing to freeze: missing {missing} under {results_dir}")
    prescreen = json.loads((results_dir / "prescreen.json").read_text())
    rank = json.loads((results_dir / "rank_analysis.json").read_text())
    prereg_path = results_dir / "prereg.json"
    prereg = json.loads(prereg_path.read_text()) if prereg_path.exists() else {}
    return prescreen, rank, prereg


def sort_key(entry: dict) -> tuple:
    """Ranked by |rho_BL1_easy| ascending; ties -> fewer prompts, then Tier A before Tier B."""
    rho = entry["rho_BL1_easy"]
    rho_abs = abs(rho) if rho is not None else float("inf")
    n_prompts = entry.get("n_prompts")
    n_prompts_key = n_prompts if n_prompts is not None else float("inf")
    tier = entry.get("tier") or ""
    tier_key = 0 if tier.strip().upper().startswith("A") else 1
    return (rho_abs, n_prompts_key, tier_key)


def build_survivors(prescreen: dict, prereg: dict, screen_table: dict | None) -> list[dict]:
    n_prompts_by_cand: dict[str, int | None] = {}
    if screen_table is not None:
        for r in screen_table.get("rows", []):
            c = r.get("candidate")
            if c not in n_prompts_by_cand and r.get("n_prompts") is not None:
                n_prompts_by_cand[c] = r.get("n_prompts")

    d_candidates = prereg.get("d_candidates", {})
    survivors = []
    for cand, rec in prescreen.get("candidates", {}).items():
        if rec.get("status") != "KEPT":
            continue
        d = d_candidates.get(cand, {})
        flags = []
        stable = rec.get("stable_flags", {})
        if stable.get("sign_agree_frac") is not None and stable["sign_agree_frac"] < 0.80:
            flags.append("sign_unstable (<80% draw agreement)")
        survivors.append({
            "candidate": cand,
            "rho_BL1_easy": rec.get("rho"),
            "tier": rec.get("tier"),
            "band_rule": d.get("band"),
            "site": d.get("site"),
            "expected_sign": d.get("expected_sign", {}),
            "scoring_ref": f"{CAND_MODULE.get(cand, 'UNKNOWN')} + prereg d_candidates.{cand}",
            "n_prompts": n_prompts_by_cand.get(cand),
            "flags": flags,
            "prescreen_ci": rec.get("ci"),
            "prescreen_n": rec.get("n"),
            "prescreen_mde": rec.get("mde"),
        })

    survivors.sort(key=sort_key)
    for i, s in enumerate(survivors):
        s["rank"] = i + 1
    return survivors


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=WS / "results")
    ap.add_argument("--logs-dir", type=Path, default=WS / "logs")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    results_dir = args.results_dir.resolve()
    logs_dir = args.logs_dir.resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.add(logs_dir / "freeze.log", rotation="10 MB", level="DEBUG")

    survivor_path = results_dir / "survivor.json"
    if survivor_path.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing {survivor_path} (pass --force)")

    prescreen, rank, prereg = load_required(results_dir)

    chain_path = results_dir / "hashchain.jsonl"
    pre_check = verify_chain(chain_path, results_dir, expected_order=EXPECTED_ORDER_PRE)
    if not pre_check["ok"]:
        raise SystemExit(f"refusing to freeze: chain S1..S3b does not verify: {pre_check}")
    logger.info("pre-freeze chain check (S1..S3b) OK: digests/order/monotonicity all verified")

    screen_table = None
    st_path = results_dir / "screen_table.json"
    if st_path.exists():
        screen_table = json.loads(st_path.read_text())

    survivors = build_survivors(prescreen, prereg, screen_table)
    if survivors:
        payload = {"utc": utc_now(), "survivors": survivors, "n_survivors": len(survivors),
                   "n_prescreen_kept": prescreen.get("n_kept"), "n_prescreen_dropped": prescreen.get("n_dropped"),
                   "rank_analysis_verdict": rank.get("verdict")}
        logger.info(f"{len(survivors)} survivor(s): " + ", ".join(s["candidate"] for s in survivors))
    else:
        payload = {"utc": utc_now(), "survivors": "NONE",
                   "n_prescreen_kept": prescreen.get("n_kept"), "n_prescreen_dropped": prescreen.get("n_dropped"),
                   "rank_analysis_verdict": rank.get("verdict")}
        logger.warning("NO survivors -- P1_WINS: THE BOUND")

    digest = write_json(survivor_path, payload)
    (results_dir / "survivor.sha256").write_text(digest)
    rec = chain_append(chain_path, "S4", survivor_path, digest)
    logger.info(f"wrote {survivor_path} sha256={digest[:16]} chain={rec['stage']}")

    full_check = verify_chain(chain_path, results_dir, expected_order=EXPECTED_ORDER_FULL)

    audit_log = logs_dir / "s3_open_audit.txt"
    audit_clean, audit_violations = True, []
    if audit_log.exists():
        text = audit_log.read_text()
        for bad in FORBIDDEN:
            if bad in text:
                audit_clean = False
                audit_violations.append(bad)
    else:
        audit_clean = False
        audit_violations = ["MISSING: " + str(audit_log)]

    order_proof = {
        "utc": utc_now(),
        "chain_verify": full_check,
        "expected_order": EXPECTED_ORDER_FULL,
        "audit_log_path": str(audit_log),
        "audit_log_clean": audit_clean,
        "audit_log_forbidden_hits": audit_violations,
        "freeze_ok": bool(full_check["ok"] and audit_clean),
    }
    write_json(results_dir / "order_proof.json", order_proof)
    logger.info(f"order_proof: chain_ok={full_check['ok']} audit_clean={audit_clean} "
                f"-> {results_dir / 'order_proof.json'}")

    if not order_proof["freeze_ok"]:
        raise SystemExit(f"FREEZE INTEGRITY FAILURE: {order_proof}")


if __name__ == "__main__":
    main()
