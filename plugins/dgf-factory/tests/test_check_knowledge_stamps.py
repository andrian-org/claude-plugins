"""tools/check_knowledge_stamps.py over a plugin root with two packs and their registries (ADR 0036 §2)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

DIGEST = "b" * 64
COMMIT = "c" * 40


def stamp(version, read_date="2026-11-04"):
    return f'---\ndgf_version: "{version}"\nread_date: {read_date}\n---\n\n# Facts\n'


LEDGER = f"---\nsources:\n  - path: src/Thing.cs\n    sha256: {DIGEST}\n---\n"


class Stamps(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "plugin", {
            "knowledge/README.md": "# The convention — exempt\n",
            "knowledge/facts.md": stamp("1.3.0"),
            "provenance/knowledge/facts.md": LEDGER,
            "packs/1.1/facts.md": stamp("1.1.16"),
            "provenance/packs/1.1/facts.md": LEDGER,
            "provenance/sync-log/2026-11-04-1.3-1.3.0.md": "# a sync log, not a ledger\n",
        })
        self.shipped = {"format": 1, "current": "1.3", "lines": [
            {"line": "1.3", "dir": "knowledge", "dgf_version": "1.3.0", "read_date": "2026-11-04"},
            {"line": "1.1", "dir": "packs/1.1", "dgf_version": "1.1.16", "read_date": "2026-11-04"}]}
        self.maintainer = {"format": 1, "lines": {
            "1.3": {"tag": "1.3.0", "commit": COMMIT, "support_branch": "1.3.x"},
            "1.1": {"tag": "1.1.16", "commit": COMMIT, "support_branch": None}}}
        self.write_registries()

    def write_registries(self):
        (self.root / "packs" / "lines.json").write_text(json.dumps(self.shipped), encoding="utf-8")
        (self.root / "provenance" / "lines.json").write_text(json.dumps(self.maintainer), encoding="utf-8")

    def run_stamps(self, *args):
        return helpers.run_cli(helpers.TOOLS / "check_knowledge_stamps.py", self.root, *args)

    def test_two_conforming_packs_are_clean(self):
        code, out, err = self.run_stamps()
        self.assertEqual(code, 0, out + err)
        self.assertIn("Packs checked: 2", out)
        self.assertIn("Files checked: 2", out)

    def test_a_stamp_other_than_the_registrys_blocks(self):
        (self.root / "packs/1.1/facts.md").write_text(stamp("1.1.15"), encoding="utf-8")
        code, out, _ = self.run_stamps()
        self.assertEqual(code, 1, out)
        self.assertIn('packs/1.1/facts.md: `dgf_version` "1.1.15" is not the registry\'s "1.1.16"', out)

    def test_a_missing_ledger_in_a_pack_blocks(self):
        (self.root / "provenance/packs/1.1/facts.md").unlink()
        code, out, _ = self.run_stamps()
        self.assertEqual(code, 1, out)
        self.assertIn("no provenance ledger at provenance/packs/1.1/facts.md", out)

    def test_a_readme_inside_a_pack_blocks(self):
        (self.root / "packs/1.1/README.md").write_text("# copy\n", encoding="utf-8")
        code, out, _ = self.run_stamps()
        self.assertEqual(code, 1, out)
        self.assertIn("a pack shares knowledge/README.md", out)

    def test_registries_that_disagree_block(self):
        del self.maintainer["lines"]["1.1"]
        self.write_registries()
        code, out, _ = self.run_stamps()
        self.assertEqual(code, 1, out)
        self.assertIn("the registries disagree", out)

    def test_a_registry_read_date_that_is_not_the_newest_blocks(self):
        self.shipped["lines"][1]["read_date"] = "2026-10-01"
        self.write_registries()
        code, out, _ = self.run_stamps()
        self.assertEqual(code, 1, out)
        self.assertIn("is not the pack's newest `read_date`", out)

    def test_an_orphan_ledger_for_an_unregistered_line_blocks(self):
        helpers.make_root(self.root, {"provenance/packs/1.0/facts.md": LEDGER})
        code, out, _ = self.run_stamps()
        self.assertEqual(code, 1, out)
        self.assertIn("provenance/packs/1.0/facts.md: ledger has no knowledge file", out)

    def test_pack_narrows_the_run(self):
        (self.root / "knowledge/facts.md").write_text(stamp("1.2.0"), encoding="utf-8")
        code, out, err = self.run_stamps("--pack", "1.1")
        self.assertEqual(code, 0, out + err)
        self.assertIn("Packs checked: 1", out)

    def test_an_unknown_pack_is_exit_3(self):
        code, _, err = self.run_stamps("--pack", "9.9")
        self.assertEqual(code, 3, err)


if __name__ == "__main__":
    unittest.main()
