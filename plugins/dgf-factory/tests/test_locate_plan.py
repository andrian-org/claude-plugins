"""locate_plan.py: the workspaces root and the active plan (ADR 0017 §6)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

CONFIG = ".dgf-factory/config.yaml"
ACTIVE = "---\nplan_format: 1\nmode: {mode}\nbranch: {branch}\ncreated: 2026-09-25\naffects_workspaces: [zims]\n" \
         "---\n\n## Tasks\n\n- [{mark}] Task 1: x\n  - kind: config\n  - files: zims/FM/_PROCESS/P/process.xml\n"


def plan_text(branch="feature/x", mode="full", done=False):
    return ACTIVE.format(mode=mode, branch=branch, mark="x" if done else " ")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "estate" / "Web" / "workspaces",
                                      {CONFIG: "dgf:\n  version: unknown\n", "zims/FM/_PROCESS/P/process.xml": "<p/>"})
        self.plans = self.root / ".dgf-factory" / "plans"

    def locate(self, *args, cwd=None):
        return helpers.run_cli("locate_plan.py", *args, cwd=cwd or self.root)

    def add(self, rel, text):
        path = self.plans / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class Root(Base):
    def test_found_from_a_subdirectory(self):
        code, out, _ = self.locate("--root-only", cwd=self.root / "zims" / "FM")
        self.assertEqual(code, 0)
        self.assertIn(f"ROOT: {self.root}", out)

    def test_found_below_the_working_directory(self):
        code, out, _ = self.locate("--root-only", cwd=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn(f"ROOT: {self.root}", out)

    def test_the_search_stops_four_levels_down(self):
        deep = helpers.make_root(self.tmp / "a" / "b" / "c" / "d" / "e" / "f", {CONFIG: ""})  # 5 below `a`
        code, out, _ = self.locate("--root-only", cwd=self.tmp / "a")
        self.assertEqual(code, 1)
        self.assertIn("ROOT_NOT_SET_UP", out)
        self.assertEqual(self.locate("--root-only", cwd=self.tmp / "a" / "b")[0], 0)  # 4 below `b`
        self.assertEqual(self.locate("--root-only", cwd=deep.parent)[0], 0)

    def test_two_roots_below_are_ambiguous(self):
        helpers.make_root(self.tmp / "other", {CONFIG: ""})
        code, out, _ = self.locate("--root-only", cwd=self.tmp)
        self.assertEqual(code, 1)
        self.assertIn("ROOT_AMBIGUOUS", out)

    def test_an_explicit_root_without_config(self):
        bare = helpers.make_root(self.tmp / "bare", {"zims/FM/x.xml": "<x/>"})
        code, out, _ = self.locate("--workspaces-root", bare, "--root-only", cwd=self.tmp)
        self.assertEqual(code, 1)
        self.assertIn("ROOT_NOT_SET_UP", out)


class Discovery(Base):
    def test_the_branch_plan(self):
        self.add("feature-x.md", plan_text())
        code, out, _ = self.locate("--branch", "feature/x")
        self.assertEqual(code, 0, out)
        self.assertIn("PLAN: .dgf-factory/plans/feature-x.md mode=full source=branch", out)

    def test_the_branch_bundle(self):
        self.add("feature-x/index.md", plan_text(mode="ultra"))
        code, out, _ = self.locate("--branch", "feature/x")
        self.assertEqual(code, 0)
        self.assertIn("PLAN: .dgf-factory/plans/feature-x/index.md mode=ultra source=branch", out)

    def test_a_file_and_a_bundle_for_one_branch_are_ambiguous(self):
        self.add("feature-x.md", plan_text())
        self.add("feature-x/index.md", plan_text(mode="ultra"))
        code, out, _ = self.locate("--branch", "feature/x")
        self.assertEqual(code, 1)
        self.assertIn("PLAN_AMBIGUOUS", out)

    def test_the_lone_active_plan_is_a_fallback(self):
        self.add("feature-a.md", plan_text("feature/a"))
        self.add("feature-done.md", plan_text("feature/done", done=True))
        code, out, _ = self.locate("--branch", "feature/other")
        self.assertEqual(code, 2)
        self.assertIn("source=lone", out)
        self.assertIn("WARN PLAN_FALLBACK", out)

    def test_several_active_plans_are_ambiguous(self):
        self.add("feature-a.md", plan_text("feature/a"))
        self.add("feature-b.md", plan_text("feature/b"))
        code, out, _ = self.locate("--branch", "feature/other")
        self.assertEqual(code, 1)
        self.assertIn("PLAN_AMBIGUOUS", out)

    def test_the_fast_plan_is_the_last_fallback(self):
        (self.root / ".dgf-factory" / "PLAN.md").write_text(plan_text("none", mode="fast"), encoding="utf-8")
        code, out, _ = self.locate("--branch", "feature/other")
        self.assertEqual(code, 2)
        self.assertIn("PLAN: .dgf-factory/PLAN.md mode=fast source=fast", out)

    def test_custom_paths(self):
        self.add("../custom/feature-x.md", plan_text())
        code, out, _ = self.locate("--branch", "feature/x", "--plans-dir", ".dgf-factory/custom")
        self.assertEqual(code, 0)
        self.assertIn(".dgf-factory/custom/feature-x.md", out)

    def test_nothing_to_find(self):
        code, out, _ = self.locate("--branch", "feature/x")
        self.assertEqual(code, 1)
        self.assertIn("PLAN_NOT_FOUND", out)

    def test_list(self):
        self.add("feature-a.md", plan_text("feature/a"))
        self.add("feature-b.md", "# no frontmatter\n")
        self.add("feature-c/index.md", plan_text("feature/c", mode="ultra", done=True))
        code, out, _ = self.locate("--list")
        self.assertEqual(code, 0)
        self.assertIn("PLAN: .dgf-factory/plans/feature-a.md mode=full progress=0/1", out)
        self.assertIn("PLAN: .dgf-factory/plans/feature-b.md mode=unreadable progress=unreadable", out)
        self.assertIn("PLAN: .dgf-factory/plans/feature-c/index.md mode=ultra progress=1/1", out)


@unittest.skipUnless(helpers.have_git(), "git is not installed")
class FromGit(Base):
    def setUp(self):
        super().setUp()
        self.repo = helpers.make_repo(self.tmp / "estate")
        helpers.commit_all(self.repo, "the estate")

    def test_the_current_branch_is_read_from_the_root(self):
        helpers.git(self.repo, "checkout", "-q", "-b", "feature/x")
        self.add("feature-x.md", plan_text())
        code, out, _ = self.locate()
        self.assertEqual(code, 0, out)
        self.assertIn("source=branch", out)

    def test_a_detached_head_falls_back(self):
        self.add("feature-x.md", plan_text())
        helpers.git(self.repo, "checkout", "-q", "--detach")
        code, out, _ = self.locate()
        self.assertEqual(code, 2)
        self.assertIn("no branch is checked out", out)
        self.assertIn("source=lone", out)


if __name__ == "__main__":
    unittest.main()
