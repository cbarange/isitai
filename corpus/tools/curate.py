#!/usr/bin/env python3
"""Ramène le corpus à la répartition demandée, sans perdre la diversité.

Les workers ont tourné avec des plans successifs : les mêmes emplacements (langue,
domaine, longueur) ont reçu des identifiants différents, donc plus de textes que la
cible. Ce script garde exactement le nombre demandé par langue, en répartissant la
sélection sur tous les couples (domaine, modèle) plutôt qu'en prenant les premiers.

Les textes écartés restent dans l'historique git : rien n'est perdu, seulement non
retenu dans le corpus publié.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

CORPUS = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = CORPUS / "manifest.jsonl"
# Proportions de la demande initiale (1 000/800/700/550/400/300/250 sur 4 000), à
# l'échelle de 600. Total : 600.
TARGETS = {"en": 150, "fr": 120, "es": 105, "pt": 83, "zh": 60, "ar": 45, "it": 37}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in MANIFEST.read_text(encoding="utf-8").splitlines() if l.strip()]
    # Les textes réaffectés ne comptent pas dans la répartition : ils ont été déplacés
    # parce qu'ils étaient dans la mauvaise langue, pas pour compléter un quota. Les
    # élaguer reviendrait à supprimer le travail de réparation.
    reassigned = [r for r in rows if "langue_demandee" in r]
    planned = [r for r in rows if "langue_demandee" not in r]
    by_lang: dict[str, list[dict]] = collections.defaultdict(list)
    for r in planned:
        by_lang[r["langue"]].append(r)

    kept: list[dict] = []
    shortfall = {}
    for lang, target in TARGETS.items():
        pool = by_lang.get(lang, [])
        buckets: dict[tuple[str, str], list[dict]] = collections.defaultdict(list)
        for r in pool:
            buckets[(r["domaine"], r["modele_id"])].append(r)
        # Ordre stable à l'intérieur d'un seau : la longueur varie avant de répéter.
        for bucket in buckets.values():
            bucket.sort(key=lambda r: (r["longueur_cible"], r["id"]))

        keys = sorted(buckets)
        chosen: list[dict] = []
        while len(chosen) < target:
            progressed = False
            for key in keys:
                if not buckets[key]:
                    continue
                chosen.append(buckets[key].pop(0))
                progressed = True
                if len(chosen) >= target:
                    break
            if not progressed:
                break
        kept.extend(chosen)
        if len(chosen) < target:
            shortfall[lang] = target - len(chosen)

    kept = kept + reassigned
    kept_ids = {r["id"] for r in kept}
    dropped = [r for r in rows if r["id"] not in kept_ids]

    print(f"  gardés : {len(kept)} (dont {len(reassigned)} réaffectés) · écartés : {len(dropped)}")
    for lang in sorted(TARGETS):
        n = sum(1 for r in kept if r["langue"] == lang and "langue_demandee" not in r)
        flag = "" if n == TARGETS[lang] else f"  ← cible {TARGETS[lang]}"
        print(f"    {lang}: {n}{flag}")
    if shortfall:
        print(f"  ✗ manque par langue : {shortfall}", file=sys.stderr)

    if args.dry_run:
        return 0 if not shortfall else 1

    for r in dropped:
        path = CORPUS / r["fichier"]
        if path.exists():
            path.unlink()
    # Les dossiers vidés par la sélection sont retirés : un dossier vide laisse croire
    # qu'un modèle a été utilisé dans une langue où il ne l'est plus.
    for d in sorted((CORPUS / "ai").rglob("*"), key=lambda p: -len(p.parts)):
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    MANIFEST.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept),
                        encoding="utf-8")
    print(f"  manifeste réécrit : {len(kept)} entrées")
    return 0 if not shortfall else 1


if __name__ == "__main__":
    sys.exit(main())
