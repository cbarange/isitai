#!/bin/bash
# Attend la fin des workers, comble les identifiants en échec, puis assainit, documente
# et publie. Chaque étape est rejouable : relancer le script ne réécrit rien d'existant.
set -u
cd /home/hermes/work/isitai || exit 1

echo "=== attente de la fin des workers ==="
while pgrep -f "^python3 corpus/tools/generate.py" > /dev/null; do sleep 60; done
echo "  workers terminés : $(find corpus/ai -name '*.txt' | wc -l) fichiers"

# Les identifiants en échec ne sont pas sur disque : sans --limit, le générateur
# parcourt tout le plan et ne retente que ce qui manque.
echo "=== comblement des échecs ==="
for lang in en fr es pt zh ar it; do
  echo "--- $lang"
  python3 corpus/tools/generate.py --lang "$lang" --sleep 0.8 2>&1 | tail -3
done

echo "=== assainissement et statistiques ==="
python3 corpus/tools/finalize.py --write-readme || {
  echo "  ✗ corpus incohérent : rien n'est publié"
  exit 1
}

echo "=== commit ==="
git add -A
git -c user.name="Hermes" -c user.email="hermes@local" commit -q -m "corpus: 600 textes générés, sept langues et douze modèles

Corpus positif destiné au banc de détection : manifeste par texte (modèle, éditeur,
langue, domaine, longueur, sujet, prompt exact, coût), statistiques et limites dans
corpus/README.md. Le manifeste est dédupliqué et vérifié fichier par fichier."
git log --oneline -1
echo "  poussée : $(git push origin HEAD 2>&1 | tail -2)"
