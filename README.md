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
// ES module (.mjs, or "type": "module"); with CommonJS use require("isitai") inside an async function.
import { checkText, checkFile } from "isitai";

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

Options apply to the files that follow them. Exit code: `0` nothing found, `1` AI signal or proof, `2` error (unknown option, unreadable file, directory, unusable `--anchors` file, standard input over `--max-bytes`). Exit code `0` does not mean human-made.

### Trust anchors

`ai-proven` and `capture-proven` need a C2PA manifest whose signer chains to a trusted root. By default the trusted roots are three lists embedded in the library:

- the two official [C2PA trust lists](https://github.com/c2pa-org/conformance-public/tree/main/trust-list): one for manifest signers, one for time-stamp authorities;
- the [interim trust list](https://github.com/contentauth/verify-site/blob/main/static/trust/anchors.pem) of the Content Authenticity Initiative, which came before the official lists. It is used for signers and for time-stamp authorities. Real files from Adobe Firefly, Adobe Photoshop and OpenAI Sora chain to it and not to the official lists.

A time-stamp counts only when its authority chains to a trusted time-stamp root; it is what keeps a file proven after its signing certificate has expired. The lists are a snapshot (date and upstream commit in `crates/isitai-core/trust/SOURCE.md`): nothing is fetched at run time, and newer lists come with a newer release.

The evidence of a trusted manifest says which list the proof rests on, in its `detail` text: `(manifest trusted, signer in the interim trust list)` or `(manifest trusted, signer in the official C2PA trust list, time-stamp authority in the official C2PA trust list)`. The time-stamp part is present when the time-stamp was checked against a list (C2PA claim version 2). When isitai cannot establish the list, or when you give your own anchors, the text is `(manifest trusted)`. A trusted manifest that gives no evidence names no list.

A PEM bundle given with `--anchors`, `trustAnchorsPem` or `trust_anchors_pem` **replaces** every embedded list; it is not added to them. The bundle is used for signers and for time-stamps, so it must also hold the roots of the time-stamp authorities to trust. There is no option to trust nothing. A bundle without a usable certificate is an error: the CLI exits with code 2, Node throws an `Error`, Python raises `ValueError`. In Rust, call `isitai::validate_trust_anchors` once before checking files.

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

### Remote and streamed files

isitai downloads nothing itself: it has no HTTP, S3, FTP or SFTP client, and it never touches the network. You open the remote file with the client you already use, and you give isitai the stream. Credentials, proxies, retries and timeouts stay in your code, and a URL sent by a user never becomes a request made by this library.

| | Function | Input |
|---|---|---|
| Node.js | `await checkStream(readable, { maxBytes })` | a `Readable`, a web `ReadableStream`, any async iterable of `Buffer` or `Uint8Array` |
| Python | `check_stream(fileobj, max_bytes=...)` | any binary object with `read(size)` |
| Rust | `check_stream(reader, max_bytes, &opts, &rules)` | any `Read` |
| CLI | `isitai -` | standard input |

The stream is read whole into memory, then checked like a file: a signed file has to be read whole anyway, because C2PA validation hashes all of it and needs to move back and forth in it. Reading stops at the limit (`maxBytes`, `max_bytes`, `--max-bytes`; default 256 MiB, exported as `DEFAULT_MAX_STREAM_BYTES`), whatever size the source declares. A stream over the limit is an error (Node rejects with a `RangeError`, Python raises `ValueError`, the CLI exits with code 2): a cut file is never analysed, because its result would be wrong. Set the limit to the largest file your service accepts: the process holds a few times the size of the stream at the peak (measured on a 100 MB file, macOS arm64: about 220 MB for the CLI, 360 MB for Node, 430 MB for Python). For large files, download to a temporary file and use `checkFile` / `check_file`, which reads from disk without loading the file. In Node, `checkStream` collects the chunks asynchronously, then runs the check on the event loop, like `check`.

HTTP, Node.js 18 or later:

```js
import { checkStream } from "isitai";

const res = await fetch("https://example.com/photo.jpg");
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const report = await checkStream(res.body, { maxBytes: 50 * 1024 * 1024 });
```

HTTP, Python:

```python
import urllib.request
from isitai import check_stream

with urllib.request.urlopen("https://example.com/photo.jpg", timeout=30) as res:
    report = check_stream(res, max_bytes=50 * 1024 * 1024)
```

With `requests` (not tested): pass `stream=True`, set `response.raw.decode_content = True` so that a compressed response is decompressed, and give `response.raw`.

S3, Node.js (AWS SDK v3):

```js
import { S3Client, GetObjectCommand } from "@aws-sdk/client-s3";
import { checkStream } from "isitai";

const { Body } = await new S3Client({}).send(new GetObjectCommand({ Bucket: "my-bucket", Key: "photo.jpg" }));
const report = await checkStream(Body);
```

S3, Python (boto3):

```python
import boto3
from isitai import check_stream

body = boto3.client("s3").get_object(Bucket="my-bucket", Key="photo.jpg")["Body"]
report = check_stream(body)
```

SFTP and FTP follow the same pattern: open the remote file with your client, pass the stream. With [paramiko](https://www.paramiko.org/) (example not tested):

```python
import paramiko
from isitai import check_stream

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()
ssh.connect("files.example.com", username="me")
with ssh.open_sftp().open("/uploads/photo.jpg", "rb") as remote:
    report = check_stream(remote)
```

CLI, from any command that writes the file to standard output:

```bash
curl -sf https://example.com/photo.jpg | isitai -
aws s3 cp s3://my-bucket/photo.jpg - | isitai --max-bytes 50000000 -
```

In a shell script, set `set -o pipefail`: when the download fails, isitai receives an empty or cut input and still prints a report (`no-signal` with exit code 0 for an empty input). Standard input has no file name, so the CLI does not compare an extension with the content there.

### Browser / WebAssembly

The core also runs in a browser, with no server. `bindings/wasm` compiles it to `wasm32-unknown-unknown` and exposes `check_text_json(text)` and `check_bytes_json(bytes, effort?, trust_anchors_pem?)`, which return the same JSON as the other bindings (there is no file-path function). The demo page ([isitai.cbarange.com](https://isitai.cbarange.com)) uses it: the file is read and checked inside the page and is never uploaded. The page lives in its own repository, [`cbarange/isitai.cbarange.com`](https://github.com/cbarange/isitai.cbarange.com); this repository only produces the WebAssembly module.

```sh
rustup target add wasm32-unknown-unknown
cargo install wasm-bindgen-cli --version 0.2.130 --locked
site/build.sh                           # writes site/pkg/ (about 6.5 MB, 2.3 MB gzipped)
# then copy site/pkg/ into the demo repository, or let the Demo workflow do it
```

The page uses relative paths only, so it can be hosted at a domain root or under a sub-path. It needs http(s): opened from disk (`file://`), a browser refuses to load the WebAssembly module and the page says so. It reads a file whole into memory and refuses files over 256 MB; a check runs on the main thread.

## What it reads

- **C2PA Content Credentials** (via `c2pa-rs`): JPEG, PNG, WebP, AVIF, HEIC, GIF, TIFF, SVG, MP4, MOV, MP3, WAV, PDF. No network access, ever.
- **IPTC `DigitalSourceType`** in XMP metadata, in any format.
- **PNG text chunks** written by local generators (Stable Diffusion WebUI, ComfyUI, InvokeAI, NovelAI). The keyword alone is not enough: the value must look like the generator's output. Compressed text chunks are not read.
- **Text artifacts** left by copy-paste from AI assistants, in text input and inside text-like files (plain text, HTML, XML, SVG, shell scripts), up to 16 MiB. A warning says when text was not analysed, or not fully.

Text files are read as UTF-8 (with or without a byte order mark), as UTF-16 LE or BE when they start with a byte order mark, and otherwise as Windows-1252 (which covers Latin-1), but only when the content is clearly text: no NUL byte and no control byte other than tab, line feed, carriage return and form feed in the first 8 KiB. A warning names the encoding when it is not UTF-8: `text decoded as UTF-16LE`, `text decoded as UTF-16BE`, `text decoded as Windows-1252`. Anything else is not read as text and gives the warning `text not analysed: the content is not UTF-8`.

Text spans in `evidence[].location` are UTF-8 byte offsets; use `location.text` instead of slicing your string. For a UTF-16 or Windows-1252 file, they are offsets in the decoded text, not in the file; the UTF-16 byte order mark is not part of the decoded text.

## Known limits

- **Metadata can be stripped.** A screenshot, a re-upload to most platforms or a re-save removes C2PA and XMP. The result is then `no-signal`.
- **A document that quotes an artifact is flagged.** A bug report or a guide that contains `:contentReference[oaicite:0]` gets `ai-signal`, like this README. The text rules cannot tell a quote from a paste.
- **Unsigned metadata is a claim, not a proof.** Anyone can write or remove an XMP field or a PNG chunk.
- **The interim trust list is frozen, and wider than the C2PA conformance programme.** The Content Authenticity Initiative accepted its roots before the official lists existed: being on it does not mean that a product passed the C2PA conformance programme. A proof that rests on it says so in its evidence (`signer in the interim trust list`). Upstream no longer adds roots to it, and it has no removal process that isitai can follow: a root stays trusted until a release of isitai drops it. To trust the official lists only, give one PEM bundle that holds both official lists with `--anchors` / `trust_anchors_pem`.
- **Revocation is not checked.** isitai never contacts a certificate authority, so a certificate revoked after signing stays trusted unless the file carries the revocation response. Example reported by the press: Nikon revoked its C2PA certificates in 2025 after a camera flaw; its root is in the interim list.
- **The interim list also trusts non-production signers.** Adobe staging certificates ("Content Credentials (Stage)") chain to it. A file signed by such a certificate that declares an AI or capture source would get a proof verdict.
- **The default trust lists do not cover every signed file.** A valid manifest whose signer is in none of the three lists gives `ai-signal` at most, or `no-signal`, where a proof could be expected.
- **Ingredients are not verified.** An AI source type found only in an ingredient manifest gives `ai-signal` at most, never `ai-proven`.
- **A leaked signing key defeats any trust list.** Whoever holds the private key of a certificate that chains to a trusted root can sign anything. For old manifests (C2PA claim version 1) certificate expiry does not limit this, because the time-stamp authority is not checked there.
- **With `--anchors` / `trust_anchors_pem`, every root in your bundle is trusted for signers and for time-stamps.**
- **A capture declared only by an ingredient is not a proof.** A photo re-saved by a trusted tool (for example a Google Pixel photo processed by Google Photos) gives `no-signal`: ingredient manifests are not verified.
- **Not read yet:** compressed PNG text chunks, XMP sidecar files, UTF-16 text without a byte order mark, UTF-32.
- **The encoding of old text files is assumed, not detected.** Text that is neither UTF-8 nor UTF-16 is read as Windows-1252. A file in another 8-bit encoding (Latin-2, Cyrillic, Shift JIS) is still searched for the ASCII artifacts, but rules with accented letters cannot match it. A very short binary file without control bytes can be reported as `text/plain`.
- **Slow input:** an MP4 with about 100 000 empty boxes takes about 25 s (time spent in the C2PA parser). Set a timeout when you check untrusted uploads.

See `docs/qa/REPORT.md` for the test corpus and the open findings.

## License

MIT

The embedded files `crates/isitai-core/trust/C2PA-TRUST-LIST.pem` and `crates/isitai-core/trust/C2PA-TSA-TRUST-LIST.pem` are the "C2PA Trust List" and the "C2PA TSA Trust List" by the Coalition for Content Provenance and Authenticity (C2PA), copied unmodified from [c2pa-org/conformance-public](https://github.com/c2pa-org/conformance-public) and licensed under [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/).

The embedded file `crates/isitai-core/trust/C2PA-INTERIM-TRUST-LIST.pem` is the interim trust list of the Content Authenticity Initiative, copied unmodified from `static/trust/anchors.pem` in [contentauth/verify-site](https://github.com/contentauth/verify-site). The file itself carries no licence or copyright notice. Its repository is distributed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0) according to its README and its `LICENSE-APACHE` file ("Copyright 2020 Adobe"). The list holds public root certificates of third parties. Details are in `crates/isitai-core/trust/SOURCE.md`.
