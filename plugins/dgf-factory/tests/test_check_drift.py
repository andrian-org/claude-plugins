"""tools/check_drift.py against a fake DGF checkout: a git repo with one commit, and a ledger that cites it."""

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import helpers

SOURCE = "src/Core/Thing.cs"


def git(root, *args):
    subprocess.run(["git", "-C", str(root), "-c", "user.name=test", "-c", "user.email=test@example.invalid", *args],
                   check=True, capture_output=True)


@unittest.skipUnless(shutil.which("git"), "git not installed")
class CheckDrift(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dgf = helpers.make_root(self.tmp / "dgf", {
            "src/Directory.Build.props": "<Project><PropertyGroup><Version>1.1.11</Version></PropertyGroup></Project>\n",
            SOURCE: "public class Thing {}\n",
        })
        git(self.dgf, "init", "-q")
        git(self.dgf, "add", ".")
        git(self.dgf, "commit", "-q", "-m", "one")
        digest = hashlib.sha256((self.dgf / SOURCE).read_bytes()).hexdigest()
        self.plugin = helpers.make_root(self.tmp / "plugin", {
            "knowledge/facts.md": '---\ndgf_version: "1.1.11"\nread_date: 2026-09-24\n---\n\n# Facts\n',
            "provenance/knowledge/facts.md": f"---\nsources:\n  - path: {SOURCE}\n    sha256: {digest}\n---\n",
        })
        for tool in ("check_drift.py", "check_knowledge_stamps.py"):
            (self.plugin / "tools").mkdir(exist_ok=True)
            shutil.copy(helpers.TOOLS / tool, self.plugin / "tools" / tool)

    def run_drift(self, root=None):
        return helpers.run_cli(self.plugin / "tools" / "check_drift.py", root or self.dgf)

    def test_clean(self):
        code, out, err = self.run_drift()
        self.assertEqual(code, 0, out + err)
        self.assertIn("Sources:  1", out)

    def test_one_byte_changed_is_drift(self):
        (self.dgf / SOURCE).write_text("public class Thing { }\n", encoding="utf-8")
        git(self.dgf, "commit", "-q", "-am", "two")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 2, out)
        self.assertIn("WARN  DRIFT provenance/knowledge/facts.md: `src/Core/Thing.cs` changed", out)
        self.assertIn("knowledge/facts.md", out)

    def test_a_removed_file_is_drift_missing(self):
        git(self.dgf, "rm", "-q", SOURCE)
        git(self.dgf, "commit", "-q", "-m", "gone")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 2, out)
        self.assertIn("WARN  DRIFT_MISSING", out)

    def test_an_uncommitted_edit_is_flagged(self):
        (self.dgf / SOURCE).write_text("public class Thing { int x; }\n", encoding="utf-8")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 2, out)
        self.assertIn("WARN  LOCAL_EDITS", out)

    def test_a_version_mismatch_warns(self):
        (self.dgf / "src/Directory.Build.props").write_text("<Project><Version>1.2.0</Version></Project>\n",
                                                           encoding="utf-8")
        git(self.dgf, "commit", "-q", "-am", "bump")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 2, out)
        self.assertIn("VERSION_MISMATCH", out)

    def test_not_a_dgf_root_is_exit_3(self):
        code, _, err = self.run_drift(self.tmp)
        self.assertEqual(code, 3, err)


if __name__ == "__main__":
    unittest.main()
