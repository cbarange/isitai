"""Reference implementation of the light text score: normalisation, language guess,
features. The Rust port (crates/isitai-core/src/score.rs) must give the same numbers;
`train.py` writes the parity fixture that `cargo test` checks.

Portability rules, so that Python and Rust cannot drift:
- no `str.isalpha`, `str.isspace`, `str.split()` without argument, no `unicodedata`, no
  regular expression: character classes are the explicit tables below;
- lower-casing is done one character at a time;
- lengths are counted in characters (code points), never in bytes;
- the n-gram hash is FNV-1a 32 bits over UTF-8 bytes.

Nothing here reads the layout: line breaks become spaces, Markdown markers are removed,
the spaces a tokeniser or French typography puts before punctuation are removed.
"""
from __future__ import annotations

import math

MAX_TOKENS = 1000          # whitespace tokens analysed; the rest of the text is ignored
MAX_CHARS = 200_000        # characters read at most: bounds memory on a text without spaces
BLOCK = 100                # lexical features are averaged over full blocks of 100 words
HASH_BITS = 12
HASH_NGRAM = (3, 4, 5)
HASH_CHARS = 3000

WHITESPACE = frozenset(
    "\t\n\x0b\x0c\r \x85\xa0          "
    "      　")
ZERO_WIDTH = frozenset("​‌‍⁠﻿­")
MARKDOWN = frozenset("*#`|~_")
CHAR_MAP = {
    "‘": "'", "’": "'", "‚": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "–": "—", "―": "—", "−": "-",
}
GLUE_BEFORE = frozenset(",.;:!?)]…")
GLUE_AFTER = frozenset("([")
CLITICS = frozenset(("n't", "'s", "'re", "'ve", "'m", "'ll", "'d"))
BULLETS = frozenset("-*+•")
SENTENCE_END = frozenset(".!?…")
CLOSERS = frozenset("\"')]")

# (first, last, script) code point ranges that count as letters.
LETTER_RANGES = (
    (0x41, 0x5A, "latin"), (0x61, 0x7A, "latin"), (0xAA, 0xAA, "latin"),
    (0xB5, 0xB5, "latin"), (0xBA, 0xBA, "latin"), (0xC0, 0xD6, "latin"),
    (0xD8, 0xF6, "latin"), (0xF8, 0x2AF, "latin"), (0x370, 0x373, "greek"),
    (0x376, 0x377, "greek"), (0x37B, 0x37D, "greek"), (0x386, 0x386, "greek"),
    (0x388, 0x3FF, "greek"), (0x400, 0x481, "cyrillic"), (0x48A, 0x52F, "cyrillic"),
    (0x531, 0x556, "armenian"), (0x561, 0x587, "armenian"), (0x5D0, 0x5EA, "hebrew"),
    (0x620, 0x64A, "arabic"), (0x66E, 0x6D3, "arabic"), (0x900, 0x97F, "devanagari"),
    (0xE01, 0xE4E, "thai"), (0x1E00, 0x1EFF, "latin"), (0x1F00, 0x1FFF, "greek"),
    (0x3041, 0x3096, "kana"), (0x30A1, 0x30FA, "kana"), (0x3400, 0x4DBF, "han"),
    (0x4E00, 0x9FFF, "han"), (0xAC00, 0xD7A3, "hangul"), (0xFF21, 0xFF3A, "latin"),
    (0xFF41, 0xFF5A, "latin"),
)
SCRIPTS = ("latin", "greek", "cyrillic", "armenian", "hebrew", "arabic", "devanagari",
           "thai", "kana", "han", "hangul")

# Very frequent function words, used only to name the language of a Latin-script text.
STOPWORDS = {
    "en": "the of and to in is that it for was with as on be by this are from at have",
    "fr": "le la les de des du et un une est en que qui dans pour pas au sur ce il",
    "de": "der die das und ist nicht ein eine zu den mit von auf dem für sich des im auch",
    "es": "el la los las de que y en un una es por con no para del se al lo su",
    "it": "il la di che e un una per non è in del della con le sono si da i gli",
    "pt": "o a os as de que e do da em um uma para não com por se dos na no",
    "nl": "de het een en van is dat op te in niet zijn met voor er aan ook als bij",
    "pl": "w i na z do nie się to jest że o jak po przez od dla za są ale tym",
    "ro": "și de la în a un o cu nu este pe care să din mai pentru se au fost",
    "tr": "ve bir bu için ile de da çok daha olarak en gibi ama ne var kadar olan her",
}
STOPWORD_SETS = {lang: frozenset(words.split(" ")) for lang, words in STOPWORDS.items()}
LANG_MIN_SHARE = 0.10      # share of the words that must be function words of the language
LANG_MIN_MARGIN = 1.25     # ratio to the second language

PUNCT = (
    ("p_comma", ","), ("p_period", "."), ("p_semicolon", ";"), ("p_colon", ":"),
    ("p_exclam", "!"), ("p_question", "?"), ("p_dash", "—"), ("p_hyphen", "-"),
    ("p_dquote", '"'), ("p_squote", "'"), ("p_paren", "()[]"), ("p_ellipsis", "…"),
    ("p_slash", "/"), ("p_other", "&%$@+=<>^"),
)

GROUPS = {
    "sent": ("sent_len_mean", "sent_len_sd", "sent_len_cv", "sent_len_adjdiff",
             "sent_short_frac", "sent_long_frac", "sent_question_frac", "sent_exclam_frac",
             "sent_opener_repeat"),
    "word": ("word_len_mean", "word_len_sd", "word_long_frac", "word_short_frac"),
    "div": ("ttr_block", "hapax_block", "mattr_20", "mattr_50"),
    "rep": ("rep_bigram_block", "top_word_block"),
    "punct": tuple(name for name, _ in PUNCT),
    "case": ("digit_ratio", "upper_ratio", "titlecase_frac", "allcaps_frac",
             "sent_lower_start_frac"),
    "char": ("char_entropy",),
    "rhet": ("rhet_pivot_pair", "rhet_not_x_but_y", "rhet_triptych"),
}
SCALAR_FEATURES = tuple(name for group in GROUPS.values() for name in group)


# ------------------------------------------------------------------ characters

def letter_script(ch: str):
    """Script of a letter, or None when the character is not a letter."""
    cp = ord(ch)
    for first, last, script in LETTER_RANGES:
        if first <= cp <= last:
            return script
    return None


def lower_char(ch: str) -> str:
    return ch.lower()


def is_upper(ch: str) -> bool:
    return lower_char(ch) != ch


def split_whitespace(text: str) -> list:
    out, current = [], []
    for ch in text:
        if ch in WHITESPACE:
            if current:
                out.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        out.append("".join(current))
    return out


# ------------------------------------------------------------------ normalisation

def clean_line(line: str) -> str:
    """One line without its Markdown prefix (quote, heading, bullet) and markers."""
    chars = list(line)
    i = 0
    while i < len(chars) and (chars[i] in WHITESPACE or chars[i] == ">"):
        i += 1
    if i + 1 < len(chars) and chars[i] in BULLETS and chars[i + 1] in WHITESPACE:
        i += 1
    out = []
    for ch in chars[i:]:
        if ch in ZERO_WIDTH or ch in MARKDOWN:
            continue
        out.append(CHAR_MAP.get(ch, ch))
    return "".join(out)


def is_citation(token: str) -> bool:
    """`[12]`, `[12].`: a reference mark left by a search assistant."""
    core = token.rstrip(".,;:")
    if len(core) < 3 or core[0] != "[" or core[-1] != "]":
        return False
    return all("0" <= ch <= "9" for ch in core[1:-1])


def is_link(token: str) -> bool:
    return "://" in token or token.startswith("www.")


def normalize(text: str) -> list:
    """Tokens of the text, layout and markup removed, at most MAX_TOKENS of them."""
    tokens = []
    for line in text[:MAX_CHARS].replace("\r", "\n").split("\n"):
        for token in split_whitespace(clean_line(line)):
            if is_link(token) or is_citation(token):
                continue
            glue = bool(tokens) and (token[0] in GLUE_BEFORE or token in CLITICS
                                     or tokens[-1][-1] in GLUE_AFTER)
            if glue:
                tokens[-1] += token
            else:
                if len(tokens) == MAX_TOKENS:
                    return tokens
                tokens.append(token)
    return tokens


def words_of(token: str) -> list:
    """Lower-cased words of a token: runs of letters, joined by an inner ' or -."""
    out, current = [], []
    chars = list(token)
    for i, ch in enumerate(chars):
        if letter_script(ch) is not None:
            current.append(lower_char(ch))
        elif (ch in "'-" and current and i + 1 < len(chars)
              and letter_script(chars[i + 1]) is not None):
            current.append(ch)
        elif current:
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return out


def ends_sentence(token: str) -> bool:
    i = len(token)
    while i > 0 and token[i - 1] in CLOSERS:
        i -= 1
    return i > 0 and token[i - 1] in SENTENCE_END


def first_letter(token: str):
    for ch in token:
        if letter_script(ch) is not None:
            return ch
    return None


# ------------------------------------------------------------------ language

def script_shares(tokens: list) -> dict:
    counts = {s: 0 for s in SCRIPTS}
    total = 0
    for token in tokens:
        for ch in token:
            s = letter_script(ch)
            if s is not None:
                counts[s] += 1
                total += 1
    return {s: (counts[s] / total if total else 0.0) for s in SCRIPTS}


def detect_language(tokens: list, words: list) -> str:
    """ISO 639-1 code for ten Latin-script languages, a script name for the other
    scripts, or `unknown`. A guess from function words, not a language identifier."""
    shares = script_shares(tokens)
    best_script = "latin"
    for s in SCRIPTS:
        if shares[s] > shares[best_script]:
            best_script = s
    if shares[best_script] == 0.0:
        return "unknown"
    if best_script != "latin":
        if best_script == "han" and shares["kana"] > 0.05:
            return "kana"
        return best_script
    if not words:
        return "unknown"
    scored = []
    for lang in sorted(STOPWORD_SETS):
        hits = sum(1 for w in words if w in STOPWORD_SETS[lang])
        scored.append((hits / len(words), lang))
    scored.sort(key=lambda t: (-t[0], t[1]))
    (best, lang), (second, _) = scored[0], scored[1]
    if best < LANG_MIN_SHARE or best < LANG_MIN_MARGIN * second:
        return "unknown"
    return lang


# ------------------------------------------------------------------ rhetoric (port of rhetoric.rs)

ASCII_WS = frozenset(" \t\n\x0c\r")
CONTRAST = ("mais", "or", "toutefois", "cependant", "néanmoins", "pourtant", "en réalité",
            "en fait", "au contraire", "but", "yet", "however", "in reality", "in fact")


def rhetoric_counts(raw: str) -> tuple:
    """(sentences, pivot pairs, not-x-but-y, triptychs) as crates/isitai-core/src/rhetoric.rs
    counts them, on the raw text. Measurement only: see README, the features were dropped."""
    sents, start, i, n = [], 0, 0, len(raw)

    def push(s, e):
        while s < e and raw[s] in ASCII_WS:
            s += 1
        while e > s and raw[e - 1] in ASCII_WS:
            e -= 1
        if e - s >= 2:
            sents.append(raw[s:e])

    while i < n:
        if raw[i] in ".!?":
            j = i + 1
            while j < n and raw[j] in ASCII_WS:
                j += 1
            push(start, i + 1)
            start = j
            i = j
            continue
        i += 1
    if start < n:
        push(start, n)
    pivot = notx = trip = 0
    lows = [s.lower() for s in sents]
    for s, low in zip(sents, lows):
        neg = next((low.find(p) for p in ("ce n'est pas", "ce n’est pas", "il ne s'agit pas",
                                           "it is not") if low.find(p) >= 0), -1)
        if neg >= 0:
            con = next((low.find(p, neg) for p in ("c'est", "il s'agit de", "it is", "but it is")
                        if low.find(p, neg) >= 0), -1)
            if con > neg and "," in low[neg:con]:
                notx += 1
        body = s.rstrip(".!? ")
        parts = body.split(", ")
        if len(parts) == 2:
            tail = parts[1].split(" et ")
            if len(tail) == 2 and all(0 < len(item.split()) <= 4
                                      for item in (parts[0], tail[0], tail[1])):
                trip += 1
    for a, b in zip(lows, lows[1:]):
        negates = (("ne " in a or "n'" in a) and "pas" in a) or " no " in a
        opens = any(b.startswith(c) and (len(b) == len(c) or not b[len(c)].isalnum())
                    for c in CONTRAST)
        if negates and opens:
            pivot += 1
    return len(sents), pivot, notx, trip


# ------------------------------------------------------------------ features

def mean_sd(values: list) -> tuple:
    if not values:
        return 0.0, 0.0
    m = sum(values) / len(values)
    return m, math.sqrt(sum((v - m) ** 2 for v in values) / len(values))


def mattr(words: list, window: int) -> float:
    """Moving-average type-token ratio (Covington & McFall 2010)."""
    n = len(words)
    if n == 0:
        return 1.0
    if n < window:
        return len(set(words)) / n
    counts = {}
    for w in words[:window]:
        counts[w] = counts.get(w, 0) + 1
    total = len(counts)
    for i in range(window, n):
        out = words[i - window]
        counts[out] -= 1
        if counts[out] == 0:
            del counts[out]
        counts[words[i]] = counts.get(words[i], 0) + 1
        total += len(counts)
    return total / (n - window + 1) / window


def block_features(words: list) -> tuple:
    """(type-token ratio, hapax share, repeated bigram share, top word share), each the
    mean over the full blocks of BLOCK words; a text shorter than a block is one block."""
    n = len(words)
    if n == 0:
        return 1.0, 1.0, 0.0, 0.0
    blocks = [words[i:i + BLOCK] for i in range(0, n - BLOCK + 1, BLOCK)] or [words]
    ttr = hapax = rep = top = 0.0
    for block in blocks:
        counts = {}
        for w in block:
            counts[w] = counts.get(w, 0) + 1
        size = len(block)
        ttr += len(counts) / size
        hapax += sum(1 for c in counts.values() if c == 1) / size
        top += max(counts.values()) / size
        if size > 1:
            bigrams = set(zip(block, block[1:]))
            rep += 1.0 - len(bigrams) / (size - 1)
    k = len(blocks)
    return ttr / k, hapax / k, rep / k, top / k


def char_entropy(text: str) -> float:
    counts = {}
    n = 0
    for ch in text:
        if n == 2000:
            break
        ch = lower_char(ch)
        counts[ch] = counts.get(ch, 0) + 1
        n += 1
    if n == 0:
        return 0.0
    return -sum(c / n * math.log2(c / n) for c in counts.values())


def fnv1a(data: bytes) -> int:
    h = 0x811C9DC5
    for b in data:
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h


def hashed_ngrams(text: str) -> list:
    """L2-normalised counts of lower-cased character 3- to 5-grams in 2^HASH_BITS buckets."""
    chars = [lower_char(ch) for ch in text[:HASH_CHARS]]
    chars = [c for piece in chars for c in piece]
    vec = [0.0] * (1 << HASH_BITS)
    mask = (1 << HASH_BITS) - 1
    for n in HASH_NGRAM:
        for i in range(len(chars) - n + 1):
            vec[fnv1a("".join(chars[i:i + n]).encode("utf-8")) & mask] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec] if norm > 0 else vec


def analyse(raw: str, with_hash: bool = False, with_rhetoric: bool = True) -> dict:
    """Everything the score needs from one text: word count, language, features."""
    tokens = normalize(raw)
    text = " ".join(tokens)
    words, sent_lens, openers, lower_starts = [], [], [], 0
    current, opener, start_letter = 0, None, None
    n_title = n_allcaps = 0
    for token in tokens:
        token_words = words_of(token)
        if token_words:
            if opener is None:
                opener = token_words[0]
                start_letter = first_letter(token)
            letters = [ch for ch in token if letter_script(ch) is not None]
            if is_upper(letters[0]):
                n_title += 1
                if len(letters) > 1 and all(is_upper(ch) for ch in letters):
                    n_allcaps += 1
        current += len(token_words)
        words.extend(token_words)
        if ends_sentence(token) and current > 0:
            sent_lens.append(current)
            openers.append(opener)
            lower_starts += 0 if is_upper(start_letter) else 1
            current, opener, start_letter = 0, None, None
    if current > 0:
        sent_lens.append(current)
        openers.append(opener)
        lower_starts += 0 if is_upper(start_letter) else 1

    nw = max(1, len(words))
    ns = max(1, len(sent_lens))
    f = {}
    m, sd = mean_sd(sent_lens)
    f["sent_len_mean"] = min(m, 100.0)
    f["sent_len_sd"] = min(sd, 100.0)
    f["sent_len_cv"] = sd / m if m > 0 else 0.0
    if len(sent_lens) > 1 and m > 0:
        f["sent_len_adjdiff"] = (sum(abs(a - b) for a, b in zip(sent_lens, sent_lens[1:]))
                                 / (len(sent_lens) - 1) / m)
    else:
        f["sent_len_adjdiff"] = 0.0
    f["sent_short_frac"] = sum(1 for v in sent_lens if v <= 5) / ns
    f["sent_long_frac"] = sum(1 for v in sent_lens if v >= 30) / ns
    f["sent_question_frac"] = min(1.0, text.count("?") / ns)
    f["sent_exclam_frac"] = min(1.0, text.count("!") / ns)
    if len(openers) > 1:
        f["sent_opener_repeat"] = (sum(1 for a, b in zip(openers, openers[1:]) if a == b)
                                   / (len(openers) - 1))
    else:
        f["sent_opener_repeat"] = 0.0
    f["sent_lower_start_frac"] = lower_starts / ns

    lens = [sum(1 for _ in w) for w in words]
    m_w, sd_w = mean_sd(lens)
    f["word_len_mean"] = m_w
    f["word_len_sd"] = sd_w
    f["word_long_frac"] = sum(1 for v in lens if v >= 7) / nw
    f["word_short_frac"] = sum(1 for v in lens if v <= 3) / nw

    f["ttr_block"], f["hapax_block"], f["rep_bigram_block"], f["top_word_block"] = \
        block_features(words)
    f["mattr_20"] = mattr(words, 20)
    f["mattr_50"] = mattr(words, 50)

    per100 = 100.0 / nw
    for name, chars in PUNCT:
        f[name] = min(100.0, sum(text.count(ch) for ch in chars) * per100)
    n_letters = n_upper = n_digit = n_chars = 0
    for ch in text:
        n_chars += 1
        if letter_script(ch) is not None:
            n_letters += 1
            if is_upper(ch):
                n_upper += 1
        elif "0" <= ch <= "9":
            n_digit += 1
    f["digit_ratio"] = n_digit / max(1, n_chars)
    f["upper_ratio"] = n_upper / max(1, n_letters)
    f["titlecase_frac"] = n_title / nw
    f["allcaps_frac"] = n_allcaps / nw
    f["char_entropy"] = char_entropy(text)

    if with_rhetoric:
        n_sent, pivot, notx, trip = rhetoric_counts(raw)
        per = 1.0 / max(1, n_sent)
        f["rhet_pivot_pair"] = pivot * per
        f["rhet_not_x_but_y"] = notx * per
        f["rhet_triptych"] = trip * per
    out = {"n_words": len(words), "language": detect_language(tokens, words), "features": f}
    if with_hash:
        out["hash"] = hashed_ngrams(text)
    return out
