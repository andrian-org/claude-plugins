"""check_change.py: the scope, means and planned checks over a changed set (ADR 0017 §6)."""

import contextlib
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
import check_change

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

    def test_deleting_an_undeclared_workspaces_last_file_is_still_undeclared(self):
        shutil.rmtree(self.root / "other")
        code, found = self.codes("D:other/FM/_PROCESS/Case/process.xml")
        self.assertEqual(code, 1, self.out)
        self.assertIn("CHANGE_UNDECLARED_WORKSPACE", found)
        self.assertNotIn("CHANGE_OUTSIDE_WORKSPACE", found)
        self.assertIn("CHANGE: D other/FM/_PROCESS/Case/process.xml class=config workspace=other", self.out)

    def test_known_workspaces_counts_what_a_deletion_proves(self):
        from lib import git
        shutil.rmtree(self.root / "other")
        changes = [git.Change("D", "other/FM/x.json"), git.Change("R", "app/FM/b.json", "gone/FM/a.json"),
                   git.Change("D", "notes/readme.md"), git.Change("D", "applibs-x/FM/a.json")]
        self.assertEqual(check_change.known_workspaces(self.root, changes), {"app", "webasm", "other", "gone"})

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

    def test_refuse_takes_plain_values(self):
        for base, files, changed in (("-x", None, None), (None, ["app/FM/../../x.json"], None),
                                     (None, None, ["M:../x.json"])):
            with self.subTest(base=base, files=files, changed=changed):
                with contextlib.redirect_stderr(io.StringIO()) as err, self.assertRaises(SystemExit) as caught:
                    check_change.refuse(base, files, changed)
                self.assertEqual(caught.exception.code, 3)
                self.assertIn("takes", err.getvalue())
        self.assertIsNone(check_change.refuse("main", [PROCESS], [f"M:{PROCESS}"]))

    def test_run_skipping_the_validators_records_the_reason_given(self):
        outcome = check_change.run(self.root, self.plan, changed=[f"M:{PROCESS}"], skip_validators=True,
                                   skip_reason="x")
        self.assertEqual(outcome.reports[0].not_run, [("validators", "x"), ("baseline", "x")])
        self.assertEqual([c.path for c in outcome.changes], [PROCESS])
        self.assertEqual((outcome.families, outcome.validated), ({}, 0))
        self.assertEqual([t.id for t in outcome.parsed.tasks], [1, 2])

    def test_run_on_an_unreadable_plan_has_no_parsed_plan(self):
        self.plan.write_text("# no frontmatter\n", encoding="utf-8")
        outcome = check_change.run(self.root, self.plan, changed=[f"M:{PROCESS}"], skip_validators=True)
        self.assertIsNone(outcome.parsed)
        self.assertIsNone(outcome.changes)
        self.assertEqual([f.code for f in outcome.reports[0].findings], ["PLAN_UNREADABLE"])

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

    def test_a_whole_root_run_records_the_validators_as_run(self):
        self.codes(f"M:{PROCESS}", extra=())
        checks = next(line for line in self.out.splitlines() if line.startswith("CHECKS RUN: "))
        self.assertIn("validators", checks.split(": ", 1)[1].split(", "))
        self.assertNotIn("NOT RUN: validators", self.out)

    def test_run_with_changed_returns_the_changes_and_no_baseline(self):
        outcome = check_change.run(self.root, self.plan, changed=[f"M:{PROCESS}"])
        self.assertEqual([(c.status, c.path) for c in outcome.changes], [("M", PROCESS)])
        rep = outcome.reports[0]
        self.assertIn("validators", rep.checks_run)
        self.assertEqual([check for check, _ in rep.not_run], ["baseline"])
        self.assertEqual(outcome.families[PROCESS], "xsd")
        self.assertEqual(outcome.validated, 2)

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
        self.assertIn("NOT RUN: validators (narrowed to 1 file(s) by --files; the gate's scope is the whole root", self.out)
        checks = next(line for line in self.out.splitlines() if line.startswith("CHECKS RUN: "))
        self.assertNotIn("validators", checks.split(": ", 1)[1].split(", "))


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class SavedBaseline(Base):
    """Without git, a run saved before the write is the baseline of the run after it (ADR 0025)."""

    MOVE = "app/FM/_WORKFLOW/Move/_workflow.xml"
    OLD_ERROR = "other/FM/_PROCESS/Case/process.xml"
    OLD_EXIT_3 = "app/FM/_DATA/Junk/settings.xml"

    def setUp(self):
        super().setUp()
        helpers.make_root(self.root, {
            # an untouched workflow whose CHANGE_STATE names the process the change edits (ADR 0014 §2)
            self.MOVE: '<Workflow><Sequence><StateProcess name="s" mode="CHANGE_STATE" process="Case" '
                       'state="Open"/></Sequence></Workflow>\n',
            # old defects in files the change never touches: a dead transition, and a file that parses as neither
            # family, whose FAMILY_UNRESOLVED is an exit-3 code
            self.OLD_ERROR: GOOD_PROCESS.replace('state="End"', 'state="Closed"'),
            self.OLD_EXIT_3: "<entity><fields></entity>\n",
        })
        self.saved = self.tmp / "baseline.json"

    def save(self, *extra):
        return self.run_check(f"M:{PROCESS}", extra=("--save-baseline", self.saved, *extra))

    def compare(self, *extra):
        code, out, _ = self.run_check(f"M:{PROCESS}", extra=("--baseline", self.saved, *extra))
        self.out = out
        return code, [line.split()[1] for line in out.splitlines() if line.split()[:1] in (["ERROR"], ["WARN"])]

    def test_without_a_baseline_an_old_exit_3_file_decides_the_exit(self):
        code, found = self.codes(f"M:{PROCESS}", extra=())
        self.assertEqual(code, 3, self.out)
        self.assertIn("FAMILY_UNRESOLVED", found)

    def test_the_saving_run_judges_no_validator_finding(self):
        code, out, _ = self.save()
        self.assertEqual(code, 0, out)
        self.assertTrue(self.saved.is_file())
        self.assertRegex(out, r"BASELINE: saved \d+ finding\(s\) — \d+ error\(s\), \d+ warning\(s\) — to ")
        self.assertNotRegex(out, r"(?m)^(ERROR|WARN) (DEAD_TRANSITION|FAMILY_UNRESOLVED)")

    def test_old_findings_are_pre_existing_so_a_harmless_edit_is_clean(self):
        self.save()
        (self.root / PROCESS).write_text(GOOD_PROCESS.replace('title="Case"', 'title="Case file"'), encoding="utf-8")
        code, found = self.compare()
        self.assertEqual((code, found), (0, []), self.out)
        self.assertIn("CHECKS RUN:", self.out)
        self.assertRegex(self.out, r"INFO PRE_EXISTING \S*Junk/settings\.xml \[FAMILY_UNRESOLVED\]")
        self.assertRegex(self.out, r"INFO PRE_EXISTING \S*other/FM/_PROCESS/Case/process\.xml\S* \[DEAD_TRANSITION\]")

    def test_a_break_in_an_untouched_file_is_new_and_blocks_despite_an_old_exit_3(self):
        self.save()
        (self.root / PROCESS).write_text(GOOD_PROCESS.replace('"Open"', '"Opened"'), encoding="utf-8")
        code, found = self.compare()
        self.assertEqual(code, 1, self.out)
        self.assertEqual(found, ["CHANGE_STATE_STATE_UNDECLARED"])
        self.assertIn(self.MOVE, self.out)
        self.assertIn("new: 1 error(s)", self.out)

    def test_a_malformed_file_the_change_writes_is_new(self):
        self.save()
        (self.root / PROCESS).write_text("<Process><States></Process>\n", encoding="utf-8")
        code, found = self.compare()
        self.assertEqual(code, 3, self.out)
        self.assertIn("FAMILY_UNRESOLVED", found)
        self.assertRegex(self.out, rf"ERROR FAMILY_UNRESOLVED \S*{PROCESS}")

    def test_a_baseline_that_cannot_be_used_is_exit_3(self):
        cases = {"missing": None, "not json": "{", "no findings": '{"format": 1}'}
        for name, text in cases.items():
            with self.subTest(name):
                if text is None:
                    self.saved.unlink(missing_ok=True)
                else:
                    self.saved.write_text(text, encoding="utf-8")
                code, found = self.compare()
                self.assertEqual(code, 3, self.out)
                self.assertEqual(found, ["BASELINE_UNUSABLE"])

    def test_a_baseline_saved_for_another_root_or_scope_is_exit_3(self):
        self.save()
        other = helpers.make_root(self.tmp / "elsewhere", ROOT)
        code, out, _ = helpers.run_cli("check_change.py", "--workspaces-root", other, "--plan", self.plan,
                                       "--changed", f"M:{PROCESS}", "--baseline", self.saved)
        self.assertEqual(code, 3, out)
        self.assertIn("BASELINE_UNUSABLE", out)
        code, found = self.compare("--files", PROCESS)
        self.assertEqual((code, found), (3, ["BASELINE_UNUSABLE"]), self.out)

    def test_the_baseline_flags_take_a_changed_set_and_the_validators(self):
        for extra in (("--save-baseline", self.saved, "--baseline", self.saved),
                      ("--baseline", self.saved, "--skip-validators"),
                      ("--save-baseline", self.saved, "--skip-validators")):
            with self.subTest(extra):
                code, _, err = self.run_check(f"M:{PROCESS}", extra=extra)
                self.assertEqual(code, 3, err)
        code, _, err = helpers.run_cli("check_change.py", "--workspaces-root", self.root, "--plan", self.plan,
                                       "--base", "main", "--baseline", self.saved)
        self.assertEqual(code, 3, err)
        self.assertIn("--changed", err)

    def test_the_gate_never_passes_a_saved_baseline(self):
        # the gate's baseline is the merge-base tree alone (ADR 0018); a saved one is a writing skill's (ADR 0025)
        source = (helpers.PLUGIN_ROOT / "scripts" / "verify_gate.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"saved_baseline|save_baseline")
        outcome = check_change.run(self.root, self.plan, changed=[f"M:{PROCESS}"])
        self.assertEqual([check for check, _ in outcome.reports[0].not_run], ["baseline"])


@unittest.skipUnless(helpers.have_dependencies() and helpers.have_git(), "needs lxml, jsonschema and git")
class RunWithABase(Base):
    def setUp(self):
        super().setUp()
        helpers.make_repo(self.root)
        helpers.commit_all(self.root, "base")
        helpers.git(self.root, "checkout", "-q", "-b", "feature/x")
        (self.root / PROCESS).write_text(GOOD_PROCESS.replace('title="Case"', 'title="Case2"'), encoding="utf-8")

    def test_run_returns_the_changes_and_each_files_family(self):
        outcome = check_change.run(self.root, self.plan, base="main")
        self.assertEqual([(c.status, c.path) for c in outcome.changes], [("M", PROCESS)])
        self.assertEqual(outcome.families, {PROCESS: "xsd", "other/FM/_PROCESS/Case/process.xml": "xsd"})
        rep = outcome.reports[0]
        self.assertIn("baseline", rep.checks_run)
        self.assertIn("validators", rep.checks_run)
        self.assertEqual(rep.not_run, [])


if __name__ == "__main__":
    unittest.main()
