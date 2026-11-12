#!/usr/bin/env python
"""Runs one detector on one or several splits and writes one result file per split.

  /tmp/isitai-bench/venv/bin/python run.py --algo NAME [--variant V] --split SPLIT [--limit N]

--split takes one split, a comma-separated list, or "all" (every split that exists except
train). The detector is loaded and fitted ONCE per process, then scores every split asked.

Result: /tmp/isitai-bench/results/<name>[.<variant>].<split>.json
        (with --limit N: ...<split>.limit<N>.json, which evaluate.py ignores)

Timing protocol, CPU only, 4 threads:
  seconds_total            wall time of the scoring pass that produced `scores`: score()
                           called on consecutive chunks of BATCH_SIZE texts (module
                           attribute, default 16).
  seconds_per_text_median  median wall time of score([text]) (batch of 1) over a seeded
                           sample of up to --time-n texts of the split (default 100), after
                           one warm-up call that is not counted. Measured BEFORE the
                           scoring pass.
  fit_seconds              wall time of fit() on the train split (0 when not trained).
  peak_rss_mb              peak resident memory of the process (load + fit + scoring).
"""
from __future__ import annotations

import os

THREADS = 4
for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
             "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "RAYON_NUM_THREADS"):
    os.environ[_var] = str(THREADS)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("HF_HOME", "/tmp/isitai-bench/hf")

import argparse  # noqa: E402
import functools  # noqa: E402
import importlib  # noqa: E402
import importlib.abc  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import random  # noqa: E402
import resource  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from common import RESULTS_DIR, SPLITS, DATA_DIR, load_split  # noqa: E402


class _PinTorchOnImport(importlib.abc.MetaPathFinder):
    """Runs pin_torch() the moment torch finishes importing, so that a detector which
    builds its model at import time already sees a CPU-only torch."""

    _busy = False

    def find_spec(self, name, path, target=None):
        # Stays installed: libraries probe `find_spec("torch")` without importing it.
        if name != "torch" or self._busy:
            return None
        self._busy = True
        try:
            spec = importlib.util.find_spec("torch")
        finally:
            self._busy = False
        if spec is None or spec.loader is None:
            return None
        original = spec.loader.exec_module

        def exec_module(module):
            original(module)
            pin_torch()

        spec.loader.exec_module = exec_module
        return spec


def mps_in_use() -> bool:
    torch = sys.modules.get("torch")
    try:
        return bool(torch is not None and torch.mps.current_allocated_memory() > 0)
    except Exception:
        return False


def pin_torch() -> None:
    """If the detector imported torch: 4 threads, CPU only (no MPS, no CUDA)."""
    torch = sys.modules.get("torch")
    if torch is None:
        return
    try:
        torch.set_num_threads(THREADS)
    except RuntimeError:
        pass
    try:
        if not getattr(torch.backends.mps.is_available, "_isitai_bench", False):
            # lru_cache keeps the attributes of the original (libraries read __wrapped__)
            off = functools.lru_cache(None)(lambda: False)
            off._isitai_bench = True
            torch.backends.mps.is_available = off
    except Exception:
        pass


def peak_rss_mb() -> float:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # bytes on macOS, kilobytes on Linux
    return rss / (1024 * 1024) if sys.platform == "darwin" else rss / 1024


def load_detector(algo: str, variant: str | None):
    module = importlib.import_module(f"algos.{algo}")
    if variant is None:
        if not hasattr(module, "score"):
            raise SystemExit(f"algos/{algo}.py has no score(); choose --variant among "
                             f"{sorted(getattr(module, 'VARIANTS', {}))}")
        return module, algo
    variants = getattr(module, "VARIANTS", None)
    if not variants or variant not in variants:
        raise SystemExit(f"algos/{algo}.py has no variant {variant!r}; "
                         f"available: {sorted(variants or {})}")
    return variants[variant](), f"{algo}.{variant}"


def check_scores(scores, n: int) -> list[float]:
    scores = [float(s) for s in scores]
    if len(scores) != n:
        raise SystemExit(f"score() returned {len(scores)} values for {n} texts")
    bad = [i for i, s in enumerate(scores) if not math.isfinite(s)]
    if bad:
        raise SystemExit(f"score() returned non-finite values (first at index {bad[0]})")
    return scores


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--algo", required=True)
    ap.add_argument("--variant")
    ap.add_argument("--split", required=True, help='one split, "a,b,c", or "all"')
    ap.add_argument("--limit", type=int, help="first N rows only (smoke test; file gets a .limitN suffix)")
    ap.add_argument("--time-n", type=int, default=100, help="texts timed one by one for the median")
    ap.add_argument("--sample", action="store_true",
                    help="score only the fixed random subsample of each split "
                         "(data/samples/<split>.ids.json, built by make_samples.py); the file "
                         "gets a .sample suffix and evaluate.py --sample reads it")
    args = ap.parse_args()

    if args.split == "all":
        splits = [s for s in SPLITS if s != "train" and os.path.exists(os.path.join(DATA_DIR, f"{s}.jsonl"))]
    else:
        splits = [s.strip() for s in args.split.split(",") if s.strip()]

    sys.meta_path.insert(0, _PinTorchOnImport())
    t0 = time.perf_counter()
    det, label = load_detector(args.algo, args.variant)
    pin_torch()
    load_seconds = time.perf_counter() - t0

    needs_training = bool(getattr(det, "NEEDS_TRAINING", False))
    fit_seconds = 0.0
    n_train = 0
    if needs_training:
        train = load_split("train")
        n_train = len(train)
        t0 = time.perf_counter()
        det.fit(train)
        fit_seconds = time.perf_counter() - t0
        pin_torch()
        print(f"[{label}] fit on {n_train} train rows: {fit_seconds:.1f}s", file=sys.stderr)

    batch_size = int(getattr(det, "BATCH_SIZE", 16))
    os.makedirs(RESULTS_DIR, exist_ok=True)
    for split in splits:
        rows = load_split(split, args.limit)
        if args.sample:
            with open(os.path.join(DATA_DIR, "samples", f"{split}.ids.json")) as f:
                keep = set(json.load(f))
            rows = [r for r in rows if r["id"] in keep]
        texts = [r["text"] for r in rows]
        ids = [r["id"] for r in rows]

        # 1. batch-of-1 timing on a seeded sample, BEFORE the scoring pass (so a detector
        #    that memoises per text cannot answer from its cache), after one uncounted
        #    warm-up call on a text outside the sample when there is one
        rng = random.Random(0)
        sample = list(range(len(texts)))
        rng.shuffle(sample)
        k = max(1, min(args.time_n, len(texts)))
        warm = sample[k] if len(sample) > k else sample[0]
        sample = sample[:k]
        pin_torch()
        det.score([texts[warm]])
        per_text = []
        for i in sample:
            pin_torch()
            t1 = time.perf_counter()
            det.score([texts[i]])
            per_text.append(time.perf_counter() - t1)
        per_text.sort()

        # 2. the scoring pass (chunks of batch_size): gives the scores and seconds_total
        scores: list[float] = []
        t0 = time.perf_counter()
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            scores.extend(check_scores(det.score(chunk), len(chunk)))
        seconds_total = time.perf_counter() - t0
        pin_torch()
        if mps_in_use():
            raise SystemExit(f"[{label}] the detector allocated memory on MPS: timings would "
                             f"not be CPU timings. Pass device=\"cpu\" explicitly.")

        result = {
            "algo": label,
            "module": args.algo,
            "variant": args.variant,
            "split": split,
            "n": len(texts),
            "scores": scores,
            "ids": ids,
            "seconds_total": seconds_total,
            "seconds_per_text_median": statistics.median(per_text),
            "seconds_per_text_p90": per_text[min(len(per_text) - 1, int(0.9 * len(per_text)))],
            "seconds_per_text_batched": seconds_total / max(1, len(texts)),
            "timing_n": len(per_text),
            "batch_size": batch_size,
            "peak_rss_mb": peak_rss_mb(),
            "fit_seconds": fit_seconds,
            "load_seconds": load_seconds,
            "threads": THREADS,
            "needs_training": needs_training,
            "n_train": n_train,
            "model": str(getattr(det, "MODEL", "none")),
            "limit": args.limit,
            "sample": bool(args.sample),
            "platform": f"{platform.system()} {platform.machine()} python {platform.python_version()}",
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        suffix = f".limit{args.limit}" if args.limit else ""
        if args.sample:
            suffix += ".sample"
        path = os.path.join(RESULTS_DIR, f"{label}.{split}{suffix}.json")
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump(result, f)
        os.replace(tmp, path)
        print(f"[{label}] {split}: n={len(texts)} total={seconds_total:.2f}s "
              f"median/text={result['seconds_per_text_median'] * 1000:.2f}ms "
              f"peak_rss={result['peak_rss_mb']:.0f}MB -> {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
