use crate::{Evidence, Layer, Location, Origin, Rules, Strength};
use regex::bytes::Regex;
use std::io::{self, Read, Seek, SeekFrom};
use std::sync::OnceLock;

/// Bytes read per step.
const CHUNK: usize = 4 * 1024 * 1024;
/// Tail kept between steps. An XMP packet larger than this that straddles a
/// chunk boundary is missed; real packets are a few KB.
const OVERLAP: usize = 256 * 1024;

fn packet_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"(?s)<x:xmpmeta\b.*?</x:xmpmeta>").unwrap())
}

fn dst_re() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"cv\.iptc\.org/newscodes/digitalsourcetype/([A-Za-z]+)").unwrap())
}

/// Reads IPTC DigitalSourceType from XMP packets found anywhere in the file.
/// Format-agnostic: JPEG APP1, PNG iTXt, WebP XMP, MP4 uuid box, uncompressed PDF metadata.
/// Only XMP packets are read, so values inside a C2PA manifest are not counted twice.
/// Memory stays bounded to CHUNK + OVERLAP.
pub fn scan<R: Read + Seek>(input: &mut R, rules: &Rules) -> io::Result<Vec<Evidence>> {
    input.seek(SeekFrom::Start(0))?;
    let mut out: Vec<Evidence> = Vec::new();
    let mut buf: Vec<u8> = Vec::with_capacity(CHUNK + OVERLAP);
    loop {
        let kept = buf.len();
        let read = input.by_ref().take(CHUNK as u64).read_to_end(&mut buf)?;
        scan_window(&buf, rules, &mut out);
        if read == 0 || buf.len() - kept < CHUNK {
            break;
        }
        let drop = buf.len().saturating_sub(OVERLAP);
        buf.drain(..drop);
    }
    Ok(out)
}

fn scan_window(window: &[u8], rules: &Rules, out: &mut Vec<Evidence>) {
    for packet in packet_re().find_iter(window) {
        for cap in dst_re().captures_iter(packet.as_bytes()) {
            let value = String::from_utf8_lossy(&cap[1]).into_owned();
            let Some(origin) = rules.dst.origin(&value) else {
                continue;
            };
            // Unsigned metadata: an AI claim is a strong hint, a capture claim only a weak one.
            let strength = match origin {
                Origin::Ai => Strength::Strong,
                Origin::Capture => Strength::Weak,
            };
            let id = format!("xmp.dst.{value}");
            if out.iter().any(|e| e.id == id) {
                continue;
            }
            out.push(Evidence {
                id,
                layer: Layer::Metadata,
                strength,
                origin,
                detail: format!("unsigned XMP DigitalSourceType = {value}"),
                location: Some(Location::Field {
                    field: "Iptc4xmpExt:DigitalSourceType".into(),
                }),
            });
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Cursor;

    const PACKET: &str = r#"<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:Description Iptc4xmpExt:DigitalSourceType="http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/></x:xmpmeta>"#;

    #[test]
    fn finds_packet_across_chunk_boundary() {
        let mut data = vec![b'.'; CHUNK - 20];
        data.extend_from_slice(PACKET.as_bytes());
        data.extend(vec![b'.'; 1000]);
        let ev = scan(&mut Cursor::new(data), &Rules::embedded()).unwrap();
        assert_eq!(ev.len(), 1);
        assert_eq!(ev[0].id, "xmp.dst.trainedAlgorithmicMedia");
    }

    #[test]
    fn ignores_uri_outside_xmp_packet() {
        let data = b"cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia".to_vec();
        assert!(scan(&mut Cursor::new(data), &Rules::embedded())
            .unwrap()
            .is_empty());
    }
}
