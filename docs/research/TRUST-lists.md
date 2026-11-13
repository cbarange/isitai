# Listes de confiance C2PA — recherche et essais du 2026-11-12

Ce document résume ce qui a été appris en embarquant les listes de confiance, et les risques acceptés. Les fichiers eux-mêmes et leur provenance sont décrits dans `crates/isitai-core/trust/SOURCE.md`.

## 1. Pourquoi une liste de confiance

Un manifeste C2PA peut être signé par n'importe qui. Sans liste de confiance, une signature valide ne prouve rien : isitai ne donne alors qu'`ai-signal`. Le verdict `ai-proven` exige que `c2pa-rs` rende l'état `Trusted`.

## 2. Les trois listes embarquées

| Liste | Source | Contenu | Rôle |
|---|---|---|---|
| Officielle, signataires | `c2pa-org/conformance-public`, `trust-list/C2PA-TRUST-LIST.pem` | 33 certificats | signataires de manifestes |
| Officielle, horodatage | même dépôt, `C2PA-TSA-TRUST-LIST.pem` | 24 certificats | autorités d'horodatage |
| Interim | `contentauth/verify-site`, `static/trust/anchors.pem` | 26 certificats distincts | signataires et horodatage |

- Les deux listes officielles sont sous CC-BY-4.0 et mises à jour toutes les une à trois semaines.
- La liste interim est gelée. Son fichier ne porte aucune mention de licence ; son dépôt se dit sous Apache-2.0 dans son README et « UNLICENSED » dans son `package.json`.
- Les trois fichiers sont des copies exactes, vérifiées par empreinte SHA-256 contre l'amont.
- Elles ne sont jamais téléchargées : ni à la compilation, ni à l'exécution. `scripts/update_trust_list.sh` les rafraîchit à la main avant une version.
- Un lot fourni par l'appelant (`--anchors`, `trust_anchors_pem`) remplace les trois listes et sert pour les signataires comme pour l'horodatage.

## 3. Ce que chaque liste a débloqué

Essais sans aucune option, sur de vrais fichiers publics.

| Fichier | Officielle seule | + horodatage | + interim |
|---|---|---|---|
| Photo Google Pixel | valide, pas de confiance | **de confiance** | de confiance |
| Adobe Firefly | `ai-signal` | `ai-signal` | **`ai-proven`** |
| OpenAI Sora | invalide | invalide | **`ai-proven`** |
| Adobe Express (PDF) | `ai-signal` | `ai-signal` | **`ai-proven`** |
| Image et PDF ChatGPT du corpus de l'auteur | **`ai-proven`** | `ai-proven` | `ai-proven` |
| Deux images ChatGPT des dépôts d'exemples | invalide | invalide | invalide (certificat expiré, pas d'horodatage) |

Constats :

- **Avec la liste officielle des signataires seule, aucun des 9 fichiers d'exemple n'était de confiance.** Pour les manifestes de version 2, `c2pa-rs` exige que l'horodatage soit rattaché à une ancre de type « tsa ».
- La liste interim n'a aucun certificat en commun avec la liste officielle. Les fichiers Firefly, Photoshop et Sora existants en dépendent.
- OpenAI signe maintenant sous la liste officielle : les fichiers ChatGPT récents n'ont pas besoin de la liste interim.
- La photo Pixel reste en `no-signal` : la mention « capture » n'est déclarée que par un ingrédient, et isitai plafonne ce qui vient d'un ingrédient (voir §5).

Le détail de chaque preuve dit sur quelle liste elle repose : « signer in the interim trust list » ou « in the official C2PA trust list ».

## 4. Essais adverses

Aucun faux `ai-proven` ni faux `capture-proven` n'a été reproduit avec les listes par défaut. Ont été essayés :

- 13 fichiers signés avec le certificat de test de `c2pa-rs` ;
- des autorités fabriquées, une feuille auto-signée, des imitations de racines réelles (Google, Adobe, Sony) avec le même nom et une autre clé ;
- un octet modifié, un manifeste greffé sur une autre image, 6 272 mutations aléatoires sur 15 fichiers signés ;
- un horodatage public réel ajouté à un signataire inconnu.

La CLI donne les mêmes résultats dans un bac à sable sans réseau.

## 5. Règles de verdict issues de ces essais

- Une preuve signée n'est pas annulée par une métadonnée non signée contraire.
- « Capture puis retouche IA » compte comme contenu IA, pas comme contradiction.
- Un type de source trouvé seulement dans un ingrédient, ou dans un autre manifeste du fichier, vaut au plus un signal fort. Il bloque aussi `capture-proven`. Trois chemins vers un faux `capture-proven` avaient été trouvés avant cette règle.
- Un manifeste invalide produit un avertissement, et son générateur n'est pas rapporté.

## 6. Risques acceptés

| Risque | Détail |
|---|---|
| Révocation non vérifiée | isitai ne contacte aucune autorité. D'après la presse, Nikon a révoqué ses certificats C2PA en 2025 après une faille ; sa racine est dans la liste interim. Non testé sur un vrai fichier. |
| Clé de signature volée | Pour les manifestes de version 1, `c2pa-rs` ne vérifie pas l'autorité d'horodatage : l'expiration d'un certificat ne borne pas une clé volée. Reproduit avec un lot fourni par l'appelant. |
| Signataires hors production | Des certificats de test d'Adobe (« Stage ») sont rattachés à la liste interim. |
| Racines généralistes | La liste interim contient des racines Microsoft, Samsung et Pinterest qui ne sont pas réservées au C2PA. Ce qu'elles émettent d'autre n'a pas été établi. |
| Listes officielles peu séparées | 17 racines figurent à la fois dans la liste des signataires et dans celle des horodatages. |
| Licence de la liste interim | Non clarifiée par l'amont. |

Pour revenir aux listes officielles seules, il suffit de passer leurs deux fichiers réunis avec `--anchors`.

## 7. Limites des essais

- Environ dix fichiers signés par de vrais produits ; aucun fichier d'appareil Leica, Nikon, Sony ou Canon.
- Aucun `capture-proven` observé sur un vrai fichier.
- Le libellé de la liste dans le détail d'une preuve dépend du texte d'explication de `c2pa` 0.92.0 ; un changement de formulation en amont le ferait disparaître sans erreur.
