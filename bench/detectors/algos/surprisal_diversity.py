"""Surprisal-dynamics detectors from one forward pass of a small causal language model on
CPU: DivEye (supervised, 10 statistics of the token surprisal series) and Lastde
(training-free, log-likelihood over multiscale diversity entropy).

  run.py --algo surprisal_diversity --variant diveye-gpt2 --split all
  run.py --algo surprisal_diversity --variant lastde-gpt2 --split all
  surprisal_diversity_dump.py --split all        # per-text and per-window features, timing split

Variants (`<method>-<model>`, model in {gpt2, smollm2-135m}):
  diveye-<model>         DivEye. "Diversity Boosts AI-Generated Text Detection", Basani and
                         Chen, TMLR 2026, arXiv 2509.18880. Feature definitions taken from
                         the official code github.com/IBM/diveye, `diveye_utils.py`
                         (read on 2026-11-12; that code is CC BY-NC-SA 4.0, so nothing is
                         copied: the statistics are rewritten here from their definitions).
                         Trained on the train split only; the score is P(ai).
  lastde-<model>         Lastde. "Training-free LLM-generated Text Detection by Mining Token
                         Probability Sequences", Xu et al., ICLR 2025, arXiv 2410.06072.
                         Zero-shot: mean token log-likelihood divided by the standard
                         deviation, over the scales 1..tau', of the diversity entropy of the
                         sliding-window means of the log-likelihood series. Higher = more
                         AI (sign of the official code, not tuned here). OUR OWN
                         REIMPLEMENTATION in numpy from the formulas. An official
                         repository exists (github.com/TrustMedia-zju/Lastde_Detector,
                         `scoring_methods/fastMDE.py`, no licence declared): it was read
                         for the parameters, but its code is not used. `_selftest()`
                         reproduces the examples of its `DE`, `get_tau_scale_DE` and
                         `get_tau_multiscale_DE` docstrings (0.30103, the tau=2 and tau=3
                         series, [0.30103, 0, 0]); the value 0.9896 of the `calculate_DE`
                         docstring contradicts those and is not reproduced. Against the
                         official formula evaluated in torch on random series the score
                         agrees to 1e-5 at n=30 and n=200 and differs by 0.06% at n=511
                         (-50.26 here, -50.29 there): numpy float64 here, float32 there,
                         and the 10*n histogram intervals are narrow enough for rounding
                         to move a few cosine values across an edge. Only the plain Lastde
                         statistic is here, not Lastde++ (which samples from the model).
  diveye-lastde-<model>  The 10 DivEye features plus the Lastde score in the same
                         classifier (the DivEye paper reports DivEye as an auxiliary
                         signal for other detectors; this exact combination is ours).

The 10 DivEye features, in the order of the official code (FEATURE_NAMES):
  s_mean, s_std, s_var, s_skew, s_kurt   surprisal s_t = -log p(x_t | x_<t): mean, standard
                                         deviation, variance, skewness, excess kurtosis
                                         (scipy defaults: biased estimators, Fisher)
  d1_mean, d1_std                        first differences of the surprisal
  d2_var, d2_entropy, d2_autocorr        second differences of the log-likelihood: variance,
                                         entropy of a 20-bin density histogram
                                         (scipy.stats.entropy, which renormalises), lag-1
                                         autocorrelation (Pearson)
The task brief lists 9 statistics (variance, not standard deviation, of the first
differences; no separate standard deviation of the surprisal). The code has 10: s_std and
s_var are both present, and it uses the standard deviation of the first differences. For a
tree classifier the two sets carry the same information (std is a monotone function of
var). The dump adds an 11th column d1_var so that the 9 of the brief are all available:
s_mean, s_var, s_skew, s_kurt, d1_mean, d1_var, d2_var, d2_entropy, d2_autocorr.

Models (pinned revisions, HF_HOME=/tmp/isitai-bench/hf):
  gpt2          openai-community/gpt2 @ 607a30d, 124M parameters, model.safetensors
                548,105,171 bytes, MIT. The paper default ("recommended to be GPT-2").
  smollm2-135m  HuggingFaceTB/SmolLM2-135M @ 93efa2f, 135M parameters, model.safetensors
                269,060,552 bytes, Apache-2.0. UNVERIFIED VARIANT: not used by either
                paper; tried because it is half the size. It is NOT a multilingual model
                (English-centric training data), so it does not answer the French question.
                Only lastde-smollm2-135m was run; diveye-smollm2-135m and
                diveye-lastde-smollm2-135m were never run (same code path, untested).
Both scorers are English models. test_fr is scored out of their training language; no
multilingual scorer was run.

Deviations from the papers and the official code:
  - Truncation: first 512 tokens of the text (MAX_TOKENS), so 511 scored tokens. DivEye
    uses max_length=1024; Lastde tokenises the whole text (its datasets are cut to a few
    hundred tokens). A 1,500-word story of test_fiction is scored on about its first third.
  - No BOS token, as in both official codes: the first token is context only.
  - Classifier: the DivEye code trains xgboost.XGBClassifier(random_state=42,
    scale_pos_weight=n_neg/n_pos, max_depth=12, n_estimators=200, colsample_bytree=0.8,
    subsample=0.7, min_child_weight=5, gamma=1.0). xgboost is used with exactly these
    parameters (n_jobs=THREADS) when it is installed. It was NOT installed in the bench
    venv on 2026-11-12, so the numbers were produced with the fallback
    sklearn.ensemble.HistGradientBoostingClassifier(max_depth=12, max_iter=200,
    max_leaf_nodes=None, min_samples_leaf=5, max_features=0.8, early_stopping=False,
    random_state=42, class_weight="balanced"). Differences of the fallback: learning rate
    0.1 (xgboost default 0.3), features sub-sampled per split and not per tree, no row
    sub-sampling (subsample), no minimum loss reduction (gamma), features binned to 255
    levels. `CLASSIFIER` says which one ran; it is also written in MODEL.
  - Training data: the bench train split (4,000 RAID texts), not the corpora of the paper.
  - Short texts: the official DivEye code calls itself again, without end, on a text with
    fewer than 10 scored tokens. Here every statistic is computed when it is defined and
    set to 0 otherwise (fewer than 4 scored tokens: all zero; NaN from a constant series:
    0). An empty text gets all-zero features.
  - Lastde parameters: those of the official `get_lastde` for open-source scoring models:
    embedding dimension s=3, epsilon=10*n intervals on [-1, 1] (n = scored tokens),
    tau'=5, aggregation = standard deviation with n-1 in the denominator (torch.std).
    The paper's white-box setting scores with the generator itself or a large proxy
    (GPT-J, Llama-3); here the scorer is a fixed small model (black-box).
    Guards that the official code does not have: fewer than 8 scored tokens (no scale-5
    orbit pair) gives the denominator 1.0, which ranks such a text as MORE AI than
    longer texts (no bench row is that short: the minimum is 10 words); the denominator
    is floored at 1e-3.
  - Lastde depends on length by construction (epsilon = 10*n): on the same random series
    it gives about -27 at n=30, -39 at n=200, -50 at n=511. Longer texts score lower.
  - Sliding windows (`window_features`): WINDOW=100 scored tokens, STRIDE=50, cut from
    the series of the SAME full-context pass (a window is not re-scored alone). Neither
    paper defines windows: this is ours, for mixed human / AI inspection. The Lastde of a
    window uses epsilon=10*window length, so it is not on the scale of the full-text value.

Batching: one text per forward pass, no padding, so a score does not depend on the other
texts of the call. Only the log-probability of the observed token is kept. CPU, float32,
eval mode, no sampling: deterministic. Seeds: torch 0, classifier 42.

Artefacts (never in the repository):
  CACHE_DIR/surprisal_diversity/<variant>.joblib          the fitted classifier
  RESULTS_DIR/features/surprisal_diversity.<model>.train.npz   train features (from fit)
  RESULTS_DIR/features/surprisal_diversity.<variant>.timing.json   LM / feature / classifier
        seconds of the last run.py process (median per text over the batch-of-1 calls)
  other splits: written by surprisal_diversity_dump.py.
fit() never reads the saved classifier. By default it also recomputes the train features
(4,000 forward passes), so fit_seconds is the real cost. With the environment variable
SURPRISAL_DIVERSITY_REUSE_TRAIN=1 it reads the train feature file above when its ids match
the train split (same features, no LM pass): fit_seconds is then only the classifier
fit and must not be reported as the training cost. Used for the smoke runs only.
"""
from __future__ import annotations

import atexit
import json
import os
import time
import warnings

import numpy as np

from common import CACHE_DIR, RESULTS_DIR, THREADS

NAME = "surprisal_diversity"
NEEDS_TRAINING = True
BATCH_SIZE = 16

MAX_TOKENS = 512          # tokens fed to the model; MAX_TOKENS - 1 are scored (no BOS)
WINDOW = 100              # scored tokens per sliding window
STRIDE = 50
LASTDE_EMBED = 3          # s
LASTDE_EPS_PER_TOKEN = 10  # epsilon = 10 * n
LASTDE_TAU = 5            # tau'
_HIST_BINS = 20
_SEED = 0
_CLF_SEED = 42

FEATURE_NAMES = ("s_mean", "s_std", "s_var", "s_skew", "s_kurt", "d1_mean", "d1_std",
                 "d2_var", "d2_entropy", "d2_autocorr")
#: Columns of the dumps: the 10 official features, then d1_var, lastde, n scored tokens.
DUMP_COLUMNS = FEATURE_NAMES + ("d1_var", "lastde", "n_scored")

_MODELS = {
    "gpt2": ("openai-community/gpt2", "607a30d783dfa663caf39e06633721c8d4cfcd7e",
             "openai-community/gpt2 (124M parameters, model.safetensors 548,105,171 bytes, MIT)"),
    "smollm2-135m": ("HuggingFaceTB/SmolLM2-135M", "93efa2f097d58c2a74874c7e644dbc9b0cee75a2",
                     "HuggingFaceTB/SmolLM2-135M (135M parameters, model.safetensors "
                     "269,060,552 bytes, Apache-2.0; unverified variant, English-centric)"),
}
_loaded: dict = {}

FEATURES_DIR = os.path.join(RESULTS_DIR, "features")
MODEL_DIR = os.path.join(CACHE_DIR, "surprisal_diversity")


# ----------------------------------------------------------------------------- LM pass

def _load(key: str):
    if key not in _loaded:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.manual_seed(_SEED)
        torch.set_num_threads(THREADS)
        repo, rev, _ = _MODELS[key]
        tok = AutoTokenizer.from_pretrained(repo, revision=rev, use_fast=True)
        model = AutoModelForCausalLM.from_pretrained(repo, revision=rev, dtype=torch.float32)
        model.to("cpu").eval()
        _loaded[key] = (tok, model)
    return _loaded[key]


def token_logprobs(key: str, text: str) -> np.ndarray:
    """log p(x_t | x_<t) for t = 2..n of the first MAX_TOKENS tokens (float64, maybe empty)."""
    import torch
    tok, model = _load(key)
    ids = tok.encode(text, truncation=True, max_length=MAX_TOKENS, add_special_tokens=False)
    if len(ids) < 2:
        return np.zeros(0)
    x = torch.tensor([ids], dtype=torch.long, device="cpu")
    with torch.no_grad():
        logits = model(input_ids=x).logits[0, :-1, :].float()
        target = x[0, 1:]
        # log_softmax of the target only: logit - logsumexp
        lp = logits.gather(-1, target.unsqueeze(-1)).squeeze(-1) - torch.logsumexp(logits, dim=-1)
    return lp.numpy().astype(np.float64)


# ------------------------------------------------------------------------------ DivEye

def _fin(v) -> float:
    v = float(v)
    return v if np.isfinite(v) else 0.0


def diveye_features(ll: np.ndarray) -> list[float]:
    """The 10 features of IBM/diveye `diveye_compute`, in its order, from the token
    log-likelihoods. Undefined statistics are 0."""
    from scipy.stats import entropy, kurtosis, skew
    n = len(ll)
    if n < 4:
        return [0.0] * len(FEATURE_NAMES)
    s = -ll
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore")      # scipy warns on a (nearly) constant series
        d1 = np.diff(s)
        d2 = np.diff(np.diff(ll))
        hist = np.histogram(d2, bins=_HIST_BINS, density=True)[0]
        ent = entropy(hist) if np.all(np.isfinite(hist)) and hist.sum() > 0 else 0.0
        if len(d2) > 2 and np.std(d2[:-1]) > 0 and np.std(d2[1:]) > 0:
            ac = np.corrcoef(d2[:-1], d2[1:])[0, 1]
        else:
            ac = 0.0
        out = [np.mean(s), np.std(s), np.var(s), skew(s), kurtosis(s),
               np.mean(d1), np.std(d1), np.var(d2), ent, ac]
    return [_fin(v) for v in out]


# ------------------------------------------------------------------------------ Lastde

def diversity_entropy(x: np.ndarray, embed: int, epsilon: int) -> float:
    """Diversity entropy of a series: cosine similarity of consecutive `embed`-dimensional
    orbits, histogram on [-1, 1] in `epsilon` equal intervals, Shannon entropy divided by
    ln(epsilon). 0 when there is no orbit pair."""
    if len(x) < embed + 1 or epsilon < 2:
        return 0.0
    orbits = np.lib.stride_tricks.sliding_window_view(x, embed)
    a, b = orbits[:-1], orbits[1:]
    # same epsilon (1e-8) as torch cosine_similarity
    den = np.maximum(np.linalg.norm(a, axis=1), 1e-8) * np.maximum(np.linalg.norm(b, axis=1), 1e-8)
    cos = np.clip((a * b).sum(axis=1) / den, -1.0, 1.0)
    idx = np.minimum(((cos + 1.0) / 2.0 * epsilon).astype(np.int64), epsilon - 1)
    counts = np.bincount(idx, minlength=epsilon).astype(np.float64)
    p = counts[counts > 0] / counts.sum()
    return float(-(p * np.log(p)).sum() / np.log(epsilon))


def multiscale_de_std(x: np.ndarray, embed: int, epsilon: int, tau_prime: int) -> float:
    """Standard deviation (n-1) over tau = 1..tau_prime of the diversity entropy of the
    sliding-window means of length tau."""
    des = []
    for tau in range(1, tau_prime + 1):
        if len(x) < tau:
            des.append(0.0)
            continue
        coarse = x if tau == 1 else np.lib.stride_tricks.sliding_window_view(x, tau).mean(axis=1)
        des.append(diversity_entropy(coarse, embed, epsilon))
    return float(np.std(des, ddof=1))


def lastde_score(ll: np.ndarray) -> float:
    """Lastde: mean log-likelihood / std of the multiscale diversity entropy."""
    n = len(ll)
    if n == 0:
        return 0.0
    mean_ll = float(np.mean(ll))
    if n < LASTDE_TAU + LASTDE_EMBED:
        return mean_ll          # denominator 1.0: no orbit pair at the largest scale
    den = multiscale_de_std(ll, LASTDE_EMBED, LASTDE_EPS_PER_TOKEN * n, LASTDE_TAU)
    return _fin(mean_ll / max(den, 1e-3))


def _selftest() -> None:
    """The worked examples of the official fastMDE.py docstrings."""
    x = np.array([1, 2, 13, 7, 9, 5, 4], dtype=float)
    assert abs(diversity_entropy(x, 3, 10) - 0.30102999566398114) < 1e-6
    c2 = np.lib.stride_tricks.sliding_window_view(x, 2).mean(axis=1)
    assert np.allclose(c2, [1.5, 7.5, 10.0, 8.0, 7.0, 4.5])
    assert abs(diversity_entropy(c2, 3, 10)) < 1e-9
    c3 = np.lib.stride_tricks.sliding_window_view(x, 3).mean(axis=1)
    assert abs(diversity_entropy(c3, 3, 10)) < 1e-9
    assert abs(multiscale_de_std(x, 3, 10, 3) - np.std([0.30102999566398114, 0, 0], ddof=1)) < 1e-6


# ------------------------------------------------------------------- features per text

def dump_row(ll: np.ndarray) -> list[float]:
    """DUMP_COLUMNS for one log-likelihood series."""
    f = diveye_features(ll)
    return f + [f[6] ** 2, lastde_score(ll), float(len(ll))]


def window_features(ll: np.ndarray, window: int = WINDOW, stride: int = STRIDE) -> list[dict]:
    """DUMP_COLUMNS for every sliding window of `window` scored tokens. A text shorter than
    one window gives one window (the whole text). `start` and `end` are indices in the
    scored-token series (token t of the text is scored token t-1)."""
    n = len(ll)
    if n == 0:
        return []
    starts = [0] if n <= window else list(range(0, n - window + 1, stride))
    if n > window and starts[-1] + window < n:
        starts.append(n - window)          # last window flush with the end
    out = []
    for a in starts:
        b = min(n, a + window)
        out.append({"start": a, "end": b, "features": dump_row(ll[a:b])})
    return out


# -------------------------------------------------------------------------- classifier

def _make_classifier(y: np.ndarray):
    try:
        import xgboost as xgb
    except Exception:
        from sklearn.ensemble import HistGradientBoostingClassifier
        clf = HistGradientBoostingClassifier(
            max_depth=12, max_iter=200, max_leaf_nodes=None, min_samples_leaf=5,
            max_features=0.8, early_stopping=False, random_state=_CLF_SEED,
            class_weight="balanced")
        return clf, "sklearn HistGradientBoostingClassifier (fallback, xgboost not installed)"
    pos = float(np.sum(y))
    clf = xgb.XGBClassifier(
        random_state=_CLF_SEED, scale_pos_weight=(len(y) - pos) / max(pos, 1.0), max_depth=12,
        n_estimators=200, colsample_bytree=0.8, subsample=0.7, min_child_weight=5, gamma=1.0,
        n_jobs=THREADS)
    return clf, f"xgboost {xgb.__version__} XGBClassifier (parameters of IBM/diveye)"


class _Timing:
    def __init__(self, label: str):
        self.label = label
        self.calls: list[tuple[int, float, float, float]] = []   # n, lm, feat, clf
        atexit.register(self.write)

    def add(self, n: int, lm: float, feat: float, clf: float) -> None:
        self.calls.append((n, lm, feat, clf))

    def summary(self) -> dict:
        single = [c for c in self.calls if c[0] == 1]
        tot = [sum(c[i] for c in self.calls) for i in range(4)]

        def med(i):
            return float(np.median([c[i] for c in single])) if single else None
        return {
            "algo": self.label, "threads": THREADS, "max_tokens": MAX_TOKENS,
            "n_texts_all_calls": int(tot[0]),
            "seconds_lm_total": tot[1], "seconds_features_total": tot[2],
            "seconds_classifier_total": tot[3],
            "batch1_calls": len(single),
            "seconds_lm_per_text_median": med(1),
            "seconds_features_per_text_median": med(2),
            "seconds_classifier_per_text_median": med(3),
            "note": "features = the 10 DivEye statistics + Lastde; batch-of-1 medians "
                    "include the warm-up call; classifier time is per call",
        }

    def write(self) -> None:
        if not self.calls:
            return
        try:
            os.makedirs(FEATURES_DIR, exist_ok=True)
            path = os.path.join(FEATURES_DIR, f"surprisal_diversity.{self.label}.timing.json")
            tmp = f"{path}.{os.getpid()}.tmp"
            with open(tmp, "w") as f:
                json.dump(self.summary(), f, indent=1)
            os.replace(tmp, path)
        except Exception:
            pass


class Detector:
    def __init__(self, method: str, model_key: str):
        assert method in ("diveye", "lastde", "diveye-lastde")
        self.method = method
        self.model_key = model_key
        self.label = f"{method}-{model_key}"
        self.NAME = f"surprisal_diversity.{self.label}"
        self.NEEDS_TRAINING = method != "lastde"
        self.BATCH_SIZE = BATCH_SIZE
        self.CLASSIFIER = "none"
        self.clf = None
        self.TRAIN_FEATURES_REUSED = False
        self.timing = _Timing(self.label)
        self._set_model()

    def _set_model(self) -> None:
        lm = _MODELS[self.model_key][2] + "; pretrained LM only, not trained on any detection corpus"
        if self.method == "lastde":
            self.MODEL = lm + "; zero-shot Lastde statistic (own reimplementation), no fitted part"
        else:
            reuse = ("; TRAIN FEATURES REUSED FROM DISK: fit_seconds is the classifier fit only"
                     if self.TRAIN_FEATURES_REUSED else "")
            self.MODEL = lm + (f"; + {self.CLASSIFIER} on {len(self._cols())} features, fitted on "
                               f"the bench train split{reuse}")

    def _cols(self) -> list[int]:
        cols = list(range(len(FEATURE_NAMES)))
        if self.method == "diveye-lastde":
            cols.append(DUMP_COLUMNS.index("lastde"))
        return cols

    def _rows(self, texts: list[str]) -> tuple[np.ndarray, float, float]:
        lm = feat = 0.0
        rows = []
        for t in texts:
            t0 = time.perf_counter()
            ll = token_logprobs(self.model_key, t)
            t1 = time.perf_counter()
            rows.append(dump_row(ll))
            lm += t1 - t0
            feat += time.perf_counter() - t1
        return np.asarray(rows, dtype=np.float64).reshape(len(texts), len(DUMP_COLUMNS)), lm, feat

    def fit(self, rows: list[dict]) -> None:
        import joblib
        y = np.asarray([r["label"] for r in rows], dtype=np.int64)
        ids = np.asarray([r["id"] for r in rows])
        path = os.path.join(FEATURES_DIR, f"surprisal_diversity.{self.model_key}.train.npz")
        x = None
        if os.environ.get("SURPRISAL_DIVERSITY_REUSE_TRAIN") == "1" and os.path.exists(path):
            z = np.load(path, allow_pickle=False)
            if (z["features"].shape == (len(rows), len(DUMP_COLUMNS))
                    and list(z["columns"]) == list(DUMP_COLUMNS) and np.array_equal(z["ids"], ids)):
                x = z["features"]
                self.TRAIN_FEATURES_REUSED = True
        if x is None:
            x, _, _ = self._rows([r["text"] for r in rows])
            os.makedirs(FEATURES_DIR, exist_ok=True)
            tmp = f"{path}.{os.getpid()}.tmp.npz"
            np.savez_compressed(tmp, ids=ids, labels=y, features=x, columns=np.asarray(DUMP_COLUMNS))
            os.replace(tmp, path)
        self.clf, self.CLASSIFIER = _make_classifier(y)
        self.clf.fit(x[:, self._cols()], y)
        self._set_model()
        os.makedirs(MODEL_DIR, exist_ok=True)
        joblib.dump({"clf": self.clf, "columns": [DUMP_COLUMNS[i] for i in self._cols()],
                     "classifier": self.CLASSIFIER, "model": self.MODEL,
                     "max_tokens": MAX_TOKENS, "n_train": len(rows)},
                    os.path.join(MODEL_DIR, f"{self.label}.joblib"))

    def score(self, texts: list[str]) -> list[float]:
        x, lm, feat = self._rows(texts)
        t0 = time.perf_counter()
        if self.method == "lastde":
            out = x[:, DUMP_COLUMNS.index("lastde")].tolist()
        else:
            if self.clf is None:
                raise RuntimeError("fit() must be called first")
            out = self.clf.predict_proba(x[:, self._cols()])[:, 1].tolist()
        self.timing.add(len(texts), lm, feat, time.perf_counter() - t0)
        return out


_selftest()

MODEL = _MODELS["gpt2"][2] + "; + gradient-boosted trees on the 10 DivEye features (variant diveye-gpt2)"

VARIANTS = {
    f"{method}-{key}": (lambda m=method, k=key: Detector(m, k))
    for key in _MODELS for method in ("diveye", "lastde", "diveye-lastde")
}

_default: Detector | None = None


def _get_default() -> Detector:
    global _default
    if _default is None:
        _default = Detector("diveye", "gpt2")
    return _default


def fit(rows: list[dict]) -> None:
    _get_default().fit(rows)


def score(texts: list[str]) -> list[float]:
    return _get_default().score(texts)
