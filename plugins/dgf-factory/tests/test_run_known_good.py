"""tools/run_known_good.py: the exceptions file and how an entry excuses a finding (DD12).

The run itself needs a DGF checkout, so it is not tested here; its parsing and
matching are, because a mistake there would excuse errors silently.
"""

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import report


def load_tool():
    spec = importlib.util.spec_from_file_location("run_known_good", helpers.TOOLS / "run_known_good.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TOOL = load_tool()


def finding(code="SCHEMA_INVALID", line=None, message="$.paging.pageSize: '20' is not of type integer"):
    return report.Finding(code, report.CODES[code], "ignored", line, message)


class ExceptionsFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def load(self, text):
        path = Path(self.tmp) / "exceptions.txt"
        path.write_text(text, encoding="utf-8")
        return TOOL.load_exceptions(path)

    def test_entries_comments_and_a_path_with_spaces(self):
        exceptions, external = self.load(
            "# a comment\n\nEXPECTED_EXTERNAL ZIMS4_Visa\n"
            "EXCEPTION SCHEMA_INVALID app/FM/_DATA/T/_forms/My Form/_form.json L7 -- the reason\n")
        self.assertEqual(external, {"ZIMS4_Visa"})
        entry = exceptions[0]
        self.assertEqual((entry.code, entry.path, entry.key, entry.reason),
                         ("SCHEMA_INVALID", "app/FM/_DATA/T/_forms/My Form/_form.json", "L7", "the reason"))

    def test_malformed_lines_are_exit_3(self):
        for text in ("EXCEPTION SCHEMA_INVALID a/b.json L7\n",            # no reason
                     "EXCEPTION SCHEMA_INVALID a/b.json -- reason\n",      # no key
                     "EXCEPTION NOT_A_CODE a/b.json L7 -- reason\n",
                     "EXPECTED_EXTERNAL two names\n",
                     "IGNORE a/b.json\n"):
            with self.subTest(text=text), self.assertRaises(SystemExit) as raised:
                self.load(text)
            self.assertEqual(raised.exception.code, 3)

    def test_the_committed_file_loads(self):
        exceptions, external = TOOL.load_exceptions()
        self.assertEqual(len(external), 8)
        self.assertTrue(all(entry.reason for entry in exceptions))


class Matching(unittest.TestCase):
    def entry(self, key, code="SCHEMA_INVALID", path="a/b.json"):
        return TOOL.Exception_(code, path, key, "reason", 1)

    def test_line_key(self):
        self.assertTrue(self.entry("L7").matches(finding(line=7), "a/b.json"))
        self.assertFalse(self.entry("L7").matches(finding(line=8), "a/b.json"))

    def test_text_key(self):
        self.assertTrue(self.entry("$.paging.pageSize").matches(finding(), "a/b.json"))
        self.assertFalse(self.entry("$.columns").matches(finding(), "a/b.json"))

    def test_star_key_is_every_finding_of_the_code_in_the_file(self):
        self.assertTrue(self.entry("*").matches(finding(line=3), "a/b.json"))

    def test_code_and_path_must_match(self):
        self.assertFalse(self.entry("*", code="XML_MALFORMED").matches(finding(), "a/b.json"))
        self.assertFalse(self.entry("*").matches(finding(), "a/c.json"))


class Arguments(unittest.TestCase):
    def test_a_directory_that_is_not_a_dgf_root_is_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = helpers.run_cli(helpers.TOOLS / "run_known_good.py", tmp)
        self.assertEqual(code, 3, err)
        self.assertIn("Not a DGF repository root", err)

    def test_an_unregistered_pack_is_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_root(Path(tmp), {"src/Directory.Build.props": "<Project/>\n",
                                                 "src/samples/workspaces/.keep": ""})
            # the arguments are settled before the dependency check: without lxml/jsonschema the answer is the same
            code, _, err = helpers.run_cli_blocking(helpers.TOOLS / "run_known_good.py", root, "--pack", "9.9")
        self.assertEqual(code, 3, err)
        self.assertIn("no knowledge pack for DGF line 9.9", err)


class Packs(unittest.TestCase):
    """--pack picks the pack's directory, exceptions file and schema ledger (ADR 0036 §2)."""

    def test_the_current_line_uses_the_tools_exceptions_file(self):
        packs = helpers.load_tool("packs")
        line, entry, knowledge_dir, exceptions, ledger = TOOL.resolve_pack(None)
        self.assertEqual(line, packs.current())
        self.assertEqual(knowledge_dir, helpers.PLUGIN_ROOT / "knowledge")
        self.assertEqual(exceptions, helpers.PLUGIN_ROOT / "tools" / "known-good-exceptions.txt")
        self.assertEqual(ledger, helpers.PLUGIN_ROOT / "provenance" / "knowledge" / "schemas" / "MANIFEST.md")
        self.assertEqual(entry["line"], line)

    def test_every_registered_pack_resolves_with_its_own_exceptions(self):
        packs = helpers.load_tool("packs")
        for line in packs.lines():
            with self.subTest(line=line):
                _line, _entry, knowledge_dir, exceptions, _ledger = TOOL.resolve_pack(line)
                self.assertEqual(knowledge_dir, packs.pack_dir(line))
                self.assertTrue(exceptions.is_file(), exceptions)


class CheckoutTag(unittest.TestCase):
    """The checkout must be at the pack's release tag, or the run says so (ADR 0036 §2, check_drift's VERSION_MISMATCH)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="known-good-tag-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = helpers.make_repo(self.tmp / "dgf", {"README.md": "dgf\n"})

    def test_the_newest_release_tag_at_head_is_read(self):
        helpers.tag(self.repo, "1.3.0")
        helpers.tag(self.repo, "1.3.1")
        helpers.tag(self.repo, "1.3.1-beta")
        self.assertEqual(TOOL.release_tag(self.repo), "1.3.1")

    def test_a_tag_other_than_the_packs_is_a_mismatch(self):
        helpers.tag(self.repo, "1.3.1")
        message = TOOL.version_mismatch(TOOL.release_tag(self.repo), {"line": "1.3", "dgf_version": "1.3.0"})
        self.assertIn("1.3.1", message)
        self.assertIn("1.3.0", message)

    def test_no_release_tag_is_a_mismatch(self):
        message = TOOL.version_mismatch(TOOL.release_tag(self.repo), {"line": "1.3", "dgf_version": "1.3.0"})
        self.assertIn("no release tag", message)

    def test_the_packs_own_tag_is_no_mismatch(self):
        helpers.tag(self.repo, "1.3.0")
        self.assertIsNone(TOOL.version_mismatch(TOOL.release_tag(self.repo), {"line": "1.3", "dgf_version": "1.3.0"}))


if __name__ == "__main__":
    unittest.main()
