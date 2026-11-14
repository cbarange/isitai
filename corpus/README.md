# Corpus de textes générés

705 textes produits par des modèles de plusieurs éditeurs, dans sept langues
et dix domaines. Ce corpus sert de matériau **positif** : il ne contient que du
texte machine, et ne permet donc à lui seul aucun calcul de faux positifs.

## Provenance

Chaque texte est consigné dans `manifest.jsonl` : identifiant, fichier, modèle,
éditeur, langue, domaine, longueur cible, longueur réelle, sujet, prompt exact,
température, date et coût en allowance. Le prompt est conservé parce qu'un texte
sans sa consigne n'est pas reproductible.

## Langues

| Langue | Textes | Part |
|---|---|---|
| fr | 222 | 31.5 % |
| en | 152 | 21.6 % |
| es | 106 | 15.0 % |
| pt | 83 | 11.8 % |
| zh | 60 | 8.5 % |
| ar | 45 | 6.4 % |
| it | 37 | 5.2 % |

## Éditeurs

| Éditeur | Textes |
|---|---|
| Zhipu AI | 95 |
| Meituan | 84 |
| DeepSeek | 81 |
| Anthropic | 58 |
| Iceman | 51 |
| Xiaomi | 51 |
| Alibaba | 48 |
| Muse | 46 |
| Google | 39 |
| OpenAI | 36 |
| MiniMax | 36 |
| Moonshot | 33 |
| xAI | 21 |
| StepFun | 18 |
| Tencent | 8 |

## Modèles

| Modèle | Textes |
|---|---|
| `deepseek-v4.1-flash` | 59 |
| `claude-haiku-5-5` | 58 |
| `glm-5.3-flash` | 52 |
| `iceman-contributor-free` | 51 |
| `longcat-2.5-free` | 46 |
| `muse-spark-1.3-contributor` | 46 |
| `gemini-4-argon` | 39 |
| `longcat-2.0` | 38 |
| `qwen3.8-flash` | 33 |
| `minimax-m3.1-flash` | 33 |
| `mimo-v2.6-flash` | 32 |
| `glm-5.2` | 29 |
| `deepseek-v4-pro` | 22 |
| `grok-4.7` | 21 |
| `gpt-5.6-luna` | 21 |
| `kimi-k3` | 19 |
| `mimo-v2.6-pro` | 19 |
| `step-5-preview` | 18 |
| `qwen3.8-max` | 15 |
| `gpt-6-luna` | 15 |
| `glm-5.3` | 14 |
| `kimi-k3.1-pro` | 14 |
| `hy4` | 8 |
| `minimax-m3` | 3 |

## Domaines

| Domaine | Textes |
|---|---|
| books | 93 |
| email | 88 |
| abstracts | 87 |
| news | 86 |
| essay | 83 |
| recipes | 80 |
| reddit | 60 |
| reviews | 51 |
| social | 44 |
| wiki | 33 |

## Textes réaffectés

Des textes produits dans un emplacement d'une langue ont été écrits dans une
autre : le gabarit du prompt était rédigé en français pour toutes les langues,
et il tirait la sortie vers le français. Ces textes sont conservés, reclassés
dans leur vraie langue, et leur nom porte le suffixe `_reassignee`. Le champ
`langue_demandee` du manifeste garde la langue qui avait été demandée.

| Demandée | Réelle | Textes |
|---|---|---|
| en | fr | 65 |
| es | fr | 16 |
| pt | fr | 8 |
| zh | fr | 7 |
| it | fr | 4 |
| ar | fr | 2 |
| fr | en | 1 |
| pt | en | 1 |
| it | es | 1 |

Les emplacements libérés ont été régénérés dans la langue demandée :
le total dépasse donc le nombre d'emplacements prévus.

## Longueurs

Comptées en caractères pour le chinois, mots ailleurs.

| Longueur | Textes | Bornes |
|---|---|---|
| court | 299 | 30-80 |
| long | 212 | 500-900 |
| moyen | 194 | 150-300 |

## Couverture des sujets

Nombre de sujets distincts par couple (langue, domaine) :

| Sujets distincts | Couples concernés |
|---|---|
| 25 | 1 |
| 18 | 3 |
| 16 | 1 |
| 15 | 1 |
| 14 | 2 |
| 13 | 1 |
| 12 | 1 |
| 9 | 6 |
| 8 | 13 |
| 7 | 5 |
| 6 | 2 |
| 5 | 7 |
| 4 | 9 |
| 3 | 3 |
| 2 | 1 |
| 1 | 1 |

Les langues à petit volume ne peuvent pas couvrir dix sujets par domaine :
37 textes italiens pour dix domaines donnent mécaniquement trois à quatre sujets.
Ce n'est pas une lacune du générateur mais une contrainte d'échelle, à connaître
avant de comparer des taux entre langues.

## Ce que ce corpus ne permet pas de dire

- Aucun taux de faux positifs : il ne contient pas de texte humain.
- Aucune comparaison entre modèles : le nombre de textes par modèle n'est pas
  équilibré, il suit une pondération par coût mesuré.
- Aucune généralisation à un domaine absent de la liste.

Coût total de production : 6.7822 allowance.

## Échecs de génération

| Raison | Occurrences |
|---|---|
| hors longueur | 52 |
| sortie vide | 38 |
| HTTP 429 | 26 |
| HTTP 400 | 8 |
| HTTP 500 | 4 |
| HTTP 400 au rappel de longueur | 1 |

Les identifiants en échec ne sont pas écrits : relancer le générateur
les retente seuls, les textes déjà présents étant sautés.
