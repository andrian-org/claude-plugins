"""scripts/lib/install_receipt.py's hash, held to the digests cli/hash.mjs is held to (ADR 0029 §4)."""

import json
import unittest

from tests import helpers
from lib import install_receipt

FIXTURES = helpers.FIXTURES / "hash"
EXPECTED = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))


class SharedFixture(unittest.TestCase):
    def test_every_fixture_matches_the_shared_digest(self):
        self.assertGreaterEqual(len(EXPECTED), 8)
        for name, want in EXPECTED.items():
            data = (FIXTURES / name).read_bytes()
            self.assertEqual(install_receipt.is_text(data), want["text"], name)
            self.assertEqual(install_receipt.hash_file(FIXTURES / name), want["sha256"], name)

    def test_the_fixtures_kept_their_bytes(self):
        # .gitattributes keeps them byte-exact; a checkout that normalised them would hash differently
        self.assertIn(b"\r\n", (FIXTURES / "crlf.txt").read_bytes())
        self.assertTrue((FIXTURES / "bom.md").read_bytes().startswith(b"\xef\xbb\xbf"))


class Hash(unittest.TestCase):
    def test_line_endings_and_trailing_whitespace_do_not_count(self):
        want = install_receipt.hash_bytes(b"a\nb")
        self.assertEqual(install_receipt.hash_bytes(b"a\r\nb\r\n"), want)
        self.assertEqual(install_receipt.hash_bytes(b"a\nb\n\n \t\n"), want)

    def test_binary_is_hashed_raw(self):
        self.assertFalse(install_receipt.is_text(b"a\x00"))
        self.assertNotEqual(install_receipt.hash_bytes(b"a\r\n\x00"), install_receipt.hash_bytes(b"a\n\x00"))


if __name__ == "__main__":
    unittest.main()
