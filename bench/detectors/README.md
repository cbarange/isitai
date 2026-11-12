# Text detector benchmark

Compares AI-text detectors (accuracy, speed, memory) on the same data, on CPU, to decide
what could become a statistical layer of isitai. Today the text layer of isitai is
deterministic only (regex rules for copy-paste artefacts); `algos/isitai_rules.py` is that
baseline.

Code lives here. Data, models, the venv and results live in `/tmp/isitai-bench`
(override with `ISITAI_BENCH_DIR`) and never enter the repository.

```
bench/detectors/
  fetch_data.sh      downloads the raw files (streams the RAID CSV through fetch_raid.py)
  fetch_raid.py      reduces the 11.8 GB RAID train.csv to two small files
  build_data.py      builds the splits, runs the leakage checks, writes manifest.json
  common.py          paths, THREADS, load_split(), length buckets
  run.py             runs one detector on one or several splits
  evaluate.py        metrics, intervals, breakdowns; writes summary.json and summary.md
  algos/<name>.py    one detector per file
```

## Rebuild

```sh
python3.12 -m venv /tmp/isitai-bench/venv
/tmp/isitai-bench/venv/bin/pip install torch transformers scikit-learn numpy scipy \
    datasets onnxruntime tokenizers psutil pandas pyarrow maturin==1.16.0
export HF_HOME=/tmp/isitai-bench/hf

bench/detectors/fetch_data.sh                                  # about 10 minutes, 1.9 GB kept
/tmp/isitai-bench/venv/bin/python bench/detectors/build_data.py   # about 1 minute

# the isitai wheel, for algos/isitai_rules.py
(cd bindings/python && CARGO_TARGET_DIR=/tmp/isitai-bench/cargo-target \
   /tmp/isitai-bench/venv/bin/maturin build --release --out /tmp/isitai-bench/wheels \
   --interpreter /tmp/isitai-bench/venv/bin/python)
/tmp/isitai-bench/venv/bin/pip install --force-reinstall /tmp/isitai-bench/wheels/isitai-*.whl
```

Versions used on 2026-11-12 (macOS arm64, Python 3.12.13): torch 2.15.0 (CPU),
transformers 5.22.2, scikit-learn 1.9.1, numpy 2.5.4, scipy 1.18.1, datasets 5.2.0,
onnxruntime 1.31.1, tokenizers 0.23.3, pandas 3.1.1, pyarrow 26.0.1, psutil 7.2.2,
maturin 1.16.0.

`build_data.py` is deterministic (seed 20261112); two runs give byte-identical files.
SHA-256 prefixes of the files built on 2026-11-12: train `f0a38c2d826cfcf7`, test
`780ad4bc359ff373`, test_ood `10f913ab4f3966a3`, test_fr `4428b6c246d51872`, test_fiction
`5cc02cdcd2ec8a9f`, test_attack `bd99e7ab5a4adc40`.

## Run

```sh
PY=/tmp/isitai-bench/venv/bin/python; export HF_HOME=/tmp/isitai-bench/hf
$PY bench/detectors/run.py --algo length_baseline --split test
$PY bench/detectors/run.py --algo NAME --variant V --split all        # fit once, every test split
$PY bench/detectors/run.py --algo NAME --split test --limit 50        # smoke test
$PY bench/detectors/evaluate.py                                       # every result file
```

## Data

`/tmp/isitai-bench/data/{train,test,test_ood,test_fr,test_fiction,test_attack}.jsonl`, one
JSON object per line:

```json
{"id": "raid:<uuid>", "text": "...", "label": 0, "source": "raid", "generator": "human",
 "domain": "news", "lang": "en", "n_words": 412}
```

`label`: 0 human, 1 AI. `generator`: model name, or `human`. `n_words`: `len(text.split())`.
`test_attack` rows also carry `attack`. `manifest.json` next to the files holds every count.

### Sources and licences

| Source | Hub id, revision | Licence (dataset card) | Used for |
|---|---|---|---|
| RAID | `liamdugan/raid` @ `865cac7`, `train.csv` | MIT | train, test, test_ood, test_attack |
| MAGE | `yaful/MAGE` @ `342663f`, `test_ood_set_gpt.csv` | Apache-2.0 | test_ood |
| HC3 (English test file) | shipped in `almanach/hc3_french_ood` @ `34acd9c` | CC-BY-SA-4.0 | test_ood |
| hc3_french_ood, native French sets | `almanach/hc3_french_ood` @ `34acd9c`, `data.tar.gz` | CC-BY-SA-4.0; FAQ part from MQA, CC0; ChatGPT / Bing output "Unknown" on the card | test_fr |
| MAiDE-up | `MichiganNLP/MAiDE-up` @ `045e993`, `all_data.csv` | MIT | test_fr |
| StoryScope | `jjrussell10/storyscope` @ `befcb67`, `stories_test.parquet` | MIT | test_fiction (AI side) |
| WritingPrompts | `euclaise/writingprompts` @ `35f0aa3`, test split | MIT on the card; the texts are Reddit r/WritingPrompts posts (fairseq archive, Fan et al. 2018) | test_fiction (human side) |

The licences are those declared on the Hub cards, read on 2026-11-12. The texts stay in
`/tmp`; nothing is redistributed.

### Splits (built 2026-11-12)

| Split | n | human / AI | Content |
|---|---|---|---|
| train | 4,000 | 2,000 / 2,000 | RAID, no attack. Domains abstracts, books, news, recipes, reddit, wiki (333-334 source documents each). Generators chatgpt, cohere, gpt2, gpt3, mistral, mistral-chat, mpt, mpt-chat (250 each). |
| test | 2,000 | 1,000 / 1,000 | Same distribution as train, other source documents (166-167 per domain, 125 per generator). |
| test_ood | 1,000 | 500 / 500 | (a) RAID held-out domains poetry and reviews, all 11 generators: 150 / 150. (b) RAID seen domains, held-out generators gpt4, cohere-chat, llama-chat: 150 / 150 (the human side of (b) is in-domain). (c) MAGE, GPT-4 on CNN, DialogSum, IMDb, PubMed: 100 / 100. (d) HC3, ChatGPT answers vs human answers (reddit, finance, medicine, open, wiki): 100 / 100. |
| test_fr | 990 | 495 / 495 | French. MAiDE-up hotel reviews: 281 Booking.com / 278 GPT-4. hc3_french_ood: 113 native ChatGPT answers + 104 Bing Chat answers (AI; two English refusals removed); 61 human answers written in Bing style + 153 human FAQ answers length-matched to the AI answers (human). |
| test_fiction | 500 | 250 / 250 | Human: r/WritingPrompts stories of at least 1,000 words. AI: StoryScope test stories, 50 each from GPT-5.4, Claude Sonnet 4.6, DeepSeek V3.2, Kimi K2.5, Gemini 3 Flash, each cut at a paragraph end to the length of one human story. |
| test_attack | 1,000 | 500 / 500 | RAID rows with an attack (11 attacks, 68 to 112 rows each), all domains and generators. Kept apart: never in train or test. |

Per generator (AI rows): test_ood gpt4 164, chatgpt 114, cohere-chat 64, llama-chat 64,
cohere 14, gpt2 14, gpt3 14, mistral 13, mistral-chat 13, mpt 13, mpt-chat 13. test_fr gpt4
278, chatgpt 113, bing-chat 104. Per language: French 990 rows (test_fr); every other split
is English (8,500 rows).

Sampling rules:

- RAID: one pass over `train.csv` (5,615,820 rows) keeps the 467,985 rows without attack,
  and the attacked rows of an "attack pool" of source documents
  (`sha1(source_id) % 100 < 2`, 253 documents). A source document is one human text plus
  its generations. Each sampled document gives its human text and ONE generation, the
  generators taken in rotation, so the two classes of a split cover the same topics.
- Texts under 10 words are dropped. A text enters the benchmark once (hash of the NFKC,
  lower-cased, whitespace-collapsed text).
- test_attack: an AI original gives one attacked variant, a human original two (under two
  different attacks), because the pool has 253 human originals.

### Leakage checks (assertions in `build_data.py`; the build fails otherwise)

1. Ids are unique inside each split and no id is in two splits.
2. No normalised text is in two splits, nor twice in one split.
3. RAID source documents are grouped by (domain, normalised title); the title is the
   generation prompt. One document per group is used, and no group is in two splits. So
   train shares no document and no prompt with any test split.
4. train and test hold no held-out generator, no held-out domain and no attacked row.
5. The attack-pool documents are only in test_attack.

MAGE, HC3, the French sets and the fiction sets share nothing with train by construction
(other corpora); check 2 covers them.

### Known limits of the data

- **Old generators.** RAID, MAGE and HC3 date from 2022-2023 (GPT-2 to GPT-4). Only
  test_fiction has 2026 models. A detector that looks good on test may not hold on current
  models; test_fiction is the only evidence here.
- **test_fiction is confounded by source.** StoryScope does not distribute its human
  stories (copyright), so the human side comes from another corpus: amateur Reddit stories
  from 2015-2018, 1,000 to 1,900 words, against AI stories written from detailed plot
  prompts and truncated to the same length. Two formatting differences remain: the
  WritingPrompts archive is tokenised and `build_data.py` detokenises it with regexes
  (residue is possible), and some AI stories start with a Markdown title (`# Title`). A
  high score on this split can come from genre, period or formatting. It is not the
  StoryScope task (about 5,000 words, professional human stories): that one cannot be
  rebuilt from public data.
- **test_fr is short and narrow.** Median 70 words (human) and 78 (AI). Reviews and question answering only;
  no French news, essays or fiction with an AI counterpart was found under a usable
  licence. The human reviews are raw Booking.com text (often lower-case, no punctuation),
  the GPT-4 reviews are polished. Bing Chat answers carry citation superscripts. The AI
  answers and the human FAQ answers do not answer the same questions. The translated
  HC3 rows of hc3_french_ood are NOT used (machine translation is not human French).
  MAiDE-up: rows are selected on `Review_Language == French`; the `Prompt_Language` column
  of the GPT-4 rows (18 values) is the language of the prompt, not of the review, and is
  not used. A stop-word check found every row of the split in French.
- **HC3 human answers are tokenised** in the source (`nature , we`, `does n't`): a
  formatting cue. Read the `hc3-*` rows of the domain breakdown with that in mind.
- **test_ood (b)** is out of distribution on the AI side only.
- **test_attack, paraphrase.** RAID labels a paraphrased human text as human, although a
  model rewrote it.
- **Length.** `length_baseline` (score = word count) measures the length confound of a
  split: AUROC 0.44 on test, 0.50 on test_ood, 0.55 on test_fr, 0.46 on test_fiction,
  0.46 on test_attack. No split can be solved by length alone. Per generator it is not
  flat (gpt3 0.17, gpt2 0.62 on test).
- **test_fiction length bucket.** 30 AI stories end between 948 and 999 words after the
  paragraph cut and fall in the 200-1000 bucket, where there is no human story.
- **Mixed texts** (human text edited by a model) are absent.

## Detector contract

A detector is one file `algos/<name>.py`:

```python
NAME = "my_detector"            # str
NEEDS_TRAINING = False          # bool
MODEL = "none"                  # the model and its size on disk, or "none"
BATCH_SIZE = 16                 # optional: chunk size of the scoring pass (default 16)

def fit(rows: list[dict]) -> None:      # only if NEEDS_TRAINING; rows = the train split
    ...

def score(texts: list[str]) -> list[float]:   # HIGHER = MORE LIKELY AI; one finite float per text
    ...
```

- `fit` receives the rows of `train.jsonl` and must use nothing else: no test split, no
  threshold tuned on a test split. A pretrained model downloaded from the Hub is allowed
  (say in `MODEL` what it was trained on: several public detectors were trained on RAID).
- `score` must accept a list of any length, including one text, and return finite floats.
  Any scale works; only the order matters for AUROC and the thresholds.
- Several related detectors in one file: expose
  `VARIANTS = {"variant-name": callable}`. Each callable takes no argument and returns an
  object with the same attributes (`NAME`, `NEEDS_TRAINING`, `MODEL`, `score`, and `fit`
  when trained; `BATCH_SIZE` optional). The module-level `score` is then optional. See
  `algos/example_template.py`.
- CPU only, 4 threads. `run.py` sets `OMP_NUM_THREADS` and the like to 4 before any import,
  calls `torch.set_num_threads(4)` and disables MPS and CUDA when the detector imported
  torch. With onnxruntime, set `intra_op_num_threads = 4` yourself
  (`from common import THREADS`). Do not start your own process pools.
- Pass `device="cpu"` explicitly to every model and pipeline. `run.py` makes
  `torch.backends.mps.is_available()` return False as soon as torch is imported (without
  that, a transformers pipeline picks `mps:0` on this Mac: tested), and aborts if memory was
  allocated on MPS anyway.
- No per-text cache of scores (in memory or on disk): the timing would measure the cache.
- Models and caches go under `/tmp/isitai-bench` (`HF_HOME=/tmp/isitai-bench/hf`, or
  `common.CACHE_DIR`). Nothing in the repository but the `.py` file.
- Load heavy models lazily or at import: both are counted in `load_seconds`, not in the
  per-text time (one warm-up call is made before timing).

### Runner

`run.py --algo NAME [--variant V] --split SPLIT [--limit N] [--time-n 100]`

`--split` takes one split, a comma-separated list, or `all` (every split except train).
The detector is loaded and fitted once per process. One file per split:
`/tmp/isitai-bench/results/<name>[.<variant>].<split>.json` with

`algo`, `split`, `n`, `scores`, `ids`, `seconds_total`, `seconds_per_text_median`,
`peak_rss_mb`, `fit_seconds`, `threads`, and also `module`, `variant`,
`seconds_per_text_p90`, `seconds_per_text_batched`, `timing_n`, `batch_size`,
`load_seconds`, `needs_training`, `n_train`, `model`, `limit`, `platform`, `finished_at`.

- `seconds_total`: wall time of the pass that produced the scores, `score()` called on
  consecutive chunks of `BATCH_SIZE` texts.
- `seconds_per_text_median`: median wall time of `score([text])` (batch of 1) over a seeded
  sample of up to 100 texts of the split, after one warm-up call, measured before the
  scoring pass. A sample, not the whole split, so that slow detectors are not scored twice.
- `peak_rss_mb`: peak resident memory of the process (import, fit and scoring together).
- With `--limit N` the file is named `...<split>.limitN.json` and `evaluate.py` ignores it.
- Files are written atomically; several runners can work in parallel on different
  detectors. Run timing-sensitive detectors alone: parallel runs share the 10 cores.

### Evaluator

`evaluate.py [--algo NAME ...] [--bootstrap 1000]` reads every result file, joins scores to
rows by id, and writes `/tmp/isitai-bench/results/summary.json` and `summary.md`.

- AUROC (ties count one half).
- TPR at 1% and 5% FPR. The threshold is the lowest `t` such that at most 1% (5%) of the
  human texts of the SAME split have `score > t`; a text is flagged when `score > t`. With
  tied scores the FPR reached can be lower; it is reported (`fpr@1`, `fpr@5`).
- Transfer: TPR **and FPR** of every other split at the thresholds fixed on `test`. This
  is the realistic figure for a shipped detector.
- 95% bootstrap intervals (1,000 resamples, stratified by label, fixed seed; same-split
  thresholds recomputed in each resample).
- Breakdowns by generator (its AI texts against all human texts of the split), domain,
  source, length bucket (under 50, 50-200, 200-1000, over 1000 words) and attack, at the
  thresholds of the whole split. A slice with one class has a null AUROC.
- Speed and memory from the result files.

## Baselines (2026-11-12)

| Detector | Split | AUROC | TPR@1%FPR | Flagged humans |
|---|---|---|---|---|
| isitai_rules | test | 0.502 | 0.4% | 0 of 1,000 |
| isitai_rules | test_ood | 0.500 | 0.0% | 0 of 500 |
| isitai_rules | test_fr | 0.496 | 0.0% | 4 of 495 (weak evidence only) |
| isitai_rules | test_fiction | 0.498 | 0.0% | 1 of 250 (weak evidence only) |
| isitai_rules | test_attack | 0.478 | 0.0% | 67 of 500 (zero-width-space attack) |
| length_baseline | test | 0.437 | 0.0% | - |

`isitai_rules` fires on 11 of the 8,490 texts outside test_attack (6 AI, 5 human), always the weak rule
`text.zero-width`, and never returns the verdict `ai-signal`: no strong evidence on any
human text (zero false signal), and almost no recall, as expected from rules that look for
copy-paste artefacts in texts that have none. About 0.003 ms per text, 43 MB peak RSS (the
Python process); the wheel is 4.6 MB. The wheel was built from the working tree of 2026-11-12 (rules hash
`bbe78b00b774e0fb`).
