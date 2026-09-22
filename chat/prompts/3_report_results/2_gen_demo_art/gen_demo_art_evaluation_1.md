# gen_demo_art_evaluation_1 — report_results

> Phase: `gen_paper_repo` · `gen_demo_art`
> Run: `run_YqmEFECOIR3D` — Specificity and Causality Audits for Activation-Based Safety Readouts
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_demo_art_evaluation_1` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-22 07:54:27 UTC

````


<pasted_content id="7d95">
<system-prompt>
<conversion_philosophy>
**MINIMAL CHANGES — PRESERVE THE ORIGINAL CODE**

The goal is to make the artifact's code READABLE, UNDERSTANDABLE, and RUNNABLE in a short time
to someone reviewing the research, with the option to easily scale parameters back to original
values for a full run (which can take much longer). Think of this as annotating and reformatting,
not refactoring.

**DO:**
- Split the original script into logical notebook cells (imports, setup, processing, results)
- Add markdown cells BETWEEN code cells explaining what each section does and why
- Add inline comments where the logic is non-obvious
- Add a visualization/summary cell at the end showing key outputs
- Fix hardcoded file paths to use the GitHub data loading pattern

**DO NOT:**
- Rewrite functions or change algorithms
- Rename variables or restructure logic
- Add error handling, type hints, or "improvements" that weren't in the original
- Simplify or "clean up" the original code
- Remove any original comments or logic
- Change the computational approach

The reader should recognize the original script when looking at the notebook — it's the
same code, just split into cells with explanatory markdown between sections.
</conversion_philosophy>

<system_reminder>
Do not ask follow up questions and do not ask the user anything. Execute all steps independently.
You must follow the todo list provided in each prompt exactly as written.
No placeholders, stubs, or incomplete code — all code must be complete and functional.
</system_reminder>

<process_isolation>
CRITICAL: Multiple pipeline runs may execute simultaneously on this machine. `ps aux | grep method.py` matches ALL runs, not just yours.
- NEVER kill processes by name (`killall`, `pkill -f`, `ps aux | grep ... | xargs kill`). This kills OTHER runs' processes.
- NEVER monitor processes by name (`ps aux | grep method.py`). You will see other runs' processes and get confused.
- ALWAYS use PID-based process management:
  Run: `uv run method.py & PID=$!` or `timeout <seconds> uv run method.py & PID=$!`
  Check: `kill -0 $PID 2>/dev/null && echo "Running" || echo "Ended"`
  Stop: `kill $PID`
  Wait: `wait $PID; echo "Exit code: $?"`
  Monitor: `tail -f logs/run.log & TAIL_PID=$!` then `kill $TAIL_PID` when done
</process_isolation>

<subagent-delegation>
Your own tokens are the scarcest and most expensive resource in this run. Your job is to decompose the work, delegate it, coordinate, decide, verify briefly, and synthesize. It is not to work through the pieces yourself.

Delegate by default (e.g. with the Task tool): anything beyond a trivial step goes to a subagent, even when it is one sequential task with nothing to split. Running a script, debugging a failure, reading a long output or log, searching the repo or the literature, drafting text: all of it is subagent work, and so is a loop of write code, run it, read the output, fix, rerun. The reason is context isolation, not only parallelism. Every stdout dump, traceback and dead end a subagent absorbs is one that never enters your context; only its conclusion comes back. Keep a step for yourself only when one obvious search-free action beats the handoff, such as a one-line edit or a single lookup.

- Pick the cheapest tier that can do the job:
- Pass `subagent_type="aii-easy"` (steered toward `claude-sonnet-5`) for a small/fast tier for mechanical work.
- Pass `subagent_type="aii-medium"` (steered toward `claude-sonnet-5`) for a mid tier for implementation or investigation (the default).
- Pass `subagent_type="aii-hard"` (steered toward `claude-opus-5`) for the strongest tier only for hard reasoning or after a cheaper model has already failed on the same task.
- Raise the tier only after a cheaper one has failed with evidence; never start at the top.
- Split orthogonal pieces by file or artifact ownership up front, one subagent per piece, and serialize only where one result feeds the next.
- Run genuinely independent pieces of work in parallel, at most 3 concurrently.
- Keep handoffs short: objective, exact scope, constraints, acceptance check, output format. Ask for findings back as text.
- Subagents report only the result, changed files, verification, and blockers, never narration or full logs.
- What stays with you: the decisions, a short sanity check on what came back (one bash command, one file read), and the integration. Do not redo a subagent's work.
- Never fork yourself, and never let a subagent spawn its own subagents.
</subagent-delegation>

<workspace>
Your workspace: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_2/art_G5pqEoRFZ75t`

CRITICAL: Every file you create, write, or save MUST be inside this workspace directory (subdirectories OK). You MUST NOT write files anywhere outside this path — external paths are READ-ONLY. Use absolute paths for all file operations.

EVERY file write MUST start with `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_2/art_G5pqEoRFZ75t/`:
GOOD: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_2/art_G5pqEoRFZ75t/file.py`, `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_2/art_G5pqEoRFZ75t/results/out.json`
BAD: `/tmp/file.py`, `~/output.json`, `./file.py`, any path outside the workspace
</workspace>
<disposable_outputs>
A SHARED CACHE ALREADY EXISTS FOR THIS RUN: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/.shared_cache`
`HF_HOME`, `HF_HUB_CACHE`, `TRANSFORMERS_CACHE`, `HF_DATASETS_CACHE`,
`TORCH_HOME`, `PIP_CACHE_DIR` and `UV_CACHE_DIR` are ALREADY set to point
there. Every step and every iteration of this run shares it, so a model or
dataset an earlier experiment downloaded is already on disk for you.

DO NOT override those variables. In particular do NOT write the common
pattern `os.environ["HF_HOME"] = <workspace>/hf_cache` — `HF_HOME` and
`TRANSFORMERS_CACHE` are read differently by `huggingface_hub` (one has
`/hub` appended, the other does not), so pointing both at one directory
stores every weight TWICE. That mistake cost one run 25 GB of identical
blobs. If you must set them, use the values above verbatim.

YOUR WORKING DIRECTORY IS A DELIVERABLE. When this module ends it must read
like a GitHub repository someone else can fork, resume and run — and the bulk
it holds must be either worth keeping or restorable. This run shares a storage
volume with the database; a run that fills it stops every other run on the box.

So before you finish, produce TWO files:

1. `.aii/manifest.yaml` — one entry per heavy path, each with EXACTLY ONE decision:

```yaml
entries:
  - path: results/
    keep: six GPU-hours of sweep output, not reproducible inside this run
  - path: hf_cache/
    delete: redownloadable
    source: "huggingface-cli download meta-llama/Llama-3-8B"
  - path: checkpoints/
    delete: regenerable
    source: "uv run train.py --epochs 3 --seed 0"
```

   - `keep:` takes a ONE-LINE reason. Use it for the expensive and the
     irreproducible: trained weights, long-running results, datasets you
     collected yourself.
   - `delete:` takes `redownloadable` (and a `source:` naming the repo id, URL
     or command) or `regenerable` (and a `source:` that is the command which
     rebuilds it). These are deleted AFTER the round ends, never mid-step.
   - Every path is RELATIVE TO YOUR CWD and must resolve INSIDE it. Absolute
     paths, `..`, and anything resolving outside are rejected.
   - Globs and whole directories are fine. A whole `hf_cache/` is ONE entry —
     do not list files individually.

2. `README.md` — written as if your cwd were a GitHub repository: what you
   did, the layout with a line per important file/directory, how to run it,
   and a **"Restoring removed files"** section giving the install/download
   command for EVERY `delete` entry. An `install.sh` or `restore.sh` beside it
   is welcome.

A CHECKER RUNS WHEN YOU SUBMIT. If anything heavy has no decision it fails
your submission and hands you the uncovered list, grouped by directory with
sizes, and you fix the manifest and submit again.

WHAT NEEDS NO DECISION — do not write entries for these:
- text and code files, at ANY size (source, JSON, CSV, YAML, logs, markdown);
- anything under the auto-keep floor (10 MB), whatever it holds.
Only large binaries and cache directories (`hf_cache/`, `.venv/`,
`node_modules/`, `checkpoints/`, `wandb/`, `__pycache__/`, …) need one.

NEVER mark your results, figures, papers, code, logs or anything a later step
reads as `delete`. If a later step needs it, it is a `keep`.
</disposable_outputs>
</system-prompt>

<prompt>
<tool_use>
Maximize parallel tool calls. Parallelize independent operations, only sequentialize dependencies.
- Multiple searches/fetches on different topics → parallel in one turn
- Search then fetch results → sequential (need URLs first)
</tool_use>

<task>
Convert this artifact's Python script into a demo notebook with MINIMAL changes to the original code.
Split into cells, add markdown explanations between sections, add a visualization cell at the end.
Output: mini_demo_data.json + code_demo.ipynb (notebook that loads data from GitHub URL)
</task>

<artifact_info>
id: art_G5pqEoRFZ75t
type: evaluation
title: Re-checking the numbers we already have
summary: |-
  ZERO-GPU, ZERO-API RE-ADJUDICATION of iteration 1's three lanes (M0-M8), computed only from files already on disk. Pre-registration frozen and hashed BEFORE the first number: SHA-256 7f6a38d94007c3a7d07b40cadfc79863cdd504f1115e2cf47e12511c4d77966b. Self-check PASS (12 tables, 0 rejected), 0 stage failures, CLAIM MATCH RATE 0.8229 (79/96 numbers), 5 contradictions, 19 corrections.

  M0 KILLS THE INHERITED CLAIM THAT GATED EVERYTHING. 'Raw hidden states were saved nowhere' is FALSE: LANE_B/out/harvest holds 104 npz (NOT the claimed 109), containing 4200 arrays of shape (1152, 2560) float16 keyed `item|win|{EARLY,LATE}|{13..22}`, for 4 lineages x 5 lesion strengths. M1 therefore got its STRONG form (probe fitted on alpha=0.00, scored on alpha>0) at zero GPU cost. Stored curves reproduce: D_curve EXACT_MATCH at 1.000 for L1-L3, D_matched_probe_curve RECONCILED within 0.005-0.015. Read site is per-lineage (lastp 29/22/23/29), not constant.

  HEADLINE (M1) - A SITE DISSOCIATION AUROC CANNOT SHOW. The 1.000 belongs to the crude `damage` corpus and is AT ITS CEILING in the unperturbed control, so it could not fall. Re-expressed as TPR@1%FPR on the SAME activations (alpha 0 -> 1, mean over 4 lineages): EARLY/prompt site dAUROC -0.0068, dTPR@1%FPR +0.0007 (FLAT - the harmful REQUEST is still recognised); LATE/response site dAUROC -0.0137, dTPR@1%FPR -0.1439, a 10.5x larger movement in the operating point than in AUROC. So 'the representation survives the lesion' is TRUE at the prompt site and FALSE at the response site - recognition-vs-execution made measurable. Equivalence (TOST, margin 0.05 TPR units, both windows, Holm on the primary window): EQUIVALENT at alpha<=0.50, NOT_EQUIVALENT at 0.75-1.00. Lineage pairs: base->instruct +0.245 NOT_EQUIVALENT, instruct->SafeRL +0.063 NOT_EQUIVALENT, base->NON-safety-FT +0.029 INCONCLUSIVE (the load-bearing control behaves).

  THE COMMISSIONED FEW-PROMPT AXIS WORKS. Restricted-budget AUROC at k=16 (unlesioned): Base 0.528 ~ NonSafetyFT-STaR 0.540 << Instruct 0.679 < SafeRL 0.698. Tracks SAFETY tuning, not fine-tuning as such, from 16 labelled items.

  M6 SPECIFICITY FAILURE. All 19 quoted judged behavioural numbers recomputed MATCH. But K1/A moves 4.14 null-SD on the granite pair, a behavioural NO-OP (d harmful-compliance 0.000) whose child only carries 'abliterated' in its repo name: scored on the label it looks right, scored on the MEASURED delta it is caught. T1 is INCONCLUSIVE_UNDERPOWERED (n=5, achieved margin 28.4 null-SD), T2 rho -0.103 against a min-resolvable |rho| 0.878, T4 SATISFIED. UNIT MISMATCH DISCLOSED: the prereg margin is in TPR units (M1) while M6's outcome is in null-SD, so no cross-scale equivalence verdict is licensed or claimed.

  REPAIRS. M2: 9 of 20 scaled outcomes SATURATED, plus 8 INDETERMINATE_NO_MATCHED_POINT rows lifted out of the limitations. M3: three protocols, not one - A at-band 0.0433-0.2346 (NOT the quoted '0.04-0.09'), Lane B 0.139-0.186, Lane C 0.057-0.603 over 7 families; HARC contradiction WITHDRAWN (a cross-concept pair REPLICATES HARC); the 1596-row rotation matrix shows instruction tuning rotates the request axis MORE (|cos| 0.200) than abliteration (0.361), content axis 0.90-0.99 across trained pairs, RandInit null 0.009-0.020. M4: 112 gate rows, compliance A 0.44 / B 1.00 / C 0.69; three lanes fit three different axes under one name and reach OPPOSITE stability verdicts; K3 re-scored FAIL under its own rule -> no candidate passes S1. M5: all 6 k rungs, k=0 explicit as NOT_RUN_BY_LANE_C (never imputed); the 0.882 scan located, MATCHED, non-monotonic. M7: 70 rows, attenuation ceilings, regex-vs-judge recomputed, B7 below the random floor. M8: substrate provenance (TOTAL_L=80, slots 8/46, NOT 144), dataset gates located in gen_art_dataset_1 (hazard 0.9429 vs 0.95; 96->85; placebo median ratio 1.25 vs 1.10), causal arm EMPTY (1 of 8 jobs), shuffled band 11.04-11.78 trained vs 1.268 RandInit with A escaping 0/7.

  RUN INVARIANT ENFORCED AS A COLUMN. Every row of all 12 tables carries READOUT_CLASS; 2039 rows are result-eligible (activation/weight), 309 are BASELINE_ONLY (logit/text/metadata). evalkit/selfcheck.py REJECTS a table missing the column, and prose naming a baseline-class readout as the answer. Nothing is framed as jailbreak or attack-success reporting.

  HANDOFF to the experiment lanes: (1) generated text from the lesioned models - needs a RE-RUN; (2) operating-point statistics for the 21-checkpoint panel - Lane C stored only AUROC scalars; (3) a scored mlabonne/Qwen3-4B-abliterated row, present in every Lane A table but absent from Lane C's panel and Lane B's harvest.

  ARTEFACTS: eval.py + evalkit/ (paths, prereg, stats, selfcheck, laneb_substrate, m0-m8); EVAL_REPORT.md opening with CONTRADICTIONS then the claim match rate; eval_out.json (exp_eval_sol_out, 23 metrics_agg, 12 datasets) + full/mini/preview; 12 CSVs and 8 JSONs under results/, EVERY ROW CARRYING ITS SOURCE FILE PATH.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_evaluation_1
out_expected_files:
- eval.py
- full_eval_out.json
- mini_eval_out.json
- preview_eval_out.json
out_demo_files:
- path: eval.py
  description: Evaluation script with metrics computation
</artifact_info>

<github_repo>
Repo URL: https://github.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned
Raw data URL: https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-2/evaluation-1/demo/mini_demo_data.json

URLs won't work yet — files pushed to GitHub AFTER notebook creation.
Use local fallback pattern so notebook works locally (now) and in Colab (after deployment).
</github_repo>

<data_file_sizes>
Data files come in three sizes:
- preview_*_out.json — READ THIS to inspect the data structure
- mini_*_out.json (~3 examples) — use for prototyping/testing
- full_*_out.json (complete) — use for the final production run. NEVER open it directly (too large to read into context). Instead, extract values programmatically with shell commands (e.g. grep) or a Python script (use aii-long-running-tasks skill for scripts).
</data_file_sizes>

<install_dependencies_pattern>
Follow the aii-colab skill exactly. It has the install cell pattern, pre-installed package list, numpy 2.0 compat shims, and all Colab-specific rules.
</install_dependencies_pattern>

<data_loading_pattern>
`mini_demo_data.json` = curated subset for the demo.
Use this pattern for Colab compatibility (GitHub URL with local fallback):
```python
GITHUB_DATA_URL = "https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-2/evaluation-1/demo/mini_demo_data.json"
import json
from pathlib import Path

def load_data():
    try:
        import urllib.request
        with urllib.request.urlopen(GITHUB_DATA_URL) as response:
            return json.loads(response.read().decode())
    except Exception: pass
    local = Path("mini_demo_data.json")
    if local.exists(): return json.loads(local.read_text())
    raise FileNotFoundError("Could not load mini_demo_data.json")
```
</data_loading_pattern>

<notebook_structure>
--- Setup ---
Cell 1 (markdown): Title, description, what this artifact does.
Cell 2 (code): Install dependencies — follow the aii-colab skill's install cell pattern exactly. Fill in all packages imported by the artifact's code.
Cell 3 (code): Imports — copy original import block as-is, plus any additional imports needed for the notebook (e.g. matplotlib for visualization).
Cell 4 (code): Data loading helper — use the <data_loading_pattern> above.
Cell 5 (code): `data = load_data()`

--- Config ---
Config cell (code): Define ALL tunable parameters (iterations, epochs, n_samples, hidden_size, etc.) as variables at the top of this cell. Start with the ABSOLUTE MINIMUM values — the smallest that produce any output at all (e.g. 1 iteration, 2 samples, smallest array size). These get gradually increased during testing — see TODOs.

--- Processing ---
Remaining cells: One code cell per logical section of the original script. Add a markdown cell BEFORE each code cell. Copy code as closely as possible, with these changes:
  1. Replace file paths to use the loaded `data` variable.
  2. Use the config variables from the config cell (NOT hardcoded values).
  3. Minimal fixes are allowed if something doesn't work in notebook context (e.g. adjusting paths, removing CLI args, fixing imports), but keep changes to the absolute minimum.

--- Results ---
Visualization cell (code): Print key results in a readable table, plot numeric data with matplotlib if appropriate.
</notebook_structure>

<priority>
WORKING > OPTIMIZED. A small-scale demo that runs correctly is the goal. Once the notebook passes with minimum config values, scale up only if time permits — do NOT spend multiple retries chasing larger parameters. If a working version exists, finish and move on.
</priority>

<max_notebook_total_runtime>600s (10 min)</max_notebook_total_runtime>

<test_environment>
To test-run the notebook in a clean environment (simulating Colab), create a disposable `.nb_env` in your workspace:
```bash
/usr/local/bin/python3.12 -m venv .nb_env
.nb_env/bin/pip install -q pip jupyter ipykernel
.nb_env/bin/jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 code_demo.ipynb --output code_demo.ipynb
rm -rf .nb_env
```
The timeout is set to <max_notebook_total_runtime>. The entire notebook must finish within this time.

What happens: the .venv starts empty (just jupyter). When the notebook's install cell runs, `google.colab` is NOT in sys.modules, so ALL packages get installed — non-Colab packages unconditionally, and Colab packages (numpy, pandas, etc.) at Colab's exact versions via the guard block. The result mirrors Colab's environment as closely as possible. If a cell fails, fix the notebook and re-run.
</test_environment>

FIRST, add ALL of these to your todo list using your task/todo-tracking tool:

CRITICAL: Todo content must be copied exactly as is written here, with NO CHANGES. These todos are intentionally detailed so that another LLM could read each one without any external context and understand exactly what it has to do.


<todos>
TODO 1. Read and STRICTLY follow these skills: aii-colab, aii-long-running-tasks.
TODO 2. Read demo file and relevant preview_* files (preview only). Understand script structure: imports, setup, processing, output. Identify ALL tunable parameters (iterations, epochs, n_samples, hidden_size, batch_size, etc.) — these go in the config cell.
TODO 3. Create `mini_demo_data.json`: curated subset from at most ONE dataset (no more than 100 diverse examples). CRITICAL: do NOT read/grep full output file — may crash. Use `head -c 5000` or stream first entries with Python to pick examples.
TODO 4. Create `code_demo.ipynb` via NotebookEdit following <notebook_structure>. Set ALL config parameters to ABSOLUTE MINIMUM values — the smallest that produce any output (e.g. 1 iteration, 2 samples, smallest array sizes). Test-run using <test_environment>. Fix all errors until it passes.
TODO 5. GRADUALLY SCALE (but don't overdo it): increase config params step by step (e.g. ~2x each round). After each increase: test-run, record runtime, fix errors. STOP SCALING as soon as results look meaningful — a working small-scale demo beats a failed large-scale one. If full original params fit within <max_notebook_total_runtime> (10% margin), use them. Otherwise keep whatever works and comment out the true original values. Do NOT spend more than 2-3 scaling rounds.
TODO 6. Verify: (1) code_demo.ipynb contains GITHUB_DATA_URL = "https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-2/evaluation-1/demo/mini_demo_data.json" exactly, (2) mini_demo_data.json exists, (3) uses GitHub URL pattern not just open('mini_demo_data.json').
</todos>

---

Output the result as JSON to: `./.terminal_claude_agent_struct_out.json`

JSON Schema:
```json
{
  "$defs": {
    "DemoExpectedFiles": {
      "description": "Expected output files from code demo notebook generation.",
      "properties": {
        "notebook": {
          "default": "",
          "description": "Path to the generated demo notebook. Example: 'code_demo.ipynb'",
          "title": "Notebook",
          "type": "string"
        },
        "mini_data_file": {
          "default": "",
          "description": "Path to the mini demo data JSON (curated subset). Example: 'mini_demo_data.json'",
          "title": "Mini Data File",
          "type": "string"
        }
      },
      "title": "DemoExpectedFiles",
      "type": "object"
    }
  },
  "description": "Dataset/experiment/evaluation \u2192 Jupyter notebook demo.\n\nTitle and summary come from the parent artifact (gen_art step),\nnot from the demo agent. The agent only outputs expected files.",
  "properties": {
    "out_expected_files": {
      "$ref": "#/$defs/DemoExpectedFiles",
      "description": "All output files you created. Must include the demo notebook."
    }
  },
  "required": [],
  "title": "CodeDemo",
  "type": "object"
}
```

IMPORTANT: this task is NOT complete until `./.terminal_claude_agent_struct_out.json` exists and contains JSON matching the schema above.

qwen3 4B on huggingface has base model also official safety finetuned version and there is a community finetuned uncensored model called abliterated (use the 4B size of each so they fit on a 16GB GPU). take these models and do a mech interp analysis of how they differ in activation. also find some patterns in internal computation on safety prompts. and possibly create a new metric for safety. so that for any random model on huggingface you would not need to run the full benchmarks, but only this metric on 0- to few prompts and get a safety evaluation

invariant: the deliverable is the activation-level comparison of the three models and any metric built from it must read activations or weights of a single model. logit-only or text-only readouts are baselines, not the result. this is a mech interp study of where safety lives, not a jailbreak or attack-selection study; do not reframe it as one.
</prompt>
</pasted_content id="7d95">
````

### [2] SKILL-INPUT — aii-colab · 2026-09-22 07:54:29 UTC

The agent loaded the **aii-colab** skill; its `SKILL.md` (the instructions injected into the agent's context) follows verbatim.

````
---
name: aii-colab
description: "Pins Google Colab's runtime for generated Jupyter notebooks — Python 3.12, the exact pre-installed versions of numpy, pandas, scikit-learn, scipy, torch, transformers and more, and the install cell guarded on google.colab that installs those versions locally but never on Colab, where reinstalling them corrupts already-loaded C extensions. ALWAYS read before writing, editing or testing any .ipynb meant to run on Colab. Triggers: Colab, notebook, ipynb, google.colab, /content, numpy.dtype size changed, ABI mismatch, np.alltrue removed in NumPy 2.0, pip install inside a notebook, nbconvert execute, Colab RAM tiers and session timeouts. NOT for plain Python scripts and repo code (aii-python), for measuring or budgeting local hardware (aii-use-hardware), or for renting cloud GPUs (aii-runpod)."
---

## Colab Runtime (as of 2026-02)

- **Python**: 3.12.12
- **OS**: Linux 6.6.105+ x86_64, glibc 2.35

## Critical Rule: Do NOT pip install pre-installed packages ON COLAB

Colab's core scientific packages have **compiled C extensions** linked against each other at specific ABI versions. Installing ANY different version (even a minor bump) partially overwrites files while the loaded `.so` extensions stay in memory, causing:

- `ValueError: numpy.dtype size changed` (numpy 1.x vs 2.x ABI)
- `ImportError: cannot import name '_center'` (numpy 2.0 vs 2.2 ABI)
- Silent corruption of scipy/sklearn/pandas internals

**On Colab: do NOT install these packages. Use Colab's versions.**
**Locally: MUST install these packages at Colab's exact versions** to match the Colab environment.

## Pre-installed Core Packages

These are pre-installed on Colab. On Colab: skip them. Locally: install at these exact versions.

```
numpy==2.0.2
pandas==2.2.2
scikit-learn==1.6.1
scipy==1.16.3
matplotlib==3.10.0
seaborn==0.13.2
torch==2.9.0+cpu
tensorflow==2.19.0
xgboost==3.1.3
lightgbm==4.6.0
networkx==3.6.1
Pillow==11.3.0
opencv-python==4.13.0.92
sympy==1.14.0
statsmodels==0.14.6
bokeh==3.7.3
plotly==5.24.1
nltk==3.9.1
spacy==3.8.11
transformers==5.0.0
datasets==4.0.0
tokenizers==0.22.2
huggingface_hub==1.4.0
openai==2.17.0
requests==2.32.4
beautifulsoup4==4.13.5
lxml==6.0.2
pydantic==2.12.3
tqdm==4.67.3
rich==13.9.4
tabulate==0.9.0
PyYAML==6.0.3
jsonschema==4.26.0
h5py==3.15.1
Cython==3.0.12
numba==0.60.0
dask==2025.12.0
polars==1.31.0
pyarrow==18.1.0
```

## Install Cell Pattern

The install cell must work on BOTH Colab and local Jupyter. Use this conditional pattern:

```python
import subprocess, sys
def _pip(*a): subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', *a])

# Packages NOT pre-installed on Colab (always install everywhere)
_pip('some-rare-pkg==1.2.3')

# Core packages (pre-installed on Colab, install locally to match Colab env)
if 'google.colab' not in sys.modules:
    _pip('numpy==2.0.2', 'pandas==2.2.2', 'scikit-learn==1.6.1', 'scipy==1.16.3', 'matplotlib==3.10.0')
```

**How this works:**
- On **Colab**: `google.colab` is in `sys.modules` → skips core packages (uses Colab's pre-installed ones) → only installs non-Colab packages
- **Locally**: `google.colab` is NOT in `sys.modules` → installs core packages at Colab's exact versions → local .venv matches Colab's environment as closely as possible

Rules:
- CRITICAL: On Colab, pip installing ANY version of numpy/pandas/sklearn/scipy/matplotlib (even the same version) CORRUPTS the pre-loaded C extensions. These MUST be behind the `google.colab` guard.
- Check the pre-installed package list above. If a package is on that list, put it in the `google.colab` guard block. If not, install it unconditionally.
- For the local (non-Colab) install, use the EXACT versions from the list above so the local environment matches Colab.
- Do NOT use `--force-reinstall` — corrupts Colab system packages.
- Do NOT use `%pip` or `!pip` — use the `_pip()` helper for proper conditional control.
- `%%capture` hides install noise — only add AFTER testing is done.
- If a package requires a newer numpy/scipy than Colab has, that package is INCOMPATIBLE with Colab — find an older version or alternative.

### Example

Code imports: `numpy`, `pandas`, `sklearn`, `matplotlib`, `imodels`, `dit`, `rich`

```python
import subprocess, sys
def _pip(*a): subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', *a])

# imodels, dit — NOT on Colab, always install
_pip('imodels==2.0.4')
_pip('--no-deps', 'dit==1.5')

# numpy, pandas, sklearn, matplotlib, rich — pre-installed on Colab, install locally only
if 'google.colab' not in sys.modules:
    _pip('numpy==2.0.2', 'pandas==2.2.2', 'scikit-learn==1.6.1', 'matplotlib==3.10.0', 'rich==13.9.4')
```

### Checking if a package is pre-installed

Before adding a package to the install cell, check:
1. Is it in the pre-installed list above?
2. If unsure, skip it — Colab has 500+ packages pre-installed. If the import works without installing, it's pre-installed.

## NumPy 2.0 Compatibility for Non-Colab Packages

Colab has **numpy 2.0.2**. NumPy 2.0 removed several long-deprecated APIs that older packages still use. If a non-Colab package was written for numpy 1.x, it may crash at runtime with errors like:

- `AttributeError: np.alltrue was removed in the NumPy 2.0 release`
- `AttributeError: np.sometrue was removed in the NumPy 2.0 release`
- `AttributeError: np.product was removed in the NumPy 2.0 release`

**Fix**: Add a compat shim in the imports cell (BEFORE importing the affected package):

```python
import numpy as np
if not hasattr(np, "alltrue"): np.alltrue = np.all
if not hasattr(np, "sometrue"): np.sometrue = np.any
if not hasattr(np, "product"): np.product = np.prod
```

**When to add this**: After installing non-Colab packages, test-run the notebook. If you get `AttributeError: np.X was removed`, add the corresponding shim. Common offenders: `dit`, older scientific libraries that haven't been updated for numpy 2.0.

## Colab-Specific Gotchas

1. **No kernel restart after pip install** — Unlike local Jupyter, Colab doesn't cleanly reload C extensions after pip install. Once numpy/scipy/sklearn are loaded, their C code stays in memory forever until full runtime reset.

2. **`%pip` vs `_pip()` helper** — In notebook install cells, use the `_pip()` helper (see pattern above) so you can wrap installs in Python `if` conditionals. `%pip` and `!pip` can't be used inside if/else blocks.

3. **File system** — `/content/` is the working directory. Files persist within a session but are lost on runtime disconnect.

4. **Memory** — Free tier: ~12GB RAM. Pro: ~25-50GB. Monitor with `!free -h`.

5. **Timeouts** — Free tier disconnects after ~90 min idle, ~12 hours max session. Pro: longer.

6. **`%%capture`** — Suppresses all cell output including errors. Only use on install cells AFTER verifying they work. During development, leave install output visible.

## Testing Notebooks Locally (Simulating Colab)

The goal: create a clean Python 3.12 .venv that mirrors Colab's environment, then run the notebook in it.

```bash
python3.12 -m venv .nb_env
.nb_env/bin/pip install -q pip jupyter ipykernel
.nb_env/bin/jupyter nbconvert --to notebook --execute code_demo.ipynb --output code_demo.ipynb
rm -rf .nb_env
```

**What happens when the notebook runs in this .venv:**
1. The .venv starts empty (just jupyter + ipykernel)
2. The install cell runs → `google.colab` is NOT in sys.modules
3. Non-Colab packages get installed unconditionally
4. Core packages (numpy, pandas, etc.) get installed at Colab's exact versions via the `google.colab` guard
5. Result: the .venv now has the same packages as Colab + the extra non-Colab packages = as close to Colab as possible

This ensures the notebook works from scratch with an environment matching Colab. If a cell fails, fix the notebook and re-run.
````

### [3] SYSTEM-USER prompt · 2026-09-22 07:55:15 UTC

```
Build a Colab-compatible demo Jupyter notebook. Work ONLY inside the workspace:
/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_2/art_G5pqEoRFZ75t
(absolute paths for every write; never write outside it. Everything outside is READ-ONLY.)

FIRST read the skill file /ai-inventor/.claude/skills/aii-colab/SKILL.md and follow its install-cell pattern EXACTLY (Colab pins: numpy==2.0.2, pandas==2.2.2, matplotlib==3.10.0, scikit-learn==1.6.1, scipy==1.16.3 — all behind the `if 'google.colab' not in sys.modules:` guard; use the `_pip()` helper, no %pip/!pip).

ORIGINAL ARTIFACT (read-only source to copy code from):
/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_evaluation_1
  - eval.py, evalkit/stats.py, evalkit/m1_recognition.py, evalkit/prereg.py, results/m1_recognition_headroom.csv, EVAL_REPORT.md
The artifact is a ZERO-GPU, ZERO-API re-adjudication ("Re-checking the numbers we already have") of a mech-interp safety study on Qwen3-4B base / instruct / SafeRL / non-safety-FT lineages. Its headline (M1) is a SITE DISSOCIATION: at the EARLY/prompt site the harm-recognition probe survives a lesion (dAUROC -0.0068, dTPR@1%FPR +0.0007), at the LATE/response site it does not (dAUROC -0.0137, dTPR@1%FPR -0.1439 — a 10.5x larger movement in the operating point than in AUROC). Plus TOST equivalence verdicts per lesion strength, and a restricted-budget k=16 AUROC ordering (Base 0.528 ~ NonSafetyFT 0.540 << Instruct 0.679 < SafeRL 0.698).

DATA: `mini_demo_data.json` ALREADY EXISTS in the workspace. Do not regenerate it. Inspect it (it is 116KB; read selectively with python, not by dumping). Shape:
{"dataset","description","source_file","columns":[...], "rows":[96 dicts, all CSV string values],
 "metrics_agg_reference":{...claimed numbers...}, "prereg_sha256", "run_invariant"}
Row columns include: metric, READOUT_CLASS, BASELINE_ONLY, DESCRIPTIVE, source, checkpoint, lineage, alpha, window, source_file, n_pos, n_neg, auroc_recomputed, `tpr@1fpr` (string "0.3750 [0.3264, 0.4255]"), `tpr@1fpr_point`, smallest_resolvable_step, `tpr@5fpr`, `tpr@5fpr_point`, power_sentence, mde_80pct, auroc_k16, auroc_k16_mean, auroc_k32, auroc_k32_mean, auroc_k64, auroc_k64_mean, `delta_tpr@1fpr`, equivalence_verdict, equivalence_margin, equivalence_margin_achieved, p_tost, p_two_sided, auroc_stored, splithalf_stored, cos_rcontent_rrequest_stored.
Rows with source starting "(a)" are Lane B per-item band activation ARMS (lineage L1..L4, alpha 0.00/0.25/0.50/0.75/1.00, window LATE/EARLY) plus PAIR rows (those have equivalence_verdict / delta_tpr@1fpr filled). Rows "(b)" are Lane A per-item cell projections.

CONVERSION PHILOSOPHY — MINIMAL CHANGES. This is annotating + reformatting, not refactoring. Copy helper functions (e.g. `tost`, `clopper_pearson`, `holm`, `power_sentence` from evalkit/stats.py; the site-dissociation / window aggregation logic and constants MARGIN, WINDOWS, PRIMARY_WINDOW, LESION_PAIRS, LINEAGE_PAIRS from evalkit/m1_recognition.py) VERBATIM where you use them. Do not rename variables, do not add type hints/error handling that were not there, do not restructure. The reader must recognise the original. Only change: file paths -> the loaded `data` variable, remove CLI args, and the minimum needed to run in a notebook. Since raw activations/npz are NOT available, the notebook re-derives the M1 headline numbers from the stored per-arm table rows and CHECKS them against `metrics_agg_reference` — that claim-checking is exactly what eval.py does, so keep eval.py's comparison style (tolerance-based match/mismatch) where you can.

Create `code_demo.ipynb` (use the NotebookEdit tool — load its schema first via ToolSearch "select:NotebookEdit") with this EXACT structure:
- Cell 1 markdown: title, what the artifact does, the run invariant (activation/weight readouts are the result; logit/text are baselines only; mech-interp study of WHERE SAFETY LIVES, not a jailbreak study).
- Cell 2 code: install cell (aii-colab pattern).
- Cell 3 code: imports (json, math, pathlib, numpy, pandas, scipy.stats, matplotlib).
- Cell 4 code: `GITHUB_DATA_URL = "https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-2/evaluation-1/demo/mini_demo_data.json"` plus the exact `load_data()` try-urllib-then-local-Path fallback function (URL first, then local mini_demo_data.json, else FileNotFoundError).
- Cell 5 code: `data = load_data()` and a short print of what loaded.
- Config cell (code, with a markdown cell before it): ALL tunable parameters as named variables at the top — LINEAGES, WINDOWS, PRIMARY_WINDOW, ALPHAS, ALPHA_BASE="0.00", ALPHA_FULL="1.00", MARGIN (TOST margin in TPR units, 0.05), N_BOOT, CLAIM_TOLERANCE, BUDGETS=(16,32,64), RANDOM_SEED. Start at the ABSOLUTE MINIMUM that still produces output (e.g. N_BOOT small), and comment the original full values beside them.
- Then one code cell per logical section, each preceded by a markdown cell explaining what it does and why:
  (1) parse rows into a pandas DataFrame, split (a)/(b) sources, show the READOUT_CLASS invariant column is present on every row (and how many rows are result-eligible vs baseline-only);
  (2) per-arm AUROC and TPR@1%FPR by lesion strength (the saturation/ceiling story — AUROC is at its ceiling unlesioned so it could not fall);
  (3) the SITE DISSOCIATION: EARLY vs LATE delta AUROC and delta TPR@1%FPR from alpha 0.00 -> 1.00 averaged over lineages, and the TPR-over-AUROC movement ratio; compare each against metrics_agg_reference with CLAIM_TOLERANCE and print MATCH/MISMATCH;
  (4) equivalence: collect stored TOST verdicts per lesion strength, and run the copied `tost` on the per-lineage delta vector for the primary window at the prereg MARGIN;
  (5) restricted-budget few-prompt axis: k=16/32/64 AUROC per unlesioned lineage, showing the ordering tracks SAFETY tuning, checked against metrics_agg_reference.
- Final visualization cell (code): print a readable summary table (pandas / to_string), and a matplotlib figure with at least: (a) AUROC and TPR@1%FPR vs lesion strength for EARLY and LATE windows, (b) a bar chart of the k=16 restricted-budget AUROC per lineage. Label axes, add a title. No seaborn.

TEST IT until it passes, from the workspace dir:
  /usr/local/bin/python3.12 -m venv .nb_env
  .nb_env/bin/pip install -q pip jupyter ipykernel
  .nb_env/bin/jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 code_demo.ipynb --output code_demo.ipynb
Run it in the background with a PID (`... & PID=$!`) and poll with `kill -0 $PID`; never kill/monitor processes by name. Total notebook runtime must be under 600s (it should be a few seconds — it is pure table arithmetic). Fix every error and re-run until the whole notebook executes cleanly with real (non-empty, non-NaN) printed output and a rendered figure. If it is fast, you may scale N_BOOT up to the original value in at most 2 scaling rounds; do not chase more. Delete `.nb_env` at the end (`rm -rf .nb_env`) and make sure the executed notebook with outputs is saved as code_demo.ipynb.

Report back (text only, no logs): final config values, total notebook runtime, the printed headline numbers (EARLY/LATE deltas, ratio, k=16 ordering) and their MATCH/MISMATCH status, and confirmation that GITHUB_DATA_URL appears verbatim in the notebook.
```

### [4] SYSTEM-USER prompt · 2026-09-22 08:17:01 UTC

```
<task-notification>
<task-id>aa9df8623bbacb35c</task-id>
<tool-use-id>toolu_01Nob5dSqHi2tZi8Ls52K7FL</tool-use-id>
<output-file>/tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--3-gen-demo-art-notebook-workspaces-iter-2-art-G5pqEoRFZ75t/e2898f60-420a-4bc0-9153-f7ba45705d38/tasks/aa9df8623bbacb35c.output</output-file>
<status>completed</status>
<summary>Agent "Build and test demo notebook" finished</summary>
<note>A task-notification fires each time this agent stops with no live background children of its own. The user can send it another message and resume it, so the same task-id may notify more than once.</note>
<result>Valid notebook, all 20 cells in the required order. The task is complete.

## Summary

**File created:** `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_2/art_G5pqEoRFZ75t/code_demo.ipynb`

**Structure** (20 cells, matching the requested layout exactly): title/invariant markdown → install cell (aii-colab pattern: `_pip()` helper, `numpy==2.0.2`/`pandas==2.2.2`/`matplotlib==3.10.0`/`scipy==1.16.3` behind the `'google.colab' not in sys.modules` guard) → imports → `GITHUB_DATA_URL` + `load_data()` (urllib → local `Path` fallback → `FileNotFoundError`) → `data = load_data()` → Config markdown+cell → 5 numbered analysis sections (each markdown-then-code) → final summary table + two-panel matplotlib figure.

**Final config values:** `LINEAGES=(L1,L2,L3,L4)`, `WINDOWS=(LATE,EARLY)`, `PRIMARY_WINDOW=LATE`, `ALPHAS=(0.00,0.25,0.50,0.75,1.00)`, `MARGIN=0.05`, `N_BOOT=10_000` (scaled up from a 200 first pass, per the ≤2-round rule — the bootstrap only resamples 4 values so this cost nothing), `CLAIM_TOLERANCE=0.01`, `BUDGETS=(16,32,64)`, `RANDOM_SEED=20260921`.

**Verified headline numbers (all MATCH, 12/12, 0 MISMATCH):**
- EARLY (prompt site) full-lesion: ΔAUROC = -0.0068, ΔTPR@1%FPR = +0.0007
- LATE (response site) full-lesion: ΔAUROC = -0.0137, ΔTPR@1%FPR = -0.1439
- LATE movement ratio |ΔTPR@1%FPR|/|ΔAUROC| = 10.51×
- Equivalence: 18 EQUIVALENT / 15 NOT_EQUIVALENT verdicts (whole table); primary-window (LATE) full-lesion 4-lineage vector re-run through the copied `tost()`: verdict NOT_EQUIVALENT, mean diff -0.1439, 90% CI [-0.1966, -0.0911]
- k=16 restricted-budget AUROC ordering: Base 0.528 &lt; NonSafetyFT 0.540 &lt; Instruct 0.679 &lt; SafeRL 0.698 — tracks safety tuning as expected

**GITHUB_DATA_URL** appears verbatim in the notebook (confirmed by string search): `https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-2/evaluation-1/demo/mini_demo_data.json`

**Runtime:** first full cold-venv run (jupyter+ipykernel+numpy/pandas/matplotlib/scipy installed from scratch under heavy shared-machine network contention) took 5m30s — still under the 600s budget. After scaling N_BOOT to 10,000 and re-running (packages already cached), the notebook executed cleanly in 35.6s wall time. `.nb_env` and all temp files (`nbconvert_run.log`, `nbconvert.pid`, `jupyter_ready.flag`) were removed; only `code_demo.ipynb` and the pre-existing `mini_demo_data.json` remain as generated artifacts (a `README.md`/`.aii/manifest.yaml` were also present in the workspace, apparently written by the pipeline's own finalize step — I did not create or modify those).

Helper functions `tost`, `TostResult`, `paired_bootstrap_se`, `power_sentence` (from `evalkit/stats.py`) and the `_site` aggregation logic plus `MARGIN`, `WINDOWS`, `PRIMARY_WINDOW`, `LESION_PAIRS` (from `evalkit/m1_recognition.py`) were copied verbatim, with only the minimal renames needed to run in a notebook (e.g. `df` → `df_` inside `tost()` since `df` is the notebook's DataFrame).</result>
<usage><subagent_tokens>299607</subagent_tokens><tool_uses>376</tool_uses><duration_ms>1304704</duration_ms></usage>
</task-notification>
```
