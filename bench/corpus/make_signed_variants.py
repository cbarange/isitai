"""Variants of the signed corpus for QA: tampered, transplanted and mixed-evidence files.

Complements `make_signed.py` (not modified). Signs with the c2pa-rs TEST certificate only.

Usage: python -I make_signed_variants.py <c2pa-rs fixtures dir> <certs dir> <signed dir from make_signed.py> <out dir>
Needs: pip install c2pa-python==0.38.0. No network.

Expected verdicts (`expected.json`) assume the c2pa-rs test root bundle is given as trust anchors.
Labels follow docs/SPEC-v0.1.md and are not adjusted to the tool's answers.

Labels changed after the 2026-11-12 QA report, because a design decision changed the
correct answer:
- `v_signed_algorithmicMedia.jpg`: ai-proven -> no-signal. `algorithmicMedia` left the AI
  list of the spec (IPTC: made by an algorithm without training data).
- `v_signed_capture_then_ai_edit.jpg`: inconsistent -> ai-proven. A capture followed by a
  generative edit is AI-edited content, not a contradiction.
"""
import json
import os
import struct
import sys

import c2pa

fixtures, certs, signed, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
EXPECTED = {}
DST = "http://cv.iptc.org/newscodes/digitalsourcetype/"


def read(path):
    with open(path, "rb") as f:
        return f.read()


def add(name, data, verdict, human, note):
    with open(os.path.join(out, name), "wb") as f:
        f.write(data)
    EXPECTED[name] = {"verdict": verdict, "category": "signed-variant", "human": human, "note": note}


def xmp(value):
    return (f"<x:xmpmeta xmlns:x=\"adobe:ns:meta/\"><rdf:RDF xmlns:rdf=\"http://www.w3.org/1999/02/22-rdf-syntax-ns#\">"
            f"<rdf:Description rdf:about=\"\" xmlns:Iptc4xmpExt=\"http://iptc.org/std/Iptc4xmpExt/2008-02-29/\" "
            f"Iptc4xmpExt:DigitalSourceType=\"{DST}{value}\"/></rdf:RDF></x:xmpmeta>").encode()


def jpeg_with_xmp(data, value):
    packet = b"http://ns.adobe.com/xap/1.0/\0" + xmp(value)
    return data[:2] + b"\xff\xe1" + struct.pack(">H", len(packet) + 2) + packet + data[2:]


def jpeg_segments(data):
    """Yields (marker, start, end) for the header segments of a JPEG, up to SOS."""
    i = 2
    while i + 4 <= len(data) and data[i] == 0xFF:
        marker = data[i + 1]
        n = struct.unpack(">H", data[i + 2:i + 4])[0]
        yield marker, i, i + 2 + n
        if marker == 0xDA:
            return
        i += 2 + n


with open(os.path.join(certs, "es256.pub"), "rb") as f:
    cert = f.read()
with open(os.path.join(certs, "es256.pem"), "rb") as f:
    key = f.read()
info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.ES256, cert, key, None)


def sign(src_path, name, actions, verdict, human, note):
    manifest = {
        "claim_generator_info": [{"name": "isitai-test-corpus", "version": "0.1"}],
        "title": name,
        "assertions": [{"label": "c2pa.actions", "data": {"actions": actions}}],
    }
    dest = os.path.join(out, name)
    if os.path.exists(dest):
        os.remove(dest)
    try:
        signer = c2pa.Signer.from_info(info)
        with c2pa.Builder(manifest) as builder:
            builder.sign_file(src_path, dest, signer)
        EXPECTED[name] = {"verdict": verdict, "category": "signed-variant", "human": human, "note": note}
        print(f"signed  {name}")
    except Exception as e:  # noqa: BLE001
        if os.path.exists(dest):
            os.remove(dest)
        print(f"FAILED  {name}: {type(e).__name__}: {str(e)[:120]}")


def created(value):
    return {"action": "c2pa.created", "digitalSourceType": DST + value}


src = os.path.join(fixtures, "no_manifest.jpg")
tmp = os.path.join(out, "_src.jpg")

# 1. Signed manifests with other source types.
sign(src, "v_signed_digitalArt.jpg", [created("digitalArt")], "no-signal", True, "trusted manifest, neutral source type")
sign(src, "v_signed_algorithmicMedia.jpg", [created("algorithmicMedia")], "no-signal", False,
     "algorithmicMedia is not an AI source type: IPTC defines it as made by an algorithm without training data")
sign(src, "v_signed_composite_ai.jpg", [created("compositeWithTrainedAlgorithmicMedia")], "ai-proven", False, "")
sign(src, "v_signed_computationalCapture.jpg", [created("computationalCapture")], "capture-proven", True, "")
sign(src, "v_signed_capture_then_ai_edit.jpg",
     [created("digitalCapture"), {"action": "c2pa.edited", "digitalSourceType": DST + "compositeWithTrainedAlgorithmicMedia"}],
     "ai-proven", False, "signed capture, then a signed generative edit: AI-edited content, not a contradiction")

# 2. Signed proof plus unsigned XMP saying the opposite (XMP added before signing, so the manifest stays valid).
with open(tmp, "wb") as f:
    f.write(jpeg_with_xmp(read(src), "digitalCapture"))
sign(tmp, "v_signed_ai_plus_xmp_capture.jpg", [created("trainedAlgorithmicMedia")], "ai-proven", False,
     "signed AI proof + unsigned XMP digitalCapture: an unsigned claim should not cancel a proof")
with open(tmp, "wb") as f:
    f.write(jpeg_with_xmp(read(src), "trainedAlgorithmicMedia"))
sign(tmp, "v_signed_capture_plus_xmp_ai.jpg", [created("digitalCapture")], "inconsistent", False,
     "signed capture + unsigned XMP AI: the SPEC example for `inconsistent`")
os.remove(tmp)

# 3. Tampering after signing.
ai = read(os.path.join(signed, "ai.jpg"))
cap = read(os.path.join(signed, "capture.jpg"))
flip = bytearray(ai)
flip[-200] ^= 0xFF  # inside the compressed image data
add("v_tampered_ai_pixel.jpg", bytes(flip), "ai-signal", False,
    "ai.jpg with one image byte changed: manifest invalid, AI claim still readable; must not be ai-proven")
flip = bytearray(cap)
flip[-200] ^= 0xFF
add("v_tampered_capture_pixel.jpg", bytes(flip), "no-signal", True,
    "capture.jpg with one image byte changed: must not be capture-proven")
add("v_ai_plus_trailing_xmp_capture.jpg", ai + xmp("digitalCapture"), "ai-signal", False,
    "ai.jpg with an XMP packet appended after the end of the image")

# 4. Manifest of ai.jpg transplanted into another image (a human photo from the fixtures).
other = read(os.path.join(fixtures, "earth_apollo17.jpg"))
if any(m == 0xEB for m, _, _ in jpeg_segments(other)):
    print("SKIP transplant: earth_apollo17.jpg already has APP11 segments")
else:
    app11 = b"".join(ai[s:e] for m, s, e in jpeg_segments(ai) if m == 0xEB)
    add("v_transplanted_manifest.jpg", other[:2] + app11 + other[2:], "no-signal", True,
        "C2PA segments of ai.jpg pasted into a different image: hash mismatch, must not be ai-proven")

# 5. Trusted capture PNG that carries an A1111 chunk (chunk added before signing).
png = read(os.path.join(fixtures, "sample1.png"))
data = b"parameters\0a fox\nSteps: 20, Sampler: Euler a"
import zlib  # noqa: E402
chunk = struct.pack(">I", len(data)) + b"tEXt" + data + struct.pack(">I", zlib.crc32(b"tEXt" + data) & 0xFFFFFFFF)
tmp_png = os.path.join(out, "_src.png")
with open(tmp_png, "wb") as f:
    f.write(png[:33] + chunk + png[33:])
sign(tmp_png, "v_signed_capture_plus_a1111_chunk.png", [created("digitalCapture")], "inconsistent", False,
     "signed capture + A1111 `parameters` chunk")
os.remove(tmp_png)

with open(os.path.join(out, "expected.json"), "w") as f:
    json.dump(EXPECTED, f, indent=1, sort_keys=True)
print(f"{len(EXPECTED)} variants in {out}")
