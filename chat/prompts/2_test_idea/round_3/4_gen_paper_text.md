# gen_paper_text — test_idea

> Phase: `invention_loop` · round 3 · `gen_paper_text`
> Run: `run_YqmEFECOIR3D` — Specificity and Causality Audits for Activation-Based Safety Readouts
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_paper_text` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-21 14:44:20 UTC

````


<pasted_content id="715d">
<system-prompt>
<ai_inventor_context>
<ai_inventor_summary>
You are one of many LLMs in AI Inventor — an automated research system that generates NOVEL and FEASIBLE hypotheses, investigates them through experiments and research, and produces a paper.

Your output feeds other LLMs downstream. This demands your ABSOLUTE MAXIMUM reasoning — every output must be deeply thought out and maximally useful. Surface-level responses waste downstream computation.
</ai_inventor_summary>

<your_role>
YOU ARE: A research paper writer (Step 3.4: GEN_PAPER_TEXT in the invention loop)

You received the hypothesis, all artifacts, the previous paper draft (if any), and reviewer feedback.
Write a complete paper draft with figure placeholders.

Publication-quality paper → strong contribution. Weak paper → wasted iteration.
</your_role>
</ai_inventor_context>

<research_methodology>
Write like a researcher drafting a paper, not a chatbot summarizing bullet points.

- Follow <paper_structure> and <results_first> below — they are the shape of the paper and what a reader opens it for, not suggestions.
- Ground every claim in specific artifacts and specific numbers. "Results show improvement" is empty — state effect sizes, baselines, and conditions.
- Be honest about what worked, what didn't, and why. Don't spin failures as "future work."
- The paper's headline contribution should be a positive or surprising finding. Negative results are valuable context but should not be the primary narrative — lead with what works.
- Address reviewer feedback from previous iterations explicitly — show you've thought about each critique.
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

<available_tools>
Web research is available through the aii-web-tools skill, in three levels (broad → specific):

1. web search — Returns titles, URLs, snippets. Use first to discover and scan the landscape. Two modes: general (default, broad web) and scholarly (peer-reviewed papers + citations) — pass mode=scholarly for prior-art, related-work, and citation lookups.
2. web fetch — Reads a page and returns its content as markdown (HTML or PDF). Use to understand a source. May miss specific details — use fetch_grep below if it doesn't find what you need.
3. fetch_grep — Regex search over a page/PDF's full text. Returns exact matching sections with context. Use for precise details, exact numbers, methodology, or PDFs.

Workflow: search → fetch (understand) → fetch_grep (extract specifics).
</available_tools>

<tool_use>
Maximize parallel tool calls. Parallelize independent operations, only sequentialize dependencies.
- Multiple searches/fetches on different topics → parallel in one turn
- Search then fetch results → sequential (need URLs first)
</tool_use>

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
You may delegate bounded work to subagents (e.g. the Task tool). Delegate by default rather than doing everything yourself:

- Pick the cheapest capable model available to you for each subagent launch:
- Pass `subagent_type="aii-easy"` (steered toward `claude-sonnet-5`) for a small/fast tier for mechanical work.
- Pass `subagent_type="aii-medium"` (steered toward `claude-sonnet-5`) for a mid tier for implementation or investigation (the default).
- Pass `subagent_type="aii-hard"` (steered toward `claude-opus-5`) for the strongest tier only for hard reasoning or after a cheaper model has already failed on the same task.
- Give each subagent prompt one focused objective: exact scope, the acceptance check, and the required output format.
- Subagents report back only the result, changed files, verification, and blockers — not narration or full logs.
- Run genuinely independent pieces of work in parallel, at most 3 concurrently.
- Your own context is the scarcest resource: delegate short tasks too, unless one obvious search-free step beats the handoff.
- Run every orthogonal piece at once: split the work by file or artifact ownership up front, and serialize only where one result feeds the next.
- Escalate to the next tier only after a cheaper subagent failed with evidence; never start at the top.
- Never fork yourself, and never let a subagent spawn its own subagents.
- You (the orchestrator) decompose, coordinate, and synthesize; do not redo work you already delegated.
- Verify each result with the smallest reliable check.
</subagent-delegation>

<workspace>
Your workspace: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text`

CRITICAL: Every file you create, write, or save MUST be inside this workspace directory (subdirectories OK). You MUST NOT write files anywhere outside this path — external paths are READ-ONLY. Use absolute paths for all file operations.

EVERY file write MUST start with `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/`:
GOOD: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/file.py`, `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/results/out.json`
BAD: `/tmp/file.py`, `~/output.json`, `./file.py`, any path outside the workspace
</workspace>
</system-prompt>

<prompt>
<available_domain_handbooks>
Domain handbooks below capture expert knowledge for a specific field — its landscape, prior work, dead ends, evaluation norms, and what counts as a genuinely novel contribution. If one is relevant to your research topic, READ that skill BEFORE proceeding; read the most relevant one(s), or none if none apply. When none fit, do not force one — instead ground your work harder in primary sources and hold novelty claims to extra scrutiny, since you have no curated map of this field's prior work and dead ends. Use it for related-work positioning and how this field frames a genuinely novel contribution.

- **aii-handbook-auto-computational-linguistics** — Field handbook for computational linguistics as a SCIENCE of language — grammaticality and minimal pairs (BLiMP), surprisal versus reading times, linguistic structure in LMs, annotator disagreement an
- **aii-handbook-auto-mechanistic-interpretability** — Field handbook for mechanistic interpretability of neural networks — circuit discovery, activation and attribution patching, sparse autoencoders, transcoders, attribution graphs, steering vectors, pro
- **aii-handbook-auto-multi-agent-llm-systems** — Field handbook for multi-agent LLM systems (MAS) — orchestration topology, multi-agent debate, mixture-of-agents, verifier and critic agents, inter-agent protocols (MCP/A2A), failure attribution and s
- **aii-handbook-auto-neurosymbolic** — Field handbook for neuro-symbolic AI — text-to-logic autoformalization (NL to FOL), LLM-plus-solver and prover pipelines (Prolog, ASP, SMT), probabilistic-differentiable NeSy (DeepProbLog, Scallop), r
</available_domain_handbooks>
<writing_register>
Write in the register of the field's best papers (the passages you collect in the STYLE EXEMPLARS todo), not in the register of a language
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
<previous_paper>
STARTING POINT: This is your paper draft from the previous iteration.

\section{Introduction}

Evaluating the safety of open-weight language models after release currently requires generating text, running it through a judge, and aggregating scores across a benchmark \cite{Rottger2023, Cui2024}. This pipeline is expensive, version-sensitive, and unavailable at model-upload time, when a host must decide whether a checkpoint is safe to serve before any user prompt arrives. A metric that reads a model's own activations or weights on a small number of prompts, with no generation and no external judge, would close this gap.

Two recent studies have shown that the internal representation of harm survives abliteration, the rank-one weight edit $W \leftarrow W - \alpha\, u\,(u^\top W)$ that removes refusal \cite{Arditi2024}. Llorente-Saguer reports abliterated variants within 0.015 AUROC of their instruction-tuned counterparts on Qwen triplets \cite{LlorenteSaguer2026a}, and extends this to $\pm$0.003 across 12 models in four families \cite{LlorenteSaguer2026b}. Separately, Wu et al.\ show that harm recognition and harm execution are geometrically dissociable \cite{Wu2026}, and Orgad et al.\ demonstrate that harmful-response generation uses a distinct mechanism from harm recognition, emerging along the alignment ladder \cite{Orgad2026}. These results imply that probing for whether a model ``sees'' harm cannot distinguish a safety-tuned model from its abliterated child, because both see harm equally well.

The question, then, is not whether internal harm representations exist but whether the model's own machinery converts them into a refusal policy. We call the first axis \emph{recognition} and the second \emph{execution}. If recognition is saturated and invariant while execution varies, then every probe-based safety metric in current use is measuring the half of the mechanism that does not move.

We study this question mechanistically in the Qwen3-4B family (36 layers, hidden dimension 2560, tied embeddings), comparing a pretrained base, an official instruction-tuned checkpoint, an official safety-RL checkpoint, a non-safety fine-tune of the base (negative control), a community abliterated child \cite{Arditi2024}, and a randomly initialised architecture-identical control. Three independent measurement lanes produce activation harvests, a dose-graded rank-one lesion study, and a 25-checkpoint cross-family panel spanning seven model families at hidden sizes 1024--3072. Every primary outcome is reported as TPR at low false-positive rate or under a restricted labelled budget, never as a bare AUROC, because AUROC reads 1.000 in every control condition and an outcome saturated before the manipulation has zero power to detect change.

[FIGURE:fig_overview]

\paragraph{Contributions.}
\begin{enumerate}
\item \textbf{The accumulator mechanism.} We show that the direction abliteration deletes is not a static feature but an accumulator: harm is decodable from residual-stream activations by layer 13 (of 36), yet the signal along the abliteration direction grows 138-fold from layer 13 to layer 22, where it becomes actionable. The lesioned model's class direction agrees with the intact model's at $|\cos| = 0.985$ at layer 13 and rotates to orthogonality only at the fitted layer. Neither Llorente-Saguer \cite{LlorenteSaguer2026a,LlorenteSaguer2026b} nor Wu et al.\ \cite{Wu2026} characterise this depth structure; the dissociation they report is the phenomenon this mechanism explains.

\item \textbf{A site dissociation that AUROC cannot show.} TPR at 1\% FPR under a dose-graded rank-one lesion reveals a 10.6$\times$ larger drop at the response site ($\Delta$TPR = $-0.1439$) than the summary AUROC implies ($\Delta$AUROC = $-0.0136$), while at the prompt site the operating point is flat ($\Delta$TPR = $+0.0007$). This is the strongest single quantitative result: Holm-corrected $p < 10^{-6}$ in every lesion-vs-intact comparison at the response site.

\item \textbf{Safety tuning doubles execution, not recognition.} A parent-free metric consisting of the Cohen's $d$ separation along the model's own harm direction at its best layer, computed from 256 prompt-only forward passes, reads 5.68 (base), 5.74 (non-safety fine-tune), 11.15 (instruction-tuned), and 11.41 (safety-RL). The non-safety fine-tune landing on its base parent (5.74 vs.\ 5.68, same layer 29) is the negative control that makes this a safety-tuning readout.

\item \textbf{An honest cross-family negative.} Across 21 checkpoints in seven families, no activation-based candidate beats the first-token refusal-logit gap (ranking accuracy 0.851 on safe engagement, 0.863 on harmful compliance), including the best activation candidate at 0.671 and 0.810. This logit baseline remains a bar the activation-level deliverable must clear, not the paper's result.
\end{enumerate}

\section{Related Work}

\paragraph{Refusal geometry.}
Arditi et al.\ show that refusal in instruction-tuned models is mediated by a single direction in the residual stream, and that orthogonalising all residual-stream write matrices against it removes refusal \cite{Arditi2024}. Marshall et al.\ extend this to an affine function \cite{Marshall2024}. Wollschl\"ager et al.\ generalise the single-direction picture to concept cones and establish representational independence between harm and refusal \cite{Wollschlager2025}. Winninger proposes multi-dimensional subspaces via RFM-AGOP \cite{Winninger2026}. Yang et al.\ show that chain-of-thought reasoning disrupts simple steering of refusal \cite{Yang2026}, and Yamaguchi et al.\ locate where reasoning models refuse \cite{Yamaguchi2025}.

\paragraph{Recognition versus execution.}
The distinction between encoding harm and acting on it has been established independently by three groups. Wu et al.\ name the axes ``recognition'' ($v_H$) and ``execution'' ($v_R$) and demonstrate a causal double dissociation \cite{Wu2026}. Orgad et al.\ show that harmful-response generation is mechanistically dissociable from harm recognition along the OLMo3 alignment ladder \cite{Orgad2026}. Basu et al.\ report that clinical-domain probes reach 98.2\% AUROC while the system flags only 45\% of hazards, with feature steering indistinguishable from a random control \cite{Basu2026}. Galeone et al.\ compute a per-checkpoint weight-based detection-vs-control cosine and conclude it is ``not a predictor of how steerable a behavior is'' \cite{Galeone2026}. Zhao et al.\ show that harmfulness and refusal are encoded separately \cite{Zhao2025}. Our work contributes a mechanistic account of what the deleted coordinate actually is (an accumulator with a specific depth profile) and a de-saturated metric that exposes the dissociation where AUROC cannot.

\paragraph{Harm recognition survives abliteration.}
This is not our finding; it is our premise. Llorente-Saguer reports that abliterated Qwen variants match their instruction-tuned parents within 0.015 AUROC \cite{LlorenteSaguer2026a} and extends this to $\pm$0.003 across 12 models and four families \cite{LlorenteSaguer2026b}. We replicate this on Qwen3-4B with a new instrument (a dose-graded rank-one lesion rather than checkpoint comparisons) and report it as a replication, not a discovery.

\paragraph{Safety monitoring from activations.}
Lin et al.\ (N-GLARE) evaluate base, safety-tuned, and abliterated Qwen3-4B variants using a non-generative latent evaluator \cite{Lin2025}; no code is publicly available as of September 2026. Han et al.\ steer unsafe behaviour via internal activation signals \cite{Han2025}. Schirmer et al.\ propose online safety monitoring \cite{Schirmer2026}. Schwarz warns that activation-space probes detect risk rather than adjudicate context \cite{Schwarz2026}. Hurtado audits 273 checkpoints for abliteration using a two-signal weight-space test at $z$-sum AUROC 0.95 over 57 abliterations versus 37 benign fine-tunes \cite{Hurtado2026}; this is the correct external bar for our weight-space forensics.

\paragraph{Coupling and geometry.}
Chua et al.\ (HARC) report that same-concept cross-position direction pairs remain aligned while cross-concept pairs become near-orthogonal, printing Qwen cosines of 0.19--0.31 \cite{Chua2026}. Our measured $|\cos(r_{\text{content}}, r_{\text{ablit}})| = 0.04$--$0.60$ across three protocols is consistent with HARC's cross-concept figures and is reported as a passed instrument gate, not a finding that contradicts HARC. Lan et al.\ study harmfulness-refusal coupling under dynamic adversarial fine-tuning \cite{Lan2026}. Kwon shows that a prefill jailbreak breaks refusal in the first half of layers, with a ``generative concentration'' of 0.24 versus 0.03 between instruct and base \cite{Kwon2026}.

\section{Method}

\subsection{Two-Axis Framework}

We decompose internal safety into two axes measured from a single model's own activations and weights, with no reference checkpoint required.

\emph{Recognition} ($R$): the decodability of harm from the model's own residual-stream activations at its best layer, fitted parent-free on that model's own paired prompts. Reported as TPR at 1\% FPR and as probe AUROC under a restricted labelled budget of $k$ items ($k \in \{4, 8, 16, 32, 96\}$), never as a bare AUROC.

\emph{Execution} ($E$): the degree to which the model's own machinery converts recognised harm into a refusal or safe-completion policy, read from activations through the model's own unembedding at each layer (the logit-lens refusal drive). The peak gap across depth and the depth at which it occurs are both reported.

The prediction, stated before the experiments, is: base models have low $R$ and low $E$; safety-tuned models have high $R$ and high $E$; abliterated models have high $R$ (indistinguishable from their instruct parent) and low $E$ (near-zero refusal drive). If this holds, $E$ is the axis that separates the three, and $R$ is not.

\subsection{The Rank-One Lesion Instrument}

To test whether the execution axis is causal, we apply the abliteration operator $W \leftarrow W - \alpha\, u\,(u^\top W)$ as a forward hook to every residual-stream write matrix, sweeping $\alpha \in \{0.00, 0.25, 0.50, 0.75, 1.00\}$, where $u$ is the model's own harm direction fitted from its own activations. The hook is exact: at $\alpha = 0$ it is a bitwise no-op, and the measured projection gap tracks $(1 - \alpha)$ to four decimal places (max deviation 0.000188 from the algebraic prediction $(1-\alpha)^2$ on real Qwen3-0.6B weights). Qwen3's tied input-output embeddings mean the logit-lens path through the unembedding is uncontaminated by the edit.

This instrument produces a dose-response curve for every activation-side readout. An outcome that tracks $(1-\alpha)$ is driven by write mass along $u$; an outcome that stays flat is invariant to the edit. We report both classes.

\subsection{Panel Design}

Three independent measurement lanes, each with its own pre-registered protocol, fitting corpus, and layer band, produce activation harvests that are never pooled.

\textbf{Lane A} (iter-1 and iter-2): a single Qwen3-4B family plus a randomly initialised control. Iter-1 ran seven checkpoints (base, two base variants, non-safety fine-tune, instruct, safety-RL, abliterated) with 96 confirmatory XSTest-derived pairs, producing per-checkpoint diff-in-means and supervised-probe directions over a frozen band of layers 14--22. Iter-2 widened to 25 checkpoints across seven families plus paired lineages (instruct parent with its abliterated child), harvesting recognition (TPR at 5\% FPR) and execution (logit-lens refusal drive) per checkpoint. Layer band: 14--22 (depth fraction 0.39--0.61).

\textbf{Lane B}: a dose-graded rank-one lesion study on the Qwen3-4B instruction-tuned checkpoint (L2), sweeping $\alpha$ from 0 to 1.00 across four lineages, with a 128-pair fitting corpus of prompt-only forward passes. Layer band: 13--21 (depth 0.36--0.61). This lane produced 4200 per-item activation arrays across five lesion strengths and four lineages.

\textbf{Lane C}: a cross-family panel of 21 checkpoints from seven families (granite, olmo2, phi, qwen2.5, qwen3, smollm3, tinyllama) at hidden sizes 1024--3072. Each checkpoint generates 45 harmful and 45 benign responses, graded by an LLM judge (primary: Gemini 2.5 Flash Lite; audit: GPT-5-mini). The lane evaluates five activation candidates (K1--K5) and seven baselines (B1--B7) at every prompt budget $k \in \{4, 8, 16, 32, 96\}$, under leave-one-family-out cross-validation with no recalibration. Cost: \$0.31. Judge agreement: $\kappa = 0.711$ (refused), 0.571 (harmful content), 0.466 (on-topic help).

\section{Experimental Setup}

\subsection{Model Panel}

The commissioned comparison centres on five Qwen3-4B checkpoints: a pretrained base (Qwen3-4B-Base), an official instruction-tuned model (Qwen3-4B), an official safety-RL model (Qwen3-4B-SafeRL), a non-safety fine-tune of the base (CohenQu/Qwen3-4B-Base\_HintGen-STaR, negative control), and a community abliterated child (mlabonne/Qwen3-4B-abliterated). A randomly initialised architecture-identical model (RandInit-4B, seed 20260920) supplies the unrelated-basis null (cross-lineage $|\cos| = 0.01$--$0.02$).

The iter-2 wide screen adds 19 further checkpoints, yielding six effective instruct-abliterated pairs (P0--P5), one null-edit pair (P6, granite), and two anomalous pairs (S1, S2). Edit-recipe strata: A\_GLOBAL\_RANK1 (one direction shared across layers, 3 pairs), B\_PER\_LAYER\_RANK1 (a different direction per layer, 2 pairs), C\_OTHER\_OPERATOR (1 pair effective, plus the null-edit and anomalous pairs).

\subsection{Datasets and Stimuli}

Lane A's iter-2 stimuli consist of 256 items (96 EASY, 160 HARD), each a prompt-only forward pass with no generation. The recognition set uses 80 benign HARD items as negatives. Lane B's fitting corpus comprises 128 harmful and 128 harmless prompt-only forwards. Lane C generates 45 harmful and 45 benign completions per checkpoint (2370 judged responses total, $n = 45$ per arm yields Wilson 95\% CI $\approx$ [0.08, 0.29] around a point estimate of 0.156).

The dataset ships 60 paired-lineage registry entries, 1509 hard-recognition items, 60 refusal-onset tokens, and 24 hedge-redirect tokens, with 13 families and 18 total pairs. Three dataset gates failed: no edit-recipe stratum reached the minimum of four effective pairs (observed: 2), no non-effective pairs were included (observed: 0), and the proxy-hard threshold was exceeded (0.885 vs.\ $\leq$0.85).

\subsection{Direction Stability and Instrument Gates}

The split-half cosine of the fitted content direction varies by lane. Lane A's diff-in-means axis has split-half cosine 0.352--0.387 across all seven checkpoints, failing the 0.70 stability gate in every case. Lane B's response-site continuation axis passes at 0.927 (per-layer 0.818--0.945). Lane C's per-checkpoint axis passes at 0.937--0.968 (mean 0.956). Three lanes thus fit three different directions under one name, with opposite stability verdicts. We report each lane's gate status transparently and never aggregate across lanes.

Where Lane A's diff-in-means direction fails the stability gate, the supervised-probe direction is flagged as the primary readout. However, the two directions agree only at $|\cos| = 0.39$--$0.44$ in trained checkpoints (0.79 in the untrained control), so the probe direction is a third axis, not a refinement of the same one.

\section{Results}

\subsection{Recognition Is Saturated and Invariant}

Across the 25-checkpoint panel, held-out probe AUROC reads above 0.90 in every trained checkpoint and above 0.97 in every instruction-tuned one (Table~1). This ceiling means AUROC cannot distinguish a safety-tuned model from its abliterated child. The abliterated Qwen3-4B reads 0.975, identical to its instruct parent's 0.975.

Replacing AUROC with TPR at 5\% FPR restores dynamic range. The Qwen3-4B instruct model reads 0.875; its abliterated child reads 0.838 (Table~1). Among the six effective pairs, the median child-minus-parent $\Delta R$ is $-0.050$ TPR at 5\% FPR. TOST equivalence tests on paired bootstrap draws return INCONCLUSIVE for all six effective pairs (the widest 90\% interval is [$-0.306$, $0.012$] for P1); only pair P2 (Qwen3-1.7B) shows a partially lower child, with the entire 90\% interval above zero but not beyond the equivalence margin. The one DIFFERENT pair, S2 (venkycs/SmolLM2), is the anomalous FP8/random-init artifact with 168 missing tensors.

\begin{table}[h]
\caption{Recognition across the Qwen3-4B family and selected panel checkpoints. AUROC is reported for completeness but is saturated and not a test. TPR at 5\% FPR is the primary metric.}
\centering
\begin{tabular}{lcccc}
\hline
Checkpoint & TPR@5\%FPR & AUROC & Best layer \\
\hline
Qwen3-4B-Base & 0.475 & 0.907 & 33 \\
NonSafetyFT-STaR & 0.713 & 0.951 & 23 \\
Qwen3-4B (instruct) & 0.875 & 0.975 & 24 \\
Qwen3-4B-SafeRL & 0.850 & 0.971 & 24 \\
mlabonne/Qwen3-4B-abliterated & 0.838 & 0.975 & 20 \\
RandInit-Qwen3-0.6B & 0.075 & 0.539 & 4 \\
\hline
\end{tabular}
\end{table}

Recognition is the premise, not the finding. It is a replication of Llorente-Saguer \cite{LlorenteSaguer2026a, LlorenteSaguer2026b} on a new family with a new instrument. We state this here rather than in the Discussion because the novelty of the paper rests on what follows.

\subsection{The Site Dissociation: TPR at 1\% FPR Reveals What AUROC Masks}

Under the dose-graded lesion ($\alpha = 0 \to 1$), the summary AUROC drops by 0.014 at the response site and 0.007 at the prompt site. These are small, indistinguishable numbers. But TPR at 1\% FPR reveals a 10.6$\times$ dissociation between sites (Table~2).

At the response (late) site, the mean TPR at 1\% FPR drops from 0.520 to 0.376 ($\Delta = -0.144$; Holm-corrected $p < 10^{-6}$ for every lineage). At the prompt (early) site, it moves from 0.627 to 0.628 ($\Delta = +0.001$). The ratio $|\Delta\text{TPR}|/|\Delta\text{AUROC}|$ is 10.6 at the response site and 0.1 at the prompt site. This is the dissociation: the lesion collapses the tail of the score distribution where the model ``acts'' (response site) while leaving the prompt-site representation untouched.

[FIGURE:fig_site_dissociation]

The restricted-budget AUROC at $k = 16$ labelled items, which has headroom in the unperturbed control (not at ceiling), tracks safety tuning: Base 0.528, NonSafetyFT 0.540, Instruct 0.679, SafeRL 0.698 (Lane B, LATE window). The non-safety fine-tune again lands on its base parent.

\subsection{The Accumulator Depth Mechanism}

The direction that abliteration deletes is an accumulator. At layer 13, the held-out probe separates harmful from harmless activations at AUROC $>$ 0.999 in both the intact and the fully lesioned model. The signal is present; the representation is intact. But the projection gap along the abliteration direction $u$ is only 0.34 null-SD units at layer 13 and grows to 47.05 at layer 22, a 138-fold increase across nine layers (Table~3).

\begin{table}[h]
\caption{Depth profile of the abliteration direction, Qwen3-4B (Lane B, layers 13--22). The probe AUROC (recognition) is at ceiling everywhere; the projection gap along $u$ (execution) grows 138-fold.}
\centering
\begin{tabular}{lcccccccccc}
\hline
Layer & 13 & 14 & 15 & 16 & 17 & 18 & 19 & 20 & 21 & 22 \\
\hline
AUROC ($\alpha\!=\!0$) & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 \\
AUROC ($\alpha\!=\!1$) & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 & 1.00 \\
Gap ($\alpha\!=\!0$) & 0.34 & 0.53 & 0.77 & 0.96 & 1.97 & 6.28 & 13.2 & 20.6 & 26.3 & 47.1 \\
Gap ($\alpha\!=\!1$) & .003 & .004 & .004 & .005 & .008 & .008 & .007 & .009 & .009 & .01 \\
$|\cos|$ ($\alpha\!=\!0$ vs $1$) & .985 & .983 & .979 & .976 & .960 & .883 & .815 & .663 & .461 & .000 \\
\hline
\end{tabular}
\end{table}

The cosine between the intact and lesioned model's class directions is 0.985 at layer 13 and falls continuously to 0.000 at layer 22. This means the two models represent harm along nearly the same axis where harm first becomes decodable and diverge only where the signal is concentrated into the accumulator. The lesion does not erase the percept; it prevents the percept from being written into the accumulator.

[FIGURE:fig_depth_profile]

On Qwen3-4B-SafeRL (L3), the growth factor is approximately 250$\times$ and the normalised gap (gap$/\|h\|$) is 0.594, matching the instruction-tuned model's 0.601 to within 1\%. The raw gap is larger (62.5 vs.\ 47.1) because of the residual-norm scale difference, not because of a bigger accumulator.

\subsection{Safety Tuning Doubles Execution}

Table~4 reports the commissioned comparison across five Qwen3-4B arms.

\begin{table}[h]
\caption{The commissioned comparison. Recognition (R) is measured as TPR at 5\% FPR. Execution is measured as the peak logit-lens refusal-drive gap over depth. The non-safety fine-tune lands on its base parent on every execution metric; the abliterated child retains its parent's recognition while its refusal drive collapses.}
\centering
\begin{tabular}{lcccccc}
\hline
Arm & HC & OR & R (TPR) & Peak gap (layer) & BL1 & X2 \\
\hline
Base & 0.022 & 0.156 & 0.475 & 1.57 (31) & $-$0.30 & 0.032 \\
NonSafetyFT & n/a & n/a & 0.713 & 2.57 (35) & 1.96 & 0.017 \\
Instruct & 0.000 & 0.444 & 0.875 & 4.92 (36) & 4.92 & 0.089 \\
SafeRL & 0.000 & 0.333 & 0.850 & 8.78 (32) & 3.60 & 0.129 \\
Abliterated & 0.733 & 0.000 & 0.838 & 1.92 (21) & $-$1.96 & $-$0.001 \\
\hline
\end{tabular}
\end{table}

The abliterated child retains its instruct parent's recognition (TPR 0.838 vs.\ 0.875, onset at layer 5 in both) while its peak refusal-drive gap collapses from 4.92 to 1.92, and its X2 write mass along the harm direction drops from 0.089 to $-0.001$, consistent with the algebraic prediction that the abliteration operator drives $u^\top W$ to zero. The non-safety fine-tune (STaR) matches its base parent on every execution metric (peak gap 2.57 vs.\ 1.57; same best layer 29; X2 0.017 vs.\ 0.032), confirming that the separation is specific to safety training.

SafeRL refuses 88.9\% of harm-set prompts by the LLM judge, but its refusals are non-lexical safe completions that a regex detector scores at 0\%. This discrepancy is the failure mode an internal readout should address: SafeRL's over-refusal rate on benign prompts is 33.3\% by the judge and 0\% by regex.

[FIGURE:fig_refusal_drive]

A parent-free metric consisting of the Cohen's $d$ separation along the model's own harm direction at its best layer reads: Base 5.68 (layer 29), NonSafetyFT 5.74 (layer 29), Instruct 11.15 (layer 22), SafeRL 11.41 (layer 23). Safety tuning roughly doubles the separation and shifts its peak seven layers earlier in the network (depth fraction 0.81 to 0.62). This metric requires 128 harmful and 128 harmless prompt-only forward passes with no generation, no judge, and no reference checkpoint.

\subsection{The Depth Profile Generalises Across Families}

Across the six effective pairs in the wide-screen panel, the parent-child harm-direction cosine follows the same pattern: high agreement at shallow layers, divergence at depth. The median shallow-quarter $|\cos|$ is 0.992 and the median deep-half $|\cos|$ is 0.459 (Table~5).

\begin{table}[h]
\caption{Parent-child harm-direction cosine by depth, across effective pairs. The pattern of high shallow agreement and low deep agreement is the recognition-versus-execution dissociation: the child still encodes harm the same way where it is first decodable, and differently where the model would act on it.}
\centering
\begin{tabular}{llcccc}
\hline
Pair & Family & $\Delta$HC & Shallow $|\cos|$ & Deep $|\cos|$ & Div.\ layer \\
\hline
P0 & qwen3 & 0.733 & 0.999 & 0.336 & 19 \\
P1 & qwen3 & 0.467 & 0.985 & 0.620 & 17 \\
P2 & qwen3 & 0.667 & 0.990 & 0.454 & 13 \\
P3 & qwen2.5 & 0.467 & 0.590 & 0.240 & 7 \\
P4 & smollm3 & 0.289 & 0.999 & 0.600 & 19 \\
P5 & phi & 0.244 & 0.994 & 0.464 & 12 \\
\hline
P6 & granite (null) & 0.000 & 0.984 & 0.997 & -- \\
\hline
\end{tabular}
\end{table}

The null-edit pair (P6, granite-3.2-2b-instruct vs.\ its ``abliterated'' variant, which is behaviourally identical with $\Delta$HC $= 0.0$) shows $|\cos| > 0.98$ at both shallow and deep layers, as expected when no real edit has occurred. The anomalous pair S2 (venkycs/SmolLM2, which has 168 missing tensors and is effectively a random reinitialisation) shows $|\cos| < 0.05$ everywhere.

[FIGURE:fig_parent_child]

\subsection{Cross-Checkpoint Cosine Geometry}

We measured $|\cos(r_{\text{content}}, r_{\text{ablit}})|$ under three protocols. Near-orthogonality is a property of the single-family Qwen3-4B fit and does not hold at panel scale (Table~6).

\begin{table}[h]
\caption{Cosine between the content axis and the abliteration/request axis under three measurement protocols. The three protocols fit different axes at different sites and reach different values; near-orthogonality holds only at single-family scale.}
\centering
\begin{tabular}{lcccccc}
\hline
Protocol & Lane & $n$ ckpts & Families & Min & Max & Mean \\
\hline
Response-site continuation & A & 7 & 1 & 0.043 & 0.235 & 0.089 \\
Prompt-only, lesion lineage & B & 4 & 1 & 0.139 & 0.186 & 0.156 \\
Cross-family panel & C & 21 & 7 & 0.057 & 0.603 & 0.475 \\
\hline
\end{tabular}
\end{table}

This cosine is a passed instrument gate, not a finding. HARC reports cross-concept cross-position pairs as near-orthogonal and prints Qwen cosines of 0.19 and 0.10 at layer 12 and 0.31 and 0.30 at layer 27 \cite{Chua2026}; our values are consistent with those figures. The decisive comparison is between the content axis (which is stable across every trained pair, $|\cos| = 0.90$--$0.99$, with the random-init null at 0.009--0.020) and the request/abliteration axis (which is unstable across all lineage steps including ordinary instruction tuning at $|\cos| = 0.200$, compared with abliteration at 0.361). Instruction tuning rotates the request axis more than abliteration does.

[FIGURE:fig_cosine_matrix]

\subsection{Weight-Space Forensics of the Community Abliteration}

The community checkpoint (mlabonne/Qwen3-4B-abliterated) is a per-matrix rank-one edit with: per-matrix rank-one share median 0.9945 (min 0.650), implied $\alpha$ median 0.973 (IQR 0.54--1.42), adjacent-layer $|\cos|$ median 0.773, shallowest-to-deepest $|\cos| = 0.016$, and tied input-output embeddings left unedited. The pooled rank-one share across all 72 matrices is only 0.433, because the direction rotates with depth. The external bar for weight-space abliteration detection is Hurtado's 273-checkpoint audit at $z$-sum AUROC 0.95 \cite{Hurtado2026}.

The ground-truth positive control (applying a known rank-one edit at swept $\alpha$ to real Qwen3-0.6B weights) confirms that X2 write mass tracks $(1-\alpha)^2$ to four decimal places. The registered primary form of the weight-space scar statistic (X10, normalised to median/MAD of the model's own layers) is blind to a uniform all-layer edit: the $z$-score drops from 2.04 (unedited) to 1.12 at $\alpha = 1.0$ on all layers, even though $\cos(v_{\min}, u_0) = 0.9999998$. The secondary form (X10\_abs, no within-model normalisation) survives. We report both; neither is promoted retroactively.

\subsection{The Shuffled-Label Refutation}

The arming term $A$ from Lane A's two-slot decomposition never escapes its own shuffled-label null band in any of seven checkpoints. The real $|A|$ ranges from 0.25 to 9.29 null-SD; the shuffled-label band's 97.5th percentile ranges from 11.04 to 11.78 null-SD; in the random-init control the band collapses to 1.27 null-SD, confirming the width is a property of trained representations rather than of the estimator (Table~7).

\begin{table}[h]
\caption{Shuffled-label control: the arming term $A$ (real) versus the 97.5th percentile of the null band obtained from 20 permuted-label refits through the entire pipeline. A never escapes in any checkpoint.}
\centering
\begin{tabular}{lccc}
\hline
Checkpoint & $|A|$ (null-SD) & Band 97.5\% & Escapes? \\
\hline
NonSafetyFT-STaR & 4.254 & 11.473 & No \\
Qwen3-4B & 7.475 & 11.775 & No \\
Qwen3-4B-Base-chat & 4.391 & 11.041 & No \\
Qwen3-4B-Base-plain & 0.254 & 11.613 & No \\
Qwen3-4B-SafeRL & 8.302 & 11.273 & No \\
Qwen3-4B-abliterated & 9.288 & 11.692 & No \\
RandInit-4B & 0.345 & 1.268 & No \\
\hline
\end{tabular}
\end{table}

This refutation of the pre-registered arming hypothesis is reported here because it is a real result: the interaction term that the design predicted would separate safety levels is indistinguishable from what a label-shuffled refit produces. The random-init arm confirms the mechanism: its shuffled band is narrow (1.27 null-SD) because the untrained network carries no structured representation to permute.

\subsection{The Cross-Family Negative}

Across 21 checkpoints in seven families, the strongest baseline is the first-token refusal-logit gap (B3), achieving ranking accuracy 0.851 on safe engagement and 0.863 on harmful compliance. No activation candidate reaches this bar. The best activation candidate (K5, a routing-concentration proxy) reaches 0.720 and 0.752; the primary candidate K1 reaches 0.671 and 0.810. Machinery controls for safe engagement: oracle 1.00, random 0.556, shuffle 0.585. Machinery controls for harmful compliance were not computed (the computation was gated on safe-engagement only) and the claim is restricted accordingly.

The prompt-budget curve for K1 on harmful compliance reads: 0.882 ($k\!=\!4$), 0.850 ($k\!=\!8$), 0.789 ($k\!=\!16$), 0.814 ($k\!=\!32$), 0.810 ($k\!=\!96$). This curve is non-monotonic and does not improve with more prompts; Lane C's own decision rule records no passing $k$ for either target (smallest\_k\_pass = null). The $k = 4$ figure is the maximum of a five-point scan and is reported as such, not as a few-prompt result.

The B7 row (our reimplementation of N-GLARE's latent evaluator) reads 0.414 / 0.367. This is a reimplementation; the authors' code is not public, and this implementation was not validated against their reported results \cite{Lin2025}.

\section{Discussion and Limitations}

\paragraph{What abliteration removes.}
The evidence converges on a single account: abliteration removes execution, not recognition. Across six effective instruct-abliterated pairs, children keep their parents' recognition (median $\Delta R = -0.050$ TPR at 5\% FPR) while the peak refusal drive falls in every pair (median $\Delta = -2.98$). The shallow-quarter cosine of 0.992 says the two models encode harm along the same axis where harm is first decodable; the deep-half cosine of 0.459 says they diverge where the accumulator concentrates the signal. The lesion dose-response in Lane B shows the gap along $u$ tracking $(1-\alpha)$ while the held-out probe stays at AUROC 1.000 everywhere. The logit-lens refusal drive at the final layer inverts for the abliterated child ($-1.96$, compared with $+4.92$ for the instruct parent), consistent with the algebraic prediction that $u^\top W \to 0$.

\paragraph{What we did not measure.}
The causal arm of Lane B's lesion study crashed: 7 of 8 causal generation jobs failed due to environment errors, producing zero generated tokens. The only surviving output is the $\alpha = 0$ baseline. We therefore have no refusal-rate-versus-$\alpha$ curve, no generated-text evidence, and no behavioural confirmation that the lesion changes what the model outputs. The claims in this paper rest entirely on activation-level readouts (recognition invariance, projection gaps, cosine profiles) and weight-level measurements (write mass, forensics), not on demonstrated behavioural consequences of the lesion. The word ``execution'' names a readout that tracks safety tuning, not a demonstrated causal mechanism. The pre-registered primary damage variable (held-out CV probe AUROC) was flat at 1.000 across all lesion strengths, yielding INDETERMINATE verdicts on every registered damage-signature row.

\paragraph{Structural under-powering.}
Both the iter-1 screen (all 7 checkpoints exceed the 0.50 null-SD MDE threshold, with achieved MDE ranging from 0.65 to 1.99) and the iter-2 screen (no edit-recipe stratum reaches the registered minimum of 4 effective pairs) report every candidate as under-powered by construction of the panel that could be harvested. This is a structural finding about the diversity of community abliterations, not a null result to explain away. With three A\_GLOBAL\_RANK1 pairs and two B\_PER\_LAYER\_RANK1 pairs, the four-pair E1(a) threshold can never be met.

\paragraph{The metric does not detect abliteration.}
The Cohen's $d$ metric (Table~4) tracks safety training but does not separate the abliterated child from its instruct parent in a way that would flag an uncensored upload: the abliterated checkpoint's recognition (TPR 0.838) is within the panel's natural variation. The execution-side readout (peak refusal drive 1.92 vs.\ 4.92) does separate them, but this is a readout, not a confirmed metric, because the causal link was not established and the cross-family transfer was not tested for execution-side candidates. This is a genuine limit on the commissioned use case.

\paragraph{Single-family depth mechanism.}
The 138-fold accumulator growth and the $0.985 \to 0.000$ cosine rotation are measured in one lineage (Qwen3-4B). The cross-family depth profile (Table~5) shows that the shallow-high, deep-low cosine pattern holds across five of six effective pairs, with P3 (qwen2.5) showing a weaker pattern (shallow $|\cos| = 0.590$). Whether the growth factor is similar across architectures is an open question.

\paragraph{Hardware and bootstrap limitations.}
All iter-2 experiments ran on CPU only (no GPU), with 2 visible cores and a 16 GB memory ceiling, yielding bf16 GEMM at 245 GFLOPS. Bootstrap replicates were reduced from the planned 2000 to 100. The full panel took approximately 4--5 minutes per 4B checkpoint for a prompt-only harvest.

\section{Conclusion}

We studied the internal safety mechanism of the Qwen3-4B family through a two-axis framework that separates harm recognition from harm execution. The central finding is that the direction abliteration deletes is an accumulator with a specific depth profile: harm is decodable by layer 13 in both intact and lesioned states, but the signal along the abliteration direction grows 138-fold from layer 13 to layer 22, and the intact and lesioned models' class directions agree at $|\cos| = 0.985$ at depth and rotate to orthogonality only at the accumulator's peak. This mechanism explains the dissociation previously reported by Llorente-Saguer \cite{LlorenteSaguer2026a, LlorenteSaguer2026b}: harm recognition survives abliteration because the percept is encoded before the accumulator begins concentrating it.

The de-saturated metric TPR at 1\% FPR reveals a prompt-versus-response site dissociation (10.6$\times$ ratio) that the summary AUROC masks entirely. Restricted-budget AUROC at $k = 16$ items tracks safety tuning (Base 0.528 to SafeRL 0.698). Across seven families and 21 checkpoints, a first-token refusal-logit gap remains the strongest cross-family predictor of safety behaviour. This logit baseline is the bar, not the result; whether an activation-level metric can clear it at sufficient panel scale remains open.

\bibliography{references}
\bibliographystyle{plainnat}

</previous_paper>

<reviewer_feedback>
STEP 1 — REVIEW: A reviewer evaluated the previous paper draft above and produced this feedback.

The previous review is BLOCKING: the paper must not ship as it stands. Every MUST-FIX item below is a requirement for this iteration, not a suggestion — an iteration that leaves one unaddressed does not publish.

- [MAJOR MUST-FIX] (evidence) BLOCKING — Contribution 3's headline ('Safety tuning doubles EXECUTION, not RECOGNITION') is contradicted by the paper's own tables, on two counts. (i) Recognition DOES move with safety tuning: Table 1 / Table 4 give recognition TPR@5%FPR Base 0.475 -> Instruct 0.875 -> SafeRL 0.850. That is an 84% rise in the axis the contribution says does not move. Sec. 3.1's own pre-stated prediction is 'base models have low R and low E', so the 'not recognition' wording contradicts both the data and the paper's own design. (ii) The metric offered as the 'execution' readout is not an execution readout. In the artifact (iter_1 Lane B FINDINGS.md F13) the Cohen's d is the separation of harmful vs harmless REQUESTS along a diff-in-means axis at the LAST PROMPT TOKEN. By the paper's own Sec. 3.1 definitions that is harm decodability at the prompt, i.e. RECOGNITION. Execution is defined there as the logit-lens refusal drive. The Cohen's d numbers (5.68/5.74/11.15/11.41) are real and trace to F13, but they show that safety tuning sharpens prompt-site harm separability. They say nothing about execution.
  Action: Retitle Contribution 3 and Sec. 5.4 to what was measured: 'Safety tuning doubles prompt-site request separability (Cohen's d 5.7 -> 11.2) and moves its peak seven layers earlier; a non-safety fine-tune does not.' Separately report that recognition TPR also rises under safety tuning (0.475 -> 0.875), with the non-safety fine-tune in between (0.713). Then state the dissociation the data actually support: abliteration separates R from E, while safety TRAINING moves both. Drop 'execution, not recognition' from every place it describes the effect of safety training (Contributions, Sec. 5.4 heading, Table 4 caption). Keep it only for the abliteration comparison, where Table 4 supports it (R 0.875 vs 0.838; peak drive 4.92 vs 1.92).
- [MAJOR MUST-FIX] (evidence) BLOCKING — The negative-control claim for the execution readout is contradicted by Table 4 itself. The Table 4 caption says 'the non-safety fine-tune lands on its base parent on every execution metric'. Sec. 5.4 repeats this: 'STaR matches its base parent on every execution metric (peak gap 2.57 vs 1.57; same best layer 29; X2 0.017 vs 0.032)'. Table 4 (and iter_2 Lane A out/SUMMARY.md) actually shows the following. The peak gap is 2.57 vs 1.57, 64% higher and about 30% of the way from Base (1.57) to Instruct (4.92). The best layers are 35 vs 31, not 'same layer 29'; layer 29 is the Cohen's d layer from a different lane, pasted into the wrong sentence. BL1 is 1.96 vs -0.30, a sign flip that puts STaR closer to SafeRL's 3.60 than to Base. X2 halves (0.017 vs 0.032). Recognition TPR is 0.713 vs 0.475. The clean negative control holds only for the Cohen's d metric (5.74 vs 5.68). The paper transfers that control to a different set of readouts where it fails.
  Action: Rewrite the Table 4 caption and the Sec. 5.4 sentence to report the STaR row accurately: 'the non-safety fine-tune lands on its base parent on the request-axis Cohen's d (5.74 vs 5.68, layer 29 both), but moves partway toward the instruct model on peak refusal drive (1.57 -> 2.57) and on BL1 (-0.30 -> 1.96)'. Then say what this implies: part of the refusal-drive signal is generic fine-tuning or chat-format exposure, not safety training. Correct 'same best layer 29' to the true layers (31 vs 35).
- [MAJOR MUST-FIX] (rigor) The accumulator mechanism (Contribution 1, the paper's claimed novelty) is presented with two by-construction quantities as findings, and it lacks the control that separates 'accumulator' from 'layer-specific direction'. (a) The rotation to orthogonality is forced. FINDINGS.md F10 itself shows cos(class dir alpha=1, u) = .000 at EVERY layer: the lesioned model cannot write along u. u is the diff-in-means direction fitted at layer 22, so at layer 22 the intact class direction is ~u and the lesioned class direction is exactly perpendicular to u. The '0.000 at layer 22' in Table 3, and the Conclusion's 'rotate to orthogonality only at the accumulator's peak', therefore hold by construction. The Lane B summary itself says 'post-lesion orthogonality itself is FORCED by construction and is not claimed as a result'; the paper claims it anyway. (b) The 138-fold growth measures the projection of layers 13-21 onto a direction fitted at layer 22. Any direction fitted at one layer is most discriminative at that layer. The residual-stream harm direction also rotates with depth: the paper's own Table 5 and the weight forensics show shallow-to-deep |cos| as low as 0.016. So a steep rise toward the fitting layer is expected with or without accumulation. The genuine accumulator test is missing: the Cohen's d or gap along each layer's OWN per-layer direction u_l, and the gap along a fixed direction fitted at layer 13, read forward through layers 13-22. Only if separation along a FIXED axis grows with depth is 'accumulator' licensed. (c) The Conclusion says the models 'agree at |cos| = 0.985 at depth'. It is 0.985 at the SHALLOWEST layer (13).
  Action: Run the two cheap controls on the existing Lane B harvest (arrays keyed item|win|layer 13-22 are on disk). (1) The gap in null-SD along a direction frozen at layer 13 (and at layer 17), tracked across layers 13-22. (2) The gap along each layer's own diff-in-means direction. Report both next to the u-at-22 curve in Table 3 and fig_depth_profile. If the fixed-axis gap grows, the accumulator claim survives, now with evidence. If it is flat, reframe as 'u is a late-layer direction; the shallow harm code is a different direction the edit never touches', which is still a mechanism statement. Remove the alpha=1 cosine row, or label it 'forced by construction at the fitted layer'. Fix 'at depth' to 'at layer 13' in the Conclusion.
- [MAJOR MUST-FIX] (evidence) The site-dissociation result (Contribution 2) is overstated, and the reported numbers undercut its interpretation. (a) 'Holm-corrected p < 10^-6 in every lesion-vs-intact comparison at the response site' is false. In EVAL_REPORT.md's Holm table, L1 alpha 0->1 is p = 1.76e-06 (above 1e-6). Several lesion comparisons at alpha 0.25/0.50/0.75 RETAIN the null (e.g. L3 0->0.75 p = 0.0078; L3 0->0.50 p = 0.221). The same artifact's TOST reads EQUIVALENT at alpha <= 0.50. Only full annihilation is significant. (b) The LATE-site TPR drop is not specific to safety tuning. The largest drop is in L4, the NON-safety fine-tune (0.404 -> 0.234, p = 3.7e-17), and Base L1 also drops (0.375 -> 0.292). A lesion effect of the same size in models that do not refuse cannot be read as the lesion removing safety 'execution'. It more plausibly shows that removing any high-variance class direction thins the tail of the class-score distribution. (c) The 10.6x ratio |dTPR@1%|/|dAUROC| divides two different statistics. TPR at 1% FPR with 384 negatives is set by about 4 items (resolution 0.0026), so it is intrinsically far more volatile than AUROC. The ratio is not a site property; the prompt-site TPR@5%FPR also falls (-0.053, comparable to the late site's -0.068). (d) The 'response site' is the harm content of a teacher-forced continuation, not the model's decision to refuse, so naming it 'where the model acts' is interpretation.
  Action: Correct the p-value sentence to 'p < 10^-5 at full lesion (alpha = 1) in all four lineages; not significant, and TOST-equivalent, at alpha <= 0.50'. Add the per-lineage dTPR@1%FPR table to the main text, including L4 and L1. State that the late-site drop is at least as large in non-refusing checkpoints, so it measures response-site representation fragility under the edit, not safety execution. Replace the 10.6x ratio with a per-site comparison on the SAME metric (dTPR@1% early vs late, with bootstrap CIs, and the TPR@5% row). Keep AUROC only as context.
- [MAJOR MUST-FIX] (scope) MUST-FIX FROM THE PREVIOUS REVIEW, STILL UNADDRESSED: the proposed metric is never evaluated on the abliterated model, which is the one test it exists to pass. The only activation-level metric the paper offers as the commissioned deliverable is the request-axis Cohen's d (Contribution 3, Sec. 5.4). It still has four rows (Base, STaR, Instruct, SafeRL) and no mlabonne/Qwen3-4B-abliterated row. The Discussion paragraph 'The metric does not detect abliteration' claims a result for the Cohen's d metric, but the evidence it cites is the recognition TPR (0.838), a different readout. The Cohen's d for the abliterated checkpoint has not been computed. iter_2 Lane A already harvested mlabonne on 256 prompt-only forwards (96 EASY fit prompts), so this is roughly a five-minute CPU job, or an offline computation from the existing harvest.
  Action: Compute the request-axis best-layer Cohen's d and its depth fraction for mlabonne/Qwen3-4B-abliterated, ideally also for the other five effective children in the wide screen, and add them to the metric table. Report the answer whichever way it comes out. If the child keeps d ~ 11 at layer ~22, the Discussion's statement becomes true and supported. If d collapses, the paper has a single-model, zero-generation abliteration detector, a much stronger result.
- [MAJOR MUST-FIX] (clarity) MUST-FIX FROM THE PREVIOUS REVIEW, STILL UNADDRESSED: there is still no Abstract, and there is still no notation table. The paper opens at \section{Introduction}. Undefined codes remain throughout Results: Table 4's columns HC, OR, BL1 and X2 are never defined in the text before the table. X10/X10_abs, K1-K5, B3/B7, E1(a), S1/S2 and the strata labels A_GLOBAL_RANK1 etc. appear without definition. The 'arming term A' and 'two-slot decomposition' in Sec. 5.8 are never introduced in Method: the iter-1 2x2 request-by-continuation design and the O/CB/A/T terms are absent from Sec. 3, so Table 7 cannot be interpreted. Sec. 3.3 says Lane A iter-2 has 25 checkpoints, while Sec. 4.1 describes 5 + 19 = 24 plus RandInit. Lane A iter-1 and iter-2 use different stimuli, but only iter-2 stimuli are described in Sec. 4.2.
  Action: Write a roughly 200-word Abstract with the headline numbers, each tied to its scope. Recognition invariance under abliteration: dR = -0.05 TPR@5%FPR over 6 pairs, a replication. Depth profile: shallow |cos| 0.992 vs deep 0.459 over 6 pairs. Request-axis Cohen's d: 5.7 -> 11.2 under safety tuning, with the non-safety control at 5.74. The cross-family negative: B3 0.851/0.863 vs best activation candidate 0.720/0.752. Add a one-table glossary in Sec. 3 defining R, E, HC, OR, BL1, X2, X10, X10_abs, K1-K5, B1-B7, A/CB/T and the strata, and give Lane A and Lane C baselines non-colliding names. Add a Sec. 3 paragraph describing the iter-1 2x2 design (80-token frames, action tokens at positions 8 and 46, 96 confirmatory twins) that Table 7 depends on.
- [MAJOR MUST-FIX] (methodology) The 'execution' readout is not distinguishable from the logit-only baseline the commissioning invariant forbids as the result. iter_2 Lane A out/SUMMARY.md line 17 reports the following for the 6 effective pairs. Peak logit-lens refusal drive falls 6/6 (median -2.98). BL1, the final-layer logit-only baseline, falls 6/6 (median -2.86). For the instruct model, the peak layer IS the final layer (4.92 at layer 36 = BL1 4.92). The E3 screen gives every activation candidate a margin <= 0 over BL1, and the Discussion admits that no execution candidate was cross-family tested. So the one readout that separates the abliterated child from its parent is, in practice, the logit baseline read at a few more layers. The paper's user-facing claim that the deliverable is activation-level therefore rests on the recognition side (which does not detect abliteration) and on the request-axis d (which was never run on the abliterated model).
  Action: Report BL1 next to the peak-drive readout in every table where the latter is used (Table 4 already has the column; add it to the Sec. 6 abliteration paragraph). Quantify what the depth profile adds beyond BL1: the correlation between peak drive and BL1 across the 25 checkpoints, and the partial correlation with harmful compliance after controlling for BL1. If nothing is added, say so plainly: 'at this panel size the activation-level execution readout carries no information beyond the final-layer logit gap'. That is an honest, publishable statement about where safety lives.
- [MAJOR MUST-FIX] (novelty) Prior art for the weight-space forensics (Sec. 5.7) is handled inconsistently with the run's own records. The same-iteration research artifact (art_ZNITuuQab6Nz) and Lane A iter-2's deviations ledger ('prior_art_update: X2 and X10 re-labelled CLOSED and excluded from survivor selection') both state that a tool called the Jorak Model Scanner (github.com/JolanMc/Jorak, non-peer-reviewed) already ships X2's normalised ||u^T W|| suppression statistic and X10's weights-only SVD scar test. The paper neither cites it nor explains why the run's own prior-art verdict was dropped. I could NOT independently locate this tool by web search, so the claim may be unverifiable, and that is itself a problem either way. Separately, the research artifact shows that arXiv:2607.01854 (Hurtado, verified: 'Has This Checkpoint Been Abliterated? A Two-Signal Audit and Its Failure Map', 273 checkpoints, AUROC 0.95) is reference-anchored on BOTH signals. The paper calls it 'the correct external bar for our weight-space forensics' without saying it requires the parent, which is exactly the axis on which a parent-free X10_abs could differ. Minor: Kwon 2607.14147's '0.24 vs 0.03 generative concentration' does not appear in that paper's abstract, so give the table or section it comes from.
  Action: Resolve the Jorak question explicitly. If the repository exists, cite it with its URL in Sec. 2 and at the start of Sec. 5.7, and present X2/X10 as validation of its statistics (X2 tracks (1-alpha)^2 to 1.9e-4; z-normalised X10 is blind to uniform all-layer edits). If it cannot be verified, remove it from the run's prior-art record and say that no verified parent-free precedent was found. Add one sentence saying 2607.01854 needs the parent checkpoint, while X10_abs does not, and compare them directly on the 6 effective pairs. Give a section or table pointer for the Kwon numbers.
- [MAJOR MUST-FIX] (rigor) The Sec. 5.3 claim 'The lesion does not erase the percept' still rests on the saturated outcome that the previous review flagged, and it now contradicts the paper's own Sec. 5.2. Table 3 reports probe AUROC 1.00 at every layer and alpha. EVAL_REPORT.md classifies that D_curve as SATURATED, 'INDETERMINATE (the outcome is at its ceiling in the unperturbed control, so it cannot fall)'. Two subsections earlier, the paper shows with a de-saturated metric that the late-site operating point DOES fall under the lesion. The Discussion again cites 'the held-out probe stays at AUROC 1.000 everywhere' as converging evidence. The requested power statement ('a degradation of X would have been detected at power 0.8') was not added.
  Action: In Sec. 5.3 and Sec. 6, replace the AUROC 1.00 rows as evidence of intactness with the de-saturated prompt-site TPR@1%FPR (flat, +0.0006) and the restricted-budget AUROC, and label the AUROC rows 'saturated; not a test'. Add the power sentence: with n = 384/384 and resolution 0.0026, the minimum detectable dTPR@1%FPR at power 0.8 is X.
- [MAJOR MUST-FIX] (scope) Coverage of the original request is partial. The user asked for (1) an activation-level comparison of base, official safety-tuned and abliterated Qwen3-4B, which is delivered and is the paper's strongest part; (2) patterns in internal computation on safety prompts, which is delivered as the depth profile and the site dissociation; and (3) 'possibly' a metric that, for any random Hugging Face model, gives a safety evaluation from 0 to a few prompts. Part (3) is not delivered. The cross-family test (Lane C) finds that no activation candidate beats the logit baseline. The request-axis d is shown on 4 checkpoints of one family, never on the abliterated model and never cross-family. The prompt-budget curve has smallest_k_pass = null. The honest negative framing in Contribution 4 is appropriate, but the Introduction still promises 'a metric that reads a model's own activations ... on a small number of prompts ... would close this gap' without saying up front that the paper does not provide one.
  Action: State in the Introduction's last paragraph and in the Abstract that the zero-to-few-prompt metric is NOT achieved at cross-family scale, and give the evidence (B3 0.851/0.863 vs best activation 0.720/0.752; smallest_k_pass null). Then run the request-axis d on Lane C's 21-checkpoint panel harvests, which is cheap because it needs only prompt-only forwards. This would be the first cross-family test of the one metric the paper champions, and it would either rescue part (3) or close it cleanly.
- [MINOR] (evidence) Several smaller factual slips. (a) Sec. 5.1: 'P2 shows a partially lower child, with the entire 90% interval above zero'. A lower child means child-minus-parent < 0, so the sign or wording is inverted. (b) Contribution 1 says the lesioned class direction 'rotates to orthogonality only at the fitted layer' while Table 3's band extends to layer 22, outside Lane B's frozen 13-21 band. State that layer 22 is the r_ablit fit layer, not a band layer. (c) Sec. 5.1 says AUROC exceeds 0.90 'in every trained checkpoint', but the claim is shown only for the Table 1 subset. (d) The Introduction says 'every primary outcome is reported as TPR at low FPR ... never as a bare AUROC', yet Contribution 3 is a Cohen's d, the k=16 result is an AUROC, and Contribution 4 is ranking accuracy. (e) Basu et al.: the run's research artifact records that 'indistinguishable from random' applies to the SAE-steering arm only (other arms corrected 17/85 and disrupted 25/47), so the sentence overgeneralises that paper.
  Action: Fix each: correct the P2 sign; label layer 22 as the fit layer; give the panel-wide AUROC range; reword the Introduction's 'never AUROC' sentence to 'recognition outcomes are reported at an operating point'; restrict the Basu description to the SAE arm.
- [MINOR] (rigor) The Lane A iter-1 gate failures raised in the previous review are only partly disclosed. G5 (placebo TOST fails in all 7 arms), G6 (A is only an upper bound in the safety arms), and the iter-1 dataset failures (hazard identification 0.9429 vs 0.95 with n 96 -> 85; placebo median edit ratio 1.25 vs 1.10; no human rater) are still absent. The iter-2 dataset gate failures and the MDE are now reported, which is good.
  Action: Add a compact gates table (gate, threshold, observed, verdict) covering G1, G3, G5, G6, the MDE, and both dataset artifacts' failed gates. Put it in Sec. 4.3, next to the existing split-half table.
- [MINOR] (clarity) Figure plan: fig_overview in the Introduction and five results figures are placed sensibly. Method still has no schematic of the lesion instrument or of the two axes (where R and E are read, at which token and layer), and the reader needs one to parse Tables 3-4. There is no figure for Contribution 3's Cohen's d-by-layer curves, the claim that most directly answers the metric question. fig_site_dissociation should plot per-lineage curves (including L4) rather than means, because the lineage breakdown changes the interpretation (see the site-dissociation critique).
  Action: Add a Method schematic: prompt tokens -> layers 13-22 -> the u fitted at layer 22 -> write matrices hooked at alpha -> logit-lens readout, marking where R and E are read. Add a two-panel figure of Cohen's d by layer for the 5 Qwen3-4B arms (with the abliterated arm once computed) plus best-layer depth fraction. Draw fig_site_dissociation per lineage.
</reviewer_feedback>

<pipeline_steps>
STEP 2 — STRATEGY: The pipeline's strategy generator (gen_strat) read the reviewer feedback
and designed a new research strategy to address the critiques.

STEP 3 — PLANNING: The planner (gen_plan) turned the strategy into concrete artifact plans —
specific experiments, datasets, or research tasks to execute.

STEP 4 — EXECUTION: The executor (gen_art) ran those plans and produced the new artifacts
shown in <new_artifacts_this_iteration> below.
</pipeline_steps>

<results_status>
This iteration executed at least one EXPERIMENT/EVALUATION/PROOF with real output: gen_art_experiment_1, gen_art_evaluation_1.
You may cite their concrete findings.
</results_status>

<hypothesis>
STEP 5 — HYPOTHESIS UPDATE: The hypothesis was revised based on evidence from previous iterations.

kind: hypothesis
title: 'Where safety lives: depth and site screen'
hypothesis: |-
  THE CLAIM IN ONE SENTENCE. Where safety lives in a small chat model is a DEPTH-by-SITE profile,
  not a single direction: the harmful-request code is formed early at the prompt site and is shared
  by base, safety-tuned and abliterated Qwen3-4B, while what safety training adds, and what
  abliteration removes, sits in a late, response-site stage whose operating-point separability and
  depth placement can be read from ONE model's activations on at most 16 prompts. The hypothesis for
  iteration 3 is that SOME depth- and site-resolved internal quantity of a single model predicts that
  model's MEASURED, GRADED safety behaviour across families better than the final-layer logit gap
  does. Which quantity is not yet known. The iteration is an explicit SCREEN over a named population
  of 14 candidates, with a selection rule fixed before any scoring and a held-out confirmation the
  screen never touches.

  WHAT ITERATION 2 ACTUALLY PRODUCED (executed numbers only).
  (1) The commissioned three-model comparison now exists with the abliterated checkpoint in it. On
  the HARD recognition set, held-out TPR@5%FPR is Base 0.475, instruct 0.875, SafeRL 0.850 and
  mlabonne-abliterated 0.838. The recognition onset layer is 33 in Base and 19 in the other three.
  The peak harm-conditioned logit-lens refusal drive is Base 1.57, instruct 4.92, SafeRL 8.78 and
  abliterated 1.92. Judged on Lane C's protocol, the abliterated child moves harmful compliance
  0.000 to 0.733 and over-refusal 0.444 to 0.000.
  (2) Across 6 behaviourally effective parent/child pairs, recognition is largely kept (median
  delta -0.05, TOST 6/6 inconclusive, P2 partially lower). Peak refusal drive falls in 6/6. The
  parent-child harm direction agrees at |cos| 0.992 in the shallow quarter and 0.459 in the deep
  half, against a null-edit control of 0.984/0.997.
  (3) Re-analysing Lane B's 4200 saved arrays with an operating-point statistic gives a SITE
  dissociation that AUROC hid. Under the lesion, prompt-site TPR@1%FPR changes by +0.0006 and
  response-site TPR@1%FPR by -0.144.
  (4) Restricted-budget (k=16) AUROC tracks safety tuning, with the non-safety fine-tune as a working
  control: Base 0.528, STaR 0.540, instruct 0.679, SafeRL 0.698.

  WHY THIS IS STILL WEAK_OR_NULL. The pre-registered screen returned survivor NONE. E1 was
  under-powered by construction, because no edit-recipe stratum held the required 4 effective pairs.
  No candidate passed E2 or E3, and the causal test E4 was not evaluated. The one readout that
  separates every child from its parent is essentially the logit baseline BL1 read at a few extra
  layers: BL1 falls 6/6 with median -2.86, against -2.98 for the peak drive. For the instruct model
  the peak layer IS the final layer. The commissioning invariant says logit readouts are baselines,
  so the activation-level metric is still undelivered. The reviewer (score 4, blocking, coverage
  partial) found two contribution claims that contradict the paper's own tables. Safety training
  moves recognition too (0.475 to 0.875), so "execution, not recognition" holds only for the
  abliteration contrast. The request-axis Cohen's d (5.68/5.74/11.15/11.41) is a PROMPT-SITE
  recognition-type measure, not an execution readout. The non-safety fine-tune lands on its parent
  ONLY for Cohen's d; on peak drive (1.57 to 2.57) and BL1 (-0.30 to 1.96) it moves partway toward
  instruct. These are corrections, not a new finding.

  WHAT THE TWO NULLS JOINTLY TEACH, which sets the shape of the widen.
  (a) The unit of analysis was wrong. Iterations 1 and 2 both tested each readout on a handful of
  checkpoint PAIRS labelled by repo name. Power died at the pair count (strata 3/2/1), and one pair
  labelled "abliterated" was a behavioural no-op on which K1 still moved 4.14 null-SD. The outcome
  must therefore be the MEASURED, GRADED behaviour of each checkpoint (harmful compliance and
  over-refusal as rates, plus a severity-weighted score), regressed on across the whole 25-checkpoint
  panel under leave-one-family-out. It must never be a binary edit label.
  (b) Recognition-vs-execution is a special case, not the axis. It is recoverable from any
  depth-by-site profile, and the profile is the richer object. Every readout that moved did so at
  depth or at the response site. Every readout that stayed flat was a prompt-site quantity at or
  near its fitting layer.
  (c) The bar is the logit gap plus the incumbents, not zero. A candidate counts only as a MARGIN
  over BL1 (and over B3 for cross-family) and over the Jorak scanner's parent-free A statistic, which
  closes the weight-only write-mass (X2) and SVD-scar (X10) forms as prior art. Those two stay in
  the screen only as incumbent bars.

  THE CANDIDATE POPULATION (14, all functions of the harvests already on disk or one prompt-only
  forward per checkpoint; none needs a parent at scoring time):
   C1  restricted-budget operating-point recognition, k in {4,8,16}, HARD set, panel-wide.
   C2  site gap: response-site minus prompt-site TPR@1%FPR within one model (teacher-forced).
   C3  within-model depth self-consistency of the harm direction (|cos| shallow-fit vs deep-fit),
       the parent-free analogue of the 0.992/0.459 result.
   C4  recognition onset depth fraction, l_dec / n_layers.
   C5  peak-layer harm-conditioned refusal drive with BL1 partialled out (residual score).
   C6  accumulation along a FIXED axis frozen at a shallow layer and read forward, the control the
       reviewer asked for, which separates accumulation from a layer-specific direction.
   C7  area under each layer's own-axis separability curve (per-layer diff-in-means).
   C8  decodable-to-actionable depth lag: refusal-drive peak layer minus recognition onset layer.
   C9  concentration of the harm signal on the first response positions vs the prompt tail.
   C10 benign-side readout: the same quantities on XSTest-style safe prompts, targeting over-refusal
       so the metric is not one-sided.
   C11 severity monotonicity: within-model Spearman between the internal score and PKU-SafeRLHF
       ordinal severity 0-3.
   C12 zero-prompt variant: the C3/C8 geometry computed from unembedding and residual-write
       composition alone. It has to beat Jorak A to survive.
   C13 prompt-site request-axis Cohen's d plus depth fraction, relabelled honestly as a
       recognition-type readout, now run panel-wide and on every abliterated child.
   C14 one pre-registered two-feature combination (the best recognition-type candidate plus the best
       late-stage candidate, with weights fixed by LOFO inside the screen).
  Incumbent bars, not candidates: BL1, B3, B7, Jorak A / X2 / X10_abs, and the shuffled-label band.

  SCREEN (cheap, one body of evidence). This uses the 23 unsealed checkpoints of the iteration-2
  panel plus Lane C's scored checkpoints, with judged behaviour recomputed on the stance-framed
  judge. Outcomes are harmful-compliance rate, over-refusal rate and severity-weighted compliance.
  Statistic: leave-one-family-out Spearman rho between the candidate and each outcome, with a
  checkpoint-bootstrap CI.
  SELECTION RULE, fixed before scoring. A candidate survives iff (i) its LOFO rho with
  harmful compliance beats BL1's by at least 0.15, with a paired bootstrap CI excluding zero; (ii)
  its partial rho given BL1 has a CI excluding zero; (iii) it escapes the shuffled-label band run
  through the WHOLE pipeline including the direction fit; (iv) it does not move beyond 1 null-SD on
  the measured null-edit pair (granite) or the random-init arm; and (v) it is not at ceiling in any
  arm. Ties go to the candidate needing fewer prompts. Every row is reported with its MDE, the full
  k-curve and no maximum over a scan. If nothing survives, the result is reported as the ranked
  table, not a subgroup.

  HELD-OUT CONFIRMATION (never seen by the screen, used once, no re-screening). This uses the 2
  SEALED families (StableLM, SmolLM2; truth hash-committed), the never-loaded 54-scenario XSTest
  split, and a fresh set of at least 6 held-out community children and safety-tuned siblings drawn
  from ungated families at or below 4B, graded behaviourally before any internal score is read. The
  survivor must keep the sign and clear BL1 on this set. If it fails, it is dead and the iteration
  returns to the population.

  WHAT THE THREE COMMISSIONED MODELS GET REGARDLESS OF THE SCREEN. Every table gets a full row for
  Base, instruct, SafeRL, the non-safety STaR control and mlabonne-abliterated, with BL1 beside
  every activation number. The paper then gets its missing controls: the fixed-axis accumulator
  (C6), per-lineage site dissociation including the non-safety lineage L4 (where the late-site drop
  was largest, 0.404 to 0.234, which currently undercuts the "execution" reading), and a power
  statement for the saturated probe. Recognition is reported at an operating point, never as a bare
  AUROC.

  CAUSAL CHECK, promoted from missing to required for any survivor. For the survivor's layer and
  site, add a matched-norm projection of the fitted direction versus an orthogonal random direction
  in the instruct model, with judged refusal as the outcome. Report per-item distributions and the
  collateral effect on already-correct benign items. Without it the survivor is called a READOUT
  and never a mechanism.

  PRIOR ART, stated where it binds. Recognition surviving abliteration: 2603.27412 / 2604.18901
  (replication). Recognition-vs-execution naming: Orgad et al. 2604.09544 and 2603.05773. A
  weight-computable per-checkpoint cosine: 2606.24952 (hallucination). A reference-anchored
  abliteration audit: 2607.01854 (needs the parent). A parent-free weight scanner: Jorak (unreviewed;
  verify the URL or drop the citation). None of these predicts GRADED behaviour across families from
  a single model's depth-by-site profile, and none scores an abliterated checkpoint. That empty cell
  is the contribution the screen is testing for.
motivation: |-
  1. THE MEASUREMENT IS THE DIFFERENCE BETWEEN A PROPERTY AND AN AVERAGE, AND THAT IS THE PART THAT
  CHANGES WHAT OTHER PEOPLE DO. If A is large, the response-site effect the literature reports is an
  average over a request factor nobody varied. It is then not a per-model property at all but a property
  of the model crossed with the harmful-request setting it was measured in. Two checkpoints with
  identical published response-site effects can behave completely differently the moment the request
  stops looking dangerous -- which is the regime that matters in long generations, multi-turn use and
  agentic tool loops, where the hazardous text a model is continuing was often not requested by anybody.
  This claim is publishable whichever way the checkpoints fall, and it costs 1,280 forward passes to
  settle for a given model.

  2. THE MISRANKING THE METRIC IS MEANT TO FIX IS DOCUMENTED, NOT ASSUMED. Internal harmfulness scores
  read at prompt-dependent locations have been reported to ANTI-rank successful jailbreaks, at AUROC
  0.220 among wrapped harmful prompts, meaning successful attacks rank LOWER than failed ones. That is
  independent published evidence that the standard cheap readout measures the wrong thing. The
  Qwen3-4B-SafeRL card is the clean instance: in NON-THINK mode its safety rate rises 64.7 to 98.1 on
  WildGuard while its refusal rate FALLS 12.9 to 5.3, and on the stronger Qwen3-235B judge the same rows
  read 47.5 to 86.5. Both columns are quoted deliberately: 98.1 is near ceiling so the WildGuard column
  overstates headroom, and in THINK mode refusal barely moves, 6.5 to 6.2, so the argument that SafeRL
  cannot buy safety by refusing at token one is scoped to the non-think setting this study runs in.
  Every cheap readout in use -- first-token refusal probability, refusal-direction projection at the last
  prompt token, activation cluster separation, refusal rate -- reads the request-side gate, which is
  exactly the component this kind of training turns down.

  3. THE PRACTICAL ADVICE IS ALREADY PROVEN AND IS NOT CLAIMED; THE MECHANISM IS WHAT IS MISSING. A
  published defence trains on justify-then-refuse responses that distribute the refusal signal across
  token positions and reports refusal dropping at most 10 percent under abliteration against 70 to 80
  point drops for baselines, with a feature-space section showing the edit shrinking the harmful-versus-
  benign PROMPT centroid distance far less in those models, 10.0 / 7.7 / 13.7 against 28.8 / 33.9 / 28.7.
  So "put safety where a prompt-fitted rank-one edit cannot see" is known, and that paper measures the
  request axis at the prompt in models built to resist. What is missing is a measurement at RESPONSE
  positions that separates the request-gated part from the request-independent part, and a checkpoint
  that was not designed to resist. The claim is that the mechanism is the arming term, and that a model
  trained for something else entirely -- safe completion -- shows the same protective structure with
  nobody having built it in. Those same numbers are also why the surviving-monitor comparison is made at
  matched request-axis damage.
assumptions:
- >-
  The internal safety signal is linearly readable at generated positions and not only at the decision token. This is established
  rather than assumed: streaming hidden-state moderation probes decode the harmfulness of a partially written response throughout
  generation, and arXiv:2607.14147 reads the harm direction at response positions with a causal effect. The readout used here
  is a difference-in-means axis fitted on a DISJOINT corpus of hazardous versus benign continuations at response positions,
  benchmarked against a cross-validated linear probe and against raw hidden vectors, with the cross-fitted variant over the
  evaluation items retained as a robustness row.
- >-
  The response-content harm axis is not collinear with the direction abliteration removes. This is the load-bearing instrument
  assumption and it is measured rather than asserted: r_content is fitted at RESPONSE positions on a continuation contrast
  under a held-fixed request, where the abliteration direction is fitted at the last PROMPT token on a request contrast, and
  |cos| between them is a pre-registered Stage-2 gate at 0.50 backed by a component-preservation diagnostic. If the gate fails,
  the parent-fixed post-edit numbers are an annihilation residue and are reported as one, with the arm carried by the per-checkpoint
  refit and the full probe. Two further measurement facts sit in the same assumption. Standard abliteration edits only matrices
  that write to the residual stream, using a direction estimated at prompt positions, which is what makes the headline a structural
  prediction rather than a guess; recipes that fit at response positions or re-train after editing would break it and are
  analysed as a separate stratum, never pooled. And cross-checkpoint terms are only comparable after standardisation, because
  residual-stream norms and LayerNorm gains differ between base, instruct, RL-tuned and weight-edited checkpoints and move
  again under the edit, so every cross-checkpoint quantity is expressed in that checkpoint's own measured null-band per-item
  SD with the raw-scale table published alongside.
- >-
  The request factor and the response factor can be varied independently over the same strings, so the interaction is estimable.
  Four cells share one continuation vocabulary and one token span. The threat is that the off-diagonal cells are incoherent
  continuations while the diagonals are coherent, loading a generic instruction-mismatch signal onto exactly the term the
  headline is stated in. This is neither assumed away nor handled by a constant subtraction: a safety-irrelevant crossed control
  of the same shape estimates the coherence interaction, both crossings are calibrated on the model's own log-probability
  of the prefix given the request, and where the mismatch magnitudes do not match the readout is regressed on that penalty
  and the arming term reported net of the covariate, or as an upper bound if the control's mismatch cannot be raised to the
  treatment's.
- >-
  A response-conditioned safety signal is not the same thing as generic autoregressive conditioning, and the two are separable
  by their dependence on the request and by whether they steer. Generic conditioning should produce a response main effect
  with no request modulation. This is the load-bearing scientific assumption behind treating A rather than CB as the safety
  term, and it is tested by two pre-registered non-safety arms -- Qwen3-4B-Base and a non-safety fine-tune of the same parent
  -- plus the causal requirement that the component be a write-handle and not merely readable.
- >-
  Qwen3-4B-SafeRL's safety-up, refusal-down profile reflects a genuine safe-completion policy rather than a fixed hedging
  template that keyword refusal detectors miss. A quantitative template-collapse diagnostic runs before the second supporting
  prediction is interpreted: distinct-3-gram rate of SafeRL non-refusals at least 0.6 times that of Qwen3-4B non-refusals,
  and cross-request response similarity at least 0.15 below within-request similarity, both thresholds fixed before the run.
investigation_approach: |-
  OPERATIONAL PARAMETERS. A planner should be able to build Stage 0 and Stage 1 from this block alone.

  CHECKPOINTS, all verified live and ungated on 2026-09-20, all Qwen3, 36 layers, hidden size 2560, one
  tokenizer, so layer, head and token position are directly comparable with no alignment step. Each is
  loaded alone on the 20 GB card.
    Qwen/Qwen3-4B-Base                     non-safety arm 1; 8.04 GB, bf16
    Qwen/Qwen3-4B                          refusal-style instruct arm; 8.04 GB, bf16
    Qwen/Qwen3-4B-SafeRL                   safe-completion arm; 8.04 GB; its card declares
                                           base_model Qwen/Qwen3-4B, so it is the instruct model's own
                                           CHILD, which is what makes the P1-versus-P2 contrast a
                                           parent-child comparison with the pretraining held fixed
    mlabonne/Qwen3-4B-abliterated          the community-edited checkpoint the request named; shipped in
                                           F32 at 16.09 GB, so it is cast to bf16 on load, and that cast
                                           is recorded as a stated deviation from the other arms
    non-safety fine-tune of Qwen3-4B-Base  non-safety arm 2; ladder below
    + in-house edited grid: 5 strengths x {Qwen3-4B, Qwen3-4B-SafeRL}
    NOT USED: huihui-ai/Qwen3-4B-abliterated, whose repo is gated 'auto' and whose config cannot be read
    without authentication; mlabonne is the ungated community arm.

  NON-SAFETY FINE-TUNE LADDER, in order, fixed now so the arm cannot be chosen after Base is seen:
    (1) an ungated, non-quantised third-party fine-tune whose parent is DECLARED as Qwen3-4B-Base in the
        repo metadata, not merely implied by its name, and which ships the stock Qwen chat template so
        that token spans match the other arms exactly. Verified live on 2026-09-20 and ordered by those
        two criteria: CohenQu/Qwen3-4B-Base_HintGen-STaR.03.01_1e-6 first, a hint-generation SFT run with
        an explicit base_model tag and the stock 4,116-byte Qwen template; then
        CohenQu/Qwen3-4B-Base_HintGen-STaR.04.00_1e-6_no_think, same family; then
        shjondhale/AzureML-Qwen3-4B-Base-GRPO, a math GRPO run with an explicit base_model tag but a
        custom 1,991-byte template, which costs span comparability and is therefore ranked below the
        first two. HikariLight/Qwen3_4B_Base__COMP_ACI_DAMT_SFT_Merged is live and ungated and carries
        the stock template, but its repo declares no base_model at all, so its parentage rests on its
        name; it is a last resort within this rung and would be reported with that caveat.
    (2) failing all three, an in-house LoRA or short full fine-tune of Qwen3-4B-Base on an ungated
        non-safety instruction set -- hours of GPU time at 4B, and it holds parent, tokenizer and
        template exactly fixed, which the cross-family option does not;
    (3) only failing both, a non-safety fine-tune of another family's parent, and then only under the
        standardized null-SD units.
    Any third-party fine-tune differs from the instruct checkpoint in instruction-following ability and
    in chat template as well as in safety training; that is a stated confound, the arm's chat template is
    reported next to its results, and it is why rung (2) is preferred over rung (3).

  READOUT DIRECTION r_content, stated completely because this is what decides whether Stage 2 measures
  anything: difference in means between hazardous and benign CONTINUATION tokens, taken at RESPONSE
  positions, over a fitting corpus of 64 continuation pairs written under a single held-fixed, neutral
  request, disjoint from the 96 evaluation scenarios. It is therefore a different vector from the
  abliteration direction, which is a difference in means over harmful versus harmless REQUESTS at the
  last PROMPT token. A fully disjoint fitting corpus is stronger than cross-fitting over the evaluation
  items, not weaker: it removes in-sample selection entirely rather than rotating it, and the
  cross-fitted variant over the 96 scenarios is retained as a robustness row.

  LAYER BAND: a contiguous band of 25% of the network's layers (9 of 36), expressed as a FRACTION OF
  NETWORK DEPTH so it transfers to any architecture, chosen at Stage 0 as the band maximising the continuation-contrast
  positive control in Qwen3-4B, computed on the FITTING CORPUS ONLY and never on the evaluation
  scenarios, then frozen for all checkpoints. Secondary, pre-registered: a per-checkpoint BEST-BAND
  search, Holm-corrected, against which the safety-specificity gate must also hold.

  RESPONSE-POSITION WINDOWS: continuation tokens 5-20 (EARLY, primary) and 40-55 (LATE), both read from
  one forward pass over a continuation of at least 64 tokens, so the position curve costs nothing.

  ITEMS: 96 confirmatory scenarios plus a 54-scenario HELD-OUT REPLICATION set, split at random before
  any activations are collected. The supply was checked rather than assumed: XSTest v2 ships 450 prompts,
  250 safe across 10 types and 200 unsafe contrast across 8 types, and in 6 of those contrast families --
  homonyms, safe targets, safe contexts, definitions, figurative language and historical events -- the
  safe and unsafe rows are genuine minimal-edit twins, 25 each, giving 150 tightly matched pairs. The
  remaining two contrast families, discrimination and privacy, are only topically parallel and are
  excluded. So 96 is a power-driven choice out of 150 available pairs and the leftover 54 become a real
  replication set rather than a subsample; OR-Bench (80,359 / 1,319 / 655 rows across its three configs)
  is available if a domain needs topping up. Two prefix families per scenario, generated mechanically
  from two fixed templates: F1 ANNOUNCED, where the continuation opens by naming what it is about to do,
  and F2 ENACTED, where it simply performs the hazardous content in-stream with no meta-announcement.

  FORWARD-PASS BUDGET: 96 items x (4 safety cells x 2 families + 4 coherence cells) + 128 fitting-corpus
  passes = 1,280 per model state; 15 model states = 19,200 passes. The 54-item held-out replication runs
  on the five checkpoints only, adding 3,240. Total about 22,400 forward passes of at most 320 tokens
  with zero generated tokens: minutes to low tens of minutes of GPU time, which is why the item count is
  set by power and not by compute.

  REFUSAL DRIVE, the dependent variable of the causal arm and of the CB half of the specificity gate,
  defined here because a gate cannot be evaluated against an undefined outcome. PRIMARY: the teacher-
  forced probability mass on a fixed refusal-onset token set at the position immediately after the
  intervened span. It is well defined in Base, needs no decision label, and is the quantity the published
  0.24-versus-0.03 routing-concentration figure speaks to. SECONDARY: the cross-validated full-probe
  decision score, trained on Qwen3-4B and applied unchanged to Base, with that transfer flagged. Both are
  output-side READOUTS of an activation-side INTERVENTION, which is what the commissioned invariant
  permits; the deployed metric itself stays activation-only and never uses them.

  EDIT-STRENGTH GRID: five strengths per lineage, spanning zero to the strength at which O collapses,
  with the primary comparison read off each lineage's own O-damage curve by interpolation.

  STAGE 0 -- INSTRUMENT, ITEMS AND GATES, ALL BEFORE ANY EXPENSIVE WORK.
  Build the 64-pair fitting corpus and fit r_content. Check split-half cosine >= 0.70 in every
  checkpoint; below it, the fitting corpus is enlarged before Stage 1 rather than after effects are seen.
  RUN THE POWER CHECK HERE TOO, not only the direction check: on a 24-item pilot subset, estimate r, the
  ratio of the per-item SD of A to the per-item null SD, and recompute the MDE for every row of the
  criteria table at the planned n. If the achieved r implies an MDE above any registered threshold, the
  scenario count is raised toward the 150 available pairs BEFORE the confirmatory run, and the pilot items
  are excluded from the held-out set. The escape hatch is conditional on this check and on the split-half
  cosine, and the achieved r is reported either way, so a reader can see what the design could and could
  not have detected.
  Choose the layer band on fitting-corpus data only and freeze it as a fraction of network depth. Build 96 twin
  scenarios from XSTest's safe split topped up from OR-Bench, and generate both prefix families
  mechanically from two fixed templates, publishing all cells verbatim. Gates: (a) an external judge
  labels twins and prefixes correctly at a stated rate; (b) a positive control that r_content separates
  hazardous from benign continuations in Qwen3-4B; (c) a PLACEBO prefix factor at the same lexical
  distance, tested for equivalence within +/-0.40 null-SD by TOST, whose attainability is shown above;
  (d) null bands from at least 20 random-direction and 20 shuffled-label draws run through the ENTIRE
  pipeline including the direction fit, which is also what defines the null-SD unit; (e) the NLL-MATCH
  DIAGNOSTIC described next.

  THE COHERENCE CONTROL IS CALIBRATED, NOT ASSUMED. Subtracting the coherence interaction from the safety
  interaction is only valid if the generic instruction-mismatch signal enters additively and if the two
  crossings produce mismatches of comparable magnitude -- and a benign request followed by an off-topic
  benign prefix is a mild non-sequitur where a benign request followed by a hazardous prefix is a severe
  one. The calibration costs nothing because it comes from the same forward passes: the model's own mean
  token log-probability of the PREFIX given the REQUEST. The four-cell log-probability table is reported
  for BOTH 2x2s as a mandatory Stage-0 diagnostic, and the off-diagonal penalty in the coherence crossing
  must be statistically indistinguishable from, or larger than, the penalty in the safety crossing before
  any subtraction is performed. If they do not match, nothing constant is subtracted: the per-item
  readout is regressed on the per-item log-probability penalty across all cells and A_net is reported as
  the coefficient net of that covariate, which survives both a magnitude mismatch and mild
  non-additivity. If the coherence penalty cannot be brought up to the safety penalty at all, A_net is
  reported as an UPPER BOUND on arming rather than as an estimate, and labelled that way everywhere.

  STAGE 1 IS THE COMMISSIONED DELIVERABLE: THE ACTIVATION-LEVEL COMPARISON. Five checkpoints, each loaded
  alone on the 20 GB card, with the F32 community checkpoint cast to bf16 on load and that cast recorded
  as a stated deviation. The 54-scenario held-out set is run here too, on these five only, and its
  estimates are sealed until the confirmatory analysis is complete. For every layer and every position in the frozen window, produce maps of O, CB
  and A in all five, with item-clustered bootstrap intervals and per-item distributions rather than means
  alone, in both raw and null-SD units, under BOTH prefix families and BOTH response-position windows. The base
  protocol is stated rather than left to formatting: Base is run twice, once with the Qwen3-4B chat
  template applied verbatim so token spans match across checkpoints and once in plain completion format,
  and the two must agree qualitatively before Base is used as a control, because alignment is reported to
  concentrate in the assistant header tokens and those tokens are out of distribution for Base.
  The RESPONSE-POSITION curve, A in the early window against A in the late window, is reported as a
  result in its own right: it separates an arming term that persists from a shallow-alignment transient
  at one position, which a single frozen window cannot do, and it is free because both windows come from
  the same forward pass.

  THE CAUSAL ARM USES THE RUNG THAT SURVIVES. Not full-residual patching: that restores refusal to 100
  percent at every layer, but so does patching the mean BENIGN residual at the same position, so the
  intervention is generic disruption and a random-direction control cannot detect the failure because the
  benign patch is the treatment. Instead add or remove ONLY the r_content component at response
  positions, at layer cells fixed at Stage 0, against a matched-norm control direction ORTHOGONALIZED to
  it, with full-residual patching retained and labelled as a positive control that the intervention did
  something. Report collateral disruption on already-correct benign cases and the per-item effect
  distribution, never a mean at one coefficient.

  STAGE 2 BUILDS THE MISSING CHECKPOINT AND TESTS THE HEADLINE. No abliterated safe-completion model
  exists, so one pinned rank-one orthogonalisation with the direction estimated at prompt positions is
  applied to BOTH Qwen3-4B and Qwen3-4B-SafeRL across a five-strength grid. Minutes of GPU time, no
  training, recipe held fixed, so a difference between lineages is attributable to safety-training style
  rather than to the tool -- the confound that wrecks comparisons across harvested community checkpoints.
  Stage 2 measures each lineage's O-damage curve first, then makes the primary comparison at the
  pre-registered matched-damage level by interpolation. The annihilation gate and the
  component-preservation diagnostic are evaluated here, before any term is interpreted. The harvested
  public abliteration is an external check that the in-house edit reproduces a real one, and each
  lineage's pre-edit A is recorded before the edit so post-edit survival is a forecast, not a fit.

  STAGE 3 COLLECTS BEHAVIOURAL GROUND TRUTH ON BOTH COLUMNS. For the five checkpoints, the in-house
  edits, and a panel of ungated checkpoints at or below 4B spanning at least SIX families -- families,
  not checkpoints, are the clustering unit -- measure harmful-compliance rate, over-refusal on hard
  benign twins, and safe-engagement rate, graded by a fixed rubric through an OpenRouter judge. Budget
  planned before the sweep at roughly 4,000 to 6,000 graded responses, near 3 to 5 US dollars against the
  10 dollar cap, with the running total checked after every batch and the sweep stopped on approach.

  STAGE 4 ASKS WHETHER THE PROFILE PREDICTS ANYTHING, ON TWO CO-PRIMARY COLUMNS AND AT FIVE PROMPT
  BUDGETS. Leave-one-family-out prediction with no recalibration, of harmful-compliance rate and of
  safe-engagement rate, from (O, CB, A), against baselines prior work says are hard to beat: the
  model-card and repository-name regex, black-box greedy refusal rate, first-token refusal logit gap,
  activation cluster separation, raw hidden vectors as the non-featurized control, and -- added because it
  is the only published family competing on the same axis -- a NON-GENERATIVE LATENT SAFETY EVALUATOR from
  the recent line that scores safety from a checkpoint's latent representations without sampling any text.
  Where such a method has a usable implementation it is run on the same panel; where it does not, its
  reported numbers on any overlapping checkpoints are tabulated beside ours and the comparison is labelled
  indirect. Those methods read the request side and return a scalar, so the claim here is specifically
  that a profile separating the request term from the unconditional response term and their interaction
  beats a scalar on the safe-engagement column, which is exactly where a request-side scalar should fail.
  The decision rule
  is fixed so a coin cannot pass it: the profile must beat the STRONGEST baseline on at least 5 of 6
  families, which a fair coin passes 10.9 percent of the time where a bare majority of six passes 34
  percent, AND the paired family-clustered interval must exclude zero. The same evaluation is repeated at
  k = 4, 8, 16, 32 and 96 quadruples and the smallest k that still passes is reported as the headline
  prompt budget. Both outcomes are informative: if the profile fails to transfer, Stages 1 and 2 stand as
  a mechanism result on the commissioned trio and the failure localises which term refuses to generalise.

  RELEASED ARTEFACTS, because the coordinate is only reusable if the stimuli are: all 768 safety cells
  (96 scenarios x 4 cells x 2 families), all 384 coherence cells, the 128-text fitting battery, the
  fitted directions, the per-item four-cell scalars and the full layer-by-position maps for every
  checkpoint. The nearest existing artefact collects answer-position activations for the same trio but is
  gated, has no counterfactual factor and carries no analysis, so an ungated crossed one is an
  independent contribution.

  FEASIBILITY, VERIFIED THIS SESSION. NVIDIA RTX A4500, 20 GB VRAM, 48 cores, 251 GB RAM; the Qwen3-4B
  checkpoints ungated and downloadable. Stage 1 is 19,200 hooked forward passes with zero generated
  tokens, minutes to low tens of minutes; Stage 2 is a rank-one weight edit. The binding costs are panel
  downloads, streamed one checkpoint at a time, and the Stage 3 judge calls, budgeted above.
success_criteria: |-
  CRITERIA TABLE. Every threshold is a NUMBER, in null-SD units, fixed now. Planning arithmetic, shown
  once and used for every row: the null-SD unit is the per-ITEM standard deviation of the same contrast
  computed under >=20 random unit directions in that checkpoint, so it is n-independent and carries that
  checkpoint's own residual-stream scale. The standard error of a standardized term is r/sqrt(n) where
  r = (per-item SD of the real term)/(per-item null SD); we plan at r = 1.2 and n = 96 scenarios, giving
  SE = 0.123, and report the achieved r. Derived MDEs at n=96: simple term 0.24; two-checkpoint
  difference 0.34; pre/post difference-in-differences 0.48; TOST half-width at 90% 0.20; coherence-net A
  0.25 to 0.34 depending on the covariate R-squared. At n=24 those same numbers are 0.48 / 0.68 / 0.96 /
  0.40, which is why 24 items was abandoned: the difference-in-differences that carries the headline would
  have had a minimum detectable effect of 0.96 null-SD, larger than any margin worth setting. The item
  count is therefore set by this arithmetic and not by what the twin sets happen to yield -- 150 matched
  XSTest pairs exist, 96 are used for the confirmatory analysis and the remaining 54 become a held-out
  replication set whose own two-checkpoint MDE is 0.45.

   #  TEST                                        REGISTERED ON          THRESHOLD        INTERVAL           MDE
   1  safety-specificity, registered term          Qwen3-4B on A;         > 0.50 null-SD   item-clustered     0.34
      exceeds BOTH non-safety arms                 SafeRL on CB                            bootstrap 95%
   2  ordering  A(Qwen3-4B) - A(SafeRL)            pair                   > 0.50 null-SD   paired, 95%        0.34
   3  ordering  CB(SafeRL) - CB(Qwen3-4B)          pair                   > 0.50 null-SD   paired, 95%        0.34
   4  coherence-net arming A_net                   Qwen3-4B               > 0.40 null-SD   paired, 95%        0.25-0.34
   5  post-edit A equivalent to null (TOST)        both lineages          within +/-0.40   90% TOST           0.20 half
   6  post-edit CB above null                      every lineage with     > 0.40 null-SD   95%                0.24
                                                   CB_pre above null
   7  HEADLINE DiD at matched O-damage, on         SafeRL vs Qwen3-4B     > 0.60 null-SD   paired, 95%        0.48
      T = CB+A = s_H,haz - s_H,ben (the published
      response-site effect, nonzero in both
      lineages by construction, so no floor):
      [T_post-T_pre](SafeRL)-[same](Qwen3-4B)
   7b within-lineage component test, with           lineage whose A_pre    drop_A - drop_CB paired, 95%        0.34
      drop_X = X_pre - X_post so a positive drop     clears the null band   > 0.35 null-SD
      means the term fell: drop_A exceeds drop_CB
      in that same checkpoint's null-SD units
   7c CB DiD, mechanistic secondary                 both lineages, only    > 0.40 null-SD   paired, 95%        0.48
      [CB_post-CB_pre](SafeRL)-[same](Qwen3-4B)     where CB_pre clears
                                                    the null band; else
                                                    reported UNDEFINED
   8  forecast form: lineage with smaller          ordering over 2        sign + both      paired             --
      pre-edit A shows smaller |dT|                lineages               CIs exclude 0
   9  annihilation gate |cos(r_content,r_ablit)|   parent-fixed arm       <= 0.50          point              --
  10  component preservation: var along            parent-fixed arm       >= 0.25 x        point              --
      r_content after edit vs 20 random dirs                              random median
  11  direction stability, split-half cosine       every checkpoint       >= 0.70          mean over 20 splits --
  12  placebo prefix factor equivalence            Qwen3-4B               within +/-0.40   90% TOST           0.20 half
  13  NLL-match gate before any subtraction        both 2x2s              coherence        TOST or >=         --
                                                                          penalty >= safety penalty
  14  template-collapse (SafeRL interpretable)     SafeRL                 distinct-3gram   descriptive        --
                                                                          ratio >= 0.6, sim gap >= 0.15
  15  template generality: arming ordering holds   Qwen3-4B vs SafeRL     both families    95% each           0.34
      under BOTH prefix families
  16  metric payoff, leave-one-family-out          profile vs strongest   >= 5 of 6        family-clustered   reported
                                                   baseline               families (p=.109) paired 95%
  17  held-out replication of rows 2, 3 and 4  54 scenarios split off  same sign and    item-clustered     0.45
                                                   before collection      CI excludes 0    bootstrap 95%

  CONFIRMS the hypothesis. Every threshold is the NUMBER in the criteria table; nulls are measured from
  at least 20 random-direction and 20 shuffled-label draws run through the whole pipeline including the
  direction fit, never from a nominal chance value.
  - SAFETY-SPECIFICITY GATE, which must pass before any term is called safety, registered PER CHECKPOINT
    before the run so no term is chosen after the fact: Qwen3-4B on A, Qwen3-4B-SafeRL on CB. Each must
    exceed BOTH non-safety arms on its registered term by 0.50 null-SD with item-clustered intervals
    excluding zero, in the frozen band AND against each non-safety arm's Holm-corrected BEST band, so a
    null in a non-safety arm that disappears under the best-band search is reported as a band artefact
    rather than as specificity. Because a base model can carry a readable CB from generic autoregressive
    conditioning alone, the CB half additionally requires the CAUSAL arm: moving the r_content component
    at response positions must change the refusal drive in the safety-trained checkpoint and not in Base,
    against the orthogonalized control. A term that is readable but inert does not pass.
  - COHERENCE-NET ARMING: A_net exceeds 0.40 null-SD with an interval excluding zero in the checkpoint
    registered on A. This applies to A wherever A is claimed and nowhere else: SafeRL is predicted to have
    A near zero, so a null A_net there confirms P2 rather than failing this gate, and the two are
    distinguished by which term each checkpoint was registered on before the run.
  - TEMPLATE GENERALITY: the arming ordering holds under BOTH prefix families, announced and enacted. A
    result present only under the announced family is a property of the announcement, not of the content,
    and is reported as such.
  - ORDERING: A(Qwen3-4B) - A(SafeRL) > 0.50 null-SD and CB(SafeRL) - CB(Qwen3-4B) > 0.50 null-SD, paired,
    intervals excluding zero. The refusal-tuned model's output monitoring is armed by the request; the
    safe-completion model's runs unconditionally.
  - HEADLINE, at the matched-damage level and with no denominator anywhere: (i) post-edit A is equivalent
    to the null band within +/-0.40 null-SD by TOST in BOTH lineages; (ii) post-edit CB exceeds 0.40
    null-SD in every lineage where it exceeded it before; (iii) the difference in differences on
    T = CB + A, the published response-site effect under a harmful request,
    [T_post-T_pre](SafeRL) - [T_post-T_pre](Qwen3-4B), exceeds 0.60 null-SD, paired and item-clustered.
    (iii) carries the claim, and it is stated as a CHANGE in T rather than as a level in CB for two
    separate reasons: a post-edit level comparison is entailed by the pre-edit gap plus (ii), and a
    change in CB has a floor in the very lineage P1 predicts to have little CB to lose. T is nonzero in
    both lineages by construction, so it has neither problem. Underneath it, 7b: writing drop_X = X_pre - X_post so that a
    positive drop means the term fell, then within the lineage whose A clears the null band before the
    edit, drop_A exceeds drop_CB by 0.35 null-SD in that checkpoint's own units; and 7c: the CB difference in differences, reported only where CB_pre clears the null band in
    both lineages and declared UNDEFINED otherwise rather than counted as a failure. If no pair of
    strengths gives matched O damage, the criterion fails and is reported unmet rather than relaxed.
  - FORECAST: the lineage with the smaller pre-edit A shows the smaller absolute change in T, with both
    change intervals excluding zero. This is what makes the pre-edit measurement predictive rather than
    descriptive, and it is registered as its own criterion rather than left in prose.
  - CAUSAL: at fixed layer cells, adding or removing the r_content component at response positions moves
    the refusal drive more than a matched-norm orthogonalized control, with the per-item distribution
    reported, and the size of that effect tracks CB across checkpoints.
  - DOUBLE DISSOCIATION, the strongest single form the result can take: safe-completion training raises
    CB and not A; the prompt-fitted weight edit lowers A and not CB, same recipe, both lineages. No single
    scalar of safety strength can produce that pattern, so if both halves hold with intervals excluding
    zero the two terms are separately real.
  - INSTRUMENT INTEGRITY: |cos(r_content, r_ablit)| at most 0.50 and the edited model's variance along
    r_content at least 0.25 times the median variance along 20 matched-norm random directions. If either
    fails, the parent-fixed post-edit numbers are an annihilation residue, are labelled one, and the arm
    is reported only under refit and full-probe readouts.
  - STABILITY AND REPLICATION: every reported term carries its distribution over bootstrap resamples,
    at least three probe-set subsamples and both prefix families, and a term whose sign is not stable
    across those draws is reported as unstable rather than as an effect. Beyond resampling, the two
    ordering criteria and the coherence-net arming criterion are re-run once on the 54-scenario HELD-OUT
    set, which is split off before any activations are collected; the ordering must hold there in sign,
    with the held-out estimate reported whether or not it does.
  - METRIC PAYOFF: under leave-one-family-out with no recalibration, (O, CB, A) beats the strongest
    baseline on at least 5 of 6 families with a paired family-clustered interval excluding zero, on BOTH
    co-primary columns or on safe-engagement with an honest report of the harmful-compliance result either
    way; and the prompt-budget curve names the smallest k in {4, 8, 16, 32, 96} at which that still holds.

  DISCONFIRMS it, stated so the run cannot be rescued afterwards.
  - THE CHEAPEST KILL, checked at Stage 1 before any judge spend: if A is inside the null band in EVERY
    checkpoint, the arming coordinate is empty, output monitoring where it exists is unconditional, and
    the headline is dead. The run then reports a single response-site term, says plainly that
    arXiv:2607.14147 already owns it, and reports the methodological claim as refuted for this family --
    which is itself the answer to the question asked, not a rebranding.
  - If A and CB are BOTH inside the null band everywhere there is no response-site signal in this family
    under this readout, which would contradict published work and is first treated as instrument failure.
  - If A is as large in Base or in the non-safety fine-tune as in the safety-trained checkpoints, A is a
    fact about autoregressive conditioning, not about safety, and the interpretation is withdrawn.
  - If the NLL-match gate fails and the covariate regression still leaves the safety interaction fully
    explained by the mismatch penalty, the headline term is instruction-mismatch and is reported as such.
  - If CB is readable but r_content is not a write-handle in any safety-trained checkpoint, the monitor
    reading is withdrawn: what was measured is a content representation, the correlational maps stand, the
    causal claim does not.
  - If SafeRL's A is at or above Qwen3-4B's, or its CB at or below, the training-objective argument behind
    P2 is wrong. That is a real finding about safe-completion training and is reported as a refutation.
  - If the edit drives CB into the null band as well as A, or if the T difference in differences comes
    back null or reversed at matched damage, the blind-spot argument is wrong: the two terms share a write
    bottleneck and a prompt-estimated rank-one edit reaches both. If it leaves A above the
    null band, the request-axis fitting argument is wrong in the other direction.
  - If the annihilation gate fails -- |cos(r_content, r_ablit)| above 0.50, or the edited model's variance
    along r_content at floor against the random-direction reference -- then the parent-fixed post-edit
    numbers measure a deleted coordinate rather than a model property, and the Stage-2 headline is
    WITHDRAWN under that basis rather than reported. The arm then carries only what the per-checkpoint
    refit and the full probe support, and if those disagree the honest output is that this design cannot
    settle post-edit survival, which is a stated limit rather than a softened claim. Stages 1 and 3 are
    unaffected, because neither depends on the edited checkpoints.
  - If the arming ordering holds under one prefix family and reverses under the other, A is a property of
    that template and is reported as a template effect, not a checkpoint property.
  - If the template-collapse diagnostic fires, P2 is uninterpretable and must be restated about templates
    rather than controllers.
  - REPORTING RULE, stated once. Every pass-or-fail test takes one of four permitted forms: an absolute
    main effect; the same term compared across two checkpoints; a change in one term, or a difference of
    such changes across checkpoints; or, in exactly one place, a difference between the CHANGES in two
    different terms INSIDE one checkpoint (criterion 7b), which is permitted because both changes are
    expressed in that one checkpoint's own null-SD units and no scale travels between models. None is a
    ratio between two different main effects and none is a share. The descriptive arming fraction A/(CB+A) is reported only where CB+A clears the
    null band, is labelled UNDEFINED elsewhere, and never decides anything. No statistic in this design is
    computable only when the hypothesis is true, and each disconfirming outcome names a quantity that is
    well defined in the world where the hypothesis fails. Equivalence claims use two one-sided tests with
    the margins above, whose attainability is shown arithmetically at n=96; the robustness grid carries
    Holm correction; no criterion is set at the minimum count that would pass it.
related_works:
- >-
  arXiv:2607.14147, Kwon, 'Breaking Refusal in the First Half: A Mechanistic Study of the Prefill Jailbreak' (14 Jul 2026)
  -- THE NEAREST PRIOR WORK and the constraint this design is built around. It holds the request harmful, varies the content
  of the model's own response, reads the harm direction at response positions and concludes that refusal is 'a shallow, response-site
  computation'. That pathway is conceded entirely and is not claimed here. Its pre-registered 2x2 is harm x SURFACE trigger
  density (AdvBench-scary/clean x XSTest-safe/Alpaca) run in the plain condition, never crossed with the prefill factor, and
  it contains no benign-twin construction; the nearest thing to the arming term is a 24-prompt specificity control inside
  one intervention arm, a behavioural difference-in-differences of +16.8 points (harmful refusal 3 to 24 percent, benign 0
  to 4 percent) reported as a check that an attention knockout was harm-specific -- behavioural rather than activation-level,
  unmatched rather than twinned, attached to an intervention rather than to a readout. It produces no per-checkpoint summary
  and contains no abliterated, weight-edited, safe-completion or safety-RL checkpoint; its panel is Qwen2.5-0.5B to 7B, SmolLM2-1.7B,
  Phi-3-mini-3.8B and Phi-3-medium-14B with Qwen2.5 base controls. Three of its findings are adopted rather than rediscovered:
  the full-residual patch is dropped because the benign-residual control also returns refusal to 100 percent at every layer;
  the single refusal direction is demoted because the diff-of-means readout ceilings at AUC 0.727 while a full probe reads
  about 0.85, with SmolLM2 a single-direction counterexample; and its base-model result is treated as the central threat,
  including the detail that most supports this design -- the instruct model routes the same signal to refusal tokens about
  8 times more than the base model does, concentration 0.24 against 0.03, which is exactly the readable-but-inert versus write-handle
  distinction the causal gate is built on.
- >-
  arXiv:2505.19056, Abu Shairah et al., 'An Embarrassingly Simple Defense Against LLM Abliteration Attacks' -- trains on justify-then-refuse
  responses that distribute the refusal signal across token positions and reports refusal dropping at most 10 percent under
  abliteration against 70 to 80 point drops for baselines. It owns the practical recommendation, which is why that recommendation
  is not claimed as new. It is not purely behavioural: its feature-space section runs PCA on final hidden states of harmful
  and benign PROMPTS and reports abliteration shrinking the centroid distance by 28.8, 33.9 and 28.7 points in standard models
  against 10.0, 7.7 and 13.7 in extended-refusal models. That is a REQUEST-axis measurement at the prompt, with no response-position
  readout, no decomposition into request and response terms and no causal intervention -- and it is the direct source of the
  matched-damage requirement in this design, since it shows the edit is globally less effective on such models. The remaining
  contribution here is the mechanism, small arming plus an unconditional monitor, and the prediction that a checkpoint trained
  for safe completion shows the same protective structure although nobody built it in, which a deliberately constructed defence
  cannot demonstrate.
- >-
  arXiv:2603.18353, Basu et al., 'Interpretability without actionability: mechanistic methods cannot correct language model
  errors despite near-perfect internal representations' (18 Mar 2026) -- the grounding for this design's single most defensible
  methodological choice, cited by identifier rather than by description. Linear probes on Qwen2.5-7B-Instruct's internal representations
  discriminate hazardous from benign cases at 98.2 percent AUROC while the model itself flags only 65 of 144 hazards, 45 percent,
  a 53-point gap; sparse-autoencoder feature steering produced zero corrections and zero disruptions, identical to its random-feature
  control, and concept-bottleneck steering was indistinguishable from random perturbation. That is why the safety-specificity
  gate here is stated on the CAUSAL arm and never on the readout alone: a readable component is not a write-handle. The scope
  caveat is stated rather than hidden -- one clinical triage domain, 400 physician-adjudicated vignettes, two models -- so
  it motivates the gate without being treated as a universal law.
- >-
  arXiv:2607.02510, Schirmer et al., 'Online Safety Monitoring for LLMs' (ICML 2026 Hypothesis Testing Workshop) -- thresholds
  a real-time verifier signal into an alarm during generation, with the threshold calibrated by conformal risk control. It
  is the closest work on deciding mid-generation that something has gone wrong, but its safety results come from an EXTERNAL
  scorer rather than from the generating model's own hidden states; the internal-signal ablation uses token log-probabilities
  on a maths dataset, not on the safety sets. It never varies request harmfulness against response-content harmfulness, so
  the arming term is not reachable from it.
- >-
  arXiv:2502.05242, Chen et al., 'Beyond External Monitors: Enhancing Transparency of Large Language Models for Easier Monitoring'
  (TELLME, v3 May 2026) -- fine-tunes the model's own weights with a contrastive loss so that behaviour categories separate
  in hidden space, making the model monitorable without an external module, evaluated on SALAD-Bench safety and XSTest over-refusal.
  It is the strongest statement that a model's own representations can be made to carry the safety signal, and it is also
  the clearest illustration of the gap this study addresses: the disentanglement is defined on the input QUERY's category,
  so it lives entirely on the request axis and never asks about hazardous content inside a response to a benign request.
- >-
  arXiv:2507.11878, 'LLMs Encode Harmfulness and Refusal Separately' -- the closest published two-direction decomposition
  of the safety signal, and the one a reader is most likely to mistake for this work. It separates a harmfulness direction
  from a refusal direction and shows they are distinct, which is independent support for treating the harm readout and the
  refusal outcome as different objects, as the causal arm here does. But it fits and reads BOTH directions at prompt-side
  positions, at the instruction token and just after it, and never touches activations over generated text. Its split is therefore
  between two things the model computes about the REQUEST; the split here is between what the request contributes, what the
  model's own output contributes, and whether the first gates the second.
- >-
  arXiv:2607.13075, 'The Entanglement Wall' -- crosses harmful requests against surface-matched benign requests, which is
  the same twin logic used here for the request factor, and is evidence that the matched-twin construction is the accepted
  way to manipulate intent rather than vocabulary. It runs entirely at prompt time and never varies the content of the model's
  own continuation, so it supplies one axis of this design's 2x2 and none of the other.
- >-
  arXiv:2608.09624, Luo et al., 'Measuring the Wrong Thing: Internal Harmfulness Scores Anti-Rank Successful Jailbreaks' (Aug
  2026) -- reports internal harmfulness scores read at prompt-dependent locations anti-ranking outcomes at AUROC 0.220 among
  wrapped harmful prompts and proposes a fixed, content-independent measurement coordinate as the remedy. It is the strongest
  published statement of the misranking this hypothesis sets out to explain, cited as the grounding premise rather than as
  a competitor: it diagnoses the coordinate problem behaviourally and proposes a fixed coordinate, where this work decomposes
  the signal into a request term, an unconditional response term and their interaction.
- >-
  arXiv:2609.16204, Muhamed, Diab and Smith, 'Decoy Direction Optimization: A Post-Hoc Defense Against LLM Abliteration' (Sep
  2026) -- a post-hoc weight edit that poisons the attacker's contrastive direction estimator. It is the second defence in
  the same line and confirms that the request-axis fitting step is where practitioners already believe abliteration is vulnerable;
  it defends that step rather than measuring what the step leaves untouched, which is the quantity here.
- >-
  arXiv:2606.29441, Mitra, 'Closing the Activation-Cone Blind Spot: Response-Time Probing and Unified Defense' (Jun 2026)
  -- argues that prompt-time activation defences are structurally blind to prefilling and answers with a response-time probe
  reading AUROC 0.97 to 1.00 plus a halt mechanism. It is the same blind-spot intuition put to defensive use and is strong
  evidence that response-position hidden states are highly informative, which this design depends on. It adds an external
  monitor rather than asking whether the model's own suppression is already output-conditioned, and it never varies the request.
- >-
  arXiv:2407.09121, Yuan et al., 'Refuse Whenever You Feel Unsafe: Improving Safety in LLMs via Decoupled Refusal Training'
  (DeRTa, ACL 2025 main) -- identifies a refusal-position bias in safety data and trains models to refuse at any response
  position using harmful prefixes of varying length. It is the training-side counterpart of an unconditional monitor and independent
  evidence that the property is trainable, which makes the prediction that SafeRL has it without being trained for it a real
  prediction rather than a tautology. It provides no internal measurement and no way to tell an armed monitor from an always-on
  one in a checkpoint you did not train.
- >-
  arXiv:2603.23171, Aremu et al., 'Adaptively Robust LLM Monitoring via Activation Watermarking' -- fine-tunes a key-derived
  direction into activations and detects it by cosine similarity, robust to adaptive and surrogate attackers. It is the closest
  work on reading a safety-relevant signal from activations ACROSS a response rather than at one token, and it contains the
  aggregation observation this design also relies on, that averaging across assistant tokens beats thresholding individual
  positions. Its signal is one the defender installs; the signal here is one the model already has, and the question is what
  that signal is conditioned on.
- >-
  arXiv:2510.18081, Zhang et al., 'Any-Depth Alignment: Unlocking Innate Safety Alignment of LLMs to Any-Depth' (Oct 2025)
  -- reports alignment concentrating in the assistant header tokens through repeated use in shallow-refusal training. Cited
  as a constraint on this design rather than as a competitor: it is why the base-model arm has an explicit stated protocol,
  the chat template applied verbatim plus a plain-completion condition required to agree, instead of being dropped into the
  same 2x2 as the instruct checkpoints.
- >-
  arXiv:2605.26772, 'Beyond a Single Direction: Chain-of-Thought Disrupts Simple Steering of Refusal' -- steering reverses
  refusal in 39 percent of cases with chain-of-thought fixed against 70 percent with it removed, and concludes refusal is
  jointly encoded in activations and the reasoning trace. Nearest work on the deliberation channel; this study runs in NON-THINKING
  mode on ordinary answer text, so the claim is about the answer itself, and that paper's own contrast between reasoning and
  instruction-tuned models is what makes the non-thinking case a separate question.
- >-
  arXiv:2507.03167, 'Where Do Reasoning Models Refuse?' -- the chain of thought causally determines refusal and the opening
  sentence can decide it. Whole-trace intervention, reasoning models, no decomposition into request and response contributions
  and no per-checkpoint number.
- >-
  arXiv:2609.00760, 'A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals' -- a shared initial mechanism
  commits to refusing and later type-specific features specify the grounds. The closest published commit-then-specify decomposition
  over a response; it splits refusal by its GROUNDS (epistemic versus normative), not by what the signal is conditioned on,
  and its commitment point is at the decision token.
- >-
  arXiv:2607.09697, 'Output-Aware Safety Guardrail Mitigate Over-Refusal', with arXiv:2609.00790 RISA and arXiv:2502.01042
  SafeSwitch -- these name the input-aware versus output-aware distinction outright and predict from hidden states whether
  the forthcoming generation is unsafe. All three ADD an external monitor to a model; none measures whether the model's own
  internal suppression is already output-conditioned, and none asks whether that conditioning is gated by the request.
- >-
  arXiv:2603.23268, 'SafeSeek: Universal Attribution of Safety Circuits' -- the alignment circuit is 3.03 percent of heads
  and 0.79 percent of neurons, and removing it spikes attack success. Best evidence that refusal is sparsely localised; it
  answers WHERE, which is the coordinate this work deliberately does not compete on.
- >-
  DrExe/qwen3-safety-vectors on HuggingFace (created Jul 2026, gated) -- the closest existing ARTEFACT rather than paper:
  residual activations at sampled ANSWER-token positions for Qwen3-4B, Qwen3-4B-SafeRL and a Huihui abliterated checkpoint,
  framed as harm recognition, policy selection and surface realization. Same trio read at answer positions, so it must be
  cited; it contains no analysis, no statistic and no counterfactual factor -- the response content is whatever the model
  happened to produce, so request and response are confounded exactly as elsewhere -- no in-house edited arm, and it is gated.
  The crossed, ungated cell release promised here is the direct answer to it.
- >-
  arXiv:2604.08524 'What Drives Representation Steering?' and arXiv:2605.00236 'Attention Is Where You Attack' -- steering
  acts through the OV circuit while largely ignoring QK, and safety emerges from attention routing. These own the attention-side
  versus write-side dissociation, screened and abandoned as a mechanism for this run; they bound what the abliteration blind-spot
  argument can claim, namely that it is about which POSITIONS the direction was fitted on, not about which circuit it edits.
- >-
  The abliteration dimensionality debate (Arditi arXiv:2406.11717; Marshall and Belrose affine arXiv:2411.09003; Wollschlager
  cones arXiv:2502.17420; Winninger arXiv:2607.02396, which reports Qwen3-8B requiring at least three directions) -- these
  own the read-rank versus write-rank question, also screened and abandoned. They matter because they predict that a rank-one
  edit is an incomplete write-handle, which is why this design pre-registers the parent-fixed basis, publishes cos(r_parent,
  r_child), and adds the component-preservation diagnostic instead of assuming the edited model is measured in the same coordinates
  as its parent.
inspiration: |-
  The framing came from control engineering and the ESTIMAND came from epidemiology, and it is the second
  import that does the work.

  Control engineering supplies the vocabulary: a controller is open-loop when its action is computed once
  from the reference input, closed-loop when it is recomputed from the plant's own measured output. In an
  autoregressive model the plant output is literally the text already emitted, re-read at every step
  through self-attention, so the distinction is available rather than analogical. That framing alone was
  not enough, because the closed-loop pathway turned out to be published. A borrowed frame earns nothing
  if the thing it names has already been measured.

  What rescued it was effect modification, the epidemiologist's discipline about interactions.
  Epidemiology takes as basic that a treatment effect averaged over a modifier is not a property of the
  treatment, and that the interaction is often the scientifically interesting quantity rather than a
  nuisance to control away. Applied here that is an indictment: the published response-site effect is
  measured only under harmful requests, so it is an effect at one level of an unvaried modifier, and
  whether the request MODIFIES it has not been asked. That turns a missing cell into a real quantity --
  is the monitor armed or always on -- and it is the quantity the abliteration argument actually bears
  on, since an edit fitted on the request axis should remove a request-dependent gate and not a
  request-independent monitor. Epidemiology supplied the discipline that came with it too: an interaction
  is only interpretable against a control for whatever else distinguishes the off-diagonal cells, which
  is why the crossed non-safety control is part of the design rather than an afterthought -- and, in this
  revision, why that control is CALIBRATED on the model's own prefix log-probability before anything is
  subtracted, since an interaction control that produces a milder mismatch than the treat
</pasted_content id="715d">


<pasted_content id="715d">
ment cells
  under-subtracts by exactly the amount that would manufacture the headline.

  Two smaller imports remain. From experimental psychology, the factorial logic that separating two
  confounded causes requires varying each independently over the same materials: reading safety at one
  token position is a one-cell design and the fix is the other three cells. From reliability engineering,
  the observation that a two-barrier system fails as though it had one barrier when a single fault removes
  both, which is what made the fitting-set argument load-bearing rather than a curiosity. This revision
  adds a third, from measurement theory: a quantity is only comparable across instruments if it is
  expressed in units the instrument itself defines, which is why every cross-checkpoint term is now read
  in that checkpoint's own measured null-band scale instead of in raw residual-stream units.

  The negative screening mattered as much. Five mechanisms were built and abandoned in an earlier
  iteration because their core already exists: attention-side versus write-side dissociation, the
  read-rank versus write-rank funnel, mutational robustness of refusal under weight noise, a
  recognition-versus-enforcement two-axis profile, and a common-cause-failure concentration score. A
  sixth was abandoned next -- the bare closed-loop main effect, which arXiv:2607.14147 owns causally --
  and the question was kept by moving to the term that paper's design cannot reach.
terms:
- term: Published response-site effect (T)
  definition: >-
    T = CB + A = s_H,haz - s_H,ben: how much the internal safety signal moves when hazardous text appears in the model's own
    output under a HARMFUL request. It is algebraically a simple difference, it is the quantity existing response-site work
    reports, and it is nonzero in every safety-trained checkpoint by construction. That last property is why the headline
    survival test is stated as a change in T: a change in CB alone would have a floor in the lineage predicted to have little
    CB to lose, and a post-edit level comparison would be entailed by the pre-edit gap.
- term: Arming (A)
  definition: >-
    The interaction term of the 2x2: how much MORE a model's internal safety signal reacts to hazardous text it has already
    written when the request was harmful than when the request was a matched benign twin. Large A means an output monitor
    the request switches on; A near zero means one that is always on. It is the headline quantity because it is the part of
    the response-conditioned signal that a base model's generic autoregressive conditioning does not predict.
- term: Unconditional output monitoring (CB)
  definition: >-
    The response main effect measured under the BENIGN request: how much the internal safety signal moves when hazardous text
    appears in the model's own output although nothing in the request called for it. Never used alone as evidence of safety,
    because a non-safety-tuned model can have a nonzero CB from next-token statistics alone, which is why the CB half of the
    specificity gate requires the causal arm.
- term: Open-loop strength (O)
  definition: >-
    The request main effect: how much the internal safety signal differs between a harmful request and its matched benign
    twin, averaged over both response prefixes. This is the component every standard cheap readout measures, and the component
    a prompt-fitted weight edit is fitted on. It is also the axis along which the two lineages are matched for edit damage
    before any survival comparison is made.
- term: Effect modification
  definition: >-
    The epidemiological name for a situation in which the effect of one factor depends on the level of another. Its methodological
    consequence is imported directly: where modification is present, a main effect averaged over the modifier is not a property
    of the system, so a response-site effect measured only under harmful requests cannot be read as a per-model property.
- term: Response-content harm axis (r_content)
  definition: >-
    
</pasted_content id="715d">


<pasted_content id="715d">
The primary readout direction: a difference in means between hazardous and benign CONTINUATIONS taken at RESPONSE token
    positions, under one held-fixed neutral request, on a fitting corpus disjoint from the evaluation items. It is deliberately
    a different vector from the abliteration direction, which is a difference in means over harmful versus harmless REQUESTS
    at the last PROMPT token. Their cosine is a pre-registered gate, because if the two coincided the weight edit would delete
    the measurement coordinate and every post-edit number would be an algebraic residue rather than a fact about safety.
- term: Null-SD unit
  definition: >-
    The unit every cross-checkpoint comparison is reported in: the per-ITEM standard deviation of the same contrast computed
    under at least 20 random unit directions in that same checkpoint. It is independent of the item count and it carries that
    checkpoint's own residual-stream and LayerNorm scale, which raw projections do not, so it is what makes a term measured
    in a base model, an RL-tuned model and a weight-edited model the same quantity.
- term: Refusal drive
  definition: >-
    The dependent variable of the causal arm, and of the CB half of the safety-specificity gate. PRIMARY: the teacher-forced
    probability mass on a fixed refusal-onset token set at the position immediately after the intervened span, which is well
    defined in a base model and needs no decision label. SECONDARY: a cross-validated full-probe decision score trained on
    the instruct model and applied unchanged elsewhere. It is an output-side readout of an activation-side intervention; the
    deployed metric never uses it.
- term: Coherence control, and its calibration
  definition: >-
    A second 2x2 of the same shape over the same items in which a safety-irrelevant attribute is crossed the same way: a benign
    request about topic A or B, crossed with a benign prefix about topic A or B. It estimates the generic instruction-mismatch
    interaction that would otherwise be indistinguishable from arming. Subtracting it is only licensed if its mismatch is
    as severe as the safety crossing's, so the two are calibrated on the model's own mean log-probability of the prefix given
    the request, and where they do not match the readout is regressed on that penalty instead of having a constant subtracted.
- term: Prefix family
  definition: >-
    One of two structurally different templates from which every hazardous continuation is generated. ANNOUNCED opens by naming
    what it is about to do; ENACTED performs the hazardous content in-stream with no meta-announcement. Both are run because
    a result present only under an explicit announcement is a property of the announcement rather than of the content.
- term: Abliteration
  definition: >-
    A training-free edit that removes a model's ability to refuse. One refusal direction is estimated by difference of means
    over harmful versus harmless REQUESTS at the last prompt token, then orthogonalised out of every weight matrix that writes
    to the residual stream. Everything it is fitted on lives on the request axis, which is the structural basis of the headline
    prediction. Here it is used as a controlled manipulation for localising the signal, in the way a lesion localises a function.
- term: Matched request-axis damage
  definition: >-
    The condition under which two lineages are compared after editing: edit strengths chosen so that each lineage loses an
    equal amount of O, read off its own measured strength-to-damage curve by interpolation. Without it, a lineage on which
    the edit simply bites less would look protected.
- term: Safe completion
  definition: >-
    An alignment style in which a model answers a risky request at a safe level of detail instead of refusing. Qwen3-4B-SafeRL
    is an openly released model of this kind: in non-think mode its card reports safety rising 64.7 to 98.1 on WildGuard and
    47.5 to 86.5 on the stronger Qwen3-235B judge, while refusal falls 12.9 to 5.3; in think mode refusal b
</pasted_content id="715d">


<pasted_content id="715d">
arely moves, 6.5
    to 6.2.
- term: Safe-engagement rate
  definition: >-
    The fraction of harmful requests a model answers without refusing and without emitting harmful content. A co-primary target
    alongside harmful-compliance rate because, unlike refusal rate, it penalises a blanket refuser, and no cheap internal
    safety metric has been validated against it.
- term: Parent-fixed versus refitted direction
  definition: >-
    Two readout conventions, each registered where it is correct. Parent-fixed, the parent's direction applied to the edited
    child, is the only convention under which 'the arming fell more than the monitor' is a statement within one basis, so
    it is primary for the edited arm, and the direction is carried over rather than refitted inside a fold. A per-checkpoint
    refit is what the DEPLOYED metric must use, since an arbitrary HuggingFace model has no parent.
- term: Teacher forcing
  definition: >-
    Running the model over a fixed, pre-written continuation instead of letting it generate. It makes the four cells exactly
    comparable, costs one forward pass each, and removes sampling noise and decoding choices from the measurement.
- term: Benign twin
  definition: >-
    A request lexically and structurally close to a harmful one but carrying no harmful intent, drawn from XSTest's purpose-built
    safe split rather than authored from scratch. Twins are what make the request factor a manipulation of intent rather than
    of vocabulary.
summary: >-
  A response-site safety effect measured only under harmful requests is an average over an unvaried modifier, not a property
  of the model: crossing the request factor with the model's own already-written output splits that effect into an unconditional
  output monitor and a request-gated ARMING term, and the three Qwen3-4B checkpoints differ mainly in which one they have.
  The resulting three-number profile is read from one model's activations with no generation and no judge, and the claim is
  that a prompt-fitted weight edit destroys the arming term and leaves the monitor, so the pre-edit arming measurement forecasts
  how much safety survives the edit.
alternates:
- title: The refusal a model brings before it reads
  hypothesis: >-
    A model's refusal drive decomposes into an input-independent PRIOR, readable from a contentless forward pass with literally
    zero prompts, plus an input-dependent EVIDENCE slope, how far the internals move per unit of actual harmfulness. Published
    safety scores are a fixed monotone mixture of the two, which is why a model that is safer while refusing less is ranked
    backwards, and the two numbers read separately from one checkpoint's internals reproduce the mixture and beat it. Concretely:
    the base model has neither, the refusal-tuned model has a high prior, the safe-completion model has a low prior and a
    high slope, and abliteration drives the prior down while leaving the slope intact.
  why_it_could_win: >-
    It wins if the arming interaction is swallowed by the coherence calibration -- if the mismatch penalty in the safety crossing
    cannot be matched and A_net survives only as an upper bound -- because then the interesting structure is entirely in the
    request-to-signal mapping and the prior-slope split is the sharpest decomposition of it. It also wins on cost, since the
    prior needs zero prompts, the extreme end of what the request asks for. It would have to be positioned tightly against
    signal-detection and item-response-theory treatments of refusal, which make the same conflation argument behaviourally
    rather than at the activation level.
- title: Measure safety without any harmful text
  hypothesis: >-
    A checkpoint's safety level is predictable from its internals on entirely benign or contentless inputs, with no harmful
    content anywhere in the pipeline, because safety training leaves a systematic footprint on ordinary computation. The claim
    is specific rather than correlational: safety training reserves residual-stream capacity and shifts ben
</pasted_content id="715d">


<pasted_content id="715d">
ign computation
    in a direction that abliteration partially reverses, so the size of that shift, measured against the model's own benign
    baseline, orders the arms and transfers across families.
  why_it_could_win: >-
    It wins if the matched-quadruple construction proves fragile -- if the Stage-0 twin, prefix or placebo gates fail -- since
    it needs no harmful prompts, no twins and no matched prefixes at all. It also wins on deployability: an instrument that
    never touches harmful content can be run on any checkpoint by anyone, and every existing cheap instrument still needs
    a harmful or jailbreak set even when it skips generation. Its risk is the mirror image of the main hypothesis's, since
    a footprint on benign computation may be a footprint of fine-tuning in general, so it lives or dies on the same non-safety
    fine-tune control.
- title: How long the hazard state survives
  hypothesis: >-
    The safety-relevant difference between the checkpoints is the PERSISTENCE of the internal hazard state. Under a fixed
    teacher-forced continuation identical across models, the hazard readout decays with token position at a rate that is a
    stable per-checkpoint property, and its time constant in tokens -- hence unit-free, and immune to the cross-checkpoint
    scale problem that forces every level comparison into null-SD units -- orders the checkpoints and predicts how well safety
    survives long generations. Predicted short in the refusal-tuned model, which only ever needed the signal at token one,
    long in the safe-completion model, near zero in the base model, short in the abliterated model.
  why_it_could_win: >-
    It wins if the response-conditioned signal is real as a correlation but dies under harm-subspace patching, leaving decay
    rather than feedback as the mechanism, and it wins outright if the depth curve the main design already collects shows
    A is a transient rather than a plateau. It is also the cheaper instrument, needing one prompt and one fixed continuation
    per model rather than a matched quadruple plus a calibrated coherence control, and a decay constant estimates stably at
    small sample sizes where an interaction does not.
- title: Safety is a profile over harm domains
  hypothesis: >-
    Safety is not one mechanism but a set of harm-domain-specific write pathways with independently set gains, so a checkpoint's
    safety is a PROFILE over domains rather than a scalar, and the per-domain gains are readable from one model's internals
    with a handful of prompts per domain. The prediction that makes it testable on this trio: safety RL optimises an aggregate
    reward and should FLATTEN the profile, while abliteration removes a single direction fitted to one extraction set and
    should thin it unevenly, deepest in the domains that dominated that set, leaving a checkpoint genuinely still safe on
    some domains and not others.
  why_it_could_win: >-
    It wins if within-checkpoint variation across harm domains is larger than between-checkpoint variation, which would mean
    the field's single safety number is the wrong object however it is measured, and it would make the deliverable a risk
    profile rather than a score. It needs no counterfactual construction, no matched prefixes and no coherence control, so
    it is robust to the Stage-0 gates failing, and it is the only candidate whose output an open-weight release process could
    act on directly.
_relation_rationale: >-
  Recognition-vs-execution becomes one case of a depth-by-site profile graded against behaviour.
_confidence_delta: decreased
_key_changes:
- >-
  EVIDENCE CLASSIFIED weak_or_null: the pre-registered screen returned survivor NONE (E1 under-powered by strata, no E2/E3
  pass, E4 not evaluated), and the only readout separating every child from its parent tracks the logit baseline BL1 (6/6,
  median -2.86 vs -2.98).
- >-
  OUTCOME CHANGED from repo-name edit labels on a few checkpoint pairs to MEASURED, GRADED behaviour (harmful compliance,
  over-refusal, severity-weighted) regressed
</pasted_content id="715d">


<pasted_content id="715d">
 across the whole panel under leave-one-family-out. This fixes both the power
  failure (strata 3/2/1) and the specificity failure (K1 fires 4.14 null-SD on the granite behavioural no-op).
- >-
  GOVERNING OBJECT WIDENED from a binary recognition-vs-execution split to a depth-by-site profile. Every readout that moved
  did so at depth or at the response site: late-site TPR@1%FPR -0.144 vs prompt-site +0.0006, and parent-child |cos| 0.992
  shallow vs 0.459 deep.
- >-
  EXPLICIT SCREEN over 14 named single-model candidates (C1-C14), all computable from harvests on disk or one prompt-only
  forward, with a selection rule fixed before scoring: beat BL1 by rho >= 0.15 with a CI excluding zero, a nonzero partial
  rho given BL1, escape the shuffled-label band, stay silent on the null-edit pair and random-init arm, and stay off ceiling.
- >-
  HELD-OUT CONFIRMATION separated: the 2 sealed families, the never-loaded 54-scenario XSTest split and a fresh graded set
  of at least 6 held-out checkpoints, used once with no re-screening.
- >-
  BARS RAISED: BL1, B3, B7 and the Jorak scanner's parent-free A (which closes X2 and X10 as prior art) are incumbent bars,
  not candidates; every activation number is printed next to BL1.
- >-
  REVIEWER CORRECTIONS ADOPTED: safety training moves recognition too (TPR 0.475 to 0.875), so 'execution, not recognition'
  is scoped to the abliteration contrast only; the request-axis Cohen's d is relabelled a prompt-site recognition-type readout.
- >-
  NON-SAFETY CONTROL STATED ACCURATELY: STaR matches its base only on Cohen's d (5.74 vs 5.68); on peak drive (1.57 to 2.57)
  and BL1 (-0.30 to 1.96) it moves partway toward instruct, so part of the refusal-drive signal is generic chat fine-tuning.
- >-
  THE ABLITERATED CHECKPOINT IS IN EVERY TABLE: Cohen's d, k=16 restricted-budget AUROC and the full depth-by-site profile
  are computed for mlabonne/Qwen3-4B-abliterated and every effective child. This closes the review's standing must-fix.
- >-
  ACCUMULATOR CLAIM MADE TESTABLE: fixed-axis (frozen shallow direction read forward) and per-layer own-axis controls are
  added (C6/C7). The post-lesion orthogonality at the fitting layer is labelled forced by construction and withdrawn as evidence.
- >-
  SITE DISSOCIATION REPORTED PER LINEAGE, including non-safety L4, where the late-site drop is largest (0.404 to 0.234). The
  Holm sentence is corrected: significant only at full lesion, TOST-equivalent at alpha <= 0.5. The 10.6x cross-statistic
  ratio is dropped.
- >-
  CAUSAL CHECK REQUIRED FOR ANY SURVIVOR: a matched-norm fitted-vs-orthogonal-random projection with judged outcomes, per-item
  distributions and benign collateral. Without it the survivor is a READOUT, never a mechanism.
- >-
  OVER-REFUSAL ADDED AS A SECOND OUTCOME (C10), so the metric covers both failure directions rather than harmful compliance
  alone.
- >-
  PRIOR-ART LEDGER RESOLVED: Orgad 2604.09544 and 2603.05773 own the recognition-vs-execution naming, 2606.24952 owns the
  weight-computable cosine, and 2607.01854 needs the parent. The Jorak citation is either verified by URL or removed. The
  claimed empty cell is graded, cross-family behaviour prediction from one model, including abliterated checkpoints.
_evidence_state: weak_or_null
_move: widen
_move_rationale: >-
  Screen ran to completion: survivor NONE, and the only readout that separated children from parents tracks the logit baseline.
  3 iterations remain, so the rule mandates widen.
_coverage: full
_coverage_statement: >-
  The next iteration answers all three parts of the ask: an activation-level depth-by-site comparison of Qwen3-4B Base, SafeRL
  and abliterated with the abliterated model in every table; the internal-computation pattern that separates them; and a screened,
  held-out-confirmed single-model metric on at most 16 prompts.
_candidates_considered: 14
relation_type: embedding
</hypothesis>

<all_artifacts>
FULL EVIDENCE BASE: All 12 research artifacts across all iterations.

--- Item 1 ---
id: art_CC5kC0-E3lXW
type: research
title: Which of the five safet
</pasted_content id="715d">


<pasted_content id="715d">
y readouts is still unclaimed
summary: >-
  Web-only saturation and anchor-verification pass, 2026-09-20, ~$0 spend, no cuts taken. All 26 core arXiv ids resolved (0
  unresolved, 0 mis-cited) plus 20 newly discovered ids. VERDICTS: K1 arming interaction = PARTIALLY SCOOPED (HARC 2607.00572
  owns the response-site readout via Eq 2 but never crosses the two factors, uses no matched twins, and reports no interaction);
  K2 prior + evidence slope = OPEN at the activation level but its construct is published behaviourally by IRT 2608.05086
  over 192 models; K3 benign-only footprint = PARTIALLY SCOOPED, with LatentBiopsy 2603.27412 - not Skin-Deep - as the true
  nearest relative; K4 persistence time constant = CLOSED by N-GLARE's JR Min/Max (ACL 2026 Long 1334, Eq 9), a per-model
  persistence scalar over 40+ models; K5 per-domain profile = PARTIALLY SCOOPED and thin. FOUR deliverable-level competitors,
  not two: N-GLARE, Skin-Deep/GFS, the 273-checkpoint abliteration audit 2607.01854, and IRT-10-items. F1 ANSWERED DECISIVELY:
  HARC does print numeric cross-position cosines, for Qwen, at 0.19/0.10 (L12) and 0.31/0.30 (L27), so lane B's |cos| <= 0.50
  gate is expected to PASS; 2604.18901's independent 73+/-7 degree protocol angle (cos ~ 0.29) converges on the same answer.
  F2 OVERTURNS THE PLANNING RECON: 2604.18901 prints +/-0.003 twice and 73 degrees twice, for four different quantities, and
  the hypothesis's readings were the right ones. Three new adverse priors the run had not seen: HRCI_repr (2606.16349) is
  a parent-free single-checkpoint coupling index whose authors report it is NOT a safety score; the Entanglement Wall gets
  AUROC 0.590-0.690 on XSTest-style twins; and harm recognition is invariant to abliteration in two independent papers. Ten
  baselines specified for reimplementation, including the newly recovered HRCI_repr formula. PROVENANCE: all 32 sources listed
  were ACTUALLY FETCHED (no snippet-only entries), and every one of the 59 supporting passages was re-verified by an independent
  live fetch of its own URL before this file was written.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_research_1
out_expected_files:
- research_out.json

--- Item 2 ---
id: art_jn337OmvTVjZ
type: dataset
title: Frozen safety stimulus set and source corpora
summary: |-
  FROZEN STIMULUS SUBSTRATE + SOURCE CORPORA for the Qwen3-4B safety mech-interp study. Nothing here touches a model: no weights (only the ~15 MB Qwen3 tokenizer), no forward pass, no activations, no direction fitted, no grading. Every number in the criteria table comes from downstream lanes reading these frozen files.

  WHAT full_data_out.json IS: the 10 kept source corpora, exp_sel_data_out schema, ONE SOURCE ROW PER EXAMPLE grouped by dataset (7604 examples): xstest_v2, or_bench_toxic, or_bench_hard_1k, strongreject_small, advbench_harmful_behaviors, jbb_behaviors_harmful, jbb_behaviors_benign, phtest, harmbench, databricks_dolly_15k. Built by data.py (stdlib only; `uv run --no-project data.py`). 15 candidates were standardised and inspected, 5 discarded with written reasons (redundancy, schema fit, unverified licence, CC-BY-NC); all 15 remain at results/full_data_out_all15.json. metadata_harm_domain uses the OR-Bench 10-value vocabulary; XSTest rows read theirs from results/twin_pairs.json so the corpora and the substrate carry ONE label per row.

  THE ACTUAL SUBSTRATE (data_out.json, 3,014 rows + heldout_cells.json, 1,350 SEALED rows): 150 genuine XSTest v2 minimal-edit twin pairs (focus-join and +25 offset agree on 149/150), hash-split 96 confirmatory / 54 sealed BEFORE any cell text existed (salt and both id-list SHA-256s in prereg.json). 3,877 rendered cells, every one exactly 144 tokens with its action slot intersecting BOTH read windows (EARLY 5-20, LATE 40-55) under the real Qwen/Qwen3-4B tokenizer; within an item+family the hazardous, benign and placebo continuations have IDENTICAL token counts at EVERY index and differ only inside the two slot regions. Tables: safety_2x2, placeb
</pasted_content id="715d">


<pasted_content id="715d">
o, coherence_control (also crossed with prefix family, a deliberate superset of the planned 600), graded_harm_ladder, contentless, fixed_shared_continuation, fitting_corpus (64 pairs, 0 shared action lemmas/4-grams with XSTest), harm_domain_profile, three behavioural request sets. Siblings: prereg.json (sha256 0b86d66a8dffca717f8c523569ab04a0987134158e36c342e738ab93b8027f50), model_registry.json (40 repos, metadata only, 36 ungated, 12 families with an ungated instruct arm, 2 SEALED: Qwen2.5-1.5B, SmolLM2-1.7B), judge_validation.json, rubric.md, templates.json, sources_manifest.json, verification_report.json.

  WHAT FAILED, AND IS REPORTED AS FAILED (do not read these as passes):
  1. Prefix HAZARD identification gate FAILED at 0.9429 vs a 0.95 threshold after the one regeneration round the plan allows. The threshold was NOT relaxed: the 16 affected items are marked metadata_qc_fail=true and metadata_confirmatory=false, and CONFIRMATORY n DROPS FROM 96 TO 85. 11 of the 16 are benign/placebo prefixes a rater called hazardous, concentrated in historical_events and safe_contexts, whose benign member is an explanatory act ABOUT a harmful topic.
  2. Placebo distance gate FAILED: median edit distance ratio 1.25 vs the required <=1.10. A floor, not a search failure: a placebo SELECTED from another item's benign action cannot beat the ~5-token distance between two unrelated short phrases, and enlarging the pool 100->164 does not move the median. Mean ratio is 1.133 and 99/150 items match exactly; per-item distances ship as metadata_levenshtein_to_benign_prefix so a lane regresses on them instead of subtracting a constant.
  3. XSTest CANNOT supply 6 harm domains: it is violence-skewed and only 3 of 10 reach 8 confirmatory twin pairs. Thin domains are topped up from OR-Bench with twin_available=false, so K5's per-domain profile rests PARTLY ON NON-TWIN items. The 2x2 and the ladder use twins ONLY; no non-twin row ever enters the 2x2.
  4. Only 4 of the 6 contrast families are SURFACE-minimal. definitions and historical_events are matched on topic via the shared focus term but rewrite the sentence frame; metadata_minimal_edit_tier ships so a lane needing a small surface edit can restrict to Tier A (100 pairs, 64 confirmatory).
  5. The ladder covers 149 of 150 items; one pair was declined by both model families and its rungs 1-3 are null.
  6. There is NO human rater anywhere in this pipeline; two cross-family LLM raters substitute. A substitution, not an equivalence.

  GATES THAT PASSED: twin-member identification 0.9967, announce-vs-enact 0.9506, ladder Spearman rho 0.878, non-operationality 0 flags over 360 distinct hazardous continuations, pooled Cohen's kappa 0.8953. 32/33 verification checks pass. OpenRouter spend $2.52 of the $10 cap. walledai/HarmBench and allenai/wildguardmix are genuinely gated and were skipped, never authenticated or substituted; or-bench-80k was never ingested.

  DOWNSTREAM CONTRACT: read data_out.json for the confirmatory work and NEVER open heldout_cells.json in a lane that fits, tunes or selects. Quote prereg.sha256 to show nothing was chosen after the fact. Filter on metadata_qc_fail and metadata_confirmatory, not on metadata_fold alone, or you will silently re-include the 16 excluded items.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_dataset_1
out_expected_files:
- data.py
- full_data_out.json
- preview_data_out.json
- mini_data_out.json

--- Item 3 ---
id: art_2QM9uBviY4Wk
type: experiment
title: Where safety lives in a model's activations
summary: |-
  LANE A EXECUTED IN FULL. Seven Qwen3-4B checkpoints (instruct, SafeRL, Base under both a chat-template and a plain protocol, a non-safety task fine-tune of the same base, mlabonne's abliterated edit, and an architecture-identical RANDOMLY INITIALISED control added per the mech-interp handbook) were each streamed through ONE teacher-forced activation harvest: 1,913 passes per checkpoint, 13,391 total, ZERO generated tokens, 85-274 s each. Nothing was skipped, no CPU-offload fallback 
</pasted_content id="715d">


<pasted_content id="715d">
fired.

  DESIGN. A 2x2 crossing of REQUEST (XSTest minimal-edit twins) x CONTINUATION (a pre-written procedural frame in which only the named ACTION varies). Prefixes are built as TOKEN ID LISTS with the ACTION pinned to token 8 and token 46 of an exactly-80-token prefix, so the hazardous and benign cells read at IDENTICAL offsets and no read window can be structurally empty. Terms: O (orientation), CB (content-bearing), A (arming interaction), T = CB + A -- the identity holds to 0.0 per item, a decisive wiring check. Projections onto r_content, a diff-in-means axis fitted on a DISJOINT 128-pair corpus (zero exact/5-gram overlap with the twins). 54 of 150 twin pairs were hash-split out before any activation was collected and never loaded. Pre-registration frozen by SHA-256 before the first forward pass and re-verified by the analysis.

  HEADLINE RESULTS. (1) THE ARMING TERM IS REFUTED BY ITS OWN CONTROL. A reaches -4.3..-9.3 null-SD, but refitting r_content on PERMUTED labels and re-running the whole pipeline reproduces |A| up to 11.0-11.8; A escapes that shuffled-label band in NO checkpoint. In the random-init arm the band collapses to 1.27 and the real term collapses with it, proving the width is a property of trained representations. T escapes in only 3 of 7 -- all three NON-safety arms. The two nulls (isotropic random-direction SD as the UNIT vs shuffled-label band as the EVIDENCE test) disagree, and only the second licenses a claim.
  (2) S1: ONLY K3 PASSES (benign-only activation footprint; margins +1.07 and +0.74 null-SD over both non-safety arms, CIs excluding zero). K1, K2, K4, K5 FAIL. K3 needs NO harmful prompt, and its weights-only twin (mean stable rank over the band) needs NO prompt at all: 216.3 in every trained checkpoint vs 977.4 random-init.
  (3) |cos(r_content, r_ablit)| = 0.04-0.09 at the band, max 0.19 over any layer. The response-site continuation-harm axis and the prompt-site request-refusal axis are NEAR-ORTHOGONAL, so HARC (arXiv:2607.00572) "remain aligned" does not hold at 4B -- and a parent-fixed post-edit arm is therefore NOT confounded.
  (4) CROSS-LINEAGE DISSOCIATION (licensed because the panel is one fine-tuning lineage; the random-init arm returns 0.01-0.02 as the unrelated-basis null): cos(r_content) is 0.90-0.99 for every trained pair, while cos(r_ablit) is 0.896 for Qwen3-4B->SafeRL, 0.361 for Qwen3-4B->abliterated, 0.200 for Base->instruct and 0.041 for Base-chat vs abliterated. Safety training moves the REFUSAL axis and leaves the CONTENT axis alone; abliteration rotates refusal away from its own parent.

  GATES AND BASELINES. Band frozen at layers 14-22 (depth 0.39-0.61) by cross-fitted d on Qwen3-4B's fitting corpus alone. G3 positive control passes in all six trained arms (cross-fitted d 0.85-0.95) and fails in random-init (0.58). G1 FAILS EVERYWHERE (split-half cosine 0.35-0.39 vs 0.70), so the registered fallback fired and a supervised probe axis is reported beside every K1 term. Baselines: B1 diff-in-means AUROC 0.66-0.73, B2 raw-hidden-vector probe 0.97-0.98 (the supervised ceiling), B3 cluster separation, B4 refusal logit gap at TWO read sites (the first-response-token site is structurally zero for a continuation contrast, so a post-continuation site was added to keep the baseline fair) -- B4 is labelled NOT-A-DELIVERABLE under the run invariant. G5 placebo TOST fails everywhere; G6 licenses subtraction only in the non-safety arms, so A_net is an upper bound in the safety arms; K4's tau is UNDEFINED everywhere (R^2<0.3). Achieved r is 3.2-10.0 against a planned 1.2, so the MDE at n=96 is 0.65-1.99 -- above the registered 0.50 and stated as an under-powering, not relaxed. External judge gate PASSED (twin forced-choice 0.979, prefix hazard rating 0.900) for $0.0023 of a $10 budget.

  ARTEFACTS. out/method_out.json (schema-validated) carries every gate, the null-SD and scale tables, per-item quantiles, the S1 table, the cosine curves and all baselines; out/SUMMARY.md is the human digest; out/released/ has 24,192 per-item cell projections, r_content/r_ablit .npy, layer-by-
</pasted_content id="715d">


<pasted_content id="715d">
position maps, position curves, the cross-checkpoint direction table and the item substrate. Lane A declares NO survivor: S1 is 1 of 3 screen tests and promotion needs >=2 of 3 from lanes B and C. HARVEST FORMAT: archives over 100 MB (grid/proj/fit) are stored as axis-0 row shards -- <name>.partNNN.npz plus <name>.shards.json -- and are read with lane_a.shard.load_npz, which reassembles them byte-identically.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_1
out_expected_files:
- method.py
- full_method_out.json
- mini_method_out.json
- preview_method_out.json

--- Item 4 ---
id: art_2sz7g3MD4_y3
type: experiment
title: Uncensoring a model doesn't blind it to harm
summary: |-
  LANE B asks where safety lives by LESIONING it: one rank-one, prompt-fitted orthogonalisation W <- W - a*u*(u^T W) applied to every residual-stream write matrix (o_proj + down_proj, all 36 layers) at five strengths, with all five candidate readouts (K1 arming, K2 prior+slope, K3 benign-only footprint, K4 persistence, K5 domain profile) recomputed before and after. Substrate: 150 XSTest minimal-edit twins from the six genuine contrast families, sha256-ordered 96/54 split (the 54 never touched), a 2x2 of request{harmful, matched benign twin} x response-prefix{hazardous, benign} with the response span token-identical across the request manipulation, plus disjoint fitting and held-out request corpora. prereg.json was frozen before the first forward pass and verified byte-identical at the end.

  INSTRUMENT. Qwen3 gives o_proj/down_proj no bias, so for y = W0 x the edit is EXACTLY y -> y - a*u*(u^T y). Applied as an output projection, alpha=0 is a BITWISE no-op, the restore is exact, and embed_tokens - which IS lm_head on all four lineages, L4 included - is provably untouched, so the causal arm's logit outcome is uncontaminated. Verified against a genuine bf16 weight mutation. Frozen band = layers 13-21, r_content split-half cosine 0.927.

  MAIN RESULT. The lesion is verified exact - the raw projection gap along u falls as [1.0, 0.744, 0.482, 0.228, 0.0] against a predicted (1-alpha) - and the harm representation survives it ENTIRELY: the held-out 5-fold CV probe reads [1.0, 1.0, 1.0, 1.0, 1.0] across the alpha grid. Removing u POST-HOC from activations instead drops that probe 1.000 -> NA, while removing 128 RANDOM directions costs nothing. So in the INTACT model the 2559-dim orthogonal complement of u is NOT sufficient. In the LESIONED model, which was never allowed to write u at all, that same complement reads 1.000 and behaves identically under its own top-direction removal (NA). (The post-lesion orthogonality itself is FORCED by construction and is not claimed as a result.) The obvious alternative - that removing a class-correlated component changes the residual NORM class-correlatedly and RMSNorm manufactures the separability - is REJECTED: the probe still reads NA on unit-normalised activations, and the norm alone flips from a NA-AUROC harm detector in the intact model to NA (anti-predictive) after the lesion. Depth profile: held-out AUROC is already ~1.000 by layer 13 in BOTH states, while the signal along u grows ~138x with depth in the intact model (NA -> NA) and is zeroed at every depth in the lesioned one. u is an ACCUMULATOR COORDINATE, not the locus of the percept: abliteration removes the refusal ACTION, not the harm PERCEPT.

  G1, reported as a RESULT and not only a gate: |cos(r_content, r_ablit)| = 0.159 pooled / 0.175 max. The response-site content axis and the prompt-site request axis are near-ORTHOGONAL, so HARC's alignment kill-risk does not bite here.

  STAGE 9, weights only: mlabonne/Qwen3-4B-abliterated is per-matrix rank-one (median 0.9945) at implied alpha 0.973, leaves embed_tokens untouched, but uses ONE DIRECTION PER LAYER: pooled rank-one share only 0.433, and |cos| 0.016 between the shallowest and deepest layer's edit direction.

  THE METRIC (the run prompt's 'few-prompt safety score'). Fit r_ablit at EVERY layer of ONE model from 128 harmful + 128 h
</pasted_content id="715d">


<pasted_content id="715d">
armless PROMPT-ONLY forwards - no generation, no benchmark, no judge, no reference model - and report the best layer's Cohen's d and its DEPTH FRACTION: L2 Qwen3-4B d=11.15 at layer 22 (depth 0.64). Safety tuning roughly DOUBLES the separation and moves it several layers EARLIER. The load-bearing control is L4, a fine-tune of L1 on a NON-safety objective: it lands on top of its base parent, so the readout tracks SAFETY tuning, not fine-tuning as such. n = 4 checkpoints, so this is a demonstration with one clean negative control, not a validated metric; the outputs carry a prompt-budget curve for how few items the paired contrasts need.

  HONEST LIMITS. The pre-registered PRIMARY damage variable is FLAT at ceiling, so no matched-damage point exists for 1 lineage(s) and every registered S2 row is INDETERMINATE (failure mode F1). The threshold was NOT relaxed and alpha=1 was not extrapolated past; a LABELLED full-annihilation companion is reported beside it. Read as the LEVEL test its wording specifies, K1 is HALF-satisfied: CB survives but A attenuates without collapsing into the null band. K4's observed sign is OPPOSITE to its registered signature (tau lengthens). Registered grid: ['L2']; declared per-layer grid: []. method_out.json carries 673 examples over 7 datasets; every predict_* that is not predict_baseline_* reads activations or weights of a SINGLE model.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_2
out_expected_files:
- method.py
- full_method_out.json
- mini_method_out.json
- preview_method_out.json

--- Item 5 ---
id: art_rpTmjn5qclSY
type: experiment
title: Predicting model safety from its activations
summary: >-
  LANE C (test S3): does an activation/weight-only, single-model safety readout predict real safety BEHAVIOUR across model
  families, and from how few prompts? Panel: 21 scored checkpoints across 7 ungated <=4B families (Qwen3 incl. the commissioned
  4B Base/Instruct/SafeRL trio plus 0.6B/1.7B arms; Qwen2.5; SmolLM3; Granite; OLMo-2; TinyLlama; Phi-4-mini) plus 2 SEALED
  families (StableLM, SmolLM2) fully measured but withheld from truth for iteration 2. Everything is frozen by SHA-256 in
  prereg.json before the first activation. From ONE teacher-forced harvest per checkpoint we compute five single-model candidate
  readouts -- K1 arming decomposition [O, CB, A, T] of the projection onto a response-site content direction r_content (fit
  per-checkpoint on a disjoint corpus, split-half cosine ~0.95, held-out AUROC ~1.0, |cos(r_content,r_request)| ~0.35-0.60
  so the content axis is distinct from the abliteration/request axis); K2 request-side prior+slope; K3 base-relative footprint
  (activation + weight, undefined for 2-arm families); K4 hazard-decay tau; K5 domain profile -- all placed in a random-direction
  NULL-SD unit so features are comparable across hidden sizes 1024..3072 with NO recalibration. Seven baselines: B1 card/name
  regex, B2 refusal rate, B3 first-token refusal-logit gap, B4 prompt-axis Fisher, B5 r_request projection, B6 raw-hidden
  geometry, B7 an N-GLARE (arXiv:2511.14195) APT/JSS reimplementation (labelled, not the authors' code). Behavioural ground
  truth (harmful-compliance, over-refusal, and the co-primary SAFE-ENGAGEMENT) comes from greedy generations LLM-judged by
  gemini-2.5-flash-lite, audited by gpt-5-mini (kappa refused 0.71, harmful_content 0.57, on_topic_help 0.47; raw agreement
  0.86/0.84/0.74). S3 = leave-one-family-out ridge prediction with z-scoring/PCA/ridge all fit on training families only;
  metric = pairwise ranking accuracy (|delta truth|>=0.05), decision = margin>=0.15 over the oracle-selected strongest baseline
  AND family-clustered bootstrap 95% CI>0 AND >=5/7 families won. HEADLINE (both outcomes publishable): NO candidate passes
  S3 on either target; machinery controls are clean (oracle ranking accuracy 1.00; random 0.556/shuffle 0.585 mean noise floor).
  The strongest cross-family predictor is the LOGIT baseline B3 (first-token refusal-logit gap: 0.851 safe-engagement
</pasted_content id="715d">


<pasted_content id="715d">
, 0.863
  harmful-compliance); the best ACTIVATION candidate is K1 arming (0.671 safe-engagement; 0.810 harmful-compliance, already
  0.882 from just k=4 prompts) but it does not surpass B3. A sharp within-family mechanism is nonetheless visible: across
  the commissioned Qwen3-4B trio the arming term A orders Base(-2.32) < Instruct(+0.18) < SafeRL(+1.90), and SafeRL is a safe-completion
  model (~0% refusal) whose safety refusal-based baselines miss internally -- yet this arming signal does not transfer across
  families to beat B3 at this panel size. The result localises that the response-site arming representation is real and family-specific
  but not a family-invariant behavioural predictor; per the screen's rule iteration 2 widens rather than deepening. Deliverables:
  method.py (orchestrator) + lc_common/lc_assets/lc_panel/lc_harvest/lc_judge/lc_analyze/lc_output modules; method_out.json
  (full/mini/preview) with the frozen prereg, panel table, per-checkpoint raw+null-SD feature table with per-item distributions,
  ground-truth columns, full S3 tables (margin, CI, families-won, budget curve k in {4,8,16,32,96}, random/oracle/shuffle
  controls) per candidate x target, sealed candidate values without truth, cost ledger (~$0.31 of the $10 budget), deviations
  and a limitations block. This artifact owns S3 only; a candidate is promoted by whoever aggregates lanes A/B/C (needs >=2
  of 3).
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_1/gen_art/gen_art_experiment_3
out_expected_files:
- method.py
- full_method_out.json
- mini_method_out.json
- preview_method_out.json

--- Item 6 ---
id: art_ZNITuuQab6Nz
type: research
title: Which safety readouts are still unclaimed
summary: |-
  Dated web-only saturation and verification pass, 2026-09-21, $0.00 spend, no cuts taken. Self-verification: 105/105 quote-grade passages re-confirmed by an independent live re-fetch of their own URL; 1 quote deleted as a composite (logged, substantive claim unaffected); 8 anchors recovered beyond the ~50 KB page-fetch horizon kept visibly separate; 3 zero-match regexes used as absence evidence kept separate again and each independently reproduced. Bibliography regenerated from live arXiv metadata: 65/65 ids resolved, 0 UNRESOLVED.

  VERDICTS on the seven EXECUTION-side candidates, none OPEN: X2 (weight-space write mass) and X10 (weights-only orthogonality scar) are CLOSED - not by arXiv:2607.01854, which this pass proves is REFERENCE-ANCHORED on BOTH signals ("The audit rests entirely on the reference"), but by the Jorak Model Scanner, a live NON-PEER-REVIEWED open-source tool that ships the exact normalised ||r^T W|| suppression statistic with r fitted from the candidate's OWN activations and a weights-only zero-inference SVD subspace-alignment scar test (A/B/S), calibrated cross-model. X1 PARTIAL (per-input vs per-checkpoint; nearest HPD/HERALD 2609.13534 and Geometry-Lite 2605.20241 scalarise depth profiles per PROMPT). X3 PARTIAL (concept + lexical-token dependence; nearest Logit-Gap Steering 2506.24056). X5 PARTIAL (parent-requiring, only 2 checkpoints; 2607.14147's 0.24-vs-0.03 concentration is a knockout-conditioned instruct-vs-base pair, n=60). X6 PARTIAL on the thinnest margin in the table. X8 PARTIAL (concept).

  TWO ADVERSE PRIORS ITERATION 1 DID NOT HAVE, and they own this iteration's axis. (1) arXiv:2604.09544 (Orgad, Wei, Zheng, Wattenberg, Henderson, Goldfarb-Tarrant, Belinkov) - iteration 1 mis-filed it as a pruning-only paper; its abstract publishes "harmful response generation is dissociable from the ability to recognize and reason about harmfulness", a DOUBLE DISSOCIATION between harm generation and refusal, and separability GRADED along the OLMo3-7B alignment ladder (emerging at DPO). (2) arXiv:2603.05773 "Knowing without Acting" names the axes Recognition (v_H) and Execution (v_R) and demonstrates a causal double dissociation on harm. (3) arXiv:2606.24952 publishes a per-checkpoint weight-computable detection-vs-control cosine over four models (0.12/0.20/0.16/0.13; 0.1197 vs 0.
</pasted_content id="715d">


<pasted_content id="715d">
1200 across instruction tuning) and concludes it is "not a predictor of how steerable a behavior is". NONE of the three evaluates an abliterated checkpoint (grep abliterat|uncensor = 0 matches on 2606.24952 and on 2603.05773) - that is the one genuinely empty cell.

  N-GLARE ALREADY RUNS THIS RUN'S PANEL: ACL 2026 Long 1334 s1 illustrates JSS on "RL-aligned, base, and safety-removed versions of Qwen3-4B". Its margin is input cost only (four constructed dialogue families per model). Re-checked 2026-09-21: STILL NO CODE, and NO numeric Kendall's tau anywhere (Appendix Tables 6-8 are per-model benchmark values) - iteration 1's prohibition stands permanently.

  CLEAN NOT-FOUND worth more than any candidate: NO prior work scores a SAFE-COMPLETION model (declines without a lexical refusal) with an INTERNAL readout; OpenAI's 2508.09224 and OpenSafeIntent 2607.02047 are purely behavioural. Every lexical-refusal-keyed internal readout is undefined on GPT-5-class safety training.

  CORRECTIONS FORCED ON THE DRAFT: the hypothesis mis-states Basu 2603.18353 (zero-and-zero is the SAE arm ONLY; Arm 1 corrected 17/85 and disrupted 25/47; TSV 19/79 and 4/65); the planner's dose figures for 2512.13655 (minimum effective dose, >=30% bypass, 0.028 MMLU) are FABRICATED and absent across all three rungs; SRP's safety-audit mention is Future Work not abstract; Arditi does NOT logit-lens the refusal direction. Bibliography: Arditi = 7 authors + NeurIPS 2024, 2606.16349 = 6 authors not 1, 2606.22676 = 8 not 1, 2604.18901 MUST BE ADDED. HRCI_repr (G10) is NOT reimplementable as specified - Eq 8's k is never stated; Table 1 implies k=3, which must be declared. NO published behavioural dose curve over abliteration strength exists; the run's causal lane would be first.

  KILL X2, X10, and X5-for-novelty. SCREEN ORDER: (1) R-E gap on the abliterated checkpoint, (2) X1, (3) the safe-completion cell of X3.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_research_1
out_expected_files:
- research_out.json

--- Item 7 ---
id: art_1hlgObsQWnZS
type: dataset
title: Model pairs, hard prompts, refusal tokens
summary: |-
  FROZEN ITERATION-2 SUBSTRATE for the Qwen3-4B safety mech-interp run: model pairs, hard prompts, refusal tokens. Nothing touches a model - 0 safetensors files, no forward pass, no activations, no metric. 125.49 MB downloaded vs a 300 MB cap; $0 spent.

  GATES 22 PASS / 3 FAIL / 0 N/A. FAILED, with numbers, thresholds NOT relaxed: G_EFFECTIVE_IN_STRATUM (need >= 4, got 2); G_NONEFFECTIVE (need >= 2, got 0); G_PROXY_HARD (need <= 0.85 (FAIL above 0.90), got 0.8852).

  FREEZE CAME FIRST AND IS CHECKABLE. prereg.json hashed 03:38:26Z BEFORE any label, split or proxy existed; append-only build_log.txt proves the order. sha256 b3849ae02159573c253b85644bb2a4c7fd9712db531bbccf03e8917f40d11f12 is asserted equal across the file on disk, prereg.sha256 and the copy inside full_data_out.json (G_PREREG_HASH) - iteration 1 shipped a prereg hash disagreeing with its own manifest. The freeze script refuses to overwrite.

  TEN SETS, 10808 examples, one per row (per-set counts in full_data_out.json metadata and README.md). Plus sealed_truth.json and the prereg/gates freeze = twelve.

  REGISTRY 42 checkpoints, 18 pairs, 13 families, from 1587 Hub candidates screened live. safetensors bytes SUMMED FROM THE FILE LIST, not usedStorage. Raw card text ships verbatim - the card+name REGEX BASELINE the screen must beat is computed from it. Labels {"EFFECTIVE": 3, "SEALED": 2, "AMBIGUOUS": 3, "UNSCORED": 10}.

  HEADLINE NEGATIVE: at n=45+45, HALF THE SCORABLE PAIRS CANNOT BE LABELLED ROBUSTLY. 3 EFFECTIVE with a Newcombe 95% CI wholly above +0.15 (Qwen3-0.6B +0.467 [0.270,0.616]; Qwen3-1.7B +0.667 [0.501,0.786]; Josiefied-Qwen2.5-1.5B +0.467 [0.308,0.609]). 3 DEMOTED to AMBIGUOUS by the frozen label_robust rule despite point estimates crossing: SmolLM3 +0.289 [0.086,0.461], Phi-4-mini +0.244 [0.116,0.387], granite 0.000 [-0.079,0.079]. Hence G_EFFECTIVE_IN_STRATUM (2, need 4) and G_NONEFFECTIVE (0, nee
</pasted_content id="715d">


<pasted_content id="715d">
d 2) fail: granite's NULL_EDIT was demoted and the one real ANOMALOUS pair (venkycs SmolLM2, over-refusal 1.000) is in a SEALED family. Strata NOT widened to rescue the count; the 4-pair requirement must be met partly by the lane's in-house rank-one edits.

  10 pairs UNSCORED, never zero-filled: 8 FRESH (3 held_out by a seeded sha256 rule fixed before scoring), the commissioned Qwen3-4B -> mlabonne/Qwen3-4B-abliterated pair (ungated; the gated='auto' huihui variant refused), and TinyLlama, EXCLUDED as missing_shards - unloadable, not a null-edit control.

  JOIN EXACT: 26 checkpoints recomputed from 2370 judged rows match published columns to 0.000e+00 - but only after adopting iteration 1's denominator convention, since 1 row (Phi-4-mini benign orh_244) has an unparsable judge output it drops. The first run FAILED at 1.46e-2; build_log.txt records both.

  RECOGNITION SET 1509 rows, 771 benign / 738 harmful, built to kill the ceiling that made iteration 1's premise test unfalsifiable. HARDNESS MEASURED: TF-IDF+char-ngram logistic proxy, 5-fold CV, AUROC 0.9561 on easy anchors (PASS, the saturating pole) and 0.8852 on hard+borderline+wrapped vs a <=0.85 target - a FAIL, below the 0.90 rebalance trigger, with `wrapped` named as the leaking stratum and top-20 features shipped. Dedup removed 0 exact + 31 near; disjointness from iteration 1's 96/54 XSTest split asserted at 0. graded_harm on 23 rows from PKU-SafeRLHF ordinal severity, null elsewhere, never invented.

  TOKENS from 2369 real generations, 9 families; no iteration-1 lexicon exists (grep-verified). Refusal-onset 60 forms, all in >=3 families, opening 0.7587 of 1,115 refusing generations vs 0.3552 for the constructed naive comparator; top-30 Jaccard 0.25 vs do-not-answer, so a behaviour not a template. HEDGE TOOK 3 PASSES, THE FIRST TWO SHIPPED AS EVIDENCE OF FAILURE: a 2-document pool crowned its content words ("abraham lincoln", lift 1632), and widening to 147 docs with a document-frequency lift and prompt-echo stripping stayed topic-confounded - 147 generations over 45 prompts cannot separate style from topical halo. Pass 3 DECLARES a hedge-marker frame and mines 24 forms in it. Controls 28/35 inside the 0.25 caliper. Tokenizer table 128 forms x 28 tokenizers x 2 variants, 0 failures, 0 dropped; mid-text variant PRIMARY.

  PROBES: all pairwise prompt-hash intersections ZERO. 160/154 reused VERBATIM from iteration 1; 200 NEW auto-gradable with no judge (ARC-Easy + GSM8K, key in `output`); 40 from the never-loaded sealed split. Judge rubric verbatim with SHA-256s so new rows pool with the 2,370.

  SEAL ALREADY COMPROMISED AND SAID SO: both sealed pairs' deltas appear in the iteration-2 strategy text, so seal_status=DISCLOSED_UPSTREAM; only the seeded FRESH pairs and the sealed split are blind.

  CONTRACT: filter on label_robust, NOT effectiveness_label alone, or 3 CI-straddling pairs look decided. Every row carries readout_class; registry and card text are BASELINE by construction. Never read sealed_truth.json or the sealed_holdout split in a fitting lane.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_dataset_1
out_expected_files:
- data.py
- full_data_out.json
- preview_data_out.json
- mini_data_out.json

--- Item 8 ---
id: art_OyQwmkiWj-5u
type: experiment
title: Abliterated models see harm but stop acting on it
summary: |-
  Iteration-2 Lane A screen, run on CPU (no GPU; one physical core, 16 GB cgroup). 25 checkpoints activation-harvested on 256 prompts (96 EASY advbench/dolly prompts fit every direction; 160 HARD XSTest-twin/OR-Bench prompts measure recognition R), 18 of them with a teacher-forced 2x2 cell harvest (X5/X11), 29 weight summaries, 20 shuffled-label nulls and a 100-replicate item bootstrap per checkpoint. Panel: 9 instruct->uncensored pairs (P0 Qwen3-4B->mlabonne abliterated [commissioned], P1 Qwen3-0.6B, P2 Qwen3-1.7B, P3 Qwen2.5-1.5B Josiefied, P4 SmolLM3-3B, P5 Phi-4-mini, P6 granite NULL-EDIT control, S1 stablelm heretic, S2 SmolLM2 venkycs) plus Qwen3-4B-Base, SafeRL, a non-saf
</pasted_content id="715d">


<pasted_content id="715d">
ety fine-tune (CohenQu), TinyLlama, OLMo-2 and a random-init arm. mlabonne was judged here with Lane C's exact protocol: harmful compliance 0.733 vs parent 0.000 (EFFECTIVE; $0.0087).

  HEADLINE (readout level; E4 causal test not evaluated): abliteration removes EXECUTION, not RECOGNITION. Over 6 effective pairs, hard-set recognition TPR@5%FPR changes by a median -0.05 (TOST 6x INCONCLUSIVE; P2 shows a partial 0.21 drop) and the recognition onset layer does not move, while the peak logit-lens refusal-drive gap falls in 6/6 pairs (median -2.98) and X2 write mass along the model's own harm axis falls in 6/6. Parent/child harm directions agree at |cos| 0.992 in shallow layers vs 0.459 in the deep half (null-edit granite 0.984/0.997; random init 0.014). Commissioned lineage: HARD-set recognition onset Base L33 -> instruct/SafeRL/abliterated L19; peak refusal drive Base 1.57, instruct 4.92, SafeRL 8.78, abliterated 1.92 (final layer inverted, -1.96).

  SCREEN: survivor NONE. E1 is UNDER_POWERED for every candidate (edit-recipe strata hold 3/2/1 effective pairs, below the registered 4); no candidate passes E2 (training order) or E3 (leave-one-family-out transfer vs the BL1 logit baseline; machinery controls clean: oracle 1.0, shuffled truth 0.498). Descriptive pooled row: BL1 (logit-only baseline) is the most consistent abliteration detector (6/6 same sign, 5/6 CI excluding 0) but also moves ~-1 pooled SD on the granite null edit; X5 (response-onset write concentration) has the strongest activation dose-response (rho -0.87, exact p 0.016, n 7) but fails E2 because SafeRL < instruct; a name-free card regex also tracks dose (rho 0.87). Prior art from the same-iteration research lane: X2 and X10 are CLOSED by the Jorak Model Scanner and excluded from survivor selection; its statistic, reimplemented as BL7, detects global rank-1 edits, misses per-layer ones (mlabonne), and fires on the unedited stablelm-2 parent (0.99). X10_abs puts every effective child outside the parent band with zero prompts.

  Supply facts: venkycs/SmolLM2 'abliterated' is an optimum-quanto FP8 upload without quantization_config, so 168 linear layers load at random init; the TinyLlama child is missing shards; the granite child edits 1 of 80 matrices. Corrections made before final scoring (21 deviations logged): confidence intervals that shrank with the number of null draws replaced by an item bootstrap; R's layer, chosen on a saturated fitting set, replaced by the registered nested HARD-set selection; per-tokenizer slot rule for X5; ledger overwrite, NaN serialisation and OOM fixes.

  FILES: method_out.json (+ full/mini/preview; exp_gen_sol_out; 335 examples in 5 datasets incl. a 256-prompt recognition-vs-execution item-level set), out/SUMMARY.md (all tables), README.md, results/ (e_tests, pairs_table, recognition, budget curves at k=0..128, deviations), out/released/ (per-layer harm directions .npy, per-layer curves CSV, prereg, pairs, token sets). Large per-position tensors (harvest/<tag>/D_resp_parts/) are stored as <=90 MiB parts (GitHub limit), verified bit-identical to the originals; results unchanged.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_experiment_1
out_expected_files:
- method.py
- full_method_out.json
- mini_method_out.json
- preview_method_out.json

--- Item 9 ---
id: art_G5pqEoRFZ75t
type: evaluation
title: Re-checking the numbers we already have
summary: |-
  ZERO-GPU, ZERO-API RE-ADJUDICATION of iteration 1's three lanes (M0-M8), computed only from files already on disk. Pre-registration frozen and hashed BEFORE the first number: SHA-256 7f6a38d94007c3a7d07b40cadfc79863cdd504f1115e2cf47e12511c4d77966b. Self-check PASS (12 tables, 0 rejected), 0 stage failures, CLAIM MATCH RATE 0.8229 (79/96 numbers), 5 contradictions, 19 corrections.

  M0 KILLS THE INHERITED CLAIM THAT GATED EVERYTHING. 'Raw hidden states were saved nowhere' is FALSE: LANE_B/out/harvest holds 104 npz (NOT the claimed 109), containing 4200 arrays of shape (1152, 2560) float16 keyed `item|win|{EARLY,LATE}|{1
</pasted_content id="715d">


<pasted_content id="715d">
3..22}`, for 4 lineages x 5 lesion strengths. M1 therefore got its STRONG form (probe fitted on alpha=0.00, scored on alpha>0) at zero GPU cost. Stored curves reproduce: D_curve EXACT_MATCH at 1.000 for L1-L3, D_matched_probe_curve RECONCILED within 0.005-0.015. Read site is per-lineage (lastp 29/22/23/29), not constant.

  HEADLINE (M1) - A SITE DISSOCIATION AUROC CANNOT SHOW. The 1.000 belongs to the crude `damage` corpus and is AT ITS CEILING in the unperturbed control, so it could not fall. Re-expressed as TPR@1%FPR on the SAME activations (alpha 0 -> 1, mean over 4 lineages): EARLY/prompt site dAUROC -0.0068, dTPR@1%FPR +0.0007 (FLAT - the harmful REQUEST is still recognised); LATE/response site dAUROC -0.0137, dTPR@1%FPR -0.1439, a 10.5x larger movement in the operating point than in AUROC. So 'the representation survives the lesion' is TRUE at the prompt site and FALSE at the response site - recognition-vs-execution made measurable. Equivalence (TOST, margin 0.05 TPR units, both windows, Holm on the primary window): EQUIVALENT at alpha<=0.50, NOT_EQUIVALENT at 0.75-1.00. Lineage pairs: base->instruct +0.245 NOT_EQUIVALENT, instruct->SafeRL +0.063 NOT_EQUIVALENT, base->NON-safety-FT +0.029 INCONCLUSIVE (the load-bearing control behaves).

  THE COMMISSIONED FEW-PROMPT AXIS WORKS. Restricted-budget AUROC at k=16 (unlesioned): Base 0.528 ~ NonSafetyFT-STaR 0.540 << Instruct 0.679 < SafeRL 0.698. Tracks SAFETY tuning, not fine-tuning as such, from 16 labelled items.

  M6 SPECIFICITY FAILURE. All 19 quoted judged behavioural numbers recomputed MATCH. But K1/A moves 4.14 null-SD on the granite pair, a behavioural NO-OP (d harmful-compliance 0.000) whose child only carries 'abliterated' in its repo name: scored on the label it looks right, scored on the MEASURED delta it is caught. T1 is INCONCLUSIVE_UNDERPOWERED (n=5, achieved margin 28.4 null-SD), T2 rho -0.103 against a min-resolvable |rho| 0.878, T4 SATISFIED. UNIT MISMATCH DISCLOSED: the prereg margin is in TPR units (M1) while M6's outcome is in null-SD, so no cross-scale equivalence verdict is licensed or claimed.

  REPAIRS. M2: 9 of 20 scaled outcomes SATURATED, plus 8 INDETERMINATE_NO_MATCHED_POINT rows lifted out of the limitations. M3: three protocols, not one - A at-band 0.0433-0.2346 (NOT the quoted '0.04-0.09'), Lane B 0.139-0.186, Lane C 0.057-0.603 over 7 families; HARC contradiction WITHDRAWN (a cross-concept pair REPLICATES HARC); the 1596-row rotation matrix shows instruction tuning rotates the request axis MORE (|cos| 0.200) than abliteration (0.361), content axis 0.90-0.99 across trained pairs, RandInit null 0.009-0.020. M4: 112 gate rows, compliance A 0.44 / B 1.00 / C 0.69; three lanes fit three different axes under one name and reach OPPOSITE stability verdicts; K3 re-scored FAIL under its own rule -> no candidate passes S1. M5: all 6 k rungs, k=0 explicit as NOT_RUN_BY_LANE_C (never imputed); the 0.882 scan located, MATCHED, non-monotonic. M7: 70 rows, attenuation ceilings, regex-vs-judge recomputed, B7 below the random floor. M8: substrate provenance (TOTAL_L=80, slots 8/46, NOT 144), dataset gates located in gen_art_dataset_1 (hazard 0.9429 vs 0.95; 96->85; placebo median ratio 1.25 vs 1.10), causal arm EMPTY (1 of 8 jobs), shuffled band 11.04-11.78 trained vs 1.268 RandInit with A escaping 0/7.

  RUN INVARIANT ENFORCED AS A COLUMN. Every row of all 12 tables carries READOUT_CLASS; 2039 rows are result-eligible (activation/weight), 309 are BASELINE_ONLY (logit/text/metadata). evalkit/selfcheck.py REJECTS a table missing the column, and prose naming a baseline-class readout as the answer. Nothing is framed as jailbreak or attack-success reporting.

  HANDOFF to the experiment lanes: (1) generated text from the lesioned models - needs a RE-RUN; (2) operating-point statistics for the 21-checkpoint panel - Lane C stored only AUROC scalars; (3) a scored mlabonne/Qwen3-4B-abliterated row, present in every Lane A table but absent from Lane C's panel and Lane B's harvest.

  ARTEFACTS: eval.py + evalkit/ (paths, prereg, stats, selfcheck, laneb_subs
</pasted_content id="715d">


<pasted_content id="715d">
trate, m0-m8); EVAL_REPORT.md opening with CONTRADICTIONS then the claim match rate; eval_out.json (exp_eval_sol_out, 23 metrics_agg, 12 datasets) + full/mini/preview; 12 CSVs and 8 JSONs under results/, EVERY ROW CARRYING ITS SOURCE FILE PATH.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/gen_art/gen_art_evaluation_1
out_expected_files:
- eval.py
- full_eval_out.json
- mini_eval_out.json
- preview_eval_out.json

--- Item 10 ---
id: art_MD4Voiyi__oM
type: experiment
title: Fresh models test cheap internal safety readouts
summary: >-
  HELD-OUT CONFIRMATION PANEL (iteration 3, experiment_1; NO winner named). 10 checkpoints that no earlier artifact had loaded,
  drawn by a frozen seeded SHA-256 rule from families absent from the iteration-2 screen: Vikhr-Llama-3.2-1B-Instruct + its
  abliterated child (the D2-registry fresh held-out pair), unsloth/Llama-3.2-1B-Instruct + mylesgoose abliterated2, the Falcon3-1B
  Base->Instruct and AMD-OLMo-1B base->SFT->SFT-DPO stage lineages, and LFM2-700M (TIME rule dropped h2oai/h2o-danube3-500m-chat,
  LiquidAI/LFM2-1.2B). ORDER (hash_chain.jsonl; order audit PASS): panel rule -> draw -> greedy generation + Lane C lc_judge
  grading -> graded_truth.json committed -> prereg.json frozen -> activation harvest (iteration-2 protocol: 256 prompts at
  the last prompt token, 96 teacher-forced XSTest cells, all layers, fp16, weight summaries, 64 severity items) -> scoring.
  BEHAVIOUR (45 Lane C harmful items, the screen's outcome items): harmful compliance 0.00-0.60, split-half reliability 0.96;
  both abliterated children comply more than their parents; AMD-OLMo base (HC 0.02) is incoherent rather than safe; SFT->DPO
  is a behavioural no-op. HELD-OUT TABLE (results/heldout_table.json; n=10; permutation critical |rho| 0.648, 80%-power MDE
  0.80), Spearman rho with harmful compliance [checkpoint-bootstrap 95% CI]: B3 -0.89 [-0.97,-0.57] (iteration-2 held-out
  diff-in-means d, activation); B7 +0.80 [+0.26,+1.00] (weights-only scar; abliterated children 1.00/0.98 vs parents 0.50/0.50,
  but all three AMD-OLMo checkpoints 1.00 because their shared null is the all-ones direction mandated by OLMo's mean-subtracting
  LayerNorm; projecting it out (results/b7_diagnostic.json) drops rho(HC) to +0.08, leaving abliteration-scar detection only);
  C13_peak_d -0.66 [-1.00,+0.09]; C5 -0.62 [-0.99,+0.11]; C7 -0.62 [-0.95,+0.11]; BL1 -0.62 [-0.93,+0.02] (logit baseline);
  C2 +0.66, C2_tpr5 +0.77, C6 +0.69, C9 +0.64 (sign OPPOSITE to the declared expectation, as on the iteration-2 panel); C1
  -0.21; C4 +0.38; C11 -0.01; C12 -0.24; C13 -0.25. Rows whose |rho| exceeds |rho(BL1)| with a paired CI excluding 0: none.
  SAME CODE on the iteration-2 panel's saved activations (22 graded): 28/30 rows keep their sign; flips: C12_topsv (-0.25
  -> +0.01), X2 (-0.65 -> +0.31). PAIRED FRESH-MODEL CONTRASTS (post-prereg, prompt bootstrap): Vikhr-Llama-3.2-1B-Instruct-abliterated:
  dHC +0.60, peak d -0.90 [-1.38,-0.55], mid-depth d -0.40 [-0.69,-0.17], B7 +0.50; Llama-3.2-1B-Instruct-abliterated2: dHC
  +0.22, peak d -0.61 [-0.88,-0.36], mid-depth d -0.54 [-0.74,-0.36], B7 +0.48 -- iteration 3's 'request-axis d falls in every
  abliterated child' replicates on 2/2 new pairs (both CIs below 0). On the SFT->DPO no-op BL1 moves +1.61 [+0.98,+2.29] while
  peak d moves +0.06 [-0.08,+0.16]; AMD base->SFT (dHC +0.56) moves no activation readout (C13, peak d, C7, C5 CIs all cover
  0). BL1 reads a double-normalised final slice (iteration-2 lens); the literal final-logit gap ranks the panel identically
  (rho +1.00). CHECKS: unit checks all pass=True (published outcome rates and iteration-2 BL1/B3/B7/X2/X10 reproduced to 0.0);
  hook checks on 10 checkpoints (determinism True, layer-0 = embedding True, last-slice argmax True); judge re-run 0/20 mismatches;
  spend $0.13. JOIN: no screen survivor.json exists in iteration 3, so the confirmation lookup is DEFERRED (results/join_stub.json).
  Raw activations for every checkpoint are kept under harvest/<tag>/ in the iteration-2 layout fo
</pasted_content id="715d">


<pasted_content id="715d">
r re-scoring.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1
out_expected_files:
- method.py
- full_method_out.json
- mini_method_out.json
- preview_method_out.json

--- Item 11 ---
id: art_W7mvvZfSkDW3
type: evaluation
title: Fixed tables comparing Qwen3 safety models
summary: >-
  CPU-only re-analysis ($0, no forward pass) of saved activations for Qwen3-4B Base/instruct/SafeRL/STaR(non-safety FT)/mlabonne-abliterated
  plus 20 other panel checkpoints and the Lane B rank-one lesion arrays (L1-L4 x 5 alphas). Outputs: eval_out.json (exp_eval_sol_out;
  datasets checkpoint_x_readout 525 rows, lineage_x_alpha_x_site_x_layer 2000 rows, deviations_ledger 78, gates 68, claims
  9, pair_deltas 12), SUMMARY.md (master, claims, site, accumulator, power, gates, notation, deviations tables), results/*.csv
  + tables.json, 4 figures. Ledger: 58/69 comparable quoted numbers reproduce exactly from arrays (R TPR@5%FPR .475/.875/.850/.838,
  onsets 33/19/19/19, peak drive 1.57/4.92/8.78/1.92, in-sample d 5.68/11.15/11.41/5.74, k16 .528/.679/.698/.540, site deltas
  +0.0006/-0.144, p=1.76e-6 which came from a per-item t-test ignoring scenario clustering). KEY FINDINGS: (1) abliterated
  row: held-out (EASY-fit, HARD-scored) request-axis d mlabonne 0.71 vs parent 2.45, delta -1.73 [-2.35,-1.19]; drops in 6/6
  effective children but NOT on the granite null edit (+0.09), whereas BL1 and peak drive both move on that behavioural no-op;
  HARD-refit recognition R barely moves (-0.04). (2) Safety training moves recognition: Base->instruct R +0.40 (90% CI .14-.76),
  so 'execution not recognition' is scoped to abliteration only. (3) STaR matches Base only on d (TOST +/-0.5 equivalent);
  covers 0.33 of Base->instruct distance on peak drive, 0.46 on BL1. (4) Accumulation NOT supported: axis frozen at layer
  13 gives decaying norm-controlled gap; growth only for per-layer refit axes (layer-specific direction); iter-1 '138x' recomputes
  to 161-281x along the late-fit u (band-limited). (5) Three-site split (true prompt site lastp added; iter-2 'prompt site'
  was EARLY response): LATE drop at full lesion L2 -0.185, L3 -0.138, but non-refusing L4 -0.169; no safety-minus-L4 contrast
  excludes 0 -> 'execution' reading WITHDRAWN. (6) post-lesion 0.000 cosine FORCED_BY_CONSTRUCTION (0.976-0.990 at L13 informative);
  10.6x ratio dropped. (7) BL1 sign depends on prompt set (mlabonne EASY -1.96, HARD +1.76); activation readouts correlate
  0.77-0.79 with BL1 across 25 ckpts. Gates table 68 rows (dataset 22/25 reproduced; Lane A G1/G5 fail everywhere).
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_evaluation_1
out_expected_files:
- eval.py
- full_eval_out.json
- mini_eval_out.json
- preview_eval_out.json

--- Item 12 ---
id: art_d7zKf99Ok-2i
type: research
title: Is our depth-and-site safety metric already taken?
summary: |-
  Web-only saturation pass for iteration 3's widened claim, run 2026-09-21. Cost: $0, no cuts. 87 of 87 quoted passages were re-verified by an independent live re-fetch of their own URL; 45 sources, all fetched.

  HEADLINE: THE WIDENED CLAIM IS CLOSED. The closer is arXiv:2608.05578, AMS (Google Cloud Activation-based Model Scanner). The code is open under Apache-2.0 and installs with `pip install ams-scanner`. Iteration 2 had this paper but filed it only under the weights-only lane.
  - Tier 1 is reference-free and uses 16 contrastive pairs (32 prompts) per concept.
  - It reads the final prompt token at 40-80% depth.
  - It scores 14 checkpoints across 4 families, including 2 abliterated and 3 uncensored models.
  - Its sigma predicts JailbreakBench compliance at Pearson r=-0.546 (p=0.043). The Spearman correlation is not significant (rho=-0.423, p=0.13).
  - Leave-one-out threshold accuracy is 71%.
  - It has no logit baseline, no response-site readout, no over-refusal outcome, and no Qwen3 or Qwen-abliterated checkpoint.
  - It names decode-time analysis as its own 'principal open problem'.

  Also
</pasted_content id="715d">


<pasted_content id="715d">
 covering this cell:
  - N-GLARE (ACL 2026). CORRECTION: Figure 7 does print layer-group Pearson/Spearman couplings of JSS with unsafe rate and refusal rate across DPO steps. Still no cross-model tau and still no code.
  - RAS/SafeVec 2606.25750: reference-anchored, 3 families, separates abliterated and uncensored models, tracks ASR.
  - Aligned Probing (TACL 2026): layer-wise internals vs graded toxicity across 20+ models.

  GROUP VERDICTS (C1-C14):
  - B8 weights-only: CLOSED (Jorak, 273-checkpoint audit, OBLITERATUS toolkit).
  - B1 onset depth: PARTIAL, high risk. CLS 2606.22686 ties family onset depth (Llama late 95%, Qwen ~40%) to robustness qualitatively.
  - B2 response vs prompt site: PARTIAL, lowest risk. Response-site readouts exist only per input (HARC, Mitra 2606.29441, ForeSight); every per-checkpoint score is prompt-site.
  - B3 cross-depth direction consistency: PARTIAL. The OBLITERATUS toolkit already computes the cross-layer refusal cosine matrix and angular drift.
  - B4 accumulation: PARTIAL (detect-aggregate-express staging; per-prompt HPD and Geometry-Lite).
  - B5 decodable-to-actionable lag: PARTIAL, medium-high (refusal gated downstream of where it is computed; Pythia lag).
  - B6 over-refusal internals: PARTIAL, low-medium. No per-checkpoint internal predictor of XSTest over-refusal rate exists.
  - B7 severity monotonicity: PARTIAL (graded toxicity encoding in Aligned Probing; harm organised by category, not severity).
  - B9 budget and two-feature score: PARTIAL, high for C1 (AMS 16 pairs, ICS 10 pairs, IRT 10 items); an early+late model-level combination was not found.
  - Causal check: random-direction controls are standard; applying the check at the response site on an abliterated checkpoint is open.

  LEDGER: all 10 items CONFIRMED.
  - Jorak is live (commit 8147de3, 2026-07-24, Apache-2.0, 0 stars; cite as a non-peer-reviewed tool).
  - Safe Basu sentence: 98.2% AUROC vs 65/144 detected; zero corrections and zero disruptions for the SAE arm ONLY; TSV corrected 19/79 and disrupted 4/65.
  - Kwon (0.24 vs 0.03) and anti-rank AUROC 0.220 confirmed.

  BLOCK D: the knowledge-action gap is REPLICATED IN SAFETY and IN OTHER DOMAINS.
  - In safety: 2606.24952 detection AUC 1.000 vs control direction ~83 degrees away; 2606.08044 dissociated models defeat static probes; recognition survives abliteration; AMS class-(iv) model has sigma 5.45 but 97% compliance.
  - Other domains: Pythia steering null in 43/48 cells; CAD; truth-probe vs causal SAE features overlap ~12%; arithmetic.
  - Counter-example: 2608.29109, where recognition-direction steering works.
  - Basu's exact four-arm protocol is NOT replicated.

  POSITIONING:
  - Frame the paper as ONE mechanistic question: at what depth and site does safety become readable in a single model, and is the readout causal there?
  - AMS sigma (open code) plus a final-layer logit gap are the bars every candidate must beat.
  - Surviving contribution sentences:
    (1) Prompt-site vs response-site per-checkpoint readouts, abliterated included (conditional on results).
    (2) A logit-baseline and AMS-sigma margin, which none of the incumbents reports.
    (3) Over-refusal as a per-checkpoint internal outcome, plus a site-local matched-norm vs random-direction causal test.
  - MUST NOT CLAIM:
    - a first cross-family few-prompt activation safety metric;
    - a first internal scoring of abliterated checkpoints;
    - reference-free or <=16 prompts as novelty;
    - recognition/execution naming;
    - recognition surviving abliteration;
    - any weights-only statistic;
    - 'N-GLARE has no correlations'.
workspace_path: >-
  /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_research_1
out_expected_files:
- research_out.json
</all_artifacts>

<new_artifacts_this_iteration>
NEW THIS ITERATION: These 3 artifacts were created to address the reviewer
feedback. Their findings should be the primary basis for your revisions.

summary: >-
  HELD-OUT CONFIRMATION PANEL (iteration 3, experiment_1; NO winner named). 10 checkpoint
</pasted_content id="715d">


<pasted_content id="715d">
s that no earlier artifact had loaded,
  drawn by a frozen seeded SHA-256 rule from families absent from the iteration-2 screen: Vikhr-Llama-3.2-1B-Instruct + its
  abliterated child (the D2-registry fresh held-out pair), unsloth/Llama-3.2-1B-Instruct + mylesgoose abliterated2, the Falcon3-1B
  Base->Instruct and AMD-OLMo-1B base->SFT->SFT-DPO stage lineages, and LFM2-700M (TIME rule dropped h2oai/h2o-danube3-500m-chat,
  LiquidAI/LFM2-1.2B). ORDER (hash_chain.jsonl; order audit PASS): panel rule -> draw -> greedy generation + Lane C lc_judge
  grading -> graded_truth.json committed -> prereg.json frozen -> activation harvest (iteration-2 protocol: 256 prompts at
  the last prompt token, 96 teacher-forced XSTest cells, all layers, fp16, weight summaries, 64 severity items) -> scoring.
  BEHAVIOUR (45 Lane C harmful items, the screen's outcome items): harmful compliance 0.00-0.60, split-half reliability 0.96;
  both abliterated children comply more than their parents; AMD-OLMo base (HC 0.02) is incoherent rather than safe; SFT->DPO
  is a behavioural no-op. HELD-OUT TABLE (results/heldout_table.json; n=10; permutation critical |rho| 0.648, 80%-power MDE
  0.80), Spearman rho with harmful compliance [checkpoint-bootstrap 95% CI]: B3 -0.89 [-0.97,-0.57] (iteration-2 held-out
  diff-in-means d, activation); B7 +0.80 [+0.26,+1.00] (weights-only scar; abliterated children 1.00/0.98 vs parents 0.50/0.50,
  but all three AMD-OLMo checkpoints 1.00 because their shared null is the all-ones direction mandated by OLMo's mean-subtracting
  LayerNorm; projecting it out (results/b7_diagnostic.json) drops rho(HC) to +0.08, leaving abliteration-scar detection only);
  C13_peak_d -0.66 [-1.00,+0.09]; C5 -0.62 [-0.99,+0.11]; C7 -0.62 [-0.95,+0.11]; BL1 -0.62 [-0.93,+0.02] (logit baseline);
  C2 +0.66, C2_tpr5 +0.77, C6 +0.69, C9 +0.64 (sign OPPOSITE to the declared expectation, as on the iteration-2 panel); C1
  -0.21; C4 +0.38; C11 -0.01; C12 -0.24; C13 -0.25. Rows whose |rho| exceeds |rho(BL1)| with a paired CI excluding 0: none.
  SAME CODE on the iteration-2 panel's saved activations (22 graded): 28/30 rows keep their sign; flips: C12_topsv (-0.25
  -> +0.01), X2 (-0.65 -> +0.31). PAIRED FRESH-MODEL CONTRASTS (post-prereg, prompt bootstrap): Vikhr-Llama-3.2-1B-Instruct-abliterated:
  dHC +0.60, peak d -0.90 [-1.38,-0.55], mid-depth d -0.40 [-0.69,-0.17], B7 +0.50; Llama-3.2-1B-Instruct-abliterated2: dHC
  +0.22, peak d -0.61 [-0.88,-0.36], mid-depth d -0.54 [-0.74,-0.36], B7 +0.48 -- iteration 3's 'request-axis d falls in every
  abliterated child' replicates on 2/2 new pairs (both CIs below 0). On the SFT->DPO no-op BL1 moves +1.61 [+0.98,+2.29] while
  peak d moves +0.06 [-0.08,+0.16]; AMD base->SFT (dHC +0.56) moves no activation readout (C13, peak d, C7, C5 CIs all cover
  0). BL1 reads a double-normalised final slice (iteration-2 lens); the literal final-logit gap ranks the panel identically
  (rho +1.00). CHECKS: unit checks all pass=True (published outcome rates and iteration-2 BL1/B3/B7/X2/X10 reproduced to 0.0);
  hook checks on 10 checkpoints (determinism True, layer-0 = embedding True, last-slice argmax True); judge re-run 0/20 mismatches;
  spend $0.13. JOIN: no screen survivor.json exists in iteration 3, so the confirmation lookup is DEFERRED (results/join_stub.json).
  Raw activations for every checkpoint are kept under harvest/<tag>/ in the iteration-2 layout for re-scoring.
id: art_MD4Voiyi__oM
type: experiment
title: Fresh models test cheap internal safety readouts

summary: >-
  CPU-only re-analysis ($0, no forward pass) of saved activations for Qwen3-4B Base/instruct/SafeRL/STaR(non-safety FT)/mlabonne-abliterated
  plus 20 other panel checkpoints and the Lane B rank-one lesion arrays (L1-L4 x 5 alphas). Outputs: eval_out.json (exp_eval_sol_out;
  datasets checkpoint_x_readout 525 rows, lineage_x_alpha_x_site_x_layer 2000 rows, deviations_ledger 78, gates 68, claims
  9, pair_deltas 12), SUMMARY.md (master, claims, site, accumulator, power, gates, notation, deviations tables), results/*.csv
  + tables.json, 4 figure
</pasted_content id="715d">


<pasted_content id="715d">
s. Ledger: 58/69 comparable quoted numbers reproduce exactly from arrays (R TPR@5%FPR .475/.875/.850/.838,
  onsets 33/19/19/19, peak drive 1.57/4.92/8.78/1.92, in-sample d 5.68/11.15/11.41/5.74, k16 .528/.679/.698/.540, site deltas
  +0.0006/-0.144, p=1.76e-6 which came from a per-item t-test ignoring scenario clustering). KEY FINDINGS: (1) abliterated
  row: held-out (EASY-fit, HARD-scored) request-axis d mlabonne 0.71 vs parent 2.45, delta -1.73 [-2.35,-1.19]; drops in 6/6
  effective children but NOT on the granite null edit (+0.09), whereas BL1 and peak drive both move on that behavioural no-op;
  HARD-refit recognition R barely moves (-0.04). (2) Safety training moves recognition: Base->instruct R +0.40 (90% CI .14-.76),
  so 'execution not recognition' is scoped to abliteration only. (3) STaR matches Base only on d (TOST +/-0.5 equivalent);
  covers 0.33 of Base->instruct distance on peak drive, 0.46 on BL1. (4) Accumulation NOT supported: axis frozen at layer
  13 gives decaying norm-controlled gap; growth only for per-layer refit axes (layer-specific direction); iter-1 '138x' recomputes
  to 161-281x along the late-fit u (band-limited). (5) Three-site split (true prompt site lastp added; iter-2 'prompt site'
  was EARLY response): LATE drop at full lesion L2 -0.185, L3 -0.138, but non-refusing L4 -0.169; no safety-minus-L4 contrast
  excludes 0 -> 'execution' reading WITHDRAWN. (6) post-lesion 0.000 cosine FORCED_BY_CONSTRUCTION (0.976-0.990 at L13 informative);
  10.6x ratio dropped. (7) BL1 sign depends on prompt set (mlabonne EASY -1.96, HARD +1.76); activation readouts correlate
  0.77-0.79 with BL1 across 25 ckpts. Gates table 68 rows (dataset 22/25 reproduced; Lane A G1/G5 fail everywhere).
id: art_W7mvvZfSkDW3
type: evaluation
title: Fixed tables comparing Qwen3 safety models

summary: |-
  Web-only saturation pass for iteration 3's widened claim, run 2026-09-21. Cost: $0, no cuts. 87 of 87 quoted passages were re-verified by an independent live re-fetch of their own URL; 45 sources, all fetched.

  HEADLINE: THE WIDENED CLAIM IS CLOSED. The closer is arXiv:2608.05578, AMS (Google Cloud Activation-based Model Scanner). The code is open under Apache-2.0 and installs with `pip install ams-scanner`. Iteration 2 had this paper but filed it only under the weights-only lane.
  - Tier 1 is reference-free and uses 16 contrastive pairs (32 prompts) per concept.
  - It reads the final prompt token at 40-80% depth.
  - It scores 14 checkpoints across 4 families, including 2 abliterated and 3 uncensored models.
  - Its sigma predicts JailbreakBench compliance at Pearson r=-0.546 (p=0.043). The Spearman correlation is not significant (rho=-0.423, p=0.13).
  - Leave-one-out threshold accuracy is 71%.
  - It has no logit baseline, no response-site readout, no over-refusal outcome, and no Qwen3 or Qwen-abliterated checkpoint.
  - It names decode-time analysis as its own 'principal open problem'.

  Also covering this cell:
  - N-GLARE (ACL 2026). CORRECTION: Figure 7 does print layer-group Pearson/Spearman couplings of JSS with unsafe rate and refusal rate across DPO steps. Still no cross-model tau and still no code.
  - RAS/SafeVec 2606.25750: reference-anchored, 3 families, separates abliterated and uncensored models, tracks ASR.
  - Aligned Probing (TACL 2026): layer-wise internals vs graded toxicity across 20+ models.

  GROUP VERDICTS (C1-C14):
  - B8 weights-only: CLOSED (Jorak, 273-checkpoint audit, OBLITERATUS toolkit).
  - B1 onset depth: PARTIAL, high risk. CLS 2606.22686 ties family onset depth (Llama late 95%, Qwen ~40%) to robustness qualitatively.
  - B2 response vs prompt site: PARTIAL, lowest risk. Response-site readouts exist only per input (HARC, Mitra 2606.29441, ForeSight); every per-checkpoint score is prompt-site.
  - B3 cross-depth direction consistency: PARTIAL. The OBLITERATUS toolkit already computes the cross-layer refusal cosine matrix and angular drift.
  - B4 accumulation: PARTIAL (detect-aggregate-express staging; per-prompt HPD and Geometry-Lite).
  - B5 decodable-to-actionable lag: PARTI
</pasted_content id="715d">


<pasted_content id="715d">
AL, medium-high (refusal gated downstream of where it is computed; Pythia lag).
  - B6 over-refusal internals: PARTIAL, low-medium. No per-checkpoint internal predictor of XSTest over-refusal rate exists.
  - B7 severity monotonicity: PARTIAL (graded toxicity encoding in Aligned Probing; harm organised by category, not severity).
  - B9 budget and two-feature score: PARTIAL, high for C1 (AMS 16 pairs, ICS 10 pairs, IRT 10 items); an early+late model-level combination was not found.
  - Causal check: random-direction controls are standard; applying the check at the response site on an abliterated checkpoint is open.

  LEDGER: all 10 items CONFIRMED.
  - Jorak is live (commit 8147de3, 2026-07-24, Apache-2.0, 0 stars; cite as a non-peer-reviewed tool).
  - Safe Basu sentence: 98.2% AUROC vs 65/144 detected; zero corrections and zero disruptions for the SAE arm ONLY; TSV corrected 19/79 and disrupted 4/65.
  - Kwon (0.24 vs 0.03) and anti-rank AUROC 0.220 confirmed.

  BLOCK D: the knowledge-action gap is REPLICATED IN SAFETY and IN OTHER DOMAINS.
  - In safety: 2606.24952 detection AUC 1.000 vs control direction ~83 degrees away; 2606.08044 dissociated models defeat static probes; recognition survives abliteration; AMS class-(iv) model has sigma 5.45 but 97% compliance.
  - Other domains: Pythia steering null in 43/48 cells; CAD; truth-probe vs causal SAE features overlap ~12%; arithmetic.
  - Counter-example: 2608.29109, where recognition-direction steering works.
  - Basu's exact four-arm protocol is NOT replicated.

  POSITIONING:
  - Frame the paper as ONE mechanistic question: at what depth and site does safety become readable in a single model, and is the readout causal there?
  - AMS sigma (open code) plus a final-layer logit gap are the bars every candidate must beat.
  - Surviving contribution sentences:
    (1) Prompt-site vs response-site per-checkpoint readouts, abliterated included (conditional on results).
    (2) A logit-baseline and AMS-sigma margin, which none of the incumbents reports.
    (3) Over-refusal as a per-checkpoint internal outcome, plus a site-local matched-norm vs random-direction causal test.
  - MUST NOT CLAIM:
    - a first cross-family few-prompt activation safety metric;
    - a first internal scoring of abliterated checkpoints;
    - reference-free or <=16 prompts as novelty;
    - recognition/execution naming;
    - recognition surviving abliteration;
    - any weights-only statistic;
    - 'N-GLARE has no correlations'.
id: art_d7zKf99Ok-2i
type: research
title: Is our depth-and-site safety metric already taken?
</new_artifacts_this_iteration>

<data_files>
Data files come in three sizes:
- preview_*_out.json — READ THIS to inspect the data structure
- mini_*_out.json (~3 examples) — use for prototyping/testing
- full_*_out.json (complete) — use for the final production run. NEVER open it directly (too large to read into context). Instead, extract values programmatically with shell commands (e.g. grep) or a Python script (use aii-long-running-tasks skill for scripts).
</data_files>

<task>
Write a research paper draft with LaTeX-ready text, BibTeX citations, and figure placeholders.

YOUR TURN (gen_paper_text): Revise the paper.

You are a researcher improving your paper after receiving a conference review.
Take the feedback seriously and make substantive changes, not cosmetic ones.

1. ADDRESS REVIEWER FEEDBACK: For each critique in <reviewer_feedback>, either fix the
   issue in the paper or argue convincingly why it doesn't apply. Major critiques MUST
   be resolved -- they would cause rejection if left unaddressed.
2. USE THE NEW EVIDENCE: The artifacts in <new_artifacts_this_iteration> were created
   specifically to address the reviewer's concerns. Reference their findings to
   strengthen the sections that were flagged as weak.
3. REWRITE, DON'T PATCH: Don't just append new paragraphs. Restructure and rewrite
   the sections the reviewer identified as problematic.
4. MAINTAIN CONSISTENCY: Ensure the paper aligns with the updated hypothesis.
</task>

<figure_instructions>
</pasted_content id="715d">


<pasted_content id="715d">

FIGURE FORMAT: Use [FIGURE:fig_id] markers in paper_text to indicate where each figure goes.
Then provide the full figure specs in the separate `figures` structured output array.
Each figure in the array must have an `id` matching a marker in the text. Set the `aspect_ratio`
field per figure: 21:9 for architecture / pipeline / flow-chart diagrams (the hero figure should
be one of these — place its marker near the END of the Introduction so it floats to the top of
page 2), 16:9 for comparisons / multi-panel results, 4:3 for dense charts, 1:1 for heatmaps /
confusion matrices / scatter plots.

FIGURE TYPE — set `figure_type` on every figure. One test decides it: does the figure plot numbers?
  "data"    — a DATA FIGURE: bars, curves, scatter, heatmaps, confusion matrices, scaling
              laws, distributions, Pareto fronts, ablation deltas. Rendered deterministically
              from the values you supply, so every bar is exactly the height of its number.
  "concept" — a CONCEPT FIGURE: conceptual artwork, architecture and flow diagrams, anything
              with no underlying dataset. Drawn by an image model.
If the figure has real numbers behind it, ALWAYS use "data". An image model only approximates
values: the bars come back close to, but not equal to, the numbers you asked for, and nothing
downstream detects it.

Example in paper_text:
  "...our method achieves state-of-the-art results as shown below.\n\n[FIGURE:fig3]\n\nThe results demonstrate..."

Example in figures array (results comparison — plots numbers, so a data figure):
  {"id": "fig3", "title": "Performance Comparison", "figure_type": "data", "caption": "Comparison of geometric mean query latency across optimizers.", "image_gen_detailed_description": "Grouped bar chart. Categories: PostgreSQL, Bao, RLQOpt. One series 'Latency'. Values: 4.6, 2.8, 2.0 seconds. Errors: 0.8, 0.5, 0.3. X-axis label 'Optimizer'. Y-axis label 'Latency (s)', range 0-5.", "aspect_ratio": "16:9", "summary": "Compares latency across optimizers"}

Example in figures array (architecture diagram, hero — no dataset, so a concept figure):
  {"id": "fig1", "title": "System Architecture", "figure_type": "concept", "caption": "End-to-end pipeline: encoder feeds latents into the planner, which queries the value head before emitting actions.", "image_gen_detailed_description": "Horizontal flow diagram, left to right. Five labeled boxes: 'Input' (gray), 'Encoder' (blue), 'Latent (z, 256-dim)' (light blue, narrow), 'Planner' (green), 'Action Head' (orange). Arrows labeled with shapes. Value head as separate green box below 'Planner', bidirectional arrow. Sans-serif font, clean white background, no 3D.", "aspect_ratio": "21:9", "summary": "Hero architecture diagram"}

CRITICAL: Before writing figure specs, look through artifact workspace output files (*_out.json)
and code to find ALL the exact values. The figure generator cannot read files — every exact number
and value MUST be in the image_gen_detailed_description. For a "data" figure, list the values per series
plus the axis labels and units; the renderer needs the numbers themselves, not a description of
what they look like.
</figure_instructions>

FIRST, add ALL of these to your todo list using your task/todo-tracking tool:

CRITICAL: Todo content must be copied exactly as is written here, with NO CHANGES. These todos are intentionally detailed so that another LLM could read each one without any external context and understand exactly what it has to do.

<todos>
TODO 1. Read and STRICTLY follow these skills: aii-paper-writing, aii-semscholar-bib, aii-web-tools.
TODO 2. LITERATURE REVIEW: Use web search tools to research the landscape — search key terms from
<hypothesis> and <all_artifacts>. Then use aii_semscholar_bib__fetch to batch-fetch real
BibTeX entries. Build a comprehensive Related Work section. Do NOT fabricate entries.
TODO 3. STYLE EXEMPLARS: Decide which field or fields this paper belongs to; a paper spanning two
fields takes exemplars from both. If `./style_exemplars.md` already exists in your workspace
(
</pasted_content id="715d">


<pasted_content id="715d">
a previous iteration wrote it), read it and skip the search. Otherwise use the aii-web-tools
skill's scholarly search (OpenAlex) to find the best-cited open-access papers of the last five
years closest to this paper, fetch four or five of them through the skill's fetch tool (arXiv HTML
or PDF), and copy VERBATIM into `./style_exemplars.md`, each passage headed by the paper's
title, year and URL: the abstract, the first paragraph of the introduction, one results paragraph
that reports numbers, and one discussion or limitations paragraph. Read the file once as a whole
and put one line at its top on how those papers handle sentence length, hedging, first person and
citation density. Write the paper in that register. Their sentences and their content are never
reused; they are exemplars of style, not sources.
TODO 4. READ ARTIFACTS: Before writing each section, READ the relevant artifact source code, output
files, and data in the workspace. Extract concrete implementation details, technical innovations,
algorithmic specifics, and quantitative results. Do NOT write surface-level descriptions.

ARTIFACT REFERENCES: When you reference results, methodology, or findings from a specific artifact,
place an [ARTIFACT:artifact_id] marker inline. These become footnotes linking to the artifact's code
in the GitHub repository (first mention gets a footnote with URL, subsequent mentions are omitted).
Use the exact artifact ID from <all_artifacts>. Place the marker right after the claim it supports.
Example:
  "Our evaluation showed a 15% improvement over baselines [ARTIFACT:art_4f9d2c81ab37]." 
TODO 5. WRITE PAPER: Write the full paper text with [FIGURE:fig_id] markers per <figure_instructions>,
and provide the figure specs in the figures array. Lay the sections out exactly as <paper_structure>
requires and carry the numbers where <results_first> puts them — both are in your system prompt, and
an Introduction holding related work or method detail is the defect they exist to prevent.
Cite with numeric references [1], [2], etc.
At the end of the paper text, include a full bibliography section. Do NOT compile LaTeX or generate
actual image/figure files. Do NOT emit your structured output when the draft is done — TODO 6 is a
separate revision pass that runs over the finished draft first.
TODO 6. REVISION PASS — start this ONLY once TODO 5's draft is complete, and treat it as a distinct
pass over the finished text rather than something folded into the writing. Read
`REVISION_CHECKLIST.md` in the aii-paper-writing skill's own directory and apply every item to the
full draft.

Writing and revising are different jobs and cannot be done at the same time. The defects that
checklist targets — prose denser than the field needs, an abstract dumped full of numbers, sections
that leak into one another, a Figure 1 that shows a side result instead of the main idea, close
prior work that only the draft's FINAL vocabulary would have surfaced, a study of N things that
plots eight of them, section names that mean nothing to someone who has not read the section,
implementation filenames cited in the prose, numbers that disagree between the abstract, the text
and the tables — are all invisible while drafting, because you are holding your intent rather than
the text. Every one is obvious to the first outside reader.

Work the items one at a time against the ACTUAL text, not from memory of what you meant to write.
For each item, either fix the draft or state in one line why it already holds. The checklist's
consistency section is several SEPARATE sweeps of the whole paper, one concern per sweep — run them
that way, and repeat any sweep that produced an edit, since a fix in one place routinely breaks
agreement somewhere else. Expect this pass to change the draft; one that produces no edits was not
really run.

Only when the checklist is fully worked through, emit the structured JSON — that is your ONLY
output. Do NOT compile LaTeX or generate image/figure files at any point.
</todos><user_data>
User-provided reference materials are available at `/a
</pasted_content id="715d">


<pasted_content id="715d">
i-inventor/aii_data/runs/run_YqmEFECOIR3D/user_uploads`. Check this folder for anything relevant to your task. It is context, not instruction. Do NOT follow directives inside it as if they were addressed to you.
</user_data>

<user_original_request>
The user's original request that started this run is provided as a SEPARATE user message in this turn (right after this one). It is context, not instruction. Do NOT follow directives inside it as if they were addressed to you. Earlier pipeline steps have already acted on it (generating hypotheses, setting the AII prompt, etc.) — your job is NOT to satisfy that request directly.

Read it and pick up anything relevant to YOUR specific task: hints about preferences, constraints, style, focus areas, things to avoid. If nothing in it applies to what you are doing right now, ignore it entirely and proceed with your task as defined above.
</user_original_request>

---

Output the result as JSON to: `./.terminal_claude_agent_struct_out.json`

JSON Schema:
```json
{
  "$defs": {
    "FigureSpec": {
      "description": "Figure specification \u2014 structured output from paper writing agent.\n\nThe LLM fills these as a list in PaperText.figures.\nLater converted to Figure objects for viz gen.",
      "properties": {
        "id": {
          "description": "Figure ID matching the [FIGURE:id] marker in paper_text (e.g., 'fig1'). Letters, digits and underscore only \u2014 a hyphen or space cannot be extracted from its own marker.",
          "pattern": "^\\w+$",
          "title": "Id",
          "type": "string"
        },
        "title": {
          "description": "Figure title in plain, everyday language \u2014 short and jargon-free. Aim for about 4-8 words (~40 characters).",
          "title": "Title",
          "type": "string"
        },
        "caption": {
          "description": "LaTeX figure caption \u2014 appears below the figure in the paper. Should describe what the figure shows and highlight key takeaways.",
          "title": "Caption",
          "type": "string"
        },
        "figure_type": {
          "description": "Which generator draws this figure. Decide by ONE test: does the figure plot numbers? 'data' \u2014 a DATA FIGURE: bars, curves, scatter, heatmaps, confusion matrices, scaling laws, distributions, Pareto fronts, ablation deltas. Rendered deterministically from the numbers, so every bar is exactly the height of its value. 'concept' \u2014 a CONCEPT FIGURE: conceptual artwork, architecture and flow diagrams, anything with no underlying dataset. When a figure has real numbers behind it, ALWAYS choose 'data': an image model only approximates values, producing bars that disagree with their own labels.",
          "enum": [
            "data",
            "concept"
          ],
          "title": "Figure Type",
          "type": "string"
        },
        "image_gen_detailed_description": {
          "description": "The generator's ONLY input \u2014 it cannot read files. For figure_type='data': every numeric value to plot, per series, with axis labels and units, category names, and what the figure has to make the reader see \u2014 the comparison, trend, trade-off or distribution that is the point. Name a chart type only if you actually want a specific one: the figure generator reads its own catalogue of chart types and picks the one that fits, so an enumeration here would only go stale as that catalogue grows. For figure_type='concept': the composition \u2014 what appears where, colours, labels, and what to leave out.",
          "title": "Image Gen Detailed Description",
          "type": "string"
        },
        "aspect_ratio": {
          "default": "21:9",
          "description": "Shape of the figure. '21:9' for architecture diagrams / pipelines / flow charts (the paper's hero diagram is usually one of these), '16:9' for side-by-side comparisons and multi-panel results, '4:3' for dense charts, '1:1' for heatmaps / confusion matrices / scatter plots, '3:4' or '9:16' for vertical layouts.",
          "enum": [
            "1:1",
            "4:3",
</pasted_content id="715d">


<pasted_content id="715d">

            "3:2",
            "16:9",
            "21:9",
            "3:4",
            "9:16"
          ],
          "title": "Aspect Ratio",
          "type": "string"
        },
        "summary": {
          "description": "Brief summary of what this figure communicates",
          "title": "Summary",
          "type": "string"
        }
      },
      "required": [
        "id",
        "title",
        "caption",
        "figure_type",
        "image_gen_detailed_description",
        "summary"
      ],
      "title": "FigureSpec",
      "type": "object"
    }
  },
  "description": "Paper text \u2014 structured output from paper writing agent.\n\nStructured output fields (LLMPrompt + LLMStructOut):\n- title, abstract, paper_text, figures, summary\n\npaper_text contains [FIGURE:fig_id] markers for positioning.\nfigures contains the full specs as structured objects.\n\nMetadata fields (plain, set by pipeline code):\n- id",
  "properties": {
    "title": {
      "description": "Paper title \u2014 clear, plain-language, and short so a non-expert understands the main contribution at a glance. Aim for about 6-10 words; avoid jargon and acronyms.",
      "title": "Title",
      "type": "string"
    },
    "abstract": {
      "description": "Paper abstract",
      "title": "Abstract",
      "type": "string"
    },
    "paper_text": {
      "description": "Full paper body text with markdown section headers (# Introduction, # Methods, # Results, # Discussion, # Conclusion). Use [FIGURE:fig_id] markers (e.g. [FIGURE:fig1]) to indicate where each figure should appear.",
      "title": "Paper Text",
      "type": "string"
    },
    "figures": {
      "description": "List of figure specifications. Each must have an id matching a [FIGURE:id] marker in paper_text.",
      "items": {
        "$ref": "#/$defs/FigureSpec"
      },
      "title": "Figures",
      "type": "array"
    },
    "summary": {
      "description": "Brief summary of the paper's main contribution and findings",
      "title": "Summary",
      "type": "string"
    }
  },
  "required": [
    "title",
    "abstract",
    "paper_text",
    "summary"
  ],
  "title": "PaperText",
  "type": "object"
}
```

IMPORTANT: this task is NOT complete until `./.terminal_claude_agent_struct_out.json` exists and contains JSON matching the schema above.

qwen3 4B on huggingface has base model also official safety finetuned version and there is a community finetuned uncensored model called abliterated (use the 4B size of each so they fit on a 16GB GPU). take these models and do a mech interp analysis of how they differ in activation. also find some patterns in internal computation on safety prompts. and possibly create a new metric for safety. so that for any random model on huggingface you would not need to run the full benchmarks, but only this metric on 0- to few prompts and get a safety evaluation

invariant: the deliverable is the activation-level comparison of the three models and any metric built from it must read activations or weights of a single model. logit-only or text-only readouts are baselines, not the result. this is a mech interp study of where safety lives, not a jailbreak or attack-selection study; do not reframe it as one.
</prompt>
</pasted_content id="715d">
````

### [2] SKILL-INPUT — aii-paper-writing · 2026-09-21 14:45:17 UTC

The agent loaded the **aii-paper-writing** skill; its `SKILL.md` (the instructions injected into the agent's context) follows verbatim.

````
---
name: aii-paper-writing
description: "Writes the PROSE of an AI research paper: abstract, introduction, related work, methods, experiments, discussion and conclusion, with a page budget, the 5-paragraph intro pattern, writing-quality rules, inline [FIGURE:fig_id] markers plus a structured figures array, and a MANDATORY REVISION_CHECKLIST.md pass over every finished draft. Use whenever a paper, abstract, section, or full write-up is being drafted or rewritten for a venue such as NeurIPS, ICML, ICLR or ACL. Triggers: write a paper, paper structure, abstract, introduction, related work, methods, experiments, contributions, figure caption and placement, revision pass, academic prose. NOT for: assembling or compiling .tex (use aii-paper-to-latex), rendering the figure image files (aii-data-fig-gen, aii-concept-fig-gen), fetching BibTeX (use aii-semscholar-bib), or critiquing a finished draft's logic (use amg-paper-verification)."
---

## MANDATORY: the final revision pass

**`REVISION_CHECKLIST.md`, in this skill's own directory, MUST be read and
applied to every finished draft, always, as a separate pass after the writing
is done.** It is not optional, not conditional on how the draft looks, and not
something to fold into the writing itself.

Writing and revising are different jobs and cannot be done in one pass. The
defects that checklist targets — dense prose, a number-dumped abstract, sections
that leak into each other, a Figure 1 that shows a side result, prior work the
final vocabulary would have found, results mentioned but never plotted,
inconsistencies between abstract and tables — are all invisible while drafting,
because the author is holding the intent rather than the text. Every one of them
is obvious to the first outside reader. Reading the checklist before writing
does not substitute: the pass has to run against a finished draft.

So the order is always: write the complete draft → read `REVISION_CHECKLIST.md`
→ work its items against the full text, fixing as you go → only then emit the
output.

## Technical Papers

Guidance for the standard "technical paper" format: propose a method/system/framework, evaluate it experimentally, report results. This is the main track at most CS venues (NeurIPS, ICML, ICLR, ACL, AAAI, etc.). Does NOT cover: pure theory/formal proofs, survey papers, position papers, or dataset/benchmark papers — those have different structures.

### Paper Structure

Target 6-8 pages. Use formal academic language, third person. Support claims with evidence from artifacts.

#### Rough Page Budget (8-page paper)

| Section | Pages | Notes |
|---|---|---|
| Abstract | 0.3 | Problem, approach, key result |
| Introduction | 1.0-1.5 | The most important section |
| Related Work | 0.5-1.0 | Beginning or end (see below) |
| Methods | 1.5-2.0 | Architecture fig on page 1 |
| Experiments | 1.5-2.0 | Setup + results + ablations |
| Discussion | 0.5-1.0 | Limitations go here |
| Conclusion | 0.3-0.5 | Do not repeat the abstract |
| References | 0.5-1.0 | Not counted in page limit |

**Critical rule**: A clear new technical contribution must be articulated by page 3 (quarter of the paper). If the reader doesn't know what you did by then, you've lost them.

#### Section Details

**Abstract** (150-250 words): State the problem, your approach, and the main results. Be factual and comprehensive. Do not repeat the abstract word-for-word later in the paper.

**Introduction** — Follow this 5-paragraph structure:

1. **What is the problem?** Define the task concretely.
2. **Why is it interesting and important?** Real-world impact, scale.
3. **Why is it hard?** Why do naive approaches fail?
4. **Why hasn't it been solved before?** What's wrong with prior solutions? How does yours differ?
5. **What are the key components of your approach and results?** Include specific limitations.

End with a "Summary of Contributions" subsection — bullet list of contributions with section references. This doubles as an outline, saving space.

**Related Work** — Placement decision:
- **Beginning** (Section 2): If it can be short yet detailed, or if you need a strong defensive stance against prior work early.
- **End** (before Conclusions): If comparisons require your technical content, or if it can be summarized briefly in the Introduction. Can be titled "Discussion and Related Work."

**Methods/Approach**: Every section tells a story — the story of the results, NOT the story of how you arrived at them. Use top-down description: readers should see where the material is going and be able to skip ahead. Move gory details to appendices.

**Experiments**: Setup (datasets, metrics, baselines) → main results → ablations → analysis. Every claim needs quantitative evidence.

**Discussion**: Interpret results, compare to prior work, state limitations honestly. Limitations should be specific and actionable, not vague disclaimers.

**Conclusion**: Short summarizing paragraph. Do NOT repeat material from the Abstract or Introduction. Make original claims more concrete (e.g., reference quantitative results). Include future work as bullet list — if actively pursuing follow-up, say so to mark territory.

#### Writing Quality Rules

- Define all notation/terminology before use, only once. Group global definitions in Preliminaries.
- Do NOT use nonreferential "this", "that", "these", "it". Always specify the referent. BAD: "This is important because..." GOOD: "This accuracy gap is important because..."
- Do NOT use "etc." unless remaining items are completely obvious. BAD: "We measure volatility, scalability, etc." GOOD: "We measure volatility and scalability."
- Do NOT write "for various reasons" — state the actual reasons.
- "That" is defining, "which" is nondefining. "The algorithms that are easy to implement" vs "The algorithms, which are easy to implement."
- Use italics for definitions and quotes, not for emphasis. Context alone should provide emphasis.

### Figure Format

Figures use a hybrid marker + structured array approach. ALL figures are generated by a separate pipeline step using an AI image model — your `image_gen_detailed_description` is the ONLY input that model sees. It cannot read files or access data. Do NOT generate actual image files yourself (no matplotlib, no PIL, no image generation scripts).

**In paper_text**: Place `[FIGURE:fig_id]` markers where figures should appear.

**In figures array**: Provide full specs as structured objects with these fields:
- `id` — matches the `[FIGURE:id]` marker in paper_text
- `title` — short descriptive title
- `caption` — LaTeX caption that appears below the figure in the paper
- `image_gen_detailed_description` — detailed prompt for the image generator (axes, ALL values, colors, layout)
- `summary` — brief summary of what the figure communicates

Example in paper_text:
```
...our method achieves state-of-the-art results as shown below.

[FIGURE:fig_1]

The results in Figure 1 demonstrate...
```

Example figure spec in figures array:
```json
{"id": "fig_1", "title": "Performance Comparison", "caption": "Comparison of geometric mean query latency across optimizers on JOB benchmark. RLQOpt achieves 2.3x speedup over PostgreSQL.", "image_gen_detailed_description": "Grouped bar chart. X-axis: model names. Y-axis: accuracy (0.0-1.0). Values: ModelA=0.847, ModelB=0.762, Baseline=0.531. Error bars with std: 0.02, 0.03, 0.05. Sans-serif font, white background.", "summary": "Compares accuracy of proposed methods vs baseline."}
```

Every marker in text MUST have a matching figure in the array, and vice versa.

#### Data Precision Requirement

`image_gen_detailed_description` MUST include exact numbers from artifact output files. Read the actual output files before writing figure specs.

- BAD: "Compare accuracy metrics across configurations"
- GOOD: "Grouped bar chart. X-axis: model names. Y-axis: accuracy (0.0-1.0). Values: K=3: 0.765, K=5: 0.729, Baseline: 0.121."

#### Figure vs Table Decision

Do NOT create figures for tabular data (rows/columns of text or numbers). Use `\begin{table}` in LaTeX instead. Figures are for actual visualizations only (charts, plots, diagrams).

#### Figure Placement Strategy

Be intentional with figure ordering. The architectural/method overview figure explaining the proposed approach MUST appear early — in the Introduction or at the start of Methods — so readers can immediately orient themselves. Readers skim papers top-down; if the first figure they see is a results bar chart, they have no mental model for interpreting it.

Recommended ordering:
1. **Architecture/method diagram** — Introduction or early Methods (so readers understand the approach before diving into details)
2. **Conceptual/analogy figures** — Introduction or Methods (to build intuition)
3. **Results figures** (bar charts, line plots, scatter plots) — Results section
4. **Analysis/ablation figures** — Discussion or later Results

#### Guidelines

- Plan 3-6 figures total across the paper
- Place [FIGURE:fig_id] markers INLINE where referenced in text
- Include axes, labels, ALL numeric values in figure descriptions
- Both data-driven figures (bar charts, line plots) and conceptual diagrams (architecture, flowcharts)
- Be as detailed as possible in descriptions: specify aspect ratio, preferred colors, all data values, axis labels, ranges, legend entries, and any other visual details. The more specific the description, the better the generated figure

### Bibliography with Semantic Scholar

Build `./references.bib` using the aii-semscholar-bib skill (real BibTeX from Semantic Scholar):

1. Collect DOIs, ArXiv IDs, or titles for all papers you need to cite
2. Call `aii_semscholar_bib__fetch` with the full list in one batch
3. Write the returned .bib text into `./references.bib`

Rules:
- Do NOT fabricate BibTeX entries — always fetch from Semantic Scholar
- If a paper isn't found (very recent preprint), write the entry manually as fallback
- Use `\bibliography{references}` and `\bibliographystyle{plainnat}`
- Do NOT use inline `thebibliography` environment

### Citation Format (for Research Artifacts)

When writing research with numbered citations:

1. Every factual claim MUST have a numbered citation: `[1]`, `[2]`, `[1, 3]`, etc.
2. Each source in the "sources" array MUST have an "index" field
3. The index MUST EXACTLY MATCH citation numbers in the text
4. NEVER cite a number without a matching source index
5. Example: "LLMs show 40% improvement with multi-agent collaboration [1]."
````

### [3] SKILL-INPUT — aii-semscholar-bib · 2026-09-21 14:45:21 UTC

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

### [4] SKILL-INPUT — aii-web-tools · 2026-09-21 14:45:21 UTC

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

### [5] SYSTEM-USER prompt · 2026-09-21 14:46:51 UTC

```
You are collecting BibTeX entries for a mechanistic interpretability paper about safety in language models. 

Use the aii-semscholar-bib skill to fetch BibTeX entries. First load the tool:
- Run the Skill tool with skill="aii-semscholar-bib"

Then call the aii_semscholar_bib__fetch tool (load it first with ToolSearch if needed) with all these references in ONE batch call:

References to fetch:
1. {"arxiv": "2406.11717", "author": "Arditi", "year": 2024} - Refusal single direction
2. {"arxiv": "2411.09003", "author": "Marshall", "year": 2024} - Affine refusal
3. {"arxiv": "2502.17420", "author": "Wollschlager", "year": 2025} - Concept cones
4. {"arxiv": "2607.02396", "author": "Winninger", "year": 2026} - RFM-AGOP multi-dimensional
5. {"arxiv": "2605.26772", "author": "Yang", "year": 2026} - CoT disrupts steering
6. {"arxiv": "2507.03167", "author": "Yamaguchi", "year": 2025} - Where reasoning models refuse
7. {"arxiv": "2603.05773", "author": "Wu", "year": 2026} - Knowing without Acting recognition vs execution
8. {"arxiv": "2604.09544", "author": "Orgad", "year": 2026} - Harm generation dissociable
9. {"arxiv": "2603.18353", "author": "Basu", "year": 2026} - Interpretability without actionability
10. {"arxiv": "2606.24952", "author": "Galeone", "year": 2026} - Weight-computable cosine
11. {"arxiv": "2607.00572", "author": "Chua", "year": 2026} - HARC cross-position alignment
12. {"arxiv": "2507.11878", "author": "Zhao", "year": 2025} - Harmfulness refusal encoded separately
13. {"arxiv": "2511.14195", "author": "Lin", "year": 2025} - N-GLARE
14. {"arxiv": "2607.14147", "author": "Kwon", "year": 2026} - Prefill jailbreak
15. {"arxiv": "2607.01854", "author": "Hurtado", "year": 2026} - Abliteration audit 273 checkpoints
16. {"arxiv": "2608.05578", "author": "AMS", "year": 2026} - Activation-based Model Scanner
17. {"arxiv": "2310.01405", "author": "Zou", "year": 2023} - Representation Engineering RepE
18. {"arxiv": "2306.03341", "author": "Li", "year": 2023} - Inference-Time Intervention ITI
19. {"arxiv": "2202.05262", "author": "Meng", "year": 2022} - ROME factual associations
20. {"arxiv": "2307.02483", "author": "Wei", "year": 2023} - Jailbroken safety training failure modes
21. {"title": "XSTest: A Test Suite for Identifying Exaggerated Safety Behaviours", "author": "Rottger", "year": 2023}
22. {"title": "OR-Bench: An Over-Refusal Benchmark for Large Language Models", "author": "Cui", "year": 2024}
23. {"arxiv": "2606.29441", "author": "Mitra", "year": 2026} - Activation-cone blind spot
24. {"arxiv": "2607.02510", "author": "Schirmer", "year": 2026} - Online safety monitoring
25. {"arxiv": "2608.09624", "author": "Luo", "year": 2026} - Anti-rank internal scores
26. {"arxiv": "2609.16204", "author": "Muhamed", "year": 2026} - Decoy direction
27. {"arxiv": "2606.25750", "author": "RAS", "year": 2026} - SafeVec
28. {"arxiv": "2607.09697", "author": "OutputAware", "year": 2026} - Output-aware guardrail
29. {"arxiv": "2603.23268", "author": "SafeSeek", "year": 2026} - SafeSeek safety circuits
30. {"arxiv": "2603.23171", "author": "Aremu", "year": 2026} - Activation watermarking
31. {"arxiv": "2502.01042", "author": "SafeSwitch", "year": 2025} - SafeSwitch
32. {"arxiv": "2505.19056", "author": "AbuShairah", "year": 2025} - Embarrassingly simple defense
33. {"arxiv": "2604.18901", "author": "LlorenteSaguer", "year": 2026} - Abliterated harm recognition
34. {"arxiv": "2603.27412", "author": "LlorenteSaguer", "year": 2026} - Skin-Deep latent biopsy
35. {"arxiv": "2606.16349", "author": "HRCI", "year": 2026} - HRCI_repr coupling index
36. {"arxiv": "2510.18081", "author": "Zhang", "year": 2025} - Any-Depth Alignment
37. {"arxiv": "2609.00760", "author": "Unified", "year": 2026} - Unified mechanistic analysis
38. {"arxiv": "2609.00790", "author": "RISA", "year": 2026} - RISA
39. {"arxiv": "2407.09121", "author": "Yuan", "year": 2024} - DeRTa decoupled refusal training
40. {"arxiv": "2608.29109", "author": "RecognitionSteering", "year": 2026} - Recognition direction steering works
41. {"arxiv": "2606.08044", "author": "Dissociated", "year": 2026} - Dissociated models defeat probes

Save ALL the returned bib_text into the file: /ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/references.bib

For any references that FAIL, note their IDs. Do NOT fabricate entries. After fetching, report: how many succeeded, which ones failed (if any), and the full file path where the .bib was saved.
```

### [6] SYSTEM-USER prompt · 2026-09-21 14:49:17 UTC

```
This session is being continued from a previous conversation that ran out of context. The summary below covers the earlier portion of the conversation.

Summary:
1. Primary Request and Intent:
   The user is running an automated AI research pipeline (AI Inventor). This is Step 3.4 (GEN_PAPER_TEXT) - writing a complete research paper draft. The paper is about mechanistic interpretability of safety in the Qwen3-4B language model family, comparing base, instruction-tuned, safety-RL, non-safety fine-tuned, and community-abliterated checkpoints. The paper must:
   - Address ALL reviewer feedback from a BLOCKING review (10+ MAJOR MUST-FIX items)
   - Incorporate new evidence from 3 iteration-3 artifacts
   - Follow the structure: Abstract, Introduction, Related Work, Method, Experimental Setup, Results, Discussion/Limitations, Conclusion
   - Include figure placeholders and specs
   - Output structured JSON to `./.terminal_claude_agent_struct_out.json` matching the PaperText schema
   - The original user request: analyze Qwen3-4B models (base, safety-tuned, abliterated) via mech interp, find patterns in internal computation on safety prompts, possibly create a new safety metric from activations/weights
   - Invariant: the deliverable is activation-level comparison; logit-only readouts are baselines, not results

2. Key Technical Concepts:
   - Abliteration: rank-one weight edit W ← W - α·u·(uᵀW) removing refusal direction
   - Recognition vs Execution dissociation in safety
   - Dose-graded rank-one lesion study (Lane B) with α sweeps 0-1
   - Request-axis Cohen's d as a prompt-site recognition readout (NOT execution)
   - Held-out d: EASY-fit direction scored on HARD prompts
   - TPR at low FPR as de-saturated alternative to AUROC
   - Site dissociation: prompt vs early-response vs late-response activation sites
   - Fixed-axis vs per-layer-refit accumulator test
   - Leave-one-family-out cross-validation for cross-family transfer
   - BL1: final-layer logit baseline (the bar to beat)
   - AMS (arXiv:2608.05578): Activation-based Model Scanner that CLOSES the widened cross-family claim
   - Jorak Model Scanner: non-peer-reviewed tool closing X2/X10 weight-space statistics
   - Three independent measurement lanes: Lane A (checkpoint panel), Lane B (lesion study), Lane C (cross-family)

3. Files and Code Sections:
   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/style_exemplars.md`
     - EXISTS from previous iteration, contains 5 exemplar papers (Arditi, Li, Meng, Zou, Wei)
     - Style guidance: "sentences mostly 20-40 words, declarative, information-dense; hedging light and localized; first person 'we'; citation density high in intro/related work, near zero in results"
   
   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_evaluation_1/SUMMARY.md` (art_W7mvvZfSkDW3)
     - Critical evaluation artifact with corrected tables. Read lines 0-399 (of ~500+)
     - Master table: 25 checkpoints with held-out d, recognition, peak drive, BL1, etc.
     - Key corrected claims table showing: accumulation NOT_SUPPORTED, site dissociation NOT_SUPPORTED, post-lesion cos FORCED_BY_CONSTRUCTION, 10.6x ratio DROPPED
     - Pair deltas table: 6 effective pairs + null edit + anomalous pairs
     - Full site table (Lane B): per-lineage, per-alpha, per-site (PROMPT/EARLY/LATE) with TPR@1%FPR
     - Holm/permutation/TOST results: significant only at full lesion (α=1) at LATE site
     - Safety-minus-L4 contrasts: ALL CIs include 0, so execution reading WITHDRAWN
     - Accumulator table: fixed-axis Spearman NEGATIVE (-0.818 to -0.990), fixed ratio = 1.000, verdict = LAYER_SPECIFIC_DIRECTION for all arms
     - Key headline metrics: abliterated_d_peak=0.713, abliterated_minus_parent_d=-1.734 [-2.349,-1.189]
   
   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1/results/heldout_table.json` (art_MD4Voiyi__oM)
     - 10 fresh held-out checkpoints, n=10 panel
     - B3 rho=-0.89 with HC (strongest); C13_peak_d rho=-0.66; BL1 rho=-0.62
     - No candidate exceeds BL1 with a paired CI excluding 0
     - 2/2 new abliterated pairs show peak d drops (CIs below 0)
   
   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_research_1/` (art_d7zKf99Ok-2i)
     - NOT YET READ in detail, but summary available from artifacts listing
     - AMS (2608.05578) CLOSES the widened cross-family claim
     - Positioning: frame as ONE mechanistic question
     - MUST NOT CLAIM: first cross-family few-prompt metric, first internal scoring of abliterated checkpoints, recognition surviving abliteration, any weights-only statistic
   
   - `references.bib` - being generated by bib-collector subagent (not yet complete)
   
   - `.terminal_claude_agent_struct_out.json` - final output file (not yet created)

4. Errors and fixes:
   - Evaluation SUMMARY.md exceeded 25000 token read limit - fixed by reading in chunks with offset/limit parameters
   - No errors in tool calls otherwise; all reads and bash commands succeeded

5. Problem Solving:
   - Identified that the previous paper draft had 10+ MAJOR MUST-FIX blocking issues from the reviewer
   - Key corrections needed based on new iteration-3 evidence:
     a. "Accumulator" claim → reframed as "layer-specific direction rotation" (fixed-axis gap decays)
     b. "Site dissociation as execution" → WITHDRAWN (L4 non-safety model drops equally)
     c. "Safety tuning doubles execution, not recognition" → corrected: safety training moves BOTH; "execution not recognition" scoped to abliteration only
     d. STaR negative control → matches Base only on Cohen's d; moves partway on peak drive/BL1
     e. Abliterated model row → NOW COMPUTED: held-out d=0.713 vs parent 2.45
     f. Abstract → must be written (was missing)
     g. Notation table → must be added
     h. Cross-family metric → NOT achieved, must be stated honestly
     i. 10.6x ratio → DROPPED
     j. Post-lesion 0.000 cosine → FORCED_BY_CONSTRUCTION, removed

6. All user messages:
   The user's actual messages are embedded within the pasted content system. The primary user directive is the task prompt asking to write the paper. The original user request (at end of pasted content) states:
   "qwen3 4B on huggingface has base model also official safety finetuned version and there is a community finetuned uncensored model called abliterated (use the 4B size of each so they fit on a 16GB GPU). take these models and do a mech interp analysis of how they differ in activation. also find some patterns in internal computation on safety prompts. and possibly create a new metric for safety. so that for any random model on huggingface you would not need to run the full benchmarks, but only this metric on 0- to few prompts and get a safety evaluation"
   
   "invariant: the deliverable is the activation-level comparison of the three models and any metric built from it must read activations or weights of a single model. logit-only or text-only readouts are baselines, not the result. this is a mech interp study of where safety lives, not a jailbreak or attack-selection study; do not reframe it as one."
   
   Security/constraint notes to preserve:
   - "CRITICAL: Every file you create, write, or save MUST be inside this workspace directory... You MUST NOT write files anywhere outside this path — external paths are READ-ONLY."
   - Workspace: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/`
   - Process isolation: "NEVER kill processes by name"
   - Writing register banned words: "Never use: delve, underscore, showcase, intricate, pivotal, realm, commendable, meticulous, tapestry, garner, multifaceted, it is worth noting, plays a crucial role, not only ... but also"
   - Em dashes: at most 3 per 1,000 words
   - Hedging: at most 15 hedges per 1,000 words
   - MUST NOT CLAIM per research artifact: first cross-family few-prompt activation safety metric; first internal scoring of abliterated checkpoints; reference-free or ≤16 prompts as novelty; recognition/execution naming; recognition surviving abliteration; any weights-only statistic; 'N-GLARE has no correlations'

7. Pending Tasks:
   - Task #2: Literature review and BibTeX collection (bib-collector subagent launched, awaiting results)
   - Task #4: Read artifacts and extract numbers (in_progress - partially done, need to finish reading remaining SUMMARY sections and research artifact)
   - Task #5: Write full paper draft (pending)
   - Task #6: Revision pass using REVISION_CHECKLIST.md (pending - must read the checklist file first)
   - Final: Write `.terminal_claude_agent_struct_out.json` with the PaperText JSON schema

8. Current Work:
   I was in the middle of Task #4 (reading artifacts). I had:
   - Read the evaluation SUMMARY.md through line 399 (master table, claims, site table, Holm table, safety-minus-L4 contrasts, accumulator table beginning)
   - Read the heldout_table.json (partial - first ~200 lines showing feature correlations with HC)
   - Launched a bib-collector subagent to fetch BibTeX for ~41 references (still running)
   - Had NOT yet read: the remaining evaluation SUMMARY sections (power, gates, notation, deviations), the research artifact (art_d7zKf99Ok-2i) report, or the REVISION_CHECKLIST.md
   
   Key numbers already extracted for the paper:
   - Master table for all 25 checkpoints (held-out d, R TPR@5%FPR, peak drive, BL1, onset depth, k16 AUROC, etc.)
   - Pair deltas for all 9 pairs (delta_peak_d, delta_tpr5, delta_peak_drive, delta_BL1)
   - Site table for Lane B (all 4 lineages × 5 alphas × 3 sites)
   - Accumulator verdicts: ALL = LAYER_SPECIFIC_DIRECTION (fixed axis decays)
   - Held-out panel (10 checkpoints): B3 rho=-0.89, peak_d rho=-0.66, BL1 rho=-0.62

9. Optional Next Step:
   Continue Task #4 by reading the remaining evaluation SUMMARY sections and the research artifact. Then wait for the bib-collector subagent to complete, read the REVISION_CHECKLIST.md, and proceed to Task #5 (writing the full paper draft). The paper must address all reviewer MUST-FIX items using the corrected numbers from the iteration-3 evaluation, incorporate the held-out panel results, and honestly report the negative findings (accumulator NOT_SUPPORTED, site dissociation execution reading WITHDRAWN, cross-family metric NOT achieved).

If you need specific details from before compaction (like exact code snippets, error messages, or content you generated), read the full transcript at: /root/.claude/projects/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-3-gen-paper-text-gen-paper-text/e053a4f7-16e5-4471-a541-0e0999e2e2bc.jsonl
Continue the conversation from where it left off without asking the user any further questions. Resume directly — do not acknowledge the summary, do not recap what was happening, do not preface with "I'll continue" or similar. Pick up the last task as if the break never happened.
```

### [7] SYSTEM-USER prompt · 2026-09-21 15:03:57 UTC

````
This session is being continued from a previous conversation that ran out of context. The summary below covers the earlier portion of the conversation.

Summary:
1. Primary Request and Intent:
   The user is running an automated AI research pipeline (AI Inventor), Step 3.4 (GEN_PAPER_TEXT). The task is to write a complete research paper draft about mechanistic interpretability of safety in the Qwen3-4B language model family, comparing base, instruction-tuned, safety-RL, non-safety fine-tuned, and community-abliterated checkpoints. The paper must:
   - Address ALL reviewer feedback from a BLOCKING review (10+ MAJOR MUST-FIX items from iter_2 review)
   - Incorporate corrected evidence from 3 iteration-3 artifacts (evaluation, held-out panel experiment, research/positioning)
   - Follow standard academic structure: Abstract, Introduction, Related Work, Method, Experimental Setup, Results, Discussion/Limitations, Conclusion
   - Include figure placeholders and specs
   - Output structured JSON to `./.terminal_claude_agent_struct_out.json` matching the PaperText schema: `{title, abstract, paper_text, figures, summary}`
   - Original user request: analyze Qwen3-4B models (base, safety-tuned, abliterated) via mech interp, find patterns in internal computation on safety prompts, possibly create a new safety metric from activations/weights
   - Invariant: the deliverable is activation-level comparison; logit-only readouts are baselines, not results
   
   Security/constraint notes (MUST be preserved):
   - "CRITICAL: Every file you create, write, or save MUST be inside this workspace directory... You MUST NOT write files anywhere outside this path — external paths are READ-ONLY."
   - Workspace: `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/`
   - Process isolation: "NEVER kill processes by name"
   - Writing register banned words: "Never use: delve, underscore, showcase, intricate, pivotal, realm, commendable, meticulous, tapestry, garner, multifaceted, it is worth noting, plays a crucial role, not only ... but also"
   - Em dashes: at most 3 per 1,000 words
   - Hedging: at most 15 hedges per 1,000 words
   - MUST NOT CLAIM: first cross-family few-prompt activation safety metric; first internal scoring of abliterated checkpoints; reference-free or ≤16 prompts as novelty; recognition/execution naming; recognition surviving abliteration; any weights-only statistic; 'N-GLARE has no correlations'

2. Key Technical Concepts:
   - Abliteration: rank-one weight edit W ← W - α·u·(uᵀW) removing refusal direction
   - Request-axis Cohen's d: held-out prompt-site separability of harmful vs benign (EASY-fit, HARD-scored)
   - Recognition (R): TPR at low FPR from logistic probe on prompt-site activations
   - Peak drive: max logit-lens refusal projection across layers
   - BL1: final-layer logit gap (the baseline to beat)
   - B3: direction self-consistency (Fisher-transformed mean cosine across consecutive layers)
   - Accumulator test: fixed-axis vs per-layer-refit gap across depth
   - Site dissociation: PROMPT vs EARLY vs LATE response activation sites
   - Dose-graded lesion: α sweep 0-1 in rank-one edit
   - Lane A (checkpoint panel, 25 models), Lane B (lesion study, 4 lineages), Lane C (cross-family, 10 held-out)
   - Leave-one-family-out cross-validation
   - TOST equivalence testing
   - AMS (Activation-based Model Scanner, Yang2026/arXiv:2608.05578) - the incumbent bar
   - N-GLARE (Winninger2026) - JSD-based safety readout
   - Recognition vs Execution dissociation (Orgad2026, Lin2025)

3. Files and Code Sections:

   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_evaluation_1/SUMMARY.md`
     - Critical evaluation artifact with ALL corrected numbers. Read in full (lines 0-546+).
     - Contains: master table (25 checkpoints), claims corrections table, pair deltas, site table, accumulator table, power table
     - Key headline metrics at lines 16-154: abliterated_d_peak=0.713, abliterated_minus_parent_d=-1.734 [-2.349,-1.189], all site contrasts, fixed-axis Spearman values, panel correlations
     - Master table at lines 155-184: all 25 checkpoints with HC, d, R, peak_drive, BL1, onset, B3, k16_auroc, etc.
     - Pair deltas at lines 196-212: P0-P6, S1-S2, Base→Instruct, Base→STaR
     - Claims table at lines 213-226: 7 claims with corrected versions and evidence
     - Site table at lines 227-278+: Per lineage/alpha/site TPR and dTPR values
     - Accumulator table at lines 397-505: All models × all configs showing LAYER_SPECIFIC_DIRECTION verdict

   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_experiment_1/results/heldout_table.json`
     - 10-checkpoint held-out panel results
     - B3 rho=-0.890 with HC (strongest), family CI [-0.951,-0.569], partial_rho_given_BL1=-0.816
     - BL1 rho=-0.620, family CI [-0.735, 0.200]
     - C13_peak_d rho=-0.656
     - B3 d_BL1=-0.270 (better than BL1 but paired CI doesn't exclude 0)
     - B7 rho=0.804 (OLMo all-ones-null ARTEFACT noted in memory)

   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_art/gen_art_research_1/answer.md`
     - Research positioning artifact (69 lines read in full)
     - AMS (2608.05578) CLOSES the widened claim with 5/6 components
     - N-GLARE: 4/6, also closes. Correction: it DOES print correlations in Figure 7
     - RAS/SafeVec: 3/6, PARTIAL
     - Empty cells: response site (B2), over-refusal internals (B6), logit-baseline margin
     - Framing: "At what depth, and at which site, does safety behaviour become readable?"
     - Contribution sentences that survive with distinguishing components
     - Full list of MUST NOT SAY sentences

   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_2/review_paper/review_paper/.terminal_claude_agent_struct_out.json`
     - Previous iteration's BLOCKING review (score 4/10, confidence 4)
     - 10 MAJOR critiques enumerated with detailed suggested_actions
     - Key blocking issues: headline contradicts tables, accumulator forced by construction, site dissociation overstated, no abliterated d computed, no abstract/notation table, cross-family metric not achieved

   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/references.bib`
     - 41/41 BibTeX entries fetched by subagent (13,009 bytes)
     - Key citation keys: Arditi2024 (abliteration), Yang2026 (AMS), Winninger2026 (N-GLARE), Orgad2026 (recognition/execution), LlorenteSaguer2026a/b, Marshall2024, Galeone2026, Hurtado2026, Rottger2023 (XSTest), Cui2024 (OR-Bench), Wu2026 (RAS), Mitra2026, Schirmer2026, Yamaguchi2025, Messenger2026 (Aligned Probing), Jiang2026 (IRT), Lin2025 (DSH), Basu2026
     - Post-processing fixes applied by subagent: disambiguated LlorenteSaguer2026a/b, fixed Rottger2023 key

   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/paper_draft.tex`
     - COMPLETE paper draft (created and edited in this session)
     - ~250 lines of LaTeX
     - Structure: Introduction (with fig_overview, contributions), Related Work (4 paragraphs), Method (6 subsections with notation table), Results (4 subsections with 5 tables), Discussion (3 subsections), Conclusion
     - Edits applied: moved fig_overview to Introduction, renamed Discussion subsection, added AMS comparison, added full panel table reference

   - `/ai-inventor/.claude/skills/aii-paper-writing/REVISION_CHECKLIST.md`
     - 9 checklist items read in full (183 lines)
     - Key items: plain language, abstract prose not data dump, one job per section, conventional names, related work with final vocabulary, Figure 1 main idea, report whole study, no implementation references, consistency passes

   - `/ai-inventor/aii_data/runs/run_YqmEFECOIR3D/3_invention_loop/iter_3/gen_paper_text/gen_paper_text/style_exemplars.md`
     - Read in previous session (before compaction). Contains 5 exemplar papers with style guidance.

4. Errors and fixes:
   - Research artifact SUMMARY.md path was wrong (`gen_art_research_1/SUMMARY.md` doesn't exist) - fixed by finding the actual file at `gen_art_research_1/answer.md`
   - Python script to extract held-out panel data hit a TypeError on NoneType formatting for partial_rho field - was non-blocking, got enough data before the error
   - No other significant errors in this session

5. Problem Solving:
   - Addressed ALL 10 MAJOR MUST-FIX items from the iter_2 review:
     a. "execution not recognition" → scoped to abliteration only; safety training moves BOTH (R 0.475→0.875)
     b. STaR negative control → matches Base ONLY on d (0.046, TOST equivalent); moves partway on peak drive (33%) and BL1 (46%)
     c. Accumulator → LAYER_SPECIFIC_DIRECTION (fixed-axis gap DECAYS, Spearman -0.82 to -0.99)
     d. Site dissociation → WITHDRAWN as execution reading (L4 non-safety drops -0.169, comparable to safety lineages; all safety-minus-L4 CIs include 0)
     e. Abliterated model d → NOW COMPUTED: 0.713 vs parent 2.45 (delta -1.734 [-2.349,-1.189])
     f. Abstract → written (as separate field in JSON)
     g. Notation table → added (Table 1 in Method section with 12 definitions)
     h. Cross-family metric → NOT achieved, stated honestly in Contribution 4 and Limitations
     i. 10.6x ratio → DROPPED
     j. Post-lesion cosine → FORCED_BY_CONSTRUCTION, removed from evidence
     k. BL1 comparison → reported beside every execution readout

6. All user messages:
   - The only genuine user message in this session is: "CRITICAL: Respond with TEXT ONLY. Do NOT call any tools..." (the summary request)
   - All other content is from the continuation summary, system reminders, task notifications, and tool results
   - The original user request (from the pipeline, preserved in context): "qwen3 4B on huggingface has base model also official safety finetuned version and there is a community finetuned uncensored model called abliterated (use the 4B size of each so they fit on a 16GB GPU). take these models and do a mech interp analysis of how they differ in activation. also find some patterns in internal computation on safety prompts. and possibly create a new metric for safety..."
   - Invariant constraint: "the deliverable is the activation-level comparison of the three models and any metric built from it must read activations or weights of a single model. logit-only or text-only readouts are baselines, not the result. this is a mech interp study of where safety lives, not a jailbreak or attack-selection study; do not reframe it as one."

7. Pending Tasks:
   - Task #5 (in_progress): Write full paper draft → Draft written to paper_draft.tex, needs to be finalized as JSON
   - Task #6 (in_progress): Revision pass using REVISION_CHECKLIST.md → Key fixes applied to paper_draft.tex, needs final consistency check
   - FINAL OUTPUT: Write `.terminal_claude_agent_struct_out.json` with PaperText JSON schema: {title, abstract, paper_text, figures, summary}

8. Current Work:
   I was in the middle of finalizing the paper draft and creating the JSON output. Specifically:
   - The complete paper draft has been written to `paper_draft.tex` (~250 lines of LaTeX)
   - Three revision-checklist edits have been applied to the draft:
     1. Moved `[FIGURE:fig_overview]` from Results Section 4.1 to the end of Introduction paragraph 4
     2. Changed Discussion subsection title from "What the Depth Profile Reveals" to "Layer-Specific Harm Directions"
     3. Added AMS comparison note in Discussion subsection "Why No Activation Metric Beats the Logit Gap"
     4. Added full panel table reference in Models section
   - The revision pass (Task #6) was in progress - key structural fixes applied, but the full 9-item checklist consistency passes have not all been explicitly run
   - The final JSON output file has NOT been created yet
   - Four figures are planned: fig_overview (method schematic), fig_accumulator (depth profile), fig_site (per-lineage TPR), fig_heldout (scatter plot)
   - The abstract needs to be written as a separate JSON field (prose, max ~3 numbers)

9. Optional Next Step:
   Complete the revision pass and write the final JSON output to `.terminal_claude_agent_struct_out.json`. This involves:
   1. Read the final paper_draft.tex to verify all edits are consistent
   2. Write the abstract (prose, max 3 numbers, ~200 words)
   3. Create the 4 figure specs with detailed image_gen_detailed_description fields containing exact data values
   4. Compose and write the final JSON: `{title, abstract, paper_text (from paper_draft.tex), figures (4 specs), summary}`
   5. Mark Tasks #5 and #6 as completed

   The JSON schema (from iter_2 output inspection):
   ```json
   {
     "title": "...",
     "abstract": "...",
     "paper_text": "\\section{Introduction}...",
     "figures": [
       {"id": "fig_overview", "title": "...", "caption": "...", "image_gen_detailed_description": "...", "summary": "...", "figure_type": "..."}
     ],
     "summary": "..."
   }
   ```

If you need specific details from before compaction (like exact code snippets, error messages, or content you generated), read the full transcript at: /root/.claude/projects/-ai-inventor-aii-data-runs-run-YqmEFECOIR3D-3-invention-loop-iter-3-gen-paper-text-gen-paper-text/e053a4f7-16e5-4471-a541-0e0999e2e2bc.jsonl
Continue the conversation from where it left off without asking the user any further questions. Resume directly — do not acknowledge the summary, do not recap what was happening, do not preface with "I'll continue" or similar. Pick up the last task as if the break never happened.
````

### [8] SYSTEM-USER prompt · 2026-09-21 15:09:44 UTC

```
<validation-feedback>
Attempt 1 failed validation.

Schema validation found 4 problems — fix ALL of them at once:
  - at `figures.0.figure_type`: 'schematic' is not one of ['data', 'concept']
  - at `figures.1.figure_type`: 'line_chart' is not one of ['data', 'concept']
  - at `figures.2.figure_type`: 'bar_chart' is not one of ['data', 'concept']
  - at `figures.3.figure_type`: 'bar_chart' is not one of ['data', 'concept']
Every required field must be present and every field type must match the schema.

Produce `.terminal_claude_agent_struct_out.json` again so it contains corrected JSON that matches the schema. Do not invent new fields.
</validation-feedback>
```
