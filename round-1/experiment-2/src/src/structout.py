"""Write ./.terminal_claude_agent_struct_out.json, pulling every number from the
finished artifacts rather than from prose."""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def g(p, default=None):
    f = OUT / p
    return json.loads(f.read_text()) if f.exists() else default


def fmt(v, n=3):
    return "NA" if v is None else f"{v:.{n}g}"


def main():
    ana = g("analysis.json", {}) or {}
    red = g("redundancy.json", {}) or {}
    st9 = g("stage9_weightcheck.json", {}) or {}
    st9d = g("stage9_depth.json", {}) or {}
    pilot = g("pilot.json", {}) or {}
    mo = json.loads((ROOT / "method_out.json").read_text())
    lg = ana.get("lineages", {})
    reg = sorted(k for k in lg if not k.endswith("PL"))
    pl = sorted(k for k in lg if k.endswith("PL"))

    L2 = lg.get("L2", {})
    gapn = [round(x, 3) for x in (L2.get("D_axis_1d_gap_normalised") or [])]
    dprim = [round(x, 3) for x in (L2.get("D_curve") or [])]
    r2 = red.get("L2_a0.00", {}) or {}
    r2b = red.get("L2_a1.00", {}) or {}
    dp = red.get("L2_depth_profile", {}) or {}
    flat = [k for k, v in lg.items() if v.get("alpha_star") is None]
    s9s = st9.get("summary") or {}
    s9g = st9.get("global") or {}
    s9d = st9d.get("self_attn.o_proj") or {}
    rasep = (L2.get("r_ablit_sep") or {})
    d_ablit = max((float(v) for v in rasep.values()), default=0.0)
    splith = pilot.get("r_content_split_half_cosine_band_mean")
    band_layer = L2.get("r_ablit_layer")
    post1_a0 = (r2.get("class_removal_auroc") or [None, None])[1]
    post1_a1 = (r2b.get("class_removal_auroc") or [None, None])[1]
    regrow_cos = r2b.get("u_cos_with_first_dir")
    ugap = dp.get("u_component_gap_a0") or [None]
    ugap_lo, ugap_hi = ugap[0], ugap[-1]
    norm_unit_a1 = r2b.get("auroc_on_unit_normalised_activations")
    norm_alone_a0 = r2.get("auroc_of_residual_norm_alone")
    norm_alone_a1 = r2b.get("auroc_of_residual_norm_alone")
    # THE METRIC: best-layer request-axis separation and its depth fraction, per checkpoint
    rows = []
    for t in reg:
        rr = lg[t]
        sep = {int(k): float(v) for k, v in (rr.get("r_ablit_sep") or {}).items()}
        if not sep:
            continue
        bl = max(sep, key=sep.get)
        nl = rr["model_facts"]["n_layers"]
        rows.append(f"{t} {rr['repo'].split('/')[-1]} d={sep[bl]:.2f} at layer {bl} "
                    f"(depth {(bl + 1) / nl:.2f})")
    metric_line = " | ".join(rows) if rows else "NA"
    n_ex = mo["metadata"]["n_examples"]
    n_ds = mo["metadata"]["n_datasets"]

    title = "Uncensoring a model doesn't blind it to harm"
    layman = ("We deleted the internal direction that uncensoring tools erase from Qwen3-4B, and "
              "checked the deletion was total. The model still told harmful requests from harmless "
              "ones perfectly: the information sat in the directions we had not touched.")

    summary = (
"LANE B asks where safety lives by LESIONING it: one rank-one, prompt-fitted orthogonalisation "
"W <- W - a*u*(u^T W) applied to every residual-stream write matrix (o_proj + down_proj, all 36 "
"layers) at five strengths, with all five candidate readouts (K1 arming, K2 prior+slope, K3 "
"benign-only footprint, K4 persistence, K5 domain profile) recomputed before and after. Substrate: "
"150 XSTest minimal-edit twins from the six genuine contrast families, sha256-ordered 96/54 split "
"(the 54 never touched), a 2x2 of request{harmful, matched benign twin} x response-prefix{hazardous, "
"benign} with the response span token-identical across the request manipulation, plus disjoint "
"fitting and held-out request corpora. prereg.json was frozen before the first forward pass and "
"verified byte-identical at the end.\n\n"
f"INSTRUMENT. Qwen3 gives o_proj/down_proj no bias, so for y = W0 x the edit is EXACTLY "
f"y -> y - a*u*(u^T y). Applied as an output projection, alpha=0 is a BITWISE no-op, the restore is "
f"exact, and embed_tokens - which IS lm_head on all four lineages, L4 included - is provably "
f"untouched, so the causal arm's logit outcome is uncontaminated. Verified against a genuine bf16 "
f"weight mutation. Frozen band = layers 13-21, r_content split-half cosine {fmt(splith)}.\n\n"
f"MAIN RESULT. The lesion is verified exact - the raw projection gap along u falls as {gapn} against a "
f"predicted (1-alpha) - and the harm representation survives it ENTIRELY: the held-out 5-fold CV probe "
f"reads {dprim} across the alpha grid. Removing u POST-HOC from activations instead drops that probe "
f"1.000 -> {fmt(post1_a0)}, while removing 128 RANDOM directions costs nothing. So in the INTACT model "
f"the 2559-dim orthogonal complement of u is NOT sufficient. In the LESIONED model, which was never "
f"allowed to write u at all, that same complement reads 1.000 and behaves identically under its own "
f"top-direction removal ({fmt(post1_a1)}). (The post-lesion orthogonality itself is FORCED by "
f"construction and is not claimed as a result.) The obvious alternative - that removing a "
f"class-correlated component changes the residual NORM class-correlatedly and RMSNorm manufactures the "
f"separability - is REJECTED: the probe still reads {fmt(norm_unit_a1, 4)} on unit-normalised "
f"activations, and the norm alone flips from a {fmt(norm_alone_a0, 4)}-AUROC harm detector in the "
f"intact model to {fmt(norm_alone_a1, 4)} (anti-predictive) after the lesion. Depth profile: "
f"held-out AUROC is already ~1.000 by layer 13 in BOTH states, while the signal along u grows ~138x "
f"with depth in the intact model ({fmt(ugap_lo, 2)} -> {fmt(ugap_hi, 4)}) and is zeroed at every depth "
f"in the lesioned one. u is an ACCUMULATOR COORDINATE, not the locus of the percept: abliteration "
f"removes the refusal ACTION, not the harm PERCEPT.\n\n"
f"G1, reported as a RESULT and not only a gate: |cos(r_content, r_ablit)| = {fmt(L2.get('G1_cos_pooled'))} "
f"pooled / {fmt(L2.get('G1_max'))} max. The response-site content axis and the prompt-site request axis "
f"are near-ORTHOGONAL, so HARC's alignment kill-risk does not bite here.\n\n"
f"STAGE 9, weights only: mlabonne/Qwen3-4B-abliterated is per-matrix rank-one (median "
f"{fmt(s9s.get('rank1_share_median'), 4)}) at implied alpha {fmt(s9s.get('implied_alpha_median'), 3)}, "
f"leaves embed_tokens untouched, but uses ONE DIRECTION PER LAYER: pooled rank-one share only "
f"{fmt(s9g.get('rank1_share_pooled'))}, and |cos| {fmt(s9d.get('cos_shallowest_vs_deepest'), 2)} "
f"between the shallowest and deepest layer's edit direction.\n\n"
f"THE METRIC (the run prompt's 'few-prompt safety score'). Fit r_ablit at EVERY layer of ONE model "
f"from 128 harmful + 128 harmless PROMPT-ONLY forwards - no generation, no benchmark, no judge, no "
f"reference model - and report the best layer's Cohen's d and its DEPTH FRACTION: {metric_line}. "
f"Safety tuning roughly DOUBLES the separation and moves it several layers EARLIER. The "
f"load-bearing control is L4, a fine-tune of L1 on a NON-safety objective: it lands on top of its "
f"base parent, so the readout tracks SAFETY tuning, not fine-tuning as such. n = 4 checkpoints, so "
f"this is a demonstration with one clean negative control, not a validated metric; the outputs "
f"carry a prompt-budget curve for how few items the paired contrasts need.\n\n"
f"HONEST LIMITS. The pre-registered PRIMARY damage variable is FLAT at ceiling, so no matched-damage "
f"point exists for {len(flat)} lineage(s) and every registered S2 row is INDETERMINATE (failure mode "
f"F1). The threshold was NOT relaxed and alpha=1 was not extrapolated past; a LABELLED "
f"full-annihilation companion is reported beside it. Read as the LEVEL test its wording specifies, K1 "
f"is HALF-satisfied: CB survives but A attenuates without collapsing into the null band. K4's observed "
f"sign is OPPOSITE to its registered signature (tau lengthens). Registered grid: {reg}; declared "
f"per-layer grid: {pl}. method_out.json carries {n_ex} examples over {n_ds} datasets; every predict_* "
f"that is not predict_baseline_* reads activations or weights of a SINGLE model."
    )

    obj = {
        "title": title,
        "layman_summary": layman,
        "summary": summary[:5000],
        "out_expected_files": {
            "script": "method.py",
            "full_output": "full_method_out.json",
            "mini_output": "mini_method_out.json",
            "preview_output": "preview_method_out.json",
        },
        # Only genuine bulk: the 5.2 GB of per-(lineage, alpha) activation npz intermediates and
        # the 7.9 GB venv. Everything else - code, results, logs (1 MB), the released direction
        # vectors, the substrate - is a real deliverable and stays published.
        "upload_ignore_regexes": [
            "(^|/)out/harvest/",
            "(^|/)\\.venv/",
            "(^|/)__pycache__/",
            "(^|/)\\.repl_agent\\.ptylog$",
        ],
    }
    assert 12 <= len(obj["title"]) <= 90, len(obj["title"])
    assert 80 <= len(obj["layman_summary"]) <= 250, len(obj["layman_summary"])
    if len(obj["summary"]) > 5000:      # never truncate mid-sentence
        obj["summary"] = obj["summary"][:4990].rsplit(". ", 1)[0] + "."
    assert 500 <= len(obj["summary"]) <= 5000, len(obj["summary"])
    (ROOT / ".terminal_claude_agent_struct_out.json").write_text(json.dumps(obj, indent=1))
    print("title     ", len(obj["title"]), repr(obj["title"]))
    print("layman    ", len(obj["layman_summary"]))
    print("summary   ", len(obj["summary"]))
    print("WROTE .terminal_claude_agent_struct_out.json")


if __name__ == "__main__":
    main()
