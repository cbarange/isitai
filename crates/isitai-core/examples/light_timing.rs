//! Time of the light text score per text. Usage:
//!   cargo run --release -p isitai --example light_timing -- FILE...
//! Prints the median and the 95th percentile of `check_text` with the score on and off.

use isitai::{check_text_with, Options, Rules};
use std::time::Instant;

/// Median and 95th percentile, in microseconds, of one `check_text_with` per text.
fn measure(texts: &[String], opts: &Options, rules: &Rules) -> (f64, f64) {
    let mut micros: Vec<f64> = texts
        .iter()
        .map(|text| {
            // Best of five runs: the first one pays for the caches.
            (0..5)
                .map(|_| {
                    let start = Instant::now();
                    std::hint::black_box(check_text_with(text, opts, rules));
                    start.elapsed().as_secs_f64() * 1e6
                })
                .fold(f64::INFINITY, f64::min)
        })
        .collect();
    micros.sort_by(f64::total_cmp);
    (micros[micros.len() / 2], micros[micros.len() * 95 / 100])
}

fn main() {
    let texts: Vec<String> = std::env::args()
        .skip(1)
        .filter_map(|path| std::fs::read_to_string(path).ok())
        .collect();
    if texts.is_empty() {
        eprintln!("usage: light_timing FILE...");
        std::process::exit(2);
    }
    let rules = Rules::embedded();
    let words: usize = texts.iter().map(|t| t.split_whitespace().count()).sum();
    let off = Options {
        score: false,
        ..Options::default()
    };
    let (on_median, on_p95) = measure(&texts, &Options::default(), &rules);
    let (off_median, off_p95) = measure(&texts, &off, &rules);
    println!(
        "{} texts, {} words on average",
        texts.len(),
        words / texts.len()
    );
    println!("score on : median {on_median:.0} us, p95 {on_p95:.0} us");
    println!("score off: median {off_median:.0} us, p95 {off_p95:.0} us");
}
