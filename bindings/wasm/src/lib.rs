//! WebAssembly module for the browser demo (`site/`). Returns JSON strings produced
//! by the Rust core; the page parses them, so every language gets the same bytes.
//! Built by `site/build.sh` for `wasm32-unknown-unknown`.

use isitai::{check_bytes, check_text, validate_trust_anchors, Options, Rules};
use wasm_bindgen::prelude::*;

/// Fails on an unknown `effort` and on unusable trust anchors; `None` means the default.
/// The error is a `String`: a `JsError` can only be built inside a WebAssembly host.
fn options(effort: Option<String>, trust_anchors_pem: Option<String>) -> Result<Options, String> {
    if let Some(pem) = &trust_anchors_pem {
        validate_trust_anchors(pem)?;
    }
    let effort = effort.map(|e| e.parse()).transpose()?.unwrap_or_default();
    Ok(Options {
        trust_anchors_pem,
        effort,
        ..Options::default()
    })
}

#[wasm_bindgen]
pub fn check_text_json(text: &str) -> String {
    check_text(text, Rules::shared()).to_json()
}

/// Synchronous. Throws an `Error` on an unknown `effort` and on `trust_anchors_pem`
/// without a usable certificate.
#[wasm_bindgen]
pub fn check_bytes_json(
    bytes: &[u8],
    effort: Option<String>,
    trust_anchors_pem: Option<String>,
) -> Result<String, JsError> {
    let opts = options(effort, trust_anchors_pem).map_err(|e| JsError::new(&e))?;
    Ok(check_bytes(bytes, &opts, Rules::shared()).to_json())
}

#[cfg(test)]
mod tests {
    use super::options;
    use isitai::Effort;

    #[test]
    fn options_default_and_explicit() {
        assert_eq!(options(None, None).unwrap().effort, Effort::default());
        assert_eq!(
            options(Some("fast".into()), None).unwrap().effort,
            Effort::Fast
        );
    }

    #[test]
    fn unknown_effort_and_bad_anchors_are_errors() {
        assert!(options(Some("turbo".into()), None).is_err());
        assert!(options(None, Some("not a pem".into())).is_err());
    }
}
