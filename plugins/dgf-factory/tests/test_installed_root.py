"""An installed project: the files `dgf-factory setup` wrote are not the estate's (ADR 0029 §2).

The runtime under `.dgf-factory/runtime/` holds DGF-shaped files — the scaffold's workspace
templates among them — and the harness folders and MCP files sit beside the workspaces. The
walks skip dot-directories; the change checks skip the install footprint the receipt lists.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
import check_change
from lib import install_receipt

PROCESS = "app/FM/_PROCESS/Case/process.xml"
GOOD_PROCESS = (helpers.PLUGIN_ROOT / "tests" / "test_check_change.py").read_text(encoding="utf-8") \
    .split('GOOD_PROCESS = """', 1)[1].split('"""', 1)[0]
RECEIPT = {
    "tool": "dgf-factory",
    "version": "0.2.0",
    "harnesses": [{"id": "claude", "selected": True}],
    "files": {
        ".claude/skills/dgf-plan/SKILL.md": {"source": "skills/dgf-plan/SKILL.md", "sourceHash": "a", "installedHash": "b"},
        ".dgf-factory/runtime/skills/dgf-scaffold/templates/workspace/FM/_PROCESS/Case/process.xml":
            {"source": "skills/dgf-scaffold/templates/workspace/FM/_PROCESS/Case/process.xml",
             "sourceHash": "c", "installedHash": "d"},
    },
    "mcp": {"claude": {"file": ".mcp.json", "key": "dgf-mcp", "entryHash": "e"}},
}
ROOT = {
    ".dgf-factory/config.yaml": "dgf:\n  version: unknown\n",
    ".dgf-factory/install.json": json.dumps(RECEIPT),
    ".dgf-factory/runtime/skills/dgf-scaffold/templates/workspace/FM/_PROCESS/Case/process.xml": "<broken",
    ".claude/skills/dgf-plan/SKILL.md": "---\nname: dgf-plan\n---\n",
    ".mcp.json": "{}\n",
    PROCESS: GOOD_PROCESS,
}
PLAN = """---
plan_format: 1
mode: full
branch: feature/x
created: 2026-10-26
affects_workspaces: [app]
---

## Tasks

- [ ] Task 1: Change the process
  - kind: config
  - files: app/FM/_PROCESS/Case/process.xml
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "root", ROOT)
        self.plan = self.root / ".dgf-factory" / "plans" / "feature-x.md"
        self.plan.parent.mkdir(parents=True, exist_ok=True)
        self.plan.write_text(PLAN, encoding="utf-8")

    def check(self, *changed):
        code, out, err = helpers.run_cli("check_change.py", "--workspaces-root", self.root, "--plan", self.plan,
                                         "--skip-validators", "--changed", *changed)
        self.out = out
        return code, [line.split()[1] for line in out.splitlines() if line.split()[:1] in (["ERROR"], ["WARN"])]


class Footprint(Base):
    def test_footprint_lists_the_managed_files_and_the_mcp_file(self):
        self.assertEqual(install_receipt.footprint(self.root), {
            ".claude/skills/dgf-plan/SKILL.md",
            ".dgf-factory/runtime/skills/dgf-scaffold/templates/workspace/FM/_PROCESS/Case/process.xml",
            ".mcp.json",
        })

    def test_no_receipt_is_an_empty_footprint(self):
        (self.root / ".dgf-factory" / "install.json").unlink()
        self.assertEqual(install_receipt.footprint(self.root), frozenset())

    def test_a_receipt_with_a_path_out_of_the_project_is_refused(self):
        bad = dict(RECEIPT, files={"../escape.md": {}})
        (self.root / ".dgf-factory" / "install.json").write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(install_receipt.ReceiptError):
            install_receipt.footprint(self.root)

    def test_each_wrong_type_is_refused_not_a_traceback(self):
        for bad in ([], {"files": []}, {"files": {}, "mcp": {"claude": "x"}}, {"files": {"": {}}},
                    {"files": {}, "mcp": {"claude": {"file": 3}}}):
            (self.root / ".dgf-factory" / "install.json").write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(install_receipt.ReceiptError, msg=repr(bad)):
                install_receipt.footprint(self.root)


class ChangeChecks(Base):
    def test_managed_skill_and_mcp_changes_are_not_outside_a_workspace(self):
        code, found = self.check(f"M:{PROCESS}", "M:.claude/skills/dgf-plan/SKILL.md", "M:.mcp.json")
        self.assertEqual((code, found), (0, []), self.out)
        self.assertIn("CHANGED: 1", self.out)

    def test_an_unlisted_harness_file_is_still_reported(self):
        code, found = self.check(f"M:{PROCESS}", "A:.claude/other.md")
        self.assertEqual(code, 2, self.out)
        self.assertIn("CHANGE_OUTSIDE_WORKSPACE", found)

    def test_an_unreadable_receipt_is_exit_3(self):
        (self.root / ".dgf-factory" / "install.json").write_text("{not json", encoding="utf-8")
        code, _, err = helpers.run_cli("check_change.py", "--workspaces-root", self.root, "--plan", self.plan,
                                       "--skip-validators", "--changed", f"M:{PROCESS}")
        self.assertEqual(code, 3, err)
        self.assertIn("INSTALL_RECEIPT_UNREADABLE", err)
        self.assertNotIn("Traceback", err)

    def test_own_changes_without_a_root_keeps_the_old_behaviour(self):
        from lib import git
        kept = check_change.own_changes([git.Change("M", ".mcp.json"), git.Change("M", ".dgf-factory/x.md")])
        self.assertEqual([c.path for c in kept], [".mcp.json"])


class Walks(Base):
    """The walks already skip dot-directories; these pin it for the runtime's templates."""

    def test_the_inventory_counts_only_the_real_workspace(self):
        code, out, err = helpers.run_cli("inventory_root.py", "--workspaces-root", self.root)
        self.assertIn(code, (0, 2), err)
        workspaces = [line for line in out.splitlines() if line.startswith("WORKSPACE:")]
        self.assertEqual(len(workspaces), 1, out)
        self.assertIn("app", workspaces[0])
        self.assertNotIn("runtime", out)

    def test_validating_the_root_never_reads_the_runtime(self):
        if not helpers.have_dependencies():
            self.skipTest("lxml / jsonschema not installed")
        code, out, err = helpers.run_cli("validate_process.py", "--workspaces-root", self.root, "--all")
        self.assertNotIn(".dgf-factory", out + err)
        self.assertNotIn(".claude", out + err)


if __name__ == "__main__":
    unittest.main()
