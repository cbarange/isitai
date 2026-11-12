"""Binoculars with SMALL model pairs (CPU budget). NOT the published setting.

Paper: Hans et al., "Spotting LLMs With Binoculars: Zero-Shot Detection of Machine-Generated
Text", ICML 2024 (arXiv 2401.12070). Official code: github.com/ahans30/Binoculars
(binoculars/metrics.py and binoculars/detector.py, read on 2026-11-12).

Formula, as in the official code (the same token ids go through both models):

    ppl   = mean over positions 0..T-2 of  -log q_performer(token[i+1] | tokens[..i])
    x_ppl = mean over positions 0..T-1 of  -sum_v p_observer(v | tokens[..i]) * log q_performer(v | tokens[..i])
    B     = ppl / x_ppl                       (LOW B means AI)

The official x_ppl mean runs over ALL T positions (it is not shifted like ppl, so it
includes the prediction after the last token); this is kept. The perplexity term uses the
PERFORMER logits (detector.py: `perplexity(encodings, performer_logits)`), and the
cross term is CrossEntropyLoss(input=performer logits, target=softmax(observer logits)).

score() returns -B, so that HIGHER means MORE LIKELY AI. The sign is fixed by the paper
(text is flagged AI when B is below a threshold); it was not chosen on any split.
Zero-shot: NEEDS_TRAINING is False, nothing is fitted, the Falcon thresholds of the paper
(0.9015 / 0.8536) are not used (they are specific to Falcon-7B and do not transfer).

Deviations from the paper and the official code
  1. Models. The paper uses observer tiiuae/falcon-7b and performer
     tiiuae/falcon-7b-instruct (7 B parameters each), impossible here. The variants
     below use pairs of small models (distilgpt2 to Qwen2.5-0.5B, 494 M parameters). The published figures (for example
     over 90% TPR at 0.01% FPR on ChatGPT text) are for Falcon-7B and must NOT be
     expected from these pairs.
  2. Roles. For base/instruct pairs the official assignment is kept: base model =
     observer, instruct model = performer. gpt2 / distilgpt2 has no base/instruct
     relation; both orders are exposed as variants ("gpt2-obs-distilgpt2-perf" and
     "distilgpt2-obs-gpt2-perf").
  3. Precision. float32 on CPU; the official default is bfloat16 on GPU. The SmolLM2
     and Qwen weight files are stored in bfloat16 and are upcast to float32 in memory
     (so RAM is about twice the file size per model); gpt2 and distilgpt2 are float32.
  4. Batching. Each text goes through the models alone, without padding (the official
     code pads a batch to the longest text and masks). The value per text is the same
     formula; this keeps memory bounded (two logit tensors of 512 x 151,936 floats for
     Qwen) and makes score([t]) identical whatever the chunk it arrives in.
  5. Truncation. 512 tokens of the observer tokenizer, as in the official code
     (max_token_observed=512). Longer texts are scored on their first 512 tokens only.
  6. Tokenisation. The observer tokenizer with its default settings, as in the official
     code; no BOS token is added by hand. The pair must have identical vocabularies
     (asserted, like the official assert_tokenizer_consistency).
  7. Degenerate input. A text of fewer than 2 tokens has no perplexity; score() returns
     -1.0 for it (B = 1, ppl equal to x_ppl: the human side of the scale, never a flag;
     the official code would return NaN). The benchmark drops texts under 10
     words, so this does not happen in the splits.
  8. Languages. gpt2, distilgpt2 are English models; SmolLM2 is mostly English. Results
     on test_fr are out of the models' main language.

No sampling anywhere: the score is a deterministic function of the text (seed fixed
anyway).

Sizes on disk are those of model.safetensors in the Hub snapshot (du, 2026-11-12);
parameter counts are the element counts of the tensors in that file (gpt2 and distilgpt2
files also hold attention-mask buffers); licences are those of the Hub model cards.
Only the official CODE was followed; the paper's equations were not re-read for this
module.
"""
from __future__ import annotations

import os

os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")

MAX_TOKENS = 512

#: variant -> (observer, performer, description for MODEL)
VARIANT_SPECS = {
    "smollm2-135m": (
        "HuggingFaceTB/SmolLM2-135M", "HuggingFaceTB/SmolLM2-135M-Instruct",
        "observer SmolLM2-135M (base) + performer SmolLM2-135M-Instruct, 134.5 M params each, "
        "257 MB + 257 MB on disk (bf16 safetensors), Apache-2.0"),
    "smollm2-360m": (
        "HuggingFaceTB/SmolLM2-360M", "HuggingFaceTB/SmolLM2-360M-Instruct",
        "observer SmolLM2-360M (base) + performer SmolLM2-360M-Instruct, 361.8 M params each, "
        "690 MB + 690 MB on disk (bf16 safetensors), Apache-2.0"),
    "qwen2.5-0.5b": (
        "Qwen/Qwen2.5-0.5B", "Qwen/Qwen2.5-0.5B-Instruct",
        "observer Qwen2.5-0.5B (base) + performer Qwen2.5-0.5B-Instruct, 494.0 M params each, "
        "942 MB + 942 MB on disk (bf16 safetensors), Apache-2.0"),
    "gpt2-obs-distilgpt2-perf": (
        "openai-community/gpt2", "distilbert/distilgpt2",
        "observer gpt2 (523 MB fp32 safetensors) + performer distilgpt2 (336 MB fp32 "
        "safetensors), MIT + Apache-2.0"),
    "distilgpt2-obs-gpt2-perf": (
        "distilbert/distilgpt2", "openai-community/gpt2",
        "observer distilgpt2 (336 MB fp32 safetensors) + performer gpt2 (523 MB fp32 "
        "safetensors), Apache-2.0 + MIT"),
}

DEFAULT_VARIANT = "smollm2-135m"

NAME = "binoculars_small"
NEEDS_TRAINING = False
MODEL = "Binoculars, small pairs (not the paper's Falcon-7B); default: " + VARIANT_SPECS[DEFAULT_VARIANT][2]
BATCH_SIZE = 16


class Binoculars:
    NEEDS_TRAINING = False
    BATCH_SIZE = 16  # only the chunking of run.py; texts are scored one by one inside

    def __init__(self, variant: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        observer_id, performer_id, desc = VARIANT_SPECS[variant]
        self.NAME = f"binoculars_small.{variant}"
        self.MODEL = (f"Binoculars with SMALL models (not the paper's Falcon-7B pair): {desc}; "
                      f"truncation {MAX_TOKENS} tokens, fp32, CPU")
        torch.manual_seed(0)
        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(observer_id)
        performer_tok = AutoTokenizer.from_pretrained(performer_id)
        if self.tokenizer.get_vocab() != performer_tok.get_vocab():
            raise RuntimeError(f"{observer_id} and {performer_id} do not share a vocabulary")
        kw = dict(dtype=torch.float32)
        self.observer = AutoModelForCausalLM.from_pretrained(observer_id, **kw).to("cpu").eval()
        self.performer = AutoModelForCausalLM.from_pretrained(performer_id, **kw).to("cpu").eval()

    def raw(self, text: str) -> float | None:
        """The Binoculars score B = ppl / x_ppl of one text (low = AI), or None."""
        torch = self.torch
        enc = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_TOKENS,
                             return_token_type_ids=False)
        ids = enc["input_ids"].to("cpu")
        if ids.shape[1] < 2:
            return None
        with torch.inference_mode():
            obs = self.observer(input_ids=ids, attention_mask=enc["attention_mask"]).logits[0].float()
            perf = self.performer(input_ids=ids, attention_mask=enc["attention_mask"]).logits[0].float()
            log_q = torch.log_softmax(perf, dim=-1)                       # (T, V)
            ppl = -log_q[:-1].gather(1, ids[0, 1:].unsqueeze(1)).mean()   # T-1 positions
            x_ppl = -(torch.softmax(obs, dim=-1) * log_q).sum(-1).mean()  # T positions
            b = (ppl / x_ppl).item()
        return b if b == b and abs(b) != float("inf") else None

    def score(self, texts: list[str]) -> list[float]:
        out = []
        for t in texts:
            b = self.raw(t)
            out.append(-1.0 if b is None else -b)
        return out


VARIANTS = {name: (lambda name=name: Binoculars(name)) for name in VARIANT_SPECS}

_default = None


def score(texts: list[str]) -> list[float]:
    global _default
    if _default is None:
        _default = Binoculars(DEFAULT_VARIANT)
    return _default.score(texts)
