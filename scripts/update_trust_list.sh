#!/usr/bin/env bash
# Refreshes the vendored C2PA trust list (crates/isitai-core/trust/) from the official
# repository and rewrites SOURCE.md. Prints the certificates added and removed.
# Needs `gh` (read access to public repos). Run from anywhere. Review the diff before committing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIR="$ROOT/crates/isitai-core/trust"
REPO="c2pa-org/conformance-public"
FILE="trust-list/C2PA-TRUST-LIST.pem"
PEM="$DIR/C2PA-TRUST-LIST.pem"
BEGIN="-----BEGIN CERTIFICATE-----"

NEW="$(mktemp)"
trap 'rm -f "$NEW"' EXIT

# Last upstream commit that changed the file: the vendored copy is pinned to it.
COMMIT="$(gh api -X GET "repos/$REPO/commits" -f path="$FILE" -f per_page=1 \
  --jq '.[0] | "\(.sha) \(.commit.committer.date)"')"
SHA="${COMMIT%% *}"
COMMIT_DATE="${COMMIT##* }"
gh api -H "Accept: application/vnd.github.raw" "repos/$REPO/contents/$FILE?ref=$SHA" > "$NEW"

COUNT="$(grep -c -e "$BEGIN" "$NEW" || true)"
if [ "$COUNT" -eq 0 ]; then
  echo "error: no certificate in $REPO/$FILE at $SHA" >&2
  exit 1
fi

if [ -f "$PEM" ] && cmp -s "$NEW" "$PEM"; then
  echo "unchanged: $COUNT certificates, upstream commit $SHA ($COMMIT_DATE)"
  exit 0
fi

# Upstream writes one `Subject` line before each certificate.
subjects() { if [ -f "$1" ]; then grep '^Subject' "$1" | sort; fi; }
echo "removed:"
comm -23 <(subjects "$PEM") <(subjects "$NEW") | sed 's/^Subject[[:space:]]*/  - /'
echo "added:"
comm -13 <(subjects "$PEM") <(subjects "$NEW") | sed 's/^Subject[[:space:]]*/  + /'

mkdir -p "$DIR"
cp "$NEW" "$PEM"
cat > "$DIR/SOURCE.md" <<EOF
# C2PA trust list

\`C2PA-TRUST-LIST.pem\` is an unmodified copy of the official C2PA trust list. Do not edit
it by hand: run \`scripts/update_trust_list.sh\`.

| | |
|---|---|
| Upstream repository | https://github.com/$REPO |
| Path | \`$FILE\` |
| Commit | \`$SHA\` ($COMMIT_DATE) |
| Fetched | $(date -u +%Y-%m-%d) |
| Certificates | $COUNT |
| SHA-256 | \`$(shasum -a 256 "$PEM" | cut -d' ' -f1)\` |
| Licence | CC-BY-4.0, https://creativecommons.org/licenses/by/4.0/ |

Attribution: "C2PA Trust List", by the Coalition for Content Provenance and Authenticity
(C2PA), from the repository above.
EOF
echo "updated: $COUNT certificates, upstream commit $SHA ($COMMIT_DATE)"
