#!/usr/bin/env python3
"""Assainit le corpus, en tire les statistiques, et écrit le README.

Ne fait aucun appel réseau : le corpus est déjà sur disque. Le script échoue si le
manifeste et les fichiers divergent — un corpus dont l'index ne décrit pas le contenu
n'est pas un corpus, c'est une collection de fichiers.

Usage: python3 corpus/tools/finalize.py [--write-readme]
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

CORPUS = pathlib.Path(__file__).resolve().parents[1]
MANIFEST = CORPUS / "manifest.jsonl"
UNIT = {"zh": "caractères", "ja": "caractères"}


def load() -> list[dict]:
    rows = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def dedupe(rows: list[dict]) -> tuple[list[dict], int]:
    """Une entrée par identifiant : la dernière gagne.

    Une relance après un arrêt brutal peut réécrire un texte déjà consigné. Garder les
    deux ferait compter deux fois le même fichier dans toutes les statistiques.
    """
    by_id: dict[str, dict] = {}
    for row in rows:
        by_id[row["id"]] = row
    return list(by_id.values()), len(rows) - len(by_id)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-readme", action="store_true")
    args = ap.parse_args()

    rows = load()
    rows, removed = dedupe(rows)

    files = {str(p.relative_to(CORPUS)) for p in (CORPUS / "ai").rglob("*.txt")}
    indexed = {r["fichier"] for r in rows}
    missing = sorted(indexed - files)
    orphans = sorted(files - indexed)

    # Le manifeste est reconstruit seulement s'il y a des doublons : une réécriture
    # inutile changerait le fichier sans raison et brouillerait l'historique git.
    if removed:
        MANIFEST.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
            encoding="utf-8",
        )

    per_lang = collections.Counter(r["langue"] for r in rows)
    per_model = collections.Counter(r["modele_id"] for r in rows)
    per_domain = collections.Counter(r["domaine"] for r in rows)
    per_length = collections.Counter(r["longueur_cible"] for r in rows)
    per_publisher = collections.Counter(r["editeur"] for r in rows)
    allowance = sum(float(r.get("allowance") or 0) for r in rows)

    subjects: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for r in rows:
        subjects[(r["langue"], r["domaine"])].add(r["sujet"])

    failures = []
    if (CORPUS / "failures.jsonl").exists():
        for line in (CORPUS / "failures.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                failures.append(json.loads(line))
    reasons = collections.Counter(
        "hors longueur" if f["raison"].startswith("hors longueur")
        else "sortie vide" if f["raison"].startswith("sortie vide")
        else f["raison"].split(":")[0]
        for f in failures
    )

    print(f"  {len(rows)} textes · {len(files)} fichiers · {removed} doublon(s) retiré(s)")
    print(f"  langues : " + " · ".join(f"{k} {v}" for k, v in sorted(per_lang.items())))
    print(f"  éditeurs : {len(per_publisher)} · modèles : {len(per_model)}")
    print(f"  allowance cumulée : {allowance:.4f}")
    print(f"  échecs consignés : {len(failures)} " + str(dict(reasons)))
    print(f"  sujets par (langue, domaine) : min {min((len(v) for v in subjects.values()), default=0)}"
          f" · max {max((len(v) for v in subjects.values()), default=0)}")

    if missing:
        print(f"  ✗ {len(missing)} entrées sans fichier : {missing[:3]}", file=sys.stderr)
    if orphans:
        print(f"  ✗ {len(orphans)} fichiers sans entrée : {orphans[:3]}", file=sys.stderr)
    if missing or orphans or not rows:
        return 1

    if args.write_readme:
        write_readme(rows, per_lang, per_model, per_domain, per_length,
                     per_publisher, allowance, subjects, failures, reasons)
        print("  README.md écrit")
    return 0


def write_readme(rows, per_lang, per_model, per_domain, per_length,
                 per_publisher, allowance, subjects, failures, reasons) -> None:
    total = len(rows)
    unit = "caractères pour le chinois, mots ailleurs"
    lines = [
        "# Corpus de textes générés",
        "",
        f"{total} textes produits par des modèles de plusieurs éditeurs, dans sept langues",
        "et dix domaines. Ce corpus sert de matériau **positif** : il ne contient que du",
        "texte machine, et ne permet donc à lui seul aucun calcul de faux positifs.",
        "",
        "## Provenance",
        "",
        "Chaque texte est consigné dans `manifest.jsonl` : identifiant, fichier, modèle,",
        "éditeur, langue, domaine, longueur cible, longueur réelle, sujet, prompt exact,",
        "température, date et coût en allowance. Le prompt est conservé parce qu'un texte",
        "sans sa consigne n'est pas reproductible.",
        "",
        "## Langues",
        "",
        "| Langue | Textes | Part |",
        "|---|---|---|",
    ]
    for lang, n in sorted(per_lang.items(), key=lambda kv: -kv[1]):
        lines.append(f"| {lang} | {n} | {n / total * 100:.1f} % |")

    lines += ["", "## Éditeurs", "", "| Éditeur | Textes |", "|---|---|"]
    for pub, n in per_publisher.most_common():
        lines.append(f"| {pub} | {n} |")

    lines += ["", "## Modèles", "", "| Modèle | Textes |", "|---|---|"]
    for model, n in per_model.most_common():
        lines.append(f"| `{model}` | {n} |")

    lines += ["", "## Domaines", "", "| Domaine | Textes |", "|---|---|"]
    for domain, n in per_domain.most_common():
        lines.append(f"| {domain} | {n} |")

    lines += ["", "## Longueurs", "",
              f"Comptées en {unit}.", "", "| Longueur | Textes | Bornes |", "|---|---|---|"]
    bounds = {"court": "30-80", "moyen": "150-300", "long": "500-900", "tres-long": "1500-3000"}
    for length, n in per_length.most_common():
        lines.append(f"| {length} | {n} | {bounds.get(length, '?')} |")

    cov = collections.Counter(len(v) for v in subjects.values())
    lines += [
        "",
        "## Couverture des sujets",
        "",
        "Nombre de sujets distincts par couple (langue, domaine) :",
        "",
        "| Sujets distincts | Couples concernés |",
        "|---|---|",
    ]
    for k, n in sorted(cov.items(), reverse=True):
        lines.append(f"| {k} | {n} |")
    lines += [
        "",
        "Les langues à petit volume ne peuvent pas couvrir dix sujets par domaine :",
        "37 textes italiens pour dix domaines donnent mécaniquement trois à quatre sujets.",
        "Ce n'est pas une lacune du générateur mais une contrainte d'échelle, à connaître",
        "avant de comparer des taux entre langues.",
        "",
        "## Ce que ce corpus ne permet pas de dire",
        "",
        "- Aucun taux de faux positifs : il ne contient pas de texte humain.",
        "- Aucune comparaison entre modèles : le nombre de textes par modèle n'est pas",
        "  équilibré, il suit une pondération par coût mesuré.",
        "- Aucune généralisation à un domaine absent de la liste.",
        "",
        f"Coût total de production : {allowance:.4f} allowance.",
        "",
        "## Échecs de génération",
        "",
    ]
    if failures:
        lines += ["| Raison | Occurrences |", "|---|---|"]
        for reason, n in reasons.most_common():
            lines.append(f"| {reason} | {n} |")
        lines += ["", "Les identifiants en échec ne sont pas écrits : relancer le générateur",
                  "les retente seuls, les textes déjà présents étant sautés."]
    else:
        lines.append("Aucun.")
    (CORPUS / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
