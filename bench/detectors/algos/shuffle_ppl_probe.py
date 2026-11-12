"""Checks of shuffle_ppl that need no fitted detector. Run from bench/detectors:

  python algos/shuffle_ppl_probe.py split      # splitter cases + shuffle modes per split
  python algos/shuffle_ppl_probe.py auroc      # AUROC of the .limitN smoke result files
  python algos/shuffle_ppl_probe.py smoke [lm]  # every variant, first 100 rows of test, test_fr
  python algos/shuffle_ppl_probe.py explain    # per-paragraph log-ratios of a mixed text
"""
from __future__ import annotations

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import RESULTS_DIR, load_split  # noqa: E402
import shuffle_ppl as sp  # noqa: E402


def split() -> None:
    cases = [
        "« Bonjour ! » dit-il. Vraiment ?",
        "Quel accueil ! Le personnel est charmant ; la chambre, propre. Vous y retournerez ?",
        "M. Dupont est arrivé. Il a dit : « Non. » Puis il est parti.",
        "Dr. Smith went home. He slept... Then he woke up! \"Really?\" she asked. Yes.",
        "super hotel. personnel sympa. je recommande",
        "Il coûte 3.5 euros, etc. C'est cher.",
    ]
    for c in cases:
        print(repr(c), "->", sp.split_sentences(c))
    p = sp.build_pair("A b c. D e f. G h i.\n\nOne two three four.", (0, 1, 2))
    print(p)
    ident = sp.build_pair("Only one sentence here.", (0,))
    print(ident["mode"], ident["orig"], "|", ident["shuf"])
    for name in ("train", "test", "test_ood", "test_fr", "test_fiction"):
        rows = load_split(name)
        modes = {"sentence": 0, "word": 0, "none": 0}
        for r in rows:
            # character-level stand-in for the 511-token cut (no tokenizer loaded here)
            modes[sp.build_pair(r["text"][:2200], (0,))["mode"]] += 1
        n = len(rows)
        print(name, n, {k: round(v / n, 4) for k, v in modes.items()})
    print(sp.split_paragraphs("Wrapped line one\nline two. Next sentence.\nSecond par:\n- item\n\nThird."))


def auroc() -> None:
    import numpy as np
    for path in sorted(glob.glob(os.path.join(RESULTS_DIR, "shuffle_ppl.*.limit*.json"))):
        r = json.load(open(path))
        labels = {x["id"]: x["label"] for x in load_split(r["split"])}
        y = np.asarray([labels[i] for i in r["ids"]])
        s = np.asarray(r["scores"])
        print(f"{os.path.basename(path):62s} n={len(y)} auroc={sp._auroc(s, y):.3f} "
              f"s/text median={r['seconds_per_text_median']:.3f}")


def explain() -> None:
    rows = load_split("test")
    h = next(r for r in rows if r["label"] == 0 and r["domain"] == "news" and r["n_words"] > 150)
    a = next(r for r in rows if r["label"] == 1 and r["generator"] == "chatgpt"
             and r["domain"] == "news" and r["n_words"] > 150)
    mixed = " ".join(h["text"].split()[:150]) + "\n\n" + " ".join(a["text"].split()[:150])
    for lm in ("gpt2", "smollm2-360m"):
        print(lm, json.dumps(sp.explain([mixed], lm=lm), ensure_ascii=False, indent=1))


def smoke() -> None:
    """Every variant on the first 100 rows of test and test_fr, from ONE extraction per
    LM and split (lp and 3 shuffles), instead of 18 runs of run.py that would redo the
    same forward passes. Same functions as Detector.score. Writes nothing to results/."""
    import numpy as np
    from common import BENCH_DIR
    lms = sys.argv[2:] or list(sp._MODELS)
    train = load_split("train")
    for lm in lms:
        for name in ("test", "test_fr"):
            rows = load_split(name, 100)
            path = os.path.join(BENCH_DIR, "scratch", f"shufppl_smoke.{lm}.{name}.json")
            if os.path.exists(path):
                raw = json.load(open(path))
            else:
                raw = [sp._raw(lm, r["text"], sp.N_SEEDS) for r in rows]
                json.dump(raw, open(path, "w"))
            y = np.asarray([r["label"] for r in rows])
            lp = np.asarray([r["lp"] for r in raw])
            modes = [r["mode"] for r in raw]
            print(f"## {lm} {name} n={len(y)} ai={int(y.sum())} word-mode="
                  f"{modes.count('word')} zero-signal={modes.count('none')}")
            lrs = np.asarray([[s - r["lp"] for s in r["lps"]] for r in raw])
            print("  raw +logratio AUROC per seed:",
                  [round(sp._auroc(lrs[:, k], y), 3) for k in range(sp.N_SEEDS)],
                  "avg3:", round(sp._auroc(lrs.mean(axis=1), y), 3),
                  "seed corr 0-1, 0-2:", np.corrcoef(lrs.T)[0, 1:].round(3).tolist(),
                  "corr seed0 vs avg3:", round(float(np.corrcoef(lrs[:, 0], lrs.mean(axis=1))[0, 1]), 3))
            for v, make in sp.VARIANTS.items():
                if not v.startswith(lm + "-"):
                    continue
                det = make()
                if det.NEEDS_TRAINING:
                    det.fit(train)
                x = np.asarray([sp.features_from(r["lp"], r["lps"][:max(1, det.n_shuf)])
                                for r in raw])
                s = np.asarray(det.score_features(x, lp))
                extra = f" sign={det.state['sign']:+.0f}" if "sign" in det.state else ""
                if det.kind == "density":
                    extra += f" rejects(score 0.5)={int((s == 0.5).sum())}"
                sm = np.asarray([m == "sentence" for m in modes])
                print(f"  {v:28s} AUROC={sp._auroc(s, y):.3f} "
                      f"sentence-mode only={sp._auroc(s[sm], y[sm]):.3f}{extra}")


if __name__ == "__main__":
    {"split": split, "auroc": auroc, "explain": explain, "smoke": smoke}[sys.argv[1]]()
