# Protocole du jeu doré — écrit avant le premier label

Version 1.0 — 2026-11-12. Ce document est **antérieur** à l'étiquetage : il fixe les règles
avant de savoir ce qu'elles produiront. Toute modification ultérieure porte un numéro de
version et une justification, jamais une correction silencieuse.

## 1. Ce que ce fichier interdit

Une bibliothèque de détection ne vaut que par ce qu'elle est capable de démentir. Un chiffre
annoncé sans que l'échantillon puisse le résoudre est un mensonge, même quand il est vrai par
hasard. Ce protocole existe pour rendre ce mensonge **impossible à écrire**, pas pour
l'éviter par discipline.

## 2. Analyse de puissance — à lire avant toute promesse

Borne supérieure exacte (Clopper-Pearson, 95 %) sur le taux de faux positifs quand on
n'observe aucun faux positif :

| Négatifs dans le jeu | Faux positifs annonçables au mieux |
|---|---|
| 25 | ≤ 11,29 % |
| 50 | ≤ 5,82 % |
| **100** | **≤ 2,95 %** |
| 150 | ≤ 1,98 % |
| **300** | **≤ 0,99 %** |
| 1 000 | ≤ 0,30 % |
| 3 000 | ≤ 0,10 % |

Corollaire, écrit noir sur blanc : **avec 100 textes humains, aucune revendication sous 3 %
n'est publiable.** Pour dire « 1 % de faux positifs », il faut 299 négatifs ; pour « 0,1 % »,
2 995. Le jeu de 300 fichiers autorise donc une phrase, et une seule : *faux positifs ≤ 3 %
(95 %)*. Toute autre formulation sera refusée en revue.

## 3. Composition du jeu

Trois classes. Les tailles ne sont pas égales, et ce n'est pas un défaut : les taux se
rapportent par classe avec leur intervalle, et c'est le nombre de négatifs qui fixe ce qu'on
peut affirmer (§2).

| Classe | Contenu | Vérité de terrain |
|---|---|---|
| `human` | Texte écrit par un humain, jamais passé par un modèle génératif | auteur nommé, document source, commit ou URL, date |
| `ai` | Texte produit par un modèle de langue, sans retouche humaine | générateur, date, identifiant de prompt |
| `mixed` | Texte humain contenant un ou plusieurs passages générés, **frontières connues** | offsets de caractères de chaque passage |

S'y ajoute une **quatrième population, hors des trois classes**, qui n'entre jamais dans le
calcul des taux : les variantes `degraded`. Ce sont des transformations déterministes de
fichiers `ai` et `human` (homoglyphes, caractères de largeur nulle, suppression du markdown,
réordonnancement de paragraphes, troncature). Elles mesurent la **robustesse**, elles ne
mesurent pas la justesse : une transformation ne change pas la vérité de terrain, elle change
la difficulté.

### 3.1 Déséquilibre linguistique assumé

Le matériau humain disponible aujourd'hui est de l'auteur : 9 documents français, 27 anglais.
Découpés en segments, cela donne environ 25 segments français et 110 anglais.

Conséquence, écrite avant la mesure : **le français sera annoncé à ≤ 11 % de faux positifs**
(25 négatifs), l'anglais à ≤ 3 % (100 négatifs). Ce n'est pas un défaut du protocole, c'est
l'état du corpus. Le français est pourtant la langue où les seuils cassent — la mesure faite
sur `corpus_scores.json` montre 10 % de faux positifs en français contre 0 % ailleurs. La
première action d'acquisition n'est donc pas un modèle : c'est **du texte humain français**.

## 4. Règles anti-fuite

Une fuite de données invalide silencieusement une mesure. Quatre règles, vérifiées par le
script de construction :

1. **Découpage par document, jamais par segment.** `document_id` est la seule unité de
   partition. Deux segments du même document ne peuvent pas se retrouver dans deux plis
   différents.
2. **Déduplication exacte** par SHA-256, puis **quasi-déduplication** par empreinte de shingles
   (Jaccard ≥ 0,8 → doublon), avant tout tirage.
3. **Aucun fichier dérivé sans son parent** : chaque `degraded` référence le SHA-256 de son
   original, et chaque `mixed` référence les SHA-256 de ses deux composants.
4. **Le jeu est figé** pendant une itération. Tout ajout crée une version (`v1.1`) et invalide
   les chiffres précédents : on ne compare pas des mesures prises sur deux jeux différents.

## 5. Protocole d'adjudication

Écrit avant de labelliser, appliqué à la lettre.

1. **Qui labellise.** Deux lecteurs indépendants. Le premier est l'auteur du fichier quand il
   existe (provenance certaine) ; le second est un lecteur qui ne voit ni le nom du fichier ni
   son origine.
2. **Ce que voit le lecteur.** Le texte nu, sans métadonnée, sans indice de nommage, dans un
   ordre mélangé par graine fixe.
3. **Accord.** κ de Cohen calculé sur 10 % de l'échantillon tiré au sort (graine consignée).
   Seuil d'acceptation : **κ ≥ 0,80**. En dessous, le désaccord est traité comme une
   information : la catégorie concernée est déclarée non labellisable et sort du jeu.
4. **Résolution des désaccords.** Règle fixée d'avance, dans cet ordre : (a) la provenance
   documentaire tranche si elle est certaine ; (b) sinon, le fichier sort du jeu — on ne
   moyenne pas deux avis, on retire le cas.
5. **Cas ambigus.** Un texte mêlant des passages d'origines différentes sans frontière
   identifiable n'est ni `human` ni `ai` : il est **exclu**, pas rangé dans `mixed`. `mixed`
   exige des frontières connues, sinon la classe n'a pas de vérité de terrain.
6. **Traçabilité.** Chaque ligne du manifeste porte qui a labellisé, quand, et sur quelle base
   (provenance, lecture, transformation).

Conséquence assumée : cette bibliothèque ne produit pas de labels elle-même. Elle ne peut pas
être à la fois le détecteur et le juge.

## 6. Ce qui est mesuré, et sous quelle forme

| Mesure | Forme du résultat | Pourquoi pas autrement |
|---|---|---|
| Faux positifs | taux + intervalle de Wilson, **par langue et par registre** | une moyenne cache le sous-groupe qui casse |
| Rappel | taux + intervalle, par générateur | la moyenne sur 26 générateurs ne dit rien d'aucun |
| Robustesse | matrice détecteur × dégradation | une seule chute moyenne masque un effondrement |
| Calibration | ECE, Brier, NLL **par sous-groupe** | l'ECE globale est une moyenne, donc un mensonge |
| Coût | médiane et p95 en ms par fichier, sur la machine la plus lente supportée | une moyenne sur machine rapide ne décrit rien |

Le rapport publie **le pire sous-groupe**, jamais la moyenne générale. Un chiffre global ne
figure qu'en second, et toujours accompagné de son pire cas.

## 7. Critères de refus en revue

Une revendication est refusée si :

- elle annonce un taux que `n` ne peut pas résoudre (§2) ;
- elle porte sur un sous-groupe de moins de 30 fichiers ;
- elle mélange des mesures prises sur deux versions du jeu ;
- elle présente une moyenne sans son pire sous-groupe ;
- elle utilise le mot « précision » sans définir quel taux il désigne ;
- elle compare un chiffre du jeu doré à un chiffre publié sur un autre corpus sans dire que ce
  sont deux populations différentes.

## 8. État d'avancement

| Élément | État |
|---|---|
| Analyse de puissance | fait (§2) |
| Règles anti-fuite | fait (§4), à implémenter dans `build.py` |
| Protocole d'adjudication | fait (§5), **pas encore appliqué** : les labels actuels viennent de la provenance, pas d'une double lecture |
| Classe `human` | 150 segments issus de 36 documents de l'auteur |
| Classe `ai` | 100 textes générés le 2026-11-12, deux lots, **un seul générateur** (`deepseek-v4.1-flash`) — la diversité de générateur reste à faire |
| Classe `mixed` | 100 textes, insertion à frontière connue, offsets dans le manifeste |
| `degraded` | 120 variantes, cinq transformations déterministes |
| Reconstruction | identique au bit près, vérifiée deux fois |
| κ de Cohen | **non mesuré — c'est la première dette du jeu** |
| Harnais d'évaluation | **absent** : aucun détecteur n'a encore été mesuré sur ce jeu |
