"""verify_gate.py: discovery, the checks it runs, the entries, and the one block it prints (ADR 0022)."""

import contextlib
import io
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import helpers
import verify_gate
from lib import git, knowledge

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
DEAD_PROCESS = GOOD_PROCESS.replace('state="End"', 'state="Closed"')
UNREACHABLE_PROCESS = GOOD_PROCESS.replace("  </States>", """    <State name="Orphan" type="Task">
      <Transitions>
        <Transition state="End" />
      </Transitions>
    </State>
  </States>""")
FIX_REASON = "1 new blocking finding(s) — fix each inside the plan's scope and record a patch"
PROCESS = "app/FM/_PROCESS/Case/process.xml"
HELPER = "app/js/formhelper.js"
ROOT = {
    ".dgf-factory/config.yaml": "dgf:\n  version: unknown\n",
    PROCESS: GOOD_PROCESS,
    HELPER: "// helper\n",
    "other/FM/_PROCESS/Case/process.xml": GOOD_PROCESS,
    "webasm/FM/.keep": "",
}
PLAN_REL = ".dgf-factory/plans/feature-x.md"
HEADER = """---
plan_format: 1
mode: full
branch: feature/x
created: 2026-09-25
affects_workspaces: [app]
---

# Implementation Plan: x

"""
GATE = re.compile(r"```dgf-gate-result\n(.*?)\n```", re.S)


def task(number, checked=True, kind="config", files=PROCESS, reason=None):
    lines = [f"- [{'x' if checked else ' '}] Task {number}: task {number}", f"  - kind: {kind}"]
    if reason:
        lines.append(f"  - reason: {reason}")
    return "\n".join(lines + [f"  - files: {files}"])


def plan_text(*tasks, body=""):
    return HEADER + body + "## Tasks\n\n" + "\n".join(tasks or (task(1),)) + "\n"


def block(stdout):
    return json.loads(GATE.findall(stdout)[-1])


def ids(payload, list_name):
    return [entry["id"] for entry in payload[list_name]]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "root", ROOT)
        self.plan = self.write_plan(plan_text())

    def write_plan(self, text, name="feature-x.md"):
        path = self.root / ".dgf-factory" / "plans" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def gate(self, *args, plan=True, blocking=False):
        run = helpers.run_cli_blocking if blocking else helpers.run_cli
        argv = ["--workspaces-root", self.root, "--no-overlap", *(["--plan", self.plan] if plan else []), *args]
        code, out, err = run("verify_gate.py", *argv)
        self.out, self.err = out, err
        return code, (block(out) if GATE.search(out) else None)


class Usage(Base):
    def test_help_imports_nothing_third_party(self):
        code, out, err = helpers.run_cli_blocking("verify_gate.py", "--help")
        self.assertEqual(code, 0, err)
        for flag in ("--workspaces-root", "--plans-dir", "--fast-plan", "--branch", "--plan", "--base", "--changed",
                     "--no-overlap", "--strict", "--verbose"):
            self.assertIn(flag, out)

    def test_a_plan_with_neither_base_nor_changed_is_exit_3_with_no_block(self):
        code, payload = self.gate()
        self.assertEqual((code, payload), (3, None), self.err)
        self.assertIn("needs --base", self.err)

    def test_a_plan_outside_the_root_is_exit_3_with_no_block(self):
        outside = helpers.make_root(self.tmp / "elsewhere", {"feature-x.md": plan_text()}) / "feature-x.md"
        code, out, err = helpers.run_cli("verify_gate.py", "--workspaces-root", self.root, "--plan", outside,
                                         "--changed", f"M:{PROCESS}")
        self.assertEqual(code, 3, out + err)
        self.assertNotIn("dgf-gate-result", out)
        self.assertIn("must be inside the workspaces root", err)

    def test_a_base_that_starts_with_a_dash_or_a_path_that_leaves_the_root_is_exit_3(self):
        for args in (["--base=-x"], ["--changed", "M:../x.json"], ["--changed", "Q:app/x.json"]):
            with self.subTest(args):
                code, payload = self.gate(*args)
                self.assertEqual((code, payload), (3, None), self.err)


class Discovery(Base):
    def test_a_root_that_is_not_set_up(self):
        (self.root / ".dgf-factory" / "config.yaml").unlink()
        code, payload = self.gate("--changed", f"M:{PROCESS}")
        self.assertEqual(code, 1, self.out)
        self.assertEqual(ids(payload, "blockers"), ["ROOT_NOT_SET_UP"])
        self.assertEqual((payload["checks_run"], payload["suggested_next"]["command"]), ([], None))
        self.assertIn("/dgf", payload["suggested_next"]["reason"])

    def test_no_plan_suggests_dgf_plan(self):
        self.plan.unlink()
        code, payload = self.gate("--branch", "feature/x", "--changed", f"M:{PROCESS}", plan=False)
        self.assertEqual(code, 1, self.out)
        self.assertEqual(ids(payload, "blockers"), ["PLAN_NOT_FOUND"])
        self.assertEqual(payload["suggested_next"]["command"], "/dgf-plan")

    def test_an_ambiguous_plan_suggests_nothing(self):
        self.write_plan(plan_text(task(1, checked=False)), name="feature-y.md")
        self.write_plan(plan_text(task(1, checked=False)), name="feature-z.md")
        code, payload = self.gate("--branch", "feature/none", "--changed", f"M:{PROCESS}", plan=False)
        self.assertEqual(code, 1, self.out)
        self.assertIn("PLAN_AMBIGUOUS", ids(payload, "blockers"))
        self.assertIsNone(payload["suggested_next"]["command"])

    def test_a_fallback_plan_is_never_chosen_for_the_user(self):
        self.write_plan(plan_text(task(1, checked=False)))
        code, payload = self.gate("--branch", "feature/elsewhere", "--changed", f"M:{PROCESS}", plan=False)
        self.assertEqual(code, 1, self.out)
        self.assertEqual(ids(payload, "blockers"), ["GATE_PLAN_UNCONFIRMED"])
        self.assertEqual(payload["blockers"][0]["file"], PLAN_REL)
        self.assertEqual(ids(payload, "warnings"), ["PLAN_FALLBACK"])
        self.assertIsNone(payload["suggested_next"]["command"])
        self.assertIn("--plan", payload["suggested_next"]["reason"])
        self.assertEqual(payload["checks_run"], [])

    def test_the_branch_plan_is_found_without_plan(self):
        code, payload = self.gate("--branch", "feature/x", "--changed", f"M:{PROCESS}", plan=False, blocking=True)
        self.assertEqual(code, 3, self.out)  # found, then the dependencies are blocked
        self.assertIn("plan-header", payload["checks_run"])


class WithoutDependencies(Base):
    def test_missing_dependencies_still_run_the_change_checks(self):
        code, payload = self.gate("--changed", f"M:{PROCESS}", blocking=True)
        self.assertEqual(code, 3, self.out + self.err)
        self.assertEqual(ids(payload, "blockers"), ["DEPENDENCY_MISSING"])
        self.assertIsNone(payload["suggested_next"]["command"])
        self.assertIn("pip install", payload["suggested_next"]["reason"])
        self.assertIn("change-scope", payload["checks_run"])
        self.assertIn("not-run-validators", ids(payload, "warnings"))
        self.assertNotIn("schema_family", payload)
        self.assertIn("NOT RUN: validators (lxml, jsonschema not installed)", self.out)

    def test_an_unreadable_plan_runs_no_change_check(self):
        self.plan.write_text("# no frontmatter\n", encoding="utf-8")
        code, payload = self.gate("--changed", f"M:{PROCESS}", blocking=True)
        self.assertEqual(code, 3, self.out)
        self.assertEqual(ids(payload, "blockers"), ["PLAN_UNREADABLE"])
        self.assertEqual(payload["suggested_next"]["command"], "/dgf-plan")
        self.assertIn("not-run-change-scope", ids(payload, "warnings"))
        self.assertTrue(all("the plan is unreadable" in e["summary"] for e in payload["warnings"]))


class KnowledgeTableInTheFootprint(Base):
    def test_a_malformed_table_is_a_finding_not_a_traceback(self):
        broken = knowledge.KnowledgeTableError("legacy-artifacts", "the header row changed")
        argv = ["--workspaces-root", str(self.root), "--plan", str(self.plan), "--no-overlap",
                "--changed", f"M:{PROCESS}"]
        out = io.StringIO()
        with mock.patch.object(verify_gate.deps, "missing", return_value=["lxml"]), \
                mock.patch.object(verify_gate, "footprint", side_effect=broken), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = verify_gate.main(argv)
        payload = block(out.getvalue())
        self.assertEqual(code, 3, out.getvalue())
        self.assertIn("KNOWLEDGE_TABLE", ids(payload, "blockers"))
        self.assertIsNone(payload["suggested_next"]["command"])
        for absent in ("affected_components", "affected_processes"):
            self.assertNotIn(absent, payload)


class Footprint(unittest.TestCase):
    KNOWN = {"app", "webasm"}

    def test_each_kind_of_changed_file(self):
        changes = [git.Change("M", "app/FM/_COMPONENTS/Button/ApplyNow.json"),
                   git.Change("A", "webasm/FM/_PROCESS/Payment/process.xml"),
                   git.Change("M", "app/FM/_PROCESS/Case/Review/_workflow.xml"),
                   git.Change("M", "app/FM/_DATA/Cases/_forms/Apply/_form.js"),
                   git.Change("R", "app/FM/_DATA/Cases/_views/New/_view.xml", "app/FM/_DATA/Cases/_views/Old/_view.xml"),
                   git.Change("M", "app/FM/_DATA/Cases/notes.xml"),
                   git.Change("M", HELPER),
                   git.Change("M", "elsewhere/FM/_PROCESS/X/process.xml")]
        components, processes = verify_gate.footprint(changes, self.KNOWN)
        self.assertEqual(processes, [{"workspace": "app", "name": "Case", "reference": "Case"},
                                     {"workspace": "webasm", "name": "Payment", "reference": "BASE:Payment"}])
        got = [(c["artifact"], c["name"], c["file"], c["change"]) for c in components]
        self.assertEqual(got, [
            ("component", "Button/ApplyNow", "app/FM/_COMPONENTS/Button/ApplyNow.json", "M"),
            ("form", "Cases/Apply", "app/FM/_DATA/Cases/_forms/Apply/_form.js", "M"),
            ("table-view", "Cases/New", "app/FM/_DATA/Cases/_views/New/_view.xml", "A"),
            ("table-view", "Cases/Old", "app/FM/_DATA/Cases/_views/Old/_view.xml", "D"),
            ("configuration", "_DATA/Cases/notes.xml", "app/FM/_DATA/Cases/notes.xml", "M"),
        ])
        self.assertEqual({c["workspace"] for c in components}, {"app"})

    def test_no_changes_is_two_empty_lists(self):
        self.assertEqual(verify_gate.footprint([], self.KNOWN), ([], []))


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Changed(Base):
    def test_changed_has_no_baseline_so_the_gate_warns(self):
        code, payload = self.gate("--changed", f"M:{PROCESS}")
        self.assertEqual(code, 2, self.out)
        self.assertEqual((payload["status"], payload["blocking"]), ("warn", False))
        self.assertEqual(ids(payload, "warnings"), ["not-run-baseline"])
        self.assertEqual(payload["suggested_next"]["command"], "/dgf-commit")
        self.assertGreaterEqual(payload["schema_family"]["xsd"], 1)
        self.assertEqual(payload["affected_processes"], [{"workspace": "app", "name": "Case", "reference": "Case"}])

    def test_an_unchecked_task(self):
        self.write_plan(plan_text(task(1), task(2, checked=False)))
        code, payload = self.gate("--changed", f"M:{PROCESS}")
        self.assertEqual(code, 1, self.out)
        self.assertEqual(ids(payload, "blockers"), ["task-2"])
        self.assertEqual(payload["blockers"][0]["file"], PLAN_REL)
        self.assertEqual(payload["suggested_next"]["command"], "/dgf-implement")

    def test_a_defective_plan_suggests_dgf_plan(self):
        cases = {"PLAN_TASK_INVALID": plan_text(task(1).replace("  - kind: config\n", "")),
                 "PLAN_COMMITS_INVALID": plan_text(task(1), body="## Commit Plan\n\n- Commit 1: not the shape\n\n")}
        for code_name, text in cases.items():
            with self.subTest(code_name):
                self.write_plan(text)
                code, payload = self.gate("--changed", f"M:{PROCESS}")
                self.assertEqual(code, 1, self.out)
                self.assertIn(code_name, ids(payload, "blockers"))
                self.assertEqual(payload["suggested_next"]["command"], "/dgf-plan")

    def test_a_code_task_makes_frontend_tests_a_warning(self):
        self.write_plan(plan_text(task(1), task(2, kind="code", files=HELPER, reason="no verb reads the callback")))
        code, payload = self.gate("--changed", f"M:{PROCESS}", f"M:{HELPER}")
        self.assertEqual(code, 2, self.out)
        self.assertIn("not-run-frontend-tests", ids(payload, "warnings"))
        self.assertIn('CODE TASK: 2 reason="no verb reads the callback"', self.out)

    def test_strict_promotes_a_new_change_warning(self):
        unplanned = "app/FM/_DATA/Case/settings.xml"
        code, payload = self.gate("--changed", f"M:{PROCESS}", f"M:{unplanned}")
        self.assertEqual((code, payload["status"]), (2, "warn"), self.out)
        self.assertIn("CHANGE_UNPLANNED_FILE", ids(payload, "warnings"))
        code, payload = self.gate("--changed", f"M:{PROCESS}", f"M:{unplanned}", "--strict")
        self.assertEqual((code, payload["status"]), (1, "fail"), self.out)
        promoted = [e for e in payload["blockers"] if e["id"] == "CHANGE_UNPLANNED_FILE"]
        self.assertEqual(len(promoted), 1)
        self.assertEqual((promoted[0]["severity"], promoted[0]["file"]), ("warning", unplanned))
        self.assertNotIn("CHANGE_UNPLANNED_FILE", ids(payload, "warnings"))
        self.assertEqual(payload["suggested_next"]["command"], "/dgf-implement")

    def test_a_deleted_workspaces_process_is_in_the_footprint(self):
        shutil.rmtree(self.root / "other")
        code, payload = self.gate("--changed", f"M:{PROCESS}", "D:other/FM/_PROCESS/Case/process.xml")
        self.assertEqual(code, 1, self.out)
        self.assertIn("CHANGE_UNDECLARED_WORKSPACE", ids(payload, "blockers"))
        self.assertIn({"workspace": "other", "name": "Case", "reference": "Case"}, payload["affected_processes"])

    def test_a_base_outside_git_computes_no_footprint(self):
        code, payload = self.gate("--base", "main")
        self.assertEqual(code, 2, self.out)
        for absent in ("affected_components", "affected_processes"):
            self.assertNotIn(absent, payload)
        self.assertIn("schema_family", payload)
        self.assertIn("not-run-change-scope", ids(payload, "warnings"))

    def test_exactly_one_block_and_nothing_after_it(self):
        self.gate("--changed", f"M:{PROCESS}")
        self.assertEqual(self.out.count("```dgf-gate-result"), 1)
        self.assertTrue(self.out.endswith("```\n"), self.out[-80:])
        self.assertIn("STATUS: warn", self.out)


@unittest.skipUnless(helpers.have_dependencies() and helpers.have_git(), "needs lxml, jsonschema and git")
class WithABase(Base):
    def setUp(self):
        super().setUp()
        helpers.make_repo(self.root)
        (self.root / "other/FM/_PROCESS/Case/process.xml").write_text(DEAD_PROCESS, encoding="utf-8")
        helpers.commit_all(self.root, "the estate, with one defect already in it")
        helpers.git(self.root, "checkout", "-q", "-b", "feature/x")

    def test_a_clean_change_passes(self):
        (self.root / PROCESS).write_text(GOOD_PROCESS.replace('title="Case"', 'title="Case file"'), encoding="utf-8")
        code, payload = self.gate("--base", "main")
        self.assertEqual(code, 0, self.out)
        self.assertEqual((payload["status"], payload["blocking"]), ("pass", False))
        self.assertTrue(set(verify_gate.REQUIRED) <= set(payload["checks_run"]), payload["checks_run"])
        self.assertEqual(payload["suggested_next"]["command"], "/dgf-commit")
        self.assertGreaterEqual(payload["schema_family"]["xsd"], 1)
        self.assertEqual(payload["affected_processes"], [{"workspace": "app", "name": "Case", "reference": "Case"}])
        self.assertEqual(payload["affected_components"], [])
        self.assertEqual(payload["blockers"] + payload["warnings"], [])
        self.assertIn("INFO PRE_EXISTING", self.out)

    def test_a_new_dead_transition_blocks_and_a_pre_existing_one_never_does(self):
        (self.root / PROCESS).write_text(DEAD_PROCESS, encoding="utf-8")
        code, payload = self.gate("--base", "main")
        self.assertEqual(code, 1, self.out)
        self.assertEqual(ids(payload, "blockers"), ["DEAD_TRANSITION"])
        dead = payload["blockers"][0]
        self.assertEqual((dead["file"], dead["line"], dead["schema_family"]), (PROCESS, 11, "xsd"))
        self.assertNotIn("PRE_EXISTING", ids(payload, "blockers") + ids(payload, "warnings"))
        self.assertNotIn("other/FM/_PROCESS/Case/process.xml", payload["affected_files"])
        self.assertEqual(payload["suggested_next"], {"command": "/dgf-fix", "reason": FIX_REASON})

    def test_an_unchecked_task_comes_before_a_new_finding(self):
        self.write_plan(plan_text(task(1), task(2, checked=False)))
        (self.root / PROCESS).write_text(DEAD_PROCESS, encoding="utf-8")
        code, payload = self.gate("--base", "main")
        self.assertEqual(code, 1, self.out)
        self.assertEqual(payload["suggested_next"], {
            "command": "/dgf-implement", "reason": "1 task(s) unchecked; then 1 new blocking finding(s) for /dgf-fix"})

    def test_a_scope_error_comes_before_a_new_finding(self):
        (self.root / PROCESS).write_text(DEAD_PROCESS, encoding="utf-8")
        (self.root / "other/FM/_PROCESS/Case/process.xml").write_text(GOOD_PROCESS, encoding="utf-8")
        code, payload = self.gate("--base", "main")
        self.assertEqual(code, 1, self.out)
        self.assertIn("CHANGE_UNDECLARED_WORKSPACE", ids(payload, "blockers"))
        self.assertIn("DEAD_TRANSITION", ids(payload, "blockers"))
        self.assertEqual(payload["suggested_next"], {
            "command": "/dgf-implement",
            "reason": "1 change-check error(s); then 1 new blocking finding(s) for /dgf-fix"})

    def test_strict_sends_a_promoted_validator_warning_to_dgf_fix(self):
        (self.root / PROCESS).write_text(UNREACHABLE_PROCESS, encoding="utf-8")
        code, payload = self.gate("--base", "main")
        self.assertEqual(code, 2, self.out)
        self.assertIn("UNREACHABLE_STATE", ids(payload, "warnings"))
        self.assertEqual(payload["suggested_next"]["command"], "/dgf-commit")
        code, payload = self.gate("--base", "main", "--strict")
        self.assertEqual(code, 1, self.out)
        self.assertEqual(ids(payload, "blockers"), ["UNREACHABLE_STATE"])
        self.assertEqual(payload["suggested_next"], {"command": "/dgf-fix", "reason": FIX_REASON})

    def test_strict_sends_a_promoted_change_warning_to_dgf_implement_first(self):
        (self.root / PROCESS).write_text(UNREACHABLE_PROCESS, encoding="utf-8")
        helpers.make_root(self.root, {"app/FM/_PROCESS/Other/process.xml": GOOD_PROCESS})  # valid, and no task lists it
        code, payload = self.gate("--base", "main", "--strict")
        self.assertEqual(code, 1, self.out)
        self.assertEqual(sorted(ids(payload, "blockers")), ["CHANGE_UNPLANNED_FILE", "UNREACHABLE_STATE"])
        self.assertEqual(payload["suggested_next"], {
            "command": "/dgf-implement",
            "reason": "1 change-check warning(s) promoted by --strict; then 1 new blocking finding(s) for /dgf-fix"})

    def test_pre_existing_findings_are_cut_at_20(self):
        for n in range(22):
            helpers.make_root(self.root, {f"app/FM/_PROCESS/Old{n}/process.xml": DEAD_PROCESS})
        helpers.git(self.root, "checkout", "-q", "main")
        helpers.commit_all(self.root, "more defects")
        helpers.git(self.root, "checkout", "-q", "feature/x")
        helpers.git(self.root, "merge", "-q", "main")
        (self.root / PROCESS).write_text(GOOD_PROCESS.replace('title="Case"', 'title="Case file"'), encoding="utf-8")
        code, payload = self.gate("--base", "main")
        self.assertEqual(code, 0, self.out)
        self.assertEqual(self.out.count("INFO PRE_EXISTING"), verify_gate.SHOWN_MAX)
        self.assertIn("Shown: 20 of 23 PRE_EXISTING — check_change.py --base main lists every one", self.out)
        self.assertIn("pre-existing: 23", self.out)


if __name__ == "__main__":
    unittest.main()
