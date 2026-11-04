"""scripts/lib/dgf_version.py — versions, lines, and which pack setup installs (ADR 0036 §3).

The selection cases come from tests/fixtures/unit/dgf-lines/selection.json, which
tests/cli/lines.test.mjs reads too: the Python and Node selectors must agree.
"""

import json
import unittest

from tests import helpers
from lib import dgf_version

VECTORS = json.loads((helpers.FIXTURES / "unit" / "dgf-lines" / "selection.json").read_text(encoding="utf-8"))


def run_case(lines, current, case_input):
    return dgf_version.select_line(lines, current, **case_input)


class Parsing(unittest.TestCase):
    def test_a_version_parses_to_three_ints(self):
        self.assertEqual(dgf_version.parse("1.3.0"), (1, 3, 0))
        self.assertEqual(dgf_version.parse(" 1.10.2 "), (1, 10, 2))

    def test_anything_else_is_a_version_error(self):
        for bad in ("1.3", "1.3.x", "v1.3.0", "1.3.0-beta", "", None, "unknown"):
            with self.assertRaises(dgf_version.VersionError, msg=repr(bad)):
                dgf_version.parse(bad)

    def test_line_of_and_parse_line(self):
        self.assertEqual(dgf_version.line_of("1.1.16"), "1.1")
        self.assertEqual(dgf_version.parse_line("1.3"), (1, 3))
        with self.assertRaises(dgf_version.VersionError):
            dgf_version.parse_line("1.3.0")

    def test_compare_is_numeric(self):
        self.assertEqual(dgf_version.compare("1.1.9", "1.1.16"), -1)
        self.assertEqual(dgf_version.compare("1.10.0", "1.9.9"), 1)
        self.assertEqual(dgf_version.compare("1.3.0", "1.3.0"), 0)


class Selection(unittest.TestCase):
    def test_every_shared_vector(self):
        for case in VECTORS["cases"]:
            with self.subTest(case["name"]):
                self.check(VECTORS["lines"], VECTORS["current"], case)

    def test_a_gap_between_lines_maps_to_the_nearest_older_pack(self):
        gap = VECTORS["gap"]
        self.check(gap["lines"], gap["current"], gap)

    def check(self, lines, current, case):
        expect = case["expect"]
        if "error" in expect:
            with self.assertRaises(dgf_version.SelectionError) as caught:
                run_case(lines, current, case["input"])
            self.assertEqual(caught.exception.kind, expect["error"])
            return
        chosen = run_case(lines, current, case["input"])
        self.assertEqual(chosen.line, expect["line"])
        self.assertEqual(chosen.source, expect["source"])
        self.assertEqual(bool(chosen.note), bool(expect.get("note")), chosen.note)

    def test_the_refusal_names_the_explicit_override(self):
        with self.assertRaises(dgf_version.SelectionError) as caught:
            dgf_version.select_line(["1.1", "1.3"], "1.3", flag_version="1.0.9")
        self.assertIn("--dgf-line 1.1", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
