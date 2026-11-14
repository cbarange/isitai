//! Spike: zero-shot AI-text scores (Binoculars, Fast-DetectGPT) from ONNX models, in Rust.
//!
//!   isitai-deep-spike --det bino|fdgpt --tokenizer tokenizer.json \
//!       --model observer.onnx [--model2 performer.onnx] --input texts.jsonl [--threads 4]
//!
//! Reads JSON Lines `{"id": ..., "text": ...}`; prints JSON Lines
//! `{"id", "n_tokens", "score", "ms", "ms_infer", "token_ids"}`. HIGHER score = MORE LIKELY AI.
//! Same formulas and truncation (512 tokens) as bench/detectors/algos/*.py. The criterion is
//! computed row by row in f64 from the f32 logits: no (T x V) temporary besides the logits.

use std::io::{BufRead, Write};

const MAX_TOKENS: usize = 512;

/// A causal LM: token ids -> logits, row-major (T x V).
trait Lm {
    fn logits(&mut self, ids: &[u32]) -> (Vec<f32>, usize);
}

#[cfg(any(feature = "ort-download", feature = "ort-dynamic"))]
mod rt {
    use ort::session::Session;
    use ort::value::Tensor;

    pub const NAME: &str = "ort";
    pub struct Model(Session);
    // ONNX Runtime allows one environment per process: shared by both models.
    static ENV: std::sync::OnceLock<ort::environment::Environment> = std::sync::OnceLock::new();

    pub fn load(path: &str, threads: usize) -> Model {
        // load-dynamic: the library path comes from ORT_DYLIB_PATH
        let env = ENV.get_or_init(|| ort::init().with_name("isitai-deep-spike").with_telemetry(false).build().unwrap());
        let s = Session::builder(env)
            .unwrap()
            .with_intra_threads(threads)
            .unwrap()
            .with_inter_threads(1)
            .unwrap()
            .commit_from_file(path)
            .unwrap();
        Model(s)
    }

    impl super::Lm for Model {
        fn logits(&mut self, ids: &[u32]) -> (Vec<f32>, usize) {
            let data: Vec<i64> = ids.iter().map(|&i| i as i64).collect();
            let input = Tensor::from_array(([1usize, ids.len()], data)).unwrap();
            let out = self.0.run(ort::inputs!["input_ids" => input]).unwrap();
            let (shape, v) = out[0].try_extract_tensor::<f32>().unwrap();
            let vocab = shape[shape.len() - 1] as usize;
            (v.to_vec(), vocab)
        }
    }
}

#[cfg(feature = "rten-rt")]
mod rt {
    use rten_tensor::prelude::*;
    use rten_tensor::NdTensor;

    pub const NAME: &str = "rten";
    pub struct Model(rten::Model);

    pub fn load(path: &str, _threads: usize) -> Model {
        // threads: RTEN_NUM_THREADS environment variable (read once by rten)
        Model(rten::Model::load_file(path).unwrap())
    }

    impl super::Lm for Model {
        fn logits(&mut self, ids: &[u32]) -> (Vec<f32>, usize) {
            let data: Vec<i32> = ids.iter().map(|&i| i as i32).collect();
            let input = NdTensor::from_data([1, ids.len()], data);
            let out = self.0.run_one(input.view().into(), None).unwrap();
            let out: NdTensor<f32, 3> = out.try_into().unwrap();
            let vocab = out.size(2);
            (out.to_vec(), vocab)
        }
    }
}

#[cfg(feature = "tract-rt")]
mod rt {
    use tract_onnx::prelude::*;

    pub const NAME: &str = "tract";
    pub struct Model(std::sync::Arc<TypedRunnableModel>);

    pub fn load(path: &str, _threads: usize) -> Model {
        let m = tract_onnx::onnx()
            .model_for_path(path)
            .unwrap()
            .into_optimized()
            .unwrap()
            .into_runnable()
            .unwrap();
        Model(m)
    }

    impl super::Lm for Model {
        fn logits(&mut self, ids: &[u32]) -> (Vec<f32>, usize) {
            let data: Vec<i64> = ids.iter().map(|&i| i as i64).collect();
            let t = tract_ndarray::Array2::from_shape_vec((1, ids.len()), data).unwrap();
            let out = self.0.run(tvec!(Tensor::from(t).into())).unwrap();
            let v = out[0].to_plain_array_view::<f32>().unwrap();
            let vocab = v.shape()[2];
            (v.iter().copied().collect(), vocab)
        }
    }
}

/// log-softmax of one row, in f64, written into `out`.
fn log_softmax_row(row: &[f32], out: &mut [f64]) {
    let m = row.iter().copied().fold(f32::NEG_INFINITY, f32::max) as f64;
    let mut s = 0.0f64;
    for &x in row {
        s += (x as f64 - m).exp();
    }
    let lse = m + s.ln();
    for (o, &x) in out.iter_mut().zip(row) {
        *o = x as f64 - lse;
    }
}

/// Binoculars: -(ppl / x_ppl). ppl over T-1 positions, x_ppl over all T (official code).
fn binoculars(obs: &[f32], perf: &[f32], vocab: usize, ids: &[u32]) -> f64 {
    let t = ids.len();
    let (mut lq, mut lp) = (vec![0f64; vocab], vec![0f64; vocab]);
    let (mut ppl, mut xppl) = (0f64, 0f64);
    for i in 0..t {
        log_softmax_row(&perf[i * vocab..(i + 1) * vocab], &mut lq);
        log_softmax_row(&obs[i * vocab..(i + 1) * vocab], &mut lp);
        if i + 1 < t {
            ppl -= lq[ids[i + 1] as usize];
        }
        let mut x = 0f64;
        for v in 0..vocab {
            x += lp[v].exp() * lq[v];
        }
        xppl -= x;
    }
    let b = (ppl / (t - 1) as f64) / (xppl / t as f64);
    if b.is_finite() { -b } else { -1.0 }
}

/// Fast-DetectGPT analytic criterion, sampling model = scoring model.
fn fast_detectgpt(logits: &[f32], vocab: usize, ids: &[u32]) -> f64 {
    let t = ids.len();
    let mut lp = vec![0f64; vocab];
    let (mut ll, mut mean_sum, mut var_sum) = (0f64, 0f64, 0f64);
    for i in 0..t - 1 {
        log_softmax_row(&logits[i * vocab..(i + 1) * vocab], &mut lp);
        ll += lp[ids[i + 1] as usize];
        let (mut m, mut m2) = (0f64, 0f64);
        for &l in &lp {
            let p = l.exp();
            m += p * l;
            m2 += p * l * l;
        }
        mean_sum += m;
        var_sum += m2 - m * m;
    }
    if !(var_sum > 0.0) {
        return 0.0;
    }
    let v = (ll - mean_sum) / var_sum.sqrt();
    if v.is_finite() { v } else { 0.0 }
}

fn arg(args: &[String], name: &str) -> Option<String> {
    args.iter().position(|a| a == name).and_then(|i| args.get(i + 1).cloned())
}

#[cfg(any(feature = "ort-download", feature = "ort-dynamic", feature = "rten-rt", feature = "tract-rt"))]
fn main() {
    let args: Vec<String> = std::env::args().collect();
    let det = arg(&args, "--det").expect("--det bino|fdgpt");
    let threads: usize = arg(&args, "--threads").map(|s| s.parse().unwrap()).unwrap_or(4);
    let mut tok = tokenizers::Tokenizer::from_file(arg(&args, "--tokenizer").expect("--tokenizer")).unwrap();
    tok.with_truncation(None).unwrap();
    tok.with_padding(None);
    let t0 = std::time::Instant::now();
    let mut m1 = rt::load(&arg(&args, "--model").expect("--model"), threads);
    let mut m2 = arg(&args, "--model2").map(|p| rt::load(&p, threads));
    eprintln!("runtime {} threads {} load {:.2}s", rt::NAME, threads, t0.elapsed().as_secs_f64());
    let input = std::fs::File::open(arg(&args, "--input").expect("--input")).unwrap();
    let out = std::io::stdout();
    let mut out = out.lock();
    for line in std::io::BufReader::new(input).lines() {
        let row: serde_json::Value = serde_json::from_str(&line.unwrap()).unwrap();
        let text = row["text"].as_str().unwrap();
        let t = std::time::Instant::now();
        // add_special_tokens = true: the Python default of the benchmark
        let enc = tok.encode(text, true).unwrap();
        let ids: Vec<u32> = enc.get_ids().iter().copied().take(MAX_TOKENS).collect();
        let mut infer_ms = 0.0;
        let score = if ids.len() < 2 {
            if det == "bino" { -1.0 } else { 0.0 }
        } else if det == "bino" {
            let ti = std::time::Instant::now();
            let (obs, vocab) = m1.logits(&ids);
            let (perf, _) = m2.as_mut().expect("--model2").logits(&ids);
            infer_ms = ti.elapsed().as_secs_f64() * 1e3;
            binoculars(&obs, &perf, vocab, &ids)
        } else {
            let ti = std::time::Instant::now();
            let (l, vocab) = m1.logits(&ids);
            infer_ms = ti.elapsed().as_secs_f64() * 1e3;
            fast_detectgpt(&l, vocab, &ids)
        };
        let ms = t.elapsed().as_secs_f64() * 1e3;
        // ms = tokenizer + model(s) + criterion; ms_infer = model forward pass(es) only
        let rec = serde_json::json!({"id": row["id"], "n_tokens": ids.len(), "score": score, "ms": ms, "ms_infer": infer_ms, "token_ids": ids});
        writeln!(out, "{rec}").unwrap();
    }
}

#[cfg(not(any(feature = "ort-download", feature = "ort-dynamic", feature = "rten-rt", feature = "tract-rt")))]
fn main() {
    let _ = (binoculars as fn(&[f32], &[f32], usize, &[u32]) -> f64, fast_detectgpt as fn(&[f32], usize, &[u32]) -> f64, arg as fn(&[String], &str) -> Option<String>, MAX_TOKENS);
    eprintln!("build with one of: --features ort-download | ort-dynamic | rten-rt | tract-rt");
}
