use crate::{Evidence, Layer, Location, Origin, Rules, Strength};
use std::io::{self, Read, Seek, SeekFrom};

const SIGNATURE: &[u8] = b"\x89PNG\r\n\x1a\n";
/// Text chunks larger than this are skipped (a ComfyUI workflow is a few hundred KB).
const MAX_TEXT_CHUNK: u32 = 16 * 1024 * 1024;

/// Walks PNG chunks with seeks, reading only text chunks, and reports keywords
/// written by local generators.
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

        let key_end = data.iter().position(|b| *b == 0).unwrap_or(data.len());
        let key = String::from_utf8_lossy(&data[..key_end]);
        if let Some(k) = rules.png_keys.iter().find(|k| k.key == key) {
            generator.get_or_insert_with(|| k.generator.clone());
            out.push(Evidence {
                id: format!("png.{}", k.key),
                layer: Layer::Metadata,
                strength: Strength::Strong,
                origin: Origin::Ai,
                detail: format!("PNG text chunk `{}` written by {}", k.key, k.generator),
                location: Some(Location::Field {
                    field: format!("{}:{}", String::from_utf8_lossy(&kind), k.key),
                }),
            });
        }
        if key == "Software" && &kind == b"tEXt" {
            let value = String::from_utf8_lossy(data.get(key_end + 1..).unwrap_or_default());
            if let Some(s) = rules
                .png_software
                .iter()
                .find(|s| value.contains(&s.contains))
            {
                generator.get_or_insert_with(|| s.generator.clone());
                out.push(Evidence {
                    id: "png.software".into(),
                    layer: Layer::Metadata,
                    strength: Strength::Strong,
                    origin: Origin::Ai,
                    detail: format!("PNG Software is {}", s.generator),
                    location: Some(Location::Field {
                        field: "tEXt:Software".into(),
                    }),
                });
            }
        }
    }
    Ok((out, generator))
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
}
