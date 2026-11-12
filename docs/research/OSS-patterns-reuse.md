# Idées récupérables dans les dépôts publics — recherche du 2026-11-12

Document de recherche. Aucun code modifié. Il prolonge `docs/research/ROADMAP-detection.md` et
`docs/research/FALLBACK-probabilistic.md`.

Méthode : chasse volontaire hors du consensus — dépôts de moins de 100 étoiles, commits de
2025-2026, projets inachevés mais contenant une brique fonctionnelle. Chaque dépôt cité a été
lu (README et, quand il existe, le code). Licence vérifiée : elle décide si l'idée est
**réimplémentable** ou seulement **inspirante**.

Convention : **[R]** réimplémentable sans risque (licence permissive, algèbre simple) ·
**[I]** inspirant seulement (licence absente, non commerciale, ou dépendance lourde).

## 1. Ce qui change la conception, par ordre d'importance

### 1.1 Le seuil doit bouger avec l'incertitude — `creator-xi/MoSEs` [R]

Dépôt de 11 étoiles (EMNLP 2025, MIT). La décision n'est pas `score > 0.5`, c'est :

```
logit = Xβ − λ · crit        avec λ = 1 par défaut
crit ∈ { entropie moyenne, écart-type de perplexité par phrase, taux de tokens hors top-100 }
```

Un texte incertain, c'est-à-dire à forte entropie, doit franchir une barre **plus haute**. Ça
tient en une ligne de code et ça règle proprement le problème des textes courts, des
traductions et des passages ambigus — sans inventer de probabilité.

C'est la meilleure réponse trouvée à la question « comment rendre le coefficient utilisable » :
on ne fabrique pas un pourcentage, on déplace le seuil.

### 1.2 L'abstention par test de transformation — `Miro382/TRP` [R]

Dépôt à 0 étoile, MIT, novembre 2026. Principe : rejouer le score sur **six vues** du même
fichier (JPEG q75, q90, redimensionnements 0,75 et 1,25…) et regarder la **dispersion**. Un
détecteur dont le score s'effondre quand on recompresse n'a rien mesuré : il renvoie
`abstain`, pas un chiffre bas.

Format de sortie : `{ verdict, accepted: bool, error_score }`. C'est le mécanisme le plus
honnête trouvé pour traiter la dégradation d'entrée sans mentir sur la confiance.

### 1.3 `p = None` quand le modèle n'est pas calibré — `sv-pro/ai-detector-bench` [R]

Dépôt à 0 étoile, MIT, août 2026. Ne détecte rien : il **mesure** les détecteurs (TPR@1 % FPR,
TPR@0,1 %, « humain condamné à p ≥ 0,95 »). Deux leçons d'ingénierie :

- 12 features stylométriques non ajustées renvoient `p = None` — **une somme pondérée à la main
  n'est pas une probabilité**, et le code le dit au lieu de faire semblant ;
- les préprocesseurs sont nommés et journalisés dans la sortie : `strip_code` déplace le score
  de **+0,275**, soit plus que l'écart entre deux documents de labels opposés.

Conséquence directe pour isitai : `preprocessors: ["unicode_nfkc", "strip_code"]` doit figurer
dans chaque rapport, et un score n'est comparable qu'à préprocesseurs égaux.

### 1.4 Trois états, jamais deux — `trufflesecurity/trufflehog` [R]

Le scanner de secrets le plus utilisé distingue `Verified` / `unverified` / `verification
error`. Transposé : un watermark est `found` / `absent` / **`inconclusive`**. Ne jamais
confondre « pas trouvé » et « pas cherché » — c'est exactement la faute que commettent les
détecteurs commerciaux quand ils répondent `human`.

### 1.5 Les métadonnées DOCX racontent une histoire — `michael-borck/provenance-analyser` [R]

0 étoile, MIT, PyPI. Lit `docProps/app.xml` : `TotalTime` (minutes d'édition), `Revision`,
`creator_app` (Word, Google Docs, LibreOffice, Pandoc, iText), écart entre `creator` et
`lastModifiedBy`. **50 pages en 23 minutes est une histoire**, et elle est déterministe.

Complété par `RoustyTousty/NoMark` [R] — 30 lignes de Python : décodeur du bloc de tags
Unicode `U+E0000–E007F` (ombre invisible de l'ASCII), caractères de largeur nulle, homoglyphes,
et la liste des `rsid` Word (chaque session d'édition en laisse un).

## 2. Dépôts Rust : les donneurs directs

Deux dépôts à très peu d'étoiles sont écrits dans la langue du cœur, sous licence permissive.
Ce sont les plus rentables de toute la chasse.

| Dépôt | Étoiles | Licence | Idée |
|---|---|---|---|
| `SamBroomy/is-it-slop` | 18 | MIT | TF-IDF + régression logistique servie en ONNX ; 9 features statistiques ; découpage 150 tokens / overlap 15 / min 30, avec redistribution uniforme pour éviter les queues minuscules |
| `elijah629/sonai` | 2 | Apache/MIT | 15 métriques de style, modèle de **521 octets** ; `not_just_count` (« it's not just X, it's Y »), ratio de guillemets typographiques, tirets cadratins, markdown mal formé, HTML échappé ; listes compilées en `aho-corasick`, blocs de code ignorés via `pulldown-cmark` |
| `arielb57/jpegpast` | 0 | MIT | **Récupère la table de quantification JPEG depuis les pixels seuls** (Fan & de Queiroz) : alignement de grille, DCT 8×8, périodicité par fréquence → verdict de ré-encodage et qualité estimée. Zéro dépendance |
| `Quincunx33/image-forensics` | 9 | MIT | Crate `forensic-engine` : `ela.rs`, `dct.rs` (énergies par bandes, périodicité de double compression), `jpeg.rs` (ghost), `clone.rs`. Compile en WASM |

`jpegpast` mérite un commentaire à part : **détecter qu'un fichier a été ré-encodé, et à quelle
qualité, est une preuve de pipeline** — pas une probabilité. Aucun concurrent ne l'expose, et
c'est exactement le genre de fait qui explique pourquoi un score est bas.

## 3. Le résultat contre-intuitif à vérifier en premier

`is-it-slop` mesure que **l'IA répète moins les bigrammes** que l'humain : coefficient **+1,98**
sur « taux de bigrammes répétés », pour un effet de taille **d = −0,419**.

C'est l'inverse de l'intuition « les modèles radotent ». Si la stylométrie du projet utilise la
répétition comme indicateur positif d'IA, son signe est peut-être inversé. À vérifier sur le
corpus du banc avant toute autre chose.

## 4. Texte : les briques à coût nul

| Idée | Source | Coût |
|---|---|---|
| Probabilité de ré-attribution du token : logits non décalés contre `input_ids`, masqués par l'attention — mesure l'auto-répétition réelle d'un LLM | `ChrisNassif/Telescope` [I] | 1 forward pass |
| `−CE_moyenne / len(zlib.compress(texte))` : la compression normalise « la quantité d'information », sans modèle | `ryuryukke/MINT` [R] | quasi nul |
| MATTR fenêtre 20 au lieu du TTR brut : tue l'artefact de longueur | `k1y0miiii/ru-ai-text-detector` [R] | quasi nul |
| Refuser de conclure sous 200 caractères fiables — « texte insuffisant », jamais une devinette | idem [R] | 0 |
| Fenêtres de 150 mots projetées sur les paragraphes, pondérées par le recouvrement | idem [R] | 0 |
| Agrégation non linéaire : `trimmed_mean` 10 %, `vote_fraction` 0,7, `logit_weighted_mean` — exposer les trois | `mjbommar/llm-detector` [R] | 0 |
| Divergence de Jensen-Shannon contre deux baselines appariées (humain / LLM) livrées en artefacts compressés | idem [R] | quelques Ko |
| z-score fermé `(Σ log p − Σ E_ref − shift·L) / √(Σ Var_ref)`, avec `shift` exposé comme paramètre de calibration | `Mamba413/AdaDetectGPT` [I, pas de licence] | 1 forward pass |
| Juger la **forme** de la distribution des p-values (KS, Anderson-Darling) plutôt que leur moyenne | `hwq0726/GoF-for-Watermark-Detection` [I] | faible |
| p-value par test de permutation, `n_runs = 100`, plutôt qu'un score brut | `doccstat/llm-watermark-adaptive` [I] | 100 × le coût |

## 5. Image et vidéo

| Idée | Source | Licence |
|---|---|---|
| **Pré-filtre résiduel NPR/SRM** : trois noyaux passe-haut fixes, z-score du résidu par blocs de 64 px — vingt lignes de Rust, remplace l'entrée RGB | `chuangchuangtan/NPR-DeepfakeDetection` | absente → réimplémenter depuis l'article |
| **Score spectral sans entraînement** : spectre radial (Hanning, 64 bins), pente log-log, résidu à la droite, ratio de queue haute fréquence, percentile calibré sur photos réelles | `andrezaiats/aidetect` (0★) | MIT |
| **Abstention par dispersion** sur six vues | `Miro382/TRP` | MIT |
| Dé-bruitage JPEG (DnCNN, FBCNN, SwinIR) pour **restaurer** les traces avant détection | `dvazquezpadin/jpeg-artifact-removal` | Apache-2.0 |
| Vidéo sans entraînement : FFT2 du gris, disque r = min(h,w)/8, énergies basse/haute normalisées, **agrégation par minimum** sur les frames | `jyothsnabondhu/STALL` | CC BY-NC → inspirant |
| Score par segment plutôt que par clip (rupture sur l'innovation d'un filtre de Kalman) | `yashwanth-maram/CoheRex_` | absente |
| Deux cartes en sortie (fiabilité, localisation) + score global | `grip-unina/TruFor` | non commerciale → structure seulement |
| `RandomStateAugmentation` : ordre et nombre d'augmentations tirés à l'entraînement — recette pour durcir aux recompressions | `JeongsooP/Community-Forensics` | MIT |

## 6. Audio et documents

**Audio.**

| Idée | Source |
|---|---|
| Registre d'adaptateurs : chaque détecteur rend `(score_fn, meta)`, sortie = **vecteur de scores**, jamais une moyenne | `MattyB95/Jabberjay` (MIT, 14★) |
| Score **par segment** (« 4,2–7,8 s suspect ») au lieu d'un score global | `Yaselley/deepfense-framework` (Apache-2.0) |
| Table de décision « marque absente + Opus 32k ⇒ ne pas conclure » : 28 dégradations testées | `nii-yamagishilab/antispoofing-watermark` (MIT) |
| Attribution sans entraînement : kNN k=21 sur la couche 4 d'un encodeur gelé → renvoyer **le générateur probable et ses voisins**, pas « IA/humain » | `adrianastan/tada` |
| Résidu de reconstruction après retrait de watermark → dire « marque possiblement effacée », pas « propre » | `DiffErase/Differase` |
| Registre de charges utiles : lire 16 bits et les mapper sur un émetteur connu (AudioSeal, WavMark, SilentCipher) | dépôts officiels, MIT |

**Documents — la couche la moins chère et la plus lisible.**

| Idée | Source |
|---|---|
| Découper les révisions sur `startxref` / `%%EOF` : **plusieurs `%%EOF` = resauvegardé en incrémental** ; nommer le générateur (ReportLab, iText, TCPDF, navigateur, OCR) ; séparer `/Info` et XMP | `genie360s/pdforensic` (MIT, 3★) |
| 40+ indicateurs nommés avec leur évidence, **jamais fusionnés en un score** (TouchUp, texte invisible, overlays, XMP history) | `Rasmus-Riis/PDFRecon` |
| Orphelins = objets non atteignables depuis `/Root` ; sous-ensembles de polices dont la couverture de glyphes ne colle pas au texte extrait | `michelcrypt4d4mus/pdfalyzer` (GPL) |
| Suivre `_rels/.rels` pour lister les parts non référencées et `customXml` | `officedissector`, `oletools` |
| La liste de suppression d'un nettoyeur est la **checklist inversée** des signaux à lire | `robazprogrammer/docx-sanitizer` (MIT) |

## 7. Format de sortie : la proposition convergente

Trois sources convergent vers la même forme — `pdforensic` (niveau + findings nommés + code de
sortie indépendant du verdict), C2PA (un code par contrôle, agrégation à l'affichage seulement),
TruffleHog (tri-état), SARIF (intégration CI).

```json
{
  "schema": "isitai/1",
  "file": { "sha256": "…", "mime": "application/pdf" },
  "engine": { "version": "0.2.0", "models": ["ferretnet-v1"], "weights_hash": "…" },
  "verdict": { "label": "ai-likely", "band": "medium" },
  "confidence": { "value": 62, "kind": "heuristic", "source": "spectral-v1" },
  "signals": [
    { "id": "pdf.producer.skia", "family": "document", "status": "found",
      "severity": "medium", "locus": { "page": 1, "obj": 12 },
      "detail": "Skia/PDF — export navigateur", "basis": "pdf-generators.v3" },
    { "id": "audioseal.payload", "family": "watermark", "status": "inconclusive",
      "detail": "extrait trop court pour 16 bits fiables" }
  ],
  "checks": { "passed": 7, "failed": 0, "skipped": 2 },
  "limits": ["texte extrait non fiable (PDFuzz)"],
  "preprocessors": ["unicode_nfkc", "strip_text_code"]
}
```

Trois règles qui rendent ce format utilisable :

1. **Deux axes séparés** : `status` dit si l'on a *cherché et trouvé*, `confidence.kind` dit si
   le chiffre est *calibré* (`calibrated`), une heuristique assumée (`heuristic`) ou absent
   (`none`). Un EER d'ASVspoof n'est pas une probabilité sur un MP3 WhatsApp.
2. **Le `locus` plutôt que le score** : timestamp audio, page et objet PDF, offset de caractère.
   C'est ce qui rend le résultat vérifiable, donc discutable.
3. **`preprocessors` toujours présent** : sans lui, deux scores ne sont pas comparables.

## 8. Premier incrément proposé, révisé

L'ordre change après cette chasse. Le moins cher pour le plus de valeur :

| # | Incrément | Coût | Source de l'idée |
|---|---|---|---|
| A | **Tri-état** `found / absent / inconclusive` sur chaque sonde existante, plus `preprocessors` | 0 | trufflehog |
| B | **Couche documentaire** : `%%EOF` multiples, `/Info` vs XMP, chaîne producteur, `TotalTime`/`rsid` DOCX, tags Unicode invisibles | 0 modèle | pdforensic, provenance-analyser, NoMark |
| C | **Spectral sans entraînement** + **NPR** en pré-filtre (image) | ~20 lignes Rust | aidetect, NPR |
| D | **Abstention par dispersion** sur six vues | faible | TRP |
| E | **Seuil conditionnel** `logit − λ·crit` sur les couches probabilistes | 1 ligne | MoSEs |
| F | `jpegpast` : ré-encodage et qualité depuis les pixels | ~200 lignes | jpegpast |
| G | Détecteurs neuronaux (FerretNet, AASIST) | 4 Mo | déjà planifié |

A et B ne coûtent aucun modèle et améliorent immédiatement la lisibilité des rapports. C, D, E
donnent le comportement « honnête » sans entraînement. F et G ajoutent la précision.

## 9. Non vérifié

| Affirmation | État |
|---|---|
| Le signe de la répétition de bigrammes sur le corpus du projet | Non testé ; `is-it-slop` mesure l'inverse de l'intuition |
| Licences effectives des poids (FerretNet, Community Forensics) | Dépôts lus, pas les checkpoints |
| Transposition exacte de `jpegpast` (alignement de grille sur images recadrées) | Algorithme compris, non exécuté |
| Compatibilité `forensic-engine` (Rust) avec les types du cœur | Non testée |
| Coût CPU réel des features spectrales sur 50 Mo d'images | Non mesuré |
