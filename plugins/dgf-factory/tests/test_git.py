"""The read-only git helper in scripts/lib/git.py, against throwaway repositories."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import git


@unittest.skipUnless(helpers.have_git(), "git is not installed")
class GitHelpers(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        # The workspaces root sits below the top level, as it does in a real estate.
        self.repo = helpers.make_repo(self.tmp / "estate", {
            "README.md": "estate\n",
            "Web/workspaces/zims/FM/_PROCESS/P/process.xml": "<process/>\n",
            "Web/workspaces/zims/js/formhelper.js": "// helper\n",
        })
        self.root = self.repo / "Web" / "workspaces"

    def test_available(self):
        self.assertTrue(git.available())

    def test_toplevel_from_the_workspaces_root(self):
        self.assertEqual(git.toplevel(self.root).resolve(), self.repo.resolve())

    def test_current_branch_and_detached_head(self):
        self.assertEqual(git.current_branch(self.root), "main")
        helpers.git(self.repo, "checkout", "-q", "--detach")
        self.assertIsNone(git.current_branch(self.root))

    def test_merge_base_of_a_branch(self):
        base = helpers.git(self.repo, "rev-parse", "HEAD").strip()
        helpers.git(self.repo, "checkout", "-q", "-b", "feature/x")
        helpers.commit_all(self.repo, "on the branch")
        helpers.git(self.repo, "checkout", "-q", "main")
        helpers.commit_all(self.repo, "on main")
        helpers.git(self.repo, "checkout", "-q", "feature/x")
        self.assertEqual(git.merge_base(self.root, "main"), base)

    def test_no_merge_base_is_a_git_error(self):
        helpers.git(self.repo, "checkout", "-q", "--orphan", "unrelated")
        helpers.commit_all(self.repo, "unrelated root")
        with self.assertRaises(git.GitError):
            git.merge_base(self.root, "main")

    def test_changed_is_relative_to_the_root_and_limited_to_it(self):
        base = helpers.git(self.repo, "rev-parse", "HEAD").strip()
        (self.root / "zims/FM/_PROCESS/P/process.xml").write_text("<process name='P'/>\n", encoding="utf-8")
        (self.root / "zims/js/new.js").write_text("// new\n", encoding="utf-8")
        (self.repo / "README.md").write_text("outside the root\n", encoding="utf-8")
        changes = {(c.status, c.path, c.old) for c in git.changed(self.root, base)}
        self.assertEqual(changes, {("M", "zims/FM/_PROCESS/P/process.xml", None),
                                   ("A", "zims/js/new.js", None)})

    def test_changed_reports_a_rename_and_a_deletion(self):
        helpers.make_root(self.root, {"zims/FM/_WORKFLOW/W/_workflow.xml": "<workflow>" + "x" * 200 + "</workflow>\n"})
        base = helpers.commit_all(self.repo, "add a workflow")
        helpers.git(self.repo, "mv", "Web/workspaces/zims/FM/_WORKFLOW/W", "Web/workspaces/zims/FM/_WORKFLOW/V")
        helpers.git(self.repo, "rm", "-q", "Web/workspaces/zims/js/formhelper.js")
        changes = {(c.status, c.path, c.old) for c in git.changed(self.root, base)}
        self.assertEqual(changes, {("R", "zims/FM/_WORKFLOW/V/_workflow.xml", "zims/FM/_WORKFLOW/W/_workflow.xml"),
                                   ("D", "zims/js/formhelper.js", None)})

    def test_refs_lists_local_and_remote_branches_and_skips_symbolic_ones(self):
        head = helpers.git(self.repo, "rev-parse", "HEAD").strip()
        helpers.git(self.repo, "branch", "feature/a")
        helpers.git(self.repo, "update-ref", "refs/remotes/origin/main", head)
        helpers.git(self.repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
        names = {name for name, _ in git.refs(self.root)}
        self.assertEqual(names, {"refs/heads/main", "refs/heads/feature/a", "refs/remotes/origin/main"})

    def test_ls_tree_and_show_read_paths_relative_to_the_root(self):
        entries = git.ls_tree(self.root, "HEAD", "zims/js")
        self.assertEqual([e.path for e in entries], ["zims/js/formhelper.js"])
        self.assertEqual(git.show(self.root, "HEAD", "zims/js/formhelper.js"), b"// helper\n")
        self.assertEqual(git.show(self.root, entries[0].sha), b"// helper\n")

    def test_outside_a_repository_is_a_git_error(self):
        outside = self.tmp / "not-a-repo"
        outside.mkdir()
        with self.assertRaises(git.GitError):
            git.toplevel(outside)
        with self.assertRaises(git.GitError):
            git.current_branch(outside)


@unittest.skipUnless(helpers.have_git(), "git is not installed")
class Materialise(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = helpers.make_repo(self.tmp / "estate")
        helpers.make_root(self.repo, {
            ".gitattributes": "Web/workspaces/zims/FM/_COMPONENTS/Page/p.json export-ignore\n",
            "Web/workspaces/zims/FM/_COMPONENTS/Page/p.json": '{"type": "Page"}\n',
            "Web/workspaces/zims/FM/_DATA/T/settings.xml": b"<settings>\r\n</settings>\r\n",
            "outside.txt": "not below the root\n",
        })
        os.symlink("p.json", self.repo / "Web/workspaces/zims/FM/_COMPONENTS/Page/link.json")
        self.commit = helpers.commit_all(self.repo, "base")
        self.root = self.repo / "Web" / "workspaces"
        self.dest = self.tmp / "base-tree"

    def test_writes_every_blob_below_the_root_exactly(self):
        counts = git.materialise(self.root, self.commit, self.dest)
        self.assertEqual(counts, {"blobs": 2, "symlinks": 1, "submodules": 0})
        self.assertEqual((self.dest / "zims/FM/_DATA/T/settings.xml").read_bytes(), b"<settings>\r\n</settings>\r\n")
        self.assertFalse((self.dest / "outside.txt").exists())

    def test_export_ignore_does_not_drop_a_file(self):
        git.materialise(self.root, self.commit, self.dest)
        self.assertEqual((self.dest / "zims/FM/_COMPONENTS/Page/p.json").read_text(encoding="utf-8"),
                         '{"type": "Page"}\n')

    def test_a_symlink_is_skipped(self):
        git.materialise(self.root, self.commit, self.dest)
        self.assertFalse(os.path.lexists(self.dest / "zims/FM/_COMPONENTS/Page/link.json"))

    def test_the_working_tree_is_untouched(self):
        (self.root / "zims/FM/_DATA/T/settings.xml").write_text("<changed/>\n", encoding="utf-8")
        git.materialise(self.root, self.commit, self.dest)
        self.assertEqual((self.root / "zims/FM/_DATA/T/settings.xml").read_text(encoding="utf-8"), "<changed/>\n")

    def test_a_path_that_escapes_the_destination_is_refused(self):
        for rel in ("../escape.txt", "a/../../escape.txt", "/etc/passwd", "a//b"):
            with self.assertRaises(git.GitError, msg=rel):
                git._inside(self.dest, rel)
        self.assertEqual(git._inside(self.dest, "zims/FM/x.xml"), self.dest / "zims" / "FM" / "x.xml")


if __name__ == "__main__":
    unittest.main()
