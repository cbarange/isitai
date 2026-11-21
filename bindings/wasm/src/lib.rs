//! WebAssembly module for the browser demo (`site/`). Returns JSON strings produced
//! by the Rust core; the page parses them, so every language gets the same bytes.
//! Built by `site/build.sh` for `wasm32-unknown-unknown`.

use isitai::{
    check_bytes, check_text_with, validate_prevalence, validate_trust_anchors, Options, Rules,
};
use wasm_bindgen::prelude::*;

/// Fails on an unknown `effort`, on unusable trust anchors and on a prevalence outside
/// ]0, 1[; `None` means the default.
/// The error is a `String`: a `JsError` can only be built inside a WebAssembly host.
fn options(
    effort: Option<String>,
    trust_anchors_pem: Option<String>,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> Result<Options, String> {
    if let Some(pem) = &trust_anchors_pem {
        validate_trust_anchors(pem)?;
    }
    let effort = effort.map(|e| e.parse()).transpose()?.unwrap_or_default();
    let prevalence = prevalence.map(validate_prevalence).transpose()?;
    Ok(Options {
        trust_anchors_pem,
        effort,
        score: score.unwrap_or(true),
        prevalence,
        ..Options::default()
    })
}

/// `score` (default true) turns the statistical score of plain text on or off;
/// `prevalence` (strictly between 0 and 1) adds a posterior to the likelihood ratio.
/// Throws an `Error` on a prevalence outside that range.
#[wasm_bindgen]
pub fn check_text_json(
    text: &str,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> Result<String, JsError> {
    let opts = options(None, None, score, prevalence).map_err(|e| JsError::new(&e))?;
    Ok(check_text_with(text, &opts, Rules::shared()).to_json())
}

/// Synchronous. Throws an `Error` on an unknown `effort` and on `trust_anchors_pem`
/// without a usable certificate.
#[wasm_bindgen]
pub fn check_bytes_json(
    bytes: &[u8],
    effort: Option<String>,
    trust_anchors_pem: Option<String>,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> Result<String, JsError> {
    let opts =
        options(effort, trust_anchors_pem, score, prevalence).map_err(|e| JsError::new(&e))?;
    Ok(check_bytes(bytes, &opts, Rules::shared()).to_json())
}

#[cfg(test)]
mod tests {
    use super::options;
    use isitai::Effort;

    #[test]
    fn options_default_and_explicit() {
        let default = options(None, None, None, None).unwrap();
        assert_eq!(default.effort, Effort::default());
        assert!(default.score);
        assert_eq!(default.prevalence, None);
        let explicit = options(Some("fast".into()), None, Some(false), Some(0.1)).unwrap();
        assert_eq!(explicit.effort, Effort::Fast);
        assert!(!explicit.score);
        assert_eq!(explicit.prevalence, Some(0.1));
    }

    #[test]
    fn unknown_effort_and_bad_anchors_are_errors() {
        assert!(options(Some("turbo".into()), None, None, None).is_err());
        assert!(options(None, Some("not a pem".into()), None, None).is_err());
        assert!(options(None, None, None, Some(1.5)).is_err());
    }
}
