# Corpus de textes générés

948 textes produits par des modèles de plusieurs éditeurs, dans sept langues
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
| en | 232 | 24.5 % |
| fr | 167 | 17.6 % |
| es | 145 | 15.3 % |
| pt | 131 | 13.8 % |
| zh | 121 | 12.8 % |
| ar | 92 | 9.7 % |
| it | 60 | 6.3 % |

## Éditeurs

| Éditeur | Textes |
|---|---|
| Zhipu AI | 146 |
| DeepSeek | 126 |
| Anthropic | 99 |
| Meituan | 91 |
| Alibaba | 75 |
| Iceman | 68 |
| Xiaomi | 68 |
| Muse | 59 |
| MiniMax | 50 |
| Google | 45 |
| OpenAI | 43 |
| Moonshot | 33 |
| xAI | 20 |
| StepFun | 18 |
| Tencent | 7 |

## Modèles

| Modèle | Textes |
|---|---|
| `deepseek-v4.1-flash` | 105 |
| `claude-haiku-5-5` | 99 |
| `glm-5.3-flash` | 96 |
| `iceman-contributor-free` | 68 |
| `muse-spark-1.3-contributor` | 59 |
| `qwen3.8-flash` | 52 |
| `longcat-2.0` | 50 |
| `mimo-v2.6-flash` | 47 |
| `minimax-m3.1-flash` | 46 |
| `gemini-4-argon` | 45 |
| `longcat-2.5-free` | 41 |
| `glm-5.2` | 35 |
| `gpt-5.6-luna` | 23 |
| `qwen3.8-max` | 23 |
| `deepseek-v4-pro` | 21 |
| `mimo-v2.6-pro` | 21 |
| `gpt-6-luna` | 20 |
| `grok-4.7` | 20 |
| `kimi-k3` | 19 |
| `step-5-preview` | 18 |
| `glm-5.3` | 15 |
| `kimi-k3.1-pro` | 14 |
| `hy4` | 7 |
| `minimax-m3` | 4 |

## Domaines

| Domaine | Textes |
|---|---|
| reviews | 101 |
| news | 100 |
| reddit | 98 |
| social | 97 |
| essay | 95 |
| recipes | 94 |
| books | 93 |
| email | 93 |
| wiki | 91 |
| abstracts | 86 |

## Longueurs

Comptées en caractères pour le chinois, mots ailleurs.

| Longueur | Textes | Bornes |
|---|---|---|
| moyen | 326 | 150-300 |
| court | 322 | 30-80 |
| long | 300 | 500-900 |

## Couverture des sujets

Nombre de sujets distincts par couple (langue, domaine) :

| Sujets distincts | Couples concernés |
|---|---|
| 10 | 26 |
| 9 | 7 |
| 8 | 7 |
| 6 | 9 |
| 5 | 6 |
| 4 | 12 |
| 3 | 3 |

Les langues à petit volume ne peuvent pas couvrir dix sujets par domaine :
37 textes italiens pour dix domaines donnent mécaniquement trois à quatre sujets.
Ce n'est pas une lacune du générateur mais une contrainte d'échelle, à connaître
avant de comparer des taux entre langues.

## Ce que ce corpus ne permet pas de dire

- Aucun taux de faux positifs : il ne contient pas de texte humain.
- Aucune comparaison entre modèles : le nombre de textes par modèle n'est pas
  équilibré, il suit une pondération par coût mesuré.
- Aucune généralisation à un domaine absent de la liste.

Coût total de production : 8.0988 allowance.

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
