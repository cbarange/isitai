# Journal des modifications

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) · versions :
[Semantic Versioning](https://semver.org/lang/fr/).

Une entrée par version publiée, jamais réécrite après coup. La section `Non publié` accumule
les changements en cours ; au moment du tag, elle est renommée en `[X.Y.Z] - AAAA-MM-JJ` et une
nouvelle section vide est ouverte.

Catégories : `Ajouté`, `Modifié`, `Déprécié`, `Retiré`, `Corrigé`, `Sécurité`.

## [Non publié]

### Ajouté
- Score statistique du texte brut, sans modèle (`text-light-v1`) : objet `coefficient` du rapport
  (`lr`, `lr_interval`, `coverage`, `calibration_id`, `prevalence_used`, `posterior`) et `notes`.
  C'est un rapport de vraisemblance, pas un pourcentage ; `posterior` reste `null` sans prévalence.
- Verdict `ai-likely` : ni preuve ni indice, et score au-dessus du seuil à 1 % de faux positifs de
  la table de calibration. Une preuve ou un indice l'emporte toujours.
- Tables de calibration par langue et par longueur, embarquées (9 Ko). Une seule langue admise à
  ce jour : l'anglais. Les autres langues et les textes de moins de 150 mots donnent `lr: null`
  et un avertissement.
- Options `score` (CLI `--no-score`) et `prevalence` (CLI `--prevalence`) dans la CLI, Node,
  Python et WASM ; `checkText` / `check_text` acceptent ces options.
- `bench/light/` : construction du jeu d'entraînement, sélection, calibration, mesures
  (`results.json`) et test de parité Python / Rust sur 258 textes.
- Jeu doré de calibration : protocole écrit avant étiquetage, analyse de puissance, règles
  anti-fuite, manifeste avec empreintes SHA-256 (`bench/golden/`).

### Modifié
- Code de sortie 1 de la CLI : aussi pour `ai-likely`.
- Un fichier de texte brut reçoit par défaut un objet `coefficient` et, en cas d'abstention, un
  avertissement supplémentaire ; `--no-score` rend les rapports d'avant.

### Sécurité
- Le journal des versions est désormais un prérequis de publication : un tag sans entrée
  correspondante est refusé par la CI.

## [0.1.0-alpha.0] - 2026-11-12

### Ajouté
- Cœur Rust hors ligne : lecture C2PA (liste de confiance embarquée, autorités d'horodatage),
  métadonnées XMP / PNG / EXIF / ID3, artefacts de copier-coller.
- Cinq verdicts : `ai-proven`, `capture-proven`, `ai-signal`, `inconsistent`, `no-signal`.
- Bindings Node.js (napi-rs), Python (maturin) et WASM.
- Entrées en flux : `stdin`, corps HTTP, corps S3 ; textes UTF-16 et Windows-1252.
- CLI `isitai`.

### Notes
- Pré-alpha : l'API peut changer sans préavis.
- Le paquet ne fait aucun appel réseau et ne télécharge aucun modèle.

[Non publié]: https://github.com/cbarange/isitai/compare/v0.1.0-alpha.0...HEAD
[0.1.0-alpha.0]: https://github.com/cbarange/isitai/releases/tag/v0.1.0-alpha.0
