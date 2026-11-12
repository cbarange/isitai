"""Hand-crafted stylometric features and a logistic regression.

  run.py --algo stylometry_lr --variant full        --split all
  run.py --algo stylometry_lr --variant lang-indep  --split all
  run.py --algo stylometry_lr --variant full-nolayout        --split all
  run.py --algo stylometry_lr --variant lang-indep-nolayout  --split all

No neural model, no tokenizer file: counts over the text, a standardisation, a dot product.

Variants
--------
full        every feature below (language-independent ones + the English ones).
lang-indep  only the features whose DEFINITION uses no word list and no language rule:
            sentence and word length statistics, lexical diversity, punctuation and
            layout profile, repetition, character-based readability. Fitted on the same
            English train split: "language-independent" describes the features, not the
            training data. Their distributions still differ between languages (French
            words are longer, French puts a space before ; : ! ?), so a threshold fixed on
            English is not expected to transfer as is.

full-nolayout, lang-indep-nolayout
            the same two feature sets made blind to line breaks: every run of whitespace
            is replaced by one space before any feature is computed, and the three layout
            features (newline_rate, para_len_mean_log, para_single_sent_frac) are dropped.
            Reason: in RAID (the train and test splits) NO human text contains a blank
            line, while 20% to 84% of the AI texts do, depending on the domain (measured
            on train). That is how the corpus was collected, not a property of human
            writing; with layout features the model mostly learns "has paragraphs = AI"
            (para_single_sent_frac alone: train AUROC 0.91) and the test score is
            inflated. The -nolayout variants are the ones to read as stylometry.

What this is, and is not
------------------------
There is no single paper to reproduce: this is the classical "stylometry + linear model"
baseline of the detection literature, assembled from the sources below. It is NOT a
reimplementation of StoryScope (arXiv 2604.03136), whose 304 discourse-level narrative
features are extracted by an LLM from about 5,000-word stories; nothing here reads plot,
characters or narration.

Feature groups and their sources
- Sentence-length mean, standard deviation, coefficient of variation ("burstiness" as the
  term is used for AI-text detection) and the Goh-Barabasi burstiness coefficient
  B = (sd - mean) / (sd + mean) (Goh & Barabasi, EPL 81, 2008).
- Type-token ratio and length-corrected variants, computed on the first 400 word tokens:
  TTR of the first 100 tokens, MATTR with a 50-token window (Covington & McFall 2010),
  Guiraud's root TTR (1954), Herdan's C (1960), Maas a^2 (1972), Yule's K (1944), hapax
  and dis-legomena ratios. No MTLD, no HD-D.
- Punctuation, case, digit and layout rates: the usual stylometric profile, as in the
  feature sets of Frohling & Zubiaga (PeerJ CS 2021), Kumarage et al. ("Stylometric
  detection of AI-generated text in Twitter timelines", arXiv 2303.03697) and Herbold et
  al. (Sci. Rep. 2023). Those papers were not re-read for this file and their exact
  feature lists are not reproduced; they are cited as the family this belongs to.
- Readability: Automated Readability Index (Smith & Senter 1967), Coleman-Liau (1975) and
  LIX (Bjornsson 1968) are character-based and kept in both variants. Flesch Reading Ease
  (1948), Flesch-Kincaid grade (1975), Gunning Fog (1952) and SMOG (McLaughlin 1969) need
  syllables and are English-only; syllables are counted with a vowel-group heuristic, not
  a pronunciation dictionary, so the absolute values differ a little from textstat.
- Repetition: share of repeated word bigrams and trigrams, share of the most frequent
  word, repeated sentence openers, character entropy.
- Function words (English): the 318-word English stop-word list shipped with scikit-learn
  (`sklearn.feature_extraction.text.ENGLISH_STOP_WORDS`, from the Glasgow Information
  Retrieval Group list; BSD-3-Clause package). One relative frequency per word, for the
  words present in at least 3% of the train texts (chosen on train), plus the total rate.
- "AI vocabulary" (English): the 407 "style" excess words of Kobak et al. (Science
  Advances 2025, arXiv 2406.07016), see stylometry_lr_words.py (MIT). Two features: token
  rate and type rate. Deviation from the paper: Kobak et al. measure the excess frequency
  of each word in a corpus over years; they do not classify single documents. The list
  comes from PubMed abstracts (2013-2024, biomedical register) and contains common words
  (across, between, both); here it is only a lexicon feature.

Parameters and deviations
- Truncation: the first 2,000 whitespace-separated words of the text (MAX_WORDS); the rest
  is ignored. Lexical-diversity and n-gram repetition features use the first 400 word
  tokens only (DIV_TOKENS).
- Length: there is no word-count feature, but the features are NOT all length-free.
  (a) About 90% of the train texts have fewer than 400 words (median 224), so the
  diversity and repetition features are computed on a prefix whose size is the text
  length, and Herdan's C, Maas, root TTR, Yule's K and the n-gram repetition rates vary
  with it. Measured: Spearman correlation between score and n_words on the train human
  texts is -0.02 (full-nolayout) and -0.14 (lang-indep-nolayout). A 100-token prefix was
  tried: cross-validated train AUROC 0.867 instead of 0.874 (full-nolayout) and 0.833
  instead of 0.848 (lang-indep-nolayout), with correlations of +0.09 and +0.04; 400 was
  kept on the cross-validation figure. (b) In the two variants WITH layout,
  para_len_mean_log equals log(1 + word count) for a text without a blank line, which is
  every RAID human text: those variants carry a length feature for humans.
- Tokenisation: plain regular expressions without lookaround or backreference (portable
  to the Rust `regex` crate), no NLTK or spaCy. Words are runs of Unicode letters with
  inner apostrophes or hyphens. Sentences end at . ! ? or an ellipsis followed by
  whitespace, or at a line break; abbreviations ("Dr. Smith") are cut wrongly.
- Model: StandardScaler, z-scores clipped to [-5, 5] (the train split is English RAID;
  French or fiction inputs fall far outside it), L2 logistic regression (lbfgs). C is
  chosen among 0.003, 0.01, 0.03, 0.1, 0.3, 1 by 5-fold stratified cross-validated AUROC on
  the train split only (seed 0). The folds are not grouped by source document (the rows
  carry no document id), so the human text and the generation of one prompt can sit in
  different folds; this only affects the choice of C.
- Score: the logit (decision function), not the probability, to avoid ties at 0 and 1.
- Deterministic: no sampling apart from the seeded folds; feature order is fixed by
  tuples.

At fit time the module writes the ranked features (standardised coefficient and
univariate train AUROC of each feature) to
/tmp/isitai-bench/cache/stylometry_lr/<variant>.features.json.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter

import numpy as np

from common import CACHE_DIR

try:  # run.py imports this file as algos.stylometry_lr
    from .stylometry_lr_words import EXCESS_STYLE_WORDS
except ImportError:  # direct import with algos/ on the path
    from stylometry_lr_words import EXCESS_STYLE_WORDS

NAME = "stylometry_lr"
NEEDS_TRAINING = True
MODEL = ("none (logistic regression on hand-crafted stylometric features; weights, means "
         "and scales well under 10 kB, plus two word lists of about 6 kB)")

MAX_WORDS = 2000      # truncation: first 2,000 whitespace-separated words
DIV_TOKENS = 400      # lexical diversity and n-gram repetition: first 400 word tokens
MATTR_WINDOW = 50
TTR_WINDOW = 100
MIN_DF = 0.03         # a function word is kept when present in >= 3% of the train texts
CLIP_Z = 5.0
C_GRID = (0.003, 0.01, 0.03, 0.1, 0.3, 1.0)
SEED = 0

_WORD_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
_SENT_SPLIT_RE = re.compile(r"[.!?…]+[\"'”’)\]]*\s+|\n+")
_PARA_SPLIT_RE = re.compile(r"\n\s*\n+")
_VOWEL_GROUP_RE = re.compile(r"[aeiouy]+")
_TRUNC_RE = re.compile(r"\S+")

# (feature name, characters counted); rate per 100 words
_PUNCT = (
    ("p_comma", ","),
    ("p_period", "."),
    ("p_semicolon", ";"),
    ("p_colon", ":"),
    ("p_exclam", "!"),
    ("p_question", "?"),
    ("p_dash", "—–"),
    ("p_hyphen", "-"),
    ("p_dquote", "\"“”«»"),
    ("p_squote", "'’‘"),
    ("p_paren", "()[]"),
    ("p_ellipsis", "…"),
    ("p_slash", "/"),
    ("p_markdown", "*#`_|"),
    ("p_other", "&%$@+=<>~^"),
)


def _function_words() -> tuple[str, ...]:
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    return tuple(sorted(ENGLISH_STOP_WORDS))


FUNCTION_WORDS = _function_words()
_FW_INDEX = {w: i for i, w in enumerate(FUNCTION_WORDS)}
_EXCESS = frozenset(EXCESS_STYLE_WORDS)   # membership tests only, never iterated

LANG_INDEP_FEATURES = (
    "sent_len_mean", "sent_len_sd", "sent_len_cv", "sent_burstiness", "sent_len_adjdiff",
    "sent_short_frac", "sent_long_frac", "sent_question_frac", "sent_exclam_frac",
    "word_len_mean", "word_len_sd", "word_long_frac", "word_short_frac",
    "ttr_100", "mattr_50", "root_ttr", "herdan_c", "maas_a2", "yule_k", "hapax_ratio",
    "dis_ratio",
    *(name for name, _ in _PUNCT),
    "digit_ratio", "upper_ratio", "titlecase_frac", "allcaps_frac", "newline_rate",
    "para_len_mean_log", "para_single_sent_frac",
    "rep_bigram", "rep_trigram", "top_word_share", "sent_opener_repeat",
    "sent_opener_distinct", "char_entropy",
    "ari", "coleman_liau", "lix",
)
ENGLISH_SCALAR_FEATURES = (
    "syll_per_word", "polysyll_frac", "flesch_ease", "flesch_kincaid", "gunning_fog", "smog",
    "fw_total", "contraction_rate", "excess_token_rate", "excess_type_rate",
)
FW_FEATURES = tuple(f"fw:{w}" for w in FUNCTION_WORDS)
ALL_FEATURES = LANG_INDEP_FEATURES + ENGLISH_SCALAR_FEATURES + FW_FEATURES
_N_BASE = len(LANG_INDEP_FEATURES) + len(ENGLISH_SCALAR_FEATURES)


def _truncate(text: str) -> str:
    n = 0
    for m in _TRUNC_RE.finditer(text):
        n += 1
        if n == MAX_WORDS:
            return text[:m.end()]
    return text


def _syllables(word: str) -> int:
    """English vowel-group heuristic (silent final e removed)."""
    n = len(_VOWEL_GROUP_RE.findall(word))
    if word.endswith("e") and not word.endswith("le") and n > 1:
        n -= 1
    return max(1, n)


def _mean_sd(values: list[int]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    return m, math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def _clip(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _features_one(text: str, layout: bool = True) -> list[float]:
    text = _truncate(text)
    if not layout:
        text = " ".join(text.split())
    n_chars = max(1, len(text))
    raw_words = _WORD_RE.findall(text)
    words = [w.lower() for w in raw_words]
    nw = max(1, len(words))
    f: dict[str, float] = {}

    # sentences
    sent_lens: list[int] = []
    openers: list[str] = []
    for chunk in _SENT_SPLIT_RE.split(text):
        sw = _WORD_RE.findall(chunk)
        if sw:
            sent_lens.append(len(sw))
            openers.append(sw[0].lower())
    ns = max(1, len(sent_lens))
    m, sd = _mean_sd(sent_lens)
    f["sent_len_mean"] = min(m, 100.0)
    f["sent_len_sd"] = min(sd, 100.0)
    f["sent_len_cv"] = sd / m if m > 0 else 0.0
    f["sent_burstiness"] = (sd - m) / (sd + m) if sd + m > 0 else -1.0
    if len(sent_lens) > 1 and m > 0:
        f["sent_len_adjdiff"] = (sum(abs(a - b) for a, b in zip(sent_lens, sent_lens[1:]))
                                 / (len(sent_lens) - 1) / m)
    else:
        f["sent_len_adjdiff"] = 0.0
    f["sent_short_frac"] = sum(1 for v in sent_lens if v <= 5) / ns
    f["sent_long_frac"] = sum(1 for v in sent_lens if v >= 30) / ns
    f["sent_question_frac"] = min(1.0, text.count("?") / ns)
    f["sent_exclam_frac"] = min(1.0, text.count("!") / ns)
    if len(openers) > 1:
        f["sent_opener_repeat"] = (sum(1 for a, b in zip(openers, openers[1:]) if a == b)
                                   / (len(openers) - 1))
    else:
        f["sent_opener_repeat"] = 0.0
    head = openers[:20]
    f["sent_opener_distinct"] = len(set(head)) / len(head) if head else 1.0

    # words
    wl = [len(w) for w in words]
    m_w, sd_w = _mean_sd(wl)
    f["word_len_mean"] = m_w
    f["word_len_sd"] = sd_w
    n_long = sum(1 for v in wl if v >= 7)
    f["word_long_frac"] = n_long / nw
    f["word_short_frac"] = sum(1 for v in wl if v <= 3) / nw

    # lexical diversity on a fixed prefix
    div = words[:DIV_TOKENS]
    n = len(div)
    counts = Counter(div)
    v = len(counts)
    first = div[:TTR_WINDOW]
    f["ttr_100"] = len(set(first)) / len(first) if first else 1.0
    if n >= MATTR_WINDOW:
        window = Counter(div[:MATTR_WINDOW])
        total = len(window)
        for i in range(MATTR_WINDOW, n):
            out = div[i - MATTR_WINDOW]
            window[out] -= 1
            if window[out] == 0:
                del window[out]
            window[div[i]] += 1
            total += len(window)
        f["mattr_50"] = total / (n - MATTR_WINDOW + 1) / MATTR_WINDOW
    else:
        f["mattr_50"] = v / n if n else 1.0
    f["root_ttr"] = v / math.sqrt(n) if n else 0.0
    if n > 1 and v > 0:
        log_n = math.log(n)
        f["herdan_c"] = math.log(v) / log_n
        f["maas_a2"] = (log_n - math.log(v)) / (log_n * log_n)
    else:
        f["herdan_c"] = 1.0
        f["maas_a2"] = 0.0
    if n > 1:
        s2 = sum(c * c for c in counts.values())
        f["yule_k"] = min(1000.0, 1e4 * (s2 - n) / (n * n))
    else:
        f["yule_k"] = 0.0
    f["hapax_ratio"] = sum(1 for c in counts.values() if c == 1) / v if v else 1.0
    f["dis_ratio"] = sum(1 for c in counts.values() if c == 2) / v if v else 0.0

    # repetition
    for name, k in (("rep_bigram", 2), ("rep_trigram", 3)):
        total = n - k + 1
        if total > 0:
            grams = set(zip(*(div[i:] for i in range(k))))
            f[name] = 1.0 - len(grams) / total
        else:
            f[name] = 0.0
    f["top_word_share"] = max(counts.values()) / n if n else 0.0
    head_chars = text[:2000].lower()
    cc = Counter(head_chars)
    hc = len(head_chars)
    f["char_entropy"] = -sum(c / hc * math.log2(c / hc) for c in cc.values()) if hc else 0.0

    # punctuation, case, layout
    per100 = 100.0 / nw
    for name, chars in _PUNCT:
        f[name] = min(100.0, sum(text.count(ch) for ch in chars) * per100)
    n_letters = 0
    n_upper = 0
    n_digit = 0
    for ch in text:
        if ch.isalpha():
            n_letters += 1
            if ch.isupper():
                n_upper += 1
        elif ch.isdigit():
            n_digit += 1
    f["digit_ratio"] = n_digit / n_chars
    f["upper_ratio"] = n_upper / n_letters if n_letters else 0.0
    f["titlecase_frac"] = sum(1 for w in raw_words if w[0].isupper() and not w.isupper()) / nw
    f["allcaps_frac"] = sum(1 for w in raw_words if len(w) > 1 and w.isupper()) / nw
    f["newline_rate"] = min(100.0, text.count("\n") * per100)
    paras = [p for p in _PARA_SPLIT_RE.split(text) if _WORD_RE.search(p)]
    np_ = max(1, len(paras))
    f["para_len_mean_log"] = math.log1p(nw / np_)
    f["para_single_sent_frac"] = min(1.0, np_ / ns)

    # readability, character-based
    letters_per_word = sum(wl) / nw
    words_per_sent = min(nw / ns, 100.0)
    f["ari"] = _clip(4.71 * letters_per_word + 0.5 * words_per_sent - 21.43, -5.0, 40.0)
    f["coleman_liau"] = _clip(0.0588 * (100.0 * letters_per_word)
                              - 0.296 * (100.0 * ns / nw) - 15.8, -5.0, 40.0)
    f["lix"] = _clip(words_per_sent + 100.0 * n_long / nw, 0.0, 150.0)

    # English only: syllables
    syl = [_syllables(w) for w in words]
    n_syl = sum(syl)
    n_poly = sum(1 for s in syl if s >= 3)
    spw = n_syl / nw
    f["syll_per_word"] = spw
    f["polysyll_frac"] = n_poly / nw
    f["flesch_ease"] = _clip(206.835 - 1.015 * words_per_sent - 84.6 * spw, -50.0, 130.0)
    f["flesch_kincaid"] = _clip(0.39 * words_per_sent + 11.8 * spw - 15.59, -5.0, 40.0)
    f["gunning_fog"] = _clip(0.4 * (words_per_sent + 100.0 * n_poly / nw), 0.0, 60.0)
    f["smog"] = _clip(1.043 * math.sqrt(n_poly * 30.0 / ns) + 3.1291, 0.0, 40.0)

    # English only: function words, contractions, excess vocabulary
    all_counts = Counter(words)
    fw = [0.0] * len(FUNCTION_WORDS)
    fw_total = 0
    for w, c in all_counts.items():
        i = _FW_INDEX.get(w)
        if i is not None:
            fw[i] = c / nw
            fw_total += c
    f["fw_total"] = fw_total / nw
    f["contraction_rate"] = sum(c for w, c in all_counts.items()
                                if "'" in w or "’" in w) / nw
    ex_tokens = 0
    ex_types = 0
    for w, c in all_counts.items():
        if w in _EXCESS:
            ex_tokens += c
            ex_types += 1
    f["excess_token_rate"] = ex_tokens / nw
    f["excess_type_rate"] = ex_types / max(1, len(all_counts))

    row = [f[name] for name in LANG_INDEP_FEATURES]
    row += [f[name] for name in ENGLISH_SCALAR_FEATURES]
    row += fw
    return row


LAYOUT_FEATURES = ("newline_rate", "para_len_mean_log", "para_single_sent_frac")


def features(texts: list[str], layout: bool = True) -> np.ndarray:
    """One row per text, columns in the order of ALL_FEATURES. layout=False: whitespace
    runs become one space first (the layout columns are then constant)."""
    if not texts:
        return np.zeros((0, len(ALL_FEATURES)))
    x = np.asarray([_features_one(t, layout) for t in texts], dtype=float)
    return np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)


def _auroc(scores: np.ndarray, y: np.ndarray) -> float:
    from scipy.stats import rankdata
    r = rankdata(scores)
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n0 == 0 or n1 == 0:
        return float("nan")
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n0 * n1))


class Detector:
    NEEDS_TRAINING = True
    BATCH_SIZE = 64

    def __init__(self, variant: str):
        self.variant = variant
        self.layout = not variant.endswith("-nolayout")
        self.lang_indep = variant.startswith("lang-indep")
        self.NAME = f"stylometry_lr.{variant}"
        self.MODEL = MODEL
        self.columns: np.ndarray | None = None
        self.names: tuple[str, ...] = ()
        self.mean = self.scale = self.coef = None
        self.intercept = 0.0
        self.c = None
        self.cv_auroc: dict[str, float] = {}

    def _z(self, x: np.ndarray) -> np.ndarray:
        return np.clip((x[:, self.columns] - self.mean) / self.scale, -CLIP_Z, CLIP_Z)

    def fit(self, rows: list[dict]) -> None:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold

        x = features([r["text"] for r in rows], self.layout)
        y = np.asarray([int(r["label"]) for r in rows])

        if self.lang_indep:
            cols = list(range(len(LANG_INDEP_FEATURES)))
        else:
            df = (x[:, _N_BASE:] > 0).mean(axis=0)
            cols = list(range(_N_BASE)) + [_N_BASE + i for i in np.flatnonzero(df >= MIN_DF)]
        if not self.layout:
            cols = [i for i in cols if ALL_FEATURES[i] not in LAYOUT_FEATURES]
        self.columns = np.asarray(cols)
        self.names = tuple(ALL_FEATURES[i] for i in cols)

        def standardise(xtr):
            mean = xtr.mean(axis=0)
            scale = xtr.std(axis=0)
            scale[scale < 1e-12] = 1.0
            return mean, scale

        def model(c):
            return LogisticRegression(C=c, max_iter=5000, tol=1e-6, random_state=SEED)

        xs = x[:, self.columns]
        folds = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(xs, y))
        best_c, best = None, -1.0
        for c in C_GRID:
            aucs = []
            for tr, va in folds:
                mean, scale = standardise(xs[tr])
                ztr = np.clip((xs[tr] - mean) / scale, -CLIP_Z, CLIP_Z)
                zva = np.clip((xs[va] - mean) / scale, -CLIP_Z, CLIP_Z)
                clf = model(c).fit(ztr, y[tr])
                aucs.append(_auroc(clf.decision_function(zva), y[va]))
            auc = float(np.mean(aucs))
            self.cv_auroc[str(c)] = auc
            if auc > best + 1e-4:      # ties go to the stronger regularisation
                best_c, best = c, auc
        self.c = best_c

        self.mean, self.scale = standardise(xs)
        z = self._z(x)
        clf = model(self.c).fit(z, y)
        self.coef = clf.coef_[0].copy()
        self.intercept = float(clf.intercept_[0])
        self._dump(z, y)

    def _dump(self, z: np.ndarray, y: np.ndarray) -> None:
        feats = []
        for j, name in enumerate(self.names):
            feats.append({
                "feature": name,
                "coef_std": float(self.coef[j]),
                "train_auroc": _auroc(z[:, j], y),
                "train_mean_human": float((z[y == 0, j] * self.scale[j] + self.mean[j]).mean()),
                "train_mean_ai": float((z[y == 1, j] * self.scale[j] + self.mean[j]).mean()),
            })
        feats.sort(key=lambda d: -abs(d["coef_std"]))
        out = {"variant": self.variant, "n_features": len(self.names), "C": self.c,
               "cv_auroc_by_C": self.cv_auroc, "intercept": self.intercept,
               "train_auroc_fitted": _auroc(z @ self.coef + self.intercept, y),
               "note": "coef_std: coefficient on the standardised, clipped feature; positive "
                       "pushes towards AI. train_auroc: AUROC of the feature alone on train "
                       "(under 0.5 means higher for humans). train_mean_*: on clipped values.",
               "features": feats}
        directory = os.path.join(CACHE_DIR, "stylometry_lr")
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{self.variant}.features.json")
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as fh:
            json.dump(out, fh, indent=1)
        os.replace(tmp, path)

    def score(self, texts: list[str]) -> list[float]:
        if self.coef is None:
            raise RuntimeError("fit() first")
        return (self._z(features(texts, self.layout)) @ self.coef + self.intercept).tolist()


VARIANTS = {
    "full": lambda: Detector("full"),
    "lang-indep": lambda: Detector("lang-indep"),
    "full-nolayout": lambda: Detector("full-nolayout"),
    "lang-indep-nolayout": lambda: Detector("lang-indep-nolayout"),
}

# `run.py --algo stylometry_lr` without --variant runs full-nolayout: the variants with
# layout features mostly measure a blank-line artefact of RAID (see the docstring).
_default = Detector("full-nolayout")
fit = _default.fit
score = _default.score
