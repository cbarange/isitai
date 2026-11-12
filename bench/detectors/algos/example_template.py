"""Template for a trained detector with variants. Copy it, do not benchmark it: three
surface features and a logistic regression, only there to show the contract.

  run.py --algo example_template --variant logreg --split test
"""
from __future__ import annotations

import numpy as np

NAME = "example_template"
NEEDS_TRAINING = True
MODEL = "none (logistic regression on 3 surface features, a few bytes)"


def features(texts: list[str]) -> np.ndarray:
    rows = []
    for t in texts:
        words = t.split()
        n = max(1, len(words))
        rows.append([np.log1p(len(words)), sum(map(len, words)) / n, t.count(",") / n])
    return np.asarray(rows, dtype=float)


class Detector:
    """What a VARIANTS callable returns: an object with NAME, NEEDS_TRAINING, MODEL,
    score(), and fit() when NEEDS_TRAINING is true. BATCH_SIZE is optional."""
    NEEDS_TRAINING = True
    BATCH_SIZE = 256

    def __init__(self, c: float):
        self.NAME = f"example_template.c{c}"
        self.MODEL = MODEL
        self.c = c
        self.clf = None

    def fit(self, rows: list[dict]) -> None:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        x = features([r["text"] for r in rows])
        y = [r["label"] for r in rows]
        self.clf = make_pipeline(StandardScaler(), LogisticRegression(C=self.c)).fit(x, y)

    def score(self, texts: list[str]) -> list[float]:
        return self.clf.predict_proba(features(texts))[:, 1].tolist()


VARIANTS = {
    "logreg": lambda: Detector(1.0),
    "logreg-strong-reg": lambda: Detector(0.01),
}
