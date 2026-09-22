# Phase-2 TODO (verbatim)
1. For the top 15 datasets, create data.py (uv inline script) that: loads from temp/datasets/, standardizes to
   exp_sel_data_out.json schema (aii-json skill), extracts all examples per dataset, handles domain requirements,
   saves to full_data_out.json. Each data ROW = one example, GROUPED BY DATASET. Required per example: input, output.
   Optional flat metadata_<name> fields. Do NOT use split/dataset/context as per-example fields.
2. Run 'uv run data.py' and fix errors. Validate full_data_out.json against exp_sel_data_out.json schema (aii-json)
   — fix errors. Generate preview, mini, full versions with aii-json skill's format script.
3. Read preview to inspect examples. Choose THE BEST 10 DATASETS based on domain requirements and artifact
   objective. Be very attentive to meticulously and exhaustively fix any errors in your code.

## Final status
1. [DONE] data.py written (stdlib only, runs via `uv run --no-project data.py`; a local pyproject.toml was added
   because `uv run` otherwise resolves the parent repo's broken workspace). 15 candidates standardized to
   exp_sel_data_out, one SOURCE ROW per example, grouped by dataset.
2. [DONE] Ran and fixed. Two real bugs found and fixed during inspection: (a) the harm-domain keyword table never
   matched a vocabulary word appearing literally in a category label ("Illegal goods and services" -> null), fixed
   with a literal-label check that takes precedence; (b) cyber-exploit rows fell through to "unethical", fixed by
   adding vulnerabilit/malware/ransomware/ddos/botnet/keylogger to the illegal tuple. Schema validation PASSED on
   full/mini; full/mini/preview variants generated. 4.5 MB, under the size limit, no split needed.
3. [DONE] Preview inspected row by row. Best 10 chosen and justified in full_data_out.json -> metadata.selection;
   the 5 discarded each carry a written reason (redundancy, schema fit, unverified licence, or CC-BY-NC).
   Final: 10 datasets / 7,604 examples. All 15 retained at results/full_data_out_all15.json.
