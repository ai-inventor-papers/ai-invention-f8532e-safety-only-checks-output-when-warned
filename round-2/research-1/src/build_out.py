import json
from pathlib import Path

bib={d['arxiv_id']:d for d in json.load(open('phase3/bibliography_verified.json'))}
ver=json.load(open('research_verification.json'))
# index verified passages by (url, quote)
pas=[r for r in ver['records'] if r['class']=='passage' and r['status']=='valid']
by_url={}
for r in pas: by_url.setdefault(r['source_url'],[]).append(r)

def yr(aid): return 2000+int(aid[:2]) if int(aid[:2])<90 else None

def P(url, *needles, loc=None):
    """pick verified passages at url whose quote starts with / contains a needle"""
    out=[]
    for n in needles:
        for r in by_url.get(url,[]):
            if n in r['quote']:
                out.append({"quote":r['quote'],"locator":r.get('locator') or loc}); break
    return out

S=[]
def add(url,title,summary,authors=None,year=None,passages=None):
    S.append({"index":len(S)+1,"url":url,"title":title,"summary":summary,
              "authors":authors,"year":year,"supporting_passages":passages or []})

def A(aid): 
    d=bib[aid]; return d['title'], d['authors'], yr(aid)

# 1
t,a,y=A('2604.09544')
add("https://arxiv.org/html/2604.09544",t,
 "THE most important adverse prior found. Publishes the recognition-vs-execution dissociation on harm at the parameter level, a double dissociation between harm generation and refusal, and a separability-vs-alignment ladder over OLMo3-7B. Iteration 1 mis-filed it as a pruning-only paper.",a,y,
 P("https://arxiv.org/html/2604.09544",
   "We further show that harmful response generation is dissociable",
   "Crucially, the identified parameters support the generation",
   "concentrating harmful-response dependence",
   "Across the OLMo3-7B checkpoint sequence",
   "pruning approximately 0.0005",
   "Our main experiments are performed on Llama3.1-8B-Instruct",
   "Metrics are StrongREJECT score (generation)",
   "We also observe a symmetric relationship",
   "Lastly, these results provide insight rather than a deployable defense"))
# 2
t,a,y=A('2603.05773')
add("https://arxiv.org/abs/2603.05773",t,
 "Names this iteration's two axes outright - Recognition Axis v_H ('Knowing') and Execution Axis v_R ('Acting') - and demonstrates a causal double dissociation on harm, with a layer-wise cosine between them. Tests no abliterated checkpoint. Framed as an attack paper (cs.CR), which the run's invariant forbids inheriting.",a,y,
 P("https://arxiv.org/abs/2603.05773",
   "positing that safety computation operates on two distinct subspaces",
   "we demonstrate a causal double dissociation",
   "which achieves State-of-the-Art attack success rates"))
# 3
t,a,y=A('2606.24952')
add("https://arxiv.org/html/2606.24952",t,
 "Publishes a per-checkpoint, weight-computable detection-vs-control cosine table over four models (0.12/0.20/0.16/0.13) and an instruction-tuning invariance (0.1197 vs 0.1200), on hallucination and output format rather than harm - plus the explicit negative result that the angle does not predict steerability. Grep for abliterat|uncensor: 0 matches.",a,y,
 P("https://arxiv.org/html/2606.24952",
   "The gap generalizes. Across four models",
   "What the cosine _is_ is a robust, weight-computable signature",
   "a 15",
   "the intervention (refusal) direction is hand-picked from lm_head alone"))
# 4
t,a,y=A('2511.14195')
add("https://aclanthology.org/2026.acl-long.1334.pdf","N-GLARE (ACL 2026 Long 1334): "+t,
 "The deliverable-level incumbent. Its illustrative example is EXACTLY this run's panel - base, RL-aligned and safety-removed Qwen3-4B. Needs four constructed dialogue families per model, so it is not a few-prompt method. Eq. 9 gives JR Min/Max. No numeric Kendall tau is printed anywhere; still no code as of 2026-09-21.",a,y,
 P("https://aclanthology.org/2026.acl-long.1334.pdf",
   "A higher value of JR Min/Max",
   "when com-",
   "remains consistently high",
   "benign (B), jailbreak (J), plainquery (P)"))
# 5
t,a,y=A('2603.27412')
add("https://arxiv.org/html/2603.27412",t,
 "One of the two papers that already publish the recognition-invariance headline: abliterated variants detect harm within 0.015 AUROC of their instruction-tuned parents, on Qwen3.5-0.8B and Qwen2.5-0.5B triplets. Crucially it measures NOTHING on the execution side (full-document grep, 9 matches, none a quantity).",a,y,
 P("https://arxiv.org/html/2603.27412",
   "First, geometry survives refusal ablation",
   "We evaluate two complete model triplets",
   "The model",
   "LatentBiopsy builds a normative reference exclusively",
   "Our findings suggest that such interventions address the generative mechanism"))
# 6
t,a,y=A('2604.18901')
add("https://arxiv.org/html/2604.18901",t,
 "The second scooping paper, absent from the current draft's reference list. Abliterated variants match their instruction-tuned counterparts within +/-0.003 AUROC across 12 models. Confirms iteration 1's four-quantity reading of the repeated 0.003 and 73 figures. Supplies the low-FPR reporting argument and the 100-labelled-examples budget.",a,y,
 P("https://arxiv.org/html/2604.18901",
   "matches its instruction-tuned counterpart within",
   "their TPR@1%FPR varies by more than ten times",
   "two pooling choices applied to the same chat-templated activations",
   "Gemma-3 is the exception",
   "Abliterated variants are community-produced",
   "A mean-difference direction fitted from 100 examples per class",
   "Across all four families, instruct-to-abliterated transfer",
   "The recovered direction is also nearly orthogonal"))
# 7 Jorak
add("https://github.com/JolanMc/Jorak","Jorak Model Scanner (modelscanner) - reference-free detection of abliteration in open-source LLMs",
 "NON-PEER-REVIEWED shipped open-source tool, verified live 2026-09-21. CLOSES BOTH X2 and X10: its 'suppression' signal is the normalised ||r^T W|| over o_proj/down_proj with r fitted from the candidate's OWN activations, and its Plan-1 A/B/S signals are a weights-only, zero-inference SVD subspace-alignment scar test. Validated 4/4 on a Qwen2.5-0.5B-derived matrix.",None,None,
 P("https://github.com/JolanMc/Jorak","Reference-free","Detector"))
# 8 Jorak metrics
add("https://raw.githubusercontent.com/JolanMc/Jorak/main/docs/METRICS.md","Jorak docs/METRICS.md - metric definitions and calibration",
 "NON-PEER-REVIEWED. Gives the exact formulae and calibrated thresholds: suppression = ||r^T W||/(||r||*||W||_F) with censored ~0.038 vs abliterated ~2e-8; global alignment A = sigma_1(U)/||U||_F with Qwen3-8B base A=0.184 vs Josiefied-Qwen3-8B-abliterated-v1 A=0.705; and a bottom-k subspace alignment S built for multi-direction ablations.",None,None,
 P("https://raw.githubusercontent.com/JolanMc/Jorak/main/docs/METRICS.md",
   "suppression","Calibration mesur","C'est","Qwen/Qwen3-8B","Les ablations modernes","L'id"))
# 9
t,a,y=A('2607.01854')
add("https://arxiv.org/abs/2607.01854",t,
 "The 273-checkpoint abliteration audit. THE DECIDING QUESTION IS ANSWERED: it is REFERENCE-ANCHORED on both signals - the activation refusal-gap fits directions on the base model, and the weight-recovery energy is computed on Delta W = W_base - W_candidate. AUROC 0.95 combined; 57 abliterations vs 37 benign negatives. It does NOT close X2 or X10.",a,y,
 P("https://arxiv.org/abs/2607.01854","we combine two cheap internal signals"))
# 10
t,a,y=A('2606.16349')
add("https://arxiv.org/html/2606.16349",t,
 "Baseline G10 and a headline adverse prior. Eq. 9 defines HRCI_repr = 1/2 C_cos + 1/2 C_sub; the authors state plainly that low coupling is not itself a safety score. Eq. 8's subspace dimension k is NEVER stated - only Table 1's three printed principal angles imply k=3 - so G10 is not reimplementable exactly as specified.",a,y,
 P("https://arxiv.org/html/2606.16349",
   "SFT supplies the negative control","drops from 0.0784 at step 50","For subspaces, let",
   "Principal angles","It was not optimized against ASR"))
# 11
t,a,y=A('2608.05086')
add("https://arxiv.org/abs/2608.05086",t,
 "The few-prompts incumbent that must be conceded by name: roughly ten adaptive items recover several individual benchmarks at 97-99% cost reduction, fit over 8 benchmarks and 192 models. Text-only, hence a baseline under the run's invariant, but it owns the few-prompt regime.",a,y,
 P("https://arxiv.org/abs/2608.05086","roughly ten adaptively chosen items","We fit IRT models to eight safety benchmarks",
   "three interpretable factors of refusal strictness"))
# 12
t,a,y=A('2603.18353')
add("https://arxiv.org/html/2603.18353",t,
 "The knowledge-action gap paper. 98.2% probe AUROC vs 45% output sensitivity, a 53-point gap, across four intervention arms. CORRECTS the hypothesis text: 'zero corrections and zero disruptions' is true of the SAE arm only; Arm 1 corrected 17/85 and disrupted 25/47 (that is the random-indistinguishable arm), and TSV corrected 19/79 while disrupting 4/65.",a,y,
 P("https://arxiv.org/html/2603.18353",
   "At baseline, Steerling-8B detected 51 of 144","Linear probes trained on Qwen",
   "Concept bottleneck steering corrected 17 of 85","SAE feature steering produced zero corrections",
   "for correcting false-negative triage errors","Hazard-feature steering at"))
# 13
t,a,y=A('2607.14147')
add("https://arxiv.org/html/2607.14147v1",t,
 "Defines the exact X5 statistic - concentration = delta p_refuse / (-delta p_comply) - but computes it only as a knockout-conditioned paired contrast between one instruct checkpoint and its base anchor (Qwen2.5-1.5B, n=60), never as a parent-free per-checkpoint score. Instruct routes ~8x more freed mass to refusal than base (0.24 vs 0.03).",a,y,
 P("https://arxiv.org/html/2607.14147v1","the instruct model routes it to refusal tokens about 8"))
# 14
t,a,y=A('2506.24056')
add("https://arxiv.org/abs/2506.24056",t,
 "X3's nearest relative: a per-prompt refusal-minus-affirmative logit GAP at the first decoding step, over pre-identified lexical refusal and affirmative tokens. Not an analytic slope with respect to a continuous harm projection, and undefined for a safe-completion model with no lexical refusal token.",a,y,
 P("https://arxiv.org/abs/2506.24056","We introduce the refusal-affirmation logit gap"))
# 15
t,a,y=A('2609.01936')
add("https://arxiv.org/abs/2609.01936",t,
 "Decomposes the readout using only its weights and expresses any token logit or logit difference as a sum of sparse-feature contributions - structurally close to X3. CORRECTION to the planning seed: its abstract contains no mention of safety, refusal or harm; the safety-audit application appears only in Section 6 Future Work and is proposed, not executed.",a,y,
 P("https://arxiv.org/abs/2609.01936","we introduce Sparse Readout Prism (SRP)"))
# 16
t,a,y=A('2605.20241')
add("https://arxiv.org/abs/2605.20241",t,
 "X1's runner-up. Summarises layer-wise margin profiles by boundary position, layer-to-layer change and coarse shape, across nine instruction-tuned backbones and seven benchmarks - but per prompt, then pooled into detection AUROC, never as a per-model number used to rank checkpoints.",a,y,
 P("https://arxiv.org/abs/2605.20241","then summarizes the resulting margin profiles"))
# 17
t,a,y=A('2609.13534')
add("https://arxiv.org/abs/2609.13534",t,
 "X1's single nearest work: extracts slope, curvature, monotonicity and onset layer from the cross-layer harm projection sequence - almost exactly X1's operations - but as a seven-dimensional PER-INSTANCE feature record fed to a 288-parameter MLP input moderator, not a per-checkpoint score.",a,y,
 P("https://arxiv.org/abs/2609.13534","extracts a seven-dimensional feature record"))
# 18
t,a,y=A('2609.07139')
add("https://arxiv.org/abs/2609.07139",t,
 "X8's single nearest work: decodability peaks early and falls to near chance before the midpoint while causal efficacy arrives late - the readable-before-usable depth lag - but on inferred partner expertise, one model, a synthetic corpus, and with no numeric per-model lag.",a,y,[])
# 19
t,a,y=A('2609.01048')
add("https://arxiv.org/abs/2609.01048",t,
 "A strong general adverse prior on any read-vs-act construct: across the Pythia suite a probe reads the target from step 1,000 at every scale, yet steering along that same direction is null-equivalent in 43 of 48 model-checkpoint cells. Note its axis is TRAINING STEP, not depth, so it does not close X8.",a,y,
 P("https://arxiv.org/abs/2609.01048","yet steering along that same reading direction remains null-equivalent"))
# 20
t,a,y=A('2608.17843')
add("https://arxiv.org/abs/2608.17843",t,
 "Multi-backbone decode-generate-steer gap on geometric constraints: decodable information is not always actionable. Off-concept, and a full-document grep confirms it never quantifies the depth lag numerically (0 matches for onset layer / depth-fraction / layers apart / layer gap).",a,y,[])
# 21
t,a,y=A('2605.12726')
add("https://arxiv.org/abs/2605.12726",t,
 "The adverse prior constraining how the run may describe r_ablit, which is fitted at the last prompt token: last-token probes keep high recall on clean harmful prompts but miss many jailbreaks and false-positive on safety-adjacent benign prompts. ICML 2026 Mechanistic Interpretability Workshop.",a,y,
 P("https://arxiv.org/abs/2605.12726","Token-level prefill analyses reveal"))
# 22
t,a,y=A('2512.13655')
add("https://arxiv.org/abs/2512.13655",t,
 "Target 5. The planner's attributed figures (a 'minimum effective dose' at >=30% refusal bypass, MMLU max degradation 0.028) are NOT PRINTED - confirmed absent across all three retrieval rungs. What it actually reports is a four-TOOL comparison over 16 models with no intensity sweep and no dose axis.",a,y,
 P("https://arxiv.org/abs/2512.13655","Single-pass methods demonstrated superior capability preservation"))
# 23
t,a,y=A('2607.17427')
add("https://arxiv.org/abs/2607.17427",t,
 "Preregistered off-target study of abliteration with exactly two arms per family (base vs abliterated; Gemma-4-26B-A4B-it and Qwen3-30B-A3B), 21,600 decisions. Not a dose curve. Also documents two toolchain contamination channels in community-modified checkpoints.",a,y,
 P("https://arxiv.org/abs/2607.17427","abliterated models are systematically more optimistic"))
# 24
t,a,y=A('2505.19056')
add("https://arxiv.org/abs/2505.19056",t,
 "The extended-refusal defence: refusal rates drop by at most 10% under abliteration versus 70-80% in baseline models. Compares defended vs undefended models, not abliteration strengths, so it is not the dose curve either.",a,y,
 P("https://arxiv.org/abs/2505.19056","refusal rates drop by at most 10%"))
# 25
t,a,y=A('2603.10012')
add("https://arxiv.org/abs/2603.10012",t,
 "Applies Heretic once to a military-tuned gpt-oss-20b: +66.5 points absolute answer rate, -2% average relative on other military tasks. A single abliteration operating point, not a graded curve.",a,y,
 P("https://arxiv.org/abs/2603.10012","showing an absolute increase in answer rate of 66.5 points"))
# 26
add("https://go.alice.io/hubfs/alice-abliteration-report-april2026.pdf","One Pass to Break Them All: Empirical Analysis of Activation-Space Abliteration on LLM Safety Alignment (Alice Research)",
 "NON-PEER-REVIEWED industry report, March 2026. Reports baseline vs post-abliteration only (five safety-trained models, 94.2% -> 98.0% compliance over 550 prompts) - again no dose axis - and independently states that safety training succeeded at harm detection but failed at harm refusal, calling them separable functions.",None,2026,
 P("https://go.alice.io/hubfs/alice-abliteration-report-april2026.pdf","training succeeded at harm detection"))
# 27
t,a,y=A('2608.30585')
add("https://arxiv.org/abs/2608.30585",t,
 "A fourth independent statement of the same pattern, from the roleplay-jailbreak side: successful attacks retain the harmful-vs-benign distinction at the request while its refusal-associated expression weakens where the answer begins - 'safety-relay attenuation'. Matched harmful/benign x wrapper design confirmed; per-condition numeric tables not extracted within budget.",a,y,
 P("https://arxiv.org/abs/2608.30585","Successful attacks retain the measured harmful-versus-benign distinction"))
# 28
t,a,y=A('2609.14754')
add("https://arxiv.org/abs/2609.14754",t,
 "CLOSES iteration 1's follow-up (d): the companion methods note DOES have a standalone arXiv id. Directly relevant to this run's null-band and instrument-integrity machinery. Code at github.com/deepsteer/deepsteer.",a,y,
 P("https://arxiv.org/abs/2609.14754","Calibrating Interpretability Instruments"))
# 29
t,a,y=A('2508.09224')
add("https://arxiv.org/abs/2508.09224",t,
 "OpenAI's own safe-completions paper, incorporated into GPT-5. Evaluated entirely at the output level - production comparisons and internally controlled experiments - with no internal activation, probe or logit-lens readout. Supports the clean NOT-FOUND on internally scoring a safe-completion model.",a,y,
 P("https://arxiv.org/abs/2508.09224","safe-completion training improves safety"))
# 30
t,a,y=A('2607.02047')
add("https://arxiv.org/abs/2607.02047",t,
 "The follow-on safe-completion evaluation, again purely behavioural: it recommends evaluating safe completion as intent-calibrated behaviour over controlled task variants. Second primary source behind the NOT-FOUND for an internal safe-completion readout.",a,y,[])
# 31
t,a,y=A('2607.00572')
add("https://arxiv.org/html/2607.00572v1","HARC: "+t,
 "Appendix A.3's cross-layer projection profiles - the exact object X1 ratios over - are reported as heat-map FIGURES only and are never reduced to a per-model scalar, which is why X1 survives as PARTIAL. HARC's one per-model scalar is a single-layer v_harm/v_ref coupling, a different quantity.",a,y,[])
# 32
t,a,y=A('2406.11717')
add("https://arxiv.org/abs/2406.11717",t,
 "The foundational refusal-direction paper, with its full seven-author list recovered and its NeurIPS 2024 venue cross-checked against the proceedings PDF. CORRECTION to a planning seed: it does not logit-lens the refusal direction to show it decodes to refusal words; unembedding directions appear only as an exclusion filter in its direction-selection procedure.",a,y,[])
# 33
add("https://proceedings.neurips.cc/paper_files/paper/2024/file/f545448535dfde4f9786555403ab7c49-Paper-Conference.pdf",
 "Refusal in Language Models Is Mediated by a Single Direction (NeurIPS 2024 proceedings PDF)",
 "Venue cross-check for the bibliography correction: the proceedings first page carries the same seven authors with affiliations (Independent, ETH Zurich, University of Maryland, ETH Zurich, Anthropic, MIT).",
 ["Andy Arditi","Oscar Obeso","Aaquib Syed","Daniel Paleka","Nina Panickssery","Wes Gurnee","Neel Nanda"],2024,[])
# 34
t,a,y=A('2507.11878')
add("https://arxiv.org/abs/2507.11878",t,
 "The correct citation for the harmfulness/refusal split, currently cited in the draft with no authors. Full author list recovered.",a,y,[])
# 35
t,a,y=A('2502.17420')
add("https://arxiv.org/abs/2502.17420",t,
 "Bibliography correction: full six-author list recovered with correct diacritics (Wollschlaeger, Guennemann). Part of the abliteration-dimensionality line predicting that a rank-one scar is incomplete - a prediction Jorak's bottom-k subspace signal already acts on.",a,y,[])
# 36
t,a,y=A('2411.09003')
add("https://arxiv.org/abs/2411.09003",t,
 "Bibliography entry confirmed correct as printed. Part of the affine/multi-dimensional refusal line.",a,y,[])
# 37
t,a,y=A('2609.14759')
add("https://arxiv.org/abs/2609.14759",t,
 "The closest thing to a cross-model routing statistic, but a different construct: a subspace-RANK causal-transfer share (76% of refusal's causal input outside the rank-16 moral basis), reported for one model (OLMo-3) only, with the other families described qualitatively.",a,y,[])
# 38
t,a,y=A('2608.05578')
add("https://arxiv.org/abs/2608.05578",t,
 "Checked as a possible X2 closer. Scores activation geometry for safety-training modification but carries no weight-side companion signal that would close the weight-space write-mass lane.",a,y,[])
# 39
add("https://huggingface.co/DrExe/qwen3-safety-vectors","DrExe/qwen3-safety-vectors (HuggingFace)",
 "Checked per the plan. Returns HTTP 401 on both the model page and the api/models endpoint as of 2026-09-21, i.e. gated or private. Existence and contents could not be confirmed from an unauthenticated fetch, so nothing about it should be asserted.",None,None,[])
# 40
add("https://huggingface.co/blog/grimjim/orthogonal-reflection-bounded-ablation","ORBA: Orthogonal Reflection Bounded Ablation",
 "NON-PEER-REVIEWED community post. A method for PERFORMING bounded directional ablation, not a detection metric; supplies the geometric background for why rank-one weight interventions leave a detectable scar but does not itself close X2 or X10.",None,2026,[])

Path('sources_draft.json').write_text(json.dumps(S,indent=1))
print("sources:",len(S))
for s in S:
    print(s['index'], len(s['supporting_passages']), s['url'])
