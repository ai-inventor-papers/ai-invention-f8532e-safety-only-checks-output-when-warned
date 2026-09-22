# Paired-Lineage Registry -- ARTEFACT 1 (raw half) build report
Built at: 2026-09-21T03:57:03.202105+00:00
Candidates screened (unique repos across the live search sweep): 1587
Search terms used (24): abliterated, uncensored, orthogonalized, orthogonalised, heretic, decensored, refusal removed, Josiefied, no refusal, Llama-3.2-1B abliterated, Llama-3.2-3B abliterated, Llama-3.2 uncensored, Falcon3 abliterated, Falcon3 uncensored, MiniCPM abliterated, MiniCPM uncensored, EXAONE abliterated, internlm abliterated, Index-1.9B abliterated, h2o-danube abliterated, Qwen2.5-0.5B abliterated, Qwen2.5-3B abliterated, gemma abliterated, gemma uncensored
Total bytes downloaded this run: 4233999 (4.234 MB) -- text/metadata only, no *.safetensors bytes were ever downloaded.

## Counts
- Pairs: **18**
- Families (via pairs): **12**
- Fresh pairs (neither side in SEED_PANEL): **8**
- Checkpoints harvested: **42**
- Unavailable repos: **0**

### recipe_stratum histogram
- unknown: 8
- standard_prompt_rank1: 7
- retrained_after_edit: 3

## Commissioned pair (Qwen/Qwen3-4B -> mlabonne/Qwen3-4B-abliterated)
- present: yes; parent gated=false; child gated=false
- comparable_dtype: False (parent dtype=bfloat16, child dtype=float32) -- an bf16 parent compared against a reported F32 (~16.09 GB) child is a STATED DEVIATION, not a silent one.
- forbidden lookalike `huihui-ai/Qwen3-4B-abliterated` was NOT used (excluded_candidates records why).

Note: `huihui-ai/Qwen3-4B-abliterated` (gated='auto') was excluded per task instruction and never fetched for use as a pair member.

## Revision drift vs iteration-1 pinned revisions
- none: every repo that was pinned in iteration-1's prereg.json still resolves to the same `sha` today.

## Size-anomaly resolutions (evidence-backed)
### TinyLlama: philippefunk/TinyLlama-1.1B-Chat-v1.0-abliterated
- size_anomaly_cause = **missing_shards**; usable_pair = False
- evidence: parent bytes=2200119864, child bytes=807426286 (ratio=0.367); parent params_total=1100048384, child params_total=630759982 -- the child's safetensors metadata reports FEWER total parameters than its declared parent (not merely a smaller dtype), with a mixed F32/F16/U8 parameter-dtype breakdown and no `torch_dtype` recorded in `config.json`. This confirms the iteration-1 report of a shape error under `ignore_mismatched_sizes`: the checkpoint is missing/incomplete weight content, not just stored in a smaller dtype.
- VERDICT: **UNLOADABLE ARTEFACT** (missing_shards), NOT a null-edit control. usable_pair forced to false; exclusion_reason recorded.

### venkycs/SmolLM2-1.7B-Instruct-Abliterated
- size_anomaly_cause = **dtype_difference**; usable_pair = True
- evidence: parent bytes=3422777952, child bytes=1814978304 (ratio=0.5303); parent params_total=1711376384, child params_total=1712015360 (essentially IDENTICAL param counts); parent dtype=bfloat16, child config-declared dtype=float16, but child's per-dtype byte breakdown is {'F32': 739328, 'F16': 100663296, 'F8_E4M3': 1610612736} -- the majority of its weight tensors are actually stored as F8_E4M3 (fp8), not the dtype its config.json declares; the single shard is present and complete (shard_list=['model.safetensors']).
- VERDICT: shard list is **COMPLETE** and the gap is **dtype** (fp8 quantization on top of an equal-parameter-count checkpoint) -> genuine ANOMALOUS pair; stays in the registry, comparable_dtype=false is recorded.

### allenai/OLMo-2-0425-1B vs allenai/OLMo-2-0425-1B-Instruct (base ~2x its own instruct; NOT a parent/child abliteration pair -- recorded under `known_size_anomalies_non_pair`)
- size_anomaly_cause = **dtype_difference**
- evidence: base bytes=5939687552 (dtype=float32), instruct bytes=2969854224 (dtype=bfloat16); ratio=0.5 (~0.5, i.e. base is ~2x); base params_total=1484916736 == instruct params_total=1484916736 (identical parameter counts) -- the base checkpoint is stored in float32 (2 shards) while the instruct checkpoint is stored in bfloat16 (1 shard); 4 bytes/param vs 2 bytes/param exactly explains the ~2x ratio.

## Gated repos we refused to authenticate into (recorded, not accessed)
- `meta-llama/Llama-3.2-3B-Instruct` gated=true (usable=False)
- `google/gemma-3-1b-it` gated=true (usable=False)
- `google/gemma-2-2b-jpn-it` gated=true (usable=False)
- `huihui-ai/Qwen3-4B-abliterated` gated='auto' was excluded per task instruction WITHOUT a live check (not fetched at all, per instruction not to use it).

## Repos that 404'd or were otherwise unreachable (as of 2026-09-21)
- none: every candidate repo resolved.

## Chat-template precedence rule (verified against installed transformers)
transformers==5.17.0, `tokenization_utils_base.py` `PreTrainedTokenizerBase._from_pretrained()` (~line 1783): "If independent chat template file(s) exist, they take priority over template entries in the tokenizer config." -- when a repo ships BOTH a standalone `chat_template.jinja` and a `chat_template` key inside `tokenizer_config.json`, `AutoTokenizer.from_pretrained` loads the `.jinja` file and never reads the tokenizer_config key. Recorded per checkpoint as `chat_template_source` (`tokenizer_config` | `chat_template_jinja` | `both` | `none`) plus `chat_template_winner`.

## Fresh (search-discovered) pairs
- **llama3.2__Llama-3.2-3B-Instruct-heretic-ablitered-uncensored**: `meta-llama/Llama-3.2-3B-Instruct` -> `DavidAU/Llama-3.2-3B-Instruct-heretic-ablitered-uncensored` (parent_declared_by=cardData_base_model, stratum=standard_prompt_rank1)
- **gemma3__gemma-3-1b-it-heretic-extreme-uncensored-abliterated**: `google/gemma-3-1b-it` -> `DavidAU/gemma-3-1b-it-heretic-extreme-uncensored-abliterated` (parent_declared_by=cardData_base_model, stratum=standard_prompt_rank1)
- **minicpm__Huihui-MiniCPM5-2B-abliterated**: `openbmb/MiniCPM5-2B` -> `huihui-ai/Huihui-MiniCPM5-2B-abliterated` (parent_declared_by=cardData_base_model, stratum=standard_prompt_rank1)
- **llama3.2__Vikhr-Llama-3.2-1B-Instruct-abliterated**: `Vikhrmodels/Vikhr-Llama-3.2-1B-Instruct` -> `Vikhrmodels/Vikhr-Llama-3.2-1B-Instruct-abliterated` (parent_declared_by=cardData_base_model, stratum=unknown)
- **minicpm__MiniCPM5-2B-Abliterated-Uncensored-Safetensors**: `openbmb/MiniCPM5-2B` -> `mondk/MiniCPM5-2B-Abliterated-Uncensored-Safetensors` (parent_declared_by=cardData_base_model, stratum=unknown)
- **gemma__gemma-2-2b-jpn-it-abliterated-18**: `google/gemma-2-2b-jpn-it` -> `ymcki/gemma-2-2b-jpn-it-abliterated-18` (parent_declared_by=cardData_base_model, stratum=retrained_after_edit)
- **gemma__gemma-2-2b-jpn-it-abliterated-17**: `google/gemma-2-2b-jpn-it` -> `ymcki/gemma-2-2b-jpn-it-abliterated-17` (parent_declared_by=cardData_base_model, stratum=retrained_after_edit)
- **qwen3__Qwen3-4B-Instruct-2507-heretic**: `Qwen/Qwen3-4B-Instruct-2507` -> `heretic-org/Qwen3-4B-Instruct-2507-heretic` (parent_declared_by=cardData_base_model, stratum=standard_prompt_rank1)
