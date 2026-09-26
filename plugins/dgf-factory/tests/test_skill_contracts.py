"""The shipped skills and the scripts they call must not drift apart (plan R1).

A prompt that quotes a finding code no script emits, or passes a flag a script
does not take, fails silently at run time: the model waits for a line that
never comes, or the script exits 3. These tests read every shipped skill's
Markdown and hold it to the scripts as they are.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

from tests import helpers
from lib import report

SKILLS = helpers.PLUGIN_ROOT / "skills"
DOCTOR = SKILLS / "dgf-doctor" / "scripts" / "doctor.py"
BACKTICKED = re.compile(r"`([^`\n]+)`")
CODE_TOKEN = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\Z")
SCRIPT_CALL = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/((?:skills/[a-z0-9-]+/)?scripts/[a-z_]+\.py)\"?(.*)")
FLAG = re.compile(r"(?<![\w-])--[a-z][a-z-]*")

# Upper-case tokens a skill may quote that are not finding codes. One line each, with why.
NOT_CODES = {
    "DGF_WORKSPACES_ROOT_PATH",  # DGF's environment variable for the workspaces root (composition-specs §1.2)
    "LOG_LEVEL",                 # LOG_LEVEL=debug turns on a script's trace, like DEBUG=1
    "CHANGE_STATE",              # a workflow step mode that moves a case to a state (process-model.md §2)
}


def skill_markdown():
    return sorted(SKILLS.rglob("*.md"))


def logical_lines(text):
    """(first line number, text) with shell `\\` continuations joined, so a flag on the next line counts."""
    joined, start, parts = [], None, []
    for number, line in enumerate(text.splitlines(), 1):
        start = start or number
        if line.rstrip().endswith("\\"):
            parts.append(line.rstrip()[:-1])
            continue
        joined.append((start, " ".join(parts + [line])))
        start, parts = None, []
    return joined


def doctor_ids():
    """The finding ids doctor.py emits: every error("…") and warn("…") call."""
    return set(re.findall(r'(?:error|warn)\("([A-Z0-9_]+)"', DOCTOR.read_text(encoding="utf-8")))


def help_text(script):
    proc = subprocess.run([sys.executable, str(helpers.PLUGIN_ROOT / script), "--help"],
                          capture_output=True, text=True)
    return proc.returncode, proc.stdout


class FindingCodes(unittest.TestCase):
    def test_every_quoted_code_is_one_a_script_emits(self):
        known = set(report.CODES) | doctor_ids() | NOT_CODES
        for path in skill_markdown():
            text = path.read_text(encoding="utf-8")
            for number, line in enumerate(text.splitlines(), 1):
                for token in BACKTICKED.findall(line):
                    if CODE_TOKEN.match(token):
                        self.assertTrue(token in known, f"{path.relative_to(helpers.PLUGIN_ROOT)}:{number} quotes "
                                                        f"`{token}`, which no script emits")

    def test_the_skills_quote_the_spine_codes(self):
        quoted = set()
        for path in skill_markdown():
            quoted |= {t for t in BACKTICKED.findall(path.read_text(encoding="utf-8")) if CODE_TOKEN.match(t)}
        for code in ("PLAN_NOT_FOUND", "PLAN_FALLBACK", "PLAN_OVERLAP", "PRE_EXISTING", "ROOT_NOT_SET_UP",
                     "VALIDATOR_DEPS_MISSING", "PARITY_PARTIAL"):
            self.assertIn(code, quoted, f"no skill tells the model what `{code}` means")


class ScriptFlags(unittest.TestCase):
    def calls(self):
        """{script path: {flag: first `file:line` that passes it}} across the shipped skills."""
        found = {}
        for path in skill_markdown():
            for number, line in logical_lines(path.read_text(encoding="utf-8")):
                match = SCRIPT_CALL.search(line)
                if not match:
                    continue
                flags = found.setdefault(match.group(1), {})
                for flag in FLAG.findall(match.group(2)):
                    flags.setdefault(flag, f"{path.relative_to(helpers.PLUGIN_ROOT)}:{number}")
        return found

    def test_every_called_script_exists(self):
        for script in self.calls():
            self.assertTrue((helpers.PLUGIN_ROOT / script).is_file(), script)

    def test_every_flag_a_skill_passes_is_in_the_scripts_help(self):
        for script, flags in self.calls().items():
            if not flags:
                continue
            code, text = help_text(script)
            self.assertEqual(code, 0, f"{script} --help exited {code}")
            for flag, where in flags.items():
                self.assertRegex(text, rf"(?<![\w-]){re.escape(flag)}(?![\w-])",
                                 f"{where} passes `{flag}`, which {script} --help does not list")

    def test_the_skills_call_the_spine_scripts(self):
        called = {Path(script).name for script in self.calls()}
        for name in ("locate_plan.py", "check_plan.py", "check_change.py", "inventory_root.py", "route_means.py",
                     "verify_gate.py", "check_override.py", "check_patches.py"):
            self.assertIn(name, called)


OVERRIDE_LIMIT = ("An override may add rules and tighten checks. It never relaxes a STOP, an exit-code row, the "
                  "status a gate script computes, a Critical Rule or Artifact Ownership, and never makes this skill "
                  "install anything, skip a script, or write outside its own artifacts. Name the override in your "
                  "report, and quote any rule in it you did not apply because it would relax one of these")
OVERRIDE_WRITER_LIMIT = ("Every rule you write may only tighten its skill: add a rule or a check. It never relaxes a "
                         "STOP, an exit-code row, the status a gate script computes, a Critical Rule or Artifact "
                         "Ownership, and never makes a skill install anything, skip a script, or write outside its "
                         "own artifacts. Refuse a prevention point that would, and log it with its patch.")
TARGETS = re.compile(r"^\*\*Targets:\*\* (.+)$", re.MULTILINE)
CHECK_OVERRIDE = re.compile(r'check_override\.py" --workspaces-root "<root>" --skill ([a-z0-9-]+)')
READERS = ["dgf", "dgf-commit", "dgf-fix", "dgf-implement", "dgf-plan", "dgf-verify"]
WRITER = "dgf-evolve"


def readers():
    """{skill: the --skill values it passes} for every SKILL.md that runs check_override.py."""
    found = {}
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        passed = CHECK_OVERRIDE.findall(path.read_text(encoding="utf-8"))
        if passed:
            found[path.parent.name] = passed
    return found


class Overrides(unittest.TestCase):
    """A committed skill-context file is repository content anyone can write: it may only tighten a skill (ADR 0021)."""

    def test_the_readers_are_the_skills_that_check_their_override(self):
        self.assertEqual(list(readers()), READERS)

    def test_each_reader_checks_its_own_override_and_limits_it(self):
        for name, passed in readers().items():
            text = " ".join((SKILLS / name / "SKILL.md").read_text(encoding="utf-8").split())
            self.assertEqual(set(passed), {name}, f"{name} checks another skill's override")
            self.assertIn(OVERRIDE_LIMIT, text, f"{name} reads an override without its limits")
            self.assertNotIn("override this file", text, f"{name} still lets an override win outright")

    def test_the_writer_limits_itself_and_targets_exactly_the_readers(self):
        text = (SKILLS / WRITER / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(OVERRIDE_WRITER_LIMIT, " ".join(text.split()))
        targets = TARGETS.findall(text)
        self.assertEqual(len(targets), 1, "dgf-evolve needs exactly one **Targets:** line")
        self.assertEqual(BACKTICKED.findall(targets[0]), READERS)
        self.assertIn("check_override.py", text)
        self.assertNotIn("--skill dgf-evolve", text, "dgf-evolve reads no override of its own")

    def test_no_skill_reads_an_override_unchecked(self):
        checked = set(readers()) | {WRITER}
        for path in sorted(SKILLS.glob("*/SKILL.md")):
            text = path.read_text(encoding="utf-8")
            if "skill-context/" in text or "skill_context" in text:
                self.assertIn(path.parent.name, checked, f"{path.parent.name} names an override but never runs "
                                                         f"check_override.py")


BASH_RULE = re.compile(r"Bash\(([^)]*)\)")
PLUGIN_PYTHON = re.compile(r'python3 "\$\{CLAUDE_PLUGIN_ROOT\}/.*')
GIT_COMMAND = re.compile(r"`git |^\s*git |git -C ", re.MULTILINE)
READ_ONLY = ("dgf-doctor", "dgf-verify")
NO_GIT = READ_ONLY + ("dgf-evolve", "dgf-fix")  # /dgf-fix's git reads are check_change.py's; /dgf-evolve needs none


def bash_rules(skill_md):
    """The Bash(…) rule bodies in a SKILL.md's `allowed-tools` frontmatter line."""
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    front = lines[1:lines.index("---", 1)]
    return [rule for line in front if line.startswith("allowed-tools:") for rule in BASH_RULE.findall(line)]


def matches(rule, command):
    """Claude Code's reading of a rule: its text as written, with `*` standing in for anything."""
    return re.fullmatch(re.escape(rule).replace(r"\*", ".*"), command) is not None


class Permissions(unittest.TestCase):
    """`allowed-tools` pre-approves; it pre-approves only what each skill runs (plan D7)."""

    def skills(self):
        return sorted(SKILLS.glob("*/SKILL.md"))

    def test_no_skill_pre_approves_every_python_command(self):
        for path in self.skills():
            self.assertNotIn("python3 *", bash_rules(path), f"{path.parent.name} pre-approves `python3 -c …`")

    def test_every_plugin_script_call_matches_a_rule_of_its_skill(self):
        for path in self.skills():
            rules = bash_rules(path)
            for doc in [path] + sorted((path.parent / "references").glob("*.md")):
                for number, line in logical_lines(doc.read_text(encoding="utf-8")):
                    call = PLUGIN_PYTHON.search(line)
                    if not call or line.startswith("allowed-tools:"):
                        continue
                    self.assertTrue(any(matches(rule, call.group(0)) for rule in rules),
                                    f"{doc.relative_to(helpers.PLUGIN_ROOT)}:{number} runs `{call.group(0)}`, "
                                    f"which no Bash rule of {path.parent.name} pre-approves")

    def test_the_skills_without_git_run_none(self):
        for name in NO_GIT:
            path = SKILLS / name / "SKILL.md"
            self.assertFalse([r for r in bash_rules(path) if r.startswith("git")], f"{name} pre-approves git")
            for doc in [path] + sorted((path.parent / "references").glob("*.md")):
                self.assertIsNone(GIT_COMMAND.search(doc.read_text(encoding="utf-8")),
                                  f"{doc.relative_to(helpers.PLUGIN_ROOT)} runs git, but {name} pre-approves none")


if __name__ == "__main__":
    unittest.main()
