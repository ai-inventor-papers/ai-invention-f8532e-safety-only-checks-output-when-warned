#!/bin/bash
# usage: wait_log.sh <file> <pattern> <timeout_s>
f=$1; pat=$2; to=${3:-240}; t=0
n0=$(grep -c "$pat" "$f" 2>/dev/null || echo 0)
until [ "$(grep -c "$pat" "$f" 2>/dev/null || echo 0)" -gt "$n0" ] || [ $t -ge $to ]; do sleep 5; t=$((t+5)); done
tail -3 "$f"
