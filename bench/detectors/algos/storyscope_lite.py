"""storyscope_lite: lexical and structural PROXIES of some StoryScope narrative features.

  run.py --algo storyscope_lite --variant lr           --split all
  run.py --algo storyscope_lite --variant lr-nolayout  --split all
  run.py --algo storyscope_lite --variant paper-sign   --split all

THIS IS NOT A REPRODUCTION OF THE PAPER
---------------------------------------
StoryScope (Russell et al., "StoryScope: Investigating idiosyncrasies in AI fiction",
arXiv 2604.03136, COLM 2026; code github.com/jenna-russell/storyscope) has an LLM read
each story (about 5,000 words): GPT-5.1 writes a structured template and discovers 304
features over 10 NarraBench dimensions, Gemini 3 Flash answers the 304 questions for each
story, and XGBoost classifies (93.2% macro-F1 human vs AI with 304 features, 84.8% with
the 30 core features, on 61,608 stories). Every feature is a JUDGEMENT about plot,
characters, theme or narration.

An offline library has no LLM. This file counts words and patterns that are plausibly
correlated with SOME of those judgements, and fits a logistic regression. A word count is
not a reading: "olfactory_rate" counts smell words, it does not decide that smell is a
dominant sensory modality. Nothing here was validated against the paper's feature values
(the per-story feature values were not used). Read the results as "what regex proxies of
narrative features give", not as "what StoryScope gives".

Deviations from the paper (all of them)
- Feature extraction: regexes and word lists (about 850 English words) instead of GPT-5.1
  and Gemini 3 Flash. 304 features become 48 proxies; see the table below.
- Classifier: standardisation + L2 logistic regression (C = 1.0, lbfgs) instead of
  XGBoost. `paper-sign` has no learned weight at all.
- Training data: the benchmark train split (RAID: 4,000 texts, median 225 words, domains
  abstracts, books, news, recipes, reddit, wiki, generators of 2022-2023). The paper
  trains on about 5,000-word stories from five 2026 models. No fiction is in train, so
  the weights are learned on non-fiction and short texts.
- Length: the paper's stories average 4,753 words; test_fiction has 1,000 to 1,950 words
  and the other splits are far shorter. Every feature is a rate or a share, never a raw
  count, because train AI texts stop at 456 words and train human texts reach 4,440.
- Truncation: features are computed on the first MAX_WORDS = 6,000 whitespace-separated
  words; the "ending" window is the last 150 words of the FULL text and the "opening"
  window its first 150 words (word windows, not paragraphs, so that they do not depend on
  line breaks). No 512-token cut: it would remove the ending.
- Language: the word lists are English. On test_fr the lexical proxies are near zero for
  both classes; only dialogue share, sentence statistics, names and layout still measure
  something. A French score from this module means little.

Normalisation before any feature (so that formatting is not the signal)
- curly quotes, guillemets, `` and '' become "; curly apostrophes become '.
- Markdown heading lines (`# Title`) and emphasis markers (* _ around words) are removed.
  Some AI stories of test_fiction start with a Markdown title; human ones never do.
- em and en dashes become " - ". Quote style and dash style are not features.
- Dialogue = text between two double quotes (at most 1,200 characters). Dialogue marked
  with single quotes or with a leading dash (French, some British books) is NOT seen.

Variants
- lr           all 48 proxies, logistic regression fitted on train.
- lr-nolayout  the 42 proxies that do not depend on line breaks; the text is whitespace-
               collapsed first. In RAID no human text has a blank line while many AI
               texts do (corpus artefact, see stylometry_lr.py), so `lr` partly learns
               "has paragraphs = AI". THIS is the variant to read.
- paper-sign   no learned weight: each core proxy is standardised with the mean and the
               standard deviation of the train split (labels unused), clipped to [-3, 3]
               and added with the sign the paper reports in Table 16 (+1 AI-elevated, -1
               human-elevated). It tests whether the paper's directions show through the
               proxies, independently of what RAID teaches. Line-break-blind too.

The 30 core features of the paper (Tables 14-16; 33 rows because three categorical
features appear with two options each) and what is done here
  P = lexical proxy implemented, W = weak proxy (loosely related), N = not approximable

  AI-elevated
   1 Thematic Explicitness and Moralizing        P  theme_rate, theme_end_rate, end_theme_lift
   2 Emotional Expression -> embodied            P  embodied_rate, embodied_share
   3 Thematic Unity                              N  needs the plot
   4 Sensory Modalities -> olfactory             P  olfactory_rate
   5 Character Introduction -> external descr.   W  open_appearance_rate (appearance words in
                                                    the first 150 words)
   6 Setting as Psychological Mirror             N  needs to relate setting to inner state
   7 Continuity of Main Causal Chain             N
   8 Sensory Density                             P  sensory_rate
   9 Agency in Resolution -> protagonist choice  N
  10 Narratorial Thematic Commentary -> yes      W  aphorism_rate (generalising sentence
                                                    patterns outside dialogue)
  11 Opening Spatial Grounding                   W  open_spatial_rate
  12 Dialogue Function -> philosophical debate   W  dialogue_theme_rate (theme and moral words
                                                    inside quotes)
  13 Spatial Granularity Level                   W  spatial_rate
  14 Subplot Integration -> no subplots          N
  15 Moral / Philosophical Weighting             P  moral_rate
  16 Reference Explicitness -> implicit echoes   N
  17 Environmental and Ecological Emphasis       P  nature_rate
  18 Mode of Resolution -> internal understand.  W  end_realisation_rate (realise/understand/
                                                    accept words in the last 150 words)
  19 Pre-Threat Character Investment             N
  20 Depth of Interior Access                    P  interior_rate
  Human-elevated
  21 Intertextual Strategy -> explicit named     N  would need a list of works and authors
  22 Frequency of Direct Reader Address          P  you_narration_rate
  23 Reference Explicitness -> balanced mix      N
  24 Depth of Recontextualization After Surprise N
  25 Dialogue-to-Narration Proportion            P  dialogue_share, dialogue_turn_rate
  26 Fourth-Wall Permeability                    W  fourth_wall_rate
  27 Subplot Integration -> thematically parallel N
  28 Degree of Chronological Discontinuity       W  timeshift_rate
  29 Location Variety Scope                      W  place_variety
  30 Anachrony Intensity                         W  pluperfect_rate, flashback_rate
  31 Moral Polarity -> ambivalent/mixed          N
  32 Emotional Expression -> explicit labels     P  emotion_label_rate (and embodied_share)
  33 Nonlinear Framing for Delayed Disclosure    N

  Rows 2/32, 14/27 and 16/23 are the same feature, so of the 30 features: 9 have a lexical
  proxy (rows 1, 2/32, 4, 8, 15, 17, 20, 22, 25), 10 a weak proxy (5, 10, 11, 12, 13, 18,
  26, 28, 29, 30) and 11 none (3, 6, 7, 9, 14/27, 16/23, 19, 21, 24, 31, 33). The 19
  features with a proxy give the 25 "core" columns used by paper-sign.

Other proxies ("extra" group, used by lr and lr-nolayout, not by paper-sign). They
relate to non-core StoryScope dimensions (Agent naming, Perspective, Time, Style,
Structure) or to features the task asked for:
  name_variety, name_rate, top_name_share (character-name diversity), first_person_rate,
  present_share and tense_switch_rate (tense consistency), opener_entropy,
  pronoun_opener_share, the_opener_share, ing_opener_share (sentence-opening variety),
  sent_len_cv, short_sent_share, question_rate, simile_rate, open_dialogue (in medias res
  with speech), end_dialogue, said_tag_share (plain "said" among speech verbs).
Layout group (lr only): para_len_log_mean, para_len_cv, para_single_sent_share,
  dialogue_para_share, scene_break_rate, last_para_rel_len.

Determinism: no randomness in the features; lbfgs logistic regression is deterministic.

First full run (2026-11-12, AUROC, machine shared with other jobs so no timing here; the
feature list was frozen before test_fiction was scored and was not changed after):
  lr           test 0.751, test_ood 0.666, test_fr 0.534, test_fiction 0.435
  lr-nolayout  test 0.684, test_ood 0.642, test_fr 0.481, test_fiction 0.335
  paper-sign   test 0.495, test_ood 0.546, test_fr 0.508, test_fiction 0.675
The weights learned on RAID point the WRONG way on fiction (below 0.5): what separates
human from AI in short 2022-2023 non-fiction is not what separates them in stories.
paper-sign gives nothing on non-fiction and 0.675 on fiction, but that is a NET figure:
taken one by one on test_fiction, 14 of the 25 core columns lean the way the paper says
and 11 do not. Clearly contrary: moral_rate (0.318, paper says AI-elevated),
pluperfect_rate (0.782) and place_variety (0.754), both human-elevated in the paper. So
the time and location proxies either do not measure the paper's constructs or the source
confound dominates: test_fiction opposes amateur Reddit stories to AI stories written
from literary plot prompts, and sensory_rate alone reaches 0.870 there. 0.675 is not
evidence that the paper's findings were reproduced.
Known residue: a title line without `#` survives the normaliser in a few AI stories (at
most 25 of 250 have a first line of 8 words or fewer) and enters the opening window.
place_variety, name_variety (types / sqrt(words)) and opener_entropy are not strictly
length-invariant.
"""
from __future__ import annotations

import math
import re
from collections import Counter

import numpy as np

NAME = "storyscope_lite"
NEEDS_TRAINING = True
MODEL = ("none (48 regex / word-list features, about 850 English words, + standardisation "
         "and logistic regression: under 20 kB of parameters and lists)")
BATCH_SIZE = 64
MAX_WORDS = 6000
EDGE_WORDS = 150


def _ws(s: str) -> frozenset:
    return frozenset(s.split())


# ----------------------------------------------------------------------------- word lists
THEME = _ws("""
truth truths meaning meanings purpose hope hopes hopeful love loss grief memory memories
legacy fate destiny freedom forgiveness redemption sacrifice courage faith belonging
identity humanity mortality eternity silence solitude loneliness compassion kindness
resilience strength wisdom lesson lessons journey beginning beginnings ending endings
future past change choice choices possibility possibilities promise promises peace
acceptance understanding healing connection story stories remembrance survival dignity
inheritance tradition traditions heritage ancestors generations home homecoming
""")
MORAL = _ws("""
moral morality ethics ethical justice injustice right wrong good evil sin sins guilt
guilty innocent innocence shame conscience duty honor honour virtue vice mercy cruelty
betrayal loyalty responsibility blame deserve deserved deserves fair unfair fairness
righteous wicked corrupt corruption principle principles truth lie lies honest honesty
dishonest forgive forgiven atonement punishment judge judgment judgement soul souls god
gods philosophy philosophical existence exist meaning believe belief beliefs
""")
EMBODIED = _ws("""
heart chest throat stomach gut breath breathing pulse jaw fists fist knuckles shoulders
spine skin lungs ribs temples palms fingers fingertips knees lips teeth brow eyebrows
trembled trembling shivered shiver shuddered shudder clenched clenching tightened
tightening flinched swallowed swallowing gasped exhaled inhaled pounded pounding
hammered racing raced fluttered flushed blushed paled stiffened tensed winced froze
shook shaking quivered quivering prickled tingled ached aching throbbed throbbing
sweat sweating goosebumps lump knot hollow tears wept sobbed sighed
""")
EMOTION_LABEL = _ws("""
angry anger furious fury rage enraged sad sadness sorrow sorrowful happy happiness
joy joyful glad afraid fear fearful scared terrified terror frightened anxious anxiety
nervous worried worry jealous jealousy envious envy ashamed embarrassed embarrassment
proud pride lonely depressed depression miserable upset annoyed irritated frustrated
frustration excited excitement delighted relieved relief disappointed disappointment
disgusted disgust surprised shocked horrified confused confusion bored guilty hopeful
hopeless desperate despair grateful hatred hate hated loved cheerful pleased content
""")
OLFACTORY = _ws("""
smell smells smelled smelt smelling scent scents scented odor odors odour odours stench
aroma aromas fragrance fragrant perfume perfumed reek reeked reeking stink stank stinking
whiff musk musky pungent acrid nostrils nose sniffed sniffing incense ozone
""")
SENSORY_OTHER = _ws("""
light dark darkness shadow shadows glow glowed glowing glint gleam gleamed shimmer
shimmered flicker flickered bright dim pale golden silver crimson scarlet amber grey gray
blue green red black white yellow violet color colour colors colours hue
sound sounds noise hum hummed humming buzz whisper whispered murmur murmured echo echoed
roar roared rumble rumbled creak creaked hiss hissed rustle rustled crackle crackled
thud clang ringing silence quiet loud
touch touched rough smooth cold warm warmth hot cool damp wet dry sticky slick soft hard
sharp heavy weight texture grit gritty coarse velvet
taste tasted tasting bitter sweet sour salt salty metallic copper tongue flavor flavour
""")
NATURE = _ws("""
tree trees forest forests wood woods river rivers stream creek lake sea ocean waves tide
shore beach mountain mountains hill hills valley field fields meadow grass soil earth
dirt mud stone stones rock rocks wind winds breeze rain rains storm storms snow frost ice
sky skies cloud clouds sun sunlight sunrise sunset dawn dusk moon moonlight star stars
leaf leaves branch branches root roots flower flowers garden bird birds animal animals
wolf deer fish insect insects moss fern pine oak desert dust horizon weather season
seasons winter summer spring autumn harvest seed seeds water
""")
PLACE = _ws("""
room house home kitchen bedroom bathroom hallway corridor door doorway window windows
street road alley city town village building tower church temple school hospital office
shop store market bar tavern inn hotel station train ship boat car truck bus apartment
basement attic cellar garden yard porch roof floor wall walls stairs staircase bridge
harbor harbour port farm barn field forest cave mountain river lake beach island camp
castle palace prison cell lab laboratory library museum restaurant cafe diner warehouse
factory mine tunnel square park cemetery graveyard courtyard cabin cottage tent bunker
airport highway desert planet colony base
""")
SPATIAL_PREP = _ws("""
above below beneath under underneath behind beside between beyond across along around
inside outside onto into toward towards through against near nearby atop amid among
""")
APPEARANCE = _ws("""
hair haired eyes eyed face beard bearded tall short thin slender stout wore wearing
dressed coat jacket dress shirt boots hat cloak robe uniform suit scar scarred wrinkled
freckles complexion build shoulders handsome beautiful pretty ugly old young elderly
""")
INTERIOR = _ws("""
thought thinking wondered wondering realized realised knew remembered remembering
imagined imagining believed hoped wished felt feeling sensed understood supposed
considered doubted feared recalled noticed decided wanted needed dreamed dreamt
""")
REALISATION = _ws("""
realized realised understood understand understanding knew accepted accept acceptance
learned learnt finally peace forgave forgiven belonged whole enough ready
""")
PRON_OPEN = _ws("he she i they it we you")
PAST_AUX = _ws("was were had did said went came got took made saw knew thought felt "
               "looked turned stood sat asked told gave found left began could would")
PRES_AUX = _ws("is are am has does do says goes comes gets takes makes sees knows thinks "
               "feels looks turns stands sits asks tells gives finds can will")
SPEECH_VERBS = _ws("""
said asked replied answered whispered murmured muttered shouted yelled cried called
snapped growled hissed sighed added continued explained demanded insisted admitted
agreed laughed breathed offered began interrupted
""")
NOT_NAMES = _ws("""
the and but then there they this that what when where why how yes not you his her she
him its our their monday tuesday wednesday thursday friday saturday sunday january
february march april may june july august september october november december god
""")

# --------------------------------------------------------------------------- regexes
_RE_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s+.*$")
_RE_EMPH = re.compile(r"(?<!\w)[*_]{1,3}(?=\S)|(?<=\S)[*_]{1,3}(?!\w)")
_RE_SCENE = re.compile(r"(?m)^\s*(?:[*#~\-_=•·]\s*){3,}\s*$")
_RE_QUOTE = re.compile(r'"([^"]{1,1200})"')
_RE_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")
_RE_SENT = re.compile(r"(?<=[.!?])[\"')\]]*\s+")
_RE_PARA = re.compile(r"\n\s*\n|\n")
_RE_YOU = re.compile(r"\b(?:you|your|yours|yourself)\b", re.I)
_RE_FIRST = re.compile(r"\b(?:I|me|my|mine|myself|we|us|our)\b")
_RE_FOURTH = re.compile(
    r"\b(?:dear reader|reader|you see|you know|believe me|trust me|let me tell you|"
    r"i(?:'m| am) telling|as i said|i should (?:mention|explain|say)|i suppose|"
    r"this story|my story|i(?:'ll| will) tell you|mind you|you might think|"
    r"you(?:'d| would) think|truth be told|to be honest|honestly)\b", re.I)
_RE_APHORISM = re.compile(
    r"\b(?:sometimes|perhaps that (?:is|was)|what it (?:means|meant) to|"
    r"some things|there (?:is|are) (?:a kind of|some|certain|things)|"
    r"that(?:'s| is) the thing about|in the end|after all|the truth (?:is|was)|"
    r"(?:it|this|that) (?:was|is|wasn't|isn't) (?:not )?(?:about|just|merely|only)|"
    r"not because [^.]{1,60} but because|was not [^.]{1,40}, but|"
    r"(?:we|people|everyone|no one|nobody) (?:always|never|all) |"
    r"the way (?:things|people|we) |as (?:all|every) [a-z]+ (?:do|does|must))\b", re.I)
_RE_TIMESHIFT = re.compile(
    r"\b(?:(?:years?|months?|weeks?|days?|hours?|minutes?|decades?|centuries) (?:later|ago|"
    r"earlier|before|after)|the (?:next|following|previous) (?:morning|day|night|week|"
    r"year|evening|afternoon)|later that (?:day|night|evening|morning)|"
    r"earlier that (?:day|night|evening|morning)|that (?:night|morning|evening)|"
    r"by the time|meanwhile|in the meantime|afterwards?|eventually|the night before|"
    r"the day before|since then|from then on|until then|some time later|"
    r"when (?:morning|night|dawn|evening) came)\b", re.I)
_RE_FLASHBACK = re.compile(
    r"\b(?:remembered (?:when|how|the)|back (?:then|when|in)|years ago|long ago|once, |"
    r"when (?:i|he|she|they|we) (?:was|were) (?:a |young|little|small|still)|"
    r"as a (?:child|boy|girl|kid)|in those days|used to|"
    r"(?:i|he|she) (?:could|can) still (?:remember|see|hear|smell))\b", re.I)
_RE_PLUPERFECT = re.compile(
    r"\bhad (?:\w+ly )?(?:\w{2,}ed|been|gone|seen|known|taken|given|come|left|made|said|"
    r"told|done|felt|found|thought|heard|lost|become|begun|grown|fallen|written|spoken|"
    r"brought|bought|taught|kept|held|met|run|stood|spent|worn|chosen|broken|forgotten)\b",
    re.I)
_RE_SIMILE = re.compile(r"\b(?:like an? |like the |as if |as though |as \w+ as )", re.I)
_TRANS = str.maketrans({
    "“": '"', "”": '"', "„": '"', "‟": '"', "«": '"',
    "»": '"', "‘": "'", "’": "'", "‚": "'", "′": "'",
    "—": " - ", "–": " - ", "―": " - ", " ": " ", " ": " ",
    "…": "...",
})

# --------------------------------------------------------------------------- feature list
# (name, group, sign in the paper for core proxies: +1 AI-elevated, -1 human-elevated)
SPEC = [
    ("theme_rate", "core", +1), ("theme_end_rate", "core", +1), ("end_theme_lift", "core", +1),
    ("moral_rate", "core", +1), ("aphorism_rate", "core", +1),
    ("dialogue_theme_rate", "core", +1),
    ("embodied_rate", "core", +1), ("embodied_share", "core", +1),
    ("emotion_label_rate", "core", -1),
    ("olfactory_rate", "core", +1), ("sensory_rate", "core", +1), ("nature_rate", "core", +1),
    ("interior_rate", "core", +1),
    ("open_spatial_rate", "core", +1), ("spatial_rate", "core", +1),
    ("open_appearance_rate", "core", +1), ("end_realisation_rate", "core", +1),
    ("you_narration_rate", "core", -1), ("fourth_wall_rate", "core", -1),
    ("dialogue_share", "core", -1), ("dialogue_turn_rate", "core", -1),
    ("timeshift_rate", "core", -1), ("pluperfect_rate", "core", -1),
    ("flashback_rate", "core", -1), ("place_variety", "core", -1),
    ("name_variety", "extra", 0), ("name_rate", "extra", 0), ("top_name_share", "extra", 0),
    ("first_person_rate", "extra", 0), ("present_share", "extra", 0),
    ("tense_switch_rate", "extra", 0),
    ("opener_entropy", "extra", 0), ("pronoun_opener_share", "extra", 0),
    ("the_opener_share", "extra", 0), ("ing_opener_share", "extra", 0),
    ("sent_len_cv", "extra", 0), ("short_sent_share", "extra", 0),
    ("question_rate", "extra", 0), ("simile_rate", "extra", 0),
    ("open_dialogue", "extra", 0), ("end_dialogue", "extra", 0), ("said_tag_share", "extra", 0),
    ("para_len_log_mean", "layout", 0), ("para_len_cv", "layout", 0),
    ("para_single_sent_share", "layout", 0), ("dialogue_para_share", "layout", 0),
    ("scene_break_rate", "layout", 0), ("last_para_rel_len", "layout", 0),
]
FEATURE_NAMES = [s[0] for s in SPEC]
_GROUP = {s[0]: s[1] for s in SPEC}
_SIGN = {s[0]: s[2] for s in SPEC}


def _words(s: str) -> list[str]:
    return [w.lower() for w in _RE_WORD.findall(s)]


def _rate(count: float, n_words: int) -> float:
    """log1p of the count per 1,000 words; 0 for an empty span."""
    return math.log1p(1000.0 * count / n_words) if n_words > 0 else 0.0


def _count(words: list[str], lex: frozenset) -> int:
    return sum(1 for w in words if w in lex)


def _cv(values: list[int]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    if m <= 0:
        return 0.0
    var = sum((v - m) ** 2 for v in values) / len(values)
    return math.sqrt(var) / m


def normalise(text: str, layout: bool) -> tuple[str, int]:
    """Returns the cleaned text and the number of scene-break lines removed."""
    t = text.translate(_TRANS).replace("``", '"').replace("''", '"')
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = _RE_HEADING.sub("", t)
    t, n_breaks = _RE_SCENE.subn("\n", t)
    t = _RE_EMPH.sub("", t)
    if not layout:
        t = " ".join(t.split())
    return t.strip(), n_breaks


def extract(text: str, layout: bool) -> dict[str, float]:
    full, n_breaks = normalise(text, layout)
    spans = [m.span() for m in re.finditer(r"\S+", full)]
    n_full = len(spans)
    if n_full == 0:
        return dict.fromkeys(FEATURE_NAMES, 0.0)
    body = full[: spans[min(n_full, MAX_WORDS) - 1][1]]
    opening = full[: spans[min(n_full, EDGE_WORDS) - 1][1]]
    ending = full[spans[max(0, n_full - EDGE_WORDS)][0]:]

    quotes = [m.group(1) for m in _RE_QUOTE.finditer(body)]
    narration = _RE_QUOTE.sub(" ", body)
    dialogue = " ".join(quotes)
    w_all = _words(body)
    w_nar = _words(narration)
    w_dia = _words(dialogue)
    w_open = _words(opening)
    w_end = _words(ending)
    n, n_nar, n_dia = len(w_all), len(w_nar), len(w_dia)
    f: dict[str, float] = {}

    # --- theme, moral, commentary
    theme_all = _count(w_all, THEME)
    theme_end = _count(w_end, THEME)
    f["theme_rate"] = _rate(theme_all, n)
    f["theme_end_rate"] = _rate(theme_end, len(w_end))
    f["end_theme_lift"] = f["theme_end_rate"] - f["theme_rate"]
    f["moral_rate"] = _rate(_count(w_all, MORAL), n)
    f["aphorism_rate"] = _rate(len(_RE_APHORISM.findall(narration)), n_nar)
    f["dialogue_theme_rate"] = _rate(_count(w_dia, THEME) + _count(w_dia, MORAL), n_dia)

    # --- emotion, senses, environment, interiority
    emb = _count(w_all, EMBODIED)
    lab = _count(w_all, EMOTION_LABEL)
    f["embodied_rate"] = _rate(emb, n)
    f["emotion_label_rate"] = _rate(lab, n)
    f["embodied_share"] = (emb + 1.0) / (emb + lab + 2.0)
    olf = _count(w_all, OLFACTORY)
    f["olfactory_rate"] = _rate(olf, n)
    f["sensory_rate"] = _rate(olf + _count(w_all, SENSORY_OTHER), n)
    f["nature_rate"] = _rate(_count(w_all, NATURE), n)
    f["interior_rate"] = _rate(_count(w_nar, INTERIOR), n_nar)

    # --- space, character introduction, resolution
    f["open_spatial_rate"] = _rate(_count(w_open, SPATIAL_PREP) + _count(w_open, PLACE), len(w_open))
    f["spatial_rate"] = _rate(_count(w_all, SPATIAL_PREP) + _count(w_all, PLACE), n)
    f["open_appearance_rate"] = _rate(_count(w_open, APPEARANCE), len(w_open))
    f["end_realisation_rate"] = _rate(_count(w_end, REALISATION), len(w_end))
    f["place_variety"] = len({w for w in w_all if w in PLACE}) / math.sqrt(n) if n else 0.0

    # --- reader address, dialogue
    f["you_narration_rate"] = _rate(len(_RE_YOU.findall(narration)), n_nar)
    f["fourth_wall_rate"] = _rate(len(_RE_FOURTH.findall(narration)), n_nar)
    f["first_person_rate"] = _rate(len(_RE_FIRST.findall(narration)), n_nar)
    f["dialogue_share"] = n_dia / n if n else 0.0
    f["dialogue_turn_rate"] = _rate(len(quotes), n)
    speech = [w for w in w_nar if w in SPEECH_VERBS]
    f["said_tag_share"] = (speech.count("said") + 1.0) / (len(speech) + 2.0)
    f["open_dialogue"] = 1.0 if opening.lstrip()[:1] == '"' else 0.0
    f["end_dialogue"] = 1.0 if ending.rstrip()[-1:] == '"' else 0.0

    # --- time
    f["timeshift_rate"] = _rate(len(_RE_TIMESHIFT.findall(narration)), n_nar)
    f["pluperfect_rate"] = _rate(len(_RE_PLUPERFECT.findall(narration)), n_nar)
    f["flashback_rate"] = _rate(len(_RE_FLASHBACK.findall(narration)), n_nar)

    # --- sentences (of the narration): openers, length, tense
    sents = [s for s in _RE_SENT.split(narration) if s.strip()]
    openers, lens, tenses = [], [], []
    for s in sents:
        ws = _words(s)
        if not ws:
            continue
        openers.append(ws[0])
        lens.append(len(ws))
        past = sum(1 for w in ws if w in PAST_AUX or (len(w) > 4 and w.endswith("ed")))
        pres = _count(ws, PRES_AUX)
        tenses.append(1 if past > pres else (-1 if pres > past else 0))
    ns = len(openers)
    if ns:
        cnt = Counter(openers)
        ent = -sum(c / ns * math.log(c / ns) for c in cnt.values())
        f["opener_entropy"] = ent / math.log(ns) if ns > 1 else 0.0
        f["pronoun_opener_share"] = sum(c for w, c in cnt.items() if w in PRON_OPEN) / ns
        f["the_opener_share"] = cnt.get("the", 0) / ns
        f["ing_opener_share"] = sum(c for w, c in cnt.items() if len(w) > 4 and w.endswith("ing")) / ns
        f["short_sent_share"] = sum(1 for x in lens if x <= 4) / ns
        f["question_rate"] = narration.count("?") / ns
    else:
        for k in ("opener_entropy", "pronoun_opener_share", "the_opener_share",
                  "ing_opener_share", "short_sent_share", "question_rate"):
            f[k] = 0.0
    f["sent_len_cv"] = _cv(lens)
    marked = [t for t in tenses if t != 0]
    f["present_share"] = (sum(1 for t in marked if t == -1) + 1.0) / (len(marked) + 2.0)
    f["tense_switch_rate"] = (sum(1 for a, b in zip(marked, marked[1:]) if a != b)
                              / (len(marked) - 1)) if len(marked) > 1 else 0.0
    f["simile_rate"] = _rate(len(_RE_SIMILE.findall(body)), n)

    # --- names: capitalised words that do not start a sentence
    names = []
    for s in sents:
        for m in list(re.finditer(r"\b[A-Z][a-z]{2,}\b", s))[0:]:
            if m.start() == 0 or s[:m.start()].strip(" \"'(-") == "":
                continue
            w = m.group(0).lower()
            if w not in NOT_NAMES:
                names.append(w)
    f["name_rate"] = _rate(len(names), n_nar)
    f["name_variety"] = len(set(names)) / math.sqrt(n_nar) if n_nar else 0.0
    f["top_name_share"] = (Counter(names).most_common(1)[0][1] / len(names)) if names else 0.0

    # --- layout (only meaningful when line breaks were kept)
    if layout:
        paras = [p for p in _RE_PARA.split(body) if p.strip()]
        plens = [len(p.split()) for p in paras]
        npar = len(paras)
        f["para_len_log_mean"] = math.log1p(sum(plens) / npar) if npar else 0.0
        f["para_len_cv"] = _cv(plens)
        f["para_single_sent_share"] = (sum(1 for p in paras if len(_RE_SENT.split(p.strip())) <= 1)
                                       / npar) if npar else 0.0
        f["dialogue_para_share"] = (sum(1 for p in paras if '"' in p) / npar) if npar else 0.0
        f["scene_break_rate"] = _rate(n_breaks, n_full)
        f["last_para_rel_len"] = (math.log1p(plens[-1]) - f["para_len_log_mean"]) if npar else 0.0
    else:
        for k in ("para_len_log_mean", "para_len_cv", "para_single_sent_share",
                  "dialogue_para_share", "scene_break_rate", "last_para_rel_len"):
            f[k] = 0.0
    return f


class Detector:
    NEEDS_TRAINING = True
    BATCH_SIZE = BATCH_SIZE

    def __init__(self, variant: str):
        self.variant = variant
        self.NAME = f"storyscope_lite.{variant}"
        self.layout = variant == "lr"
        if variant == "lr":
            self.cols = list(FEATURE_NAMES)
        elif variant == "lr-nolayout":
            self.cols = [k for k in FEATURE_NAMES if _GROUP[k] != "layout"]
        elif variant == "paper-sign":
            self.cols = [k for k in FEATURE_NAMES if _GROUP[k] == "core"]
        else:
            raise ValueError(variant)
        self.MODEL = (f"none ({len(self.cols)} regex / word-list features; "
                      + ("train mean and sd per feature + fixed signs from the paper, no learned weight"
                         if variant == "paper-sign" else "standardisation + logistic regression")
                      + "; parameters and word lists under 20 kB)")
        self.mean = self.sd = self.coef = None
        self.intercept = 0.0

    def _matrix(self, texts: list[str]) -> np.ndarray:
        feats = [extract(t, self.layout) for t in texts]
        x = np.asarray([[f[k] for k in self.cols] for f in feats], dtype=float)
        return np.nan_to_num(x.reshape(len(texts), len(self.cols)), nan=0.0, posinf=0.0, neginf=0.0)

    def fit(self, rows: list[dict]) -> None:
        x = self._matrix([r["text"] for r in rows])
        self.mean = x.mean(axis=0)
        sd = x.std(axis=0)
        self.sd = np.where(sd > 1e-9, sd, 1.0)
        if self.variant == "paper-sign":
            self.coef = np.asarray([_SIGN[k] for k in self.cols], dtype=float)
            self.intercept = 0.0
            return
        from sklearn.linear_model import LogisticRegression
        y = np.asarray([r["label"] for r in rows])
        z = np.clip((x - self.mean) / self.sd, -5.0, 5.0)
        clf = LogisticRegression(C=1.0, max_iter=5000, random_state=0).fit(z, y)
        self.coef = clf.coef_[0].astype(float)
        self.intercept = float(clf.intercept_[0])

    def score(self, texts: list[str]) -> list[float]:
        if not texts:
            return []
        clip = 3.0 if self.variant == "paper-sign" else 5.0
        z = np.clip((self._matrix(texts) - self.mean) / self.sd, -clip, clip)
        return (z @ self.coef + self.intercept).tolist()


VARIANTS = {
    "lr": lambda: Detector("lr"),
    "lr-nolayout": lambda: Detector("lr-nolayout"),
    "paper-sign": lambda: Detector("paper-sign"),
}
