"""Fast-DetectGPT: conditional probability curvature with analytic sampling, zero-shot.

Paper: Bao, Zhao, Teng, Yang, Zhang, "Fast-DetectGPT: Efficient Zero-Shot Detection of
Machine-Generated Text via Conditional Probability Curvature", ICLR 2024 (arXiv 2310.05130).
Official code (MIT): github.com/baoguangsheng/fast-detect-gpt, scripts/fast_detect_gpt.py
(`get_sampling_discrepancy_analytic`), scripts/local_infer.py (`compute_crit`) and
scripts/model.py. The criterion below is a line-for-line port of the official function.

Method. A text x = (x_1..x_n) is tokenised once. A SAMPLING (reference) model q gives the
distribution of alternative tokens at each position, conditioned on the real prefix; a
SCORING model p gives log-probabilities. With lp_j = log p(. | x_<j) and q_j = q(. | x_<j):

    mean_j = sum_v q_j(v) lp_j(v)
    var_j  = sum_v q_j(v) lp_j(v)^2 - mean_j^2
    score  = ( sum_j lp_j(x_j) - sum_j mean_j ) / sqrt( sum_j var_j )

Machine text sits near a local maximum of the conditional probability, so the score is
HIGHER for AI text. The centre of the human scores depends on the model pair (near 0
when sampling = scoring, clearly positive for a mixed pair). No training, no
threshold fitted here: the raw criterion is returned (the calibrated probability of
local_infer.py is not used: its constants exist only for the large official pairs).

Variants (run.py --algo fast_detectgpt --variant V):
    gpt2          sampling = scoring = gpt2 (124M). "gpt2" is in the official model table.
    neo125        sampling = scoring = EleutherAI/gpt-neo-125m.
    gpt2_neo125   sampling gpt2, scoring EleutherAI/gpt-neo-125m (a small-scale copy of the
                  paper's black-box pair gpt-j-6B -> gpt-neo-2.7B: smaller sampler, Neo scorer).
    distilgpt2    sampling = scoring = distilgpt2 (82M), the smallest candidate for a port.
There is no module-level score(): always pass --variant.

Deviations from the paper and the official code:
  * MODELS. The paper's black-box setting samples with gpt-j-6B and scores with
    gpt-neo-2.7B; the current official default is falcon-7b -> falcon-7b-instruct. Those
    are 2.7 to 7 billion parameters in float16 on a GPU. Here: 82M to 125M parameters,
    float32, CPU. Only "gpt2" is in the official table; gpt-neo-125m and distilgpt2 are NOT
    (the official loader accepts any Hub id, so the code path is the same). The paper's
    white-box setting (scoring model = the generator) does not apply to any generator
    of the benchmark, except possibly RAID "gpt2" (which GPT-2 size RAID used was not
    checked). Expect lower accuracy than the published figures on ChatGPT / GPT-4 text.
  * TRUNCATION. Inputs are truncated to MAX_TOKENS = 512 tokens. The official code uses
    truncation=True with the tokenizer's own limit (1024 for gpt2, 2048 for gpt-neo). Long
    texts (test_fiction) are therefore scored on their first 512 tokens only.
  * BATCHING. One text per forward pass, no padding, like the official code (which asserts
    batch size 1). BATCH_SIZE only sets the chunking of run.py.
  * DEGENERATE INPUTS. A text with fewer than 2 tokens (nothing to predict), or a zero
    variance, gets 0.0, an arbitrary finite constant; the official code would fail or return
    NaN. No such text exists in the benchmark splits (minimum 13 tokens).
  * As in the official code, no BOS token is prepended for GPT-2-family tokenizers: the
    first token is context only and is not scored.
  * LANGUAGE. All three models are English models; on test_fr the score measures how
    French text looks to an English model. No multilingual variant is included (the official
    table has sberbank-ai/mGPT, not tried here).
  * MEMORY. Like the official code, the criterion materialises several float32 tensors of
    (tokens x 50,257 vocabulary entries), about 100 MB each at 512 tokens; the peak RSS of
    about 2 to 3 GB comes from them, not from the weights.

Deterministic: analytic sampling draws no random number; seeds are fixed anyway.
"""
from __future__ import annotations

import os

os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

MAX_TOKENS = 512
SEED = 0

_MODELS = {
    "gpt2": ("openai-community/gpt2", "124M params, 548 MB safetensors fp32, MIT"),
    "neo125": ("EleutherAI/gpt-neo-125m", "125M params, 526 MB safetensors fp32, MIT"),
    "distilgpt2": ("distilbert/distilgpt2", "82M params, 353 MB safetensors fp32, Apache-2.0"),
}

_loaded: dict[str, tuple] = {}


def _load(key: str):
    """Tokenizer and model, loaded once per process, CPU, eval mode."""
    if key not in _loaded:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch.manual_seed(SEED)
        hub_id = _MODELS[key][0]
        # official load_tokenizer: padding_side="right", pad = eos when there is no pad token
        tok = AutoTokenizer.from_pretrained(hub_id, padding_side="right")
        if tok.pad_token_id is None:
            tok.pad_token_id = tok.eos_token_id
        model = AutoModelForCausalLM.from_pretrained(hub_id)
        model.to("cpu")
        model.eval()
        _loaded[key] = (tok, model)
    return _loaded[key]


def _criterion(logits_ref, logits_score, labels) -> float:
    """get_sampling_discrepancy_analytic of the official repository."""
    import torch
    if logits_ref.size(-1) != logits_score.size(-1):
        vocab_size = min(logits_ref.size(-1), logits_score.size(-1))
        logits_ref = logits_ref[:, :, :vocab_size]
        logits_score = logits_score[:, :, :vocab_size]
    labels = labels.unsqueeze(-1) if labels.ndim == logits_score.ndim - 1 else labels
    lprobs_score = torch.log_softmax(logits_score, dim=-1)
    probs_ref = torch.softmax(logits_ref, dim=-1)
    log_likelihood = lprobs_score.gather(dim=-1, index=labels).squeeze(-1)
    mean_ref = (probs_ref * lprobs_score).sum(dim=-1)
    var_ref = (probs_ref * torch.square(lprobs_score)).sum(dim=-1) - torch.square(mean_ref)
    var_sum = var_ref.sum(dim=-1)
    if not bool(torch.all(var_sum > 0)):
        return 0.0
    discrepancy = (log_likelihood.sum(dim=-1) - mean_ref.sum(dim=-1)) / var_sum.sqrt()
    value = discrepancy.mean().item()
    return value if value == value and abs(value) != float("inf") else 0.0


class Detector:
    NEEDS_TRAINING = False
    BATCH_SIZE = 16

    def __init__(self, variant: str, sampling: str, scoring: str):
        self.NAME = f"fast_detectgpt.{variant}"
        self.sampling = sampling
        self.scoring = scoring
        if sampling == scoring:
            self.MODEL = f"{_MODELS[scoring][0]} as sampling and scoring model ({_MODELS[scoring][1]})"
        else:
            self.MODEL = (f"sampling {_MODELS[sampling][0]} ({_MODELS[sampling][1]}) + "
                          f"scoring {_MODELS[scoring][0]} ({_MODELS[scoring][1]})")
        self.MODEL += f"; zero-shot, pretrained LM only, inputs truncated to {MAX_TOKENS} tokens"

    def _one(self, text: str) -> float:
        import torch
        tok, model = _load(self.scoring)
        tokenized = tok(text, truncation=True, max_length=MAX_TOKENS, return_tensors="pt",
                        padding=True, return_token_type_ids=False)
        if tokenized.input_ids.size(1) < 2:
            return 0.0
        labels = tokenized.input_ids[:, 1:]
        with torch.no_grad():
            logits_score = model(**tokenized).logits[:, :-1]
            if self.sampling == self.scoring:
                logits_ref = logits_score
            else:
                tok_ref, model_ref = _load(self.sampling)
                tokenized = tok_ref(text, truncation=True, max_length=MAX_TOKENS,
                                    return_tensors="pt", padding=True,
                                    return_token_type_ids=False)
                assert torch.equal(tokenized.input_ids[:, 1:], labels), "Tokenizer is mismatch."
                logits_ref = model_ref(**tokenized).logits[:, :-1]
            return _criterion(logits_ref, logits_score, labels)

    def score(self, texts: list[str]) -> list[float]:
        return [self._one(t) for t in texts]


VARIANTS = {
    "gpt2": lambda: Detector("gpt2", "gpt2", "gpt2"),
    "neo125": lambda: Detector("neo125", "neo125", "neo125"),
    "gpt2_neo125": lambda: Detector("gpt2_neo125", "gpt2", "neo125"),
    "distilgpt2": lambda: Detector("distilgpt2", "distilgpt2", "distilgpt2"),
}

NAME = "fast_detectgpt"
NEEDS_TRAINING = False
MODEL = "see VARIANTS (gpt2, gpt-neo-125m, distilgpt2); no module-level score()"
