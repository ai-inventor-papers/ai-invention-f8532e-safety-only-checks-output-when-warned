# gen_demo_art_experiment_8 — report_results

> Phase: `gen_paper_repo` · `gen_demo_art`
> Run: `run_YqmEFECOIR3D` — Specificity and Causality Audits for Activation-Based Safety Readouts
>
> Full, verbatim transcript of this agent task — every system/user prompt, assistant response, thinking block, tool call and tool result — in the order they occurred. Nothing truncated.

## Task: `gen_demo_art_experiment_8` (terminal_claude_agent, claude-opus-5)

### [1] CONFIG · 2026-09-22 08:09:45 UTC

```
model: claude-opus-5 | effort: medium | permission: bypassPermissions
```

### [2] SYSTEM-USER prompt · 2026-09-22 08:09:51 UTC

````


<pasted_content id="b62b">
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
Your workspace: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU`

CRITICAL: Every file you create, write, or save MUST be inside this workspace directory (subdirectories OK). You MUST NOT write files anywhere outside this path — external paths are READ-ONLY. Use absolute paths for all file operations.

EVERY file write MUST start with `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU/`:
GOOD: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU/file.py`, `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU/results/out.json`
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
id: art_l3WSWrVMeJZU
type: experiment
title: Wide screen of 15 second-order safety readouts
summary: >-
  PRE-REGISTERED SCREEN + ONE-SHOT BLIND CONFIRMATION of 15 second-order single-model activation readouts (W1-W8 write-handle/redundancy,
  G1-G4 dimensionless geometry, A1-A3 competing mechanisms) against the incumbent bars. Order is proved by a 10-record SHA-256
  chain, verified end to end (digests/order/UTC/mtime monotone): prereg 689216f41af9cff6 frozen 00:49:37Z BEFORE any candidate
  value -> 7 amendments in 4 immutable batch files -> screen table -> pre-screen + effective rank in a process whose builtins/io/os
  open() calls are audited (0 forbidden reads, self-test passes) -> survivor freeze 8f0b7db5e0bbcbd9 at 03:06:19Z -> held-out
  manifest opened at the registered 04:31Z. PANEL: 48 of 72 graded iteration-4 checkpoints (<=2.2B, verified harvest manifests;
  3 resave arms excluded for shipping no manifest), 42 with a full GPU intervention battery and 6 INTERVENTION_MISSING (LoRA/DPO
  adapters absent from disk, never imputed); the Qwen3-4B quartet + STaR control are array-only and excluded from screen statistics.
  RESULT: the pre-screen dropped 4 of 15 as collinear with the logit gap (G2 +0.745, G1 -0.713, W8 +0.615, W6 +0.554) and
  kept 11; the P1 one-coordinate bound is NOT supported (effective rank 7.16 entropy / 5.32 participation, |cos| 0.645 with
  z(BL1_easy)). On the blind 12-checkpoint panel (MDE 0.73) NO candidate passes clause (ii): every paired checkpoint-bootstrap
  margin over BL1_easy includes zero. The measured trade-off is the deliverable: activation readouts predict held-out over-refusal
  (W3 -0.943 n=6, G4 -0.815 n=12, difference-in-means FLOOR -0.683, G3 -0.673) where the final-layer logit gap gets +0.152
  and AMS sigma +0.657 with the OPPOSITE sign; the five GEOMETRIC candidates (G1-G4, A3) raise 0 false alarms on 24 graded
  no-op edits where BL1_easy raises 11 (exact McNemar p=0.00098; 0 vs 7, p=0.0156 on the 18-pair non-degenerate subset) and
  W2 likewise raises 0 vs 7 on its 14 evaluable pairs (p=0.0156), while W1 is LESS specific than the logit gap (6 vs 1, p=0.125)
  and W7 is 2 vs 1 - and all of them detect at most 3/10 real edits (G3 3, G1 2, G4 2, A3 1, W1/W2/W7 0); and EVERY observed
  sign is opposite to the registered expectation (higher harm-separation = less over-refusal AND more harmful compliance).
  COMMISSIONED FOUR-WAY Qwen3-4B: abliteration rotates the request axis (|cos| 0.98/0.77/0.36/0.015/0.13/0.22 over six depth
  bands) and the child still separates harmful from benign on its OWN axis (d 4.83 at B4) while the parent's axis is blind
  on it (d 0.22); SafeRL keeps the axis (|cos| >= 0.87) and sharpens it (d 6.63 vs 5.78); instruction tuning creates it (Base-instruct
  |cos| <= 0.53); a non-safety STaR fine-tune rotates far less (0.43); abliteration also shrinks the axis ~40%, contradicting
  the inherited 'rotates but does not shrink' claim. MEASURED LIMITATIONS: activation-patching agreement with the first-order
  ablation is +0.53/-0.54/+0.40 across the three declared checkpoints; W2 is fold-unstable and NaN on every held-out row;
  the W normaliser degenerates on base models with no refusal behaviour (pythia-410m, Pleias-1.2b); G3 and A1 are RANK_UNSTABLE;
  the screen panel holds only 7 independent lineages, and under a lineage-cluster bootstrap G4's (+0.663 [+0.096,+0.813])
  and W3's (+0.914 [+0.227,+0.943]) margins over the logit gap DO exclude zero - reported as a sensitivity, never as a pass.
  Bars reproduce iteration 4 on 51/51 tags (max rel diff 4e-8) and the band convention reproduces its direction cosines to
  <1e-6. OpenRouter spend $0.00 (every outcome column already existed on disk). 14 datasets / 3310 examples in method_out.json,
  schema-validated.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1
out_expected_files:
- method.py
- full_method_out.json
- mini_method_out.json
- preview_method_out.json
out_demo_files:
- path: method.py
  description: Research methodology implementation
</artifact_info>

<github_repo>
Repo URL: https://github.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned
Raw data URL: https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-5/experiment-1/demo/mini_demo_data.json

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
GITHUB_DATA_URL = "https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-5/experiment-1/demo/mini_demo_data.json"
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
TODO 6. Verify: (1) code_demo.ipynb contains GITHUB_DATA_URL = "https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-5/experiment-1/demo/mini_demo_data.json" exactly, (2) mini_demo_data.json exists, (3) uses GitHub URL pattern not just open('mini_demo_data.json').
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
</pasted_content id="b62b">
````

### [3] ASSISTANT · 2026-09-22 08:09:53 UTC

```
I'll start by setting up the todo list and reading the required skills.
```

### [4] TOOL CALL — Skill · 2026-09-22 08:09:53 UTC

```
aii-colab
```

### [5] TOOL CALL — Skill · 2026-09-22 08:09:53 UTC

```
aii-long-running-tasks
```

### [6] TOOL RESULT — Skill · 2026-09-22 08:09:53 UTC

```
{"success": true, "commandName": "aii-colab"}
```

### [7] TOOL RESULT — Skill · 2026-09-22 08:09:53 UTC

```
{"success": true, "commandName": "aii-long-running-tasks"}
```

### [8] TOOL CALL — Bash · 2026-09-22 08:09:53 UTC

```
List artifact workspace:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1 && ls -la && echo "---SIZES---" && du -sh * 2>/dev/null
```

### [9] TOOL RESULT — Bash · 2026-09-22 08:09:53 UTC

```
{"stdout": "total 27637\ndrwxrwxrwx 13 root root 3000886 Sep 22 04:38 .\ndrwxrwxrwx  6 root root 3002046 Sep 21 23:09 ..\ndrwxrwxrwx  2 root root 1000251 Sep 22 04:14 .aii\ndrwxrwxrwx  3 root root 1000156 Sep 21 23:24 .claude\n-rw-rw-rw-  1 root root 1973308 Sep 22 04:48 .repl_agent.ptylog\n-rw-rw-rw-  1 root root    4342 Sep 22 04:46 .terminal_claude_agent_struct_out.json\ndrwxrwxrwx  5 root root 2085231 Sep 21 23:26 .venv_ams\ndrwxrwxrwx  5 root root 3000700 Sep 21 23:27 .venv_gpu\n-rw-rw-rw-  1 root root    9415 Sep 22 04:42 README.md\ndrwxrwxrwx  2 root root 1006283 Sep 22 00:37 assets\ndrwxrwxrwx  4 root root 2008609 Sep 22 03:12 cache\ndrwxrwxrwx  2 root root 1000348 Sep 21 23:25 env\n-rw-rw-rw-  1 root root 1506698 Sep 22 04:42 full_method_out.json\ndrwxrwxrwx  2 root root       1 Sep 21 23:25 hf_cache\ndrwxrwxrwx  4 root root 2000106 Sep 22 04:33 logs\n-rw-rw-rw-  1 root root   40213 Sep 22 04:41 method.py\n-rw-rw-rw-  1 root root 1303132 Sep 22 04:41 method_out.json\n-rw-rw-rw-  1 root root  171864 Sep 22 04:42 mini_method_out.json\n-rw-rw-rw-  1 root root   82474 Sep 22 04:42 preview_method_out.json\n-rwxrwxrwx  1 root root     858 Sep 22 01:38 restore.sh\ndrwxrwxrwx  6 root root 2095392 Sep 22 04:37 results\n-rwxrwxrwx  1 root root    1022 Sep 22 02:38 run_s5.sh\ndrwxrwxrwx  5 root root 2000157 Sep 22 04:39 src\n---SIZES---\n9.5K\tREADME.md\n1.1M\tassets\n102M\tcache\n981K\tenv\n1.5M\tfull_method_out.json\n512\thf_cache\n5.0M\tlogs\n40K\tmethod.py\n1.3M\tmethod_out.json\n168K\tmini_method_out.json\n81K\tpreview_method_out.json\n1.0K\trestore.sh\n988M\tresults\n1.0K\trun_s5.sh\n13M\tsrc", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [10] TOOL CALL — Bash · 2026-09-22 08:09:57 UTC

```
Outline method.py:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1 && wc -l method.py && grep -n "^def \|^class \|^# ---\|^####\|^if __name__\|^[A-Z_]* = \|^@" method.py | head -120
```

### [11] TOOL CALL — Bash · 2026-09-22 08:09:57 UTC

```
Preview output structure:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1 && head -c 6000 preview_method_out.json
```

### [12] TOOL RESULT — Bash · 2026-09-22 08:09:57 UTC

```
{"stdout": "748 method.py\n25:WS = Path(__file__).resolve().parent\n31:PLAN_FILE = Path(\"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_plan/\"\n34:MUST_NOT_CLAIM_PATH = RESEARCH1_DIR / \"must_not_claim.json\"\n61:def _load(path: Path) -> dict | None:\n71:def _ex(input_obj, output, **kw) -> dict:\n82:def build_screen_table_dataset(screen_table: dict | None) -> dict:\n97:def build_prescreen_dataset(prescreen: dict | None) -> dict:\n113:def build_rank_analysis_dataset(rank: dict | None) -> dict:\n133:def build_confirmation_dataset(confirmation: dict | None, survivors: list[dict]) -> dict:\n153:def build_quartet_dataset(quartet: dict | None) -> dict:\n169:def build_stability_dataset(screen_table: dict | None) -> dict:\n190:def build_patching_dataset(ckpt_files: list[dict]) -> dict:\n201:def build_transfer_dataset(tierA_files: list[dict], ckpt_files: list[dict]) -> dict:\n216:def build_norm_displacement_dataset(ckpt_files: list[dict]) -> dict:\n227:def _excludes_zero(ci) -> bool | None:\n233:def build_pair_audits_dataset(pair_boot: dict | None, pair_audit: dict | None) -> dict:\n274:def build_selection_clauses_metadata(pair_audit: dict | None) -> dict:\n296:def build_a3_domain_profile_dataset(a3_var: dict | None) -> dict:\n316:def build_quartet_geometry_dataset(quartet: dict | None) -> dict:\n340:def build_bars_and_validation_dataset(screen_table: dict | None, bars_validation: dict | None,\n379:def build_stability_flags_dataset(stability_flags: dict | None) -> dict:\n398:def build_prior_art_fences() -> dict:\n408:def build_readout_only_labelling() -> dict:\n455:def build_deviations_metadata(results_dir: Path) -> dict:\n479:def build_prereg_amendments_metadata(results_dir: Path) -> dict:\n490:def build_hash_chain_metadata(results_dir: Path) -> dict:\n505:def build_sensitivity_analyses_metadata(cluster_sens: dict | None, confirm_cluster_sens: dict | None) -> dict:\n522:def build_headlines_metadata(screen_headlines: dict | None, quartet_headlines: dict | None) -> dict:\n531:def build_per_item_array_coverage_metadata(restore_log: dict | None) -> dict:\n546:LIMITATIONS = [\n574:def build_limitations_metadata(stability_flags: dict | None) -> dict:\n583:def compute_verdict(survivor: dict | None, confirmation: dict | None) -> str:\n622:def main() -> None:\n746:if __name__ == \"__main__\":", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [13] TOOL RESULT — Bash · 2026-09-22 08:09:57 UTC

```
{"stdout": "{\n  \"metadata\": {\n    \"method_name\": \"iter5_wide_screen_and_confirmation_join\",\n    \"description\": \"S2.6 assemble -> S3 pre-screen/effective-rank -> S4 freeze -> S5 confirmation join -> S6 output, per src/SPEC_tail.md.\",\n    \"artifact\": \"iter5 wide screen + one-shot confirmation join (gen_plan_experiment_2_idx2)\",\n    \"generated_utc\": \"2026-09-22T04:41:59.562321Z\",\n    \"results_dir\": \"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/results\",\n    \"n_panel_checkpoints\": 48,\n    \"n_candidates_registered\": 15,\n    \"prescreen_n_dropped\": 4,\n    \"prescreen_n_kept\": 11,\n    \"rank_analysis_verdict\": \"P1 NOT supported by the rank structure: erank_entropy=7.158 (threshold <=1.5), |cos(leading ckpt singvec, z(BL1_easy))|=0.645 (threshold >=0.8)\",\n    \"n_survivors\": 11,\n    \"s6_2_disclosure\": \"S6.2  Mandatory disclosure block in the output (reviewer must-fixes carried forward):\\n        - the 15 no-op pairs by CATEGORY: numerical precision x8, head-only unembedding x3,\\n          system-promp...\",\n    \"verdict\": \"NO CANDIDATE PASSES THE REGISTERED BAR: 11 frozen survivors, 0 confirmed on clause (ii) [confirmation FULL, n=12, MDE=0.7321442233518527]. P1 (the one-coordinate bound) is ALSO NOT SUPPORTED (effectiv...\",\n    \"cost_ledger\": {\n      \"openrouter_usd_planned\": 0.0,\n      \"openrouter_usd_actual\": 0.0,\n      \"note\": \"every outcome column already existed on disk; no judge call was made\"\n    },\n    \"deviations\": {\n      \"sources\": [\n        \"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/results/deviations.json\",\n        \"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/results/deviations_orchestrator.json\",\n        \"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/results/proposed_amendments_tail.json\"\n      ],\n      \"n_merged\": 33,\n      \"merged\": [\n        {\n          \"id\": \"d1_int8bnb_missing_p3\",\n          \"stage\": \"P0.3\",\n          \"what\": \"F1__int8bnb, F2__int8bnb, F3__int8bnb are each missing A_prompt_p3.npy (the fp16-cast N5 perturbation) out of the 27-file schema.\",\n          \"impact\": \"EXPECTED per harvest_variants.py (int8bnb is already quantized; the fp16-cast perturbation is not applicable). Do not treat as corrupt; A_prompt_p3 is simply NOT_AVAILABLE for the 3 int8bnb tags.\"\n        },\n        {\n          \"id\": \"d2_resave_no_manifest\",\n          \"stage\": \"P0.3\",\n          \"what\": \"F1__resave, F2__resave, F3__resave lack MANIFEST.sha256.json (24 files instead of 27; DONE+meta.json present).\",\n          \"impact\": \"By design: harvest_variants.py's resave branch copies parent arrays but explicitly excludes DONE/meta.json/MANIFEST.sha256.json from the copy, and never writes its own manifest. Integrity instead rest...\"\n        },\n        {\n          \"id\": \"d3_private_dir_gone\",\n          \"stage\": \"P0.3\",\n          \"what\": \"I4/private/ (PRIVATE, holding ADAPTERS=private/adapters and resave snapshots) does not exist on disk; only results/edits/*.npz + *_train.json metadata remain (17 files: F1-F4 hbar.npz/chunks, F1-F3 le...\",\n          \"impact\": \"lora/dpo adapter WEIGHTS are unrecoverable without retraining (train_lora/train_dpo in variants.py, deterministic given SEED=20260921 and side_sets.json['lora_rows'/'dpo_rows'], but re-running costs G...\"\n        }\n      ]\n    },\n    \"prereg_amendments\": {\n      \"status\": \"OK\",\n      \"source\": \"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/results/prereg_amendments.json\",\n      \"n\": 7,\n      \"amendments\": [\n        {\n          \"id\": \"A1\",\n          \"section\": \"b_band_rule (descriptive parenthetical only)\",\n          \"reason\": \"factual correction discovered by the unit tests after the freeze\",\n          \"change\": \"The parenthetical 'L = RAW pre-final-norm output of block L' is WRONG. Unit test T10 (results/unit_tests.json) shows transformers-5.17 output_hidden_states stores final_norm(output of the last block) ...\",\n          \"impact\": \"none on any definition: G3 already caps its top index at min(hi(b), L-1) precisely so it is valid whichever normalisation index L carries; W4's end-of-stack read is normalised by its own mean norm; ba...\"\n        },\n        {\n          \"id\": \"A2\",\n          \"section\": \"tier-A structural-pair prompt bootstrap (SPEC_tierA)\",\n          \"reason\": \"I4/assets/pairs.json embeds iteration-2 behaviour rates (HC/OR/SE), i.e. outcome data, so no pre-freeze process may open it.\",\n          \"change\": \"Pair STRUCTURE is defined by rule from tag names (every in-house arm vs its family ref; 8 Hub lineage pairs: Qwen3-0.6B->huihui-0.6B-abl, Qwen3-1.7B->huihui-1.7B-abl, Qwen2.5-1.5B-Instruct->Josiefied-...\",\n          \"impact\": \"no candidate definition changes; S5 joins these structural pairs to classification.json labels by (parent, child) name after the freeze.\"\n        },\n        {\n          \"id\": \"A3\",\n          \"section\": \"disclosure (no rule change)\",\n          \"reason\": \"honest reporting of an outcome exposure before the freeze\",\n          \"change\": \"At 01:26Z the orchestrator printed a 2-row snippet of I4/assets/pairs.json while locating the pair structure; it showed iteration-2 behaviour rates for Qwen/Qwen3-4B (OR .444; quartet block, excluded ...\",\n          \"impact\": \"none: the prereg (00:49:37Z) was already frozen, the pre-screen is mechanical (|rho| vs BL1_easy, no outcome) and runs in an audited process; no definition, threshold or selection was changed after th...\"\n        }\n      ]\n    },\n    \"field_norm_positions\": {\n      \"A\": \"decodable-but-inert = the field's knowledge-action gap (Basu 2603.18353: probes 98.2% AUROC vs 45.1% output sensitivity; the zero-and-zero figure is the SAE arm only): PREMISE, never a finding\",\n      \"B\": \"every write-handle scalar is READOUT-ONLY unless output-level correction AND collateral disruption vs a random-perturbation control are both run", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [14] TOOL CALL — Bash · 2026-09-22 08:10:01 UTC

```
Read method.py head:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1 && sed -n '1,135p' method.py
```

### [15] TOOL RESULT — Bash · 2026-09-22 08:10:01 UTC

```
{"stdout": "#!/usr/bin/env python3\n\"\"\"S6: method_out.json (exp_gen_sol_out schema) -- the pipeline's final aggregate output.\n\nAggregates results/{screen_table,prescreen,rank_analysis,survivor,confirmation}.json,\nresults/screen/{quartet_tierA,pair_boot_tierA}.json and results/screen/ckpt_*.json into one\nexp_gen_sol_out document: {\"metadata\":{...}, \"datasets\":[{\"dataset\",\"examples\":[...]}]}.\n\nWorks when confirmation.json is missing (verdict = \"CONFIRMATION NOT RUN\") and when\nsurvivor.json's survivors == \"NONE\" (verdict = \"P1_WINS: THE BOUND\"). Includes the S6.2\ndisclosure block verbatim from the iter-5 experiment-2 plan file.\n\nCLI:\n    .venv_gpu/bin/python method.py [--results-dir DIR] [--out-path PATH]\n\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport json\nimport sys\nfrom pathlib import Path\n\nfrom loguru import logger\n\nWS = Path(__file__).resolve().parent\nsys.path.insert(0, str(WS / \"src\"))\n\nlogger.remove()\nlogger.add(sys.stdout, level=\"INFO\", format=\"{time:HH:mm:ss}|{level:<7}|{message}\")\n\nPLAN_FILE = Path(\"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_plan/\"\n                  \"gen_plan_experiment_2/.terminal_claude_agent_struct_out.json\")\nRESEARCH1_DIR = Path(\"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_research_1\")\nMUST_NOT_CLAIM_PATH = RESEARCH1_DIR / \"must_not_claim.json\"\nI4_EXP2_ANALYSIS = Path(\"/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_4/gen_art/\"\n                         \"gen_art_experiment_2/results/analysis.json\")\n\n# S6.2 disclosure block, VERBATIM from the plan's implementation_pseudocode (the 'S6.2' section).\nS6_2_DISCLOSURE = \"\"\"S6.2  Mandatory disclosure block in the output (reviewer must-fixes carried forward):\n        - the 15 no-op pairs by CATEGORY: numerical precision x8, head-only unembedding x3,\n          system-prompt x2, DPO x1, rank-one lesion alpha 0.5 x1; re-saves EXCLUDED as trivially zero;\n          ALL THREE LoRA ARMS FAILED TO BE NO-OPS.\n        - the defensible 12-pair denominator (BL1_easy 4/12 vs N1 1/12), not only 6/15 vs 1/15.\n        - SENSITIVITY IS THE BINDING FAILURE, NOT SPECIFICITY, and the trade-off runs THROUGH the\n          activation class (C13_peak_d and N11 are the two most sensitive at 6/9 and the two least\n          specific at 3/15 and 2/15), not along the activation-vs-logit boundary.\n        - the BL1 variant ordering FLIP, disclosed in every table.\n        - AMS at batch 1 AND batch 8 with the padding hazard named.\n        - the two over-refusal measurements reconciled BY NAMING THE BENIGN SET IN THE COLUMN HEADER\n          (XSTest twins 0.11 instruct / 0.00 SafeRL vs hard-benign probes 0.438 / 0.479).\n        - PRIOR-ART FENCES: MUST NOT claim a first cross-family few-prompt activation metric (AMS);\n          a first internal scoring of abliterated checkpoints; reference-free or <=16 prompts as\n          novelty; recognition/execution naming; any weights-only statistic; a first decode-site\n          readout (2609.18471); a first readout-under-quantisation or benign-fine-tune FPR (Duan\n          2606.15980, Hurtado); a first logit-vs-activation comparison; a first random-direction\n          control; or the read-vs-write dissociation itself (Basu 2603.18353, Galeone 2606.24952 own\n          it at the model level; it is a PREMISE here). Self-repair and backup behaviour are\n          established in the circuits literature; W4 is a SCALARISATION, never a discovery.\"\"\"\n\n\ndef _load(path: Path) -> dict | None:\n    if not path.exists():\n        return None\n    try:\n        return json.loads(path.read_text())\n    except json.JSONDecodeError:\n        logger.warning(f\"unreadable JSON: {path}\")\n        return None\n\n\ndef _ex(input_obj, output, **kw) -> dict:\n    \"\"\"Build one exp_gen_sol_out example; predict_/metadata_ kwargs are cast to str/JSON as required.\"\"\"\n    e = {\"input\": json.dumps(input_obj, sort_keys=True), \"output\": str(output)}\n    for k, v in kw.items():\n        if k.startswith(\"predict_\"):\n            e[k] = \"\" if v is None else str(v)\n        elif k.startswith(\"metadata_\"):\n            e[k] = v\n    return e\n\n\ndef build_screen_table_dataset(screen_table: dict | None) -> dict:\n    examples = []\n    if screen_table:\n        for r in screen_table.get(\"rows\", []):\n            examples.append(_ex(\n                {\"tag\": r[\"tag\"], \"candidate\": r[\"candidate\"]}, r.get(\"value\"),\n                metadata_tier=r.get(\"tier\"), metadata_censored=r.get(\"censored\"),\n                metadata_flags=r.get(\"flags\"), metadata_band=r.get(\"band\"),\n                metadata_n_prompts=r.get(\"n_prompts\"),\n            ))\n    if not examples:\n        examples = [_ex({\"note\": \"screen_table.json not available\"}, \"N/A\")]\n    return {\"dataset\": \"screen_table\", \"examples\": examples}\n\n\ndef build_prescreen_dataset(prescreen: dict | None) -> dict:\n    examples = []\n    if prescreen:\n        for cand, rec in prescreen.get(\"candidates\", {}).items():\n            examples.append(_ex(\n                {\"candidate\": cand}, rec.get(\"status\"),\n                metadata_rho=rec.get(\"rho\"), metadata_ci=rec.get(\"ci\"), metadata_n=rec.get(\"n\"),\n                metadata_mde=rec.get(\"mde\"), metadata_tier=rec.get(\"tier\"),\n                predict_rho_BL1_easy=rec.get(\"rho\"),\n                predict_rho_censored_dropped=rec.get(\"rho_censored_dropped\"),\n            ))\n    if not examples:\n        examples = [_ex({\"note\": \"prescreen.json not available\"}, \"N/A\")]\n    return {\"dataset\": \"prescreen\", \"examples\": examples}\n\n\ndef build_rank_analysis_dataset(rank: dict | None) -> dict:\n    examples = []\n    if rank:\n        for block_name in (\"full_panel_all_candidates\", \"tier_A_only_full_panel\", \"complete_tierB_coverage\"):\n            b = rank.get(block_name, {})\n            if \"erank_full\" not in b:\n                continue\n            examples.append(_ex(\n                {\"block\": block_name}, rank.get(\"verdict\"),\n                metadata_erank_entropy=b[\"erank_full\"].get(\"erank_entropy\"),\n                metadata_erank_participation=b[\"erank_full\"].get(\"erank_participation\"),\n                metadata_erank_entropy_partial_BL1=b.get(\"erank_partial_BL1\", {}).get(\"erank_entropy\"),\n                metadata_abs_cos_ckpt_vs_zBL1=b.get(\"abs_cos_leading_right_singvec_vs_zBL1\"),\n                metadata_n_candidates=b.get(\"n_candidates\"), metadata_n_checkpoints=b.get(\"n_checkpoints\"),\n            ))\n    if not examples:\n        examples = [_ex({\"note\": \"rank_analysis.json not available\"}, \"N/A\")]\n    return {\"dataset\": \"rank_analysis\", \"examples\": examples}\n\n\ndef build_confirmation_dataset(confirmation: dict | None, survivors: list[dict]) -> dict:\n    examples = []\n    if confirmation and confirmation.get(\"confirmation_table\"):", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [16] TOOL CALL — Bash · 2026-09-22 08:10:01 UTC

```
Inspect datasets structure:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1 && python3 -c "
import json
d=json.load(open('preview_method_out.json'))
print(list(d.keys()))
ds=d.get('datasets')
print(type(ds), len(ds) if hasattr(ds,'__len__') else '')
if isinstance(ds,list):
    for x in ds: print(x.get('dataset_name'), list(x.keys()), len(x.get('examples',[])))
elif isinstance(ds,dict):
    for k,v in ds.items(): print(k, type(v), list(v.keys())[:8] if isinstance(v,dict) else len(v))
"
```

### [17] TOOL RESULT — Bash · 2026-09-22 08:10:01 UTC

```
{"stdout": "['metadata', 'datasets']\n<class 'list'> 3\nNone ['dataset', 'examples'] 3\nNone ['dataset', 'examples'] 3\nNone ['dataset', 'examples'] 3", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [18] TOOL CALL — Bash · 2026-09-22 08:10:07 UTC

```
Read stability + main:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1 && sed -n '169,232p' method.py && echo "=====MAIN=====" && sed -n '622,748p' method.py
```

### [19] TOOL RESULT — Bash · 2026-09-22 08:10:07 UTC

```
{"stdout": "def build_stability_dataset(screen_table: dict | None) -> dict:\n    examples = []\n    if screen_table:\n        for r in screen_table.get(\"rows\", []):\n            stab = r.get(\"stability\")\n            if not isinstance(stab, list) or not stab:\n                continue\n            vals = [d[\"value\"] for d in stab if isinstance(d, dict) and d.get(\"value\") is not None]\n            reg = r.get(\"value\")\n            agree = None\n            if vals and reg is not None:\n                agree = float(sum(1 for v in vals if (v >= 0) == (reg >= 0)) / len(vals))\n            examples.append(_ex(\n                {\"tag\": r[\"tag\"], \"candidate\": r[\"candidate\"]}, reg,\n                metadata_n_draws=len(stab), metadata_sign_agree_frac=agree,\n            ))\n    if not examples:\n        examples = [_ex({\"note\": \"no stability draws available\"}, \"N/A\")]\n    return {\"dataset\": \"stability\", \"examples\": examples}\n\n\ndef build_patching_dataset(ckpt_files: list[dict]) -> dict:\n    examples = []\n    for c in ckpt_files:\n        p = c.get(\"patching\")\n        if p:\n            examples.append(_ex({\"tag\": c.get(\"tag\")}, p.get(\"spearman\", p), metadata_patching=p))\n    if not examples:\n        examples = [_ex({\"note\": \"no Tier-B patching-validation rows available (Tier B not run)\"}, \"N/A\")]\n    return {\"dataset\": \"patching_validation\", \"examples\": examples}\n\n\ndef build_transfer_dataset(tierA_files: list[dict], ckpt_files: list[dict]) -> dict:\n    examples = []\n    for t in tierA_files:\n        tr = t.get(\"transfer\")\n        if tr:\n            examples.append(_ex({\"tag\": t.get(\"tag\"), \"source\": \"tierA\"}, tr.get(\"G2_c11\"), metadata_transfer=tr))\n    for c in ckpt_files:\n        tr = c.get(\"transfer\")\n        if tr:\n            examples.append(_ex({\"tag\": c.get(\"tag\"), \"source\": \"tierB\"}, tr.get(\"W2_c11\"), metadata_transfer=tr))\n    if not examples:\n        examples = [_ex({\"note\": \"no transfer_I rows available\"}, \"N/A\")]\n    return {\"dataset\": \"transfer_check\", \"examples\": examples}\n\n\ndef build_norm_displacement_dataset(ckpt_files: list[dict]) -> dict:\n    examples = []\n    for c in ckpt_files:\n        nd = c.get(\"norm_displacement\")\n        if nd:\n            examples.append(_ex({\"tag\": c.get(\"tag\")}, nd, metadata_norm_displacement=nd))\n    if not examples:\n        examples = [_ex({\"note\": \"no norm_displacement rows available (Tier B not run)\"}, \"N/A\")]\n    return {\"dataset\": \"norm_displacement\", \"examples\": examples}\n\n\ndef _excludes_zero(ci) -> bool | None:\n    if not ci or len(ci) != 2 or ci[0] is None or ci[1] is None:\n        return None\n    return bool(ci[0] > 0 or ci[1] < 0)\n\n\n=====MAIN=====\ndef main() -> None:\n    ap = argparse.ArgumentParser()\n    ap.add_argument(\"--results-dir\", type=Path, default=WS / \"results\")\n    ap.add_argument(\"--out-path\", type=Path, default=WS / \"method_out.json\")\n    ap.add_argument(\"--logs-dir\", type=Path, default=WS / \"logs\")\n    args = ap.parse_args()\n\n    logs_dir = args.logs_dir.resolve()\n    logs_dir.mkdir(parents=True, exist_ok=True)\n    logger.add(logs_dir / \"method.log\", rotation=\"10 MB\", level=\"DEBUG\")\n\n    results_dir = args.results_dir.resolve()\n    logger.info(f\"method.py: results_dir={results_dir}\")\n\n    screen_table = _load(results_dir / \"screen_table.json\")\n    prescreen = _load(results_dir / \"prescreen.json\")\n    rank = _load(results_dir / \"rank_analysis.json\")\n    survivor = _load(results_dir / \"survivor.json\")\n    confirmation = _load(results_dir / \"confirmation.json\")\n    quartet = _load(results_dir / \"screen\" / \"quartet_tierA.json\")\n    pair_boot = _load(results_dir / \"screen\" / \"pair_boot_tierA.json\")\n    a3_var = _load(results_dir / \"screen\" / \"a3_variance_decomposition.json\")\n    bars_validation = _load(results_dir / \"bars_validation.json\")\n    ams_cli_validation = _load(results_dir / \"ams_cli_validation.json\")\n    regression_check = _load(results_dir / \"regression_check.json\")\n    unit_tests = _load(results_dir / \"unit_tests.json\")\n    unit_tests_rowhooks = _load(results_dir / \"unit_tests_rowhooks.json\")\n    stability_flags = _load(results_dir / \"stability_flags.json\")\n    prereg = _load(results_dir / \"prereg.json\")\n    pair_audit = _load(results_dir / \"pair_audit.json\")\n    cluster_sens = _load(results_dir / \"cluster_sensitivity.json\")\n    confirm_cluster_sens = _load(results_dir / \"confirm_cluster_sensitivity.json\")\n    screen_headlines = _load(results_dir / \"screen_headlines.json\")\n    quartet_headlines = _load(results_dir / \"screen\" / \"quartet_headlines.json\")\n    restore_log = _load(results_dir / \"registered_items_restore_log.json\")\n\n    tierA_files = []\n    tierA_dir = results_dir / \"screen\" / \"tierA\"\n    if tierA_dir.exists():\n        for f in tierA_dir.glob(\"*.json\"):\n            d = _load(f)\n            if d:\n                tierA_files.append(d)\n    ckpt_files = []\n    screen_dir = results_dir / \"screen\"\n    if screen_dir.exists():\n        for f in screen_dir.glob(\"ckpt_*.json\"):\n            d = _load(f)\n            if d:\n                ckpt_files.append(d)\n\n    survivors_list = survivor.get(\"survivors\") if survivor and survivor.get(\"survivors\") != \"NONE\" else []\n    verdict = compute_verdict(survivor, confirmation)\n    logger.info(f\"verdict: {verdict}\")\n\n    plan_disclosure = S6_2_DISCLOSURE\n    if PLAN_FILE.exists():\n        try:\n            plan = json.loads(PLAN_FILE.read_text())\n            pseudo = plan.get(\"implementation_pseudocode\", \"\")\n            idx = pseudo.find(\"S6.2\")\n            if idx >= 0:\n                end = pseudo.find(\"S6.3\", idx)\n                plan_disclosure = pseudo[idx: end if end > idx else idx + 3000].strip()\n        except (json.JSONDecodeError, OSError) as exc:\n            logger.warning(f\"could not re-read plan file, using embedded copy: {exc!r}\")\n\n    metadata = {\n        \"method_name\": \"iter5_wide_screen_and_confirmation_join\",\n        \"description\": (\"S2.6 assemble -> S3 pre-screen/effective-rank -> S4 freeze -> S5 confirmation \"\n                         \"join -> S6 output, per src/SPEC_tail.md.\"),\n        \"artifact\": \"iter5 wide screen + one-shot confirmation join (gen_plan_experiment_2_idx2)\",\n        \"generated_utc\": __import__(\"datetime\").datetime.now(__import__(\"datetime\").timezone.utc)\n                          .strftime(\"%Y-%m-%dT%H:%M:%S.%fZ\"),\n        \"results_dir\": str(results_dir),\n        \"n_panel_checkpoints\": len(screen_table.get(\"panel\", [])) if screen_table else None,\n        \"n_candidates_registered\": 15,\n        \"prescreen_n_dropped\": prescreen.get(\"n_dropped\") if prescreen else None,\n        \"prescreen_n_kept\": prescreen.get(\"n_kept\") if prescreen else None,\n        \"rank_analysis_verdict\": rank.get(\"verdict\") if rank else None,\n        \"n_survivors\": len(survivors_list),\n        \"s6_2_disclosure\": plan_disclosure,\n        \"verdict\": verdict,\n        \"cost_ledger\": {\"openrouter_usd_planned\": 0.0, \"openrouter_usd_actual\": 0.0,\n                        \"note\": \"every outcome column already existed on disk; no judge call was made\"},\n        \"deviations\": build_deviations_metadata(results_dir),\n        \"prereg_amendments\": build_prereg_amendments_metadata(results_dir),\n        \"field_norm_positions\": prereg.get(\"field_norm_positions\") if prereg else\n                                {\"status\": \"NOT_FOUND\", \"path_searched\": str(results_dir / \"prereg.json\")},\n        \"prior_art_fences\": build_prior_art_fences(),\n        \"readout_only_labelling\": build_readout_only_labelling(),\n        \"hash_chain\": build_hash_chain_metadata(results_dir),\n        \"selection_clauses\": build_selection_clauses_metadata(pair_audit),\n        \"sensitivity_analyses\": build_sensitivity_analyses_metadata(cluster_sens, confirm_cluster_sens),\n        **build_headlines_metadata(screen_headlines, quartet_headlines),\n        \"per_item_array_coverage\": build_per_item_array_coverage_metadata(restore_log),\n        \"limitations\": build_limitations_metadata(stability_flags),\n    }\n\n    datasets = [\n        build_screen_table_dataset(screen_table),\n        build_prescreen_dataset(prescreen),\n        build_rank_analysis_dataset(rank),\n        build_confirmation_dataset(confirmation, survivors_list),\n        build_quartet_dataset(quartet),\n        build_stability_dataset(screen_table),\n        build_patching_dataset(ckpt_files),\n        build_transfer_dataset(tierA_files, ckpt_files),\n        build_norm_displacement_dataset(ckpt_files),\n        build_pair_audits_dataset(pair_boot, pair_audit),\n        build_a3_domain_profile_dataset(a3_var),\n        build_quartet_geometry_dataset(quartet),\n        build_bars_and_validation_dataset(screen_table, bars_validation, ams_cli_validation,\n                                           regression_check, unit_tests, unit_tests_rowhooks),\n        build_stability_flags_dataset(stability_flags),\n    ]\n\n    out = {\"metadata\": metadata, \"datasets\": datasets}\n    args.out_path.parent.mkdir(parents=True, exist_ok=True)\n    args.out_path.write_text(json.dumps(out, indent=1, default=str))\n    logger.info(f\"wrote {args.out_path} ({sum(len(d['examples']) for d in datasets)} total examples \"\n                f\"across {len(datasets)} datasets)\")\n\n\nif __name__ == \"__main__\":\n    from loguru import logger as _lg\n    _lg.catch(reraise=True)(main)()", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [20] TOOL CALL — Bash · 2026-09-22 08:10:07 UTC

```
Inspect mini/full datasets:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1 && python3 -c "
import json
d=json.load(open('mini_method_out.json'))
for x in d['datasets']:
    print(x['dataset'], len(x['examples']))
print('---first screen_table ex---')
for x in d['datasets']:
    if x['dataset']=='screen_table':
        for e in x['examples'][:3]: print(json.dumps(e)[:400])
"
echo "=== full counts ==="
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1 && python3 -c "
import json
d=json.load(open('full_method_out.json'))
for x in d['datasets']: print(x['dataset'], len(x['examples']))
"
```

### [21] TOOL RESULT — Bash · 2026-09-22 08:10:07 UTC

```
{"stdout": "screen_table 3\nprescreen 3\nrank_analysis 3\nconfirmation 3\ncommissioned_quartet 3\nstability 3\npatching_validation 3\ntransfer_check 3\nnorm_displacement 3\npair_audits 3\na3_domain_profile 3\nquartet_geometry 3\nbars_and_validation 3\nstability_flags 3\n---first screen_table ex---\n{\"input\": \"{\\\"candidate\\\": \\\"W1\\\", \\\"tag\\\": \\\"F1__a05\\\"}\", \"output\": \"0.28591621092291675\", \"metadata_tier\": \"B\", \"metadata_censored\": false, \"metadata_flags\": [], \"metadata_band\": {\"A\": 4, \"B\": 4}, \"metadata_n_prompts\": 32}\n{\"input\": \"{\\\"candidate\\\": \\\"W2\\\", \\\"tag\\\": \\\"F1__a05\\\"}\", \"output\": \"1.0\", \"metadata_tier\": \"B\", \"metadata_censored\": false, \"metadata_flags\": [], \"metadata_band\": {\"A\": 4, \"B\": 4}, \"metadata_n_prompts\": 32}\n{\"input\": \"{\\\"candidate\\\": \\\"W3\\\", \\\"tag\\\": \\\"F1__a05\\\"}\", \"output\": \"1.6497853808181875\", \"metadata_tier\": \"B\", \"metadata_censored\": false, \"metadata_flags\": [], \"metadata_band\": {\"A\": 4, \"B\": 4}, \"metadata_n_prompts\": 32}\n=== full counts ===\nscreen_table 810\nprescreen 15\nrank_analysis 3\nconfirmation 12\ncommissioned_quartet 30\nstability 702\npatching_validation 3\ntransfer_check 60\nnorm_displacement 42\npair_audits 41\na3_domain_profile 147\nquartet_geometry 96\nbars_and_validation 1334\nstability_flags 15", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [22] TOOL CALL — Bash · 2026-09-22 08:10:11 UTC

```
Find prescreen source:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/src && ls && echo "---" && grep -rln "erank\|prescreen\|DROPPED_COLLINEAR" . | head
```

### [23] TOOL RESULT — Bash · 2026-09-22 08:10:11 UTC

```
{"stdout": "ASSETS.md\nSPEC_tail.md\nSPEC_tierA.md\nSPEC_tierB.md\n__pycache__\na3_decomp.py\namend.py\nams_cli_validation.py\nassemble_screen.py\nassets\nbars.py\nbars_partial.py\ncluster_sensitivity.py\nconfirm_cluster_sensitivity.py\nconfirm_harvest_all.py\nconfirm_score.py\ncore.py\nfreeze.py\ninterv.py\njoin.py\npair_audit.py\npanel.py\nprereg.py\nprescreen.py\nquartet.py\nregression_check.py\nrestore_registered_items.py\nreuse\nrowhooks.py\ns5_prepare.py\ns5_run_tierb.py\nstability_flags.py\nstatlib.py\ntierA.py\ntierB.py\nunit_tests.py\nvalidate_bars.py\n---\nunit_tests.py\nprescreen.py\nSPEC_tail.md\nfreeze.py\nstatlib.py\nprereg.py", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [24] TOOL CALL — Bash · 2026-09-22 08:10:13 UTC

```
Read prescreen.py:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/src && wc -l prescreen.py statlib.py && echo "=== prescreen.py ===" && cat prescreen.py
```

### [25] TOOL RESULT — Bash · 2026-09-22 08:10:13 UTC

```
{"stdout": "  447 prescreen.py\n  286 statlib.py\n  733 total\n=== prescreen.py ===\n#!/usr/bin/env python3\n\"\"\"S3: pre-screen (S3.2) + effective-rank (S3.3), run under a hardened open() audit (INV-3).\n\nIts own process. FIRST statement of main() hardens+self-tests core.OpenAudit, THEN installs it\nfor the entire S3.2/S3.3 computation. Only inputs read inside the audited block: prereg.json,\nscreen_table.json (both under --results-dir). Never opens graded_truth / classification /\naggregates / panel_manifest / anything under gen_art_experiment_2 / judge / truth / sealed / heldout.\n\nOutputs (under --results-dir): s3_audit_selftest.json, prescreen.json (chain S3a),\nrank_analysis.json (chain S3b). Audit trail: <logs-dir>/s3_open_audit.txt (+ a separate\ns3_open_audit_selftest.txt for the self-test).\n\nCLI:\n    .venv_gpu/bin/python src/prescreen.py [--results-dir DIR] [--logs-dir DIR] [--force]\n\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport json\nimport sys\nimport tempfile\nfrom pathlib import Path\n\nimport numpy as np\nfrom loguru import logger\n\nWS = Path(__file__).resolve().parents[1]\nsys.path.insert(0, str(WS / \"src\"))\nfrom core import OpenAudit, canonical_json, chain_append, sha256_text, utc_now, write_json  # noqa: E402\nimport statlib  # noqa: E402\n\nlogger.remove()\nlogger.add(sys.stdout, level=\"INFO\", format=\"{time:HH:mm:ss}|{level:<7}|{message}\")\n\nFORBIDDEN = [\"graded_truth\", \"classification\", \"aggregates\", \"panel_manifest\",\n             \"gen_art_experiment_2\", \"judge\", \"truth\", \"sealed\", \"heldout\"]\n\nCANDIDATES = [\"W1\", \"W2\", \"W3\", \"W4\", \"W5\", \"W6\", \"W7\", \"W8\", \"G1\", \"G2\", \"G3\", \"G4\", \"A1\", \"A2\", \"A3\"]\nTIER_A_CANDS = {\"G1\", \"G2\", \"G3\", \"G4\", \"A3\"}  # available from the array-only pass on the full panel\n\n\n# --------------------------------------------------------------------------- #\n# self-test (proves the hardened shim actually blocks pathlib / numpy / open) #\n# --------------------------------------------------------------------------- #\n\n\ndef self_test(logs_dir: Path) -> dict:\n    logs_dir.mkdir(parents=True, exist_ok=True)\n    audit_log = logs_dir / \"s3_open_audit_selftest.txt\"\n    tests = []\n    with tempfile.TemporaryDirectory() as td:\n        tmp = Path(td)\n        planted = tmp / \"graded_truth.json\"\n        planted.write_text(\"{}\")\n        planted_npy = tmp / \"graded_truth_arr.npy\"\n        np.save(planted_npy, np.arange(4))\n        control = tmp / \"not_forbidden.json\"\n        control.write_text(\"{}\")\n\n        with OpenAudit(audit_log, forbidden_substrings=FORBIDDEN) as audit:\n            # 1. pathlib\n            try:\n                Path(planted).read_text()\n                tests.append({\"mechanism\": \"pathlib.Path.read_text\", \"raised_permission_error\": False})\n            except PermissionError:\n                tests.append({\"mechanism\": \"pathlib.Path.read_text\", \"raised_permission_error\": True})\n            # 2. numpy\n            try:\n                np.load(planted_npy)\n                tests.append({\"mechanism\": \"numpy.load\", \"raised_permission_error\": False})\n            except PermissionError:\n                tests.append({\"mechanism\": \"numpy.load\", \"raised_permission_error\": True})\n            # 3. builtins.open\n            try:\n                open(planted)  # noqa: SIM115\n                tests.append({\"mechanism\": \"builtins.open\", \"raised_permission_error\": False})\n            except PermissionError:\n                tests.append({\"mechanism\": \"builtins.open\", \"raised_permission_error\": True})\n            # 4. io.open directly\n            import io as _io\n            try:\n                _io.open(planted)\n                tests.append({\"mechanism\": \"io.open\", \"raised_permission_error\": False})\n            except PermissionError:\n                tests.append({\"mechanism\": \"io.open\", \"raised_permission_error\": True})\n            # 5. os.open (low-level fd)\n            import os as _os\n            try:\n                _os.open(str(planted), _os.O_RDONLY)\n                tests.append({\"mechanism\": \"os.open\", \"raised_permission_error\": False})\n            except PermissionError:\n                tests.append({\"mechanism\": \"os.open\", \"raised_permission_error\": True})\n            # negative control: a NON-forbidden path must still open fine\n            try:\n                txt = control.read_text()\n                tests.append({\"mechanism\": \"negative_control (non-forbidden path)\",\n                               \"opened_ok\": txt == \"{}\"})\n            except Exception as exc:  # noqa: BLE001\n                tests.append({\"mechanism\": \"negative_control (non-forbidden path)\",\n                               \"opened_ok\": False, \"error\": repr(exc)})\n            violations_seen = list(audit.violations)\n            records_seen = list(audit.records)\n\n    all_blocked = all(t.get(\"raised_permission_error\", False) for t in tests if \"raised_permission_error\" in t)\n    control_ok = next((t[\"opened_ok\"] for t in tests if t[\"mechanism\"].startswith(\"negative_control\")), False)\n    result = {\n        \"utc\": utc_now(),\n        \"tests\": tests,\n        \"n_violations_logged\": len(violations_seen),\n        \"violations_sample\": violations_seen[:5],\n        \"n_records_logged\": len(records_seen),\n        \"all_forbidden_mechanisms_blocked\": bool(all_blocked),\n        \"negative_control_ok\": bool(control_ok),\n        \"PASS\": bool(all_blocked and control_ok),\n        \"audit_log\": str(audit_log),\n    }\n    return result\n\n\n# --------------------------------------------------------------------------- #\n# S3.2 pre-screen                                                              #\n# --------------------------------------------------------------------------- #\n\n\ndef _row_values(rows: list[dict], cand: str, panel: list[str]) -> dict[str, dict]:\n    \"\"\"tag -> {'value':.., 'censored':bool} for a candidate, panel rows only.\"\"\"\n    out = {}\n    for r in rows:\n        if r[\"candidate\"] != cand or r[\"tag\"] not in panel:\n            continue\n        out[r[\"tag\"]] = {\"value\": r[\"value\"], \"censored\": bool(r.get(\"censored\", False))}\n    return out\n\n\ndef _expected_sign(prereg: dict, cand: str) -> str | None:\n    d = prereg.get(\"d_candidates\", {}).get(cand, {})\n    es = d.get(\"expected_sign\", {})\n    hc = es.get(\"HC\")\n    if hc is None:\n        return None\n    hc = str(hc).strip()\n    if hc.startswith(\"-\"):\n        return \"-\"\n    if hc.startswith(\"+\"):\n        return \"+\"\n    return hc[:1] if hc else None\n\n\ndef _sign_stability(rows: list[dict], cand: str, panel: list[str]) -> dict:\n    \"\"\"From screen_table stability draws (when present): fraction of (row, draw) pairs\n    whose sign matches the row's registered value sign.\"\"\"\n    n_agree, n_total = 0, 0\n    for r in rows:\n        if r[\"candidate\"] != cand or r[\"tag\"] not in panel:\n            continue\n        reg = r.get(\"value\")\n        draws = r.get(\"stability\")\n        if reg is None or not isinstance(draws, list) or not draws:\n            continue\n        reg_sign = np.sign(reg)\n        if reg_sign == 0:\n            continue\n        for d in draws:\n            v = d.get(\"value\")\n            if v is None or not np.isfinite(v):\n                continue\n            n_total += 1\n            if np.sign(v) == reg_sign:\n                n_agree += 1\n    if n_total == 0:\n        return {\"sign_agree_frac\": None, \"n_draws\": 0}\n    return {\"sign_agree_frac\": n_agree / n_total, \"n_draws\": n_total}\n\n\ndef run_s3_2(prereg: dict, screen_table: dict) -> dict:\n    panel = list(screen_table.get(\"panel\", []))\n    rows = screen_table.get(\"rows\", [])\n\n    # BL1_easy per tag, from the bars table (bar == \"BL1_easy\").\n    bl1 = {}\n    for b in screen_table.get(\"bars\", []):\n        if b.get(\"bar\") == \"BL1_easy\" and b.get(\"tag\") not in bl1:\n            bl1[b[\"tag\"]] = b.get(\"value\")\n\n    out = {}\n    n_dropped = n_kept = n_not_evaluable = 0\n    for cand in CANDIDATES:\n        vals = _row_values(rows, cand, panel)\n        tags_ordered = [t for t in panel if t in vals]\n        raw = np.array([vals[t][\"value\"] if vals[t][\"value\"] is not None else np.nan for t in tags_ordered], dtype=float)\n        cen = np.array([vals[t][\"censored\"] for t in tags_ordered], dtype=bool)\n        y_raw = np.array([bl1.get(t, np.nan) for t in tags_ordered], dtype=float)\n\n        # censoring rule: winsorise at panel-95th-pct of uncensored values, EXCEPT W2 keeps its\n        # sentinel 7 (never winsorised -- it is a meaningful ceiling code, not an outlier).\n        if cand == \"W2\":\n            wins = raw.copy()\n        else:\n            wins = statlib.winsorise_high(raw, cen) if cen.any() else raw\n\n        sp_w = statlib.spearman(wins, y_raw)\n        n = sp_w[\"n\"]\n\n        def _stat(idx, a=wins, b=y_raw):\n            return statlib.spearman(a[idx], b[idx])[\"rho\"]\n\n        ci = statlib.checkpoint_bootstrap(_stat, len(wins), n_boot=2000,\n                                           seed=prereg[\"operationalisation_seed\"]) if len(wins) >= 5 else \\\n            {\"point\": sp_w[\"rho\"], \"lo\": float(\"nan\"), \"hi\": float(\"nan\"), \"n_boot_ok\": 0, \"excludes_zero\": False}\n\n        # censored-dropped variant\n        keep = ~cen\n        sp_dropped = statlib.spearman(raw[keep], y_raw[keep])\n\n        mde = statlib.rho_mde(n) if n and n > 3 else float(\"nan\")\n        expected = _expected_sign(prereg, cand)\n        stability = _sign_stability(rows, cand, panel)\n\n        evaluable = n >= 3 and np.isfinite(sp_w[\"rho\"])\n        if not evaluable:\n            status = \"NOT_EVALUABLE\"\n            n_not_evaluable += 1\n        elif abs(sp_w[\"rho\"]) >= 0.50:\n            status = \"DROPPED\"\n            n_dropped += 1\n        else:\n            status = \"KEPT\"\n            n_kept += 1\n\n        out[cand] = {\n            \"rho\": sp_w[\"rho\"], \"ci\": {\"lo\": ci[\"lo\"], \"hi\": ci[\"hi\"], \"n_boot_ok\": ci.get(\"n_boot_ok\")},\n            \"n\": n, \"mde\": mde, \"status\": status,\n            \"rho_censored_dropped\": sp_dropped[\"rho\"], \"n_censored_dropped\": sp_dropped[\"n\"],\n            \"n_censored\": int(cen.sum()), \"tier\": \"Tier-A-only\" if cand in TIER_A_CANDS else \"mixed/Tier-B\",\n            \"stable_flags\": stability, \"expected_sign_HC\": expected,\n        }\n\n    return {\n        \"utc\": utc_now(),\n        \"threshold\": 0.50,\n        \"prescreen_rule\": \"|Spearman(candidate, BL1_easy)| over screen-panel rows with both finite >= 0.50 -> DROPPED\",\n        \"candidates\": out,\n        \"n_dropped\": n_dropped, \"n_kept\": n_kept, \"n_not_evaluable\": n_not_evaluable,\n        \"n_panel\": len(panel),\n    }\n\n\n# --------------------------------------------------------------------------- #\n# S3.3 effective rank                                                         #\n# --------------------------------------------------------------------------- #\n\n\ndef _zscore_impute(mat: np.ndarray) -> tuple[np.ndarray, int]:\n    \"\"\"z-score each ROW (candidate) over its finite entries; NaN -> 0 AFTER z-scoring\n    (mean imputation). Returns (matrix, n_imputed).\"\"\"\n    m = mat.copy()\n    n_imputed = 0\n    for i in range(m.shape[0]):\n        row = m[i]\n        finite = np.isfinite(row)\n        if finite.sum() >= 2:\n            mu = row[finite].mean()\n            sd = row[finite].std(ddof=0) or 1.0\n            m[i] = (row - mu) / sd\n        else:\n            m[i] = 0.0\n        bad = ~np.isfinite(m[i])\n        n_imputed += int(bad.sum())\n        m[i, bad] = 0.0\n    return m, n_imputed\n\n\ndef _partial_out_bl1(mat_z: np.ndarray, y_z: np.ndarray) -> np.ndarray:\n    \"\"\"Replace each row by its OLS residual on z(BL1_easy) (with intercept).\"\"\"\n    out = np.zeros_like(mat_z)\n    design = np.column_stack([np.ones_like(y_z), y_z])\n    for i in range(mat_z.shape[0]):\n        beta, *_ = np.linalg.lstsq(design, mat_z[i], rcond=None)\n        out[i] = mat_z[i] - design @ beta\n    return out\n\n\ndef _build_matrix(rows: list[dict], cands: list[str], tags: list[str]) -> np.ndarray:\n    idx = {(r[\"tag\"], r[\"candidate\"]): r[\"value\"] for r in rows}\n    m = np.full((len(cands), len(tags)), np.nan, dtype=float)\n    for i, c in enumerate(cands):\n        for j, t in enumerate(tags):\n            v = idx.get((t, c))\n            if v is not None:\n                m[i, j] = v\n    return m\n\n\ndef _spearman_matrix(mat_raw: np.ndarray, cands: list[str]) -> dict:\n    n = len(cands)\n    out = {}\n    for i in range(n):\n        for j in range(n):\n            r = statlib.spearman(mat_raw[i], mat_raw[j])\n            out[f\"{cands[i]}|{cands[j]}\"] = r[\"rho\"]\n    return out\n\n\ndef _rank_block(rows: list[dict], cands: list[str], tags: list[str], bl1_by_tag: dict) -> dict:\n    mat_raw = _build_matrix(rows, cands, tags)\n    mat_z, n_imputed = _zscore_impute(mat_raw)\n    y_raw = np.array([bl1_by_tag.get(t, np.nan) for t in tags], dtype=float)\n    y_finite = np.isfinite(y_raw)\n    y_z = np.zeros_like(y_raw)\n    if y_finite.sum() >= 2:\n        mu, sd = y_raw[y_finite].mean(), (y_raw[y_finite].std(ddof=0) or 1.0)\n        y_z[y_finite] = (y_raw[y_finite] - mu) / sd\n    # y NaNs -> 0 too (same imputation convention)\n\n    full = statlib.erank(mat_z)\n    mat_partial = _partial_out_bl1(mat_z, y_z)\n    partial = statlib.erank(mat_partial)\n\n    # leading right singular vector (checkpoint loadings) -> |cos| with z(BL1_easy)\n    if mat_z.shape[0] >= 2 and mat_z.shape[1] >= 2:\n        _u, _s, vt = np.linalg.svd(mat_z, full_matrices=False)\n        v1 = vt[0]\n        denom = (np.linalg.norm(v1) * np.linalg.norm(y_z)) or 1.0\n        cos_ckpt_bl1 = abs(float(np.dot(v1, y_z) / denom)) if denom else float(\"nan\")\n    else:\n        cos_ckpt_bl1 = float(\"nan\")\n\n    return {\n        \"n_candidates\": len(cands), \"n_checkpoints\": len(tags), \"n_imputed\": n_imputed,\n        \"candidates\": cands, \"checkpoints\": tags,\n        \"erank_full\": {\"erank_entropy\": full[\"erank_entropy\"], \"erank_participation\": full[\"erank_participation\"],\n                        \"singular_values\": full[\"singular_values\"], \"leading_left_loadings\": full[\"leading_left\"]},\n        \"erank_partial_BL1\": {\"erank_entropy\": partial[\"erank_entropy\"],\n                               \"erank_participation\": partial[\"erank_participation\"],\n                               \"singular_values\": partial[\"singular_values\"],\n                               \"leading_left_loadings\": partial[\"leading_left\"]},\n        \"leading_eigenvector_loading_pattern\": dict(zip(cands, full[\"leading_left\"])) if full[\"leading_left\"] else {},\n        \"abs_cos_leading_right_singvec_vs_zBL1\": cos_ckpt_bl1,\n        \"spearman_matrix\": _spearman_matrix(mat_raw, cands),\n    }\n\n\ndef run_s3_3(prereg: dict, screen_table: dict) -> dict:\n    panel = list(screen_table.get(\"panel\", []))\n    rows = screen_table.get(\"rows\", [])\n    bl1 = {}\n    for b in screen_table.get(\"bars\", []):\n        if b.get(\"bar\") == \"BL1_easy\" and b.get(\"tag\") not in bl1:\n            bl1[b[\"tag\"]] = b.get(\"value\")\n\n    full_panel_block = _rank_block(rows, CANDIDATES, panel, bl1)\n\n    tierA_block = _rank_block(rows, sorted(TIER_A_CANDS), panel, bl1)\n\n    # complete-Tier-B-coverage: checkpoints where EVERY candidate (incl. Tier-B) is finite\n    idx = {(r[\"tag\"], r[\"candidate\"]): r[\"value\"] for r in rows}\n    complete_tags = [t for t in panel\n                     if all(idx.get((t, c)) is not None and np.isfinite(idx[(t, c)]) for c in CANDIDATES)]\n    if len(complete_tags) >= 2:\n        complete_block = _rank_block(rows, CANDIDATES, complete_tags, bl1)\n    else:\n        complete_block = {\"note\": f\"only {len(complete_tags)} checkpoints have complete Tier-B coverage \"\n                                   f\"(need >=2 for SVD); block skipped\", \"n_checkpoints\": len(complete_tags)}\n\n    ent = full_panel_block[\"erank_full\"][\"erank_entropy\"]\n    cos = full_panel_block[\"abs_cos_leading_right_singvec_vs_zBL1\"]\n    if np.isfinite(ent) and np.isfinite(cos) and ent <= 1.5 and cos >= 0.8:\n        verdict = \"P1-consistent: one coordinate, BL1-aligned\"\n    elif np.isfinite(ent) and np.isfinite(cos):\n        verdict = (f\"P1 NOT supported by the rank structure: erank_entropy={ent:.3f} \"\n                   f\"(threshold <=1.5), |cos(leading ckpt singvec, z(BL1_easy))|={cos:.3f} (threshold >=0.8)\")\n    else:\n        verdict = \"erank/cos not computable (insufficient finite data)\"\n\n    return {\n        \"utc\": utc_now(),\n        \"full_panel_all_candidates\": full_panel_block,\n        \"tier_A_only_full_panel\": tierA_block,\n        \"complete_tierB_coverage\": complete_block,\n        \"verdict\": verdict,\n    }\n\n\n# --------------------------------------------------------------------------- #\n# main                                                                        #\n# --------------------------------------------------------------------------- #\n\n\n@logger.catch(reraise=True)\ndef main() -> None:\n    ap = argparse.ArgumentParser()\n    ap.add_argument(\"--results-dir\", type=Path, default=WS / \"results\")\n    ap.add_argument(\"--logs-dir\", type=Path, default=WS / \"logs\")\n    ap.add_argument(\"--force\", action=\"store_true\")\n    args = ap.parse_args()\n\n    results_dir = args.results_dir.resolve()\n    logs_dir = args.logs_dir.resolve()\n    logs_dir.mkdir(parents=True, exist_ok=True)\n    logger.add(logs_dir / \"prescreen.log\", rotation=\"10 MB\", level=\"DEBUG\")\n\n    # FIRST statement of business: harden + self-test the shim before trusting it.\n    logger.info(\"running OpenAudit self-test (pathlib / numpy / builtins.open / io.open / os.open)\")\n    st = self_test(logs_dir)\n    st_path = results_dir / \"s3_audit_selftest.json\"\n    st_path.parent.mkdir(parents=True, exist_ok=True)\n    st_path.write_text(json.dumps(st, indent=1))\n    logger.info(f\"self-test PASS={st['PASS']} -> {st_path}\")\n    if not st[\"PASS\"]:\n        raise SystemExit(\"OpenAudit self-test FAILED -- refusing to run S3 with an unproven audit shim\")\n\n    for name in (\"prescreen.json\", \"rank_analysis.json\"):\n        p = results_dir / name\n        if p.exists() and not args.force:\n            raise SystemExit(f\"refusing to overwrite existing {p} (pass --force)\")\n\n    audit_log = logs_dir / \"s3_open_audit.txt\"\n    with OpenAudit(audit_log, forbidden_substrings=FORBIDDEN) as audit:\n        prereg = json.loads((results_dir / \"prereg.json\").read_text())\n        screen_table = json.loads((results_dir / \"screen_table.json\").read_text())\n        prereg[\"operationalisation_seed\"] = prereg.get(\"f_selection_rule_verbatim\", {}) \\\n            .get(\"operationalisation\", {}).get(\"bootstrap\", {}).get(\"seed\", 20260922)\n\n        logger.info(f\"S3.2 pre-screen over {len(screen_table.get('panel', []))} panel rows\")\n        prescreen_result = run_s3_2(prereg, screen_table)\n        logger.info(f\"S3.2: dropped={prescreen_result['n_dropped']} kept={prescreen_result['n_kept']} \"\n                    f\"not_evaluable={prescreen_result['n_not_evaluable']}\")\n\n        logger.info(\"S3.3 effective rank\")\n        rank_result = run_s3_3(prereg, screen_table)\n        logger.info(f\"S3.3 verdict: {rank_result['verdict']}\")\n\n        digest1 = write_json(results_dir / \"prescreen.json\", prescreen_result)\n        rec1 = chain_append(results_dir / \"hashchain.jsonl\", \"S3a\", results_dir / \"prescreen.json\", digest1)\n        digest2 = write_json(results_dir / \"rank_analysis.json\", rank_result)\n        rec2 = chain_append(results_dir / \"hashchain.jsonl\", \"S3b\", results_dir / \"rank_analysis.json\", digest2)\n        logger.info(f\"wrote prescreen.json {digest1[:16]} chain={rec1['stage']}\")\n        logger.info(f\"wrote rank_analysis.json {digest2[:16]} chain={rec2['stage']}\")\n\n    if audit.violations:\n        raise SystemExit(f\"INV-3 VIOLATION during S3 main pass: {audit.violations}\")\n    logger.info(f\"S3 open-audit clean: {len(audit.records)} opens recorded, 0 violations -> {audit_log}\")\n\n\nif __name__ == \"__main__\":\n    main()", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [26] TOOL CALL — Bash · 2026-09-22 08:10:21 UTC

```
Inspect screen_table.json:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/results && ls -la *.json | head -30 && python3 -c "
import json
d=json.load(open('screen_table.json'))
print(list(d.keys()))
print('panel',len(d['panel']), d['panel'][:6])
print('rows',len(d['rows']))
print('row0', json.dumps(d['rows'][0])[:600])
print('bars',len(d.get('bars',[])), json.dumps(d['bars'][0])[:300])
import collections
print(collections.Counter(b['bar'] for b in d['bars']))
"
```

### [27] TOOL CALL — Bash · 2026-09-22 08:10:21 UTC

```
Outline statlib:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/src && grep -n "^def \|^EPS\|^import\|^from" statlib.py
```

### [28] TOOL RESULT — Bash · 2026-09-22 08:10:21 UTC

```
{"stdout": "-rw-rw-rw- 1 root root   29007 Sep 22 00:45 asset_inventory.json\n-rw-rw-rw- 1 root root    2247 Sep 22 00:46 bars_validation.json\n-rw-rw-rw- 1 root root    1328 Sep 22 04:37 chain_verification_final.json\n-rw-rw-rw- 1 root root    4932 Sep 22 03:06 cluster_sensitivity.json\n-rw-rw-rw- 1 root root    4144 Sep 22 04:35 confirm_bar_comparison.json\n-rw-rw-rw- 1 root root    7652 Sep 22 04:34 confirm_cluster_sensitivity.json\n-rw-rw-rw- 1 root root    4839 Sep 22 04:35 confirm_headlines.json\n-rw-rw-rw- 1 root root   33127 Sep 22 04:33 confirmation.json\n-rw-rw-rw- 1 root root    5469 Sep 22 00:45 deviations.json\n-rw-rw-rw- 1 root root    8550 Sep 22 04:19 deviations_confirmfix.json\n-rw-rw-rw- 1 root root    7052 Sep 22 04:39 deviations_orchestrator.json\n-rw-rw-rw- 1 root root    1738 Sep 22 03:06 order_proof.json\n-rw-rw-rw- 1 root root   47026 Sep 22 04:05 pair_audit.json\n-rw-rw-rw- 1 root root      81 Sep 22 04:05 pair_audit_selftest.json\n-rw-rw-rw- 1 root root   15647 Sep 22 00:50 panel.json\n-rw-rw-rw- 1 root root   35813 Sep 22 00:49 prereg.json\n-rw-rw-rw- 1 root root    7018 Sep 22 04:32 prereg_amendments.json\n-rw-rw-rw- 1 root root    2781 Sep 22 01:55 prereg_amendments_b1.json\n-rw-rw-rw- 1 root root    1853 Sep 22 01:55 prereg_amendments_b2.json\n-rw-rw-rw- 1 root root    1290 Sep 22 02:55 prereg_amendments_b3.json\n-rw-rw-rw- 1 root root    1342 Sep 22 04:32 prereg_amendments_b4.json\n-rw-rw-rw- 1 root root    6886 Sep 22 03:06 prescreen.json\n-rw-rw-rw- 1 root root    9643 Sep 22 01:44 proposed_amendments_tail.json\n-rw-rw-rw- 1 root root   25288 Sep 22 03:06 rank_analysis.json\n-rw-rw-rw- 1 root root    4311 Sep 22 03:50 registered_items_restore_log.json\n-rw-rw-rw- 1 root root    8711 Sep 22 00:48 regression_check.json\n-rw-rw-rw- 1 root root    1037 Sep 22 03:06 s3_audit_selftest.json\n-rw-rw-rw- 1 root root    6010 Sep 22 03:35 screen_headlines.json\n-rw-rw-rw- 1 root root 1130775 Sep 22 03:06 screen_table.json\n-rw-rw-rw- 1 root root  117529 Sep 22 03:06 stability_flags.json\n['utc', 'panel', 'blocks', 'rows', 'bars', 'subcolumns', 'a1_joint_loading', 'coverage', 'n_tierA_files', 'n_tierB_files', 'n_tierB_ok']\npanel 48 ['F1__a05', 'F1__a10', 'F1__cautious', 'F1__dpo', 'F1__fp16', 'F1__int8bnb']\nrows 810\nrow0 {\"tag\": \"F1__a05\", \"candidate\": \"W1\", \"value\": 0.28591621092291675, \"tier\": \"B\", \"censored\": false, \"flags\": [], \"band\": {\"A\": 4, \"B\": 4}, \"n_prompts\": 32, \"k_curve\": {\"0\": \"N/A\", \"4\": \"N/A\", \"8\": \"N/A\", \"16\": \"N/A\", \"32\": 0.28591621092291675, \"pool\": \"N/A\"}, \"stability\": [{\"prompt_draw\": 0, \"fold_seed\": 1, \"band_offset\": 0, \"value\": -0.08056770507681119}, {\"prompt_draw\": 0, \"fold_seed\": 2, \"band_offset\": 0, \"value\": 0.03750861395349307}, {\"prompt_draw\": 1, \"fold_seed\": 1, \"band_offset\": 0, \"value\": 0.5854709834507157}, {\"prompt_draw\": 1, \"fold_seed\": 2, \"band_offset\": 0, \"value\": 0.7871896772\nbars 1302 {\"tag\": \"F1__a05\", \"bar\": \"BL1_easy\", \"value\": -0.8151386181513467, \"meta\": {\"array\": \"r_refusal - r_control @ hidden-state index L (final layer)\", \"layer\": \"L=28\", \"prompt_set\": \"EASY n=96 (48 advbench-harmful vs 48 dolly-benign)\"}}\nCounter({'BL1_easy': 54, 'BL1_hard': 54, 'BL1_truelogit': 54, 'BL1_truelogit_hard': 54, 'N1': 54, 'N1_l_star': 54, 'N6': 54, 'C7': 54, 'C13_peak_d': 54, 'C13_peak_f': 54, 'N11': 54, 'plain_diffmeans': 54, 'B7_nullproj': 54, 'AMS_T1_sigma': 54, 'prompting_ceiling.d': 42, 'prompting_ceiling.auroc': 42, 'prompting_ceiling.rule': 42, 'AMS_T1_b1': 42, 'AMS_T1_b8_emulated': 42, 'per_concept_b1.harmful_content': 42, 'per_concept_b1.injection_resistance': 42, 'per_concept_b1.refusal_capability': 42, 'per_concept_b8.harmful_content': 42, 'per_concept_b8.injection_resistance': 42, 'per_concept_b8.refusal_capability': 42, 'padding_side_default': 42, 'b1_vs_stored_A_ams_median_rel_err': 42})", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [29] TOOL RESULT — Bash · 2026-09-22 08:10:21 UTC

```
{"stdout": "19:from __future__ import annotations\n21:import math\n22:from typing import Callable, Sequence\n24:import numpy as np\n31:def _rankdata(a: np.ndarray) -> np.ndarray:\n49:def _pearson(x: np.ndarray, y: np.ndarray) -> float:\n62:def _finite_pair(x: Sequence[float], y: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:\n69:def spearman(x: Sequence[float], y: Sequence[float]) -> dict:\n78:def partial_spearman(\n113:def checkpoint_bootstrap(\n156:def paired_margin_ci(\n194:def _binom_pmf(k: int, n: int, p: float = 0.5) -> float:\n198:def mcnemar_exact(b: int, c: int) -> dict:\n219:def erank(matrix: np.ndarray) -> dict:\n254:def rho_mde(n: int) -> float:\n264:def mde_table(ns: Sequence[int] = (8, 10, 12, 15, 20, 25, 30, 40, 50)) -> dict:\n273:def winsorise_high(values: Sequence[float], censored: Sequence[bool]) -> np.ndarray:", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [30] ASSISTANT · 2026-09-22 08:10:35 UTC

```
Now building the demo data file.
```

### [31] TOOL CALL — Bash · 2026-09-22 08:10:35 UTC

```
Build mini_demo_data.json:
cat > /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--3-gen-demo-art-notebook-workspaces-iter-5-art-l3WSWrVMeJZU/4199f3f8-bef6-4e67-a967-eef1820c455e/scratchpad/build_mini.py <<'EOF'
import json, pathlib
RES = pathlib.Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/results")
OUT = pathlib.Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU/mini_demo_data.json")
st = json.loads((RES/"screen_table.json").read_text())
prereg = json.loads((RES/"prereg.json").read_text())

CANDS = ["G1","G2","W6","W8","W3","G4","G3","A3"]   # 4 known collinear + 4 kept
panel = st["panel"]
rows = st["rows"]
bl1 = {}
for b in st["bars"]:
    if b.get("bar")=="BL1_easy" and b["tag"] not in bl1:
        bl1[b["tag"]] = b.get("value")
idx = {(r["tag"], r["candidate"]): r for r in rows}
# pick checkpoints where all 8 candidates are present with finite values and BL1_easy exists
import math
def ok(t):
    if bl1.get(t) is None or not math.isfinite(bl1[t]): return False
    for c in CANDS:
        r = idx.get((t,c))
        if r is None or r.get("value") is None or not math.isfinite(r["value"]): return False
    return True
tags = [t for t in panel if ok(t)][:12]
print("tags", len(tags), tags)

MAXDRAWS = 8
examples = []
for t in tags:
    for c in CANDS:
        r = idx[(t,c)]
        stab = r.get("stability") or []
        examples.append({
            "input": json.dumps({"candidate": c, "tag": t}, sort_keys=True),
            "output": str(r.get("value")),
            "metadata_tier": r.get("tier"),
            "metadata_censored": r.get("censored"),
            "metadata_flags": r.get("flags"),
            "metadata_band": r.get("band"),
            "metadata_n_prompts": r.get("n_prompts"),
            "metadata_stability": stab[:MAXDRAWS],
        })
print("n examples", len(examples))
exp = {}
for c in CANDS:
    d = prereg.get("d_candidates", {}).get(c, {})
    exp[c] = d.get("expected_sign", {})
seed = prereg.get("f_selection_rule_verbatim", {}).get("operationalisation", {}).get("bootstrap", {}).get("seed", 20260922)
out = {
  "dataset": "screen_table",
  "description": ("Curated subset of the iteration-5 wide-screen table: 8 of the 15 registered "
                  "second-order activation readouts on 12 of the 48 graded panel checkpoints, plus the "
                  "incumbent final-layer logit-gap bar (BL1_easy) for the same checkpoints."),
  "source": "results/screen_table.json + results/prereg.json (gen_art_experiment_1, iteration 5)",
  "candidates": CANDS,
  "panel": tags,
  "examples": examples,
  "support": {
      "bars_BL1_easy": {t: bl1[t] for t in tags},
      "prereg_expected_sign": exp,
      "operationalisation_seed": seed,
      "bar_meta": next(b["meta"] for b in st["bars"] if b.get("bar")=="BL1_easy"),
  },
}
OUT.write_text(json.dumps(out, indent=1))
print("wrote", OUT, OUT.stat().st_size)
EOF
python3 /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--3-gen-demo-art-notebook-workspaces-iter-5-art-l3WSWrVMeJZU/4199f3f8-bef6-4e67-a967-eef1820c455e/scratchpad/build_mini.py
```

### [32] TOOL RESULT — Bash · 2026-09-22 08:10:35 UTC

```
{"stdout": "tags 12 ['F1__a05', 'F1__a10', 'F1__cautious', 'F1__fp16', 'F1__int8bnb', 'F1__int8wo', 'F1__ref', 'F1__sysprompt', 'F1__wu05', 'F1__wu20', 'F2__a05', 'F2__a10']\nn examples 96\nwrote /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU/mini_demo_data.json 77553", "stderr": "", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [33] TOOL CALL — Bash · 2026-09-22 08:10:37 UTC

```
Show panel tags:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/results && python3 -c "
import json;d=json.load(open('screen_table.json'));print(d['panel'])"
```

### [34] TOOL RESULT — Bash · 2026-09-22 08:10:37 UTC

```
{"stdout": "['F1__a05', 'F1__a10', 'F1__cautious', 'F1__dpo', 'F1__fp16', 'F1__int8bnb', 'F1__int8wo', 'F1__lora', 'F1__ref', 'F1__sysprompt', 'F1__wu05', 'F1__wu20', 'F2__a05', 'F2__a10', 'F2__cautious', 'F2__dpo', 'F2__fp16', 'F2__int8bnb', 'F2__int8wo', 'F2__lora', 'F2__ref', 'F2__sysprompt', 'F2__wu05', 'F2__wu20', 'F3__a05', 'F3__a10', 'F3__cautious', 'F3__dpo', 'F3__fp16', 'F3__int8bnb', 'F3__int8wo', 'F3__lora', 'F3__ref', 'F3__sysprompt', 'F3__wu05', 'F3__wu20', 'HG__Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3', 'HG__Qwen--Qwen2.5-1.5B-Instruct', 'HG__Qwen--Qwen3-1.7B', 'HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct', 'HG__Vikhrmodels--Vikhr-Llama-3.2-1B-Instruct-abliterated', 'HG__amd--AMD-OLMo-1B', 'HG__amd--AMD-OLMo-1B-SFT', 'HG__amd--AMD-OLMo-1B-SFT-DPO', 'HG__huihui-ai--Huihui-Qwen3-0.6B-abliterated-v2', 'HG__huihui-ai--Huihui-Qwen3-1.7B-abliterated-v2', 'HG__mylesgoose--Llama-3.2-1B-Instruct-abliterated2', 'HG__tiiuae--Falcon3-1B-Base']", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [35] TOOL CALL — Bash · 2026-09-22 08:10:41 UTC

```
Rebuild mini data with family spread:
SP=/tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--3-gen-demo-art-notebook-workspaces-iter-5-art-l3WSWrVMeJZU/4199f3f8-bef6-4e67-a967-eef1820c455e/scratchpad/build_mini.py
python3 - <<'EOF'
import re,pathlib
p=pathlib.Path("/tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--3-gen-demo-art-notebook-workspaces-iter-5-art-l3WSWrVMeJZU/4199f3f8-bef6-4e67-a967-eef1820c455e/scratchpad/build_mini.py")
s=p.read_text()
s=s.replace('tags = [t for t in panel if ok(t)][:12]', '''elig = [t for t in panel if ok(t)]
# spread the 12 demo checkpoints across families (F1/F2/F3 in-house edit arms + HG hub lineages)
from collections import defaultdict
byfam = defaultdict(list)
for t in elig:
    byfam[t.split("__")[0]].append(t)
tags, i = [], 0
while len(tags) < 12 and any(len(v) > i for v in byfam.values()):
    for fam in sorted(byfam):
        if len(byfam[fam]) > i and len(tags) < 12:
            tags.append(byfam[fam][i])
    i += 1
tags = [t for t in panel if t in tags]''')
p.write_text(s)
EOF
python3 $SP
```

### [36] TOOL RESULT — Bash · 2026-09-22 08:10:41 UTC

```
{"stdout": "tags 12 ['F1__a05', 'F1__a10', 'F1__cautious', 'F2__a05', 'F2__a10', 'F2__cautious', 'F3__a05', 'F3__a10', 'F3__cautious', 'HG__Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3', 'HG__Qwen--Qwen2.5-1.5B-Instruct', 'HG__Qwen--Qwen3-1.7B']\nn examples 96\nwrote /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU/mini_demo_data.json 74815", "stderr": "", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [37] TOOL CALL — Bash · 2026-09-22 08:10:43 UTC

```
Extract statlib functions:
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_5/gen_art/gen_art_experiment_1/src && sed -n '26,80p;113,156p;219,286p' statlib.py
```

### [38] TOOL RESULT — Bash · 2026-09-22 08:10:43 UTC

```
{"stdout": "# --------------------------------------------------------------------------- #\n# ranks                                                                        #\n# --------------------------------------------------------------------------- #\n\n\ndef _rankdata(a: np.ndarray) -> np.ndarray:\n    \"\"\"Average-rank transform (identical to scipy.stats.rankdata method='average').\"\"\"\n    a = np.asarray(a, dtype=float)\n    n = a.size\n    order = np.argsort(a, kind=\"mergesort\")\n    ranks = np.empty(n, dtype=float)\n    sa = a[order]\n    i = 0\n    while i < n:\n        j = i\n        while j + 1 < n and sa[j + 1] == sa[i]:\n            j += 1\n        avg = 0.5 * (i + j) + 1.0\n        ranks[order[i : j + 1]] = avg\n        i = j + 1\n    return ranks\n\n\ndef _pearson(x: np.ndarray, y: np.ndarray) -> float:\n    x = np.asarray(x, dtype=float)\n    y = np.asarray(y, dtype=float)\n    if x.size < 3:\n        return float(\"nan\")\n    xc = x - x.mean()\n    yc = y - y.mean()\n    den = math.sqrt(float(xc @ xc) * float(yc @ yc))\n    if den <= 0.0:\n        return float(\"nan\")\n    return float((xc @ yc) / den)\n\n\ndef _finite_pair(x: Sequence[float], y: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:\n    x = np.asarray(x, dtype=float)\n    y = np.asarray(y, dtype=float)\n    m = np.isfinite(x) & np.isfinite(y)\n    return x[m], y[m]\n\n\ndef spearman(x: Sequence[float], y: Sequence[float]) -> dict:\n    \"\"\"Spearman rho with pairwise deletion. Returns {rho, n}.\"\"\"\n    xf, yf = _finite_pair(x, y)\n    n = int(xf.size)\n    if n < 3:\n        return {\"rho\": float(\"nan\"), \"n\": n}\n    return {\"rho\": _pearson(_rankdata(xf), _rankdata(yf)), \"n\": n}\n\n\ndef partial_spearman(\n    x: Sequence[float], y: Sequence[float], controls: Sequence[Sequence[float]]\n) -> dict:\ndef checkpoint_bootstrap(\n    stat_fn: Callable[[np.ndarray], float],\n    n_items: int,\n    *,\n    n_boot: int = 2000,\n    seed: int = 20260921,\n    alpha: float = 0.05,\n) -> dict:\n    \"\"\"Percentile bootstrap over CHECKPOINT indices.\n\n    `stat_fn` receives an index array (with replacement) and returns a scalar.\n    Every statistic in this artifact is computed on the SAME resampled index\n    vector, which is what makes the margins paired.\n    \"\"\"\n    rng = np.random.default_rng(seed)\n    point = float(stat_fn(np.arange(n_items)))\n    draws = np.empty(n_boot, dtype=float)\n    for b in range(n_boot):\n        idx = rng.integers(0, n_items, size=n_items)\n        try:\n            draws[b] = float(stat_fn(idx))\n        except (ValueError, ZeroDivisionError, np.linalg.LinAlgError):\n            draws[b] = np.nan\n    good = draws[np.isfinite(draws)]\n    if good.size < 50:\n        return {\n            \"point\": point,\n            \"lo\": float(\"nan\"),\n            \"hi\": float(\"nan\"),\n            \"n_boot_ok\": int(good.size),\n            \"excludes_zero\": False,\n        }\n    lo = float(np.quantile(good, alpha / 2.0))\n    hi = float(np.quantile(good, 1.0 - alpha / 2.0))\n    return {\n        \"point\": point,\n        \"lo\": lo,\n        \"hi\": hi,\n        \"n_boot_ok\": int(good.size),\n        \"excludes_zero\": bool((lo > 0.0) or (hi < 0.0)),\n    }\n\n\ndef paired_margin_ci(\ndef erank(matrix: np.ndarray) -> dict:\n    \"\"\"Effective rank of a (candidates x checkpoints) matrix.\n\n    Returns both the entropy variant exp(-sum p log p) and the participation\n    ratio (sum s^2)^2 / sum s^4, plus the singular-value spectrum and the\n    leading right/left singular vectors.\n    \"\"\"\n    m = np.asarray(matrix, dtype=float)\n    if m.ndim != 2 or min(m.shape) < 2:\n        return {\"erank_entropy\": float(\"nan\"), \"erank_participation\": float(\"nan\"),\n                \"singular_values\": [], \"explained\": [], \"leading_left\": []}\n    u, s, _vt = np.linalg.svd(m, full_matrices=False)\n    s2 = s**2\n    tot = float(s2.sum())\n    if tot <= 0.0:\n        return {\"erank_entropy\": float(\"nan\"), \"erank_participation\": float(\"nan\"),\n                \"singular_values\": s.tolist(), \"explained\": [], \"leading_left\": []}\n    p = s2 / tot\n    nz = p[p > 1e-15]\n    ent = float(np.exp(-float(np.sum(nz * np.log(nz)))))\n    part = float((tot**2) / float(np.sum(s2**2)))\n    return {\n        \"erank_entropy\": ent,\n        \"erank_participation\": part,\n        \"singular_values\": s.tolist(),\n        \"explained\": p.tolist(),\n        \"leading_left\": u[:, 0].tolist(),\n    }\n\n\n# --------------------------------------------------------------------------- #\n# power                                                                        #\n# --------------------------------------------------------------------------- #\n\n\ndef rho_mde(n: int) -> float:\n    \"\"\"Minimum detectable Spearman rho, two-sided alpha=0.05, power 0.80.\n\n    rho_MDE = tanh(2.80 / sqrt(n - 3))   (Fisher-z, z_{.975}+z_{.80} = 2.80)\n    \"\"\"\n    if n is None or n <= 3:\n        return float(\"nan\")\n    return float(math.tanh(2.80 / math.sqrt(n - 3.0)))\n\n\ndef mde_table(ns: Sequence[int] = (8, 10, 12, 15, 20, 25, 30, 40, 50)) -> dict:\n    return {str(int(n)): rho_mde(int(n)) for n in ns}\n\n\n# --------------------------------------------------------------------------- #\n# censoring guard                                                              #\n# --------------------------------------------------------------------------- #\n\n\ndef winsorise_high(values: Sequence[float], censored: Sequence[bool]) -> np.ndarray:\n    \"\"\"Replace CENSORED_HIGH cells with the panel's 95th percentile of the\n    uncensored finite values. Returns a new array; never mutates the input.\"\"\"\n    v = np.asarray(values, dtype=float).copy()\n    cen = np.asarray(censored, dtype=bool)\n    ok = np.isfinite(v) & (~cen)\n    if ok.sum() >= 3:\n        cap = float(np.quantile(v[ok], 0.95))\n    elif ok.sum() > 0:\n        cap = float(np.nanmax(v[ok]))\n    else:\n        return v\n    v[cen] = cap\n    return v", "stderr": "\nShell cwd was reset to /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [39] TOOL CALL — Bash · 2026-09-22 08:11:36 UTC

```
Generate notebook:
mkdir -p /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--3-gen-demo-art-notebook-workspaces-iter-5-art-l3WSWrVMeJZU/4199f3f8-bef6-4e67-a967-eef1820c455e/scratchpad && cat > /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--3-gen-demo-art-notebook-workspaces-iter-5-art-l3WSWrVMeJZU/4199f3f8-bef6-4e67-a967-eef1820c455e/scratchpad/gen_nb.py <<'PYEOF'
import json, pathlib

WS = pathlib.Path("/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU")
cells = []
def md(s): cells.append({"cell_type":"markdown","metadata":{},"source":s.rstrip("\n").split("\n")})
def code(s):
    src = s.rstrip("\n").split("\n")
    cells.append({"cell_type":"code","execution_count":None,"metadata":{},"outputs":[],"source":[l+"\n" for l in src[:-1]]+[src[-1]]})

md(r"""# Wide screen of 15 second-order safety readouts — demo

**Artifact:** pre-registered wide screen + one-shot blind confirmation of second-order *activation*
readouts for safety, scored against the incumbent **final-layer logit gap** (`BL1_easy`).

The full artifact registers 15 single-model activation candidates (W1–W8 write-handle/redundancy,
G1–G4 dimensionless geometry, A1–A3 competing mechanisms), measures each on a 48-checkpoint graded
panel, then runs

1. **S3.2 pre-screen** — a candidate whose Spearman correlation with the incumbent logit gap is
   `|rho| >= 0.50` across the panel is *collinear with the bar* and is DROPPED before any outcome is
   looked at (in the real run: G2 +0.745, G1 −0.713, W8 +0.615, W6 +0.554 dropped, 11 kept);
2. **S3.3 effective rank** — is the whole candidate family really one coordinate (hypothesis P1)?
   In the real run it is not: `erank_entropy = 7.16` and `|cos(leading checkpoint singular vector,
   z(BL1_easy))| = 0.645`, so P1 is NOT supported;
3. **S6 assembly** (`method.py`) — every stage is folded into the `exp_gen_sol_out` document.

This notebook runs exactly those three stages, with the original code from `src/statlib.py`,
`src/prescreen.py` and `method.py`, on a curated 8-candidate × 12-checkpoint slice of the real
screen table. Nothing is re-measured from model weights here — the activation readouts were computed
on GPU in the artifact; the demo replays the statistics stage on their stored values.""")

code(r"""import subprocess, sys
def _pip(*a): subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-q', *a])

# numpy, matplotlib — pre-installed on Colab, install locally to match Colab's versions
if 'google.colab' not in sys.modules:
    _pip('numpy==2.0.2', 'matplotlib==3.10.0')""")

md("""## Imports

The original modules import only the standard library plus NumPy (`statlib.py` deliberately
reimplements `rankdata`/Spearman so the screen has no SciPy dependency). `matplotlib` is added
for the summary figures at the end.""")

code(r"""from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import matplotlib.pyplot as plt""")

md("""## Data loading

`mini_demo_data.json` is the curated subset of `results/screen_table.json`: 96 measured cells
(8 candidates × 12 panel checkpoints), the incumbent `BL1_easy` bar value for each checkpoint, the
pre-registered expected signs, and the bootstrap seed.""")

code(r'''GITHUB_DATA_URL = "https://raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-5/experiment-1/demo/mini_demo_data.json"

def load_data():
    try:
        import urllib.request
        with urllib.request.urlopen(GITHUB_DATA_URL) as response:
            return json.loads(response.read().decode())
    except Exception: pass
    local = Path("mini_demo_data.json")
    if local.exists(): return json.loads(local.read_text())
    raise FileNotFoundError("Could not load mini_demo_data.json")''')

code(r"""data = load_data()

print(data["description"])
print()
print("candidates :", data["candidates"])
print("checkpoints:", len(data["panel"]))
for t in data["panel"]:
    print("   ", t)
print("cells      :", len(data["examples"]))
print("bar meta   :", data["support"]["bar_meta"])""")

md("""## Config

Every tunable of the demo lives here. `N_CHECKPOINTS` and `N_CANDIDATES` slice the demo panel;
`N_BOOT` is the checkpoint-bootstrap replicate count. The values on the right in the comments are
what the full artifact run used (48 checkpoints, 15 candidates, 2000 replicates) — the demo slice is
capped by what ships in `mini_demo_data.json`.""")

code(r"""# ---- tunables -------------------------------------------------------------
N_CHECKPOINTS = 12          # full run: 48 graded panel checkpoints
N_CANDIDATES = 8            # full run: 15 registered candidates (W1-W8, G1-G4, A1-A3)
N_BOOT = 2000               # full run: 2000 checkpoint-bootstrap replicates
N_STABILITY_DRAWS = 8       # full run: all stored (prompt_draw x fold_seed x band_offset) draws
PRESCREEN_THRESHOLD = 0.50  # |rho| vs BL1_easy at or above this -> DROPPED as collinear
ERANK_ENTROPY_MAX = 1.5     # P1 thresholds, from the frozen pre-registration
ERANK_COS_MIN = 0.8
# ---------------------------------------------------------------------------

# prescreen.py globals, restricted to the candidates present in the demo slice
CANDIDATES = data["candidates"][:N_CANDIDATES]
TIER_A_CANDS = {"G1", "G2", "G3", "G4", "A3"}   # array-only pass, available on the full panel
PANEL = data["panel"][:N_CHECKPOINTS]
SEED = data["support"]["operationalisation_seed"]

print("CANDIDATES  :", CANDIDATES)
print("TIER-A here :", sorted(TIER_A_CANDS & set(CANDIDATES)))
print("PANEL       :", len(PANEL), "checkpoints")
print("SEED        :", SEED)""")

md("""## Rebuilding the screen table

The artifact's S3 stage reads `results/screen_table.json` from disk. Here the same structure —
`{"panel": [...], "rows": [...], "bars": [...]}` — is rebuilt from the demo examples, so every
function below is called exactly as it is in the pipeline.""")

code(r"""rows = []
for e in data["examples"]:
    key = json.loads(e["input"])
    if key["candidate"] not in CANDIDATES or key["tag"] not in PANEL:
        continue
    rows.append({
        "tag": key["tag"],
        "candidate": key["candidate"],
        "value": float(e["output"]),
        "tier": e["metadata_tier"],
        "censored": e["metadata_censored"],
        "flags": e["metadata_flags"],
        "band": e["metadata_band"],
        "n_prompts": e["metadata_n_prompts"],
        "stability": e["metadata_stability"][:N_STABILITY_DRAWS],
    })

bars = [{"tag": t, "bar": "BL1_easy", "value": data["support"]["bars_BL1_easy"][t],
         "meta": data["support"]["bar_meta"]} for t in PANEL]

screen_table = {"panel": PANEL, "rows": rows, "bars": bars}

# prereg.json, reduced to the two fields S3.2 reads out of it
prereg = {"d_candidates": {c: {"expected_sign": data["support"]["prereg_expected_sign"].get(c, {})}
                            for c in CANDIDATES},
          "operationalisation_seed": SEED}

print(f"{len(rows)} rows, {len(bars)} bar rows, {len(PANEL)} panel checkpoints")
print("example row:", json.dumps({k: v for k, v in rows[0].items() if k != 'stability'}))
print("stability draws on that row:", len(rows[0]["stability"]))""")

md("""## `src/statlib.py` — the screen's statistics

Copied verbatim from the artifact. Spearman uses pairwise deletion; the bootstrap resamples
**checkpoint indices** (which is what makes margins between candidates paired); `erank` returns both
the entropy effective rank `exp(-sum p log p)` and the participation ratio; `rho_mde` is the
minimum detectable Spearman rho at alpha=0.05 / power 0.80; `winsorise_high` caps CENSORED_HIGH
cells at the panel's 95th percentile.""")

code(r'''def _rankdata(a: np.ndarray) -> np.ndarray:
    """Average-rank transform (identical to scipy.stats.rankdata method='average')."""
    a = np.asarray(a, dtype=float)
    n = a.size
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    sa = a[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sa[j + 1] == sa[i]:
            j += 1
        avg = 0.5 * (i + j) + 1.0
        ranks[order[i : j + 1]] = avg
        i = j + 1
    return ranks


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 3:
        return float("nan")
    xc = x - x.mean()
    yc = y - y.mean()
    den = math.sqrt(float(xc @ xc) * float(yc @ yc))
    if den <= 0.0:
        return float("nan")
    return float((xc @ yc) / den)


def _finite_pair(x: Sequence[float], y: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    m = np.isfinite(x) & np.isfinite(y)
    return x[m], y[m]


def spearman(x: Sequence[float], y: Sequence[float]) -> dict:
    """Spearman rho with pairwise deletion. Returns {rho, n}."""
    xf, yf = _finite_pair(x, y)
    n = int(xf.size)
    if n < 3:
        return {"rho": float("nan"), "n": n}
    return {"rho": _pearson(_rankdata(xf), _rankdata(yf)), "n": n}


def checkpoint_bootstrap(
    stat_fn: Callable[[np.ndarray], float],
    n_items: int,
    *,
    n_boot: int = 2000,
    seed: int = 20260921,
    alpha: float = 0.05,
) -> dict:
    """Percentile bootstrap over CHECKPOINT indices.

    `stat_fn` receives an index array (with replacement) and returns a scalar.
    Every statistic in this artifact is computed on the SAME resampled index
    vector, which is what makes the margins paired.
    """
    rng = np.random.default_rng(seed)
    point = float(stat_fn(np.arange(n_items)))
    draws = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, n_items, size=n_items)
        try:
            draws[b] = float(stat_fn(idx))
        except (ValueError, ZeroDivisionError, np.linalg.LinAlgError):
            draws[b] = np.nan
    good = draws[np.isfinite(draws)]
    if good.size < 50:
        return {
            "point": point,
            "lo": float("nan"),
            "hi": float("nan"),
            "n_boot_ok": int(good.size),
            "excludes_zero": False,
        }
    lo = float(np.quantile(good, alpha / 2.0))
    hi = float(np.quantile(good, 1.0 - alpha / 2.0))
    return {
        "point": point,
        "lo": lo,
        "hi": hi,
        "n_boot_ok": int(good.size),
        "excludes_zero": bool((lo > 0.0) or (hi < 0.0)),
    }


def erank(matrix: np.ndarray) -> dict:
    """Effective rank of a (candidates x checkpoints) matrix.

    Returns both the entropy variant exp(-sum p log p) and the participation
    ratio (sum s^2)^2 / sum s^4, plus the singular-value spectrum and the
    leading right/left singular vectors.
    """
    m = np.asarray(matrix, dtype=float)
    if m.ndim != 2 or min(m.shape) < 2:
        return {"erank_entropy": float("nan"), "erank_participation": float("nan"),
                "singular_values": [], "explained": [], "leading_left": []}
    u, s, _vt = np.linalg.svd(m, full_matrices=False)
    s2 = s**2
    tot = float(s2.sum())
    if tot <= 0.0:
        return {"erank_entropy": float("nan"), "erank_participation": float("nan"),
                "singular_values": s.tolist(), "explained": [], "leading_left": []}
    p = s2 / tot
    nz = p[p > 1e-15]
    ent = float(np.exp(-float(np.sum(nz * np.log(nz)))))
    part = float((tot**2) / float(np.sum(s2**2)))
    return {
        "erank_entropy": ent,
        "erank_participation": part,
        "singular_values": s.tolist(),
        "explained": p.tolist(),
        "leading_left": u[:, 0].tolist(),
    }


def rho_mde(n: int) -> float:
    """Minimum detectable Spearman rho, two-sided alpha=0.05, power 0.80.

    rho_MDE = tanh(2.80 / sqrt(n - 3))   (Fisher-z, z_{.975}+z_{.80} = 2.80)
    """
    if n is None or n <= 3:
        return float("nan")
    return float(math.tanh(2.80 / math.sqrt(n - 3.0)))


def winsorise_high(values: Sequence[float], censored: Sequence[bool]) -> np.ndarray:
    """Replace CENSORED_HIGH cells with the panel's 95th percentile of the
    uncensored finite values. Returns a new array; never mutates the input."""
    v = np.asarray(values, dtype=float).copy()
    cen = np.asarray(censored, dtype=bool)
    ok = np.isfinite(v) & (~cen)
    if ok.sum() >= 3:
        cap = float(np.quantile(v[ok], 0.95))
    elif ok.sum() > 0:
        cap = float(np.nanmax(v[ok]))
    else:
        return v
    v[cen] = cap
    return v


print("statlib loaded; MDE at n =", len(PANEL), "->", round(rho_mde(len(PANEL)), 4))''')

md("""## S3.2 — the pre-screen (`src/prescreen.py`)

For each candidate: winsorise censored cells (except W2, whose sentinel 7 is a meaningful ceiling
code), take Spearman against `BL1_easy` over the panel, bootstrap a CI over checkpoints, also report
the censored-dropped variant and the sign stability of the stored re-draws. `|rho| >= 0.50` ⇒
**DROPPED** as collinear with the incumbent bar.

In the artifact this whole block runs inside a hardened `open()` audit that makes reading any
outcome file (`graded_truth`, `classification`, `heldout`, …) raise `PermissionError` — the demo
drops the audit wrapper only because there is no filesystem to guard here.""")

code(r'''def _row_values(rows: list[dict], cand: str, panel: list[str]) -> dict[str, dict]:
    """tag -> {'value':.., 'censored':bool} for a candidate, panel rows only."""
    out = {}
    for r in rows:
        if r["candidate"] != cand or r["tag"] not in panel:
            continue
        out[r["tag"]] = {"value": r["value"], "censored": bool(r.get("censored", False))}
    return out


def _expected_sign(prereg: dict, cand: str) -> str | None:
    d = prereg.get("d_candidates", {}).get(cand, {})
    es = d.get("expected_sign", {})
    hc = es.get("HC")
    if hc is None:
        return None
    hc = str(hc).strip()
    if hc.startswith("-"):
        return "-"
    if hc.startswith("+"):
        return "+"
    return hc[:1] if hc else None


def _sign_stability(rows: list[dict], cand: str, panel: list[str]) -> dict:
    """From screen_table stability draws (when present): fraction of (row, draw) pairs
    whose sign matches the row's registered value sign."""
    n_agree, n_total = 0, 0
    for r in rows:
        if r["candidate"] != cand or r["tag"] not in panel:
            continue
        reg = r.get("value")
        draws = r.get("stability")
        if reg is None or not isinstance(draws, list) or not draws:
            continue
        reg_sign = np.sign(reg)
        if reg_sign == 0:
            continue
        for d in draws:
            v = d.get("value")
            if v is None or not np.isfinite(v):
                continue
            n_total += 1
            if np.sign(v) == reg_sign:
                n_agree += 1
    if n_total == 0:
        return {"sign_agree_frac": None, "n_draws": 0}
    return {"sign_agree_frac": n_agree / n_total, "n_draws": n_total}


def run_s3_2(prereg: dict, screen_table: dict) -> dict:
    panel = list(screen_table.get("panel", []))
    rows = screen_table.get("rows", [])

    # BL1_easy per tag, from the bars table (bar == "BL1_easy").
    bl1 = {}
    for b in screen_table.get("bars", []):
        if b.get("bar") == "BL1_easy" and b.get("tag") not in bl1:
            bl1[b["tag"]] = b.get("value")

    out = {}
    n_dropped = n_kept = n_not_evaluable = 0
    for cand in CANDIDATES:
        vals = _row_values(rows, cand, panel)
        tags_ordered = [t for t in panel if t in vals]
        raw = np.array([vals[t]["value"] if vals[t]["value"] is not None else np.nan for t in tags_ordered], dtype=float)
        cen = np.array([vals[t]["censored"] for t in tags_ordered], dtype=bool)
        y_raw = np.array([bl1.get(t, np.nan) for t in tags_ordered], dtype=float)

        # censoring rule: winsorise at panel-95th-pct of uncensored values, EXCEPT W2 keeps its
        # sentinel 7 (never winsorised -- it is a meaningful ceiling code, not an outlier).
        if cand == "W2":
            wins = raw.copy()
        else:
            wins = winsorise_high(raw, cen) if cen.any() else raw

        sp_w = spearman(wins, y_raw)
        n = sp_w["n"]

        def _stat(idx, a=wins, b=y_raw):
            return spearman(a[idx], b[idx])["rho"]

        ci = checkpoint_bootstrap(_stat, len(wins), n_boot=N_BOOT,
                                   seed=prereg["operationalisation_seed"]) if len(wins) >= 5 else \
            {"point": sp_w["rho"], "lo": float("nan"), "hi": float("nan"), "n_boot_ok": 0, "excludes_zero": False}

        # censored-dropped variant
        keep = ~cen
        sp_dropped = spearman(raw[keep], y_raw[keep])

        mde = rho_mde(n) if n and n > 3 else float("nan")
        expected = _expected_sign(prereg, cand)
        stability = _sign_stability(rows, cand, panel)

        evaluable = n >= 3 and np.isfinite(sp_w["rho"])
        if not evaluable:
            status = "NOT_EVALUABLE"
            n_not_evaluable += 1
        elif abs(sp_w["rho"]) >= PRESCREEN_THRESHOLD:
            status = "DROPPED"
            n_dropped += 1
        else:
            status = "KEPT"
            n_kept += 1

        out[cand] = {
            "rho": sp_w["rho"], "ci": {"lo": ci["lo"], "hi": ci["hi"], "n_boot_ok": ci.get("n_boot_ok")},
            "n": n, "mde": mde, "status": status,
            "rho_censored_dropped": sp_dropped["rho"], "n_censored_dropped": sp_dropped["n"],
            "n_censored": int(cen.sum()), "tier": "Tier-A-only" if cand in TIER_A_CANDS else "mixed/Tier-B",
            "stable_flags": stability, "expected_sign_HC": expected,
        }

    return {
        "threshold": PRESCREEN_THRESHOLD,
        "prescreen_rule": "|Spearman(candidate, BL1_easy)| over screen-panel rows with both finite >= 0.50 -> DROPPED",
        "candidates": out,
        "n_dropped": n_dropped, "n_kept": n_kept, "n_not_evaluable": n_not_evaluable,
        "n_panel": len(panel),
    }


prescreen_result = run_s3_2(prereg, screen_table)
print(f"S3.2: dropped={prescreen_result['n_dropped']} kept={prescreen_result['n_kept']} "
      f"not_evaluable={prescreen_result['n_not_evaluable']}")
for cand, rec in prescreen_result["candidates"].items():
    print(f"  {cand:<3} rho={rec['rho']:+.3f}  CI[{rec['ci']['lo']:+.3f},{rec['ci']['hi']:+.3f}]  "
          f"n={rec['n']:>2}  MDE={rec['mde']:.3f}  {rec['status']}")''')

md("""## S3.3 — effective rank (is the family one coordinate?)

Each candidate row is z-scored over its finite entries (NaN → 0 after z-scoring = mean imputation),
then the (candidates × checkpoints) matrix is decomposed. `erank_partial_BL1` repeats the
decomposition on the OLS residuals of every row on `z(BL1_easy)`, and the leading **right** singular
vector (checkpoint loadings) is compared to `z(BL1_easy)` by absolute cosine.

Hypothesis **P1** ("all of this is one coordinate, and that coordinate is the logit gap") survives
only if `erank_entropy <= 1.5` **and** `|cos| >= 0.8`.""")

code(r'''def _zscore_impute(mat: np.ndarray) -> tuple[np.ndarray, int]:
    """z-score each ROW (candidate) over its finite entries; NaN -> 0 AFTER z-scoring
    (mean imputation). Returns (matrix, n_imputed)."""
    m = mat.copy()
    n_imputed = 0
    for i in range(m.shape[0]):
        row = m[i]
        finite = np.isfinite(row)
        if finite.sum() >= 2:
            mu = row[finite].mean()
            sd = row[finite].std(ddof=0) or 1.0
            m[i] = (row - mu) / sd
        else:
            m[i] = 0.0
        bad = ~np.isfinite(m[i])
        n_imputed += int(bad.sum())
        m[i, bad] = 0.0
    return m, n_imputed


def _partial_out_bl1(mat_z: np.ndarray, y_z: np.ndarray) -> np.ndarray:
    """Replace each row by its OLS residual on z(BL1_easy) (with intercept)."""
    out = np.zeros_like(mat_z)
    design = np.column_stack([np.ones_like(y_z), y_z])
    for i in range(mat_z.shape[0]):
        beta, *_ = np.linalg.lstsq(design, mat_z[i], rcond=None)
        out[i] = mat_z[i] - design @ beta
    return out


def _build_matrix(rows: list[dict], cands: list[str], tags: list[str]) -> np.ndarray:
    idx = {(r["tag"], r["candidate"]): r["value"] for r in rows}
    m = np.full((len(cands), len(tags)), np.nan, dtype=float)
    for i, c in enumerate(cands):
        for j, t in enumerate(tags):
            v = idx.get((t, c))
            if v is not None:
                m[i, j] = v
    return m


def _spearman_matrix(mat_raw: np.ndarray, cands: list[str]) -> dict:
    n = len(cands)
    out = {}
    for i in range(n):
        for j in range(n):
            r = spearman(mat_raw[i], mat_raw[j])
            out[f"{cands[i]}|{cands[j]}"] = r["rho"]
    return out


def _rank_block(rows: list[dict], cands: list[str], tags: list[str], bl1_by_tag: dict) -> dict:
    mat_raw = _build_matrix(rows, cands, tags)
    mat_z, n_imputed = _zscore_impute(mat_raw)
    y_raw = np.array([bl1_by_tag.get(t, np.nan) for t in tags], dtype=float)
    y_finite = np.isfinite(y_raw)
    y_z = np.zeros_like(y_raw)
    if y_finite.sum() >= 2:
        mu, sd = y_raw[y_finite].mean(), (y_raw[y_finite].std(ddof=0) or 1.0)
        y_z[y_finite] = (y_raw[y_finite] - mu) / sd
    # y NaNs -> 0 too (same imputation convention)

    full = erank(mat_z)
    mat_partial = _partial_out_bl1(mat_z, y_z)
    partial = erank(mat_partial)

    # leading right singular vector (checkpoint loadings) -> |cos| with z(BL1_easy)
    if mat_z.shape[0] >= 2 and mat_z.shape[1] >= 2:
        _u, _s, vt = np.linalg.svd(mat_z, full_matrices=False)
        v1 = vt[0]
        denom = (np.linalg.norm(v1) * np.linalg.norm(y_z)) or 1.0
        cos_ckpt_bl1 = abs(float(np.dot(v1, y_z) / denom)) if denom else float("nan")
    else:
        cos_ckpt_bl1 = float("nan")

    return {
        "n_candidates": len(cands), "n_checkpoints": len(tags), "n_imputed": n_imputed,
        "candidates": cands, "checkpoints": tags,
        "erank_full": {"erank_entropy": full["erank_entropy"], "erank_participation": full["erank_participation"],
                        "singular_values": full["singular_values"], "leading_left_loadings": full["leading_left"]},
        "erank_partial_BL1": {"erank_entropy": partial["erank_entropy"],
                               "erank_participation": partial["erank_participation"],
                               "singular_values": partial["singular_values"],
                               "leading_left_loadings": partial["leading_left"]},
        "leading_eigenvector_loading_pattern": dict(zip(cands, full["leading_left"])) if full["leading_left"] else {},
        "abs_cos_leading_right_singvec_vs_zBL1": cos_ckpt_bl1,
        "spearman_matrix": _spearman_matrix(mat_raw, cands),
    }


def run_s3_3(prereg: dict, screen_table: dict) -> dict:
    panel = list(screen_table.get("panel", []))
    rows = screen_table.get("rows", [])
    bl1 = {}
    for b in screen_table.get("bars", []):
        if b.get("bar") == "BL1_easy" and b.get("tag") not in bl1:
            bl1[b["tag"]] = b.get("value")

    full_panel_block = _rank_block(rows, CANDIDATES, panel, bl1)

    tierA_block = _rank_block(rows, sorted(TIER_A_CANDS & set(CANDIDATES)), panel, bl1)

    # complete-Tier-B-coverage: checkpoints where EVERY candidate (incl. Tier-B) is finite
    idx = {(r["tag"], r["candidate"]): r["value"] for r in rows}
    complete_tags = [t for t in panel
                     if all(idx.get((t, c)) is not None and np.isfinite(idx[(t, c)]) for c in CANDIDATES)]
    if len(complete_tags) >= 2:
        complete_block = _rank_block(rows, CANDIDATES, complete_tags, bl1)
    else:
        complete_block = {"note": f"only {len(complete_tags)} checkpoints have complete Tier-B coverage "
                                   f"(need >=2 for SVD); block skipped", "n_checkpoints": len(complete_tags)}

    ent = full_panel_block["erank_full"]["erank_entropy"]
    cos = full_panel_block["abs_cos_leading_right_singvec_vs_zBL1"]
    if np.isfinite(ent) and np.isfinite(cos) and ent <= ERANK_ENTROPY_MAX and cos >= ERANK_COS_MIN:
        verdict = "P1-consistent: one coordinate, BL1-aligned"
    elif np.isfinite(ent) and np.isfinite(cos):
        verdict = (f"P1 NOT supported by the rank structure: erank_entropy={ent:.3f} "
                   f"(threshold <={ERANK_ENTROPY_MAX}), |cos(leading ckpt singvec, z(BL1_easy))|={cos:.3f} "
                   f"(threshold >={ERANK_COS_MIN})")
    else:
        verdict = "erank/cos not computable (insufficient finite data)"

    return {
        "full_panel_all_candidates": full_panel_block,
        "tier_A_only_full_panel": tierA_block,
        "complete_tierB_coverage": complete_block,
        "verdict": verdict,
    }


rank_result = run_s3_3(prereg, screen_table)
fb = rank_result["full_panel_all_candidates"]
print("erank entropy       :", round(fb["erank_full"]["erank_entropy"], 3))
print("erank participation :", round(fb["erank_full"]["erank_participation"], 3))
print("erank after partialling out BL1_easy:",
      round(fb["erank_partial_BL1"]["erank_entropy"], 3))
print("|cos(leading ckpt singvec, z(BL1_easy))| :",
      round(fb["abs_cos_leading_right_singvec_vs_zBL1"], 3))
print()
print("VERDICT:", rank_result["verdict"])''')

md("""## S6 — assembly (`method.py`)

`method.py` is the final aggregation stage: every results file becomes one dataset of
`exp_gen_sol_out` examples. The builders below are copied verbatim; they are fed the S3.2/S3.3
results just computed instead of the JSON files on disk.""")

code(r'''def _ex(input_obj, output, **kw) -> dict:
    """Build one exp_gen_sol_out example; predict_/metadata_ kwargs are cast to str/JSON as required."""
    e = {"input": json.dumps(input_obj, sort_keys=True), "output": str(output)}
    for k, v in kw.items():
        if k.startswith("predict_"):
            e[k] = "" if v is None else str(v)
        elif k.startswith("metadata_"):
            e[k] = v
    return e


def build_screen_table_dataset(screen_table: dict | None) -> dict:
    examples = []
    if screen_table:
        for r in screen_table.get("rows", []):
            examples.append(_ex(
                {"tag": r["tag"], "candidate": r["candidate"]}, r.get("value"),
                metadata_tier=r.get("tier"), metadata_censored=r.get("censored"),
                metadata_flags=r.get("flags"), metadata_band=r.get("band"),
                metadata_n_prompts=r.get("n_prompts"),
            ))
    if not examples:
        examples = [_ex({"note": "screen_table.json not available"}, "N/A")]
    return {"dataset": "screen_table", "examples": examples}


def build_prescreen_dataset(prescreen: dict | None) -> dict:
    examples = []
    if prescreen:
        for cand, rec in prescreen.get("candidates", {}).items():
            examples.append(_ex(
                {"candidate": cand}, rec.get("status"),
                metadata_rho=rec.get("rho"), metadata_ci=rec.get("ci"), metadata_n=rec.get("n"),
                metadata_mde=rec.get("mde"), metadata_tier=rec.get("tier"),
                predict_rho_BL1_easy=rec.get("rho"),
                predict_rho_censored_dropped=rec.get("rho_censored_dropped"),
            ))
    if not examples:
        examples = [_ex({"note": "prescreen.json not available"}, "N/A")]
    return {"dataset": "prescreen", "examples": examples}


def build_rank_analysis_dataset(rank: dict | None) -> dict:
    examples = []
    if rank:
        for block_name in ("full_panel_all_candidates", "tier_A_only_full_panel", "complete_tierB_coverage"):
            b = rank.get(block_name, {})
            if "erank_full" not in b:
                continue
            examples.append(_ex(
                {"block": block_name}, rank.get("verdict"),
                metadata_erank_entropy=b["erank_full"].get("erank_entropy"),
                metadata_erank_participation=b["erank_full"].get("erank_participation"),
                metadata_erank_entropy_partial_BL1=b.get("erank_partial_BL1", {}).get("erank_entropy"),
                metadata_abs_cos_ckpt_vs_zBL1=b.get("abs_cos_leading_right_singvec_vs_zBL1"),
                metadata_n_candidates=b.get("n_candidates"), metadata_n_checkpoints=b.get("n_checkpoints"),
            ))
    if not examples:
        examples = [_ex({"note": "rank_analysis.json not available"}, "N/A")]
    return {"dataset": "rank_analysis", "examples": examples}


def build_stability_dataset(screen_table: dict | None) -> dict:
    examples = []
    if screen_table:
        for r in screen_table.get("rows", []):
            stab = r.get("stability")
            if not isinstance(stab, list) or not stab:
                continue
            vals = [d["value"] for d in stab if isinstance(d, dict) and d.get("value") is not None]
            reg = r.get("value")
            agree = None
            if vals and reg is not None:
                agree = float(sum(1 for v in vals if (v >= 0) == (reg >= 0)) / len(vals))
            examples.append(_ex(
                {"tag": r["tag"], "candidate": r["candidate"]}, reg,
                metadata_n_draws=len(stab), metadata_sign_agree_frac=agree,
            ))
    if not examples:
        examples = [_ex({"note": "no stability draws available"}, "N/A")]
    return {"dataset": "stability", "examples": examples}


metadata = {
    "method_name": "iter5_wide_screen_and_confirmation_join (demo slice)",
    "description": "S3 pre-screen/effective-rank -> S6 output, on the curated demo slice.",
    "n_panel_checkpoints": len(screen_table["panel"]),
    "n_candidates_registered": len(CANDIDATES),
    "prescreen_n_dropped": prescreen_result["n_dropped"],
    "prescreen_n_kept": prescreen_result["n_kept"],
    "rank_analysis_verdict": rank_result["verdict"],
}

datasets = [
    build_screen_table_dataset(screen_table),
    build_prescreen_dataset(prescreen_result),
    build_rank_analysis_dataset(rank_result),
    build_stability_dataset(screen_table),
]

demo_out = {"metadata": metadata, "datasets": datasets}
print(json.dumps(metadata, indent=1)[:900])
print()
for d in datasets:
    print(f"  {d['dataset']:<14} {len(d['examples']):>4} examples")''')

md("""## Results

1. **Pre-screen table** — rho against the incumbent logit gap, its bootstrap CI, MDE and verdict.
2. **|rho| bar chart** — which candidates are collinear with the bar (above the 0.50 line) and which
   carry independent signal.
3. **Candidate × checkpoint z-matrix** — the matrix the effective rank is computed on.
4. **Singular-value spectrum** — before and after partialling out `z(BL1_easy)`. A family that were
   "one coordinate" would put nearly all mass on the first singular value.""")

code(r'''# ---- 1. pre-screen table --------------------------------------------------
hdr = f"{'cand':<5}{'tier':<14}{'rho vs BL1':>11}{'95% CI':>20}{'rho (cens.drop)':>17}{'MDE':>8}{'sign-stab':>11}  status"
print(hdr)
print("-" * len(hdr))
for cand, rec in prescreen_result["candidates"].items():
    ss = rec["stable_flags"]["sign_agree_frac"]
    print(f"{cand:<5}{rec['tier']:<14}{rec['rho']:>+11.3f}"
          f"{'[' + format(rec['ci']['lo'], '+.2f') + ',' + format(rec['ci']['hi'], '+.2f') + ']':>20}"
          f"{rec['rho_censored_dropped']:>+17.3f}{rec['mde']:>8.3f}"
          f"{('n/a' if ss is None else format(ss, '.2f')):>11}  {rec['status']}")
print()
print("VERDICT:", rank_result["verdict"])

fig, axes = plt.subplots(2, 2, figsize=(13.5, 9))

# ---- 2. |rho| vs the pre-screen threshold ---------------------------------
ax = axes[0, 0]
cands = list(prescreen_result["candidates"])
rhos = [prescreen_result["candidates"][c]["rho"] for c in cands]
cols = ["#c44e52" if abs(r) >= PRESCREEN_THRESHOLD else "#4c72b0" for r in rhos]
ax.bar(cands, [abs(r) for r in rhos], color=cols)
ax.axhline(PRESCREEN_THRESHOLD, ls="--", c="k", lw=1)
ax.text(len(cands) - 0.4, PRESCREEN_THRESHOLD + 0.02, f"drop at |rho| >= {PRESCREEN_THRESHOLD}",
        ha="right", fontsize=9)
ax.set_title("S3.2 pre-screen: collinearity with the incumbent logit gap")
ax.set_ylabel("|Spearman rho| vs BL1_easy")
ax.set_ylim(0, 1)

# ---- 3. candidate x checkpoint z-matrix -----------------------------------
ax = axes[0, 1]
mat_raw = _build_matrix(screen_table["rows"], CANDIDATES, PANEL)
mat_z, _ = _zscore_impute(mat_raw)
im = ax.imshow(mat_z, cmap="RdBu_r", vmin=-2.5, vmax=2.5, aspect="auto")
ax.set_yticks(range(len(CANDIDATES)), CANDIDATES)
ax.set_xticks(range(len(PANEL)), [t.split("__")[0] + "/" + t.split("__")[1][:10] for t in PANEL],
              rotation=90, fontsize=7)
ax.set_title("z-scored readout matrix (candidates x checkpoints)")
fig.colorbar(im, ax=ax, shrink=0.8)

# ---- 4. singular-value spectrum -------------------------------------------
ax = axes[1, 0]
sv = np.array(fb["erank_full"]["singular_values"])
svp = np.array(fb["erank_partial_BL1"]["singular_values"])
w = 0.4
ax.bar(np.arange(len(sv)) - w / 2, sv**2 / (sv**2).sum(), w, label="full")
ax.bar(np.arange(len(svp)) + w / 2, svp**2 / (svp**2).sum(), w, label="BL1_easy partialled out")
ax.set_xlabel("singular value index")
ax.set_ylabel("variance share")
ax.set_title(f"Spectrum: erank(entropy) = {fb['erank_full']['erank_entropy']:.2f} "
             f"(P1 needs <= {ERANK_ENTROPY_MAX})")
ax.legend(fontsize=8)

# ---- 5. loading of each candidate on the leading component ----------------
ax = axes[1, 1]
load = fb["leading_eigenvector_loading_pattern"]
ax.barh(list(load), [load[c] for c in load], color="#55a868")
ax.axvline(0, c="k", lw=1)
ax.set_title(f"Leading-component loadings\n|cos(leading ckpt singvec, z(BL1_easy))| = "
             f"{fb['abs_cos_leading_right_singvec_vs_zBL1']:.3f} (P1 needs >= {ERANK_COS_MIN})")
ax.invert_yaxis()

fig.tight_layout()
plt.show()''')

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                    "language_info": {"name": "python", "version": "3.12.12"}},
      "nbformat": 4, "nbformat_minor": 5}
(WS/"code_demo.ipynb").write_text(json.dumps(nb, indent=1))
print("wrote notebook,", len(cells), "cells")
PYEOF
python3 /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--3-gen-demo-art-notebook-workspaces-iter-5-art-l3WSWrVMeJZU/4199f3f8-bef6-4e67-a967-eef1820c455e/scratchpad/gen_nb.py
```

### [40] TOOL RESULT — Bash · 2026-09-22 08:11:36 UTC

```
{"stdout": "wrote notebook, 21 cells", "stderr": "", "interrupted": false, "isImage": false, "noOutputExpected": true}
```

### [41] TOOL CALL — Bash · 2026-09-22 08:11:38 UTC

```
Create test venv:
/usr/local/bin/python3.12 -m venv .nb_env && .nb_env/bin/pip install -q pip jupyter ipykernel 2>&1 | tail -3 && echo VENV_OK
```

### [42] TOOL RESULT — Bash · 2026-09-22 08:19:32 UTC

```
{"stdout": "[notice] A new release of pip is available: 25.0.1 -> 26.2.1\n[notice] To update, run: python3.12 -m pip install --upgrade pip\nVENV_OK", "stderr": "", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [43] TOOL CALL — Bash · 2026-09-22 08:20:02 UTC

```
Execute notebook:
time .nb_env/bin/jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 code_demo.ipynb --output code_demo.ipynb 2>&1 | tail -30
```

### [44] TOOL RESULT — Bash · 2026-09-22 08:22:00 UTC

```
{"stdout": "[NbConvertApp] Converting notebook code_demo.ipynb to notebook\n/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_3_gen_demo_art/notebook_workspaces/iter_5/art_l3WSWrVMeJZU/.nb_env/lib/python3.12/site-packages/nbformat/validator.py:434: MissingIDFieldWarning: Cell is missing an id field, this will become a hard error in future nbformat versions. You may want to use `normalize()` on your notebooks before validations (available since nbformat 5.1.4). Previous versions of nbformat are fixing this issue transparently, and will stop doing so in the future.\n  _validate(nbdict, ref, version, version_minor, relax_add_props)\n[IPKernelApp] WARNING | Kernel is running over TCP without encryption. All communication (including code and outputs) is sent in plain text and is susceptible to eavesdropping. Use IPC transport or launch with kernel manager-provisioned CurveZMQ keys to enable transport encryption.\n\n\u001b[1m[\u001b[0m\u001b[34;49mnotice\u001b[0m\u001b[1;39;49m]\u001b[0m\u001b[39;49m A new release of pip is available: \u001b[0m\u001b[31;49m25.0.1\u001b[0m\u001b[39;49m -> \u001b[0m\u001b[32;49m26.2.1\u001b[0m\n\u001b[1m[\u001b[0m\u001b[34;49mnotice\u001b[0m\u001b[1;39;49m]\u001b[0m\u001b[39;49m To update, run: \u001b[0m\u001b[32;49mpython3.12 -m pip install --upgrade pip\u001b[0m\n[NbConvertApp] Writing 171771 bytes to code_demo.ipynb\n\nreal\t2m18.234s\nuser\t0m11.275s\nsys\t0m1.772s", "stderr": "", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [45] TOOL CALL — Bash · 2026-09-22 08:22:00 UTC

```
Check notebook outputs:
python3 -c "
import json
nb=json.load(open('code_demo.ipynb'))
for i,c in enumerate(nb['cells']):
    if c['cell_type']!='code': continue
    for o in c.get('outputs',[]):
        if o.get('output_type')=='error': print('CELL',i,'ERROR',o['ename'],o['evalue'])
        t=''.join(o.get('text',[]))
        if t.strip(): print('--- cell',i,'---'); print(t[:1500])
"
```

### [46] TOOL RESULT — Bash · 2026-09-22 08:22:00 UTC

```
{"stdout": "--- cell 1 ---\n\n\u001b[1m[\u001b[0m\u001b[34;49mnotice\u001b[0m\u001b[1;39;49m]\u001b[0m\u001b[39;49m A new release of pip is available: \u001b[0m\u001b[31;49m25.0.1\u001b[0m\u001b[39;49m -> \u001b[0m\u001b[32;49m26.2.1\u001b[0m\n\u001b[1m[\u001b[0m\u001b[34;49mnotice\u001b[0m\u001b[1;39;49m]\u001b[0m\u001b[39;49m To update, run: \u001b[0m\u001b[32;49mpython3.12 -m pip install --upgrade pip\u001b[0m\n\n--- cell 6 ---\nCurated subset of the iteration-5 wide-screen table: 8 of the 15 registered second-order activation readouts on 12 of the 48 graded panel checkpoints, plus the incumbent final-layer logit-gap bar (BL1_easy) for the same checkpoints.\n\ncandidates : ['G1', 'G2', 'W6', 'W8', 'W3', 'G4', 'G3', 'A3']\ncheckpoints: 12\n    F1__a05\n    F1__a10\n    F1__cautious\n    F2__a05\n    F2__a10\n    F2__cautious\n    F3__a05\n    F3__a10\n    F3__cautious\n    HG__Goekdeniz-Guelmez--Josiefied-Qwen2.5-1.5B-Instruct-abliterated-v3\n    HG__Qwen--Qwen2.5-1.5B-Instruct\n    HG__Qwen--Qwen3-1.7B\ncells      : 96\nbar meta   : {'array': 'r_refusal - r_control @ hidden-state index L (final layer)', 'layer': 'L=28', 'prompt_set': 'EASY n=96 (48 advbench-harmful vs 48 dolly-benign)'}\n\n--- cell 8 ---\nCANDIDATES  : ['G1', 'G2', 'W6', 'W8', 'W3', 'G4', 'G3', 'A3']\nTIER-A here : ['A3', 'G1', 'G2', 'G3', 'G4']\nPANEL       : 12 checkpoints\nSEED        : 20260922\n\n--- cell 10 ---\n96 rows, 12 bar rows, 12 panel checkpoints\nexample row: {\"tag\": \"F1__a05\", \"candidate\": \"G1\", \"value\": 53.8166350177096, \"tier\": \"A\", \"censored\": false, \"flags\": [], \"band\": {\"A\": 4, \"B\": 6}, \"n_prompts\": 32}\nstability draws on that row: 4\n\n--- cell 12 ---\nstatlib loaded; MDE at n = 12 -> 0.7321\n\n--- cell 14 ---\nS3.2: dropped=3 kept=5 not_evaluable=0\n  G1  rho=-0.629  CI[-0.913,-0.119]  n=12  MDE=0.732  DROPPED\n  G2  rho=+0.587  CI[+0.000,+0.941]  n=12  MDE=0.732  DROPPED\n  W6  rho=+0.105  CI[-0.640,+0.774]  n=12  MDE=0.732  KEPT\n  W8  rho=+0.469  CI[-0.080,+0.863]  n=12  MDE=0.732  KEPT\n  W3  rho=+0.049  CI[-0.740,+0.690]  n=12  MDE=0.732  KEPT\n  G4  rho=+0.497  CI[-0.177,+0.839]  n=12  MDE=0.732  KEPT\n  G3  rho=+0.538  CI[-0.081,+0.851]  n=12  MDE=0.732  DROPPED\n  A3  rho=-0.280  CI[-0.674,+0.324]  n=12  MDE=0.732  KEPT\n\n--- cell 16 ---\nerank entropy       : 3.865\nerank participation : 2.763\nerank after partialling out BL1_easy: 4.181\n|cos(leading ckpt singvec, z(BL1_easy))| : 0.609\n\nVERDICT: P1 NOT supported by the rank structure: erank_entropy=3.865 (threshold <=1.5), |cos(leading ckpt singvec, z(BL1_easy))|=0.609 (threshold >=0.8)\n\n--- cell 18 ---\n{\n \"method_name\": \"iter5_wide_screen_and_confirmation_join (demo slice)\",\n \"description\": \"S3 pre-screen/effective-rank -> S6 output, on the curated demo slice.\",\n \"n_panel_checkpoints\": 12,\n \"n_candidates_registered\": 8,\n \"prescreen_n_dropped\": 3,\n \"prescreen_n_kept\": 5,\n \"rank_analysis_verdict\": \"P1 NOT supported by the rank structure: erank_entropy=3.865 (threshold <=1.5), |cos(leading ckpt singvec, z(BL1_easy))|=0.609 (threshold >=0.8)\"\n}\n\n  screen_table     96 examples\n  prescreen         8 examples\n  rank_analysis     3 examples\n  stability        96 examples\n\n--- cell 20 ---\ncand tier           rho vs BL1              95% CI  rho (cens.drop)     MDE  sign-stab  status\n----------------------------------------------------------------------------------------------\nG1   Tier-A-only        -0.629       [-0.91,-0.12]           -0.629   0.732       1.00  DROPPED\nG2   Tier-A-only        +0.587       [+0.00,+0.94]           +0.587   0.732       1.00  DROPPED\nW6   mixed/Tier-B       +0.105       [-0.64,+0.77]           +0.105   0.732       0.75  KEPT\nW8   mixed/Tier-B       +0.469       [-0.08,+0.86]           +0.469   0.732       1.00  KEPT\nW3   mixed/Tier-B       +0.049       [-0.74,+0.69]           +0.049   0.732       1.00  KEPT\nG4   Tier-A-only        +0.497       [-0.18,+0.84]           +0.497   0.732       1.00  KEPT\nG3   Tier-A-only        +0.538       [-0.08,+0.85]           +0.538   0.732       0.94  DROPPED\nA3   Tier-A-only        -0.280       [-0.67,+0.32]           -0.355   0.732       1.00  KEPT\n\nVERDICT: P1 NOT supported by the rank structure: erank_entropy=3.865 (threshold <=1.5), |cos(leading ckpt singvec, z(BL1_easy))|=0.609 (threshold >=0.8)", "stderr": "", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [47] ASSISTANT · 2026-09-22 08:22:00 UTC

```
Notebook passes on the first run with meaningful results. Adding a caveat note, then cleaning up.
```

### [48] TOOL CALL — Bash · 2026-09-22 08:22:00 UTC

```
Add note, remove test venv:
python3 - <<'EOF'
import json,pathlib
p=pathlib.Path("code_demo.ipynb"); nb=json.loads(p.read_text())
note=("\n\n*Note:* these numbers are the demo slice (8 candidates × 12 checkpoints), not the "
      "48-checkpoint / 15-candidate figures quoted in the paper — the pre-screen rho and the "
      "effective rank both move with the panel. The qualitative result is the same: the geometry "
      "candidates that track the logit gap are dropped, and the family is not one coordinate.")
for c in nb["cells"]:
    if c["cell_type"]=="markdown" and c["source"][0].startswith("## Results"):
        c["source"][-1]=c["source"][-1]+note
        break
p.write_text(json.dumps(nb,indent=1))
print("ok")
EOF
rm -rf .nb_env && ls -la && du -sh *
```

### [49] TOOL RESULT — Bash · 2026-09-22 08:22:02 UTC

```
{"stdout": "ok\ntotal 4764\ndrwxrwxrwx 3 root root 1074407 Sep 22 08:22 .\ndrwxrwxrwx 5 root root 2041631 Sep 22 08:17 ..\ndrwxrwxrwx 3 root root 1000156 Sep 22 08:09 .claude\n-rw-rw-rw- 1 root root  517381 Sep 22 08:22 .repl_agent.ptylog\n-rw-rw-rw- 1 root root  172273 Sep 22 08:21 code_demo.ipynb\n-rw-rw-rw- 1 root root   74815 Sep 22 08:10 mini_demo_data.json\n169K\tcode_demo.ipynb\n74K\tmini_demo_data.json", "stderr": "", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [50] TOOL CALL — Bash · 2026-09-22 08:22:11 UTC

````
Write README, manifest, struct out:
grep -c "raw.githubusercontent.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned/main/round-5/experiment-1/demo/mini_demo_data.json" code_demo.ipynb && python3 -c "
import json;nb=json.load(open('code_demo.ipynb'))
print('cells',len(nb['cells']),'with outputs',sum(1 for c in nb['cells'] if c.get('outputs')))
print('images',sum(1 for c in nb['cells'] for o in c.get('outputs',[]) if 'image/png' in o.get('data',{})))
"
mkdir -p .aii && cat > .aii/manifest.yaml <<'EOF'
# No heavy binaries or caches in this workspace: the deliverables are a 169 KB notebook
# and a 74 KB JSON data file (both text, both under the 10 MB auto-keep floor).
# The disposable .nb_env test virtualenv was deleted at the end of the run.
entries: []
EOF
cat > README.md <<'EOF'
# Wide screen of 15 second-order safety readouts — demo notebook

Demo for round-5 / experiment-1 of
*ai-invention-f8532e-safety-only-checks-output-when-warned*.

The experiment registers 15 single-model **activation** readouts for safety (W1–W8
write-handle/redundancy, G1–G4 dimensionless geometry, A1–A3 competing mechanisms), measures each on
a 48-checkpoint graded panel, and scores them against the incumbent final-layer **logit gap**
(`BL1_easy`). This notebook replays the statistics stages of that pipeline — the pre-screen, the
effective-rank test of hypothesis P1, and the `method.py` assembly — on a curated slice of the real
screen table.

## Layout

| path | what it is |
| --- | --- |
| `code_demo.ipynb` | the demo notebook (Colab-ready; loads its data from GitHub with a local fallback) |
| `mini_demo_data.json` | curated subset of `results/screen_table.json`: 96 measured cells = 8 candidates × 12 panel checkpoints, plus the `BL1_easy` bar per checkpoint, the pre-registered expected signs and the bootstrap seed |
| `.aii/manifest.yaml` | disposable-output decisions (nothing heavy here) |

## What the notebook runs

1. **S3.2 pre-screen** (`src/prescreen.py`, verbatim) — Spearman of each candidate against
   `BL1_easy` over the panel, checkpoint bootstrap CI, censored-dropped variant and sign stability;
   `|rho| >= 0.50` drops the candidate as collinear with the bar.
2. **S3.3 effective rank** (`src/prescreen.py`, verbatim) — z-scored candidate × checkpoint matrix,
   entropy effective rank and participation ratio, the same decomposition after partialling out
   `z(BL1_easy)`, and `|cos(leading checkpoint singular vector, z(BL1_easy))|`. P1 ("it is all one
   coordinate, and that coordinate is the logit gap") survives only if `erank_entropy <= 1.5` **and**
   `|cos| >= 0.8`.
3. **S6 assembly** (`method.py`, verbatim builders) — the stage results become `exp_gen_sol_out`
   datasets.
4. **Figures** — pre-screen table, |rho| bar chart against the 0.50 threshold, the z-scored readout
   matrix, the singular-value spectrum with and without `BL1_easy`, and the leading-component
   loadings.

The statistics helpers are copied verbatim from `src/statlib.py` (Spearman with pairwise deletion,
checkpoint bootstrap, `erank`, `rho_mde`, `winsorise_high`) — no SciPy, exactly as in the artifact.

Nothing is measured from model weights in the notebook: the activation readouts were computed on GPU
in the artifact and the demo replays the statistics stage on their stored values.

## How to run

**Colab:** open `code_demo.ipynb` and run all cells. The install cell installs nothing on Colab
(numpy and matplotlib are pre-installed) and the data is fetched from the repo's raw URL.

**Locally:**

```bash
python3.12 -m venv .nb_env
.nb_env/bin/pip install -q pip jupyter ipykernel
.nb_env/bin/jupyter nbconvert --to notebook --execute --ExecutePreprocessor.timeout=600 \
    code_demo.ipynb --output code_demo.ipynb
```

The install cell then pins `numpy==2.0.2` and `matplotlib==3.10.0` (Colab's versions) into the
fresh venv. End-to-end runtime, including the install: about 2.5 minutes.

## Scale

The config cell holds every tunable. It already runs at the maximum the shipped data file allows —
12 checkpoints, 8 candidates, 2000 bootstrap replicates (the full artifact run used 48 checkpoints
and 15 candidates; those values are noted in the comments beside each parameter). The demo slice's
rho values therefore differ from the paper's 48-checkpoint numbers; the qualitative result is the
same.

## Restoring removed files

Nothing in this directory is marked for deletion, so there is nothing to restore. The only file the
run removed is the disposable local test virtualenv, rebuilt with the two commands under
**How to run → Locally**.
EOF
cat > .terminal_claude_agent_struct_out.json <<'EOF'
{
  "out_expected_files": {
    "notebook": "code_demo.ipynb",
    "mini_data_file": "mini_demo_data.json"
  }
}
EOF
ls -la
````

### [51] TOOL RESULT — Bash · 2026-09-22 08:22:11 UTC

```
{"stdout": "1\ncells 21 with outputs 9\nimages 1\ntotal 4837\ndrwxrwxrwx 4 root root 1078485 Sep 22 08:22 .\ndrwxrwxrwx 5 root root 2044252 Sep 22 08:17 ..\ndrwxrwxrwx 2 root root   25600 Sep 22 08:22 .aii\ndrwxrwxrwx 3 root root 1000156 Sep 22 08:09 .claude\n-rw-rw-rw- 1 root root  554358 Sep 22 08:22 .repl_agent.ptylog\n-rw-rw-rw- 1 root root     113 Sep 22 08:22 .terminal_claude_agent_struct_out.json\n-rw-rw-rw- 1 root root    3807 Sep 22 08:22 README.md\n-rw-rw-rw- 1 root root  172273 Sep 22 08:21 code_demo.ipynb\n-rw-rw-rw- 1 root root   74815 Sep 22 08:10 mini_demo_data.json", "stderr": "", "interrupted": false, "isImage": false, "noOutputExpected": false}
```

### [52] ASSISTANT · 2026-09-22 08:22:16 UTC

```
Done. Both deliverables are in the workspace and verified.

**`mini_demo_data.json`** (75 KB) — curated subset of one dataset (`screen_table`): 96 examples = 8 of the 15 registered candidates × 12 of the 48 graded panel checkpoints, spread across 4 lineages (F1/F2/F3 in-house edit arms + Hub models incl. an abliterated one), plus the `BL1_easy` logit-gap bar per checkpoint, the pre-registered expected signs and the bootstrap seed.

**`code_demo.ipynb`** (21 cells) — title → install cell (numpy/matplotlib behind the `google.colab` guard) → imports → GitHub-URL loader with local fallback → config cell → then one code cell per pipeline stage, each preceded by markdown:
- `src/statlib.py` helpers verbatim (Spearman, checkpoint bootstrap, `erank`, `rho_mde`, `winsorise_high` — no SciPy, as in the original)
- **S3.2 pre-screen** verbatim from `src/prescreen.py` (the hardened `open()` audit wrapper is the one thing dropped — no filesystem to guard in a notebook)
- **S3.3 effective rank** verbatim
- **S6 assembly** — `method.py`'s `_ex` / `build_screen_table_dataset` / `build_prescreen_dataset` / `build_rank_analysis_dataset` / `build_stability_dataset` verbatim, fed the in-memory stage results instead of `results/*.json`
- results cell: pre-screen table + 4-panel figure (|rho| vs the 0.50 drop line, z-scored candidate×checkpoint matrix, singular-value spectrum with/without `BL1_easy` partialled out, leading-component loadings)

Test run in a clean 3.12 venv passed first try, **2m18s** end to end including installs (budget 10 min). Output reproduces the artifact's qualitative findings on the slice: 3 candidates dropped as collinear with the logit gap (G1 −0.63, G2 +0.59, G3 +0.54), 5 kept, and **P1 not supported** (erank entropy 3.87 vs threshold 1.5; |cos| 0.609 vs 0.8).

No scaling rounds were needed — the config already runs at the maximum the shipped data allows (12 checkpoints, 8 candidates, 2000 bootstrap replicates); the full-run values (48 checkpoints, 15 candidates) are in comments beside each parameter, and a note in the results markdown states that the slice's rho values differ from the paper's 48-checkpoint numbers.

Also wrote `README.md` and `.aii/manifest.yaml` (`entries: []` — nothing heavy remains; the disposable `.nb_env` was deleted) and `.terminal_claude_agent_struct_out.json`.
```
