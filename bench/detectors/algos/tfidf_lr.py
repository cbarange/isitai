"""TF-IDF n-grams with a linear classifier: the family of small open detectors.

  run.py --algo tfidf_lr --variant char15-lr --split test

There is no single reference paper for this family. It is the classic stylometric
baseline (character and word n-gram TF-IDF, logistic regression or linear SVM) used as
the "small model" row of most detection benchmarks, and the approach of the open detector
is-it-slop (github.com/SamBroomy/is-it-slop, MIT), whose README (read 2026-11-12) states:
tiktoken o200k_base tokens, token 2-4-grams, TF-IDF with about 105k features
(min_df 0.07%), chunks of 150 tokens with 15 overlap, a stacked ensemble of calibrated
linear models exported to ONNX, chunk predictions aggregated by weighted mean, about
11.4 MB of artefacts, trained on about 687k samples of 25+ datasets.

Variants (all fitted on the 4,000-row train split only, nothing downloaded but the
o200k_base vocabulary for the bpe variant):

  char15-lr, char15-svm     character 1-5-grams over the raw text (case kept; sklearn
                            replaces each run of 2+ whitespace characters by one
                            space, a single newline or tab is kept), min_df 2,
                            TF-IDF (sublinear tf, smooth idf, L2 norm).
  word12-lr, word12-svm     lower-cased word 1-2-grams; a token is a run of word characters
                            or one punctuation mark (`\\w+|[^\\w\\s]`), min_df 2, same TF-IDF.
  charword-lr               both feature sets side by side (each L2-normalised).
  hash16-lr, hash18-lr,     character 1-5-grams hashed into 2^16 / 2^18 / 2^20 buckets
  hash20-lr                 (sklearn HashingVectorizer: MurmurHash3 x86 32-bit, seed 0,
                            over the UTF-8 bytes of the n-gram, bucket = abs(h) mod 2^b,
                            no sign trick), then the same TF-IDF. No vocabulary to ship:
                            two float32 arrays of 2^b values (idf, weight).
  hash16-lr-q8, hash18-lr-q8, hash20-lr-q8
                            the same model with idf and weights stored as 8-bit integers
                            (linear quantisation, one scale each). The scores of these
                            variants are computed FROM the quantised arrays, so size and
                            accuracy describe the same model.
  bpe24-chunk-lr            the is-it-slop recipe as far as its README describes it:
                            o200k_base tokens, 2-4-grams, chunks of 150 tokens with 15
                            overlap, one logistic regression on chunks, document score =
                            mean of the chunk log-odds weighted by chunk length.

Classifiers: LogisticRegression(C=10, lbfgs, L2) with score = log-odds, and
LinearSVC(C=1) with score = signed distance. Both are monotone in "more likely AI".
C and min_df were set a priori, not tuned on any test split; tfidf_lr_sizes.py reports a
cross-validation on the train split for other values.

Truncation: every text is cut to its first MAX_CHARS = 20,000 characters (code points),
in fit and in score. On the data of 2026-11-12 this cuts one train row (25,815 characters)
and no row of any test split (longest: 15,998).
The bpe variant cuts at MAX_TOKENS = 4,096 tokens after that.

Deviations from is-it-slop (bpe24-chunk-lr), all forced by the contract or unverifiable:
  - trained on 4,000 RAID texts instead of about 687k texts of 25+ datasets;
  - one logistic regression instead of a stacked ensemble of calibrated linear models;
  - min_df 2 documents-chunks instead of 0.07% (which would be 2.8 on 4,000 texts; the
    count of chunks is higher, so the vocabulary is larger in proportion);
  - TF-IDF settings (sublinear tf, smoothing, norm) are sklearn's with sublinear_tf: the
    README does not give theirs and their code was not read;
  - their two-stage text cleaning is not reproduced (no cleaning here);
  - weighted mean of chunk log-odds, weight = number of tokens of the chunk: the README
    says "weighted mean" without the weights.
The pretrained is-it-slop model itself is NOT evaluated here.

Model size: after fit() the model is written in a flat binary layout to
/tmp/isitai-bench/cache/tfidf_lr/<variant>.bin (and .bin.gz, zlib level 9) and both
measured sizes go in MODEL. Layout of a vocabulary model: for each feature the UTF-8
n-gram with a one-byte length, then float32 idf and float32 weight arrays, then the
float32 intercept. Hashed model: the two arrays (float32 or int8/uint8) and the scales.

Deterministic: no sampling anywhere (lbfgs; LinearSVC with random_state=0).
"""
from __future__ import annotations

import gzip
import os
import struct

import numpy as np

from common import CACHE_DIR

NAME = "tfidf_lr"
NEEDS_TRAINING = True
MODEL = "none downloaded; fitted on train (size in the result file of each variant)"

MAX_CHARS = 20_000
MAX_TOKENS = 4_096
CHUNK_TOKENS = 150
CHUNK_OVERLAP = 15
WORD_PATTERN = r"(?u)\w+|[^\w\s]"
SIZE_DIR = os.path.join(CACHE_DIR, "tfidf_lr")


def cut(texts: list[str]) -> list[str]:
    return [t[:MAX_CHARS] for t in texts]


def char_vectorizer(max_features=None):
    from sklearn.feature_extraction.text import TfidfVectorizer
    return TfidfVectorizer(analyzer="char", ngram_range=(1, 5), lowercase=False, min_df=2,
                           sublinear_tf=True, max_features=max_features, dtype=np.float32)


def word_vectorizer(max_features=None):
    from sklearn.feature_extraction.text import TfidfVectorizer
    return TfidfVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True, min_df=2,
                           token_pattern=WORD_PATTERN, sublinear_tf=True,
                           max_features=max_features, dtype=np.float32)


def make_clf(kind: str, c: float | None = None):
    if kind == "lr":
        from sklearn.linear_model import LogisticRegression
        return LogisticRegression(C=10.0 if c is None else c, max_iter=2000)
    from sklearn.svm import LinearSVC
    return LinearSVC(C=1.0 if c is None else c, random_state=0)


def write_sized(name: str, parts: list[bytes]) -> tuple[int, int]:
    """Writes the flat model file and its gzip; returns both sizes in bytes."""
    os.makedirs(SIZE_DIR, exist_ok=True)
    blob = b"".join(parts)
    path = os.path.join(SIZE_DIR, f"{name}.bin")
    with open(path, "wb") as f:
        f.write(blob)
    with open(path + ".gz", "wb") as f:
        f.write(gzip.compress(blob, compresslevel=9, mtime=0))
    return os.path.getsize(path), os.path.getsize(path + ".gz")


def vocab_blob(vocabulary: dict) -> bytes:
    """Features in column order, each as one length byte (UTF-8 bytes) and the n-gram."""
    out = bytearray()
    for term, _ in sorted(vocabulary.items(), key=lambda kv: kv[1]):
        if not isinstance(term, str):  # bpe: a tuple of token ids
            out += struct.pack(f"<B{len(term)}I", len(term), *term)
            continue
        b = term.encode("utf-8")[:255]
        out += bytes([len(b)]) + b
    return bytes(out)


def mb(n: int) -> str:
    return f"{n / 1e6:.2f} MB"


class VocabDetector:
    """TF-IDF over a fitted vocabulary (char, word, or both) and a linear classifier."""
    NEEDS_TRAINING = True
    BATCH_SIZE = 64

    def __init__(self, variant: str, feats: str, clf: str):
        self.NAME = f"tfidf_lr.{variant}"
        self.variant, self.feats, self.clf_kind = variant, feats, clf
        self.MODEL = "not fitted"
        self.vecs = []
        self.clf = None

    def _x(self, texts, fit=False):
        from scipy.sparse import hstack
        mats = [v.fit_transform(texts) if fit else v.transform(texts) for v in self.vecs]
        return mats[0] if len(mats) == 1 else hstack(mats, format="csr")

    def fit(self, rows: list[dict]) -> None:
        self.vecs = {"char": [char_vectorizer()], "word": [word_vectorizer()],
                     "charword": [char_vectorizer(), word_vectorizer()]}[self.feats]
        x = self._x(cut([r["text"] for r in rows]), fit=True)
        self.clf = make_clf(self.clf_kind).fit(x, [r["label"] for r in rows])
        parts = []
        for v in self.vecs:
            parts += [vocab_blob(v.vocabulary_), v.idf_.astype("<f4").tobytes()]
        parts += [self.clf.coef_.astype("<f4").tobytes(), self.clf.intercept_.astype("<f4").tobytes()]
        raw, gz = write_sized(self.variant, parts)
        n = x.shape[1]
        self.MODEL = (f"none downloaded; {self.feats} TF-IDF + {self.clf_kind}, {n:,} features, "
                      f"{mb(raw)} flat ({mb(gz)} gzip), fitted on train")

    def score(self, texts: list[str]) -> list[float]:
        return self.clf.decision_function(self._x(cut(texts))).tolist()


class HashDetector:
    """Hashed character 1-5-grams, TF-IDF, logistic regression; optional 8-bit storage."""
    NEEDS_TRAINING = True
    BATCH_SIZE = 64

    def __init__(self, variant: str, bits: int, q8: bool = False):
        from sklearn.feature_extraction.text import HashingVectorizer
        self.NAME = f"tfidf_lr.{variant}"
        self.variant, self.bits, self.q8 = variant, bits, q8
        self.MODEL = "not fitted"
        self.hasher = HashingVectorizer(analyzer="char", ngram_range=(1, 5), lowercase=False,
                                        n_features=2 ** bits, alternate_sign=False, norm=None,
                                        dtype=np.float32)
        self.idf = self.w = None
        self.b = 0.0

    def _x(self, texts):
        from sklearn.preprocessing import normalize
        x = self.hasher.transform(texts)
        x.data = 1.0 + np.log(x.data)                    # sublinear tf
        x = x.multiply(self.idf.reshape(1, -1)).tocsr()  # idf
        return normalize(x, norm="l2", copy=False)

    def fit(self, rows: list[dict]) -> None:
        texts = cut([r["text"] for r in rows])
        counts = self.hasher.transform(texts)
        n = counts.shape[0]
        df = np.bincount(counts.indices, minlength=counts.shape[1])
        self.idf = (np.log((1.0 + n) / (1.0 + df)) + 1.0).astype(np.float32)  # sklearn smooth idf
        clf = make_clf("lr").fit(self._x(texts), [r["label"] for r in rows])
        self.w = clf.coef_[0].astype(np.float32)
        self.b = float(clf.intercept_[0])
        used = int((df > 0).sum())
        if self.q8:
            # idf: uint8 over [min, max]; weight: int8 symmetric. Scoring uses these.
            lo, hi = float(self.idf.min()), float(self.idf.max())
            qi = np.round((self.idf - lo) / (hi - lo) * 255).astype(np.uint8)
            ws = float(np.abs(self.w).max()) / 127
            qw = np.round(self.w / ws).astype(np.int8)
            self.idf = (qi.astype(np.float32) / 255 * (hi - lo) + lo).astype(np.float32)
            self.w = qw.astype(np.float32) * ws
            parts = [qi.tobytes(), qw.tobytes(), struct.pack("<4f", lo, hi, ws, self.b)]
        else:
            parts = [self.idf.astype("<f4").tobytes(), self.w.astype("<f4").tobytes(),
                     struct.pack("<f", self.b)]
        raw, gz = write_sized(self.variant, parts)
        self.MODEL = (f"none downloaded; hashed char 1-5 TF-IDF + lr, 2^{self.bits} buckets "
                      f"({used:,} used), {'int8' if self.q8 else 'float32'} storage, "
                      f"{mb(raw)} flat ({mb(gz)} gzip), fitted on train")

    def score(self, texts: list[str]) -> list[float]:
        return (self._x(cut(texts)) @ self.w + self.b).tolist()


class BpeChunkDetector:
    """is-it-slop recipe: o200k_base token 2-4-grams, 150-token chunks, linear model."""
    NEEDS_TRAINING = True
    BATCH_SIZE = 64

    def __init__(self, variant: str):
        os.environ.setdefault("TIKTOKEN_CACHE_DIR", os.path.join(CACHE_DIR, "tiktoken"))
        import tiktoken
        self.NAME = f"tfidf_lr.{variant}"
        self.variant = variant
        self.MODEL = "not fitted"
        self.enc = tiktoken.get_encoding("o200k_base")
        self.vec = self.clf = None

    def _chunks(self, text: str) -> list[list[int]]:
        ids = self.enc.encode(text[:MAX_CHARS], disallowed_special=())[:MAX_TOKENS]
        if len(ids) <= CHUNK_TOKENS:
            return [ids]
        step = CHUNK_TOKENS - CHUNK_OVERLAP
        out = [ids[i:i + CHUNK_TOKENS] for i in range(0, len(ids) - CHUNK_OVERLAP, step)]
        return out

    @staticmethod
    def _ngrams(ids: list[int]):
        return [tuple(ids[i:i + n]) for n in (2, 3, 4) for i in range(len(ids) - n + 1)]

    def fit(self, rows: list[dict]) -> None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        chunks, y = [], []
        for r in rows:
            c = self._chunks(r["text"])
            chunks += c
            y += [r["label"]] * len(c)
        self.vec = TfidfVectorizer(analyzer=self._ngrams, min_df=2, sublinear_tf=True, dtype=np.float32)
        x = self.vec.fit_transform(chunks)
        self.clf = make_clf("lr").fit(x, y)
        raw, gz = write_sized(self.variant, [
            vocab_blob(self.vec.vocabulary_), self.vec.idf_.astype("<f4").tobytes(),
            self.clf.coef_.astype("<f4").tobytes(), self.clf.intercept_.astype("<f4").tobytes()])
        self.MODEL = (f"tiktoken o200k_base vocabulary (3.6 MB download, MIT); token 2-4-gram TF-IDF "
                      f"+ lr on {len(chunks):,} chunks, {x.shape[1]:,} features, {mb(raw)} flat "
                      f"({mb(gz)} gzip) without the tokenizer, fitted on train")

    def score(self, texts: list[str]) -> list[float]:
        chunks, owner = [], []
        for i, t in enumerate(texts):
            c = self._chunks(t)
            chunks += c
            owner += [i] * len(c)
        z = self.clf.decision_function(self.vec.transform(chunks))
        w = np.array([max(1, len(c)) for c in chunks], dtype=float)
        owner = np.asarray(owner)
        num = np.bincount(owner, weights=z * w, minlength=len(texts))
        den = np.bincount(owner, weights=w, minlength=len(texts))
        return (num / den).tolist()


VARIANTS = {
    "char15-lr": lambda: VocabDetector("char15-lr", "char", "lr"),
    "char15-svm": lambda: VocabDetector("char15-svm", "char", "svm"),
    "word12-lr": lambda: VocabDetector("word12-lr", "word", "lr"),
    "word12-svm": lambda: VocabDetector("word12-svm", "word", "svm"),
    "charword-lr": lambda: VocabDetector("charword-lr", "charword", "lr"),
    "hash16-lr": lambda: HashDetector("hash16-lr", 16),
    "hash18-lr": lambda: HashDetector("hash18-lr", 18),
    "hash20-lr": lambda: HashDetector("hash20-lr", 20),
    "hash16-lr-q8": lambda: HashDetector("hash16-lr-q8", 16, q8=True),
    "hash18-lr-q8": lambda: HashDetector("hash18-lr-q8", 18, q8=True),
    "hash20-lr-q8": lambda: HashDetector("hash20-lr-q8", 20, q8=True),
    "bpe24-chunk-lr": lambda: BpeChunkDetector("bpe24-chunk-lr"),
}
