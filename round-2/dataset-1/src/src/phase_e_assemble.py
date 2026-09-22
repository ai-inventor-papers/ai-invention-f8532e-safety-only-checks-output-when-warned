#!/usr/bin/env python3
"""PHASE E: assemble data_out.json (exp_sel_data_out schema), compute every gate, and
print the freeze.

Ten shipped sets live inside data_out.json; sealed_truth.json, prereg.json,
prereg_addendum.json and gates.json ship beside it, for twelve in all.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
sys.path.insert(0, str(ROOT / "src"))
from lib_gates import Gates  # noqa: E402
from lib_recog import phash, sizing_statement  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add(ROOT / "logs" / "phase_e.log", rotation="30 MB", level="DEBUG")

BUILD_LOG = ROOT / "build_log.txt"
PREFIX = "qwen3_safety_iter2_substrate_v1"


def blog(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with BUILD_LOG.open("a") as fh:
        fh.write(f"{ts}  {msg}\n")
    logger.info(msg)


def jload(name: str) -> dict | None:
    p = BUILD / name
    if not p.exists():
        logger.warning(f"missing build artefact {name}")
        return None
    return json.loads(p.read_text())


def md(prefix: str, d: dict) -> dict:
    """Flatten a dict into metadata_* keys, JSON-encoding nested values."""
    out = {}
    for k, v in d.items():
        key = f"metadata_{prefix}{k}" if prefix else f"metadata_{k}"
        out[key] = v
    return out


@logger.catch(reraise=True)
def main() -> None:
    blog("PHASE E start: assembly + gates")
    prereg = json.loads((ROOT / "prereg.json").read_text())
    prereg_sha = (ROOT / "prereg.sha256").read_text().split()[0]
    live_sha = hashlib.sha256((ROOT / "prereg.json").read_bytes()).hexdigest()
    G = Gates(prereg)

    reg = jload("registry_labelled.json")
    rec = jload("recognition_set.json")
    tok_r = jload("tokens_refusal_onset.json")
    tok_h = jload("tokens_hedge_redirect.json")
    tok_c = jload("tokens_matched_control.json")
    tok_t = jload("tokenizer_table.json")
    probes = jload("probe_pools.json")
    sources = jload("sources_manifest.json")
    beh = jload("behavioural.json")

    datasets: list[dict] = []

    # ---------------- 1. paired lineage registry ----------------
    if reg:
        ex: list[dict] = []
        for c in reg["checkpoints"]:
            row = {"input": c["repo_id"], "output": c.get("role", ""),
                   "metadata_row_kind": "checkpoint", "metadata_readout_class": "metadata"}
            for k, v in c.items():
                if k in ("repo_id", "role"):
                    continue
                row[f"metadata_{k}"] = v
            ex.append(row)
        for p in reg["pairs"]:
            row = {"input": f"{p['parent_repo']} -> {p['child_repo']}",
                   "output": str(p.get("effectiveness_label") or "SEALED"),
                   "metadata_row_kind": "pair", "metadata_readout_class": "metadata"}
            for k, v in p.items():
                row[f"metadata_{k}"] = v
            ex.append(row)
        datasets.append({"dataset": f"{PREFIX}::paired_lineage_registry", "examples": ex})

        pairs = reg["pairs"]
        fams = {c.get("family") for c in reg["checkpoints"] if c.get("family")}
        G.check_ge("G_PAIRS_TOTAL", len(pairs), 12)
        G.check_ge("G_FAMILIES", len(fams), 8, note=f"families: {sorted(fams)}")
        ebs = reg.get("effective_by_stratum") or {}
        G.check_ge("G_EFFECTIVE_IN_STRATUM", max(ebs.values(), default=0), 4,
                   note=f"EFFECTIVE by stratum: {ebs}")
        hist = reg.get("label_histogram", {})
        G.check_ge("G_NONEFFECTIVE", hist.get("NULL_EDIT", 0) + hist.get("ANOMALOUS", 0), 2,
                   note=f"label histogram: {hist}")
        G.check_ge("G_FRESH_HELDOUT", len(reg.get("held_out_pairs", [])), 3,
                   note=(f"fresh-eligible {reg.get('n_fresh_eligible')}, shortfall extras "
                         f"{reg.get('held_out_shortfall_extras')}"))
        comm = [p for p in pairs if p.get("child_repo") == "mlabonne/Qwen3-4B-abliterated"]
        G.record("G_COMMISSIONED_PAIR",
                 comm[0]["pair_id"] if comm else None,
                 "PASS" if comm else "FAIL",
                 note="Qwen/Qwen3-4B -> mlabonne/Qwen3-4B-abliterated")
        tl = [p for p in pairs if "tinyllama" in str(p.get("family", "")).lower()
              or "TinyLlama" in p.get("child_repo", "")]
        tl_ok = bool(tl) and all(p.get("size_anomaly_cause") or p.get("exclusion_reason")
                                 for p in tl)
        G.record("G_TINYLLAMA",
                 [{"pair_id": p["pair_id"], "cause": p.get("size_anomaly_cause"),
                   "exclusion_reason": p.get("exclusion_reason")} for p in tl],
                 "PASS" if tl_ok else "FAIL")

    # ---------------- 2. hard recognition set ----------------
    if rec:
        rows = rec["rows"]
        datasets.append({"dataset": f"{PREFIX}::hard_recognition_set", "examples": rows})
        n_b = sum(1 for r in rows if r.get("metadata_harm_label") == "benign")
        n_h = len(rows) - n_b
        G.check_ge("G_RECOG_TOTAL", len(rows), 1300)
        G.check_ge("G_RECOG_BENIGN", n_b, 600)
        pe = (rec.get("proxy") or {}).get("easy", {}).get("auroc")
        ph_ = (rec.get("proxy") or {}).get("hard", {}).get("auroc")
        G.check_ge("G_PROXY_EASY", pe, 0.95)
        if ph_ is None:
            G.record("G_PROXY_HARD", None, "NOT_APPLICABLE")
        else:
            G.record("G_PROXY_HARD", ph_, "PASS" if ph_ <= 0.85 else "FAIL",
                     note=("hard-subset text proxy; FAIL above 0.90 is the hard branch, "
                           "0.85-0.90 is a missed target reported as FAIL"))
        dd = rec.get("dedup", {})
        G.check_eq("G_DEDUP", dd.get("n_remaining_duplicates", 0), 0,
                   note=f"removed exact={dd.get('n_exact_removed')} near={dd.get('n_near_removed')}")
        G.check_eq("G_DISJOINT_ITER1", rec.get("n_overlap_iter1_xstest_split"), 0)
        rec["sizing"] = sizing_statement(n_b, n_h)

    # ---------------- 3/4/5. token sets ----------------
    # The mining lane emits `forms` / `matches` / `table`; adapt rather than rename its
    # files, so the shipped rows stay traceable to the file that produced them.
    mining = jload("mining_stats.json") or {}
    mgates = mining.get("gates", {})

    if tok_r:
        ex = []
        for t in tok_r.get("forms", []):
            r = {"input": t["form"], "output": "refusal_onset",
                 "metadata_pool_id": "refusal_onset", "metadata_readout_class": "text"}
            r.update({f"metadata_{k}": v for k, v in t.items()})
            ex.append(r)
        datasets.append({"dataset": f"{PREFIX}::refusal_onset_tokens", "examples": ex})
        n_ok = sum(1 for t in tok_r.get("forms", []) if (t.get("n_families") or 0) >= 3)
        G.check_ge("G_REFUSAL_FORMS", n_ok, 20,
                   note=(f"naive constructed comparator opens "
                         f"{mining.get('naive_comparator', {}).get('frac_opened_by_naive_comparator')} "
                         f"of refusing generations; the mined set opens "
                         f"{mining.get('naive_comparator', {}).get('frac_opened_by_mined_set')}"))
        xj = mgates.get("G_XSRC_JACCARD", {})
        if xj.get("observed_jaccard") is None:
            G.record("G_XSRC_JACCARD", None, "NOT_APPLICABLE")
        else:
            G.check_ge("G_XSRC_JACCARD", xj["observed_jaccard"], 0.20,
                       note=f"top-30 overlap vs LibrAI/do-not-answer: {xj.get('intersection')}")

    # the hedge set ships in its FINAL frame-restricted form; the unrestricted pass is
    # carried inside it as evidence of what unsupervised mining does to this corpus.
    tok_h_final = jload("tokens_hedge_redirect_final.json") or tok_h
    if tok_h_final:
        ex = []
        for t in tok_h_final.get("forms", []):
            r = {"input": t["form"], "output": "hedge_redirect",
                 "metadata_pool_id": "hedge_redirect", "metadata_readout_class": "text"}
            r.update({f"metadata_{k}": v for k, v in t.items()})
            ex.append(r)
        datasets.append({"dataset": f"{PREFIX}::hedge_redirect_tokens", "examples": ex})
        n_ok = sum(1 for t in tok_h_final.get("forms", [])
                   if (t.get("lift_document_frequency") or t.get("lift") or 0) >= 2.0)
        ev = tok_h_final.get("unrestricted_mining_evidence", {})
        G.check_ge("G_HEDGE_FORMS", n_ok, 20,
                   note=("mined inside a DECLARED hedge frame. Unrestricted mining on this "
                         f"corpus is TOPIC-CONFOUNDED - its top forms were {ev.get('top10_forms')} "
                         "- because the safe-decline pool is 147 generations over 45 harm "
                         "prompts; that ranking ships as evidence, not as a lexicon."))

    if tok_c:
        ex = []
        for t in tok_c.get("matches", []):
            r = {"input": t.get("control_token", ""), "output": "matched_control",
                 "metadata_pool_id": "matched_control", "metadata_readout_class": "text"}
            r.update({f"metadata_{k}": v for k, v in t.items()})
            ex.append(r)
        datasets.append({"dataset": f"{PREFIX}::matched_control_tokens", "examples": ex})
        bal = tok_c.get("achieved_balance", {})
        G.check_le("G_CONTROL_BALANCE", bal.get("median_abs_delta_log_freq"), 0.25,
                   note=(f"max |delta log-freq| = {bal.get('max_abs_delta_log_freq')}, "
                         f"matched {bal.get('n_matched')} of {bal.get('n_selected')}, "
                         f"{bal.get('n_unmatched')} unmatched inside the 0.25 caliper"))

    # ---------------- 6. tokenizer compatibility table ----------------
    if tok_t:
        ex = []
        for form, cell in (tok_t.get("table") or {}).items():
            for tokzr, v in (cell.get("per_tokenizer") or {}).items():
                for variant in ("mid_text", "turn_initial"):
                    d = v.get(variant) or {}
                    ex.append({
                        "input": f"{form}||{tokzr}||{variant}",
                        "output": json.dumps(d.get("ids", [])),
                        "metadata_readout_class": "metadata",
                        "metadata_form": form,
                        "metadata_tokenizer": tokzr,
                        "metadata_variant": variant,
                        "metadata_variant_role": ("primary" if variant == "mid_text"
                                                  else "secondary"),
                        "metadata_tokenizer_verified": v.get("tokenizer_verified"),
                        "metadata_ids": d.get("ids"),
                        "metadata_n_pieces": d.get("n_pieces"),
                        "metadata_is_single_token": d.get("is_single_token"),
                        "metadata_exact_surface_roundtrip": d.get("exact_surface_roundtrip"),
                    })
        datasets.append({"dataset": f"{PREFIX}::tokenizer_compatibility_table", "examples": ex})
        st = tok_t.get("gate_G_SINGLE_TOKEN", {})
        G.record("G_SINGLE_TOKEN",
                 {"n_primary_forms": st.get("n_primary_forms"),
                  "n_dropped": st.get("n_dropped"),
                  "dropped_forms": st.get("dropped_forms"),
                  "n_tokenizers_verified": tok_t.get("n_tokenizers_verified"),
                  "n_tokenizers_failed": tok_t.get("n_tokenizers_failed")},
                 "PASS" if st.get("pass") else "FAIL",
                 note=f"tokenizer load failures: {tok_t.get('tokenizer_load_failures')}")

    # ---------------- 7-10. probe pools ----------------
    if probes:
        for pool_id, rows in probes["pools"].items():
            datasets.append({"dataset": f"{PREFIX}::{pool_id}", "examples": rows})
        G.check_eq("G_PROBE_DISJOINT", probes["max_off_diagonal_intersection"], 0,
                   note=json.dumps(probes["intersection_matrix"]))
        sz = probes["pool_sizes"]
        need = {"probe_harmful": 120, "probe_hard_benign": 120,
                "probe_already_correct_benign": 150, "probe_baseline_disjoint": 24}
        ok = all(sz.get(k, 0) >= v for k, v in need.items())
        G.record("G_PROBE_NS", sz, "PASS" if ok else "FAIL")

    # ---------------- behavioural join consistency ----------------
    if beh:
        cons = beh["consistency"]
        G.check_le("G_JOIN_CONSISTENCY", cons["max_abs_rate_difference"], 1e-9,
                   note=(f"{cons['n_mismatches']} mismatches; {beh['n_unparsed_primary']} of "
                         f"{beh['n_judged_rows']} judged rows had an unparsable primary judge "
                         f"output and are dropped from the denominator, which is the convention "
                         f"iteration-1's published columns already used"))

    # ---------------- rubric / budget gates ----------------
    rub = ROOT / "assets" / "rubric_iter1.md"
    jd = ROOT / "assets" / "lc_judge_iter1.py"
    G.record("G_RUBRIC_HASH",
             {"rubric_md_sha256": hashlib.sha256(rub.read_bytes()).hexdigest(),
              "lc_judge_py_sha256": hashlib.sha256(jd.read_bytes()).hexdigest()},
             "PASS" if rub.exists() and jd.exists() else "FAIL")

    # Measured on disk rather than trusted from a manifest field: the corpora this
    # artifact actually downloaded, plus the Hub metadata/card bytes the registry lane
    # fetched. Tokenizers were read from the run-shared HF cache, not downloaded.
    def dir_bytes(d: Path) -> int:
        return sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.exists() else 0
    corpora = dir_bytes(ROOT / "temp" / "datasets")
    repo_meta = dir_bytes(BUILD / "repo_meta")
    reg_bytes = int((reg or {}).get("bytes_downloaded", 0) or 0)
    total_mb = (corpora + max(repo_meta, reg_bytes)) / 1e6
    G.check_le("G_DOWNLOAD_BUDGET", round(total_mb, 2), 300.0,
               note=(f"megabytes measured on disk: public corpora {corpora/1e6:.2f} MB + "
                     f"Hub metadata/cards {max(repo_meta, reg_bytes)/1e6:.2f} MB; tokenizers "
                     f"were read from the run-shared HF cache, not downloaded"))
    weights = list((ROOT).rglob("*.safetensors"))
    G.check_eq("G_NO_WEIGHTS", len(weights), 0)

    # ---------------- metadata + freeze ----------------
    meta = {
        "artifact": ("iteration-2 dataset substrate: paired-lineage registry, hard recognition "
                     "set, execution-side token sets, causal-lane probe pools"),
        "run_id": "run_YqmEFECOIR3D",
        "iteration": 2,
        "built_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prereg_sha256": prereg_sha,
        "prereg_sha256_recomputed_from_disk": live_sha,
        "sealed_truth_sha256": (ROOT / "sealed_truth.sha256").read_text().split()[0]
        if (ROOT / "sealed_truth.sha256").exists() else None,
        "row_counts_by_table": {d["dataset"].split("::")[-1]: len(d["examples"]) for d in datasets},
        "twelve_shipped_sets": [
            "paired_lineage_registry", "hard_recognition_set", "refusal_onset_tokens",
            "hedge_redirect_tokens", "matched_control_tokens", "tokenizer_compatibility_table",
            "probe_harmful", "probe_hard_benign", "probe_already_correct_benign",
            "probe_baseline_disjoint", "sealed_truth (side file)",
            "prereg + gates freeze manifest (side files)",
        ],
        "readout_class_invariant": prereg["readout_class_invariant"],
        "out_of_scope": prereg["out_of_scope"],
        "judge_assets": (beh or {}).get("judge_assets"),
        "sizing_statement": (rec or {}).get("sizing"),
        "siblings": ["prereg.json", "prereg.sha256", "prereg_addendum.json", "sealed_truth.json",
                     "sealed_truth.sha256", "gates.json", "build_log.txt",
                     "assets/rubric_iter1.md", "assets/lc_judge_iter1.py",
                     "build/sources_manifest.json"],
    }
    G.check_eq("G_PREREG_HASH", live_sha, prereg_sha,
               note="hash of prereg.json on disk vs prereg.sha256 vs the string embedded here")
    gates_payload = G.write(ROOT / "gates.json")
    meta["gates_summary"] = gates_payload["summary"]

    out = {"metadata": meta, "datasets": datasets}
    # ONE canonical file. Iteration 1 shipped data_out.json and full_data_out.json as
    # near-duplicates; here full_data_out.json is the only copy and mini_/preview_ are
    # generated from it, so there is nothing for the two to disagree about.
    (ROOT / "full_data_out.json").write_text(json.dumps(out, indent=1))

    # re-read and assert the embedded hash matches the file and prereg.sha256
    back = json.loads((ROOT / "full_data_out.json").read_text())
    assert back["metadata"]["prereg_sha256"] == prereg_sha == \
        hashlib.sha256((ROOT / "prereg.json").read_bytes()).hexdigest()
    blog(f"PHASE E done: {len(datasets)} sets, "
         f"{sum(len(d['examples']) for d in datasets)} rows; gates {gates_payload['summary']}")
    print(G.table())
    print(json.dumps(gates_payload["summary"], indent=1))


if __name__ == "__main__":
    main()
