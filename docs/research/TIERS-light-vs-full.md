# Score statistique du texte : niveau léger et niveau complet — 2026-11-12

Synthèse des deux prototypes du repli statistique pour le texte non signé. Les détails et les tables complètes sont dans `bench/light/README.md` (PR 11) et `bench/deep-spike/RESULTS.md` (PR 12). Tant que ces deux PR ne sont pas fusionnées, ces fichiers ne sont pas sur `main`.

## 1. Le cadre

- Quand il existe une preuve signée ou un signal, il gagne toujours.
- Sinon, isitai donne une estimation : un rapport de vraisemblance avec son intervalle et un identifiant de calibration (forme définie dans `FALLBACK-probabilistic.md` §7).
- Deux niveaux : un léger dans le paquet normal (cible : moins de 30 Mo), un complet dans un paquet séparé (cible : 500 Mo au plus).

## 2. Niveau léger (PR 11)

Sans modèle : 11 caractéristiques de style, une régression logistique et des tables de calibration. 9 Ko au total, aucune dépendance en plus, 0,2 ms par texte.

**Choix de conception**

- Une caractéristique n'est gardée que si son sens est le même dans chaque famille de sources et chaque langue. Sont restées : longueurs de phrases et de mots, parenthèses, chiffres, mots en capitales, phrases sans majuscule.
- Écartés après mesure : diversité du vocabulaire, répétitions, n-grammes de caractères, décomptes de la couche rhétorique. Leur sens s'inverse d'un corpus à l'autre.
- Abstention sous 150 mots, et pour toute langue sans table. Une table exige 200 textes humains natifs et 200 textes IA de 150 mots et plus.
- Seul l'anglais est admis. Le français s'abstient : 29 textes humains natifs disponibles.

**Mesures** (anglais, 150 mots et plus, seuil du verdict `ai-likely`)

| Jeu | Faux positifs | Détection |
|---|---|---|
| test | 3 sur 884 (0,3 %) | 4,5 % |
| hors distribution | 1 sur 349 (0,3 %) | 3,9 % |
| textes attaqués | 0 sur 395 | 2,6 % |
| fiction de 2026 | 0 sur 250 | 0 % |
| jeu doré, humains anglais | 0 sur 74 (au plus 4,9 %, à 95 %) | — |

Lecture : les faux positifs tiennent, ce qui était le défaut des détecteurs sans modèle du banc (14 à 72 %). La détection est faible. Le rapport de vraisemblance maximal est d'environ 2,3 : le nom `ai-likely` dit plus que ce chiffre ne soutient.

## 3. Niveau complet (PR 12)

Détecteurs sans entraînement, fondés sur un petit modèle de langue, exportés en ONNX et exécutés par un binaire Rust autonome.

**Recommandation de l'essai** : Fast-DetectGPT avec GPT-Neo-125M (licence MIT), en précision fp32, avec le moteur `ort` 2.0.0-rc.15 et ONNX Runtime 1.31.1 livré par plateforme. `rten` 0.28 fonctionne comme repli en Rust pur.

| Option | Téléchargement | Sur disque | ms par texte (4 fils) | Mémoire |
|---|---|---|---|---|
| Fast-DetectGPT GPT-Neo-125M, `ort` | 209,6 Mo | 592,3 Mo | 188 | 1,5 Go |
| Même modèle, `rten` | 201,8 Mo | 562,4 Mo | 390 | 1,5 Go |
| Binoculars, paire SmolLM2-135M | 437,3 Mo | 1 125,5 Mo | 440 | 2,4 Go |

**Constats**

- Les scores sont identiques à PyTorch : écart maximal de 0,0011 sur 1 800 textes. Entre Rust et Python, l'écart est de 1e-13.
- **La quantification int8 est rejetée.** Elle change le classement des textes, et ses scores diffèrent d'un moteur à l'autre. L'AUROC en distribution ne le montre pas.
- Un seul modèle SmolLM2-135M ne suffit pas : 9 textes Wikipédia humains sur 117 accusés, dont 4 sur 10 en français.
- `tract-onnx` échoue à l'exécution sur ces graphes. Le build WebAssembly passe la vérification avec `rten`, pas avec `ort` ; il n'a pas été exécuté.

## 4. Comparaison

Détection puis faux positifs, en %, au seuil réglé pour 1 % de faux positifs sur le jeu de test.

| | Taille | Hors distribution | Français | Fiction de 2026 |
|---|---|---|---|---|
| Léger | 9 Ko | 4 / 0,3 | s'abstient | 0 / 0 |
| Complet (Fast-DetectGPT) | 210 Mo | 75 / 1 | 22 / 2 | 28 / 3 |
| Complet (Binoculars) | 437 Mo | 86 / 6 | 47 / 9 | 31 / 1 |

Les populations ne sont pas identiques : le léger est mesuré sur les textes anglais de 150 mots et plus, le complet sur un sous-échantillon de 400 textes de toutes longueurs.

## 5. Le verrou : les générateurs récents

Sur le jeu doré, écrit par un générateur de 2026, chaque variante du niveau complet signale 0 ou 1 texte IA sur 100. Binoculars y est sous le hasard en anglais (AUROC 0,357). Le jeu doré n'a qu'un générateur et un auteur humain : c'est un indice, pas une mesure. Il va dans le même sens que la fiction du banc.

Conséquence : la précision du niveau complet n'est démontrée que sur des générateurs de 2022-2023. Aucun seuil n'est défendable sans un jeu de textes de générateurs récents.

## 6. Autres limites

- Tout est mesuré sur macOS arm64, sur une machine chargée : les temps sont indicatifs.
- Le français est la langue la plus touchée par les faux positifs pour tous les détecteurs à modèle.
- Les auteurs non natifs n'ont pas été mesurés.
- L'intervalle du niveau léger est nominal : sa couverture de 90 % n'est pas vérifiée.
- Les textes d'entraînement et de calibration datent de 2022-2023.

## 7. Suite proposée

1. Constituer un jeu de textes de générateurs de 2026, sur plusieurs domaines et en français.
2. Réunir 200 textes humains français natifs d'avant 2022 pour ouvrir une table française.
3. Écrire le harnais de calibration commun aux deux niveaux (tables par langue, intervalle vérifié).
4. Décider du nom et du seuil du verdict `ai-likely`, puis fusionner ou non la PR 11.
5. Emballer le niveau complet : poids hors du paquet, vérifiés par empreinte, version du modèle dans chaque résultat.
