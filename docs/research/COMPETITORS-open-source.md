# Bibliothèques open source locales : algorithmes exacts — recherche du 2026-11-12

Document de recherche. Aucun code modifié. Il complète, sans les répéter :

- `BENCH-text-detectors.md` (mesures des familles stylométrie, n-grammes, compression, perplexité, classifieurs) ;
- `OSS-patterns-reuse.md` (idées prises dans des dépôts GitHub : MoSEs, TRP, trufflehog, pdforensic, jpegpast, `is-it-slop`, `sonai`, `llm-detector`…) ;
- `FALLBACK-probabilistic.md` (forme du coefficient) ;
- `COMPETITORS-commercial.md` (produits payants, recommandations de score §7.4).

**Objet** : les **paquets publiés** sur npm, PyPI et crates.io qui détectent du contenu IA en local. Pour chacun, ce que fait réellement le code.

**Méthode.** Archives téléchargées (tarball npm, sdist PyPI, `.crate`) et lues comme des données. Rien n'a été exécuté ni installé. Les algorithmes sont décrits avec mes mots ; aucun code ni liste n'est recopié. Téléchargements : 30 derniers jours, relevés le 2026-11-12 (API npm, pypistats, crates.io « recent » = 90 jours).

Conventions : **[R]** idée ou liste réutilisable (licence permissive) · **[I]** inspirant seulement (licence absente, copyleft, non commerciale, ou origine de la liste non créditée) · **non mesuré** = famille absente du banc du projet.

## 1. Inventaire

### 1.1 npm

| Paquet | Version | Dernière publication | Licence | Taille décompressée | Téléch./mois |
|---|---|---|---|---|---|
| `ai-text-detector` | 1.0.8 | 2025-06-19 | MIT | 308 Ko | 380 |
| `@jongleberry/vurst-ai` | 0.4.3 | 2026-09-08 | MIT | 28 Ko (chargeur seul) | 406 841 |
| `avoid-ai-writing-detector` | 3.38.0 | 2026-10-15 | MIT | 268 Ko | 8 272 |
| `slop-detector` | 1.2.0 | 2026-04-06 | MIT | 1,58 Mo | 105 |
| `@yavqo/pistachi` | 0.2.0 | 2026-10-19 | MIT | 39 Ko | 93 |
| `humanize-cli` | 2.0.0 | 2026-01-31 | MIT | 109 Ko | 133 |
| `@aedilic/nonescape` | 1.0.4 | 2025-08-18 | Apache-2.0 | 833 Ko | 49 |
| `@delicity/ai-image-detection` | 1.1.0 | 2026-09-17 | MIT | 766 Ko | 71 |
| `@enslo/sd-metadata` | 4.1.0 | 2026-11-09 | MIT | 1,23 Mo | 3 818 |
| `@textlint-ja/textlint-rule-preset-ai-writing` | 1.7.0 | 2026-05-13 | MIT | 188 Ko | 170 220 |
| `humanizer-lint` | 1.6.0 | 2026-11-07 | MIT | 447 Ko | 2 622 |
| `naturable-rules` | 1.2.0 | 2026-10-23 | MIT AND CC-BY-4.0 | 349 Ko | 432 |
| `slop-chop-wasm` | 0.55.1 | 2026-11-02 | MIT | 5,7 Mo | 1 464 |
| `patina-cli` | 9.1.0 | 2026-09-26 | MIT | 2,4 Mo | 3 566 |
| `slopless` | 0.2.42 | 2026-10-23 | MIT | 1,6 Mo | 7 494 |
| `slopsift` | 0.12.0 | 2026-10-31 | MIT | 333 Ko | 696 |
| `slopfix` | 0.1.1 | 2026-10-25 | MIT | 56 Ko | 619 |
| `@e1i0/human` | 0.3.0 | 2026-10-25 | MIT | 252 Ko | 276 |
| `plain-english` | 1.17.5 | 2026-10-10 | MIT | 5,1 Mo | 742 |
| `mcp-varianceiskey` | 1.0.0 | 2026-03-27 | MIT | 10 Ko | 20 |
| `@lukstei/slop-grader` | 0.5.0 | 2026-10-29 | MIT | 166 Ko | 664 |
| `humanizer-semitic` | 1.0.0 | 2026-08-03 | MIT | 224 Ko | 55 |
| `humanizer-ru` | 3.32.0 | 2026-10-19 | MIT | 386 Ko | 642 |
| `zero-slop` | 2.12.39 | 2026-11-12 | MIT | 726 Ko | 3 129 |

### 1.2 PyPI

| Paquet | Version | Dernière publication | Licence (métadonnées) | sdist | Téléch./mois |
|---|---|---|---|---|---|
| `llm-detector` | 0.2.0 | 2025-09-19 | MIT | 6,4 Mo | 30 |
| `thinkst-zippy` | 0.1.3 | 2025-02-27 | vide (voir §3) | 39 Ko | 652 |
| `aidetector` | 0.0.2 | 2023-07-11 | Apache (classifieur) | 13 Ko | 32 |
| `pangram-sdk` | 1.2.0 | 2026-11-10 | vide | 23 Ko | 6 480 |
| `synthid-text` | 0.2.1 | 2024-11-14 | Apache-2.0 | 41 Ko | 336 |
| `audioseal` | 0.2.1 | 2026-11-03 | MIT | 54 Ko | 155 652 |
| `videoseal` | 1.0.1 | 2025-07-21 | vide (voir §3) | 3,9 Mo | 15 916 |
| `trustmark` | 0.9.2 | 2026-09-08 | MIT | 64 Ko | 17 691 |
| `invisible-watermark` | 0.2.0 | 2023-07-06 | MIT | 1,6 Mo (wheel) | 123 254 |
| `wavmark` | 0.0.3 | 2024-01-07 | MIT | 565 Ko | 9 419 |
| `silentcipher` | 1.0.5 | 2024-06-18 | MIT | 15 Ko | 321 |
| `is-it-slop` | 0.6.3 | 2026-06-02 | MIT | 128 Ko | 148 |
| `slop-guard` | 0.5.0 | 2026-07-09 | MIT | 2,2 Mo | 644 |
| `sloplint` | 0.11.0 | 2026-09-30 | MIT (classifieur) | 8 Ko | 414 |
| `deslop` | 0.2.0 | 2026-04-25 | MIT | 12 Ko | 17 |
| `raid-bench` | 0.2.0 | 2025-07-25 | MIT | 1,4 Mo | 145 |
| `openai-detector` | 0.1.2 | 2023-02-14 | Apache | 9 Ko | 61 |
| `llm-watermark` | 0.1.18 | 2025-11-07 | vide | 15 Ko | 47 |

Noms sans paquet sur PyPI (404 le 2026-11-12) : `binoculars-detector`, `desklib`, `gptid`, `detectgpt`, `fast-detectgpt`, `ai-detector`, `pangram`, `radar-detector`, `gltr`. Les paquets `zippy`, `binoculars`, `ghostbuster` existent mais sont sans rapport (codes postaux, intervalles binomiaux, adresses IP). **Binoculars, DetectGPT, Fast-DetectGPT, GLTR, desklib et GPTID ne sont donc distribués que comme dépôts GitHub ou modèles Hugging Face**, déjà mesurés dans le banc.

### 1.3 crates.io

| Crate | Version | Dernière publication | Licence | Taille `.crate` | Téléch. total / 90 j |
|---|---|---|---|---|---|
| `is-it-slop` | 0.6.3 | 2026-06-02 | MIT | 59 Ko | 2 513 / 264 |
| `is-it-slop-preprocessing` | 0.6.3 | 2026-06-02 | MIT | 72 Ko | 2 776 / 297 |
| `antitransformer` | 1.0.0 | 2026-03-30 | MIT OR Apache-2.0 | 37 Ko | 28 / 4 |
| `prose-sanitiser-slop` | 0.1.6 | 2026-11-11 | MIT OR Apache-2.0 | 68 Ko | 128 / 128 |
| `slop-guard` (portage Rust) | 0.3.0 | 2026-03-15 | MIT | 1,8 Mo | 91 / 17 |
| `ai-slop` | 0.1.16 | 2026-10-04 | MIT OR Apache-2.0 | 303 Ko | 314 / 164 |
| `slop-lint` | 0.1.0 | 2026-07-02 | MIT | 30 Ko | 26 / 2 |
| `declawd` | 0.3.3 | 2026-11-02 | Apache-2.0 | 5,9 Mo | 85 / 72 |
| `provcheck-detect` | 1.5.2 | 2026-10-29 | Apache-2.0 | 23 Ko | 145 / 145 |
| `provcheck-synthid-text` | 1.5.2 | 2026-10-29 | Apache-2.0 | 45 Ko | 38 / 38 |

Hors sujet, une ligne : `slop-scan`, `antislop` (crate), `ai-slop-detector` (PyPI), `eslint-plugin-*slop*`, `vibecheck-core` visent le **code** généré par IA, pas la prose ni les médias.

## 2. Dix paquets lus en détail

### 2.1 `avoid-ai-writing-detector` (npm, MIT) — le plus abouti des moteurs à règles

Dépôt `conorbronsdon/avoid-ai-writing`, 5 607 étoiles. Deux fichiers utiles : `detector/patterns.js` (3 369 lignes) et `validate.js`. Anglais seulement. Aucune dépendance, aucun modèle.

**Chaîne de traitement**

1. **Normalisation avant les règles** : retrait des caractères de largeur nulle et remplacement des sosies cyrilliques et grecs par leur lettre latine, avec une table qui ramène chaque position au texte d'origine. Le nombre de caractères retirés est gardé comme signal.
2. **Masquage** : blocs de code, code en ligne, en-tête YAML, tableaux, citations, commentaires HTML, régions marquées « ignore ». Mode `rendered-markdown` ou brut. Mode de contexte (`general`, `technical`…) : en `technical`, une liste de termes légitimes (robust, leverage…) n'est plus signalée.
3. **Règles** : une soixantaine de catégories. Vocabulaire en trois niveaux (ordre de grandeur compté ici : 60 mots et 30 expressions au niveau 1, 85 au niveau 2, 25 au niveau 3 ; le niveau 2 ne compte que s'il y a regroupement dans un paragraphe). Puis restes de chatbot, flatterie, avertissement de date de coupure, traces de raisonnement, attributions vagues, conclusions génériques, ouvertures toutes faites, questions rhétoriques, fausse concession, chaîne de négations, parallélisme négatif, bloc de hashtags, liste à puces de groupes nominaux, titres en capitales de titre.
4. **Empreintes d'outil** (un seul cas suffit) : paramètres d'URL `utm_source=chatgpt.com` et équivalents, balisage de citation de chatbot resté dans le texte, champs à remplir (`[Your Name]`, `2025-XX-XX`).
5. **Stylométrie sans modèle**, avec seuils fixés à la main :

| Signal | Calcul | Seuil | Longueur minimale |
|---|---|---|---|
| Diversité lexicale | MATTR, fenêtre de 200 mots | < 0,40 | 200 mots |
| Entropie des trigrammes de mots-outils | entropie de Shannon normalisée par log2 du nombre de trigrammes distincts ; approche l'entropie des trigrammes de catégories grammaticales sans étiqueteur | < 0,82 et au moins 50 trigrammes | 150 mots |
| Rythme entre paragraphes | coefficient de variation des longueurs de phrase calculé par paragraphe ; écart-type de ces coefficients < 0,08 et moyenne < 0,45 | les deux | plusieurs paragraphes |
| Uniformité des phrases | coefficient de variation < 0,25 et moyenne > 10 mots | les deux | — |
| Signature de ponctuation « propre » | guillemets courbes + tiret cadratin + virgule d'Oxford + aucune faute courante + aucun double espace : les quatre ensemble | 4 sur 4 | 80 mots |

**Score** : somme des poids des constats dédupliqués (par type et texte), divisée par `max(1, log2(mots / 50))`, bornée à 100. Poids fixés à la main : 10 pour un avertissement de date de coupure, 8 pour un reste de chatbot, 5 pour un mot de niveau 1, 2 à 3 pour le reste, 9 pour des caractères invisibles, 12 pour les signaux de structure sur texte court.

**Deux poids sont à zéro, et c'est le point le plus intéressant.** Le tiret cadratin et la « platitude émotionnelle » restent affichés mais ne déplacent plus le score : le premier parce que sa polarité change d'une génération de modèles à l'autre, la seconde parce que la règle n'a produit aucun cas dans les corpus du projet, donc aucune direction mesurée.

**Verdict à trois classes** (`HUMAN_ONLY`, `MIXED`, `AI_ONLY`) : sous 15 sans corroboration forte, humain ; corroboration forte ou score ≥ 70, IA ; score ≥ 40 avec une corroboration, IA ; sinon mixte. Corroborations fortes : date de coupure, au moins 2 caractères invisibles ou sosies, trace de raisonnement avec reste de chatbot, vocabulaire dense (5 mots de niveau 1 distincts, 2 paragraphes de niveau 2, une transition, 150 mots). La signature de ponctuation seule ne compte pas : elle correspond aussi à un texte humain passé par Word.

**Sortie** : score 0–100, libellé en six bandes, classe, « probabilités » des trois classes, bande de confiance, liste des constats avec positions dans le texte d'origine, régions de phrases contiguës fusionnées. Refus explicite : moins de 10 mots (`Too short`), script sans espaces (chinois, japonais : `unsupportedScript`), plafond de 10 000 mots.

**Mon évaluation**

- Les « probabilités » sont des formules écrites à la main, et le code le dit en commentaire (« not calibrated »). C'est exactement ce que `FALLBACK-probabilistic.md` §2 interdit. À ne pas imiter.
- Les seuils viennent du jugement de l'auteur, puis sont corrigés sur des corpus : le dépôt échantillonne HC3 et RAID, et ses tickets ajoutent des textes humains par registre (un message de liste W3C de 1995, la RFC 4180). Aucun taux de faux positifs n'est publié dans le paquet. **Non mesuré** dans le banc du projet.
- Ce qui cassera : toute la partie vocabulaire est datée (les mots de 2023-2024) et anglaise. Le paquet le sait : il met à zéro ce qui s'inverse.
- **Idées à prendre [R]** : la normalisation avec table de retour aux positions d'origine ; les empreintes d'outil (paramètres `utm_source`, balisage de citation, champs non remplis), qui sont déterministes et relèvent de la couche d'artefacts existante ; le poids zéro pour un motif sans direction mesurée ; le masquage nommé (rejoint `preprocessors` de `OSS-patterns-reuse.md` §1.3).
- Listes : paquet MIT, mais les crédits citent la page Wikipédia « Signs of AI writing » (CC BY-SA 4.0), Pangram et deux « humanizers ». L'origine mot par mot n'est pas tracée : **[I] pour les listes**, [R] pour les mécanismes.

### 2.2 `slop-detector` (npm, MIT) — le score EQ-Bench

Portage TypeScript de `sam-paech/slop-score`. Licence amont : double ; le fichier de licence lu place sous MIT le calcul du score et les listes de `data/`.

**Quatre composantes**

| Composante | Mesure | Poids |
|---|---|---|
| Mots | occurrences d'une liste de **1 655 mots** par 1 000 mots | 0,50 |
| Motif « not X but Y » | occurrences par 1 000 caractères | 0,20 |
| Trigrammes | occurrences d'une liste de **430 trigrammes** (mots vides retirés) par 1 000 mots | 0,12 |
| Tropes | expressions figées par 1 000 caractères | 0,18 |

Chaque composante est ramenée entre 0 et 1 par rapport à l'étendue observée **sur les modèles du classement EQ-Bench** (minimum et maximum, élargis de 10 %), lue dans un fichier de 1,4 Mo embarqué. Les tropes n'ont pas de données : étendue fixée à 0–5. Score final sur 100.

**Le détecteur de contraste est le plus élaboré trouvé.** Deux étages : 10 expressions régulières sur le texte brut (forme « not X, but Y », forme à tiret, forme sur deux phrases avec pronom, forme à groupe nominal), puis 31 expressions appliquées à un texte où les verbes ont été remplacés par une marque après étiquetage grammatical (`wink-pos-tagger`), pour attraper « doesn't VERBE. It VERBE ». Chaque règle porte des gardes : pas après « not that », « not only », pas quand la suite commence par une conjonction ou un pronom de première personne, pas dans un discours rapporté (« said that… »).

**Mon évaluation**

- **Ce score classe des modèles, il ne classe pas des documents.** La normalisation est relative aux modèles du classement, pas à du texte humain. Un texte humain n'a pas de place définie sur cette échelle. L'utiliser comme détecteur est un contresens. **Non mesuré** dans le banc.
- Les listes viennent de la fiction générée (on y trouve des prénoms de personnages) : elles ne valent pas pour un courriel ou un article.
- **À prendre [R]** : la liste de gardes du détecteur de contraste, comme cas de test négatifs pour `rhetoric.not-x-but-y` ; l'idée de mesurer une densité par 1 000 caractères. La couche `rhetoric` du cœur a 14 connecteurs et quelques amorces ; elle n'a pas ces gardes.
- Tout est anglais. L'étage 2 dépend d'un étiqueteur anglais : non transposable au français sans étiqueteur.

### 2.3 `slop-guard` (PyPI 0.5.0, MIT ; portage Rust sur crates.io 0.3.0, MIT)

Dépôt `eric-tramel/slop-guard`, 167 étoiles. Environ 25 règles rangées par portée : mot (78 mots), phrase (110 expressions, marqueurs de ton, aveu d'IA, champ non rempli, paire de contraste, fragment sentencieux, « mise en place puis résolution », gras au milieu d'une phrase), paragraphe (densité de puces, de citations, de filets, suites de puces à terme en gras), passage (rythme, rythme des paragraphes, densité de tirets cadratins et de deux-points, chaîne de copules, aphorisme final, réemploi d'expressions).

**Score** : chaque violation porte une pénalité (1 à 10 ; 10 pour un aveu d'IA). Quand une catégorie « typique » se répète, la pénalité est amplifiée : `pénalité × (1 + 2,5 × (occurrences − 1))`. La somme est rapportée à la longueur, puis `score = 100 × exp(−0,04 × densité)`. Cinq bandes : propre ≥ 80, léger ≥ 60, modéré ≥ 40, lourd ≥ 20, saturé en dessous. Ici 100 veut dire propre : sens inverse des autres paquets.

**Ce qu'il fait différemment : l'ajustement sur corpus (`sg-fit`).** Une commande lit un corpus de textes jugés bons, et en option un corpus négatif, puis réécrit la configuration de chaque règle :

- les seuils sont placés sur des percentiles du corpus de référence ;
- la pénalité est réduite quand la règle se déclenche souvent dans les bons textes, et **mise à zéro quand elle se déclenche autant ou plus dans les bons textes que dans les mauvais** ;
- la valeur ajustée est mélangée à la valeur par défaut selon le nombre de documents (`poids = n / (n + 12)`), pour ne pas sur-apprendre sur dix textes.

**Mon évaluation**

- Valeurs par défaut fixées à la main, aucune mesure publiée. **Non mesuré** dans le banc.
- **Idée à prendre [R], la plus utile de ce paquet** : l'ajustement par contraste avec retour vers la valeur par défaut. C'est le pendant « règles » de la calibration par langue de `FALLBACK-probabilistic.md` §3 : une règle n'a le droit de compter que si elle se déclenche plus sur l'IA que sur l'humain **dans le registre visé**.
- Tickets ouverts : les utilisateurs demandent des listes d'exceptions par terme. Signe que les faux positifs de vocabulaire sont la plainte principale.

### 2.4 `ai-text-detector` (npm, MIT, 2025)

Un fichier de 47 Ko, sans modèle. Environ 25 mesures, toutes calculées sur le texte seul : « perplexité » et « caractère inhabituel des bigrammes » (estimées à partir des fréquences internes au texte et de listes, **pas d'un modèle de langue**), variation des longueurs de phrase, diversité et richesse lexicales, entropie, complexité syntaxique approchée, cohérence, répétition de n-grammes, densité de transitions, indice de formalité, ponctuation, puis cinq mesures « humaines » : pronoms personnels, fragments, marqueurs de conversation, émotion, familiarité, récit, créativité. Listes anglaises embarquées (mots courants, mots-outils, transitions, mots « sophistiqués »).

**Décision** : score = somme pondérée à la main (indicateurs humains inversés 0,25 ; formalité 0,20 ; perplexité 0,18 ; émotion 0,15 ; variation 0,15…). Le seuil de base est 0,58, puis **il monte** quand le texte paraît narratif (+0,08 à +0,15), humain (+0,05 à +0,20), familier (+0,03 à +0,15), émotif (+0,06 à +0,12) ou créatif (+0,10 à +0,20). Sortie : booléen, « confiance » égale au score, mesures détaillées. Minimum : 50 caractères.

**Mon évaluation**

- C'est la famille « stylométrie » du banc, sans même l'ajustement sur données : le banc mesure 14 à 72 % de faux positifs hors distribution pour la version entraînée. Rien ne permet d'attendre mieux ici.
- Biais construit : tout texte formel, sans contraction ni émotion, monte vers « IA ». Un courriel administratif ou un texte d'auteur non natif est la victime désignée (`FALLBACK` §5, Liang et al.).
- **Seule idée à garder [R]** : le seuil qui bouge selon le registre détecté. C'est une version naïve du seuil conditionnel MoSEs (`OSS-patterns-reuse.md` §1.1), dans le bon sens : plus de prudence quand le registre sort du domaine connu.

### 2.5 `@yavqo/pistachi` (npm, MIT, 2026) — le concurrent le plus proche en périmètre

Texte, image et lecture C2PA dans 39 Ko, sans dépendance. Pas de dépôt public déclaré.

**Texte** : neuf signaux ramenés entre 0 et 1.

| Signal | Mesure | Poids |
|---|---|---|
| Régularité des phrases | `(0,6 − coefficient de variation) / 0,35` | 0,25 |
| Expressions types | 34 expressions anglaises par 100 mots, saturation à 1,5 | 0,22 |
| Transitions en tête de phrase | part des phrases, saturation à 20 % (14 mots) | 0,11 |
| Trigrammes répétés | part, saturation à 12 % | 0,09 |
| Absence de contractions | contractions par 100 mots | 0,09 |
| Régularité des paragraphes | à partir de 3 paragraphes | 0,08 |
| Mise en forme de chatbot | puces à terme en gras, titres, émojis en tête de ligne | 0,07 |
| Caractères invisibles | saturation à 3 | 0,05 |
| Tirets cadratins | par phrase, saturation à 0,3 | 0,04 |

Score = moitié somme pondérée, moitié moyenne des trois signaux les plus forts (pour qu'un petit nombre d'indices nets ne soit pas dilué). Sept phrases de chatbot forcent le score à 0,95 au moins. Seuils : 0,6 IA, 0,4 mixte. « Confiance » = `min(1, mots / 300) × 0,8`. **Sous 40 mots : `score: null`, verdict `unknown`.** Option `segments` : chaque paragraphe est noté seul, avec ses positions.

**Image** : aucune statistique de pixels. Recherche dans le premier mégaoctet de : type de source IPTC `trainedAlgorithmicMedia` et sa variante composite, présence de C2PA/JUMBF, noms de générateurs (DALL·E, OpenAI, Midjourney, Firefly, Google AI, Stable Diffusion), paramètres « Steps, Sampler », graphe ComfyUI. Indices faibles : dimensions égales à une sortie courante de générateur (12 tailles), présence d'EXIF d'appareil. Verdict `ai` ou `unknown`, jamais `human`. Le manifeste C2PA est analysé mais **la signature n'est pas vérifiée**, et le paquet le dit dans chaque message.

**Mon évaluation**

- Texte : même famille que 2.4, mêmes risques. Le signe du signal « trigrammes répétés » (plus de répétition = IA) est **l'inverse** de ce que mesure `is-it-slop` (`OSS-patterns-reuse.md` §3). Deux paquets, deux signes opposés : aucun des deux ne doit être repris sans mesure.
- Image : isitai fait déjà mieux (signature vérifiée). Rien à prendre sauf la liste des 12 tailles comme indice très faible, à ne jamais afficher seul.
- **Sortie à noter** : `score: null` sous le minimum, raisons en phrases, segments par paragraphe. Conforme à la recommandation 2 de `COMPETITORS-commercial.md` §7.4.

### 2.6 `@jongleberry/vurst-ai` (npm, MIT) — une enveloppe

Le tarball ne contient que le chargeur N-API. Source lue dans `jonathanong/vurst` (`packages/ai/src/slop_detection/mod.rs`) : **c'est un appel direct à la crate `is-it-slop`**, sans autre logique. Sortie : `flagged`, probabilité, seuil, classe, nom du détecteur et **version du modèle**. Seuil par défaut **0,95**, bien plus strict que celui d'`is-it-slop`. Une panique du détecteur est rattrapée et rendue comme « détecteur indisponible ».

- Les 406 841 téléchargements mensuels ne sont pas attribuables : le dépôt a 0 étoile. Je ne peux pas dire s'il s'agit d'usage réel, d'intégration continue ou de miroirs.
- Pour `is-it-slop` lui-même, voir `OSS-patterns-reuse.md` §2 et §3. Deux compléments lus dans les crates : le script de construction **télécharge le modèle ONNX, le vocabulaire et les seuils depuis les « releases » GitHub** (modèle 3.0.0), donc la crate seule ne suffit pas hors ligne ; et le nettoyeur a deux étages, dont un **réservé à l'entraînement** qui retire les artefacts propres aux jeux de données (en-têtes Wikipédia, résidus RAID, citations numérotées). C'est la réponse directe au constat du banc (§4, « une partie du signal est un artefact de mise en forme »).
- **Idée à prendre [R]** : rendre `detector` et `detector_model_version` dans chaque résultat ; un seuil par défaut prudent côté intégrateur.

### 2.7 Règles hors anglais : `slopfix` (FR), `@e1i0/human` (ES), `naturable-rules` (ZH), `@textlint-ja/…` (JA), `humanizer-ru`, `humanizer-semitic`

| Paquet | Langues | Contenu | Licence des listes |
|---|---|---|---|
| `slopfix` 0.1.1 | anglais, **français** | 9 règles françaises, environ 110 expressions : restes de chatbot, ouvertures flatteuses, formules de fin, remplissage (« il convient de noter que »), vocabulaire, « ce n'est pas X, c'est Y », « que vous soyez… » | MIT, origine non citée |
| `@e1i0/human` 0.3.0 | espagnol, anglais | 35 détecteurs de construction (écho nié, pivot déictique, pseudo-clivée, tricolon, anaphore, calque de l'anglais, passif sans agent…), 12 registres, outil de calibration | MIT |
| `naturable-rules` 1.2.0 | anglais (23 règles), chinois (16) | paquets de règles JSON avec schéma ; chaque règle porte sévérité, confiance et **poids par usage** (courriel, universitaire, marketing, technique…) | code MIT, **règles CC BY 4.0** (crédit « Naturable (naturable.app) ») |
| `@textlint-ja/textlint-rule-preset-ai-writing` 1.7.0 | japonais | 5 règles textlint : expressions d'emphase, deux-points de continuation, mise en liste, motifs d'insistance, guide de rédaction technique | MIT |
| `humanizer-ru` 3.32.0 | russe | compétence d'agent + scripts Python de mesure (morphologie, répétitions, marqueurs, rythme, score) ; 67 marqueurs annoncés | MIT |
| `humanizer-semitic` 1.0.0 | arabe (standard, égyptien, levantin), hébreu | texte de compétences seulement, aucun code | MIT |

Le paquet japonais est le plus téléchargé de toute l'étude côté règles (170 220 par mois) : la demande existe hors anglais, et elle se présente comme un **linter de style**, pas comme un détecteur.

**`slopfix`, à la lecture des règles françaises**

- `fr/not-x-but-y` (trois formes : « X n'est pas [seulement] … , c'est … », « il ne s'agit pas [seulement] de … mais de … », « plus qu'un …, c'est … ») exige une négation explicite et la reprise par « c'est » ou « il s'agit ». **Elle ne se déclencherait pas** sur les paires « Si vous… / Nous vous… » que isitchatgpt a signalées.
- En revanche `fr/chatbot-sign-off`, de sévérité « erreur », signale « n'hésitez pas à nous contacter » et « j'espère que cela vous aide ». **La première est la formule de politesse la plus courante du courriel professionnel français.** Faux positif certain sur le registre où le propriétaire a déjà observé l'échec.
- `fr/filler-opener` signale « il convient de noter que », « force est de constater que » : français administratif ordinaire.

**`@e1i0/human`, ce qu'il fait différemment**

- Chaque détecteur est un fichier avec un contrat écrit : ce qu'il détecte, un avant/après, **« ce que ce n'est pas »**, et pourquoi. Les gardes sont linguistiques (en espagnol la négation précède le verbe ; un infinitif après « no » est un complément, pas un écho).
- **Registres** : 12 fichiers (formel, universitaire, technique, récit, vente…) qui disent quels motifs coûtent plus ou moins cher dans ce registre.
- **Calibration en deux modes** : sur la prose de l'auteur, pour placer les seuils juste au-delà de ce qu'il écrit déjà ; ou avec un dossier de textes d'avant l'IA et un dossier de textes générés, pour décider si chaque détecteur mérite d'exister. Règle écrite dans l'outil : un détecteur qui se déclenche plus sur les textes anciens que sur les textes générés « signale des gens ».
- Sortie : des comptes par motif et un **budget** ; l'intégration continue échoue quand un motif dépasse son budget. Aucun score global.

**Ce qui dépend de la langue**

| Élément | Portable ? |
|---|---|
| Listes de mots et d'expressions | non : à réécrire par langue, et par registre |
| « not X but Y » | la forme existe partout, les amorces et l'ordre des mots changent (négation en deux parties en français, avant le verbe en espagnol) |
| Triptyque / tricolon | forme portable, mais c'est une figure scolaire en français : densité humaine élevée |
| Typographie (tiret cadratin, guillemets courbes, virgule d'Oxford) | non : le français impose les guillemets « » et les espaces insécables ; un correcteur les pose seul |
| Absence de contractions | propre à l'anglais |
| Caractères invisibles, restes de chatbot, champs non remplis, paramètres d'URL | oui |

### 2.8 `antitransformer` (crates.io, MIT OR Apache-2.0) — statistiques sans modèle, en Rust

Cinq mesures, aucune donnée externe :

| Mesure | Calcul | Sens supposé | Poids |
|---|---|---|---|
| Écart à la loi de Zipf | pente de la régression log-rang / log-fréquence, écart à 1 | écart = IA | 2,5 |
| Variance de la « perplexité » | variance de la surprise par fenêtre, estimée sur les fréquences du texte | faible = IA | 2,2 |
| Écart-type de l'entropie | entropie par fenêtre | faible = IA | 2,0 |
| Rafales | `(σ − μ) / (σ + μ)` sur les intervalles entre réapparitions d'un même mot | faible = IA | 1,8 |
| Diversité lexicale | écart du ratio types/occurrences à 0,7 | écart = IA | 1,5 |

Normalisation par des « valeurs humaines typiques » écrites en dur (1,0 ; 0,3 ; 0,5 ; 0,3), somme pondérée, puis une fonction de Hill (demi-saturation 0,5, exposant 2,5) et une porte en exponentielle baptisée « Arrhenius » ; seuil 0,5. Sortie : verdict, probabilité, confiance, valeurs intermédiaires.

**Mon évaluation**

- Aucune donnée, aucune mesure, 28 téléchargements. Les constantes sont habillées d'un vocabulaire de chimie qui ne leur donne aucune justification. Le ratio types/occurrences brut dépend de la longueur (corrigé ailleurs par MATTR, `OSS-patterns-reuse.md` §4). **Non mesuré**, et rien à en attendre au vu de la stylométrie du banc.
- **Une seule mesure est nouvelle par rapport au banc [R]** : les rafales par intervalles entre réapparitions d'un mot. L'intuition (les mots de sujet se regroupent chez l'humain) est indépendante de la langue. À mettre dans la liste des caractéristiques à tester sur le jeu doré, sans attente.
- La sortie des valeurs intermédiaires est la bonne pratique.

### 2.9 Détection de marques : `synthid-text` (PyPI, Apache-2.0), `provcheck-*` et `declawd` (crates.io, Apache-2.0)

**`synthid-text` 0.2.1** (Google DeepMind). Côté détecteur, trois fonctions : score moyen des valeurs g, score moyen pondéré par couche de tournoi, et un détecteur bayésien entraîné (vraisemblance du texte marqué contre non marqué, a priori réglable, sortie = probabilité a posteriori). **Toutes exigent les clés de marquage et le tokenizer exact du modèle qui a généré.** Sans les clés, rien n'est détectable. Les clés de Gemini ne sont pas publiées.

**`provcheck` 1.5.2** est le concurrent direct d'isitai en Rust : vérification C2PA, plus des crates de détection de marques (AudioSeal, WavMark, SilentCipher, TrustMark image et vidéo, SynthID-text), un téléchargement de poids vérifié à part, et `provcheck-detect`, un simple **trait** : nom, familles couvertes (audio, vidéo, image, texte), méthode `run` sur des octets ; les erreurs sont par détecteur, les résultats vont dans une liste du rapport. Aucun poids de détecteur n'est livré ; les modèles sont annoncés comme extension payante.

- `provcheck-synthid-text`, à la lecture de sa documentation : découpe le texte **sur les espaces**, calcule une valeur g par mot avec un sel, puis un score z contre 0,5 avec l'erreur type `√(1/(12N))`, et rend `Φ(z)` comme « confiance ». Deux défauts : sans la clé et le tokenizer du générateur, le test ne mesure rien sur du texte Gemini réel ; et `Φ(z)` est une valeur p unilatérale, pas une probabilité que le texte soit marqué (`FALLBACK` §2). **Ne pas reprendre.**
- **À prendre [R]** : le trait de détecteur enfichable à erreurs isolées (même forme que le registre d'adaptateurs audio de `OSS-patterns-reuse.md` §6) ; les poids distribués hors du paquet avec vérification d'empreinte, ce qui règle la question 30 Mo / 500 Mo.

**`declawd` 0.3.3** : registre explicite de structures Unicode « porteuses » (caractères de balise, largeur nulle, espaces rares), avec classes, règles de position et sortie SARIF ; reproduction du calcul SynthID public à titre d'expérience. Le README refuse deux conclusions par écrit : un constat ne montre pas qu'une IA est intervenue, une absence ne prouve pas un auteur humain. Il précise ne pas détecter la marque de texte d'un fournisseur sans sa clé. **À prendre [R]** : le registre de points de code en données versionnées, et la sortie SARIF (déjà citée dans `OSS-patterns-reuse.md` §7).

Paquets de marquage PyPI, côté détection, en une ligne chacun : §3.

### 2.10 Image : `@enslo/sd-metadata`, `@delicity/ai-image-detection`, `@aedilic/nonescape`

**`@enslo/sd-metadata` 4.1.0 (MIT, 3 818/mois)** — lecteur de métadonnées de génération, sans verdict. PNG (blocs texte), JPEG et WebP (EXIF, commentaire). Reconnaît 15 outils : ComfyUI, NovelAI, InvokeAI, SwarmUI, Fooocus, Ruined Fooocus, Easy Diffusion, Draw Things, Stability Matrix, TensorArt, Civitai, espaces Hugging Face, Dezgo, Kusart, et les sorties `gpt-image`. Clés lues : `parameters`, `prompt`, `workflow`, `Comment`, `invokeai_metadata`, `generation_data`, `Model`, plus les champs EXIF de description et de commentaire. Rend le prompt, le modèle, l'échantillonneur, la graine, les dimensions. **[R]** : la table des clés par outil est la référence la plus complète trouvée ; à comparer à la table du cœur.

**`@delicity/ai-image-detection` 1.1.0 (MIT)** — métadonnées seulement, aucune analyse de pixels. Ce qu'il ajoute à une lecture de clés :

- **Signature Grok** : un identifiant au format UUID dans le champ EXIF `Artist`, et une même signature longue dans `ImageDescription` et `UserComment`. Confiance « haute » seulement si l'identifiant est conforme et si la signature est identique dans les deux champs.
- **Pauvreté EXIF** : « riche » (marque ou modèle d'appareil, plus réglages d'exposition ou note du fabricant), « pauvre », « absent ».
- **Incohérences** : C2PA contre mots-clés, appareil photo déclaré contre indices d'IA, ordre des dates, dates dans le futur.
- Niveaux de sortie : `verified`, `inconsistent`, `signal`, `none`, avec confiance en mots, constats, raisonnement et mises en garde. Proche du modèle d'isitai.
- **[R]** : la signature Grok à double champ et les contrôles de cohérence de dates. À vérifier sur des fichiers réels avant d'en faire un signal.

**`@aedilic/nonescape` 1.0.4 (Apache-2.0)** — classifieur d'images. Le paquet ne contient **pas** le modèle : il charge `onnxruntime-web` depuis un CDN et télécharge `nonescape-mini-v0.onnx` depuis un stockage de l'éditeur, ou appelle son API. Normalisation ImageNet, softmax, seuil 0,5. Architecture, données d'entraînement et licence des poids : **non trouvées dans le paquet**. Rien à reprendre ; exemple de ce qu'un paquet « local » ne doit pas faire (téléchargement silencieux à l'exécution).

## 3. Le reste, en une table

| Paquet | Registre | Ce que c'est, à la lecture | Note |
|---|---|---|---|
| `is-it-slop`, `is-it-slop-preprocessing` | crates, PyPI | TF-IDF + régression logistique en ONNX, découpage en fenêtres | décrit dans `OSS-patterns-reuse.md` §2-3 ; compléments en 2.6 |
| `llm-detector` | PyPI | divergence contre deux profils, agrégations | décrit dans `OSS-patterns-reuse.md` §4 ; 30 téléch./mois |
| `thinkst-zippy` | PyPI | compression avec amorce de texte IA (fichier `ai-generated.txt` embarqué) | famille mesurée dans le banc (AUROC 0,82 puis 0,56 en français) ; licence MIT dans le sdist |
| `pangram-sdk` | PyPI | client HTTP d'un service payant | aucun algorithme local ; MIT |
| `aidetector`, `openai-detector`, `sloplint`, `deslop` | PyPI | petit entraîneur de classifieur ; client de l'ancien classifieur OpenAI ; linter Markdown ; réécriture par LLM | non lus en détail |
| `raid-bench` | PyPI | outil d'évaluation RAID et ses détecteurs de référence | sert au banc, pas à la détection |
| `audioseal` | PyPI | détecteur de marque audio, sortie par échantillon + message de 16 bits | MIT ; déjà dans `FALLBACK` §4.2 ; 155 652 téléch./mois |
| `videoseal` | PyPI | marque image/vidéo de Meta | MIT (fichier du sdist ; métadonnées vides) |
| `trustmark` | PyPI | marque image d'Adobe, charge utile avec code correcteur | MIT |
| `invisible-watermark` | PyPI | marque DWT-DCT utilisée par Stable Diffusion | MIT ; c'est le `sd-watermark` de la feuille de route |
| `wavmark`, `silentcipher` | PyPI | marques audio | MIT |
| `llm-watermark` | PyPI | marquage de logits | licence absente : **[I]** |
| `humanizer-lint` | npm | linter : expressions types, rythme plat, répétitions ; se dit « pas un détecteur » | MIT |
| `slopless` | npm | règles textlint pour Markdown anglais | MIT ; 7 494 téléch./mois |
| `patina-cli`, `humanize-cli`, `zero-slop` | npm | détection de motifs puis réécriture (par LLM ou service hébergé) | MIT |
| `slopsift`, `plain-english`, `@lukstei/slop-grader`, `slop-chop-wasm` | npm | linters de prose à règles ; le dernier en WebAssembly (5,7 Mo) | MIT ; non lus en détail |
| `mcp-varianceiskey` | npm | serveur MCP qui appelle un service local ; l'algorithme n'est pas dans le paquet | MIT |
| `prose-sanitiser-slop`, `ai-slop`, `slop-lint` | crates | analyseurs de tics d'écriture à règles, rapport seul | MIT ou Apache ; non lus en détail |

Projets GitHub du cahier des charges, sans paquet : `liamdugan/raid` et les détecteurs Hello-SimpleAI sont couverts par le banc (RAID, HC3, `roberta-openai`). `Croups/is-it-ai`, `umm-maybe/AI-image-detector` et `sdxl-detector` : **non lus** (voir §8).

## 4. Synthèse 1 — familles d'algorithmes

| Famille | Qui | Preuve publiée | Coût | Dans isitai ? |
|---|---|---|---|---|
| Restes de chatbot, aveux, champs non remplis | tous les paquets de règles | évidence par construction | nul | oui (artefacts de copier-coller) |
| Empreintes d'outil dans le texte (`utm_source`, balisage de citation) | `avoid-ai-writing` | évidence par construction | nul | à vérifier ; probablement partiel |
| Caractères invisibles et sosies, avec normalisation | `avoid-ai-writing`, `pistachi`, `declawd` | attaque documentée (RAID : 8 à 9 points perdus, `COMPETITORS-commercial` §7.4 n° 5) | nul | partiel |
| Listes de mots et d'expressions | `avoid-ai-writing`, `slop-detector`, `slop-guard`, `pistachi`, `slopfix`, `naturable` | sur-représentation mesurée par modèle (EQ-Bench) ; aucune mesure de faux positifs sur documents | nul | non ; **non mesuré** |
| Motifs rhétoriques (contraste, triade, question rhétorique) | `slop-detector`, `avoid-ai-writing`, `slop-guard`, `@e1i0/human`, `slopfix` | aucune mesure publiée ; faux positifs observés sur le français formel | nul | oui, couche `rhetoric`, descriptive |
| Mise en forme de chatbot (puces à terme en gras, titres, émojis) | `pistachi`, `slop-guard`, `avoid-ai-writing`, `textlint-ja` | banc : la mise en forme porte une part du signal, et ne se transfère pas | nul | non |
| Typographie (tiret cadratin, guillemets courbes) | la plupart | polarité instable, mise à zéro par `avoid-ai-writing` | nul | non, et à ne pas ajouter comme signal |
| Stylométrie à seuils fixes | `ai-text-detector`, `pistachi`, `antitransformer`, `avoid-ai-writing` | banc : 14 à 72 % de faux positifs hors distribution pour la version entraînée | < 1 ms | non, écartée par le banc |
| TF-IDF + régression logistique | `is-it-slop`, `vurst-ai` | banc : AUROC 0,97 puis 0,55 en français | 1 ms, quelques Mo | non, écartée par le banc |
| Compression | `thinkst-zippy` | banc : 0,82 puis 0,56 | 4 ms | non |
| Ajustement de règles par contraste sur corpus | `slop-guard`, `@e1i0/human` | méthode, pas un détecteur | hors ligne | non |
| Marque de texte à clé | `synthid-text`, `provcheck-synthid-text`, `declawd` | article SynthID ; inutilisable sans clé | faible | non |
| Marques image, audio, vidéo | `audioseal`, `trustmark`, `invisible-watermark`, `videoseal`, `provcheck-*` | articles et `FALLBACK` §4 | modèle de 1 à 100 Mo | prévu (`sd-watermark`, AudioSeal) |
| Métadonnées de génération d'image | `sd-metadata`, `delicity`, `pistachi` | déterministe | nul | oui |
| Cohérence des métadonnées (dates, appareil contre IA, EXIF pauvre) | `delicity` | aucune mesure | nul | partiel (`inconsistent` existe) |
| Classifieur d'image téléchargé | `nonescape` | aucune dans le paquet | réseau | non |

## 5. Synthèse 2 — actifs réutilisables

| Actif | Contenu | Licence | Adresse | Usage possible |
|---|---|---|---|---|
| Listes EQ-Bench | 1 655 mots, 430 trigrammes, anglais, fiction | MIT (fichier de licence amont lu) | https://github.com/sam-paech/slop-score | table d'expressions descriptive ; jamais un score |
| Gardes du détecteur de contraste | 41 expressions et leurs exclusions | MIT | idem, et `slop-detector` sur npm | cas de test négatifs pour `rhetoric` (à réécrire, pas à copier) |
| Paquets de règles Naturable | 23 règles anglaises, 16 chinoises, schéma JSON, poids par usage | **CC BY 4.0** (crédit obligatoire) | https://github.com/GUCCI-atlasv/naturable-rules | modèle de format de règle ; règles chinoises |
| Règles françaises `slopfix` | environ 110 expressions | MIT, origine non citée | https://github.com/Zwarmex/slopfix | **à mesurer d'abord** : plusieurs formules sont du français formel courant |
| Détecteurs espagnols `@e1i0/human` | 35 constructions avec contre-exemples, 12 registres | MIT | https://github.com/e1i0r/human | modèle de fiche par motif ; espagnol |
| Règles japonaises | 5 règles textlint | MIT | https://github.com/textlint-ja/textlint-rule-preset-ai-writing | japonais |
| Table des clés par outil | 15 générateurs d'image | MIT | https://github.com/enslo/sd-metadata | compléter la table du cœur |
| Registre de points de code | classes de caractères porteurs et règles de position | Apache-2.0 | https://github.com/san-digital/declawd | normalisation |
| Adaptations `avoid-ai-writing` en allemand, français, italien, roumain, suédois | fichiers de compétence | **non lue** | https://github.com/jurigis/avoid-ai-writing-multilingual | à lire avant tout usage |

Licences à surveiller :

- La page Wikipédia « Signs of AI writing » est sous **CC BY-SA 4.0**. Une liste recopiée de cette page porte le partage à l'identique, même dans un paquet MIT. Aucun des paquets lus ne trace l'origine de ses mots. Règle pour isitai : réécrire les listes à partir de mesures sur un corpus, citer les sources comme inspiration.
- `llm-watermark` (PyPI) n'a pas de licence. `nonescape` : licence des poids inconnue.
- Aucun paquet GPL ni « non commercial » parmi ceux lus.
- Jeux de test : aucun paquet lu ne publie de corpus étiqueté réutilisable. Les corpus humains par registre d'`avoid-ai-writing` vivent dans son dépôt, **non lus**.

## 6. Synthèse 3 — idées à reprendre, classées

### Paquet léger (aucun modèle)

| # | Idée | Source | Preuve |
|---|---|---|---|
| 1 | **Droit de compter mesuré par registre** : un motif ne pèse que s'il se déclenche plus sur l'IA que sur l'humain dans la langue et le registre visés ; sinon poids zéro, motif toujours affiché | `slop-guard` (`sg-fit`), `@e1i0/human` (calibration), `avoid-ai-writing` (deux poids à zéro) | trois paquets indépendants arrivent à la même règle ; cohérent avec `COMPETITORS-commercial` §7.4 n° 11 |
| 2 | **Empreintes d'outil dans le texte** : paramètres `utm_source` de chatbot, balisage de citation resté, champs non remplis | `avoid-ai-writing` | déterministe ; même nature que la couche d'artefacts existante |
| 3 | **Normalisation journalisée avec retour aux positions d'origine**, et registre des points de code en données | `avoid-ai-writing`, `declawd` | RAID : 8 à 9 points perdus sur les caractères de largeur nulle |
| 4 | **Fiche par motif** : ce qu'il détecte, « ce que ce n'est pas », contre-exemples devenus tests | `@e1i0/human`, gardes de `slop-detector` | répond au faux positif « Si vous… / Nous vous… » : chaque garde est un test |
| 5 | **Refus nommés** : `score: null` sous le minimum, script non pris en charge, plafond de longueur | `pistachi`, `avoid-ai-writing` | `COMPETITORS-commercial` §7.4 n° 2 |
| 6 | Signature Grok à double champ, cohérence des dates, complément de la table des générateurs | `delicity`, `sd-metadata` | déterministe ; à vérifier sur fichiers réels |
| 7 | Régions de phrases contiguës fusionnées, et segments par paragraphe | `avoid-ai-writing`, `pistachi` | demande récurrente (voir §7) |
| 8 | Rafales par intervalles entre réapparitions d'un mot, comme caractéristique candidate | `antitransformer` | aucune ; à tester sans attente |

### Paquet complet

| # | Idée | Source | Preuve |
|---|---|---|---|
| 1 | Poids distribués hors du paquet, vérifiés par empreinte, version du modèle dans chaque résultat | `provcheck-weights`, `vurst-ai`, `is-it-slop` | pratique ; le contre-exemple est `nonescape` |
| 2 | Trait de détecteur enfichable à erreurs isolées, une liste de résultats par détecteur | `provcheck-detect` | converge avec `OSS-patterns-reuse.md` §6 |
| 3 | Nettoyage des artefacts de jeu de données réservé à l'entraînement | `is-it-slop-preprocessing` | banc §4 : chute de 0,98 à 0,88 sans la mise en forme |
| 4 | Détecteurs de marque ouverts (AudioSeal, TrustMark, DWT-DCT) | PyPI | déjà planifié ; rien de neuf |

### À ne pas reprendre

- Un score 0–100 ou des « probabilités » issues d'une somme de poids écrits à la main (`avoid-ai-writing`, `pistachi`, `ai-text-detector`, `antitransformer`).
- Le score EQ-Bench comme détecteur de document.
- La détection SynthID sans clé (`provcheck-synthid-text`).
- La typographie comme signal, surtout en français.
- Les listes françaises de `slopfix` telles quelles.
- Le signe de la répétition de n-grammes, tant qu'il n'est pas mesuré : `pistachi` et `is-it-slop` se contredisent.

## 7. Synthèse 4 — présentation des résultats

| Paquet | Chiffre | Classes | Raisons | Par segment | Refus |
|---|---|---|---|---|---|
| `avoid-ai-writing` | 0–100 + « probabilités » | 3 + bande de confiance + 6 libellés | constats typés, sévérité, positions | régions de phrases | trop court, script non pris en charge |
| `slop-detector` | 0–100 | aucune | mots, trigrammes et motifs trouvés, quatre taux | non | non |
| `slop-guard` | 100–0 (100 = propre) | 5 bandes | violations avec règle, extrait, conseil | par règle | non |
| `ai-text-detector` | 0–1 | booléen | mesures brutes | non | 50 caractères |
| `pistachi` | 0–1 ou `null` | `ai`, `mixed`, `human`, `unknown` | phrases, signaux nommés | paragraphes | 40 mots |
| `vurst-ai` | probabilité | booléen | détecteur et version du modèle | non | erreur explicite |
| `@e1i0/human` | comptes par motif | budget dépassé ou non | fiche du motif | phrase | — |
| `delicity` | aucun | 4 niveaux + confiance en mots | constats, raisonnement, mises en garde | — | — |
| `declawd` | aucun | aucune | constats, SARIF | position | refus de conclure écrit dans le README |

Ce que les développeurs demandent, d'après les descriptions, les options et les tickets lus :

- **Un outil de relecture, pas un tribunal.** Les paquets récents les plus téléchargés se présentent comme linters (`textlint-ja`, `slopless`, `humanizer-lint` : « pas un détecteur d'IA »). Sortie attendue : constats, positions, conseil, code de sortie pour l'intégration continue.
- **Des exceptions** : listes d'autorisation par terme (ticket `slop-guard`), mode technique, marqueurs d'ignorance dans le texte, masquage du code et des citations.
- **Des budgets par motif** plutôt qu'un score global (`@e1i0/human`, seuil de 6 constats d'`avoid-ai-writing`).
- **Un serveur MCP et des crochets d'éditeur** : presque tous les paquets de 2026 en livrent un.
- **D'autres langues** : adaptations communautaires en sept langues autour d'`avoid-ai-writing`, paquets japonais, chinois, russe, arabe, espagnol.
- Aucun ticket lu ne demande un pourcentage plus précis.

Conséquence pour isitai : la forme déjà retenue (constats avec `locus`, pas de score pour `rhetoric`, tri-état) correspond à ce que ces utilisateurs emploient réellement. Il manque les exceptions déclarées par l'appelant et un mode « budget » pour l'intégration continue.

## 8. Jeu doré : ce qui peut y être évalué

`bench/golden/PROTOCOL.md` fixe les règles. Rappel des limites : pas encore de harnais, un seul générateur (`deepseek-v4.1-flash`), 150 segments humains (environ 110 anglais, 25 français), donc **≤ 3 % annonçable en anglais, ≤ 11 % en français**, et aucune revendication sur un sous-groupe de moins de 30 fichiers.

| Idée | Classe du jeu | Mesure | Limite |
|---|---|---|---|
| Densité de chaque motif `rhetoric` et de chaque garde (§2.2, §2.7) | `human` contre `ai` | taux de déclenchement par classe et par langue, avec intervalle | français : 25 segments, résultat indicatif seulement |
| Droit de compter par motif (idée 1) | `human` contre `ai` | un motif plus fréquent chez l'humain passe à poids zéro | un seul générateur : la conclusion ne vaut que pour lui |
| Signe de la répétition de n-grammes | `human` contre `ai` | différence de moyenne et son intervalle | tranche la contradiction `pistachi` / `is-it-slop` pour ce générateur seulement |
| Rafales par intervalles (idée 8) | `human` contre `ai` | AUROC | aucune attente |
| Régions et segments (idée 7) | `mixed` | recouvrement entre régions signalées et passages insérés (positions connues) | 100 textes |
| Normalisation (idée 3) | `degraded` (sosies, largeur nulle) | constats identiques avant et après dégradation | mesure de robustesse, pas de justesse |
| Mise en forme de chatbot | `degraded` (Markdown retiré) | ce qui reste du signal sans Markdown | idem |
| Empreintes d'outil (idée 2) | aucune | le jeu n'en contient pas : il faut des textes copiés depuis des interfaces de chatbot | à ajouter comme version 1.1 |

Ce que le jeu ne peut pas trancher : les listes françaises de `slopfix` sur du courriel formel. Il faut d'abord des textes humains français formels, première acquisition déjà demandée par le protocole (§3.1) et par `COMPETITORS-commercial` §7.4 n° 7.

## 9. Non lu ou non vérifié

| Élément | État |
|---|---|
| `Croups/is-it-ai`, `umm-maybe/AI-image-detector`, `sdxl-detector` (cartes de modèle) | non lus, faute de temps |
| Listes de mots Wikipédia « Signs of AI writing » et outils dérivés autres que ceux cités | page non lue ; licence connue (CC BY-SA 4.0) |
| `humanize-cli`, `patina-cli`, `slopless`, `slopsift`, `plain-english`, `zero-slop`, `slop-chop-wasm`, `humanizer-lint`, `@lukstei/slop-grader` | description et structure seulement |
| `prose-sanitiser-slop`, `ai-slop`, `slop-lint` (crates), portage Rust de `slop-guard` | téléchargés, non lus |
| `llm-detector`, `aidetector`, `openai-detector`, `sloplint`, `deslop`, `llm-watermark`, `wavmark`, `silentcipher`, `trustmark`, `audioseal`, `videoseal`, `invisible-watermark` | licence et taille relevées ; code non relu (familles déjà couvertes ailleurs) |
| Contenu des 5 règles japonaises et des règles russes | noms de fichiers lus, règles non lues |
| Décompte exact des listes d'`avoid-ai-writing` | ordre de grandeur, compté par motif grossier |
| Formule de densité de `slop-guard` (dénominateur exact) | non lue |
| Calculs de « perplexité » sans modèle (`ai-text-detector`, `antitransformer`) | noms et constantes lus, détail non relu |
| Origine des 406 841 téléchargements de `@jongleberry/vurst-ai` | inconnue |
| Poids et entraînement de `nonescape-mini-v0` | absents du paquet |
| Toute performance des paquets de règles | aucune mesure publiée trouvée, aucune faite ici (rien n'a été exécuté) |
| Recherche PyPI par mots-clés | PyPI n'a pas d'API de recherche : seuls les noms devinés ont été testés |

