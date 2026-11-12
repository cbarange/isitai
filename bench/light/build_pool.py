#!/usr/bin/env python
"""Builds the training / calibration pool of the light text score.

Reads the raw files of the detector benchmark (/tmp/isitai-bench/raw, see
bench/detectors/fetch_data.sh) and writes /tmp/isitai-bench/light/pool.jsonl.
Nothing of the five benchmark test splits may enter the pool: exclusion is by
normalised text hash, by RAID (domain, title) group (attack pool included) and by
HC3 question id across English and French. The script asserts a zero overlap.

Kept out on purpose, so that test_ood stays out of distribution: the RAID domains
poetry and reviews, and the RAID generators gpt4, cohere-chat, llama-chat.

Run:  /tmp/isitai-bench/venv/bin/python bench/light/build_pool.py
"""
from __future__ import annotations

import collections
import csv
import hashlib
import json
import os
import random
import re
import sys
import unicodedata

SEED = 20261113
RAW = "/tmp/isitai-bench/raw"
DATA = "/tmp/isitai-bench/data"
OUT = "/tmp/isitai-bench/light"
TEST_SPLITS = ("test", "test_ood", "test_fr", "test_fiction", "test_attack")
MIN_WORDS = 40                      # pool floor; the detector's own floor is decided later
RAID_OOD_DOMAINS = {"poetry", "reviews"}
RAID_OOD_GENERATORS = {"cohere-chat", "gpt4", "llama-chat"}
RAID_SOURCES_PER_DOMAIN = 700
HC3_PER_SOURCE_LABEL = 500
HC3FR_PER_SOURCE_LABEL = 300
FAQ_FR = 1200
MAIDE_LANG = {"French": "fr", "English": "en", "German": "de", "Italian": "it",
              "Spanish": "es", "Romanian": "ro", "Russian": "ru", "Turkish": "tr",
              "Chinese": "zh", "Korean": "ko"}

csv.field_size_limit(10 ** 9)


def norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text).lower()).strip()


def text_hash(text: str) -> str:
    return hashlib.sha1(norm_text(text).encode()).hexdigest()


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKC", title or "").lower()).strip()


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def main() -> int:
    rng = random.Random(SEED)
    os.makedirs(OUT, exist_ok=True)

    test_hashes, test_raid_ids, test_hc3_ids = set(), set(), set()
    for split in TEST_SPLITS:
        for r in load_jsonl(f"{DATA}/{split}.jsonl"):
            test_hashes.add(text_hash(r["text"]))
            if r["id"].startswith("raid:"):
                test_raid_ids.add(r["id"][5:])
            elif r["id"].startswith(("hc3:en:", "hc3fr:chatgpt_native:")):
                test_hc3_ids.add(str(r["id"].split(":")[2]))
    # Every HC3 question of a test or validation file, in either language, is excluded.
    base = f"{RAW}/hc3fr/x/data"
    for name in ("hc3_en/test_qa_examples.json", "hc3_en/val_qa_examples.json",
                 "hc3_fr/test_qa_examples.json", "hc3_fr/val_qa_examples.json",
                 "hc3_fr_chatgpt/test_qa_examples.jsonl",
                 "hc3_fr_chatgpt/test_qa_examples_chatgpt.jsonl"):
        for r in load_jsonl(f"{base}/{name}"):
            test_hc3_ids.add(str(r["id"]))

    pool, seen = [], set(test_hashes)

    def add(id_, text, label, lang, domain, generator, group):
        text = text.strip()
        n = len(text.split())
        if n < MIN_WORDS and lang not in ("zh", "ko"):
            return False
        h = text_hash(text)
        if h in seen:
            return False
        seen.add(h)
        pool.append({"id": id_, "text": text, "label": label, "lang": lang, "domain": domain,
                     "generator": generator, "group": group, "n_words": n})
        return True

    # ------------------------------------------------------------------ RAID
    humans, gens, titles = {}, collections.defaultdict(list), {}
    for r in load_jsonl(f"{RAW}/raid/none.jsonl"):
        titles[r["id"]] = (r["domain"], norm_title(r["title"]) or r["source_id"])
        if r["domain"] in RAID_OOD_DOMAINS:
            continue
        if r["model"] == "human":
            humans[r["source_id"]] = r
        elif r["model"] not in RAID_OOD_GENERATORS:
            gens[r["source_id"]].append(r)
    banned_groups = {titles[i] for i in test_raid_ids if i in titles}
    for r in load_jsonl(f"{RAW}/raid/attack.jsonl"):
        banned_groups.add((r["domain"], norm_title(r["title"]) or r["source_id"]))
    by_domain = collections.defaultdict(dict)       # domain -> group -> source id
    for sid, h in sorted(humans.items()):
        g = titles[h["id"]]
        if g not in banned_groups:
            by_domain[h["domain"]].setdefault(g, sid)
    generators = sorted({g["model"] for rows in gens.values() for g in rows})
    gi = 0
    for domain in sorted(by_domain):
        groups = sorted(by_domain[domain])
        rng.shuffle(groups)
        got = 0
        for g in groups:
            if got >= RAID_SOURCES_PER_DOMAIN:
                break
            sid = by_domain[domain][g]
            h = humans[sid]
            want = generators[gi % len(generators)]
            cands = [c for c in gens.get(sid, []) if c["model"] == want]
            if not cands:
                continue
            c = rng.choice(cands)
            gid = f"raid:{domain}:{g[1]}"
            if len(h["generation"].split()) < MIN_WORDS or len(c["generation"].split()) < MIN_WORDS:
                continue
            if add(f"raid:{h['id']}", h["generation"], 0, "en", f"raid-{domain}", "human", gid):
                add(f"raid:{c['id']}", c["generation"], 1, "en", f"raid-{domain}", c["model"], gid)
                gi += 1
                got += 1
    del humans, gens

    # ------------------------------------------------------------------ HC3 (train files only)
    for sub, lang, tag, cap in (("hc3_en", "en", "hc3", HC3_PER_SOURCE_LABEL),
                                ("hc3_fr", "fr", "hc3fr-mt", HC3FR_PER_SOURCE_LABEL)):
        rows = [r for r in load_jsonl(f"{base}/{sub}/train_qa_examples.json")
                if str(r["id"]) not in test_hc3_ids and isinstance(r.get("answer"), str)]
        rng.shuffle(rows)
        count = collections.Counter()
        for r in rows:
            label = 0 if r["is_human"] else 1
            key = (r["source"], label)
            if count[key] >= cap:
                continue
            if add(f"{tag}:{r['id']}:{r['entry_id']}:{label}", r["answer"], label, lang,
                   f"{tag}-{r['source']}", "human" if label == 0 else "chatgpt",
                   f"{tag}:{r['id']}"):
                count[key] += 1

    # ------------------------------------------------------------------ MAGE (rows not in test_ood)
    with open(f"{RAW}/mage/test_ood_set_gpt.csv", newline="", encoding="utf-8-sig") as f:
        for i, r in enumerate(csv.DictReader(f)):
            label = 0 if r["label"] == "1" else 1
            d = r["src"].rsplit("_", 1)[0]
            add(f"mage:ood_gpt:{i}", r["text"], label, "en", f"mage-{d}",
                "human" if label == 0 else "gpt4", f"mage:{i}")

    # ------------------------------------------------------------------ MAiDE-up hotel reviews
    with open(f"{RAW}/maideup/all_data.csv", newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            lang = MAIDE_LANG.get(r["Review_Language"])
            if lang is None:
                continue
            parts = [r[k].strip() for k in ("Upside_Review", "Downside_Review")
                     if r[k] and r[k].strip() and r[k].strip().lower() != "nan"]
            label = int(r["source"])
            add(f"maideup:{lang}:{r['']}", "\n".join(parts), label, lang, f"reviews-{lang}",
                "human" if label == 0 else "gpt4", f"maideup:{r['']}")

    # ------------------------------------------------------------------ French FAQ (human only)
    faq = []
    for name in ("faq_fr_gouv", "faq_fr_random"):
        for i, r in enumerate(load_jsonl(f"{base}/{name}.jsonl")):
            if isinstance(r.get("answer"), str):
                faq.append((f"hc3fr:{name}:{i}", r["answer"], r.get("domain") or name))
    rng.shuffle(faq)
    got = 0
    for id_, text, site in faq:
        if got >= FAQ_FR:
            break
        if add(id_, text, 0, "fr", "faq-fr", "human", f"faq:{site}"):
            got += 1

    # ------------------------------------------------------------------ leakage checks
    assert not {text_hash(r["text"]) for r in pool} & test_hashes, "text shared with a test split"
    assert not {r["id"][5:] for r in pool if r["id"].startswith("raid:")} & test_raid_ids
    assert not {r["group"] for r in pool if r["id"].startswith("raid:")} & {
        f"raid:{d}:{t}" for d, t in banned_groups}, "RAID title group shared with a test split"
    assert not {r["id"].split(":")[1] for r in pool if r["id"].startswith("hc3")
                and not r["id"].startswith("hc3fr:faq")} & test_hc3_ids
    print("overlap with test splits: 0 texts, 0 RAID ids, 0 RAID title groups, 0 HC3 questions",
          file=sys.stderr)

    rng.shuffle(pool)
    with open(f"{OUT}/pool.jsonl", "w", encoding="utf-8") as f:
        for r in pool:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    table = collections.Counter()
    for r in pool:
        for floor in (40, 80, 100, 150):
            if r["n_words"] >= floor:
                table[(r["lang"], r["domain"], r["label"], floor)] += 1
    print("lang domain label n>=40 n>=80 n>=100 n>=150")
    for lang, domain, label in sorted({k[:3] for k in table}):
        print(lang, domain, label, *(table[(lang, domain, label, f)] for f in (40, 80, 100, 150)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
