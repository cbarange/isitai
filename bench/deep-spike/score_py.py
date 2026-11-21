#!/usr/bin/env python
"""Score texts with Binoculars or Fast-DetectGPT under onnxruntime (or PyTorch fp32 as reference).

  score_py.py --det bino  --models smollm2-135m,smollm2-135m-instruct --prec int8 --sets test,test_fr
  score_py.py --det fdgpt --models smollm2-135m --prec fp32 --backend torch --sets all

Same formulas, truncation (512 tokens) and tokenizer calls as bench/detectors/algos/
binoculars_small.py and fast_detectgpt.py. Batch of 1, no padding. The criterion is computed
in float64 from the float32 logits. Writes /tmp/isitai-deep/results/<name>.json with ids,
scores, token counts, per-text seconds, peak RSS. HIGHER score = MORE LIKELY AI.
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import statistics
import time

os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import numpy as np

MODELS_DIR = "/tmp/isitai-deep/models"
TEXTS = "/tmp/isitai-deep/texts"
RESULTS = "/tmp/isitai-deep/results"
MAX_TOKENS = 512
ALL = ["test", "test_ood", "test_fr", "test_fiction", "test_attack", "corpus", "golden"]


def log_softmax(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float64)
    m = x.max(-1, keepdims=True)
    return x - m - np.log(np.exp(x - m).sum(-1, keepdims=True))


def binoculars(obs: np.ndarray, perf: np.ndarray, ids: np.ndarray) -> float:
    """-(ppl / x_ppl); obs, perf: (T, V) logits."""
    if len(ids) < 2:
        return -1.0
    log_q = log_softmax(perf)
    ppl = -log_q[np.arange(len(ids) - 1), ids[1:]].mean()
    x_ppl = -(np.exp(log_softmax(obs)) * log_q).sum(-1).mean()
    b = ppl / x_ppl
    return -float(b) if np.isfinite(b) else -1.0


def fast_detectgpt(logits: np.ndarray, ids: np.ndarray) -> float:
    """Analytic sampling discrepancy, sampling model = scoring model."""
    if len(ids) < 2:
        return 0.0
    lp = log_softmax(logits[:-1])
    p = np.exp(lp)
    ll = lp[np.arange(len(ids) - 1), ids[1:]]
    mean = (p * lp).sum(-1)
    var = (p * lp * lp).sum(-1) - mean * mean
    if not var.sum() > 0:
        return 0.0
    v = (ll.sum() - mean.sum()) / np.sqrt(var.sum())
    return float(v) if np.isfinite(v) else 0.0


class OnnxLM:
    def __init__(self, key, prec, threads):
        import onnxruntime as ort
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        so.inter_op_num_threads = 1
        self.s = ort.InferenceSession(os.path.join(MODELS_DIR, key, f"{prec}.onnx"), so,
                                      providers=["CPUExecutionProvider"])

    def __call__(self, ids):
        return self.s.run(None, {"input_ids": ids[None].astype(np.int64)})[0][0]


class TorchLM:
    def __init__(self, key, prec, threads):
        import torch
        from transformers import AutoModelForCausalLM
        torch.set_num_threads(threads)
        self.torch = torch
        hub = json.load(open(os.path.join(MODELS_DIR, key, "info.json")))["hub_id"]
        self.m = AutoModelForCausalLM.from_pretrained(hub, dtype=torch.float32).eval()

    def __call__(self, ids):
        with self.torch.inference_mode():
            return self.m(input_ids=self.torch.tensor(ids[None])).logits[0].float().numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--det", required=True, choices=["bino", "fdgpt"])
    ap.add_argument("--models", required=True)
    ap.add_argument("--prec", default="fp32")
    ap.add_argument("--backend", default="onnx", choices=["onnx", "torch"])
    ap.add_argument("--sets", default="all")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    keys = a.models.split(",")
    sets = ALL if a.sets == "all" else a.sets.split(",")
    name = f"{a.det}.{'+'.join(keys)}.{a.backend}-{a.prec}{a.tag}"

    from transformers import AutoTokenizer
    hub = json.load(open(os.path.join(MODELS_DIR, keys[0], "info.json")))["hub_id"]
    tok = AutoTokenizer.from_pretrained(hub)
    cls = OnnxLM if a.backend == "onnx" else TorchLM
    t0 = time.time()
    lms = [cls(k, a.prec, a.threads) for k in keys]
    load_s = time.time() - t0

    def score(text):
        ids = np.array(tok(text, truncation=True, max_length=MAX_TOKENS)["input_ids"], dtype=np.int64)
        if len(ids) < 2:
            return (-1.0 if a.det == "bino" else 0.0), ids
        if a.det == "bino":
            return binoculars(lms[0](ids), lms[1](ids), ids), ids
        return fast_detectgpt(lms[0](ids), ids), ids

    out = {"name": name, "det": a.det, "models": keys, "prec": a.prec, "backend": a.backend,
           "threads": a.threads, "load_seconds": load_s, "sets": {}}
    for s in sets:
        rows = [json.loads(l) for l in open(os.path.join(TEXTS, f"{s}.jsonl"), encoding="utf-8")]
        if a.limit:
            rows = rows[:a.limit]
        score(rows[0]["text"])  # warm-up
        ids_, scores, ntok, secs, toks = [], [], [], [], []
        for r in rows:
            t = time.perf_counter()
            v, ids = score(r["text"])
            secs.append(time.perf_counter() - t)
            ids_.append(r["id"]); scores.append(v); ntok.append(len(ids))
            if s == "parity":
                toks.append(ids.tolist())
        out["sets"][s] = {"ids": ids_, "scores": scores, "n_tokens": ntok, "seconds": secs,
                          "seconds_median": statistics.median(secs)}
        if toks:
            out["sets"][s]["token_ids"] = toks
        print(name, s, len(rows), f"median {statistics.median(secs) * 1000:.1f} ms", flush=True)
    out["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6  # bytes on macOS
    suffix = "" if a.sets == "all" else "." + a.sets.replace(",", "_")
    if a.limit:
        suffix += f".limit{a.limit}"
    if a.threads != 4:
        suffix += f".t{a.threads}"
    json.dump(out, open(os.path.join(RESULTS, name + suffix + ".json"), "w"))
    print("peak RSS MB", round(out["peak_rss_mb"]), "->", name + suffix)


if __name__ == "__main__":
    main()
