"""The maintainer skill .claude/skills/dgf-sync/ (ADR 0036 §7): its frontmatter, its grants, and the tools it names.

Not a shipped skill, so tests/test_skill_contracts.py does not cover it. It is held to the same rules where they
apply: every Bash rule names one script (ADR 0035), nothing pre-approves git, and every tool, reference and
command it names exists.
"""

import re
import unittest

from tests import helpers

SKILL_DIR = helpers.PLUGIN_ROOT / ".claude" / "skills" / "dgf-sync"
SKILL = SKILL_DIR / "SKILL.md"
ALLOWED_COMMANDS = ("python3 -m unittest *", "bash tools/check-dual-schema-docs.sh")


def frontmatter(text):
    lines = text.splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    fields = {}
    for line in lines[1:end]:
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, "\n".join(lines[end + 1:])


class DgfSync(unittest.TestCase):
    def setUp(self):
        self.fields, self.body = frontmatter(SKILL.read_text(encoding="utf-8"))
        self.rules = re.findall(r"Bash\(([^)]*)\)", self.fields["allowed-tools"])

    def test_frontmatter(self):
        self.assertEqual(self.fields["name"], "dgf-sync")
        for key in ("description", "argument-hint", "allowed-tools", "version"):
            self.assertTrue(self.fields.get(key), key)

    def test_every_bash_rule_names_one_existing_script_and_none_is_git(self):
        self.assertTrue(self.rules)
        for rule in self.rules:
            with self.subTest(rule=rule):
                self.assertNotRegex(rule, r"(^|\s)git(\s|$)", "ADR 0035: no skill pre-approves git")
                if rule in ALLOWED_COMMANDS:
                    continue
                match = re.fullmatch(r"python3 ((?:tools|skills)/[\w./-]+\.py) \*", rule)
                self.assertIsNotNone(match, f"`{rule}` does not name exactly one script")
                self.assertTrue((helpers.PLUGIN_ROOT / match.group(1)).is_file(), match.group(1))

    def test_every_command_in_the_body_is_granted(self):
        granted = {re.sub(r" \*$", "", rule) for rule in self.rules}
        for command in sorted(set(re.findall(r"^(python3 (?:tools|skills)/[\w./-]+\.py|bash [\w./-]+)", self.body, re.M))):
            with self.subTest(command=command):
                self.assertIn(command, granted)

    def test_every_dgf_lines_subcommand_it_uses_exists(self):
        source = (helpers.TOOLS / "dgf_lines.py").read_text(encoding="utf-8")
        for sub in sorted(set(re.findall(r"tools/dgf_lines\.py (\w+)", self.body))):
            with self.subTest(subcommand=sub):
                self.assertIn(f'sub.add_parser("{sub}")', source)

    def test_its_references_exist(self):
        for name in sorted(set(re.findall(r"references/([\w.-]+\.md)", self.body))):
            with self.subTest(reference=name):
                self.assertTrue((SKILL_DIR / "references" / name).is_file(), name)

    def test_it_is_not_shipped(self):
        self.assertFalse((helpers.PLUGIN_ROOT / "skills" / "dgf-sync").exists())


if __name__ == "__main__":
    unittest.main()
