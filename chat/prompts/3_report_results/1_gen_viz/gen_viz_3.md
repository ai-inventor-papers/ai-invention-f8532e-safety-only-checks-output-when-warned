# gen_viz_3 — report_results

> Phase: `gen_paper_repo` · `gen_viz`
> Run: `run_YqmEFECOIR3D` — Specificity and Causality Audits for Activation-Based Safety Readouts
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_viz_3` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-22 07:28:14 UTC

````


<pasted_content id="fa8a">
<system-prompt>
<research_methodology>
Create figures that belong in a top-venue paper.

- Every figure needs a clear takeaway visible at a glance.
- Choose chart types that match the data relationship (comparisons, trends, correlations, distributions).
- Include uncertainty (error bars, confidence intervals) when showing experimental results.
- Keep it clean — no clutter, clear labels with units, readable at print size.
</research_methodology>

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
Your workspace: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_2_gen_viz/gen_viz_3`

CRITICAL: Every file you create, write, or save MUST be inside this workspace directory (subdirectories OK). You MUST NOT write files anywhere outside this path — external paths are READ-ONLY. Use absolute paths for all file operations.

EVERY file write MUST start with `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_2_gen_viz/gen_viz_3/`:
GOOD: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_2_gen_viz/gen_viz_3/file.py`, `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_2_gen_viz/gen_viz_3/results/out.json`
BAD: `/tmp/file.py`, `~/output.json`, `./file.py`, any path outside the workspace
</workspace>
<disposable_outputs>
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
<task>
Render a publication-quality DATA figure for a top-tier venue research paper.

This figure plots numbers, so it is RENDERED from those numbers — not drawn by an image model. Use the aii-data-fig-gen skill. The output is deterministic: run it once, look at it, fix the spec if the data or labels are wrong, run it again.

STEPS:
1. Read the skill: `.claude/skills/aii-data-fig-gen/SKILL.md`.
2. Pick the chart type that fits the specification below. `python <skill>/scripts/chart_gen.py --list-types` lists them; `--example <type>` prints a complete spec to copy.
3. Write your spec to `fig_displacement_spec.json` in your workspace. Put EVERY numeric value from the specification into it — the spec is the figure.
4. Render it:
   `python <skill>/scripts/chart_gen.py --spec fig_displacement_spec.json --out fig_displacement_v0`
   That writes `fig_displacement_v0.pdf` (the deliverable, vector) and `fig_displacement_v0.png` (for you to look at).
5. READ THE PNG BACK and check it against the checklist below.
6. If anything is wrong, edit the spec and re-render. Repeat until clean — this is cheap and deterministic, so there is no attempt limit and no reason to accept a flawed figure.

DELIVERABLE: `fig_displacement_v0.pdf` in your workspace root. Leave `fig_displacement_spec.json` there too — it is the figure's source, and the step files it next to the figure so the figure stays reproducible.

Verification checklist (after EVERY render) — these are the things only you can check, because they are about whether the figure says what you meant:
- Every number in the figure matches the specification — no invented or dropped values
- Axis labels state what is measured AND its units
- Axis ranges make the comparison readable rather than flattening it
- The chart type still makes the point once you can see it drawn
- The caption describes what is actually drawn

The generator already REFUSES the rest rather than shipping them, so a figure you can read back cannot have them: overlapping or cut-off labels, a legend covering the data, a series drawn without a name beside named ones, two series a reader cannot tell apart, and a fit or a scale that the data cannot support. When it exits non-zero the message names the exact key, index or label and what to change — do that rather than re-rolling.

Reach for a generator first, and hand-write only if none fits. Every type in `--list-types` already carries the house style, the data-integrity checks and the layout fixes, so using one is less work than plotting by hand and the result matches every other figure in the paper.

If nothing in the catalogue fits, writing matplotlib yourself is expected and supported — novel figures exist. When you do, import the house style AND its layout passes so the figure still belongs to the set — `apply_house_style`, `place_legend`, `place_point_label`, `fit_legends`, `clear_legends_of_data`, `fit_tick_labels`, `fit_titles`, `rasterize_dense_clouds`, `assert_legends_clear_of_data`, `assert_series_are_distinguishable`, `assert_axis_names_are_unique` from `chart_style`, and `fit_point_labels` + `assert_text_is_legible` from `chart_geometry`, the last of which raises if any label ends up printed over another or cut off at the edge. Build legends with `place_legend` and point names with `place_point_label` — a legend made with a bare `ax.legend` cannot be reflowed when it turns out too wide, and a name written with a bare `ax.annotate` will not be moved off the marker it landed on. The "Use a generator when one fits" section of SKILL.md has the exact snippet and the order to call them in. What you lose is the automatic checking that the picture agrees with the numbers, so verify every value yourself against the specification.
</task>

<figure_specification>
Figure ID: fig_displacement
Title: Displacement Comparison
Caption: Median no-op displacement (in null standard deviations) for each readout class. The logit baseline operates 6.2$\times$ further from zero than the median activation readout, explaining its higher false-alarm rate. Error bars show interquartile range across readouts within each class.
Data and chart description: Horizontal bar chart on white background. Y-axis has 5 bars from top to bottom, each labeled: 'BL1_truelogit' (value 0.178), 'BL1_hard' (value 0.174), 'BL1_easy' (value 0.150), 'BL1_truelogit_hard' (value 0.092), 'Activation median' (value 0.024). X-axis: 'Median displacement (null SD)', range 0.00 to 0.20, ticks at 0.00, 0.05, 0.10, 0.15, 0.20. Top 4 bars colored orange (logit readouts). Bottom bar colored blue (activation readouts). A vertical dashed gray reference line at x = 0.024. An annotation arrow pointing from the BL1_easy bar to the Activation median bar with text '6.2x'. Values printed at the end of each bar: 0.178, 0.174, 0.150, 0.092, 0.024. Sans-serif font, clean minimal design, white background.
Aspect Ratio: 21:9
Summary: Shows logit baselines displace 6x more than activation readouts on no-ops, explaining specificity gap.
</figure_specification>


<evidence_check>
CRITICAL — this run's own final audit says its headline result is NOT supported:
the final review is marked blocking; the final hypothesis update recorded evidence_state='weak_or_null'. The figure specification above was written from a paper draft
that may therefore quote numbers no run ever produced.

Before you plot ANY number, find the artifact output file it is supposed to come from
and read the value there. Plot only values you have read back from an artifact output
file. If a value in the specification above is not in any results file — or the results
file holds far fewer examples, methods or conditions than the specification implies —
do NOT invent it and do NOT carry it over: draw only the series the data actually
supports, and say what the figure covers in its caption.

A figure whose bars disagree with the run's own output files is worse than a missing
figure, because nothing downstream can detect it.
</evidence_check>


---

Output the result as JSON to: `./.terminal_claude_agent_struct_out.json`

JSON Schema:
```json
{
  "$defs": {
    "VizExpectedFiles": {
      "description": "Expected output files from viz generation.",
      "properties": {
        "image_path": {
          "description": "Path to the generated figure image file. Example: 'fig1_v0.jpg'",
          "title": "Image Path",
          "type": "string"
        }
      },
      "required": [
        "image_path"
      ],
      "title": "VizExpectedFiles",
      "type": "object"
    }
  },
  "description": "Structured output from viz figure generation agent.",
  "properties": {
    "title": {
      "description": "Figure title in plain, everyday language \u2014 short and jargon-free so a non-expert grasps it at a glance. Aim for about 4-8 words (~40 characters).",
      "maxLength": 90,
      "minLength": 12,
      "title": "Title",
      "type": "string"
    },
    "summary": {
      "description": "Brief summary of the generated figure: what it shows, style, any issues fixed",
      "maxLength": 5000,
      "minLength": 500,
      "title": "Summary",
      "type": "string"
    },
    "out_expected_files": {
      "$ref": "#/$defs/VizExpectedFiles",
      "description": "Output file you created. Must include the generated figure image path."
    }
  },
  "required": [
    "title",
    "summary",
    "out_expected_files"
  ],
  "title": "VizFigureOutput",
  "type": "object"
}
```

IMPORTANT: this task is NOT complete until `./.terminal_claude_agent_struct_out.json` exists and contains JSON matching the schema above.

qwen3 4B on huggingface has base model also official safety finetuned version and there is a community finetuned uncensored model called abliterated (use the 4B size of each so they fit on a 16GB GPU). take these models and do a mech interp analysis of how they differ in activation. also find some patterns in internal computation on safety prompts. and possibly create a new metric for safety. so that for any random model on huggingface you would not need to run the full benchmarks, but only this metric on 0- to few prompts and get a safety evaluation

invariant: the deliverable is the activation-level comparison of the three models and any metric built from it must read activations or weights of a single model. logit-only or text-only readouts are baselines, not the result. this is a mech interp study of where safety lives, not a jailbreak or attack-selection study; do not reframe it as one.
</prompt>
</pasted_content id="fa8a">
````

### [2] SYSTEM-USER prompt · 2026-09-22 07:28:26 UTC

```
Search the run directory /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/ (READ-ONLY; do not write anything anywhere except you may write scratch notes to /tmp/claude-0/) for the artifact output files backing a figure called "fig_displacement".

The figure spec (from a paper draft, possibly unreliable) claims: median no-op displacement in null standard deviations for readout classes:
- BL1_truelogit = 0.178
- BL1_hard = 0.174
- BL1_easy = 0.150
- BL1_truelogit_hard = 0.092
- Activation median = 0.024
and a "6.2x" ratio (0.150 / 0.024 = 6.25), plus IQR error bars across readouts within each class.

Your job:
1. Locate the results/output JSON/CSV files (likely under iter_4 or iter_5 exec dirs, e.g. no-op set / widescreen screen / noopset exec directories) that contain per-readout displacement values on no-op pairs (things named like BL1_easy, BL1_hard, BL1_truelogit, W1..W3, G1..G4, A3, N1, N6, DiM etc.).
2. Read the ACTUAL numbers. Report: exact file paths, the exact field names, and the exact values for each of the 5 spec entries (or the nearest real equivalent). Also report whether IQR / quartiles across readouts within a class can be computed (i.e., how many activation readouts and how many logit readouts exist, and their individual displacement values so I can compute medians and IQRs myself).
3. If the numbers differ from the spec, say so clearly and give the real ones. If no such file exists at all, say so.

Useful search commands: grep -rl 'BL1_easy' <dir>, grep -rl 'displacement' <dir> --include=*.json --include=*.py --include=*.csv, find for *.json under exec dirs.

Return a concise text report with: file paths, per-readout values (full list with names), and which are logit-based vs activation-based readouts (check the code that defines them). Include raw numbers, not summaries. Do not paste huge logs.
```
