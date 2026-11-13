#!/usr/bin/env python3
"""Génère le corpus de textes IA du benchmark `isitai`.

Reprenable : un fichier déjà présent n'est jamais regénéré. Chaque texte est écrit
puis consigné dans `corpus/manifest.jsonl` avant de passer au suivant, donc une
interruption ne perd rien.

    python3 corpus/tools/generate.py --list-models
    python3 corpus/tools/generate.py --dry-run --lang fr --limit 20
    python3 corpus/tools/generate.py --lang en --limit 50 --max-allowance 0.20

Garde-fous, dans l'ordre où ils s'appliquent :

1. **Quota** : lit `/usage` avant chaque lot et s'arrête si le mois dépasse
   `--quota-ceiling` (défaut 85 %). Un corpus qui vide l'abonnement n'est pas un corpus.
2. **Budget** : additionne `usage.opencode.allowance` et s'arrête à `--max-allowance`.
3. **Sortie vide** : certains modèles raisonnants consomment tout `max_tokens` en
   raisonnement et rendent une chaîne vide. On relance une fois avec le double, puis on
   abandonne et on consigne l'échec — un fichier vide serait un faux négatif du corpus.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus"
MANIFEST = CORPUS / "manifest.jsonl"
BASE = "https://opencode.ai/zen/go/v1"

# ------------------------------------------------------------------ modèles

# Éditeur déduit du préfixe : le manifeste doit nommer l'éditeur, pas seulement le modèle.
PUBLISHERS = {
    "deepseek": "DeepSeek", "glm": "Zhipu AI", "grok": "xAI", "gpt": "OpenAI",
    "claude": "Anthropic", "kimi": "Moonshot", "mimo": "Xiaomi", "minimax": "MiniMax",
    "longcat": "Meituan", "qwen": "Alibaba", "step": "StepFun", "gemini": "Google",
    "hy": "Tencent", "muse": "Muse", "iceman": "Iceman", "beam": "Beam",
}

# Modèles retenus pour la diversité d'éditeurs. Les « contributor » et « free » coûtent
# une fraction des gros modèles : ils servent à couvrir du volume sans vider le quota.
MODELS = [
    "deepseek-v4-pro", "deepseek-v4.1-flash",
    "glm-5.3", "glm-5.3-flash", "glm-5.2",
    "qwen3.8-max", "qwen3.8-flash",
    "kimi-k3.1-pro", "kimi-k3",
    "minimax-m3.1-flash", "minimax-m3",
    "mimo-v2.6-pro", "mimo-v2.6-flash",
    "longcat-2.0", "longcat-2.5-free",
    "grok-4.7",
    "gpt-6-luna", "gpt-5.6-luna",
    "claude-haiku-5-5",
    "gemini-4-argon",
    "hy4", "step-5-preview",
    "iceman-contributor-free", "muse-spark-1.3-contributor",
]

# Pondération par coût mesuré (allowance par texte moyen, voir le manifeste) : les modèles
# bon marché portent le volume, les chers apportent la diversité d'éditeurs sans ruiner le
# quota. Un poids de 4 signifie quatre fois plus de textes.
WEIGHTS = {
    # Mesuré sur un texte « moyen » : glm-5.3-flash 8 s / 0,00023 · claude-haiku 5 s / 0,0017
    # · gemini 10 s / 0,0092 · deepseek-flash 17 s / 0,00044 · kimi-k3 31 s / 0,1021.
    # Le volume va aux modèles rapides et bon marché ; les chers restent pour la diversité.
    "glm-5.3-flash": 6, "claude-haiku-5-5": 4, "deepseek-v4.1-flash": 4,
    "longcat-2.5-free": 3, "iceman-contributor-free": 3, "muse-spark-1.3-contributor": 3,
    "qwen3.8-flash": 2, "longcat-2.0": 2, "glm-5.2": 2, "minimax-m3.1-flash": 2,
    "mimo-v2.6-flash": 2, "gemini-4-argon": 2,
    "qwen3.8-max": 1, "glm-5.3": 1, "hy4": 1, "step-5-preview": 1,
    "minimax-m3": 1, "mimo-v2.6-pro": 1, "gpt-5.6-luna": 1, "gpt-6-luna": 1,
    "grok-4.7": 1, "kimi-k3": 1, "kimi-k3.1-pro": 1, "deepseek-v4-pro": 1,
}

LANGS = ["en", "fr", "es", "pt", "zh", "ar", "it"]
# Proportions de la demande initiale (1 000 / 800 / 700 / 550 / 400 / 300 / 250 sur 4 000),
# mises à l'échelle de 600 textes. Total : 600 exactement.
TARGETS = {"en": 150, "fr": 120, "es": 105, "pt": 83, "zh": 60, "ar": 45, "it": 37}

LENGTHS = {"court": (30, 80), "moyen": (150, 300), "long": (500, 900), "tres-long": (1500, 3000)}
VERY_LONG_DOMAINS = {"essay", "news", "wiki", "abstracts", "books"}

# Longueurs autorisées par domaine. Un « post social » de 900 mots n'existe pas : le
# produire créerait une classe qui n'a pas de contrepartie humaine.
DOMAIN_LENGTHS = {
    "news": ["court", "moyen", "long"],
    "wiki": ["moyen", "long"],
    "abstracts": ["court", "moyen"],
    "reviews": ["court", "moyen"],
    "reddit": ["court", "moyen"],
    "recipes": ["court", "moyen", "long"],
    "books": ["moyen", "long"],
    "social": ["court"],
    "email": ["court", "moyen"],
    "essay": ["moyen", "long"],
}

DOMAINS = ["news", "wiki", "abstracts", "reviews", "reddit", "recipes", "books", "social", "email", "essay"]

# Consigne de style par domaine et par langue. Écrite dans la langue cible : une consigne
# anglaise fait écrire dans un anglais traduit, ce qui biaise le corpus.
STYLE = {
    "fr": {
        "news": "Rédige un article de presse d'actualité, ton factuel de journal national, sans titre ni préambule.",
        "wiki": "Rédige un article encyclopédique, ton neutre et sourcé, sans titre, en paragraphes continus.",
        "abstracts": "Rédige le résumé structuré d'un article scientifique (contexte, méthode, résultats, conclusion), sans titre.",
        "reviews": "Rédige un avis client sincère sur un produit, ton personnel, comme publié sur un site marchand.",
        "reddit": "Rédige un message de forum, ton familier, avec une question ou une anecdote personnelle.",
        "recipes": "Rédige une recette de cuisine complète avec ingrédients et étapes, sans titre.",
        "books": "Rédige un passage narratif original, style littéraire, sans jamais reprendre une œuvre existante.",
        "social": "Rédige une publication courte de réseau social, ton spontané, éventuellement avec des emojis.",
        "email": "Rédige un courriel professionnel, formule d'usage et objet implicite dans le corps, sans signature.",
        "essay": "Rédige une dissertation d'étudiant argumentée, avec introduction, développement et conclusion.",
    },
    "en": {
        "news": "Write a news article in factual national-newspaper style, no headline, no preamble.",
        "wiki": "Write an encyclopedic article in neutral, sourced tone, no title, continuous paragraphs.",
        "abstracts": "Write a structured scientific abstract (background, methods, results, conclusion), no title.",
        "reviews": "Write a sincere customer review of a product, personal tone, as posted on a store.",
        "reddit": "Write a forum post, casual tone, with a personal anecdote or a question.",
        "recipes": "Write a complete recipe with ingredients and steps, no title.",
        "books": "Write an original narrative passage in literary style, never reproducing an existing work.",
        "social": "Write a short social media post, spontaneous tone, emojis allowed.",
        "email": "Write a professional email, standard register, no signature block.",
        "essay": "Write an argued student essay with introduction, body and conclusion.",
    },
    "es": {
        "news": "Redacta un artículo de prensa de actualidad, tono factual de periódico nacional, sin titular ni preámbulo.",
        "wiki": "Redacta un artículo enciclopédico, tono neutro y documentado, sin título, en párrafos continuos.",
        "abstracts": "Redacta el resumen estructurado de un artículo científico (contexto, método, resultados, conclusión), sin título.",
        "reviews": "Redacta una opinión sincera de cliente sobre un producto, tono personal, como en una tienda online.",
        "reddit": "Redacta un mensaje de foro, tono informal, con una anécdota personal o una pregunta.",
        "recipes": "Redacta una receta de cocina completa con ingredientes y pasos, sin título.",
        "books": "Redacta un pasaje narrativo original, estilo literario, sin reproducir ninguna obra existente.",
        "social": "Redacta una publicación corta de red social, tono espontáneo, emojis permitidos.",
        "email": "Redacta un correo profesional, registro estándar, sin bloque de firma.",
        "essay": "Redacta un ensayo académico argumentado con introducción, desarrollo y conclusión.",
    },
    "pt": {
        "news": "Escreve uma notícia de atualidade, tom factual de jornal nacional, sem título nem preâmbulo.",
        "wiki": "Escreve um artigo enciclopédico, tom neutro e documentado, sem título, em parágrafos contínuos.",
        "abstracts": "Escreve o resumo estruturado de um artigo científico (contexto, método, resultados, conclusão), sem título.",
        "reviews": "Escreve uma avaliação sincera de cliente sobre um produto, tom pessoal, como numa loja online.",
        "reddit": "Escreve uma mensagem de fórum, tom informal, com uma anedota pessoal ou uma pergunta.",
        "recipes": "Escreve uma receita de cozinha completa com ingredientes e passos, sem título.",
        "books": "Escreve uma passagem narrativa original, estilo literário, sem reproduzir nenhuma obra existente.",
        "social": "Escreve uma publicação curta de rede social, tom espontâneo, emojis permitidos.",
        "email": "Escreve um e-mail profissional, registo padrão, sem bloco de assinatura.",
        "essay": "Escreve uma dissertação académica argumentada com introdução, desenvolvimento e conclusão.",
    },
    "it": {
        "news": "Scrivi un articolo di cronaca, tono fattuale da quotidiano nazionale, senza titolo né preambolo.",
        "wiki": "Scrivi una voce enciclopedica, tono neutro e documentato, senza titolo, in paragrafi continui.",
        "abstracts": "Scrivi l'abstract strutturato di un articolo scientifico (contesto, metodo, risultati, conclusione), senza titolo.",
        "reviews": "Scrivi una recensione sincera di un prodotto, tono personale, come su un negozio online.",
        "reddit": "Scrivi un messaggio di forum, tono informale, con un aneddoto personale o una domanda.",
        "recipes": "Scrivi una ricetta completa con ingredienti e passaggi, senza titolo.",
        "books": "Scrivi un brano narrativo originale, stile letterario, senza riprodurre opere esistenti.",
        "social": "Scrivi un post breve sui social, tono spontaneo, emoji ammesse.",
        "email": "Scrivi un'email professionale, registro standard, senza blocco firma.",
        "essay": "Scrivi un tema argomentato con introduzione, sviluppo e conclusione.",
    },
    "zh": {
        "news": "写一篇新闻报道，采用全国性报纸的客观语气，不要标题，不要开场白。",
        "wiki": "写一篇百科条目，语气中立、有依据，不要标题，连续段落。",
        "abstracts": "写一篇科学论文的结构化摘要（背景、方法、结果、结论），不要标题。",
        "reviews": "写一条真实的商品用户评价，语气个人化，就像发布在电商网站上。",
        "reddit": "写一条论坛帖子，语气随意，包含个人经历或一个问题。",
        "recipes": "写一份完整的菜谱，包含食材和步骤，不要标题。",
        "books": "写一段原创叙事文字，文学风格，不得复制任何已有作品。",
        "social": "写一条简短的社交媒体帖子，语气自然，可以使用表情符号。",
        "email": "写一封专业电子邮件，标准语体，不要签名区。",
        "essay": "写一篇有论点的学生作文，包含引言、正文和结论。",
    },
    "ar": {
        "news": "اكتب مقالاً إخبارياً بأسلوب صحيفة وطنية، دون عنوان ودون مقدمة.",
        "wiki": "اكتب مقالة موسوعية بنبرة محايدة وموثقة، دون عنوان، في فقرات متصلة.",
        "abstracts": "اكتب ملخصاً منَظَّماً لبحث علمي (السياق، المنهج، النتائج، الخاتمة)، دون عنوان.",
        "reviews": "اكتب تقييماً صادقاً لمنتج، بنبرة شخصية، كما يُنشر على موقع تسوق.",
        "reddit": "اكتب رسالة في منتدى، بأسلوب غير رسمي، مع قصة شخصية أو سؤال.",
        "recipes": "اكتب وصفة طبخ كاملة مع المكونات والخطوات، دون عنوان.",
        "books": "اكتب مقطعاً سردياً أصلياً بأسلوب أدبي، دون نسخ أي عمل موجود.",
        "social": "اكتب منشوراً قصيراً على شبكة اجتماعية، بنبرة عفوية، مع إمكانية الرموز التعبيرية.",
        "email": "اكتب بريداً إلكترونياً مهنياً، بأسلوب رسمي معتاد، دون توقيع.",
        "essay": "اكتب مقالاً مدرسياً مُحتَجّاً به، بمقدمة وعرض وخاتمة.",
    },
}

# Sujets : dix par domaine et par langue. Les domaines news et wiki utilisent des sujets
# réels et datés pour rester comparables aux corpus humains.
SUBJECTS = {
    "fr": {
        "news": ["réforme des retraites", "ouverture d'une ligne de train de nuit Paris-Berlin", "sécheresse dans le Sud-Est", "grève des transports lyonnais", "baisse des taux immobiliers", "cyberattaque contre un hôpital", "vote du budget à l'Assemblée", "records de chaleur en octobre", "fusion de deux groupes bancaires", "ouverture d'un data center en Bretagne"],
        "wiki": ["le phare de Cordouan", "la tectonique des plaques", "l'histoire du papier", "le système immunitaire", "la fermentation du pain", "le canal du Midi", "les marées", "la photographie argentique", "la soie lyonnaise", "les volcans d'Auvergne"],
        "abstracts": ["effet du sommeil sur la consolidation mnésique", "prédiction de la consommation électrique par apprentissage automatique", "biodiversité des sols agricoles", "diagnostic précoce par imagerie médicale", "résistance aux antibiotiques chez les bactéries Gram négatif", "impact du télétravail sur la mobilité urbaine", "corrosion des aciers en milieu marin", "modélisation climatique régionale", "apprentissage de la lecture chez l'enfant", "qualité de l'air intérieur dans les écoles"],
        "reviews": ["un robot pâtissier haut de gamme", "une paire de chaussures de randonnée", "un abonnement de streaming sportif", "un matelas à ressorts", "une banque en ligne", "un vélo électrique urbain", "un casque audio à réduction de bruit", "une imprimante laser", "un service de livraison de repas", "une tondeuse à gazon robotisée"],
        "reddit": ["changer de carrière à 40 ans", "le meilleur moyen d'apprendre une langue seul", "mon premier appartement et mes voisins", "investir un petit héritage", "réparer soi-même son lave-linge", "partir vivre à l'étranger sans diplôme", "gérer un manager incompétent", "choisir un chien en appartement", "mon pire entretien d'embauche", "se lancer en freelance"],
        "recipes": ["tarte aux pommes et au romarin", "blanquette de veau traditionnelle", "soupe de courge butternut au lait de coco", "pain au levain sans machine", "risotto aux cèpes", "gratin dauphinois", "poulet rôti aux herbes", "salade de lentilles et chèvre chaud", "tarte au citron meringuée", "ratatouille niçoise"],
        "books": ["un gardien de phare découvre une lettre dans une bouteille", "deux sœurs se retrouvent après vingt ans", "un village entier perd la mémoire une nuit", "un horloger répare une montre qui n'existe pas", "une dernière conversation dans une gare vide", "un enfant apprend que sa maison va être détruite", "un médecin de campagne pendant une tempête", "un libraire reçoit un manuscrit anonyme", "une traversée de l'Atlantique à la voile en solitaire", "un immeuble se réveille sans électricité"],
        "social": ["annoncer une reconversion professionnelle", "partager une photo de randonnée en montagne", "réagir à une actualité sportive", "poser une question sur l'achat d'un vélo", "raconter un petit succès du quotidien", "demander des conseils pour déménager", "annoncer la naissance d'un enfant", "critiquer une décision municipale", "partager une recette maison", "chercher un colocataire"],
        "email": ["relancer un client sur une facture impayée", "proposer une réunion de cadrage à une équipe", "annoncer un changement de prestataire à un partenaire", "demander un congé à son responsable", "refuser une proposition commerciale poliment", "confirmer un entretien d'embauche", "signaler un incident technique à un fournisseur", "féliciter une collègue promue", "demander des précisions sur un contrat", "organiser un déplacement professionnel"],
        "essay": ["la place du travail dans nos vies", "faut-il encadrer l'usage de l'IA à l'école", "les réseaux sociaux rendent-ils plus seuls", "le rôle de l'art dans la société", "faut-il habiter en ville ou à la campagne", "la protection de l'environnement est-elle une contrainte", "l'argent fait-il le bonheur", "le sport est-il un vecteur d'intégration", "faut-il rendre le vote obligatoire", "la lecture de fiction a-t-elle une utilité sociale"],
    },
    "en": {
        "news": ["pension reform protests", "new night train between Paris and Berlin", "drought in southern Europe", "bank merger announcement", "fall in mortgage rates", "cyberattack on a hospital network", "budget vote in parliament", "record October temperatures", "opening of a data centre", "crisis in the shipping industry"],
        "wiki": ["the lighthouse of Cordouan", "plate tectonics", "the history of paper", "the immune system", "bread fermentation", "the Suez Canal", "tides", "the history of photography", "silkworm farming", "volcanism in Iceland"],
        "abstracts": ["sleep and memory consolidation", "electricity demand forecasting with machine learning", "biodiversity in agricultural soils", "early diagnosis through medical imaging", "antibiotic resistance in Gram-negative bacteria", "remote work and urban mobility", "corrosion of steel in marine environments", "regional climate modelling", "reading acquisition in children", "indoor air quality in schools"],
        "reviews": ["a premium stand mixer", "hiking boots", "a sports streaming subscription", "a spring mattress", "an online bank", "a city e-bike", "noise-cancelling headphones", "a laser printer", "a food delivery service", "a robot lawn mower"],
        "reddit": ["changing careers at 40", "best way to learn a language alone", "my first apartment and my neighbours", "investing a small inheritance", "fixing my own washing machine", "moving abroad without a degree", "dealing with an incompetent manager", "choosing a dog for an apartment", "my worst job interview", "going freelance"],
        "recipes": ["apple and rosemary tart", "traditional beef stew", "butternut squash and coconut soup", "sourdough bread without a machine", "mushroom risotto", "potato gratin", "roast chicken with herbs", "lentil salad with warm goat cheese", "lemon meringue pie", "vegetable ratatouille"],
        "books": ["a lighthouse keeper finds a letter in a bottle", "two sisters meet again after twenty years", "an entire village loses its memory overnight", "a watchmaker repairs a watch that does not exist", "a last conversation in an empty station", "a child learns the house will be demolished", "a country doctor during a storm", "a bookseller receives an anonymous manuscript", "a solo Atlantic crossing", "a building wakes up without electricity"],
        "social": ["announcing a career change", "sharing a mountain hiking photo", "reacting to a sports result", "asking for advice on buying a bike", "sharing a small daily win", "asking for moving tips", "announcing a birth", "criticising a council decision", "sharing a homemade recipe", "looking for a flatmate"],
        "email": ["chasing an unpaid invoice", "proposing a kick-off meeting", "informing a partner about a provider change", "requesting leave from a manager", "politely declining a sales offer", "confirming a job interview", "reporting a technical incident to a supplier", "congratulating a promoted colleague", "asking for contract clarification", "organising a business trip"],
        "essay": ["the place of work in our lives", "should AI be regulated in schools", "do social networks make us lonelier", "the role of art in society", "city or countryside living", "is environmental protection a constraint", "does money buy happiness", "is sport a vector of integration", "should voting be compulsory", "does reading fiction have social value"],
    },
}

# Les cinq autres langues reprennent les sujets anglais, traduits : un sujet identique
# d'une langue à l'autre est ce qui rend les textes comparables entre eux.
SUBJECTS_TRANSLATED = {
    "es": {
        "news": ["reforma de las pensiones", "nuevo tren nocturno París-Berlín", "sequía en el sur de Europa", "fusión bancaria", "bajada de los tipos hipotecarios", "ciberataque a un hospital", "votación del presupuesto", "récords de temperatura en octubre", "apertura de un centro de datos", "crisis del transporte marítimo"],
        "wiki": ["el faro de Cordouan", "la tectónica de placas", "la historia del papel", "el sistema inmunitario", "la fermentación del pan", "el canal de Suez", "las mareas", "la historia de la fotografía", "la sericicultura", "el vulcanismo en Islandia"],
        "abstracts": ["el sueño y la consolidación de la memoria", "previsión de la demanda eléctrica con aprendizaje automático", "biodiversidad de los suelos agrícolas", "diagnóstico precoz por imagen médica", "resistencia a los antibióticos en bacterias Gram negativas", "teletrabajo y movilidad urbana", "corrosión del acero en medio marino", "modelización climática regional", "aprendizaje de la lectura en la infancia", "calidad del aire interior en las escuelas"],
        "reviews": ["una amasadora de gama alta", "botas de montaña", "una suscripción deportiva", "un colchón de muelles", "un banco en línea", "una bici eléctrica urbana", "auriculares con cancelación de ruido", "una impresora láser", "un servicio de reparto de comida", "un robot cortacésped"],
        "reddit": ["cambiar de carrera a los 40", "aprender un idioma solo", "mi primer piso y mis vecinos", "invertir una pequeña herencia", "reparar mi lavadora", "emigrar sin título", "lidiar con un jefe incompetente", "elegir un perro para un piso", "mi peor entrevista de trabajo", "trabajar por cuenta propia"],
        "recipes": ["tarta de manzana y romero", "estofado de ternera tradicional", "sopa de calabaza y coco", "pan de masa madre sin máquina", "risotto de setas", "gratén de patatas", "pollo asado con hierbas", "ensalada de lentejas con queso de cabra", "tarta de limón merengada", "pisto de verduras"],
        "books": ["un farero encuentra una carta en una botella", "dos hermanas se reencuentran tras veinte años", "un pueblo entero pierde la memoria en una noche", "un relojero repara un reloj que no existe", "una última conversación en una estación vacía", "un niño descubre que derribarán su casa", "un médico rural durante una tormenta", "un librero recibe un manuscrito anónimo", "una travesía del Atlántico en solitario", "un edificio despierta sin electricidad"],
        "social": ["anunciar un cambio profesional", "compartir una foto de montaña", "reaccionar a un resultado deportivo", "pedir consejo para comprar una bici", "contar un pequeño logro", "pedir consejos para una mudanza", "anunciar un nacimiento", "criticar una decisión municipal", "compartir una receta casera", "buscar compañero de piso"],
        "email": ["reclamar una factura impagada", "proponer una reunión de arranque", "informar a un socio de un cambio de proveedor", "pedir vacaciones al responsable", "rechazar una oferta comercial con educación", "confirmar una entrevista de trabajo", "reportar un incidente técnico a un proveedor", "felicitar a una compañera ascendida", "pedir aclaraciones sobre un contrato", "organizar un viaje de trabajo"],
        "essay": ["el lugar del trabajo en nuestras vidas", "¿debe regularse la IA en la escuela?", "¿las redes sociales nos aíslan?", "el papel del arte en la sociedad", "¿ciudad o campo?", "¿es la protección ambiental una carga?", "¿el dinero da la felicidad?", "¿es el deporte integrador?", "¿debería ser obligatorio votar?", "¿tiene valor social la ficción?"],
    },
    "pt": {
        "news": ["reforma das pensões", "novo comboio noturno Paris-Berlim", "seca no sul da Europa", "fusão bancária", "descida dos juros da habitação", "ciberataque a um hospital", "votação do orçamento", "recordes de temperatura em outubro", "abertura de um data center", "crise do transporte marítimo"],
        "wiki": ["o farol de Cordouan", "a tectónica de placas", "a história do papel", "o sistema imunitário", "a fermentação do pão", "o canal do Suez", "as marés", "a história da fotografia", "a sericicultura", "o vulcanismo na Islândia"],
        "abstracts": ["o sono e a consolidação da memória", "previsão da procura elétrica com aprendizagem automática", "biodiversidade dos solos agrícolas", "diagnóstico precoce por imagem médica", "resistência aos antibióticos em bactérias Gram negativas", "teletrabalho e mobilidade urbana", "corrosão do aço em meio marinho", "modelação climática regional", "aprendizagem da leitura na infância", "qualidade do ar interior nas escolas"],
        "reviews": ["uma batedeira de gama alta", "botas de caminhada", "uma subscrição desportiva", "um colchão de molas", "um banco online", "uma bicicleta elétrica urbana", "auscultadores com cancelamento de ruído", "uma impressora laser", "um serviço de entrega de refeições", "um corta-relvas robô"],
        "reddit": ["mudar de carreira aos 40", "aprender uma língua sozinho", "o meu primeiro apartamento e os vizinhos", "investir uma pequena herança", "reparar a minha máquina de lavar", "emigrar sem curso", "lidar com um chefe incompetente", "escolher um cão para um apartamento", "a minha pior entrevista", "trabalhar por conta própria"],
        "recipes": ["tarte de maçã e alecrim", "estufado de vaca tradicional", "sopa de abóbora e coco", "pão de fermentação natural", "risoto de cogumelos", "gratinado de batata", "frango assado com ervas", "salada de lentilhas com queijo de cabra", "tarte de limão merengada", "ratatouille de legumes"],
        "books": ["um faroleiro encontra uma carta numa garrafa", "duas irmãs reencontram-se vinte anos depois", "uma aldeia inteira perde a memória numa noite", "um relojoeiro repara um relógio que não existe", "uma última conversa numa estação vazia", "uma criança sabe que a casa vai ser demolida", "um médico rural durante uma tempestade", "um livreiro recebe um manuscrito anónimo", "uma travessia do Atlântico a solo", "um edifício acorda sem eletricidade"],
        "social": ["anunciar uma mudança de carreira", "partilhar uma foto de montanha", "reagir a um resultado desportivo", "pedir conselhos para comprar bicicleta", "contar uma pequena conquista", "pedir dicas para uma mudança de casa", "anunciar um nascimento", "criticar uma decisão da câmara", "partilhar uma receita caseira", "procurar colega de casa"],
        "email": ["cobrar uma fatura em atraso", "propor uma reunião inicial", "informar um parceiro de mudança de fornecedor", "pedir férias ao responsável", "recusar educadamente uma proposta comercial", "confirmar uma entrevista", "reportar um incidente técnico", "felicitar uma colega promovida", "pedir esclarecimentos sobre um contrato", "organizar uma viagem de trabalho"],
        "essay": ["o lugar do trabalho na nossa vida", "deve regular-se a IA na escola", "as redes sociais isolam-nos", "o papel da arte na sociedade", "cidade ou campo", "a proteção ambiental é uma restrição", "o dinheiro traz felicidade", "o desporto integra", "o voto deve ser obrigatório", "a ficção tem valor social"],
    },
    "it": {
        "news": ["riforma delle pensioni", "nuovo treno notturno Parigi-Berlino", "siccità nel sud Europa", "fusione bancaria", "calo dei tassi sui mutui", "cyberattacco a un ospedale", "voto del bilancio", "record di temperature in ottobre", "apertura di un data center", "crisi del trasporto marittimo"],
        "wiki": ["il faro di Cordouan", "la tettonica a placche", "la storia della carta", "il sistema immunitario", "la fermentazione del pane", "il canale di Suez", "le maree", "la storia della fotografia", "la bachicoltura", "il vulcanismo in Islanda"],
        "abstracts": ["il sonno e la consolidazione della memoria", "previsione della domanda elettrica con apprendimento automatico", "biodiversità dei suoli agricoli", "diagnosi precoce con imaging medico", "resistenza agli antibiotici nei batteri Gram negativi", "lavoro da remoto e mobilità urbana", "corrosione dell'acciaio in ambiente marino", "modellistica climatica regionale", "apprendimento della lettura nei bambini", "qualità dell'aria indoor nelle scuole"],
        "reviews": ["una planetaria di fascia alta", "scarponi da trekking", "un abbonamento sportivo", "un materasso a molle", "una banca online", "una bici elettrica urbana", "cuffie con cancellazione del rumore", "una stampante laser", "un servizio di consegna pasti", "un robot tagliaerba"],
        "reddit": ["cambiare carriera a 40 anni", "imparare una lingua da soli", "il mio primo appartamento e i vicini", "investire una piccola eredità", "riparare la lavatrice da solo", "trasferirsi all'estero senza laurea", "gestire un capo incompetente", "scegliere un cane in appartamento", "il mio peggior colloquio", "lavorare in proprio"],
        "recipes": ["crostata di mele e rosmarino", "brasato di manzo tradizionale", "zuppa di zucca e cocco", "pane a lievitazione naturale", "risotto ai funghi", "gratin di patate", "pollo arrosto alle erbe", "insalata di lenticchie e caprino", "crostata al limone meringata", "ratatouille di verdure"],
        "books": ["un guardiano del faro trova una lettera in una bottiglia", "due sorelle si ritrovano dopo vent'anni", "un intero paese perde la memoria in una notte", "un orologiaio ripara un orologio che non esiste", "un'ultima conversazione in una stazione vuota", "un bambino scopre che abbatteranno la casa", "un medico di campagna durante una tempesta", "un libraio riceve un manoscritto anonimo", "una traversata atlantica in solitaria", "un palazzo si sveglia senza elettricità"],
        "social": ["annunciare un cambio di carriera", "condividere una foto in montagna", "commentare un risultato sportivo", "chiedere consigli per comprare una bici", "raccontare un piccolo successo", "chiedere consigli per un trasloco", "annunciare una nascita", "criticare una decisione comunale", "condividere una ricetta casalinga", "cercare un coinquilino"],
        "email": ["sollecitare una fattura non pagata", "proporre una riunione di avvio", "informare un partner del cambio fornitore", "chiedere ferie al responsabile", "rifiutare educatamente un'offerta", "confermare un colloquio", "segnalare un incidente tecnico a un fornitore", "fare i complimenti a una collega promossa", "chiedere chiarimenti su un contratto", "organizzare un viaggio di lavoro"],
        "essay": ["il posto del lavoro nella nostra vita", "va regolata l'IA a scuola", "i social ci isolano", "il ruolo dell'arte nella società", "città o campagna", "la tutela ambientale è un vincolo", "i soldi fanno la felicità", "lo sport integra", "il voto deve essere obbligatorio", "la narrativa ha valore sociale"],
    },
    "zh": {
        "news": ["养老金改革", "巴黎至柏林夜间列车开通", "南欧干旱", "银行合并", "房贷利率下降", "医院遭网络攻击", "议会预算表决", "十月气温创纪录", "数据中心启用", "航运业危机"],
        "wiki": ["科尔杜昂灯塔", "板块构造", "造纸术的历史", "免疫系统", "面包发酵", "苏伊士运河", "潮汐", "摄影史", "养蚕业", "冰岛火山活动"],
        "abstracts": ["睡眠与记忆巩固", "用机器学习预测电力需求", "农业土壤的生物多样性", "医学影像的早期诊断", "革兰阴性菌的抗生素耐药性", "远程办公与城市出行", "海洋环境中钢材的腐蚀", "区域气候模拟", "儿童阅读习得", "学校室内空气质量"],
        "reviews": ["高端厨师机", "登山鞋", "体育流媒体订阅", "弹簧床垫", "网络银行", "城市电动自行车", "降噪耳机", "激光打印机", "外卖配送服务", "机器人割草机"],
        "reddit": ["四十岁转行", "独自学一门语言", "我的第一套房子和邻居", "小额遗产如何投资", "自己修洗衣机", "没有学历出国", "如何应对无能的领导", "公寓里养什么狗", "我最糟的面试", "开始做自由职业"],
        "recipes": ["苹果迷迭香塔", "传统红酒炖牛肉", "南瓜椰奶浓汤", "无机器酸面包", "蘑菇烩饭", "法式土豆焗", "香草烤鸡", "扁豆沙拉配热羊奶酪", "柠檬蛋白塔", "普罗旺斯炖菜"],
        "books": ["灯塔看守人在瓶子里发现一封信", "姐妹二十年后重逢", "整个村庄一夜之间失去记忆", "钟表匠修理一只不存在的表", "空车站里的最后一次对话", "孩子得知房子将被拆除", "暴风雨中的乡村医生", "书商收到匿名手稿", "独自横渡大西洋", "一栋楼在没有电的清晨醒来"],
        "social": ["宣布转行", "分享登山照片", "评论一场体育比赛", "询问买自行车的建议", "分享一个小成就", "咨询搬家建议", "宣布孩子出生", "批评市政决定", "分享家常菜", "寻找合租室友"],
        "email": ["催收逾期发票", "提议召开项目启动会", "通知合作伙伴更换供应商", "向主管请假", "婉拒商务报价", "确认面试", "向供应商报告技术故障", "祝贺同事升职", "询问合同细节", "安排出差"],
        "essay": ["工作在生活中的位置", "学校是否应规范人工智能", "社交媒体是否让人更孤独", "艺术在社会中的作用", "住城市还是乡村", "环保是不是负担", "金钱能带来幸福吗", "体育是否促进融合", "投票应否强制", "虚构文学有社会价值吗"],
    },
    "ar": {
        "news": ["إصلاح نظام التقاعد", "قطار ليلي جديد بين باريس وبرلين", "الجفاف في جنوب أوروبا", "اندماج مصرفي", "انخفاض فوائد القروض العقارية", "هجوم سيبراني على مستشفى", "التصويت على الميزانية", "أرقام قياسية للحرارة في أكتوبر", "افتتاح مركز بيانات", "أزمة النقل البحري"],
        "wiki": ["منارة كوردوان", "تكتونية الصفائح", "تاريخ الورق", "الجهاز المناعي", "تخمير الخبز", "قناة السويس", "المد والجزر", "تاريخ التصوير الفوتوغرافي", "تربية دودة القز", "النشاط البركاني في آيسلندا"],
        "abstracts": ["النوم وتثبيت الذاكرة", "التنبؤ بالطلب على الكهرباء بالتعلم الآلي", "التنوع الحيوي في التربة الزراعية", "التشخيص المبكر بالتصوير الطبي", "مقاومة المضادات الحيوية في البكتيريا سالبة الغرام", "العمل عن بعد والتنقل الحضري", "تآكل الفولاذ في البيئة البحرية", "النمذجة المناخية الإقليمية", "تعلم القراءة عند الأطفال", "جودة الهواء الداخلي في المدارس"],
        "reviews": ["عجانة مطبخ راقية", "حذاء للمشي الجبلي", "اشتراك رياضي للبث", "مرتبة نابضية", "بنك عبر الإنترنت", "دراجة كهربائية حضرية", "سماعات عازلة للضوضاء", "طابعة ليزر", "خدمة توصيل الطعام", "جزازة عشب آلية"],
        "reddit": ["تغيير المهنة في الأربعين", "تعلم لغة بمفردك", "شقتي الأولى وجيراني", "استثمار ميراث صغير", "إصلاح غسالتي بنفسي", "الهجرة دون شهادة", "التعامل مع مدير غير كفؤ", "اختيار كلب لشقة", "أسوأ مقابلة عمل مررت بها", "العمل الحر"],
        "recipes": ["تارت التفاح وإكليل الجبل", "طاجين لحم البقر التقليدي", "شوربة القرع وجوز الهند", "خبز بالخمير الطبيعي دون آلة", "ريزوتو الفطر", "غراتان البطاطس", "دجاج مشوي بالأعشاب", "سلطة العدس مع جبن الماعز", "تارت الليمون بالمرينغ", "راتاتوي الخضار"],
        "books": ["حارس منارة يجد رسالة في زجاجة", "شقيقتان تلتقيان بعد عشرين عاماً", "قرية بأكملها تفقد ذاكرتها في ليلة", "ساعاتي يصلح ساعة غير موجودة", "حديث أخير في محطة فارغة", "طفل يعلم أن منزلهم سيُهدم", "طبيب ريفي خلال عاصفة", "بائع كتب يتلقى مخطوطاً مجهولاً", "عبور الأطلسي منفرداً", "مبنى يستيقظ دون كهرباء"],
        "social": ["الإعلان عن تغيير المسار المهني", "مشاركة صورة من الجبل", "التعليق على نتيجة رياضية", "طلب نصيحة لشراء دراجة", "الحديث عن إنجاز صغير", "طلب نصائح للانتقال", "الإعلان عن مولود", "انتقاد قرار بلدي", "مشاركة وصفة منزلية", "البحث عن رفيق سكن"],
        "email": ["مطالبة بفاتورة متأخرة", "اقتراح اجتماع انطلاق", "إبلاغ شريك بتغيير المزود", "طلب إجازة من المسؤول", "رفض عرض تجاري بلطف", "تأكيد مقابلة عمل", "الإبلاغ عن عطل تقني لمزود", "تهنئة زميلة بترقية", "طلب توضيح بشأن عقد", "تنظيم رحلة عمل"],
        "essay": ["مكانة العمل في حياتنا", "هل يجب تنظيم استخدام الذكاء الاصطناعي في المدارس", "هل تزيد الشبكات الاجتماعية العزلة", "دور الفن في المجتمع", "السكن في المدينة أم الريف", "هل حماية البيئة قيد", "هل يجلب المال السعادة", "هل الرياضة وسيلة اندماج", "هل يجب أن يكون التصويت إلزامياً", "هل للرواية قيمة اجتماعية"],
    },
}

WORD_TARGET = {"court": "30 à 80 mots", "moyen": "150 à 300 mots",
               "long": "500 à 900 mots", "tres-long": "1500 à 3000 mots"}
# Le chinois ne sépare pas les mots : la longueur se compte en caractères.
WORD_TARGET_ZH = {"court": "30 至 80 字", "moyen": "150 至 300 字",
                  "long": "500 至 900 字", "tres-long": "1500 至 3000 字"}

# Rappel de longueur quand le modèle s'arrête trop tôt. Dans la langue cible : une
# consigne française glissée dans un prompt arabe fait basculer la langue de sortie.
LENGTH_HINT = {
    "fr": "Le texte doit contenir au moins {n} mots. Développe jusqu'à cette longueur.",
    "en": "The text must contain at least {n} words. Keep writing until you reach it.",
    "es": "El texto debe tener al menos {n} palabras. Sigue escribiendo hasta alcanzarla.",
    "pt": "O texto deve ter pelo menos {n} palavras. Continua até a atingir.",
    "it": "Il testo deve contenere almeno {n} parole. Continua fino a raggiungerla.",
    "zh": "文本至少需要 {n} 个字，请继续写到达标。",
    "ar": "يجب أن يحتوي النص على {n} كلمة على الأقل. واصل الكتابة حتى تبلغها.",
}
MAX_TOKENS = {"court": 700, "moyen": 1200, "long": 2600, "tres-long": 7000}


# ------------------------------------------------------------------ utilitaires

def subject_slug(subject: str, index: int) -> str:
    """Slug ASCII du sujet. Repli numéroté quand l'écriture n'est pas latine.

    `ارتفاع...` et `养老金改革` ne laissent aucun caractère après translittération : sans
    repli, tous les fichiers d'une langue porteraient le même nom de sujet.
    """
    s = slug(subject)
    return s if s != "sujet" else f"sujet{index + 1:02d}"


def slug(text: str, limit: int = 40) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:limit].rstrip("-") or "sujet"


def publisher(model: str) -> str:
    """Préfixe le plus long connu : `qwen3.8-max` commence par `qwen`, pas par `qwen3.8`."""
    for prefix in sorted(PUBLISHERS, key=len, reverse=True):
        if model.startswith(prefix):
            return PUBLISHERS[prefix]
    return model.split("-")[0]


def subjects_for(lang: str, domain: str) -> list[str]:
    table = SUBJECTS.get(lang) or SUBJECTS_TRANSLATED.get(lang)
    if table:
        return table[domain]
    return SUBJECTS["en"][domain]


def api(path: str, payload=None, token=None, session=None, method=None):
    body = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method or ("POST" if payload else "GET"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                 "x-opencode-session": session or str(uuid.uuid4()), "User-Agent": "isitai-corpus"})
    # Un run de plusieurs heures traverse forcément une coupure réseau. Sans reprise ici,
    # un seul timeout tue le processus et perd la file entière.
    last: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError:
            raise
        except (TimeoutError, urllib.error.URLError, OSError) as e:
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"réseau : {type(last).__name__}: {last}")


def load_token() -> str:
    for line in open(os.path.expanduser("~/.hermes/.env"), encoding="utf-8"):
        m = re.match(r"^OPENCODE_GO_API_KEY=(.*)$", line.strip())
        if m:
            return m.group(1).strip("\"'")
    sys.exit("OPENCODE_GO_API_KEY absente de ~/.hermes/.env")


def monthly_percent(token: str) -> int:
    try:
        return api("/usage", token=token)["usage"]["monthly"]["percent"]
    except Exception:
        return -1


def existing_ids() -> set[str]:
    if not MANIFEST.exists():
        return set()
    out = set()
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.add(json.loads(line)["id"])
            except (KeyError, json.JSONDecodeError):
                continue
    return out


def weight_of(model: str) -> int:
    return WEIGHTS.get(model, 1)


def plan_for(lang: str, models: list[str]) -> list[dict]:
    """Répartition déterministe : le modèle tourne le plus vite, puis le domaine, puis le sujet.

    L'ordre compte. Faire tourner le domaine le plus vite revenait à produire 140 textes
    avec un seul modèle avant de passer au suivant : la diversité d'éditeurs, qui est la
    raison d'être de ce corpus, arrivait trop tard. Ici, tous les modèles apparaissent dès
    les premières dizaines de textes, et un même sujet est traité par plusieurs modèles —
    ce qui est aussi le contrôle scientifique utile.
    """
    total = TARGETS[lang]
    very_long_budget = max(1, int(total * 0.10))
    distinct = sorted(set(models), key=weight_of, reverse=True)
    # Un balayage complet des modèles par domaine : le domaine change tous les
    # `len(distinct)` textes, donc chaque domaine voit passer tous les modèles.
    slots = [m for m in distinct for _ in range(weight_of(m))]
    if not slots:
        slots = models
    rows = []
    i = 0
    while len(rows) < total:
        model = slots[i % len(slots)]
        # Le domaine change à chaque texte, le sujet tous les dix : un même domaine voit
        # ainsi défiler tous ses sujets, au lieu de rester sur le premier pendant 240 textes.
        domain = DOMAINS[i % len(DOMAINS)]
        subjects = subjects_for(lang, domain)
        subject = subjects[(i // len(DOMAINS)) % len(subjects)]
        if domain in VERY_LONG_DOMAINS and very_long_budget > 0 and i % 20 == 7:
            length = "tres-long"
            very_long_budget -= 1
        else:
            # La longueur tourne sur les trois autres, sans restriction par domaine :
            # c'est la répartition de la demande initiale, conservée telle quelle.
            length = ["court", "moyen", "long"][i % 3]
        rows.append({"langue": lang, "modele_id": model, "domaine": domain,
                     "longueur_cible": length, "sujet": subject,
                     "sujet_n": subjects.index(subject), "n": len(rows) + 1})
        i += 1
    return rows


def count_units(text: str, lang: str) -> int:
    """Longueur du texte dans l'unité de la langue.

    `text.split()` compte les mots à l'espace : un texte chinois de 300 caractères n'en
    compte qu'un seul, passe donc pour une sortie vide et se fait jeter deux fois de suite.
    """
    if lang in ("zh", "ja"):
        cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        latin = len([w for w in text.split() if w.isascii()])
        return cjk + latin
    return len(text.split())


def prompt_for(row: dict) -> str:
    style = STYLE[row["langue"]][row["domaine"]]
    words = (WORD_TARGET_ZH if row["langue"] == "zh" else WORD_TARGET)[row["longueur_cible"]]
    return f"{style}\n\nSujet : {row['sujet']}.\nLongueur : {words}. Écris uniquement le texte demandé."


def generate(token: str, row: dict, temperature: float) -> tuple[str, dict]:
    """Renvoie (texte, métadonnées d'usage). Lève RuntimeError après deux sorties vides."""
    prompt = prompt_for(row)
    max_tokens = MAX_TOKENS[row["longueur_cible"]]
    for attempt in (1, 2, 3):
        payload = {"model": row["modele_id"],
                   "messages": [{"role": "user", "content": prompt}],
                   "max_tokens": max_tokens * attempt, "temperature": temperature}
        try:
            d = api("/chat/completions", payload, token=token)
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode("utf-8", "replace")
            if e.code in (429, 503) and attempt < 3:
                # Les modèles gratuits limitent durement le débit : vingt secondes ne
                # suffisent pas, et un texte perdu ici doit être repayé ailleurs.
                time.sleep(60 * attempt)
                continue
            # Certains modèles refusent une température libre : la sortie n'est pas en
            # cause, seulement le réglage. On rejoue une fois avec la valeur acceptée
            # plutôt que de perdre le texte.
            if e.code == 400 and "temperature" in body.lower() and payload["temperature"] != 1.0:
                payload["temperature"] = 1.0
                try:
                    d = api("/chat/completions", payload, token=token)
                except Exception:
                    raise RuntimeError(f"HTTP 400 (température imposée) : {body[:120]}")
                text = (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
                if count_units(text, row["langue"]) >= 20:
                    return text, d.get("usage", {})
            raise RuntimeError(f"HTTP {e.code}: {body[:120]}")
        except RuntimeError:
            if attempt == 1:
                raise
            continue
        text = (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        usage = d.get("usage", {})
        if count_units(text, row["langue"]) < 20:
            time.sleep(3)
            continue
        lo, hi = LENGTHS[row["longueur_cible"]]
        words = count_units(text, row["langue"])
        if lo * 0.85 <= words <= hi * 1.15:
            return text, usage
        # Trop court : un « long » de 300 mots serait mal étiqueté et fausserait toute
        # comparaison par longueur. On relance une fois avec une consigne explicite.
        payload["messages"][0]["content"] = prompt + "\n" + LENGTH_HINT[row["langue"]].format(n=int(lo))
        payload["max_tokens"] = max_tokens * 2
        try:
            d = api("/chat/completions", payload, token=token)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} au rappel de longueur")
        text = (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        usage = d.get("usage", {})
        words = count_units(text, row["langue"])
        if lo * 0.85 <= words <= hi * 1.15:
            return text, usage
        raise RuntimeError(f"hors longueur : {words} unités pour {lo}-{hi}")
    raise RuntimeError("sortie vide après deux tentatives")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=LANGS, action="append")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--models", default="", help="liste séparée par des virgules")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--temperature", type=float, default=0.9)
    ap.add_argument("--max-allowance", type=float, default=1.0)
    ap.add_argument("--quota-ceiling", type=int, default=85)
    ap.add_argument("--sleep", type=float, default=1.5)
    args = ap.parse_args()

    if args.list_models:
        for m in MODELS:
            print(f"  {m:<28} {publisher(m)}")
        return 0

    token = load_token()
    models = [m.strip() for m in args.models.split(",") if m.strip()] or MODELS
    langs = args.lang or LANGS
    CORPUS.mkdir(exist_ok=True)
    seen = existing_ids()

    quota = monthly_percent(token)
    print(f"  quota mensuel : {quota} % (plafond {args.quota_ceiling} %)")
    if quota >= args.quota_ceiling:
        print("  plafond atteint : aucun appel ne sera fait", file=sys.stderr)
        return 1

    written = failed = skipped = 0
    spent = 0.0
    for lang in langs:
        rows = plan_for(lang, models)
        for row in rows:
            if args.limit and written + failed >= args.limit:
                break
            text_id = (f"ia_{row['modele_id']}_{lang}_{row['domaine']}_{row['longueur_cible']}"
                       f"_{subject_slug(row['sujet'], row['sujet_n'])}_{row['n']:03d}")
            target = CORPUS / "ai" / lang / row["modele_id"] / f"{text_id}.txt"
            if text_id in seen or target.exists():
                skipped += 1
                continue
            if args.dry_run:
                print(f"  [sec] {text_id}")
                written += 1
                continue
            if spent >= args.max_allowance:
                print(f"  budget de {args.max_allowance} atteint : arrêt propre")
                return 0
            try:
                text, usage = generate(token, row, args.temperature)
            except RuntimeError as e:
                failed += 1
                print(f"  ✗ {text_id} : {e}")
                with open(CORPUS / "failures.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"id": text_id, "modele_id": row["modele_id"],
                                        "raison": str(e), "date": time.strftime("%Y-%m-%dT%H:%M:%S")},
                                       ensure_ascii=False) + "\n")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
            allowance = float(usage.get("opencode", {}).get("allowance") or 0)
            spent += allowance
            entry = {"id": text_id, "fichier": str(target.relative_to(CORPUS)),
                     "modele_id": row["modele_id"], "editeur": publisher(row["modele_id"]),
                     "langue": lang, "domaine": row["domaine"],
                     "longueur_cible": row["longueur_cible"],
                     "nb_mots": count_units(text, row["langue"]),
                     "sujet": row["sujet"], "prompt": prompt_for(row),
                     "temperature": args.temperature,
                     "date_generation": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "allowance": round(allowance, 8)}
            with open(MANIFEST, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            written += 1
            unit = "字" if row["langue"] == "zh" else "mots"
            print(f"  ✓ {text_id} · {entry['nb_mots']} {unit} · {allowance:.6f}")
            # Le quota se relit en cours de lot : un plafond vérifié au seul démarrage ne
            # protège de rien sur un run de plusieurs heures.
            if written % 50 == 0:
                q = monthly_percent(token)
                if q >= args.quota_ceiling:
                    print(f"  quota mensuel à {q} % (plafond {args.quota_ceiling}) : arrêt propre")
                    return 0
            time.sleep(args.sleep)

    print(f"\n  écrits {written} · ignorés {skipped} · échecs {failed} · allowance {spent:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
