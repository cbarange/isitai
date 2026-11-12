# IsItAI — spécification v0.1

## Objectif

Une lib locale, déterministe et hors ligne. Elle dit si un texte ou une image porte une **preuve** ou un **signal** d'origine IA, et elle montre ses preuves.

Elle ne devine pas. Un fichier sans signal reçoit `no-signal`, jamais « humain ».

## Périmètre

| Dans la v0.1 | Hors v0.1 |
|---|---|
| Texte : artefacts de copier-coller d'IA | Classifieur statistique (modèle) |
| Image : C2PA, IPTC/XMP, chunks PNG des outils SD | Watermarks invisibles (TrustMark, SDXL, SynthID) |
| Formats : JPEG, PNG, WebP, AVIF/HEIF (ceux que `c2pa-rs` lit) | Audio, vidéo (v0.2) |
| Node (napi-rs), Python (PyO3/maturin), CLI | Navigateur/WASM, autres langages |

## Matrice des formats

La lecture C2PA est fournie par `c2pa-rs` pour environ 20 formats, quasiment sans coût. Le vrai travail, format par format, ce sont les métadonnées non signées.

Légende :
- ✅ fait et testé sur les fixtures c2pa-rs ;
- 🔜 version indiquée ;
- 👁 à observer sur de vrais fichiers de générateurs avant d'écrire une règle.

| Famille | Formats | C2PA | Métadonnées non signées | Watermark ouvert | Surcoût binaire | Version |
|---|---|---|---|---|---|---|
| Image | JPEG, PNG, WebP, AVIF, HEIC/HEIF, GIF, TIFF, SVG ; DNG et JXL 👁 (pas de fichier signé testé) | ✅ par défaut, `ai-proven` vérifié sur un fichier signé par format | ✅ XMP `DigitalSourceType` (tous formats) ; ✅ chunks PNG (A1111, ComfyUI, InvokeAI, NovelAI) ; 🔜 EXIF `Software`/`Make` (v0.2) ; 👁 champs propres à Midjourney, Gemini, Firefly | 🔜 TrustMark, invisible-watermark/SDXL (v0.3, plugin ONNX) ; SynthID non ouvert | 0 | v0.1 |
| Vidéo | MP4, MOV ; AVI 👁 | ✅ par défaut, `ai-proven` vérifié pour MP4 et MOV | ✅ XMP dans la boîte `uuid` (scan générique) ; 🔜 MP4 `udta` (`©too`, `©swr`) (v0.2) ; 👁 Sora, Veo, Runway | 🔜 VideoSeal (v0.3) | 0 | v0.1 (C2PA), v0.2 |
| Audio | MP3, WAV ; FLAC 👁 ; M4A 👁 (c2pa-python refuse de le signer) | ✅ par défaut, `ai-proven` vérifié pour MP3 et WAV | 🔜 ID3 `TSSE`/`TXXX`, RIFF `INFO/ISFT`, Vorbis comments (v0.2) ; 👁 ElevenLabs, Suno, Udio | 🔜 AudioSeal (v0.3) | 0 | v0.1 (C2PA), v0.2 |
| Document | PDF | ✅ feature `pdf`, activée par défaut ; `ai-proven` vérifié sur un PDF signé, et `express-signed.pdf` (Adobe Express) donne `ai-signal` | ✅ XMP non compressé ; 🔜 dictionnaire Info `/Producer`, `/Creator` (v0.2) ; 👁 exports Gamma, Copilot, Canva | — | +0,5 Mo | v0.1 |
| Document | DOCX, XLSX, PPTX, EPUB | 👁 `c2pa-rs` contient un `zip_io`, mais la doc ne liste pas ces formats : à vérifier | 🔜 `docProps/app.xml` `Application`, `docProps/core.xml` (v0.2) | — | à mesurer | v0.2 |
| Texte | texte brut, Markdown, HTML | 🔜 feature `c2pa-text` (API amont instable, +0,13 Mo, opt-in) | ✅ règles d'artefacts (`crates/isitai-core/rules/text.toml`) ; 🔜 HTML : texte visible + liens `utm_source` (v0.2) | SynthID-Text exige les clés du fournisseur | 0 | v0.1 |

Règle : un format ne passe en ✅ qu'avec au moins une fixture positive et une négative dans le corpus.

## API

Node :

```ts
import { check, checkText, checkFile } from "isitai";

checkText("…texte…");            // texte
await checkFile("photo.jpg");    // chemin
check(buffer, { mime: "image/png" }); // octets
```

Python :

```python
from isitai import check, check_text, check_file
```

CLI :

```bash
isitai [--anchors racines.pem] [--effort fast|standard] [--text "…"] photo.jpg essay.txt
```

La sortie est toujours du JSON. Les options s'appliquent aux fichiers qui les suivent.

Sortie de la CLI : code `0` = rien trouvé, `1` = signal ou preuve IA, `2` = erreur. Le code `0` ne veut pas dire « fait par un humain ».

Erreurs (code `2`) : option inconnue commençant par `--`, fichier illisible, dossier, fichier `--anchors` inutilisable.

### Ancres de confiance

Un PEM d'ancres inutilisable est une erreur, jamais une perte silencieuse de la lecture C2PA. Le cœur expose `validate_trust_anchors(pem)` : le PEM doit contenir au moins un bloc `CERTIFICATE` et être accepté par `c2pa`. La CLI sort en code `2`, Node lève une `Error`, Python lève `ValueError`. Les fonctions `check*` du cœur restent sans échec.

### Effort

`effort` vaut `fast` ou `standard` (défaut). Le texte l'ignore.

`fast` skips the XMP scan of the whole file; C2PA validation may still read a signed file whole; `fast` can miss unsigned metadata, including a contradiction that `standard` would report.

## Schéma de sortie

```ts
type Verdict =
  | "ai-proven"        // manifeste C2PA valide, certificat de confiance, source IA
  | "capture-proven"   // manifeste C2PA valide, certificat de confiance, capture appareil
  | "ai-signal"        // indice non signé ou C2PA non fiable
  | "inconsistent"     // indices contradictoires (ex. IPTC IA + C2PA capture)
  | "no-signal";       // rien trouvé ; ne veut PAS dire humain

interface Result {
  verdict: Verdict;
  media: "text" | "image";
  generator?: string;          // ex. "OpenAI", "Adobe Firefly", "ComfyUI"
  evidence: Evidence[];        // triées par force décroissante
  summary: string;             // phrase lisible, EN par défaut, FR en option
  version: { lib: string; rules: string };
}

interface Evidence {
  id: string;                  // ex. "c2pa.ai-source", "text.oaicite"
  layer: "provenance" | "metadata" | "artifact";
  strength: "proof" | "strong" | "weak";
  detail: string;
  location?: { start: number; end: number } | { field: string };
}
```

Règles de verdict, appliquées dans l'ordre. Une preuve (`proof`) n'est pas annulée par un indice contraire plus faible.

1. Une preuve IA, sans preuve de capture, donne `ai-proven`. Les indices de capture plus faibles restent listés dans `evidence`.
2. Une preuve de capture, sans aucun indice IA, donne `capture-proven`.
3. Une preuve de capture avec un indice IA, quel qu'il soit, donne `inconsistent` : on n'affirme jamais une capture quand quelque chose pointe vers l'IA.
4. Sinon, des indices IA et capture présents ensemble donnent `inconsistent`.
5. Au moins un indice IA `strong`, ou deux `weak` distincts, donnent `ai-signal`.
6. Sinon : `no-signal`.

## Règles de détection

### Image, couche provenance (C2PA via le crate `c2pa`)

- Lire le manifeste actif et l'état de validation.
- Repérer les `digitalSourceType` IA dans les actions du manifeste actif :
  - `trainedAlgorithmicMedia` ;
  - `compositeWithTrainedAlgorithmicMedia`.
- `algorithmicMedia` n'est pas une source IA : l'IPTC le définit comme un média produit par un algorithme sans données d'entraînement.
- Capture : `digitalCapture`, `computationalCapture`.
- Force d'un type déclaré par le manifeste actif : `proof` si le manifeste est de confiance, `strong` s'il est valide, `weak` s'il est invalide.
- Un type hérité du manifeste d'un ingrédient (l'action n'en déclare pas elle-même) donne aussi un indice, plafonné à `strong`, jamais `proof` : la confiance du manifeste de l'ingrédient n'est pas vérifiée. Le détail de l'indice dit qu'il vient d'un ingrédient. Conséquence : une image IA de confiance ouverte puis recadrée dans un autre outil donne `ai-signal` avec `history_summary` = `ai-then-edited`.
- Si la chaîne déclare une source IA, la provenance ne donne aucun indice de capture : « capture puis retouche IA » est un contenu retouché par IA, pas une contradiction.
- Prendre `claim_generator_info` comme `generator`, sauf si le manifeste est invalide.
- Manifeste invalide : avertissement « C2PA manifest is invalid: the file changed after signing, or the manifest is broken », pas de `generator`, pas de `history_summary` ; `history` reste listé.
- Bornes face à un manifeste hostile : `history` garde au plus 64 actions (avertissement au-delà) ; les noms d'action, de type de source et de logiciel sont coupés à 128 caractères.
- Dans `history`, un `digital_source_type` hérité est celui de la première action de l'ingrédient, et seulement celle-là.
- **Piège** : n'importe qui peut auto-signer un manifeste. Il faut donc `verify_trust: true` et les trust anchors de la liste de confiance C2PA, embarquée et versionnée. Une signature valide sur un certificat non fiable ne donne que `ai-signal`.
- **Piège** : `remote_manifest_fetch` vaut `true` par défaut. Il faut le forcer à `false` (et laisser `ocsp_fetch: false`), sinon la lib fait des appels réseau.

### Image, couche métadonnées

- XMP/IPTC `Iptc4xmpExt:DigitalSourceType` avec une valeur IA : `strong`, car non signé.
- Chunks PNG `tEXt` et `iTXt` non compressé. Une clé seule n'est pas un indice : la valeur doit contenir un marqueur (`rules/metadata.toml`).

  | Clé | Marqueur exigé dans la valeur | Générateur |
  |---|---|---|
  | `parameters` | `Steps:` | A1111/Forge |
  | `prompt` | `class_type` | ComfyUI |
  | `workflow` | `nodes` | ComfyUI |
  | `invokeai_metadata` | `{` | InvokeAI |
  | `Software` | valeur égale à `NovelAI`, espaces de bord retirés | NovelAI |

  Tous donnent `strong`, avec `generator` renseigné. Chaque id d'indice sort au plus une fois par fichier. Les valeurs compressées (`zTXt`, `iTXt` compressé) ne sont pas décompressées : elles sont ignorées.
- EXIF `Software` ou `Make` connus d'un générateur : `weak`.

### Texte, couche artefacts

| id | Motif | Force |
|---|---|---|
| `text.oaicite` | `:contentReference[oaicite:N]{index=N}`, `【oaicite:N】` | strong |
| `text.citeturn` | `turn0search3` et variantes (`news`, `view`, `fetch`, `file`, `image`), isolé ou collé à `cite` (`citeturn0search3`) | strong |
| `text.utm-ai` | `utm_source=chatgpt.com`, `utm_source=openai` | weak : le marqueur décrit un lien, pas le texte |
| `text.self-disclosure` | La voix de l'assistant : « as an AI language model » ; « as an AI » suivi, à quatre mots au plus, de « I » ; « as of my (last) knowledge update/cutoff » ; « en tant que modèle de langage », « en tant qu'IA », « en tant qu'intelligence artificielle » suivis de « , je » | strong |
| `text.zero-width` | U+200B, U+2060, U+FEFF au milieu du texte | weak |

Toutes ces règles restent marquées `verified = false` tant qu'elles ne sont pas confirmées sur un corpus réel.

- Il n'y a pas de règle sur le Markdown : `**gras**` et `### titre` touchent 81 % des fichiers Markdown réels.
- `text.self-disclosure` ne doit pas toucher une phrase humaine comme « As an AI model grows, its training bill grows faster. » ou « En tant qu'intelligence artificielle générative, ChatGPT … ».
- Les règles texte tournent aussi sur le contenu d'un fichier reconnu comme texte par le crate `infer` (`text/*` : HTML, XML, script shell ; et SVG), en plus des autres couches, dans la limite `MAX_TEXT_BYTES`. Un texte non UTF-8 ou plus long que la limite donne un avertissement : le texte n'a pas été analysé, ou pas en entier.
- **Piège** : U+200D (ZWJ) est légitime dans les emojis composés. On l'ignore entre deux emojis.
- **Piège** : U+202F et U+00A0 sont de la typographie française normale (`« »`, `:`, `?`). On ne s'en sert jamais comme signal.
- **Piège** : le tiret cadratin et les tournures « IA » ne sont pas des preuves. On les exclut de la v0.1.
- Les motifs vivent dans un fichier `crates/isitai-core/rules/*.toml` versionné, comme la liste de Mailchecker, pour qu'une contribution n'ait pas besoin de toucher au code.

## Architecture

```
isitai/
  crates/isitai-core/     # Rust : règles, C2PA, parsing, verdict
  crates/isitai-cli/
  bindings/node/          # napi-rs, binaires précompilés par plateforme
  bindings/python/        # PyO3 + maturin, wheels abi3
  rules/                  # text.toml, png-keys.toml, generators.toml
  corpus/                 # échantillons de test + manifest.json
  bench/
```

### Décision : un cœur Rust unique, pas d'implémentation native Node ni Python

| Option | Perf v0.1 | Verdicts identiques (critère 5) | Coût |
|---|---|---|---|
| Natif JS + natif Python | suffisante (le hash s'exécute en C dans `crypto` et `hashlib`) | non : deux validateurs C2PA différents (`@trustnxt/c2pa-ts` et `c2pa-python`) | deux bases de code |
| Wrappers fins sur les SDK officiels | suffisante | partiel | `c2pa-node` pèse 52 Mo, exige Node ≥ 22 et télécharge son binaire à l'installation |
| **Cœur Rust + bindings** | la meilleure, mais l'écart est faible en v0.1 | **oui, une seule logique** | une CI multi-plateforme |

La perf ne tranche pas. Ce sont le critère 5 et la réutilisation de `c2pa-rs` qui décident.

**Mesure** (`c2pa` 0.92.0, `default-features = false`, `rust_native_crypto`, `lto`, `opt-level="z"`, `strip`) :
- dylib macOS arm64 de 4,96 Mo, 2,6 Mo en gzip ;
- build release en 1 min 06 s.

Crates : `c2pa` (sans `openssl` ni `default_http` : pas d'OpenSSL système, pas de client HTTP), `png` (chunks), `kamadak-exif`, `quick-xml` (XMP), `regex`, `serde`.

### Distribution

- **Nom npm** : le paquet principal s'appelle `isitai`, sans scope (le nom était libre le 2026-11-11). Les binaires par plateforme sont publiés sous le scope du compte : `@cbarange/isitai-darwin-arm64`, `@cbarange/isitai-linux-x64-gnu`, etc. On ne publie pas de doublon `@cbarange/isitai`, pour ne pas partager les téléchargements entre deux noms. Côté PyPI et crates.io, le nom est `isitai`.
- **Node** : napi-rs. Un paquet `isitai-<plateforme>` par cible, déclaré en `optionalDependencies`, **sans postinstall ni téléchargement**, donc compatible avec le hors-ligne, les proxys et Docker. Node ≥ 18.
- **Fallback Node** : la cible napi-rs `wasm32-wasip1-threads` (documentée dans `napi-rs/cli/docs/wasi.md`) couvre les plateformes non compilées, StackBlitz, Bun et Deno. À valider pendant le week-end 2.
- **Python** : maturin, wheels `abi3` (une seule wheel par plateforme pour Python ≥ 3.9), manylinux + musllinux. Une sdist est publiée en dernier recours (elle exige Rust).
- **Cibles natives** : macOS arm64/x64, Linux x64/arm64 (gnu + musl), Windows x64/arm64.
- **Repère** : `c2pa-python` 0.38.0 publiait macOS, manylinux et Windows, mais pas musllinux. C'est notre avantage pour Alpine.

## Corpus de test

- Fichiers générés soi-même, sans contenu protégé : ChatGPT image, Adobe Firefly, Gemini, Midjourney, ComfyUI, A1111.
- Pour chacun, deux versions : l'original, puis une copie dont les métadonnées sont retirées (`exiftool -all=`).
- Photos d'appareils signées C2PA (Pixel, Leica ou Sony s'ils sont disponibles), plus des photos sans métadonnées.
- Texte : copies réelles depuis ChatGPT web (avec recherche), Claude, Gemini, Perplexity. En face, des textes humains FR et EN contenant des emojis composés et de la typographie française.
- `corpus/manifest.json` donne l'étiquette attendue de chaque fichier. Les étiquettes sont figées avant toute écriture de règle.

## Critères d'acceptation (release 0.1.0)

1. **0 faux `ai-proven`** et **0 faux `ai-signal` strong** sur les fichiers humains du corpus.
2. 100 % des originaux de générateurs qui portent C2PA ou IPTC sont détectés.
3. Les copies sans métadonnées donnent `no-signal`.
4. Aucun appel réseau : un test sans réseau (sandbox) doit passer.
5. Résultat identique pour des octets identiques, en Node, en Python et en CLI (tests croisés).
6. Performance (cibles à mesurer) : texte de 10 Ko en moins de 1 ms, image de 10 Mo en moins de 50 ms.
7. Paquet npm par plateforme de moins de 10 Mo, wheel de moins de 10 Mo. Le spike C2PA seul mesure 4,96 Mo, ce qui laisse environ 5 Mo pour le reste.
8. Installation sans réseau sortant au-delà du registre (pas de postinstall).

## Livraison

| Étape | Contenu |
|---|---|
| Week-end 1 | `isitai-core` : règles texte, chunks PNG, XMP/IPTC, verdict, CLI, corpus v0 |
| Week-end 2 | C2PA (trust, sans réseau), bindings Node et Python, tests croisés |
| Week-end 3 | CI de build multi-plateforme, bench, README avec les limites, publication 0.1.0 |

## Hors sujet assumé

- Une image passée par un réseau social perd souvent son EXIF et son C2PA. Elle tombera en `no-signal`, et le README le dit en premier.
- Le score de probabilité arrivera avec les classifieurs, en plugin, au plus tôt en v0.4.

## Checklist avant 0.1.0

- [ ] **Liste de confiance C2PA embarquée.** Source officielle : `c2pa-org/conformance-public`, fichier `trust-list/C2PA-TRUST-LIST.pem` (licence CC-BY-4.0, attribution dans le README). Synchronisée automatiquement par la C2PA, environ toutes les 1 à 3 semaines (relevé du 2026-11-12). À faire :
  - embarquer le PEM dans le crate, versionné, avec sa date et son commit source ;
  - l'utiliser par défaut, avec une option pour le remplacer ;
  - ajouter un workflow planifié qui ouvre une PR quand la liste change.

  Sans elle, aucun fichier réel (ChatGPT, Firefly…) ne peut atteindre `ai-proven`.
- [ ] Liste TSA (`C2PA-TSA-TRUST-LIST.pem`) : vérifier si `c2pa-rs` en a besoin pour valider les horodatages.
- [ ] Corpus réel : au moins un fichier par générateur (ChatGPT, Firefly, Gemini, Midjourney) et des photos d'appareils signées.
- [ ] Mesurer l'addon Node en profil `size` (9,4 Mo en `release`, limite de 10 Mo).
- [ ] Valider en CI le build `wasm32-wasip1-threads`.
