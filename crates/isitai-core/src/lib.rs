//! IsItAI core: finds proof or signals that a text or file was made by AI.
//!
//! The library never guesses. Absence of signal is reported as `no-signal`,
//! never as "human".

mod png;
mod provenance;
mod rules;
mod text;
mod xmp;

pub use rules::Rules;
use serde::Serialize;
use std::io::{Read, Seek};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum Verdict {
    AiProven,
    CaptureProven,
    AiSignal,
    Inconsistent,
    NoSignal,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Strength {
    Weak,
    Strong,
    Proof,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Layer {
    Provenance,
    Metadata,
    Artifact,
}

/// What a piece of evidence points to.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum Origin {
    Ai,
    Capture,
}

#[derive(Debug, Clone, Serialize)]
#[serde(untagged)]
pub enum Location {
    /// First match in a text. `start` and `end` are **UTF-8 byte offsets**, not
    /// JS/Python string indices; use `text` rather than slicing the input.
    Span {
        start: usize,
        end: usize,
        text: String,
    },
    Field {
        field: String,
    },
}

#[derive(Debug, Clone, Serialize)]
pub struct Evidence {
    pub id: String,
    pub layer: Layer,
    pub strength: Strength,
    pub origin: Origin,
    pub detail: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub location: Option<Location>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Report {
    pub verdict: Verdict,
    /// Sniffed MIME type, or `text/plain` for text input.
    pub media: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub generator: Option<String>,
    pub evidence: Vec<Evidence>,
    /// Non-evidence notes: parse errors, declared/sniffed type mismatch.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub warnings: Vec<String>,
    pub version: Version,
}

impl Report {
    /// The one serializer used by the CLI and every binding (criterion 5).
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("Report is always serializable")
    }
}

/// Checks a file by path, streaming it. Used by the bindings.
pub fn check_path(
    path: &std::path::Path,
    opts: &Options,
    rules: &Rules,
) -> std::io::Result<Report> {
    let file = std::fs::File::open(path)?;
    Ok(check_reader(std::io::BufReader::new(file), opts, rules))
}

#[derive(Debug, Clone, Serialize)]
pub struct Version {
    pub lib: &'static str,
    pub rules: String,
}

#[derive(Debug, Clone, Default)]
pub struct Options {
    /// PEM bundle of trusted C2PA roots. Without it, valid manifests are only `strong`.
    pub trust_anchors_pem: Option<String>,
    /// MIME type claimed by the caller (upload header, extension). Compared with the sniffed one.
    pub declared_mime: Option<String>,
}

/// Checks a text string.
pub fn check_text(input: &str, rules: &Rules) -> Report {
    let evidence = text::scan(input, rules);
    finish("text/plain".into(), None, evidence, Vec::new(), rules)
}

/// Checks raw bytes (file content). Text is detected when no binary format matches.
pub fn check_bytes(bytes: &[u8], opts: &Options, rules: &Rules) -> Report {
    check_reader(std::io::Cursor::new(bytes), opts, rules)
}

/// Bytes sniffed to detect the format.
const SNIFF_LEN: usize = 8192;
/// Largest input still treated as text when no binary format matches.
pub const MAX_TEXT_BYTES: u64 = 16 * 1024 * 1024;

/// Checks a seekable stream (an open file). Memory stays bounded: the file is
/// never loaded whole, except text input up to [`MAX_TEXT_BYTES`].
pub fn check_reader<R: Read + Seek + Send>(mut input: R, opts: &Options, rules: &Rules) -> Report {
    let mut warnings = Vec::new();
    let mut head = Vec::with_capacity(SNIFF_LEN);
    if let Err(e) = (&mut input).take(SNIFF_LEN as u64).read_to_end(&mut head) {
        warnings.push(format!("read: {e}"));
        return finish(
            "application/octet-stream".into(),
            None,
            Vec::new(),
            warnings,
            rules,
        );
    }
    let sniffed = normalize_mime(infer::get(&head).map(|t| t.mime_type()), &head);

    let Some(mime) = sniffed else {
        let mut all = head;
        let read = (&mut input).take(MAX_TEXT_BYTES).read_to_end(&mut all);
        return match (read, String::from_utf8(all)) {
            (Ok(_), Ok(s)) => check_text(&s, rules),
            _ => finish(
                "application/octet-stream".into(),
                None,
                Vec::new(),
                warnings,
                rules,
            ),
        };
    };

    if let Some(declared) = &opts.declared_mime {
        if !declared.eq_ignore_ascii_case(&mime) {
            warnings.push(format!(
                "declared type {declared} differs from content type {mime}"
            ));
        }
    }

    let mut evidence = Vec::new();
    let mut generator = None;

    match provenance::read(&mut input, &mime, opts.trust_anchors_pem.as_deref()) {
        Ok(Some(mut p)) => {
            provenance::classify(&mut p, &rules.dst.ai, &rules.dst.capture);
            generator = p.generator;
            evidence.extend(p.evidence);
            warnings.extend(p.warnings);
        }
        Ok(None) => {}
        Err(e) => warnings.push(format!("c2pa: {e}")),
    }

    match xmp::scan(&mut input, rules) {
        Ok(ev) => evidence.extend(ev),
        Err(e) => warnings.push(format!("xmp: {e}")),
    }

    if mime == "image/png" {
        match png::scan(&mut input, rules) {
            Ok((ev, gen)) => {
                evidence.extend(ev);
                generator = generator.or(gen);
            }
            Err(e) => warnings.push(format!("png: {e}")),
        }
    }

    finish(mime, generator, evidence, warnings, rules)
}

/// Maps `infer` names to the names c2pa-rs expects, and detects SVG, which `infer`
/// reports as `text/xml` (with an XML declaration) or not at all.
fn normalize_mime(sniffed: Option<&str>, head: &[u8]) -> Option<String> {
    let looks_svg = || head.windows(4).any(|w| w == b"<svg");
    let mime = match sniffed {
        Some("text/xml") | None if looks_svg() => "image/svg+xml",
        Some("audio/x-wav") => "audio/wav",
        Some("audio/m4a") => "audio/mp4",
        Some(m) => m,
        None => return None,
    };
    Some(mime.to_string())
}

fn finish(
    media: String,
    generator: Option<String>,
    mut evidence: Vec<Evidence>,
    warnings: Vec<String>,
    rules: &Rules,
) -> Report {
    evidence.sort_by_key(|e| std::cmp::Reverse(e.strength));
    Report {
        verdict: verdict(&evidence),
        media,
        generator,
        evidence,
        warnings,
        version: Version {
            lib: env!("CARGO_PKG_VERSION"),
            rules: rules.version.clone(),
        },
    }
}

/// Spec v0.1 verdict rules, applied in order.
pub fn verdict(evidence: &[Evidence]) -> Verdict {
    let has =
        |o: Origin, min: Strength| evidence.iter().any(|e| e.origin == o && e.strength >= min);
    let ai_any = has(Origin::Ai, Strength::Weak);
    let cap_any = has(Origin::Capture, Strength::Weak);

    if has(Origin::Ai, Strength::Proof) && !cap_any {
        return Verdict::AiProven;
    }
    if has(Origin::Capture, Strength::Proof) && !ai_any {
        return Verdict::CaptureProven;
    }
    if ai_any && cap_any {
        return Verdict::Inconsistent;
    }
    let mut weak_ids: Vec<&str> = evidence
        .iter()
        .filter(|e| e.origin == Origin::Ai && e.strength == Strength::Weak)
        .map(|e| e.id.as_str())
        .collect();
    weak_ids.sort_unstable();
    weak_ids.dedup();
    if has(Origin::Ai, Strength::Strong) || weak_ids.len() >= 2 {
        return Verdict::AiSignal;
    }
    Verdict::NoSignal
}
