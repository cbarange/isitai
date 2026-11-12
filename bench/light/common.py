"""Shared helpers of the light-score scripts: cached features, families, model fit."""
from __future__ import annotations

import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features as F  # noqa: E402

FEAT_DIR = "/tmp/isitai-bench/light/feat"
CLIP_Z = 4.0
TRAIN_MIN_WORDS = 60


def load(name: str) -> dict:
    with open(os.path.join(FEAT_DIR, f"{name}.pkl"), "rb") as f:
        d = pickle.load(f)
    rows = d["rows"]
    d["y"] = np.array([r["label"] for r in rows])
    d["nw"] = np.array([r["nw"] for r in rows])
    d["lang"] = np.array([r["lang"] for r in rows])
    d["det"] = np.array([r["lang_detected"] for r in rows])
    d["domain"] = np.array([r["domain"] for r in rows])
    d["gen"] = np.array([r["generator"] for r in rows])
    d["family"] = np.array([family(r["domain"]) for r in rows])
    return d


def family(domain: str) -> str:
    """Source family: a held-out family shares no collection process with the others.
    The machine-translated HC3 rows are the same answers as HC3, so one family."""
    for prefix, fam in (("raid-", "raid"), ("hc3", "hc3"), ("mage-", "mage"),
                        ("reviews-", "reviews"), ("faq-", "faq")):
        if domain.startswith(prefix):
            return fam
    return domain


def columns(groups) -> list:
    return [F.SCALAR_FEATURES.index(n) for g in groups for n in F.GROUPS[g]]


def cell_weights(fam, y) -> np.ndarray:
    """Every (family, label) cell weighs the same: RAID does not drown the rest."""
    w = np.zeros(len(y))
    for f in np.unique(fam):
        for label in (0, 1):
            m = (fam == f) & (y == label)
            if m.any():
                w[m] = 1.0 / m.sum()
    return w * len(y) / w.sum()


class Model:
    """Standardisation (clipped z-scores) and an L2 logistic regression."""

    def __init__(self, cols, c=0.1, use_hash=False, hash_scale=1.0):
        self.cols, self.c, self.use_hash, self.hash_scale = cols, c, use_hash, hash_scale

    def design(self, d, idx):
        parts = []
        if self.cols:
            z = (d["X"][idx][:, self.cols] - self.mean) / self.scale
            parts.append(np.clip(z, -CLIP_Z, CLIP_Z))
        if self.use_hash:
            parts.append(d["hash"][idx].toarray() * self.hash_scale)
        return np.hstack(parts)

    def fit(self, d, idx):
        from sklearn.linear_model import LogisticRegression
        if self.cols:
            x = d["X"][idx][:, self.cols]
            self.mean = x.mean(axis=0)
            self.scale = x.std(axis=0)
            self.scale[self.scale < 1e-9] = 1.0
        w = cell_weights(d["family"][idx], d["y"][idx])
        self.lr = LogisticRegression(C=self.c, max_iter=2000)
        self.lr.fit(self.design(d, idx), d["y"][idx], sample_weight=w)
        return self

    def score(self, d, idx=None):
        idx = np.arange(len(d["y"])) if idx is None else idx
        return self.lr.decision_function(self.design(d, idx))


def auroc(y, s) -> float:
    from sklearn.metrics import roc_auc_score
    if len(set(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, s))
