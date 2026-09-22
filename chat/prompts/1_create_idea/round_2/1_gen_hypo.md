# gen_hypo_1 — create_idea

> Phase: `hypo_loop` · round 2 · `gen_hypo`
> Run: `run_YqmEFECOIR3D` — Specificity and Causality Audits for Activation-Based Safety Readouts
>
> Full, verbatim record of every prompt the AI Inventor pipeline gave this agent — system-user, human-user and skill-input — in the order they landed. Nothing truncated.

## Task: `gen_hypo_1` (terminal_claude_agent)

### [1] SYSTEM-USER prompt · 2026-09-20 20:48:32 UTC

```
a jailbreak or attack-selection study; do not reframe it as one.
</prompt>
```

### [2] SYSTEM-USER prompt · 2026-09-20 20:49:28 UTC

```
You are verifying prior-art citations for a mechanistic-interpretability hypothesis. Today is 2026-09-20. Do NOT trust snippets: fetch the actual abstract/PDF.

TOOLS: read the `aii-web-tools` skill first (Skill tool, skill="aii-web-tools"). The python for its scripts is `/ai-inventor/.claude/skills/.ability_client_venv/bin/python`. `aii_fast_web_fetch.py grep --url <pdf-or-abs-url> --pattern '<regex>'` gives verbatim extraction. Built-in WebSearch/WebFetch are deferred: `ToolSearch("select:WebSearch,WebFetch")` once if you want them. arxiv.org/abs/<id> and arxiv.org/pdf/<id> both work.

VERIFY EACH OF THESE EIGHT arXiv IDs: does it exist, what is its EXACT title, authors, date, and is the described content correct?

1. 2607.14147 — claimed "Breaking Refusal in the First Half: A Mechanistic Study of the Prefill Jailbreak", 14 Jul 2026. THIS IS THE MOST IMPORTANT ONE. For it, extract verbatim:
   (a) the exact sentence containing "response-site computation";
   (b) the full model list (which models, which sizes);
   (c) whether it CROSSES a request factor (harmful vs benign-twin REQUEST) with the response/prefill factor, or whether it only varies the response content while holding the request HARMFUL — quote the passage that settles this;
   (d) whether it reports any per-checkpoint scalar/summary number comparing checkpoints;
   (e) the exact wording about full-residual patching restoring refusal to 100% and the benign control;
   (f) the exact wording about the base-model control showing the same prefill collapse;
   (g) the exact wording about no single refusal-decision direction in Qwen (the ≤0.73 / ~0.85 probe numbers);
   (h) whether it includes any safety-RL / safe-completion model or any abliterated / weight-edited model.
2. 2505.19056 — claimed "An Embarrassingly Simple Defense Against LLM Abliteration Attacks". Verify title + the "at most 10%" vs "70-80% drops" numbers verbatim, and confirm it has NO activation-level analysis.
3. 2609.16204 — claimed "Decoy Direction Optimization" anti-abliteration defence.
4. 2606.29441 — claimed "Closing the Activation-Cone Blind Spot: Response-Time Probing and Unified Defense".
5. 2608.09624 — claimed "Measuring the Wrong Thing: Internal Harmfulness Scores Anti-Rank Successful Jailbreaks", AUROC 0.220.
6. 2407.09121 — claimed Decoupled Refusal Training.
7. 2603.23171 — claimed activation watermarking with token/span/whole-response monitor taxonomy.
8. 2510.18081 — claimed "Any-Depth Alignment", alignment concentrated in ASSISTANT HEADER TOKENS.

REPORT BACK, compactly:
- A table: ID | EXISTS yes/no | exact title | date | one-line what-it-owns.
- For 2607.14147, all eight verbatim extractions (a)-(h), each as a quoted sentence with nothing invented. If a claim cannot be verified in the text, say NOT FOUND explicitly rather than guessing.
- Flag loudly any ID that does NOT exist or whose title differs from the claim.
Be rigorous and concise. No file writes needed.
```

### [3] SKILL-INPUT — aii-web-tools · 2026-09-20 20:49:28 UTC

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

### [4] SYSTEM-USER prompt · 2026-09-20 20:49:37 UTC

```
Adversarial prior-art screen for a mechanistic-interpretability hypothesis. Today is 2026-09-20. Your job is to try to KILL the novelty claim, not to confirm it. Snippets are not evidence: FETCH candidate papers.

TOOLS: read the `aii-web-tools` skill first (Skill tool, skill="aii-web-tools"). Python: `/ai-inventor/.claude/skills/.ability_client_venv/bin/python`. Use `aii_fast_web_search.py` and `aii_fast_web_fetch.py` (supports `grep --url ... --pattern ...` over HTML and PDFs). Built-in WebSearch/WebFetch are deferred: `ToolSearch("select:WebSearch,WebFetch")` once if wanted.

THE NARROWED CLAIM TO ATTACK (three deltas, all must be unoccupied):
(A) A **CROSSED 2x2 factorial** in which the REQUEST factor (harmful vs matched benign twin) and the ALREADY-WRITTEN RESPONSE-PREFIX factor (hazardous vs benign) are varied INDEPENDENTLY over the same strings, teacher-forced, with an internal (activation) safety readout taken over identical token spans in all four cells — yielding two MAIN EFFECTS and their INTERACTION. Known prior art holds the request harmful and varies only the response (arXiv:2607.14147), so the crossing is the claimed delta.
(B) Reducing that pair to a **per-checkpoint two-number summary (O, C)** = (open-loop strength, closed-loop strength) used as a cheap, transferable model-level SAFETY METRIC across checkpoints/families.
(C) Running it on a **safe-completion / safety-RL checkpoint** and on **weight-edited (abliterated) checkpoints**, including an in-house rank-1 edit applied to two different parents.

SEARCH HARD, at least these angles, 2 searches each, and fetch anything close:
1. Within-field rephrasings: "prompt vs response contribution to refusal", "input-conditioned vs output-conditioned safety", "factorial activation patching safety", "2x2 counterfactual hidden states refusal", "decompose refusal signal into prompt and generated-text components".
2. Cross-field CORE MECHANISM: this is a two-factor ANOVA / variance decomposition of a neural readout into main effects + interaction, with the factors being two sources of conditioning. Search: causal mediation analysis in NLP (prompt vs context), "direct and indirect effect" activation analysis, ANOVA decomposition of neural representations, "factorial design" probing/interpretability, econometrics-style variance decomposition of model internals, psycholinguistics factorial ERP designs ported to LMs. Does anyone already run a CROSSED factorial over activations to split a readout into two conditioning sources?
3. Model-level cheap safety metrics read from ONE model's activations/weights with few prompts, that produce a TWO-number profile rather than a scalar. Search "safety fingerprint activations", "model-level safety metric hidden states no benchmark", "predict safety benchmark score from internals".
4. Failed/negative results: "prompt-side vs response-side safety does not", "no difference", "limitations of response-position probes".
5. Anything measuring open-loop vs closed-loop / feedback vs feedforward control framing of LLM safety specifically.

ALSO ANSWER THESE TWO FACTUAL QUESTIONS (they gate the design):
6. On HuggingFace, list UNGATED fine-tunes of **Qwen/Qwen3-4B-Base** that are NOT safety-related (e.g. code, math, general instruct from a third party) and are ~4B and downloadable — needed as a NON-SAFETY fine-tune control. Give exact repo ids and confirm gated status. Check `https://huggingface.co/api/models?search=Qwen3-4B&limit=100&full=true` style API calls and verify individual repos via `https://huggingface.co/api/models/<id>`; a repo's JSON has a `gated` field (can be false, "auto", or "manual").
7. Confirm current availability + exact loading path of **XSTest** (safe/unsafe splits) and **OR-Bench** as HuggingFace datasets for harmful/benign-twin request pairs: exact dataset repo ids, config/split names, row counts, gated status. Note: a previous run found `xstest_v2_prompts.csv` 404s, so verify the HF dataset route.

REPORT BACK compactly:
- VERDICT on each of (A), (B), (C): OCCUPIED / PARTIALLY OCCUPIED / OPEN, each with the single strongest paper (id, title, verbatim sentence) that comes closest.
- Any paper that runs a crossed request x response factorial on activations — this is the kill shot if it exists.
- Answers to 6 and 7 with exact repo ids and gated status.
Do not pad. Quote verbatim or say NOT FOUND.
```
