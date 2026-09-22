#!/usr/bin/env python3
"""Write README.md and .aii/manifest.yaml from the finished build, so the numbers in
the prose are read off the shipped files rather than retyped.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def du(p: Path) -> str:
    try:
        out = subprocess.run(["du", "-sh", str(p)], capture_output=True, text=True, timeout=120)
        return out.stdout.split()[0]
    except Exception:
        return "?"


def main() -> None:
    data = json.loads((ROOT / "full_data_out.json").read_text())
    gates = json.loads((ROOT / "gates.json").read_text())
    meta = data["metadata"]
    counts = meta["row_counts_by_table"]
    summ = gates["summary"]

    failed = gates["summary"]["failed_gates"]
    fail_lines = "\n".join(
        f"- **{f['gate_id']} FAILED** — threshold `{f['threshold']}`, observed `{f['observed']}`"
        for f in failed) or "- none"

    gate_table = ["| gate | threshold | observed | status |", "|---|---|---|---|"]
    for g in gates["gates"]:
        obs = g["observed"]
        if isinstance(obs, (dict, list)):
            obs = json.dumps(obs)
        if isinstance(obs, str) and len(obs) > 90:
            obs = obs[:87] + "..."
        gate_table.append(f"| `{g['gate_id']}` | {g['threshold']} | {obs} | **{g['status']}** |")

    count_lines = "\n".join(f"| `{k}` | {v} |" for k, v in counts.items())

    readme = f"""# Iteration-2 dataset substrate — model pairs, hard prompts, refusal tokens

Twelve frozen artefacts for the iteration-2 execution screen of run `run_YqmEFECOIR3D`
(*cheap activation-level safety metric for Qwen3-4B and friends*). Everything here is
**metadata, tokenizers and text**. No model weights were downloaded, no forward pass was
run, no activations were read, and no deliverable metric was computed — those belong to
the experiment lanes.

**Prereg SHA-256: `{meta['prereg_sha256']}`**
(recomputed from `prereg.json` on disk at assembly time: `{meta['prereg_sha256_recomputed_from_disk']}` — gate `G_PREREG_HASH`)

## Gates — {summ['n_pass']} PASS / {summ['n_fail']} FAIL / {summ['n_not_applicable']} N/A

Every failed gate is named here with its number, in the artifact's own summary:

{fail_lines}

{chr(10).join(gate_table)}

## What is shipped

| set | rows |
|---|---|
{count_lines}

Side files: `prereg.json` + `prereg.sha256` (the Phase-A freeze), `prereg_addendum.json`
(binds the sealed-truth hash to the frozen prereg), `sealed_truth.json` +
`sealed_truth.sha256`, `gates.json`, `build_log.txt` (timestamped, append-only, proving
the freeze preceded every label and split).

## Layout

```
prereg.json / prereg.sha256      PHASE A freeze: thresholds, split rules, gate list
prereg_addendum.json             sealed_truth hash, bound to the prereg it extends
full_data_out.json               the ten in-file sets (exp_sel_data_out schema)
full_/mini_/preview_data_out.json  size variants
gates.json                       every gate with its observed number and status
sealed_truth.json                the two sealed families' true deltas (DISCLOSED_UPSTREAM)
build_log.txt                    append-only ordering proof
assets/rubric_iter1.md           iteration-1 grading rubric, verbatim
assets/lc_judge_iter1.py         iteration-1 judge script, verbatim
src/                             every build step, in dependency order
build/                           intermediate JSON each step hands to the next
temp/datasets/                   the downloaded public corpora
logs/                            loguru run logs
```

## How to run

```bash
./install.sh     # uv venv + deps
./rebuild.sh     # every phase in dependency order
```

`src/phase_a_prereg.py` **refuses to overwrite an existing `prereg.json`**. The freeze is
deliberately not re-runnable: a changed rule means a new file with a new hash and a logged
reason.

## Things a reader should know before using this

1. **Precision.** Every behavioural rate rests on n=45 harm / 45 benign judged items
   (60/60 for `Qwen__Qwen3-0.6B-Base`, 45/44 for `microsoft__Phi-4-mini-instruct`). A
   point estimate of 0.156 carries a Wilson 95% interval of roughly [0.08, 0.29], and the
   +0.15 effectiveness threshold is of the same order as that interval width. Every pair
   therefore ships `delta_ci95` (Newcombe) and `label_robust`; a pair whose interval
   straddles its deciding threshold is relabelled `AMBIGUOUS` whatever the point estimate
   says. This artifact cannot enlarge n — that needs new generations and a GPU.
2. **The seal is already compromised.** The iteration-2 strategy text prints both sealed
   pairs' judged deltas. `seal_status` is `DISCLOSED_UPSTREAM` for them. The only
   genuinely blind confirmation material is the seeded-hash FRESH held-out pairs and the
   never-loaded 54-scenario XSTest split.
3. **Readout class.** Every row carries `readout_class`. The registry and the raw card
   text are `metadata`/`text` and are therefore **baseline** material by construction. The
   run's deliverable metric must read activations or weights; nothing here may be promoted
   into that role by a later table.
4. **Denominator convention.** One of the 2,370 iteration-1 judged rows (Phi-4-mini benign
   `orh_244`) has an unparsable primary judge output. Iteration 1's published columns drop
   it from the denominator; this rebuild adopts the same convention, which is why
   `G_JOIN_CONSISTENCY` reads exactly 0 and not 1.46e-2. `build_log.txt` records both runs.
5. **Hardness is measured, not claimed.** The TF-IDF text proxy is reported on the easy
   anchors and on the hard subset, with the top-20 leaking features. It is a *textual*
   proxy; the activation-level headroom check is the experiment lanes' job.
6. **No iteration-1 refusal lexicon exists.** A targeted grep across `gen_art_dataset_1`
   and all three iteration-1 experiment lanes found none. The token sets are built from
   nothing, and a constructed naive comparator ships alongside them so the screen can
   quantify what mining adds over the obvious guess.

## Restoring removed files

Only two paths are marked for deletion in `.aii/manifest.yaml`, and both come straight
back:

| deleted path | how to restore |
|---|---|
| `.venv/` (2.4 GB, redownloadable) | `./install.sh` |
| `**/__pycache__/` (regenerable) | nothing to run — Python rewrites it on the next `./rebuild.sh` |

Everything else is kept: `build/` (9.7 MB of intermediate JSON each phase hands to the
next) and `temp/datasets/` (144 MB of corpus snapshots) are what the frozen row ids point
at, and re-downloading them later could pick up a changed upstream revision.

`temp/datasets/` is nevertheless EXCLUDED FROM THE PUBLIC REPOSITORY via
`upload_ignore_regexes`: these are third-party corpora and four of the downloaded files
(BeaverTails, FalseReject train, FalseReject test, PKU-SafeRLHF) are CC-BY-NC, so this
artifact should not redistribute them. `build/sources_manifest.json`
records the repo id, config, split, revision, license and byte count of every one, so any
reader can re-fetch them:

```bash
.venv/bin/python src/download_sources.py        # HuggingFace corpora
.venv/bin/python src/download_github_sources.py # XSTest and AdvBench CSVs
```

Per-row `metadata_license` is carried throughout so downstream release decisions stay
auditable.
"""
    (ROOT / "README.md").write_text(readme)
    (ROOT / "README_SKELETON.md").unlink(missing_ok=True)

    # Only large binaries and cache directories need a decision. Everything else
    # here is JSON, CSV, Markdown or Python and sits under the auto-keep floor, so
    # build/ and temp/datasets/ are deliberately NOT listed.
    manifest = """entries:
  - path: .venv/
    delete: redownloadable
    source: "./install.sh"
  - path: "**/__pycache__/"
    delete: regenerable
    source: "regenerated automatically on the next run of ./rebuild.sh"
"""
    (ROOT / ".aii").mkdir(exist_ok=True)
    (ROOT / ".aii" / "manifest.yaml").write_text(manifest)
    print("README.md and .aii/manifest.yaml written")


if __name__ == "__main__":
    main()
