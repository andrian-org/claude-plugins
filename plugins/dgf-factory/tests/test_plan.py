"""The plan parser and path classes in scripts/lib/plan.py (ADR 0017 §1–§3)."""

import unittest

from tests import helpers
from lib import plan

PLANS = helpers.FIXTURES / "unit" / "plans"


def header(*lines):
    return plan.parse_header(["---", *lines, "---"])[0]


class Header(unittest.TestCase):
    def test_scalars_lists_and_comments(self):
        got = header("plan_format: 1", "mode: full   # a comment", 'reason: "a: b # not a comment"',
                     "affects_workspaces: [zims, \"webasm\"]", "", "# a whole-line comment")
        self.assertEqual(got, {"plan_format": "1", "mode": "full", "reason": "a: b # not a comment",
                               "affects_workspaces": ["zims", "webasm"]})

    def test_escapes_in_a_quoted_value(self):
        self.assertEqual(header(r'reason: "say \"no\" \\ twice"')["reason"], 'say "no" \\ twice')

    def test_an_empty_list_and_an_empty_value(self):
        got = header("affects_workspaces: []", "base_workspace_reason:")
        self.assertEqual(got, {"affects_workspaces": [], "base_workspace_reason": None})

    def test_a_hash_inside_a_bare_word_is_kept(self):
        self.assertEqual(header("branch: feature/c#-fix")["branch"], "feature/c#-fix")

    def test_line_numbers_are_recorded(self):
        _, where, start = plan.parse_header(["---", "mode: full", "", "branch: x", "---", "body"])
        self.assertEqual(where, {"mode": 2, "branch": 4})
        self.assertEqual(start, 5)

    def assert_unreadable(self, lines, fragment, line=None):
        with self.assertRaises(plan.PlanFormatError) as ctx:
            plan.parse_header(lines)
        self.assertIn(fragment, str(ctx.exception))
        if line is not None:
            self.assertEqual(ctx.exception.line, line)

    def test_no_frontmatter(self):
        self.assert_unreadable(["# Implementation Plan"], "first line must be `---`", 1)

    def test_frontmatter_never_closes(self):
        self.assert_unreadable(["---", "mode: full"], "never closes")

    def test_a_nested_map_is_outside_the_subset(self):
        self.assert_unreadable(["---", "paths:", "  plans: x", "---"], "not a flat `key: value` line", 3)

    def test_a_block_list_is_outside_the_subset(self):
        self.assert_unreadable(["---", "affects_workspaces:", "- zims", "---"], "not a flat", 3)

    def test_an_unquoted_colon_is_outside_the_subset(self):
        self.assert_unreadable(["---", "base_workspace_reason: shared: by all", "---"], "contains `: `", 2)

    def test_single_quotes_and_flow_maps_are_outside_the_subset(self):
        self.assert_unreadable(["---", "mode: 'full'", "---"], "outside the flat subset", 2)
        self.assert_unreadable(["---", "mode: {a: 1}", "---"], "outside the flat subset", 2)

    def test_quoted_list_items_may_hold_commas_and_brackets(self):
        self.assertEqual(header('affects_workspaces: ["a, b", "c]", d]  # note')["affects_workspaces"],
                         ["a, b", "c]", "d"])
        self.assert_unreadable(["---", "affects_workspaces: [a, ]", "---"], "outside the flat subset", 2)
        self.assert_unreadable(["---", "affects_workspaces: [a, b", "---"], "never closes", 2)

    def test_a_nested_list_is_outside_the_subset(self):
        self.assert_unreadable(["---", "affects_workspaces: [[zims]]", "---"], "nested list", 2)

    def test_a_duplicate_key(self):
        self.assert_unreadable(["---", "mode: full", "mode: fast", "---"], "given twice", 3)

    def test_an_unterminated_quote(self):
        self.assert_unreadable(["---", 'reason: "open', "---"], "never closes", 2)


class Plans(unittest.TestCase):
    def test_a_full_plan(self):
        parsed = plan.parse(PLANS / "feature-zims-inspection-fee.md")
        self.assertEqual(parsed.mode, "full")
        self.assertEqual(parsed.header["affects_workspaces"], ["zims", "webasm"])
        self.assertTrue(parsed.tasks_section)
        self.assertEqual([t.id for t in parsed.tasks], [1, 2, 3])
        self.assertEqual(parsed.progress(), (1, 3))

    def test_task_fields_and_state(self):
        one, two, three = plan.parse(PLANS / "feature-zims-inspection-fee.md").tasks
        self.assertTrue(one.checked)
        self.assertEqual((one.kind, one.reason), ("config", None))
        self.assertEqual(one.files, ["webasm/FM/_COMPONENTS/DataSource/InspectionFee.json"])
        self.assertEqual(two.title, "Show the fee on the application form")
        self.assertEqual(two.depends, [1])
        self.assertEqual(two.files, ["zims/FM/_DATA/Inspection/_forms/Apply/_form.xml"])  # backticks removed
        self.assertEqual(three.depends, [1, 2])
        self.assertEqual(three.kind, "code")
        self.assertIn("EventBase", three.reason)
        self.assertEqual(three.deletes, ["zims/js/legacy-fee.js"])
        self.assertEqual(three.fields["files"][1], three.line + 3)

    def test_a_task_inside_a_code_fence_is_not_read(self):
        ids = [t.id for t in plan.parse(PLANS / "feature-zims-inspection-fee.md").tasks]
        self.assertNotIn(99, ids)

    def test_a_fast_plan(self):
        parsed = plan.parse(PLANS / "PLAN.md")
        self.assertEqual((parsed.mode, parsed.header["branch"]), ("fast", "none"))
        self.assertEqual(parsed.tasks[0].files, ["dgf/FM/_DATA/Contact/_forms/default/_form.xml"])

    def test_an_ultra_bundle(self):
        parsed = plan.parse(PLANS / "feature-zims-inspection-fee-ultra" / "index.md")
        self.assertEqual(parsed.mode, "ultra")
        self.assertEqual([target for target, _ in parsed.phase_links], ["phase-1.md"])
        task = parsed.tasks[0]
        self.assertEqual(task.title, "Add the inspection-fee DataSource")
        self.assertEqual(task.links, ["phase-1.md#task-1"])

    def test_no_tasks_section(self):
        parsed = plan.parse_text("---\nmode: fast\n---\n# Plan\n\n## Risks\n- [ ] Task 1: not under Tasks\n")
        self.assertFalse(parsed.tasks_section)
        self.assertEqual(parsed.tasks, [])

    def test_a_duplicate_field_is_recorded(self):
        parsed = plan.parse_text("---\nmode: fast\n---\n## Tasks\n- [ ] Task 1: x\n  - kind: config\n"
                                 "  - kind: code\n  - files: a/FM/b.json\n")
        self.assertEqual(parsed.tasks[0].kind, "config")
        self.assertEqual(parsed.tasks[0].duplicates, ["kind"])

    def test_fields_stop_at_the_next_unindented_line(self):
        parsed = plan.parse_text("---\nmode: fast\n---\n## Tasks\n- [ ] Task 1: x\n### Phase 2\n"
                                 "  - kind: code\n")
        self.assertIsNone(parsed.tasks[0].kind)

    def test_a_bundle_directory_reads_its_index(self):
        bundle = PLANS / "feature-zims-inspection-fee-ultra"
        self.assertEqual(plan.entrypoint(bundle), bundle / "index.md")
        self.assertEqual(plan.parse(bundle).mode, "ultra")

    def test_an_unreadable_file(self):
        with self.assertRaises(plan.PlanFormatError):
            plan.parse(PLANS / "no-such-plan.md")


class Classes(unittest.TestCase):
    CASES = {
        "zims/FM/_COMPONENTS/DataSource/Fee.json": "config",
        "zims/FM/_PROCESS/Apply/process.xml": "config",
        "zims/FM/_DATA/Inspection/_forms/Apply/_form.xml": "config",
        "zims/FM/_DATA/Inspection/_forms/Apply/_form.js": "code",
        "webasm/FM/_DATA/PWF/_forms/ASP.Net/Resources/designer.aspx/_form.js": "code",  # a form name with `/`
        "zims/js/formhelper.js": "code",
        "zims/js/vendor/lib.js": "code",
        "webasm/FM/js/formhelper.js": "code",
        "zims/css/custom.css": "code",
        "applibs-zims/Zims.Plugin.dll": "excluded",
        "applibs-zims/readme.md": "excluded",
        "zims/FM/_DATA/T/Handler.cs": "excluded",
        "zims/src/app.component.ts": "excluded",
        "zims/FM/_DATA/T/query.sql": "excluded",
        "zims/FM/_DATA/T/_forms/F/other.js": "other",
        "zims/FM/_DATA/T/_forms/_form.js": "other",  # no form folder
        "zims/images/banner.jpg": "other",
        "zims/FM/_COMPONENTS/Template/t.html": "excluded",
        "zims/css/print.scss": "other",
        "zims/JS/formhelper.js": "other",  # the folder is exact-case
        "README.md": "other",
    }

    def test_each_path_has_one_class(self):
        for path, expected in self.CASES.items():
            self.assertEqual(plan.classify(path), expected, path)

    def test_code_place_names_the_row(self):
        self.assertEqual(plan.code_place("zims/FM/_DATA/T/_forms/F/_form.js")["Place"], "form-script")
        self.assertEqual(plan.code_place("webasm/FM/js/formhelper.js")["Place"], "global-script-base")
        self.assertEqual(plan.code_place("zims/css/custom.css")["New file loaded"], "no")
        self.assertIsNone(plan.code_place("zims/FM/_COMPONENTS/Page/p.json"))

    def test_workspace_and_pipeline_paths(self):
        self.assertEqual(plan.workspace_of("zims/FM/x.xml"), "zims")
        self.assertTrue(plan.is_pipeline(".dgf-factory/plans/feature-x.md"))
        self.assertTrue(plan.is_plugin_assembly_folder("applibs-zims"))
        self.assertFalse(plan.is_plugin_assembly_folder("zims"))

    def test_split_paths(self):
        self.assertEqual(plan.split_paths(" `a/FM/b.json`, ./c/js/d.js ,"), ["a/FM/b.json", "c/js/d.js"])
        self.assertEqual(plan.split_paths(None), [])


class PathProblems(unittest.TestCase):
    BAD = {
        "webasm/FM/../../x.json": "climbs out with `..`",
        "..": "climbs out with `..`",
        "/zims/FM/x.json": "is absolute",
        "\\zims\\FM\\x.json": "is absolute",
        "C:/zims/FM/x.json": "names a drive",
        "c:zims/FM/x.json": "names a drive",
        "zims/FM\\x.json": "uses `\\`",
        "zims/FM/": "ends with `/`",
        "zims/./FM/x.json": "has a `.` segment",
        "./zims/FM/x.json": "has a `.` segment",  # split_paths strips one `./` before this is asked
        "zims//FM/x.json": "has an empty segment",
    }
    GOOD = ("zims/FM/x.json", "zims/FM/_DATA/a..b.json", "zims/FM/_DATA/.hidden/x.json",
            "webasm/FM/_DATA/PWF/_forms/ASP.Net/Resources/designer.aspx/_form.js")

    def test_each_bad_path_names_its_problem(self):
        for path, why in self.BAD.items():
            with self.subTest(path):
                self.assertEqual(plan.path_problem(path), why)

    def test_plain_root_relative_paths_have_none(self):
        for path in self.GOOD:
            with self.subTest(path):
                self.assertIsNone(plan.path_problem(path))


if __name__ == "__main__":
    unittest.main()
