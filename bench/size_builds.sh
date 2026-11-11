#!/usr/bin/env bash
# Measures the CLI binary size for each feature set (criterion 7). Run from anywhere.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/target}"
cd "$ROOT"
for f in "" "pdf" "c2pa-text" "pdf,c2pa-text"; do
  # --no-default-features so that "none" really means no optional feature (pdf is a default).
  cargo build -q --profile size -p isitai-cli --no-default-features ${f:+--features "$f"}
  bin="$CARGO_TARGET_DIR/size/isitai"
  echo "features=[${f:-none}] bin=$(wc -c < "$bin" | tr -d ' ') gz=$(gzip -c "$bin" | wc -c | tr -d ' ')"
done
