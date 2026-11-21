#!/usr/bin/env python
"""Rust versus Python (onnxruntime) on the 120 parity texts: token ids, score differences,
time per text, peak RSS. Reads /tmp/isitai-deep/rust-runs/*.jsonl and the Python result files."""
import glob
import json
import os
import re
import statistics

RES = "/tmp/isitai-deep/results"
PAIR = "smollm2-135m+smollm2-135m-instruct"


def py_scores(det, prec):
    name = f"bino.{PAIR}.onnx-{prec}" if det == "bino" else f"fdgpt.{det.split('-', 1)[1]}.onnx-{prec}"
    out = {}
    for p in glob.glob(f"{RES}/{name}*.json"):
        d = json.load(open(p))
        if d["threads"] != 4 or d["name"] != name:  # exact name: "int8" must not match "int8-matmul"
            continue
        for s in d["sets"].values():
            out.update(zip(s["ids"], s["scores"]))
    return out


py_tok = {}
for m in ("smollm2-135m", "neo125"):
    tok = json.load(open(f"{RES}/fdgpt.{m}.onnx-fp32.parity.json"))["sets"]["parity"]
    py_tok[m] = dict(zip(tok["ids"], tok["token_ids"]))
print("| Runtime | detector | precision | threads | n | token ids equal | max abs diff vs Python ORT | mean abs diff | median ms/text | of which model forward | p90 ms | median tokens | peak RSS MB |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for p in sorted(glob.glob("/tmp/isitai-deep/rust-runs/*.jsonl")):
    rt, det, prec, t = os.path.basename(p)[:-6].rsplit(".", 3)
    rows = [json.loads(l) for l in open(p)]
    if not rows:
        print(f"| {rt} | {det} | {prec} | {t[1:]} | 0 | FAILED | | | | | |")
        continue
    ref = py_scores(det, prec)
    pt = py_tok["neo125" if det.endswith("neo125") else "smollm2-135m"]
    same = sum(r["token_ids"] == pt[r["id"]] for r in rows)
    d = [abs(r["score"] - ref[r["id"]]) for r in rows if r["id"] in ref]
    ms = sorted(r["ms"] for r in rows)
    rss = re.search(r"(\d+)\s+maximum resident set size", open(p[:-6] + ".time").read())
    if not rss:
        continue  # run in progress
    dm = f"{max(d):.2e} | {statistics.mean(d):.2e}" if d else "n/a | n/a"
    print(f"| {rt} | {det} | {prec} | {t[1:]} | {len(rows)} | {same}/{len(rows)} | {dm} | "
          f"{statistics.median(ms):.0f} | {statistics.median(r.get('ms_infer', float('nan')) for r in rows):.0f} | "
          f"{ms[int(0.9 * len(ms))]:.0f} | {statistics.median(r['n_tokens'] for r in rows):.0f} | {int(rss.group(1)) / 1e6:.0f} |")

print()
print("| int8, same texts | n | max abs diff | mean abs diff |")
print("|---|---|---|---|")
D = "/tmp/isitai-deep/rust-runs"
for det in ("bino", "fdgpt-smollm2-135m", "fdgpt-neo125"):
    try:
        a = {r["id"]: r["score"] for r in map(json.loads, open(f"{D}/ort-dyn.{det}.int8.t4.jsonl"))}
        b = {r["id"]: r["score"] for r in map(json.loads, open(f"{D}/rten.{det}.int8.t4.jsonl"))}
    except FileNotFoundError:
        continue
    d = [abs(a[i] - b[i]) for i in a if i in b]
    if d:
        print(f"| {det}: rten vs ort (Rust) | {len(d)} | {max(d):.2e} | {statistics.mean(d):.2e} |")
