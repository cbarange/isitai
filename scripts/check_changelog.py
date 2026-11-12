"""Refuse de publier une version qui n'a pas d'entrée de journal.

Une publication est irréversible sur les trois registres : un numéro de version consommé ne se
réutilise pas, et un paquet publié sans description de son contenu ne se répare pas. Ce contrôle
s'exécute donc avant tout envoi.

Usage:
    python3 scripts/check_changelog.py            # vérifie la version de Cargo.toml
    python3 scripts/check_changelog.py v0.1.0     # vérifie aussi que le tag correspond
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
MIN_ITEMS = 1


def fail(message: str) -> NoReturn:
    sys.exit(f"journal des versions : {message}")


def main() -> int:
    if not CHANGELOG.exists():
        fail("CHANGELOG.md absent")

    version = tomllib.loads((ROOT / "Cargo.toml").read_text(encoding="utf-8"))["workspace"]["package"]["version"]
    text = CHANGELOG.read_text(encoding="utf-8")

    # La section de la version courante doit exister et ne pas être vide : une entrée
    # « Ajouté / rien » serait un contournement du contrôle.
    pattern = re.compile(rf"^##\s*\[?{re.escape(version)}\]?[^\n]*\n(.*?)(?=^##\s|\Z)", re.S | re.M)
    match = pattern.search(text)
    if not match:
        fail(
            f"aucune section « ## [{version}] » dans CHANGELOG.md.\n"
            f"  Renommer « ## [Non publié] » en « ## [{version}] - <date> » avant de taguer."
        )

    body = match.group(1)
    items = [line for line in body.splitlines() if line.strip().startswith(("-", "*"))]
    if len(items) < MIN_ITEMS:
        fail(f"la section [{version}] ne contient aucun changement listé")

    if len(sys.argv) > 1 and sys.argv[1] != f"v{version}":
        fail(f"le tag {sys.argv[1]} ne correspond pas à la version {version}")

    print(f"journal des versions : [{version}] présent, {len(items)} changement(s) listé(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
