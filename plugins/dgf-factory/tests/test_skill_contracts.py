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
        for name in ("locate_plan.py", "check_plan.py", "check_change.py", "inventory_root.py", "route_means.py"):
            self.assertIn(name, called)


if __name__ == "__main__":
    unittest.main()
