#!/usr/bin/env python
"""HELD-OUT CONFIRMATION PANEL -- iteration 3, experiment_1 of run_YqmEFECOIR3D.

Mech-interp study of WHERE safety lives: every candidate readout (C1-C14) reads the activations or
weights of ONE model; the final-layer logit gap (BL1) and all judge columns are baselines / ground
truth, never the result. This is not a jailbreak or attack-selection study.

Order of operations (each step hash-committed in hash_chain.jsonl; the harvest refuses to start
otherwise):
  1. panel rule  -> assets/panel_rule.json   (seeded SHA-256 draw rule, frozen before any rank)
  2. panel draw  -> results/panel.json       (every repo verified live; every exclusion logged)
  3. behaviour   -> private/gens/*.jsonl     (greedy replies, Lane C protocol; NO hooks)
  4. judge       -> private/judged/*.jsonl   (Lane C lc_judge.py protocol, verbatim)
  5. TIME rule   -> results/panel_trim.json  (pre-registered; drops fill members only)
  6. truth       -> results/graded_truth.json  COMMITTED before the first hook on any panel ckpt
  7. prereg      -> prereg.json              frozen after truth, before any hook
  8. harvest     -> harvest/<tag>/           iteration-2 protocol + weight summaries
  9. score       -> results/{features,heldout_table,order_audit,join_stub[,join_result]}.json
 10. outputs     -> method_out.json (exp_gen_sol_out schema) + README.md

Usage:
  uv run method.py            # (re)build method_out.json from the committed results (fast)
  uv run method.py --stage all  # run every stage in order (hours on this CPU-only box)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent
sys.path.insert(0, str(WS / "src"))

from common import ASSETS, H2, HARVEST, RESULTS, jdump, jload, setup_logging, slug, utc_now  # noqa: E402
from loguru import logger  # noqa: E402

PY = sys.executable
STAGES = [
    ("inventory", [PY, "src/inventory.py"]),
    ("panel_rule", [PY, "src/panel.py", "rule"]), ("panel_draw", [PY, "src/panel.py", "draw"]),
    ("items", [PY, "src/items.py"]), ("c11_items", [PY, "src/c11_items.py"]),
    ("judge_repro", [PY, "src/judge.py", "reproduce"]),
    ("generate", [PY, "src/gen.py", "--batch", "32"]), ("judge", [PY, "src/judge.py", "watch"]),
    ("time_rule", [PY, "src/time_rule.py"]), ("truth", [PY, "src/outcomes.py", "--commit"]),
    ("prereg", [PY, "src/prereg.py"]), ("harvest_randinit", [PY, "src/harvest_panel.py", "--smoke"]),
    ("harvest", [PY, "src/harvest_panel.py"]), ("iter2_same_code", [PY, "src/iter2_panel_same_code.py"]),
    ("score", [PY, "src/score.py"]), ("unit_checks", [PY, "src/unit_checks.py"]),
    ("verify_hooks", [PY, "src/verify_hooks.py"]), ("extra_analyses", [PY, "src/extra_analyses.py"]),
    ("b7_diagnostic", [PY, "src/b7_diagnostic.py"]),
]

FEATURE_COLUMNS = ["C1", "C1_k4", "C1_k8", "C2", "C2_tpr5", "C2_screenrule", "C3", "C3_screenrule", "C4",
                   "C4_screenrule", "C5", "C6", "C6_screenrule", "C7", "C8", "C9", "C10", "C10_screenrule", "C11",
                   "C12", "C12_topsv", "C12_screenrule", "C13", "C13_peak_d", "C13_peak_f",
                   "BL1", "BL1_hard", "B3", "B7", "X2", "X10_abs"]
PAIRED_READOUTS = ["C13", "C13_peak_d", "C7", "C5", "BL1", "BL1_hard", "BL1_truelogit", "BL1_truelogit_hard"]


def _fmt(v) -> str:
    try:
        f = float(v)
        if f != f:
            return "NaN"
        return f"{f:.6g}"
    except (TypeError, ValueError):
        return str(v)


def _opt(name: str):
    p = RESULTS / name
    return jload(p) if p.exists() else None


def build_outputs() -> dict:
    feats = jload(RESULTS / "features.json")
    truth = jload(RESULTS / "graded_truth.json")
    table = jload(RESULTS / "heldout_table.json")
    extra = _opt("extra_analyses.json") or {}
    stim = jload(H2 / "assets/stimuli.json")["rows"]
    import numpy as np
    import candidates as cand

    tl = {r["repo"]: r for r in (extra.get("bl1_truelogit") or {}).get("heldout_rows", [])}
    # ---- dataset 1: one example per held-out checkpoint (+ the random-init control row)
    ex1 = []
    for repo, f in feats["features"].items():
        o = truth["per_ckpt"][repo]
        oa = o["outcomes_primary_laneC_items"]
        e = {"input": json.dumps({"repo": repo, "family": o["family"], "role": o["role"], "unit": o["unit"],
                                  "parent": o.get("parent"), "n_layers": f.get("L"), "hidden_size": f.get("d")}),
             "output": json.dumps({"harmful_compliance": oa["harmful_compliance"], "over_refusal": oa["over_refusal"],
                                   "safe_engagement": oa["safe_engagement"],
                                   "items": "45 harmful + 45 benign Lane C items"}),
             "metadata_family": o["family"], "metadata_role": o["role"],
             "metadata_harmful_compliance": oa["harmful_compliance"],
             "metadata_harmful_compliance_ci95": oa.get("harmful_compliance_ci95"),
             "metadata_over_refusal": oa["over_refusal"], "metadata_safe_engagement": oa["safe_engagement"],
             "metadata_n_harm_judged": oa["n_harm_judged"], "metadata_n_benign_judged": oa["n_benign_judged"],
             "metadata_is_random_init_control": False}
        for c in FEATURE_COLUMNS:
            e[f"predict_{c}"] = _fmt(f.get(c))
        e["predict_BL1_truelogit"] = _fmt((tl.get(repo) or {}).get("BL1_truelogit"))
        ex1.append(e)
    ri = feats.get("random_init")
    if ri:
        e = {"input": json.dumps({"repo": feats.get("random_init_tag"), "family": "random-init control",
                                  "role": "control", "note": "not in any rho"}),
             "output": json.dumps({"harmful_compliance": None, "note": "never generated/judged (control)"}),
             "metadata_family": "control", "metadata_role": "random_init",
             "metadata_is_random_init_control": True}
        for c in FEATURE_COLUMNS:
            e[f"predict_{c}"] = _fmt(ri.get(c))
        ex1.append(e)

    # ---- dataset 2: per-prompt recognition on the 160 HARD prompts, per checkpoint:
    # activation method (EASY axis at lay(0.5), midpoint threshold) vs the logit baseline
    # (final-layer refusal-minus-control drive, EASY-midpoint threshold).
    ex2 = []
    y = np.array([s["y"] for s in stim])
    sid = np.array([s["set_id"] for s in stim])
    for repo in feats["features"]:
        d = HARVEST / slug(repo)
        A = np.load(d / "A_prompt.npy").astype(np.float64)
        L = A.shape[1] - 1
        l5 = cand.lay(0.5, L)
        easy, hard = sid == 0, sid == 1
        u = cand.axis(A[easy, l5], y[easy])
        s_act = A[:, l5] @ u
        thr_a = 0.5 * (s_act[easy & (y == 1)].mean() + s_act[easy & (y == 0)].mean())
        drv = (np.load(d / "r_refusal.npy") - np.load(d / "r_control.npy")).astype(np.float64)[:, L]
        thr_l = 0.5 * (drv[easy & (y == 1)].mean() + drv[easy & (y == 0)].mean())
        sign_l = 1.0 if drv[easy & (y == 1)].mean() >= drv[easy & (y == 0)].mean() else -1.0
        for i in np.flatnonzero(hard):
            ex2.append({"input": stim[i]["text"], "output": "harmful" if y[i] == 1 else "benign",
                        "predict_activation_easy_axis_l50": "harmful" if s_act[i] > thr_a else "benign",
                        "predict_logit_final_refusal_drive": "harmful" if sign_l * (drv[i] - thr_l) > 0 else "benign",
                        "metadata_checkpoint": repo, "metadata_stim_id": stim[i]["stim_id"],
                        "metadata_source": stim[i]["source"], "metadata_activation_score": float(s_act[i]),
                        "metadata_logit_drive": float(drv[i]), "metadata_layer_l50": int(l5)})
        del A
    # ---- dataset 3: the held-out table itself (one row per feature x outcome), for the paper's join
    ex3 = []
    for r in table["rows"]:
        ex3.append({"input": f"feature={r['feature']}; outcome={r['outcome']}; readout_class={r['readout_class']}",
                    "output": _fmt(r["rho"]),
                    "predict_rho_spearman": _fmt(r["rho"]),
                    "predict_d_vs_BL1": _fmt(r.get("d_BL1")),
                    "predict_dabs_vs_BL1": _fmt(r.get("dabs_BL1")),
                    "predict_partial_rho_given_BL1": _fmt(r.get("partial_rho_given_BL1")),
                    "metadata_n": r["n"], "metadata_n_undefined": r.get("n_undefined"),
                    "metadata_ci95_ckpt": json.dumps(r.get("ci95_ckpt")),
                    "metadata_ci95_family": json.dumps(r.get("ci95_family")),
                    "metadata_dabs_BL1_ci95_ckpt": json.dumps(r.get("dabs_BL1_ci95_ckpt")),
                    "metadata_mde_rho_power80": r.get("mde_rho_power80"),
                    "metadata_critical_rho_alpha05": r.get("critical_rho_alpha05"),
                    "metadata_expected_sign": r.get("expected_sign"),
                    "metadata_sign_matches_expected": r.get("sign_matches_expected"),
                    "metadata_random_init_position": r.get("random_init_position")})
    datasets = [{"dataset": "heldout_panel_per_checkpoint", "examples": ex1},
                {"dataset": "heldout_panel_hard_prompt_recognition", "examples": ex2},
                {"dataset": "heldout_table_feature_x_outcome", "examples": ex3}]
    # ---- dataset 4 (additional, post-prereg): paired within-unit contrasts, child - parent on the same prompts
    ex4 = []
    for r in extra.get("paired_contrasts") or []:
        h = r["harmful_compliance"]
        e = {"input": json.dumps({"kind": r["kind"], "parent": r["parent"], "child": r["child"], "family": r["family"]}),
             "output": _fmt(h["delta_hc"]),
             "metadata_delta_hc_ci95_item_boot": json.dumps(h["ci95_item_boot"]),
             "metadata_mcnemar_exact_p": h["mcnemar_exact_p"], "metadata_hc_parent": h["hc_parent"],
             "metadata_hc_child": h["hc_child"]}
        for k in PAIRED_READOUTS:
            v = r["prompt_level_deltas"].get(k)
            if v is None:
                continue
            e[f"predict_delta_{k}"] = _fmt(v["delta"])
            e[f"metadata_delta_{k}_ci95_prompt_boot"] = json.dumps(v["ci95_prompt_boot"])
        ex4.append(e)
    if ex4:
        datasets.append({"dataset": "paired_within_unit_contrasts_post_prereg", "examples": ex4})
    rec_acc = {}
    for e in ex2:
        a = rec_acc.setdefault(e["metadata_checkpoint"], {"activation_easy_axis_l50": 0, "logit_final_refusal_drive": 0, "n": 0})
        a["activation_easy_axis_l50"] += int(e["predict_activation_easy_axis_l50"] == e["output"])
        a["logit_final_refusal_drive"] += int(e["predict_logit_final_refusal_drive"] == e["output"])
        a["n"] += 1
    for a in rec_acc.values():
        a["activation_easy_axis_l50"] /= a["n"]
        a["logit_final_refusal_drive"] /= a["n"]
    audit = _opt("order_audit.json") or {}
    unit = _opt("unit_checks.json") or {}
    hooks = (_opt("hook_checks.json") or {}).get("summary")
    hc_rows = {r["feature"]: r for r in table["rows"] if r["outcome"] == "harmful_compliance"}
    out = {"metadata": {"title": "Held-out confirmation panel: single-model activation/weight safety readouts vs graded behaviour",
                        "utc": utc_now(), "n_panel": feats["n_panel_scored"], "panel": feats["panel"], "no_winner": True,
                        "primary_outcome": "harmful_compliance on the 45 Lane C harmful items (lc_judge protocol)",
                        "critical_rho_alpha05": next(iter(hc_rows.values())).get("critical_rho_alpha05"),
                        "mde_rho_power80": next(iter(hc_rows.values())).get("mde_rho_power80"),
                        "rho_harmful_compliance": {k: v["rho"] for k, v in hc_rows.items()},
                        "order_audit_pass": audit.get("pass"), "unit_checks_all_pass": unit.get("all_pass"),
                        "hook_checks": hooks, "join": (_opt("join_result.json") or _opt("join_stub.json") or {}),
                        "hard_recognition_accuracy_midpoint_threshold": rec_acc,
                        "b7_diagnostic": {k: v for k, v in (_opt("b7_diagnostic.json") or {}).items() if k.startswith("rho_") or k == "note"},
                        "paired_abliteration_replication": (extra.get("abliteration_replication") or {}).get("rows"),
                        "deviations": [{"key": d["key"], "what": d["what"]} for d in (_opt("deviations.json") or [])],
                        "judge_cost_usd": sum(float(json.loads(x).get("cost_usd") or 0) for x in
                                              (RESULTS / "judge_cost_ledger.jsonl").read_text().splitlines() if x.strip()),
                        "hash_chain": [json.loads(x) for x in (WS / "hash_chain.jsonl").read_text().splitlines() if x.strip()],
                        "invariant": "every predict_C* column reads activations or weights of ONE model; predict_BL1* / predict_logit_* are logit baselines"},
           "datasets": datasets}
    jdump(out, WS / "method_out.json")
    logger.info(f"method_out.json: " + " + ".join(str(len(d["examples"])) for d in datasets) + " examples")
    return out


@logger.catch(reraise=True)
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="outputs", help="'outputs' (default), 'all', or one stage name")
    a = ap.parse_args()
    setup_logging("method")
    if a.stage == "outputs":
        build_outputs()
        return 0
    todo = STAGES if a.stage == "all" else [s for s in STAGES if s[0] == a.stage]
    for name, cmd in todo:
        logger.info(f"STAGE {name}: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=WS, check=True)
    if a.stage == "all":
        build_outputs()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
