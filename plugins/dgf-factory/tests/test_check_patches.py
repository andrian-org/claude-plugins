"""check_patches.py: which patches are well formed, and which the cursor has not seen (ADR 0021 §1)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from tests.test_patches import EXAMPLE, NAME

PATCHES = ".dgf-factory/patches"
CURSOR = ".dgf-factory/evolutions/patch-cursor.json"
SECOND = "2026-09-27-09.00-second.md"
BROKEN = "2026-09-25-09.00-broken.md"


def dated(name):
    stamp = name[:16]
    return EXAMPLE.replace("2026-09-26 14:30", f"{stamp[:10]} {stamp[11:13]}:{stamp[14:16]}")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = self.tmp / "workspaces"
        self.root.mkdir()

    def add(self, name, text=None):
        path = self.root / PATCHES / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else (text if text is not None else dated(name)).encode())
        return path

    def cursor(self, value):
        path = self.root / CURSOR
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")

    def check(self, *args, cwd=None, blocking=False):
        run = helpers.run_cli_blocking if blocking else helpers.run_cli
        return run("check_patches.py", "--workspaces-root", self.root, *args, cwd=cwd or self.tmp)


class Discovery(Base):
    def test_every_patch_in_the_directory_sorted_by_name(self):
        self.add(SECOND)
        self.add(NAME)
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn(f"PATCHES: {PATCHES}/ total=2 malformed=0", out)
        self.assertLess(out.index(NAME), out.index(SECOND))
        self.assertIn("CHECKS RUN: patch-name, patch-fields, patch-sections\n", out)
        self.assertNotIn("state=", out)

    def test_a_missing_patches_directory_is_zero_patches(self):
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn("total=0", out)

    def test_a_patch_named_relative_and_one_named_absolutely(self):
        path = self.add(NAME)
        self.add(SECOND)
        code, out, _ = self.check(f"workspaces/{PATCHES}/{NAME}", cwd=self.tmp)
        self.assertEqual(code, 0, out)
        self.assertIn("total=1", out)
        self.assertNotIn(SECOND, out)
        code, out, _ = self.check(str(path), cwd=self.root / PATCHES)
        self.assertEqual(code, 0, out)
        self.assertIn(f"PATCH: {NAME}", out)

    def test_a_patch_outside_the_patches_directory_is_usage(self):
        self.add(NAME)
        outside = self.root / NAME
        outside.write_text(EXAMPLE, encoding="utf-8")
        code, _, err = self.check(str(outside))
        self.assertEqual(code, 3)
        self.assertIn("not directly in the patches directory", err)
        self.assertEqual(self.check(str(self.root / PATCHES / "absent.md"))[0], 3)

    def test_a_missing_root_is_usage(self):
        code, _, err = helpers.run_cli("check_patches.py", "--workspaces-root", self.tmp / "absent")
        self.assertEqual(code, 3)
        self.assertIn("--workspaces-root is not a directory", err)

    def test_a_patches_dir_of_the_config(self):
        self.add(NAME).rename(self.root / NAME)
        code, out, _ = self.check("--patches-dir", ".")
        self.assertEqual(code, 0, out)
        self.assertIn("PATCHES: ./ total=1", out)


class Findings(Base):
    def test_a_malformed_patch_blocks_and_is_reported_at_its_line(self):
        self.add(NAME)
        self.add(BROKEN, dated(BROKEN).replace("A task that renames a state lists every file with a transition to it.",
                                              ""))
        code, out, _ = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("total=2 malformed=1", out)
        self.assertIn(f"ERROR PATCH_SECTION_INVALID {PATCHES}/{BROKEN}:20 `## Prevention` is empty", out)

    def test_an_unreadable_patch_is_malformed(self):
        self.add(BROKEN, b"\xff")
        code, out, _ = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("PATCH_UNREADABLE", out)
        self.assertIn(f'PATCH: {BROKEN} severity=? findings=? title=""', out)

    def test_an_entry_that_is_not_a_regular_file_is_malformed_not_skipped(self):
        self.add(NAME)
        (self.root / PATCHES / "2026-09-27-09.00-a-folder.md").mkdir()
        (self.root / PATCHES / "2026-09-27-10.00-a-device.md").symlink_to("/dev/zero")
        code, out, _ = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("total=3 malformed=2", out)
        self.assertEqual(out.count("PATCH_UNREADABLE"), 2, out)
        self.assertIn("not a regular file", out)

    def test_a_title_holding_a_control_character_prints_on_one_line(self):
        self.add(NAME, EXAMPLE.replace("never declares", "never declares\x1b[2J"))
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        line = next(l for l in out.splitlines() if l.startswith("PATCH: "))
        self.assertIn("never\\u2028declares\\x1b[2J", line)


class Cursor(Base):
    def test_states(self):
        self.add(NAME)
        self.add(SECOND)
        self.add(BROKEN, "# broken\n")
        self.cursor({"processed": [NAME, "2026-01-01-00.00-gone.md"], "updated": "2026-09-26 15:00"})
        code, out, err = self.check("--cursor", CURSOR, "--verbose")
        self.assertEqual(code, 1, out)
        self.assertIn(f"PATCHES: {PATCHES}/ total=3 new=1 processed=1 malformed=1", out)
        self.assertIn(f"PATCH: {NAME} state=processed", out)
        self.assertIn(f"PATCH: {SECOND} state=new", out)
        self.assertIn(f"PATCH: {BROKEN} state=malformed", out)
        self.assertIn("patch-cursor", out)
        self.assertNotIn("gone", out)
        self.assertIn("gone", err)

    def test_a_malformed_patch_is_never_new_even_when_processed(self):
        self.add(BROKEN, "# broken\n")
        self.cursor({"processed": [BROKEN], "updated": "x"})
        self.assertIn("state=malformed", self.check("--cursor", CURSOR)[1])

    def test_an_absent_cursor_makes_every_patch_new(self):
        self.add(NAME)
        code, out, _ = self.check("--cursor", CURSOR)
        self.assertEqual(code, 0, out)
        self.assertIn("new=1 processed=0", out)

    def test_an_unreadable_cursor_warns_and_every_patch_is_new(self):
        self.add(NAME)
        self.add(SECOND)
        self.cursor('{"processed": [1, 2], "updated": "x"}')
        code, out, _ = self.check("--cursor", CURSOR)
        self.assertEqual(code, 2, out)
        self.assertIn(f"WARN PATCH_CURSOR_UNREADABLE {CURSOR}", out)
        self.assertIn("new=2 processed=0", out)

    def test_a_deeply_nested_cursor_warns_instead_of_crashing(self):
        self.add(NAME)
        self.cursor("[" * 200000)
        code, out, err = self.check("--cursor", CURSOR)
        self.assertEqual(code, 2, out + err)
        self.assertIn("PATCH_CURSOR_UNREADABLE", out)
        self.assertNotIn("Traceback", err)

    def test_it_never_writes(self):
        self.add(NAME)
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        self.check("--cursor", CURSOR)
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob("*")), before)


class Contract(Base):
    def test_no_third_party_import(self):
        self.add(NAME)
        self.cursor({"processed": [], "updated": "x"})
        code, out, err = self.check("--cursor", CURSOR, blocking=True)
        self.assertEqual(code, 0, out + err)

    def test_help_lists_every_flag(self):
        code, out, _ = helpers.run_cli_blocking("check_patches.py", "--help")
        self.assertEqual(code, 0)
        for flag in ("--workspaces-root", "--patches-dir", "--cursor", "--verbose"):
            self.assertIn(flag, out)

    def test_a_bad_argument_is_usage(self):
        self.assertEqual(helpers.run_cli("check_patches.py", "--nope")[0], 3)

    def test_traces_go_to_stderr(self):
        self.add(NAME)
        code, out, err = self.check("--verbose")
        self.assertEqual(code, 0)
        self.assertIn("DEBUG [check_patches.main] checked total=1", err)
        self.assertIn("DEBUG [patches.parse] parsed", err)
        self.assertNotIn("DEBUG", out)


class WholeRootWalk(unittest.TestCase):
    """The cursor is a .json outside every FM/: only the dot-directory skip keeps the validators off it (E20)."""

    def test_the_configuration_walk_never_reads_the_pipeline_directory(self):
        from lib import cli
        with tempfile.TemporaryDirectory() as tmp:
            root = helpers.make_root(tmp, {CURSOR: '{"processed": [], "updated": "x"}', f"{PATCHES}/{NAME}": EXAMPLE,
                                           "draft.json": "{}", "app/FM/_COMPONENTS/a.json": "{}"})
            found = [p.relative_to(root).as_posix() for p in cli.collect([root])]
        self.assertIn("draft.json", found)
        self.assertEqual([p for p in found if p.startswith(".dgf-factory")], [])


if __name__ == "__main__":
    unittest.main()
