#!/usr/bin/env bash
# Idempotent relauncher for the blind held-out panel.
#
# This pod has restarted mid-run more than once.  Everything in this artifact is
# resumable -- chunk-resumable generation, per-tag GEN_DONE / JUDGED / DONE
# markers, an append-only hash chain and an atomically written manifest -- so the
# correct recovery action after ANY crash is simply to re-run this script.  It
# skips completed tags and never redoes finished work.
#
#   bash logs/relaunch.sh            # resume the sweep with the current settings
#   bash logs/relaunch.sh status     # report progress and exit, changing nothing
#   N_TAGS=16 bash logs/relaunch.sh  # resume but cap the panel at 16 checkpoints
#
set -uo pipefail

WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
PY="$WS/.venv_gpu/bin/python"
cd "$WS"

# --- environment -------------------------------------------------------------
# NOTE: HF_HOME / HF_HUB_CACHE / TRANSFORMERS_CACHE / UV_CACHE_DIR / PIP_CACHE_DIR
# are deliberately NOT set here.  They already point at the shared per-run cache
# and overriding them stores every weight twice (see deviation D01).
export TORCH_DISABLE_NATIVE_JIT=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
export TOKENIZERS_PARALLELISM=false
export HF_HUB_DISABLE_TELEMETRY=1

N_TAGS="${N_TAGS:-16}"
R_DRAWS_P="${R_DRAWS_P:-5}"

status() {
  echo "=== chain ==="
  python3 src/hygiene_check.py chain || true
  echo "=== generation ==="
  echo "  gens done : $(ls private/gens/*.GEN_DONE 2>/dev/null | wc -l)"
  echo "  judged    : $(ls private/gens/*.JUDGED  2>/dev/null | wc -l)"
  echo "=== graded_truth commits ==="
  ls -1 results/graded_truth_s*.json 2>/dev/null || echo "  (none yet)"
  echo "=== harvest ==="
  echo "  arrays DONE: $(ls arrays/*/DONE 2>/dev/null | wc -l)"
  echo "=== spend ==="
  if [ -f results/judge_cost_ledger.jsonl ]; then
    python3 -c "import json,sys;print('  ledger_usd %.4f' % sum((json.loads(l).get('cost_usd') or json.loads(l).get('cost') or 0) for l in open('results/judge_cost_ledger.jsonl') if l.strip()))"
  else echo "  (no ledger yet)"; fi
  echo "=== disk ==="; df -h /ai-inventor/aii_data | tail -1
}

if [ "${1:-}" = "status" ]; then status; exit 0; fi

if [ ! -x "$PY" ]; then
  echo "FATAL: $PY missing. Rebuild with: bash logs/build_venv.sh" >&2; exit 1
fi

mkdir -p private/gens private/judged results/labels arrays logs

# --- 1. judge watcher, in the background, so judging costs no wall clock ------
if [ -f src/judgeflow.py ]; then
  "$PY" src/judgeflow.py watch --poll 20 --soft-stop-usd 4.5 >> logs/judge_watch.log 2>&1 &
  JUDGE_PID=$!
  echo "judge watcher pid=$JUDGE_PID"
  trap 'kill "$JUDGE_PID" 2>/dev/null || true' EXIT
else
  echo "WARN: src/judgeflow.py absent; skipping judge watcher" >&2
  JUDGE_PID=""
fi

# --- 2. generation sweep (skips tags that already have GEN_DONE) --------------
"$PY" src/pipeline.py gen --from-sweep "$N_TAGS" 2>&1 | tee -a logs/gen_sweep.log
GEN_RC=${PIPESTATUS[0]}
echo "gen sweep rc=$GEN_RC"

# --- 3. wait for judging to drain, then commit the order gate ----------------
if [ -n "$JUDGE_PID" ]; then
  for _ in $(seq 1 60); do
    n_done=$(ls private/gens/*.GEN_DONE 2>/dev/null | wc -l)
    n_jud=$(ls private/gens/*.JUDGED 2>/dev/null | wc -l)
    [ "$n_jud" -ge "$n_done" ] && break
    sleep 20
  done
  kill "$JUDGE_PID" 2>/dev/null || true
fi

STAGE=$(ls -1 results/graded_truth_s*.json 2>/dev/null | wc -l)
"$PY" src/judgeflow.py commit --stage "$STAGE" 2>&1 | tee -a logs/commit.log

# --- 4. harvest + interventions (the order gate refuses ungated tags) --------
"$PY" src/pipeline.py harvest --from-sweep "$N_TAGS" --tier2 --r-draws-p "$R_DRAWS_P" \
      2>&1 | tee -a logs/harvest_sweep.log

# --- 5. diagnostics, lint, chain ---------------------------------------------
"$PY" src/rates.py diagnostics 2>&1 | tail -20
python3 src/hygiene_check.py all
status
