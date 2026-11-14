//! Native addon for the `isitai` npm package. Returns JSON strings produced by the
//! Rust core; `index.js` parses them, so every language gets the same bytes.

use isitai::{
    check_bytes, check_path, check_text_with, validate_prevalence, validate_trust_anchors, Options,
    Rules,
};
use napi::bindgen_prelude::*;
use napi_derive::napi;

/// Fails on an unknown `effort`, on unusable trust anchors and on a prevalence outside
/// ]0, 1[; `None` means the default.
fn options(
    trust_anchors_pem: Option<String>,
    declared_mime: Option<String>,
    effort: Option<String>,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> Result<Options> {
    if let Some(pem) = &trust_anchors_pem {
        validate_trust_anchors(pem).map_err(Error::from_reason)?;
    }
    let effort = effort
        .map(|e| e.parse().map_err(Error::from_reason))
        .transpose()?
        .unwrap_or_default();
    let prevalence = prevalence
        .map(|p| validate_prevalence(p).map_err(Error::from_reason))
        .transpose()?;
    Ok(Options {
        trust_anchors_pem,
        declared_mime,
        effort,
        score: score.unwrap_or(true),
        prevalence,
    })
}

/// Default `maxBytes` of `checkStream`: the constant of the core.
#[napi]
pub const DEFAULT_MAX_STREAM_BYTES: f64 = isitai::DEFAULT_MAX_STREAM_BYTES as f64;

#[napi]
pub fn check_text_json(
    text: String,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> Result<String> {
    let opts = options(None, None, None, score, prevalence)?;
    Ok(check_text_with(&text, &opts, Rules::shared()).to_json())
}

/// Synchronous: meant for in-memory uploads. Use `checkFileJson` for files on disk.
#[napi]
pub fn check_buffer_json(
    data: Buffer,
    trust_anchors_pem: Option<String>,
    declared_mime: Option<String>,
    effort: Option<String>,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> Result<String> {
    let opts = options(trust_anchors_pem, declared_mime, effort, score, prevalence)?;
    Ok(check_bytes(&data, &opts, Rules::shared()).to_json())
}

pub struct CheckFileTask {
    path: String,
    opts: Options,
}

impl Task for CheckFileTask {
    type Output = String;
    type JsValue = String;

    fn compute(&mut self) -> Result<Self::Output> {
        check_path(
            std::path::Path::new(&self.path),
            &self.opts,
            Rules::shared(),
        )
        .map(|r| r.to_json())
        .map_err(|e| Error::from_reason(format!("{}: {e}", self.path)))
    }

    fn resolve(&mut self, _env: Env, output: Self::Output) -> Result<Self::JsValue> {
        Ok(output)
    }
}

/// Runs on the libuv thread pool, off the event loop. The file is streamed.
#[napi]
pub fn check_file_json(
    path: String,
    trust_anchors_pem: Option<String>,
    declared_mime: Option<String>,
    effort: Option<String>,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> Result<AsyncTask<CheckFileTask>> {
    Ok(AsyncTask::new(CheckFileTask {
        path,
        opts: options(trust_anchors_pem, declared_mime, effort, score, prevalence)?,
    }))
}
