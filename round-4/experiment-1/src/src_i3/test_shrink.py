"""Equivalence test: greedy_shrink vs model.generate(do_sample=False) on 8 items (4 harm, 4 benign)."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import torch
from common import ASSETS, RESULTS, jdump, jload, utc_now
import gen as G
torch.set_num_threads(1)
repo = sys.argv[1] if len(sys.argv) > 1 else "Vikhrmodels/Vikhr-Llama-3.2-1B-Instruct"
MAXN = int(sys.argv[2]) if len(sys.argv) > 2 else 48
items = jload(ASSETS / "behaviour_items.json")["items"]
pick = items[:4] + items[45:49]
model, tok, _ = G.load(repo, G.download(repo))
tok.padding_side = "left"
texts = [G.chat_text(tok, x["prompt"]) for x in pick]
enc = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=G.MAX_LEN, add_special_tokens=False)
P = enc["input_ids"].shape[1]
with torch.no_grad():
    t0 = time.time(); a = model.generate(**enc, max_new_tokens=MAXN, do_sample=False, pad_token_id=tok.pad_token_id)[:, P:]; ta = time.time() - t0
    t0 = time.time(); b, st = G.greedy_shrink(model, enc, MAXN, G._eos_ids(model, tok), tok.pad_token_id); tb = time.time() - t0
same_rows = [bool(torch.equal(a[i], b[i])) for i in range(len(pick))]
res = {"repo": repo, "max_new": MAXN, "n": len(pick), "identical_rows": sum(same_rows), "per_row": same_rows,
       "t_hf_generate_s": ta, "t_shrink_s": tb, "utc": utc_now(),
       "first_diff": [int((a[i] != b[i]).nonzero()[0]) if not same_rows[i] else None for i in range(len(pick))]}
jdump(res, RESULTS / "shrink_equivalence_test.json")
print(json.dumps(res))
