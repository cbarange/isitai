#!/usr/bin/env python
"""Ablation of the light score, out of distribution only.

Leave-one-family-out (raid, hc3, mage, reviews, faq) and leave-one-generator-out.
The threshold is the 99th percentile of the human scores of the TRAINING folds, then
applied as is to the held-out family: the figure that matters is the false-positive
rate there, and the configuration is chosen on its worst value. No test split, no
Wikipedia text and no golden file is read here.

Run:  /tmp/isitai-bench/venv/bin/python bench/light/experiments.py
"""
from __future__ import annotations

import json
import sys

import numpy as np

from common import TRAIN_MIN_WORDS, Model, auroc, columns, load
import features as F

EVAL_MIN_WORDS = 100
BASE = ("sent", "word", "div", "rep", "punct", "case", "char")
CONFIGS = {
    "all": dict(groups=BASE),
    "all+rhet": dict(groups=BASE + ("rhet",)),
    "all+hash": dict(groups=BASE, use_hash=True),
    "hash-only": dict(groups=(), use_hash=True),
    **{f"all-{g}": dict(groups=tuple(x for x in BASE if x != g)) for g in BASE},
    "no-case-char": dict(groups=("sent", "word", "div", "rep", "punct")),
    "sent+div+rep": dict(groups=("sent", "div", "rep")),
    "sent+div+rep+punct": dict(groups=("sent", "div", "rep", "punct")),
}


def lofo(d, cfg, c=0.1):
    out = {}
    train_ok = d["nw"] >= TRAIN_MIN_WORDS
    eval_ok = d["nw"] >= EVAL_MIN_WORDS
    for fam in ("raid", "hc3", "mage", "reviews", "faq"):
        tr = np.nonzero(train_ok & (d["family"] != fam))[0]
        te = np.nonzero(eval_ok & (d["family"] == fam))[0]
        m = Model(columns(cfg["groups"]), c=c, use_hash=cfg.get("use_hash", False)).fit(d, tr)
        s_tr = m.score(d, tr)
        ref = s_tr[(d["y"][tr] == 0) & (d["nw"][tr] >= EVAL_MIN_WORDS)]
        thr = float(np.quantile(ref, 0.99))
        s = m.score(d, te)
        for lang in ("en", "fr"):
            k = d["lang"][te] == lang
            y = d["y"][te][k]
            if (y == 0).sum() < 30:
                continue
            fpr = float((s[k][y == 0] > thr).mean())
            tpr = float((s[k][y == 1] > thr).mean()) if (y == 1).sum() >= 30 else float("nan")
            out[f"{fam}/{lang}"] = dict(fpr=fpr, tpr=tpr, auroc=auroc(y, s[k]),
                                        n0=int((y == 0).sum()), n1=int((y == 1).sum()))
    return out


def logo(d, cfg, c=0.1):
    """Leave one generator out: its texts leave the training set, the humans stay."""
    out = {}
    ok = d["nw"] >= TRAIN_MIN_WORDS
    for gen in sorted(set(d["gen"]) - {"human"}):
        tr = np.nonzero(ok & (d["gen"] != gen))[0]
        te = np.nonzero((d["nw"] >= EVAL_MIN_WORDS) & (d["gen"] == gen) & (d["lang"] == "en"))[0]
        if len(te) < 30:
            continue
        m = Model(columns(cfg["groups"]), c=c, use_hash=cfg.get("use_hash", False)).fit(d, tr)
        s_tr = m.score(d, tr)
        thr = float(np.quantile(s_tr[(d["y"][tr] == 0) & (d["nw"][tr] >= EVAL_MIN_WORDS)], 0.99))
        out[gen] = float((m.score(d, te) > thr).mean())
    return out


def main():
    d = load("pool")
    names = sys.argv[1:] or list(CONFIGS)
    results = {}
    print(f"{'config':20s} worstFPR  meanFPR meanTPR meanAUC | per family/lang fpr:tpr:auroc")
    for name in names:
        r = lofo(d, CONFIGS[name])
        fprs = [v["fpr"] for v in r.values()]
        tprs = [v["tpr"] for v in r.values() if v["tpr"] == v["tpr"]]
        aucs = [v["auroc"] for v in r.values() if v["auroc"] == v["auroc"]]
        cells = " ".join(f"{k}={v['fpr']:.2f}:{v['tpr']:.2f}:{v['auroc']:.2f}" for k, v in r.items())
        print(f"{name:20s} {max(fprs):.3f}    {np.mean(fprs):.3f}   {np.mean(tprs):.3f}   "
              f"{np.mean(aucs):.3f} | {cells}", flush=True)
        results[name] = r
    with open("/tmp/isitai-bench/light/experiments.json", "w") as f:
        json.dump(results, f, indent=1)


if __name__ == "__main__":
    main()
