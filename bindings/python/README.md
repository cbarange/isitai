# isitai

Local, offline check for **proof** or **signals** that a text, image, audio, video or PDF file was made by AI.

> Pre-alpha. The API may change.

isitai does not guess. It reads what the file says about itself and reports the evidence:

| Verdict | Meaning |
|---|---|
| `ai-proven` | A valid C2PA manifest, signed by a trusted certificate, declares AI generation. |
| `capture-proven` | A valid C2PA manifest, signed by a trusted certificate, declares a camera capture. |
| `ai-signal` | Unsigned metadata, an untrusted C2PA manifest, or AI copy-paste artifacts in text. |
| `inconsistent` | The evidence contradicts itself. |
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
```

## What it reads

- **C2PA Content Credentials** (via `c2pa-rs`): JPEG, PNG, WebP, AVIF, HEIC, GIF, TIFF, SVG, MP4, MOV, MP3, WAV, PDF. No network access, ever.
- **IPTC `DigitalSourceType`** in XMP metadata, in any format.
- **PNG text chunks** written by local generators (Stable Diffusion WebUI, ComfyUI, InvokeAI, NovelAI).
- **Text artifacts** left by copy-paste from AI assistants.

Text spans in `evidence[].location` are UTF-8 byte offsets; use `location.text` instead of slicing your string.

## License

MIT
