# Reprise de session — état au 2026-11-12, 13 h 50

Note pour reprendre le travail dans une nouvelle session (autre compte, ou après une coupure).

## État du dépôt

- Tout le code livré est sur `main` et la CI est verte au commit `35d2579` (dernier commit : `3b30914`, documentation seule).
- Démo : dépôt `cbarange/isitai.cbarange.com`, déployée par Netlify à chaque push. Dernier build : isitai `35d2579`.
- Non commité : `corpus/` (voir « Corpus » plus bas).

## Travail en cours : banc d'essai des détecteurs de texte

Objectif : comparer la couche texte d'isitai à des détecteurs publiés (StoryScope, arXiv 2604.03136, et d'autres), en précision et en vitesse, puis proposer un modèle multicouche.

- Code : `bench/detectors/` (lire son `README.md`). 12 détecteurs dans `bench/detectors/algos/`.
- Données, environnement et résultats, **hors dépôt** : `/tmp/isitai-bench/` (`venv/`, `data/`, `results/`, `hf/`). Ce dossier disparaît au redémarrage de la machine.
- État à 13 h 50 : recherche, banc, sélection et réimplémentation terminés. L'exécution complète était en cours (255 fichiers de résultats, dernier détecteur : `fast_detectgpt`). **Le rapport et la vérification n'existent pas encore.**

### Pour finir sans relancer les calculs

```bash
PY=/tmp/isitai-bench/venv/bin/python
ls /tmp/isitai-bench/results | grep -v limit | wc -l    # résultats déjà calculés
$PY bench/detectors/evaluate.py                         # recalcule summary.md et summary.json
```

Reste à faire, dans l'ordre :

1. Vérifier que chaque détecteur a ses 5 jeux de test (`test`, `test_ood`, `test_fr`, `test_fiction`, `test_attack`) ; relancer ceux qui manquent avec `$PY bench/detectors/run.py --algo NOM --variant V --split all`, un seul à la fois.
2. Lancer l'évaluateur, puis chercher les pièges : scores inversés, détecteur entraîné sur les données du test, effet de la longueur.
3. Expérience d'empilement (régression logistique sur les scores) : détecteurs sans modèle seuls, puis avec un petit modèle de langue, puis tous.
4. Écrire `docs/research/BENCH-text-detectors.md` (en français) : résultats, limites, proposition multicouche cohérente avec `docs/research/ROADMAP-detection.md`.
5. Faire recalculer les chiffres clés par une relecture indépendante, et chercher les fuites entre entraînement et test.
6. Passer aussi `corpus/text/` dans les meilleurs détecteurs.

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
