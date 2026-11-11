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

    def test_missing_file_raises(self):
        with self.assertRaises(OSError):
            isitai.check_file("/definitely/missing.jpg")


if __name__ == "__main__":
    unittest.main()
