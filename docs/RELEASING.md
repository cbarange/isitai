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
