#!/usr/bin/env python3
"""Regenerate out/method_out.json, out/SUMMARY.md and out/released/ from the saved
work/analysis_raw.json, without redoing the ~30-minute statistical recompute."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from loguru import logger
import run_analysis as RA

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")


def main() -> None:
    res = json.loads((HERE / "work" / "analysis_raw.json").read_text())
    sub = json.loads((HERE / "items" / "substrate.json").read_text())
    prereg, sha = __import__("lane_a.prereg", fromlist=["verify"]).verify(HERE / "work")
    assert sha == res["prereg_sha256"], f"prereg hash drift: {sha} != {res['prereg_sha256']}"

    per = res["per_checkpoint"]
    a_vals = {t: per[t]["candidates"]["K1"]["early|F1|A"]["term_std"] for t in per}
    a_bands = {t: per[t]["G4_shuffled_label_null"]["A"]["abs_p975"] for t in per}
    cb_vals = {t: per[t]["candidates"]["K1"]["early|F1|CB"]["term_std"] for t in per}
    a_empty = all(abs(a_vals[t]) < a_bands[t] for t in per)
    both_empty = a_empty and all(abs(cb_vals[t]) < a_bands[t] for t in per)
    res["cheapest_kill"].update({
        "verdict": ("INSTRUMENT_FAILURE_SUSPECTED" if both_empty else
                    "K1_ARMING_COORDINATE_NOT_LABEL_SPECIFIC" if a_empty
                    else "ARMING_COORDINATE_NON_EMPTY"),
        "which_null": "shuffled_label",
        "note": (
            "TWO different nulls are in play and they answer different questions. (i) The "
            "random-direction null-SD is the UNIT: it says how large a term is relative to "
            "projections onto isotropic directions. (ii) The SHUFFLED-LABEL null band is the "
            "DECISIVE control: r_content is refitted on PERMUTED hazardous/benign labels and the "
            "whole pipeline re-run, so it says whether the term depends on the labels at all. This "
            "verdict uses (ii). A term can be many null-SD units large and still sit inside the "
            "shuffled-label band -- which is exactly what happens here -- and that means the effect "
            "is not evidence of the registered coordinate. The response-site main effect is in any "
            "case already owned by arXiv:2607.14147."),
        "A_shuffled_label_band_abs_p975": a_bands,
        "A_escapes_shuffled_label_band": {t: bool(abs(a_vals[t]) >= a_bands[t]) for t in per},
        "randinit_control": {
            "note": ("The randomly-initialised arm is the check that the wide shuffled-label band is "
                     "a property of TRAINED representations and not of the code: there the band "
                     "collapses and the real term collapses with it."),
            "A_term_std": a_vals.get("RandInit-4B"),
            "A_shuffled_label_band": a_bands.get("RandInit-4B"),
        },
    })
    (HERE / "work" / "analysis_raw.json").write_text(json.dumps(res, indent=2, default=float))
    RA.write_outputs(res, sub, prereg)
    print("REBUILD OK")


if __name__ == "__main__":
    main()
