# Étude de marché initiale — 2026-11-11

Ce document garde la trace de l'étude qui a lancé le projet : ce qui existait, et pourquoi isitai a pris sa forme actuelle. Les chiffres sont des relevés du 11 novembre 2026 sur les API publiques des registres ; ils n'ont pas été relevés une seconde fois.

## 1. Question de départ

Faire une petite bibliothèque open source utile, dans l'esprit de Mailchecker, qui dise si un contenu a été produit par une IA. Cibles : Node et Python d'abord.

## 2. Détection de texte : l'état de l'art publié

Source : les 63 fichiers de résultats du classement RAID, lus dans le dépôt `liamdugan/raid`. Colonnes : précision à 5 % puis à 1 % de faux positifs, attaques comprises.

| Détecteur | À 5 % | À 1 % | Ouvert |
|---|---|---|---|
| Winston AI | 1,000 | 0,999 | non |
| GPTTrace (Ettin-1B) | 0,999 | 0,995 | oui |
| GPTTrace (Ettin-150M) | 0,998 | 0,989 | oui |
| Grammarly | 0,995 | 0,982 | non |
| GPTZero | 0,972 | 0,929 | non |
| Desklib v1.01 | 0,912 | 0,765 | oui |
| RADAR | 0,639 | 0,431 | oui |
| GLTR | 0,515 | 0,365 | oui |
| Binoculars (sans attaque seulement) | 0,79 | 0,695 | oui |

À retenir :

- Un encodeur ouvert de 150 M de paramètres atteint 98,9 % sur RAID. Sur ce banc, un petit modèle suffit.
- **Ces scores ne se transportent pas.** Le jeu d'entraînement de RAID est public et plusieurs soumissions sont réglées dessus. Notre banc l'a confirmé ensuite : le même GPTTrace accuse 96 % des textes humains français (voir `BENCH-text-detectors.md`).
- Limites connues de la littérature : OpenAI a retiré son classifieur en 2023 ; la paraphrase fait tomber les détecteurs sans entraînement ; les auteurs non natifs sont sur-signalés.

## 3. Paquets existants pour le texte

| Registre | Paquet | Téléchargements par mois | Méthode |
|---|---|---|---|
| npm | `@jongleberry/vurst-ai` | 390 049 | enveloppe Rust autour de `is-it-slop` ; 0 étoile, origine du trafic inconnue |
| npm | `avoid-ai-writing-detector` | 8 152 | règles et stylométrie, anglais |
| npm | `ai-text-detector` | 388 | heuristiques, plus maintenu depuis 2025 |
| PyPI | `synthid-text` | 336 | watermark, exige les clés du fournisseur |
| PyPI | `gptzero` | 131 | client d'API, 2023 |
| crates.io | `is-it-slop` | environ 250 | TF-IDF |
| Hugging Face | `roberta-base-openai-detector` | 336 353 | classifieur de 2019, obsolète |
| Hugging Face | `desklib/ai-text-detector-v1.01` | 69 983 | classifieur |

Conclusion : le marché est saturé du côté des services HTTP payants (GPTZero, Winston, Originality, Pangram, Copyleaks) et presque vide du côté des bibliothèques locales installables. Le détail des mécanismes est dans `COMPETITORS-commercial.md` et `COMPETITORS-open-source.md`.

## 4. Les autres médias

| Couche | Image | Audio | Vidéo |
|---|---|---|---|
| Provenance signée (C2PA) | `@contentauth/c2pa-node` 507 983/mois, `c2pa-python` 455 841/mois | idem | idem |
| Watermark ouvert | `invisible-watermark` 123 254, `trustmark` 17 691 | `audioseal` 155 652 | `videoseal` 15 916 |
| Métadonnées | `exifr` 10,5 M, `@enslo/sd-metadata` 3 680 | — | — |
| Classifieurs | `umm-maybe/AI-image-detector` 65 571, `Organika/sdxl-detector` 13 613 | modèles wav2vec2 | modèles entraînés sur des échanges de visages |
| API commerciales | TruthScan, Sightengine, Hive | Reality Defender (PyPI : 38 584) | Reality Defender |

Deux tentatives seulement réunissaient plusieurs médias dans un paquet local : `@yavqo/pistachi` (92 téléchargements par mois) et `@delicity/ai-image-detection` (74). Personne n'agrégeait provenance, métadonnées et estimation derrière une seule fonction. C'est le créneau retenu.

## 5. Décisions prises à l'issue de l'étude

| Décision | Raison |
|---|---|
| Une bibliothèque « 360 » : texte, image, son, vidéo, PDF | aucun paquet local ne le fait |
| Commencer par le déterministe (C2PA, métadonnées, artefacts) | vérifiable, sans modèle, et sans faux positif sur les preuves |
| Estimation statistique en repli, avec un coefficient et non une certitude | décision du propriétaire du 12 novembre ; voir `FALLBACK-probabilistic.md` |
| Un cœur Rust, des bindings Node, Python et WebAssembly | la brique C2PA de référence (`c2pa-rs`) est en Rust ; un seul validateur donne les mêmes verdicts partout |
| Nom `isitai` | libre sur npm, PyPI et crates.io ; réservé le 12 novembre |

Mesures qui ont appuyé le choix de Rust (détail dans `bench/RESULTS.md`) :

- Un binaire minimal avec `c2pa` 0.92.0 pèse 4,96 Mo, soit 2,6 Mo compressé.
- Le SDK Node officiel pèse 52 Mo, exige Node 22 et télécharge son binaire à l'installation.
- Sur les mêmes fichiers, le validateur TypeScript `@trustnxt/c2pa-ts` déclare invalides deux fichiers que `c2pa-rs` juge valides : deux validateurs donnent bien deux verdicts.

| Mesure | isitai | `c2pa-python` | `c2pa-ts` |
|---|---|---|---|
| JPEG signé, médiane | 1,8 ms | 1,7 ms | 9,9 ms |
| Mémoire | 19 Mo | 37 Mo | 340 Mo |
| Démarrage | 1 ms | 43 ms | 148 ms |

## 6. Ce qui n'a pas été vérifié

- Les tarifs des API commerciales.
- L'origine des 390 000 téléchargements mensuels de `vurst-ai`.
- Les chiffres de précision des classifieurs d'image, de son et de vidéo : seules des tendances de la littérature ont été relevées, aucune mesure.
- Les téléchargements n'ont été relevés qu'une fois.
