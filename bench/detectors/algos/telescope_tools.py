#!/usr/bin/env python
"""Side tools of algos/telescope.py. They never write under results/ and never change a
score: run.py and evaluate.py stay the source of the benchmark figures.

  PY=/tmp/isitai-bench/venv/bin/python
  $PY algos/telescope_tools.py smoke                 AUROC of every telescope.*.limitN.json
                                                     result file (evaluate.py skips --limit
                                                     runs), with evaluate.py's own auroc(),
                                                     whole file and short / not-short texts
  $PY algos/telescope_tools.py calibrate             orientation and thresholds from the
                                                     TRAIN result files only
                                                     (run.py --split train [--limit N]),
                                                     written to cache/telescope/calibration.json
  $PY algos/telescope_tools.py windows --variant smollm2-135m --split test --limit 20
                                                     per-text detail (both metrics, short
                                                     flag, per-window values) written to
                                                     cache/telescope/windows.<variant>.<split>.jsonl
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")

import numpy as np  # noqa: E402

from common import CACHE_DIR, RESULTS_DIR, THREADS, load_split  # noqa: E402
from evaluate import auroc, rate, threshold  # noqa: E402

OUT_DIR = os.path.join(CACHE_DIR, "telescope")
SHORT_WORDS = 100  # the paper skips texts under 100 words


def _load(pattern: str):
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, pattern))):
        with open(path) as f:
            r = json.load(f)
        rows = {row["id"]: row for row in load_split(r["split"])}
        yield path, r, [rows[i] for i in r["ids"]]


def _auc(scores, rows, keep=lambda row: True):
    h = np.array([s for s, row in zip(scores, rows) if row["label"] == 0 and keep(row)])
    a = np.array([s for s, row in zip(scores, rows) if row["label"] == 1 and keep(row)])
    return auroc(h, a), len(h), len(a)


def _f(x):
    return "  n/a" if x is None else f"{x:.3f}"


def smoke() -> None:
    print(f"{'result file':62s} {'n':>5s} {'AUROC':>6s}  {'<100w':>6s} (h/a)    {'>=100w':>6s} (h/a)   ms/text(median, NOT final)")
    for path, r, rows in _load("telescope.*.limit*.json"):
        if r["split"] == "train":
            continue
        allr, _, _ = _auc(r["scores"], rows)
        sh, shh, sha = _auc(r["scores"], rows, lambda row: row["n_words"] < SHORT_WORDS)
        lo, loh, loa = _auc(r["scores"], rows, lambda row: row["n_words"] >= SHORT_WORDS)
        print(f"{os.path.basename(path):62s} {r['n']:5d} {_f(allr):>6s}  {_f(sh):>6s} ({shh}/{sha})  "
              f"{_f(lo):>6s} ({loh}/{loa})  {r['seconds_per_text_median'] * 1000:8.1f}  load {r['load_seconds']:.1f}s")


def calibrate() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {}
    for path, r, rows in _load("telescope.*.train*.json"):
        s = np.array(r["scores"], dtype=float)
        y = np.array([row["label"] for row in rows])
        h, a = s[y == 0], s[y == 1]
        entry = {"result_file": os.path.basename(path), "n_train": int(len(s)),
                 "auroc_train": auroc(h, a),
                 "orientation_ok": bool(auroc(h, a) is not None and auroc(h, a) > 0.5)}
        for target in (0.01, 0.05):
            t = threshold(h, target)
            entry[f"threshold_fpr{int(target * 100)}"] = t
            entry[f"tpr_train_fpr{int(target * 100)}"] = rate(a, t)
        long_ = np.array([row["n_words"] >= SHORT_WORDS for row in rows])
        entry["auroc_train_100w_plus"] = auroc(s[(y == 0) & long_], s[(y == 1) & long_])
        out[r["algo"]] = entry
        print(r["algo"], json.dumps(entry))
    with open(os.path.join(OUT_DIR, "calibration.json"), "w") as f:
        json.dump(out, f, indent=1)
    print("->", os.path.join(OUT_DIR, "calibration.json"))


def windows(variant: str, split: str, limit: int | None) -> None:
    import torch
    torch.set_num_threads(THREADS)
    from algos import telescope
    det = telescope.VARIANTS[variant]()
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"windows.{variant}.{split}.jsonl")
    with open(path, "w") as f:
        for row in load_split(split, limit):
            d = det.detail(row["text"])
            d.update(id=row["id"], label=row["label"], generator=row["generator"], n_words=row["n_words"])
            f.write(json.dumps(d) + "\n")
    print("->", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["smoke", "calibrate", "windows"])
    ap.add_argument("--variant", default="smollm2-135m")
    ap.add_argument("--split", default="test")
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.cmd == "smoke":
        smoke()
    elif a.cmd == "calibrate":
        calibrate()
    else:
        windows(a.variant, a.split, a.limit)
