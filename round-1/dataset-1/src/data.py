#!/usr/bin/env python3
"""Standardise the acquired safety corpora into the exp_sel_data_out schema.

One ROW of a source dataset becomes ONE example. Examples are grouped by
dataset. Only `input`, `output` and flat `metadata_*` fields are emitted, which
is what the schema allows.

Run with: uv run data.py
Standard library only, so it needs no environment beyond Python 3.12.
"""

from __future__ import annotations

import csv
import json
import logging
import random
import re
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

log = logging.getLogger("data")
logging.basicConfig(level=logging.INFO, format="%(asctime)s|%(levelname)-7s|%(message)s", datefmt="%H:%M:%S")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "temp/datasets"
OUT = ROOT / "full_data_out.json"
SEED = 20260920
MAX_ROWS = 2000  # per dataset; larger sources are seed-sampled so the file stays under the size limit

# The OR-Bench 10-value harm vocabulary this whole artifact standardises on.
VOCAB = ["deception", "harassment", "harmful", "hate", "illegal",
         "privacy", "self-harm", "sexual", "unethical", "violence"]

# Fixed keyword table, identical to src/harm_domains.py. First match wins.
KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("self-harm", ("suicide", "kill myself", "end my life", "self-harm", "cut myself", "starve myself", "overdose")),
    ("hate", ("racist", "racial slur", "slur", "immigrants", "black people", "jewish", "jews", "roma", "muslim",
              "gay people", "trans people", "women are", "genocide", "holocaust", "ethnic", "disabled")),
    ("sexual", ("porn", "sexual", "rape", "pedophil", "molest", "nude", "prostitut", "adult content")),
    ("violence", ("kill", "murder", "shoot", "stab", "assault", "attack", "beat up", "poison", "strangle",
                  "behead", "torture", "bomb", "terror", "weapon", "gun", "knife", "crush", "eradicate",
                  "exterminate", "wipe out", "decimate", "eliminate", "execute", "arson", "burn down", "animal_abuse")),
    ("illegal", ("cocaine", "meth", "crack", "lsd", "marihuana", "marijuana", "heroin", "drug", "smuggl",
                 "launder", "counterfeit", "steal", "shoplift", "rob", "burglar", "traffick", "kidnap",
                 "hack", "pirate", "evade tax", "treason", "firearm", "chemical_biological", "cybercrime",
                 "vulnerabilit", "malware", "ransomware", "ddos", "sql injection", "botnet", "keylogger",
                 "amphetamine", "narcotic", "controlled substance")),
    ("privacy", ("address of", "phone number", "social security", "credit card", "password", "private information",
                 "home address", "track someone", "stalk", "spy on", "medical record", "privacy")),
    ("deception", ("scam", "fraud", "phish", "forge", "fake", "impersonat", "lie to", "mislead", "identity theft",
                   "deny that", "propaganda", "misinformation", "disinformation")),
    ("harassment", ("bully", "harass", "threaten", "intimidat", "insult", "humiliat", "troll", "doxx", "meanest")),
    ("unethical", ("cheat", "plagiar", "bribe", "exploit", "manipulate", "blackmail", "unethical")),
]


# Several sources label rows with a category string that already CONTAINS a
# vocabulary word ("Illegal goods and services", "Hate speech"). Checking for
# that literal first is both more accurate and more honest than inferring it
# from the prompt text, so it takes precedence over the keyword table.
_VOCAB_LITERAL = [("self-harm", ("self-harm", "self harm", "suicide")),
                  ("harassment", ("harassment",)), ("deception", ("deception", "disinformation", "misinformation")),
                  ("hate", ("hate",)), ("illegal", ("illegal",)), ("privacy", ("privacy",)),
                  ("sexual", ("sexual", "adult content")), ("unethical", ("unethical",)),
                  ("violence", ("violence", "violent")), ("harmful", ("harmful",))]


def harm_domain(*texts: Any) -> str | None:
    """Map free text onto the OR-Bench vocabulary. None when nothing matches.

    A vocabulary word appearing literally in a category label wins; otherwise
    the fixed keyword table decides.
    """
    label_blob = str(texts[0]).lower() if texts and texts[0] else ""
    for lab, lits in _VOCAB_LITERAL:
        if any(l in label_blob for l in lits):
            return lab
    blob = " ".join(str(t) for t in texts if t).lower()
    if not blob.strip():
        return None
    for lab, kws in KEYWORDS:
        if any(k in blob for k in kws):
            return lab
    return None


def s(v: Any) -> str:
    """Schema requires strings for input and output."""
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(str(x) for x in v)
    return str(v)


def load_json(name: str) -> list[dict]:
    p = DATA / f"full_{name}.json"
    if not p.exists():
        raise FileNotFoundError(p)
    rows = json.loads(p.read_text())
    if not isinstance(rows, list):
        raise ValueError(f"{p} is not a JSON array")
    return rows


def load_twin_domains() -> dict[int, str]:
    """The authoritative per-pair harm domain already fixed in results/twin_pairs.json.

    Reusing it keeps the source table and the stimulus substrate on ONE label per
    XSTest row instead of two independently-derived ones.
    """
    p = ROOT / "results/twin_pairs.json"
    if not p.exists():
        log.warning("results/twin_pairs.json absent; falling back to the keyword table for XSTest")
        return {}
    out: dict[int, str] = {}
    for pair in json.loads(p.read_text()).get("pairs", []):
        dom = pair.get("harm_domain")
        if dom:
            out[int(pair["safe_id"])] = dom
            out[int(pair["contrast_id"])] = dom
    log.info(f"loaded authoritative harm domains for {len(out)} XSTest rows from results/twin_pairs.json")
    return out


TWIN_DOMAINS: dict[int, str] = {}


def load_xstest() -> list[dict]:
    with (DATA / "xstest_prompts.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --------------------------------------------------------------------------
# One adapter per dataset. Each returns the example dict for a single row.
# --------------------------------------------------------------------------

def a_xstest(r: dict, i: int) -> dict:
    fam = r["type"]
    return {
        "input": s(r["prompt"]),
        "output": s(r["label"]),
        "metadata_row_index": i,
        "metadata_task_type": "classification",
        "metadata_n_classes": 2,
        "metadata_xstest_id": int(r["id"]),
        "metadata_family": fam,
        "metadata_is_contrast_member": fam.startswith("contrast_"),
        "metadata_focus": r.get("focus") or None,
        "metadata_note": r.get("note") or None,
        "metadata_harm_domain": (TWIN_DOMAINS.get(int(r["id"])) or harm_domain(r.get("note"), r["prompt"])),
        "metadata_harm_domain_source": ("results/twin_pairs.json (authoritative, shared with the stimulus substrate)"
                                        if int(r["id"]) in TWIN_DOMAINS else "keyword table"),
        "metadata_in_twin_pair": int(r["id"]) in TWIN_DOMAINS,
        "metadata_role": "harmful_twin" if r["label"] == "unsafe" else "benign_twin",
    }


def a_orbench(cfg: str) -> Callable[[dict, int], dict]:
    def f(r: dict, i: int) -> dict:
        return {
            "input": s(r["prompt"]),
            "output": s(r["category"]),
            "metadata_row_index": i,
            "metadata_task_type": "classification",
            "metadata_n_classes": 10,
            "metadata_harm_domain": r["category"] if r["category"] in VOCAB else harm_domain(r["prompt"]),
            "metadata_role": "toxic" if cfg == "or-bench-toxic" else "hard_benign_over_refusal",
            "metadata_orbench_config": cfg,
        }
    return f


def a_strongreject(r: dict, i: int) -> dict:
    return {
        "input": s(r["forbidden_prompt"]),
        "output": s(r["category"]),
        "metadata_row_index": i,
        "metadata_task_type": "classification",
        "metadata_strongreject_source": r.get("source") or None,
        "metadata_harm_domain": harm_domain(r.get("category"), r["forbidden_prompt"]),
        "metadata_role": "harmful_request",
    }


def a_advbench_behaviors(r: dict, i: int) -> dict:
    return {
        "input": s(r["goal"]),
        "output": s(r["target"]),
        "metadata_row_index": i,
        "metadata_task_type": "generation",
        "metadata_harm_domain": harm_domain(r["goal"]),
        "metadata_role": "harmful_request",
        "metadata_output_is": "the affirmative-compliance target string AdvBench pairs with the goal",
    }


def a_advbench_strings(r: dict, i: int) -> dict:
    return {
        "input": s(r["target"]),
        "output": "harmful_string",
        "metadata_row_index": i,
        "metadata_task_type": "classification",
        "metadata_harm_domain": harm_domain(r["target"]),
        "metadata_role": "harmful_completion_string",
        "metadata_schema_note": "AdvBench harmful_strings has no prompt column; the string itself is the input and "
                                "the output is a constant class label",
    }


def a_jbb(split: str) -> Callable[[dict, int], dict]:
    def f(r: dict, i: int) -> dict:
        return {
            "input": s(r["Goal"]),
            "output": s(r["Target"]),
            "metadata_row_index": i,
            "metadata_task_type": "generation",
            "metadata_behavior": r.get("Behavior") or None,
            "metadata_category": r.get("Category") or None,
            "metadata_jbb_source_flag": r.get("Source") or None,
            "metadata_harm_domain": harm_domain(r.get("Category"), r["Goal"]) if split == "harmful" else None,
            "metadata_role": "harmful_request" if split == "harmful" else "matched_benign_request",
        }
    return f


def a_phtest(r: dict, i: int) -> dict:
    return {
        "input": s(r["Request"]),
        "output": s(r["Harmfulness"]),
        "metadata_row_index": i,
        "metadata_task_type": "classification",
        "metadata_n_classes": 2,
        "metadata_harm_domain": harm_domain(r["Request"]),
        "metadata_role": "pseudo_harmful_over_refusal",
    }


def a_harmbench(r: dict, i: int) -> dict:
    return {
        "input": s(r["Behavior"]),
        "output": s(r["SemanticCategory"]),
        "metadata_row_index": i,
        "metadata_task_type": "classification",
        "metadata_functional_category": r.get("FunctionalCategory") or None,
        "metadata_tags": r.get("Tags") or None,
        "metadata_context_string": r.get("ContextString") or None,
        "metadata_behavior_id": r.get("BehaviorID") or None,
        "metadata_harm_domain": harm_domain(r.get("SemanticCategory"), r["Behavior"]),
        "metadata_role": "harmful_request",
    }


def a_sorrybench(r: dict, i: int) -> dict:
    return {
        "input": s(r["turns"]),
        "output": s(r["category"]),
        "metadata_row_index": i,
        "metadata_task_type": "classification",
        "metadata_n_classes": 45,
        "metadata_prompt_style": r.get("prompt_style") or None,
        "metadata_question_id": r.get("question_id") or None,
        "metadata_harm_domain": harm_domain(r["turns"]),
        "metadata_role": "harmful_request",
    }


def a_do_not_answer(r: dict, i: int) -> dict:
    return {
        "input": s(r["question"]),
        "output": s(r["types_of_harm"]),
        "metadata_row_index": i,
        "metadata_task_type": "classification",
        "metadata_risk_area": r.get("risk_area") or None,
        "metadata_specific_harms": r.get("specific_harms") or None,
        "metadata_reference_response": s(r.get("GPT4_response"))[:2000] or None,
        "metadata_harm_domain": harm_domain(r.get("types_of_harm"), r["question"]),
        "metadata_role": "should_be_refused_request",
    }


def a_beavertails_eval(r: dict, i: int) -> dict:
    return {
        "input": s(r["prompt"]),
        "output": s(r["category"]),
        "metadata_row_index": i,
        "metadata_task_type": "classification",
        "metadata_category_id": r.get("category_id"),
        "metadata_harm_domain": harm_domain(r["category"], r["prompt"]),
        "metadata_role": "harmful_request",
    }


def a_dolly(r: dict, i: int) -> dict:
    ctx = s(r.get("context")).strip()
    inp = s(r["instruction"]).strip()
    if ctx:
        inp = f"{inp}\n\n{ctx}"
    return {
        "input": inp,
        "output": s(r["response"]),
        "metadata_row_index": i,
        "metadata_task_type": "generation",
        "metadata_dolly_category": r.get("category") or None,
        "metadata_has_context": bool(ctx),
        "metadata_harm_domain": None,
        "metadata_role": "neutral_instruction",
    }


# --------------------------------------------------------------------------
# THE BEST 10, chosen after inspecting the preview. Selection criterion: does
# the dataset do a job this artifact's objective actually requires, with
# verifiable provenance and a licence safe to redistribute?
# --------------------------------------------------------------------------
TOP10: dict[str, str] = {
    "xstest_v2": "THE minimal-edit twin source. The entire request factor of the 2x2 is built from it and nothing "
                 "else can supply row-level harmful/benign correspondence. Non-negotiable.",
    "or_bench_hard_1k": "the hard-benign over-refusal set for lane C, and the origin of the 10-value harm-domain "
                        "vocabulary the whole artifact standardises on.",
    "or_bench_toxic": "same vocabulary, near-opposite category skew, so it is what tops up the domains XSTest is "
                      "too violence-skewed to cover.",
    "strongreject_small": "peer-reviewed (NeurIPS 2024) harmful-request set; supplies both the lane-C behavioural "
                          "set and the harmful action phrases of the fitting corpus.",
    "advbench_harmful_behaviors": "canonical harmful behaviours; the rest of the fitting-corpus action phrases, "
                                  "verified to share no action lemma or 4-gram with XSTest.",
    "jbb_behaviors_harmful": "the second half of the lane-C harmful set, and its Source column is a free "
                             "contamination flag.",
    "jbb_behaviors_benign": "the only paired benign/harmful resource besides XSTest: 100 topic-matched benign "
                            "counterparts, which makes it a genuine external check on the twin design.",
    "databricks_dolly_15k": "the neutral instruction corpus the contentless set and the benign half of the fitting "
                            "corpus are actually sampled from.",
    "phtest": "pseudo-harmful over-refusal pool with an explicit harmfulness tier, used to top up any thin "
              "over-refusal category.",
    "harmbench": "standardised harmful behaviours spanning chemical/biological, cyber and misinformation -- the "
                 "domains XSTest does not reach at all.",
}
DISCARDED: dict[str, str] = {
    "strongreject_full": "a superset of strongreject_small, which is the registered behavioural set; keeping both "
                         "would double-count the same items.",
    "advbench_harmful_strings": "has no prompt column at all, so it only fits the input/output schema awkwardly "
                                "(the string is the input and the output is a constant label), and nothing in this "
                                "artifact reads it.",
    "sorrybench_base": "licence did not resolve from the dataset card, and its 45-category taxonomy does not map "
                       "onto the 10-value vocabulary this artifact standardises on.",
    "do_not_answer": "genuinely good, but redundant with JBB + StrongREJECT for lane C, and the part that is "
                     "distinctive (its reference responses) is not read by this artifact.",
    "beavertails_evaluation": "CC-BY-NC-4.0, i.e. non-commercial, which is a worse redistribution licence than the "
                              "alternatives, and it is redundant with harmbench and JBB for the harmful set.",
}


# name -> (loader, adapter, row filter or None, provenance)
SPECS: list[tuple[str, Callable[[], list[dict]], Callable[[dict, int], dict], Callable[[dict], bool] | None, dict]] = [
    ("xstest_v2", load_xstest, a_xstest, None,
     dict(source="https://raw.githubusercontent.com/paul-rottger/exaggerated-safety/main/xstest_prompts.csv",
          license="CC-BY-4.0", role="THE minimal-edit twin source for the request factor")),
    ("or_bench_toxic", lambda: load_json("or_bench_toxic"), a_orbench("or-bench-toxic"), None,
     dict(source="bench-llm/or-bench:or-bench-toxic", license="CC-BY-4.0",
          role="toxic prompts; supplies the 10-value harm-domain vocabulary and thin-domain top-ups")),
    ("or_bench_hard_1k", lambda: load_json("or_bench_hard_1k"), a_orbench("or-bench-hard-1k"), None,
     dict(source="bench-llm/or-bench:or-bench-hard-1k", license="CC-BY-4.0",
          role="hard-benign over-refusal set for lane C")),
    ("strongreject_small", lambda: load_json("strongreject_small"), a_strongreject, None,
     dict(source="alexandrasouly/strongreject strongreject_small_dataset.csv", license="MIT",
          role="behavioural harmful-request set + harmful action phrases for the fitting corpus")),
    ("strongreject_full", lambda: load_json("strongreject_full"), a_strongreject, None,
     dict(source="alexandrasouly/strongreject strongreject_dataset.csv", license="MIT",
          role="full StrongREJECT; reserve pool")),
    ("advbench_harmful_behaviors", lambda: load_json("advbench_harmful_behaviors"), a_advbench_behaviors, None,
     dict(source="llm-attacks/llm-attacks advbench/harmful_behaviors.csv", license="MIT",
          role="harmful action phrases for the fitting corpus, disjoint from XSTest")),
    ("advbench_harmful_strings", lambda: load_json("advbench_harmful_strings"), a_advbench_strings, None,
     dict(source="llm-attacks/llm-attacks advbench/harmful_strings.csv", license="MIT",
          role="harmful completion strings; reserve pool")),
    ("jbb_behaviors_harmful", lambda: load_json("jbb_behaviors_harmful"), a_jbb("harmful"), None,
     dict(source="JailbreakBench/JBB-Behaviors:behaviors[harmful]", license="MIT",
          role="behavioural harmful-request set for lane C")),
    ("jbb_behaviors_benign", lambda: load_json("jbb_behaviors_benign"), a_jbb("benign"), None,
     dict(source="JailbreakBench/JBB-Behaviors:behaviors[benign]", license="MIT",
          role="topic-matched benign counterparts to the JBB harmful behaviours")),
    ("phtest", lambda: load_json("phtest"), a_phtest, None,
     dict(source="furonghuang-lab/PHTest", license="MIT",
          role="pseudo-harmful over-refusal top-up pool")),
    ("harmbench", lambda: load_json("harmbench"), a_harmbench, None,
     dict(source="swiss-ai/harmbench:DirectRequest (ungated mirror; walledai/HarmBench is gated)", license="unverified",
          role="standardised harmful-behaviour set spanning chemical/biological, cyber and misinformation")),
    ("sorrybench_base", lambda: load_json("sorrybench"), a_sorrybench,
     lambda r: r.get("prompt_style") == "base",
     dict(source="SillyTilly/SorryBench", license="unverified",
          role="fine-grained 45-category harmful requests; ONLY the `base` prompt style is kept because the other "
               "20 styles are jailbreak mutations and this is not a jailbreak study")),
    ("do_not_answer", lambda: load_json("do_not_answer"), a_do_not_answer, None,
     dict(source="LibrAI/do-not-answer", license="apache-2.0",
          role="requests a responsible model should refuse, with reference responses")),
    ("beavertails_evaluation", lambda: load_json("beavertails_evaluation"), a_beavertails_eval, None,
     dict(source="PKU-Alignment/BeaverTails-Evaluation", license="CC-BY-NC-4.0",
          role="held-out 14-category harmful prompt set")),
    ("databricks_dolly_15k", lambda: load_json("databricks_dolly_15k"), a_dolly, None,
     dict(source="databricks/databricks-dolly-15k", license="CC-BY-SA-3.0",
          role="neutral instruction corpus for the contentless set and the benign half of the fitting corpus")),
]


def build() -> dict[str, Any]:
    global TWIN_DOMAINS
    TWIN_DOMAINS = load_twin_domains()
    rng = random.Random(SEED)
    datasets: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []

    for name, loader, adapt, keep, prov in SPECS:
        if name not in TOP10:
            log.info(f"{name:28s} DISCARDED -- {DISCARDED[name]}")
            continue
        rows = loader()
        n_raw = len(rows)
        if keep is not None:
            rows = [r for r in rows if keep(r)]
        n_filtered = len(rows)
        sampled = False
        if n_filtered > MAX_ROWS:
            idx = sorted(rng.sample(range(n_filtered), MAX_ROWS))
            rows = [rows[i] for i in idx]
            sampled = True
        else:
            idx = list(range(n_filtered))

        examples = []
        for orig_i, r in zip(idx, rows):
            try:
                ex = adapt(r, orig_i)
            except (KeyError, TypeError, ValueError) as e:
                log.error(f"{name}: row {orig_i} failed to adapt: {type(e).__name__}: {e}")
                continue
            if not ex["input"].strip():
                continue
            ex = {k: v for k, v in ex.items() if v is not None}
            ex.setdefault("output", "")
            examples.append(ex)

        if not examples:
            log.error(f"{name}: produced ZERO examples -- skipping")
            continue

        datasets.append({"dataset": name, "examples": examples})
        report.append({
            "dataset": name, "n_rows_source": n_raw, "n_rows_after_filter": n_filtered,
            "n_examples": len(examples), "seed_sampled_to_max": sampled, "max_rows": MAX_ROWS, **prov,
        })
        log.info(f"{name:28s} {n_raw:6d} raw -> {n_filtered:6d} kept -> {len(examples):5d} examples"
                 f"{'  (seed-sampled)' if sampled else ''}")

    total = sum(len(d["examples"]) for d in datasets)
    log.info(f"TOTAL {len(datasets)} datasets, {total} examples")

    return {
        "metadata": {
            "artifact": "source corpora for the frozen safety stimulus substrate",
            "run_id": "run_YqmEFECOIR3D",
            "schema": "exp_sel_data_out",
            "one_example_per": "row of the source dataset",
            "seed": SEED,
            "max_rows_per_dataset": MAX_ROWS,
            "max_rows_note": "sources larger than max_rows are sampled with random.Random(20260920) so the output "
                             "stays under the file-size limit; metadata_row_index keeps the original row index",
            "harm_domain_vocabulary": VOCAB,
            "harm_domain_method": "fixed keyword table (published in data.py), identical to src/harm_domains.py; "
                                  "null where nothing matches or the row is benign by construction",
            "selection": {
                "n_candidates_standardised": len(SPECS),
                "n_kept": len(TOP10),
                "kept_and_why": TOP10,
                "discarded_and_why": DISCARDED,
                "all_15_candidate_version": "results/full_data_out_all15.json",
            },
            "n_datasets": len(datasets),
            "n_examples": total,
            "per_dataset": report,
            "not_included": {
                "tatsu-lab/alpaca": "second neutral corpus; dolly is the one the substrate actually samples from",
                "PKU-Alignment/BeaverTails (30k)": "superseded by its official held-out evaluation split",
                "nvidia/Aegis-AI-Content-Safety-2.0": "moderation-labelled dialogues, not a request set this study reads",
                "bench-llm/or-bench:or-bench-80k": "explicitly forbidden by the plan; never ingested",
                "walledai/HarmBench, allenai/wildguardmix": "gated=auto; skipped, never authenticated or substituted",
            },
        },
        "datasets": datasets,
    }


def main() -> None:
    try:
        obj = build()
    except FileNotFoundError as e:
        log.error(f"missing source file: {e}")
        raise
    OUT.write_text(json.dumps(obj, ensure_ascii=False, indent=1))
    mb = OUT.stat().st_size / 1e6
    log.info(f"wrote {OUT.name}: {mb:.2f} MB")
    if mb > 10:
        log.warning("output exceeds the 10 MB limit -- run the aii-file-size-limit split")


if __name__ == "__main__":
    main()
