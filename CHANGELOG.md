# Journal des modifications

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/) · versions :
[Semantic Versioning](https://semver.org/lang/fr/).

Une entrée par version publiée, jamais réécrite après coup. La section `Non publié` accumule
les changements en cours ; au moment du tag, elle est renommée en `[X.Y.Z] - AAAA-MM-JJ` et une
nouvelle section vide est ouverte.

Catégories : `Ajouté`, `Modifié`, `Déprécié`, `Retiré`, `Corrigé`, `Sécurité`.

## [Non publié]

### Ajouté
- Jeu doré de calibration : protocole écrit avant étiquetage, analyse de puissance, règles
  anti-fuite, manifeste avec empreintes SHA-256 (`bench/golden/`).

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
