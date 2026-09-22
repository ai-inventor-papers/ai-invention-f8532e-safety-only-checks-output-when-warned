# SPEC — Tier A array-only screen (`src/tierA.py`)

Authoritative definitions: `results/prereg.json` (`d_candidates`, `c_fold_rule_and_prompts`,
`stability_C`, `transfer_I`, `a_panel_inclusion_rule`). This file adds implementation detail only;
the PREREG wins on any disagreement. NO outcome file (graded_truth / classification / aggregates /
any iter_5 sibling file) is opened by Tier A code — ever.

## Inputs (read-only)
- `I4/harvest/<tag>/`: A_prompt (256,L+1,d) f16 in `I4/assets/stimuli.json` row order; A_c11 (64);
  A_dec, A_dec_tok1 (160 = HARD rows in stimuli order); WU_ref (44,d); gamma (d,); meta.json.
- `results/items/twin_pairs.json`, `results/items/hard_domains.json`, `I4/assets/c11_items.json`.
- Commissioned quartet + controls: iteration-2 harvest dirs (see `src/ASSETS.md` for schema/order).
- Bars: `src/bars.py::compute_bars(tag_dir)`.

## Per checkpoint (one tag at a time; load only needed rows as float32; del + gc after)
Registered draw (prompt_draw 0, fold_seed 0, band offset 0):
- For each fold f ∈ {A,B} as FIT fold (the other = scoring fold): F_b, N6_b for b=1..6; b*_read.
- G1, G2 (+CENSORED_HIGH guard), G3 (raw-residual top index rule), G4 (+G4_ratio), A1_slope
  (A_c11, severity 0..3, / (mean_H − mean_P) on the scoring fold), A3 (+A3_sd, per-domain g, guard;
  S32 fit-fold items excluded from the domain sets), W7c and W7c_tok1 (A_dec / A_dec_tok1 at B6 on
  r_late; items in the fit fold excluded), plain_DiM (Cohen's d of <X[b*_read],F> H vs P, scoring fold).
  Registered value = mean over the two fit/score assignments. Also store per-fold values, b*s and the
  6-band curve of every candidate (candidate evaluated at each b instead of b*).
- Degenerate numerics → NaN + flag, never 0.

Extras (all cheap, all per prereg):
- k-curve: k ∈ {4,8,16,32} using `k_curve_subsets` (k=4/8 in-sample, flagged) + `"pool"` = all 40
  twin pairs + 48 dolly with the same hash-alternating fold rule (salt SALT+'|pool'). k=0: N/A.
- Stability: STAB18 rows → 18 draws (prompt_draw × fold_seed × band_offset ±1); others → 4 draws.
  Store every draw's values; compute per-candidate sign-stability and rank-stability per prereg.
- Shuffled-label band: 50 permutations (seed from sha256(SALT|tag|perm)) of the class labels among
  the S32 items that define the candidate's contrast (H∪P for F-based, H∪Bn for N6-based, all three
  for G2); store [2.5, 97.5] percentiles and whether the registered value is outside.
- Transfer (field norm I): G2 on A_c11 with H=sev3, Bn=sev1, P=sev0 (fold split by
  sha256(SALT|c11|c11_id) alternating within severity).
- Prompt bootstrap for structural pairs (needed after the freeze for false alarms / sensitivity):
  pair structure from `I4/assets/pairs.json` (STRUCTURE ONLY, no outcomes): for every
  (parent, child) with both tags in the panel, B=200 resamples of items WITHIN fold and class (same
  indices for parent and child) → delta = child − parent for every Tier-A candidate and every bar
  that bars.py can recompute from resampled rows (at least plain_DiM; others NaN) → store the
  delta's 2.5/97.5 percentiles + point delta in `results/screen/pair_boot_tierA.json`.
- Bars: `compute_bars(tag_dir)` → stored under `bars`.

## Panel (S2.1, run before any score)
`src/panel.py` applies prereg rule (a) mechanically using `results/items/gt_tag_counts.json` (counts
only) → `results/panel.json` {included:[...], excluded:[{tag, reason}], expected, achieved, flags}.
Quartet/controls listed separately under `blocks`.

## Commissioned quartet (its own section)
For Qwen3-4B Base / instruct / SafeRL / mlabonne-abliterated + CohenQu STaR (+ RandInit control):
every Tier-A candidate and bar computable from their arrays, plus the four-way geometry table:
per band b, |cos| of F_b and N6_b between arms (instruct–SafeRL, instruct–abliterated,
Base–instruct, instruct–STaR, Base–STaR), ‖mean_H − mean_P‖ and ‖mean_H − mean_Bn‖ magnitudes
(raw and divided by mean residual norm) → `results/screen/quartet_tierA.json`.

## Output
`results/screen/tierA/<tag>.json`:
```
{"tag","group":"panel|quartet|control","repo","n_layers","hidden","params",
 "registered":{"G1","G2","G3","G4","G4_ratio","A1_slope","A3","A3_sd","W7c","W7c_tok1","plain_DiM"},
 "censored":{"G2":bool,"A3":bool}, "flags":{cand:[...]}, "bstar_read":{"A":b,"B":b},
 "per_fold":{...}, "band_curves":{cand:[6]}, "k_curve":{cand:{"4","8","16","32","pool"}},
 "stability":{"draws":[{"prompt_draw","fold_seed","band_offset","values":{...}}],
              "summary":{cand:{"sign_agree_frac","n_draws"}}},
 "shuffled_band":{cand:{"lo","hi","outside":bool}}, "transfer":{"G2_c11"},
 "A3_domains":{dom:{"g","n_harm","n_benign"}}, "bars":{...}, "utc"}
```
CLI: `python src/tierA.py --all` (panel + quartet + controls), `--tags ...`; resumable (skip
existing unless `--force`); runtime log per tag; RSS < 6 GB (read `/sys/fs/cgroup/memory/...` is not
needed — use psutil RSS of the process).
