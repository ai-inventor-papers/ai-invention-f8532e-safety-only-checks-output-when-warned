# Task todos (copied verbatim from the task prompt)

TODO 1. Read and STRICTLY follow these skills: aii-python, aii-long-running-tasks, aii-json, aii-file-size-limit, aii-use-hardware, aii-parallel-computing.
TODO 2. Read preview files from dependencies to understand data structure. Use ALL datasets provided — do not skip or select a subset. Read domain handbook if applicable (see <available_domain_handbooks>). Test basic functionality with 'uv run'.
TODO 3. Fully implement our method AND baseline (comparison) as described in artifact plan in './method.py'. Use exp_gen_sol_out.json schema in aii-json skill for output format validation. Include everything specified in the artifact plan, but you may also implement additional relevant methods or analysis beyond what's listed. Be very attentive to meticulously and exhaustively fix any errors in your code.

# Session-2 working list (resumed 2026-09-21 07:10 on a NEW container)

Facts: EPYC 9655, cpuset = 2 hyperthreads of ONE core, no GPU, 16 GB cgroup, run-shared HF cache found
EMPTY (re-created 07:02) -> all checkpoints re-fetched at ~500 MB/s; .venv absent -> rebuilt (CPU torch).
bf16 GEMM 245 GFLOPS -> a 4B P-harvest takes ~4-5 min here (8-20 min on the session-1 box).

- [x] rebuild venv; re-fetch 28 repos; relaunch supervised P-harvest sweep
- [x] fix: Deviations.add overwrote the ledger (no reload)            -> read-modify-write
- [x] fix: jdump crashed on Python-float NaN inside lists              -> recursive sanitiser
- [x] fix: pair-delta CI and E2 CI used null_sd/sqrt(n_null)            -> item bootstrap (B=100)
- [x] fix: weightfp OOM on 200k-vocab embed diff                        -> row-chunked
- [x] W-summaries: 29 checkpoints (extremes-only eigensolver, 5.8x) + random-init arm
- [x] fingerprints P5 (B_PER_LAYER_RANK1), S1 (C); S2 retry queued (quanto dequantisation)
- [x] judge extension: mlabonne HC 0.733 vs 0.000 -> EFFECTIVE ($0.0087)
- [x] C-harvest v2 built+verified (100% slot_ok, exact causal truncation); queued after P-sweep
- [x] score X5/X11 in score_ckpt + nulls + bootstrap over cell items
- [x] prior-art: Jorak closes X2+X10 (excluded from survivor); X8 PARTIAL; BL7_JORAK_A added
- [x] make_outputs: hardware, deviations, X5 status, MDE pooled-SD, lineage table, budget pairs, E1 status
- [x] full analyze (nulls 20, boot 100, budget k=0..128) -> confirm (survivor NONE frozen) -> outputs
- [x] method_out.json schema PASSED (+full/mini/preview, 335 examples); README; manifest; memory note
- [x] score watcher -> finish2.sh (T7 PASS, T5 6/6) -> emit.sh -> README/manifest

TODO 1-3 (task): DONE. Session 2 closed 10:25 UTC.

# Finalization todos (copied verbatim from the finalization prompt)
TODO 1. Use aii-json skill's format script with `--input method_out.json` to generate full, mini, and preview versions. If not in your workspace (see <workspace> above), copy them there. Run 'ls -lh' to verify these three files exist (DO NOT read them).
TODO 2. Apply aii-file-size-limit skill's file size check procedure (100MB limit) to method_out.json and full_method_out.json.
TODO 3. Ensure a `pyproject.toml` exists in your workspace with ALL dependencies pinned to the exact versions installed in your .venv (run `.venv/bin/pip freeze` to get them). This is required for reproducibility. The [project] section must include name, version, requires-python, and a dependencies list with pinned versions (e.g. `numpy==2.0.2`, not `numpy>=2.0`).
