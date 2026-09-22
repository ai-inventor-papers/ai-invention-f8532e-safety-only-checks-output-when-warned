#!/usr/bin/env bash
WS=/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_2
cd "$WS"
while true; do
  G=$(ls private/gens/HG__*.GEN_DONE 2>/dev/null | wc -l)
  J=$(ls private/gens/*.JUDGED 2>/dev/null | wc -l)
  A=$(ls arrays/*/DONE 2>/dev/null | wc -l)
  PB=$(ls private/partb/*/COMMIT_DONE 2>/dev/null | wc -l)
  PBH=$(ls private/partb/*/HARVEST_DONE 2>/dev/null | wc -l)
  C=$(wc -l < logs/chain.jsonl)
  USD=$(python3 -c "import json;print('%.3f'%sum((json.loads(l).get('cost_usd') or 0) for l in open('results/judge_cost_ledger.jsonl') if l.strip()))" 2>/dev/null || echo NA)
  echo "$(date -u +%H:%M) gen=$G/20 judged=$J arrays=$A pb_commit=$PB pb_harvest=$PBH chain=$C usd=$USD" >> logs/progress.log
  sleep 120
done
