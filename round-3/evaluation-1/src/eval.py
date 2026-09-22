#!/usr/bin/env python3
"""Fix the three-model comparison tables: ASSEMBLER.

Reads the cached intermediates written by
  src/panel.py      (A_prompt panel, 25 checkpoints: steps 1, 2a, 2c, 5-STaR)
  src/laneb.py      (Lane B lesion arrays: steps 2b, 2d, 3, 4)
  src/gates.py      (step 6)          src/notation.py (step 5c)
  src/behaviour.py  (judged behavioural truth, K1 granite)
and writes the master / claims / site / accumulator / power / gates / notation / deviations
tables (results/*.csv + results/tables.json), eval_out.json (exp_eval_sol_out) and SUMMARY.md.
No forward pass, no LLM call. Re-running costs seconds.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from scipy.stats import norm, spearmanr

WS = Path(__file__).resolve().parent
RES = WS / "results"
RUN = Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop")
E2 = RUN / "iter_2/gen_art/gen_art_experiment_1"
DS2 = RUN / "iter_2/gen_art/gen_art_dataset_1"

logger.remove()
logger.add(sys.stdout, level="INFO", format="{time:HH:mm:ss}|{level:<7}|{message}")
(WS / "logs").mkdir(exist_ok=True)
logger.add(WS / "logs/eval.log", rotation="30 MB", level="DEBUG")

VERDICTS = {"SUPPORTED", "NOT_SUPPORTED", "EQUIVALENT", "INCONCLUSIVE_UNDERPOWERED", "CEILING",
            "FORCED_BY_CONSTRUCTION", "UNDEFINED"}

COMMISSIONED = [
    ("Qwen--Qwen3-4B-Base", "Base (chat template)"),
    ("Qwen--Qwen3-4B", "instruct"),
    ("Qwen--Qwen3-4B-SafeRL", "SafeRL"),
    ("CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6", "STaR non-safety FT of Base"),
    ("mlabonne--Qwen3-4B-abliterated", "mlabonne abliterated (child of instruct)"),
]
OTHER_ORDER = [
    "huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2", "Qwen--Qwen3-0.6B",
    "huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2", "Qwen--Qwen3-1.7B",
    "Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3", "Qwen--Qwen2.5-1.5B-Instruct",
    "mlx-community--SmolLM3-3B-abliterated-bf16", "HuggingFaceTB--SmolLM3-3B",
    "lunahr--Phi-4-mini-instruct-abliterated", "microsoft--Phi-4-mini-instruct",
    "Damien420--granite-3.2-2b-instruct-abliterated", "ibm-granite--granite-3.2-2b-instruct",
    "RandInit-Qwen3-0.6B",
]


# ----------------------------------------------------------------------------- utils
def jl(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(f"missing/unreadable {path.name}: {exc}")
        return default


def fnum(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def fmt(x: Any, nd: int = 3) -> str:
    v = fnum(x)
    return "NA" if v is None else f"{v:.{nd}f}"


def fci(ci: Any, nd: int = 3) -> str:
    if not isinstance(ci, (list, tuple)) or len(ci) < 2:
        return ""
    lo, hi = (ci[1], ci[2]) if len(ci) == 3 else (ci[0], ci[1])
    return f"[{fmt(lo, nd)}, {fmt(hi, nd)}]"


def ci2(ci: Any) -> tuple[float | None, float | None]:
    if not isinstance(ci, (list, tuple)) or len(ci) < 2:
        return None, None
    return (fnum(ci[1]), fnum(ci[2])) if len(ci) == 3 else (fnum(ci[0]), fnum(ci[1]))


def clean(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def newcombe_diff(k1: int, n1: int, k0: int, n0: int, z: float = 1.96) -> list[float]:
    """Newcombe hybrid-score CI for p1 - p0 (the dataset's label_robust rule)."""
    def wil(k: int, n: int) -> tuple[float, float]:
        p = k / n
        den = 1 + z * z / n
        c = (p + z * z / (2 * n)) / den
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
        return c - h, c + h
    p1, p0 = k1 / n1, k0 / n0
    l1, u1 = wil(k1, n1)
    l0, u0 = wil(k0, n0)
    d = p1 - p0
    lo = d - math.sqrt((p1 - l1) ** 2 + (u0 - p0) ** 2)
    hi = d + math.sqrt((u1 - p1) ** 2 + (p0 - l0) ** 2)
    return [round(lo, 4), round(hi, 4)]


# ----------------------------------------------------------------------------- ledger
class Ledger:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, quoted: Any, source_artifact: str, source_text: str, recomputed: Any, *,
            kind: str = "other", explanation: str = "", status: str | None = None) -> None:
        q, r = fnum(quoted), fnum(recomputed)
        if status is None:
            if q is None or r is None:
                status = "NOT_RECOMPUTABLE" if r is None else "NON_NUMERIC"
                match = None
                diff = None
            else:
                diff = abs(q - r)
                if kind == "rate":
                    match = diff <= 0.005
                elif kind == "int":
                    match = diff < 0.5
                elif kind == "p":
                    match = (q > 0 and r > 0 and abs(math.log10(q) - math.log10(r)) <= 0.05)
                else:
                    # quoted numbers are rounded; 1% relative OR within the quoted rounding
                    nd = len(str(quoted).split(".")[-1]) if "." in str(quoted) else 0
                    match = diff <= max(0.01 * abs(q), 0.5 * 10 ** (-nd) + 1e-9)
                status = "MATCH" if match else "MISMATCH"
        else:
            match = status == "MATCH"
            diff = abs(q - r) if (q is not None and r is not None) else None
        self.rows.append({"quoted_value": quoted, "source_artifact": source_artifact,
                          "source_text": source_text, "recomputed_value": recomputed,
                          "abs_diff": diff, "match": match, "status": status,
                          "kind": kind, "explanation": explanation})


# ----------------------------------------------------------------------------- loaders
def load_all() -> dict:
    D: dict[str, Any] = {}
    D["panel"] = {p.stem: jl(p) for p in sorted((RES / "panel_ckpt").glob("*.json"))}
    for name in ("panel_pairs", "panel_star", "panel_reconcile", "laneb_cells", "laneb_tests",
                 "laneb_contrasts", "laneb_power", "laneb_accum", "laneb_reconcile",
                 "laneb_inventory", "laneb_k16_repro", "gates_table", "notation_table", "behaviour"):
        D[name] = jl(RES / f"{name}.json", None)
    D["scored"] = jl(E2 / "results/scored_checkpoints.json", {})
    D["recog"] = jl(E2 / "results/recognition.json", {})
    D["pairs_table"] = jl(E2 / "results/pairs_table.json", [])
    full = jl(DS2 / "full_data_out.json", {"datasets": [{"examples": []}]})
    D["registry_pairs"] = [e for e in full["datasets"][0]["examples"] if e.get("metadata_row_kind") == "pair"]
    del full
    return D


def role_of(D: dict, tag: str) -> str:
    return ((D["scored"].get(tag) or {}).get("meta") or {}).get("role", "")


def label_robust_for(D: dict, tag: str) -> str:
    child = tag.split("--", 1)[-1]
    for e in D["registry_pairs"]:
        if str(e.get("metadata_child_repo", "")).endswith(child):
            return f"{e.get('metadata_effectiveness_label')} (robust={e.get('metadata_label_robust')})"
        if str(e.get("metadata_parent_repo", "")).endswith(child):
            return "parent"
    return "not in registry"


# ----------------------------------------------------------------------------- master
def behaviour_row(D: dict, tag: str) -> dict:
    b = ((D["behaviour"] or {}).get("checkpoints") or {}).get(tag)
    if not b:
        return {"HC": None, "HC_ci": None, "OR": None, "OR_ci": None, "n_harm": None, "n_benign": None,
                "beh_source": "UNDEFINED (no judged generations for this checkpoint)"}
    return {"HC": b["HC"], "HC_ci": b["HC_ci"], "OR": b["OR"], "OR_ci": b["OR_ci"],
            "n_harm": b["n_harm"], "n_benign": b["n_benign"], "beh_source": Path(b["source"]).name}


def resp_at(p: dict, win: str, cls: str, layer: int | None) -> tuple[float | None, float | None, int | None]:
    r = ((p.get("section1c") or {}).get("resp") or {}).get(f"{win}_{cls}")
    if not isinstance(r, dict) or not isinstance(r.get("tpr5"), list):
        return None, None, None
    li = layer if (layer is not None and layer < len(r["tpr5"])) else r.get("best_layer")
    if li is None:
        return None, None, None
    return fnum(r["tpr5"][li]), fnum(r["auroc"][li]), int(li)


def master_table(D: dict) -> list[dict]:
    rows = []
    order = [t for t, _ in COMMISSIONED] + OTHER_ORDER
    order += [t for t in D["panel"] if t not in order]
    names = dict(COMMISSIONED)
    for tag in order:
        p = D["panel"].get(tag)
        if p is None:
            continue
        L = p.get("n_layers")
        s1a, s1b, s1c = p.get("section1a", {}), p.get("section1b_kbudget", {}), p.get("section1c", {})
        ra, rr = p.get("reproduction_asserts", {}), p.get("recognition_repro", {}) or {}
        acc = (p.get("section2a") or {}).get("s36", {}) or {}
        acc25 = (p.get("section2a") or {}).get("s25", {}) or {}
        pl = s1a.get("peak_layer")
        tpr_late, au_late, late_layer = resp_at(p, "LATE", "REQUEST", pl)
        tpr_late_c, _, _ = resp_at(p, "LATE", "CONTINUATION", pl)
        row = {"checkpoint": tag, "arm": names.get(tag, role_of(D, tag)), **behaviour_row(D, tag),
               "label_robust": label_robust_for(D, tag),
               "heldout_d_peak": s1a.get("peak_d"), "heldout_d_ci": s1a.get("peak_d_ci"),
               "heldout_d_layer": pl, "heldout_d_depth": s1a.get("peak_depth"),
               "insample_d_easy_lstar": ra.get("d_cohen_lstar_recomputed"), "insample_lstar": ra.get("l_star_recomputed"),
               "tpr5_at_peak_ci": s1a.get("peak_tpr5_ci")}
        for k in (4, 8, 16):
            row[f"k{k}_auroc"] = s1b.get(f"k{k}_auroc_mean")
            row[f"k{k}_auroc_p5_p95"] = [s1b.get(f"k{k}_auroc_p5"), s1b.get(f"k{k}_auroc_p95")]
            row[f"k{k}_tpr5"] = s1b.get(f"k{k}_tpr5_mean")
            row[f"k{k}_tpr5_p5_p95"] = [s1b.get(f"k{k}_tpr5_p5"), s1b.get(f"k{k}_tpr5_p95")]
        row.update({
            "R_TPR5_registered": rr.get("R_TPR5_repro"), "R_TPR1_registered": rr.get("R_TPR1_repro"),
            "R_AUROC_registered": rr.get("R_AUROC_repro"), "R_layer": rr.get("R_layer_mode"),
            "onset_hard": s1c.get("onset_hard"), "onset_hard_depth": (s1c.get("onset_hard") / L) if (L and s1c.get("onset_hard") is not None) else None,
            "onset_easy_ldec": ra.get("l_dec_recomputed"), "onset_cvtpr5": s1c.get("onset_tpr"),
            "peak_drive": ra.get("peak_drive_recomputed"), "peak_drive_layer": ra.get("peak_drive_layer"),
            "peak_is_final": ra.get("peak_is_final"),
            "fixed_axis_ratio_s36": acc.get("fixed_axis_peak_over_start_normgap"),
            "fixed_axis_ratio_s36_ci": acc.get("fixed_axis_peak_over_start_ci"),
            "fixed_axis_spearman_s36": acc.get("spearman_normgap_layer"), "fixed_axis_spearman_s36_ci": acc.get("spearman_ci"),
            "own_axis_ratio_s36": acc.get("own_axis_d_ratio_max_over_start"), "accum_verdict_s36": acc.get("verdict"),
            "accum_verdict_s25": acc25.get("verdict"),
            "fixed_axis_ratio_easy_s36": (acc.get("easy_cv") or {}).get("fixed_axis_peak_over_start_normgap"),
            "fixed_axis_ratio_easy_s36_ci": (acc.get("easy_cv") or {}).get("fixed_axis_peak_over_start_ci"),
            "fixed_axis_spearman_easy_s36": (acc.get("easy_cv") or {}).get("spearman_normgap_layer"),
            "fixed_axis_spearman_easy_s36_ci": (acc.get("easy_cv") or {}).get("spearman_ci"),
            "own_axis_ratio_easy_s36": (acc.get("easy_cv") or {}).get("own_axis_d_ratio_max_over_start"),
            "start_d_easy_s36": (acc.get("easy_cv") or {}).get("start_d"),
            "accum_verdict_easy_s36": (acc.get("easy_cv") or {}).get("verdict"),
            "resp_LATE_request_tpr5": tpr_late, "resp_LATE_request_auroc": au_late, "resp_layer": late_layer,
            "resp_LATE_continuation_tpr5": tpr_late_c,
            "resp_tpr1": "NOT_RESOLVABLE (n_neg=48)" if p.get("has_A_resp") else "UNDEFINED (no A_resp)",
            "BL1_easy": ra.get("BL1_easy_recomputed"), "BL1_hard": ra.get("BL1_hard"),
            "B3_fisher": ra.get("BL4_CLUSTSEP_recomputed"), "BL7_jorak_A": ra.get("BL7_recomputed"),
            "X10_abs": ra.get("X10_abs_recomputed"), "has_A_resp": p.get("has_A_resp"),
        })
        rows.append(row)
    # partial correlation / residual of each activation readout given BL1_hard across the panel
    df = pd.DataFrame(rows)
    for col in ("heldout_d_peak", "k16_auroc", "R_TPR5_registered", "peak_drive", "onset_hard_depth"):
        ok = df[col].notna() & df["BL1_hard"].notna()
        if ok.sum() >= 5:
            x = df.loc[ok, "BL1_hard"].astype(float).to_numpy()
            y = df.loc[ok, col].astype(float).to_numpy()
            b = np.polyfit(x, y, 1)
            res = y - np.polyval(b, x)
            df.loc[ok, f"{col}_resid_given_BL1"] = res
    return clean(df.to_dict(orient="records"))


def panel_corr_with_bl1(master: list[dict]) -> list[dict]:
    df = pd.DataFrame(master)
    out = []
    for col in ("heldout_d_peak", "k16_auroc", "R_TPR5_registered", "peak_drive", "onset_hard_depth", "B3_fisher"):
        ok = df[col].notna() & df["BL1_hard"].notna()
        if ok.sum() < 5:
            continue
        rho, p = spearmanr(df.loc[ok, col].astype(float), df.loc[ok, "BL1_hard"].astype(float))
        row = {"readout": col, "n_checkpoints": int(ok.sum()), "spearman_with_BL1_hard": rho, "p": p}
        # partial Spearman with HC given BL1 (rank-residual method) where HC exists
        ok2 = ok & df["HC"].notna()
        if ok2.sum() >= 6:
            r = lambda s: pd.Series(s).rank().to_numpy()
            xa, xb, xc = r(df.loc[ok2, col].astype(float)), r(df.loc[ok2, "HC"].astype(float)), r(df.loc[ok2, "BL1_hard"].astype(float))
            ra = xa - np.polyval(np.polyfit(xc, xa, 1), xc)
            rb = xb - np.polyval(np.polyfit(xc, xb, 1), xc)
            row["partial_spearman_with_HC_given_BL1"] = float(np.corrcoef(ra, rb)[0, 1])
            row["spearman_with_HC"] = float(spearmanr(df.loc[ok2, col].astype(float), df.loc[ok2, "HC"].astype(float))[0])
            row["n_with_HC"] = int(ok2.sum())
        out.append(row)
    return clean(out)


# ----------------------------------------------------------------------------- site table (step 3)
def site_rows(D: dict) -> list[dict]:
    cells = D["laneb_cells"]
    if isinstance(cells, dict):
        cells = cells.get("cells") or cells.get("rows") or []
    return cells or []


def site_table(D: dict) -> list[dict]:
    """Primary site table: band-pooled logistic REQUEST class, per lineage x site x alpha."""
    out = []
    for c in site_rows(D):
        if str(c.get("layer")) != "band" or c.get("probe") not in ("logistic", "logreg", "lr") \
                or str(c.get("cls", "")).upper() != "REQUEST":
            continue
        out.append({k: c.get(k) for k in ("lineage", "alpha", "site", "auroc", "auroc_ci", "tpr1", "tpr1_ci",
                                          "tpr5", "tpr5_ci", "d_auroc", "d_auroc_ci", "d_tpr1", "d_tpr1_ci",
                                          "d_tpr5", "d_tpr5_ci", "n_pos", "n_neg")})
    order = {"PROMPT": 0, "EARLY": 1, "LATE": 2}
    out.sort(key=lambda r: (str(r["lineage"]), order.get(str(r["site"]).upper(), 9), float(r["alpha"])))
    return clean(out)


def site_delta(D: dict, lineage: str, site: str, alpha: float = 1.0, key: str = "d_tpr1",
               probe: tuple = ("logistic", "logreg", "lr"), cls: str = "REQUEST") -> tuple[Any, Any]:
    for c in site_rows(D):
        if c.get("lineage") == lineage and str(c.get("site")).upper() == site and str(c.get("layer")) == "band" \
                and c.get("probe") in probe and str(c.get("cls", "")).upper() == cls \
                and abs(float(c.get("alpha")) - alpha) < 1e-6:
            return c.get(key), c.get(f"{key}_ci")
    return None, None


# ----------------------------------------------------------------------------- generic flatteners
def flatten(obj: Any, prefix: str = "", out: dict | None = None, depth: int = 0) -> dict:
    out = {} if out is None else out
    if isinstance(obj, dict) and depth < 6:
        for k, v in obj.items():
            flatten(v, f"{prefix}.{k}" if prefix else str(k), out, depth + 1)
    elif isinstance(obj, list) and obj and all(isinstance(x, dict) for x in obj) and depth < 6:
        for i, v in enumerate(obj):
            flatten(v, f"{prefix}[{i}]", out, depth + 1)
    else:
        out[prefix] = obj
    return out


def find_first(obj: Any, *needles: str) -> Any:
    """First scalar whose flattened key contains ALL needles (case-insensitive)."""
    flat = flatten(obj or {})
    for k, v in flat.items():
        kl = k.lower()
        if all(n.lower() in kl for n in needles) and not isinstance(v, (dict, list)):
            return v
    return None


# ----------------------------------------------------------------------------- ledger (G1)
def pget(D: dict, tag: str, *path: str) -> Any:
    o: Any = D["panel"].get(tag) or {}
    for k in path:
        o = o.get(k) if isinstance(o, dict) else None
    return o


def build_ledger(D: dict) -> Ledger:
    led = Ledger()
    A2 = "art_OyQwmkiWj-5u (iter-2 Lane A screen) out/SUMMARY.md"
    base, inst, safe, star, abl = (t for t, _ in COMMISSIONED)
    arms = [(base, "Base"), (inst, "instruct"), (safe, "SafeRL"), (abl, "abliterated")]
    for (t, n), q in zip(arms, (0.475, 0.875, 0.850, 0.838)):
        led.add(q, A2, f"HARD-set recognition R TPR@5%FPR, {n}", pget(D, t, "recognition_repro", "R_TPR5_repro"),
                kind="rate", explanation="iter-2 nested HARD-set protocol re-run from A_prompt (seed 921)")
    for (t, n), q in zip(arms, (33, 19, 19, 19)):
        led.add(q, A2, f"HARD-set recognition onset layer, {n}", pget(D, t, "section1c", "onset_hard"), kind="int",
                explanation="first layer whose cross-fitted HARD diff-in-means AUROC >= 0.5+0.9*(max-0.5)")
    for (t, n), q in zip([(base, "Base"), (inst, "instruct"), (safe, "SafeRL"), (abl, "abliterated"), (star, "STaR")],
                         (1.57, 4.92, 8.78, 1.92, 2.57)):
        led.add(q, A2, f"peak logit-lens refusal-drive gap, {n}", pget(D, t, "reproduction_asserts", "peak_drive_recomputed"),
                explanation="max over layers of the EASY-set harm-conditioned drive gap (iter-2 x8 curve, unsmoothed)")
    led.add(-1.96, A2, "abliterated final-layer drive (BL1)", pget(D, abl, "reproduction_asserts", "BL1_easy_recomputed"),
            explanation="BL1 on the EASY prompts (iter-2 definition); on HARD prompts it is " +
            fmt(pget(D, abl, "reproduction_asserts", "BL1_hard"), 2) + " -- the sign flips with the prompt set")
    led.add(-0.30, A2, "BL1 Base", pget(D, base, "reproduction_asserts", "BL1_easy_recomputed"),
            explanation="EASY-set BL1; HARD-set BL1 = " + fmt(pget(D, base, "reproduction_asserts", "BL1_hard"), 2))
    led.add(1.96, A2, "BL1 STaR", pget(D, star, "reproduction_asserts", "BL1_easy_recomputed"),
            explanation="EASY-set BL1; HARD-set BL1 = " + fmt(pget(D, star, "reproduction_asserts", "BL1_hard"), 2))
    # in-sample Cohen's d (Lane B quotes) vs our EASY in-sample d at l_star and held-out d
    for t, q, qtxt in ((base, 5.68, "5.68 (Base)"), (star, 5.74, "5.74 (STaR)"), (inst, 11.15, "11.15 (instruct, layer 22)"),
                       (safe, 11.41, "11.41 (SafeRL)")):
        led.add(q, "art_2sz7g3MD4_y3 Lane B (r_ablit_sep, damage/fit_ablit 128+128 in-sample)",
                f"request-axis Cohen's d {qtxt} -- A_prompt analogue", pget(D, t, "reproduction_asserts", "d_cohen_lstar_recomputed"),
                status="DIFFERENT_ESTIMAND",
                explanation=("NOT the same estimand: Lane B fitted and scored in-sample on its own 128+128 prompt corpus; "
                             "recomputed value here is the A_prompt EASY 48+48 in-sample d at l*; the Lane-B-corpus value is "
                             "re-derived in laneb_accum.json (see the Lane B rows of this ledger). Held-out (EASY-fit, HARD-"
                             f"scored) peak d = {fmt(pget(D, t, 'section1a', 'peak_d'), 2)}"))
    # k=16 restricted budget
    for (t, n), q in zip([(base, "Base"), (star, "STaR"), (inst, "instruct"), (safe, "SafeRL")], (0.528, 0.540, 0.679, 0.698)):
        led.add(q, "iter-2 eval (gen_art_evaluation_1) M5 k=16 AUROC", f"k=16 restricted-budget AUROC, {n} -- plan step-1b protocol",
                pget(D, t, "section1b_kbudget", "k16_auroc_mean"), kind="rate", status="DIFFERENT_ESTIMAND",
                explanation="DIFFERENT PROTOCOL: iter-2 M5 fitted on 16 Lane B LATE-window items and scored the rest; "
                            "recomputed here = 16+16 EASY prompts, layer chosen inside the subset, scored on 160 HARD "
                            "prompts (plan step 1b). Ordering Base<STaR<instruct/SafeRL is the comparable part")
    # panel_reconcile extras (pair medians, cosines)
    pr = D.get("panel_reconcile") or {}
    rec = {r.get("quantity"): r for r in pr.get("reconcile", [])} if isinstance(pr, dict) else {}
    led.add(-2.86, A2, "BL1 median delta over 6 effective pairs", pr.get("effective_pairs_delta_BL1_median"))
    led.add(-2.98, A2, "peak-drive median delta over 6 effective pairs", pr.get("effective_pairs_delta_peak_drive_median"))
    for q_name, r in rec.items():
        if "cos" in str(q_name).lower():
            qv, rv = r.get("quoted") or [], r.get("recomputed") or []
            labels = ["P0 shallow", "P0 deep", "granite shallow", "granite deep"]
            for i, qq in enumerate(qv):
                led.add(qq, A2, f"|cos| parent-child harm direction {labels[i] if i < 4 else i}",
                        rv[i] if i < len(rv) else None, kind="rate",
                        explanation="per-layer |cos| of EASY diff-in-means directions parent vs child, mean over shallow / deep half")
    # behaviour
    beh = (D.get("behaviour") or {}).get("checkpoints", {})
    for tag, lab, q in ((inst, "instruct HC", 0.000), (abl, "abliterated HC", 0.733)):
        led.add(q, A2, f"harmful compliance, {lab}", (beh.get(tag) or {}).get("HC"), kind="rate",
                explanation="recomputed from judged jsonl rows (judge_primary.harmful_content)")
    for tag, lab, q in ((inst, "instruct OR", 0.444), (abl, "abliterated OR", 0.000)):
        led.add(q, A2, f"over-refusal, {lab}", (beh.get(tag) or {}).get("OR"), kind="rate",
                explanation="recomputed from judged jsonl rows (judge_primary.refused on benign)")
    k1 = (D.get("behaviour") or {}).get("k1_granite") or {}
    led.add(4.14, "iter-2 eval M6 (granite null edit)", "K1/A moves 4.14 null-SD on a behavioural no-op",
            k1.get("delta_null_sd"), explanation=k1.get("note", ""))
    # gates quoted upstream
    g = {r["gate"]: r for r in (D.get("gates_table") or [])}
    def gobs(name: str) -> Any:
        return (g.get(name) or {}).get("observed")
    led.add(0.9429, "iter-1 dataset judge_validation.json", "prefix hazard identification accuracy",
            gobs("D1_prefix_hazard_identification_accuracy"), kind="rate")
    led.add(85, "iter-1 dataset prereg.json", "confirmatory set 96 -> 85 after QC", gobs("D1_confirmatory_n_after_qc"), kind="int")
    led.add(1.25, "iter-1 dataset prereg.json", "placebo median edit ratio", gobs("D1_placebo_median_edit_ratio"))
    led.add(0.8852, "iter-2 dataset gates.json", "G_PROXY_HARD", gobs("G_PROXY_HARD"), kind="rate",
            explanation="copied - not recomputable (text proxy CV not re-run)")
    n_pass = sum(1 for r in (D.get("gates_table") or []) if r["artifact"].startswith("art_1hlg") and r["verdict"] == "PASS")
    led.add(22, "iter-2 dataset gates.json", "22 of 25 gates PASS", n_pass, kind="int")
    lb_rows = [r for r in (D.get("gates_table") or []) if r["gate"].startswith("B_G1_cos|")]
    if lb_rows:
        pooled = float(np.mean([float(r["observed"]) for r in lb_rows]))
        led.add(0.159, "art_2sz7g3MD4_y3 Lane B summary", "|cos(r_content, r_ablit)| pooled", pooled, kind="rate",
                explanation="quoted value equals lineage L2 alone (0.1594); mean over the 4 lineages recomputed")
    led.add(0.927, "art_2sz7g3MD4_y3 Lane B summary", "r_content split-half cosine",
            float(str(gobs("B_split_half_r_content")).split()[1]) if gobs("B_split_half_r_content") else None, kind="rate")
    return led


# ----------------------------------------------------------------------------- pairs (step 1d)
def pair_table(D: dict) -> list[dict]:
    out = []
    beh = (D.get("behaviour") or {}).get("checkpoints", {})
    for p in (D.get("panel_pairs") or {}).get("pairs", []):
        if p.get("status") == "MISSING_HARVEST":
            continue
        row = {"pair": p["pair"], "parent": p["parent"], "child": p["child"],
               "effectiveness_label_iter2": p.get("effectiveness"), "measured_dHC": p.get("delta_HC"),
               "measured_dOR": p.get("delta_OR")}
        # Newcombe CI of the MEASURED behavioural delta (label_robust rule, recomputed)
        pt, ct = p["parent"].replace("/", "--"), p["child"].replace("/", "--")
        bp, bc = beh.get(pt), beh.get(ct)
        if bp and bc and bp.get("n_harm") and bc.get("n_harm"):
            k1, k0 = round(bc["HC"] * bc["n_harm"]), round(bp["HC"] * bp["n_harm"])
            ci = newcombe_diff(k1, bc["n_harm"], k0, bp["n_harm"])
            row["dHC_newcombe_ci"] = ci
            row["label_robust_recomputed"] = ("EFFECTIVE" if ci[0] > 0.15 else "NULL_EDIT" if (ci[0] > -0.1 and ci[1] < 0.1)
                                              else "AMBIGUOUS")
        for k, v in p.items():
            if isinstance(v, dict) and "point" in v:
                row[f"{k}"] = v.get("point")
                row[f"{k}_ci95"] = v.get("ci95") or v.get("ci")
                if v.get("ci90"):
                    row[f"{k}_ci90"] = v.get("ci90")
                if v.get("tost_verdict"):
                    row[f"{k}_verdict"] = v["tost_verdict"].replace("NOT_EQUIVALENT_SUPPORTED_CHANGE", "SUPPORTED")
        out.append(row)
    return clean(out)


# ----------------------------------------------------------------------------- claims (step 5b)
def ci_str(v: Any, ci: Any) -> str:
    return f"{fmt(v)} {fci(ci)}"


def pairs_by(D: dict) -> dict:
    return {r["pair"]: r for r in pair_table(D)}


def claims_table(D: dict, master: list[dict]) -> list[dict]:
    P = pairs_by(D)
    M = {r["checkpoint"]: r for r in master}
    base, inst, safe, star, abl = (t for t, _ in COMMISSIONED)
    star_d = (D.get("panel_star") or {})
    eff = [k for k in ("P0", "P1", "P2", "P3", "P4", "P5") if k in P]
    d_drop = [P[k]["delta_peak_d"] for k in eff]
    d_drop_ci_excl = sum(1 for k in eff if (P[k].get("delta_peak_d_ci95") or [0, 0])[1] < 0)
    rows = []

    def add(cid: str, old: str, new: str, evidence: str, verdict: str) -> None:
        assert verdict.split("(")[0] in VERDICTS, verdict
        rows.append({"id": cid, "claim_as_previously_stated": old, "corrected_claim": new,
                     "evidence": evidence, "verdict": verdict})

    bi = P.get("Base->instruct", {})
    add("i", "Abliteration removes EXECUTION, not RECOGNITION; safety lives in execution.",
        "Scoped to the abliteration contrast only. Safety TRAINING moves prompt-site recognition: HARD R TPR@5%FPR "
        "Base->instruct rises; so 'execution, not recognition' does not describe what safety training adds.",
        f"R TPR@5%FPR Base {fmt(M.get(base, {}).get('R_TPR5_registered'))} -> instruct {fmt(M.get(inst, {}).get('R_TPR5_registered'))}; "
        f"paired-bootstrap delta {ci_str(bi.get('delta_tpr5_recognition_json'), bi.get('delta_tpr5_recognition_json_ci90'))} (90% CI; "
        f"{bi.get('delta_tpr5_recognition_json_verdict')})",
        "SUPPORTED")
    p0 = P.get("P0", {})
    add("ii", "Request-axis Cohen's d (5.68 / 11.15 / ...) is a few-prompt safety score that tracks safety tuning.",
        "Relabelled: request-axis d is a PROMPT-SITE RECOGNITION-TYPE readout, not an execution readout. The quoted "
        "values are IN-SAMPLE on Lane B's 128+128 corpus; the held-out (EASY-fit, HARD-scored) peak d is 0.5-2.5.",
        "Lane B in-sample d at the r_ablit layer (re-derived from fit_ablit arrays): " + "; ".join(
            f"{L} {fmt(((D.get('laneb_accum') or {}).get('ledger_values') or {}).get(f'insample_d_fit_ablit_at_rablit_layer_{L}'), 2)} "
            f"(layer {((D.get('laneb_accum') or {}).get('ledger_values') or {}).get(f'rablit_layer_{L}')})" for L in ("L1", "L2", "L3", "L4"))
        + " | held-out peak d: " + "; ".join(f"{n} {fmt(M.get(t, {}).get('heldout_d_peak'), 2)} (layer {M.get(t, {}).get('heldout_d_layer')})"
                                        for t, n in COMMISSIONED),
        "SUPPORTED")
    sd = star_d.get("heldout_peak_d_diff_STaR_minus_Base") or {}
    fr = {k: star_d.get(f"fraction_{k}") or {} for k in ("heldout_peak_d", "peak_drive", "BL1_easy", "BL1_hard")}
    bs = P.get("Base->STaR", {})
    add("iii", "The non-safety STaR fine-tune lands on top of its Base parent, so the readout tracks SAFETY tuning, not fine-tuning.",
        "STaR matches Base ONLY on request-axis d. On peak drive, BL1 (EASY) and HARD recognition R it moves part of the way toward "
        "instruct: part of the refusal-drive and recognition signal is generic chat fine-tuning.",
        f"d STaR-Base {ci_str(sd.get('point'), sd.get('ci90'))} (90% CI, TOST +/-0.5 {sd.get('tost_verdict')}); fraction of Base->instruct "
        f"distance covered: peak drive {ci_str(fr['peak_drive'].get('mean'), fr['peak_drive'].get('ci90'))}, BL1_easy "
        f"{ci_str(fr['BL1_easy'].get('mean'), fr['BL1_easy'].get('ci90'))}, BL1_hard {ci_str(fr['BL1_hard'].get('mean'), fr['BL1_hard'].get('ci90'))}; "
        f"R TPR@5%FPR Base->STaR {ci_str(bs.get('delta_tpr5_recognition_json'), bs.get('delta_tpr5_recognition_json_ci90'))} (90% CI)",
        "SUPPORTED")
    pr = D.get("panel_reconcile") or {}
    add("iv", "Peak logit-lens refusal drive (activation) falls 6/6 (median -2.98) while BL1 falls 6/6 (median -2.86).",
        "The two readouts move together (Spearman of the per-pair deltas reported); for instruct the peak layer IS the final layer "
        "(peak drive = BL1 = 4.92), so for that arm the 'activation' readout is the logit baseline. Both also move on the granite "
        "NULL edit, so neither is specific; the held-out request-axis d does NOT move on granite.",
        f"median d(peak drive) {fmt(pr.get('effective_pairs_delta_peak_drive_median'), 2)}, median d(BL1) {fmt(pr.get('effective_pairs_delta_BL1_median'), 2)}, "
        f"Spearman across {pr.get('n_effective_pairs')} pairs {fmt(pr.get('spearman_delta_peakdrive_vs_deltaBL1'), 2)}; instruct peak layer "
        f"{M.get(inst, {}).get('peak_drive_layer')} of {36} (peak_is_final={M.get(inst, {}).get('peak_is_final')}); granite P6 d(peak drive) "
        f"{ci_str(P.get('P6', {}).get('delta_peak_drive_easy'), P.get('P6', {}).get('delta_peak_drive_easy_ci95'))}, d(BL1) "
        f"{ci_str(P.get('P6', {}).get('delta_BL1_easy'), P.get('P6', {}).get('delta_BL1_easy_ci95'))}, d(held-out d) "
        f"{ci_str(P.get('P6', {}).get('delta_peak_d'), P.get('P6', {}).get('delta_peak_d_ci95'))}",
        "SUPPORTED")
    add("iv-b", "Abliteration keeps the request axis (recognition kept) while execution collapses.",
        "Only for the HARD-refit (nested) recognition probe. The EASY-fit request axis -- an AdvBench-vs-benign diff-in-means, i.e. "
        "close to the harmful-vs-harmless contrast abliteration recipes fit and project out -- LOSES its held-out separation on HARD prompts in every effective child "
        f"({d_drop_ci_excl}/{len(eff)} CIs below 0) and not on the granite null edit. Its drop is close to the recipe's construction, "
        "so it is not independent evidence of lost recognition either.",
        f"P0 d(held-out d) {ci_str(p0.get('delta_peak_d'), p0.get('delta_peak_d_ci95'))}; P0 d(R TPR@5%FPR, HARD-refit) "
        f"{ci_str(p0.get('delta_tpr5_recognition_json'), p0.get('delta_tpr5_recognition_json_ci90'))} (90% CI, TOST +/-0.05: {p0.get('delta_tpr5_recognition_json_verdict')}); "
        f"mlabonne peak drive {fmt(M.get(abl, {}).get('peak_drive'), 2)} vs Base {fmt(M.get(base, {}).get('peak_drive'), 2)}",
        "NOT_SUPPORTED")
    ev = "; ".join(f"{n}: start d {fmt(M.get(t, {}).get('start_d_easy_s36'), 2)}, fixed-axis Spearman(gap, layer) "
                   f"{ci_str(M.get(t, {}).get('fixed_axis_spearman_easy_s36'), M.get(t, {}).get('fixed_axis_spearman_easy_s36_ci'))}, "
                   f"fixed peak/start {fmt(M.get(t, {}).get('fixed_axis_ratio_easy_s36'), 2)}, own-axis ratio "
                   f"{fmt(M.get(t, {}).get('own_axis_ratio_easy_s36'), 2)} -> {M.get(t, {}).get('accum_verdict_easy_s36')}"
                   for t, n in COMMISSIONED)
    verdicts = {M.get(t, {}).get("accum_verdict_easy_s36") for t, _ in COMMISSIONED}
    add("acc", "u is an ACCUMULATOR coordinate: the signal along u grows ~138x with depth.",
        "Not supported as accumulation. With the axis FROZEN at layer 13 (fit on EASY, held-out EASY prompts), the class gap along it "
        "peaks at the start layer and decays with depth in every commissioned arm; separation is maintained only by an axis that is "
        "REFIT at each layer (|cos| to u_13 decays). The growth is layer-specific re-writing/rotation, not accumulation along one "
        "coordinate. On HARD prompts the EASY-fit layer-13 axis has a NEGATIVE start gap, so a HARD ratio is undefined.",
        ev + " | Lane B: gap along the STORED late-fit u grows " + ", ".join(
            f"{L} {fmt(((D.get('laneb_accum') or {}).get('ledger_values') or {}).get(f'u_signal_growth_ratio_fixed_{L}'), 0)}x"
            for L in ("L1", "L2", "L3", "L4")) + " from layer 13 to the fitting layer (raw gap, axis fitted at the END layer, "
            "band-limited); with the axis frozen at layer 13 the item-group raw gap grows only 1.0-3.2x over layers 13-21 while the "
            "norm-controlled gap falls (Spearman CI below 0 or spanning 0) in every lineage, site and alpha (accumulator table).",
        "NOT_SUPPORTED" if verdicts <= {"LAYER_SPECIFIC_DIRECTION", "NO_GROWTH", None} else "INCONCLUSIVE_UNDERPOWERED")
    rows.extend(laneb_claims(D))
    return clean(rows)


def laneb_claims(D: dict) -> list[dict]:
    """Claims (v)-(vii) + accumulator claims from the Lane B intermediates."""
    out = []
    acc = D.get("laneb_accum") or {}
    cos_fit = find_first(acc, "forced") if acc else None
    out.append({"id": "v", "claim_as_previously_stated": "post-lesion cos(class dir alpha=0, alpha=1) = 0.000 at the fitting layer shows the lesion is exact / orthogonal.",
                "corrected_claim": "REMOVED from the evidence list: the lesion projects u out of every residual write, so orthogonality at the fitting layer holds algebraically. The informative quantity is the same cosine at band layers where it is not forced.",
                "evidence": json.dumps(clean(laneb_cosine_summary(D)))[:600], "verdict": "FORCED_BY_CONSTRUCTION"})
    out.append({"id": "vi", "claim_as_previously_stated": "Operating-point movement is 10.6x larger than AUROC movement at the response site.",
                "corrected_claim": "DROPPED: a ratio of a TPR@1%FPR delta to an AUROC delta is not a quantity (different units and scales).",
                "evidence": "iter-2 eval: -0.1439 / -0.0136 = 10.6", "verdict": "UNDEFINED"})
    sites = laneb_site_summary(D)
    out.append({"id": "vii", "claim_as_previously_stated": "Prompt-site recognition survives the lesion (dTPR@1%FPR +0.0006) while the response site loses it (-0.144).",
                "corrected_claim": "Site labels corrected: the iter-2 'prompt site' was the EARLY RESPONSE window. With the true prompt site (lastp) added, "
                                   "each lineage is reported per site with its own CI (table site_table); the L4 non-safety contrast decides whether the late drop reads as execution.",
                "evidence": sites["text"], "verdict": sites["verdict"]})
    return out


def laneb_ledger(D: dict, led: Ledger) -> None:
    r = D.get("laneb_reconcile") or {}
    src = "iter-2 eval (gen_art_evaluation_1) M1 / EVAL_REPORT"
    d = r.get("delta_alpha0_to_1_recomputed") or {}
    q = r.get("quoted") or {}
    for site in ("EARLY", "LATE"):
        led.add((q.get(site) or {}).get("d_mean_tpr1"), src, f"mean-of-4 dTPR@1%FPR alpha 0->1, {site} window (labelled "
                f"'{'prompt site' if site == 'EARLY' else 'response site'}' upstream)", (d.get(site) or {}).get("d_mean_tpr1_recomputed"),
                kind="rate", explanation="band-pooled logistic, request class; EARLY is a RESPONSE window, not the prompt site")
        led.add((q.get(site) or {}).get("d_mean_auroc"), src, f"mean-of-4 dAUROC alpha 0->1, {site}",
                (d.get(site) or {}).get("d_mean_auroc_recomputed"), kind="rate")
    l4 = r.get("L4_LATE_recomputed") or {}
    led.add(0.404, src, "L4 LATE TPR@1%FPR alpha=0", l4.get("tpr1_alpha0"), kind="rate")
    led.add(0.234, src, "L4 LATE TPR@1%FPR alpha=1", l4.get("tpr1_alpha1"), kind="rate")
    pr = (r.get("p_1.76e-6_reproduction") or {})
    led.add(1.76e-6, src, "Holm L1 p (full lesion, LATE)", (pr.get("reproduced_with_exact_iter2_method") or {}).get("p_two_sided"),
            kind="p", explanation="reproduced with iter-2's per-item one-sample t-test on 384 hit differences, which treats the 8 "
                                  "cells of a scenario as independent; the scenario-permutation p is in laneb_tests.json")
    led.add(-0.1439 / -0.0136, src, "10.6x operating-point vs AUROC movement ratio", None,
            status="DROPPED", explanation="a ratio of a TPR delta to an AUROC delta is not a quantity; removed from all tables")
    for L, v in (r.get("damage_Dcurve_reconcile") or {}).items():
        led.add(1.0, "art_2sz7g3MD4_y3 Lane B analysis.json D_curve", f"{L} D_curve (damage corpus) at alpha=1",
                (v.get("recomputed_D_curve") or [None])[-1], kind="rate",
                explanation=f"read at {v.get('read_site')}; CEILING at alpha=0 so it cannot fall")
    # tests / accumulator quotes (filled from laneb_tests / laneb_accum if present)
    t = D.get("laneb_tests") or {}
    tost = {(r["lineage"], r["site"]): r.get("largest_alpha_equivalent") for r in t.get("tost_rows", [])}
    for L in ("L1", "L2", "L3", "L4"):
        led.add(0.5, "iter-2 eval M1", f"TOST-equivalent (margin 0.05 TPR) at alpha <= 0.5 ({L}, LATE)", tost.get((L, "LATE")),
                explanation="largest alpha whose paired scenario-bootstrap 90% CI of dTPR@1%FPR (thresholds re-derived per "
                            "draw) lies inside +/-0.05; iter-2 did not name a lineage, so each is checked")
    lv = (D.get("laneb_accum") or {}).get("ledger_values") or {}
    for L, q in (("L1", 5.68), ("L2", 11.15), ("L3", 11.41), ("L4", 5.74)):
        led.add(q, "art_2sz7g3MD4_y3 Lane B summary", f"request-axis in-sample Cohen's d, {L} (Lane B fit_ablit corpus, r_ablit layer "
                f"{lv.get(f'rablit_layer_{L}')})", lv.get(f"insample_d_fit_ablit_at_rablit_layer_{L}"),
                explanation=f"recomputed from Lane B fit_ablit|lastp arrays (in-sample, 128+128); iter-1 meta r_ablit_sep = "
                            f"{fmt(lv.get(f'meta_r_ablit_sep_at_rablit_layer_{L}'), 2)}")
        led.add(138, "art_2sz7g3MD4_y3 Lane B summary", f"signal along u grows ~138x with depth ({L}, fixed axis, band-limited)",
                lv.get(f"u_signal_growth_ratio_fixed_{L}"),
                explanation=f"only layers 13-21 + r_ablit layer stored; own-axis ratio {fmt(lv.get(f'own_axis_ratio_{L}'), 2)}")
        led.add(0.985, "art_2sz7g3MD4_y3 Lane B", f"cos(class dir alpha=0, alpha=1) at L13 ({L})", lv.get(f"cos_a0_a1_L13_{L}"), kind="rate")
        led.add(0.000, "art_2sz7g3MD4_y3 Lane B", f"post-lesion cos at the fitting layer ({L})", lv.get(f"cos_a0_a1_fitting_layer_{L}"),
                kind="rate", explanation="FORCED_BY_CONSTRUCTION -- removed from the evidence list")
    k16 = D.get("laneb_k16_repro") or {}
    for L, q in (("L1", 0.528), ("L4", 0.540), ("L2", 0.679), ("L3", 0.698)):
        led.add(q, "iter-2 eval M5", f"k=16 restricted-budget AUROC, {L} (iter-2 protocol: Lane B LATE band, logistic)",
                (k16.get(L) or {}).get("mean"), kind="rate", explanation="iter-2 M5 function re-run on Lane B alpha=0 LATE features")

def laneb_site_summary(D: dict) -> dict:
    parts = []
    for site in ("PROMPT", "EARLY", "LATE"):
        s = []
        for L in ("L1", "L2", "L3", "L4"):
            v, ci = site_delta(D, L, site, 1.0)
            s.append(f"{L} {ci_str(v, ci)}")
        parts.append(f"{site}: dTPR@1%FPR a0->1 " + "; ".join(s))
    c = D.get("laneb_contrasts") or {}
    con = [f"{r['site']} {r['lineage']}-L4 {ci_str(r.get('contrast_tpr1'), r.get('contrast_tpr1_ci'))}"
           for r in c.get("rows", []) if r.get("alpha") == "1.00" and r.get("site") == "LATE"]
    verdict_txt = c.get("verdict_LATE_alpha1.00_tpr1", "")
    txt = " | ".join(parts) + " | L4 contrasts (safety drop minus L4 drop, LATE, a=1): " + "; ".join(con) + f" | {verdict_txt}"
    verdict = "NOT_SUPPORTED" if "WITHDRAWN" in verdict_txt else ("SUPPORTED" if "RESCUED" in verdict_txt else "INCONCLUSIVE_UNDERPOWERED")
    return {"text": txt, "verdict": verdict}


def laneb_cosine_summary(D: dict) -> dict:
    lv = (D.get("laneb_accum") or {}).get("ledger_values") or {}
    return {L: {"fitting_layer": lv.get(f"rablit_layer_{L}"), "cos_at_fitting_layer (FORCED)": lv.get(f"cos_a0_a1_fitting_layer_{L}"),
                "cos_at_L13 (informative)": lv.get(f"cos_a0_a1_L13_{L}")} for L in ("L1", "L2", "L3", "L4")}


# ----------------------------------------------------------------------------- accumulator (step 2)
def accumulator_table(D: dict) -> list[dict]:
    out = []
    for tag, name in COMMISSIONED + [(t, t) for t in OTHER_ORDER]:
        p = D["panel"].get(tag)
        if not p:
            continue
        for s in ("s25", "s36"):
            a = (p.get("section2a") or {}).get(s) or {}
            row = {"source": "A_prompt (HARD-scored, EASY-fit axis)", "checkpoint": tag, "arm": name, "s_key": s,
                   "s_layer": a.get("s_layer"), "start_d": a.get("start_d"), "start_d_ci": a.get("start_d_ci"),
                   "fixed_spearman": a.get("spearman_normgap_layer"), "fixed_spearman_ci": a.get("spearman_ci"),
                   "fixed_ratio_normgap": a.get("fixed_axis_peak_over_start_normgap"),
                   "fixed_ratio_ci": a.get("fixed_axis_peak_over_start_ci"),
                   "fixed_raw_ratio": a.get("fixed_axis_raw_gap_ratio_max_over_start"),
                   "own_axis_d_ratio": a.get("own_axis_d_ratio_max_over_start"),
                   "cos_start_end": [a.get("cos_start"), a.get("cos_end")], "verdict": a.get("verdict")}
            out.append(row)
            e = a.get("easy_cv") or {}
            if e:
                out.append({"source": "A_prompt (EASY cross-fitted, in-distribution)", "checkpoint": tag, "arm": name,
                            "s_key": s, "s_layer": a.get("s_layer"), "start_d": e.get("start_d"), "start_d_ci": e.get("start_d_ci"),
                            "fixed_spearman": e.get("spearman_normgap_layer"), "fixed_spearman_ci": e.get("spearman_ci"),
                            "fixed_ratio_normgap": e.get("fixed_axis_peak_over_start_normgap"),
                            "fixed_ratio_ci": e.get("fixed_axis_peak_over_start_ci"),
                            "fixed_raw_ratio": e.get("fixed_axis_raw_gap_ratio_max_over_start"),
                            "own_axis_d_ratio": e.get("own_axis_d_ratio_max_over_start"),
                            "cos_start_end": [e.get("cos_start"), e.get("cos_end")], "verdict": e.get("verdict")})
    acc = D.get("laneb_accum") or {}
    for L in ("L1", "L2", "L3", "L4"):
        la = acc.get(L) or {}
        for key, g in (la.get("by_group_alpha") or {}).items():
            rp, sp = g.get("ratio_peak_over_l0_fixed_axis") or {}, g.get("spearman_gapnorm_vs_layer_fixed_axis") or {}
            pl = g.get("per_layer") or []
            own = [x.get("cohend_own_axis") for x in pl]
            out.append({"source": "Lane B (band-limited 13-21 + r_ablit layer)", "checkpoint": L, "arm": key, "s_key": "u_13",
                        "s_layer": 13, "start_d": pl[0].get("cohend_fixed_axis") if pl else None,
                        "fixed_spearman": sp.get("point"), "fixed_spearman_ci": sp.get("ci95"),
                        "fixed_ratio_normgap": rp.get("point"), "fixed_ratio_ci": rp.get("ci95"),
                        "own_axis_d_ratio": (max(o for o in own if o is not None) / own[0]) if own and own[0] else None,
                        "cos_start_end": [pl[0].get("abs_cos_u13_ul"), pl[-1].get("abs_cos_u13_ul")] if pl else None,
                        "verdict": g.get("verdict")})
        u = la.get("u_138x_recompute") or {}
        for grp in ("fit_ablit", "damage"):
            if isinstance(u.get(grp), dict):
                out.append({"source": "Lane B: gap along the STORED late-fit u (iter-1 '138x' claim)", "checkpoint": L, "arm": grp,
                            "s_key": f"u@{la.get('r_ablit_layer')}", "fixed_raw_ratio": u[grp].get("ratio_max_over_min_abs_gap"),
                            "verdict": "GROWTH ALONG A LATE-FIT AXIS (raw gap, not norm-controlled; axis fitted at the end layer)"})
    return clean(out)


# ----------------------------------------------------------------------------- power (step 4)
def power_table(D: dict) -> list[dict]:
    pw = D.get("laneb_power") or {}
    rows = (pw.get("item_cell_rows") or []) + (pw.get("damage_corpus_rows") or []) if isinstance(pw, dict) else []
    out = []
    for r in rows:
        if isinstance(r, dict):
            q = {k: v for k, v in r.items() if not isinstance(v, (list, dict))}
            q["mde_tpr1_mcnemar"] = (r.get("mde_tpr1_mcnemar_sim") or {}).get("delta_mde")
            q["mde_bootstrap_shift_f"] = (r.get("mde_bootstrap_shift") or {}).get("f_mde")
            out.append(q)
    return clean(out)


# ----------------------------------------------------------------------------- eval_out
READOUT_CLASS = {"heldout_d_peak": "activation (prompt-site recognition-type)", "k4_auroc": "activation", "k8_auroc": "activation",
                 "k16_auroc": "activation", "k16_tpr5": "activation", "R_TPR5_registered": "activation", "R_TPR1_registered": "activation",
                 "onset_hard": "activation", "peak_drive": "activation through unembedding (logit-lens)",
                 "fixed_axis_ratio_easy_s36": "activation", "fixed_axis_spearman_easy_s36": "activation",
                 "own_axis_ratio_easy_s36": "activation", "own_axis_ratio_s36": "activation",
                 "resp_LATE_request_tpr5": "activation (response site)", "BL1_easy": "logit-baseline", "BL1_hard": "logit-baseline",
                 "B3_fisher": "activation baseline", "BL7_jorak_A": "weight baseline (incumbent)", "X10_abs": "weight",
                 "HC": "text (behavioural truth)", "OR": "text (behavioural truth)"}


def ex_row(inp: str, out: str, evals: dict, meta: dict, preds: dict | None = None) -> dict:
    r = {"input": inp, "output": out}
    for k, v in (preds or {}).items():
        r[f"predict_{k}"] = "NA" if v is None else str(v)
    for k, v in evals.items():
        fv = fnum(v)
        if fv is not None:
            r[f"eval_{k}"] = fv
    for k, v in meta.items():
        r[f"metadata_{k}"] = clean(v)
    return r


def build_eval_out(D: dict, master: list[dict], claims: list[dict], led: Ledger, pairs: list[dict], metrics: dict) -> dict:
    ds1 = []
    for m in master:
        for ro, cls in READOUT_CLASS.items():
            if ro not in m:
                continue
            val = m.get(ro)
            ds1.append(ex_row(f"{m['checkpoint']} :: {ro}", "UNDEFINED" if val is None else fmt(val, 4),
                              {"value": val, "BL1_hard": m.get("BL1_hard"), "BL1_easy": m.get("BL1_easy"),
                               "residual_given_BL1": m.get(f"{ro}_resid_given_BL1"), "HC": m.get("HC")},
                              {"readout_class": cls, "arm": m.get("arm"), "label_robust": m.get("label_robust"),
                               "ci": m.get({"heldout_d_peak": "heldout_d_ci", "fixed_axis_ratio_s36": "fixed_axis_ratio_s36_ci"}.get(ro, "_"))},
                              {"readout": val, "baseline_BL1_hard": m.get("BL1_hard")}))
    ds2 = []
    for c in site_rows(D):
        ds2.append(ex_row(f"{c['lineage']} | alpha={c['alpha']} | site={c['site']} | layer={c['layer']} | probe={c['probe']} | class={c['cls']}",
                          f"TPR@1%FPR={fmt(c.get('tpr1'))} TPR@5%FPR={fmt(c.get('tpr5'))} AUROC={fmt(c.get('auroc'), 4)}",
                          {"auroc": c.get("auroc"), "tpr1": c.get("tpr1"), "tpr5": c.get("tpr5"), "d_tpr1": c.get("d_tpr1"),
                           "d_auroc": c.get("d_auroc"), "d_tpr5": c.get("d_tpr5"), "n_pos": c.get("n_pos"), "n_neg": c.get("n_neg")},
                          {"tpr1_ci": c.get("tpr1_ci"), "d_tpr1_ci": c.get("d_tpr1_ci"), "auroc_ci": c.get("auroc_ci"),
                           "bootstrap_B": c.get("B"), "repo": c.get("repo")},
                          {"probe_tpr1": c.get("tpr1"), "delta_vs_alpha0_tpr1": c.get("d_tpr1")}))
    ds3 = [ex_row(f"{r['source_text']} [{r['source_artifact']}]", str(r["status"]),
                  {"quoted": r["quoted_value"], "recomputed": r["recomputed_value"], "abs_diff": r["abs_diff"],
                   "match": (1.0 if r["match"] else 0.0) if r["match"] is not None else None},
                  {"explanation": r["explanation"], "kind": r["kind"]},
                  {"recomputed": r["recomputed_value"]}) for r in led.rows]
    ds4 = [ex_row(f"{g['gate']} [{g['artifact']}] threshold {g['threshold']}", g["verdict"], {"observed": g["observed"], "pass": 1.0 if g["verdict"] in ("PASS", "LICENSED") else 0.0},
                  {"provenance": g["provenance"], "consequence": g["consequence"], "note": g["note"]},
                  {"observed": g["observed"]}) for g in (D.get("gates_table") or [])]
    ds5 = [ex_row(f"claim {c['id']}: {c['claim_as_previously_stated']}", c["verdict"], {"verdict_supported": 1.0 if c["verdict"] == "SUPPORTED" else 0.0,
                                  "verdict_not_supported": 1.0 if c["verdict"] == "NOT_SUPPORTED" else 0.0},
                  {"corrected_claim": c["corrected_claim"], "evidence": c["evidence"]},
                  {"corrected_claim": c["corrected_claim"]}) for c in claims]
    ds6 = []
    for p in pairs:
        ds6.append(ex_row(f"{p['pair']}: {p['parent']} -> {p['child']}", f"dHC={fmt(p.get('measured_dHC'))} d(heldout d)={fmt(p.get('delta_peak_d'))}",
                          {k: v for k, v in p.items() if isinstance(v, (int, float)) and not isinstance(v, bool)},
                          {k: v for k, v in p.items() if k.endswith("_ci95") or k.endswith("_verdict") or k.startswith("label")},
                          {"delta_heldout_d": p.get("delta_peak_d"), "delta_BL1_easy": p.get("delta_BL1_easy")}))
    datasets = [{"dataset": n, "examples": e} for n, e in (
        ("checkpoint_x_readout", ds1), ("lineage_x_alpha_x_site_x_layer", ds2), ("deviations_ledger", ds3),
        ("gates", ds4), ("claims", ds5), ("pair_deltas", ds6)) if e]
    return {"metadata": {"evaluation_name": "Fix the three-model comparison tables (iter-3 evaluation)",
                         "description": "CPU-only re-analysis of iter-1/iter-2 activation arrays: abliterated row, accumulator "
                                        "controls, three-site lesion dissociation per lineage, power for saturated probes, "
                                        "gates, notation and a ledger of re-derived numbers. No forward pass, $0 LLM spend.",
                         "verdict_vocabulary": sorted(VERDICTS), "run_invariant": "activation readouts are the result; BL1 "
                         "(logit) and text readouts are baselines printed beside them"},
            "metrics_agg": {k: v for k, v in clean(metrics).items() if fnum(v) is not None},
            "datasets": datasets}


def compute_metrics(D: dict, master: list[dict], led: Ledger, pairs: list[dict]) -> dict:
    M = {r["checkpoint"]: r for r in master}
    P = {p["pair"]: p for p in pairs}
    base, inst, safe, star, abl = (t for t, _ in COMMISSIONED)
    st = [r for r in led.rows if r["status"] in ("MATCH", "MISMATCH")]
    m: dict[str, Any] = {"n_numbers_rederived": len(st), "n_match": sum(r["status"] == "MATCH" for r in st),
                         "n_ledger_rows": len(led.rows)}
    m["match_rate"] = m["n_match"] / max(len(st), 1)
    m["abliterated_d_peak"] = M.get(abl, {}).get("heldout_d_peak")
    p0 = P.get("P0", {})
    m["abliterated_minus_parent_d"] = p0.get("delta_peak_d")
    lo, hi = ci2(p0.get("delta_peak_d_ci95"))
    m["abliterated_minus_parent_d_ci_lo"], m["abliterated_minus_parent_d_ci_hi"] = lo, hi
    m["abliterated_minus_parent_R_tpr5"] = p0.get("delta_tpr5_recognition_json")
    m["abliterated_k16_auroc"] = M.get(abl, {}).get("k16_auroc")
    m["abliterated_k16_tpr5"] = M.get(abl, {}).get("k16_tpr5")
    m["abliterated_peak_drive"] = M.get(abl, {}).get("peak_drive")
    m["base_peak_drive"] = M.get(base, {}).get("peak_drive")
    for L in ("L1", "L2", "L3", "L4"):
        for site in ("PROMPT", "EARLY", "LATE"):
            v, ci = site_delta(D, L, site, 1.0)
            m[f"site_delta_tpr1_{site.lower()}_{L}"] = v
            lo, hi = ci2(ci)
            m[f"site_delta_tpr1_{site.lower()}_{L}_ci_lo"], m[f"site_delta_tpr1_{site.lower()}_{L}_ci_hi"] = lo, hi
    for r in (D.get("laneb_contrasts") or {}).get("rows", []):
        if r.get("alpha") == "1.00":
            key = f"{r['lineage']}_minus_L4_drop_tpr1_{r['site'].lower()}"
            m[key] = r.get("contrast_tpr1")
            lo, hi = ci2(r.get("contrast_tpr1_ci"))
            m[key + "_ci_lo"], m[key + "_ci_hi"] = lo, hi
    for t, n in COMMISSIONED:
        short = {"Qwen--Qwen3-4B-Base": "base", "Qwen--Qwen3-4B": "instruct", "Qwen--Qwen3-4B-SafeRL": "saferl",
                 "CohenQu--Qwen3-4B-Base_HintGen-STaR.03.01_1e-6": "star", "mlabonne--Qwen3-4B-abliterated": "abliterated"}[t]
        m[f"fixed_axis_ratio_{short}"] = M.get(t, {}).get("fixed_axis_ratio_easy_s36")
        m[f"fixed_axis_spearman_{short}"] = M.get(t, {}).get("fixed_axis_spearman_easy_s36")
        m[f"own_axis_ratio_{short}"] = M.get(t, {}).get("own_axis_ratio_easy_s36")
        m[f"own_axis_ratio_hard_{short}"] = M.get(t, {}).get("own_axis_ratio_s36")
        m[f"heldout_d_{short}"] = M.get(t, {}).get("heldout_d_peak")
        m[f"BL1_hard_{short}"] = M.get(t, {}).get("BL1_hard")
    sd = D.get("panel_star") or {}
    m["STaR_fraction_of_base_to_instruct_d"] = (sd.get("fraction_heldout_peak_d") or {}).get("mean")
    m["STaR_fraction_of_base_to_instruct_peak_drive"] = (sd.get("fraction_peak_drive") or {}).get("mean")
    m["STaR_fraction_of_base_to_instruct_BL1"] = (sd.get("fraction_BL1_easy") or {}).get("mean")
    m["STaR_fraction_of_base_to_instruct_BL1_hard"] = (sd.get("fraction_BL1_hard") or {}).get("mean")
    m["STaR_minus_Base_heldout_d"] = (sd.get("heldout_peak_d_diff_STaR_minus_Base") or {}).get("point")
    g = D.get("gates_table") or []
    m["n_gates_pass"] = sum(r["verdict"] in ("PASS", "LICENSED") for r in g)
    m["n_gates_fail"] = sum(r["verdict"] in ("FAIL", "NOT_LICENSED") for r in g)
    m["n_gates_total"] = len(g)
    bi = P.get("Base->instruct", {})
    m["base_to_instruct_R_tpr5_delta"] = bi.get("delta_tpr5_recognition_json")
    lo, hi = ci2(bi.get("delta_tpr5_recognition_json_ci90"))
    m["base_to_instruct_R_tpr5_delta_ci90_lo"], m["base_to_instruct_R_tpr5_delta_ci90_hi"] = lo, hi
    eff = [p for k, p in P.items() if k in ("P0", "P1", "P2", "P3", "P4", "P5")]
    m["n_effective_pairs_heldout_d_drop_ci_below_0"] = sum(1 for p in eff if (ci2(p.get("delta_peak_d_ci95"))[1] or 0) < 0)
    m["granite_null_edit_delta_heldout_d"] = P.get("P6", {}).get("delta_peak_d")
    m["granite_null_edit_delta_BL1_easy"] = P.get("P6", {}).get("delta_BL1_easy")
    m["granite_null_edit_delta_peak_drive"] = P.get("P6", {}).get("delta_peak_drive_easy")
    return m


# ----------------------------------------------------------------------------- SUMMARY.md
def md_table(rows: list[dict], cols: list[str] | None = None, max_rows: int = 400) -> str:
    if not rows:
        return "_(no rows)_\n"
    df = pd.DataFrame(rows[:max_rows])
    if cols:
        df = df[[c for c in cols if c in df.columns]]
    def cell(v: Any) -> str:
        if isinstance(v, float):
            return fmt(v, 3)
        if isinstance(v, list):
            return "[" + ", ".join(fmt(x, 3) if isinstance(x, (float, int)) and not isinstance(x, bool) else str(x) for x in v) + "]"
        return str(v).replace("|", "/").replace("\n", " ")
    return df.map(cell).to_markdown(index=False) + "\n"


def write_summary(T: dict, metrics: dict) -> None:
    S = ["# Fix the three-model comparison tables -- SUMMARY", "",
         "CPU-only re-analysis, no forward pass, $0 LLM spend. Every activation number sits beside BL1 (logit baseline). "
         "Tables in the plan's order: master, claims, site, accumulator, power, gates, notation, deviations.", "",
         "## Key findings (every number re-derived from arrays; CIs are 95% unless marked)", ""] + [f"- {x}" for x in T["findings"]] + ["",
         "## Headline metrics", "", md_table([{"metric": k, "value": v} for k, v in metrics.items()], max_rows=200)]
    S += ["## 1. Master table (checkpoint x readout; BL1 beside every activation readout)", "",
          md_table(T["master"], ["checkpoint", "arm", "HC", "HC_ci", "OR", "n_harm", "label_robust", "heldout_d_peak", "heldout_d_ci",
                                 "heldout_d_layer", "heldout_d_depth", "insample_d_easy_lstar", "k4_auroc", "k8_auroc", "k16_auroc",
                                 "k16_auroc_p5_p95", "k16_tpr5", "R_TPR1_registered", "R_TPR5_registered", "onset_hard", "onset_hard_depth",
                                 "peak_drive", "peak_drive_layer", "peak_is_final", "fixed_axis_ratio_easy_s36", "fixed_axis_spearman_easy_s36",
                                 "own_axis_ratio_easy_s36", "accum_verdict_easy_s36", "accum_verdict_s36", "resp_LATE_request_tpr5", "BL1_easy", "BL1_hard", "B3_fisher", "BL7_jorak_A", "X10_abs"]),
          "Correlation of each activation readout with BL1_hard across the panel (and partial Spearman with HC given BL1):", "",
          md_table(T["bl1_corr"]), "### Pair deltas (child - parent, paired 1000-rep bootstrap 95% CI; behavioural effect = MEASURED dHC)", "",
          md_table(T["pairs"], ["pair", "child", "measured_dHC", "dHC_newcombe_ci", "label_robust_recomputed", "effectiveness_label_iter2",
                                "delta_peak_d", "delta_peak_d_ci95", "delta_tpr5_recognition_json", "delta_tpr5_recognition_json_ci90",
                                "delta_tpr5_recognition_json_verdict", "delta_peak_drive_easy", "delta_peak_drive_easy_ci95",
                                "delta_BL1_easy", "delta_BL1_easy_ci95", "delta_BL1_hard", "delta_BL1_hard_ci95"])]
    S += ["## 2. Claims table (as previously stated -> corrected)", "", md_table(T["claims"])]
    S += ["## 3. Site table (Lane B, band-pooled logistic probe, REQUEST class; fitted at alpha=0, scored at alpha>0; scenario-bootstrap CIs)", "",
          "PROMPT = item|lastp (true prompt site); EARLY/LATE = response windows (tokens 5-20 / 40-55). The iter-2 'prompt site' was EARLY.", "",
          md_table(T["site"]), "### Holm / permutation / TOST", "", md_table(T["tests"]),
          "### Safety-minus-L4 drop contrasts (alpha=1)", "", md_table(T["contrasts"])]
    S += ["## 4. Accumulator table (fixed axis vs own axis)", "", md_table(T["accum"])]
    S += ["## 5. Power table (saturated probes)", "", md_table(T["power"])]
    S += ["## 6. Gates table", "", md_table(T["gates"], ["gate", "artifact", "threshold", "observed", "provenance", "verdict", "consequence"])]
    S += ["## 7. Notation table", "", md_table(T["notation"])]
    S += ["## 8. Deviations ledger (quoted vs recomputed)", "",
          md_table(T["ledger"], ["source_text", "source_artifact", "quoted_value", "recomputed_value", "abs_diff", "status", "explanation"]),
          "### Deviations of THIS artifact from its plan", ""] + [f"- {x}" for x in T["own_deviations"]] + ["",
          "## Appendix: Lane B inventory (counted by script)", "", md_table(T["inventory"])]
    (WS / "SUMMARY.md").write_text("\n".join(S))


def own_deviations(D: dict) -> list[str]:
    out = [
        "BL1 is reported in BOTH forms: BL1_easy (iter-2's stored definition, EASY prompts; asserted equal to the stored value for all 25 "
        "checkpoints) and BL1_hard (the plan's HARD-prompt definition). They can differ in sign (mlabonne: -1.96 vs +1.76).",
        "Held-out request-axis d is fit on EASY and scored on HARD; at layer 0 all prompts share one state, so layers with degenerate "
        "(tied) scores are excluded from onset search.",
        "The fixed-axis accumulation test on HARD prompts is UNDEFINED for every 4B arm (the EASY-fit layer-13 axis has a NEGATIVE HARD "
        "start gap); an in-distribution cross-fitted EASY variant was added and is the one reported in the master table.",
        "Lane B per-layer cells use B=500 scenario bootstraps (band cells B=2000); the Holm family is 48 tests with a per-site 16-test "
        "family reported beside it (no verdict changed).",
        "The scenario sign-flip permutation (thresholds held fixed) can reject where the re-thresholding bootstrap CI spans 0 "
        "(e.g. L1 LATE alpha=1): the permutation p conditions on the operating threshold, the bootstrap CI does not; both are reported.",
        "Response-site TPR@1%FPR on A_resp is NOT_RESOLVABLE (48 negatives); only TPR@5%FPR and AUROC are reported there.",
        "STaR (CohenQu) has no judged generations: its HC/OR are UNDEFINED, never zero-filled.",
    ]
    for f in (RES / "laneb_deviations.json",):
        d = jl(f, [])
        items = d if isinstance(d, list) else d.get("deviations", []) if isinstance(d, dict) else []
        for x in items:
            out.append("Lane B: " + (x if isinstance(x, str) else json.dumps(x))[:400])
    return out


def findings(m: dict, T: dict) -> list[str]:
    g = lambda k, nd=3: fmt(m.get(k), nd)
    cl = {c["id"]: c for c in T["claims"]}
    return [
        f"Ledger: {m.get('n_match')}/{m.get('n_numbers_rederived')} numerically comparable quoted numbers reproduce (match rate {g('match_rate')}); "
        "the rest are genuine mismatches (P0 deep-layer |cos|, band-limited '138x', TOST alpha) or DIFFERENT_ESTIMAND rows, all listed.",
        f"Abliterated row (the never-run test): held-out request-axis d mlabonne {g('abliterated_d_peak', 2)} vs parent instruct {g('heldout_d_instruct', 2)} "
        f"(delta {g('abliterated_minus_parent_d', 2)} [{g('abliterated_minus_parent_d_ci_lo', 2)}, {g('abliterated_minus_parent_d_ci_hi', 2)}]); "
        f"it falls in {m.get('n_effective_pairs_heldout_d_drop_ci_below_0')}/6 effective pairs and NOT on the granite null edit "
        f"({g('granite_null_edit_delta_heldout_d', 2)}), whereas BL1 ({g('granite_null_edit_delta_BL1_easy', 2)}) and peak drive "
        f"({g('granite_null_edit_delta_peak_drive', 2)}) both move on that behavioural no-op. HARD-refit recognition R barely moves "
        f"({g('abliterated_minus_parent_R_tpr5')}); peak drive falls to {g('abliterated_peak_drive', 2)} vs Base {g('base_peak_drive', 2)}.",
        f"Safety training moves recognition: HARD R TPR@5%FPR Base->instruct delta {g('base_to_instruct_R_tpr5_delta')} "
        f"(90% CI [{g('base_to_instruct_R_tpr5_delta_ci90_lo')}, {g('base_to_instruct_R_tpr5_delta_ci90_hi')}]); 'execution, not recognition' is scoped to abliteration.",
        f"STaR (non-safety FT) matches Base only on held-out d (diff {g('STaR_minus_Base_heldout_d')}, TOST +/-0.5 EQUIVALENT); it covers "
        f"{g('STaR_fraction_of_base_to_instruct_peak_drive', 2)} of the Base->instruct distance on peak drive and "
        f"{g('STaR_fraction_of_base_to_instruct_BL1', 2)} on BL1 (EASY).",
        "Accumulation: " + cl.get("acc", {}).get("verdict", "") + " -- with the axis frozen at a shallow layer the norm-controlled gap "
        "decays with depth in every arm; growth exists only for an axis refit per layer (layer-specific direction).",
        "Site dissociation (three sites, per lineage): " + cl.get("vii", {}).get("verdict", "") + ". The LATE-response TPR@1%FPR drop at full "
        f"lesion is L1 {g('site_delta_tpr1_late_L1')}, L2 {g('site_delta_tpr1_late_L2')}, L3 {g('site_delta_tpr1_late_L3')}, L4 (non-safety, does not refuse) "
        f"{g('site_delta_tpr1_late_L4')}; no safety-minus-L4 contrast excludes 0, so the late drop reads as generic readout disruption, "
        "not loss of refusal execution. The true PROMPT site (lastp) and EARLY response window stay within CIs of 0 at alpha=1.",
        "The post-lesion 0.000 cosine is FORCED_BY_CONSTRUCTION and removed; the informative band cosine is 0.976-0.990 at layer 13. "
        "The 10.6x ratio is dropped.",
        f"Activation readouts vs BL1 across 25 checkpoints: Spearman with BL1_hard is {g('panel_spearman_heldout_d_peak_vs_BL1_hard', 2)} "
        f"(held-out d), {g('panel_spearman_R_TPR5_registered_vs_BL1_hard', 2)} (R), {g('panel_spearman_peak_drive_vs_BL1_hard', 2)} (peak drive); "
        f"partial Spearman with harmful compliance given BL1: held-out d {g('panel_partial_spearman_heldout_d_peak_vs_HC_given_BL1', 2)}, "
        f"R {g('panel_partial_spearman_R_TPR5_registered_vs_HC_given_BL1', 2)}, peak drive {g('panel_partial_spearman_peak_drive_vs_HC_given_BL1', 2)}.",
        f"Gates: {m.get('n_gates_pass')} pass / {m.get('n_gates_fail')} fail of {m.get('n_gates_total')} rows (dataset 22/25 reproduced; Lane A G1 and G5 fail "
        "everywhere; G6 licenses subtraction only in the non-safety arms).",
    ]


# ----------------------------------------------------------------------------- main
@logger.catch(reraise=True)
def main() -> None:
    D = load_all()
    logger.info(f"panel checkpoints: {len(D['panel'])}; laneb cells: {len(site_rows(D))}")
    master = master_table(D)
    pairs = pair_table(D)
    led = build_ledger(D)
    laneb_ledger(D, led)
    claims = claims_table(D, master)
    T = {"master": master, "bl1_corr": panel_corr_with_bl1(master), "pairs": pairs, "claims": claims,
         "site": site_table(D), "accum": accumulator_table(D), "power": power_table(D),
         "gates": D.get("gates_table") or [], "notation": D.get("notation_table") or [], "ledger": led.rows}
    t = D.get("laneb_tests") or {}
    holm = t.get("holm_across_all_48") or {}
    site16 = {k: v for d in (t.get("holm_within_each_site_16") or {}).values() for k, v in d.items()}
    T["tests"] = clean([{"test": x.get("name"), "obs_mean_hit_diff": x.get("observed_mean_hit_diff"), "p_perm": x.get("p_perm"),
                         "holm48": (holm.get(x.get("name")) or {}).get("decision", "not listed"),
                         "holm16_site": (site16.get(x.get("name")) or {}).get("decision", "not listed")}
                        for x in t.get("tests", [])] +
                       [{"test": f"TOST {r['lineage']}|{r['site']}", "largest_alpha_equivalent": r.get("largest_alpha_equivalent")}
                        for r in t.get("tost_rows", [])])
    T["contrasts"] = clean([{k: v for k, v in r.items() if k.startswith(("site", "alpha", "lineage", "contrast"))}
                            for r in (D.get("laneb_contrasts") or {}).get("rows", [])])
    metrics = compute_metrics(D, master, led, pairs)
    T["inventory"] = clean([{"lineage": L, **{k: v for k, v in (D.get("laneb_inventory") or {}).get(L, {}).items()
                                              if k in ("repo", "r_ablit_layer", "n_npz_files", "lastp_layers_stored", "win_layers_stored")},
                             "group_rows_match_expected": (D.get("laneb_inventory") or {}).get(L, {}).get("group_row_counts")
                             == (D.get("laneb_inventory") or {}).get(L, {}).get("expected_group_row_counts")}
                            for L in ("L1", "L2", "L3", "L4")])
    T["own_deviations"] = own_deviations(D)
    for r in T["bl1_corr"]:
        metrics[f"panel_spearman_{r['readout']}_vs_BL1_hard"] = r.get("spearman_with_BL1_hard")
        metrics[f"panel_partial_spearman_{r['readout']}_vs_HC_given_BL1"] = r.get("partial_spearman_with_HC_given_BL1")
    T["findings"] = findings(metrics, T)
    for name, rows in T.items():
        pd.DataFrame(rows).to_csv(RES / f"{name}_table.csv" if not name.endswith("table") else RES / f"{name}.csv", index=False)
    (RES / "tables.json").write_text(json.dumps(clean(T), indent=1, default=str))
    (RES / "deviations_ledger.json").write_text(json.dumps(clean(led.rows), indent=1, default=str))
    out = build_eval_out(D, master, claims, led, pairs, metrics)
    (WS / "eval_out.json").write_text(json.dumps(clean(out), indent=1, default=str))
    write_summary(T, clean(metrics))
    logger.info(f"ledger: {metrics['n_match']}/{metrics['n_numbers_rederived']} match; datasets "
                f"{[(d['dataset'], len(d['examples'])) for d in out['datasets']]}")


if __name__ == "__main__":
    main()
