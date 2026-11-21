#!/usr/bin/env bash
# Runs the Rust binaries on the parity texts. Usage: run_rust.sh THREADS [runtime ...]
# Output: /tmp/isitai-deep/rust-runs/<runtime>.<det>.<prec>.t<threads>.jsonl and .time (peak RSS from /usr/bin/time -l)
set -u
T=${1:-4}; shift || true
RUNTIMES=${*:-"ort-dyn rten"}
D=/tmp/isitai-deep; M=$D/models; O=$D/rust-runs; mkdir -p $O
export ORT_DYLIB_PATH=$D/venv/lib/python3.12/site-packages/onnxruntime/capi/libonnxruntime.1.31.1.dylib
export RTEN_NUM_THREADS=$T
for rt in $RUNTIMES; do
  for prec in ${PRECS:-fp32 int8}; do
    [ -n "${SKIP_BINO:-}" ] || /usr/bin/time -l $D/spike-$rt --det bino --threads $T --tokenizer $M/smollm2-135m/tokenizer.json \
      --model $M/smollm2-135m/$prec.onnx --model2 $M/smollm2-135m-instruct/$prec.onnx \
      --input $D/texts/parity.jsonl > $O/$rt.bino.$prec.t$T.jsonl 2> $O/$rt.bino.$prec.t$T.time
    for fm in ${FD_MODELS:-smollm2-135m neo125}; do
      /usr/bin/time -l $D/spike-$rt --det fdgpt --threads $T --tokenizer $M/$fm/tokenizer.json \
        --model $M/$fm/$prec.onnx \
        --input $D/texts/parity.jsonl > $O/$rt.fdgpt-$fm.$prec.t$T.jsonl 2> $O/$rt.fdgpt-$fm.$prec.t$T.time
    done
  done
done
