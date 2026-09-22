import sys, time, json
sys.path.insert(0, 'src')
from pathlib import Path
import score
I3 = Path('/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1')
r = score.paired_change('unsloth--Llama-3.2-1B-Instruct', 'mylesgoose--Llama-3.2-1B-Instruct-abliterated2', 'TEST_llama_abl2', 'edited',
                        n_boot=1000, root=I3/'harvest', scores_dir=Path('results/test_scoring/scores'), out_dir=Path('results/test_scoring/pairs'))
for k in ['N1','N2','N3','N6','N7','N8','N11','C7','C13_peak_d','BL1_easy','BL1_hard','BL1_truelogit','B7','B7_proj','N9','GREEDY_REFUSAL']:
    x = r['rows'][k]; print(k, x['a'], x['b'], x['delta'], x.get('ci95'), x.get('covers0'), x['method'], x['abs_delta_over_null_sd'])
print(r['timing'], r['elapsed_s'])
