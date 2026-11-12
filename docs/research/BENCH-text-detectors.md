# Banc d'essai des détecteurs de texte — 2026-11-12

Document de recherche. Aucun code de la bibliothèque n'a changé. Il complète `docs/research/ROADMAP-detection.md`.

**Statut : non relu de façon indépendante.** La phase de vérification prévue (recalcul des chiffres, chasse aux fuites entre entraînement et test) n'a pas eu lieu : la session a été interrompue. Tous les chiffres sont « mesurés ici » sauf mention contraire, et lus dans `bench/detectors/results/` (`compact.txt`, `summary_sample.md`, `stack.log`).

## 1. Résumé

- La couche texte actuelle d'isitai ne détecte rien sur du texte généré propre : AUROC 0,50 sur tous les jeux, 0 % de détection. C'est attendu : elle ne cherche que des traces de copier-coller.
- **Les détecteurs entraînés sans modèle** (stylométrie, n-grammes) sont minuscules et rapides (0,4 à 1,5 ms par texte), et excellents sur des données semblables à leur entraînement (AUROC 0,97 à 0,98). **Ils s'effondrent ailleurs** : avec le seuil réglé pour 1 % de faux positifs, ils en font 14 à 23 % sur d'autres générateurs et domaines, et 36 à 72 % sur du français.
- **Les détecteurs sans entraînement à petit modèle de langue** (Binoculars et Fast-DetectGPT, modèles de 125 à 135 M de paramètres) sont les seuls dont le taux de faux positifs se transporte à peu près : 1 à 9 %. Leur précision est moyenne, et ils coûtent 100 à 180 ms par texte et un modèle de 260 à 530 Mo.
- **Les classifieurs publiés** sont presque parfaits sur RAID, sur lequel ils ont été entraînés. Un seul généralise correctement (desklib, 435 M de paramètres, 1,74 Go).
- **Fiction écrite par des modèles de 2026** : presque tout échoue. C'est le seul jeu avec des modèles récents, et il est biaisé par la source.
- **L'empilement de détecteurs ne bat pas le meilleur détecteur seul** hors distribution.
- **Recommandation** : ne rien ajouter au cœur pour l'instant. Un détecteur statistique ira dans un paquet optionnel, avec un score séparé qui n'est jamais une preuve, et seulement après une mesure des faux positifs sur du texte humain réel, en français et sur des modèles récents.

## 2. StoryScope (arXiv 2604.03136)

**Publié.** StoryScope détecte la fiction écrite par IA à partir de choix narratifs (304 caractéristiques, 10 dimensions) sur des récits d'environ 5 000 mots : 93,2 % de macro-F1 humain contre IA sur 61 608 histoires. Les caractéristiques sont extraites par un grand modèle de langue.

**Ce que nous avons pu faire.** Une bibliothèque hors ligne ne peut pas appeler un LLM. `storyscope_lite` calcule 48 caractéristiques par expressions régulières et listes de mots (part de dialogue, marqueurs de temps, vocabulaire de morale en fin de texte, etc.). **Ce n'est pas une reproduction de l'article.**

| Variante | AUROC test | AUROC fiction |
|---|---|---|
| `storyscope_lite.lr` (régression entraînée sur RAID) | 0,76 | 0,42 |
| `storyscope_lite.paper-sign` (signes de l'article, sans entraînement) | 0,52 | 0,64 |

L'approximation déterministe ne retrouve pas le signal de l'article. La variante entraînée sur RAID est pire que le hasard sur la fiction : ce qu'elle apprend sur des articles et des recettes ne vaut pas pour des récits.

## 3. Banc d'essai

- **Données** (détail et licences dans `bench/detectors/README.md`) :

| Jeu | Taille | Contenu |
|---|---|---|
| train | 4 000 | RAID sans attaque, 6 domaines, 8 générateurs |
| test | 2 000 | même distribution, autres documents |
| test_ood | 1 000 | domaines et générateurs absents de train (RAID, MAGE, HC3) |
| test_fr | 990 | français : avis d'hôtel (MAiDE-up) et questions-réponses (hc3_french_ood) |
| test_fiction | 500 | humain : r/WritingPrompts ; IA : histoires StoryScope de 5 modèles de 2026 |
| test_attack | 1 000 | RAID avec attaques (paraphrase, homoglyphes, etc.) |

- **Sous-échantillon commun** : 400 textes par jeu (200 pour la fiction), les mêmes pour tous les détecteurs. Les intervalles sont donc larges : environ ± 0,03 à 0,07 d'AUROC.
- **Mesures** : AUROC ; taux de détection à 1 % de faux positifs, avec le seuil fixé sur `test` puis appliqué tel quel aux autres jeux (« transféré »). C'est la mesure qui compte pour une bibliothèque : on ne peut pas régler un seuil par client.
- **Machine** : macOS arm64, CPU seul, 4 fils. Les temps sont une médiane par texte. **Un autre travail a tourné sur la machine pendant une partie des mesures : les temps sont indicatifs.**
- 57 variantes de 12 familles ont tourné sans échec.

## 4. Résultats

Format des colonnes « transféré » : détection / faux positifs, en %, au seuil réglé pour 1 % de faux positifs sur `test`.

| Détecteur | AUROC test | AUROC hors distrib. | AUROC français | AUROC fiction | Transféré hors distrib. | Transféré français | ms/texte | Modèle |
|---|---|---|---|---|---|---|---|---|
| **isitai aujourd'hui** (`isitai_rules`) | 0,50 | 0,50 | 0,50 | 0,49 | 0 / 0 | 0 / 0 | < 0,1 | aucun |
| Stylométrie (`stylometry_lr.full`) | 0,98 | 0,87 | 0,63 | 0,67 | 69 / 14 | 50 / 36 | 0,4 | aucun, < 20 Ko |
| Stylométrie indépendante de la langue | 0,98 | 0,86 | 0,67 | 0,64 | 77 / 23 | 93 / 72 | 0,4 | aucun |
| N-grammes hachés (`tfidf_lr.hash16-lr-q8`) | 0,97 | 0,83 | 0,55 | 0,31 | 72 / 20 | 66 / 55 | 1,0 | aucun, 0,13 Mo |
| Compression (`zippy.zlib-contrast`) | 0,82 | 0,77 | 0,56 | 0,37 | 22 / 2 | 0 / 2 | 4,1 | aucun, 1 Mo de texte |
| GLTR log-rang (`gltr_ppl.gpt2-logrank`) | 0,78 | 0,87 | 0,72 | 0,14 | 22 / 0 | 0 / 0 | 83 | GPT-2, 548 Mo |
| Fast-DetectGPT (`neo125`) | 0,80 | 0,94 | 0,82 | 0,65 | 75 / 1 | 22 / 2 | 96 | GPT-Neo 125M, 526 Mo |
| Binoculars petits modèles (`smollm2-135m`) | 0,83 | 0,95 | 0,81 | 0,70 | 86 / 6 | 47 / 9 | 176 | 2 × SmolLM2-135M, 2 × 257 Mo |
| Telescope (`smollm2-135m`) | 0,63 | 0,79 | 0,69 | 0,83 | 27 / 0 | 38 / 22 | 90 | SmolLM2-135M, 257 Mo |
| Dimension intrinsèque (`phd`) | 0,50 | 0,63 | 0,53 | 0,42 | 12 / 4 | 2 / 4 | 87 | RoBERTa-base, 499 Mo |
| Classifieur `roberta-openai` (2019) | 0,88 | 0,82 | 0,33 | 0,44 | 60 / 6 | 0 / 8 | 48 | 125 M |
| Classifieur `modernbert-raid-mage` int8 | 1,00 | 0,98 | 0,61 | 0,38 | 72 / 2 | 38 / 7 | 51 | 150 M, entraîné sur RAID |
| Classifieur `gpttrace-ettin150` | 1,00 | 0,99 | 0,63 | 0,67 | 100 / 24 | 100 / 96 | 67 | 151 Mo int8, entraîné sur RAID |
| Classifieur `desklib` | 0,99 | 0,99 | 0,84 | 0,79 | 92 / 2 | 19 / 4 | 257 | 1,74 Go, entraîné sur RAID |

Mémoire : 250 à 300 Mo pour la stylométrie (processus Python compris), 2 à 3,5 Go pour les détecteurs à modèle sous PyTorch.

### Lecture

- **Le piège principal : l'entraînement sur RAID.** Les détecteurs entraînés sont jugés sur des données voisines de leur entraînement. Leurs scores sur `test`, et en partie sur `test_ood` et `test_attack`, ne disent rien de leur comportement réel. Le français et la fiction sont les seuls jeux vraiment étrangers.
- **Une partie du signal est un artefact de mise en forme.** Sans les caractéristiques de mise en page, la stylométrie tombe de 0,98 à 0,88 sur `test`, et de 0,63 à 0,38 sur le français.
- **`gpttrace-ettin150`**, premier du classement public RAID à 1 % de faux positifs, déclare IA 96 % des textes humains français au même seuil. Il est entraîné sur de l'anglais.
- **Sur la fiction de 2026**, plusieurs détecteurs à perplexité sont inversés (AUROC 0,08 à 0,17) : les histoires des modèles récents sont moins prévisibles pour GPT-2 que les récits humains de Reddit. Le biais de source (Reddit contre corpus StoryScope) peut aussi y contribuer ; ce n'est pas démêlé.
- **Textes attaqués** : les détecteurs entraînés tiennent (AUROC 0,84 à 0,90), ceux à perplexité baissent (0,67 à 0,79).

### Empilement (modèle multicouche)

Régression logistique sur les scores, ajustée sur `test` seulement.

| Pile | AUROC hors distrib. | AUROC français | AUROC fiction | Transféré hors distrib. | ms/texte |
|---|---|---|---|---|---|
| Sans modèle (stylométrie, n-grammes, compression, StoryScope allégé, règles) | 0,89 | 0,64 | 0,52 | 90 / 28 | 6 |
| Sans modèle + Binoculars | 0,93 | 0,69 | 0,57 | 94 / 28 | 183 |
| Détecteurs à modèle sans entraînement (17) | 0,95 | 0,70 | 0,64 | 68 / 2 | 1 682 |
| Tout (57) | 0,99 | 0,64 | 0,47 | 100 / 29 | 2 899 |

Empiler n'apporte rien hors distribution : la pile sans modèle hérite des faux positifs de ses composants (28 %), et la pile de 17 détecteurs à modèle ne fait pas mieux que Binoculars seul (0,95) pour dix fois le temps.

## 5. Limites

- **Pas de relecture indépendante** (voir le statut en tête).
- **Petits échantillons** : 400 textes par jeu, 200 pour la fiction.
- **Générateurs anciens** : RAID, MAGE et HC3 datent de 2022-2023. Seule la fiction a des modèles de 2026, et elle est biaisée par la source.
- **Français étroit** : avis d'hôtel et questions-réponses, médiane de 70 à 78 mots. Aucun article, essai ou récit français.
- **Petits modèles** : Binoculars et Fast-DetectGPT sont testés avec des modèles de 125 à 135 M de paramètres, pas avec ceux des articles (Falcon-7B). Leurs résultats publiés ne sont pas reproduits ici.
- **Aucune étude de faux positifs sur des auteurs non natifs**, le biais connu de ces détecteurs.
- **Temps indicatifs** ; mémoire mesurée sous PyTorch, pas sous un moteur léger.

## 5 bis. Faux positifs sur le corpus de l'auteur (incrément 1, mesuré le 2026-11-12)

117 textes Wikipédia d'avant 2019, donc humains, en 12 langues (`corpus/text/`), plus le seul texte IA du corpus. Seuils fixés sur `test`, appliqués tels quels. Commande : `bench/detectors/score_corpus.py`. Scores : `bench/detectors/results/corpus_scores.json`.

| Détecteur | Humains accusés au seuil 1 % | Au seuil 5 % | Texte IA (`ai-snowman.txt`) |
|---|---|---|---|
| Binoculars (`smollm2-135m`) | 1 sur 117 (`fr-volcano`) | 3 sur 117 (2 français, 1 portugais) | non détecté |
| Fast-DetectGPT (`neo125`) | 2 sur 117 (`fr-snowman`, `pt-snowman`) | 10 sur 117 (4 français, 2 espagnols, 2 portugais, 1 anglais, 1 japonais) | détecté |

- Globalement, le taux de faux positifs reste proche de la cible : 0,9 % et 1,7 % au seuil de 1 %.
- **Par langue, le français est le plus touché** : 1 texte sur 10 pour chaque détecteur au seuil de 1 %, et 4 sur 10 pour Fast-DetectGPT au seuil de 5 %. Avec 10 textes par langue, ce chiffre est très incertain, mais il dépasse le critère de 2 % proposé plus bas.
- Aucun faux positif en arabe, allemand, italien, néerlandais, polonais, russe et chinois.
- Un seul texte IA : on ne peut rien conclure sur la détection.
- Limites : textes encyclopédiques seulement, coupés à 512 tokens par les détecteurs, 9 ou 10 textes par langue.

## 6. Proposition pour isitai

Cohérente avec `ROADMAP-detection.md` : le cœur reste déterministe ; un score statistique n'est jamais une preuve.

**À ne pas faire**

- **Pas de classifieur entraîné dans le cœur**, même minuscule. La stylométrie tient en 20 Ko et 0,4 ms, mais elle accuse à tort 14 à 72 % des textes humains dès qu'on sort de ses données d'entraînement. Cela viole le premier critère du projet.
- **Pas d'empilement** : aucun gain mesuré.
- **Pas de StoryScope hors ligne** : le signal vient de l'extraction par LLM.

**Couches possibles, par niveau d'effort**

| Niveau | Couche | Coût | Sortie |
|---|---|---|---|
| `fast`, `standard` | ce qui existe (C2PA, métadonnées, artefacts) | 0 | verdicts actuels |
| `deep` (paquet optionnel) | un détecteur sans entraînement à petit modèle, type Binoculars avec SmolLM2-135M | 2 × 257 Mo de modèles (à quantifier), un moteur d'inférence, environ 0,2 s par texte | un score dans un champ séparé, verdict `ai-likely` au mieux |

**Trois incréments, avec test d'acceptation**

1. **Corpus de faux positifs.** Passer `corpus/text/` (117 textes Wikipédia d'avant 2019, 12 langues) et un lot de textes humains français longs dans Binoculars et Fast-DetectGPT. Acceptation : taux de faux positifs mesuré par langue au seuil de 1 %. Si le français dépasse 2 %, le détecteur n'est pas proposé pour cette langue.
2. **Modèles récents.** Générer des textes avec des modèles de 2026 sur les mêmes sujets que le corpus, hors fiction. Acceptation : AUROC et détection à 1 % de faux positifs, par modèle. Sans ce jeu, aucun seuil n'est défendable.
3. **Essai de moteur** (déjà prévu à l'incrément 4 de la feuille de route) : SmolLM2-135M en ONNX quantifié, sous `ort` et sous `rten`. Acceptation : taille du paquet, temps par texte et mémoire sur une machine ancienne, et scores identiques à PyTorch à 0,01 près.

## 7. Reproduire

```bash
PY=/tmp/isitai-bench/venv/bin/python          # voir bench/detectors/README.md pour le créer
$PY bench/detectors/build_data.py             # données
$PY bench/detectors/run_all.py --phase 1,2,3  # tous les détecteurs, un à la fois
$PY bench/detectors/stack.py                  # empilement
$PY bench/detectors/evaluate.py --sample      # summary_sample.md
```

`run_all.py --phase 4` lance 50 variantes supplémentaires ; 15 ont tourné, le reste a été arrêté volontairement.
