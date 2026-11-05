"""scripts/lib/install_receipt.py's hash, held to the digests cli/hash.mjs is held to (ADR 0029 §4), and its
table of where setup installs, held to cli/harnesses.mjs."""

import json
import re
import unittest
from pathlib import Path

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


class Places(unittest.TestCase):
    HARNESS = re.compile(r"^\s*\{ id: '([^']+)'.*?skillsDir: '([^']+)'(?:.*?agentsDir: '([^']+)')?.*?"
                         r"mcp: (?:\{ file: '([^']+)'|null)", re.M)

    def test_the_table_is_cli_harnesses_mjs(self):
        text = (helpers.PLUGIN_ROOT / "cli" / "harnesses.mjs").read_text(encoding="utf-8")
        found = {hid: (skills, agents or None, mcp or None) for hid, skills, agents, mcp in self.HARNESS.findall(text)}
        self.assertGreaterEqual(len(found), 16, found)
        self.assertEqual(install_receipt.HARNESS_PLACES, found)

    def test_the_former_folders_are_cli_harnesses_mjs(self):
        text = (helpers.PLUGIN_ROOT / "cli" / "harnesses.mjs").read_text(encoding="utf-8")
        found = {hid: tuple(re.findall(r"'([^']+)'", dirs))
                 for hid, dirs in re.findall(r"^\s*\{ id: '([^']+)'.*?formerDirs: \[([^\]]*)\]", text, re.M)}
        self.assertEqual(install_receipt.FORMER_PLACES, found)
        self.assertIsNone(install_receipt.misplaced(".windsurf/skills/dgf/SKILL.md", "windsurf"))
        self.assertIsNotNone(install_receipt.misplaced(".windsurf/skills/dgf/SKILL.md", "claude"))

    def test_misplaced_matches_cli_receipt_mjs(self):
        self.assertIsNone(install_receipt.misplaced(".dgf-factory/runtime/scripts/x.py", "runtime"))
        self.assertIsNone(install_receipt.misplaced(".claude/agents/a.md", "claude"))
        for rel, owner in (("src/Program.cs", "runtime"), ("src/Program.cs", "claude"), (".git/hooks/x", "runtime"),
                           (".claude/skills/x/.Git/config", "claude"), (".cursor/skills/x", "claude"),
                           (".claude/skills/x", "nobody"), (".claude/skills/x", None)):
            with self.subTest(rel=rel, owner=owner):
                self.assertIsNotNone(install_receipt.misplaced(rel, owner))


if __name__ == "__main__":
    unittest.main()


class Line(unittest.TestCase):
    """The receipt's dgfLine (ADR 0036 §3): read as cli/receipt.mjs writes and refuses it."""

    def write(self, data):
        import json
        import shutil
        import tempfile
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root)
        (root / ".dgf-factory").mkdir()
        (root / ".dgf-factory" / "install.json").write_text(json.dumps(data), encoding="utf-8")
        return root

    def test_a_recorded_line_is_read(self):
        root = self.write({"tool": "dgf-factory", "version": "0.3.0", "dgfLine": "1.2", "files": {}, "mcp": {}})
        self.assertEqual(install_receipt.line(root), "1.2")

    def test_an_older_receipt_and_no_receipt_have_no_line(self):
        root = self.write({"tool": "dgf-factory", "version": "0.2.0", "files": {}, "mcp": {}})
        self.assertIsNone(install_receipt.line(root))
        self.assertIsNone(install_receipt.line(root / "elsewhere"))

    def test_a_malformed_line_is_refused(self):
        for bad in ("1.2.0", "latest", 12):
            with self.subTest(bad=bad):
                root = self.write({"tool": "dgf-factory", "version": "0.3.0", "dgfLine": bad, "files": {}, "mcp": {}})
                with self.assertRaises(install_receipt.ReceiptError):
                    install_receipt.line(root)
