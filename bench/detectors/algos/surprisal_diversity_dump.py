#!/usr/bin/env python
"""Feature dumps and smoke AUROC of algos/surprisal_diversity.py.

  PY=/tmp/isitai-bench/venv/bin/python
  $PY algos/surprisal_diversity_dump.py dump --model gpt2 --split all [--limit N]
  $PY algos/surprisal_diversity_dump.py smoke [--limit 100]

dump   one forward pass per text of the split(s) and, under RESULTS_DIR/features/:
         surprisal_diversity.<model>.<split>[.limitN].npz
             ids, labels, features (n x 13, columns = DUMP_COLUMNS: the 10 DivEye
             features, d1_var, lastde, n_scored), columns
         surprisal_diversity.<model>.<split>[.limitN].windows.jsonl
             one line per text: {"id", "label", "n_scored", "windows": [{"start", "end",
             "features": [13 values]}]}, windows of 100 scored tokens, stride 50
         surprisal_diversity.<model>.<split>[.limitN].dump_timing.json
             seconds per text (median, mean) split into LM pass, per-text features and
             window features
       These files are for stacking with other detectors; they are not result files
       (evaluate.py only reads RESULTS_DIR/*.json).
smoke  AUROC of the `.limitN.json` result files written by run.py, which evaluate.py
       ignores: joins them to the data by id and uses evaluate.auroc.

CPU only, THREADS threads. Timings from this script are indicative only when other jobs
share the machine.
"""
from __future__ import annotations

import os

for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
             "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "RAYON_NUM_THREADS"):
    os.environ.setdefault(_var, "4")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")

import argparse  # noqa: E402
import glob  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import DATA_DIR, RESULTS_DIR, SPLITS, THREADS, load_split  # noqa: E402


def cmd_dump(args) -> None:
    from algos import surprisal_diversity as sd
    import torch
    torch.set_num_threads(THREADS)
    if args.split == "all":
        splits = [s for s in SPLITS if os.path.exists(os.path.join(DATA_DIR, f"{s}.jsonl"))]
    else:
        splits = [s.strip() for s in args.split.split(",") if s.strip()]
    os.makedirs(sd.FEATURES_DIR, exist_ok=True)
    for split in splits:
        rows = load_split(split, args.limit)
        suffix = f".limit{args.limit}" if args.limit else ""
        base = os.path.join(sd.FEATURES_DIR, f"surprisal_diversity.{args.model}.{split}{suffix}")
        sd.token_logprobs(args.model, rows[0]["text"])       # warm-up, not timed
        feats, t_lm, t_feat, t_win = [], [], [], []
        with open(base + ".windows.jsonl.tmp", "w") as fw:
            for r in rows:
                t0 = time.perf_counter()
                ll = sd.token_logprobs(args.model, r["text"])
                t1 = time.perf_counter()
                row = sd.dump_row(ll)
                t2 = time.perf_counter()
                wins = sd.window_features(ll)
                t3 = time.perf_counter()
                feats.append(row)
                t_lm.append(t1 - t0)
                t_feat.append(t2 - t1)
                t_win.append(t3 - t2)
                fw.write(json.dumps({"id": r["id"], "label": r["label"], "n_scored": len(ll),
                                     "windows": wins}) + "\n")
        os.replace(base + ".windows.jsonl.tmp", base + ".windows.jsonl")
        np.savez_compressed(base + ".npz", ids=np.asarray([r["id"] for r in rows]),
                            labels=np.asarray([r["label"] for r in rows], dtype=np.int64),
                            features=np.asarray(feats, dtype=np.float64),
                            columns=np.asarray(sd.DUMP_COLUMNS))
        timing = {
            "model": args.model, "split": split, "n": len(rows), "threads": THREADS,
            "max_tokens": sd.MAX_TOKENS,
            "seconds_lm_per_text_median": float(np.median(t_lm)),
            "seconds_lm_per_text_mean": float(np.mean(t_lm)),
            "seconds_features_per_text_median": float(np.median(t_feat)),
            "seconds_features_per_text_mean": float(np.mean(t_feat)),
            "seconds_windows_per_text_median": float(np.median(t_win)),
            "seconds_windows_per_text_mean": float(np.mean(t_win)),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        with open(base + ".dump_timing.json", "w") as f:
            json.dump(timing, f, indent=1)
        print(f"[dump {args.model}] {split}: n={len(rows)} lm median {timing['seconds_lm_per_text_median'] * 1000:.1f} ms, "
              f"features median {timing['seconds_features_per_text_median'] * 1000:.2f} ms, "
              f"windows median {timing['seconds_windows_per_text_median'] * 1000:.2f} ms -> {base}.npz")


def cmd_smoke(args) -> None:
    from evaluate import auroc
    labels: dict = {}
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, f"surprisal_diversity.*.limit{args.limit}.json"))):
        r = json.load(open(path))
        if r["split"] not in labels:
            labels[r["split"]] = {x["id"]: x["label"] for x in load_split(r["split"])}
        y = np.array([labels[r["split"]][i] for i in r["ids"]])
        s = np.array(r["scores"])
        print(f"{r['algo']:48s} {r['split']:12s} n={r['n']} human={int((y == 0).sum())} ai={int((y == 1).sum())} "
              f"auroc={auroc(s[y == 0], s[y == 1]):.3f}  fit={r['fit_seconds']:.0f}s  "
              f"median/text={r['seconds_per_text_median'] * 1000:.1f}ms  rss={r['peak_rss_mb']:.0f}MB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dump")
    d.add_argument("--model", default="gpt2")
    d.add_argument("--split", required=True, help='one split, "a,b", or "all" (train included)')
    d.add_argument("--limit", type=int)
    d.set_defaults(func=cmd_dump)
    s = sub.add_parser("smoke")
    s.add_argument("--limit", type=int, default=100)
    s.set_defaults(func=cmd_smoke)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
