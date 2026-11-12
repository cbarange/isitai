"""GLTR, perplexity and burstiness detectors from a small causal language model on CPU.

One forward pass of GPT-2 (or DistilGPT-2) over the text gives, for every token, its
log-probability, its rank in the model's prediction and the entropy of the prediction.
Every variant below is a statistic of those three series.

  run.py --algo gltr_ppl --variant gpt2-logrank --split test
  run.py --algo gltr_ppl --variant distilgpt2-feats-lr --split all

Variants: `<model>-<stat>`, with <model> in {gpt2, distilgpt2}.

Zero-shot (no fitting; the sign comes from the cited code and is never tuned on a test
split; `entropy` is the one exception, see below):
  loglik      mean token log-probability. Higher = more AI.
              Fast-DetectGPT `scripts/baselines.py::get_likelihood` (Bao et al. 2024), the
              log-likelihood baseline of DetectGPT (Mitchell et al. 2023); GLTR shows the
              same per-token probability. It is minus the log-perplexity, so it IS the
              perplexity detector.
  rank        minus the mean 1-indexed rank (`get_rank`).
  logrank     minus the mean log of the 1-indexed rank (`get_logrank`).
  entropy     MINUS the mean entropy of the predictive distribution. `get_entropy` of the
              official code returns the positive mean entropy; with that sign the AUROC
              on the TRAIN split (4,000 rows) was 0.34 (gpt2) and 0.36 (distilgpt2), so
              the sign is reversed here to respect "higher = more AI". This is a one-bit
              choice made on train only, and a deviation from the official code.
  lrr         log-likelihood / log-rank ratio of DetectLLM (Su et al. 2023):
              -sum(log p) / sum(log rank). Written from the formula of the paper; the
              official code was not re-read. An epsilon (1e-6) is added to the denominator.
  burstiness  minus the standard deviation of the per-sentence log-perplexity (uniform
              sentences = more AI). This is the "burstiness" idea popularised by GPTZero,
              which has no public reference code: the definition here is ours.

Trained on the train split only (StandardScaler + LogisticRegression, C=1, lbfgs,
max_iter=2000, random_state=0; the score is P(ai)):
  gltr-lr     the 4 GLTR bucket fractions: share of tokens whose rank is in the top 10,
              top 100, top 1000, beyond (Gehrmann et al. 2019; bucket edges [10, 100, 1000]
              read in the GLTR front end, `GLTR_Text_Box.ts`). The paper itself was not
              re-read: whether its own classifier used exactly these features is
              unverified.
  feats-lr    34 features: mean / std / quantiles of the token log-probability, mean log
              rank, log of the mean rank, quantiles of the log rank, the 4 GLTR buckets,
              the GLTR "frac(p)" histogram (p(token) / max p, 10 bins), mean and std of
              the entropy, mean of (surprisal - entropy), and the per-sentence
              log-perplexity statistics (mean, std, range, a flag "at least 2
              sentences", log of the sentence count). No token or word count is used;
              the sentence count is the only length-related feature.

Models (pinned revisions, downloaded once into HF_HOME):
  gpt2        openai-community/gpt2 @ 607a30d, 124M parameters, model.safetensors 548 MB,
              MIT. This is the "gpt-2-small" of the GLTR demo.
  distilgpt2  distilbert/distilgpt2 @ 2290a62, 82M parameters, model.safetensors 353 MB,
              Apache-2.0.
Both are English models; on French (test_fr) they score out of their training language.

Deviations from the papers and official code:
  - Truncation: the text is cut to its first 511 BPE tokens (512 positions with the BOS
    token). GLTR and the DetectGPT baselines use the full 1024-token context or the whole
    text. A 1,500-word story of test_fiction is therefore scored on about its first
    quarter to third.
  - BOS: `<|endoftext|>` is prepended, as in GLTR `backend/api.py`, so the first token is
    scored too. The Fast-DetectGPT baselines do not prepend it and skip the first token.
  - Rank: number of vocabulary entries with a strictly higher logit (ties resolved in
    favour of the observed token), 0-indexed for the GLTR buckets (`pos < 10`), +1 for
    rank / logrank / lrr as in `get_rank`. GLTR uses argsort; the two differ only on
    exact ties.
  - Scoring model: here the scorer is a fixed small model and the generators are other
    models (black-box setting). The papers also report settings where the scorer is the
    generator, and larger scorers; their exact model list was not re-checked.
  - Per-sentence perplexity comes from the SAME forward pass (each token keeps the context
    of the previous sentences), not from scoring each sentence alone. Sentences are split
    with a regex on `.!?…` followed by white space, and on line breaks; a sentence needs
    at least 3 scored tokens. A text with fewer than 2 such sentences has a sentence
    standard deviation of 0, so `burstiness` gives it the most-AI value (0): short texts
    are a known weak spot of that variant.
  - GLTR is a visual tool; `gltr-lr` is a classifier on its histogram, not a
    reproduction of an experiment of the paper.
  - An empty text (no token) gets all-zero features.

Batching: the forward pass takes one text at a time (_INNER_BATCH = 1), so a score does
not depend on the other texts of the call. The padded path (_INNER_BATCH > 1: right
padding with BOS/EOS, attention mask, padded positions excluded from every statistic) was
checked against it: same ranks, statistics equal to 1e-5. CPU only, float32, eval mode, no
sampling: deterministic.
"""
from __future__ import annotations

import re

import numpy as np

NAME = "gltr_ppl"
NEEDS_TRAINING = False
BATCH_SIZE = 16

MAX_TOKENS = 511          # scored tokens; 512 positions with BOS
_INNER_BATCH = 1          # forward-pass batch. 512 x 50257 float32 logits = 103 MB per text;
                          # larger batches were not faster on CPU (the full-vocabulary
                          # softmax dominates), so texts go one by one, without padding.
_MIN_SENT_TOKENS = 3
_SEED = 0

_MODELS = {
    "gpt2": ("openai-community/gpt2", "607a30d783dfa663caf39e06633721c8d4cfcd7e",
             "openai-community/gpt2 (124M parameters, model.safetensors 548 MB, MIT)"),
    "distilgpt2": ("distilbert/distilgpt2", "2290a62682d06624634c1f46a6ad5be0f47f38aa",
                   "distilbert/distilgpt2 (82M parameters, model.safetensors 353 MB, Apache-2.0)"),
}
MODEL = _MODELS["gpt2"][2] + "; pretrained LM only, not trained on any detection corpus"

_SENT_END = re.compile(r"[.!?…]+[\"'”’)\]]*\s+|\n+")
_loaded: dict = {}


def _load(key: str):
    if key not in _loaded:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.manual_seed(_SEED)
        repo, rev, _ = _MODELS[key]
        tok = AutoTokenizer.from_pretrained(repo, revision=rev, use_fast=True)
        model = AutoModelForCausalLM.from_pretrained(repo, revision=rev, dtype=torch.float32)
        model.to("cpu").eval()
        _loaded[key] = (tok, model)
    return _loaded[key]


def _token_series(key: str, texts: list[str]) -> list[dict]:
    """Per text: log-prob, 0-indexed rank, entropy, p/max p and sentence index of every
    scored token (float64 / int64 numpy arrays, possibly empty)."""
    import torch
    tok, model = _load(key)
    bos = tok.bos_token_id
    encoded = []
    for t in texts:
        e = tok(t, truncation=True, max_length=MAX_TOKENS, return_offsets_mapping=True,
                add_special_tokens=False)
        encoded.append((e["input_ids"], [o[0] for o in e["offset_mapping"]]))
    out: list[dict | None] = [None] * len(texts)
    order = sorted(range(len(texts)), key=lambda i: len(encoded[i][0]))
    for b in range(0, len(order), _INNER_BATCH):
        idx = order[b:b + _INNER_BATCH]
        longest = max(len(encoded[i][0]) for i in idx)
        if longest == 0:
            for i in idx:
                out[i] = _empty()
            continue
        ids = torch.full((len(idx), longest + 1), bos, dtype=torch.long)
        mask = torch.zeros((len(idx), longest + 1), dtype=torch.long)
        for r, i in enumerate(idx):
            n = len(encoded[i][0])
            ids[r, 1:n + 1] = torch.tensor(encoded[i][0], dtype=torch.long)
            mask[r, :n + 1] = 1
        with torch.no_grad():
            logits = model(input_ids=ids, attention_mask=mask).logits[:, :-1, :]
            target = ids[:, 1:]
            logp_all = torch.log_softmax(logits, dim=-1)
            del logits
            logp = logp_all.gather(-1, target.unsqueeze(-1)).squeeze(-1)
            rank = (logp_all > logp.unsqueeze(-1)).sum(-1)
            ent = -(logp_all.exp() * logp_all).sum(-1)
            frac = (logp - logp_all.max(-1).values).exp()
            del logp_all
        logp, rank, ent, frac = (x.numpy() for x in (logp, rank, ent, frac))
        for r, i in enumerate(idx):
            n = len(encoded[i][0])
            if n == 0:
                out[i] = _empty()
                continue
            out[i] = {"logp": logp[r, :n].astype(np.float64), "rank": rank[r, :n].astype(np.int64),
                      "ent": ent[r, :n].astype(np.float64), "frac": frac[r, :n].astype(np.float64),
                      "sent": _sentence_index(texts[i], encoded[i][1])}
    return out  # type: ignore[return-value]


def _empty() -> dict:
    z = np.zeros(0)
    return {"logp": z, "rank": z.astype(np.int64), "ent": z, "frac": z, "sent": z.astype(np.int64)}


def _sentence_index(text: str, starts: list[int]) -> np.ndarray:
    """Index of the sentence each token starts in."""
    ends = np.asarray([m.end() for m in _SENT_END.finditer(text)], dtype=np.int64)
    return np.searchsorted(ends, np.asarray(starts, dtype=np.int64), side="right")


def _sentence_logppl(s: dict) -> np.ndarray:
    """Log-perplexity of every sentence with at least _MIN_SENT_TOKENS scored tokens."""
    if len(s["logp"]) == 0:
        return np.zeros(0)
    sent = s["sent"]
    counts = np.bincount(sent)
    sums = np.bincount(sent, weights=-s["logp"])
    keep = counts >= _MIN_SENT_TOKENS
    return sums[keep] / counts[keep]


_STATS = ("loglik", "rank", "logrank", "entropy", "lrr", "burstiness")


def _zero_shot(stat: str, s: dict) -> float:
    if len(s["logp"]) == 0:
        return 0.0
    if stat == "loglik":
        return float(s["logp"].mean())
    if stat == "rank":
        return float(-(s["rank"] + 1).mean())
    if stat == "logrank":
        return float(-np.log(s["rank"] + 1).mean())
    if stat == "entropy":
        return float(-s["ent"].mean())   # sign reversed against the official code: see docstring
    if stat == "lrr":
        return float(-s["logp"].sum() / (np.log(s["rank"] + 1).sum() + 1e-6))
    if stat == "burstiness":
        sp = _sentence_logppl(s)
        return float(-sp.std()) if len(sp) >= 2 else 0.0
    raise ValueError(stat)


def _buckets(s: dict) -> list[float]:
    r = s["rank"]
    n = max(1, len(r))
    return [float((r < 10).sum()) / n, float(((r >= 10) & (r < 100)).sum()) / n,
            float(((r >= 100) & (r < 1000)).sum()) / n, float((r >= 1000).sum()) / n]


N_FEATS = 34


def _features(s: dict) -> list[float]:
    if len(s["logp"]) == 0:
        return [0.0] * N_FEATS
    lp, ent = s["logp"], s["ent"]
    lr = np.log(s["rank"] + 1)
    sp = _sentence_logppl(s)
    hist = np.histogram(s["frac"], bins=10, range=(0.0, 1.0))[0] / len(lp)
    f = [lp.mean(), lp.std(), *np.percentile(lp, [10, 25, 50, 75, 90]),
         lr.mean(), float(np.log((s["rank"] + 1).mean())), *np.percentile(lr, [50, 75, 90]),
         *_buckets(s), *hist.tolist(),
         ent.mean(), ent.std(), (-lp - ent).mean(),
         sp.mean() if len(sp) else -lp.mean(),
         sp.std() if len(sp) >= 2 else 0.0,
         (sp.max() - sp.min()) if len(sp) >= 2 else 0.0,
         1.0 if len(sp) >= 2 else 0.0,
         float(np.log1p(len(sp)))]
    assert len(f) == N_FEATS
    return [float(v) for v in f]


class ZeroShot:
    NEEDS_TRAINING = False
    BATCH_SIZE = BATCH_SIZE

    def __init__(self, key: str, stat: str):
        self.key, self.stat = key, stat
        self.NAME = f"gltr_ppl.{key}-{stat}"
        self.MODEL = _MODELS[key][2] + "; pretrained LM only, zero-shot"
        _load(key)

    def score(self, texts: list[str]) -> list[float]:
        return [_zero_shot(self.stat, s) for s in _token_series(self.key, texts)]


class Trained:
    NEEDS_TRAINING = True
    BATCH_SIZE = BATCH_SIZE

    def __init__(self, key: str, kind: str):
        self.key, self.kind = key, kind
        self.NAME = f"gltr_ppl.{key}-{kind}-lr"
        n = 4 if kind == "gltr" else N_FEATS
        self.MODEL = (_MODELS[key][2] + f" + logistic regression on {n} features "
                      "(a few hundred bytes), fitted on the RAID train split")
        self.clf = None
        _load(key)

    def _x(self, texts: list[str]) -> np.ndarray:
        fn = _buckets if self.kind == "gltr" else _features
        rows = []
        for b in range(0, len(texts), BATCH_SIZE):
            rows.extend(fn(s) for s in _token_series(self.key, texts[b:b + BATCH_SIZE]))
        return np.asarray(rows, dtype=np.float64)

    def fit(self, rows: list[dict]) -> None:
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        x = self._x([r["text"] for r in rows])
        y = np.asarray([r["label"] for r in rows])
        self.clf = make_pipeline(
            StandardScaler(), LogisticRegression(C=1.0, max_iter=2000, random_state=_SEED)).fit(x, y)

    def score(self, texts: list[str]) -> list[float]:
        return self.clf.predict_proba(self._x(texts))[:, 1].tolist()


def _zs(key, stat):
    return lambda: ZeroShot(key, stat)


def _tr(key, kind):
    return lambda: Trained(key, kind)


VARIANTS = {}
for _k in _MODELS:
    for _s in _STATS:
        VARIANTS[f"{_k}-{_s}"] = _zs(_k, _s)
    VARIANTS[f"{_k}-gltr-lr"] = _tr(_k, "gltr")
    VARIANTS[f"{_k}-feats-lr"] = _tr(_k, "feats")


def score(texts: list[str]) -> list[float]:
    """Module default (run.py --algo gltr_ppl without --variant): gpt2-logrank."""
    return [_zero_shot("logrank", s) for s in _token_series("gpt2", texts)]
