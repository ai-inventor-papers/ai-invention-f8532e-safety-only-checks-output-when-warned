"""Assemble research_out.json and .terminal_claude_agent_struct_out.json from the verified passage ledger."""
import json, sys
from pathlib import Path

WS = Path(__file__).parent
sys.path.insert(0, str(WS))
from passages_main import PASSAGES

VER = {(e["url"], e["passage"]): e["verified"] for e in json.load(open(WS / "research_verification.json"))["passages"]}
TODAY = "2026-09-21"

# index, key, url, title, summary, authors, year, used_for
S = [
 (1, "AMS", "https://arxiv.org/abs/2608.05578", "Detecting Safety Training Modification in Language Models via Activation Analysis (AMS: Activation-based Model Scanner)",
  "THE CLOSER of the widened claim. Reference-free (Tier 1) activation scanner: 16 contrastive pairs per concept, final prompt token, 40-80% depth sweep, 14 checkpoints / 4 families incl. 2 abliterated and 3 uncensored; sigma predicts JailbreakBench compliance at Pearson r=-0.546 (p=0.043); LOO threshold accuracy 71%.", None, 2026, "Block A, B1, B8, B9, D"),
 (2, "AMSREPO", "https://raw.githubusercontent.com/GoogleCloudPlatform/activation-model-scanner/main/README.md", "AMS - Activation-based Model Scanner (GoogleCloudPlatform/activation-model-scanner README)",
  "Open-source (Apache-2.0, pip ams-scanner) implementation of AMS; Tier 1 needs no baseline; README table: instruct 4.7-8.4 sigma, abliterated 3.3 sigma, uncensored 1.1-1.3 sigma, base 0.7 sigma. Repo live, 69 commits, latest commit e7ca0d1 on 2026-08-27, 33 stars.", None, 2026, "Block A; incumbent bar to reimplement"),
 (3, "NGLARE", "https://aclanthology.org/2026.acl-long.1334.pdf", "N-GLARE: A Non-Generative Latent Representation-Efficient LLM Safety Evaluator (ACL 2026 Long 1334)",
  "Per-model latent JSS scalar over 40+ models, last token across all layers before the response, four constructed dialogue families; Figure 1 uses the RL-aligned/base/safety-removed Qwen3-4B trio; Figure 7 prints layer-group Pearson/Spearman couplings of JSS with Unsafe Rate and keyword Refusal Rate across DPO steps. Still no code.", None, 2026, "Block A, B4, B6, C"),
 (4, "RAS", "https://arxiv.org/html/2606.25750", "RAS: Measuring LLM Safety Through Refusal Alignment (SafeVec)",
  "White-box 0-100 safety score from last-token refusal-direction alignment in a fixed family-specific layer window; needs a per-family aligned reference model and a calibration set; three families (Llama-3.1-8B, Gemma-3-4B, Qwen2.5-7B); separates aligned from uncensored/abliterated and tracks HEx-PHI ASR; no correlation coefficient, no over-refusal outcome, no logit baseline.", None, 2026, "Block A"),
 (5, "ALIGNED", "https://aclanthology.org/2026.tacl-1.14.pdf", "Aligned Probing: Relating Toxic Behavior and Model Internals (TACL 2026)",
  "Across 20+ OLMo/Llama/Mistral LMs, layer-wise toxicity-encoding strength (graded, Pearson of probe-predicted vs actual toxicity) correlates with output toxicity (EMT) across models; signal in lower layers; causal interventions; 6 OLMo pretraining checkpoints. Toxicity domain, not refusal; no abliterated checkpoints.", ["Andreas Waldis", "Vagrant Gautam", "Anne Lauscher", "Dietrich Klakow", "Iryna Gurevych"], 2026, "Block A, B7"),
 (6, "IRT", "https://arxiv.org/abs/2608.05086", "Item Response Theory for AI Safety",
  "Behavioural IRT over 8 safety benchmarks and 192 models; ~10 adaptively chosen items suffice. Owns the few-item regime behaviourally (a baseline, not an activation competitor).", None, 2026, "Block A, B9"),
 (7, "LVS", "https://arxiv.org/html/2606.08044", "When Behavioral Safety Evaluation Fails: A Representation-Level Perspective",
  "Adverse prior: constructed 'dissociated' models pass every static audit including a strong fixed activation probe; only an intervention-based Latent Vulnerability Score (2.5-3.1x) separates them.", ["Enyi Jiang", "Anders Gjølbye", "Yibo Jacky Zhang", "Sanmi Koyejo"], 2026, "Block A, D"),
 (8, "AUDIT273", "https://arxiv.org/abs/2607.01854", "Has This Checkpoint Been Abliterated? A Two-Signal Audit and Its Failure Map",
  "273-checkpoint registry, AUROC 0.95 for 57 abliterations vs 37 benign; presumes an attested reference (reference-anchored). Re-verified today.", None, 2026, "Block C, B8"),
 (9, "JORAK", "https://raw.githubusercontent.com/JolanMc/Jorak/main/docs/METRICS.md", "Jorak Model Scanner docs/METRICS.md",
  "Parent-free, weights-only abliteration detector (suppression statistic, SVD alignment A=sigma1(U)/||U||_F). Repo live today: Apache-2.0, latest commit 8147de3 (2026-07-24), 0 stars, non-peer-reviewed.", None, 2026, "Block C, B8"),
 (10, "LATBIOP", "https://arxiv.org/html/2603.27412", "The Geometry of Harmful Intent: Training-Free Anomaly Detection via Angular Deviation in LLM Residual Streams (LatentBiopsy)",
  "Harm geometry survives abliteration (Qwen3.5-0.8B, Qwen2.5-0.5B; AUROC within 0.015).", ["Isaac Llorente-Saguer"], 2026, "Block C, B1, D"),
 (11, "HIGRF", "https://arxiv.org/html/2604.18901", "Harmful Intent as a Geometrically Recoverable Feature of LLM Residual Streams",
  "12 models, 4 families, base/instruct/abliterated; harm detection within +/-0.003 AUROC across variants; two pooling choices recover harm directions 73 degrees apart.", None, 2026, "Block C, B1, B3, D"),
 (12, "ORGAD", "https://arxiv.org/html/2604.09544", "Large Language Models Generate Harmful Responses Using a Distinct Mechanism, Shared Across Harm Types",
  "Harm generation dissociable from harm recognition; double dissociation; separability emerges along the OLMo-3-7B ladder at DPO.", ["Hadas Orgad", "Boyi Wei", "Kaden Zheng", "Martin Wattenberg", "Peter Henderson", "Seraphina Goldfarb-Tarrant", "Yonatan Belinkov"], 2026, "Block C, E"),
 (13, "DSH", "https://arxiv.org/html/2603.05773v2", "Knowing without Acting: The Disentangled Geometry of Safety Mechanisms in Large Language Models",
  "Owns the Recognition-Axis / Execution-Axis naming and a causal double dissociation (attack framing: Refusal Erasure Attack).", ["Jinman Wu", "Yi Xie", "Shen Lin", "Shiqian Zhao", "Xiaofeng Chen"], 2026, "Block C, B3, E"),
 (14, "PDFC", "https://arxiv.org/html/2606.24952", "Perfect Detection, Failed Control: The Geometry of Knowing vs. Steering in Language Models",
  "Detection AUC 1.000 yet the refusal-control direction sits ~83 degrees away; weight cosine 0.1197 vs 0.1200 across instruction tuning; 'not a predictor of how steerable a behavior is'.", None, 2026, "Block C, D"),
 (15, "BASU", "https://arxiv.org/html/2603.18353", "Interpretability without actionability: mechanistic methods cannot correct language model errors despite near-perfect internal representations",
  "Clinical triage, Qwen 2.5 7B Instruct: probe AUROC 98.2% vs output sensitivity 65/144 (45%); SAE arm zero corrections/zero disruptions; concept-bottleneck 17/85 corrected, 25/47 disrupted; TSV 19/79 corrected, 4/65 disrupted.", ["Sanjay Basu", "Sadiq Y. Patel", "Parth Sheth", "Bhairavi Muralidharan", "Namrata Elamaran", "Aakriti Kinra", "John Morgan", "Rajaie Batniji"], 2026, "Block C, D"),
 (16, "KWON", "https://arxiv.org/html/2607.14147v1", "Breaking Refusal in the First Half: A Mechanistic Study of the Prefill Jailbreak",
  "Logit-trace concentration 0.24 vs 0.03 (instruct vs base, knockout-conditioned). Re-verified.", None, 2026, "Block C"),
 (17, "ANTIRANK", "https://arxiv.org/html/2608.09624", "Measuring the Wrong Thing: Internal Harmfulness Scores Anti-Rank Successful Jailbreaks",
  "Outcome AUROC 0.220 among wrapped harmful prompts: internal harm scores rank successful attacks below failed ones. Re-verified.", None, 2026, "Block C, D"),
 (18, "HRCI", "https://arxiv.org/html/2606.16349", "From Refusal Geometry to Safety Geometry: Harmfulness-Refusal Coupling under Dynamic Adversarial Fine-Tuning (HRCI_repr)",
  "Parent-free coupling index whose authors state low coupling is not itself a safety score; tracks XSTest refusal during adversarial fine-tuning.", None, 2026, "Block C, B6"),
 (19, "CLS", "https://arxiv.org/html/2606.22686v2", "The Geometry of Refusal: Linear Instability in Safety-Aligned LLMs (Contrastive Logit Steering)",
  "Seven families: harmful/safe hidden-state KL divergence onset depth differs by family ('Late Decision' Llama-3.1 at the final head vs 'Early Divergence' Qwen-2.5 at ~40% depth), qualitatively tied to robustness. TrustNLP 2026.", None, 2026, "B1"),
 (20, "ZHOU24", "https://arxiv.org/abs/2406.05644", "How Alignment and Jailbreak Work: Explain LLM Safety through Intermediate Hidden States",
  "2024 anchor: malicious vs normal inputs identified in early layers; alignment maps them via middle layers to reject tokens.", None, 2024, "B1, B4"),
 (21, "SAFELAYERS", "https://arxiv.org/abs/2408.17003", "Safety Layers in Aligned Large Language Models: The Key to LLM Security",
  "Contiguous mid-depth 'safety layers' distinguish malicious from normal queries.", ["Shen Li", "Liuyi Yao", "Lan Zhang", "Yaliang Li"], 2024, "B1"),
 (22, "RBD", "https://arxiv.org/html/2605.28553", "Refusal Before Decoding: Detecting and Exploiting Refusal Signals in Intermediate LLM Activations",
  "Refusal linearly decodable well before the final layer (per-input probes, used for attack search).", None, 2026, "B1"),
 (23, "MITRA", "https://arxiv.org/html/2606.29441", "Closing the Activation-Cone Blind Spot: Response-Time Probing and Unified Defense",
  "Seven models: prompt-time activation defenses are structurally blind to prefilling; response-time probe at the first generated tokens (AUROC 0.97-1.00), per input.", None, 2026, "B2"),
 (24, "FORESIGHT", "https://arxiv.org/abs/2609.13737", "ForeSight: Enhancing Risk Monitoring via Early Safety Signal Distillation",
  "First-response-token hidden states forecast output harm (two target models, per input). Findings of EMNLP 2026.", None, 2026, "B2"),
 (25, "HARC", "https://arxiv.org/abs/2607.00572", "HARC: Coupling Harmfulness and Refusal Directions for Robust Safety Alignment",
  "Owns the response-site harmfulness readout (model recognises harm while generating it even when the prompt side missed it).", ["Shei Pern Chua", "Hao Wu", "Qianli Ma", "Fangzhao Wu"], 2026, "B2"),
 (26, "ROT", "https://arxiv.org/html/2604.13386", "Linear Probe Accuracy Scales with Model Size and Benefits from Multi-Layer Ensembling",
  "Deception directions rotate gradually across layers (12 models); multi-layer ensembles fix single-layer brittleness.", None, 2026, "B3, B9"),
 (27, "OBLIT", "https://raw.githubusercontent.com/elder-plinius/OBLITERATUS/cb4aec45/obliteratus/analysis/cross_layer.py", "OBLITERATUS toolkit, analysis/cross_layer.py (community abliteration tool)",
  "Non-peer-reviewed public code that already computes the pairwise cross-layer refusal-direction cosine matrix, direction clusters and cumulative angular drift per layer.", None, None, "B3, B4"),
 (28, "PERSONA", "https://arxiv.org/html/2606.26161", "Refusal Lives Downstream of Persona in Chat Models",
  "Refusal staged as detection -> aggregation -> late-layer expression; refusal is gated at the late expression stage, downstream of where it is computed; random-direction control. ICML 2026 MI workshop.", None, 2026, "B4, B5, E"),
 (29, "WRITE", "https://arxiv.org/abs/2609.04721", "Locating and Steering Refusal Beyond Attention",
  "Where refusal must be read (write site) is architecture-specific while where it is steered is not; matched-size random-direction control.", None, 2026, "B5, E"),
 (30, "HPD", "https://arxiv.org/abs/2609.13534", "Harmfulness Propagation Dynamics: Layer-wise Trajectories of Adversarial Intent in Large Language Models",
  "Per-prompt depth-profile scalarisation (slope, curvature, monotonicity, onset layer) fed to a 288-parameter MLP.", ["Noor Islam S. Mohammad", "Uluğ Bayazıt"], 2026, "B4, B9"),
 (31, "GEOLITE", "https://arxiv.org/abs/2605.20241", "Geometry-Lite: Interpretable Safety Probing via Layer-Wise Margin Geometry",
  "Per-prompt layer-wise margin-profile summaries over nine backbones.", ["Woo Seob Sim", "Yu Rang Park"], 2026, "B4, B9"),
 (32, "ICS", "https://arxiv.org/html/2608.16852", "What Do Compliance Detectors Read? An Audit of Activation Probes and Guard Models",
  "10-pair training-free diff-in-means activation readout (Internal Compliance Score); fails its pre-registered bar and ties a bag-of-words model.", None, 2026, "B9"),
 (33, "PYTHIA", "https://arxiv.org/pdf/2609.01048v1", "Lagged Coupling: Internal Representations Become Readable Before They Become Causal",
  "Pythia 160M-12B, 8 checkpoints: probes read targets from step 1,000 yet steering is null-equivalent in 43 of 48 model x checkpoint cells.", None, 2026, "Block D, B5"),
 (34, "CAD", "https://arxiv.org/html/2608.17843v1", "Encoded but Not Actionable: Auditing the Decode-Generate-Steer Gap in Frozen LLMs for Geometric Constraints",
  "Non-safety (CAD geometry), six models: decodable information is not always actionable; patching effects vanish while decodability persists.", None, 2026, "Block D"),
 (35, "SAEPROBE", "https://arxiv.org/html/2609.18080v1", "Decodability is Not Causality: Dissociating Probe Readouts from Behavioral Drivers via SAE Decomposition",
  "Truth/deception: probe-weighted and behaviourally causal SAE features overlap only ~12% (Spearman rho=0.10); ablation dissociates them.", None, 2026, "Block D"),
 (36, "ARITH", "https://arxiv.org/html/2608.07528", "The Knowing-Saying Gap: When Probes See Errors that Confidence Misses",
  "Near-perfect corruption probes do not predict failures; probe-based interventions are model-dependent.", None, 2026, "Block D"),
 (37, "ORSUB", "https://arxiv.org/abs/2603.27518", "Over-Refusal and Representation Subspaces: A Mechanistic Analysis of Task-Conditioned Refusal in Aligned LLMs",
  "Over-refusal directions are task-dependent and representationally distinct from harmful refusal from early layers; single model, per input. EMNLP 2026 Main.", None, 2026, "B6"),
 (38, "MOREDIR", "https://arxiv.org/abs/2602.02132", "There Is More to Refusal in Large Language Models than a Single Direction",
  "Distinct refusal directions but steering along any gives nearly identical refusal/over-refusal trade-offs (one shared control knob).", None, 2026, "B6"),
 (39, "THOUSAND", "https://arxiv.org/pdf/2507.21141v1.pdf", "The Geometry of Harmfulness in LLMs through Subconcept Probing",
  "55 harmfulness sub-concept directions: harm organised by category, not ordinal severity.", None, 2025, "B7"),
 (40, "CYBER24", "https://arxiv.org/html/2607.02714", "Not All Refusals Are Equal: How Safety Alignment Fails Cybersecurity at Scale",
  "Abliteration over 24 open models; susceptibility predicted from safety-training type and architecture (metadata), not activations.", None, 2026, "Block A"),
 (41, "OPSTATE", "https://arxiv.org/html/2608.30748", "The Fragility of Jailbreak Robustness Across Operational States",
  "Within a model, projection on a refusal-related axis predicts ASR across operational states (per condition, not per checkpoint).", None, 2026, "Block A"),
 (42, "TRANSFER", "https://arxiv.org/abs/2506.12913", "Jailbreak Transferability Emerges from Shared Representations",
  "Across 20 models, benign-prompt representational similarity predicts jailbreak transfer (attack-side; not a safety score).", None, 2025, "Block A"),
 (43, "AMS", "https://arxiv.org/html/2608.05578", "Detecting Safety Training Modification in Language Models via Activation Analysis (AMS) - full text",
  "Full-text anchors: 16 pairs (32 prompts) per concept, final-token extraction, 40-80% depth; Spearman weaker (rho=-0.423, p=0.13); class-(iv) blind spot (DarkIdol sigma 5.45 with 97% compliance) and decode-time analysis named as the principal open problem; zero XSTest/over-refusal matches.", None, 2026, "Block A, B2, D, E"),
 (44, "REFWO", "https://arxiv.org/abs/2609.04714", "Refuse without Refusal: A Structural Analysis of Safety-Tuning Responses for Reducing False Refusals in Language Models",
  "Behavioural only: rationale-only safety tuning reduces false refusals. Checked for the safe-completion internal-readout cell; it has no activation readout, so that NOT-FOUND stands.", ["Minji Kim", "Hyounghun Kim"], 2026, "Block E (absence)"),
 (45, "RRMIS", "https://arxiv.org/abs/2608.29109", "Recognition-Refusal Misalignment in LLMs: Why Models Answer Structurally Unanswerable Questions",
  "Non-safety knowledge-action gap (impossible math/code): a recognition direction exists before generation and is nearly orthogonal to safety refusal, yet steering along it works dose-responsively vs random directions. Counter-example to 'readable implies not actionable'.", None, 2026, "Block D"),
]

src = []
for idx, key, url, title, summ, authors, year, used in S:
    sp = [dict(quote=p["passage"], locator=f"regex: {p['regex']}") for p in PASSAGES
          if p["key"] == key and p["url"] == url and VER.get((p["url"], p["passage"]))]
    src.append(dict(index=idx, url=url, title=title, summary=summ, authors=authors, year=year,
                    supporting_passages=sp[:5], fetched=True, date_checked=TODAY, used_for=used))

answer = (WS / "answer.md").read_text()
summary = (WS / "summary.txt").read_text().strip()
title = "Is our depth-and-site safety metric already taken?"
layman = ("Checks whether anyone has already built a cheap safety score that reads a model's internal activations, and finds "
          "that a Google tool already does most of it, leaving only the during-the-reply reading and over-refusal open.")
fups = [
    "Does a response-site readout (first generated tokens) beat the AMS harmful-content sigma and a final-layer logit gap at predicting harmful-compliance rate on a panel that includes the Qwen3-4B base / instruct / abliterated trio, and which of AMS's four modification classes does the community Qwen3-4B abliterated checkpoint fall into?",
    "Can any internal readout rank checkpoints by XSTest over-refusal rate across at least three families, a behaviour none of AMS, RAS or N-GLARE scores?",
    "At the surviving layer and site, does a matched-norm projection along the readout direction move behaviour more than a norm-matched random orthogonal direction on the instruct checkpoint and fail to on the abliterated one? That would turn the readout into the mechanistic answer rather than a correlate.",
]
out = dict(title=title, layman_summary=layman, summary=summary, answer=answer, sources=src, follow_up_questions=fups)
json.dump(out, open(WS / "research_out.json", "w"), indent=1, ensure_ascii=False)

struct = dict(title=title, layman_summary=layman, summary=summary,
              out_expected_files=dict(output="research_out.json"),
              upload_ignore_regexes=[r"(^|/)verify_cache/", r"(^|/)__pycache__/", r"(^|/)blockA/(g|s|z|q|abs_|cit_)[^/]*\.txt$", r"(^|/)blockB/(q|abs_)[^/]*\.txt$"],
              answer=answer,
              sources=[{k: v for k, v in s.items() if k in ("index", "url", "title", "summary", "authors", "year", "supporting_passages")} for s in src],
              follow_up_questions=fups)
json.dump(struct, open(WS / ".terminal_claude_agent_struct_out.json", "w"), indent=1, ensure_ascii=False)

# citation integrity
import re
cited = {int(n) for grp in re.findall(r"\[([\d,\s]+)\]", answer) for n in grp.split(",") if n.strip()}
idxs = {s["index"] for s in src}
print("cited not listed:", sorted(cited - idxs), "| listed not cited:", sorted(idxs - cited))
print("summary chars", len(summary), "| title chars", len(title), "| layman", len(layman))
print("passages attached:", sum(len(s["supporting_passages"]) for s in src))
