# Benchmarks

All numbers come from a single machine: macOS arm64, Rust 1.99.1, `c2pa` 0.92.0 (`rust_native_crypto`, no OpenSSL, no HTTP). Re-run before quoting them elsewhere.

## 1. Binary size per feature (criterion 7: under 10 MB)

`isitai` CLI, profile `size` (`opt-level="z"`, `lto`, `strip`, `panic="abort"`).

| Features | Binary | gzip |
|---|---|---|
| none | 5.11 MB | 2.70 MB |
| `pdf` (default) | 5.59 MB | 2.96 MB |
| `c2pa-text` (`unstable_plain_text` + `unstable_structured_text`) | 5.24 MB | 2.77 MB |
| `pdf` + `c2pa-text` | 5.60 MB | 2.97 MB |

Re-measured with `bench/size_builds.sh` after the streaming API (+0.02 MB). Note: the CLI must depend on `isitai` (the core crate) with `default-features = false`, otherwise `--no-default-features` silently keeps `pdf`.

Decisions:
- `pdf` costs +0.5 MB, so it is on by default.
- `c2pa-text` costs +0.13 MB, but its upstream API is unstable, so it stays opt-in.
- The `release` profile (`opt-level=3`) gives 8.5 MB. Before publishing, compare its speed with `size`: if the difference is not measurable, ship `size`.

## 2. c2pa-rs fixtures (67 files, 20 formats)

Commands: `bench/fetch_fixtures.sh <dir>` then `python3 -I bench/run_fixtures.py <isitai-binary> <dir>/fixtures <dir>/fixtures/test_cert_root_bundle.pem`. Each file is run once without trust anchors and once with the c2pa-rs test root bundle.

Results:
- **No crash, no hang** on the hostile files:
  - `riff_bomb_1000.wav`: handled.
  - `nested_moov_1000.mp4`: clean error "Boxes are too deeply nested".
  - `sample3.invalid.wav`: clean error.
  - `id3v23_compression_underflow.mp3`: handled.
- **Trust works**: without anchors, signed fixtures produce the warning "valid but signer not in trust list". With the test anchors, most become trusted.
- `ocsp.jpg` declares `compositeWithTrainedAlgorithmicMedia` and gives `ai-signal`. Its signer is not covered by the test bundle, so it is not `ai-proven`.
- `C_with_CAWG_data.jpg` declares `digitalCapture` from an untrusted signer. That evidence is `strong`, not `proof`, so the verdict stays `no-signal`, as the spec requires.
- `cloud.jpg` and `libpng-test_with_url.png` point to a remote manifest. Because `remote_manifest_fetch=false`, no network call is made, and the CLI reports a warning instead.
- PDF fixtures gave `no-signal` in this run because `pdf` was not enabled yet. To re-run.
- **Time**: under 10 ms per file once the OS file cache is warm; the 64.7 MB MP4 takes 0.36 s on a cold read.
- **Memory: peak RSS follows file size** (64.7 MB MP4 gives 71 MB RSS; 35.8 MB DNG gives 42 MB). The CLI reads the whole file into memory.

## 3. Streaming API (`check_reader`)

The CLI now opens files as streams (`BufReader<File>`). XMP is scanned in 4 MB windows with a 256 KB overlap, and PNG chunks are walked with seeks.

| File | Peak RSS before | Peak RSS after |
|---|---|---|
| `BigBuckBunny_320x180.mp4` (64.7 MB) | 71 MB | 14 MB |
| `Foo.dng` (35.8 MB) | 42 MB | 14 MB |
| `subfiles.dng` (17.0 MB) | 23 MB | 14 MB |

`exp-test1.png` (5.9 MB) still reaches 38 MB: memory is used inside `c2pa-rs` for that PNG. Not investigated.

With `pdf` on, `express-signed.pdf` (Adobe Express) gives `ai-signal`: `compositeWithTrainedAlgorithmicMedia`, from a valid but untrusted signer. No other verdict changed.

## 4. Comparison: isitai (Rust core) vs c2pa-python vs @trustnxt/c2pa-ts

Command: `bench/compare/run.sh <fixtures> <venv/bin> <node-dir>`. Same files, 50 iterations (5 for the large MP4), in-process timing, network off everywhere.

Versions: `c2pa-python` 0.38.2 (bundles c2pa-rs 0.91.6), `@trustnxt/c2pa-ts` 0.14.1, Node 24.15, Python 3.15.

The work per call is not identical:
- isitai runs the full check: C2PA, plus the XMP scan of the whole file, plus PNG chunks.
- c2pa-python reads and validates C2PA with trust verification on.
- c2pa-ts reads and validates C2PA, but has no chain-of-trust validation (README).

Median time per call (ms):

| File | isitai | c2pa-python | c2pa-ts |
|---|---|---|---|
| CA.jpg (signed) | 1.82 | 1.69 | 9.85 |
| C.jpg (signed) | 1.51 | 1.60 | 7.89 |
| ocsp.jpg (signed) | 3.33 | 3.34 | 6.79 |
| no_manifest.jpg | 0.07 | 0.12 | 0.06 |
| sample1.png | 0.21 | 0.36 | 0.11 |
| sample1.heic | 0.22 | 0.14 | 0.42 |
| sample1.mp3 | 0.11 | 0.07 | 0.31 |
| video1.mp4 (signed) | 2.63 | 3.19 | 7.11 |
| BigBuckBunny 64.7 MB (no manifest) | 4.85 | 0.44 | 10.52 |

Process-level figures:

| | isitai | c2pa-python | c2pa-ts |
|---|---|---|---|
| Startup (import / rules init) | 1 ms | 43 ms | 148 ms |
| Peak RSS, small files | 19 MB | 37 MB | 340 MB |
| Peak RSS, 64.7 MB MP4 | 14 MB | 29 MB | 278 MB |
| Native library size | 5.1–5.6 MB (single arch) | 41 MB (universal2 x86_64 + arm64) | none (pure TS, 1.5 MB + deps) |

Findings:
- **Speed is the same as c2pa-python** on signed files, since both run c2pa-rs. As predicted, Rust alone does not make v0.1 faster than a binding of the same engine.
- **Against pure TypeScript**: about 2 to 5 times faster on signed files, 18 to 20 times less memory, and a startup about 150 times shorter.
- **The verdicts differ: c2pa-ts says `invalid` for `ocsp.jpg` and `video1.mp4`, while c2pa-rs says `Valid`.** The cause, printed by `bench/compare/why_invalid.mjs`, is the same for both: `assertion.action.ingredientMismatch (c2pa.opened action is missing ingredients)`. c2pa-ts applies this structural rule strictly; c2pa-rs does not fail on it. The cryptography is not the issue. Two validators still give different answers on the same file, which confirms the reason for criterion 5 (one core for all languages).
- isitai is slower on the 64.7 MB MP4 (4.85 ms vs 0.44 ms) because it also scans the whole file for XMP; c2pa-python stops as soon as no manifest is found. Possible optimisation: look for XMP only in the containers where it can be (MP4 `uuid`/`moov`), not across the whole file.

## 5. Signed corpus: does each format really reach `ai-proven`?

The c2pa-rs fixtures alone did not prove it: most of them carry no manifest, and an unknown MIME name used to look exactly like "no manifest". So:
- `UnsupportedType` from c2pa is now reported as a warning, never silently as "no manifest".
- `bench/corpus/make_signed.py` signs one file per format with the c2pa-rs **test** ES256 certificate (no timestamp authority, so no network). Each manifest has a `c2pa.created` action with a known `digitalSourceType`.

Result with `isitai --anchors test_cert_root_bundle.pem`:

| Format | Without anchors | With test anchors |
|---|---|---|
| JPEG (AI) | ai-signal | **ai-proven** |
| JPEG (`digitalCapture`) | no-signal | **capture-proven** |
| PNG, WebP, AVIF, HEIC, GIF, TIFF | ai-signal | **ai-proven** |
| MP4, MOV | ai-signal | **ai-proven** |
| MP3, WAV | ai-signal | **ai-proven** |
| PDF | ai-signal | **ai-proven** |
| SVG | ai-signal | **ai-proven**, after the fix below |
| M4A | — | not tested: c2pa-python refuses to sign it ("type is unsupported") |

Fix found by this test: `infer` reports SVG as `text/xml`, which c2pa-rs rejects. MIME names are now normalised before calling c2pa: SVG to `image/svg+xml`, `audio/x-wav` to `audio/wav`, `audio/m4a` to `audio/mp4`.

Without trust anchors, no file ever reaches `ai-proven`: a valid signature from an unknown signer stays a signal, as the spec requires.

## To do (next benches)

1. `criterion` bench of the text rules: `RegexSet` vs `aho-corasick` (low priority: text already takes well under 1 ms).
2. XMP scan per container to remove the full read on large videos.
3. Repeat these benches on Linux x64 and in CI.
