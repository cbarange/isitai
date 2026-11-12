#!/usr/bin/env python
"""Fixed random subsample of each test split, for the detectors too slow to score every
text: /tmp/isitai-bench/data/samples/<split>.ids.json. Stratified by label, seeded, the
same ids for every detector (run.py --sample, evaluate.py --sample)."""
import json
import os
import random

from common import DATA_DIR, load_split

SEED = 20261112
SIZES = {"test": 400, "test_ood": 400, "test_fr": 400, "test_attack": 400, "test_fiction": 200}

os.makedirs(os.path.join(DATA_DIR, "samples"), exist_ok=True)
for split, n in SIZES.items():
    rows = load_split(split)
    rng = random.Random(f"{SEED}:{split}")
    ids = []
    for label in (0, 1):
        pool = sorted(r["id"] for r in rows if r["label"] == label)
        ids += rng.sample(pool, n // 2)
    with open(os.path.join(DATA_DIR, "samples", f"{split}.ids.json"), "w") as f:
        json.dump(sorted(ids), f)
    print(split, len(ids))
