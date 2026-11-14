#!/usr/bin/env python3
"""Audit du corpus : langue réellement écrite et balisage parasite.

Deux défauts cherchés ici, tous deux invisibles à l'œil sur 600 fichiers :

1. **Langue** — une consigne de style rédigée en français fait basculer la sortie en
   français même quand la langue demandée est l'anglais. Le fichier porte alors un nom
   anglais et un contenu français.
2. **Balisage** — du HTML ou du Markdown dans un texte censé être du texte brut fausse
   toute mesure de longueur et tout détecteur qui lit les balises.

Aucune dépendance : un détecteur à mots outils suffit pour des textes de plus de trente
mots, et il est lisible — donc vérifiable.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import unicodedata

CORPUS = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = CORPUS / "manifest.jsonl"

STOPWORDS = {
    "en": "the and of to is that in it you for with on as are be this have from not but they we your was were been has had will would can could there their which when what how all more than into about after before over such only also these those".split(),
    "fr": "le la les de des du et est que qui dans pour pas une un sur au aux avec ce il elle nous vous sont plus mais ou où donc car ne se sa son leur leurs cette ces était être avoir fait comme tout tous".split(),
    "es": "el la los las de que y en un una es por con para se del al lo como más pero sus le su está son fue han pero entre cuando donde también".split(),
    "pt": "o a os as de que e em um uma é por com para se do da no na mais como dos das ao aos pelo pela são foi ser ter sua seu".split(),
    "it": "il la gli le di che e in un una è per con si del della al lo come più ma dei delle nel nella sono era essere stato".split(),
}
# Écritures non latines : la présence de caractères suffit, pas besoin de mots outils.
SCRIPTS = {"zh": (0x4E00, 0x9FFF), "ar": (0x0600, 0x06FF)}
TAG_RE = re.compile(r"</?([a-zA-Z][a-zA-Z0-9]{0,10})(\s[^<>]{0,80})?/?>")
MD_RE = re.compile(r"(\*\*[^*\n]{1,80}\*\*|^#{1,6}\s|^\s*[-*]\s)", re.MULTILINE)


def detect(text: str) -> tuple[str, float]:
    """Langue détectée et part des mots outils reconnus.

    Une part faible signifie « je ne sais pas » : un texte de 30 mots peut n'employer
    aucun mot outil. On renvoie alors une confiance basse plutôt qu'une langue fausse.
    """
    tokens = re.findall(r"[a-zA-ZÀ-ÿ']+", text.lower())
    for lang, (lo, hi) in SCRIPTS.items():
        chars = sum(1 for c in text if lo <= ord(c) <= hi)
        if chars >= 15 and chars / max(1, len(text)) > 0.15:
            return lang, 1.0
    if not tokens:
        return "?", 0.0
    scores = {}
    for lang, words in STOPWORDS.items():
        vocab = set(words)
        scores[lang] = sum(1 for t in tokens if t in vocab) / len(tokens)
    best = max(scores, key=scores.get)
    return best, scores[best]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="sortie machine")
    ap.add_argument("--min-confidence", type=float, default=0.04)
    args = ap.parse_args()

    rows = [json.loads(l) for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
    mismatches, marked_up, weak = [], [], []
    tags_seen = collections.Counter()

    for r in rows:
        path = CORPUS / r["fichier"]
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        lang, conf = detect(text)
        if lang != r["langue"] and conf >= args.min_confidence:
            mismatches.append({**r, "detecte": lang, "confiance": round(conf, 3)})
        elif lang == "?" or conf < args.min_confidence:
            weak.append({**r, "detecte": lang, "confiance": round(conf, 3)})

        tags = TAG_RE.findall(text)
        md = MD_RE.findall(text)
        if tags or md:
            for name, _ in tags:
                tags_seen[name.lower()] += 1
            marked_up.append({**r, "balises": len(tags), "markdown": len(md),
                              "noms": sorted({t[0].lower() for t in tags})})

    if args.json:
        print(json.dumps({"mismatches": mismatches, "marked_up": marked_up, "weak": weak},
                         ensure_ascii=False, indent=1))
        return 0

    print(f"  {len(rows)} textes audités")
    print(f"  langue inattendue : {len(mismatches)}")
    per = collections.Counter((m["langue"], m["detecte"]) for m in mismatches)
    for (attendu, trouve), n in per.most_common():
        print(f"    {trouve} → annoncé {attendu} : {n}")
    print(f"  balisage parasite : {len(marked_up)}")
    for name, n in tags_seen.most_common(12):
        print(f"    <{name}> × {n}")
    print(f"  confiance trop faible pour trancher : {len(weak)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
