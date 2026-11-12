# isitai

Local, offline check for **proof** or **signals** that a text, image, audio, video or PDF file was made by AI.

> Pre-alpha. The API may change.

isitai does not guess. It reads what the file says about itself and reports the evidence:

| Verdict | Meaning |
|---|---|
| `ai-proven` | A valid C2PA manifest, signed by a trusted certificate, declares AI generation. Weaker evidence of a capture does not cancel it. |
| `capture-proven` | A valid C2PA manifest, signed by a trusted certificate, declares a camera capture, and nothing points to AI. |
| `ai-signal` | Unsigned metadata, an untrusted C2PA manifest, or AI copy-paste artifacts in text. |
| `inconsistent` | The evidence contradicts itself: AI and capture evidence without a proof, a proven capture with any AI hint, or two proofs. |
| `no-signal` | Nothing found. **This does not mean "human"**: most platforms strip metadata. |

## Install

```bash
npm i isitai@next
```

```bash
pip install --pre isitai
```

## Use

Node.js:

```js
const { checkText, checkFile } = require("isitai");

checkText("Paris is big :contentReference[oaicite:0]{index=0}").verdict; // "ai-signal"
(await checkFile("photo.jpg")).verdict;
```

Python:

```python
from isitai import check_text, check_file

check_text("Paris is big :contentReference[oaicite:0]{index=0}")["verdict"]  # "ai-signal"
check_file("photo.jpg")["verdict"]
```

CLI:

```bash
isitai photo.jpg essay.txt
isitai --anchors roots.pem photo.jpg
```

Options apply to the files that follow them. Exit code: `0` nothing found, `1` AI signal or proof, `2` error (unknown option, unreadable file, directory, unusable `--anchors` file). Exit code `0` does not mean human-made.

### Trust anchors

`ai-proven` and `capture-proven` need a C2PA manifest whose signer chains to a trusted root. By default the trusted roots are the official [C2PA trust list](https://github.com/c2pa-org/conformance-public/tree/main/trust-list), embedded in the library. It is a snapshot (date and upstream commit in `crates/isitai-core/trust/SOURCE.md`): nothing is fetched at run time, and a newer list comes with a newer release.

A PEM bundle given with `--anchors`, `trustAnchorsPem` or `trust_anchors_pem` **replaces** the embedded list; it is not added to it. There is no option to trust nothing. A bundle without a usable certificate is an error: the CLI exits with code 2, Node throws an `Error`, Python raises `ValueError`. In Rust, call `isitai::validate_trust_anchors` once before checking files.

### Effort

File checks take an effort level. Text ignores it.

| Level | Work |
|---|---|
| `standard` (default) | Every layer. |
| `fast` | `fast` skips the XMP scan of the whole file; C2PA validation may still read a signed file whole; `fast` can miss unsigned metadata, including a contradiction that `standard` would report. |

```js
await checkFile("video.mp4", { effort: "fast" });
```

```python
check_file("video.mp4", effort="fast")
```

```bash
isitai --effort fast video.mp4
```

An unknown level is an error (exit code 2 for the CLI).

### Edit history

When a file carries a C2PA manifest, the report lists the actions of its active manifest in order, and says what they establish:

```json
{
  "verdict": "ai-signal",
  "history": [
    { "action": "c2pa.opened", "digital_source_type": "compositeWithTrainedAlgorithmicMedia" },
    { "action": "c2pa.cropped" },
    { "action": "c2pa.edited", "digital_source_type": "compositeWithTrainedAlgorithmicMedia", "software": "Adobe Firefly" }
  ],
  "history_summary": "ai-then-edited"
}
```

- `history` is absent when there is no manifest or no action. It lists at most 64 actions, with a warning when the manifest holds more. `digital_source_type` is the one the action declares or, failing that, the one declared by the manifest of the ingredient the action opened or placed: the type of that ingredient's first action only.
- `history_summary` is `ai-then-edited` (declared AI-made, then modified) or `capture-then-ai-edited` (declared a camera capture, then an edit declares an AI source). It is absent when the chain does not establish either, and always absent for a manifest that fails validation.
- The history is what the manifest declares, and the report does not state how far to trust it. It adds no evidence and does not change the verdict.
- The evidence reads the same chain. A source type declared by the active manifest is as strong as its signature (`proof` when trusted). A source type inherited from an ingredient is at most `strong`, because the trust of an ingredient manifest is not verified: a trusted AI image opened and cropped in another tool gives `ai-signal` with `ai-then-edited`, not `ai-proven`.
- A capture followed by an AI edit is AI-edited content, not a contradiction: when the chain declares an AI source, the manifest gives no capture evidence.
- A manifest that fails validation gives a warning and no `generator`. It still lists its history.

### Browser / WebAssembly

The core also runs in a browser, with no server. `bindings/wasm` compiles it to `wasm32-unknown-unknown` and exposes `check_text_json(text)` and `check_bytes_json(bytes, effort?, trust_anchors_pem?)`, which return the same JSON as the other bindings (there is no file-path function). The demo page in `site/` uses it: the file is read and checked inside the page and is never uploaded.

```sh
rustup target add wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version 0.2.130 --locked
site/build.sh                           # writes site/pkg/ (about 6.5 MB, 2.3 MB gzipped)
python3 -m http.server -d site 8000     # then open http://localhost:8000/
```

`site/` is static and uses relative paths only, so it can be hosted at a domain root or under a sub-path. It needs http(s): opened from disk (`file://`), a browser refuses to load the WebAssembly module and the page says so. The page reads a file whole into memory and refuses files over 256 MB; a check runs on the main thread.

## What it reads

- **C2PA Content Credentials** (via `c2pa-rs`): JPEG, PNG, WebP, AVIF, HEIC, GIF, TIFF, SVG, MP4, MOV, MP3, WAV, PDF. No network access, ever.
- **IPTC `DigitalSourceType`** in XMP metadata, in any format.
- **PNG text chunks** written by local generators (Stable Diffusion WebUI, ComfyUI, InvokeAI, NovelAI). The keyword alone is not enough: the value must look like the generator's output. Compressed text chunks are not read.
- **Text artifacts** left by copy-paste from AI assistants, in text input and inside text-like files (plain text, HTML, XML, SVG, shell scripts), up to 16 MiB of UTF-8. A warning says when text was not analysed, or not fully.

Text spans in `evidence[].location` are UTF-8 byte offsets; use `location.text` instead of slicing your string.

## Known limits

- **Metadata can be stripped.** A screenshot, a re-upload to most platforms or a re-save removes C2PA and XMP. The result is then `no-signal`.
- **A document that quotes an artifact is flagged.** A bug report or a guide that contains `:contentReference[oaicite:0]` gets `ai-signal`, like this README. The text rules cannot tell a quote from a paste.
- **Unsigned metadata is a claim, not a proof.** Anyone can write or remove an XMP field or a PNG chunk.
- **The default trust list does not cover every signed file.** Two cases give `ai-signal` at most, or `no-signal`, where a proof could be expected. First, a signer that is only in the older "interim" list used by contentcredentials.org (seen on Adobe Firefly and Photoshop files from 2025) is not in the official list. Second, the C2PA time-stamp authority list is not embedded yet, so a C2PA 2.x manifest whose proof depends on its time-stamp (for example once a signing certificate has expired) cannot be proven.
- **Ingredients are not verified.** An AI source type found only in an ingredient manifest gives `ai-signal` at most, never `ai-proven`.
- **Not read yet:** compressed PNG text chunks, UTF-16 or Latin-1 text, XMP sidecar files.
- **Slow input:** an MP4 with about 100 000 empty boxes takes about 25 s (time spent in the C2PA parser). Set a timeout when you check untrusted uploads.

See `docs/qa/REPORT.md` for the test corpus and the open findings.

## License

MIT

The embedded file `crates/isitai-core/trust/C2PA-TRUST-LIST.pem` is the "C2PA Trust List" by the Coalition for Content Provenance and Authenticity (C2PA), copied unmodified from [c2pa-org/conformance-public](https://github.com/c2pa-org/conformance-public) and licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).
