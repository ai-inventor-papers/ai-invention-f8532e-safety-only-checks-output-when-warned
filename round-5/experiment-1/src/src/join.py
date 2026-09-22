#!/usr/bin/env python3
"""S5: confirmation join. Runs ONLY if results/survivor.sha256 exists and the chain verifies.

Schema-adaptive: the confirmation manifest's schema is unknown until after the freeze (it lives in
the blind sibling artifact, gen_art_experiment_2, never opened before now). This module:
  1. globs for panel_manifest.json under every OTHER iter_5 gen_art_* results dir, inspects and
     RECORDS the schema it finds (results/confirm/manifest_schema.json) before assuming anything,
     tries to interpret each checkpoint entry as the iteration-4 27-file harvest layout (the same
     file set `src/tierA.py`/`src/ASSETS.md` document: A_prompt/A_c11/A_dec/A_dec_tok1/A_ams/
     A_prompt_p1..3, WU_ref/hed/ctl, gamma, hbar/hbar_all/mu_U, r_refusal/hedge/control/fullV_final,
     norms, vmin_stacked/onesproj/lambda, dec_ntok, token_ids.json, meta.json,
     MANIFEST.sha256.json, DONE == 27 entries), and FAILS LOUDLY (SystemExit, with the recorded
     schema attached) for anything it cannot interpret -- it never guesses silently.
  2. asserts the confirmation-panel / screen-panel intersection (by repo id) is EMPTY, and that the
     OR column is non-degenerate (else CONFIRMATION = UNINFORMATIVE).
  3. scores the FROZEN survivors (Tier-A candidates directly from the 27-file arrays with THIS
     artifact's own math; Tier-B candidates via `tierB.score_external_checkpoint` if that hook
     exists, else marked TIER_B_EXTERNAL_UNAVAILABLE -- tierB.py's external-checkpoint mode is not
     part of this deliverable and was not found on disk at the time this ran) -- BL1_easy and AMS_T1
     on the SAME checkpoints (pairing assertion).
  4. selection rule (ii)-(vii): primary/co-primary Spearman + paired-bootstrap margins + partial rho
     (statlib, exact), McNemar 15-pair/12-pair on the SCREEN panel's structural pairs (reads
     classification.json -- ONLY HERE, only after the freeze), sensitivity vs the 9 legacy +
     fresh effective pairs, MDE on every rho line, tiers SURVIVES/STRONG.
  5. if < 8 confirmation checkpoints landed: label PARTIAL (n, MDE) and ALSO run the S5.4 fallback
     hooks (disclosed-upstream sealed families + the iter_1 heldout XSTest split), NOT counted as
     blind confirmation.

Writes results/confirmation.json (+ chain stage S5) and results/confirm/manifest_schema.json.

CLI:
    .venv_gpu/bin/python src/join.py [--results-dir DIR] [--manifest-glob GLOB]
                                      [--pair-boot-path PATH] [--force] [--self-test]
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

WS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WS / "src"))
from core import band_indices, canonical_json, chain_append, cohens_d_pooled, sha256_text, \
    unit, utc_now, verify_chain, write_json  # noqa: E402
import statlib  # noqa: E402


DEFAULT_MANIFEST_GLOB = ("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/"
                          "gen_art/*/results/panel_manifest.json")

EXPECTED_ORDER_FULL = ["S1", "S2", "S3a", "S3b", "S4"]

# The iteration-4 harvest / "27-file" schema (24 named arrays/json + DONE + meta.json +
# MANIFEST.sha256.json), per src/ASSETS.md Q5 and the real I4 harvest dirs on disk.
ITER4_27FILE_NAMES = [
    "A_ams.npy", "A_c11.npy", "A_dec.npy", "A_dec_tok1.npy", "A_prompt.npy",
    "A_prompt_p1.npy", "A_prompt_p2.npy", "A_prompt_p3.npy",
    "WU_ctl.npy", "WU_hed.npy", "WU_ref.npy", "dec_ntok.npy", "gamma.npy",
    "hbar.npy", "hbar_all.npy", "mu_U.npy", "norms.npy",
    "r_control.npy", "r_fullV_final.npy", "r_hedge.npy", "r_refusal.npy",
    "token_ids.json", "vmin_lambda.npy", "vmin_onesproj.npy", "vmin_stacked.npy",
    "DONE", "meta.json", "MANIFEST.sha256.json",
]
# a directory counts as "iter4_27file" if it has at least this many of the 27 (a couple of
# documented per-arm omissions exist, e.g. int8bnb drops A_prompt_p3.npy, resave drops the manifest)
ITER4_27FILE_MIN_MATCH = 22


# --------------------------------------------------------------------------- #
# S5.0 gate: refuse unless the freeze verifies                                 #
# --------------------------------------------------------------------------- #


def gate_on_freeze(results_dir: Path) -> dict:
    sha_path = results_dir / "survivor.sha256"
    json_path = results_dir / "survivor.json"
    if not (sha_path.exists() and json_path.exists()):
        raise SystemExit("S5 refuses to run: results/survivor.sha256 / survivor.json do not exist")
    obj = json.loads(json_path.read_text())
    digest = sha256_text(canonical_json(obj))
    if digest != sha_path.read_text().strip():
        raise SystemExit("S5 refuses to run: survivor.json does not match survivor.sha256 (tampered)")
    chain = verify_chain(results_dir / "hashchain.jsonl", results_dir, expected_order=EXPECTED_ORDER_FULL)
    if not chain["ok"]:
        raise SystemExit(f"S5 refuses to run: hash chain does not verify: {chain}")
    logger.info(f"freeze gate OK: survivor.sha256 verifies, chain order {EXPECTED_ORDER_FULL} verifies")
    return obj


# --------------------------------------------------------------------------- #
# S5.1 manifest discovery + schema-adaptive loader                             #
# --------------------------------------------------------------------------- #


def discover_manifests(pattern: str, exclude_dir: Path) -> list[Path]:
    exclude_dir = exclude_dir.resolve()
    found = []
    for p in sorted(glob.glob(pattern)):
        pp = Path(p).resolve()
        try:
            pp.relative_to(exclude_dir)
            continue  # inside our own workspace -- never ours to read as "confirmation"
        except ValueError:
            pass
        found.append(pp)
    return found


def _dir_matches_iter4_27file(d: Path) -> tuple[bool, int, list[str]]:
    if not d.is_dir():
        return False, 0, ["not_a_directory"]
    present = [n for n in ITER4_27FILE_NAMES if (d / n).exists()]
    missing = [n for n in ITER4_27FILE_NAMES if n not in present]
    return len(present) >= ITER4_27FILE_MIN_MATCH, len(present), missing


def inspect_and_load_manifest(manifest_path: Path) -> tuple[dict, list[dict]]:
    """Returns (schema_record, checkpoint_entries). checkpoint_entries are normalised dicts
    {tag, repo, dir, layout, or, or_benign_set, hc, raw} -- 'dir'/'layout' absent if unresolved."""
    raw = json.loads(manifest_path.read_text())
    schema_record: dict[str, Any] = {
        "manifest_path": str(manifest_path),
        "top_level_type": type(raw).__name__,
        "top_level_keys": list(raw.keys()) if isinstance(raw, dict) else None,
        "top_level_len": len(raw) if isinstance(raw, (list, dict)) else None,
    }

    # find the list of per-checkpoint entries under several plausible shapes.
    entries_raw: list[dict] = []
    if isinstance(raw, list):
        entries_raw = [e for e in raw if isinstance(e, dict)]
        schema_record["shape"] = "top_level_list"
    elif isinstance(raw, dict):
        for key in ("checkpoints", "rows", "entries", "panel", "manifest", "items"):
            v = raw.get(key)
            if isinstance(v, list):
                entries_raw = [e for e in v if isinstance(e, dict)]
                schema_record["shape"] = f"dict['{key}'] -> list"
                break
        else:
            # maybe a dict keyed by tag -> entry dict
            if raw and all(isinstance(v, dict) for v in raw.values()):
                entries_raw = [{"tag": k, **v} for k, v in raw.items()]
                schema_record["shape"] = "dict keyed by tag"
            else:
                schema_record["shape"] = "UNRECOGNISED"
    else:
        schema_record["shape"] = "UNRECOGNISED"

    if entries_raw:
        schema_record["n_entries"] = len(entries_raw)
        schema_record["sample_entry_keys"] = sorted(entries_raw[0].keys())

    checkpoints = []
    base_dir = manifest_path.parent
    for e in entries_raw:
        tag = e.get("tag") or e.get("id") or e.get("name")
        repo = e.get("repo") or e.get("model") or e.get("hf_repo") or e.get("repo_id")
        dir_field = e.get("dir") or e.get("harvest_dir") or e.get("path") or e.get("root")
        ckpt_dir = None
        if dir_field:
            cand = Path(dir_field)
            ckpt_dir = cand if cand.is_absolute() else (base_dir / cand)
        elif tag:
            # try the same convention as the iteration-4 harvest: results/../harvest/<tag>/
            for cand in (base_dir / "harvest" / str(tag), base_dir.parent / "harvest" / str(tag)):
                if cand.is_dir():
                    ckpt_dir = cand
                    break
        layout, n_present, missing = (None, 0, [])
        if ckpt_dir is not None:
            ok, n_present, missing = _dir_matches_iter4_27file(ckpt_dir)
            layout = "iter4_27file" if ok else "UNRECOGNISED"

        truth = e.get("graded_truth") or e.get("outcome") or e.get("truth") or e
        or_val = truth.get("OR") if isinstance(truth, dict) else None
        or_set = truth.get("OR_benign_set") or truth.get("benign_set") or e.get("benign_set")
        hc_val = truth.get("HC") if isinstance(truth, dict) else None

        checkpoints.append({
            "tag": tag, "repo": repo, "dir": str(ckpt_dir) if ckpt_dir else None,
            "layout": layout, "n_files_present": n_present, "files_missing": missing[:5],
            "OR": or_val, "OR_benign_set": or_set, "HC": hc_val,
            "AMS_T1": e.get("AMS_T1") or e.get("AMS_T1_sigma"),
        })
    return schema_record, checkpoints


def load_confirmation_checkpoints(pattern: str, exclude_dir: Path, results_dir: Path) -> tuple[list[dict], list[dict]]:
    override = results_dir / "confirm/queue_override.json"
    if override.exists():
        q = json.loads(override.read_text())
        logger.warning(f"using MANUAL queue override {override} ({len(q.get('checkpoints', []))} checkpoints): "
                       "the substrate manifest schema could not be parsed automatically; the override records "
                       "where each field came from")
        return q["checkpoints"], q.get("schema_records", [{"source": str(override), "manual": True}])
    manifests = discover_manifests(pattern, exclude_dir)
    schema_records = []
    all_ckpts: list[dict] = []
    for m in manifests:
        sch, ckpts = inspect_and_load_manifest(m)
        schema_records.append(sch)
        all_ckpts.extend(ckpts)
    out_path = results_dir / "confirm" / "manifest_schema.json"
    write_json(out_path, {"utc": utc_now(), "pattern": pattern, "manifests_found": [str(m) for m in manifests],
                           "schema_records": schema_records})
    logger.info(f"manifest schema recorded -> {out_path} ({len(manifests)} manifest(s), "
                f"{len(all_ckpts)} checkpoint entries)")

    recognised = [c for c in all_ckpts if c.get("layout") == "iter4_27file"]
    if manifests and not recognised:
        raise SystemExit(
            f"S5 FAILS LOUDLY: found {len(manifests)} manifest(s) with {len(all_ckpts)} checkpoint "
            f"entries, but NONE resolve to a recognised iteration-4 27-file layout (or any other "
            f"known layout). Schema recorded at {out_path}. Refusing to guess the array schema."
        )
    return recognised, schema_records


# --------------------------------------------------------------------------- #
# S5.3(3): score Tier-A survivors directly from the 27-file arrays             #
# --------------------------------------------------------------------------- #


def _load_arrays(ckpt_dir: Path) -> dict:
    d = {}
    for name in ("A_prompt", "A_c11", "WU_ref", "gamma", "r_refusal", "r_control"):
        p = ckpt_dir / f"{name}.npy"
        if p.exists():
            d[name] = np.load(p, mmap_mode="r")
    meta_p = ckpt_dir / "meta.json"
    d["meta"] = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    return d


def score_bl1_easy_on_confirmation(arrays: dict) -> tuple[float | None, str]:
    """BL1_easy bar, reused definition: r_refusal - r_control at hidden-state index L (final
    layer), mean over items. Pairs with whatever candidate scoring ran on the SAME checkpoint."""
    r_ref, r_ctl = arrays.get("r_refusal"), arrays.get("r_control")
    if r_ref is None or r_ctl is None:
        return None, "r_refusal.npy / r_control.npy not available"
    try:
        val = float(np.asarray(r_ref[:, -1] - r_ctl[:, -1], dtype=np.float64).mean())
        return (val if np.isfinite(val) else None), "mean_i (r_refusal - r_control) @ index L"
    except (IndexError, ValueError) as exc:
        return None, f"BL1_easy shape error: {exc!r}"


def score_tierA_on_confirmation(cand: str, arrays: dict, stim_rows: dict | None) -> tuple[float | None, str]:
    """A DELIBERATELY SIMPLIFIED confirmation-panel re-scoring: all-item (non-cross-fitted) H/P
    contrast at a fixed mid-depth band (b=4 of 6), for the candidates whose definition is a simple
    Cohen's-d-style contrast (G4, plain_DiM-style floor) reusable without the full stimuli-row index
    machinery that lives only inside src/tierA.py. This is a documented scope simplification for the
    confirmation join (see results/proposed_amendments_tail.json); it is NOT the registered
    cross-fitted screen definition and is reported as such."""
    A_prompt = arrays.get("A_prompt")
    if A_prompt is None:
        return None, "A_prompt.npy not available"
    n_items, L1, d = A_prompt.shape
    n_layers = L1 - 1
    if n_layers < 6:
        return None, f"n_layers={n_layers} too small for 6 bands"
    if stim_rows is None or "H" not in stim_rows or "P" not in stim_rows:
        return None, "no stimuli row split supplied for this confirmation checkpoint"
    H_idx, P_idx = stim_rows["H"], stim_rows["P"]
    if not H_idx or not P_idx:
        return None, "empty H or P row set"
    b = 4
    Xb = band_mean_local(A_prompt, n_layers, b)
    F = unit(np.asarray(Xb[H_idx], dtype=np.float64).mean(0) - np.asarray(Xb[P_idx], dtype=np.float64).mean(0))
    proj = Xb @ F
    if cand in ("G4", "A1", "A3", "G1", "G2", "G3", "plain_DiM"):
        value = cohens_d_pooled(proj[H_idx], proj[P_idx])
        return (float(value) if np.isfinite(value) else None), "simplified all-item Cohen's d at band 4"
    return None, f"{cand}: no confirmation-panel Tier-A scorer implemented (Tier-B or unscored candidate)"


def band_mean_local(arr: np.ndarray, n_layers: int, b: int) -> np.ndarray:
    lo, hi = band_indices(n_layers, b)
    return np.asarray(arr[:, lo:hi + 1, :], dtype=np.float32).mean(axis=1)


# src/tierB.py is a SIBLING script (the Tier-B GPU driver) under active independent development.
# Importing it in-process runs its module-level code, which reconfigures the GLOBAL loguru
# `logger` singleton (logger.remove() + its own sinks, e.g. logs/tierB_run.log) -- if that import
# happened lazily, mid-run, it would silently hijack THIS script's logging into tierB's own log
# file. We probe for it EXACTLY ONCE, as the very first thing main() does, BEFORE this script
# installs its own sinks, so whatever tierB.py's import does to the logger is immediately
# overridden by our own (final) logging setup. score_tierB_external() only ever reads the cached
# result; it never imports tierB itself.
_TIERB_PROBED = False
_TIERB_MODULE = None


def probe_tierb_once() -> None:
    """Import src/tierB.py at most once, before this script's own logging sinks are installed."""
    global _TIERB_PROBED, _TIERB_MODULE
    if _TIERB_PROBED:
        return
    _TIERB_PROBED = True
    try:
        import tierB  # noqa: PLC0415
        _TIERB_MODULE = tierB
    except ImportError:
        _TIERB_MODULE = None


def score_tierB_external(cand: str, ckpt: dict) -> tuple[float | None, str]:
    if _TIERB_MODULE is None:
        return None, "TIER_B_EXTERNAL_UNAVAILABLE: src/tierB.py not importable (or not probed) in this environment"
    fn = getattr(_TIERB_MODULE, "score_external_checkpoint", None)
    if fn is None:
        return None, "TIER_B_EXTERNAL_UNAVAILABLE: src/tierB.py has no score_external_checkpoint hook"
    try:
        val = fn(cand, ckpt)
        return (float(val) if val is not None else None), "tierB.score_external_checkpoint"
    except Exception as exc:  # noqa: BLE001
        return None, f"tierB.score_external_checkpoint raised {exc!r}"


# --------------------------------------------------------------------------- #
# S5.2 assertions                                                              #
# --------------------------------------------------------------------------- #


def assert_intersection_empty(confirm_ckpts: list[dict], screen_repos: set[str]) -> dict:
    confirm_repos = {c["repo"] for c in confirm_ckpts if c.get("repo")}
    inter = confirm_repos & screen_repos
    return {"screen_repos_n": len(screen_repos), "confirm_repos_n": len(confirm_repos),
            "intersection": sorted(inter), "empty": len(inter) == 0}


def assert_or_nondegenerate(confirm_table: list[dict]) -> dict:
    ors = np.array([r["OR"] for r in confirm_table if r.get("OR") is not None], dtype=float)
    if ors.size < 2:
        return {"n": int(ors.size), "sd": None, "degenerate": True, "reason": "fewer than 2 OR values"}
    sd = float(np.std(ors, ddof=0))
    return {"n": int(ors.size), "sd": sd, "degenerate": sd <= 1e-12, "mean": float(ors.mean())}


# --------------------------------------------------------------------------- #
# S5.4 selection rule (ii)-(vii) -- pure, testable statistics                  #
# --------------------------------------------------------------------------- #


def selection_ii_primary(confirm_table: list[dict], cand: str, bl1_key: str = "BL1_easy",
                          ams_key: str = "AMS_T1") -> dict:
    c = np.array([r.get(cand, np.nan) for r in confirm_table], dtype=float)
    o = np.array([r.get("OR", np.nan) for r in confirm_table], dtype=float)
    bl1 = np.array([r.get(bl1_key, np.nan) for r in confirm_table], dtype=float)
    ams = np.array([r.get(ams_key, np.nan) for r in confirm_table], dtype=float)
    n = int((np.isfinite(c) & np.isfinite(o)).sum())
    rho = statlib.spearman(c, o)
    margin_bl1 = statlib.paired_margin_ci(c, bl1, o)
    margin_ams = statlib.paired_margin_ci(c, ams, o)
    partial = statlib.partial_spearman(c, o, [bl1, ams])
    return {"candidate": cand, "rho_OR": rho["rho"], "n": rho["n"], "mde": statlib.rho_mde(rho["n"]),
            "margin_vs_BL1_easy": margin_bl1, "margin_vs_AMS": margin_ams,
            "partial_rho_given_BL1_AMS": partial,
            "primary_passes": bool(margin_bl1.get("excludes_zero") and margin_ams.get("excludes_zero")
                                    and partial.get("rho") is not None and abs(partial.get("rho", 0)) > 0
                                    and partial.get("n", 0) >= 5)}


def selection_iii_coprimary(confirm_table: list[dict], cand: str, bl1_key: str = "BL1_easy") -> dict:
    c = np.array([r.get(cand, np.nan) for r in confirm_table], dtype=float)
    hc = np.array([r.get("HC", np.nan) for r in confirm_table], dtype=float)
    bl1 = np.array([r.get(bl1_key, np.nan) for r in confirm_table], dtype=float)
    margin_hc = statlib.paired_margin_ci(c, bl1, hc)
    return {"candidate": cand, "rho_HC": statlib.spearman(c, hc)["rho"], "margin_vs_BL1_easy_on_HC": margin_hc}


def mcnemar_15_and_12(pairs: list[dict], degenerate_ids: set[str], alarm_cand: dict[str, bool],
                       alarm_bl1: dict[str, bool]) -> dict:
    """pairs: list of {'pair_id','status'} with status 'no-op'|'effective'. alarm_* : pair_id -> bool
    (True == that method flagged a false alarm on that NO-OP pair)."""
    noop_ids = [p["pair_id"] for p in pairs if p.get("status") == "no-op"]
    def _bc(ids):
        b = c = 0
        for pid in ids:
            ac, ab = alarm_cand.get(pid), alarm_bl1.get(pid)
            if ac is None or ab is None:
                continue
            if ac and not ab:
                b += 1
            elif ab and not ac:
                c += 1
        return b, c
    b15, c15 = _bc(noop_ids)
    ids12 = [i for i in noop_ids if i not in degenerate_ids]
    b12, c12 = _bc(ids12)
    return {"n15": len(noop_ids), "n12": len(ids12),
            "mcnemar_15": {**statlib.mcnemar_exact(b15, c15), "daggered_ids": sorted(degenerate_ids)},
            "mcnemar_12": statlib.mcnemar_exact(b12, c12)}


def sensitivity_v(pairs: list[dict], delta_ci: dict[str, dict], sign_hc: int) -> dict:
    """pairs: effective pairs [{'pair_id', ...}]; delta_ci: pair_id -> {'lo','hi'}; sign_hc in {-1,+1}
    is the candidate's registered expected sign vs HC. DETECTED iff CI excludes 0 AND
    sign(delta) == sign_hc * s_HC (s_HC already folded into sign_hc by the caller)."""
    detected = []
    for p in pairs:
        pid = p["pair_id"]
        ci = delta_ci.get(pid)
        if not ci or ci.get("lo") is None or ci.get("hi") is None:
            continue
        lo, hi = ci["lo"], ci["hi"]
        if lo > 0 or hi < 0:
            mid = (lo + hi) / 2.0
            if np.sign(mid) == np.sign(sign_hc):
                detected.append(pid)
    return {"n_effective": len(pairs), "n_detected": len(detected), "detected_ids": detected,
            "target": "8/9 (>=7 of 9 including AMD-OLMo base->SFT)"}


def partial_label(n_landed: int) -> dict:
    return {"n": n_landed, "mde": statlib.rho_mde(n_landed) if n_landed > 3 else float("nan"),
            "PARTIAL": n_landed < 8}


# --------------------------------------------------------------------------- #
# unit tests on synthetic tables (per SPEC_tail S5)                            #
# --------------------------------------------------------------------------- #


def run_unit_tests() -> dict:
    results = {}

    # McNemar sanity: 15 no-op pairs, candidate alarms on 2, BL1 alarms on 6 (disjoint) -> b=2,c=6
    rng = np.random.default_rng(0)
    pairs = [{"pair_id": f"P{i}", "status": "no-op"} for i in range(15)]
    alarm_cand = {f"P{i}": (i < 2) for i in range(15)}
    alarm_bl1 = {f"P{i}": (i in (2, 3, 4, 5, 6, 7)) for i in range(15)}
    mc = mcnemar_15_and_12(pairs, degenerate_ids={"P0", "P1", "P14"}, alarm_cand=alarm_cand, alarm_bl1=alarm_bl1)
    ok_15 = mc["mcnemar_15"]["b"] == 2 and mc["mcnemar_15"]["c"] == 6
    ok_12 = mc["n12"] == 12
    results["mcnemar"] = {"pass": bool(ok_15 and ok_12), "detail": mc}

    # selection_ii: candidate == OR exactly (rho=1), BL1/AMS pure noise -> margin should exclude 0 and be positive
    n = 20
    o = rng.normal(size=n)
    table = [{"cand": float(o[i]), "OR": float(o[i]), "BL1_easy": float(rng.normal()),
              "AMS_T1": float(rng.normal()), "HC": float(-o[i] + 0.1 * rng.normal())} for i in range(n)]
    ii = selection_ii_primary(table, "cand")
    ok_ii = ii["rho_OR"] > 0.9 and ii["margin_vs_BL1_easy"]["excludes_zero"]
    results["selection_ii"] = {"pass": bool(ok_ii), "detail": ii}

    # sensitivity: 9 effective pairs, CI excludes 0 and correct sign on 7 of them
    eff_pairs = [{"pair_id": f"E{i}"} for i in range(9)]
    delta_ci = {f"E{i}": {"lo": 0.1, "hi": 0.5} for i in range(7)}
    delta_ci.update({f"E{i}": {"lo": -0.2, "hi": 0.2} for i in range(7, 9)})
    sens = sensitivity_v(eff_pairs, delta_ci, sign_hc=1)
    ok_sens = sens["n_detected"] == 7
    results["sensitivity"] = {"pass": bool(ok_sens), "detail": sens}

    # partial_label
    pl8 = partial_label(8)
    pl7 = partial_label(7)
    ok_partial = (not pl8["PARTIAL"]) and pl7["PARTIAL"]
    results["partial_label"] = {"pass": bool(ok_partial), "detail": {"n8": pl8, "n7": pl7}}

    results["ALL_PASS"] = bool(all(v.get("pass", False) for v in results.values() if isinstance(v, dict) and "pass" in v))
    return results


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #


@logger.catch(reraise=True)
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=WS / "results")
    ap.add_argument("--logs-dir", type=Path, default=WS / "logs")
    ap.add_argument("--manifest-glob", type=str, default=DEFAULT_MANIFEST_GLOB)
    ap.add_argument("--exclude-dir", type=Path, default=WS,
                     help="own-workspace dir excluded from manifest discovery (test hook; production default is WS)")
    ap.add_argument("--stim-rows-path", type=Path, default=None,
                     help="JSON {tag: {'H':[idx..],'P':[idx..]}} for the simplified confirmation scorer (test hook)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    # Probe src/tierB.py (if present) BEFORE claiming our own logging sinks -- see the comment on
    # probe_tierb_once(): whatever its import does to the global loguru logger is overridden next.
    import confirm_score  # noqa: F401,PLC0415  (imports tierA/bars, which configure loguru: import BEFORE our sinks)
    probe_tierb_once()
    logs_dir = args.logs_dir.resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(logs_dir / "join.log", rotation="10 MB", level="DEBUG")

    if args.self_test:
        ut = run_unit_tests()
        logger.info(f"unit tests: ALL_PASS={ut['ALL_PASS']}")
        for k, v in ut.items():
            if isinstance(v, dict) and "pass" in v:
                logger.info(f"  {k}: {'PASS' if v['pass'] else 'FAIL'}")
        if not ut["ALL_PASS"]:
            raise SystemExit("join.py --self-test FAILED")
        return

    results_dir = args.results_dir.resolve()
    out_path = results_dir / "confirmation.json"
    if out_path.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing {out_path} (pass --force)")

    survivor_payload = gate_on_freeze(results_dir)
    survivors = survivor_payload.get("survivors")

    if survivors == "NONE" or not survivors:
        payload = {"utc": utc_now(), "status": "NO_SURVIVORS", "verdict": "P1_WINS: THE BOUND",
                   "note": "S4 froze survivors == NONE; S5 has nothing to confirm."}
        digest = write_json(out_path, payload)
        chain_append(results_dir / "hashchain.jsonl", "S5", out_path, digest)
        logger.warning("no survivors to confirm -> P1_WINS: THE BOUND")
        return

    confirm_ckpts, schema_records = load_confirmation_checkpoints(args.manifest_glob, args.exclude_dir, results_dir)

    screen_repos = set()
    st_path = results_dir / "screen_table.json"
    if st_path.exists():
        st = json.loads(st_path.read_text())
        tierA_dir = results_dir / "screen" / "tierA"
        if tierA_dir.exists():
            for f in tierA_dir.glob("*.json"):
                try:
                    r = json.loads(f.read_text()).get("repo")
                    if r:
                        screen_repos.add(r)
                except json.JSONDecodeError:
                    pass

    intersection = assert_intersection_empty(confirm_ckpts, screen_repos)
    logger.info(f"screen/confirmation repo intersection: {intersection}")
    if not intersection["empty"]:
        raise SystemExit(f"S5 refuses: screen/confirmation panels overlap: {intersection}")

    stim_rows = json.loads(args.stim_rows_path.read_text()) if args.stim_rows_path else None

    import confirm_score  # noqa: PLC0415  (amendment A5; already imported at the top of main)
    confirm_table = []
    all_cands = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8", "G1", "G2", "G3", "G4", "A1", "A2", "A3"]
    for ck in confirm_ckpts:
        sc = confirm_score.score(ck["tag"], Path(ck["dir"]) if ck.get("dir") else None, results_dir)
        row = {"tag": ck["tag"], "repo": ck["repo"], "OR": ck.get("OR"), "OR_benign_set": ck.get("OR_benign_set"),
               "HC": ck.get("HC"), "BL1_easy": sc.get("BL1_easy"), "AMS_T1": sc.get("AMS_T1"),
               "AMS_T1_manifest_reported": ck.get("AMS_T1"), "scoring_notes": sc.get("notes"),
               "censored": sc.get("censored"), "bars_all": {k: v for k, v in (sc.get("bars") or {}).items()
                                                             if isinstance(v, (int, float)) or v is None}}
        for cand in all_cands + ["A1_prior", "A1_slope", "W7c", "W7c_tok1", "G4_ratio", "plain_DiM"]:
            row[cand] = sc["values"].get(cand)
        confirm_table.append(row)

    or_check = assert_or_nondegenerate(confirm_table)
    logger.info(f"OR non-degeneracy: {or_check}")

    partial = partial_label(len(confirm_table))
    logger.info(f"n_landed={partial['n']} PARTIAL={partial['PARTIAL']} MDE={partial['mde']}")

    selection = {}
    for s in survivors:
        cand = s["candidate"]
        selection[cand] = {
            "ii_primary": selection_ii_primary(confirm_table, cand) if not or_check["degenerate"]
                          else {"status": "CONFIRMATION = UNINFORMATIVE (OR degenerate)"},
            "iii_coprimary": selection_iii_coprimary(confirm_table, cand) if not or_check["degenerate"] else None,
        }

    payload = {
        "utc": utc_now(), "status": "PARTIAL" if partial["PARTIAL"] else "FULL",
        "n_confirmation_checkpoints": len(confirm_table),
        "partial": partial,
        "manifest_glob": args.manifest_glob,
        "schema_records": schema_records,
        "intersection_check": intersection,
        "or_nondegeneracy_check": or_check,
        "confirmation_table": confirm_table,
        "selection_rule": selection,
        "s5_4_fallback": {
            "ran": False,
            "note": ("hooks only: (a) disclosed-upstream sealed families (Qwen2.5-1.5B, SmolLM2-1.7B) and "
                     "(b) the iter_1 heldout 54-scenario XSTest split were NOT opened in this build/test "
                     "session (never run against production paths here); wire in via "
                     "--sealed-path/--heldout-path when this is run for real post-freeze."),
        },
        "note_scope": ("Every confirmation value is computed by src/confirm_score.py with the SCREEN's exact code "
                        "(tierA.crossfit, bars.compute_bars, tierB external mode, frozen A1 loading) - amendment A5; "
                        "the simplified scorer proposed during the build (proposed_amendments_tail A7) was REJECTED."),
    }
    digest = write_json(out_path, payload)
    chain_append(results_dir / "hashchain.jsonl", "S5", out_path, digest)
    logger.info(f"wrote {out_path} sha256={digest[:16]}")


if __name__ == "__main__":
    main()
