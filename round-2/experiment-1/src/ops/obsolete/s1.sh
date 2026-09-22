#!/usr/bin/env bash
cd "$(dirname "$0")"
H=$(ls harvest/*/DONE 2>/dev/null|wc -l); W=$(ls harvest/*/W_DONE 2>/dev/null|wc -l)
F=$(.venv/bin/python -c "import json;print(len(json.load(open('results/weight_fingerprints.json'))))" 2>/dev/null||echo 0)
A=$(.venv/bin/python -c "import sys;sys.path.insert(0,'src')
from aii_common import cgroup_mem_limit_bytes as L,cgroup_mem_used_bytes as U,human_bytes as h
print(h(L()-U()))" 2>/dev/null||echo "?")
LAST=$(tr '\r' '\n' < logs/sweep.log 2>/dev/null | grep -aE "\] HARVEST |P-harvest|HARVESTED" | tail -2 | sed 's/.*INFO *| *//;s/^ *//' | tr '\n' ' | ')
echo "$(date +%H:%M:%S) load=$(cut -d' ' -f1 /proc/loadavg) free=$A harvested=$H wsum=$W fp=$F"
echo "   $LAST"
