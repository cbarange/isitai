"""Calibration of intrinsic_dim on the TRAIN split only (never a test split).

  /tmp/isitai-bench/venv/bin/python algos/intrinsic_dim_calibrate.py [--n 300] [--model roberta|xlmr]

On a class-balanced, seeded sample of train it records, per text: number of points, the
PH-dim under 3 seeds and the MLE. It prints
  - the median dimension (the FALLBACK_DIM constants of intrinsic_dim.py),
  - the AUROC of -dimension on that train sample (direction check),
  - the seed-to-seed spread of PH-dim and the AUROC by number of points (the practical
    minimum length),
  - a check of prim_tree against scipy's minimum spanning tree.
Output: /tmp/isitai-bench/scratch/intrinsic_dim_calibration.<model>.json
"""
from __future__ import annotations

import os

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_v] = "4"
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")

import argparse  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402
import sys  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from common import BENCH_DIR, load_split  # noqa: E402
from algos import intrinsic_dim as idim  # noqa: E402

BINS = [(0, 47), (47, 80), (80, 120), (120, 200), (200, 350), (350, 511)]


def auroc(h, a):
    h, a = np.asarray(h), np.asarray(a)
    if not len(h) or not len(a):
        return None
    return float(((a[:, None] > h[None, :]).sum() + 0.5 * (a[:, None] == h[None, :]).sum()) / (len(h) * len(a)))


def check_prim() -> float:
    from scipy.sparse.csgraph import minimum_spanning_tree
    rng = np.random.RandomState(0)
    worst = 0.0
    for n in (5, 40, 200):
        d = idim.distance_matrix(rng.randn(n, 16))
        worst = max(worst, abs(idim.prim_tree(d) - minimum_spanning_tree(d).sum()))
    return worst


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--model", choices=["roberta", "xlmr"], default="roberta")
    args = ap.parse_args()
    model_id = idim.ROBERTA if args.model == "roberta" else idim.XLMR

    import torch
    torch.set_num_threads(4)
    print("prim_tree vs scipy MST, max abs difference:", check_prim())

    rows = load_split("train")
    rng = random.Random(idim.SEED)
    human = rng.sample([r for r in rows if r["label"] == 0], args.n // 2)
    ai = rng.sample([r for r in rows if r["label"] == 1], args.n // 2)
    recs = []
    for i, r in enumerate(human + ai):
        points = idim.embed(model_id, r["text"])
        n = points.shape[0]
        rec = {"id": r["id"], "label": r["label"], "n_points": n, "n_words": r["n_words"],
               "phd": [None] * 3, "mle": None}
        if n >= idim.MLE_MIN_POINTS:
            dist = idim.distance_matrix(points)
            rec["mle"] = idim.mle_dimension(dist)
            if n >= idim.PHD_MIN_POINTS:
                rec["phd"] = [idim.phd_dimension(dist, idim.text_rng(r["text"], idim.SEED + s)) for s in range(3)]
        recs.append(rec)
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(human) + len(ai)}", file=sys.stderr)

    out = os.path.join(BENCH_DIR, "scratch", f"intrinsic_dim_calibration.{args.model}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(recs, f)

    def ok(v):
        return v is not None and np.isfinite(v) and v > 0

    print(f"model {model_id}, {len(recs)} train texts, points: median "
          f"{np.median([r['n_points'] for r in recs]):.0f}")
    for est in ("phd", "mle"):
        get = (lambda r: r["phd"][0]) if est == "phd" else (lambda r: r["mle"])
        good = [r for r in recs if ok(get(r))]
        vals = np.array([get(r) for r in good])
        lab = np.array([r["label"] for r in good])
        print(f"{est}: scored {len(good)}/{len(recs)}; median dimension {np.median(vals):.3f} "
              f"(human {np.median(vals[lab == 0]):.3f}, ai {np.median(vals[lab == 1]):.3f}); "
              f"AUROC of -dimension {auroc(-vals[lab == 0], -vals[lab == 1]):.3f}")
        for lo, hi in BINS:
            sel = [r for r in good if lo <= r["n_points"] < hi]
            if not sel:
                continue
            v = np.array([get(r) for r in sel])
            l = np.array([r["label"] for r in sel])
            a = auroc(-v[l == 0], -v[l == 1])
            line = (f"   points [{lo},{hi}): n={len(sel)} (human {int((l == 0).sum())}, ai {int((l == 1).sum())}) "
                    f"AUROC {'n/a' if a is None else format(a, '.3f')}")
            if est == "phd":
                sd = [np.std(r["phd"]) for r in sel if all(ok(x) for x in r["phd"])]
                if sd:
                    line += f"; seed-to-seed std of the dimension: median {np.median(sd):.2f}, p90 {np.percentile(sd, 90):.2f}"
            print(line)
    bad = [r["n_points"] for r in recs if r["n_points"] >= idim.PHD_MIN_POINTS and not ok(r["phd"][0])]
    print("PH-dim not finite or not positive although >= 47 points:", len(bad), sorted(bad)[:20])


if __name__ == "__main__":
    main()
