import io
import os
import struct
import tempfile
import unittest

import isitai


_HERE = os.path.dirname(os.path.abspath(__file__))
_TEXT = os.path.join(_HERE, "..", "..", "..", "bench", "crosslang", "text")
with open(os.path.join(_TEXT, "en_prose.txt"), encoding="utf-8") as _f:
    EN_PROSE = _f.read()
with open(os.path.join(_TEXT, "fr_prose.txt"), encoding="utf-8") as _f:
    FR_PROSE = _f.read()


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
        self.assertEqual(latin1["warnings"][0], "text decoded as Windows-1252")
        utf16 = isitai.check(b"\xff\xfe" + "Très bien cite turn0search1".encode("utf-16-le"))
        self.assertEqual(utf16["verdict"], "ai-signal")
        self.assertEqual(utf16["warnings"][0], "text decoded as UTF-16LE")
        # With the score off, the encoding is the only warning.
        utf16 = isitai.check(
            b"\xff\xfe" + "Très bien cite turn0search1".encode("utf-16-le"), score=False
        )
        self.assertEqual(utf16["warnings"], ["text decoded as UTF-16LE"])
        self.assertNotIn("coefficient", utf16)

    def test_score_of_an_english_text(self):
        r = isitai.check_text(EN_PROSE)
        c = r["coefficient"]
        self.assertIn(r["verdict"], ("no-signal", "ai-likely"))
        self.assertGreater(c["lr"], 0)
        self.assertLessEqual(c["lr_interval"][0], c["lr"])
        self.assertLessEqual(c["lr"], c["lr_interval"][1])
        self.assertEqual(c["coverage"], 0.9)
        self.assertTrue(c["calibration_id"].startswith("text-light-v1/en/"))
        self.assertIsNone(c["prevalence_used"])
        self.assertIsNone(c["posterior"])
        self.assertIn("language detected: en", r["notes"])
        # A plain text file gets the same report as the string.
        self.assertEqual(isitai.check(EN_PROSE.encode()), r)

    def test_posterior_needs_a_prevalence(self):
        c = isitai.check_text(EN_PROSE, prevalence=0.5)["coefficient"]
        self.assertEqual(c["prevalence_used"], 0.5)
        self.assertAlmostEqual(c["posterior"], c["lr"] / (c["lr"] + 1), places=3)
        for bad in (0, 1, -0.2, 1.5, float("nan")):
            with self.assertRaises(ValueError):
                isitai.check_text(EN_PROSE, prevalence=bad)
        with self.assertRaises(ValueError):
            isitai.check(EN_PROSE.encode(), prevalence=2)

    def test_score_abstains_and_can_be_turned_off(self):
        short = isitai.check_text("Back on Monday. See you.")
        self.assertEqual(short["verdict"], "no-signal")
        self.assertIsNone(short["coefficient"]["lr"])
        self.assertIsNone(short["coefficient"]["calibration_id"])
        self.assertTrue(short["warnings"][0].startswith("score not given: text too short"))
        french = isitai.check_text(FR_PROSE)
        self.assertIsNone(french["coefficient"]["lr"])
        self.assertIn("no calibration table for `fr` text", french["warnings"][0])
        off = isitai.check_text(EN_PROSE, score=False)
        self.assertNotIn("coefficient", off)
        self.assertNotIn("warnings", off)
        # Markup is not scored.
        self.assertNotIn("coefficient", isitai.check(b"<!DOCTYPE html><p>" + EN_PROSE.encode() + b"</p>"))
        # A proof or a signal always wins over the score.
        signal = isitai.check_text(EN_PROSE + " :contentReference[oaicite:0]{index=0}")
        self.assertEqual(signal["verdict"], "ai-signal")

    def test_missing_file_raises(self):
        with self.assertRaises(OSError):
            isitai.check_file("/definitely/missing.jpg")


if __name__ == "__main__":
    unittest.main()
