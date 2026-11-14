# Corpus de textes générés

600 textes produits par des modèles de plusieurs éditeurs, dans sept langues
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
| en | 150 | 25.0 % |
| fr | 120 | 20.0 % |
| es | 105 | 17.5 % |
| pt | 83 | 13.8 % |
| zh | 60 | 10.0 % |
| ar | 45 | 7.5 % |
| it | 37 | 6.2 % |

## Éditeurs

| Éditeur | Textes |
|---|---|
| Zhipu AI | 83 |
| DeepSeek | 71 |
| Meituan | 64 |
| Anthropic | 49 |
| Xiaomi | 46 |
| Iceman | 42 |
| Muse | 42 |
| Alibaba | 42 |
| Google | 32 |
| OpenAI | 32 |
| MiniMax | 31 |
| Moonshot | 28 |
| xAI | 18 |
| StepFun | 14 |
| Tencent | 6 |

## Modèles

| Modèle | Textes |
|---|---|
| `deepseek-v4.1-flash` | 53 |
| `claude-haiku-5-5` | 49 |
| `glm-5.3-flash` | 47 |
| `iceman-contributor-free` | 42 |
| `muse-spark-1.3-contributor` | 42 |
| `gemini-4-argon` | 32 |
| `longcat-2.0` | 32 |
| `longcat-2.5-free` | 32 |
| `qwen3.8-flash` | 29 |
| `mimo-v2.6-flash` | 29 |
| `minimax-m3.1-flash` | 29 |
| `glm-5.2` | 25 |
| `deepseek-v4-pro` | 18 |
| `gpt-5.6-luna` | 18 |
| `grok-4.7` | 18 |
| `mimo-v2.6-pro` | 17 |
| `kimi-k3` | 16 |
| `gpt-6-luna` | 14 |
| `step-5-preview` | 14 |
| `qwen3.8-max` | 13 |
| `kimi-k3.1-pro` | 12 |
| `glm-5.3` | 11 |
| `hy4` | 6 |
| `minimax-m3` | 2 |

## Domaines

| Domaine | Textes |
|---|---|
| email | 76 |
| essay | 76 |
| books | 74 |
| news | 74 |
| abstracts | 73 |
| recipes | 66 |
| reddit | 56 |
| reviews | 46 |
| social | 37 |
| wiki | 22 |

## Longueurs

Comptées en caractères pour le chinois, mots ailleurs.

| Longueur | Textes | Bornes |
|---|---|---|
| court | 256 | 30-80 |
| long | 184 | 500-900 |
| moyen | 160 | 150-300 |

## Couverture des sujets

Nombre de sujets distincts par couple (langue, domaine) :

| Sujets distincts | Couples concernés |
|---|---|
| 9 | 11 |
| 8 | 13 |
| 7 | 11 |
| 6 | 1 |
| 5 | 8 |
| 4 | 8 |
| 3 | 2 |
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

Coût total de production : 5.9907 allowance.

## Échecs de génération

| Raison | Occurrences |
|---|---|
| hors longueur | 46 |
| sortie vide | 37 |
| HTTP 429 | 26 |
| HTTP 400 | 8 |
| HTTP 500 | 4 |

Les identifiants en échec ne sont pas écrits : relancer le générateur
les retente seuls, les textes déjà présents étant sautés.
