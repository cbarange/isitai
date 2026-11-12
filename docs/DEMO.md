# Reconstruit et publie la démonstration WebAssembly.

La démo vit dans un dépôt séparé, `cbarange/isitai.cbarange.com`, servi par Netlify sur
`isitai.cbarange.com`. Elle n'est pas construite par Netlify : le dépôt contient le module
WASM déjà compilé. Sans ce workflow, elle dérive silencieusement du code — c'est exactement
ce qui a failli arriver, et seule une vérification manuelle l'a évité.

## Ce qui déclenche une republication

Un push sur `main` qui touche `site/`, `bindings/wasm/`, `crates/` ou les fichiers Cargo.
Le workflow ne se déclenche pas pour une modification de documentation : reconstruire un
module de 6,6 Mo pour un fichier markdown serait du gaspillage.

`workflow_dispatch` permet de le lancer à la main après un changement d'environnement.

## Le secret nécessaire

| Secret | Portée | Pourquoi un jeton séparé |
|---|---|---|
| `DEMO_TOKEN` | `cbarange/isitai.cbarange.com`, Contents: Read and write | Le `GITHUB_TOKEN` d'un workflow ne peut écrire que dans **son** dépôt. Publier ailleurs demande un jeton dédié |

Création, une fois :

```bash
gh secret set DEMO_TOKEN --repo cbarange/isitai
```

Le jeton est un jeton fine-grained limité à ce seul dépôt, avec `Contents: Read and write`
et une expiration courte. Il ne doit rien pouvoir faire d'autre : s'il fuit, la perte est un
site de démonstration écrasé, pas un dépôt de code.

Sans ce secret, le workflow ne casse pas : il s'arrête sur un message explicite dans le
résumé du job. Un travail silencieusement ignoré est un travail qui disparaît.

## Ce que le workflow garantit

- **Idempotence** : si le module reconstruit est identique à celui du dépôt de démo, aucun
  commit n'est créé. Une republication sans changement ne produit pas de bruit.
- **Traçabilité** : le message de commit porte le SHA court du dépôt source, comme les
  commits précédents (`Update the demo to isitai 35d2579`).
- **Reproductibilité** : la version de `wasm-bindgen` est épinglée à celle qu'exige
  `bindings/wasm/Cargo.toml` (0.2.130). Une version décalée produit un module incompatible,
  pas une erreur de build : le binaire est téléchargé depuis la release officielle, pas
  installé par `cargo install`, pour que la version soit exacte et non résolue.

## Vérifier que la démo est à jour

```bash
curl -s https://isitai.cbarange.com/pkg/isitai_wasm_bg.wasm | sha256sum
git clone --depth 1 https://github.com/cbarange/isitai.cbarange.com && \
  sha256sum isitai.cbarange.com/pkg/isitai_wasm_bg.wasm
```

Les deux empreintes doivent être égales. Pour savoir si un rebuild est nécessaire, la
question n'est pas « le dépôt de démo est-il récent » mais « du code a-t-il changé depuis le
SHA inscrit dans son dernier commit » :

```bash
git log --oneline 35d2579..HEAD -- crates/ bindings/ Cargo.toml Cargo.lock
```

Aucune ligne = aucun rebuild nécessaire, même si le dépôt de démo semble ancien.
