"""Tiny smoke test for judge.py. Run with:
    cd WS && .venv/bin/python src/test_judge.py

Uses 4 BENIGN synthetic records (no harmful text anywhere), a real
OPENROUTER_API_KEY from the environment, and a cache/ledger scoped to
WS/out/test_judge/ (kept separate from WS/.aii_cost_ledger.jsonl).
Total spend must stay under $0.01.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import judge  # noqa: E402

WS = Path(__file__).resolve().parent.parent
TEST_DIR = WS / "out" / "test_judge"
CACHE_PATH = TEST_DIR / "cache.jsonl"
LEDGER_PATH = TEST_DIR / "ledger.jsonl"


def main() -> None:
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    assert LEDGER_PATH != (WS / ".aii_cost_ledger.jsonl"), "test ledger must be separate from the real one"

    print(f"assets/lc_judge_iter1.py sha256: {judge.JUDGE_PY_SHA256}")
    print(f"assets/rubric_iter1.md   sha256: {judge.RUBRIC_SHA256_FILE}")
    assert judge.JUDGE_PY_SHA256 == "71c4ba09f494a5f7f7bd2ddc345337ad8c05e8c47c961ad68946172401056c65"
    assert judge.RUBRIC_SHA256_FILE == "b11e322dc64e25f79bdb909fdda571fd856345a4b74b39c827d7bfd431194629"

    req_bread = "How do I bake bread?"
    resp_refuse = "I'm sorry, but I can't help with that."
    resp_help = (
        "Mix flour, water, yeast and salt, knead for 10 minutes, let it rise for "
        "an hour, then bake at 220C for 30 minutes."
    )
    req_france = "What is the capital of France?"
    resp_france = "Paris."

    records = [
        {"request": req_bread, "response": resp_refuse},  # (a)
        {"request": req_bread, "response": resp_help},  # (b)
        {"request": req_bread, "response": resp_refuse},  # (c) duplicate of (a)
        {"request": req_france, "response": resp_france},  # (d)
    ]

    # keyword_proxy sanity checks (no API calls)
    proxy_a = judge.keyword_proxy(resp_refuse)
    proxy_b = judge.keyword_proxy(resp_help)
    assert proxy_a["refused"] is True, proxy_a
    assert proxy_b["refused"] is False, proxy_b
    print(f"keyword_proxy(a) = {proxy_a}")
    print(f"keyword_proxy(b) = {proxy_b}")

    ledger_before = judge.ledger_total(LEDGER_PATH)
    print(f"ledger before: ${ledger_before:.6f}")

    labels1, stats1 = judge.judge_sync(records, cache_path=CACHE_PATH, ledger_path=LEDGER_PATH)
    print("=== first call stats ===")
    for k, v in stats1.items():
        print(f"  {k}: {v}")
    print("=== first call labels ===")
    for i, lab in enumerate(labels1):
        print(f"  [{i}] {lab}")

    assert stats1["n_records"] == 4
    assert stats1["n_unique"] == 3, f"expected 3 unique (a==c dup), got {stats1['n_unique']}"
    # dedup: only 3 unique records should ever be sent to the API
    assert stats1["n_api_calls_made"] <= 3, f"n_api_calls_made={stats1['n_api_calls_made']} exceeds unique count"
    assert all(lab is not None for lab in labels1), f"expected 4/4 non-None labels, got {labels1}"

    lab_a, lab_b, lab_c, lab_d = labels1
    assert lab_a["refused"] is True, lab_a
    assert lab_b["refused"] is False, lab_b
    assert lab_b["on_topic_help"] is True, lab_b
    assert lab_b["harmful_content"] is False, lab_b
    assert lab_a == lab_c or (lab_a["refused"] == lab_c["refused"]), "duplicate (a)/(c) must agree (same key)"
    print(f"[d] capital-of-France label: {lab_d}")

    ledger_after_1 = judge.ledger_total(LEDGER_PATH)
    print(f"ledger after call 1: ${ledger_after_1:.6f}")

    # second call: everything should come from cache now, zero new API calls
    labels2, stats2 = judge.judge_sync(records, cache_path=CACHE_PATH, ledger_path=LEDGER_PATH)
    print("=== second call stats (should be all cache) ===")
    for k, v in stats2.items():
        print(f"  {k}: {v}")
    assert stats2["n_api_calls_made"] == 0, f"expected 0 API calls on cached re-run, got {stats2['n_api_calls_made']}"
    assert stats2["n_cache_hits"] == 4, f"expected 4 cache hits, got {stats2['n_cache_hits']}"
    assert all(lab is not None for lab in labels2)
    for lab in labels2:
        assert lab.get("source") == "cache", lab

    ledger_after_2 = judge.ledger_total(LEDGER_PATH)
    print(f"ledger after call 2 (cache-only): ${ledger_after_2:.6f}")
    assert ledger_after_2 == ledger_after_1, "cache-only call must not add any cost"

    total_spend = ledger_after_2
    print(f"TOTAL SPEND: ${total_spend:.6f}")
    assert total_spend < 0.01, f"spend ${total_spend:.6f} exceeds $0.01 budget"

    # agreement() sanity: compare judge labels against keyword_proxy on the responses
    proxy_labels = [judge.keyword_proxy(r["response"]) for r in records]
    agr = judge.agreement(labels1, proxy_labels)
    print(f"agreement(judge, proxy): {agr}")
    assert agr["n_pairs"] == 4

    # derive() sanity
    derived_harm = judge.derive(lab_b, "harm")
    derived_hb = judge.derive(lab_a, "hb")
    print(f"derive(b, 'harm') = {derived_harm}")
    print(f"derive(a, 'hb')   = {derived_hb}")
    assert derived_harm["safe_engagement"] is True
    assert derived_hb["over_refusal"] is True

    print("ALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
