#!/usr/bin/env python
"""Fits, calibrates, measures and exports the light text score (`light-text-v1`).

Steps, in this order (each choice is made before the test splits are read):
 1. feature selection by sign invariance on the pool (see `invariant_columns`);
 2. leave-one-family-out scores of the pool: every text is scored by a model that never
    saw its source family. Calibration uses ONLY these out-of-family scores;
 3. minimum length from the truncation curve;
 4. per-language calibration table (admission rule: `admit`), likelihood ratio by a
    class-balanced logistic fit, 90 % interval by bootstrap, thresholds by the conformal
    quantile of the native human scores;
 5. final model on the whole pool, export to crates/isitai-core/model/light-text-v1.json;
 6. measurement on the benchmark test splits, the Wikipedia corpus and the golden set
    (read-only: nothing is tuned on them), written to bench/light/results.json;
 7. parity fixture for `cargo test` (crates/isitai-core/tests/fixtures/light_parity.json).

Run:  /tmp/isitai-bench/venv/bin/python bench/light/train.py
"""
from __future__ import annotations

import json
import math
import multiprocessing
import sys
import warnings
from pathlib import Path

import numpy as np

from common import CLIP_Z, TRAIN_MIN_WORDS, Model, auroc, load
import features as F

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent.parent
LIGHT = Path("/tmp/isitai-bench/light")
MODEL_PATH = ROOT / "crates/isitai-core/model/light-text-v1.json"
FIXTURE_PATH = ROOT / "crates/isitai-core/tests/fixtures/light_parity.json"
RESULTS_PATH = ROOT / "bench/light/results.json"

DETECTOR = "text-light-v1"
TABLE_DATE = "2026-11-12"
SEED = 20261113
FAMILIES = ("raid", "hc3", "mage", "reviews", "faq")
C = 0.1
SELECT_MIN_WORDS = 100          # texts used to select features and to study thresholds
INVARIANCE_MARGIN = 0.03
LENGTH_GRID = (30, 50, 75, 100, 150, 200, 300)
BUCKETS = (100, 150, 200, 300)   # candidate lower bounds of the calibration length buckets
COVERAGE = 0.90
BOOTSTRAP = 1000
GRID_POINTS = 33
ALPHA_HIGH, ALPHA_MEDIUM = 0.01, 0.05
# `ai-likely` needs the score above the 1 % threshold AND the lower bound of the interval
# of ln LR above this value. 0 = "the whole interval says AI rather than human". Raising it
# (ln 10 = 2.3 is "moderate support" on the forensic scale) is the owner's decision.
AI_LIKELY_MIN_LN_LR_LOW = 0.0
# Admission of a language (written before any score was looked at): at or above the
# minimum length, out-of-family scores of at least 200 native human texts from at least
# 2 source families, and of at least 200 AI texts from at least 2 source families.
ADMIT_MIN_TEXTS, ADMIT_MIN_FAMILIES = 200, 2
# Machine-translated human answers are not human writing in the target language.
TRANSLATED_PREFIX = "hc3fr-mt-"


# ------------------------------------------------------------------ selection

def invariant_columns(d, mask) -> list:
    """Features whose univariate AUROC is on the same side of 0.5 in every
    (family, language) cell with at least 50 human and 20 AI texts, and at least
    INVARIANCE_MARGIN away from 0.5 on average. A feature that says "AI" in one source
    and "human" in another is a property of the source, not of the author."""
    cols = []
    cells = [(f, l) for f in FAMILIES for l in ("en", "fr")]
    for j, name in enumerate(F.SCALAR_FEATURES):
        devs = []
        for fam, lang in cells:
            m = mask & (d["family"] == fam) & (d["lang"] == lang) & (d["nw"] >= SELECT_MIN_WORDS)
            y = d["y"][m]
            if (y == 0).sum() >= 50 and (y == 1).sum() >= 20:
                devs.append(auroc(y, d["X"][m][:, j]) - 0.5)
        devs = np.array(devs)
        if len(devs) and (np.all(devs > 0) or np.all(devs < 0)) \
                and np.abs(devs).mean() >= INVARIANCE_MARGIN:
            cols.append(j)
    return cols


def out_of_family_scores(d):
    """Score of every pool row by a model fitted without its family (features selected
    without it too). Also the per-family transfer table."""
    oof = np.full(len(d["y"]), np.nan)
    transfer = {}
    for fam in FAMILIES:
        train_mask = (d["nw"] >= TRAIN_MIN_WORDS) & (d["family"] != fam)
        tr = np.nonzero(train_mask)[0]
        model = Model(invariant_columns(d, train_mask), c=C).fit(d, tr)
        te = np.nonzero(d["family"] == fam)[0]
        oof[te] = model.score(d, te)
        s_tr = model.score(d, tr)
        ref = s_tr[(d["y"][tr] == 0) & (d["nw"][tr] >= SELECT_MIN_WORDS)]
        for lang in ("en", "fr"):
            k = te[(d["lang"][te] == lang) & (d["nw"][te] >= SELECT_MIN_WORDS)]
            y = d["y"][k]
            if (y == 0).sum() < 30:
                continue
            cell = {"n_human": int((y == 0).sum()), "n_ai": int((y == 1).sum()),
                    "auroc": auroc(y, oof[k])}
            for tag, q in (("1pct", 0.99), ("5pct", 0.95)):
                thr = np.quantile(ref, q)
                cell[f"fpr_{tag}"] = float((oof[k][y == 0] > thr).mean())
                cell[f"tpr_{tag}"] = (float((oof[k][y == 1] > thr).mean())
                                      if (y == 1).sum() >= 30 else None)
            transfer[f"{fam}/{lang}"] = cell
    return oof, transfer


def out_of_generator(d, cols):
    """Detection of a generator whose texts were removed from training (humans stay), at
    the 1 % and 5 % thresholds of the training humans."""
    out = {}
    for gen in sorted(set(d["gen"]) - {"human"}):
        tr = np.nonzero((d["nw"] >= TRAIN_MIN_WORDS) & (d["gen"] != gen))[0]
        te = np.nonzero((d["nw"] >= SELECT_MIN_WORDS) & (d["gen"] == gen) & (d["lang"] == "en"))[0]
        if len(te) < 30:
            continue
        model = Model(cols, c=C).fit(d, tr)
        s_tr = model.score(d, tr)
        ref = s_tr[(d["y"][tr] == 0) & (d["nw"][tr] >= SELECT_MIN_WORDS)]
        s = model.score(d, te)
        out[gen] = {"n": int(len(te)), "tpr_1pct": float((s > np.quantile(ref, 0.99)).mean()),
                    "tpr_5pct": float((s > np.quantile(ref, 0.95)).mean())}
    return out


# ------------------------------------------------------------------ length

def _features_truncated(args):
    text, k = args
    tokens = F.split_whitespace(text)
    a = F.analyse(" ".join(tokens[:k]), with_rhetoric=False)
    return [a["features"].get(n, 0.0) for n in F.SCALAR_FEATURES]


def length_curve(d, pool_rows, cols):
    """Out-of-family AUROC and false-positive rate when only the first k words are read.
    Same texts at every k (those with at least 300 words), English and French pooled; the
    threshold is the 99th percentile of the out-of-family human scores at 300 words."""
    rng = np.random.default_rng(SEED)
    idx = np.nonzero((d["nw"] >= 300) & np.isin(d["lang"], ("en", "fr")))[0]
    idx = rng.choice(idx, size=min(4000, len(idx)), replace=False)
    texts = [pool_rows[i]["text"] for i in idx]
    scores = {}
    with multiprocessing.Pool(8) as pool:
        for k in LENGTH_GRID:
            X = np.asarray(pool.map(_features_truncated, [(t, k) for t in texts], chunksize=64))
            s = np.full(len(idx), np.nan)
            for fam in FAMILIES:
                train_mask = (d["nw"] >= TRAIN_MIN_WORDS) & (d["family"] != fam)
                tr = np.nonzero(train_mask)[0]
                model = Model(invariant_columns(d, train_mask), c=C).fit(d, tr)
                te = d["family"][idx] == fam
                if te.any():
                    z = np.clip((X[te][:, model.cols] - model.mean) / model.scale, -CLIP_Z, CLIP_Z)
                    s[te] = model.lr.decision_function(z)
            scores[k] = s
    y = d["y"][idx]
    thr = np.quantile(scores[300][y == 0], 0.99)
    curve = []
    for k in LENGTH_GRID:
        s = scores[k]
        curve.append({"words": k, "auroc": auroc(y, s),
                      "fpr_at_300w_threshold": float((s[y == 0] > thr).mean()),
                      "tpr_at_300w_threshold": float((s[y == 1] > thr).mean()),
                      "human_score_sd": float(s[y == 0].std())})
    return curve, int(len(idx))


def choose_min_words(curve) -> int:
    """Smallest length of BUCKETS whose out-of-family AUROC keeps at least half of the
    gain over chance seen at 300 words. Below it the score is noise: it is not given.
    The false-positive rate is NOT part of this rule: it is controlled by calibrating
    each length bucket apart (the curve shows why one threshold cannot serve all lengths)."""
    full = curve[-1]["auroc"] - 0.5
    for point in curve:
        if point["words"] in BUCKETS and point["auroc"] - 0.5 >= 0.5 * full:
            return point["words"]
    return BUCKETS[-1]


def bucket_scores(d, pool_rows) -> dict:
    """Out-of-family score of every pool text of at least k words when only its first k
    words are read, for each k of BUCKETS; the last bucket reads the text as the library
    does (up to MAX_TOKENS). A text of 180 words is judged with the 150-word table: its
    score is at most as noisy as the scores the table was built from."""
    out = {}
    models = {}
    for fam in FAMILIES:
        train_mask = (d["nw"] >= TRAIN_MIN_WORDS) & (d["family"] != fam)
        models[fam] = Model(invariant_columns(d, train_mask), c=C).fit(d, np.nonzero(train_mask)[0])
    with multiprocessing.Pool(8) as pool:
        for k in BUCKETS:
            idx = np.nonzero(d["nw"] >= k)[0]
            if k == BUCKETS[-1]:
                X = d["X"][idx]
            else:
                X = np.asarray(pool.map(_features_truncated,
                                        [(pool_rows[i]["text"], k) for i in idx], chunksize=64))
            s = np.full(len(d["y"]), np.nan)
            for fam, model in models.items():
                te = d["family"][idx] == fam
                if te.any():
                    z = np.clip((X[te][:, model.cols] - model.mean) / model.scale, -CLIP_Z, CLIP_Z)
                    s[idx[te]] = model.lr.decision_function(z)
            out[k] = s
    return out


# ------------------------------------------------------------------ calibration

def platt(scores, labels, weights):
    """ln LR(s) = a*s + b: logistic fit with the two classes weighing the same, so the
    fitted odds are a likelihood ratio and not a posterior under the corpus mix."""
    from sklearn.linear_model import LogisticRegression
    w = weights.copy()
    for label in (0, 1):
        w[labels == label] /= w[labels == label].sum()
    lr = LogisticRegression(C=1e6, max_iter=1000)
    lr.fit(scores.reshape(-1, 1), labels, sample_weight=w * len(w))
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def conformal_quantile(scores, alpha) -> float:
    """The ceil((n+1)(1-alpha))-th smallest score: under exchangeability a new human
    text exceeds it with probability at most alpha (marginal guarantee)."""
    s = np.sort(scores)
    k = math.ceil((len(s) + 1) * (1 - alpha))
    return float(s[min(k, len(s)) - 1])


def admit(d, oof, lang, min_words):
    """Rows of the language admitted to calibration, or the reason for refusing a table."""
    base = (d["det"] == lang) & (d["lang"] == lang) & (d["nw"] >= min_words) & ~np.isnan(oof)
    native = np.array([not dom.startswith(TRANSLATED_PREFIX) for dom in d["domain"]])
    human = base & (d["y"] == 0) & native
    ai = base & (d["y"] == 1)
    counts = {"n_human": int(human.sum()), "n_ai": int(ai.sum()),
              "human_families": sorted(set(d["family"][human])),
              "ai_families": sorted(set(d["family"][ai]))}
    ok = (counts["n_human"] >= ADMIT_MIN_TEXTS and counts["n_ai"] >= ADMIT_MIN_TEXTS
          and len(counts["human_families"]) >= ADMIT_MIN_FAMILIES
          and len(counts["ai_families"]) >= ADMIT_MIN_FAMILIES)
    return ok, human, ai, counts


def calibrate(d, oof, lang, human, ai, counts, rng):
    idx = np.nonzero(human | ai)[0]
    s, y, fam = oof[idx], d["y"][idx], d["family"][idx]
    a, b = platt(s, y, np.ones(len(s)))
    lo, hi = np.quantile(s, 0.001), np.quantile(s, 0.999)
    grid = np.linspace(lo, hi, GRID_POINTS)
    # Bootstrap: rows are resampled inside each (family, label) cell, and each family
    # gets a random weight, so the interval also carries the uncertainty on the mix of
    # sources, which is unknown for a new text.
    cells = [np.nonzero((fam == f) & (y == label))[0] for f in sorted(set(fam)) for label in (0, 1)]
    cells = [c for c in cells if len(c)]
    cell_fam = [fam[c[0]] for c in cells]
    curves = np.empty((BOOTSTRAP, GRID_POINTS))
    for i in range(BOOTSTRAP):
        fam_weight = {f: rng.exponential(1.0) for f in sorted(set(cell_fam))}
        take, weight = [], []
        for c, f in zip(cells, cell_fam):
            pick = rng.choice(c, size=len(c), replace=True)
            take.append(pick)
            weight.append(np.full(len(c), fam_weight[f] / len(c)))
        take, weight = np.concatenate(take), np.concatenate(weight)
        ai_b, bi_b = platt(s[take], y[take], weight)
        curves[i] = ai_b * grid + bi_b
    # No ratio beyond what the sample can resolve: with n texts, a rate under 3/n is not
    # measurable (rule of three), so |ln LR| is capped at ln(n/3) of the smaller class.
    cap = math.log(min(counts["n_human"], counts["n_ai"]) / 3.0)
    clip = lambda v: np.clip(v, -cap, cap)  # noqa: E731
    ln_lr = clip(a * grid + b)
    ln_lo = np.minimum(clip(np.quantile(curves, (1 - COVERAGE) / 2, axis=0)), ln_lr)
    ln_hi = np.maximum(clip(np.quantile(curves, 1 - (1 - COVERAGE) / 2, axis=0)), ln_lr)

    h = oof[human]
    thresholds = {}
    for tag, alpha in (("high", ALPHA_HIGH), ("medium", ALPHA_MEDIUM)):
        values = {"pooled": conformal_quantile(h, alpha)}
        for f in sorted(set(d["family"][human])):
            hf = oof[human & (d["family"] == f)]
            if len(hf) + 1 >= 1 / alpha:           # the quantile exists for this family
                values[f] = conformal_quantile(hf, alpha)
        thresholds[tag] = {"value": max(values.values()), "by_family": values}
    p = 1 / (1 + np.exp(-(a * s + b)))
    quality = {"ece_balanced": ece(p, y), "brier_balanced": brier(p, y),
               "by_family": {f: {"n": int((fam == f).sum()), "auroc": auroc(y[fam == f], s[fam == f]),
                                 "ece": ece(p[fam == f], y[fam == f])}
                             for f in sorted(set(fam))}}
    return {
        "n_human": counts["n_human"], "n_ai": counts["n_ai"],
        "grid": [round(float(v), 6) for v in grid],
        "ln_lr": [round(float(v), 6) for v in ln_lr],
        "ln_lr_low": [round(float(v), 6) for v in ln_lo],
        "ln_lr_high": [round(float(v), 6) for v in ln_hi],
        "threshold_high": round(thresholds["high"]["value"], 6),
        "threshold_medium": round(thresholds["medium"]["value"], 6),
    }, {"platt": [a, b], "ln_lr_cap": cap, "thresholds": thresholds, "quality": quality}


def ece(p, y, bins=10) -> float:
    """Expected calibration error with the two classes weighing the same."""
    w = np.where(y == 1, 0.5 / max(1, (y == 1).sum()), 0.5 / max(1, (y == 0).sum()))
    total = 0.0
    for lo in np.linspace(0, 1, bins + 1)[:-1]:
        m = (p >= lo) & (p < lo + 1 / bins + 1e-12)
        if w[m].sum() > 0:
            total += w[m].sum() * abs(np.average(p[m], weights=w[m]) - np.average(y[m], weights=w[m]))
    return float(total / w.sum())


def brier(p, y) -> float:
    w = np.where(y == 1, 0.5 / max(1, (y == 1).sum()), 0.5 / max(1, (y == 0).sum()))
    return float(np.average((p - y) ** 2, weights=w))


# ------------------------------------------------------------------ reference scorer

class Scorer:
    """The run-time logic, as the Rust core implements it. Reads the exported JSON."""

    def __init__(self, model: dict):
        self.m = model
        self.names = [f["name"] for f in model["features"]]

    def logit(self, feats: dict) -> float:
        total = self.m["intercept"]
        for f in self.m["features"]:
            z = (feats[f["name"]] - f["mean"]) / f["scale"]
            z = max(-self.m["clip"], min(self.m["clip"], z))
            total += f["weight"] * z
        return total

    @staticmethod
    def bucket(table, n_words):
        """The length bucket of a text: the largest lower bound not above its word count."""
        return [b for b in table["buckets"] if b["min_words"] <= n_words][-1]

    @staticmethod
    def interpolate(grid, values, x) -> float:
        if x <= grid[0]:
            return values[0]
        if x >= grid[-1]:
            return values[-1]
        for i in range(1, len(grid)):
            if x <= grid[i]:
                t = (x - grid[i - 1]) / (grid[i] - grid[i - 1])
                return values[i - 1] + t * (values[i] - values[i - 1])
        return values[-1]

    def score(self, raw: str) -> dict:
        a = F.analyse(raw, with_rhetoric=False)
        # The raw logit is always computed: the parity test compares it on every text.
        s = self.logit(a["features"])
        out = {"n_words": a["n_words"], "language": a["language"], "status": "ok", "logit": s}
        table = self.m["tables"].get(a["language"])
        if table is None:
            out["status"] = "no-table"
            return out
        if a["n_words"] < self.m["min_words"]:
            out["status"] = "too-short"
            return out
        table = self.bucket(table, a["n_words"])
        out["ln_lr"] = self.interpolate(table["grid"], table["ln_lr"], s)
        out["ln_lr_low"] = self.interpolate(table["grid"], table["ln_lr_low"], s)
        out["ln_lr_high"] = self.interpolate(table["grid"], table["ln_lr_high"], s)
        out["ai_likely"] = bool(s >= table["threshold_high"]
                                and out["ln_lr_low"] > self.m["ai_likely_min_ln_lr_low"])
        out["above_medium"] = bool(s >= table["threshold_medium"])
        return out


# ------------------------------------------------------------------ measurement

def wilson(k: int, n: int) -> list:
    if n == 0:
        return [None, None]
    z = 1.959964
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def rate(flags) -> dict:
    k, n = int(np.sum(flags)), int(len(flags))
    return {"k": k, "n": n, "rate": (k / n if n else None), "wilson95": wilson(k, n)}


def measure(d, model_json, logits) -> dict:
    """Per detected language with a table: AUROC of the raw score, detection and
    false-positive rates at the two thresholds, and what was not scored."""
    out = {"n": int(len(d["y"])), "by_language": {}}
    has_table = np.isin(d["det"], list(model_json["tables"]))
    long_enough = d["nw"] >= model_json["min_words"]
    out["not_scored"] = {"no_table": int((~has_table).sum()),
                         "too_short": int((has_table & ~long_enough).sum())}
    for lang, table in model_json["tables"].items():
        m = (d["det"] == lang) & long_enough
        if not m.any():
            continue
        y, s = d["y"][m], logits[m]
        likely, medium = flags_of(table, s, d["nw"][m])
        cell = {"n_human": int((y == 0).sum()), "n_ai": int((y == 1).sum()), "auroc": auroc(y, s)}
        for tag, flags in (("high", likely), ("medium", medium)):
            cell[f"fpr_{tag}"] = rate(flags[y == 0])
            cell[f"detection_{tag}"] = rate(flags[y == 1])
        out["by_language"][lang] = cell
    return out


def flags_of(table, scores, n_words):
    """(ai-likely, above the medium threshold) for each text, with its length bucket."""
    likely, medium = [], []
    for v, n in zip(scores, n_words):
        b = Scorer.bucket(table, n)
        lo = Scorer.interpolate(b["grid"], b["ln_lr_low"], v)
        likely.append(v >= b["threshold_high"] and lo > AI_LIKELY_MIN_LN_LR_LOW)
        medium.append(v >= b["threshold_medium"])
    return np.array(likely, dtype=bool), np.array(medium, dtype=bool)


# ------------------------------------------------------------------ fixture

EDGE_CASES = [
    "", "ok", "\U0001F600", "Bonjour, je rentre demain soir. On se voit samedi ?",
    "## Titre\n\n- **Premier** point\n- Second point avec `code`\n\n> Une citation.\n" * 12,
    "The cat sat on the mat. " * 40,
    "Le chat : « il dort » ! Vraiment ? Oui… " * 30,
    "Это русский текст о погоде и о жизни в большом городе. " * 20,
    "هذا نص عربي قصير عن الطقس والحياة في المدينة الكبيرة. " * 20,
    "这是一个关于天气和城市生活的中文文本。" * 30,
    "これは天気と都市生活についての日本語のテキストです。" * 30,
    "이것은 날씨와 도시 생활에 관한 한국어 텍스트입니다. " * 20,
    "Der Hund läuft über die Straße und die Katze schläft auf dem Sofa im Haus. " * 15,
    "El perro corre por la calle y el gato duerme en el sofá de la casa. " * 15,
    "I 've heard three theories . The first , as he said , is n't new ; it 's old ( really ) . " * 12,
    "Vis​it https://example.com/?utm_source=chatgpt.com or www.example.org [1] [23]. " * 15,
    "İSTANBUL'DA HAVA ÇOK GÜZEL VE DENİZ ÇOK SAKİN BİR GÜN DAHA BAŞLADI. " * 15,
    "ΑΥΤΟ ΕΙΝΑΙ ΕΝΑ ΚΕΙΜΕΝΟ ΣΤΑ ΕΛΛΗΝΙΚΑ ΓΙΑ ΤΟΝ ΚΑΙΡΟ ΣΗΜΕΡΑ. " * 15,
    "a-b-c d'e f- -g 'h i' j--k l'-m. " * 40,
    "1234 5678 (90) [12] 3.14 2,718 100% $5 #tag @user a/b <x> ^y " * 20,
    "word " * 99, "word " * 100, "x" * (F.MAX_CHARS - 600) + (" The cat is on the mat." * 60), "The of and to in is that it. " * 13,
    "Straße ŒUVRE Ǆ ǅ ǆ ß ẞ ﬁ Ａｂｃ naïve café ÉTÉ été. " * 20,
    "line one\r\nline two\rline three\n\n\n\tline four\x0bfive\x0csix\x85seven eight " * 15,
]


def build_fixture(scorer: Scorer) -> list:
    """Slices of tracked repository files (the raw texts of the golden set, by character
    offsets) plus inline edge cases. The expected values come from this Python reference."""
    entries = []
    base = ROOT / "bench" / "golden" / "raw"
    paths = sorted(p for sub in ("human", "ai", "ai2") for p in (base / sub).glob("*.txt"))
    for path in paths:
        text = path.read_text(encoding="utf-8")
        cuts = [0]
        if len(text) > 6000:                 # long documents give several slices
            cuts = list(range(0, min(len(text), 40000) - 2000, 2000))
        for start in cuts:
            end = min(len(text), start + 4000)
            entries.append({"file": str(path.relative_to(ROOT)), "start": start, "end": end,
                            "expect": scorer.score(text[start:end])})
    for text in EDGE_CASES:
        entries.append({"text": text, "expect": scorer.score(text)})
    return entries


def without_nan(value):
    """NaN (an AUROC with one class only) is not valid JSON: written as null."""
    if isinstance(value, dict):
        return {k: without_nan(v) for k, v in value.items()}
    if isinstance(value, list):
        return [without_nan(v) for v in value]
    if isinstance(value, float) and value != value:
        return None
    return value


# ------------------------------------------------------------------ main

def main() -> int:
    rng = np.random.default_rng(SEED)
    d = load("pool")
    pool_rows = [json.loads(line) for line in open(LIGHT / "pool.jsonl", encoding="utf-8")]
    results = {"detector": DETECTOR, "date": TABLE_DATE}

    cols = invariant_columns(d, d["nw"] >= TRAIN_MIN_WORDS)
    kept = [F.SCALAR_FEATURES[j] for j in cols]
    results["features_kept"] = kept
    results["features_dropped"] = [n for n in F.SCALAR_FEATURES if n not in kept]
    print("features kept:", kept, file=sys.stderr)

    oof, transfer = out_of_family_scores(d)
    results["leave_one_family_out"] = transfer
    results["leave_one_generator_out"] = out_of_generator(d, cols)

    curve, n_curve = length_curve(d, pool_rows, cols)
    min_words = choose_min_words(curve)
    results["length_curve"] = {"n_texts": n_curve, "points": curve, "min_words": min_words}
    print("minimum length:", min_words, file=sys.stderr)

    per_bucket = bucket_scores(d, pool_rows)
    buckets = [k for k in BUCKETS if k >= min_words]
    tables, calibration = {}, {}
    for lang in sorted(set(d["det"])):
        ok, human, ai, counts = admit(d, per_bucket[min_words], lang, min_words)
        if not ok:
            calibration[lang] = {"admitted": False, **counts}
            continue
        tables[lang] = {"calibration_id": f"{DETECTOR}/{lang}/{TABLE_DATE}", "buckets": []}
        calibration[lang] = {"admitted": True, **counts, "buckets": {}}
        for k in buckets:
            _, human, ai, counts_k = admit(d, per_bucket[k], lang, k)
            table, detail = calibrate(d, per_bucket[k], lang, human, ai, counts_k, rng)
            tables[lang]["buckets"].append({"min_words": k, **table})
            calibration[lang]["buckets"][str(k)] = {**counts_k, **detail}
    results["calibration"] = calibration
    print("tables:", sorted(tables), file=sys.stderr)

    final = Model(cols, c=C).fit(d, np.nonzero(d["nw"] >= TRAIN_MIN_WORDS)[0])
    model_json = {
        "detector": DETECTOR, "date": TABLE_DATE, "min_words": min_words,
        "max_tokens": F.MAX_TOKENS, "max_chars": F.MAX_CHARS, "clip": CLIP_Z, "coverage": COVERAGE,
        "ai_likely_min_ln_lr_low": AI_LIKELY_MIN_LN_LR_LOW,
        "intercept": round(float(final.lr.intercept_[0]), 8),
        "features": [{"name": F.SCALAR_FEATURES[j], "mean": round(float(final.mean[i]), 8),
                      "scale": round(float(final.scale[i]), 8),
                      "weight": round(float(final.lr.coef_[0, i]), 8)}
                     for i, j in enumerate(cols)],
        "tables": tables,
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODEL_PATH.write_text(json.dumps(model_json, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
    # The exported (rounded) model is the one measured below.
    scorer = Scorer(model_json)

    def logits_of(data):
        return np.array([scorer.logit(dict(zip(F.SCALAR_FEATURES, row))) for row in data["X"]])

    measures = {}
    for name in ("test", "test_ood", "test_fr", "test_fiction", "test_attack"):
        data = load(name)
        s = logits_of(data)
        measures[name] = measure(data, model_json, s)
        measures[name]["auroc_all_texts_raw_score"] = auroc(data["y"], s)
        if name == "test_ood":
            src = np.array([r["source"] for r in data["rows"]])
            measures[name]["by_source"] = {
                k: measure({key: (v[src == k] if isinstance(v, np.ndarray) and len(v) == len(src)
                                  else v) for key, v in data.items()}, model_json, s[src == k])
                for k in sorted(set(src))}
    results["benchmark"] = measures

    wiki = {}
    for name in ("wiki_docs", "wiki_chunks"):
        data = load(name)
        s = logits_of(data)
        by_lang = {}
        for lang in sorted(set(data["lang"])):
            m = data["lang"] == lang
            det = data["det"][m]
            cell = {"n": int(m.sum()), "detected": sorted(set(det))}
            table = model_json["tables"].get(lang)
            scored = m & (data["det"] == lang) & (data["nw"] >= min_words)
            if table is not None:
                likely, medium = flags_of(table, s[scored], data["nw"][scored])
                cell["scored"] = int(scored.sum())
                cell["fpr_high"] = rate(likely)
                cell["fpr_medium"] = rate(medium)
            else:
                # No table: the library abstains. For the record, what the English
                # thresholds would have done on these texts.
                en = model_json["tables"]["en"]["buckets"][-1]
                cell["scored"] = 0
                cell["would_exceed_en_high"] = rate(s[m] >= en["threshold_high"])
                cell["would_exceed_en_medium"] = rate(s[m] >= en["threshold_medium"])
            by_lang[lang] = cell
        wiki[name] = by_lang
    results["wikipedia_humans"] = wiki

    gold = load("golden")
    s = logits_of(gold)
    cls = np.array([r["class"] for r in gold["rows"]])
    golden = {}
    for c in ("human", "ai", "mixed"):
        sub = {k: (v[cls == c] if isinstance(v, np.ndarray) and len(v) == len(cls) else v)
               for k, v in gold.items()}
        golden[c] = measure(sub, model_json, s[cls == c])
    both = np.isin(cls, ("human", "ai"))
    golden["auroc_human_vs_ai"] = {
        lang: auroc(gold["y"][both & (gold["lang"] == lang)], s[both & (gold["lang"] == lang)])
        for lang in ("en", "fr")}
    by_sha = {r["sha256"]: s[i] for i, r in enumerate(gold["rows"])}
    shifts = {}
    for i, r in enumerate(gold["rows"]):
        if r["class"] == "degraded" and r["parents"] and r["parents"][0] in by_sha:
            shifts.setdefault(r["transform"], []).append(float(s[i] - by_sha[r["parents"][0]]))
    golden["degraded_logit_shift"] = {
        k: {"n": len(v), "mean_abs": float(np.mean(np.abs(v))), "max_abs": float(np.max(np.abs(v)))}
        for k, v in sorted(shifts.items())}
    results["golden"] = golden

    fixture = build_fixture(scorer)
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(fixture, ensure_ascii=False, indent=0) + "\n",
                            encoding="utf-8")
    results["fixture"] = {"entries": len(fixture),
                          "scored": sum(1 for e in fixture if e["expect"]["status"] == "ok")}
    RESULTS_PATH.write_text(
        json.dumps(without_nan(results), ensure_ascii=False, indent=1, allow_nan=False) + "\n",
        encoding="utf-8")
    print("model:", MODEL_PATH.stat().st_size, "bytes; fixture:", len(fixture), "entries",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
