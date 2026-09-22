# TODO (copied verbatim from the task prompt) -- session 4 (resumed 18:25 UTC after pod restart; GPU pod: NVIDIA L4)

- [x] TODO 1. Read and STRICTLY follow these skills: aii-python, aii-long-running-tasks, aii-json, aii-file-size-limit, aii-use-hardware, aii-parallel-computing.
- [x] TODO 2. Read preview files from dependencies to understand data structure. Use ALL datasets provided — do not skip or select a subset. Read domain handbook if applicable (see <available_domain_handbooks>). Test basic functionality with 'uv run'.
- [x] TODO 3. Fully implement our method AND baseline (comparison) as described in artifact plan in './method.py'. Use exp_gen_sol_out.json schema in aii-json skill for output format validation. Include everything specified in the artifact plan, but you may also implement additional relevant methods or analysis beyond what's listed. Be very attentive to meticulously and exhaustively fix any errors in your code.

## Session-4 state
- GPU venv: .venv_gpu (torch 2.9.1+cu128, transformers 5.17.0). CPU venv .venv (analysis).
- Engine ported to CUDA (src/engine.py), S-position hooks, all arms at decode sites; hook hash 6e406f7f.
- prereg_gpu_addendum.json frozen 18:39 UTC (sha 524c15c0...) BEFORE any 4B outcome.
- GPU smoke (Qwen3-0.6B) PASSED hook checks a1/a2/b/c + site checks (18:45).
- Main run: `.venv_gpu/bin/python method.py --models instruct,saferl --stages unit,twins,decod,arm0,grid1,gen,genP,genDprime,genE,arc,grid2,grid3,stimro,decodgen,spanD,spanE --deadline-min 200 --kv-gb 2.5` -> logs/main_gpu.out, PID in logs/main_gpu.pid. Re-running the same command skips finished cells.
- Analysis subagent writing src/analyze.py (+ main, method_out) and src/figures.py per .aii/analysis_brief.md.
- [x] abliterated: `--models abliterated --stages unit,twins,decod,arm0,grid1,genP,arc,stimro` (after main)
- [x] gsm on CAUSAL cells: `--models instruct,saferl --stages gsm --gsm-cells P:B3,...`
- [x] analyze -> method_out.json (validate), figures, README.md, .aii/manifest.yaml, pyproject.toml/uv.lock
- [x] cleanup: delete out/private, hf_cache/ (confirm-panel leftovers), .venv_ams? (manifest: delete regenerable)

## Session-4 completion (21:25 UTC)
- All GPU stages done (main 2 models, genG, abliterated, genU+e2x2, gsm); final analysis + figures + method_out (schema PASSED); README complete; out/private deleted after hygiene grep (0 hits); judge cost $0.764.
