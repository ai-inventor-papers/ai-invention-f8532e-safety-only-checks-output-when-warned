# ASSET MAP — verified on disk 2026-09-22, copied into `WS/assets/`

Source: `iter_4/gen_art/gen_art_experiment_1/assets/` (H1). SHA-256 of each copy is in
`results/asset_hashes.json`. These are the frozen stimulus substrates that define the
harvest array shapes. **Use these, do not rebuild them.**

| WS/assets file | container | n | feeds harvest array | array shape |
|---|---|---|---|---|
| `stimuli.json` | `["rows"]` | 256 | `A_prompt.npy`, `A_prompt_p1/p2/p3.npy`, `r_*.npy` | (256, L+1, d) f16 / (256, L+1) f32 |
| `cells.json` | `["cells"]` | 96 | `A_ams.npy` | (96, L+1, d) f16 |
| `c11_items.json` | `["items"]` | 64 | `A_c11.npy` | (64, L+1, d) f16 |
| `behaviour_items.json` | `["items"]` | 168 | `A_dec.npy`, `A_dec_tok1.npy`, `dec_ntok.npy` | (160, L+1, d) f16 / (160,) i32 |
| `token_sets.json` | `["refusal"]=56 `, `["hedge"]=18`, `["control"]=56` | — | `WU_ref/WU_hed/WU_ctl.npy` | (n_kept, d) f32 |
| `side_sets.json` | see below | — | Part-B arms | — |
| `ams_spec.json` | code-pinned AMS protocol | — | `A_ams` / AMS instrument | — |
| `pairs.json` | iteration-4 pair registry | — | reference only | — |

## Details that matter

- **`stimuli.json.rows[i]`** = `{text, y, set_id, source, ...}`; `y=1` harmful, `y=0` benign.
  `meta`: n_total 256, n_easy 96, n_hard 160, n_benign_hard 80, n_xstest_twin_pairs 40.
  `easy` FITS every direction (standard abliteration recipe); `hard` MEASURES and must
  never be used to choose a layer or a strength.
- **`behaviour_items.json`** is authoritative for the behavioural item ids:
  `n_items 168`, `n_harm 85`, `n_benign 83`, `n_xs 80`, `n_laneC 88`, and carries
  `item_id_list_sha256`. Rows look like
  `{item_id: "sr_38", set: "harm", subset: "laneC", harmful: 1, prompt: "..."}`.
  This is the SAME 85/83 split that `H1/results/graded_truth.json` grades, so it is the
  join key for `item_sets.json`. `A_dec` uses a 160-row subset of these 168.
- **`token_sets.json`** holds 56 refusal / 18 hedge / 56 control surface forms
  (leading-space variants included). Its `meta.note` states ids are **resolved PER
  TOKENIZER at harvest time**, which is why `H1/harvest/F1__ref/` shows
  WU_ref 44 / WU_hed 16 / WU_ctl 56 for Qwen3-0.6B rather than 56/18/56.
  **Keep the true per-checkpoint kept-count and record it in `meta.json`. Never pad.**
- **`side_sets.json.sizes`** = `{lesion_fit: {harm 64, benign 64}, lesion_val: {harm 16,
  benign 16}, hbar_32: 32, sanity_32: 32, lora_rows: 782, dpo_rows: 0}`.
  `lora_rows` (782, from databricks/dolly-15k, 5 non-safety categories) are ready to use
  for the Part-B LoRA arm. **`dpo_rows` is 0 — the DPO preference pairs must be BUILT**
  from the same dolly rows (chosen = reference answer, rejected = truncated/shuffled).
  `lesion_fit` / `lesion_val` are the iteration-2 recognition-set splits that the in-house
  rank-one lesion arms (a10/a05) fit and validate on.

## Hardware correction to the artifact plan
The plan assumes an **L4 with 23,034 MiB**. The real device is an **NVIDIA RTX 2000 Ada
with 16,380 MiB**, currently idle. Keep the declared 7.5 GB budget
(`set_per_process_memory_fraction(7500/16380)`), but the lease ceiling and any
`max_memory` offload figures must be computed against 16,380 MiB, not 23,034.
