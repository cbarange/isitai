//! Native module `isitai._isitai`. Returns JSON strings produced by the Rust core;
//! the Python wrapper parses them, so every language gets the same bytes.

use isitai::{check_bytes, check_path, check_text, Options, Rules};
use pyo3::prelude::*;

fn options(trust_anchors_pem: Option<String>, declared_mime: Option<String>) -> Options {
    Options {
        trust_anchors_pem,
        declared_mime,
    }
}

#[pyfunction]
fn check_text_json(py: Python<'_>, text: String) -> String {
    py.detach(|| check_text(&text, Rules::shared()).to_json())
}

#[pyfunction]
#[pyo3(signature = (data, trust_anchors_pem=None, declared_mime=None))]
fn check_bytes_json(
    py: Python<'_>,
    data: Vec<u8>,
    trust_anchors_pem: Option<String>,
    declared_mime: Option<String>,
) -> String {
    let opts = options(trust_anchors_pem, declared_mime);
    py.detach(|| check_bytes(&data, &opts, Rules::shared()).to_json())
}

#[pyfunction]
#[pyo3(signature = (path, trust_anchors_pem=None, declared_mime=None))]
fn check_file_json(
    py: Python<'_>,
    path: std::path::PathBuf,
    trust_anchors_pem: Option<String>,
    declared_mime: Option<String>,
) -> PyResult<String> {
    let opts = options(trust_anchors_pem, declared_mime);
    let report = py.detach(|| check_path(&path, &opts, Rules::shared()))?;
    Ok(report.to_json())
}

#[pymodule]
fn _isitai(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(check_text_json, m)?)?;
    m.add_function(wrap_pyfunction!(check_bytes_json, m)?)?;
    m.add_function(wrap_pyfunction!(check_file_json, m)?)?;
    Ok(())
}
