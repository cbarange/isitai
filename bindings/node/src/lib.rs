//! Native addon for the `isitai` npm package. Returns JSON strings produced by the
//! Rust core; `index.js` parses them, so every language gets the same bytes.

use isitai::{check_bytes, check_path, check_text, Options, Rules};
use napi::bindgen_prelude::*;
use napi_derive::napi;

fn options(trust_anchors_pem: Option<String>, declared_mime: Option<String>) -> Options {
    Options { trust_anchors_pem, declared_mime }
}

#[napi]
pub fn check_text_json(text: String) -> String {
    check_text(&text, Rules::shared()).to_json()
}

/// Synchronous: meant for in-memory uploads. Use `checkFileJson` for files on disk.
#[napi]
pub fn check_buffer_json(data: Buffer, trust_anchors_pem: Option<String>, declared_mime: Option<String>) -> String {
    check_bytes(&data, &options(trust_anchors_pem, declared_mime), Rules::shared()).to_json()
}

pub struct CheckFileTask {
    path: String,
    opts: Options,
}

impl Task for CheckFileTask {
    type Output = String;
    type JsValue = String;

    fn compute(&mut self) -> Result<Self::Output> {
        check_path(std::path::Path::new(&self.path), &self.opts, Rules::shared())
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
) -> AsyncTask<CheckFileTask> {
    AsyncTask::new(CheckFileTask { path, opts: options(trust_anchors_pem, declared_mime) })
}
