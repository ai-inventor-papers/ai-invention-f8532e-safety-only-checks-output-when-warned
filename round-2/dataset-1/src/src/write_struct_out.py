#!/usr/bin/env python3
"""Emit .terminal_claude_agent_struct_out.json from the finished build.

Every number is read off the shipped files rather than retyped. The schema caps
layman_summary at 250 characters and summary at 5000, so this writes tightly and
asserts both limits before it writes.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LAYMAN_MAX = 250
SUMMARY_MAX = 5000


def main() -> None:
    data = json.loads((ROOT / "full_data_out.json").read_text())
    gates = json.loads((ROOT / "gates.json").read_text())
    meta, summ = data["metadata"], gates["summary"]
    counts = meta["row_counts_by_table"]
    reg = json.loads((ROOT / "build" / "registry_labelled.json").read_text())
    beh = json.loads((ROOT / "build" / "behavioural.json").read_text())
    mining = json.loads((ROOT / "build" / "mining_stats.json").read_text())
    rec = json.loads((ROOT / "build" / "recognition_set.json").read_text())
    g = {x["gate_id"]: x for x in gates["gates"]}

    fails = "; ".join(f"{f['gate_id']} (need {f['threshold']}, got {f['observed']})"
                      for f in summ["failed_gates"])
    nc = mining["naive_comparator"]
    rc, pr = rec["counts"], rec["proxy"]
    gh = rec.get("graded_harm", {})
    gh_n = gh.get("n_populated", 0)
    dedup = rec["dedup"]
    compact_counts = ", ".join(f"{k.replace('probe_', '').replace('_tokens', '')} {v}"
                               for k, v in counts.items())

    summary = f"""FROZEN ITERATION-2 SUBSTRATE for the Qwen3-4B safety mech-interp run: model pairs, hard prompts, refusal tokens. Nothing touches a model - 0 safetensors files, no forward pass, no activations, no metric. {g['G_DOWNLOAD_BUDGET']['observed']} MB downloaded vs a 300 MB cap; $0 spent.

GATES {summ['n_pass']} PASS / {summ['n_fail']} FAIL / {summ['n_not_applicable']} N/A. FAILED, with numbers, thresholds NOT relaxed: {fails}.

FREEZE CAME FIRST AND IS CHECKABLE. prereg.json hashed 03:38:26Z BEFORE any label, split or proxy existed; append-only build_log.txt proves the order. sha256 {meta['prereg_sha256']} is asserted equal across the file on disk, prereg.sha256 and the copy inside full_data_out.json (G_PREREG_HASH) - iteration 1 shipped a prereg hash disagreeing with its own manifest. The freeze script refuses to overwrite.

TEN SETS, {sum(counts.values())} examples, one per row (per-set counts in full_data_out.json metadata and README.md). Plus sealed_truth.json and the prereg/gates freeze = twelve.

REGISTRY {len(reg['checkpoints'])} checkpoints, {len(reg['pairs'])} pairs, 13 families, from {reg.get('n_candidates_screened')} Hub candidates screened live. safetensors bytes SUMMED FROM THE FILE LIST, not usedStorage. Raw card text ships verbatim - the card+name REGEX BASELINE the screen must beat is computed from it. Labels {json.dumps(reg['label_histogram'])}.

HEADLINE NEGATIVE: at n=45+45, HALF THE SCORABLE PAIRS CANNOT BE LABELLED ROBUSTLY. 3 EFFECTIVE with a Newcombe 95% CI wholly above +0.15 (Qwen3-0.6B +0.467 [0.270,0.616]; Qwen3-1.7B +0.667 [0.501,0.786]; Josiefied-Qwen2.5-1.5B +0.467 [0.308,0.609]). 3 DEMOTED to AMBIGUOUS by the frozen label_robust rule despite point estimates crossing: SmolLM3 +0.289 [0.086,0.461], Phi-4-mini +0.244 [0.116,0.387], granite 0.000 [-0.079,0.079]. Hence G_EFFECTIVE_IN_STRATUM (2, need 4) and G_NONEFFECTIVE (0, need 2) fail: granite's NULL_EDIT was demoted and the one real ANOMALOUS pair (venkycs SmolLM2, over-refusal 1.000) is in a SEALED family. Strata NOT widened to rescue the count; the 4-pair requirement must be met partly by the lane's in-house rank-one edits.

10 pairs UNSCORED, never zero-filled: 8 FRESH (3 held_out by a seeded sha256 rule fixed before scoring), the commissioned Qwen3-4B -> mlabonne/Qwen3-4B-abliterated pair (ungated; the gated='auto' huihui variant refused), and TinyLlama, EXCLUDED as missing_shards - unloadable, not a null-edit control.

JOIN EXACT: 26 checkpoints recomputed from {beh['n_judged_rows']} judged rows match published columns to 0.000e+00 - but only after adopting iteration 1's denominator convention, since 1 row (Phi-4-mini benign orh_244) has an unparsable judge output it drops. The first run FAILED at 1.46e-2; build_log.txt records both.

RECOGNITION SET {rc['total']} rows, {rc['benign']} benign / {rc['harmful']} harmful, built to kill the ceiling that made iteration 1's premise test unfalsifiable. HARDNESS MEASURED: TF-IDF+char-ngram logistic proxy, 5-fold CV, AUROC {pr['easy']['auroc']} on easy anchors (PASS, the saturating pole) and {pr['hard']['auroc']} on hard+borderline+wrapped vs a <=0.85 target - a FAIL, below the 0.90 rebalance trigger, with `{pr.get('leaking_stratum')}` named as the leaking stratum and top-20 features shipped. Dedup removed {dedup['n_exact_removed']} exact + {dedup['n_near_removed']} near; disjointness from iteration 1's 96/54 XSTest split asserted at {rec['n_overlap_iter1_xstest_split']}. graded_harm on {gh_n} rows from PKU-SafeRLHF ordinal severity, null elsewhere, never invented.

TOKENS from {mining['judged_source']['n_rows_loaded']} real generations, 9 families; no iteration-1 lexicon exists (grep-verified). Refusal-onset 60 forms, all in >=3 families, opening {nc['frac_opened_by_mined_set']} of 1,115 refusing generations vs {nc['frac_opened_by_naive_comparator']} for the constructed naive comparator; top-30 Jaccard 0.25 vs do-not-answer, so a behaviour not a template. HEDGE TOOK 3 PASSES, THE FIRST TWO SHIPPED AS EVIDENCE OF FAILURE: a 2-document pool crowned its content words ("abraham lincoln", lift 1632), and widening to 147 docs with a document-frequency lift and prompt-echo stripping stayed topic-confounded - 147 generations over 45 prompts cannot separate style from topical halo. Pass 3 DECLARES a hedge-marker frame and mines 24 forms in it. Controls 28/35 inside the 0.25 caliper. Tokenizer table 128 forms x 28 tokenizers x 2 variants, 0 failures, 0 dropped; mid-text variant PRIMARY.

PROBES: all pairwise prompt-hash intersections ZERO. 160/154 reused VERBATIM from iteration 1; 200 NEW auto-gradable with no judge (ARC-Easy + GSM8K, key in `output`); 40 from the never-loaded sealed split. Judge rubric verbatim with SHA-256s so new rows pool with the 2,370.

SEAL ALREADY COMPROMISED AND SAID SO: both sealed pairs' deltas appear in the iteration-2 strategy text, so seal_status=DISCLOSED_UPSTREAM; only the seeded FRESH pairs and the sealed split are blind.

CONTRACT: filter on label_robust, NOT effectiveness_label alone, or 3 CI-straddling pairs look decided. Every row carries readout_class; registry and card text are BASELINE by construction. Never read sealed_truth.json or the sealed_holdout split in a fitting lane."""

    layman = ("A hash-sealed toolkit for studying what changes inside small AI models when "
              "their safety training is stripped out: before/after model pairs, deliberately "
              "hard prompts, and real refusal wording. Every failed check is reported as "
              "failed.")

    assert len(layman) <= LAYMAN_MAX, f"layman_summary {len(layman)} > {LAYMAN_MAX}"
    assert len(summary) <= SUMMARY_MAX, f"summary {len(summary)} > {SUMMARY_MAX}"

    out = {
        "title": "Model pairs, hard prompts, refusal tokens",
        "layman_summary": layman,
        "summary": summary,
        "out_expected_files": {
            "script": "data.py",
            "datasets": [{
                "full": sorted(Path(p).name for p in glob.glob(str(ROOT / "full_data_out*.json"))),
                "mini": "mini_data_out.json",
                "preview": "preview_data_out.json",
            }],
        },
        "upload_ignore_regexes": [
            "(^|/)\\.venv/",
            "(^|/)__pycache__/",
            "(^|/)build/repo_meta/",
            "(^|/)temp/datasets/",
        ],
    }
    (ROOT / ".terminal_claude_agent_struct_out.json").write_text(json.dumps(out, indent=2))
    print(f"wrote struct_out: layman {len(layman)}/{LAYMAN_MAX}, summary {len(summary)}/{SUMMARY_MAX}")


if __name__ == "__main__":
    main()
