"""Plumbing test of the iteration-4-only inputs on a SYNTHETIC copy (symlinks) of one I3 harvest.
D_dec = A_prompt rows of the n9 subset + noise (NOT real generations); perturbations = A_prompt + noise / exact copy."""
import sys, json, os, shutil
sys.path.insert(0, 'src')
from pathlib import Path
import numpy as np
import score
I3 = Path('/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1/harvest')
src_tag = 'unsloth--Llama-3.2-1B-Instruct'
root = Path('results/test_scoring/synth_harvest'); shutil.rmtree(root, ignore_errors=True)
t = root / 'SYNTH--llama'; t.mkdir(parents=True)
for f in (I3 / src_tag).iterdir():
    os.symlink(f.resolve(), t / f.name)
A = np.load(t / 'A_prompt.npy')
rng = np.random.default_rng(0)
sub = json.load(open('assets/prereg_subsets.json'))['n9_subset_stim_idx']
D = np.repeat(A[sub][:, None], 8, 1).astype(np.float32) + rng.standard_normal((32, 8) + A.shape[1:]).astype(np.float32) * 0.5
np.save(t / 'D_dec.npy', D.astype(np.float16))
nv = [8] * 32; nv[3] = 0; nv[20] = 2
json.dump({'n_valid': nv}, open(t / 'dec_meta.json', 'w'))
Ap = (A.astype(np.float32) + rng.standard_normal(A.shape).astype(np.float32) * 0.05).astype(np.float16)
np.save(t / 'A_prompt_notemplate.npy', Ap)
for r in ('r_refusal', 'r_control'):
    x = np.load(t / f'{r}.npy'); np.save(t / f'{r}_notemplate.npy', x + rng.standard_normal(x.shape).astype(x.dtype) * 0.1)
v = root / 'SYNTH--llama__NOOP_fp32'; v.mkdir()
for n in ('A_prompt.npy', 'r_refusal.npy', 'r_control.npy', 'r_hedge.npy', 'meta.json', 'WU_ref.npy', 'WU_ctl.npy', 'WU_hed.npy', 'gamma.npy', 'A_c11.npy', 'DONE', 'norms.npy'):
    os.symlink((I3 / src_tag / n).resolve(), v / n)
json.dump({'rate_primary': 0.25, 'rate_companion': 0.3125}, open(t / 'greedy_refusal.json', 'w'))
json.dump({'REGEX': 0, 'REGEX_NAMEFREE': 0}, open(t / 'card_regex.json', 'w'))
json.dump({'overall': 0.42, 'per_concept': {}}, open(t / 'ams_reimpl.json', 'w'))
out = Path('results/test_scoring/synth_scores')
r = score.score_tag('SYNTH--llama', root=root, out_dir=out)
rv = score.score_tag('SYNTH--llama__NOOP_fp32', root=root, out_dir=out)
p = score.paired_change('SYNTH--llama', 'SYNTH--llama__NOOP_fp32', 'SYNTH_noop_fp32', 'noop', n_boot=200, root=root, scores_dir=out, out_dir=out)
rep = {'values': r['values'], 'status_not_ok': {k: s for k, s in r['status'].items() if s != 'OK'}, 'n5_used': r['n5_perturbations_used'],
       'n5_detail': r['n5_detail'], 'kcurve_N9': r['kcurve'].get('N9'), 'null_N9': r['null'].get('N9'), 'n9': r['n9'],
       'variant_status_not_ok': {k: s for k, s in rv['status'].items() if s != 'OK'}, 'variant_notes': rv['notes'],
       'pair_N1': p['rows']['N1'], 'pair_N9': p['rows']['N9'], 'pair_B7': p['rows']['B7']}
json.dump(rep, open('results/test_scoring/test_synth.json', 'w'), indent=1, default=str)
print(json.dumps(rep, indent=1, default=str)[:6000])
