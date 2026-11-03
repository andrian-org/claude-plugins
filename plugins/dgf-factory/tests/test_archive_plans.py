"""archive_plans.py: which plans are finished, and moving them into the archive (ADR 0032 §3)."""

import contextlib
import datetime
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import plan

CONFIG = ".dgf-factory/config.yaml"
PLANS = ".dgf-factory/plans"
ARCHIVE = ".dgf-factory/archive"
PLAN = "---\nplan_format: 1\nmode: {mode}\nbranch: {branch}\ncreated: 2026-09-25\naffects_workspaces: [zims]\n" \
       "---\n\n# Plan\n\n## Tasks\n\n{tasks}"
TASK = "- [{mark}] Task {n}: x\n  - kind: config\n  - files: zims/FM/_PROCESS/P/process.xml\n"


def plan_text(branch="feature/x", mode="full", marks="x"):
    tasks = "".join(TASK.format(mark=mark, n=n) for n, mark in enumerate(marks, 1)) or "(none yet)\n"
    return PLAN.format(mode=mode, branch=branch, tasks=tasks)


TODAY = datetime.date.today().isoformat()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "root", {CONFIG: "dgf:\n  version: unknown\n",
                                                          "zims/FM/_PROCESS/P/process.xml": "<p/>"})

    def add(self, rel, text):
        return helpers.make_root(self.root, {rel: text}) / rel

    def archive(self, *args):
        return helpers.run_cli("archive_plans.py", "--workspaces-root", self.root, *args)

    def lines(self, out, prefix):
        return [line for line in out.splitlines() if line.startswith(prefix)]


class Listing(Base):
    def test_help_lists_every_flag(self):
        code, out, _ = helpers.run_cli("archive_plans.py", "--help")
        self.assertEqual(code, 0)
        for flag in ("--workspaces-root", "--plans-dir", "--fast-plan", "--archive-dir", "--plan", "--apply",
                     "--verbose"):
            self.assertIn(flag, out)

    def test_complete_incomplete_and_zero_task_plans(self):
        self.add(f"{PLANS}/feature-done.md", plan_text(marks="xx"))
        self.add(f"{PLANS}/feature-open.md", plan_text(marks="x "))
        self.add(f"{PLANS}/feature-empty.md", plan_text(marks=""))
        code, out, err = self.archive()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines(out, "ARCHIVE: "),
                         [f"ARCHIVE: {PLANS}/feature-done.md -> {ARCHIVE}/plans/feature-done.md progress=2/2"])
        self.assertEqual(self.lines(out, "KEEP: "), [f"KEEP: {PLANS}/feature-empty.md progress=0/0",
                                                     f"KEEP: {PLANS}/feature-open.md progress=1/2"])
        self.assertIn("CHECKS RUN: plans-progress", out)
        self.assertIn("NOT RUN: archive-move (a dry run", out)
        self.assertTrue((self.root / PLANS / "feature-done.md").is_file(), "a dry run writes nothing")
        self.assertFalse((self.root / ARCHIVE).exists())

    def test_an_ultra_bundle_and_the_fast_plan(self):
        self.add(f"{PLANS}/feature-big/index.md", plan_text(mode="ultra", marks="x"))
        self.add(f"{PLANS}/feature-big/phase-01-a.md", "# Phase 1\n")
        self.add(".dgf-factory/PLAN.md", plan_text(mode="fast", marks="x"))
        code, out, _ = self.archive()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.lines(out, "ARCHIVE: "), [
            f"ARCHIVE: {PLANS}/feature-big/ -> {ARCHIVE}/plans/feature-big/ progress=1/1",
            f"ARCHIVE: .dgf-factory/PLAN.md -> {ARCHIVE}/plans/PLAN-{TODAY}.md progress=1/1"])

    def test_nothing_complete_is_a_warning(self):
        self.add(f"{PLANS}/feature-open.md", plan_text(marks=" "))
        code, out, _ = self.archive()
        self.assertEqual(code, 2)
        self.assertIn("WARN ARCHIVE_NOTHING", out)
        shutil.rmtree(self.root / PLANS)
        code, out, _ = self.archive()
        self.assertEqual(code, 2)
        self.assertIn("ARCHIVE_NOTHING", out)

    def test_a_malformed_plan_is_skipped(self):
        self.add(f"{PLANS}/feature-bad.md", "no frontmatter\n")
        self.add(f"{PLANS}/feature-done.md", plan_text())
        code, out, _ = self.archive("--apply")
        self.assertEqual(code, 2, out)
        self.assertIn(f"WARN ARCHIVE_PLAN_SKIPPED {PLANS}/feature-bad.md", out)
        self.assertIn(f"KEEP: {PLANS}/feature-bad.md progress=unreadable", out)
        self.assertTrue((self.root / PLANS / "feature-bad.md").is_file())
        self.assertTrue((self.root / ARCHIVE / "plans" / "feature-done.md").is_file(), "the others still move")

    def test_paths_are_checked(self):
        for args in (("--archive-dir", "archive/"), ("--archive-dir", ".dgf-factory/"),
                     ("--archive-dir", "../x"), ("--plans-dir", "/abs"), ("--fast-plan", "a/../../b")):
            code, _, err = self.archive(*args)
            self.assertEqual(code, 3, f"{args}: {err}")
        code, _, err = self.archive("--plan", f"{PLANS}/nope.md")
        self.assertEqual(code, 3)
        self.assertIn("is no plan", err)


class Named(Base):
    def test_a_named_incomplete_plan_is_refused(self):
        self.add(f"{PLANS}/feature-done.md", plan_text())
        self.add(f"{PLANS}/feature-open.md", plan_text(marks=" "))
        code, out, _ = self.archive("--plan", f"{PLANS}/feature-open.md", f"{PLANS}/feature-done.md", "--apply")
        self.assertEqual(code, 1, out)
        self.assertIn(f"ERROR ARCHIVE_PLAN_INCOMPLETE {PLANS}/feature-open.md", out)
        self.assertIn("NOT RUN: archive-move (refused", out)
        self.assertFalse(self.lines(out, "MOVED: "))
        self.assertTrue((self.root / PLANS / "feature-done.md").is_file(), "a refused run moves nothing")
        self.assertNotIn("archived:", (self.root / PLANS / "feature-done.md").read_text())

    def test_plan_restricts_the_run_and_takes_a_bundles_index(self):
        self.add(f"{PLANS}/feature-done.md", plan_text())
        self.add(f"{PLANS}/feature-big/index.md", plan_text(mode="ultra"))
        code, out, _ = self.archive("--plan", f"./{PLANS}/feature-big/index.md")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.lines(out, "ARCHIVE: "),
                         [f"ARCHIVE: {PLANS}/feature-big/ -> {ARCHIVE}/plans/feature-big/ progress=1/1"])
        self.assertFalse(self.lines(out, "KEEP: "))


class Apply(Base):
    def test_apply_stamps_and_moves(self):
        self.add(f"{PLANS}/feature-done.md", plan_text())
        self.add(f"{PLANS}/feature-big/index.md", plan_text(mode="ultra"))
        self.add(f"{PLANS}/feature-big/phase-01-a.md", "# Phase 1\n")
        self.add(".dgf-factory/PLAN.md", plan_text(mode="fast"))
        code, out, err = self.archive("--apply")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.lines(out, "MOVED: "), [  # locate_plan.py --list's order: files, bundles, fast plan
            f"MOVED: {PLANS}/feature-done.md -> {ARCHIVE}/plans/feature-done.md",
            f"MOVED: {PLANS}/feature-big/ -> {ARCHIVE}/plans/feature-big/",
            f"MOVED: .dgf-factory/PLAN.md -> {ARCHIVE}/plans/PLAN-{TODAY}.md"])
        self.assertIn("CHECKS RUN: plans-progress, archive-move", out)
        self.assertEqual(sorted(p.name for p in (self.root / PLANS).iterdir()), [])
        self.assertFalse((self.root / ".dgf-factory/PLAN.md").exists())
        self.assertTrue((self.root / ARCHIVE / "plans/feature-big/phase-01-a.md").is_file(), "moved whole")
        for rel in ("feature-done.md", "feature-big/index.md", f"PLAN-{TODAY}.md"):
            parsed = plan.parse(self.root / ARCHIVE / "plans" / rel)
            self.assertEqual(parsed.header["archived"], TODAY, rel)
            self.assertEqual(parsed.progress(), (1, 1), rel)
        text = (self.root / ARCHIVE / "plans/feature-done.md").read_text(encoding="utf-8")
        self.assertIn(f"affects_workspaces: [zims]\narchived: {TODAY}\n---\n", text)

    def test_a_stamp_keeps_crlf_and_replaces_an_old_one(self):
        text = plan_text().replace("created:", "archived: 2020-01-01\ncreated:").replace("\n", "\r\n")
        path = self.add(f"{PLANS}/feature-done.md", "")
        path.write_bytes(text.encode("utf-8"))
        code, out, _ = self.archive("--apply")
        self.assertEqual(code, 0, out)
        moved = (self.root / ARCHIVE / "plans/feature-done.md").read_bytes().decode("utf-8")
        self.assertIn(f"archived: {TODAY}\r\ncreated:", moved)
        self.assertNotIn("2020-01-01", moved)
        self.assertNotIn("\n", moved.replace("\r\n", ""))

    def test_an_existing_destination_refuses_everything(self):
        self.add(f"{PLANS}/feature-a.md", plan_text())
        self.add(f"{PLANS}/feature-b.md", plan_text())
        self.add(f"{ARCHIVE}/plans/feature-b.md", "an older plan\n")
        code, out, _ = self.archive("--apply")
        self.assertEqual(code, 1, out)
        self.assertIn(f"ERROR ARCHIVE_DEST_EXISTS {PLANS}/feature-b.md", out)
        self.assertFalse(self.lines(out, "MOVED: "))
        self.assertTrue((self.root / PLANS / "feature-a.md").is_file(), "nothing moves when one is refused")
        self.assertNotIn("archived:", (self.root / PLANS / "feature-a.md").read_text())
        self.assertEqual((self.root / ARCHIVE / "plans/feature-b.md").read_text(), "an older plan\n")

    def test_two_plans_on_one_destination_are_refused(self):
        self.add(f"{PLANS}/PLAN-{TODAY}.md", plan_text())
        self.add(".dgf-factory/PLAN.md", plan_text(mode="fast"))
        code, out, _ = self.archive("--apply")
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR ARCHIVE_DEST_EXISTS .dgf-factory/PLAN.md", out)
        self.assertTrue((self.root / ".dgf-factory/PLAN.md").is_file())


    def test_destinations_that_differ_only_in_case_are_one(self):
        self.add(f"{PLANS}/plan-{TODAY}.md", plan_text())
        self.add(".dgf-factory/PLAN.md", plan_text(mode="fast"))
        code, out, _ = self.archive("--apply")
        self.assertEqual(code, 1, out)
        self.assertIn("ERROR ARCHIVE_DEST_EXISTS .dgf-factory/PLAN.md", out)
        self.assertIn("when case is ignored", out)
        self.assertFalse(self.lines(out, "MOVED: "))
        self.assertTrue((self.root / PLANS / f"plan-{TODAY}.md").is_file())
        self.assertTrue((self.root / ".dgf-factory/PLAN.md").is_file())

    def candidate(self, rel):
        import archive_plans
        found = archive_plans.candidates(self.root, PLANS, ".dgf-factory/PLAN.md", ARCHIVE, TODAY)
        return archive_plans, next(item for item in found if item.src == rel)

    def test_a_move_never_replaces_a_destination_that_appeared(self):
        for name, files in (("feature-a.md", {f"{PLANS}/feature-a.md": plan_text()}),
                            ("feature-big", {f"{PLANS}/feature-big/index.md": plan_text(mode="ultra")})):
            with self.subTest(plan=name):
                for rel, text in files.items():
                    self.add(rel, text)
                archive_plans, item = self.candidate(f"{PLANS}/{name}")
                self.add(f"{ARCHIVE}/plans/{name}" + ("/keep.md" if item.is_dir else ""), "an older plan\n")
                before = item.entry.read_bytes()
                with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(io.StringIO()):
                    archive_plans.move(self.root, item, TODAY, [])
                self.assertEqual(raised.exception.code, 3)
                self.assertEqual(item.entry.read_bytes(), before, "the source is untouched")
                kept = self.root / ARCHIVE / "plans" / name / ("keep.md" if item.is_dir else "")
                self.assertEqual(kept.read_text(encoding="utf-8"), "an older plan\n", "nothing is moved over it")

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root writes into a read-only folder")
    def test_a_failed_move_leaves_the_source_byte_for_byte(self):
        self.add(f"{PLANS}/feature-done.md", plan_text().replace("\n", "\r\n"))
        self.add(f"{PLANS}/feature-big/index.md", plan_text(mode="ultra"))
        sources = {rel: (self.root / PLANS / rel).read_bytes() for rel in ("feature-done.md", "feature-big/index.md")}
        locked = self.root / ARCHIVE / "plans"
        locked.mkdir(parents=True)
        locked.chmod(0o500)
        self.addCleanup(locked.chmod, 0o700)
        for name in ("feature-done.md", "feature-big"):
            with self.subTest(plan=name):
                code, out, err = self.archive("--plan", f"{PLANS}/{name}", "--apply")
                self.assertEqual(code, 3, out + err)
                self.assertIn("it is where it was, unchanged; nothing was moved before it", err)
        for rel, raw in sources.items():
            self.assertEqual((self.root / PLANS / rel).read_bytes(), raw, rel)

    def test_a_symlinked_plan_is_skipped_and_never_written_through(self):
        outside = self.tmp / "outside.md"
        outside.write_text(plan_text(), encoding="utf-8")
        (self.root / PLANS).mkdir(parents=True, exist_ok=True)
        os.symlink(outside, self.root / PLANS / "feature-link.md")
        bundle = self.tmp / "outside-bundle"
        bundle.mkdir()
        (bundle / "index.md").write_text(plan_text(mode="ultra"), encoding="utf-8")
        os.symlink(bundle, self.root / PLANS / "feature-linked-bundle")
        code, out, _ = self.archive("--apply")
        self.assertEqual(code, 2, out)
        self.assertIn(f"WARN ARCHIVE_PLAN_SKIPPED {PLANS}/feature-link.md the plan is a symlink", out)
        self.assertIn(f"WARN ARCHIVE_PLAN_SKIPPED {PLANS}/feature-linked-bundle/ the plan is a symlink", out)
        self.assertFalse(self.lines(out, "MOVED: "))
        self.assertEqual(outside.read_text(encoding="utf-8"), plan_text(), "never stamped through the link")
        self.assertNotIn("archived:", (bundle / "index.md").read_text(encoding="utf-8"))
        self.assertTrue(os.path.islink(self.root / PLANS / "feature-link.md"))


@unittest.skipUnless(helpers.have_git(), "git not installed")
class CurrentBranch(Base):
    def setUp(self):
        super().setUp()
        helpers.make_repo(self.root)
        helpers.commit_all(self.root, "initial")
        helpers.git(self.root, "checkout", "-q", "-b", "feature/done")
        self.add(f"{PLANS}/feature-done.md", plan_text(branch="feature/done"))

    def test_the_current_branchs_plan_is_kept_unless_named(self):
        code, out, _ = self.archive("--apply")
        self.assertEqual(code, 2, out)
        self.assertIn(f"KEEP: {PLANS}/feature-done.md progress=1/1 — the current branch's plan; name it with --plan",
                      out)
        self.assertIn("ARCHIVE_NOTHING", out)
        self.assertTrue((self.root / PLANS / "feature-done.md").is_file())
        code, out, _ = self.archive("--plan", f"{PLANS}/feature-done.md", "--apply")
        self.assertEqual(code, 0, out)
        self.assertIn(f"MOVED: {PLANS}/feature-done.md -> {ARCHIVE}/plans/feature-done.md", out)

    def test_it_needs_neither_lxml_nor_jsonschema(self):
        code, out, err = helpers.run_cli_blocking("archive_plans.py", "--workspaces-root", self.root)
        self.assertEqual(code, 2, out + err)
        self.assertIn("KEEP: ", out)


if __name__ == "__main__":
    unittest.main()
