#!/usr/bin/env bash
# Runs the three C2PA readers on the same files with the same protocol.
# Usage: bench/compare/run.sh <fixtures-dir> <python-venv-bin> <node-project-dir>
# The node project dir must contain @trustnxt/c2pa-ts and reflect-metadata
# (npm i --ignore-scripts @trustnxt/c2pa-ts reflect-metadata).
set -euo pipefail
F="$1"; PY="$2"; JS="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SMALL=("$F/CA.jpg" "$F/C.jpg" "$F/ocsp.jpg" "$F/no_manifest.jpg" "$F/sample1.png" "$F/sample1.heic" "$F/sample1.mp3" "$F/video1.mp4")
BIG=("$F/BigBuckBunny_320x180.mp4")

(cd "$ROOT" && cargo build -q --release --example bench_files)
EX="${CARGO_TARGET_DIR:-$ROOT/target}/release/examples/bench_files"
cp "$HERE/bench_c2pa_ts.mjs" "$JS/"

rss() { grep -E '^\{|_ms=|maximum resident' | sed -E 's/^ +([0-9]+) +maximum resident set size/rss_bytes=\1/'; }

echo "## isitai (Rust core, full check)"
/usr/bin/time -l "$EX" 50 "${SMALL[@]}" 2>&1 | rss
/usr/bin/time -l "$EX" 5 "${BIG[@]}" 2>&1 | rss
echo "## c2pa-python"
/usr/bin/time -l "$PY/python" -I "$HERE/bench_c2pa_python.py" 50 "${SMALL[@]}" 2>&1 | rss
/usr/bin/time -l "$PY/python" -I "$HERE/bench_c2pa_python.py" 5 "${BIG[@]}" 2>&1 | rss
echo "## @trustnxt/c2pa-ts"
(cd "$JS" && /usr/bin/time -l node bench_c2pa_ts.mjs 50 "${SMALL[@]}" 2>&1 | rss)
(cd "$JS" && /usr/bin/time -l node bench_c2pa_ts.mjs 5 "${BIG[@]}" 2>&1 | rss)
