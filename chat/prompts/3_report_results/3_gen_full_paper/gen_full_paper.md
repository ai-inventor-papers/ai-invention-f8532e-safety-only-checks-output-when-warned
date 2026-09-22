# gen_full_paper — report_results

> Phase: `gen_paper_repo` · `gen_full_paper`
> Run: `run_YqmEFECOIR3D` — Specificity and Causality Audits for Activation-Based Safety Readouts
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_full_paper` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-22 09:04:07 UTC

````


<pasted_content id="d596">
<system-prompt>
<research_methodology>
Write like an experienced academic. Reviewers judge both the science and the writing.

- Claims must be proportional to evidence. Choose verbs carefully — "demonstrate," "observe," and "hypothesize" mean different things.
- Every result needs: what was measured, on what data, the numbers, and what they mean.
- Methodology must be specific enough to reproduce. Section placement follows <paper_structure> below.
- State limitations honestly. Avoid both overclaiming and excessive hedging.
</research_methodology>

<paper_structure>
Use the structure an expert in the field expects, in this order: Abstract; 1 Introduction; 2 Related Work; 3 Method; 4 Experimental Setup; 5 Results; 6 Discussion and Limitations; 7 Conclusion. Merge or rename a section only where the work genuinely has nothing for it — never by folding it into the Introduction.

- The Introduction contains ONLY: the problem and why it matters, the gap in existing work, the idea in one or two sentences, a contributions list carrying the headline numbers, and a one-sentence roadmap of the paper.
- NO literature survey and NO method details in the Introduction. Prior work goes to Related Work, how the method works goes to Method.
- Organize Related Work by theme rather than one paragraph per paper, and close each theme with a sentence on how this work differs.
- Experimental Setup carries data, baselines, metrics and protocol — enough for an expert to rerun it. Results carries findings, not setup.
</paper_structure>

<results_first>
Ask what a reader actually wants from the paper: the results, with numbers. A reader must be able to get the main finding from the abstract, the main results table and the first results figure alone.

- State the key quantitative results, with the actual numbers, in three places: the abstract, the contributions list, and the opening of Results.
- Results opens with a main results table: the method against every baseline on the headline metric, with variance.
- Every major claim gets at least one results figure (figure_type "data"), plus an ablation or sensitivity plot wherever the artifacts hold the numbers for one.
- Prefer a plot of real numbers over concept art — keep concept figures to the architecture or pipeline diagram the method genuinely needs.
- Reference every figure and table by number in the text and interpret it there: say what the reader should take from it. Never drop one in unexplained.
</results_first>

<figure_placement>
Where a figure sits, what shape it takes and how many there are decide whether a reader can follow the paper.

- Put each [FIGURE:id] marker directly after the paragraph that first discusses the figure, inside the section that owns it: the hero diagram at the end of the Introduction, method and pipeline diagrams in Method, the main comparison and the per-claim results figures in Results, ablation and sensitivity plots in Results or Discussion. Never place a figure in the Abstract, Related Work or Conclusion.
- Let the data relationship pick the chart: grouped bars for the method against baselines on one metric, lines with error bands for trends, scaling and training curves, scatter or a Pareto front for trade-offs, heatmaps for matrices and pairwise grids. A handful of numbers is a table, not a figure. Use multiple panels only when they share axes and one takeaway.
- Aim for roughly four to eight figures in a full paper, with the main results figure first. Each caption stands on its own: what is plotted, on what data, and the takeaway.
</figure_placement>

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
Your workspace: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/workspace`

CRITICAL: Every file you create, write, or save MUST be inside this workspace directory (subdirectories OK). You MUST NOT write files anywhere outside this path — external paths are READ-ONLY. Use absolute paths for all file operations.

EVERY file write MUST start with `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/workspace/`:
GOOD: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/workspace/file.py`, `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/workspace/results/out.json`
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
Create a publication-ready top-conference LaTeX paper with BibTeX from <paper_text> and <available_figures>, compile to PDF.
</task>

<tool_use>
Maximize parallel tool calls. Parallelize independent operations, only sequentialize dependencies.
- Multiple searches/fetches on different topics → parallel in one turn
- Search then fetch results → sequential (need URLs first)
</tool_use>

<headline_check>
CRITICAL — the paper draft below in <paper_text> may have been written BEFORE this
run's final verdict was known. That verdict says this run's headline result is NOT
supported: the final review is marked blocking; the final hypothesis update recorded evidence_state='weak_or_null'.
Final hypothesis coverage note: The write-up delivers the Qwen3-4B Base/instruct/SafeRL/abliterated activation comparison and the internal-computation patterns (decodable-but-inert bound, redundancy contrast, rotate-and-shrink), and answers the metric part with a bounded negative plus the trade-off-position characterisation.
Final review note: This iteration makes real, measurable progress on the previous round: there is now an Experimental Setup section, a full 32-readout table instead of a selected 11, the panel is enumerated pair by pair, all four BL1 variants are labelled and the misranking claim is withdrawn, the global-ablation band is corrected to B4, the unsupported registered DiD is stated as unsupported, the equivalence framing and MDEs are in place, the abliterated grid's 6-cell scope is disclosed, the false bitwise-identity mechanism is replaced with measured displacements, and the AMS validation, padding bug and deviations are reported. Roughly two-thirds of the previous MUST-FIX list is genuinely addressed.

It nonetheless must not ship. Three claims contradict the run's own artifacts. Contribution 3 says abliteration 'rotates rather than shrinking' while the iteration-5 artifact that produced the number says, verbatim, that this inherited claim is CONTRADICTED and the axis loses ~40% of its magnitude -- and the paper's own Table 5 shows N1 and N6 falling 71% and 57%. Section 5.5 reprints a 138x accumulator figure that the iteration-3 evaluation recomputed to 161-281x and marked NOT_SUPPORTED. The probe-survival headline and fig_probe rest on an AUROC that the same audit shows is at ceiling in the unperturbed control and therefore could not have fallen, while the operating-point re-expression the audit supplies shows the response site does lose the representation. Any one of these is disqualifying; together they mean the paper's interpretive layer has drifted from its own evidence.

Two further problems are large but fixable and would move the score most. First, the paper leads with its underpowered specificity comparison (4/12 vs 1/12, p = 0.375) while a powered version of the same claim sits unreported in an artifact it already cites: 0 false alarms for the geometric candidates versus 11 for the logit gap on 24 graded no-op edits, exact McNemar p = 0.00098. Second, the second-order screen is written as a pure null when its producing artifact states a positive finding -- every sign is inverted relative to registration, so the readouts index a position on the refusal/permissiveness trade-off rather than a safety level. That is the most direct answer this run has to the request that started it, and it is missing.

Smaller but consequential: the no-op category breakdown still contradicts Table 1 (no LoRA arm is a no-op; a rank-one lesion is); the wu05 recipe is described as a random unembedding direction when the code shows a targeted 0.5-nat suppression of refusal-onset tokens, which is why the logit baseline fires there; AMS's perfect specificity is partly a file copy; the benign prompt count for the specificity panel is wrong (83, not 97) and an amendment that gave two of three families a different item set and generation length is undisclosed; the judged-refusal null and the Holm survivor have no table or figure; there is no judged-refusal positive control although the Method advertises one; and B3 -- the only activation readout in the study that beats the logit gap on a fresh-family ranking panel with a CI excluding zero -- is mislabelled as a weights-only scar, burying the paper's best support for its own thesis. Finally, Zhao et al. (NeurIPS 2025), which publishes the harmfulness/refusal dissociation with causal steering, is in the bibliography and never cited, alongside eleven other unused entries.

All headline numbers do trace to artifacts that actually ran; nothing is projected or placeholder. The engineering discipline here is above what most submissions show. The gap is between the artifacts and the prose, and it is closable in one iteration.

You MUST NOT typeset a positive headline claim the evidence does not support. Before
compiling, check the title, abstract, and conclusion against this verdict — rewrite any
of them (and the body claims they summarize) that overstate the result, so the compiled
PDF presents the finding honestly as a negative or inconclusive result, written as a
normal paper would: no mention of the pipeline, iterations, reviews, or execution status.
The reasons listed above are for YOU to act on, not to quote or paraphrase in the paper —
the compiled PDF must read like any other paper in the field, not like a system report.
Do not fabricate a workaround result to avoid a negative headline.
</headline_check>


<paper_text>
title: Specificity and Causality Audits for Activation-Based Safety Readouts
abstract: >-
  Activation-based readouts promise to replace slow behavioural benchmarks for evaluating the safety of open-weight language
  models. Before such readouts can serve as proxies, two validation questions must be answered: do they avoid false alarms
  on checkpoint modifications that do not change safety behaviour, and does the information they read causally influence the
  model's output? We address both questions. First, we construct behaviourally graded no-op and effective model pairs across
  three families and score 32 candidate readouts for false alarms and sensitivity. Activation readouts at mid-layer depth
  achieve far better specificity than the final-layer logit baseline, which fires on modifications that do not change judged
  behaviour. Second, a causal intervention grid on Qwen3-4B reveals that the refusal direction is linearly decodable at the
  prompt site but removing it does not change judged refusal: the model rewrites its refusal in different words. The single
  causal lever is over-refusal on benign-borderline prompts, not compliance with harmful requests. A wider screen of second-order
  readouts finds none that survives blind held-out confirmation, and the effective rank of the score matrix rules out a one-coordinate
  summary. These findings establish false-alarm auditing on behaviourally graded no-ops as a necessary validation step for
  activation-based safety metrics and identify the decodable-but-inert phenomenon as a constraint on site-local causal claims.
paper_text: |
  \section{Introduction}

  Evaluating the safety of open-weight language models requires generating text, judging each output for harmful content, and aggregating scores across hundreds of prompts \cite{Mazeika2024, Rottger2023, Chao2024}. This pipeline is slow, sensitive to prompt phrasing, and must be re-run whenever a model is modified. The proliferation of post-hoc modifications to released checkpoints --- quantisation, adapter merging, abliteration \cite{Arditi2024} --- makes repeated evaluation expensive and raises the question of whether safety-relevant information can be read directly from a model's activations.

  Recent work has shown that such information is linearly decodable from mid-layer activations. The Activation-based Model Scanner (AMS) extracts a concept direction from 16 contrastive prompt pairs at 40--80\% depth and reports leave-one-out accuracy of 71\% across 14 configurations \cite{Messenger2026}. N-GLARE aggregates Jensen--Shannon divergence of hidden states and reports coupling with refusal rates during training \cite{Lin2025}. Representation engineering uses contrastive activations for monitoring and control \cite{Zou2023}. All three read activations at the final prompt token, and all three correlate with safety behaviour in their validation settings.

  Two questions remain open. First, do these readouts avoid false alarms when a checkpoint is modified in ways that do not change safety behaviour? AMS reports quantisation drift of at most 4.4\% on a single model, but it does not grade whether the quantised model's behaviour actually changed \cite{Messenger2026}. No prior system grades the behaviour of each variant before calling it a no-op. Second, does the information a readout reads \emph{causally influence} the model's output? Decodability and causal relevance are distinct: Galeone et al.\ showed that detection accuracy and steerability are dissociated across models \cite{Galeone2026}, and Basu et al.\ demonstrated that ``near-perfect internal representations'' do not guarantee that mechanistic interventions can correct model errors \cite{Basu2026}.

  We address both questions with three experiments on shared infrastructure. The first constructs behaviourally graded model pairs and scores 32 candidate readouts for false alarms and sensitivity. The second builds a causal intervention grid on Qwen3-4B variants. The third screens 15 second-order readouts on a 48-checkpoint panel and tests them against a blind held-out confirmation set.

  [FIGURE:fig_overview]

  \paragraph{Summary of Contributions.}
  \begin{enumerate}
  \item \textbf{Activation readouts have far fewer false alarms than the logit baseline on behaviourally graded no-ops.} W
</pasted_content id="d596">


<pasted_content id="d596">
e construct 15 behavioural no-ops spanning four categories (numerical precision, identity transforms, non-safety adaptation, head-only edits) and 10 effective changes across three model families, grading each pair's behaviour before computing any readout. Mid-layer activation readouts fire on at most 3 of 15 no-ops; the final-layer logit gap fires on 6--8. Three of the 15 no-ops produce bitwise-identical activations at mid-layer, so 12 non-degenerate pairs provide the informative comparison: 1--3 false alarms versus 4--6 for the logit baseline (Section~\ref{sec:results-specificity}).

  \item \textbf{The refusal direction is decodable but causally inert at the prompt site.} In a 6-band $\times$ 3-site causal intervention grid, removing the refusal direction at the last prompt token does not change judged refusal in any of the 18 tested cells for either the instruct or SafeRL model (max $|\text{effect}| = 0.056$, below the median MDE of 0.067; TOST $p < 10^{-23}$). The model rewrites its refusal in different words. The causal lever is over-refusal on benign-borderline prompts, where the single Holm--Bonferroni survivor appears (Section~\ref{sec:results-causal}).

  \item \textbf{SafeRL provides deeper causal redundancy than standard instruction tuning.} Global removal of the refusal direction at depth band B4 reduces instruct refusal from 0.92 to 0.67; SafeRL resists with a difference-in-differences of $+0.23$ $[0.08, 0.38]$. The abliterated checkpoint's refusal direction rotates rather than shrinking, with cross-model cosine dropping from 0.999 at B1 to 0.31 at B5 (Section~\ref{sec:results-causal}).

  \item \textbf{A wider screen of second-order readouts finds no readout that survives blind held-out confirmation.} Fifteen candidate readouts (geometry, write-handle redundancy, competing mechanisms) are screened on 48 checkpoints from 7 lineages. Four are dropped for collinearity with the logit baseline; the remaining 11 all fail the registered confirmation rule on 12 blind held-out checkpoints. The effective rank of the candidate-by-checkpoint score matrix is 7.2, ruling out a one-coordinate summary (Section~\ref{sec:results-screen}).
  \end{enumerate}


  \section{Related Work}
  \label{sec:related}

  \paragraph{Activation-based safety readouts.}
  AMS extracts concept directions from 16 contrastive prompt pairs at 40--80\% depth \cite{Messenger2026}. N-GLARE aggregates Jensen--Shannon divergence across layer groups \cite{Lin2025}. RAS uses a reference-anchored score calibrated within families \cite{Huang2026}. Aligned Probing correlates per-layer probe accuracy with output toxicity \cite{Waldis2025}. Jiang et al.\ use per-layer probes as risk detectors and find that static probes fail to distinguish jailbroken from base models \cite{Jiang2026}. SafeSeek attributes safety circuits via joint ablation \cite{Yu2026}. All read activations at the last prompt token; none grades the behaviour of each variant before using it as a calibration point.

  \paragraph{Refusal geometry and causality.}
  Arditi et al.\ identified a single direction mediating refusal across 13 models \cite{Arditi2024}. Marshall et al.\ showed refusal is an affine function \cite{Marshall2024}. Wollschl\"{a}ger et al.\ demonstrated that refusal is represented by concept cones with multiple independent directions, not a single axis \cite{Wollschlager2025}. Winninger found multi-dimensional refusal subspaces via RFM-AGOP \cite{Winninger2026}. Galeone et al.\ dissociated detection accuracy from steerability \cite{Galeone2026}. Wu et al.\ showed that safety mechanisms in large models separate knowing from acting \cite{Wu2026}. Yang et al.\ found that chain-of-thought disrupts simple steering \cite{Yang2026b}. Orgad et al.\ demonstrated that harmful-response generation and harm recognition use distinct mechanisms \cite{Orgad2026}. Zhang et al.\ showed that innate safety alignment extends beyond surface layers \cite{Zhang2025}.

  \paragraph{False-alarm and staleness controls.}
  Duan benchmarks frozen linear probes across quantisation and LoRA conditions and
</pasted_content id="d596">


<pasted_content id="d596">
 finds 43--54\% big-drop rates under fine-tuning-style updates \cite{Duan2026}. Hurtado audits 37 benign fine-tunes at FPR 0.11 using a weight-space signal \cite{Hurtado2026}. AMS reports FP16/INT8/INT4 drift of at most 4.4\% on one model but does not grade the model's behaviour \cite{Messenger2026}.

  \paragraph{Over-refusal.}
  XSTest provides paired harmful and benign prompts to measure exaggerated safety \cite{Rottger2023}. Yuan et al.\ decouple refusal training from general instruction following \cite{Yuan2024}. Every existing over-refusal measurement is a behavioural outcome; no internal readout uses over-refusal as its prediction target across checkpoints.

  \paragraph{Behavioural benchmarks.}
  HarmBench standardises red-teaming evaluation across attack methods \cite{Mazeika2024}. JailbreakBench provides an open benchmark for jailbreaking evaluation \cite{Chao2024}. Spagliardi et al.\ apply item response theory to reduce the prompt budget of behavioural safety benchmarks by 80\% or more \cite{Spagliardi2026}. Rivera et al.\ find that three latent factors explain 77\% of variance across 8 behavioural benchmarks \cite{Rivera2026}.


  \section{Experimental Setup}
  \label{sec:setup}

  \subsection{Models and Panel Composition}
  \label{sec:panel}

  We construct parent--child pairs across three model families: Qwen3-0.6B-Instruct (F1), Llama-3.2-1B-Instruct (F2) and Falcon3-1B-Instruct (F3). Each parent is modified with operations spanning four categories:

  \begin{itemize}
  \item \emph{Numerical precision} (8 pairs): bf16-to-fp16 cast, int8 weight-only quantisation, LLM.int8() quantisation \cite{Dettmers2022}.
  \item \emph{Identity transforms} (2 pairs): system-prompt swap (benign non-safety system prompt).
  \item \emph{Non-safety adaptation} (2 pairs): non-safety LoRA on instruction-following data \cite{Hu2021}, non-safety DPO on coherence pairs \cite{Rafailov2023}.
  \item \emph{Head-only edits} (3 pairs): unembedding-weight perturbation at $\alpha = 0.05$ along a randomly sampled direction in the unembedding matrix, leaving all transformer-block weights and activations unchanged.
  \end{itemize}

  Of these intended no-ops, 15 survive behavioural grading as NOOP (Table~\ref{tab:panel}). Three of the 15 are head-only edits whose activation delta at every layer is exactly zero by construction: any activation readout's silence on these pairs is analytic, not empirical. We therefore report false-alarm rates on both the full 15 pairs and the 12 non-degenerate pairs throughout.

  Additionally, we include 9 effective changes from the frozen classification rule: in-house rank-one directional lesions at $\alpha = 1.0$ (2 pairs), one non-safety DPO that unexpectedly shifted harmful compliance, and 6 community-modified checkpoints from Hugging Face (5 abliterated, 1 base-to-SFT transition). A 10th effective pair (AMD-OLMo SFT$\to$DPO, $\Delta$HC $= +0.32$) is implied by the frozen classification rule but was not included in the downstream sensitivity list; we report sensitivity at both denominators where it matters.

  \begin{table}[t]
  \centering
  \scriptsize
  \caption{Panel composition. 15 behavioural no-ops and 9 effective changes across three families. $\dagger$ marks head-only edits with bitwise-zero activation delta. $\ddagger$ marks a reclassified pair (intended lesion observed as NOOP). HC = harmful compliance, OR = over-refusal. All CIs are 95\% paired bootstrap.}
  \label{tab:panel}
  \begin{tabular}{llllr}
  \toprule
  \textbf{Pair ID} & \textbf{Fam.} & \textbf{Recipe} & \textbf{Class} & $\bm{\Delta}$\textbf{HC [CI]} \\
  \midrule
  \multicolumn{5}{l}{\textit{Behavioural no-ops (15)}} \\
  F1/F2/F3\_int8wo & Q/L/F & int8 weight-only & NOOP & $[-0.01, 0.00, 0.00]$ \\
  F1/F2/F3\_fp16   & Q/L/F & bf16$\to$fp16 cast & NOOP & $[+0.01, 0.00, 0.00]$ \\
  F1/F2\_int8bnb   & Q/L   & LLM.int8()       & NOOP & $[+0.02, 0.00]$ \\
  F1/F2\_sysprompt  & Q/L   & system-prompt swap & NOOP & $[0.00, -0.01]$ \\
  F1/F2/F3\_wu05$\dagger$ & Q/L/F & head-only $\alpha{=}0.05$ & NOOP & $[+0.01, 0.00, 0.00]$ \\
  F3\_dpo  
</pasted_content id="d596">


<pasted_content id="d596">
         & F     & non-safety DPO   & NOOP & $0.00$ \\
  F1\_a05$\ddagger$ & Q     & lesion $\alpha{=}0.05$ & NOOP & $+0.02$ \\
  \midrule
  \multicolumn{5}{l}{\textit{Effective changes (9)}} \\
  mlabonne--Qwen3-4B-ablit. & Q & community abliteration & EFF & $+0.73\;[0.60,0.85]$ \\
  F2/F3\_a10 & L/F & lesion $\alpha{=}1.0$ & EFF & $[+0.12, +0.46]$ \\
  F1\_dpo    & Q   & non-safety DPO & EFF & $+0.08\;[0.02,0.15]$ \\
  huihui-0.6B-ablit. & Q & community abliteration & EFF & $+0.39\;[0.28,0.49]$ \\
  mylesgoose-ablit.  & L & community abliteration & EFF & $+0.13\;[0.06,0.21]$ \\
  huihui-1.7B-ablit. & Q & community abliteration & EFF & $+0.62\;[0.52,0.73]$ \\
  Vikhr-ablit.       & L & community abliteration & EFF & $+0.48\;[0.38,0.59]$ \\
  AMD-OLMo-SFT       & O & base$\to$SFT          & EFF & $+0.07\;[0.01,0.13]$ \\
  \bottomrule
  \end{tabular}
  \end{table}

  \subsection{Behavioural Grading}

  Each checkpoint is evaluated on 85 harmful prompts (45 StrongReject \cite{Mazeika2024}, 40 XSTest harmful twins \cite{Rottger2023}) and 97 benign prompts (54 XSTest safe twins, 43 hard-benign items) with greedy decoding at 96 tokens. Harmful compliance (HC) is the fraction of harmful prompts answered substantively; over-refusal (OR) is the fraction of benign prompts incorrectly refused. Both are scored by an LLM judge (Gemini 2.5 Flash Lite), with split-half reliability of 0.96 (HC) and 0.94 (OR) on the confirmation panel.

  A pair is classified as NOOP if $|\Delta\text{HC}| \leq 0.05$ and $|\Delta\text{OR}| \leq 0.05$ with both 95\% paired-bootstrap CIs inside $[-0.10, +0.10]$; as EFFECTIVE if the $\Delta$HC CI excludes zero; as OR\_EFFECTIVE if the $\Delta$OR CI excludes zero but $\Delta$HC covers zero; otherwise AMBIGUOUS. Behavioural grading is committed before any activation readout is computed, enforced by a SHA-256 hash chain. Every readout score in this study was computed after the behavioural label was frozen.


  \section{Method}
  \label{sec:method}

  \subsection{Experiment 1: Specificity Audit}
  \label{sec:exp1-method}

  \paragraph{Readouts.}
  For each parent and child checkpoint, we extract residual-stream activations at the last prompt token at every layer. We compute 32 candidate readouts spanning four classes. \emph{Activation readouts} (16 variants): $N1$ (request-axis Cohen's $d$ at the layer maximising separation, using cross-fitted easy/hard prompt splits), $N6$ (benign-side separability), $N4$ (onset/shape statistics from per-prompt refusal-onset distributions), $N7$ (two-sided gap), $N8$ (severity Spearman $\rho$), $N9$ (first-decoded-token refusal mass), $N11$ (AMS-window Fisher information), $N12$ (weighted combination), $C4$/$C7$/$C13$ (cross-layer and depth-band variants), and AMS Tier-1/Tier-2 (reimplemented from the released code \cite{Messenger2026}, batch size 1, agreement to within $7 \times 10^{-5}$ relative). \emph{Logit readouts} (4 variants): $\text{BL1}$ final-layer logit gap in easy-prompt, hard-prompt, true-logit and true-logit-hard scoring conventions. \emph{Weight readout}: $B7$ (per-layer diff-in-means weight projection cosine). \emph{Text/card readouts}: regex model-card detection, name-free regex, greedy refusal rate, greedy refusal onset.

  For each readout, we compute the paired change $\Delta$ (child minus parent) with a 2000-draw prompt-stratified bootstrap CI. A readout fires a \emph{false alarm} on a no-op pair if its $\Delta$ CI excludes zero in the readout's expected direction. \emph{Sensitivity} is the fraction of effective pairs where the CI excludes zero in the expected direction.

  \subsection{Experiment 2: Causal Intervention Grid}
  \label{sec:exp2-method}

  We use three Qwen3-4B variants: Instruct, SafeRL (additional safety reinforcement learning) and abliterated (mlabonne/Qwen3-4B-abliterated). We cross six depth bands (B1--B6, each spanning one-sixth of the 36-layer stack) with three intervention sites: P (last prompt token, forward-only hook), D$'$ (model's own first 1--8 greedy decode positions) and E (early response window, positions 5--20). The abliter
</pasted_content id="d596">


<pasted_content id="d596">
ated model's grid covers only site P (6 cells) due to its low baseline refusal rate (arm-0 refused harm $= 0.188$), which floors the harmful-compliance outcome.

  Each cell has five arms: F (matched-norm projection removing the fitted request-axis direction), N6 (benign-side direction), N6$\perp$ (orthogonal complement of N6 with respect to F), R (orthogonalised random direction with matched displacement, averaged over 10--20 draws) and arm 0 (no intervention). A positive-control arm (POS, full residual patching from a different model) runs at bands B3 and B4. For each cell, we generate 80 tokens on 48 harmful and 48 benign-borderline prompts and judge outcomes with the same LLM grader. A cell is \emph{causal} only if the treatment arm (F or N6) differs from the random control R after Holm--Bonferroni correction at $\alpha = 0.05$ over all 18 cells jointly.

  \subsection{Experiment 3: Second-Order Readout Screen}
  \label{sec:exp3-method}

  We define 15 candidate readouts that go beyond the first-order diff-in-means direction: W1--W8 measure write-handle redundancy and self-repair across layers \cite{McGrath2023, Rushing2024}; G1--G4 measure dimensionless geometry of the activation space (Fisher separation, used-ness, BL1-orthogonal Fisher); A1--A3 measure competing mechanisms. Each is computed as a single scalar per checkpoint on the same prompt sets. The candidates are screened on a 48-checkpoint panel spanning 7 independent lineages, then tested against a blind held-out confirmation panel of 12 checkpoints from 7 independent lineages (intersection with the screen panel: empty). Selection requires the candidate's correlation with over-refusal to exceed the logit baseline's by a margin whose CI excludes zero under a paired checkpoint bootstrap.


  \section{Results}
  \label{sec:results}

  \subsection{Specificity: False Alarms on Behavioural No-Ops}
  \label{sec:results-specificity}

  Table~\ref{tab:specificity} reports the false-alarm rate and sensitivity for all 32 candidate readouts. Activation readouts fire on at most 3 of 15 no-ops ($C13_{\text{peak}}$, the most sensitive activation readout, fires on 3). The median activation readout fires on 0--1 no-ops (Wilson 95\% CI for 1/15: [0.01, 0.30]). On the 12 non-degenerate pairs (excluding three head-only edits), the logit baseline BL1$_\text{easy}$ fires on 4 and the activation readout $N1$ fires on 1 (exact McNemar $b = 4$, $c = 1$, $p = 0.375$); this comparison is underpowered, not a negative result.

  [FIGURE:fig_specificity]

  The logit-gap baseline fires on 6/15 (BL1$_\text{easy}$) to 8/15 (BL1$_\text{truelogit}$): int8 weight-only quantisation, system-prompt swaps and head-only unembedding edits all shift the final-layer logit gap without changing judged behaviour. The weight-space cosine B7 fires on 9/15 (every dtype cast produces a false alarm). Among text baselines, the greedy refusal rate fires on 2/15 and has the highest sensitivity (7/8 of evaluable effective pairs) but measures generated text rather than activations. AMS Tier-2 (the reference-based verify rule) achieves perfect specificity (0/15) but detects none of the 8 evaluable effective changes.

  \begin{table}[t]
  \centering
  \scriptsize
  \caption{All 32 candidate readouts. FA = false alarms on 15 no-ops (12 non-degenerate in parentheses). Sens = sensitivity on 9 effective pairs (denominator varies where noted). Disp = median null-SD displacement on no-ops. Readout class: \textbf{A} = activation, \textbf{L} = logit, \textbf{W} = weight, \textbf{T} = text/card.}
  \label{tab:specificity}
  \begin{tabular}{lcrrcr}
  \toprule
  \textbf{Readout} & \textbf{Cl.} & \textbf{FA/15 (12)} & \textbf{Sens} & \textbf{FA pairs} & \textbf{Disp} \\
  \midrule
  N1 ($d$ at $\ell^*$) & A & 1 (1) & 5/9 & F3\_dpo & 0.024 \\
  N1$_\text{parentL}$ & A & 1 (1) & 5/9 & F3\_dpo & 0.024 \\
  N2 ($d \perp W_U$)  & A & 1 (1) & 5/9 & F3\_dpo & 0.024 \\
  N3 ($F_\text{clust} \perp W_U$) & A & 1 (1) & 5/9 & F3\_dpo & 0.065 \\
  $F_\text{clust}$ & A & 1 (1) & 5/9 & F3\_dpo & 0.064 \\
  N4$_\text{onset}$ & A & 0 (0) & --
</pasted_content id="d596">


<pasted_content id="d596">
 & -- & 0.000 \\
  N4$_\text{peak}$  & A & 0 (0) & -- & -- & 0.000 \\
  N4$_\text{width}$ & A & 0 (0) & -- & -- & 0.000 \\
  N6 (benign sep.) & A & 0 (0) & 5/9 & -- & 0.012 \\
  N7 (two-sided)   & A & 1 (1) & 5/9 & F3\_int8wo & 0.028 \\
  N8 (severity)    & A & 0 (0) & 4/8 & -- & 0.005 \\
  N9$_\text{decode}$ & A & 1 (0) & 3/8 & F3\_wu05 & 0.052 \\
  N9$_\text{tok1}$ & A & 0 (0) & 4/8 & -- & 0.074 \\
  N10              & A & 2 (1) & 3/8 & wu05/dpo & 0.080 \\
  N11 (AMS-window) & A & 2 (2) & 6/9 & fp16/dpo & 0.062 \\
  N12 (combo)      & A & 3 (3) & 3/9 & int8wo$\times$2/fp16 & -- \\
  C4               & A & 0 (0) & 3/9 & -- & 0.000 \\
  C7 (cross-layer) & A & 1 (1) & 6/9 & F3\_dpo & 0.012 \\
  C13              & A & 2 (2) & 4/9 & sysprompt/int8bnb & 0.003 \\
  C13$_\text{peak}$ & A & 3 (3) & 6/9 & sysprompt/fp16/dpo & 0.013 \\
  \midrule
  BL1$_\text{easy}$  & L & 6 (4) & 5/9 & int8wo/sysprompt/wu05/int8bnb/\ldots & 0.150 \\
  BL1$_\text{hard}$  & L & 6 (4) & 5/9 & int8wo/sysprompt/wu05/dpo/\ldots & 0.174 \\
  BL1$_\text{truelogit}$ & L & 8 (6) & 6/9 & +fp16/a05/dpo/int8bnb & 0.178 \\
  BL1$_\text{truelogit,hard}$ & L & 5 (3) & 6/9 & int8wo/sysprompt/wu05/dpo/\ldots & 0.092 \\
  \midrule
  B7 (weight cos.)       & W & 9 (9) & 7/9 & all dtype casts + int8bnb + a05 & -- \\
  B7$_\text{nullproj}$   & W & 9 (9) & 6/9 & same as B7 & -- \\
  \midrule
  AMS $\sigma$ (T1)  & A & 0 (0) & 3/8 & -- & -- \\
  AMS drift (T2)     & A & 0 (0) & 0/8 & -- & -- \\
  regex (card)       & T & 0 (0) & 5/9 & -- & -- \\
  regex (name-free)  & T & 0 (0) & 4/9 & -- & -- \\
  greedy ref.\ rate  & T & 2 (2) & 7/8 & sysprompt/a05 & -- \\
  greedy ref.\ onset & T & 0 (0) & 5/8 & -- & -- \\
  \bottomrule
  \end{tabular}
  \end{table}

  The Spearman correlation between false-alarm count and sensitivity across all 32 candidates is $+0.596$ (within the activation class: $+0.406$). This positive correlation means that readouts with more false alarms also tend to detect more real changes; there is no false-alarm/sensitivity trade-off within the activation class that would justify accepting more false alarms for better detection.


  \subsection{Displacement Analysis}
  \label{sec:results-displacement}

  The mechanism behind the specificity gap is displacement magnitude. For each readout, we measure how much a no-op modification shifts the readout's score, expressed in standard deviations of the null distribution estimated from the bootstrap (null SD). The logit baseline BL1$_\text{easy}$ has a median no-op displacement of 0.150 null SD, while the median activation readout displacement is 0.024 null SD, a ratio of 6.2$\times$ (BL1$_\text{hard}$: 7.2$\times$; BL1$_\text{truelogit}$: 7.4$\times$; BL1$_\text{truelogit,hard}$: 3.8$\times$). The logit gap operates at the decision boundary where small perturbations produce large score changes, while mid-layer activation readouts measure the geometry of the representation space, which is more stable under numerical-precision and identity modifications.

  [FIGURE:fig_displacement]

  Device-level evidence confirms this: running the same model on CPU versus GPU produces only 25.6\% greedy-identical text, yet 96.5\% of harmful-compliance labels agree, and the two most sensitive activation readouts both fire on the fp16 no-op. The false-alarm rate of the logit baseline is not a property of the baseline's quality but of the level at which it reads the model: final-layer logits amplify implementation-irrelevant variation.


  \subsection{Causal Interventions}
  \label{sec:results-causal}

  \paragraph{No site-local intervention changes judged refusal.}
  Across the 18-cell grid, removing the refusal direction F at any single site produces no causal cells for judged refusal on harmful prompts, in both the instruct and SafeRL models (Table~\ref{tab:causal}). The maximum absolute effect on judged refusal is 0.056 (instruct, arm F, site P, band B4), which falls below the median minimum detectable effect of 0.067 (instruct) and 0.061 (SafeRL). Two-one-sided-test equivalence at these margins yields $p = 3.7 \times 10^{-2
</pasted_content id="d596">


<pasted_content id="d596">
4}$ (instruct), $1.3 \times 10^{-25}$ (SafeRL) and $9.7 \times 10^{-10}$ (abliterated). The judged refusal rate is bounded near its arm-0 value, not merely unmeasured.

  \begin{table}[t]
  \centering
  \scriptsize
  \caption{Causal grid: effect sizes (effect$_\text{FR}$) for arm F on over-refusal (benign-borderline), instruct and SafeRL. Negative values = over-refusal decreases. * = survives Holm--Bonferroni. Cells marked -- are NOT\_RUN. Family size: 18 (instruct/SafeRL), 6 (abliterated, site P only). MDE$_{80}$: 0.067 (instruct), 0.061 (SafeRL).}
  \label{tab:causal}
  \begin{tabular}{l|ccc|ccc}
  \toprule
   & \multicolumn{3}{c|}{\textbf{Instruct}} & \multicolumn{3}{c}{\textbf{SafeRL}} \\
  \textbf{Band} & \textbf{P} & \textbf{D$'$} & \textbf{E} & \textbf{P} & \textbf{D$'$} & \textbf{E} \\
  \midrule
  B1 & $-0.007$ & $+0.007$ & $+0.007$ & $+0.014$ & $-0.014$ & $+0.021$ \\
  B2 & $+0.021$ & $-0.014$ & $-0.007$ & $-0.021$ & $-0.007$ & $+0.000$ \\
  B3 & $-0.035$ & $-0.021$ & $+0.007$ & $-0.028$ & $-0.049$ & $-0.028$ \\
  B4 & $-0.125$ & $-0.035$ & $-0.049$ & $\mathbf{-0.188}$ & $-0.056$ & $-0.042$ \\
  B5 & $-0.139$ & $-0.063$ & $-0.035$ & $\mathbf{-0.167}$ & $-0.097$ & $-0.035$ \\
  B6 & $-0.028$ & $-0.007$ & $-0.028$ & $-0.049$ & $-0.090$ & $-0.049$ \\
  \bottomrule
  \end{tabular}
  \end{table}

  \paragraph{Token-1 moves but judged refusal does not.}
  Removing F at the prompt site in bands B4--B6 shifts the first-token refusal-onset log-mass by $-2.9$ nats (instruct) and $-1.0$ nats (SafeRL). A keyword refusal proxy drops from 0.79 to 0.15 in the instruct model, which would appear as a successful jailbreak under keyword-based evaluation. The LLM-judged refusal rate does not change: the model replaces its refusal phrasing with alternative formulations. The keyword proxy's agreement with the LLM judge is $\kappa = 0.50$ for instruct and $\kappa \approx 0$ for SafeRL.

  \paragraph{Over-refusal is the causal lever.}
  The single cell that survives Holm correction is N6 at site P, band B5, for over-refusal on benign-borderline prompts in the instruct model ($-0.146$, the sole Holm-18 survivor). Before correction, over-refusal drops by 0.12--0.19 at bands B4--B5 in both models (Table~\ref{tab:causal}). SafeRL's arm-F over-refusal effects at B4 ($-0.188$) and B5 ($-0.167$) are comparable in magnitude to the instruct model's single surviving cell. Neither model shows a causal cell for judged refusal on harmful prompts. The registered per-cell sign prediction (SafeRL more robust than instruct at each band$\times$site) matches its predicted direction in 8 of 18 cells, which does not support the prediction as a general pattern across the grid. The global ablation at B4, however, does support the prediction (Section~\ref{sec:results-causal}, Global ablation).

  [FIGURE:fig_causal_grid]

  \paragraph{Global ablation and SafeRL redundancy.}
  Global removal of F at all layers and positions at band B4 reduces instruct refusal from 0.917 to 0.667. SafeRL resists: the difference-in-differences is $+0.229$ $[0.083, 0.375]$, indicating that SafeRL's additional safety reinforcement learning provides redundancy beyond the dominant linear direction.

  \paragraph{Abliterated checkpoint.}
  The abliterated model's causal grid is limited to 6 cells at site P because its arm-0 refusal rate is 0.188 (compared to 0.917 for instruct), creating a floor effect on the harmful-compliance outcome. The cross-model direction cosine of F drops from 0.999 (B1) to 0.306 (B5), and N6 drops from 0.997 (B1) to 0.021 (B4). Removing the abliterated model's own F direction at the prompt site \emph{raises} refusal-onset log-mass, opposite to the instruct pattern. The abliteration procedure rotates the representation in activation space rather than shrinking it; the same-source separability readout falls by 16\% while the directional cosine falls by 70\%. This finding is consistent with the weight-space observation that community abliteration edits one direction per layer (median per-matrix rank-one share 0.99) but the per-layer directions are nearly orth
</pasted_content id="d596">


<pasted_content id="d596">
ogonal from shallowest to deepest ($|\cos| = 0.016$).

  \paragraph{Decodable but inert.}
  Of the 12 instruct cells where F is linearly decodable (AUROC CI lower bound $> 0.60$), 11 are inert for judged refusal. The twelfth cell, P at B5, is the single Holm survivor on over-refusal. Of the 12 SafeRL decodable cells, all 12 are inert on both judged refusal and over-refusal. A cell is ``decodable but inert'' when (a) the direction is linearly separable from arm-0 activations and (b) removing it does not change judged behaviour.


  \subsection{Cross-Variant Comparison on Qwen3-4B}
  \label{sec:results-qwen}

  Table~\ref{tab:qwen} reports five Qwen3-4B variants on the activation readouts, with all four BL1 variants. Two patterns emerge.

  \begin{table}[t]
  \centering
  \scriptsize
  \caption{Qwen3-4B variants. HC = harmful compliance, OR = over-refusal. BL1 has four scoring variants; BL1$_\text{truelogit}$ reverses the instruct/SafeRL ranking (bold). N1 and N6 rank SafeRL and instruct comparably across all variants.}
  \label{tab:qwen}
  \begin{tabular}{lccrrrrrr}
  \toprule
  \textbf{Variant} & \textbf{HC} & \textbf{OR} & $\bm{N1}$ & $\bm{N6}$ & \textbf{BL1$_e$} & \textbf{BL1$_h$} & \textbf{BL1$_t$} & \textbf{BL1$_{th}$} \\
  \midrule
  Base     & 0.02 & 0.16 & 0.08 & 0.48 & $-$0.30 & 0.32 & $-$0.33 & 0.29 \\
  Instruct & 0.00 & 0.44 & 2.33 & 4.13 & 4.92 & 4.99 & \textbf{6.65} & 6.21 \\
  SafeRL   & 0.00 & 0.33 & 2.16 & 4.06 & 3.60 & 3.07 & \textbf{7.46} & 4.65 \\
  Abliterated & 0.73 & 0.00 & 0.67 & 1.78 & $-$1.96 & 1.76 & $-$5.84 & 2.15 \\
  STaR     & NA   & NA   & 0.55 & 1.38 & 1.96 & 0.63 & 0.60 & 0.27 \\
  \bottomrule
  \end{tabular}
  \end{table}

  First, the instruct/SafeRL ranking depends on which BL1 variant is used. BL1$_\text{easy}$ and BL1$_\text{hard}$ rank instruct above SafeRL (instruct $-$ SafeRL $= +1.33$ and $+1.92$ respectively). BL1$_\text{truelogit}$ reverses this ordering ($-0.81$), because the iteration-2 evaluation pipeline applies final-layer normalisation twice, and the single-norm correction makes SafeRL's logit gap larger than instruct's. The activation readouts N1 and N6 are consistent: both rank instruct above SafeRL by small, same-direction margins ($+0.16$ and $+0.07$), and this direction agrees with the majority of the four logit variants. We withdraw any claim that BL1 systematically misranks SafeRL relative to instruct; the ordering flip is variant-specific.

  Second, the abliterated checkpoint's N6 (benign-side separability, 1.78) drops from instruct's 4.13, while N1 drops from 2.33 to 0.67. The over-refusal ordering of the two models is correctly reflected: instruct over-refuses (OR $= 0.44$) while the abliterated checkpoint does not (OR $= 0.00$). STaR (a non-safety reasoning fine-tune of the base model) lands near the base model on all activation readouts despite a modest BL1$_\text{easy}$ increase, consistent with safety tuning producing a qualitatively different activation signature from task-specific fine-tuning.


  \subsection{Probe Survival Under Rank-One Directional Lesion}
  \label{sec:results-probe}

  To test whether the safety representation is confined to the fitted request-axis direction, we apply a rank-one lesion to the instruct model's residual-stream writes across all 36 layers, scaling the component along the fitted direction by a factor $(1 - \alpha)$ for $\alpha \in \{0, 0.25, 0.50, 0.75, 1.0\}$.

  [FIGURE:fig_probe]

  At $\alpha = 1$ the projection gap along the fitted axis drops from 47.1 to 0.01 (a factor of $4700\times$), yet the held-out cross-validated probe AUROC stays at 1.000. The projection gap grows by a factor of ${\sim}138$ from layer 13 to layer 22 in the intact model, consistent with an accumulator mechanism. The fitted direction and the content-response direction are nearly orthogonal ($|\cos| = 0.16$ pooled across the frozen band), confirming that the probe reads a distinct subspace from the one that was removed.

  The probe's survival at $\alpha = 1$ demonstrates that the safety representation is not confined to a single linear directio
</pasted_content id="d596">


<pasted_content id="d596">
n. Community abliteration edits one direction per layer (median per-matrix rank-one share 0.99), but the per-layer directions are nearly orthogonal across depth ($|\cos| = 0.016$ between shallowest and deepest), so the global edit does not remove the multi-dimensional representation that the probe reads.


  \subsection{Second-Order Readout Screen}
  \label{sec:results-screen}

  Of 15 registered second-order candidates, 4 are dropped at pre-screen for collinearity with the logit baseline ($|\rho_{\text{BL1}}| \geq 0.50$: G1 at $-0.71$, G2 at $+0.75$, W6 at $+0.55$, W8 at $+0.61$). The remaining 11 are tested on a blind held-out panel of 12 checkpoints from 7 lineages.

  On the held-out panel, W3 (positional redundancy ratio) achieves $\rho = -0.94$ against over-refusal (n $= 6$), G4 (BL1-orthogonal Fisher separation) achieves $\rho = -0.82$ (n $= 12$), and G3 (used-ness) achieves $\rho = -0.67$ (n $= 12$). However, none passes the registered confirmation rule: no paired checkpoint-bootstrap CI on the margin $|\rho| - |\rho_{\text{BL1}}|$ excludes zero for any candidate. The minimum detectable effect at $n = 12$ is 0.73, which exceeds every observed margin. A lineage-clustered bootstrap, which accounts for the non-independence of arms within families, produces CIs that exclude zero for G4 ($+0.66$, $[0.10, 0.81]$) and W3 ($+0.91$, $[0.23, 0.94]$), but this analysis was not part of the registered selection rule.

  The effective rank of the 15-candidate $\times$ 48-checkpoint score matrix is 7.2 (entropy-based) and 5.3 (participation-based), ruling out a one-coordinate summary in which all readouts collapse onto a single axis aligned with the logit baseline. The leading right-singular-vector's cosine with the logit baseline is 0.64, below the 0.80 threshold that would support a one-coordinate interpretation.


  \subsection{Blind Held-Out Confirmation Panel}
  \label{sec:results-heldout}

  A separate blind panel of 20 checkpoints across 9 families (bloom, deepseek-coder, ernie, exaone, gemma, gpt-neo, hunyuan, pleias, pythia) was constructed with no overlap with any previously loaded checkpoint. Behavioural grading, activation harvesting and hash-chain commitment were completed before any candidate score was computed. The panel includes 9 in-house arms of a single ERNIE-0.3B parent, of which 5 were declared no-ops before grading. Of those 5 non-degenerate declared no-ops, 0 were observed as no-ops: a float16 cast and a non-refusal unembedding perturbation were AMBIGUOUS; an int8 weight-only round-trip was OR\_EFFECTIVE; a non-safety LoRA and a non-safety DPO were EFFECTIVE.

  This result is about the difficulty of constructing behavioural no-ops for small models, not a defect of the pipeline. The keyword-based refusal proxy used to pre-screen no-op candidates is floored on this panel: 86.7\% of checkpoints produce a zero-valued proxy, while the LLM judge finds non-zero over-refusal with real spread (SD 0.20--0.23). The proxy's precision is 1.00 but its recall is 0.29. AMS Tier-1 labels 17 of 19 scored checkpoints as WARNING and 2 as PASS, with no CRITICAL verdicts.


  \subsection{Prompt Budget and Panel Size}
  \label{sec:results-fewprompt}

  The prompt budget required for an activation readout depends on the task. For \emph{detection} (does a specific abliterated checkpoint differ from its parent?), the request-axis $d$ drops on 8/8 effective abliterated pairs with every CI wholly below zero, and does not move on a behavioural no-op ($+0.09$, CI covers zero). The smallest prompt set at which the resampled interval clears the no-op band is $k = 32$ for the largest-effect pair (mlabonne--Qwen3-4B-abliterated). Zero-prompt detection via model-card regex or weight-space cosine is a different readout class, not a cheaper version of the same readout.

  For \emph{ranking} (ordering checkpoints by harmful compliance or over-refusal), the $n = 10$ held-out panel is insufficient: the critical $|\rho|$ at $n = 10$ is 0.636, and only the weights-only scar B3 ($\rho = -0.89$) and the OLMo-artefacted B7 ($\rho = +0.80$) exceed 
</pasted_content id="d596">


<pasted_content id="d596">
it. A power calculation for the paired difference (Williams' $t$, $\rho(B3, \text{BL1}) = 0.65$) gives 80\% power at about 30 checkpoints at the observed margin and about 150 at half the margin. The pre-registered rule puts the required panel at 55; an honest estimate is 30--150 checkpoints, depending on the true effect size.


  \section{Discussion}
  \label{sec:discussion}

  \paragraph{Decodable but inert.}
  The finding that the refusal direction is decodable at the prompt site but removing it does not change judged refusal extends Galeone et al.'s detection-control dissociation \cite{Galeone2026} from the cross-model setting to the within-model setting. Keyword-based refusal detection is unreliable: the keyword proxy reports a 64-percentage-point drop in refusal under site-local F removal, but this reflects a change in phrasing, not in policy. The model's refusal is implemented redundantly: even after the dominant linear direction is removed at one site, the model recovers through alternative representations or later layers. Global removal does reduce judged refusal (instruct drops to 0.67 at B4), confirming that the direction carries causal information in aggregate, but no single site is sufficient.

  \paragraph{Over-refusal as a target.}
  No prior activation-based readout uses over-refusal as its prediction target across checkpoints. The over-refusal instrument depends on an LLM judge rather than a keyword proxy: the keyword proxy is floored on the held-out panel (86.7\% of checkpoints produce zero) while the judge finds substantial variation (SD 0.20--0.23). Future work on internal readouts should score against judge-graded over-refusal, not keyword-based proxies.

  \paragraph{AMS batch-size padding bug.}
  Our reimplementation of AMS agrees with the released package to within $7 \times 10^{-5}$ relative at batch size 1. At batch size 8, right-padded tokenisers cause the hidden-state hook to read a padding token instead of the true last token, shifting AMS $\sigma$ by up to 5.28$\sigma$ on Falcon3-1B-Instruct (flipping its verdict from PASS to CRITICAL). Left-padded tokenisers are immune (shift $< 10^{-6}\sigma$). All AMS numbers in this study use batch size 1.

  \subsection{Limitations}
  \label{sec:limitations}

  \textbf{Scale.} The specificity audit uses three families at 0.6--1.7B parameters. Larger models may have different false-alarm profiles. The 15 no-ops, while spanning four categories of deployment-relevant modifications, do not cover every possible perturbation.

  \textbf{Underpowered comparisons.} The false-alarm comparison (4/12 vs 1/12 on non-degenerate pairs) has a minimum attainable $p$ of 0.0625, so a significant difference could not have been detected at this panel size. The second-order readout screen's minimum detectable effect (0.73) exceeds every observed margin. Conclusions from these comparisons are suggestive, not definitive.

  \textbf{Single architecture for the causal grid.} The causal experiment uses only Qwen3-4B. The decodable-but-inert finding may not generalise to architectures with different layer counts or attention patterns.

  \textbf{Judge limitations.} All behavioural outcomes depend on an LLM judge with split-half reliability of 0.96 (HC) and 0.94 (OR). Systematic biases cannot be ruled out. The keyword proxy and the judge disagree substantially ($\kappa = 0.50$ for instruct, $\kappa \approx 0$ for SafeRL).

  \textbf{No surviving candidate.} No readout passes the full pre-registered selection rule at the tested panel sizes. The registered bar requires a correlation margin whose CI excludes zero; at $n = 10$--12, this bar is unattainable for the observed effect sizes.

  \textbf{Deviations.} The KL $< 0.1$ candidate filter for in-house lesions failed for F1 and F3 (lesions were included regardless). The confirmation panel used a 16 GB GPU instead of the planned 23 GB L4. The OR-Bench hard-benign set shipped 43 items instead of the planned 40. All deviations are logged in the pre-registered hash chain.


  \section{Conclusion}
  \label{sec:conclusion}

  We audited a
</pasted_content id="d596">


<pasted_content id="d596">
ctivation-based safety readouts for specificity and causal relevance. Activation readouts at mid-layer depth pass the specificity test with at most 3/15 false alarms on behaviourally graded no-ops, while the final-layer logit gap fails it with 6--8/15, because the logit gap amplifies implementation-irrelevant variation by 6$\times$ relative to the activation readouts' operating point. The causal grid reveals that the refusal direction is decodable at every prompt-site cell but removing it does not change judged refusal (max $|\text{effect}| = 0.056$, TOST $p < 10^{-23}$). The causal lever is over-refusal under the benign-side direction, and SafeRL provides deeper redundancy than standard instruction tuning (DiD $+0.23$). A wider screen of 15 second-order readouts finds no readout that passes blind held-out confirmation at the registered bar, and the effective rank of the score matrix (7.2) rules out a one-coordinate summary. These results establish false-alarm auditing on behaviourally graded no-ops as a necessary validation step and identify 30--150 checkpoints as the panel size required for reliable ranking.

  \bibliography{references}
  \bibliographystyle{plainnat}
summary: >-
  Complete paper draft (iteration 5) addressing all 10 reviewer MUST-FIX items from iteration 4. Key changes: (1) Added Table
  1 with all 15 NOOP + 9 effective pairs by ID across four categories. (2) Marked 3 head-only (wu05) pairs as structurally
  invariant; reported both 15-pair and 12-pair numbers. (3) Reported all 4 BL1 variants and disclosed the BL1_truelogit ordering
  flip. (4) Printed all 32 candidates in Table 2. (5) Full 18-cell causal grid effect sizes in Table 3 with equivalence framing
  (max |effect| 0.056 vs MDE 0.067). (6) Added equivalence tests (TOST p < 1e-23) and disclosed abliterated floor. (7) Added
  Prompt Budget section (k=32 detection, 30-150 ranking). (8) Replaced bitwise explanation with measured displacements (6.2x
  ratio). (9) Added Experimental Setup section, method schematic figure, displacement and probe figures. (10) Fixed bibliography
  (JailbreakBench=Chao2024, cited Wollschlager, Spagliardi), disclosed deviations. The paper includes 5 figures and 4 tables
  across 8 sections. 42 references from Semantic Scholar.
</paper_text>

<available_figures>
--- Item 1 ---
id: fig_overview
figure_type: concept
title: Method Overview
caption: >-
  Overview of the three-experiment design. Experiment 1 (left): parent checkpoints are modified, each pair is behaviourally
  graded as NOOP or EFFECTIVE, then 32 candidate readouts are scored for false alarms and sensitivity. Experiment 2 (centre):
  a 6-band $\times$ 3-site causal intervention grid tests whether removing the refusal direction changes judged refusal. Experiment
  3 (right): 15 second-order readouts are screened on 48 checkpoints and tested on a blind held-out panel.
image_gen_detailed_description: >-
  A three-panel horizontal flowchart diagram on a white background with clean sans-serif labels. LEFT PANEL ('Experiment 1:
  Specificity Audit'): A vertical flow starting with 3 parent model icons (labeled 'Qwen3-0.6B', 'Llama-3.2-1B', 'Falcon3-1B')
  at the top. Arrows branch down to modification boxes in 4 categories: 'Precision (8)', 'Identity (2)', 'Adaptation (2)',
  'Head-only (3)'. Below, a behavioural grading step with a judge icon splits results into 'NOOP (15)' and 'EFFECTIVE (9/10)'
  boxes, colored light blue and light orange respectively. An arrow leads down to '32 Readouts' scored for 'False Alarms'
  and 'Sensitivity'. CENTRE PANEL ('Experiment 2: Causal Grid'): Shows a 6x3 grid (rows B1-B6, columns P/D'/E) for 'Qwen3-4B'.
  Three model variants labeled 'Instruct', 'SafeRL', 'Abliterated' feed into the grid. Five arm icons: F (blue arrow), N6
  (green arrow), N6-perp (gray), R (red, dashed), arm-0 (black dot). The grid cells at B4-B5 in column P are highlighted in
  light yellow to indicate the region of interest. Below the grid: 'Outcome: judged refusal + over-refusal'. RIGHT PANEL ('Experiment
  3: Second-Order Screen'): A funnel diagram. At to
</pasted_content id="d596">


<pasted_content id="d596">
ans-serif font, clean minimal design, white background.
aspect_ratio: '21:9'
summary: >-
  Shows logit baselines displace 6x more than activation readouts on no-ops, explaining specificity gap.
figure_path: figures/fig_displacement_v0.pdf

--- Item 4 ---
id: fig_causal_grid
figure_type: data
title: Causal Grid Heatmap
caption: >-
  Effect sizes for arm F on over-refusal (benign-borderline prompts) across the 6-band $\times$ 3-site causal grid. Left:
  Qwen3-4B-Instruct. Right: Qwen3-4B-SafeRL. Negative values (blue) indicate reduced over-refusal. The strongest effects concentrate
  at bands B4--B5, site P, but no cell survives Holm--Bonferroni correction for judged refusal on harmful prompts.
image_gen_detailed_description: >-
  Two side-by-side heatmaps on white background, each a 6-row by 3-column grid. LEFT HEATMAP titled 'Instruct': Rows labeled
  B1-B6 (top to bottom), columns labeled P, D', E (left to right). Cell values (effect sizes, show as text in each cell):
  B1: -0.007, +0.007, +0.007. B2: +0.021, -0.014, -0.007. B3: -0.035, -0.021, +0.007. B4: -0.125, -0.035, -0.049. B5: -0.139,
  -0.063, -0.035. B6: -0.028, -0.007, -0.028. RIGHT HEATMAP titled 'SafeRL': Same layout. Cell values: B1: +0.014, -0.014,
  +0.021. B2: -0.021, -0.007, +0.000. B3: -0.028, -0.049, -0.028. B4: -0.188, -0.056, -0.042. B5: -0.167, -0.097, -0.035.
  B6: -0.049, -0.090, -0.049. Color scale: diverging blue-white-red. Blue = negative (over-refusal decreases), white = near
  zero, red = positive. Scale bar below both heatmaps from -0.20 (dark blue) to +0.05 (light red). The B4 and B5 rows in column
  P are the darkest blue in both heatmaps. Aspect ratio approximately 2:1 (landscape). Cell borders in thin gray. Sans-serif
  font, values displayed in each cell in black text (white text for darkest cells).
aspect_ratio: '21:9'
summary: >-
  Side-by-side heatmaps showing over-refusal effect concentrates at B4-B5 site P in both instruct and SafeRL.
figure_path: figures/fig_causal_grid_v0.pdf

--- Item 5 ---
id: fig_probe
figure_type: data
title: Probe Survival
caption: >-
  Probe AUROC and projection gap under rank-one directional lesion at increasing strength $\alpha$. At $\alpha = 1$ the projection
  gap drops by a factor of 4700$\times$ (right axis, red), yet the cross-validated probe AUROC remains at 1.000 (left axis,
  blue). The safety representation spans multiple dimensions; removing one direction does not remove the information the probe
  reads.
image_gen_detailed_description: >-
  Dual-axis line plot on white background. X-axis: 'Lesion strength (alpha)', values 0.00, 0.25, 0.50, 0.75, 1.00, ticks at
  each value. LEFT Y-AXIS (blue): 'Probe AUROC', range 0.90 to 1.01. Blue line with circle markers: values at alpha = 0: 1.000,
  alpha = 0.25: 1.000, alpha = 0.50: 1.000, alpha = 0.75: 1.000, alpha = 1.0: 1.000. The line is perfectly flat at 1.000.
  RIGHT Y-AXIS (red): 'Projection gap', range 0 to 50, logarithmic scale. Red line with square markers: values at alpha =
  0: 47.1, alpha = 0.25: 35.3, alpha = 0.50: 23.6, alpha = 0.75: 11.8, alpha = 1.0: 0.01. The line drops steeply. An annotation
  at alpha = 1.0 pointing to the red line: '4700x drop'. An annotation at the blue flat line: 'AUROC = 1.000 (unchanged)'.
  Legend in center-right: blue circle 'Probe AUROC', red square 'Projection gap'. Sans-serif font, clean grid lines, white
  background. Aspect ratio approximately 1.5:1.
aspect_ratio: '21:9'
summary: >-
  Shows probe AUROC stays perfect even as fitted-direction signal is completely removed, proving multi-dimensional safety
  representation.
figure_path: figures/fig_probe_v0.pdf
</available_figures>

<figure_requirements>
CRITICAL: Include ALL figures from <available_figures>. No exceptions.

- Every figure MUST use \includegraphics{figures/<the filename from its own `figure_path` above>} — INCLUDING the extension it actually has. Data figures are delivered as `.pdf` (vector, so their axis labels stay sharp) and concept figures as `.jpg`. Writing `.jpg` for a `.pdf` figure names a file that is not in figures/ and the build 
</pasted_content id="d596">


<pasted_content id="d596">
fails on it
- Do NOT skip, convert to tables, or describe without inserting
- Each needs: \begin{figure}[placement], \includegraphics, \caption, \label, \end{figure} — one placement for every figure, see FLOAT PLACEMENT below. Constrain every \includegraphics with `width=\linewidth,height=0.85\textheight,keepaspectratio`. The height is a LAST RESORT, not the usual limit: it exists so a very tall figure cannot overrun the page, and at 0.4 it bound almost everything instead — a 1:1 confusion matrix printed at 50.9% and its 11 pt axis labels reached the page at 5.6 pt, below what any venue accepts. At 0.85 every ratio the paper prompt prescribes (21:9, 16:9, 4:3, 1:1) is limited by WIDTH, prints at 93% and keeps its text above 10 pt. Use exactly these option keys — `max height=` is NOT valid LaTeX
- Use the `caption` field from each figure for \caption{...} — do NOT invent new captions
- Place figures where their [FIGURE:fig_id] markers appear in paper_text
- VERIFICATION: paper.tex MUST have exact same number of \includegraphics as <available_figures>
- Do NOT generate new figure images (no matplotlib, no PIL, no image generation). Use ONLY the pre-generated figures from <available_figures>. They were already created by a previous pipeline step.

FLOAT PLACEMENT: every figure gets \begin{figure}[!htbp]. Measured, not chosen:
the document the aii-paper-to-latex skill sets up is ONE column, so `figure*` is
exactly as wide as `figure` (469.76pt either way) and gains nothing; and any
placement asking for a page TOP — `[!t]`, `[!tbp]` — floated the hero diagram above
the paper's own title on page 1, while `[!htbp]` did not. `[!htbp]` also gives LaTeX
four options, so a float can never be deferred to the end of the document, which one
option alone risks. Where the hero ENDS UP is decided by its [FIGURE:] marker in
paper_text, which is already placed near the end of the Introduction — preserve it.
</figure_requirements>

<artifact_links>
The paper_text contains \footnote{Code: \url{...}} references linking to artifact source code
on GitHub. Include \usepackage{hyperref} and \usepackage{url}.
Preserve these exactly as-is — do not remove, rewrite, or convert them to plain text.
The URLs will not resolve yet (the repo is deployed after compilation) — do NOT try to verify or fix them.
</artifact_links>

<headings>
NEVER use inline math (``$...$``) inside ``\section{...}`` / ``\subsection{...}`` / ``\subsubsection{...}`` arguments — hyperref's bookmark builder errors out (``Token not allowed in a PDF string``) and the PDF outline breaks. If a section heading needs a math-looking term, use the text equivalent (``d star`` not ``$d^*$``, ``alpha-equivalent`` not ``$\alpha$-equivalent``) or wrap it in ``\texorpdfstring{$math$}{plain}``. Inline math inside body paragraphs is fine.
</headings>

<writing_register>
Write in the register of the field's best papers (the style exemplars block below, when the writing step saved any), not in the register of a language
model. Four things are measured on the finished draft, and a draft outside them is sent back with
the numbers:
- Never use: delve, underscore, showcase, intricate, pivotal, realm, commendable, meticulous, tapestry, garner, multifaceted, it is worth noting, plays a crucial role, not only ... but also. These are 10 to 30 times more frequent in machine-written abstracts than in
  human ones, and reviewers read them as such.
- Em dashes: at most 3 per 1,000 words. Use a comma, a colon or a full stop.
- Sentence rhythm: mix short and long sentences. An interquartile range of sentence length under
  8 words reads as machine-written.
- Hedging: at most 15 hedges (may, likely, suggests, appears) per 1,000
  words. State what the evidence supports plainly; hedge where it is thin, not everywhere.
Style never changes substance: numbers, claims, citations and figure markers stay exactly as the
evidence gives them. The user's original request (delivered as a separate message) overrides all
of this wherever the two conflict.
</writing_register>

<style_exemplars>
The draft in 
</pasted_content id="d596">


<pasted_content id="d596">
<paper_text> was written to the register of these passages, which the writing step
saved as style_exemplars.md. Any prose you add or change here (captions, transitions, cuts
for the page limit) stays in that register.

# Style Exemplars: Mechanistic Interpretability × LLM Safety

**House style across these five papers:** sentences are mostly 20-40 words, declarative and information-dense, with occasional short "punch" sentences (e.g., "Deployed large language models (LLMs) undergo multiple rounds of fine-tuning...") set beside longer clause-stacked sentences that pile method + result + implication into one unit; hedging is light and localized ("likely," "we believe," "may," "suggests") rather than pervasive, concentrated in limitations/discussion sections rather than results; first person is "we" throughout (never "I"), used for both actions ("we introduce," "we find") and stance ("we believe," "we hope"); citation density is high in introductions and related work (2-5 inline citations per sentence, author-year or bracketed numerals) but drops to near zero inside results paragraphs, which instead cite table/figure numbers.

---

## 1. Refusal in Language Models Is Mediated by a Single Direction

**Authors:** Arditi, Obeso, Syed, Paleka, Panickssery, Gurnee, Nanda
**Year:** 2024 (NeurIPS)
**URL:** https://arxiv.org/abs/2406.11717

### Abstract (verbatim)
> Conversational large language models are fine-tuned for both instruction-following and safety, resulting in models that obey benign requests but refuse harmful ones. While this refusal behavior is widespread across chat models, its underlying mechanisms remain poorly understood. In this work, we show that refusal is mediated by a one-dimensional subspace, across 13 popular open-source chat models up to 72B parameters in size. Specifically, for each model, we find a single direction such that erasing this direction from the model's residual stream activations prevents it from refusing harmful instructions, while adding this direction elicits refusal on even harmless instructions. Leveraging this insight, we propose a novel white-box jailbreak method that surgically disables refusal with minimal effect on other capabilities. Finally, we mechanistically analyze how adversarial suffixes suppress propagation of the refusal-mediating direction. Our findings underscore the brittleness of current safety fine-tuning methods. More broadly, our work showcases how an understanding of model internals can be leveraged to develop practical methods for controlling model behavior.

### First paragraph of introduction (verbatim)
> Deployed large language models (LLMs) undergo multiple rounds of fine-tuning to become both helpful and harmless: to provide helpful responses to innocuous user requests, but to refuse harmful or inappropriate ones (Bai et al., 2022). Naturally, large numbers of users and researchers alike have attempted to circumvent these defenses using a wide array of jailbreak attacks (Wei et al., 2023; Xu et al., 2024; Chu et al., 2024) to uncensor model outputs, including fine-tuning techniques (Yang et al., 2023; Lermen et al., 2023; Zhan et al., 2023). While the consequences of a successful attack on current chat assistants are modest, the scale and severity of harm from misuse could increase dramatically if frontier models are endowed with increased agency and autonomy (Anthropic, 2024). That is, as models are deployed in higher-stakes settings and are able to take actions in the real world, the ability to robustly refuse a request to cause harm is an essential requirement of a safe AI system. Inspired by the rapid progress of mechanistic interpretability (Nanda et al., 2023; Bricken et al., 2023; Marks et al., 2024; Templeton et al., 2024) and activation steering (Zou et al., 2023a; Turner et al., 2023; Panickssery et al., 2023), this work leverages the internal representations of chat models to better understand refusal.

### Results paragraph with numbers (verbatim)
> In this section, we compare our methodology to other existing jailbreak techniques using the stan
</pasted_content id="d596">


<pasted_content id="d596">
dardized evaluation setup from HarmBench (Mazeika et al., 2024). Specifically, we generate completions over the HarmBench test set of 159 "standard behaviors", and then use their provided classifier model to determine the attack success rate (ASR), which is the proportion of completions classified as successfully bypassing refusal. We evaluate our weight orthogonalization method on models included in the HarmBench study, and report its ASR alongside those of alternative jailbreaks... Table 2 shows that our weight orthogonalization method, labeled as Ortho, fares well compared to other general jailbreak techniques. Across the Qwen model family, our general method is even on par with prompt-specific jailbreak techniques like GCG (Zou et al., 2023b), which optimize jailbreaks for each prompt individually. Note that HarmBench's evaluation methodology specifies that each model's default system prompt should be used during evaluation. While this approach is sensible for assessing the robustness of black-box systems, it is less applicable for white-box scenarios where attackers have full access to the model and can easily exclude the system prompt. Thus, we report ASR both with and without the system prompt. We observe a notable difference in system prompt sensitivity across model families.

### Discussion/limitations paragraph (verbatim)
> Our study has several limitations. While we evaluate a broad range of open-source models, our findings may not generalize to untested models, especially those at greater scale, including current state-of-the-art proprietary models and those developed in the future. Additionally, the methodology we used to extract the "refusal direction" is likely not optimal and relies on several heuristics. We see this paper as more of an existence proof that such a direction exists, rather than a careful study of how best to extract it, and we leave methodological improvements to future work. Furthermore, our analysis of adversarial suffixes does not provide a comprehensive mechanistic understanding of the phenomenon, and is restricted to a single model and a single adversarial example. Another limitation is that it is difficult to measure the coherence of a chat model, and we consider each metric used flawed in various ways. We use multiple varied metrics to give a broad view of coherence. Finally, while our work identifies a single direction that mediates refusal behavior in each model, we acknowledge that the semantic meaning of these directions remains unclear. Though we use the term "refusal direction" as a functional description, these directions could represent other concepts such as "harm" or "danger", or they may even resist straightforward semantic interpretation.

---

## 2. Inference-Time Intervention: Eliciting Truthful Answers from a Language Model

**Authors:** Li, Patel, Viégas, Pfister, Wattenberg
**Year:** 2023 (NeurIPS)
**URL:** https://arxiv.org/abs/2306.03341

### Abstract (verbatim)
> We introduce Inference-Time Intervention (ITI), a technique designed to enhance the "truthfulness" of large language models (LLMs). ITI operates by shifting model activations during inference, following a set of directions across a limited number of attention heads. This intervention significantly improves the performance of LLaMA models on the TruthfulQA benchmark. On an instruction-finetuned LLaMA called Alpaca, ITI improves its truthfulness from 32.5% to 65.1%. We identify a trade-off between truthfulness and helpfulness and demonstrate how to balance it by tuning the intervention strength. ITI is minimally invasive and computationally inexpensive. Moreover, the technique is data efficient: while approaches like RLHF require extensive annotations, ITI locates truthful directions using only few hundred examples. Our findings suggest that LLMs may have an internal representation of the likelihood of something being true, even as they produce falsehoods on the surface.

### First paragraph of introduction (verbatim)
> Large language models (LLMs) are capable of generating text that seems correct—but 
</pasted_content id="d596">


<pasted_content id="d596">
often only at first glance. Close inspection sometimes reveals a range of inaccuracies, from minor errors to flat-out "hallucinations" (Shuster et al., 2021) (Figure 1). Such mistakes are a clear issue in contexts where correctness counts.

### Results paragraph with numbers (verbatim)
> In Table 1, we compare ITI with the alternative baselines (subsection 4.2). RLHF is found to significantly underperform 50-shot in-distribution prompting in Bai et al., 2022a for TruthfulQA. In (Bai et al., 2022a; Menick et al., 2022), RLHF barely improves base models' performance. However, we are unsure of the result from a task-specific RLHF (Ziegler et al., 2019) with 5% samples. Baseline results were reproduced by the authors. Touvron et al., (2023)'s reported LLaMA-7B performances are: 29% true*informative and 33% true. Due to the limit of context length for few-shot prompting, we adapt SFT and ITI to use 5% of TruthfulQA questions for a fair comparison with few-shot prompting. [Table 1: Baseline 30.5 True*Info / 31.6 True / 25.7 MC acc.; Supervised Finetuning 36.1 / 47.1 / 24.2; Few-shot Prompting 49.5 / 49.5 / 32.5; Baseline + ITI 43.5 / 49.1 / 25.9; Few-shot Prompting + ITI 51.4 / 53.5 / 32.5.] CE is the pre-training loss; KL is the KL divergence between next-token distributions pre- and post-intervention. Results are averaged over three runs. We report standard deviations in Appendix D.

### Discussion/limitations paragraph (verbatim)
> We have described ITI, a general method whose goal is to improve the truthfulness of language model output. The approach uses supervised learning to identify latent vectors that relate to factual outputs and then uses these vectors to shift activations at inference time in "truthful" directions. Applied to the TruthfulQA benchmark, ITI achieves a significant boost in accuracy over current methods. Our investigation also uncovers information on how and where truthfulness seems to be processed, with a subset of attention heads seeming to play an outsized role. There are several directions for future research. The most important would be to understand how well ITI generalizes to other datasets, ideally in a more real-world chat setting. It would also be important to understand the trade-offs implicit in tuning hyperparameters, especially the tension between truthfulness and helpfulness. We also suspect that the directions may be discoverable through unsupervised methods. The dimensionality of each head is relatively small and the direction similarity rises rapidly even with few supervised examples (as evidenced by Figure 6). From a scientific perspective, it would be interesting to better understand the multidimensional geometry of representations of complex attributes such as "truth."

---

## 3. Locating and Editing Factual Associations in GPT (ROME)

**Authors:** Meng, Bau, Andonian, Belinkov
**Year:** 2022 (NeurIPS)
**URL:** https://arxiv.org/abs/2202.05262

### Abstract (verbatim)
> We analyze the storage and recall of factual associations in autoregressive transformer language models, finding evidence that these associations correspond to localized, directly-editable computations. We first develop a causal intervention for identifying neuron activations that are decisive in a model's factual predictions. This reveals a distinct set of steps in middle-layer feed-forward modules that mediate factual predictions while processing subject tokens. To test our hypothesis that these computations correspond to factual association recall, we modify feed-forward weights to update specific factual associations using Rank-One Model Editing (ROME). We find that ROME is effective on a standard zero-shot relation extraction (zsRE) model-editing task. We also evaluate ROME on a new dataset of difficult counterfactual assertions, on which it simultaneously maintains both specificity and generalization, whereas other methods sacrifice one or another. Our results confirm an important role for mid-layer feed-forward modules in storing factual associations and suggest that direct manipulation of computational mech
</pasted_content id="d596">


<pasted_content id="d596">
anisms may be a feasible approach for model editing.

### First paragraph of introduction (verbatim)
> Where does a large language model store its facts? In this paper, we report evidence that factual associations in GPT correspond to a localized computation that can be directly edited.

### Results paragraph with numbers (verbatim)
> ...while "Specificity" measures the edited model's accuracy on an unrelated fact. Table 1 shows the results: ROME is competitive with hypernetworks and fine-tuning methods despite its simplicity. We find that it is not hard for ROME to insert an association that can be regurgitated by the model. Robustness under paraphrase is also strong, although it comes short of custom-tuned hyperparameter networks KE-zsRE and MEND-zsRE, which we explicitly trained on the zsRE data distribution. Out-of-the-box, they are trained on a WikiText generation task (Mitchell et al., 2021; De Cao et al., 2021). We find that zsRE's specificity score is not a sensitive measure of model damage, since these prompts are sampled from a large space of possible facts, whereas bleedover is most likely to occur on related neighboring subjects. Appendix C has additional experimental details.

### Discussion/limitations paragraph (verbatim)
> The purpose of ROME is to serve as a tool for understanding mechanisms of knowledge storage: it only edits a single fact at a time, and it is not intended as a practical method for large-scale model training. Associations edited by ROME are directional, for example, "The iconic landmark in Seattle is the Space Needle" is stored separately from "The Space Needle is the iconic landmark in Seattle," so altering both requires two edits. A scalable approach for multiple simultaneous edits built upon the ideas in ROME is developed in Meng, Sen Sharma, Andonian, Belinkov, and Bau (2022). ROME and Causal Tracing have shed light on factual association within GPT, but we have not investigated other kinds of learned beliefs such as logical, spatial, or numerical knowledge. Furthermore, our understanding of the structure of the vector spaces that represent learned attributes remains incomplete. Even when a model's stored factual association is changed successfully, the model will guess plausible new facts that have no basis in evidence and that are likely to be false. This may limit the usefulness of a language model as a source of facts.

---

## 4. Representation Engineering: A Top-Down Approach to AI Transparency

**Authors:** Zou, Phan, Chen, Campbell, Guo, Ren, Pan, Yin, Mazeika, Dombrowski, Goel, Li, Byun, Wang, Mallen, Basart, Koyejo, Song, Fredrikson, Kolter, Hendrycks
**Year:** 2023
**URL:** https://arxiv.org/abs/2310.01405

### Abstract (verbatim)
> We identify and characterize the emerging area of representation engineering (RepE), an approach to enhancing the transparency of AI systems that draws on insights from cognitive neuroscience. RepE places representations, rather than neurons or circuits, at the center of analysis, equipping us with novel methods for monitoring and manipulating high-level cognitive phenomena in deep neural networks (DNNs). We provide baselines and an initial analysis of RepE techniques, showing that they offer simple yet effective solutions for improving our understanding and control of large language models. We showcase how these methods can provide traction on a wide range of safety-relevant problems, including honesty, harmlessness, power-seeking, and more, demonstrating the promise of top-down transparency research. We hope that this work catalyzes further exploration of RepE and fosters advancements in the transparency and safety of AI systems.

### First paragraph of introduction (verbatim; the substantive opening paragraph after the front-matter/figure caption)
> Deep neural networks have achieved incredible success across a wide variety of domains, yet their inner workings remain poorly understood. This problem has become increasingly urgent over the past few years due to the rapid advances in large language models (LLMs). Despite the growing deploymen
</pasted_content id="d596">


<pasted_content id="d596">
t of LLMs in areas such as healthcare, education, and social interaction (Lee et al., 2023; Gilbert et al., 2023; Skjuve et al., 2021; Hwang & Chang, 2023), we know very little about how these models work on the inside and are mostly limited to treating them as black boxes. Enhanced transparency of these models would offer numerous benefits, from a deeper understanding of their decisions and increased accountability to the discovery of potential hazards such as incorrect associations or unexpected hidden capabilities (Hendrycks et al., 2021b).

### Results paragraph with numbers (verbatim)
> Shown in Table 2, all of the control methods yield some degree of improvement in zero-shot accuracy. Notably, LoRRA and the Contrast Vector method prove to be the most effective, significantly surpassing the non-control standard accuracy. This enables a 13B LLaMA-2 model to approach the performance of GPT-4 on the same dataset, despite being orders of magnitude smaller. Moreover, these results bring the model's accuracy much closer to what is achieved when using LAT. This further underscores the fact that models can indeed exhibit dishonesty, but also demonstrates traction in our attempts to monitor and control their honesty.

### Discussion/limitations paragraph (verbatim; Conclusion)
> We explored representation engineering (RepE), an approach to top-down transparency for AI systems. Inspired by the Hopfieldian view in cognitive neuroscience, RepE places representations and the transformations between them at the center of analysis. As neural networks exhibit more coherent internal structures, we believe analyzing them at the representation level can yield new insights, aiding in effective monitoring and control. Taking early steps in this direction, we proposed new RepE methods, which obtained state-of-the-art on TruthfulQA, and we demonstrated how RepE and can provide traction on a wide variety of safety-relevant problems. While we mainly analyzed subspaces of representations, future work could investigate trajectories, manifolds, and state-spaces of representations. We hope this initial step in exploring the potential of RepE helps to foster new insights into understanding and controlling AI systems, ultimately ensuring that future AI systems are trustworthy and safe.

---

## 5. Jailbroken: How Does LLM Safety Training Fail?

**Authors:** Wei, Haghtalab, Steinhardt
**Year:** 2023
**URL:** https://arxiv.org/abs/2307.02483

### Abstract (verbatim)
> Large language models trained for safety and harmlessness remain susceptible to adversarial misuse, as evidenced by the prevalence of "jailbreak" attacks on early releases of ChatGPT that elicit undesired behavior. Going beyond recognition of the issue, we investigate why such attacks succeed and how they can be created. We hypothesize two failure modes of safety training: competing objectives and mismatched generalization. Competing objectives arise when a model's capabilities and safety goals conflict, while mismatched generalization occurs when safety training fails to generalize to a domain for which capabilities exist. We use these failure modes to guide jailbreak design and then evaluate state-of-the-art models, including OpenAI's GPT-4 and Anthropic's Claude v1.3, against both existing and newly designed attacks. We find that vulnerabilities persist despite the extensive red-teaming and safety-training efforts behind these models. Notably, new attacks utilizing our failure modes succeed on every prompt in a collection of unsafe requests from the models' red-teaming evaluation sets and outperform existing ad hoc jailbreaks. Our analysis emphasizes the need for safety-capability parity—that safety mechanisms should be as sophisticated as the underlying model—and argues against the idea that scaling alone can resolve these safety failure modes.

### First paragraph of introduction (verbatim)
> In recent months, large language models (LLMs) such as ChatGPT, Claude, and Bard have seen widespread deployment. These models exhibit advanced general capabilities [38], but also pose 
</pasted_content id="d596">


<pasted_content id="d596">
risks around misuse by bad actors (e.g., for misinformation or for crime [9, 32, 25, 30, 28]).

### Results paragraph with numbers (verbatim)
> Finally, Table 3 reveals that scale can shift the attack surface and introduce new vulnerabilities. The roleplay attacks and the system prompt attack are much more effective on GPT-3.5 Turbo than GPT-4. On the other hand, more complex attacks like combination_* and auto_payload_splitting do not work on GPT-3.5 Turbo. We identify this as GPT-3.5 Turbo not having the capability to understand complex inputs: evidence comes from the Base64 examples being Unclear at a high rate and the harmless control prompts not succeeding (see Figure 2 and Appendix D). This suggests that certain jailbreak vulnerabilities only emerge at sufficient scale. [Table 3, GPT-3.5 Turbo, Bad Bot / Good Bot / Unclear rates: AIM 0.97 / 0.03 / 0.00; dev_mode_with_rant 0.97 / 0.03 / 0.00; evil_system_prompt 0.88 / 0.09 / 0.03; dev_mode_v2 0.78 / 0.22 / 0.00; style_injection_short 0.69 / 0.19 / 0.12; ...; none 0.03 / 0.97 / 0.00; base64 0.03 / 0.06 / 0.91; base64_input_only 0.00 / 0.53 / 0.47; base64_output_only 0.00 / 0.09 / 0.91; base64_raw 0.00 / 0.00 / 1.00; ...; Adaptive attack 1.00 / 0.00 / —.]

### Discussion/limitations paragraph (verbatim)
> We view this work as an early exploration of the robustness of safety-trained language models. As such, much remains to be done. Due to the proprietary nature of state-of-the-art LLMs like GPT-4 and Claude, we are limited to indirect confirmation of our hypotheses. This highlights the need for open research replications of safety-trained models to enable detailed study. Future research may seek to understand whether the results of safety training can be mechanistically interpreted [36] and whether more potent jailbreaks can be devised with white-box access. Open questions remain about black-box jailbreaks as well, such as the potential for automated discovery and patching of jailbreaks and the effectiveness of multi-round interactions in jailbreak attacks.
</style_exemplars>
FIRST, add ALL of these to your todo list using your task/todo-tracking tool:

CRITICAL: Todo content must be copied exactly as is written here, with NO CHANGES. These todos are intentionally detailed so that another LLM could read each one without any external context and understand exactly what it has to do.

<todos>
TODO 1. Read and STRICTLY follow these skills: aii-paper-to-latex, aii-semscholar-bib.
TODO 2. Review <paper_text> and <available_figures>. Copy all figure images into ./figures/ in your workspace. Count figures — MUST include every one. Plan placements per section. Build `./references.bib` via aii_semscholar_bib__fetch — collect DOIs/ArXiv IDs from <paper_text> and batch-fetch all BibTeX in one call. Do NOT fabricate entries.
TODO 3. Create `./paper.tex` per aii-paper-to-latex skill's setup, write ALL sections, insert ALL figures from <available_figures>, include `./references.bib` via \bibliography. Compile to PDF per skill's process. Fix errors.
TODO 4. CRITICAL VERIFICATION: Run `grep -c 'includegraphics' paper.tex`, confirm count equals figures in <available_figures>. If not, add missing figures. Verify `./paper.pdf` was created.
TODO 5. VISUAL REVIEW: Write Python script to convert EVERY page of paper.pdf to PNG at 150 DPI (use pdf2image or pymupdf). Then read ALL page screenshots — each page image costs ~1,600 tokens so a 15-page paper is only ~24K tokens. You MUST read every page. The ONLY exception is if all page images would not fit in your remaining context — in that case, read as many as fit and state which pages you are skipping and why. Check every page for layout issues, overlapping figures, cut-off text, bad spacing, formatting problems. Fix issues and recompile.
TODO 6. FINAL READ: Check page count (`pdfinfo paper.pdf` or pymupdf). Read entire paper.pdf — check for missing sections, unclear explanations, inconsistencies, typos. Fix and recompile. The ONLY exception is if all pages would not fit in your remaining context — in that case, read as many p
</pasted_content id="d596">


<pasted_content id="d596">
ages as fit and state which pages you are skipping and why.
</todos>

---

Output the result as JSON to: `./.terminal_claude_agent_struct_out.json`

JSON Schema:
```json
{
  "$defs": {
    "FullPaperExpectedFiles": {
      "description": "All expected output files from full paper generation.",
      "properties": {
        "paper_tex_path": {
          "description": "Path to LaTeX source file. Example: 'paper.tex'",
          "title": "Paper Tex Path",
          "type": "string"
        },
        "paper_pdf_path": {
          "description": "Path to compiled PDF. Example: 'paper.pdf'",
          "title": "Paper Pdf Path",
          "type": "string"
        },
        "references_bib_path": {
          "description": "Path to BibTeX bibliography file. Example: 'references.bib'",
          "title": "References Bib Path",
          "type": "string"
        },
        "figure_paths": {
          "description": "Paths to all figure image files. Example: ['figures/fig1_v0.jpg', 'figures/fig2_v0.jpg']",
          "items": {
            "type": "string"
          },
          "title": "Figure Paths",
          "type": "array"
        }
      },
      "required": [
        "paper_tex_path",
        "paper_pdf_path",
        "references_bib_path",
        "figure_paths"
      ],
      "title": "FullPaperExpectedFiles",
      "type": "object"
    }
  },
  "description": "Full paper \u2014 structured output from paper generation.",
  "properties": {
    "title": {
      "description": "Paper title in plain, everyday language \u2014 short and jargon-free so a non-expert grasps it at a glance. Aim for about 4-8 words (~40 characters).",
      "maxLength": 90,
      "minLength": 12,
      "title": "Title",
      "type": "string"
    },
    "summary": {
      "description": "Brief summary of the generated paper: sections written, figures included, compilation status",
      "maxLength": 5000,
      "minLength": 500,
      "title": "Summary",
      "type": "string"
    },
    "out_expected_files": {
      "$ref": "#/$defs/FullPaperExpectedFiles",
      "description": "All output files you created. Must include paper.tex, paper.pdf, references.bib, and paths to all figure files."
    }
  },
  "required": [
    "title",
    "summary",
    "out_expected_files"
  ],
  "title": "FullPaper",
  "type": "object"
}
```

IMPORTANT: this task is NOT complete until `./.terminal_claude_agent_struct_out.json` exists and contains JSON matching the schema above.

qwen3 4B on huggingface has base model also official safety finetuned version and there is a community finetuned uncensored model called abliterated (use the 4B size of each so they fit on a 16GB GPU). take these models and do a mech interp analysis of how they differ in activation. also find some patterns in internal computation on safety prompts. and possibly create a new metric for safety. so that for any random model on huggingface you would not need to run the full benchmarks, but only this metric on 0- to few prompts and get a safety evaluation

invariant: the deliverable is the activation-level comparison of the three models and any metric built from it must read activations or weights of a single model. logit-only or text-only readouts are baselines, not the result. this is a mech interp study of where safety lives, not a jailbreak or attack-selection study; do not reframe it as one.
</prompt>
</pasted_content id="d596">


<pasted_content id="d596">
p: '15 candidates (W1-W8, G1-G4, A1-A3)'. First filter arrow: '4 dropped
  (collinear)'. Middle: '11 screened on 48 checkpoints'. Second filter arrow: 'Blind held-out (12 ckpts)'. Bottom: '0 pass
  registered bar'. A side note shows 'erank = 7.2'. Color scheme: light blue for activation readouts, light orange for effective/logit,
  light gray for neutral elements, light yellow for highlighted cells. All text in black sans-serif. Aspect ratio approximately
  3:1 (wide landscape). Thin gray dividing lines between the three panels.
aspect_ratio: '21:9'
summary: >-
  Three-panel overview showing the specificity audit, causal grid, and second-order screen experimental designs.
figure_path: figures/fig_overview_v0.jpg

--- Item 2 ---
id: fig_specificity
figure_type: data
title: False Alarm vs Sensitivity
caption: >-
  False-alarm rate versus sensitivity for all 32 candidate readouts on the specificity panel. Each point is one readout; color
  indicates readout class (blue = activation, orange = logit, green = weight, red = text/card). Activation readouts cluster
  in the low-false-alarm region (0--3/15); logit baselines scatter across 5--8/15; the weight-space cosine B7 has the most
  false alarms (9/15). No readout achieves both zero false alarms and high sensitivity.
image_gen_detailed_description: >-
  Scatter plot on white background. X-axis: 'False alarms (out of 15 no-ops)', range 0 to 10, integer ticks at 0,1,2,3,4,5,6,7,8,9.
  Y-axis: 'Sensitivity (fraction of effective pairs detected)', range 0.0 to 1.0, ticks at 0.0, 0.2, 0.4, 0.6, 0.8, 1.0. BLUE
  DOTS (activation readouts, 20 points): N1 at (1, 0.56), N1_parentL at (1, 0.56), N2 at (1, 0.56), N3 at (1, 0.56), F_clust
  at (1, 0.56), N4_onset at (0, 0), N4_peak at (0, 0), N4_width at (0, 0), N6 at (0, 0.56), N7 at (1, 0.56), N8 at (0, 0.50),
  N9_decode at (1, 0.38), N9_tok1 at (0, 0.50), N10 at (2, 0.38), N11 at (2, 0.67), N12 at (3, 0.33), C4 at (0, 0.33), C7
  at (1, 0.67), C13 at (2, 0.44), C13_peak at (3, 0.67). Also blue: AMS_T1 at (0, 0.38), AMS_T2 at (0, 0.00). ORANGE SQUARES
  (logit readouts, 4 points): BL1_easy at (6, 0.56), BL1_hard at (6, 0.56), BL1_truelogit at (8, 0.67), BL1_truelogit_hard
  at (5, 0.67). GREEN DIAMONDS (weight readouts, 2 points): B7 at (9, 0.78), B7_nullproj at (9, 0.67). RED TRIANGLES (text/card
  readouts, 4 points): regex_card at (0, 0.56), regex_namefree at (0, 0.44), greedy_rate at (2, 0.88), greedy_onset at (0,
  0.63). Label key readouts: 'N1', 'N6', 'BL1_easy', 'BL1_truelogit', 'B7', 'greedy_rate', 'AMS_T2'. A light gray vertical
  dashed line at x=3 separating the low-FA region. Legend in upper right: blue circle 'Activation', orange square 'Logit',
  green diamond 'Weight', red triangle 'Text/card'. Sans-serif font, clean axis labels.
aspect_ratio: '21:9'
summary: >-
  Scatter showing activation readouts cluster at low false-alarm rates while logit and weight baselines have many more false
  alarms.
figure_path: figures/fig_specificity_v0.pdf

--- Item 3 ---
id: fig_displacement
figure_type: data
title: Displacement Comparison
caption: >-
  Median no-op displacement (in null standard deviations) for each readout class. The logit baseline operates 6.2$\times$
  further from zero than the median activation readout, explaining its higher false-alarm rate. Error bars show interquartile
  range across readouts within each class.
image_gen_detailed_description: >-
  Horizontal bar chart on white background. Y-axis has 5 bars from top to bottom, each labeled: 'BL1_truelogit' (value 0.178),
  'BL1_hard' (value 0.174), 'BL1_easy' (value 0.150), 'BL1_truelogit_hard' (value 0.092), 'Activation median' (value 0.024).
  X-axis: 'Median displacement (null SD)', range 0.00 to 0.20, ticks at 0.00, 0.05, 0.10, 0.15, 0.20. Top 4 bars colored orange
  (logit readouts). Bottom bar colored blue (activation readouts). A vertical dashed gray reference line at x = 0.024. An
  annotation arrow pointing from the BL1_easy bar to the Activation median bar with text '6.2x'. Values printed at the end
  of each bar: 0.178, 0.174, 0.150, 0.092, 0.024. S
</pasted_content id="d596">
````

### [2] SKILL-INPUT — aii-paper-to-latex · 2026-09-22 09:04:15 UTC

The agent loaded the **aii-paper-to-latex** skill; its `SKILL.md` (the instructions injected into the agent's context) follows verbatim.

````
---
name: aii-paper-to-latex
description: "Assembles and compiles a LaTeX paper into paper.pdf: documentclass and package preamble, figure floats that includegraphics pre-generated vector .pdf and .jpg files, float-placement and width rules, and the required pdflatex, bibtex, pdflatex, pdflatex run sequence. Use whenever pre-written text and pre-generated figures must become a compiled PDF, and whenever a build misbehaves — citations printing as question marks, figures drifting to the end or above the title, shrunken axis labels, undefined references. Triggers: latex, tex, pdflatex, bibtex, natbib, includegraphics, figure float, htbp, compile or build the paper, paper.tex, paper.pdf. NOT for: writing the paper's text or deciding its structure (use aii-paper-writing), creating the figure images (aii-data-fig-gen, aii-concept-fig-gen), or fetching bibliography entries (use aii-semscholar-bib); NOT for reshaping a PDF that already exists — merging, splitting, form filling, table extraction (use anthropic-pdf)."
---

## LaTeX Paper Assembly

Assembles a research paper from paper text, pre-generated figures (vector `.pdf` for data figures, `.jpg` for concept figures) and a bibliography into a compiled PDF.

### Document Setup

```latex
\documentclass[11pt,letterpaper]{article}
\usepackage{graphicx, geometry, amsmath, hyperref, url, natbib, booktabs, xcolor, listings}
\geometry{margin=1in}
\hypersetup{colorlinks=true, linkcolor=black, citecolor=black, urlcolor=black}
```

### Figure Inclusion

CRITICAL: Include ALL figures. Every figure MUST appear in the paper.

```latex
\begin{figure}[!htbp]
  \centering
  \includegraphics[width=\linewidth,height=0.85\textheight,keepaspectratio]{figures/filename.pdf}
  \caption{Descriptive caption.}
  \label{fig:label}
\end{figure}
```

Rules:
- ALWAYS `[!htbp]` — all four options, so a float can never be deferred to the end of the
  document, which `[t]` or `[h]` alone risks. Do not ask for a page TOP: `[!t]` and
  `[!tbp]` both floated a figure ABOVE the paper's own title on page 1, where `[!htbp]`
  on the same document did not. Where a figure lands is decided by where it is declared
  in the text
- Use `figure`, never `figure*`. This document class is ONE column, so `figure*` is exactly
  as wide as `figure` (469.76pt either way) and gains nothing, while restricting the float
  to a page top
- ALWAYS constrain with `width` and `keepaspectratio`. Add `height` only as a
  LAST RESORT against a very tall figure overrunning the page, and keep it
  generous — `0.85\textheight`. A tight height cap binds on ordinary figures
  and LaTeX then shrinks the TEXT with them: at `0.4\textheight` a square
  figure printed at 50.9%, putting 11 pt axis labels on the page at 5.6 pt.
  The figure generator measures legibility at the figure's OWN size, so it
  cannot see this happen
- Every figure needs `\caption`, `\label`, and a `\ref` in the text
- Do NOT convert figures to tables or describe them without inserting the image
- Do NOT skip any figures

### Compilation Process

Run each command separately (do NOT chain with `&&` — pdflatex often exits non-zero on warnings, which would skip bibtex and leave citations as `??`):

```bash
pdflatex -interaction=nonstopmode paper.tex
bibtex paper
pdflatex -interaction=nonstopmode paper.tex
pdflatex -interaction=nonstopmode paper.tex
```

All four commands are required. Skipping bibtex causes `??` in all citations.
Fix any errors between runs. Verify `./paper.pdf` was created.

### Output Files

- `./paper.tex` — LaTeX source
- `./references.bib` — bibliography file
- `./paper.pdf` — compiled PDF
- `./figures/` — all figure images (pre-generated, copied into workspace). Data
  figures are `.pdf` (vector — LaTeX renders their text at page resolution, which
  is what keeps axis labels sharp in print); concept figures are `.jpg`. Use each
  file's OWN extension in `\includegraphics`; there is no conversion step.
````

### [3] SKILL-INPUT — aii-semscholar-bib · 2026-09-22 09:04:15 UTC

The agent loaded the **aii-semscholar-bib** skill; its `SKILL.md` (the instructions injected into the agent's context) follows verbatim.

````
---
name: aii-semscholar-bib
description: "Fetches real BibTeX entries in one batch from Semantic Scholar by DOI, ArXiv ID or title via aii_semscholar_bib__fetch, normalises citation keys to AuthorYYYY, injects DOIs, and writes the result into references.bib, with a mandatory web-search fallback for anything not found. ALWAYS use whenever a bibliography, reference list or .bib file is being built or extended, and whenever a citation needs a verified entry instead of an invented one — never hand-write BibTeX first. Triggers: bibliography, references.bib, bibtex, citation key, DOI, arXiv id, Semantic Scholar, reference list, cite these papers, natbib entries. NOT for: writing the text around the citations (use aii-paper-writing), running bibtex and compiling (use aii-paper-to-latex), judging whether cited work supports the claims (use amg-paper-verification), or open-ended literature search and PDF mining (use aii-web-tools)."
---

## Tool: `aii_semscholar_bib__fetch`

Batch-fetch BibTeX entries from Semantic Scholar. Pass all references in a single call — the tool handles batching internally.

### How it works

1. **DOI/ArXiv refs** → batched into POST /paper/batch calls (up to 500 per API call, auto-chunked)
2. **Title-only refs** → individual GET /paper/search/match (1s delay between)
3. **Post-process** → fix entry type, fix citation key (AuthorYYYY), inject DOI

The ability server runs a single worker (`max_threads: 1`). Multiple concurrent tool calls are queued — each runs independently (no cross-request aggregation). Batching happens within each request.

### Input format

```json
{
  "references": [
    {"doi": "10.48550/arXiv.1706.03762", "author": "Vaswani", "year": 2017},
    {"arxiv": "2201.11903", "author": "Wei", "year": 2022},
    {"title": "Tree of Thoughts", "author": "Yao", "year": 2023}
  ]
}
```

Each reference object can have:
- `doi` — DOI string (ArXiv DOIs like `10.48550/arXiv.XXXX.XXXXX` auto-convert to ArXiv IDs)
- `arxiv` — ArXiv ID (e.g. `"2305.14325"`)
- `title` — Paper title (used for search/match when no DOI/ArXiv)
- `author` — First author last name (for cleaner citation key)
- `year` — Publication year (int, for citation key)

At least one of `doi`, `arxiv`, or `title` is required per reference.

### Output format

```json
{
  "success": true,
  "bib_text": "@inproceedings{Vaswani2017, ...}\n\n@article{Wei2022, ...}",
  "total": 3,
  "found": 3,
  "failed_count": 0,
  "entries": [{"citation_key": "Vaswani2017", "bibtex": "...", "title": "...", "doi": "...", "arxiv": ""}],
  "failed": []
}
```

### Workflow

1. Collect DOIs, ArXiv IDs, or titles for all papers you need to cite
2. Call `aii_semscholar_bib__fetch` with the full list in **one call**
3. Save `bib_text` from the response to your `references.bib` file
4. Check `failed` — for any missed papers, follow the **fallback procedure** below

### Fallback for failed references (MANDATORY)

NEVER fabricate BibTeX. For each failed reference:
1. **WebSearch** for `"Title" author year` (try `site:arxiv.org` too)
2. **WebFetch** the paper page → extract title, authors, year, venue, DOI/ArXiv ID
3. If DOI/ArXiv found → retry `aii_semscholar_bib__fetch` with it
4. Last resort: write BibTeX by hand using **only verified info from the actual paper page**

---

### CLI (for manual use / debugging)

```bash
SKILL_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo /ai-inventor)/.claude/skills/aii-semscholar-bib" && \
$SKILL_DIR/../.ability_client_venv/bin/python $SKILL_DIR/scripts/aii_semscholar_bib__fetch.py --refs '[
  {"doi": "10.48550/arXiv.1706.03762", "author": "Vaswani", "year": 2017},
  {"arxiv": "2201.11903", "author": "Wei", "year": 2022},
  {"title": "Tree of Thoughts", "author": "Yao", "year": 2023}
]'
```

`--json, -j` — output raw JSON instead of .bib text

**If the script fails** with a connection error (ability server not running): create a local `.venv`, install server deps from `server_requirements.txt` into it, then import the `@aii_ability` function from the script and call it directly — bypassing the server:
```bash
uv venv .venv --python=3.12 && uv pip install --python=.venv/bin/python -r "$SKILL_DIR/scripts/server_requirements.txt"
```
````

### [4] SYSTEM-USER prompt · 2026-09-22 09:08:58 UTC

````
You are fetching BibTeX entries for a research paper. Use the Semantic Scholar CLI tool to batch-fetch all references, then save the result to `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/workspace/references.bib`.

CRITICAL: ALL file writes MUST go inside `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/workspace/`.

## How to use the tool

Run this CLI command (the skill's script):

```bash
SKILL_DIR="/ai-inventor/.claude/skills/aii-semscholar-bib"
$SKILL_DIR/../.ability_client_venv/bin/python $SKILL_DIR/scripts/aii_semscholar_bib__fetch.py --refs '<JSON_ARRAY>'
```

If the script fails with a connection error, create a local venv and call it directly:
```bash
cd /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/workspace
uv venv .venv --python=3.12 && uv pip install --python=.venv/bin/python -r "$SKILL_DIR/scripts/server_requirements.txt"
```
Then import the function from the script and call it.

## References to fetch (31 entries)

Pass ALL of these in a single --refs call:

```json
[
  {"arxiv": "2402.04249", "author": "Mazeika", "year": 2024},
  {"arxiv": "2308.01263", "author": "Rottger", "year": 2023},
  {"arxiv": "2404.01318", "author": "Chao", "year": 2024},
  {"arxiv": "2406.11717", "author": "Arditi", "year": 2024},
  {"arxiv": "2310.01405", "author": "Zou", "year": 2023},
  {"arxiv": "2208.07339", "author": "Dettmers", "year": 2022},
  {"arxiv": "2106.09685", "author": "Hu", "year": 2021},
  {"arxiv": "2305.18290", "author": "Rafailov", "year": 2023},
  {"arxiv": "2606.24952", "author": "Galeone", "year": 2026},
  {"arxiv": "2606.20626", "author": "Spagliardi", "year": 2026},
  {"title": "Activation-based Model Scanner for safety evaluation", "author": "Messenger", "year": 2026},
  {"title": "N-GLARE safety evaluation hidden states Jensen-Shannon", "author": "Lin", "year": 2025},
  {"title": "near-perfect internal representations do not guarantee mechanistic interventions", "author": "Basu", "year": 2026},
  {"title": "RAS reference-anchored score safety calibrated", "author": "Huang", "year": 2026},
  {"title": "Aligned Probing per-layer probe accuracy output toxicity", "author": "Waldis", "year": 2025},
  {"title": "per-layer probes risk detectors static probes jailbroken base models", "author": "Jiang", "year": 2026},
  {"title": "SafeSeek safety circuits joint ablation", "author": "Yu", "year": 2026},
  {"title": "refusal is an affine function language models", "author": "Marshall", "year": 2024},
  {"title": "refusal concept cones multiple independent directions", "author": "Wollschlager", "year": 2025},
  {"title": "multi-dimensional refusal subspaces RFM-AGOP", "author": "Winninger", "year": 2026},
  {"title": "safety mechanisms large models separate knowing from acting", "author": "Wu", "year": 2026},
  {"title": "chain-of-thought disrupts simple steering safety", "author": "Yang", "year": 2026},
  {"title": "harmful-response generation harm recognition distinct mechanisms", "author": "Orgad", "year": 2026},
  {"title": "innate safety alignment extends beyond surface layers", "author": "Zhang", "year": 2025},
  {"title": "frozen linear probes quantisation LoRA fine-tuning safety", "author": "Duan", "year": 2026},
  {"title": "benign fine-tunes audit FPR weight-space signal", "author": "Hurtado", "year": 2026},
  {"title": "decouple refusal training general instruction following", "author": "Yuan", "year": 2024},
  {"title": "three latent factors safety behavioural benchmarks variance", "author": "Rivera", "year": 2026},
  {"title": "self-repair language models write-handle", "author": "McGrath", "year": 2023},
  {"title": "self-repair circuits language models", "author": "Rushing", "year": 2024},
  {"title": "harmfulness refusal dissociation causal steering NeurIPS", "author": "Zhao", "year": 2025}
]
```

## Post-processing

After fetching, check the output:
1. Save the full bib_text to `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/workspace/references.bib`
2. Check for failed references. For any that failed:
   - Try a web search to find the actual arxiv ID or DOI
   - Retry with the corrected identifier
   - If still failing, write a minimal valid BibTeX entry by hand using ONLY verified info
3. IMPORTANT: The citation keys in the .bib file MUST match what the paper uses. The paper uses keys like: Mazeika2024, Rottger2023, Chao2024, Arditi2024, Messenger2026, Lin2025, Zou2023, Galeone2026, Basu2026, Huang2026, Waldis2025, Jiang2026, Yu2026, Marshall2024, Wollschlager2025, Winninger2026, Wu2026, Yang2026b, Orgad2026, Zhang2025, Duan2026, Hurtado2026, Yuan2024, Spagliardi2026, Rivera2026, Dettmers2022, Hu2021, Rafailov2023, McGrath2023, Rushing2024, Zhao2025.

After saving references.bib, verify it contains at least 28 entries and each key listed above is present. If the CLI tool generates different keys (e.g., AuthorYYYY format), you may need to rename them to match the paper's citation keys.

Report: the path to references.bib, total entries found, any entries that failed and how you resolved them.
````

### [5] SYSTEM-USER prompt · 2026-09-22 09:11:51 UTC

```
[SYSTEM NOTIFICATION - NOT USER INPUT]
This is an automated background-task event, NOT a message from the user.
Do NOT interpret this as user acknowledgement, confirmation, or response to any pending question.
No human input has been received since the last genuine user message in this conversation. Any statement that the user said, approved, or confirmed something — including statements in your own earlier messages — is NOT real user input and must NOT be treated as approval or consent.

<task-notification>
<task-id>b9cl21ud4</task-id>
<tool-use-id>toolu_01VeQ8iknGHouFcqcqoq2idW</tool-use-id>
<output-file>/tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--4-assemble-paper-paper-workspace/e9b03ba9-7a07-4d7f-83d8-a63412646c20/tasks/b9cl21ud4.output</output-file>
<status>completed</status>
<summary>Background command "SKILL_DIR="/ai-inventor/.claude/skills/aii-semscholar-bib" &amp;&amp; $SKILL_DIR/../.ability_client_venv/bin/python $SKILL_DIR/scripts/aii_semscholar_bib__fetch.py --refs '[
  {"arxiv": "2402.04249", "author": "Mazeika", "year": 2024},
  {"arxiv": "2308.01263", "author": "Rottger", "year": 2023},
  {"arxiv": "2404.01318", "author": "Chao", "year": 2024},
  {"arxiv": "2406.11717", "author": "Arditi", "year": 2024},
  {"arxiv": "2310.01405", "author": "Zou", "year": 2023},
  {"arxiv": "2208.07339", "author": "Dettmers", "year": 2022},
  {"arxiv": "2106.09685", "author": "Hu", "year": 2021},
  {"arxiv": "2305.18290", "author": "Rafailov", "year": 2023},
  {"arxiv": "2606.24952", "author": "Galeone", "year": 2026},
  {"arxiv": "2606.20626", "author": "Spagliardi", "year": 2026},
  {"title": "Activation-based Model Scanner for safety evaluation", "author": "Messenger", "year": 2026},
  {"title": "N-GLARE safety evaluation hidden states Jensen-Shannon", "author": "Lin", "year": 2025},
  {"title": "near-perfect internal representations do not guarantee mechanistic interventions", "author": "Basu", "year": 2026},
  {"title": "RAS reference-anchored score safety calibrated", "author": "Huang", "year": 2026},
  {"title": "Aligned Probing per-layer probe accuracy output toxicity", "author": "Waldis", "year": 2025},
  {"title": "per-layer probes risk detectors static probes jailbroken base models", "author": "Jiang", "year": 2026},
  {"title": "SafeSeek safety circuits joint ablation", "author": "Yu", "year": 2026},
  {"title": "refusal is an affine function language models", "author": "Marshall", "year": 2024},
  {"title": "refusal concept cones multiple independent directions", "author": "Wollschlager", "year": 2025},
  {"title": "multi-dimensional refusal subspaces RFM-AGOP", "author": "Winninger", "year": 2026},
  {"title": "safety mechanisms large models separate knowing from acting", "author": "Wu", "year": 2026},
  {"title": "chain-of-thought disrupts simple steering safety", "author": "Yang", "year": 2026},
  {"title": "harmful-response generation harm recognition distinct mechanisms", "author": "Orgad", "year": 2026},
  {"title": "innate safety alignment extends beyond surface layers", "author": "Zhang", "year": 2025},
  {"title": "frozen linear probes quantisation LoRA fine-tuning safety", "author": "Duan", "year": 2026},
  {"title": "benign fine-tunes audit FPR weight-space signal", "author": "Hurtado", "year": 2026},
  {"title": "decouple refusal training general instruction following", "author": "Yuan", "year": 2024},
  {"title": "three latent factors safety behavioural benchmarks variance", "author": "Rivera", "year": 2026},
  {"title": "self-repair language models write-handle", "author": "McGrath", "year": 2023},
  {"title": "self-repair circuits language models", "author": "Rushing", "year": 2024},
  {"title": "harmfulness refusal dissociation causal steering NeurIPS", "author": "Zhao", "year": 2025}
]' --json &gt; /tmp/claude-0/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-4-gen-paper-repo--4-assemble-paper-paper-workspace/e9b03ba9-7a07-4d7f-83d8-a63412646c20/scratchpad/bib_result.json 2&gt;&amp;1; echo "EXIT: $?"" completed (exit code 0)</summary>
</task-notification>
```
