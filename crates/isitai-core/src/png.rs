use crate::{Evidence, Layer, Location, Origin, Rules, Strength};
use std::io::{self, Read, Seek, SeekFrom};

const SIGNATURE: &[u8] = b"\x89PNG\r\n\x1a\n";
/// Text chunks larger than this are skipped (a ComfyUI workflow is a few hundred KB).
const MAX_TEXT_CHUNK: u32 = 16 * 1024 * 1024;

/// Walks PNG chunks with seeks, reading only text chunks, and reports the text
/// chunks written by local generators. Each evidence id is reported once per file.
pub fn scan<R: Read + Seek>(
    input: &mut R,
    rules: &Rules,
) -> io::Result<(Vec<Evidence>, Option<String>)> {
    let mut out = Vec::new();
    let mut generator = None;
    input.seek(SeekFrom::Start(0))?;
    let mut sig = [0u8; 8];
    if input.read_exact(&mut sig).is_err() || sig != SIGNATURE {
        return Ok((out, generator));
    }
    let mut header = [0u8; 8];
    while input.read_exact(&mut header).is_ok() {
        let len = u32::from_be_bytes(header[..4].try_into().unwrap());
        let kind: [u8; 4] = header[4..].try_into().unwrap();
        if kind == *b"IEND" {
            break;
        }
        let is_text = matches!(&kind, b"tEXt" | b"iTXt" | b"zTXt");
        if !is_text || len > MAX_TEXT_CHUNK {
            input.seek(SeekFrom::Current(len as i64 + 4))?;
            continue;
        }
        let mut data = vec![0u8; len as usize];
        if input.read_exact(&mut data).is_err() {
            break; // truncated file
        }
        input.seek(SeekFrom::Current(4))?; // CRC

        let Some((key, value)) = text_entry(&kind, &data) else {
            continue;
        };
        let Some((id, detail, name)) = generator_of(&key, &value, rules) else {
            continue;
        };
        if out.iter().any(|e| e.id == id) {
            continue;
        }
        generator.get_or_insert_with(|| name.to_string());
        out.push(Evidence {
            id,
            layer: Layer::Metadata,
            strength: Strength::Strong,
            origin: Origin::Ai,
            detail,
            location: Some(Location::Field {
                field: format!("{}:{key}", String::from_utf8_lossy(&kind)),
            }),
        });
    }
    Ok((out, generator))
}

/// Keyword and value of a tEXt or uncompressed iTXt chunk. `None` for a compressed
/// value (zTXt, compressed iTXt), which is not inflated, and for a malformed chunk.
fn text_entry(kind: &[u8; 4], data: &[u8]) -> Option<(String, String)> {
    let key_end = data.iter().position(|b| *b == 0)?;
    let rest = &data[key_end + 1..];
    let value = match kind {
        b"tEXt" => rest,
        b"iTXt" => {
            // Compression flag, compression method, language tag NUL, translated keyword NUL.
            let (flag, rest) = rest.split_first()?;
            if *flag != 0 {
                return None;
            }
            let mut fields = rest.get(1..)?.splitn(3, |b| *b == 0);
            fields.nth(2)?
        }
        _ => return None,
    };
    Some((
        String::from_utf8_lossy(&data[..key_end]).into_owned(),
        String::from_utf8_lossy(value).into_owned(),
    ))
}

/// Evidence id, detail and generator name when a text chunk was written by a known
/// generator: a keyword alone is not enough, the value must carry the rule's marker.
fn generator_of<'a>(key: &str, value: &str, rules: &'a Rules) -> Option<(String, String, &'a str)> {
    if key == "Software" {
        let s = rules
            .png_software
            .iter()
            .find(|s| value.trim() == s.equals)?;
        return Some((
            "png.software".into(),
            format!("PNG Software is {}", s.generator),
            &s.generator,
        ));
    }
    let k = rules
        .png_keys
        .iter()
        .find(|k| k.key == key && value.contains(&k.marker))?;
    Some((
        format!("png.{}", k.key),
        format!("PNG text chunk `{}` written by {}", k.key, k.generator),
        &k.generator,
    ))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    fn chunk(kind: &[u8; 4], data: &[u8]) -> Vec<u8> {
        let mut c = (data.len() as u32).to_be_bytes().to_vec();
        c.extend_from_slice(kind);
        c.extend_from_slice(data);
        c.extend_from_slice(&[0, 0, 0, 0]); // CRC not checked
        c
    }

    fn png(chunks: &[Vec<u8>]) -> Vec<u8> {
        let mut p = SIGNATURE.to_vec();
        for c in chunks {
            p.extend(c);
        }
        p
    }

    #[test]
    fn a1111_parameters_after_idat() {
        let data = png(&[
            chunk(b"IHDR", &[0; 13]),
            chunk(b"IDAT", &[1; 64]),
            chunk(b"tEXt", b"parameters\0a cat, Steps: 20"),
            chunk(b"IEND", &[]),
        ]);
        let (ev, gen) = scan(&mut Cursor::new(data), &Rules::embedded()).unwrap();
        assert_eq!(ev[0].id, "png.parameters");
        assert_eq!(gen.as_deref(), Some("Stable Diffusion WebUI (A1111/Forge)"));
    }

    #[test]
    fn plain_png_and_truncated_png_are_quiet() {
        let plain = png(&[
            chunk(b"IHDR", &[0; 13]),
            chunk(b"tEXt", b"Comment\0holiday"),
            chunk(b"IEND", &[]),
        ]);
        assert!(scan(&mut Cursor::new(plain), &Rules::embedded())
            .unwrap()
            .0
            .is_empty());
        let mut truncated = png(&[chunk(b"IHDR", &[0; 13])]);
        truncated.extend_from_slice(&[0, 0, 0, 50, b't', b'E', b'X', b't', b'p']);
        assert!(scan(&mut Cursor::new(truncated), &Rules::embedded())
            .unwrap()
            .0
            .is_empty());
    }

    fn text(key: &str, value: &str) -> Vec<u8> {
        chunk(b"tEXt", format!("{key}\0{value}").as_bytes())
    }

    fn itxt(key: &str, compressed: bool, value: &str) -> Vec<u8> {
        let flag = if compressed { '\u{1}' } else { '\0' };
        chunk(b"iTXt", format!("{key}\0{flag}\0\0\0{value}").as_bytes())
    }

    fn ztxt(key: &str, value: &str) -> Vec<u8> {
        chunk(b"zTXt", format!("{key}\0\0{value}").as_bytes())
    }

    /// Evidence ids and generator of a PNG made of these chunks.
    fn found(chunks: &[Vec<u8>]) -> (Vec<String>, Option<String>) {
        let mut all = vec![chunk(b"IHDR", &[0; 13])];
        all.extend_from_slice(chunks);
        all.push(chunk(b"IEND", &[]));
        let (ev, gen) = scan(&mut Cursor::new(png(&all)), &Rules::embedded()).unwrap();
        (ev.into_iter().map(|e| e.id).collect(), gen)
    }

    const COMFY_PROMPT: &str = r#"{"3": {"class_type": "KSampler", "inputs": {"seed": 1}}}"#;
    const COMFY_WORKFLOW: &str = r#"{"last_node_id": 9, "nodes": [{"id": 3}]}"#;

    #[test]
    fn each_key_needs_its_marker() {
        let cases = [
            (
                "parameters",
                "a fox\nSteps: 20, Sampler: Euler a",
                "ISO 100, f/2.8, 1/250 s",
            ),
            (
                "prompt",
                COMFY_PROMPT,
                "Daily photo challenge: 'something blue'",
            ),
            ("workflow", COMFY_WORKFLOW, "RAW > Lightroom > export sRGB"),
            ("invokeai_metadata", r#"{"app_version": "4.2.0"}"#, "none"),
        ];
        for (key, generated, human) in cases {
            let id = format!("png.{key}");
            assert_eq!(found(&[text(key, generated)]).0, [id.as_str()]);
            assert_eq!(found(&[itxt(key, false, generated)]).0, [id.as_str()]);
            // The key alone, with another content or none, is not evidence.
            assert_eq!(found(&[text(key, human)]), (vec![], None), "{key}");
            assert_eq!(found(&[text(key, "")]), (vec![], None), "{key}");
            assert_eq!(found(&[itxt(key, false, human)]), (vec![], None), "{key}");
        }
    }

    #[test]
    fn generator_comes_from_the_matching_chunk_only() {
        let (ids, gen) = found(&[text("parameters", "ISO 100"), text("prompt", COMFY_PROMPT)]);
        assert_eq!(ids, ["png.prompt"]);
        assert_eq!(gen.as_deref(), Some("ComfyUI"));
    }

    #[test]
    fn software_must_equal_novelai() {
        let novelai = (
            vec!["png.software".to_string()],
            Some("NovelAI".to_string()),
        );
        assert_eq!(found(&[text("Software", "NovelAI")]), novelai);
        assert_eq!(found(&[text("Software", " NovelAI\n")]), novelai);
        assert_eq!(found(&[itxt("Software", false, "NovelAI")]), novelai);
        for value in [
            "viewer 1.0 (not NovelAI)",
            "NovelAI Diffusion",
            "novelai",
            "GIMP 2.10",
            "",
        ] {
            assert_eq!(found(&[text("Software", value)]), (vec![], None), "{value}");
            assert_eq!(
                found(&[itxt("Software", false, value)]),
                (vec![], None),
                "{value}"
            );
        }
    }

    #[test]
    fn itxt_location_names_the_chunk_type() {
        let data = png(&[itxt("Software", false, "NovelAI"), chunk(b"IEND", &[])]);
        let (ev, _) = scan(&mut Cursor::new(data), &Rules::embedded()).unwrap();
        assert!(
            matches!(&ev[0].location, Some(Location::Field { field }) if field == "iTXt:Software")
        );
    }

    #[test]
    fn compressed_values_are_skipped() {
        // Not inflated: even a value that would match in clear is not read.
        assert_eq!(found(&[ztxt("parameters", "Steps: 20")]), (vec![], None));
        assert_eq!(found(&[ztxt("Software", "NovelAI")]), (vec![], None));
        assert_eq!(
            found(&[itxt("parameters", true, "Steps: 20")]),
            (vec![], None)
        );
        assert_eq!(found(&[itxt("Software", true, "NovelAI")]), (vec![], None));
    }

    #[test]
    fn malformed_text_chunks_are_quiet() {
        let chunks = [
            chunk(b"tEXt", b"parameters"),     // no NUL after the keyword
            chunk(b"iTXt", b"parameters\0"),   // nothing after the keyword
            chunk(b"iTXt", b"parameters\0\0"), // no compression method
            chunk(b"iTXt", b"parameters\0\0\0Steps: 20"), // no language / translated keyword end
            chunk(b"iTXt", b""),
        ];
        assert_eq!(found(&chunks), (vec![], None));
    }

    #[test]
    fn each_evidence_id_is_reported_once() {
        let mut chunks = vec![text("parameters", "Steps: 20"); 500];
        chunks.push(text("prompt", COMFY_PROMPT));
        chunks.push(text("prompt", COMFY_PROMPT));
        let (ids, gen) = found(&chunks);
        assert_eq!(ids, ["png.parameters", "png.prompt"]);
        assert_eq!(gen.as_deref(), Some("Stable Diffusion WebUI (A1111/Forge)"));
    }
}
