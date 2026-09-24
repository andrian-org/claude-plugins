"""The known-bad corpus: every blocking finding and every exit-3 path has a failing fixture.

"A validator with no failing fixture has not been tested" (ADR 0014, follow-ups).
Each case under tests/fixtures/known-bad/<case>/ holds a synthetic workspaces
root and an expected.json — {"cli", "args", "exit", "codes"}. The CLI runs from
the case directory; it must exit exactly `exit`, report every code in `codes`,
and report no other error. Fixtures are synthetic, never copied from DGF, and
live outside the shipped directories.
"""

import importlib.util
import json
import re
import unittest

from tests import helpers

CORPUS = helpers.FIXTURES / "known-bad"
FINDING = re.compile(r"^(ERROR|WARN|INFO) ([A-Z_]+) ", re.MULTILINE)
EXPECTED_KEYS = {"cli", "args", "exit", "codes"}


def cases():
    return sorted(path for path in CORPUS.iterdir() if (path / "expected.json").is_file())


def load_doctor():
    spec = importlib.util.spec_from_file_location("doctor", helpers.PLUGIN_ROOT / "skills/dgf-doctor/scripts/doctor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Corpus(unittest.TestCase):
    def test_the_corpus_is_not_shipped(self):
        self.assertNotIn("tests", load_doctor().SHIPPED_DIRS)

    def test_every_expected_file_is_well_formed(self):
        self.assertGreaterEqual(len(cases()), 24)
        for case in cases():
            expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
            self.assertEqual(set(expected), EXPECTED_KEYS, case.name)
            self.assertTrue((helpers.SCRIPTS / expected["cli"]).is_file(), case.name)
            self.assertIn(expected["exit"], (1, 3), case.name)

    def test_no_fixture_names_a_dgf_path(self):
        pattern = load_doctor().DGF_PATH_PATTERN
        for path in CORPUS.rglob("*"):
            if path.is_file():
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")), path)


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class KnownBad(unittest.TestCase):
    def test_each_case_fails_exactly_as_expected(self):
        from lib import report
        for case in cases():
            expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
            with self.subTest(case=case.name):
                code, out, err = helpers.run_cli(expected["cli"], *expected["args"], cwd=case)
                shown = f"{case.name}\n--- stdout ---\n{out}--- stderr ---\n{err}"
                self.assertEqual(code, expected["exit"], shown)
                found = set(FINDING.findall(out + err))
                codes = {finding_code for _, finding_code in found}
                for wanted in expected["codes"]:
                    self.assertIn(wanted, codes, shown)
                errors = {c for label, c in found if label == "ERROR" and report.CODES[c] != report.EXIT_WARNINGS}
                self.assertEqual(errors - set(expected["codes"]), set(), shown)


if __name__ == "__main__":
    unittest.main()
