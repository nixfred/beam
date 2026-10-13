"""A poisoned QR cache file is served as success and the UI retry loop cannot recover."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_helpers import load_beam, FakeSystem

beam = load_beam()


class QrCacheTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.system = FakeSystem(present={"qrencode"})
        self.beam = beam.Beam(home=self.home, system=self.system)
        self.beam.cache.mkdir(parents=True)

    def target(self, text):
        return self.beam.cache / ("qr-" + hashlib.sha256(text.encode()).hexdigest() + ".png")

    def test_corrupt_cached_file_is_reported_ready_without_validation(self):
        text = "192.168.1.20"
        self.target(text).write_bytes(b"garbage-garbage-garbage")
        result = self.beam.qr(text)
        # BUG: ok=True although the cached file is not a PNG. QrCode.qml then
        # fails to load it and its retry loops back to the same poisoned file.
        self.assertTrue(result["ok"])
        self.assertEqual(result["path"], str(self.target(text)))
        self.assertEqual(self.system.commands, [])  # qrencode never re-run

    def test_tiny_cached_file_triggers_regeneration(self):
        text = "192.168.1.20"
        self.target(text).write_bytes(b"tiny")
        result = self.beam.qr(text)
        self.assertFalse(result["ok"])
        self.assertTrue(any(c and c[0] == "qrencode" for c in self.system.commands))

    def test_text_size_limit_and_missing_helper_are_truthful(self):
        self.assertFalse(self.beam.qr("")["ok"])
        self.assertFalse(self.beam.qr("x" * 2049)["ok"])
        self.system.present.clear()
        self.assertFalse(self.beam.qr("192.168.1.20")["ok"])
        self.assertEqual(self.beam.qr("192.168.1.20")["retryAction"], "install")


if __name__ == "__main__":
    unittest.main()
