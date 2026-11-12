import io
import os
import struct
import tempfile
import unittest

import isitai


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + b"\0\0\0\0"


PNG = (
    b"\x89PNG\r\n\x1a\n"
    + chunk(b"IHDR", b"\0" * 13)
    + chunk(b"tEXt", b"parameters\0a cat, Steps: 20")
    + chunk(b"IEND", b"")
)


class BasicTest(unittest.TestCase):
    def test_text_artifact(self):
        r = isitai.check_text("Élève doué :contentReference[oaicite:0]{index=0}")
        self.assertEqual(r["verdict"], "ai-signal")
        self.assertEqual(r["evidence"][0]["location"]["text"], ":contentReference[oaicite:0]{index=0}")

    def test_french_typography_is_no_signal(self):
        self.assertEqual(isitai.check_text("Il a dit : « oui »")["verdict"], "no-signal")

    def test_file_and_bytes_agree(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sd.png")
            with open(path, "wb") as f:
                f.write(PNG)
            from_file = isitai.check_file(path)
        self.assertEqual(from_file["verdict"], "ai-signal")
        self.assertEqual(from_file["generator"], "Stable Diffusion WebUI (A1111/Forge)")
        self.assertEqual(isitai.check(PNG), from_file)

    def test_effort(self):
        xmp = (
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:Description Iptc4xmpExt:DigitalSourceType='
            b'"http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"/></x:xmpmeta>'
        )
        jpeg = b"\xff\xd8\xff\xe0" + xmp
        self.assertEqual(isitai.check(jpeg)["verdict"], "ai-signal")
        self.assertEqual(isitai.check(jpeg, effort="standard")["verdict"], "ai-signal")
        self.assertEqual(isitai.check(jpeg, effort="fast")["verdict"], "no-signal")
        with self.assertRaisesRegex(ValueError, "unknown effort `thorough`"):
            isitai.check(jpeg, effort="thorough")
        with self.assertRaisesRegex(ValueError, "unknown effort `turbo`"):
            isitai.check(jpeg, effort="turbo")
        with self.assertRaisesRegex(ValueError, "unknown effort `turbo`"):
            isitai.check_file(__file__, effort="turbo")

    def test_unusable_trust_anchors_raise(self):
        jpeg = b"\xff\xd8\xff\xe0"
        for pem in ("", "not a pem file"):
            with self.assertRaisesRegex(ValueError, "trust anchors: no PEM certificate block"):
                isitai.check(jpeg, trust_anchors_pem=pem)
            with self.assertRaisesRegex(ValueError, "trust anchors: no PEM certificate block"):
                isitai.check_file(__file__, trust_anchors_pem=pem)
        junk = "-----BEGIN CERTIFICATE-----\nnot base64\n-----END CERTIFICATE-----\n"
        with self.assertRaisesRegex(ValueError, "trust anchors: .*no certificate that can be loaded"):
            isitai.check(jpeg, trust_anchors_pem=junk)
        # No anchors at all stays valid.
        self.assertEqual(isitai.check(jpeg, trust_anchors_pem=None)["verdict"], "no-signal")

    def test_text_rules_run_inside_an_html_file(self):
        html = "<!DOCTYPE html>\n<p>Paris :contentReference[oaicite:0]{index=0}</p>".encode()
        r = isitai.check(html)
        self.assertEqual(r["media"], "text/html")
        self.assertEqual(r["verdict"], "ai-signal")

    def test_stream_and_bytes_agree(self):
        html = "<!DOCTYPE html>\n<p>Paris :contentReference[oaicite:0]{index=0}</p>".encode()
        expected = isitai.check(html)
        self.assertEqual(expected["verdict"], "ai-signal")
        self.assertEqual(isitai.DEFAULT_MAX_STREAM_BYTES, 256 * 1024 * 1024)
        self.assertEqual(isitai.check_stream(io.BytesIO(html)), expected)
        self.assertEqual(isitai.check_stream(io.BytesIO(PNG)), isitai.check(PNG))
        self.assertEqual(isitai.check_stream(io.BytesIO(b"")), isitai.check(b""))
        # The limit is the size of the data: accepted.
        self.assertEqual(isitai.check_stream(io.BytesIO(html), max_bytes=len(html)), expected)
        # Options go to the check.
        with self.assertRaisesRegex(ValueError, "unknown effort `turbo`"):
            isitai.check_stream(io.BytesIO(html), effort="turbo")

    def test_stream_over_the_limit_raises(self):
        html = b"<p>Paris :contentReference[oaicite:0]{index=0}</p>"
        with self.assertRaisesRegex(ValueError, "stream is larger than the limit of 49 bytes"):
            isitai.check_stream(io.BytesIO(html), max_bytes=len(html) - 1)
        with self.assertRaises(ValueError):
            isitai.check_stream(io.BytesIO(html), max_bytes=-1)

        class Endless:
            """Never ends, like a hostile HTTP body. Counts what was asked of it."""

            def __init__(self):
                self.given = 0

            def read(self, size):
                self.given += size
                return b"x" * size

        endless = Endless()
        with self.assertRaises(ValueError):
            isitai.check_stream(endless, max_bytes=3 * 1024 * 1024)
        self.assertEqual(endless.given, 3 * 1024 * 1024 + 1)

    def test_stream_needs_only_read(self):
        class OnlyRead:
            """Like urllib3 and boto3 bodies: `read(amt)`, short reads, then b""."""

            def __init__(self, data):
                self.data = data

            def read(self, amt):
                chunk, self.data = self.data[:7], self.data[7:]
                return chunk

        self.assertEqual(isitai.check_stream(OnlyRead(PNG)), isitai.check(PNG))
        with self.assertRaisesRegex(TypeError, "binary stream"):
            isitai.check_stream(io.StringIO("text"))

    def test_text_encodings_are_decoded(self):
        latin1 = isitai.check("Très bien :contentReference[oaicite:0]{index=0}".encode("latin-1"))
        self.assertEqual(latin1["verdict"], "ai-signal")
        self.assertEqual(latin1["warnings"], ["text decoded as Windows-1252"])
        utf16 = isitai.check(b"\xff\xfe" + "Très bien cite turn0search1".encode("utf-16-le"))
        self.assertEqual(utf16["verdict"], "ai-signal")
        self.assertEqual(utf16["warnings"], ["text decoded as UTF-16LE"])

    def test_missing_file_raises(self):
        with self.assertRaises(OSError):
            isitai.check_file("/definitely/missing.jpg")


if __name__ == "__main__":
    unittest.main()
