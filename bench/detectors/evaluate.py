#!/usr/bin/env python
"""Reads every result file of /tmp/isitai-bench/results and the data splits, prints a
summary and writes summary.json and summary.md next to the results.

  /tmp/isitai-bench/venv/bin/python evaluate.py [--algo NAME ...] [--bootstrap 1000]

Definitions
  label            0 human, 1 AI; a score is HIGHER when the text is MORE LIKELY AI.
  AUROC            probability that a random AI text scores above a random human text
                   (ties count one half).
  threshold at x%  the lowest threshold t such that the share of human texts with
                   score > t is at most x%. A text is flagged when score > t. With tied
                   scores the achieved FPR can be below x%; it is reported ("fpr").
  TPR@x%FPR        share of AI texts flagged at that threshold, the threshold being taken
                   on the human texts of the SAME split.
  transfer         TPR and FPR on a split at the threshold taken on `test`. This is what a
                   shipped detector with a fixed threshold would do there.
  intervals        95% percentile bootstrap, stratified by label, fixed seed; same-split
                   thresholds are recomputed inside each resample, transferred thresholds
                   stay fixed.
  breakdowns       generator: the AI texts of one generator against ALL human texts of the
                   split. domain / length / source / attack: both classes inside the slice
                   (AUROC is null when a class is missing); TPR and FPR use the thresholds
                   of the whole split.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import defaultdict

import numpy as np
from scipy.stats import rankdata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import DATA_DIR, RESULTS_DIR, SPLITS, LENGTH_BUCKETS, length_bucket, load_split  # noqa: E402

SEED = 20261112
TARGETS = (0.01, 0.05)


def auroc(h: np.ndarray, a: np.ndarray):
    if len(h) == 0 or len(a) == 0:
        return None
    ranks = rankdata(np.concatenate([h, a]))
    return float((ranks[len(h):].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(h)))


def threshold(h: np.ndarray, target: float) -> float:
    """Lowest t with mean(h > t) <= target."""
    if len(h) == 0:
        return float("inf")
    m = int(np.floor(target * len(h) + 1e-9))
    hs = np.sort(h)[::-1]
    return float(hs[m]) if m < len(hs) else float("-inf")


def rate(x: np.ndarray, t: float):
    return float(np.mean(x > t)) if len(x) else None


def ci(values) -> list | None:
    values = [v for v in values if v is not None]
    if not values:
        return None
    lo, hi = np.percentile(values, [2.5, 97.5])
    return [float(lo), float(hi)]


def core_metrics(h, a, n_boot, rng, fixed=None):
    """Metrics of one (algo, split). `fixed` = {target: threshold taken on test}."""
    out = {"n": int(len(h) + len(a)), "n_human": int(len(h)), "n_ai": int(len(a)),
           "auroc": auroc(h, a)}
    thr = {t: threshold(h, t) for t in TARGETS}
    for t in TARGETS:
        key = f"{int(t * 100)}"
        out[f"thr@{key}"] = thr[t]
        out[f"tpr@{key}"] = rate(a, thr[t])
        out[f"fpr@{key}"] = rate(h, thr[t])
        if fixed is not None:
            out[f"transfer_thr@{key}"] = fixed[t]
            out[f"transfer_tpr@{key}"] = rate(a, fixed[t])
            out[f"transfer_fpr@{key}"] = rate(h, fixed[t])
    if n_boot and len(h) and len(a):
        boot = defaultdict(list)
        for _ in range(n_boot):
            hb = h[rng.integers(0, len(h), len(h))]
            ab = a[rng.integers(0, len(a), len(a))]
            boot["auroc"].append(auroc(hb, ab))
            for t in TARGETS:
                key = f"{int(t * 100)}"
                boot[f"tpr@{key}"].append(rate(ab, threshold(hb, t)))
                if fixed is not None:
                    boot[f"transfer_tpr@{key}"].append(rate(ab, fixed[t]))
                    boot[f"transfer_fpr@{key}"].append(rate(hb, fixed[t]))
        for k, v in boot.items():
            out[f"{k}_ci95"] = ci(v)
    return out


def slice_metrics(h, a, thr, h_all=None):
    """Breakdown row. With h_all (generator slices) AUROC is against all humans."""
    ref = h_all if h_all is not None else h
    out = {"n_human": int(len(h)), "n_ai": int(len(a)),
           "auroc": auroc(ref, a) if len(ref) and len(a) else None}
    for t in TARGETS:
        key = f"{int(t * 100)}"
        out[f"tpr@{key}"] = rate(a, thr[t])
        out[f"fpr@{key}"] = rate(h, thr[t])
    return out


def load_results(algos, sample=False):
    """Full-split result files; with sample=True also the .sample files (a full file wins)."""
    results = {}
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "*.json"))):
        name = os.path.basename(path)
        if name.startswith("summary"):
            continue
        try:
            with open(path) as f:
                r = json.load(f)
        except (json.JSONDecodeError, OSError):
            print(f"skip unreadable {name}", file=sys.stderr)
            continue
        if not isinstance(r, dict) or "scores" not in r or r.get("limit"):
            continue
        if algos and r["algo"] not in algos and r.get("module") not in algos:
            continue
        if r.get("sample"):
            if not sample or (r["algo"], r["split"]) in results:
                continue
        results[(r["algo"], r["split"])] = r
    return results


def fmt(x, pct=False, digits=3):
    if x is None:
        return "-"
    return f"{100 * x:.1f}" if pct else f"{x:.{digits}f}"


def fmt_ci(m, key, pct=False):
    c = m.get(f"{key}_ci95")
    base = fmt(m.get(key), pct)
    if not c:
        return base
    return f"{base} [{fmt(c[0], pct)}, {fmt(c[1], pct)}]"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--algo", action="append", help="restrict to these detectors (repeatable)")
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--sample", action="store_true",
                    help="evaluate EVERY detector on the fixed subsample of each split "
                         "(data/samples/<split>.ids.json), including the detectors that were "
                         "only run on it (run.py --sample); writes summary_sample.json / .md")
    args = ap.parse_args()

    data = {}
    for split in SPLITS:
        if os.path.exists(os.path.join(DATA_DIR, f"{split}.jsonl")):
            data[split] = {r["id"]: r for r in load_split(split)}
            ids_path = os.path.join(DATA_DIR, "samples", f"{split}.ids.json")
            if args.sample and os.path.exists(ids_path):
                with open(ids_path) as f:
                    keep = set(json.load(f))
                data[split] = {i: r for i, r in data[split].items() if i in keep}
    results = load_results(set(args.algo or []), sample=args.sample)
    algos = sorted({a for a, _ in results})
    summary = {"seed": SEED, "bootstrap": args.bootstrap, "targets": list(TARGETS),
               "splits": {s: len(d) for s, d in data.items()}, "detectors": {}}

    for algo in algos:
        entry = {"splits": {}}
        test_thr = None
        order = ["test"] + [s for s in SPLITS if s != "test"]
        for split in order:
            r = results.get((algo, split))
            if r is None or split not in data:
                continue
            rows = data[split]
            score_of = dict(zip(r["ids"], r["scores"]))
            missing = [i for i in rows if i not in score_of]
            if missing:
                print(f"skip {algo} {split}: {len(missing)} of {len(rows)} ids have no score "
                      f"(stale result file: rerun it)", file=sys.stderr)
                continue
            ids = list(rows)
            y = np.array([rows[i]["label"] for i in ids])
            s = np.array([score_of[i] for i in ids], dtype=float)
            h, a = s[y == 0], s[y == 1]
            rng = np.random.default_rng(SEED)
            m = core_metrics(h, a, args.bootstrap, rng,
                             fixed=test_thr if (test_thr and split != "test") else None)
            thr = {t: m[f"thr@{int(t * 100)}"] for t in TARGETS}
            if split == "test":
                test_thr = thr

            def breakdown(key_fn, generator=False):
                groups = defaultdict(list)
                for j, i in enumerate(ids):
                    k = key_fn(rows[i])
                    if k is not None:
                        groups[k].append(j)
                out = {}
                for k in sorted(groups, key=str):
                    idx = np.array(groups[k])
                    hs, as_ = s[idx][y[idx] == 0], s[idx][y[idx] == 1]
                    out[str(k)] = slice_metrics(hs, as_, thr, h_all=h if generator else None)
                return out

            m["by_generator"] = breakdown(lambda r_: r_["generator"] if r_["label"] == 1 else None, True)
            m["by_domain"] = breakdown(lambda r_: r_["domain"])
            m["by_source"] = breakdown(lambda r_: r_["source"])
            by_len = breakdown(lambda r_: length_bucket(r_["n_words"]))
            m["by_length"] = {b[0]: by_len[b[0]] for b in LENGTH_BUCKETS if b[0] in by_len}
            if any("attack" in rows[i] for i in ids):
                m["by_attack"] = breakdown(lambda r_: r_.get("attack"))
            m["speed"] = {k: r.get(k) for k in (
                "seconds_total", "seconds_per_text_median", "seconds_per_text_p90",
                "seconds_per_text_batched", "timing_n", "batch_size", "peak_rss_mb",
                "fit_seconds", "load_seconds", "threads")}
            entry["splits"][split] = m
            entry["model"] = r.get("model")
            entry["needs_training"] = r.get("needs_training")
        if entry["splits"]:
            summary["detectors"][algo] = entry

    # ---------------------------------------------------------------- markdown
    L = ["# Detector benchmark summary" + (" (fixed subsample of each split)" if args.sample else ""), "",
         f"Splits: " + ", ".join(f"{s} ({n})" for s, n in summary["splits"].items()) + ".",
         f"Intervals: 95% bootstrap, {args.bootstrap} resamples, stratified by label, seed {SEED}.",
         "TPR and FPR in %. `TPR@1%` uses the threshold of the same split; `xfer` columns use "
         "the threshold fixed on `test`. `FPR got` is the false-positive rate actually reached "
         "at the same-split 1% threshold (ties can push it below 1%).", ""]
    dets = summary["detectors"]
    for split in [s for s in SPLITS if any(s in d["splits"] for d in dets.values())]:
        L += [f"## {split}", "",
              "| detector | AUROC | TPR@1%FPR | TPR@5%FPR | FPR got @1% | xfer TPR@1% | xfer FPR@1% | xfer TPR@5% | xfer FPR@5% |",
              "|---|---|---|---|---|---|---|---|---|"]
        for algo, d in dets.items():
            m = d["splits"].get(split)
            if not m:
                continue
            L.append(f"| {algo} | {fmt_ci(m, 'auroc')} | {fmt_ci(m, 'tpr@1', True)} | "
                     f"{fmt_ci(m, 'tpr@5', True)} | {fmt(m.get('fpr@1'), True)} | "
                     f"{fmt_ci(m, 'transfer_tpr@1', True)} | {fmt_ci(m, 'transfer_fpr@1', True)} | "
                     f"{fmt_ci(m, 'transfer_tpr@5', True)} | {fmt_ci(m, 'transfer_fpr@5', True)} |")
        L.append("")
    L += ["## Speed and memory", "",
          "CPU, 4 threads. `ms/text` = median of batch-of-1 calls; `ms/text batched` = scoring "
          "pass time / n. Measured on the `test` split when present.", "",
          "| detector | trained | model | ms/text (median) | ms/text (p90) | ms/text batched | fit s | peak RSS MB |",
          "|---|---|---|---|---|---|---|---|"]
    for algo, d in dets.items():
        split = "test" if "test" in d["splits"] else next(iter(d["splits"]))
        sp = d["splits"][split]["speed"]

        def ms(k):
            return "-" if sp.get(k) is None else f"{1000 * sp[k]:.3f}"
        L.append(f"| {algo} | {'yes' if d.get('needs_training') else 'no'} | {d.get('model')} | "
                 f"{ms('seconds_per_text_median')} | {ms('seconds_per_text_p90')} | "
                 f"{ms('seconds_per_text_batched')} | {sp.get('fit_seconds') or 0:.1f} | "
                 f"{sp.get('peak_rss_mb') or 0:.0f} |")
    L.append("")
    for title, key in (("generator", "by_generator"), ("domain", "by_domain"),
                       ("length (words)", "by_length"), ("attack", "by_attack")):
        L += [f"## Breakdown by {title}", "",
              "AUROC / TPR@1% / FPR@1% (thresholds of the whole split), n = human+AI in the slice.", ""]
        for split in SPLITS:
            keys = []
            for d in dets.values():
                for k in d["splits"].get(split, {}).get(key, {}):
                    if k not in keys:
                        keys.append(k)
            if not keys:
                continue
            L += [f"### {split}", "", "| detector | " + " | ".join(keys) + " |",
                  "|---|" + "---|" * len(keys)]
            for algo, d in dets.items():
                b = d["splits"].get(split, {}).get(key)
                if not b:
                    continue
                cells = []
                for k in keys:
                    x = b.get(k)
                    cells.append("-" if not x else
                                 f"{fmt(x['auroc'])} / {fmt(x['tpr@1'], True)} / {fmt(x['fpr@1'], True)} "
                                 f"(n={x['n_human']}+{x['n_ai']})")
                L.append(f"| {algo} | " + " | ".join(cells) + " |")
            L.append("")
    md = "\n".join(L)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    stem = "summary_sample" if args.sample else "summary"
    for name, content in ((f"{stem}.json", json.dumps(summary, indent=1)), (f"{stem}.md", md)):
        tmp = os.path.join(RESULTS_DIR, f"{name}.{os.getpid()}.tmp")
        with open(tmp, "w") as f:
            f.write(content)
        os.replace(tmp, os.path.join(RESULTS_DIR, name))
    print(md)


if __name__ == "__main__":
    main()
