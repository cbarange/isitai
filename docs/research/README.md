# Recherches du projet — index

Point d'entrée de la recherche menée du 11 au 13 novembre 2026. Chaque ligne donne la question, la conclusion et le document de détail. Plusieurs documents de détail sont longs ; ce fichier en donne l'essentiel.

## 1. Ce que la recherche a établi

| Sujet | Conclusion | Document |
|---|---|---|
| Marché | Saturé du côté des services HTTP payants, presque vide du côté des bibliothèques locales. Personne ne réunit tous les médias dans un paquet. | `MARKET-survey.md` |
| Preuves signées | C2PA donne une certitude quand le signataire est de confiance. Trois listes sont embarquées ; de vrais fichiers ChatGPT, Firefly et Sora donnent `ai-proven`. | `TRUST-lists.md` |
| Feuille de route de détection | Un algorithme par couche et par média, activé par niveau d'effort ; ce qu'il faut refuser de construire. | `ROADMAP-detection.md` |
| Repli probabiliste | Un pourcentage de vérité est impossible ; la grandeur défendable est un rapport de vraisemblance avec intervalle, calibré par langue. | `FALLBACK-probabilistic.md` |
| Détecteurs de texte | 12 familles réimplémentées et mesurées. Les détecteurs entraînés ne se transportent pas ; seuls ceux à petit modèle de langue gardent peu de faux positifs. | `BENCH-text-detectors.md` |
| Léger contre complet | Le léger (9 Ko) tient ses faux positifs mais détecte 4 % ; le complet (210 Mo) détecte 75 % sur d'anciens générateurs et presque rien sur ceux de 2026. | `TIERS-light-vs-full.md` |
| Services payants | Mécanismes et présentation des scores de GPTZero, Pangram, Turnitin, Grammarly et autres. Presque tous les chiffres viennent du marketing. | `COMPETITORS-commercial.md` |
| Paquets open source | 52 paquets inventoriés ; presque tous sont des moteurs de règles à poids fixés à la main, sans taux de faux positifs publié. | `COMPETITORS-open-source.md` |
| Idées de dépôts publics | Seuil conditionnel, abstention, trois états, couche documentaire PDF et DOCX. | `OSS-patterns-reuse.md` |
| OCR | PP-OCRv6 existe et tourne sans PaddlePaddle, mais plusieurs affirmations du fil promotionnel sont fausses. Nos règles exactes résistent mal aux erreurs d'OCR. | `OCR-layer.md` |

Hors de ce dossier :

| Sujet | Document |
|---|---|
| Spécification de la version 0.1 | `docs/SPEC-v0.1.md` |
| Critique de l'API | `docs/design/API.md` |
| Rapport de test et corpus synthétique | `docs/qa/REPORT.md` |
| Mesures de taille, de vitesse et de formats | `bench/RESULTS.md` |
| Protocole du jeu doré | `bench/golden/PROTOCOL.md` |

## 2. Les résultats qui comptent

**Ce qui marche**

- Aucun faux `ai-proven` dans tous les essais, y compris avec des certificats forgés.
- Les rapports sont identiques entre la CLI, Node, Python et WebAssembly.
- Le cœur pèse environ 5,7 Mo et lit un fichier signé en 2 ms environ.

**Ce qui ne marche pas**

- Un texte IA sans trace de copier-coller n'est pas détecté par le cœur.
- Une capture d'écran ou un fichier ré-encodé perd ses métadonnées : le résultat est `no-signal`.
- Les détecteurs statistiques échouent sur les générateurs de 2026, sur la fiction, et font plus de faux positifs en français.

**Chiffres de référence du banc de texte** (détection puis faux positifs, en %, seuil réglé pour 1 % de faux positifs)

| Détecteur | Hors distribution | Français |
|---|---|---|
| isitai, règles seules | 0 / 0 | 0 / 0 |
| Stylométrie sans modèle | 69 / 14 | 50 / 36 |
| Fast-DetectGPT, 125 M de paramètres | 75 / 1 | 22 / 2 |
| Binoculars, 2 × 135 M | 86 / 6 | 47 / 9 |
| GPTTrace, premier du classement RAID | 100 / 24 | 100 / 96 |

## 3. Ce qui n'a pas été vérifié

- Les deux études de concurrents n'ont pas été relues contre leurs sources. La plupart des pages ont été lues à travers un outil qui résume.
- Le banc des détecteurs de texte n'a pas eu de relecture indépendante (recalcul des chiffres, fuites entre entraînement et test).
- Aucune mesure propre sur les classifieurs d'image, de son et de vidéo.
- Aucun fichier d'appareil photo signé n'a été testé.
- Presque tout est mesuré sur macOS arm64.
- Les auteurs non natifs n'ont jamais été mesurés.

## 4. Questions ouvertes

1. Quel jeu de textes de générateurs récents pour régler et annoncer un seuil ?
2. Où trouver 200 textes humains français natifs d'avant 2022 pour la calibration ?
3. Faut-il garder le nom `ai-likely` pour un rapport de vraisemblance qui plafonne à 2,3 ?
4. Deux formes de sortie coexistent dans les documents : `coefficient` (`FALLBACK-probabilistic.md`) et `confidence {value, kind}` (`OSS-patterns-reuse.md`). Le code suit la première.
5. La liste de confiance interim : la garder par défaut malgré ses risques ?
6. Un mode « texte venu d'un OCR » avec des motifs tolérants ?

## 5. Convention

Chaque document sépare ce qui est publié, ce qui est mesuré ici et ce qui est un jugement. Un nouveau document de recherche vise moins de 2 000 mots et s'ajoute au tableau de la section 1.
