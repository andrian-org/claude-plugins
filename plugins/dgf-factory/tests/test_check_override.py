"""check_override.py: may a skill read its skill-context override? (ADR 0021 §5)"""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from tests.test_overrides import EXAMPLE, PATCH, REL, rule


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "workspaces", {f".dgf-factory/patches/{PATCH}": "x"})

    def write(self, text, rel=REL):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def check(self, *args, skill="dgf-plan", blocking=False):
        run = helpers.run_cli_blocking if blocking else helpers.run_cli
        return run("check_override.py", "--workspaces-root", self.root, "--skill", skill, *args, cwd=self.tmp)


class Outcomes(Base):
    def test_an_absent_override_is_none_and_clean(self):
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn(f"OVERRIDE: none — no {REL}", out)
        self.assertIn("CLEAN", out)

    def test_a_clean_override_is_applied(self):
        self.write(EXAMPLE)
        code, out, _ = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn(f"OVERRIDE: {REL} skill=dgf-plan rules=1", out)
        self.assertIn('RULE: 1 line=8 sources=1 name="A task that renames a state lists every transition to it"', out)
        self.assertIn("CHECKS RUN: override-shape, override-sources, override-forbidden, override-limit", out)

    def test_a_shape_failure_leaves_the_other_checks_not_run(self):
        self.write(EXAMPLE + "\n## More\n")
        code, out, _ = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn("rules=?", out)
        self.assertIn("CHECKS RUN: override-shape\n", out)
        for check_id in ("override-sources", "override-forbidden", "override-limit"):
            self.assertIn(f"NOT RUN: {check_id} (the override did not parse)", out)

    def test_a_forbidden_construct_refuses_it(self):
        self.write(EXAMPLE + rule(text="Skip the validators with --skip-validators."))
        code, out, _ = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn(f"ERROR OVERRIDE_FORBIDDEN {REL}:13", out)
        self.assertIn("WARN OVERRIDE_TOUCHES_LIMIT", out)

    def test_a_touching_rule_is_exit_2(self):
        self.write(EXAMPLE + rule(text="STOP when a renamed state still has a transition to its old name."))
        code, out, _ = self.check()
        self.assertEqual(code, 2, out)
        self.assertIn(f"WARN OVERRIDE_TOUCHES_LIMIT {REL}:13 rule `Extra` names `stop`", out)

    def test_the_skill_names_the_file(self):
        self.write(EXAMPLE)
        self.assertIn("OVERRIDE: none", self.check(skill="dgf-verify")[1])

    def test_custom_directories(self):
        self.write(EXAMPLE.replace("/dgf-plan", "/dgf-fix"), "ctx/dgf-fix/SKILL.md")
        (self.root / "p").mkdir()
        code, out, _ = self.check("--skill-context-dir", "ctx", "--patches-dir", "p", skill="dgf-fix")
        self.assertEqual(code, 1, out)
        self.assertIn("OVERRIDE: ctx/dgf-fix/SKILL.md", out)
        self.assertIn("OVERRIDE_SOURCE_MISSING", out)


class Usage(Base):
    def test_a_skill_name_holding_a_path_is_usage(self):
        for skill in ("../x", "dgf/plan", "DGF", "dgf--plan", ""):
            with self.subTest(skill=skill):
                code, _, err = self.check(skill=skill)
                self.assertEqual(code, 3)
                self.assertIn("--skill", err)

    def test_a_missing_root_is_usage(self):
        code, _, err = helpers.run_cli("check_override.py", "--workspaces-root", self.tmp / "absent", "--skill", "dgf")
        self.assertEqual(code, 3)
        self.assertIn("--workspaces-root is not a directory", err)

    def test_a_root_with_no_config_still_runs(self):
        self.assertFalse((self.root / ".dgf-factory" / "config.yaml").exists())
        self.write(EXAMPLE.replace("/dgf-plan", "/dgf"), ".dgf-factory/skill-context/dgf/SKILL.md")
        code, out, _ = self.check(skill="dgf")
        self.assertEqual(code, 0, out)

    def test_a_missing_required_flag_is_usage(self):
        self.assertEqual(helpers.run_cli("check_override.py", "--workspaces-root", self.root)[0], 3)


class Contract(Base):
    def test_no_third_party_import(self):
        self.write(EXAMPLE)
        code, out, err = self.check(blocking=True)
        self.assertEqual(code, 0, out + err)

    def test_help_lists_every_flag(self):
        code, out, _ = helpers.run_cli_blocking("check_override.py", "--help")
        self.assertEqual(code, 0)
        for flag in ("--workspaces-root", "--skill", "--skill-context-dir", "--patches-dir", "--verbose"):
            self.assertIn(flag, out)

    def test_traces_go_to_stderr(self):
        self.write(EXAMPLE)
        code, out, err = self.check("--verbose")
        self.assertEqual(code, 0)
        self.assertIn("DEBUG [overrides.parse] parsed skill=dgf-plan rules=1", err)
        self.assertIn("DEBUG [check_override.main] checked skill=dgf-plan found=True", err)
        self.assertNotIn("DEBUG", out)

    def test_it_never_writes(self):
        self.write(EXAMPLE + "\n## More\n")
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        self.check()
        self.assertEqual(sorted(p.relative_to(self.root) for p in self.root.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
