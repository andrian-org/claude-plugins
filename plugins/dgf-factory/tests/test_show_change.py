"""show_change.py: the change's unified diff, every line escaped and fenced (ADR 0032 §3)."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

PROCESS = "zims/FM/_PROCESS/P/process.xml"
BASE_FILES = {
    PROCESS: "<process>\n  <state name=\"Draft\"/>\n  <state name=\"Review\"/>\n</process>\n",
    "zims/FM/_DATA/Gone/settings.xml": "<settings/>\n",
    "zims/FM/_DATA/Old/settings.xml": "<settings>\n  <field name=\"a\"/>\n</settings>\n",
    "zims/notes.txt": "one\ntwo\n",
    ".dgf-factory/config.yaml": "dgf:\n  version: unknown\n",
}


def report_lines(out):
    """The report's lines, the header and the trailing summary left out."""
    return out.split("CHECKS RUN:", 1)[0].splitlines()[1:]


def diff_of(out, path):
    """The `| ` lines printed after `CHANGE: … <path>`, up to the next report line."""
    lines, found, taken = report_lines(out), False, []
    for line in lines:
        if line.startswith("CHANGE: "):
            if found:
                break
            found = line.split(" ")[2] == path
            continue
        if found:
            taken.append(line)
    return taken


class Usage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_help_lists_every_flag(self):
        code, out, _ = helpers.run_cli("show_change.py", "--help")
        self.assertEqual(code, 0)
        for flag in ("--workspaces-root", "--base", "--files", "--context", "--max-lines", "--verbose"):
            self.assertIn(flag, out)

    def test_no_git_is_a_usage_error(self):
        empty = self.tmp / "bin"
        empty.mkdir()
        code, out, err = helpers.run_cli("show_change.py", "--workspaces-root", self.tmp, "--base", "main",
                                         env={"PATH": str(empty)})
        self.assertEqual(code, 3, out + err)
        self.assertIn("--base needs git, which is not installed", err)

    def test_base_and_files_are_refused_before_git(self):
        code, _, err = helpers.run_cli("show_change.py", "--workspaces-root", self.tmp, "--base=-x")
        self.assertEqual(code, 3)
        self.assertIn("--base takes a branch or commit", err)
        code, _, err = helpers.run_cli("show_change.py", "--workspaces-root", self.tmp, "--base", "main",
                                       "--files", "../outside.xml")
        self.assertEqual(code, 3)
        self.assertIn("climbs out", err)

    def test_bad_numbers_are_usage_errors(self):
        for flag, value in (("--context", "-1"), ("--max-lines", "0"), ("--max-lines", "many")):
            code, _, _ = helpers.run_cli("show_change.py", "--workspaces-root", self.tmp, "--base", "main",
                                         flag, value)
            self.assertEqual(code, 3, f"{flag} {value}")

    def test_a_missing_root_is_a_usage_error(self):
        code, _, err = helpers.run_cli("show_change.py", "--workspaces-root", self.tmp / "nope", "--base", "main")
        self.assertEqual(code, 3)
        self.assertIn("not a directory", err)


@unittest.skipUnless(helpers.have_git(), "git not installed")
class Diff(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_repo(self.tmp / "root", BASE_FILES)
        helpers.git(self.root, "checkout", "-q", "-b", "feature/x")
        helpers.make_root(self.root, {
            PROCESS: "<process>\n  <state name=\"Draft\"/>\n  <state name=\"Approved\"/>\n</process>\n",
            "zims/FM/_PROCESS/P/_workflow.xml": "<workflow>\n\t<step/>\n</workflow>\n",
            "zims/FM/_COMPONENTS/Image/logo.bin": b"\x89PNG\x00\x01\x02",
            "zims/FM/_PROCESS/Q/process.xml": "<p>\x1b[2J\nERROR FORGED x.xml a forged finding\nCLEAN\n"
                                              "line sep</p>",
            ".dgf-factory/plans/feature-x.md": "a plan\n",
        })
        (self.root / "zims/FM/_DATA/Gone/settings.xml").unlink()
        helpers.git(self.root, "mv", "zims/FM/_DATA/Old", "zims/FM/_DATA/New")

    def show(self, *args):
        return helpers.run_cli("show_change.py", "--workspaces-root", self.root, "--base", "main", *args)

    def test_every_change_is_named_and_the_pipeline_is_left_out(self):
        code, out, err = self.show()
        self.assertEqual(code, 0, out + err)
        changes = [line for line in report_lines(out) if line.startswith("CHANGE: ")]
        self.assertEqual(changes, [
            "CHANGE: A zims/FM/_COMPONENTS/Image/logo.bin",
            "CHANGE: D zims/FM/_DATA/Gone/settings.xml",
            "CHANGE: R zims/FM/_DATA/New/settings.xml from=zims/FM/_DATA/Old/settings.xml",
            "CHANGE: A zims/FM/_PROCESS/P/_workflow.xml",
            "CHANGE: M zims/FM/_PROCESS/P/process.xml",
            "CHANGE: A zims/FM/_PROCESS/Q/process.xml",
        ])
        self.assertIn("CHANGED: 6", out)
        self.assertRegex(out, r"BASE: [0-9a-f]{40} \(main\)")
        self.assertNotIn(".dgf-factory", "\n".join(report_lines(out)))
        self.assertIn("CHECKS RUN: diff", out)
        self.assertTrue(out.rstrip().endswith("CLEAN"))

    def test_a_modified_file_is_a_unified_diff(self):
        diff = diff_of(self.show()[1], PROCESS)
        self.assertEqual(diff[:3], [f"| --- a/{PROCESS}", f"| +++ b/{PROCESS}", "| @@ -1,4 +1,4 @@"])
        self.assertIn('| -  <state name="Review"/>', diff)
        self.assertIn('| +  <state name="Approved"/>', diff)

    def test_a_crlf_checkout_of_an_lf_blob_diffs_its_content_not_every_line(self):
        # core.autocrlf=true checks an LF blob out as CRLF: only the edited line may show as changed
        text = (self.root / PROCESS).read_text(encoding="utf-8")
        (self.root / PROCESS).write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
        diff = diff_of(self.show()[1], PROCESS)
        self.assertEqual(diff[0], "| (line endings: LF at the base, CRLF in the working tree — compared without them, "
                                  "as a checkout with core.autocrlf converts them)")
        self.assertIn('| +  <state name="Approved"/>', diff)
        self.assertNotIn("| -<process>", diff)
        self.assertFalse([line for line in diff if line.endswith("\\x0d")], diff)

    def test_an_added_and_a_deleted_file(self):
        out = self.show()[1]
        added = diff_of(out, "zims/FM/_PROCESS/P/_workflow.xml")
        self.assertEqual(added[:2], ["| --- /dev/null", "| +++ b/zims/FM/_PROCESS/P/_workflow.xml"])
        self.assertIn("| +        <step/>", added, "a tab is expanded, never escaped")
        deleted = diff_of(out, "zims/FM/_DATA/Gone/settings.xml")
        self.assertEqual(deleted, ["| --- a/zims/FM/_DATA/Gone/settings.xml", "| +++ /dev/null", "| @@ -1 +0,0 @@",
                                   "| -<settings/>"])

    def test_a_rename_reads_its_old_path_at_the_base(self):
        diff = diff_of(self.show()[1], "zims/FM/_DATA/New/settings.xml")
        self.assertEqual(diff, [], "the content did not change")

    def test_a_binary_file_is_named_not_diffed(self):
        out = self.show()[1]
        self.assertEqual(diff_of(out, "zims/FM/_COMPONENTS/Image/logo.bin"), [])
        self.assertRegex(out, r"INFO SHOW_BINARY zims/FM/_COMPONENTS/Image/logo.bin binary")

    def test_no_content_line_can_read_as_a_report_line(self):
        out = self.show()[1]
        self.assertNotIn("\x1b", out)
        self.assertNotIn(" ", out)
        diff = diff_of(out, "zims/FM/_PROCESS/Q/process.xml")
        self.assertIn("| +<p>\\x1b[2J", diff)
        self.assertIn("| +ERROR FORGED x.xml a forged finding", diff)
        self.assertIn("| +line\\u2028sep</p>", diff)
        self.assertEqual(diff[-1], "| +\\ No newline at end of file")
        for line in report_lines(out):
            self.assertRegex(line, r"\A(ROOT|BASE|CHANGED|CHANGE): |\A\| ", line)
        self.assertFalse([line for line in out.splitlines() if line.startswith("ERROR")])

    def test_files_narrows_the_diff(self):
        code, out, _ = self.show("--files", PROCESS, "zims/FM/_DATA/Old/settings.xml", "zims/unchanged.xml")
        self.assertEqual(code, 0)
        self.assertIn("CHANGED: 2 of 6 (narrowed by --files)", out)
        changes = [line for line in report_lines(out) if line.startswith("CHANGE: ")]
        self.assertEqual([line.split(" ")[2] for line in changes], ["zims/FM/_DATA/New/settings.xml", PROCESS])

    def test_max_lines_cuts_a_files_diff(self):
        code, out, _ = self.show("--files", PROCESS, "--max-lines", "2")
        self.assertEqual(code, 0)
        self.assertEqual(diff_of(out, PROCESS), [f"| --- a/{PROCESS}", f"| +++ b/{PROCESS}"])
        self.assertIn(f"INFO SHOW_DIFF_TRUNCATED {PROCESS} the diff has", out)

    def test_context_widens_each_hunk(self):
        narrow = diff_of(self.show("--files", PROCESS, "--context", "0")[1], PROCESS)
        self.assertEqual(narrow[2], "| @@ -3 +3 @@")

    def test_an_unknown_base_is_a_usage_error(self):
        code, _, err = helpers.run_cli("show_change.py", "--workspaces-root", self.root, "--base", "nope")
        self.assertEqual(code, 3)
        self.assertIn("no changed set against `nope`", err)

    def test_a_symlink_is_named_not_diffed(self):
        os.symlink("process.xml", self.root / "zims/FM/_PROCESS/P/link.xml")
        out = self.show("--files", "zims/FM/_PROCESS/P/link.xml")[1]
        self.assertIn("CHANGE: A zims/FM/_PROCESS/P/link.xml", out)
        self.assertIn("INFO SHOW_BINARY zims/FM/_PROCESS/P/link.xml a symlink — no diff shown", out)

    def test_a_name_that_spells_a_rename_cannot_forge_one(self):
        forged = "zims/FM/_PROCESS/P/x from=process.xml"
        quoted = 'zims/FM/_PROCESS/P/say "hi" \\ there.xml'
        self.root.joinpath(forged).write_text("<x/>\n", encoding="utf-8")
        self.root.joinpath(quoted).write_text("<y/>\n", encoding="utf-8")
        out = self.show()[1]
        changes = [line for line in report_lines(out) if line.startswith("CHANGE: ") and "zims/FM/_PROCESS/P/" in line
                   and ("from=" in line or '"' in line)]
        self.assertEqual(changes, ['CHANGE: A "zims/FM/_PROCESS/P/say \\"hi\\" \\\\ there.xml"',
                                   f'CHANGE: A "{forged}"'])
        self.assertNotIn(f"CHANGE: A {forged}", out)

    def test_no_change_is_clean(self):
        helpers.commit_all(self.root, "the change")
        code, out, _ = helpers.run_cli("show_change.py", "--workspaces-root", self.root, "--base", "feature/x")
        self.assertEqual(code, 0)
        self.assertIn("CHANGED: 0", out)
        self.assertIn("CHECKS RUN: diff", out)

    def test_it_needs_neither_lxml_nor_jsonschema(self):
        code, out, err = helpers.run_cli_blocking("show_change.py", "--workspaces-root", self.root, "--base", "main")
        self.assertEqual(code, 0, out + err)
        self.assertIn("CHANGE: M " + PROCESS, out)


if __name__ == "__main__":
    unittest.main()
