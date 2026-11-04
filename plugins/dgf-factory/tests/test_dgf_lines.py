"""tools/dgf_lines.py and tools/restamp_knowledge.py over a synthetic DGF repository and a fake plugin with two packs.

The DGF repository has release tags on three lines, support branches as
remote-tracking refs, an untagged `2.x`, and `.next` fragments; the plugin has
knowledge/ (line 1.3, read at 1.3.0) and packs/1.2/ (read at 1.2.0).
"""

import hashlib
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

THING = "src/Core/Thing.cs"
SCHEMA_A = "src/Tools/dgf-mcp/Schemas/Json/AConfiguration.schema.json"
SCHEMA_B = "src/Tools/dgf-mcp/Schemas/Json/BConfiguration.schema.json"
FRAGMENT = "docs/wiki/Release-notes/.next/feature-x.md"
TOOLS = ("dgf_lines.py", "packs.py", "check_drift.py", "check_knowledge_stamps.py", "vendor_schemas.py",
         "restamp_knowledge.py")


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def fact(version):
    return f'---\ndgf_version: "{version}"\nread_date: 2026-11-04\n---\n\n# Facts\n'


def build_dgf(root):
    """Commit A (tags 1.1.9, 1.2.0, 1.3.0) → B (tag 1.3.1, 1.4.0 later) → C (origin/1.3.x, untagged)."""
    dgf = helpers.make_repo(root, {
        "src/Directory.Build.props": "<Project><PropertyGroup><Version>1.1.15</Version></PropertyGroup></Project>\n",
        THING: "v1\n",
        SCHEMA_A: '{"title": "A"}\n',
    })
    a = helpers.tag(dgf, "1.3.0")
    for name in ("1.2.0", "1.1.9", "1.0.5"):
        helpers.tag(dgf, name)
    helpers.git(dgf, "update-ref", "refs/remotes/origin/1.2.x", a)
    helpers.git(dgf, "update-ref", "refs/remotes/origin/2.x", a)
    helpers.make_root(dgf, {THING: "v2\n", SCHEMA_B: '{"title": "B"}\n', FRAGMENT: "# x\n"})
    b = helpers.commit_all(dgf, "B")
    helpers.tag(dgf, "1.3.1")
    helpers.make_root(dgf, {"src/Core/Later.cs": "later\n"})
    c = helpers.commit_all(dgf, "C")
    helpers.git(dgf, "update-ref", "refs/remotes/origin/1.3.x", c)
    return dgf, a, b, c


def pack_files(prefix, ledger_prefix, version, commit):
    schema = '{"title": "A"}\n'
    return {
        f"{prefix}/facts.md": fact(version),
        f"{ledger_prefix}/facts.md": f"---\nsources:\n  - path: {THING}\n    sha256: {sha('v1' + chr(10))}\n---\n",
        f"{prefix}/schemas/MANIFEST.md": fact(version),
        f"{prefix}/schemas/json/AConfiguration.schema.json": schema,
        f"{ledger_prefix}/schemas/MANIFEST.md": (
            f"---\ndgf_commit: {commit}\ndgf_tag: {version}\nsources:\n  - path: {SCHEMA_A}\n"
            f"    sha256: {sha(schema)}\n    vendored: json/AConfiguration.schema.json\n"
            f"    shipped_sha256: {sha(schema)}\n---\n\n# Ledger\n"),
    }


def build_plugin(root, commit):
    files = {"knowledge/README.md": "# convention\n", "tools/known-good-exceptions.txt": "# none\n",
             "provenance/packs/1.2/known-good-exceptions.txt": "# none\n"}
    files.update(pack_files("knowledge", "provenance/knowledge", "1.3.0", commit))
    files.update(pack_files("packs/1.2", "provenance/packs/1.2", "1.2.0", commit))
    plugin = helpers.make_root(root, files)
    (plugin / "packs" / "lines.json").write_text(json.dumps({"format": 1, "current": "1.3", "lines": [
        {"line": "1.3", "dir": "knowledge", "dgf_version": "1.3.0", "read_date": "2026-11-04"},
        {"line": "1.2", "dir": "packs/1.2", "dgf_version": "1.2.0", "read_date": "2026-11-04"}]}, indent=2))
    (plugin / "provenance" / "lines.json").write_text(json.dumps({"format": 1, "lines": {
        "1.3": {"tag": "1.3.0", "commit": commit, "support_branch": "1.3.x"},
        "1.2": {"tag": "1.2.0", "commit": commit, "support_branch": "1.2.x"}}}, indent=2))
    for tool in TOOLS:
        shutil.copy(helpers.TOOLS / tool, plugin / "tools" / tool)
    (plugin / "scripts" / "lib").mkdir(parents=True)
    shutil.copy(helpers.SCRIPTS / "lib" / "dgf_version.py", plugin / "scripts" / "lib" / "dgf_version.py")
    helpers.make_repo(plugin)
    helpers.commit_all(plugin, "plugin")
    return plugin


@unittest.skipUnless(helpers.have_git(), "git not installed")
class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dgf, self.a, self.b, self.c = build_dgf(self.tmp / "dgf")
        self.plugin = build_plugin(self.tmp / "plugin", self.a)
        self.env = {**os.environ, "DGF_LINES_CACHE": str(self.tmp / "cache")}

    def lines(self, *args):
        return helpers.run_cli(self.plugin / "tools" / "dgf_lines.py", *args, env=self.env)

    def restamp(self, *args):
        return helpers.run_cli(self.plugin / "tools" / "restamp_knowledge.py", *args, env=self.env)

    def dgf_state(self):
        return helpers.git(self.dgf, "rev-parse", "HEAD"), helpers.git(self.dgf, "status", "--porcelain")

    def registries(self):
        return (json.loads((self.plugin / "packs/lines.json").read_text()),
                json.loads((self.plugin / "provenance/lines.json").read_text()))


class Status(Base):
    def test_status_reports_every_kind_of_work(self):
        helpers.tag(self.dgf, "1.4.0", self.b)
        before = self.dgf_state()
        report = self.tmp / "out" / "status.json"
        code, out, err = self.lines("status", self.dgf, "--json", report)
        self.assertEqual(code, 2, out + err)
        self.assertIn("WARN  TAG_AVAILABLE line 1.3: 1.3.1 is newer than the pack's 1.3.0", out)
        self.assertIn("WARN  DRIFT line 1.3: knowledge/facts.md cites 1 source(s) that changed at 1.3.1", out)
        self.assertIn("WARN  SCHEMA_SET_CHANGED line 1.3 at 1.3.1: 1 schema file(s) added", out)
        self.assertIn("1 unreleased commit(s) on origin/1.3.x since 1.3.1, 1 .next fragment(s)", out)
        self.assertIn("line 1.2 is at 1.2.0 with no drift", out)
        self.assertIn("WARN  NEW_LINE release line 1.4 (1.4.0) has no knowledge pack", out)
        self.assertIn("not tracked: 1.0", out)
        self.assertIn("origin/2.x carries no release tag", out)
        self.assertEqual(self.dgf_state(), before)
        data = json.loads(report.read_text())
        self.assertEqual(data["verdict"], "WARNINGS")
        self.assertEqual(data["lines"]["1.3"]["newest_tag"], "1.3.1")
        self.assertEqual(data["lines"]["1.3"]["drift"], {"knowledge/facts.md": 1})
        self.assertEqual(data["lines"]["1.3"]["schema_added"], [SCHEMA_B])
        self.assertEqual(data["lines"]["1.2"]["drift_total"], 0)
        self.assertEqual([n["line"] for n in data["new_lines"]], ["1.4"])

    def test_a_line_at_its_newest_tag_is_clean(self):
        code, out, err = self.lines("status", self.dgf, "--line", "1.2")
        self.assertEqual(code, 0, out + err)
        self.assertIn("CLEAN", out)

    def test_an_unregistered_line_and_a_non_dgf_root_are_exit_3(self):
        self.assertEqual(self.lines("status", self.dgf, "--line", "1.9")[0], 3)
        self.assertEqual(self.lines("status", self.tmp)[0], 3)


class Diff(Base):
    def test_diff_shows_each_drifted_source_and_leaves_the_dgf_alone(self):
        before = self.dgf_state()
        code, out, err = self.lines("diff", self.dgf, "1.3", "--to", "1.3.1")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Drifted sources of pack 1.3", out)
        self.assertIn("knowledge/facts.md — 1 source(s)", out)
        self.assertIn("-v1", out)
        self.assertIn("+v2", out)
        self.assertNotIn("AConfiguration", out, "the vendored schema set is vendor_schemas.py's")
        self.assertEqual(self.dgf_state(), before)

    def test_diff_runs_from_the_facts_stamp_even_after_a_re_vendor_or_a_freeze(self):
        ledger = self.plugin / "provenance/knowledge/schemas/MANIFEST.md"
        ledger.write_text(ledger.read_text().replace(f"dgf_commit: {self.a}", f"dgf_commit: {self.b}"))
        ship, maint = self.registries()
        maint["lines"]["1.3"]["commit"] = self.b
        (self.plugin / "provenance/lines.json").write_text(json.dumps(maint))
        code, out, err = self.lines("diff", self.dgf, "1.3", "--to", "1.3.1")
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"Drifted sources of pack 1.3: {self.a[:12]} → 1.3.1", out)
        self.assertIn("+v2", out)

    def test_stat_and_path_narrow_it(self):
        code, out, _ = self.lines("diff", self.dgf, "1.3", "--to", "1.3.1", "--stat", "--path", "src/Elsewhere.cs")
        self.assertEqual(code, 0, out)
        self.assertIn("(0)", out)

    def test_a_tag_off_the_line_is_exit_3(self):
        self.assertEqual(self.lines("diff", self.dgf, "1.3", "--to", "1.2.0")[0], 3)


class Checkout(Base):
    def test_checkout_detaches_a_cache_at_the_tag_and_leaves_the_dgf_alone(self):
        before = self.dgf_state()
        code, out, err = self.lines("checkout", self.dgf, "1.3", "--tag", "1.3.1")
        self.assertEqual(code, 0, out + err)
        cache = Path(out.strip().splitlines()[-1])
        self.assertEqual(cache, self.tmp / "cache" / "1.3")
        self.assertEqual(helpers.git(cache, "rev-parse", "HEAD").strip(), self.b)
        self.assertIn("1.3.1", helpers.git(cache, "tag", "--points-at", "HEAD").split())
        self.assertEqual(self.dgf_state(), before)

    def test_a_tag_off_the_line_is_refused(self):
        self.assertEqual(self.lines("checkout", self.dgf, "1.3", "--tag", "1.2.0")[0], 3)


class FreezeAndFork(Base):
    def test_freeze_moves_the_current_line_into_packs(self):
        helpers.tag(self.dgf, "1.4.0", self.b)
        code, out, err = self.lines("freeze", self.dgf, "1.3", "--next", "1.4", "--tag", "1.4.0")
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.plugin / "packs/1.3/facts.md").is_file())
        self.assertFalse((self.plugin / "packs/1.3/README.md").exists())
        self.assertTrue((self.plugin / "provenance/packs/1.3/facts.md").is_file())
        self.assertTrue((self.plugin / "provenance/packs/1.3/known-good-exceptions.txt").is_file())
        ship, maint = self.registries()
        self.assertEqual(ship["current"], "1.4")
        dirs = {entry["line"]: entry["dir"] for entry in ship["lines"]}
        self.assertEqual(dirs, {"1.4": "knowledge", "1.3": "packs/1.3", "1.2": "packs/1.2"})
        self.assertEqual(maint["lines"]["1.4"], {"tag": "1.4.0", "commit": self.b, "support_branch": None})

    def test_freeze_refuses_a_line_that_is_not_current(self):
        helpers.tag(self.dgf, "1.4.0", self.b)
        self.assertEqual(self.lines("freeze", self.dgf, "1.2", "--next", "1.4", "--tag", "1.4.0")[0], 3)

    def test_freeze_refuses_uncommitted_changes(self):
        helpers.tag(self.dgf, "1.4.0", self.b)
        (self.plugin / "knowledge/facts.md").write_text(fact("1.3.0") + "edit\n")
        code, _, err = self.lines("freeze", self.dgf, "1.3", "--next", "1.4", "--tag", "1.4.0")
        self.assertEqual(code, 1, err)
        self.assertIn("uncommitted changes", err)

    def test_freeze_refuses_an_existing_target(self):
        helpers.tag(self.dgf, "1.4.0", self.b)
        helpers.make_root(self.plugin, {"packs/1.3/old.md": "x\n"})
        helpers.commit_all(self.plugin, "stale target")
        code, _, err = self.lines("freeze", self.dgf, "1.3", "--next", "1.4", "--tag", "1.4.0")
        self.assertEqual(code, 1, err)
        self.assertIn("already exists", err)

    def test_fork_registers_an_older_line(self):
        code, out, err = self.lines("fork", self.dgf, "1.1", "--from", "1.2", "--tag", "1.1.9")
        self.assertEqual(code, 0, out + err)
        self.assertTrue((self.plugin / "packs/1.1/facts.md").is_file())
        self.assertTrue((self.plugin / "provenance/packs/1.1/known-good-exceptions.txt").is_file())
        ship, maint = self.registries()
        self.assertIn({"line": "1.1", "dir": "packs/1.1", "dgf_version": "1.1.9", "read_date": "2026-11-04"},
                      ship["lines"])
        self.assertEqual(maint["lines"]["1.1"]["tag"], "1.1.9")


class Restamp(Base):
    def checkout(self, tag):
        code, out, err = self.lines("checkout", self.dgf, tag.rsplit(".", 1)[0], "--tag", tag)
        self.assertEqual(code, 0, out + err)
        return Path(out.strip().splitlines()[-1])

    def test_restamp_re_digests_and_stamps(self):
        cache = self.checkout("1.3.1")
        code, out, err = self.restamp(cache, "--pack", "1.3", "facts.md", "--read-date", "2026-11-05")
        self.assertEqual(code, 0, out + err)
        self.assertIn(sha("v2\n"), (self.plugin / "provenance/knowledge/facts.md").read_text())
        stamp = (self.plugin / "knowledge/facts.md").read_text()
        self.assertIn('dgf_version: "1.3.1"', stamp)
        self.assertIn("read_date: 2026-11-05", stamp)

    def test_add_source_appends_to_the_ledger(self):
        cache = self.checkout("1.3.1")
        code, out, err = self.restamp(cache, "--pack", "1.3", "facts.md", "--add-source", "src/Core/Thing.cs",
                                      "--dry-run")
        self.assertEqual(code, 1, out + err)
        self.assertIn("already a source", out)
        code, out, err = self.restamp(cache, "--pack", "1.3", "facts.md", "--add-source", SCHEMA_B)
        self.assertEqual(code, 0, out + err)
        self.assertIn(f"path: {SCHEMA_B}", (self.plugin / "provenance/knowledge/facts.md").read_text())

    def test_refusals(self):
        cache = self.checkout("1.3.1")
        self.assertEqual(self.restamp(self.dgf, "--pack", "1.3", "facts.md")[0], 1)          # HEAD untagged
        self.assertEqual(self.restamp(cache, "--pack", "1.2", "facts.md")[0], 1)             # another line
        self.assertEqual(self.restamp(cache, "--pack", "1.3", "facts.md",
                                      "--add-source", "src/Nowhere.cs")[0], 1)               # missing source
        self.assertEqual(self.restamp(cache, "--pack", "1.3", "--all")[0], 1)                # schema ledger at 1.3.0
        self.assertEqual(self.restamp(cache, "--pack", "1.3", "schemas/MANIFEST.md")[0], 3)  # vendor's to stamp
        self.assertEqual(self.restamp(cache, "--pack", "1.3")[0], 3)                         # neither files nor --all

    def test_all_records_the_pack_in_both_registries(self):
        cache = self.checkout("1.3.1")
        ledger = self.plugin / "provenance/knowledge/schemas/MANIFEST.md"
        ledger.write_text(ledger.read_text().replace("dgf_tag: 1.3.0", "dgf_tag: 1.3.1"))
        code, out, err = self.restamp(cache, "--pack", "1.3", "--all", "--read-date", "2026-11-06")
        self.assertEqual(code, 0, out + err)
        ship, maint = self.registries()
        current = next(entry for entry in ship["lines"] if entry["line"] == "1.3")
        self.assertEqual((current["dgf_version"], current["read_date"]), ("1.3.1", "2026-11-06"))
        self.assertEqual((maint["lines"]["1.3"]["tag"], maint["lines"]["1.3"]["commit"]), ("1.3.1", self.b))


if __name__ == "__main__":
    unittest.main()
