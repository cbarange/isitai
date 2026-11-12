"""Telescope perplexity (token repetition probability), with small reference models on CPU.

Paper: Nassif and Cooper, "Telescope: Improving Zero Shot Detection of LLM Generated
Content By Measuring Token Repetition Probability", ICML 2026 (arXiv 2607.04061).
Reference code: github.com/ChrisNassif/Telescope, file
llm_text_detectors/llm_text_detectors.py, read on 2026-11-12. That repository is under
CC BY-NC-SA 4.0: nothing is copied from it; this file is an independent implementation
of the published formula, checked against the reference for indexing and sign only.

Formula (T tokens s_0..s_{T-1}, logits z_i = model output after reading s_0..s_i):

    telescope  = mean over i = 0..T-2 of  -log softmax(z_i)[s_i]        (repeat s_i)
    perplexity = mean over i = 0..T-2 of  -log softmax(z_i)[s_{i+1}]    (usual next token)

Both are mean cross-entropies in nats (the reference also calls them "perplexity" without
exponentiating). As in the reference (`logits[:-1]` against `input_ids[:-1]`), the last
position is dropped from the telescope mean although it could be scored.

Sign. The reference feeds telescope perplexity to the ROC as it is (label 1 = LLM) and
negates perplexity and Binoculars. So HIGH telescope = AI (a model avoids repeating the
token it just read, and its own text carries that aversion), LOW perplexity = AI.
score() returns +telescope for the telescope variants and -perplexity for the "-ppl"
variants. The sign comes from the paper, not from any split of this benchmark; if a
smoke AUROC is under 0.5 it is reported, never flipped.

Only the abstract of the paper and the reference repository were read for this file, not
the body of the paper: statements below about "the reference" are read in its code.

Zero-shot: NEEDS_TRAINING is False and nothing is fitted. The brief of this benchmark
reports (from a literature sweep, not checked here in the paper body) that the raw value
is poorly calibrated across datasets and models and that the threshold must be tuned on
local data; the repository does ship a threshold-transfer script. A threshold does not change the scores written by run.py; it is derived from the
train split only by `telescope_tools.py calibrate` (reads a `run.py --split train` result
file, writes /tmp/isitai-bench/cache/telescope/calibration.json).

Deviations from the paper and the reference code
  1. Model. The reference scores telescope perplexity with the PERFORMER logits, and its
     experiment script (scripts/generate_experiment_results.py, dict
     MODEL_PERFORMER_OBSERVER_PAIRS_TO_TEST, unpacked as (performer, observer)) pairs
     performer "<model>-Instruct" with observer "<model>" (base). Those SmolLM pairs are
     commented out in the repository head, so the paper's "SmolLM2 135M" row is most
     likely HuggingFaceTB/SmolLM2-135M-Instruct, not proven. The task of
     this benchmark asked for the base models; both are exposed and named:
       smollm2-135m, smollm-135m                    base model (asked for here)
       smollm2-135m-instruct, smollm-135m-instruct  performer of the reference code
  2. Precision. float32 on CPU. The reference loads these models in float16 on GPU.
  3. Length. The reference truncates to min(tokenizer.model_max_length, 10,000) tokens
     and reads the text in one pass. Here the text is tokenised once, without truncation,
     and cut into consecutive chunks of CHUNK_TOKENS = 2048 tokens (the context of
     SmolLM v1; SmolLM2 has 8192); each chunk is a separate forward pass and the per-token
     losses of all chunks are pooled (token-weighted mean, not a mean of chunk means). A
     text of at most 2048 tokens gets exactly the reference value. A longer text differs:
     the first tokens of each later chunk are read without their left context. A final
     chunk of one token cannot be scored and is dropped.
     The "-trunc512" variants keep only the first 512 tokens, like the other model-based
     detectors of this benchmark (same input budget, not the paper's setting).
  4. Short texts. The reference experiments skip samples under 100 words and over 5,000
     words (`len(text.split(" "))`). Here every text is scored; detail() carries
     `short: True` under 100 words by that same count (it can differ slightly from the
     benchmark's `n_words = len(text.split())`). The <50 and 50-200 buckets of
     evaluate.py therefore show a regime the paper did not evaluate.
  5. Batching. One text per forward pass, no padding (the reference does the same).
  6. Tokenisation. Tokenizer defaults, as in the reference: no BOS token is added by hand
     (the SmolLM tokenizers add none), so position 0 is the first token of the text read
     with no context at all.
  7. Degenerate input. Under 2 tokens there is nothing to average: score() returns 0.0
     (the reference would return NaN). The benchmark has no text under 10 words.
  8. Language. SmolLM and SmolLM2 are English-centric. The repository's config.yaml lists
     multilingual M4 sets (Arabic, Chinese, Russian, Urdu) and no French; test_fr is unverified
     territory for this method. No multilingual model is substituted.
  9. Extra outputs, not in the paper's headline metric: detail() returns plain perplexity
     from the same pass and a per-window score (rolling mean of the per-token losses over
     WINDOW_TOKENS = 100 tokens, stride WINDOW_STRIDE = 50) so that mixed human/AI texts
     can be inspected. The reference has a per-token ablation, no windowing. No extra
     forward pass is made for either. `start_token` / `end_token` index SCORED positions
     (one fewer than tokens per chunk), so beyond 2048 tokens they lag the token index by
     one per earlier chunk, and a window can straddle a chunk boundary.
 10. The "-median" option of the reference (median instead of mean) is not exposed; the
     reference default is the mean.

Deterministic: no sampling; the score is a function of the text and the weights (seed
fixed anyway). CPU only, THREADS threads.

Sizes on disk (Hub file listing, 2026-11-12): model.safetensors is 269 MB (257 MiB) for
SmolLM2-135M, SmolLM2-135M-Instruct and SmolLM-135M-Instruct, stored in bfloat16, and
538 MB for SmolLM-135M (float32). All four have 134.5 M parameters and take about 538 MB
once loaded in float32. The MODEL string of each variant gives the size of the file found
in the local cache. Licence of the four models: Apache-2.0 (Hub model cards).
"""
from __future__ import annotations

import os

os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")

import numpy as np  # noqa: E402

from common import THREADS  # noqa: E402

CHUNK_TOKENS = 2048
TRUNC_TOKENS = 512
WINDOW_TOKENS = 100
WINDOW_STRIDE = 50
MIN_WORDS_PAPER = 100
MAX_WORDS_PAPER = 5000

MODELS = {
    "smollm2-135m": ("HuggingFaceTB/SmolLM2-135M", "base model; NOT the performer of the reference code"),
    "smollm2-135m-instruct": ("HuggingFaceTB/SmolLM2-135M-Instruct", "performer of the reference code (paper row 'SmolLM2 135M')"),
    "smollm-135m": ("HuggingFaceTB/SmolLM-135M", "base model; NOT the performer of the reference code"),
    "smollm-135m-instruct": ("HuggingFaceTB/SmolLM-135M-Instruct", "performer of the reference code (paper row 'SmolLM 135M')"),
}

DEFAULT_VARIANT = "smollm2-135m"

NAME = "telescope"
NEEDS_TRAINING = False
MODEL = ("Telescope perplexity, HuggingFaceTB/SmolLM2-135M (135 M params, 269 MB bf16 safetensors, "
         "Apache-2.0), zero-shot, chunks of 2048 tokens, CPU fp32")
BATCH_SIZE = 16


def _weights_mb(model_id: str) -> float | None:
    """Size of the weight file in the local Hub cache, in MB (None if not found)."""
    try:
        from huggingface_hub import try_to_load_from_cache
        for name in ("model.safetensors", "pytorch_model.bin"):
            path = try_to_load_from_cache(model_id, name)
            if isinstance(path, str) and os.path.exists(path):
                return os.path.getsize(path) / (1024 * 1024)
    except Exception:
        pass
    return None


class Telescope:
    NEEDS_TRAINING = False
    BATCH_SIZE = 16  # only the chunking of run.py; texts are scored one by one inside

    def __init__(self, model_key: str, metric: str = "telescope", truncate: int | None = None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        assert metric in ("telescope", "ppl")
        model_id, role = MODELS[model_key]
        self.model_id = model_id
        self.metric = metric
        self.truncate = truncate
        suffix = ("" if metric == "telescope" else "-ppl") + (f"-trunc{truncate}" if truncate else "")
        self.NAME = f"telescope.{model_key}{suffix}"

        torch.manual_seed(0)
        torch.set_num_threads(THREADS)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, dtype=torch.float32).to("cpu").eval()
        self.context = int(getattr(self.model.config, "max_position_embeddings", CHUNK_TOKENS))
        self.chunk = min(CHUNK_TOKENS, self.context)
        n_params = sum(p.numel() for p in self.model.parameters())
        mb = _weights_mb(model_id)
        size = f"{mb:.0f} MiB weight file on disk" if mb else "weight file size not measured"
        what = ("Telescope perplexity, mean of -log p(repeat the token just read)" if metric == "telescope"
                else "plain perplexity (negated mean next-token cross-entropy), same forward pass as Telescope")
        length = (f"first {truncate} tokens only" if truncate
                  else f"whole text in chunks of {self.chunk} tokens")
        self.MODEL = (f"{what}; {model_id} ({role}), {n_params / 1e6:.0f} M params, {size}, "
                      f"Apache-2.0; zero-shot; {length}; CPU fp32")

    # -- one forward pass per chunk -------------------------------------------------
    def token_losses(self, text: str):
        """(telescope_losses, perplexity_losses, n_tokens): two float64 arrays with one
        value per scored position, pooled over the chunks of the text."""
        torch = self.torch
        ids = self.tokenizer(text, add_special_tokens=True, truncation=False, verbose=False)["input_ids"]
        if self.truncate:
            ids = ids[:self.truncate]
        tel, ppl = [], []
        for start in range(0, len(ids), self.chunk):
            piece = ids[start:start + self.chunk]
            if len(piece) < 2:
                continue
            x = torch.tensor([piece], dtype=torch.long, device="cpu")
            with torch.inference_mode():
                z = self.model(input_ids=x, attention_mask=torch.ones_like(x)).logits[0, :-1].float()
                lse = torch.logsumexp(z, dim=-1)
                same = z.gather(1, x[0, :-1].unsqueeze(1)).squeeze(1)   # logit of s_i after reading s_i
                nxt = z.gather(1, x[0, 1:].unsqueeze(1)).squeeze(1)     # logit of s_{i+1}
                tel.append((lse - same).double().numpy())
                ppl.append((lse - nxt).double().numpy())
        if not tel:
            return np.zeros(0), np.zeros(0), len(ids)
        return np.concatenate(tel), np.concatenate(ppl), len(ids)

    def detail(self, text: str) -> dict:
        """Everything one pass gives: both metrics, the paper's length flag, and the
        per-window values. Not used by run.py."""
        tel, ppl, n_tokens = self.token_losses(text)
        n_words = len(text.split(" "))
        out = {
            "telescope": float(tel.mean()) if len(tel) else None,
            "perplexity": float(ppl.mean()) if len(ppl) else None,
            "n_tokens": n_tokens,
            "n_words_paper_count": n_words,
            "short": n_words < MIN_WORDS_PAPER,          # the paper skips these
            "over_paper_max": n_words > MAX_WORDS_PAPER,  # and these
            "windows": [],
        }
        n = len(tel)
        if n:
            starts = [0] if n <= WINDOW_TOKENS else list(range(0, n - WINDOW_TOKENS + 1, WINDOW_STRIDE))
            if n > WINDOW_TOKENS and starts[-1] + WINDOW_TOKENS < n:
                starts.append(n - WINDOW_TOKENS)  # last window flush with the end
            for s in starts:
                e = min(n, s + WINDOW_TOKENS)
                out["windows"].append({"start_token": s, "end_token": e,
                                       "telescope": float(tel[s:e].mean()),
                                       "perplexity": float(ppl[s:e].mean())})
        return out

    def score(self, texts: list[str]) -> list[float]:
        out = []
        for t in texts:
            tel, ppl, _ = self.token_losses(t)
            if not len(tel):
                out.append(0.0)
            elif self.metric == "telescope":
                out.append(float(tel.mean()))
            else:
                out.append(-float(ppl.mean()))
        return out


def _variants() -> dict:
    v = {}
    for key in MODELS:
        v[key] = (lambda key=key: Telescope(key, "telescope"))
        v[f"{key}-ppl"] = (lambda key=key: Telescope(key, "ppl"))
        v[f"{key}-trunc{TRUNC_TOKENS}"] = (lambda key=key: Telescope(key, "telescope", TRUNC_TOKENS))
        v[f"{key}-ppl-trunc{TRUNC_TOKENS}"] = (lambda key=key: Telescope(key, "ppl", TRUNC_TOKENS))
    return v


VARIANTS = _variants()

_default = None


def score(texts: list[str]) -> list[float]:
    """Module-level default (smollm2-135m). Prefer --variant: here the model loads on the
    first call, so run.py reports a load time near zero."""
    global _default
    if _default is None:
        _default = Telescope(DEFAULT_VARIANT)
    return _default.score(texts)
