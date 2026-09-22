# BLOCK P — CONTRIBUTION BRANCHES (written 2026-09-22, before Blocks S and T returned, so the write-up lane can pick one without re-reasoning)

All three branches assume the run invariant: the deliverable is the activation-level comparison of the
Qwen3-4B family, and any metric built from it must read ACTIVATIONS OR WEIGHTS OF A SINGLE MODEL.
Logit-only and text-only readouts (BL1_easy, BL1_hard, BL1_truelogit, the model-card regex, the greedy
refusal-text rate) are BARS, never results. This is a mech-interp study of where safety lives. It is not
a jailbreak or attack-selection study and must not be reframed as one.

---

## BRANCH 1 — Block S returns NO CLOSED W, and Block T returns OPEN.

Three contributions, in this order:

(i) **A per-checkpoint false-alarm audit on BEHAVIOURALLY GRADED no-ops.** Nobody grades behaviour
    before calling a variant a no-op: everyone assumes a dtype cast, a re-download or a non-safety LoRA
    is a no-op rather than measuring whether it is. Closest prior, each of which must be cited and
    survived: Duan (arXiv:2606.15980) freezes probes across 12 quantisation/LoRA/QLoRA updates but
    scores per-input AUC and never grades behaviour; AMS (arXiv:2608.05578) runs FP16/INT8/INT4 on a
    SINGLE model with drift <= 4.4%, in an earlier round explicitly excluded from its own 14-model
    bootstrap/LOOCV panel; Hurtado (arXiv:2607.01854) runs 37 benign fine-tunes at FPR 0.11 but is
    reference-anchored -- "The audit rests entirely on the reference."

(ii) **Over-refusal as the TARGET a per-checkpoint internal readout is validated against**, reported
    beside BOTH the final-layer logit gap AND AMS Tier-1 sigma. Conditional on Block T returning OPEN.
    The distinction that carries this claim: reporting over-refusal as an OUTCOME COLUMN of one's own
    defence (which 2609.18471 and 2609.04721 both do) is not the same object as validating a score
    against it across checkpoints.

(iii) **A per-checkpoint scalarisation of redundancy and self-repair**, explicitly attributed to the
    circuits anchors -- see the attribution sentence in section "W4 ATTRIBUTION" of research_out.json.
    This contribution is a SCALARISATION of an established phenomenon, never its discovery, and it must
    be written that way in the abstract as well as in Related Work.

## BRANCH 2 — some W comes back CLOSED.

Drop that candidate from the contribution list BY NAME, state the closer with its quote, and re-issue
the surviving set. Specifically:

- If **W2 (redundancy depth)** or **W4 (self-repair coefficient)** is CLOSED, contribution (iii)
  degrades to "applying a known scalar in the safety domain against a new target". That is a weaker
  claim and MUST BE WRITTEN AS WEAKER: not "we introduce", but "we apply <closer>'s quantity to
  safety-relevant layer bands and score it against over-refusal, which <closer> does not do".
  The contribution then rests on the TARGET and the PANEL, not on the quantity.
- If **W8 (rotation under self-lesion)** is CLOSED, the parent-free framing is the only thing left and
  the paper should lead with (i) and (ii).
- If a G candidate is CLOSED, it drops silently from the screen; no G was ever load-bearing.
- In every case, contributions (i) and (ii) are untouched by a Block S closure, because they are
  claims about the AUDIT PROTOCOL and the TARGET, not about the quantity.

## BRANCH 3 — Block T returns CLOSED.

Then only (i) and the P1 bound survive. Say so in one sentence and hand the write-up lane the
demotion list:

- The over-refusal correlation table demotes from a CONTRIBUTION to a REPLICATION of the closer,
  reported with the closer cited in the caption.
- Every W candidate whose only outcome was over-refusal demotes from "validated readout" to
  "screened and reported", and the screen's conclusion becomes descriptive.
- P1 (the effective-rank bound on the candidate x checkpoint score matrix) becomes the HEADLINE, and
  the paper's deliverable is the BOUND: a family of cheap single-model internal safety readouts has
  only one usable coordinate, which AMS sigma and the logit gap already read. That is a result the
  field would act on, and it is a legitimate primary result rather than a consolation prize.
- The graded-no-op audit (i) is then the second result and the only surviving positive claim.

---

## THE TWO NARROWED DEFENSIBLE CLAIMS (the ONLY two novelty sentences the paper may assert)

**(a) Nobody grades behaviour before calling a variant a no-op.**
Must survive: Duan arXiv:2606.15980 (frozen probes across 12 quantisation/LoRA/QLoRA updates, per-input
AUC, no graded behaviour); AMS arXiv:2608.05578 (single-model FP16/INT8/INT4, drift <= 4.4%, excluded
from its own main 14-model panel); Hurtado arXiv:2607.01854 (37 benign fine-tunes, FPR 0.11,
reference-anchored).
Pre-register BOTH outcomes, because the specificity screen can genuinely fail: template and
system-prompt changes DO move behaviour (Arditi: Llama-2 22.6 vs 79.9% ASR; Qwen flat; ChatBug), and
quantisation usually preserves refusal but not always (SmolLM3; Kadadekar 12-68 point drops), while
frozen probes go stale under LoRA (43.2-53.8% big-drop). So an activation readout MAY fail specificity,
and that is a reportable result rather than a failed experiment.

**(b) Nobody uses over-refusal as the TARGET of a per-checkpoint internal readout.**
Must survive: whatever Block T's nearest miss turns out to be. Fill this in from
blockT/target_cell_table.json before the draft goes out.
