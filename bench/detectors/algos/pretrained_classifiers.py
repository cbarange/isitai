"""Published fine-tuned AI-text classifiers, run as they are (no fitting on our data).

  run.py --algo pretrained_classifiers --variant VARIANT --split SPLIT

Every variant is pinned to a Hub revision, loads only safetensors or ONNX files, runs on CPU
with common.THREADS threads and returns a LOGIT MARGIN (higher = more likely AI), not a
probability: probabilities saturate at 1.0 and the ties would distort the thresholds at 1%
FPR. The direction of each score comes from the model card or config (never from our data).

Variants

  roberta-openai          openai-community/roberta-base-openai-detector  (MIT)
      RoBERTa-base, 125 M parameters, PyTorch. Trained by OpenAI in 2019 on the outputs of
      GPT-2 1.5B (Solaiman et al., arXiv 1908.09203). NOT trained on RAID.
      config.id2label = {0: "Fake", 1: "Real"}: score = logit[Fake] - logit[Real].
      Truncation as in OpenAI's detector/server.py: the first 510 BPE tokens, then <s> and
      </s> are added (512 positions). No deviation except batching with padding.
      An automatic ONNX conversion exists (onnx-community/roberta-base-openai-detector-ONNX);
      it is not used: the PyTorch/ONNX comparison is made on the ModernBERT below.

  desklib                 desklib/ai-text-detector-v1.01  (MIT)
      DeBERTa-v3-large, 435 M parameters, PyTorch, mean pooling and one linear unit (class
      copied from the model card). Trained on RAID (card: `datasets: liamdugan/raid`).
      score = the single logit (card: sigmoid(logit) = probability of AI).
      Truncation: the first 768 tokens, as in the card's predict_single_text(max_len=768).
      Deviation: the card pads every text to 768 tokens; here nothing is padded when a
      text is scored alone, and BATCH_SIZE = 1 makes run.py score one text per forward
      pass (padded batches of 8 were 4 to 5 times slower per text in the smoke run). The
      pooling and the attention ignore padding, so the logit is the same up to float
      rounding (checked: 5e-7 between a padded batch of 12 and single texts).
      No ONNX export of this model was found on the Hub (searched 2026-11-12).

  gpttrace-ettin150       nakas/gpttrace-ettin150-text-v5e  (CC-BY-SA-4.0, share-alike)
      Ettin-encoder-150M (ModernBERT family), distilled from GPTTrace Ettin-1B; the only
      file published is the dynamic int8 ONNX (151 MB), run with ONNX Runtime. Trained on
      RAID train, 200k rows of MAGE train and 100k human rows (Wikipedia, PMC, arXiv,
      Gutenberg) according to the card. Third on the RAID leaderboard with attacks on
      2026-10-21 according to the card (not verified here).
      Recipe of the card: normalize_text() (removes Unicode format characters and
      variation selectors, maps Cyrillic/Greek homoglyphs to Latin in mostly-Latin text),
      whole text tokenised, `ids[:511] + ids[-1:]` when over 512 tokens, one text per
      session run with an all-ones mask, logits ordered [human, ai]:
      score = logit[ai] - logit[human]. No padding, so no batching: score() loops over the
      texts. Deviation: the model repository ships normalize.py; it is NOT executed here
      (downloaded code). _gpttrace_normalize() below is a re-implementation of the same
      rules; its homoglyph table was compared with the original by parsing, the rest by
      reading, never by running both side by side.

  modernbert-raid-mage             GeorgeDrayson/modernbert-ai-detection-raid-mage  (Apache-2.0)
  modernbert-raid-mage-onnx        onnx-community/modernbert-ai-detection-raid-mage-ONNX, onnx/model.onnx (fp32)
  modernbert-raid-mage-onnx-int8   same repository, onnx/model_quantized.onnx (dynamic int8)
      ModernBERT-base, 150 M parameters, trained on MAGE and RAID (Drayson, Yilmaz,
      Lampos, "Machine-generated text detection prevents language model collapse", arXiv
      2502.15654). The same model three times, to compare PyTorch with ONNX Runtime and
      fp32 with int8. Official code (GeorgeDrayson/model_collapse, src/utils/detector.py):
      softmax(logits)[:, 1] is the machine-generated confidence, so
      score = logit[1] - logit[0].
      Deviations: (1) the official code divides the logits by a temperature (1.3017) before
      the softmax; a positive scale does not change the order, so it is left out. (2) the
      official code truncates on the LEFT (keeps the end) at the generator's block length
      (64-token continuations in the paper); the training length of the detector is not
      stated. Here: the first 512 tokens, like the other variants. (3) the ONNX files are
      an automatic conversion by the onnx-community Space, not a release of the authors.
      This is the "small ModernBERT" of the task. Hub searches of 2026-11-12 ("MiniLM ai
      detect", "minilm ai detector", "tiny ai text detector") returned nothing, and the
      DistilBERT detectors found have no paper and no leaderboard entry, so no model
      smaller than this one is included. ModernBERT-base is the size class of
      RoBERTa-base: not small against a 6 MB core.

Contamination, to read the numbers correctly
  The benchmark's RAID rows come from RAID `train.csv`. desklib, gpttrace-ettin150 and
  modernbert-raid-mage were trained on RAID train (their cards), so `train`, `test`,
  `test_attack` and the RAID parts of `test_ood` (a, b) were very probably SEEN during their
  training: not merely in-distribution. The MAGE part of test_ood comes from MAGE's own
  out-of-distribution test file (unseen GPT-4), but gpttrace and modernbert were trained on
  MAGE train (same human sources). Informative for these three: the HC3 part of test_ood,
  test_fr and test_fiction. roberta-openai saw none of the benchmark data (it only knows
  GPT-2, one of RAID's generators).
  All four models are English-only: test_fr is out of language for every variant.

Determinism: inference only, eval mode, no dropout, torch.manual_seed(0); ONNX Runtime with
the CPU provider only. The score of a text does not depend on the batch it is in beyond
float rounding (checked on 12 texts: at most 1e-5 for the padded PyTorch and fp32 ONNX
variants; the two int8 variants run one text at a time, because dynamic quantisation takes
its ranges from the whole batch). The fp32 ONNX export gives the PyTorch logits to 3e-6.
"""
from __future__ import annotations

import os
import re
import unicodedata

import numpy as np

from common import THREADS

NAME = "pretrained_classifiers"
NEEDS_TRAINING = False
MODEL = "see VARIANTS: published classifiers from the Hugging Face Hub, pinned revisions"

os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


def _snapshot(repo: str, revision: str, files: list[str]) -> str:
    """Local directory of a pinned revision; downloads only the listed files."""
    from huggingface_hub import snapshot_download
    try:
        return snapshot_download(repo, revision=revision, allow_patterns=files, local_files_only=True)
    except Exception:
        return snapshot_download(repo, revision=revision, allow_patterns=files)


def _ort_session(path: str):
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = THREADS
    opts.inter_op_num_threads = 1
    opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return ort.InferenceSession(path, sess_options=opts, providers=["CPUExecutionProvider"])


def _torch():
    import torch
    torch.manual_seed(0)
    return torch


# --- GPTTrace input normalisation (re-implementation of the rules of the model's normalize.py)
_HOMOGLYPHS = dict(zip(
    # Cyrillic lower, Cyrillic upper, Greek upper, Greek lower
    "\u0430\u0435\u043e\u0440\u0441\u0443\u0445\u0456\u0458\u0455\u04bb\u0501\u051b\u051d\u04cf"
    "\u0410\u0412\u0415\u041a\u041c\u041d\u041e\u0420\u0421\u0422\u0425\u0406\u0408\u0405\u04ae\u0500\u051a\u051c"
    "\u0391\u0392\u0395\u0396\u0397\u0399\u039a\u039c\u039d\u039f\u03a1\u03a4\u03a5\u03a7"
    "\u03bf\u03bd\u03b9\u03ba\u03c1\u03c4\u03c5\u03c7\u03b1",
    "aeopcyxijshdqwl"
    "ABEKMHOPCTXIJSYDQW"
    "ABEZHIKMNOPTYX"
    "ovikptuxa",
    strict=True,
))
_LOOKALIKE = re.compile("[" + "".join(_HOMOGLYPHS) + "]")
_GREEK_CYRILLIC = re.compile("[\u0370-\u03ff\u0400-\u052f]")
_LATIN = re.compile("[A-Za-z]")
_LETTERS = re.compile(r"[^\W\d_]+")


def _gpttrace_normalize(text: str) -> str:
    """Drops format characters (category Cf) and variation selectors U+FE00-FE0F. Then, in
    a text with more Latin letters than genuine Greek/Cyrillic ones, maps lookalike letters
    to Latin in every word that becomes free of Greek/Cyrillic once mapped."""
    t = "".join(c for c in str(text)
                if not (unicodedata.category(c) == "Cf" or "\ufe00" <= c <= "\ufe0f"))
    look = _LOOKALIKE.findall(t)
    if not look:
        return t
    foreign = len(_GREEK_CYRILLIC.findall(t)) - len(look)
    if len(_LATIN.findall(t)) <= foreign:
        return t

    def fix(match):
        word = match.group(0)
        mapped = _LOOKALIKE.sub(lambda m: _HOMOGLYPHS[m.group(0)], word)
        return word if _GREEK_CYRILLIC.search(mapped) else mapped

    return _LETTERS.sub(fix, t)


class _Base:
    NEEDS_TRAINING = False
    BATCH_SIZE = 16


class RobertaOpenAI(_Base):
    REPO = "openai-community/roberta-base-openai-detector"
    REV = "6cba99c003b711c7fe94f8a3aa2be35a792cb6fa"
    MAX_TOKENS = 512  # 510 text tokens + <s> + </s>

    def __init__(self):
        torch = _torch()
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.NAME = "pretrained_classifiers.roberta-openai"
        self.MODEL = (f"{self.REPO}@{self.REV[:7]} (MIT): RoBERTa-base 125 M params, PyTorch fp32, "
                      "model.safetensors 501 MB; trained on GPT-2 1.5B outputs, not on RAID; "
                      "first 512 tokens")
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(self.REPO, revision=self.REV)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.REPO, revision=self.REV, use_safetensors=True).to("cpu").eval()
        labels = {int(k): v for k, v in self.model.config.id2label.items()}
        assert labels == {0: "Fake", 1: "Real"}, labels

    def score(self, texts: list[str]) -> list[float]:
        enc = self.tok(texts, truncation=True, max_length=self.MAX_TOKENS, padding=True, return_tensors="pt")
        with self.torch.inference_mode():
            logits = self.model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"]).logits
        return (logits[:, 0] - logits[:, 1]).double().tolist()


class Desklib(_Base):
    REPO = "desklib/ai-text-detector-v1.01"
    REV = "5fdea974cd4287c61674951ec78803aa274e2fb7"
    MAX_TOKENS = 768
    # one text per forward pass: padded batches of 8 were 4 to 5 times slower per text
    # than single texts on this CPU (smoke run, machine shared with other jobs)
    BATCH_SIZE = 1

    def __init__(self):
        torch = _torch()
        from torch import nn
        from transformers import AutoConfig, AutoModel, AutoTokenizer, PreTrainedModel

        class DesklibAIDetectionModel(PreTrainedModel):
            """The class of the model card (mean pooling + one linear unit)."""
            config_class = AutoConfig
            _tied_weights_keys = []

            @property
            def all_tied_weights_keys(self):  # transformers >= 5
                return {}

            def __init__(self, config):
                super().__init__(config)
                self.model = AutoModel.from_config(config)
                self.classifier = nn.Linear(config.hidden_size, 1)

            def forward(self, input_ids, attention_mask=None):
                hidden = self.model(input_ids, attention_mask=attention_mask)[0]
                mask = attention_mask.unsqueeze(-1).expand(hidden.size()).float()
                pooled = torch.sum(hidden * mask, dim=1) / torch.clamp(mask.sum(dim=1), min=1e-9)
                return self.classifier(pooled)

        self.NAME = "pretrained_classifiers.desklib"
        self.MODEL = (f"{self.REPO}@{self.REV[:7]} (MIT): DeBERTa-v3-large 435 M params, PyTorch fp32, "
                      "model.safetensors 1.74 GB; TRAINED ON RAID; first 768 tokens")
        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(self.REPO, revision=self.REV)
        config = AutoConfig.from_pretrained(self.REPO, revision=self.REV)
        model, info = DesklibAIDetectionModel.from_pretrained(
            self.REPO, revision=self.REV, config=config, use_safetensors=True, output_loading_info=True)
        # a silently re-initialised head would look like a merely weak detector
        problems = {k: v for k, v in info.items() if v and k in ("missing_keys", "unexpected_keys", "mismatched_keys")}
        assert not problems, f"desklib weights did not load cleanly: {problems}"
        self.model = model.to("cpu").eval()

    def score(self, texts: list[str]) -> list[float]:
        enc = self.tok(texts, truncation=True, max_length=self.MAX_TOKENS, padding=True, return_tensors="pt")
        with self.torch.inference_mode():
            logits = self.model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"])
        return logits.reshape(-1).double().tolist()


class GPTTraceEttin150(_Base):
    REPO = "nakas/gpttrace-ettin150-text-v5e"
    REV = "9dadc95474b74a7be285866203788a6568b3c216"
    MAX_TOKENS = 512

    def __init__(self):
        from tokenizers import Tokenizer
        self.NAME = "pretrained_classifiers.gpttrace-ettin150"
        self.MODEL = (f"{self.REPO}@{self.REV[:7]} (CC-BY-SA-4.0): Ettin-encoder-150M, ONNX Runtime, "
                      "dynamic int8, onnx/model_quantized.onnx 151 MB; TRAINED ON RAID and MAGE; "
                      "first 511 tokens + [SEP]")
        root = _snapshot(self.REPO, self.REV, ["onnx/model_quantized.onnx", "tokenizer.json"])
        self.normalize = _gpttrace_normalize
        self.tok = Tokenizer.from_file(os.path.join(root, "tokenizer.json"))
        self.tok.no_truncation()
        self.tok.no_padding()
        self.sess = _ort_session(os.path.join(root, "onnx", "model_quantized.onnx"))
        self.inputs = [i.name for i in self.sess.get_inputs()]

    def score(self, texts: list[str]) -> list[float]:
        out = []
        for text in texts:
            ids = self.tok.encode(self.normalize(text)).ids
            if len(ids) > self.MAX_TOKENS:
                ids = ids[:self.MAX_TOKENS - 1] + ids[-1:]  # keep the closing [SEP], as in training
            feeds = {}
            for name in self.inputs:
                if "mask" in name:
                    feeds[name] = np.ones((1, len(ids)), np.int64)
                else:
                    feeds[name] = np.array([ids], np.int64)
            human, ai = self.sess.run(None, feeds)[0][0][:2]
            out.append(float(ai) - float(human))
        return out


class ModernBertRaidMage(_Base):
    REPO = "GeorgeDrayson/modernbert-ai-detection-raid-mage"
    REV = "e047d9c56f51a7e5c5ef5b0dd556f519bb9dd624"
    ONNX_REPO = "onnx-community/modernbert-ai-detection-raid-mage-ONNX"
    ONNX_REV = "6dcd8a3100e75d1224d7222d883bde596113d3f3"
    MAX_TOKENS = 512

    def __init__(self, backend: str):
        from transformers import AutoTokenizer
        assert backend in ("torch", "onnx", "onnx-int8")
        self.backend = backend
        suffix = {"torch": "", "onnx": "-onnx", "onnx-int8": "-onnx-int8"}[backend]
        self.NAME = f"pretrained_classifiers.modernbert-raid-mage{suffix}"
        how = {
            "torch": f"{self.REPO}@{self.REV[:7]}, PyTorch fp32, model.safetensors 598 MB",
            "onnx": f"{self.ONNX_REPO}@{self.ONNX_REV[:7]}, ONNX Runtime fp32, onnx/model.onnx 599 MB",
            "onnx-int8": f"{self.ONNX_REPO}@{self.ONNX_REV[:7]}, ONNX Runtime dynamic int8, onnx/model_quantized.onnx 151 MB",
        }[backend]
        self.MODEL = f"ModernBERT-base 150 M params (Apache-2.0), {how}; TRAINED ON RAID and MAGE; first 512 tokens"
        self.tok = AutoTokenizer.from_pretrained(self.REPO, revision=self.REV)
        if backend == "torch":
            self.torch = _torch()
            from transformers import AutoModelForSequenceClassification
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.REPO, revision=self.REV, use_safetensors=True).to("cpu").eval()
            assert self.model.config.num_labels == 2
        else:
            file = "onnx/model.onnx" if backend == "onnx" else "onnx/model_quantized.onnx"
            root = _snapshot(self.ONNX_REPO, self.ONNX_REV, [file])
            self.sess = _ort_session(os.path.join(root, file))
            self.inputs = {i.name for i in self.sess.get_inputs()}

    def score(self, texts: list[str]) -> list[float]:
        if self.backend == "torch":
            enc = self.tok(texts, truncation=True, max_length=self.MAX_TOKENS, padding=True, return_tensors="pt")
            with self.torch.inference_mode():
                logits = self.model(input_ids=enc["input_ids"], attention_mask=enc["attention_mask"]).logits
            return (logits[:, 1] - logits[:, 0]).double().tolist()
        if self.backend == "onnx-int8":
            # dynamic quantisation takes its ranges from the whole batch: a padded batch
            # moves the margin by a few hundredths. One text per run keeps scores stable.
            groups = [[t] for t in texts]
        else:
            groups = [texts]
        out: list[float] = []
        for group in groups:
            enc = self.tok(group, truncation=True, max_length=self.MAX_TOKENS, padding=True, return_tensors="np")
            feeds = {k: enc[k].astype(np.int64) for k in ("input_ids", "attention_mask") if k in self.inputs}
            logits = self.sess.run(None, feeds)[0]
            out.extend((logits[:, 1].astype(np.float64) - logits[:, 0].astype(np.float64)).tolist())
        return out


VARIANTS = {
    "roberta-openai": RobertaOpenAI,
    "desklib": Desklib,
    "gpttrace-ettin150": GPTTraceEttin150,
    "modernbert-raid-mage": lambda: ModernBertRaidMage("torch"),
    "modernbert-raid-mage-onnx": lambda: ModernBertRaidMage("onnx"),
    "modernbert-raid-mage-onnx-int8": lambda: ModernBertRaidMage("onnx-int8"),
}
