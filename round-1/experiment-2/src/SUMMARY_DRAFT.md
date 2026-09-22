# Draft summary — fill every <> from out/*.json before shipping. No number from memory.

TITLE (<=90 chars, plain, ~40 target):
  "Abliteration removes the refusal, not the harm representation"

LAYMAN SUMMARY (2-3 sentences, no jargon):
  We tried to surgically delete a model's sense of "this request is harmful" by erasing the one
  internal direction that uncensoring tools erase. The deletion worked perfectly — that direction
  was completely gone — and the model could still tell harmful requests from harmless ones just
  as well as before. What those tools actually remove is the model's willingness to refuse, not
  its ability to recognise harm; and the thing they remove is not one direction but a different
  direction at every layer.

SUMMARY (technical, ~2000 chars):
  - what was built: 96 XSTest minimal-edit twins in a 2x2 (request x response-prefix) with
    token-identical response spans; frozen prereg; 4 Qwen3-4B lineages x 5 lesion strengths
  - THE LESION IS VERIFIED: raw projection gap falls as (1-alpha) to 0.02% of baseline
  - THE REPRESENTATION SURVIVES: held-out CV probe AUROC 1.000 at every alpha
  - G1 = 0.159: prompt-site and response-site harm axes are near-ORTHOGONAL
  - STAGE 9: real community abliteration is per-matrix rank-one, implied alpha 0.973,
    embed_tokens untouched, and its direction ROTATES with depth (layer0 vs layer35 cos 0.016)
  - registered S2 = INDETERMINATE (F1, flat damage curve) — reported, not relaxed
  - K1 signature holds in SIGN: |A| falls 21%, |CB| holds
  - metric answer: <fill from cross_lineage_metric_alpha0>

OUT_EXPECTED_FILES:
  script: method.py
  full_output: full_method_out.json
  mini_output: mini_method_out.json
  preview_output: preview_method_out.json

MUST STATE PLAINLY IN THE FINAL MESSAGE:
  - the registered PRIMARY damage variable was UNMET for every lineage (if so) -> S2 INDETERMINATE
  - K4's observed sign is OPPOSITE to its registered signature
  - the full-annihilation companion is NOT matched damage
  - the per-layer grid is a DECLARED addition motivated by STAGE 9, scored separately
  - the hook implementation of the edit is a stated deviation (with its equivalence proof)
  - what was NOT done / cut
