"""STEP 0 inventory (plan): what every input file holds and how each dependency is used. Read-only; writes
results/inventory.json. Numbers are counted from the files, never typed."""
from __future__ import annotations

import collections
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ASSETS, D1, D2, H2, LANEC, RESULTS, RUN, jdump, jload, sha256_file, utc_now  # noqa: E402

RESEARCH = RUN / "iter_2/gen_art/gen_art_research_1"


def _grep_count(pattern: str, root: Path) -> int:
    r = subprocess.run(["grep", "-rIicE", pattern, str(root)], capture_output=True, text=True)
    return sum(int(x.rsplit(":", 1)[1]) for x in r.stdout.splitlines() if x.rsplit(":", 1)[-1].isdigit())


def main() -> None:
    out: dict = {"utc": utc_now()}
    gh, gb = jload(LANEC / "assets/gt_harm.json"), jload(LANEC / "assets/gt_benign.json")
    r54 = jload(LANEC / "assets/reserved_54.json")
    out["laneC_items"] = {"gt_harm": len(gh), "gt_benign": len(gb),
                          "gt_harm_categories": dict(collections.Counter(x.get("category") for x in gh)),
                          "gt_benign_categories": dict(collections.Counter(x.get("category") for x in gb))}
    out["reserved_54"] = {"n_scenarios": len(r54), "prompts": 2 * len(r54), "structure": "one XSTest twin scenario per row "
                          "(harmful_request + benign_request)", "families": dict(collections.Counter(x.get("family") for x in r54)),
                          "opened_for": "Vikhrmodels/Vikhr-Llama-3.2-1B-Instruct only (deviation items_cut_to_laneC90)"}
    bi = jload(ASSETS / "behaviour_items.json")
    out["behaviour_items_asset"] = {k: bi[k] for k in ("n_items", "n_harm", "n_benign", "n_laneC", "n_r54")}
    stim = jload(H2 / "assets/stimuli.json")["rows"]
    out["harvest_stimuli_256"] = {
        "n": len(stim),
        "by_set_label_source": {f"set{s}_y{y}_{src}": n for (s, y, src), n in
                                sorted(collections.Counter((x["set_id"], x["y"], x.get("source", "")) for x in stim).items())},
        "roles": "set 0 = EASY (fits axes), set 1 = HARD (scores them)"}
    cells = jload(H2 / "assets/cells.json")["cells"]
    out["teacher_forced_cells"] = {"n": len(cells), "by_request_x_continuation": dict(collections.Counter(
        f"{c['request_level']}|{c['prefix_level']}" for c in cells)), "n_scenarios": len({c["item_uid"] for c in cells})}
    ts = jload(H2 / "assets/token_sets.json")
    ts = {k: v for k, v in ts.items() if k in ("refusal", "hedge", "control")} if "refusal" in ts else ts.get("sets", ts)
    out["token_sets"] = {k: len(v) for k, v in ts.items()}
    c11 = jload(ASSETS / "c11_items.json")
    out["c11_items"] = {"n": c11["n"], "n_from_D2": c11["n_from_D2"], "n_drawn": c11["n_drawn"],
                        "severity_counts": c11["severity_counts"], "draw_rule": c11["draw_rule"]}
    lc = (LANEC / "lc_common.py").read_text()
    gen_src = (Path(__file__).resolve().parent / "gen.py").read_text()
    out["judges"] = {"primary": re.search(r'PRIMARY_JUDGE\s*=\s*"([^"]+)"', lc).group(1),
                     "audit": re.search(r'SECOND_JUDGE\s*=\s*"([^"]+)"', lc).group(1),
                     "secondary": "H2 judge_ext.py plain-rubric variant (same primary model)",
                     "stance_framed_variant_in_H2_src": {"grep_i_word_stance_hits": _grep_count(r"\bstance", H2 / "src"),
                                                         "note": "word-boundary match; substrings such as assi-stance / sub-stance / in-stance excluded"},
                     "lc_judge_py_sha256": sha256_file(LANEC / "lc_judge.py")}
    m = re.search(r"MAX_NEW\w*\s*=\s*(\d+)", gen_src)
    out["generation"] = {"decoding": "greedy (do_sample=False)", "max_new_tokens": int(m.group(1)) if m else None,
                         "template_rule": "tokenizer chat template (enable_thinking=False where supported); plain "
                                          "request + newline when no template (Lane C lc_harvest fallback)",
                         "timings": "results/gen_timings.json"}
    reg = jload(D1 / "model_registry.json") if (D1 / "model_registry.json").exists() else None
    out["dependencies"] = {
        "D1 iter_1/gen_art/gen_art_dataset_1 (frozen stimulus substrate + source corpora)": {
            "used": "source of the XSTest / OR-Bench / AdvBench / Dolly prompts behind H2's 256 stimuli and 96 cells; "
                    "model_registry.json repos enter the exclusion list; rubric.md hashed; heldout_cells.json NOT opened",
            "model_registry_repos": (sum(len(v) for k, v in reg.items() if k in ("core_arms", "nonsafety_ladder", "family_panel"))
                                     if isinstance(reg, dict) else len(reg)) if reg else None,
            "rubric_md_sha256": sha256_file(D1 / "rubric.md") if (D1 / "rubric.md").exists() else None,
            "full_data_out_sha256": sha256_file(D1 / "full_data_out.json")},
        "D2 iter_2/gen_art/gen_art_dataset_1 (model pairs, hard prompts, refusal tokens)": {
            "used": "paired_lineage_registry FRESH held-out pair (Vikhr-Llama-3.2-1B-Instruct + abliterated) enters the panel "
                    "first; hard_recognition_set rows with graded_harm feed C11; refusal/hedge/control token sets (via H2 "
                    "assets/token_sets.json) feed BL1 and the logit-lens drives; rubric SHA-256s recorded in graded truth",
            "full_data_out_sha256": sha256_file(D2 / "full_data_out.json")},
        "R iter_2/gen_art/gen_art_research_1 (which safety readouts are still unclaimed)": {
            "used": "prior-art status of the bars: X2/X10 (weights-only write mass / orthogonality scar) are CLOSED by the "
                    "Jorak Model Scanner, so B7/X10_abs are reported as prior-art readouts, not as novel metrics; "
                    "abliterated checkpoints are the one empty cell in 2606.24952 / 2603.05773, which motivates the "
                    "paired abliteration contrasts",
            "research_out_sha256": sha256_file(RESEARCH / "research_out.json")},
        "H2 iter_2/gen_art/gen_art_experiment_1 (iteration-2 Lane A harvest + incumbents)": {
            "used": "harvest kernels copied verbatim (src/h2/, sha256 in results/provenance.json); stimuli, cells, token "
                    "sets; scored_checkpoints.json = exclusion list + incumbent reproduction target; saved harvest arrays "
                    "re-scored read-only (results/iter2_panel_same_code.json)"},
        "LANEC iter_1/gen_art/gen_art_experiment_3 (behavioural lane)": {
            "used": "the 90 behaviour items, the reserved-54 split, the lc_judge.py protocol and judged rows (reproduction check)"}}
    jdump(out, RESULTS / "inventory.json")
    print("inventory written:", {k: (v if not isinstance(v, dict) else len(v)) for k, v in out.items()})


if __name__ == "__main__":
    main()
