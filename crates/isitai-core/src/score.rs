//! Light statistical score for plain text (`text-light-v1`): no neural model, eleven
//! counts over the text, a dot product, and a calibration table per language.
//!
//! The output is a **likelihood ratio**, never a probability that the text is AI-made:
//! see `docs/research/FALLBACK-probabilistic.md`. A language without a calibration
//! table, or a text below the minimum length, gets no ratio.
//!
//! This file is the port of `bench/light/features.py` (the reference). The two must
//! agree: `tests/light_parity.rs` checks it on a fixture written by `bench/light/train.py`.
//! To keep them identical, character classes are explicit tables (no Unicode property
//! lookup), lengths count characters, and nothing here reads the layout of the text.

use serde::{Deserialize, Serialize};
use std::sync::OnceLock;

const MODEL_JSON: &str = include_str!("../model/light-text-v1.json");

/// Characters removed before anything is counted.
const ZERO_WIDTH: [char; 6] = [
    '\u{200B}', '\u{200C}', '\u{200D}', '\u{2060}', '\u{FEFF}', '\u{00AD}',
];
const MARKDOWN: [char; 6] = ['*', '#', '`', '|', '~', '_'];
const GLUE_BEFORE: [char; 9] = [',', '.', ';', ':', '!', '?', ')', ']', '\u{2026}'];
const GLUE_AFTER: [char; 2] = ['(', '['];
const CLITICS: [&str; 7] = ["n't", "'s", "'re", "'ve", "'m", "'ll", "'d"];
const BULLETS: [char; 4] = ['-', '*', '+', '\u{2022}'];
const SENTENCE_END: [char; 4] = ['.', '!', '?', '\u{2026}'];
const CLOSERS: [char; 4] = ['"', '\'', ')', ']'];
const BRACKETS: [char; 4] = ['(', ')', '[', ']'];

#[derive(Clone, Copy, PartialEq, Eq)]
enum Script {
    Latin,
    Greek,
    Cyrillic,
    Armenian,
    Hebrew,
    Arabic,
    Devanagari,
    Thai,
    Kana,
    Han,
    Hangul,
}

/// Order used to break ties between scripts.
const SCRIPTS: [(Script, &str); 11] = [
    (Script::Latin, "latin"),
    (Script::Greek, "greek"),
    (Script::Cyrillic, "cyrillic"),
    (Script::Armenian, "armenian"),
    (Script::Hebrew, "hebrew"),
    (Script::Arabic, "arabic"),
    (Script::Devanagari, "devanagari"),
    (Script::Thai, "thai"),
    (Script::Kana, "kana"),
    (Script::Han, "han"),
    (Script::Hangul, "hangul"),
];

/// Code point ranges that count as letters, with their script.
const LETTER_RANGES: [(u32, u32, Script); 31] = [
    (0x41, 0x5A, Script::Latin),
    (0x61, 0x7A, Script::Latin),
    (0xAA, 0xAA, Script::Latin),
    (0xB5, 0xB5, Script::Latin),
    (0xBA, 0xBA, Script::Latin),
    (0xC0, 0xD6, Script::Latin),
    (0xD8, 0xF6, Script::Latin),
    (0xF8, 0x2AF, Script::Latin),
    (0x370, 0x373, Script::Greek),
    (0x376, 0x377, Script::Greek),
    (0x37B, 0x37D, Script::Greek),
    (0x386, 0x386, Script::Greek),
    (0x388, 0x3FF, Script::Greek),
    (0x400, 0x481, Script::Cyrillic),
    (0x48A, 0x52F, Script::Cyrillic),
    (0x531, 0x556, Script::Armenian),
    (0x561, 0x587, Script::Armenian),
    (0x5D0, 0x5EA, Script::Hebrew),
    (0x620, 0x64A, Script::Arabic),
    (0x66E, 0x6D3, Script::Arabic),
    (0x900, 0x97F, Script::Devanagari),
    (0xE01, 0xE4E, Script::Thai),
    (0x1E00, 0x1EFF, Script::Latin),
    (0x1F00, 0x1FFF, Script::Greek),
    (0x3041, 0x3096, Script::Kana),
    (0x30A1, 0x30FA, Script::Kana),
    (0x3400, 0x4DBF, Script::Han),
    (0x4E00, 0x9FFF, Script::Han),
    (0xAC00, 0xD7A3, Script::Hangul),
    (0xFF21, 0xFF3A, Script::Latin),
    (0xFF41, 0xFF5A, Script::Latin),
];

/// Very frequent function words, used only to name the language of a Latin-script
/// text. Sorted by language code: the order breaks ties.
const STOPWORDS: [(&str, &str); 10] = [
    (
        "de",
        "der die das und ist nicht ein eine zu den mit von auf dem für sich des im auch",
    ),
    (
        "en",
        "the of and to in is that it for was with as on be by this are from at have",
    ),
    (
        "es",
        "el la los las de que y en un una es por con no para del se al lo su",
    ),
    (
        "fr",
        "le la les de des du et un une est en que qui dans pour pas au sur ce il",
    ),
    (
        "it",
        "il la di che e un una per non è in del della con le sono si da i gli",
    ),
    (
        "nl",
        "de het een en van is dat op te in niet zijn met voor er aan ook als bij",
    ),
    (
        "pl",
        "w i na z do nie się to jest że o jak po przez od dla za są ale tym",
    ),
    (
        "pt",
        "o a os as de que e do da em um uma para não com por se dos na no",
    ),
    (
        "ro",
        "și de la în a un o cu nu este pe care să din mai pentru se au fost",
    ),
    (
        "tr",
        "ve bir bu için ile de da çok daha olarak en gibi ama ne var kadar olan her",
    ),
];
/// Share of the words that must be function words of the language.
const LANG_MIN_SHARE: f64 = 0.10;
/// Ratio to the second language.
const LANG_MIN_MARGIN: f64 = 1.25;

// ------------------------------------------------------------------ model file

#[derive(Deserialize)]
struct Model {
    min_words: usize,
    max_tokens: usize,
    /// Characters read at most: bounds memory on a text without spaces.
    max_chars: usize,
    clip: f64,
    coverage: f64,
    ai_likely_min_ln_lr_low: f64,
    intercept: f64,
    features: Vec<Weight>,
    tables: std::collections::BTreeMap<String, Table>,
}

#[derive(Deserialize)]
struct Weight {
    name: String,
    mean: f64,
    scale: f64,
    weight: f64,
}

#[derive(Deserialize)]
struct Table {
    calibration_id: String,
    /// Sorted by `min_words`; a text uses the last bucket whose bound it reaches.
    buckets: Vec<Bucket>,
}

#[derive(Deserialize)]
struct Bucket {
    min_words: usize,
    n_human: usize,
    n_ai: usize,
    grid: Vec<f64>,
    ln_lr: Vec<f64>,
    ln_lr_low: Vec<f64>,
    ln_lr_high: Vec<f64>,
    threshold_high: f64,
    threshold_medium: f64,
}

fn model() -> &'static Model {
    static MODEL: OnceLock<Model> = OnceLock::new();
    MODEL.get_or_init(|| serde_json::from_str(MODEL_JSON).expect("embedded model is valid"))
}

// ------------------------------------------------------------------ public types

/// Strength of the statistical evidence that a text was written by a model.
///
/// `lr` is a likelihood ratio: how much more often this score is seen on AI text than on
/// human text in the calibration data. It is **not** a probability that the text is
/// AI-made. `posterior` is that probability, and exists only when the caller gave the
/// share of AI text it expects (`Options::prevalence`).
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Coefficient {
    /// `None`: the detector ran and abstained (see the report warnings).
    pub lr: Option<f64>,
    /// Bootstrap interval of `lr`, at the stated `coverage`.
    pub lr_interval: Option<[f64; 2]>,
    pub coverage: Option<f64>,
    /// Detector, language and date of the calibration table.
    pub calibration_id: Option<String>,
    pub prevalence_used: Option<f64>,
    pub posterior: Option<f64>,
}

/// What the score says about one text.
pub(crate) struct Assessment {
    pub coefficient: Coefficient,
    /// Score above the 1 % false-positive threshold of the table, interval above 1.
    pub ai_likely: bool,
    pub notes: Vec<String>,
    /// Why no ratio is given.
    pub warning: Option<String>,
}

/// Internal values, exposed for the parity test with the Python reference.
#[doc(hidden)]
#[derive(Debug, Clone, PartialEq)]
pub struct Raw {
    pub n_words: usize,
    pub language: String,
    pub logit: f64,
    /// ln of the ratio and of the two bounds of its interval; `None` when abstaining.
    pub ln_lr: Option<[f64; 3]>,
    pub ai_likely: bool,
}

/// Checks a prevalence given by a caller: a share strictly between 0 and 1.
pub fn validate_prevalence(p: f64) -> Result<f64, String> {
    if p.is_finite() && p > 0.0 && p < 1.0 {
        Ok(p)
    } else {
        Err(format!(
            "prevalence must be a number strictly between 0 and 1, got {p}"
        ))
    }
}

// ------------------------------------------------------------------ characters

fn letter_script(c: char) -> Option<Script> {
    let cp = c as u32;
    LETTER_RANGES
        .iter()
        .find(|(first, last, _)| *first <= cp && cp <= *last)
        .map(|(_, _, script)| *script)
}

fn is_letter(c: char) -> bool {
    letter_script(c).is_some()
}

/// Upper case: lower-casing changes the character.
fn is_upper(c: char) -> bool {
    let mut lower = c.to_lowercase();
    !(lower.next() == Some(c) && lower.next().is_none())
}

/// The whitespace set of the reference, which is not `char::is_whitespace`.
fn is_space(c: char) -> bool {
    matches!(
        c,
        '\t' | '\n' | '\x0B' | '\x0C' | '\r' | ' ' | '\u{85}' | '\u{A0}' | '\u{1680}' | '\u{2000}'
            ..='\u{200A}' | '\u{2028}' | '\u{2029}' | '\u{202F}' | '\u{205F}' | '\u{3000}'
    )
}

/// Typographic variants mapped to one character.
fn map_char(c: char) -> char {
    match c {
        '\u{2018}' | '\u{2019}' | '\u{201A}' | '\u{2032}' => '\'',
        '\u{201C}' | '\u{201D}' | '\u{201E}' | '\u{00AB}' | '\u{00BB}' => '"',
        '\u{2013}' | '\u{2015}' => '\u{2014}',
        '\u{2212}' => '-',
        other => other,
    }
}

// ------------------------------------------------------------------ normalisation

/// Characters of one line without its Markdown prefix (quote, heading, bullet) and
/// markers. Lazy: a line of many megabytes is never copied.
fn clean_line(line: &str) -> impl Iterator<Item = char> + '_ {
    let mut body = line.trim_start_matches(|c| is_space(c) || c == '>');
    let mut head = body.chars();
    if let (Some(first), Some(second)) = (head.next(), head.next()) {
        if BULLETS.contains(&first) && is_space(second) {
            body = &body[first.len_utf8()..];
        }
    }
    body.chars()
        .filter(|c| !ZERO_WIDTH.contains(c) && !MARKDOWN.contains(c))
        .map(map_char)
}

/// `[12]`, `[12].`: a reference mark left by a search assistant.
fn is_citation(token: &str) -> bool {
    let core: Vec<char> = token
        .trim_end_matches(['.', ',', ';', ':'])
        .chars()
        .collect();
    core.len() >= 3
        && core[0] == '['
        && core[core.len() - 1] == ']'
        && core[1..core.len() - 1].iter().all(char::is_ascii_digit)
}

fn is_link(token: &str) -> bool {
    token.contains("://") || token.starts_with("www.")
}

/// Adds one whitespace-separated token: dropped (link, reference mark), glued to the
/// token before it (punctuation or clitic set apart by a tokeniser), or appended.
/// Returns `false` when the token would be the one after `max_tokens`.
fn push_token(tokens: &mut Vec<String>, token: &str, max_tokens: usize) -> bool {
    if is_link(token) || is_citation(token) {
        return true;
    }
    let first = token.chars().next().expect("token is not empty");
    let glue = tokens.last().is_some_and(|last| {
        GLUE_BEFORE.contains(&first)
            || CLITICS.contains(&token)
            || last.chars().last().is_some_and(|c| GLUE_AFTER.contains(&c))
    });
    if glue {
        tokens
            .last_mut()
            .expect("glue needs a token")
            .push_str(token);
    } else {
        if tokens.len() == max_tokens {
            return false;
        }
        tokens.push(token.to_string());
    }
    true
}

/// Tokens of the first `max_chars` characters of the text, layout and markup removed, at
/// most `max_tokens` of them. Reading stops at the first token over the limit.
fn normalize(text: &str, max_tokens: usize, max_chars: usize) -> Vec<String> {
    let text = match text.char_indices().nth(max_chars) {
        Some((end, _)) => &text[..end],
        None => text,
    };
    let mut tokens: Vec<String> = Vec::new();
    let mut current = String::new();
    for line in text.split(['\n', '\r']) {
        // The closing space ends the last token of the line.
        for c in clean_line(line).chain(std::iter::once(' ')) {
            if !is_space(c) {
                current.push(c);
            } else if !current.is_empty() {
                if !push_token(&mut tokens, &current, max_tokens) {
                    return tokens;
                }
                current.clear();
            }
        }
    }
    tokens
}

/// Lower-cased words of a token: runs of letters, joined by an inner `'` or `-`.
fn words_of(token: &str) -> Vec<String> {
    let chars: Vec<char> = token.chars().collect();
    let mut out = Vec::new();
    let mut current = String::new();
    for (i, &c) in chars.iter().enumerate() {
        if is_letter(c) {
            current.extend(c.to_lowercase());
        } else if (c == '\'' || c == '-')
            && !current.is_empty()
            && chars.get(i + 1).is_some_and(|&next| is_letter(next))
        {
            current.push(c);
        } else if !current.is_empty() {
            out.push(std::mem::take(&mut current));
        }
    }
    if !current.is_empty() {
        out.push(current);
    }
    out
}

fn ends_sentence(token: &str) -> bool {
    token
        .trim_end_matches(CLOSERS)
        .chars()
        .last()
        .is_some_and(|c| SENTENCE_END.contains(&c))
}

// ------------------------------------------------------------------ language

/// Share of each script among the letters, in the order of `SCRIPTS`.
fn script_shares(tokens: &[String]) -> [f64; 11] {
    let mut counts = [0usize; 11];
    let mut total = 0usize;
    for c in tokens.iter().flat_map(|t| t.chars()) {
        if let Some(script) = letter_script(c) {
            let slot = SCRIPTS.iter().position(|(s, _)| *s == script);
            counts[slot.expect("every script is listed")] += 1;
            total += 1;
        }
    }
    let mut shares = [0.0; 11];
    if total > 0 {
        for (share, count) in shares.iter_mut().zip(counts) {
            *share = count as f64 / total as f64;
        }
    }
    shares
}

/// ISO 639-1 code for ten Latin-script languages, a script name for the other scripts,
/// or `unknown`. A guess from function words, not a language identifier.
fn detect_language(tokens: &[String], words: &[String]) -> &'static str {
    let shares = script_shares(tokens);
    let mut best = 0;
    for i in 1..shares.len() {
        if shares[i] > shares[best] {
            best = i;
        }
    }
    if shares[best] == 0.0 {
        return "unknown";
    }
    let (script, name) = SCRIPTS[best];
    if script != Script::Latin {
        let kana = SCRIPTS.iter().position(|(s, _)| *s == Script::Kana);
        if script == Script::Han && shares[kana.expect("kana is listed")] > 0.05 {
            return "kana";
        }
        return name;
    }
    if words.is_empty() {
        return "unknown";
    }
    let mut scored: Vec<(f64, &'static str)> = STOPWORDS
        .iter()
        .map(|(lang, list)| {
            let hits = words
                .iter()
                .filter(|w| list.split(' ').any(|s| s == w.as_str()))
                .count();
            (hits as f64 / words.len() as f64, *lang)
        })
        .collect();
    // Highest share first; the list is sorted by language code, and the sort is stable.
    scored.sort_by(|a, b| b.0.total_cmp(&a.0));
    let (top, lang) = scored[0];
    if top < LANG_MIN_SHARE || top < LANG_MIN_MARGIN * scored[1].0 {
        return "unknown";
    }
    lang
}

// ------------------------------------------------------------------ features

/// What is counted over the normalised text.
#[derive(Default)]
struct Counts {
    words: Vec<String>,
    /// Number of words of each sentence that has at least one word.
    sentence_lengths: Vec<usize>,
    /// Sentences whose first letter is not upper case.
    lower_starts: usize,
    /// Tokens of two letters or more, all upper case.
    all_caps: usize,
    brackets: usize,
    digits: usize,
    chars: usize,
}

fn count(tokens: &[String]) -> Counts {
    let mut c = Counts::default();
    let mut current = 0usize;
    // First letter of the sentence being read, once a word was seen.
    let mut start: Option<char> = None;
    for token in tokens {
        let token_words = words_of(token);
        if !token_words.is_empty() {
            let letters: Vec<char> = token.chars().filter(|&ch| is_letter(ch)).collect();
            if start.is_none() {
                start = Some(letters[0]);
            }
            if letters.len() > 1 && letters.iter().all(|&ch| is_upper(ch)) {
                c.all_caps += 1;
            }
        }
        current += token_words.len();
        c.words.extend(token_words);
        for ch in token.chars() {
            c.chars += 1;
            if BRACKETS.contains(&ch) {
                c.brackets += 1;
            } else if ch.is_ascii_digit() {
                c.digits += 1;
            }
        }
        if ends_sentence(token) && current > 0 {
            close_sentence(&mut c, &mut current, &mut start);
        }
    }
    if current > 0 {
        close_sentence(&mut c, &mut current, &mut start);
    }
    // The reference counts the characters of the tokens joined by one space.
    c.chars += tokens.len().saturating_sub(1);
    c
}

fn close_sentence(c: &mut Counts, current: &mut usize, start: &mut Option<char>) {
    c.sentence_lengths.push(*current);
    if !(*start).is_some_and(is_upper) {
        c.lower_starts += 1;
    }
    *current = 0;
    *start = None;
}

/// Mean and population standard deviation.
fn mean_sd(values: &[usize]) -> (f64, f64) {
    if values.is_empty() {
        return (0.0, 0.0);
    }
    let n = values.len() as f64;
    let mean = values.iter().sum::<usize>() as f64 / n;
    let var = values
        .iter()
        .map(|&v| (v as f64 - mean).powi(2))
        .sum::<f64>()
        / n;
    (mean, var.sqrt())
}

/// Value of one named feature. Names are those of `bench/light/features.py`.
fn feature(name: &str, c: &Counts) -> f64 {
    let lengths = &c.sentence_lengths;
    let n_words = c.words.len().max(1) as f64;
    let n_sentences = lengths.len().max(1) as f64;
    let (mean, sd) = mean_sd(lengths);
    let word_lengths: Vec<usize> = c.words.iter().map(|w| w.chars().count()).collect();
    match name {
        "sent_len_sd" => sd.min(100.0),
        "sent_len_cv" if mean > 0.0 => sd / mean,
        "sent_len_adjdiff" if lengths.len() > 1 && mean > 0.0 => {
            let total: usize = lengths.windows(2).map(|w| w[0].abs_diff(w[1])).sum();
            total as f64 / (lengths.len() - 1) as f64 / mean
        }
        "sent_len_cv" | "sent_len_adjdiff" => 0.0,
        "sent_short_frac" => lengths.iter().filter(|&&v| v <= 5).count() as f64 / n_sentences,
        "sent_lower_start_frac" => c.lower_starts as f64 / n_sentences,
        "word_len_mean" => mean_sd(&word_lengths).0,
        "word_len_sd" => mean_sd(&word_lengths).1,
        "word_long_frac" => word_lengths.iter().filter(|&&v| v >= 7).count() as f64 / n_words,
        "p_paren" => (c.brackets as f64 * (100.0 / n_words)).min(100.0),
        "digit_ratio" => c.digits as f64 / c.chars.max(1) as f64,
        "allcaps_frac" => c.all_caps as f64 / n_words,
        other => panic!("the embedded model names an unknown feature: {other}"),
    }
}

/// Weighted sum of the clipped z-scores.
fn logit(m: &Model, c: &Counts) -> f64 {
    m.features.iter().fold(m.intercept, |total, f| {
        let z = (feature(&f.name, c) - f.mean) / f.scale;
        total + f.weight * z.clamp(-m.clip, m.clip)
    })
}

// ------------------------------------------------------------------ calibration

/// Linear interpolation on the grid of a table, constant outside it.
fn interpolate(grid: &[f64], values: &[f64], x: f64) -> f64 {
    if x <= grid[0] {
        return values[0];
    }
    for i in 1..grid.len() {
        if x <= grid[i] {
            let t = (x - grid[i - 1]) / (grid[i] - grid[i - 1]);
            return values[i - 1] + t * (values[i] - values[i - 1]);
        }
    }
    values[values.len() - 1]
}

/// The length bucket of a text: the largest lower bound not above its word count.
fn bucket(table: &Table, n_words: usize) -> Option<&Bucket> {
    table.buckets.iter().rfind(|b| b.min_words <= n_words)
}

fn round4(x: f64) -> f64 {
    (x * 1e4).round() / 1e4
}

/// Internal values of the score for one text.
#[doc(hidden)]
pub fn raw(text: &str) -> Raw {
    raw_with_bucket(text).0
}

fn raw_with_bucket(text: &str) -> (Raw, Option<&'static Bucket>) {
    let m = model();
    let tokens = normalize(text, m.max_tokens, m.max_chars);
    let counts = count(&tokens);
    let language = detect_language(&tokens, &counts.words);
    let n_words = counts.words.len();
    let score = logit(m, &counts);
    let found = m
        .tables
        .get(language)
        .filter(|_| n_words >= m.min_words)
        .and_then(|table| bucket(table, n_words));
    let ln_lr = found.map(|b| {
        [
            interpolate(&b.grid, &b.ln_lr, score),
            interpolate(&b.grid, &b.ln_lr_low, score),
            interpolate(&b.grid, &b.ln_lr_high, score),
        ]
    });
    let ai_likely = found
        .zip(ln_lr)
        .is_some_and(|(b, ln)| score >= b.threshold_high && ln[1] > m.ai_likely_min_ln_lr_low);
    let raw = Raw {
        n_words,
        language: language.to_string(),
        logit: score,
        ln_lr,
        ai_likely,
    };
    (raw, found)
}

/// Scores one plain text. `prevalence`: share of AI text the caller expects, already
/// validated; without it no posterior is given.
pub(crate) fn assess(text: &str, prevalence: Option<f64>) -> Assessment {
    let m = model();
    let (raw, found) = raw_with_bucket(text);
    let abstain = |warning: String| Assessment {
        coefficient: Coefficient {
            lr: None,
            lr_interval: None,
            coverage: None,
            calibration_id: None,
            prevalence_used: None,
            posterior: None,
        },
        ai_likely: false,
        notes: Vec::new(),
        warning: Some(warning),
    };
    let Some(table) = m.tables.get(raw.language.as_str()) else {
        let known: Vec<&str> = m.tables.keys().map(String::as_str).collect();
        return abstain(format!(
            "score not given: no calibration table for `{}` text (tables: {})",
            raw.language,
            known.join(", ")
        ));
    };
    let (Some(b), Some(ln)) = (found, raw.ln_lr) else {
        return abstain(format!(
            "score not given: text too short ({} words, minimum {})",
            raw.n_words, m.min_words
        ));
    };
    let lr = ln[0].exp();
    let mut notes = vec![
        format!("language detected: {}", raw.language),
        format!("words analysed: {}", raw.n_words),
        format!(
            "calibration: {} human and {} AI texts of {} words or more, scored out of their source family",
            b.n_human, b.n_ai, b.min_words
        ),
    ];
    if raw.ai_likely {
        notes.push("score above the 1 % false-positive threshold of the table".into());
    } else if raw.logit >= b.threshold_medium {
        notes.push("score above the 5 % false-positive threshold of the table".into());
    }
    Assessment {
        coefficient: Coefficient {
            lr: Some(round4(lr)),
            lr_interval: Some([round4(ln[1].exp()), round4(ln[2].exp())]),
            coverage: Some(m.coverage),
            calibration_id: Some(table.calibration_id.clone()),
            prevalence_used: prevalence,
            posterior: prevalence.map(|p| round4(lr * p / (lr * p + 1.0 - p))),
        },
        ai_likely: raw.ai_likely,
        notes,
        warning: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_model_is_consistent() {
        let m = model();
        assert!(m.min_words >= 100);
        let empty = Counts::default();
        for f in &m.features {
            assert!(f.scale > 0.0, "{}", f.name);
            feature(&f.name, &empty); // panics on a name this file does not compute
        }
        for (lang, table) in &m.tables {
            assert!(table.calibration_id.contains(&format!("/{lang}/")));
            assert_eq!(table.buckets[0].min_words, m.min_words);
            for b in &table.buckets {
                assert!(b.grid.windows(2).all(|w| w[0] < w[1]));
                assert!(b.threshold_medium <= b.threshold_high);
                for i in 0..b.grid.len() {
                    assert!(b.ln_lr_low[i] <= b.ln_lr[i] && b.ln_lr[i] <= b.ln_lr_high[i]);
                }
            }
        }
    }

    #[test]
    fn layout_and_markup_do_not_change_the_tokens() {
        let plain = "The plan is simple. It has two parts (see below), and it's short.";
        let dressed = "## The plan\u{200B} is **simple**.\n\n> - It has two parts ( see below ) ,\r\n  and it 's   short .";
        assert_eq!(
            normalize(plain, 1000, 200_000),
            normalize(dressed, 1000, 200_000)
        );
        // French spacing before double punctuation, links and reference marks.
        assert_eq!(
            normalize(
                "Vraiment\u{202F}? Oui\u{A0}! https://example.com [12] fin",
                1000,
                200_000
            ),
            ["Vraiment?", "Oui!", "fin"]
        );
    }

    #[test]
    fn reading_stops_at_the_limits() {
        assert_eq!(normalize("a b c d", 2, 200_000), ["a", "b"]);
        // Punctuation glued to the last token still belongs to it.
        assert_eq!(normalize("a b . c", 2, 200_000), ["a", "b."]);
        assert_eq!(normalize("abcdef ghi", 1000, 4), ["abcd"]);
        assert_eq!(normalize("éèà ù", 1000, 2), ["éè"]);
    }

    #[test]
    fn words_and_sentences() {
        assert_eq!(words_of("L'État-major,"), ["l'état-major".to_string()]);
        assert_eq!(words_of("-a- 'b' c3d"), ["a", "b", "c", "d"]);
        let tokens = normalize("One two. three FOUR five! (Six.) seven", 1000, 200_000);
        let c = count(&tokens);
        assert_eq!(c.sentence_lengths, [2, 3, 1, 1]);
        assert_eq!(c.lower_starts, 2);
        assert_eq!(c.all_caps, 1);
        assert_eq!(c.brackets, 2);
    }

    #[test]
    fn language_guess() {
        let lang = |s: &str| {
            let tokens = normalize(s, 1000, 200_000);
            detect_language(&tokens, &count(&tokens).words)
        };
        assert_eq!(lang("The cat is on the mat and it is happy."), "en");
        assert_eq!(lang("Le chat est sur le tapis et il est content."), "fr");
        assert_eq!(lang("Это русский текст о погоде."), "cyrillic");
        assert_eq!(lang("これは日本語のテキストです。"), "kana");
        assert_eq!(lang("这是一个中文文本。"), "han");
        assert_eq!(lang("12345 !!!"), "unknown");
        assert_eq!(lang("Lorem ipsum dolor sit amet consectetur"), "unknown");
    }

    #[test]
    fn abstains_without_a_table_or_below_the_minimum() {
        let short = assess("The cat is on the mat and it is happy.", None);
        assert_eq!(short.coefficient.lr, None);
        assert!(short.warning.unwrap().contains("too short"));
        let french = "Le chat est sur le tapis et il est content de la vie. ".repeat(40);
        let report = assess(&french, Some(0.1));
        assert_eq!(report.coefficient.lr, None);
        assert_eq!(report.coefficient.prevalence_used, None);
        assert!(report
            .warning
            .unwrap()
            .contains("no calibration table for `fr`"));
        // The language is checked before the length: a short Chinese text is not "too short".
        let chinese = assess("这是一个中文文本。", None);
        assert!(chinese.warning.unwrap().contains("`han`"));
    }

    #[test]
    fn posterior_needs_a_prevalence() {
        let english =
            "The cat is on the mat and it is happy with the day that it has had. ".repeat(20);
        let without = assess(&english, None);
        let lr = without
            .coefficient
            .lr
            .expect("an English text of 300 words is scored");
        let [low, high] = without.coefficient.lr_interval.unwrap();
        assert!(low <= lr && lr <= high);
        assert_eq!(without.coefficient.posterior, None);
        assert_eq!(without.coefficient.coverage, Some(0.9));
        let with = assess(&english, Some(0.5));
        assert_eq!(with.coefficient.prevalence_used, Some(0.5));
        // At a prevalence of one half the posterior odds are the ratio itself.
        let posterior = with.coefficient.posterior.unwrap();
        assert!((posterior - lr / (lr + 1.0)).abs() < 1e-3);
        assert!(validate_prevalence(0.0).is_err());
        assert!(validate_prevalence(1.0).is_err());
        assert!(validate_prevalence(f64::NAN).is_err());
        assert_eq!(validate_prevalence(0.02), Ok(0.02));
    }
}
