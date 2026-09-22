#!/usr/bin/env python3
"""Prereg amendments, each appended to results/prereg_amendments.json and hash-chained BEFORE the graded-truth commit.
Usage: python src/amend.py <id>   (ids defined below; idempotent)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, chain_append, chain_records, jdump, jload, setup_logging, utc_now  # noqa: E402

AMENDMENTS = {
    "A1": {"what": "int8 arm: torch.ao dynamic (per-channel weight + per-tensor dynamic ACTIVATION) quantisation replaced by "
                   "int8 WEIGHT-ONLY round trip (per-output-channel symmetric absmax, bf16 compute; head untied first). Arm tag int8wo.",
           "why": "smoke test on F1 before any behaviour item was generated: int8dyn gave first-token agreement 0.06 and max "
                  "|logit diff| 32.7 on the 32 held-aside Dolly sanity prompts (activation outliers; per-tensor activation "
                  "quantisation is exactly what LLM.int8 avoids). A destroyed model is not a deployment no-op.",
           "evidence": "private/smoke_gens/smoke_sanity.json (F1__int8dyn), logs/smoke_gen.out"},
    "A2": {"what": "run order: the core arms of all three families (ref, a10, int8wo, sysprompt, wu05, resave) first; then F1 "
                   "wu20, cautious, a05, lora; then F2/F3 wu20, cautious, a05; then fp32/attn_eager. Arms not reached by the "
                   "time budget are recorded NOT_RUN (never imputed).",
           "why": "measured throughput on this shared 2-thread CPU (F1 ref: 115 s + 59 s for the first two 42-item chunks; the "
                  "sibling agent's process took ~1.3 of the 2 cores at times) projects the full 30-arm design past the time budget.",
           "evidence": "logs/gen_F1ref.out"},
    "A3": {"what": "N5 perturbation set = {p2 system prompt (the sysprompt arm's A_prompt), p3 other precision (F1: fp32 arm "
                   "if run, else the int8wo arm; F2/F3: the int8wo arm)}; p1 (plain render) NOT harvested.",
           "why": "CPU budget; p2/p3 come free from arms that are harvested anyway.", "evidence": ""},
    "A4": {"what": "harvest reuse: wu05/wu20 arms run p_harvest and the decode pass live but COPY A_c11, A_ams and the vmin "
                   "files from the parent (same inputs and same body weights => identical activations; A_prompt bitwise "
                   "equality is asserted as a structural check); resave copies all parent arrays after a bitwise check on 8 stimuli.",
           "why": "CPU budget; exact by construction.", "evidence": ""},
    "A5": {"what": "N2 basis Q = QR of ALL stored WU_ref rows (the H2/D2 refusal-onset token set under this tokenizer, "
                   "~20-28 unique ids) instead of the top-16 D2 ids.",
           "why": "the top-16 ids are not stored for the on-disk harvested checkpoints (their weights are not in the cache); "
                  "WU_ref exists for every checkpoint, so the same rule applies to all.", "evidence": ""},
    "A6": {"what": "per-family generation protocol: F1 (Qwen3-0.6B) keeps the registered 168 items x 96 new tokens (chunks of 42); "
                   "F2 (Llama-3.2-1B) and F3 (Falcon3-1B) use Lane C 88 + the first 20 XSTest twin pairs (128 items) x 64 new "
                   "tokens (chunks of 64). Every pair is within one family, so parent and child always share one protocol; "
                   "pooled columns of F2/F3 pairs are over their 128 items.",
           "why": "a sibling agent's generation shares the 2 CPU threads (it held ~1.1 cores during F1 ref); F1 ref took 6.5 min "
                  "for 0.6B params, projecting 12-15 min per 1-1.7B arm at the registered protocol -> the three-family core "
                  "would not fit the time budget with the harvest and scoring after it.",
           "evidence": "logs/gen_F1ref.out, top snapshots (sibling PIDs in gen_art_experiment_2)"},
    "A7": {"what": "run order revised again: core = F1 {ref,int8wo,a10,sysprompt,wu05,resave}, F2 {same}, F3 {ref,a10,int8wo,"
                   "sysprompt,resave}; then F1 lora, cautious, wu20; then F3 wu05, F2 cautious, F1 a05, F2 wu20, F3 cautious/wu20, "
                   "F2/F3 a05; fp32/attn_eager last. F3 wu05 moved behind the extras because a head-only edit leaves every "
                   "prompt-site activation bitwise identical (it can only test logit/decode readouts).",
           "why": "16 GB cgroup at 15.5 GB and four processes on two threads during F1 ref (sibling generation + scoring + "
                  "this artifact's AMS validation): measured F1 arm cost ~7-8 min, 1B arms ~10 min.",
           "evidence": "top / memory.current snapshots at 16:26 UTC"},
    "A8": {"what": "parents F2 and F3 replaced: F2 unsloth/Llama-3.2-1B-Instruct -> Qwen/Qwen2.5-0.5B-Instruct (family qwen2.5); "
                   "F3 tiiuae/Falcon3-1B-Instruct -> HuggingFaceTB/SmolLM2-360M-Instruct (family smollm2). Both are SCREEN families "
                   "(iteration-2 harvest: Qwen2.5-1.5B(-Instruct), SmolLM2-1.7B(-Instruct)), so the confirmation sibling's new-family "
                   "panel stays uncontaminated. Their stock chat templates inject a default system prompt; 'sysprompt'/'cautious' "
                   "REPLACE it (a system-prompt swap). The Llama-3.2 family remains in the study through the harvested "
                   "unsloth->mylesgoose and Vikhr pairs. Decided before any F2/F3 arm was generated.",
           "why": "measured: F1 ref (0.6B) took 752 s at 21 tok/s under sibling contention; a 1.2-1.7B arm projects to 15+ min to "
                  "generate and 7-11 min to harvest, so the Llama/Falcon core (10 arms) plus harvest would exceed the remaining "
                  "budget; the 0.36-0.5B parents cost ~3x less per token.",
           "evidence": "logs/gen_F1ref.out (chunk times 115/59/115/423 s), results/gen_timings.json"},
    "A9": {"what": "extras order: F1 cautious (OR_EFFECTIVE, the within-pair two-sidedness test) before F1 lora and wu20; "
                   "decode-site harvest batch 32 (was 16; same computation, fewer batches).",
           "why": "on this CPU the LoRA arm is capped at ~12 min of training (a small benign fine-tune); the over-refusal "
                  "arm carries the iteration's TWO-SIDEDNESS question and is cheaper.", "evidence": ""},
    "A10": {"what": "order: F1 {ref,int8wo,a10,sysprompt} -> F2 {ref,a10,int8wo,sysprompt,wu05} -> F3 {ref,a10,int8wo,sysprompt,wu05} "
                    "-> F1 resave, F1 wu05, F1 cautious, F2/F3 resave, F1 lora, F1 wu20, then the rest. F1 wu05 (a head-only edit: "
                    "prompt-site activations identical by construction) is replaced in the core by the ~3x cheaper F3 wu05, keeping "
                    "8 intended non-trivial no-ops over 3 families in the core.",
            "why": "renice is not permitted in this container and the sibling runs three CPU-heavy processes, so this artifact's "
                   "single generation process gets ~0.4-0.5 of one core (F1 arm ~15-18 min).",
            "evidence": "top snapshots 16:32-16:35 UTC; renice: Permission denied"},
    "A11": {"what": "STAGED order chain: behaviour truth and pair classification are committed per stage (stage 1 = F1 core arms "
                    "+ the reused truth of the harvested checkpoints; later stages = F2/F3/extras), each stage as its own "
                    "graded_truth_sN.json -> classification_sN.json chain records; an arm may be harvested only after a "
                    "committed classification covering it (per-arm gate in src/harvest_variants.py). The rule, thresholds and "
                    "bootstrap are unchanged; per-pair bootstrap seeds are derived from the pair id so results do not depend on "
                    "stage composition; the final classification.json is the merged union (chain step 'merged').",
            "why": "CFS shares CPU per process and the sibling runs three CPU-bound processes: harvesting stage-1 arms while "
                   "later stages generate doubles this artifact's CPU share without ever harvesting an arm before its "
                   "behaviour is committed.", "evidence": ""},
    "A12": {"what": "lesion direction selection (a_lesion.selection): a candidate is KEPT only if it passes the KL filter "
                    "(KL < 0.1 on the 16 Dolly validation prompts) AND its refusal log-mass drop is POSITIVE (ablation must "
                    "reduce refusal, i.e. Arditi's bypass condition); pick the max drop among kept candidates; if none is kept, "
                    "the registered fallback applies unchanged: pick the max-drop candidate over ALL candidates and flag "
                    "KL_FILTER_FAILED. The F1 candidate table already computed under the literal rule (before any lesion-arm "
                    "behaviour existed) is reused verbatim (deterministic; no recomputation).",
            "why": "session 2, F1 fit (17:21 UTC): the ONLY KL-passing candidate was l=14 with drop -0.190 (its ablation "
                   "RAISES refusal log-mass), so the literal rule would register a 'lesion' that is not a refusal lesion for "
                   "the EFFECTIVE_LESION stratum. The generation process was stopped before any F1__a10 behaviour was "
                   "generated (no gens file existed); with A12, F1 falls back to l=19 (drop +0.731, KL 0.570, "
                   "KL_FILTER_FAILED). F2/F3 are fitted fresh under A12.",
            "evidence": "private/edits/F1_lesion_literal_rule_table.json (full 13-candidate table), logs/gen_sweep3.out"},
    "A13": {"what": "GPU RE-PLAN (session 4). (a) DEVICE: every arm is generated and harvested on CUDA (NVIDIA L4; bf16, sdpa). "
                    "Weights are CONSTRUCTED on CPU (lesion edit now in float64; int8wo elementwise; LoRA/DPO adapters merged "
                    "into a fresh CPU copy of the parent) and only then moved to the GPU, so generation and harvest rebuild "
                    "identical weights (fingerprint asserted). F1's three CPU-generated arms (ref, int8wo, a10: generated and "
                    "judged in session 3; no truth committed, no rate aggregated or inspected) are ARCHIVED to "
                    "private/gens_cpu_s3 + private/judged_cpu_s3 and enter NO pair; F1 is regenerated on the GPU so parent "
                    "and child always share one device; the CPU-vs-GPU F1__ref label agreement is reported only as a "
                    "DEVICE_SWAP check, never pooled. (b) PARENTS: A8 is WITHDRAWN -> F2 = unsloth/Llama-3.2-1B-Instruct, "
                    "F3 = tiiuae/Falcon3-1B-Instruct (the preregistered parents); no F2/F3 arm was ever generated under A8 "
                    "(only Qwen2.5-0.5B sanity logits / chunk files existed; archived). (c) PROTOCOL: A6 is WITHDRAWN -> "
                    "every family uses the registered 168 items x 96 new tokens (chunks of 42). (d) ARMS: the plan's GPU "
                    "arms are restored for all three families: fp16 (replaces the CPU fp32 substitute), int8bnb "
                    "(bitsandbytes LLM.int8 = the plan's registered int8 arm; int8wo from A1 is KEPT as a second int8 "
                    "no-op), lora (plan recipe: r 8, alpha 16, dropout 0.05, q/v, 150 steps, effective batch 8 = 2x4, seq "
                    "384, lr 1e-4 cosine, response-only loss) and dpo (plan recipe: LoRA from the PARENT, 100 steps, batch "
                    "4, beta 0.1, lr 5e-5, 400 Dolly coherence pairs, reference = adapter disabled). fp32 / attn_eager "
                    "(CPU-only optional extras) are dropped. (e) ORDER/STAGES: s1 = F1 {ref,a10,int8wo,sysprompt,fp16,"
                    "wu05,lora,resave} + the reused truth of the harvested checkpoints; s2 = the same F2 arms; s3 = the same "
                    "F3 arms; s4 = extras {cautious,wu20,a05,dpo,int8bnb} x F1-F3; s5 = optional F4 = Qwen/Qwen3-1.7B (the "
                    "ORIGINAL plan's F1; same family as F1, so it adds pairs, not families) with all 13 arms; s6 = optional "
                    "HG pairs: the <=1.7B harvested checkpoints regenerated under the same 168-item protocol on the GPU so "
                    "their POOLED columns exist (plan section 4), classified as separate pairs HG::<child> (their stage-1 "
                    "Lane C classification from reused truth stands). (f) N5: A3 is WITHDRAWN -> the plan's p1 (plain "
                    "render), p2 (helpful system prompt) and p3 (other half precision; int8bnb: NOT_AVAILABLE) are harvested "
                    "for EVERY arm. (g) LESION: F1 keeps the A12-selected direction already on disk (fit before any lesion "
                    "behaviour existed); F2/F3/F4 are fitted on the GPU under A12. Thresholds, the classification rule, "
                    "the bootstrap and every candidate definition are UNCHANGED.",
            "why": "the pod restarted at ~18:23 UTC onto a box with an NVIDIA L4 (23 GB) and 62 GB RAM; every CPU-budget "
                   "reason behind A2, A3, A6, A7, A8, A9 and A10 no longer applies. Decided before any F2/F3 behaviour "
                   "existed and before any graded truth or classification was committed.",
            "evidence": "logs/venv_gpu.out, results/hardware_session4.json",
            "added_pairs": [
                *[{"pair_id": f"{fk}__{v}", "parent": f"{fk}__ref", "child": f"{fk}__{v}", "family": fam,
                   "intended_stratum": st, "kind": "constructed", "optional": fk == "F4", "added_by": "A13"}
                  for fk, fam in (("F1", "qwen3"), ("F2", "llama3.2"), ("F3", "falcon3"), ("F4", "qwen3"))
                  for v, st in (("fp16", "NOOP"), ("int8bnb", "NOOP"), ("lora", "NOOP"), ("dpo", "NOOP"))
                  if not (fk == "F1" and v == "lora")],
                *[{"pair_id": f"F4__{v}", "parent": "F4__ref", "child": f"F4__{v}", "family": "qwen3",
                   "intended_stratum": st, "kind": "constructed", "optional": True, "added_by": "A13"}
                  for v, st in (("resave", "NOOP_TRIVIAL"), ("int8wo", "NOOP"), ("sysprompt", "NOOP"), ("wu05", "NOOP"),
                                ("wu20", "EXPR_EFFECTIVE"), ("cautious", "OR_EFFECTIVE"), ("a05", "EFFECTIVE_LESION"),
                                ("a10", "EFFECTIVE_LESION"))],
            ],
            "hg_pairs": [
                {"pair_id": f"HG::{c}", "parent": a, "child": f"HG__{c}", "family": fam, "intended_stratum": st,
                 "kind": "harvested_regen", "optional": True, "added_by": "A13"}
                for a, c, fam, st in (
                    ("F1__ref", "huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2", "qwen3", "EFFECTIVE_HARVESTED"),
                    ("F2__ref", "mylesgoose--Llama-3.2-1B-Instruct-abliterated2", "llama3.2", "EFFECTIVE_HARVESTED"),
                    ("HG__Qwen--Qwen3-1.7B", "huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2", "qwen3", "EFFECTIVE_HARVESTED"),
                    ("HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct", "Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct-abliterated",
                     "llama3.2", "EFFECTIVE_HARVESTED"),
                    ("HG__amd--AMD-OLMo-1B", "amd--AMD-OLMo-1B-SFT", "olmo", "SENSITIVITY_AMD"),
                    ("HG__amd--AMD-OLMo-1B-SFT", "amd--AMD-OLMo-1B-SFT-DPO", "olmo", "NOOP_HARVESTED"),
                    ("HG__Qwen--Qwen2.5-1.5B-Instruct", "Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3",
                     "qwen2.5", "EFFECTIVE_HARVESTED_EXTRA"),
                )] + [{"pair_id": "HG::tiiuae--Falcon3-1B-Instruct", "parent": "HG__tiiuae--Falcon3-1B-Base",
                       "child": "F3__ref", "family": "falcon3", "intended_stratum": "SAFETY_TRAINING_EXTRA",
                       "kind": "harvested_regen", "optional": True, "added_by": "A13"}],
            "withdrawn": ["A3", "A6", "A8", "fp32/attn_eager arms (A2/A7 CPU extras)"]},
}


def main() -> None:
    setup_logging("amend")
    ids = sys.argv[1:]
    if any(r["step"] == "graded_truth" for r in chain_records()):
        raise SystemExit("graded truth already committed: no further amendments")
    p = RESULTS / "prereg_amendments.json"
    cur = jload(p) if p.exists() else []
    have = {a["id"] for a in cur}
    for i in ids:
        if i in have:
            continue
        cur.append({"id": i, "utc": utc_now(), **AMENDMENTS[i]})
    jdump(cur, p)
    chain_append("prereg_amendment", p, ",".join(ids))


if __name__ == "__main__":
    main()
