//! In-process timing of `check_reader` per file, same protocol as bench/compare/*.
//! Usage: cargo run --release --example bench_files -- <iterations> FILE...
//! Prints one JSON line per file: {"file", "first_ms", "median_ms", "p95_ms", "verdict"}.

use isitai::{check_reader, Options, Rules};
use std::{fs::File, io::BufReader, time::Instant};

fn main() {
    let mut args = std::env::args().skip(1);
    let iterations: usize = args.next().and_then(|n| n.parse().ok()).unwrap_or(20);
    let start = Instant::now();
    let rules = Rules::embedded();
    eprintln!("rules_init_ms={:.3}", start.elapsed().as_secs_f64() * 1e3);
    let opts = Options::default();

    for path in args {
        let mut times = Vec::with_capacity(iterations);
        let mut verdict = String::new();
        for _ in 0..iterations {
            let t = Instant::now();
            let report = check_reader(BufReader::new(File::open(&path).unwrap()), &opts, &rules);
            times.push(t.elapsed().as_secs_f64() * 1e3);
            verdict = serde_json::to_value(report.verdict).unwrap().as_str().unwrap().to_string();
        }
        let first = times[0];
        times.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let median = times[times.len() / 2];
        let p95 = times[((times.len() as f64 * 0.95) as usize).min(times.len() - 1)];
        println!(
            "{}",
            serde_json::json!({ "file": path.rsplit('/').next().unwrap(), "first_ms": first, "median_ms": median, "p95_ms": p95, "verdict": verdict })
        );
    }
}
