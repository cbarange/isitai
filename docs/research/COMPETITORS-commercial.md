# Détecteurs commerciaux : mécanismes et présentation des scores — recherche du 2026-11-12

Document de recherche. Aucun code modifié. Il prolonge `FALLBACK-probabilistic.md` (dont la section 5 donne déjà les chiffres indépendants par produit : ils ne sont pas répétés ici), `BENCH-text-detectors.md`, `ROADMAP-detection.md` et `OSS-patterns-reuse.md`.

Règles de salle blanche appliquées : pages publiques seulement (documentation, rapports techniques, articles, dépôt public du classement RAID, communiqués). Aucun compte créé, aucune API de détection appelée, aucun texte soumis à un détecteur, aucun code d'application ou d'extension inspecté. Les pages qui ont répondu 403 ou 404 n'ont pas été contournées.

Marquage de chaque affirmation :

- **[F]** : dit par le fournisseur lui-même (page produit, documentation, article de ses employés). Non contrôlé.
- **[T]** : montré par un tiers indépendant, ou lu dans une source publique contrôlable (fichiers du dépôt RAID).
- **[D]** : déduction du rédacteur.
- **[mém.]** : rappelé de mémoire, la page n'a pas pu être relue ce jour. À revérifier avant de citer.
- **non trouvé** : cherché, absent des sources lues. Rien n'est estimé à la place.

Limite de méthode : la plupart des pages ont été lues à travers un outil qui résume, ou à travers des extraits de moteur de recherche. Un chiffre cité ici a été vu dans ce résumé, pas toujours dans la page brute. Les chiffres RAID ont été lus directement dans les fichiers `results.json`. Le budget de recherche était serré : le texte est traité en détail, l'image, l'audio et la vidéo plus brièvement.

## 1. Résumé

1. **Les détecteurs de texte qui documentent leur mécanisme sont des classifieurs supervisés**, ré-entraînés en continu : transformeur chez Pangram et Originality [F], « apprentissage profond » chez GPTZero [F], transformeur chez Turnitin [mém.]. Les autres ne disent rien. La perplexité et la « burstiness » appartiennent à la première génération de 2023 [mém.] ; aucune source lue ne montre un fournisseur qui s'appuie encore dessus seul.
2. **Le faux positif se combat à l'entraînement, pas au seuil.** La méthode la mieux documentée est celle de Pangram : chercher dans des millions de textes humains anciens ceux que le modèle accuse à tort, générer pour chacun un jumeau IA, ré-entraîner, recommencer.
3. **Les faux positifs se publient par domaine et par langue.** Chez Pangram, l'écart entre domaines atteint deux ordres de grandeur (0,00 % à 0,49 %). Un taux global ne dit rien.
4. **Tous découpent le texte** en phrases ou en fenêtres, notent chaque morceau, puis agrègent. Le chiffre affiché est le plus souvent une **part du texte signalée**, pas une probabilité que le document soit IA. Ce sont deux grandeurs différentes.
5. **Les meilleurs s'abstiennent** : minimum de longueur (300 mots chez Turnitin), score marqué comme peu fiable sous 20 % (et masqué [mém.]), drapeau « texte court », catégorie de confiance, classe « mixte ».
6. **Le prétraitement fait partie du détecteur** : titres, listes, références, caractères spéciaux.
7. **GPTZero publie un identifiant daté pour chaque version du modèle** (`2026-11-04-base`). Qu'il figure dans chaque réponse d'API est une déduction [D]. C'est l'équivalent du `calibration_id` déjà proposé. Pangram et Originality numérotent leurs modèles ; la présence du numéro dans leurs réponses n'a pas été vue.
8. **Image, audio, vidéo** : ensembles de modèles spécialisés, score de 0 à 1, verdict à trois états chez Reality Defender, cartes de chaleur. Le fournisseur d'un générateur détecte très bien ses propres sorties et très mal celles des autres.
9. **Ce qu'une bibliothèque hors ligne ne peut pas reproduire** : le ré-entraînement toutes les trois semaines, la recherche dans un stock de sorties générées, les watermarks à clé privée, l'enregistrement du processus d'écriture.

## 2. Texte

### 2.1 GPTZero

**Ce qui est détecté.** Texte IA, texte mixte, texte humain « poli » par IA, texte paraphrasé ou « humanisé ». [F]

**Mécanisme, d'après le journal public des versions** (https://gptzero.me/news/ai-detection-model-api-updates, environ 60 versions du 23 mai 2023 au 4 novembre 2026) [F] :

| Date | Version | Ce que la version change |
|---|---|---|
| mai à sept. 2023 | sans numéro | passage à un « modèle d'apprentissage profond » ; ensemble de détecteurs ; message affiché quand les détecteurs de l'ensemble sont en désaccord (7 juil. 2023) ; ajout de documents humains « vérifiés par archive » et réglage pour les auteurs non natifs ; seuil « entièrement IA » relevé de 0,85 à 0,88 (19 juil. 2023) |
| oct. et nov. 2023 | sans numéro | surlignage par phrase aligné sur le score du document ; ensemble consolidé ; probabilités calibrées |
| 11 déc. 2023 | sans numéro | ajout de la classe « mixte » et d'un score de confiance de 0 à 1 |
| 9 janv. 2024 | `2024-01-09` | calibration : un score de 90 % doit correspondre à 90 % de chances que le texte soit entièrement IA |
| 10 avr. 2024 | `2024-04-10-multilingual` | modèle multilingue séparé (français, espagnol) |
| nov. 2024 à mars 2025 | jusqu'à 3.3b | robustesse à la paraphrase et aux changements de mise en forme |
| 2 mai 2025 | 3.4b | sortie plus stable quand on relance l'analyse du même texte |
| 3 juin 2025 | 3.5b | détection du texte « poli » (légèrement retouché par IA) |
| sept. à déc. 2025 | 3.3m à 3.7m | modèle multilingue plus gros ; 10 langues ajoutées en deux étapes (environ 14 au total) ; baisse des faux positifs sur les documents formels non anglais |
| nov. 2025 à févr. 2026 | 3.13b à 4.2b | corrections ciblées de faux positifs : documents contenant des dates, entités nommées, textes classiques, textes juridiques ; moindre dépendance aux caractères spéciaux |
| 6 mai 2026 | 4.5b | prédictions mixtes plus fines, textes mixtes entrelacés |
| 10 juin 2026 | 4.1m | rééquilibrage des données pour la presse (modèle multilingue) |
| 1er août 2026 | 4.8b | les titres sont exclus de l'entrée du modèle |
| 7 oct. 2026 | 4.11b | découpage du document en morceaux puis agrégation |
| 4 nov. 2026 | 5.0b | architecture plus grande ; mieux sur le texte poli et paraphrasé |

Ce que ce journal apprend [D] :

- Deux modèles distincts sont servis : `base` (anglais) et `multilingual`. Le suffixe « b » ou « m » le dit. « Model 4.1m » est donc la version 4.1 du modèle multilingue, pas une taille.
- Le rythme est d'une version toutes les deux à trois semaines. La détection est un service ré-entraîné en continu contre les nouveaux générateurs (4.9b cite les modèles sortis l'été 2026). Une bibliothèque hors ligne ne peut pas suivre : elle doit dater ses tables et le dire.
- La moitié des versions corrige une famille nommée de faux positifs (dates, entités, titres, textes classiques, documents formels non anglais). Le faux positif se traite domaine par domaine.
- Le prétraitement fait partie du modèle : exclure les titres, ignorer les caractères spéciaux, traiter une liste numérotée comme un seul bloc.
- Les versions de 2023 parlent de perplexité et de « burstiness » combinées à d'autres composants [F, mém.]. Le journal montre le remplacement progressif par un classifieur profond.

Taille du modèle, architecture, données d'entraînement : **non trouvé**. Le journal ne donne aucun chiffre d'exactitude.

**Sortie de l'API** (aide publique : https://support.gptzero.me/articles/8947054519-how-do-i-use-and-interpret-the-results-from-your-api et l'article voisin sur les seuils) [F] :

| Champ | Sens |
|---|---|
| `document_classification` | `HUMAN_ONLY`, `MIXED` ou `AI_ONLY` |
| `class_probabilities` | trois probabilités (`human`, `mixed`, `ai`) qui somment à 1 |
| probabilité de la classe prédite | à lire comme « la chance que le détecteur ait raison » sur des documents semblables |
| `confidence_category` | `high`, `medium`, `low`. Pour `high` : 99,1 % des textes humains classés humains, 98,4 % des textes IA classés IA. Aucun chiffre pour `medium` et `low` |
| identifiant de version | `modelVersion` dans le journal, par exemple `2026-11-04-base` ; sa présence dans chaque réponse n'a pas été vue [D] |

Le fournisseur montre comment déplacer soi-même les seuils (par exemple, ramener à « humain » toute prédiction IA ou mixte sous 80 %) et déconseille d'augmenter la sensibilité en contexte scolaire : un faux négatif y est « préférable » à un faux positif [F].

**Page de résultat grand public.** Répartition en trois parts (IA, mixte, humain) en pourcentage, surlignage par phrase, phrase de confiance du type « nous sommes très confiants que ce texte est entièrement humain », onglets séparés (analyse avancée, plagiat, hallucinations). [Observation du propriétaire ; non reproduite, aucun texte n'a été soumis.]

**Mesure indépendante.** Dépôt RAID, soumission du 7 octobre 2025 : détection à 1 % de faux positifs de 95,7 % sans attaque, 71,6 % sous paraphrase, 89,2 % sous synonymes ; AUROC 0,995 [T]. Le rapport de Pangram mesure pour GPTZero 7,7 % de faux positifs sur 91 essais TOEFL, ou 1,1 % si la mention « contenu IA possible » compte comme négative [F côté Pangram, concurrent].

**Rachat.** Superhuman (nouveau nom de Grammarly) a annoncé le 23 juin 2026 un accord pour acquérir GPTZero ; montant non publié [F, https://blog.superhuman.com/superhuman-to-acquire-gptzero/, repris par Business Wire]. GPTZero rejoint le détecteur de Grammarly et l'outil Authorship. Conséquences [D] : deux des détecteurs grand public les plus cités appartiennent au même groupe, donc leurs chiffres ne sont plus deux témoignages indépendants ; le groupe détient à la fois la détection a posteriori et l'enregistrement du processus d'écriture ; la finalisation de l'opération n'a pas été vérifiée.

**Prix** : 8 à 13 dollars par mois selon des sites de revue, chiffres divergents [T faible]. Page officielle non relue.

### 2.2 Pangram Labs

**Mécanisme.** Rapport technique de ses fondateurs (Emi et Spero, arXiv 2402.14873) [F] :

- Un classifieur à architecture de type transformeur « légèrement modifiée ». Nombre de paramètres et fenêtre de contexte : **non trouvé**.
- Réserve d'environ 28 millions de documents humains datés de 2021 ou avant, sous licence permettant l'usage commercial (dont 15 millions d'avis et 7 millions de livres).
- Entraînement initial : 40 000 exemples par domaine.
- **Extraction de négatifs difficiles avec « miroirs synthétiques ».** Le modèle parcourt la réserve et relève les textes humains qu'il accuse à tort (jusqu'à 10 000 par domaine et par tour). Pour chacun, un LLM écrit un jumeau IA : un avis sur le même commerce et de même longueur, un essai sur le titre déduit de l'essai humain, un article qui commence par les mêmes phrases. Les paires entrent dans l'entraînement. La boucle continue tant que le modèle s'améliore. Les exemples de moins de 50 mots sont écartés.
- Environ 4 millions de documents sont tenus hors de la boucle pour l'évaluation.
- Une erreur sur un texte humain est pénalisée beaucoup plus qu'une erreur sur un texte IA [F, https://www.pangram.com/blog/all-about-false-positives-in-ai-detectors].

**Classes et sortie** (documentation de l'API v3 et carte du modèle 3.3, https://www.pangram.com/research/model-card/pangram-3-3) [F] :

- Trois parts du texte qui somment à 1 : IA, assisté par IA, humain. Étiquette courte : « AI », « AI-Assisted », « Human » ou « Mixed ».
- Une liste de fenêtres avec positions de caractères, étiquette et score d'assistance de 0 à 1. Seuils publiés : jusqu'à 0,25 humain ; 0,25 à 0,5 légèrement assisté ; 0,5 à 0,75 modérément assisté ; au-dessus de 0,75 IA.
- Le score d'assistance vient d'un modèle qui estime **l'ampleur de la retouche par IA** (rapport « EditLens », cité par la carte, non relu ici). Ce serait donc une régression sur un degré plutôt qu'une classification binaire [D, mém.].
- Le découpage des documents de plus de 450 mots a changé en version 3.3.1.

**Faux positifs et seuil** [F] :

- Taux global annoncé : environ 1 sur 10 000.
- Tableau par domaine dans la carte 3.3 : 0,00 % (discours, scénarios), 0,01 % (avis, articles biomédicaux), 0,02 % (écrits scolaires anglais), **0,17 % (écrits scolaires traduits par Google Translate)**, **0,49 % (poésie)**. Faux négatifs : 0,00 % à 1,50 % (échantillon de conversations de chatbots).
- Quatre étages d'évaluation : gros jeux tenus à l'écart (10 000 à 10 millions de textes d'avant ChatGPT), jeux soignés à la main (environ 1 000), jeux de cas difficiles (10 à 100 : anciens faux positifs signalés, recettes, poésie) et **tests unitaires** (Déclaration d'indépendance, phrases littéraires célèbres, textes du site). Un seul échec de test unitaire bloque la mise en production.
- Seuil choisi sur des millions de documents. Dans le rapport, la comparaison se fait à 1 % de faux positifs fixé pour chaque détecteur.
- Auteurs non natifs : 0 % sur 91 essais TOEFL, 0 sur 3 907 essais ELLIPSE, 0,09 % sur 5 600 essais ICNALE.
- Limites déclarées : listes à puces, modes d'emploi, tables des matières, bibliographies, textes à gabarit, mathématiques denses. Le fournisseur demande de retirer en-têtes et pieds de page, et préfère le texte brut ou le `.docx` au PDF, dont l'extraction ajoute des artefacts.

**Mesure indépendante.** Aucune soumission au nom de Pangram dans le dépôt RAID lu ce jour [T]. Le chiffre RAID de la carte (99,26 % d'exactitude, 0,01 % de faux positifs sur 66 855 textes) est mesuré par le fournisseur sur un échantillon [F]. Un billet critique de LessWrong affirme que des cas que l'article du fournisseur appelle « assistés » sortent étiquetés « générés » dans l'outil [T faible, non relu en détail].

**Prix** : non trouvé (« contacter les ventes » d'après un site tiers).

### 2.3 Originality.ai

- **Mécanisme** : classifieur supervisé ; la page d'explication du fournisseur parle d'un modèle « basé sur une version modifiée de BERT » [F]. Taille et données : non trouvé.
- **Plusieurs modèles au choix de l'utilisateur**, selon sa tolérance au faux positif : Lite (0,5 % de faux positifs annoncés), Turbo (1,5 %, plus sensible), Academic (moins de 1 %), remplacés en septembre 2026 par 5.0 et 5.0 Max [F, via extrait de recherche]. L'idée transférable : le compromis rappel contre faux positifs est un réglage exposé et nommé, pas un seuil caché.
- **Sortie** : probabilité « IA » contre « original » pour le document, surlignage par phrase [F]. Noms de champs de l'API : non trouvé.
- **Indépendant** : premier des détecteurs commerciaux dans l'article RAID de 2024 (voir `FALLBACK-probabilistic.md` §5). Le rapport de Pangram lui mesure 9,24 % de faux positifs [F côté concurrent]. Des revues tierces citent 4,8 % à 5,7 % [T faible].
- **Prix** : environ 13 à 15 dollars par mois pour 200 000 mots, un crédit pour 100 mots [T faible, sites de revue].

### 2.4 Copyleaks

- **Sortie** : un classement humain ou IA par section du texte et un résumé global des deux parts [F, https://docs.copyleaks.com/concepts/products/ai-text-detection-api.md]. Noms exacts des champs : non trouvé (page de référence en 404).
- **Trois niveaux de sensibilité** : 1 pour le texte copié tel quel d'un outil, 2 pour le texte légèrement modifié, 3 pour le texte fortement retouché [F].
- **« AI Logic »**, la couche d'explication [F, https://copyleaks.com/ai-content-detector/ai-logic] :
  - **AI Phrases** : signale les expressions statistiquement plus fréquentes dans le texte IA que dans le texte humain. Disponible pour six langues seulement.
  - **AI Source Match** : cherche si un passage correspond à un contenu IA déjà publié ailleurs. C'est de la recherche dans un index, le même mécanisme que la détection de plagiat. Seul fournisseur de la liste à documenter ce mécanisme.
- **Langues** : 30 annoncées [F]. **Minimum de longueur** : non trouvé. **Taux de faux positifs chiffré** : non trouvé sur les pages lues (la page de méthode de test n'a pas été lue).
- **Indépendant** : voir `FALLBACK-probabilistic.md` §5.
- **Prix** : à partir de 8 dollars par mois d'après un site de revue [T faible].

### 2.5 Turnitin

- **Mécanisme** : classifieur de type transformeur ; le document est découpé en segments de quelques centaines de mots qui se chevauchent ; chaque phrase reçoit un score, moyenné sur les segments qui la contiennent [F, mém. : la FAQ officielle a répondu 403 ce jour].
- **Score affiché** : la part du texte « qualifiant » (prose en phrases longues) jugée écrite par IA. Ce n'est pas une probabilité.
- **Abstention** [F] :
  - minimum relevé de 150 à 300 mots, parce que la précision croît avec la longueur ;
  - sous 20 %, un astérisque signale un résultat moins fiable, parce que les faux positifs sont plus fréquents dans cette zone [F] ; le pourcentage lui-même n'y serait plus affiché [mém.].
- **Faux positifs annoncés** [F, https://www.turnitin.co.uk/blog/understanding-the-false-positive-rate-for-sentences-of-our-ai-writing-detection-capability] : moins de 1 % au niveau du document quand au moins 20 % du texte est signalé (validé sur 800 000 textes d'avant ChatGPT d'après la presse) ; environ **4 % au niveau de la phrase**. 54 % des phrases accusées à tort sont voisines d'un vrai passage IA.
- **Texte « humanisé »** : détection des contournements ajoutée le 27 août 2025, en anglais seulement ; le texte modifié par un outil de contournement est compté **dans** la catégorie « généré par IA seulement » du rapport, qui présente deux catégories dont les noms n'ont pas été trouvés [F, via extrait de recherche].
- **Langues** : anglais, puis espagnol et japonais depuis avril 2025 [F].
- **Indépendant** : étude de Weber-Wulff et collègues (2023), 14 détecteurs dont Turnitin, tous sous 80 % d'exactitude, avec un biais vers la réponse « humain » [T, mém.].
- **Prix** : licence d'établissement, non public.

### 2.6 Grammarly : détecteur et Authorship

**Détecteur** (https://www.grammarly.com/ai-detector) [F] :

- Découpe le texte, analyse chaque section, et rend **un pourcentage du texte qui semble généré par IA**.
- Entraîné sur « des dizaines de milliers » de textes, dont des textes d'avant 2021 (le propriétaire a lu « textes humains écrits avant 2021 » ; le résumé automatique a rendu la phrase de travers, à relire sur la page).
- Avertissements explicites : aucun détecteur n'est exact à 100 % ; un détecteur ne peut pas conclure qu'une IA a été utilisée ; le résultat n'est qu'un élément d'une évaluation d'ensemble.
- La FAQ dit que des détecteurs, en général, examinent des traces de métadonnées ou comparent le texte à une base de contenus IA connus. Elle ne dit pas que Grammarly le fait.
- Annonce 99 % d'exactitude et la première place sur RAID.
- Minimum de mots, langues : non trouvé.

**Mesure contrôlable.** Dépôt RAID, soumission du 9 février 2026 : détection à 1 % de faux positifs de 99,7 % sans attaque, 95,7 % sous paraphrase, 96,2 % sous homoglyphes, **90,3 % sous caractères de largeur nulle** ; AUROC 0,999 [T]. La « première place » dépend de la date : dans les fichiers lus ce jour, la soumission de Winston AI du 24 septembre 2026 a des chiffres plus hauts [T]. Rappel de `BENCH-text-detectors.md` : un score RAID très haut signale souvent un entraînement sur RAID et ne dit rien du français.

**Authorship** [F] : ce n'est pas un détecteur. L'extension enregistre l'origine de chaque passage pendant l'écriture dans Google Docs ou Word : tapé, collé depuis une source connue, collé depuis une source inconnue, généré par IA, modifié par l'IA de Grammarly. Le rapport montre les parts. Un test de Plagiarism Today note que rien n'est suivi hors du navigateur [T]. C'est de la provenance déclarée au moment de l'écriture, comme C2PA pour l'image.

### 2.7 ZeroGPT

- **Annonces** (https://www.zerogpt.com/) [F, publicité] : « DeepAnalyse Technology », une « méthodologie en plusieurs étapes » sans autre détail ; 98,4 % d'exactitude ; moins de 1 % de faux positifs ; « toutes les langues » ; plus de 35 familles de LLM. Entrée limitée à 15 000 caractères dans la version gratuite.
- **Sortie** : une jauge avec « le pourcentage d'IA dans le texte » [F]. Le propriétaire a relevé neuf libellés gradués, de « écrit par un humain » à « généré par IA/GPT », et une FAQ citant 98 % après 20 millions d'articles ; ces deux points n'apparaissaient pas dans la page lue ce jour.
- **Mécanisme, jeu d'entraînement, jeu de test, méthode de calibration** : non trouvé. Aucune des annonces n'est vérifiable.
- **Indépendant** : aucune étude à comité de lecture ne reproduit les 98 %. Liang et collègues (Patterns, 2023) incluent ZeroGPT parmi sept détecteurs qui classent IA en moyenne 61 % des essais TOEFL [T]. Des tests de sites tiers donnent 20,5 % de faux positifs sur 78 textes humains, et 26,4 % sur 37 874 essais [T faible : sites de revue, parfois liés à des concurrents]. Une étude PeerJ Computer Science de 2025 citerait 64 % d'exactitude et 17 % de faux positifs [non vérifié].

### 2.8 isitchatgpt.com

Depuis le commit `7b5e2b4`, le cœur a une couche `rhetoric` inspirée de ce site ; les motifs ne sont pas redécrits ici.

**Ce que dit la page d'accueil** [F] : analyse stylistique de deux motifs « souvent trouvés » dans le texte IA, plus une « analyse structurelle » et des explications pédagogiques. Aucun chiffre d'exactitude. Aucune mention de la méthode (règles ou LLM) : **non trouvé**. Dix langues déclarées dans les métadonnées de la page. Une extension de navigateur est proposée en mode développeur ; elle n'a pas été examinée.

**Ce que contient la page « research »** (https://isitchatgpt.com/research, lue telle qu'affichée) :

- Ce n'est pas une page de recherche. C'est une base de 50 exemples de motifs, avec des filtres (type, statut de validation, faux positifs, langue), un bloc « Analytics & Insights » et un panneau « Curation Actions » [T, lecture directe].
- **Aucune étude citée, aucune mesure d'exactitude, de rappel ou de faux positifs dans le texte affiché.** Le bloc « Analytics & Insights » et les filtres n'ont pas été ouverts. L'affirmation « ces motifs sont fréquents dans le texte IA » ne repose sur aucune source publiée par le site.
- Chaque exemple porte une étiquette « medium confidence » ou « high confidence ». Sa définition n'est pas donnée.
- **Les exemples semblent être des extraits de textes soumis par les utilisateurs.** Les deux premiers sont deux paires de phrases d'un courriel formel français (« Si vous… nous vous… ») classées « dyptych, medium confidence ». Elles correspondent au faux positif observé par le propriétaire (30 % de probabilité IA sur un courriel formel). Si c'est bien son texte, **le site publie des extraits de ce qu'on lui soumet**. À vérifier par le propriétaire, et à ne pas reproduire avec un texte sensible. [T pour la présence des extraits, D pour leur origine]
- **Langue mal identifiée** : plusieurs extraits en néerlandais sont étiquetés « Spanish » [T].
- **Mode de faux positif** : sont classés « diptyque pivot » des paires ordinaires condition puis conséquence, concession puis nuance (« Évidemment… mais… »), question puis réponse, et des comparaisons factuelles (« Les deux textes… Cependant… »). Sont classées « triptyque » de simples énumérations de trois termes. Le français soutenu et l'écrit scolaire emploient ces tournures en permanence. [T pour les exemples, D pour la généralisation]
- Erreurs d'étiquette de langue et étiquettes de confiance par extrait font penser à une classification par LLM plutôt qu'à des règles [D, non confirmé].

Leçon pour la couche `rhetoric` [D] : un compte de motifs ne doit jamais devenir une probabilité. Le choix déjà fait (décrire, ne jamais changer le verdict) est le bon. Il faudra mesurer la densité de ces motifs sur du texte humain français formel avant d'afficher quoi que ce soit comme « inhabituel ».

### 2.9 Autres détecteurs de texte, en bref

| Produit | Ce que les sources publiques disent | Indépendant |
|---|---|---|
| **Winston AI** | Minimum 500 caractères [F]. « Score humain » global et carte de prédiction par phrase ; le fournisseur écrit que le score global est plus fiable que la carte par phrase, surtout sur les passages courts [F]. 23 langues dans l'API récente, détection automatique [F]. Mécanisme : non trouvé | RAID, soumission du 24 sept. 2026 : 99,99 % à 1 % de faux positifs sans attaque, 99,3 % sous paraphrase [T]. Aussi haut, cela évoque un entraînement sur des données proches de RAID [D] |
| **Sapling** | API documentée : score du document, scores par phrase calculés dans la même passe, surlignage par token en option ; jusqu'à 200 000 caractères, 300 recommandés au minimum ; **un texte court est marqué avec une raison de faible confiance `short_text`** ; 8 langues [F, https://sapling.ai/docs/api/detector/] | non trouvé |
| **QuillBot** | Mécanisme : non trouvé. Le même éditeur vend un paraphraseur | RAID, soumission du 30 janv. 2025 : 99,2 % à 1 % de faux positifs sans attaque, 94,1 % sous paraphrase, 91,4 % sous caractères de largeur nulle [T] |

## 3. Image

| Produit | Mécanisme public | Sortie | Indépendant |
|---|---|---|---|
| **Hive Moderation** | Classifieur ; attribue aussi le générateur probable (Midjourney, Stable Diffusion…) [F]. Taille et données : non trouvé | Liste de classes avec un score de 0 à 1 chacune : `ai_generated`, `not_ai_generated`, puis une classe par générateur [F, docs.thehive.ai]. Seuil recommandé : non trouvé | Étude « Organic or Diffused » de l'université de Chicago (Ha et collègues, 2024) : Hive fait mieux que les autres détecteurs automatiques et que la plupart des experts humains, mais se trompe autrement qu'eux ; l'association humain et machine est la meilleure ; les perturbations de Glaze le font échouer [T, via extraits]. Le « 98,03 % et 0 % de faux positifs » est repris par le blog de Hive [F]. Purdue 2025 : 83,6 % (voir `FALLBACK` §5) |
| **Sightengine** | Détection « sur les pixels seulement » : les métadonnées, l'EXIF et C2PA n'influencent pas le score [F, https://sightengine.com/docs/ai-generated-image-detection] | Un score `ai_generated` de 0 à 1 ; scores par générateur en option [F] | non trouvé ; le fournisseur publie son propre banc [F] |
| **AI or Not** | Non trouvé | Verdict, scores de confiance, indices par générateur [F] | Purdue 2025 : 89,2 % (`FALLBACK` §5) |
| **Illuminarty** | Non trouvé | Probabilité et zones suspectes [F, mém.] | Purdue 2025 : 49,4 %, 57 % de fausses acceptations (`FALLBACK` §5) |
| **TruthScan** | Non trouvé | Non trouvé | non trouvé |
| **Reality Defender** | **Ensemble pondéré de plusieurs modèles** ; le poids de chaque modèle dépend de sa fiabilité sur le type de contenu ; modèles séparés pour le visage et pour l'image entière [F, aide publique] | Verdict final à **trois états : Authentic, Suspicious, Manipulated** ; score agrégé ; résultat de chaque modèle dans `models[]` ; un modèle hors de son domaine rend **`NOT_APPLICABLE` avec un score nul** ; cartes de chaleur [F] | Purdue 2025 : 93,5 % (`FALLBACK` §5) |

À retenir [D] :

- Sightengine sépare strictement pixels et provenance. C'est la séparation déjà retenue par isitai entre preuves déterministes et score statistique.
- `NOT_APPLICABLE` par modèle est exactement le tri-état « pas cherché » de `OSS-patterns-reuse.md` §1.4.
- L'attribution du générateur est le service que tous vendent. Elle demande des données d'entraînement par générateur, tenues à jour : hors de portée d'une bibliothèque.

## 4. Audio et vidéo

| Produit | Mécanisme public | Sortie et chiffres annoncés | Indépendant |
|---|---|---|---|
| **Reality Defender** (audio, vidéo) | Audio : analyse par **segments de 3 secondes**, puis un modèle d'agrégation décide pour le fichier. Vidéo : trois modèles fondus en un score d'ensemble [F] | Mêmes trois états que pour l'image [F] | voir `FALLBACK` §5 |
| **Pindrop Pulse** | Détection de « vivacité » de la voix ; en centre d'appels, combinée à la reconnaissance de la voix, de l'appareil et du comportement [F] | Score de vivacité. 99 % annoncés pour la combinaison des couches, pas pour la détection seule [F] | Test de NPR : 81 extraits sur 84 bien classés (96,4 %), extraits de 6 secondes en moyenne [T, mais rapporté ici par la page de Pindrop ; article de NPR non relu] |
| **Resemble Detect** (DETECT-3B Omni) | Modèle multimodal de grande taille [F] | Taux d'erreur égal « sous 6 % » sur ses jeux ; 98 % annoncés ; nombre de langues incohérent d'une page à l'autre (38, 40 ou 51) [F] | Prépublication de 2026 cosignée par ses employés : pas indépendante |
| **ElevenLabs AI Speech Classifier** | Ne reconnaît que l'audio produit par ElevenLabs [F]. Classifieur ou watermark : non trouvé | 99 % de précision et **80 % de rappel** sur l'audio non modifié ; baisse après codec ou réverbération ; outil désormais « ancien », remplacé par un « Audio Detector » [F] | non trouvé |
| **Deepware** | Détection de visages truqués en vidéo ; mécanisme non trouvé | non trouvé | taux de faux négatifs de 68 % (`FALLBACK` §5) |
| **Sensity** | Non trouvé (offre d'entreprise) | non trouvé | non trouvé |

À retenir [D] : même les fournisseurs audio découpent en segments courts et agrègent ; le détecteur d'un générateur pour ses propres sorties annonce 80 % de rappel seulement, sur des fichiers intacts.

## 5. Détecteurs des fournisseurs de modèles

| Fournisseur | Mécanisme | Sortie | Chiffres et limites |
|---|---|---|---|
| **OpenAI, classifieur de texte** (retiré) | Modèle de langue affiné sur des paires humain et IA sur le même sujet [F, mém. : page en 403 ce jour] | Cinq libellés, de « très improbable » à « probable », avec une zone centrale « pas clair » [mém.] | 26 % de textes IA détectés pour 9 % de textes humains accusés ; peu fiable sous 1 000 caractères ; anglais surtout ; retiré le 20 juillet 2023 pour « faible exactitude » [F, mém.] |
| **OpenAI, classifieur d'images** | Classifieur binaire « vient de DALL-E 3 ou non », ouvert à des chercheurs [F] | probabilité | Environ 98 % des images DALL-E 3 détectées, moins de 0,5 % d'images non IA signalées ; résiste à la compression, au recadrage, à la saturation ; **ne signale que 5 à 10 % des images d'autres générateurs** [F, via presse de mai 2024] |
| **OpenAI aujourd'hui** | C2PA et watermark SynthID dans les images ; vérificateur en ligne (voir `ROADMAP-detection.md` §6) | — | — |
| **Google SynthID Detector** | Lecture d'un watermark posé à la génération. Aucune inférence sur le contenu non marqué [F, https://blog.google/technology/ai/google-synthid-ai-content-detector/] | « Watermark détecté » ou « non détecté », avec les zones de l'image ou les segments audio et vidéo concernés. « Non détecté » est présenté comme ne prouvant pas l'absence d'IA [F et presse]. Un état intermédiaire « incertain » : non trouvé pour le portail | Ouvert au public en octobre 2026, couvre Google, OpenAI, Nvidia et Kakao [T, presse ; billet officiel non trouvé]. En ligne, clés privées |
| **Meta** | Trois voies : métadonnées C2PA et IPTC des autres générateurs, watermark invisible de ses propres outils, classifieurs en développement pour le contenu sans marque [F, https://about.fb.com/news/2024/02/labeling-ai-generated-images-on-facebook-instagram-and-threads/] | Étiquette « AI info » sur la publication | Meta écrit qu'il n'est pas possible d'identifier tout le contenu IA et que les marques peuvent être retirées [F]. Chiffres : non trouvé |
| **Adobe Content Authenticity** | Outil « Inspect » : lit les Content Credentials ; s'ils ont été retirés, tente de les **retrouver par watermark invisible ou par empreinte de similarité visuelle** dans son registre [F, helpx.adobe.com] | Affiche l'historique retrouvé, ou rien | Ne détecte pas l'IA : retrouve une provenance. La récupération peut échouer après un traitement destructeur [F]. Le registre est en ligne |

À retenir [D] : les fournisseurs de modèles ont abandonné la détection statistique de texte (OpenAI, 2023) et misent sur la provenance et le watermark. Leur classifieur d'image ne généralise pas hors de leur propre générateur. C'est l'argument le plus fort pour garder le score statistique d'isitai dans un champ séparé et secondaire.

## 6. Ce que la présentation des résultats nous apprend

### 6.1 Deux grandeurs que les produits confondent

| Grandeur | Sens | Qui l'affiche |
|---|---|---|
| **Probabilité de classe** | « quelle chance que ce document soit IA » (ou que le détecteur ait raison) | GPTZero (`class_probabilities`), Originality, Hive, Sightengine, isitchatgpt |
| **Part du texte signalée** | « quelle fraction des phrases ou fenêtres est classée IA » | Turnitin, Grammarly, Pangram (trois parts), Copyleaks (résumé), ZeroGPT (« pourcentage d'IA dans le texte », ambigu) |

Un lecteur voit « 30 % » dans les deux cas. La première grandeur dépend de la prévalence (`FALLBACK-probabilistic.md` §2) ; la seconde est une mesure descriptive, sans prévalence, qui correspond au champ `spans` déjà prévu. [D]

### 6.2 Les quatre produits demandés

| | GPTZero | Grammarly | ZeroGPT | isitchatgpt |
|---|---|---|---|---|
| Chiffre principal | trois probabilités (IA, mixte, humain) | part du texte qui « semble » IA | jauge en pourcentage | compte de motifs, densité, probabilité IA |
| Incertitude montrée | catégorie de confiance haute, moyenne, basse ; phrase de confiance en mots | aucune sur le chiffre ; avertissement en prose | neuf libellés gradués (relevé du propriétaire) | « confiance » déclarée, non définie |
| Localisation | surlignage par phrase | par section | phrases surlignées [mém.] | chaque motif cité avec son extrait |
| Explication | onglets séparés ; message si l'ensemble est en désaccord | FAQ générale | aucune | explication pédagogique par motif |
| Avertissement | faux négatif préféré au faux positif en contexte scolaire | « aucun détecteur n'est concluant » ; résultat à replacer dans une évaluation d'ensemble | aucun relevé | « outil éducatif » |
| Chiffre défini et contrôlable ? | en partie : la classe `high` a des taux d'erreur publiés, pas les autres | non | non | non |
| Version du modèle dans la sortie | identifiant daté publié ; présence dans la réponse déduite [D] | non trouvé | non trouvé | non trouvé |

Lecture [D] :

- **GPTZero est le plus proche du dessin `coefficient`.** Il sépare la classe, la probabilité, une catégorie de confiance adossée à des taux d'erreur mesurés, et un identifiant de version daté (publié dans le journal ; présence dans chaque réponse déduite). Il lui manque l'intervalle et la prévalence : sa probabilité « calibrée » ne vaut que pour la population de son jeu de calibration, ce qu'il ne dit pas.
- **Grammarly a les meilleurs mots** : « semble », pas « est » ; un avertissement qui dit que la détection ne conclut pas. Mais son chiffre n'a ni définition ni incertitude.
- **ZeroGPT est le contre-exemple.** Neuf libellés gradués fabriquent neuf niveaux de fausse précision à partir d'un seul score non documenté. Une jauge se lit comme une mesure physique.
- **isitchatgpt montre le bon réflexe et la mauvaise conclusion.** Citer le passage et expliquer le motif rend le résultat discutable, donc honnête. Convertir un compte de tournures en « 30 % de probabilité IA » ne l'est pas : rien ne relie ce compte à une fréquence mesurée.

### 6.3 Ce qui s'accorde avec `coefficient`, et ce qui le contredit

| Élément de présentation | Avec `lr` + intervalle + `calibration_id` |
|---|---|
| Identifiant de version daté (GPTZero ; présence dans chaque résultat déduite [D]) | **S'accorde** : c'est `calibration_id` |
| Catégorie de confiance adossée à des taux d'erreur publiés (GPTZero `high`) | **S'accorde**, si chaque bande est définie par une plage de `lr` et que la table des erreurs est publiée pour toutes les bandes |
| Abstention : minimum de longueur, astérisque sous 20 %, `short_text`, `NOT_APPLICABLE` | **S'accorde** : c'est `lr: null` avec un `warning`, ou le verdict `indeterminate` |
| Surlignage par phrase ou fenêtre, part du texte signalée | **S'accorde**, dans `spans`, à condition de ne jamais l'appeler probabilité |
| Explication par motif cité (isitchatgpt, AI Phrases de Copyleaks) | **S'accorde**, dans `signals` avec un `locus`, sans effet sur le verdict |
| Avertissement en prose (Grammarly) | **S'accorde** : champ `limits` |
| Trois classes dont « mixte » | **Neutre** : utile comme description de `spans` hétérogènes, pas comme troisième probabilité |
| Pourcentage unique, jauge | **Contredit** `FALLBACK` §2 : sera lu comme une probabilité a posteriori |
| Neuf libellés gradués | **Contredit** : fausse précision |
| Probabilité tirée d'un compte de motifs | **Contredit** : pas de calibration possible |

Tension à trancher par le propriétaire : `OSS-patterns-reuse.md` §7 montre encore `"confidence": { "value": 62, "kind": "heuristic" }`, alors que `FALLBACK-probabilistic.md` §2 interdit de rendre un pourcentage. Ce que font les concurrents plaide pour la règle de `FALLBACK` : chaque fois qu'un nombre de 0 à 100 est affiché, il est lu comme une probabilité, quelle que soit l'étiquette posée à côté. Si une valeur heuristique doit sortir, mieux vaut une bande en mots qu'un nombre. [D]

## 7. Synthèse pour le propriétaire

### 7.1 Mécanismes récurrents, classés par solidité de la preuve

| # | Mécanisme | Preuve | Reproductible hors ligne ? |
|---|---|---|---|
| 1 | Découpage en phrases ou fenêtres, score par morceau, agrégation | Forte : documenté chez GPTZero, Pangram, Turnitin, Grammarly, Copyleaks, Sapling, Winston, Reality Defender (audio) | **Oui, léger et complet.** Coût nul une fois le détecteur présent |
| 2 | Classifieur supervisé de type transformeur | Forte : rapport Pangram, journal GPTZero, Originality, Turnitin | **Complet seulement** (un encodeur d'environ 150 M de paramètres quantifié tient dans 150 Mo). Pas en léger : les petits modèles s'effondrent (`ROADMAP` §3.1) |
| 3 | Abstention : minimum de longueur, zone basse masquée, drapeau de faible confiance | Forte : Turnitin, Sapling, Winston, Pangram, Reality Defender | **Oui, léger.** Gratuit |
| 4 | Prétraitement comme partie du détecteur (titres, listes, références, caractères spéciaux) | Forte : journal GPTZero, carte Pangram | **Oui, léger** |
| 5 | Modèles ou tables séparés par langue | Forte : GPTZero base et multilingue, Turnitin, mesures propres du projet | **Oui** pour les tables de calibration (léger) ; un modèle multilingue va en complet |
| 6 | Extraction de négatifs difficiles avec jumeaux synthétiques, perte asymétrique | Moyenne : un seul fournisseur la décrit (Pangram), mais en détail et avec un rapport technique | **À l'entraînement seulement.** La bibliothèque ne peut que livrer un modèle entraîné ainsi ; la boucle demande des millions de textes humains sous licence et un LLM. Faisable à petite échelle par le projet [D] |
| 7 | Version datée du modèle | Moyenne : identifiants datés publiés par GPTZero ; modèles numérotés chez Pangram et Originality ; présence dans chaque réponse non vue [D] | **Oui, léger.** Déjà prévu |
| 8 | Classes « mixte », « poli », « assisté », degré de retouche | Moyenne : GPTZero et Pangram les annoncent ; les études indépendantes disent que cela marche mal (`ROADMAP` §5) | **Partiel, complet** : uniquement comme description des fenêtres hétérogènes |
| 9 | Ensemble de modèles avec poids selon le type de contenu, et état « non applicable » | Moyenne : Reality Defender (documenté), GPTZero en 2023 | **Partiel.** Le projet a mesuré que l'empilement n'apporte rien en texte ; l'état « non applicable » est, lui, à reprendre |
| 10 | Liste d'expressions sur-représentées dans le texte IA (AI Phrases) | Moyenne : Copyleaks seulement, six langues | **Oui, léger** : une table de rapports de fréquence pèse quelques Ko. À traiter comme explication, pas comme score |
| 11 | Attribution du générateur | Moyenne : Hive, Sightengine, AI or Not | **Non** en pratique : données par générateur à tenir à jour |
| 12 | Recherche dans un stock de contenus IA déjà publiés | Faible : Copyleaks (AI Source Match) ; Adobe pour les images | **Non** : il faut un index en ligne |
| 13 | Watermark propriétaire | Forte, mais chez les fournisseurs de modèles seulement | **Non** : clés privées. Les watermarks ouverts restent possibles (`ROADMAP` §3) |
| 14 | Enregistrement du processus d'écriture | Forte pour un produit (Grammarly Authorship) | **Non** : il faut être dans l'éditeur. L'équivalent pour isitai est de lire les métadonnées de révision des documents |
| 15 | Perplexité et « burstiness » | Faible aujourd'hui : première génération de GPTZero [mém.], remplacée par un classifieur d'après son journal | **Complet** (deux petits modèles de langue) ; c'est la voie déjà mesurée par le projet |
| 16 | Motifs rhétoriques comptés | Très faible : un site, aucune mesure | **Oui, léger**, mais seulement descriptif |

### 7.2 Comment les meilleurs tiennent les faux positifs bas

1. **Une réserve de textes humains datés d'avant les LLM**, grande et variée (Pangram : 28 millions de documents de 2021 ou avant ; Turnitin : validation sur 800 000 textes d'avant ChatGPT ; Grammarly et GPTZero : textes anciens ou « vérifiés par archive »). La date est la seule étiquette « humain » sûre. Le corpus Wikipédia d'avant 2019 du projet suit le même principe ; il lui manque le volume et la variété.
2. **Chercher ses propres faux positifs et s'entraîner dessus**, avec un jumeau IA par cas (Pangram).
3. **Pénaliser davantage l'erreur sur un humain** pendant l'entraînement (Pangram), et le dire dans la doctrine d'usage (GPTZero : le faux négatif est préférable).
4. **Mesurer par domaine et par langue, et publier le tableau** (Pangram). Les pires cases sont instructives : poésie, texte traduit automatiquement, recettes, listes.
5. **Des tests unitaires de non-régression sur des textes humains célèbres**, bloquants (Pangram). Transférable tel quel dans l'intégration continue du projet.
6. **Un jeu de cas difficiles alimenté par les faux positifs signalés** (Pangram ; le journal de GPTZero montre la même pratique version après version).
7. **Refuser les entrées hors domaine** : texte trop court, listes, tableaux, bibliographies, code (Turnitin, Pangram, Sapling).
8. **Marquer ou masquer la zone d'incertitude** au lieu d'y afficher un petit chiffre nu (Turnitin sous 20 % : astérisque [F], masquage [mém.]).
9. **Exiger une preuve plus forte pour le mot le plus fort** : seuil « entièrement IA » relevé à 0,88 chez GPTZero ; seuil à 0,75 pour « IA » chez Pangram, avec deux bandes « assisté » en dessous.
10. **Annoncer un taux par phrase distinct du taux par document** (Turnitin : 4 % contre moins de 1 %). Le surlignage est toujours moins fiable que le verdict global ; Winston le dit aussi.

Réserve : tous ces taux sont mesurés par les fournisseurs. Les mesures indépendantes sont nettement moins bonnes (`FALLBACK-probabilistic.md` §5).

### 7.3 Présentation : quoi copier, quoi éviter

À copier :

- La version datée du modèle et de la table dans chaque résultat (principe des identifiants datés de GPTZero).
- Le minimum de longueur avec une raison lisible par machine, comme `short_text` (Sapling, Turnitin).
- Les fenêtres avec positions de caractères et un score par fenêtre (Pangram), accompagnées de l'avertissement que la localisation est moins fiable que le résultat global (Winston, Turnitin).
- Des bandes en mots, peu nombreuses (trois ou quatre), chacune adossée à un taux d'erreur publié (GPTZero pour `high`, à étendre à toutes).
- Le verbe « semble » et l'avertissement « ne conclut pas » (Grammarly).
- L'état « non applicable » par couche (Reality Defender) et « non détecté ne veut pas dire absent » (SynthID Detector).
- Le motif cité avec son extrait, à titre d'explication (isitchatgpt, Copyleaks).

À éviter :

- Un pourcentage unique ou une jauge (ZeroGPT, Grammarly).
- Plus de quatre libellés gradués (ZeroGPT).
- Le mot « humain » comme verdict (presque tous). Le projet l'a déjà exclu.
- Une probabilité dérivée d'un compte de motifs (isitchatgpt).
- Un chiffre d'exactitude sans jeu, sans date et sans auteur de la mesure (ZeroGPT, Resemble, AI or Not).
- Publier ou conserver ce que l'utilisateur soumet (isitchatgpt, à confirmer). Une bibliothèque hors ligne a ici un avantage à dire clairement.

### 7.4 Recommandations pour le score d'isitai

| # | Recommandation | Source |
|---|---|---|
| 1 | Garder `lr`, `lr_interval`, `calibration_id` ; ne rendre aucun pourcentage. Ajouter une bande en mots (par exemple « faible », « modéré », « fort », « non concluant ») définie par des plages de `lr`, avec la table d'erreurs publiée pour chaque bande | GPTZero `confidence_category` ; contre-exemple ZeroGPT ; `FALLBACK` §2 |
| 2 | Fixer un minimum de longueur par couche et rendre `lr: null` avec une raison `short_text` en dessous. Point de départ à mesurer : 300 mots pour un verdict, les concurrents allant de 300 caractères (Sapling) à 300 mots (Turnitin) | Turnitin, Sapling, Winston |
| 3 | Rendre des `spans` par fenêtre avec positions de caractères, et une **part signalée** nommée comme telle (`flagged_fraction`), distincte du `lr` du document. Documenter que le taux d'erreur par fenêtre est plus élevé | Pangram `windows`, Turnitin (4 % par phrase), Winston |
| 4 | Ne pas afficher la part signalée sous un plancher à mesurer ; rendre « non concluant » | Turnitin (astérisque sous 20 % [F] ; masquage du chiffre [mém.]) |
| 5 | Nommer et journaliser le prétraitement : retrait des titres, listes, références, code, normalisation des caractères invisibles. Les soumissions RAID de Grammarly et QuillBot perdent environ 8 et 9 points sur les caractères de largeur nulle (99,2 % à 91,4 % et 99,7 % à 90,3 %) : normaliser avant le modèle | Journal GPTZero, carte Pangram, `results.json` RAID |
| 6 | Tables de calibration par langue, et refus de rendre un `lr` pour une langue sans table. Publier le tableau des faux positifs par langue et par domaine, y compris les mauvaises cases | Pangram (tableau par domaine), GPTZero (modèle multilingue séparé), mesures du projet |
| 7 | Tests unitaires bloquants en intégration continue : une liste de textes humains célèbres et de textes formels français (courriels administratifs, textes juridiques) qui ne doivent jamais dépasser le seuil | Pangram ; faux positif observé sur isitchatgpt |
| 8 | Jeu de cas difficiles versionné dans le dépôt, alimenté par chaque faux positif signalé | Pangram, journal GPTZero |
| 9 | Si un classifieur est entraîné pour le paquet complet : textes humains d'avant 2021, jumeaux synthétiques des faux positifs, perte asymétrique. Sinon, ne livrer qu'un modèle dont l'auteur documente une méthode comparable | Rapport Pangram |
| 10 | Chaque couche rend `found`, `absent`, `inconclusive` ou `not_applicable` ; « absent » est toujours accompagné de « ne prouve pas l'origine humaine » | Reality Defender, SynthID Detector, `OSS-patterns` §1.4 |
| 11 | La couche `rhetoric` et une éventuelle table d'expressions restent descriptives : motif, extrait, position. Aucune conversion en score. Mesurer d'abord leur densité sur du texte humain français formel | isitchatgpt (aucune mesure, faux positifs sur le français formel), Copyleaks AI Phrases |
| 12 | Dater les tables et afficher un avertissement quand la table est plus ancienne que N mois : les concurrents ré-entraînent toutes les deux à trois semaines | Journal GPTZero |
| 13 | Paquet léger (moins de 30 Mo) : provenance, métadonnées, watermarks ouverts, règles, abstention, prétraitement, motifs descriptifs. Aucun `lr` de texte : dans le banc du projet, les détecteurs sans modèle accusent à tort 14 à 72 % des textes humains hors de leur distribution, et les petits classifieurs s'effondrent sous paraphrase. Pour l'image et l'audio, les petits modèles de `FALLBACK` §8 (FerretNet, 4 Mo ; AASIST, 1 à 2 Mo) tiennent dans le budget ; rien dans cette étude ne les valide ni ne les écarte, les concurrents ne publiant pas la taille de leurs modèles : à décider sur le banc du projet, comme indice faible | `BENCH-text-detectors.md` §1 et §4 ; `ROADMAP` §3.1 ; `FALLBACK` §4.2, §4.3 |
| 14 | Paquet complet (jusqu'à 500 Mo) : un seul classifieur ou un seul détecteur à modèle de langue par média, fenêtres, tables par langue. Pas d'attribution du générateur, pas de classe « humanisé » : ces promesses demandent un ré-entraînement continu | §7.1 lignes 8 et 11 |
| 15 | Dans la documentation, répéter la doctrine des meilleurs : le résultat est un indice parmi d'autres, jamais une preuve, et un faux négatif vaut mieux qu'une fausse accusation | Grammarly, GPTZero, Turnitin |

## 8. Affirmations qui reposent sur la seule parole du fournisseur

| Affirmation | Fournisseur |
|---|---|
| Taux de faux positifs d'environ 1 sur 10 000, tableau par domaine, 0 % sur les essais TOEFL, « 38 fois moins d'erreurs » | Pangram |
| Efficacité de l'extraction de négatifs difficiles avec miroirs synthétiques | Pangram (méthode décrite, gain non reproduit par un tiers) |
| 99,1 % et 98,4 % pour la catégorie de confiance `high` ; probabilités « calibrées » | GPTZero |
| Tout le contenu du journal des versions (baisse des faux positifs, rappel sur les nouveaux modèles) | GPTZero |
| 0,5 %, 1,5 % et moins de 1 % de faux positifs selon le modèle ; « 99 % et plus » | Originality.ai |
| Moins de 1 % de faux positifs par document, 4 % par phrase, 54 % des erreurs voisines d'un passage IA | Turnitin |
| 99 % d'exactitude, première place sur RAID, entraînement sur des dizaines de milliers de textes | Grammarly (les chiffres RAID eux-mêmes sont contrôlables dans le dépôt) |
| 98,4 % d'exactitude, moins de 1 % de faux positifs, toutes les langues, « DeepAnalyse » | ZeroGPT |
| Les deux motifs rhétoriques sont caractéristiques du texte IA | isitchatgpt (aucune source) |
| 30 langues, « très peu de fausses alertes », fonctionnement d'AI Source Match | Copyleaks |
| Score global plus fiable que la carte par phrase ; 23 langues | Winston AI |
| 98,03 % et 0 % de faux positifs | Hive (reprise d'une étude tierce par son blog ; article non relu) |
| Pondération de l'ensemble selon la fiabilité de chaque modèle | Reality Defender |
| 99 % avec les couches combinées ; 96,4 % au test de NPR tel que rapporté par Pindrop | Pindrop |
| 98 % sur 38 langues ou plus, taux d'erreur égal sous 6 % | Resemble |
| 99 % de précision et 80 % de rappel | ElevenLabs |
| 98 % sur DALL-E 3, moins de 0,5 % de faux positifs ; 26 % et 9 % pour le classifieur de texte | OpenAI |
| Robustesse du watermark, sens de « non détecté » | Google SynthID Detector |
| Récupération des Content Credentials par watermark ou empreinte | Adobe |

## 9. Non trouvé ou non vérifié

| Point | État |
|---|---|
| Taille et architecture exactes des modèles de GPTZero, Pangram, Originality, Turnitin, Copyleaks | Non publié dans les sources lues |
| FAQ officielle de Turnitin, billet d'OpenAI sur le classifieur de texte | 403 ce jour ; contenu rappelé de mémoire |
| Référence de l'API Copyleaks, documentation image de Hive | 404 ce jour ; contenu via extraits de recherche |
| Brevets (Google Patents) | Non cherchés, faute de budget |
| Neuf libellés et « 20 millions d'articles » de ZeroGPT | Relevés par le propriétaire, absents de la page lue |
| Phrase exacte de Grammarly sur les textes d'avant 2021 | Résumé automatique douteux ; à relire |
| Origine des extraits de la base d'isitchatgpt ; méthode (règles ou LLM) | Déduction ; non confirmé |
| Finalisation du rachat de GPTZero | Annonce d'accord seulement |
| Portail SynthID Detector ouvert au public en octobre 2026 | Presse seulement |
| Étude Weber-Wulff 2023, étude PeerJ 2025 sur ZeroGPT, article de NPR sur Pindrop, étude de Chicago sur Hive | Citées de mémoire ou via extraits ; non relues |
| Prix | Sites de revue seulement, chiffres divergents ; aucune page de prix officielle lue |
| Sensity, TruthScan, Deepware, Illuminarty, QuillBot : mécanisme | Rien de public trouvé dans le temps imparti |
| Rapport EditLens de Pangram ; billet LessWrong critique | Cités, non relus |

## 10. Sources

- GPTZero : https://gptzero.me/news/ai-detection-model-api-updates ; https://support.gptzero.me/articles/8947054519-how-do-i-use-and-interpret-the-results-from-your-api ; https://support.gptzero.me/articles/4083713560-how-do-i-turn-the-probabilities-from-your-api-into-outcomes
- Rachat : https://blog.superhuman.com/superhuman-to-acquire-gptzero/ ; https://www.businesswire.com/news/home/20260623083788/en/Superhuman-to-Acquire-GPTZero-AI-Authenticity-Platform
- Pangram : https://arxiv.org/abs/2402.14873 ; https://www.pangram.com/blog/all-about-false-positives-in-ai-detectors ; https://www.pangram.com/research/model-card/pangram-3-3 ; https://www.pangram.com/blog/v3-api-migration-guide ; https://www.lesswrong.com/posts/qEjSaKxxLrpeHfiZG/we-underestimate-the-weaknesses-of-pangram
- Originality.ai : https://originality.ai/blog/how-does-ai-content-detection-work ; https://originality.ai/blog/ai-content-detection-accuracy
- Copyleaks : https://docs.copyleaks.com/concepts/products/ai-text-detection-api.md ; https://copyleaks.com/ai-content-detector/ai-logic ; https://docs.copyleaks.com/concepts/features/ai-source-match
- Turnitin : https://www.turnitin.co.uk/blog/understanding-the-false-positive-rate-for-sentences-of-our-ai-writing-detection-capability ; https://campustechnology.com/articles/2023/05/turnitin-says-its-ai-detector-analyzed-38m-submissions-in-six-weeks.aspx ; https://www.plagiarismtoday.com/2025/08/27/turnitin-launches-anti-ai-humanizer-feature/
- Grammarly : https://www.grammarly.com/ai-detector ; https://www.grammarly.com/authorship ; https://www.plagiarismtoday.com/2025/11/06/how-grammarly-launders-ai-generated-content/
- ZeroGPT : https://www.zerogpt.com/ ; Liang et collègues 2023 : https://www.cell.com/patterns/fulltext/S2666-3899(23)00130-7
- isitchatgpt : https://isitchatgpt.com/ ; https://isitchatgpt.com/research
- Winston AI, Sapling : https://help.gowinston.ai/understanding-winston-ai/what-types-of-content-can-i-scan-with-winston-ai ; https://sapling.ai/docs/api/detector/
- RAID : https://github.com/liamdugan/raid/tree/main/leaderboard/submissions (dossiers `gptzero`, `grammarly`, `QuillBot`, `winston-ai`)
- Image : https://docs.thehive.ai/docs/ai-generated-content-detection ; https://sightengine.com/docs/ai-generated-image-detection ; https://docs.aiornot.com/ ; https://www.mat.ucsb.edu/~g.legrady/academic/courses/24f255/organicOrDiffused.pdf
- Reality Defender : https://intercom.help/reality-defender/en/articles/15090070-image-detection-how-results-are-returned ; https://intercom.help/reality-defender/en/articles/15089732-audio-detection-how-results-are-returned ; https://intercom.help/reality-defender/en/articles/15089028-video-detection-how-results-are-returned
- Audio : https://www.pindrop.com/article/npr-audio-deepfake-study/ ; https://www.resemble.ai/detect-3b-omni/ ; https://elevenlabs.io/docs/product-guides/audio-tools/ai-speech-classifier
- Fournisseurs de modèles : https://www.engadget.com/openai-says-it-can-detect-images-made-by-its-own-software-mostly-170012976.html ; https://blog.google/technology/ai/google-synthid-ai-content-detector/ ; https://about.fb.com/news/2024/02/labeling-ai-generated-images-on-facebook-instagram-and-threads/ ; https://helpx.adobe.com/creative-cloud/help/cai/adobe-content-authenticitiy-inspect.html
