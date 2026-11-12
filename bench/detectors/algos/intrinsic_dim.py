"""Intrinsic dimension of the token-embedding cloud of a text (zero-shot).

Paper: Tulchinskii et al., "Intrinsic Dimension Estimation for Robust Detection of
AI-Generated Texts", NeurIPS 2023 (arXiv 2306.04723). Official code: ArGintum/GPTID
(MIT), files IntrinsicDim.py and example.ipynb, read on 2026-11-12.

Idea: run the text through a frozen encoder, take the last-layer embedding of every
token as a point cloud in R^768, estimate the intrinsic dimension of that cloud. Human
text has a higher dimension than generated text, so the score is MINUS the dimension
(higher = more likely AI). No training: the paper then fits a one-feature logistic
regression, which only chooses a threshold and does not change the ranking.

Variants
  phd        persistent homology dimension (PH-dim, alpha = 1), roberta-base
  mle        Levina-Bickel maximum likelihood estimator, roberta-base
  phd-xlmr   PH-dim, xlm-roberta-base (the encoder the paper uses for other languages)
  mle-xlmr   MLE, xlm-roberta-base
The module-level score() is `phd`.

Copied from the official code, unchanged
  - text cleaning: text.replace('\\n', ' ').replace('  ', ' ')
  - tokenizer(truncation=True, max_length=512); the first and last token (<s>, </s>)
    are dropped, so a cloud has at most 510 points. Longer texts are TRUNCATED to their
    first 510 tokens: the rest of the text is not looked at.
  - last hidden state of the encoder, Euclidean distance
  - PH-dim: subsample sizes range(40, N - step, step) with step = (N - 40) // 7
    (MIN_SUBSAMPLE = 40, INTERMEDIATE_POINTS = 7); for each size, 7 random subsamples
    (3 when the subsample holds at least half of the cloud), length of the minimum
    spanning tree of each (Prim, alpha = 1), median over the subsamples; least-squares
    slope m of log(length) against log(size); 3 reruns, mean of the slopes;
    dimension = 1 / (1 - m).
  - MLE: skdim.id.MLE().fit_transform(X) as called in the notebook: k = 20 nearest
    neighbours, pointwise estimate (k - 1) / sum_j log(R_k / R_j), combined over the
    points with the ARITHMETIC mean (fit_transform passes comb="mean"; read in
    scikit-dimension 0.3.3 of May 2023 and in master; MLE.fit alone would default to
    the harmonic mean). Reimplemented in numpy from that source because
    scikit-dimension is not installed in the shared venv; checked against the formula
    with sklearn NearestNeighbors, not against an installed skdim.

Deviations
  1. Randomness. The official code runs the 3 reruns in 3 threads that share the global
     numpy generator, so it is not reproducible. Here the reruns run one after the other
     with a generator seeded by SEED and the CRC32 of the cleaned text: the same text
     gives the same score in any batch and any order.
  2. The distance matrix of the whole cloud is computed once (float64) and indexed for
     each subsample, instead of cdist on each subsample. Same numbers (it is the
     `dist=True` path of the official class), less time.
  3. Short texts. The official code fails under 47 points (step = 0) and returns
     numpy.nan or garbage near that limit. Here a text with fewer than PHD_MIN_POINTS
     (47) points for PH-dim, or fewer than MLE_MIN_POINTS (21, i.e. k + 1) for MLE, or
     whose estimate is not finite or not positive, gets a NEUTRAL dimension: the median
     dimension of a class-balanced sample of the TRAIN split (table FALLBACK_DIM below,
     produced by intrinsic_dim_calibrate.py). Such a text is in effect not scored.
  4. MLE: a point whose pointwise estimate is not finite (zero distance to a neighbour,
     or its 20 neighbours all at the same distance) is left out of the mean.
  5. Models: the notebook loads a local 'roberta-base-cased'; no such model is public,
     the paper says RoBERTa-base, so `FacebookAI/roberta-base` is used (it is cased).
     The multilingual encoder is `FacebookAI/xlm-roberta-base`.
  6. roberta-base on French (test_fr) is outside the setup of the paper, which uses
     XLM-RoBERTa for non-English text; the -xlmr variants are the faithful ones there.
  7. One text per forward pass (as in the official code), float32, CPU.
"""
from __future__ import annotations

import zlib

import numpy as np

SEED = 20261112
MAX_LENGTH = 512          # tokens, special tokens included
MIN_SUBSAMPLE = 40
INTERMEDIATE_POINTS = 7
PHD_MIN_POINTS = MIN_SUBSAMPLE + INTERMEDIATE_POINTS   # 47: below, step = 0
MLE_K = 20
MLE_MIN_POINTS = MLE_K + 1

ROBERTA = "FacebookAI/roberta-base"
XLMR = "FacebookAI/xlm-roberta-base"

#: Neutral dimension given to texts that cannot be scored: median over a class-balanced
#: sample of 300 texts of the train split (intrinsic_dim_calibrate.py --n 300, run on
#: 2026-11-12, texts with enough points). Constants, not fitted at run time.
FALLBACK_DIM = {
    (ROBERTA, "phd"): 9.211,
    (ROBERTA, "mle"): 11.811,
    (XLMR, "phd"): 8.752,
    (XLMR, "mle"): 12.880,
}

MODEL_DESC = {
    ROBERTA: "FacebookAI/roberta-base (MIT; model.safetensors 499 MB + tokenizer 2.7 MB; frozen, not trained on any detection data)",
    XLMR: "FacebookAI/xlm-roberta-base (MIT; model.safetensors 1,116 MB + tokenizer.json 9.1 MB; frozen, not trained on any detection data)",
}


def preprocess_text(text: str) -> str:
    return text.replace("\n", " ").replace("  ", " ")


def prim_tree(adj_matrix: np.ndarray, alpha: float = 1.0) -> float:
    """Length of the minimum spanning tree. Copied from GPTID IntrinsicDim.py (MIT)."""
    infty = np.max(adj_matrix) + 10
    dst = np.ones(adj_matrix.shape[0]) * infty
    visited = np.zeros(adj_matrix.shape[0], dtype=bool)
    ancestor = -np.ones(adj_matrix.shape[0], dtype=int)
    v, s = 0, 0.0
    for _ in range(adj_matrix.shape[0] - 1):
        visited[v] = 1
        ancestor[dst > adj_matrix[v]] = v
        dst = np.minimum(dst, adj_matrix[v])
        dst[visited] = infty
        v = np.argmin(dst)
        s += adj_matrix[v][ancestor[v]] ** alpha
    return float(s)


def distance_matrix(points: np.ndarray) -> np.ndarray:
    from scipy.spatial.distance import cdist
    points = np.asarray(points, dtype=np.float64)
    return cdist(points, points, metric="euclidean")


def phd_dimension(dist: np.ndarray, rng: np.random.RandomState, alpha: float = 1.0,
                  n_reruns: int = 3, n_points: int = 7, n_points_min: int = 3) -> float:
    """PH-dim of a cloud given its distance matrix; nan when the cloud is too small."""
    n_total = dist.shape[0]
    if n_total < PHD_MIN_POINTS:
        return float("nan")
    step = (n_total - MIN_SUBSAMPLE) // INTERMEDIATE_POINTS
    test_n = range(MIN_SUBSAMPLE, n_total - step, step)
    if len(test_n) < 2:
        return float("nan")
    x = np.log(np.array(list(test_n)))
    slopes = np.zeros(n_reruns)
    for r in range(n_reruns):
        lengths = []
        for n in test_n:
            restarts = n_points_min if n_total <= 2 * n else n_points
            reruns = np.ones(restarts)
            for i in range(restarts):
                idx = rng.choice(n_total, size=n, replace=False)
                reruns[i] = prim_tree(dist[np.ix_(idx, idx)], alpha)
            lengths.append(np.median(reruns))
        with np.errstate(divide="ignore", invalid="ignore"):
            y = np.log(np.array(lengths))
            k = len(x)
            slopes[r] = (k * (x * y).sum() - x.sum() * y.sum()) / (k * (x ** 2).sum() - x.sum() ** 2)
    m = np.mean(slopes)
    with np.errstate(divide="ignore", invalid="ignore"):
        return float(1 / (1 - m))


def mle_dimension(dist: np.ndarray, k: int = MLE_K) -> float:
    """Levina-Bickel MLE as skdim.id.MLE().fit_transform(X): k neighbours (self excluded),
    pointwise (k - 1) / sum log(R_k / R_j), arithmetic mean over the points."""
    n_total = dist.shape[0]
    if n_total < k + 1:
        return float("nan")
    d = np.sort(dist, axis=1)[:, 1:k + 1]   # column 0 is the point itself
    with np.errstate(divide="ignore", invalid="ignore"):
        pw = (k - 1) / np.sum(np.log(d[:, -1:] / d), axis=1)   # pointwise dimension
    pw = pw[np.isfinite(pw) & (pw > 0)]
    if pw.size == 0:
        return float("nan")
    return float(np.mean(pw))


_ENCODERS: dict = {}


def load_encoder(model_id: str):
    if model_id not in _ENCODERS:
        import torch
        from transformers import AutoModel, AutoTokenizer
        torch.manual_seed(SEED)
        tok = AutoTokenizer.from_pretrained(model_id)
        model = AutoModel.from_pretrained(model_id, add_pooling_layer=False).to("cpu").eval()
        _ENCODERS[model_id] = (tok, model)
    return _ENCODERS[model_id]


def embed(model_id: str, text: str) -> np.ndarray:
    """Last-layer embeddings of the tokens of one text, <s> and </s> dropped: (N, 768)."""
    import torch
    tok, model = load_encoder(model_id)
    inputs = tok(preprocess_text(text), truncation=True, max_length=MAX_LENGTH, return_tensors="pt")
    with torch.no_grad():
        out = model(**inputs)
    return out[0][0].numpy()[1:-1]


def text_rng(text: str, seed: int = SEED) -> np.random.RandomState:
    return np.random.RandomState((seed ^ zlib.crc32(preprocess_text(text).encode("utf-8"))) & 0xFFFFFFFF)


def dimension(model_id: str, estimator: str, text: str, seed: int = SEED) -> tuple[float, int]:
    """(dimension or nan, number of points)."""
    points = embed(model_id, text)
    n = points.shape[0]
    if n < (PHD_MIN_POINTS if estimator == "phd" else MLE_MIN_POINTS):
        return float("nan"), n
    dist = distance_matrix(points)
    if estimator == "phd":
        dim = phd_dimension(dist, text_rng(text, seed))
    else:
        dim = mle_dimension(dist)
    if not np.isfinite(dim) or dim <= 0:
        dim = float("nan")
    return dim, n


class Detector:
    NEEDS_TRAINING = False
    BATCH_SIZE = 16

    def __init__(self, model_id: str, estimator: str, name: str):
        self.model_id = model_id
        self.estimator = estimator
        self.NAME = name
        self.MODEL = (f"{MODEL_DESC[model_id]}; estimator {estimator}; "
                      f"first {MAX_LENGTH - 2} tokens")
        self.fallback = FALLBACK_DIM[(model_id, estimator)]
        self.n_scored = 0
        self.n_fallback = 0
        load_encoder(model_id)

    def score(self, texts: list[str]) -> list[float]:
        out = []
        for t in texts:
            dim, _ = dimension(self.model_id, self.estimator, t)
            self.n_scored += 1
            if not np.isfinite(dim):
                self.n_fallback += 1
                dim = self.fallback
            out.append(-float(dim))
        return out


VARIANTS = {
    "phd": lambda: Detector(ROBERTA, "phd", "intrinsic_dim.phd"),
    "mle": lambda: Detector(ROBERTA, "mle", "intrinsic_dim.mle"),
    "phd-xlmr": lambda: Detector(XLMR, "phd", "intrinsic_dim.phd-xlmr"),
    "mle-xlmr": lambda: Detector(XLMR, "mle", "intrinsic_dim.mle-xlmr"),
}

NAME = "intrinsic_dim"
NEEDS_TRAINING = False
MODEL = f"{MODEL_DESC[ROBERTA]}; estimator phd; first {MAX_LENGTH - 2} tokens"
BATCH_SIZE = 16
_default = None


def score(texts: list[str]) -> list[float]:
    global _default
    if _default is None:
        _default = Detector(ROBERTA, "phd", NAME)
    return _default.score(texts)
