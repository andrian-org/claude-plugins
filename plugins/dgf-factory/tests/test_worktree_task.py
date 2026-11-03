"""worktree_task.py and lib/worktree.py over real linked worktrees (`git worktree add`) (ADR 0033 §3)."""

import json
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import worktree

A = "zims/FM/_COMPONENTS/Button/a.json"
B = "zims/FM/_COMPONENTS/Button/b.json"
NEW = "zims/FM/_COMPONENTS/Button/new.json"
OLD = "zims/js/old.js"
PROCESS = "zims/FM/_PROCESS/P/process.xml"
PLAN = ".dgf-factory/plans/feature-x.md"
PLAN_TEXT = """---
plan_format: 1
mode: full
branch: feature/x
created: 2026-11-03
affects_workspaces: [zims]
---

## Tasks

- [ ] Task 1: the button
  - kind: config
  - files: {a}, {new}
  - deletes: {old}
- [ ] Task 2: the other button
  - kind: config
  - files: {b}
""".format(a=A, new=NEW, old=OLD, b=B)


def estate(prefix=""):
    """The committed files, with the workspaces root at `prefix` below the toplevel."""
    files = {A: '{"type": "Button"}\n', B: '{"type": "Button", "n": 2}\n', OLD: "// old\n",
             PROCESS: "<process/>\n", PLAN: PLAN_TEXT, ".dgf-factory/config.yaml": "dgf:\n  version: unknown\n",
             ".dgf-factory/runtime/scripts/x.py": "print(1)\n"}
    found = {f"{prefix}{rel}": text for rel, text in files.items()}
    found[".gitignore"] = "ignored.txt\n"
    found["README.md"] = "estate\n"
    return found


@unittest.skipUnless(helpers.have_git(), "git is not installed")
class Base(unittest.TestCase):
    PREFIX = ""  # the workspaces root below the git toplevel

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = helpers.make_repo(self.tmp / "estate", estate(self.PREFIX))
        self.first = helpers.git(self.repo, "rev-parse", "HEAD").strip()
        self.root = self.repo / self.PREFIX if self.PREFIX else self.repo

    # --- plumbing ---------------------------------------------------------------

    def add_worktree(self, name="a", at="HEAD", detach=False):
        path = self.repo / ".claude" / "worktrees" / name
        if detach:
            helpers.git(self.repo, "worktree", "add", "-q", "--detach", path, at)
        else:
            helpers.git(self.repo, "worktree", "add", "-q", "-b", f"worktree-{name}", path, at)
        return path.resolve()

    def wroot(self, wt):
        return wt / self.PREFIX if self.PREFIX else wt

    def sync(self, wt, cwd=None):
        return helpers.run_cli("worktree_task.py", "--sync", "--from", self.root, "--worktree", wt, cwd=cwd)

    def merge(self, wt, task=1, *extra):
        return helpers.run_cli("worktree_task.py", "--merge", "--from", self.wroot(wt), "--to", self.root,
                               "--plan", self.root / PLAN, "--task", task, *extra)

    def write(self, base, rel, text):
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def read(self, base, rel):
        return (base / rel).read_text(encoding="utf-8")

    def ok(self, result):
        code, out, err = result
        self.assertEqual(code, 0, out + err)
        return out

    def refused(self, result, code_expected, finding):
        code, out, err = result
        self.assertEqual(code, code_expected, out + err)
        self.assertIn(f" {finding} ", out)
        return out


class Sync(Base):
    def test_a_clean_worktree_at_an_older_commit_is_moved_to_the_main_head(self):
        self.write(self.root, "zims/FM/_COMPONENTS/Button/later.json", "{}\n")
        head = helpers.commit_all(self.repo, "later")
        wt = self.add_worktree(at=self.first)
        out = self.ok(self.sync(wt))
        self.assertIn(f"HEAD: {head} (moved from {self.first})", out)
        self.assertEqual(helpers.git(wt, "rev-parse", "HEAD").strip(), head)
        self.assertEqual(helpers.git(self.repo, "rev-parse", "worktree-a").strip(), head, "its own branch moved")
        self.assertTrue((wt / "zims/FM/_COMPONENTS/Button/later.json").is_file())
        self.assertIn(f"WORKTREE ROOT: {wt}", out)

    def test_a_dirty_worktree_at_another_commit_is_refused(self):
        self.write(self.root, "zims/later.txt", "x\n")
        helpers.commit_all(self.repo, "later")
        wt = self.add_worktree(at=self.first)
        self.write(wt, "zims/mine.txt", "the worker's own\n")
        self.refused(self.sync(wt), 1, "WORKTREE_HEAD_MISMATCH")
        self.assertEqual(helpers.git(wt, "rev-parse", "HEAD").strip(), self.first)
        self.assertTrue((wt / "zims/mine.txt").is_file())
        self.assertFalse((Path(helpers.git(wt, "rev-parse", "--absolute-git-dir").strip()) / "dgf-sync.json").exists())

    def test_the_main_worktree_and_another_repository_are_not_linked(self):
        self.refused(self.sync(self.repo), 3, "WORKTREE_NOT_LINKED")
        other = helpers.make_repo(self.tmp / "other", {"x.txt": "x\n"})
        self.refused(self.sync(other), 3, "WORKTREE_NOT_LINKED")
        plain = self.tmp / "plain"
        plain.mkdir()
        self.refused(self.sync(plain), 3, "WORKTREE_NOT_LINKED")

    def test_the_dirty_state_is_copied_and_recorded_in_the_worktrees_git_dir(self):
        self.write(self.root, A, '{"type": "Button", "edited": true}\n')          # modified, unstaged
        self.write(self.root, "zims/FM/_COMPONENTS/Button/staged.json", "{}\n")   # added, staged
        helpers.git(self.repo, "add", f"{self.PREFIX}zims/FM/_COMPONENTS/Button/staged.json")
        self.write(self.root, "zims/FM/_COMPONENTS/Button/untracked.json", "{}\n")
        (self.root / PROCESS).unlink()                                              # deleted, unstaged
        helpers.git(self.repo, "rm", "-q", f"{self.PREFIX}{OLD}")                  # deleted, staged
        script = self.write(self.root, "zims/js/run.sh", "#!/bin/sh\n")
        script.chmod(0o755)
        os.symlink("FM/_COMPONENTS/Button/a.json", self.root / "zims/link.json")
        self.write(self.root, ".dgf-factory/runtime/scripts/x.py", "print(2)\n")   # the runtime: never copied
        self.write(self.root, ".dgf-factory/runtime/scripts/y.py", "print(3)\n")
        self.write(self.root, "zims/ignored.txt", "ignored\n")                    # ignored: never copied
        self.write(self.repo, ".claude/worktrees/notes.txt", "not the estate's\n")
        wt = self.add_worktree()
        out = self.ok(self.sync(wt))
        self.assertIn("SYNCED: 5 file(s), 2 deletion(s)", out)
        self.assertEqual(self.read(wt, A), '{"type": "Button", "edited": true}\n')
        self.assertTrue((wt / "zims/FM/_COMPONENTS/Button/staged.json").is_file())
        self.assertTrue((wt / "zims/FM/_COMPONENTS/Button/untracked.json").is_file())
        self.assertFalse((wt / PROCESS).exists())
        self.assertFalse((wt / OLD).exists())
        self.assertEqual(stat.S_IMODE((wt / "zims/js/run.sh").stat().st_mode), 0o755)
        self.assertTrue(os.path.islink(wt / "zims/link.json"))
        self.assertEqual(os.readlink(wt / "zims/link.json"), "FM/_COMPONENTS/Button/a.json")
        self.assertEqual(self.read(wt, ".dgf-factory/runtime/scripts/x.py"), "print(1)\n")
        self.assertFalse((wt / ".dgf-factory/runtime/scripts/y.py").exists())
        self.assertFalse((wt / "zims/ignored.txt").exists())
        self.assertFalse((wt / ".claude/worktrees/notes.txt").exists())
        git_dir = Path(helpers.git(wt, "rev-parse", "--absolute-git-dir").strip())
        record = json.loads((git_dir / "dgf-sync.json").read_text(encoding="utf-8"))
        self.assertEqual(record["head"], self.first)
        self.assertEqual(Path(record["main"]), self.repo.resolve())
        self.assertIsNone(record["files"][PROCESS])
        self.assertIsNone(record["files"][OLD])
        self.assertEqual(len(record["files"][A]), 64)
        self.assertNotIn("dgf-sync", helpers.git(wt, "status", "--porcelain", "--untracked-files=all"))

    def test_the_helpers_read_both_trees(self):
        wt = self.add_worktree()
        self.assertFalse(worktree.is_linked(self.repo))
        self.assertTrue(worktree.is_linked(wt))
        self.assertEqual(worktree.git_dirs(wt)[1], worktree.git_dirs(self.repo)[1])
        listed = {entry.path: entry for entry in worktree.worktrees(self.repo)}
        self.assertEqual(listed[wt].branch, "worktree-a")
        self.assertEqual(listed[self.repo.resolve()].branch, "main")
        self.assertFalse(listed[wt].locked)
        (wt / "zims/x.txt").write_text("x\n", encoding="utf-8")
        (wt / A).unlink()
        self.assertEqual(sorted(worktree.status(wt)), [(" D", A), ("??", "zims/x.txt")])


class Merge(Base):
    def synced(self, name="a", **kw):
        wt = self.add_worktree(name, **kw)
        self.ok(self.sync(wt))
        return wt

    def test_the_declared_files_are_merged_with_their_mode(self):
        wt = self.synced()
        (self.wroot(wt) / A).write_text('{"type": "Button", "by": "worker"}\n', encoding="utf-8")
        (self.wroot(wt) / A).chmod(0o755)
        self.write(self.wroot(wt), NEW, '{"type": "Button"}\n')
        (self.wroot(wt) / OLD).unlink()
        out = self.ok(self.merge(wt))
        self.assertIn(f"MERGED: M {A}", out)
        self.assertIn(f"MERGED: A {NEW}", out)
        self.assertIn(f"MERGED: D {OLD}", out)
        self.assertEqual(self.read(self.root, A), '{"type": "Button", "by": "worker"}\n')
        self.assertEqual(stat.S_IMODE((self.root / A).stat().st_mode), 0o755)
        self.assertTrue((self.root / NEW).is_file())
        self.assertFalse((self.root / OLD).exists())
        self.assertIn("CHECKS RUN: worktree-linked, sync-record, scope, main-unchanged, merge", out)
        self.assertFalse(list((self.root / "zims/FM/_COMPONENTS/Button").glob(".*.tmp")))

    def test_an_undeclared_file_refuses_the_whole_merge(self):
        wt = self.synced()
        self.write(self.wroot(wt), A, "{}\n")
        self.write(self.wroot(wt), B, "{}\n")
        out = self.refused(self.merge(wt), 1, "WORKTREE_UNDECLARED_FILE")
        self.assertIn(f"{B} was modified, and Task 1 does not list it in `files`", out)
        self.assertEqual(self.read(self.root, A), '{"type": "Button"}\n', "nothing is copied")
        self.assertNotIn("MERGED:", out)

    def test_the_plan_is_never_merged(self):
        wt = self.synced()
        self.write(self.wroot(wt), A, "{}\n")
        plan = self.wroot(wt) / PLAN
        plan.write_text(plan.read_text(encoding="utf-8").replace("- [ ] Task 1", "- [x] Task 1"), encoding="utf-8")
        out = self.refused(self.merge(wt), 1, "WORKTREE_UNDECLARED_FILE")
        self.assertIn(f"{PLAN} is the plan — only the coordinator ticks it", out)
        self.assertIn("- [ ] Task 1", self.read(self.root, PLAN))

    def test_a_files_path_deleted_and_a_deletes_path_modified_are_refused(self):
        wt = self.synced()
        (self.wroot(wt) / A).unlink()
        self.write(self.wroot(wt), OLD, "// changed, not deleted\n")
        out = self.refused(self.merge(wt), 1, "WORKTREE_UNDECLARED_FILE")
        self.assertIn(f"{A} was deleted, but Task 1 lists it in `files`", out)
        self.assertIn(f"{OLD} was modified, but Task 1 lists it in `deletes`", out)
        self.assertTrue((self.root / A).is_file())

    def test_a_symlink_is_never_merged(self):
        wt = self.synced()
        os.symlink("a.json", self.wroot(wt) / NEW)
        out = self.refused(self.merge(wt), 1, "WORKTREE_UNDECLARED_FILE")
        self.assertIn("a symlink is never merged", out)
        self.assertFalse(os.path.lexists(self.root / NEW))

    def test_a_main_tree_changed_since_the_sync_is_refused(self):
        self.write(self.root, A, '{"dirty": "at sync"}\n')
        wt = self.synced()
        self.write(self.root, A, '{"dirty": "after sync"}\n')     # a synced path, changed again
        self.write(self.root, NEW, '{"main": "made it"}\n')       # a path main did not have at sync
        self.write(self.wroot(wt), A, '{"worker": 1}\n')
        self.write(self.wroot(wt), NEW, '{"worker": 2}\n')
        out = self.refused(self.merge(wt), 1, "WORKTREE_MAIN_CHANGED")
        self.assertEqual(out.count("WORKTREE_MAIN_CHANGED"), 2, out)
        self.assertEqual(self.read(self.root, A), '{"dirty": "after sync"}\n')

    def test_a_synced_path_the_main_tree_left_alone_merges(self):
        self.write(self.root, A, '{"dirty": "at sync"}\n')
        wt = self.synced()
        self.write(self.wroot(wt), A, '{"worker": 1}\n')
        out = self.ok(self.merge(wt))
        self.assertIn(f"MERGED: M {A}", out)
        self.assertEqual(self.read(self.root, A), '{"worker": 1}\n')

    def test_a_main_head_that_moved_is_refused(self):
        wt = self.synced()
        self.write(self.wroot(wt), A, "{}\n")
        self.write(self.root, "zims/later.txt", "x\n")
        helpers.commit_all(self.repo, "a commit during the layer")
        self.refused(self.merge(wt), 1, "WORKTREE_HEAD_MISMATCH")
        self.assertEqual(self.read(self.root, A), '{"type": "Button"}\n')

    def test_no_sync_record_is_refused(self):
        wt = self.add_worktree()
        self.write(wt, A, "{}\n")
        self.refused(self.merge(wt), 1, "WORKTREE_SYNC_MISSING")

    def test_autocrlf_never_reads_as_a_main_tree_change(self):
        helpers.git(self.repo, "config", "core.autocrlf", "true")
        (self.root / A).unlink()
        helpers.git(self.repo, "checkout", "--", f"{self.PREFIX}{A}")
        self.assertIn(b"\r\n", (self.root / A).read_bytes(), "the checkout has CRLF; its blob has LF")
        self.assertEqual(helpers.git(self.repo, "status", "--porcelain"), "")
        wt = self.synced()
        self.write(self.wroot(wt), A, '{"worker": 1}\n')
        out = self.ok(self.merge(wt))
        self.assertIn(f"MERGED: M {A}", out)

    def test_an_addition_over_a_file_the_main_tree_ignores_is_refused(self):
        wt = self.synced()
        self.write(self.root, "zims/FM/_COMPONENTS/Button/.gitignore", "new.json\n")
        self.write(self.root, NEW, '{"main": "ignored, but there"}\n')
        self.assertNotIn("new.json", helpers.git(self.repo, "status", "--porcelain", "--untracked-files=all"))
        self.write(self.wroot(wt), NEW, '{"worker": 1}\n')
        out = self.refused(self.merge(wt), 1, "WORKTREE_MAIN_CHANGED")
        self.assertIn(f"{NEW} changed in the main tree since the sync", out)
        self.assertEqual(self.read(self.root, NEW), '{"main": "ignored, but there"}\n')

    def test_an_addition_whose_name_differs_only_in_case_is_refused(self):
        probe = self.tmp / "CaseProbe"
        probe.write_text("", encoding="utf-8")
        if not (self.tmp / "caseprobe").exists():
            self.skipTest("this disk tells names apart by case: the two are two files")
        wt = self.synced()
        upper = NEW.replace("new.json", "NEW.json")
        self.write(self.root, upper, '{"main": "made it"}\n')
        self.write(self.wroot(wt), NEW, '{"worker": 1}\n')
        self.refused(self.merge(wt), 1, "WORKTREE_MAIN_CHANGED")
        self.assertEqual(self.read(self.root, upper), '{"main": "made it"}\n')

    def hidden_by(self, bit):
        """A main-tree edit of A that `git status` cannot see, made after the sync; the worker edits A too."""
        wt = self.synced()
        helpers.git(self.repo, "update-index", bit, f"{self.PREFIX}{A}")
        self.write(self.root, A, '{"main": "hidden"}\n')
        self.assertNotIn(A, helpers.git(self.repo, "status", "--porcelain"), "status cannot see it")
        self.write(self.wroot(wt), A, '{"worker": 1}\n')
        self.refused(self.merge(wt), 1, "WORKTREE_MAIN_CHANGED")
        self.assertEqual(self.read(self.root, A), '{"main": "hidden"}\n')

    def test_a_change_assume_unchanged_hides_is_refused(self):
        self.hidden_by("--assume-unchanged")

    def test_a_change_skip_worktree_hides_is_refused(self):
        self.hidden_by("--skip-worktree")

    def test_cleanup_removes_the_worktree_and_its_branch(self):
        wt = self.synced()
        self.write(self.wroot(wt), A, "{}\n")
        out = self.ok(self.merge(wt, 1, "--cleanup"))
        self.assertIn(f"REMOVED: {wt} (worktree-a)", out)
        self.assertFalse(wt.exists())
        self.assertEqual(helpers.git(self.repo, "branch", "--list", "worktree-a"), "")

    def test_cleanup_of_a_detached_worktree(self):
        wt = self.synced("d", detach=True)
        out = self.ok(self.merge(wt, 1, "--cleanup"))
        self.assertIn(f"REMOVED: {wt} (detached)", out)
        self.assertFalse(wt.exists())

    def test_a_locked_worktree_is_left_in_place(self):
        wt = self.synced()
        self.write(self.wroot(wt), A, "{}\n")
        helpers.git(self.repo, "worktree", "lock", wt)
        out = self.ok(self.merge(wt, 1, "--cleanup"))
        self.assertIn(f"REMOVED: none — {wt} is locked", out)
        self.assertTrue(wt.is_dir())
        self.assertEqual(self.read(self.root, A), "{}\n", "the merge itself happened")

    def test_nothing_changed_merges_nothing(self):
        wt = self.synced()
        out = self.ok(self.merge(wt, 2))
        self.assertNotIn("MERGED:", out)


class WithoutDependencies(Base):
    def test_sync_and_merge_run_without_the_validator_dependencies(self):
        wt = self.add_worktree()
        code, out, err = helpers.run_cli_blocking("worktree_task.py", "--sync", "--from", self.root, "--worktree", wt)
        self.assertEqual(code, 0, out + err)
        self.write(wt, A, "{}\n")
        code, out, err = helpers.run_cli_blocking("worktree_task.py", "--merge", "--from", wt, "--to", self.root,
                                                  "--plan", self.root / PLAN, "--task", "1")
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"MERGED: M {A}", out)


class SubfolderRoot(Merge):
    """The workspaces root two folders below the git toplevel, as in a real estate."""
    PREFIX = "Web/workspaces/"

    def test_paths_are_root_relative_and_the_root_is_found_in_the_worktree(self):
        wt = self.add_worktree()
        out = self.ok(self.sync(wt))
        self.assertIn(f"WORKTREE ROOT: {wt / 'Web/workspaces'}", out)

    def test_a_change_outside_the_root_is_refused(self):
        wt = self.synced()
        self.write(self.wroot(wt), A, "{}\n")
        self.write(wt, "README.md", "changed outside the root\n")
        out = self.refused(self.merge(wt), 1, "WORKTREE_UNDECLARED_FILE")
        self.assertIn("README.md is outside the workspaces root", out)

    def test_the_roots_runtime_is_never_synced(self):
        self.write(self.root, ".dgf-factory/runtime/scripts/x.py", "print(2)\n")
        self.write(self.root, ".dgf-factory/RULES.md", "# rules\n")
        wt = self.add_worktree()
        out = self.ok(self.sync(wt))
        self.assertIn("SYNCED: 1 file(s), 0 deletion(s)", out)
        self.assertEqual(self.read(self.wroot(wt), ".dgf-factory/runtime/scripts/x.py"), "print(1)\n")
        self.assertTrue((self.wroot(wt) / ".dgf-factory/RULES.md").is_file())


class CopyFile(unittest.TestCase):
    def test_a_link_planted_at_a_predictable_temporary_name_is_never_written_through(self):
        import worktree_task
        tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, tmp)
        victim, src, dst = tmp / "victim.txt", tmp / "src.json", tmp / "tree" / "a.json"
        victim.write_text("keep me\n", encoding="utf-8")
        src.write_text('{"worker": 1}\n', encoding="utf-8")
        dst.parent.mkdir()
        os.symlink(victim, dst.parent / f".{dst.name}.dgf-{os.getpid()}.tmp")
        worktree_task.copy_file(src, dst)
        self.assertEqual(victim.read_text(encoding="utf-8"), "keep me\n")
        self.assertEqual(dst.read_text(encoding="utf-8"), '{"worker": 1}\n')
        self.assertFalse(dst.is_symlink())
        self.assertEqual(sorted(p.name for p in dst.parent.iterdir()), [".a.json.dgf-%d.tmp" % os.getpid(), "a.json"],
                         "no temporary file of its own is left")


@unittest.skipUnless(helpers.have_git(), "git is not installed")
class Usage(unittest.TestCase):
    def test_help_lists_every_flag(self):
        code, out, _ = helpers.run_cli("worktree_task.py", "--help")
        self.assertEqual(code, 0)
        for flag in ("--sync", "--merge", "--from", "--worktree", "--to", "--plan", "--task", "--cleanup", "--verbose"):
            self.assertIn(flag, out)

    def test_a_mode_with_the_wrong_flags_is_a_usage_error(self):
        here = str(helpers.PLUGIN_ROOT)
        self.assertEqual(helpers.run_cli("worktree_task.py", "--from", here, "--worktree", here)[0], 3)
        self.assertEqual(helpers.run_cli("worktree_task.py", "--sync", "--from", here)[0], 3)
        self.assertEqual(helpers.run_cli("worktree_task.py", "--merge", "--from", here, "--to", here)[0], 3)
        self.assertEqual(helpers.run_cli("worktree_task.py", "--sync", "--from", here, "--worktree", here,
                                         "--task", "1")[0], 3)
        self.assertEqual(helpers.run_cli("worktree_task.py", "--merge", "--from", here, "--to", here, "--plan", "p",
                                         "--task", "one")[0], 3)


if __name__ == "__main__":
    unittest.main()
