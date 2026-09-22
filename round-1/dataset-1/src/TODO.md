# Artifact TODO (verbatim from prompt) — final status

1. Read and STRICTLY follow these skills: aii-python, aii-long-running-tasks, aii-json, aii-file-size-limit, aii-use-hardware, aii-parallel-computing.
   [DONE] All six read before any code was written. uv-only env, loguru stdout+file sinks, pathlib, type hints,
   @logger.catch(reraise=True), asyncio+bounded Semaphore for every API sweep, staged scale-up, size check on output.

2. Read skill files for data sources + domain handbook. Run 50 diverse searches across chosen source(s).
   [DONE] aii-hf-datasets used as the primary source; aii-web-tools for provenance. Exactly 50 diverse HuggingFace
   searches run in parallel (GNU parallel -j 10), 287 unique repos surfaced. Raw output: research/hf_search_raw.txt.

3. Identify the 25 most promising datasets (<300MB). Preview/inspect sample rows for each.
   [DONE] 26 previewed by streaming (25 kept + 1 discarded on a verified size check: ToxicityPrompts/PolyGuardMix is
   really 2.3 GB despite its size_categories tag, replaced by PolyGuardPrompts at 52.9 MB).
   Raw output: research/hf_preview_raw.txt.

4. Research each candidate BEFORE downloading (web search: name, papers, provenance, popularity).
   [DONE] 25 parallel provenance checks. Peer-reviewed provenance found for most; 3-4 flagged "unverified" rather than
   given an invented justification. Raw output: research/web_research_raw.txt; table: research/dataset_candidates.md/.json.

5. Decide KEEP vs DISCARD; download 15 to temp/datasets/.
   [DONE] 25 KEEP / 1 DISCARD. 19 source entries actually downloaded into temp/datasets/ (127.1 MB total, under the
   200 MB budget), recorded in sources_manifest.json with revision, row count, license and SHA-256 each.
   2 were genuinely gated (walledai/HarmBench, allenai/wildguardmix) and were skipped, not substituted silently.
   bench-llm/or-bench config or-bench-80k was never ingested, as required.
