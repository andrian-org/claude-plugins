"""scripts/lib/patches.py: the patch format and the cursor (ADR 0024 §1, §6)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers  # noqa: F401 — puts scripts/ on sys.path
from lib import patches, report

NAME = "2026-09-26-14.30-review-moves-to-undeclared-state.md"
EXAMPLE = """# `Review` moves to a state the process never declares

- date: 2026-09-26 14:30
- plan: .dgf-factory/plans/feature-zims-fee.md
- workspaces: zims
- files: zims/FM/_PROCESS/Apply/process.xml
- findings: DEAD_TRANSITION
- dgf_version: 1.1.15
- severity: high

## Problem
The gate blocked the branch: `Review` moved to `Archive`, which is neither a declared state nor `End`.

## Root Cause
The state was renamed `Archived` in the process, but the transition kept the old name.

## Solution
The transition now names `Archived`.

## Prevention
A task that renames a state lists every file with a transition to it.

## Tags
#process #transition #rename
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def parse(self, text=EXAMPLE, name=NAME):
        path = self.tmp / name
        path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)
        rep = report.Report(name)
        return patches.parse(path, name, rep), rep

    def codes(self, text=EXAMPLE, name=NAME):
        return [f.code for f in self.parse(text, name)[1].findings]

    def assertOnly(self, code, text=EXAMPLE, name=NAME, contains=None):
        found = self.parse(text, name)[1].findings
        self.assertEqual([f.code for f in found], [code], [f.render() for f in found])
        if contains:
            self.assertIn(contains, found[0].message)
        return found[0]


class Example(Base):
    def test_the_design_example_is_clean(self):
        patch, rep = self.parse()
        self.assertEqual(rep.findings, [])
        self.assertEqual(patch.title, "`Review` moves to a state the process never declares")
        self.assertEqual(patch.value("severity"), "high")
        self.assertEqual(patch.codes(), ["DEAD_TRANSITION"])
        self.assertEqual(list(patch.sections), list(patches.SECTIONS))
        self.assertTrue(patch.sections["Root Cause"].startswith("The state was renamed"))

    def test_none_values_are_clean(self):
        text = (EXAMPLE.replace("- plan: .dgf-factory/plans/feature-zims-fee.md", "- plan: none")
                .replace("- workspaces: zims", "- workspaces: none")
                .replace("- files: zims/FM/_PROCESS/Apply/process.xml", "- files: none")
                .replace("- findings: DEAD_TRANSITION", "- findings: none")
                .replace("- dgf_version: 1.1.15", "- dgf_version: unknown"))
        patch, rep = self.parse(text)
        self.assertEqual(rep.findings, [])
        self.assertEqual(patch.codes(), [])

    def test_fields_in_any_order_and_lists_with_spaces(self):
        text = EXAMPLE.replace("- workspaces: zims\n- files: zims/FM/_PROCESS/Apply/process.xml\n", "").replace(
            "- severity: high", "- severity: high\n- files: zims/a.xml, other/b.json\n- workspaces: zims, other")
        self.assertEqual(self.codes(text), [])


class Name(Base):
    def test_a_name_without_a_slug(self):
        self.assertOnly("PATCH_NAME_INVALID", EXAMPLE, "2026-09-26-14.30.md")

    def test_an_uppercase_slug(self):
        self.assertOnly("PATCH_NAME_INVALID", EXAMPLE, "2026-09-26-14.30-Review.md")

    def test_a_slug_over_fifty_characters(self):
        self.assertOnly("PATCH_NAME_INVALID", EXAMPLE, "2026-09-26-14.30-" + "a" * 51 + ".md", contains="51")
        self.assertEqual(self.codes(EXAMPLE, "2026-09-26-14.30-" + "a" * 50 + ".md"), [])

    def test_a_timestamp_that_is_not_a_date(self):
        text = EXAMPLE.replace("2026-09-26 14:30", "2026-02-30 14:30")
        codes = self.codes(text, "2026-02-30-14.30-x.md")
        self.assertEqual(codes, ["PATCH_NAME_INVALID", "PATCH_FIELD_INVALID"])


class Title(Base):
    def test_a_missing_title(self):
        self.assertOnly("PATCH_FIELD_MISSING", EXAMPLE.split("\n", 1)[1], contains="# <title>")

    def test_a_title_over_the_limit(self):
        self.assertOnly("PATCH_FIELD_MISSING", "# " + "x" * 121 + EXAMPLE[EXAMPLE.index("\n"):], contains="121")


class Fields(Base):
    def replaced(self, old, new):
        return EXAMPLE.replace(old, new)

    def test_each_missing_field(self):
        for key in patches.FIELDS:
            line = next(l for l in EXAMPLE.splitlines() if l.startswith(f"- {key}:"))
            with self.subTest(key=key):
                text = EXAMPLE.replace(line + "\n", "")
                if key == "workspaces":  # files then names a workspace nobody listed — only the missing key
                    text = text.replace("- files: zims/FM/_PROCESS/Apply/process.xml", "- files: none")
                self.assertOnly("PATCH_FIELD_MISSING", text, contains=f"`- {key}:`")

    def test_an_unknown_key(self):
        self.assertOnly("PATCH_FIELD_INVALID", self.replaced("- severity: high", "- severity: high\n- owner: me"),
                        contains="`owner`")

    def test_a_repeated_key(self):
        self.assertOnly("PATCH_FIELD_INVALID", self.replaced("- severity: high", "- severity: high\n- severity: low"),
                        contains="twice")

    def test_a_stray_line_before_the_sections(self):
        self.assertOnly("PATCH_FIELD_INVALID", self.replaced("- severity: high", "- severity: high\nfree text"))

    def test_an_empty_value(self):
        self.assertOnly("PATCH_FIELD_INVALID", self.replaced("- severity: high", "- severity:"), contains="empty")

    def test_bad_values(self):
        cases = {
            "- date: 2026-09-26 14:30": ["- date: 2026-09-26", "- date: 2026-09-26 25:30"],
            "- plan: .dgf-factory/plans/feature-zims-fee.md": ["- plan: zims/plan.md", "- plan: .dgf-factory",
                                                               "- plan: .dgf-factory/../x.md", "- plan: /tmp/x.md"],
            "- workspaces: zims": ["- workspaces: zims/FM", "- workspaces: applibs", "- workspaces: .dgf-factory",
                                   "- workspaces: zims, "],
            "- files: zims/FM/_PROCESS/Apply/process.xml": ["- files: other/a.xml", "- files: zims/../x.xml",
                                                           "- files: /zims/a.xml"],
            "- findings: DEAD_TRANSITION": ["- findings: NOT_A_CODE", "- findings: DEAD_TRANSITION, nope"],
            "- dgf_version: 1.1.15": ["- dgf_version: 1.1", "- dgf_version: latest"],
            "- severity: high": ["- severity: High", "- severity: urgent"],
        }
        for old, news in cases.items():
            for new in news:
                with self.subTest(value=new):
                    self.assertOnly("PATCH_FIELD_INVALID", self.replaced(old, new), contains=new.split(":")[0][2:])

    def test_a_date_that_disagrees_with_the_name(self):
        self.assertOnly("PATCH_FIELD_INVALID", self.replaced("- date: 2026-09-26 14:30", "- date: 2026-09-26 14:31"),
                        contains="2026-09-26 14:30")

    def test_files_set_while_workspaces_is_none(self):
        found = self.assertOnly("PATCH_FIELD_INVALID", self.replaced("- workspaces: zims", "- workspaces: none"),
                                contains="`workspaces` is `none`")
        self.assertIn("`files`", found.message)

    def test_an_unknown_finding_code_is_named(self):
        self.assertOnly("PATCH_FIELD_INVALID", self.replaced("DEAD_TRANSITION", "DEAD_TRANSITION, NOPE"),
                        contains="`NOPE`")

    def test_the_finding_is_at_the_field_line(self):
        found = self.assertOnly("PATCH_FIELD_INVALID", self.replaced("- severity: high", "- severity: urgent"))
        self.assertEqual(found.line, 9)


class Sections(Base):
    def test_a_missing_section(self):
        self.assertOnly("PATCH_SECTION_INVALID", EXAMPLE.replace("## Solution\nThe transition now names `Archived`.\n\n",
                                                                 ""), contains="no `## Solution`")

    def test_an_empty_section(self):
        found = self.assertOnly("PATCH_SECTION_INVALID",
                                EXAMPLE.replace("A task that renames a state lists every file with a transition to it.",
                                                "  "), contains="empty")
        self.assertEqual(found.line, 20)

    def test_a_repeated_section(self):
        self.assertOnly("PATCH_SECTION_INVALID", EXAMPLE + "\n## Problem\nagain\n", contains="repeated")

    def test_an_unknown_section(self):
        self.assertOnly("PATCH_SECTION_INVALID", EXAMPLE.replace("## Tags", "## Notes\nx\n\n## Tags"),
                        contains="`## Notes`")

    def test_sections_out_of_order(self):
        text = EXAMPLE.replace("## Solution\nThe transition now names `Archived`.\n\n", "").replace(
            "## Tags", "## Solution\nThe transition now names `Archived`.\n\n## Tags")
        self.assertOnly("PATCH_SECTION_INVALID", text, contains="out of order")

    def test_a_heading_inside_a_fence_is_text(self):
        text = EXAMPLE.replace("The transition now names `Archived`.",
                               "The transition now names `Archived`:\n\n```markdown\n## Problem\n```")
        patch, rep = self.parse(text)
        self.assertEqual(rep.findings, [])
        self.assertIn("## Problem", patch.sections["Solution"])

    def test_a_bad_tag(self):
        self.assertOnly("PATCH_SECTION_INVALID", EXAMPLE.replace("#rename", "#Rename rename"),
                        contains="`#Rename`, `rename`")


class Unreadable(Base):
    def test_invalid_utf8_is_unreadable_and_nothing_more(self):
        patch, rep = self.parse(b"# t\n\xff\xfe\n")
        self.assertIsNone(patch)
        self.assertEqual([f.code for f in rep.findings], ["PATCH_UNREADABLE"])

    def test_a_leading_bom_is_accepted(self):
        patch, rep = self.parse(("\ufeff" + EXAMPLE).encode("utf-8"))
        self.assertEqual(rep.findings, [])
        self.assertEqual(patch.title, "`Review` moves to a state the process never declares")

    def test_a_patch_over_the_size_limit_is_unreadable(self):
        patch, rep = self.parse(EXAMPLE + "x" * patches.MAX_BYTES)
        self.assertIsNone(patch)
        self.assertEqual([f.code for f in rep.findings], ["PATCH_UNREADABLE"])

    def test_a_patch_that_is_not_a_regular_file_is_unreadable(self):
        path = self.tmp / NAME
        path.symlink_to("/dev/zero")
        rep = report.Report(NAME)
        self.assertIsNone(patches.parse(path, NAME, rep))
        self.assertEqual([f.code for f in rep.findings], ["PATCH_UNREADABLE"])

    def test_a_bad_name_is_still_reported_with_unreadable(self):
        self.assertEqual(self.codes(b"\xff", "x.md"), ["PATCH_NAME_INVALID", "PATCH_UNREADABLE"])


class Cursor(Base):
    def write(self, value):
        path = self.tmp / "patch-cursor.json"
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
        return path

    def test_a_missing_cursor_is_nothing_processed(self):
        self.assertEqual(patches.read_cursor(self.tmp / "absent.json"), (set(), None))

    def test_a_valid_cursor(self):
        path = self.write({"processed": [NAME, "2026-09-25-09.00-x.md"], "updated": "2026-09-26 15:00"})
        self.assertEqual(patches.read_cursor(path), ({NAME, "2026-09-25-09.00-x.md"}, None))

    def test_a_cursor_that_is_not_an_object(self):
        processed, why = patches.read_cursor(self.write([NAME]))
        self.assertIsNone(processed)
        self.assertIn("object", why)

    def test_a_list_of_numbers(self):
        processed, why = patches.read_cursor(self.write({"processed": [1, 2], "updated": "x"}))
        self.assertIsNone(processed)
        self.assertIn("processed", why)

    def test_a_deeply_nested_cursor_is_unreadable_not_a_crash(self):
        processed, why = patches.read_cursor(self.write("[" * 200000))
        self.assertIsNone(processed)
        self.assertIn("JSON", why)

    def test_a_cursor_that_is_not_a_regular_file_is_unreadable(self):
        path = self.tmp / "patch-cursor.json"
        path.symlink_to("/dev/zero")
        processed, why = patches.read_cursor(path)
        self.assertIsNone(processed)
        self.assertIn("regular file", why)

    def test_invalid_json_and_a_missing_updated(self):
        self.assertIsNone(patches.read_cursor(self.write("{"))[0])
        self.assertIsNone(patches.read_cursor(self.write({"processed": []}))[0])


if __name__ == "__main__":
    unittest.main()
