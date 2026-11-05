"""tools/check_drift.py against a fake DGF checkout: a git repo with release tags, and two packs whose ledgers cite it."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

SOURCE = "src/Core/Thing.cs"
OTHER = "src/Core/Other.cs"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_plugin(root, dgf, commit, current="1.2", legacy=False):
    """A plugin root holding the drift tools, two packs (1.2 current, 1.1 older) and their registries."""
    version = "1.1.11" if legacy else "1.2.0"
    plugin = helpers.make_root(root, {
        "knowledge/facts.md": f'---\ndgf_version: "{version}"\nread_date: 2026-11-04\n---\n\n# Facts\n',
        "provenance/knowledge/facts.md": f"---\nsources:\n  - path: {SOURCE}\n    sha256: {sha(dgf / SOURCE)}\n---\n",
        "packs/1.1/facts.md": '---\ndgf_version: "1.1.16"\nread_date: 2026-11-04\n---\n\n# Facts\n',
        "provenance/packs/1.1/facts.md": f"---\nsources:\n  - path: {OTHER}\n    sha256: {sha(dgf / OTHER)}\n---\n",
    })
    lines = [{"line": current, "dir": "knowledge", "dgf_version": version, "read_date": "2026-11-04"},
             {"line": "1.1", "dir": "packs/1.1", "dgf_version": "1.1.16", "read_date": "2026-11-04"}]
    maint = {current: {"tag": "1.2.0", "commit": commit, "support_branch": "1.2.x"},
             "1.1": {"tag": "1.1.16", "commit": commit, "support_branch": None}}
    if legacy:
        lines[0]["legacy"] = True
        maint[current] = {"tag": None, "commit": commit, "support_branch": None, "legacy": True}
    (plugin / "packs" / "lines.json").write_text(json.dumps({"format": 1, "current": current, "lines": lines}))
    (plugin / "provenance" / "lines.json").write_text(json.dumps({"format": 1, "lines": maint}))
    (plugin / "tools").mkdir(exist_ok=True)
    for tool in ("check_drift.py", "check_knowledge_stamps.py", "packs.py"):
        shutil.copy(helpers.TOOLS / tool, plugin / "tools" / tool)
    (plugin / "scripts" / "lib").mkdir(parents=True, exist_ok=True)
    shutil.copy(helpers.SCRIPTS / "lib" / "dgf_version.py", plugin / "scripts" / "lib" / "dgf_version.py")
    return plugin


@unittest.skipUnless(helpers.have_git(), "git not installed")
class CheckDrift(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dgf = helpers.make_repo(self.tmp / "dgf", {
            "src/Directory.Build.props": "<Project><PropertyGroup><Version>1.1.15</Version></PropertyGroup></Project>\n",
            SOURCE: "public class Thing {}\n",
            OTHER: "public class Other {}\n",
        })
        self.commit = helpers.tag(self.dgf, "1.2.0")
        helpers.tag(self.dgf, "1.1.16")
        self.plugin = make_plugin(self.tmp / "plugin", self.dgf, self.commit)

    def run_drift(self, *args, root=None):
        return helpers.run_cli(self.plugin / "tools" / "check_drift.py", root or self.dgf, *args)

    def test_clean_at_the_packs_tag(self):
        code, out, err = self.run_drift()
        self.assertEqual(code, 0, out + err)
        self.assertIn("Sources:  1", out)
        self.assertIn("at tag 1.2.0, pack 1.2's dgf_version", out)
        self.assertIn("PROPS_VERSION", out)

    def test_one_byte_changed_is_drift(self):
        (self.dgf / SOURCE).write_text("public class Thing { }\n", encoding="utf-8")
        helpers.commit_all(self.dgf, "two")
        helpers.tag(self.dgf, "1.2.1")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 2, out)
        self.assertIn("WARN  DRIFT provenance/knowledge/facts.md: `src/Core/Thing.cs` changed", out)
        self.assertIn("re-read it for knowledge/facts.md", out)
        self.assertIn("VERSION_MISMATCH the checkout is at tag 1.2.1; pack 1.2 was read at 1.2.0", out)

    def test_a_removed_file_is_drift_missing(self):
        helpers.git(self.dgf, "rm", "-q", SOURCE)
        helpers.commit_all(self.dgf, "gone")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 2, out)
        self.assertIn("WARN  DRIFT_MISSING", out)

    def test_an_uncommitted_edit_is_flagged(self):
        (self.dgf / SOURCE).write_text("public class Thing { int x; }\n", encoding="utf-8")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 2, out)
        self.assertIn("WARN  LOCAL_EDITS", out)

    def test_an_untagged_head_is_an_unreleased_tree(self):
        (self.dgf / "README.md").write_text("more\n", encoding="utf-8")
        helpers.commit_all(self.dgf, "untagged")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 2, out)
        self.assertIn("VERSION_NOT_A_TAG", out)

    def test_the_props_version_never_decides(self):
        (self.dgf / "src/Directory.Build.props").write_text("<Project><Version>9.9.9</Version></Project>\n")
        helpers.commit_all(self.dgf, "bump props")
        helpers.git(self.dgf, "tag", "-f", "1.2.0", "HEAD")
        code, out, _ = self.run_drift()
        self.assertEqual(code, 0, out)
        self.assertIn("<Version> is 9.9.9", out)

    def test_pack_reads_that_lines_ledgers(self):
        (self.dgf / SOURCE).write_text("changed\n", encoding="utf-8")
        helpers.commit_all(self.dgf, "current line moved")
        helpers.git(self.dgf, "tag", "-f", "1.1.16", "HEAD")
        code, out, err = self.run_drift("--pack", "1.1")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Pack: 1.1 — packs/1.1/", out)
        self.assertNotIn("Thing.cs", out)

    def test_a_legacy_pin_compares_commits(self):
        plugin = make_plugin(self.tmp / "legacy", self.dgf, self.commit, legacy=True)
        code, out, err = helpers.run_cli(plugin / "tools" / "check_drift.py", self.dgf)
        self.assertEqual(code, 0, out + err)
        self.assertIn("legacy pin; HEAD is its commit", out)

    def test_an_unknown_pack_is_exit_3(self):
        code, _, err = self.run_drift("--pack", "9.9")
        self.assertEqual(code, 3, err)

    def test_not_a_dgf_root_is_exit_3(self):
        code, _, err = self.run_drift(root=self.tmp)
        self.assertEqual(code, 3, err)


if __name__ == "__main__":
    unittest.main()
