"""The merge-base baseline: lib/baseline.py and check_change.py --base (ADR 0018) — and a saved one (ADR 0025)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import baseline, report

PROCESS = """<?xml version="1.0" encoding="utf-8"?>
<Process title="{name}" table="Cases" keyName="id" allowBack="false" allowHistory="true" assignTasks="false">
  <OnStart action="">
    <Transitions>
      <Transition state="Open" />
    </Transitions>
  </OnStart>
  <States>
    <State name="Open" type="Task" action="{action}">
      <Transitions>
        <Transition state="{target}" />
      </Transitions>
    </State>
  </States>
</Process>
"""
WORKFLOW = '<?xml version="1.0" encoding="utf-8"?>\n<Workflow name="Notify">\n  <Sequence/>\n</Workflow>\n'
PLAN = """---
plan_format: 1
mode: full
branch: feature/x
created: 2026-09-25
affects_workspaces: [app]
---

## Tasks

- [ ] Task 1: Change the case process
  - kind: config
  - files: app/FM/_PROCESS/Case/process.xml, app/FM/_PROCESS/Other/process.xml
  - deletes: app/FM/_WORKFLOW/Notify/_workflow.xml
"""


def process(name="Case", target="End", action=""):
    return PROCESS.format(name=name, target=target, action=action)


def finding(code, file, message, line=None):
    return report.Finding(code, report.CODES[code], file, line, message)


class Compare(unittest.TestCase):
    ROOT = "/estate/workspaces"
    BASE = "/tmp/dgf-base-1"

    def test_the_same_finding_at_both_trees_is_pre_existing(self):
        head = [finding("DEAD_TRANSITION", "app/p.xml", f"`{self.ROOT}/app/p.xml` goes nowhere", line=9)]
        base = [finding("DEAD_TRANSITION", "app/p.xml", f"`{self.BASE}/app/p.xml` goes nowhere", line=5)]
        new, pre, fixed = baseline.compare(head, base, self.ROOT, self.BASE)
        self.assertEqual((len(new), len(pre), len(fixed)), (0, 1, 0))

    def test_a_second_copy_is_new(self):
        one = finding("SCHEMA_INVALID", "app/c.json", "bad")
        new, pre, _ = baseline.compare([one, one], [one], self.ROOT, self.BASE)
        self.assertEqual((len(new), len(pre)), (1, 1))

    def test_a_finding_the_branch_removed_is_fixed(self):
        gone = finding("WORKFLOW_UNRESOLVED", "app/p.xml", "missing")
        new, pre, fixed = baseline.compare([], [gone], self.ROOT, self.BASE)
        self.assertEqual(fixed, [gone])

    def test_info_findings_pass_through(self):
        info = finding("NO_SERVICE", "app/c.json", "legal, not dispatchable")
        new, pre, fixed = baseline.compare([info], [info], self.ROOT, self.BASE)
        self.assertEqual((new, pre, fixed), ([info], [], []))

    def test_a_relative_root_is_never_stripped(self):
        self.assertEqual(baseline.root_forms("/a/b"), ["/a/b"])
        self.assertNotIn(".", baseline.root_forms("."))


class Saved(unittest.TestCase):
    """A run saved before a write stands for the tree before it (ADR 0025): save() and load(), stdlib only."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root)
        self.path = self.root / ".dgf-factory" / "baseline.json"
        self.path.parent.mkdir()

    def round_trip(self, before, files=None):
        baseline.save(self.path, before, self.root, files)
        return baseline.load(self.path, self.root, files)

    def rows(self, **overrides):
        data = {"format": baseline.FORMAT, "root": str(self.root), "files": None,
                "findings": [{"code": "DEAD_TRANSITION", "file": "app/p.xml", "line": 3, "message": "m"}]}
        data.update(overrides)
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_a_message_carrying_the_root_is_saved_without_it_and_still_matches_after_the_write(self):
        message = f"`{self.root}/app/p.xml` moves to `Nowhere`"
        saved = self.round_trip([finding("DEAD_TRANSITION", "app/p.xml", message, line=5)])
        rows = json.loads(self.path.read_text(encoding="utf-8"))["findings"]  # the file names its root; rows do not
        self.assertEqual(rows[0]["message"], "`app/p.xml` moves to `Nowhere`")
        after = [finding("DEAD_TRANSITION", "app/p.xml", message, line=9)]  # lines moved; the key has none
        new, pre, fixed = baseline.compare(after, saved, self.root, [])
        self.assertEqual((len(new), len(pre), len(fixed)), (0, 1, 0))

    def test_a_second_copy_of_a_saved_key_is_new(self):
        one = finding("SCHEMA_INVALID", "app/c.json", "bad")
        new, pre, _ = baseline.compare([one, one], self.round_trip([one]), self.root, [])
        self.assertEqual((len(new), len(pre)), (1, 1))

    def test_an_info_finding_is_never_saved(self):
        info, error = finding("NO_SERVICE", "app/c.json", "legal"), finding("WORKFLOW_UNRESOLVED", "app/p.xml", "gone")
        self.assertEqual(baseline.save(self.path, [info, error], self.root, None), [error])
        self.assertEqual([f.code for f in baseline.load(self.path, self.root, None)], ["WORKFLOW_UNRESOLVED"])

    def test_the_scope_is_compared_whatever_its_order(self):
        self.round_trip([], files=["b.xml", "a.xml"])
        self.assertEqual(baseline.load(self.path, self.root, ["a.xml", "b.xml"]), [])
        with self.assertRaises(baseline.Unusable):
            baseline.load(self.path, self.root, None)

    def test_a_baseline_that_cannot_stand_for_the_tree_is_refused(self):
        row = {"code": "DEAD_TRANSITION", "file": "app/p.xml", "line": 3, "message": "m"}
        cases = {
            "another format": {"format": 2},
            "another root": {"root": "/somewhere/else"},
            "another scope": {"files": ["app/p.xml"]},
            "no findings list": {"findings": "none"},
            "an unknown code": {"findings": [dict(row, code="NOT_A_CODE")]},
            "a code that is no string": {"findings": [dict(row, code=["DEAD_TRANSITION"])]},
            "a row that is no object": {"findings": ["DEAD_TRANSITION"]},
            "a line that is text": {"findings": [dict(row, line="3")]},
            "a message that is no string": {"findings": [dict(row, message=None)]},
        }
        for name, overrides in cases.items():
            with self.subTest(name):
                self.rows(**overrides)
                with self.assertRaises(baseline.Unusable):
                    baseline.load(self.path, self.root, None)
        self.rows()
        self.assertEqual(len(baseline.load(self.path, self.root, None)), 1)  # and the unchanged rows load


@unittest.skipUnless(helpers.have_git() and helpers.have_dependencies(), "needs git, lxml and jsonschema")
class FromGit(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = helpers.make_repo(self.tmp / "estate")
        self.root = helpers.make_root(self.repo / "Web" / "workspaces", {
            ".dgf-factory/config.yaml": "dgf:\n  version: unknown\n",
            "app/FM/_PROCESS/Case/process.xml": process(),
            "app/FM/_PROCESS/Other/process.xml": process("Other", action="WORKFLOW:/Notify"),
            "app/FM/_PROCESS/Broken/process.xml": process("Broken", target="Nowhere"),  # pre-existing error
            "app/FM/_WORKFLOW/Notify/_workflow.xml": WORKFLOW,
            "webasm/FM/.keep": "",
        })
        helpers.commit_all(self.repo, "the estate")
        helpers.git(self.repo, "checkout", "-q", "-b", "feature/x")
        self.plan = helpers.make_root(self.root, {".dgf-factory/plans/feature-x.md": PLAN}) / \
            ".dgf-factory/plans/feature-x.md"

    def check(self, *extra, base="main"):
        code, out, err = helpers.run_cli("check_change.py", "--workspaces-root", self.root, "--plan", self.plan,
                                         "--base", base, *extra)
        self.out = out
        return code

    def found(self, label, code):
        return [line for line in self.out.splitlines() if line.startswith(f"{label} {code} ")]

    def test_a_pre_existing_error_in_an_untouched_file_does_not_block(self):
        self.assertEqual(self.check(), 0, self.out)
        self.assertTrue(self.found("INFO", "PRE_EXISTING"), self.out)
        self.assertIn("[DEAD_TRANSITION]", self.found("INFO", "PRE_EXISTING")[0])
        self.assertIn("new: 0 error(s), 0 warning(s); pre-existing: 1; fixed: 0", self.out)

    def test_an_added_dead_transition_blocks(self):
        (self.root / "app/FM/_PROCESS/Case/process.xml").write_text(process(target="Closed"), encoding="utf-8")
        self.assertEqual(self.check(), 1, self.out)
        self.assertEqual(len(self.found("ERROR", "DEAD_TRANSITION")), 1, self.out)

    def test_deleting_a_workflow_an_untouched_process_uses_is_new(self):
        helpers.git(self.repo, "rm", "-q", "Web/workspaces/app/FM/_WORKFLOW/Notify/_workflow.xml")
        self.assertEqual(self.check(), 1, self.out)
        self.assertTrue(self.found("ERROR", "WORKFLOW_UNRESOLVED"), self.out)

    def test_fixing_a_pre_existing_error_is_credited(self):
        (self.root / "app/FM/_PROCESS/Broken/process.xml").write_text(process("Broken"), encoding="utf-8")
        self.assertIn(self.check(), (0, 2), self.out)
        self.assertTrue(self.found("INFO", "FIXED"), self.out)

    def test_lines_inserted_above_a_finding_keep_it_pre_existing(self):
        path = self.root / "app/FM/_PROCESS/Broken/process.xml"
        text = path.read_text(encoding="utf-8").replace("<States>", "<!-- one -->\n  <!-- two -->\n  <States>")
        path.write_text(text, encoding="utf-8")
        self.assertIn(self.check(), (0, 2), self.out)
        self.assertFalse(self.found("ERROR", "DEAD_TRANSITION"), self.out)
        self.assertTrue(self.found("INFO", "PRE_EXISTING"), self.out)

    def test_a_second_copy_of_a_pre_existing_finding_is_new(self):
        # The same transition twice: two findings with one key, so only the multiset rule tells them apart.
        path = self.root / "app/FM/_PROCESS/Broken/process.xml"
        text = path.read_text(encoding="utf-8")
        once = '        <Transition state="Nowhere" />\n'
        path.write_text(text.replace(once, once * 2), encoding="utf-8")
        self.assertEqual(self.check(), 1, self.out)
        new, pre = self.found("ERROR", "DEAD_TRANSITION"), self.found("INFO", "PRE_EXISTING")
        self.assertEqual((len(new), len(pre)), (1, 1), self.out)
        self.assertEqual(new[0].split(" ", 3)[3], pre[0].split("] ", 1)[1], self.out)  # the same message

    def test_files_limit_the_run(self):
        (self.root / "app/FM/_PROCESS/Case/process.xml").write_text(process(target="Closed"), encoding="utf-8")
        self.assertEqual(self.check("--files", "app/FM/_PROCESS/Other/process.xml"), 0, self.out)
        self.assertIn("Validated: 1 file(s)", self.out)

    def test_no_merge_base_counts_every_finding(self):
        empty_tree = helpers.git(self.repo, "hash-object", "-t", "tree", "/dev/null").strip()
        unrelated = helpers.git(self.repo, "commit-tree", empty_tree, "-m", "unrelated history").strip()
        helpers.git(self.repo, "update-ref", "refs/heads/unrelated", unrelated)
        self.assertEqual(self.check(base="unrelated"), 1, self.out)
        self.assertIn("NOT RUN: baseline (no merge-base; every finding counts as new)", self.out)
        self.assertIn("NOT RUN: change-scope", self.out)
        self.assertTrue(self.found("ERROR", "DEAD_TRANSITION"), self.out)


if __name__ == "__main__":
    unittest.main()
