"""tools/packs.py — the line registries and where each pack lives (ADR 0036 §2)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

packs = helpers.load_tool("packs")

COMMIT = "a" * 40


def shipped(current="1.3", lines=None):
    lines = lines or [
        {"line": "1.3", "dir": "knowledge", "dgf_version": "1.3.0", "read_date": "2026-11-04"},
        {"line": "1.1", "dir": "packs/1.1", "dgf_version": "1.1.16", "read_date": "2026-11-04"},
    ]
    return {"format": 1, "current": current, "lines": lines}


def maintainer(lines=None):
    return {"format": 1, "lines": lines or {
        "1.3": {"tag": "1.3.0", "commit": COMMIT, "support_branch": "1.3.x"},
        "1.1": {"tag": "1.1.16", "commit": COMMIT, "support_branch": None},
    }}


class Registry(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        (self.root / "packs").mkdir()
        (self.root / "provenance").mkdir()

    def write(self, shipped_data, maintainer_data):
        (self.root / "packs" / "lines.json").write_text(json.dumps(shipped_data), encoding="utf-8")
        (self.root / "provenance" / "lines.json").write_text(json.dumps(maintainer_data), encoding="utf-8")

    def test_a_well_formed_pair_loads(self):
        self.write(shipped(), maintainer())
        lines, _maint, current = packs.load_registry(self.root)
        self.assertEqual(current, "1.3")
        self.assertEqual(packs.lines(self.root), ["1.1", "1.3"])
        self.assertEqual(set(lines), {"1.1", "1.3"})

    def test_directories_per_line(self):
        self.write(shipped(), maintainer())
        self.assertEqual(packs.pack_dir(None, self.root), self.root / "knowledge")
        self.assertEqual(packs.pack_dir("1.1", self.root), self.root / "packs" / "1.1")
        self.assertEqual(packs.ledger_dir("1.3", self.root), self.root / "provenance" / "knowledge")
        self.assertEqual(packs.ledger_dir("1.1", self.root), self.root / "provenance" / "packs" / "1.1")
        self.assertEqual(packs.exceptions_file("1.3", self.root), self.root / "tools" / "known-good-exceptions.txt")
        self.assertEqual(packs.exceptions_file("1.1", self.root),
                         self.root / "provenance" / "packs" / "1.1" / "known-good-exceptions.txt")

    def test_an_unregistered_line_is_refused(self):
        self.write(shipped(), maintainer())
        with self.assertRaisesRegex(packs.RegistryError, "no knowledge pack for DGF line 1.2"):
            packs.pack_dir("1.2", self.root)

    def test_malformed_registries_are_refused(self):
        cases = {
            "not json": ("{", maintainer()),
            "wrong format": ({**shipped(), "format": 2}, maintainer()),
            "current not listed": (shipped(current="1.2"), maintainer()),
            "current outside knowledge/": (shipped(lines=[
                {"line": "1.3", "dir": "packs/1.3", "dgf_version": "1.3.0", "read_date": "2026-11-04"}]), maintainer()),
            "older line outside packs/": (shipped(lines=[
                {"line": "1.3", "dir": "knowledge", "dgf_version": "1.3.0", "read_date": "2026-11-04"},
                {"line": "1.1", "dir": "elsewhere", "dgf_version": "1.1.16", "read_date": "2026-11-04"}]), maintainer()),
            "version off its line": (shipped(lines=[
                {"line": "1.3", "dir": "knowledge", "dgf_version": "1.2.0", "read_date": "2026-11-04"}]),
                maintainer({"1.3": {"tag": "1.3.0", "commit": COMMIT}})),
            "unknown key": (shipped(lines=[
                {"line": "1.3", "dir": "knowledge", "dgf_version": "1.3.0", "read_date": "2026-11-04", "x": 1}]),
                maintainer({"1.3": {"tag": "1.3.0", "commit": COMMIT}})),
            "registries disagree": (shipped(), maintainer({"1.3": {"tag": "1.3.0", "commit": COMMIT}})),
            "short commit": (shipped(), maintainer({**maintainer()["lines"], "1.1": {"tag": "1.1.16", "commit": "abc"}})),
            "tag without legacy is required": (shipped(), maintainer({**maintainer()["lines"], "1.1": {"tag": None, "commit": COMMIT}})),
            "tag differs from dgf_version": (shipped(), maintainer({**maintainer()["lines"], "1.1": {"tag": "1.1.15", "commit": COMMIT}})),
        }
        for name, (ship, maint) in cases.items():
            with self.subTest(name):
                if isinstance(ship, str):
                    (self.root / "packs" / "lines.json").write_text(ship, encoding="utf-8")
                    (self.root / "provenance" / "lines.json").write_text(json.dumps(maint), encoding="utf-8")
                else:
                    self.write(ship, maint)
                with self.assertRaises(packs.RegistryError):
                    packs.load_registry(self.root)

    def test_a_legacy_pin_may_have_no_tag_and_a_props_era_version(self):
        self.write(shipped(current="1.1", lines=[
            {"line": "1.1", "dir": "knowledge", "dgf_version": "1.1.11", "read_date": "2026-09-30", "legacy": True}]),
            maintainer({"1.1": {"tag": None, "commit": COMMIT, "support_branch": None, "legacy": True}}))
        _lines, _maint, current = packs.load_registry(self.root)
        self.assertEqual(current, "1.1")


class RealRegistry(unittest.TestCase):
    def test_the_repository_registries_agree(self):
        lines, _maint, current = packs.load_registry()
        self.assertIn(current, lines)
        for line in lines:
            self.assertTrue(packs.pack_dir(line).is_dir(), line)
            self.assertTrue(packs.ledger_dir(line).is_dir(), line)


if __name__ == "__main__":
    unittest.main()
