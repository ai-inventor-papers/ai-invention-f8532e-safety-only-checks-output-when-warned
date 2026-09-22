#!/bin/bash
# wait until <file> has more than <n0> lines matching <pat>, up to <to> seconds
f=$1; pat=$2; n0=$3; to=$4; t=0
while true; do
  n=$(grep -c -- "$pat" "$f" 2>/dev/null); n=${n:-0}
  if [ "$n" -gt "$n0" ] || [ "$t" -ge "$to" ]; then break; fi
  sleep 5; t=$((t+5))
done
tail -2 "$f"
