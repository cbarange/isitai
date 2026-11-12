# Releasing

Publishing runs in `.github/workflows/release.yml` when a `v*` tag is pushed. It uses **OIDC trusted publishing**: no registry token is stored in GitHub. Each registry trusts this repo, this workflow file and the `release` environment, and nothing else.

## One-time setup

### 1. GitHub environment `release`

The publish jobs run only after a manual approval, and only for `v*` tags. Create the environment once:

```bash
gh api -X PUT repos/cbarange/isitai/environments/release \
  -F "reviewers[][type]=User" -F "reviewers[][id]=$(gh api users/cbarange --jq .id)" \
  -F "deployment_branch_policy[protected_branches]=false" \
  -F "deployment_branch_policy[custom_branch_policies]=true"
```

```bash
gh api -X POST repos/cbarange/isitai/environments/release/deployment-branch-policies \
  -f name='v*' -f type=tag
```

### 2. Trusted publishers

Use these values on each registry: owner `cbarange`, repository `isitai`, workflow `release.yml`, environment `release`.

| Registry | Where | Packages |
|---|---|---|
| PyPI | pypi.org, project `isitai`, Manage, Publishing | `isitai` |
| crates.io | crates.io, crate `isitai`, Settings, Trusted Publishing | `isitai` |
| npm | npmjs.com, package settings, Trusted Publisher | `isitai`, then each `@cbarange/isitai-*` |

**npm bootstrap.** A trusted publisher can only be attached to a package that already exists, and the eight `@cbarange/isitai-*` platform packages do not exist yet. For the first release only:

1. Create a granular npm token, limited to publishing, that expires after one day.
2. Store it in the environment, not in the repository. `gh` prompts for the value, so it never appears in your shell history:
   ```bash
   gh secret set NPM_TOKEN --env release --repo cbarange/isitai
   ```
3. After the release, add the trusted publisher to each `@cbarange/isitai-*` package, then delete the secret and revoke the token:
   ```bash
   gh secret delete NPM_TOKEN --env release --repo cbarange/isitai
   ```

## Each release

1. Bump the version in `Cargo.toml` (`[workspace.package]`), `bindings/node/package.json` and `bindings/python/pyproject.toml` (PEP 440 form: `0.1.0-alpha.1` becomes `0.1.0a1`).
2. Run `python3 scripts/check_versions.py`.
3. Refresh the three embedded trust lists (official C2PA lists of manifest signers and of time-stamp authorities, interim list): run `scripts/update_trust_list.sh` (needs `gh` and `openssl`), read the added and removed certificates of each list, then run `cargo test -p isitai`. The interim list is frozen upstream: a change to it is unexpected, so read it with care. The lists are only read from the repository at build time; a release ships the snapshot it was built with.
4. Commit, then tag and push:
   ```bash
   git tag v0.1.0-alpha.1 && git push origin v0.1.0-alpha.1
   ```
5. Approve the `release` deployment in the Actions tab.

A version with a pre-release suffix (`-alpha.N`) goes to the npm dist-tag `next`, so `npm i isitai` keeps installing the last stable version.

## Security rules for this public repo

- No workflow uses `pull_request_target`. Fork pull requests run without secrets and with a read-only token.
- Only the publish jobs get `id-token: write`, and only inside the approved `release` environment.
- Every action is pinned by commit SHA. Dependabot proposes the updates.
- `.env`, `*.pem` and `.npmrc*` are git-ignored. Never commit a token, even in a test.

## Tokens: when they are needed, and which one

Trusted publishing (OIDC) is the default and needs no secret. Three cases still require a token,
and each has a dedicated secret in the `release` environment:

| Registre | Secret | Pourquoi un jeton reste nécessaire |
|---|---|---|
| crates.io | `CRATES_IO` | Un trusted publisher ne peut pas être attaché à un crate qui n'existe pas encore : le tout premier envoi se fait au jeton |
| npm | `NPM_TOKEN` | Même raison pour les paquets de plateforme `@cbarange/isitai-*`, qui doivent exister avant qu'un publisher y soit rattaché |
| PyPI | `PIPY` | Le projet doit exister avant l'attachement du trusted publisher |

Le workflow lit le secret s'il est présent et retombe sur OIDC sinon. Conséquences pratiques :

- **Le jeton l'emporte quand il est défini.** C'est voulu pour le premier envoi, mais cela veut
  dire qu'un secret oublié désactive la publication de confiance. Après le premier envoi réussi
  de chaque registre : supprimer le secret, rattacher le trusted publisher, et le workflow
  repasse seul sur OIDC.
- **Un jeton exposé doit être révoqué, pas remplacé discrètement.** Les quatre règles : révoquer
  sur le registre, supprimer le secret, publier une entrée `Sécurité` dans `CHANGELOG.md`,
  vérifier les publications inattendues depuis la date d'exposition.

```bash
gh secret set CRATES_IO --env release --repo cbarange/isitai   # valeur demandée par gh, jamais dans l'historique
gh secret set PIPY --env release --repo cbarange/isitai
gh secret list --env release --repo cbarange/isitai
```

Un jeton ne se colle ni dans un ticket, ni dans un fichier du dépôt, ni dans une conversation :
`gitleaks` tourne à chaque push et bloque l'ajout, mais il ne peut pas annuler une fuite déjà
lue par quelqu'un.

## Journal des versions

Une publication est irréversible : un numéro consommé ne se réutilise pas, un paquet publié
sans description de son contenu ne se répare pas. D'où deux contrôles bloquants, sur le tag :

1. `scripts/check_versions.py` — Cargo, npm et PyPI portent la même version, et le tag
   correspond.
2. `scripts/check_changelog.py` — `CHANGELOG.md` contient une section pour cette version, avec
   au moins un changement listé.

Le geste, à chaque release :

```bash
# 1. renommer la section « Non publié » en « [X.Y.Z] - AAAA-MM-JJ » et ouvrir une nouvelle section vide
# 2. aligner les trois fichiers de version, puis :
python3 scripts/check_versions.py && python3 scripts/check_changelog.py
git commit -am "release: vX.Y.Z" && git tag vX.Y.Z && git push origin main vX.Y.Z
```

## Budget de taille

Deux contrôles, avec la même logique : le paquet doit rester petit, et une régression de taille
est une régression tout court.

- **En CI, à chaque push** (`package-size`) : le crate, le tarball npm, la sdist et le wheel
  sont construits puis comparés à un budget. Le tableau est publié dans le résumé du job.
- **Sur le tag** (`size-gate`) : les artefacts réellement destinés à la publication sont
  contrôlés avant l'envoi. Un paquet hors budget arrête la release avant qu'elle ne devienne
  irréversible.

Budgets, ancrés sur la première mesure réelle (`v0.1.0-alpha.0`, ubuntu-24.04, 2026-11-12) :

| Paquet | Mesuré | Budget | Marge |
|---|---|---|---|
| crate | 118 Ko | 700 Ko | ×5,9 |
| npm (méta, sans binaire) | 3 Ko | 500 Ko | très large |
| sdist | 131 Ko | 900 Ko | ×6,9 |
| wheel | 4 967 Ko | 5 200 Ko | 5 % |

Le wheel est le seul paquet volumineux : il embarque `c2pa` et son implémentation crypto native.
Son budget est donc serré, et c'est voulu — c'est lui qui signalera l'ajout d'une dépendance
lourde. Les trois autres budgets sont larges parce qu'ils ne mesurent presque rien. Ils vivent dans les workflows, pas dans un
fichier partagé, parce qu'un budget de taille se lit à côté de ce qu'il mesure.

Ce qui réduit réellement la taille, dans cet ordre : `strip = true` et `lto = true` (déjà dans
`[profile.release]`), `panic = "abort"` dans le profil `size`, l'exclusion des fixtures et du
banc du paquet (`cargo package --list` pour vérifier), et le refus de toute dépendance qui
embarque un moteur d'inférence dans le paquet de base — les modèles vivent dans un paquet
optionnel, jamais dans le cœur.

## Ce que la CI vérifie, et pourquoi ces trois-là

| Job | Ce qu'il empêche |
|---|---|
| `hygiene` | Un secret ajouté au dépôt, une licence copyleft dans l'arbre de dépendances, un workflow YAML invalide |
| `package-size` | Un paquet qui double de volume sans que personne ne le remarque |
| `bindings-node-versions` / `bindings-python-versions` | Une API qui ne fonctionne que sur la version de Node ou de Python du développeur |

