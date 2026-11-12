"""Perplexity under text shuffling, after Luminol-AIDetect (La Cava and Tagarelli,
"Luminol-AIDetect: Fast Zero-shot Machine-Generated Text Detection based on Perplexity
under Text Shuffling", arXiv 2604.25860v2, 2026).

THIS IS A REIMPLEMENTATION FROM THE PAPER. No official code or fitted distribution
repository was public on 2026-11-12 (the paper says both will be released); nothing here
was checked against the authors' implementation.

Idea of the paper: shuffle the sentences of a text, score the text and its shuffled
version with a small causal LM, and look at how the perplexity moves. The claim is that
machine text loses more (larger shuffled-minus-original perplexity) than human text.

  run.py --algo shuffle_ppl --variant gpt2-logratio --split test
  run.py --algo shuffle_ppl --variant smollm2-360m-density --split all

Variants: `<lm>-<kind>[-avg3]`, <lm> in {gpt2, smollm2-360m}.
  logratio   log(ppl_shuf) - log(ppl), raw. Zero-shot statistic; only its SIGN is chosen
             on the train split (the paper's a-priori sign is +, "shuffling hurts machine
             text more"; the fit artefact records whether train kept or flipped it).
  diff       ppl_shuf - ppl, raw, sign chosen on train in the same way.
  lr         StandardScaler + LogisticRegression (C=1, lbfgs, random_state=0) on the five
             perplexity features sum, diff, ratio, log-ratio, percent change, each passed
             through sign(z) * log(1 + |z|) and clipped to the 1st-99th percentile of the
             fit data. A stand-in, not in the paper. (On the raw features the regression
             was dominated by the heavy right tail of perplexity: fit-data AUROC 0.57 with
             GPT-2, below plain perplexity. The transform was chosen on the fit data.)
  density    the paper's Phase 3-4: per feature and per class a fitted density (Gamma for
             every feature, Burr XII also tried for sum and ratio), implausibility check,
             per-feature probability pdf_M / (pdf_M + pdf_H). See deviations.
  ref-loglik minus log(ppl) of the ORIGINAL text only (sign a priori, no shuffling,
             ONE forward pass). A reference: `sum` is mostly plain perplexity, so `lr` and
             `density` can score well without any shuffling signal. Compare them to this.
  -avg3      the features are averaged over 3 shuffles with different seeds (4 forward
             passes instead of 2). Without the suffix: one shuffle (seed index 0), which
             is the paper's procedure.
Every variant has NEEDS_TRAINING = True (even the zero-shot ones, for the sign) except
ref-loglik.

Models (pinned revisions, HF_HOME cache, CPU fp32):
  gpt2          openai-community/gpt2 @ 607a30d, 124M parameters, model.safetensors
                548 MB, MIT. English model.
  smollm2-360m  HuggingFaceTB/SmolLM2-360M @ f8027fd, 362M parameters, model.safetensors
                724 MB, Apache-2.0 (Hub model card, as recorded by telescope.py; the
                cached snapshot holds no README). Mostly English training data.

Deviations from the paper:
  - Proxy LM. The paper's default is GPT-Neo-2.7B (about 10 GB fp32), too heavy for a CPU
    library. The paper itself reports GPT-2 as a weaker proxy (Appendix H.2: degraded on
    attacked and multilingual text: FNR .123 against .094 under attacks, .137
    against .087 on MULTITuDE, and a "+0.061" FPR increase, as read in the PDF). SmolLM2-360M
    is not in the paper.
  - Truncation. The text is cut to its first 511 tokens of the LM's tokenizer BEFORE
    shuffling (512 positions with BOS), so the two versions hold the same sentences. The
    paper does not state a limit. A 1,500-word story is scored on its first quarter to
    third. A sentence cut by the limit stays as a (truncated) last sentence.
  - BOS is prepended so the first token is scored; the paper does not say.
  - Both versions are rebuilt the same way: sentences joined by one space, paragraph
    separators kept as found. The "original" is therefore the text with white space
    between sentences normalised, so that order is the only difference (the identity
    permutation gives a log-ratio of exactly 0).
  - Paragraphs end at a blank line, or at a line break that follows sentence-final
    punctuation, a colon or a semicolon; any other line break is a hard wrap and becomes
    a space. The paper does not define the delimiter. (A first version took every line
    as a paragraph when the text had no blank line: the human abstracts of RAID are
    hard-wrapped at about 80 columns, so sentence fragments were swapped inside lines for
    human texts only, an artefact that gave abstracts a log-ratio AUROC of 0.05.)
  - Sentence splitter: ours (regex), see `split_sentences`. Handles French spaces before
    ? ! and guillemets. The paper does not name its splitter.
  - Word shuffling. The paper is ambiguous: its formal rule shuffles the words of every
    single-sentence paragraph, its prose says words are shuffled only for single-sentence
    texts. Here: if at least one paragraph has 2+ sentences, sentences are shuffled inside
    those paragraphs and single-sentence paragraphs are left alone; otherwise (a
    one-sentence text, or only single-sentence paragraphs such as verse) the words of each
    paragraph are shuffled and its terminal punctuation is kept in place.
  - Non-identity permutations. The paper draws a uniform permutation, which is the
    identity with probability 1/n! (1/2 for two sentences): no signal at all. Here the
    draw is repeated until the order changes (up to 20 tries). A text where nothing can
    move (fewer than 2 words) has all shuffle features at their neutral value.
  - Seeds: the permutation is seeded by SHA-256(text, seed index), so a score does not
    depend on the process or on the other texts of the call.
  - No domain at inference. The paper fits one distribution repository per RAID domain
    and needs the domain of the query text. `score()` receives only the text, so the
    densities are POOLED over the train domains.
  - Fit data. The paper fits on RAID GPT-3 text only (80% of each domain). Here: a seeded
    subset of the train split (FIT_N rows, half human, all 8 train generators).
  - Family selection: lowest Kolmogorov-Smirnov statistic between Gamma and Burr XII
    (free `loc`, because diff, log-ratio and percent change can be negative). The paper
    uses a bootstrap KS p-value over 11 families.
  - IQR outlier removal (paper, Appendix A) is applied to the fit data of each feature
    and class before fitting; the paper enables it per domain by grid search on test
    data, which is not done here.
  - Implausibility check as in the paper (Eq. 4, tau = min over classes of the 1st
    percentile of the fitted pdf on the fit data). The paper then takes a MAJORITY VOTE
    over features and rejects when no feature is left. A vote has at most 6 values, which
    is useless for AUROC and low-FPR thresholds, so the score is the MEAN of the
    per-feature probabilities (the paper's `ensemble_probs`), and 0.5 on reject. The
    uncertainty threshold Upsilon is 0.
  - Per-paragraph log-ratios (`explain`) are not in the paper. They come from the same
    two forward passes: mean token surprisal of the paragraph's tokens in the shuffled
    text minus the same in the original, both in full-document context.

What the fit data showed (400 train rows, pooled domains, one shuffle; details in
CACHE_DIR/shuffle_ppl/fit.<variant>.json). The raw log-ratio separates the classes
weakly: AUROC 0.552 with GPT-2 and 0.557 with SmolLM2-360M for the paper's + sign (kept),
0.53 and 0.54 on sentence-mode texts only. Per domain it ranges from 0.44 (books,
recipes) to 0.72 (news, abstracts) with GPT-2. Minus log-perplexity alone gives 0.77 on
the same rows, and `diff` gets its sign (-) from perplexity, not from shuffling: `lr`
and `density` score mostly through `sum`. Averaging 3 shuffles does not change the
log-ratio (seed-to-seed correlation 0.99, AUROC 0.547 against 0.552 with GPT-2).
Word-mode log-ratios (about 3) are on another scale than sentence-mode ones (about 0.1).
The classes also differ in layout in RAID (blank lines in most AI texts, in almost no
human text), so the number of sentences a shuffle can move differs by class.

No French number exists for the method: MULTITuDE (the paper's multilingual set) has no
French. test_fr results are ours and unverified against any publication.

Cost: 2 forward passes per text (4 for -avg3), each over at most 512 positions, texts one
by one without padding. Fit features (never test scores) are cached once per LM under
CACHE_DIR/shuffle_ppl. Deterministic: CPU, fp32, eval mode, fixed seeds.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import warnings

import numpy as np

from common import CACHE_DIR, THREADS

NAME = "shuffle_ppl"
NEEDS_TRAINING = True
BATCH_SIZE = 16

MAX_TOKENS = 511        # scored tokens of the original text; 512 positions with BOS
N_SEEDS = 3             # shuffles of the -avg3 variants
FIT_N = 400             # rows of the train split used for fitting (half human, half AI)
_FIT_SEED = "shuffle_ppl-fit-v1"
_LOGPPL_MAX = 20.0      # clamp of log-perplexity, keeps exp() finite
_VERSION = 3            # bump when the shuffling or the features change (cache key)
FEATURES = ("sum", "diff", "ratio", "logratio", "change")
_BURR_FEATURES = ("sum", "ratio")
_ALPHA = 0.01

_MODELS = {
    "gpt2": ("openai-community/gpt2", "607a30d783dfa663caf39e06633721c8d4cfcd7e",
             "openai-community/gpt2 (124M parameters, model.safetensors 548 MB, MIT)"),
    "smollm2-360m": ("HuggingFaceTB/SmolLM2-360M", "f8027fd0eaeea54caa13c31d31b9fdc459c38b49",
                     "HuggingFaceTB/SmolLM2-360M (362M parameters, model.safetensors 724 MB, "
                     "Apache-2.0)"),
}
MODEL = ("reimplementation of Luminol-AIDetect (arXiv 2604.25860) with a small proxy LM: "
         + _MODELS["gpt2"][2] + " or " + _MODELS["smollm2-360m"][2]
         + "; pretrained LMs, not trained on any detection corpus")

_ART_DIR = os.path.join(CACHE_DIR, "shuffle_ppl")
_loaded: dict = {}


# ----------------------------------------------------------------------------- text ----

_NBSP = "\u00a0\u202f\u2009"
_CLOSERS = "»”\"’')\\]"
# A sentence end: terminator(s), optional closing quotes or brackets (a French closing
# guillemet may be preceded by a space), then white space. The space before a French
# ? or ! sits inside the sentence, so it never splits. `;` and `:` are not sentence ends.
_SENT_END = re.compile(r"([.!?…]+)((?:[ " + _NBSP + r"]?[" + _CLOSERS + r"])*)(\s+)(?=\S)")
_ABBREV = {
    "m", "mm", "mme", "mmes", "mlle", "mlles", "dr", "pr", "me", "st", "ste", "cf", "vs",
    "mr", "mrs", "ms", "prof", "sr", "jr", "no", "vol", "fig", "art", "p", "pp", "ex",
    "env", "av", "bd", "tél", "tel", "e.g", "i.e", "c.-à-d", "approx", "inc", "ltd", "co",
}
_LAST_WORD = re.compile(r"([^\s" + _NBSP + r"]+)$")
_PARA_BREAK = re.compile(r"\n[ \t\r\f\v]*\n\s*|(?<=[.!?…:;" + _CLOSERS + r"])[ \t]*\n\s*")
_WRAP = re.compile(r"\s*\n\s*")
_TERMINAL = re.compile(r"^(.*?)([.!?…]+[" + _CLOSERS + r"]*)$", re.S)


def split_sentences(par: str) -> list[str]:
    """Sentences of one paragraph, stripped. Rules: split after . ! ? … (and closing
    quotes) followed by white space; not after a known abbreviation or a single-letter
    initial; not when a closing quote follows the terminator and the next word starts in
    lower case (`« Bonjour ! » dit-il.` is one sentence)."""
    par = par.strip()
    out, start = [], 0
    for m in _SENT_END.finditer(par):
        term, closers = m.group(1), m.group(2)
        nxt = par[m.end()] if m.end() < len(par) else ""
        if closers and nxt.islower():
            continue
        if term == ".":
            w = _LAST_WORD.search(par[start:m.start()])
            raw_word = (w.group(1) if w else "").lstrip("«“\"'([")
            word = raw_word.lower()
            if word in _ABBREV or (len(word) == 1 and raw_word.isupper() and nxt.isupper()):
                continue
            if word.isdigit() and nxt.islower():        # "1. faire revenir" list items
                continue
        s = par[start:m.start() + len(term) + len(closers)].strip()
        if s:
            out.append(s)
        start = m.end()
    tail = par[start:].strip()
    if tail:
        out.append(tail)
    return out


def split_paragraphs(text: str) -> tuple[list[str], list[str]]:
    """(paragraphs, separators), len(separators) == len(paragraphs) - 1. A paragraph ends
    at a blank line, or at a line break that follows sentence-final punctuation, a colon
    or a semicolon. Any other line break is a hard wrap and becomes a space."""
    text = text.strip()
    pars, seps, pos = [], [], 0
    for m in _PARA_BREAK.finditer(text):
        if m.start() <= pos:
            continue
        pars.append(_WRAP.sub(" ", text[pos:m.start()]))
        seps.append("\n\n" if m.group().count("\n") >= 2 else "\n")
        pos = m.end()
    pars.append(_WRAP.sub(" ", text[pos:]))
    return pars, seps


def _rng(text: str, seed: int) -> random.Random:
    h = hashlib.sha256(f"{seed}\x00{text}".encode("utf-8", "surrogatepass")).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


def _permute(items: list, rng: random.Random) -> list:
    """A random order of `items` that differs from the original when one exists."""
    if len(items) < 2:
        return list(items)
    for _ in range(20):
        out = list(items)
        rng.shuffle(out)
        if out != items:
            return out
    return list(items)


def _shuffle_words(par_sents: list[str], rng: random.Random) -> str:
    par = " ".join(par_sents)
    m = _TERMINAL.match(par)
    body, punct = (m.group(1), m.group(2)) if m else (par, "")
    words = body.split()
    return " ".join(_permute(words, rng)) + punct


def build_pair(text: str, seeds: tuple[int, ...] = (0,)) -> dict:
    """The normalised original and its shuffled versions.

    Returns {"orig": str, "shuf": [str per seed], "mode": "sentence" | "word" | "none",
    "spans": [(start, end) of each paragraph in orig], "shuf_spans": [[...] per seed],
    "n_sent": [sentences per paragraph]}. Paragraph order and separators are the same in
    every version, so paragraph i of a shuffled text is paragraph i of the original."""
    pars, seps = split_paragraphs(text)
    sents = [split_sentences(p) for p in pars]
    keep = [i for i, s in enumerate(sents) if s]
    sents = [sents[i] for i in keep]
    seps = [seps[i] if i < len(seps) else "\n" for i in keep][:max(0, len(keep) - 1)]
    mode = "sentence" if any(len(s) > 1 for s in sents) else "word"

    def assemble(par_texts: list[str]) -> tuple[str, list[tuple[int, int]]]:
        buf, spans, pos = [], [], 0
        for i, p in enumerate(par_texts):
            if i:
                buf.append(seps[i - 1])
                pos += len(seps[i - 1])
            buf.append(p)
            spans.append((pos, pos + len(p)))
            pos += len(p)
        return "".join(buf), spans

    orig, spans = assemble([" ".join(s) for s in sents])
    shuf, shuf_spans = [], []
    for seed in seeds:
        rng = _rng(text, seed)
        if mode == "sentence":
            parts = [" ".join(_permute(s, rng)) if len(s) > 1 else " ".join(s) for s in sents]
        else:
            parts = [_shuffle_words(s, rng) for s in sents]
        t, sp = assemble(parts)
        shuf.append(t)
        shuf_spans.append(sp)
    if all(t == orig for t in shuf):
        mode = "none"
    return {"orig": orig, "shuf": shuf, "mode": mode, "spans": spans,
            "shuf_spans": shuf_spans, "n_sent": [len(s) for s in sents]}


# ------------------------------------------------------------------------------- LM ----

def _load(key: str):
    if key not in _loaded:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.set_num_threads(THREADS)
        torch.manual_seed(0)
        repo, rev, _ = _MODELS[key]
        tok = AutoTokenizer.from_pretrained(repo, revision=rev, use_fast=True)
        model = AutoModelForCausalLM.from_pretrained(repo, revision=rev, dtype=torch.float32)
        model.to("cpu").eval()
        bos = tok.bos_token_id if tok.bos_token_id is not None else tok.eos_token_id
        if bos is None:
            raise RuntimeError(f"{repo}: no BOS or EOS token id")
        limit = int(getattr(model.config, "max_position_embeddings", 1024) or 1024)
        _loaded[key] = (tok, model, int(bos), limit)
    return _loaded[key]


def _truncate(key: str, text: str) -> str:
    """The text cut to its first MAX_TOKENS tokens (string level, via offsets)."""
    tok = _load(key)[0]
    e = tok(text, add_special_tokens=False, return_offsets_mapping=True,
            truncation=True, max_length=MAX_TOKENS + 1)
    if len(e["input_ids"]) <= MAX_TOKENS:
        return text
    return text[:e["offset_mapping"][MAX_TOKENS - 1][1]]


def _surprisals(key: str, text: str) -> tuple[np.ndarray, list[int]]:
    """Per-token surprisal (nats, float64) of `text` after BOS, and each token's start
    offset in `text`. Only the observed token's log-probability is read."""
    import torch
    tok, model, bos, limit = _load(key)
    e = tok(text, add_special_tokens=False, return_offsets_mapping=True,
            truncation=True, max_length=min(limit - 1, 2 * MAX_TOKENS))
    ids = e["input_ids"]
    if not ids:
        return np.zeros(0), []
    x = torch.tensor([[bos] + ids], dtype=torch.long, device="cpu")
    with torch.inference_mode():
        logits = model(input_ids=x).logits[0, :-1].float()
        nll = torch.nn.functional.cross_entropy(logits, x[0, 1:], reduction="none")
    return nll.double().numpy(), [o[0] for o in e["offset_mapping"]]


def _logppl(nll: np.ndarray) -> float:
    return float(min(_LOGPPL_MAX, nll.mean())) if len(nll) else 0.0


def _raw(key: str, text: str, n_shuf: int, detail: bool = False) -> dict:
    """log-perplexity of the original and of `n_shuf` shuffles of one text."""
    pair = build_pair(_truncate(key, text), tuple(range(n_shuf)))
    nll_o, off_o = _surprisals(key, pair["orig"])
    lp = _logppl(nll_o)
    lps, shuf_series = [], []
    for t in pair["shuf"]:
        if t == pair["orig"]:
            lps.append(lp)
            shuf_series.append((nll_o, off_o))
            continue
        nll_s, off_s = _surprisals(key, t)
        lps.append(_logppl(nll_s))
        shuf_series.append((nll_s, off_s))
    out = {"lp": lp, "lps": lps, "mode": pair["mode"], "n_tokens": int(len(nll_o))}
    if detail:
        out["pair"] = pair
        out["orig_series"] = (nll_o, off_o)
        out["shuf_series"] = shuf_series
    return out


def features_from(lp: float, lps: list[float]) -> np.ndarray:
    """The five perplexity features of the paper, averaged over the given shuffles.
    Order: FEATURES = sum, diff, ratio, logratio, change (percent)."""
    ppl = math.exp(lp)
    rows = []
    for s in lps:
        ps = math.exp(s)
        rows.append([ppl + ps, ps - ppl, ps / ppl, s - lp, 100.0 * (ps - ppl) / ppl])
    return np.mean(np.asarray(rows, dtype=float), axis=0)


def explain(texts: list[str], lm: str = "gpt2", seed: int = 0) -> list[dict]:
    """Per-paragraph log-ratios, to inspect mixed human / AI texts. For each text:
    {"mode", "logratio", "ppl", "ppl_shuf", "paragraphs": [{"index", "n_sentences",
    "n_tokens", "logratio", "head"}]}. A paragraph's log-ratio is its mean token
    surprisal in the shuffled text minus the same in the original (0 = order does not
    matter to the LM). A single-sentence paragraph in sentence mode is not shuffled: its
    value only reflects the changed context before it. Not part of the paper."""
    out = []
    for text in texts:
        cut = _truncate(lm, text)
        pair = build_pair(cut, (seed,))
        nll_o, off_o = _surprisals(lm, pair["orig"])
        nll_s, off_s = _surprisals(lm, pair["shuf"][0])
        lp, ls = _logppl(nll_o), _logppl(nll_s)

        def per_par(nll, offs, spans):
            res = []
            offs = np.asarray(offs, dtype=int)
            for a, b in spans:
                m = (offs >= a) & (offs < b) if len(offs) else np.zeros(0, bool)
                res.append((float(nll[m].mean()) if m.any() else float("nan"), int(m.sum())))
            return res

        po = per_par(nll_o, off_o, pair["spans"])
        ps = per_par(nll_s, off_s, pair["shuf_spans"][0])
        pars = []
        for i, ((a, b), (mo, no), (ms, _)) in enumerate(zip(pair["spans"], po, ps)):
            pars.append({"index": i, "n_sentences": pair["n_sent"][i], "n_tokens": no,
                         "logratio": None if (math.isnan(mo) or math.isnan(ms)) else ms - mo,
                         "head": pair["orig"][a:b][:60]})
        out.append({"mode": pair["mode"], "logratio": ls - lp, "ppl": math.exp(lp),
                    "ppl_shuf": math.exp(ls), "paragraphs": pars})
    return out


# ------------------------------------------------------------------------------ fit ----

def _fit_subset(rows: list[dict]) -> list[dict]:
    def k(r):
        return hashlib.sha1(f"{_FIT_SEED}\x00{r['id']}".encode()).hexdigest()
    picked = []
    for label in (0, 1):
        cls = sorted((r for r in rows if r["label"] == label), key=k)
        picked += cls[:FIT_N // 2]
    return sorted(picked, key=k)


def _atomic_json(path: str, obj) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def train_raw(key: str, rows: list[dict]) -> list[dict]:
    """lp / lps (N_SEEDS shuffles) of the fit subset of the train split, cached on disk.
    The cache holds train rows only and is keyed by LM revision, limits and row ids."""
    sub = _fit_subset(rows)
    sig = hashlib.sha256(json.dumps(
        [_VERSION, _MODELS[key][1], MAX_TOKENS, N_SEEDS, FIT_N, _FIT_SEED,
         [r["id"] for r in sub]]).encode()).hexdigest()[:16]
    path = os.path.join(_ART_DIR, f"train_raw.{key}.{sig}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    out = []
    for r in sub:
        raw = _raw(key, r["text"], N_SEEDS)
        out.append({"id": r["id"], "label": r["label"], "domain": r.get("domain"),
                    "generator": r.get("generator"), "lp": raw["lp"], "lps": raw["lps"],
                    "mode": raw["mode"], "n_tokens": raw["n_tokens"]})
    _atomic_json(path, out)
    return out


def _auroc(scores: np.ndarray, y: np.ndarray) -> float:
    from scipy.stats import rankdata
    r = rankdata(scores)
    n1 = int(y.sum())
    n0 = len(y) - n1
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n0 * n1))


def _iqr_keep(v: np.ndarray) -> np.ndarray:
    q1, q3 = np.percentile(v, [25, 75])
    w = 1.5 * (q3 - q1)
    return v[(v >= q1 - w) & (v <= q3 + w)]


def _fit_density(v: np.ndarray, families: list[str]) -> dict:
    """Best of `families` on v by the KS statistic. Returns {"family", "params", "ks"}."""
    from scipy import stats
    best = None
    for fam in families:
        dist = getattr(stats, fam)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                params = dist.fit(v)
                ks = float(stats.kstest(v, fam, args=params).statistic)
        except Exception:
            continue
        if not all(np.isfinite(params)) or not np.isfinite(ks):
            continue
        if best is None or ks < best["ks"]:
            best = {"family": fam, "params": [float(p) for p in params], "ks": ks}
    if best is None:                       # last resort: a normal always fits
        params = stats.norm.fit(v)
        best = {"family": "norm", "params": [float(p) for p in params],
                "ks": float(stats.kstest(v, "norm", args=params).statistic)}
    return best


def _slog(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.log1p(np.abs(x))


def _pdf(d: dict, z) -> np.ndarray:
    from scipy import stats
    with np.errstate(all="ignore"):
        p = getattr(stats, d["family"]).pdf(np.asarray(z, dtype=float), *d["params"])
    return np.nan_to_num(p, nan=0.0, posinf=0.0, neginf=0.0)


class Detector:
    NEEDS_TRAINING = True
    BATCH_SIZE = BATCH_SIZE

    def __init__(self, lm: str, kind: str, n_shuf: int = 1):
        self.lm, self.kind, self.n_shuf = lm, kind, n_shuf
        self.variant = f"{lm}-{kind}" + ("-avg3" if n_shuf > 1 else "")
        self.NAME = f"shuffle_ppl.{self.variant}"
        self.NEEDS_TRAINING = kind != "ref-loglik"
        if kind == "ref-loglik":
            self.n_shuf = n_shuf = 0           # one forward pass, no shuffled text
        passes = 1 + n_shuf
        self.MODEL = (f"{_MODELS[lm][2]}; Luminol-AIDetect reimplementation (arXiv "
                      f"2604.25860, no official code), {passes} forward passes per text, "
                      f"first {MAX_TOKENS} tokens; pretrained LM, "
                      + ("no fitting" if kind == "ref-loglik" else
                         f"{kind} fitted on {FIT_N} rows of the train split"))
        self.state: dict = {}

    # -- features of new texts
    def _feats(self, texts: list[str]) -> tuple[np.ndarray, np.ndarray]:
        f, lp = [], []
        for t in texts:
            raw = _raw(self.lm, t, self.n_shuf)
            f.append(features_from(raw["lp"], raw["lps"]) if raw["lps"]
                     else np.zeros(len(FEATURES)))
            lp.append(raw["lp"])
        return np.asarray(f, dtype=float).reshape(len(texts), len(FEATURES)), np.asarray(lp)

    def fit(self, rows: list[dict]) -> None:
        raw = train_raw(self.lm, rows)
        x = np.asarray([features_from(r["lp"], r["lps"][:self.n_shuf]) for r in raw])
        y = np.asarray([r["label"] for r in raw], dtype=int)
        info = {"variant": self.variant, "n_fit": int(len(y)),
                "zero_signal_rate_fit": float(np.mean([r["mode"] == "none" for r in raw])),
                "word_mode_rate_fit": float(np.mean([r["mode"] == "word" for r in raw])),
                "train_auroc_plus_sign": {f: _auroc(x[:, j], y) for j, f in enumerate(FEATURES)},
                "train_auroc_ref_loglik": _auroc(-np.asarray([r["lp"] for r in raw]), y)}
        # seed-to-seed agreement of the raw log-ratio on the fit rows
        lr_seeds = np.asarray([[s - r["lp"] for s in r["lps"]] for r in raw])
        info["logratio_auroc_per_seed"] = [_auroc(lr_seeds[:, k], y) for k in range(N_SEEDS)]
        info["logratio_auroc_avg3"] = _auroc(lr_seeds.mean(axis=1), y)
        info["logratio_seed_corr"] = np.corrcoef(lr_seeds.T).round(4).tolist()

        if self.kind in ("logratio", "diff"):
            j = FEATURES.index(self.kind)
            auc = info["train_auroc_plus_sign"][self.kind]
            sign = 1.0 if auc >= 0.5 else -1.0
            s = sign * x[:, j]
            h = np.sort(s[y == 0])
            self.state = {"feature": self.kind, "sign": sign, "paper_sign": 1.0,
                          "flipped_vs_paper": sign < 0,
                          "train_threshold_fpr1": float(np.quantile(h, 0.99)),
                          "train_threshold_fpr5": float(np.quantile(h, 0.95))}
        elif self.kind == "lr":
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import make_pipeline
            from sklearn.preprocessing import StandardScaler
            z = _slog(x)
            lo, hi = np.percentile(z, 1, axis=0), np.percentile(z, 99, axis=0)
            self._clip = (lo, hi)
            self._clf = make_pipeline(
                StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, random_state=0)
            ).fit(np.clip(z, lo, hi), y)
            lrm = self._clf[-1]
            self.state = {"transform": "sign(z)*log1p(|z|)", "clip_lo": lo.tolist(), "clip_hi": hi.tolist(),
                          "mean": self._clf[0].mean_.tolist(), "scale": self._clf[0].scale_.tolist(),
                          "coef": dict(zip(FEATURES, lrm.coef_[0].tolist())),
                          "intercept": float(lrm.intercept_[0])}
        elif self.kind == "density":
            repo = {}
            for j, f in enumerate(FEATURES):
                fams = ["gamma"] + (["burr12"] if f in _BURR_FEATURES else [])
                d = {}
                taus = []
                for c, name in ((1, "mgt"), (0, "hgt")):
                    v = _iqr_keep(x[y == c, j])
                    d[name] = _fit_density(v, fams)
                    d[name]["n"] = int(len(v))
                    taus.append(float(np.quantile(_pdf(d[name], v), _ALPHA)))
                d["tau"] = min(taus)
                repo[f] = d
            self.state = {"repo": repo}
        info["state"] = self.state
        _atomic_json(os.path.join(_ART_DIR, f"fit.{self.variant}.json"), info)

    def score(self, texts: list[str]) -> list[float]:
        x, lp = self._feats(texts)
        return self.score_features(x, lp)

    def score_features(self, x: np.ndarray, lp: np.ndarray) -> list[float]:
        """Scores from a feature matrix (columns FEATURES) and the log-perplexities of
        the original texts. `score` is this applied to `_feats(texts)`."""
        if self.kind == "ref-loglik":
            s = -lp
        elif self.kind in ("logratio", "diff"):
            s = self.state["sign"] * x[:, FEATURES.index(self.kind)]
        elif self.kind == "lr":
            s = self._clf.predict_proba(np.clip(_slog(x), *self._clip))[:, 1]
        else:
            probs = np.full((len(x), len(FEATURES)), np.nan)
            for j, f in enumerate(FEATURES):
                d = self.state["repo"][f]
                pm, ph = _pdf(d["mgt"], x[:, j]), _pdf(d["hgt"], x[:, j])
                ok = (np.maximum(pm, ph) >= d["tau"]) & ((pm + ph) > 0)
                probs[ok, j] = pm[ok] / (pm[ok] + ph[ok])
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                s = np.nanmean(probs, axis=1)
            s = np.where(np.isnan(s), 0.5, s)          # reject: no plausible feature
        return [float(v) for v in np.nan_to_num(s, nan=0.0, posinf=1e30, neginf=-1e30)]


def _make(lm: str, kind: str, n: int):
    return lambda: Detector(lm, kind, n)


VARIANTS = {}
for _lm in _MODELS:
    for _kind in ("logratio", "diff", "lr", "density"):
        VARIANTS[f"{_lm}-{_kind}"] = _make(_lm, _kind, 1)
        VARIANTS[f"{_lm}-{_kind}-avg3"] = _make(_lm, _kind, N_SEEDS)
    VARIANTS[f"{_lm}-ref-loglik"] = _make(_lm, "ref-loglik", 1)
