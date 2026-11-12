#!/usr/bin/env python
"""Combination experiment: does a logistic regression over several detectors beat the best
single one, out of distribution, and at what cost?

  /tmp/isitai-bench/venv/bin/python stack.py

Protocol (everything on the fixed subsample of each split, data/samples, so that slow and
fast detectors are combined on the same texts):
  - inputs: the scores of the component detectors, read from the result files;
  - standardised with the mean and deviation of the `test` subsample only, clipped to +-6;
  - L2 logistic regression (C = 1) fitted on the `test` subsample only (400 texts);
  - scores of `test` itself are OUT-OF-FOLD (5 folds, stratified), so that the thresholds
    transferred by evaluate.py do not come from in-sample scores;
  - the other splits are scored by the model fitted on the whole `test` subsample.
Each stack is written as an ordinary result file `stack.<name>.<split>.sample.json`, so
evaluate.py --sample gives it the same metrics and intervals as any detector. Its time per
text is the SUM of the medians of its components (they do not share forward passes here),
its memory the maximum.

Stacks are defined by rule, not by looking at out-of-distribution results:
  a-nomodel            one detector per no-model family (stylometry, char TF-IDF,
                       storyscope_lite, compression contrast) + the isitai rules
  a-nomodel-nolayout   the same with the layout-free variants
  a-untrained          no model AND no fit on RAID (compression alone, length, rules)
  b-nomodel+lm         a-nomodel + the zero-shot small-LM detector with the best AUROC on test
  b-nolayout+lm        a-nomodel-nolayout + the same LM detector
  zeroshot-lm          every zero-shot LM detector that was run (no training on RAID at all)
  c-all                every detector that has results on all splits
  c-all-clean          c-all without the pretrained classifiers trained on RAID or MAGE
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import DATA_DIR, RESULTS_DIR, load_split  # noqa: E402

SPLITS = ["test", "test_ood", "test_fr", "test_fiction", "test_attack"]
SEED = 20261112

A = ["stylometry_lr.full", "tfidf_lr.char15-lr", "storyscope_lite.lr", "zippy.zlib-contrast",
     "isitai_rules"]
A_NOLAYOUT = ["stylometry_lr.full-nolayout", "tfidf_lr.char15-lr", "storyscope_lite.lr-nolayout",
              "zippy.zlib-contrast", "isitai_rules"]
A_UNTRAINED = ["zippy.zlib-alone", "zippy.brotli-alone", "length_baseline", "isitai_rules"]
# zero-shot LM families: pretrained LM only, nothing fitted on the train split
ZEROSHOT_PREFIX = ("binoculars_small.", "fast_detectgpt.", "telescope.", "intrinsic_dim.")
ZEROSHOT_EXACT_SUFFIX = ("-loglik", "-logrank", "-rank", "-entropy", "-lrr", "-burstiness")
CONTAMINATED = ("pretrained_classifiers.modernbert-raid-mage", "pretrained_classifiers.gpttrace",
                "pretrained_classifiers.desklib")


def load():
    ids, y = {}, {}
    for s in SPLITS:
        keep = set(json.load(open(os.path.join(DATA_DIR, "samples", f"{s}.ids.json"))))
        rows = [r for r in load_split(s) if r["id"] in keep]
        ids[s] = [r["id"] for r in rows]
        y[s] = np.array([r["label"] for r in rows])
    res = {}
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json"))):
        name = os.path.basename(path)
        if name.startswith(("summary", "stack.")):
            continue
        r = json.load(open(path))
        if not isinstance(r, dict) or "scores" not in r or r.get("limit"):
            continue
        key = (r["algo"], r["split"])
        if r.get("sample") and key in res:
            continue
        res[key] = r
    scores, meta = {}, {}
    for algo in sorted({a for a, _ in res}):
        if not all((algo, s) in res for s in SPLITS):
            continue
        per = {}
        for s in SPLITS:
            m = dict(zip(res[(algo, s)]["ids"], res[(algo, s)]["scores"]))
            if any(i not in m for i in ids[s]):
                per = None
                break
            per[s] = np.array([m[i] for i in ids[s]], dtype=float)
        if per is None:
            continue
        scores[algo] = per
        meta[algo] = {s: res[(algo, s)] for s in SPLITS}
    return ids, y, scores, meta


def is_zeroshot_lm(algo):
    if algo.startswith(ZEROSHOT_PREFIX):
        return True
    return algo.startswith("gltr_ppl.") and algo.endswith(ZEROSHOT_EXACT_SUFFIX)


def design(scores, comps, split, mu, sd):
    x = np.column_stack([scores[c][split] for c in comps])
    return np.clip((x - mu) / sd, -6, 6)


def main():
    ids, y, scores, meta = load()
    algos = sorted(scores)
    auc_test = {a: roc_auc_score(y["test"], scores[a]["test"]) for a in algos}
    zs = [a for a in algos if is_zeroshot_lm(a)]
    best_lm = max(zs, key=lambda a: auc_test[a]) if zs else None
    stacks = {
        "a-nomodel": A,
        "a-nomodel-nolayout": A_NOLAYOUT,
        "a-untrained": A_UNTRAINED,
        "zeroshot-lm": zs,
        "c-all": algos,
        "c-all-clean": [a for a in algos if not a.startswith(CONTAMINATED)],
    }
    if best_lm:
        stacks["b-nomodel+lm"] = A + [best_lm]
        stacks["b-nolayout+lm"] = A_NOLAYOUT + [best_lm]
    report = {"best_zero_shot_lm_on_test": best_lm, "auc_test": auc_test, "stacks": {}}
    for name, comps in stacks.items():
        absent = [c for c in comps if c not in scores]
        comps = [c for c in comps if c in scores]
        if len(comps) < 2:
            print(f"stack {name}: skipped, components missing: {absent}")
            continue
        xt = np.column_stack([scores[c]["test"] for c in comps])
        mu, sd = xt.mean(0), xt.std(0)
        sd[sd == 0] = 1.0
        x_test = design(scores, comps, "test", mu, sd)
        clf = LogisticRegression(C=1.0, max_iter=5000).fit(x_test, y["test"])
        oof = np.zeros(len(x_test))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=SEED).split(x_test, y["test"]):
            fold = LogisticRegression(C=1.0, max_iter=5000).fit(x_test[tr], y["test"][tr])
            oof[te] = fold.decision_function(x_test[te])
        coef = sorted(zip(comps, clf.coef_[0].tolist()), key=lambda t: -abs(t[1]))
        report["stacks"][name] = {"components": comps, "absent": absent, "coef": coef}
        for s in SPLITS:
            sc = oof if s == "test" else clf.decision_function(design(scores, comps, s, mu, sd))
            med = sum(meta[c][s]["seconds_per_text_median"] for c in comps)
            out = {
                "algo": f"stack.{name}", "module": "stack", "variant": name, "split": s,
                "n": len(sc), "scores": sc.tolist(), "ids": ids[s],
                "seconds_total": sum(meta[c][s]["seconds_per_text_batched"] for c in comps) * len(sc),
                "seconds_per_text_median": med,
                "seconds_per_text_p90": sum(meta[c][s]["seconds_per_text_p90"] for c in comps),
                "seconds_per_text_batched": sum(meta[c][s]["seconds_per_text_batched"] for c in comps),
                "timing_n": None, "batch_size": None,
                "peak_rss_mb": max(meta[c][s]["peak_rss_mb"] for c in comps),
                "fit_seconds": sum(meta[c][s]["fit_seconds"] for c in comps),
                "load_seconds": sum(meta[c][s]["load_seconds"] for c in comps),
                "threads": 4, "needs_training": True, "n_train": len(x_test),
                "model": f"logistic regression over {len(comps)} detectors: " + ", ".join(comps)
                         + " (time = sum of components, RSS = max)",
                "limit": None, "sample": True,
                "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
            with open(os.path.join(RESULTS_DIR, f"stack.{name}.{s}.sample.json"), "w") as f:
                json.dump(out, f)
        print(f"stack {name}: {len(comps)} components, "
              + " ".join(f"{s}={roc_auc_score(y[s], oof if s == 'test' else clf.decision_function(design(scores, comps, s, mu, sd))):.3f}" for s in SPLITS))
        print("   top weights: " + ", ".join(f"{c} {w:+.2f}" for c, w in coef[:6]))
    with open(os.path.join(RESULTS_DIR, "stack_report.json.txt"), "w") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":
    main()
