# Phase-3 TODO (verbatim)
1. Update data.py to only include the chosen 10 datasets and generate full_data_out.json. Re-run to generate
   full_data_out.json. Validate output format with aii-json skill and fix any errors. Generate full, mini, and
   preview versions with aii-json skill's format script using `--input full_data_out.json` (creates
   full_full_data_out.json, mini_full_data_out.json, preview_full_data_out.json — rename to full_data_out.json,
   mini_data_out.json, preview_data_out.json).
2. Verify full_data_out.json, preview_data_out.json, and mini_data_out.json exist in your workspace and contain
   correct data.
3. Apply aii-file-size-limit skill's file size check procedure (100MB limit) to full_data_out.json.
4. Ensure a pyproject.toml exists with ALL dependencies pinned to the exact versions installed in .venv.
