"""The plan parser and path classes in scripts/lib/plan.py (ADR 0017 §1–§3)."""

import unittest

from tests import helpers
from lib import knowledge, plan

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



def commit_plan(*lines, mode="full"):
    """A plan whose `## Commit Plan` holds `lines`, followed by one task."""
    body = "\n".join(lines)
    return plan.parse_text(f"---\nmode: {mode}\n---\n# Plan\n\n## Commit Plan\n\n{body}\n\n## Tasks\n\n"
                           "- [ ] Task 1: x\n  - kind: config\n  - files: a/FM/b.json\n")


class CommitPlan(unittest.TestCase):
    def test_the_line_shapes_a_plan_writes(self):
        parsed = commit_plan("- **Commit 1** (after tasks 1–3): `feat(zims): show the fee`",
                             "- **Commit 2** (after tasks 4-6): `fix: hyphen`",
                             "- **Commit 3** (after task 7): `docs: one task`",
                             "- **Commit 4** (after tasks 8 – 9): `chore: spaces round the dash`",
                             '- **Commit 5** (after tasks 10-11): "feat: a double-quoted message"')
        self.assertTrue(parsed.commit_section)
        got = [(c.number, c.first, c.last, c.message) for c in parsed.commits]
        self.assertEqual(got, [(1, 1, 3, "feat(zims): show the fee"), (2, 4, 6, "fix: hyphen"),
                               (3, 7, 7, "docs: one task"), (4, 8, 9, "chore: spaces round the dash"),
                               (5, 10, 11, "feat: a double-quoted message")])
        self.assertEqual(parsed.commits[0].line, 8)
        self.assertEqual(parsed.tasks[0].id, 1)

    def test_a_wrong_shaped_bullet_is_kept_without_a_number_and_never_raises(self):
        for bad in ("- Commit 1 after tasks 1-3: feat: x", "- **Commit 1** (after tasks 1-3): no quotes",
                    "- **Commit one** (after tasks 1-3): `x`", "- **Commit 1** (after tasks 1-3): `x` trailing",
                    "- **Commit 1** (tasks 1-3): `x`", "- **Commit 1** (after tasks 1-3): `unclosed",
                    "- **Commit " + "9" * 5000 + "** (after tasks 1-3): `a number int() refuses`",
                    "- **Commit 1** (after tasks 1-" + "9" * 5000 + "): `x`"):
            with self.subTest(bad=bad):
                parsed = commit_plan(bad)
                self.assertEqual(len(parsed.commits), 1)
                commit = parsed.commits[0]
                self.assertIsNone(commit.number)
                self.assertEqual((commit.text, commit.line), (bad, 8))

    def test_a_task_or_dependency_number_too_long_for_int_is_unreadable_at_its_line(self):
        for line in ("- [ ] Task " + "9" * 5000 + ": x", "- [ ] Task 2: x (depends on " + "9" * 5000 + ")"):
            with self.subTest(line=line[:30]):
                with self.assertRaises(plan.PlanFormatError) as caught:
                    plan.parse_text(f"---\nmode: fast\n---\n## Tasks\n\n{line}\n")
                self.assertEqual(caught.exception.line, 6)
                self.assertIn("more than 9 digits", caught.exception.message)
        self.assertEqual(plan.parse_text("---\nmode: fast\n---\n## Tasks\n\n- [ ] Task 123456789: x\n").tasks[0].id,
                         123456789)

    def test_a_placeholder_and_prose_are_ignored(self):
        parsed = commit_plan("<only when there are 5 or more tasks>", "Groups follow the phases.",
                             "  - an indented note")
        self.assertTrue(parsed.commit_section)
        self.assertEqual(parsed.commits, [])

    def test_a_bullet_inside_a_fence_is_ignored(self):
        parsed = commit_plan("```markdown", "- **Commit 1** (after tasks 1-2): `x`", "```",
                             "- **Commit 1** (after task 1): `real`")
        self.assertEqual([(c.number, c.message) for c in parsed.commits], [(1, "real")])

    def test_no_section(self):
        parsed = plan.parse(PLANS / "feature-zims-inspection-fee.md")
        self.assertFalse(parsed.commit_section)
        self.assertEqual(parsed.commits, [])

    def test_bullets_under_another_heading_are_not_commits(self):
        parsed = plan.parse_text("---\nmode: fast\n---\n## Risks\n- **Commit 1** (after task 1): `x`\n")
        self.assertFalse(parsed.commit_section)
        self.assertEqual(parsed.commits, [])

    def test_an_ultra_index_is_parsed_the_same_way(self):
        parsed = commit_plan("- **Commit 1** (after tasks 1–2): `feat: fee data`", mode="ultra")
        self.assertEqual(parsed.mode, "ultra")
        self.assertEqual([(c.number, c.first, c.last) for c in parsed.commits], [(1, 1, 2)])

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



class Artifacts(unittest.TestCase):
    """plan.artifact(): which artifact a root-relative path is, and its name (ADR 0022 §6)."""

    def test_each_legacy_artifacts_row(self):
        cases = {
            "zims/FM/_PROCESS/Apply/process.xml": ("process", "Apply"),
            "zims/FM/_WORKFLOW/Expert.MoveTaskTo/_workflow.xml": ("workflow", "Expert.MoveTaskTo"),
            "zims/FM/_DATA/Cases/_forms/Apply/_form.xml": ("form", "Cases/Apply"),
            "zims/FM/_DATA/Cases/settings.xml": ("settings", "Cases"),
            "zims/FM/_DATA/Cases/_views/Open/_view.xml": ("table-view", "Cases/Open"),
            "zims/FM/_DATA/Cases/_lookupviews/Pick/_view.xml": ("lookup-view", "Cases/Pick"),
            "zims/FM/_DATA/Cases/_gridforms/Lines/_grid.xml": ("grid-form", "Cases/Lines"),
            "zims/FM/_DATA/Cases/_options.xml": ("options", "Cases"),
        }
        self.assertEqual({row["Artifact"] for row in knowledge.load("legacy-artifacts")},
                         {artifact for artifact, _ in cases.values()})
        for rel, expected in cases.items():
            with self.subTest(rel):
                self.assertEqual(plan.artifact(rel), expected)

    def test_components(self):
        self.assertEqual(plan.artifact("zims/FM/_COMPONENTS/Button/ApplyNow.json"), ("component", "Button/ApplyNow"))
        self.assertEqual(plan.artifact("webasm/FM/_COMPONENTS/Page/SiteMap/loginPage.json"),
                         ("component", "Page/SiteMap/loginPage"))
        self.assertEqual(plan.artifact("zims/FM/_COMPONENTS/sitemap.json"), ("component", "sitemap"))

    def test_a_process_local_workflow(self):
        self.assertEqual(plan.artifact("zims/FM/_PROCESS/Apply/Review/_workflow.xml"),
                         ("process-workflow", "Apply/Review"))

    def test_a_form_whose_name_holds_a_slash(self):
        self.assertEqual(plan.artifact("zims/FM/_DATA/Cases/_forms/Apply/Step1/_form.xml"),
                         ("form", "Cases/Apply/Step1"))

    def test_a_config_file_of_no_known_shape(self):
        for rel in ("zims/FM/_DATA/Cases/_forms/Apply/extra.xml", "zims/FM/_COMPONENTS/Button/old.xml",
                    "zims/FM/_PROCESS/Apply/notes.xml", "zims/FM/settings.xml"):
            with self.subTest(rel):
                self.assertIsNone(plan.artifact(rel))

    def test_artifact_inside_takes_the_segments_inside_the_workspace(self):
        self.assertEqual(plan.artifact_inside(["FM", "_PROCESS", "Case", "process.xml"]), ("process", "Case"))
        self.assertIsNone(plan.artifact_inside([]))

    def test_placeholder_values(self):
        pattern = plan.segments("FM/_DATA/<table>/_forms/<form>/")
        self.assertEqual(plan.placeholder_values(pattern, ["FM", "_DATA", "Cases", "_forms", "A", "B"]),
                         ["Cases", "A/B"])

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
