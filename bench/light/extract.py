#!/usr/bin/env python
"""Computes the features of every data set once and caches them in
/tmp/isitai-bench/light/feat/<name>.pkl : {"rows": [meta...], "X": array, "hash": csr}.

Data sets: pool (bench/light/build_pool.py), the five benchmark test splits, the human
Wikipedia corpus (whole documents and 300-word chunks), the golden set.

Run:  /tmp/isitai-bench/venv/bin/python bench/light/extract.py
"""
from __future__ import annotations

import json
import multiprocessing
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features as F  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
LIGHT = Path("/tmp/isitai-bench/light")
DATA = Path("/tmp/isitai-bench/data")
CHUNK_WORDS = 300


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def wikipedia():
    docs, chunks = [], []
    for path in sorted((ROOT / "corpus" / "text").glob("human-wikipedia-*.txt")):
        lang = path.name.split("-")[2]
        text = path.read_text(encoding="utf-8")
        base = {"id": path.name, "label": 0, "lang": lang, "domain": "wikipedia",
                "generator": "human", "group": path.name}
        docs.append({**base, "text": text})
        # Chunks cut at paragraph ends; a language without spaces is cut by characters.
        spaced = lang not in ("zh", "ja")
        size = (lambda t: len(t.split())) if spaced else (lambda t: len(t) // 2)
        current, n, k = [], 0, 0
        for para in [p for p in text.split("\n") if p.strip()]:
            current.append(para)
            n += size(para)
            if n >= CHUNK_WORDS:
                chunks.append({**base, "id": f"{path.name}#{k}", "text": "\n".join(current)})
                current, n, k = [], 0, k + 1
    return docs, chunks


def golden():
    rows = []
    base = ROOT / "bench" / "golden"
    for r in load_jsonl(base / "set" / "MANIFEST.jsonl"):
        text = (base / r["path"]).read_text(encoding="utf-8")
        true = r.get("true_class") or r["class"]
        rows.append({"id": r["path"], "text": text, "label": 1 if true == "ai" else 0,
                     "lang": r["lang"], "domain": f"golden-{r['class']}",
                     "generator": r["class"], "group": r["source"], "class": r["class"],
                     "transform": r["subclass"], "parents": r["parents"], "sha256": r["sha256"]})
    return rows


def one(text):
    a = F.analyse(text, with_hash=True)
    h = np.asarray(a["hash"], dtype=np.float32)
    idx = np.nonzero(h)[0]
    return a["n_words"], a["language"], [a["features"][k] for k in F.SCALAR_FEATURES], idx, h[idx]


def run(name, rows, pool):
    out = pool.map(one, [r["text"] for r in rows], chunksize=64)
    for r, (n, lang, _, _, _) in zip(rows, out):
        r["nw"] = n
        r["lang_detected"] = lang
    X = np.asarray([o[2] for o in out], dtype=np.float64)
    indptr = np.cumsum([0] + [len(o[3]) for o in out])
    H = sp.csr_matrix((np.concatenate([o[4] for o in out]), np.concatenate([o[3] for o in out]),
                       indptr), shape=(len(out), 1 << F.HASH_BITS), dtype=np.float32)
    meta = [{k: v for k, v in r.items() if k != "text"} for r in rows]
    (LIGHT / "feat").mkdir(parents=True, exist_ok=True)
    with open(LIGHT / "feat" / f"{name}.pkl", "wb") as f:
        pickle.dump({"rows": meta, "X": X, "hash": H, "features": F.SCALAR_FEATURES}, f)
    print(name, X.shape, file=sys.stderr)


def main():
    only = set(sys.argv[1:])
    sets = {"pool": lambda: load_jsonl(LIGHT / "pool.jsonl")}
    for split in ("test", "test_ood", "test_fr", "test_fiction", "test_attack"):
        sets[split] = (lambda s=split: load_jsonl(DATA / f"{s}.jsonl"))
    sets["wiki_docs"] = lambda: wikipedia()[0]
    sets["wiki_chunks"] = lambda: wikipedia()[1]
    sets["golden"] = golden
    with multiprocessing.Pool(8) as pool:
        for name, loader in sets.items():
            if not only or name in only:
                run(name, loader(), pool)


if __name__ == "__main__":
    main()
