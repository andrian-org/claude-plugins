"""check_plan.py: the plan header, tasks, files, routes and overlap checks (ADR 0017)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
import check_plan

ROOT_FILES = {
    "zims/FM/_DATA/Inspection/_forms/Apply/_form.xml": "<form/>\n",
    "zims/FM/_COMPONENTS/Workflow/old.json": '{"type": "Workflow"}\n',
    "zims/js/formhelper.js": "// helper\n",
    "zims/css/custom.css": "body {}\n",
    "webasm/FM/_COMPONENTS/.keep": "",
    "applibs-zims/Zims.Plugin.dll": b"MZ",
}
HEADER = ["plan_format: 1", "mode: full", "branch: feature/x", "created: 2026-09-25", "affects_workspaces: [zims]"]
FORM = "zims/FM/_DATA/Inspection/_forms/Apply/_form.xml"


def task(number, kind="config", files=FORM, extra=(), checked=False, suffix=""):
    lines = [f"- [{'x' if checked else ' '}] Task {number}: task {number}{suffix}"]
    if kind is not None:
        lines.append(f"  - kind: {kind}")
    lines += [f"  - {line}" for line in extra]
    if files is not None:
        lines.append(f"  - files: {files}")
    return "\n".join(lines)


def plan_text(header=HEADER, tasks=None, body=""):
    tasks = [task(1)] if tasks is None else tasks
    return "---\n" + "\n".join(header) + "\n---\n\n# Implementation Plan: x\n\n" + body + \
           "## Tasks\n\n" + "\n".join(tasks) + "\n\n## Risks\n\n- none\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "root", ROOT_FILES)

    def write(self, text, name="feature-x.md"):
        path = self.root / ".dgf-factory" / "plans" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def codes(self, text=None, path=None, overlap=False, **kw):
        path = path or self.write(text if text is not None else plan_text(**kw))
        rep, lines = check_plan.check(path, self.root, overlap)
        self.lines = lines
        self.rep = rep
        return [f.code for f in rep.findings]

    def message(self, code):
        return next(f.message for f in self.rep.findings if f.code == code)


class Header(Base):
    def test_a_sound_plan_is_clean(self):
        self.assertEqual(self.codes(), [])
        self.assertIn("PROGRESS: 0/1", self.lines)
        self.assertIn("AFFECTS: zims", self.lines)

    def test_unreadable_and_unsupported(self):
        self.assertEqual(self.codes("# no frontmatter\n"), ["PLAN_UNREADABLE"])
        self.assertEqual(self.codes(header=["plan_format: 2"] + HEADER[1:]), ["PLAN_FORMAT_UNSUPPORTED"])

    def test_missing_fields(self):
        self.assertEqual(self.codes(header=HEADER[:3] + HEADER[4:]), ["PLAN_FIELD_MISSING"])
        # An empty list also leaves every task's file in an undeclared workspace.
        self.assertEqual(self.codes(header=HEADER[:4] + ["affects_workspaces: []"]),
                         ["PLAN_FIELD_MISSING", "PLAN_FILE_UNDECLARED_WORKSPACE"])

    def test_invalid_fields(self):
        for bad in (["owner: someone"], ["mode: quick"], ["created: 2026-13-40"], ["branch: none"],
                    ["mode: [full]"], ["affects_workspaces: zims"], ["affects_workspaces: [zims, zims]"]):
            key = bad[0].split(":")[0]
            header = [line for line in HEADER if not line.startswith(key + ":")] + bad
            with self.subTest(bad=bad):
                self.assertIn("PLAN_FIELD_INVALID", self.codes(header=header))

    def test_archived_is_accepted(self):
        self.assertEqual(self.codes(header=HEADER + ["archived: 2026-10-01"]), [])

    def test_an_applibs_folder_is_not_a_workspace(self):
        codes = self.codes(header=HEADER[:4] + ["affects_workspaces: [zims, applibs-zims]"])
        self.assertEqual(codes, ["PLAN_UNKNOWN_WORKSPACE"])
        self.assertIn("plugin-assembly folder", self.message("PLAN_UNKNOWN_WORKSPACE"))

    def test_an_unknown_workspace(self):
        self.assertEqual(self.codes(header=HEADER[:4] + ["affects_workspaces: [zims, nope]"]), ["PLAN_UNKNOWN_WORKSPACE"])

    def test_webasm_absent_from_the_root(self):
        shutil.rmtree(self.root / "webasm")
        codes = self.codes(header=HEADER[:4] + ["affects_workspaces: [zims, webasm]", 'base_workspace_reason: "x"'])
        self.assertEqual(codes, ["PLAN_UNKNOWN_WORKSPACE"])
        self.assertIn("BASE_WORKSPACE_ABSENT", self.message("PLAN_UNKNOWN_WORKSPACE"))

    def test_webasm_needs_a_reason(self):
        header = HEADER[:4] + ["affects_workspaces: [zims, webasm]"]
        self.assertEqual(self.codes(header=header), ["PLAN_BASE_REASON_MISSING"])
        self.assertEqual(self.codes(header=header + ['base_workspace_reason: "shared fee"']), [])

    def test_the_stem_is_the_branch(self):
        path = self.write(plan_text(), name="feature-y.md")
        self.assertEqual(self.codes(path=path), ["PLAN_BRANCH_MISMATCH"])

    def test_a_fast_plan_has_no_stem_rule(self):
        header = ["plan_format: 1", "mode: fast", "branch: none", "created: 2026-09-25", "affects_workspaces: [zims]"]
        path = self.root / ".dgf-factory" / "PLAN.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(plan_text(header=header), encoding="utf-8")
        self.assertEqual(self.codes(path=path), [])


class Tasks(Base):
    def test_no_tasks(self):
        self.assertEqual(self.codes(plan_text().replace("## Tasks", "## Steps")), ["PLAN_NO_TASKS"])
        self.assertEqual(self.codes(tasks=["No tasks yet."]), ["PLAN_NO_TASKS"])

    def test_invalid_tasks(self):
        cases = {
            "a duplicate id": [task(1), task(1)],
            "an unknown dependency": [task(1, suffix=" (depends on 7)")],
            "a missing kind": [task(1, kind=None)],
            "an unknown kind": [task(1, kind="script")],
            "no files": [task(1, files=None)],
            "a cycle": [task(1, suffix=" (depends on 2)"), task(2, suffix=" (depends on 1)")],
        }
        for name, tasks in cases.items():
            with self.subTest(name):
                self.assertIn("PLAN_TASK_INVALID", self.codes(tasks=tasks))

    def test_a_deletes_only_task_is_valid(self):
        self.assertEqual(self.codes(tasks=[task(1, files=None, extra=[f"deletes: {FORM}"])]), [])

    def test_code_needs_a_reason(self):
        code = task(1, kind="code", files="zims/js/formhelper.js")
        self.assertEqual(self.codes(tasks=[code]), ["PLAN_CODE_REASON_MISSING"])
        with_reason = task(1, kind="code", files="zims/js/formhelper.js", extra=["reason: no verb reads the callback"])
        self.assertEqual(self.codes(tasks=[with_reason]), [])


class Ultra(Base):
    HEADER = ["plan_format: 1", "mode: ultra", "branch: feature/x", "created: 2026-09-25", "affects_workspaces: [zims]"]

    def bundle(self, index_body, phases=("phase-1.md",)):
        bundle = self.root / ".dgf-factory" / "plans" / "feature-x"
        bundle.mkdir(parents=True)
        for name in phases:
            (bundle / name).write_text("# Phase\n", encoding="utf-8")
        index = bundle / "index.md"
        index.write_text(plan_text(header=self.HEADER, body=index_body,
                                   tasks=[task(1).replace("task 1", "[task 1](phase-1.md#task-1)")]),
                         encoding="utf-8")
        return index

    def test_a_sound_bundle(self):
        self.assertEqual(self.codes(path=self.bundle("## Phase Index\n\n- [Phase 1](phase-1.md)\n\n")), [])

    def test_a_missing_phase_file(self):
        index = self.bundle("## Phase Index\n\n- [Phase 1](phase-1.md)\n- [Phase 2](phase-2.md)\n\n")
        self.assertEqual(self.codes(path=index), ["PLAN_ULTRA_BROKEN"])

    def test_a_phase_file_outside_the_bundle(self):
        index = self.bundle("## Phase Index\n\n- [Phase 1](phase-1.md)\n- [Elsewhere](../other.md)\n\n")
        self.assertEqual(self.codes(path=index), ["PLAN_ULTRA_BROKEN"])

    def test_no_phase_index(self):
        self.assertEqual(self.codes(path=self.bundle("")), ["PLAN_ULTRA_BROKEN"])


class Files(Base):
    def test_undeclared_workspace(self):
        self.assertEqual(self.codes(tasks=[task(1, files="webasm/FM/_COMPONENTS/DataSource/A.json")]),
                         ["PLAN_FILE_UNDECLARED_WORKSPACE"])
        self.assertEqual(self.codes(tasks=[task(1, files="nope/FM/x.xml")]), ["PLAN_FILE_UNDECLARED_WORKSPACE"])

    def test_kind_mismatch(self):
        self.assertEqual(self.codes(tasks=[task(1, files="zims/js/formhelper.js")]), ["PLAN_KIND_MISMATCH"])
        code = task(1, kind="code", files=FORM, extra=["reason: r"])
        self.assertEqual(self.codes(tasks=[code]), ["PLAN_KIND_MISMATCH"])

    def test_out_of_scope(self):
        for path in ("zims/FM/_DATA/Inspection/Handler.cs", "applibs-zims/Zims.Plugin.dll", "zims/app/main.ts"):
            with self.subTest(path):
                self.assertEqual(self.codes(tasks=[task(1, files=path)]), ["PLAN_OUT_OF_SCOPE"])

    def test_a_new_global_script_is_refused_and_a_new_form_script_is_not(self):
        new_global = task(1, kind="code", files="zims/js/new.js", extra=["reason: r"])
        self.assertEqual(self.codes(tasks=[new_global]), ["PLAN_CODE_FILE_NEW"])
        new_form = task(1, kind="code", files="zims/FM/_DATA/Inspection/_forms/Apply/_form.js", extra=["reason: r"])
        self.assertEqual(self.codes(tasks=[new_form]), [])
        edit_style = task(1, kind="code", files="zims/css/custom.css", extra=["reason: r"])
        self.assertEqual(self.codes(tasks=[edit_style]), [])

    def test_a_deleted_global_script_is_not_new(self):
        delete = task(1, kind="code", files=None, extra=["reason: r", "deletes: zims/js/formhelper.js"])
        self.assertEqual(self.codes(tasks=[delete]), [])

    def test_not_authored(self):
        self.assertEqual(self.codes(tasks=[task(1, files="zims/images/banner.png")]), ["PLAN_NOT_AUTHORED"])


class Routes(Base):
    def routed(self, path):
        return self.codes(tasks=[task(1, files=path)])

    def test_new_json_for_a_supported_type(self):
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/DataSource/Fee.json"), [])
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/Page/SiteMap/loginPage.json"), [])  # a nested name

    def test_a_site_map_at_the_components_root(self):
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/sitemap.json"), [])

    def test_json_for_a_legacy_or_not_runtime_type(self):
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/Workflow/new.json"), ["PLAN_ROUTE_MISMATCH"])
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/ProcessFlow/new.json"), ["PLAN_ROUTE_MISMATCH"])

    def test_an_existing_file_is_not_routed(self):
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/Workflow/old.json"), [])

    def test_a_legacy_artifact_written_as_json(self):
        self.assertEqual(self.routed("zims/FM/_DATA/Inspection/_forms/New/_form.json"), ["PLAN_ROUTE_MISMATCH"])
        self.assertEqual(self.routed("zims/FM/_PROCESS/Apply/process.json"), ["PLAN_ROUTE_MISMATCH"])

    def test_xml_under_components(self):
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/Page/p.xml"), ["PLAN_ROUTE_MISMATCH"])

    def test_folder_case(self):
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/datasource/Fee.json"), ["PLAN_ROUTE_MISMATCH"])
        self.assertIn("folder case", self.message("PLAN_ROUTE_MISMATCH"))
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/page/p.json"), ["PLAN_ROUTE_MISMATCH"])

    def test_no_route(self):
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/NotAType/x.json"), ["PLAN_ROUTE_UNKNOWN"])
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/Search/x.json"), ["PLAN_ROUTE_UNKNOWN"])  # no parity row

    def test_a_partial_type_warns(self):
        self.assertEqual(self.routed("zims/FM/_COMPONENTS/Uploader/u.json"), ["PARITY_PARTIAL"])


class Exits(Base):
    def run_cli(self, text):
        path = self.write(text)
        return helpers.run_cli("check_plan.py", path, "--workspaces-root", self.root)

    def test_exit_codes(self):
        self.assertEqual(self.run_cli(plan_text())[0], 0)
        self.assertEqual(self.run_cli(plan_text(tasks=[task(1, kind=None)]))[0], 1)
        self.assertEqual(self.run_cli(plan_text(tasks=[task(1, files="zims/images/a.png")]))[0], 2)
        code, out, _ = self.run_cli("# no frontmatter\n")
        self.assertEqual(code, 3)
        self.assertIn("ERROR PLAN_UNREADABLE", out)

    def test_output_lines(self):
        code, out, _ = self.run_cli(plan_text(tasks=[task(1, checked=True), task(2, suffix=" (depends on 1)")]))
        self.assertEqual(code, 0)
        self.assertIn("TASK: 1 [x] kind=config files=" + FORM, out)
        self.assertIn("TASK: 2 [ ] kind=config depends=1 files=" + FORM, out)
        self.assertIn("NOT RUN: plan-overlap (--overlap not given)", out)

    def test_a_root_that_is_not_a_directory(self):
        code, _, err = helpers.run_cli("check_plan.py", "x.md", "--workspaces-root", self.tmp / "missing")
        self.assertEqual(code, 3)
        self.assertIn("not a directory", err)


@unittest.skipUnless(helpers.have_git(), "git is not installed")
class Overlap(Base):
    def setUp(self):
        super().setUp()
        self.repo = helpers.make_repo(self.tmp / "estate")
        self.root = helpers.make_root(self.repo / "Web" / "workspaces", ROOT_FILES)
        helpers.commit_all(self.repo, "the estate")

    def branch_with_plan(self, branch, workspaces, done=False, text=None, base="main"):
        helpers.git(self.repo, "checkout", "-q", base)
        helpers.git(self.repo, "checkout", "-q", "-b", branch)
        header = HEADER[:2] + [f"branch: {branch}", HEADER[3], f"affects_workspaces: [{workspaces}]"]
        if "webasm" in workspaces:
            header.append('base_workspace_reason: "shared"')
        stem = branch.replace("/", "-")
        self.write(text if text is not None else plan_text(header=header, tasks=[task(1, checked=done)]),
                   name=f"{stem}.md")
        return helpers.commit_all(self.repo, f"plan {branch}")

    def this_plan(self):
        self.branch_with_plan("feature/x", "zims")
        return self.root / ".dgf-factory" / "plans" / "feature-x.md"

    def overlap_codes(self, path):
        codes = self.codes(path=path, overlap=True)
        return sorted(c for c in codes if c.startswith("PLAN_OVERLAP"))

    def test_a_branch_whose_plan_shares_a_workspace(self):
        self.branch_with_plan("feature/b", "zims")
        path = self.this_plan()
        self.assertEqual(self.overlap_codes(path), ["PLAN_OVERLAP"])
        self.assertIn("feature-b.md", self.message("PLAN_OVERLAP"))
        self.assertIn("`zims`", self.message("PLAN_OVERLAP"))
        self.assertTrue(any(line.startswith("OVERLAP SOURCES: ") for line in self.lines))

    def test_webasm_is_shared_with_every_plan(self):
        self.branch_with_plan("feature/base", "webasm")
        path = self.this_plan()
        self.assertEqual(self.overlap_codes(path), ["PLAN_OVERLAP"])
        self.assertIn("shared with every plan", self.message("PLAN_OVERLAP"))

    def test_a_completed_plan_is_ignored(self):
        self.branch_with_plan("feature/done", "zims", done=True)
        self.assertEqual(self.overlap_codes(self.this_plan()), [])

    def test_the_same_plan_on_a_local_and_a_remote_ref_counts_once(self):
        sha = self.branch_with_plan("feature/b", "zims")
        helpers.git(self.repo, "update-ref", "refs/remotes/origin/feature/b", sha)
        self.assertEqual(self.overlap_codes(self.this_plan()), ["PLAN_OVERLAP"])

    def test_the_plan_under_check_is_not_its_own_overlap(self):
        path = self.this_plan()
        helpers.git(self.repo, "update-ref", "refs/remotes/origin/feature/x", "HEAD")
        self.assertEqual(self.overlap_codes(path), [])

    def test_an_unreadable_plan_on_a_ref_is_info(self):
        self.branch_with_plan("feature/broken", "zims", text="# no frontmatter\n")
        path = self.this_plan()
        self.assertEqual(self.overlap_codes(path), ["PLAN_OVERLAP_UNREADABLE"])
        self.assertEqual(self.rep.exit_code(), 0)

    def test_a_disjoint_plan_does_not_overlap(self):
        helpers.make_root(self.root, {"dgf/FM/.keep": ""})
        helpers.commit_all(self.repo, "a second application")
        self.branch_with_plan("feature/dgf", "dgf")
        self.assertEqual(self.overlap_codes(self.this_plan()), [])

    def test_outside_a_work_tree_the_check_is_not_run(self):
        plain = helpers.make_root(self.tmp / "plain", ROOT_FILES)
        self.root = plain
        codes = self.codes(overlap=True)
        self.assertEqual(codes, [])
        self.assertIn(("plan-overlap", "the workspaces root is not in a git work tree"), self.rep.not_run)


if __name__ == "__main__":
    unittest.main()
