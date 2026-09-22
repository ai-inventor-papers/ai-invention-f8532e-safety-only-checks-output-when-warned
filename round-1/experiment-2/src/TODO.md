# LANE B — Erase the safety signal, remeasure  (gen_art_experiment_2)

## OUTPUT CONTRACT (recovered from the step's own prompt files — my prompt arrived TRUNCATED)
`/ai-inventor/aii_pipeline/src/aii_pipeline/prompts/steps/_3_invention_loop/_3_gen_art/experiment/`
- REQUIRED: method.py, method_out.json, full_method_out.json, mini_method_out.json, preview_method_out.json
- schema exp_gen_sol_out: {"datasets":[{"dataset":str,"examples":[{"input","output",metadata_*,predict_*}]}]}
  predict_* MUST be STRING; examples are additionalProperties:false; >=50 examples; >=1 predict_*
- must implement a BASELINE comparison; pyproject.toml required; max file 100MB

## ENV FACTS (measured)
- /ai-inventor/aii_data = MooseFS 2.2PB / 715TB free. The plan's "40GB disk" was `df /` on the
  docker overlay. Disk is NOT a constraint; all 5 checkpoints were already in the shared HF cache.
- 1x RTX A4500 20GB SHARED with 3 sibling lanes -> VRAM is the real constraint (saw 19.6/20.5 GB).
- numpy BLAS thrashes without OMP_NUM_THREADS=8 (a 205x205 solve took 3.6 s). Always export it.
- `pkill -f <pat>` MATCHES MY OWN Bash command line. Use `pgrep -f "name[.]sh"` bracketing.
- foreground `sleep` is blocked by the harness; it aborts the rest of the command chain.

## DONE
- [x] S0 substrate + prereg (T0 all pass). 150 twins, 96/54, 1 cosmetic focus disagreement logged.
- [x] S1 pilot: band [13..21] (depth .36-.61), split-half cos .927, r_ablit layer 22 d=11.16
      G1 |cos(r_content,r_ablit)| = .159 pooled / .175 max -> PASS (HARC kill-risk does NOT bite)
      T2 determinism 0.0, batch-invariance .0013; T3 alpha=0 bitwise no-op, embed_tokens untouched
      CONFIRMATION CB = 28.2 null-SD. achieved r = 6.07 (registered thresholds assumed ~1.2)
- [x] S9  mlabonne weight-space: per-matrix rank1 share .994, implied alpha .973, embed_tokens NOT edited
- [x] S9b DEPTH: community edit is ONE DIRECTION PER LAYER. adjacent-layer cos .773,
      shallowest-vs-deepest cos .016 (ORTHOGONAL), o_proj and down_proj share a layer's direction.
      Our per-layer r_ablit matches it at cos .646 vs only .265 for one pinned direction.

## PIPELINE BUILT AND VALIDATED END-TO-END (673 examples emit + schema PASS on L2 alone)
src/: lexicon substrate addendum engine seqbuild common readouts analyze redundancy
      causal weightcheck stage9_depth emit assemble   |  method.py  pyproject.toml
      run_all.sh (registered grid) followup.sh (causal then per-layer) finalize.sh

## RUNNING / QUEUED
- [x] L2 registered grid (693 s, peak VRAM 9.7 GB)
- [ ] L3, L1, L4 registered grid                          (run_all.sh)
- [ ] STAGE 7 causal arm L2,L3,L1,L4 at alpha 0 and 1     (followup.sh)
- [ ] DECLARED per-layer grid L*PL x 5 alphas             (followup.sh)
- [ ] finalize.sh: analyze -> redundancy -> emit -> assemble -> format -> validate

## PERFORMANCE FIXES THAT MATTERED
- State.win/lastp/nll/perposproj CACHED: analysis I/O 5.2 GB -> 242 MB, 6 min -> 45 s
- k4 exponential fit VECTORISED over items (bitwise-identical to the scalar fit)
- cv_probe_auroc uses the DUAL ridge form (n x n, not d x d) - d=2560 >> n
- np.savez (uncompressed): float16 residuals barely compress and the mount has 712 TB

## KEY OPEN ISSUE
D_primary (held-out CV probe AUROC) came back FLAT AT 1.000 at every alpha => failure mode F1,
no matched-damage point. Handled by: reporting the flat curve, falling back to the PRE-REGISTERED
SECONDARY (K1 O term) with the deviation declared, and adding two diagnostics (1-D axis readout
along u; JBB matched-behaviour probe). S9b explains WHY: one pinned direction is the wrong object.
