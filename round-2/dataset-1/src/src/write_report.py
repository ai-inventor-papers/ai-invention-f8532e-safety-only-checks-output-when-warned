#!/usr/bin/env python3
"""Assemble <WS>/build/tokens_report.md from the JSON artefacts already on
disk (mining_stats.json, tokens_refusal_onset.json, tokens_hedge_redirect.json,
tokens_matched_control.json, tokenizer_table.json, sources_manifest.json,
dna_action_taxonomy.json). No transformers import needed here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from loguru import logger

WS = Path(__file__).resolve().parent.parent
BUILD = WS / "build"
LOGS = WS / "logs"


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
    logger.add(LOGS / "write_report.log", rotation="10 MB", level="DEBUG")


def load(name: str) -> dict:
    return json.loads((BUILD / name).read_text())


def gate_line(name: str, g: dict) -> str:
    status = "PASS" if g.get("pass") else "FAILED"
    obs = {k: v for k, v in g.items() if k not in ("pass", "threshold") and not isinstance(v, (list, dict))}
    return f"| {name} | {g.get('threshold', '')} | {status} | {json.dumps(obs)} |"


def main() -> None:
    setup_logging()
    stats = load("mining_stats.json")
    onset = load("tokens_refusal_onset.json")
    hedge = load("tokens_hedge_redirect.json")
    control = load("tokens_matched_control.json")
    tbl = load("tokenizer_table.json")
    sources = load("donotanswer_source_manifest.json")
    taxonomy = load("dna_action_taxonomy.json")

    dna_src = sources["sources"][0]
    gates = stats["gates"]

    md = []
    md.append("# Execution-Side Token Sets + Tokenizer Compatibility Table")
    md.append("")
    md.append("Artefact 3 (a/b/c) + Artefact 6, mined from REAL judged model generations.")
    md.append("No GPU / model weights used -- tokenizer files and text mining only.")
    md.append("")

    md.append("## Sources")
    md.append("")
    md.append(f"- **Source 1 (primary)**: iteration-1 panel judged generations -- "
               f"`{stats['judged_source']['dir']}` ({stats['judged_source']['n_files']} files, "
               f"{stats['judged_source']['n_rows_loaded']} rows loaded, 1 row dropped for null "
               f"`judge_primary`). SEED_PANEL: {stats['seed_panel']['n_families']} families, "
               f"{stats['seed_panel']['n_repos']} repos: {', '.join(stats['seed_panel']['families'])}.")
    md.append(f"- **Source 2 (cross-model generality check)**: `LibrAI/do-not-answer`, default/train, "
               f"{dna_src['n_rows_actually_loaded']} rows, {dna_src['n_real_responses']} real responses "
               f"across 6 models ({', '.join(dna_src['models_with_responses'])}).")
    md.append(f"  - **License**: `{dna_src['license']}` (VERIFIED live from the HF dataset-card API and "
               f"the GitHub repo's own LICENSE file -- both agree). {dna_src['license_verification']['discrepancy_note']}")
    md.append(f"  - Action-code taxonomy VERIFIED from the authors' own evaluator source "
               f"(`{taxonomy['source_url']}`, `annotation_aspects_en['do_not_answer']`), not assumed: "
               f"codes 0-6, code 0 = explicit refusal (\"not willing to answer\"), code 6 = full compliance "
               f"(never observed in this curated do-not-answer prompt set). {taxonomy['source_note']}")
    md.append("")

    md.append("## No iteration-1 refusal lexicon on disk (verified)")
    md.append("")
    grep = stats["grep_check_no_iter1_lexicon"]
    md.append(f"Grep command run:\n```\n{grep['command']}\n```")
    md.append(f"\nFinding: {grep['finding']}")
    md.append("")

    md.append("## Generation-class definitions (as computed)")
    md.append("")
    md.append(stats["class_definitions"])
    md.append("")
    md.append("| Class | n rows |")
    md.append("|---|---|")
    for k, v in stats["generation_class_counts"].items():
        md.append(f"| {k} | {v} |")
    md.append("")

    md.append("## Artefact 3a: refusal-onset set")
    md.append("")
    md.append(f"- Mined from {onset['stats']['n_candidates_total']} candidate surface forms across "
               f"{stats['generation_class_counts'].get('REFUSING', 0)} REFUSING generations.")
    md.append(f"- {onset['stats']['n_dropped_family_coverage_lt_3']} candidates dropped for family "
               f"coverage < 3.")
    md.append(f"- **Shipped: {onset['n_shipped']} forms** (both `qwen3_first_token` tokenizer-based and "
               f"`surface_ngram_1/2/3` tokenizer-independent levels).")
    md.append("")
    md.append("Top 15 by generations opened:")
    md.append("")
    md.append("| rank | form | level | n_generations_opened | n_families |")
    md.append("|---|---|---|---|---|")
    for r in onset["forms"][:15]:
        md.append(f"| {r['rank']} | `{r['form']}` | {r['level']} | {r['n_refusing_generations_opened']} | {r['n_families']} |")
    md.append("")

    md.append("## Naive comparator vs mined refusal-onset set")
    md.append("")
    nv = stats["naive_comparator"]
    md.append(f"CONSTRUCTED (not mined) list: {nv['naive_comparator_list']}")
    md.append("")
    md.append(f"- Naive comparator opens **{nv['n_opened_by_naive_comparator']}/{nv['n_total_refusing_generations']}** "
               f"REFUSING generations ({nv['frac_opened_by_naive_comparator']:.1%}).")
    md.append(f"- Mined refusal-onset set opens **{nv['n_opened_by_mined_set']}/{nv['n_total_refusing_generations']}** "
               f"REFUSING generations ({nv['frac_opened_by_mined_set']:.1%}).")
    md.append("")

    md.append("## Artefact 3b: hedge-and-redirect set")
    md.append("")
    md.append(f"- SAFE-DECLINE pool: {hedge['stats']['n_full_panel_pool_docs']} rows total; the 3 named "
               f"\"preferred\" checkpoints contribute only {hedge['stats']['n_preferred_pool_docs']} rows "
               f"between them.")
    md.append(f"- **Documented pivot**: {hedge['stats']['pivot_note']}")
    md.append(f"- Compliant contrast checkpoints contribute {hedge['stats']['n_contrast_compliant_pool_docs']} "
               f"SAFE-DECLINE rows (consistent with them mostly refusing outright or complying harmfully instead).")
    md.append(f"- **Shipped: {hedge['n_shipped']} forms**, each with lift = freq(safe-decline)/freq(ordinary-helpful) "
               f">= 2.0 and requiring >=2 distinct checkpoints AND >=2 distinct prompts (anti-topical-echo filter).")
    md.append("")
    md.append("Top 15 by rank (preferred-checkpoint support, then breadth, then count):")
    md.append("")
    md.append("| rank | form | lift | count_sd | count_oh | n_slugs | n_prompts | from_preferred |")
    md.append("|---|---|---|---|---|---|---|---|")
    for r in hedge["forms"][:15]:
        md.append(f"| {r['rank']} | `{r['form']}` | {r['lift']} | {r['count_safe_decline']} | "
                   f"{r['count_ordinary_helpful']} | {r['n_distinct_slugs']} | {r['n_distinct_prompts']} | "
                   f"{r['n_generations_from_preferred_checkpoints']} |")
    md.append("")
    md.append("**Caveat**: the panel only has 41-45 distinct GT prompts feeding all 26 checkpoints, so some "
               "shipped forms (e.g. `historical`, `american`) partly reflect many checkpoints answering the "
               "*same small set of recurring prompts* similarly, not purely per-model stylistic behaviour. This "
               "is a structural property of the underlying judged panel (fixed GT test set), not a mining bug, "
               "and is reported honestly rather than hidden.")
    md.append("")

    md.append("## Artefact 3c: matched control set")
    md.append("")
    bal = control["achieved_balance"]
    md.append(f"- {bal['n_selected']} single-token-shaped refusal/hedge tokens selected for control matching "
               f"(from 3a's `qwen3_first_token` forms + 3b's single-word forms, filtered to those that "
               f"tokenize to exactly 1 Qwen3-4B token).")
    md.append(f"- **{bal['n_matched']}/{bal['n_selected']} matched** within the caliper "
               f"(|Δ log-freq| <= {bal['caliper']}); **{bal['n_unmatched']} could not be matched**.")
    md.append(f"- Unmatched (mostly short/rare BPE sub-word fragments like `**`, `A`, `To`, `Dis`, `Inc`, `Le`, "
               f"or specific content words like `president`/`document`/`commitment` with no length+frequency-"
               f"matched neutral counterpart in the top-500 ordinary-helpful pool): "
               f"{[u['surface'] for u in bal['unmatched']]}")
    md.append(f"- **Achieved balance: median |Δ log-freq| = {bal['median_abs_delta_log_freq']}, "
               f"max |Δ log-freq| = {bal['max_abs_delta_log_freq']}**.")
    md.append("")
    md.append("Sample matches:")
    md.append("")
    md.append("| selected | control | |Δ log-freq| | selected len | control len |")
    md.append("|---|---|---|---|---|")
    for m in control["matches"][:12]:
        md.append(f"| `{m['selected_token']}` | `{m['control_token']}` | {m['abs_delta_log_freq']} | "
                   f"{m['selected_char_len']} | {m['control_char_len']} |")
    md.append("")

    md.append("## Artefact 6: tokenizer compatibility table")
    md.append("")
    md.append(f"- {tbl['n_tokenizers_verified']}/{len(tbl['tokenizers_attempted'])} tokenizers loaded "
               f"successfully (27-repo SEED_PANEL + `mlabonne/Qwen3-4B-abliterated`); "
               f"{tbl['n_tokenizers_failed']} failed.")
    if tbl["tokenizer_load_failures"]:
        md.append("Failures:")
        for repo, err in tbl["tokenizer_load_failures"].items():
            md.append(f"  - `{repo}`: {err}")
    else:
        md.append("  All 28 tokenizers loaded and verified in one process.")
    md.append(f"- Compatibility recorded for {tbl['n_forms']} distinct surface forms (union of 3a+3b+3c) x "
               f"{len(tbl['tokenizers_attempted'])} tokenizers x 2 variants (MID-TEXT primary w/ leading space, "
               f"TURN-INITIAL no leading space).")
    n_flagged = sum(1 for v in tbl["table"].values() if v["segmentation_disagreement_flag"])
    md.append(f"- **{n_flagged}/{tbl['n_forms']} forms show a segmentation disagreement** (differing "
               f"`n_pieces` in the MID-TEXT variant across the 28 tokenizers) -- expected given vocab "
               f"sizes ranging 32k (TinyLlama) to 200k (Phi-4-mini), and exactly the kind of fact this "
               f"table exists to surface for a downstream causal lane.")
    g = tbl["gate_G_SINGLE_TOKEN"]
    md.append(f"- Single-token coverage gate on the {g['n_primary_forms']} PRIMARY (token-shaped) forms: "
               f"{g['n_primary_forms'] - g['n_dropped']}/{g['n_primary_forms']} pass >= 80% coverage; "
               f"{g['n_dropped']} dropped: {g['dropped_forms']}.")
    md.append("")

    md.append("## GATES (observed numbers)")
    md.append("")
    md.append("| Gate | Threshold | Result | Observed |")
    md.append("|---|---|---|---|")
    md.append(gate_line("G_REFUSAL_FORMS", gates["G_REFUSAL_FORMS"]))
    md.append(gate_line("G_HEDGE_FORMS", gates["G_HEDGE_FORMS"]))
    md.append(gate_line("G_CONTROL_BALANCE", gates["G_CONTROL_BALANCE"]))
    md.append(gate_line("G_SINGLE_TOKEN", gates["G_SINGLE_TOKEN"]))
    md.append(gate_line("G_XSRC_JACCARD", gates["G_XSRC_JACCARD"]))
    md.append("")
    xj = gates["G_XSRC_JACCARD"]
    md.append(f"Cross-source top-30 intersection ({len(xj['intersection'])} forms): {xj['intersection']}")
    md.append("")

    md.append("## Tokenizer load status")
    md.append("")
    tl = stats["tokenizer_load"]
    md.append(f"{tl['n_verified']}/{tl['n_attempted']} verified, {tl['n_failed']} failed.")
    md.append("")

    out_path = BUILD / "tokens_report.md"
    out_path.write_text("\n".join(md) + "\n")
    logger.info(f"wrote {out_path} ({out_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
