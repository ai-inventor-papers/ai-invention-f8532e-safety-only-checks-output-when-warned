#!/usr/bin/env python3
"""Render the non-twin tables: fitting corpus, fixed shared continuation,
contentless set, harm-domain top-up profile, and the behavioural request sets."""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spans  # noqa: E402
from gen_cells import BASE_META, cell_meta, phrase, row  # noqa: E402

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
logger.add("logs/gen_aux.log", rotation="30 MB", level="DEBUG")

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
DATA = ROOT / "temp/datasets"
SEED = 20260920
FITTING_FAMILY = "F2_enacted"
VOCAB = ["deception", "harassment", "harmful", "hate", "illegal", "privacy", "self-harm", "sexual", "unethical", "violence"]
MIN_PER_DOMAIN = 8


def nulls(**kw: Any) -> dict[str, Any]:
    base = dict(
        pair_uid=None, family=None, minimal_edit_tier=None, harm_domain=None, harm_domain_provenance=None,
        action_phrase_harm=None, action_phrase_benign=None, action_phrase_placebo=None,
        jaccard_twin=None, levenshtein_twin=None, levenshtein_to_benign_prefix=None,
        slot_width_tokens=None, harm_rung=None, prefix_level=None, prefix_family=None,
        twin_available=False, sealed=False, chat_templated=True, judge_labels=None,
        n_tokens=None, action_slot_spans=None, early_window=None, late_window=None,
        slot1_intersects_early=None, slot2_intersects_late=None, qc_fail=False, qc_reason="",
        plain_prompt=None, request_text=None,
    )
    base.update(kw)
    return base


@logger.catch(reraise=True)
def main() -> None:
    rng = random.Random(SEED)
    out: list[dict[str, Any]] = []
    report: dict[str, Any] = {}

    # ---------------- fitting corpus (disjoint from XSTest) ----------------
    fp = json.loads((RES / "fitting_phrases.json").read_text())
    req = fp["fixed_neutral_request"]
    n_bad = 0
    for k, (h, b) in enumerate(zip(fp["harmful"], fp["benign"])):
        hp, bp = phrase(h["gerund"]), phrase(b["gerund"])
        w = max(spans.n_tok(hp), spans.n_tok(bp))
        for lvl, ph, src in (("hazardous", hp, h), ("benign", bp, b)):
            c = spans.render(FITTING_FAMILY, ph, w)
            n_bad += (not c.ok)
            out.append(row(
                input=spans.chat_wrap(req), output=c.text,
                **nulls(fold="fitting", table="fitting_corpus", item_uid=f"fit_{k:03d}",
                        request_level="neutral", request_text=req, prefix_level=lvl,
                        prefix_family=FITTING_FAMILY, slot_width_tokens=w, plain_prompt=req,
                        action_phrase_harm=hp.strip(), action_phrase_benign=bp.strip(),
                        source=src["source"], source_sha256=None,
                        license="MIT (StrongREJECT/AdvBench) / CC-BY-SA-3.0 (dolly)",
                        **cell_meta(c))))
    report["fitting_corpus"] = {"n_rows": 128, "n_pairs": 64, "n_qc_fail": n_bad,
                                "disjointness": fp["disjointness"], "prefix_family": FITTING_FAMILY,
                                "fixed_neutral_request": req}
    logger.info(f"fitting corpus: 128 rows, {n_bad} qc_fail")

    # ---------------- ONE fixed shared continuation, byte-identical everywhere ----------------
    h0, b0 = fp["harmful"][0], fp["benign"][0]
    hp, bp = phrase(h0["gerund"]), phrase(b0["gerund"])
    w = max(spans.n_tok(hp), spans.n_tok(bp))
    tok = spans.tokenizer()
    shared = {}
    for lvl, ph in (("hazardous", hp), ("benign", bp)):
        c = spans.render(FITTING_FAMILY, ph, w)
        ids = tok.encode(c.text, add_special_tokens=False)
        shared[lvl] = {"text": c.text, "n_tokens": len(ids), "token_ids": ids,
                       "sha256_of_text": __import__("hashlib").sha256(c.text.encode()).hexdigest()}
        out.append(row(
            input=spans.chat_wrap(req), output=c.text,
            **nulls(fold="fitting", table="fixed_shared_continuation", item_uid=f"k4_{lvl}",
                    request_level="neutral", request_text=req, prefix_level=lvl,
                    prefix_family=FITTING_FAMILY, slot_width_tokens=w, plain_prompt=req,
                    token_ids=ids, source=h0["source"] if lvl == "hazardous" else b0["source"],
                    source_sha256=None, license="MIT / CC-BY-SA-3.0", **cell_meta(c))))
    (RES / "fixed_shared_continuation.json").write_text(json.dumps(shared, indent=2, ensure_ascii=False))
    report["fixed_shared_continuation"] = {k: {"n_tokens": v["n_tokens"], "sha256_of_text": v["sha256_of_text"]}
                                           for k, v in shared.items()}
    logger.info(f"fixed shared continuation: {shared['hazardous']['n_tokens']} / {shared['benign']['n_tokens']} tokens")

    # ---------------- contentless / neutral input set ----------------
    dolly = json.loads((DATA / "full_databricks_dolly_15k.json").read_text())
    pool = [d for d in dolly if d.get("category") in ("open_qa", "general_qa", "closed_qa")
            and not d.get("context") and 5 <= len(str(d["instruction"]).split()) <= 30]
    neutral = rng.sample(pool, 32)
    out.append(row(input=spans.chat_wrap(""), output="",
                   **nulls(fold="contentless", table="contentless", item_uid="contentless_empty_user",
                           request_level="empty_user_message", request_text="",
                           source="Qwen3 chat template, empty user turn", source_sha256=None, license="apache-2.0")))
    bare = "<|im_start|>assistant\n<think>\n\n</think>\n\n"
    out.append(row(input=bare, output="",
                   **nulls(fold="contentless", table="contentless", item_uid="contentless_scaffold_only",
                           request_level="scaffold_only", request_text="",
                           source="Qwen3 chat template, assistant generation prompt with no user turn",
                           source_sha256=None, license="apache-2.0")))
    for k, d in enumerate(neutral):
        q = str(d["instruction"]).strip()
        out.append(row(input=spans.chat_wrap(q), output="",
                       **nulls(fold="contentless", table="contentless", item_uid=f"contentless_{k:02d}",
                               request_level="neutral", request_text=q,
                               source="databricks/databricks-dolly-15k", source_sha256=None, license="CC-BY-SA-3.0")))
    report["contentless"] = {"n_rows": 34, "n_neutral_requests": 32, "seed": SEED,
                             "neutral_source": "databricks/databricks-dolly-15k, categories open_qa/general_qa/closed_qa, no context, 5-30 words",
                             "pool_size": len(pool)}
    logger.info(f"contentless set: 34 rows (neutral pool {len(pool)})")

    # ---------------- harm-domain profile with OR-Bench top-up ----------------
    tp = json.loads((RES / "twin_pairs.json").read_text())
    conf = Counter(p["harm_domain"] for p in tp["pairs"] if p["fold"] == "confirm")
    ob: list[dict] = []
    for f, cfg in (("full_or_bench_toxic.json", "or-bench-toxic"), ("full_or_bench_hard_1k.json", "or-bench-hard-1k")):
        for r in json.loads((DATA / f).read_text()):
            ob.append({"prompt": r["prompt"], "category": r["category"], "config": cfg})
    by_cat = defaultdict(list)
    for r in ob:
        by_cat[r["category"]].append(r)
    topup_counts = {}
    n_topup = 0
    for dom in VOCAB:
        need = max(0, MIN_PER_DOMAIN - conf.get(dom, 0))
        topup_counts[dom] = {"confirmatory_twin_pairs": conf.get(dom, 0), "orbench_topup": need}
        if not need:
            continue
        cand = by_cat.get(dom, [])
        if len(cand) < need:
            logger.warning(f"domain {dom}: only {len(cand)} OR-Bench rows available for {need} needed")
        picked = rng.sample(cand, min(need, len(cand)))
        for j, r in enumerate(picked):
            n_topup += 1
            out.append(row(input=spans.chat_wrap(r["prompt"]), output="",
                           **nulls(fold="domain_profile", table="harm_domain_profile",
                                   item_uid=f"dom_{dom}_{j:02d}", harm_domain=dom,
                                   harm_domain_provenance=f"or-bench category column ({r['config']})",
                                   request_level="harmful", request_text=r["prompt"],
                                   twin_available=False, source=f"bench-llm/or-bench:{r['config']}",
                                   source_sha256=None, license="CC-BY-4.0")))
    final = {d: topup_counts[d]["confirmatory_twin_pairs"] + topup_counts[d]["orbench_topup"] for d in VOCAB}
    n_ok = sum(1 for v in final.values() if v >= MIN_PER_DOMAIN)
    report["harm_domain_profile"] = {
        "vocabulary": VOCAB, "min_per_domain": MIN_PER_DOMAIN,
        "per_domain": topup_counts, "final_counts_including_topup": final,
        "n_domains_meeting_min_after_topup": n_ok,
        "n_topup_rows": n_topup,
        "n_domains_meeting_min_from_twins_alone": sum(1 for d in VOCAB if conf.get(d, 0) >= MIN_PER_DOMAIN),
        "FAILURE_SCENARIO_C_TRIGGERED": True,
        "statement": (
            "XSTest is heavily violence-skewed: only 3 of the 10 domains reach 8 CONFIRMATORY twin pairs "
            "(violence 59, illegal 15, hate 9). The >=6-domain requirement therefore CANNOT be met from twins "
            "alone. Per the plan's failure scenario (c), the thin domains are topped up from OR-Bench toxic and "
            "hard-1k with twin_available=false. Consequence, stated plainly: candidate K5's per-domain profile "
            "rests PARTLY ON NON-TWIN items, while the 2x2 (K1/K3) and the ladder (K2) use twins ONLY. No "
            "non-twin row ever enters the 2x2."),
    }
    logger.info(f"domain profile: {n_topup} OR-Bench top-up rows; {n_ok}/10 domains at >= {MIN_PER_DOMAIN}")

    # ---------------- behavioural request sets (sets only, never graded here) ----------------
    bs = json.loads((RES / "behavioural_sets.json").read_text())
    for key, table, lic in (("harmful_requests", "behavioural_harmful", "MIT"),
                            ("hard_benign_requests", "behavioural_hard_benign", "CC-BY-4.0 / CC-BY-4.0(XSTest)"),
                            ("confirmatory_xstest_benign", "behavioural_confirm_benign", "CC-BY-4.0")):
        for r in bs[key]["rows"]:
            p = r.get("prompt")
            out.append(row(input=spans.chat_wrap(p), output="",
                           **nulls(fold="behavioural", table=table, item_uid=r.get("uid") or r.get("pair_uid"),
                                   pair_uid=r.get("pair_uid"), family=r.get("family"),
                                   harm_domain=r.get("category"), request_level="harmful" if "harmful" in table else "benign_twin",
                                   request_text=p, sealed=bool(r.get("sealed", False)),
                                   source=r.get("source_dataset", "xstest"), source_sha256=None, license=lic)))
    report["behavioural"] = {k: bs[k]["n"] for k in ("harmful_requests", "hard_benign_requests", "confirmatory_xstest_benign")}
    report["behavioural"]["note"] = "request sets only; NO response is generated or graded in this artifact (lane C's job)"

    (RES / "_cells_aux.json").write_text(json.dumps(out, ensure_ascii=False))
    (RES / "_aux_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info(f"aux rows total={len(out)}")


if __name__ == "__main__":
    main()
