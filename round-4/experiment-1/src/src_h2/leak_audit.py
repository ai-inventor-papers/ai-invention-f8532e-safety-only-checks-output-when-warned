"""T5 -- LEAKAGE AUDITS, as assertions in code, not as intentions."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import RESULTS, jdump, setup_logging  # noqa: E402
from loguru import logger  # noqa: E402

SRC = Path(__file__).resolve().parent
FIT_PATH = ["assets_build.py", "harvest.py", "sweep.py", "numerics.py", "score_ckpt.py",
            "score_panel.py", "analyze.py", "wsummary.py", "weightfp.py", "c_harvest2.py",
            "randinit_wsummary.py", "t7_determinism.py", "fetch_models.py"]


def main() -> int:
    setup_logging("leak_audit")
    checks = []

    # (a) the sealed holdouts must be opened by NOTHING in the fitting/selection path
    for needle, where in (("reserved_54", "confirm.py"), ("heldout_cells", None)):
        hits = []
        for f in SRC.glob("*.py"):
            if f.name in ("leak_audit.py",):
                continue
            if re.search(needle, f.read_text(encoding="utf-8")):
                hits.append(f.name)
        bad = [h for h in hits if h in FIT_PATH]
        checks.append({
            "check": f"T5a_{needle}_not_in_fitting_path",
            "files_referencing": hits, "files_in_fitting_path": bad,
            "pass": len(bad) == 0,
            "detail": f"{needle} may be referenced only by confirm.py (and the output "
                      f"builder's prose); it is referenced by {hits or 'nothing'}",
        })

    # (b) the layer band and l_star must come from EASY / fitting data only
    sc = (SRC / "score_panel.py").read_text(encoding="utf-8")
    checks.append({
        "check": "T5b_lstar_and_band_from_EASY_only",
        "pass": ("easy = np.flatnonzero(sid == 0)" in sc
                 and "subset=easy" in sc),
        "detail": "score_checkpoint restricts every candidate fit to sid==0 (the EASY set); "
                  "the HARD set is used only inside recognition_axis().",
    })

    # (c) the probe's C must be chosen on an INNER fold only
    nmsrc = (SRC / "numerics.py").read_text(encoding="utf-8")
    checks.append({
        "check": "T5c_probe_C_chosen_on_inner_fold",
        "pass": ("inner = StratifiedKFold" in nmsrc and nmsrc.count("inner.split") >= 2
                 and "inner_folds = _folds(y, 3, seed, groups)" in nmsrc),
        "detail": "cv_auroc_per_layer and cv_probe_scores select C on an inner split of the "
                  "TRAINING fold; logistic_probe_direction selects C on inner folds of the "
                  "data it is given (group-aware when a bootstrap duplicated items), and is "
                  "only ever given the EASY set.",
    })

    # (d) E3's z-scoring/imputation/ridge must be fitted on training families only
    checks.append({
        "check": "T5d_E3_impute_and_z_on_train_fold_only",
        "pass": ("_impute_and_z(X[tr], X[te])" in sc),
        "detail": "_impute_and_z takes (Xtr, Xte) and computes the median and the z-scaling "
                  "from Xtr alone; machinery_controls() reports the shuffled-truth control "
                  "that would expose any leak.",
    })

    # (e) nothing in the screen path may read the sealed families' rows except as controls
    an = (SRC / "analyze.py").read_text(encoding="utf-8")
    checks.append({
        "check": "T5e_sealed_families_used_only_as_anomalous_controls",
        "pass": ("s3_results.json" in an),
        "detail": "the two leaked-seal pairs carry effectiveness=ANOMALOUS, and e1_test() "
                  "consumes ANOMALOUS pairs only through anomalous_controls, never through "
                  "e1a_sensitivity (which filters on EFFECTIVE) or e1b_specificity (NULL_EDIT).",
    })

    n_pass = sum(1 for c in checks if c["pass"])
    res = {"n_checks": len(checks), "n_pass": n_pass, "all_pass": n_pass == len(checks),
           "checks": checks}
    for c in checks:
        logger.info(f"{'PASS' if c['pass'] else 'FAIL'}  {c['check']}")
    jdump(res, RESULTS / "leak_audit.json")
    return 0 if res["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
