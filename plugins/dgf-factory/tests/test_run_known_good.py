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


if __name__ == "__main__":
    unittest.main()
