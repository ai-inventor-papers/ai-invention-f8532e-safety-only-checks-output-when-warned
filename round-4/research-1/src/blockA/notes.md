# Prior-art scan: cheap activation-based safety metrics (C1-C5), 2026-09-21

## Verdict: OPEN

No single paper combines (a) per-checkpoint no-op/false-alarm robustness testing (C1), (b) over-refusal as an
outcome (C2), (c) a logit/first-token baseline compared against the activation readout (C3), (d) a decode-site
(model's-own-generated-token) activation readout (C4), and (e) a causal steering/ablation test of the readout
direction with a random/orthogonal control (C5) — together with an AMS-style stored-baseline "identity
verification" comparison. The empty cell targeted by the invention is confirmed **OPEN**.

## Compact C1-C5 table

| Row | Paper | C1 (no-op FA) | C2 (over-refusal) | C3 (logit baseline) | C4 (decode-site) | C5 (causal test) |
|---|---|---|---|---|---|---|
| 1a | AMS / Messenger 2026 (2608.05578, = IEEE Access) | **PARTIAL** (1-model FP16/INT8/INT4, excluded from main panel) | OPEN | OPEN | OPEN (named "principal open problem") | OPEN |
| 1b | N-GLARE (2511.14195, ACL 2026) | OPEN | OPEN (RR is on harmful/jailbreak prompts, not benign) | OPEN | OPEN (last PROMPT token, pre-generation) | OPEN |
| 1c | RAS/SafeVec (2606.25750) | OPEN | OPEN | OPEN | OPEN (last-token, prompt-side) | OPEN (explicitly disclaims steering) |
| 1d | Aligned Probing (2503.13390, TACL 2026) | **CLOSED** (OLMo Full/Half/4-bit, toxicity not refusal) | OPEN | OPEN | OPEN | PARTIAL (layer-skip ablation, no direction-vs-random control) |
| 1e | IRT for AI Safety (2608.05086) | OPEN (quant named as risk, not tested) | CLOSED but **behavioral only** (OR-Bench-Hard, no activations at all) | OPEN | OPEN | OPEN |
| 1f | Jiang, "When Behavioral Eval Fails" (2606.08044) | OPEN (own limitation: "quantization ... untested") | **CLOSED** (per-model over-refusal + benign-answer-rate) | OPEN | OPEN | **CLOSED** (PGD/steering/patching w/ matched random controls) |
| 1f | Galeone, "Perfect Detection, Failed Control" (2606.24952) | OPEN | PARTIAL (factual over-refusal stress test, not harmful-request) | **CLOSED** (lm_head/logit-lens dir vs. activation dir) | OPEN (last prompt token) | **CLOSED** (dose-response steering, cross-model) |
| 1f | Hurtado, "Has this checkpoint been abliterated?" (2607.01854) | PARTIAL (273-ckpt registry, 37 benign FT/merge hard negatives, FPR 0.11) | OPEN | OPEN | OPEN (own limitation: last-token gap "cannot see" CoT-migrated refusal) | OPEN (layer-band ablation named future work) |
| 1f | Mitra, "Closing the Activation-Cone Blind Spot" (2606.29441) | PARTIAL (probe FPR vs. negative-set diversity, not model no-ops) | OPEN | OPEN | **CLOSED** (probe on hidden state at first generated tokens, AUROC .97-1.0) | PARTIAL (rich defense comparison, no explicit random-direction control of own probe) |
| 1f | Jorak (GitHub, no arXiv) | OPEN (GGUF = load failure only) | PARTIAL (`behavioral_over_refusal` veto signal, custom probes not XSTest) | OPEN (logit-gap only *proposed*, not implemented) | OPEN (1-forward-pass activations + separate behavioral generation, never combined) | OPEN |
| **NEW** | "First Token Matters" (2609.18471, 16 Sep 2026) | OPEN | **CLOSED** (XSTest, per model) | **CLOSED** (Logit Lens vs. activation Refusal-Projection-Strength) | **CLOSED** (readout explicitly at first generated token) | **CLOSED** (two-sided NS/PS steering) |
| **NEW** | "Locating and Steering Refusal Beyond Attention" (2609.04721, 4 Sep 2026) | OPEN | **CLOSED** (XSTest + OR-Bench-hard) | OPEN | PARTIAL (write-site, not clearly decode-token) | **CLOSED** (systematic matched-random-direction controls) |

## Most important quotes

**AMS (2608.05578) — Tier 2 "identity verification"**: "Tier 2: Identity Verification ... Compares a model's
activation fingerprint against a stored baseline for its claimed identity. We measure: Direction similarity:
Cosine similarity between direction vectors (>0.8 required); Separation drift: Relative change in separation
magnitude (<20% required)." The paper's own quantization robustness test: "Maximum drift across concepts was
4.4% ... We also verified that a CRITICAL model (Dolphin-2.9) remains CRITICAL at INT4," but this is explicitly
"an earlier round of validation" excluded from the main 14-model bootstrap/LOOCV panel. AMS names decode-site
detection as its own open problem: "detecting class (iv) likely requires ... token-level decoding analysis
(measuring how the model treats refusal tokens at generation time) ... We treat this as the principal open
problem motivated by the present work."

**Aligned Probing (2503.13390)** is the strongest true C1 (no-op quantization) precedent found anywhere, but for
toxicity, not refusal/jailbreak safety, and on one model (OLMo): "These results demonstrate behavioral and
internal evaluations in the context of toxicity remain valid under model quantization."

**Hurtado (2607.01854)** is the strongest C1 precedent aimed at refusal/abliteration specifically: "On a
273-checkpoint registry ... their z-sum separates 57 public abliterations from 37 benign fine-tunes, merges, and
instruction-tunes at AUROC 0.95 ... FPR 0.11." It also directly benchmarks AMS Tier-1/Tier-2. But it explicitly
flags C4 as unaddressed: "a last-token gap cannot see" refusal that "migrates into the generated
chain-of-thought," and names layer-band causal ablation as future work.

**Jiang (2606.08044)** gives the richest C5 battery found (matched random controls for PGD attacks, directional
steering, and activation patching with a control), and explicitly closes C2 (over-refusal moves ≤0.04 across
base/"dissociated" models). Yet its own limitations section states plainly: "whether it survives routine
operations like quantization is untested" — a direct admission of the C1 gap.

**Galeone (2606.24952)** is the strongest C3 precedent: an lm_head/logit-derived direction is built from the
identity of the first generated token and compared, geometrically and causally, against an activation-derived
direction — including measuring the angle to "the direction producing a refusal" (cos = 0.12, ~83°). This is a
direct empirical demonstration that a detectable direction is not necessarily the causally controlling one — a
key caution for any C3-style comparison.

**Mitra (2606.29441)** gives the cleanest C4 precedent: "a linear probe on the model's hidden state at the first
few generated tokens (mean-pooled over N = 5 ... N = 1 sufficient), training-distribution AUROC 0.97–1.00 across
all seven models" — activations read explicitly at the model's own decoded tokens, not the last prompt token.

**New work, "First Token Matters" (2609.18471, posted 2026-09-16)** is the single closest work to the target
empty cell found in the whole survey. It closes C2 ("we measure over-refusal using the XSTest dataset"), C3
("we use Logit Lens to trace the rank evolution of typical refusal tokens ... the final-token logit difference
between the two label tokens 'Sure' and 'I'"), C4 ("We project the hidden states of each generated token onto V
and track the resulting Refusal Projection Strength ... it drops sharply at the first generated token"), and C5
(two-sided steering: "R1-8B 45% → 75% [Negative Steering] / 45% → 21% [Positive Steering]"). Critically, it never
mentions quantization, dtype, chat templates, re-downloads, or non-safety fine-tuning anywhere in the paper —
C1 is untouched even in this most complete precedent — and it is evaluated on only two reasoning-model
checkpoint families (DeepSeek-R1-Distill-Llama-8B / R1-Qwen-7B), not a broad per-checkpoint panel with an
AMS-style stored-baseline comparison.

**New work, "Locating and Steering Refusal Beyond Attention" (2609.04721, posted 2026-09-04)** closes C2
(XSTest + OR-Bench-hard, with an explicit 21% false-positive rate on the OOD benchmark) and C5 (systematic
"matched random direction through the same map" controls across six cross-architecture transfer directions),
but has no logit baseline (C3 OPEN), no quantization testing (C1 OPEN), and its "write site" readout is a
within-layer spatial locus rather than a clearly decode-token-indexed readout (C4 scored PARTIAL).

## Surprises

1. **AMS already has a quantization robustness experiment** (FP16/INT8/INT4 on one Llama model, 4.4% max drift,
   CRITICAL stays CRITICAL) but it is explicitly siloed from the paper's main validated 14-model panel — the
   authors clearly saw the need for a C1-style check but did not scale it or integrate it into Tier-1/Tier-2
   scoring. This is a strong argument that the target invention (per-checkpoint no-op battery, integrated into
   the main scanner) is a genuine, motivated gap rather than an oversight nobody has thought about.
2. **"Messenger 2026 IEEE Access"** (row 1f in the brief) turned out to be the *same paper* as AMS (2608.05578) —
   confirmed via the author's own LinkedIn post ("Pleased to share that my paper is now published in IEEE
   Access: 'Detecting Safety Training Modification in Language Models via Activation Analysis'") and his Google
   Research page. No separate IEEE Access paper exists; this collapses two brief rows into one.
3. **Jiang (2606.08044) explicitly names quantization robustness as untested** in its own limitations section —
   an unusually direct, citable admission of exactly the gap targeted by this research, from a paper otherwise
   very strong on C2/C5.
4. **N-GLARE's Fig. 7 "Refusal Rate" is on the harmful/jailbreak side, not the benign side** — resolving the
   brief's key open question: it is a safety-training-persistence signal, not an over-refusal (C2) signal. This
   matters because at a glance the RR/JSS coupling figure could easily be mis-read as over-refusal tracking.
5. **The single closest work to the target invention (2609.18471) is about large reasoning models' "onset
   refusal collapse," not about a general-purpose model-scanning tool** — it closes 4 of 5 criteria almost by
   accident, as a side effect of mechanistically explaining why LRMs comply more than their instruction-tuned
   counterparts, rather than as a deliberate safety-metric-validation exercise. It has zero awareness of C1
   (quantization/no-op robustness) as a concern.
6. **Item Response Theory for AI Safety (2608.05086)** is a highly relevant *framing* paper (explicit
   measurement-invariance/construct-validity treatment of safety scores, with over-refusal as one of three
   extracted latent factors, and an audit application to detect silent API model swaps) but is entirely
   behavioral — it never touches model internals at all, so despite strong topical overlap it cannot close any
   of C3/C4/C5.
7. **Jorak**, a community (non-arXiv, French-documented) GitHub tool, independently arrived at almost the same
   three-plane design philosophy (weight-space / activation / behavioral, with an explicit over-refusal veto)
   that a principled cheap-safety-metric system would want, and even *proposes* (but has not implemented) a
   refusal-logit-gap metric as a future refinement — corroborating from an independent, non-academic source that
   practitioners perceive the same C1/C3/C4/C5 gaps as this research targets.
8. **No paper anywhere gives an internal/activation-based readout for a safe-completion-style model** (declines
   without lexical refusal, OpenAI 2508.09224-style) — searched explicitly and found nothing; this remains an
   open niche adjacent to, but not resolved by, any paper in this survey.

## Searches run (≥12, mixed scholarly/general)
See `searches_run` array in `cell_table.json` for the full list of 17 queries executed.
