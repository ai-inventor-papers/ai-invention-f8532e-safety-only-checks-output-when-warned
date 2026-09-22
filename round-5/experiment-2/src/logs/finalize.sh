#!/usr/bin/env bash
# STAGE G -- finalize. Idempotent: safe to run more than once.
#
#   bash logs/finalize.sh            # full wrap, DELETES private/
#   bash logs/finalize.sh --keep     # everything except the private/ deletion (dry wrap)
#
# Order matters: stop the drivers so nothing writes while we hash, then rebuild the manifest
# with per-file sha256, recompute the instrument diagnostics and the design arithmetic, write
# the per-tag join contracts, classify the in-house arms, THEN delete private/ (raw completions
# on harmful prompts + edited weights), then lint/verify and assemble the outputs.
set -uo pipefail
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
PY="$WS/.venv_gpu/bin/python"
KEEP_PRIVATE=0
[ "${1:-}" = "--keep" ] && KEEP_PRIVATE=1
export TORCH_DISABLE_NATIVE_JIT=1 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 \
       TOKENIZERS_PARALLELISM=false HF_HUB_DISABLE_TELEMETRY=1

say() { echo; echo "=== $* ==="; }

say "1. stop the drivers (PID-based; never by name -- other runs share this pod)"
for f in gen_supervisor gen_sweep orchestrate partb_run judge_watch selftest progress; do
  p=$(cat "logs/$f.pid" 2>/dev/null || true)
  if [ -n "${p:-}" ] && kill -0 "$p" 2>/dev/null; then kill "$p" 2>/dev/null && echo "  stopped $f ($p)"; fi
done
pkill -P $$ sleep 2>/dev/null || true
sleep 5
# Any harvest/gen CHILD still running would keep writing while we hash, so wait for the venv
# interpreter to be gone. The bracket in the pattern stops pgrep matching its own cmdline.
for i in $(seq 1 30); do
  busy=$(pgrep -f 'venv_gpu/bin/pytho[n]' 2>/dev/null | wc -l)
  [ "${busy:-0}" -eq 0 ] && { echo "  no pipeline children running"; break; }
  echo "  waiting for $busy pipeline child(ren) to finish ($i/30)"; sleep 10
done

say "2. Part-B classification (paired bootstrap, B=2000, seed 20260921)"
"$PY" src/partb.py classify 2>&1 | tail -6 || echo "  (classify reported a problem; see logs/partb_classify.log)"

say "3. per-tag JOIN CONTRACT"
python3 src/join_readme.py

say "4. panel manifest with per-file sha256"
python3 src/manifest.py rebuild 2>&1 | tail -25

say "4b. AMS baseline instrument (CPU, from each tag's A_ams.npy)"
"$PY" src/ams_recompute.py 2>&1 | tail -24

say "4c. re-verify every array manifest (re-hash of every listed file)"
python3 src/verify_manifests.py 2>&1 | tail -8

say "5. instrument diagnostics + design arithmetic (MDE)"
"$PY" src/rates.py all 2>&1 | tail -8          # diagnostics THEN mde (design arithmetic)

say "6. hygiene: assert nothing released carries raw harmful text, then delete private/"
python3 - <<'PYEOF'
import json, pathlib, sys
leak = {"completion", "generation", "response", "response_text", "raw_completion", "output_text"}
bad = []
for root in ("results", "arrays"):
    for p in pathlib.Path(root).rglob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        stack = [d]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                for k, v in o.items():
                    if str(k).lower() in leak and isinstance(v, str) and len(v) > 40:
                        bad.append(f"{p}::{k}")
                    stack.append(v)
            elif isinstance(o, list):
                stack.extend(o[:200])
print(f"  raw-text suspects in results/ + arrays/: {len(set(bad))}")
for b in sorted(set(bad))[:10]:
    print("   ", b)
sys.exit(1 if bad else 0)
PYEOF
RAW=$?
if [ "$KEEP_PRIVATE" = "1" ]; then
  echo "  --keep: private/ NOT deleted"
elif [ "$RAW" != "0" ]; then
  echo "  REFUSING to delete private/: released files still reference raw text (fix first)"
else
  du -sh private 2>/dev/null
  rm -rf private && echo "  private/ deleted (raw completions on harmful prompts + edited weights)"
fi
# WS/hf_cache is never created: HF_HOME points at the run's shared cache (deviation D01).
# Snapshots are deleted after each checkpoint's visit instead.
rm -rf src/__pycache__ hf_cache harvest 2>/dev/null || true

say "7. blindness lint + hash chain + order-gate audit"
python3 src/hygiene_check.py all
LINT=$?

say "8. method_out.json + mini/preview + README"
python3 src/build_method_out.py
python3 /ai-inventor/.claude/skills/aii-json/scripts/aii_json_format_mini_preview.py \
        --format exp_gen_sol_out --input method_out.json 2>&1 | tail -4
python3 /ai-inventor/.claude/skills/aii-json/scripts/aii_json_validate_schema.py \
        --format exp_gen_sol_out --file method_out.json 2>&1 | tail -3
python3 src/readme_results.py

say "9. sizes (100 MB output limit) and the heavy-path manifest"
ls -lh method_out.json full_method_out.json mini_method_out.json preview_method_out.json
du -sh arrays results logs src .venv_gpu 2>/dev/null
cat .aii/manifest.yaml

say "DONE  lint_rc=$LINT"
bash logs/relaunch.sh status
