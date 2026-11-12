"""AUROC of the tfidf_lr smoke runs. evaluate.py ignores `.limitN.json` result files, so
this helper joins them to the data by id and uses evaluate.auroc.

  /tmp/isitai-bench/venv/bin/python algos/tfidf_lr_smoke.py [--limit 100]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import RESULTS_DIR, load_split  # noqa: E402
from evaluate import auroc  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--limit", type=int, default=100)
args = ap.parse_args()

labels = {}
for path in sorted(glob.glob(os.path.join(RESULTS_DIR, f"tfidf_lr.*.limit{args.limit}.json"))):
    r = json.load(open(path))
    if r["split"] not in labels:
        labels[r["split"]] = {x["id"]: x["label"] for x in load_split(r["split"])}
    y = np.array([labels[r["split"]][i] for i in r["ids"]])
    s = np.array(r["scores"])
    print(f"{r['algo']:28s} {r['split']:8s} n={r['n']} human={int((y == 0).sum())} ai={int((y == 1).sum())} "
          f"auroc={auroc(s[y == 0], s[y == 1]):.3f}  fit={r['fit_seconds']:.0f}s  "
          f"median/text={r['seconds_per_text_median'] * 1000:.1f}ms  rss={r['peak_rss_mb']:.0f}MB\n"
          f"    {r['model']}")
