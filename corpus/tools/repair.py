#!/usr/bin/env python3
"""Répare le corpus : retire le balisage parasite et reclasse les textes mal étiquetés.

Trois défauts, trois traitements distincts.

**Balisage** (`<think>`, HTML, Markdown) : retiré, jamais réécrit. Un texte nettoyé reste
le même texte ; le retoucher serait une réécriture déguisée.

**Langue** : un texte écrit en français dans un emplacement anglais est déplacé vers la
section française et renommé de façon explicite. On ne le supprime pas — il est correct,
c'est son étiquette qui était fausse — et l'emplacement d'origine devient libre, donc
régénéré dans la bonne langue.

**Fichiers corrompus** (caractères de remplacement, sortie tronquée en plein idéogramme) :
supprimés et retirés du manifeste. Un texte à moitié décodé n'est pas réparable.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from audit import detect  # noqa: E402  même détecteur que l'audit : sinon on répare à l'aveugle

CORPUS = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = CORPUS / "manifest.jsonl"

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
THINK_OPEN_RE = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)
HTML_RE = re.compile(r"</?[a-zA-Z][a-zA-Z0-9]{0,10}(\s[^<>]{0,120})?/?>")
BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1", re.DOTALL)
HEAD_RE = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
BULLET_RE = re.compile(r"^\s{0,3}[-*+]\s+", re.MULTILINE)
LINK_RE = re.compile(r"\[([^\]]{1,80})\]\((?:[^)]{0,200})\)")
META_START = ("we need", "the user", "okay,", "ok,", "let me", "i need to",
              "nous devons", "il faut rédiger", "l'utilisateur")


def strip_markup(text: str) -> tuple[str, int]:
    """Retire le balisage. Renvoie le texte et le nombre de retouches."""
    before = text
    text = THINK_RE.sub("", text)
    if "<think>" in text.lower():          # bloc non refermé : tout ce qui suit est du raisonnement
        text = THINK_OPEN_RE.sub("", text)
    text = HTML_RE.sub("", text)
    text = LINK_RE.sub(r"\1", text)
    text = BOLD_RE.sub(r"\2", text)
    text = HEAD_RE.sub("", text)
    text = BULLET_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text, (0 if text == before else 1)


def is_corrupt(text: str) -> bool:
    """Sortie inexploitable : décodage cassé ou remplissage de caractères inconnus."""
    if "\ufffd" in text:
        return True
    odd = sum(1 for c in text if 0x2500 <= ord(c) <= 0x259F)  # blocs et trames
    return odd > len(text) * 0.02


def looks_like_meta(text: str) -> bool:
    head = text.lstrip().lower()[:60]
    return any(head.startswith(prefix) for prefix in META_START)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
    kept, deleted, moved, cleaned = [], [], [], []

    for row in rows:
        path = CORPUS / row["fichier"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")

        if is_corrupt(text):
            deleted.append(row["id"])
            if not args.dry_run:
                path.unlink()
            continue

        text, touched = strip_markup(text)
        if looks_like_meta(text):
            deleted.append(row["id"])
            if not args.dry_run and path.exists():
                path.unlink()
            continue
        if touched:
            cleaned.append(row["id"])
            if not args.dry_run:
                path.write_text(text, encoding="utf-8", newline="\n")

        lang, conf = detect(text)
        if lang != row["langue"] and conf >= 0.04 and lang in ("en", "fr", "es", "pt", "it", "zh", "ar"):
            # Déplacé, pas supprimé : le contenu est bon, l'étiquette ne l'était pas.
            new_id = row["id"].replace(f"_{row['langue']}_", f"_{lang}_", 1) + "_reassignee"
            new_path = CORPUS / "ai" / lang / row["modele_id"] / f"{new_id}.txt"
            moved.append((row["id"], new_id, row["langue"], lang))
            if not args.dry_run:
                new_path.parent.mkdir(parents=True, exist_ok=True)
                new_path.write_text(text, encoding="utf-8", newline="\n")
                path.unlink()
                row = {**row, "id": new_id, "fichier": str(new_path.relative_to(CORPUS)),
                       "langue": lang, "langue_demandee": row["langue"]}
        kept.append(row)

    if not args.dry_run:
        MANIFEST.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept),
                            encoding="utf-8")
        for d in sorted((CORPUS / "ai").rglob("*"), key=lambda p: -len(p.parts)):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()

    print(f"  {len(rows)} entrées examinées")
    print(f"  balisage retiré : {len(cleaned)}")
    print(f"  supprimés (corrompus ou méta) : {len(deleted)}")
    for old, new, src, dst in moved[:5]:
        print(f"    {src} → {dst} : {new}")
    print(f"  déplacés vers leur vraie langue : {len(moved)}")
    print(f"  restants au manifeste : {len(kept)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
