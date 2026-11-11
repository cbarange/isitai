use crate::{Evidence, Layer, Location, Origin, Strength};
use c2pa::{Context, Reader, ValidationState};
use serde_json::{json, Value};
use std::io::{Read, Seek};

pub struct Provenance {
    pub evidence: Vec<Evidence>,
    pub generator: Option<String>,
    pub warnings: Vec<String>,
}

/// Reads the C2PA manifest store. Never touches the network.
/// Returns Ok(None) when the file carries no manifest.
pub fn read<R: Read + Seek + Send>(
    input: &mut R,
    mime: &str,
    anchors_pem: Option<&str>,
) -> Result<Option<Provenance>, String> {
    let mut settings = json!({
        "verify": { "remote_manifest_fetch": false, "ocsp_fetch": false, "verify_trust": true }
    });
    if let Some(pem) = anchors_pem {
        settings["trust"] = json!({ "trust_anchors": pem });
    }
    let ctx = Context::new().with_settings(settings.to_string().as_str()).map_err(|e| e.to_string())?;

    let reader = match Reader::from_context(ctx).with_stream(mime, &mut *input) {
        Ok(r) => r,
        Err(c2pa::Error::JumbfNotFound | c2pa::Error::ProvenanceMissing) => return Ok(None),
        // Must stay visible: a MIME name c2pa does not know looks exactly like "no manifest".
        Err(c2pa::Error::UnsupportedType) => return Err(format!("unsupported type for C2PA: {mime}")),
        Err(e) => return Err(e.to_string()),
    };

    let state = reader.validation_state();
    let strength = match state {
        ValidationState::Trusted => Strength::Proof,
        ValidationState::Valid => Strength::Strong,
        ValidationState::Invalid => Strength::Weak,
    };
    let state_name = format!("{state:?}").to_lowercase();

    let store: Value = serde_json::from_str(&reader.json()).map_err(|e| e.to_string())?;
    let Some(label) = store.get("active_manifest").and_then(Value::as_str) else {
        return Ok(None);
    };
    let manifest = &store["manifests"][label];

    let generator = manifest["claim_generator_info"]
        .as_array()
        .and_then(|a| a.first())
        .and_then(|g| g["name"].as_str())
        .or_else(|| manifest["claim_generator"].as_str())
        .map(str::to_string);

    let mut out = Provenance { evidence: Vec::new(), generator, warnings: Vec::new() };
    if state == ValidationState::Valid {
        out.warnings.push("C2PA manifest is valid but its signer is not in the trust list".into());
    }

    let mut seen = Vec::new();
    for assertion in manifest["assertions"].as_array().into_iter().flatten() {
        let is_actions = assertion["label"].as_str().is_some_and(|l| l.starts_with("c2pa.actions"));
        if !is_actions {
            continue;
        }
        for action in assertion["data"]["actions"].as_array().into_iter().flatten() {
            let Some(dst) = action["digitalSourceType"].as_str() else { continue };
            let value = dst.rsplit('/').next().unwrap_or(dst).to_string();
            if seen.contains(&value) {
                continue;
            }
            seen.push(value.clone());
            out.evidence.push(Evidence {
                id: format!("c2pa.dst.{value}"),
                layer: Layer::Provenance,
                strength,
                origin: Origin::Ai, // fixed below
                detail: format!(
                    "C2PA {} action declares digitalSourceType {value} (manifest {state_name})",
                    action["action"].as_str().unwrap_or("?")
                ),
                location: Some(Location::Field { field: format!("{label}/{}", assertion["label"].as_str().unwrap_or("")) }),
            });
        }
    }
    Ok(Some(out))
}

/// Maps DST values to an origin, dropping neutral ones (e.g. `digitalArt`).
pub fn classify(p: &mut Provenance, ai: &[String], capture: &[String]) {
    p.evidence.retain_mut(|e| {
        let value = e.id.trim_start_matches("c2pa.dst.");
        if ai.iter().any(|v| v == value) {
            e.origin = Origin::Ai;
            true
        } else if capture.iter().any(|v| v == value) {
            e.origin = Origin::Capture;
            true
        } else {
            false
        }
    });
}
