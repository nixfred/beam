"""Adversarial pairing_root parser probes: credential-shaped decoys, nesting, truncation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_helpers import load_beam

beam = load_beam()


class PairingParserTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "sunshine_state.json"

    def parse(self, text):
        self.path.write_text(text)
        return beam.pairing_root(self.path)

    def test_nested_root_inside_skipped_value_is_not_collected(self):
        root = self.parse('{"creds": {"root": {"named_devices": [{"uuid": "a", "cert": "b"}]}}, "x": 1}')
        self.assertEqual(beam.paired_count(root), 0)

    def test_credential_lookalike_strings_with_escapes_are_skipped(self):
        root = self.parse('{"salt": "a\\"} , \\" }", "root": {"named_devices": [{"uuid": "u", "cert": "c"}]}}')
        self.assertEqual(beam.paired_count(root), 1)

    def test_root_as_primitive_or_string_counts_nothing(self):
        for text in ('{"root": 5}', '{"root": "abc"}', '{"root": [1, 2]}', '{"root": null}'):
            with self.subTest(text=text):
                self.assertEqual(beam.paired_count(self.parse(text)), 0)

    def test_enabled_variants(self):
        root = self.parse('{"root": {"named_devices": ['
                          '{"uuid": "a", "cert": "c", "enabled": "False"},'
                          '{"uuid": "b", "cert": "c", "enabled": 0},'
                          '{"uuid": "c", "cert": "c", "enabled": false},'
                          '{"uuid": "d", "cert": "c"},'
                          '{"uuid": "", "cert": "c"},'
                          '{"uuid": "e"}'
                          ']}}')
        self.assertEqual(beam.paired_count(root), 1)

    def test_deep_nesting_and_truncation_never_raise(self):
        for text in ('', '   \n ', '\ufeff{"root": {}}', '{"root"', '{"a": 123',
                     '{"a": {"b": {"c": [1, {"d": "e"}]}}, "root": {"named_devices": [{"uuid": "u", "cert": "c"}]}}',
                     '{"root": {"named_devices": [{"uuid": "u", "cert": "c"}]}, "trailing": broken'):
            with self.subTest(text=text[:30]):
                root = self.parse(text)
                self.assertIsInstance(root, dict)

    def test_oversize_file_is_rejected(self):
        self.path.write_text(' ' * (4 * 1024 * 1024 + 1) + '{"root": {}}')
        self.assertEqual(beam.pairing_root(self.path), {})

    def test_roundtrip_with_json_module_on_typical_file(self):
        payload = {"username": "alice", "password": "hash-value",
                   "root": {"named_devices": [{"uuid": "u", "cert": "c", "name": "iPad"}]}}
        self.path.write_text(json.dumps(payload))
        root = beam.pairing_root(self.path)
        self.assertEqual(root, payload["root"])
        self.assertEqual(beam.paired_count(root), 1)


if __name__ == "__main__":
    unittest.main()
