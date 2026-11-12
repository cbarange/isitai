# -*- coding: utf-8 -*-
import json, re, unicodedata
from pathlib import Path

OUT = Path("/home/hermes/work/isitai/bench/golden/raw/ai2")

TOPICS = {
    1: "fonctionnement d'un cache",
    2: "explication d'un impot",
    3: "entretien d'une chaudiere",
    4: "choix d'un velo",
    5: "organisation d'un demenagement",
    6: "mecanique d'une horloge",
    7: "gestion d'un stock",
    8: "securite d'un mot de passe",
    9: "description d'un paysage",
    10: "methode de travail",
}
REGISTERS = [
    ("technique sec", "technique"),
    ("vulgarisation", "vulgarisation"),
    ("argumentatif", "argumentatif"),
    ("narratif", "narratif"),
    ("procédural", "procedural"),
]
GEN = "deepseek-v4.1-flash (Hermes Agent subagent, provider opencode-go)"
DATE = "2026-11-12"

rows = []
problems = []

for i in range(1, 51):
    lang = "fr" if i % 2 == 1 else "en"
    topic = (i - 1) % 10 + 1
    reg_label, reg_slug = REGISTERS[(i - 1) // 10]
    name = f"ai2-{i:02d}-{lang}.txt"
    p = OUT / name
    text = p.read_text(encoding="utf-8").strip()

    n_sent = len(re.findall(r"[.!?]+(?=\s|$)", text))
    if not 8 <= n_sent <= 12:
        problems.append(f"{name}: {n_sent} phrases")
    if "\n" in text:
        problems.append(f"{name}: saut de ligne interne")
    if re.search(r"(^|\s)(#{1,6}\s|[-*+]\s|\d+\.\s|>\s|\|)", text):
        problems.append(f"{name}: marqueur markdown/liste")
    if re.search(r"[*_`\[\]<>|]", text):
        problems.append(f"{name}: caractere markdown")
    for ch in text:
        if ord(ch) > 0x2100 and unicodedata.category(ch) == "So":
            problems.append(f"{name}: emoji/symbole {ch!r}")
            break

    rows.append({
        "file": name,
        "lang": lang,
        "topic_id": topic,
        "register": reg_label,
        "generator": GEN,
        "generated_at": DATE,
        "prompt_id": f"p02-t{topic}-{reg_slug}-{lang}",
    })

with (OUT / "PROVENANCE.jsonl").open("w", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

txt = sorted(OUT.glob("ai2-*.txt"))
sizes = [p.stat().st_size for p in txt]
lines = sum(1 for _ in (OUT / "PROVENANCE.jsonl").open(encoding="utf-8"))
langs = {}
for r in rows:
    langs[r["lang"]] = langs.get(r["lang"], 0) + 1

print("problemes:", problems if problems else "aucun")
print("fichiers txt:", len(txt))
print("lignes jsonl:", lines)
print("tailles:", min(sizes), max(sizes))
print("langues:", langs)
print("registres:", sorted({r["register"] for r in rows}))
good = True
for reg, _ in REGISTERS:
    got = sorted(r["topic_id"] for r in rows if r["register"] == reg)
    if got != list(range(1, 11)):
        good = False
print("un sujet par registre (1-10) :", good)
print("premiere ligne:", json.dumps(rows[0], ensure_ascii=False))
