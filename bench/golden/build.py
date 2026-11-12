#!/usr/bin/env python3
"""Construit le jeu doré de `isitai` et son manifeste.

Déterministe : la même entrée produit toujours les mêmes octets, donc les mêmes SHA-256.
Stdlib uniquement, pour que n'importe qui puisse le relancer sur une machine neuve.

    python3 bench/golden/build.py            # construit, refuse si une classe est incomplète
    python3 bench/golden/build.py --check    # vérifie les empreintes sans reconstruire
    python3 bench/golden/build.py --partial  # construit avec ce qui existe (diagnostic)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW = BASE / "raw"
SET = BASE / "set"
SEED = 20261112  # graine figée : la distribution du jeu ne doit pas dépendre du jour

TARGET_PER_CLASS = 100
CHUNK_WORDS = 400
MIN_CHUNK_WORDS = 150

FR = (" le ", " la ", " les ", " des ", " une ", " du ", " est ", " pour ")
EN = (" the ", " and ", " of ", " to ", " is ", " that ", " with ", " for ")

HOMOGLYPHS = {"a": "а", "e": "е", "o": "о", "c": "с", "p": "р", "x": "х"}


# ---------------------------------------------------------------- utilitaires

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def detect_lang(text: str) -> str:
    low = f" {text.lower()} "
    return "fr" if sum(low.count(w) for w in FR) > sum(low.count(w) for w in EN) else "en"


def strip_markup(text: str) -> str:
    """Retire frontmatter, blocs de code, liens et emphases markdown."""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>\-\*\+]+\s*", "", text, flags=re.M)
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_document(text: str) -> list[str]:
    """Découpe en segments d'environ CHUNK_WORDS, sans recouvrement (règle anti-fuite n°2)."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current, size = [], [], 0
    for para in paragraphs:
        words = para.split()
        if size and size + len(words) > CHUNK_WORDS:
            chunks.append("\n\n".join(current))
            current, size = [], 0
        current.append(para)
        size += len(words)
    if current:
        tail = "\n\n".join(current)
        # une queue trop courte est fusionnée, jamais publiée seule : elle ferait un
        # segment non représentatif que le détecteur jugerait sur du vide
        if chunks and len(tail.split()) < MIN_CHUNK_WORDS:
            chunks[-1] = chunks[-1] + "\n\n" + tail
        else:
            chunks.append(tail)
    return [c for c in chunks if len(c.split()) >= MIN_CHUNK_WORDS]


def record(path: str, text: str, cls: str, **extra) -> dict:
    return {"path": path, "sha256": sha256_text(text), "class": cls, **extra}


# ---------------------------------------------------------------- classes

def import_human_sources() -> list[dict]:
    """Importe une fois les textes humains dans raw/human (jeu autonome, donc reproductible)."""
    sources = [
        (Path("/home/hermes/work/blog-nuxt/content/blog"), "blog.accessdevops.com", "author:cbarange"),
        (Path("/home/hermes/work/isitai/docs"), "isitai/docs", "author:cbarange"),
        (Path("/home/hermes/work/s3site/content/guides"), "s3explorer guides", "author:cbarange"),
    ]
    RAW.joinpath("human").mkdir(parents=True, exist_ok=True)
    index = []
    for root, label, lic in sources:
        if not root.exists():
            continue
        for src in sorted(root.rglob("*.md")):
            body = strip_markup(src.read_text(encoding="utf-8", errors="ignore"))
            if len(body.split()) < MIN_CHUNK_WORDS:
                continue
            name = f"{label.split('.')[0]}-{src.stem}.txt".replace("/", "-")
            dest = RAW / "human" / name
            dest.write_text(body, encoding="utf-8")
            index.append({"file": f"raw/human/{name}", "source": f"{label}:{src.name}",
                          "license": lic, "words": len(body.split()),
                          "doc_sha256": sha256_text(body)})
    RAW.joinpath("human", "SOURCES.jsonl").write_text(
        "\n".join(json.dumps(i, ensure_ascii=False) for i in index) + "\n", encoding="utf-8")
    return index


def build_human() -> list[dict]:
    out = []
    for src in sorted((RAW / "human").glob("*.txt")):
        text = src.read_text(encoding="utf-8")
        doc_id = sha256_text(text)
        for i, chunk in enumerate(chunk_document(text)):
            name = f"human-{len(out) + 1:04d}.txt"
            (SET / "human" / name).write_text(chunk, encoding="utf-8")
            out.append(record(f"set/human/{name}", chunk, "human",
                              subclass=src.stem.split("-")[0], lang=detect_lang(chunk),
                              doc_id=doc_id, source=src.name, parents=[], transform=None,
                              license="author:cbarange", label_basis="provenance"))
    return out


def build_ai() -> list[dict]:
    out = []
    for folder in ("ai", "ai2"):
        root = RAW / folder
        if not root.exists():
            continue
        prov = {}
        pj = root / "PROVENANCE.jsonl"
        if pj.exists():
            for line in pj.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    prov[row["file"]] = row
        for src in sorted(root.glob("*.txt")):
            text = src.read_text(encoding="utf-8").strip()
            if len(text.split()) < 60:
                continue
            meta = prov.get(src.name, {})
            name = f"ai-{len(out) + 1:04d}.txt"
            (SET / "ai" / name).write_text(text, encoding="utf-8")
            out.append(record(f"set/ai/{name}", text, "ai",
                              subclass=f"gen-{folder}",
                              lang=(meta.get("lang") or detect_lang(text)),
                              doc_id=sha256_text(text), source=src.name, parents=[],
                              transform=None,
                              license=f"generated:{meta.get('generator', 'unknown')}/{meta.get('generated_at', '?')}",
                              label_basis="provenance"))
    return out


def build_mixed(humans: list[dict], ais: list[dict], rng: random.Random) -> list[dict]:
    """Insère un paragraphe IA à une frontière de phrase connue, et enregistre les offsets."""
    out = []
    pool = [a for a in ais if len(a.get("_text", "").split()) > 40]
    for i, human in enumerate(humans[:TARGET_PER_CLASS]):
        if not pool:
            break
        h = (SET / human["path"].split("set/")[1]).read_text(encoding="utf-8")
        ai = pool[i % len(pool)]
        paragraph = " ".join(ai["_text"].split("\n")[0].split(".")[:3]).strip() + "."
        sentences = re.split(r"(?<=[.!?])\s+", h)
        if len(sentences) < 4:
            continue
        at = rng.randint(len(sentences) // 3, (2 * len(sentences)) // 3)
        before, after = " ".join(sentences[:at]), " ".join(sentences[at:])
        composed = f"{before} {paragraph} {after}".strip()
        start = len(before) + 1
        name = f"mixed-{len(out) + 1:04d}.txt"
        (SET / "mixed" / name).write_text(composed, encoding="utf-8")
        out.append(record(f"set/mixed/{name}", composed, "mixed",
                          subclass="ai-insert",
                          lang=detect_lang(composed), doc_id=human["doc_id"],
                          source=human["source"], parents=[human["sha256"], ai["sha256"]],
                          transform=f"insert ai paragraph at char {start}..{start + len(paragraph)}",
                          license="mixed:authors + generated",
                          label_basis="provenance",
                          boundary=[start, start + len(paragraph)]))
    return out


def build_degraded(sources: list[dict], rng: random.Random) -> list[dict]:
    """Cinq transformations déterministes : elles changent la difficulté, pas la vérité."""
    def homoglyph(t: str) -> str:
        return "".join(HOMOGLYPHS.get(c, c) if rng.random() < 0.05 else c for c in t)

    def zero_width(t: str) -> str:
        words = t.split()
        return " ".join(w + ("\u200b" if i % 7 == 3 else "") for i, w in enumerate(words))

    def shuffle(t: str) -> str:
        paras = [p for p in t.split("\n\n") if p.strip()]
        rng.shuffle(paras)
        return "\n\n".join(paras)

    def truncate(t: str) -> str:
        words = t.split()
        return " ".join(words[: max(60, int(len(words) * 0.6))])

    def demark(t: str) -> str:
        return re.sub(r"[*_#>`]", "", t)

    transforms = {"homoglyph": homoglyph, "zero_width": zero_width,
                  "shuffle": shuffle, "truncate": truncate, "demark": demark}
    out = []
    for i, parent in enumerate(sources):
        text = parent["_text"]
        name_t, fn = list(transforms.items())[i % len(transforms)]
        altered = fn(text)
        name = f"degraded-{len(out) + 1:04d}.txt"
        (SET / "degraded" / name).write_text(altered, encoding="utf-8")
        out.append(record(f"set/degraded/{name}", altered, "degraded",
                          subclass=name_t, true_class=parent["class"],
                          lang=parent["lang"], doc_id=parent["doc_id"],
                          source=parent["source"], parents=[parent["sha256"]],
                          transform=name_t, license=parent["license"],
                          label_basis="provenance"))
    return out


# ---------------------------------------------------------------- manifeste

def write_manifest(rows: list[dict]) -> None:
    for row in rows:
        row.pop("_text", None)
    rows.sort(key=lambda r: r["path"])
    payload = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n"
    (SET / "MANIFEST.jsonl").write_text(payload, encoding="utf-8")
    (SET / "MANIFEST.sha256").write_text(sha256_text(payload) + "\n", encoding="utf-8")


def check() -> int:
    manifest = SET / "MANIFEST.jsonl"
    if not manifest.exists():
        print("aucun manifeste : lancer build.py d'abord", file=sys.stderr)
        return 1
    expected = (SET / "MANIFEST.sha256").read_text().strip()
    actual = sha256_text(manifest.read_text(encoding="utf-8"))
    ok = expected == actual
    print(f"  manifeste : {'intègre' if ok else 'MODIFIÉ depuis la construction'}")
    bad = 0
    for line in manifest.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        f = SET / row["path"].split("set/")[1]
        if not f.exists() or sha256_file(f) != row["sha256"]:
            bad += 1
            print(f"  empreinte invalide : {row['path']}")
    print(f"  fichiers vérifiés : {sum(1 for _ in manifest.open())} · anomalies : {bad}")
    return 0 if ok and bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--partial", action="store_true")
    ap.add_argument("--import-human", action="store_true")
    args = ap.parse_args()

    if args.check:
        return check()

    if args.import_human or not (RAW / "human").exists():
        print("import des sources humaines…")
        import_human_sources()

    for sub in ("human", "ai", "mixed", "degraded"):
        (SET / sub).mkdir(parents=True, exist_ok=True)
        for old in (SET / sub).glob("*.txt"):
            old.unlink()

    rng = random.Random(SEED)
    humans = build_human()
    ais = build_ai()
    for row in ais:
        row["_text"] = (SET / row["path"].split("set/")[1]).read_text(encoding="utf-8")

    mixed = build_mixed(humans, ais, rng)
    pool = []
    for row in humans[:60] + ais[:60]:
        row["_text"] = (SET / row["path"].split("set/")[1]).read_text(encoding="utf-8")
        pool.append(row)
    degraded = build_degraded(pool, rng)

    rows = humans + ais + mixed + degraded
    write_manifest(rows)

    counts = {}
    for row in rows:
        counts[row["class"]] = counts.get(row["class"], 0) + 1
    print(f"  classes : {counts}")
    print(f"  manifeste : {sha256_text((SET / 'MANIFEST.jsonl').read_text(encoding='utf-8'))[:16]}…")

    missing = [c for c in ("human", "ai", "mixed") if counts.get(c, 0) < TARGET_PER_CLASS]
    if missing and not args.partial:
        print(f"  INCOMPLET : {missing} — la construction est refusée (fail fast)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
