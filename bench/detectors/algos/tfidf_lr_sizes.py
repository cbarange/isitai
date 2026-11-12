"""Model size as a function of vocabulary size, with a 5-fold cross-validation on the
TRAIN split only (no test split is read). Writes /tmp/isitai-bench/cache/tfidf_lr/sizes.json.

  /tmp/isitai-bench/venv/bin/python algos/tfidf_lr_sizes.py

Caveats: the vocabulary and the idf are computed on the whole train split before the
folds (unsupervised, labels unused); folds are stratified by label, not grouped by RAID
source document, so a human text and the generation of the same prompt can sit in
different folds. The AUROC here is optimistic and only ranks settings.
"""
from __future__ import annotations

import gzip
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load_split  # noqa: E402
from evaluate import auroc  # noqa: E402
from algos import tfidf_lr as m  # noqa: E402

from sklearn.feature_extraction.text import CountVectorizer, HashingVectorizer, TfidfTransformer  # noqa: E402
from sklearn.model_selection import StratifiedKFold  # noqa: E402

rows = load_split("train")
texts = m.cut([r["text"] for r in rows])
y = np.array([r["label"] for r in rows])
folds = list(StratifiedKFold(5, shuffle=True, random_state=0).split(texts, y))


def cv(x, kind="lr", c=None) -> float:
    s = np.zeros(len(y))
    for tr, va in folds:
        s[va] = m.make_clf(kind, c).fit(x[tr], y[tr]).decision_function(x[va])
    return round(auroc(s[y == 0], s[y == 1]), 4)


def tfidf(counts):
    return TfidfTransformer(sublinear_tf=True).fit_transform(counts).astype(np.float32)


def size(terms, n) -> dict:
    blob = m.vocab_blob({t: i for i, t in enumerate(terms)}) + bytes(8 * n + 4)
    # gzip of the vocabulary only + 8 bytes per feature: float arrays are taken as incompressible
    return {"flat_mb": round(len(blob) / 1e6, 2),
            "vocab_gzip_plus_floats_mb": round((len(gzip.compress(m.vocab_blob({t: i for i, t in enumerate(terms)}), 9)) + 8 * n + 4) / 1e6, 2),
            "int8_flat_mb_accuracy_not_measured": round((len(blob) - 6 * n) / 1e6, 2)}


out = {"n_train": len(rows), "vocab": [], "hashed": [], "c": []}
for name, cvz in (("char 1-5", CountVectorizer(analyzer="char", ngram_range=(1, 5), lowercase=False, min_df=2)),
                  ("word 1-2", CountVectorizer(analyzer="word", ngram_range=(1, 2), lowercase=True, min_df=2,
                                               token_pattern=m.WORD_PATTERN))):
    counts = cvz.fit_transform(texts).tocsc()
    terms = np.array(cvz.get_feature_names_out(), dtype=object)
    order = np.argsort(-np.asarray(counts.sum(axis=0)).ravel(), kind="stable")  # what max_features keeps
    for k in (2_000, 5_000, 20_000, 50_000, 100_000, 200_000, counts.shape[1]):
        if k > counts.shape[1]:
            continue
        keep = np.sort(order[:k])
        x = tfidf(counts[:, keep].tocsr())
        row = {"features": name, "vocab": int(k), **size(list(terms[keep]), k),
               "cv_auroc_lr": cv(x), "cv_auroc_svm": cv(x, "svm")}
        out["vocab"].append(row)
        print(row, flush=True)
    if name == "char 1-5":
        x = tfidf(counts.tocsr())
        for kind, cs in (("lr", (1, 10, 100)), ("svm", (0.1, 1, 10))):
            for c in cs:
                row = {"features": name, "clf": kind, "C": c, "cv_auroc": cv(x, kind, c)}
                out["c"].append(row)
                print(row, flush=True)

for bits in (14, 16, 18, 20):
    counts = HashingVectorizer(analyzer="char", ngram_range=(1, 5), lowercase=False, n_features=2 ** bits,
                               alternate_sign=False, norm=None).transform(texts)
    row = {"buckets": f"2^{bits}", "float32_mb": round(8 * 2 ** bits / 1e6, 2), "int8_mb": round(2 * 2 ** bits / 1e6, 2),
           "cv_auroc_lr": cv(tfidf(counts))}
    out["hashed"].append(row)
    print(row, flush=True)

os.makedirs(m.SIZE_DIR, exist_ok=True)
with open(os.path.join(m.SIZE_DIR, "sizes.json"), "w") as f:
    json.dump(out, f, indent=1)
