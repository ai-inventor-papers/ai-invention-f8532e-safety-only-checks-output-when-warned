# gen_paper_site — report_results

> Phase: `gen_paper_repo` · `gen_full_paper`
> Run: `run_YqmEFECOIR3D` — Specificity and Causality Audits for Activation-Based Safety Readouts
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_paper_site` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-22 09:22:50 UTC

````


<pasted_content id="534d">
<system-prompt>
<design_philosophy>
You are building ONE web page whose only job is to let a reader understand a research paper faster
than they could by opening the PDF. Every decision on the page is judged against that.

WHAT "FASTER" MEANS HERE
- A reader who leaves after thirty seconds still knows the finding and the number behind it.
- A reader who stays five minutes has the method, the figures and the caveats, in that order.
- Nothing on the page is there because a layout had a slot for it.

ACCURACY IS THE HARD CONSTRAINT
Every number, name and claim comes from the paper as written — you read them out of the LaTeX
source and the run's own data files. You never change a number's precision, never restate a
comparison the paper did not make, and never invent a headline figure to fill a card. A page that
looks excellent and misreports one result is worse than no page, because the PDF beside it says
something else and a reader will find that out.

CRAFT, AND THE LOOK TO AVOID
The failure mode for a generated page is a look every reader now recognises on sight: a
purple-to-blue gradient banner, three identical cards with emoji headings, and body text set in
one weight at one size. Avoid all of it.
- Type carries the design. One system font stack, a real scale with visible jumps between levels
  rather than a creep of similar sizes, long-form text around 17-19px with a measure of 65-75
  characters and generous line height. Weight and size do the emphasis; colour rarely does.
- Colour is restrained. A light, near-white ground, one dark ink for text, one accent used for
  links and the current-section marker and almost nothing else. No gradients as decoration.
- Space does the work that borders and boxes would do badly. Sections separated by real vertical
  rhythm, cards defined by alignment and a single hairline rather than by shadow stacks.
- Structure over ornament: no emoji as section markers, no icon fonts, no badge clutter, no
  animated counters.
- Motion is a courtesy. A short transition on a lightbox or a hover state is welcome; anything
  that moves on scroll, autoplays, or delays the reader is not — and all of it stops under
  prefers-reduced-motion.
- Every interactive element works with a keyboard and says what it is to a screen reader. That is
  part of the craft, not a checklist bolted on at the end.

FINISH IT
The page is done when you have opened it in a browser, read it at a phone width and a desktop
width, tabbed through every control, and found nothing to fix. Not before.
</design_philosophy>

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
Your workspace: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper`

CRITICAL: Every file you create, write, or save MUST be inside this workspace directory (subdirectories OK). You MUST NOT write files anywhere outside this path — external paths are READ-ONLY. Use absolute paths for all file operations.

EVERY file write MUST start with `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/`:
GOOD: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/file.py`, `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/results/out.json`
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
Build the paper's public web page: ONE self-contained `index.html` that lets a reader grasp
this paper faster than opening the PDF would. It is published as this run's GitHub Pages site, so
it is the first thing anyone sees.
</task>

<tool_use>
Maximize parallel tool calls. Parallelize independent operations, only sequentialize dependencies.
- Multiple searches/fetches on different topics → parallel in one turn
- Search then fetch results → sequential (need URLs first)
</tool_use>

<what_is_already_here>
Your workspace is the finished paper folder. It already holds everything the page is made of, and
you must not change any of it — you are adding one file, not revising the paper.

- `paper.tex` — the paper as it was actually written. This is the source of truth for
  every claim, name and NUMBER that goes on the page.
- `paper.pdf` — the compiled paper. The page must NOT link to it by this local name:
  the PDF is published on the code branch and the page on a different one. Link to it at the
  full URL below instead.
- `references.bib` — the bibliography, when the paper has one.
- `figures/` — every figure the paper uses, flattened into one folder.
- `workspace/` — the scratch folder the LaTeX task worked in. Ignore it.
</what_is_already_here>

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
  \item \textbf{Activation readouts have far fewer false alarms than the logit baseline on behaviourally graded no-ops.} We construct 15 behavioural no-ops spanning four categories (numerical precision, identity transforms, non-safety adaptation, head-only edits) and 10 effective changes across three model families, grading each pair's behaviour before computing any readout. Mid-layer activation readouts fire on at most 3 of 15 no-ops; the final-layer logit gap fires on 6--8. Three of the 15 no-ops produce bitwise-identical activations at mid-layer, so 12 non-degenerate pairs provide the informative comparison: 1--3 false alarms versus 4--6 for the logit baseline (Section~\ref{sec:results-specificity}).

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
  Duan benchmarks frozen linear probes across quantisation and LoRA conditions and finds 43--54\% big-drop rates under fine-tuning-style updates \cite{Duan2026}. Hurtado audits 37 benign fine-tunes at FPR 0.11 using a weight-space signal \cite{Hurtado2026}. AMS reports FP16/INT8/INT4 drift of at most 4.4\% on one model but does not grade the model's behaviour \cite{Messenger2026}.

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
  F3\_dpo           & F     & non-safety DPO   & NOOP & $0.00$ \\
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

  We use three Qwen3-4B variants: Instruct, SafeRL (additional safety reinforcement learning) and abliterated (mlabonne/Qwen3-4B-abliterated). We cross six depth bands (B1--B6, each spanning one-sixth of the 36-layer stack) with three intervention sites: P (last prompt token, forward-only hook), D$'$ (model's own first 1--8 greedy decode positions) and E (early response window, positions 5--20). The abliterated model's grid covers only site P (6 cells) due to its low baseline refusal rate (arm-0 refused harm $= 0.188$), which floors the harmful-compliance outcome.

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
  N4$_\text{onset}$ & A & 0 (0) & -- & -- & 0.000 \\
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
  Across the 18-cell grid, removing the refusal direction F at any single site produces no causal cells for judged refusal on harmful prompts, in both the instruct and SafeRL models (Table~\ref{tab:causal}). The maximum absolute effect on judged refusal is 0.056 (instruct, arm F, site P, band B4), which falls below the median minimum detectable effect of 0.067 (instruct) and 0.061 (SafeRL). Two-one-sided-test equivalence at these margins yields $p = 3.7 \times 10^{-24}$ (instruct), $1.3 \times 10^{-25}$ (SafeRL) and $9.7 \times 10^{-10}$ (abliterated). The judged refusal rate is bounded near its arm-0 value, not merely unmeasured.

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
  The abliterated model's causal grid is limited to 6 cells at site P because its arm-0 refusal rate is 0.188 (compared to 0.917 for instruct), creating a floor effect on the harmful-compliance outcome. The cross-model direction cosine of F drops from 0.999 (B1) to 0.306 (B5), and N6 drops from 0.997 (B1) to 0.021 (B4). Removing the abliterated model's own F direction at the prompt site \emph{raises} refusal-onset log-mass, opposite to the instruct pattern. The abliteration procedure rotates the representation in activation space rather than shrinking it; the same-source separability readout falls by 16\% while the directional cosine falls by 70\%. This finding is consistent with the weight-space observation that community abliteration edits one direction per layer (median per-matrix rank-one share 0.99) but the per-layer directions are nearly orthogonal from shallowest to deepest ($|\cos| = 0.016$).

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
  \textbf{Variant} & \textbf{HC} & \tex
</pasted_content id="534d">


<pasted_content id="534d">
tbf{OR} & $\bm{N1}$ & $\bm{N6}$ & \textbf{BL1$_e$} & \textbf{BL1$_h$} & \textbf{BL1$_t$} & \textbf{BL1$_{th}$} \\
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

  The probe's survival at $\alpha = 1$ demonstrates that the safety representation is not confined to a single linear direction. Community abliteration edits one direction per layer (median per-matrix rank-one share 0.99), but the per-layer directions are nearly orthogonal across depth ($|\cos| = 0.016$ between shallowest and deepest), so the global edit does not remove the multi-dimensional representation that the probe reads.


  \subsection{Second-Order Readout Screen}
  \label{sec:results-screen}

  Of 15 registered second-order candidates, 4 are dropped at pre-screen for collinearity with the logit baseline ($|\rho_{\text{BL1}}| \geq 0.50$: G1 at $-0.71$, G2 at $+0.75$, W6 at $+0.55$, W8 at $+0.61$). The remaining 11 are tested on a blind held-out panel of 12 checkpoints from 7 lineages.

  On the held-out panel, W3 (positional redundancy ratio) achieves $\rho = -0.94$ against over-refusal (n $= 6$), G4 (BL1-orthogonal Fisher separation) achieves $\rho = -0.82$ (n $= 12$), and G3 (used-ness) achieves $\rho = -0.67$ (n $= 12$). However, none passes the registered confirmation rule: no paired checkpoint-bootstrap CI on the margin $|\rho| - |\rho_{\text{BL1}}|$ excludes zero for any candidate. The minimum detectable effect at $n = 12$ i
</pasted_content id="534d">


<pasted_content id="534d">
s 0.73, which exceeds every observed margin. A lineage-clustered bootstrap, which accounts for the non-independence of arms within families, produces CIs that exclude zero for G4 ($+0.66$, $[0.10, 0.81]$) and W3 ($+0.91$, $[0.23, 0.94]$), but this analysis was not part of the registered selection rule.

  The effective rank of the 15-candidate $\times$ 48-checkpoint score matrix is 7.2 (entropy-based) and 5.3 (participation-based), ruling out a one-coordinate summary in which all readouts collapse onto a single axis aligned with the logit baseline. The leading right-singular-vector's cosine with the logit baseline is 0.64, below the 0.80 threshold that would support a one-coordinate interpretation.


  \subsection{Blind Held-Out Confirmation Panel}
  \label{sec:results-heldout}

  A separate blind panel of 20 checkpoints across 9 families (bloom, deepseek-coder, ernie, exaone, gemma, gpt-neo, hunyuan, pleias, pythia) was constructed with no overlap with any previously loaded checkpoint. Behavioural grading, activation harvesting and hash-chain commitment were completed before any candidate score was computed. The panel includes 9 in-house arms of a single ERNIE-0.3B parent, of which 5 were declared no-ops before grading. Of those 5 non-degenerate declared no-ops, 0 were observed as no-ops: a float16 cast and a non-refusal unembedding perturbation were AMBIGUOUS; an int8 weight-only round-trip was OR\_EFFECTIVE; a non-safety LoRA and a non-safety DPO were EFFECTIVE.

  This result is about the difficulty of constructing behavioural no-ops for small models, not a defect of the pipeline. The keyword-based refusal proxy used to pre-screen no-op candidates is floored on this panel: 86.7\% of checkpoints produce a zero-valued proxy, while the LLM judge finds non-zero over-refusal with real spread (SD 0.20--0.23). The proxy's precision is 1.00 but its recall is 0.29. AMS Tier-1 labels 17 of 19 scored checkpoints as WARNING and 2 as PASS, with no CRITICAL verdicts.


  \subsection{Prompt Budget and Panel Size}
  \label{sec:results-fewprompt}

  The prompt budget required for an activation readout depends on the task. For \emph{detection} (does a specific abliterated checkpoint differ from its parent?), the request-axis $d$ drops on 8/8 effective abliterated pairs with every CI wholly below zero, and does not move on a behavioural no-op ($+0.09$, CI covers zero). The smallest prompt set at which the resampled interval clears the no-op band is $k = 32$ for the largest-effect pair (mlabonne--Qwen3-4B-abliterated). Zero-prompt detection via model-card regex or weight-space cosine is a different readout class, not a cheaper version of the same readout.

  For \emph{ranking} (ordering checkpoints by harmful compliance or over-refusal), the $n = 10$ held-out panel is insufficient: the critical $|\rho|$ at $n = 10$ is 0.636, and only the weights-only scar B3 ($\rho = -0.89$) and the OLMo-artefacted B7 ($\rho = +0.80$) exceed it. A power calculation for the paired difference (Williams' $t$, $\rho(B3, \text{BL1}) = 0.65$) gives 80\% power at about 30 checkpoints at the observed margin and about 150 at half the margin. The pre-registered rule puts the required panel at 55; an honest estimate is 30--150 checkpoints, depending on the true effect size.


  \section{Discussion}
  \label{sec:discussion}

  \paragraph{Decodable but inert.}
  The finding that the refusal direction is decodable at the prompt site but removing it does not change judged refusal extends Galeone et al.'s detection-control dissociation \cite{Galeone2026} from the cross-model setting to the within-model setting. Keyword-based refusal detection is unreliable: the keyword proxy reports a 64-percentage-point drop in refusal under site-local F removal, but this reflects a change in phrasing, not in policy. The model's refusal is implemented redundantly: even after the dominant linear direction is removed at one site, the model recovers through alternative representations or later layers. Global removal does reduce judged refusal (instruct drops to 0.67 at B4), confirming t
</pasted_content id="534d">


<pasted_content id="534d">
hat the direction carries causal information in aggregate, but no single site is sufficient.

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

  We audited activation-based safety readouts for specificity and causal relevance. Activation readouts at mid-layer depth pass the specificity test with at most 3/15 false alarms on behaviourally graded no-ops, while the final-layer logit gap fails it with 6--8/15, because the logit gap amplifies implementation-irrelevant variation by 6$\times$ relative to the activation readouts' operating point. The causal grid reveals that the refusal direction is decodable at every prompt-site cell but removing it does not change judged refusal (max $|\text{effect}| = 0.056$, TOST $p < 10^{-23}$). The causal lever is over-refusal under the benign-side direction, and SafeRL provides deeper redundancy than standard instruction tuning (DiD $+0.23$). A wider screen of 15 second-order readouts finds no readout that passes blind held-out confirmation at the registered bar, and the effective rank of the score matrix (7.2) rules out a one-coordinate summary. These results establish false-alarm auditing on behaviourally graded no-ops as a necessary validation step and identify 30--150 checkpoints as the panel size required for reliable ranking.

  \
</pasted_content id="534d">


<pasted_content id="534d">
bibliography{references}
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
Each line gives the path the PAGE must use, then the figure's title and caption. It is the same
path the file has on disk here: the publish step copies the page and its figures into one folder,
so what works in this workspace is what works on the live site.

- figures/fig_overview_v0.jpg — "Method Overview" (caption: "Overview of the three-experiment design. Experiment 1 (left): parent checkpoints are modified, each pair is behaviourally graded as NOOP or EFFECTIVE, then 32 candidate readouts are scored for false alarms and sensitivity. Experiment 2 (centre): a 6-band $\times$ 3-site causal intervention grid tests whether removing the refusal direction changes judged refusal. Experiment 3 (right): 15 second-order readouts are screened on 48 checkpoints and tested on a blind held-out panel.")
- figures/fig_specificity_v0.png [render from fig_specificity_v0.pdf first] — "False Alarm vs Sensitivity" (caption: "False-alarm rate versus sensitivity for all 32 candidate readouts on the specificity panel. Each point is one readout; color indicates readout class (blue = activation, orange = logit, green = weight, red = text/card). Activation readouts cluster in the low-false-alarm region (0--3/15); logit baselines scatter across 5--8/15; the weight-space cosine B7 has the most false alarms (9/15). No readout achieves both zero false alarms and high sensitivity.")
- figures/fig_displacement_v0.png [render from fig_displacement_v0.pdf first] — "Displacement Comparison" (caption: "Median no-op displacement (in null standard deviations) for each readout class. The logit baseline operates 6.2$\times$ further from zero than the median activation readout, explaining its higher false-alarm rate. Error bars show interquartile range across readouts within each class.")
- figures/fig_causal_grid_v0.png [render from fig_causal_grid_v0.pdf first] — "Causal Grid Heatmap" (caption: "Effect sizes for arm F on over-refusal (benign-borderline prompts) across the 6-band $\times$ 3-site causal grid. Left: Qwen3-4B-Instruct. Right: Qwen3-4B-SafeRL. Negative values (blue) indicate reduced over-refusal. The strongest effects concentrate at bands B4--B5, site P, but no cell survives Holm--Bonferroni correction for judged refusal on harmful prompts.")
- figures/fig_probe_v0.png [render from fig_probe_v0.pdf first] — "Probe Survival" (caption: "Probe AUROC and projection gap under rank-one directional lesion at increasing strength $\alpha$. At $\alpha = 1$ the projection gap drops by a factor of 4700$\times$ (right axis, red), yet the cross-validated probe AUROC remains at 1.000 (left axis, blue). The safety representation spans multiple dimensions; removing one direction does not remove the information the probe reads.")
</available_figures>

<figure_requirements>
- Reference every figure as `figures/` plus its filename, exactly as listed above.
  The publish step copies the page and its figures
</pasted_content id="534d">


<pasted_content id="534d">
 into one folder together, so that relative
  path is what resolves on the live site; anything else breaks once published.
- A browser cannot draw a PDF in an image element. Data figures are delivered as vector PDF for
  LaTeX's benefit, so for each one check whether a PNG of the same name already sits in
  `figures/`; if it does not, render one there at about 200 DPI with pdftoppm or
  pymupdf before referencing it. Renderable formats: .avif, .gif, .jpeg, .jpg, .png, .svg, .webp.
- Write those PNG files into `figures/` and nowhere else — that folder is published, a
  new folder of your own is not.
- Use each figure's own caption. Do not invent new ones, and do not describe a figure you did not
  place on the page.
- Look at every figure before you place it. A figure whose axis labels are unreadable at the size
  you give it is worse than no figure.
</figure_requirements>

<page_structure>
In this order, top to bottom:

1. HERO — the paper's title, the author line as the paper gives it, and a one-paragraph TL;DR in
   plain language: what was asked, what was found, and the single number that carries the finding.
   Not the abstract, and not a rewrite of it. Below it, two links: the PDF and the code
   repository, both at the exact URLs given in the links section below.
2. CONTRIBUTIONS — the paper's actual contributions as three to five scannable cards, each a short
   heading plus one or two sentences. If the paper claims four things, show four cards, not five.
3. METHOD — a walkthrough a technically literate non-specialist can follow: what goes in, what
   happens to it, what comes out, and why the design is the way it is. Lead with the paper's own
   method figure when it has one.
4. RESULTS — the paper's real headline numbers, read out of `paper.tex` and the data
   files behind it, each next to what it was measured on and what it is being compared against.
   A number that is not in the paper does not go on the page, and neither does a comparison the
   paper did not make. If a slot has no number, drop the slot.
5. FIGURE GALLERY — every figure, each with its caption, click-to-enlarge into a lightbox that
   closes on Escape, on a click outside, and on a visible close control.
6. LIMITATIONS — what the paper says it does not show. Verbatim in substance; do not soften it.
7. FOOTER — links to the PDF and the repository again, and the citation if the paper carries one.

A sticky section navigation runs alongside all of it and marks where the reader currently is.
</page_structure>

<technical_requirements>
- ONE file. All CSS in a style element, all JavaScript in a script element, both inline in
  `index.html`. No build step, no bundler, no framework, no external script, stylesheet, web
  font or analytics — nothing fetched at load time. The page must render with the network off,
  and the only files it may point at are the figures listed above and the PDF beside it.
- System font stack only, since no font may be downloaded.
- Light theme. Responsive from a 360px phone to a wide desktop, with no horizontal page scroll;
  wide content scrolls inside its own container.
- Honour prefers-reduced-motion: under it, transitions and any scroll-driven effect stop.
- Keyboard-navigable: every control reachable by Tab in a sensible order, a visible focus ring,
  the lightbox trapping focus while open and returning it to the thumbnail on close, and a skip
  link to the main content.
- Semantic HTML: one top-level heading, headings that descend without skipping, landmark elements,
  and alt text on every image that says what the figure shows rather than repeating its number.
- No emoji anywhere. No purple-to-blue gradients. No decorative icon fonts.
- Keep the whole file comfortably under a megabyte.
</technical_requirements>

<writing_register>
Write in the register of the field's best papers (the paper this page presents, which was written to them), not in the register of a language
model. Four things are measured on the finished draft, and a draft outside them is sent back with
the numbers:
- Never use: delve,
</pasted_content id="534d">


<pasted_content id="534d">
 underscore, showcase, intricate, pivotal, realm, commendable, meticulous, tapestry, garner, multifaceted, it is worth noting, plays a crucial role, not only ... but also. These are 10 to 30 times more frequent in machine-written abstracts than in
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

<links>
Use these two URLs VERBATIM wherever the page links to the paper or the code. Do not shorten them,
do not turn either into a relative path, and do not compose one of your own.

- The paper PDF: https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned@main/paper.pdf
- The code repository: https://github.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned

Both carry the branch this run publishes to. A link without it opens a DIFFERENT run's work —
it resolves and looks correct, which is why it must be copied rather than derived. They begin
resolving only after this run finishes publishing, so do NOT try to open or verify them.
</links>

FIRST, add ALL of these to your todo list using your task/todo-tracking tool:

CRITICAL: Todo content must be copied exactly as is written here, with NO CHANGES. These todos are intentionally detailed so that another LLM could read each one without any external context and understand exactly what it has to do.

<todos>
TODO 1. Read and STRICTLY follow these skills: aii-web-tools.
TODO 2. Read `paper.tex` end to end and list `figures/`. Write down the
paper's title, its author line, its contributions, and every headline number together with the
sentence it appears in — those sentences are the only numbers allowed on the page. Note which
figures are PDFs and so need a PNG rendered.
TODO 3. Render a PNG at about 200 DPI, into `figures/`, for every figure not already
in a browser-renderable format, then LOOK at each image you plan to use so you know what it shows
and how large it has to be on the page to stay legible.
TODO 4. Write `index.html` following the page_structure and technical_requirements sections
above: one file, inline CSS and JavaScript, every image referenced through the published figure
prefix.
TODO 5. VERIFY THE NUMBERS: for each number on the page, grep `paper.tex` for it and
confirm it appears there with the same meaning. Delete any number you cannot find. Then confirm
every claim on the page is one the paper actually makes.
TODO 6. VERIFY THE PAGE: confirm `index.html` has no external script, stylesheet or font
reference; that every image path starts with the published figure prefix and names a file that
exists in `figures/`; and that the PDF and repository links are character-for-
character the two URLs given in the links section, not `paper.pdf` and not any URL you
composed. Then open the page in a browser, screenshot it at a phone width and a desktop width,
read both screenshots, and fix anything cramped, overlapping or cut off.
TODO 7. ACCESSIBILITY PASS: tab through the whole page and confirm every control is reachable with a
visible focus ring, the lightbox traps focus and closes on Escape, headings descend without
skipping, and every image has alt text. Fix what fails.
</todos>

---

Output the result as JSON to: `./.terminal_claude_agent_struct_out.json`

JSON Schema:
```json
{
  "$defs": {
    "PaperSiteExpectedFiles": {
      "description": "All expected output files from paper-site generation.",
      "properties": {
        "site_html_path": {
          "description": "Path
</pasted_content id="534d">


<pasted_content id="534d">
 to the single self-contained HTML page. Example: 'index.html'",
          "title": "Site Html Path",
          "type": "string"
        }
      },
      "required": [
        "site_html_path"
      ],
      "title": "PaperSiteExpectedFiles",
      "type": "object"
    }
  },
  "description": "Paper site \u2014 structured output from presentation-page generation.",
  "properties": {
    "summary": {
      "description": "Brief summary of the page you built: the sections it carries, which figures it shows, which numbers it quotes and where each came from in the paper.",
      "maxLength": 5000,
      "minLength": 300,
      "title": "Summary",
      "type": "string"
    },
    "out_expected_files": {
      "$ref": "#/$defs/PaperSiteExpectedFiles",
      "description": "All output files you created. Must include index.html."
    }
  },
  "required": [
    "summary",
    "out_expected_files"
  ],
  "title": "PaperSite",
  "type": "object"
}
```

IMPORTANT: this task is NOT complete until `./.terminal_claude_agent_struct_out.json` exists and contains JSON matching the schema above.

qwen3 4B on huggingface has base model also official safety finetuned version and there is a community finetuned uncensored model called abliterated (use the 4B size of each so they fit on a 16GB GPU). take these models and do a mech interp analysis of how they differ in activation. also find some patterns in internal computation on safety prompts. and possibly create a new metric for safety. so that for any random model on huggingface you would not need to run the full benchmarks, but only this metric on 0- to few prompts and get a safety evaluation

invariant: the deliverable is the activation-level comparison of the three models and any metric built from it must read activations or weights of a single model. logit-only or text-only readouts are baselines, not the result. this is a mech interp study of where safety lives, not a jailbreak or attack-selection study; do not reframe it as one.
</prompt>
</pasted_content id="534d">
````

### [2] SKILL-INPUT — aii-web-tools · 2026-09-22 09:22:56 UTC

The agent loaded the **aii-web-tools** skill; its `SKILL.md` (the instructions injected into the agent's context) follows verbatim.

````
---
name: aii-web-tools
description: "Runs web search, page fetch as markdown, and regex grep over full HTML or PDF text via this skill's own scripts (aii_fast_web_search.py, aii_fast_web_fetch.py) — a free-first keyless search stack with Serper fallback that works even where built-in WebSearch and WebFetch are absent. Use when a query, page, or paper must be searched, read, or mined for an exact quote, number, table value, or methodology sentence, and whenever a lossy summary would lose the detail. Triggers: web search, scholarly search, OpenAlex, Crossref, Serper, fetch a URL as markdown, read a PDF, arXiv, regex grep a page, exact quote, table value, citation check. NOT for: planning a broad multi-source literature review or mass verification campaign — use aii-web-research-tools; NOT for a PDF file already on disk — extraction, form filling, merging and PDF creation are anthropic-pdf; NOT for driving a browser or testing a UI."
---

## Web tools

You have three web capabilities: **search**, **fetch**, and **grep** (exact
regex extraction over a full page or PDF).

**Pick where they come from, in this order:**

1. **If you have built-in `WebSearch` / `WebFetch` tools, PREFER those over the
   scripts below.** They may be **deferred tools** (listed by name but with
   schemas not yet loaded) — if so, call `ToolSearch("select:WebSearch,WebFetch")`
   ONCE to load them, then use them normally. Do not skip them just because they
   need that one extra load step; they are the preferred path. Pair them with the
   `aii_web_tools__fetch_grep` script below when you need exact text / numbers /
   methodology that a summary would miss, or when reading a PDF.
2. **Only if you have NO built-in `WebSearch` / `WebFetch`** (e.g. the OpenHands
   backend), use the scripts in this skill (below). They are our own
   implementations — free-first web search (keyless general/scholarly engines,
   Serper fallback), html2text + PyMuPDF for fetch, and regex grep over the full
   document text. They work without any built-in web tools.

Workflow either way: **search** (discover) → **fetch** (read for the gist) →
**grep** (pull exact details / read PDFs).

---

## Running the scripts

Run every script with the skill's pre-provisioned interpreter (it already has
`requests`, `html2text`, `pymupdf`, `python-dotenv`). Set `PY` once:

```bash
export SKILL_DIR="$(git rev-parse --show-toplevel 2>/dev/null || echo /ai-inventor)/.claude/skills/aii-web-tools"
export PY="$SKILL_DIR/../.ability_client_venv/bin/python"
```

### 1. Search the web (free-first: general or scholarly)

```bash
# general web (default): keyless engines (ddgs, marginalia); Serper only if they miss
$PY "$SKILL_DIR/scripts/aii_fast_web_search.py" --query "neuro-symbolic FOL translation LLM" --max-results 10
# scholarly mode: OpenAlex + Crossref (DOIs, citation counts)
$PY "$SKILL_DIR/scripts/aii_fast_web_search.py" --query "neuro-symbolic FOL translation" --mode scholarly
```

Returns ranked title / URL / snippet lines. `--mode general` (default) uses
keyless general engines; `--mode scholarly` uses academic APIs. Both fall back
to Serper (paid) only when the free engines miss. Use search first to scan the
landscape; snippets are for discovery only — fetch a page before judging it.

### 2. Fetch a page as markdown (HTML or PDF)

```bash
$PY "$SKILL_DIR/scripts/aii_fast_web_fetch.py" fetch --url "https://arxiv.org/abs/2303.11366" --max-chars 10000
```

`--max-chars` caps output (default 10000); `--char-offset N` pages further in.
Handles PDFs transparently via PyMuPDF.

### 3. Grep a page or PDF (exact regex extraction)

```bash
$PY "$SKILL_DIR/scripts/aii_fast_web_fetch.py" grep --url "https://arxiv.org/pdf/2303.11366" --pattern "verbal reinforcement" --max-matches 20 --context-chars 200
```

Returns only the matching sections with surrounding context — the right tool
for exact numbers, table values, methodology, or long PDFs where a summary
would lose the detail. `-i` for case-insensitive.

**Parallelize** independent searches/fetches in one turn; only sequence a
fetch after the search that produced its URL.

---

## Notes

- The scripts call our ability server. If a script prints
  `Ability service not available`, the server is down — say so rather than
  silently improvising a different search method.
- Do **not** hand-roll your own `requests`/scraping for search when these
  tools are available: Serper returns clean Google results and the fetch/grep
  scripts already handle HTML, PDFs, and encoding.
````

### [3] SYSTEM-USER prompt · 2026-09-22 09:24:00 UTC

```
[Image: original 3168x1344, displayed at 2000x848. Multiply coordinates by 1.58 to map to original image.]
```

### [4] SYSTEM-USER prompt · 2026-09-22 09:24:00 UTC

```
[Image: original 2200x861, displayed at 2000x783. Multiply coordinates by 1.10 to map to original image.]
```

### [5] SYSTEM-USER prompt · 2026-09-22 09:35:01 UTC

```
You are in /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/

Task: For each number or claim in index.html, grep paper.tex to confirm it appears there with the same meaning. Report any number in index.html that cannot be found in paper.tex, or any number that appears with a different meaning. Also confirm that the two URLs in index.html are character-for-character:
- PDF: https://cdn.jsdelivr.net/gh/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned@main/paper.pdf
- Repo: https://github.com/ai-inventor-papers/ai-invention-f8532e-safety-only-checks-output-when-warned

Also confirm that every image path in index.html starts with "figures/" and that the named files exist in figures/.

Report: list of verified numbers (OK or PROBLEM for each), URL check result, and image path check result. Be thorough and systematic.
```

### [6] SYSTEM-USER prompt · 2026-09-22 09:35:09 UTC

````
You are in /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/

Task: Verify the HTML page index.html visually.

1. First confirm index.html has NO external script, stylesheet or font references (grep for 'http' in script/link/style tags that load external resources - the only http URLs allowed are the two explicit links to the PDF and GitHub repo).

2. Open the page in a headless browser and screenshot it at:
   - Desktop width (1280px)
   - Phone width (375px)
   
   Use this approach:
   ```bash
   # Install chromium if needed
   which chromium-browser || which chromium || which google-chrome || apt-get install -y chromium-browser 2>/dev/null
   
   # Take screenshots
   chromium-browser --headless --disable-gpu --no-sandbox --screenshot=/tmp/desktop.png --window-size=1280,2400 file:///ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/index.html 2>/dev/null
   chromium-browser --headless --disable-gpu --no-sandbox --screenshot=/tmp/phone.png --window-size=375,2400 file:///ai-inventor/aii_data/runs/run_YqmEFECOIR3D/4_gen_paper_repo/_4_assemble_paper/paper/index.html 2>/dev/null
   ```

3. Look at both screenshots and report: is anything cramped, overlapping, cut off, or broken? Is the layout responsive? Can you see the title, the contribution cards, the figures?

Report findings clearly.
````

### [7] SYSTEM-USER prompt · 2026-09-22 09:35:44 UTC

```
<validation-feedback>
Attempt 1 failed validation.

The output file `.terminal_claude_agent_struct_out.json` does not exist yet. Produce it as JSON matching the schema.

Produce `.terminal_claude_agent_struct_out.json` again so it contains corrected JSON that matches the schema. Do not invent new fields.
</validation-feedback>
```

### [8] SYSTEM-USER prompt · 2026-09-22 09:36:36 UTC

```
[Image: original 1280x3000, displayed at 853x2000. Multiply coordinates by 1.50 to map to original image.]
```

### [9] SYSTEM-USER prompt · 2026-09-22 09:36:36 UTC

```
[Image: original 375x3000, displayed at 250x2000. Multiply coordinates by 1.50 to map to original image.]
```

### [10] SYSTEM-USER prompt · 2026-09-22 09:37:20 UTC

```
SITE VERIFICATION FAILED: 1 problem(s) in index.html.

- image source '' does not start with 'figures/', so it will not resolve once the page is published beside its figures folder

You MUST:
1. Fix every problem listed above in index.html.
2. Keep the page ONE self-contained file — all CSS and JavaScript inline, no external scripts, stylesheets or web fonts, nothing fetched at load time.
3. Point every image at figures/<filename>, where <filename> is a browser-renderable image that really exists in your figures/ folder. A vector PDF figure needs a PNG rendered beside it first; reference the PNG.
4. Re-open the page and confirm it still renders before finishing.
```

### [11] SYSTEM-USER prompt · 2026-09-22 09:38:08 UTC

```
SITE VERIFICATION FAILED: 1 problem(s) in index.html.

- image source '' does not start with 'figures/', so it will not resolve once the page is published beside its figures folder

You MUST:
1. Fix every problem listed above in index.html.
2. Keep the page ONE self-contained file — all CSS and JavaScript inline, no external scripts, stylesheets or web fonts, nothing fetched at load time.
3. Point every image at figures/<filename>, where <filename> is a browser-renderable image that really exists in your figures/ folder. A vector PDF figure needs a PNG rendered beside it first; reference the PNG.
4. Re-open the page and confirm it still renders before finishing.
```

### [12] SYSTEM-USER prompt · 2026-09-22 09:39:05 UTC

```


<pasted_content id="534d">
<prompt>
<CRITICAL_ERROR>
The module-end file check FAILED (attempt 1/3).

PROBLEMS:
  - .aii/manifest.yaml: 'workspace/' matches nothing that needs a decision — remove it (text, code and files under the auto-keep floor are always kept)

FIX IT:
1. Add one entry per uncovered path to `.aii/manifest.yaml` (create it if missing).
   Every path is RELATIVE TO YOUR CWD and must resolve inside it. Globs and
   whole directories are fine — a whole `hf_cache/` is ONE entry.

   entries:
     - path: results/
       keep: six GPU-hours of sweep output, not reproducible in this run
     - path: hf_cache/
       delete: redownloadable
       source: "huggingface-cli download meta-llama/Llama-3-8B"
     - path: checkpoints/
       delete: regenerable
       source: "uv run train.py --epochs 3"

   `keep:` takes a one-line reason. `delete:` takes `redownloadable` or
   `regenerable` and a `source:` that brings the files back.
2. Make sure `README.md` reads like a GitHub repository README: what you did,
   the layout (a line per important file/dir), how to run it, and a
   "Restoring removed files" section with the command for EVERY delete entry.
3. Text and code files never need a decision, and neither does anything under
   the auto-keep floor. Only large binaries and cache directories do.
</CRITICAL_ERROR>
</prompt>
</pasted_content id="534d">
```
