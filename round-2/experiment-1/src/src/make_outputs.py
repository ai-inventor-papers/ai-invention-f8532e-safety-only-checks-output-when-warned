"""Build out/method_out.json (exp_gen_sol_out), out/SUMMARY.md and out/released/.

FRAMING RULE (handbook rule a): the summary is written as ONE mechanistic question --
is the axis that separates a base model, its safety-tuned child and its abliterated child
RECOGNITION or EXECUTION -- and never as a leaderboard of readouts.  The candidate table
is the instrument; the mechanism is the result.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aii_common import (  # noqa: E402
    ASSETS, HARVEST, LANE_C, RELEASED, RESULTS, OUT, WS, clean_float, jdump, jload,
    jload_maybe, sha256_file, setup_logging, slug,
)
from loguru import logger  # noqa: E402
import numerics as nm  # noqa: E402
from panel import DROPPED_PAIRS, lane_c_slug  # noqa: E402
import score_panel as sp  # noqa: E402

S = lambda x: "" if x is None else (f"{x:.6g}" if isinstance(x, (int, float)) else str(x))  # noqa: E731


def _isfin(x: Any) -> bool:
    """True for a finite real number; False for None (a JSON-sanitised NaN), bools, text."""
    if x is None or isinstance(x, bool):
        return False
    try:
        return bool(np.isfinite(float(x)))
    except (TypeError, ValueError):
        return False


def fmt(x: Any, nd: int = 4) -> str:
    v = clean_float(x)
    return "n/a" if v is None else f"{v:.{nd}f}"


# ----------------------------------------------------------------------------------
# Prior-art verdicts. Two dated passes are folded together and the STRICTER verdict governs
# survivor eligibility:
#   (a) this lane's planning-time search (2026-09-21), and
#   (b) the SAME-ITERATION execution-side research lane
#       iter_2/gen_art/gen_art_research_1/research_out.json (2026-09-21, every source fetched,
#       59+ passages re-verified by an independent live fetch), which screened exactly these
#       candidates and returned 0 OPEN / 2 CLOSED / 5 PARTIAL.
# Source numbers [n] below refer to that research lane's `sources` list.
RESEARCH_LANE = ("iter_2/gen_art/gen_art_research_1/research_out.json "
                 "(same-iteration execution-side prior-art pass, 2026-09-21)")
PRIOR_ART = {
    "X1": {"verdict": "PARTIALLY_SCOOPED",
           "basis": "HPD / HERALD arXiv:2609.13534 [17] extracts a seven-dimensional per-INPUT "
                    "feature record (slope, curvature, monotonicity, onset layer) from the "
                    "cross-layer harm-projection sequence; Geometry-Lite arXiv:2605.20241 [16] "
                    "summarises per-prompt margin profiles over nine backbones; HARC "
                    "arXiv:2607.00572 [31] keeps the per-layer profile heat-map-only.",
           "unclaimed_increment": "a ONE-NUMBER-PER-CHECKPOINT reduction -- peak gap over the "
                                  "gap at the model's OWN earliest 0.95-AUROC layer -- and its "
                                  "behaviour under abliteration. The depth-profile phenomenon "
                                  "is established; only the per-checkpoint scalar is claimed.",
           "source_of_verdict": RESEARCH_LANE,
           "excluded_from_survivor_selection": False},
    "X2": {"verdict": "CLOSED",
           "basis": "The Jorak Model Scanner (github.com/JolanMc/Jorak [7], docs/METRICS.md [8]) "
                    "is a public, documented, reference-free abliteration detector that ships "
                    "X2's exact quantity -- suppression_l = ||r^T W|| / (||r|| ||W||_F) for W in "
                    "{o_proj, down_proj}, per layer, with r taken from the candidate's OWN "
                    "activations -- calibrated cross-model (censored ~0.038 vs abliterated "
                    "~2e-8). X2 = log10(d * ||u^T M||^2 / ||M||_F^2) is a monotone transform "
                    "of the same statistic. CAVEAT: Jorak is a 17-commit, NON-PEER-REVIEWED "
                    "repository validated 4/4 on Qwen2.5-0.5B derivatives; the idea is closed, "
                    "the empirical bar is low. arXiv:2607.01854 [9] is NOT the closer: its "
                    "weight signal is reference-anchored (needs W_base - W_candidate).",
           "unclaimed_increment": "none as an idea. What this lane adds is replication at larger "
                                  "n across several families and edit recipes, scored against a "
                                  "shuffled-label null and a registered decision rule -- "
                                  "replication, not novelty.",
           "source_of_verdict": RESEARCH_LANE,
           "excluded_from_survivor_selection": True},
    "X3": {"verdict": "PARTIALLY_SCOOPED",
           "basis": "arXiv:2604.15557 (Billa) uses the unembedding applied to intermediate "
                    "states as a non-sampling predictor of a steering vector's effect -- the "
                    "closest relative. Logit-Gap Steering arXiv:2506.24056 [14] computes the "
                    "first-decoding-step refusal-vs-affirmative logit gap PER PROMPT over "
                    "pre-identified vocabulary. Sparse Readout Prism arXiv:2609.01936 [15] "
                    "explains logit-lens scores in features; its safety use is future work, so "
                    "it does not close X3. CORRECTION KEPT FROM THIS LANE: arXiv:2406.11717 "
                    "(Arditi et al.) does NOT project the refusal direction through the "
                    "unembedding (it excludes late layers near the unembedding), so that "
                    "attribution was withdrawn.",
           "unclaimed_increment": "an ANALYTIC slope with respect to a continuous harm "
                                  "projection -- the closed-form RMSNorm-Jacobian pullback that "
                                  "makes every null draw free -- and the refusal-versus-safe-"
                                  "completion two-way split.",
           "source_of_verdict": RESEARCH_LANE,
           "excluded_from_survivor_selection": False},
    "X5": {"verdict": "PARTIALLY_SCOOPED",
           "basis": "arXiv:2607.14147 (Kwon, 'Breaking Refusal in the First Half') [13] "
                    "defines and prints the statistic: when a knockout frees probability mass "
                    "off the compliance continuation, the instruct model routes it to refusal "
                    "tokens ~8x more than its base ('concentration 0.24 vs 0.03, App. E') -- "
                    "for ONE instruct model against its own base, n=60, conditional on a causal "
                    "knockout. This lane's planning-time doubt about the number was WRONG and "
                    "is withdrawn; the phrase 'routing concentration' is OUR label, not the "
                    "paper's.",
           "unclaimed_increment": "a position-keyed, parent-free, per-checkpoint "
                                  "HARMFUL-minus-BENIGN-TWIN contrast in residual write "
                                  "concentration, read without any knockout, across pairs.",
           "source_of_verdict": RESEARCH_LANE,
           "excluded_from_survivor_selection": False},
    "X8": {"verdict": "PARTIALLY_SCOOPED",
           "basis": "The readable-before-usable depth LAG is published at least three times "
                    "OFF-CONCEPT: 'Lagged Coupling: Internal Representations Become Readable "
                    "Before They Become Causal' arXiv:2609.01048 [19], 'Encoded Early, Used "
                    "Late' arXiv:2609.07139 [18], 'Encoded but Not Actionable' "
                    "arXiv:2608.17843 [20]. ON-concept, the FRAMING is published: Orgad et al. "
                    "arXiv:2604.09544 [1] show harmful generation is dissociable from harm "
                    "recognition (a double dissociation, graded along an alignment ladder); "
                    "'Knowing without Acting' arXiv:2603.05773 [2] names a Recognition axis "
                    "v_H and an Execution axis v_R; arXiv:2609.14759 [37] argues refusal reads "
                    "only a slice of what the model knows. The nearest multi-model paper never "
                    "quantifies the lag (full-document grep for onset layer / depth-fraction / "
                    "layers apart: 0 matches).",
           "unclaimed_increment": "the lag on the HARM-RECOGNITION -> REFUSAL-DRIVE pathway, "
                                  "normalised by depth into ONE unit-free per-checkpoint "
                                  "scalar, and its behaviour across abliteration pairs. The "
                                  "recognition-versus-execution framing itself is NOT claimed.",
           "source_of_verdict": RESEARCH_LANE,
           "excluded_from_survivor_selection": False},
    "X10": {"verdict": "CLOSED",
            "basis": "The Jorak Model Scanner [7][8] ships X10's idea weights-only and "
                     "inference-free ('NumPy pur, sans inference'): stack each layer's "
                     "least-singular vector into U and take A = sigma_1(U)/||U||_F (censored "
                     "Qwen3-8B A=0.184 ~ floor 0.167 vs Josiefied-Qwen3-8B-abliterated "
                     "A=0.705), plus a bottom-k statistic for multi-direction ablations. It is "
                     "reimplemented here as baseline BL7_JORAK_A. Same NON-PEER-REVIEWED caveat "
                     "as X2. The nearest PAPER, arXiv:2511.06390 ('Ghost in the Transformer', "
                     "AAAI 2026), is a lineage fingerprint, not an orthogonalisation scar; "
                     "arXiv:2608.05578 [38] is activation-based.",
            "unclaimed_increment": "none as an idea. What this lane adds is the PARENT PRESENCE "
                                   "TEST, a ground-truth detection floor from a known lesion "
                                   "(T2), and a head-to-head against the incumbent statistic "
                                   "(BL7_JORAK_A) on the same weights.",
            "source_of_verdict": RESEARCH_LANE,
            "excluded_from_survivor_selection": True},
    "X11": {"verdict": "PARTIALLY_SCOOPED",
            "basis": "HARC arXiv:2607.00572 owns the response-site readout (iteration-1 "
                     "research dependency: K1 arming interaction PARTIALLY SCOOPED); the "
                     "crossing of prefix hazard x request harm on matched twins is not "
                     "published. X11 is a CARRIED re-test, never a headline candidate.",
            "unclaimed_increment": "the 2x2 interaction on matched XSTest twins, refit on the "
                                   "stable axis.",
            "source_of_verdict": "iteration-1 research dependency art_CC5kC0-E3lXW",
            "excluded_from_survivor_selection": True},
}

UNVERIFIED_IDS = {
    "2605.16600": {
        "named_as": "owning X2's algebra, via a Relative Subspace Fraction identity",
        "status": "NOT CITED -- absent from this run's evidence base",
        "what_was_checked": "full-text search of this run's research_out.json returns ZERO "
                            "hits for this id; it was not independently fetched by this lane "
                            "either. It is therefore neither asserted nor denied: it is simply "
                            "not used as support for anything.",
    },
    "2609.01936": {
        "named_as": "'Sparse Readout Prism', likely CLOSING X3",
        "status": "VERIFIED by the same-iteration research lane [15]; does NOT close X3",
        "what_was_checked": "Fetched by iter_2/gen_art/gen_art_research_1: it explains "
                            "logit-lens scores in features instead of tokens, and its safety "
                            "application appears as future work, not as a result. X3 stays "
                            "PARTIALLY_SCOOPED and eligible.",
    },
    "2606.24952": {
        "named_as": "publishing a weight-computable knowing-versus-steering cosine",
        "status": "VERIFIED by the same-iteration research lane [3]",
        "what_was_checked": "'Perfect Detection, Failed Control: The Geometry of Knowing vs. "
                            "Steering in Language Models'. Right STRUCTURE (a per-checkpoint "
                            "weight-computable cosine over 4 models) but on HALLUCINATION, not "
                            "harm, and it concludes the cosine is not a predictor of "
                            "steerability. It evaluates no abliterated checkpoint.",
    },
    "2406.11717": {
        "named_as": "already projecting the refusal direction through the unembedding (X3 "
                    "prior art)",
        "status": "RESOLVES, BUT THE ATTRIBUTION WAS WRONG AND IS WITHDRAWN",
        "what_was_checked": "The id is real -- 'Refusal in Language Models Is Mediated by a "
                            "Single Direction' (Arditi, Obeso, Syed, Paleka, Panickssery, "
                            "Gurnee, Nanda). But the paper does NOT use an unembedding "
                            "projection as its method: it ablates a difference-in-means "
                            "direction and explicitly EXCLUDES late-layer directions close to "
                            "the unembedding (an l < 0.8L filter) to avoid a trivial "
                            "token-level effect. Citing it for X3's mechanism reversed what "
                            "the paper actually does, so the citation is withdrawn.",
    },
    "0.24 vs 0.03 (routing concentration)": {
        "named_as": "the figure motivating X5",
        "status": "VERIFIED REAL -- this lane's own earlier scepticism was WRONG and is "
                  "withdrawn",
        "what_was_checked": "A direct check of arXiv:2607.14147 ('Breaking Refusal in the "
                            "First Half', Kwon) finds the verbatim string 'concentration 0.24 "
                            "vs 0.03, App. E', confirmed in Appendix E. The NUMBER is real. "
                            "What is not real is the LABEL: the paper's own term is "
                            "logit-trace / generative concentration of a refusal attractor, "
                            "and the phrase 'routing concentration' never occurs in it. We "
                            "therefore report the quantity as published and drop the invented "
                            "label.",
    },
    "_method": ("Every arXiv id this lane cites was checked two ways: against this run's own "
                "research_out.json (32 sources that were actually fetched) and by an "
                "independent live lookup on arxiv.org. Four ids used here -- 2511.06390, "
                "2604.15557, 2609.13534 and 2406.11717 -- are absent from research_out.json "
                "and were verified only by this lane's live lookup; that is stated rather than "
                "hidden. One attribution (2406.11717) was found to be backwards and was "
                "withdrawn, and one of this lane's own sceptical notes (the 0.24-vs-0.03 "
                "figure) was found to be wrong and was withdrawn. No id used anywhere in this "
                "output failed to resolve."),
}


def main() -> int:
    setup_logging("make_outputs")
    t0 = time.time()
    prereg = jload(WS / "prereg.json")
    cfg = prereg["config"]
    stim_meta = prereg["stimuli_meta"]
    pairs_doc = (jload_maybe(RESULTS / "pairs_effective.json", None)
                 or jload(ASSETS / "pairs.json"))
    scored = jload_maybe(RESULTS / "scored_checkpoints.json", {}) or {}
    recog = jload_maybe(RESULTS / "recognition.json", {}) or {}
    rows = jload_maybe(RESULTS / "pairs_table.json", []) or []
    rows = _join_robust_labels(rows)
    etests = jload_maybe(RESULTS / "e_tests.json", {}) or {}
    e4 = jload_maybe(RESULTS / "e4.json", {}) or {}
    budget = jload_maybe(RESULTS / "budget_curve.json", {}) or {}
    equiv = jload_maybe(RESULTS / "recognition_equivalence.json", []) or []
    fps = jload_maybe(RESULTS / "weight_fingerprints.json", {}) or {}
    x10only = jload_maybe(RESULTS / "x10_weight_only.json", {}) or {}
    t1 = jload_maybe(RESULTS / "t1_unit_tests.json", {}) or {}
    t2 = jload_maybe(RESULTS / "t2_lesion_control.json", {}) or {}
    leak = jload_maybe(RESULTS / "leak_audit.json", {}) or {}
    judge_ext = jload_maybe(RESULTS / "judge_extension.json", {}) or {}
    devs = jload_maybe(RESULTS / "deviations.json", []) or []
    fails = jload_maybe(RESULTS / "harvest_failures.json", []) or []
    wfails = jload_maybe(RESULTS / "wsummary_failures.json", []) or []
    sweep_status = jload_maybe(RESULTS / "sweep_status.json", {}) or {}
    confirm = jload_maybe(RESULTS / "confirmation.json", {}) or {}
    survivor_doc = jload_maybe(WS / "survivor.json", {}) or {}

    e_tables = etests.get("e_tables", {})
    cand_keys = sp.HEADLINE

    # ---------------- S-TABLE ----------------
    s_table = []
    for k in cand_keys + ["X10_abs", "X10_median", "X11", "BL1_REFLOGIT", "BL2_RAWHID",
                          "BL3_DIFFMEAN", "BL6_HRCI", "BL7_JORAK_A", "BL5_CARDREGEX",
                          "BL5_CARDREGEX_NAMEFREE"]:
        e = e_tables.get(k, {})
        e1, e2, e3 = e.get("E1", {}), e.get("E2", {}), e.get("E3", {})
        n_esc = sum(1 for r in rows if (r.get("deltas", {}).get(k, {}) or {}).get("escapes_band"))
        n_tot = sum(1 for r in rows if k in r.get("deltas", {}))
        n_pairs = e1.get("e1a_sensitivity", {}).get("n", 0)
        # MDE IN POOLED-NULL-SD UNITS (the unit of every E1/E2 threshold): 1.96 x the item-
        # bootstrap SE of Delta_j divided by that pair's pooled shuffled-label SD, median over
        # the pairs that have both. A raw-unit MDE would not be comparable to a 0.50-SD rule.
        mdes = [((r.get("deltas", {}).get(k) or {}).get("mde_pooled_sd")) for r in rows]
        mdes = [m for m in mdes if _isfin(m)]
        mde_v = float(np.median(mdes)) if mdes else None
        s_table.append({
            "candidate": k,
            "is_headline_candidate": k in sp.HEADLINE,
            "is_registered_secondary_of": ("X10 -- the form WITHOUT within-model "
                                           "normalisation, which the T2 control shows is the "
                                           "one that survives a UNIFORM edit"
                                           if k == "X10_abs" else
                                           ("X10 -- the MEDIAN scar across layers, which is "
                                            "what moves under a GLOBAL-UNIFORM edit and stays "
                                            "put under a LOCALISED one"
                                            if k == "X10_median" else None)),
            "computed": bool(n_tot > 0 or k in x10only or any(
                _isfin((scored[t].get("real", {}) or {}).get(k))
                for t in scored if isinstance(scored.get(t), dict) and "real" in scored[t])),
            "e1_pass": e1.get("e1_pass"),
            "e1_status": e1.get("e1_status"),
            "e1_per_stratum": {st: {"n": v.get("n"), "pairs": v.get("pairs"),
                                    "same_signed": v.get("same_signed"),
                                    "n_ci_excluding_zero": v.get("n_ci_excluding_zero"),
                                    "under_powered": v.get("under_powered", False)}
                               for st, v in (e1.get("e1a_per_stratum") or {}).items()},
            "e1_pooled_secondary": {kk: (e1.get("e1a_pooled_secondary") or {}).get(kk)
                                    for kk in ("n", "pairs", "same_signed",
                                               "n_ci_excluding_zero", "n_outside_parent_band",
                                               "pass", "label", "deltas")},
            "excluded_by_prior_art": sp.SURVIVOR_EXCLUDED.get(k),
            "e1_n_pairs": n_pairs,
            "e1_stratum": e1.get("e1a_stratum"),
            "e1_stratum_shortfall": e1.get("e1_stratum_shortfall"),
            "e1_specificity_pass": (e1.get("e1b_specificity") or {}).get("pass"),
            "e1_rho": (e1.get("e1c_dose_response") or {}).get("rho"),
            "e1_rho_permutation_p": (e1.get("e1c_dose_response") or {}).get("p"),
            "e1_power_statement": (e1.get("e1c_dose_response") or {}).get("power_statement"),
            "e2_pass": e2.get("e2_pass"),
            "e2_margin_pooled_null_sd": e2.get("margin_pooled_null_sd"),
            "e3_margin_vs_BL1": e3.get("e3_margin_vs_BL1"),
            "e3_ci95": e3.get("e3_ci95"),
            "e3_pass": e3.get("e3_pass"),
            "e4_status": e4.get("e4_status"),
            "escapes_shuffled_band_n_pairs": ("N/A -- label-free candidate, see null_used"
                                              if k in sp.LABEL_FREE else f"{n_esc}/{n_tot}"),
            "mde_beside_threshold": mde_v,
            "mde_unit": "pooled shuffled-label SD of the pair difference",
            "mde_note": (f"per-pair MDE = {fmt(mde_v)} pooled null SD (median over {len(mdes)} "
                         f"pairs; 1.96 x item-bootstrap SE / pooled null SD) beside the "
                         f"registered E2 threshold of {cfg['e2_margin_pooled_null_sd']} pooled "
                         "null SD and E1(a)'s CI-excludes-zero rule"
                         + ("; MDE EXCEEDS the 0.50 threshold, so this row is under-powered"
                            if (mde_v is not None and mde_v > cfg["e2_margin_pooled_null_sd"])
                            else "")) if mde_v is not None else
                        "no bootstrap/shuffled-label SD available (label-free candidate or "
                        "not scored)",
            "label_free": k in sp.LABEL_FREE,
            "null_used": ("matched random-matrix (Marchenko-Pastur) baseline + within-model "
                          "layer distribution + PARENT PRESENCE TEST -- X10 uses NO LABELS so "
                          "the shuffled-label band does not apply"
                          if k in sp.LABEL_FREE else "shuffled-label band, n_null="
                          f"{cfg['n_null']}"),
            "prior_art_verdict": PRIOR_ART.get(k, {}).get("verdict"),
            "prior_art_basis": PRIOR_ART.get(k, {}).get("basis"),
            "prior_art_unclaimed_increment": PRIOR_ART.get(k, {}).get("unclaimed_increment"),
        })

    # ---------------- NOT COMPUTED / PARTIALLY COMPUTED ----------------
    # X5 and X11 read the teacher-forced C-harvest. Session 1 dropped it on a slower box;
    # session 2 restored it as a separate resumable pass (src/c_harvest2.py) with the
    # registered PER-TOKENIZER slot rule. Report exactly where each is defined.
    def _c_status(key: str) -> dict:
        have, undef, missing = [], [], []
        for t, s_ in scored.items():
            if not isinstance(s_, dict) or "real" not in s_:
                continue
            cm = (s_.get("meta") or {}).get("c_meta") or {}
            v = (s_.get("real") or {}).get(key)
            if _isfin(v):
                have.append(t)
            elif cm:
                undef.append({"checkpoint": t, "drop_frac": cm.get("drop_frac"),
                              "reason": "more than 20% of cells failed the per-tokenizer "
                                        "slot-in-both-windows rule -> UNDEFINED"})
            else:
                missing.append(t)
        return {"computed_on": have, "n_computed": len(have), "undefined": undef,
                "not_harvested": missing}
    not_computed = {}
    for key, what in (("X5", "per-position residual deltas (D_resp)"),
                      ("X11", "window-pooled 2x2 cell states (A_resp)")):
        st = _c_status(key)
        if st["n_computed"] == 0:
            st["status"] = (f"NOT COMPUTED. {key} needs {what} from the teacher-forced "
                            "C-harvest, which did not complete for any checkpoint within the "
                            "wall clock. Reported as NOT COMPUTED rather than computed on a "
                            "degraded substrate.")
        else:
            st["status"] = (f"COMPUTED on {st['n_computed']} checkpoint(s) from the "
                            "session-2 C-harvest pass (per-tokenizer slot rule applied); see "
                            "'undefined' and 'not_harvested' for the rest.")
        not_computed[key] = st

    # ---------------- RECOGNITION TABLE ----------------
    rec_table = []
    for tag, r in sorted(recog.items()):
        if "error" in r:
            rec_table.append({"checkpoint": tag, "error": r["error"]})
            continue
        rec_table.append({
            "checkpoint": tag,
            "R_TPR": r.get("R_TPR"), "R_TPR_fpr_level": r.get("R_TPR_fpr_level"),
            "R_TPR_se": r.get("R_TPR_se"),
            "R_TPR_at_1pct_FPR_secondary": r.get("R_TPR_at_1pct"),
            "n_benign_hard": r.get("n_benign_hard"), "n_harm_hard": r.get("n_harm_hard"),
            "R_AUROC": r.get("R_AUROC"),
            "R_AUROC_label": "SATURATED / NOT A TEST",
            "R_b16": r.get("R_b16"), "R_b32": r.get("R_b32"), "R_b64": r.get("R_b64"),
            "best_layer": r.get("best_layer"),
            "outer_fold_layers": r.get("outer_fold_layers"),
            "layer_selection": r.get("layer_selection"),
            "secondary_easy_layer": r.get("secondary_easy_layer"),
            "secondary_hard_argmax": r.get("secondary_hard_argmax"),
            "headroom_sentence": r.get("headroom_sentence"),
        })

    # ---------------- PER CHECKPOINT ----------------
    per_ckpt = []
    for tag in sorted(set(list(scored) + list(x10only))):
        s_ = scored.get(tag, {})
        real = s_.get("real", {}) or {}
        nulls = s_.get("nulls", {}) or {}
        meta = s_.get("meta", {}) or {}
        row: dict[str, Any] = {
            "checkpoint": tag, "repo": meta.get("repo", tag),
            "family": meta.get("family"), "role": meta.get("role"),
            "n_layers": meta.get("n_layers"), "hidden_size": meta.get("hidden_size"),
            "random_init": meta.get("random_init"),
            "template_mode": meta.get("template_mode"),
            "dtype_loaded": meta.get("dtype_loaded"),
            "dtype_config": meta.get("dtype_config"),
            "tie_word_embeddings": meta.get("tie_word_embeddings"),
            "split_half_cosine": real.get("split_half_cosine"),
            "primary_axis": real.get("primary_axis"),
            "axis_substitution_reason": real.get("axis_substitution_reason"),
            "l_star": real.get("l_star"), "l_dec": real.get("l_dec"),
            "l_peak": real.get("l_peak"), "l_act": real.get("l_act"),
            "f_dec": real.get("f_dec"), "f_act": real.get("f_act"),
            "n_null_draws": s_.get("n_null_draws"),
            "escapes_own_shuffled_band": s_.get("escapes_own_band"),
            "item_bootstrap": {"n_boot": (s_.get("boot") or {}).get("n_boot"),
                               "ci95": (s_.get("boot") or {}).get("ci95"),
                               "se": (s_.get("boot") or {}).get("se"),
                               "protocol": (s_.get("boot") or {}).get("protocol")},
            "load_missing_keys_n": meta.get("load_missing_keys_n"),
            "weights_fully_bound": meta.get("weights_fully_bound"),
            "c_harvest": meta.get("c_meta"),
            "random_direction_unit": s_.get("random_direction"),
            "error": s_.get("error"),
        }
        for k in sp.HEADLINE + sp.CARRIED + sp.BASELINES + ["X10_abs", "X10_argmax_layer",
                                                            "X10_cos_vmin_vs_u",
                                                            "X10_cos_vmin_vs_u_max",
                                                            "X10_median", "X10_mad",
                                                            "BL3_AUROC", "BL2_TPR5",
                                                            "X3_finallayer", "X9"]:
            v = real.get(k, x10only.get(tag, {}).get(k))
            if v is None:
                continue
            nd = nulls.get(k) or {}
            row[k] = {"raw": clean_float(v),
                      "shuffled_sd_units": clean_float(v / nd["sd"]) if nd.get("sd") else None,
                      "shuffled_band": nd.get("band"), "shuffled_sd": nd.get("sd")}
        if tag in x10only:
            row["weight_only_checkpoint"] = True
            row["note"] = x10only[tag].get("note")
        per_ckpt.append(row)

    # ---------------- PARENT PRESENCE TESTS ----------------
    ppt = []
    for p in pairs_doc["pairs"]:
        pt, ct = slug(p["parent"]), slug(p["child"])
        gp = (scored.get(pt, {}).get("real") or {}) or x10only.get(pt, {})
        gc_ = (scored.get(ct, {}).get("real") or {}) or x10only.get(ct, {})
        if "X10" not in gp and "X10" not in gc_:
            continue
        ppt.append({
            "signature": "X10 orthogonality scar",
            "pair": p["pair"], "parent": p["parent"], "child": p["child"],
            "parent_value": clean_float(gp.get("X10")),
            "child_value": clean_float(gc_.get("X10")),
            "parent_abs": clean_float(gp.get("X10_abs")),
            "child_abs": clean_float(gc_.get("X10_abs")),
            "effectiveness": p.get("effectiveness"),
            "interpretation": ("a scar present in the PARENT is not abliteration-specific; "
                               "any signature called abliteration-specific without this test "
                               "is a model-diffing misattribution"),
        })

    # ---------------- INHERITED CLAIMS AUDIT ----------------
    audit = _inherited_audit(fps, pairs_doc, jload_maybe(RESULTS / "embed_tokens_check.json", {}))

    # ---------------- SURVIVOR ----------------
    survivor = survivor_doc.get("survivor")
    if survivor is None:
        passing = [r for r in s_table if r["is_headline_candidate"] and r.get("e1_pass")
                   and not r.get("excluded_by_prior_art")
                   and (r.get("e2_pass") or r.get("e3_pass"))]
        passing.sort(key=lambda r: (-(r.get("e3_margin_vs_BL1") or -9),
                                    -(r.get("e1_n_pairs") or 0)))
        survivor = passing[0]["candidate"] if passing else "NONE"

    metadata = {
        "method_name": "Parent-free single-checkpoint EXECUTION-side readouts vs the "
                       "RECOGNITION axis (iteration 2, Lane A)",
        "one_mechanistic_question": (
            "Is the axis that separates a base model, its safety-tuned child and its "
            "abliterated child a RECOGNITION axis -- the model still sees the harm -- or an "
            "EXECUTION axis -- the model stops acting on it? The candidate table is the "
            "INSTRUMENT for answering that; it is not a leaderboard of readouts."),
        "prereg_sha256": sha256_file(WS / "prereg.json"),
        "prereg": prereg,
        "run_invariant": prereg["invariant"],
        "hardware": _hardware(),
        "package_versions": _versions(),
        "t1_unit_tests": t1,
        "t7_determinism": jload_maybe(RESULTS / "t7_determinism.json", {}) or {
            "status": "NOT RUN"},
        "t2_t3_ground_truth_lesion_control": _t2_block(t2),
        "t5_leakage_audits": leak,
        "judge_extension": {k: {kk: vv for kk, vv in v.items() if kk != "rows"}
                            for k, v in judge_ext.items()} if judge_ext else {
            "status": "NOT RUN",
            "reason": "the commissioned child mlabonne/Qwen3-4B-abliterated carries no judged "
                      "behavioural row from iteration 1, so its effectiveness label is "
                      "UNKNOWN and it is EXCLUDED from E1. E1 is evaluated on the five pairs "
                      "that do carry judged rows, which meets the registered minimum of 4."},
        "s_table": s_table,
        "not_computed": not_computed,
        "recognition_table": rec_table,
        "recognition_equivalence": equiv,
        "recognition_premise_note": (
            "R is the PREMISE and is reported FIRST. If R separates parent from child beyond "
            "the registered equivalence margin in most pairs, the hypothesis's premise is "
            "wrong and two published results are contradicted -- that is the finding, not a "
            "failure, and the recognition set is NOT re-tuned to restore the expected answer."),
        "per_checkpoint": per_ckpt,
        "pairs_table": rows,
        "stratification_table": _strata(rows, fps),
        "prompt_budget_curve": budget,
        "baselines_note": {
            "implemented": sp.BASELINES,
            "BL5_CARDREGEX": "run in BOTH a term-swept and a NAME-FREE variant and reported "
                             "separately; the term-swept version is inflated by the very "
                             "label it predicts. If it wins, we say so.",
            "BL6_HRCI": "reimplementation of arXiv:2606.16349 Eq 9; k=8 and the CCA-on-PCs "
                        "subspace protocol are OURS because the source does not state them. "
                        "Its authors report the 0.5/0.5 weighting is a fixed symmetry-based "
                        "summary, not optimised against ASR, refusal or utility, and conclude "
                        "'low coupling is not a safety score'. If HRCI beats our candidates "
                        "that is an important finding, not an embarrassment.",
            "not_implemented": {
                "N-GLARE JSS / JR-Min-Max": "marked NOT IMPLEMENTABLE by this run's research "
                                            "dependency: no public code found, and it needs 4 "
                                            "dialogue families so it is not a 0-prompt method.",
                "GFS/Skin-Deep, two-signal z-sum audit, CANARY": "PARENT-REQUIRING, so they "
                                                                "violate the parent-free "
                                                                "invariant and are excluded.",
            },
        },
        "nulls": {
            "shuffled_label_band": f"n_null={cfg['n_null']} permutations of y over the EASY "
                                   "set, refitting u and the probe from scratch each draw",
            "escape_rule": prereg["decision_rules"]["escape_rule"],
            "random_direction_unit": "n_rand=%d; A UNIT ONLY, NEVER A TEST" % cfg["n_rand"],
            "random_init_arm": _randinit(scored, x10only),
        },
        "parent_presence_tests": ppt,
        "machinery_controls": etests.get("machinery_controls"),
        "e_tests": e_tables,
        "e4": e4,
        "weight_fingerprints_summary": {k: (v.get("summary") or {}) | {
            "stratum": v.get("stratum"), "embed_tokens_edited":
            (v.get("embed_tokens") or {}).get("edited"),
            "power_iteration_verification": v.get("power_iteration_verification")}
            for k, v in fps.items() if isinstance(v, dict)},
        "inherited_claims_audit": audit,
        "unverified_citations_refused": UNVERIFIED_IDS,
        "prior_art_verdicts": PRIOR_ART,
        "confirmation": confirm or {
            "status": "NOT RUN",
            "reason": "no candidate was frozen as a survivor, or the wall clock was reached "
                      "before the confirmation tier; see deviations.",
        },
        "survivor": survivor,
        "survivor_wording_rule": (
            "E4 is %s, so the word EXECUTION is WITHHELD from any survivor; it is called a "
            "READOUT." % e4.get("e4_status", "NOT_EVALUATED")),
        "deviations": devs + [{"kind": "harvest_failure", **f} for f in fails]
        + [{"kind": "wsummary_failure", **f} for f in wfails],
        "dropped_pairs": DROPPED_PAIRS,
        "sweep_status": sweep_status,
        "empty_blocks_declared": _empty_blocks(scored, rows, e_tables, budget, confirm),
        "self_audit": _self_audit(s_table, ppt, budget, audit, rows),
        "cost_ledger_total_usd": _cost(),
        "build_seconds": time.time() - t0,
    }

    _released(scored, recog, rows, x10only)
    metadata["cross_iteration_direction_check"] = cross_iteration_direction_check()
    metadata["cross_checkpoint_direction_matrix"] = cross_checkpoint_direction_matrix()
    metadata["recognition_vs_execution_depth_profile"] = \
        recognition_vs_execution_depth_profile(pairs_doc, scored)
    metadata["commissioned_lineage"] = commissioned_lineage(scored, recog, judge_ext, x10only)
    metadata["mechanistic_verdict"] = mechanistic_verdict(
        rows, equiv, metadata["recognition_vs_execution_depth_profile"], cfg, scored)
    metadata["x2_parent_identity_rows"] = jload_maybe(RESULTS / "x2_parent_identity.json", [])
    metadata["budget_pair_deltas"] = jload_maybe(RESULTS / "budget_pair_deltas.json", [])
    datasets = _datasets(scored, recog, rows, s_table, pairs_doc, x10only, e_tables, e4)
    doc = {"metadata": metadata, "datasets": datasets}
    p = jdump(doc, OUT / "method_out.json")
    logger.info(f"wrote {p} ({p.stat().st_size/1e6:.1f} MB)")
    _summary_md(metadata, datasets)
    return 0


# ---------------------------------------------------------------- helpers
def _t2_block(t2: dict) -> dict:
    """T2/T3: the ground-truth control that says whether X2 and X10 mean anything at all."""
    if not t2:
        return {"status": "NOT RUN"}
    pc = t2.get("positive_control", {}) or {}
    loc = t2.get("localisation_verdict", {}) or {}
    per = pc.get("per_alpha", {}) or {}
    rows = []
    for a in sorted(per, key=float):
        r = per[a]
        rows.append({"alpha": float(a), "X10_max_z": r.get("X10_max_z"),
                     "X10_argmax_is_edited_layer": r.get("X10_argmax_is_edited_layer"),
                     "X2_write_mass_u0": r.get("X2_write_mass_u0_mean"),
                     "X2_write_mass_algebraic_prediction": (1.0 - float(a)) ** 2,
                     "cos_vmin_u0_edited": r.get("cos_vmin_u0_mean_edited")})
    # DETECTION FLOOR, derived from the sweep rather than from a single hard-coded rule:
    # the smallest swept alpha at which the scar z-score rises meaningfully above the
    # UNEDITED baseline (alpha = 0) AND the near-null direction has turned into the deleted
    # direction. Both are reported, because they can separate.
    base_z = next((r["X10_max_z"] for r in rows if r["alpha"] == 0.0), None)
    floor_z = next((r["alpha"] for r in rows if r["alpha"] > 0 and base_z is not None
                    and r["X10_max_z"] is not None
                    and r["X10_max_z"] > base_z * 1.5), None)
    floor_cos = next((r["alpha"] for r in rows if r["alpha"] > 0
                      and (r["cos_vmin_u0_edited"] or 0) > 0.5), None)
    mass_err = max(
        (abs((r["X2_write_mass_u0"] or 0) - r["X2_write_mass_algebraic_prediction"])
         for r in rows if r["X2_write_mass_u0"] is not None), default=None)
    return {
        "repo": pc.get("repo"), "alpha_sweep": rows,
        "X2_matches_algebraic_prediction": {
            "max_abs_error_vs_(1-alpha)^2": mass_err,
            "verdict": ("X2's write mass along the deleted direction follows the exact "
                        "algebraic prediction (1-alpha)^2 on REAL weights across the whole "
                        "sweep" if (mass_err is not None and mass_err < 1e-3) else
                        "X2's write mass DEPARTS from (1-alpha)^2 -- investigate before "
                        "trusting any X2 number")},
        "detection_floor_alpha_by_z_jump": floor_z,
        "detection_floor_alpha_by_null_direction": floor_cos,
        "detection_floor_note": (
            f"the scar z-score only rises above its unedited baseline ({base_z}) at "
            f"alpha >= {floor_z}, and the near-null direction only becomes the deleted "
            f"direction at alpha >= {floor_cos}. BELOW that, a partial abliteration removes "
            "write mass exactly as predicted yet leaves NO weights-only scar, so it would be "
            "MISSED. That is the number to quote when a community edit is missed. For "
            "context, iteration 1 measured the real mlabonne/Qwen3-4B-abliterated edit at an "
            "implied alpha near 0.97, i.e. above this floor."),
        "detection_floor_alpha_source_rule": pc.get("detection_floor_note"),
        "UNIFORM_EDIT_BLINDS_THE_Z_FORM": _uniform_edit_finding(rows, loc),
        "T3_negative_control": pc.get("T3_negative_control"),
        "localisation_verdict": loc,
        "what_this_establishes": (
            "A KNOWN rank-one orthogonalisation is applied to a clean model at a known "
            "direction u0 and a swept alpha. (i) the write mass along u0 must follow the "
            "algebraic prediction (1-alpha)^2 exactly -- if it does not, X2 is not measuring "
            "what it claims; (ii) X10's scar must fire at the edited layers and nowhere else; "
            "(iii) cos(vmin, u0) must approach 1 at the edited layers, i.e. the near-null "
            "direction IS the deleted one; (iv) the alpha sweep gives the DETECTION FLOOR, "
            "the smallest edit strength a weights-only scar still sees. That floor is the "
            "number to quote when a community edit is missed. T3 is the negative control: "
            "X10 must NOT fire on the unedited model or on random init."),
    }


def _uniform_edit_finding(rows: list, loc: dict) -> dict:
    """The registered PRIMARY form of X10 fails its own ground-truth control when the edit
    is applied UNIFORMLY to every layer -- which is exactly what a community abliteration
    does.  This is reported as a finding, not quietly patched by swapping in the secondary.
    """
    z0 = next((r["X10_max_z"] for r in rows if r["alpha"] == 0.0), None)
    z75 = next((r["X10_max_z"] for r in rows if r["alpha"] == 0.75), None)
    z100 = next((r["X10_max_z"] for r in rows if r["alpha"] == 1.0), None)
    cos100 = next((r["cos_vmin_u0_edited"] for r in rows if r["alpha"] == 1.0), None)
    collapses = bool(z100 is not None and z0 is not None and z100 <= z0)
    return {
        "X10_max_z_unedited": z0,
        "X10_max_z_at_alpha_0p75_partial": z75,
        "X10_max_z_at_alpha_1p0_ALL_LAYERS": z100,
        "cos_vmin_u0_at_alpha_1p0": cos100,
        "z_form_collapses_under_uniform_edit": collapses,
        "half_layer_localisation_control": loc,
        "finding": (
            "X10's REGISTERED PRIMARY form is max_l z(scar_l), where z is taken against the "
            "MEDIAN AND MAD OF THE MODEL'S OWN LAYERS. That normalisation asks 'which layer "
            "is anomalous relative to this model's other layers', so it is BLIND BY "
            "CONSTRUCTION to an edit applied uniformly to every layer: when all layers are "
            f"scarred the median moves with them and the z-score collapses ({z0} unedited -> "
            f"{z100} at alpha=1.0 on ALL layers), even though cos(vmin, u0) = {cos100}, i.e. "
            "the near-null direction IS exactly the deleted one. The HALF-LAYER localisation "
            "control confirms the mechanism is intact when the edit is localised: mean scar "
            f"{loc.get('mean_scar_edited')} on edited layers versus "
            f"{loc.get('mean_scar_unedited')} on unedited ones, with cos(vmin, u0) "
            f"{loc.get('cos_vmin_u0_edited')} versus {loc.get('cos_vmin_u0_unedited')}."),
        "consequence": (
            "Community abliterations edit EVERY layer, so the registered primary is the wrong "
            "statistic for the very case this lane screens. The registered SECONDARY, "
            "X10_abs = max_l scar_l (no within-model normalisation), is the form that "
            "survives a uniform edit. We report BOTH, we do NOT retroactively promote the "
            "secondary to primary, and any X10 result is read with this control beside it. "
            "This is the kind of thing a ground-truth positive control exists to catch, and "
            "it would have been invisible without the alpha sweep."),
    }


def _join_robust_labels(rows: list) -> list:
    """SENSITIVITY ONLY: the same-iteration dataset lane re-labelled the pairs with a
    CI rule (Newcombe 95% interval of delta_HC entirely on one side of the threshold at
    n=45/45). Its label never replaces this lane's REGISTERED point-estimate rule; it is joined
    so a reader can see which EFFECTIVE labels are statistically fragile."""
    reg = jload_maybe(WS.parent / "gen_art_dataset_1" / "build" / "registry_labelled.json", {})
    by_child = {}
    for q in (reg or {}).get("pairs", []) or []:
        pid = str(q.get("pair_id") or "")
        if "__" in pid:
            by_child[pid.split("__", 1)[1]] = q
    for r in rows:
        child_name = str(r.get("child") or "").split("/")[-1]
        q = by_child.get(child_name)
        if q is not None:
            r["sibling_dataset_lane_label"] = q.get("effectiveness_label")
            r["sibling_dataset_lane_label_robust"] = q.get("label_robust")
            r["sibling_label_note"] = ("SENSITIVITY ONLY -- iter_2 dataset lane's CI rule "
                                       "(Newcombe 95% CI of delta_HC entirely on one side of the "
                                       "threshold); the registered label here is the point-"
                                       "estimate rule fixed before any label was assigned")
    return rows


def _hardware() -> dict:
    import os
    import platform
    try:
        import torch
        cuda = torch.cuda.is_available()
        tv = torch.__version__
    except Exception:  # noqa: BLE001
        cuda, tv = False, None
    load = None
    try:
        load = os.getloadavg()
    except Exception:  # noqa: BLE001
        pass
    return {"platform": platform.platform(), "cpu_count_visible": os.cpu_count(),
            "cuda_available": cuda, "torch": tv, "loadavg_at_write": load,
            "note": ("NO GPU in either session. SESSION 1 (03:36-04:47 UTC): 2 visible cores "
                     "of an AMD Ryzen Threadripper 7960X at an external load average near 40 on "
                     "24 cores; it harvested Qwen3-4B, mlabonne/Qwen3-4B-abliterated and "
                     "Qwen3-4B-Base (8-20 min per 4B checkpoint) and 12 weight summaries before "
                     "the container ended. SESSION 2 (from 07:10 UTC): a NEW container on an "
                     "AMD EPYC 9655 whose cpuset is the two hyperthreads of ONE physical core, "
                     "host load ~200 on 192 threads, a 16 GB cgroup memory ceiling, and the "
                     "run-shared HF cache found EMPTY (re-created 07:02) and the .venv gone, so "
                     "every checkpoint was re-downloaded (~500 MB/s) and the environment rebuilt. "
                     "Measured there: bf16 GEMM 245 GFLOPS, fp32 112 GFLOPS (AVX512-BF16), a 4B "
                     "prompt harvest ~4-5 min. Every harvested number is scoped to what actually "
                     "ran; session-1 caches were reused byte-for-byte (the harvest is resumable "
                     "by DONE sentinels), not recomputed.")}


def _versions() -> dict:
    out = {}
    for m in ("torch", "transformers", "numpy", "scipy", "sklearn", "safetensors"):
        try:
            out[m] = __import__(m).__version__
        except Exception:  # noqa: BLE001
            out[m] = None
    return out


def _cost() -> float:
    from aii_common import COST
    return COST.total()


def _randinit(scored: dict, x10only: dict) -> dict:
    out = {}
    for tag in list(scored) + list(x10only):
        if not tag.startswith("RandInit"):
            continue
        real = (scored.get(tag, {}) or {}).get("real", {}) or x10only.get(tag, {})
        out[tag] = {k: clean_float(real.get(k)) for k in sp.HEADLINE if real.get(k) is not None}
    out["rule"] = ("handbook rule d: any candidate whose value on an architecture-identical "
                   "RANDOMLY INITIALISED model is comparable to its value on trained models "
                   "is reported as NOT A PROPERTY OF TRAINED REPRESENTATIONS. X10 especially "
                   "must NOT fire on random init.")
    return out


def _strata(rows: list, fps: dict) -> list:
    from collections import Counter
    c = Counter(r.get("stratum", "UNKNOWN") for r in rows)
    eff = Counter(r.get("stratum", "UNKNOWN") for r in rows
                  if r.get("effectiveness") == "EFFECTIVE")
    return [{"stratum": s, "n_pairs": n, "n_effective": eff.get(s, 0),
             "meets_e1a_minimum": bool(eff.get(s, 0) >= 4),
             "members": [r["pair"] for r in rows if r.get("stratum") == s]}
            for s, n in sorted(c.items())] + [
        {"rule": "NEVER pool across strata for E1(a). If no stratum reaches 4 EFFECTIVE "
                 "pairs, E1(a) is evaluated in the LARGEST stratum, e1_stratum_shortfall is "
                 "set true, and the pooled-across-strata result is given ONLY as a labelled "
                 "secondary row."}]


def _inherited_audit(fps: dict, pairs_doc: dict, emb: dict | None = None) -> dict:
    lane_a_dirs = LANE_C.parent / "gen_art_experiment_1" / "out" / "released" / "directions"
    n_dirs = len(list(lane_a_dirs.glob("*.npy"))) if lane_a_dirs.exists() else 0
    lb = LANE_C.parent / "gen_art_experiment_2"
    n_npz = len(list(lb.glob("out/harvest/*.npz"))) if lb.exists() else 0
    return {
        "D6_i_raw_hidden_states_saved_nowhere": {
            "claim": "iteration 1 saved no raw hidden states",
            "resolution": f"PARTLY FALSE. Lane B kept a {n_npz}-file .npz harvest "
                          "(~7.6 GB) under out/harvest/, but its arrays are WINDOW-POOLED "
                          "vectors keyed item|win|{EARLY,LATE}|{layer} over the 2x2 cell "
                          "substrate under lesion alphas, for a subset of layers only -- not "
                          "per-item per-layer PROMPT hidden states for the pairs. They are "
                          "therefore NOT reusable as this lane's P-harvest, and were not "
                          "reused. Lane C saved none (a glob for .npy/.npz/.pt returns zero).",
        },
        "D6_ii_abliterated_in_no_metric_table": {
            "claim": "the abliterated checkpoint is in NO metric table",
            "resolution": f"FALSE, AND VERIFIED FALSE. Lane A's out/released/directions/ "
                          f"holds {n_dirs} .npy files = 2 per checkpoint over 7 checkpoints "
                          "including Qwen3-4B-abliterated and a RandInit-4B arm, and Lane A's "
                          "method_out.json carries a 'checkpoint_panel_readouts' dataset with "
                          "one row per checkpoint. THE TRUE STATEMENT, which this lane acts "
                          "on: the abliterated checkpoint has RECOGNITION-side readouts in "
                          "Lane A, but (1) no EXECUTION-side readout was computed on it or on "
                          "any other pair, (2) the pairs were never analysed AS pairs, and "
                          "(3) it appears in no CROSS-FAMILY panel. Those three are the "
                          "genuine gaps and they are what this lane fills.",
        },
        "D6_iii_two_families_sealed": {
            "claim": "the stablelm and smollm2 families are SEALED held-out evidence",
            "resolution": "THE SEAL IS LEAKED. Lane C's prereg.json lists sealed_families = "
                          "[stablelm, smollm2] and lc_output.py does restrict the EXPORT to "
                          "scored families -- but results/s3/s3_results.json computes "
                          "behavioural_columns straight from results/judged/*.jsonl with no "
                          "sealed filter, so both families' real truth values sit in it "
                          "(stablelm-2-1_6b-chat 0.467 -> heretic 0.356; SmolLM2-1.7B-Instruct "
                          "0.200 -> venkycs 0.000 at over_refusal 1.000). Both also REVERSE "
                          "the expected direction. They are therefore used ONLY as ANOMALOUS "
                          "specificity controls, never as confirmation.",
        },
        "D6_iv_five_size_anomalies": {
            "claim": "five size anomalies in the panel",
            "resolution": "IT IS TWO. (i) philippefunk/TinyLlama-1.1B-Chat-v1.0-abliterated: "
                          "0.81 GB vs 2.20 GB and 630,759,982 vs 1,100,048,384 params -- a "
                          "BROKEN upload with missing shards, dropped, not repairable. "
                          "(ii) venkycs/SmolLM2-1.7B-Instruct-Abliterated: 1.82 GB vs 3.42 GB "
                          "with a params ratio of ~1.0004 and float16 vs bfloat16 -- it loads "
                          "and produces judged rows, and its judged profile (harmful "
                          "compliance 0.000, over-refusal 1.000) says BROKEN-BEHAVING, not "
                          "uncensored, so it is labelled ANOMALOUS. CAUSE, VERIFIED IN SESSION 2: "
                          "it is an optimum-quanto FP8 upload (<key>._data float8_e4m3fn + "
                          "per-channel <key>._scale) with no quantization_config, so a standard "
                          "transformers load reports 168 MISSING tensors -- every linear layer "
                          "of all 24 blocks is left at RANDOM init. What Lane C judged is a "
                          "random network with trained embeddings; its recognition R collapses "
                          "(0.825 -> 0.138) exactly as a broken model's should. "
                          "allenai/OLMo-2-0425-1B at "
                          "0.501x is purely float32 vs bfloat16 and is a base-vs-instruct "
                          "pair, not an abliteration pair.",
        },
        "D6_v_tinyllama_repairable": {
            "claim": "the TinyLlama pair can be repaired",
            "resolution": "IT CANNOT. The weights are not there. It is DROPPED as EXCLUDED: "
                          "BROKEN UPLOAD. Worth one sentence in any write-up: a hub "
                          "checkpoint labelled 'abliterated' is simply broken, which is a "
                          "fact about the supply of these uploads.",
        },
        "conflict_1_which_families_are_sealed": {
            "conflict": "the dataset artifact's model_registry.json marks the Qwen2.5-1.5B "
                        "and SmolLM2-1.7B triads sealed=true (6 repos); Lane C's prereg lists "
                        "sealed_families=[stablelm, smollm2] and puts qwen2.5 among its "
                        "SCORED families. They disagree about Qwen2.5-1.5B, which is pair P3.",
            "resolution": "RESOLVED IN FAVOUR OF LANE C, ON EVIDENCE. The registry names the "
                          "Josiefied -v1 revision; the panel and Lane C use -v3, and Lane C "
                          "did score it -- results/per_ckpt/Goekdeniz-Guelmez__Josiefied-"
                          "Qwen2.5-1.5B-Instruct-abliterated-v3.json EXISTS, and qwen2.5 is "
                          "in Lane C's scored_families. The registry's seal therefore applies "
                          "to a DIFFERENT revision. P3 IS USABLE and is kept as an EFFECTIVE "
                          "pair (0.000 -> 0.467).",
        },
        "conflict_2_routing_concentration_0p24_vs_0p03": {
            "conflict": "the 0.24-vs-0.03 routing-concentration figure motivating X5",
            "resolution": "RESOLVED AGAINST THIS LANE'S OWN PLANNING-TIME SCEPTICISM. A "
                          "full-text search of this run's research_out.json for 'routing "
                          "concentration', 'concentration' and '0.24' returns ZERO matches, "
                          "which is why the figure was initially treated as unverifiable. A "
                          "direct check of arXiv:2607.14147 ('Breaking Refusal in the First "
                          "Half', Kwon) then found the verbatim string 'concentration 0.24 vs "
                          "0.03, App. E' in Appendix E. THE NUMBER IS REAL; the planning-time "
                          "note that it could not be verified was wrong and is withdrawn. "
                          "What is NOT real is the label: the paper's term is logit-trace / "
                          "generative concentration, and 'routing concentration' never occurs "
                          "in it. Consequence: X5 is a re-operationalisation of a PUBLISHED "
                          "concentration measure, not a new one, and its prior-art verdict is "
                          "upgraded to PARTIALLY_SCOOPED. X5 was not computed in this run, so "
                          "this is recorded for the next iteration.",
        },
        "D6_extra_embed_tokens_claim": _embed_claim(emb or {}),
        "effective_pairs_in_hand": {
            "count": sum(1 for p in pairs_doc["pairs"] if p["effectiveness"] == "EFFECTIVE"),
            "null_edit": [p["pair"] for p in pairs_doc["pairs"]
                          if p["effectiveness"] == "NULL_EDIT"],
            "anomalous": [p["pair"] for p in pairs_doc["pairs"]
                          if p["effectiveness"] == "ANOMALOUS"],
            "unknown": [p["pair"] for p in pairs_doc["pairs"]
                        if p["effectiveness"] == "UNKNOWN"],
        },
    }


def _embed_claim(emb: dict) -> dict:
    """An inherited claim this lane tested directly and FOUND FALSE."""
    p0 = emb.get("P0") or {}
    t = p0.get("tensors") or {}
    return {
        "claim": ("iteration 1 Lane B recorded: 'mlabonne DOES edit embed_tokens. Qwen3-4B "
                  "has tie_word_embeddings=True, so that edit also removes the direction from "
                  "the UNEMBED.' That note was load-bearing -- it was used to argue a "
                  "logit-side outcome could be contaminated by the edit."),
        "test": ("re-read model.embed_tokens.weight from BOTH snapshots' safetensors shards "
                 "and compute the exact Frobenius norm of the difference"),
        "resolution": (
            "FALSE for this checkpoint pair, VERIFIED DIRECTLY. "
            + ("model.embed_tokens.weight is BITWISE IDENTICAL between Qwen/Qwen3-4B and "
               "mlabonne/Qwen3-4B-abliterated: ||child - parent||_F^2 = 0 exactly, over "
               "identical (151936, 2560) tensors, with the two repos carrying the same 398 "
               "tensor keys and no key present in one and absent from the other. The "
               "embeddings ARE tied (no lm_head.weight exists), so the tying half of the "
               "claim holds -- but the edit does not touch them, so the unembedding is NOT "
               "modified and a logit-side outcome is NOT contaminated by this edit."
               if (t.get("model.embed_tokens.weight", {}).get("bitwise_identical") is True)
               else "see embed_tokens_check.json for the measured norms")),
        "measured": t,
        "embed_or_head_edited": p0.get("embed_or_head_edited"),
        "tied_embeddings_implied": p0.get("tied_embeddings_implied"),
        "all_pairs": {k: {"embed_or_head_edited": v.get("embed_or_head_edited")}
                      for k, v in emb.items() if isinstance(v, dict) and "tensors" in v},
    }


def _empty_blocks(scored, rows, e_tables, budget, confirm) -> list:
    out = []
    if not rows:
        out.append("pairs_table is EMPTY -- no pair had both members harvested.")
    if not e_tables:
        out.append("e_tests is EMPTY.")
    if not budget:
        out.append("prompt_budget_curve is EMPTY.")
    if not confirm:
        out.append("confirmation is EMPTY / NOT RUN.")
    n_err = sum(1 for v in scored.values() if isinstance(v, dict) and v.get("error"))
    if n_err:
        out.append(f"{n_err} checkpoints failed scoring; see deviations.")
    out.append("Iteration 1's self-audit missed an entirely empty causal results block and a "
               "paper then asserted a claim with zero evidence. This list exists so that "
               "cannot recur: every empty block above is declared here AND in SUMMARY.md.")
    return out


def _self_audit(s_table, ppt, budget, audit, rows) -> dict:
    return {
        "every_candidate_has_a_null_verdict": all(
            r.get("null_used") for r in s_table),
        "label_free_candidates_use_declared_alternative_null": [
            r["candidate"] for r in s_table if r.get("label_free")],
        "parent_presence_test_present_for_abliteration_specific_signatures":
            bool(ppt),
        "every_threshold_has_its_MDE": all("mde_note" in r for r in s_table),
        "budget_curve_has_monotonicity_verdict": {
            t: v.get("monotonicity_verdict") for t, v in budget.items()},
        "X2_parent_labelled_structurally_guaranteed": (
            "X2_parent is an ALGEBRAIC IDENTITY (orthogonalising M against u drives "
            "||u^T M||^2 to zero by construction), is labelled structurally_guaranteed and "
            "is EXCLUDED from all scoring. T1g verifies the identity numerically: write mass "
            "0.925 -> 2.7e-17 with cos(vmin, u0) = 1.000."),
        "scooped_candidates_carry_verdict_at_definition": list(PRIOR_ART),
        "inherited_claims_audit_resolves_all_five_D6_items_and_both_conflicts": (
            len([k for k in audit if k.startswith("D6_")]) == 5
            and "conflict_1_which_families_are_sealed" in audit
            and "conflict_2_routing_concentration_0p24_vs_0p03" in audit),
        "summary_framed_as_one_mechanistic_question_not_a_leaderboard": True,
        "n_pairs_scored": len(rows),
    }


def _datasets(scored, recog, rows, s_table, pairs_doc, x10only, e_tables, e4) -> list:
    ds = []

    ex = []
    for r in sorted(_per_ckpt_rows(scored, recog, x10only), key=lambda x: x["checkpoint"]):
        ex.append({
            "input": f"Checkpoint {r['checkpoint']} ({r.get('repo')}): compute every "
                     "parent-free single-model readout from its own activations and weights.",
            "output": r.get("truth_summary", "no judged behavioural row for this checkpoint"),
            **{f"metadata_{k}": v for k, v in r.items() if k not in ("predicts",)},
            **{f"predict_{k}": S(v) for k, v in (r.get("predicts") or {}).items()},
        })
    if ex:
        ds.append({"dataset": "checkpoint_panel_readouts", "examples": ex})

    ex = []
    for r in rows:
        d = r.get("deltas", {})
        ex.append({
            "input": f"Pair {r['pair']}: {r['parent']} -> {r['child']} (family {r['family']}).",
            "output": (f"{r['effectiveness']}: judged harmful-compliance delta "
                       f"{fmt(r.get('delta_HC'))}, over-refusal delta {fmt(r.get('delta_OR'))}"),
            "metadata_pair": r["pair"], "metadata_family": r["family"],
            "metadata_stratum": r.get("stratum"),
            "metadata_effectiveness": r["effectiveness"],
            "metadata_delta_HC": r.get("delta_HC"), "metadata_delta_OR": r.get("delta_OR"),
            "metadata_delta_SE": r.get("delta_SE"),
            "metadata_fingerprint": r.get("fingerprint_summary"),
            "metadata_deltas": d,
            **{f"predict_{k}": S(v.get("delta_raw")) for k, v in d.items()},
        })
    if ex:
        ds.append({"dataset": "instruct_abliterated_pairs", "examples": ex})

    ex = []
    for tag, r in sorted(recog.items()):
        if "error" in r:
            continue
        ex.append({
            "input": f"Recognition axis for {tag}: cross-validated probe on the HARD set "
                     f"({r.get('n_harm_hard')} harmful vs {r.get('n_benign_hard')} benign, "
                     "lexically matched XSTest twins plus OR-Bench toxic vs OR-Bench hard).",
            "output": (f"TPR@{r.get('R_TPR_fpr_level'):.0%}FPR = {fmt(r.get('R_TPR'))}; "
                       f"{r.get('headroom_sentence')}"),
            "metadata_checkpoint": tag,
            "metadata_R_TPR": r.get("R_TPR"), "metadata_R_TPR_se": r.get("R_TPR_se"),
            "metadata_R_AUROC_SATURATED": r.get("R_AUROC"),
            "metadata_best_layer": r.get("best_layer"),
            "metadata_R_b16": r.get("R_b16"), "metadata_R_b32": r.get("R_b32"),
            "metadata_R_b64": r.get("R_b64"),
            "metadata_n_benign_hard": r.get("n_benign_hard"),
            "predict_R_TPR": S(r.get("R_TPR")),
            "predict_R_AUROC": S(r.get("R_AUROC")),
        })
    if ex:
        ds.append({"dataset": "recognition_axis_hard_set", "examples": ex})

    ex = _item_level_examples(recog)
    if ex:
        ds.append({"dataset": "commissioned_lineage_item_level", "examples": ex})

    ex = []
    for r in s_table:
        e = e_tables.get(r["candidate"], {})
        st = r.get("e1_status")
        if r.get("e1_pass") and (r.get("e2_pass") or r.get("e3_pass")):
            verdict = ("PASSES_E1_AND_E2orE3_BUT_CLOSED_BY_PRIOR_ART"
                       if r.get("excluded_by_prior_art") else "SURVIVOR")
        elif st == "UNDER_POWERED":
            verdict = "E1_UNDER_POWERED"
        elif r.get("e1_pass") is False:
            verdict = "FAILS_E1"
        else:
            verdict = "NOT_EVALUATED"
        ex.append({
            "input": f"Candidate {r['candidate']}: "
                     + str(jload(WS / "prereg.json")["candidates"].get(r["candidate"], "")
                           or jload(WS / "prereg.json")["baselines"].get(r["candidate"], "")),
            "output": verdict,
            **{f"metadata_{k}": v for k, v in r.items()},
            "metadata_E1": e.get("E1"), "metadata_E2": e.get("E2"), "metadata_E3": e.get("E3"),
            "metadata_E4_status": e4.get("e4_status"),
            "predict_e1_pass": S(r.get("e1_pass")),
            "predict_e2_pass": S(r.get("e2_pass")),
            "predict_e3_pass": S(r.get("e3_pass")),
            "predict_verdict": verdict,
        })
    if ex:
        ds.append({"dataset": "candidate_decision_table", "examples": ex})
    return ds


LINEAGE_ARMS = [("Qwen--Qwen3-4B-Base", "base"), ("Qwen--Qwen3-4B", "instruct"),
                ("Qwen--Qwen3-4B-SafeRL", "safety_rl"),
                ("mlabonne--Qwen3-4B-abliterated", "abliterated"),
                ("CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6", "nonsafety_ft")]


def _item_level_examples(recog: dict) -> list:
    """RECOGNITION vs EXECUTION, prompt by prompt, across the commissioned Qwen3-4B lineage.

    For every stimulus: each arm's final-layer logit-lens refusal drive (log-sum-exp over the
    refusal-onset tokens minus the frequency-matched control set -- an EXECUTION readout of the
    activations through the model's own unembedding), and for the HARD measurement set each
    arm's held-out RECOGNITION probe score (5-fold CV logistic probe at the layer chosen on the
    fitting set). A prompt the abliterated model still RECOGNISES but no longer DRIVES toward
    refusal is the dissociation at the level of a single input.
    """
    stim = jload(ASSETS / "stimuli.json")["rows"]
    sid = np.array([s["set_id"] for s in stim])
    hard_pos = {int(i): k for k, i in enumerate(np.flatnonzero(sid == 1))}
    drives, probes = {}, {}
    for tag, arm in LINEAGE_ARMS:
        d = HARVEST / tag
        if not (d / "DONE").exists():
            continue
        try:
            rr, rc = np.load(d / "r_refusal.npy"), np.load(d / "r_control.npy")
            drives[arm] = (rr[:, -1] - rc[:, -1]).astype(float)
        except (OSError, ValueError):
            continue
        ps = (recog.get(tag) or {}).get("probe_scores")
        if isinstance(ps, list) and len(ps) == len(hard_pos):
            probes[arm] = ps
    if not drives:
        return []
    ex = []
    for i, srow in enumerate(stim):
        e = {"input": srow["text"],
             "output": ("harmful" if srow["y"] == 1 else "benign"),
             "metadata_stim_id": srow.get("stim_id"), "metadata_source": srow.get("source"),
             "metadata_set": "HARD (measures R)" if srow["set_id"] == 1 else "EASY (fits u)"}
        for arm, v in drives.items():
            e[f"predict_refusal_drive_final_layer_{arm}"] = S(round(float(v[i]), 4))
        if i in hard_pos:
            for arm, ps in probes.items():
                v = ps[hard_pos[i]]
                e[f"predict_recognition_probe_score_{arm}"] = S(
                    None if v is None else round(float(v), 4))
        ex.append(e)
    return ex


def _per_ckpt_rows(scored, recog, x10only):
    s3 = jload_maybe(LANE_C / "results" / "s3" / "s3_results.json", {}) or {}
    cols = s3.get("behavioural_columns", {}) or {}
    out = []
    for tag in sorted(set(list(scored) + list(x10only))):
        s_ = scored.get(tag, {}) or {}
        real = s_.get("real", {}) or {}
        meta = s_.get("meta", {}) or {}
        repo = meta.get("repo", tag.replace("--", "/"))
        tr = cols.get(lane_c_slug(repo))
        row = {"checkpoint": tag, "repo": repo, "family": meta.get("family"),
               "role": meta.get("role"), "l_star": real.get("l_star"),
               "l_dec": real.get("l_dec"), "l_act": real.get("l_act"),
               "split_half_cosine": real.get("split_half_cosine"),
               "primary_axis": real.get("primary_axis"),
               "weight_only": tag in x10only,
               "R_TPR": (recog.get(tag) or {}).get("R_TPR"),
               "truth_summary": (
                   f"judged harmful-compliance {tr['harmful_compliance_rate']:.3f}, "
                   f"over-refusal {tr['over_refusal_rate']:.3f}, safe-engagement "
                   f"{tr['safe_engagement_rate']:.3f} (n={tr['n_harm_judged']}/"
                   f"{tr['n_benign_judged']})" if tr else
                   "no judged behavioural row for this checkpoint"),
               }
        pred = {}
        for k in sp.HEADLINE + sp.BASELINES:
            v = real.get(k, x10only.get(tag, {}).get(k))
            if v is not None and np.isfinite(v):
                pred[k] = clean_float(v)
        row["predicts"] = pred
        out.append(row)
    return out


def _released(scored, recog, rows, x10only) -> None:
    import csv
    import shutil

    for f in ("prereg.json",):
        if (WS / f).exists():
            shutil.copy(WS / f, RELEASED / f)
    for f in ("pairs.json", "token_sets.json", "stimuli.json", "cells.json"):
        if (ASSETS / f).exists():
            shutil.copy(ASSETS / f, RELEASED / f)

    with open(RELEASED / "per_layer_candidate_curves.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["checkpoint", "curve", "layer", "value"])
        for tag, s_ in scored.items():
            real = (s_ or {}).get("real", {}) or {}
            for name in ("x1_g_curve", "auroc_by_layer", "cohen_by_layer", "x2_wm_curve",
                         "x8_drive_gap_curve", "x10_scar_curve", "x10_z_curve",
                         "x10_sigma_min_curve", "x10_sigma_mp_curve"):
                c = real.get(name)
                if isinstance(c, list):
                    for i, v in enumerate(c):
                        w.writerow([tag, name, i, clean_float(v)])
            for name in ("x10_scar_curve", "x10_z_curve"):
                c = (x10only.get(tag) or {}).get(name)
                if isinstance(c, list):
                    for i, v in enumerate(c):
                        w.writerow([tag, name, i, clean_float(v)])
        for tag, r in recog.items():
            c = (r or {}).get("auroc_by_layer")
            if isinstance(c, list):
                for i, v in enumerate(c):
                    w.writerow([tag, "R_auroc_by_layer", i, clean_float(v)])

    dd = RELEASED / "directions"
    dd.mkdir(exist_ok=True)
    n = 0
    for tag in scored:
        src = HARVEST / tag
        if not (src / "A_prompt.npy").exists():
            continue
        try:
            stim = jload(ASSETS / "stimuli.json")["rows"]
            y = np.array([s["y"] for s in stim])
            sid = np.array([s["set_id"] for s in stim])
            A = np.load(src / "A_prompt.npy").astype(np.float32)
            easy = sid == 0
            U = nm.diffmeans_directions(A[easy], y[easy])
            np.save(dd / f"{tag}__u_harm_per_layer.npy", U.astype(np.float32))
            n += 1
            del A
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"could not release directions for {tag}: {exc}")
    logger.info(f"released {n} direction files")


def _summary_md(md: dict, datasets: list) -> None:
    L: list[str] = []
    A = L.append
    A("# Does the model act on harm, or only see it?\n")
    A("**One mechanistic question.** " + md["one_mechanistic_question"] + "\n")
    A(f"- prereg SHA-256 `{md['prereg_sha256']}`")
    A(f"- survivor: **{md['survivor']}**"
      + (f" — {(md.get('confirmation') or {}).get('rationale')}"
         if (md.get('confirmation') or {}).get('rationale') else ""))
    A(f"- E4: **{md['e4'].get('e4_status')}** — {md['survivor_wording_rule']}")
    A(f"- OpenRouter spend: **${md['cost_ledger_total_usd']:.4f}**")
    A(f"- hardware: {md['hardware']['note']}\n")

    mv = md.get("mechanistic_verdict") or {}
    if mv.get("n_effective_pairs"):
        A("## The answer to the one mechanistic question\n")
        A(f"**{mv['answer']}**\n")
        rc, ex_ = mv.get("recognition", {}), mv.get("execution", {})
        b1 = ex_.get("final_layer_refusal_drive_gap_BL1", {})
        pk = ex_.get("peak_refusal_drive_gap_over_depth", {})
        x2 = ex_.get("X2_write_mass", {})
        x3 = ex_.get("X3_percept_to_refusal_gain", {})
        hd = mv.get("harm_direction_agreement", {})
        A(f"- EFFECTIVE pairs: {mv['n_effective_pairs']} ({', '.join(mv['pairs'])}).")
        A(f"- Recognition: median child−parent ΔR (TPR@5%FPR, HARD set) = "
          f"{fmt(rc.get('median_delta_R_TPR'),3)} over {rc.get('n')} pairs; TOST verdicts "
          f"{rc.get('tost_verdicts')}; pairs whose 90% interval shows the child recognising "
          f"less: {rc.get('pairs_with_interval_excluding_zero_child_lower') or 'none'}; median "
          f"shift of the first decodable layer = "
          f"{fmt(rc.get('median_shift_l_dec_layers'),1)} layers.")
        A(f"- Execution (PRIMARY, activations): the peak over depth of the harm-conditioned "
          f"logit-lens refusal drive falls in {pk.get('n_negative')}/{pk.get('n')} pairs (median Δ "
          f"{fmt(pk.get('median_delta'),2)}). Baseline BL1 (final layer only, logit-only): falls "
          f"in {b1.get('n_negative')}/{b1.get('n')} (median Δ {fmt(b1.get('median_delta'),2)}); X2 write mass falls in "
          f"{x2.get('n_negative')}/{x2.get('n')} (median Δ {fmt(x2.get('median_delta'),3)}); X3 "
          f"falls in {x3.get('n_negative')}/{x3.get('n')} (median Δ {fmt(x3.get('median_delta'),3)}).")
        A(f"- Harm-direction agreement parent vs child: shallow quarter median |cos| "
          f"{fmt(hd.get('shallow_quarter_median_abs_cos'),3)}, deep half "
          f"{fmt(hd.get('deep_half_median_abs_cos'),3)}.")
        A(f"\n> {mv.get('caveats')}\n")


    # ---- what the ground-truth control established, BEFORE any real result
    t2 = md.get("t2_t3_ground_truth_lesion_control") or {}
    if t2.get("alpha_sweep"):
        A("## Ground truth first: do X2 and X10 measure what they claim?\n")
        A("A KNOWN rank-one orthogonalisation at a known direction `u0` and a swept `alpha`, "
          "applied to real Qwen3-0.6B weights.\n")
        A("| alpha | X2 write mass along u0 | algebraic prediction (1−α)² | X10 max z | cos(vmin, u0) |")
        A("|---|---|---|---|---|")
        for r in t2["alpha_sweep"]:
            A(f"| {r['alpha']:.2f} | {fmt(r['X2_write_mass_u0'])} | "
              f"{r['X2_write_mass_algebraic_prediction']:.4f} | {fmt(r['X10_max_z'],2)} | "
              f"{fmt(r['cos_vmin_u0_edited'],3)} |")
        alg = t2.get("X2_matches_algebraic_prediction") or {}
        A("")
        A(f"- **X2 is exact on real weights**: max |write mass − (1−α)²| = "
          f"{fmt(alg.get('max_abs_error_vs_(1-alpha)^2'), 6)}.")
        A(f"- **Detection floor**: the scar only appears at α ≥ "
          f"**{t2.get('detection_floor_alpha_by_z_jump')}** (z jump) / "
          f"**{t2.get('detection_floor_alpha_by_null_direction')}** (the near-null direction "
          "becoming the deleted one). Below that, a partial abliteration strips write mass "
          "exactly as predicted yet leaves **no weights-only scar** — it would be missed.")
        u = t2.get("UNIFORM_EDIT_BLINDS_THE_Z_FORM") or {}
        if u.get("z_form_collapses_under_uniform_edit"):
            A(f"- **The registered PRIMARY form of X10 fails this control under a UNIFORM "
              f"edit.** {u.get('finding')}")
            A(f"  - {u.get('consequence')}")
        t3 = t2.get("T3_negative_control") or {}
        A(f"- **T3 negative control**: on the unedited model X10 max z = "
          f"{fmt(t3.get('unedited_X10_max_z'),2)} and cos(vmin,u0) = "
          f"{fmt(t3.get('unedited_cos_vmin_u0'),3)} — it does **not** fire.")
        A("")

    # ---- the premise
    A("## The premise: is RECOGNITION preserved?\n")
    rt = [r for r in md["recognition_table"] if not r.get("error")]
    if rt:
        A("| checkpoint | TPR@FPR | n benign | AUROC (SATURATED — not a test) | layer |")
        A("|---|---|---|---|---|")
        for r in rt[:40]:
            A(f"| {r['checkpoint']} | {fmt(r.get('R_TPR'),3)} @ {r.get('R_TPR_fpr_level')} | "
              f"{r.get('n_benign_hard')} | {fmt(r.get('R_AUROC'),3)} | {r.get('best_layer')} |")
        A("")
    else:
        A("_No recognition rows: no checkpoint completed the activation harvest._\n")
    if md["recognition_equivalence"]:
        A("### Parent vs child equivalence (TOST on PAIRED bootstrap draws)\n")
        A("| pair | effectiveness | parent TPR | child TPR | verdict | TOST interval |")
        A("|---|---|---|---|---|---|")
        for e in md["recognition_equivalence"]:
            A(f"| {e['pair']} | {e.get('effectiveness')} | {fmt(e.get('R_TPR_parent'),3)} | "
              f"{fmt(e.get('R_TPR_child'),3)} | **{e['equivalence_verdict']}** | "
              f"[{fmt(e['tost_interval'][0],3)}, {fmt(e['tost_interval'][1],3)}] |")
        A("")
    A("> " + md["recognition_premise_note"] + "\n")

    cl = md.get("commissioned_lineage") or {}
    if cl.get("rows"):
        A("## The commissioned comparison: base, instruct, safety-RL, abliterated\n")
        A("| arm | harmful compl. | over-refusal | R TPR@5%FPR | recognition onset l_dec (frac) "
          "| HARD-set onset | execution onset l_act (frac) | peak refusal-drive gap (layer) | "
          "final-layer gap (BL1) | X3 | X2 | X10_abs | BL7 |")
        A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in cl["rows"]:
            A(f"| {r['arm']} | {fmt(r.get('harmful_compliance_rate'),3)} | "
              f"{fmt(r.get('over_refusal_rate'),3)} | {fmt(r.get('R_TPR_at_5pct_FPR'),3)} | "
              f"{r.get('l_dec_recognition_onset')} ({fmt(r.get('f_dec'),2)}) | "
              f"{r.get('hard_set_recognition_onset_layer')} | "
              f"{r.get('l_act_execution_onset')} ({fmt(r.get('f_act'),2)}) | "
              f"{fmt(r.get('refusal_drive_gap_peak'),2)} ({r.get('refusal_drive_gap_peak_layer')}) | "
              f"{fmt(r.get('refusal_drive_gap_final_layer_BL1'),2)} | {fmt(r.get('X3'),3)} | "
              f"{fmt(r.get('X2'),3)} | {fmt(r.get('X10_abs'),3)} | {fmt(r.get('BL7_JORAK_A'),3)} |")
        A("")
        A("> " + cl["reading"] + "\n")

    rv = md.get("recognition_vs_execution_depth_profile") or {}
    if rv.get("status") == "RUN" and rv.get("rows"):
        A("## Recognition versus execution, as a depth profile\n")
        A("Per-layer |cos| between each parent's harm direction and its child's, both refit "
          "parent-free.\n")
        A("| pair | effectiveness | ΔHC | shallow-quarter |cos| | deep-half |cos| | divergence layer | depth frac |")
        A("|---|---|---|---|---|---|---|")
        for r in rv["rows"]:
            A(f"| {r['pair']} {r['family']} | {r['effectiveness']} | {fmt(r.get('delta_HC'),3)} "
              f"| {fmt(r.get('abs_cos_shallow_quarter_median'),3)} "
              f"| {fmt(r.get('abs_cos_deep_half_median'),3)} | {r.get('divergence_layer')} "
              f"| {fmt(r.get('divergence_depth_fraction'),3)} |")
        A("")
        A(f"Across EFFECTIVE pairs: shallow-quarter median |cos| = "
          f"**{fmt(rv.get('effective_pairs_shallow_median_abs_cos'),3)}**, deep-half median "
          f"|cos| = **{fmt(rv.get('effective_pairs_deep_median_abs_cos'),3)}**.\n")
        A("> " + rv["reading"] + "\n")

    # ---- how the checkpoints differ in activation
    cm = md.get("cross_checkpoint_direction_matrix") or {}
    if cm.get("status") == "RUN" and cm.get("pairs"):
        A("## How the checkpoints differ IN ACTIVATION SPACE\n")
        A("Per-layer |cos| between each checkpoint's OWN parent-free harm direction.\n")
        A("| a | b | median |cos| | deep-half median | min | max |")
        A("|---|---|---|---|---|---|")
        for r in cm["pairs"][:30]:
            A(f"| {r['a']} | {r['b']} | {fmt(r['abs_cos_median'],3)} | "
              f"{fmt(r['abs_cos_deep_half_median'],3)} | {fmt(r['abs_cos_min'],3)} | "
              f"{fmt(r['abs_cos_max'],3)} |")
        A("")
        A("> " + cm["reading"] + "\n")

    # ---- edit recipes
    fp = md.get("weight_fingerprints_summary") or {}
    if fp:
        A("## The edit recipes are NOT one operator\n")
        A("| pair | stratum | implied alpha (median) | rank-1 share | cos(shallow, deep) | embed edited |")
        A("|---|---|---|---|---|---|")
        for k, v in sorted(fp.items()):
            A(f"| {k} | **{v.get('stratum')}** | {fmt(v.get('implied_alpha_median'),4)} | "
              f"{fmt(v.get('rank1_share_median'),4)} | {fmt(v.get('cos_shallow_deep'),4)} | "
              f"{v.get('embed_tokens_edited')} |")
        A("")
        A("> A GLOBAL_RANK1 edit removes ONE direction shared across all layers; a "
          "PER_LAYER_RANK1 edit removes a different direction at every layer. Pooling the two "
          "would average two different operators, which is why E1(a) is never pooled across "
          "strata.\n")

    # ---- the screen
    A("## The screen (S-table)\n")
    A("E1 status is PASS / FAIL / UNDER_POWERED (no stratum reaches 4 EFFECTIVE pairs). The "
      "pooled row is the labelled SECONDARY reading and never decides E1. MDE is in pooled "
      "shuffled-label SD units, beside the 0.50-SD E2 rule.\n")
    A("| candidate | E1 status | largest stratum (n) | pooled secondary: same sign / CI≠0 of n | "
      "E1(b) spec | E2 | E2 margin (SD) | E3 margin vs BL1 | E4 | escapes band | MDE (SD) | "
      "prior art | survivor-eligible |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in md["s_table"]:
        ps = r.get("e1_pooled_secondary") or {}
        A(f"| **{r['candidate']}** | {r.get('e1_status')} | {r.get('e1_stratum')} "
          f"({r.get('e1_n_pairs')}) | {ps.get('same_signed')} / "
          f"{ps.get('n_ci_excluding_zero') if ps.get('n_ci_excluding_zero') is not None else ps.get('n_outside_parent_band')} of {ps.get('n')} | "
          f"{r.get('e1_specificity_pass')} | {r.get('e2_pass')} | "
          f"{fmt(r.get('e2_margin_pooled_null_sd'),2)} | {fmt(r.get('e3_margin_vs_BL1'),3)} | "
          f"{r.get('e4_status')} | {r.get('escapes_shuffled_band_n_pairs')} | "
          f"{fmt(r.get('mde_beside_threshold'),2)} | {r.get('prior_art_verdict')} | "
          f"{'NO (' + str(r.get('prior_art_verdict')) + ')' if r.get('excluded_by_prior_art') else ('yes' if r.get('is_headline_candidate') else ('baseline' if str(r['candidate']).startswith('BL') else 'carried / secondary'))} |")
    A("")
    bpd = [r for r in (md.get("budget_pair_deltas") or []) if isinstance(r, dict) and "by_k" in r]
    if bpd:
        A("## Zero-to-few prompts: the pair difference at every prompt budget k\n")
        A("Delta(k) = child minus parent with u refit on k fitting prompts (k/2 per class; draw r "
          "uses the SAME prompts in both checkpoints), in pooled shuffled-label SD, with the share "
          "of draws agreeing in sign. k=0 rows are weights-only. Reported at EVERY k, never as a "
          "scan maximum; k=128 exceeds the 96-prompt fitting set, so every draw uses all 96.\n")
        keys = ["X2", "X3", "X8", "BL1_REFLOGIT"]
        A("| pair | label | k=0: ΔX10_abs / ΔBL7 | " + " | ".join(
            f"k={k}: " + " / ".join(keys) for k in (4, 16, 128)) + " |")
        A("|---|---|---|" + "---|" * 3)
        for r in bpd:
            k0 = r["by_k"].get("0") or {}
            cells = []
            for k in ("4", "16", "128"):
                c = r["by_k"].get(k) or {}
                vals = []
                for kk in keys:
                    v = c.get(kk) or {}
                    m = v.get("mean_delta_pooled_sd")
                    vals.append(f"{fmt(m, 1)}({fmt(v.get('frac_draws_same_sign_as_mean'), 1)})"
                                if m is not None else "n/a")
                cells.append(" / ".join(vals))
            A(f"| {r['pair']} | {r.get('effectiveness')} | {fmt(k0.get('X10_abs'), 2)} / "
              f"{fmt(k0.get('BL7_JORAK_A'), 2)} | " + " | ".join(cells) + " |")
        A("")

    A("### Response-site readouts (X5, X11): where they are defined\n")
    for k, v in md["not_computed"].items():
        if isinstance(v, dict):
            A(f"- **{k}** — {v.get('status')} Undefined: "
              f"{[u['checkpoint'] for u in v.get('undefined', [])] or 'none'}; "
              f"not harvested: {v.get('not_harvested') or 'none'}.")
        else:
            A(f"- **{k}** — {v}")
    A("")

    # ---- audits
    A("## Declared empty or missing blocks\n")
    for b_ in md["empty_blocks_declared"]:
        A(f"- {b_}")
    A("")
    lk = md.get("t5_leakage_audits") or {}
    if lk.get("checks"):
        A(f"## Leakage audits ({lk.get('n_pass')}/{lk.get('n_checks')} pass)\n")
        for c in lk["checks"]:
            A(f"- {'PASS' if c['pass'] else 'FAIL'} `{c['check']}` — {c['detail']}")
        A("")
    t1 = md.get("t1_unit_tests") or {}
    if t1.get("tests"):
        A(f"## Arithmetic unit tests ({t1.get('n_pass')}/{t1.get('n_tests')} pass)\n")
        for t in t1["tests"]:
            A(f"- {'PASS' if t['pass'] else 'FAIL'} `{t['name']}`")
        A("")
    A("## Inherited-claims audit\n")
    for k, v in md["inherited_claims_audit"].items():
        if isinstance(v, dict) and "resolution" in v:
            A(f"- **{k}** — {v['resolution']}")
    A("")
    ci = md.get("cross_iteration_direction_check") or {}
    if ci.get("status") == "RUN":
        A("## Cross-iteration reproducibility of the harm direction\n")
        A(f"panel median |cos| vs iteration 1 Lane A's released directions: "
          f"**{fmt(ci.get('panel_median_abs_cos'),3)}**\n")
        A("| checkpoint | median |cos| | deep-half median | max |")
        A("|---|---|---|---|")
        for r in ci["rows"]:
            if "abs_cos_median" in r:
                A(f"| {r['checkpoint']} | {fmt(r['abs_cos_median'],3)} | "
                  f"{fmt(r['abs_cos_deep_half_median'],3)} | {fmt(r['abs_cos_max'],3)} |")
        A("")
        A("> " + ci["interpretation"] + "\n")
    A("## Citation hygiene: what was checked, corrected and withdrawn\n")
    uc = md["unverified_citations_refused"]
    A(uc.get("_method", "") + "\n")
    for k, v in uc.items():
        if k == "_method":
            continue
        if isinstance(v, dict):
            A(f"- **`{k}`** — named as: {v.get('named_as')}. **{v.get('status')}** "
              f"{v.get('what_was_checked')}")
        else:
            A(f"- **`{k}`** — {v}")
    A("")
    A(f"## Deviations ({len(md['deviations'])})\n")
    for d in md["deviations"][:80]:
        A(f"- `{d.get('kind')}` {d.get('what') or d.get('tag') or d.get('repo')}: "
          f"{str(d.get('detail') or d.get('error') or '')[:300]}")
    A("")
    (OUT / "SUMMARY.md").write_text("\n".join(L), encoding="utf-8")
    logger.info(f"wrote {OUT / 'SUMMARY.md'}")


# ----------------------------------------------------------------------------------
LANE_A_DIR_MAP = {
    "Qwen--Qwen3-4B": "Qwen3-4B",
    "mlabonne--Qwen3-4B-abliterated": "Qwen3-4B-abliterated",
    "Qwen--Qwen3-4B-SafeRL": "Qwen3-4B-SafeRL",
    "Qwen--Qwen3-4B-Base": "Qwen3-4B-Base-chat",
    "Qwen--Qwen3-4B-Base--plain": "Qwen3-4B-Base-plain",
    "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6": "NonSafetyFT-STaR",
    "RandInit-Qwen3-4B": "RandInit-4B",
}


def _load_dirs(d: Path) -> dict:
    U = {}
    for f in sorted(d.glob("*__u_harm_per_layer.npy")):
        tag = f.name.replace("__u_harm_per_layer.npy", "")
        try:
            a = np.load(f).astype(np.float64)
            U[tag] = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-12)
        except Exception:  # noqa: BLE001
            continue
    return U


def cross_iteration_direction_check() -> dict:
    """Do THIS lane's refit harm directions reproduce iteration 1 Lane A's released ones?

    Lane A released, per checkpoint, a float32 (37, 2560) array holding one direction PER
    LAYER for the Qwen3-4B lineage. This lane refits its own direction, parent-free, from a
    DIFFERENT prompt set, on a different substrate and in a different dtype. A high per-layer
    |cos| is therefore a genuine cross-iteration reproducibility check on the one object
    every candidate depends on; a low one says the harm axis is prompt-set dependent, which
    would be a finding in itself and is reported either way.
    """
    lane_a = LANE_C.parent / "gen_art_experiment_1" / "out" / "released" / "directions"
    ours = RELEASED / "directions"
    if not lane_a.exists() or not ours.exists():
        return {"status": "UNAVAILABLE", "lane_a_dir": str(lane_a)}
    U = _load_dirs(ours)
    out = []
    for tag, a_name in LANE_A_DIR_MAP.items():
        f_theirs = lane_a / f"{a_name}__r_ablit.npy"
        if tag not in U or not f_theirs.exists():
            continue
        try:
            V = np.load(f_theirs).astype(np.float64)
        except Exception as exc:  # noqa: BLE001
            out.append({"checkpoint": tag, "error": str(exc)})
            continue
        Un = U[tag]
        if Un.shape != V.shape:
            out.append({"checkpoint": tag, "error": f"shape {Un.shape} vs {V.shape}"})
            continue
        Vn = V / np.maximum(np.linalg.norm(V, axis=1, keepdims=True), 1e-12)
        cos = np.abs(np.einsum("ld,ld->l", Un, Vn))
        out.append({"checkpoint": tag, "lane_a_file": f_theirs.name,
                    "n_layers": int(cos.size),
                    "abs_cos_median": float(np.median(cos)),
                    "abs_cos_max": float(np.max(cos)),
                    "abs_cos_deep_half_median": float(np.median(cos[cos.size // 2:])),
                    "per_layer_abs_cos": [float(c) for c in cos]})
    med = [r["abs_cos_median"] for r in out if "abs_cos_median" in r]
    return {"status": "RUN" if out else "NO_OVERLAP", "rows": out,
            "panel_median_abs_cos": float(np.median(med)) if med else None,
            "interpretation": (
                "This lane's direction is refit from a DIFFERENT prompt set and substrate "
                "than iteration 1 Lane A's. A high per-layer |cos| means the parent-free harm "
                "axis is a property of the CHECKPOINT rather than of the prompt set that "
                "fitted it; a low one means it is prompt-set dependent, which would undercut "
                "every candidate built on it. Reported either way, with no threshold chosen "
                "after the fact.")}


def _peak_drive(scored: dict, repo: str):
    real = ((scored.get(slug(repo)) or {}).get("real") or {})
    c = real.get("x8_drive_gap_curve")
    v = [float(x) for x in (c or []) if _isfin(x)]
    return max(v) if v else None


def mechanistic_verdict(rows: list, equiv: list, rv: dict, cfg: dict,
                        scored: dict | None = None) -> dict:
    """The answer to the ONE mechanistic question, computed from the pair tables (descriptive:
    E1 is under-powered by construction of the panel and E4 was not evaluated, so this is a
    READOUT-level answer, never an EXECUTION claim in the causal sense)."""
    eff = [r for r in rows if r.get("effectiveness") == "EFFECTIVE"]
    eq = {e["pair"]: e for e in equiv}
    prof = {r["pair"]: r for r in (rv or {}).get("rows", [])}
    out: dict = {"n_effective_pairs": len(eff), "pairs": [r["pair"] for r in eff]}
    # recognition side
    dR, verdicts, dldec = [], [], []
    for r in eff:
        e = eq.get(r["pair"])
        if e and _isfin(e.get("R_TPR_parent")) and _isfin(e.get("R_TPR_child")):
            dR.append(float(e["R_TPR_child"]) - float(e["R_TPR_parent"]))
            verdicts.append(e.get("equivalence_verdict"))
        pr = prof.get(r["pair"])
        if pr and pr.get("parent_l_dec") is not None and pr.get("child_l_dec") is not None:
            dldec.append(float(pr["child_l_dec"]) - float(pr["parent_l_dec"]))
    # execution side
    def deltas(key):
        v = [(r.get("deltas", {}).get(key) or {}).get("delta_raw") for r in eff]
        return [float(x) for x in v if _isfin(x)]
    dBL1, dX2, dX3 = deltas("BL1_REFLOGIT"), deltas("X2"), deltas("X3")
    # PRIMARY execution readout: the PEAK over depth of the harm-conditioned logit-lens refusal
    # drive (an activation readout through the model's own unembedding). The final-layer value
    # alone is BL1, a logit-only baseline, and is reported beside it, never instead of it.
    dPK = []
    for r in eff:
        a, b = _peak_drive(scored or {}, r["parent"]), _peak_drive(scored or {}, r["child"])
        if a is not None and b is not None:
            dPK.append(b - a)
    shallow = [prof[p_]["abs_cos_shallow_quarter_median"] for p_ in out["pairs"]
               if p_ in prof and _isfin(prof[p_].get("abs_cos_shallow_quarter_median"))]
    deep = [prof[p_]["abs_cos_deep_half_median"] for p_ in out["pairs"]
            if p_ in prof and _isfin(prof[p_].get("abs_cos_deep_half_median"))]
    med = lambda v: float(np.median(v)) if v else None  # noqa: E731
    out.update({
        "recognition": {"median_delta_R_TPR": med(dR), "n": len(dR),
                        "tost_verdicts": {k: verdicts.count(k) for k in set(verdicts)},
                        "median_shift_l_dec_layers": med(dldec), "n_l_dec": len(dldec)},
        "execution": {"peak_refusal_drive_gap_over_depth": {
                          "median_delta": med(dPK), "n_negative": sum(1 for x in dPK if x < 0),
                          "n": len(dPK), "role": "PRIMARY execution readout (activations)"},
                      "final_layer_refusal_drive_gap_BL1": {
                          "median_delta": med(dBL1), "n_negative": sum(1 for x in dBL1 if x < 0),
                          "n": len(dBL1)},
                      "X2_write_mass": {"median_delta": med(dX2),
                                        "n_negative": sum(1 for x in dX2 if x < 0), "n": len(dX2)},
                      "X3_percept_to_refusal_gain": {"median_delta": med(dX3),
                                                     "n_negative": sum(1 for x in dX3 if x < 0),
                                                     "n": len(dX3)}},
        "harm_direction_agreement": {"shallow_quarter_median_abs_cos": med(shallow),
                                     "deep_half_median_abs_cos": med(deep)},
    })
    margin = float(cfg.get("equivalence_margin_tpr", 0.10))
    n_diff_down = sum(1 for r in eff if (eq.get(r["pair"]) or {}).get("equivalence_verdict") == "DIFFERENT"
                      and _isfin((eq.get(r["pair"]) or {}).get("point_estimate"))
                      and float(eq[r["pair"]]["point_estimate"]) > 0)
    # pairs whose whole 90% TOST interval says the CHILD recognises less (parent - child > 0)
    partial = [r["pair"] for r in eff
               if _isfin(((eq.get(r["pair"]) or {}).get("tost_interval") or [None])[0])
               and float(eq[r["pair"]]["tost_interval"][0]) > 0]
    out["recognition"]["pairs_with_interval_excluding_zero_child_lower"] = partial
    rec_lost = bool(len(dR) and n_diff_down > len(dR) / 2)
    rec_kept = bool(dR and abs(med(dR)) < margin and (not dldec or abs(med(dldec)) <= 2))
    exec_down = bool(dPK and sum(1 for x in dPK if x < 0) >= max(1, int(np.ceil(2 * len(dPK) / 3))))
    if rec_lost:
        answer = ("RECOGNITION: the recognition axis R separates parent from child beyond the "
                  "registered margin in most effective pairs -- the hypothesis's premise is WRONG "
                  "and probe-based safety scores would be vindicated.")
    elif rec_kept and exec_down:
        answer = ("EXECUTION (at the level of a READOUT): the children keep their parents' "
                  "recognition -- the same onset depth and a median held-out TPR change inside "
                  "the registered margin -- while the harm-conditioned refusal drive that the "
                  "model's own unembedding reads from its activations falls in most effective "
                  "pairs. What abliteration removes is acting on harm, not seeing it.")
        if partial:
            answer += (f" Qualification: in {len(partial)} of {len(dR)} effective pairs "
                       f"({', '.join(partial)}) the child's recognition is PARTIALLY lower -- the "
                       "whole 90% TOST interval of parent-minus-child TPR lies above zero, though "
                       "not beyond the equivalence margin -- so recognition is largely, not "
                       "uniformly, preserved.")
    else:
        answer = ("MIXED / INCONCLUSIVE at this n: see the recognition and execution rows; "
                  "neither the recognition-kept nor the execution-removed pattern holds across "
                  "most effective pairs.")
    out["answer"] = answer
    out["caveats"] = ("Descriptive: E1(a) is UNDER-POWERED by construction (no edit-recipe "
                      "stratum holds 4 EFFECTIVE pairs), the TOST intervals on TPR@5%FPR with 80 "
                      "benign HARD items are wide, and E4 (the causal write-handle test) was not "
                      "evaluated, so 'execution' names a readout, not a demonstrated mechanism.")
    return out


def _hard_onset(au) -> int | None:
    v = [float(x) if _isfin(x) else np.nan for x in (au or [])]
    if not v or not np.isfinite(np.nanmax(v)):
        return None
    thr = 0.5 + 0.9 * (np.nanmax(v) - 0.5)
    idx = [i for i, x in enumerate(v) if np.isfinite(x) and x >= thr]
    return int(idx[0]) if idx else None


def commissioned_lineage(scored: dict, recog: dict, judge_ext: dict, x10only: dict) -> dict:
    """THE COMMISSIONED THREE-MODEL COMPARISON (+ the abliterated child and the non-safety
    control), one row per arm, recognition-side and execution-side readouts side by side.

    Recognition side: the depth at which harm first becomes decodable (l_dec, the earliest layer
    whose cross-fitted diff-in-means AUROC on the fitting set reaches 0.95) and R, the held-out
    TPR at 5% FPR on the HARD set. Execution side: the per-layer logit-lens REFUSAL DRIVE
    (log-sum-exp over refusal-onset tokens minus a frequency-matched control set, harmful minus
    benign), its peak and final-layer values, the layer where it rises fastest (l_act), and the
    closed-form percept-to-refusal gain X3. Weight side: X2 write mass and the X10 scar.
    """
    s3 = jload_maybe(LANE_C / "results" / "s3" / "s3_results.json", {}) or {}
    cols = s3.get("behavioural_columns", {}) or {}
    arms = [("Qwen/Qwen3-4B-Base", "pretrained base"),
            ("CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6", "NON-safety fine-tune of Base (control)"),
            ("Qwen/Qwen3-4B", "official instruct"),
            ("Qwen/Qwen3-4B-SafeRL", "official safety RL"),
            ("mlabonne/Qwen3-4B-abliterated", "community abliterated child of Qwen3-4B")]
    rows = []
    for repo, role in arms:
        tag = slug(repo)
        s_ = scored.get(tag) or {}
        real = s_.get("real") or {}
        r = recog.get(tag) or {}
        beh = cols.get(repo.replace("/", "__"))
        src = "iteration-1 Lane C (n=45+45)"
        if beh is None and (judge_ext.get(tag) or {}).get("columns"):
            beh = judge_ext[tag]["columns"]
            src = "judge extension run by THIS lane with Lane C's exact protocol"
        drv = real.get("x8_drive_gap_curve")
        drv = [v for v in drv] if isinstance(drv, list) else None
        dv = [v for v in (drv or []) if _isfin(v)]
        rows.append({
            "arm": role, "repo": repo, "harvested": "real" in s_,
            "harmful_compliance_rate": (beh or {}).get("harmful_compliance_rate"),
            "over_refusal_rate": (beh or {}).get("over_refusal_rate"),
            "safe_engagement_rate": (beh or {}).get("safe_engagement_rate"),
            "behaviour_source": src if beh else "NOT JUDGED",
            "R_TPR_at_5pct_FPR": r.get("R_TPR"), "R_TPR_se": r.get("R_TPR_se"),
            "R_AUROC_saturated": r.get("R_AUROC"),
            "l_dec_recognition_onset": real.get("l_dec"), "f_dec": real.get("f_dec"),
            "hard_set_recognition_onset_layer": _hard_onset(r.get("auroc_by_layer")),
            "hard_set_recognition_onset_rule": ("first layer whose cross-fitted diff-in-means "
                                                "AUROC on the HARD set reaches 0.5 + 0.9 x "
                                                "(its own maximum - 0.5), i.e. 90% of the "
                                                "above-chance separation (descriptive)"),
            "l_act_execution_onset": real.get("l_act"), "f_act": real.get("f_act"),
            "X8_lag": real.get("X8"),
            "refusal_drive_gap_peak": (max(dv) if dv else None),
            "refusal_drive_gap_peak_layer": (int(np.nanargmax(np.array(
                [v if _isfin(v) else -np.inf for v in drv]))) if dv else None),
            "refusal_drive_gap_final_layer_BL1": real.get("BL1_REFLOGIT"),
            "X1": real.get("X1"), "X2": real.get("X2"), "X3": real.get("X3"),
            "X3_finallayer": real.get("X3_finallayer"), "X5": real.get("X5"),
            "X11": real.get("X11"),
            "X10": real.get("X10", (x10only.get(tag) or {}).get("X10")),
            "X10_abs": real.get("X10_abs", (x10only.get(tag) or {}).get("X10_abs")),
            "BL7_JORAK_A": real.get("BL7_JORAK_A", (x10only.get(tag) or {}).get("BL7_JORAK_A")),
            "l_star": real.get("l_star"), "primary_axis": real.get("primary_axis"),
            "refusal_drive_gap_curve": drv,
            "recognition_auroc_by_layer_fitting_set": real.get("auroc_by_layer"),
        })
    return {"rows": rows,
            "reading": ("RECOGNITION is read where harm first becomes decodable and on the HARD "
                        "held-out set; EXECUTION is read as the logit-lens refusal drive that "
                        "harm produces at each depth. If the abliterated child keeps the "
                        "instruct model's recognition onset and R while its refusal drive "
                        "collapses, the axis that separates them is EXECUTION, not "
                        "RECOGNITION. The logit-lens drive is a readout of activations through "
                        "the model's own unembedding; the final-layer value alone (BL1) is a "
                        "logit-only BASELINE, never the deliverable.")}


def cross_checkpoint_direction_matrix() -> dict:
    """How do the checkpoints differ IN ACTIVATION SPACE? -- the direct comparison.

    For every pair of harvested checkpoints sharing a hidden size, the per-layer absolute
    cosine between their OWN parent-free harm directions. If a base model, its safety-tuned
    child and its abliterated child all carry the SAME harm direction, then what changed
    between them is not the direction the model uses to represent harm.
    """
    dd = RELEASED / "directions"
    if not dd.exists():
        return {"status": "UNAVAILABLE"}
    U = _load_dirs(dd)
    if len(U) < 2:
        return {"status": "TOO_FEW_CHECKPOINTS", "n": len(U)}
    tags = sorted(U)
    fam = {t: ((jload_maybe(HARVEST / t / "meta.json", {}) or {}).get("family")) for t in tags}
    rows = []
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            a, b = U[tags[i]], U[tags[j]]
            # residual bases of independently trained models are NOT aligned, so a cosine is
            # only meaningful WITHIN one lineage: same family AND same architecture shape
            fa, fb = fam.get(tags[i]), fam.get(tags[j])
            is_null_row = a.shape == b.shape and "randinit" in (fa, fb) and fa != fb
            if a.shape != b.shape or (fa != fb and not is_null_row) or None in (fa, fb):
                continue
            cos = np.abs(np.einsum("ld,ld->l", a, b))
            rows.append({"a": tags[i], "b": tags[j], "n_layers": int(cos.size),
                         "role": ("NULL REFERENCE (trained vs architecture-identical random init)"
                                  if is_null_row else "within-lineage comparison"),
                         "abs_cos_median": float(np.median(cos)),
                         "abs_cos_min": float(np.min(cos)),
                         "abs_cos_max": float(np.max(cos)),
                         "abs_cos_deep_half_median": float(np.median(cos[cos.size // 2:])),
                         "per_layer_abs_cos": [float(c) for c in cos]})
    lin = ("Qwen--Qwen3-4B", "mlabonne", "CohenQu", "RandInit-Qwen3-4B")
    qwen4b = [r for r in rows if r["a"].startswith(lin) and r["b"].startswith(lin)]
    return {"status": "RUN", "n_checkpoints": len(tags), "checkpoints": tags,
            "pairs": rows, "commissioned_qwen3_4b_lineage": qwen4b,
            "reading": (
                "A HIGH per-layer |cos| between an instruct parent and its abliterated child "
                "says the two still represent harm along the SAME axis -- the uncensoring did "
                "not move the direction, so whatever it changed is downstream of the "
                "representation. A LOW one says the direction itself moved. The same "
                "comparison across Qwen3-4B-Base, Qwen3-4B, Qwen3-4B-SafeRL and the "
                "abliterated child IS the commissioned activation-level comparison, reduced "
                "to one number per layer per pair. Raw per-layer curves ship in "
                "released/per_layer_candidate_curves.csv.")}


# ----------------------------------------------------------------------------------
def recognition_vs_execution_depth_profile(pairs_doc: dict, scored: dict) -> dict:
    """THE COMMISSIONED COMPARISON, as one profile per pair.

    For each parent -> child pair, the per-layer |cos| between the two checkpoints' OWN
    parent-free harm directions, plus the depth at which that agreement breaks.

    This is the sharpest form of the lane's question. If the child still represents harm
    along the SAME axis where harm is first RECOGNISED, but along a DIFFERENT axis in the
    layers where the model would ACT on it, then uncensoring did not remove the model's
    ability to see harm -- it changed what the deep layers do with it. A flat profile (high
    |cos| everywhere) would say the direction is untouched and the change is elsewhere
    entirely; a uniformly low profile would say the representation itself moved.
    """
    dd = RELEASED / "directions"
    if not dd.exists():
        return {"status": "UNAVAILABLE"}
    U = _load_dirs(dd)
    rows = []
    for p in pairs_doc["pairs"]:
        pt, ct = slug(p["parent"]), slug(p["child"])
        if pt not in U or ct not in U or U[pt].shape != U[ct].shape:
            continue
        cos = np.abs(np.einsum("ld,ld->l", U[pt], U[ct]))
        L = cos.size - 1
        half = cos.size // 2
        # the first layer, after the shallow quarter, where agreement falls below 0.8
        start = max(1, cos.size // 4)
        below = np.flatnonzero(cos[start:] < 0.80)
        l_div = int(start + below[0]) if below.size else None
        rec = (scored.get(ct) or {}).get("real") or {}
        prec = (scored.get(pt) or {}).get("real") or {}
        rows.append({
            "pair": p["pair"], "parent": p["parent"], "child": p["child"],
            "family": p["family"], "effectiveness": p.get("effectiveness"),
            "stratum": p.get("stratum"), "delta_HC": p.get("delta_HC"),
            "n_layers": int(cos.size),
            "abs_cos_shallow_quarter_median": float(np.median(cos[1:start])) if start > 1
            else None,
            "abs_cos_deep_half_median": float(np.median(cos[half:])),
            "abs_cos_median": float(np.median(cos)),
            "divergence_layer": l_div,
            "divergence_depth_fraction": (float(l_div / L) if (l_div is not None and L)
                                          else None),
            "parent_l_dec": prec.get("l_dec"), "child_l_dec": rec.get("l_dec"),
            "parent_f_dec": prec.get("f_dec"), "child_f_dec": rec.get("f_dec"),
            "parent_l_act": prec.get("l_act"), "child_l_act": rec.get("l_act"),
            "per_layer_abs_cos": [float(c) for c in cos],
        })
    deep = [r["abs_cos_deep_half_median"] for r in rows
            if r["effectiveness"] == "EFFECTIVE" and r["abs_cos_deep_half_median"] is not None]
    shal = [r["abs_cos_shallow_quarter_median"] for r in rows
            if r["effectiveness"] == "EFFECTIVE"
            and r["abs_cos_shallow_quarter_median"] is not None]
    return {
        "status": "RUN", "rows": rows,
        "effective_pairs_shallow_median_abs_cos": float(np.median(shal)) if shal else None,
        "effective_pairs_deep_median_abs_cos": float(np.median(deep)) if deep else None,
        "reading": (
            "Per-layer |cos| between an instruct parent's harm direction and its abliterated "
            "child's, both refit parent-free on that checkpoint's own activations. High "
            "SHALLOW agreement with low DEEP agreement is the recognition-versus-execution "
            "dissociation in its most direct form: the child still encodes harm the same way "
            "where harm is first decodable, and differently where the model would act on it. "
            "Reported for NULL_EDIT and ANOMALOUS pairs too, so a reader can see whether the "
            "profile is specific to pairs that actually changed behaviour."),
    }


if __name__ == "__main__":
    raise SystemExit(main())
