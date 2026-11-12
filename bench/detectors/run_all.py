#!/usr/bin/env python
"""Runs the whole benchmark, ONE process at a time, so timings are comparable.

  /tmp/isitai-bench/venv/bin/python run_all.py --phase 1,2,3 [--deadline-min 240] [--since EPOCH]

One `run.py --split all` process per detector variant. A variant is skipped when its five
result files exist and are newer than --since (default: the start of the first run_all of
the day, kept in logs/runall/since.txt) and than its module file. When a process fails,
the missing splits are retried one by one; what still fails is recorded.

Phases (a cut-off still leaves a usable benchmark):
  1  detectors without a downloaded model, on the FULL splits
  2  one variant per language-model family (the module default, else the plain one)
  3  pretrained classifiers
  4  every other variant

Phases 2-4 and the slow compression variants run on the fixed subsample of each split
(make_samples.py: 400 texts, 200 for test_fiction; --sample of run.py), because 75
language-model variants on 5,490 texts do not fit in a working day on one CPU.

Log: /tmp/isitai-bench/logs/runall/<label>.log, status in logs/runall/status.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import BENCH_DIR, RESULTS_DIR  # noqa: E402

PY = os.path.join(BENCH_DIR, "venv", "bin", "python")
LOG_DIR = os.path.join(BENCH_DIR, "logs", "runall")
SPLITS = ["test", "test_ood", "test_fr", "test_fiction", "test_attack"]

FULL, SAMPLE = False, True


def V(module, *variants):
    return [(module, v) for v in variants]


PHASES = {
    1: (FULL, 100,
        [("length_baseline", None), ("isitai_rules", None)]
        + V("storyscope_lite", "lr", "lr-nolayout", "paper-sign")
        + V("stylometry_lr", "full", "full-nolayout", "lang-indep", "lang-indep-nolayout")
        + V("tfidf_lr", "char15-lr", "char15-svm", "charword-lr", "word12-lr", "word12-svm",
            "bpe24-chunk-lr", "hash16-lr", "hash16-lr-q8", "hash18-lr", "hash18-lr-q8",
            "hash20-lr", "hash20-lr-q8")
        + V("zippy", "zlib", "zlib-alone", "zlib-contrast", "zlib-perbyte",
            "brotli", "brotli-alone", "brotli-contrast", "brotli-perbyte")),
    2: (SAMPLE, 50,
        V("binoculars_small", "smollm2-135m") + V("fast_detectgpt", "gpt2")
        + V("gltr_ppl", "gpt2-logrank") + V("intrinsic_dim", "phd")
        + V("shuffle_ppl", "gpt2-lr") + V("surprisal_diversity", "diveye-gpt2")
        + V("telescope", "smollm2-135m")),
    3: (SAMPLE, 50,
        V("pretrained_classifiers", "modernbert-raid-mage-onnx-int8", "gpttrace-ettin150",
          "roberta-openai", "modernbert-raid-mage", "modernbert-raid-mage-onnx", "desklib")),
    4: (SAMPLE, 50,
        # ordered by interest: a deadline cuts the tail, not the head
        V("gltr_ppl", "gpt2-loglik", "gpt2-rank", "gpt2-entropy", "gpt2-lrr",
          "gpt2-burstiness", "distilgpt2-logrank")
        + V("fast_detectgpt", "neo125", "distilgpt2", "gpt2_neo125")
        + V("binoculars_small", "distilgpt2-obs-gpt2-perf", "gpt2-obs-distilgpt2-perf")
        + V("shuffle_ppl", "gpt2-ref-loglik", "gpt2-logratio", "gpt2-density")
        + V("telescope", "smollm2-135m-ppl", "smollm2-135m-trunc512", "smollm2-135m-instruct",
            "smollm-135m")
        + V("surprisal_diversity", "lastde-gpt2", "diveye-lastde-gpt2")
        + V("gltr_ppl", "distilgpt2-feats-lr")
        + V("zippy", "stack", "ensemble-contrast", "lzma", "lzma-contrast")
        + V("intrinsic_dim", "mle", "phd-xlmr")
        + V("binoculars_small", "smollm2-360m")
        + V("shuffle_ppl", "smollm2-360m-lr", "gpt2-diff", "gpt2-lr-avg3")
        + V("zippy", "lzma-perbyte", "lzma-alone", "ensemble")
        + V("gltr_ppl", "gpt2-feats-lr", "gpt2-gltr-lr", "distilgpt2-gltr-lr",
            "distilgpt2-loglik", "distilgpt2-entropy", "distilgpt2-rank", "distilgpt2-lrr",
            "distilgpt2-burstiness")
        + V("surprisal_diversity", "diveye-smollm2-135m", "lastde-smollm2-135m",
            "diveye-lastde-smollm2-135m")
        + V("telescope", "smollm2-135m-instruct-ppl", "smollm-135m-ppl", "smollm-135m-instruct",
            "smollm2-135m-ppl-trunc512", "smollm2-135m-instruct-trunc512",
            "smollm2-135m-instruct-ppl-trunc512", "smollm-135m-instruct-ppl",
            "smollm-135m-trunc512", "smollm-135m-ppl-trunc512",
            "smollm-135m-instruct-trunc512", "smollm-135m-instruct-ppl-trunc512")
        + V("intrinsic_dim", "mle-xlmr")
        + V("shuffle_ppl", "smollm2-360m-ref-loglik", "smollm2-360m-logratio",
            "smollm2-360m-density", "smollm2-360m-diff", "gpt2-logratio-avg3",
            "gpt2-density-avg3", "gpt2-diff-avg3", "smollm2-360m-lr-avg3",
            "smollm2-360m-logratio-avg3", "smollm2-360m-density-avg3",
            "smollm2-360m-diff-avg3")
        + V("binoculars_small", "qwen2.5-0.5b")),
}


def label_of(module, variant):
    return module if variant is None else f"{module}.{variant}"


def result_path(label, split, sample):
    return os.path.join(RESULTS_DIR, f"{label}.{split}{'.sample' if sample else ''}.json")


def missing_splits(label, module, sample, since):
    floor = max(since, os.path.getmtime(os.path.join(HERE, "algos", f"{module}.py")))
    out = []
    for s in SPLITS:
        # a full-split file also satisfies a sample run
        ok = any(os.path.exists(p) and os.path.getmtime(p) >= floor
                 for p in {result_path(label, s, sample), result_path(label, s, False)})
        if not ok:
            out.append(s)
    return out


def run(module, variant, splits, sample, time_n, timeout, log):
    cmd = [PY, os.path.join(HERE, "run.py"), "--algo", module, "--split", ",".join(splits),
           "--time-n", str(time_n)]
    if variant:
        cmd += ["--variant", variant]
    if sample:
        cmd.append("--sample")
    env = dict(os.environ, HF_HOME=os.path.join(BENCH_DIR, "hf"),
               PYTHONWARNINGS="ignore")
    t0 = time.time()
    with open(log, "a") as f:
        f.write(f"\n$ {' '.join(cmd)}\n# load averages at start: {os.getloadavg()}\n")
        f.flush()
        try:
            code = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env,
                                  timeout=timeout, cwd=HERE).returncode
        except subprocess.TimeoutExpired:
            code = "timeout"
            f.write(f"\n# TIMEOUT after {timeout}s\n")
    return code, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="1,2,3,4")
    ap.add_argument("--deadline-min", type=float, default=600,
                    help="start no new variant after this many minutes")
    ap.add_argument("--timeout-min", type=float, default=50, help="per process")
    ap.add_argument("--since", type=float)
    args = ap.parse_args()
    os.makedirs(LOG_DIR, exist_ok=True)
    since_path = os.path.join(LOG_DIR, "since.txt")
    if args.since is None:
        if not os.path.exists(since_path):
            with open(since_path, "w") as f:
                f.write(str(time.time()))
        args.since = float(open(since_path).read())
    status_path = os.path.join(LOG_DIR, "status.json")
    status = json.load(open(status_path)) if os.path.exists(status_path) else {}
    start = time.time()
    for phase in [int(p) for p in args.phase.split(",")]:
        sample, time_n, variants = PHASES[phase]
        for module, variant in variants:
            label = label_of(module, variant)
            todo = missing_splits(label, module, sample, args.since)
            if not todo:
                continue
            if (time.time() - start) / 60 > args.deadline_min:
                status.setdefault(label, {"phase": phase, "state": "not run (deadline)"})
                continue
            log = os.path.join(LOG_DIR, f"{label}.log")
            load = os.getloadavg()[0]
            code, secs = run(module, variant, todo, sample, time_n, args.timeout_min * 60, log)
            left = missing_splits(label, module, sample, args.since)
            retried = []
            if left and code != "timeout":
                for s in left:
                    c2, s2 = run(module, variant, [s], sample, time_n, args.timeout_min * 60, log)
                    retried.append([s, c2])
                    secs += s2
                left = missing_splits(label, module, sample, args.since)
            status[label] = {"phase": phase, "sample": sample, "exit": code, "seconds": round(secs, 1),
                             "load_at_start": round(load, 2), "retried": retried,
                             "missing_splits": left,
                             "state": "ok" if not left else "failed"}
            with open(status_path, "w") as f:
                json.dump(status, f, indent=1)
            print(f"{time.strftime('%H:%M:%S')} phase {phase} {label}: {status[label]['state']} "
                  f"exit={code} {secs:.0f}s load={load:.2f} missing={left}", flush=True)
    with open(status_path, "w") as f:
        json.dump(status, f, indent=1)


if __name__ == "__main__":
    main()
