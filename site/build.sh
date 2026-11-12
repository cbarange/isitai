#!/usr/bin/env bash
# Builds the WebAssembly engine of the demo page into site/pkg/ (ignored by git).
# Run from anywhere. Needs:
#   rustup target add wasm32-unknown-unknown
#   cargo install wasm-bindgen-cli --version 0.2.130 --locked
# No wasm-opt pass: measured with binaryen 132, -Oz saves 6 % raw and nothing after gzip.
set -euo pipefail

# Must equal the `wasm-bindgen` version in bindings/wasm/Cargo.toml.
WASM_BINDGEN_VERSION="0.2.130"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/target}"
PKG="$ROOT/site/pkg"

found="$(wasm-bindgen --version 2>/dev/null || true)"
if [ "$found" != "wasm-bindgen $WASM_BINDGEN_VERSION" ]; then
  echo "need wasm-bindgen $WASM_BINDGEN_VERSION, found: ${found:-none}" >&2
  echo "install: cargo install wasm-bindgen-cli --version $WASM_BINDGEN_VERSION --locked" >&2
  exit 1
fi

cd "$ROOT"
# Profile `size` (opt-level z, LTO, panic=abort): the module is downloaded by every visitor.
# strip=debuginfo, not the profile's strip=true: wasm-bindgen needs the `target_features`
# section. It drops the name and producers sections itself (flags below), same final size.
CARGO_PROFILE_SIZE_STRIP=debuginfo \
  cargo build --locked -p isitai-wasm --profile size --target wasm32-unknown-unknown

rm -rf "$PKG"
wasm-bindgen --target web --no-typescript --remove-name-section --remove-producers-section \
  --out-dir "$PKG" \
  "$CARGO_TARGET_DIR/wasm32-unknown-unknown/size/isitai_wasm.wasm"

wasm="$PKG/isitai_wasm_bg.wasm"
echo "wasm=$(wc -c < "$wasm" | tr -d ' ') gz=$(gzip -9 -c "$wasm" | wc -c | tr -d ' ')"
