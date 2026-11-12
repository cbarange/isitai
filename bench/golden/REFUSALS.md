# Ce que le projet refuse de construire

Écrit avant le développement, conformément à l'étape 1. Cette liste ne s'allonge pas en cours
de route sans justification mesurée. Chaque refus porte sa raison : un refus sans raison devient
une superstition au bout de six mois.

## Ce qu'on refuse parce que c'est faux

| Refus | Raison |
|---|---|
| Un pourcentage de probabilité sur un fichier unique | À 1 % de prévalence, un détecteur 99/99 se trompe une fois sur deux quand il accuse. Le nombre n'existe pas (`FALLBACK-probabilistic.md` §2) |
| Un verdict « humain » | Aucune méthode ne prouve l'absence d'IA. On rend « aucun signal », jamais une absolution |
| Annoncer un taux que l'échantillon ne peut pas résoudre | 100 négatifs ⇒ plafond 2,95 %, quel que soit le résultat observé (`PROTOCOL.md` §2) |
| Utiliser le mot « précision » sans dire quel taux il désigne | VPP, sensibilité, spécificité et exactitude sont quatre choses différentes |
| Détecter sur du texte extrait de PDF sans le déclarer | `PDFuzz` fait tomber un détecteur de 93,6 % à 50,4 % en réordonnant l'extraction, sans changer le rendu |

## Ce qu'on refuse parce que ça ne marche pas

| Refus | Raison |
|---|---|
| Le vote ou l'empilement comme levier de performance | Mesuré sur le banc du projet : l'empilement ne bat pas le meilleur détecteur hors distribution. La fusion sert à **s'abstenir**, pas à gagner des points |
| Plusieurs classifieurs par modalité au choix | Les petits s'effondrent sous paraphrase (BERT-tiny : 0,506) ; les gros font doublon. Un seul, bien mesuré |
| Techniques à grand modèle de langue dans le cœur (Binoculars 2×7B, DetectGPT) | Plusieurs Go, lent sur CPU, plus faible sous attaque. Paquet optionnel ou rien |
| Classifieur vidéo et décodage vidéo dans le cœur | Pas de décodeur léger ; AUC en baisse de 50 % en conditions réelles |
| Classifieur audio passif dans le cœur | AASIST : 0,83 % d'EER en labo, 43 % en conditions réelles. Indice faible ou paquet optionnel |
| Détection SynthID | Aucun détecteur public. On renvoie vers le vérificateur du fournisseur et on dit que l'appel sort du hors-ligne |
| Localisation de retouche par réseau (TruFor et proches) | Licence absente ou non commerciale, poids de recherche : non redistribuable |

## Ce qu'on refuse par principe d'ingénierie

| Refus | Raison |
|---|---|
| Client réseau, S3, FTP dans la bibliothèque | Casse la promesse hors-ligne, ouvre une surface SSRF, et alourdit le binaire |
| Téléchargement de modèles, `postinstall` | Une bibliothèque ne déclenche pas de réseau à l'installation. L'appelant fournit `models_dir` |
| Modèles sous licence non commerciale dans un paquet MIT | Piège juridique pour l'utilisateur |
| Toute fonctionnalité sans critère d'acceptation chiffré | Le rôle du PM est de refuser ; sans mesure, une fonctionnalité n'est pas livrable |
| Une couche qui ne déplace pas la mesure | Ablation obligatoire. Si le delta est nul, la couche est supprimée, pas documentée |

## Ce qu'on refuse pour l'usage

| Refus | Raison |
|---|---|
| Un mode « triche » ou « plagiat » dans l'API | L'outil mesure une trace, il ne juge pas une personne. Le vocabulaire de l'API contraint l'usage |
| Un score exploitable en notation d'élèves | 61 % de faux positifs sur des textes d'apprenants non natifs (Liang et al., 2023). Documenté dans le README, pas seulement dans la doc |
| Un chiffre sans `locus` | Sans page, offset ou timestamp, le résultat n'est pas vérifiable, donc pas discutable |

## Les refus qu'on aura du mal à tenir

Deux refus vont être douloureux, et il vaut mieux le dire maintenant.

**Refuser le classifieur audio passif** prive la bibliothèque de ce qu'un utilisateur attend le
plus : « est-ce une voix clonée ? ». La réponse honnête — 43 % d'erreur en conditions réelles —
est décevante, mais elle est vraie. On livrera un indice faible, nommé comme tel.

**Refuser le pourcentage** va coûter des utilisateurs. Tout le monde en veut un. On rendra un
indice 0–100 monotone, avec des ancrages publiés et l'interdiction de l'appeler probabilité.
C'est le compromis de la barre de volume : une convention d'affichage honnête sur ce qu'elle
n'est pas.
