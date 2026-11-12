# La démonstration WebAssembly

`isitai.cbarange.com` est servie par Netlify depuis le dépôt
[`cbarange/isitai.cbarange.com`](https://github.com/cbarange/isitai.cbarange.com), à chaque
push. Ce dépôt-ci ne produit qu'une chose pour elle : le module `pkg/`.

## Qui possède quoi

| Objet | Où il vit | Qui le modifie |
|---|---|---|
| `index.html`, `app.js`, `engine.js`, `strings.js`, `style.css` | dépôt de démonstration | à la main, là-bas |
| `pkg/isitai_wasm.js`, `pkg/isitai_wasm_bg.wasm` | dépôt de démonstration, produit ici | le workflow `Demo` |
| `site/build.sh` | ce dépôt | à la main |

Un fichier statique n'existe qu'à un seul endroit. Il a existé en double : les cinq fichiers
ci-dessus étaient aussi dans `site/`. Deux copies identiques divergent toujours, et la copie
qui gagne est celle que personne ne relit. Elles ont été retirées de ce dépôt.

## Le workflow

`.github/workflows/demo.yml` se déclenche sur un push vers `main` qui touche
`bindings/wasm/`, `crates/`, `Cargo.toml`, `Cargo.lock` ou `site/build.sh`, plus
`workflow_dispatch` pour un lancement manuel.

Il télécharge le binaire officiel de `wasm-bindgen` à la version exacte qu'exige
`bindings/wasm/Cargo.toml` (0.2.130) — pas `cargo install`, qui résoudrait la version —,
construit le module, puis pousse **uniquement `pkg/`** dans le dépôt de démonstration :

- **Ne jamais copier les fichiers statiques.** Le site appartient au dépôt de démonstration ;
  les écraser depuis ici annulerait une modification faite à la main.
- **Idempotent** : si le module reconstruit est identique, aucun commit n'est créé. Le dépôt de
  démonstration ne produit pas de bruit de déploiements inutiles.
- **Traçable** : le message de commit porte le SHA court de ce dépôt, comme les précédents
  (`Update the demo to isitai 35d2579`).

## Le secret nécessaire

| Secret | Portée | Pourquoi un jeton séparé |
|---|---|---|
| `DEMO_TOKEN` | `cbarange/isitai.cbarange.com`, Contents: Read and write | Le `GITHUB_TOKEN` d'un workflow ne peut écrire que dans son propre dépôt |

```bash
gh secret set DEMO_TOKEN --repo cbarange/isitai
```

Jeton fine-grained, limité à ce seul dépôt, expiration courte. S'il fuit, la perte est une
démonstration écrasée, pas du code source.

Sans ce secret, le job ne casse pas : il s'arrête sur un message dans le résumé du job. Un
travail silencieusement ignoré est un travail qui n'existe pas — mais un job rouge parce qu'un
secret optionnel manque est du bruit qui apprend à ignorer le rouge.

## Savoir si un rebuild est nécessaire

La mauvaise question est « le dépôt de démonstration est-il récent ». La bonne : **du code
a-t-il changé depuis le SHA inscrit dans son dernier commit ?**

```bash
git log --oneline 35d2579..HEAD -- crates/ bindings/ Cargo.toml Cargo.lock
```

Aucune ligne = aucun rebuild nécessaire, même si la démo semble ancienne. Une modification de
documentation ne change pas le module.

Vérifier que le site en ligne sert bien le dépôt :

```bash
curl -s https://isitai.cbarange.com/pkg/isitai_wasm_bg.wasm | sha256sum
git clone --depth 1 https://github.com/cbarange/isitai.cbarange.com && \
  sha256sum isitai.cbarange.com/pkg/isitai_wasm_bg.wasm
```

Les deux empreintes doivent être égales. Le 2026-11-12 elles l'étaient, et le module datait de
`35d2579` : la démo était à jour, mais rien ne garantissait qu'elle le reste — c'est ce que ce
workflow corrige.
