#!/usr/bin/env python
"""Dump the texts to score as JSON Lines under /tmp/isitai-deep/texts/ (never in the repo).

  test, test_ood, test_fr, test_fiction, test_attack : fixed benchmark subsamples (same ids)
  corpus  : corpus/text/human-*.txt and ai-*.txt (read-only), lang from the file name
  golden  : bench/golden/set (built by bench/golden/build.py), classes human and ai only
  parity  : 120 texts for the Rust-vs-Python comparison (60 test, 30 test_fr, 30 test_fiction)
"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..", "..")
DATA = "/tmp/isitai-bench/data"
OUT = "/tmp/isitai-deep/texts"
os.makedirs(OUT, exist_ok=True)


def dump(name, rows):
    with open(os.path.join(OUT, f"{name}.jsonl"), "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(name, len(rows))


splits = {}
for split in ["test", "test_ood", "test_fr", "test_fiction", "test_attack"]:
    ids = set(json.load(open(f"{DATA}/samples/{split}.ids.json")))
    rows = [json.loads(l) for l in open(f"{DATA}/{split}.jsonl", encoding="utf-8")]
    rows = [{"id": r["id"], "text": r["text"], "label": r["label"], "lang": r["lang"],
             "generator": r["generator"]} for r in rows if r["id"] in ids]
    rows.sort(key=lambda r: r["id"])
    splits[split] = rows
    dump(split, rows)

rows = []
for f in sorted(glob.glob(os.path.join(REPO, "corpus", "text", "human-*.txt"))
                + glob.glob(os.path.join(REPO, "corpus", "text", "ai-*.txt"))):
    n = os.path.basename(f)
    human = n.startswith("human-")
    lang = n.split("-")[2] if n.startswith("human-wikipedia-") else "?"
    rows.append({"id": n, "text": open(f, encoding="utf-8").read(), "label": 0 if human else 1, "lang": lang})
dump("corpus", rows)

gold = os.path.join(REPO, "bench", "golden", "set")
rows = []
for line in open(os.path.join(gold, "MANIFEST.jsonl"), encoding="utf-8"):
    m = json.loads(line)
    if m["class"] not in ("human", "ai"):  # mixed / degraded are not scored in this spike
        continue
    p = os.path.join(gold, m["path"].split("set/")[1])
    rows.append({"id": m["path"], "text": open(p, encoding="utf-8").read(), "class": m["class"],
                 "label": {"human": 0, "ai": 1}.get(m["class"], -1), "lang": m["lang"],
                 "source": m["source"], "transform": m["transform"]})
dump("golden", rows)

parity = splits["test"][:60] + splits["test_fr"][:30] + splits["test_fiction"][:30]
dump("parity", parity)
