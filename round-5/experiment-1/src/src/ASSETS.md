# Asset recon (P0.3) — answers to Q1-Q8

All paths relative to `R = .../run_YqmEFECOIR3D/3_invention_loop`. I4 = `iter_4/gen_art/gen_art_experiment_1`.

## Q1 — row order & hidden-state index convention
`I4/src/harvest_variants.py:harvest_arm` builds `texts=[render_fn(s["text"]) for s in S]` with `S=stimuli` (256 rows,
`I4/assets/stimuli.json["rows"]`, byte-identical sha256 to `iter_2/.../assets/stimuli.json`) — so **A_prompt /
A_prompt_p1/p2/p3 rows == stimuli.json row order**, 1:1, no reorder (line ~254-259).
`hard_idx = [i for i,s in enumerate(S) if int(s["set_id"])==1]` (line ~294) then `dec_harvest(..., [texts[i] for i in
hard_idx], ...)` → **A_dec/A_dec_tok1 rows == the 160 HARD (set_id=1) rows in stimuli.json order** (meta.json
`dec.rows = "HARD stimuli in stimuli.json order"`).
`A_c11` rows == `c11[:smoke_limit] if ... else c11]` == `I4/assets/c11_items.json["items"]` order verbatim (no sort).
`A_ams` (96 rows) = `ams_reimpl.ams_prompts()`: **3 concepts (harmful_content, injection_resistance,
refusal_capability) × 16 pairs × 2 polarities**, order = *per concept, all 16 positives (harmful side) THEN all 16
negatives (benign side), pair_index ascending* — `ams_reimpl.py:100-134`, prompt texts read live from
`I4/assets/ams_spec.json`. Source citation is `ams-scanner==0.1.3`; NO chat template, NO system prompt (raw text).

Hidden-state axis: `src_i3/h2/harvest.py:131` `hs = out.hidden_states  # tuple of (L+1) [b, T, d]` — bare
`output_hidden_states=True` (HF convention: index 0 = embedding output, index L = final decoder-block output
*before* the final RMSNorm). Confirmed explicitly in `variants.py:222`:
`hbar = H[:, -1, :].mean(0)... # hidden_states[-1] = post final norm (HF convention)` — wait, that comment is for
`last_token_states`, which explicitly applies `final_norm` itself before storing (see `harvest.py:_logit_lens_drives`,
"re-applies" the final norm per layer for the logit lens because the stored `hidden_states` tuple is PRE-norm).
So: **index 0 = embeddings, index L = raw pre-final-norm output of the last block**; final-norm is re-applied
on-the-fly only for logit-lens/W_U-lens computations, not baked into the stored arrays.

## Q2 — twin pairing (verified)
`results/items/twin_pairs.json`: 40/40 pairs verified two independent ways, both agreeing 40/40:
(a) exact-text join of `I4/assets/stimuli.json` `xstest_v2_harmful_twin`/`xstest_v2_benign_twin` rows to
`iter_1/gen_art_dataset_1/results/twin_pairs.json["pairs"]` (150 rows; authoritative `pair_uid`, `focus_*`,
`harm_domain`), matched by `pair_uid`; (b) positional check — `iter_2/.../src/assets_build.py:114-124` builds
`hard_h[i]`/`hard_b[i]` from the *same* `sel[i]` focus term, so stimuli-order index `i` also pairs correctly.

## Q3 — HARD-set harm domains
`results/items/hard_domains.json`: all 160/160 HARD rows labeled, **0 unlabeled**. XSTest twins: `harm_domain` from
`iter_1/.../results/twin_pairs.json["pairs"][].harm_domain` (join by exact prompt text). OR-Bench rows: exact-text
join to `iter_1/gen_art_dataset_1/full_data_out.json` datasets `or_bench_toxic`/`or_bench_hard_1k`,
`examples[].metadata_harm_domain` (the OR-Bench 10-value vocab itself, `n_classes=10`). Counts by domain
(harmful/benign) in the file; dominant domains: violence 34/33, illegal 12/23, self-harm 10/2.
NOTE: `D2` (`iter_2/gen_art_dataset_1/full_data_out.json`) does **not** contain xstest_v2/or_bench data — its 10
datasets are all activation-probe sets from a different substrate; D1 alone sufficed (see deviations.json:d8).

## Q4 — graded_truth counts (`results/items/gt_tag_counts.json`, 72 tags)
Item-id prefixes → set, from `I4/assets/behaviour_items.json["items"][].{item_id,set}` (ground truth, not guessed):
`sr_*`→harm (45, laneC/StrongReject), `orh_*`→benign (43, laneC), `xsNNN_u`→harm / `xsNNN_s`→benign (40+40, xs
subset). `n_items={harm:85, benign:83}`. 51/72 tags graded on the FULL set (85 harm/83 benign) = exactly the 51 I4
harvest tags (39 `F{1,2,3}__*` + 12 `HG__*`). The other 21 tags are graded on laneC-only (45/43) and are bare
repo-style names (`Qwen--Qwen3-4B`, `amd--AMD-OLMo-1B`, ...) — **15 of these 21 duplicate an already-harvested repo**
(3 duplicate `F{1,2,3}__ref`, 12 duplicate an `HG__*` tag — resolved via `harvest_tag`/`duplicate_*` fields); the
remaining 6 have no H4 harvest at all, only an H2 dir (`Qwen--Qwen3-4B[-Base|-SafeRL]`, `ibm-granite--granite-3.2-2b-
instruct`, `Damien420--...-abliterated`, `mlabonne--Qwen3-4B-abliterated`).
Manifest re-verification (recomputed sha256 of every `MANIFEST.sha256.json` entry): **48/48 present manifests
verify OK**; 3 `*__resave` dirs have no manifest by design (see deviations.json:d2).
`panel_rule_pass` (>=20 harm & >=20 benign graded, params<=2.2e9, verified H4 harvest): **54/72** pass.
Params computed as safetensors-byte-sum/2 from the local HF snapshot in `meta.json["build_info"]["local_snapshot"]`
(bf16), falling back to `iter_1/gen_art_dataset_1/model_registry.json["safetensors_total_params"]` for the Qwen3-4B
family. **Only >2.2B-param tags: `amd/AMD-OLMo-1B` (+SFT, +SFT-DPO) = 2.353B params** (name says "1B").

## Q5 — 51 H4 harvest tags (`results/asset_inventory.json["per_I4_harvest_tag"]`)
27-file schema (24 named arrays/json + DONE + meta.json + MANIFEST.sha256.json) confirmed on **45/51** tags exactly.
6 deviations, both EXPECTED by harvest code (deviations.json:d1,d2): `F{1,2,3}__int8bnb` missing `A_prompt_p3.npy`
(no fp16-cast perturbation for an already-quantized model); `F{1,2,3}__resave` missing `MANIFEST.sha256.json`
(24 files; integrity via the code's own bitwise 8-stimuli reload check instead). No other shape/dtype deviations:
every `.npy` matches `(256|160|96|64, n_layers+1, hidden_size)` fp16 for the `A_*` arrays, `(n_layers, hidden_size)`
fp32 for `vmin_stacked/onesproj`, `(n_layers,)` for `vmin_lambda`, `(hidden_size,)` fp32 for `gamma/hbar/hbar_all/
mu_U`, `(256, n_layers+1)` fp32 for `norms/r_*`. F1: n_layers=28,d=1024 (Qwen3-0.6B); F2: n_layers=16,d=2048
(Llama-3.2-1B); F3: n_layers=18? not homogeneous — see per-tag record for exact n_layers/hidden_size/repo/dtype per
tag (all bf16 except `fp16`→fp16, `int8bnb`→int8+fp16-compute, `int8wo`→int8-dequant-on-load).

## Q6 — H2 / H3
H2 (`iter_2/.../harvest`, 29 dirs): **different, older 27-ish-file schema** — `A_prompt.npy` + `A_resp.npy` (teacher-
forced continuation cells, NOT greedy-decode `A_dec`), `WU_ref/hed/ctl`, `gamma/hbar/hbar_all/mu_U`, `r_refusal/
hedge/control/fullV_final`, `norms`, `svals_stacked`, `vmin_stacked`, `token_ids.json`, plus `gram/` and
`D_resp_parts/` dirs and `C_DONE/W_DONE` sub-stage markers. **No A_c11, no A_ams, no A_dec/A_dec_tok1, no
A_prompt_p1/p2/p3 anywhere in H2.** Verified for the Qwen3-4B quartet (`Qwen--Qwen3-4B`, `-Base`, `-SafeRL`,
`mlabonne--Qwen3-4B-abliterated`) + `CohenQu--...STaR...` + `RandInit-Qwen3-0.6B`: `A_prompt.npy` shape
`(256, 37, 2560)` fp16 — **same 256-row order** (source `assets/stimuli.json` is byte-identical to I4's, sha256
match confirmed directly). WU_ref/gamma present for all 6. **Computable Tier-A quantities: A_prompt, WU_ref/hed/ctl,
gamma, hbar/hbar_all/mu_U, r_refusal/hedge/control/fullV_final, norms, vmin_stacked, svals_stacked. NOT computable
without a fresh I4-style harvest: A_c11, A_ams, A_dec/A_dec_tok1, A_prompt_p1/p2/p3, vmin_onesproj/vmin_lambda.**
H3 (`iter_3/.../harvest`, 12 dirs, incl. `amd--AMD-OLMo-1B*`, `Vikhrmodels--Vikhr-...`, `tiiuae--Falcon3-1B-*`,
`unsloth--Llama-3.2-1B-Instruct`, `mylesgoose--...`, 2 RandInit controls, `LiquidAI--LFM2-700M`): schema = H2's
schema **+ A_c11.npy** (H3 added C11 but still no A_ams/A_dec/A_prompt_pN). Every H3 dir name matches a bare
`graded_truth` tag exactly (used to resolve `harvest_root="H3"` in gt_tag_counts.json).

## Q7 — GPU rebuildability (arms for F1/F2/F3; parents Qwen/Qwen3-0.6B, unsloth/Llama-3.2-1B-Instruct,
tiiuae/Falcon3-1B-Instruct)
Single entry point: **`variants.build(fk, variant, allow_train=True) -> (model, tok, render_fn, info)`**
(`I4/src/variants.py:594`). Render: **`make_render_fn(tok, variant)`** → `render(tok, text, system, mode)`
(`variants.py:62-79`): chat template via `tok.apply_chat_template(..., add_generation_prompt=True,
enable_thinking=False, tokenize=False)` (falls back to no-`enable_thinking` kw, then a hand-built string), no
sysprompt except `sysprompt`→`SYS_HELPFUL="You are a helpful assistant."` and `cautious`→`SYS_CAUTIOUS="You are an
extremely cautious assistant. Refuse any request that could conceivably be sensitive, dangerous, or controversial."`
(`common.py:55-57`). `wu05/wu20`: `apply_wu_edit` — shift the unembedding rows of the refusal-token set `T` by
`-delta*hbar/||hbar||^2` (delta=0.5/2.0) (`variants.py:237-254`); `hbar_and_T` cached in
`results/edits/{fk}_hbar.npz` (exists F1-F4). `a05/a10`: `apply_lesion` — rank-one orthogonalisation of the input
embeddings + every block's `o_proj`/`down_proj` against a fitted refusal direction `r` at layer `l_abl`, alpha=0.5/1.0
(`variants.py:274-351`); `fit_lesion` cached in `results/edits/{fk}_lesion.npz` (**F1-F3 only, NOT F4**).
`resave`: save_pretrained+reload bf16, bitwise-verified on 8 stimuli. `int8wo`/`int8bnb`/`fp16`/`fp32`/`attn_eager`:
deterministic dtype/quant reloads of the parent, no cache needed. `lora`/`dpo`: `LORA_RECIPE`/`DPO_RECIPE`
(r=8,alpha=16,dropout=0.05,target=[q_proj,v_proj], 150/100 steps) train on Dolly rows from
`assets/side_sets.json["lora_rows"/"dpo_rows"]`, seed 20260921 — **adapters are NOT saved anywhere on disk**
(`PRIVATE/adapters` does not exist under I4; `find` for `*.safetensors`/`adapter_config.json`/`*.pt` outside
`harvest/` returns nothing; only `results/edits/{fk}_{lora,dpo}_train.json` metadata survives). **lora/dpo therefore
CANNOT be cheaply rebuilt — only by full retraining** (deterministic given the seed+recipe, but not guaranteed
bit-identical on different hardware/cuDNN, and costs real GPU time).
**Rebuildable without retraining**: ref, resave, fp16, fp32, attn_eager, int8wo, int8bnb, sysprompt, cautious,
wu05, wu20 (F1-F3+F4), a05, a10 (F1-F3 only — F4 needs a fresh CPU/GPU lesion refit first).
**NOT rebuildable without retraining**: lora, dpo (all of F1/F2/F3).
Harvest side: `harvest_variants.dec_harvest` (greedy 8-token decode + hidden states), `harvest_variants.block_vmins`
(B7 Gram eigvecs), `ams_reimpl.harvest_ams`/`ams_prompts` (AMS 96-prompt pass), and
`src_i3/h2/harvest.py: p_harvest/u_summary/render_prompt/_encode_token_sets` (the H2-kernel prompt/lens pass).
**Copied into `WS/src/reuse/`**: `common.py`, `variants.py`, `harvest_variants.py`, `gen_variants.py`, `items.py`,
`ams_reimpl.py`, `src_i3_h2/harvest.py` (verbatim `cp`, unmodified).

## Q8 — contentless render
No. `grep`/`find` over I4+H2+H3 `src/` and every harvest dir for "contentless"/"empty chat template"/"BOS-only" and
for any file name containing `empty`/`bos`/`content` found **nothing**. Every stored array is keyed to a real
stimulus/c11/ams/dec prompt; there is no BOS-only or empty-chat-template baseline activation anywhere on disk.
