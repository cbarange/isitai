"""Build a signed C2PA test corpus, one file per format, with the c2pa-rs TEST certificates.

Each output declares a digitalSourceType in a `c2pa.created` action, so the expected
verdict is known: `ai-proven` (trainedAlgorithmicMedia) or `capture-proven` (digitalCapture)
when read with the c2pa-rs test root bundle as trust anchors.

Usage: python -I make_signed.py <c2pa-rs fixtures dir> <certs dir (es256.pem, es256.pub)> <out dir>
Needs: pip install c2pa-python. No network: no timestamp authority is used.
"""
import json, os, sys
import c2pa

fixtures, certs, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)

DST = "http://cv.iptc.org/newscodes/digitalsourcetype/"
# (source fixture, output name, digitalSourceType)
CASES = [
    ("no_manifest.jpg", "ai.jpg", "trainedAlgorithmicMedia"),
    ("no_manifest.jpg", "capture.jpg", "digitalCapture"),
    ("sample1.png", "ai.png", "trainedAlgorithmicMedia"),
    ("sample1.webp", "ai.webp", "trainedAlgorithmicMedia"),
    ("sample1.avif", "ai.avif", "trainedAlgorithmicMedia"),
    ("sample1.heic", "ai.heic", "trainedAlgorithmicMedia"),
    ("sample1.gif", "ai.gif", "trainedAlgorithmicMedia"),
    ("sample1.svg", "ai.svg", "trainedAlgorithmicMedia"),
    ("MultiPage.tif", "ai.tif", "trainedAlgorithmicMedia"),
    ("sample1.mp3", "ai.mp3", "trainedAlgorithmicMedia"),
    ("sample1.wav", "ai.wav", "trainedAlgorithmicMedia"),
    ("sample1.m4a", "ai.m4a", "trainedAlgorithmicMedia"),
    ("video1_no_manifest.mp4", "ai.mp4", "trainedAlgorithmicMedia"),
    ("c.mov", "ai.mov", "trainedAlgorithmicMedia"),
    ("basic.pdf", "ai.pdf", "trainedAlgorithmicMedia"),
]

# c2pa-python 0.38 wants bytes here, despite its docstring saying "string".
with open(os.path.join(certs, "es256.pub"), "rb") as f:
    cert = f.read()
with open(os.path.join(certs, "es256.pem"), "rb") as f:
    key = f.read()
info = c2pa.C2paSignerInfo(c2pa.C2paSigningAlg.ES256, cert, key, None)

expected = {}
for src, name, dst in CASES:
    manifest = {
        "claim_generator_info": [{"name": "isitai-test-corpus", "version": "0.1"}],
        "title": name,
        "assertions": [{
            "label": "c2pa.actions",
            "data": {"actions": [{"action": "c2pa.created", "digitalSourceType": DST + dst}]},
        }],
    }
    dest = os.path.join(out, name)
    if os.path.exists(dest):
        os.remove(dest)
    try:
        signer = c2pa.Signer.from_info(info)
        with c2pa.Builder(manifest) as builder:
            builder.sign_file(os.path.join(fixtures, src), dest, signer)
        expected[name] = "capture-proven" if dst == "digitalCapture" else "ai-proven"
        print(f"signed  {name:<12} from {src}")
    except Exception as e:
        if os.path.exists(dest):
            os.remove(dest)  # a failed sign can leave an empty file behind
        print(f"FAILED  {name:<12} from {src}: {type(e).__name__}: {str(e)[:120]}")

with open(os.path.join(out, "expected.json"), "w") as f:
    json.dump(expected, f, indent=2)
