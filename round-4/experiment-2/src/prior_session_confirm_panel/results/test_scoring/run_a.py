import sys, time, json
sys.path.insert(0, 'src')
from pathlib import Path
import score
I3 = Path('/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1')
out = Path('results/test_scoring/scores')
tags = sys.argv[1:]
F = json.load(open(I3/'results/features.json'))['features']
rep = {}
for t in tags:
    r = score.score_tag(t, root=I3/'harvest', out_dir=out)
    f = F[t.replace('--', '/', 1)]
    v = r['values']
    cmp = {k: (v[k2], f[k], (v[k2] - f[k]) if v[k2] is not None else None) for k2, k in
           [('C7','C7'),('C13_peak_d','C13_peak_d'),('BL1_easy','BL1'),('B3','B3'),('B7','B7'),('BL1_hard','BL1_hard'),('N8','C11')]}
    rep[t] = {'cmp_vs_features_json': cmp, 'N1': v['N1'], 'N2': v['N2'], 'null_N1': r['null']['N1'],
              'N1_null_mean_over_sd': r['null']['N1']['mean']/r['null']['N1']['sd'],
              'consistency': r['consistency_engine_minus_verbatim'], 'elapsed_s': r['elapsed_s'], 'timing': r['timing'],
              'status_not_ok': {k: s for k, s in r['status'].items() if s != 'OK'}, 'l_star': r['l_star'], 'l_star_cf': r['l_star_cf'],
              'B7_proj': v['B7_proj'], 'norm': r['norm_info']}
    print(json.dumps(rep[t], indent=1, default=str))
json.dump(rep, open(f'results/test_scoring/test_a_{"_".join(t[:12] for t in tags)}.json', 'w'), indent=1, default=str)
