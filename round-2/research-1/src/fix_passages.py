import json, re, unicodedata
from pathlib import Path

def ws(s):
    return re.sub(r"\s+"," ",unicodedata.normalize("NFC",s)).strip()

DOCS={}
for p in Path("strict_cache").glob("*.txt"):
    DOCS[p.name]=ws(p.read_text())
def doc(url):
    return DOCS[re.sub(r"[^A-Za-z0-9]+","_",url)[:150]+".txt"]

ABS_DSH="https://arxiv.org/abs/2603.05773"
MET="https://raw.githubusercontent.com/JolanMc/Jorak/main/docs/METRICS.md"
AUD="https://arxiv.org/abs/2607.01854"
OKA="https://arxiv.org/abs/2609.07139"
RRR="https://arxiv.org/abs/2609.14759"
DSHH="https://arxiv.org/html/2603.05773v2"

# index -> full replacement passage list (locator, quote)
REPLACE={
 2:[("Abstract","Safety alignment is often conceptualized as a monolithic process wherein harmfulness detection automatically triggers refusal. However, the persistence of jailbreak attacks suggests a fundamental mechanistic decoupling."),
    ("Abstract","positing that safety computation operates on two distinct subspaces"),
    ("Abstract","Our geometric analysis reveals a universal ``Reflex-to-Dissociation'' evolution, where these signals transition from antagonistic entanglement in early layers to structural independence in deep layers."),
    ("Abstract","we demonstrate a causal double dissociation, effectively creating a state of ``Knowing without Acting.''"),
    ("Abstract","which achieves State-of-the-Art attack success rates by surgically lobotomizing the refusal mechanism")],
 8:[("docs/METRICS.md, Plan 1 metric table","`suppression_ℓ = ‖r̂ᵀW‖ / (‖r̂‖·‖W‖_F)` pour `W ∈ {o_proj, down_proj}`, par couche."),
    ("docs/METRICS.md, suppression calibration","Calibration mesurée : censuré ≈ `0.038` vs abliteré ≈ `2e-8`. Le seuil `≤ 1e-2` les sépare nettement (0.038 > 0.01 > 2e-8)."),
    ("docs/METRICS.md, Section 1 (Plan 1 - JORAK)","C'est **le cœur** du projet (« la technique mise en avant »). NumPy pur, sans inférence."),
    ("docs/METRICS.md, Section 1.1 svd_alignment","Pour chaque couche, on prend `u_min` = le vecteur singulier gauche de **plus petite** valeur singulière de `W` (la direction « la moins écrite »). On empile les `u_min` en `U ∈ ℝ^{n×d_model}`, puis **A = σ₁(U) / ‖U‖_F**"),
    ("docs/METRICS.md, Section 1.1 worked values","**Qwen/Qwen3-8B (base, censuré)** : `A = 0.184` ≈ le plancher 0.167 → `u_min` dispersés, **aucune** direction partagée → poids intacts."),
    ("docs/METRICS.md, Section 1.1 worked values","**Josiefied-Qwen3-8B-abliterated-v1** : `A = 0.705` → forte direction commune → poids sectionnés."),
    ("docs/METRICS.md, Section 1.3 subspace_alignment","Gabliteration) retirent un **sous-espace de k directions** (`n_directions ≈ 4`), pas une seule."),
    ("docs/METRICS.md, Section 1.3 subspace_alignment","On agrège les projecteurs `M = Σ_ℓ B_ℓ B_ℓᵀ`, puis **S = (somme des k plus grandes valeurs propres de M) / (n·k)**."),
    ("docs/METRICS.md, reference-free rationale","L'idée-clé **reference-free** : on n'a pas besoin de générer ni de comparer à un original pour séparer *censuré* de *ablated*")],
 9:[("Abstract","We combine two cheap internal signals, a reference-anchored activation refusal-gap and a weight-recovery energy of the base-to-candidate weight difference, into a threshold-free checkpoint audit."),
    ("Abstract","The audit is effective triage, not tamper-proofing: it presumes an attested reference, and its claims are bounded by the registry we evaluate it on."),
    ("Abstract","a spoofed reference evades both axes with no training")],
 18:[("Abstract","partner expertise is most decodable in the early layers and falls to near chance before the midpoint of the network."),
     ("Abstract","An inferred relational attribute is therefore represented well before it becomes causally active"),
     ("Abstract","We use one model on a synthetic corpus as an initial demonstration.")],
 37:[("Abstract","The central result is causal and comes from one model, OLMo-3."),
     ("Abstract","about three-quarters of refusal's causal input lies outside the moral subspace altogether."),
     ("Abstract","The picture is not uniform across families. Llama reads broad moral content; Qwen reads beyond the single harm cue but is unresolved at our sample size; GPT-OSS reads harm, and its refusals can be argued in either direction by its own reasoning trace.")],
 41:[("Section 4, Figure 4 caption","The dashed line and grey band represent the mean and 95% confidence interval of 1000 random vector pairs, respectively. In deep layers, the safety axes’ similarity converges to this random baseline, confirming the “Reflex-to-Dissociation” pattern."),
     ("Section 3 (Models)","Models. We evaluate three aligned models spanning distinct architectural lineages: Llama-3.1-8B-Instruct, Mistral-7B-Instruct-v0.2, and Qwen2.5-7B-Instruct.")],
}

d=json.load(open("research_out.json"))
src=d["sources"]
dropped=[]
for idx,newp in REPLACE.items():
    s=src[idx-1]; url=s["url"]; t=doc(url)
    kept=[]
    for loc,q in newp:
        if ws(q) in t: kept.append({"quote":q,"locator":loc})
        else: dropped.append((idx,url,q))
    s["supporting_passages"]=kept
json.dump(d,open("research_out.json","w"),indent=1)
print("DROPPED (not literal):")
for idx,u,q in dropped: print(" ",idx,u,"|",q[:110])
print("done")
