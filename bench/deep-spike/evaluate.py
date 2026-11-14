#!/usr/bin/env python
"""Metrics of the spike runs (/tmp/isitai-deep/results/*.json). Markdown on stdout.

Same definitions as bench/detectors/evaluate.py (imported): AUROC, threshold at 1 % false
positives on the human texts of `test`, flagged when score > threshold, transfer = that
threshold applied unchanged elsewhere. Wilson 95 % intervals for the golden set.
"""
from __future__ import annotations

import collections
import glob
import json
import math
import os
import sys

import numpy as np
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "detectors"))
from evaluate import auroc, rate, threshold  # noqa: E402

RES = "/tmp/isitai-deep/results"
TEXTS = "/tmp/isitai-deep/texts"
BENCH = "/tmp/isitai-bench/results"
SPLITS = ["test", "test_ood", "test_fr", "test_fiction", "test_attack"]
REF = {"bino.smollm2-135m+smollm2-135m-instruct": "binoculars_small.smollm2-135m",
       "fdgpt.neo125": "fast_detectgpt.neo125"}

meta = {s: {r["id"]: r for r in map(json.loads, open(f"{TEXTS}/{s}.jsonl", encoding="utf-8"))}
        for s in SPLITS + ["corpus", "golden"]}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def load():
    runs = {}
    for p in sorted(glob.glob(f"{RES}/*.json")):
        d = json.load(open(p))
        if "test" not in d["sets"] or d["threads"] != 4:
            continue
        runs[d["name"]] = d
    return runs


def hl(d, s):
    sc = dict(zip(d["sets"][s]["ids"], d["sets"][s]["scores"]))
    h = np.array([v for i, v in sc.items() if meta[s][i]["label"] == 0])
    a = np.array([v for i, v in sc.items() if meta[s][i]["label"] == 1])
    return h, a


def pct(x):
    return f"{100 * x:.0f}"


def main():
    runs = load()
    print("## Accuracy (fixed subsamples; threshold = 1 % false positives on `test`)\n")
    print("| Run | AUROC test | ood | fr | fiction | attack | TPR test | ood TPR/FPR | fr TPR/FPR | fiction TPR/FPR | attack TPR/FPR | thr@1 |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    thr = {}
    for name, d in runs.items():
        h, a = hl(d, "test")
        t = thr[name] = threshold(h, 0.01)
        cells = [f"{auroc(*hl(d, s)):.3f}" if s in d["sets"] else "-" for s in SPLITS] + [pct(rate(a, t))]
        for s in SPLITS[1:]:
            if s not in d["sets"]:
                cells.append("-")
                continue
            hh, aa = hl(d, s)
            cells.append(f"{pct(rate(aa, t))} / {pct(rate(hh, t))}")
        print(f"| {name} | " + " | ".join(cells) + f" | {t:.4f} |")

    print("\n## Parity with the benchmark's PyTorch fp32 scores (same ids)\n")
    print("| Run | reference | n | max abs diff | mean abs diff |")
    print("|---|---|---|---|---|")
    for name, d in runs.items():
        fam = name.rsplit(".", 1)[0]
        if fam not in REF or not all(s in d["sets"] for s in SPLITS):
            continue
        diffs = []
        for s in SPLITS:
            ref = json.load(open(f"{BENCH}/{REF[fam]}.{s}.sample.json"))
            r = dict(zip(ref["ids"], ref["scores"]))
            diffs += [abs(v - r[i]) for i, v in zip(d["sets"][s]["ids"], d["sets"][s]["scores"])]
        print(f"| {name} | {REF[fam]} (torch fp32) | {len(diffs)} | {max(diffs):.2e} | {np.mean(diffs):.2e} |")

    print("\n## Quantised versus ONNX fp32 of the same detector (benchmark texts of the splits both runs scored: 1,800, or 1,200 for int8-matmul)\n")
    print("| Run | Spearman | max abs diff | mean abs diff | score sd (fp32) | at the fp32 threshold: test TPR/FPR | fr TPR/FPR | ood TPR/FPR |")
    print("|---|---|---|---|---|---|---|---|")
    for name, d in runs.items():
        fam, prec = name.rsplit(".", 1)
        base = runs.get(fam + ".onnx-fp32")
        if base is None or prec == "onnx-fp32":
            continue
        common = [s for s in SPLITS if s in d["sets"]]
        x = np.concatenate([base["sets"][s]["scores"] for s in common])
        y = np.concatenate([d["sets"][s]["scores"] for s in common])
        t = thr[fam + ".onnx-fp32"]
        cells = []
        for s in ("test", "test_fr", "test_ood"):
            hh, aa = hl(d, s)
            cells.append(f"{pct(rate(aa, t))} / {pct(rate(hh, t))}")
        print(f"| {name} | {spearmanr(x, y)[0]:.4f} | {np.abs(x - y).max():.3f} | {np.abs(x - y).mean():.3f} | {x.std():.3f} | " + " | ".join(cells) + " |")

    print("\n## Wikipedia humans (corpus/text, 117 texts): flagged at the run's own thr@1, per language\n")
    langs = sorted({r["lang"] for r in meta["corpus"].values() if r["label"] == 0})
    print("| Run | all | " + " | ".join(langs) + " | ai-snowman |")
    print("|---|---|" + "---|" * (len(langs) + 1))
    for name, d in runs.items():
        if "corpus" not in d["sets"]:
            continue
        sc = dict(zip(d["sets"]["corpus"]["ids"], d["sets"]["corpus"]["scores"]))
        by = collections.defaultdict(list)
        ai = "-"
        for i, v in sc.items():
            m = meta["corpus"][i]
            if m["label"] == 0:
                by[m["lang"]].append(v > thr[name])
            else:
                ai = "flagged" if v > thr[name] else "missed"
        tot = sum(sum(v) for v in by.values())
        n = sum(len(v) for v in by.values())
        print(f"| {name} | {tot}/{n} | " + " | ".join(f"{sum(by[l])}/{len(by[l])}" for l in langs) + f" | {ai} |")

    print("\n## Golden set (bench/golden, v1.0): human class flagged at the run's own thr@1, Wilson 95 %\n")
    print("| Run | fr humans flagged (n=75, 9 documents) | en humans flagged (n=75, 27 documents) | fr AI flagged (n=50) | en AI flagged (n=50) | AUROC fr | AUROC en |")
    print("|---|---|---|---|---|---|---|")
    for name, d in runs.items():
        if "golden" not in d["sets"]:
            continue
        sc = dict(zip(d["sets"]["golden"]["ids"], d["sets"]["golden"]["scores"]))
        cells, aucs = [], []
        for cls in ("human", "ai"):
            for lang in ("fr", "en"):
                v = [s for i, s in sc.items() if meta["golden"][i]["class"] == cls and meta["golden"][i]["lang"] == lang]
                k = sum(s > thr[name] for s in v)
                lo, hi = wilson(k, len(v))
                cells.append(f"{k}/{len(v)} = {100 * k / len(v):.0f} % [{100 * lo:.0f}, {100 * hi:.0f}]")
        for lang in ("fr", "en"):
            h = np.array([s for i, s in sc.items() if meta["golden"][i]["class"] == "human" and meta["golden"][i]["lang"] == lang])
            a = np.array([s for i, s in sc.items() if meta["golden"][i]["class"] == "ai" and meta["golden"][i]["lang"] == lang])
            aucs.append(f"{auroc(h, a):.3f}")
        print(f"| {name} | " + " | ".join(cells + aucs) + " |")

    print("\n## Per-language threshold sketch: French threshold = 1 % false positives on the human texts of `test_fr` (n=200)\n")
    print("| Run | thr en (test) | thr fr (test_fr) | test_fr TPR at thr fr | Wikipedia fr humans flagged | golden fr humans flagged | golden fr AI flagged |")
    print("|---|---|---|---|---|---|---|")
    for name, d in runs.items():
        if not all(s in d["sets"] for s in ("test_fr", "corpus", "golden")):
            continue
        h, a = hl(d, "test_fr")
        tf = threshold(h, 0.01)
        c = dict(zip(d["sets"]["corpus"]["ids"], d["sets"]["corpus"]["scores"]))
        wf = [v for i, v in c.items() if meta["corpus"][i]["lang"] == "fr" and meta["corpus"][i]["label"] == 0]
        g = dict(zip(d["sets"]["golden"]["ids"], d["sets"]["golden"]["scores"]))
        gh = [v for i, v in g.items() if meta["golden"][i]["lang"] == "fr" and meta["golden"][i]["class"] == "human"]
        ga = [v for i, v in g.items() if meta["golden"][i]["lang"] == "fr" and meta["golden"][i]["class"] == "ai"]
        kh, ka = sum(v > tf for v in gh), sum(v > tf for v in ga)
        lo, hi = wilson(kh, len(gh))
        print(f"| {name} | {thr[name]:.4f} | {tf:.4f} | {pct(rate(a, tf))} | {sum(v > tf for v in wf)}/{len(wf)} | "
              f"{kh}/{len(gh)} [{100 * lo:.0f}, {100 * hi:.0f}] | {ka}/{len(ga)} |")

    print("\n## Python timing and memory (4 threads; machine shared, indicative)\n")
    print("| Run | median ms/text on test | peak RSS MB | load s |")
    print("|---|---|---|---|")
    for name, d in runs.items():
        print(f"| {name} | {1000 * d['sets']['test']['seconds_median']:.0f} | {d['peak_rss_mb']:.0f} | {d['load_seconds']:.1f} |")


if __name__ == "__main__":
    main()
