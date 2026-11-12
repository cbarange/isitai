"""Shared constants and helpers of the detector benchmark. Importable from detector
modules: `from common import THREADS, load_split, BENCH_DIR`."""
from __future__ import annotations

import json
import os

BENCH_DIR = os.environ.get("ISITAI_BENCH_DIR", "/tmp/isitai-bench")
DATA_DIR = os.path.join(BENCH_DIR, "data")
RESULTS_DIR = os.path.join(BENCH_DIR, "results")
#: Scratch space for a detector's own fitted artefacts (never the repo).
CACHE_DIR = os.path.join(BENCH_DIR, "cache")
#: Every detector runs on CPU with this many threads.
THREADS = 4
SPLITS = ["train", "test", "test_ood", "test_fr", "test_fiction", "test_attack"]
LENGTH_BUCKETS = [("<50", 0, 50), ("50-200", 50, 200), ("200-1000", 200, 1000), (">1000", 1000, 10**9)]


def load_split(split: str, limit: int | None = None) -> list[dict]:
    path = os.path.join(DATA_DIR, f"{split}.jsonl")
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
            if limit and len(rows) >= limit:
                break
    return rows


def length_bucket(n_words: int) -> str:
    for name, lo, hi in LENGTH_BUCKETS:
        if lo <= n_words < hi:
            return name
    return LENGTH_BUCKETS[-1][0]
