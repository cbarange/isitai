#!/usr/bin/env python
"""Export causal LMs to ONNX (logits only, no KV cache), quantise, record sizes.

  HF_HOME=/tmp/isitai-bench/hf /tmp/isitai-deep/venv/bin/python bench/deep-spike/export_onnx.py KEY [KEY...]

Writes /tmp/isitai-deep/models/<key>/{fp32.onnx,int8.onnx,fp16.onnx?,tokenizer.json,info.json}.
"""
from __future__ import annotations

import collections
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys

os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")
import numpy as np
import onnx
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

OUT = "/tmp/isitai-deep/models"
MODELS = {
    "smollm2-135m": "HuggingFaceTB/SmolLM2-135M",
    "smollm2-135m-instruct": "HuggingFaceTB/SmolLM2-135M-Instruct",
    "neo125": "EleutherAI/gpt-neo-125m",
    "smollm2-360m": "HuggingFaceTB/SmolLM2-360M",
    "qwen2.5-0.5b": "Qwen/Qwen2.5-0.5B",
}


class Wrap(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, input_ids):
        return self.m(input_ids=input_ids, use_cache=False).logits


def sizes(path: str) -> dict:
    raw = os.path.getsize(path)
    h = hashlib.sha256()
    gz = 0
    comp = gzip.GzipFile(fileobj=(sink := _Count()), mode="wb", compresslevel=6)
    with open(path, "rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
            comp.write(chunk)
    comp.close()
    gz = sink.n
    z = int(subprocess.run(f"zstd -19 -T0 -c '{path}' | wc -c", shell=True, capture_output=True,
                           text=True).stdout.strip())
    return {"bytes": raw, "gzip6": gz, "zstd19": z, "sha256": h.hexdigest()}


class _Count:
    n = 0

    def write(self, b):
        self.n += len(b)
        return len(b)

    def flush(self):
        pass


def ops(path: str) -> dict:
    m = onnx.load(path, load_external_data=False)
    c = collections.Counter(n.op_type for n in m.graph.node)
    return dict(c.most_common())


def main():
    for key in sys.argv[1:]:
        hub = MODELS[key]
        d = os.path.join(OUT, key)
        os.makedirs(d, exist_ok=True)
        info = {"hub_id": hub}
        tok = AutoTokenizer.from_pretrained(hub)
        tok.backend_tokenizer.save(os.path.join(d, "tokenizer.json"))
        model = AutoModelForCausalLM.from_pretrained(hub, dtype=torch.float32).eval()
        info["params"] = sum(p.numel() for p in model.parameters())
        fp32 = os.path.join(d, "fp32.onnx")
        ids = torch.tensor([tok("The quick brown fox jumps over the lazy dog.")["input_ids"]])
        exporter = "legacy"
        try:
            torch.onnx.export(Wrap(model), (ids,), fp32, input_names=["input_ids"],
                              output_names=["logits"], opset_version=17, dynamo=False,
                              dynamic_axes={"input_ids": {0: "b", 1: "t"}, "logits": {0: "b", 1: "t"}})
        except Exception as e:  # noqa: BLE001
            print("legacy exporter failed:", repr(e)[:300])
            exporter = "dynamo"
            b, t = torch.export.Dim("b", max=4), torch.export.Dim("t", min=2, max=2048)
            prog = torch.onnx.export(Wrap(model), (ids,), dynamo=True, input_names=["input_ids"],
                                     output_names=["logits"], dynamic_shapes={"input_ids": {0: b, 1: t}})
            prog.save(fp32)
        info["exporter"] = exporter
        # single-file fp32 (no external data) when it fits
        m = onnx.load(fp32)
        for f in os.listdir(d):
            if f not in ("tokenizer.json",) and not f.endswith(".json"):
                os.remove(os.path.join(d, f))
        onnx.save(m, fp32)
        del m

        from onnxruntime.quantization import QuantType, quantize_dynamic
        int8 = os.path.join(d, "int8.onnx")
        quantize_dynamic(fp32, int8, weight_type=QuantType.QInt8)
        # variant: MatMul only (embedding Gather stays fp32)
        int8mm = os.path.join(d, "int8-matmul.onnx")
        try:
            quantize_dynamic(fp32, int8mm, weight_type=QuantType.QInt8, op_types_to_quantize=["MatMul"])
        except Exception as e:  # noqa: BLE001
            info["int8_matmul_error"] = repr(e)[:300]
        fp16 = os.path.join(d, "fp16.onnx")
        try:
            from onnxruntime.transformers.float16 import convert_float_to_float16
            m16 = convert_float_to_float16(onnx.load(fp32), keep_io_types=True)
            onnx.save(m16, fp16)
        except Exception as e:  # noqa: BLE001
            info["fp16_error"] = repr(e)[:300]

        info["files"] = {}
        for f in sorted(os.listdir(d)):
            if f.endswith(".onnx"):
                p = os.path.join(d, f)
                info["files"][f] = {**sizes(p), "ops": ops(p)}
        info["files"]["tokenizer.json"] = sizes(os.path.join(d, "tokenizer.json"))
        snap = os.path.dirname(tok.vocab_file) if getattr(tok, "vocab_file", None) else None
        json.dump(info, open(os.path.join(d, "info.json"), "w"), indent=1)
        print(key, exporter, info["params"],
              {k: (v["bytes"], v["gzip6"], v["zstd19"]) for k, v in info["files"].items()})
        del model


if __name__ == "__main__":
    main()
