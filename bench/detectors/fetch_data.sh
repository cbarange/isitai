#!/usr/bin/env bash
# Downloads the raw files of the detector benchmark into /tmp/isitai-bench/raw.
# Nothing is written in the repository. About 1.9 GB kept; the 11.8 GB RAID CSV is
# streamed through fetch_raid.py and never stored (about 10 minutes).
set -euo pipefail
BENCH="${ISITAI_BENCH_DIR:-/tmp/isitai-bench}"
RAW="${BENCH}/raw"
PY="${BENCH}/venv/bin/python"
HERE="$(cd "$(dirname "$0")" && pwd)"
HF="https://huggingface.co/datasets"
mkdir -p "${RAW}/raid" "${RAW}/mage" "${RAW}/hc3fr/x" "${RAW}/maideup" "${RAW}/storyscope" "${RAW}/wp"

get() { [ -s "$2" ] || curl -fsSL -o "$2" "$1"; }

# RAID (MIT): train.csv, the only public split with labels for every row.
if [ ! -s "${RAW}/raid/none.jsonl" ]; then
  curl -fsSL "${HF}/liamdugan/raid/resolve/main/train.csv" | "${PY}" "${HERE}/fetch_raid.py" "${RAW}/raid"
fi
# MAGE (Apache-2.0): GPT-4 on unseen domains.
get "${HF}/yaful/MAGE/resolve/main/test_ood_set_gpt.csv" "${RAW}/mage/test_ood_set_gpt.csv"
# almanach/hc3_french_ood (CC-BY-SA-4.0): native French sets and the HC3 English test file.
get "${HF}/almanach/hc3_french_ood/resolve/main/data.tar.gz" "${RAW}/hc3fr/data.tar.gz"
[ -d "${RAW}/hc3fr/x/data" ] || tar xzf "${RAW}/hc3fr/data.tar.gz" -C "${RAW}/hc3fr/x"
# MAiDE-up (MIT): hotel reviews, Booking.com vs GPT-4, 10 languages; French rows are used.
get "${HF}/MichiganNLP/MAiDE-up/resolve/main/all_data.csv" "${RAW}/maideup/all_data.csv"
# StoryScope (MIT): AI stories of the test prompts (human stories are not distributed).
get "${HF}/jjrussell10/storyscope/resolve/main/stories_test.parquet" "${RAW}/storyscope/stories_test.parquet"
# WritingPrompts (MIT on the Hub; Reddit r/WritingPrompts stories, fairseq archive), test split.
get "${HF}/euclaise/writingprompts/resolve/main/data/test-00000-of-00001-16503b0c26ed00c6.parquet" "${RAW}/wp/test.parquet"
echo "raw files ready in ${RAW}"
