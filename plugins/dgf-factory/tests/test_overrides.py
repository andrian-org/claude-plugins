"""scripts/lib/overrides.py: the override template, its sources, and what it may never say (ADR 0021 §3–§5)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers  # noqa: F401 — puts scripts/ on sys.path
from lib import overrides, report

PATCH = "2026-09-26-14.30-review-moves-to-undeclared-state.md"
REL = ".dgf-factory/skill-context/dgf-plan/SKILL.md"
EXAMPLE = f"""# Project Rules for /dgf-plan

> Written by /dgf-evolve from the estate's patches. Each rule may only tighten /dgf-plan (ADR 0021).
> Updated: 2026-09-26 15:00

## Rules

### A task that renames a state lists every transition to it
- source: {PATCH}
- rule: When a task renames a process state, list in the same task every process and workflow file whose
  transition or `CHANGE_STATE` step names the old state.
"""


def rule(name="Extra", text="List every form the task touches.", source=PATCH):
    return f"\n### {name}\n- source: {source}\n- rule: {text}\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.patches = self.tmp / "patches"
        self.patches.mkdir()
        (self.patches / PATCH).write_text("x", encoding="utf-8")

    def run_all(self, text=EXAMPLE, skill="dgf-plan"):
        path = self.tmp / "SKILL.md"
        path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
        rep = report.Report(REL)
        parsed = overrides.parse(path, REL, skill, rep)
        if parsed is not None:
            overrides.check_sources(parsed.rules, self.patches, REL, rep)
            overrides.check_rules(parsed.rules, REL, rep, quoted=parsed.quoted)
        return parsed, rep

    def codes(self, text=EXAMPLE, skill="dgf-plan"):
        return [f.code for f in self.run_all(text, skill)[1].findings]

    def assertOnly(self, code, text, line=None, contains=None, skill="dgf-plan"):
        found = self.run_all(text, skill)[1].findings
        self.assertEqual([f.code for f in found], [code], [f.render() for f in found])
        if line is not None:
            self.assertEqual(found[0].line, line)
        if contains:
            self.assertIn(contains, found[0].message)
        return found[0]


class Example(Base):
    def test_the_design_example_is_clean_when_its_patch_exists(self):
        parsed, rep = self.run_all()
        self.assertEqual(rep.findings, [])
        self.assertEqual(len(parsed.rules), 1)
        only = parsed.rules[0]
        self.assertEqual((only.name, only.line, only.sources), (
            "A task that renames a state lists every transition to it", 8, [PATCH]))
        self.assertTrue(only.text.endswith("step names the old state."))
        self.assertEqual(len(parsed.quoted), 2)

    def test_several_sources_and_rules(self):
        second = "2026-09-27-09.00-second.md"
        (self.patches / second).write_text("x", encoding="utf-8")
        self.assertEqual(self.codes(EXAMPLE + rule(source=f"{PATCH}, {second}")), [])


class Shape(Base):
    def test_a_title_for_another_skill(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE, line=1, skill="dgf-verify", contains="/dgf-verify")

    def test_a_second_level_two_heading(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE + "\n## More\n", line=13)

    def test_a_second_rules_heading(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE + "\n## Rules\n", line=13, contains="twice")

    def test_other_heading_levels(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE + "\n#### Deeper\n", line=13)
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE.replace("## Rules\n", "## Rules\n\n# Again\n"), line=8)

    def test_text_outside_a_rule(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE.replace("> Updated", "Updated"), line=4, contains="outside a rule")
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE.replace("## Rules\n", "## Rules\nloose text\n"), line=7)

    def test_a_missing_bullet(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE.replace(f"- source: {PATCH}\n", ""), line=8, contains="`- source:`")

    def test_an_extra_bullet_or_line(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE + f"- source: {PATCH}\n", line=12, contains="second")
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE + "- note: also\n", line=12)

    def test_a_duplicate_name(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE + rule("A task that renames a state lists every transition to it"),
                        line=13, contains="second rule")

    def test_a_name_over_the_limit(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE + rule("n" * 101), line=13)
        self.assertEqual(self.codes(EXAMPLE + rule("n" * 100)), [])

    def test_forty_one_rules(self):
        text = EXAMPLE + "".join(rule(f"Rule {i}") for i in range(40))
        self.assertOnly("OVERRIDE_SHAPE", text, contains="41 rules")
        self.assertEqual(self.codes(EXAMPLE + "".join(rule(f"Rule {i}") for i in range(39))), [])

    def test_a_rule_of_601_characters(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE + rule(text="x" * 601), line=13, contains="601")
        self.assertEqual(self.codes(EXAMPLE + rule(text="x" * 600)), [])

    def test_a_fence(self):
        found = self.run_all(EXAMPLE + "\n```\nhidden\n```\n")[1].findings
        self.assertEqual({f.code for f in found}, {"OVERRIDE_SHAPE"})
        self.assertEqual(found[0].line, 13)
        self.assertIn("fence", found[0].message)
        self.assertIn("OVERRIDE_SHAPE", self.codes(EXAMPLE + "\n~~~\n"))

    def test_an_html_comment(self):
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE.replace("> Updated", "> <!-- hidden --> Updated"), line=4,
                        contains="HTML comment")

    def test_invalid_utf8_is_unreadable(self):
        self.assertOnly("OVERRIDE_UNREADABLE", EXAMPLE.encode("utf-8").replace(b"renames", b"ren\xffames"))

    def test_over_the_byte_limit_is_unreadable(self):
        self.assertOnly("OVERRIDE_UNREADABLE", EXAMPLE + "  " + "x" * overrides.MAX_BYTES, contains="bytes")

    def test_an_empty_file_and_no_rules(self):
        self.assertOnly("OVERRIDE_SHAPE", "\n\n", contains="empty")
        self.assertOnly("OVERRIDE_SHAPE", EXAMPLE.split("\n### ")[0], contains="holds no rule")
        self.assertOnly("OVERRIDE_SHAPE", "# Project Rules for /dgf-plan\n", contains="no `## Rules`")

    def test_a_shape_failure_parses_to_nothing(self):
        parsed, _ = self.run_all(EXAMPLE + "\n## More\n")
        self.assertIsNone(parsed)


class Sources(Base):
    def test_a_missing_source_patch(self):
        self.assertOnly("OVERRIDE_SOURCE_MISSING", EXAMPLE + rule(source="2026-01-01-00.00-gone.md"), line=14,
                        contains="`2026-01-01-00.00-gone.md` is not in the patches directory")

    def test_a_source_that_is_not_a_patch_name(self):
        self.assertOnly("OVERRIDE_SOURCE_MISSING", EXAMPLE + rule(source="my notes"), contains="not a patch name")

    def test_an_empty_source(self):
        self.assertOnly("OVERRIDE_SOURCE_MISSING", EXAMPLE + rule(source=""), contains="names no patch")

    def test_a_source_matched_only_by_case_is_missing(self):
        (self.patches / "2026-09-27-09.00-Upper.md").write_text("x", encoding="utf-8")
        self.assertEqual(self.codes(EXAMPLE + rule(source="2026-09-27-09.00-upper.md")), ["OVERRIDE_SOURCE_MISSING"])


class Forbidden(Base):
    def assertRefused(self, text, construct):
        found = self.run_all(EXAMPLE + rule(text=text))[1].findings
        refused = [f for f in found if f.code == "OVERRIDE_FORBIDDEN"]
        self.assertEqual(len(refused), 1, [f.render() for f in found])
        self.assertIn(f"({construct})", refused[0].message)
        self.assertEqual(refused[0].line, 13)

    def test_every_entry_is_pinned(self):
        self.assertEqual([name for name, _, _ in overrides.FORBIDDEN],
                         ["gate-block", "flag", "tool-grant", "install", "git-write", "outside-root"])

    def test_a_gate_block(self):
        self.assertRefused("Add a dgf-gate-result entry for each form.", "gate-block")

    def test_a_flag(self):
        self.assertRefused("Run check_change.py with --skip-validators.", "flag")
        self.assertRefused("Pass --strict-mode to the gate.", "flag")
        self.assertRefused("Use --files to narrow it.", "flag")

    def test_strict_and_verbose_pass(self):
        self.assertEqual(self.codes(EXAMPLE + rule(text="Run the gate with --strict and --verbose.")), [])

    def test_a_tool_grant(self):
        self.assertRefused("Add Bash(rm *) to allowed-tools.", "tool-grant")
        self.assertRefused("Set disable-model-invocation to true.", "tool-grant")

    def test_an_install(self):
        for text in ("pip install lxml first.", "Run python3 -m pip for the deps.", "Use npm install.",
                     "brew install libxml2.", "Fetch it with curl https://x.", "wget the schema."):
            with self.subTest(text=text):
                self.assertRefused(text, "install")

    def test_a_history_rewriting_git_command(self):
        for text in ("Run git reset on the file.", "git push after each fix.", "Use git stash to park it.",
                     "Use git checkout to restore."):
            with self.subTest(text=text):
                self.assertRefused(text, "git-write")
        self.assertEqual(self.codes(EXAMPLE + rule(text="Read git log for the fix.")), [])

    def test_a_path_outside_the_root(self):
        for text in ("Read ../other/FM.", "Read ..\\other.", "Read ~" + "/notes.", "Read /Users" + "/me/x.",
                     "Read /home" + "/me/x."):
            with self.subTest(text=text):
                self.assertRefused(text, "outside-root")

    def test_a_rule_name_is_checked_too(self):
        found = self.run_all(EXAMPLE + rule(name="Use --files"))[1].findings
        self.assertIn("OVERRIDE_FORBIDDEN", [f.code for f in found])

    def test_a_quoted_line_is_checked_too(self):
        found = self.run_all(EXAMPLE.replace("> Updated", "> Always pass --skip-validators. Updated"))[1].findings
        refused = [f for f in found if f.code == "OVERRIDE_FORBIDDEN"]
        self.assertEqual(len(refused), 1)
        self.assertEqual(refused[0].line, 4)
        self.assertIn("the quoted lines", refused[0].message)


class Limit(Base):
    def test_word_bounded_and_case_insensitive_one_warning_per_rule(self):
        found = self.run_all(EXAMPLE + rule(text="STOP before the gate; stop again, and do not Skip it."))[1].findings
        self.assertEqual([f.code for f in found], ["OVERRIDE_TOUCHES_LIMIT"])
        self.assertIn("`stop`, `skip`", found[0].message)

    def test_a_word_inside_another_word_does_not_match(self):
        found = self.run_all(EXAMPLE + rule(text="Use the stopwatch and the statuesque blocks."))[1].findings
        self.assertEqual([f.code for f in found], ["OVERRIDE_TOUCHES_LIMIT"])
        self.assertIn("names `blocks` —", found[0].message)  # stopwatch and statuesque do not match
        self.assertEqual(self.codes(EXAMPLE + rule(text="Use the stopwatch and the statuesque form.")), [])

    def test_plural_and_past_forms_count(self):
        for text in ("It STOPs.", "Warnings appear.", "A skipped task.", "Allowed forms.", "It is waived."):
            with self.subTest(text=text):
                self.assertEqual(self.codes(EXAMPLE + rule(text=text)), ["OVERRIDE_TOUCHES_LIMIT"])

    def test_multi_word_entries(self):
        found = self.run_all(EXAMPLE + rule(text="A Critical Rule, a PRE_EXISTING finding, a check not run."))[1]
        self.assertIn("`critical rule`, `pre_existing`, `not run`", found.findings[0].message)

    def test_every_rule_is_judged_separately(self):
        text = EXAMPLE + rule("One", "Block it.") + rule("Two", "Warn on it.")
        self.assertEqual(self.codes(text), ["OVERRIDE_TOUCHES_LIMIT", "OVERRIDE_TOUCHES_LIMIT"])


if __name__ == "__main__":
    unittest.main()
