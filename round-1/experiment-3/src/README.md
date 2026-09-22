# LANE C — Does an activation-only safety readout predict real safety?

A cross-family mechanistic-interpretability screen (**test S3**): can a metric that
reads only the **activations or weights of a single model** predict how safely that
model actually *behaves*, across model families, from a handful of prompts — and does
it beat cheap text/logit baselines?

This is the "payoff" lane of a five-candidate wide screen. It owns **S3 only**
(leave-one-family-out prediction with no recalibration); a candidate is promoted by
whoever aggregates lanes A/B/C (needs ≥2 of 3).

## What was done

1. **Assets (C1)** — built self-contained prompt/panel assets from verified public
   URLs (XSTest twins, StrongREJECT-small, JBB-Behaviors, OR-Bench), with hard
   leakage assertions (ground-truth ∩ probe = ∅, reserved twins loaded nowhere, etc.).
2. **Panel + seal (C2)** — live HuggingFace sweep; **7 scored families** (Qwen3 incl.
   the commissioned 4B Base/Instruct/SafeRL trio + 0.6B/1.7B arms; Qwen2.5; SmolLM3;
   Granite; OLMo-2; TinyLlama; Phi-4-mini) and **2 SEALED families** (StableLM,
   SmolLM2) measured but withheld from truth for iteration 2. Frozen by SHA-256 in
   `prereg.json` before the first activation.
3. **Harvest (C3)** — ONE teacher-forced activation sweep per checkpoint pays for all
   five candidate readouts: **K1** arming decomposition `[O, CB, A, T]` of the
   projection onto a per-checkpoint response-site content direction `r_content`; **K2**
   request-side prior+slope; **K3** base-relative footprint (activation+weight); **K4**
   hazard-decay τ; **K5** domain profile. All in a random-direction NULL-SD unit so
   features are comparable across hidden sizes 1024–3072 with no recalibration. Seven
   baselines B1–B7 (incl. an N-GLARE APT/JSS reimplementation).
4. **Ground truth (C4/C5)** — greedy generations LLM-judged (gemini-2.5-flash-lite
   primary, gpt-5-mini audit) into three columns: harmful-compliance, over-refusal,
   and the co-primary **safe-engagement**.
5. **S3 (C6)** — leave-one-family-out ridge; pairwise ranking accuracy; decision =
   margin ≥ 0.15 over the oracle-selected strongest baseline AND family-clustered
   bootstrap 95 % CI > 0 AND ≥ 5/7 families won; prompt-budget curve k∈{4,8,16,32,96};
   random/oracle/shuffle machinery controls.

## Headline result

**No candidate passes S3** on either target (machinery clean: oracle 1.00, random/
shuffle ≈ 0.56 noise floor). The strongest cross-family predictor is the **logit
baseline B3** (first-token refusal-logit gap: 0.851 safe-engagement, 0.863
harmful-compliance). The best **activation** candidate is **K1 (arming)** — 0.671 /
0.810, and already 0.882 on harmful-compliance from just **k=4 prompts** — but it does
not beat B3. Within the commissioned Qwen3-4B trio the arming term **A** cleanly orders
Base (−2.32) < Instruct (+0.18) < SafeRL (+1.90), and SafeRL is a *safe-completion*
model (~0 % refusal) whose safety refusal-based baselines miss internally — yet this
arming signal does not transfer across families. Both outcomes are publishable; the
result localises that the response-site arming representation is real and
family-specific but not a family-invariant behavioural predictor at this panel size.
Total OpenRouter cost ≈ **$0.31** of the $10 budget.

## Layout

| Path | What it is |
|------|-----------|
| `method.py` | Entry point / stage dispatcher (`--stage assets\|prereg\|harvest\|judge\|analyze\|output\|finalize\|all`; default `finalize`). |
| `lc_common.py` | Shared config, paths, hashing, logging. |
| `lc_assets.py` | C1 asset build + leakage assertions. |
| `lc_panel.py` | C2 live HF panel sweep + seal + `prereg.json`. |
| `lc_harvest.py` | C3/C4 per-checkpoint activation harvest + generation (GPU). |
| `lc_judge.py` | C5 async LLM judging (+ audit / kappa). |
| `lc_analyze.py` | C6 S3 leave-one-family-out + controls + budget curve. |
| `lc_output.py` | C7 assembles `method_out.json` (exp_gen_sol_out schema). |
| `prereg.json`, `prereg.sha256` | Pre-registered, SHA-256-frozen design. |
| `assets/` | Prompt/panel assets (twins, ground-truth, probes, fitting corpora). |
| `results/per_ckpt/`, `results/sealed/`, `results/s3/` | Per-checkpoint features, sealed candidate values (no truth), S3 tables. |
| `results/gens/`, `results/judged/` | Raw generations & judge labels (excluded from the repo; see `upload_ignore_regexes`). |
| `method_out.json` + `full_/mini_/preview_` | Final output (2 datasets: S3 predictions with `predict_<method>`, and behavioural ground truth). |
| `pyproject.toml` | Pinned dependencies (exact run versions). |
| `.aii/manifest.yaml` | Keep/delete decisions for large cache dirs. |

## How to run

```bash
# regenerate method_out.json + S3 tables from the cached harvest/judge results (no GPU):
uv run method.py                      # default stage = finalize (analyze + output)

# full pipeline from scratch (needs a GPU for the harvest, ~hours):
uv run method.py --stage all
# or stage by stage: assets -> prereg -> harvest -> judge -> analyze -> output
```

## Restoring removed files

The two virtual environments and the Python bytecode caches are deleted from the repo
(regenerable). To restore them:

```bash
# .venv  (main environment, transformers 5.17.0)
uv venv .venv --python=3.12
uv pip install --python=.venv/bin/python torch==2.6.0 \
  --index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match
uv pip install --python=.venv/bin/python transformers==5.17.0 accelerate==1.15.0 \
  safetensors==0.8.0 huggingface-hub==1.32.0 numpy==2.5.3 scipy==1.18.1 pandas==3.0.6 \
  scikit-learn==1.9.1 loguru==0.7.3 requests==2.34.2 aiohttp==3.14.3 tenacity==9.1.4 pyarrow==25.0.1

# .venv_phi  (transformers 4.53.3 — used ONLY for the two Phi-4-mini checkpoints,
#             whose trust_remote_code modelling is incompatible with transformers 5.x)
uv venv .venv_phi --python=3.12
uv pip install --python=.venv_phi/bin/python torch==2.6.0 \
  --index-url https://download.pytorch.org/whl/cu124 --index-strategy unsafe-best-match
uv pip install --python=.venv_phi/bin/python transformers==4.53.3 accelerate safetensors \
  huggingface_hub numpy scipy scikit-learn loguru requests aiohttp

# __pycache__/  (bytecode) — regenerates automatically on the next import; or:
uv run python -c "import method"
```
