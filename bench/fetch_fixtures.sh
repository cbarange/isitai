#!/usr/bin/env bash
# Downloads the c2pa-rs test fixtures and test certificates used by the benches.
# They stay outside the repo (license not checked yet). Usage: bench/fetch_fixtures.sh <dest-dir>
set -euo pipefail
DEST="$1"; mkdir -p "$DEST/fixtures" "$DEST/certs"
BASE="https://raw.githubusercontent.com/contentauth/c2pa-rs/main/sdk/tests/fixtures"
gh api "repos/contentauth/c2pa-rs/git/trees/HEAD?recursive=1" --jq '.tree[].path' \
  | grep -E '^sdk/tests/fixtures/[^/]+\.(jpg|png|webp|avif|heic|mp4|mov|wav|mp3|m4a|pdf|svg|gif|tif|dng)$' \
  | while read -r p; do curl -sfL -o "$DEST/fixtures/$(basename "$p")" "https://raw.githubusercontent.com/contentauth/c2pa-rs/main/$p"; done
curl -sfL -o "$DEST/fixtures/test_cert_root_bundle.pem" "$BASE/certs/trust/test_cert_root_bundle.pem"
for f in README.md es256.pem es256.pub; do curl -sfL -o "$DEST/certs/$f" "$BASE/certs/$f"; done
echo "fixtures: $(ls "$DEST/fixtures" | wc -l | tr -d ' ') files"
