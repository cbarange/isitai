# Rapport QA — isitai 0.1.0-alpha.0

Date : 2026-11-12. Machine : macOS arm64, rustc 1.99.1, Node 24.15, Python 3.15.
Build testé : commit `f5e48b8`. L'option `effort` et le champ `history` ne sont pas couverts.

Marques : **[O]** observé avec la commande donnée, **[S]** supposé. Les constats 1, 2, 3, 6 et 10 ont été reproduits une seconde fois, indépendamment, sur l'arbre de travail du 2026-11-12.

## Résumé

- **0 faux `ai-proven`** sur 315 fichiers lus avec les ancres de test : 223 synthétiques, 13 signés, 12 variantes (manifeste falsifié ou greffé), 67 fixtures c2pa-rs. [O]
- **Le critère 1 n'est pas tenu pour `ai-signal`** : 13 fichiers humains sur 80 reçoivent un verdict IA appuyé sur une preuve `strong`, et 3 autres sur deux preuves `weak`. [O]
- Un MP4 de 800 Ko occupe l'outil 28 s (temps quadratique). [O]
- Aucun crash, aucun panic, aucune croissance de mémoire liée à une longueur déclarée. [O]
- CLI, Node et Python donnent le même rapport sur 247 fichiers, sauf un avertissement présent dans la CLI seule. [O]

## Reproduire

Utiliser un `CARGO_TARGET_DIR` que personne d'autre n'utilise : pendant ce test, un build concurrent a écrasé le binaire une fois, et tout a dû être rejoué.

```bash
T=$(mktemp -d)
CARGO_TARGET_DIR=$T/target cargo build --release --locked -p isitai-cli
B=$T/target/release/isitai; C=$T/corpus
python3 -I bench/corpus/make_synthetic.py $C
python3 -I bench/corpus/check_expected.py $B $C --out $T/run.json     # code 1 : « 223 files, 48 not ok »
```

Corpus signé (réseau requis pour les fixtures, `gh` authentifié) :

```bash
bench/fetch_fixtures.sh $T/c2pa
python3 -m venv $T/venv && $T/venv/bin/pip install --quiet c2pa-python==0.38.0
A=$T/c2pa/fixtures/test_cert_root_bundle.pem; S=$T/signed; V=$T/variants
$T/venv/bin/python -I bench/corpus/make_signed.py $T/c2pa/fixtures $T/c2pa/certs $S
$T/venv/bin/python -I bench/corpus/make_signed_variants.py $T/c2pa/fixtures $T/c2pa/certs $S $V
python3 -I bench/corpus/check_expected.py $B $S --anchors $A          # « 13 files, 0 not ok »
python3 -I bench/corpus/check_expected.py $B $V --anchors $A          # « 12 files, 4 not ok »
```

Depuis que la liste de confiance C2PA officielle est embarquée, le même corpus signé vérifie aussi que le certificat de TEST de c2pa-rs n'est pas de confiance par défaut. Sans `--anchors`, `check_expected.py $B $S` doit annoncer « 13 files, 13 not ok », tous en `VERDICT` : `ai-signal` au lieu de `ai-proven`, `no-signal` au lieu de `capture-proven`, avec l'avertissement « signer is not in the trust list ». Avec `--anchors $A`, « 13 files, 0 not ok » (relevé du 2026-11-12).

`make_synthetic.py` est déterministe (mêmes sha256 sur deux générations). Les étiquettes ont été fixées avant la première exécution et jamais ajustées.

## Ce qui a été testé

| Catégorie | Fichiers | Écarts | Contenu |
|---|---|---|---|
| `text-human` | 39 | 12 | prose FR/EN, Markdown, code, CSV/JSON/YAML/HTML, emoji ZWJ, typographie française, BOM, 10 Mo, textes qui citent les artefacts |
| `text-ai` | 27 | 6 | un positif par alternative de chaque règle de `text.toml` |
| `text-path` | 18 | 15 | le même positif dans d'autres conteneurs : HTML, XML, shebang, Latin-1, UTF-16, plus de 16 Mio |
| `png` | 21 | 7 | chaque clé de `metadata.toml` en tEXt/iTXt/zTXt, clés au contenu non IA |
| `xmp` | 67 | 7 | 11 valeurs DigitalSourceType × JPEG/PNG/WebP, MP4, PDF, SVG, frontières de 4 Mio |
| `hostile` | 45 | 1 | vide, 1 octet, aléatoire, tronqués, mauvaise extension, longueurs déclarées géantes |
| `perf` | 6 | 0 | PNG à 1 M de chunks, textes pathologiques de 10 Mo |
| signé | 13 | 0 | 12 formats IA + 1 capture, certificat de test c2pa-rs |
| variantes signées | 12 | 4 | manifeste falsifié, greffé, preuve signée + XMP contraire |

En plus : un balayage de 7 405 fichiers texte locaux présumés humains (`.md`, `.rs`, `.js`, `.py`).

## Constats, par gravité

Classe : **B** bug, **R** règle trop large, **S** écart avec la spec, **L** limite connue.
Variables : `$B` binaire, `$C` corpus synthétique, `$S` corpus signé, `$V` variantes, `$A` ancres de test, `$T` dossier temporaire.

| # | Gravité | Classe | Constat | Reproduction |
|---|---|---|---|---|
| 1 | Critique | B | **Temps quadratique sur MP4.** 100 000 boîtes `free` vides (800 Ko) : 28,5 s ; ×4 à chaque doublement. [O] Cause dans le parseur BMFF de c2pa-rs. [S] | `/usr/bin/time -l $B $C/len_mp4_size_zero_boxes.mp4` |
| 2 | Haute | R | **Clés PNG sans regard sur le contenu.** Un chunk `prompt`, `parameters` ou `workflow` donne `ai-signal` `strong` et un `generator`, même vide. `Software` contenant « NovelAI » aussi. 5 faux positifs humains. [O] | `$B $C/png_h_prompt_empty.png` |
| 3 | Haute | R | **Règles texte `strong` sur du texte humain** qui emploie ou cite le motif (article, rapport de trafic, code, doc). 7 faux positifs. Le `README.md` et la spec du dépôt sont eux-mêmes `ai-signal`. [O] | `$B --text 'As an AI model grows, its training bill grows faster.'` ; `$B README.md` |
| 4 | Haute | B | **Une preuve signée est annulée par un XMP non signé.** Manifeste IA de confiance + XMP `digitalCapture` (preuve `weak`) : `inconsistent` au lieu de `ai-proven`. [O] | `$B --anchors $A $V/v_signed_ai_plus_xmp_capture.jpg` |
| 5 | Haute | B | **Les règles texte ne tournent pas si le fichier est reconnu comme autre chose** : HTML, XML, script avec shebang, texte qui commence par `BM`, `MZ`, `ID3`, `%PDF`, ou tout texte contenant `<svg` dans les 8 premiers Ko. Le même contenu via `--text` donne `ai-signal`. 12 faux négatifs ; 377 fichiers `.rs` réels sur 3 000 sont vus comme scripts shell. [O] | `$B $C/tp_html_doctype.html` puis `$B --text "$(cat $C/tp_html_doctype.html)"` |
| 6 | Haute | B | **Fichier d'ancres illisible : la lecture C2PA est coupée.** Un fichier signé IA passe de `ai-signal` à `no-signal`, code 0, avec seulement un avertissement « TOML parse error ». [O] | `: > $T/empty.pem; $B --anchors $T/empty.pem $S/ai.jpg` |
| 7 | Moyenne | R | **Deux `weak` suffisent sur du Markdown humain** : un titre ou du gras, plus un seul U+200B. 3 faux positifs synthétiques et 1 réel. [O] | `$B $C/h_notion_export_zwsp.md` |
| 8 | Moyenne | B | **Preuves PNG non dédupliquées.** 300 000 chunks `parameters` (7,2 Mo) : 89 Mo de JSON, 551 Mo de RSS. [O] | `$B $C/perf_png_300k_parameters.png \| wc -c` |
| 9 | Moyenne | B | **PNG à très nombreux petits chunks.** 1 M de chunks vides (12 Mo) : 3,1 s, 111 Mo de RSS ; linéaire, environ 3 µs par chunk. [O] | `/usr/bin/time -l $B $C/perf_png_1m_tiny_chunks.png` |
| 10 | Moyenne | S | **`citeturn0search0` n'est pas détecté** : la règle exige une frontière de mot avant `turn`. 6 faux négatifs. [O] | `$B --text 'Paris citeturn0search3.'` |
| 11 | Moyenne | R | **Paquet XMP cité dans un HTML** : `ai-signal` `strong` ; le même texte en Markdown donne `no-signal`. [O] | `$B $C/h_doc_xmp_in_script.html` |
| 12 | Moyenne | S | **`algorithmicMedia` absent des règles** alors que la spec le liste comme source IA : `no-signal`, y compris dans un manifeste signé de confiance. [O] | `$B --anchors $A $V/v_signed_algorithmicMedia.jpg` |
| 13 | Moyenne | B | **Manifeste invalide : aucun avertissement**, mais `generator` rempli à partir de ce manifeste. [O] | `$B --anchors $A $V/v_tampered_ai_pixel.jpg` |
| 14 | Moyenne | B | **Texte non UTF-8 ou trop long : ignoré sans avertissement** (Latin-1, UTF-16, au-delà de 16 Mio). [O] | `$B $C/tp_latin1.txt` |
| 15 | Basse | B | `Software: NovelAI` n'est lu qu'en tEXt, pas en iTXt ni zTXt. [O] | `$B $C/png_software_novelai_itxt.png` |
| 16 | Basse | L | XMP non vu : iTXt compressé, paquet UTF-16, sidecar `.xmp`, paquet de plus de 256 Kio à cheval sur une fenêtre. [O] | `$B $C/xmp_packet_300k_straddles_chunk.png` |
| 17 | Basse | S | **CLI.** `--json` (donné dans la spec) est pris pour un fichier, code 2. Un dossier en argument : `no-signal`, code 0. [O] | `$B $C/h_fr_prose.txt --json; echo $?` |
| 18 | Basse | S | **Schéma de sortie différent de la spec** : `media` est un type MIME, pas de `summary`, champs `origin` et `warnings` en plus ; `generator` rempli même avec `no-signal`. [O] | `$B --anchors $A $V/v_signed_digitalArt.jpg` |
| 19 | Basse | B | **Bindings.** La CLI ajoute l'avertissement « declared type differs », pas Node ni Python. Node : `checkText(null)` répond `no-signal` sans erreur. Un surrogate isolé est accepté par Node, refusé par Python. [O] | `bench/crosslang/diff.py` |

## Faux positifs de chaque règle texte sur du contenu humain

Base : 39 fichiers humains synthétiques et 7 405 fichiers réels. Les fichiers synthétiques ont été écrits en connaissant les règles : ils montrent que le cas existe, pas sa fréquence.

| Règle | Force | Synthétique (touchés / verdict IA) | Réel (touchés / verdict IA) | Analyse |
|---|---|---|---|---|
| `text.oaicite` | strong | 1 / 1 | 0 / 0 | Très spécifique. Faux positif seulement quand un texte cite l'artefact. |
| `text.citeturn` | strong | 1 / 1 | 0 / 0 | Même cas. |
| `text.utm-ai` | strong | 3 / 3 | 0 / 0 | Touche un rapport de trafic, du code, et tout message humain qui contient un lien copié depuis ChatGPT. Le signal porte sur le lien, pas sur le texte. |
| `text.self-disclosure` | strong | 3 / 3 | 0 / 0 | La plus fragile : « As an AI model grows… » est une phrase de journaliste. Aucune ancre sur la première personne. |
| `text.zero-width` | weak | 5 / 3 | 3 / 1 | Légitime en thaï, fréquent dans du texte copié du web. |
| `text.markdown-residue` | weak | 9 / 3 | 1 861 / 1 | Touche 81 % des `.md` réels et du code (`f(**a, **b)`). Ne distingue pas « Markdown resté dans un champ texte » de « fichier Markdown ». |

Conséquence : sur un fichier `.md`, la règle « deux `weak` » revient à « un seul U+200B ».

Contrôles négatifs réussis : typographie française, emoji ZWJ, BOM initial, CSV, JSON, HTML simple, 10 Mo de prose. [O]

## Performance

| Entrée | Taille | Temps | RSS max |
|---|---|---|---|
| texte court | 1,3 Ko | < 0,01 s | 8,4 Mo |
| prose | 10,5 Mo | 0,02 s | 21 Mo |
| MP4 BigBuckBunny | 64,7 Mo | 0,01 s | 14 Mo |
| PNG 1 M chunks vides | 12 Mo | 3,1 s | 111 Mo |
| PNG 300 000 `parameters` | 7,2 Mo | 3,3 s | 551 Mo |
| MP4 100 000 boîtes vides | 0,8 Mo | 28,5 s | 41 à 46 Mo |

c2pa-python 0.38.0 seul est lent sur les mêmes fichiers (34 s pour 50 000 boîtes MP4), ce qui désigne c2pa-rs pour les constats 1 et 9, sans le prouver pour la version 0.92.0. [S]

## Non testé, et pourquoi

- **Aucune sortie réelle de générateur** : pas de générateur d'image, d'audio ni de vidéo disponible. Les positifs sont écrits à la main d'après les formats publics.
- **Aucun fichier signé par un vrai produit ou appareil** : seul le certificat de test c2pa-rs a servi.
- **PDF et M4A signés** : c2pa-python 0.38.0 refuse de les signer.
- **Autres plateformes** : macOS arm64 seulement.
- **Absence d'appel réseau (critère 4)** : non vérifiée, faute de bac à sable réseau.
- **Fréquence réelle des faux positifs** : le balayage ne contient ni presse ni messages ; il sous-estime sans doute `self-disclosure` et `utm-ai`. [S]
