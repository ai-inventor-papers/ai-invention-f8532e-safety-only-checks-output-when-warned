#!/usr/bin/env python
"""Record the SESSION-2 deviations in the append-only ledger (idempotent by `what`).

Session 1 ran 03:36-04:47 UTC on 2026-09-21 and ended with its container. Session 2 resumed
the same workspace at 07:10 UTC in a NEW container. Everything that changed between the two,
and every correction made before any result was scored, is written here so that
results/deviations.json -- and through it method_out.json -- carries it.

    uv run src/session2_deviations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import DEVIATIONS, setup_logging  # noqa: E402

ENTRIES = [
    ("session_restart",
     "session 1 ended at ~04:47 UTC; session 2 resumed the workspace at 07:10 UTC in a NEW container",
     "Session 1 had harvested Qwen3-4B, mlabonne/Qwen3-4B-abliterated and Qwen3-4B-Base, 12 weight "
     "summaries and 6 edit-recipe fingerprints; its Qwen3-4B-SafeRL harvest was at 192/256 prompts "
     "when the container ended and was redone from scratch. All session-1 caches were reused "
     "byte-for-byte (resumable by DONE / W_DONE sentinels). The new container is an AMD EPYC 9655 "
     "whose cpuset is the two hyperthreads of ONE physical core (host load ~200 on 192 threads), "
     "16 GB cgroup memory, no GPU. The run-shared HF cache was found EMPTY (re-created at 07:02 by "
     "the harness) and the workspace .venv was gone: every checkpoint was re-downloaded (~500 MB/s, "
     "28 repos in ~5 min) and the CPU environment rebuilt from pyproject.toml."),
    ("ci_method_corrected",
     "pair-delta and E2 confidence intervals re-derived from an ITEM-LEVEL BOOTSTRAP",
     "The session-1 code built the per-pair Delta CI as a normal interval with SE = "
     "sqrt(sd_p^2/n_null + sd_c^2/n_null) and the E2 CI with SE = pooled*sqrt(2/n_null): both "
     "divide the shuffled-label SD by the NUMBER OF NULL DRAWS, so the interval would shrink to zero "
     "as more null draws were taken. That is a statistical error, found and replaced BEFORE any "
     "result was scored: every label-dependent candidate now gets B item-bootstrap replicates "
     "(EASY items resampled with replacement, stratified by class, axis refit per replicate, folds "
     "split by original item so a duplicated prompt never straddles a fold; C-harvest readouts also "
     "resample cell items). Pair CIs use INDEPENDENT resampling per checkpoint (the registered "
     "reading); the PAIRED reading is reported as secondary."),
    ("bootstrap_B",
     "item bootstrap uses B=100 replicates, not the 2000 the plan names",
     "Each replicate refits the harm axis and recomputes every candidate, ~0.5-3 s on one "
     "contended core; 2000 x ~25 checkpoints was not affordable. Percentile CIs from 100 draws are "
     "coarse at the 2.5/97.5 tails; every CI in the output is labelled with its B."),
    ("w_summary_extremes_only",
     "session-2 weight summaries compute only the extreme eigenpairs",
     "Only sigma_min (= sqrt(lambda_min(MM^T))) and the near-null left singular vector are read by "
     "any statistic (X10, BL7, cos(vmin,u)). Session-2 W-summaries therefore use LAPACK dsyevr with "
     "a one-index subset for (lambda_min, vmin) and 60 power iterations for lambda_max, measured "
     "5.8x faster at d=2560 with identical lambda_min and |cos(vmin)|=1.0000 on a test Gram. "
     "Session-1 summaries keep their full spectra; svals then holds [sigma_max, sigma_min]."),
    ("prior_art_update",
     "X2 and X10 re-labelled CLOSED and excluded from survivor selection; X8 OPEN -> PARTIALLY_SCOOPED",
     "The same-iteration execution-side research lane (iter_2/gen_art/gen_art_research_1, "
     "2026-09-21) screened exactly these candidates and found 0 OPEN: the Jorak Model Scanner "
     "(github.com/JolanMc/Jorak; non-peer-reviewed, validated 4/4 on Qwen2.5-0.5B derivatives) "
     "ships X2's suppression statistic and X10's weights-only least-singular-vector test, and the "
     "readable-before-usable depth lag behind X8 is published three times off-concept. The plan "
     "says map silence means NOT-YET-CHECKED and to prefer the research verdict where it "
     "disagrees, so the stricter verdicts govern survivor eligibility. Both closed candidates are "
     "still computed; the incumbent statistic is added as baseline BL7_JORAK_A."),
    ("stratum_shortfall",
     "no edit-recipe stratum can reach the 4 EFFECTIVE pairs E1(a) requires",
     "The Phi-4-mini pair P5 fingerprints as B_PER_LAYER_RANK1 (like the commissioned P0), not "
     "A_GLOBAL_RANK1, so stratum A holds three EFFECTIVE pairs (P1, P2, P4), B holds P5 (+P0 if "
     "its judged label is EFFECTIVE) and C holds P3 plus the null-edit granite P6. E1(a) is "
     "therefore UNDER-POWERED by construction of the panel that exists, for every label-dependent "
     "candidate (fallback 7/8). The pooled-across-strata row is reported only as a labelled "
     "SECONDARY row and never enters the E1 verdict."),
    ("quanto_checkpoint",
     "venkycs/SmolLM2-1.7B-Instruct-Abliterated is an optimum-quanto FP8 upload with no quantization_config",
     "Its linear weights are stored as <key>._data (float8_e4m3fn) + a per-output-channel "
     "<key>._scale, and config.json declares float16 with quantization_config=None, so a plain "
     "transformers load cannot bind them. The weight-side summaries dequantise exactly "
     "(W = _data * _scale); the harvest records the load's missing/unexpected tensor counts. This "
     "is a fact about the hub supply: a checkpoint labelled 'abliterated' whose weights do not load "
     "is broken, not uncensored, which is consistent with its judged over-refusal of 1.000."),
    ("registered_drop",
     "the 4B random-init arm was dropped; the 0.6B random-init arm is kept",
     "Registered drop order (Section 12): '... -> the 4B random-init arm (keep the 0.6B one)'. "
     "Its forward passes cost as much as a real 4B checkpoint on one CPU core, and the 0.6B "
     "random-init arm already provides the untrained-representation control for every "
     "activation candidate plus (via an independent initialiser draw) for X10 and BL7."),
    ("c_harvest_restored",
     "the teacher-forced C-harvest (X5, X11) was RESTORED in session 2, with the registered per-tokenizer slot rule",
     "Session 1 dropped it on a slower box; its harvest.c_harvest also tested slot-in-window with the "
     "STORED Qwen token spans for every model and never dropped a failing cell, contrary to the "
     "registered rule. Session 2's src/c_harvest2.py re-tokenises each cell per model, maps the "
     "action slots from character offsets, drops cells whose slot misses either window (X5/X11 "
     "UNDEFINED above 20% drop), and feeds only prompt + 56 continuation tokens: every stored "
     "quantity reads positions < 56 and causal attention makes that EXACT (D_resp bit-identical to "
     "an untruncated pass; A_resp within 1.3e-4 relative, i.e. bf16 kernel rounding), a ~2.4x "
     "speed-up. All 8 tokenizer families keep 96/96 cells (0% drop)."),
    ("judge_extension_run",
     "the commissioned child mlabonne/Qwen3-4B-abliterated was judged with Lane C's exact protocol",
     "Same 45 harmful + 45 benign prompt ids/texts as Lane C's Qwen/Qwen3-4B row, same generation "
     "settings (greedy, max_new 140, batch 16, enable_thinking=False), same rubric and judges "
     "(google/gemini-2.5-flash-lite primary, openai/gpt-5-mini second on a 20% audit), same "
     "aggregation. Differences: CPU instead of GPU and a bf16 load of an F32 checkpoint. The parent's "
     "columns recomputed from Lane C's judged rows match s3_results.json exactly. Result: harmful "
     "compliance 0.733 vs 0.000, over-refusal 0.000 vs 0.444 -> EFFECTIVE (registered rule). "
     "Cost $0.0087; the CohenQu fine-tune was NOT judged (not needed by E2, which scores the "
     "candidate's ordering; ~21 min of CPU generation per 4B checkpoint)."),
    ("recognition_layer_selection_corrected",
     "R now uses the REGISTERED nested layer selection on the HARD set, not the session-1 EASY-set shortcut",
     "The plan (Section 5) chooses R's layer by inner-fold AUROC on the HARD set. Session-1 code "
     "chose it on the EASY fitting set instead, whose cross-fitted AUROC saturates at 1.0 over many "
     "layers, so the argmax took the FIRST saturated layer -- for huihui-ai/Huihui-Qwen3-0.6B-"
     "abliterated-v2 that was layer 4, a shallow lexical layer where the HARD contrast is not yet "
     "decodable, which manufactured a spurious recognition collapse (TPR@5%FPR 0.138 vs 0.588 at a "
     "proper layer). Found on a pilot before the final scoring and corrected: each of 5 outer folds "
     "picks its layer by cross-fitted AUROC on its own training portion only, fits the L2 probe there "
     "(C on inner folds), and scores the held-out portion; fold scores are standardised by the "
     "training portion's projection mean/SD before pooling so one low-FPR threshold applies. The "
     "EASY-layer value is kept in the output as a labelled secondary, never as R."),
    ("time_gate_tail_dropped",
     "prompt sweep stopped after the E3 family singles; C-harvest restricted to the checkpoints the registered tests need",
     "At 08:20 the measured pace (granite-3.2-2b alone took 8 min under host load ~220: its and "
     "SmolLM3's chat templates prepend long system headers) projected the full queue plus the "
     "C-harvest past a safe margin. Registered drop order applied: the Qwen3-4B-Base "
     "plain-completion re-run (the chat-template Base run is kept; iteration-1 Lane A already "
     "reported both protocols) and four extra base singles (Qwen3-0.6B-Base, Qwen3-1.7B-Base, "
     "Qwen2.5-1.5B, SmolLM2-1.7B; their weight summaries are kept, so X10/BL7 still cover them) "
     "were not activation-harvested; the C-harvest (X5, X11) covers the E2 arms, every pair member "
     "P0-P6 and the random-init arm, and SKIPS the anomalous controls S1/S2, TinyLlama and OLMo-2 "
     "(marked C_SKIPPED), for which X5/X11 are reported as not harvested."),
    ("github_file_size_split",
     "the per-position C-harvest tensors are stored as numbered parts below GitHub's 100 MiB limit",
     "harvest/<tag>/D_resp.npy (120-290 MB for the 1.5B-4B checkpoints) was split along the cell "
     "axis into harvest/<tag>/D_resp_parts/D_resp_part_NNN.npy (<= 90 MiB each) + index.json by "
     "src/split_large_arrays.py, which verified every reassembled array BIT-IDENTICAL to the "
     "original before deleting it (results/split_report.json). Readers (CkptCache.arr, confirm) and "
     "writers (c_harvest2, harvest) now go through aii_common.load_npy_maybe_split / "
     "save_npy_split. Regression check: X5, X11 and X5 concentrations recomputed from the parts "
     "equal the values scored from the original files exactly, and e_tests.json, pairs_table.json "
     "and budget_pair_deltas.json are byte-identical before and after the split; T7 PASS."),
    ("sweep_paused_for_judge",
     "the harvest sweep was paused between checkpoints while the judge extension ran",
     "Generating 90 responses with mlabonne/Qwen3-4B-abliterated needs ~9 GB resident; beside a "
     "3-4B harvest model that exceeds the 16 GB cgroup. The sweep was stopped right after "
     "Qwen3-1.7B finished and resumed after the judge job, so no checkpoint was lost or redone."),
]


def main() -> int:
    setup_logging("session2_deviations")
    DEVIATIONS.load()
    have = {d.get("what") for d in DEVIATIONS.items}
    n = 0
    for kind, what, detail in ENTRIES:
        if what in have:
            continue
        DEVIATIONS.add(kind, what, detail)
        n += 1
    print(f"added {n} session-2 deviation(s); ledger now {len(DEVIATIONS.items)} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
