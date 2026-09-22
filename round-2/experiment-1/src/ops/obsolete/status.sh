#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "=== $(date +%H:%M:%S)  load $(cut -d' ' -f1-3 /proc/loadavg) ==="
printf "harvested (%s): " "$(ls harvest/*/DONE 2>/dev/null|wc -l)"
ls harvest/*/DONE 2>/dev/null | sed 's|harvest/||;s|/DONE||' | tr '\n' ' '; echo
printf "w-summary (%s): " "$(ls harvest/*/W_DONE 2>/dev/null|wc -l)"
ls harvest/*/W_DONE 2>/dev/null | sed 's|harvest/||;s|/W_DONE||' | tr '\n' ' '; echo
for f in sweep wsum weightfp judge_chain; do
  P=$(cat logs/$f.pid 2>/dev/null)
  printf "%-11s " "$f"
  if [ -n "$P" ] && kill -0 "$P" 2>/dev/null; then ps -o pcpu=,etime= -p "$P"; else echo "ended/na"; fi
done
echo "--- last lines ---"
tr '\r' '\n' < logs/sweep.log 2>/dev/null | grep -aE "P-harvest|HARVESTED|FAILED" | tail -2
grep -a "W-SUMMARY\|FAILED" logs/wsum.log 2>/dev/null | tail -1
grep -a "stratum=\|fingerprint\|FAILED" logs/weightfp.log 2>/dev/null | tail -2
