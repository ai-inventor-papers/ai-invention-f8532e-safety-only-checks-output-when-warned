# REQUIRED TODOS (copied verbatim from the task prompt)

- [ ] TODO 1. Use aii-json skill's format script with `--input method_out.json` to generate full, mini, and preview versions. If not in your workspace (see <workspace> above), copy them there. Run 'ls -lh' to verify these three files exist (DO NOT read them).
- [ ] TODO 2. Apply aii-file-size-limit skill's file size check procedure (100MB limit) to method_out.json and full_method_out.json.
- [ ] TODO 3. Ensure a `pyproject.toml` exists in your workspace with ALL dependencies pinned to the exact versions installed in your .venv (run `.venv/bin/pip freeze` to get them). This is required for reproducibility. The [project] section must include name, version, requires-python, and a dependencies list with pinned versions (e.g. `numpy==2.0.2`, not `numpy>=2.0`).
- [ ] FINAL. Write ./.terminal_claude_agent_struct_out.json (title, layman_summary, summary, out_expected_files, upload_ignore_regexes).


## STATUS (proven on a partial method_out.json; all three re-run at the end by ./finalize.sh)
- TODO 1 DONE-mechanism: aii_json_format_mini_preview.py --input method_out.json ->
  full_method_out.json / mini_method_out.json / preview_method_out.json. `ls -lh` verified,
  and all four validate against exp_gen_sol_out.
- TODO 2 DONE-mechanism: sizes 908K / 25K / 14K, i.e. <<100MB, so no split is needed.
  finalize.sh re-checks both method_out.json and full_method_out.json with `stat -c%s`.
- TODO 3 DONE: pyproject.toml has 71 dependencies, ALL pinned with == from
  `uv pip freeze` (the venv was made by `uv venv`, which installs no pip, so plain
  `pip freeze` returns nothing - that is the trap here).


## FILE-SIZE FIX (out/harvest/*.npz exceeded the 100MB deployment limit)
STRATEGY 1 (split), implemented in code and tested, not a one-off shell hack:
- `common.save_sharded(stem, arrays)` packs keys greedily by nbytes into
  `{stem}.partNNN.npz`, each < 90MB. `common.ShardedNpz(stem)` reads the parts back
  through the same `z[key]` / `z.files` API and ALSO falls back to a single
  `{stem}.npz` when one exists, so old and new harvests both load.
- `run_lineage.save_state` now calls save_sharded; `readouts.State` now uses ShardedNpz.
  Those two are the only writer/reader of the big per-(lineage, alpha) files; every other
  `np.load` in src/ targets a ~350KB `*_dirs.npz`.
- `src/shard_harvest.py` converts any already-written oversized file. It VERIFIES the
  round-trip key-by-key with np.array_equal and asserts every part is under the limit
  BEFORE unlinking the original, and it skips a lineage that is still harvesting.
- TESTED: after conversion, `analyze.analyse_lineage("L2")` reproduces the pre-shard
  numbers EXACTLY (G1 0.1594; gap curve [1.0, 0.7444, 0.4822, 0.2282, 0.0002];
  |CB|z 25.51->25.38; |A|z 11.95->9.43) and `redundancy.py` likewise.
- PATHLIB TRAP worth knowing: `Path("L2_a0.00").suffix` is `".00"`, so `with_suffix(".npz")`
  yields `L2_a0.npz`. The fallback uses `Path(str(stem) + ".npz")` instead. Both branches
  have a unit test.
- The shard step is wired into ./finalize.sh and `method.py --stage shard`, so the
  end state is compliant no matter which lineages ran.
- out/harvest stays in upload_ignore_regexes anyway: it is ~5GB of regenerable activation
  cache, reproducible with `method.py --stage harvest`. The real deliverables (results.json,
  method_out.json and variants, released direction vectors) are small and published.

## MODULE-END FILE CHECK
- `.aii/manifest.yaml`: 4 delete entries (out/harvest/ 7.5GB, .venv/ 5.3GB, src/__pycache__/,
  tests/__pycache__/ — all `regenerable`, each with a working `source:`) and 4 keep entries
  (out/released_directions/, out/substrate.json, data/, logs/) with one-line reasons.
- `README.md`: reads as a repo README — what was done, headline results, a line per important
  file/dir, how to run, and a "Restoring removed files" section carrying the command for
  EVERY delete entry.
- VERIFIED: nothing outside the manifest entries exceeds 10MB (54 uncovered files, 8.2MB
  total), and every delete entry's path appears in the README restore section.
- Also fixed a real bug the sharding introduced: redundancy.py tested for
  `{tag}_a{alpha}.npz`, which no longer exists after sharding, so it SILENTLY skipped every
  state and wrote only depth profiles. Now uses `state_exists()` (parts OR legacy single
  file). Re-ran: all 8 per-state entries recovered.
