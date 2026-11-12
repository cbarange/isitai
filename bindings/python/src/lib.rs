//! Native module `isitai._isitai`. Returns JSON strings produced by the Rust core;
//! the Python wrapper parses them, so every language gets the same bytes.

use isitai::{
    check_bytes, check_path, check_text_with, validate_prevalence, validate_trust_anchors, Options,
    Rules,
};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

/// Fails on an unknown `effort`, on unusable trust anchors and on a prevalence outside
/// ]0, 1[; `None` means the default.
fn options(
    trust_anchors_pem: Option<String>,
    declared_mime: Option<String>,
    effort: Option<String>,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> PyResult<Options> {
    if let Some(pem) = &trust_anchors_pem {
        validate_trust_anchors(pem).map_err(PyValueError::new_err)?;
    }
    let effort = effort
        .map(|e| e.parse().map_err(PyValueError::new_err))
        .transpose()?
        .unwrap_or_default();
    let prevalence = prevalence
        .map(|p| validate_prevalence(p).map_err(PyValueError::new_err))
        .transpose()?;
    Ok(Options {
        trust_anchors_pem,
        declared_mime,
        effort,
        score: score.unwrap_or(true),
        prevalence,
    })
}

#[pyfunction]
#[pyo3(signature = (text, score=None, prevalence=None))]
fn check_text_json(
    py: Python<'_>,
    text: String,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> PyResult<String> {
    let opts = options(None, None, None, score, prevalence)?;
    Ok(py.detach(|| check_text_with(&text, &opts, Rules::shared()).to_json()))
}

#[pyfunction]
#[pyo3(signature = (data, trust_anchors_pem=None, declared_mime=None, effort=None, score=None, prevalence=None))]
fn check_bytes_json(
    py: Python<'_>,
    data: Vec<u8>,
    trust_anchors_pem: Option<String>,
    declared_mime: Option<String>,
    effort: Option<String>,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> PyResult<String> {
    let opts = options(trust_anchors_pem, declared_mime, effort, score, prevalence)?;
    Ok(py.detach(|| check_bytes(&data, &opts, Rules::shared()).to_json()))
}

#[pyfunction]
#[pyo3(signature = (path, trust_anchors_pem=None, declared_mime=None, effort=None, score=None, prevalence=None))]
fn check_file_json(
    py: Python<'_>,
    path: std::path::PathBuf,
    trust_anchors_pem: Option<String>,
    declared_mime: Option<String>,
    effort: Option<String>,
    score: Option<bool>,
    prevalence: Option<f64>,
) -> PyResult<String> {
    let opts = options(trust_anchors_pem, declared_mime, effort, score, prevalence)?;
    let report = py.detach(|| check_path(&path, &opts, Rules::shared()))?;
    Ok(report.to_json())
}

#[pymodule]
fn _isitai(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(check_text_json, m)?)?;
    m.add_function(wrap_pyfunction!(check_bytes_json, m)?)?;
    m.add_function(wrap_pyfunction!(check_file_json, m)?)?;
    m.add("DEFAULT_MAX_STREAM_BYTES", isitai::DEFAULT_MAX_STREAM_BYTES)?;
    Ok(())
}
