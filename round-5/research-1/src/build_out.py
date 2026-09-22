"""Assemble research_verification.json, research_out.json, research_report.md and the struct-out file
from the block outputs. Re-runnable; reads only files inside this workspace."""
import json, re
from collections import Counter
from pathlib import Path

WS = Path(__file__).parent
J = lambda p: json.loads((WS / p).read_text())
qres = J("verify/quote_results.json")
ares = J("verify/absence_results.json")
sat = J("saturation_table.json")
T = J("blockT/target_cell_table.json")
D = J("blockD/dimensionality.json")
A = J("ams_spec_iter5.json")
MNC = J("must_not_claim.json")
BIB = J("bib_changelog.json")

# ---------------------------------------------------------------- sources
S = [
 ("https://arxiv.org/abs/2608.05578","AMS: Detecting Safety Training Modification in Language Models via Activation Analysis","Incumbent bar; single-model INT4 drift <=4.4%; no over-refusal target; names token-level decoding analysis its principal open problem.","closer",["Glen Messenger"],2026),
 ("https://github.com/GoogleCloudPlatform/activation-model-scanner","AMS source repository (activation-model-scanner)","Code-line evidence for the eight pinned facts and the padding hazard (extractor.py:130, 167-173).","tool",None,2026),
 ("https://raw.githubusercontent.com/huggingface/transformers/main/src/transformers/tokenization_utils_base.py","transformers tokenization_utils_base.py","Class attribute padding_side: str = \"right\" -- the default inherited when tokenizer_config.json omits the key.","tool",None,None),
 ("https://huggingface.co/Qwen/Qwen3-4B/raw/main/tokenizer_config.json","Qwen/Qwen3-4B tokenizer_config.json","padding_side key ABSENT (control: model_max_length, pad_token present); pad_token <|endoftext|>.","tool",None,None),
 ("https://huggingface.co/Qwen/Qwen3-4B-Base/raw/main/tokenizer_config.json","Qwen/Qwen3-4B-Base tokenizer_config.json","padding_side ABSENT; pad_token and eos both <|endoftext|>.","tool",None,None),
 ("https://huggingface.co/Qwen/Qwen3-4B-SafeRL/raw/main/tokenizer_config.json","Qwen/Qwen3-4B-SafeRL tokenizer_config.json","padding_side ABSENT; pad_token <|endoftext|>.","tool",None,None),
 ("https://huggingface.co/mlabonne/Qwen3-4B-abliterated/raw/main/tokenizer_config.json","mlabonne/Qwen3-4B-abliterated tokenizer_config.json","padding_side ABSENT; pad_token <|endoftext|>.","tool",None,None),
 ("https://huggingface.co/tiiuae/Falcon3-1B-Instruct/raw/main/tokenizer_config.json","tiiuae/Falcon3-1B-Instruct tokenizer_config.json","padding_side ABSENT (control regex returned 2 matches); pad_token <|pad|>.","tool",None,None),
 ("https://arxiv.org/abs/2307.15771","The Hydra Effect: Emergent Self-repair in Language Model Computations","Canonical self-repair anchor 1 for the W4 attribution sentence.","framing",["Thomas McGrath","Matthew Rahtz","Janos Kramar","Vladimir Mikulik","Shane Legg"],2023),
 ("https://arxiv.org/abs/2402.15390","Explorations of Self-Repair in Language Models","Canonical self-repair anchor 2 (ICML 2024); per-head/per-prompt self-repair, never one number per model.","framing",["Cody Rushing","Neel Nanda"],2024),
 ("https://arxiv.org/abs/2211.00593","Interpretability in the Wild: a Circuit for Indirect Object Identification in GPT-2 small","Origin of backup name-mover heads.","framing",["Kevin Wang","Alexandre Variengien","Arthur Conmy","Buck Shlegeris","Jacob Steinhardt"],2022),
 ("https://arxiv.org/abs/2607.01940","Conditional Co-Ablation: Recovering Self-Repair Backups in Transformer Circuits","Nearest W4 neighbour: a self-repair score per unit/circuit, never per checkpoint (0 checkpoint-framing matches, control 'ablation' 143).","near_miss",["Zhiren Gong","Zihao Zeng","Chau Yuen","Wei Yang Bryan Lim"],2026),
 ("https://arxiv.org/abs/2603.23268","SafeSeek: Universal Attribution of Safety Circuits in Language Models","Nearest W2 neighbour: minimal joint-ablation safety circuits per scenario (0.42%; 3.03% heads + 0.79% neurons), not a k-band depth scored across checkpoints.","near_miss",None,2026),
 ("https://arxiv.org/abs/2510.18081","Any-Depth Alignment: Unlocking Innate Safety Alignment of LLMs to Any-Depth","Nearest W3/W7 neighbour; inference-time defence; no all-position/last-token ablation ratio.","near_miss",None,2025),
 ("https://arxiv.org/abs/2606.24952","Perfect Detection, Failed Control","Per-checkpoint weight-computable detection-vs-intervention cosine over four models; nearest G3/W1 neighbour.","near_miss",None,2026),
 ("https://arxiv.org/abs/2506.24056","Logit-Gap Steering","Reads the refusal-affirmation logit gap directly; nearest G4 neighbour.","near_miss",None,2025),
 ("https://arxiv.org/abs/2602.02132","There Is More to Refusal in Large Language Models than a Single Direction","Pairwise cosines among 11 refusal-category directions; nearest G1 neighbour; G2 absence control.","near_miss",None,2026),
 ("https://github.com/elder-plinius/OBLITERATUS","OBLITERATUS toolkit (CrossLayerAlignmentAnalyzer)","Cross-layer consistency / angular-drift scalar, explicitly NOT a joint-ablation redundancy scalar.","tool",None,2026),
 ("https://github.com/JolanMc/Jorak","Jorak Model Scanner","Re-located live: weights-only r^T W suppression and SVD subspace-alignment scar test; parent-free; W8 neighbour.","tool",None,2026),
 ("https://arxiv.org/abs/2609.18471","First Token Matters","Nearest over-refusal-as-target miss: decode-site score + XSTest outcome, but over-refusal is its own defence's outcome column on 2 checkpoint families.","near_miss",None,2026),
 ("https://arxiv.org/abs/2609.04721","Locating and Steering Refusal (2609.04721)","XSTest over-refusal outcome with orthogonalised-random controls; outcome of a defence, not a target.","near_miss",None,2026),
 ("https://arxiv.org/abs/2606.15980","Do Activation Monitors Survive Model Updates? (Duan)","Frozen probes across twelve update conditions; per-cell Spearman prediction of monitor staleness, not over-refusal.","near_miss",None,2026),
 ("https://arxiv.org/abs/2511.14195","N-GLARE","Scores base/RL/safety-removed Qwen3-4B; refusal rate is keyword refusal on HARMFUL prompts, not over-refusal.","framing",None,2026),
 ("https://arxiv.org/abs/2606.25750","RAS / SafeVec","Reference-anchored; no over-refusal target.","framing",None,2026),
 ("https://arxiv.org/abs/2503.13390","Aligned Probing","Layer-wise internals vs graded toxicity across 20+ models; no over-refusal target.","framing",None,2025),
 ("https://arxiv.org/abs/2607.01854","Has This Checkpoint Been Abliterated? (Hurtado)","273-checkpoint registry, benign fine-tunes as hard negatives, reference-anchored; fails the benign-PROMPT axis.","near_miss",None,2026),
 ("https://arxiv.org/abs/2603.27518","Over-Refusal and Representation (2603.27518)","Over-refusal directions are task/intent dependent; over-refusal an outcome, not a per-checkpoint target.","near_miss",None,2026),
 ("https://arxiv.org/abs/2608.09624","Measuring the Wrong Thing: Internal scores (2608.09624)","Internal scores anti-rank; benign set used only as false-positive calibration.","near_miss",None,2026),
 ("https://arxiv.org/abs/2606.08044","When Behavioral Safety Evaluation Fails (2606.08044)","Latent Vulnerability Score + per-model over-refusal column; the two are NEVER correlated ('correlat' 0 matches; controls 4 and 49).","near_miss",None,2026),
 ("https://arxiv.org/abs/2607.09697","Safe responses matter: Output-aware safety guardrail mitigate over-refusal in MLLMs","Over-refusal as an outcome of a guardrail.","near_miss",None,2026),
 ("https://arxiv.org/abs/2609.00790","RISA: Response Inspection and Selective Actions for Refusal Calibration","Per-base-model thresholds; over-refusal rate an outcome of its method.","near_miss",None,2026),
 ("https://arxiv.org/abs/2609.00760","A Unified Mechanistic Analysis of Knowledge- and Safety-Based Refusals","Secondary nearest miss: XSTest over-refusal column AND probe-accuracy column in one paper, never correlated.","near_miss",None,2026),
 ("https://arxiv.org/abs/2608.05086","Item Response Theory for AI Safety","P1's nearest cousin: factor analysis of BENCHMARK OUTPUTS (8 benchmarks, 5,255 items, 192 models, 3 factors, 77% variance).","framing",["Joshua Fonseca Rivera","Neil Shah","David Demitri Africa","Konstantinos Voudouris"],2026),
 ("https://arxiv.org/abs/2606.20626","Efficient Safety Benchmarking via Item Response Theory","The real 'Spagliardi' paper: few-item behavioural safety evaluation; assumes (never tests) unidimensionality.","bib",["Fabio Spagliardi","Mirian Silva","Ayan Datta","Aiden Zhou","Vamshi Bonagiri","Diogo Cruz"],2026),
 ("https://arxiv.org/abs/2406.11717","Refusal in Language Models Is Mediated by a Single Direction","Rank-of-the-refusal-direction debate: single direction.","framing",None,2024),
 ("https://arxiv.org/abs/2411.09003","Refusal in LLMs is an Affine Function","Rank debate: affine.","framing",None,2024),
 ("https://arxiv.org/abs/2502.17420","The Geometry of Refusal in Large Language Models: Concept Cones and Representational Independence","Rank debate: multiple independent directions and cones (ICML 2025).","framing",None,2025),
 ("https://arxiv.org/abs/2607.02396","Fast Multi-dimensional Refusal Subspaces via RFM-AGOP","Rank debate: multi-dimensional refusal subspaces.","framing",None,2026),
 ("https://arxiv.org/abs/2502.09674","The Hidden Dimensions of LLM Alignment","Most dangerous P1 near-miss: 'safety residual space is low-rank' -- about one model's internal subspace, not a score family.","near_miss",None,2025),
 ("https://arxiv.org/abs/2404.01318","JailbreakBench: An Open Robustness Benchmark for Jailbreaking Large Language Models","Bib fix: Chao et al., NeurIPS 2024 D&B.","bib",["Patrick Chao","Edoardo Debenedetti","Alexander Robey","Maksym Andriushchenko","Francesco Croce","Vikash Sehwag","Edgar Dobriban","Nicolas Flammarion","George J. Pappas","Florian Tramer","Hamed Hassani","Eric Wong"],2024),
 ("https://arxiv.org/abs/2402.04249","HarmBench: A Standardized Evaluation Framework for Automated Red Teaming and Robust Refusal","Bib fix: Mazeika et al.","bib",["Mantas Mazeika","Long Phan","Xuwang Yin","Andy Zou","Zifan Wang","Norman Mu","Elham Sakhaee","Nathaniel Li","Steven Basart","Bo Li","David Forsyth","Dan Hendrycks"],2024),
 ("https://arxiv.org/abs/2603.18353","Interpretability without actionability (Basu et al.)","Knowledge-action gap premise; the handbook DOES name Basu and 2603.18353 (SOURCES.md row S3).","framing",None,2026),
 ("https://arxiv.org/abs/2604.09544","Large Language Models Generate Harmful Responses Using a Distinct Mechanism, Shared Across Harm Types (Orgad et al.)","Owns recognition-vs-generation dissociation (carried fence).","framing",None,2026),
 ("https://arxiv.org/abs/2504.02922","Overcoming Sparsity Artifacts in Crosscoders to Interpret Chat-Tuning","Crosscoder L1 misattribution artefact -- fence for the four-way comparison.","framing",["Julian Minder","Clement Dumas","Bilal Chughtai","Neel Nanda"],2025),
 ("https://arxiv.org/abs/2509.17196","Evolution of Concepts in Language Model Pre-Training","Training-dynamics checkpoint tracking with crosscoders (ICLR 2026) -- fence.","framing",None,2025),
 ("https://api.semanticscholar.org/graph/v1/paper/arXiv:2307.15771/citations?fields=title,abstract,year,externalIds&limit=100","Semantic Scholar forward citations of the Hydra Effect","Forward-citation sweep: 100 citing papers screened (API cap).","absence_control",None,None),
 ("https://api.semanticscholar.org/graph/v1/paper/arXiv:2402.15390/citations?fields=title,abstract,year,externalIds&limit=100","Semantic Scholar forward citations of Rushing & Nanda","Forward-citation sweep: all 36 citing papers screened.","absence_control",None,None),
 ("https://pypi.org/pypi/ams-scanner/json","PyPI ams-scanner metadata","Version 0.1.3 unchanged since 2026-04-28.","tool",None,None),
 ("https://api.github.com/repos/GoogleCloudPlatform/activation-model-scanner/commits?per_page=5","AMS GitHub commits API","HEAD e7ca0d1a... dated 2026-08-27, unchanged.","tool",None,None),
 ("https://www.lesswrong.com/posts/Sj92Atv6qwNn5JxbF/","LessWrong: refusal mediated redundantly across layers","W2 near-miss: joint ablation of 31/32 layers on one model; not a k-search scored across checkpoints.","near_miss",None,None),
 ("https://jdunbar.net/pages/self_repair/","How much self-repair is in GPT2 without LayerNorm? (blog)","Informal W4 near-miss: compares two GPT-2 variants, never scalarised per model, not peer-reviewed.","near_miss",None,None),
]
IDX = {u: i + 1 for i, (u, *_rest) in enumerate(S)}
def aid(u):
    m = re.search(r"(\d{4}\.\d{4,5})", u); return m.group(1) if m else None

# verified single-passage quotes -> supporting passages (no ellipses, no brackets, <=320 chars)
def clean(q): return "..." not in q and "[" not in q and not q.startswith("'") and len(q) <= 320 and "FALSE-POSITIVE" not in q
passages = {}
for r in qres:
    if not r["status"].startswith("REVERIFIED") or not clean(r["quote"]): continue
    u = r["url"]; key = None
    for src in IDX:
        if aid(src) and aid(src) == aid(u): key = src; break
        if not aid(src) and src.rstrip("/") in u: key = src; break
    if key and len(passages.setdefault(key, [])) < 2:
        passages[key].append({"quote": r["quote"], "locator": f"re-fetched {u} (Block V, {r['status']})"})
# a few passages verified by the orchestrator directly in this session
extra = {
 "https://raw.githubusercontent.com/huggingface/transformers/main/src/transformers/tokenization_utils_base.py": ['padding_side: str = "right"'],
 "https://arxiv.org/abs/2606.20626": ["Efficient Safety Benchmarking via Item Response Theory"],
}
for k, qs in extra.items():
    passages.setdefault(k, []).extend({"quote": q, "locator": "orchestrator re-fetch 2026-09-22"} for q in qs)

sources = [{"index": IDX[u], "url": u, "title": t, "summary": s, "authors": a, "year": y,
            "role": role, "arxiv_id": aid(u), "date_checked": "2026-09-22",
            "supporting_passages": passages.get(u, [])} for (u, t, s, role, a, y) in S]

# ---------------------------------------------------------------- verification ledger
qc = Counter(r["status"] for r in qres)
deletions = [
 {"quote": "Safety Awareness Increases with Generation Depth ... features from injected Safety Tokens ... become highly separable, while those from the last [prompt token do not]",
  "url": "https://arxiv.org/pdf/2510.18081",
  "reason": "COMPOSITE WITH A DISTORTING EDITORIAL INSERTION. The source's Figure 3 caption says the last GENERATED token 'remain[s] entangled'; the insertion '[prompt token do not]' changed generated->prompt, which is exactly the distinction W3 turns on. Replaced with the verbatim caption sentence, which re-verified."},
 {"quote": "The smoking gun is the bottom row -- per-layer weight alignment to the refusal direction. It stays near-zero for a censored model ... but is lit up across layers for an abliterated one",
  "url": "https://github.com/JolanMc/Jorak",
  "reason": "COMPOSITE joined with '...'; lead sentence not reproducible on re-fetch. Claim carried by the separately re-verified 'Weights -- spectral signature (SVD)' passage."},
 {"quote": "detecting class (iv) likely requires ... token-level decoding analysis ... We treat this as the principal open problem motivated by the present results",
  "url": "https://arxiv.org/pdf/2608.05578", "reason": "COMPOSITE with ellipses. Anchor phrase 'principal open problem' present (1 match) and the substantive claim was verified in iteration 3; cite as a paraphrase."},
 {"quote": "Figure 10: ... Random heads (baseline)", "url": "https://arxiv.org/pdf/2609.00760", "reason": "COMPOSITE of a caption fragment; 'Random heads' is present (2 matches). Not usable as a quote."},
] + [{"quote": q, "url": u, "reason": "RELABELLED, not deleted: a paraphrase stored in a quote field. The cell verdict rests on its regex + positive-control evidence."}
     for q, u in [("last PROMPT token, pre-generation","https://arxiv.org/pdf/2511.14195"),("explicitly disclaims steering","https://arxiv.org/pdf/2606.25750"),
                  ("layer-skip ablation, no direction-vs-random control","https://arxiv.org/pdf/2503.13390"),("layer-band causal ablation named future work","https://arxiv.org/pdf/2607.01854"),
                  ("a matched random-head/random-probe baseline is used for the harmfulness-score ranking task ('the random probe on Llama')","https://arxiv.org/pdf/2608.09624")]]
ellipsis = [{"id": r["id"], "url": r["url"], "quote": r["quote"]} for r in qres if "..." in r["quote"] and r["status"].startswith("REVERIFIED")]
screened = [r for r in ares if r["status"] == "NOT_REPRODUCED"]
ver = {
 "date": "2026-09-22",
 "quotes_total": len(qres), "quotes_reverified": sum(v for k, v in qc.items() if k.startswith("REVERIFIED")),
 "quote_status_counts": dict(qc),
 "method": "Every quote in lane outputs was re-fetched against its OWN URL by the orchestrator (the finders were subagents), using a whitespace/punctuation-flexible regex over an 8-word window; fallback: >=2 distinct 4-word windows must match (REVERIFIED_BY_ANCHOR), which tolerates PDF line-wraps. Script: verify_quotes.py; raw results verify/quote_results.json.",
 "ellipsis_quotes_reverified_piecewise": ellipsis,
 "ellipsis_rule": "These passed piecewise but contain '...'. Present them only as excerpts with the ellipsis visible, never as one sentence. They are excluded from supporting_passages.",
 "deletions": deletions,
 "absence_claims": [r for r in ares if r["status"] == "REPRODUCED"],
 "absence_claims_not_regrep_reproducible": [r for r in ares if r["status"].startswith("NOT_REPRODUCIBLE")],
 "screening_regexes_misfiled_as_absences": [{**r, "ruling": "NOT a zero-match claim: a screening regex whose hits were then read by hand (citation sweeps: 15 and 8 hits; 2606.20626: 2 hits = the 2PL 'unidimensional latent safety ability' ASSUMPTION, which is exactly Block D's reading). Reclassified, not failed."} for r in screened],
 "absence_count_reproduced": sum(r["status"] == "REPRODUCED" for r in ares),
 "handbook_silence_check": "0 matches for self-repair, self repair, hydra, backup head, backup behavior, backup behaviour, redundan, compensat, ablation-induced over SKILL.md/SOURCES.md/volatile.md; positive controls sparse autoencoder 8, steering 16, circuit 29, patching 11 (blockS/handbook_greps.txt).",
 "beyond_horizon": [
   {"item": "tiiuae/Falcon3-1B-Instruct tokenizer_config.json tail (pad_token, model_max_length) at char 275262 of 275360", "recovered_by": "fetch_grep", "beyond_fetch_horizon": True},
   {"item": "transformers PreTrainedTokenizerBase class attribute padding_side = \"right\" at char 38468 of 147189", "recovered_by": "fetch_grep", "beyond_fetch_horizon": True},
   {"item": "Any-Depth Alignment Figure 3 caption at char 15406 of the PDF", "recovered_by": "fetch_grep", "beyond_fetch_horizon": True}],
 "ids_total": 16 + 7, "ids_resolved": 16 + 7, "unresolved": [],
 "id_resolution_note": "All 16 never-independently-checked hypothesis ids resolve via the arXiv API (blockB/id_resolution.txt); 7 new bib entries (Chao2024, Mazeika2024, Spagliardi2026, McGrath2023, Rushing2024, Wang2022, Gong2026) resolved live. 0 NOT_FOUND.",
 "service_note": "Late in the session the fetch service intermittently returned empty output (one re-grep of 2606.20626). That result was not counted either way.",
}
(WS / "research_verification.json").write_text(json.dumps(ver, indent=1))
print("verification:", ver["quotes_reverified"], "/", ver["quotes_total"], "| absences reproduced:", ver["absence_count_reproduced"])
json.dump({"IDX": IDX}, open(WS / "verify/_idx.json", "w"))
json.dump(sources, open(WS / "verify/_sources.json", "w"), indent=1)
