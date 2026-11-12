#!/usr/bin/env python
"""Builds the benchmark splits in /tmp/isitai-bench/data from the raw files in
/tmp/isitai-bench/raw (see fetch_data.sh). Deterministic: one seed, sorted inputs.

Output rows: {"id", "text", "label" (0 human, 1 ai), "source", "generator", "domain",
"lang", "n_words"}; test_attack rows also carry "attack".

Run:  /tmp/isitai-bench/venv/bin/python build_data.py
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

SEED = 20261112
RAW = "/tmp/isitai-bench/raw"
OUT = "/tmp/isitai-bench/data"
MIN_WORDS = 10

# RAID: what train and test never see.
RAID_OOD_DOMAINS = ["poetry", "reviews"]
RAID_OOD_GENERATORS = ["cohere-chat", "gpt4", "llama-chat"]

SIZES = {
    "train_sources": 2000,       # 2,000 human + 2,000 AI
    "test_sources": 1000,        # 1,000 human + 1,000 AI
    "ood_domain_sources": 150,   # held-out RAID domains, any generator
    "ood_generator_sources": 150,  # seen RAID domains, held-out generators
    "ood_mage_per_label": 100,
    "ood_hc3_per_label": 100,
    "attack_per_label": 500,
    "fr_reviews_per_label": 281,
    "fiction_per_label": 250,
}


def norm_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def text_hash(text: str) -> str:
    return hashlib.sha1(norm_text(text).encode()).hexdigest()


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKC", title or "").lower()).strip()


def n_words(text: str) -> int:
    return len(text.split())


def row(id_, text, label, source, generator, domain, lang, **extra):
    text = text.strip()
    out = {"id": id_, "text": text, "label": int(label), "source": source,
           "generator": generator, "domain": domain, "lang": lang, "n_words": n_words(text)}
    out.update(extra)
    return out


class Dedup:
    """Global registry of normalised text hashes: a text enters one split, once."""

    def __init__(self):
        self.seen = set()

    def take(self, text: str) -> bool:
        if n_words(text) < MIN_WORDS:
            return False
        h = text_hash(text)
        if h in self.seen:
            return False
        self.seen.add(h)
        return True


# ----------------------------------------------------------------------------- RAID

def load_jsonl(path):
    with open(path) as f:
        for line in f:
            yield json.loads(line)


def build_raid(rng: random.Random, dedup: Dedup):
    humans = {}                                  # source_id -> row
    gens = collections.defaultdict(list)         # source_id -> [rows]
    for r in load_jsonl(f"{RAW}/raid/none.jsonl"):
        if r["model"] == "human":
            humans[r["source_id"]] = r
        else:
            gens[r["source_id"]].append(r)
    attack_rows = collections.defaultdict(list)  # source_id -> [attacked rows]
    for r in load_jsonl(f"{RAW}/raid/attack.jsonl"):
        attack_rows[r["source_id"]].append(r)
    attack_sources = set(attack_rows)

    all_generators = sorted({g["model"] for rows in gens.values() for g in rows})
    domains = sorted({h["domain"] for h in humans.values()})
    seen_domains = [d for d in domains if d not in RAID_OOD_DOMAINS]
    seen_generators = [g for g in all_generators if g not in RAID_OOD_GENERATORS]
    print("RAID domains", domains, "generators", all_generators, file=sys.stderr)

    # A "group" is every source document that shares a normalised title in a domain:
    # the title is the prompt, so a group never straddles two splits.
    group_of = {}
    groups = collections.defaultdict(list)
    for sid, h in sorted(humans.items()):
        key = (h["domain"], norm_title(h["title"]) or sid)
        group_of[sid] = key
        groups[key].append(sid)
    attack_groups = {group_of[s] for s in attack_sources if s in group_of}

    # Shuffled list of usable groups per domain (attack-pool groups removed).
    per_domain = collections.defaultdict(list)
    for key in sorted(groups):
        if key not in attack_groups:
            per_domain[key[0]].append(key)
    for d in per_domain:
        rng.shuffle(per_domain[d])
    cursor = collections.Counter()

    def take_pairs(n_sources, doms, generators, source_name):
        """n_sources source documents spread evenly over `doms`; each gives its human
        text and one generation, generators taken in rotation."""
        out = []
        quota = {d: n_sources // len(doms) + (1 if i < n_sources % len(doms) else 0)
                 for i, d in enumerate(doms)}
        gi = 0
        for d in doms:
            got = 0
            while got < quota[d]:
                if cursor[d] >= len(per_domain[d]):
                    raise RuntimeError(f"RAID domain {d} exhausted")
                key = per_domain[d][cursor[d]]
                cursor[d] += 1
                sid = groups[key][0]     # one source per title group; the rest stay unused
                h = humans[sid]
                want = generators[gi % len(generators)]
                cands = [g for g in gens.get(sid, []) if g["model"] == want]
                rng.shuffle(cands)
                cand = next((g for g in cands
                             if n_words(g["generation"]) >= MIN_WORDS
                             and text_hash(g["generation"]) not in dedup.seen
                             and text_hash(g["generation"]) != text_hash(h["generation"])), None)
                if cand is None or n_words(h["generation"]) < MIN_WORDS \
                        or text_hash(h["generation"]) in dedup.seen:
                    continue
                assert dedup.take(h["generation"]) and dedup.take(cand["generation"])
                out.append(row(f"raid:{h['id']}", h["generation"], 0, source_name, "human", d, "en",
                               _group=key))
                out.append(row(f"raid:{cand['id']}", cand["generation"], 1, source_name,
                               cand["model"], d, "en", _group=key))
                gi += 1
                got += 1
        return out

    train = take_pairs(SIZES["train_sources"], seen_domains, seen_generators, "raid")
    test = take_pairs(SIZES["test_sources"], seen_domains, seen_generators, "raid")
    ood_dom = take_pairs(SIZES["ood_domain_sources"], RAID_OOD_DOMAINS, all_generators, "raid")
    ood_gen = take_pairs(SIZES["ood_generator_sources"], seen_domains, RAID_OOD_GENERATORS, "raid")

    # test_attack: attacked variants of the attack-pool sources. Originals are taken in
    # shuffled order and attacks in rotation, so the 11 attacks are evenly represented.
    # An AI original gives one attacked variant; the pool holds only ~250 human originals,
    # so a human original gives two variants, under two different attacks.
    variants = collections.defaultdict(dict)     # adv_source_id -> {attack: row}
    for sid in sorted(attack_rows):
        for r in attack_rows[sid]:
            variants[r["adv_source_id"]][r["attack"]] = r
    attacks = sorted({a for v in variants.values() for a in v})
    attack = []
    for label, per_original in ((0, 2), (1, 1)):
        originals = sorted(k for k, v in variants.items()
                           if (next(iter(v.values()))["model"] == "human") == (label == 0))
        rng.shuffle(originals)
        got, ai = 0, 0
        for _pass in range(per_original):
            for adv in originals:
                if got >= SIZES["attack_per_label"]:
                    break
                # rotation offset by the pass so the second variant uses another attack
                for step in range(len(attacks)):
                    a = attacks[(ai + step) % len(attacks)]
                    r = variants[adv].get(a)
                    if r is not None and not r.get("_used") and dedup.take(r["generation"]):
                        r["_used"] = True
                        attack.append(row(f"raid:{r['id']}", r["generation"], label, "raid",
                                          r["model"], r["domain"], "en", attack=a,
                                          _group=group_of.get(r["source_id"], ("?", r["source_id"]))))
                        got += 1
                        ai += 1
                        break
    info = {"domains": domains, "generators": all_generators,
            "seen_domains": seen_domains, "seen_generators": seen_generators,
            "attack_pool_sources": len(attack_sources), "attacks": attacks,
            "human_sources": len(humans)}
    return train, test, ood_dom + ood_gen, attack, info


# ----------------------------------------------------------------------------- MAGE / HC3

def build_mage(rng, dedup):
    """MAGE test_ood_set_gpt.csv: GPT-4 on four domains (label column: 1 human, 0 machine)."""
    with open(f"{RAW}/mage/test_ood_set_gpt.csv", newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for i, r in enumerate(rows):
        r["_i"] = i
    out = []
    for label, mage_label in ((0, "1"), (1, "0")):
        pool = [r for r in rows if r["label"] == mage_label]
        by_dom = collections.defaultdict(list)
        for r in pool:
            by_dom[r["src"].rsplit("_", 1)[0]].append(r)
        doms = sorted(by_dom)
        for d in doms:
            rng.shuffle(by_dom[d])
        n = SIZES["ood_mage_per_label"]
        # dialogsum has no long texts; share evenly over the domains present for the label
        for i, d in enumerate(doms):
            want = n // len(doms) + (1 if i < n % len(doms) else 0)
            got = 0
            for r in by_dom[d]:
                if got >= want:
                    break
                if dedup.take(r["text"]):
                    out.append(row(f"mage:ood_gpt:{r['_i']}", r["text"], label, "mage",
                                   "human" if label == 0 else "gpt4", f"mage-{d}", "en"))
                    got += 1
    return out


def build_hc3(rng, dedup):
    """HC3 English test questions (file shipped in almanach/hc3_french_ood): human answers
    and ChatGPT (gpt-3.5, Dec 2022 - Jan 2023) answers."""
    with open(f"{RAW}/hc3fr/x/data/hc3_en/test_qa_examples.json") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    out = []
    for label in (0, 1):
        pool = [r for r in rows if bool(r["is_human"]) == (label == 0)]
        rng.shuffle(pool)
        got = 0
        for r in pool:
            if got >= SIZES["ood_hc3_per_label"]:
                break
            if dedup.take(r["answer"]):
                out.append(row(f"hc3:en:{r['id']}:{r['entry_id']}:{label}", r["answer"], label, "hc3",
                               "human" if label == 0 else "chatgpt", f"hc3-{r['source']}", "en"))
                got += 1
    return out


# ----------------------------------------------------------------------------- French

def length_match(targets, pool, rng):
    """For each target length, the unused pool item with the closest word count."""
    pool = sorted(pool, key=lambda t: (n_words(t[1]), t[0]))
    used = [False] * len(pool)
    lens = [n_words(t[1]) for t in pool]
    import bisect
    picked = []
    for want in targets:
        i = bisect.bisect_left(lens, want)
        best = None
        for j in range(max(0, i - 200), min(len(pool), i + 200)):
            if not used[j] and (best is None or abs(lens[j] - want) < abs(lens[best] - want)):
                best = j
        if best is None:
            continue
        used[best] = True
        picked.append(pool[best])
    return picked


def build_french(rng, dedup):
    base = f"{RAW}/hc3fr/x/data"
    ai = []
    # Native French ChatGPT answers (the 113 rows that carry `chatgpt_answer`).
    for r in load_jsonl(f"{base}/hc3_fr_chatgpt/test_qa_examples_chatgpt.jsonl"):
        ans = r.get("chatgpt_answer")
        if isinstance(ans, list) and ans and isinstance(ans[0], str) and dedup.take(ans[0]):
            ai.append(row(f"hc3fr:chatgpt_native:{r['id']}:{r['entry_id']}", ans[0], 1, "hc3_french_ood",
                          "chatgpt", "qa", "fr"))
    for i, r in enumerate(load_jsonl(f"{base}/qa_binggpt.jsonl")):
        # two Bing answers are English refusals ("I am sorry, I don't know how to ...")
        if isinstance(r.get("answer"), str) and not r["answer"].lstrip().startswith("I am sorry") \
                and dedup.take(r["answer"]):
            ai.append(row(f"hc3fr:binggpt:{i}", r["answer"], 1, "hc3_french_ood",
                          "bing-chat", "qa", "fr"))
    human = []
    # Human answers written in the style of Bing Chat (the "Adversarial" subset).
    for i, r in enumerate(load_jsonl(f"{base}/qa_binglikehuman.jsonl")):
        if isinstance(r.get("answer"), str) and dedup.take(r["answer"]):
            human.append(row(f"hc3fr:binglikehuman:{i}", r["answer"], 0, "hc3_french_ood",
                             "human", "qa", "fr"))
    # Human FAQ answers (MQA fr-faq-page), length-matched to the remaining AI answers.
    faq = []
    for name in ("faq_fr_gouv", "faq_fr_random"):
        for i, r in enumerate(load_jsonl(f"{base}/{name}.jsonl")):
            if isinstance(r.get("answer"), str) and n_words(r["answer"]) >= MIN_WORDS:
                faq.append((f"hc3fr:{name}:{i}", r["answer"]))
    rng.shuffle(faq)
    ai_lens = sorted(r["n_words"] for r in ai)
    human_lens = sorted(r["n_words"] for r in human)
    # targets: AI lengths not already covered by the 61 adversarial human answers
    need = len(ai) - len(human)
    targets = rng.sample(ai_lens, need)
    for id_, text in length_match(targets, faq, rng):
        if dedup.take(text):
            human.append(row(id_, text, 0, "hc3_french_ood", "human", "faq", "fr"))

    # MAiDE-up French hotel reviews: source 0 = Booking.com (human), 1 = GPT-4.
    with open(f"{RAW}/maideup/all_data.csv", newline="", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r["Review_Language"] == "French"]
    for label, src in ((0, "0"), (1, "1")):
        pool = [r for r in rows if r["source"] == src]
        rng.shuffle(pool)
        got = 0
        for r in pool:
            if got >= SIZES["fr_reviews_per_label"]:
                break
            parts = [r[k].strip() for k in ("Upside_Review", "Downside_Review")
                     if r[k] and r[k].strip() and r[k].strip().lower() != "nan"]
            text = "\n".join(parts)
            if dedup.take(text):
                target = human if label == 0 else ai
                target.append(row(f"maideup:fr:{'human' if label == 0 else 'gpt4'}:{r['']}", text, label, "maide-up",
                                  "human" if label == 0 else "gpt4", "reviews", "fr"))
                got += 1
    n = min(len(ai), len(human))
    return human[:n] + ai[:n] if len(ai) != len(human) else human + ai


# ----------------------------------------------------------------------------- Fiction

def detok_wp(text: str) -> str:
    """Undoes the tokenisation of the fairseq WritingPrompts archive (spaced quotes,
    `<newline>` tokens, split contractions)."""
    t = text.replace("<newline>", "\n")
    t = re.sub(r"[ \t]*\n[ \t]*", "\n", t)
    t = t.replace("``", "\u201c").replace("''", "\u201d")
    t = re.sub(r"\u201c ", "\u201c", t)
    t = re.sub(r" \u201d", "\u201d", t)
    t = re.sub(r"(\w) \u2019 (\w)", "\\1\u2019\\2", t)       # don ’ t -> don’t
    t = re.sub(r"(\w) ' (\w)", r"\1'\2", t)
    t = re.sub(r"\u2018 ", "\u2018", t)
    t = re.sub(r" \u2019", "\u2019", t)
    t = re.sub(r" (n't|'s|'re|'ve|'m|'ll|'d)\b", r"\1", t)
    t = re.sub(r" ([.,!?;:])", r"\1", t)
    t = re.sub(r"\( ", "(", t)
    t = re.sub(r" \)", ")", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def truncate_paragraphs(text: str, max_words: int) -> str:
    """Whole paragraphs from the start, up to max_words (at least one paragraph)."""
    out, total = [], 0
    for para in re.split(r"\n\s*\n", text.strip()):
        w = n_words(para)
        if out and total + w > max_words:
            break
        out.append(para.strip())
        total += w
    return "\n\n".join(out)


def build_fiction(rng, dedup):
    import pandas as pd
    wp = pd.read_parquet(f"{RAW}/wp/test.parquet")
    humans = []
    order = list(range(len(wp)))
    rng.shuffle(order)
    for i in order:
        if len(humans) >= SIZES["fiction_per_label"]:
            break
        story = detok_wp(wp.story.iloc[i])
        if n_words(story) >= 1000 and dedup.take(story):
            humans.append(row(f"wp:test:{i}", story, 0, "writingprompts", "human", "fiction", "en"))

    ss = pd.read_parquet(f"{RAW}/storyscope/stories_test.parquet")
    cols = {"story_gpt": "gpt-5.4", "story_claude": "claude-sonnet-4.6",
            "story_deepseek": "deepseek-v3.2", "story_kimi": "kimi-k2.5",
            "story_gemini": "gemini-3-flash"}
    order = list(range(len(ss)))
    rng.shuffle(order)
    ai = []
    names = sorted(cols)
    k = 0
    for h_i, h in enumerate(humans):
        # one story per prompt, generators in rotation, cut to the paired human length
        while True:
            r = ss.iloc[order[k]]
            k += 1
            col = names[h_i % len(names)]
            story = r[col]
            if not isinstance(story, str) or n_words(story) < h["n_words"]:
                continue
            cut = truncate_paragraphs(story, h["n_words"])
            if n_words(cut) < 0.7 * h["n_words"] or not dedup.take(cut):
                continue
            ai.append(row(f"storyscope:test:{int(r['prompt_id'])}:{col[6:]}", cut, 1, "storyscope",
                          cols[col], "fiction", "en"))
            break
    return humans + ai


# ----------------------------------------------------------------------------- main

def write(name, rows, rng):
    rows = list(rows)
    rng.shuffle(rows)
    path = f"{OUT}/{name}.jsonl"
    with open(path + ".tmp", "w") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")},
                               ensure_ascii=False) + "\n")
    os.replace(path + ".tmp", path)


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = random.Random(SEED)
    dedup = Dedup()
    train, test, ood, attack, info = build_raid(rng, dedup)
    ood = ood + build_mage(rng, dedup) + build_hc3(rng, dedup)
    fr = build_french(rng, dedup)
    fiction = build_fiction(rng, dedup)
    splits = {"train": train, "test": test, "test_ood": ood, "test_fr": fr,
              "test_fiction": fiction, "test_attack": attack}

    # Leakage checks (hard failures).
    ids, hashes, groups = {}, {}, {}
    for name, rows in splits.items():
        ids[name] = {r["id"] for r in rows}
        hashes[name] = {text_hash(r["text"]) for r in rows}
        groups[name] = {r["_group"] for r in rows if "_group" in r}
        assert len(ids[name]) == len(rows), f"duplicate id in {name}"
        assert len(hashes[name]) == len(rows), f"duplicate text in {name}"
    names = list(splits)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not ids[a] & ids[b], f"id shared by {a} and {b}"
            assert not hashes[a] & hashes[b], f"text shared by {a} and {b}"
            assert not groups[a] & groups[b], f"RAID source/title shared by {a} and {b}"
    seen_gen = set(info["seen_generators"]) | {"human"}
    for name in ("train", "test"):
        assert {r["generator"] for r in splits[name]} <= seen_gen
        assert not {r["domain"] for r in splits[name]} & set(RAID_OOD_DOMAINS)
        assert all("attack" not in r for r in splits[name])

    manifest = {"seed": SEED, "raid": info, "sizes": SIZES, "splits": {}}
    for name, rows in splits.items():
        write(name, rows, rng)
        c = collections.Counter
        manifest["splits"][name] = {
            "n": len(rows),
            "label": dict(sorted(c(r["label"] for r in rows).items())),
            "lang": dict(sorted(c(r["lang"] for r in rows).items())),
            "source_x_label": {f"{k[0]}|{k[1]}": v for k, v in
                               sorted(c((r["source"], r["label"]) for r in rows).items())},
            "generator": dict(sorted(c(r["generator"] for r in rows).items())),
            "domain_x_label": {f"{k[0]}|{k[1]}": v for k, v in
                               sorted(c((r["domain"], r["label"]) for r in rows).items())},
            "attack": dict(sorted(c(r["attack"] for r in rows if "attack" in r).items())),
            "n_words_median": {str(l): sorted(r["n_words"] for r in rows if r["label"] == l)
                               [len([r for r in rows if r["label"] == l]) // 2] for l in (0, 1)},
        }
    manifest["leakage_checks"] = [
        "unique id within each split", "unique normalised text (NFKC, lowercase, collapsed "
        "whitespace, SHA-1) within each split",
        "no id shared by two splits", "no normalised text shared by two splits",
        "no RAID (domain, normalised title) group shared by two splits; one source document "
        "per group", "train/test hold no held-out RAID generator, no held-out RAID domain, "
        "no attacked row", "RAID attack-pool sources (sha1(source_id) % 100 < 2) appear "
        "only in test_attack",
    ]
    with open(f"{OUT}/manifest.json", "w") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False)
    print(json.dumps(manifest["splits"], indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
