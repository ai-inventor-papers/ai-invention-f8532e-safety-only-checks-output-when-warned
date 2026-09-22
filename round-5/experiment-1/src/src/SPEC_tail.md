# SPEC — pipeline tail: S2.6 assemble → S3 pre-screen/rank → S4 freeze → S5 join → S6 outputs

Authoritative rules: `results/prereg.json` (`f_selection_rule_verbatim`, `g_mde`, `h_deadline_rule`,
`d_candidates`). The PREREG wins on any disagreement. All chained files live DIRECTLY in `results/`
(core.verify_chain resolves `results/<name>`). Hash = sha256 of `core.canonical_json(obj)`; append
with `core.chain_append(results/hashchain.jsonl, stage, path, digest)`.

## S2.6 `src/assemble_screen.py`
Inputs: `results/panel.json`, `results/screen/tierA/*.json`, `results/screen/ckpt_*.json`.
- The 15 REGISTERED candidate scalars: W1..W8 (W7 = intervention; if a row's W7 is NOT_RUN, W7c
  carries the slot for that row, flagged `W7_is_W7c`), G1..G4, A1 (= A1_joint: PC1 of z-scored
  (A1_prior, A1_slope) across SCREEN-panel rows with both finite; loading vector stored and reused
  unchanged later; oriented so the A1_prior loading > 0; if A1_prior is missing everywhere, A1 =
  A1_slope, flagged), A2, A3. Sub-columns (reported, never registered): A1_prior, A1_slope, W7c,
  W7c_tok1, G4_ratio, A2_cos, A2_mag, A3_sd, W2_raw.
- `results/screen_table.json` = {"panel":[tags], "blocks":{"quartet":[...],"control":[...]},
  "rows":[{tag, candidate, value, tier, censored, flags, band, n_prompts, k_curve, stability}...],
  "bars":[{tag, bar, value, meta}...], "subcolumns":[...], "a1_joint_loading":{...},
  "coverage":{candidate:{n_panel_finite, n_tierB_missing, reasons}}}. k-curve points not computed are
  the STRING "N/A" (never 0). Hash it → chain stage `S2`.

## S3 `src/prescreen.py` — its OWN process; INV-3 proven by an open() audit
- First statement of main(): install `core.OpenAudit(logs/s3_open_audit.txt, forbidden=
  ["graded_truth","classification","aggregates","panel_manifest","gen_art_experiment_2",
  "judge","truth","sealed","heldout"])`. HARDEN the shim before relying on it: it must also patch
  `io.open` and `os.open` (pathlib and numpy bypass `builtins.open` otherwise) and be exercised by a
  test that plants `Path(...graded_truth.json).read_text()`, `np.load` and `open()` reads → each must
  raise and be logged (`results/s3_audit_selftest.json`). Only inputs: prereg.json, screen_table.json.
- S3.2: for each registered candidate: Spearman ρ with BL1_easy over panel rows with both finite;
  checkpoint-bootstrap 95% CI (B=2000, seed 20260922); DROPPED iff |ρ| ≥ 0.50 (point estimate).
  Censored cells: carried at the panel 95th percentile of the uncensored values (W2 keeps 7), AND
  ρ recomputed with censored rows dropped (both printed). Also print sub-columns' ρ (information
  only), n, MDE(n) = tanh(2.80/sqrt(n−3)), EXPECTED sign (from prereg) — no outcome sign exists yet.
  `results/prescreen.json` {candidates:{c:{rho, ci, n, mde, status, rho_censored_dropped, tier,
  stable_flags}}, n_dropped, n_kept, n_not_evaluable}. Chain stage `S3a`.
- S3.3 effective rank: M = registered candidates × panel checkpoints, z-scored per candidate,
  NaN → 0 after z-scoring (mean imputation; count reported); SVD; p_i = s_i²/Σs²;
  erank_entropy = exp(−Σ p log p); erank_participation = (Σs²)²/Σs⁴. Repeat with every candidate
  row replaced by its OLS residual on z(BL1_easy) across checkpoints. Report leading left singular
  vector (candidate loadings), |cos(u1_ckpt, z(BL1_easy))| for the leading right singular vector,
  the 15×15 Spearman matrix, and the same analysis restricted to Tier-A candidates (full panel) and
  to rows with complete Tier-B coverage. `results/rank_analysis.json`, chain stage `S3b`.
  Verdict text: if erank_entropy ≲ 1.5 AND |cos| ≥ 0.8 → "P1-consistent: one coordinate, BL1-aligned".

## S4 `src/freeze.py`
- `results/survivor.json` = {"utc", "survivors":[{candidate, rank, rho_BL1_easy, tier, band_rule,
  site, expected_sign:{OR,HC}, scoring_ref:"src/<module>.py::<function> + prereg d_candidates.<c>",
  n_prompts, flags}], ...} ranked by |ρ_BL1_easy| ascending, ties → fewer prompts, then Tier A
  before Tier B — or {"survivors":"NONE"}. Write `results/survivor.sha256`, chain stage `S4`.
- Verify the whole chain (`core.verify_chain(..., expected_order=["S1","S2","S3a","S3b","S4"])`):
  digests, stage order, monotone UTC AND monotone mtimes; assert `logs/s3_open_audit.txt` contains
  no forbidden substring; write `results/order_proof.json`.
- Refuse to run if any chained file changed or prescreen/rank are missing.

## S5 `src/join.py` (runs only if survivor.sha256 exists and verifies)
1. `glob('/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/*/results/panel_manifest.json')`
   excluding this workspace; union checkpoints across matches, dedupe by repo id. Record every file
   opened after the freeze in `logs/s5_open_log.txt`. Inspect the manifest schema first and write
   `results/confirm/manifest_schema.json`; adapt loaders to it (graded truth per checkpoint: HC / OR
   with the benign set NAMED; arrays per checkpoint if in the iteration-4 27-file schema).
2. Assert the confirmation ∩ screen-panel intersection (by repo id / weight fingerprint) is EMPTY
   (print it). Assert the OR column is non-degenerate (else CONFIRMATION = UNINFORMATIVE).
3. Score the FROZEN survivors (and, for reporting only, every candidate and bar) on each landed
   checkpoint with THIS artifact's code: Tier A from 27-file-schema arrays when present, otherwise from
   our own capture; Tier B via `src/tierB.py` external-checkpoint mode. BL1_easy and AMS computed on
   the SAME checkpoints (pairing assertion). NO re-screening, NO subgroup search.
4. Selection rule (ii)-(vii) exactly as frozen; McNemar 15-pair AND 12-pair (daggers on degenerate
   cells: 3 wu05 head-only edits, 2 system-prompt arms); sensitivity x/9 legacy + fresh with
   AMD-OLMo base→SFT named; prompt-bootstrap deltas from `results/screen/pair_boot_tierA.json` and
   Tier-B per-item npz; MDE printed on every ρ line; tiers SURVIVES / STRONG.
5. If < 8 checkpoints landed: label PARTIAL (n, MDE) and ALSO run the S5.4 fallback (disclosed
   upstream sealed families, NOT blind).
Outputs `results/confirmation.json` (+ chain stage `S5`).

## S6 `method.py` (workspace root) → `method_out.json` (exp_gen_sol_out schema)
`{"metadata": {...every section listed in plan S6.1 + S6.2 disclosures...}, "datasets":[...]}`
Datasets (each example: `input` = JSON string describing the row, `output` = the observed/target
string, `metadata_*` fields, `predict_*` STRINGS for candidate values and bars):
`screen_table` (checkpoint × candidate), `prescreen`, `rank_analysis`, `confirmation`
(per confirmation checkpoint: output = observed over-refusal, predict_<survivor>, predict_BL1_easy,
predict_AMS_T1 ...), `commissioned_quartet`, `stability`, `patching_validation`, `transfer_check`,
`norm_displacement`, `pair_audits` (false alarms / sensitivity). Verdict: SURVIVOR(s) with tier, or
"P1_WINS: THE BOUND". Validate with the aii-json skill (`--format exp_gen_sol_out`), then generate
mini/preview variants.
