# Reprise de session — état au 2026-11-12, 13 h 50

Note pour reprendre le travail dans une nouvelle session (autre compte, ou après une coupure).

## État du dépôt

- Tout le code livré est sur `main` et la CI est verte au commit `35d2579` (dernier commit : `3b30914`, documentation seule).
- Démo : dépôt `cbarange/isitai.cbarange.com` — c'est là que vit le site (HTML, JS, CSS), déployé par Netlify à chaque push. Ce dépôt-ci ne produit que le module WASM (`site/build.sh` → `site/pkg/`). Dernier module : isitai `35d2579`.
- Non commité : `corpus/` (voir « Corpus » plus bas).

## Banc d'essai des détecteurs de texte : terminé, non relu

Rapport : `docs/research/BENCH-text-detectors.md`. Tableaux : `bench/detectors/results/`. Reste à faire : une relecture indépendante (recalcul des chiffres, fuites entre entraînement et test), puis les trois incréments proposés en section 6 du rapport. Les données et modèles sont dans `/tmp/isitai-bench/`, effacé au redémarrage.

## Corpus

`corpus/` contient 7 fichiers de l'auteur et 117 textes Wikipédia d'avant 2019 (`corpus/text/wikipedia-sources.json` pour la provenance, `corpus/tools/fetch_wikipedia.py` pour le refaire). Il n'est pas commité : une image porte un copyright de banque d'images. Décision de l'auteur attendue.

## Décisions en attente de l'auteur

- Commiter le corpus sans les images aux droits incertains ?
- Ajouter à `check_text` un mode « texte venu d'un OCR » avec des motifs tolérants (voir `docs/research/OCR-layer.md`) ?
- Ouvrir un ticket chez c2pa-rs pour le MP4 lent (voir `docs/qa/REPORT.md`, constat 1) ?
- Premier algorithme à modèle : attendre le rapport du banc.

## Règles de travail

- Ne jamais lire ni utiliser `.env`. Les publications npm, PyPI et crates.io se font par l'auteur ou par le workflow de release (`docs/RELEASING.md`).
- Principes de l'auteur : KISS, pas de sur-ingénierie, diff minimal, mesurer avant d'optimiser.
- Documents de référence : `docs/SPEC-v0.1.md`, `docs/research/ROADMAP-detection.md`, `docs/research/OCR-layer.md`, `docs/qa/REPORT.md`, `bench/RESULTS.md`.
