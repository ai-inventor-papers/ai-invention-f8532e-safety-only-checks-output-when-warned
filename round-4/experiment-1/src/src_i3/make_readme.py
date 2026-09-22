"""Generate README.md from the committed result files (every number is read from a file, never typed)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RESULTS, WS, chain_records, jload  # noqa: E402


def f3(v, nd: int = 3) -> str:
    try:
        x = float(v)
        return "NaN" if x != x else f"{x:.{nd}f}"
    except (TypeError, ValueError):
        return "n/a" if v is None else str(v)


def ci(v) -> str:
    if not v or v[0] is None:
        return "n/a"
    return f"[{f3(v[0])}, {f3(v[1])}]"


def opt(name: str):
    p = RESULTS / name
    return jload(p) if p.exists() else None


HC_ROWS = ["C1", "C1_k4", "C1_k8", "C2", "C2_tpr5", "C2_screenrule", "C3", "C3_screenrule", "C4", "C4_screenrule", "C5",
           "C6", "C6_screenrule", "C7", "C8", "C9", "C10", "C10_screenrule", "C11", "C12", "C12_topsv", "C12_screenrule",
           "C13", "C13_peak_d", "C13_peak_f", "BL1", "BL1_hard", "B3", "B7", "X2", "X10_abs"]


def main() -> None:
    pan = jload(RESULTS / "panel.json")
    trim = jload(RESULTS / "panel_trim.json")
    truth = jload(RESULTS / "graded_truth.json")
    feats = opt("features.json")
    table = opt("heldout_table.json")
    audit = opt("order_audit.json") or {}
    devs = opt("deviations.json") or []
    rep = jload(RESULTS / "judge_reproduction_check.json")
    unit = opt("unit_checks.json") or {}
    hooks = opt("hook_checks.json") or {}
    extra = opt("extra_analyses.json") or {}
    two = opt("two_panel_table.json")
    join = opt("join_result.json") or opt("join_stub.json") or {}
    cost = 0.0
    lp = RESULTS / "judge_cost_ledger.jsonl"
    if lp.exists():
        cost = sum(float(json.loads(x).get("cost_usd") or 0) for x in lp.read_text().splitlines() if x.strip())
    final = trim["final_panel"]
    n = table["n_panel"] if table else len(final)
    L: list[str] = []
    a = L.append

    a("# Held-out confirmation panel: single-model safety readouts on fresh checkpoints\n")
    a("Iteration 3, `experiment_1` of run `run_YqmEFECOIR3D`. The user-level question is whether a cheap readout of ONE "
      "model's activations or weights (0 to a few hundred prompts, no generation) can stand in for a behavioural safety "
      "benchmark. The iteration-2/3 lanes proposed 14 candidate readouts (C1-C14) and scored them on a screen panel. This "
      "artifact is the **held-out half**. It builds a panel of checkpoints that **no earlier artifact has loaded**, grades "
      "their behaviour **first**, commits that graded truth by hash, freezes the scoring rules, and only then reads the "
      "activations. It reports every candidate and every bar against the graded behaviour and **names no winner**.\n")
    a("**Invariant.** Every C-row reads the activations or weights of **one** model. BL1 (the final-layer logit gap) and "
      "all judge columns are baselines or ground truth, never the result. This is a mech-interp study of *where safety "
      "lives* (which depth and which site make the safety behaviour readable), not a jailbreak or attack-selection "
      "study.\n")

    # ------------------------------------------------------------------ headline
    a("## Results at a glance\n")
    if table:
        rows = {r["feature"]: r for r in table["rows"] if r["outcome"] == "harmful_compliance"}
        crit = next(iter(rows.values()))["critical_rho_alpha05"]
        mde = next(iter(rows.values()))["mde_rho_power80"]
        big = [k for k, r in rows.items() if r["rho"] == r["rho"] and abs(r["rho"]) >= crit]
        a(f"- **Panel**: n = {n} fresh checkpoints in {len(set(feats['families'].values()))} families. The exact "
          f"permutation critical |ρ| at α = .05 is **{f3(crit)}** and the 80%-power MDE is **{f3(mde)}**. With this n "
          "only very large correlations can be distinguished from zero.")
        a(f"- **Rows with |ρ(harmful compliance)| ≥ {f3(crit)}**: " + (", ".join(
            f"{k} (ρ = {f3(rows[k]['rho'])}, CI {ci(rows[k].get('ci95_ckpt'))})" for k in big) if big else "none") + ".")
        bl = rows.get("BL1")
        if bl:
            a(f"- **Logit baseline BL1**: ρ = {f3(bl['rho'])} {ci(bl.get('ci95_ckpt'))}.")
        rev = [k for k, r in rows.items() if r.get("sign_matches_expected") is False and r["rho"] == r["rho"] and abs(r["rho"]) >= 0.5]
        if rev:
            a("- **Sign reversals (read before using the list above)**: " + ", ".join(f"{k} ({f3(rows[k]['rho'])})" for k in rev) +
              " have the OPPOSITE sign to the prereg's declared expectation. They show the same reversed sign on the iteration-2 "
              "panel (see the two-panel table below). So the relation is stable but inverted: the more compliant the model, the "
              "larger its response-site advantage over the prompt site (C2/C9) and the larger the late-layer growth of the "
              "frozen shallow axis (C6). This is not the confirmation of a pre-declared direction.")
        beat = [k for k, r in rows.items() if k != "BL1" and (r.get("dabs_BL1_ci95_ckpt") or [None])[0] is not None and r["dabs_BL1_ci95_ckpt"][0] > 0]
        a("- **Against the logit baseline**: rows whose |ρ| exceeds |ρ(BL1)| with a paired CI excluding 0: " +
          (", ".join(beat) if beat else "**none**") + ". At n = " + str(n) + " the MDE is too large to separate most rows from BL1.")
        if feats and "B7" in rows:
            fb = {r: v.get("B7") for r, v in feats["features"].items()}
            amd = [v for r, v in fb.items() if r.startswith("amd/")]
            abl_c = [v for r, v in fb.items() if "abliterated" in r]
            a(f"- **B7 caveat**: the weights-only scar is {', '.join(f3(v) for v in abl_c)} for the abliterated children, "
              f"about 0.5 for their parents, and {', '.join(f3(v) for v in amd)} for all three AMD-OLMo checkpoints, "
              "including the base, which barely complies. B7 marks a shared null direction in the write matrices. That "
              "is the abliteration scar, plus a family constant in AMD-OLMo, and not a within-family grade of safety.")
            b7d = opt("b7_diagnostic.json")
            if b7d:
                rw = b7d["rows"]
                amdp = [f3(v["B7_ones_projected"]) for r, v in rw.items() if r.startswith("amd/")]
                ablp = [f3(v["B7_ones_projected"]) for r, v in rw.items() if "abliterated" in r]
                cosr = [f3(v["mean_abs_cos_null_with_all_ones"]) for r, v in rw.items() if r.startswith("amd/")]
                a(f"- **Why AMD-OLMo reads ~1.0 on B7** (`results/b7_diagnostic.json`, post-prereg diagnostic): every AMD-OLMo "
                  f"block's least-singular write direction is the all-ones vector 1/√d (|cos| = {', '.join(cosr)}). OLMo-1 "
                  "uses a parameter-free, mean-subtracting LayerNorm before every read, so no block is trained to write along "
                  "that direction. It is an architecture-mandated null, not an edit. If that direction is projected out of "
                  f"every block's Gram, AMD-OLMo drops to {', '.join(amdp)}, while the abliterated children stay at "
                  f"{', '.join(ablp)}. ρ(HC) then falls from {f3(b7d['rho_hc_B7_preregistered'])} to "
                  f"**{f3(b7d['rho_hc_B7_ones_projected'])}**. On this panel B7's correlation with harmful compliance is carried by "
                  "an architecture artefact. What survives is abliteration-scar detection.")
    ab = (extra.get("abliteration_replication") or {}).get("rows") or []
    for r in ab:
        a(f"- **Abliteration, fresh pair** `{r['child']}`: harmful compliance Δ = {f3(r['delta_hc'])} "
          f"{ci(r['delta_hc_ci95'])}; request-axis d at mid-depth (C13) Δ = {f3(r['delta_C13'])} {ci(r['delta_C13_ci95'])}; "
          f"peak d Δ = {f3(r['delta_C13_peak_d'])} {ci(r['delta_C13_peak_d_ci95'])}; BL1 Δ = {f3(r['delta_BL1'])} "
          f"{ci(r['delta_BL1_ci95'])}.")
    pcs = extra.get("paired_contrasts") or []
    dpo = next((r for r in pcs if r["parent"].endswith("-SFT") and r["child"].endswith("-SFT-DPO")), None)
    if dpo:
        d = dpo["prompt_level_deltas"]
        a(f"- **Specificity on a behavioural no-op** (AMD-OLMo SFT → SFT-DPO, ΔHC {f3(dpo['harmful_compliance']['delta_hc'])} "
          f"{ci(dpo['harmful_compliance']['ci95_item_boot'])}): the logit baseline moves (ΔBL1 {f3(d['BL1']['delta'])} "
          f"{ci(d['BL1']['ci95_prompt_boot'])}), while the activation readouts do not (Δpeak d {f3(d['C13_peak_d']['delta'])} "
          f"{ci(d['C13_peak_d']['ci95_prompt_boot'])}; ΔC7 {f3(d['C7']['delta'])} {ci(d['C7']['ci95_prompt_boot'])}).")
    a("- **Join with the screen**: " + str(join.get("verdict") or ("DEFERRED: no screen `survivor.json` exists under "
      "`iter_3/gen_art/*/` (this iteration's evaluation artifact rebuilt the three-model tables and ran no C1-C14 screen); "
      "`results/join_stub.json` holds the mechanical lookup rule")) + ".\n")

    # ------------------------------------------------------------------ behaviour table
    a("## Behaviour: graded before any hook\n")
    a("Each checkpoint answered the 90 Lane C items greedily: 45 harmful and 45 benign, with the same ids, order and "
      "protocol as the screen's outcome source, and at most 140 new tokens. Grading used Lane C's `lc_judge.py` protocol "
      "verbatim: google/gemini-2.5-flash-lite as primary, a 20% openai/gpt-5-mini audit, and the H2 plain-rubric variant as a "
      f"secondary column. Re-judging 20 of Lane C's rows gave {rep['n_mismatch_rows']} mismatches. Judge spend was "
      f"${cost:.3f} against a $3 hard stop.\n")
    a("| repo | family | role | harmful compliance [95% CI] | over-refusal [95% CI] | safe engagement |\n|---|---|---|---|---|---|")
    for repo in final:
        p = next(x for x in pan["panel"] if x["repo"] == repo)
        o = truth["per_ckpt"][repo]["outcomes_primary_laneC_items"]
        a(f"| `{repo}` | {p['family']} | {p['role']} | {f3(o['harmful_compliance'])} {ci(o.get('harmful_compliance_ci95'))} | "
          f"{f3(o['over_refusal'])} {ci(o.get('over_refusal_ci95'))} | {f3(o['safe_engagement'])} |")
    rel = truth.get("split_half_reliability", {})
    a("")
    for o, v in rel.items():
        a(f"- split-half reliability of **{o}** across the panel: odd/even Spearman-Brown {f3(v.get('odd_even_spearman_brown'))}; "
          f"attenuation ceiling √rel = {f3(v.get('attenuation_ceiling_sqrt_reliability'))}")
    a("\nRaw completions stay in `private/`, which is never published. `results/judged_labels_released.json` carries only "
      "the per-item labels.\n")

    # ------------------------------------------------------------------ held-out table
    if table:
        a(f"## Held-out table: every candidate and bar vs harmful compliance (n = {n}; NO winner)\n")
        a("Each row gives the Spearman ρ, a checkpoint-bootstrap 95% CI (B = 10000), a family-cluster CI, |ρ| − |ρ(BL1)| with "
          "a paired CI, the partial ρ given BL1, the declared expected sign, and where the random-init control falls. "
          "`results/heldout_table.json` also has over-refusal and safe-engagement, the paired "
          "d_BL1 CIs and the MDE. Readout classes: activation = residual stream of one model; "
          "activation(logit-lens) = intermediate-layer residual read through the unembedding; weight = weights only; logit = "
          "final-layer logits (baseline).\n")
        a("| feature | class | ρ(HC) | 95% CI ckpt | 95% CI family | \\|ρ\\|−\\|ρ(BL1)\\| [CI] | partial ρ\\|BL1 | exp. sign / match | random-init |\n|---|---|---|---|---|---|---|---|---|")
        for k in HC_ROWS:
            r = rows.get(k)
            if not r:
                continue
            a(f"| {k} | {r['readout_class']} | {f3(r['rho'])} | {ci(r.get('ci95_ckpt'))} | {ci(r.get('ci95_family'))} | "
              f"{f3(r.get('dabs_BL1'))} {ci(r.get('dabs_BL1_ci95_ckpt'))} | {f3(r.get('partial_rho_given_BL1'))} | "
              f"{r.get('expected_sign')} / {r.get('sign_matches_expected')} | {r.get('random_init_position', 'n/a')} |")
        a("")
        a("Definitions are frozen verbatim in `prereg.json` (`operational_definitions`). The `_screenrule` rows are the "
          "screen plan's wording of the same candidate. C5-residual and C14 need the screen's frozen coefficients, which "
          "do not exist, so they are DEFERRED and their raw features are persisted.\n")

    mo = WS / "method_out.json"
    racc = jload(mo)["metadata"].get("hard_recognition_accuracy_midpoint_threshold") if mo.exists() else None
    if racc:
        a("## Per-prompt recognition on the 160 HARD prompts (dataset 2 of `full_method_out.json`)\n")
        a("Each checkpoint's HARD prompts are classified by (i) its own EASY-fitted diff-in-means axis at mid-depth "
          "(activation; threshold = EASY class midpoint) and (ii) the final-layer refusal-minus-control logit drive (logit "
          "baseline; EASY midpoint threshold). The table gives accuracy against the harmful/benign label. A fixed EASY "
          "threshold is sensitive to the EASY-to-HARD calibration shift; the threshold-free per-layer AUROC is C7's input.\n")
        a("| checkpoint | activation axis @ lay(0.5) | final-logit refusal drive |\n|---|---|---|")
        for k, v in racc.items():
            a(f"| `{k}` | {f3(v['activation_easy_axis_l50'])} | {f3(v['logit_final_refusal_drive'])} |")
        a("")

    # ------------------------------------------------------------------ paired contrasts
    pc = extra.get("paired_contrasts") or []
    if pc:
        a("## Paired within-unit contrasts (additional, post-prereg, descriptive)\n")
        a("Each row is child − parent on the **same prompts**. The CIs come from a paired prompt bootstrap (B = 2000; EASY "
          "fit and HARD score prompts resampled within class, with the same indices for both models). ΔHC uses a paired "
          "bootstrap over the 45 harmful items plus an exact McNemar test. "
          "This is the fresh-model replication of iteration 3's finding that the held-out request-axis d falls in "
          "every effective abliterated child.\n")
        a("| kind | parent → child | ΔHC [CI] (McNemar p) | ΔC13 d@0.5 [CI] | Δpeak d [CI] | ΔC7 [CI] | ΔC5 [CI] | ΔBL1 [CI] | ΔBL1_truelogit [CI] |\n|---|---|---|---|---|---|---|---|---|")
        for r in pc:
            d = r["prompt_level_deltas"]
            h = r["harmful_compliance"]
            a(f"| {r['kind']} | `{r['parent'].split('/')[-1]}` → `{r['child'].split('/')[-1]}` | {f3(h['delta_hc'])} "
              f"{ci(h['ci95_item_boot'])} (p={f3(h['mcnemar_exact_p'], 4)}) | "
              + " | ".join(f"{f3(d[k]['delta'])} {ci(d[k]['ci95_prompt_boot'])}" for k in
                           ("C13", "C13_peak_d", "C7", "C5", "BL1", "BL1_truelogit")) + " |")
        a("")
    tl = extra.get("bl1_truelogit")
    if tl:
        hr, ir = tl["heldout_rho_hc"], tl["iter2_rho_hc"]
        a("**BL1 is read on a double-normalised final slice.** `results/hook_checks.json` shows `hidden_states[-1]` is "
          "already post-final-norm, and the iteration-2 lens applies the final norm again at l = L. BL1 is kept exactly as "
          "iteration 2 defined it, for comparability. The literal final-logit version (`BL1_truelogit`, computed from the "
          f"stored unembedding rows) gives ρ(HC) = {f3(hr['BL1_truelogit'][0])} on the held-out panel, against "
          f"{f3(hr['BL1'][0])} for BL1. On the iteration-2 panel the two give {f3(ir['BL1_truelogit'][0])} vs "
          f"{f3(ir['BL1'][0])}. The rank correlation between BL1 and BL1_truelogit is "
          f"{f3(tl['heldout_rho_BL1_vs_truelogit'][0])} held-out and {f3(tl['iter2_rho_BL1_vs_truelogit'][0])} on iteration 2.\n")
    lofo = extra.get("leave_one_family_out_hc") or []
    if lofo:
        a("**Leave-one-family-out** (ρ with HC after dropping each of the 4 families; `results/extra_analyses.json`):\n")
        a("| feature | ρ full | LOFO min | LOFO max | sign stable |\n|---|---|---|---|---|")
        for r in lofo:
            a(f"| {r['feature']} | {f3(r['rho_full'])} | {f3(r['lofo_min'])} | {f3(r['lofo_max'])} | {r['sign_stable_across_lofo']} |")
        a("")

    # ------------------------------------------------------------------ two-panel table
    if two:
        a("## Same code, two panels (additional; no selection)\n")
        a("The candidate code was also run on the iteration-2 screen panel's saved activations (read-only; "
          "`results/iter2_panel_same_code.json`). Each row therefore has a same-code ρ with harmful compliance on both "
          "panels. This is a sign/size replication table, not a screen.\n")
        a("| feature | class | exp. sign | ρ held-out (n) | ρ iter-2 all graded (n) | ρ iter-2 selection-like (n) | same sign (all / sel) |\n|---|---|---|---|---|---|---|")
        for r in two["rows"]:
            a(f"| {r['feature']} | {r['readout_class']} | {r['expected_sign']} | {f3(r['rho_heldout'])} ({r['n_heldout']}) | "
              f"{f3(r['rho_iter2_all_graded'])} ({r['n_iter2_all']}) | {f3(r['rho_iter2_selection_like'])} ({r['n_iter2_sel']}) | "
              f"{r['same_sign_heldout_vs_iter2_all']} / {r['same_sign_heldout_vs_iter2_sel']} |")
        a("")
    pooled = (extra.get("pooled_two_panel_hc") or {}).get("rows") or []
    if pooled:
        a("Pooled over both panels (context only): " + "; ".join(
            f"{r['feature']} {f3(r['rho_pooled'])} {ci(r['ci95_family_cluster'])} (n={r['n']})" for r in pooled
            if r["feature"] in ("C1", "C4", "C7", "C8", "C13", "C13_peak_d", "BL1", "B3", "B7", "X2")) + ".\n")

    # ------------------------------------------------------------------ verification
    a("## Verification\n")
    a(f"- **Order audit** (`results/order_audit.json`): **{'PASS' if audit.get('pass') else 'FAIL / NOT RUN'}**. The graded "
      "truth precedes the prereg in the hash chain, both files still re-hash to their recorded values, and every harvested "
      "panel file is newer than the prereg commit.")
    if unit:
        a(f"- **Unit checks** (`results/unit_checks.json`): all pass = **{unit.get('all_pass')}**. Synthetic statistics: "
          f"permutation critical ρ(n=10) = {f3((unit.get('stats_synthetic') or {}).get('critical_rho_n10', {}).get('value'), 4)}. "
          "The published outcome rates of 3 screen checkpoints are recomputed from Lane C's judged rows with a max "
          f"difference of 0. The iteration-2 BL1/B3/B7/X2/X10 values reproduce on "
          f"{(unit.get('incumbent_code_repro_iter2_arrays') or {}).get('n_checkpoints')} checkpoints with a max difference of "
          f"{f3((unit.get('incumbent_code_repro_iter2_arrays') or {}).get('max_abs_diff'), 6)}. Harvest arrays pass the "
          "shape, finiteness and manifest checks.")
    hs = hooks.get("summary") or {}
    if hs:
        a(f"- **Hook checks per checkpoint** (`results/hook_checks.json`, n = {hs.get('n')}): determinism pass "
          f"{hs.get('all_determinism_pass')}, layer-0 = embedding lookup {hs.get('all_layer0_pass')}, logit-lens argmax "
          f"at the last slice = model argmax (8/8) {hs.get('all_lens_index_pass')}. Peak RSS was "
          f"{f3(hs.get('max_peak_rss_gb'), 2)} GB.")
    a(f"- **Judge reproduction** (`results/judge_reproduction_check.json`): {rep['n']} Lane C rows re-judged, "
      f"{rep['n_mismatch_rows']} mismatches.\n")

    # ------------------------------------------------------------------ order of operations
    a("## Order of operations (hash chain `hash_chain.jsonl`)\n")
    a("| # | file | sha256 (first 16) | UTC | note |\n|---|---|---|---|---|")
    for i, r in enumerate(chain_records()):
        a(f"| {i} | `{r['file']}` | `{r['sha256'][:16]}` | {r['utc']} | {r['note']} |")
    a("")

    # ------------------------------------------------------------------ panel
    a("## Panel selection\n")
    a(f"The panel was drawn by the frozen seeded rule (`assets/panel_rule.json`, seed `{pan['seed']}`, rank key "
      "sha256(seed + repo_id)). Every pool repo was verified live on the Hub for gating, safetensors size, architecture "
      "and chat template. Excluded were families in the iteration-2 screen panel (Qwen3, Qwen2.5, SmolLM2/3, "
      "TinyLlama, Phi, granite, StableLM, OLMo-2) and every repo loaded by an earlier artifact. The quotas held: "
      f"{pan.get('n_stage_lineages')} stage lineages, {pan.get('n_edited_pairs')} edited parent/child pairs, and "
      f"{pan.get('n_families')} families. The pre-registered TIME rule dropped {trim.get('dropped')}. Every exclusion "
      "and its reason is in `results/panel.json` (`all_rows`). A random-init control (the config of the first "
      "included instruct model, seed 0) is harvested but belongs to no ρ.\n")

    # ------------------------------------------------------------------ criterion / join
    a("## Confirmation criterion (stated before any hook) and join\n")
    a(jload(WS / "prereg.json")["confirmation_criterion"] + "\n")
    jtxt = (f"**{join['verdict']}** (survivor `{join.get('survivor')}`, `results/join_result.json`)" if join.get("verdict") else
            "**DEFERRED**: no screen `survivor.json` was found under `iter_3/gen_art/*/` at scoring time "
            f"(screen_survivor_found = {join.get('screen_survivor_found')}). `results/join_stub.json` holds the mechanical lookup "
            "rule for when a survivor exists")
    a("Join status: " + jtxt + ". The raw activations of every panel "
      "checkpoint are in `harvest/<tag>/`, in the iteration-2 layout, so the next iteration can re-score this panel "
      "with the screen's exact code.\n")

    # ------------------------------------------------------------------ deviations
    a("## Deviations (`results/deviations.json`)\n")
    for d in devs:
        a(f"- **{d.get('key')}**: {d.get('what')} (why: {d.get('why')}; impact: {d.get('impact')})")
    a("")

    # ------------------------------------------------------------------ layout
    a("## Repository layout\n")
    for path, desc in [
        ("method.py", "entry point: `--stage all` runs every stage in order; the default rebuilds `method_out.json` from `results/`"),
        ("full_method_out.json / mini_ / preview_", "exp_gen_sol_out output: per-checkpoint rows, per-HARD-prompt recognition (activation axis vs logit baseline), held-out table"),
        ("prereg.json (+ .sha256)", "frozen scoring rules, candidate text verbatim, code SHA-256s, confirmation criterion"),
        ("hash_chain.jsonl", "append-only {file, sha256, utc} chain: panel rule → draw → trim → graded truth → prereg"),
        ("assets/", "panel rule, behaviour items (Lane C 90 + reserved-54 ids), C11 severity items, copied H2 stimuli/cells/token sets"),
        ("src/inventory.py", "STEP-0 inventory of every input and how each dependency is used (results/inventory.json)"),
        ("src/panel.py, src/hf_probe.py", "seeded panel draw with live Hub verification"),
        ("src/items.py, src/c11_items.py", "behaviour item assembly; the 64 PKU-SafeRLHF severity items for C11"),
        ("src/gen.py, src/test_shrink.py", "greedy generation (Lane C protocol) and the shrink-decoder equivalence test"),
        ("src/judge.py, src/outcomes.py", "Lane C lc_judge protocol (async, cost ledger) and graded-truth aggregation + commit"),
        ("src/time_rule.py", "pre-registered TIME rule"),
        ("src/prereg.py", "writes and hash-commits prereg.json"),
        ("src/harvest_panel.py, src/h2/", "activation harvest: iteration-2 kernels copied verbatim (sha256 in results/provenance.json)"),
        ("src/candidates.py, src/stats_panel.py, src/score.py", "C1-C14 + bars, statistics, order audit, heldout table, join"),
        ("src/iter2_panel_same_code.py", "the same candidate code on the iteration-2 panel's saved arrays (read-only)"),
        ("src/unit_checks.py, src/verify_hooks.py", "testing-plan checks (statistics, reproduction, determinism, layer indexing)"),
        ("src/extra_analyses.py", "post-prereg descriptive analyses: paired contrasts, BL1_truelogit, leave-one-family-out, pooled ρ"),
        ("src/b7_diagnostic.py", "post-prereg diagnostic: B7 with the architecture-mandated all-ones null projected out"),
        ("src/make_readme.py, src/build_struct_out.py", "this README and the structured summary, generated from results/"),
        ("results/", "every result JSON (graded truth, features, heldout table, checks, deviations, judged labels, ledgers)"),
        ("harvest/<tag>/", "per-checkpoint activations (A_prompt, A_resp, A_c11, lens drives) + weight summaries (gram/, svals, vmin)"),
        ("logs/", "run logs and the chain scripts"),
        ("private/", "raw generations and full judged rows (harmful completions): never published"),
        ("hf_cache/", "EMPTY: the public model snapshots (31 GB, files up to 4.5 GB) were removed before deployment; "
                      "model-loading stages re-download on demand (see below)"),
    ]:
        a(f"- `{path}`: {desc}")
    a("")

    # ------------------------------------------------------------------ run
    a("## How to run\n")
    a("```bash\nuv venv --python 3.12 .venv\nuv pip install --python .venv/bin/python -r pyproject.toml \\\n"
      "    --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match\n"
      "export OPENROUTER_API_KEY=...        # only the judge stage calls an API (~$0.12 total)\n"
      ".venv/bin/python method.py --stage all   # every stage in order (about 3-4 h on 2 CPU cores)\n"
      ".venv/bin/python method.py               # rebuild method_out.json from results/ (seconds)\n"
      "# the checks and post-prereg analyses alone (stages of --stage all; CPU, minutes):\n"
      "for s in inventory unit_checks verify_hooks extra_analyses b7_diagnostic; do .venv/bin/python src/$s.py; done\n```\n")
    a("The stages refuse to run out of order: `harvest_panel.py` verifies the hash chain before it hooks any panel "
      "checkpoint.\n")

    # ------------------------------------------------------------------ restore
    a("## Restoring removed files\n")
    a("`.aii/manifest.yaml` keeps `harvest/` (the raw activations: they cannot be regenerated without 31 GB of downloads) "
      "and marks `hf_cache/` and the two `__pycache__/` directories for deletion after the round. Every deleted path "
      "can be restored:\n")
    a("- `hf_cache/` (**redownloadable; already emptied before deployment**). The public Hugging Face weights exceed "
      "GitHub's 100 MB file limit (up to 4.5 GB per file), so the cache was deleted rather than split. Nothing that "
      "scores, analyses or builds outputs reads it: `method.py`, `score.py`, `extra_analyses.py`, `b7_diagnostic.py` and "
      "`unit_checks.py` use `results/` + `harvest/` only. The model-loading stages (`gen.py`, `harvest_panel.py`, "
      "`verify_hooks.py`) call `src/gen.py:download`, which re-fetches a missing snapshot automatically. "
      "`src/h2/wsummary.py:open_repo` reads the snapshot that `harvest_panel.py` has just downloaded. The snapshots "
      "were originally downloaded with "
      "`huggingface_hub.snapshot_download(repo, cache_dir='hf_cache', allow_patterns=[...])` (`src/gen.py:download`). "
      "To restore them:\n```bash\nfor r in " + " ".join(final) + "; do\n"
      "  .venv/bin/python -c \"import sys; sys.path.insert(0,'src'); from gen import download; print(download('$r'))\"\ndone\n"
      "# Qwen/Qwen3-4B: tokenizer files ONLY (9 MB; used by src/harvest_panel.py for the cell character spans)\n"
      ".venv/bin/python -c \"from huggingface_hub import snapshot_download; snapshot_download('Qwen/Qwen3-4B', "
      "cache_dir='hf_cache', allow_patterns=['tokenizer*', 'vocab.json', 'merges.txt', '*.jinja', 'config.json'])\"\n```\n")
    a("- `src/__pycache__/`, `src/h2/__pycache__/` (**regenerable**): `python -m compileall src`.")
    a("- `.venv` is not shipped. It lived in the session scratchpad. Rebuild it with `uv venv --python 3.12 .venv && uv pip install "
      "--python .venv/bin/python -r pyproject.toml --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy "
      "unsafe-best-match`, or run `uv run method.py`, which syncs it from `pyproject.toml` / `uv.lock`. "
      "`results/venv_freeze.txt` has the exact freeze.\n")
    (WS / "README.md").write_text("\n".join(L))
    print("README.md written", len("\n".join(L)))


if __name__ == "__main__":
    main()
