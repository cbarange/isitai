//! The Rust port of the light text score gives the numbers of the Python reference.
//!
//! `bench/light/train.py` writes `fixtures/light_parity.json`: slices of tracked
//! repository files (the raw texts of the golden set) and inline edge cases, each with
//! the values of `bench/light/features.py`. Tolerance: 1e-3 on the logit and on ln LR.

use serde::Deserialize;
use std::path::Path;

const TOLERANCE: f64 = 1e-3;

#[derive(Deserialize)]
struct Entry {
    file: Option<String>,
    start: Option<usize>,
    end: Option<usize>,
    text: Option<String>,
    expect: Expect,
}

#[derive(Deserialize)]
struct Expect {
    n_words: usize,
    language: String,
    status: String,
    logit: f64,
    ln_lr: Option<f64>,
    ln_lr_low: Option<f64>,
    ln_lr_high: Option<f64>,
    ai_likely: Option<bool>,
}

/// Characters `start..end` of a file, as Python slices a `str`.
fn slice(text: &str, start: usize, end: usize) -> String {
    text.chars().skip(start).take(end - start).collect()
}

#[test]
fn rust_and_python_give_the_same_score() {
    let manifest = Path::new(env!("CARGO_MANIFEST_DIR"));
    let fixture = std::fs::read_to_string(manifest.join("tests/fixtures/light_parity.json"))
        .expect("fixture written by bench/light/train.py");
    let entries: Vec<Entry> = serde_json::from_str(&fixture).expect("valid fixture");
    let root = manifest.join("../..");
    let (mut compared, mut scored, mut worst) = (0usize, 0usize, 0f64);
    for (i, entry) in entries.iter().enumerate() {
        let text = match (&entry.file, &entry.text) {
            (Some(file), _) => {
                // Python read these files with universal newlines; a Windows checkout
                // may hold CRLF, which would shift every character offset.
                let content = std::fs::read_to_string(root.join(file))
                    .unwrap_or_else(|e| panic!("{file}: {e} (the fixture names repository files)"))
                    .replace("\r\n", "\n")
                    .replace('\r', "\n");
                slice(&content, entry.start.unwrap(), entry.end.unwrap())
            }
            (None, Some(text)) => text.clone(),
            (None, None) => panic!("entry {i} has no text"),
        };
        let raw = isitai::light_score_raw(&text);
        let e = &entry.expect;
        assert_eq!(raw.n_words, e.n_words, "entry {i}: word count");
        assert_eq!(raw.language, e.language, "entry {i}: language");
        let mut gap = (raw.logit - e.logit).abs();
        match (raw.ln_lr, e.status.as_str()) {
            (Some(ln), "ok") => {
                let expected = [
                    e.ln_lr.unwrap(),
                    e.ln_lr_low.unwrap(),
                    e.ln_lr_high.unwrap(),
                ];
                for (got, want) in ln.iter().zip(expected) {
                    gap = gap.max((got - want).abs());
                }
                assert_eq!(Some(raw.ai_likely), e.ai_likely, "entry {i}: ai-likely");
                scored += 1;
            }
            (None, "no-table" | "too-short") => assert!(!raw.ai_likely),
            (got, status) => panic!("entry {i}: Python says {status}, Rust gives {got:?}"),
        }
        assert!(gap <= TOLERANCE, "entry {i}: gap {gap}");
        worst = worst.max(gap);
        compared += 1;
    }
    println!("parity: {compared} texts, {scored} with a ratio, largest gap {worst:e}");
    assert!(compared >= 200, "the fixture must hold at least 200 texts");
    assert!(scored >= 100, "at least 100 texts must get a ratio");
}
