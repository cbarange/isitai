#!/usr/bin/env python
"""False positives of zero-shot detectors on the author's corpus (corpus/text/).

Scores every `human-*.txt` and `ai-*.txt` file with the given detectors and applies the
thresholds fixed on the `test` subsample (1 % and 5 % false positives), read from
/tmp/isitai-bench/results/summary_sample.json. Zero-shot detectors only: nothing is fitted.

  /tmp/isitai-bench/venv/bin/python bench/detectors/score_corpus.py \
      binoculars_small:smollm2-135m fast_detectgpt:neo125

Writes bench/detectors/results/corpus_scores.json and prints a table per language.
"""
from __future__ import annotations

import collections
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa: E402  (the benchmark runner: load_detector, pin_torch)

CORPUS = os.path.join(HERE, "..", "..", "corpus", "text")
SUMMARY = "/tmp/isitai-bench/results/summary_sample.json"


def main() -> None:
    run.pin_torch()
    thresholds = json.load(open(SUMMARY))["detectors"]
    files = sorted(glob.glob(os.path.join(CORPUS, "human-*.txt")) + glob.glob(os.path.join(CORPUS, "ai-*.txt")))
    texts = [open(f, encoding="utf-8").read() for f in files]
    names = [os.path.basename(f) for f in files]
    out = {}
    for spec in sys.argv[1:]:
        algo, variant = spec.split(":")
        det, _ = run.load_detector(algo, variant)
        scores = [float(det.score([t])[0]) for t in texts]
        t = thresholds[f"{algo}.{variant}"]["splits"]["test"]
        out[spec] = {"thr@1": t["thr@1"], "thr@5": t["thr@5"], "scores": dict(zip(names, scores))}
        print(f"\n== {spec}  (threshold at 1% FPR on test: {t['thr@1']:.4f}, at 5%: {t['thr@5']:.4f})")
        by_lang = collections.defaultdict(list)
        for n, s in zip(names, scores):
            parts = n.split("-")
            lang = parts[2] if n.startswith("human-wikipedia-") else "ai"
            by_lang[lang].append((n, s))
        print("lang   n  flagged@1%  flagged@5%  median score")
        for lang, rows in sorted(by_lang.items()):
            ss = sorted(s for _, s in rows)
            f1 = sum(s > t["thr@1"] for s in ss)
            f5 = sum(s > t["thr@5"] for s in ss)
            print(f"{lang:<5} {len(rows):>3}  {f1:>10}  {f5:>10}  {ss[len(ss) // 2]:>12.4f}")
    dest = os.path.join(HERE, "results", "corpus_scores.json")
    json.dump(out, open(dest, "w"), indent=1)
    print("\nwrote", dest)


if __name__ == "__main__":
    main()
