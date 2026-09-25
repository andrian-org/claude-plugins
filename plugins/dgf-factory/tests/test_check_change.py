"""check_change.py: the scope, means and planned checks over a changed set (ADR 0017 §6)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

GOOD_PROCESS = """<?xml version="1.0" encoding="utf-8"?>
<Process title="Case" table="Cases" keyName="id" allowBack="false" allowHistory="true" assignTasks="false">
  <OnStart action="">
    <Transitions>
      <Transition state="Open" />
    </Transitions>
  </OnStart>
  <States>
    <State name="Open" type="Task">
      <Transitions>
        <Transition state="End" />
      </Transitions>
    </State>
  </States>
</Process>
"""
ROOT = {
    ".dgf-factory/config.yaml": "dgf:\n  version: unknown\n",
    "app/FM/_PROCESS/Case/process.xml": GOOD_PROCESS,
    "app/js/formhelper.js": "// helper\n",
    "other/FM/_PROCESS/Case/process.xml": GOOD_PROCESS,
    "webasm/FM/.keep": "",
    "applibs-app/App.Plugin.dll": b"MZ",
}
PROCESS = "app/FM/_PROCESS/Case/process.xml"
PLAN = """---
plan_format: 1
mode: full
branch: feature/x
created: 2026-09-25
affects_workspaces: [app]
---

## Tasks

- [{done}] Task 1: Change the process
  - kind: config
  - files: {files}
- [ ] Task 2: Adjust the helper
  - kind: code
  - reason: no EventBase verb reads the callback
  - files: app/js/formhelper.js
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "root", ROOT)
        self.plan = self.write_plan()

    def write_plan(self, done=False, files=PROCESS, extra=""):
        path = self.root / ".dgf-factory" / "plans" / "feature-x.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(PLAN.format(done="x" if done else " ", files=files) + extra, encoding="utf-8")
        return path

    def run_check(self, *changed, extra=(), blocking=False):
        run = helpers.run_cli_blocking if blocking else helpers.run_cli
        args = ["--workspaces-root", self.root, "--plan", self.plan, *extra]
        if changed:
            args += ["--changed", *changed]
        return run("check_change.py", *args)

    def codes(self, *changed, extra=("--skip-validators",)):
        code, out, err = self.run_check(*changed, extra=extra)
        self.out = out
        found = [line.split()[1] for line in out.splitlines() if line.split()[:1] in (["ERROR"], ["WARN"], ["INFO"])]
        return code, found


class Scope(Base):
    def test_a_planned_change_is_clean(self):
        self.assertEqual(self.codes(f"M:{PROCESS}"), (0, []))
        self.assertIn(f"CHANGE: M {PROCESS} class=config workspace=app", self.out)

    def test_an_undeclared_workspace(self):
        self.assertEqual(self.codes("M:other/FM/_PROCESS/Case/process.xml")[0], 1)
        self.assertIn("ERROR CHANGE_UNDECLARED_WORKSPACE other/FM/_PROCESS/Case/process.xml", self.out)

    def test_a_file_in_no_workspace(self):
        code, found = self.codes("M:README.md")
        self.assertEqual(code, 2)
        self.assertIn("CHANGE_OUTSIDE_WORKSPACE", found)

    def test_a_bare_scalar_affects_declares_nothing_rather_than_letters(self):
        self.plan.write_text(self.plan.read_text(encoding="utf-8").replace("affects_workspaces: [app]",
                                                                           "affects_workspaces: app"),
                             encoding="utf-8")
        code, found = self.codes(f"M:{PROCESS}")
        self.assertEqual(code, 1)
        self.assertIn("`app`, which the plan's", self.out)
        self.assertNotIn("`a`", self.out)

    def test_a_directory_without_index_md_is_unreadable_not_a_traceback(self):
        code, _, err = helpers.run_cli("check_change.py", "--workspaces-root", self.root, "--plan",
                                       self.plan.parent, "--changed", f"M:{PROCESS}", "--skip-validators")
        self.assertEqual(code, 3, err)
        self.assertNotIn("Traceback", err)

    def test_pipeline_artifacts_are_ignored(self):
        self.assertEqual(self.codes(f"M:{PROCESS}", "A:.dgf-factory/plans/feature-y.md"), (0, []))
        self.assertIn("CHANGED: 1", self.out)


class Means(Base):
    def test_out_of_scope(self):
        for path in ("applibs-app/App.Plugin.dll", "app/FM/_DATA/Case/Handler.cs"):
            with self.subTest(path):
                code, found = self.codes(f"M:{path}")
                self.assertEqual(code, 1)
                self.assertIn("CHANGE_OUT_OF_SCOPE", found)

    def test_unplanned_code(self):
        code, found = self.codes("M:app/css/custom.css")
        self.assertEqual(code, 1)
        self.assertIn("CHANGE_CODE_UNPLANNED", found)

    def test_planned_code_is_clean(self):
        self.assertEqual(self.codes(f"M:{PROCESS}", "M:app/js/formhelper.js"), (0, []))

    def test_a_new_global_script(self):
        self.write_plan(extra="- [ ] Task 3: new\n  - kind: code\n  - reason: r\n  - files: app/js/new.js\n")
        code, found = self.codes("A:app/js/new.js")
        self.assertEqual(code, 1)
        self.assertEqual(found, ["CHANGE_CODE_FILE_NEW"])

    def test_a_new_form_script_is_allowed(self):
        form_js = "app/FM/_DATA/Case/_forms/Apply/_form.js"
        self.write_plan(extra=f"- [ ] Task 3: form\n  - kind: code\n  - reason: r\n  - files: {form_js}\n")
        self.assertEqual(self.codes(f"A:{form_js}"), (0, []))


class Planned(Base):
    def test_an_unplanned_config_file(self):
        code, found = self.codes("A:app/FM/_PROCESS/New/process.xml")
        self.assertEqual(code, 2)
        self.assertEqual(found, ["CHANGE_UNPLANNED_FILE"])

    def test_a_file_nothing_authors(self):
        code, found = self.codes("A:app/images/banner.png")
        self.assertEqual(code, 2)
        self.assertEqual(sorted(found), ["CHANGE_NOT_AUTHORED", "CHANGE_UNPLANNED_FILE"])

    def test_a_checked_task_whose_file_did_not_change(self):
        self.plan = self.write_plan(done=True)
        code, found = self.codes("M:app/js/formhelper.js")
        self.assertEqual(code, 2)
        self.assertEqual(found, ["CHANGE_TASK_FILE_UNCHANGED"])

    def test_a_checked_delete_that_still_exists(self):
        self.plan = self.write_plan(done=True, files=f"{PROCESS}\n  - deletes: app/js/formhelper.js")
        code, found = self.codes(f"M:{PROCESS}")
        self.assertEqual(code, 2)
        self.assertEqual(found, ["CHANGE_TASK_FILE_UNCHANGED"])


class Usage(Base):
    def test_a_bad_changed_entry(self):
        code, _, err = self.run_check("X:app/a.xml", extra=("--skip-validators",))
        self.assertEqual(code, 3)
        self.assertIn("--changed takes", err)

    def test_an_unreadable_plan(self):
        self.plan.write_text("# no frontmatter\n", encoding="utf-8")
        code, out, _ = self.run_check(f"M:{PROCESS}", extra=("--skip-validators",))
        self.assertEqual(code, 3)
        self.assertIn("ERROR PLAN_UNREADABLE", out)

    def test_skip_validators_needs_neither_dependency(self):
        code, out, err = self.run_check(f"M:{PROCESS}", extra=("--skip-validators",), blocking=True)
        self.assertEqual(code, 0, err)
        self.assertIn("NOT RUN: validators (--skip-validators)", out)

    def test_help_needs_neither_dependency(self):
        code, out, err = helpers.run_cli_blocking("check_change.py", "--help")
        self.assertEqual(code, 0, err)
        self.assertIn("--skip-validators", out)

    def test_validators_without_dependencies_exit_3(self):
        code, _, err = self.run_check(f"M:{PROCESS}", blocking=True)
        self.assertEqual(code, 3)
        self.assertIn("DEPENDENCY_MISSING", err)

    def test_a_files_path_that_leaves_the_root_is_exit_3(self):
        code, _, err = self.run_check(f"M:{PROCESS}", extra=("--skip-validators", "--files", "app/FM/../../x.json"),
                                      blocking=True)
        self.assertEqual(code, 3)
        self.assertIn("--files takes paths relative to the workspaces root; `app/FM/../../x.json` climbs out", err)

    def test_a_changed_path_that_leaves_the_root_is_exit_3(self):
        for value in ("A:../x.json", "M:/app/FM/x.xml", "D:app\\FM\\x.xml"):
            with self.subTest(value):
                code, _, err = self.run_check(value, extra=("--skip-validators",), blocking=True)
                self.assertEqual(code, 3)
                self.assertIn("--changed takes paths relative to the workspaces root", err)

    def test_a_base_that_starts_with_a_dash_is_exit_3_before_git_runs(self):
        for value in ("--base=-x", "--base=--output=x"):
            with self.subTest(value):
                code, out, err = helpers.run_cli_blocking("check_change.py", "--workspaces-root", self.root,
                                                          "--plan", self.plan, value, "--skip-validators")
                self.assertEqual(code, 3)
                self.assertIn("--base takes a branch or commit", err)
                self.assertNotIn("BASE:", out)

    def test_a_checked_task_path_that_leaves_the_root_is_left_to_check_plan(self):
        self.plan = self.write_plan(done=True, files="app/FM/../../outside.json")
        code, found = self.codes(f"M:{PROCESS}")
        self.assertEqual(found, ["CHANGE_UNPLANNED_FILE"])  # no CHANGE_TASK_FILE_UNCHANGED for the refused path
        self.assertEqual(code, 2)


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Validators(Base):
    def test_a_clean_root(self):
        code, found = self.codes(f"M:{PROCESS}", extra=())
        self.assertEqual((code, found), (0, []), self.out)
        self.assertIn("new: 0 error(s), 0 warning(s)", self.out)

    def test_a_dead_transition_is_reported(self):
        (self.root / PROCESS).write_text(GOOD_PROCESS.replace('state="End"', 'state="Closed"'), encoding="utf-8")
        code, found = self.codes(f"M:{PROCESS}", extra=())
        self.assertEqual(code, 1)
        self.assertIn("DEAD_TRANSITION", found)

    def test_files_limit_the_validators(self):
        broken = "other/FM/_PROCESS/Case/process.xml"
        (self.root / broken).write_text(GOOD_PROCESS.replace('state="End"', 'state="Closed"'), encoding="utf-8")
        code, found = self.codes(f"M:{PROCESS}", extra=("--files", PROCESS))
        self.assertEqual((code, found), (0, []), self.out)
        self.assertIn("Validated: 1 file(s)", self.out)


if __name__ == "__main__":
    unittest.main()
