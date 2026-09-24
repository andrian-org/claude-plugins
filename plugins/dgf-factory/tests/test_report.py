"""Exit aggregation and rendering in scripts/lib/report.py."""

import io
import unittest

from tests import helpers  # noqa: F401 — puts scripts/ on sys.path
from lib import report


class ExitAggregation(unittest.TestCase):
    def test_usage_beats_blocked_beats_warnings_beats_clean(self):
        self.assertEqual(report.worst([0, 2, 1, 3]), 3)
        self.assertEqual(report.worst([0, 2, 1]), 1)
        self.assertEqual(report.worst([0, 2]), 2)
        self.assertEqual(report.worst([0, 0]), 0)
        self.assertEqual(report.worst([]), 0)

    def test_blocked_is_not_hidden_by_a_later_warning(self):
        self.assertEqual(report.worst([1, 2, 2]), 1)

    def test_exit_code_across_reports(self):
        clean = report.Report("a.json", "json")
        warned = report.Report("b.json", "json")
        warned.add("UNKNOWN_PROPERTY", "x")
        blocked = report.Report("c.xml", "xsd")
        blocked.add("XSD_INVALID", "y")
        self.assertEqual(report.exit_code([clean, warned]), 2)
        self.assertEqual(report.exit_code([clean, warned, blocked]), 1)

    def test_info_does_not_change_the_exit_code(self):
        rep = report.Report("a.json", "json")
        rep.add("NO_SERVICE", "legal, not dispatchable")
        self.assertEqual(rep.exit_code(), 0)

    def test_severity_comes_from_the_code(self):
        rep = report.Report("a.json", "json")
        self.assertEqual(rep.add("FAMILY_UNRESOLVED", "z").severity, 3)
        with self.assertRaises(KeyError):
            rep.add("NOT_A_CODE", "z")


class Rendering(unittest.TestCase):
    def test_output_order_and_verdict(self):
        rep = report.Report("f.json", "json")
        rep.ran("json-schema")
        rep.skipped("json-format", "annotation-only, ADR 0015")
        rep.add("UNKNOWN_PROPERTY", "`x` is ignored by the runtime", line=3)
        buf = io.StringIO()
        code = report.render([rep], buf, header="Config validation")
        lines = [line for line in buf.getvalue().splitlines() if line]
        self.assertEqual(code, 2)
        self.assertEqual(lines[0], "Config validation")
        self.assertEqual(lines[1], "FAMILY: json f.json")
        self.assertEqual(lines[2], "CHECKS RUN: json-schema")
        self.assertEqual(lines[3], "NOT RUN: json-format (annotation-only, ADR 0015)")
        self.assertEqual(lines[4], "WARN UNKNOWN_PROPERTY f.json:3 `x` is ignored by the runtime")
        self.assertEqual(lines[-1], "WARNINGS")

    def test_usage_error_renders_blocked(self):
        rep = report.Report("f.txt")
        rep.add("FAMILY_UNRESOLVED", "neither")
        buf = io.StringIO()
        self.assertEqual(report.render([rep], buf), 3)
        self.assertEqual(buf.getvalue().splitlines()[-1], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
