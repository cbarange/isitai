use crate::{Origin, Strength};
use regex::Regex;
use serde::Deserialize;

const TEXT_TOML: &str = include_str!("../rules/text.toml");
const METADATA_TOML: &str = include_str!("../rules/metadata.toml");

#[derive(Deserialize)]
struct TextFile {
    rule: Vec<RawTextRule>,
}

#[derive(Deserialize)]
struct RawTextRule {
    id: String,
    strength: String,
    detail: String,
    pattern: String,
}

#[derive(Deserialize)]
struct MetadataFile {
    digital_source_type: Dst,
    png_key: Vec<PngKey>,
    png_software: Vec<PngSoftware>,
}

#[derive(Deserialize, Clone)]
pub struct Dst {
    pub ai: Vec<String>,
    pub capture: Vec<String>,
}

impl Dst {
    /// Origin a DigitalSourceType value points to; `None` for neutral values (e.g. `digitalArt`).
    pub fn origin(&self, value: &str) -> Option<Origin> {
        if self.ai.iter().any(|v| v == value) {
            Some(Origin::Ai)
        } else if self.capture.iter().any(|v| v == value) {
            Some(Origin::Capture)
        } else {
            None
        }
    }
}

#[derive(Deserialize, Clone)]
pub struct PngKey {
    pub key: String,
    pub generator: String,
}

#[derive(Deserialize, Clone)]
pub struct PngSoftware {
    pub contains: String,
    pub generator: String,
}

pub struct TextRule {
    pub id: String,
    pub strength: Strength,
    pub detail: String,
    pub regex: Regex,
}

/// Compiled rule set. Build once and reuse: compiling regexes is the expensive part.
pub struct Rules {
    pub version: String,
    pub text: Vec<TextRule>,
    pub dst: Dst,
    pub png_keys: Vec<PngKey>,
    pub png_software: Vec<PngSoftware>,
}

impl Rules {
    /// Process-wide embedded rules, compiled once on first use. Bindings use this.
    pub fn shared() -> &'static Self {
        static RULES: std::sync::OnceLock<Rules> = std::sync::OnceLock::new();
        RULES.get_or_init(Self::embedded)
    }

    /// Rules embedded at build time from `rules/*.toml`.
    pub fn embedded() -> Self {
        Self::from_toml(TEXT_TOML, METADATA_TOML).expect("embedded rules are valid")
    }

    pub fn from_toml(text_toml: &str, metadata_toml: &str) -> Result<Self, String> {
        let t: TextFile = toml::from_str(text_toml).map_err(|e| e.to_string())?;
        let m: MetadataFile = toml::from_str(metadata_toml).map_err(|e| e.to_string())?;
        let text = t
            .rule
            .into_iter()
            .map(|r| {
                let strength = match r.strength.as_str() {
                    "strong" => Strength::Strong,
                    "weak" => Strength::Weak,
                    s => return Err(format!("{}: unknown strength {s}", r.id)),
                };
                let regex = Regex::new(&r.pattern).map_err(|e| format!("{}: {e}", r.id))?;
                Ok(TextRule {
                    id: r.id,
                    strength,
                    detail: r.detail,
                    regex,
                })
            })
            .collect::<Result<Vec<_>, String>>()?;
        Ok(Rules {
            version: format!(
                "{:016x}",
                fnv1a(text_toml.as_bytes()) ^ fnv1a(metadata_toml.as_bytes())
            ),
            text,
            dst: m.digital_source_type,
            png_keys: m.png_key,
            png_software: m.png_software,
        })
    }
}

fn fnv1a(bytes: &[u8]) -> u64 {
    bytes.iter().fold(0xcbf29ce484222325, |h, b| {
        (h ^ *b as u64).wrapping_mul(0x100000001b3)
    })
}
