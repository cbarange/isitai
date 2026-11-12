#!/usr/bin/env python
"""Streams RAID train.csv (11.8 GB) once from stdin and keeps two reduced files.

Usage:
  curl -sL https://huggingface.co/datasets/liamdugan/raid/resolve/main/train.csv \
    | /tmp/isitai-bench/venv/bin/python fetch_raid.py /tmp/isitai-bench/raw/raid

Writes:
  none.jsonl    every row with attack == "none" (all domains, all generators)
  attack.jsonl  every attacked row whose source document falls in the "attack pool":
                sha1(source_id) % 100 < 2. build_data.py keeps these source documents
                out of every other split.
The CSV itself is never stored.
"""
import csv
import hashlib
import json
import os
import sys

KEEP = ["id", "adv_source_id", "source_id", "model", "decoding", "repetition_penalty",
        "attack", "domain", "title", "generation"]


def in_attack_pool(source_id: str) -> bool:
    return int(hashlib.sha1(source_id.encode()).hexdigest(), 16) % 100 < 2


def main() -> None:
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    csv.field_size_limit(1 << 30)
    stream = open(sys.stdin.fileno(), "r", encoding="utf-8", newline="")
    reader = csv.reader(stream)
    header = next(reader)
    ix = {name: header.index(name) for name in KEEP}
    n = n_none = n_att = 0
    with open(os.path.join(out, "none.jsonl.tmp"), "w") as f_none, \
            open(os.path.join(out, "attack.jsonl.tmp"), "w") as f_att:
        for row in reader:
            n += 1
            attack = row[ix["attack"]]
            if attack == "none":
                f_none.write(json.dumps({k: row[ix[k]] for k in KEEP}, ensure_ascii=False) + "\n")
                n_none += 1
            elif in_attack_pool(row[ix["source_id"]]):
                f_att.write(json.dumps({k: row[ix[k]] for k in KEEP}, ensure_ascii=False) + "\n")
                n_att += 1
            if n % 500000 == 0:
                print(n, n_none, n_att, file=sys.stderr, flush=True)
    os.replace(os.path.join(out, "none.jsonl.tmp"), os.path.join(out, "none.jsonl"))
    os.replace(os.path.join(out, "attack.jsonl.tmp"), os.path.join(out, "attack.jsonl"))
    print(json.dumps({"rows": n, "none": n_none, "attack_pool": n_att}))


if __name__ == "__main__":
    main()
