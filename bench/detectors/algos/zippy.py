"""Compression-based detection, no model: ZipPy (Thinkst Applied Research) and variants.

Idea: an LZ compressor seeded with a corpus of AI-written text (the "prelude") compresses a
new AI text better than a new human text, because the AI text repeats more of what the
window already holds.

Reference: https://github.com/thinkst/zippy (MIT), file zippy/zippy.py read on 2026-11-12
(main branch, 18,196 bytes). No paper was looked for; only the repository was read.

  run.py --algo zippy --variant lzma --split test

Variants
--------
Faithful to the official code (formula, compressor parameters, text cleaning, chunking):

  zlib, lzma, brotli   one engine. Per 1,500-character chunk:
                           delta = ratio(prelude) - ratio(prelude + chunk)
                       with ratio = compressed bytes / input bytes; delta > 0 means "AI".
                       The text score is the sum of 100 * delta weighted by
                       len(chunk) / len(text), as in Zippy.run_on_text_chunked (the path
                       the official CLI takes; lzma is its default engine).
                       zlib: level 9, wbits -15, memLevel 9, prelude cut in line chunks of
                       at most 32 KiB, ratio averaged over the chunks. lzma: xz container,
                       preset 4. brotli: quality 8, lgwin 24, MODE_TEXT, lgblock 0.
  ensemble             0.33 * lzma + 0.33 * brotli + 0.33 * zlib (EnsembledZippy weights).

Deviations, NOT in ZipPy (named apart so that nobody takes them for the original):

  <engine>-perbyte     -(C(P+s) - C(P)) / len(s): the cost in compressed bytes of each
                       byte of the sample once the AI prelude P is in the window. The
                       faithful delta shrinks as 1/len(P) and grows with the sample length;
                       this one does not depend on either.
  <engine>-alone       (C(s) - C(empty)) / len(s) - (C(P+s) - C(P)) / len(s): how much the
                       AI prelude helps, against compressing the sample alone (the literal
                       "appended to the prelude versus alone").
  <engine>-contrast    ((C(H+s) - C(H)) - (C(A+s) - C(A))) / len(s): AI prelude A against
                       a HUMAN prelude H of the same size, also from train. This is the
                       two-corpus compression classifier (relative entropy by zipping).
  ensemble-contrast    plain mean of the three -contrast scores (same unit: compressed
                       bytes per byte), no fitted weight.
  stack                logistic regression on 10 features: for each engine the per-byte
                       cost after A, after H, and alone, plus log(len). Fitted on train
                       rows that are in no prelude.

  In the deviation variants: the whole (capped) text is scored at once, without 1,500
  character chunks; the text is only whitespace-normalised (case, punctuation and accents
  are kept; see NORM_DEV); lzma is a raw LZMA2 stream (preset 4) instead of the xz
  container, whose 4-byte block padding quantises the cost of short texts; zlib keeps the
  official line chunks of at most 32 KiB and averages over them.

Deviations of the "faithful" variants from the official code
------------------------------------------------------------
- Prelude: built from the train split (AI rows only), not the 87,152-byte
  zippy/ai-generated.txt shipped with ZipPy. Sizes in PRELUDE_BYTES, chosen on train rows
  held out of the prelude (zippy_sweep.py); the real byte counts are written in MODEL
  after fit().
- No multiprocessing.Pool for texts of more than two chunks (the benchmark forbids process
  pools); the result is the same number.
- The official EnsembledZippy._score_chunk is broken (its loop variable shadows the chunk);
  the ensemble here does what run_on_text_chunked does: each engine scores the chunked
  text, then the weighted sum.
- An empty text after cleaning scores 0.0 (the official code divides by zero).
- zlib: the prelude chunk is compressed once and the compressor state is copied for each
  sample (zlib.compressobj().copy()). The byte count is identical to compressing
  prelude + sample from scratch (asserted in zippy_sweep.py); only the time changes.
- Input cap: the first MAX_CHARS = 12,000 characters of the text (before cleaning). The
  official code has no cap. 12,000 covers every text of test_fiction (longest 11,616).
- The official clean_text() is kept in the faithful variants. It deletes every character
  outside [0-9A-Za-z,.() \\n], so accented letters and apostrophes vanish: French text is
  scored without its accents, against an English prelude.

Prelude size (zippy_sweep.py, AUROC on train rows held out of the preludes; 300 rows per
class for zlib, 150 for lzma and brotli, so about +/- 0.03; "xz" = the AI prelude compressed
with xz -9, what a package would embed):

  bytes (xz)          faithful zlib / lzma / brotli   contrast zlib / lzma / brotli (ws)
     32,000 ( 12 KB)   0.699 /   -   /   -             0.655 /   -   /   -
     64,000 ( 23 KB)   0.678 /   -   /   -             0.734 /   -   /   -
     96,000 ( 34 KB)   0.665 / 0.719 / 0.726           0.706 / 0.740 / 0.732
    128,000 ( 44 KB)   0.670 /   -   /   -             0.745 /   -   /   -
    256,000 ( 81 KB)   0.691 / 0.761 / 0.765           0.837 / 0.794 / 0.797
    512,000 (152 KB)   0.693 /   -   /   -             0.857 /   -   /   -
  1,000,000 (284 KB)   0.692 /   -   /   -             0.862 /   -   /   -
  1,300,000 (363 KB)   0.694 /   -   /   -             0.869 /   -   /   -

Chosen: 256,000 for the faithful variants (zlib is flat; lzma and brotli gain from 96,000
to 256,000; larger sizes were not swept for lzma and brotli because each score recompresses
the whole prelude). Deviation variants: zlib 512,000 (plateau after), lzma and brotli
256,000. The -contrast variants need a human prelude of the same size as well. zlib
-perbyte and -alone do not gain from size (0.65 and 0.63 at every size); lzma and brotli
-perbyte go from 0.72 at 96,000 to 0.74 at 256,000.
The lzma and brotli lines come from `--n 150 --sizes 96000,256000`: the full grid did not
finish in 20 minutes on a loaded machine. Outputs: /tmp/isitai-bench/cache/zippy/sweep_*.txt.
Caveat: RAID train holds, for each source document, the human text and one generation, and
the two classes are shuffled apart, so a held-out row can have its same-prompt twin of the
other class in a prelude. That can bias these AUROCs and the `stack` fit (not the test
splits, which share no document with train).
In the whitespace-normalised preludes each text is flattened to one line.
Normalisation of the deviation variants: the official clean_text scored 0.005 to 0.024
higher than whitespace-only on held-out English (contrast: zlib 512,000 0.881 vs 0.857,
lzma 0.799 vs 0.794, brotli 0.813 vs 0.797). Whitespace-only is kept anyway, on purpose:
clean_text erases every non-ASCII letter, which a multilingual library cannot ship.

Train use: fit() receives the train split, shuffles it with a fixed seed, and cuts each
class in two halves. Preludes come from the first half, everything that is tuned or fitted
(prelude size in zippy_sweep.py, the logistic regression of `stack`) from the second.
No randomness at scoring time.
"""
from __future__ import annotations

import lzma
import math
import random
import re
import zlib

import numpy as np

try:  # brotli is not in the README's pip line; `pip install brotli` (1.2.1 used here)
    import brotli
except ImportError:  # the zlib and lzma variants still work
    brotli = None

NAME = "zippy"
NEEDS_TRAINING = True
MODEL = "none (zlib / lzma / brotli + a text prelude built from train)"

SEED = 20261112
MAX_CHARS = 12_000
CHUNK_CHARS = 1_500          # official chunk_size
ZLIB_WINDOW = 2 ** 15        # official: 2**abs(WBITS)
ENGINES = ("lzma", "brotli", "zlib")   # official ensemble order
WEIGHTS = (0.33, 0.33, 0.33)           # official ensemble weights

#: Prelude size in bytes per (engine, family), chosen by zippy_sweep.py on held-out train
#: rows. "faithful" = official formula, "dev" = the deviation variants.
PRELUDE_BYTES = {
    ("zlib", "faithful"): 256_000, ("lzma", "faithful"): 256_000, ("brotli", "faithful"): 256_000,
    ("zlib", "dev"): 512_000, ("lzma", "dev"): 256_000, ("brotli", "dev"): 256_000,
}
#: Normalisation of the deviation variants: "ws" (whitespace only) or "clean" (official).
NORM_DEV = "ws"
#: Rows of the held-out half used to fit `stack` (per class).
STACK_FIT_PER_CLASS = 500


# ----------------------------------------------------------------------------- text

def clean_text(s: str) -> str:
    """Verbatim from zippy/zippy.py."""
    s = re.sub(' +', ' ', s)
    s = re.sub('\t', '', s)
    s = re.sub('\n+', '\n', s)
    s = re.sub('\n ', '\n', s)
    s = re.sub(' \n', '\n', s)
    s = re.sub(r'[^0-9A-Za-z,\.\(\) \n]', '', s)
    return s


def ws_text(s: str) -> str:
    """Whitespace only: runs of spaces/tabs -> one space, runs of newlines -> one."""
    s = re.sub(r'[ \t\r\f\v ]+', ' ', s)
    s = re.sub(r' ?\n[ \n]*', '\n', s)
    return s.strip()


NORMS = {"clean": clean_text, "ws": ws_text}


def official_chunks(contents: str, chunk_size: int = CHUNK_CHARS) -> list[str]:
    """Verbatim chunking of Zippy.run_on_text_chunked (quirks included)."""
    start = 0
    end = 0
    chunks = []
    while start + chunk_size < len(contents) and end != -1:
        end = contents.rfind(' ', start, start + chunk_size + 1)
        chunks.append(contents[start:end])
        start = end + 1
    chunks.append(contents[start:])
    return chunks


# ----------------------------------------------------------------------------- engines

def _zlib_obj():
    return zlib.compressobj(level=9, wbits=-15, memLevel=9)


def clen(engine: str, data: bytes, raw_lzma: bool = False) -> int:
    """Compressed length of `data`, official parameters."""
    if engine == "zlib":
        c = _zlib_obj()
        return len(c.compress(data)) + len(c.flush(zlib.Z_FINISH))
    if engine == "lzma":
        if raw_lzma:
            c = lzma.LZMACompressor(format=lzma.FORMAT_RAW,
                                    filters=[{"id": lzma.FILTER_LZMA2, "preset": 4}])
        else:
            c = lzma.LZMACompressor(preset=4)
        return len(c.compress(data)) + len(c.flush())
    if engine == "brotli":
        if brotli is None:
            raise RuntimeError("the brotli package is not installed: pip install brotli")
        return len(brotli.compress(data, mode=brotli.MODE_TEXT, quality=8, lgwin=24, lgblock=0))
    raise ValueError(engine)


class Seeded:
    """One prelude piece P for one engine: C(P) once, then C(P + s) for many s."""

    def __init__(self, engine: str, prelude: bytes, raw_lzma: bool = False):
        self.engine = engine
        self.prelude = prelude
        self.raw_lzma = raw_lzma
        self.n = len(prelude)
        self.base = clen(engine, prelude, raw_lzma)
        if engine == "zlib":
            self._state = _zlib_obj()
            self._emitted = len(self._state.compress(prelude))

    def total(self, sample: bytes) -> int:
        """len(compress(P + sample))."""
        if self.engine == "zlib":
            c = self._state.copy()
            return self._emitted + len(c.compress(sample)) + len(c.flush(zlib.Z_FINISH))
        return clen(self.engine, self.prelude + sample, self.raw_lzma)

    def extra(self, sample: bytes) -> int:
        """C(P + sample) - C(P): compressed bytes the sample costs after P."""
        return self.total(sample) - self.base


def split_prelude(engine: str, prelude: str) -> list[str]:
    """zlib: line chunks of at most about 32 KiB, as the official ZlibLlmDetector
    (numpy.array_split over the lines). Other engines: one piece."""
    if engine != "zlib":
        return [prelude]
    lines = prelude.split('\n')
    k = max(1, math.ceil(len(prelude) / ZLIB_WINDOW))
    return ['\n'.join(list(x)) for x in np.array_split(np.array(lines, dtype=object), k)]


# ----------------------------------------------------------------------------- train split

def split_train(rows: list[dict]):
    """(prelude_pool, heldout_pool): each class shuffled with SEED and cut in two halves."""
    pools = ([], [])
    for label in (0, 1):
        cls = sorted((r for r in rows if r["label"] == label), key=lambda r: r["id"])
        random.Random(SEED + label).shuffle(cls)
        half = len(cls) // 2
        pools[0].extend(cls[:half])
        pools[1].extend(cls[half:])
    return pools


def build_prelude(pool: list[dict], label: int, target_bytes: int, norm: str) -> str:
    """Texts of one class, round robin over (generator, domain) cells so that the prelude
    is balanced, joined by newlines, until `target_bytes` UTF-8 bytes are reached (whole
    texts only, each capped at MAX_CHARS)."""
    fn = NORMS[norm]
    cells: dict[tuple, list[dict]] = {}
    for r in pool:
        if r["label"] == label:
            cells.setdefault((r.get("generator", ""), r.get("domain", "")), []).append(r)
    keys = sorted(cells)
    parts, size, depth = [], 0, 0
    while size < target_bytes:
        added = False
        for k in keys:
            if depth < len(cells[k]) and size < target_bytes:
                t = fn(cells[k][depth]["text"][:MAX_CHARS]).replace('\n', ' ') if norm == "ws" \
                    else fn(cells[k][depth]["text"][:MAX_CHARS])
                if t:
                    parts.append(t)
                    size += len(t.encode()) + 1
                    added = True
        depth += 1
        if not added and all(depth >= len(cells[k]) for k in keys):
            break
    return '\n'.join(parts)


# ----------------------------------------------------------------------------- scorers

class Faithful:
    """One engine, official formula."""

    def __init__(self, engine: str, prelude: str):
        self.engine = engine
        self.pieces = [Seeded(engine, p.encode()) for p in split_prelude(engine, prelude)]
        self.prelude_bytes = sum(p.n for p in self.pieces)
        self.prelude_ratio = sum(p.base / p.n for p in self.pieces) / len(self.pieces)

    def delta(self, chunk: str) -> float:
        b = chunk.encode()
        ratio = sum(p.total(b) / (p.n + len(b)) for p in self.pieces) / len(self.pieces)
        return self.prelude_ratio - ratio

    def score_text(self, text: str) -> float:
        contents = clean_text(text[:MAX_CHARS])
        if not contents:
            return 0.0
        chunks = official_chunks(contents)
        # official: 'AI' when delta >= 0, summed with a minus sign; here AI is positive
        return sum(100.0 * self.delta(c) * (len(c) / len(contents)) for c in chunks)


class PerByte:
    """Per-byte costs of a sample for one engine: after the AI prelude, after the human
    prelude (when given), and alone."""

    def __init__(self, engine: str, ai_prelude: str, human_prelude: str | None, norm: str):
        self.engine = engine
        self.norm = NORMS[norm]
        self.ai = [Seeded(engine, p.encode(), True) for p in split_prelude(engine, ai_prelude)]
        self.human = [Seeded(engine, p.encode(), True)
                      for p in split_prelude(engine, human_prelude)] if human_prelude else []
        self.empty = clen(engine, b"", True)
        self.prelude_bytes = sum(p.n for p in self.ai) + sum(p.n for p in self.human)

    def costs(self, text: str):
        """(n_bytes, cost_after_ai, cost_after_human, cost_alone), costs per byte."""
        b = b"\n" + self.norm(text[:MAX_CHARS]).encode()
        n = len(b)
        if n <= 1:
            return 0, 0.0, 0.0, 0.0
        ai = sum(p.extra(b) for p in self.ai) / len(self.ai) / n
        hu = sum(p.extra(b) for p in self.human) / len(self.human) / n if self.human else 0.0
        alone = (clen(self.engine, b, True) - self.empty) / n
        return n, ai, hu, alone


class Detector:
    NEEDS_TRAINING = True
    BATCH_SIZE = 16

    def __init__(self, kind: str, engines: tuple[str, ...]):
        # kind: faithful | perbyte | alone | contrast | stack
        self.kind = kind
        self.engines = engines
        self.NAME = "zippy"
        self.MODEL = MODEL
        self.scorers: list = []
        self.clf = None

    def fit(self, rows: list[dict]) -> None:
        missing = [e for e in self.engines if e == "brotli" and brotli is None]
        if missing:
            raise SystemExit("zippy: this variant needs the brotli package (pip install brotli)")
        pool, heldout = split_train(rows)
        self.scorers = []
        desc = []
        for e in self.engines:
            if self.kind == "faithful":
                p = build_prelude(pool, 1, PRELUDE_BYTES[(e, "faithful")], "clean")
                s = Faithful(e, clean_text(p))
                desc.append(f"{e}: AI prelude {s.prelude_bytes:,} bytes")
            else:
                size = PRELUDE_BYTES[(e, "dev")]
                a = build_prelude(pool, 1, size, NORM_DEV)
                h = build_prelude(pool, 0, size, NORM_DEV) if self.kind in ("contrast", "stack") else None
                s = PerByte(e, a, h, NORM_DEV)
                desc.append(f"{e}: AI prelude {len(a.encode()):,} bytes"
                            + (f" + human prelude {len(h.encode()):,} bytes" if h else ""))
            self.scorers.append(s)
        if self.kind == "stack":
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            fit_rows = []
            for label in (0, 1):
                fit_rows += [r for r in heldout if r["label"] == label][:STACK_FIT_PER_CLASS]
            x = self._features([r["text"] for r in fit_rows])
            y = [r["label"] for r in fit_rows]
            self.clf = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=1000)).fit(x, y)
            desc.append(f"logistic regression, 10 features, fitted on {len(fit_rows)} held-out train rows")
        self.MODEL = "none; text prelude from train (" + "; ".join(desc) + "), raw UTF-8, uncompressed"

    def _features(self, texts: list[str]) -> np.ndarray:
        out = []
        for t in texts:
            row, n = [], 0
            for s in self.scorers:
                n, ai, hu, alone = s.costs(t)
                row += [ai, hu, alone]
            out.append(row + [math.log1p(n)])
        return np.asarray(out, dtype=float)

    def score(self, texts: list[str]) -> list[float]:
        if self.kind == "faithful":
            if len(self.scorers) == 1:
                return [self.scorers[0].score_text(t) for t in texts]
            return [sum(w * s.score_text(t) for w, s in zip(WEIGHTS, self.scorers)) for t in texts]
        if self.kind == "stack":
            return self.clf.decision_function(self._features(texts)).tolist()
        out = []
        for t in texts:
            vals = []
            for s in self.scorers:
                _, ai, hu, alone = s.costs(t)
                vals.append({"perbyte": -ai, "alone": alone - ai, "contrast": hu - ai}[self.kind])
            out.append(sum(vals) / len(vals))
        return out


def _make(kind: str, engines: tuple[str, ...]):
    return lambda: Detector(kind, engines)


VARIANTS = {"ensemble": _make("faithful", ENGINES),
            "ensemble-contrast": _make("contrast", ENGINES),
            "stack": _make("stack", ENGINES)}
for _e in ("zlib", "lzma", "brotli"):
    VARIANTS[_e] = _make("faithful", (_e,))
    for _k in ("perbyte", "alone", "contrast"):
        VARIANTS[f"{_e}-{_k}"] = _make(_k, (_e,))
