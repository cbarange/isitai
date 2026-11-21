# Light text score (`text-light-v1`)

A statistical score for plain text with no neural model: eleven counts, a logistic
regression, a calibration table per language. It lives in the core
(`crates/isitai-core/src/score.rs`, data in `crates/isitai-core/model/light-text-v1.json`,
9 kB). Output shape: `docs/research/FALLBACK-probabilistic.md` section 7 (a likelihood ratio,
never a percentage).

All figures below were measured on 2026-11-12 and are in `results.json`. Nothing was tuned on
the benchmark test splits, on the Wikipedia corpus or on the golden set.

## Reproduce

```bash
PY=/tmp/isitai-bench/venv/bin/python      # see bench/detectors/README.md
python3 bench/golden/build.py             # golden set
$PY bench/light/build_pool.py             # training / calibration pool, leakage asserts
$PY bench/light/extract.py                # features of every data set (cached in /tmp)
$PY bench/light/experiments.py            # ablations, leave-one-family-out
$PY bench/light/train.py                  # selection, calibration, export, measures, fixture
cargo test -p isitai --test light_parity  # Rust port = Python reference
```

## Training and calibration data

`build_pool.py` reads the raw files of `bench/detectors` and excludes everything of the five
test splits: by text hash, by RAID (domain, title) group (attack pool included), by HC3
question id in English and French. It asserts a zero overlap. The RAID domains (poetry,
reviews) and generators (gpt4, cohere-chat, llama-chat) that make `test_ood` out of
distribution stay out of the pool.

| Family | Content | Languages |
|---|---|---|
| raid | 700 source documents per domain (abstracts, books, news, recipes, reddit, wiki), 8 generators | en |
| hc3 | HC3 train file: human and ChatGPT answers; its machine-translated French copy (AI side only for calibration) | en, fr |
| mage | MAGE GPT-4 set, the rows that are not in `test_ood` | en |
| reviews | MAiDE-up hotel reviews (Booking.com / GPT-4) | 10 languages, nearly all under 100 words |
| faq | French FAQ answers (human only) | fr |

28,374 texts. Each (family, label) cell has the same total weight in the fit.

## Features kept and dropped

39 layout-free candidates plus the three counts of the `rhetoric` layer were measured. The
selection rule: a feature is kept only when its univariate AUROC is on the **same side of 0.5
in every (family, language) cell** and at least 0.03 away from 0.5 on average. A feature that
says "AI" in one source and "human" in another describes the source, not the author.

- **Kept (11)**: `sent_len_sd`, `sent_len_cv`, `sent_len_adjdiff`, `sent_short_frac`,
  `word_len_mean`, `word_len_sd`, `word_long_frac`, `p_paren`, `digit_ratio`, `allcaps_frac`,
  `sent_lower_start_frac`.
- **Dropped: vocabulary diversity and repetition** (TTR, hapax, MATTR 20 and 50, repeated
  bigrams, top word). Their sign flips between sources: repeated bigrams have AUROC 0.78 on HC3
  and 0.33 on reviews. The "AI repeats bigrams less" claim of `OSS-patterns-reuse.md` §3 is
  therefore neither confirmed nor refuted: it depends on the source.
- **Dropped: punctuation profile** except brackets, upper-case ratio, character entropy:
  sign flips.
- **Dropped: hashed character n-grams** (4,096 buckets). Out of family they add nothing
  reliable (mean AUROC 0.73 against 0.72) and raise the worst false-positive rate when added
  to the scalar features (8.7 %). They also carry topic and language, and cost 100 kB.
- **Dropped: rhetoric counts** (`pivot-pair`, `not-x-but-y`, `triptych`). Univariate AUROC
  0.49 to 0.55 everywhere; they fire on 2 of 100 AI texts and 9 of 150 human texts of the
  golden set. The patterns stay in the `rhetoric` layer, which never changes the verdict.
  The pivot rule also has a known false positive on formal French conditional sentences
  ("Si vous ... Nous vous ..."): one more reason not to let it weigh in a score.
- **Not measured** (not "dropped"): compression ratio (`zlib` is not a dependency of the core,
  and the benchmark measured it as weak), windows projected on paragraphs, non-linear
  aggregation of window scores, Jensen-Shannon divergence against shipped baselines, and every
  idea of `OSS-patterns-reuse.md` §4 that needs a language model.
  Taken from that list: MATTR (measured, dropped), refusal below a minimum length, fixed
  windows for the lexical features.

Leave-one-family-out, threshold at the 99th percentile of the training humans, texts of 100
words or more: false positives 0 to 1.6 % on the held-out family (worst: translated French
HC3), where the full 39-feature model reaches 7.9 % (French FAQ) and the benchmark's
detectors 14 to 72 %. The price is detection: 0 to 6 % at that threshold, AUROC 0.57 (RAID)
to 0.88 (reviews).

## Minimum length: 150 words

The same 4,000 texts were scored on their first k words, out of family:

| First k words | 30 | 50 | 75 | 100 | 150 | 200 | 300 |
|---|---|---|---|---|---|---|---|
| AUROC | 0.49 | 0.51 | 0.51 | 0.53 | 0.56 | 0.57 | 0.59 |
| Humans above the 1 % threshold of 300-word texts | 18.9 % | 12.3 % | 9.5 % | 7.2 % | 4.3 % | 2.5 % | 1.0 % |

Under 100 words the score is chance. A first rule (90 % of the gain and under 2 % on the second
line) gave 300 words and one table; it was replaced by the rule below with one table per
length bucket, before any test split was read. 150 is the first length that keeps half of the gain over
chance seen at 300 words (rule in `choose_min_words`). The second line shows why one threshold
cannot serve every length: short texts have noisier scores. So each length bucket (150, 200,
300 words and more) has its own table, built from texts cut to the lower bound of the bucket.

## Calibration

- **Scores used**: out of family only (each text is scored by a model that never saw its
  source family, features selected without it too).
- **Admission of a language**: at least 200 native human texts and 200 AI texts of 150 words
  or more, each from at least two source families. Machine-translated human answers do not
  count as native. **Admitted: English** (4,757 human, 4,680 AI). **Refused**: French (29
  native human texts), German (24), Spanish (23), Italian (26), Romanian (34), and every
  language with no data. A refused language gets no `lr`.
- **Likelihood ratio**: logistic fit of the label on the score with the two classes at equal
  weight, read on a 33-point grid. |ln LR| is capped at ln(n/3) of the smaller class.
- **Interval: bootstrap**, 1,000 resamples, 90 %. Rows are resampled inside each (family,
  label) cell and each family gets a random weight, so the interval carries the uncertainty
  on the mix of sources. Chosen over a conformal interval because the quantity is a ratio of
  two densities, not a prediction set; the conformal method is used where it fits, for the
  thresholds.
- **Thresholds: conformal quantile** of the native human scores, the ⌈(n+1)(1−α)⌉-th
  smallest, α = 1 % (`ai-likely`) and 5 %; the value kept is the **highest** of the pooled
  quantile and of each family's own quantile. The guarantee is marginal, under
  exchangeability: it promises nothing for one given text or for a new kind of text.
- Balanced ECE of the English tables: 0.02 to 0.05 pooled, but 0.09 on RAID and 0.23 on HC3
  taken alone: the ratio is calibrated on the mix, not inside each source.

## Measures

English texts of 150 words or more. "high" = `ai-likely`. 95 % Wilson intervals in
`results.json`. `stylometry_lr` and `tfidf_lr` are the benchmark's figures at their own
1 % threshold (`docs/research/BENCH-text-detectors.md`, 400-text sample, all lengths): a
different population, shown for the order of magnitude.

| Set | Scored | AUROC | FPR high | Detection high | FPR medium | Detection medium | `stylometry_lr` det / FPR | `tfidf_lr` det / FPR |
|---|---|---|---|---|---|---|---|---|
| test | 1,481 of 2,000 | 0.63 | 3/884 = 0.3 % | 27/597 = 4.5 % | 37/884 = 4.2 % | 112/597 = 18.8 % | AUROC 0.98 | AUROC 0.97 |
| test_ood | 705 of 1,000 | 0.77 | 1/349 = 0.3 % | 14/356 = 3.9 % | 10/349 = 2.9 % | 83/356 = 23.3 % | 69 % / 14 % | 72 % / 20 % |
| test_attack | 704 of 1,000 | 0.67 | 0/395 | 8/309 = 2.6 % | 11/395 = 2.8 % | 42/309 = 13.6 % | AUROC 0.84–0.90 | — |
| test_fiction | 500 of 500 | 0.53 | 0/250 | 0/250 | 0/250 | 0/250 | AUROC 0.67 | AUROC 0.31 |
| test_fr | 0 of 990 (no table) | (0.73 raw) | — | — | — | — | 50 % / 36 % | 66 % / 55 % |

Not scored: texts under 150 words, and texts whose language was not recognised as English
(98 of `test`).

Human Wikipedia texts (before 2019), by language:

| Language | Whole articles | 300-word parts | Result |
|---|---|---|---|
| en | 10 | 84 | high 0/10 and 0/84 (≤ 4.4 %); medium 0/10 and 3/84 |
| fr, de, es, it, nl, pl, pt, ru, ar, ja, zh | 107 | 758 | not scored (no table) |

For the record only, what the English thresholds would do on the parts of the other
languages if the library did not abstain: high 0 to 1 part per language (ja, pl, pt, ru: 1
each); medium: fr 5/79, pt 4/55, pl 2/35, ru 2/57.

Golden set (`bench/golden`, v1.0, protocol respected: nothing tuned on it, worst subgroup
first, no claim under what n can resolve):

| Class | English, scored | Result | French |
|---|---|---|---|
| human | 74 | `ai-likely` 0/74, medium 0/74 → **false positives ≤ 4.9 % (95 %)**, the only claim 74 negatives allow | 75 texts, not scored |
| ai (one generator) | 40 (10 too short) | `ai-likely` 1/40, medium 20/40 | 50 texts, not scored |
| mixed (labelled human here) | 52 | `ai-likely` 0/52 | 48 texts, not scored |
| degraded | — | score shift: homoglyphs 0, zero-width 0, Markdown removed ≤ 0.02, paragraphs shuffled ≤ 0.66, truncation ≤ 1.1 (logit units; the 1 % threshold is 1.0 to 1.6) | — |

The raw score separates the golden human and AI classes perfectly (AUROC 1.0 in both
languages). Do not read it as accuracy: one generator, and the human class is the author's
technical documents, full of brackets and identifiers, which the score reads as human.

## Cost

| | Before | After | Added |
|---|---|---|---|
| CLI, profile `size` (macOS arm64) | 5,735,728 B | 5,785,520 B | 49.8 kB |
| Python wheel (macOS arm64) | 4,642,532 B | 4,683,092 B | 40.6 kB (CI budget: 5,200 kB) |
| Crate package | 124,738 B | 141,688 B | 17.0 kB (CI budget: 700 kB) |
| Python sdist | not measured | 165,869 B | (CI budget: 900 kB) |
| npm package (meta) | not measured | 10,335 B | (CI budget: 500 kB) |
| WASM module, profile `release`, before `wasm-bindgen` | 10,316,052 B | 10,384,684 B | 68.6 kB |

Time (`cargo run --release -p isitai --example light_timing`, macOS arm64, one thread): 250
golden texts of 287 words on average: median 0.20 ms, p95 0.35 ms per text with the score,
0.01 ms without. Ten Wikipedia articles of 3,000 words: 1.0 ms against 0.2 ms. The score
reads at most 200,000 characters and 1,000 words: a 16 MB file of one unbroken line takes
0.05 s and 45 MB of peak memory with the score, as without it.

## Known weaknesses

- **Detection is poor.** 3 to 5 % of AI texts at the `ai-likely` threshold, none on 2026
  fiction. The table cannot give a ratio above about 2.3: on a forensic scale this is weak
  support at best. The verdict name `ai-likely` says more than a ratio of 1.5 to 2 supports;
  `ai_likely_min_ln_lr_low` in the model file is the knob if the owner wants a stricter rule
  (at ln 10 the verdict would never fire).
- **One language.** The French question that motivated per-language tables is answered by an
  abstention, not by a table: the first need is native French human text of 150 words or more
  with an AI counterpart.
- **Old generators.** RAID, HC3 and MAGE are from 2022-2023. On the only 2026 texts measured
  (fiction, golden set) the score sees nothing or little.
- **The strongest features are editing habits** (brackets, sentences that start without a
  capital, words in capitals): they say "typed by a person, unedited" more than "not AI". A
  carefully edited human text, or an AI text with brackets added, moves the score.
- **No measure on non-native writers**, the known bias of these detectors.
- **Language guess**: function-word counts, ten Latin-script languages. A text it cannot name
  is not scored.
- **Calibration is marginal**: per source the ratio is off (ECE 0.09 to 0.23).
- **The interval is nominal**: its 90 % coverage was not verified on held-out data. At the
  `ai-likely` threshold its lower bound is already 1.3 to 1.65, so the "interval above 1"
  condition never decides; the threshold does.
- **The tables come from the five leave-one-family-out models, the library runs the final
  model.** Only the measured rates on the test splits show that the thresholds transfer.
