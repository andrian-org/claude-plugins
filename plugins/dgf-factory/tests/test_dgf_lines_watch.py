"""tools/dgf_lines_watch.sh with a stub status tool and a stub `claude` (ADR 0036 §7).

The watcher runs from a copy inside a throwaway git repository, so the worktree it adds is the copy's.
"""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import helpers

STUB_STATUS = """import os, sys
code = int(os.environ.get("STUB_EXIT", "0"))
args = sys.argv[1:]
out = args[args.index("--json") + 1]
open(out, "w").write('{"verdict": "x"}')
open(os.environ["STUB_CALLS"], "a").write(" ".join(args) + "\\n")
if code == 2:
    print("WARN  TAG_AVAILABLE line 1.3: 1.3.1 is newer than the pack's 1.3.0")
    print("WARN  NEW_LINE release line 1.4 (1.4.0) has no knowledge pack")
sys.exit(code)
"""

STUB_CLAUDE = """#!/bin/sh
printf '%s|%s|%s\\n' "$PWD" "$DGF_ROOT" "$*" >> "$STUB_CALLS"
exit 0
"""


@unittest.skipUnless(helpers.have_git() and shutil.which("bash"), "git or bash not installed")
class Watch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = helpers.make_repo(self.tmp / "repo", {"plugins/dgf-factory/README.md": "x\n"})
        tools = self.repo / "plugins" / "dgf-factory" / "tools"
        tools.mkdir()
        shutil.copy(helpers.TOOLS / "dgf_lines_watch.sh", tools / "dgf_lines_watch.sh")
        helpers.commit_all(self.repo, "watch")
        self.script = tools / "dgf_lines_watch.sh"
        (self.tmp / "stub_status.py").write_text(STUB_STATUS, encoding="utf-8")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        claude = bin_dir / "claude"
        claude.write_text(STUB_CLAUDE, encoding="utf-8")
        claude.chmod(claude.stat().st_mode | stat.S_IEXEC)
        self.dgf = self.tmp / "dgf"
        self.dgf.mkdir()
        self.calls = self.tmp / "calls.txt"
        self.cache = self.tmp / "cache"
        self.env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "DGF_LINES_CACHE": str(self.cache),
                    "DGF_LINES_TOOL": str(self.tmp / "stub_status.py"), "STUB_CALLS": str(self.calls),
                    "HOME": str(self.tmp)}
        for key in ("DGF_SYNC_AUTORUN", "DEBUG"):
            self.env.pop(key, None)

    def watch(self, **env):
        return subprocess.run(["bash", str(self.script), str(self.dgf)], capture_output=True, text=True,
                              env={**self.env, **env})

    def calls_made(self):
        return self.calls.read_text(encoding="utf-8").splitlines() if self.calls.exists() else []

    def test_nothing_to_do_runs_nothing_else(self):
        done = self.watch(STUB_EXIT="0")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(len(self.calls_made()), 1)
        self.assertIn("--fetch", self.calls_made()[0])
        self.assertIn("CLEAN", (self.cache / "watch.log").read_text(encoding="utf-8"))

    def test_work_without_autorun_only_reports(self):
        done = self.watch(STUB_EXIT="2")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        log = (self.cache / "watch.log").read_text(encoding="utf-8")
        self.assertIn("WARN  TAG_AVAILABLE line 1.3", log)
        self.assertIn("2 item(s) of DGF knowledge work available", log)
        self.assertIn("autorun is off", log)
        self.assertEqual(len(self.calls_made()), 1, "claude was not run")
        self.assertNotIn("chore/dgf-sync", helpers.git(self.repo, "branch", "--list"))

    def test_autorun_syncs_in_a_new_worktree_and_commits_nothing(self):
        from datetime import date
        head = helpers.git(self.repo, "rev-parse", "HEAD")
        done = self.watch(STUB_EXIT="2", DGF_SYNC_AUTORUN="1")
        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        branch = f"chore/dgf-sync-{date.today().isoformat()}"
        worktree = Path(f"{self.repo}-dgf-sync-{date.today().isoformat()}")
        self.addCleanup(shutil.rmtree, worktree, True)
        branches = helpers.git(self.repo, "for-each-ref", "--format=%(refname:short)", "refs/heads/chore").split()
        self.assertEqual(branches, [branch])
        cwd, dgf_root, prompt = self.calls_made()[1].split("|")
        self.assertEqual(Path(cwd).resolve(), (worktree / "plugins" / "dgf-factory").resolve())
        self.assertEqual(Path(dgf_root).resolve(), self.dgf.resolve())
        self.assertEqual(prompt, "-p /dgf-sync sync --all")
        self.assertEqual(helpers.git(self.repo, "rev-parse", "HEAD"), head, "the main tree did not move")
        self.assertEqual(helpers.git(self.repo, "rev-parse", branch), head, "nothing was committed")

    def test_an_existing_branch_blocks_the_autorun(self):
        from datetime import date
        helpers.git(self.repo, "branch", f"chore/dgf-sync-{date.today().isoformat()}")
        done = self.watch(STUB_EXIT="2", DGF_SYNC_AUTORUN="1")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("already exists", (self.cache / "watch.log").read_text(encoding="utf-8"))

    def test_a_held_lock_is_exit_3(self):
        (self.cache / "watch.lock").mkdir(parents=True)
        done = self.watch(STUB_EXIT="0")
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertEqual(self.calls_made(), [])

    def test_a_failed_status_blocks(self):
        done = self.watch(STUB_EXIT="3")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)

    def test_the_lock_is_released(self):
        self.watch(STUB_EXIT="0")
        self.assertFalse((self.cache / "watch.lock").exists())


if __name__ == "__main__":
    unittest.main()
