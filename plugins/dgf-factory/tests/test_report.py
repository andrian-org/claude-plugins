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


class SpineCodes(unittest.TestCase):
    """The pipeline spine's codes force the exits ADR 0017 and ADR 0018 give them."""

    EXPECTED = {
        report.EXIT_USAGE: ("ROOT_NO_WORKSPACE", "PLAN_UNREADABLE", "PLAN_FORMAT_UNSUPPORTED"),
        report.EXIT_BLOCKED: (
            "ROOT_NOT_SET_UP", "ROOT_AMBIGUOUS", "PLAN_NOT_FOUND", "PLAN_AMBIGUOUS", "PLAN_FIELD_MISSING",
            "PLAN_FIELD_INVALID", "PLAN_UNKNOWN_WORKSPACE", "PLAN_BASE_REASON_MISSING", "PLAN_BRANCH_MISMATCH",
            "PLAN_NO_TASKS", "PLAN_TASK_INVALID", "PLAN_CODE_REASON_MISSING", "PLAN_ULTRA_BROKEN",
            "PLAN_FILE_UNDECLARED_WORKSPACE", "PLAN_KIND_MISMATCH", "PLAN_OUT_OF_SCOPE", "PLAN_CODE_FILE_NEW",
            "PLAN_ROUTE_MISMATCH", "PLAN_ROUTE_UNKNOWN", "PLAN_COMMITS_INVALID", "CHANGE_UNDECLARED_WORKSPACE", "CHANGE_OUT_OF_SCOPE",
            "CHANGE_CODE_UNPLANNED", "CHANGE_CODE_FILE_NEW", "GATE_TASK_UNCHECKED", "GATE_STRICT_WARNING",
            "GATE_PLAN_UNCONFIRMED"),
        report.EXIT_WARNINGS: (
            "PLAN_FALLBACK", "BASE_WORKSPACE_ABSENT", "VALIDATOR_DEPS_MISSING", "PLAN_NOT_AUTHORED",
            "PLAN_OVERLAP", "PLAN_COMMITS_MISSING", "CHANGE_OUTSIDE_WORKSPACE", "CHANGE_UNPLANNED_FILE", "CHANGE_TASK_FILE_UNCHANGED",
            "CHANGE_NOT_AUTHORED", "GATE_CHECK_NOT_RUN"),
        report.EXIT_CLEAN: ("PLAN_OVERLAP_UNREADABLE", "PRE_EXISTING", "FIXED"),
    }

    def test_every_spine_code_has_its_exit(self):
        for exit_code, codes in self.EXPECTED.items():
            for code in codes:
                self.assertEqual(report.CODES.get(code), exit_code, code)

    def test_existing_codes_keep_their_severity(self):
        self.assertEqual(report.CODES["PARITY_PARTIAL"], report.EXIT_WARNINGS)
        self.assertEqual(report.CODES["DEAD_TRANSITION"], report.EXIT_BLOCKED)
        self.assertEqual(report.CODES["ROUTE_NO_ROW"], report.EXIT_USAGE)


class LearningCodes(unittest.TestCase):
    """The learning loop's codes force the exits ADR 0021 gives them."""

    EXPECTED = {
        report.EXIT_BLOCKED: ("PATCH_NAME_INVALID", "PATCH_UNREADABLE", "PATCH_FIELD_MISSING", "PATCH_FIELD_INVALID",
                              "PATCH_SECTION_INVALID", "OVERRIDE_UNREADABLE", "OVERRIDE_SHAPE",
                              "OVERRIDE_SOURCE_MISSING", "OVERRIDE_FORBIDDEN"),
        report.EXIT_WARNINGS: ("PATCH_CURSOR_UNREADABLE", "OVERRIDE_TOUCHES_LIMIT"),
    }

    def test_every_learning_code_has_its_exit(self):
        for exit_code, codes in self.EXPECTED.items():
            for code in codes:
                self.assertEqual(report.CODES.get(code), exit_code, code)


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

    def test_a_finding_with_control_characters_renders_as_one_line(self):
        rep = report.Report("app/FM/a\nERROR FAKE x.json")
        rep.add("UNKNOWN_PROPERTY", "key `a\nCLEAN`\r \x1b[31mred\x7f \x85     end", line=2)
        buf = io.StringIO()
        report.render([rep], buf, lines=["PLAN: p\nCLEAN"])
        rendered = [line for line in buf.getvalue().splitlines() if line.startswith("WARN ")]
        self.assertEqual(rendered, ["WARN UNKNOWN_PROPERTY app/FM/a\\x0aERROR FAKE x.json:2 key `a\\x0aCLEAN`\\x0d "
                                    "\\x1b[31mred\\x7f \\x85 \\u2028 \\u2029 end"])
        self.assertIn("PLAN: p\\x0aCLEAN", buf.getvalue().splitlines())
        self.assertEqual(buf.getvalue().splitlines().count("CLEAN"), 0)  # the verdict is WARNINGS; nothing forged it

    def test_a_not_run_reason_renders_as_one_line(self):
        rep = report.Report("f.json", "json")
        rep.skipped("plan-overlap", "git failed: a\nb")
        buf = io.StringIO()
        report.render([rep], buf)
        self.assertIn("NOT RUN: plan-overlap (git failed: a\\x0ab)", buf.getvalue().splitlines())

    def test_plain_and_non_ascii_text_is_unchanged(self):
        for text in ("`x` is ignored by the runtime", "Ünïcødé — naïve café", "tab nbsp"):
            with self.subTest(text):
                self.assertEqual(report.one_line(text), text)
        self.assertEqual(report.one_line("a\tb"), "a\\x09b")

    def test_usage_error_renders_blocked(self):
        rep = report.Report("f.txt")
        rep.add("FAMILY_UNRESOLVED", "neither")
        buf = io.StringIO()
        self.assertEqual(report.render([rep], buf), 3)
        self.assertEqual(buf.getvalue().splitlines()[-1], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
