import numpy as np, json, glob, os
B="/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_2"
for f in ["out/harvest/L2_a0.00.part001.npz","out/harvest/L2_dirs.npz","out/released_directions/L2_r_ablit.npz","out/pilot_dirs.npz"]:
    p=os.path.join(B,f)
    if not os.path.exists(p): print("ABSENT",f); continue
    try:
        z=np.load(p,allow_pickle=True)
        print("==",f, os.path.getsize(p))
        for k in z.files: 
            a=z[k]; print("   ",k,a.shape,a.dtype)
    except Exception as e: print("ERR",f,repr(e))
print("== L2_meta.json =="); 
m=json.load(open(os.path.join(B,"out/harvest/L2_meta.json"))) if os.path.exists(os.path.join(B,"out/harvest/L2_meta.json")) else None
print(json.dumps(m,indent=1)[:3000] if m else glob.glob(B+"/out/harvest/*meta*"))
