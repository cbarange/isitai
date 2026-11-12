#!/usr/bin/env bash
# Refreshes the vendored C2PA trust lists (crates/isitai-core/trust/) from their upstream
# repositories and rewrites SOURCE.md. Prints the certificates added and removed.
# Needs `gh` (read access to public repos) and `openssl`. Run from anywhere. Review the
# diff before committing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/crates/isitai-core/trust"
OFFICIAL="c2pa-org/conformance-public"
INTERIM="contentauth/verify-site"
CC_BY="CC-BY-4.0, https://creativecommons.org/licenses/by/4.0/"
BEGIN="-----BEGIN CERTIFICATE-----"
END="-----END CERTIFICATE-----"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
SOURCE="$TMP/SOURCE.md"
# Subject of every certificate of a PEM file, read from the certificates themselves:
# the lists do not label their certificates the same way.
subjects() {
  if [ -f "$1" ]; then
    openssl crl2pkcs7 -nocrl -certfile "$1" | openssl pkcs7 -print_certs -noout |
      sed -n 's/^subject=[[:space:]]*//p' | sort
  fi
}
# Number of different certificates in a PEM file.
different() {
  awk -v b="$BEGIN" -v e="$END" '$0 == b { c = ""; next } $0 == e { print c } { c = c $0 }' "$1" |
    sort -u | wc -l | tr -d ' '
}

# refresh NAME REPO FILE LICENCE: fetches FILE from the GitHub repository REPO, replaces
# the vendored copy NAME when it differs and appends the origin of the file to the new
# SOURCE.md.
refresh() {
  local name="$1" repo="$2" file="$3" licence="$4" pem="$DIR/$1" new="$TMP/$1"
  local commit sha commit_date count unique
  # Last upstream commit that changed the file: the vendored copy is pinned to it.
  commit="$(gh api -X GET "repos/$repo/commits" -f path="$file" -f per_page=1 \
    --jq '.[0] | "\(.sha) \(.commit.committer.date)"')"
  sha="${commit%% *}"
  commit_date="${commit##* }"
  gh api -H "Accept: application/vnd.github.raw" "repos/$repo/contents/$file?ref=$sha" > "$new"

  count="$(grep -c -e "$BEGIN" "$new" || true)"
  if [ "$count" -eq 0 ]; then
    echo "error: no certificate in $repo/$file at $sha" >&2
    exit 1
  fi
  # A list may hold the same certificate twice.
  unique="$(different "$new")"
  if [ "$unique" -ne "$count" ]; then
    count="$count PEM blocks, $unique different"
  fi

  if [ -f "$pem" ] && cmp -s "$new" "$pem"; then
    echo "$name unchanged: $count certificates, upstream commit $sha ($commit_date)"
  else
    echo "$name removed:"
    comm -23 <(subjects "$pem") <(subjects "$new") | sed 's/^/  - /'
    echo "$name added:"
    comm -13 <(subjects "$pem") <(subjects "$new") | sed 's/^/  + /'
    cp "$new" "$pem"
    echo "$name updated: $count certificates, upstream commit $sha ($commit_date)"
  fi

  cat >> "$SOURCE" <<EOF

## \`$name\`

| | |
|---|---|
| Upstream repository | https://github.com/$repo |
| Path | \`$file\` |
| Commit | \`$sha\` ($commit_date) |
| Certificates | $count |
| SHA-256 | \`$(shasum -a 256 "$pem" | cut -d' ' -f1)\` |
| Licence | $licence |
EOF
}

mkdir -p "$DIR"
cat > "$SOURCE" <<EOF
# C2PA trust lists

Unmodified copies of three trust lists. Two are the official C2PA trust lists:
\`C2PA-TRUST-LIST.pem\` holds the roots of manifest signers, \`C2PA-TSA-TRUST-LIST.pem\` the
roots of time-stamp authorities. \`C2PA-INTERIM-TRUST-LIST.pem\` is the interim trust list
that the Content Authenticity Initiative kept before the official lists existed: it holds
roots of manifest signers and of time-stamp authorities, and upstream has frozen it. Do
not edit them by hand: run \`scripts/update_trust_list.sh\`.

Fetched: $(date -u +%Y-%m-%d)
EOF
refresh C2PA-TRUST-LIST.pem "$OFFICIAL" trust-list/C2PA-TRUST-LIST.pem "$CC_BY"
refresh C2PA-TSA-TRUST-LIST.pem "$OFFICIAL" trust-list/C2PA-TSA-TRUST-LIST.pem "$CC_BY"
refresh C2PA-INTERIM-TRUST-LIST.pem "$INTERIM" static/trust/anchors.pem \
  "none stated for this file; see the note below"
cat >> "$SOURCE" <<EOF

Attribution: "C2PA Trust List" and "C2PA TSA Trust List", by the Coalition for Content
Provenance and Authenticity (C2PA), from \`$OFFICIAL\`.

The interim trust list comes from the verify site of the Content Authenticity Initiative
(\`$INTERIM\`). Its licence, as found on 2026-11-12: the file and its directory
carry no licence or copyright notice; the repository holds \`LICENSE-APACHE\`
("Copyright 2020 Adobe") and its README places the project under the Apache License 2.0
(https://www.apache.org/licenses/LICENSE-2.0), while its \`package.json\` says
\`"license": "UNLICENSED"\`. The list holds public root certificates of third parties.
EOF

# SOURCE.md is rewritten when it no longer describes the files. An unchanged run
# leaves it alone, with the date of the last change.
described() { if [ -f "$1" ]; then grep -v '^Fetched:' "$1"; fi; }
if ! cmp -s <(described "$SOURCE") <(described "$DIR/SOURCE.md"); then
  cp "$SOURCE" "$DIR/SOURCE.md"
  echo "SOURCE.md rewritten"
fi
