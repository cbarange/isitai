#!/usr/bin/env bash
# Refreshes the vendored C2PA trust lists (crates/isitai-core/trust/) from the official
# repository and rewrites SOURCE.md. Prints the certificates added and removed.
# Needs `gh` (read access to public repos). Run from anywhere. Review the diff before committing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/crates/isitai-core/trust"
REPO="c2pa-org/conformance-public"
BEGIN="-----BEGIN CERTIFICATE-----"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
SOURCE="$TMP/SOURCE.md"
# Upstream writes one `Subject` line before each certificate.
subjects() { if [ -f "$1" ]; then grep '^Subject' "$1" | sort; fi; }

# refresh NAME: fetches trust-list/NAME, replaces the vendored copy when it differs
# and appends the origin of the file to the new SOURCE.md.
refresh() {
  local name="$1" file="trust-list/$1" pem="$DIR/$1" new="$TMP/$1"
  local commit sha commit_date count
  # Last upstream commit that changed the file: the vendored copy is pinned to it.
  commit="$(gh api -X GET "repos/$REPO/commits" -f path="$file" -f per_page=1 \
    --jq '.[0] | "\(.sha) \(.commit.committer.date)"')"
  sha="${commit%% *}"
  commit_date="${commit##* }"
  gh api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/$file?ref=$sha" > "$new"

  count="$(grep -c -e "$BEGIN" "$new" || true)"
  if [ "$count" -eq 0 ]; then
    echo "error: no certificate in $REPO/$file at $sha" >&2
    exit 1
  fi

  if [ -f "$pem" ] && cmp -s "$new" "$pem"; then
    echo "$name unchanged: $count certificates, upstream commit $sha ($commit_date)"
  else
    echo "$name removed:"
    comm -23 <(subjects "$pem") <(subjects "$new") | sed 's/^Subject[[:space:]]*/  - /'
    echo "$name added:"
    comm -13 <(subjects "$pem") <(subjects "$new") | sed 's/^Subject[[:space:]]*/  + /'
    cp "$new" "$pem"
    echo "$name updated: $count certificates, upstream commit $sha ($commit_date)"
  fi

  cat >> "$SOURCE" <<EOF

## \`$name\`

| | |
|---|---|
| Upstream repository | https://github.com/$REPO |
| Path | \`$file\` |
| Commit | \`$sha\` ($commit_date) |
| Certificates | $count |
| SHA-256 | \`$(shasum -a 256 "$pem" | cut -d' ' -f1)\` |
| Licence | CC-BY-4.0, https://creativecommons.org/licenses/by/4.0/ |
EOF
}

mkdir -p "$DIR"
cat > "$SOURCE" <<EOF
# C2PA trust lists

Unmodified copies of the official C2PA trust lists: \`C2PA-TRUST-LIST.pem\` holds the roots
of manifest signers, \`C2PA-TSA-TRUST-LIST.pem\` the roots of time-stamp authorities. Do not
edit them by hand: run \`scripts/update_trust_list.sh\`.

Fetched: $(date -u +%Y-%m-%d)
EOF
refresh C2PA-TRUST-LIST.pem
refresh C2PA-TSA-TRUST-LIST.pem
cat >> "$SOURCE" <<EOF

Attribution: "C2PA Trust List" and "C2PA TSA Trust List", by the Coalition for Content
Provenance and Authenticity (C2PA), from the repository above.
EOF

# SOURCE.md is rewritten when it no longer describes the files. An unchanged run
# leaves it alone, with the date of the last change.
described() { if [ -f "$1" ]; then grep -v '^Fetched:' "$1"; fi; }
if ! cmp -s <(described "$SOURCE") <(described "$DIR/SOURCE.md"); then
  cp "$SOURCE" "$DIR/SOURCE.md"
  echo "SOURCE.md rewritten"
fi
