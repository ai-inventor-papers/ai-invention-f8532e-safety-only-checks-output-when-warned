#!/usr/bin/env python3
"""Canonical read-only paths into iteration 1's three lanes, and this artifact's own tree.

Lane workspaces are READ-ONLY. Nothing in this module may open a lane path for writing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent

RESULTS = WORKSPACE / "results"
LOGS = WORKSPACE / "logs"
SCRATCH = WORKSPACE / "scratch"
COPIED = WORKSPACE / "copied_inputs"

ITER1 = Path(
    "/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art"
)
LANE_A = ITER1 / "gen_art_experiment_1"
LANE_B = ITER1 / "gen_art_experiment_2"
LANE_C = ITER1 / "gen_art_experiment_3"

LANE_OF = {"A": LANE_A, "B": LANE_B, "C": LANE_C}

# ---- Lane A -----------------------------------------------------------------
A_METHOD_OUT = LANE_A / "out" / "method_out.json"
A_SUMMARY = LANE_A / "out" / "SUMMARY.md"
A_PREREG = LANE_A / "work" / "prereg.json"
A_RELEASED = LANE_A / "out" / "released"
A_COS_CONTENT_ABLIT = A_RELEASED / "cos_content_ablit.json"
A_CROSS_CKPT = A_RELEASED / "cross_checkpoint_directions.json"
A_PER_ITEM_CELLS = A_RELEASED / "per_item_cell_projections.csv"
A_DIRECTIONS = A_RELEASED / "directions"
A_SUBSTRATE_PY = LANE_A / "lane_a" / "substrate.py"

# ---- Lane B -----------------------------------------------------------------
B_METHOD_OUT = LANE_B / "method_out.json"
B_ANALYSIS = LANE_B / "out" / "analysis.json"
B_PREREG = LANE_B / "out" / "prereg.json"
B_HARVEST = LANE_B / "out" / "harvest"
B_CAUSAL = LANE_B / "out" / "causal"
B_RELEASED_DIRS = LANE_B / "out" / "released_directions"
B_LOGS = LANE_B / "logs"
B_FOLLOWUP_SH = LANE_B / "followup.sh"
B_STAGE9_WEIGHT = LANE_B / "out" / "stage9_weightcheck.json"
B_STAGE9_DEPTH = LANE_B / "out" / "stage9_depth.json"
B_PILOT_DIRS = LANE_B / "out" / "pilot_dirs.npz"
B_MLABONNE_U1 = LANE_B / "out" / "mlabonne_u1_pooled.npy"

B_LINEAGE_REPO = {
    "L1": "Qwen/Qwen3-4B-Base",
    "L2": "Qwen/Qwen3-4B",
    "L3": "Qwen/Qwen3-4B-SafeRL",
    "L4": "CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6",
}
B_ALPHAS = ["0.00", "0.25", "0.50", "0.75", "1.00"]

# ---- Lane C -----------------------------------------------------------------
C_METHOD_OUT = LANE_C / "method_out.json"
C_PREREG = LANE_C / "prereg.json"
C_PER_CKPT = LANE_C / "results" / "per_ckpt"
C_SEALED = LANE_C / "results" / "sealed"
C_JUDGED = LANE_C / "results" / "judged"
C_GENS = LANE_C / "results" / "gens"
C_S3 = LANE_C / "results" / "s3" / "s3_results.json"

# ---- iteration-1 dataset artifact (the registered STIMULUS gates live here) ----
LANE_D = ITER1 / "gen_art_dataset_1"
D_PREREG = LANE_D / "prereg.json"
D_JUDGE_VALIDATION = LANE_D / "judge_validation.json"
D_VERIFICATION = LANE_D / "verification_report.json"


def rel(path: Path | str) -> str:
    """Render an absolute lane path in the short LANE_X/... form used in tables."""
    p = str(path)
    for name, root in (("LANE_A", LANE_A), ("LANE_B", LANE_B),
                       ("LANE_C", LANE_C), ("DATASET", LANE_D)):
        if p.startswith(str(root)):
            return name + p[len(str(root)) :]
    return p


def sha256_file(path: Path, *, chunk: int = 1 << 20) -> str:
    """Streamed SHA-256 so multi-GB npz archives never enter memory whole."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
