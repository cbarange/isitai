# Le fallback probabiliste et le coefficient de certitude — recherche du 2026-11-12

Document de recherche. Aucun code modifié. Il prolonge `docs/research/ROADMAP-detection.md`,
dont il ne répète pas les mesures : il traite la question laissée ouverte — quand aucune
signature n'existe, que peut-on affirmer, et comment l'exprimer sans mentir.

Conventions identiques : **[V]** vérifié sur une source primaire citée, **[J]** jugement du
rédacteur, **non trouvé** cherché sans résultat. Une mesure faite ici est marquée **[M]**.

## 1. Résumé

1. **Un pourcentage de vérité est impossible à produire.** Pas par prudence : par
   arithmétique. Un détecteur à 99 % de sensibilité et 99 % de spécificité se trompe une fois
   sur deux quand il accuse, sur une population où l'IA représente 1 % (§2).
2. **La seule quantité défendable est un rapport de vraisemblance**, accompagné de son
   intervalle et de la prévalence supposée. La probabilité a posteriori n'est calculable que
   si l'appelant fournit sa prévalence — elle ne peut pas être devinée par la bibliothèque.
3. **Le levier de précision le plus rentable n'est pas un détecteur de plus, c'est la
   calibration conditionnelle** : les scores se décalent par langue, par domaine et par
   générateur. Mesuré ici : au seuil réglé pour 1 % de faux positifs en anglais, les deux
   détecteurs de texte du projet en font **10 % en français** et 0 % dans les dix autres
   langues testées (§3.1).
4. **Le meilleur gain immédiat, sans modèle ni seuil, est documentaire** : chaîne de
   métadonnées PDF/DOCX, empreintes de générateurs, cohérence Info/XMP. Déterministe, coût
   quasi nul, et c'est ce que personne ne fait (§4).
5. **Les produits commerciaux ne résolvent pas le problème** : leurs chiffres publics
   tombent à 0,78–0,89 en conditions réelles, et le plus documenté d'entre eux plafonne à
   49 % d'exactitude pour 57 % de fausses accusations sur un banc indépendant (§5).
6. **La fusion n'est pas un levier de performance, c'est un mécanisme d'abstention.** Le
   projet l'a déjà mesuré : l'empilement ne bat pas le meilleur détecteur seul hors
   distribution. Elle sert à dire « je ne sais pas », pas à gagner des points (§6).

## 2. Le taux de base : pourquoi « 99 % » est un mensonge arithmétique

Soit un détecteur à sensibilité 0,99 et spécificité 0,99. Le rapport de vraisemblance positif
vaut `LR+ = Se / (1 − Sp) = 99`. La valeur prédictive positive dépend entièrement de la
prévalence `p` de contenus IA dans la population analysée :

| Prévalence de l'IA | VPP quand le détecteur accuse | Faux positifs par million |
|---|---|---|
| 1 % | **50 %** | 9 900 |
| 10 % | 91,7 % | 900 |
| 50 % | 99 % | 100 |

À 1 % de prévalence — l'ordre de grandeur d'un flux web quelconque, non mesuré — « 99 % de
sensibilité, 99 % de spécificité » signifie : **une accusation sur deux est fausse**.

Pour obtenir une VPP de 90 % à 1 % de prévalence, il faut une spécificité de **99,89 %** ;
pour 95 %, **99,947 %**. Aucun détecteur du banc du projet n'approche ces valeurs : au seuil
de 1 % de faux positifs, la spécificité vaut 99 % par construction.

Conséquences pour la bibliothèque [J] :

- Ne jamais rendre un pourcentage. Un `confidence: 0.97` sera lu comme « 97 % de chances »,
  et c'est faux.
- Rendre `lr` (rapport de vraisemblance) et `lr_interval`. L'appelant combine avec sa propre
  prévalence s'il en a une.
- Si une prévalence est fournie, rendre `posterior` **et** `prevalence_used`, pour que le
  chiffre reste reproductible.
- Refuser un verdict d'autorité : la littérature forensique (ENFSI) impose exactement cette
  forme — force de l'évidence, pas probabilité de culpabilité.

Ce point n'est pas un détail de présentation : c'est ce qui distingue un outil utilisable
devant un comité d'éthique d'un gadget qui fait accuser des étudiants.

## 3. Calibration : ce que le projet peut mesurer, et où ça casse

### 3.1 Mesure faite ici : le décalage est par langue

**[M]** Sur `bench/detectors/results/corpus_scores.json` — corpus Wikipédia humain, 12
langues, 9 à 10 textes par langue — au seuil enregistré (`thr@1`, réglé pour 1 % de faux
positifs) :

| Langue | Binoculars-small | Fast-DetectGPT | n |
|---|---|---|---|
| fr | **10 %** au-dessus du seuil | **10 %** | 10 |
| pt | 0 % | **11 %** | 9 |
| ar, de, en, es, it, ja, nl, pl, ru, zh | 0 % | 0 % | 9–10 |

Lecture prudente : la granularité est de 10 points (un texte sur dix). Ce n'est pas un taux,
c'est un signal — mais il est net et il localise le problème. Ce n'est pas le détecteur qui
dérive uniformément : **c'est la distribution des scores qui se décale par langue**, et le
français est la langue la plus décalée.

Deux détecteurs, deux comportements sur le seul texte IA du corpus (`ai-snowman`) :
Binoculars-small le place **sous** son seuil (raté), Fast-DetectGPT **au-dessus** (détecté).
Corrélation de rang entre les deux sur les 117 textes humains communs : **0,46** — donc
partiellement indépendants [M].

Ce que ça implique [J] : une correction par langue (décalage mesuré, pas un modèle) est
moins coûteuse et plus efficace qu'un détecteur supplémentaire. Et la mesure du français
doit être refaite sur un corpus sérieux : 10 textes ne suffisent pas à publier un taux.

### 3.2 Ce qu'il faut mesurer, et comment

| Élément | Méthode | Pourquoi |
|---|---|---|
| Étalonnage | reliability diagram, ECE, Brier, NLL **par sous-groupe** (langue, générateur, modalité) | une ECE globale cache un groupe à 30 % d'écart |
| Correction d'échelle | temperature scaling (1 paramètre, préserve l'argmax) puis isotonic si assez de données | un softmax n'est pas une probabilité (Guo et al., 2017) |
| Intervalle | prédiction conforme, seuil `q̂ = ⌈(n+1)(1−α)⌉`-ième score, couverture **marginale** | garantit `P(Y ∈ C(X)) ≥ 1−α` sous échangeabilité seulement |
| Robustesse au décalage | re-calibration par générateur, ou méthodes robustes (Ovadia et al., 2019) | nouveau générateur = distribution nouvelle |

Limite à écrire dans la doc : la couverture conforme est marginale, pas conditionnelle. Elle
ne promet rien sur un fichier donné. Un intervalle qui chevauche le seuil doit produire
`indeterminate` — une réponse, pas un échec.

### 3.3 Les corpus de calibration, et leur mensonge intégré

RAID, MAGE, AIGIBench, Deepfake-Eval-2024 sont **échantillonnés par classe**, souvent
50/50. Ils donnent des LR et des intervalles ; ils ne donnent **jamais** une prévalence. Un
taux de faux positifs calculé dessus ne dit rien du comportement sur un flux réel.

Pour la prévalence, seule une méthode esthonnête : un échantillon stratifié du trafic visé,
avec adjudication humaine, et le plan de sondage écrit à côté du chiffre. Tant que ce
sondage n'existe pas, `prevalence_used` doit valoir `null` et `posterior` aussi.

## 4. Par modalité : ce qui est réellement faisable

### 4.1 Documents (PDF, DOCX) — le meilleur rapport précision/coût, sans modèle

Rien de probabiliste ici : ce sont des empreintes de chaîne de production.

| Signal | Force | Note |
|---|---|---|
| C2PA | preuve | déjà en place dans le projet |
| Cohérence `/Info` ↔ XMP (`Producer`, `Creator`, `CreatorTool`, `xmpMM:History`) | indice fort | une divergence trahit une réécriture |
| Chaîne de production : `Skia/PDF` (exports Chrome, donc ChatGPT/Gemini), ReportLab, WeasyPrint, Typst, pdfTeX, `Microsoft® Word` | indice | bibliothèque Python sur un document « institutionnel » = indice fort, pas preuve |
| Sous-ensembles de polices (préfixe 6 majuscules + `+` dans `/BaseFont`) | indice | survit au stripping ; deux sous-ensembles de la même police = collage |
| **DOCX `python-docx` par défaut** : `creator="python-docx"`, `created=modified=2013-12-23T23:15:00Z`, `revision=1`, `Words=0` | **quasi déterministe** [V] | vérifié sur le template du dépôt python-docx |
| Absence d'EXIF caméra, tables de quantification libjpeg, PNG sans chunks annexes | indice | non validé publiquement |

Piège à documenter : `PDFuzz` (arXiv 2508.01887) réordonne l'extraction de texte sans changer
le rendu et fait tomber un détecteur de 93,6 % à 50,4 %. **Tout détecteur de texte appliqué à
du PDF extrait est attaquable** — la couche documentaire doit rester déterministe, et le
texte extrait ne doit pas hériter de la confiance du document.

### 4.2 Audio — le meilleur compromis conditions réelles / coût

| Modèle | EER labo (ASVspoof19 LA) | EER réel (InTheWild) | Taille | Licence |
|---|---|---|---|---|
| AASIST | 0,83 % | **43,01 %** | 0,3 M param. | MIT |
| W2V2-AASIST (XLS-R + AASIST) | 0,22 % | **11,22 %** | 318 M | MIT |
| XLSR-SLS | — | 7,46 % (voix clonée) | 341 M | MIT |

Trois ordres de grandeur d'écart entre labo et réel : c'est la preuve qu'un chiffre
d'ASVspoof ne doit jamais être publié sans son pendant « in the wild ».

Recommandation [J] : AASIST (1–2 Mo) dans le paquet de base comme **indice faible**, et
W2V2-AASIST dans le paquet optionnel comme détecteur sérieux, tous deux sortant un LR et non
un verdict. AudioSeal reste la seule couche à pouvoir produire `ai-signal` en niveau
`standard` — un watermark n'est pas une estimation.

### 4.3 Image — un petit modèle surpasse le commercial moyen

- **FerretNet** : 1,1 M paramètres, Apache-2.0, 97,1 % de moyenne sur 22 générateurs, entraîné
  sur ProGAN seul (arXiv 2509.20890). Meilleur rapport précision/coût CPU, et redistribuable.
- **AEROBLADE** : erreur de reconstruction par l'autoencodeur du modèle de diffusion, AP 0,992
  sur SD/Kandinsky/Midjourney, sans entraînement — mais seulement pour la diffusion latente,
  et licence non explicite.
- **NPR** : +11,6 % sur 28 générateurs en labo, mais **F.Acc de 95,9 % à 12,2 %** après un
  simple JPEG/redimensionnement (AIGIBench). Illustration parfaite de ce que « capture
  d'écran » fait à un détecteur.
- Fréquentiel (FFT/DCT) : 66–75 % sur AIGIBench. Bon marché, mais le rééchantillonnage
  déplace le pic haute fréquence.
- Sondes linéaires CLIP/DINOv2 : 82–84 % sur générateurs non vus, au prix d'un ViT-L.

Recommandation [J] : FerretNet en `deep`, avec un avertissement mesuré sur les entrées
recompressées. Community Forensics (déjà évalué dans la roadmap) reste le concurrent direct.

### 4.4 Texte — le plus dur, et déjà bien mesuré par le projet

Rien à ajouter au banc existant. Deux compléments utiles :

- **RADAR** (RoBERTa + paraphraser adverse, Apache-2.0) : 70,9 % → 67,3 % sous paraphrase, là
  où GLTR perd 15 points. C'est la seule famille qui survit à la paraphrase sans LLM géant.
- **Français** : CamemBERTa affiné donne F1 0,97 en test mais **0,45 en adversarial**, et sa
  carte est réservée à la recherche — donc non redistribuable. Binoculars reste le meilleur
  zéro-shot d'après le PEReN (2025).

Et la contrainte de fond, qui n'a pas bougé : **la traduction casse tout** (couple de LM,
watermarks). Aucune étude n'isole la traduction seule — non vérifié.

### 4.5 Vidéo — trois signaux avant tout modèle

1. Conteneur et métadonnées (`udta`, `©too`, XMP) — déterministe, 0 coût.
2. **Vecteurs de mouvement H.264** : incohérence temporelle pour un coût quasi nul, sans
   décodage RGB complet. Seule voie CPU réaliste sur un extrait de quelques secondes.
3. Piste audio, avec les modèles du §4.2 — souvent plus fiable que l'image.

Le classifieur par frame reste un tie-break : GenConViT passe de 0,96 d'AUC en labo à 0,63 en
réel (Deepfake-Eval-2024), et un modèle affiné remonte à 0,82 — donc entraîner sur le réel
change tout, mais ce n'est pas le sujet d'une bibliothèque hors ligne.

## 5. Ce que font les produits commerciaux

Chiffres **indépendants** uniquement (les benchmarks maison ne sont pas des preuves) :

| Service | Modalités | Chiffre indépendant | Source |
|---|---|---|---|
| Reality Defender | image, audio, vidéo | 93,51 % exactitude, 5,53 % de fausses acceptations | Purdue 2025 |
| AI or Not | tout | 89,22 % / 12,00 % | Purdue 2025 |
| Hive | tout | 83,62 % / 18,50 % | Purdue 2025 |
| Illuminarty | image | 49,37 % / **57,07 %** | Purdue 2025 |
| Deepware | vidéo (faces) | FNR 68,1 % | ACM 2024 |
| Copyleaks | texte | 64,8 % sur IA brute, **5 faux positifs sur 10 témoins humains** | aitruthbench |
| Originality.ai | texte | 85 % à 5 % de FPR (RAID), 1er des 12 commerciaux | RAID ACL 2024 |

Deux constats qui valent pour le projet :

- **Le meilleur commercial plafonne à 0,82–0,89** en conditions réelles (Deepfake-Eval-2024 :
  1 975 images, 45 h vidéo, 56,5 h audio in the wild). Les « 99 % » des pages produit ne
  décrivent que leur propre banc.
- **Le biais linguistique est documenté** : Liang et al. (Patterns 2023) mesurent 61,22 % de
  textes TOEFL classés IA contre 5,19 % pour des natifs. Publier un FPR par langue n'est pas
  une coquetterie : c'est la seule défense contre l'usage punitif.

Ce qu'ils ont et que le projet n'a pas : l'attribution du générateur (Hive : ~55 générateurs),
la localisation par région ou par phrase, et un état explicite « non concluant ». Les deux
premiers coûtent cher ; le troisième est gratuit et devrait exister dès la v0.2.

## 6. Fusion : ce qu'elle peut et ne peut pas faire

Le projet a mesuré que l'empilement ne bat pas le meilleur détecteur hors distribution. Ma
mesure (corrélation de rang 0,46) dit autre chose : les deux détecteurs ne sont pas
redondants, donc il y a de l'information à combiner — mais pas là où le banc l'a cherchée.

Position défendable [J] :

- **Fusionner en log-LR, jamais en moyenne de scores.** Une moyenne suppose le même événement
  et l'indépendance conditionnelle : faux ici.
- **Décoter la corrélation par famille** (shrinkage vers LR = 1). Mieux vaut sous-estimer la
  preuve que fabriquer de la certitude.
- **Abstention sur conflit** : deux couches franchement opposées doivent produire
  `inconsistent` ou `indeterminate`, pas un compromis.
- **Ne pas dépasser deux ou trois couches fusionnées.** Au-delà, on empile des corrélations
  qu'on ne mesure pas.

Dempster-Shafer peut représenter l'ignorance, jamais gonfler la confiance : la règle de
combinaison est agressive et connue pour produire des paradoxes sur des sources en conflit.

## 7. Architecture proposée

```
                 ┌─────────────────────────────────────────────┐
   fichier  ───► │ 0. Provenance (déterministe)                │
                 │    C2PA signé + trust list → ai-proven      │
                 │    capture-proven / inconsistent            │
                 └───────────────┬─────────────────────────────┘
                                 │ pas de preuve
                 ┌───────────────▼─────────────────────────────┐
                 │ 1. Détecteurs par famille                   │
                 │    documentaire · watermark · artefacts     │
                 │    · sémantique                             │
                 │    sortie : log-LR + domaine de validité    │
                 └───────────────┬─────────────────────────────┘
                 ┌───────────────▼─────────────────────────────┐
                 │ 2. Calibration conditionnelle               │
                 │    table par langue / générateur / modalité │
                 │    → intervalle conforme                    │
                 └───────────────┬─────────────────────────────┘
                 ┌───────────────▼─────────────────────────────┐
                 │ 3. Fusion (Σ log-LR, corrélation décotée)   │
                 │    conflit → abstention                     │
                 └───────────────┬─────────────────────────────┘
                 ┌───────────────▼─────────────────────────────┐
                 │ 4. Décision : verdict + coefficient         │
                 │    posterior SEULEMENT si prévalence fournie│
                 └─────────────────────────────────────────────┘
```

Forme de sortie proposée, qui remplace `confidence: float` :

```json
{
  "verdict": "ai-likely",
  "coefficient": {
    "lr": 12.4,
    "lr_interval": [4.1, 37.2],
    "coverage": 0.9,
    "calibration_id": "text-fastdetectgpt/smollm2-135m/fr/2026-11-12",
    "prevalence_used": null,
    "posterior": null
  },
  "notes": ["langue détectée : fr", "couche calibrée sur 990 textes, 10 par langue"]
}
```

Trois règles qui rendent `calibration_id` utile : il nomme le modèle, la langue, la date de la
table ; une table absente interdit de rendre un `lr` (on rend `null` et un `warning`) ; toute
mise à jour de la table change l'identifiant, donc un rapport ancien reste interprétable.

## 8. Incréments proposés, dans l'ordre

| # | Incrément | Coût | Pourquoi maintenant |
|---|---|---|---|
| A | **Couche documentaire déterministe** (PDF/DOCX : chaîne Producer, sous-ensembles, template python-docx) | 0 modèle | meilleur rapport précision/coût de tout le document, et personne ne le fait |
| B | **Harnais de calibration** : tables par langue/générateur, intervalle conforme, `calibration_id` | 0 modèle | sans lui, aucun coefficient n'est publiable |
| C | `sd-watermark` (déjà prévu, incrément 3 de la roadmap) | petit | premier signal `standard` propre |
| D | Audio : AASIST en `deep` | 1–2 Mo | indice faible mais honnête ; W2V2-AASIST en optionnel |
| E | Image : FerretNet | 4 Mo | Apache-2.0, 97,1 % sur 22 générateurs |
| F | Texte : seuil par langue **avant** tout nouveau modèle | 0 | corrige 10 % de faux positifs français sans rien ajouter |

L'ordre B avant C–E est volontaire : un détecteur sans table de calibration produit un chiffre
qui ne vaut pas la peine d'être affiché.

## 9. Affirmations non vérifiées

| Affirmation | État |
|---|---|
| Taux de faux positifs réel par langue sur un corpus sérieux | Mesuré ici sur 10 textes par langue seulement |
| NPR, FerretNet : licence effective des poids | Licence du dépôt lue, pas celle des checkpoints |
| AEROBLADE : redistribution autorisée | Aucune licence explicite trouvée |
| Surcoût CPU de FerretNet et d'AASIST sur le cœur Rust | Non mesuré |
| FPR de `sd-watermark` à 48 bits sans code correcteur | À mesurer sur corpus |
| Prévalence de l'IA dans un flux web réel | Inconnue ; aucun sondage public trouvé |
| Effet de la traduction seule sur les détecteurs | Non isolé dans la littérature |
| Robustesse de FerretNet après capture d'écran | Non trouvée |

## 10. Sources

- Guo et al., 2017 — calibration des réseaux : https://arxiv.org/abs/1706.04599
- Platt, 1999 — Platt scaling : https://www.cs.cornell.edu/courses/cs678/2007sp/platt.pdf
- Zadrozny & Elkan, 2002 — isotonic : https://www.cs.columbia.edu/~djhsu/coms4771-f25/handouts/zadrozny2002kdd.pdf
- Ovadia et al., 2019 — calibration sous décalage : https://arxiv.org/abs/1906.02530
- Angelopoulos & Bates, 2021 — prédiction conforme : https://arxiv.org/abs/2107.07511
- ENFSI — guideline évaluation forensique : https://enfsi.eu/wp-content/uploads/2016/09/m1_guideline.pdf
- NIST AI 100-2e2025 : https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-2e2025.pdf
- AI Act, art. 50 : https://artificialintelligenceact.eu/article/50/
- FerretNet : https://arxiv.org/abs/2509.20890 — AEROBLADE : https://arxiv.org/abs/2401.17879
- AIGIBench : https://arxiv.org/abs/2606.10309 — Deepfake-Eval-2024 : https://arxiv.org/abs/2503.02857
- W2V2-AASIST : https://huggingface.co/SpeechAntiSpoofingBenchmarks/W2V2-AASIST
- RADAR : https://arxiv.org/abs/2405.07940 — RAID : https://aclanthology.org/2024.acl-long.674.pdf
- Purdue 2025 (banc indépendant des produits) : https://arxiv.org/html/2510.16556v2
- Liang et al., 2023 (biais ESL) : https://www.cell.com/patterns/fulltext/S2666-3899(23)00130-7
- PDFuzz : https://arxiv.org/abs/2508.01887 — template python-docx : https://github.com/python-openxml/python-docx/blob/master/src/docx/templates/default.docx
