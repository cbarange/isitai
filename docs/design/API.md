# API publique : critique et proposition

État lu le 2026-11-12 sur `0.1.0-alpha.0` (`bindings/node/index.js`, `index.d.ts`, `bindings/python/python/isitai/__init__.py`, `crates/isitai-cli/src/main.rs`, `crates/isitai-core/src/lib.rs`). Les comportements cités ont été observés en exécutant l'addon Node et le module Python compilés, sauf la CLI (pas de binaire compilé : lue dans le code). Ces binaires datent d'avant les dernières modifications de `crates/isitai-core/src/` ; chaque constat a été recoupé avec le code source actuel.

L'option `effort` et le champ `history` sont en cours d'écriture dans `crates/isitai-core/src/` (non commités, non compilés). La section 2.9 commente l'état vu dans l'arbre de travail.

## 1. Ce qu'un développeur pressé rencontre

### Ce qui marche déjà

- Trois fonctions, un rapport identique partout, pas de réseau, pas de postinstall.
- Le verdict est une chaîne lisible, pas un score.
- `location.text` évite de découper la chaîne avec des offsets en octets.
- En Python, un mauvais type lève `TypeError` et un fichier absent lève `FileNotFoundError`.

### Ce qui surprend, par gravité

**A. Un `no-signal` peut vouloir dire « je n'ai rien regardé ».** C'est le défaut le plus grave, parce qu'il contredit la règle du produit.

| Entrée | Résultat actuel |
|---|---|
| Binaire inconnu (zip, docx, octets quelconques) | `no-signal`, `media: "application/octet-stream"`, aucun avertissement |
| Texte non UTF-8 (UTF-16, Latin-1) | idem, aucun avertissement |
| Chemin vers un dossier | `no-signal` avec `warnings: ["read: Is a directory (os error 21)"]`, sans exception |
| `trustAnchorsPem` invalide | toute la lecture C2PA est abandonnée, `no-signal`, un avertissement de dix lignes d'erreur TOML |
| Option mal orthographiée (`{ trustAnchors, mime }`) | ignorée en silence |
| `checkText(undefined)` en Node | analyse la chaîne `"undefined"`, rend `no-signal` |
| `checkFile(undefined)` en Node | rejette avec `undefined: No such file or directory` |

**B. `ai-proven` est inatteignable par défaut.** Sans `trustAnchorsPem`, un manifeste valide plafonne à `ai-signal`. Le développeur qui teste une image ChatGPT conclut que la lib ne marche pas. La checklist de la spec prévoit d'embarquer la liste de confiance : c'est un point d'API, pas seulement de packaging.

**C. Les noms ne disent pas ce que prend la fonction.**

| | Texte | Chemin | Octets |
|---|---|---|---|
| Node | `checkText` | `checkFile` | `check` |
| Python | `check_text` | `check_file` | `check` |
| Natif Node / Python | `checkTextJson` | `checkFileJson` | `checkBufferJson` / `check_bytes_json` |
| CLI | `--text "…"` | argument | absent (pas de stdin) |

`check` est le nom le plus court, donc celui qu'on essaie en premier, et il n'accepte que des octets. `check("du texte")` donne en Node `TypeError: The first argument must be of type string or an instance of Buffer… Received undefined`, et en Python `TypeError: string argument without an encoding`. Aucun des deux messages ne renvoie vers `checkText`.

**D. Synchrone ou asynchrone selon la fonction, en Node.** `checkFile` rend une promesse, `check` est synchrone et hache jusqu'à plusieurs dizaines de Mo sur la boucle d'événements. Or `check` est justement la fonction des uploads, donc celle d'un serveur.

**E. `warnings` et `generator` disparaissent quand ils sont vides.** `report.warnings.length` lève une exception sur le cas le plus courant. Les avertissements sont de la prose anglaise : une application ne peut pas réagir à « signataire hors liste de confiance » sans comparer des phrases.

**F. La spec, le README et le code divergent.**

| Sujet | Spec | Code |
|---|---|---|
| Option de type | `mime` | `declaredMime` |
| `Result.media` | `"text" \| "image"` | type MIME (`"image/png"`) |
| `Result.summary` | présent | absent |
| `Evidence.origin`, `warnings` | absents | présents |
| `--json` | documenté | n'existe pas, la sortie est toujours du JSON |
| Code de sortie 0 | `no-signal` | `no-signal` et `capture-proven` |
| Clé `path` | absente | ajoutée par la CLI, absente des types |

**G. Types.** En TypeScript, `media: string`, `checkText` n'a pas d'options, `location` est une union non étiquetée. En Python, `Report = Dict[str, Any]` : aucune complétion, pas de `py.typed`.

**H. CLI.** Un seul fichier rend quand même un tableau JSON indenté. Pas de sortie lisible, pas de `--version`, pas de stdin. Le code de sortie `0` sur `no-signal` se lit « OK » dans un script (`isitai photo.jpg && publier`).

## 2. Proposition

### 2.1 Fonctions : trois, nommées d'après l'entrée

Pas de `check(x)` polymorphe. Une chaîne seule est ambiguë : texte ou chemin ? Toute devinette finit en `no-signal` trompeur.

| Entrée | Node | Python | CLI |
|---|---|---|---|
| Texte | `checkText(text, options?)` : synchrone | `check_text(text, *, …)` | `--text "…"` |
| Chemin | `checkFile(path, options?)` : `Promise` | `check_file(path, *, …)` | `isitai FICHIER…` |
| Octets | `checkBytes(bytes, options?)` : `Promise` | `check_bytes(data, *, …)` | `isitai -` (stdin, plus tard) |

- `check` devient `checkBytes` / `check_bytes`. Le nom du cœur Rust est déjà `check_bytes`.
- Node : tout ce qui peut lire un fichier entier est asynchrone et tourne hors de la boucle d'événements. `checkText` reste synchrone (moins de 1 ms pour 10 Ko).
- Python : tout reste synchrone. Le GIL est déjà relâché, `asyncio.to_thread` suffit à qui en a besoin.
- Arguments stricts : un mauvais type lève `TypeError`. On retire `String(text)` et `String(path)`.

### 2.2 Entrées acceptées

| Ce que le développeur a | La lib | L'appelant |
|---|---|---|
| Chemin (`string`, `os.PathLike`) | `checkFile` | |
| `Buffer`, `Uint8Array`, `bytes`, `bytearray`, `memoryview` | `checkBytes` | |
| Objet d'upload (`File`/`Blob` web, multer, FastAPI `UploadFile`) | | une ligne, voir les recettes |
| Flux (`Readable`, `ReadableStream`, fichier ouvert) | | l'écrire sur disque puis `checkFile`, ou le mettre en mémoire |
| URL http(s) | jamais | télécharger soi-même |

Raisons : le cœur a besoin d'un flux repositionnable (`Read + Seek`), donc un flux réseau devrait de toute façon être mis en tampon ; et « aucun appel réseau » est une promesse du produit. Le README donne les recettes :

```js
await checkBytes(new Uint8Array(await file.arrayBuffer()), { declaredMime: file.type }); // File, Blob
await checkBytes(req.file.buffer, { declaredMime: req.file.mimetype });                  // multer en mémoire
await checkFile(req.file.path, { declaredMime: req.file.mimetype });                     // multer sur disque
```

```python
check_bytes(await upload.read(), declared_mime=upload.content_type)  # FastAPI
```

### 2.3 Options

Un seul objet d'options, le même pour les trois fonctions. En Python, les mêmes noms en `snake_case`, par mot-clé uniquement.

| Option | Décision | Raison |
|---|---|---|
| `trustAnchorsPem` | garder le nom ; la liste C2PA embarquée devient la valeur par défaut, l'option la **remplace** | le nom dit le format ; `ai-proven` marche sans configuration |
| `declaredMime` | garder le nom, corriger la spec (`mime`) | `mime` laisserait croire qu'on force le type ; ici il est seulement comparé au type détecté |
| `effort` | `"fast" \| "standard" \| "thorough"`, défaut `"standard"` | voir les contraintes ci-dessous |

- Une clé inconnue ou une valeur invalide lève `TypeError` (`ValueError` en Python). Un PEM illisible lève aussi : c'est une erreur de configuration, pas un fait sur le fichier.
- `effort` : la doc dit en une ligne ce que chaque niveau **ne lit pas**. Le rapport répète le niveau utilisé (`"effort": "fast"`), sinon un `no-signal` rapide et un `no-signal` complet sont indiscernables.

### 2.4 Rapport

```ts
interface Report {
  verdict: Verdict;
  mime: string;               // renommé depuis `media` ; type détecté, "text/plain" pour du texte
  generator: string | null;   // toujours présent
  evidence: Evidence[];       // la plus forte en premier
  warnings: Warning[];        // toujours présent, [] si aucun
  effort: Effort;
  history: HistoryEntry[];    // toujours présent, [] si rien (voir 2.9)
  history_summary: 'ai-then-edited' | 'capture-then-ai-edited' | null;
  version: { lib: string; rules: string };
}

interface Warning {
  code: 'unsupported-format' | 'untrusted-signer' | 'type-mismatch' | 'parse-error' | 'remote-manifest-skipped';
  message: string;            // phrase anglaise, pour les logs
}
```

- **Forme stable** : toutes les clés toujours présentes. `generator: null`, `warnings: []`.
- **`unsupported-format`** : émis quand aucun lecteur ne s'applique (binaire inconnu, texte non UTF-8). Le verdict reste `no-signal`, mais l'application peut afficher « format non pris en charge » au lieu de « rien trouvé ».
- **`media` devient `mime`** : c'est un type MIME, et il fait la paire avec `declaredMime`.
- **`summary`** : le retirer de la spec. La traduction n'a pas sa place dans le cœur (voir 2.5).
- **`evidence[].location`** : utilisable tel quel. `{ field }` pour une métadonnée, `{ start, end, text }` pour un texte. Garder les offsets en octets UTF-8 (identiques dans les trois langages, corrects sur un `Buffer` ou des `bytes`) et garder `text` comme chemin normal. Seule la première occurrence est localisée, les autres ne sont comptées que dans la prose de `detail` : à documenter.
- **`history`** : ne doit jamais changer le sens d'un verdict. Une retouche après création ne transforme pas `ai-proven` en autre chose sans que la règle soit écrite dans la spec. Détail en 2.9.

### 2.5 Du rapport à un libellé d'interface

Pas de fonction `label()` dans la lib pour 0.1.0. Une table documentée, que l'application copie et traduit. La page de démo (`site/strings.js`) en est la référence.

| Verdict | Libellé | Ne jamais écrire |
|---|---|---|
| `ai-proven` | Généré par IA : prouvé | |
| `capture-proven` | Capture d'appareil : prouvée | « authentique », « non IA » |
| `ai-signal` | Signal d'IA trouvé | « généré par IA » sans réserve |
| `inconsistent` | Indices contradictoires | |
| `no-signal` | Rien trouvé | « humain », « authentique », « vérifié », une coche verte |

```js
const LABELS = {
  'ai-proven': 'Généré par IA : prouvé',
  'capture-proven': "Capture d'appareil : prouvée",
  'ai-signal': "Signal d'IA trouvé",
  'inconsistent': 'Indices contradictoires',
  'no-signal': 'Rien trouvé',
};
const unsupported = report.warnings.some((w) => w.code === 'unsupported-format');
const label = unsupported ? 'Format non pris en charge' : LABELS[report.verdict];
```

### 2.6 Erreurs

Règle unique : **une exception pour une erreur de l'appelant ou du système, un avertissement pour un problème du contenu.**

| Cas | Comportement |
|---|---|
| Mauvais type d'argument, option inconnue, `effort` invalide, PEM illisible | `TypeError` (Node), `TypeError` / `ValueError` (Python) |
| Fichier absent, dossier, permission, erreur de lecture | Node : promesse rejetée avec le message actuel (`code` standard `ENOENT`… : plus tard) ; Python : `OSError` (déjà le cas pour `FileNotFoundError`) |
| Fichier corrompu, manifeste illisible, format inconnu | jamais d'exception ; rapport avec `warnings` |

Aujourd'hui Node rejette avec `code: "GenericFailure"`, et une erreur de lecture après ouverture (dossier, disque) rend un rapport `no-signal`.

### 2.7 Types

- TypeScript : `mime`, `generator: string | null`, `warnings: Warning[]`, `effort`, options sur `checkText`. Une phrase JSDoc sur chaque verdict pour que le survol de `'no-signal'` dise « rien trouvé, ne veut pas dire humain ». Exporter `Verdict`, `Evidence`, `Warning`, `Report`, `CheckOptions`.
- Python : `Report`, `Evidence`, `Warning` en `TypedDict`, `Verdict` en `Literal`, fichier `py.typed`.

### 2.8 CLI

```
isitai [--json] [--effort NIVEAU] [--anchors racines.pem] [--text "…"] [FICHIER… | -]
```

- Sortie par défaut (plus tard, voir section 5) : une ligne lisible par entrée, `verdict`, chemin, outil, compte des preuves et avertissements.

  ```
  ai-signal       photo.png   ComfyUI   3 evidence, 1 warning
  no-signal       scan.jpg    -         nothing found (does not mean human-made)
  ```
- `--json` : accepté dès maintenant comme option sans effet, puisque la spec le documente ; ce sera le tableau JSON actuel, toujours un tableau, avec la clé `path` (à ajouter aux types comme champ propre à la CLI).
- `--version` et `--effort` maintenant ; `-` (stdin) plus tard.
- Codes de sortie : garder `0`, `1`, `2`, mais les documenter comme « trouvé / pas trouvé », jamais « OK ».

| Code | Sens |
|---|---|
| `0` | aucune preuve ni signal d'IA (`no-signal`, `capture-proven`). **Ne veut pas dire « humain ».** |
| `1` | au moins une entrée `ai-proven`, `ai-signal` ou `inconsistent` |
| `2` | erreur d'usage ou de lecture sur au moins une entrée |

### 2.9 `effort` et `history`, d'après le travail en cours

Vu dans l'arbre de travail : `Effort { Fast, Standard, Thorough }` ; `history: [{ action, digital_source_type?, software? }]` ; `history_summary: "ai-then-edited" | "capture-then-ai-edited"`.

- **`thorough` fait aujourd'hui la même chose que `standard`.** Une valeur publique sans effet surprend. Ne documenter que `fast` et `standard` pour 0.1.0, ou dire en toutes lettres que `thorough` est réservé.
- **`fast` ne lit pas le XMP.** Un fichier dont le seul indice est l'IPTC rend donc `no-signal` en `fast`. Le rapport doit répéter le niveau (`effort`), et la doc de l'option doit le dire en une ligne.
- **Le texte ignore `effort`** : l'accepter sans erreur dans `checkText`, pour garder un seul objet d'options.
- **Casse des clés.** `history_summary` et `digital_source_type` sont les premières clés du rapport en plusieurs mots. Choisir maintenant : garder `snake_case` partout dans le JSON (identique dans les trois langages, critère 5) et le déclarer tel quel dans `index.d.ts`. Ne pas convertir en `camelCase` côté Node.
- **`history_summary` ne dit que des faits positifs**, et aucune valeur ne signifie « retouché sans IA » : c'est le bon choix, à conserver.
- **Forme stable** : `history: []` et `history_summary: null` toujours présents, comme `warnings` (point 3 de la section 4).
- **Libellés** : proposés dans `site/strings.js` (`history.summary.*`).

## 3. Avant / après sur les quatre tâches courantes

### Vérifier un texte

```js
// avant                                   // après (inchangé, plus strict sur le type)
checkText(input).verdict;                  checkText(input).verdict;
```

### Vérifier un fichier sur disque

```js
// avant : ai-proven impossible sans fournir la liste
const pem = fs.readFileSync('C2PA-TRUST-LIST.pem', 'utf8');
const report = await checkFile('photo.jpg', { trustAnchorsPem: pem });

// après : liste embarquée
const report = await checkFile('photo.jpg');
```

### Vérifier un upload (octets en mémoire)

```js
// avant : synchrone, bloque le serveur ; le nom ne dit pas « octets »
const report = check(req.file.buffer, { declaredMime: req.file.mimetype });

// après
const report = await checkBytes(req.file.buffer, { declaredMime: req.file.mimetype });
```

```python
# avant                                         # après
check(data, declared_mime=mime)                 check_bytes(data, declared_mime=mime)
```

### Afficher le résultat

```js
// avant : lève si aucun avertissement ; un zip s'affiche « rien trouvé »
if (report.warnings && report.warnings.length) show(report.warnings.join('\n'));
show(report.verdict === 'no-signal' ? 'Rien trouvé' : report.verdict);

// après
const unsupported = report.warnings.some((w) => w.code === 'unsupported-format');
show(unsupported ? 'Format non pris en charge' : LABELS[report.verdict]);
for (const e of report.evidence) show(`${e.strength}: ${e.detail}`);
```

## 4. À changer avant 0.1.0 (cassant, peu coûteux maintenant)

Classé par importance. Aucun point ne touche aux règles de détection. Les points 1 à 5 tiennent en une journée ; le point 6 est déjà planifié à part.

| # | Changement | Où | Estimation |
|---|---|---|---|
| 1 | **Plus de `no-signal` silencieux.** Avertissement `unsupported-format` pour un binaire inconnu ou un texte non UTF-8. Exception sur erreur de lecture, dossier, PEM illisible, option inconnue, mauvais type (retirer `String(…)`). | Cœur : `check_reader` et `check_bytes` rendent un `Result` au lieu d'un `Report`, ce qui change leur signature pour la CLI et les deux bindings. Bindings : validation des arguments. | 2 h 30 |
| 2 | **`check` devient `checkBytes` / `check_bytes`**, asynchrone en Node. | Bindings : renommage, et le même `AsyncTask` que `checkFile`. | 1 h |
| 3 | **Rapport à forme stable** : `warnings` et `generator` toujours présents ; `warnings` en `{ code, message }` ; `media` renommé `mime` ; `effort` répété dans le rapport. | Cœur : `Report`, sites d'émission des avertissements. Tests croisés à mettre à jour. | 2 h |
| 4 | **Types** : `index.d.ts` à jour, JSDoc par verdict ; `TypedDict` et `py.typed` en Python. | Bindings. | 1 h |
| 5 | **Aligner spec, README et aide de la CLI** : `declaredMime`, retrait de `summary`, `origin`, clé `path`, codes de sortie. Le texte d'aide dit que `0` ne veut pas dire « humain ». Ajouter `--version`. | Docs, `main.rs`. | 1 h |
| 6 | **Liste de confiance C2PA embarquée par défaut**, `trustAnchorsPem` la remplace. C'est le changement le plus visible pour l'utilisateur, mais il a déjà sa ligne dans la checklist de la spec (PEM versionné, workflow planifié) : hors de la journée. | Cœur, CI. | planifié |

## 5. Plus tard

- Toutes les occurrences d'un motif (`spans[]`) et leur nombre en champ, au lieu de la seule première et d'un compte dans la prose.
- CLI : sortie lisible par défaut avec `--json` pour le JSON (section 2.8), stdin (`-`), NDJSON pour les gros lots. Cassant pour les scripts qui lisent la sortie : à faire avant 1.0, pas forcément avant 0.1.0.
- Erreurs Node avec `code` standard (`ENOENT`…) si napi-rs le permet simplement ; sinon garder le message actuel.
- Une fonction `label(report, locale)` seulement si plusieurs intégrateurs recopient la table.
- Entrée flux dans les bindings, seulement si un cas réel dépasse la mémoire et n'a pas de disque.
- Variante navigateur (WASM) : `checkText` et `checkBytes` uniquement, pas de `checkFile`. La page `site/` attend déjà ce contrat dans `site/engine.js`.

## 6. Points à vérifier par le développeur

- `trustAnchorsPem` invalide : l'avertissement observé est une erreur d'analyse **TOML** sur la configuration JSON passée à `c2pa`. Vérifier que ce n'est qu'un message de repli et que la configuration JSON est bien lue quand le PEM est valide.
- Une déclaration `digitalCapture` d'un signataire hors liste donne `no-signal` (preuve `strong` d'origine capture, aucune règle ne la retient). C'est conforme à la spec, mais l'avertissement `untrusted-signer` devient alors la seule trace : raison de plus pour le rendre structuré.
- `ai-proven` plus n'importe quel indice de capture, même `weak` et non signé, donne `inconsistent`. Un simple champ XMP ajouté à la main fait donc tomber une preuve signée. À confirmer comme voulu.
