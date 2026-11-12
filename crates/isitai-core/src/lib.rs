//! IsItAI core: finds proof or signals that a text or file was made by AI.
//!
//! The library never guesses. Absence of signal is reported as `no-signal`,
//! never as "human".

mod png;
mod provenance;
mod rules;
mod text;
mod xmp;

pub use provenance::validate_trust_anchors;
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
    /// Actions of the active C2PA manifest, in the order the manifest lists them.
    /// It is what the manifest declares, whatever its validation state: it adds no
    /// evidence and does not change the verdict.
    #[serde(skip_serializing_if = "Vec::is_empty")]
    pub history: Vec<HistoryEntry>,
    /// What `history` establishes about edits after creation; absent when it establishes nothing.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub history_summary: Option<HistorySummary>,
    pub version: Version,
}

/// One action of the active C2PA manifest.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct HistoryEntry {
    /// C2PA action name, e.g. `c2pa.created`, `c2pa.opened`, `c2pa.edited`.
    pub action: String,
    /// Short `digitalSourceType` declared by the action or, failing that, by the
    /// manifest of the ingredient the action refers to. An inherited value is the
    /// type of the ingredient's first action only (`c2pa.created` or `c2pa.opened`):
    /// later actions of the ingredient are not read.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub digital_source_type: Option<String>,
    /// `softwareAgent` of the action.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub software: Option<String>,
}

/// Summary of a C2PA history. Only positive claims: there is no "edited without AI"
/// value, because a manifest cannot establish that no AI step happened.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "kebab-case")]
pub enum HistorySummary {
    /// Declared AI-made when created or opened, then modified by a later action.
    AiThenEdited,
    /// Declared a camera capture when created or opened, then a later action declares an AI source.
    CaptureThenAiEdited,
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

/// How much work a file check does. Text input ignores it.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Effort {
    /// Skips the XMP scan of the whole file. C2PA validation may still read a signed
    /// file whole. `Fast` can miss unsigned metadata (IPTC `DigitalSourceType`),
    /// including a contradiction that `Standard` would report.
    Fast,
    /// Every layer, including the XMP scan of the whole file.
    #[default]
    Standard,
}

impl std::str::FromStr for Effort {
    type Err = String;

    /// The one parser used by the CLI and every binding.
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s {
            "fast" => Ok(Self::Fast),
            "standard" => Ok(Self::Standard),
            _ => Err(format!("unknown effort `{s}` (expected fast or standard)")),
        }
    }
}

#[derive(Debug, Clone, Default)]
pub struct Options {
    /// PEM bundle of trusted C2PA roots. It **replaces** the default, which is the
    /// official C2PA trust list embedded in this crate (`trust/SOURCE.md`). A valid
    /// manifest whose signer does not chain to the roots in use is only `strong`.
    /// Check it once with [`validate_trust_anchors`]: the check functions never fail,
    /// so an unusable bundle only shows as a `c2pa:` warning in each report.
    pub trust_anchors_pem: Option<String>,
    /// MIME type claimed by the caller (upload header, extension). Compared with the sniffed one.
    pub declared_mime: Option<String>,
    pub effort: Effort,
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
/// Text is analysed up to this many bytes after the sniffed head; the rest is ignored.
pub const MAX_TEXT_BYTES: u64 = 16 * 1024 * 1024;

/// Checks a seekable stream (an open file). Memory stays bounded: the file is
/// never loaded whole, except text content up to [`MAX_TEXT_BYTES`].
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
        let (text, warning) = read_text(&mut input);
        warnings.extend(warning);
        let (media, evidence) = match &text {
            Some(t) => ("text/plain", text::scan(t, rules)),
            None => ("application/octet-stream", Vec::new()),
        };
        return finish(media.into(), None, evidence, warnings, rules);
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
    let mut history = Vec::new();
    let mut history_summary = None;

    match provenance::read(
        &mut input,
        &mime,
        opts.trust_anchors_pem.as_deref(),
        &rules.dst,
    ) {
        Ok(Some(p)) => {
            generator = p.generator;
            evidence.extend(p.evidence);
            warnings.extend(p.warnings);
            history = p.history;
            history_summary = p.history_summary;
        }
        Ok(None) => {}
        Err(e) => warnings.push(format!("c2pa: {e}")),
    }

    if opts.effort != Effort::Fast {
        match xmp::scan(&mut input, rules) {
            Ok(ev) => evidence.extend(ev),
            Err(e) => warnings.push(format!("xmp: {e}")),
        }
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

    if is_text_like(&mime) {
        let (text, warning) = read_text(&mut input);
        warnings.extend(warning);
        if let Some(t) = text {
            evidence.extend(text::scan(&t, rules));
        }
    }

    let mut report = finish(mime, generator, evidence, warnings, rules);
    report.history = history;
    report.history_summary = history_summary;
    report
}

/// Sniffed types whose content is also read as text: what `infer` reports as
/// `text/*` (HTML, XML, shell script), and SVG.
fn is_text_like(mime: &str) -> bool {
    mime.starts_with("text/") || mime == "image/svg+xml"
}

/// Reads the stream from its start as UTF-8 text, up to `SNIFF_LEN + MAX_TEXT_BYTES`.
/// Returns the text that can be analysed, and a warning when the text was not
/// analysed, or not fully.
fn read_text<R: Read + Seek>(input: &mut R) -> (Option<String>, Option<String>) {
    let limit = SNIFF_LEN as u64 + MAX_TEXT_BYTES;
    let mut bytes = Vec::new();
    let read = input
        .seek(std::io::SeekFrom::Start(0))
        .and_then(|_| input.take(limit + 1).read_to_end(&mut bytes));
    if let Err(e) = read {
        return (None, Some(format!("text not analysed: read: {e}")));
    }
    let truncated = bytes.len() as u64 > limit;
    bytes.truncate(limit as usize);
    let text = match String::from_utf8(bytes) {
        Ok(text) => text,
        // The size limit can cut the last character in two: keep what precedes it.
        Err(e) if truncated && e.utf8_error().error_len().is_none() => {
            let valid = e.utf8_error().valid_up_to();
            let mut bytes = e.into_bytes();
            bytes.truncate(valid);
            String::from_utf8(bytes).expect("valid up to this length")
        }
        Err(_) => {
            return (
                None,
                Some("text not analysed: the content is not UTF-8".into()),
            )
        }
    };
    let warning = truncated.then(|| {
        format!("text not fully analysed: only the first {limit} bytes were read as text")
    });
    (Some(text), warning)
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
        history: Vec::new(),
        history_summary: None,
        version: Version {
            lib: env!("CARGO_PKG_VERSION"),
            rules: rules.version.clone(),
        },
    }
}

/// Spec v0.1 verdict rules, applied in order. A proof is not cancelled by weaker
/// contrary evidence, except that a capture is never claimed when there is any AI hint.
pub fn verdict(evidence: &[Evidence]) -> Verdict {
    let has =
        |o: Origin, min: Strength| evidence.iter().any(|e| e.origin == o && e.strength >= min);
    let ai_any = has(Origin::Ai, Strength::Weak);
    let cap_any = has(Origin::Capture, Strength::Weak);
    let cap_proof = has(Origin::Capture, Strength::Proof);

    if has(Origin::Ai, Strength::Proof) && !cap_proof {
        return Verdict::AiProven;
    }
    if cap_proof && !ai_any {
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

#[cfg(test)]
mod tests {
    use super::*;

    fn ev(origin: Origin, strength: Strength, id: &str) -> Evidence {
        Evidence {
            id: id.into(),
            layer: Layer::Metadata,
            strength,
            origin,
            detail: String::new(),
            location: None,
        }
    }

    #[test]
    fn verdict_rules() {
        use Origin::{Ai, Capture};
        use Strength::{Proof, Strong, Weak};
        use Verdict::*;
        let v = |list: &[(Origin, Strength, &str)]| {
            let evidence: Vec<_> = list.iter().map(|(o, s, id)| ev(*o, *s, id)).collect();
            verdict(&evidence)
        };
        // An AI proof stands against weaker capture evidence.
        assert_eq!(v(&[(Ai, Proof, "a")]), AiProven);
        assert_eq!(v(&[(Ai, Proof, "a"), (Capture, Weak, "c")]), AiProven);
        assert_eq!(v(&[(Ai, Proof, "a"), (Capture, Strong, "c")]), AiProven);
        // Two proofs contradict each other.
        assert_eq!(v(&[(Ai, Proof, "a"), (Capture, Proof, "c")]), Inconsistent);
        // A capture is claimed only without any AI hint.
        assert_eq!(v(&[(Capture, Proof, "c")]), CaptureProven);
        assert_eq!(
            v(&[(Capture, Proof, "c"), (Capture, Weak, "d")]),
            CaptureProven
        );
        assert_eq!(v(&[(Capture, Proof, "c"), (Ai, Weak, "a")]), Inconsistent);
        assert_eq!(v(&[(Capture, Proof, "c"), (Ai, Strong, "a")]), Inconsistent);
        // No proof: both sides present contradict each other.
        assert_eq!(v(&[(Ai, Strong, "a"), (Capture, Weak, "c")]), Inconsistent);
        assert_eq!(v(&[(Ai, Weak, "a"), (Capture, Strong, "c")]), Inconsistent);
        // One strong, or two distinct weak.
        assert_eq!(v(&[(Ai, Strong, "a")]), AiSignal);
        assert_eq!(v(&[(Ai, Weak, "a"), (Ai, Weak, "b")]), AiSignal);
        assert_eq!(v(&[(Ai, Weak, "a"), (Ai, Weak, "a")]), NoSignal);
        assert_eq!(v(&[(Ai, Weak, "a")]), NoSignal);
        // Capture evidence below proof claims nothing.
        assert_eq!(v(&[(Capture, Strong, "c")]), NoSignal);
        assert_eq!(v(&[]), NoSignal);
    }

    #[test]
    fn effort_parses_known_names_only() {
        assert_eq!("fast".parse(), Ok(Effort::Fast));
        assert_eq!("standard".parse(), Ok(Effort::Standard));
        assert!("thorough".parse::<Effort>().is_err());
        assert!("Fast".parse::<Effort>().is_err());
        assert!("".parse::<Effort>().is_err());
    }

    const XMP_AI: &str = r#"<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:Description Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/></x:xmpmeta>"#;
    const ARTIFACT: &str = "Paris :contentReference[oaicite:0]{index=0}.";

    fn check(bytes: &[u8], effort: Effort) -> Report {
        let opts = Options {
            effort,
            ..Options::default()
        };
        check_bytes(bytes, &opts, &Rules::embedded())
    }

    #[test]
    fn fast_skips_the_xmp_scan() {
        let mut jpeg = vec![0xFF, 0xD8, 0xFF, 0xE0];
        jpeg.extend_from_slice(XMP_AI.as_bytes());
        assert_eq!(check(&jpeg, Effort::Fast).verdict, Verdict::NoSignal);
        assert_eq!(check(&jpeg, Effort::Standard).verdict, Verdict::AiSignal);
    }

    #[test]
    fn text_rules_run_inside_text_like_files() {
        let cases = [
            (
                format!("<!DOCTYPE html>\n<html><body><p>{ARTIFACT}</p></body></html>"),
                "text/html",
            ),
            (format!("<p>{ARTIFACT}</p>\n"), "text/html"),
            (
                format!("<?xml version=\"1.0\"?>\n<note>{ARTIFACT}</note>"),
                "text/xml",
            ),
            (
                format!("#!/bin/sh\n# {ARTIFACT}\necho ok\n"),
                "text/x-shellscript",
            ),
            (
                format!("Use `<svg width=\"16\">`.\n\n{ARTIFACT}"),
                "image/svg+xml",
            ),
        ];
        for (content, media) in cases {
            for effort in [Effort::Fast, Effort::Standard] {
                let report = check(content.as_bytes(), effort);
                assert_eq!(report.media, media);
                assert_eq!(report.verdict, Verdict::AiSignal, "{media}");
                assert_eq!(report.evidence[0].id, "text.oaicite");
                assert_eq!(report.evidence[0].layer, Layer::Artifact);
            }
        }
        let human = check(
            b"<!DOCTYPE html>\n<html><body><h1>Bienvenue</h1></body></html>",
            Effort::Standard,
        );
        assert_eq!(human.verdict, Verdict::NoSignal);
        assert!(!warns(&human, "text not"));
    }

    #[test]
    fn text_rules_add_to_the_other_layers() {
        // An HTML page with an XMP packet and a pasted artifact: both layers report.
        let page = format!("<!DOCTYPE html>\n<p>{ARTIFACT}</p>{XMP_AI}");
        let ids = |effort| -> Vec<String> {
            let report = check(page.as_bytes(), effort);
            report.evidence.into_iter().map(|e| e.id).collect()
        };
        assert_eq!(
            ids(Effort::Standard),
            ["xmp.dst.trainedAlgorithmicMedia", "text.oaicite"]
        );
        assert_eq!(ids(Effort::Fast), ["text.oaicite"]);
    }

    fn warns(report: &Report, prefix: &str) -> bool {
        report.warnings.iter().any(|w| w.starts_with(prefix))
    }

    #[test]
    fn text_that_is_not_utf8_gives_a_warning() {
        // Latin-1 text, no format sniffed.
        let latin1 = check(
            b"Tr\xE8s bien :contentReference[oaicite:0]{index=0}.",
            Effort::Standard,
        );
        assert_eq!(latin1.verdict, Verdict::NoSignal);
        assert_eq!(latin1.media, "application/octet-stream");
        assert!(warns(&latin1, "text not analysed"));
        // Latin-1 HTML: sniffed as text-like.
        let html = check(
            b"<p>Tr\xE8s bien :contentReference[oaicite:0]{index=0}.</p>",
            Effort::Standard,
        );
        assert_eq!(html.media, "text/html");
        assert_eq!(html.verdict, Verdict::NoSignal);
        assert!(warns(&html, "text not analysed"));
        // Plain UTF-8 text: no warning.
        let utf8 = check("Très bien.".as_bytes(), Effort::Standard);
        assert_eq!(utf8.media, "text/plain");
        assert!(utf8.warnings.is_empty());
    }

    #[test]
    fn text_beyond_the_limit_gives_a_warning() {
        let limit = SNIFF_LEN + MAX_TEXT_BYTES as usize;

        // The artifact ends exactly at the limit: analysed, no warning.
        let mut inside = vec![b'x'; limit - ARTIFACT.len()];
        inside.extend_from_slice(ARTIFACT.as_bytes());
        let report = check(&inside, Effort::Standard);
        assert_eq!(report.verdict, Verdict::AiSignal);
        assert!(report.warnings.is_empty());

        // The artifact sits after the limit, and a 2-byte character straddles the cut.
        let mut beyond = vec![b'x'; limit - 1];
        beyond.extend_from_slice("é".as_bytes());
        beyond.extend_from_slice(ARTIFACT.as_bytes());
        let report = check(&beyond, Effort::Standard);
        assert_eq!(report.media, "text/plain");
        assert_eq!(report.verdict, Verdict::NoSignal);
        assert!(warns(&report, "text not fully analysed"));

        // Same in a text-like file.
        beyond[..3].copy_from_slice(b"<p>");
        let report = check(&beyond, Effort::Standard);
        assert_eq!(report.media, "text/html");
        assert_eq!(report.verdict, Verdict::NoSignal);
        assert!(warns(&report, "text not fully analysed"));
    }
}
