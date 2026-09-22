#!/usr/bin/env bash
# After the main weight-summary pass ends: (1) the random-init arm's weight summary, (2) retry any
# weight summary that failed (e.g. the quanto-FP8 venkycs child, now dequantised), (3) the S2
# fingerprint, which failed on the same checkpoint. Sequential and memory-light.
cd "$(dirname "$0")"
WP=$(cat logs/wsum.pid 2>/dev/null)
echo "[w] $(date +%T) waiting for weight-summary pid $WP"
while [ -n "$WP" ] && kill -0 "$WP" 2>/dev/null; do sleep 20; done
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONUNBUFFERED=1
echo "[w] $(date +%T) random-init weight summary"
.venv/bin/python -u src/randinit_wsummary.py --tag RandInit-Qwen3-0.6B --repo Qwen/Qwen3-0.6B \
  > logs/randinit_wsum.log 2>&1
echo "[w] $(date +%T) retry failed weight summaries"
FAILED=$(.venv/bin/python -c "import json;print(' '.join(sorted({f['repo'] for f in json.load(open('results/wsummary_failures.json'))})))" 2>/dev/null)
if [ -n "$FAILED" ]; then
  .venv/bin/python -c "import json;json.dump([],open('results/wsummary_failures.json','w'))"
  .venv/bin/python -u src/wsummary.py --deadline-min 60 --repos $FAILED > logs/wsum_retry.log 2>&1
fi
echo "[w] $(date +%T) S2 fingerprint retry"
.venv/bin/python - <<'EOF'
import json
p = "results/weight_fingerprints.json"
d = json.load(open(p))
if "S2" in d and d["S2"].get("error"):
    d.pop("S2"); json.dump(d, open(p, "w"), indent=1); print("removed failed S2 entry for retry")
EOF
.venv/bin/python -u src/weightfp.py --pairs S2 --deadline-min 30 --need-gb 2.0 > logs/weightfp_s2.log 2>&1
echo "[w] $(date +%T) done"
