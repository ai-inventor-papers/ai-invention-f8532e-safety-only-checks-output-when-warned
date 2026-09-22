"""Direct check of an inherited claim: does the community abliteration touch embed_tokens?

Iteration 1 Lane B's stage-9 weight check recorded the note

    "mlabonne DOES edit embed_tokens. Qwen3-4B has tie_word_embeddings=True, so that edit
     also removes the direction from the UNEMBED."

That note was load-bearing: it was used to argue a logit-side outcome could be contaminated
by the edit.  This module re-reads both checkpoints' tensors directly and reports the exact
Frobenius norm of the difference, for every pair in the panel.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import RESULTS, jdump, setup_logging  # noqa: E402
from loguru import logger  # noqa: E402
from panel import PAIRS  # noqa: E402
from wsummary import get, open_repo  # noqa: E402


def check(parent: str, child: str) -> dict:
    ph, pw, _ = open_repo(parent)
    ch, cw, _ = open_repo(child)
    out: dict = {"parent": parent, "child": child,
                 "n_tensors_parent": len(pw), "n_tensors_child": len(cw),
                 "keys_only_in_child": sorted(set(cw) - set(pw))[:10],
                 "keys_only_in_parent": sorted(set(pw) - set(cw))[:10], "tensors": {}}
    for k in sorted(set(pw) & set(cw)):
        if not (k.endswith("embed_tokens.weight") or k.endswith("lm_head.weight")):
            continue
        A, B = get(ph, pw, k), get(ch, cw, k)
        if tuple(A.shape) != tuple(B.shape):
            out["tensors"][k] = {"shape_mismatch": [list(A.shape), list(B.shape)]}
            continue
        D = (B - A).double()
        f2 = float((D * D).sum().item())
        out["tensors"][k] = {"shape": list(A.shape), "fro2_delta": f2,
                             "bitwise_identical": bool(f2 == 0.0),
                             "fro_parent": float(A.double().norm().item())}
    out["embed_or_head_edited"] = any(
        v.get("fro2_delta", 0.0) > 0.0 for v in out["tensors"].values())
    out["tied_embeddings_implied"] = not any(k.endswith("lm_head.weight") for k in pw)
    del ph, ch
    return out


def main() -> int:
    setup_logging("verify_embed")
    res = {}
    for p in PAIRS:
        try:
            r = check(p["parent"], p["child"])
            res[p["pair"]] = r
            logger.info(f"{p['pair']}: embed/head edited = {r['embed_or_head_edited']} "
                        f"(tied={r['tied_embeddings_implied']}) {list(r['tensors'])}")
        except Exception as exc:  # noqa: BLE001
            res[p["pair"]] = {"error": repr(exc)}
            logger.warning(f"{p['pair']}: {exc}")
    res["_inherited_claim_under_test"] = (
        "Iteration 1 Lane B recorded 'mlabonne DOES edit embed_tokens ... so that edit also "
        "removes the direction from the UNEMBED'. This module tests that claim directly.")
    jdump(res, RESULTS / "embed_tokens_check.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
