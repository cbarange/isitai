# Full-tier spike: zero-shot text detectors outside Python — 2026-11-12

Question: can the "full" statistical tier (small language model, zero-shot) run in Rust, on
CPU, cross-platform, under about 500 MB, with the same scores as the Python benchmark?

Status: single machine (macOS arm64, 10 cores, 24 GB, CPU only), not independently
reviewed. **The machine was shared and at times heavily loaded (load average up to 60): all
timings are indicative.** Everything is measured here unless marked otherwise. Nothing under
`crates/`, `bindings/`, `docs/` was touched; models, builds and score files live in
`/tmp/isitai-deep`.

## 1. Answer

- **Feasible in Rust, with exact scores, in fp32.** `ort` 2.0.0-rc.15 (ONNX Runtime 1.31.1)
  reproduces the Python onnxruntime scores to 1e-13 and the benchmark's PyTorch scores to
  5e-5 (Binoculars) and 1e-3 (Fast-DetectGPT GPT-Neo). `rten` 0.28 (pure Rust) reproduces
  them to 4e-5, about twice as slow, and passes `cargo check` for `wasm32-unknown-unknown`.
- **int8 quantisation is rejected.** It changes the ranking (Spearman 0.85 to 0.97 against
  fp32), destroys detection on French and fiction at a fixed false-positive rate, and the
  int8 scores are not portable across runtimes: on the same int8 file `rten` and `ort`
  differ by 0.3 to 0.6 standard deviations of the score on average. A calibration table
  cannot be attached to such a score.
- **Recommended model: Fast-DetectGPT with GPT-Neo-125M (MIT), fp32, one model.** Same
  accuracy class as the Binoculars pair, lower false-positive rate off-distribution (1 to
  3 % against 1 to 12 %), half the size, twice the speed. SmolLM2-135M alone as a
  Fast-DetectGPT model is not good enough (4 of 10 French Wikipedia texts flagged).
- **Size.** Download about 210 MB (model zstd 199 MB + ONNX Runtime 9 MB gzip + binary);
  on disk about 590 MB with fp32 weights. Within the budget as a download, 18 % over it
  on disk. The Binoculars pair is 437 MB to download and 1.13 GB on disk.
- **"Clearly more accurate" is proven only on 2022-2023 generators.** On the golden set
  (one generator of 2026) every variant flags 0 or 1 of 100 AI texts at the 1 % threshold.
  The runtime question is answered; the value question is not. See section 5.

## 2. Models: export, licences, sizes

Export: `torch.onnx.export(dynamo=True)`, logits only, no KV cache, dynamic sequence length.
The legacy TorchScript exporter fails on all three models (`aten::diff` unsupported at
opset 17). int8: `onnxruntime.quantization.quantize_dynamic` (QInt8), all operators
("int8") or MatMul only, embedding left in fp32 ("int8-matmul"). fp16:
`onnxruntime.transformers.float16.convert_float_to_float16(keep_io_types=True)`.

| Model | Licence (Hub card, read 2026-11-12) | Revision | Parameters |
|---|---|---|---|
| HuggingFaceTB/SmolLM2-135M | Apache-2.0 | `93efa2f097d5` | 134,515,008 |
| HuggingFaceTB/SmolLM2-135M-Instruct | Apache-2.0 | `12fd25f77366` | 134,515,008 |
| EleutherAI/gpt-neo-125m | MIT | `21def0189f57` | 125,198,592 |

Sizes in MB (10^6 bytes); gzip -6 and zstd -19. SHA-256 of every file is in
`/tmp/isitai-deep/models/<key>/info.json`.

| File | SmolLM2-135M raw / gzip / zstd | SmolLM2-135M-Instruct | GPT-Neo-125M |
|---|---|---|---|
| fp32.onnx | 542.8 / 253.6 / 213.2 | 542.8 / 253.6 / 213.1 | 552.3 / 236.2 / 198.6 |
| fp16.onnx | 273.8 / 208.3 / 204.1 | 273.8 / 208.3 / 204.2 | 301.9 / 194.1 / 189.4 |
| int8-matmul.onnx | 224.0 / 127.5 / 116.5 | 224.0 / 127.5 / 116.2 | 297.3 / 131.1 / 116.0 |
| int8.onnx | 139.0 / 93.4 / 90.6 | 139.0 / 93.5 / 89.8 | 176.8 / 84.9 / 81.9 |
| tokenizer.json | 3.5 / 0.6 / 0.5 | same file | 3.6 / 0.6 / 0.5 |

- fp32 is 4 bytes per parameter: the tied embedding is not duplicated. GPT-Neo carries
  about 50 MB more than its parameters (not investigated; probably the attention-mask
  buffers).
- The SmolLM2 weights are published in bf16: the fp32 file compresses to the size of the
  fp16 one (zstd 213 MB against 204 MB). **A compressed fp32 download costs the same as
  fp16 and keeps exact scores.**
- fp16 scores stay close to fp32 (120 texts: max 4e-4 Binoculars, 8e-3 Fast-DetectGPT
  SmolLM2, 1.5e-2 Fast-DetectGPT GPT-Neo) but the fp16 graph is slow on CPU under
  onnxruntime (GPT-Neo, Python, same run conditions: 919 ms against 386 ms median). `rten`
  has no f16 tensor type. Not pursued.
- int8 graph: 210 `MatMulInteger` and 120 `DynamicQuantizeLinear` (SmolLM2). Both `ort`
  and `rten` execute it.
- Not done: the optional larger model (SmolLM2-360M, Qwen2.5-0.5B).

## 3. Accuracy: PyTorch fp32 (benchmark), ONNX fp32, ONNX int8

Python onnxruntime 1.31.1, 4 threads, batch of 1, truncation at 512 tokens, the same ids
as the benchmark (400 texts per split, 200 for fiction). Definitions imported from
`bench/detectors/evaluate.py`. Threshold: 1 % false positives on the human texts of `test`,
applied unchanged to the other splits. Cells "TPR / FPR" are percentages at that threshold.
Intervals are wide (about ± 0.03 to 0.07 AUROC).

| Detector, precision | AUROC test | ood | fr | fiction | attack | TPR test | ood | fr | fiction | attack |
|---|---|---|---|---|---|---|---|---|---|---|
| Binoculars SmolLM2 pair, PyTorch fp32 (benchmark) | 0.83 | 0.95 | 0.81 | 0.70 | — | 70 | 86 / 6 | 47 / 9 | — | — |
| Binoculars SmolLM2 pair, ONNX fp32 | 0.828 | 0.947 | 0.814 | 0.697 | 0.789 | 70 | 86 / 6 | 47 / 9 | 31 / 1 | 60 / 12 |
| Binoculars SmolLM2 pair, ONNX int8 | 0.821 | 0.955 | 0.803 | 0.670 | 0.793 | 67 | 82 / 2 | **20 / 4** | **14 / 0** | 55 / 10 |
| Binoculars SmolLM2 pair, ONNX int8-matmul | 0.822 | 0.953 | 0.804 | not run | not run | 67 | 82 / 4 | 24 / 4 | not run | not run |
| Fast-DetectGPT GPT-Neo-125M, PyTorch fp32 (benchmark) | 0.80 | 0.94 | 0.82 | 0.65 | — | — | 75 / 1 | 22 / 2 | — | — |
| Fast-DetectGPT GPT-Neo-125M, ONNX fp32 | 0.800 | 0.938 | 0.818 | 0.646 | 0.750 | 60 | 75 / 1 | 22 / 2 | 28 / 3 | 42 / 2 |
| Fast-DetectGPT GPT-Neo-125M, ONNX int8 | 0.800 | 0.920 | 0.795 | 0.625 | 0.720 | 60 | 70 / 2 | 15 / 0 | **2 / 0** | 55 / **20** |
| Fast-DetectGPT SmolLM2-135M alone, ONNX fp32 | 0.793 | 0.908 | 0.767 | 0.631 | 0.732 | 61 | 74 / 4 | 29 / 8 | 40 / 7 | 48 / 16 |
| Fast-DetectGPT SmolLM2-135M alone, ONNX int8 | 0.790 | 0.911 | 0.743 | 0.613 | 0.723 | 58 | 74 / 5 | 10 / 0 | 41 / 14 | 46 / 14 |
| Fast-DetectGPT SmolLM2-135M alone, ONNX int8-matmul | 0.790 | 0.913 | 0.730 | not run | not run | 59 | 77 / 5 | 14 / 2 | not run | not run |

The benchmark rows are the figures of `docs/research/BENCH-text-detectors.md`; "—" means
the figure is not in that table.

### Parity of ONNX fp32 with the benchmark's PyTorch scores (1,800 texts, same ids)

| Detector | max abs diff | mean abs diff | Score scale (sd) |
|---|---|---|---|
| Binoculars SmolLM2 pair | 4.8e-05 | 2.9e-05 | 0.14 |
| Fast-DetectGPT GPT-Neo-125M | 1.1e-03 | 6.2e-04 | 2.5 |
| Fast-DetectGPT SmolLM2-135M alone (no benchmark run; PyTorch fp32 run here on 120 texts) | 1.3e-05 | 3.7e-06 | 2.3 |

The acceptance criterion of the benchmark report (scores equal to PyTorch within 0.01) is
met in fp32.

### What int8 does to the scores (against ONNX fp32 of the same detector)

| Detector | Spearman | mean abs diff | max abs diff | fp32 score sd | At the fp32 threshold: test TPR / FPR | fr | ood |
|---|---|---|---|---|---|---|---|
| Binoculars pair, int8 | 0.968 | 0.050 | 0.215 | 0.140 | 76 / **16** | 64 / **18** | 94 / **16** |
| Binoculars pair, int8-matmul (1,200 texts) | 0.970 | 0.044 | 0.260 | 0.149 | 76 / 10 | 64 / 18 | 94 / 15 |
| Fast-DetectGPT GPT-Neo, int8 | **0.855** | 3.116 | 6.651 | 2.471 | 24 / 0 | 0 / 0 | 24 / 0 |
| Fast-DetectGPT SmolLM2, int8 | 0.926 | 0.550 | 2.606 | 2.267 | 62 / 4 | 14 / 1 | 79 / 6 |
| Fast-DetectGPT SmolLM2, int8-matmul (1,200 texts) | 0.932 | 0.513 | 2.671 | 2.294 | 62 / 3 | 16 / 4 | 82 / 7 |

Findings:

- The in-distribution AUROC barely moves, which hides the damage. The score scale shifts
  (an fp32 threshold gives 16 % false positives on `test` with int8 Binoculars), and with a
  threshold refitted for int8 the transferred detection falls: French 47 % to 20 %
  (Binoculars), fiction 31 % to 14 % (Binoculars) and 28 % to 2 % (GPT-Neo).
- On the golden set the int8 Binoculars AUROC in French falls from 0.80 to 0.56.
- Keeping the embedding in fp32 (int8-matmul) does not repair it.
- Dynamic int8 is the only quantisation tried. Static quantisation with calibration data,
  per-channel weights or QAT were not tried.

## 4. Rust inference

Standalone project `bench/deep-spike/` (own `[workspace]`, one binary, runtime chosen by a
cargo feature). Tokenizer: `tokenizers` 0.23.2 with `tokenizer.json`; token ids equal to
Python `AutoTokenizer` on 120 of 120 texts for both tokenizers. Criterion computed row by
row in f64. Parity set: 120 texts (60 `test`, 30 `test_fr`, 30 `test_fiction`), median 444
to 447 tokens, so longer than the benchmark's median text: do not compare these times with
the benchmark's 96 and 176 ms.

### What works

| Runtime | Version, status | Result |
|---|---|---|
| `ort` | 2.0.0-rc.15: **release candidate, no stable 2.x**; wraps ONNX Runtime 1.31 (C++, MIT) | Works, fp32 and int8. Exact parity with Python onnxruntime. |
| `rten` | 0.28.0, pure Rust, 0.x, one main author | Works, fp32 and int8, loads the `.onnx` file directly. fp32 parity 4e-5. |
| `tract-onnx` | 0.23.10, pure Rust | **Failed as loaded here** (symbolic sequence length, no concrete input fact), on both fp32 and int8 graphs: `Evaluating "node_cumsum" CumSum: TDim is not a number`. Builds (20.0 MB binary). A concrete input shape or a fixed-length export was not tried. |
| `candle` | 0.11.1 (safetensors, no ONNX) | **Not tried** (time). |
| Crates named in `OSS-patterns-reuse.md` section 2 | `is-it-slop` serves a TF-IDF model in ONNX; `sonai`, `jpegpast`, `image-forensics` use no inference runtime | No additional runtime to test. Which ONNX crate `is-it-slop` uses was not checked. Its section 3 result (bigram repetition sign) concerns stylometry, not this tier. |

How `ort` gets the native library:

- `download-binaries` (the crate's default): `ort-sys` downloads a prebuilt static
  `libonnxruntime.a` (83.5 MB for aarch64-apple-darwin) from pyke's CDN **at build time**,
  and now requires a TLS feature (`tls-rustls` here). On this machine the link then fails
  with `Undefined symbols: ___isPlatformVersionAtLeast`; it passes with
  `MACOSX_DEPLOYMENT_TARGET=13.4` and `-C link-arg=<libclang_rt.osx.a>`. Result: one
  22.1 MB binary, no dylib.
- `load-dynamic`: nothing downloaded at build time; the binary (3.4 MB) loads the library
  named by `ORT_DYLIB_PATH`. Used for every measurement below, with the
  `libonnxruntime.1.31.1.dylib` of the onnxruntime 1.31.1 Python wheel (33.0 MB, 9.1 MB
  gzip). This is the mode to ship: it matches the "no download at build time" rule already
  applied to `c2pa`.
- ONNX Runtime allows one environment per process: both sessions must share it (the first
  version of the spike panicked on the second model).

Official ONNX Runtime 1.31.1 CPU archives (GitHub release asset sizes, compressed; the
unpacked library was measured only on macOS arm64):

| Platform | Archive |
|---|---|
| linux-x64 | 11.4 MB (tgz) |
| linux-aarch64 | 10.3 MB (tgz) |
| osx-arm64 | 36.9 MB (tgz); the dylib alone is 33.0 MB, 9.1 MB gzip |
| win-x64 | 82.9 MB (zip, content not inspected) |
| win-arm64 | 85.9 MB (zip, content not inspected) |

### Parity, speed, memory (macOS arm64, release build, 120 texts)

"vs Python" is the difference with Python onnxruntime on the same ONNX file. "Model" is the
forward pass alone; the rest is tokenisation and the criterion, which is single-threaded
and not optimised (about 80 to 130 ms per text).

| Runtime | detector | precision | threads | n | token ids equal | max abs diff vs Python ORT | mean abs diff | median ms/text | of which model forward | p90 ms | median tokens | peak RSS MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `ort` | bino | fp32 | 1 | 120 | 120/120 | 2.34e-14 | 1.22e-15 | 498 | 370 | 598 | 444 | 2629 |
| `ort` | bino | fp32 | 4 | 120 | 120/120 | 2.34e-14 | 1.22e-15 | 440 | 311 | 540 | 444 | 2418 |
| `ort` | bino | int8 | 4 | 120 | 120/120 | 1.38e-14 | 9.50e-16 | 468 | 334 | 550 | 444 | 1892 |
| `ort` | fdgpt-neo125 | fp16 | 4 | 120 | 120/120 | 5.56e-13 | 1.31e-13 | 393 | 312 | 467 | 447 | 1134 |
| `ort` | fdgpt-neo125 | fp32 | 1 | 120 | 120/120 | 9.35e-14 | 2.42e-14 | 235 | 154 | 271 | 447 | 1501 |
| `ort` | fdgpt-neo125 | fp32 | 4 | 120 | 120/120 | 9.35e-14 | 2.42e-14 | 188 | 110 | 221 | 447 | 1513 |
| `ort` | fdgpt-neo125 | int8 | 4 | 120 | 120/120 | 6.86e-14 | 2.15e-14 | 194 | 112 | 232 | 447 | 1134 |
| `ort` | fdgpt-smollm2-135m | fp32 | 1 | 120 | 120/120 | 8.19e-14 | 2.37e-14 | 267 | 182 | 326 | 444 | 1496 |
| `ort` | fdgpt-smollm2-135m | fp32 | 4 | 120 | 120/120 | 8.19e-14 | 2.37e-14 | 229 | 150 | 271 | 444 | 1383 |
| `ort` | fdgpt-smollm2-135m | int8 | 4 | 120 | 120/120 | 1.14e-13 | 2.58e-14 | 246 | 163 | 289 | 444 | 1074 |
| `rten` | bino | fp32 | 4 | 120 | 120/120 | 1.35e-06 | 1.97e-07 | 870 | 734 | 1001 | 444 | 2393 |
| `rten` | bino | int8 | 4 | 120 | 120/120 | 2.01e-01 | 4.64e-02 | 516 | 385 | 587 | 444 | 1678 |
| `rten` | fdgpt-neo125 | fp32 | 1 | 120 | 120/120 | 3.64e-05 | 9.35e-06 | 1110 | 1023 | 1290 | 447 | 1566 |
| `rten` | fdgpt-neo125 | fp32 | 4 | 120 | 120/120 | 3.64e-05 | 9.35e-06 | 390 | 307 | 455 | 447 | 1486 |
| `rten` | fdgpt-neo125 | int8 | 4 | 120 | 120/120 | 5.39e+00 | 1.46e+00 | 263 | 169 | 300 | 447 | 1177 |
| `rten` | fdgpt-smollm2-135m | fp32 | 4 | 120 | 120/120 | 1.94e-05 | 4.61e-06 | 438 | 350 | 514 | 444 | 1462 |
| `rten` | fdgpt-smollm2-135m | int8 | 4 | 120 | 120/120 | 3.27e+00 | 1.02e+00 | 272 | 185 | 314 | 444 | 1068 |

- fp32: `ort` is bit-for-bit the Python onnxruntime; `rten` differs by at most 3.6e-5.
- **int8 is not portable across runtimes.** Same int8 file, same texts, `rten` against
  `ort`: mean difference 0.046 (Binoculars, score sd 0.14), 1.0 (Fast-DetectGPT SmolLM2,
  sd 2.3) and 1.5 (GPT-Neo, sd 2.5); maximum 0.20, 3.3 and 5.4. Within one runtime int8 is
  stable: `ort` in Rust equals Python onnxruntime to 1e-13, and two Rust runs are
  identical.
- int8 is not faster under `ort` on this CPU (194 ms against 188 ms); it is faster under
  `rten` (263 ms against 390 ms). The fp16 graph is twice as slow under `ort` (393 ms).
- Threads: `ort` loses little at 1 thread (235 ms against 188 ms, GPT-Neo; CPU time equals
  wall time in that run, so the setting did bind); `rten` needs its threads (1,110 ms
  against 390 ms, measured for GPT-Neo only). `rten` takes its thread count from
  `RTEN_NUM_THREADS`.
- Peak RSS is 1.4 to 1.5 GB for one fp32 model and 2.4 GB for the pair. The spike copies
  the logits (512 x 50,257 floats, 103 MB) and does not memory-map the model: this is an
  upper bound, not a tuned figure.

Release binary sizes (stripped, thin LTO, `tokenizers` with `onig` included):

| Build | Binary | gzip |
|---|---|---|
| `ort` load-dynamic | 3.37 MB (+ ONNX Runtime library) | 1.38 MB |
| `ort` static (download-binaries) | 22.10 MB | 8.57 MB |
| `rten` | 6.46 MB | 2.70 MB |
| `tract-onnx` (does not run the model) | 19.97 MB | 7.66 MB |

WebAssembly:

- `rten` + `tokenizers` (`unstable_wasm`, no `onig`):
  `cargo check --release --target wasm32-unknown-unknown` **passes**. Not built, not run,
  size not measured. A 550 MB model is not a browser payload anyway.
- `ort` feature set of this spike: `cargo check` for `wasm32-unknown-unknown` **fails**, in
  dependencies (`getrandom` without the `wasm_js` flag, and the C code of `onig_sys`: `stdlib.h`
  not found). `ort` itself has a separate `web` backend that was not tried.

## 5. Corpus and golden set: false positives per language

Threshold "high" = each run's own 1 % threshold on `test` (English, RAID). Two different
populations; they are never pooled.

### Wikipedia humans (`corpus/text/`, 117 texts, 9 or 10 per language): counts only

| Run | All | ar | de | en | es | fr | it | ja | nl | pl | pt | ru | zh | `ai-snowman` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Binoculars pair fp32 | 1/117 | 0/10 | 0/10 | 0/10 | 0/10 | 1/10 | 0/10 | 0/9 | 0/10 | 0/10 | 0/9 | 0/10 | 0/9 | missed |
| Binoculars pair int8 | 0/117 | 0 | 0 | 0 | 0 | 0/10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | missed |
| Fast-DetectGPT GPT-Neo fp32 | 2/117 | 0/10 | 0/10 | 0/10 | 0/10 | 1/10 | 0/10 | 0/9 | 0/10 | 0/10 | 1/9 | 0/10 | 0/9 | flagged |
| Fast-DetectGPT GPT-Neo int8 | 0/117 | 0 | 0 | 0 | 0 | 0/10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | missed |
| Fast-DetectGPT SmolLM2 fp32 | **9/117** | 1/10 | 0/10 | 0/10 | 1/10 | **4/10** | 0/10 | 0/9 | 2/10 | 0/10 | 1/9 | 0/10 | 0/9 | flagged |
| Fast-DetectGPT SmolLM2 int8 | 0/117 | 0 | 0 | 0 | 0 | 0/10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | missed |

The fp32 rows reproduce the benchmark (1/117 and 2/117, same files). With 9 or 10 texts a
language cannot support a rate: zero flagged out of 10 only bounds the rate below 26 %
(95 %). French is the worst subgroup in every fp32 row.

### Golden set v1.0 (`bench/golden/build.py`, manifest `047fd6829dee315a…`)

Worst subgroup first. Human class: 75 French segments from 9 documents and 75 English
segments from 27 documents, all by one author; segments of one document are not
independent. AI class: 100 texts, **one generator** (`deepseek-v4.1-flash`). Labels come
from provenance; the protocol's double reading (Cohen's kappa) has not been done. `mixed`
and `degraded` were not scored.

| Run | Humans flagged, fr (n=75) | Humans flagged, en (n=75) | AI flagged, fr (n=50) | AI flagged, en (n=50) | AUROC fr | AUROC en |
|---|---|---|---|---|---|---|
| Binoculars pair fp32 | 0/75 | 0/75 | 0/50 | 0/50 | 0.804 | **0.357** |
| Binoculars pair int8 | 0/75 | 0/75 | 0/50 | 0/50 | 0.561 | 0.202 |
| Fast-DetectGPT GPT-Neo fp32 | 0/75 | 0/75 | 1/50 | 0/50 | 0.846 | 0.730 |
| Fast-DetectGPT GPT-Neo int8 | 0/75 | 0/75 | 0/50 | 0/50 | 0.822 | 0.882 |
| Fast-DetectGPT SmolLM2 fp32 | 0/75 | 0/75 | 1/50 | 0/50 | 0.825 | 0.542 |
| Fast-DetectGPT SmolLM2 int8 | 0/75 | 0/75 | 0/50 | 0/50 | 0.538 | 0.289 |

What the protocol allows:

- False positives, per language, zero observed out of 75: **at most 3.9 %** (exact one-sided
  95 % bound, the rule of PROTOCOL section 2; Wilson two-sided interval [0, 5] %). Nothing
  below that may be claimed. Counted in documents, French has 9: under the protocol's
  minimum of 30 for a subgroup, so the French figure is a count, not a claim.
- Recall on this generator: 0 or 1 of 50 per language (Wilson upper bound 7 to 10 %). At
  the threshold that keeps humans safe, **the full tier does not detect this 2026
  generator.** The English AUROC of Binoculars is below 0.5: these AI texts look less
  "machine" to the SmolLM2 pair than the author's own English writing.
- One generator and one human author: no general statement on current models follows.
  These figures must not be compared with the RAID figures of section 3 as if they were
  the same population.

## 6. Packaging

Measured on macOS arm64. Other platforms: only the ONNX Runtime archive size differs
(section 4); binaries for them were not built.

| "Full" package | Model files | Runtime | Binary | Download (compressed) | On disk |
|---|---|---|---|---|---|
| **Fast-DetectGPT GPT-Neo-125M fp32, `ort` load-dynamic** | 552.3 MB + tokenizer 3.6 MB (zstd 198.6 + 0.5) | dylib 33.0 MB (gzip 9.1) | 3.4 MB (gzip 1.4) | **209.6 MB** | **592.3 MB** |
| Same, `rten` (pure Rust) | same | none | 6.5 MB (gzip 2.7) | 201.8 MB | 562.4 MB |
| Binoculars SmolLM2 pair fp32, `ort` load-dynamic | 1,085.6 MB + 3.5 MB (zstd 426.3 + 0.5) | 33.0 MB (9.1) | 3.4 MB (1.4) | 437.3 MB | 1,125.5 MB |
| Binoculars pair int8, `ort` (rejected: accuracy, portability) | 278.0 MB + 3.5 MB (zstd 180.4 + 0.5) | 33.0 MB (9.1) | 3.4 MB (1.4) | 191.4 MB | 317.9 MB |

The binary here is the spike's command-line program, not an N-API or Python extension;
the binding's own size is not measured.

Delivery:

- **Not inside the npm or PyPI package.** 550 MB exceeds what registries accept in
  practice (PyPI's default limit is 100 MB per file: not re-checked here) and would be
  paid by every install.
- **Separate, explicit fetch step**, never at run time and never at build time:
  for example `isitai-full fetch` (or the caller places the files itself). It downloads
  the zstd files, checks the SHA-256 pinned in the package (the values are in
  `info.json`), and decompresses. `check()` only reads local files; if the model is
  absent it returns a warning and no coefficient, as `effort: deep` already does in the
  roadmap. This keeps the promise "no network at run time" and avoids the pattern noted
  for `is-it-slop` (model downloaded by the build script).
- The ONNX Runtime library is a second artefact per platform; it can be vendored in the
  platform package (10 to 37 MB compressed on Linux and macOS) rather than fetched.
- Every result carries the model file's SHA-256 prefix and the runtime, through
  `calibration_id` (section 7).

## 7. Calibration sketch

Following `docs/research/FALLBACK-probabilistic.md` (sections 3 and 7): the output is a
likelihood ratio with an interval and a `calibration_id`, never a bare probability;
`posterior` stays `null` without a prevalence supplied by the caller.

1. **One table per (detector, model file, precision, runtime family, language).**
   `calibration_id = text-fastdetectgpt/gpt-neo-125m@8d6b02f63d51/fp32/ort-1.31/<lang>/<date>`.
   The model hash and the precision are part of the key because the score scale depends on
   them (section 3: an fp32 threshold gives 16 % false positives with int8). fp32 under
   `ort` and `rten` agree within 4e-5, so one table can serve both; this needs checking on
   x86-64.
2. **Language is an input of the lookup**, so the full tier needs a language identifier
   (not built here). No table for the language: `lr = null` and a warning. Today that is
   every language except English and French.
3. **Method.** Per language, human and AI score samples. Monotone fit (isotonic regression,
   pool-adjacent-violators) of P(AI | score) on a class-balanced sample; `lr = p / (1 - p)`,
   shrunk towards 1. Interval: bootstrap over the calibration sample, reported with its
   coverage. Bands from the LR, with the "high" band additionally gated by a conformal
   threshold on the human scores (the ceil((n+1)(1-alpha))-th score): alpha = 1 % needs at
   least 99 human texts in that language. An interval that straddles a band limit gives
   `indeterminate`. Reported per subgroup: ECE, Brier, NLL (not computed here).
4. **Abstention** when: no table; fewer than 30 calibration texts (or 99 for the 1 % band);
   text under a minimum length (the benchmark dropped texts under 10 words; a floor of
   about 50 tokens is a proposal, not measured); language identification uncertain.
5. **Data available today, and what it supports.**

| Language | Human calibration data | Supports |
|---|---|---|
| en | `test` humans (200 in the subsample, 1,000 in the split; RAID, 6 domains) | a table; checked on 75 golden segments (0 flagged) and 10 Wikipedia texts (0 flagged) |
| fr | `test_fr` humans (200 in the subsample, 495 in the split; hotel reviews and Q&A, median 70 words) | a provisional table, wrong register; 75 golden segments from 9 documents; 10 Wikipedia texts |
| 10 other Wikipedia languages | 9 or 10 texts each | nothing: abstain |

Measured effect of a per-language threshold (French threshold = 1 % false positives on
the `test_fr` humans, fp32):

| Run | English threshold | French threshold | `test_fr` detection at the French threshold | Wikipedia fr humans flagged | Golden fr humans flagged | Golden fr AI flagged |
|---|---|---|---|---|---|---|
| Binoculars pair | -0.8802 | -0.8303 | 20 % (47 % at the English threshold, with 9 % false positives) | 0/10 (1/10 before) | 0/75 | 0/50 |
| Fast-DetectGPT GPT-Neo | 2.2146 | 2.4502 | 18 % (22 %, with 2 % false positives) | 1/10 (1/10 before) | 0/75 | 0/50 |
| Fast-DetectGPT SmolLM2 | 1.8485 | 2.7455 | 16 % (29 %, with 8 % false positives) | 1/10 (4/10 before) | 0/75 | 1/50 |

The French threshold removes the excess false positives and costs most of the French
detection: the high English figure was bought with false positives. The AI side of any
table is the weak point: RAID, MAGE and HC3 are 2022-2023 generators, and the only 2026
generator measured here is not detected.

## 8. Recommendation

1. **Runtime: `ort` with `load-dynamic`**, ONNX Runtime 1.31.1 shipped per platform,
   fp32. Exact parity, 188 ms per 447-token text for the recommended model, no download
   at build time. Known cost: a release-candidate crate and a native library per platform.
   **`rten` is a working pure-Rust fallback** (same scores within 4e-5, about 2 times
   slower, compiles for wasm32) if the native library is refused.
2. **Model: Fast-DetectGPT with GPT-Neo-125M, fp32, MIT.** One 552 MB file (199 MB
   compressed).
3. **No int8.** If the on-disk size must drop under 500 MB, the option to test next is
   fp16 storage decoded to fp32 at load time (302 MB on disk, scores within 0.015), not
   int8.
4. **Do not call the tier "accurate" yet.** Before shipping: a recent-generator set
   outside fiction (increment 2 of the benchmark report), long-form human French, and the
   calibration harness (increment B of the fallback document). On the golden set the
   recommended detector flags 1 of 100 AI texts.

## 9. Not verified

- Any platform other than macOS arm64: no Linux, Windows or x86-64 run. fp32 score
  equality across CPU architectures is assumed, not measured; the calibration tables
  depend on it.
- Timings (shared, loaded machine) and peak RSS (unoptimised glue). No measurement on an
  old or slow machine.
- Why `rten` and `ort` disagree on int8 graphs (which of the two is closer to the
  reference arithmetic was not investigated).
- `tract` with a concrete input shape or a fixed-length export; `candle`; a wasm build that runs; `ort` on wasm.
- Larger models (SmolLM2-360M, Qwen2.5-0.5B); static or per-channel quantisation.
- fp16 storage with fp32 execution (only the fp16 graph was run).
- Size of real Node and Python bindings; Windows archive content; PyPI and npm size limits.
- Licences are those of the Hub cards; the ONNX conversions made here were not published
  and their redistribution terms were not reviewed.
- Golden set: labels from provenance only, one AI generator, one human author.

## 10. Reproduce

```sh
REPO=$PWD; D=/tmp/isitai-deep; export HF_HOME=/tmp/isitai-bench/hf
python3.12 -m venv $D/venv
$D/venv/bin/pip install torch==2.15.0 transformers==5.22.2 onnxruntime==1.31.1 onnx onnxscript \
    numpy==2.5.4 tokenizers==0.23.3 scikit-learn psutil zstandard safetensors
PY=$D/venv/bin/python; S=bench/deep-spike

python3 bench/golden/build.py                       # writes bench/golden/set (gitignored)
$PY $S/prepare_texts.py                             # texts -> $D/texts/*.jsonl
$PY $S/export_onnx.py smollm2-135m smollm2-135m-instruct neo125   # -> $D/models, about 15 min

P=smollm2-135m,smollm2-135m-instruct
$PY $S/score_py.py --det bino  --models $P --prec fp32          # also int8; int8-matmul
$PY $S/score_py.py --det fdgpt --models neo125 --prec fp32      # also int8
$PY $S/score_py.py --det fdgpt --models smollm2-135m --prec fp32
$PY $S/score_py.py --det fdgpt --models smollm2-135m --prec fp32 --sets parity   # token ids
$PY $S/score_py.py --det fdgpt --models neo125 --prec fp32 --sets parity
$PY $S/evaluate.py > $D/results/eval.md

cd $S; export CARGO_TARGET_DIR=$D/target
cargo build --release --features ort-dynamic && cp $D/target/release/isitai-deep-spike $D/spike-ort-dyn
cargo build --release --features "rten-rt native-tok" && cp $D/target/release/isitai-deep-spike $D/spike-rten
cargo check --release --target wasm32-unknown-unknown --features "rten-rt wasm-tok"
./run_rust.sh 4 ort-dyn rten; PRECS=fp32 ./run_rust.sh 1 ort-dyn
$PY compare_rust.py
```

Versions: rustc 1.99.1, `ort` 2.0.0-rc.15, `rten` 0.28.0, `tract-onnx` 0.23.10,
`tokenizers` (Rust) 0.23.2; Python 3.12.13, torch 2.15.0, transformers 5.22.2,
onnxruntime 1.31.1, onnx 1.23.2, onnxscript 0.7.2. Raw tables: `results/eval.md`,
`results/rust.md` and `results/model-info.*.json` (sizes, SHA-256, operator counts) next to
this file.
