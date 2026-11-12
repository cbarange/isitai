#!/usr/bin/env python3
"""Mesure la couche rhétorique sur le jeu doré, par classe.

Ce n'est pas un test de précision : c'est une **description** de ce que la couche
trouve, et de ce qu'elle ne doit jamais casser. Le seul invariant dur est vérifié
ailleurs, dans les tests Rust (`rhetoric_never_changes_the_verdict`).

    python3 bench/rhetoric/eval.py [--corpus bench/golden/set] [--binary target/release/isitai]

Échoue si le corpus ou le binaire manquent : une mesure sur un corpus absent n'est pas
une mesure, c'est un zéro silencieux.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
RHETORIC_IDS = {"rhetoric.pivot-pair", "rhetoric.not-x-but-y", "rhetoric.triptych"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "bench/golden/set"))
    ap.add_argument("--binary", default=str(ROOT / "target/release/isitai"))
    args = ap.parse_args()

    corpus = pathlib.Path(args.corpus)
    binary = pathlib.Path(args.binary)
    manifest = corpus / "MANIFEST.jsonl"

    for path, what in ((corpus, "corpus"), (manifest, "manifeste"), (binary, "binaire")):
        if not path.exists():
            print(f"  manquant : {what} ({path})", file=sys.stderr)
            if what == "corpus":
                print("  construire d'abord : python3 bench/golden/build.py", file=sys.stderr)
            if what == "binaire":
                print("  construire d'abord : cargo build --release -p isitai-cli", file=sys.stderr)
            return 1

    rows = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    files = [corpus / row["path"].split("set/")[1] for row in rows]
    klass = {f"set/{row['path'].split('set/')[1]}": row["class"] for row in rows}

    out = subprocess.run(
        [str(binary), *map(str, files)],
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode not in (0, 1):  # 1 = at least one signal, which is expected
        print(f"  le binaire a échoué ({out.returncode}) : {out.stderr[:300]}", file=sys.stderr)
        return 1

    reports = json.loads(out.stdout)
    per_class: dict[str, list[dict]] = defaultdict(list)
    for report in reports:
        path = pathlib.Path(report.get("path", ""))
        key = f"set/{path.parent.name}/{path.name}"
        per_class[klass.get(key, "inconnu")].append(report)

    print(f"\n  {'classe':<10}{'fichiers':>9}{'avec motif':>12}{'motifs/fichier':>16}{'verdicts':>26}")
    summary = {}
    for name in sorted(per_class):
        reports = per_class[name]
        marks = [len([e for e in r["evidence"] if e["id"] in RHETORIC_IDS]) for r in reports]
        with_pattern = sum(1 for m in marks if m > 0)
        verdicts = Counter(r["verdict"] for r in reports)
        summary[name] = {
            "files": len(reports),
            "with_pattern": with_pattern,
            "share_with_pattern": round(with_pattern / len(reports), 3),
            "patterns_per_file": round(sum(marks) / len(reports), 2),
            "verdicts": dict(verdicts),
        }
        print(
            f"  {name:<10}{len(reports):>9}{with_pattern:>12}"
            f"{sum(marks) / len(reports):>16.2f}"
            f"{str(dict(verdicts)):>26}"
        )

    target = ROOT / "bench/rhetoric/results.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n  écrit : {target.relative_to(ROOT)}")
    print("  Ce tableau décrit un comportement, il ne mesure pas une précision.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
