#!/usr/bin/env python
"""Chooses the prelude sizes of algos/zippy.py. Uses the TRAIN split only: preludes come
from the first half of each class, AUROC is measured on rows of the second half.

  /tmp/isitai-bench/venv/bin/python bench/detectors/algos/zippy_sweep.py [--n 300]

Writes /tmp/isitai-bench/cache/zippy/sweep.json and prints one line per configuration.
Also asserts that the zlib state-copy shortcut gives the same byte count as compressing
prelude + sample from scratch, and prints raw and xz-compressed prelude sizes.
"""
from __future__ import annotations

import argparse
import json
import lzma
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import CACHE_DIR, load_split  # noqa: E402
from evaluate import auroc  # noqa: E402
from algos import zippy as z  # noqa: E402

import numpy as np  # noqa: E402


def au(scores, labels):
    s, y = np.asarray(scores, dtype=float), np.asarray(labels)
    return auroc(s[y == 0], s[y == 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300, help="held-out train rows per class")
    ap.add_argument("--sizes", default="32000,64000,96000,128000,256000,512000")
    ap.add_argument("--engines", default="zlib,lzma,brotli")
    args = ap.parse_args()
    sizes = [int(s) for s in args.sizes.split(",")]
    pool, heldout = z.split_train(load_split("train"))
    val = [r for r in heldout if r["label"] == 0][-args.n:] + [r for r in heldout if r["label"] == 1][-args.n:]
    texts, labels = [r["text"] for r in val], [r["label"] for r in val]
    out = []

    # zlib shortcut check
    p = z.clean_text(z.build_prelude(pool, 1, 30_000, "clean")).encode()
    sd = z.Seeded("zlib", p)
    for t in texts[:50]:
        b = t.encode()
        assert sd.total(b) == z.clen("zlib", p + b), "zlib copy() shortcut differs"
    print("zlib copy() shortcut: identical byte counts on 50 samples")

    for engine in args.engines.split(","):
        for size in sizes:
            t0 = time.perf_counter()
            pre = z.clean_text(z.build_prelude(pool, 1, size, "clean"))
            f = z.Faithful(engine, pre)
            row = {"engine": engine, "size": size, "family": "faithful",
                   "prelude_bytes": f.prelude_bytes,
                   "prelude_xz_bytes": len(lzma.compress(pre.encode(), preset=9)),
                   "auroc": au([f.score_text(t) for t in texts], labels),
                   "seconds_per_text": (time.perf_counter() - t0) / len(texts)}
            out.append(row)
            print(json.dumps(row), flush=True)
            for norm in ("ws", "clean"):
                t0 = time.perf_counter()
                a = z.build_prelude(pool, 1, size, norm)
                h = z.build_prelude(pool, 0, size, norm)
                pb = z.PerByte(engine, a, h, norm)
                c = [pb.costs(t) for t in texts]
                row = {"engine": engine, "size": size, "family": "dev", "norm": norm,
                       "ai_prelude_bytes": len(a.encode()), "human_prelude_bytes": len(h.encode()),
                       "ai_prelude_xz_bytes": len(lzma.compress(a.encode(), preset=9)),
                       "auroc_perbyte": au([-x[1] for x in c], labels),
                       "auroc_alone": au([x[3] - x[1] for x in c], labels),
                       "auroc_contrast": au([x[2] - x[1] for x in c], labels),
                       "seconds_per_text": (time.perf_counter() - t0) / len(texts)}
                out.append(row)
                print(json.dumps(row), flush=True)
    d = os.path.join(CACHE_DIR, "zippy")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "sweep.json"), "w") as fh:
        json.dump({"n_per_class": args.n, "rows": out}, fh, indent=1)


if __name__ == "__main__":
    main()
